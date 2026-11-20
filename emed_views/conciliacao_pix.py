# -*- coding: utf-8 -*-
"""
Módulo de Conciliação Bancária & Pagamentos PIX para o Sistema EMED.
Permite emissão de cobranças com QR Code PIX oficial padrão Banco Central (EMV/BRCode),
acompanhamento de liquidações, simulação de webhooks de pagamento e conciliação financeira de OS.
"""

import os
import io
import re
import unicodedata
import base64
import sqlite3
import datetime
import pandas as pd
import streamlit as st
import qrcode
from emed_core import limpar_texto, obter_id_os
from emed_services import AppContext


def _sanitizar_texto_emv(texto: str, max_chars: int) -> str:
    """Sanitiza texto removendo acentos para conformidade estrita com o padrão EMV/Pix."""
    if not texto:
        return ""
    texto_norm = unicodedata.normalize('NFKD', str(texto))
    texto_ascii = "".join(c for c in texto_norm if not unicodedata.combining(c))
    texto_limpo = "".join(c for c in texto_ascii if c.isalnum() or c in " .-_")
    return texto_limpo.strip()[:max_chars].upper()


def _calcular_crc16(payload: str) -> str:
    """Calcula o checksum CRC16 (CCITT-FALSE 0x1021) obrigatório na especificação EMV do PIX."""
    polinomio = 0x1021
    resultado = 0xFFFF
    dados = (payload + "6304").encode("utf-8")
    for b in dados:
        resultado ^= (b << 8)
        for _ in range(8):
            if resultado & 0x8000:
                resultado = ((resultado << 1) ^ polinomio) & 0xFFFF
            else:
                resultado = (resultado << 1) & 0xFFFF
    return f"{resultado:04X}"


def gerar_payload_pix(chave: str, nome_recebedor: str, cidade: str, valor: float, txid: str = "***") -> str:
    """Gera a string 'Copia e Cola' oficial no padrão BR Code do Banco Central do Brasil."""
    chave = chave.strip()
    nome = _sanitizar_texto_emv(nome_recebedor, 25)
    cidade = _sanitizar_texto_emv(cidade, 15)
    txid = (txid or "***").strip()[:25]

    gui = "0014br.gov.bcb.pix"
    campo_chave = f"01{len(chave.encode('utf-8')):02d}{chave}"
    campo_26 = f"{gui}{campo_chave}"
    bloco_26 = f"26{len(campo_26.encode('utf-8')):02d}{campo_26}"

    bloco_mcc = "52040000"
    bloco_moeda = "5303986"

    str_val = f"{valor:.2f}"
    bloco_valor = f"54{len(str_val.encode('utf-8')):02d}{str_val}"

    bloco_pais = "5802BR"
    bloco_nome = f"59{len(nome.encode('utf-8')):02d}{nome}"
    bloco_cidade = f"60{len(cidade.encode('utf-8')):02d}{cidade}"

    campo_txid = f"05{len(txid.encode('utf-8')):02d}{txid}"
    bloco_62 = f"62{len(campo_txid.encode('utf-8')):02d}{campo_txid}"

    payload_sem_crc = f"000201{bloco_26}{bloco_mcc}{bloco_moeda}{bloco_valor}{bloco_pais}{bloco_nome}{bloco_cidade}{bloco_62}"
    crc = _calcular_crc16(payload_sem_crc)
    return f"{payload_sem_crc}6304{crc}"


def gerar_qr_code_pix_base64(payload_pix: str) -> str:
    """Renderiza a imagem do QR Code a partir do payload PIX e retorna em formato base64 para o Streamlit."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(payload_pix)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b132b", back_color="#ffffff")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{b64_str}"


def inicializar_tabela_pix(db_name: str):
    """Garante a existência da tabela pagamentos_pix no SQLite."""
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagamentos_pix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                os_id TEXT,
                cliente TEXT,
                cnpj TEXT,
                valor REAL,
                chave_pix TEXT,
                status_pagamento TEXT,
                txid TEXT,
                e2e_id TEXT,
                data_geracao TEXT,
                data_pagamento TEXT,
                metodo TEXT
            )
        """)
        conn.commit()


def liquidar_pagamento_pix(db_name: str, os_id: str, txid: str = "", metodo: str = "SIMULAÇÃO_WEBHOOK_INSTANTANEO", valor_recebido: float = 0.0, e2e_id_externo: str = "") -> tuple[bool, str]:
    """Liquida o pagamento da OS de forma atômica, atualizando pagamentos_pix, notas_fiscais e clientes_equipamentos."""
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e2e_id = e2e_id_externo.strip() if e2e_id_externo else f"E2E{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(3).hex().upper()}"
    try:
        os_id_num = re.sub(r'\D', '', str(os_id))
        target_os_id = int(os_id_num) if os_id_num else os_id

        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            if e2e_id_externo:
                dup = cursor.execute("SELECT os_id FROM pagamentos_pix WHERE e2e_id = ? AND UPPER(status_pagamento) = 'PAGO'", (e2e_id,)).fetchone()
                if dup:
                    return True, f"Transação já conciliada anteriormente na OS #{dup[0]} (Idempotência E2E: {e2e_id})."

            info_nf = cursor.execute(
                "SELECT cliente, cnpj_tomador, valor_liquido FROM notas_fiscais WHERE os_id = ? OR os_id = ? ORDER BY id DESC LIMIT 1",
                (str(os_id), target_os_id),
            ).fetchone()
            info_os = cursor.execute(
                "SELECT cliente, valor_os FROM clientes_equipamentos WHERE id = ?",
                (target_os_id,),
            ).fetchone() if isinstance(target_os_id, int) else None

            cli_nome = (info_nf[0] if info_nf and info_nf[0] else (info_os[0] if info_os and info_os[0] else "CLIENTE EMED"))
            cli_cnpj = (info_nf[1] if info_nf and info_nf[1] else "")
            val_final = float(valor_recebido or (info_nf[2] if info_nf and info_nf[2] else (info_os[1] if info_os and info_os[1] else 0.0)))

            cursor.execute("SELECT id FROM pagamentos_pix WHERE os_id = ? OR os_id = ?", (str(os_id), str(target_os_id)))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE pagamentos_pix
                    SET status_pagamento = 'PAGO',
                        valor = CASE WHEN ? > 0 THEN ? ELSE valor END,
                        data_pagamento = ?,
                        e2e_id = ?,
                        metodo = ?
                    WHERE id = ?
                """, (val_final, val_final, agora, e2e_id, metodo, row[0]))
            else:
                cursor.execute("""
                    INSERT INTO pagamentos_pix (os_id, cliente, cnpj, valor, chave_pix, status_pagamento, txid, e2e_id, data_geracao, data_pagamento, metodo)
                    VALUES (?, ?, ?, ?, 'financeiro@emed.med.br', 'PAGO', ?, ?, ?, ?, ?)
                """, (str(target_os_id), cli_nome, cli_cnpj, val_final, txid, e2e_id, agora, agora, metodo))

            cursor.execute("""
                UPDATE notas_fiscais
                SET status_fiscal = 'LIQUIDADO / PAGO VIA PIX',
                    atualizado_em = ?
                WHERE (os_id = ? OR os_id = ?) AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%'
            """, (agora, target_os_id, str(os_id)))

            if isinstance(target_os_id, int):
                cursor.execute("""
                    UPDATE clientes_equipamentos
                    SET condicao_pagamento = 'PAGO / LIQUIDADO (' || ? || ')'
                    WHERE id = ?
                """, (metodo[:35], target_os_id))

            conn.commit()
        return True, f"Pagamento da OS #{target_os_id} ({cli_nome}) confirmado com sucesso via {metodo}! E2E ID: {e2e_id}"
    except Exception as e:
        return False, f"Erro ao liquidar pagamento: {str(e)}"


def conciliar_pagamento_bancario_duplo(
    db_name: str,
    cnpj: str = "",
    valor: float = 0.0,
    txid: str = "",
    end_to_end_id: str = "",
    nome_pagador: str = ""
) -> dict:
    """Realiza a conciliação bancária blindada em 4 camadas para evitar erro de baixa:
    1ª Camada (Determinística): Via TXID / Identificador único da OS ou NF (ex: EMED-OS-41).
    2ª Camada (Dupla Checagem Fiscal): CNPJ limpo do Tomador + Valor (Líquido, Bruto ou com Retenção de ISS).
    3ª Camada (Cruzamento Nominal): Nome/Razão Social do Pagador + Valor exato (tolerância R$ 0,05).
    4ª Camada (Trava Anti-Homônimo): Se apenas o valor bater, só baixa automaticamente se houver
       EXATAMENTE 1 título em aberto com aquele valor. Se houver 2 ou mais títulos de mesmo valor,
       bloqueia a baixa automática e retorna a lista de candidatos para confirmação manual segura."""
    inicializar_tabela_pix(db_name)
    os_id_encontrado = ""
    cliente_encontrado = nome_pagador or "CLIENTE NÃO IDENTIFICADO"
    camada_match = ""
    candidatos_ambiguos = []
    valor_float = float(valor or 0.0)
    cnpj_limpo = re.sub(r"\D", "", str(cnpj or ""))
    nome_norm = str(nome_pagador or "").strip().upper()

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()

        if end_to_end_id:
            dup = cur.execute("SELECT os_id, cliente FROM pagamentos_pix WHERE e2e_id = ? AND UPPER(status_pagamento) = 'PAGO'", (end_to_end_id.strip(),)).fetchone()
            if dup:
                return {
                    "conciliado": True,
                    "os_id": str(dup[0]),
                    "cliente": dup[1] or cliente_encontrado,
                    "valor": valor_float,
                    "camada": "IDEMPOTENCIA_E2E",
                    "mensagem": f"Transação E2E {end_to_end_id} já estava conciliada na OS #{dup[0]}."
                }

        if txid:
            match = re.search(r'(?:OS[-_]?|^)(\d+)', txid.upper())
            if match:
                candidato_os = match.group(1)
                row = cur.execute(
                    "SELECT os_id, cliente, valor_liquido FROM notas_fiscais WHERE (os_id = ? OR os_id = ?) AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%' ORDER BY id DESC LIMIT 1",
                    (candidato_os, int(candidato_os)),
                ).fetchone()
                if not row:
                    row_os = cur.execute("SELECT id, cliente, valor_os FROM clientes_equipamentos WHERE id = ?", (int(candidato_os),)).fetchone()
                    if row_os:
                        row = (row_os[0], row_os[1], row_os[2])
                if row:
                    os_id_encontrado = str(row[0])
                    cliente_encontrado = row[1] or cliente_encontrado
                    camada_match = "NIVEL_1_TXID_EXATO"

        if not os_id_encontrado and valor_float > 0:
            abertas = cur.execute("""
                SELECT os_id, cliente, COALESCE(cnpj_tomador, ''), COALESCE(valor_liquido, 0),
                       COALESCE(valor_servicos, 0) + COALESCE(valor_pecas, 0) - COALESCE(valor_desconto, 0) as valor_bruto,
                       COALESCE(valor_iss, 0), COALESCE(numero_nf, '')
                FROM notas_fiscais
                WHERE UPPER(COALESCE(status_fiscal, '')) NOT LIKE '%LIQUIDAD%'
                  AND UPPER(COALESCE(status_fiscal, '')) NOT LIKE '%PAGO%'
                  AND UPPER(COALESCE(status_fiscal, '')) NOT LIKE '%CANCELAD%'
            """).fetchall()

            def _valor_bate(r_row) -> bool:
                v_liq = float(r_row[3] or 0.0)
                v_bruto = float(r_row[4] or v_liq)
                v_iss = float(r_row[5] or 0.0)
                v_com_retencao_iss = max(0.0, v_liq - v_iss)
                v_pix_10_desc = round(v_liq * 0.90, 2)
                return any(abs(v_cand - valor_float) <= 0.05 for v_cand in (v_liq, v_bruto, v_com_retencao_iss, v_pix_10_desc) if v_cand > 0)

            if cnpj_limpo:
                matches_cnpj = [r for r in abertas if re.sub(r"\D", "", str(r[2] or "")) == cnpj_limpo and _valor_bate(r)]
                if len(matches_cnpj) == 1:
                    os_id_encontrado = str(matches_cnpj[0][0])
                    cliente_encontrado = matches_cnpj[0][1] or cliente_encontrado
                    camada_match = "NIVEL_2_CNPJ_E_VALOR"
                elif len(matches_cnpj) > 1:
                    candidatos_ambiguos = [{"os_id": str(m[0]), "cliente": m[1], "nf": m[6], "valor": float(m[3])} for m in matches_cnpj]

            if not os_id_encontrado and not candidatos_ambiguos and nome_norm:
                tokens_pag = [t for t in re.split(r"\s+", nome_norm) if len(t) >= 4 and t not in ("HOSPITAL", "CLINICA", "LTDA", "EIRELI", "SAUDE", "INSTITUTO")]
                matches_nome = []
                for r in abertas:
                    if not _valor_bate(r):
                        continue
                    cli_up = str(r[1] or "").upper()
                    if nome_norm in cli_up or cli_up in nome_norm or (tokens_pag and any(tk in cli_up for tk in tokens_pag)):
                        matches_nome.append(r)
                if len(matches_nome) == 1:
                    os_id_encontrado = str(matches_nome[0][0])
                    cliente_encontrado = matches_nome[0][1] or cliente_encontrado
                    camada_match = "NIVEL_3_RAZAO_SOCIAL_E_VALOR"
                elif len(matches_nome) > 1:
                    candidatos_ambiguos = [{"os_id": str(m[0]), "cliente": m[1], "nf": m[6], "valor": float(m[3])} for m in matches_nome]

            if not os_id_encontrado and not candidatos_ambiguos:
                matches_valor = [r for r in abertas if _valor_bate(r)]
                if len(matches_valor) == 1:
                    os_id_encontrado = str(matches_valor[0][0])
                    cliente_encontrado = matches_valor[0][1] or cliente_encontrado
                    camada_match = "NIVEL_4_VALOR_UNIVOCO"
                elif len(matches_valor) > 1:
                    candidatos_ambiguos = [{"os_id": str(m[0]), "cliente": m[1], "nf": m[6], "valor": float(m[3])} for m in matches_valor]

    if os_id_encontrado:
        sucesso, msg = liquidar_pagamento_pix(
            db_name,
            os_id=os_id_encontrado,
            txid=txid,
            metodo=f"{camada_match} (E2E: {end_to_end_id or 'N/A'})",
            valor_recebido=valor_float,
            e2e_id_externo=end_to_end_id,
        )
        return {
            "conciliado": sucesso,
            "status_conciliacao": "CONCILIADO",
            "camada": camada_match,
            "os_id": os_id_encontrado,
            "cliente": cliente_encontrado,
            "valor": valor_float,
            "mensagem": msg
        }

    if candidatos_ambiguos:
        return {
            "conciliado": False,
            "status_conciliacao": "QUARENTENA_AMBIGUIDADE",
            "os_id": "",
            "cliente": cliente_encontrado,
            "valor": valor_float,
            "candidatos": candidatos_ambiguos,
            "mensagem": f"⚠️ TRAVA ANTI-ERRO ATIVADA: Existem {len(candidatos_ambiguos)} títulos em aberto compatíveis com R$ {valor_float:,.2f}. Selecione manualmente a OS correta para evitar baixa trocada."
        }

    return {
        "conciliado": False,
        "status_conciliacao": "NAO_LOCALIZADO",
        "os_id": "",
        "cliente": cliente_encontrado,
        "valor": valor_float,
        "mensagem": "Pagamento recebido mas não vinculado automaticamente a nenhuma OS em aberto."
    }


def render_conciliacao_pix(ctx: AppContext):
    """Visão Completa do Módulo de Conciliação Bancária & Pagamentos PIX."""
    db_name = ctx.db_name
    inicializar_tabela_pix(db_name)

    st.markdown("""
        <div style="background: linear-gradient(135deg, #092c3e 0%, #0e4b5c 50%, #1a365d 100%);
                    border-radius: 12px; padding: 18px 24px; border: 1.5px solid #00b4d8;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="color: #90e0ef; margin: 0; font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        💳 CONCILIAÇÃO BANCÁRIA & COBRANÇA PIX
                        <span style="font-size: 13px; background: #00b4d8; color: #03045e; padding: 3px 8px; border-radius: 6px; font-weight: 800;">Banco Central / EMV</span>
                    </h2>
                    <p style="color: #caf0f8; margin: 6px 0 0 0; font-size: 13.5px;">
                        Emissão de QR Code PIX dinâmico/estático, conciliação automática com faturamento de OS e simulação de webhooks bancários em tempo real.
                    </p>
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">INTEGRAÇÃO PIX</div>
                    <div style="font-size: 14px; font-weight: 800; color: #48cae4;">🟢 ONLINE / CONCILIADO</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Coleta dados consolidados de notas_fiscais e pagamentos_pix
    with sqlite3.connect(db_name) as conn:
        df_nf = pd.read_sql_query("SELECT * FROM notas_fiscais", conn)
        df_pix = pd.read_sql_query("SELECT * FROM pagamentos_pix ORDER BY id DESC", conn)

    # Cálculos dos Big KPIs
    total_faturado = float(df_nf["valor_liquido"].sum()) if not df_nf.empty and "valor_liquido" in df_nf.columns else 0.0
    
    # Total recebido via PIX ou liquidado
    df_pagos = df_pix[df_pix["status_pagamento"].str.upper() == "PAGO"] if not df_pix.empty else pd.DataFrame()
    total_liquidado_pix = float(df_pagos["valor"].sum()) if not df_pagos.empty else 0.0

    # Total em aberto
    total_pendente = max(0.0, total_faturado - total_liquidado_pix)
    taxa_conciliacao = (total_liquidado_pix / total_faturado * 100) if total_faturado > 0 else 100.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #00b4d8; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">TOTAL FATURADO (OS)</div>
                <div style="color: #f8fafc; font-size: 22px; font-weight: 800;">R$ {total_faturado:,.2f}</div>
                <div style="color: #38bdf8; font-size: 11px; margin-top: 2px;">{len(df_nf)} faturas emitidas</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #10b981; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">LIQUIDADO / RECEBIDO (PIX)</div>
                <div style="color: #10b981; font-size: 22px; font-weight: 800;">R$ {total_liquidado_pix:,.2f}</div>
                <div style="color: #6ee7b7; font-size: 11px; margin-top: 2px;">{len(df_pagos)} liquidações confirmadas</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #f59e0b; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">PENDENTE DE CONCILIAÇÃO</div>
                <div style="color: #f59e0b; font-size: 22px; font-weight: 800;">R$ {total_pendente:,.2f}</div>
                <div style="color: #fcd34d; font-size: 11px; margin-top: 2px;">Aguardando liquidação</div>
            </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #a855f7; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">TAXA DE LIQUIDAÇÃO</div>
                <div style="color: #c084fc; font-size: 22px; font-weight: 800;">{taxa_conciliacao:.1f}%</div>
                <div style="color: #d8b4fe; font-size: 11px; margin-top: 2px;">Eficiência de cobrança</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    tab_pix_cob, tab_pix_extrato, tab_pix_cfg = st.tabs([
        "⚡ 1. Cobrança & Geração de QR Code PIX",
        "📋 2. Extrato de Conciliação em Tempo Real",
        "⚙️ 3. Configuração de Chave & Gateway",
    ])

    # =========================================================================
    # TAB 1: COBRANÇA & GERAÇÃO DE QR CODE PIX
    # =========================================================================
    with tab_pix_cob:
        col_form, col_qr = st.columns([1.5, 1.5])
        with col_form:
            st.markdown("#### 📝 Dados da Ordem de Serviço para Cobrança")
            # Lista as OS disponíveis para faturamento ou cobrança
            df_chamados = ctx.df
            opcoes_os = []
            for idx, r in df_chamados.iterrows():
                os_num = obter_id_os(idx, r)
                cli_nome = limpar_texto(r.get("cliente"), "CLIENTE")
                status_os = limpar_texto(r.get("status"), "ATIVO")
                opcoes_os.append(f"OS #{os_num} — {cli_nome} [{status_os}]")

            sel_os_str = st.selectbox("Selecione a Ordem de Serviço:", opcoes_os)
            os_id_sel = sel_os_str.split("—")[0].replace("OS #", "").strip()

            # Puxa dados da OS selecionada
            dados_os_match = df_chamados[df_chamados.index.astype(str) == os_id_sel]
            if dados_os_match.empty:
                # Tenta match pela coluna se for id numérico
                dados_os_match = df_chamados.iloc[[int(os_id_sel) % len(df_chamados)]]
            
            linha_os = dados_os_match.iloc[0]
            cli_selecionado = limpar_texto(linha_os.get("cliente"), "EMED CLIENTE")
            cnpj_sel = limpar_texto(linha_os.get("cnpj"), "")

            # Valor padrão
            val_padrao = float(linha_os.get("valor_os", 0.0) or 1500.0)
            if val_padrao <= 0.0:
                val_padrao = 1500.0

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                valor_cobranca = st.number_input("Valor da Fatura (R$):", min_value=1.0, value=val_padrao, step=50.0)
            with col_v2:
                txid_input = st.text_input("Identificador TXID / Ref:", value=f"EMEDOS{os_id_sel}")

            chave_pix_padrao = st.session_state.get("cfg_chave_pix", "financeiro@emed.med.br")
            nome_recebedor = st.session_state.get("cfg_nome_pix", "EMED MANUTENCAO")
            cidade_recebedor = st.session_state.get("cfg_cidade_pix", "FORTALEZA")

            payload_gerado = gerar_payload_pix(
                chave=chave_pix_padrao,
                nome_recebedor=nome_recebedor,
                cidade=cidade_recebedor,
                valor=valor_cobranca,
                txid=txid_input,
            )

        with col_qr:
            st.markdown("#### 📱 QR Code PIX (Copia e Cola)")
            qr_base64 = gerar_qr_code_pix_base64(payload_gerado)
            st.markdown(
                f"""
                <div style="background: #ffffff; padding: 18px; border-radius: 12px; text-align: center; border: 2px solid #00b4d8; max-width: 340px; margin: 0 auto;">
                    <img src="{qr_base64}" style="width: 220px; height: 220px; display: block; margin: 0 auto;"/>
                    <div style="color: #03045e; font-weight: 800; font-size: 18px; margin-top: 10px;">R$ {valor_cobranca:,.2f}</div>
                    <div style="color: #475569; font-size: 12px;">Favorecido: {nome_recebedor}</div>
                    <div style="color: #475569; font-size: 11px;">Chave: {chave_pix_padrao}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.text_area("Código PIX Copia e Cola:", value=payload_gerado, height=75)

        st.markdown("---")
        st.markdown("#### ⚡ Ações de Conciliação e Confirmação de Pagamento")
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🚀 Simular Webhook de Liquidação Instantânea (Banco / Gateway)", type="primary", use_container_width=True):
                ok, msg = liquidar_pagamento_pix(db_name, os_id_sel, txid_input, metodo="WEBHOOK_GATEWAY_API")
                if ok:
                    st.success(f"🎉 {msg}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)
        with col_btn2:
            if st.button("✅ Confirmar Recebimento Manual via Comprovante", type="secondary", use_container_width=True):
                ok, msg = liquidar_pagamento_pix(db_name, os_id_sel, txid_input, metodo="MANUAL_COMPROVANTE_BANCARIO")
                if ok:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(msg)

    # =========================================================================
    # TAB 2: EXTRATO DE CONCILIAÇÃO EM TEMPO REAL
    # =========================================================================
    with tab_pix_extrato:
        st.markdown("#### 📋 Histórico Consolidado de Transações e Baixas Financeiras")
        if df_pix.empty:
            st.info("Nenhuma transação PIX registrada até o momento. Gere uma cobrança na aba 1 para iniciar a conciliação.")
        else:
            # Formatação visual do extrato
            df_view = df_pix.copy()
            st.dataframe(
                df_view[["id", "os_id", "valor", "status_pagamento", "data_pagamento", "e2e_id", "metodo"]],
                use_container_width=True,
                column_config={
                    "id": "Reg",
                    "os_id": "OS #",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                    "status_pagamento": st.column_config.TextColumn("Status"),
                    "data_pagamento": "Data/Hora",
                    "e2e_id": "ID E2E Bancário",
                    "metodo": "Método de Baixa",
                }
            )

    # =========================================================================
    # TAB 3: CONFIGURAÇÃO DE CHAVE & GATEWAY
    # =========================================================================
    with tab_pix_cfg:
        st.markdown("#### ⚙️ Parâmetros da Conta de Recebimento da EMED")
        c_k1, c_k2, c_k3 = st.columns(3)
        with c_k1:
            cfg_chave = st.text_input("Chave PIX Oficial:", value=st.session_state.get("cfg_chave_pix", "financeiro@emed.med.br"))
        with c_k2:
            cfg_nome = st.text_input("Nome do Beneficiário:", value=st.session_state.get("cfg_nome_pix", "EMED HOSPITALAR"))
        with c_k3:
            cfg_cid = st.text_input("Cidade da Conta:", value=st.session_state.get("cfg_cidade_pix", "FORTALEZA"))

        if st.button("💾 Salvar Parâmetros PIX", type="primary"):
            st.session_state["cfg_chave_pix"] = cfg_chave
            st.session_state["cfg_nome_pix"] = cfg_nome
            st.session_state["cfg_cidade_pix"] = cfg_cid
            st.success("✅ Configurações de recebimento PIX atualizadas com sucesso!")
