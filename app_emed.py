import os
import pandas as pd
import streamlit as st
from emed_core import normalizar_dataframe_os
from emed_services import (
    AppContext,
    BASE_DIR,
    DB_NAME,
    CAMINHO_EXCEL,
    init_db,
    carregar_dados,
    carregar_tecnicos,
    carregar_veiculos,
    carregar_estoque,
    carregar_clientes_internos,
    carregar_solicitacoes,
    carregar_baixas_consumiveis,
    montar_equipa_tecnica,
    salvar_dados_seguro,
)
from emed_ui import inject_custom_css, renderizar_area_trabalho_icones
from emed_views import verificar_e_renderizar_portal_qr, VIEW_ROUTER

# Configuração da Página do Sistema EMED com Tema Escuro Nativo
st.set_page_config(
    page_title="EMED - Gestão de Equipamentos e Frota",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Camada de Apresentação: Tema Escuro, Puxador Vertical Mobile e Blindagem CSS BaseWeb
inject_custom_css()

# Camada de Persistência: Inicialização e Carregamento Cacheado
init_db(DB_NAME, CAMINHO_EXCEL)

hoje = pd.Timestamp.today().normalize()
df = normalizar_dataframe_os(carregar_dados(DB_NAME))
df_tecnicos = carregar_tecnicos(DB_NAME)
df_veiculos = carregar_veiculos(DB_NAME)
df_estoque = carregar_estoque(DB_NAME)
df_internos = carregar_clientes_internos(DB_NAME)
EQUIPA_TECNICA = montar_equipa_tecnica(df_tecnicos)

# Inicialização de Sessão e Autenticação RBAC
if "autenticado" not in st.session_state:
    st.session_state.autenticado = True
    st.session_state.utilizador = "NETTO"
    st.session_state.perfil = "Gestor"

ctx = AppContext(
    base_dir=BASE_DIR,
    db_name=DB_NAME,
    caminho_excel=CAMINHO_EXCEL,
    hoje=hoje,
    usuario_atual=st.session_state.get("utilizador", "NETTO"),
    perfil_atual=st.session_state.get("perfil", "Gestor"),
    df=df,
    df_tecnicos=df_tecnicos,
    df_veiculos=df_veiculos,
    df_estoque=df_estoque,
    df_internos=df_internos,
    equipa_tecnica=EQUIPA_TECNICA,
)

# Interceptador do Portal Externo de QR Code (para execução caso ?equipamento_qr= esteja ativo)
verificar_e_renderizar_portal_qr(ctx)

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

# Barra Lateral e Navegação Modular
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

# Hook de Plugabilidade para o Módulo Fiscal Desacoplado (emed_fiscal.py)
try:
    from emed_fiscal import render_modulo_fiscal
    VIEW_ROUTER["🧾 Faturamento & Notas Fiscais"] = lambda c: render_modulo_fiscal(
        c.db_name, c.usuario_atual, c.perfil_atual
    )
    if "🧾 Faturamento & Notas Fiscais" not in opcoes_menu:
        opcoes_menu.insert(4, "🧾 Faturamento & Notas Fiscais")
except ImportError:
    pass

if "menu_acao_ativa" not in st.session_state or st.session_state.menu_acao_ativa not in opcoes_menu:
    st.session_state.menu_acao_ativa = opcoes_menu[0]

if "radio_menu_sidebar" not in st.session_state or st.session_state.radio_menu_sidebar not in opcoes_menu:
    st.session_state.radio_menu_sidebar = st.session_state.menu_acao_ativa


def _ao_mudar_sidebar():
    st.session_state.menu_acao_ativa = st.session_state.radio_menu_sidebar


acao = st.sidebar.radio(
    "Menu:",
    opcoes_menu,
    key="radio_menu_sidebar",
    on_change=_ao_mudar_sidebar,
)
st.session_state.menu_acao_ativa = acao

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

# Cabeçalho Principal com Logo Ampliada e Centralizada
col1, col_logo, col3 = st.columns([0.5, 5.0, 0.5])
with col_logo:
    caminho_logo = os.path.join(BASE_DIR, "emed1.jpg")
    if os.path.exists(caminho_logo):
        st.image(caminho_logo, use_container_width=True)
    elif os.path.exists("emed1.jpg"):
        st.image("emed1.jpg", use_container_width=True)

# Grade de Ícones Estilo Área de Trabalho do Windows (Navegação 1-Toque para Celular e PC)
renderizar_area_trabalho_icones(opcoes_menu, acao, st.session_state.perfil)

st.markdown(
    "<hr style='border: 0; border-top: 1px solid #3a506b; margin-top: 10px; margin-bottom: 20px;'>",
    unsafe_allow_html=True
)

# Roteador O(1) de Views Desacopladas
render_view = VIEW_ROUTER.get(acao)
if render_view:
    render_view(ctx)