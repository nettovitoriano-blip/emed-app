# -*- coding: utf-8 -*-
"""Automacao Local Dedicada do WhatsApp Web para envio direto de arquivos PDF (Playwright + Edge).
Roda em processo dedicado (127.0.0.1:8509) para evitar conflito com o SelectorEventLoop do aiohttp no Windows.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

BOT_PORT = 8509
BOT_URL = f"http://127.0.0.1:{BOT_PORT}"
BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_DIR = BASE_DIR / "whatsapp_session_perfil"
LOG_FILE = BASE_DIR / "whatsapp_bot.log"


def _log(msg: str) -> None:
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ==============================================================================
# SERVIDOR DEDICADO DO ROBÔ (EXECUTADO COMO PROCESSO INDEPENDENTE)
# ==============================================================================
if __name__ == "__main__":
    import queue
    import threading
    from playwright.sync_api import sync_playwright

    cmd_queue: "queue.Queue[tuple]" = queue.Queue()
    status_cache = {"status": "DESCONECTADO", "ultimo_erro": ""}

    def _worker_loop() -> None:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        pw = None
        ctx = None
        page = None

        def _launch():
            nonlocal pw, ctx, page
            if ctx is not None:
                try:
                    _ = ctx.pages
                    return
                except Exception:
                    ctx = None
            _log("Iniciando Playwright + Edge...")
            pw = sync_playwright().start()
            try:
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    channel="msedge",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1180, "height": 680},
                )
            except Exception:
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    channel="chrome",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                    viewport={"width": 1180, "height": 680},
                )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=45000)
            _log("WhatsApp Web aberto.")

        def _is_logged_in(pg) -> bool:
            try:
                return pg.locator('#pane-side, div[aria-label="Lista de conversas"], [data-testid="chat-list"], footer').count() > 0
            except Exception:
                return False

        def _has_qr(pg) -> bool:
            try:
                return pg.locator('canvas[aria-label*="QR"], [data-testid="qrcode"], div[data-ref]').count() > 0
            except Exception:
                return False

        ATTACH_SEL = (
            'footer button[aria-label*="Anexar" i], '
            'footer button[aria-label*="Attach" i], '
            'footer button[title*="Anexar" i], '
            'footer [data-testid="clip"], '
            'footer [data-testid="attach-menu-plus"], '
            'footer span[data-icon="plus"], '
            'footer span[data-icon="plus-rounded"], '
            'footer span[data-icon="clip"]'
        )

        SEND_SEL = (
            'div[aria-label="Enviar"], '
            'button[aria-label="Enviar"], '
            'div[aria-label="Send"], '
            'button[aria-label="Send"], '
            '[data-testid="send"], '
            'span[data-icon="send"], '
            'span[data-icon="wds-ic-send-filled"]'
        )

        while True:
            cmd, payload, resp_q = cmd_queue.get()
            try:
                if cmd == "CONECTAR":
                    _launch()
                    page.bring_to_front()
                    for _ in range(20):
                        if _is_logged_in(page):
                            status_cache["status"] = "CONECTADO"
                            break
                        if _has_qr(page):
                            status_cache["status"] = "AGUARDANDO_QRCODE"
                            break
                        time.sleep(0.5)
                    _log(f"CONECTAR -> {status_cache['status']}")
                    resp_q.put({"ok": True, "status": status_cache["status"]})

                elif cmd == "STATUS":
                    if ctx is None:
                        resp_q.put({"ok": True, "status": "DESCONECTADO", "perfil_existe": (PROFILE_DIR / "Default").exists()})
                    else:
                        if _is_logged_in(page):
                            status_cache["status"] = "CONECTADO"
                        elif _has_qr(page):
                            status_cache["status"] = "AGUARDANDO_QRCODE"
                        resp_q.put({"ok": True, "status": status_cache["status"], "perfil_existe": True})

                elif cmd == "DEBUG_FOOTER":
                    _launch()
                    fone = str(payload.get("fone") or "5585996197923")
                    page.goto(f"https://web.whatsapp.com/send?phone={fone}", wait_until="domcontentloaded", timeout=30000)
                    for _ in range(40):
                        if page.locator('footer').count() > 0:
                            break
                        time.sleep(0.5)
                    time.sleep(1.5)
                    page.bring_to_front()
                    page.locator('footer button[aria-label="Anexar"]').first.click()
                    time.sleep(0.8)
                    doc_btn = page.locator('button[role="menuitem"][aria-label="Documento"]').first
                    with page.expect_file_chooser(timeout=8000) as fc_info:
                        doc_btn.click(force=True, timeout=5000)
                    fc = fc_info.value
                    tmp_pdf = Path(tempfile.gettempdir()) / "emed_whatsapp_pdfs" / "DANFE_NFe_116.pdf"
                    fc.set_files(str(tmp_pdf))
                    time.sleep(3.5)
                    dbg_png = BASE_DIR / "whatsapp_debug.png"
                    page.screenshot(path=str(dbg_png))
                    resp_q.put({"ok": True, "screenshot": str(dbg_png), "exists": tmp_pdf.exists(), "size": tmp_pdf.stat().st_size if tmp_pdf.exists() else 0})

                elif cmd == "ENVIAR_PDF":
                    _launch()
                    logged = False
                    for _ in range(30):
                        if _is_logged_in(page):
                            logged = True
                            status_cache["status"] = "CONECTADO"
                            break
                        if _has_qr(page):
                            status_cache["status"] = "AGUARDANDO_QRCODE"
                            break
                        time.sleep(0.5)

                    if not logged:
                        page.bring_to_front()
                        resp_q.put({
                            "ok": False,
                            "needs_qr": True,
                            "status": status_cache["status"],
                            "msg": "Escaneie o QR Code na janela do WhatsApp Web que abriu e tente novamente.",
                        })
                        continue

                    numeros: List[str] = payload["numeros"]
                    pdf_path: str = payload["pdf_path"]
                    legenda: str = payload.get("legenda", "")
                    enviados: List[str] = []
                    falhas: List[Dict[str, str]] = []

                    for num_raw in numeros:
                        digits = "".join(c for c in str(num_raw) if c.isdigit())
                        if len(digits) < 10:
                            falhas.append({"numero": num_raw, "erro": "Numero invalido"})
                            continue
                        fone = digits if digits.startswith("55") else f"55{digits}"
                        _log(f"ENVIAR_PDF -> abrindo conversa {fone}...")

                        try:
                            page.goto(f"https://web.whatsapp.com/send?phone={fone}", wait_until="domcontentloaded", timeout=30000)

                            chat_pronto = False
                            num_invalido = False
                            for i_wait in range(40):
                                if page.locator('div[role="dialog"]').count() > 0:
                                    txt_pop = page.locator('div[role="dialog"]').first.inner_text()
                                    if "inválido" in txt_pop.lower() or "invalid" in txt_pop.lower():
                                        num_invalido = True
                                        break
                                if page.locator(ATTACH_SEL).count() > 0 or page.locator('footer div[contenteditable="true"]').count() > 0:
                                    chat_pronto = True
                                    break
                                time.sleep(0.5)

                            if num_invalido:
                                _log(f"Numero {fone} invalido segundo WhatsApp.")
                                falhas.append({"numero": num_raw, "erro": "Numero sem WhatsApp"})
                                continue

                            if not chat_pronto:
                                _log(f"Timeout ao aguardar conversa {fone}.")
                                falhas.append({"numero": num_raw, "erro": "Tempo esgotado ao carregar conversa"})
                                continue

                            time.sleep(0.6)
                            _log(f"Conversa {fone} pronta. Clicando em Anexar...")
                            page.bring_to_front()

                            doc_sel = (
                                'button[role="menuitem"][aria-label="Documento"], '
                                '[role="menuitem"][aria-label*="Documento" i], '
                                '[role="menuitem"]:has-text("Documento"), '
                                '[role="menuitem"]:has-text("Document")'
                            )
                            anexou_fc = False
                            for attempt in range(2):
                                btn_anexar = page.locator(ATTACH_SEL)
                                if btn_anexar.count() == 0:
                                    btn_anexar = page.locator('footer button').first
                                btn_anexar.first.click(force=True, timeout=5000)
                                time.sleep(0.8)
                                doc_item = page.locator(doc_sel)
                                if doc_item.count() > 0:
                                    try:
                                        doc_item.first.wait_for(state="visible", timeout=3000)
                                        _log(f"Menuitem 'Documento' encontrado (tentativa {attempt+1}). Acionando file_chooser...")
                                        with page.expect_file_chooser(timeout=8000) as fc_info:
                                            doc_item.first.click(force=True, timeout=5000)
                                        fc = fc_info.value
                                        fc.set_files(pdf_path)
                                        anexou_fc = True
                                        break
                                    except Exception as e_fc:
                                        _log(f"Tentativa {attempt+1} file_chooser falhou: {e_fc}")
                                        time.sleep(0.5)

                            if not anexou_fc:
                                inp_star = page.locator('input[type="file"][accept="*"]')
                                if inp_star.count() > 0:
                                    inp_star.last.set_input_files(pdf_path)
                                else:
                                    raise RuntimeError("Nao foi possivel acionar o menu 'Documento' no WhatsApp Web.")

                            # Aguarda tela de preview do PDF montar e localiza o botao verde Enviar
                            time.sleep(3.0)
                            if legenda:
                                try:
                                    cap_box = page.locator('div[aria-label*="Digite uma mensagem" i], div[aria-label*="legenda" i], div[contenteditable="true"]').last
                                    if cap_box.count() > 0 and cap_box.is_visible():
                                        cap_box.click()
                                        cap_box.fill(legenda)
                                        time.sleep(0.3)
                                except Exception:
                                    pass

                            btn_send = page.locator(
                                '[aria-label="Enviar" i], '
                                '[aria-label="Send" i], '
                                '[data-testid="send"], '
                                '[data-icon*="send"]'
                            )
                            clicou_send = False
                            if btn_send.count() > 0:
                                _log(f"Botao Enviar encontrado ({btn_send.count()}). Clicando no ultimo (.last) para {fone}...")
                                try:
                                    btn_send.last.scroll_into_view_if_needed(timeout=3000)
                                except Exception:
                                    pass
                                btn_send.last.click(force=True)
                                clicou_send = True
                            else:
                                _log(f"Tentando Enter na tela de preview para {fone}...")
                                page.keyboard.press("Enter")
                                clicou_send = True

                            time.sleep(2.0)
                            # Verifica se a tela de preview fechou (se o botao X de fechar preview ainda estiver la, aperta Enter)
                            if page.locator('button[aria-label="Fechar" i], [data-icon="x-viewer"], [data-icon="x"]').count() > 0:
                                _log(f"Preview ainda visivel, reforcando envio via Enter + JS click para {fone}...")
                                page.keyboard.press("Enter")
                                page.evaluate("""() => {
                                    const s = document.querySelectorAll('[aria-label="Enviar"], [aria-label="Send"], [data-testid="send"], [data-icon*="send"]');
                                    if (s.length) s[s.length - 1].click();
                                }""")
                                time.sleep(2.0)

                            if clicou_send:
                                _log(f"Enviado com sucesso para {fone}!")
                                enviados.append(num_raw)
                        except Exception as ex_num:
                            err_n = f"{type(ex_num).__name__}: {ex_num}"[:180]
                            _log(f"Falha ao enviar para {fone}: {err_n}")
                            falhas.append({"numero": num_raw, "erro": err_n})

                    resp_q.put({
                        "ok": len(enviados) > 0,
                        "enviados": enviados,
                        "falhas": falhas,
                        "msg": (
                            f"✅ DANFE em PDF enviada automaticamente no WhatsApp para {len(enviados)} numero(s)!"
                            if enviados else "Nao foi possivel enviar para os numeros informados."
                        ),
                    })
            except Exception as exc:
                err_txt = f"{type(exc).__name__}: {exc}"
                status_cache["ultimo_erro"] = err_txt
                _log(f"Erro geral no worker: {err_txt}")
                resp_q.put({"ok": False, "msg": f"Erro no robo WhatsApp: {err_txt}"})

    threading.Thread(target=_worker_loop, daemon=True).start()

    class _BotHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, data: dict, code: int = 200):
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/status":
                rq: "queue.Queue[dict]" = queue.Queue()
                cmd_queue.put(("STATUS", None, rq))
                self._send_json(rq.get(timeout=10))
            else:
                self._send_json({"ok": True, "service": "EMED-WhatsApp-Bot"})

        def do_POST(self):
            ln = int(self.headers.get("Content-Length", "0") or 0)
            body = json.loads(self.rfile.read(ln).decode("utf-8") or "{}") if ln else {}
            rq: "queue.Queue[dict]" = queue.Queue()
            if self.path == "/conectar":
                cmd_queue.put(("CONECTAR", None, rq))
                self._send_json(rq.get(timeout=50))
            elif self.path == "/debug_footer":
                cmd_queue.put(("DEBUG_FOOTER", body, rq))
                self._send_json(rq.get(timeout=45))
            elif self.path == "/enviar_pdf":
                cmd_queue.put(("ENVIAR_PDF", body, rq))
                self._send_json(rq.get(timeout=180))
            else:
                self._send_json({"ok": False, "msg": "Rota desconhecida"}, 404)

    srv = ThreadingHTTPServer(("127.0.0.1", BOT_PORT), _BotHandler)
    srv.serve_forever()


# ==============================================================================
# CLIENTE USADO PELO PORTAL FISCAL (AIOHTTP)
# ==============================================================================
class _WhatsAppBotClient:
    def _ensure_bot_process(self) -> None:
        try:
            urllib.request.urlopen(f"{BOT_URL}/status", timeout=1.5).read()
            return
        except Exception:
            pass

        creation_flags = 0x08000000 if os.name == "nt" else 0
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())],
            cwd=str(Path(__file__).resolve().parent.parent),
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(25):
            time.sleep(0.3)
            try:
                urllib.request.urlopen(f"{BOT_URL}/status", timeout=1.5).read()
                return
            except Exception:
                pass
        raise RuntimeError("Nao foi possivel iniciar o servico dedicado do WhatsApp na porta 8509.")

    def status(self) -> Dict[str, Any]:
        try:
            raw = urllib.request.urlopen(f"{BOT_URL}/status", timeout=2.0).read()
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {"ok": True, "status": "DESCONECTADO", "perfil_existe": (PROFILE_DIR / "Default").exists()}

    def conectar_qrcode(self) -> Dict[str, Any]:
        self._ensure_bot_process()
        req = urllib.request.Request(f"{BOT_URL}/conectar", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        raw = urllib.request.urlopen(req, timeout=55).read()
        return json.loads(raw.decode("utf-8"))

    def enviar_pdf(self, numeros: List[str], pdf_bytes: bytes, filename: str, legenda: str = "") -> Dict[str, Any]:
        self._ensure_bot_process()
        tmp_dir = Path(tempfile.gettempdir()) / "emed_whatsapp_pdfs"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = tmp_dir / filename
        pdf_path.write_bytes(pdf_bytes)

        payload = json.dumps({"numeros": numeros, "pdf_path": str(pdf_path), "legenda": legenda}).encode("utf-8")
        req = urllib.request.Request(f"{BOT_URL}/enviar_pdf", data=payload, headers={"Content-Type": "application/json"}, method="POST")
        raw = urllib.request.urlopen(req, timeout=185).read()
        return json.loads(raw.decode("utf-8"))


WHATSAPP_BOT = _WhatsAppBotClient()
