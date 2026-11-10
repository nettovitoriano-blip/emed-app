# app_emed.py
"""Streamlit UI for EMED Fiscal / EMED Nota.

Painel Oficial de Faturamento, Emissão de Notas Fiscais e Gestão Tributária
da EMED Eletromedicina.

Perfis:
- Diretoria & Controladoria (netto, vitor) - Acesso irrestrito
- Faturamento & Emissão Fiscal (faturamento)
- Financeiro & Contabilidade (financeiro)
"""

import json
import re
import urllib.parse
import time
import uuid
import base64
from pathlib import Path
from io import BytesIO
import streamlit as st
import qrcode

# Import do módulo fiscal completo da EMED
try:
    from emed_fiscal import render_modulo_fiscal, FiscalManager, CertificadoManager
except Exception as e:
    render_modulo_fiscal = None

ASSETS_DIR = Path(__file__).parent / "assets"
BLUE_ICON_PATH = ASSETS_DIR / "icone_fiscal_azul.png"

# Configurações de página Streamlit
st.set_page_config(
    page_title="EMED Fiscal – Faturamento & NFS-e",
    page_icon=str(BLUE_ICON_PATH) if BLUE_ICON_PATH.is_file() else "🧾",
    layout="wide"
)

# Configurações de arquivos
USERS_FILE = Path(__file__).parent / "users.json"
CONFIG_FILE = Path(__file__).parent / "config.json"
DEVICES_FILE = Path(__file__).parent / "devices.json"
DB_PATH = Path(__file__).parent / "emed.db"

def safe_rerun():
    """Rerun compatível com Streamlit moderno e versões legadas."""
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

def safe_clear_query_params():
    """Limpa a query string da URL para evitar loops de autenticação."""
    try:
        if hasattr(st, "query_params"):
            st.query_params.clear()
        elif hasattr(st, "experimental_set_query_params"):
            st.experimental_set_query_params()
    except Exception:
        pass

def load_json(file_path: Path, default):
    """Carrega JSON de file_path ou cria com default se não existir."""
    if file_path.is_file():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    file_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

# Perfis formais da Área Fiscal & Financeira
DEFAULT_USERS = [
    {"username": "netto", "password": "12345", "role": "admin", "cargo": "Diretoria & Controladoria"},
    {"username": "vitor", "password": "12345", "role": "admin", "cargo": "Diretoria & Gestão Geral"},
    {"username": "faturamento", "password": "123", "role": "faturamento", "cargo": "Faturamento & Emissão Fiscal"},
    {"username": "financeiro", "password": "123", "role": "financeiro", "cargo": "Financeiro & Contabilidade"}
]
USERS = load_json(USERS_FILE, DEFAULT_USERS)

DEFAULT_CONFIG = {
    "youtube_id": "abc123XYZ",
    "cron_expression": "0 6 * * *",
    "admin_users": ["vitor", "netto", "admin"]
}
CONFIG = load_json(CONFIG_FILE, DEFAULT_CONFIG)


def get_image_base64(path: Path) -> str:
    """Retorna a string base64 de uma imagem."""
    if path.is_file():
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    return ""


def get_logo_path():
    """Busca o melhor arquivo de logo disponível para exibição."""
    candidates = [
        ASSETS_DIR / "emed_logo_user_dark.png",
        ASSETS_DIR / "emed_logo.png",
        ASSETS_DIR / "emed_logo_oficial.png",
        Path(__file__).parent / "emed_logo_user_dark.png",
        Path(__file__).parent / "emed_logo_oficial.png",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def authenticate():
    """Exibe formulário de login estilizado com logo e o ícone fiscal azul da EMED."""
    if st.session_state.get("authenticated"):
        return True

    logo_path = get_logo_path()
    blue_icon_b64 = get_image_base64(BLUE_ICON_PATH)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if logo_path:
            st.image(logo_path, use_container_width=True)
            
        icon_html = f'<img src="data:image/png;base64,{blue_icon_b64}" width="42" height="42" style="vertical-align: middle; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));" />' if blue_icon_b64 else '🧾'
        
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 5px; margin-bottom: 2px;">
                {icon_html}
                <span style="color: #38bdf8; font-size: 24px; font-weight: 700; letter-spacing: -0.3px;">
                    EMED Fiscal • Módulo NF
                </span>
            </div>
            <p style="text-align: center; font-size: 13px; color: #94a3b8; margin-bottom: 24px;">
                Portal de Faturamento, Emissão de Notas & Gestão Tributária
            </p>
            """,
            unsafe_allow_html=True
        )

    user = st.text_input("Usuário", placeholder="Digite seu usuário (ex: netto, vitor ou faturamento)")
    pwd = st.text_input("Senha", type="password", placeholder="Digite sua senha")
    
    if st.button("Entrar", use_container_width=True):
        username_clean = user.strip().lower()
        matched = next(
            (u for u in USERS if u["username"].strip().lower() == username_clean and u["password"] == pwd),
            None
        )
        if matched:
            st.session_state["authenticated"] = True
            st.session_state["username"] = matched["username"]
            st.session_state["role"] = matched["role"]
            st.session_state["cargo"] = matched.get("cargo", "Colaborador")
            safe_clear_query_params()
            safe_rerun()
        else:
            st.error("Credenciais inválidas. Verifique o usuário e senha informados.")
    return False


def is_admin() -> bool:
    """Retorna True se o usuário logado for admin ou estiver na lista admin_users."""
    current_user = str(st.session_state.get("username", "")).strip().lower()
    admins_config = [str(a).strip().lower() for a in CONFIG.get("admin_users", [])]
    return (
        st.session_state.get("role") == "admin" or
        current_user in admins_config
    )


# Token QR (login automático autorizado) – validade 30 min
def get_query_params():
    try:
        if hasattr(st, "query_params"):
            return dict(st.query_params)
        elif hasattr(st, "experimental_get_query_params"):
            return st.experimental_get_query_params()
    except Exception:
        pass
    import urllib.parse
    qs = st.experimental_get_query_string() if hasattr(st, "experimental_get_query_string") else ""
    return urllib.parse.parse_qs(qs)

query_params = get_query_params()
token_val = query_params.get("token")
if token_val and not st.session_state.get("authenticated"):
    if isinstance(token_val, list):
        token_val = token_val[0]
    try:
        decoded = base64.urlsafe_b64decode(str(token_val).encode()).decode()
        data = json.loads(decoded)
        username = data.get("username")
        ts = data.get("ts")
        if time.time() - ts > 1800:
            st.error("Token expirado (validade de 30 minutos excedida).")
        else:
            user_obj = next((u for u in USERS if u["username"].lower() == str(username).lower()), None)
            if user_obj:
                st.session_state["authenticated"] = True
                st.session_state["username"] = user_obj["username"]
                st.session_state["role"] = user_obj["role"]
                st.session_state["cargo"] = user_obj.get("cargo", "Colaborador")
                devices = load_json(DEVICES_FILE, {})
                device_id = data.get("device_id") or uuid.uuid4().hex
                devices.setdefault(username, []).append(device_id)
                devices[username] = list(set(devices[username]))
                DEVICES_FILE.write_text(json.dumps(devices, indent=2), encoding="utf-8")
                st.success(f"Dispositivo móvel autorizado com sucesso! (ID: {device_id}).")
                safe_clear_query_params()
                safe_rerun()
    except Exception as e:
        st.error(f"Erro ao validar token de acesso: {e}")


# Executa login (se ainda não autenticado)
if not authenticate():
    st.stop()

# Header da aplicação logada
blue_icon_b64 = get_image_base64(BLUE_ICON_PATH)
icon_html = f'<img src="data:image/png;base64,{blue_icon_b64}" width="40" height="40" style="vertical-align: middle; margin-right: 10px;" />' if blue_icon_b64 else '🧾 '

st.markdown(
    f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; margin-bottom: 20px;">
        <div style="display: flex; align-items: center;">
            {icon_html}
            <div>
                <h3 style="margin: 0; padding: 0; color: #f8fafc; font-size: 19px; font-weight: 700;">EMED Fiscal • Módulo Tributário</h3>
                <span style="color: #94a3b8; font-size: 13px;">Operador: <b style="color: #38bdf8;">{st.session_state.get('username')}</b> &bull; Cargo: <span style="color: #a5f3fc;">{st.session_state.get('cargo', st.session_state.get('role'))}</span></span>
            </div>
        </div>
        <div style="text-align: right;">
            <span style="background: #0284c7; color: white; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;">AMBIENTE EM NUVEM ATIVO</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar de navegação
if st.session_state.get("authenticated"):
    st.sidebar.markdown(f"**👤 {st.session_state.get('username').upper()}**")
    st.sidebar.caption(f"{st.session_state.get('cargo')}")
    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        st.session_state.clear()
        safe_clear_query_params()
        safe_rerun()
    st.sidebar.markdown("---")

# Menu estruturado da Área Fiscal
menu_items = ["Emissão Fiscal (NFS-e)", "Tutorial & Vídeos", "Sobre"]
if is_admin():
    menu_items.insert(1, "🔑 Gerar Acesso QR (Novo Dispositivo)")
    menu_items.append("⚙️ Configurações & Logs")

selected_tab = st.sidebar.radio("Navegação do Módulo", menu_items)


# ABA 1: EMISSÃO FISCAL
if selected_tab == "Emissão Fiscal (NFS-e)":
    if render_modulo_fiscal:
        render_modulo_fiscal(
            db_name=str(DB_PATH),
            usuario_atual=str(st.session_state.get("username", "netto")),
            perfil_atual=str(st.session_state.get("role", "admin"))
        )
    else:
        st.error("Módulo fiscal em processo de inicialização. Recarregue a página.")


# ABA 2: GERAR ACESSO QR (EXCLUSIVO ADMIN / NETTO)
elif selected_tab == "🔑 Gerar Acesso QR (Novo Dispositivo)" and is_admin():
    st.title("🔑 Autorização de Dispositivos Móveis via QR Code")
    st.caption("Gere um QR Code temporário de 30 minutos para autorizar o acesso de um operador do Financeiro ou Faturamento sem precisar digitar senha no celular/tablet.")

    contas_financeiro = [u["username"] for u in USERS if u.get("role") != "admin"]
    if not contas_financeiro:
        st.info("Nenhuma conta de operador cadastrada.")
    else:
        user_alvo = st.selectbox("Selecione o operador a autorizar:", contas_financeiro)
        if st.button("📲 Gerar QR Code de Acesso Seguro", type="primary"):
            try:
                token_dict = {
                    "username": user_alvo,
                    "ts": int(time.time()),
                    "device_id": uuid.uuid4().hex,
                }
                token_json = json.dumps(token_dict)
                token_b64 = base64.urlsafe_b64encode(token_json.encode()).decode()

                base_url = "https://fiscal.emedservice.med.br"
                full_url = f"{base_url}?token={urllib.parse.quote_plus(token_b64)}"

                qr = qrcode.QRCode(box_size=8, border=2)
                qr.add_data(full_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption=f"Aponte a câmera do dispositivo do operador {user_alvo.upper()}", width=320)
                st.success(f"QR Code gerado com sucesso para {user_alvo}! Válido por 30 minutos.")
            except Exception as e:
                st.error(f"Erro ao gerar QR Code: {e}")


# ABA 3: TUTORIAL & VÍDEOS
elif selected_tab == "Tutorial & Vídeos":
    st.title("Capacitação & Tutorial de Emissão Fiscal")
    
    YOUTUBE_ID = CONFIG.get("youtube_id", "")
    if YOUTUBE_ID and YOUTUBE_ID != "abc123XYZ":
        tutorial_src = f"https://www.youtube.com/watch?v={YOUTUBE_ID}"
    else:
        local_video = ASSETS_DIR / "tutorial_emissao_nf.mp4"
        tutorial_src = str(local_video) if local_video.is_file() else None
        
    if tutorial_src:
        st.video(tutorial_src)
    else:
        st.info("Vídeo de tutorial não disponível no momento.")
    st.caption("Vídeo oficial de treinamento do Módulo Fiscal da EMED Eletromedicina.")


# ABA 4: CONFIGURAÇÕES & LOGS (ADMIN)
elif selected_tab == "⚙️ Configurações & Logs" and is_admin():
    st.title("Configurações do Sistema & Logs de Auditoria")
    
    tab_cfg1, tab_cfg2 = st.tabs(["⚙️ Parâmetros", "📋 Logs do Sistema"])
    
    with tab_cfg1:
        youtube_id = st.text_input("YouTube ID ou URL do Vídeo Tutorial:", value=CONFIG.get("youtube_id", ""))
        cron_expr = st.text_input("Expressão Cron de Sincronização Diária:", value=CONFIG.get("cron_expression", "0 6 * * *"))
        admin_list = st.text_area(
            "Usuários Administradores (um por linha):",
            value="\n".join(CONFIG.get("admin_users", [])),
            height=100,
        )
        if st.button("Salvar Parâmetros"):
            new_cfg = {
                "youtube_id": youtube_id.strip(),
                "cron_expression": cron_expr.strip(),
                "admin_users": [u.strip() for u in admin_list.splitlines() if u.strip()],
            }
            CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2), encoding="utf-8")
            st.success("Configurações salvas com sucesso!")

    with tab_cfg2:
        log_path = Path("logs/emed_fiscal.log")
        if log_path.is_file():
            content = log_path.read_text(encoding="utf-8")
            st.text_area("Registro de Logs:", content, height=350)
            st.download_button("📥 Baixar Arquivo de Log", data=content, file_name="emed_fiscal.log")
        else:
            st.info("Nenhum log gravado até o momento.")


# ABA 5: SOBRE
elif selected_tab == "Sobre":
    st.title("Sobre o EMED Fiscal")
    st.markdown(
        """
        ### Portal Integrado de Emissão Fiscal & Tributária • EMED Eletromedicina
        
        - **Multi-Filiais**: Emissão independente para a Filial Brasília (SEFAZ-DF / Nota Control) e Matriz (Ceará).
        - **Integração Operacional**: Preenchimento automático com dados de clientes, equipamentos e ordens de serviço.
        - **Emissão 1-Clique**: Geração instantânea de XML ABRASF e espelho DANFE.
        - **Disparo Digital**: Envio simplificado da nota ao cliente via WhatsApp ou E-mail.
        - **Certificado Digital A1**: Suporte completo a arquivo `.pfx` com chaveamento Produção / Homologação.
        """
    )
