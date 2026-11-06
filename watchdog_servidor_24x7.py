"""
watchdog_servidor_24x7.py — Guardião Permanente 24/7 do Servidor Oficial eMED (Porta 8502)
Monitora continuamente a saúde do servidor HTTP/PWA na porta 8502.
Se o processo cair ou travar, reinicia automaticamente em 2 segundos.
"""
import os
import sys
import time
import socket
import subprocess
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8502"))
SERVER_SCRIPT = os.path.join(BASE_DIR, "emed_app_server.py")
LOG_FILE = os.path.join(BASE_DIR, "servidor_24x7.log")


def porta_respondendo(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/manifest.json", timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    os.chdir(BASE_DIR)
    proc = None
    while True:
        if not porta_respondendo(PORT):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    pass
            env = os.environ.copy()
            env["PORT"] = str(PORT)
            env["PYTHONIOENCODING"] = "utf-8"
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando/Reiniciando emed_app_server.py na porta {PORT}...\n")
                proc = subprocess.Popen(
                    [sys.executable, SERVER_SCRIPT],
                    cwd=BASE_DIR,
                    env=env,
                    stdout=lf,
                    stderr=lf,
                )
            # Aguarda subir
            for _ in range(15):
                time.sleep(1)
                if porta_respondendo(PORT):
                    break
        time.sleep(5)


if __name__ == "__main__":
    main()
