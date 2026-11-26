# -*- coding: utf-8 -*-
"""
supervisorio_web.py — Centro de Supervisão, Auditoria Contínua & Defesa Cibernética Ativa (SOC eMED)
Monitora em tempo real:
- Todas as tentativas de login (PWA, Portal do Cliente, Portal Fiscal, EmedNav).
- Defesa ativa contra robôs/botnets e tentativas de força bruta (Auto-Ban e Rate Limiting).
- Varredura heurística contra mineradores clandestinos de criptomoedas (XMRig, Stratum, etc.).
- Telemetria de hardware (CPU, Memória, Portas e Sockets de rede).
"""

import os
import time
import json
import sqlite3
import datetime
import html as _h
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from aiohttp import web

try:
    import psutil
except ImportError:
    psutil = None

# Cache em memória para consulta ultra-rápida de IPs bloqueados (microsegundos)
_IPS_BLOQUEADOS_CACHE: Dict[str, float] = {}  # {ip: expira_timestamp}
_FALHAS_RECENTES_IP: Dict[str, List[float]] = {}  # {ip: [timestamp_falhas]}

MINER_SIGNATURES = [
    "xmrig", "miner", "monero", "xmr", "stratum", "cpuminer", "ethminer",
    "ccminer", "nicehash", "cryptonight", "coinhive", "kdevtmpfsi", "kinsing",
    "p2pool", "nanopool", "supportxmr", "c3pool", "hashvault", "minergate"
]

MINING_PORTS = {3333, 4444, 5555, 7777, 8888, 9999, 14433, 14444, 45560}

KNOWN_BOT_AGENTS = [
    "sqlmap", "nikto", "masscan", "nmap", "dirbuster", "gobuster",
    "wpscan", "zgrab", "shodan", "censys", "curl", "python-requests"
]


def _obter_db_path(app: Optional[web.Application] = None) -> str:
    if app and app.get("db_name"):
        return str(app["db_name"])
    return str(Path(__file__).resolve().parent.parent / "emed.db")


def garantir_schema_supervisorio(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_tentativas_login (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            timestamp_epoch REAL NOT NULL,
            tipo_sistema TEXT NOT NULL,
            usuario_tentado TEXT NOT NULL,
            ip_origem TEXT NOT NULL,
            status_resultado TEXT NOT NULL,
            motivo_detalhado TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            dispositivo_info TEXT DEFAULT '',
            geoloc_info TEXT DEFAULT '',
            bloqueio_ativo INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_dt ON auditoria_tentativas_login(data_hora)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_ip ON auditoria_tentativas_login(ip_origem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_st ON auditoria_tentativas_login(status_resultado)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ips_bloqueados_seguranca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE NOT NULL,
            motivo TEXT NOT NULL,
            bloqueado_em TEXT NOT NULL,
            expira_em TEXT DEFAULT '',
            bloqueado_por TEXT DEFAULT 'SISTEMA_SUPERVISORIO',
            ativo INTEGER DEFAULT 1
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ips_bloq_ativo ON ips_bloqueados_seguranca(ip, ativo)")


def recarregar_cache_ips_bloqueados(db_path: str) -> None:
    global _IPS_BLOQUEADOS_CACHE
    agora = time.time()
    try:
        with sqlite3.connect(db_path) as conn:
            garantir_schema_supervisorio(conn)
            cur = conn.cursor()
            rows = cur.execute("SELECT ip, expira_em FROM ips_bloqueados_seguranca WHERE ativo = 1").fetchall()
            novo_cache = {}
            for ip, exp_str in rows:
                if not exp_str or exp_str == "PERMANENTE":
                    novo_cache[ip] = agora + 86400 * 365
                else:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(exp_str)
                        exp_ts = exp_dt.timestamp()
                        if exp_ts > agora:
                            novo_cache[ip] = exp_ts
                    except Exception:
                        novo_cache[ip] = agora + 3600
            _IPS_BLOQUEADOS_CACHE = novo_cache
    except Exception as e:
        print(f"[SUPERVISORIO] Erro ao recarregar cache de IPs bloqueados: {e}")


def verificar_ip_bloqueado(ip: str, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """Verifica instantaneamente se o IP está em quarentena ou bloqueado por ataque."""
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return False, ""

    agora = time.time()
    exp_ts = _IPS_BLOQUEADOS_CACHE.get(ip)
    if exp_ts:
        if exp_ts > agora:
            return True, "IP bloqueado por múltiplas tentativas incorretas ou atividade suspeita de robô."
        else:
            _IPS_BLOQUEADOS_CACHE.pop(ip, None)

    if db_path:
        try:
            with sqlite3.connect(db_path) as conn:
                r = conn.execute("SELECT motivo, expira_em FROM ips_bloqueados_seguranca WHERE ip = ? AND ativo = 1", (ip,)).fetchone()
                if r:
                    motivo, exp_str = r[0], r[1]
                    if not exp_str or exp_str == "PERMANENTE":
                        _IPS_BLOQUEADOS_CACHE[ip] = agora + 86400 * 365
                        return True, motivo
                    try:
                        exp_ts = datetime.datetime.fromisoformat(exp_str).timestamp()
                        if exp_ts > agora:
                            _IPS_BLOQUEADOS_CACHE[ip] = exp_ts
                            return True, motivo
                        else:
                            conn.execute("UPDATE ips_bloqueados_seguranca SET ativo = 0 WHERE ip = ?", (ip,))
                            conn.commit()
                    except Exception:
                        pass
        except Exception:
            pass

    return False, ""


def registrar_auditoria_login(
    tipo_sistema: str,
    usuario: str,
    ip: str,
    status: str,
    motivo: str = "",
    user_agent: str = "",
    dispositivo: str = "",
    db_path: Optional[str] = None
) -> None:
    """Grava formalmente toda e qualquer tentativa de login no banco e aplica Auto-Ban contra robôs."""
    db_p = db_path or _obter_db_path()
    agora_dt = datetime.datetime.now()
    agora_str = agora_dt.strftime("%d/%m/%Y %H:%M:%S")
    agora_epoch = agora_dt.timestamp()

    # Detecção de User-Agent robótico conhecido
    ua_lower = (user_agent or "").lower()
    is_bot_ua = any(bot in ua_lower for bot in KNOWN_BOT_AGENTS)
    if is_bot_ua and status != "SUCESSO":
        status = "BOT_SCANNER_DETECTADO"
        motivo = f"Varredor automatizado detectado no User-Agent ({user_agent[:40]})"

    # Verificação de Auto-Ban por Brute-Force
    bloqueio_gerado = 0
    if status in ("SENHA_INCORRETA", "USUARIO_INEXISTENTE", "BOT_SCANNER_DETECTADO"):
        lista = _FALHAS_RECENTES_IP.get(ip, [])
        lista = [t for t in lista if agora_epoch - t < 300]  # janela de 5 minutos
        lista.append(agora_epoch)
        _FALHAS_RECENTES_IP[ip] = lista

        # Mais de 5 falhas ou bot detectado -> Auto-Ban de 15 minutos (ou 24h para bots)
        duracao_min = 60 if is_bot_ua else 15
        if len(lista) >= 5 or is_bot_ua:
            bloqueio_gerado = 1
            expira_iso = (agora_dt + datetime.timedelta(minutes=duracao_min)).isoformat()
            _IPS_BLOQUEADOS_CACHE[ip] = agora_epoch + (duracao_min * 60)
            try:
                with sqlite3.connect(db_p) as conn:
                    garantir_schema_supervisorio(conn)
                    conn.execute("""
                        INSERT INTO ips_bloqueados_seguranca (ip, motivo, bloqueado_em, expira_em, bloqueado_por, ativo)
                        VALUES (?, ?, ?, ?, 'AUTO_DEFESA_SUPERVISORIO', 1)
                        ON CONFLICT(ip) DO UPDATE SET
                            motivo = excluded.motivo,
                            bloqueado_em = excluded.bloqueado_em,
                            expira_em = excluded.expira_em,
                            ativo = 1
                    """, (ip, f"Excesso de tentativas incorretas ({len(lista)} em 5min)", agora_str, expira_iso))
                    conn.commit()
            except Exception as e:
                print(f"[SUPERVISORIO] Erro ao registrar auto-ban para {ip}: {e}")

    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            conn.execute("""
                INSERT INTO auditoria_tentativas_login (
                    data_hora, timestamp_epoch, tipo_sistema, usuario_tentado,
                    ip_origem, status_resultado, motivo_detalhado, user_agent,
                    dispositivo_info, geoloc_info, bloqueio_ativo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
            """, (
                agora_str, agora_epoch, tipo_sistema, (usuario or 'ANONIMO').upper(),
                ip, status, motivo, user_agent[:250], dispositivo[:200], bloqueio_gerado
            ))
            conn.commit()
    except Exception as e:
        print(f"[SUPERVISORIO] Erro ao persistir auditoria de login: {e}")


def executar_varredura_ameacas_servidor(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Realiza varredura forense ativa nos processos, conexões, portas e integridade do servidor."""
    agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    resultado = {
        "timestamp": agora_str,
        "status": "SEGURO",
        "cpu_percent": 0.0,
        "ram_percent": 0.0,
        "ram_usada_gb": 0.0,
        "ram_total_gb": 0.0,
        "processos_analisados": 0,
        "processos_suspeitos": [],
        "conexoes_suspeitas": [],
        "portas_mineracao_abertas": [],
        "alertas": [],
        "servicos_emed_ativos": []
    }

    if not psutil:
        resultado["alertas"].append("Biblioteca psutil não disponível para telemetria em tempo real.")
        return resultado

    # 1. Telemetria de CPU e Memória
    try:
        resultado["cpu_percent"] = psutil.cpu_percent(interval=0.2)
        vmem = psutil.virtual_memory()
        resultado["ram_percent"] = vmem.percent
        resultado["ram_usada_gb"] = round(vmem.used / (1024**3), 1)
        resultado["ram_total_gb"] = round(vmem.total / (1024**3), 1)
    except Exception as e:
        resultado["alertas"].append(f"Erro ao ler CPU/RAM: {e}")

    # 2. Varredura Heurística em Todos os Processos Ativos
    proc_count = 0
    procs_suspeitos = []
    emed_procs = []

    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'cpu_percent']):
        try:
            proc_count += 1
            p_name = str(proc.info['name'] or '').lower()
            p_cmd = " ".join(proc.info['cmdline'] or []).lower()
            p_exe = str(proc.info['exe'] or '').lower()
            pid = proc.info['pid']

            # Verifica serviços oficiais eMED
            if "emed" in p_cmd or "app_emed" in p_cmd or "emed_nav" in p_cmd:
                emed_procs.append({"pid": pid, "nome": proc.info['name'], "cmd": p_cmd[:80]})

            # Busca por mineradores e botnets
            for sig in MINER_SIGNATURES:
                if sig in p_name or sig in p_cmd:
                    procs_suspeitos.append({
                        "pid": pid,
                        "nome": proc.info['name'],
                        "motivo": f"Assinatura de criptomineração detectada: '{sig}'",
                        "cmd": p_cmd[:120]
                    })
                    break

            # Processos executando da pasta Temp (exceto python/compiladores autorizados)
            if ("\\temp\\" in p_exe or "\\local\\temp\\" in p_exe) and not any(ok in p_name for ok in ["python", "powershell", "code", "node", "git"]):
                procs_suspeitos.append({
                    "pid": pid,
                    "nome": proc.info['name'],
                    "motivo": f"Executável rodando em diretório temporário: {p_exe}",
                    "cmd": p_cmd[:120]
                })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    resultado["processos_analisados"] = proc_count
    resultado["processos_suspeitos"] = procs_suspeitos
    resultado["servicos_emed_ativos"] = emed_procs

    # 3. Varredura de Conexões de Rede em Portas de Pools de Mineração
    conns_suspeitas = []
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.status == 'ESTABLISHED' and conn.raddr:
                r_ip, r_port = conn.raddr
                if r_port in MINING_PORTS:
                    conns_suspeitas.append({
                        "pid": conn.pid,
                        "ip_destino": r_ip,
                        "porta_destino": r_port,
                        "motivo": "Conexão ativa em porta típica de pool de mineração"
                    })
    except Exception:
        pass

    resultado["conexoes_suspeitas"] = conns_suspeitas

    # Classificação de Risco
    if procs_suspeitos or conns_suspeitas:
        resultado["status"] = "AMEACA_DETECTADA"
        resultado["alertas"].append("⚠️ Ameaça cibernética ativa detectada! Verifique os processos suspeitos imediatamente.")
    elif resultado["cpu_percent"] > 85.0:
        resultado["status"] = "ALERTA_SOBRECARGA"
        resultado["alertas"].append("Atenção: Uso de CPU elevado acima de 85%. Pode indicar processo oculto em execução.")
    else:
        resultado["status"] = "SEGURO"

    return resultado


# =========================================================================
# HANDLERS HTTP DA API DO SISTEMA SUPERVISÓRIO
# =========================================================================

async def api_supervisorio_metricas(request: web.Request) -> web.Response:
    """Retorna métricas em tempo real de hardware, ameaças e auditoria das últimas 24h."""
    db_name = _obter_db_path(request.app)
    recarregar_cache_ips_bloqueados(db_name)

    # 1. Telemetria do Servidor
    varredura = executar_varredura_ameacas_servidor(db_name)

    # 2. Auditoria e Métricas de Tentativas de Login
    total_24h = 0
    sucessos_24h = 0
    falhas_24h = 0
    bloqueios_24h = 0
    top_ips = []
    ips_bloqueados_list = []

    try:
        with sqlite3.connect(db_name) as conn:
            garantir_schema_supervisorio(conn)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Janela de 24 horas
            limite_epoch = time.time() - 86400

            total_24h = cur.execute("SELECT count(*) FROM auditoria_tentativas_login WHERE timestamp_epoch >= ?", (limite_epoch,)).fetchone()[0]
            sucessos_24h = cur.execute("SELECT count(*) FROM auditoria_tentativas_login WHERE timestamp_epoch >= ? AND status_resultado = 'SUCESSO'", (limite_epoch,)).fetchone()[0]
            falhas_24h = cur.execute("SELECT count(*) FROM auditoria_tentativas_login WHERE timestamp_epoch >= ? AND status_resultado != 'SUCESSO'", (limite_epoch,)).fetchone()[0]
            bloqueios_24h = cur.execute("SELECT count(*) FROM auditoria_tentativas_login WHERE timestamp_epoch >= ? AND (bloqueio_ativo = 1 OR status_resultado LIKE 'BLOQUE%')", (limite_epoch,)).fetchone()[0]

            top_ips = [dict(r) for r in cur.execute("""
                SELECT ip_origem, count(*) as tentativas,
                       SUM(CASE WHEN status_resultado != 'SUCESSO' THEN 1 ELSE 0 END) as falhas
                FROM auditoria_tentativas_login
                WHERE timestamp_epoch >= ?
                GROUP BY ip_origem
                ORDER BY falhas DESC, tentativas DESC
                LIMIT 5
            """, (limite_epoch,)).fetchall()]

            ips_bloqueados_list = [dict(r) for r in cur.execute("""
                SELECT id, ip, motivo, bloqueado_em, expira_em, bloqueado_por
                FROM ips_bloqueados_seguranca
                WHERE ativo = 1
                ORDER BY id DESC
            """).fetchall()]

            try:
                honeypot_total = cur.execute("SELECT count(*) FROM honeypot_evidencias_forenses").fetchone()[0]
            except Exception:
                honeypot_total = 0

    except Exception as e:
        print(f"[SUPERVISORIO] Erro nas métricas: {e}")

    return web.json_response({
        "ok": True,
        "hardware": {
            "cpu_percent": varredura["cpu_percent"],
            "ram_percent": varredura["ram_percent"],
            "ram_usada_gb": varredura["ram_usada_gb"],
            "ram_total_gb": varredura["ram_total_gb"],
        },
        "seguranca": {
            "status_geral": varredura["status"],
            "processos_analisados": varredura["processos_analisados"],
            "processos_suspeitos_qtd": len(varredura["processos_suspeitos"]),
            "conexoes_mineracao_qtd": len(varredura["conexoes_suspeitas"]),
            "alertas": varredura["alertas"],
            "honeypot_total": honeypot_total,
        },
        "auditoria_24h": {
            "total_tentativas": total_24h,
            "sucessos": sucessos_24h,
            "falhas": falhas_24h,
            "bloqueios_anti_robo": bloqueios_24h,
            "top_ips_ofensores": top_ips,
            "ips_bloqueados_ativos": ips_bloqueados_list,
        }
    })


async def api_supervisorio_auditoria_listar(request: web.Request) -> web.Response:
    """Lista o histórico detalhado de tentativas de login com filtros e paginação."""
    db_name = _obter_db_path(request.app)
    status_filtro = request.query.get("status", "TODOS").strip().upper()
    sistema_filtro = request.query.get("sistema", "TODOS").strip().upper()
    busca = request.query.get("busca", "").strip()
    limite = min(int(request.query.get("limit", 60)), 300)

    query = "SELECT * FROM auditoria_tentativas_login WHERE 1=1"
    params = []

    if status_filtro == "FALHAS":
        query += " AND status_resultado != 'SUCESSO'"
    elif status_filtro == "SUCESSO":
        query += " AND status_resultado = 'SUCESSO'"
    elif status_filtro == "BLOQUEADOS":
        query += " AND (bloqueio_ativo = 1 OR status_resultado LIKE 'BLOQUE%')"

    if sistema_filtro != "TODOS":
        query += " AND UPPER(tipo_sistema) = ?"
        params.append(sistema_filtro)

    if busca:
        query += " AND (UPPER(usuario_tentado) LIKE ? OR ip_origem LIKE ? OR motivo_detalhado LIKE ?)"
        b_term = f"%{busca.upper()}%"
        params.extend([b_term, b_term, b_term])

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limite)

    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

    return web.json_response({"ok": True, "total": len(rows), "auditoria": rows})


async def api_supervisorio_exportar_csv(request: web.Request) -> web.Response:
    """Exporta o log integral de auditoria de logins em CSV padronizado RFC 4180 UTF-8 BOM."""
    db_name = _obter_db_path(request.app)
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM auditoria_tentativas_login ORDER BY id DESC LIMIT 5000").fetchall()

    csv_lines = [
        "\ufeff\"ID\";\"DATA_HORA\";\"SISTEMA\";\"USUARIO\";\"IP_ORIGEM\";\"STATUS\";\"MOTIVO\";\"USER_AGENT\";\"BLOQUEADO\""
    ]
    for r in rows:
        ua_limpo = str(r["user_agent"] or "").replace('"', '""')
        mot_limpo = str(r["motivo_detalhado"] or "").replace('"', '""')
        csv_lines.append(
            f'"{r["id"]}";"{r["data_hora"]}";"{r["tipo_sistema"]}";"{r["usuario_tentado"]}";"{r["ip_origem"]}";'
            f'"{r["status_resultado"]}";"{mot_limpo}";"{ua_limpo}";"{r["bloqueio_ativo"]}"'
        )

    csv_data = "\r\n".join(csv_lines).encode("utf-8")
    nome_arq = f"auditoria_logins_emed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return web.Response(
        body=csv_data,
        content_type="text/csv",
        charset="utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arq}"'}
    )


async def api_supervisorio_ip_bloquear(request: web.Request) -> web.Response:
    """Bloqueia manualmente um IP suspeito a partir do painel supervisório."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    ip = str(body.get("ip", "")).strip()
    motivo = str(body.get("motivo", "Bloqueio Manual efetuado pelo Gestor")).strip()
    horas = int(body.get("horas", 24))

    if not ip or len(ip) < 7:
        return web.json_response({"ok": False, "msg": "Informe um endereço IP válido."}, status=400)

    agora_dt = datetime.datetime.now()
    exp_iso = (agora_dt + datetime.timedelta(hours=horas)).isoformat() if horas > 0 else "PERMANENTE"
    exp_epoch = (agora_dt + datetime.timedelta(hours=horas)).timestamp() if horas > 0 else agora_dt.timestamp() + (86400 * 365)
    _IPS_BLOQUEADOS_CACHE[ip] = exp_epoch

    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.execute("""
            INSERT INTO ips_bloqueados_seguranca (ip, motivo, bloqueado_em, expira_em, bloqueado_por, ativo)
            VALUES (?, ?, ?, ?, 'GESTOR_SUPERVISORIO', 1)
            ON CONFLICT(ip) DO UPDATE SET
                motivo = excluded.motivo,
                bloqueado_em = excluded.bloqueado_em,
                expira_em = excluded.expira_em,
                ativo = 1
        """, (ip, motivo, agora_dt.strftime("%d/%m/%Y %H:%M:%S"), exp_iso))
        conn.commit()

    return web.json_response({"ok": True, "msg": f"IP {ip} bloqueado com sucesso por {horas}h."})


async def api_supervisorio_ip_desbloquear(request: web.Request) -> web.Response:
    """Desbloqueia um IP previamente em quarentena."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    ip = str(body.get("ip", "")).strip()
    if not ip:
        return web.json_response({"ok": False, "msg": "Informe o IP."}, status=400)

    _IPS_BLOQUEADOS_CACHE.pop(ip, None)
    _FALHAS_RECENTES_IP.pop(ip, None)

    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.execute("UPDATE ips_bloqueados_seguranca SET ativo = 0 WHERE ip = ?", (ip,))
        conn.commit()

    return web.json_response({"ok": True, "msg": f"IP {ip} desbloqueado e removido da quarentena."})


async def api_supervisorio_varredura(request: web.Request) -> web.Response:
    """Dispara varredura forense completa sob demanda."""
    db_name = _obter_db_path(request.app)
    res = executar_varredura_ameacas_servidor(db_name)
    return web.json_response({"ok": True, "varredura": res})


# =========================================================================
# INTERFACE DO USUÁRIO — PAINEL SUPERVISÓRIO & SOC (Security Operations Center)
# =========================================================================

async def handle_pagina_supervisorio(request: web.Request) -> web.Response:
    html_page = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sistema Supervisório &amp; Defesa Cibernética — eMED SOC</title>
  <style>
    :root {
      --bg: #030712;
      --card: #0b132b;
      --card-border: #1e293b;
      --primary: #38bdf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f8fafc;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 18px; font-size: 13px; }
    .wrap { max-width: 1280px; margin: 0 auto; }
    
    /* Top Bar */
    .top-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--card-border); }
    .brand { display: flex; align-items: center; gap: 10px; }
    .brand-icon { width: 36px; height: 36px; background: linear-gradient(135deg, #0284c7, #38bdf8); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 900; }
    .brand-text h1 { font-size: 16px; font-weight: 800; letter-spacing: 0.5px; }
    .brand-text span { font-size: 11px; color: var(--primary); text-transform: uppercase; font-weight: 700; }
    .top-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

    .btn { background: #1e293b; color: #fff; border: 1px solid #334155; border-radius: 6px; padding: 7px 12px; font-size: 12px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; transition: all 0.15s ease; }
    .btn:hover { background: #334155; border-color: #475569; }
    .btn-primary { background: #0284c7; border-color: #0284c7; color: #fff; }
    .btn-primary:hover { background: #0369a1; }
    .btn-danger { background: #991b1b; border-color: #ef4444; color: #fff; }
    .btn-danger:hover { background: #b91c1c; }
    .btn-success { background: #065f46; border-color: #10b981; color: #fff; }

    /* Telemetry Grid */
    .grid-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 18px; }
    .card { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 14px; position: relative; }
    .kpi-title { font-size: 11px; color: var(--muted); text-transform: uppercase; font-weight: 700; margin-bottom: 6px; display: flex; justify-content: space-between; }
    .kpi-value { font-size: 26px; font-weight: 900; line-height: 1.1; }
    .kpi-sub { font-size: 11px; color: var(--muted); margin-top: 4px; }

    /* Security Status Banner */
    .sec-shield { border-left: 4px solid var(--success); display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }
    .sec-shield.alert { border-left-color: var(--danger); background: #1f1315; }
    .pulse-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--success); margin-right: 6px; box-shadow: 0 0 8px var(--success); animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

    /* Audit Table Card */
    .panel { background: var(--card); border: 1px solid var(--card-border); border-radius: 10px; padding: 16px; margin-bottom: 18px; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; }
    .panel-title { font-size: 14px; font-weight: 800; display: flex; align-items: center; gap: 8px; }
    
    .filters-bar { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .inp-search { background: #030712; border: 1px solid #1e293b; color: #fff; padding: 6px 10px; border-radius: 6px; font-size: 12px; min-width: 200px; outline: none; }
    .inp-search:focus { border-color: var(--primary); }
    .tab-pill { background: #030712; border: 1px solid #1e293b; color: var(--muted); padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; }
    .tab-pill.active { background: #0284c7; color: #fff; border-color: #0284c7; }

    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { text-align: left; padding: 9px 8px; font-size: 10.5px; color: var(--muted); text-transform: uppercase; border-bottom: 1px solid var(--card-border); font-weight: 800; }
    td { padding: 9px 8px; border-bottom: 1px solid #131c31; vertical-align: middle; }
    tr:hover td { background: #101a35; }

    .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 4px; font-size: 10.5px; font-weight: 800; }
    .badge-ok { background: #064e3b; color: #34d399; border: 1px solid #059669; }
    .badge-warn { background: #451a03; color: #fbbf24; border: 1px solid #b45309; }
    .badge-danger { background: #450a0a; color: #f87171; border: 1px solid #dc2626; }
    .badge-sys { background: #1e293b; color: var(--primary); border: 1px solid #334155; }

    /* Modal */
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.85); backdrop-filter: blur(4px); display: none; align-items: center; justify-content: center; z-index: 9999; padding: 14px; }
    .modal-box { background: var(--card); border: 1px solid var(--card-border); border-radius: 12px; width: 100%; max-width: 650px; padding: 20px; max-height: 85vh; overflow-y: auto; }
  </style>
</head>
<body>
  <div class="wrap">
    
    <!-- TOP BAR -->
    <div class="top-bar">
      <div class="brand">
        <div class="brand-icon">🛡️</div>
        <div class="brand-text">
          <h1>SISTEMA SUPERVISÓRIO eMED</h1>
          <span>CENTRO DE AUDITORIA &amp; OPERAÇÕES DE SEGURANÇA CIBERNÉTICA (SOC)</span>
        </div>
      </div>
      <div class="top-actions">
        <button class="btn btn-primary" onclick="abrirModalGeradorAcesso()" style="background:#10b981; border-color:#10b981;">🔑 Gerar Acesso de Cliente</button>
        <button class="btn btn-primary" onclick="executarVarreduraAgora()">🔍 Escanear Servidor Agora</button>
        <a class="btn" href="/api/supervisorio/exportar-csv" target="_blank">📥 Exportar Log CSV</a>
        <button class="btn" id="btnAutoRefresh" onclick="toggleAutoRefresh()">⏸️ Pausar (5s)</button>
        <a class="btn" href="/portal-cliente" target="_blank" style="background:#0f172a;">🏥 Portal do Cliente</a>
      </div>
    </div>

    <!-- ESCUDO CIBERNÉTICO & TELEMETRIA DE MINERAÇÃO -->
    <div id="shieldBox" class="card sec-shield">
      <div>
        <div style="display:flex; align-items:center;">
          <span id="shieldDot" class="pulse-dot"></span>
          <b id="shieldTitle" style="font-size:14px; color:#34d399;">ESCUDO DE DEFESA CIBERNÉTICA: 100% OPERACIONAL</b>
        </div>
        <div id="shieldMsg" style="font-size:11.5px; color:#cbd5e1; margin-top:3px;">
          Nenhum minerador de criptomoedas (XMRig/Stratum) detectado. Varredura contínua de processos e portas de rede ativa.
        </div>
      </div>
      <div style="font-size:11px; color:var(--muted); text-align:right;">
        Última checagem: <span id="lblUltimaChecagem">Agora</span>
      </div>
    </div>

    <!-- KPIS DE HARDWARE & TENTATIVAS DE LOGIN -->
    <div class="grid-kpis">
      <div class="card">
        <div class="kpi-title"><span>Uso de CPU</span><span id="kpiCpuIcon">⚡</span></div>
        <div class="kpi-value" id="kpiCpuVal" style="color:#38bdf8;">--%</div>
        <div class="kpi-sub" id="kpiCpuSub">Alerta configurado para > 70%</div>
      </div>
      <div class="card">
        <div class="kpi-title"><span>Memória RAM</span><span>💾</span></div>
        <div class="kpi-value" id="kpiRamVal" style="color:#34d399;">--%</div>
        <div class="kpi-sub" id="kpiRamSub">0.0 GB / 0.0 GB em uso</div>
      </div>
      <div class="card">
        <div class="kpi-title"><span>Logins Bem-Sucedidos</span><span>✅</span></div>
        <div class="kpi-value" id="kpiOkVal" style="color:#10b981;">0</div>
        <div class="kpi-sub">Últimas 24 horas</div>
      </div>
      <div class="card">
        <div class="kpi-title"><span>Falhas / Usuário Incorreto</span><span>⚠️</span></div>
        <div class="kpi-value" id="kpiFailVal" style="color:#fbbf24;">0</div>
        <div class="kpi-sub">Rastreadas com IP e User-Agent</div>
      </div>
      <div class="card">
        <div class="kpi-title"><span>Bloqueios Anti-Robô</span><span>🚨</span></div>
        <div class="kpi-value" id="kpiBlockVal" style="color:#ef4444;">0</div>
        <div class="kpi-sub" id="kpiIpsBloqSub">0 IPs em quarentena</div>
      </div>
      <div class="card" style="border-left: 3px solid #8b5cf6;">
        <div class="kpi-title"><span>🍯 Armadilha (Honeypot)</span><span style="color:#a78bfa; font-weight:bold;">DECEPTION</span></div>
        <div class="kpi-value" id="kpiHoneypotVal" style="color:#c084fc;">0</div>
        <div class="kpi-sub" id="kpiHoneypotSub">Invasores / Bots Enganados</div>
      </div>
    </div>

    <!-- PAINEL DE IPS BLOQUEADOS & QUARENTENA -->
    <div id="panelIpsBloqueados" class="panel" style="display:none; border-left:4px solid var(--danger);">
      <div class="panel-header">
        <div class="panel-title" style="color:#f87171;">🛑 Endereços IP em Quarentena / Auto-Ban Ativo</div>
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead><tr><th>IP</th><th>Motivo do Bloqueio</th><th>Bloqueado Em</th><th>Expiração</th><th>Origem</th><th>Ação</th></tr></thead>
          <tbody id="tbodyIpsBloq"></tbody>
        </table>
      </div>
    </div>

    <!-- PAINEL DE INVASORES NA ARMADILHA DECEPTION (HONEYPOT SOC) -->
    <div id="panelHoneypot" class="panel" style="border-left: 4px solid #8b5cf6;">
      <div class="panel-header">
        <div class="panel-title" style="color:#c084fc;">
          <span>🍯 Invasores na Armadilha Cibernética (Deception Honeypot)</span>
          <span id="lblHoneypotTotal" style="font-size:11px; color:var(--muted); font-weight:normal;"></span>
        </div>
        <div>
          <button class="btn btn-primary" onclick="recarregarHoneypot()" style="background:#7c3aed; border-color:#8b5cf6;">🔄 Atualizar Armadilha</button>
        </div>
      </div>
      <div style="font-size:11.5px; color:#cbd5e1; margin-bottom:12px;">
        Bots e invasores que executaram força bruta são desviados para o ambiente simulado (Decoy). Suas impressões digitais (GPU, Canvas, IP, Resolução e Comandos) são gravadas com assinatura SHA-256 para subsidiar Notícia-Crime perante a <b>Polícia Civil / DRCI</b>.
      </div>
      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Data / Horário</th>
              <th>IP de Origem</th>
              <th>Usuário Tentado</th>
              <th>Senhas Testadas</th>
              <th>Fingerprint (GPU / Canvas / Tela)</th>
              <th>Tempo Preso</th>
              <th>Status Pericial</th>
              <th>Ações Legais</th>
            </tr>
          </thead>
          <tbody id="tbodyHoneypot">
            <tr><td colspan="9" style="text-align:center; color:var(--muted); padding:16px;">Nenhum invasor registrado na armadilha no momento.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- PAINEL DE AUDITORIA FORENSE DE LOGINS EM TEMPO REAL -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">
          <span>📋 Auditoria em Tempo Real de Tentativas de Acesso</span>
          <span id="lblAuditTotal" style="font-size:11px; color:var(--muted); font-weight:normal;"></span>
        </div>
        <div class="filters-bar">
          <button class="tab-pill active" onclick="setFiltro('TODOS', this)">Todos</button>
          <button class="tab-pill" onclick="setFiltro('FALHAS', this)">⚠️ Apenas Falhas</button>
          <button class="tab-pill" onclick="setFiltro('BLOQUEADOS', this)">🚨 Bloqueios Anti-Robô</button>
          <button class="tab-pill" onclick="setFiltro('SUCESSO', this)">✅ Sucessos</button>
          <input type="text" id="inpBusca" class="inp-search" placeholder="🔍 Buscar usuário ou IP..." oninput="filtrarLocal()" />
        </div>
      </div>

      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Data / Horário</th>
              <th>Sistema</th>
              <th>Usuário Tentado</th>
              <th>IP de Origem</th>
              <th>Status / Resultado</th>
              <th>Motivo Detalhado</th>
              <th>User-Agent / Detecção</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody id="tbodyAudit">
            <tr><td colspan="8" style="text-align:center; padding:16px; color:var(--muted);">Carregando trilha de auditoria...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <!-- MODAL DE VARREDURA FORENSE -->
  <div id="modalVarredura" class="modal-backdrop">
    <div class="modal-box">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h3 style="font-size:15px; font-weight:800; color:#38bdf8;">🔍 Relatório de Varredura Heurística Antimalware</h3>
        <button class="btn" onclick="fecharModal()" style="padding:4px 8px;">✕</button>
      </div>
      <div id="modalBody" style="font-size:12px; line-height:1.6; color:#cbd5e1;">Carregando...</div>
      <div style="margin-top:16px; text-align:right;">
        <button class="btn btn-primary" onclick="fecharModal()">Concluído</button>
      </div>
    </div>
  </div>

  <script>
    let FILTRO_STATUS = 'TODOS';
    let AUTO_REFRESH = true;
    let TIMER = null;
    let CACHE_AUDITORIA = [];

    window.addEventListener('load', () => {
      carregarTudo();
      TIMER = setInterval(() => { if (AUTO_REFRESH) carregarTudo(); }, 5000);
    });

    
    async function recarregarHoneypot() {
      try {
        const res = await fetch('/api/supervisorio/honeypot').then(r => r.json());
        if (!res.ok) return;
        const total = res.total || 0;
        document.getElementById('kpiHoneypotVal').textContent = total;
        document.getElementById('lblHoneypotTotal').textContent = `(${total} invasores registrados)`;
        
        const tbody = document.getElementById('tbodyHoneypot');
        if (!res.invasores || res.invasores.length === 0) {
          tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--muted); padding:16px;">Nenhum invasor capturado na armadilha no momento. Sistema monitorando tentativas de forçamento 24/7.</td></tr>';
          return;
        }

        tbody.innerHTML = res.invasores.map(inv => {
          const fps = [
            inv.gpu_renderer ? `GPU: ${_escapeHtml(inv.gpu_renderer)}` : '',
            inv.canvas_hash ? `Hash: ${_escapeHtml(inv.canvas_hash)}` : '',
            inv.screen_resolution ? `Tela: ${_escapeHtml(inv.screen_resolution)}` : ''
          ].filter(Boolean).join('<br>') || '<span style="color:#64748b;">Aguardando beacon...</span>';

          const tempo = inv.tempo_na_armadilha_segundos ? `${Number(inv.tempo_na_armadilha_segundos)}s` : 'Ativo';
          const senhas = inv.senhas_tentadas ? _escapeHtml(inv.senhas_tentadas.substring(0, 35) + (inv.senhas_tentadas.length > 35 ? '...' : '')) : '-';

          return `<tr>
            <td style="font-weight:bold; color:#a78bfa;">#${Number(inv.id) || 0}</td>
            <td style="white-space:nowrap;">${_escapeHtml(inv.data_hora)}</td>
            <td><code style="background:#0f172a; padding:2px 5px; border-radius:4px; color:#38bdf8;">${_escapeHtml(inv.ip_origem)}</code></td>
            <td style="font-weight:bold; color:#fbbf24;">${_escapeHtml(inv.usuario_tentado || '-')}</td>
            <td style="font-size:11px; color:#f87171;">${senhas}</td>
            <td style="font-size:10.5px; line-height:1.3; max-width:240px;">${fps}</td>
            <td style="color:#34d399; font-weight:bold;">${tempo}</td>
            <td><span class="badge badge-ok">${_escapeHtml(inv.status_pericia || 'COLETADO')}</span></td>
            <td>
              <div style="display:flex; gap:6px;">
                <a href="/api/supervisorio/dossie-forense/${encodeURIComponent(String(inv.id || ''))}" target="_blank" class="btn" style="background:#0369a1; border-color:#0284c7; padding:3px 8px; font-size:11px;">
                  📄 Laudo Polícia
                </a>
                <button data-ip="${_escapeHtml(inv.ip_origem)}" onclick="bloquearIpManual(this.dataset.ip)" class="btn btn-danger" style="padding:3px 8px; font-size:11px;">
                  🛑 Bloquear IP
                </button>
              </div>
            </td>
          </tr>`;
        }).join('');
      } catch (e) {
        console.error("Erro ao carregar honeypot:", e);
      }
    }

    function toggleAutoRefresh() {
      AUTO_REFRESH = !AUTO_REFRESH;
      const btn = document.getElementById('btnAutoRefresh');
      btn.textContent = AUTO_REFRESH ? '⏸️ Pausar (5s)' : '▶️ Retomar';
      btn.style.background = AUTO_REFRESH ? '#1e293b' : '#0284c7';
    }

    async function carregarTudo() {
      document.getElementById('lblUltimaChecagem').textContent = new Date().toLocaleTimeString('pt-BR');
      await Promise.all([carregarMetricas(), carregarAuditoria(), recarregarHoneypot()]);
    }

    async function carregarMetricas() {
      try {
        const res = await fetch('/api/supervisorio/metricas').then(r => r.json());
        if (!res.ok) return;

        // CPU & RAM
        const cpu = res.hardware.cpu_percent || 0;
        document.getElementById('kpiCpuVal').textContent = cpu.toFixed(1) + '%';
        document.getElementById('kpiCpuVal').style.color = cpu > 70 ? '#ef4444' : (cpu > 40 ? '#fbbf24' : '#38bdf8');
        
        const ram = res.hardware.ram_percent || 0;
        document.getElementById('kpiRamVal').textContent = ram.toFixed(1) + '%';
        document.getElementById('kpiRamSub').textContent = `${res.hardware.ram_usada_gb} GB / ${res.hardware.ram_total_gb} GB em uso`;

        // Logins 24h
        document.getElementById('kpiOkVal').textContent = res.auditoria_24h.sucessos;
        document.getElementById('kpiFailVal').textContent = res.auditoria_24h.falhas;
        document.getElementById('kpiBlockVal').textContent = res.auditoria_24h.bloqueios_anti_robo;

        if (res.seguranca && res.seguranca.honeypot_total !== undefined) {
          document.getElementById('kpiHoneypotVal').textContent = res.seguranca.honeypot_total;
        }

        // Banner de Proteção
        const st = res.seguranca.status_geral;
        const shieldBox = document.getElementById('shieldBox');
        const shieldDot = document.getElementById('shieldDot');
        const shieldTitle = document.getElementById('shieldTitle');
        const shieldMsg = document.getElementById('shieldMsg');

        if (st === 'AMEACA_DETECTADA') {
          shieldBox.className = 'card sec-shield alert';
          shieldDot.style.background = '#ef4444';
          shieldDot.style.boxShadow = '0 0 10px #ef4444';
          shieldTitle.textContent = '🚨 ALERTA: AMEAÇA OU MINERADOR SUSPEITO DETECTADO!';
          shieldTitle.style.color = '#f87171';
          shieldMsg.textContent = res.seguranca.alertas.join(' • ');
        } else {
          shieldBox.className = 'card sec-shield';
          shieldDot.style.background = '#10b981';
          shieldDot.style.boxShadow = '0 0 8px #10b981';
          shieldTitle.textContent = 'ESCUDO DE DEFESA CIBERNÉTICA: 100% OPERACIONAL';
          shieldTitle.style.color = '#34d399';
          shieldMsg.textContent = `Nenhum minerador de criptomoedas detectado. ${res.seguranca.processos_analisados} processos verificados em tempo real. Zero conexões estranhas.`;
        }

        // Tabela de IPs Bloqueados
        const ipsBloq = res.auditoria_24h.ips_bloqueados_ativos || [];
        const pIps = document.getElementById('panelIpsBloqueados');
        document.getElementById('kpiIpsBloqSub').textContent = `${ipsBloq.length} IP(s) em quarentena`;
        if (ipsBloq.length > 0) {
          pIps.style.display = 'block';
          document.getElementById('tbodyIpsBloq').innerHTML = ipsBloq.map(b => `
            <tr>
              <td><b style="color:#f87171;">${_escapeHtml(b.ip)}</b></td>
              <td>${_escapeHtml(b.motivo)}</td>
              <td>${_escapeHtml(b.bloqueado_em)}</td>
              <td>${_escapeHtml(b.expira_em || 'Permanente')}</td>
              <td><span class="badge badge-sys">${_escapeHtml(b.bloqueado_por)}</span></td>
              <td>
                <button class="btn btn-success" style="padding:3px 8px; font-size:11px;" data-ip="${_escapeHtml(b.ip)}" onclick="desbloquearIp(this.dataset.ip)">
                  🔓 Desbloquear
                </button>
              </td>
            </tr>
          `).join('');
        } else {
          pIps.style.display = 'none';
        }

      } catch (err) {
        console.error('Erro ao ler métricas:', err);
      }
    }

    async function carregarAuditoria() {
      try {
        const res = await fetch(`/api/supervisorio/auditoria?status=${encodeURIComponent(FILTRO_STATUS)}&limit=100`).then(r => r.json());
        if (!res.ok) return;
        CACHE_AUDITORIA = res.auditoria || [];
        document.getElementById('lblAuditTotal').textContent = `(Mostrando ${CACHE_AUDITORIA.length} registros)`;
        renderTabelaAuditoria(CACHE_AUDITORIA);
      } catch (err) {
        console.error('Erro na auditoria:', err);
      }
    }

    function setFiltro(f, el) {
      FILTRO_STATUS = f;
      document.querySelectorAll('.tab-pill').forEach(b => b.classList.remove('active'));
      if (el) el.classList.add('active');
      carregarAuditoria();
    }

    function filtrarLocal() {
      const q = document.getElementById('inpBusca').value.trim().toUpperCase();
      if (!q) {
        renderTabelaAuditoria(CACHE_AUDITORIA);
        return;
      }
      const filtrados = CACHE_AUDITORIA.filter(r => 
        (r.usuario_tentado || '').toUpperCase().includes(q) ||
        (r.ip_origem || '').toUpperCase().includes(q) ||
        (r.motivo_detalhado || '').toUpperCase().includes(q)
      );
      renderTabelaAuditoria(filtrados);
    }

    function renderTabelaAuditoria(lista) {
      const tb = document.getElementById('tbodyAudit');
      if (!lista || lista.length === 0) {
        tb.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:18px; color:var(--muted);">Nenhum registro encontrado para este filtro.</td></tr>';
        return;
      }

      tb.innerHTML = lista.map(r => {
        let stBadge = '<span class="badge badge-ok">✅ SUCESSO</span>';
        if (r.status_resultado === 'SENHA_INCORRETA') {
          stBadge = '<span class="badge badge-warn">⚠️ SENHA INCORRETA</span>';
        } else if (r.status_resultado === 'USUARIO_INEXISTENTE') {
          stBadge = '<span class="badge badge-warn" style="color:#f97316;">🟠 NÃO ENCONTRADO</span>';
        } else if (r.status_resultado.includes('BLOQUE') || r.bloqueio_ativo === 1) {
          stBadge = '<span class="badge badge-danger">🚨 BLOQUEADO / BRUTE FORCE</span>';
        } else if (r.status_resultado.includes('BOT')) {
          stBadge = '<span class="badge badge-danger">🤖 ROBÔ DETECTADO</span>';
        }

        const isLocal = (r.ip_origem === '127.0.0.1' || r.ip_origem === '::1');
        const btnBlock = isLocal ? '' : `<button class="btn btn-danger" style="padding:2px 6px; font-size:10px;" data-ip="${_escapeHtml(r.ip_origem)}" onclick="bloquearIpManual(this.dataset.ip)">⛔ Bloquear IP</button>`;

        return `
          <tr>
            <td style="white-space:nowrap; font-weight:bold;">${_escapeHtml(r.data_hora)}</td>
            <td><span class="badge badge-sys">${_escapeHtml(r.tipo_sistema)}</span></td>
            <td><b style="color:#e2e8f0;">${_escapeHtml(r.usuario_tentado)}</b></td>
            <td><code>${_escapeHtml(r.ip_origem)}</code></td>
            <td>${stBadge}</td>
            <td style="max-width:240px; color:#cbd5e1;">${_escapeHtml(r.motivo_detalhado || '-')}</td>
            <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; color:var(--muted);" title="${_escapeHtml(r.user_agent)}">
              ${_escapeHtml(r.user_agent ? r.user_agent.slice(0, 32) + '...' : '-')}
            </td>
            <td>${btnBlock}</td>
          </tr>
        `;
      }).join('');
    }

    function _escapeHtml(s) {
      if (s === null || s === undefined) return '';
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    async function bloquearIpManual(ip) {
      const motivo = prompt(`Informe o motivo para bloquear o IP ${ip}:`, 'Tentativas de login repetidas suspeitas de robô') || '';
      if (!motivo) return;
      const res = await fetch('/api/supervisorio/ip/bloquear', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ip, motivo, horas: 24 })
      }).then(r => r.json());
      alert(res.msg || 'IP Bloqueado');
      carregarTudo();
    }

    async function desbloquearIp(ip) {
      if (!confirm(`Deseja desbloquear o IP ${ip}?`)) return;
      const res = await fetch('/api/supervisorio/ip/desbloquear', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ip })
      }).then(r => r.json());
      alert(res.msg || 'IP Desbloqueado');
      carregarTudo();
    }

    async function executarVarreduraAgora() {
      const modal = document.getElementById('modalVarredura');
      const mb = document.getElementById('modalBody');
      modal.style.display = 'flex';
      mb.innerHTML = '<div style="text-align:center; padding:20px;"><b>⏳ Escaneando todos os processos do sistema operacional e conexões ativas...</b></div>';

      try {
        const res = await fetch('/api/supervisorio/varredura', { method: 'POST' }).then(r => r.json());
        const v = res.varredura;
        let html = `
          <div style="background:#030712; padding:12px; border-radius:8px; margin-bottom:12px; border-left:4px solid ${v.status === 'SEGURO' ? '#10b981' : '#ef4444'};">
            <h4 style="color:${v.status === 'SEGURO' ? '#34d399' : '#f87171'};">STATUS DA VARREDURA: ${v.status}</h4>
            <div style="font-size:11.5px; margin-top:4px;">Realizada em ${v.timestamp} • ${v.processos_analisados} processos analisados</div>
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:12px;">
            <div class="card" style="padding:10px;"><b>Uso de CPU:</b> ${v.cpu_percent}%</div>
            <div class="card" style="padding:10px;"><b>Uso de Memória:</b> ${v.ram_percent}% (${v.ram_usada_gb} GB)</div>
          </div>
          <div style="margin-bottom:10px;">
            <b>Assinaturas de Criptomineração (XMRig, Stratum, etc.):</b> 
            <span style="color:#34d399; font-weight:bold;">${v.processos_suspeitos.length === 0 ? '✅ 0 Encontradas (100% Limpo)' : '🚨 ' + v.processos_suspeitos.length + ' detectadas!'}</span>
          </div>
          <div style="margin-bottom:10px;">
            <b>Conexões com Pools de Mineração:</b> 
            <span style="color:#34d399; font-weight:bold;">${v.conexoes_suspeitas.length === 0 ? '✅ 0 Conexões Ativas' : '🚨 ' + v.conexoes_suspeitas.length + ' detectadas!'}</span>
          </div>
        `;

        if (v.processos_suspeitos.length > 0) {
          html += `<div style="background:#450a0a; padding:10px; border-radius:6px; margin-top:8px;"><b>Processos Suspeitos:</b><br>${v.processos_suspeitos.map(p => `• PID ${p.pid}: ${p.nome} — ${p.motivo}`).join('<br>')}</div>`;
        }

        html += `
          <div style="margin-top:12px; padding:10px; background:#0f172a; border-radius:6px; font-size:11.5px;">
            <b>Serviços Oficiais eMED Monitorados:</b><br>
            ${(v.servicos_emed_ativos || []).map(p => `• [PID ${p.pid}] ${p.nome} (${p.cmd})`).join('<br>') || 'Nenhum serviço em segundo plano detectado.'}
          </div>
        `;

        mb.innerHTML = html;
        carregarTudo();
      } catch (err) {
        mb.innerHTML = `<div style="color:#f87171;">Erro ao executar varredura: ${err}</div>`;
      }
    }

    function fecharModal() {
      document.getElementById('modalVarredura').style.display = 'none';
    }
  </script>
  <!-- MODAL GERADOR DE ACESSOS DO CLIENTE -->
  <div id="modalGeradorAcesso" class="modal-backdrop">
    <div class="modal-box" style="max-width:720px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid var(--card-border); padding-bottom:10px;">
        <h3 style="font-size:16px; font-weight:800; color:#38bdf8; display:flex; align-items:center; gap:8px;">
          <span>🔑 Gerador &amp; Gestor de Credenciais do Portal do Cliente</span>
        </h3>
        <button class="btn" onclick="fecharModalGerador()" style="padding:4px 8px;">✕</button>
      </div>

      <div style="background:#030712; border:1px solid #1e293b; border-radius:8px; padding:14px; margin-bottom:16px;">
        <div style="font-size:12px; font-weight:700; color:#cbd5e1; margin-bottom:8px;">1. Selecione ou digite a Unidade Hospitalar / Clínica:</div>
        <input list="dlClientesCadastrados" id="genCliNome" class="inp-search" style="width:100%; padding:9px 12px; font-size:13px; margin-bottom:10px;" placeholder="Digite o nome da clínica/hospital (ex: A G S CLINICA MEDICA, HOSPITAL SAO CARLOS)..." oninput="sugerirSlugUsuario()" />
        <datalist id="dlClientesCadastrados"></datalist>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px;">
          <div>
            <label style="font-size:11px; color:var(--muted); font-weight:700;">Usuário de Acesso (slug)</label>
            <input id="genCliUsuario" class="inp-search" style="width:100%; margin-top:4px;" placeholder="ex: clinica.ags" />
          </div>
          <div>
            <label style="font-size:11px; color:var(--muted); font-weight:700; display:flex; justify-content:space-between;">
              <span>Senha</span>
              <a href="javascript:void(0)" onclick="gerarSenhaAleatoria()" style="color:#38bdf8; font-size:10.5px; text-decoration:none;">🎲 Gerar Aleatória</a>
            </label>
            <input id="genCliSenha" class="inp-search" style="width:100%; margin-top:4px;" placeholder="ex: emed4821 (ou em branco)" />
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
          <div>
            <label style="font-size:11px; color:var(--muted); font-weight:700;">Nome do Gestor / Diretor (opcional)</label>
            <input id="genCliGestor" class="inp-search" style="width:100%; margin-top:4px;" placeholder="ex: Dra. Adda Moreira" />
          </div>
          <div>
            <label style="font-size:11px; color:var(--muted); font-weight:700;">WhatsApp do Gestor (DDD + número)</label>
            <input id="genCliWpp" class="inp-search" style="width:100%; margin-top:4px;" placeholder="ex: 85988887631" />
          </div>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:8px;">
          <button class="btn btn-primary" onclick="executarCriacaoAcessoCliente()" style="background:#10b981; border-color:#10b981; padding:9px 18px; font-size:13px;">
            ⚡ Criar / Atualizar Acesso do Cliente
          </button>
        </div>
      </div>

      <!-- RESULTADO DO ACESSO GERADO -->
      <div id="boxResultadoGerado" style="display:none; background:#064e3b; border:1px solid #059669; border-radius:8px; padding:14px; margin-bottom:16px;">
        <div style="font-weight:800; color:#34d399; font-size:13.5px; margin-bottom:6px;">✅ Credenciais Geradas com Sucesso!</div>
        <div id="txtMsgGerada" style="background:#022c22; padding:10px; border-radius:6px; font-size:12px; font-family:monospace; color:#a7f3d0; margin-bottom:10px; white-space:pre-wrap;"></div>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn" style="background:#047857; color:#fff;" onclick="copiarMensagemAcesso()">📋 Copiar Mensagem</button>
          <button class="btn" id="btnEnviarWppGerado" style="background:#25d366; color:#000; font-weight:900;" onclick="enviarWppGerado()">📲 Enviar WhatsApp</button>
        </div>
      </div>

      <!-- LISTA DE ACESSOS ATIVOS -->
      <div style="font-weight:800; font-size:13px; color:#cbd5e1; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
        <span>📋 Unidades com Acesso ao Portal Cadastrado</span>
        <button class="btn" style="padding:2px 8px; font-size:11px;" onclick="carregarListaAcessosCadastrados()">🔄 Atualizar</button>
      </div>
      <div style="max-height:220px; overflow-y:auto;">
        <table>
          <thead><tr><th>Unidade Hospitalar</th><th>Usuário</th><th>Gestor</th><th>WhatsApp</th><th>Último Acesso</th><th>Ação</th></tr></thead>
          <tbody id="tbodyAcessosCadastrados"><tr><td colspan="6" style="text-align:center; padding:10px; color:var(--muted);">Carregando...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    let CACHE_CLIENTES_LISTA = [];
    let MSG_GERADA_ATUAL = '';
    let WPP_GERADO_ATUAL = '';

    async function abrirModalGeradorAcesso() {
      document.getElementById('modalGeradorAcesso').style.display = 'flex';
      carregarListaAcessosCadastrados();
      if (CACHE_CLIENTES_LISTA.length === 0) {
        try {
          const res = await fetch('/api/supervisorio/clientes-lista').then(r=>r.json());
          if (res.ok) {
            CACHE_CLIENTES_LISTA = res.clientes || [];
            const dl = document.getElementById('dlClientesCadastrados');
            dl.innerHTML = CACHE_CLIENTES_LISTA.map(c => `<option value="${_escapeHtml(c)}"></option>`).join('');
          }
        } catch(e) {}
      }
    }

    function fecharModalGerador() {
      document.getElementById('modalGeradorAcesso').style.display = 'none';
      document.getElementById('boxResultadoGerado').style.display = 'none';
    }

    function sugerirSlugUsuario() {
      const cli = document.getElementById('genCliNome').value.trim();
      const slug = cli.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, ".").replace(/^\\.+|\\.+$/g, "").slice(0, 24);
      document.getElementById('genCliUsuario').value = slug || '';
    }

    function gerarSenhaAleatoria() {
      const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789@#';
      const arr = new Uint32Array(8);
      (window.crypto || window.msCrypto).getRandomValues(arr);
      let suf = '';
      for (let i = 0; i < arr.length; i++) suf += chars[arr[i] % chars.length];
      document.getElementById('genCliSenha').value = 'Emed@' + suf;
    }

    async function executarCriacaoAcessoCliente() {
      const cliente_nome = document.getElementById('genCliNome').value.trim();
      if (!cliente_nome) return alert('Informe o nome da unidade hospitalar.');
      const usuario = document.getElementById('genCliUsuario').value.trim();
      const senha = document.getElementById('genCliSenha').value.trim();
      const gestor_nome = document.getElementById('genCliGestor').value.trim();
      const gestor_whatsapp = document.getElementById('genCliWpp').value.trim();

      const res = await fetch('/api/supervisorio/cliente-acesso-gerar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ cliente_nome, usuario, senha, gestor_nome, gestor_whatsapp })
      }).then(r => r.json());

      if (!res.ok) return alert(res.msg || 'Erro ao gerar acesso.');

      const urlPortal = `${window.location.origin}/portal-cliente`;
      MSG_GERADA_ATUAL = `Olá${gestor_nome ? ' ' + gestor_nome : ''}! Segue o acesso exclusivo de *${res.cliente_nome}* ao Portal de Gestão do Parque Tecnológico & Vigilância Sanitária da *EMED Eletromedicina*:

🔗 *Link do Portal:* ${urlPortal}
👤 *Usuário:* ${res.usuario}
🔑 *Senha:* ${res.senha}

_Guarde esta credencial com segurança. Acesso 24/7 aos equipamentos, laudos e DANFEs da sua unidade._`;
      WPP_GERADO_ATUAL = gestor_whatsapp.replace(/\\D/g, '');

      document.getElementById('txtMsgGerada').textContent = MSG_GERADA_ATUAL;
      document.getElementById('boxResultadoGerado').style.display = 'block';
      carregarListaAcessosCadastrados();
    }

    function copiarMensagemAcesso() {
      navigator.clipboard.writeText(MSG_GERADA_ATUAL);
      alert('Mensagem copiada para a área de transferência!');
    }

    function enviarWppGerado() {
      const tel = WPP_GERADO_ATUAL;
      const url = `https://wa.me/${tel ? '55' + tel : ''}?text=${encodeURIComponent(MSG_GERADA_ATUAL)}`;
      window.open(url, '_blank');
    }

    async function carregarListaAcessosCadastrados() {
      try {
        const res = await fetch('/api/supervisorio/clientes-acessos').then(r=>r.json());
        if (!res.ok) return;
        const tb = document.getElementById('tbodyAcessosCadastrados');
        const rows = res.acessos || [];
        if (rows.length === 0) {
          tb.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:10px; color:var(--muted);">Nenhum acesso gerado ainda.</td></tr>';
          return;
        }
        tb.innerHTML = rows.map(r => `
          <tr>
            <td><b>${_escapeHtml(r.cliente_nome)}</b></td>
            <td><code style="color:#38bdf8;">${_escapeHtml(r.usuario)}</code></td>
            <td>${_escapeHtml(r.gestor_nome || '-')}</td>
            <td>${_escapeHtml(r.gestor_whatsapp || '-')}</td>
            <td>${_escapeHtml(r.ultimo_acesso || 'Nunca')}</td>
            <td>
              <button class="btn" style="padding:2px 7px; font-size:10.5px; background:#0284c7;"
                data-cli="${_escapeHtml(r.cliente_nome)}" data-usr="${_escapeHtml(r.usuario)}"
                data-gst="${_escapeHtml(r.gestor_nome||'')}" data-wpp="${_escapeHtml(r.gestor_whatsapp||'')}"
                onclick="prepararRedefinicao(this.dataset.cli, this.dataset.usr, this.dataset.gst, this.dataset.wpp)">
                ✏️ Redefinir Senha
              </button>
            </td>
          </tr>
        `).join('');
      } catch(e) {}
    }

    function prepararRedefinicao(cli, usr, gst, wpp) {
      document.getElementById('genCliNome').value = cli;
      document.getElementById('genCliUsuario').value = usr;
      document.getElementById('genCliGestor').value = gst;
      document.getElementById('genCliWpp').value = wpp;
      gerarSenhaAleatoria();
      alert(`Unidade ${cli} carregada no formulário. A senha foi alterada para um novo código aleatório. Clique em "Criar / Atualizar Acesso" para confirmar.`);
    }
  </script>

</body>
</html>"""
    return web.Response(text=html_page, content_type="text/html", charset="utf-8", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


async def api_supervisorio_clientes_lista(request: web.Request) -> web.Response:
    """Retorna a lista de todas as unidades/hospitais distintos cadastrados no sistema."""
    db_name = _obter_db_path(request.app)
    try:
        with sqlite3.connect(db_name) as conn:
            c1 = [r[0] for r in conn.execute("SELECT DISTINCT nome FROM clientes WHERE nome IS NOT NULL AND TRIM(nome) != ''").fetchall()]
            c2 = [r[0] for r in conn.execute("SELECT DISTINCT cliente FROM clientes_equipamentos WHERE cliente IS NOT NULL AND TRIM(cliente) != ''").fetchall()]
            c3 = [r[0] for r in conn.execute("SELECT DISTINCT cliente_nome FROM equipamentos WHERE cliente_nome IS NOT NULL AND TRIM(cliente_nome) != ''").fetchall()]
            todos = sorted(list(set(c1 + c2 + c3)))
    except Exception as e:
        todos = []
    return web.json_response({"ok": True, "clientes": todos})


async def api_supervisorio_clientes_acessos(request: web.Request) -> web.Response:
    """Lista todos os acessos cadastrados no portal do cliente para o painel supervisório."""
    db_name = _obter_db_path(request.app)
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, cliente_nome, usuario, gestor_nome, gestor_whatsapp, gestor_email, ativo, criado_em, ultimo_acesso FROM clientes_acessos_portal ORDER BY id DESC").fetchall()
    return web.json_response({"ok": True, "acessos": [dict(r) for r in rows]})


async def api_supervisorio_cliente_acesso_gerar(request: web.Request) -> web.Response:
    """Gera ou redefine credenciais de acesso do cliente a partir do painel supervisório."""
    import re as _re
    import secrets
    from emed_app_server import hash_senha_forte, _garantir_schema_acessos_cliente
    db_name = _obter_db_path(request.app)
    body = await request.json()
    cliente_nome = str(body.get("cliente_nome", "")).strip().upper()
    if not cliente_nome:
        return web.json_response({"ok": False, "msg": "Informe o nome da unidade hospitalar."}, status=400)

    gestor_nome = str(body.get("gestor_nome", "")).strip()
    gestor_wpp = str(body.get("gestor_whatsapp", "")).strip()
    gestor_email = str(body.get("gestor_email", "")).strip()

    slug = _re.sub(r"[^a-z0-9]+", ".", cliente_nome.lower()).strip(".")[:24] or "unidade"
    usuario = str(body.get("usuario") or slug).strip().lower()
    senha_plana = str(body.get("senha") or "").strip() or f"Emed@{secrets.token_hex(4).upper()}"
    senha_hash = hash_senha_forte(senha_plana)
    token = secrets.token_hex(24)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        _garantir_schema_acessos_cliente(conn)
        row_ex = conn.execute("SELECT id FROM clientes_acessos_portal WHERE UPPER(cliente_nome) = ?", (cliente_nome,)).fetchone()
        if row_ex:
            conn.execute("""
                UPDATE clientes_acessos_portal
                SET usuario = ?, senha_hash = ?, gestor_nome = ?, gestor_whatsapp = ?, gestor_email = ?, token_acesso = ?, ativo = 1
                WHERE id = ?
            """, (usuario, senha_hash, gestor_nome, gestor_wpp, gestor_email, token, row_ex[0]))
        else:
            while conn.execute("SELECT 1 FROM clientes_acessos_portal WHERE usuario = ?", (usuario,)).fetchone():
                usuario = f"{slug}.{secrets.randbelow(90)+10}"
            conn.execute("""
                INSERT INTO clientes_acessos_portal (
                    cliente_nome, usuario, senha_hash, gestor_nome, gestor_whatsapp, gestor_email, token_acesso, ativo, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (cliente_nome, usuario, senha_hash, gestor_nome, gestor_wpp, gestor_email, token, agora))
        conn.commit()

    return web.json_response({
        "ok": True,
        "cliente_nome": cliente_nome,
        "usuario": usuario,
        "senha": senha_plana,
        "gestor_nome": gestor_nome,
        "gestor_whatsapp": gestor_wpp,
        "msg": f"✅ Acesso criado com sucesso para {cliente_nome}! Usuário: {usuario}",
    })


def registrar_rotas_supervisorio(app: web.Application) -> None:
    """Registra as rotas da interface e das APIs do Sistema Supervisório."""
    app.router.add_get("/supervisorio", handle_pagina_supervisorio)
    app.router.add_get("/api/supervisorio/metricas", api_supervisorio_metricas)
    app.router.add_get("/api/supervisorio/auditoria", api_supervisorio_auditoria_listar)
    app.router.add_get("/api/supervisorio/exportar-csv", api_supervisorio_exportar_csv)
    app.router.add_post("/api/supervisorio/ip/bloquear", api_supervisorio_ip_bloquear)
    app.router.add_post("/api/supervisorio/ip/desbloquear", api_supervisorio_ip_desbloquear)
    app.router.add_post("/api/supervisorio/varredura", api_supervisorio_varredura)
    app.router.add_get("/api/supervisorio/clientes-lista", api_supervisorio_clientes_lista)
    app.router.add_get("/api/supervisorio/clientes-acessos", api_supervisorio_clientes_acessos)
    app.router.add_post("/api/supervisorio/cliente-acesso-gerar", api_supervisorio_cliente_acesso_gerar)

    # Módulo de Defesa Cibernética Ativa: Deception Honeypot & Forense Digital
    try:
        from emed_views.honeypot_deception import (
            handle_honeypot_dashboard, api_honeypot_beacon,
            api_honeypot_fake_terminal, api_supervisorio_honeypot_listar,
            api_supervisorio_gerar_dossie_policia
        )
        for _method, _path, _handler in [
            ("GET", "/admin/dashboard", handle_honeypot_dashboard),
            ("POST", "/api/honeypot/beacon", api_honeypot_beacon),
            ("POST", "/api/honeypot/fake-terminal", api_honeypot_fake_terminal),
            ("GET", "/api/supervisorio/honeypot", api_supervisorio_honeypot_listar),
            ("GET", "/api/supervisorio/dossie-forense/{id}", api_supervisorio_gerar_dossie_policia),
        ]:
            try:
                if _method == "GET":
                    app.router.add_get(_path, _handler)
                elif _method == "POST":
                    app.router.add_post(_path, _handler)
            except RuntimeError:
                pass
    except Exception as _eh:
        print(f"[SUPERVISORIO] Aviso ao registrar rotas de Honeypot Deception: {_eh}")
