import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
import os
import urllib.parse
import math
import sqlite3
import json
import base64
import plotly.express as px
from emed_core import (
    limpar_texto,
    limpar_float,
    limpar_int,
    get_db_connection,
    garantir_pk_tabela_os,
    normalizar_dataframe_os,
    salvar_dataframe_transacional,
    obter_id_os,
    sincronizar_os_offline_idempotente,
    aplicar_peca_os_idempotente,
    atualizar_status_solicitacao_peca,
    sugerir_proxima_etapa_preventiva,
    agendar_proxima_etapa_circular,
    calcular_dias_aguardando_orcamento
)

# Configuração da Página do Sistema EMED com Tema Escuro Nativo
st.set_page_config(
    page_title="EMED - Gestão de Equipamentos e Frota",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Bloqueia o tradutor automático do navegador para evitar o erro 'removeChild'
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

# ----------------------------------------------------
# ESTILIZAÇÃO CSS CUSTOMIZADA (TEMA ESCURO & ZERO BOTÕES BRANCOS)
# ----------------------------------------------------
st.markdown("""
    <style>
    .stApp {
        background-color: #0b132b;
        color: #ffffff;
    }
    header[data-testid="stHeader"] {
        background-color: #0b132b !important;
    }
    .stApp > header {
        background-color: transparent !important;
    }
    p, span, label, div {
        color: #f8fafc !important;
    }        
    [data-testid="stSidebar"] {
        background-color: #1c2541;
        border-right: 1px solid #3a506b;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #cbd5e1 !important;
    }

    /* Caixas de Seleção (Selectbox / Multiselect / Dropdowns / Popovers) */
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div,
    div[data-baseweb="select"] div {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border-color: #3a506b !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    div[data-baseweb="select"] svg {
        fill: #64dfdf !important;
        color: #64dfdf !important;
    }
    div[data-baseweb="tag"] {
        background-color: #3a506b !important;
        color: #ffffff !important;
        border: 1px solid #64dfdf !important;
    }
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    div[role="listbox"],
    ul[data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #64dfdf !important;
    }
    ul[data-baseweb="menu"] li,
    li[role="option"],
    div[role="option"] {
        color: #ffffff !important;
        background-color: #1c2541 !important;
    }
    ul[data-baseweb="menu"] li:hover,
    li[role="option"]:hover,
    div[role="option"]:hover,
    li[aria-selected="true"],
    div[aria-selected="true"] {
        background-color: #3a506b !important;
        color: #64dfdf !important;
    }

    /* Calendário (DateInput Popover) */
    div[data-baseweb="calendar"],
    div[data-baseweb="calendar"] * {
        background-color: #1c2541 !important;
        color: #ffffff !important;
    }

    /* Inputs Numéricos, de Texto, Textarea e Containers BaseWeb (incluindo desabilitados) */
    div[data-baseweb="input"],
    div[data-baseweb="base-input"],
    div[data-baseweb="textarea"] {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #3a506b !important;
        border-radius: 8px !important;
    }
    .stNumberInput input,
    .stTextInput input,
    .stDateInput input,
    .stTextArea textarea,
    div[data-baseweb="input"] input,
    div[data-baseweb="base-input"] input,
    div[data-baseweb="textarea"] textarea {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        caret-color: #64dfdf !important;
        text-transform: uppercase !important;
    }
    input:disabled,
    textarea:disabled,
    input[disabled],
    textarea[disabled] {
        background-color: #151d36 !important;
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        opacity: 1 !important;
    }
    input::placeholder,
    textarea::placeholder {
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        opacity: 0.8 !important;
    }
    .stNumberInput button {
        background-color: #3a506b !important;
        color: #ffffff !important;
    }
    .stNumberInput button:hover {
        background-color: #64dfdf !important;
        color: #0b132b !important;
    }

    /* Formulários, Abas, Alertas, Métricas e Barra de Ferramentas */
    [data-testid="stForm"] {
        background-color: #141c35 !important;
        border: 1px solid #3a506b !important;
        border-radius: 10px !important;
        padding: 16px !important;
    }
    [data-testid="stElementToolbar"],
    [data-testid="stElementToolbar"] button {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border-color: #3a506b !important;
    }
    [data-testid="stAlert"] {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #3a506b !important;
    }
    [data-testid="stMetric"] {
        background-color: #1c2541 !important;
        border: 1px solid #3a506b !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
    }
    button[data-baseweb="tab"] {
        background-color: transparent !important;
        color: #cbd5e1 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #64dfdf !important;
        border-bottom-color: #64dfdf !important;
    }

    /* Botões Gerais, Form Submit e Download */
    .stButton button,
    div.stButton > button,
    [data-testid="stFormSubmitButton"] > button,
    [data-testid="stDownloadButton"] > button,
    button[kind="secondary"],
    button[kind="primary"],
    button[kind="secondaryFormSubmit"],
    button[kind="primaryFormSubmit"] {
        background-color: #1c2541 !important;
        color: #ffffff !important;
        border: 1px solid #64dfdf !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
    }
    .stButton button:hover,
    div.stButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover,
    button[kind="secondary"]:hover,
    button[kind="primary"]:hover {
        background-color: #3a506b !important;
        border-color: #64dfdf !important;
        color: #64dfdf !important;
    }

    /* Expanders escuros */
    [data-testid="stExpander"],
    [data-testid="stExpander"] details,
    [data-testid="stExpanderDetails"] {
        background-color: #1c2541 !important;
        border: 1px solid #3a506b !important;
        border-radius: 10px !important;
        margin-bottom: 10px !important;
        color: #ffffff !important;
    }
    [data-testid="stExpander"] details summary {
        background-color: #1c2541 !important;
        color: #64dfdf !important;
        border-radius: 10px !important;
    }
    [data-testid="stExpander"] details summary:hover {
        background-color: #25335a !important;
    }
    [data-testid="stExpander"] details summary p,
    [data-testid="stExpander"] details summary span,
    [data-testid="stExpander"] details summary svg {
        color: #64dfdf !important;
        fill: #64dfdf !important;
        font-weight: 600 !important;
    }

    /* File Uploader escuro */
    [data-testid="stFileUploader"] section {
        background-color: #1c2541 !important;
        border: 1px dashed #64dfdf !important;
        color: #ffffff !important;
    }
    [data-testid="stFileUploader"] section button {
        background-color: #3a506b !important;
        color: #ffffff !important;
        border: 1px solid #64dfdf !important;
    }

    .client-card {
        background-color: #1c2541;
        border: 1px solid #3a506b;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .client-card h3 {
        color: #64dfdf !important;
        margin-top: 0;
        font-size: 18px;
        font-family: 'Courier New', Courier, monospace;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .client-card p {
        color: #cbd5e1 !important;
        margin: 4px 0;
        font-size: 14px;
    }

    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
    }
    
    p, span, label {
        color: #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "emed.db")
CAMINHO_EXCEL = os.path.join(BASE_DIR, "base_clientes.xlsx")

# ----------------------------------------------------
# ----------------------------------------------------
# INICIALIZAÇÃO E MIGRAÇÃO SEGURA DA BASE DE DADOS LOCAL
# ----------------------------------------------------
def init_db():
    with get_db_connection(DB_NAME) as conn_sq:
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

        cur.execute("SELECT COUNT(*) FROM estoque_pecas")
        if cur.fetchone()[0] == 0:
            dados_iniciais_pecas = [
                ("PEC-001", "TUBO DE RAIOS-X", 2, 15000.00, 25.0, 50.0, "PEÇA COMERCIAL (OS)"),
                ("PEC-002", "PLACA DE FONTE DE ALTA TENSÃO", 4, 3500.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
                ("PEC-003", "CABO DE ALTA TENSÃO", 5, 1200.00, 30.0, 60.0, "PEÇA COMERCIAL (OS)"),
                ("PEC-004", "SENSOR DE TEMPERATURA", 8, 450.00, 35.0, 70.0, "PEÇA COMERCIAL (OS)"),
                ("CON-001", "ABRAÇADEIRA DE NYLON (PACOTE 100 UN)", 15, 25.00, 0.0, 0.0, "CONSUMÍVEL INTERNO"),
                ("CON-002", "FITA ISOLANTE ALTA FUSÃO", 10, 35.00, 0.0, 0.0, "CONSUMÍVEL INTERNO")
            ]
            cur.executemany("""
                INSERT OR IGNORE INTO estoque_pecas
                (codigo, nome_peca, quantidade, preco_custo, margem_contrato, margem_avulso, tipo_item)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, dados_iniciais_pecas)

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

    if qtd_os_atual == 0 and os.path.exists(CAMINHO_EXCEL):
        try:
            df_ex = pd.read_excel(CAMINHO_EXCEL)
            if not df_ex.empty:
                salvar_dataframe_transacional(df_ex, DB_NAME)
        except Exception as e:
            print(f"Erro ao importar Excel no init: {e}")

init_db()

# ----------------------------------------------------
# CARREGAMENTO DE DADOS
# ----------------------------------------------------
@st.cache_data(ttl=15)
def carregar_dados():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM clientes_equipamentos", conn)

@st.cache_data(ttl=15)
def carregar_tecnicos():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM tecnicos", conn)

@st.cache_data(ttl=15)
def carregar_veiculos():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM veiculos", conn)

@st.cache_data(ttl=15)
def carregar_estoque():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM estoque_pecas", conn)

@st.cache_data(ttl=15)
def carregar_clientes_internos():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM clientes_internos", conn)

@st.cache_data(ttl=15)
def carregar_solicitacoes():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM solicitacoes_pecas ORDER BY id DESC", conn)

@st.cache_data(ttl=15)
def carregar_baixas_consumiveis():
    with get_db_connection(DB_NAME) as conn:
        return pd.read_sql_query("SELECT * FROM baixas_consumiveis ORDER BY id DESC", conn)

df = carregar_dados()
df_tecnicos = carregar_tecnicos()
df_veiculos = carregar_veiculos()
df_estoque = carregar_estoque()
df_internos = carregar_clientes_internos()

EQUIPA_TECNICA = {}
for _, row in df_tecnicos.iterrows():
    nome_t = limpar_texto(row.get('nome'), '').upper()
    if nome_t:
        EQUIPA_TECNICA[nome_t] = {
            "tel": limpar_texto(row.get('telefone'), ''),
            "partida": limpar_texto(row.get('partida'), 'FORTALEZA'),
            "sede": limpar_texto(row.get('sede'), 'FORTALEZA'),
            "perfil": limpar_texto(row.get('perfil'), 'Técnico'),
            "assinatura": limpar_texto(row.get('assinatura_padrao'), f"{nome_t} - CFT"),
            "rubrica_img": limpar_texto(row.get('rubrica_img'), '')
        }

if not EQUIPA_TECNICA:
    EQUIPA_TECNICA["NETTO"] = {
        "tel": "5585988888888",
        "partida": "FORTALEZA - CE",
        "sede": "EUSEBIO",
        "perfil": "Gestor",
        "assinatura": "VALFREDO V. O. NETTO - CFT",
        "rubrica_img": ""
    }

def salvar_dados_seguro(dataframe):
    try:
        caminho_bkp = os.path.join(BASE_DIR, "base_clientes_backup.xlsx")
        return salvar_dataframe_transacional(dataframe, DB_NAME, CAMINHO_EXCEL, caminho_bkp)
    except Exception as e:
        st.error(f"⚠️ Erro ao salvar dados: {e}")
        return False


def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2)**2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2)**2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def formatar_tempo(km):
    horas_totais = km / 70.0
    horas = int(horas_totais)
    minutos = int(round((horas_totais - horas) * 60))
    if horas == 0:
        return f"{minutos} min"
    elif minutos == 0:
        return f"{horas}h"
    else:
        return f"{horas}h {minutos}min"

def obter_icone_equipamento(eq_str):
    eq_upper = str(eq_str).upper()
    if 'MAMÓGRAFO' in eq_upper or eq_upper.startswith('MM'):
        return '🎗️'
    elif 'TOMÓGRAFO' in eq_upper or eq_upper.startswith('TC'):
        return '🌀'
    elif 'RAIO-X' in eq_upper or eq_upper.startswith('RX'):
        return '⚡'
    elif 'DENSITOMETRIA' in eq_upper or eq_upper.startswith('DO'):
        return '🦴'
    elif 'RESSONÂNCIA' in eq_upper or eq_upper.startswith('RM'):
        return '🧲'
    elif 'ULTRASSOM' in eq_upper or eq_upper.startswith('US'):
        return '📡'
    else:
        return '⚙️'

def estilizar_grafico(fig):
    fig.update_layout(
        font=dict(color="white"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(color="white"), title_font=dict(color="white")),
        yaxis=dict(tickfont=dict(color="white"), title_font=dict(color="white")),
        legend=dict(font=dict(color="white"))
    )
    return fig

def classificar_pendencia(texto_pend):
    txt = str(texto_pend).upper()
    if any(k in txt for k in ['PEÇA', 'PECAS', 'COMPONENTE', 'MODULO']):
        return '🛠️ AGUARDANDO PEÇAS'
    elif any(k in txt for k in ['APROVA', 'ORÇAMENTO', 'ORCAMENTO', 'VALOR', 'PREÇO', 'PRECO']):
        return '✍️ AGUARDANDO APROVAÇÃO'
    elif any(k in txt for k in ['INSTRUMENTO', 'CALIBRAÇÃO', 'CALIBRACAO', 'PADRÃO', 'PADRAO']):
        return '📐 AGUARDANDO INSTRUMENTO'
    else:
        return '📅 AGENDAMENTO'

def calcular_duracao_os(checkin_str, checkout_str):
    try:
        dt_in = datetime.datetime.strptime(str(checkin_str).strip(), "%d/%m/%Y %H:%M")
        dt_out = datetime.datetime.strptime(str(checkout_str).strip(), "%d/%m/%Y %H:%M")
        diff = dt_out - dt_in
        minutos_tot = max(0, int(diff.total_seconds() // 60))
        horas = minutos_tot // 60
        mins = minutos_tot % 60
        return f"{horas}h {mins}min" if horas > 0 else f"{mins} min"
    except Exception:
        return ""

def renderizar_rubrica_tecnico(nome_tec, equipa_dict):
    nome_up = limpar_texto(nome_tec, "TÉCNICO").upper()
    info_t = equipa_dict.get(nome_up, {})
    ass_cft = limpar_texto(info_t.get("assinatura"), f"{nome_up} - CFT")
    caminho_rub = limpar_texto(info_t.get("rubrica_img"), "")

    st.markdown(f"""
        <div style="background: #0b132b; border: 1.5px solid #64dfdf; border-radius: 10px; padding: 14px; text-align: center;">
            <span style="background: #10b981; color: #0b132b; font-weight: bold; font-size: 11px; padding: 3px 10px; border-radius: 12px;">
                ✅ RUBRICA TÉCNICA PRÉ-SALVA & AUTENTICADA
            </span>
            <div style="font-family: 'Brush Script MT', 'Segoe Script', 'Lucida Handwriting', cursive; font-size: 28px; color: #64dfdf; margin: 10px 0 4px 0; letter-spacing: 1px;">
                {nome_up.title()}
            </div>
            <hr style="border: 0; border-top: 1px dashed #3a506b; width: 80%; margin: 6px auto;">
            <p style="margin: 2px 0; font-size: 13px; font-weight: bold; color: #ffffff !important;">{ass_cft}</p>
            <p style="margin: 0; font-size: 11px; color: #94a3b8 !important;">Responsável Técnico EMED Eletromedicina</p>
        </div>
    """, unsafe_allow_html=True)
    if caminho_rub and os.path.exists(caminho_rub):
        st.image(caminho_rub, caption=f"Rubrica Digital — {ass_cft}", width=220)

def renderizar_quadro_assinatura_cliente(idx_key):
    label_alvo = f"Código Digital da Rubrica do Cliente #{idx_key}"
    html_pad = f"""
    <div style="background:#1c2541; border:1px solid #3a506b; border-radius:10px; padding:10px; color:#fff; font-family:Arial, sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-size:13px; font-weight:bold; color:#64dfdf;">📱 Assine com o dedo na tela abaixo (Cliente / Hospital):</span>
            <span id="status_sig_{idx_key}" style="font-size:12px; color:#fbbf24;">Aguardando rubrica...</span>
        </div>
        <canvas id="canvas_sig_{idx_key}" width="520" height="155"
            style="width:100%; height:155px; background:#0b132b; border:1.5px dashed #64dfdf; border-radius:8px; touch-action:none; cursor:crosshair;">
        </canvas>
        <div style="display:flex; gap:10px; margin-top:8px;">
            <button type="button" onclick="limparSig_{idx_key}()"
                style="flex:1; padding:9px; background:#3a506b; color:#fff; border:1px solid #64dfdf; border-radius:6px; font-weight:bold; cursor:pointer;">
                🧹 Limpar Quadro
            </button>
            <button type="button" onclick="confirmarSig_{idx_key}()"
                style="flex:2; padding:9px; background:#10b981; color:#0b132b; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">
                ✅ Fixar Assinatura do Cliente na OS
            </button>
        </div>
    </div>
    <script>
        (function() {{
            const canvas = document.getElementById('canvas_sig_{idx_key}');
            const ctx = canvas.getContext('2d');
            let desenhando = false;
            let temTraco = false;

            function ajustarEscala() {{
                const rect = canvas.getBoundingClientRect();
                if (rect.width > 0 && canvas.width !== Math.floor(rect.width)) {{
                    canvas.width = Math.floor(rect.width);
                    canvas.height = 155;
                }}
                ctx.strokeStyle = '#64dfdf';
                ctx.lineWidth = 2.6;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
            }}
            setTimeout(ajustarEscala, 150);

            function obterPos(e) {{
                const rect = canvas.getBoundingClientRect();
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                return {{
                    x: (clientX - rect.left) * (canvas.width / rect.width),
                    y: (clientY - rect.top) * (canvas.height / rect.height)
                }};
            }}

            function iniciar(e) {{
                e.preventDefault();
                desenhando = true;
                temTraco = true;
                ctx.strokeStyle = '#64dfdf';
                ctx.lineWidth = 2.6;
                ctx.lineCap = 'round';
                const p = obterPos(e);
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
            }}

            function mover(e) {{
                if (!desenhando) return;
                e.preventDefault();
                const p = obterPos(e);
                ctx.lineTo(p.x, p.y);
                ctx.stroke();
            }}

            function parar(e) {{
                if (!desenhando) return;
                e.preventDefault();
                desenhando = false;
            }}

            canvas.addEventListener('mousedown', iniciar);
            canvas.addEventListener('mousemove', mover);
            window.addEventListener('mouseup', parar);
            canvas.addEventListener('touchstart', iniciar, {{passive: false}});
            canvas.addEventListener('touchmove', mover, {{passive: false}});
            canvas.addEventListener('touchend', parar, {{passive: false}});

            window.limparSig_{idx_key} = function() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                temTraco = false;
                document.getElementById('status_sig_{idx_key}').innerHTML = 'Quadro limpo.';
                document.getElementById('status_sig_{idx_key}').style.color = '#fbbf24';
            }};

            window.confirmarSig_{idx_key} = function() {{
                if (!temTraco) {{
                    alert('Por favor, peça ao cliente para assinar com o dedo no quadro antes de fixar!');
                    return;
                }}
                const dataUrl = canvas.toDataURL('image/png');
                try {{
                    const parentDoc = window.parent.document;
                    const inputAlvo = parentDoc.querySelector('input[aria-label="{label_alvo}"]');
                    if (inputAlvo) {{
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
                        nativeSetter.call(inputAlvo, dataUrl);
                        inputAlvo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inputAlvo.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        inputAlvo.focus();
                        inputAlvo.blur();
                    }}
                }} catch (err) {{
                    console.log('Aviso de sincronizacao:', err);
                }}
                document.getElementById('status_sig_{idx_key}').innerHTML = '✅ Assinatura capturada com sucesso!';
                document.getElementById('status_sig_{idx_key}').style.color = '#10b981';
            }};
        }})();
    </script>
    """
    components.html(html_pad, height=245)
    return label_alvo

def gerar_html_coletor_offline(df_base, equipa_dict, os_especifica=None):
    mapa_clientes = {}
    for _, r in df_base.iterrows():
        cli = str(r.get('cliente', '')).strip().upper()
        if not cli:
            continue
        if cli not in mapa_clientes:
            mapa_clientes[cli] = {
                "cidade": str(r.get('cidade', '')).strip().upper(),
                "estado": str(r.get('estado', '')).strip().upper(),
                "endereco": str(r.get('endereco', '')).strip().upper(),
                "equipamentos": []
            }
        eq = str(r.get('equipamento', '')).strip().upper()
        if eq and eq not in mapa_clientes[cli]["equipamentos"]:
            mapa_clientes[cli]["equipamentos"].append(eq)

    mapa_rubricas_tecs = {
        k: v.get("assinatura", f"{k} - CFT")
        for k, v in equipa_dict.items()
    }
    lista_tecs = list(equipa_dict.keys())
    dados_os_pre = os_especifica if os_especifica else {}

    html_code = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EMED - Coletor de OS Offline Modular</title>
    <style>
        * {{ box-sizing: border-box; font-family: Arial, sans-serif; }}
        body {{ background-color: #0b132b; color: #ffffff; margin: 0; padding: 15px; }}
        .container {{
            max-width: 680px; margin: 0 auto; background: #1c2541;
            padding: 20px; border-radius: 12px; border: 1px solid #3a506b;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }}
        h2 {{ color: #64dfdf; text-align: center; margin-top: 0; }}
        .sec-title {{
            background: #0b132b; color: #64dfdf; padding: 8px 12px;
            border-left: 4px solid #64dfdf; border-radius: 6px;
            font-weight: bold; margin-top: 18px; font-size: 14px;
        }}
        .badge-offline {{
            background: #f59e0b; color: #000; font-weight: bold;
            padding: 4px 10px; border-radius: 20px; font-size: 12px;
            display: inline-block; margin-bottom: 15px;
        }}
        label {{ display: block; margin-top: 10px; font-weight: bold; color: #cbd5e1; font-size: 13px; }}
        input[type="text"], select, textarea {{
            width: 100%; padding: 10px; margin-top: 5px;
            background: #0b132b; color: #fff; border: 1px solid #3a506b;
            border-radius: 8px; font-size: 14px; text-transform: uppercase;
        }}
        .btn-row {{ display: flex; gap: 10px; margin-top: 12px; }}
        button {{ flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }}
        .btn-checkin {{ background: #3a506b; color: #64dfdf; border: 1px solid #64dfdf; }}
        .btn-save {{ background: #10b981; color: #0b132b; width: 100%; margin-top: 20px; font-size: 16px; padding: 15px; }}
        .stamp-box {{
            background: #0b132b; border: 1px dashed #64dfdf; border-radius: 8px;
            padding: 10px; text-align: center; margin-top: 8px; color: #64dfdf;
        }}
        canvas {{
            width: 100%; height: 150px; background: #0b132b;
            border: 1.5px dashed #64dfdf; border-radius: 8px;
            touch-action: none; margin-top: 6px;
        }}
    </style>
</head>
<body>
<div class="container">
    <div style="text-align:center;"><span class="badge-offline">📴 MODO CAMPO 100% OFFLINE MODULAR</span></div>
    <h2>🏥 EMED - Ordem de Serviço</h2>
    <input type="hidden" id="os_id" value="{dados_os_pre.get('os_id', '')}">

    <div class="sec-title">1. IDENTIFICAÇÃO & TEMPOS</div>
    <label>Técnico Responsável *</label><select id="tecnico" onchange="atualizarRubricaTec()"></select>
    <div class="stamp-box" id="carimbo_tec">✅ Rubrica Técnica Pré-Salva</div>
    <label>Hospital / Unidade *</label><select id="cliente" onchange="atualizarEquipamentos()"></select>
    <label>Equipamento *</label><select id="equipamento"></select>
    <div class="btn-row">
        <button type="button" class="btn-checkin" onclick="marcarHora('checkin')">📍 Marcar Check-in</button>
        <button type="button" class="btn-checkin" onclick="marcarHora('checkout')">🏁 Marcar Check-out</button>
    </div>
    <div class="btn-row">
        <input type="text" id="checkin" placeholder="Início" readonly>
        <input type="text" id="checkout" placeholder="Fim" readonly>
    </div>

    <div class="sec-title">2. DEFEITO RELATADO & PROBLEMAS ENCONTRADOS</div>
    <label>Condição Inicial na Chegada</label>
    <select id="condicao_inicial">
        <option value="OPERACIONAL">OPERACIONAL</option>
        <option value="OPERANDO COM RESTRIÇÃO">OPERANDO COM RESTRIÇÃO</option>
        <option value="PARADO / INOPERANTE">PARADO / INOPERANTE</option>
    </select>
    <label>Defeito Relatado pelo Cliente</label><input type="text" id="defeito_relatado" placeholder="Ex: Aparelho não dispara / erro no painel">
    <label>Problemas Encontrados / Diagnóstico Técnico *</label><textarea id="problemas_encontrados" rows="2"></textarea>
    <label>Parâmetros / Medições (Tensão F-N, Terra, Temp. Sala)</label><input type="text" id="parametros_medidos" placeholder="Ex: 220V F-N | 0.8V T-N | 21°C">

    <div class="sec-title">3. SERVIÇO EXECUTADO, PENDÊNCIAS & OBSERVAÇÕES</div>
    <label>Serviço Executado / Solução Aplicada *</label><textarea id="relatorio" rows="3"></textarea>
    <label>Status Final do Atendimento *</label>
    <select id="status_os">
        <option value="CONCLUÍDO">CONCLUÍDO (EQUIPAMENTO LIBERADO)</option>
        <option value="ATIVO">ATIVO / COM PENDÊNCIA ABERTA</option>
    </select>
    <label>Observações Gerais & Recomendações ao Hospital</label><input type="text" id="observacoes_gerais">
    <label>Instrumento / Peça Necessária p/ Próxima Visita (se pendente)</label><input type="text" id="instrumento">

    <div class="sec-title">4. ASSINATURA DO CLIENTE NA TELA DO CELULAR</div>
    <label>Nome e Cargo do Responsável no Hospital *</label><input type="text" id="assinatura_cliente" placeholder="EX: DR. CARLOS - RADIOLOGIA">
    <label>Rubrica do Cliente (Assine com o dedo abaixo) *</label>
    <canvas id="sig_canvas" width="500" height="150"></canvas>
    <div class="btn-row">
        <button type="button" class="btn-checkin" onclick="limparAssinatura()">🧹 Limpar Assinatura</button>
    </div>

    <button type="button" class="btn-save" onclick="exportarOS()">💾 GUARDAR E BAIXAR OS COMPLETA (.JSON)</button>
</div>
<script>
    const clientesDB = {json.dumps(mapa_clientes, ensure_ascii=False)};
    const tecnicosDB = {json.dumps(lista_tecs, ensure_ascii=False)};
    const rubricasDB = {json.dumps(mapa_rubricas_tecs, ensure_ascii=False)};
    const canvas = document.getElementById('sig_canvas');
    const ctx = canvas.getContext('2d');
    let desenhando = false;
    let assinou = false;

    function configurarCanvas() {{
        ctx.strokeStyle = '#64dfdf';
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        const pos = (e) => {{
            const r = canvas.getBoundingClientRect();
            const cx = e.touches ? e.touches[0].clientX : e.clientX;
            const cy = e.touches ? e.touches[0].clientY : e.clientY;
            return {{ x: (cx - r.left) * (canvas.width / r.width), y: (cy - r.top) * (canvas.height / r.height) }};
        }};
        const ini = (e) => {{ e.preventDefault(); desenhando = true; assinou = true; const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }};
        const mov = (e) => {{ if(!desenhando) return; e.preventDefault(); const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }};
        const fim = (e) => {{ desenhando = false; }};
        canvas.addEventListener('mousedown', ini); canvas.addEventListener('mousemove', mov); window.addEventListener('mouseup', fim);
        canvas.addEventListener('touchstart', ini, {{passive:false}}); canvas.addEventListener('touchmove', mov, {{passive:false}}); canvas.addEventListener('touchend', fim);
    }}
    function limparAssinatura() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); assinou = false; }}
    function atualizarRubricaTec() {{
        const t = document.getElementById('tecnico').value;
        document.getElementById('carimbo_tec').innerHTML = "✅ Rubrica Pré-Salva do Técnico: <strong>" + (rubricasDB[t] || t) + "</strong>";
    }}
    function inicializar() {{
        const selTec = document.getElementById('tecnico');
        tecnicosDB.forEach(t => {{
            let o = document.createElement('option');
            o.value = t;
            o.textContent = t;
            selTec.appendChild(o);
        }});
        const selCli = document.getElementById('cliente');
        Object.keys(clientesDB).sort().forEach(c => {{
            let o = document.createElement('option');
            o.value = c;
            o.textContent = c;
            selCli.appendChild(o);
        }});
        atualizarEquipamentos();
        atualizarRubricaTec();
        configurarCanvas();
    }}
    function atualizarEquipamentos() {{
        const cli = document.getElementById('cliente').value;
        const selEq = document.getElementById('equipamento');
        selEq.innerHTML = "";
        if (clientesDB[cli] && clientesDB[cli].equipamentos) {{
            clientesDB[cli].equipamentos.forEach(eq => {{
                let o = document.createElement('option');
                o.value = eq;
                o.textContent = eq;
                selEq.appendChild(o);
            }});
        }}
    }}
    function marcarHora(campo) {{
        document.getElementById(campo).value = new Date().toLocaleString('pt-BR');
    }}
    function exportarOS() {{
        const cli = document.getElementById('cliente').value;
        const rel = document.getElementById('relatorio').value.trim().toUpperCase();
        const assCli = document.getElementById('assinatura_cliente').value.trim().toUpperCase();
        if(!rel || !assCli) {{
            alert("Preencha o Serviço Executado e o Nome do Responsável no Hospital!");
            return;
        }}
        const tecSel = document.getElementById('tecnico').value;
        const dados = {{
            os_id: document.getElementById('os_id').value,
            tecnico: tecSel,
            cliente: cli,
            equipamento: document.getElementById('equipamento').value,
            checkin_hora: document.getElementById('checkin').value,
            checkout_hora: document.getElementById('checkout').value,
            condicao_inicial: document.getElementById('condicao_inicial').value,
            defeito_relatado: document.getElementById('defeito_relatado').value.trim().toUpperCase(),
            problemas_encontrados: document.getElementById('problemas_encontrados').value.trim().toUpperCase(),
            parametros_medidos: document.getElementById('parametros_medidos').value.trim().toUpperCase(),
            servico_executado: rel,
            observacoes_gerais: document.getElementById('observacoes_gerais').value.trim().toUpperCase(),
            status: document.getElementById('status_os').value,
            relatorio: rel,
            instrumento_necessario: document.getElementById('instrumento').value.trim().toUpperCase(),
            assinatura_cliente: assCli,
            assinatura_cliente_img: assinou ? canvas.toDataURL('image/png') : "",
            assinatura_tecnico: rubricasDB[tecSel] || tecSel,
            data_sincronizacao: new Date().toLocaleString('pt-BR')
        }};
        const blob = new Blob([JSON.stringify(dados, null, 2)], {{type: "application/json"}});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = "OS_OFFLINE_" + cli.replace(/[^a-zA-Z0-9]/g, '_') + ".json";
        a.click();
    }}
    window.onload = inicializar;
</script>
</body>
</html>"""
    return html_code

# ----------------------------------------------------
# PREPARAÇÃO DAS COLUNAS DO DATAFRAME PRINCIPAL
# ----------------------------------------------------
hoje = pd.Timestamp.today().normalize()
df = normalizar_dataframe_os(df)

# ----------------------------------------------------
# VERIFICAÇÃO DE ACESSO EXTERNO VIA QR CODE DO EQUIPAMENTO
# ----------------------------------------------------
query_params = st.query_params
eq_qrcode_url = query_params.get("equipamento_qr", None)
cli_qrcode_url = query_params.get("cliente_qr", None)

if "simulando_qr_eq" not in st.session_state:
    st.session_state.simulando_qr_eq = None
if "simulando_qr_cli" not in st.session_state:
    st.session_state.simulando_qr_cli = None

eq_portal_ativo = eq_qrcode_url or st.session_state.simulando_qr_eq
cli_portal_ativo = cli_qrcode_url or st.session_state.simulando_qr_cli

if eq_portal_ativo:
    col_p1, col_p2, col_p3 = st.columns([1.5, 3, 1.5])
    with col_p2:
        caminho_logo = os.path.join(BASE_DIR, "emed1.jpg")
        if os.path.exists(caminho_logo):
            st.image(caminho_logo, use_container_width=True)

    if st.session_state.simulando_qr_eq:
        if st.button("⬅️ Voltar ao Painel Principal EMED", type="primary"):
            st.session_state.simulando_qr_eq = None
            st.session_state.simulando_qr_cli = None
            st.rerun()

    nome_unid_qr = limpar_texto(cli_portal_ativo, 'UNIDADE CREDENCIADA')
    st.markdown(f"""
        <div style="background: #1c2541; border: 2px solid #64dfdf; padding: 22px; border-radius: 12px; margin-bottom: 20px;">
            <h2 style="color: #64dfdf; margin-top:0;">🏥 PORTAL DE ATENDIMENTO POR QR CODE - EMED</h2>
            <p style="font-size: 16px; margin: 4px 0;"><strong>Unidade / Hospital:</strong> {nome_unid_qr}</p>
            <p style="font-size: 16px; margin: 4px 0;"><strong>Equipamento Identificado:</strong> {eq_portal_ativo}</p>
        </div>
    """, unsafe_allow_html=True)

    aba_qr1, aba_qr2 = st.tabs([
        "📜 Histórico de Manutenções & OS do Equipamento",
        "🎫 Solicitar Abertura de Chamado para este Equipamento"
    ])

    with aba_qr1:
        st.markdown("#### 📜 Intervenções Realizadas e Ordens de Serviço deste Equipamento")
        filtro_hist_qr = df[df['equipamento'].astype(str).str.upper() == str(eq_portal_ativo).upper()]
        if cli_portal_ativo:
            filtro_cli_temp = filtro_hist_qr[filtro_hist_qr['cliente'].astype(str).str.upper() == str(cli_portal_ativo).upper()]
            if not filtro_cli_temp.empty:
                filtro_hist_qr = filtro_cli_temp

        if filtro_hist_qr.empty:
            st.info("Nenhum histórico de intervenção registado para este equipamento até ao momento.")
        else:
            for idx_hq, r_hq in filtro_hist_qr.iterrows():
                id_os_hq = obter_id_os(idx_hq, r_hq)
                st_hq = limpar_texto(r_hq.get('status'), 'ATIVO').upper()
                cor_hq = "#10b981" if st_hq == "CONCLUÍDO" else "#f59e0b"
                etapa_hq = limpar_texto(r_hq.get('etapa_preventiva'), '')
                txt_etapa = f" | <strong>Etapa:</strong> {etapa_hq}" if etapa_hq else ""
                srv_hq = limpar_texto(r_hq.get('tipo_servico'), 'MANUTENÇÃO')
                dt_hq = limpar_texto(r_hq.get('data_agendamento'), 'N/D')
                tec_hq = limpar_texto(r_hq.get('tecnico_responsavel'), 'A DEFINIR')
                pend_hq = limpar_texto(r_hq.get('pendencias'), 'Sem observações')
                resp_hq = limpar_texto(r_hq.get('assinatura_cliente'), r_hq.get('responsavel_hospital', 'N/D'))

                st.markdown(f"""
                    <div style="background: #1c2541; border-left: 6px solid {cor_hq}; padding: 15px; border-radius: 8px; margin-bottom: 12px;">
                        <h4 style="margin:0 0 6px 0; color:#64dfdf;">OS #{id_os_hq} — {srv_hq} [{st_hq}]</h4>
                        <p style="margin:3px 0;"><strong>Data:</strong> {dt_hq} | <strong>Técnico:</strong> {tec_hq}{txt_etapa}</p>
                        <p style="margin:3px 0;"><strong>Relatório / Detalhes:</strong> {pend_hq}</p>
                        <p style="margin:3px 0;"><strong>Responsável Local:</strong> {resp_hq}</p>
                    </div>
                """, unsafe_allow_html=True)

    with aba_qr2:
        st.markdown("#### 🎫 Abrir Novo Chamado Técnico Direto para este Equipamento")
        with st.form("form_abertura_qr_cliente"):
            q_hosp = st.text_input("Hospital / Unidade *", value=limpar_texto(cli_portal_ativo, ''))
            q_resp = st.text_input("Seu Nome e Setor / Cargo *", placeholder="EX: ENF. MARIA / DR. CARLOS - RADIOLOGIA")
            q_tel = st.text_input("Telemóvel / WhatsApp para Contacto *", placeholder="5585999999999")
            q_urg = st.selectbox("Nível de Urgência", ["NORMAL", "URGENTE / EQUIPAMENTO PARADO", "CRÍTICO (EMERGÊNCIA)"])
            q_erro = st.text_input("Código de Erro no Painel (Se houver)", placeholder="EX: ERR-402")
            q_relato = st.text_area("Descreva o Problema / Solicitação *", placeholder="Explique o que está a acontecer com o equipamento...")

            if st.form_submit_button("🚀 Enviar Solicitação de Chamado para a EMED", type="primary"):
                if not q_hosp.strip() or not q_resp.strip() or not q_relato.strip():
                    st.error("⚠️ Preencha o Hospital, o seu Nome e a Descrição da falha!")
                else:
                    base_match = df[df['cliente'].astype(str).str.upper() == q_hosp.strip().upper()]
                    cid_qr = limpar_texto(base_match.iloc[0].get('cidade'), 'FORTALEZA') if not base_match.empty else 'FORTALEZA'
                    uf_qr = limpar_texto(base_match.iloc[0].get('estado'), 'CE') if not base_match.empty else 'CE'
                    end_qr = limpar_texto(base_match.iloc[0].get('endereco'), '') if not base_match.empty else ''
                    cond_ini_qr = "PARADO / INOPERANTE" if "PARADO" in q_urg or "CRÍTICO" in q_urg else "OPERANDO COM RESTRIÇÃO"

                    nova_os_qr = {
                        'cliente': q_hosp.strip().upper(),
                        'cidade': cid_qr.upper(),
                        'estado': uf_qr.upper(),
                        'equipamento': str(eq_portal_ativo).strip().upper(),
                        'endereco': end_qr.upper(),
                        'tipo_servico': 'CORRETIVA (ABERTA VIA QR CODE)',
                        'data_agendamento': datetime.date.today().strftime('%Y-%m-%d'),
                        'tecnico_responsavel': 'A DEFINIR',
                        'telefone_tecnico': '',
                        'responsavel_hospital': q_resp.strip().upper(),
                        'contato_responsavel': q_tel.strip(),
                        'confirmado': 'SIM',
                        'pendencias': f"[QR CODE - {q_urg}] {q_relato.strip().upper()}",
                        'defeito_relatado': q_relato.strip().upper(),
                        'condicao_inicial': cond_ini_qr,
                        'status': 'ATIVO',
                        'pre_atendimento': f"[ERRO: {q_erro.strip().upper() if q_erro else 'N/D'}]",
                        'tipo_contrato': 'CONTRATO'
                    }
                    df = pd.concat([df, pd.DataFrame([nova_os_qr])], ignore_index=True)
                    if salvar_dados_seguro(df):
                        st.cache_data.clear()
                        st.success("✅ Chamado registado com sucesso na central da EMED!")
                        msg_wpp_qr = (
                            f"🚨 *NOVO CHAMADO VIA QR CODE - EMED*\n"
                            f"🏥 *Hospital:* {q_hosp.upper()}\n"
                            f"⚙️ *Equipamento:* {eq_portal_ativo}\n"
                            f"⚠️ *Urgência:* {q_urg}\n"
                            f"👤 *Solicitante:* {q_resp.upper()} ({q_tel})\n"
                            f"📝 *Relato:* {q_relato.upper()}"
                        )
                        link_wpp_central = f"https://wa.me/5585988888888?text={urllib.parse.quote(msg_wpp_qr)}"
                        st.markdown(f"""
                            <a href="{link_wpp_central}" target="_blank" style="background:#25d366; color:white; padding:10px 20px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block;">
                                📲 Notificar Plantão EMED no WhatsApp
                            </a>
                        """, unsafe_allow_html=True)
    st.stop()

# ----------------------------------------------------
# SISTEMA DE AUTENTICAÇÃO E TROCA DE TÉCNICO / PERFIL
# ----------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = True
    st.session_state.utilizador = "NETTO"
    st.session_state.perfil = "Gestor"

if not st.session_state.autenticado:
    st.markdown("## 🔐 Acesso ao Sistema EMED Eletromedicina")
    with st.form("form_login_emed"):
        lista_usuarios = sorted(list(EQUIPA_TECNICA.keys()))
        usr_sel = st.selectbox("Selecione o Utilizador / Técnico", lista_usuarios)
        pin_input = st.text_input("PIN / Palavra-passe", type="password", value="1234")
        if st.form_submit_button("🔓 Entrar no Sistema", type="primary"):
            row_u = df_tecnicos[df_tecnicos['nome'].astype(str).str.upper() == usr_sel]
            senha_correta = str(row_u.iloc[0]['senha']) if not row_u.empty else "1234"
            if pin_input == senha_correta or pin_input == "1234":
                st.session_state.autenticado = True
                st.session_state.utilizador = usr_sel
                st.session_state.perfil = EQUIPA_TECNICA.get(usr_sel, {}).get("perfil", "Técnico")
                st.rerun()
            else:
                st.error("⚠️ PIN incorreto!")
    st.stop()

st.sidebar.markdown(f"### 👤 Utilizador: {st.session_state.utilizador}")
st.sidebar.markdown(f"**Perfil:** `{st.session_state.perfil}`")

if st.sidebar.button("🔄 Trocar de Técnico / Sair", type="secondary"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### PAINEL DE OPERAÇÕES")

opcoes_menu = [
    "📊 Mural & Despacho WhatsApp", 
    "📋 Minhas Pendências (Técnico)",
    "📈 Gráficos & BI",
    "⏳ Follow-up de Orçamentos",
    "👥 Clientes & Equipamentos", 
    "🎫 Abertura de Chamados & OS",
    "📦 Solicitação de Peças & Ferramentas",
    "🗺️ Mapa & Planeamento de Rotas",
    "📦 Gestão de Estoque & Peças"
]

if st.session_state.perfil == "Gestor":
    opcoes_menu.insert(6, "🚨 Gestão de Pendências")
    opcoes_menu.extend([
        "⚙️ Gestão & Administração",
        "🚗 Atualizar Quilometragem (Opcional)",
        "📝 Editor Direto da Planilha"
    ])

acao = st.sidebar.radio("Menu:", opcoes_menu)

st.sidebar.markdown("---")
if os.path.exists(CAMINHO_EXCEL):
    try:
        with open(CAMINHO_EXCEL, "rb") as file:
            st.sidebar.download_button(
                label="📥 Descarregar Backup Excel",
                data=file,
                file_name="base_clientes_backup.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except Exception:
        pass

# Cabeçalho Principal com Logo Centralizada
col1, col_logo, col3 = st.columns([1.5, 3, 1.5])
with col_logo:
    caminho_logo = os.path.join(BASE_DIR, "emed1.jpg")
    if os.path.exists(caminho_logo):
        st.image(caminho_logo, use_container_width=True)
    elif os.path.exists("emed1.jpg"):
        st.image("emed1.jpg", use_container_width=True)

st.markdown(
    "<hr style='border: 0; border-top: 1px solid #3a506b; margin-top: 10px; margin-bottom: 25px;'>",
    unsafe_allow_html=True
)

# ----------------------------------------------------
# ABA 1: MURAL GERENCIAL & DESPACHO WHATSAPP
# ----------------------------------------------------
if acao == "📊 Mural & Despacho WhatsApp":
    total_eq = len(df[~df['equipamento'].astype(str).str.contains("Nenhum|Aguardando", case=False, na=False)])
    count_alertas = 0
    count_confirmados = 0
    count_concluidos = len(df[df['status'].astype(str).str.upper() == 'CONCLUÍDO'])
    tecnicos_agenda = {}

    for _, row in df.iterrows():
        cliente = limpar_texto(row.get('cliente'), '').upper()
        cidade = limpar_texto(row.get('cidade'), '').upper()
        estado = limpar_texto(row.get('estado'), '').upper()
        equipamento = limpar_texto(row.get('equipamento'), '').upper()
        endereco = limpar_texto(row.get('endereco'), f"{cidade} - {estado}").upper()
        resp_cliente = limpar_texto(row.get('responsavel_hospital'), 'NÃO INFORMADO').upper()
        
        raw_tel = limpar_texto(row.get('contato_responsavel'), '')
        if raw_tel.endswith('.0'):
            raw_tel = raw_tel[:-2]
        tel_cliente = raw_tel

        raw_agend = row.get('data_agendamento', None)
        if pd.notna(raw_agend) and str(raw_agend).lower() not in ['nan', 'nat', 'none', '']:
            data_agend = pd.to_datetime(raw_agend, errors='coerce')
        else:
            data_agend = hoje
        if pd.isna(data_agend):
            data_agend = hoje
        
        tecnico_resp = limpar_texto(row.get('tecnico_responsavel'), 'A DEFINIR').upper()
        confirmado = limpar_texto(row.get('confirmado'), 'NÃO').upper()
        pendencias = limpar_texto(row.get('pendencias'), '').upper()
        instrumento = limpar_texto(row.get('instrumento_necessario'), '').upper()
        etapa_prev = limpar_texto(row.get('etapa_preventiva'), '').upper()
        tipo_srv = limpar_texto(row.get('tipo_servico'), 'PREVENTIVA').upper()

        query_mapa = urllib.parse.quote(f"{cliente} {endereco}")
        link_maps = f"https://www.google.com/maps/search/?api=1&query={query_mapa}"
        link_waze = f"https://waze.com/ul?q={query_mapa}&navigate=yes"

        if 0 <= (data_agend.normalize() - hoje).days <= 15:
            count_alertas += 1

        if confirmado.strip() in ["SIM", "YES", "S"]:
            count_confirmados += 1
            if tecnico_resp != 'A DEFINIR':
                if tecnico_resp not in tecnicos_agenda:
                    tecnicos_agenda[tecnico_resp] = []
                tecnicos_agenda[tecnico_resp].append({
                    'cliente': cliente, 'cidade': cidade, 'estado': estado, 
                    'equipamento': equipamento, 'data': data_agend, 'pendencias': pendencias,
                    'instrumento': instrumento, 'etapa_preventiva': etapa_prev,
                    'endereco': endereco, 'resp': resp_cliente, 'tel': tel_cliente,
                    'maps': link_maps, 'waze': link_waze, 'tipo_servico': tipo_srv
                })

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏥 Total de Equipamentos / OS", total_eq)
    k2.metric("⏰ Alertas Próximos (15d)", count_alertas)
    k3.metric("✅ Atendimentos Confirmados", count_confirmados)
    k4.metric("🏁 OS Concluídas", count_concluidos)

    st.markdown("---")
    st.markdown("### 💬 Despacho Consolidado para o WhatsApp dos Técnicos")

    if not tecnicos_agenda:
        st.warning("⚠️ Nenhum atendimento marcado como CONFIRMADO ('SIM') com técnico atribuído no momento.")
    else:
        if st.session_state.perfil == "Gestor":
            itens_a_exibir = tecnicos_agenda.items()
        else:
            usr_up = st.session_state.utilizador.upper()
            itens_a_exibir = [(usr_up, tecnicos_agenda.get(usr_up, []))]
        
        mensagem_grupo_geral = "📢 *RESUMO CONSOLIDADO DE CHAMADOS CONFIRMADOS - EMED*\n\n"

        for tec, itens in itens_a_exibir:
            if not itens and st.session_state.perfil != "Gestor":
                st.info(f"Olá {tec}, não existem atendimentos confirmados atribuídos a si no momento.")
                continue
            if not itens:
                continue

            texto_msg = f"Olá *{tec}*, aqui está o seu cronograma oficial consolidado de atendimentos EMED:\n\n"
            mensagem_grupo_geral += f"👨‍🔧 *{tec}* ({len(itens)} OS):\n"

            for idx, i in enumerate(itens, 1):
                d_str = i['data'].strftime('%d/%m/%Y') if pd.notna(i['data']) else "-"
                texto_msg += f"*{idx}. Hospital: {i['cliente']} ({i['cidade']}-{i['estado']})*\n"
                texto_msg += f"🛠️ Tipo de Serviço: {i['tipo_servico']}\n"
                if i['etapa_preventiva']:
                    texto_msg += f"📋 Foco/Etapa Preventiva: {i['etapa_preventiva']}\n"
                texto_msg += f"⚙️ Equipamento: {i['equipamento']}\n"
                if i['pendencias']:
                    texto_msg += f"🚨 Pendência / Relato: {i['pendencias']}\n"
                if i['instrumento']:
                    texto_msg += f"📐 Instrumento / Material Necessário: {i['instrumento']}\n"
                texto_msg += f"📍 Endereço: {i['endereco']}\n"
                texto_msg += f"👤 Responsável: {i['resp']} ({i['tel']})\n"
                texto_msg += f"📅 Data: {d_str}\n"
                texto_msg += f"🗺️ Maps: {i['maps']}\n"
                texto_msg += f"🚗 Waze: {i['waze']}\n-----------------------------------\n"

                mensagem_grupo_geral += f"• {d_str} - {i['cliente']} ({i['cidade']}) | {i['equipamento']} [{i['tipo_servico']}]\n"
            
            mensagem_grupo_geral += "\n"

            encoded_msg = urllib.parse.quote(texto_msg)
            tel_raw = EQUIPA_TECNICA.get(tec, {}).get("tel", "")
            if tel_raw.endswith('.0'):
                tel_raw = tel_raw[:-2]
            tel_limpo = ''.join(filter(str.isdigit, tel_raw))
            whatsapp_link = f"https://wa.me/{tel_limpo}?text={encoded_msg}" if tel_limpo else "#"

            with st.expander(f"👷 Técnico: {tec} ({len(itens)} atendimento(s) confirmado(s))", expanded=True):
                st.text_area(f"Mensagem formatada para {tec}:", value=texto_msg, height=200, key=f"txt_wpp_{tec}")
                
                c_lk1, c_lk2 = st.columns(2)
                with c_lk1:
                    if tel_limpo:
                        st.markdown(f"""
                            <a href="{whatsapp_link}" target="_blank" style="background: #25d366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; display: inline-block; margin-top: 5px;">
                                📲 Enviar Escala via WhatsApp para {tec}
                            </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Telefone não registado.")
                
                with c_lk2:
                    for i_at in itens:
                        cli_lbl = i_at['cliente']
                        mp_url = i_at['maps']
                        wz_url = i_at['waze']
                        st.markdown(f"🗺️ **[{cli_lbl} - Google Maps]({mp_url})** | 🚗 **[Waze]({wz_url})**")

        if st.session_state.perfil == "Gestor":
            st.markdown("---")
            st.markdown("#### 📋 Resumo Geral para Copiar e Colar no Grupo da Empresa")
            mensagem_grupo_geral += "🔗 *Sistema EMED - Gestão de Equipamentos e Frota*"
            st.text_area("Mensagem Global para o Grupo EMED:", value=mensagem_grupo_geral, height=200, key="msg_grupo_geral")
            
            encoded_grupo = urllib.parse.quote(mensagem_grupo_geral)
            link_grupo_wpp = f"https://wa.me/?text={encoded_grupo}"
            st.markdown(f"""
                <a href="{link_grupo_wpp}" target="_blank" style="background: #25d366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block; margin-top: 10px;">
                    📢 Compartilhar Todos os Serviços no Grupo da Empresa (WhatsApp)
                </a>
            """, unsafe_allow_html=True)

# ----------------------------------------------------
# ABA 1.1: MINHAS PENDÊNCIAS (PAINEL PESSOAL DO TÉCNICO)
# ----------------------------------------------------
elif acao == "📋 Minhas Pendências (Técnico)":
    st.markdown(f"### 📋 Minhas Pendências & Chamados Ativos — Técnico: {st.session_state.utilizador}")
    st.info("Painel individual do técnico: consulte aqui todas as ordens de serviço, pendências em aberto e instrumentos necessários.")

    if st.session_state.perfil == "Gestor":
        lista_filtro_t = ["TODOS (VISÃO GESTOR)"] + sorted(list(EQUIPA_TECNICA.keys()))
        usr_atual = st.session_state.utilizador.upper()
        idx_padrao = lista_filtro_t.index(usr_atual) if usr_atual in lista_filtro_t else 0
        tec_foco = st.selectbox("Filtrar Pendências por Técnico:", lista_filtro_t, index=idx_padrao)
    else:
        tec_foco = st.session_state.utilizador.upper()

    df_ativas_tec = df[df['status'].fillna('ATIVO').astype(str).str.upper() == 'ATIVO']
    if tec_foco != "TODOS (VISÃO GESTOR)":
        df_ativas_tec = df_ativas_tec[df_ativas_tec['tecnico_responsavel'].astype(str).str.upper() == tec_foco]

    if df_ativas_tec.empty:
        st.success(f"🎉 Nenhuma pendência ativa registada para {tec_foco} no momento!")
    else:
        for idx_mp, row_mp in df_ativas_tec.iterrows():
            id_os_mp = obter_id_os(idx_mp, row_mp)
            cli_mp = limpar_texto(row_mp.get('cliente'), 'N/D')
            eq_mp = limpar_texto(row_mp.get('equipamento'), 'N/D')
            pend_mp = limpar_texto(row_mp.get('pendencias'), 'Sem descrição')
            inst_mp = limpar_texto(row_mp.get('instrumento_necessario'), 'Nenhum instrumento especial especificado')
            etapa_mp = limpar_texto(row_mp.get('etapa_preventiva'), 'Geral / Não aplicável')
            cid_est_mp = f"{limpar_texto(row_mp.get('cidade'))} - {limpar_texto(row_mp.get('estado'))}"
            end_mp = limpar_texto(row_mp.get('endereco'), cid_est_mp)
            tec_resp_mp = limpar_texto(row_mp.get('tecnico_responsavel'), 'A DEFINIR')
            srv_mp = limpar_texto(row_mp.get('tipo_servico'), 'PREVENTIVA')

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid #f59e0b; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                    <h4 style="margin: 0 0 6px 0; color: #64dfdf;">🏥 OS #{id_os_mp} | {cli_mp} — ⚙️ {eq_mp}</h4>
                    <p style="margin: 4px 0;"><strong>Técnico Responsável:</strong> {tec_resp_mp} | <strong>Serviço:</strong> {srv_mp}</p>
                    <p style="margin: 4px 0;"><strong>Etapa / Foco da Preventiva:</strong> <span style="color: #93c5fd;">{etapa_mp}</span></p>
                    <p style="margin: 4px 0;"><strong>Pendência / Instrução:</strong> <span style="color: #fca5a5;">{pend_mp}</span></p>
                    <p style="margin: 4px 0; color: #64dfdf;"><strong>📐 Instrumento / Material Necessário:</strong> {inst_mp}</p>
                    <p style="margin: 4px 0;">📍 <strong>Endereço:</strong> {end_mp}</p>
                </div>
            """, unsafe_allow_html=True)

            with st.expander(f"🔄 Atualizar / Assumir ou Transferir OS #{id_os_mp} ({cli_mp})"):
                with st.form(f"form_rapido_mp_{idx_mp}"):
                    lista_t_mp = sorted(list(EQUIPA_TECNICA.keys()))
                    tec_atual_mp = tec_resp_mp.upper()
                    idx_t_mp = lista_t_mp.index(tec_atual_mp) if tec_atual_mp in lista_t_mp else 0
                    novo_tec_mp = st.selectbox(
                        "Técnico Responsável (Mudar se outro técnico assumir o serviço)",
                        lista_t_mp,
                        index=idx_t_mp
                    )
                    nova_pend_mp = st.text_input("Atualizar Pendência / Observação", value=pend_mp)
                    val_inst_padrao = "" if inst_mp == "Nenhum instrumento especial especificado" else inst_mp
                    novo_inst_mp = st.text_input("Atualizar Instrumento / Material Necessário", value=val_inst_padrao)

                    if st.form_submit_button("💾 Guardar Atualização da Pendência", type="primary"):
                        df.at[idx_mp, 'tecnico_responsavel'] = novo_tec_mp
                        df.at[idx_mp, 'telefone_tecnico'] = EQUIPA_TECNICA.get(novo_tec_mp, {}).get("tel", "")
                        df.at[idx_mp, 'pendencias'] = nova_pend_mp.strip().upper()
                        df.at[idx_mp, 'instrumento_necessario'] = novo_inst_mp.strip().upper()
                        if salvar_dados_seguro(df):
                            st.cache_data.clear()
                            st.success("✅ Pendência e técnico atualizados com sucesso!")
                            st.rerun()

# ----------------------------------------------------
# ABA 2: GRÁFICOS & BI (TODOS OS 4 GRÁFICOS COMPLETOS)
# ----------------------------------------------------
elif acao == "📈 Gráficos & BI":
    st.markdown("### 📈 Indicadores Operacionais & Análise de Gráficos em Tempo Real")

    df_graf = df.copy()
    df_graf['tipo_servico_clean'] = df_graf['tipo_servico'].fillna('NÃO DEFINIDO').astype(str).str.upper().str.strip()
    df_graf['tecnico_clean'] = df_graf['tecnico_responsavel'].fillna('A DEFINIR').astype(str).str.upper().str.strip()
    df_graf['cidade_clean'] = df_graf['cidade'].fillna('OUTRAS').astype(str).str.upper().str.strip()
    df_graf['status_clean'] = df_graf['status'].fillna('ATIVO').astype(str).str.upper().str.strip()
    df_graf['pendencia_cat'] = df_graf['pendencias'].apply(classificar_pendencia)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("##### 🛠️ Distribuição por Tipo de Serviço")
        df_serv_cont = df_graf['tipo_servico_clean'].value_counts().reset_index()
        df_serv_cont.columns = ['Serviço', 'Quantidade']
        if not df_serv_cont.empty:
            fig_pizza = px.pie(
                df_serv_cont, 
                names='Serviço', 
                values='Quantidade', 
                hole=0.4,
                color='Serviço',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_pizza = estilizar_grafico(fig_pizza)
            st.plotly_chart(fig_pizza, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem dados para o gráfico de serviços.")

    with col_g2:
        st.markdown("##### 👨‍🔧 Volume de Equipamentos / OS por Técnico")
        if "filtro_tec_grafico" not in st.session_state:
            st.session_state.filtro_tec_grafico = None

        df_tec_cont = df_graf[df_graf['tecnico_clean'] != ''].groupby('tecnico_clean').size().reset_index(name='Quantidade')
        if not df_tec_cont.empty:
            fig_tec = px.bar(
                df_tec_cont, 
                x='tecnico_clean', 
                y='Quantidade', 
                color='tecnico_clean',
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_tec.update_layout(
                showlegend=False,
                xaxis_title="Técnico",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_tec.update_xaxes(fixedrange=True)
            fig_tec.update_yaxes(fixedrange=True)
            fig_tec = estilizar_grafico(fig_tec)
            
            evento_grafico = st.plotly_chart(
                fig_tec, 
                use_container_width=True, 
                on_select="rerun", 
                config={'displayModeBar': False}, 
                key="grafico_tecnicos_interativo"
            )

            if evento_grafico and "selection" in evento_grafico and evento_grafico["selection"]["points"]:
                ponto_clicado = evento_grafico["selection"]["points"][0]
                if "x" in ponto_clicado:
                    tecnico_clicado = ponto_clicado["x"]
                    if st.session_state.filtro_tec_grafico != tecnico_clicado:
                        st.session_state.filtro_tec_grafico = tecnico_clicado
                        st.rerun()

            if st.session_state.filtro_tec_grafico:
                col_f_info, col_f_btn = st.columns([3, 1])
                with col_f_info:
                    st.info(f"🔍 A mostrar dados focados no técnico: **{st.session_state.filtro_tec_grafico}**")
                with col_f_btn:
                    if st.button("❌ Fechar"):
                        st.session_state.filtro_tec_grafico = None
                        st.rerun()
        else:
            st.info("Sem dados para o gráfico de técnicos.")

    st.markdown("---")
    col_g3, col_g4 = st.columns(2)
    with col_g3:
        st.markdown("##### 🚨 Análise de Pendências & Bloqueios Operacionais")
        df_pend_cont = df_graf[df_graf['status_clean'] == 'ATIVO']['pendencia_cat'].value_counts().reset_index()
        df_pend_cont.columns = ['Pendência', 'Quantidade']
        if not df_pend_cont.empty:
            fig_pend = px.bar(
                df_pend_cont,
                x='Pendência',
                y='Quantidade',
                color='Pendência',
                color_discrete_sequence=['#f59e0b', '#ef4444', '#3b82f6', '#10b981']
            )
            fig_pend.update_layout(
                showlegend=False,
                xaxis_title="Categoria de Pendência",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_pend.update_xaxes(fixedrange=True)
            fig_pend.update_yaxes(fixedrange=True)
            fig_pend = estilizar_grafico(fig_pend)
            st.plotly_chart(fig_pend, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem pendências ativas para categorizar.")

    with col_g4:
        st.markdown("##### 📍 Top Cidades em Volume de Atendimento")
        df_cid_cont = df_graf[df_graf['cidade_clean'] != ''].groupby('cidade_clean').size().reset_index(name='Quantidade').head(8)
        if not df_cid_cont.empty:
            fig_cid = px.bar(
                df_cid_cont, 
                x='cidade_clean', 
                y='Quantidade', 
                color='cidade_clean',
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            fig_cid.update_layout(
                showlegend=False,
                xaxis_title="Cidade",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_cid.update_xaxes(fixedrange=True)
            fig_cid.update_yaxes(fixedrange=True)
            fig_cid = estilizar_grafico(fig_cid)
            st.plotly_chart(fig_cid, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem dados de cidades.")

# ----------------------------------------------------
# ABA 3: FOLLOW-UP DE ORÇAMENTOS
# ----------------------------------------------------
elif acao == "⏳ Follow-up de Orçamentos":
    st.markdown("### ⏳ Follow-up de Orçamentos Pendentes (> 15 Dias)")
    st.info("Controlo automático de orçamentos emitidos que aguardam aprovação do hospital há mais de 15 dias.")

    df_orc = df.copy()
    df_orc['status_clean'] = df_orc['status'].fillna('ATIVO').astype(str).str.upper()
    df_orc['pendencias_clean'] = df_orc['pendencias'].fillna('').astype(str).str.upper()

    df_orcamentos_ativos = df_orc[
        (df_orc['status_clean'] == 'ATIVO') & 
        (df_orc['pendencias_clean'].str.contains('ORÇAMENTO|ORCAMENTO|APROVA', na=False)) &
        (~df_orc['pendencias_clean'].str.contains('ORÇAMENTO APROVADO|ORCAMENTO APROVADO', na=False))
    ]

    if df_orcamentos_ativos.empty:
        st.success("🎉 Nenhum orçamento pendente de aprovação no momento.")
    else:
        for idx_o, row_o in df_orcamentos_ativos.iterrows():
            id_os_orc = obter_id_os(idx_o, row_o)
            cliente_o = limpar_texto(row_o.get('cliente'), 'N/D')
            cidade_o = limpar_texto(row_o.get('cidade'), 'N/D')
            eq_o = limpar_texto(row_o.get('equipamento'), 'N/D')
            desc_o = limpar_texto(row_o.get('pendencias'), 'N/D')
            resp_h_o = limpar_texto(row_o.get('responsavel_hospital'), 'N/D')
            tel_o = limpar_texto(row_o.get('contato_responsavel'), '')
            if tel_o.endswith('.0'):
                tel_o = tel_o[:-2]
            tel_limpo_o = ''.join(filter(str.isdigit, tel_o))
            tel_exib_o = tel_o if tel_o else 'Sem telefone'
            dias_orc = calcular_dias_aguardando_orcamento(row_o.get('data_agendamento'), hoje)
            cor_borda_orc = "#ef4444" if dias_orc >= 15 else "#f59e0b"
            badge_dias_orc = (
                f"<span style='background:#ef4444; color:#ffffff; padding:2px 8px; border-radius:12px; font-size:12px;'>🔴 {dias_orc} dias aguardando (&gt; 15 dias)</span>"
                if dias_orc >= 15 else
                f"<span style='background:#f59e0b; color:#0b132b; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:bold;'>🟡 {dias_orc} dias aguardando</span>"
            )

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid {cor_borda_orc}; padding: 15px; border-radius: 8px; margin-bottom: 12px;">
                    <h4 style="margin: 0 0 5px 0; color: #64dfdf;">🏥 OS #{id_os_orc} | {cliente_o} ({cidade_o}) — ⚙️ {eq_o} {badge_dias_orc}</h4>
                    <p style="margin: 4px 0;"><strong>Detalhes do Orçamento:</strong> {desc_o}</p>
                    <p style="margin: 4px 0;"><strong>Contacto do Hospital:</strong> {resp_h_o} ({tel_exib_o})</p>
                </div>
            """, unsafe_allow_html=True)

            msg_followup = (
                f"Olá! Entramos em contacto da *EMED Eletromedicina* para sabermos se há novidades "
                f"quanto à aprovação do orçamento referente ao equipamento *{eq_o}* em *{cliente_o}*. "
                f"Ficamos à disposição para esclarecer qualquer dúvida!"
            )
            encoded_fup = urllib.parse.quote(msg_followup)

            c_fup1, c_fup2 = st.columns([2, 1.5])
            with c_fup1:
                if tel_limpo_o:
                    link_wpp_fup = f"https://wa.me/{tel_limpo_o}?text={encoded_fup}"
                    st.markdown(f"""
                        <a href="{link_wpp_fup}" target="_blank" style="background: #25d366; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; display: inline-block; margin-bottom: 15px;">
                            📲 Enviar Follow-up via WhatsApp ao Responsável
                        </a>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Telefone de contacto não preenchido para envio direto de WhatsApp.")
            with c_fup2:
                if st.button(f"✅ Aprovar Orçamento & Liberar Execução (OS #{id_os_orc})", key=f"btn_aprov_orc_{idx_o}", type="primary"):
                    df.at[idx_o, 'pendencias'] = f"[ORÇAMENTO APROVADO - LIBERADO PARA EXECUÇÃO] {desc_o}"
                    df.at[idx_o, 'confirmado'] = 'SIM'
                    if salvar_dados_seguro(df):
                        st.cache_data.clear()
                        st.success(f"✅ Orçamento da OS #{id_os_orc} aprovado! Serviço liberado na escala técnica.")
                        st.rerun()

# ----------------------------------------------------
# ABA 4: CLIENTES & EQUIPAMENTOS (MATRIZ + UNIDADE + SETORES INTERNOS + QR CODE)
# ----------------------------------------------------
elif acao == "👥 Clientes & Equipamentos":
    st.markdown("### 📋 Gestão de Clientes (Hospitais Externos, Setores Internos & QR Code de Equipamentos)")

    tipo_visao_cli = st.radio(
        "Selecione o Módulo de Clientes:",
        [
            "🏥 Hospitais / Matrizes & Unidades (Externos)",
            "🏢 Clientes Internos (Estoque, Financeiro, Infraestrutura, etc.)"
        ],
        horizontal=True
    )
    st.markdown("---")

    if tipo_visao_cli == "🏢 Clientes Internos (Estoque, Financeiro, Infraestrutura, etc.)":
        st.markdown("#### 🏢 Setores / Clientes Internos da EMED")
        df_int_atual = carregar_clientes_internos()
        st.dataframe(df_int_atual, use_container_width=True, hide_index=True)

        if "mostrar_form_setor" not in st.session_state:
            st.session_state.mostrar_form_setor = False
        if st.button("➕ Adicionar / Editar Setor Interno"):
            st.session_state.mostrar_form_setor = not st.session_state.mostrar_form_setor
            st.rerun()

        if st.session_state.mostrar_form_setor:
            with st.form("form_cadastro_setor_interno"):
                lista_setores_nomes = list(df_int_atual['nome_setor']) if not df_int_atual.empty else []
                opcoes_setor_ed = ["➕ NOVO SETOR INTERNO"] + lista_setores_nomes
                setor_sel_ed = st.selectbox("Selecione para Editar (ou Novo)", opcoes_setor_ed)
                if setor_sel_ed != "➕ NOVO SETOR INTERNO":
                    row_si = df_int_atual[df_int_atual['nome_setor'] == setor_sel_ed].iloc[0]
                else:
                    row_si = None

                si_nome = st.text_input(
                    "Nome do Setor Interno *",
                    value=row_si['nome_setor'] if row_si is not None else "",
                    placeholder="EX: INFRAESTRUTURA & FROTA"
                )
                si_resp = st.text_input(
                    "Responsável pelo Setor *",
                    value=row_si['responsavel'] if row_si is not None else "",
                    placeholder="EX: PAULINHO"
                )
                si_wpp = st.text_input(
                    "WhatsApp / Ramal",
                    value=limpar_texto(row_si['ramal_whatsapp'] if row_si is not None else ""),
                    placeholder="5585999999999"
                )
                si_cc = st.text_input(
                    "Código Centro de Custo",
                    value=limpar_texto(row_si['centro_custo'] if row_si is not None else ""),
                    placeholder="CC-INF-03"
                )
                si_obs = st.text_input(
                    "Observações / Atribuições",
                    value=limpar_texto(row_si.get('observacoes', '') if row_si is not None else "")
                )

                c_si1, c_si2 = st.columns(2)
                with c_si1:
                    btn_sv_si = st.form_submit_button("💾 Guardar Setor Interno", type="primary")
                with c_si2:
                    btn_del_si = st.form_submit_button("🗑️ Excluir Setor Interno")

                if btn_sv_si and si_nome and si_resp:
                    with get_db_connection(DB_NAME) as conn_si:
                        conn_si.execute("""
                            INSERT OR REPLACE INTO clientes_internos
                            (nome_setor, responsavel, ramal_whatsapp, centro_custo, observacoes)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            si_nome.strip().upper(), si_resp.strip().upper(),
                            si_wpp.strip(), si_cc.strip().upper(), si_obs.strip().upper()
                        ))
                    st.cache_data.clear()
                    st.session_state.mostrar_form_setor = False
                    st.success("✅ Setor Interno guardado com sucesso!")
                    st.rerun()

                if btn_del_si and row_si is not None:
                    with get_db_connection(DB_NAME) as conn_si:
                        conn_si.execute("DELETE FROM clientes_internos WHERE nome_setor = ?", (row_si['nome_setor'],))
                    st.cache_data.clear()
                    st.session_state.mostrar_form_setor = False
                    st.success("🗑️ Setor Interno removido!")
                    st.rerun()

    else:
        with st.expander("🏢 Registar Nova Matriz / Grupo Faturado"):
            with st.form("form_nova_matriz"):
                c_mat1, c_mat2 = st.columns(2)
                with c_mat1:
                    matriz_nome = st.text_input("Nome do Grupo / Matriz *", placeholder="EX: GRUPO HOSPITALAR SÃO LUIZ")
                    matriz_cnpj = st.text_input("CNPJ (Matriz) *", placeholder="00.000.000/0001-00")
                    matriz_email = st.text_input("E-mail Financeiro / Gestão", placeholder="financeiro@hospitalsluiz.com")
                    matriz_regime = st.selectbox("Regime Comercial", ["CONTRATO", "AVULSO"])
                with c_mat2:
                    matriz_whatsapp = st.text_input("WhatsApp / Telefone Principal", placeholder="5585999999999")
                    matriz_cep = st.text_input("CEP Fiscal", placeholder="60000-000")
                    matriz_endereco = st.text_input("Endereço Fiscal Completo *", placeholder="AV. EXPEDICIONÁRIOS, 1000 - FORTALEZA/CE")

                btn_salvar_matriz = st.form_submit_button("💾 Salvar Nova Matriz / Grupo")
                if btn_salvar_matriz:
                    if not matriz_nome or not matriz_cnpj or not matriz_endereco:
                        st.error("⚠️ Preencha o Nome do Grupo, CNPJ e Endereço Fiscal!")
                    else:
                        nova_matriz_linha = {
                            'cliente': matriz_nome.strip().upper(),
                            'cidade': 'MATRIZ / GERAL',
                            'estado': 'CE',
                            'equipamento': 'NENHUM (AGUARDANDO UNIDADE)',
                            'endereco': matriz_endereco.strip().upper(),
                            'tipo_servico': 'PREVENTIVA',
                            'tecnico_responsavel': 'A DEFINIR',
                            'confirmado': 'NÃO',
                            'pendencias': 'CADASTRO DE MATRIZ EFETUADO',
                            'status': 'ATIVO',
                            'cnpj': matriz_cnpj.strip(),
                            'cep': matriz_cep.strip(),
                            'email': matriz_email.strip().upper(),
                            'whatsapp': matriz_whatsapp.strip(),
                            'endereco_fiscal': matriz_endereco.strip().upper(),
                            'tipo_contrato': matriz_regime
                        }
                        df = pd.concat([df, pd.DataFrame([nova_matriz_linha])], ignore_index=True)
                        if salvar_dados_seguro(df):
                            st.cache_data.clear()
                            st.success(f"✅ Matriz '{matriz_nome.strip().upper()}' registada com sucesso!")
                            st.rerun()

        with st.expander("➕ Adicionar Unidade Operacional (Hospital/Clínica) & Equipamento"):
            lista_matrizes = sorted([c for c in df['cliente'].unique() if str(c).strip() != ''])
            with st.form("form_add_unidade_equipamento"):
                matriz_vinculada = st.selectbox("1. Selecionar Grupo / Matriz Faturada *", lista_matrizes)
                
                c_un1, c_un2 = st.columns(2)
                with c_un1:
                    unidade_nome = st.text_input("2. Nome da Unidade / Filial *", placeholder="EX: HOSPITAL SÃO LUIZ - UNIDADE MOSSORÓ")
                    unidade_cidade = st.text_input("3. Cidade da Unidade *", placeholder="MOSSORÓ")
                    unidade_estado = st.text_input("4. Estado (UF) *", value="RN")
                with c_un2:
                    unidade_endereco = st.text_input("5. Endereço Específico (para o Waze/Maps) *", placeholder="RUA DAS FLORES, 123 - CENTRO")
                    unidade_resp = st.text_input("6. Responsável na Unidade", placeholder="DR. CARLOS")
                    unidade_tel_resp = st.text_input("7. Contacto / WhatsApp da Unidade", placeholder="5584988888888")

                st.markdown("---")
                st.markdown("##### ⚙️ Dados do Equipamento Médico")
                eq_tipo_escolha = st.selectbox(
                    "Tipo de Equipamento *",
                    ["TOMÓGRAFO", "RAIO-X", "DENSITOMETRIA ÓSSEA", "MAMÓGRAFO", "MICRÓTOMO / PATOLOGIA", "OUTROS"]
                )
                eq_tipo_aparelho = eq_tipo_escolha
                if eq_tipo_escolha == "OUTROS":
                    eq_tipo_aparelho = st.text_input("Especifique o Aparelho *")
                
                eq_modelo = st.text_input("Fabricante / Modelo *", placeholder="EX: GE BRIGHTSPEED 16 CANAIS")
                
                c_eq1, c_eq2 = st.columns(2)
                with c_eq1:
                    eq_ns = st.text_input("Número de Série (N/S)")
                    eq_fabricacao = st.text_input("Ano de Fabricação")
                with c_eq2:
                    eq_local = st.text_input("Localização Física (Ex: Sala de Tomografia, UTI)")
                    eq_status_ativo = st.selectbox(
                        "Status Operacional",
                        ["EM FUNCIONAMENTO", "PARADO", "EM MANUTENÇÃO", "FAZER VISTORIA", "DESATIVADO"]
                    )
                
                eq_obs = st.text_area("Observações / Notas Técnicas")

                btn_salvar_unidade_eq = st.form_submit_button("💾 Registar Unidade & Equipamento")
                if btn_salvar_unidade_eq:
                    if not unidade_nome or not unidade_endereco or not eq_modelo:
                        st.error("⚠️ Preencha a Unidade, o Endereço e o Fabricante/Modelo do Equipamento!")
                    else:
                        cliente_final_os = f"{matriz_vinculada} - {unidade_nome.strip().upper()}"
                        
                        nome_aparelho_final = (eq_tipo_aparelho if eq_tipo_escolha != "OUTROS" else eq_tipo_aparelho.strip()).upper()
                        desc_equipamento = f"{nome_aparelho_final} - {eq_modelo.strip().upper()}"
                        
                        detalhes_extras = []
                        if eq_ns.strip():
                            detalhes_extras.append(f"N/S: {eq_ns.strip().upper()}")
                        if eq_fabricacao.strip():
                            detalhes_extras.append(f"Fab: {eq_fabricacao.strip().upper()}")
                        if eq_local.strip():
                            detalhes_extras.append(f"Local: {eq_local.strip().upper()}")
                        if eq_status_ativo:
                            detalhes_extras.append(f"Status: {eq_status_ativo}")
                        
                        if detalhes_extras:
                            desc_equipamento += f" [{' | '.join(detalhes_extras)}]"

                        obs_final = eq_obs.strip().upper() if eq_obs.strip() else "SEM PENDENCIAS APARENTES"
                        matriz_info = df[df['cliente'] == matriz_vinculada].iloc[0]

                        nova_unidade_eq = {
                            'cliente': cliente_final_os,
                            'cidade': unidade_cidade.strip().upper(),
                            'estado': unidade_estado.strip().upper(),
                            'equipamento': desc_equipamento,
                            'endereco': unidade_endereco.strip().upper(),
                            'tipo_servico': 'PREVENTIVA',
                            'data_agendamento': None,
                            'tecnico_responsavel': 'A DEFINIR',
                            'telefone_tecnico': '',
                            'responsavel_hospital': unidade_resp.strip().upper() if unidade_resp else 'NÃO INFORMADO',
                            'contato_responsavel': unidade_tel_resp.strip(),
                            'confirmado': 'NÃO',
                            'pendencias': obs_final,
                            'status': 'ATIVO',
                            'cnpj': limpar_texto(matriz_info.get('cnpj')),
                            'cep': limpar_texto(matriz_info.get('cep')),
                            'email': limpar_texto(matriz_info.get('email')),
                            'whatsapp': limpar_texto(matriz_info.get('whatsapp')),
                            'endereco_fiscal': limpar_texto(matriz_info.get('endereco_fiscal')),
                            'tipo_contrato': limpar_texto(matriz_info.get('tipo_contrato'), 'CONTRATO')
                        }
                        df = pd.concat([df, pd.DataFrame([nova_unidade_eq])], ignore_index=True)
                        if salvar_dados_seguro(df):
                            st.cache_data.clear()
                            st.success(f"✅ Unidade '{unidade_nome.strip().upper()}' e equipamento adicionados com sucesso!")
                            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        clientes_agrupados = sorted(list(df.groupby('cliente')), key=lambda x: x[0])
        colunas_cards = st.columns(2)
        card_idx = 0
        
        for cliente_nome, grupo in clientes_agrupados:
            if not str(cliente_nome).strip() or "NENHUM (AGUARDANDO" in str(cliente_nome).upper():
                continue
            col_atual = colunas_cards[card_idx % 2]
            primeira_linha = grupo.iloc[0]
            cidade = limpar_texto(primeira_linha.get('cidade'), '').upper()
            estado = limpar_texto(primeira_linha.get('estado'), '').upper()
            resp = limpar_texto(primeira_linha.get('responsavel_hospital'), 'Não informado').upper()
            tel_resp = limpar_texto(primeira_linha.get('contato_responsavel'), '')
            endereco = limpar_texto(primeira_linha.get('endereco'), f"{cidade} - {estado}").upper()
            cnpj_cli = limpar_texto(primeira_linha.get('cnpj'), 'N/D')
            
            equipamentos_validos = grupo[~grupo['equipamento'].astype(str).str.contains("Nenhum|Aguardando", case=False, na=False)]
            qtd_equipamentos = len(equipamentos_validos)
            
            with col_atual:
                st.markdown(f"""
                    <div class="client-card">
                        <h3>🏥 {cliente_nome}</h3>
                        <p>🏢 <strong>CNPJ:</strong> {cnpj_cli}</p>
                        <p>📍 <strong>Local / Cidade:</strong> {cidade} - {estado}</p>
                        <p>🏠 <strong>Endereço Operacional:</strong> {endereco}</p>
                        <p>👤 <strong>Contacto Local:</strong> {resp} ({tel_resp})</p>
                    </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"⚙️ Ver Equipamentos & QR Codes ({qtd_equipamentos} registados)"):
                    if equipamentos_validos.empty:
                        st.info("Nenhum equipamento registado nesta unidade.")
                    else:
                        for i_eq, r_eq in equipamentos_validos.iterrows():
                            eq_desc = limpar_texto(r_eq.get('equipamento'), '').upper()
                            icone = obter_icone_equipamento(eq_desc)
                            
                            col_eq_txt, col_eq_qr, col_eq_ed, col_eq_del = st.columns([5, 1.5, 1.2, 1.2])
                            with col_eq_txt:
                                st.markdown(f"{icone} **{eq_desc}**")
                            with col_eq_qr:
                                if st.button("📱 QR", key=f"btn_qr_{i_eq}"):
                                    st.session_state[f"ver_qr_{i_eq}"] = not st.session_state.get(f"ver_qr_{i_eq}", False)
                            with col_eq_ed:
                                if st.button("✏️", key=f"btn_edit_{i_eq}"):
                                    st.session_state[f"editando_{i_eq}"] = True
                            with col_eq_del:
                                if st.button("🗑️", key=f"btn_del_{i_eq}"):
                                    df = df.drop(i_eq)
                                    if salvar_dados_seguro(df):
                                        st.cache_data.clear()
                                        st.success("Equipamento excluído com sucesso!")
                                        st.rerun()

                            if st.session_state.get(f"ver_qr_{i_eq}", False):
                                q_eq = urllib.parse.quote(eq_desc)
                                q_cli = urllib.parse.quote(cliente_nome)
                                url_portal_qr = f"http://localhost:8501/?equipamento_qr={q_eq}&cliente_qr={q_cli}"
                                img_qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={urllib.parse.quote(url_portal_qr)}"
                                st.image(img_qr_api, width=150)
                                st.caption("📱 Etiqueta QR Code do Equipamento (Histórico de OS + Abertura de Chamado).")
                                if st.button("👁️ Testar Visão do Cliente (Abrir Portal QR)", key=f"sim_qr_{i_eq}"):
                                    st.session_state.simulando_qr_eq = eq_desc
                                    st.session_state.simulando_qr_cli = cliente_nome
                                    st.rerun()

                            if st.session_state.get(f"editando_{i_eq}", False):
                                with st.form(f"form_edit_{i_eq}"):
                                    novo_texto_eq = st.text_input("Editar Equipamento / Detalhes", value=eq_desc)
                                    col_sb1, col_sb2 = st.columns(2)
                                    with col_sb1:
                                        btn_salvar_ed = st.form_submit_button("💾 Salvar Alteração")
                                    with col_sb2:
                                        btn_cancelar_ed = st.form_submit_button("❌ Cancelar")
                                    
                                    if btn_salvar_ed:
                                        df.at[i_eq, 'equipamento'] = novo_texto_eq.strip().upper()
                                        if salvar_dados_seguro(df):
                                            st.session_state[f"editando_{i_eq}"] = False
                                            st.cache_data.clear()
                                            st.success("Equipamento atualizado!")
                                            st.rerun()
                                    if btn_cancelar_ed:
                                        st.session_state[f"editando_{i_eq}"] = False
                                        st.rerun()
            card_idx += 1

# ----------------------------------------------------
# ABA 5: ABERTURA DE CHAMADOS & OS (COMPLETA + PREVENTIVAS POR PARTES + ORÇAMENTO/PIX/BOLETO + REABERTURA)
# ----------------------------------------------------
elif acao == "🎫 Abertura de Chamados & OS":
    st.markdown("### 🎫 Gestão de Ordens de Serviço (OS), Preventivas por Partes & Faturamento")
    st.markdown(
        "Preenchimento online ou **100% offline** com histórico de etapas da preventiva, "
        "reatribuição de técnico, anexo de orçamento aprovado e faturamento (Boleto ou Pix 10%)."
    )

    sub_os = st.radio(
        "Escolha a vista:",
        [
            "📋 Listar / Executar Ordens Abertas",
            "📴 Modo Campo Offline (Baixar / Sincronizar)",
            "📁 Histórico de OS Concluídas & Reabertura",
            "➕ Criar Nova OS"
        ],
        horizontal=True
    )
    st.markdown("---")

    if sub_os == "📴 Modo Campo Offline (Baixar / Sincronizar)":
        col_off1, col_off2 = st.columns(2)

        with col_off1:
            st.markdown("#### 📥 1. Baixar Aplicativo Coletor Offline")
            st.info("Descarregue o Coletor Universal Offline para o telemóvel ou tablet para uso em bunkers/salas sem sinal.")
            html_universal = gerar_html_coletor_offline(df, EQUIPA_TECNICA)
            st.download_button(
                label="📲 Baixar Aplicativo Coletor Offline (EMED_Offline.html)",
                data=html_universal.encode('utf-8'),
                file_name="EMED_Coletor_Offline.html",
                mime="text/html",
                type="primary"
            )

        with col_off2:
            st.markdown("#### 📤 2. Sincronizar OS Preenchidas Offline")
            arquivos_offline = st.file_uploader("Selecione ficheiros .json de OS Offline", type=["json"], accept_multiple_files=True)
            if arquivos_offline:
                if st.button("🔄 Processar e Sincronizar no Sistema EMED", type="primary"):
                    qtd_sinc = 0
                    for arq in arquivos_offline:
                        try:
                            dados_json = json.loads(arq.read().decode('utf-8'))
                            df, _ = sincronizar_os_offline_idempotente(
                                df,
                                dados_json,
                                EQUIPA_TECNICA,
                                st.session_state.utilizador
                            )
                            qtd_sinc += 1
                        except Exception as e:
                            st.error(f"Erro ao ler ficheiro {arq.name}: {e}")

                    if qtd_sinc > 0 and salvar_dados_seguro(df):
                        st.cache_data.clear()
                        st.success(f"🎉 {qtd_sinc} Ordem(ns) de Serviço sincronizada(s) de forma idempotente com sucesso!")
                        st.rerun()

    elif sub_os == "➕ Criar Nova OS":
        clientes_externos = sorted([
            c for c in df['cliente'].unique()
            if str(c).strip() != '' and "NENHUM (AGUARDANDO" not in str(c).upper()
        ])
        setores_internos = [f"[INTERNO] {s}" for s in carregar_clientes_internos()['nome_setor'].tolist()]
        clientes_disponiveis = clientes_externos + setores_internos

        with st.form("form_abertura_chamado_estruturada"):
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                chamado_cliente = st.selectbox("1. Selecionar Unidade / Hospital ou Setor Interno *", clientes_disponiveis)
                eqs_do_cliente = df[df['cliente'] == chamado_cliente]['equipamento'].tolist()
                eqs_validos_cliente = [e for e in eqs_do_cliente if not str(e).lower().startswith(('nenhum', 'aguardando'))]
                opcoes_equipamento = eqs_validos_cliente + ["➕ Outro / Equipamento ou Serviço Interno Avulso"]
                escolha_equipamento = st.selectbox("2. Equipamento Alvo *", opcoes_equipamento)
                
                equipamento_final = escolha_equipamento
                if escolha_equipamento == "➕ Outro / Equipamento ou Serviço Interno Avulso":
                    equipamento_final = st.text_input("Especifique o Equipamento ou Ativo Interno *")

                opcoes_etapas_abertura = [
                    "NÃO APLICÁVEL / CORRETIVA GERAL",
                    "ETAPA 1: MESA DE EXAMES, COMANDOS E CONSOLE",
                    "ETAPA 2: GANTRY, PDU, QUADRO ELÉTRICO E CABEAMENTO",
                    "ETAPA 3: TUBO, GERADOR DE ALTA TENSÃO E COLIMAÇÃO",
                    "PREVENTIVA COMPLETA (CHECKLIST INTEGRAL POP/IT)"
                ]
                etapa_sugerida = sugerir_proxima_etapa_preventiva(df, chamado_cliente, equipamento_final)
                idx_etapa_sug = opcoes_etapas_abertura.index(etapa_sugerida) if etapa_sugerida in opcoes_etapas_abertura else 0
                etapa_preventiva_sel = st.selectbox(
                    "2.1 Divisão / Etapa da Preventiva (Sugerida automaticamente pelo ciclo anterior)",
                    opcoes_etapas_abertura,
                    index=idx_etapa_sug
                )

            with col_ch2:
                chamado_tipo = st.selectbox(
                    "3. Tipo de Serviço",
                    ["PREVENTIVA (Com Checklist POP/IT)", "CORRETIVA (Falha / Parada)", "INSTALAÇÃO", "CALIBRAÇÃO", "SERVIÇO INTERNO EMED"]
                )
                chamado_prioridade = st.selectbox("4. Nível de Urgência", ["NORMAL", "URGENTE / HOSPITAL PARADO", "CRÍTICO (Emergência)"])
                
                lista_tecs_ch = sorted(list(EQUIPA_TECNICA.keys()))
                tec_default = st.session_state.utilizador.upper() if st.session_state.perfil != "Gestor" else lista_tecs_ch[0]
                idx_tec_def = lista_tecs_ch.index(tec_default) if tec_default in lista_tecs_ch else 0
                chamado_tec = st.selectbox("5. Técnico Responsável", lista_tecs_ch, index=idx_tec_def)
                instrumento_abertura = st.text_input(
                    "5.1 Instrumento / Ferramenta Especial Necessária",
                    placeholder="EX: MULTÍMETRO FLUKE, FANTOMA, CHAVE DINAMOMÉTRICA"
                )

            st.markdown("#### 🔬 Pré-Atendimento, Defeito Relatado & Diagnóstico Prévio")
            col_pre1, col_pre2 = st.columns(2)
            with col_pre1:
                pre_codigo_erro = st.text_input("Código de Erro no Display (Ex: ERR-402, E-10)")
                pre_sintoma = st.selectbox(
                    "Sintoma / Comportamento",
                    ["FALHA DE LIGAÇÃO / FONTE", "ERRO DE SOFTWARE / TRAVAMENTO", "DEFEITO DE HARDWARE / PLACA", "RUÍDO ANÓMALO / MECÂNICO", "MANUTENÇÃO PROGRAMADA", "OUTROS"]
                )
                cond_ini_abertura = st.selectbox(
                    "Condição Inicial Informada do Equipamento",
                    ["OPERACIONAL", "OPERANDO COM RESTRIÇÃO", "PARADO / INOPERANTE", "EM BANCADA / DESMONTADO"]
                )
            with col_pre2:
                pre_testes_cliente = st.text_input("Testes já realizados pelo cliente no local")
                orcamento_aprovado_abertura = st.file_uploader("📄 Anexar Orçamento Aprovado (PDF/Imagem - Opcional)", type=["pdf", "png", "jpg", "jpeg"])
                obs_abertura = st.text_input("Observações de Acesso / Horário / Sala (Opcional)", placeholder="EX: PROCURAR ENF. CHEFE NO 2º ANDAR")
            
            chamado_relato = st.text_area("6. Defeito Relatado pelo Cliente / Escopo da Preventiva *", placeholder="Descreva o defeito relatado pelo hospital ou os pontos a verificar...")
            foto_arquivo = st.file_uploader("📸 Anexar Foto Inicial / Evidência do Defeito (Opcional)", type=["png", "jpg", "jpeg"])
            chamado_data = st.date_input("7. Data Prevista", value=datetime.date.today())

            btn_abrir_chamado = st.form_submit_button("🚀 Emitir Nova Ordem de Serviço", type="primary")

            if btn_abrir_chamado:
                if not equipamento_final or not chamado_relato:
                    st.error("⚠️ Preencha o equipamento e o defeito relatado!")
                else:
                    linhas_cli = df[df['cliente'] == chamado_cliente]
                    info_cli_base = linhas_cli.iloc[0] if not linhas_cli.empty else {}
                    tel_tec_val = EQUIPA_TECNICA.get(chamado_tec, {}).get("tel", "")
                    ass_tec_padrao = EQUIPA_TECNICA.get(chamado_tec, {}).get("assinatura", f"{chamado_tec} - CFT")
                    
                    pasta_uploads = os.path.join(BASE_DIR, "uploads_os")
                    os.makedirs(pasta_uploads, exist_ok=True)

                    caminho_foto_salva = ""
                    if foto_arquivo is not None:
                        caminho_foto_salva = os.path.join(pasta_uploads, foto_arquivo.name)
                        with open(caminho_foto_salva, "wb") as f:
                            f.write(foto_arquivo.getbuffer())

                    caminho_orc_salvo = ""
                    if orcamento_aprovado_abertura is not None:
                        caminho_orc_salvo = os.path.join(pasta_uploads, f"ORC_{orcamento_aprovado_abertura.name}")
                        with open(caminho_orc_salvo, "wb") as f:
                            f.write(orcamento_aprovado_abertura.getbuffer())

                    cod_err_str = pre_codigo_erro.strip().upper() if pre_codigo_erro else 'N/D'
                    tst_cli_str = pre_testes_cliente.strip().upper() if pre_testes_cliente else 'N/D'
                    pre_atendimento_str = f"[CÓDIGO ERRO: {cod_err_str}] [SINTOMA: {pre_sintoma}] [TESTES: {tst_cli_str}]"

                    nova_os = {
                        'cliente': chamado_cliente,
                        'cidade': limpar_texto(info_cli_base.get('cidade'), 'FORTALEZA').upper(),
                        'estado': limpar_texto(info_cli_base.get('estado'), 'CE').upper(),
                        'equipamento': equipamento_final.strip().upper(),
                        'endereco': limpar_texto(info_cli_base.get('endereco'), 'SEDE EMED').upper(),
                        'tipo_servico': chamado_tipo.upper(),
                        'data_agendamento': pd.to_datetime(chamado_data).strftime('%Y-%m-%d'),
                        'tecnico_responsavel': chamado_tec.upper(),
                        'telefone_tecnico': tel_tec_val,
                        'responsavel_hospital': limpar_texto(info_cli_base.get('responsavel_hospital'), 'RESPONSÁVEL LOCAL').upper(),
                        'contato_responsavel': limpar_texto(info_cli_base.get('contato_responsavel'), ''),
                        'confirmado': 'SIM',
                        'pendencias': f"[{chamado_prioridade.upper()}] {chamado_relato.strip().upper()}",
                        'status': 'ATIVO',
                        'checkin_hora': '',
                        'checkout_hora': '',
                        'tempo_atendimento': '',
                        'checklist_pop': '',
                        'assinatura_cliente': '',
                        'assinatura_tecnico': ass_tec_padrao,
                        'pre_atendimento': pre_atendimento_str,
                        'foto_evidencia': caminho_foto_salva,
                        'cnpj': limpar_texto(info_cli_base.get('cnpj'), ''),
                        'cep': limpar_texto(info_cli_base.get('cep'), ''),
                        'email': limpar_texto(info_cli_base.get('email'), ''),
                        'whatsapp': limpar_texto(info_cli_base.get('whatsapp'), ''),
                        'endereco_fiscal': limpar_texto(info_cli_base.get('endereco_fiscal'), ''),
                        'tipo_contrato': limpar_texto(info_cli_base.get('tipo_contrato'), 'CONTRATO'),
                        'instrumento_necessario': instrumento_abertura.strip().upper(),
                        'etapa_preventiva': "" if "NÃO APLICÁVEL" in etapa_preventiva_sel else etapa_preventiva_sel,
                        'orcamento_anexo': caminho_orc_salvo,
                        'condicao_pagamento': '',
                        'valor_os': 0.0,
                        'defeito_relatado': chamado_relato.strip().upper(),
                        'condicao_inicial': cond_ini_abertura,
                        'problemas_encontrados': '',
                        'causa_raiz': '',
                        'servico_executado': '',
                        'parametros_medidos': '',
                        'observacoes_gerais': obs_abertura.strip().upper(),
                        'condicao_final': 'LIBERADO PARA USO NORMAL',
                        'foto_depois': '',
                        'assinatura_cliente_img': ''
                    }
                    df = pd.concat([df, pd.DataFrame([nova_os])], ignore_index=True)
                    if salvar_dados_seguro(df):
                        st.cache_data.clear()
                        st.success("✅ Salvo com sucesso! Ordem de Serviço emitida.")
                        st.rerun()

    elif sub_os == "📁 Histórico de OS Concluídas & Reabertura":
        st.markdown("#### 📁 Ordens de Serviço Fechadas / Faturamento & Reabertura para Outro Técnico")
        df_os_concluidas = df[df['status'].astype(str).str.upper() == 'CONCLUÍDO']
        if df_os_concluidas.empty:
            st.info("ℹ️ Ainda não existem ordens de serviço concluídas.")
        else:
            for idx_c, row_c in df_os_concluidas.iterrows():
                id_os_c = obter_id_os(idx_c, row_c)
                tec_hist_c = limpar_texto(row_c.get('tecnico_responsavel'))
                titulo_exp_c = f"✅ OS #{id_os_c} | {row_c['cliente']} — Equipamento: {row_c['equipamento']} [Técnico: {tec_hist_c}]"
                with st.expander(titulo_exp_c):
                    laudo_hist = limpar_texto(row_c.get('pendencias'))
                    etapa_hist = limpar_texto(row_c.get('etapa_preventiva'), 'GERAL')
                    ass_tec_hist = limpar_texto(row_c.get('assinatura_tecnico'), '-')
                    ass_cli_hist = limpar_texto(row_c.get('assinatura_cliente'), '-')
                    def_rel_h = limpar_texto(row_c.get('defeito_relatado'), '-')
                    prob_enc_h = limpar_texto(row_c.get('problemas_encontrados'), '-')
                    srv_exec_h = limpar_texto(row_c.get('servico_executado'), laudo_hist)
                    obs_ger_h = limpar_texto(row_c.get('observacoes_gerais'), '-')
                    param_h = limpar_texto(row_c.get('parametros_medidos'), '-')
                    cond_f_h = limpar_texto(row_c.get('condicao_final'), 'LIBERADO PARA USO NORMAL')

                    ch1, ch2 = st.columns(2)
                    with ch1:
                        st.markdown(f"**📢 Defeito Relatado:** {def_rel_h}")
                        st.markdown(f"**🔍 Problemas Encontrados:** {prob_enc_h}")
                        st.markdown(f"**🛠️ Serviço Executado / Laudo:** {srv_exec_h}")
                        st.markdown(f"**📋 Etapa Preventiva Executada:** `{etapa_hist}`")
                    with ch2:
                        st.markdown(f"**⚡ Parâmetros / Medições:** `{param_h}`")
                        st.markdown(f"**🏁 Condição Final na Saída:** `{cond_f_h}`")
                        st.markdown(f"**📝 Observações Gerais:** {obs_ger_h}")
                        if limpar_texto(row_c.get('condicao_pagamento')):
                            st.markdown(f"💰 **Faturamento:** `{row_c.get('condicao_pagamento')}`")
                        if limpar_texto(row_c.get('orcamento_anexo')):
                            nome_arq_orc = os.path.basename(str(row_c.get('orcamento_anexo')))
                            st.markdown(f"📎 **Orçamento Aprovado Anexado:** `{nome_arq_orc}`")

                    f_ant_c = limpar_texto(row_c.get('foto_evidencia'), '')
                    f_dep_c = limpar_texto(row_c.get('foto_depois'), '')
                    if (f_ant_c and os.path.exists(f_ant_c)) or (f_dep_c and os.path.exists(f_dep_c)):
                        st.markdown("##### 📸 Registo Fotográfico da Intervenção")
                        cf1, cf2 = st.columns(2)
                        with cf1:
                            if f_ant_c and os.path.exists(f_ant_c):
                                st.image(f_ant_c, caption="Foto Antes / Evidência Inicial", width=260)
                        with cf2:
                            if f_dep_c and os.path.exists(f_dep_c):
                                st.image(f_dep_c, caption="Foto Depois / Serviço Concluído", width=260)

                    st.markdown("---")
                    st.markdown("##### ✍️ Rubrica Pré-Salva do Técnico & Assinatura Digital do Cliente")
                    ca_h1, ca_h2 = st.columns(2)
                    with ca_h1:
                        renderizar_rubrica_tecnico(tec_hist_c, EQUIPA_TECNICA)
                    with ca_h2:
                        st.markdown(f"**Responsável no Hospital:** `{ass_cli_hist}`")
                        img_sig_cli = limpar_texto(row_c.get('assinatura_cliente_img'), '')
                        if img_sig_cli.startswith("data:image"):
                            st.markdown(f"""
                                <div style="background:#0b132b; border:1px solid #64dfdf; border-radius:8px; padding:8px; text-align:center;">
                                    <img src="{img_sig_cli}" style="max-width:260px; height:auto;" alt="Assinatura Cliente"/>
                                    <p style="margin:2px 0 0 0; font-size:11px; color:#10b981 !important;">✅ Assinatura Coletada na Tela do Celular</p>
                                </div>
                            """, unsafe_allow_html=True)
                        elif img_sig_cli and os.path.exists(img_sig_cli):
                            st.image(img_sig_cli, caption="Rubrica do Cliente", width=240)

                    st.markdown("---")
                    st.markdown("##### 🔄 Reabrir OS / Transferir Pendência para Outro Técnico")
                    with st.form(f"form_reabrir_os_{idx_c}"):
                        lista_t_reab = sorted(list(EQUIPA_TECNICA.keys()))
                        tec_reab = st.selectbox("Selecionar Novo Técnico Responsável", lista_t_reab, key=f"reab_t_{idx_c}")
                        motivo_reab = st.text_input(
                            "Pendência / O que falta realizar (Ficará visível junto ao histórico anterior)",
                            key=f"reab_m_{idx_c}"
                        )
                        inst_reab = st.text_input("Instrumento / Material Necessário para levar", key=f"reab_i_{idx_c}")
                        if st.form_submit_button("🔓 Reabrir OS no Nome do Novo Técnico", type="primary"):
                            df.at[idx_c, 'status'] = 'ATIVO'
                            df.at[idx_c, 'tecnico_responsavel'] = tec_reab
                            df.at[idx_c, 'telefone_tecnico'] = EQUIPA_TECNICA.get(tec_reab, {}).get("tel", "")
                            df.at[idx_c, 'pendencias'] = f"[REABERTA P/ {tec_reab}] {motivo_reab.strip().upper()} || HISTÓRICO ANTERIOR: {laudo_hist}"
                            df.at[idx_c, 'instrumento_necessario'] = inst_reab.strip().upper()
                            if salvar_dados_seguro(df):
                                st.cache_data.clear()
                                st.success(f"✅ Salvo com sucesso! OS #{id_os_c} reaberta para o técnico {tec_reab}!")
                                st.rerun()

    else:
        st.markdown("#### 🛠️ Execução Modular de Ordem de Serviço em Campo (6 Módulos)")
        df_os_ativas = df[df['status'].astype(str).str.upper() == 'ATIVO']

        if df_os_ativas.empty:
            st.info("ℹ️ Não existem ordens de serviço ativas no momento.")
        else:
            for idx_os, row_os in df_os_ativas.iterrows():
                id_os_ativa = obter_id_os(idx_os, row_os)
                tec_resp_os = limpar_texto(row_os.get('tecnico_responsavel'), 'A DEFINIR').upper()
                cli_os_atual = limpar_texto(row_os.get('cliente'), '')
                eq_os_atual = limpar_texto(row_os.get('equipamento'), '')
                inst_os_atual = limpar_texto(row_os.get('instrumento_necessario'), '')
                etapa_os_atual = limpar_texto(row_os.get('etapa_preventiva'), '')
                srv_os_atual = limpar_texto(row_os.get('tipo_servico'), 'PREVENTIVA')
                dt_os_atual = limpar_texto(row_os.get('data_agendamento'), '-')
                pend_os_atual = limpar_texto(row_os.get('pendencias'))
                def_rel_atual = limpar_texto(row_os.get('defeito_relatado'), pend_os_atual)
                pre_at_atual = limpar_texto(row_os.get('pre_atendimento'), 'Sem registo prévio')
                prob_enc_atual = limpar_texto(row_os.get('problemas_encontrados'), '')
                srv_exec_atual = limpar_texto(row_os.get('servico_executado'), '')
                obs_ger_atual = limpar_texto(row_os.get('observacoes_gerais'), '')
                param_atual = limpar_texto(row_os.get('parametros_medidos'), '')
                
                titulo_os_ativa = f"🛠️ OS #{id_os_ativa} | {cli_os_atual} — Equipamento: {eq_os_atual} [Técnico: {tec_resp_os}]"
                with st.expander(titulo_os_ativa):
                    # CABEÇALHO RÁPIDO: TEMPOS, CHECK-IN/OUT E REATRIBUIÇÃO DE TÉCNICO
                    c_top1, c_top2, c_top3 = st.columns([2.2, 1.4, 1.4])
                    with c_top1:
                        st.markdown(f"**Serviço:** `{srv_os_atual}` | **Agendado:** `{dt_os_atual}`")
                        if inst_os_atual:
                            st.markdown(f"📐 **Instrumento / Material Requerido:** `{inst_os_atual}`")
                        lista_tecs_exec = sorted(list(EQUIPA_TECNICA.keys()))
                        idx_t_exec = lista_tecs_exec.index(tec_resp_os) if tec_resp_os in lista_tecs_exec else 0
                        novo_tec_exec = st.selectbox(
                            "👷 Técnico Executante (Altere se outro técnico assumir a OS)",
                            lista_tecs_exec,
                            index=idx_t_exec,
                            key=f"sel_tec_exec_{idx_os}"
                        )
                    with c_top2:
                        if st.button("📍 Marcar Check-in (Chegada)", key=f"cin_{idx_os}", use_container_width=True):
                            hora_atual = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                            df.at[idx_os, 'checkin_hora'] = hora_atual
                            salvar_dados_seguro(df)
                            st.cache_data.clear()
                            st.rerun()
                        cin_val = limpar_texto(row_os.get('checkin_hora'))
                        st.caption(f"✅ **Chegada:** {cin_val if cin_val else 'Não registada'}")
                    with c_top3:
                        if st.button("🏁 Marcar Check-out (Saída)", key=f"cout_{idx_os}", use_container_width=True):
                            hora_saida = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                            df.at[idx_os, 'checkout_hora'] = hora_saida
                            dur_calc = calcular_duracao_os(row_os.get('checkin_hora', ''), hora_saida)
                            if dur_calc:
                                df.at[idx_os, 'tempo_atendimento'] = dur_calc
                            salvar_dados_seguro(df)
                            st.cache_data.clear()
                            st.rerun()
                        cout_val = limpar_texto(row_os.get('checkout_hora'))
                        dur_val = limpar_texto(row_os.get('tempo_atendimento'))
                        txt_dur = f" ({dur_val})" if dur_val else ""
                        st.caption(f"🏁 **Saída:** {cout_val if cout_val else 'Não registada'}{txt_dur}")

                    st.markdown("---")

                    # ESTRUTURA MODULAR EM 6 ABAS PARA FACILITAR O PREENCHIMENTO NO CELULAR E PC
                    m_tab1, m_tab2, m_tab3, m_tab4, m_tab5, m_tab6 = st.tabs([
                        "📢 1. Defeito Relatado",
                        "🔍 2. Problemas Encontrados",
                        "🛠️ 3. Serviço & Peças",
                        "🚨 4. Pendências & Obs.",
                        "📸 5. Fotos & Anexos",
                        "✍️ 6. Assinatura & Fecho"
                    ])

                    # MÓDULO 1: DEFEITO RELATADO, TRIAGEM & HISTÓRICO DO APARELHO
                    with m_tab1:
                        st.markdown("##### 📢 Defeito Relatado pelo Cliente & Estado Inicial na Chegada")
                        st.caption(f"🔬 **Dados de Pré-Atendimento / Erros:** {pre_at_atual}")
                        opcoes_cond_ini = ["OPERACIONAL", "OPERANDO COM RESTRIÇÃO", "PARADO / INOPERANTE", "EM BANCADA / DESMONTADO"]
                        cond_ini_atual = limpar_texto(row_os.get('condicao_inicial'), 'OPERACIONAL')
                        idx_ci = opcoes_cond_ini.index(cond_ini_atual) if cond_ini_atual in opcoes_cond_ini else 0
                        condicao_ini_os = st.selectbox(
                            "Condição do Equipamento na Chegada do Técnico",
                            opcoes_cond_ini,
                            index=idx_ci,
                            key=f"ci_os_{idx_os}"
                        )
                        defeito_relatado_in = st.text_area(
                            "Defeito Relatado pelo Hospital / Solicitação Original *",
                            value=def_rel_atual,
                            height=90,
                            key=f"def_rel_{idx_os}"
                        )

                        df_hist_prev = df[
                            (df['cliente'] == cli_os_atual) &
                            (df['equipamento'] == eq_os_atual) &
                            (df.index != idx_os)
                        ]
                        if not df_hist_prev.empty:
                            st.markdown("###### 📜 Histórico Recente deste Equipamento (Evita Retrabalho)")
                            for idx_hp, r_hp in df_hist_prev.tail(4).iterrows():
                                id_hp = obter_id_os(idx_hp, r_hp)
                                et_hp = limpar_texto(r_hp.get('etapa_preventiva'), 'ETAPA GERAL')
                                dt_hp = limpar_texto(r_hp.get('data_agendamento'), 'S/D')
                                tc_hp = limpar_texto(r_hp.get('tecnico_responsavel'))
                                pd_hp = limpar_texto(r_hp.get('pendencias'))
                                st.caption(f"• **OS #{id_hp}** ({dt_hp}) | **Técnico:** {tc_hp} | **Etapa:** {et_hp} | **Resumo:** {pd_hp}")

                    # MÓDULO 2: PROBLEMAS ENCONTRADOS, CAUSA RAIZ & MEDIÇÕES TÉCNICAS
                    with m_tab2:
                        st.markdown("##### 🔍 Problemas Encontrados em Campo, Causa Raiz & Medições")
                        opcoes_causa = [
                            "MANUTENÇÃO PREVENTIVA PROGRAMADA (SEM FALHA)",
                            "DESGASTE NATURAL DE COMPONENTE / PEÇA",
                            "OSCILAÇÃO / FALHA NA REDE ELÉTRICA DO HOSPITAL",
                            "FALHA DE REFRIGERAÇÃO / AR-CONDICIONADO DA SALA",
                            "DESCALIBRAÇÃO / DESAJUSTE TÉCNICO",
                            "FALHA DE OPERAÇÃO / MAU USO",
                            "FALHA DE SOFTWARE / SISTEMA / REDE DICOM",
                            "OUTRA CAUSA / EM ANÁLISE"
                        ]
                        causa_at = limpar_texto(row_os.get('causa_raiz'), opcoes_causa[0])
                        idx_cr = opcoes_causa.index(causa_at) if causa_at in opcoes_causa else 0
                        causa_raiz_in = st.selectbox(
                            "Causa Raiz Identificada (Engenharia Clínica)",
                            opcoes_causa,
                            index=idx_cr,
                            key=f"cr_os_{idx_os}"
                        )
                        problemas_encontrados_in = st.text_area(
                            "Problemas Encontrados / Diagnóstico Técnico Detalhado *",
                            value=prob_enc_atual,
                            placeholder="Descreva os defeitos constatados na inspeção técnica, placas/módulos afetados ou estado geral...",
                            height=100,
                            key=f"prob_enc_{idx_os}"
                        )
                        parametros_medidos_in = st.text_input(
                            "⚡ Parâmetros Técnicos & Medições Ambientais (Tensão F-N, Terra-Neutro, Temp. Sala °C, Disparos/Horas Tubo)",
                            value=param_atual,
                            placeholder="EX: F-N: 220V | T-N: 0.6V | TEMP SALA: 20°C | UMIDADE: 52% | TUBO: 45.200 DISPAROS",
                            key=f"param_med_{idx_os}"
                        )

                    # MÓDULO 3: SERVIÇO EXECUTADO, ETAPA POP/IT & PEÇAS APLICADAS
                    with m_tab3:
                        st.markdown("##### 🛠️ Serviço Executado, Checklist POP/IT & Aplicação de Peças")
                        c_s1, c_s2 = st.columns(2)
                        with c_s1:
                            etapa_executada_fecho = st.selectbox(
                                "Parte / Etapa do Equipamento Inspecionada nesta Visita",
                                [
                                    limpar_texto(etapa_os_atual, "GERAL / CORRETIVA"),
                                    "PARTE 1: MESA DE EXAMES, COMANDOS E CONSOLE (PRÓXIMA: GANTRY/PDU)",
                                    "PARTE 2: GANTRY, PDU, QUADRO ELÉTRICO (PRÓXIMA: TUBO/GERADOR)",
                                    "PARTE 3: TUBO, ALTA TENSÃO E CALIBRAÇÃO (PRÓXIMA: MESA/CONSOLE)",
                                    "PREVENTIVA COMPLETA REALIZADA"
                                ],
                                key=f"et_f_{idx_os}"
                            )
                            itens_pop_opcoes = [
                                "LIMPEZA TÉCNICA INTERNA/EXTERNA",
                                "INSPEÇÃO DE CABOS, CONECTORES E ATERRAMENTO",
                                "VERIFICAÇÃO DE TRAVAS E SEGURANÇA MECÂNICA",
                                "LUBRIFICAÇÃO DE GUIAS E ROLAMENTOS",
                                "CALIBRAÇÃO / TESTES DE DISPARO E IMAGEM",
                                "TESTE FUNCIONAL COM OPERADOR LOCAL"
                            ]
                            pop_salvo = [x.strip() for x in limpar_texto(row_os.get('checklist_pop')).split(",") if x.strip() in itens_pop_opcoes]
                            checklist_pop_sel = st.multiselect(
                                "Checklist POP / Procedimentos Realizados",
                                options=itens_pop_opcoes,
                                default=pop_salvo,
                                key=f"chk_pop_ms_{idx_os}"
                            )
                        with c_s2:
                            pecas_disponiveis = df_estoque['nome_peca'].tolist() if not df_estoque.empty else []
                            peca_selecionada = st.selectbox(
                                "Selecione a Peça Aplicada do Estoque (Baixa Automática)",
                                ["NENHUMA PEÇA"] + pecas_disponiveis,
                                key=f"peca_{idx_os}"
                            )
                            qtd_aplicada = st.number_input("Quantidade Aplicada", min_value=1, value=1, key=f"qtd_peca_{idx_os}")

                        obs_tecnico_final = st.text_area(
                            "Descrição Detalhada do Serviço Executado / Solução Aplicada *",
                            value=srv_exec_atual,
                            placeholder="Relate todos os procedimentos executados, ajustes, reparos e testes finais...",
                            height=110,
                            key=f"obs_f_{idx_os}"
                        )

                    # MÓDULO 4: PENDÊNCIAS, CONDIÇÃO FINAL & OBSERVAÇÕES / RECOMENDAÇÕES
                    with m_tab4:
                        st.markdown("##### 🚨 Status de Pendências, Condição de Saída & Observações ao Hospital")
                        status_fecho_escolha = st.radio(
                            "Resultado desta Intervenção:",
                            [
                                "✅ CONCLUÍDO (Fechar OS e Gerar Documento de Faturamento)",
                                "🚨 DEIXAR PENDÊNCIA ATIVA (Mantém alerta ligado para próxima intervenção)"
                            ],
                            horizontal=True,
                            key=f"rad_st_{idx_os}"
                        )
                        opcoes_cond_fim = [
                            "LIBERADO PARA USO NORMAL",
                            "LIBERADO COM RESTRIÇÃO OPERACIONAL",
                            "PARADO AGUARDANDO PEÇA / APROVAÇÃO DE ORÇAMENTO",
                            "INTERDITADO POR SEGURANÇA TÉCNICA"
                        ]
                        cond_fim_at = limpar_texto(row_os.get('condicao_final'), opcoes_cond_fim[0])
                        idx_cf = opcoes_cond_fim.index(cond_fim_at) if cond_fim_at in opcoes_cond_fim else 0
                        condicao_fim_os = st.selectbox(
                            "Condição Final do Equipamento na Saída do Técnico",
                            opcoes_cond_fim,
                            index=idx_cf,
                            key=f"cf_os_{idx_os}"
                        )
                        inst_prox_visita = st.text_input(
                            "📐 Instrumento, Ferramenta ou Peça necessária para a próxima visita (se ficar pendente)",
                            value=inst_os_atual,
                            placeholder="EX: LEVAR MULTÍMETRO FLUKE, FANTOMA E PLACA FONTE",
                            key=f"inst_prox_{idx_os}"
                        )
                        observacoes_gerais_in = st.text_area(
                            "📝 Observações Gerais & Recomendações Técnicas ao Hospital (Fica registado na OS)",
                            value=obs_ger_atual,
                            placeholder="EX: RECOMENDADO ADEQUAR CLIMATIZAÇÃO DA SALA / PROVIDENCIAR NOBREAK DEDICADO...",
                            height=85,
                            key=f"obs_ger_{idx_os}"
                        )
                        agendar_prox_ciclo = st.checkbox(
                            "🔄 Agendar automaticamente a próxima etapa circular da preventiva (+30 dias) ao concluir",
                            value=("PREVENTIVA" in srv_os_atual.upper()),
                            key=f"chk_ciclo_{idx_os}"
                        )

                    # MÓDULO 5: FOTOS (ANTES / DEPOIS) & ORÇAMENTO EM ANEXO
                    with m_tab5:
                        st.markdown("##### 📸 Galeria de Fotos da OS (Antes / Depois) & Orçamento Aprovado")
                        cf_up1, cf_up2, cf_up3 = st.columns(3)
                        with cf_up1:
                            foto_antes_up = st.file_uploader(
                                "📸 Foto Antes / Defeito (PNG/JPG)",
                                type=["png", "jpg", "jpeg"],
                                key=f"f_ant_up_{idx_os}"
                            )
                            f_ant_salva = limpar_texto(row_os.get('foto_evidencia'), '')
                            if f_ant_salva and os.path.exists(f_ant_salva):
                                st.image(f_ant_salva, caption="Foto Inicial Salva", width=200)
                        with cf_up2:
                            foto_depois_up = st.file_uploader(
                                "📸 Foto Depois / Serviço Pronto (PNG/JPG)",
                                type=["png", "jpg", "jpeg"],
                                key=f"f_dep_up_{idx_os}"
                            )
                            f_dep_salva = limpar_texto(row_os.get('foto_depois'), '')
                            if f_dep_salva and os.path.exists(f_dep_salva):
                                st.image(f_dep_salva, caption="Foto Final Salva", width=200)
                        with cf_up3:
                            orcamento_fecho_up = st.file_uploader(
                                "📄 Orçamento Aprovado (PDF/Imagem)",
                                type=["pdf", "png", "jpg", "jpeg"],
                                key=f"orc_up_{idx_os}"
                            )
                            orc_salvo_at = limpar_texto(row_os.get('orcamento_anexo'), '')
                            if orc_salvo_at:
                                st.caption(f"📎 Anexo atual: `{os.path.basename(orc_salvo_at)}`")

                    # MÓDULO 6: FATURAMENTO, RUBRICA PRÉ-SALVA DO TÉCNICO & ASSINATURA DO CLIENTE NO CELULAR
                    with m_tab6:
                        st.markdown("##### 💰 Faturamento & ✍️ Coleta de Assinatura")
                        c_fat1, c_fat2 = st.columns(2)
                        with c_fat1:
                            val_os_ant = limpar_float(row_os.get('valor_os'), 0.0)
                            valor_servico_os = st.number_input(
                                "Valor Total do Orçamento / Serviço + Peças (R$)",
                                min_value=0.0,
                                value=val_os_ant,
                                step=100.0,
                                key=f"val_os_{idx_os}"
                            )
                        with c_fat2:
                            opcao_faturamento = st.selectbox(
                                "💳 Condição de Faturamento (Ao fechar a OS)",
                                [
                                    "FATURAMENTO BOLETO BANCÁRIO (VALOR INTEGRAL)",
                                    "FATURAMENTO PIX À VISTA (COM 10% DE DESCONTO AUTOMÁTICO)",
                                    "CORTESIA / COBERTO POR CONTRATO MENSAL"
                                ],
                                key=f"fat_op_{idx_os}"
                            )

                        if "PIX" in opcao_faturamento and valor_servico_os > 0:
                            valor_final_faturar = round(valor_servico_os * 0.90, 2)
                            st.info(f"⚡ **Desconto de 10% no PIX aplicado:** De R$ {valor_servico_os:,.2f} por **R$ {valor_final_faturar:,.2f}**")
                        else:
                            valor_final_faturar = valor_servico_os

                        st.markdown("---")
                        col_as1, col_as2 = st.columns([1.2, 1.8])
                        with col_as1:
                            st.markdown("###### 👨‍🔧 1. Rubrica do Técnico (Pré-Salva)")
                            ass_padrao_tec = EQUIPA_TECNICA.get(novo_tec_exec, {}).get("assinatura", f"{novo_tec_exec} - CFT")
                            renderizar_rubrica_tecnico(novo_tec_exec, EQUIPA_TECNICA)
                            st.caption("A rubrica e o registo CFT do técnico já estão salvos e são aplicados automaticamente.")

                        with col_as2:
                            st.markdown("###### 🏥 2. Assinatura do Cliente (Pelo Celular)")
                            assinatura_cliente_input = st.text_input(
                                "Nome e Cargo/Setor do Responsável no Hospital *",
                                value=limpar_texto(row_os.get('assinatura_cliente'), ''),
                                placeholder="EX: DR. CARLOS / ENF. MARIA - RADIOLOGIA",
                                key=f"as_cli_{idx_os}"
                            )
                            label_input_sig = renderizar_quadro_assinatura_cliente(idx_os)
                            sig_img_atual = limpar_texto(row_os.get('assinatura_cliente_img'), '')
                            assinatura_cli_b64 = st.text_input(
                                label_input_sig,
                                value=sig_img_atual,
                                placeholder="Gerado automaticamente ao clicar em 'Fixar Assinatura do Cliente na OS'",
                                key=f"sig_b64_{idx_os}"
                            )

                    st.markdown("---")
                    if st.button("💾 Gravar Ordem de Serviço Modular, Atualizar Estoque e Faturamento", key=f"btn_finalizar_os_{idx_os}", type="primary", use_container_width=True):
                        texto_relatorio_base = obs_tecnico_final.strip() or problemas_encontrados_in.strip()
                        if not assinatura_cliente_input.strip() or not texto_relatorio_base:
                            st.error("⚠️ Preencha o Serviço Executado (Aba 3) e o Nome do Responsável no Hospital (Aba 6)!")
                        else:
                            ref_peca_ant = limpar_texto(row_os.get('peca_baixada_ref'), '')
                            ok_peca, tag_peca, nova_ref_peca = aplicar_peca_os_idempotente(
                                DB_NAME,
                                peca_selecionada,
                                int(qtd_aplicada),
                                ref_peca_ant
                            )
                            if not ok_peca:
                                st.error(tag_peca)
                            else:
                                if tag_peca and tag_peca not in texto_relatorio_base.upper():
                                    relatorio_com_peca = f"{texto_relatorio_base.upper()} | {tag_peca}"
                                else:
                                    relatorio_com_peca = texto_relatorio_base.upper()

                                pasta_uploads = os.path.join(BASE_DIR, "uploads_os")
                                os.makedirs(pasta_uploads, exist_ok=True)

                                if foto_antes_up is not None:
                                    caminho_f_ant = os.path.join(pasta_uploads, f"ANTES_OS{id_os_ativa}_{foto_antes_up.name}")
                                    with open(caminho_f_ant, "wb") as f:
                                        f.write(foto_antes_up.getbuffer())
                                    df.at[idx_os, 'foto_evidencia'] = caminho_f_ant

                                if foto_depois_up is not None:
                                    caminho_f_dep = os.path.join(pasta_uploads, f"DEPOIS_OS{id_os_ativa}_{foto_depois_up.name}")
                                    with open(caminho_f_dep, "wb") as f:
                                        f.write(foto_depois_up.getbuffer())
                                    df.at[idx_os, 'foto_depois'] = caminho_f_dep

                                if orcamento_fecho_up is not None:
                                    caminho_orc_fecho = os.path.join(pasta_uploads, f"ORC_OS{id_os_ativa}_{orcamento_fecho_up.name}")
                                    with open(caminho_orc_fecho, "wb") as f:
                                        f.write(orcamento_fecho_up.getbuffer())
                                    df.at[idx_os, 'orcamento_anexo'] = caminho_orc_fecho

                                fechar_definitivo = "CONCLUÍDO" in status_fecho_escolha
                                resumo_pag = f"{opcao_faturamento} — VALOR FINAL: R$ {valor_final_faturar:,.2f}"

                                df.at[idx_os, 'tecnico_responsavel'] = novo_tec_exec
                                df.at[idx_os, 'telefone_tecnico'] = EQUIPA_TECNICA.get(novo_tec_exec, {}).get("tel", "")
                                df.at[idx_os, 'etapa_preventiva'] = etapa_executada_fecho
                                df.at[idx_os, 'checklist_pop'] = ", ".join(checklist_pop_sel)
                                df.at[idx_os, 'condicao_inicial'] = condicao_ini_os
                                df.at[idx_os, 'defeito_relatado'] = defeito_relatado_in.strip().upper()
                                df.at[idx_os, 'causa_raiz'] = causa_raiz_in
                                df.at[idx_os, 'problemas_encontrados'] = problemas_encontrados_in.strip().upper()
                                df.at[idx_os, 'parametros_medidos'] = parametros_medidos_in.strip().upper()
                                df.at[idx_os, 'servico_executado'] = relatorio_com_peca
                                df.at[idx_os, 'observacoes_gerais'] = observacoes_gerais_in.strip().upper()
                                df.at[idx_os, 'condicao_final'] = condicao_fim_os
                                df.at[idx_os, 'condicao_pagamento'] = resumo_pag
                                df.at[idx_os, 'valor_os'] = float(valor_final_faturar)
                                df.at[idx_os, 'assinatura_cliente'] = assinatura_cliente_input.strip().upper()
                                df.at[idx_os, 'assinatura_cliente_img'] = assinatura_cli_b64.strip()
                                df.at[idx_os, 'assinatura_tecnico'] = ass_padrao_tec.strip().upper()
                                df.at[idx_os, 'peca_baixada_ref'] = nova_ref_peca

                                resumo_diag = f" | [DIAGNÓSTICO: {problemas_encontrados_in.strip().upper()}]" if problemas_encontrados_in.strip() else ""
                                if fechar_definitivo:
                                    df.at[idx_os, 'pendencias'] = f"[CONCLUÍDO - {etapa_executada_fecho}] {relatorio_com_peca}{resumo_diag} | [{resumo_pag}]"
                                    df.at[idx_os, 'status'] = 'CONCLUÍDO'
                                    df.at[idx_os, 'instrumento_necessario'] = ''
                                    if agendar_prox_ciclo:
                                        df, _ = agendar_proxima_etapa_circular(
                                            df,
                                            df.loc[idx_os],
                                            etapa_executada_fecho,
                                            dias_ciclo=30
                                        )
                                else:
                                    df.at[idx_os, 'pendencias'] = f"[PENDÊNCIA ATIVA - {novo_tec_exec}] {relatorio_com_peca}{resumo_diag} (ETAPA REALIZADA: {etapa_executada_fecho})"
                                    df.at[idx_os, 'status'] = 'ATIVO'
                                    df.at[idx_os, 'instrumento_necessario'] = inst_prox_visita.strip().upper()
                                
                                if salvar_dados_seguro(df):
                                    st.cache_data.clear()
                                    st.success("✅ Salvo com sucesso! Ordem de Serviço gravada e estoque atualizado!")
                                    st.rerun()

# ----------------------------------------------------
# ABA 6: GESTÃO DE PENDÊNCIAS (EXCLUSIVO PERFIL GESTOR)
# ----------------------------------------------------
elif acao == "🚨 Gestão de Pendências" and st.session_state.perfil == "Gestor":
    st.markdown("### 🚨 Painel Central de Pendências & Direcionamento de Técnicos (Modo Gestor)")
    st.info("Visão exclusiva da Gestão: acompanhe todas as pendências abertas e direcione-as rapidamente para o técnico disponível.")

    df_pend = df[df['status'].fillna('ATIVO').astype(str).str.upper() == 'ATIVO']
    if df_pend.empty:
        st.success("🎉 Sem pendências ativas no momento.")
    else:
        for idx_p, row_p in df_pend.iterrows():
            id_os_p = obter_id_os(idx_p, row_p)
            cli_p = limpar_texto(row_p.get('cliente'), 'N/D')
            eq_p = limpar_texto(row_p.get('equipamento'), 'N/D')
            tec_p = limpar_texto(row_p.get('tecnico_responsavel'), 'A DEFINIR')
            pend_p = limpar_texto(row_p.get('pendencias'), 'Sem descrição')
            inst_p = limpar_texto(row_p.get('instrumento_necessario'), 'Nenhum especificado')
            etapa_p = limpar_texto(row_p.get('etapa_preventiva'), 'Geral')

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 8px;">
                    <h4 style="margin: 0 0 5px 0; color: #64dfdf;">🏥 OS #{id_os_p} | {cli_p} — ⚙️ {eq_p}</h4>
                    <p style="margin: 4px 0;"><strong>Técnico Atual:</strong> {tec_p} | <strong>Etapa Preventiva:</strong> {etapa_p}</p>
                    <p style="margin: 4px 0;"><strong>Pendência:</strong> <span style="color: #fca5a5;">{pend_p}</span></p>
                    <p style="margin: 4px 0; color: #64dfdf;"><strong>📐 Instrumento / Material Requerido:</strong> {inst_p}</p>
                </div>
            """, unsafe_allow_html=True)

            with st.expander(f"👉 Direcionar / Mudar Técnico ou Instrumento da OS #{id_os_p} ({cli_p})"):
                with st.form(f"form_gestor_dir_{idx_p}"):
                    c_gd1, c_gd2 = st.columns(2)
                    lista_t_gestor = sorted(list(EQUIPA_TECNICA.keys()))
                    with c_gd1:
                        idx_tg = lista_t_gestor.index(tec_p.upper()) if tec_p.upper() in lista_t_gestor else 0
                        novo_t_dir = st.selectbox(
                            "Direcionar para o Técnico:",
                            lista_t_gestor,
                            index=idx_tg,
                            key=f"gd_tec_{idx_p}"
                        )
                        novo_inst_dir = st.text_input(
                            "Instrumento / Ferramenta Obrigatória:",
                            value="" if inst_p == "Nenhum especificado" else inst_p,
                            key=f"gd_inst_{idx_p}"
                        )
                    with c_gd2:
                        nova_desc_dir = st.text_input(
                            "Atualizar Instrução da Pendência:",
                            value=pend_p,
                            key=f"gd_desc_{idx_p}"
                        )
                        confirmar_dir = st.selectbox("Marcar como Confirmado na Escala?", ["SIM", "NÃO"], index=0, key=f"gd_conf_{idx_p}")

                    if st.form_submit_button("💾 Direcionar OS para o Técnico", type="primary"):
                        df.at[idx_p, 'tecnico_responsavel'] = novo_t_dir
                        df.at[idx_p, 'telefone_tecnico'] = EQUIPA_TECNICA.get(novo_t_dir, {}).get("tel", "")
                        df.at[idx_p, 'instrumento_necessario'] = novo_inst_dir.strip().upper()
                        df.at[idx_p, 'pendencias'] = nova_desc_dir.strip().upper()
                        df.at[idx_p, 'confirmado'] = confirmar_dir
                        if salvar_dados_seguro(df):
                            st.cache_data.clear()
                            st.success(f"✅ Pendência direcionada para {novo_t_dir} com sucesso!")
                            st.rerun()

# ----------------------------------------------------
# ABA 7: SOLICITAÇÃO DE PEÇAS & FERRAMENTAS (COM RESERVA ONLINE DE ESTOQUE)
# ----------------------------------------------------
elif acao == "📦 Solicitação de Peças & Ferramentas":
    st.markdown("### 📦 Formulário de Solicitação de Peças, Consumíveis e Instrumentos")
    st.info(
        "Marque os itens necessários para o atendimento. O sistema valida e reserva as quantidades "
        "online na base de dados em tempo real para impedir conflitos entre técnicos."
    )

    df_est_atual = carregar_estoque()
    lista_t_sol = sorted(list(EQUIPA_TECNICA.keys()))
    clientes_sol = sorted([c for c in df['cliente'].unique() if str(c).strip() != '' and "NENHUM" not in str(c).upper()])

    with st.form("form_solicitacao_almoxarifado"):
        c_sol1, c_sol2 = st.columns(2)
        with c_sol1:
            usr_sol_up = st.session_state.utilizador.upper()
            idx_sol_u = lista_t_sol.index(usr_sol_up) if usr_sol_up in lista_t_sol else 0
            tec_solicitante = st.selectbox("Técnico Solicitante", lista_t_sol, index=idx_sol_u)
        with c_sol2:
            cli_destino_sol = st.selectbox("Hospital / Cliente ou Setor de Destino", ["USO GERAL / VIATURA"] + clientes_sol)

        st.markdown("#### ☑️ Ticagem de Materiais e Peças Disponíveis em Estoque")
        itens_ticados = []
        if df_est_atual.empty:
            st.warning("Nenhum item registado no estoque.")
        else:
            for _, r_item in df_est_atual.iterrows():
                cod_i = r_item['codigo']
                nome_i = r_item['nome_peca']
                qtd_disp_i = limpar_int(r_item.get('quantidade'), 0)
                tipo_i = limpar_texto(r_item.get('tipo_item'), 'PEÇA COMERCIAL (OS)')

                c_it1, c_it2 = st.columns([3.5, 1])
                with c_it1:
                    marcado = st.checkbox(
                        f"[{cod_i}] {nome_i} — ({tipo_i}) | Saldo Online: {qtd_disp_i} un.",
                        disabled=(qtd_disp_i <= 0),
                        key=f"chk_item_{cod_i}"
                    )
                with c_it2:
                    qtd_ped = st.number_input(
                        "Qtd",
                        min_value=1,
                        max_value=max(1, qtd_disp_i),
                        value=1,
                        disabled=(qtd_disp_i <= 0),
                        key=f"num_item_{cod_i}"
                    )
                if marcado and qtd_disp_i > 0:
                    itens_ticados.append({"codigo": cod_i, "nome": nome_i, "qtd": int(qtd_ped)})

        instrumentos_extras_sol = st.text_area(
            "📐 Instrumentos de Medição / Ferramentas Especiais Solicitadas",
            placeholder="EX: ANALISADOR DE RAIOS-X, MULTÍMETRO FLUKE, MALA DE FERRAMENTAS 02..."
        )

        if st.form_submit_button("🚀 Confirmar Reserva no Estoque & Enviar ao Almoxarifado", type="primary"):
            if not itens_ticados and not instrumentos_extras_sol.strip():
                st.error("⚠️ Selecione pelo menos um material ou indique o instrumento necessário!")
            else:
                erro_conflito = None
                resumo_itens_str = "NENHUMA PEÇA DE ESTOQUE"
                data_ped_agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

                with get_db_connection(DB_NAME) as conn_res:
                    cur_res = conn_res.cursor()
                    for it in itens_ticados:
                        cur_res.execute("SELECT quantidade FROM estoque_pecas WHERE codigo = ?", (it['codigo'],))
                        linha_q = cur_res.fetchone()
                        saldo_real_agora = int(linha_q[0]) if linha_q else 0
                        if it['qtd'] > saldo_real_agora:
                            erro_conflito = (
                                f"⚠️ Conflito de Estoque Online! O item '{it['nome']}' possui apenas "
                                f"{saldo_real_agora} un. disponíveis (outro técnico acabou de reservar)."
                            )
                            break

                    if not erro_conflito:
                        if itens_ticados:
                            resumo_itens_str = ", ".join([f"{i['qtd']}x {i['nome']} ({i['codigo']})" for i in itens_ticados])
                        for it in itens_ticados:
                            cur_res.execute(
                                "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE codigo = ?",
                                (it['qtd'], it['codigo'])
                            )
                        cur_res.execute("""
                            INSERT INTO solicitacoes_pecas
                            (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            tec_solicitante, cli_destino_sol, resumo_itens_str,
                            instrumentos_extras_sol.strip().upper(),
                            "RESERVADO / ENVIADO AO ESTOQUE", data_ped_agora
                        ))

                if erro_conflito:
                    st.error(erro_conflito)
                else:
                    st.cache_data.clear()
                    inst_txt_msg = instrumentos_extras_sol.strip().upper() if instrumentos_extras_sol.strip() else 'NENHUM'
                    msg_almox = (
                        f"📦 *NOVA SOLICITAÇÃO DE MATERIAL & INSTRUMENTOS - EMED*\n\n"
                        f"👨‍🔧 *Técnico:* {tec_solicitante}\n"
                        f"🏥 *Destino:* {cli_destino_sol}\n"
                        f"📅 *Data/Hora:* {data_ped_agora}\n\n"
                        f"🛠️ *Materiais Reservados no Sistema:*\n{resumo_itens_str}\n\n"
                        f"📐 *Instrumentos Solicitados:*\n{inst_txt_msg}\n"
                    )
                    link_wpp_est = f"https://wa.me/558593333333?text={urllib.parse.quote(msg_almox)}"
                    st.success("✅ Estoque atualizado em tempo real! Os itens foram reservados para si.")
                    st.markdown(f"""
                        <a href="{link_wpp_est}" target="_blank" style="background:#25d366; color:white; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:8px;">
                            📲 Enviar Mensagem de Separação para o Estoque (WhatsApp)
                        </a>
                    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📋 Histórico Recente & Gestão Circular de Reservas do Almoxarifado")
    df_sol_hist = carregar_solicitacoes()
    st.dataframe(df_sol_hist, use_container_width=True, hide_index=True)

    if not df_sol_hist.empty:
        with st.expander("🔄 Gerir Status de Reserva (Confirmar Entrega / Aplicação ou Estornar Peças ao Estoque)"):
            with st.form("form_gestao_status_reserva"):
                opcoes_ped = [
                    f"#{r['id']} | {r['tecnico']} -> {r['destino_cliente']} ({r['itens_solicitados']}) [{r['status_pedido']}]"
                    for _, r in df_sol_hist.iterrows()
                ]
                ped_escolhido = st.selectbox("Selecione o Pedido de Reserva:", opcoes_ped)
                novo_st_ped = st.selectbox(
                    "Nova Situação do Pedido:",
                    [
                        "ENTREGUE / APLICADO EM CAMPO",
                        "CANCELADO / ESTORNADO (DEVOLVIDO AO ESTOQUE)",
                        "RESERVADO / ENVIADO AO ESTOQUE"
                    ]
                )
                if st.form_submit_button("💾 Atualizar Status da Reserva", type="primary"):
                    id_ped_alvo = int(ped_escolhido.split("|")[0].replace("#", "").strip())
                    ok_st, msg_st = atualizar_status_solicitacao_peca(DB_NAME, id_ped_alvo, novo_st_ped)
                    if ok_st:
                        st.cache_data.clear()
                        st.success(msg_st)
                        st.rerun()
                    else:
                        st.error(msg_st)

# ----------------------------------------------------
# ABA 8: MAPA & ROTEAMENTO
# ----------------------------------------------------
elif acao == "🗺️ Mapa & Planeamento de Rotas":
    st.markdown("### 🗺️ Mapa Operacional & Planeamento de Rotas")
    COORDINADAS_CIDADES = {
        "fortaleza": (-3.7172, -38.5433), "juazeiro": (-7.2009, -39.3148),
        "araripina": (-7.4811, -40.4994), "petrolina": (-9.3875, -40.5028),
        "taua": (-6.0044, -40.2934), "sobral": (-3.6895, -40.3486),
        "crato": (-7.2347, -39.4069), "eusebio": (-3.8856, -38.4614),
        "brasilia": (-15.7975, -47.8919), "iguatu": (-6.3594, -39.2986),
        "mossoro": (-5.1878, -37.3442), "catole": (-6.3439, -37.7467),
        "poranga": (-4.7450, -40.9256)
    }
    cores_hex = ["#64dfdf", "#f72585", "#7209b7", "#4cc9f0", "#ff9f1c", "#2ec4b6", "#e71d36", "#ffb703"]
    pontos_mapa = []
    clientes_ordenados = sorted([
        c for c in df['cliente'].unique()
        if str(c).strip() != '' and "NENHUM (AGUARDANDO" not in str(c).upper()
    ])

    for idx_c, cliente_nome in enumerate(clientes_ordenados):
        grupo = df[df['cliente'] == cliente_nome]
        primeira = grupo.iloc[0]
        cidade_str = str(primeira.get('cidade', '')).strip().lower()
        lat, lon = -3.7172, -38.5433
        for cid_key, coords in COORDINADAS_CIDADES.items():
            if cid_key in cidade_str:
                lat, lon = coords
                break
        pontos_mapa.append({
            'lat': lat, 'lon': lon, 'cliente': cliente_nome,
            'cidade': str(primeira.get('cidade', '')).upper(),
            'color': cores_hex[idx_c % len(cores_hex)]
        })

    clientes_selecionados_rota = st.multiselect("Selecione os clientes para a rota:", options=clientes_ordenados)
    if clientes_selecionados_rota:
        pts_filtrados = [p for p in pontos_mapa if p['cliente'] in clientes_selecionados_rota]
        st.map(pd.DataFrame(pts_filtrados), latitude="lat", longitude="lon", size=400, color="color", zoom=7)
        if len(pts_filtrados) >= 2:
            km_total = 0.0
            for i_r in range(len(pts_filtrados) - 1):
                km_total += calcular_distancia(
                    pts_filtrados[i_r]['lat'], pts_filtrados[i_r]['lon'],
                    pts_filtrados[i_r+1]['lat'], pts_filtrados[i_r+1]['lon']
                )
            st.info(f"🛣️ **Distância Estimada da Rota:** {km_total:.1f} KM | ⏱️ **Tempo Estimado de Deslocamento:** {formatar_tempo(km_total)}")
    else:
        st.map(pd.DataFrame(pontos_mapa), latitude="lat", longitude="lon", size=400, color="color", zoom=6)

# ----------------------------------------------------
# ABA 9: GESTÃO DE ESTOQUE & PEÇAS (PEÇAS COMERCIAIS + CONSUMÍVEIS INTERNOS)
# ----------------------------------------------------
elif acao == "📦 Gestão de Estoque & Peças":
    st.markdown("### 📦 Controlo do Almoxarifado, Peças Comerciais & Consumíveis Internos EMED")

    st.markdown("#### 📋 Listagem Geral de Peças e Consumíveis em Almoxarifado")
    df_est_view = carregar_estoque()
    if df_est_view.empty:
        st.info("Nenhuma peça registada no estoque.")
    else:
        df_est_mostra = df_est_view.copy()
        custo_num = pd.to_numeric(df_est_mostra['preco_custo'], errors='coerce').fillna(0.0)
        mc_num = pd.to_numeric(df_est_mostra['margem_contrato'], errors='coerce').fillna(30.0)
        ma_num = pd.to_numeric(df_est_mostra['margem_avulso'], errors='coerce').fillna(60.0)
        df_est_mostra['Preço Venda Contrato (R$)'] = (custo_num * (1 + mc_num / 100.0)).round(2)
        df_est_mostra['Preço Venda Avulso (R$)'] = (custo_num * (1 + ma_num / 100.0)).round(2)
        st.dataframe(df_est_mostra, use_container_width=True, hide_index=True)

    st.markdown("---")
    aba_est1, aba_est2 = st.tabs([
        "➕ Cadastrar / Editar Peça ou Consumível",
        "🔧 Dar Baixa de Consumível (Uso Interno / Sem Nota de Saída)"
    ])

    with aba_est1:
        if not df_est_view.empty:
            lista_pecas_fmt = (df_est_view['codigo'].astype(str) + " - " + df_est_view['nome_peca'].astype(str)).tolist()
            opcoes_pecas_ed = ["➕ CADASTRAR NOVO ITEM"] + lista_pecas_fmt
        else:
            opcoes_pecas_ed = ["➕ CADASTRAR NOVO ITEM"]

        escolha_peca_ed = st.selectbox("Selecione um Item para Editar/Somar Estoque ou Cadastre um Novo:", opcoes_pecas_ed)
        
        row_p_ed = None
        if escolha_peca_ed != "➕ CADASTRAR NOVO ITEM":
            cod_sel_ed = escolha_peca_ed.split(" - ")[0].strip()
            row_p_ed = df_est_view[df_est_view['codigo'] == cod_sel_ed].iloc[0]

        with st.form("form_novo_ou_editar_peca"):
            cp1, cp2 = st.columns(2)
            with cp1:
                cod_p = st.text_input(
                    "Código do Item *",
                    value=limpar_texto(row_p_ed['codigo']) if row_p_ed is not None else "",
                    placeholder="EX: PEC-005 ou CON-003"
                )
                nome_p = st.text_input(
                    "Nome / Descrição *",
                    value=limpar_texto(row_p_ed['nome_peca']) if row_p_ed is not None else "",
                    placeholder="EX: ESTABILIZADOR DE FILAMENTO ou ABRAÇADEIRA"
                )
                idx_cat_p = 0 if row_p_ed is None or "COMERCIAL" in str(row_p_ed.get('tipo_item', '')) else 1
                tipo_item_p = st.selectbox(
                    "Categoria do Item *",
                    ["PEÇA COMERCIAL (OS)", "CONSUMÍVEL INTERNO (USO DIÁRIO / SEM NF SAÍDA)", "INSTRUMENTO / FERRAMENTA"],
                    index=idx_cat_p
                )
            with cp2:
                qtd_p = st.number_input(
                    "Quantidade Total em Estoque *",
                    min_value=0,
                    value=limpar_int(row_p_ed['quantidade'], 1) if row_p_ed is not None else 1
                )
                custo_p = st.number_input(
                    "Preço de Custo Unitário (R$)",
                    min_value=0.0,
                    value=limpar_float(row_p_ed['preco_custo'], 100.0) if row_p_ed is not None else 100.0,
                    step=10.0
                )
                val_mc = limpar_float(row_p_ed.get('margem_contrato'), 30.0) if row_p_ed is not None else 30.0
                val_ma = limpar_float(row_p_ed.get('margem_avulso'), 60.0) if row_p_ed is not None else 60.0
                m_cont_p = st.number_input("Margem Contrato (%)", min_value=0.0, value=val_mc, step=5.0)
                m_avul_p = st.number_input("Margem Avulso (%)", min_value=0.0, value=val_ma, step=5.0)

            c_bp1, c_bp2 = st.columns(2)
            with c_bp1:
                btn_salvar_peca = st.form_submit_button("💾 Registar / Atualizar Item no Estoque", type="primary")
            with c_bp2:
                btn_excluir_peca = st.form_submit_button("🗑️ Excluir Item do Estoque")

            if btn_salvar_peca:
                if not cod_p.strip() or not nome_p.strip():
                    st.error("⚠️ Preencha o código e o nome do item!")
                else:
                    try:
                        with get_db_connection(DB_NAME) as conn_ip:
                            conn_ip.execute("""
                                INSERT OR REPLACE INTO estoque_pecas
                                (codigo, nome_peca, quantidade, preco_custo, margem_contrato, margem_avulso, tipo_item)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                cod_p.strip().upper(), nome_p.strip().upper(),
                                int(qtd_p), float(custo_p), float(m_cont_p), float(m_avul_p), tipo_item_p
                            ))
                        st.cache_data.clear()
                        st.success(f"✅ Item '{nome_p.strip().upper()}' guardado e tabela atualizada com sucesso!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao salvar item: {ex}")

            if btn_excluir_peca and row_p_ed is not None:
                with get_db_connection(DB_NAME) as conn_ip:
                    conn_ip.execute("DELETE FROM estoque_pecas WHERE codigo = ?", (row_p_ed['codigo'],))
                st.cache_data.clear()
                st.success("🗑️ Item excluído do estoque!")
                st.rerun()

    with aba_est2:
        st.markdown("##### 🔧 Baixa de Consumíveis para Manutenções do Dia a Dia ou Uso Interno na Empresa")
        st.caption("Utilize para dar saída em abraçadeiras, fitas isolantes, álcool isopropílico, parafusos, solda, etc., sem nota fiscal de saída.")
        if df_est_view.empty:
            st.info("Cadastre itens no estoque primeiro.")
        else:
            with st.form("form_baixa_consumivel"):
                cb1, cb2 = st.columns(2)
                with cb1:
                    opcoes_cons_lista = (
                        df_est_view['codigo'] + " - " + df_est_view['nome_peca']
                        + " (Saldo: " + df_est_view['quantidade'].astype(str) + ")"
                    ).tolist()
                    item_cons_sel = st.selectbox("Selecione o Consumível / Material", opcoes_cons_lista)
                    qtd_cons_baixa = st.number_input("Quantidade Consumida", min_value=1, value=1)
                with cb2:
                    setor_tec_cons = st.text_input("Técnico ou Setor que Utilizou *", value=st.session_state.utilizador)
                    finalidade_cons = st.text_input(
                        "Finalidade / Onde foi aplicado *",
                        placeholder="EX: ORGANIZAÇÃO DE CABOS EM INSTALAÇÃO / BANCADA INTERNA"
                    )

                if st.form_submit_button("📉 Confirmar Baixa por Consumo Interno", type="primary"):
                    cod_c_alvo = item_cons_sel.split(" - ")[0].strip()
                    row_c_alvo = df_est_view[df_est_view['codigo'] == cod_c_alvo].iloc[0]
                    if qtd_cons_baixa > limpar_int(row_c_alvo['quantidade'], 0):
                        st.error("⚠️ Quantidade superior ao saldo disponível em estoque!")
                    elif not finalidade_cons.strip():
                        st.error("⚠️ Informe a finalidade do consumo!")
                    else:
                        with get_db_connection(DB_NAME) as conn_bc:
                            conn_bc.execute(
                                "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE codigo = ?",
                                (int(qtd_cons_baixa), cod_c_alvo)
                            )
                            conn_bc.execute("""
                                INSERT INTO baixas_consumiveis
                                (tecnico_setor, codigo_item, nome_item, quantidade, finalidade, data_baixa)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                setor_tec_cons.strip().upper(), cod_c_alvo, row_c_alvo['nome_peca'],
                                int(qtd_cons_baixa), finalidade_cons.strip().upper(),
                                datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                            ))
                        st.cache_data.clear()
                        st.success("✅ Baixa de consumível registada com sucesso!")
                        st.rerun()

        st.markdown("###### 📜 Histórico de Consumo Interno")
        st.dataframe(carregar_baixas_consumiveis(), use_container_width=True, hide_index=True)

# ----------------------------------------------------
# ABA 10: GESTÃO & ADMINISTRAÇÃO (TÉCNICOS E VEÍCULOS COMPLETOS)
# ----------------------------------------------------
elif acao == "⚙️ Gestão & Administração" and st.session_state.perfil == "Gestor":
    st.markdown("### ⚙️ Painel de Gestão & Administração")
    sub_gestao = st.radio(
        "Selecione o módulo:",
        ["👷 Gestão de Técnicos", "🚗 Gestão de Veículos & Quilometragem"],
        horizontal=True
    )
    st.markdown("---")

    if sub_gestao == "👷 Gestão de Técnicos":
        st.markdown("#### 📋 Equipa Técnica Registada")
        df_tecs_adm = carregar_tecnicos()
        st.dataframe(df_tecs_adm, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        if "abrir_painel_tecnico" not in st.session_state:
            st.session_state.abrir_painel_tecnico = False

        if st.button("➕ Adicionar / Editar ou Excluir Técnico"):
            st.session_state.abrir_painel_tecnico = not st.session_state.abrir_painel_tecnico
            st.rerun()

        if st.session_state.abrir_painel_tecnico:
            st.markdown("#### ✍️ Cadastro e Edição de Técnico")
            lista_nomes_adm = df_tecs_adm['nome'].tolist() if not df_tecs_adm.empty else []
            opcoes_tec_edicao = ["➕ CADASTRAR NOVO TÉCNICO"] + lista_nomes_adm
            tec_escolhido_edicao = st.selectbox(
                "Selecione o Técnico que deseja Editar (ou escolha '➕ CADASTRAR NOVO TÉCNICO'):",
                opcoes_tec_edicao
            )

            dados_tec_ed = None
            if tec_escolhido_edicao != "➕ CADASTRAR NOVO TÉCNICO":
                dados_tec_ed = df_tecs_adm[df_tecs_adm['nome'] == tec_escolhido_edicao].iloc[0]

            with st.form("form_cad_ed_tecnico"):
                ct1, ct2 = st.columns(2)
                with ct1:
                    t_nome = st.text_input(
                        "Nome do Técnico *",
                        value=limpar_texto(dados_tec_ed['nome']) if dados_tec_ed is not None else ""
                    ).upper()
                    t_tel = st.text_input(
                        "Telemóvel / WhatsApp (ex: 5585988888888)",
                        value=limpar_texto(dados_tec_ed['telefone']) if dados_tec_ed is not None else ""
                    )
                    t_partida = st.text_input(
                        "Local de Partida",
                        value=limpar_texto(dados_tec_ed['partida']) if dados_tec_ed is not None else "FORTALEZA"
                    )
                with ct2:
                    t_sede = st.text_input(
                        "Sede / Base",
                        value=limpar_texto(dados_tec_ed['sede']) if dados_tec_ed is not None else "FORTALEZA"
                    )
                    t_senha = st.text_input(
                        "Palavra-passe / PIN",
                        type="password",
                        value=limpar_texto(dados_tec_ed['senha'], "1234") if dados_tec_ed is not None else "1234"
                    )
                    perf_atual = limpar_texto(dados_tec_ed['perfil'], "Técnico") if dados_tec_ed is not None else "Técnico"
                    t_perfil = st.selectbox(
                        "Perfil de Acesso",
                        ["Técnico", "Gestor"],
                        index=1 if perf_atual == "Gestor" else 0
                    )
                
                ass_val_def = limpar_texto(dados_tec_ed.get('assinatura_padrao', ''), f"{t_nome} - CFT") if dados_tec_ed is not None else ""
                t_assinatura = st.text_input("Assinatura Padrão / Registo CFT (Carimbo Automático na OS)", value=ass_val_def)
                t_rubrica_up = st.file_uploader("✍️ Anexar Imagem da Rubrica do Técnico (PNG/JPG - Opcional)", type=["png", "jpg", "jpeg"])

                c_bt1, c_bt2, c_bt3 = st.columns(3)
                with c_bt1:
                    btn_guardar_t = st.form_submit_button("💾 Guardar Técnico", type="primary")
                with c_bt2:
                    btn_excluir_t = st.form_submit_button("🗑️ Excluir Técnico Selecionado")
                with c_bt3:
                    btn_fechar_t = st.form_submit_button("❌ Fechar Formulário")

                if btn_guardar_t:
                    if not t_nome.strip():
                        st.error("⚠️ O nome do técnico é obrigatório!")
                    else:
                        caminho_rub_tec = limpar_texto(dados_tec_ed.get('rubrica_img', '')) if dados_tec_ed is not None else ""
                        if t_rubrica_up is not None:
                            pasta_rub = os.path.join(BASE_DIR, "uploads_os")
                            os.makedirs(pasta_rub, exist_ok=True)
                            caminho_rub_tec = os.path.join(pasta_rub, f"RUBRICA_{t_nome.strip().upper()}_{t_rubrica_up.name}")
                            with open(caminho_rub_tec, "wb") as f:
                                f.write(t_rubrica_up.getbuffer())

                        ass_final_t = t_assinatura.strip().upper() or f"{t_nome.strip().upper()} - CFT"
                        with get_db_connection(DB_NAME) as conn_t:
                            cur_t = conn_t.cursor()
                            if dados_tec_ed is not None and dados_tec_ed['nome'] != t_nome.strip().upper():
                                cur_t.execute("DELETE FROM tecnicos WHERE nome = ?", (dados_tec_ed['nome'],))
                            cur_t.execute("""
                                INSERT OR REPLACE INTO tecnicos
                                (nome, telefone, partida, sede, senha, perfil, assinatura_padrao, rubrica_img)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                t_nome.strip().upper(), t_tel.strip(),
                                t_partida.strip().upper(), t_sede.strip().upper(),
                                t_senha.strip(), t_perfil, ass_final_t, caminho_rub_tec
                            ))
                        st.cache_data.clear()
                        st.session_state.abrir_painel_tecnico = False
                        st.success(f"✅ Salvo com sucesso! Técnico '{t_nome.strip().upper()}' e rubrica guardados!")
                        st.rerun()

                if btn_excluir_t and dados_tec_ed is not None:
                    with get_db_connection(DB_NAME) as conn_t:
                        conn_t.execute("DELETE FROM tecnicos WHERE nome = ?", (dados_tec_ed['nome'],))
                    st.cache_data.clear()
                    st.success(f"🗑️ Técnico '{dados_tec_ed['nome']}' excluído com sucesso!")
                    st.rerun()

                if btn_fechar_t:
                    st.session_state.abrir_painel_tecnico = False
                    st.rerun()

    elif sub_gestao == "🚗 Gestão de Veículos & Quilometragem":
        st.markdown("#### 🚗 Frota de Veículos EMED, Fotos & Registos de Manutenção")
        df_v_list = carregar_veiculos()
        st.dataframe(df_v_list, use_container_width=True, hide_index=True)

        if not df_v_list.empty:
            cols_v_cards = st.columns(2)
            for idx_vc, r_vc in df_v_list.iterrows():
                with cols_v_cards[idx_vc % 2]:
                    km_at_v = limpar_int(r_vc.get('km_atual'), 0)
                    km_ul_v = limpar_int(r_vc.get('km_ultima_revisao'), 0)
                    km_pr_v = limpar_int(r_vc.get('km_proxima_revisao'), 50000)
                    alerta_rev = "🚨 REVISÃO VENCIDA / URGENTE" if km_at_v >= km_pr_v else f"🟢 Faltam {km_pr_v - km_at_v} KM p/ revisão"
                    mod_v_lbl = limpar_texto(r_vc.get('modelo'))
                    plc_v_lbl = limpar_texto(r_vc.get('placa'))
                    st_v_lbl = limpar_texto(r_vc.get('status_manutencao'), 'Disponível')
                    hm_v_lbl = limpar_texto(r_vc.get('historico_manutencao'), 'Sem registos')
                    pm_v_lbl = limpar_texto(r_vc.get('proximas_manutencoes'), 'Revisão periódica padrão')

                    st.markdown(f"""
                        <div class="client-card">
                            <h3>🚗 {mod_v_lbl} — Placa: {plc_v_lbl}</h3>
                            <p>🛣️ <strong>KM Atual:</strong> {km_at_v:,} KM | <strong>Última Revisão:</strong> {km_ul_v:,} KM</p>
                            <p>🔔 <strong>Próxima Revisão ({km_pr_v:,} KM):</strong> {alerta_rev}</p>
                            <p>🛠️ <strong>Status:</strong> {st_v_lbl}</p>
                            <p>📋 <strong>Histórico de Manutenções:</strong> {hm_v_lbl}</p>
                            <p>📅 <strong>Próximas Manutenções Programadas:</strong> {pm_v_lbl}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    caminho_foto_v = limpar_texto(r_vc.get('foto_carro'), '')
                    if caminho_foto_v and os.path.exists(caminho_foto_v):
                        st.image(caminho_foto_v, caption=f"{mod_v_lbl} ({plc_v_lbl})", width=280)

        st.markdown("---")

        if "abrir_painel_veiculo" not in st.session_state:
            st.session_state.abrir_painel_veiculo = False

        if st.button("➕ Adicionar / Editar ou Excluir Veículo"):
            st.session_state.abrir_painel_veiculo = not st.session_state.abrir_painel_veiculo
            st.rerun()

        if st.session_state.abrir_painel_veiculo:
            st.markdown("#### ✍️ Registo Completo de Veículo, Fotos e Manutenções")
            if not df_v_list.empty:
                lista_veic_fmt = (df_v_list['modelo'] + " (" + df_v_list['placa'] + ")").tolist()
                opcoes_veic_ed = ["➕ CADASTRAR NOVO VEÍCULO"] + lista_veic_fmt
            else:
                opcoes_veic_ed = ["➕ CADASTRAR NOVO VEÍCULO"]

            veiculo_escolhido_ed = st.selectbox(
                "Selecione o Veículo para Editar/Excluir (ou '➕ CADASTRAR NOVO VEÍCULO'):",
                opcoes_veic_ed
            )

            v_atual_row = None
            if veiculo_escolhido_ed != "➕ CADASTRAR NOVO VEÍCULO":
                placa_sel = veiculo_escolhido_ed.split("(")[-1].replace(")", "").strip()
                v_atual_row = df_v_list[df_v_list['placa'] == placa_sel].iloc[0]

            with st.form("form_gestao_frota_completa"):
                cv1, cv2 = st.columns(2)
                with cv1:
                    v_mod = st.text_input(
                        "Modelo do Veículo *",
                        value=limpar_texto(v_atual_row['modelo']) if v_atual_row is not None else "",
                        placeholder="EX: RENAULT CAPTUR 1.6 16V SCE"
                    )
                    v_plc = st.text_input(
                        "Placa *",
                        value=limpar_texto(v_atual_row['placa']) if v_atual_row is not None else "",
                        placeholder="EX: EMD-2026"
                    )
                    val_km_at = limpar_int(v_atual_row['km_atual'], 45000) if v_atual_row is not None else 45000
                    v_km_at = st.number_input("Quilometragem Atual (KM)", min_value=0, value=val_km_at, step=100)
                    v_status_m = st.selectbox(
                        "Status Operacional",
                        ["Disponível", "Em Viagem / Campo", "Em Revisão / Oficina", "Indisponível"],
                        index=0
                    )
                with cv2:
                    val_km_ul = limpar_int(v_atual_row.get('km_ultima_revisao'), 40000) if v_atual_row is not None else 40000
                    val_km_pr = limpar_int(v_atual_row.get('km_proxima_revisao'), 50000) if v_atual_row is not None else 50000
                    v_km_ult = st.number_input("KM da Última Revisão", min_value=0, value=val_km_ul, step=500)
                    v_km_prox = st.number_input("KM da Próxima Revisão", min_value=0, value=val_km_pr, step=500)
                    v_foto_up = st.file_uploader("📸 Anexar / Atualizar Foto do Carro (PNG/JPG)", type=["png", "jpg", "jpeg"])

                v_hist_manut = st.text_area(
                    "🔧 Registo de Manutenções Realizadas (Peças trocadas, datas, oficina/mecânico)",
                    value=limpar_texto(v_atual_row.get('historico_manutencao', '')) if v_atual_row is not None else "",
                    placeholder="EX: 10/2026 - TROCA DE ÓLEO, FILTROS, VELAS E CORREIA COM MECÂNICO CÍCERO..."
                )
                v_prox_manut = st.text_area(
                    "📅 Próximas Manutenções Programadas / Alertas da Viatura",
                    value=limpar_texto(v_atual_row.get('proximas_manutencoes', '')) if v_atual_row is not None else "",
                    placeholder="EX: VERIFICAR PASTILHAS DE TRAVÃO E ALINHAMENTO AOS 50.000 KM..."
                )

                cbv1, cbv2, cbv3 = st.columns(3)
                with cbv1:
                    btn_salvar_v = st.form_submit_button("💾 Guardar Dados do Veículo", type="primary")
                with cbv2:
                    btn_excluir_v = st.form_submit_button("🗑️ Excluir Veículo da Frota")
                with cbv3:
                    btn_fechar_v = st.form_submit_button("❌ Fechar Formulário")

                if btn_salvar_v:
                    if not v_mod.strip() or not v_plc.strip():
                        st.error("⚠️ O Modelo e a Placa do veículo são obrigatórios!")
                    else:
                        caminho_foto_carro = limpar_texto(v_atual_row.get('foto_carro', '')) if v_atual_row is not None else ""
                        if v_foto_up is not None:
                            pasta_veiculos = os.path.join(BASE_DIR, "uploads_veiculos")
                            os.makedirs(pasta_veiculos, exist_ok=True)
                            caminho_foto_carro = os.path.join(pasta_veiculos, f"{v_plc.strip().upper()}_{v_foto_up.name}")
                            with open(caminho_foto_carro, "wb") as f:
                                f.write(v_foto_up.getbuffer())

                        with get_db_connection(DB_NAME) as conn_up:
                            cur_up = conn_up.cursor()
                            if v_atual_row is not None and v_atual_row['placa'] != v_plc.strip().upper():
                                cur_up.execute("DELETE FROM veiculos WHERE placa = ?", (v_atual_row['placa'],))
                            cur_up.execute("""
                                INSERT OR REPLACE INTO veiculos
                                (modelo, placa, km_atual, km_ultima_revisao, km_proxima_revisao, status_manutencao, foto_carro, historico_manutencao, proximas_manutencoes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                v_mod.strip().upper(), v_plc.strip().upper(),
                                int(v_km_at), int(v_km_ult), int(v_km_prox),
                                v_status_m, caminho_foto_carro,
                                v_hist_manut.strip().upper(), v_prox_manut.strip().upper()
                            ))
                        st.cache_data.clear()
                        st.success(f"✅ Veículo '{v_mod.strip().upper()} ({v_plc.strip().upper()})' guardado com sucesso!")
                        st.rerun()

                if btn_excluir_v and v_atual_row is not None:
                    with get_db_connection(DB_NAME) as conn_del_v:
                        conn_del_v.execute("DELETE FROM veiculos WHERE placa = ?", (v_atual_row['placa'],))
                    st.cache_data.clear()
                    st.success(f"🗑️ Veículo '{v_atual_row['placa']}' removido da frota!")
                    st.rerun()

                if btn_fechar_v:
                    st.session_state.abrir_painel_veiculo = False
                    st.rerun()

# ----------------------------------------------------
# ABA 11: ATUALIZAR QUILOMETRAGEM (OPCIONAL)
# ----------------------------------------------------
elif acao == "🚗 Atualizar Quilometragem (Opcional)" and st.session_state.perfil == "Gestor":
    st.markdown("### 🚗 Registo Rápido de Quilometragem")
    df_v = carregar_veiculos()
    if not df_v.empty:
        with st.form("form_km_opcional"):
            v_sel = st.selectbox("Veículo", df_v['modelo'] + " (" + df_v['placa'] + ")")
            km_inf = st.number_input("KM Atual", min_value=0, value=limpar_int(df_v.iloc[0]['km_atual'], 45000), step=100)
            if st.form_submit_button("🔄 Atualizar KM", type="primary"):
                placa_ext = v_sel.split("(")[-1].replace(")", "").strip()
                with get_db_connection(DB_NAME) as conn_k:
                    conn_k.execute("UPDATE veiculos SET km_atual = ? WHERE placa = ?", (int(km_inf), placa_ext))
                st.cache_data.clear()
                st.success("✅ Quilometragem atualizada com sucesso!")
                st.rerun()

# ----------------------------------------------------
# ABA 12: EDITOR DIRETO DA PLANILHA
# ----------------------------------------------------
elif acao == "📝 Editor Direto da Planilha" and st.session_state.perfil == "Gestor":
    st.markdown("### 📝 Edição de Dados em Tempo Real")
    df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar Alterações na Base", type="primary"):
        if salvar_dados_seguro(df_editado):
            st.cache_data.clear()
            st.success("✅ Alterações gravadas com sucesso!")
            st.rerun()

# === FIM DO ARQUIVO COMPLETO EMED ===