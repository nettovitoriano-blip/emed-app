import os
import math
import json
import hashlib
import sqlite3
import datetime
from contextlib import contextmanager
import pandas as pd

SCHEMA_COLUNAS_OS = [
    ("cliente", "TEXT DEFAULT ''"),
    ("cidade", "TEXT DEFAULT ''"),
    ("estado", "TEXT DEFAULT ''"),
    ("equipamento", "TEXT DEFAULT ''"),
    ("tipo_servico", "TEXT DEFAULT ''"),
    ("tecnico_responsavel", "TEXT DEFAULT ''"),
    ("telefone_tecnico", "TEXT DEFAULT ''"),
    ("confirmado", "TEXT DEFAULT 'NÃO'"),
    ("data_agendamento", "TEXT DEFAULT ''"),
    ("endereco", "TEXT DEFAULT ''"),
    ("responsavel_hospital", "TEXT DEFAULT ''"),
    ("contato_responsavel", "TEXT DEFAULT ''"),
    ("pendencias", "TEXT DEFAULT ''"),
    ("status", "TEXT DEFAULT 'ATIVO'"),
    ("checkin_hora", "TEXT DEFAULT ''"),
    ("checkout_hora", "TEXT DEFAULT ''"),
    ("tempo_atendimento", "TEXT DEFAULT ''"),
    ("checklist_pop", "TEXT DEFAULT ''"),
    ("assinatura_cliente", "TEXT DEFAULT ''"),
    ("assinatura_tecnico", "TEXT DEFAULT ''"),
    ("pre_atendimento", "TEXT DEFAULT ''"),
    ("foto_evidencia", "TEXT DEFAULT ''"),
    ("cnpj", "TEXT DEFAULT ''"),
    ("cep", "TEXT DEFAULT ''"),
    ("email", "TEXT DEFAULT ''"),
    ("whatsapp", "TEXT DEFAULT ''"),
    ("endereco_fiscal", "TEXT DEFAULT ''"),
    ("tipo_contrato", "TEXT DEFAULT 'CONTRATO'"),
    ("instrumento_necessario", "TEXT DEFAULT ''"),
    ("etapa_preventiva", "TEXT DEFAULT ''"),
    ("orcamento_anexo", "TEXT DEFAULT ''"),
    ("condicao_pagamento", "TEXT DEFAULT ''"),
    ("valor_os", "REAL DEFAULT 0.0"),
    ("defeito_relatado", "TEXT DEFAULT ''"),
    ("condicao_inicial", "TEXT DEFAULT 'OPERACIONAL'"),
    ("problemas_encontrados", "TEXT DEFAULT ''"),
    ("causa_raiz", "TEXT DEFAULT ''"),
    ("servico_executado", "TEXT DEFAULT ''"),
    ("parametros_medidos", "TEXT DEFAULT ''"),
    ("observacoes_gerais", "TEXT DEFAULT ''"),
    ("condicao_final", "TEXT DEFAULT 'LIBERADO PARA USO NORMAL'"),
    ("foto_depois", "TEXT DEFAULT ''"),
    ("assinatura_cliente_img", "TEXT DEFAULT ''"),
    ("sync_hash", "TEXT DEFAULT ''"),
    ("peca_baixada_ref", "TEXT DEFAULT ''"),
    ("tecnico_auxiliar", "TEXT DEFAULT ''"),
    ("video_evidencia", "TEXT DEFAULT ''"),
    ("formulario_anexo", "TEXT DEFAULT ''"),
    ("data_ultima_calibracao", "TEXT DEFAULT ''"),
    ("data_validade_calibracao", "TEXT DEFAULT ''"),
    ("certificado_calibracao", "TEXT DEFAULT ''"),
    ("requer_calibracao_anual", "TEXT DEFAULT 'SIM'"),
]

NOMES_COLUNAS_OS = [c[0] for c in SCHEMA_COLUNAS_OS]

CICLO_ETAPAS_PREVENTIVA = [
    "ETAPA 1: MESA DE EXAMES, COMANDOS E CONSOLE",
    "ETAPA 2: GANTRY, PDU, QUADRO ELÉTRICO E CABEAMENTO",
    "ETAPA 3: TUBO, GERADOR DE ALTA TENSÃO E COLIMAÇÃO",
    "PREVENTIVA COMPLETA (CHECKLIST INTEGRAL POP/IT)"
]

SUGESTOES_SEPARACAO_POR_ATIVIDADE = {
    "AFERIÇÃO RADIOMÉTRICA & FOTOCÉLULA (AEC)": {
        "nome": "SUGESTÃO: AFERIÇÃO RADIOMÉTRICA & FOTOCÉLULA / AEC (MULTÍMETRO 1000V)",
        "itens": [
            "FER-001: Multímetro Especial até 1000V (Aferição Fotocélula / AEC & Mamógrafo)",
            "FER-004: Medidor Radiométrico Multi-Parâmetro (kVp, Dose, Tempo, CSR)",
            "FER-005: Kit de Mamografia (Phantom, Acrílicos, Balança e Cassete)",
            "FER-017: Kit de Alinhamento de Colimador (Beam Alignment Tools & Campo Luminoso)",
            "FER-009: Trena Laser Métrica Digital",
        ],
    },
    "MANUTENÇÃO DE ELETROFREIOS & MECÂNICA": {
        "nome": "SUGESTÃO: MANUTENÇÃO DE ELETROFREIOS & MECÂNICA (ESTATIVA / MESA)",
        "itens": [
            "PEC-005: Bobina Solenoide / Eletrofreio (Universal 12V / 24V / 100V)",
            "PEC-006: Botão de Acionamento / Microswitch de Freio",
            "PEC-007: Fonte de Alimentação Chaveada Industrial",
            "PEC-008: Cabo de Alimentação / Chicote Flexível de Freio",
            "CON-003: Kit Limpeza Padrão (Limpa-Contatos Elétricos, Desengripante, Veja, Panos e Aspirador)",
        ],
    },
    "CALIBRAÇÃO DE DENSITOMETRIA": {
        "nome": "SUGESTÃO: CALIBRAÇÃO & MANUTENÇÃO EM DENSITOMETRIA ÓSSEA",
        "itens": [
            "FER-006: Phantom Oficial de Calibração de Densidade Óssea",
            "PEC-003: Cabos de Alta Tensão (HV) Sobressalentes",
            "CON-003: Kit Limpeza Padrão (Limpa-Contatos Elétricos, Desengripante, Veja, Panos e Aspirador)",
        ],
    },
    "SISTEMAS DIGITAIS (DR / CR)": {
        "nome": "SUGESTÃO: SISTEMAS DIGITAIS (DR / CR & WORKSTATION)",
        "itens": [
            "PEC-010: Interface Box / Fonte de Alimentação do Detector DR",
            "PEC-009: Baterias Sobressalentes e Carregador para Flat Panel Wi-Fi",
            "PEC-011: Cabos de Comunicação Tether Cable e Rede Cat6 Blindados",
            "FER-017: Kit de Alinhamento de Colimador (Beam Alignment Tools & Campo Luminoso)",
            "CON-004: Álcool Isopropílico 99% ESD e Panos de Microfibra",
        ],
    },
    "INSTALAÇÃO PESADA": {
        "nome": "SUGESTÃO: INSTALAÇÃO & MONTAGEM MECÂNICA PESADA",
        "itens": [
            "FER-008: Nível a Laser Autonivelante com Tripé",
            "FER-016: Kit Furadeira de Impacto com Brocas (5, 8, 10 e 12mm)",
            "FER-009: Trena Laser Métrica Digital",
            "FER-010: Torquímetro Calibrado com Jogo de Soquetes",
            "FER-003: Osciloscópio Digital Portátil com Pontas HV",
            "FER-002: Multímetro Digital True RMS Calibrado",
        ],
    },
    "TROCA DE TUBO & VÁCUO": {
        "nome": "SUGESTÃO: TROCA DE TUBO DE RAIOS-X / TC & ALTA TENSÃO",
        "itens": [
            "FER-015: Giga de Comunicação JEDI & Cabos de Serviço (Tomografia)",
            "FER-010: Torquímetro Calibrado para Anel de Fixação",
            "FER-012: Talha de Içamento Mecânica / Macaco Hidráulico de Gantry",
            "CON-005: Graxa Especial de Alta Rotação SlipRing",
            "PEC-003: Cabos de Alta Tensão (HV)",
            "CON-003: Kit Limpeza Padrão (Limpa-Contatos, Desengripante, Panos)",
        ],
    },
    "PREVENTIVA PADRÃO": {
        "nome": "SUGESTÃO: MANUTENÇÃO PREVENTIVA PADRÃO & POP",
        "itens": [
            "FER-005: Phantoms de Calibração Padrão (Cabeça / Corpo / QA)",
            "FER-002: Multímetro Digital Calibrado True RMS",
            "FER-011: Alicate Amperímetro DC/AC True RMS",
            "CON-005: Graxa Especial para Rolamentos e SlipRing",
            "CON-004: Álcool Isopropílico 99% e Panos de Microfibra ESD",
            "CON-003: Kit Limpeza Padrão (Limpa-Contatos, Desengripante, Veja, Panos e Aspirador)",
        ],
    },
    "DIAGNÓSTICO & BANCADA DE LABORATÓRIO": {
        "nome": "SUGESTÃO: DIAGNÓSTICO & BANCADA DE LABORATÓRIO INTERNO EMED",
        "itens": [
            "FER-001: Multímetro Especial até 1000V (Aferição Fotocélula / AEC & Mamógrafo)",
            "FER-003: Osciloscópio Digital Portátil com Pontas HV / Atenuadas",
            "FER-013: Estação de Solda Portátil ESD com Controle Térmico",
            "FER-011: Alicate Amperímetro DC/AC True RMS",
            "FER-014: Soprador / Aspirador Antiestático ESD",
            "PEC-012: Kit Sortido de Fusíveis de Ação Rápida e Retardada",
        ],
    },
}

# Alias de compatibilidade retroativa
KITS_INSTRUMENTOS_POR_SITUACAO = SUGESTOES_SEPARACAO_POR_ATIVIDADE


def obter_kit_por_servico(tipo_servico: str, defeito: str = "") -> dict:
    """Retorna a sugestão de separação de ferramentas e materiais mais indicada com base no tipo de serviço e no relato técnico."""
    texto_busca = ((tipo_servico or "") + " " + (defeito or "")).upper()
    if any(k in texto_busca for k in ["FOTOCEL", "FOTO-CEL", "AEC", "1000V", "MAMOGR", "MAMO"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["AFERIÇÃO RADIOMÉTRICA & FOTOCÉLULA (AEC)"]
    if any(k in texto_busca for k in ["FREIO", "ESTATIVA", "PORTA TUBO", "PORTA-TUBO", "TRILHO", "MECANIC"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["MANUTENÇÃO DE ELETROFREIOS & MECÂNICA"]
    if any(k in texto_busca for k in ["DENSITO", "LUNAR", "PRODIGY", "SHUTTER"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["CALIBRAÇÃO DE DENSITOMETRIA"]
    if any(k in texto_busca for k in ["DR", "CR", "FLAT PANEL", "DETECTOR", "DIGITALIZADOR", "CHASSI", "CASSETE", "WORKSTATION", "DICOM"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["SISTEMAS DIGITAIS (DR / CR)"]
    if any(k in texto_busca for k in ["INSTALA", "MONTAG"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["INSTALAÇÃO PESADA"]
    if any(k in texto_busca for k in ["TUBO", "GANTRY", "JEDI"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["TROCA DE TUBO & VÁCUO"]
    if any(k in texto_busca for k in ["LABORAT", "BANCADA", "PLACA"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["DIAGNÓSTICO & BANCADA DE LABORATÓRIO"]
    if any(k in texto_busca for k in ["PREVENT"]):
        return SUGESTOES_SEPARACAO_POR_ATIVIDADE["PREVENTIVA PADRÃO"]
    for chave, dados in SUGESTOES_SEPARACAO_POR_ATIVIDADE.items():
        if chave in texto_busca:
            return dados
    return {
        "nome": "SUGESTÃO GERAL DE ATENDIMENTO",
        "itens": [
            "FER-002: Multímetro Digital True RMS Calibrado",
            "CON-003: Kit Limpeza Padrão (Limpa-Contatos, Desengripante, Veja, Panos e Aspirador)",
        ]
    }



def limpar_texto(valor, padrao=""):
    if valor is None or pd.isna(valor):
        return padrao
    txt = str(valor).strip()
    if txt.lower() in ["none", "nan", "nat", "null", ""]:
        return padrao
    return txt


def limpar_float(valor, padrao=0.0):
    if valor is None or pd.isna(valor):
        return float(padrao)
    txt = str(valor).strip().replace(",", ".")
    if txt.lower() in ["none", "nan", "nat", "null", ""]:
        return float(padrao)
    try:
        return float(txt)
    except Exception:
        return float(padrao)


def limpar_int(valor, padrao=0):
    return int(round(limpar_float(valor, padrao)))


@contextmanager
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def garantir_pk_tabela_os(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(clientes_equipamentos)")
    info_cols = cur.fetchall()
    if not info_cols:
        defs_sql = ", ".join([f"{col} {tipo}" for col, tipo in SCHEMA_COLUNAS_OS])
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS clientes_equipamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {defs_sql}
            )
        """)
        return

    tem_pk_id = any(c[1] == "id" and c[5] == 1 for c in info_cols)
    colunas_atuais = [c[1] for c in info_cols]

    if not tem_pk_id:
        defs_sql = ", ".join([f"{col} {tipo}" for col, tipo in SCHEMA_COLUNAS_OS])
        cur.execute(f"""
            CREATE TABLE clientes_equipamentos_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {defs_sql}
            )
        """)
        cols_comuns = [c for c in NOMES_COLUNAS_OS if c in colunas_atuais]
        if cols_comuns:
            lista_c = ", ".join(cols_comuns)
            cur.execute(f"""
                INSERT INTO clientes_equipamentos_new ({lista_c})
                SELECT {lista_c} FROM clientes_equipamentos
            """)
        cur.execute("DROP TABLE clientes_equipamentos")
        cur.execute("ALTER TABLE clientes_equipamentos_new RENAME TO clientes_equipamentos")
    else:
        for col_n, col_t in SCHEMA_COLUNAS_OS:
            if col_n not in colunas_atuais:
                try:
                    cur.execute(f"ALTER TABLE clientes_equipamentos ADD COLUMN {col_n} {col_t}")
                except Exception:
                    pass


def normalizar_dataframe_os(df):
    df_norm = df.copy()
    for col, _ in SCHEMA_COLUNAS_OS:
        if col not in df_norm.columns:
            if col == "tipo_contrato":
                df_norm[col] = "CONTRATO"
            elif col == "valor_os":
                df_norm[col] = 0.0
            elif col == "condicao_inicial":
                df_norm[col] = "OPERACIONAL"
            elif col == "condicao_final":
                df_norm[col] = "LIBERADO PARA USO NORMAL"
            elif col == "status":
                df_norm[col] = "ATIVO"
            elif col == "confirmado":
                df_norm[col] = "NÃO"
            else:
                df_norm[col] = ""
    df_norm["cliente"] = df_norm["cliente"].fillna("").astype(str).str.upper()
    return df_norm


def salvar_dataframe_transacional(dataframe, db_path, excel_path=None, backup_path=None):
    df_save = normalizar_dataframe_os(dataframe)
    with get_db_connection(db_path) as conn:
        garantir_pk_tabela_os(conn)
        cur = conn.cursor()

        ids_presentes = []
        if "id" in df_save.columns:
            for val_id in df_save["id"].dropna():
                id_int = limpar_int(val_id, 0)
                if id_int > 0:
                    ids_presentes.append(id_int)

        if ids_presentes:
            placeholders = ",".join(["?"] * len(ids_presentes))
            cur.execute(f"DELETE FROM clientes_equipamentos WHERE id NOT IN ({placeholders})", ids_presentes)
        else:
            cur.execute("DELETE FROM clientes_equipamentos")

        cols_insert = NOMES_COLUNAS_OS
        placeholders_cols = ",".join(["?"] * len(cols_insert))
        col_names_sql = ",".join(cols_insert)

        for _, row in df_save.iterrows():
            valores = []
            for c in cols_insert:
                if c == "valor_os":
                    valores.append(limpar_float(row.get(c), 0.0))
                else:
                    valores.append(limpar_texto(row.get(c), ""))

            row_id = limpar_int(row.get("id"), 0) if "id" in df_save.columns else 0
            if row_id > 0:
                cur.execute(
                    f"INSERT OR REPLACE INTO clientes_equipamentos (id, {col_names_sql}) VALUES (?, {placeholders_cols})",
                    [row_id] + valores
                )
            else:
                cur.execute(
                    f"INSERT INTO clientes_equipamentos ({col_names_sql}) VALUES ({placeholders_cols})",
                    valores
                )

        df_export = pd.read_sql_query("SELECT * FROM clientes_equipamentos", conn)

    if excel_path:
        try:
            df_export.to_excel(excel_path, index=False, engine="openpyxl")
            if backup_path:
                df_export.to_excel(backup_path, index=False, engine="openpyxl")
        except Exception:
            pass
    return True


def obter_url_base_sistema(fallback_url: str = None) -> str:
    """Retorna a URL base pública acessível do sistema para geração de links e QR Codes utilizáveis no celular.
    
    Ordem de prioridade:
    1. URL personalizada definida na sessão (ex: domínio próprio)
    2. Header da requisição web atual (se acessado via Cloudflare / proxy reverso)
    3. URL pública do túnel Cloudflare ativo em execução na máquina
    4. IP da rede local (ex: http://192.168.X.X:8501) para uso no mesmo Wi-Fi
    5. Fallback informado ou localhost
    """
    try:
        import streamlit as st
        # 1. Customização manual na sessão
        if "url_base_publica_custom" in st.session_state and st.session_state.url_base_publica_custom:
            return str(st.session_state.url_base_publica_custom).strip().rstrip("/")

        # 2. Captura automática via headers do Streamlit
        headers = getattr(st.context, "headers", {})
        host = headers.get("x-forwarded-host") or headers.get("host")
        proto = headers.get("x-forwarded-proto", "https" if host and ("trycloudflare.com" in host or "https" in str(host)) else "http")
        if host and "localhost" not in host and "127.0.0.1" not in host:
            return f"{proto}://{host}"
    except Exception:
        pass

    # 3. Fallback explícito passado
    if fallback_url and "localhost" not in fallback_url and "127.0.0.1" not in fallback_url:
        return fallback_url.rstrip("/")

    # 4. Procura túnel Cloudflare ativo nos logs
    try:
        import glob
        import re
        task_logs = glob.glob(r"C:\Users\vitor\.gemini\antigravity\brain\*\.system_generated\tasks\task-*.log")
        for log_f in sorted(task_logs, key=os.path.getmtime, reverse=True):
            try:
                with open(log_f, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "trycloudflare.com" in content:
                        m = re.search(r"https://[a-zA-Z0-9\-\.]+\.trycloudflare\.com", content)
                        if m:
                            return m.group(0).rstrip("/")
            except Exception:
                pass
    except Exception:
        pass

    # 5. IP da rede local (Wi-Fi do hospital/empresa)
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return f"http://{local_ip}:8501"
    except Exception:
        pass

    return fallback_url.rstrip("/") if fallback_url else "http://localhost:8501"


def obter_id_os(idx, row):
    val_id = limpar_int(row.get("id"), 0)
    return val_id if val_id > 0 else int(idx)


def localizar_indice_por_os_id(df, os_id_str):
    if not str(os_id_str).strip().isdigit():
        return None
    alvo = int(str(os_id_str).strip())
    if "id" in df.columns:
        match = df[df["id"].apply(lambda x: limpar_int(x, -1)) == alvo]
        if not match.empty:
            return match.index[0]
    if alvo in df.index:
        return alvo
    return None


def gerar_hash_os_offline(dados_json):
    chave = "|".join([
        str(dados_json.get("os_id", "")).strip(),
        str(dados_json.get("cliente", "")).strip().upper(),
        str(dados_json.get("equipamento", "")).strip().upper(),
        str(dados_json.get("tecnico", "")).strip().upper(),
        str(dados_json.get("checkin_hora", "")).strip(),
        str(dados_json.get("relatorio", "")).strip().upper()
    ])
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:24]


def sincronizar_os_offline_idempotente(df, dados_json, equipa_tecnica, utilizador_padrao):
    sync_hash = gerar_hash_os_offline(dados_json)
    os_id_ref = str(dados_json.get("os_id", "")).strip()
    status_final = str(dados_json.get("status", "CONCLUÍDO")).upper()
    prefixo_status = "[CONCLUÍDO OFFLINE]" if status_final == "CONCLUÍDO" else "[PENDÊNCIA OFFLINE]"
    relatorio_final = f"{prefixo_status} {str(dados_json.get('relatorio', '')).upper()}"
    tec_off = str(dados_json.get("tecnico", utilizador_padrao)).upper()
    ass_tec_off = equipa_tecnica.get(tec_off, {}).get("assinatura", f"{tec_off} - CFT")

    idx_alvo = localizar_indice_por_os_id(df, os_id_ref)
    if idx_alvo is None and "sync_hash" in df.columns:
        match_hash = df[df["sync_hash"].astype(str) == sync_hash]
        if not match_hash.empty:
            idx_alvo = match_hash.index[0]

    campos_sync = {
        "checkin_hora": limpar_texto(dados_json.get("checkin_hora", "")),
        "checkout_hora": limpar_texto(dados_json.get("checkout_hora", "")),
        "condicao_inicial": limpar_texto(dados_json.get("condicao_inicial", "OPERACIONAL"), "OPERACIONAL"),
        "defeito_relatado": limpar_texto(dados_json.get("defeito_relatado", "")),
        "problemas_encontrados": limpar_texto(dados_json.get("problemas_encontrados", "")),
        "parametros_medidos": limpar_texto(dados_json.get("parametros_medidos", "")),
        "servico_executado": limpar_texto(dados_json.get("servico_executado", relatorio_final), relatorio_final),
        "observacoes_gerais": limpar_texto(dados_json.get("observacoes_gerais", "")),
        "pendencias": relatorio_final,
        "status": status_final,
        "instrumento_necessario": limpar_texto(dados_json.get("instrumento_necessario", "")),
        "assinatura_cliente": limpar_texto(dados_json.get("assinatura_cliente", "")),
        "assinatura_cliente_img": limpar_texto(dados_json.get("assinatura_cliente_img", "")),
        "assinatura_tecnico": ass_tec_off,
        "sync_hash": sync_hash
    }

    if idx_alvo is not None:
        for k, v in campos_sync.items():
            df.at[idx_alvo, k] = v
        return df, "ATUALIZADA"

    nova_off = {
        "cliente": limpar_texto(dados_json.get("cliente", "OFFLINE"), "OFFLINE").upper(),
        "equipamento": limpar_texto(dados_json.get("equipamento", "")).upper(),
        "tecnico_responsavel": tec_off,
        "tipo_servico": "CORRETIVA / CAMPO OFFLINE",
        "confirmado": "SIM",
        "data_agendamento": datetime.date.today().strftime("%Y-%m-%d"),
        **campos_sync
    }
    df_out = pd.concat([df, pd.DataFrame([nova_off])], ignore_index=True)
    return df_out, "CRIADA"


def aplicar_peca_os_idempotente(db_path, nome_peca, qtd_aplicada, ref_anterior=""):
    if not nome_peca or nome_peca == "NENHUMA PEÇA":
        return True, "", ""

    nova_ref = f"{int(qtd_aplicada)}x {nome_peca.strip().upper()}"
    if limpar_texto(ref_anterior).upper() == nova_ref.upper():
        return True, f"[PEÇA JÁ CONTABILIZADA: {nova_ref}]", nova_ref

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantidade FROM estoque_pecas WHERE UPPER(nome_peca) = ?", (nome_peca.strip().upper(),))
        row = cur.fetchone()
        if not row:
            # Peça aplicada via preenchimento manual (avulsa / fora do estoque formal)
            # Permite o registro completo na OS e segue o fluxo sem travar o fechamento
            return True, f"[PEÇA MANUAL: {nova_ref}]", nova_ref
        # Blindagem Atômica contra Race Condition: UPDATE condicional com trava de saldo
        cur.execute(
            "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE UPPER(nome_peca) = ? AND quantidade >= ?",
            (int(qtd_aplicada), nome_peca.strip().upper(), int(qtd_aplicada))
        )
        if cur.rowcount == 0:
            cur.execute("SELECT quantidade FROM estoque_pecas WHERE UPPER(nome_peca) = ?", (nome_peca.strip().upper(),))
            r_recheck = cur.fetchone()
            saldo_recheck = int(r_recheck[0]) if r_recheck else 0
            return (
                False,
                f"⚠️ Saldo insuficiente para '{nome_peca}' no estoque! Disponível: {saldo_recheck} un.",
                ref_anterior
            )
    return True, f"[PEÇA APLICADA: {nova_ref}]", nova_ref


def registrar_aplicacao_definitiva_e_fluxo_cobranca(
    db_path,
    os_id,
    cliente,
    equipamento,
    tecnico,
    nome_peca,
    qtd_aplicada,
    valor_total_os,
    condicao_pagamento="FATURAMENTO BOLETO BANCÁRIO",
    tipo_contrato="CONTRATO"
):
    """
    Ao finalizar a OS com peça definitiva:
    1. Atualiza o status da peça em solicitacoes_pecas para 'APLICADO EM DEFINITIVO NO CLIENTE / BAIXADO'
    2. Garante a baixa permanente no estoque_pecas
    3. Dá sequência automática ao fluxo de cobrança e faturamento (inserindo/atualizando em notas_fiscais)
    """
    if not nome_peca or nome_peca == "NENHUMA PEÇA":
        # Mesmo sem peça, se houver valor faturável na OS, registra no fluxo de cobrança
        if float(valor_total_os or 0) > 0:
            with get_db_connection(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT cnpj FROM clientes_equipamentos WHERE id = ?", (int(os_id),))
                r_cnpj = cur.fetchone()
                cnpj_val = r_cnpj[0] if r_cnpj and r_cnpj[0] else ""

                cur.execute("SELECT id FROM notas_fiscais WHERE os_id = ?", (int(os_id),))
                ja_nf = cur.fetchone()
                agora_iso = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if not ja_nf:
                    cur.execute("""
                        INSERT INTO notas_fiscais (
                            os_id, cliente, cnpj_tomador, tipo_nota, valor_servicos, valor_pecas,
                            valor_liquido, status_fiscal, natureza_operacao, data_emissao, criado_em, atualizado_em
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(os_id), cliente, cnpj_val, "NFSE", float(valor_total_os), 0.0,
                        float(valor_total_os), "AGUARDANDO FATURAMENTO / COBRANÇA",
                        f"SERVIÇO TÉCNICO [{condicao_pagamento}]", agora_iso, agora_iso, agora_iso
                    ))
            return True, "✅ Serviço concluído e encaminhado para o fluxo de cobrança!"
        return True, ""

    qtd = int(qtd_aplicada) if qtd_aplicada else 1
    nome_peca_limpo = str(nome_peca).strip().upper()
    ref_peca = f"{qtd}x {nome_peca_limpo}"

    import re
    match_cod = re.search(r"(PEC-\d+|FER-\d+|CON-\d+)", nome_peca_limpo)
    cod_encontrado = match_cod.group(1) if match_cod else None

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Obter dados de preço da peça em estoque_pecas
        if cod_encontrado:
            cur.execute("""
                SELECT codigo, preco_custo, margem_contrato, margem_avulso, quantidade 
                FROM estoque_pecas 
                WHERE codigo = ?
            """, (cod_encontrado,))
            row_peca = cur.fetchone()
        else:
            cur.execute("""
                SELECT codigo, preco_custo, margem_contrato, margem_avulso, quantidade 
                FROM estoque_pecas 
                WHERE UPPER(nome_peca) = ? OR UPPER(codigo) = ?
            """, (nome_peca_limpo, nome_peca_limpo))
            row_peca = cur.fetchone()

        cod_peca = row_peca[0] if row_peca else (cod_encontrado or "PEC-000")
        preco_custo = float(row_peca[1]) if row_peca and row_peca[1] is not None else 0.0
        m_contrato = float(row_peca[2]) if row_peca and row_peca[2] is not None else 25.0
        m_avulso = float(row_peca[3]) if row_peca and row_peca[3] is not None else 50.0

        # Baixa física definitiva no estoque_pecas
        if row_peca and cod_peca != "PEC-000":
            cur.execute("""
                UPDATE estoque_pecas 
                SET quantidade = MAX(0, quantidade - ?) 
                WHERE codigo = ?
            """, (qtd, cod_peca))

        margem_aplicada = m_contrato if "CONTRATO" in str(tipo_contrato).upper() else m_avulso
        valor_un_venda = round(preco_custo * (1 + margem_aplicada / 100.0), 2)
        if valor_un_venda == 0 and float(valor_total_os or 0) > 0:
            valor_total_pecas = round(float(valor_total_os) * 0.7, 2)
        else:
            valor_total_pecas = round(valor_un_venda * qtd, 2)

        v_total_os = float(valor_total_os or 0)
        if v_total_os >= valor_total_pecas:
            valor_servicos = round(v_total_os - valor_total_pecas, 2)
            valor_liquido = v_total_os
        else:
            valor_servicos = 0.0
            valor_liquido = valor_total_pecas

        # 2. Atualizar status na tabela solicitacoes_pecas para 'APLICADO EM DEFINITIVO NO CLIENTE / BAIXADO'
        cur.execute("""
            SELECT id FROM solicitacoes_pecas
            WHERE (UPPER(destino_cliente) LIKE ? OR UPPER(destino_cliente) LIKE ?)
            AND UPPER(status_pedido) NOT LIKE '%APLICADO%'
            ORDER BY id DESC LIMIT 1
        """, (f"%OS #{os_id}%", f"%{str(cliente).strip().upper()}%"))
        
        row_sol = cur.fetchone()
        agora_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        if row_sol:
            id_sol = row_sol[0]
            cur.execute("""
                UPDATE solicitacoes_pecas 
                SET status_pedido = 'APLICADO EM DEFINITIVO NO CLIENTE / BAIXADO',
                    itens_solicitados = ?
                WHERE id = ?
            """, (f"{ref_peca} ({cod_peca})", id_sol))
        else:
            cur.execute("""
                INSERT INTO solicitacoes_pecas 
                (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(tecnico).upper(),
                f"{cliente} ({equipamento}) [OS #{os_id}]".upper(),
                f"{ref_peca} ({cod_peca})",
                "BAIXA DEFINITIVA AO FINALIZAR OS",
                "APLICADO EM DEFINITIVO NO CLIENTE / BAIXADO",
                agora_str
            ))

        # 3. Encaminhamento para o Fluxo de Cobrança / Faturamento (tabela notas_fiscais)
        cur.execute("SELECT cnpj FROM clientes_equipamentos WHERE id = ?", (int(os_id),))
        r_cnpj = cur.fetchone()
        cnpj_val = r_cnpj[0] if r_cnpj and r_cnpj[0] else ""

        cur.execute("SELECT id FROM notas_fiscais WHERE os_id = ?", (int(os_id),))
        ja_nf = cur.fetchone()
        agora_iso = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        tipo_nota_final = "NF-e (PRODUTO/PEÇA) + NFS-e (SERVIÇO)" if valor_servicos > 0 else "NF-e (PEÇA DE REPOSIÇÃO)"
        natureza_op = f"VENDA/APLICAÇÃO DE {cod_peca} + MÃO DE OBRA [{condicao_pagamento}]"

        if ja_nf:
            cur.execute("""
                UPDATE notas_fiscais SET
                    valor_servicos = ?,
                    valor_pecas = ?,
                    valor_liquido = ?,
                    status_fiscal = 'AGUARDANDO FATURAMENTO / COBRANÇA',
                    tipo_nota = ?,
                    natureza_operacao = ?,
                    atualizado_em = ?
                WHERE os_id = ?
            """, (valor_servicos, valor_total_pecas, valor_liquido, tipo_nota_final, natureza_op, agora_iso, int(os_id)))
        else:
            cur.execute("""
                INSERT INTO notas_fiscais (
                    os_id, cliente, cnpj_tomador, tipo_nota, valor_servicos, valor_pecas,
                    valor_liquido, status_fiscal, natureza_operacao, data_emissao, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(os_id), cliente, cnpj_val, tipo_nota_final,
                valor_servicos, valor_total_pecas, valor_liquido,
                "AGUARDANDO FATURAMENTO / COBRANÇA", natureza_op,
                agora_iso, agora_iso, agora_iso
            ))

    resumo_cobranca = (
        f"✅ Peça '{ref_peca}' baixada em definitivo no Almoxarifado! "
        f"Encaminhada para o Fluxo de Cobrança: R$ {valor_liquido:,.2f} "
        f"(Peças: R$ {valor_total_pecas:,.2f} | Serviços: R$ {valor_servicos:,.2f})."
    )
    return True, resumo_cobranca


def registrar_peca_em_teste_observacao(
    db_path,
    os_id,
    cliente,
    equipamento,
    tecnico,
    nome_peca,
    qtd_aplicada,
    dias_observacao=3,
    criterio_teste=""
):
    """
    Registra a instalação de uma peça em caráter de teste para finalização de diagnóstico,
    colocando o equipamento em observação SEM cobrança imediata ao cliente.
    """
    if not nome_peca or nome_peca == "NENHUMA PEÇA":
        return False, "Nenhuma peça indicada para teste."

    qtd = int(qtd_aplicada) if qtd_aplicada else 1
    nome_peca_limpo = str(nome_peca).strip().upper()
    ref_teste = f"{qtd}x {nome_peca_limpo} [EM TESTE DE DIAGNÓSTICO]"
    dias_n = int(dias_observacao or 3)
    criterio_txt = str(criterio_teste).strip().upper() if criterio_teste else "FINALIZAR DIAGNÓSTICO EM OBSERVAÇÃO"

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Garante que a peça é reservada no estoque físico para não ser entregue a outro técnico
        import re
        match_cod = re.search(r"(PEC-\d+|FER-\d+|CON-\d+)", nome_peca_limpo)
        cod_encontrado = match_cod.group(1) if match_cod else None

        if cod_encontrado:
            cur.execute("SELECT codigo, quantidade FROM estoque_pecas WHERE codigo = ?", (cod_encontrado,))
            r_pec = cur.fetchone()
        else:
            cur.execute("SELECT codigo, quantidade FROM estoque_pecas WHERE UPPER(nome_peca) = ? OR UPPER(codigo) = ?", (nome_peca_limpo, nome_peca_limpo))
            r_pec = cur.fetchone()

        cod_p = r_pec[0] if r_pec else (cod_encontrado or "PEC-000")
        saldo_p = int(r_pec[1]) if r_pec and r_pec[1] is not None else 0

        # Deduz saldo físico temporário (está na máquina do cliente em teste)
        if saldo_p >= qtd:
            cur.execute("UPDATE estoque_pecas SET quantidade = max(0, quantidade - ?) WHERE codigo = ?", (qtd, cod_p))

        # 2. Registra na tabela solicitacoes_pecas como em observação/teste
        agora_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        cur.execute("""
            SELECT id FROM solicitacoes_pecas
            WHERE (UPPER(destino_cliente) LIKE ? OR UPPER(destino_cliente) LIKE ?)
            AND UPPER(status_pedido) NOT LIKE '%APLICADO%'
            ORDER BY id DESC LIMIT 1
        """, (f"%OS #{os_id}%", f"%{str(cliente).strip().upper()}%"))
        
        row_sol = cur.fetchone()
        status_obs = f"PEÇA EM TESTE NO CLIENTE ({dias_n} DIAS OBSERVAÇÃO)"
        if row_sol:
            cur.execute("""
                UPDATE solicitacoes_pecas 
                SET status_pedido = ?,
                    itens_solicitados = ?,
                    instrumentos_solicitados = ?
                WHERE id = ?
            """, (status_obs, f"{ref_teste} ({cod_p})", f"TESTE CLÍNICO: {criterio_txt}", row_sol[0]))
        else:
            cur.execute("""
                INSERT INTO solicitacoes_pecas 
                (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(tecnico).upper(),
                f"{cliente} ({equipamento}) [OS #{os_id}]".upper(),
                f"{ref_teste} ({cod_p})",
                f"TESTE CLÍNICO: {criterio_txt}",
                status_obs,
                agora_str
            ))

        # 3. Atualiza na tabela clientes_equipamentos: status = 'EM OBSERVAÇÃO'
        nova_pendencia = f"[EM TESTE: {ref_teste}] OBSERVAÇÃO POR {dias_n} DIAS. CRITÉRIO: {criterio_txt}"
        cur.execute("""
            UPDATE clientes_equipamentos SET
                status = 'EM OBSERVAÇÃO',
                peca_baixada_ref = ?,
                pendencias = ?
            WHERE id = ?
        """, (ref_teste, nova_pendencia, int(os_id)))

    msg = (
        f"🔬 Peça '{nome_peca_limpo}' instalada em caráter de teste! "
        f"Equipamento colocado em observação por {dias_n} dias. "
        f"Não foi gerada cobrança imediata ao cliente (aguardando validação do teste e proposta aprovada)."
    )
    return True, msg


def converter_teste_em_aplicacao_definitiva_e_cobranca(
    db_path,
    os_id,
    valor_total_os=None,
    condicao_pagamento="FATURAMENTO BOLETO BANCÁRIO"
):
    """
    Após o período de teste e validação da proposta com o cliente:
    Converte a peça em teste para APLICAÇÃO DEFINITIVA, conclui a OS e encaminha para cobrança/faturamento.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT cliente, equipamento, tecnico_responsavel, peca_baixada_ref, valor_os, tipo_contrato 
            FROM clientes_equipamentos WHERE id = ?
        """, (int(os_id),))
        row = cur.fetchone()
        if not row:
            return False, f"OS #{os_id} não encontrada."

        cliente, equip, tec, peca_ref, val_os_bd, tp_contrato = row
        val_final = float(valor_total_os) if valor_total_os is not None else float(val_os_bd or 0)

        # Extrai nome da peça limpo de peca_baixada_ref
        peca_pura = str(peca_ref or "").replace("[EM TESTE DE DIAGNÓSTICO]", "").replace("[EM TESTE/OBSERVAÇÃO]", "").strip()
        qtd_app = 1
        nome_peca_final = peca_pura
        if "x " in peca_pura:
            partes = peca_pura.split("x ", 1)
            try:
                qtd_app = int(partes[0].strip())
            except Exception:
                qtd_app = 1
            nome_peca_final = partes[1].strip()

        # Atualiza status da OS para CONCLUÍDO e grava o valor final aprovado
        cur.execute("""
            UPDATE clientes_equipamentos SET
                status = 'CONCLUÍDO',
                valor_os = ?,
                condicao_pagamento = ?,
                peca_baixada_ref = ?,
                pendencias = ?
            WHERE id = ?
        """, (
            float(val_final),
            str(condicao_pagamento),
            f"{qtd_app}x {nome_peca_final}",
            f"[CONCLUÍDO - PROPOSTA APROVADA] Peça {nome_peca_final} validada e aplicada em definitivo.",
            int(os_id)
        ))

    # Executa a baixa definitiva contábil e encaminhamento para faturamento
    ok_cob, msg_cob = registrar_aplicacao_definitiva_e_fluxo_cobranca(
        db_path,
        os_id,
        cliente,
        equip,
        tec,
        nome_peca_final,
        qtd_app,
        val_final,
        condicao_pagamento=condicao_pagamento,
        tipo_contrato=tp_contrato or "CONTRATO"
    )
    return True, f"🎉 Proposta aprovada! {msg_cob}"


def retirar_peca_teste_e_devolver_estoque(
    db_path,
    os_id,
    motivo="Teste não validou o defeito / Proposta não aprovada"
):
    """
    Caso o teste não solucione a falha ou o cliente não aprove o orçamento:
    O técnico retira a peça do cliente e estorna o saldo de volta ao Almoxarifado.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT cliente, equipamento, tecnico_responsavel, peca_baixada_ref 
            FROM clientes_equipamentos WHERE id = ?
        """, (int(os_id),))
        row = cur.fetchone()
        if not row:
            return False, f"OS #{os_id} não encontrada."

        cliente, equip, tec, peca_ref = row
        peca_pura = str(peca_ref or "").replace("[EM TESTE DE DIAGNÓSTICO]", "").replace("[EM TESTE/OBSERVAÇÃO]", "").strip()
        qtd_dev = 1
        nome_peca_dev = peca_pura
        if "x " in peca_pura:
            partes = peca_pura.split("x ", 1)
            try:
                qtd_dev = int(partes[0].strip())
            except Exception:
                qtd_dev = 1
            nome_peca_dev = partes[1].strip()

        # 1. Estorna a peça de volta em estoque_pecas
        cur.execute("""
            UPDATE estoque_pecas 
            SET quantidade = quantidade + ? 
            WHERE UPPER(nome_peca) = ? OR UPPER(codigo) = ?
        """, (qtd_dev, nome_peca_dev.upper(), nome_peca_dev.upper()))

        # 2. Atualiza em solicitacoes_pecas para 'DEVOLVIDO AO ESTOQUE / BAIXA DE RETORNO'
        cur.execute("""
            UPDATE solicitacoes_pecas 
            SET status_pedido = 'DEVOLVIDO AO ESTOQUE / BAIXA DE RETORNO',
                instrumentos_solicitados = ?
            WHERE (UPPER(destino_cliente) LIKE ? OR UPPER(destino_cliente) LIKE ?)
            AND UPPER(status_pedido) LIKE '%TESTE%'
        """, (f"RETIRADA DE TESTE: {motivo.upper()}", f"%OS #{os_id}%", f"%{str(cliente).strip().upper()}%"))

        # 3. Retorna a OS para ATIVO mantendo o relato da retirada
        cur.execute("""
            UPDATE clientes_equipamentos SET
                status = 'ATIVO',
                peca_baixada_ref = '',
                pendencias = ?
            WHERE id = ?
        """, (f"[PEÇA DE TESTE RETIRADA] {nome_peca_dev} devolvida ao estoque. Motivo: {motivo.upper()}", int(os_id)))

    return True, f"🔄 Peça '{nome_peca_dev}' estornada com sucesso! Saldo recomposto no Almoxarifado e OS mantida em aberto para novo direcionamento."


def atualizar_status_solicitacao_peca(db_path, id_pedido, novo_status):
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT itens_solicitados, status_pedido FROM solicitacoes_pecas WHERE id = ?",
            (int(id_pedido),)
        )
        row = cur.fetchone()
        if not row:
            return False, "Solicitação não encontrada."

        itens_str, status_atual = str(row[0]), str(row[1]).upper()
        novo_status_up = novo_status.strip().upper()

        if status_atual == novo_status_up:
            return True, f"O pedido #{id_pedido} já está com o status '{novo_status_up}'."

        # Se devolver ao estoque (cancelado/estornado ou devolvido pelo técnico)
        if ("ESTORNADO" in novo_status_up or "DEVOLVIDO" in novo_status_up) and ("ESTORNADO" not in status_atual and "DEVOLVIDO" not in status_atual):
            partes = [p.strip() for p in itens_str.split(",") if "x " in p and "(" in p]
            for p in partes:
                try:
                    qtd_str = p.split("x ")[0].strip()
                    cod_str = p.split("(")[-1].replace(")", "").strip()
                    qtd_dev = int(qtd_str)
                    cur.execute(
                        "UPDATE estoque_pecas SET quantidade = quantidade + ? WHERE codigo = ?",
                        (qtd_dev, cod_str)
                    )
                except Exception:
                    pass
        elif ("ESTORNADO" not in novo_status_up and "DEVOLVIDO" not in novo_status_up) and ("ESTORNADO" in status_atual or "DEVOLVIDO" in status_atual):
            # Se estava devolvido e voltou a ficar em posse do técnico, deduz novamente do estoque
            partes = [p.strip() for p in itens_str.split(",") if "x " in p and "(" in p]
            for p in partes:
                try:
                    qtd_str = p.split("x ")[0].strip()
                    cod_str = p.split("(")[-1].replace(")", "").strip()
                    qtd_sub = int(qtd_str)
                    cur.execute(
                        "UPDATE estoque_pecas SET quantidade = max(0, quantidade - ?) WHERE codigo = ?",
                        (qtd_sub, cod_str)
                    )
                except Exception:
                    pass

        cur.execute(
            "UPDATE solicitacoes_pecas SET status_pedido = ? WHERE id = ?",
            (novo_status_up, int(id_pedido))
        )
    return True, f"✅ Status do pedido #{id_pedido} atualizado para '{novo_status_up}'!"


def acionar_separacao_automatica_almoxarifado(
    db_path,
    tecnico,
    cliente,
    equipamento="",
    tipo_servico="",
    instrumentos_materiais="",
    pecas="",
    os_id=None
):
    """
    Aciona o almoxarifado automaticamente quando um técnico é selecionado para um serviço
    que necessite de peças ou ferramentas.
    Cria a solicitação com status 'A SEPARAR / AGUARDANDO ALMOXARIFADO' e pré-reserva os itens.
    """
    if not tecnico or str(tecnico).strip().upper() in ["A DEFINIR", "N/D", "SEM TÉCNICO", "NONE", ""]:
        return False, "Nenhum técnico atribuído ao serviço."

    tec_up = str(tecnico).strip().upper()
    cli_up = str(cliente).strip().upper()
    eq_up = str(equipamento).strip().upper()
    dest_str = f"{cli_up} — {eq_up}" if eq_up and eq_up not in cli_up else cli_up
    
    inst_str = str(instrumentos_materiais).strip().upper() if instrumentos_materiais else ""
    pecas_str = str(pecas).strip().upper() if pecas else ""

    # Se não foram explicitados instrumentos nem peças, obtém automaticamente pelo tipo de serviço e equipamento
    if not inst_str and not pecas_str:
        kit_auto = obter_kit_por_servico(tipo_servico, f"{eq_up} {tipo_servico}")
        inst_str = f"[{kit_auto['nome']}] " + ", ".join(kit_auto.get("itens", []))

    if not inst_str and not pecas_str:
        return False, "Serviço não requer ferramentas ou peças especiais."

    # Identificador de OS no texto
    ref_os_txt = f" [OS #{os_id}]" if os_id else ""
    dest_com_os = f"{dest_str}{ref_os_txt}"

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        # Verificar se já existe solicitação pendente para este técnico e destino/OS
        cur.execute("""
            SELECT id, status_pedido FROM solicitacoes_pecas 
            WHERE UPPER(tecnico) = ? AND (UPPER(destino_cliente) = ? OR UPPER(destino_cliente) LIKE ?)
            AND UPPER(status_pedido) IN ('A SEPARAR / AGUARDANDO ALMOXARIFADO', 'RESERVADO / ENVIADO AO ESTOQUE', 'ENTREGUE AO TÉCNICO / EM CAMPO')
            ORDER BY id DESC LIMIT 1
        """, (tec_up, dest_com_os.upper(), f"%{cli_up}%"))
        
        existente = cur.fetchone()
        if existente:
            return True, f"O Almoxarifado já está com o Pedido #{existente[0]} ({existente[1]}) em separação para {tec_up}."

        data_ped_agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
        resumo_pecas = pecas_str if pecas_str else "NENHUMA PEÇA EXTRA"

        # Reserva itens do estoque se houver códigos padrão PEC-xxx, FER-xxx, CON-xxx
        import re
        codigos_encontrados = re.findall(r'[A-Z]{3}-\d{3}', f"{resumo_pecas} {inst_str}")
        for cod in set(codigos_encontrados):
            cur.execute("SELECT quantidade FROM estoque_pecas WHERE codigo = ?", (cod,))
            r_stk = cur.fetchone()
            if r_stk and r_stk[0] > 0:
                cur.execute("UPDATE estoque_pecas SET quantidade = max(0, quantidade - 1) WHERE codigo = ?", (cod,))

        cur.execute("""
            INSERT INTO solicitacoes_pecas
            (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tec_up, dest_com_os, resumo_pecas, inst_str,
            "A SEPARAR / AGUARDANDO ALMOXARIFADO", data_ped_agora
        ))
        novo_id = cur.lastrowid

    msg_sucesso = (
        f"✅ Almoxarifado acionado automaticamente! Pedido #{novo_id} "
        f"gerado com status 'A SEPARAR' para o técnico {tec_up}."
    )
    return True, msg_sucesso


def sugerir_proxima_etapa_preventiva(df, cliente, equipamento):
    if df.empty or not cliente or not equipamento:
        return CICLO_ETAPAS_PREVENTIVA[0]

    hist = df[
        (df["cliente"].astype(str).str.upper() == str(cliente).strip().upper()) &
        (df["equipamento"].astype(str).str.upper() == str(equipamento).strip().upper())
    ]
    if hist.empty:
        return CICLO_ETAPAS_PREVENTIVA[0]

    for _, row in hist.iloc[::-1].iterrows():
        et = limpar_texto(row.get("etapa_preventiva"), "").upper()
        if "ETAPA 1" in et or "PARTE 1" in et:
            return CICLO_ETAPAS_PREVENTIVA[1]
        if "ETAPA 2" in et or "PARTE 2" in et:
            return CICLO_ETAPAS_PREVENTIVA[2]
        if "ETAPA 3" in et or "PARTE 3" in et:
            return CICLO_ETAPAS_PREVENTIVA[0]
    return CICLO_ETAPAS_PREVENTIVA[0]


def agendar_proxima_etapa_circular(df, row_os_atual, etapa_concluida, dias_ciclo=30):
    cli = limpar_texto(row_os_atual.get("cliente"), "").upper()
    eq = limpar_texto(row_os_atual.get("equipamento"), "").upper()
    if not cli or not eq:
        return df, None

    et_up = str(etapa_concluida).upper()
    if "PARTE 1" in et_up or "ETAPA 1" in et_up:
        prox_etapa = CICLO_ETAPAS_PREVENTIVA[1]
    elif "PARTE 2" in et_up or "ETAPA 2" in et_up:
        prox_etapa = CICLO_ETAPAS_PREVENTIVA[2]
    else:
        prox_etapa = CICLO_ETAPAS_PREVENTIVA[0]

    ja_existe = df[
        (df["cliente"].astype(str).str.upper() == cli) &
        (df["equipamento"].astype(str).str.upper() == eq) &
        (df["status"].astype(str).str.upper() == "ATIVO") &
        (df["etapa_preventiva"].astype(str).str.upper() == prox_etapa)
    ]
    if not ja_existe.empty:
        return df, prox_etapa

    prox_data = (datetime.date.today() + datetime.timedelta(days=int(dias_ciclo))).strftime("%Y-%m-%d")
    nova_os_ciclo = {
        "cliente": cli,
        "cidade": limpar_texto(row_os_atual.get("cidade"), "FORTALEZA").upper(),
        "estado": limpar_texto(row_os_atual.get("estado"), "CE").upper(),
        "equipamento": eq,
        "endereco": limpar_texto(row_os_atual.get("endereco"), "").upper(),
        "tipo_servico": "PREVENTIVA (Com Checklist POP/IT)",
        "data_agendamento": prox_data,
        "tecnico_responsavel": limpar_texto(row_os_atual.get("tecnico_responsavel"), "A DEFINIR").upper(),
        "telefone_tecnico": limpar_texto(row_os_atual.get("telefone_tecnico"), ""),
        "responsavel_hospital": limpar_texto(row_os_atual.get("responsavel_hospital"), "").upper(),
        "contato_responsavel": limpar_texto(row_os_atual.get("contato_responsavel"), ""),
        "confirmado": "NÃO",
        "pendencias": f"[CICLO PREVENTIVO AUTOMÁTICO] PROGRAMADO PARA {prox_etapa}",
        "status": "ATIVO",
        "etapa_preventiva": prox_etapa,
        "defeito_relatado": f"MANUTENÇÃO PREVENTIVA PROGRAMADA — {prox_etapa}",
        "condicao_inicial": "OPERACIONAL",
        "condicao_final": "LIBERADO PARA USO NORMAL",
        "tipo_contrato": limpar_texto(row_os_atual.get("tipo_contrato"), "CONTRATO"),
        "cnpj": limpar_texto(row_os_atual.get("cnpj"), ""),
        "cep": limpar_texto(row_os_atual.get("cep"), ""),
        "email": limpar_texto(row_os_atual.get("email"), ""),
        "whatsapp": limpar_texto(row_os_atual.get("whatsapp"), ""),
        "endereco_fiscal": limpar_texto(row_os_atual.get("endereco_fiscal"), ""),
        "valor_os": 0.0
    }
    df_out = pd.concat([df, pd.DataFrame([nova_os_ciclo])], ignore_index=True)
    return df_out, prox_etapa


def calcular_dias_aguardando_orcamento(data_str, hoje_ts=None):
    if hoje_ts is None:
        hoje_ts = pd.Timestamp.today().normalize()
    dt = pd.to_datetime(data_str, errors="coerce")
    if pd.isna(dt):
        return 0
    return max(0, int((hoje_ts - dt.normalize()).days))


def calcular_status_calibracao(data_validade_str: str) -> dict:
    """Calcula o status de conformidade anual de calibração ou renovação de créditos."""
    if not data_validade_str or not str(data_validade_str).strip():
        return {
            "status": "NÃO INFORMADO",
            "dias_restantes": 9999,
            "badge_cor": "#64748b",
            "badge_bg": "rgba(100, 116, 139, 0.15)",
            "badge_txt": "⚪ SEM DATA CADASTRADA",
            "alerta_urgente": False,
            "nivel_alerta": 0
        }

    dt_alvo = None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt_alvo = datetime.datetime.strptime(str(data_validade_str).strip(), fmt).date()
            break
        except ValueError:
            continue

    if not dt_alvo:
        return {
            "status": "INVÁLIDO",
            "dias_restantes": 9999,
            "badge_cor": "#64748b",
            "badge_bg": "rgba(100, 116, 139, 0.15)",
            "badge_txt": "⚪ DATA INVÁLIDA",
            "alerta_urgente": False,
            "nivel_alerta": 0
        }

    hoje = datetime.date.today()
    dias = (dt_alvo - hoje).days

    if dias < 0:
        return {
            "status": "VENCIDO",
            "dias_restantes": dias,
            "badge_cor": "#ef4444",
            "badge_bg": "rgba(239, 68, 68, 0.18)",
            "badge_txt": f"🔴 VENCIDO HÁ {abs(dias)} D",
            "alerta_urgente": True,
            "nivel_alerta": 3
        }
    elif dias <= 30:
        return {
            "status": "A VENCER",
            "dias_restantes": dias,
            "badge_cor": "#f59e0b",
            "badge_bg": "rgba(245, 158, 11, 0.18)",
            "badge_txt": f"🟡 VENCE EM {dias} D",
            "alerta_urgente": True,
            "nivel_alerta": 2
        }
    elif dias <= 60:
        return {
            "status": "ATENÇÃO",
            "dias_restantes": dias,
            "badge_cor": "#38bdf8",
            "badge_bg": "rgba(56, 189, 248, 0.15)",
            "badge_txt": f"🔵 VENCE EM {dias} D",
            "alerta_urgente": False,
            "nivel_alerta": 1
        }
    else:
        return {
            "status": "EM DIA",
            "dias_restantes": dias,
            "badge_cor": "#10b981",
            "badge_bg": "rgba(16, 185, 129, 0.15)",
            "badge_txt": f"🟢 EM DIA ({dias} D)",
            "alerta_urgente": False,
            "nivel_alerta": 0
        }


def obter_resumo_alarmes_calibracao(db_path: str) -> dict:
    """Retorna contagem consolidada de instrumentos e equipamentos com calibração ou créditos anuais a vencer ou vencidos."""
    resumo = {
        "instrumentos_vencidos": 0,
        "instrumentos_a_vencer": 0,
        "instrumentos_em_dia": 0,
        "equipamentos_vencidos": 0,
        "equipamentos_a_vencer": 0,
        "equipamentos_em_dia": 0,
        "total_alarmes_urgentes": 0,
        "itens_urgentes": []
    }

    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT codigo, nome_peca, data_validade_calibracao, certificado_calibracao,
                       requer_calibracao, requer_creditos, saldo_creditos
                FROM estoque_pecas
                WHERE requer_calibracao = 1 OR requer_creditos = 1
            """)
            rows_inst = cur.fetchall()
            for r in rows_inst:
                st_info = calcular_status_calibracao(r[2])
                if st_info["status"] == "VENCIDO":
                    resumo["instrumentos_vencidos"] += 1
                elif st_info["status"] == "A VENCER":
                    resumo["instrumentos_a_vencer"] += 1
                elif st_info["status"] == "EM DIA":
                    resumo["instrumentos_em_dia"] += 1

                if st_info["alerta_urgente"]:
                    resumo["total_alarmes_urgentes"] += 1
                    tipo_desc = "CRÉDITOS ANUAIS" if r[5] == 1 and r[4] == 0 else ("CALIBRAÇÃO & CRÉDITOS" if r[5] == 1 else "CALIBRAÇÃO ANUAL")
                    resumo["itens_urgentes"].append({
                        "origem": "INSTRUMENTO EMED",
                        "codigo": r[0],
                        "nome": r[1],
                        "tipo": tipo_desc,
                        "validade": r[2],
                        "status": st_info["status"],
                        "badge_txt": st_info["badge_txt"],
                        "dias": st_info["dias_restantes"]
                    })

            cur.execute("""
                SELECT cliente, equipamento, data_validade_calibracao, certificado_calibracao, cidade
                FROM clientes_equipamentos
                WHERE data_validade_calibracao IS NOT NULL AND data_validade_calibracao != ''
            """)
            rows_eq = cur.fetchall()
            for req in rows_eq:
                st_eq = calcular_status_calibracao(req[2])
                if st_eq["status"] == "VENCIDO":
                    resumo["equipamentos_vencidos"] += 1
                elif st_eq["status"] == "A VENCER":
                    resumo["equipamentos_a_vencer"] += 1
                elif st_eq["status"] == "EM DIA":
                    resumo["equipamentos_em_dia"] += 1

                if st_eq["alerta_urgente"]:
                    resumo["total_alarmes_urgentes"] += 1
                    resumo["itens_urgentes"].append({
                        "origem": "EQUIPAMENTO CLIENTE",
                        "codigo": req[0],
                        "nome": f"{req[0]} — {req[1]} ({req[4]})",
                        "tipo": "CALIBRAÇÃO / QA ANUAL (RDC 611)",
                        "validade": req[2],
                        "status": st_eq["status"],
                        "badge_txt": st_eq["badge_txt"],
                        "dias": st_eq["dias_restantes"]
                    })
    except Exception:
        pass

    return resumo


def atualizar_calibracao_instrumento(db_path: str, codigo: str, data_ultima: str, data_validade: str, certificado: str, saldo_creditos: str = "") -> tuple:
    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE estoque_pecas 
                SET data_ultima_calibracao = ?,
                    data_validade_calibracao = ?,
                    certificado_calibracao = ?,
                    saldo_creditos = ?
                WHERE codigo = ?
            """, (data_ultima.strip(), data_validade.strip(), certificado.strip().upper(), saldo_creditos.strip(), codigo.strip()))
        return True, "✅ Calibração / Créditos do instrumento atualizados com sucesso!"
    except Exception as ex:
        return False, f"Erro ao atualizar calibração: {ex}"


def atualizar_calibracao_equipamento_cliente(db_path: str, os_id: int, data_ultima: str, data_validade: str, certificado: str) -> tuple:
    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE clientes_equipamentos
                SET data_ultima_calibracao = ?,
                    data_validade_calibracao = ?,
                    certificado_calibracao = ?
                WHERE id = ?
            """, (data_ultima.strip(), data_validade.strip(), certificado.strip().upper(), int(os_id)))
        return True, "✅ Calibração do equipamento cliente atualizada com sucesso!"
    except Exception as ex:
        return False, f"Erro ao atualizar calibração do cliente: {ex}"




# =============================================================================
# MÓDULO DE RESILIÊNCIA OFFLINE, RASCUNHOS PROVISÓRIOS & SUGESTÃO INTELIGENTE IA
# =============================================================================

def inicializar_tabela_rascunhos(db_name: str):
    """Garante a existência das tabelas de rascunhos e configurações do sistema."""
    try:
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS os_rascunhos (
                    os_id TEXT PRIMARY KEY,
                    dados_json TEXT,
                    data_atualizacao TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes_sistema (
                    chave TEXT PRIMARY KEY,
                    valor TEXT,
                    data_atualizacao TEXT
                )
            """)
            conn.commit()
    except Exception:
        pass


def salvar_rascunho_provisorio(db_name: str, os_id: str, dados: dict) -> tuple:
    """Salva um snapshot provisório do preenchimento da OS no SQLite (proteção contra quedas de sinal)."""
    try:
        inicializar_tabela_rascunhos(db_name)
        data_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dados_json = json.dumps(dados, ensure_ascii=False)
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO os_rascunhos (os_id, dados_json, data_atualizacao)
                VALUES (?, ?, ?)
                ON CONFLICT(os_id) DO UPDATE SET
                    dados_json = excluded.dados_json,
                    data_atualizacao = excluded.data_atualizacao
            """, (str(os_id), dados_json, data_str))
            conn.commit()
        return True, f"Rascunho provisório da OS #{os_id} salvo com sucesso às {data_str.split()[1]}!"
    except Exception as e:
        return False, f"Erro ao salvar rascunho: {str(e)}"


def obter_rascunho_provisorio(db_name: str, os_id: str) -> tuple:
    """Recupera o rascunho provisório salvo para uma OS se existir."""
    try:
        inicializar_tabela_rascunhos(db_name)
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT dados_json, data_atualizacao FROM os_rascunhos WHERE os_id = ?", (str(os_id),))
            row = cur.fetchone()
            if row and row[0]:
                return json.loads(row[0]), str(row[1])
    except Exception:
        pass
    return {}, ""


def limpar_rascunho_provisorio(db_name: str, os_id: str) -> bool:
    """Remove o rascunho provisório após o fechamento bem-sucedido da OS."""
    try:
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM os_rascunhos WHERE os_id = ?", (str(os_id),))
            conn.commit()
        return True
    except Exception:
        return False


def obter_configuracao(db_name: str, chave: str, padrao: str = "") -> str:
    """Obtém parâmetro de configuração do sistema persistido no SQLite."""
    try:
        inicializar_tabela_rascunhos(db_name)
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (chave,))
            row = cur.fetchone()
            if row and row[0] is not None:
                return str(row[0]).strip()
    except Exception:
        pass
    return padrao


def salvar_configuracao(db_name: str, chave: str, valor: str) -> bool:
    """Persiste parâmetro de configuração do sistema no SQLite."""
    try:
        inicializar_tabela_rascunhos(db_name)
        dt = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO configuracoes_sistema (chave, valor, data_atualizacao)
                VALUES (?, ?, ?)
                ON CONFLICT(chave) DO UPDATE SET
                    valor = excluded.valor,
                    data_atualizacao = excluded.data_atualizacao
            """, (chave, str(valor).strip(), dt))
            conn.commit()
        return True
    except Exception:
        return False


TEMPLATES_RELATORIO_TECNICO = {
    "🔬 Manutenção Preventiva Completa (Padrão POP-EMED)": (
        "MANUTENÇÃO PREVENTIVA PERIÓDICA EXECUTADA CONFORME PROTOCOLO EMED. "
        "INSPEÇÃO VISUAL E MECÂNICA GERAL, LIMPEZA TÉCNICA INTERNA COM ASPIRAÇÃO E AR COMPRIMIDO SECO. "
        "LUBRIFICAÇÃO DAS GUIAS LINEARES, TRILHOS E SISTEMAS DE ROLAMENTO COM GRAXA SINTÉTICA DE ALTA PERFORMANCE. "
        "REAPERTO E VERIFICAÇÃO DE TORQUE NOS CABOS DE FORÇA, ELETROFREIOS E CONECTORES DE CONTROLE. "
        "TESTES DE SEGURANÇA ELÉTRICA: AFERIÇÃO DE TENSÃO REDE (F-N), RESISTÊNCIA DE ATERRAMENTO (T-N < 1.0V) E CORRENTE DE FUGA DENTRO DA NORMA NBR IEC 60601-1. "
        "TESTES FUNCIONAIS EM CARGA REAL EXECUTADOS COM ÊXITO. EQUIPAMENTO 100% OPERACIONAL E LIBERADO PARA USO CLÍNICO."
    ),
    "⚡ Manutenção Corretiva & Troca de Peça": (
        "MANUTENÇÃO CORRETIVA EXECUTADA PARA RESOLUÇÃO DE FALHA OPERACIONAL. "
        "DESMONTAGEM DO MÓDULO AFETADO, ISOLAMENTO DO CIRCUITO E ANÁLISE DE DIAGNÓSTICO. "
        "SUBSTITUIÇÃO DA PEÇA DANIFICADA POR COMPONENTE NOVO COMPATÍVEL HOMOLOGADO. "
        "AJUSTES DE TENSÃO, SINCRONISMO E CALIBRAÇÃO DOS SENSORES DE FIM DE CURSO. "
        "TESTES DE DISPARO, CARGA E REPRODUTIBILIDADE CONCLUÍDOS SEM APRESENTAÇÃO DE CÓDIGOS DE ERRO. "
        "EQUIPAMENTO TESTADO, HOMOLOGADO E LIBERADO PARA A EQUIPE MÉDICA."
    ),
    "🎯 Calibração Radiométrica & Dosimetria (Phantom / Anvisa)": (
        "AFERIÇÃO RADIOMÉTRICA E CALIBRAÇÃO DE FEIXE DE RAIOS-X EXECUTADA CONFORME RDC 611 DA ANVISA. "
        "AFERIÇÃO DE TENSÃO DE PICO (KVp), CORRENTE DO TUBO (mA) E TEMPO DE EXPOSIÇÃO (ms) UTILIZANDO MULTÍMETRO RADIOMÉTRICO CALIBRADO. "
        "TESTE DE COINCIDÊNCIA DO CAMPO LUMINOSO COM O CAMPO DE RADIAÇÃO (COLIMADOR). "
        "AVALIAÇÃO DA CAMADA SEMIREDUTORA (HVL), RENDIMENTO DO TUBO E QUALIDADE DE IMAGEM COM PHANTOM RADIOGRÁFICO PADRÃO. "
        "PARÂMETROS EM CONFORMIDADE COM AS ESPECIFICAÇÕES DO FABRICANTE."
    ),
    "🎛️ Reparo Eletrônico em Bancada / Placa de Potência": (
        "DIAGNÓSTICO E MANUTENÇÃO EM PLACA ELETRÔNICA NO LABORATÓRIO TÉCNICO EMED. "
        "IDENTIFICADOS COMPONENTES EM CURTO-CIRCUITO / DEGRADADOS NA ETAPA DE ALIMENTAÇÃO E CONTROLE. "
        "SUBSTITUIÇÃO DE SEMICONDUTORES, CAPACITORES E DIODOS DE POTÊNCIA. "
        "RESSOLDA COM ESTAÇÃO DE SOLDA PROFISSIONAL, BANHO TÉCNICO DE LIMPEZA E APLICAÇÃO DE VERNIZ PROTETOR. "
        "TESTES DE FONTE SOB CARGA EM BANCADA DURANTE 4 HORAS COM SUCESSO. REINSTALAÇÃO E VALIDAÇÃO NO EQUIPAMENTO."
    ),
    "🛡️ Segurança Elétrica, Cabos & Freios Mecânicos": (
        "INSPEÇÃO DE SEGURANÇA MECÂNICA E ELÉTRICA. "
        "REVISÃO DE CABOS DE AÇO DE SUSTENTAÇÃO DO CONTRAPESO E SISTEMA DE POLIAS. "
        "AFERIÇÃO DA FORÇA DE RETENÇÃO DOS ELETROFREIOS LONGITUDINAL, VERTICAL E TRANSVERSAL. "
        "CHECAGEM DOS INTERTRAVAMENTOS DE PORTA E BOTÕES DE PARADA DE EMERGÊNCIA (E-STOP). "
        "TESTES SATISFATÓRIOS CONFORME PADRÕES INTERNACIONAIS DE ENGENHARIA BIOMÉDICA."
    )
}


def gerar_sugestao_relatorio_clinico(equipamento: str, defeito: str = "", tipo_servico: str = "", causa_raiz: str = "") -> str:
    """Gera sugestão inteligente de relatório técnico da EMED baseado na modalidade e no sintoma relatado."""
    eq_norm = str(equipamento).upper().replace("Ó", "O").replace("Ã", "A").replace("Õ", "O").replace("É", "E")
    def_norm = str(defeito).upper().replace("Ó", "O").replace("Ã", "A").replace("Õ", "O").replace("É", "E")
    
    # 1. Tomografia
    if any(k in eq_norm for k in ["TOMO", "TC", "BRIGHTSPEED", "BRIVO", "OPTIMA"]):
        if any(w in def_norm for w in ["MESA", "UP", "DOWN", "SUBIDA", "DESCIDA", "ELEVACAO", "TRAV"]):
            return (
                "INTERVENÇÃO TÉCNICA NO SISTEMA DE MOVIMENTAÇÃO DA MESA DO PACIENTE (TOMOGRAFIA). "
                "REALIZADA ABERTURA DOS PAINÉIS LATERAIS E INSPEÇÃO DAS GUIAS LINEARES VERTICAIS E CABOS DE TRAÇÃO. "
                "IDENTIFICADO RESÍDUO E FALTA DE LUBRIFICAÇÃO NOS TRILHOS. EXECUTADA LIMPEZA QUÍMICA E APLICAÇÃO DE GRAXA SINTÉTICA DE ALTA VISCOSIDADE. "
                "EFETUADA A RECALIBRAÇÃO DOS POTENCIÔMETROS DE ELEVAÇÃO (ENCODERS UP/DOWN) E ALINHAMENTO DO SENSOR DE FIM DE CURSO. "
                "REALIZADOS 10 CICLOS DE TESTES COM CARGA (150 KG) COM RESPOSTA SUAVE E REPRODUTÍVEL. "
                "EQUIPAMENTO APROVADO E LIBERADO CONFORME PROTOCOLO POP-EMED-TC-004."
            )
        elif any(w in def_norm for w in ["TUBO", "KV", "MA", "DISPARO", "ALTA TENSAO", "ARCING", "GERADOR", "JEDI"]):
            return (
                "INSPEÇÃO E DIAGNÓSTICO DO SISTEMA GERADOR DE ALTA TENSÃO E TUBO DE RAIOS-X DE TC. "
                "AFERIÇÃO DAS CONEXÕES DE ALTA TENSÃO, VERIFICAÇÃO DO NÍVEL E FLUXO DO ÓLEO DE REFRIGERAÇÃO DO MONOBLOCO. "
                "EXECUTADA LEITURA DO HISTÓRICO DE ERROS DE ARCING E CALIBRAÇÃO DE CORRENTE DE FILAMENTO. "
                "PROCEDIMENTO DE WARM-UP (AQUECIMENTO GRADUAL DO ÂNODO) EXECUTADO COM SUCESSO. "
                "CALIBRAÇÃO DE AR (AIR CALIBRATION) REALIZADA NOS DETECTORES COM NÍVEIS DE RUÍDO DENTRO DO TOLERADO PELO FABRICANTE."
            )
        else:
            return (
                "MANUTENÇÃO PREVENTIVA E CALIBRAÇÃO GERAL EM SISTEMA DE TOMOGRAFIA COMPUTADORIZADA. "
                "LIMPEZA DO GANTRY, CHECAGEM DAS ESCOVAS DO SLIP-RING E VERIFICAÇÃO DE DESGASTE. "
                "INSPEÇÃO DOS SISTEMAS DE REFRIGERAÇÃO, TESTE DE SENSORES DE PARADA DE EMERGÊNCIA E LASERS DE POSICIONAMENTO. "
                "AFERIÇÃO DE SEGURANÇA ELÉTRICA E QUALIDADE DE IMAGEM COM PHANTOM DE CALIBRAÇÃO. EQUIPAMENTO 100% OPERACIONAL."
            )
            
    # 2. Mamografia
    elif any(k in eq_norm for k in ["MAMO", "SENOGRAPHE", "LILLY", "SELENIA"]):
        if any(w in def_norm for w in ["COMPRESS", "PEDAL", "FORCA", "DANO"]):
            return (
                "MANUTENÇÃO CORRETIVA NO SISTEMA DE COMPRESSÃO E PEDAIS DO MAMÓGRAFO. "
                "DESMONTAGEM DA CAIXA DE REDUÇÃO E ENGRENAGENS DO SISTEMA MOTORIZADO DE COMPRESSÃO. "
                "AJUSTE DA TENSÃO MECÂNICA, LUBRIFICAÇÃO DOS EIXOS E TESTE DE CONTINUIDADE NOS MICRO-SWITCHES DOS PEDAIS. "
                "CALIBRAÇÃO DA CÉLULA DE CARGA: AJUSTE DO LIMITE MÁXIMO DE COMPRESSÃO PARA 18 daN CONFORME REQUISITOS DA RDC 611/ANVISA. "
                "TESTES DE DESCOMPRESSÃO AUTOMÁTICA DE EMERGÊNCIA VALIDADOS COM SUCESSO."
            )
        else:
            return (
                "MANUTENÇÃO PREVENTIVA E AFERIÇÃO RADIOMÉTRICA EM MAMÓGRAFO. "
                "INSPEÇÃO MECÂNICA DO BRAÇO C, VERIFICAÇÃO DOS ELETROFREIOS DE ROTAÇÃO E ALINHAMENTO DA BANDEJA DE COMPRESSÃO. "
                "AFERIÇÃO DA FOTOCÉLULA (AEC) E CONTROLE DE QUALIDADE COM PHANTOM ACRÍLICO PADRÃO. "
                "NENHUMA ANOMALIA DETECTADA. EQUIPAMENTO LIBERADO PARA EXAMES CLÍNICOS."
            )

    # 3. Raio-X
    elif any(k in eq_norm for k in ["RAIO", "RX", "LOTUS", "SHIMADZU", "MOBILEDART", "NEUVISION"]):
        if any(w in def_norm for w in ["FREIO", "ESTATIVA", "MESA", "CABO", "PESO"]):
            return (
                "MANUTENÇÃO MECÂNICA E ELÉTRICA NA ESTATIVA E MESA DE EXAMES DE RAIOS-X. "
                "AJUSTE E TENSIONAMENTO DOS CABOS DE AÇO DO CONTRAPESO COM INSPEÇÃO DE DESGASTE. "
                "REGULAGEM DA FOLGA DOS ELETROFREIOS LONGITUDINAL E VERTICAL COM TESTE DE RETENÇÃO EM CARGA. "
                "LUBRIFICAÇÃO DOS TRILHOS E SISTEMA DE ROLAMENTOS. "
                "MOVIMENTAÇÃO SUAVE RESTABELECIDA EM TODA A EXTENSÃO DO CURSO."
            )
        elif any(w in def_norm for w in ["COLIMADOR", "LUZ", "CAMPO", "LAMPADA"]):
            return (
                "ALINHAMENTO E CALIBRAÇÃO DO COLIMADOR DE RAIOS-X. "
                "SUBSTITUIÇÃO DA LÂMPADA HALÓGENA DE PROJEÇÃO E AJUSTE DO ESPELHO REFLETOR. "
                "CALIBRAÇÃO DE CONGRUÊNCIA ENTRE O CAMPO DE LUZ E O CAMPO EFETIVO DE RADIAÇÃO CONFORME PORTARIA ANVISA. "
                "VERIFICAÇÃO DAS LÂMINAS DE CHUMBO E TEMPORIZADOR AUTOMÁTICO DE ILUMINAÇÃO. APROVADO."
            )
        else:
            return (
                "MANUTENÇÃO PREVENTIVA E AFERIÇÃO RADIOMÉTRICA EM EQUIPAMENTO DE RAIOS-X. "
                "AFERIÇÃO DE KVP, MA E TEMPO DE DISPARO COM MULTÍMETRO RADIOMÉTRICO HOMOLOGADO. "
                "TESTE DE REPETIBILIDADE, LINEARIDADE E RENDIMENTO DO TUBO. "
                "INSPEÇÃO DA ISOLAÇÃO DOS CABOS DE ALTA TENSÃO E NÍVEL DE ÓLEO DO TANQUE GERADOR. EQUIPAMENTO LIBERADO."
            )

    # 4. Padrão Geral
    return (
        "MANUTENÇÃO TÉCNICA ESPECIALIZADA REALIZADA PELA EQUIPE DA EMED ELETROMEDICINA. "
        "INSPEÇÃO COMPLETA DOS SISTEMAS MECÂNICOS, ELETRÔNICOS E DE CONTROLE. "
        "TESTES DE FUNCIONALIDADE, CALIBRAÇÃO DE PARÂMETROS OPERACIONAIS E VERIFICAÇÃO DE SEGURANÇA. "
        "EQUIPAMENTO AVALIADO E LIBERADO PARA USO NORMAL CONFORME PADRÕES DA ENGENHARIA BIOMÉDICA."
    )


def obter_checklist_acoes_sugeridas(equipamento: str, defeito: str = "") -> list:
    """Retorna itens práticos de checklist de intervenção para o técnico marcar no celular."""
    eq_norm = str(equipamento).upper().replace("Ó", "O").replace("Ã", "A").replace("Õ", "O").replace("É", "E")
    def_norm = str(defeito).upper().replace("Ó", "O").replace("Ã", "A").replace("Õ", "O").replace("É", "E")

    # 1. Tomografia
    if any(k in eq_norm for k in ["TOMO", "TC", "BRIGHTSPEED", "BRIVO", "OPTIMA"]):
        if any(w in def_norm for w in ["MESA", "UP", "DOWN", "SUBIDA", "DESCIDA", "ELEVACAO", "TRAV"]):
            return [
                "Desmontagem e remoção dos painéis laterais de proteção da mesa",
                "Inspeção visual dos trilhos, correntes e cabos de sustentação mecânica",
                "Limpeza química e desengraxe das guias lineares verticais",
                "Aplicação de graxa sintética de alta viscosidade nos rolamentos e guias",
                "Ajuste de tensão mecânica da correia e fuso de acionamento",
                "Calibração dos potenciômetros e encoders de elevação (up/down)",
                "Ajuste e teste de acionamento dos limit switches (sensores de fim de curso)",
                "Teste de movimentação contínua em curso completo sem ruídos ou travamento",
                "Teste funcional com carga nominal de 150 kg com retorno suave",
                "Liberação do equipamento para a equipe clínica conforme POP-EMED-TC-004",
            ]
        elif any(w in def_norm for w in ["TUBO", "KV", "MA", "DISPARO", "ALTA TENSAO", "ARCING", "GERADOR", "JEDI"]):
            return [
                "Verificação visual e teste de isolação das conexões e buchas de alta tensão (HV cables)",
                "Checagem do nível, fluxo e temperatura do óleo de arrefecimento do monobloco",
                "Leitura e limpeza do histórico de erros de arcing no gerador JEDI e console",
                "Calibração da corrente de filamento e tensão de aceleração (kVp / mA)",
                "Execução do protocolo de aquecimento progressivo do ânodo (warm-up)",
                "Calibração de ar nos detectores (Air Calibration / DAS)",
                "Verificação dos intertravamentos de segurança e paradas de emergência do Gantry",
                "Disparos de validação de qualidade de feixe e homogeneidade",
            ]
        else:
            return [
                "Abertura das tampas do Gantry e aspiração de poeira/resíduos internos",
                "Inspeção visual das escovas e pistas do slip-ring com medição de desgaste",
                "Limpeza técnica especializada dos trilhos e anéis de contato do slip-ring",
                "Checagem do sistema de refrigeração líquida e arrefecimento do Gantry",
                "Alinhamento e teste dos lasers de posicionamento sagital, coronal e axial",
                "Aferição de segurança elétrica: resistência de terra e corrente de fuga (NBR IEC 60601)",
                "Execução de calibração periódica de detectores e teste de homogeneidade de imagem",
                "Equipamento 100% operacional e liberado para rotina de exames",
            ]

    # 2. Mamografia
    elif any(k in eq_norm for k in ["MAMO", "SENOGRAPHE", "LILLY", "SELENIA"]):
        if any(w in def_norm for w in ["COMPRESS", "PEDAL", "FORCA", "DANO"]):
            return [
                "Desmontagem da tampa da coluna e inspeção da caixa de redução da compressão",
                "Inspeção mecânica das engrenagens, fusos e lubrificação com graxa técnica",
                "Teste de continuidade elétrica e resposta nos microswitches dos pedais de acionamento",
                "Calibração da célula de carga e ajuste da força máxima de compressão (limite 18 daN)",
                "Teste funcional do sistema de descompressão automática de emergência",
                "Alinhamento da bandeja de compressão e teste de paralelismo com o receptor de imagem",
                "Aferição da fotocélula (AEC) em phantom acrílico padrão",
                "Certificação dos parâmetros de compressão conforme requisitos da RDC 611/ANVISA",
            ]
        else:
            return [
                "Inspeção mecânica geral do braço C e travamentos angulares",
                "Aferição dos eletrofreios de rotação e verificação de folgas mecânicas",
                "Limpeza e higienização técnica da mesa de exame e bandejas de compressão",
                "Teste dos pedais de controle e comandos no painel da workstation",
                "Controle de qualidade de imagem radiográfica com phantom de mamografia padrão",
                "Verificação de reprodutibilidade e linearidade de dose do feixe",
                "Equipamento liberado e em conformidade técnica para exames clínicos",
            ]

    # 3. Raio-X
    elif any(k in eq_norm for k in ["RAIO", "RX", "LOTUS", "SHIMADZU", "MOBILEDART", "NEUVISION"]):
        if any(w in def_norm for w in ["FREIO", "ESTATIVA", "MESA", "CABO", "PESO"]):
            return [
                "Inspeção visual e teste de tração nos cabos de aço de sustentação do contrapeso",
                "Regulagem de pressão e alinhamento das sapatas dos eletrofreios longitudinal e vertical",
                "Limpeza técnica e lubrificação das colunas de deslizamento e roldanas",
                "Verificação dos botões de liberação de freios no comando do colimador",
                "Teste de movimentação suave em toda a extensão do curso da estativa e mesa",
                "Reaperto de parafusos estruturais e verificação de batentes de fim de curso",
                "Trava mecânica e elétrica testada com carga e validada",
            ]
        elif any(w in def_norm for w in ["COLIMADOR", "LUZ", "CAMPO", "LAMPADA"]):
            return [
                "Abertura do conjunto colimador e substituição da lâmpada de projeção halógena",
                "Limpeza e ajuste do espelho refletor interno e lâminas de chumbo",
                "Calibração de coincidência do campo de luz com o campo de radiação X (tolerância < 2%)",
                "Aferição do temporizador automático de desligamento da luz do colimador",
                "Verificação dos botões de ajuste de abertura de campo transversal e longitudinal",
                "Disparos de radiografia teste com chassi/detector para validação de bordas",
            ]
        else:
            return [
                "Inspeção geral da estativa, mesa de exames e cabeçote monobloco",
                "Aferição radiométrica de kVp, mA e tempo com multímetro calibrado",
                "Teste de repetibilidade e linearidade da taxa de kerma no ar (RDC 611)",
                "Checagem do estado dos cabos de alta tensão e aterramento de carcaça",
                "Revisão dos freios mecânicos e fluidez de movimentação de todos os eixos",
                "Equipamento aprovado nos ensaios de segurança e liberado para uso médico",
            ]

    # 4. Padrão Geral / Preventiva
    return [
        "Inspeção visual externa e interna do chassi, conectores e fiações",
        "Limpeza técnica interna especializada para eliminação de impurezas e poeira",
        "Reaperto de bornes elétricos, barramentos de alimentação e conexões de aterramento",
        "Teste de segurança elétrica: resistência de condutor de proteção e corrente de fuga",
        "Lubrificação técnica dos pontos mecânicos móveis, eixos e articulações",
        "Aferição dos parâmetros nominais e calibração de sensores operacionais",
        "Teste de todos os comandos nos painéis de controle e paradas de emergência",
        "Realização de ensaios funcionais simulados de rotina com liberação clínica",
    ]
