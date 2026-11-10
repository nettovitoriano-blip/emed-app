"""
watchdog_servidor_24x7.py — Guardião Permanente 24/7 do Ecossistema eMED + Domínio Oficial emedservice.med.br
Mantém vivos e monitorados automaticamente:
1. Servidor Oficial PWA/ERP eMED (emed_app_server.py na porta 8502)
2. Servidor Streamlit ERP Hospitalar (app_emed.py na porta 8501)
3. Túnel Oficial Cloudflare (emedservice.med.br / sistema.emedservice.med.br / car.emedservice.med.br)
4. Servidor EmedNav GPS Dedicado (emed_nav/emed_nav_server.py na porta 5000)
5. Receptor de Telemetria J16 4G (emed_gps_gateway.py na porta 5023)
"""
import os
import sys
import time
import shutil
import subprocess
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT_PWA = int(os.environ.get("PORT", "8502"))
PORT_ST = 8501
PORT_NAV = 5000
LOG_FILE = os.path.join(BASE_DIR, "servidor_24x7.log")
CF_TOKEN = os.environ.get("CF_TUNNEL_TOKEN", "eyJhIjoiYjMyZTc4YmVmNzk0Nzc0YTFkOTA1MTVlMTJlYzMwNTIiLCJ0IjoiMWNkZmEwNDMtYTVkYi00Mzg0LWJjMTctNDQzMGY3Mzg2NjhmIiwicyI6IlpXSXpOamhsTWprdE1UTTVZaTAwTXpRekxXSXlZVGN0TWpGa016SmtNalV6T0dVeCJ9")


def porta_http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            return r.status in (200, 301, 302, 404)
    except Exception:
        return False


def localizar_cloudflared() -> str:
    w = shutil.which("cloudflared")
    if w:
        return w
    cands = [
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Program Files\cloudflared\cloudflared.exe",
        os.path.join(BASE_DIR, "cloudflared.exe"),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return ""


def log_msg(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass



import datetime
import sqlite3

_ULTIMO_BACKUP_DIA = None

def rotacionar_log_se_necessario():
    """Garante que o arquivo de log do servidor nunca ultrapasse 10 MB."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 10 * 1024 * 1024:
            old_log = LOG_FILE + ".old"
            if os.path.exists(old_log):
                try:
                    os.remove(old_log)
                except Exception:
                    pass
            os.rename(LOG_FILE, old_log)
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{agora}] Log rotacionado com sucesso (limite 10MB atingido).\n")
    except Exception as e:
        print(f"Erro ao rotacionar log: {e}")

def executar_backup_diario_automatico():
    """Gera um snapshot atômico diário do banco emed.db com retenção de 7 dias e cópia para o pendrive se plugado."""
    global _ULTIMO_BACKUP_DIA
    hoje_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if _ULTIMO_BACKUP_DIA == hoje_str:
        return

    db_origem = os.path.join(BASE_DIR, "emed.db")
    if not os.path.exists(db_origem):
        return

    pasta_bkp_local = os.path.join(BASE_DIR, "backups_diarios")
    os.makedirs(pasta_bkp_local, exist_ok=True)
    arquivo_bkp_local = os.path.join(pasta_bkp_local, f"emed_auto_{hoje_str}.db")

    try:
        src = sqlite3.connect(db_origem)
        dst = sqlite3.connect(arquivo_bkp_local)
        src.backup(dst)
        dst.close()
        src.close()
        log_msg(f"Backup diário automático gerado com sucesso: {arquivo_bkp_local}")
        _ULTIMO_BACKUP_DIA = hoje_str

        # Retenção: mantém os últimos 7 dias
        arquivos = sorted([os.path.join(pasta_bkp_local, f) for f in os.listdir(pasta_bkp_local) if f.startswith("emed_auto_") and f.endswith(".db")])
        while len(arquivos) > 7:
            remover = arquivos.pop(0)
            try:
                os.remove(remover)
                log_msg(f"Expurgado backup diário antigo: {remover}")
            except Exception:
                pass

        # Cópia para o Pendrive (I:) se estiver conectado
        if os.path.exists("I:\\"):
            pendrive_dir = "I:\\BACKUPS_DIARIOS_EMED"
            os.makedirs(pendrive_dir, exist_ok=True)
            shutil.copy2(arquivo_bkp_local, os.path.join(pendrive_dir, f"emed_auto_{hoje_str}.db"))
            log_msg(f"Cópia de redundância do backup diário salva no pendrive: {pendrive_dir}")

        # Cópia para a Unidade G:
        if os.path.exists(r"G:\Sistema Emed"):
            g_bkp = os.path.join(r"G:\Sistema Emed", "backups_diarios")
            os.makedirs(g_bkp, exist_ok=True)
            shutil.copy2(arquivo_bkp_local, os.path.join(g_bkp, f"emed_auto_{hoje_str}.db"))
    except Exception as e:
        log_msg(f"Aviso no backup diário automático: {e}")

def main():
    os.chdir(BASE_DIR)
    proc_pwa = None
    proc_st = None
    proc_cf = None
    proc_nav = None
    proc_gps = None

    cf_exe = localizar_cloudflared()
    log_msg(f"Iniciando Watchdog 24/7 eMED Completo. cloudflared={cf_exe}")

    while True:
        try:
            rotacionar_log_se_necessario()
            executar_backup_diario_automatico()
        except Exception as e:
            log_msg(f"Erro manutencao: {e}")
        # 1. Servidor Principal PWA (Porta 8502)
        if not porta_http_ok(f"http://127.0.0.1:{PORT_PWA}/manifest.json"):
            pwa_precisa_subir = False
            if proc_pwa is None or proc_pwa.poll() is not None:
                pwa_precisa_subir = True
            else:
                falhas_pwa = getattr(main, "_falhas_pwa", 0) + 1
                setattr(main, "_falhas_pwa", falhas_pwa)
                if falhas_pwa >= 4:
                    log_msg(f"emed_app_server travou ({falhas_pwa} falhas). Reiniciando...")
                    try:
                        proc_pwa.terminate()
                        proc_pwa.wait(timeout=3)
                    except Exception:
                        pass
                    pwa_precisa_subir = True
                    setattr(main, "_falhas_pwa", 0)

            if pwa_precisa_subir:
                env = os.environ.copy()
                env["PORT"] = str(PORT_PWA)
                env["PYTHONIOENCODING"] = "utf-8"
                log_msg(f"Subindo emed_app_server.py na porta {PORT_PWA}...")
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    proc_pwa = subprocess.Popen(
                        [sys.executable, os.path.join(BASE_DIR, "emed_app_server.py")],
                        cwd=BASE_DIR,
                        env=env,
                        stdout=lf,
                        stderr=lf,
                    )
                for _ in range(30):
                    time.sleep(1)
                    if porta_http_ok(f"http://127.0.0.1:{PORT_PWA}/manifest.json"):
                        log_msg(f"emed_app_server.py ONLINE na porta {PORT_PWA}.")
                        setattr(main, "_falhas_pwa", 0)
                        break
        else:
            setattr(main, "_falhas_pwa", 0)

        # 2. Servidor Streamlit ERP (Porta 8501)
        st_script = os.path.join(BASE_DIR, "app_emed.py")
        if os.path.exists(st_script) and not porta_http_ok(f"http://127.0.0.1:{PORT_ST}/_stcore/health"):
            if proc_st is None or proc_st.poll() is not None:
                log_msg(f"Subindo Streamlit ERP (app_emed.py) na porta {PORT_ST}...")
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    proc_st = subprocess.Popen(
                        [sys.executable, "-m", "streamlit", "run", st_script, "--server.port", str(PORT_ST), "--server.headless", "true"],
                        cwd=BASE_DIR,
                        stdout=lf,
                        stderr=lf,
                    )

        # 3. Túnel Oficial Cloudflare (emedservice.med.br)
        if cf_exe and (proc_cf is None or proc_cf.poll() is not None):
            log_msg("Iniciando Túnel Oficial Cloudflare (emedservice.med.br)...")
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                proc_cf = subprocess.Popen(
                    [cf_exe, "tunnel", "--protocol", "http2", "run", "--token", CF_TOKEN],
                    cwd=BASE_DIR,
                    stdout=lf,
                    stderr=lf,
                )

        # 4. EmedNav GPS Server (Porta 5000)
        nav_script = os.path.join(BASE_DIR, "emed_nav", "emed_nav_server.py")
        if os.path.exists(nav_script) and not porta_http_ok(f"http://127.0.0.1:{PORT_NAV}/"):
            if proc_nav is None or proc_nav.poll() is not None:
                log_msg("Iniciando EmedNav Server na porta 5000...")
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    proc_nav = subprocess.Popen(
                        [sys.executable, nav_script, str(PORT_NAV)],
                        cwd=BASE_DIR,
                        stdout=lf,
                        stderr=lf,
                    )

        # 5. Receptor GPS J16 (Porta 5023)
        gps_script = os.path.join(BASE_DIR, "emed_gps_gateway.py")
        if os.path.exists(gps_script) and (proc_gps is None or proc_gps.poll() is not None):
            log_msg("Iniciando Receptor GPS J16 na porta 5023...")
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                proc_gps = subprocess.Popen(
                    [sys.executable, gps_script, "5023"],
                    cwd=BASE_DIR,
                    stdout=lf,
                    stderr=lf,
                )

        time.sleep(5)


if __name__ == "__main__":
    main()
