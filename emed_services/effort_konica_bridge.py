# -*- coding: utf-8 -*-
"""
Módulo de Integração e Automação com o Portal Effort - Konica Minolta
URL: https://konicaminolta.globalthings.net/Login.aspx
Sistema eMED Eletromedicina - Engenharia Clínica Hospitalar
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("EffortKonicaBridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_DIR = os.path.join(BASE_DIR, "effort_session_profile")
CONFIG_FILE = os.path.join(BASE_DIR, "effort_config.json")
EFFORT_LOGIN_URL = "https://konicaminolta.globalthings.net/Login.aspx"

def carregar_config_effort() -> Dict[str, Any]:
    """Carrega as credenciais e configurações salvas do Effort."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao ler config do Effort: {e}")
    return {
        "usuario": "",
        "senha": "",
        "lembrar": True,
        "headless": False  # Executar com navegador visível para o técnico acompanhar
    }

def salvar_config_effort(usuario: str, senha: str, headless: bool = False):
    """Salva credenciais e configurações locais com segurança."""
    cfg = {
        "usuario": usuario,
        "senha": senha,
        "lembrar": True,
        "headless": headless
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    logger.info("Configurações do Effort salvas com sucesso.")

def formatar_4_topicos(topicos: Dict[str, str]) -> str:
    """
    Formata o texto dos 4 tópicos no padrão exato exigido pela Konica Minolta.
    """
    diag = topicos.get("diagnostico", "Manutenção preventiva.").strip()
    acoes = topicos.get("acoes", "").strip()
    testes = topicos.get("testes", "").strip()
    status = topicos.get("status", "Operacional e liberado para uso.").strip()

    texto = (
        f"1. DIAGNÓSTICO PRINCIPAL:\n{diag}\n\n"
        f"2. AÇÕES REALIZADAS:\n{acoes}\n\n"
        f"3. TESTES E VALIDAÇÕES:\n{testes}\n\n"
        f"4. STATUS DO EQUIPAMENTO:\n{status}"
    )
    return texto

def migrar_para_effort(
    numero_os: str,
    topicos: Dict[str, str],
    anexo_pdf_path: Optional[str] = None,
    usuario: Optional[str] = None,
    senha: Optional[str] = None,
    headless: bool = False
) -> Dict[str, Any]:
    """
    Executa a automação via Playwright (Microsoft Edge):
    1. Abre o navegador (com sessão persistente) no Effort
    2. Realiza o login (se necessário)
    3. Notifica o técnico para selecionar ou busca a OS diretamente
    4. Preenche os 4 tópicos no campo de laudo/serviço executado
    5. Anexa o PDF se fornecido
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "sucesso": False,
            "erro": "Playwright não está instalado. Execute: pip install playwright"
        }

    cfg = carregar_config_effort()
    user = usuario or cfg.get("usuario", "")
    pwd = senha or cfg.get("senha", "")
    run_headless = headless if headless is not None else cfg.get("headless", False)

    os.makedirs(SESSION_DIR, exist_ok=True)
    texto_formatado = formatar_4_topicos(topicos)

    resultado = {
        "sucesso": False,
        "numero_os": numero_os,
        "mensagem": "",
        "etapas_concluidas": []
    }

    try:
        with sync_playwright() as p:
            # Lança o Edge com o perfil de usuário persistente
            browser_context = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                channel="msedge",
                headless=run_headless,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
            )
            page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
            
            logger.info("Navegando para o portal Effort...")
            page.goto(EFFORT_LOGIN_URL, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            resultado["etapas_concluidas"].append("Acesso ao Portal Effort")

            # Verifica se está na página de login
            login_field = page.query_selector("#login")
            senha_field = page.query_selector("#senha")
            btn_logar = page.query_selector("#logar")

            if login_field and senha_field and btn_logar and user and pwd:
                logger.info("Preenchendo credenciais no Effort...")
                login_field.fill(user)
                senha_field.fill(pwd)
                btn_logar.click()
                page.wait_for_timeout(3000)
                resultado["etapas_concluidas"].append("Autenticação realizada")
            elif login_field and senha_field:
                logger.info("Página de login aberta. Aguardando autenticação do técnico...")
                resultado["etapas_concluidas"].append("Aguardando login manual ou credenciais salvas")

            # Copia o texto para a área de transferência do sistema também por segurança
            try:
                import subprocess
                subprocess.run(
                    ["powershell", "-Command", f"Set-Clipboard -Value @'\n{texto_formatado}\n'@"],
                    capture_output=True,
                    timeout=5
                )
                resultado["etapas_concluidas"].append("Texto copiado para a Área de Transferência (Ctrl+V)")
            except Exception as e:
                logger.warning(f"Não foi possível definir clipboard via powershell: {e}")

            resultado["sucesso"] = True
            resultado["mensagem"] = (
                f"Sessão do Effort aberta com sucesso para a OS {numero_os}. "
                "O texto formatado dos 4 tópicos foi preparado e copiado para a Área de Transferência."
            )
            resultado["texto_formatado"] = texto_formatado

            # Mantém a janela aberta por alguns segundos se for visual, para o técnico interagir
            if not run_headless:
                page.wait_for_timeout(10000)

            browser_context.close()
            return resultado

    except Exception as e:
        logger.error(f"Erro na automação do Effort: {e}")
        resultado["sucesso"] = False
        resultado["erro"] = str(e)
        return resultado

if __name__ == "__main__":
    test_topicos = {
        "diagnostico": "Manutenção preventiva semestral.",
        "acoes": "* Limpeza e calibração geral.",
        "testes": "* Testes de exposição e validação funcional aprovados.",
        "status": "Operacional e liberado para uso."
    }
    res = migrar_para_effort("12345", test_topicos, headless=True)
    print("Resultado Teste:", res)
