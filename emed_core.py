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
            "FER-006: Fantoma Oficial de Calibração de Densidade Óssea",
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
            "FER-005: Fantomas de Calibração Padrão (Cabeça / Corpo / QA)",
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
        cur.execute("SELECT quantidade FROM estoque_pecas WHERE nome_peca = ?", (nome_peca,))
        row = cur.fetchone()
        if not row:
            return False, f"⚠️ Peça '{nome_peca}' não localizada no estoque!", ref_anterior
        saldo_atual = int(row[0])
        if int(qtd_aplicada) > saldo_atual:
            return (
                False,
                f"⚠️ Saldo insuficiente para '{nome_peca}'! Disponível: {saldo_atual} un.",
                ref_anterior
            )
        cur.execute(
            "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE nome_peca = ?",
            (int(qtd_aplicada), nome_peca)
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

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Obter dados de preço da peça em estoque_pecas
        cur.execute("""
            SELECT codigo, preco_custo, margem_contrato, margem_avulso, quantidade 
            FROM estoque_pecas 
            WHERE UPPER(nome_peca) = ? OR UPPER(codigo) = ?
        """, (nome_peca_limpo, nome_peca_limpo))
        row_peca = cur.fetchone()

        cod_peca = row_peca[0] if row_peca else "PEC-000"
        preco_custo = float(row_peca[1]) if row_peca and row_peca[1] is not None else 0.0
        m_contrato = float(row_peca[2]) if row_peca and row_peca[2] is not None else 25.0
        m_avulso = float(row_peca[3]) if row_peca and row_peca[3] is not None else 50.0

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

