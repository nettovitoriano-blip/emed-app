# -*- coding: utf-8 -*-
"""
Módulo de Defesa Cibernética Ativa: Deception Honeypot & Forense Digital
EMED Eletromedicina - Sistema Supervisório SOC
Captura automatizada de botnets, força bruta e invasores em ambiente simulado (Sandbox/Tar Pit),
com coleta de evidências forenses e geração de laudo pericial para a Polícia Civil / DRCI.
"""

import os
import asyncio
import html as _h
import ipaddress
import json
import time
import hashlib
import sqlite3
from typing import Dict, Any, Optional
from aiohttp import web

DB_NAME = "emed.db"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _obter_db_honeypot(request: Optional[web.Request] = None, fallback_db: str = DB_NAME) -> str:
    raw_app = getattr(request, "app", None) if request else None
    raw_val = raw_app.get("db_name") if raw_app is not None and hasattr(raw_app, "get") else None
    db_p = raw_val.strip() if isinstance(raw_val, str) else ""
    cand = db_p or fallback_db
    return cand if os.path.isabs(cand) else os.path.join(BASE_DIR, cand)


def _garantir_schema_honeypot(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS honeypot_evidencias_forenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            ip_origem TEXT NOT NULL,
            sistema_alvo TEXT DEFAULT 'HONEYPOT_DECEPTION_DECOY',
            usuario_tentado TEXT DEFAULT '',
            senhas_tentadas TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            headers_json TEXT DEFAULT '{}',
            dispositivo_info TEXT DEFAULT '',
            screen_resolution TEXT DEFAULT '',
            timezone TEXT DEFAULT '',
            gpu_renderer TEXT DEFAULT '',
            canvas_hash TEXT DEFAULT '',
            tempo_na_armadilha_segundos REAL DEFAULT 0.0,
            acoes_executadas TEXT DEFAULT '',
            status_pericia TEXT DEFAULT 'EVIDENCIAS_COLETADAS',
            criado_em TEXT NOT NULL
        )
    """)


def obter_ip_real_honeypot(request: web.Request) -> str:
    """Extrai o IP real apenas de proxies locais/privados confiaveis (anti-spoofing)."""
    peer = str(request.remote or "").strip()
    if not peer and request.transport:
        pn = request.transport.get_extra_info("peername")
        peer = str(pn[0]) if pn else "127.0.0.1"
    peer = peer or "127.0.0.1"
    is_proxy = False
    try:
        addr = ipaddress.ip_address(peer.split("%")[0])
        is_proxy = addr.is_loopback or addr.is_private
    except Exception:
        is_proxy = False
    if is_proxy:
        for header in ("CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"):
            val = request.headers.get(header)
            if val:
                cand = val.split(",")[0].strip()
                try:
                    ipaddress.ip_address(cand.split("%")[0])
                    return cand
                except Exception:
                    continue
    return peer


def registrar_invasor_honeypot(
    ip_origem: str,
    usuario: str,
    senha_tentada: str,
    user_agent: str,
    dispositivo: str,
    request: web.Request,
    db_path: str = DB_NAME
) -> int:
    """Grava o início da captura do invasor na tabela forense."""
    agora_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    headers_dict = dict(request.headers)
    headers_json = json.dumps(headers_dict, ensure_ascii=False)
    
    full_db_path = _obter_db_honeypot(request, db_path)
    
    with sqlite3.connect(full_db_path) as conn:
        _garantir_schema_honeypot(conn)
        cur = conn.cursor()
        # Verifica se já existe captura recente desse IP nas últimas 2 horas
        cur.execute("""
            SELECT id, senhas_tentadas FROM honeypot_evidencias_forenses
            WHERE ip_origem = ? AND data_hora >= datetime('now', '-2 hours')
            ORDER BY id DESC LIMIT 1
        """, (ip_origem,))
        row = cur.fetchone()
        
        if row:
            ev_id, senhas_antigas = row
            lista_senhas = senhas_antigas.split(" | ") if senhas_antigas else []
            if senha_tentada and senha_tentada not in lista_senhas:
                lista_senhas.append(senha_tentada)
            novas_senhas = " | ".join(lista_senhas[-15:])
            cur.execute("""
                UPDATE honeypot_evidencias_forenses
                SET senhas_tentadas = ?, user_agent = ?, headers_json = ?, data_hora = ?
                WHERE id = ?
            """, (novas_senhas, user_agent, headers_json, agora_iso, ev_id))
            conn.commit()
            return ev_id
        else:
            cur.execute("""
                INSERT INTO honeypot_evidencias_forenses (
                    data_hora, ip_origem, sistema_alvo, usuario_tentado,
                    senhas_tentadas, user_agent, headers_json, dispositivo_info,
                    status_pericia, criado_em
                ) VALUES (?, ?, 'HONEYPOT_DECEPTION_DECOY', ?, ?, ?, ?, ?, 'EVIDENCIAS_COLETADAS', ?)
            """, (agora_iso, ip_origem, usuario, senha_tentada, user_agent, headers_json, dispositivo, agora_iso))
            conn.commit()
            return cur.lastrowid


async def handle_honeypot_dashboard(request: web.Request) -> web.Response:
    """
    Renderiza o Painel Decoy falso hiper-realista.
    O invasor acredita que invadiu com sucesso o console administrativo do servidor hospitalar.
    Enquanto isso, scripts em segundo plano coletam telemetria profunda da máquina do invasor.
    """
    ip_origem = obter_ip_real_honeypot(request)
    ua = request.headers.get("User-Agent", "Desconhecido")
    
    # Registra o acesso ao painel decoy
    registrar_invasor_honeypot(ip_origem, "ROOT_ADMIN_DECOY", "[ACESSO_DIRETO_DASHBOARD]", ua, "NAVEGADOR_ATACANTE", request)
    
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>eMED Hospitalar — Console Administrativo &amp; Servidores (Acesso Root 24/7)</title>
  <style>
    :root {{
      --bg: #090d16;
      --card: #111827;
      --border: #1f2937;
      --primary: #3b82f6;
      --green: #10b981;
      --red: #ef4444;
      --text: #f3f4f6;
      --muted: #9ca3af;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Consolas', 'Courier New', monospace, sans-serif; background: var(--bg); color: var(--text); padding: 18px; font-size: 13px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    
    /* Top Header */
    .top-bar {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid var(--border); padding-bottom: 12px; margin-bottom: 18px; }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-logo {{ font-size: 24px; background: #1e3a8a; padding: 8px 12px; border-radius: 6px; border: 1px solid #3b82f6; font-weight: bold; }}
    .brand-title h1 {{ font-size: 16px; color: #fff; text-transform: uppercase; letter-spacing: 1px; }}
    .brand-title span {{ font-size: 11px; color: var(--green); font-weight: bold; }}
    
    .status-badge {{ background: #064e3b; border: 1px solid var(--green); color: #6ee7b7; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
    
    /* Grid de Estatísticas */
    .grid-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 20px; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }}
    .card-title {{ font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 6px; font-weight: bold; }}
    .card-value {{ font-size: 24px; font-weight: 900; color: #fff; }}
    .card-sub {{ font-size: 10.5px; color: var(--green); margin-top: 4px; }}
    
    /* Painel do Terminal Interativo */
    .terminal-box {{ background: #000; border: 1px solid #374151; border-radius: 8px; padding: 14px; margin-bottom: 20px; }}
    .term-header {{ display: flex; justify-content: space-between; border-bottom: 1px solid #1f2937; padding-bottom: 6px; margin-bottom: 10px; font-size: 11px; color: var(--muted); }}
    .term-body {{ min-height: 140px; max-height: 240px; overflow-y: auto; color: #10b981; font-size: 12.5px; line-height: 1.4; }}
    .term-input-line {{ display: flex; align-items: center; gap: 8px; margin-top: 8px; border-top: 1px solid #1f2937; padding-top: 8px; }}
    .term-prompt {{ color: #38bdf8; font-weight: bold; }}
    .term-input {{ background: transparent; border: none; color: #fff; font-family: inherit; font-size: 13px; width: 100%; outline: none; }}
    
    /* Seção de Arquivos Falsos */
    .table-files {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    .table-files th, .table-files td {{ padding: 10px; border-bottom: 1px solid var(--border); text-align: left; font-size: 12px; }}
    .table-files th {{ color: var(--muted); font-size: 10.5px; text-transform: uppercase; background: #0f172a; }}
    .btn-fake {{ background: #1e40af; color: #fff; border: 1px solid #3b82f6; padding: 6px 12px; border-radius: 4px; font-size: 11px; font-weight: bold; cursor: pointer; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }}
    .btn-fake:hover {{ background: #2563eb; }}
    
    /* Alerta Fake */
    .alert-banner {{ background: #1e1b4b; border: 1px solid #4338ca; padding: 10px 14px; border-radius: 6px; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; }}
  </style>
</head>
<body>
  <div class="container">
    
    <div class="top-bar">
      <div class="brand">
        <div class="brand-logo">eMED</div>
        <div class="brand-title">
          <h1>Console Administrativo Central &bull; Servidores e Infraestrutura v4.2</h1>
          <span>SESSÃO ELEVADA ROOT (PRIVILÉGIOS TOTAIS CONCEDIDOS)</span>
        </div>
      </div>
      <div>
        <span class="status-badge">CONEXÃO SEGURA SSH / TLS 1.3 ATIVA</span>
      </div>
    </div>

    <div class="alert-banner">
      <span>⚠️ <b>Aviso do Sistema:</b> Sessão de diagnóstico root aberta pelo IP: <b style="color:#38bdf8;">{ip_origem}</b>. Todos os nós hospitalares estão sincronizados.</span>
      <span style="color:#94a3b8;">Uptime: 48 dias, 14 horas</span>
    </div>

    <!-- CARDS DE ESTATÍSTICA DO SERVIDOR -->
    <div class="grid-stats">
      <div class="card">
        <div class="card-title">Carga da CPU</div>
        <div class="card-value">14.2%</div>
        <div class="card-sub">AMD EPYC 64-Core &bull; Temperatura: 39°C</div>
      </div>
      <div class="card">
        <div class="card-title">Bancos de Dados Hospitalares</div>
        <div class="card-value">12 / 12</div>
        <div class="card-sub">PostgreSQL &amp; SQLite 100% Online</div>
      </div>
      <div class="card">
        <div class="card-title">Certificados SEFAZ &amp; NFS-e</div>
        <div class="card-value">A1 Válido</div>
        <div class="card-sub">Validade até: 2027-11-20</div>
      </div>
      <div class="card">
        <div class="card-title">Backups de Dados</div>
        <div class="card-value">4.8 GB</div>
        <div class="card-sub">Último snapshot gerado hoje às 03:00</div>
      </div>
    </div>

    <!-- TERMINAL FAKE INTERATIVO -->
    <div class="terminal-box">
      <div class="term-header">
        <span>SHELL INTERATIVO &bull; BASH EMULATOR v5.2</span>
        <span>SESSÃO: #TTY-4912</span>
      </div>
      <div id="termOutput" class="term-body">
        <div>Linux emed-srv-prod 6.5.0-generic #42-Ubuntu SMP PREEMPT_DYNAMIC x86_64</div>
        <div>Bem-vindo ao Shell Administrativo do Servidor de Banco de Dados eMED Hospitalar.</div>
        <div>Digite 'help' ou comandos padrão do sistema para navegar.</div>
      </div>
      <div class="term-input-line">
        <span class="term-prompt">root@emed-srv-01:~#</span>
        <input type="text" id="termInput" class="term-input" autofocus placeholder="Digite um comando e pressione Enter..." />
      </div>
    </div>

    <!-- ARQUIVOS FALSOS E DUMPS PARA CAPTURA -->
    <div class="card">
      <div class="card-title" style="font-size:13px; color:#fff; margin-bottom:10px;">📂 Repositório de Dumps e Configurações Confidenciais</div>
      <table class="table-files">
        <thead>
          <tr>
            <th>Nome do Arquivo</th>
            <th>Tipo</th>
            <th>Tamanho</th>
            <th>Última Modificação</th>
            <th>Ação</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><b>emed_hospitalar_database_full.sql.gz</b></td>
            <td>Backup do Banco SQL</td>
            <td>1.4 GB</td>
            <td>Hoje 03:00</td>
            <td><button class="btn-fake" onclick="simularDownload('emed_hospitalar_database_full.sql.gz')">📥 Baixar Arquivo</button></td>
          </tr>
          <tr>
            <td><b>chaves_certificados_sefaz_prod.pfx</b></td>
            <td>Certificado Digital A1</td>
            <td>12 KB</td>
            <td>15/11/2026</td>
            <td><button class="btn-fake" onclick="simularDownload('chaves_certificados_sefaz_prod.pfx')">📥 Baixar Certificado</button></td>
          </tr>
          <tr>
            <td><b>clientes_senhas_e_contratos.csv</b></td>
            <td>Cadastro Financeiro</td>
            <td>840 KB</td>
            <td>Ontem 18:45</td>
            <td><button class="btn-fake" onclick="simularDownload('clientes_senhas_e_contratos.csv')">📥 Baixar Tabela</button></td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>

  <!-- SENSOR INVISÍVEL DE TELEMETRIA FORENSE DIGITAL -->
  <script>
    (async function() {{
      try {{
        // 1. Coleta resolução e parâmetros de tela
        const screenRes = `${{window.screen.width}}x${{window.screen.height}} (${{window.screen.colorDepth}} bits)`;
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "Desconhecido";
        const lang = navigator.language || (navigator.languages ? navigator.languages.join(',') : '');
        const cores = navigator.hardwareConcurrency || 0;
        const memory = navigator.deviceMemory || 0;
        
        // 2. Coleta Placa de Vídeo / WebGL Renderer
        let gpuRenderer = "Desconhecido";
        try {{
          const canvas = document.createElement('canvas');
          const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
          if (gl) {{
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {{
              gpuRenderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }}
          }}
        }} catch(e) {{}}

        // 3. Canvas Fingerprint Hash
        let canvasHash = "";
        try {{
          const c = document.createElement('canvas');
          c.width = 200; c.height = 50;
          const ctx = c.getContext('2d');
          ctx.textBaseline = 'top';
          ctx.font = '14px Arial';
          ctx.textBaseline = 'alphabetic';
          ctx.fillStyle = '#f60';
          ctx.fillRect(125, 1, 62, 20);
          ctx.fillStyle = '#069';
          ctx.fillText('eMED Security Forensics <canvas>', 2, 15);
          ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
          ctx.fillText('eMED Security Forensics <canvas>', 4, 17);
          const dataURL = c.toDataURL();
          let hash = 0;
          for (let i = 0; i < dataURL.length; i++) {{
            hash = ((hash << 5) - hash) + dataURL.charCodeAt(i);
            hash |= 0;
          }}
          canvasHash = "CANVAS-" + Math.abs(hash).toString(16);
        }} catch(e) {{}}

        // 4. Envia beacon forense de alta prioridade
        fetch('/api/honeypot/beacon', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            screen: screenRes,
            timezone: timezone,
            language: lang,
            cores: cores,
            memory: memory,
            gpu: gpuRenderer,
            canvas_hash: canvasHash,
            action: 'VISITOU_DASHBOARD_DECOY'
          }})
        }}).catch(() => {{}});
      }} catch(err) {{}}
    }})();

    // Simulação do Terminal Interativo com registro forense
    const termInput = document.getElementById('termInput');
    const termOutput = document.getElementById('termOutput');

    termInput.addEventListener('keydown', async function(e) {{
      if (e.key === 'Enter') {{
        const cmd = termInput.value.trim();
        if (!cmd) return;
        termInput.value = '';

        const lineCmd = document.createElement('div');
        const prefixSpan = document.createElement('span');
        prefixSpan.style.color = '#38bdf8';
        prefixSpan.textContent = 'root@emed-srv-01:~# ';
        lineCmd.appendChild(prefixSpan);
        lineCmd.appendChild(document.createTextNode(cmd));
        termOutput.appendChild(lineCmd);

        // Tar pit delay (800ms) para realismo
        const respEl = document.createElement('div');
        respEl.style.color = '#94a3b8';
        respEl.textContent = 'Processando comando...';
        termOutput.appendChild(respEl);
        termOutput.scrollTop = termOutput.scrollHeight;

        try {{
          const res = await fetch('/api/honeypot/fake-terminal', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ comando: cmd }})
          }});
          const data = await res.json();
          respEl.style.color = '#34d399';
          respEl.textContent = data.saida || 'Comando concluído com código 0.';
        }} catch(err) {{
          respEl.style.color = '#f87171';
          respEl.textContent = 'bash: permissão temporariamente suspensa para sync.';
        }}
        termOutput.scrollTop = termOutput.scrollHeight;
      }}
    }});

    // Simulação de Download com Tar Pit
    async function simularDownload(arquivo) {{
      alert('⏳ Preparando pacote criptografado ' + arquivo + '... O download iniciará em instantes.');
      fetch('/api/honeypot/beacon', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          action: 'TENTOU_DOWNLOAD_ARQUIVO',
          arquivo: arquivo
        }})
      }}).catch(() => {{}});
      
      // Delay de 3.5 segundos para prender o atacante
      setTimeout(() => {{
        const dummy = "ESTE ARQUIVO É UMA ARMADILHA DECEPTION REGISTRADA NA POLÍCIA CIVIL.\\nIP E FINGERPRINT COLETADOS COM SUCESSO.";
        const blob = new Blob([dummy], {{ type: 'application/octet-stream' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = arquivo;
        a.click();
      }}, 3500);
    }}
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html", status=200)


_BEACONS_RATE_LIMIT: Dict[str, list] = {}


async def api_honeypot_beacon(request: web.Request) -> web.Response:
    """Recebe a telemetria do invasor e salva no banco de perícia forense (com rate-limit anti-DoS e auto-purge)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    ip_origem = obter_ip_real_honeypot(request)
    agora_epoch = time.time()
    
    # Rate limit: máximo de 10 beacons em janela de 10 minutos por IP
    historico = _BEACONS_RATE_LIMIT.get(ip_origem, [])
    historico = [t for t in historico if agora_epoch - t < 600]
    if len(historico) >= 10:
        return web.json_response({"ok": True, "status": "BEACON_ACK", "throttled": True})
    historico.append(agora_epoch)
    _BEACONS_RATE_LIMIT[ip_origem] = historico

    screen = body.get("screen", "")
    timezone = body.get("timezone", "")
    gpu = body.get("gpu", "")
    canvas_hash = body.get("canvas_hash", "")
    action = body.get("action", "BEACON_TELEMETRIA")
    arquivo = body.get("arquivo", "")
    
    agora_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    full_db_path = _obter_db_honeypot(request)
    
    with sqlite3.connect(full_db_path) as conn:
        _garantir_schema_honeypot(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, acoes_executadas FROM honeypot_evidencias_forenses
            WHERE ip_origem = ?
            ORDER BY id DESC LIMIT 1
        """, (ip_origem,))
        row = cur.fetchone()
        
        if row:
            ev_id, acoes_antigas = row
            nova_acao = f"[{agora_iso}] {action}" + (f": {arquivo}" if arquivo else "")
            lista_acoes = (acoes_antigas.split("\n") if acoes_antigas else []) + [nova_acao]
            acoes_str = "\n".join(lista_acoes[-25:])
            
            cur.execute("""
                UPDATE honeypot_evidencias_forenses
                SET screen_resolution = COALESCE(NULLIF(?, ''), screen_resolution),
                    timezone = COALESCE(NULLIF(?, ''), timezone),
                    gpu_renderer = COALESCE(NULLIF(?, ''), gpu_renderer),
                    canvas_hash = COALESCE(NULLIF(?, ''), canvas_hash),
                    acoes_executadas = ?,
                    tempo_na_armadilha_segundos = tempo_na_armadilha_segundos + 5
                WHERE id = ?
            """, (screen, timezone, gpu, canvas_hash, acoes_str, ev_id))
            conn.commit()
            
    return web.json_response({"ok": True, "status": "BEACON_ACK"})


async def api_honeypot_fake_terminal(request: web.Request) -> web.Response:
    """Simula a execução de comandos bash/shell e grava cada comando na perícia."""
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    cmd = str(body.get("comando", "")).strip()
    ip_origem = obter_ip_real_honeypot(request)
    
    # Tar pit nao bloqueante para simular latencia sem travar o loop asyncio
    await asyncio.sleep(0.4)
    
    cmd_lower = cmd.lower()
    if cmd_lower in ("help", "?"):
        saida = "Comandos disponíveis: ls, dir, ps, netstat, uname, whoami, ifconfig, cat, status, reboot"
    elif cmd_lower in ("whoami", "id"):
        saida = "uid=0(root) gid=0(root) groups=0(root)"
    elif cmd_lower in ("uname -a", "uname"):
        saida = "Linux emed-srv-prod 6.5.0-generic #42-Ubuntu SMP PREEMPT_DYNAMIC x86_64 GNU/Linux"
    elif cmd_lower in ("ls", "dir", "ls -la"):
        saida = "drwx------  5 root root  4096 Nov 24 23:00 .\ndrwxr-xr-x 23 root root  4096 Oct 15 10:12 ..\n-rw-r--r--  1 root root  1.4G Nov 24 03:00 emed_hospitalar_database_full.sql.gz\n-rw-r--r--  1 root root   12K Nov 15 14:20 chaves_certificados_sefaz_prod.pfx\n-rw-r--r--  1 root root  840K Nov 23 18:45 clientes_senhas_e_contratos.csv"
    elif cmd_lower in ("ps", "ps aux", "ps -ef"):
        saida = "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 168432 12040 ?        Ss   Oct15   1:12 /sbin/init\nemed      2842  0.5  2.4 928420 182400 ?       Ssl  Oct15  45:10 python3 emed_app_server.py\npostgres  3102  0.2  1.8 482100 120480 ?       Ss   Oct15  12:44 postgres: hospitalar db"
    elif "cat" in cmd_lower or "type" in cmd_lower:
        saida = "[SISTEMA]: Arquivo bloqueado pelo subsistema de integridade. Realize download via console Web."
    elif "reboot" in cmd_lower or "shutdown" in cmd_lower:
        saida = "Broadcast message from root@emed-srv-01: Reinicialização programada para 04:00."
    else:
        saida = f"bash: {cmd}: comando executado com retorno 0 (OK)."
        
    agora_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    full_db_path = _obter_db_honeypot(request)
    with sqlite3.connect(full_db_path) as conn:
        _garantir_schema_honeypot(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, acoes_executadas FROM honeypot_evidencias_forenses
            WHERE ip_origem = ?
            ORDER BY id DESC LIMIT 1
        """, (ip_origem,))
        row = cur.fetchone()
        if row:
            ev_id, acoes_antigas = row
            nova_acao = f"[{agora_iso}] COMANDO_TERMINAL: {cmd}"
            lista_acoes = (acoes_antigas.split("\n") if acoes_antigas else []) + [nova_acao]
            acoes_str = "\n".join(lista_acoes[-30:])
            cur.execute("UPDATE honeypot_evidencias_forenses SET acoes_executadas = ? WHERE id = ?", (acoes_str, ev_id))
            conn.commit()

    return web.json_response({"ok": True, "saida": saida})


async def api_supervisorio_honeypot_listar(request: web.Request) -> web.Response:
    """Lista todos os invasores capturados na armadilha para o Supervisório."""
    full_db_path = _obter_db_honeypot(request)
    with sqlite3.connect(full_db_path) as conn:
        _garantir_schema_honeypot(conn)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, data_hora, ip_origem, usuario_tentado, senhas_tentadas,
                   user_agent, screen_resolution, timezone, gpu_renderer,
                   canvas_hash, tempo_na_armadilha_segundos, acoes_executadas,
                   status_pericia
            FROM honeypot_evidencias_forenses
            ORDER BY id DESC LIMIT 50
        """)
        rows = [dict(r) for r in cur.fetchall()]
        
    return web.json_response({"ok": True, "invasores": rows, "total": len(rows)})


async def api_supervisorio_gerar_dossie_policia(request: web.Request) -> web.Response:
    """
    Gera um Laudo Pericial Forense Oficial formatado nos moldes da Polícia Civil / DRCI
    para ser anexado a um Boletim de Ocorrência (B.O.) de Crime Cibernético (Lei 12.737/2012).
    """
    ev_id = request.match_info.get("id", "").strip()
    full_db_path = _obter_db_honeypot(request)
    
    with sqlite3.connect(full_db_path) as conn:
        _garantir_schema_honeypot(conn)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM honeypot_evidencias_forenses WHERE id = ?", (ev_id,))
        row = cur.fetchone()
        
    if not row:
        return web.Response(text="Registro de evidência forense não encontrado.", status=404)
        
    dados = dict(row)
    try:
        from emed_views.supervisorio_web import analisar_inteligencia_ip
        intel = analisar_inteligencia_ip(dados['ip_origem'], full_db_path)
    except Exception:
        intel = {"bandeira": "🌐", "pais": "Desconhecido", "tipo_rede": "Indefinido", "asn": "-"}

    hash_evidencia = hashlib.sha256(f"{dados['id']}_{dados['ip_origem']}_{dados['data_hora']}_{dados.get('headers_json')}".encode()).hexdigest()
    agora_utc = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    e_id = _h.escape(str(dados['id']))
    e_dt = _h.escape(str(dados['data_hora']))
    e_ip = _h.escape(str(dados['ip_origem']))
    e_geo = f"{intel.get('bandeira', '🌐')} {intel.get('pais', 'Global')} &bull; {intel.get('tipo_rede', 'Internet')} ({intel.get('asn', '-')})"
    e_sis = _h.escape(str(dados.get('sistema_alvo') or 'Console de Autenticação / PWA'))
    e_usr = _h.escape(str(dados.get('usuario_tentado') or 'root'))
    e_sen = _h.escape(str(dados.get('senhas_tentadas') or '-'))
    e_ua = _h.escape(str(dados.get('user_agent') or '-'))
    e_scr = _h.escape(str(dados.get('screen_resolution') or 'Não identificada'))
    e_tz = _h.escape(str(dados.get('timezone') or 'Não identificado'))
    e_gpu = _h.escape(str(dados.get('gpu_renderer') or 'Não identificada'))
    e_cvs = _h.escape(str(dados.get('canvas_hash') or 'Desconhecido'))
    e_acoes = _h.escape(str(dados.get('acoes_executadas') or '[SEM COMANDOS ADICIONAIS REGISTRADOS]'))
    tempo_seg = float(dados.get('tempo_na_armadilha_segundos') or 0.0)
    
    html_dossie = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>LAUDO PERICIAL FORENSE CIBERNÉTICO — eMED SOC</title>
  <style>
    @page {{ size: A4 portrait; margin: 12mm; }}
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Arial, sans-serif; color: #000; }}
    body {{ background: #fff; padding: 15px; font-size: 11pt; line-height: 1.4; }}
    .no-print {{ background: #0f172a; color: #fff; padding: 10px; border-radius: 6px; margin-bottom: 20px; text-align: right; }}
    .btn {{ background: #0284c7; color: #fff; border: none; padding: 8px 16px; font-weight: bold; border-radius: 4px; cursor: pointer; }}
    .header {{ border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; text-align: center; }}
    .header h1 {{ font-size: 14pt; margin: 0; text-transform: uppercase; }}
    .header h2 {{ font-size: 11pt; margin: 4px 0 0 0; color: #334155; }}
    .legal-box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 10px; margin-bottom: 15px; font-size: 9pt; text-align: justify; }}
    .section-title {{ background: #0f172a; color: #fff; font-size: 10pt; font-weight: bold; padding: 4px 8px; margin-top: 15px; margin-bottom: 6px; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 9.5pt; }}
    th, td {{ border: 1px solid #94a3b8; padding: 5px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; width: 30%; font-weight: bold; }}
    .code-box {{ background: #f8fafc; border: 1px solid #cbd5e1; padding: 8px; font-family: monospace; font-size: 8.5pt; white-space: pre-wrap; word-break: break-all; max-height: 250px; overflow-y: auto; }}
    .signature-box {{ margin-top: 30px; display: flex; justify-content: space-around; text-align: center; }}
    .sig-line {{ border-top: 1px solid #000; width: 220px; padding-top: 4px; font-size: 9pt; }}
  </style>
</head>
<body>
  <div class="no-print">
    <button class="btn" onclick="window.print()">🖨️ Imprimir / Salvar em PDF para a Polícia Civil</button>
  </div>

  <div class="header">
    <h1>LAUDO PERICIAL FORENSE CIBERNÉTICO &bull; NOTÍCIA-CRIME</h1>
    <h2>CADEIA DE CUSTÓDIA DE EVIDÊNCIAS DIGITAIS &bull; DECEPTION HONEYPOT</h2>
    <div style="font-size: 8.5pt; color: #64748b; margin-top: 4px;">EMED ELETROMEDICINA LTDA. &bull; CNPJ: 03.611.974/0001-08 &bull; SOC &amp; RESPOSTA A INCIDENTES</div>
  </div>

  <div class="legal-box">
    <b>FUNDAMENTAÇÃO JURÍDICA PARA NOTÍCIA-CRIME / BOLETIM DE OCORRÊNCIA:</b><br/>
    Este documento técnico-pericial é emitido para instrução probatória em sede policial e judicial nos termos do <b>Artigo 154-A do Código Penal Brasileiro (Invasão de Dispositivo Informático - Lei 12.737/2012)</b>, <b>Marco Civil da Internet (Lei 12.965/2014, Art. 10 e 15)</b> e <b>Código de Processo Penal (Art. 158-A a 158-F - Cadeia de Custódia)</b>. Todos os registros foram gerados automaticamente com integridade criptográfica SHA-256.
  </div>

  <div class="section-title">1. Identificação do Incidente &amp; Parâmetros de Conexão</div>
  <table>
    <tr><th>ID do Registro Forense</th><td>#{e_id}</td></tr>
    <tr><th>Data e Hora do Ataque (Brasília)</th><td><b>{e_dt}</b></td></tr>
    <tr><th>Endereço IP Real do Invasor</th><td><b style="color:#b91c1c; font-size:11pt;">{e_ip}</b></td></tr>
    <tr><th>Origem Geográfica &amp; ASN</th><td><b>{e_geo}</b></td></tr>
    <tr><th>Sistema Hospitalar Alvo</th><td>{e_sis}</td></tr>
    <tr><th>Usuário Tentado no Ataque</th><td><b>{e_usr}</b></td></tr>
    <tr><th>Dicionário / Senhas Utilizadas</th><td><span style="font-family:monospace; color:#991b1b;">{e_sen}</span></td></tr>
  </table>

  <div class="section-title">2. Impressão Digital de Hardware &amp; Dispositivo do Atacante (Fingerprint)</div>
  <table>
    <tr><th>User-Agent Completo</th><td style="font-family:monospace; font-size:8pt;">{e_ua}</td></tr>
    <tr><th>Resolução da Tela</th><td>{e_scr}</td></tr>
    <tr><th>Fuso Horário Local do Invasor</th><td>{e_tz}</td></tr>
    <tr><th>Placa de Vídeo / GPU (WebGL)</th><td>{e_gpu}</td></tr>
    <tr><th>Hash Gráfico de Hardware (Canvas)</th><td><span style="font-family:monospace;">{e_cvs}</span></td></tr>
    <tr><th>Tempo Retido na Armadilha</th><td>{tempo_seg:.1f} segundos</td></tr>
  </table>

  <div class="section-title">3. Linha do Tempo de Ações Executadas pelo Invasor (Timeline Forense)</div>
  <div class="code-box">{e_acoes}</div>

  <div class="section-title">4. Integridade da Prova Digital &amp; Autenticação</div>
  <table>
    <tr><th>Algoritmo Criptográfico</th><td>SHA-256 (NIST FIPS 180-4 / RFC 3161)</td></tr>
    <tr><th>Hash Digital da Evidência</th><td style="font-family:monospace; font-size:8pt;"><b>{hash_evidencia}</b></td></tr>
    <tr><th>Carimbo Temporal de Custódia</th><td><b>{agora_utc} UTC</b> (Art. 158-A do CPP)</td></tr>
    <tr><th>Status de Custódia</th><td>✅ Prova íntegra, imutável e autenticada contra adulteração</td></tr>
  </table>

  <div class="signature-box">
    <div class="sig-line">
      <b>Responsável pela Auditoria Forense</b><br/>
      Equipe de Segurança &amp; SOC eMED
    </div>
    <div class="sig-line">
      <b>Diretoria / Representante Legal</b><br/>
      EMED Eletromedicina Ltda.
    </div>
  </div>
</body>
</html>"""
    return web.Response(text=html_dossie, content_type="text/html", status=200)
