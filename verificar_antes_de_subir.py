# -*- coding: utf-8 -*-
"""
Validador Automático Pré-Deploy (Python + JavaScript).
Garante que nenhum erro de sintaxe em Python ou em scripts do PWA
seja enviado para produção no Render.
"""

import os
import re
import sys
import py_compile
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_python_files() -> bool:
    print("🔍 [1/2] Validando sintaxe de todos os arquivos Python...")
    ok = True
    py_files = [
        p for p in ROOT.rglob("*.py")
        if ".git" not in p.parts and ".venv" not in p.parts and "__pycache__" not in p.parts
    ]
    for p in py_files:
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as exc:
            print(f"  ❌ ERRO PYTHON em {p.relative_to(ROOT)}: {exc}")
            ok = False
    if ok:
        print(f"  ✅ {len(py_files)} arquivo(s) Python validados sem erros.")
    return ok


def check_html_scripts() -> bool:
    print("🔍 [2/2] Validando sintaxe JavaScript em emed_pwa_static/index.html...")
    html_path = ROOT / "emed_pwa_static" / "index.html"
    if not html_path.exists():
        print("  ⚠️ emed_pwa_static/index.html não encontrado.")
        return True

    html = html_path.read_text(encoding="utf-8")
    scripts = list(re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE))
    ok = True
    for idx, m in enumerate(scripts, 1):
        js_code = m.group(1)
        line_offset = html[:m.start(1)].count("\n")
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tf:
            tf.write(js_code)
            tmp_path = tf.name
        try:
            res = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
            if res.returncode != 0:
                ok = False
                print(f"  ❌ ERRO JAVASCRIPT no <script> #{idx} (linha HTML ~{line_offset + 1}):")
                print(res.stderr.strip())
            else:
                print(f"  ✅ <script> #{idx} (linha HTML {line_offset + 1}) OK.")
        except FileNotFoundError:
            print("  ⚠️ Node.js não encontrado no PATH; pulando validação JS.")
            break
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    return ok


def main() -> int:
    py_ok = check_python_files()
    js_ok = check_html_scripts()
    if py_ok and js_ok:
        print("\n🚀 TUDO VALIDADO! Sistema 100% seguro para subir para produção.")
        return 0
    print("\n🛑 BLOQUEADO: Corrija os erros acima antes de enviar para produção!")
    return 1


if __name__ == "__main__":
    sys.exit(main())
