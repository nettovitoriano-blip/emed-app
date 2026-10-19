import os
import importlib
import pandas as pd
import streamlit as st
import emed_core as _emed_core
importlib.reload(_emed_core)
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
import emed_ui.styles as _ui_styles
import emed_ui.components as _ui_comp
import emed_views.chamados_os as _vw_os
import emed_views.manuais_tecnicos as _vw_manuais
import emed_views as _vw_all
importlib.reload(_ui_styles)
importlib.reload(_ui_comp)
importlib.reload(_vw_os)
importlib.reload(_vw_manuais)
importlib.reload(_vw_all)
from emed_ui.styles import inject_custom_css
from emed_ui.components import renderizar_area_trabalho_icones
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
if st.sidebar.button(
    "◀️",
    key="btn_sidebar_esconder_interno",
    type="tertiary",
    help="Esconder Aba Lateral Esquerda",
):
    st.session_state.aba_lateral_oculta = True
    st.rerun()

st.sidebar.markdown(f"### 👤 Utilizador: {st.session_state.utilizador}")
st.sidebar.markdown(f"**Perfil:** `{st.session_state.perfil}`")

if st.sidebar.button("🔄 Trocar de Técnico / Sair", type="secondary", use_container_width=True):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### PAINEL DE OPERAÇÕES")

opcoes_menu = [
    "📊 Mural & Despacho WhatsApp",
    "📋 Minhas Pendências (Técnico)",
    "📚 Manuais & Procedimentos",
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

if "nav_sync_id" not in st.session_state:
    st.session_state.nav_sync_id = 0

if "menu_acao_ativa" not in st.session_state or st.session_state.menu_acao_ativa not in opcoes_menu:
    st.session_state.menu_acao_ativa = opcoes_menu[0]

chave_radio_atual = f"radio_menu_sidebar_{st.session_state.nav_sync_id}"
idx_menu_atual = opcoes_menu.index(st.session_state.menu_acao_ativa)


def _ao_mudar_sidebar():
    novo_valor = st.session_state.get(chave_radio_atual)
    if novo_valor in opcoes_menu:
        st.session_state.menu_acao_ativa = novo_valor


acao_sidebar = st.sidebar.radio(
    "Menu:",
    opcoes_menu,
    index=idx_menu_atual,
    key=chave_radio_atual,
    on_change=_ao_mudar_sidebar,
)
if acao_sidebar != st.session_state.menu_acao_ativa:
    st.session_state.menu_acao_ativa = acao_sidebar

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

with st.sidebar.expander("📱 Conectar Celular (QR Code)"):
    st.markdown("**Acesso 4G / 5G:**")
    caminho_qr = os.path.join(BASE_DIR, "qrcode_mobile_4g.png")
    if os.path.exists(caminho_qr):
        st.image(caminho_qr, caption="Aponte a câmera do celular")
    st.markdown("[🌐 Abrir link](https://fashion-spending-earned-medium.trycloudflare.com)")
    st.caption("Disponível via Cloudflare Tunnel")

# Cabeçalho Principal com Logo Ampliada e Centralizada
col1, col_logo, col3 = st.columns([0.5, 5.0, 0.5])
with col_logo:
    caminho_logo = os.path.join(BASE_DIR, "emed1.jpg")
    if os.path.exists(caminho_logo):
        st.image(caminho_logo, use_container_width=True)
    elif os.path.exists("emed1.jpg"):
        st.image("emed1.jpg", use_container_width=True)

# Grade de Ícones Estilo Área de Trabalho do Windows (Navegação 1-Toque e Edição por Utilizador)
renderizar_area_trabalho_icones(
    opcoes_menu,
    st.session_state.menu_acao_ativa,
    st.session_state.perfil,
    usuario_atual=st.session_state.utilizador,
    db_name=DB_NAME,
)

acao = st.session_state.menu_acao_ativa

st.markdown(
    f"""
    <div style="background: linear-gradient(90deg, #1c2541 0%, #0b132b 100%); border-left: 4px solid #64dfdf; border-top: 1px solid #3a506b; border-right: 1px solid #3a506b; border-bottom: 1px solid #3a506b; border-radius: 8px; padding: 8px 14px; margin-top: 6px; margin-bottom: 18px; display: flex; align-items: center; justify-content: space-between;">
        <span style="color: #64dfdf !important; font-weight: 700; font-size: 14px;">📍 MÓDULO EM EXIBIÇÃO: <span style="color: #ffffff !important;">{acao}</span></span>
        <span style="color: #94a3b8 !important; font-size: 12px;">👤 {st.session_state.utilizador} ({st.session_state.perfil})</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Roteador O(1) de Views Desacopladas
render_view = VIEW_ROUTER.get(acao)
if render_view:
    render_view(ctx)