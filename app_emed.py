# app_emed.py
"""Streamlit UI for EMED Fiscal / EMED Nota.

Funcionalidades principais:
- Login simples (usuário/senha) com sessão Streamlit.
- Logout no sidebar.
- Aba "Técnico" que gera QR Code contendo token JWT‑like (username, timestamp, device_id).
  O token tem validade de 30 min e ao ser escaneado realiza login automático e registra o dispositivo em devices.json.
- Aba "Emissão NF" (tutorial video, informações do cron).
- Aba "Logs" (visualização e download).
- Aba "Sobre".
- Aba "Config" (visível apenas para admins).
"""

import json
import re
import urllib.parse
import time
import uuid
import base64
import streamlit as st
from pathlib import Path
import qrcode
from io import BytesIO


# Configurações de arquivos

USERS_FILE = Path(__file__).parent / "users.json"
CONFIG_FILE = Path(__file__).parent / "config.json"
DEVICES_FILE = Path(__file__).parent / "devices.json"

def load_json(file_path: Path, default):
    """Carrega JSON de file_path ou cria com default se não existir."""
    if file_path.is_file():
        return json.loads(file_path.read_text(encoding="utf-8"))
    file_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default

# Usuários padrão (não use em produção – sem hash!)
DEFAULT_USERS = [
    {"username": "vitor", "password": "12345", "role": "admin"},
    {"username": "guest", "password": "guest", "role": "user"},
    {"username": "tecnico1", "password": "tecnico", "role": "technician"},
]
USERS = load_json(USERS_FILE, DEFAULT_USERS)

# Configurações padrão
DEFAULT_CONFIG = {
    "youtube_id": "abc123XYZ",
    "cron_expression": "0 6 * * *",
    "admin_users": ["vitor"]
}
CONFIG = load_json(CONFIG_FILE, DEFAULT_CONFIG)


# Funções auxiliares

def authenticate():
    """Exibe formulário de login simples e persiste sessão em st.session_state."""
    if st.session_state.get("authenticated"):
        return True
    st.subheader("Login")
    user = st.text_input("Usuário")
    pwd = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        for u in USERS:
            if u["username"] == user and u["password"] == pwd:
                st.session_state["authenticated"] = True
                st.session_state["username"] = user
                st.session_state["role"] = u["role"]
                st.experimental_rerun()
        st.error("Credenciais inválidas")
    return False

def is_admin() -> bool:
    """Retorna True se o usuário logado for admin ou estiver na lista admin_users."""
    return (
        st.session_state.get("role") == "admin" or
        st.session_state.get("username") in CONFIG.get("admin_users", [])
    )


# Token QR (login automático) – validade 30 min

# Função segura para obter parâmetros de consulta
def get_query_params():
    try:
        return st.experimental_get_query_params()
    except AttributeError:
        # Fallback: analisar a query string manualmente
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
        # validade 30 minutos = 1800 segundos
        if time.time() - ts > 1800:
            st.error("Token expirado (validade 30 min).")
        else:
            user_obj = next((u for u in USERS if u["username"] == username), None)
            if user_obj:
                st.session_state["authenticated"] = True
                st.session_state["username"] = user_obj["username"]
                st.session_state["role"] = user_obj["role"]
                # registra dispositivo
                devices = load_json(DEVICES_FILE, {})
                device_id = data.get("device_id") or uuid.uuid4().hex
                devices.setdefault(username, []).append(device_id)
                devices[username] = list(set(devices[username]))
                DEVICES_FILE.write_text(json.dumps(devices, indent=2), encoding="utf-8")
                st.success(f"Login automático realizado. Dispositivo cadastrado (ID: {device_id}).")
                # Limpar parâmetros da query para evitar login automático recorrente
                st.experimental_set_query_params()
                st.experimental_rerun()
    except Exception as e:
        st.error(f"Erro ao processar token: {e}")

# UI principal

# Configurações de layout
st.set_page_config(page_title="EMED Fiscal – Emissão NF", layout="centered")

# Executa login (se ainda não autenticado)
if not authenticate():
    st.stop()

# Logo
LOGO_PATH = Path(__file__).parent / "assets" / "emed_logo.png"
if LOGO_PATH.is_file():
    st.image(str(LOGO_PATH), width=240)
else:
    st.markdown("## EMED Fiscal")

# Sidebar logout (aparece quando autenticado)
if st.session_state.get("authenticated"):
    if st.sidebar.button("Sair"):
        for key in ["authenticated", "username", "role"]:
            st.session_state.pop(key, None)
        st.experimental_rerun()

# Sidebar menu
menu_items = ["Emissão NF", "Logs", "Sobre"]
if is_admin():
    menu_items.append("Config")
    menu_items.append("Técnico")
selected_tab = st.sidebar.selectbox("Menu", menu_items)


# Aba Emissão NF

if selected_tab == "Emissão NF":
    st.title("Emissão de Nota Fiscal")
    if LOGO_PATH.is_file():
        st.image(str(LOGO_PATH), width=200)
    else:
        st.markdown("## EMED Fiscal")
    # Vídeo tutorial
    YOUTUBE_ID = CONFIG.get("youtube_id", "")
    if YOUTUBE_ID:
        tutorial_src = f"https://www.youtube.com/watch?v={YOUTUBE_ID}"
    else:
        local_video = Path(__file__).parent / "assets" / "tutorial_emissao_nf.mp4"
        tutorial_src = str(local_video) if local_video.is_file() else None
    with st.expander("Tutorial – como gerar a pré‑visualização (passo a passo)"):
        if tutorial_src:
            st.video(tutorial_src)
        else:
            st.info("Vídeo de tutorial não disponível.")
        st.caption("Substitua `abc123XYZ` pelo ID real após upload.")
    st.markdown("---")
    st.info(
        "⚙️ **Agendamento diário** (06:00 UTC) já está configurado e executa `python cli.py preview-nota 1` silenciosamente.\n"
        "Você pode confirmar o cron em **Automation → Schedules**."
    )
    st.caption("Este aplicativo foi criado como parte da automação de pré‑visualização de notas fiscais.")


# Aba Técnico (geração QR)

elif selected_tab == "Técnico":
    st.title("Login via QR Code – Técnico")
    tecnicos = [u["username"] for u in USERS if u.get("role") == "technician"]
    if not tecnicos:
        st.info("Nenhum técnico cadastrado.")
    else:
        tech_user = st.selectbox("Selecione o técnico", tecnicos)
        if st.button("Gerar QR"):
            try:
                token_dict = {
                    "username": tech_user,
                    "ts": int(time.time()),
                    "device_id": uuid.uuid4().hex,
                }
                token_json = json.dumps(token_dict)
                token_b64 = base64.urlsafe_b64encode(token_json.encode()).decode()

                base_url = st.get_option("server.baseUrl") or "http://localhost:8501"
                # Encode token for safe URL inclusion
                full_url = f"{base_url}?token={urllib.parse.quote_plus(token_b64)}"

                qr = qrcode.QRCode(box_size=8, border=2)
                qr.add_data(full_url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), caption="Escaneie com a câmera do celular")
                st.success("QR Code gerado. O técnico pode escanear para login automático (validade 30 min).")
            except Exception as e:
                st.error(f"Erro ao gerar QR Code: {e}")


# Aba Logs

elif selected_tab == "Logs":
    st.title("Logs do Preview Diário")
    log_path = Path(r"C:/Users/vitor/.gemini/antigravity/logs/emed_fiscal.log")
    start_date = st.date_input("Data inicial (opcional)", value=None)
    if st.button("Refresh logs"):
        st.experimental_rerun()
    if log_path.is_file():
        content = log_path.read_text(encoding="utf-8")
        if start_date:
            lines = [ln for ln in content.splitlines() if ln and start_date.isoformat() in ln]
            content = "\n".join(lines)
        st.text_area("Conteúdo do log", content, height=400)
        st.download_button(
            label="Download completo do log",
            data=content,
            file_name="emed_fiscal.log",
            mime="text/plain",
        )
    else:
        st.warning("Arquivo de log não encontrado.")
    # Auditar DB
    db_path = Path(r"C:/Users/vitor/.gemini/antigravity/emed_dados.db")
    if db_path.is_file():
        try:
            import sqlite3, pandas as pd
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("SELECT id, action, timestamp FROM audit_log ORDER BY id DESC LIMIT 10", conn)
            st.subheader("Últimas entradas de auditoria")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV da auditoria",
                data=csv,
                file_name="audit_log.csv",
                mime="text/csv",
            )
        except Exception as e:
            st.error(f"Erro ao ler audit_log: {e}")
        finally:
            conn.close()
    else:
        st.info("Banco de dados de auditoria não encontrado.")


# Aba Sobre

elif selected_tab == "Sobre":
    st.title("Sobre o EMED Fiscal")
    st.markdown(
        """
        **EMED Fiscal** – solução para geração automática de pré‑visualizações de notas fiscais.

        - **Automação diária**: cron configurado para rodar às 06:00 UTC.
        - **Log & auditoria**: cada preview grava em `logs/emed_fiscal.log` e na tabela `audit_log`.
        - **Tutorial**: vídeo embutido para orientar usuários.
        - **Tecnologia**: Streamlit para UI, CLI Python para backend.
        """
    )


# Aba Config (admin apenas)

elif selected_tab == "Config" and is_admin():
    st.title("Configurações da Aplicação")
    youtube_id = st.text_input("YouTube ID (ou URL completa)", value=CONFIG.get("youtube_id", ""))
    cron_expr = st.text_input("Expressão cron", value=CONFIG.get("cron_expression", "0 6 * * *"))
    admin_list = st.text_area(
        "Usuários administradores (um por linha)",
        value="\n".join(CONFIG.get("admin_users", [])),
        height=150,
    )
    if st.button("Salvar Configurações"):
        new_cfg = {
            "youtube_id": youtube_id.strip(),
            "cron_expression": cron_expr.strip(),
            "admin_users": [u.strip() for u in admin_list.splitlines() if u.strip()],
        }
        CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2), encoding="utf-8")
        st.success("Configurações salvas. Reinicie o app para aplicar.")
