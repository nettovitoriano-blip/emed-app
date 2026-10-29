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


def liquidar_pagamento_pix(db_name: str, os_id: str, txid: str = "", metodo: str = "SIMULAÇÃO_WEBHOOK_INSTANTANEO") -> tuple[bool, str]:
    """Liquida o pagamento da OS, atualizando a tabela pagamentos_pix e o status fiscal de notas_fiscais."""
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e2e_id = f"E2E{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(3).hex().upper()}"
    try:
        os_id_num = re.sub(r'\D', '', str(os_id))
        target_os_id = int(os_id_num) if os_id_num else os_id

        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            # Atualiza ou insere na tabela pagamentos_pix
            cursor.execute("SELECT id FROM pagamentos_pix WHERE os_id = ? OR os_id = ?", (str(os_id), str(target_os_id)))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE pagamentos_pix
                    SET status_pagamento = 'PAGO',
                        data_pagamento = ?,
                        e2e_id = ?,
                        metodo = ?
                    WHERE id = ?
                """, (agora, e2e_id, metodo, row[0]))
            else:
                cursor.execute("""
                    INSERT INTO pagamentos_pix (os_id, cliente, cnpj, valor, chave_pix, status_pagamento, txid, e2e_id, data_geracao, data_pagamento, metodo)
                    VALUES (?, 'CLIENTE EMED', '', 0.0, 'financeiro@emed.med.br', 'PAGO', ?, ?, ?, ?, ?)
                """, (str(os_id), txid, e2e_id, agora, agora, metodo))

            # Atualiza status fiscal em notas_fiscais caso exista
            cursor.execute("""
                UPDATE notas_fiscais
                SET status_fiscal = 'LIQUIDADO / PAGO VIA PIX',
                    atualizado_em = ?
                WHERE os_id = ? OR os_id = ?
            """, (agora, target_os_id, str(os_id)))

            # Atualiza a tabela operacional clientes_equipamentos (para mudar na tela para PAGO)
            cursor.execute("""
                UPDATE clientes_equipamentos
                SET condicao_pagamento = 'PAGO VIA PIX (CONCILIAÇÃO BANCÁRIA)'
                WHERE id = ? OR id = ?
            """, (str(os_id), str(target_os_id)))
            conn.commit()
        return True, f"Pagamento da OS #{os_id} confirmado com sucesso via {metodo}! E2E ID: {e2e_id}"
    except Exception as e:
        return False, f"Erro ao liquidar pagamento: {str(e)}"


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



def conciliar_pagamento_bancario_duplo(db_name: str, cnpj: str = "", valor: float = 0.0, txid: str = "", end_to_end_id: str = "", nome_pagador: str = "") -> dict:
    """
    Inteligência de Conciliação Bancária Automática:
    1º Tenta identificar pelo txid único (PIX padrão BACEN).
    2º Caso seja Pix avulso/TED, cruza o CNPJ do tomador + Valor exato da OS pendente.
    3º Realiza a baixa automática imediata em clientes_equipamentos e notas_fiscais.
    """
    cnpj_limpo = re.sub(r'\D', '', str(cnpj or ""))
    val_float = float(valor or 0.0)
    txid_limpo = str(txid or "").strip()
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    e2e = end_to_end_id or f"E2E{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(3).hex().upper()}"

    os_encontrada = None
    cliente_encontrado = ""

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()

        # 1. Busca por txid se fornecido
        if txid_limpo:
            # Tenta extrair ID numérico do txid (ex: EMED-OS-84 ou PIX_APP_84)
            match_os = re.search(r'OS[-_]?(\d+)', txid_limpo, re.IGNORECASE)
            if match_os:
                cand_id = match_os.group(1)
                cur.execute("SELECT id, cliente, valor_os FROM clientes_equipamentos WHERE id = ?", (cand_id,))
                r = cur.fetchone()
                if r:
                    os_encontrada = str(r[0])
                    cliente_encontrado = str(r[1])

        # 2. Se não achou por txid, faz o Cruzamento Duplo: CNPJ do Pagador + Valor Exato
        if not os_encontrada and val_float > 0:
            # Busca OS aberta compatível com o CNPJ ou nome do cliente
            query = """
                SELECT id, cliente, valor_os 
                FROM clientes_equipamentos 
                WHERE (UPPER(condicao_pagamento) NOT LIKE '%PAGO%' AND UPPER(condicao_pagamento) NOT LIKE '%LIQUIDADO%')
                  AND abs(valor_os - ?) < 0.05
            """
            params = [val_float]

            if cnpj_limpo:
                query += " AND (replace(replace(replace(cnpj, '.', ''), '/', ''), '-', '') = ? OR UPPER(cliente) LIKE ?)"
                params.extend([cnpj_limpo, f"%{str(nome_pagador or '').strip().upper()}%"])
            elif nome_pagador:
                query += " AND UPPER(cliente) LIKE ?"
                params.append(f"%{str(nome_pagador).strip().upper()}%")

            query += " ORDER BY id DESC LIMIT 1"
            cur.execute(query, tuple(params))
            r = cur.fetchone()
            if r:
                os_encontrada = str(r[0])
                cliente_encontrado = str(r[1])

    if os_encontrada:
        ok, msg = liquidar_pagamento_pix(db_name, os_encontrada, txid=txid_limpo, metodo="WEBHOOK_AUTOMATICO_BANCO")
        return {
            "ok": True,
            "conciliado": True,
            "os_id": os_encontrada,
            "cliente": cliente_encontrado,
            "valor": val_float,
            "e2e_id": e2e,
            "metodo_identificacao": "TXID_BACEN" if txid_limpo and os_encontrada in txid_limpo else "CRUZAMENTO_CNPJ_VALOR",
            "msg": f"✅ Baixa bancária automática confirmada! OS #{os_encontrada} ({cliente_encontrado}) liquidada via Pix/Banco."
        }
    else:
        # Registra como crédito recebido a conciliar para o financeiro
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO pagamentos_pix (os_id, cliente, cnpj, valor, chave_pix, status_pagamento, txid, e2e_id, data_geracao, data_pagamento, metodo)
                VALUES ('PENDENTE', ?, ?, ?, 'financeiro@emed.med.br', 'A_CONCILIAR', ?, ?, ?, ?, 'PIX_AVULSO_SEM_OS')
            """, (str(nome_pagador or 'CLIENTE DESCONHECIDO'), str(cnpj or ''), val_float, txid_limpo, e2e, agora, agora))
            conn.commit()

        return {
            "ok": True,
            "conciliado": False,
            "valor": val_float,
            "e2e_id": e2e,
            "msg": f"⚠️ Recebimento de R$ {val_float:,.2f} registrado. Nenhuma OS em aberto com valor/CNPJ correspondente exato. Registro salvo em 'A Conciliar'."
        }
