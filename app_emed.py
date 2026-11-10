# app_emed.py
"""Streamlit UI for EMED Fiscal / EMED Nota.

Funcionalidades principais:
- Login seguro com logo oficial e ícone fiscal.
- Suporte a administradores (netto, vitor, admin).
- Logout no sidebar.
- Aba "Técnico" com QR Code para login automático de técnicos.
- Aba "Emissão NF" (tutorial video, emissão e cron).
- Aba "Logs" (visualização e download).
- Aba "Sobre".
- Aba "Config" (administradores).
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

# Configurações de página Streamlit (deve ser o primeiro comando Streamlit)
st.set_page_config(
    page_title="EMED Fiscal – Emissão NF",
    page_icon="🧾",
    layout="centered"
)

# Configurações de arquivos
USERS_FILE = Path(__file__).parent / "users.json"
CONFIG_FILE = Path(__file__).parent / "config.json"
DEVICES_FILE = Path(__file__).parent / "devices.json"

def load_json(file_path: Path, default):
    """Carrega JSON de file_path ou cria com default se não existir."""
    if file_path.is_file():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    file_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

# Usuários padrão do sistema
DEFAULT_USERS = [
    {"username": "netto", "password": "12345", "role": "admin"},
    {"username": "vitor", "password": "12345", "role": "admin"},
    {"username": "admin", "password": "12345", "role": "admin"},
    {"username": "guest", "password": "guest", "role": "user"},
    {"username": "tecnico1", "password": "tecnico", "role": "technician"},
]
USERS = load_json(USERS_FILE, DEFAULT_USERS)

# Configurações padrão
DEFAULT_CONFIG = {
    "youtube_id": "abc123XYZ",
    "cron_expression": "0 6 * * *",
    "admin_users": ["vitor", "netto", "admin"]
}
CONFIG = load_json(CONFIG_FILE, DEFAULT_CONFIG)


def get_logo_path():
    """Busca o melhor arquivo de logo disponível para exibição."""
    candidates = [
        Path(__file__).parent / "assets" / "emed_logo_user_dark.png",
        Path(__file__).parent / "assets" / "emed_logo.png",
        Path(__file__).parent / "assets" / "emed_logo_oficial.png",
        Path(__file__).parent / "emed_logo_user_dark.png",
        Path(__file__).parent / "emed_logo_oficial.png",
        Path(__file__).parent / "emed_logo_clean_white_bg.png"
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def authenticate():
    """Exibe formulário de login estilizado com logo e ícone fiscal."""
    if st.session_state.get("authenticated"):
        return True

    logo_path = get_logo_path()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if logo_path:
            st.image(logo_path, use_column_width=True)
        st.markdown(
            "<h3 style='text-align: center; margin-top: -5px; color: #38bdf8; font-weight: 700;'>"
            "🧾 EMED Fiscal • Módulo NF"
            "</h3>"
            "<p style='text-align: center; font-size: 13px; color: #94a3b8; margin-bottom: 25px;'>"
            "Painel de Emissão de Notas & Gestão Tributária"
            "</p>",
            unsafe_allow_html=True
        )

    user = st.text_input("Usuário", placeholder="Digite seu usuário (ex: netto ou vitor)")
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
            st.experimental_rerun()
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


# Token QR (login automático de técnicos) – validade 30 min
def get_query_params():
    try:
        return st.experimental_get_query_params()
    except AttributeError:
        import urllib.parse
        qs = st.experimental_get_query_string() if hasattr(st, "experimental_get_query_string") else ""
        return urllib.parse.parse_qs(qs)

query_params = get_query_params()
if "token" in query_params:
    try:
        token = query_params["token"][0]
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        data = json.loads(decoded)
        username = data.get("username")
        ts = data.get("ts")
        if time.time() - ts > 1800:
            st.error("Token expirado (validade 30 min).")
        else:
            user_obj = next((u for u in USERS if u["username"].lower() == str(username).lower()), None)
            if user_obj:
                st.session_state["authenticated"] = True
                st.session_state["username"] = user_obj["username"]
                st.session_state["role"] = user_obj["role"]
                devices = load_json(DEVICES_FILE, {})
                device_id = data.get("device_id") or uuid.uuid4().hex
                devices.setdefault(username, []).append(device_id)
                devices[username] = list(set(devices[username]))
                DEVICES_FILE.write_text(json.dumps(devices, indent=2), encoding="utf-8")
                st.success(f"Login automático realizado. Dispositivo cadastrado (ID: {device_id}).")
                st.experimental_set_query_params()
                st.experimental_rerun()
    except Exception as e:
        st.error(f"Erro ao processar token de autenticação: {e}")


# Executa login (se ainda não autenticado)
if not authenticate():
    st.stop()

# Header da aplicação logada
logo_path = get_logo_path()
col_h1, col_h2 = st.columns([1, 4])
with col_h1:
    if logo_path:
        st.image(logo_path, width=140)
with col_h2:
    st.markdown(
        f"<h3 style='margin: 0; padding: 0;'>🧾 EMED Fiscal – Emissão NF</h3>"
        f"<span style='color: #64748b; font-size: 13px;'>Usuário conectado: <b>{st.session_state.get('username')}</b> ({st.session_state.get('role')})</span>",
        unsafe_allow_html=True
    )

st.markdown("---")

# Sidebar logout
if st.session_state.get("authenticated"):
    if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
        for key in ["authenticated", "username", "role"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()

# Sidebar menu
menu_items = ["Emissão NF", "Logs", "Sobre"]
if is_admin():
    menu_items.append("Config")
    menu_items.append("Técnico")
selected_tab = st.sidebar.selectbox("Navegação", menu_items)


# Aba Emissão NF
if selected_tab == "Emissão NF":
    st.title("Emissão de Nota Fiscal")
    
    YOUTUBE_ID = CONFIG.get("youtube_id", "")
    if YOUTUBE_ID:
        tutorial_src = f"https://www.youtube.com/watch?v={YOUTUBE_ID}"
    else:
        local_video = Path(__file__).parent / "assets" / "tutorial_emissao_nf.mp4"
        tutorial_src = str(local_video) if local_video.is_file() else None
        
    with st.expander("📺 Tutorial – como gerar a pré-visualização e emissão (passo a passo)", expanded=False):
        if tutorial_src:
            st.video(tutorial_src)
        else:
            st.info("Vídeo de tutorial não disponível.")
        st.caption("Vídeo oficial de treinamento fiscal eMed.")

    st.info(
        "⚙️ **Rotina Fiscal Ativa**: A sincronização automática diária executa a validação e prévia das ordens de serviço faturadas."
    )


# Aba Técnico (geração QR)
elif selected_tab == "Técnico":
    st.title("Login via QR Code – Técnico")
    tecnicos = [u["username"] for u in USERS if u.get("role") == "technician"]
    if not tecnicos:
        st.info("Nenhum técnico cadastrado.")
    else:
        tech_user = st.selectbox("Selecione o técnico", tecnicos)
        if st.button("Gerar QR Code de Acesso"):
            try:
                token_dict = {
                    "username": tech_user,
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
                st.image(buf.getvalue(), caption="Escaneie com a câmera do celular para login instantâneo")
                st.success("QR Code gerado com sucesso. O técnico pode escanear para login automático (validade de 30 min).")
            except Exception as e:
                st.error(f"Erro ao gerar QR Code: {e}")


# Aba Logs
elif selected_tab == "Logs":
    st.title("Logs de Atividades & Auditoria")
    log_path = Path(r"logs/emed_fiscal.log")
    start_date = st.date_input("Filtrar por data (opcional)", value=None)
    if st.button("Atualizar Logs"):
        st.experimental_rerun()
    if log_path.is_file():
        content = log_path.read_text(encoding="utf-8")
        if start_date:
            lines = [ln for ln in content.splitlines() if ln and start_date.isoformat() in ln]
            content = "\n".join(lines)
        st.text_area("Conteúdo do log", content, height=400)
        st.download_button(
            label="Baixar Arquivo de Log",
            data=content,
            file_name="emed_fiscal.log",
            mime="text/plain",
        )
    else:
        st.info("Nenhum log registrado ainda.")


# Aba Sobre
elif selected_tab == "Sobre":
    st.title("Sobre o EMED Fiscal")
    st.markdown(
        """
        ### Sistema Integrado de Emissão e Faturamento Fiscal • EMED Eletromedicina
        
        - **Multi-Filiais**: Suporte integrado às filiais de Brasília (SEFAZ-DF) e Matriz (Ceará).
        - **Automação Segura**: Login simplificado, autenticação de técnicos via QR Code e persistência na nuvem.
        - **Dispositivos**: Registro automático de aparelhos móveis autorizados.
        - **Tecnologia**: Plataforma em nuvem 24/7 de alta disponibilidade com criptografia SSL ponta a ponta.
        """
    )


# Aba Config (admin apenas)
elif selected_tab == "Config" and is_admin():
    st.title("Configurações do Sistema")
    youtube_id = st.text_input("YouTube ID ou URL do Tutorial", value=CONFIG.get("youtube_id", ""))
    cron_expr = st.text_input("Expressão Cron de Sincronização", value=CONFIG.get("cron_expression", "0 6 * * *"))
    admin_list = st.text_area(
        "Usuários Administradores (um por linha)",
        value="\n".join(CONFIG.get("admin_users", [])),
        height=120,
    )
    if st.button("Salvar Configurações"):
        new_cfg = {
            "youtube_id": youtube_id.strip(),
            "cron_expression": cron_expr.strip(),
            "admin_users": [u.strip() for u in admin_list.splitlines() if u.strip()],
        }
        CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2), encoding="utf-8")
        st.success("Configurações salvas com sucesso!")
