import os
import pandas as pd
import streamlit as st
from emed_core import (
    limpar_texto,
    get_db_connection,
    garantir_pk_tabela_os,
    salvar_dataframe_transacional,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "emed.db")
CAMINHO_EXCEL = os.path.join(BASE_DIR, "base_clientes.xlsx")


def init_db(db_name: str = DB_NAME, caminho_excel: str = CAMINHO_EXCEL):
    with get_db_connection(db_name) as conn_sq:
        garantir_pk_tabela_os(conn_sq)
        cur = conn_sq.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS clientes_internos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_setor TEXT UNIQUE, responsavel TEXT, ramal_whatsapp TEXT, centro_custo TEXT, observacoes TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tecnicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE, telefone TEXT, partida TEXT, sede TEXT, senha TEXT, perfil TEXT, assinatura_padrao TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS veiculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modelo TEXT, placa TEXT UNIQUE, km_atual INTEGER, km_ultima_revisao INTEGER,
                km_proxima_revisao INTEGER, status_manutencao TEXT, foto_carro TEXT,
                historico_manutencao TEXT, proximas_manutencoes TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS estoque_pecas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE, nome_peca TEXT, quantidade INTEGER, preco_custo REAL,
                margem_contrato REAL DEFAULT 30.0, margem_avulso REAL DEFAULT 60.0,
                tipo_item TEXT DEFAULT 'PEÇA COMERCIAL (OS)'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS solicitacoes_pecas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tecnico TEXT, destino_cliente TEXT, itens_solicitados TEXT,
                instrumentos_solicitados TEXT, status_pedido TEXT, data_pedido TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS baixas_consumiveis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tecnico_setor TEXT, codigo_item TEXT, nome_item TEXT,
                quantidade INTEGER, finalidade TEXT, data_baixa TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS preferencias_usuario (
                usuario TEXT PRIMARY KEY,
                atalhos_excluidos TEXT DEFAULT '[]'
            )
        """)

        colunas_extras_veiculos = [
            ("foto_carro", "TEXT DEFAULT ''"),
            ("historico_manutencao", "TEXT DEFAULT ''"),
            ("proximas_manutencoes", "TEXT DEFAULT ''")
        ]
        for col_n, col_t in colunas_extras_veiculos:
            try:
                cur.execute(f"ALTER TABLE veiculos ADD COLUMN {col_n} {col_t}")
            except Exception:
                pass

        colunas_extras_estoque = [
            ("margem_contrato", "REAL DEFAULT 30.0"),
            ("margem_avulso", "REAL DEFAULT 60.0"),
            ("tipo_item", "TEXT DEFAULT 'PEÇA COMERCIAL (OS)'")
        ]
        for col_n, col_t in colunas_extras_estoque:
            try:
                cur.execute(f"ALTER TABLE estoque_pecas ADD COLUMN {col_n} {col_t}")
            except Exception:
                pass

        for col_tec_n, col_tec_t in [("assinatura_padrao", "TEXT DEFAULT ''"), ("rubrica_img", "TEXT DEFAULT ''")]:
            try:
                cur.execute(f"ALTER TABLE tecnicos ADD COLUMN {col_tec_n} {col_tec_t}")
            except Exception:
                pass

        cur.execute("SELECT COUNT(*) FROM tecnicos")
        if cur.fetchone()[0] == 0:
            dados_iniciais_tecs = [
                ("NETTO", "5585988888888", "MARAPONGA", "FORTALEZA", "1234", "Gestor", "VALFREDO V. O. NETTO - CFT"),
                ("ARQUIMEDES", "558597777777", "FORTALEZA", "FORTALEZA", "1234", "Técnico", "ARQUIMEDES - CFT"),
                ("GABRIEL", "558596666666", "FORTALEZA", "FORTALEZA", "1234", "Técnico", "GABRIEL - CFT"),
                ("SÉRGIO", "558595555555", "FORTALEZA - CE", "FORTALEZA", "1234", "Técnico", "SÉRGIO - CFT"),
                ("FELIPE", "558594444444", "FORTALEZA", "FORTALEZA", "1234", "Técnico", "FELIPE - CFT"),
                ("TONY", "558593333333", "FORTALEZA - (EUSÉBIO)", "FORTALEZA", "1234", "Técnico", "TONY - CFT"),
                ("JAIR", "558592222222", "FORTALEZA - (EUSÉBIO)", "FORTALEZA", "1234", "Técnico", "JAIR - CFT"),
                ("ANTONIO", "558591111111", "FORTALEZA", "FORTALEZA", "1234", "Técnico", "ANTONIO - CFT")
            ]
            cur.executemany("""
                INSERT OR IGNORE INTO tecnicos
                (nome, telefone, partida, sede, senha, perfil, assinatura_padrao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, dados_iniciais_tecs)

        cur.execute("SELECT COUNT(*) FROM veiculos")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT OR IGNORE INTO veiculos
                (modelo, placa, km_atual, km_ultima_revisao, km_proxima_revisao, status_manutencao, foto_carro, historico_manutencao, proximas_manutencoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "Renault Captur 1.6 16V SCe", "EMD-2026", 45000, 40000, 50000,
                "Disponível", "", "Troca de óleo, filtros e velas aos 40.000 KM",
                "Revisão de 50.000 KM (Freios e Suspensão)"
            ))

        catalogo_iniciais_itens = [
            # INSTRUMENTOS E FERRAMENTARIA ESPECIALIZADA
            ("FER-001", "MULTÍMETRO ESPECIAL ATÉ 1000V (AFERIÇÃO FOTOCÉLULA / AEC & MAMÓGRAFO)", 3, 2800.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-002", "MULTÍMETRO DIGITAL TRUE RMS CALIBRADO", 6, 950.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-003", "OSCILOSCÓPIO DIGITAL PORTÁTIL COM PONTAS HV / ATENUADAS", 2, 6500.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-004", "MEDIDOR RADIOMÉTRICO MULTI-PARÂMETRO (kVp, DOSE, TEMPO, CSR)", 2, 18500.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-005", "KIT DE MAMOGRAFIA (PHANTOM, ACRÍLICOS, BALANÇA E CASSETE)", 2, 4200.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-006", "FANTOMA OFICIAL DE CALIBRAÇÃO DE DENSIDADE ÓSSEA (DENSITOMETRIA)", 1, 7800.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-007", "FANTOMA DE CABEÇA E CORPO CTDI (TOMOGRAFIA)", 1, 12000.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-008", "NÍVEL A LASER AUTONIVELANTE COM TRIPÉ", 3, 850.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-009", "TRENA LASER MÉTRICA DIGITAL", 4, 320.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-010", "TORQUÍMETRO CALIBRADO COM JOGO DE SOQUETES", 3, 1400.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-011", "ALICATE AMPERÍMETRO DC/AC TRUE RMS", 4, 680.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-012", "TALHA DE IÇAMENTO MECÂNICA / MACACO HIDRÁULICO DE GANTRY", 2, 2200.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-013", "ESTAÇÃO DE SOLDA PORTÁTIL ESD COM CONTROLE TÉRMICO", 3, 750.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-014", "SOPRADOR / ASPIRADOR ANTIESTÁTICO ESD", 3, 550.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-015", "GIGA DE COMUNICAÇÃO JEDI & CABOS DE SERVIÇO (TOMOGRAFIA)", 2, 4500.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-016", "KIT FURADEIRA DE IMPACTO COM BROCAS (5, 8, 10 E 12MM)", 2, 1100.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),
            ("FER-017", "KIT DE ALINHAMENTO DE COLIMADOR (BEAM ALIGNMENT TOOLS & CAMPO LUMINOSO)", 2, 3800.00, 0.0, 0.0, "INSTRUMENTO / FERRAMENTA"),

            # PEÇAS DE REPOSIÇÃO (COMERCIAIS / OS)
            ("PEC-001", "TUBO DE RAIOS-X", 2, 15000.00, 25.0, 50.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-002", "PLACA DE FONTE DE ALTA TENSÃO", 4, 3500.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-003", "CABO DE ALTA TENSÃO", 5, 1200.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-004", "SENSOR DE TEMPERATURA", 8, 450.00, 35.0, 70.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-005", "BOBINA SOLENOIDE / ELETROFREIO (ESTATIVA PORTA-TUBO / MESA)", 6, 480.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-006", "BOTÃO DE ACIONAMENTO / MICROSWITCH DE FREIO", 12, 85.00, 35.0, 70.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-007", "FONTE DE ALIMENTAÇÃO CHAVEADA INDUSTRIAL (12V / 24V / 100V)", 5, 380.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-008", "CABO DE ALIMENTAÇÃO / CHICOTE FLEXÍVEL DE FREIO", 10, 110.00, 35.0, 70.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-009", "BATERIA SOBRESSALENTE PARA FLAT PANEL DR WI-FI", 4, 890.00, 25.0, 50.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-010", "INTERFACE BOX / FONTE DE ALIMENTAÇÃO DO DETECTOR DR", 2, 3200.00, 25.0, 50.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-011", "CABO DE COMUNICAÇÃO TETHER CABLE & REDE CAT6 BLINDADO", 6, 260.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
            ("PEC-012", "KIT SORTIDO DE FUSÍVEIS DE AÇÃO RÁPIDA E RETARDADA", 20, 45.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),

            # CONSUMÍVEIS & LIMPEZA TÉCNICA
            ("CON-001", "ABRAÇADEIRA DE NYLON (PACOTE 100 UN)", 15, 25.00, 0.0, 0.0, "CONSUMÍVEL INTERNO"),
            ("CON-002", "FITA ISOLANTE ALTA FUSÃO", 10, 35.00, 0.0, 0.0, "CONSUMÍVEL INTERNO"),
            ("CON-003", "KIT LIMPEZA PADRÃO (LIMPA-CONTATOS, DESENGRIPANTE, VEJA, PANOS E ASPIRADOR)", 8, 180.00, 0.0, 0.0, "CONSUMÍVEL INTERNO"),
            ("CON-004", "ÁLCOOL ISOPROPÍLICO 99% ESD (FRASCO 1L)", 10, 40.00, 0.0, 0.0, "CONSUMÍVEL INTERNO"),
            ("CON-005", "GRAXA ESPECIAL DE ALTA ROTAÇÃO SLIPRING / ROLAMENTOS", 6, 160.00, 0.0, 0.0, "CONSUMÍVEL INTERNO")
        ]
        cur.executemany("""
            INSERT OR IGNORE INTO estoque_pecas
            (codigo, nome_peca, quantidade, preco_custo, margem_contrato, margem_avulso, tipo_item)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, catalogo_iniciais_itens)

        cur.execute("SELECT COUNT(*) FROM clientes_internos")
        if cur.fetchone()[0] == 0:
            dados_iniciais_internos = [
                ("ESTOQUE / ALMOXARIFADO", "TONY", "558593333333", "CC-EST-01", "Controlo central de peças, ferramentas e consumíveis"),
                ("FINANCEIRO / FATURAMENTO", "YASMIM", "558592222222", "CC-FIN-02", "Emissão de NF, boletos, PIX e compras"),
                ("INFRAESTRUTURA & FROTA", "PAULINHO", "558591111111", "CC-INF-03", "Gestão de viaturas, sede e manutenção predial"),
                ("LABORATÓRIO ELETRÓNICO INTERNO", "NETTO", "5585988888888", "CC-LAB-04", "Bancada de reparo de placas, tomografia e patologia")
            ]
            cur.executemany("""
                INSERT OR IGNORE INTO clientes_internos
                (nome_setor, responsavel, ramal_whatsapp, centro_custo, observacoes)
                VALUES (?, ?, ?, ?, ?)
            """, dados_iniciais_internos)

        cur.execute("SELECT COUNT(*) FROM clientes_equipamentos")
        qtd_os_atual = cur.fetchone()[0]

    if qtd_os_atual == 0 and os.path.exists(caminho_excel):
        try:
            df_ex = pd.read_excel(caminho_excel)
            if not df_ex.empty:
                salvar_dataframe_transacional(df_ex, db_name)
        except Exception as e:
            print(f"Erro ao importar Excel no init: {e}")


@st.cache_data(ttl=15)
def carregar_dados(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM clientes_equipamentos", conn)


@st.cache_data(ttl=15)
def carregar_tecnicos(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM tecnicos", conn)


@st.cache_data(ttl=15)
def carregar_veiculos(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM veiculos", conn)


@st.cache_data(ttl=15)
def carregar_estoque(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM estoque_pecas", conn)


@st.cache_data(ttl=15)
def carregar_clientes_internos(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM clientes_internos", conn)


@st.cache_data(ttl=15)
def carregar_solicitacoes(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM solicitacoes_pecas ORDER BY id DESC", conn)


@st.cache_data(ttl=15)
def carregar_baixas_consumiveis(db_name: str = DB_NAME):
    with get_db_connection(db_name) as conn:
        return pd.read_sql_query("SELECT * FROM baixas_consumiveis ORDER BY id DESC", conn)


def montar_equipa_tecnica(df_tecnicos: pd.DataFrame) -> dict:
    equipa = {}
    for _, row in df_tecnicos.iterrows():
        nome_t = limpar_texto(row.get('nome'), '').upper()
        if nome_t:
            equipa[nome_t] = {
                "tel": limpar_texto(row.get('telefone'), ''),
                "partida": limpar_texto(row.get('partida'), 'FORTALEZA'),
                "sede": limpar_texto(row.get('sede'), 'FORTALEZA'),
                "perfil": limpar_texto(row.get('perfil'), 'Técnico'),
                "assinatura": limpar_texto(row.get('assinatura_padrao'), f"{nome_t} - CFT"),
                "rubrica_img": limpar_texto(row.get('rubrica_img'), '')
            }

    if not equipa:
        equipa["NETTO"] = {
            "tel": "5585988888888",
            "partida": "FORTALEZA - CE",
            "sede": "EUSEBIO",
            "perfil": "Gestor",
            "assinatura": "VALFREDO V. O. NETTO - CFT",
            "rubrica_img": ""
        }
    return equipa


def salvar_dados_seguro(dataframe: pd.DataFrame, db_name: str = DB_NAME, caminho_excel: str = CAMINHO_EXCEL) -> bool:
    try:
        caminho_bkp = os.path.join(BASE_DIR, "base_clientes_backup.xlsx")
        return salvar_dataframe_transacional(dataframe, db_name, caminho_excel, caminho_bkp)
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar dados: {e}")
        return False


def carregar_atalhos_excluidos_usuario(db_name: str, usuario: str) -> list:
    import json
    usr_key = limpar_texto(usuario, "NETTO").upper()
    try:
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS preferencias_usuario (usuario TEXT PRIMARY KEY, atalhos_excluidos TEXT DEFAULT '[]')"
            )
            cur.execute("SELECT atalhos_excluidos FROM preferencias_usuario WHERE usuario = ?", (usr_key,))
            row = cur.fetchone()
            if row and row[0]:
                dados = json.loads(row[0])
                if isinstance(dados, list):
                    return dados
    except Exception:
        pass
    return []


def salvar_atalhos_excluidos_usuario(db_name: str, usuario: str, excluidos: list) -> None:
    import json
    usr_key = limpar_texto(usuario, "NETTO").upper()
    try:
        with get_db_connection(db_name) as conn:
            cur = conn.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS preferencias_usuario (usuario TEXT PRIMARY KEY, atalhos_excluidos TEXT DEFAULT '[]')"
            )
            cur.execute(
                "INSERT INTO preferencias_usuario (usuario, atalhos_excluidos) VALUES (?, ?) "
                "ON CONFLICT(usuario) DO UPDATE SET atalhos_excluidos = excluded.atalhos_excluidos",
                (usr_key, json.dumps(excluidos, ensure_ascii=False)),
            )
            conn.commit()
    except Exception:
        pass
