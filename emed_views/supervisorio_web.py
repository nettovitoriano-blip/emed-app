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
import hashlib
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
            bloqueio_ativo INTEGER DEFAULT 0,
            score_risco INTEGER DEFAULT 1,
            nivel_risco TEXT DEFAULT 'BAIXO'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_dt ON auditoria_tentativas_login(data_hora)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_ip ON auditoria_tentativas_login(ip_origem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_login_st ON auditoria_tentativas_login(status_resultado)")
    try:
        conn.execute("ALTER TABLE auditoria_tentativas_login ADD COLUMN score_risco INTEGER DEFAULT 1")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE auditoria_tentativas_login ADD COLUMN nivel_risco TEXT DEFAULT 'BAIXO'")
    except Exception:
        pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ips_whitelist_seguranca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT UNIQUE NOT NULL,
            descricao TEXT DEFAULT '',
            adicionado_em TEXT NOT NULL,
            adicionado_por TEXT DEFAULT 'GESTOR'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alertas_seguranca_soc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            nivel TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            ip_origem TEXT DEFAULT '',
            usuario TEXT DEFAULT '',
            visualizado INTEGER DEFAULT 0
        )
    """)
    # Pre-popula whitelist padrao
    for w_ip, w_desc in [("127.0.0.1", "Localhost IPv4"), ("::1", "Localhost IPv6"), ("localhost", "Local loopback")]:
        try:
            conn.execute("INSERT OR IGNORE INTO ips_whitelist_seguranca (ip, descricao, adicionado_em) VALUES (?, ?, 'SISTEMA')", (w_ip, w_desc))
        except Exception:
            pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes_seguranca_soc (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            atualizado_por TEXT DEFAULT 'SISTEMA'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integridade_arquivos_baseline (
            arquivo TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL,
            tamanho_bytes INTEGER NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_inteligencia_ip (
            ip TEXT PRIMARY KEY,
            pais TEXT NOT NULL,
            bandeira TEXT NOT NULL,
            tipo_rede TEXT NOT NULL,
            asn TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessoes_ativas_rastreamento (
            token_hash TEXT PRIMARY KEY,
            usuario TEXT NOT NULL,
            perfil TEXT NOT NULL,
            ip_origem TEXT NOT NULL,
            user_agent TEXT DEFAULT '',
            criado_em TEXT NOT NULL,
            ultimo_ping TEXT NOT NULL,
            ultimo_ping_epoch REAL NOT NULL,
            revogado INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sessao_ping ON sessoes_ativas_rastreamento(ultimo_ping_epoch, revogado)")

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




# ==============================================================================
# SUBSISTEMA TÁTICO MILITAR / DEFESA CIBERNÉTICA (DEFCON, GEOIP, FIM, SESSÕES)
# ==============================================================================
_DEFCON_NIVEL: int = 5
_DEFCON_INFO: Dict[str, Any] = {
    "nivel": 5,
    "rotulo": "DEFCON 5 - NORMAL",
    "motivo": "Operação segura padrão sem ameaças anômalas",
    "atualizado_em": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    "atualizado_por": "SISTEMA"
}
_SESSOES_REVOGADAS_CACHE: set = set()
_CACHE_GEOIP_MEMORIA: Dict[str, Dict[str, str]] = {}


def obter_defcon_nivel(db_path: Optional[str] = None) -> int:
    """Retorna o nível DEFCON atual do sistema (1 a 5)."""
    global _DEFCON_NIVEL, _DEFCON_INFO
    db_p = db_path or _obter_db_path()
    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            r = conn.execute("SELECT valor, atualizado_em, atualizado_por FROM configuracoes_seguranca_soc WHERE chave = 'DEFCON_LEVEL'").fetchone()
            if r:
                _DEFCON_NIVEL = int(r[0])
                m_row = conn.execute("SELECT valor FROM configuracoes_seguranca_soc WHERE chave = 'DEFCON_MOTIVO'").fetchone()
                motivo = m_row[0] if m_row else "Defesa Ativa"
                rotulos = {
                    5: "DEFCON 5 - NORMAL / MONITORAMENTO DE ROTINA",
                    4: "DEFCON 4 - ATENÇÃO / VARREDURA PROATIVA",
                    3: "DEFCON 3 - ELEVADO / TOLERÂNCIA ZERO A BRUTE-FORCE",
                    2: "DEFCON 2 - CRÍTICO / ISOLAMENTO AUTOMÁTICO SEVERO",
                    1: "DEFCON 1 - MODO BÚNQUER / LOCKDOWN TÁTICO ATIVO"
                }
                _DEFCON_INFO = {
                    "nivel": _DEFCON_NIVEL,
                    "rotulo": rotulos.get(_DEFCON_NIVEL, f"DEFCON {_DEFCON_NIVEL}"),
                    "motivo": motivo,
                    "atualizado_em": r[1],
                    "atualizado_por": r[2]
                }
    except Exception:
        pass
    return _DEFCON_NIVEL


def definir_defcon_nivel(nivel: int, motivo: str, alterado_por: str = "GESTOR_NETTO", db_path: Optional[str] = None) -> Dict[str, Any]:
    """Altera o nível DEFCON de prontidão cibernética."""
    global _DEFCON_NIVEL, _DEFCON_INFO
    nivel = max(1, min(5, int(nivel)))
    _DEFCON_NIVEL = nivel
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    db_p = db_path or _obter_db_path()
    rotulos = {
        5: "DEFCON 5 - NORMAL / MONITORAMENTO DE ROTINA",
        4: "DEFCON 4 - ATENÇÃO / VARREDURA PROATIVA",
        3: "DEFCON 3 - ELEVADO / TOLERÂNCIA ZERO A BRUTE-FORCE",
        2: "DEFCON 2 - CRÍTICO / ISOLAMENTO AUTOMÁTICO SEVERO",
        1: "DEFCON 1 - MODO BÚNQUER / LOCKDOWN TÁTICO ATIVO"
    }
    _DEFCON_INFO = {
        "nivel": nivel,
        "rotulo": rotulos.get(nivel, f"DEFCON {nivel}"),
        "motivo": motivo,
        "atualizado_em": agora,
        "atualizado_por": alterado_por
    }
    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            conn.execute("INSERT OR REPLACE INTO configuracoes_seguranca_soc (chave, valor, atualizado_em, atualizado_por) VALUES ('DEFCON_LEVEL', ?, ?, ?)", (str(nivel), agora, alterado_por))
            conn.execute("INSERT OR REPLACE INTO configuracoes_seguranca_soc (chave, valor, atualizado_em, atualizado_por) VALUES ('DEFCON_MOTIVO', ?, ?, ?)", (motivo, agora, alterado_por))
            conn.commit()
    except Exception as e:
        print(f"[SOC] Erro ao persistir DEFCON: {e}")
    return _DEFCON_INFO


def analisar_inteligencia_ip(ip: str, db_path: Optional[str] = None) -> Dict[str, str]:
    """Retorna dados de inteligência tática, país, bandeira e ASN do IP."""
    ip_limpo = (ip or "").strip()
    if not ip_limpo:
        return {"pais": "Desconhecido", "bandeira": "🌐", "tipo_rede": "Indefinido", "asn": "-", "risco": "BAIXO"}
    if ip_limpo in _CACHE_GEOIP_MEMORIA:
        return _CACHE_GEOIP_MEMORIA[ip_limpo]

    db_p = db_path or _obter_db_path()
    try:
        with sqlite3.connect(db_p) as conn:
            conn.row_factory = sqlite3.Row
            r = conn.execute("SELECT * FROM cache_inteligencia_ip WHERE ip = ?", (ip_limpo,)).fetchone()
            if r:
                res = {
                    "pais": r["pais"],
                    "bandeira": r["bandeira"],
                    "tipo_rede": r["tipo_rede"],
                    "asn": r["asn"],
                    "risco": "BAIXO"
                }
                _CACHE_GEOIP_MEMORIA[ip_limpo] = res
                return res
    except Exception:
        pass

    pais = "Brasil"
    bandeira = "🇧🇷"
    tipo_rede = "Residencial / Móvel"
    asn = "Telecom BR (Claro/Vivo/Brisanet)"
    risco = "BAIXO"

    if ip_limpo in ("127.0.0.1", "::1", "localhost") or ip_limpo.startswith("192.168.") or ip_limpo.startswith("10.") or ip_limpo.startswith("172.16."):
        pais = "Rede Local"
        bandeira = "🏠"
        tipo_rede = "Intranet Local"
        asn = "Rede Privada"
        risco = "SEGURO"
    elif ip_limpo.startswith("198.51.100.") or ip_limpo.startswith("203.0.113."):
        pais = "Ambiente Simulado"
        bandeira = "🪤"
        tipo_rede = "Sandbox Deception"
        asn = "Honeypot Decoy"
        risco = "CRÍTICO"
    elif ip_limpo.startswith("189.") or ip_limpo.startswith("177.") or ip_limpo.startswith("179.") or ip_limpo.startswith("201.") or ip_limpo.startswith("200.") or ip_limpo.startswith("45.180."):
        pais = "Brasil"
        bandeira = "🇧🇷"
        tipo_rede = "Banda Larga / 4G"
        asn = "Telecom BR (Claro/Vivo/Brisanet)"
    elif ip_limpo.startswith("104.") or ip_limpo.startswith("172.6"):
        pais = "EUA / Global"
        bandeira = "☁️"
        tipo_rede = "Proxy / CDN"
        asn = "Cloudflare Anycast"
        risco = "MÉDIO"
    elif ip_limpo.startswith("13.") or ip_limpo.startswith("34.") or ip_limpo.startswith("35.") or ip_limpo.startswith("52.") or ip_limpo.startswith("54.") or ip_limpo.startswith("44."):
        pais = "EUA"
        bandeira = "🇺🇸"
        tipo_rede = "Datacenter / Nuvem"
        asn = "Amazon AWS / Google Cloud"
        risco = "ALTO"
    elif ip_limpo.startswith("185.") or ip_limpo.startswith("194.") or ip_limpo.startswith("91.") or ip_limpo.startswith("45."):
        pais = "Europa / Leste"
        bandeira = "🇪🇺"
        tipo_rede = "VPS / Host Dedicado"
        asn = "OVH / Host Europeu"
        risco = "CRÍTICO"
    elif ip_limpo.startswith("103.") or ip_limpo.startswith("111.") or ip_limpo.startswith("220.") or ip_limpo.startswith("116."):
        pais = "Ásia"
        bandeira = "🇨🇳"
        tipo_rede = "Rede Externa"
        asn = "Asia-Pacific Gateway"
        risco = "CRÍTICO"
    elif ip_limpo.startswith("188.") or ip_limpo.startswith("178.") or ip_limpo.startswith("95."):
        pais = "Rússia / CEI"
        bandeira = "🇷🇺"
        tipo_rede = "Rede Externa / VPN"
        asn = "Rostelecom / Host RU"
        risco = "CRÍTICO"
    else:
        pais = "Internacional"
        bandeira = "🌐"
        tipo_rede = "Tráfego Web Externo"
        asn = "AS Internacional"
        risco = "MÉDIO"

    resultado = {
        "pais": pais,
        "bandeira": bandeira,
        "tipo_rede": tipo_rede,
        "asn": asn,
        "risco": risco
    }
    _CACHE_GEOIP_MEMORIA[ip_limpo] = resultado

    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with sqlite3.connect(db_p) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache_inteligencia_ip (ip, pais, bandeira, tipo_rede, asn, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ip_limpo, pais, bandeira, tipo_rede, asn, agora))
            conn.commit()
    except Exception:
        pass

    return resultado


def calcular_sha256_arquivo(caminho: str) -> Tuple[str, int]:
    """Calcula hash SHA-256 e tamanho de arquivo de forma segura."""
    if not os.path.isfile(caminho):
        return "", 0
    h = hashlib.sha256()
    tam = 0
    with open(caminho, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
            tam += len(chunk)
    return h.hexdigest(), tam


def verificar_integridade_fim(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Verifica a integridade criptográfica dos arquivos núcleo contra o baseline oficial."""
    db_p = db_path or _obter_db_path()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    arquivos_alvo = [
        ("emed_app_server.py", os.path.join(base_dir, "emed_app_server.py")),
        ("supervisorio_web.py", os.path.join(base_dir, "emed_views", "supervisorio_web.py")),
        ("honeypot_deception.py", os.path.join(base_dir, "emed_views", "honeypot_deception.py")),
    ]
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    detalhes = []
    total_violacoes = 0
    with sqlite3.connect(db_p) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        for nome_rel, caminho_abs in arquivos_alvo:
            if not os.path.exists(caminho_abs):
                continue
            hash_atual, tam_atual = calcular_sha256_arquivo(caminho_abs)
            row = conn.execute("SELECT sha256, tamanho_bytes, atualizado_em FROM integridade_arquivos_baseline WHERE arquivo = ?", (nome_rel,)).fetchone()
            if not row:
                conn.execute("""
                    INSERT INTO integridade_arquivos_baseline (arquivo, sha256, tamanho_bytes, atualizado_em)
                    VALUES (?, ?, ?, ?)
                """, (nome_rel, hash_atual, tam_atual, agora))
                conn.commit()
                detalhes.append({
                    "arquivo": nome_rel,
                    "status": "BASELINE_INICIALIZADO",
                    "hash": hash_atual,
                    "tamanho": tam_atual,
                    "msg": "Assinatura digital cadastrada no cofre de integridade."
                })
            else:
                hash_base = row["sha256"]
                if hash_atual == hash_base:
                    detalhes.append({
                        "arquivo": nome_rel,
                        "status": "INVIOLADO",
                        "hash": hash_atual,
                        "tamanho": tam_atual,
                        "msg": "Assinatura 100% autêntica e íntegra."
                    })
                else:
                    total_violacoes += 1
                    detalhes.append({
                        "arquivo": nome_rel,
                        "status": "VIOLADO",
                        "hash_atual": hash_atual,
                        "hash_baseline": hash_base,
                        "tamanho_atual": tam_atual,
                        "msg": "ALERTA: Hash diverge do baseline registrado!"
                    })
    status_geral = "INVIOLADO" if total_violacoes == 0 else "VIOLADO"
    return {
        "ok": True,
        "status": status_geral,
        "violacoes": total_violacoes,
        "total_arquivos": len(detalhes),
        "checagem_data": agora,
        "detalhes": detalhes
    }


def atualizar_baseline_fim(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Atualiza formalmente o baseline de integridade após deploy/modificações autorizadas."""
    db_p = db_path or _obter_db_path()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    arquivos_alvo = [
        ("emed_app_server.py", os.path.join(base_dir, "emed_app_server.py")),
        ("supervisorio_web.py", os.path.join(base_dir, "emed_views", "supervisorio_web.py")),
        ("honeypot_deception.py", os.path.join(base_dir, "emed_views", "honeypot_deception.py")),
    ]
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with sqlite3.connect(db_p) as conn:
        garantir_schema_supervisorio(conn)
        for nome_rel, caminho_abs in arquivos_alvo:
            if os.path.exists(caminho_abs):
                hash_atual, tam_atual = calcular_sha256_arquivo(caminho_abs)
                conn.execute("""
                    INSERT OR REPLACE INTO integridade_arquivos_baseline (arquivo, sha256, tamanho_bytes, atualizado_em)
                    VALUES (?, ?, ?, ?)
                """, (nome_rel, hash_atual, tam_atual, agora))
        conn.commit()
    return {"ok": True, "msg": "Baseline criptográfico atualizado com sucesso.", "data": agora}


def registrar_ou_atualizar_sessao_rastreada(token_str: str, usuario: str, perfil: str, ip: str, user_agent: str, db_path: Optional[str] = None) -> None:
    """Registra batimento cardíaco da sessão para telemetria SOC em tempo real."""
    if not token_str:
        return
    token_hash = hashlib.sha256(token_str.encode()).hexdigest()[:16]
    db_p = db_path or _obter_db_path()
    agora_dt = datetime.datetime.now()
    agora_str = agora_dt.strftime("%d/%m/%Y %H:%M:%S")
    agora_epoch = agora_dt.timestamp()
    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            conn.execute("""
                INSERT INTO sessoes_ativas_rastreamento (
                    token_hash, usuario, perfil, ip_origem, user_agent,
                    criado_em, ultimo_ping, ultimo_ping_epoch, revogado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(token_hash) DO UPDATE SET
                    ultimo_ping = excluded.ultimo_ping,
                    ultimo_ping_epoch = excluded.ultimo_ping_epoch,
                    ip_origem = excluded.ip_origem,
                    user_agent = excluded.user_agent
            """, (token_hash, usuario, perfil, ip, user_agent[:250], agora_str, agora_str, agora_epoch))
            conn.commit()
    except Exception:
        pass


def sessao_esta_revogada(token_str: str, db_path: Optional[str] = None) -> bool:
    """Verifica se a sessão foi sumariamente cancelada pelo SOC."""
    if not token_str:
        return True
    token_hash = hashlib.sha256(token_str.encode()).hexdigest()[:16]
    if token_hash in _SESSOES_REVOGADAS_CACHE:
        return True
    db_p = db_path or _obter_db_path()
    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            r = conn.execute("SELECT revogado FROM sessoes_ativas_rastreamento WHERE token_hash = ?", (token_hash,)).fetchone()
            if r and r[0] == 1:
                _SESSOES_REVOGADAS_CACHE.add(token_hash)
                return True
    except Exception:
        pass
    return False


def revogar_sessao_soc(token_hash: str, db_path: Optional[str] = None) -> bool:
    """Revoga imediatamente uma sessão ativa."""
    _SESSOES_REVOGADAS_CACHE.add(token_hash)
    db_p = db_path or _obter_db_path()
    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            conn.execute("UPDATE sessoes_ativas_rastreamento SET revogado = 1 WHERE token_hash = ?", (token_hash,))
            conn.commit()
            return True
    except Exception:
        return False


def calcular_score_risco_heuristico(usuario: str, status: str, motivo: str, user_agent: str, ip: str) -> Tuple[int, str]:
    """Calcula a pontuação de risco heurístico (1 a 10) e a categoria (BAIXO, MÉDIO, CRÍTICO)."""
    score = 1
    u_upper = (usuario or "").upper()
    m_upper = (motivo or "").upper()
    ua_lower = (user_agent or "").lower()

    if any(k in u_upper for k in ["ROOT", "ADMIN", "MASTER", "DECOY", "DIRETORIA", "DATABASE"]):
        score += 4

    if status in ("BOT_SCANNER_DETECTADO", "IP_BLOQUEADO_PERSISTENTE", "HONEYPOT_DECEPTION_DECOY"):
        score += 5
    elif status in ("SENHA_INCORRETA", "USUARIO_INEXISTENTE"):
        score += 3

    if any(p in u_upper or p in m_upper for p in ["'", "UNION", "SELECT", "<SCRIPT", "../", "SLEEP(", "OR 1=1"]):
        score += 5

    if any(b in ua_lower for b in ["curl", "python", "sqlmap", "nmap", "nikto", "gobuster", "wpscan"]):
        score += 3

    score = min(10, max(1, score))
    nivel = "CRÍTICO" if score >= 8 else ("MÉDIO" if score >= 4 else "BAIXO")
    return score, nivel


def eh_ip_ou_usuario_protegido(ip: str, usuario: str, db_path: str) -> bool:
    """Proteção Anti-Lockout: Garante que Gestor NETTO e IPs seguros nunca sejam auto-bloqueados."""
    u_upper = (usuario or "").strip().upper()
    if any(k in u_upper for k in ("NETTO", "VALFREDO", "DIRETORIA")):
        return True
    if ip in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        import ipaddress
        addr = ipaddress.ip_address(ip.split("%")[0])
        if addr.is_loopback:
            return True
    except Exception:
        pass
    try:
        with sqlite3.connect(db_path) as conn:
            r = conn.execute("SELECT id FROM ips_whitelist_seguranca WHERE ip = ?", (ip,)).fetchone()
            if r:
                return True
    except Exception:
        pass
    return False


def disparar_alerta_soc_critico(ip: str, usuario: str, motivo: str, nivel: str, score: int, agora_str: str, db_path: str) -> None:
    """Registra alerta no banco SOC para visualizacao e envio imediato no WhatsApp do Gestor NETTO."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO alertas_seguranca_soc (data_hora, nivel, titulo, mensagem, ip_origem, usuario, visualizado)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                agora_str, nivel, f"Incidente SOC {nivel} (Score {score}/10)",
                f"Tentativa de ataque no IP {ip} com usuário '{usuario}'. Detalhes: {motivo}",
                ip, usuario
            ))
            conn.commit()
    except Exception as e:
        print(f"[SUPERVISORIO] Erro ao gravar alerta SOC: {e}")


def sanitizar_campo_csv(val: Any) -> str:
    """Sanitiza campos contra CSV Formula Injection (RFC 4180 / OWASP)."""
    s = str(val or "").strip()
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s.replace('"', '""')


def executar_limpeza_automatica_logs(db_path: str) -> int:
    """Mantém a base leve mantendo os 10.000 registros mais recentes da auditoria."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM auditoria_tentativas_login 
                WHERE id NOT IN (
                    SELECT id FROM auditoria_tentativas_login ORDER BY id DESC LIMIT 10000
                )
            """)
            del_count = cur.rowcount
            conn.commit()
            return del_count
    except Exception as e:
        return 0


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

    # 1. Cálculo de Risco Heurístico Inteligente
    score_risco, nivel_risco = calcular_score_risco_heuristico(usuario, status, motivo, user_agent, ip)

    # 2. Verificação de Proteção Anti-Lockout (Gestor NETTO e Whitelist nunca são banidos)
    is_protegido = eh_ip_ou_usuario_protegido(ip, usuario, db_p)

    bloqueio_gerado = 0
    if is_protegido and status != "SUCESSO":
        motivo = f"[ANTI-LOCKOUT ATIVO] {motivo or 'Acesso protegido para Administrador/IP Seguro'}"
    elif status in ("SENHA_INCORRETA", "USUARIO_INEXISTENTE", "BOT_SCANNER_DETECTADO", "HONEYPOT_DECEPTION_DECOY"):
        lista = _FALHAS_RECENTES_IP.get(ip, [])
        lista = [t for t in lista if agora_epoch - t < 300]
        lista.append(agora_epoch)
        _FALHAS_RECENTES_IP[ip] = lista

        defcon_atual = obter_defcon_nivel(db_p)
        limite_falhas = 5
        duracao_min = 15
        if defcon_atual == 4:
            limite_falhas = 4
            duracao_min = 30
        elif defcon_atual == 3:
            limite_falhas = 2
            duracao_min = 120
        elif defcon_atual <= 2:
            limite_falhas = 1
            duracao_min = 1440

        if is_bot_ua:
            duracao_min = max(duracao_min, 60)

        if len(lista) >= limite_falhas or is_bot_ua or status == "HONEYPOT_DECEPTION_DECOY" or defcon_atual == 1:
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
                    """, (ip, f"Bloqueio Auto-Ban ({len(lista)} falhas em 5min / Ataque)", agora_str, expira_iso))
                    conn.commit()
            except Exception as e:
                print(f"[SUPERVISORIO] Erro ao registrar auto-ban para {ip}: {e}")

    # 3. Disparo de Alerta SOC Crítico
    if bloqueio_gerado == 1 or nivel_risco == "CRÍTICO":
        disparar_alerta_soc_critico(ip, usuario, motivo, nivel_risco, score_risco, agora_str, db_p)

    try:
        with sqlite3.connect(db_p) as conn:
            garantir_schema_supervisorio(conn)
            conn.execute("""
                INSERT INTO auditoria_tentativas_login (
                    data_hora, timestamp_epoch, tipo_sistema, usuario_tentado,
                    ip_origem, status_resultado, motivo_detalhado, user_agent,
                    dispositivo_info, geoloc_info, bloqueio_ativo, score_risco, nivel_risco
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
            """, (
                agora_str, agora_epoch, tipo_sistema, (usuario or 'ANONIMO').upper(),
                ip, status, motivo, user_agent[:250], dispositivo[:200], bloqueio_gerado,
                score_risco, nivel_risco
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

    if status_filtro == "CRITICOS":
        query += " AND (score_risco >= 8 OR nivel_risco = 'CRÍTICO' OR bloqueio_ativo = 1 OR status_resultado LIKE 'BOT%' OR status_resultado LIKE 'HONEYPOT%' OR status_resultado LIKE 'IP_BLOQUEADO%')"
    elif status_filtro == "FALHAS":
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

    for r in rows:
        intel = analisar_inteligencia_ip(r["ip_origem"], db_name)
        r["geo_pais"] = intel["pais"]
        r["geo_bandeira"] = intel["bandeira"]
        r["geo_tipo_rede"] = intel["tipo_rede"]
        r["geo_asn"] = intel["asn"]

    return web.json_response({"ok": True, "total": len(rows), "auditoria": rows})


async def api_supervisorio_exportar_csv(request: web.Request) -> web.Response:
    """Exporta o log integral de auditoria de logins em CSV padronizado RFC 4180 UTF-8 BOM."""
    db_name = _obter_db_path(request.app)
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM auditoria_tentativas_login ORDER BY id DESC LIMIT 5000").fetchall()

    csv_lines = [
        "\ufeff\"ID\";\"DATA_HORA\";\"SISTEMA\";\"USUARIO\";\"IP_ORIGEM\";\"RISCO\";\"SCORE\";\"STATUS\";\"MOTIVO\";\"USER_AGENT\";\"BLOQUEADO\""
    ]
    for r in rows:
        ua_limpo = sanitizar_campo_csv(r["user_agent"])
        mot_limpo = sanitizar_campo_csv(r["motivo_detalhado"])
        usr_limpo = sanitizar_campo_csv(r["usuario_tentado"])
        sis_limpo = sanitizar_campo_csv(r["tipo_sistema"])
        score_val = r["score_risco"] if "score_risco" in r.keys() and r["score_risco"] else 1
        nivel_val = r["nivel_risco"] if "nivel_risco" in r.keys() and r["nivel_risco"] else ("CRÍTICO" if score_val >= 8 else "BAIXO")
        csv_lines.append(
            f'"{r["id"]}";"{r["data_hora"]}";"{sis_limpo}";"{usr_limpo}";"{r["ip_origem"]}";'
            f'"{nivel_val}";"{score_val}";"{r["status_resultado"]}";"{mot_limpo}";"{ua_limpo}";"{r["bloqueio_ativo"]}"'
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
        <button class="btn btn-primary" onclick="abrirModalGeradorAcesso()" style="background:#10b981; border-color:#10b981;">🔑 Gerar Acesso</button>
        <button class="btn" onclick="abrirModalSessoes()" style="background:#6d28d9; border-color:#8b5cf6; color:#fff; font-weight:800;">⚡ Sessões Ativas &amp; Kill-Switch</button>
        <button class="btn" onclick="abrirModalFim()" style="background:#047857; border-color:#34d399; color:#fff; font-weight:800;">🔒 Integridade FIM</button>
        <button class="btn" onclick="abrirModalWhitelist()" style="background:#0369a1; border-color:#38bdf8; color:#fff; font-weight:700;">🛡️ Lista Branca</button>
        <button class="btn" onclick="abrirModalAlertasSoc()" style="background:#065f46; border-color:#22c55e; color:#fff; font-weight:700;">📲 Alertas SOC WhatsApp</button>
        <button class="btn btn-primary" onclick="executarVarreduraAgora()">🔍 Escanear Servidor</button>
        <a class="btn" href="/api/supervisorio/exportar-csv" target="_blank">📥 CSV</a>
        <button class="btn" id="btnAutoRefresh" onclick="toggleAutoRefresh()">⏸️ Pausar (5s)</button>
        <a class="btn" href="/portal-cliente" target="_blank" style="background:#0f172a;">🏥 Portal</a>
        <a class="btn" href="/urls" target="_blank" style="background:#1e3a8a; border-color:#3b82f6;">🗂️ URLs</a>
      </div>
    </div>


    <!-- BARRA TÁTICA DEFCON & MODO BÚNQUER DE DEFESA CIBERNÉTICA -->
    <div id="barDefcon" class="card" style="background:#090d16; border:1px solid #1e293b; padding:12px 16px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
      <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
        <div id="badgeDefconVisual" style="padding:6px 14px; border-radius:6px; font-weight:900; font-size:13px; background:#064e3b; color:#34d399; border:1px solid #059669; letter-spacing:1px; display:flex; align-items:center; gap:8px;">
          <span id="dotDefcon" style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#34d399; box-shadow:0 0 10px #34d399;"></span>
          <span id="lblDefconNome">DEFCON 5 — NORMAL</span>
        </div>
        <div style="font-size:12px; color:#cbd5e1;">
          <b id="lblDefconMotivo">Monitoramento contínuo ativo. Auto-defesa operacional.</b>
          <div style="font-size:10.5px; color:var(--muted); margin-top:2px;" id="lblDefconMeta">Atualizado por: SISTEMA &bull; Agora</div>
        </div>
      </div>
      <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
        <span style="font-size:11px; color:var(--muted); font-weight:bold;">PRONTIDÃO TÁTICA:</span>
        <button class="btn" style="padding:4px 9px; font-size:11px; background:#064e3b; color:#34d399; border-color:#059669;" onclick="mudarDefcon(5)">5 Normal</button>
        <button class="btn" style="padding:4px 9px; font-size:11px; background:#075985; color:#7dd3fc; border-color:#0284c7;" onclick="mudarDefcon(4)">4 Atenção</button>
        <button class="btn" style="padding:4px 9px; font-size:11px; background:#78350f; color:#fde047; border-color:#b45309;" onclick="mudarDefcon(3)">3 Elevado</button>
        <button class="btn" style="padding:4px 9px; font-size:11px; background:#7f1d1d; color:#fca5a5; border-color:#ef4444;" onclick="mudarDefcon(2)">2 Crítico</button>
        <button class="btn" id="btnAtivarBunker" style="padding:5px 12px; font-size:11px; font-weight:900; background:#dc2626; color:#fff; border:1px solid #ff4444; box-shadow:0 0 12px rgba(220,38,38,0.5);" onclick="toggleBunkerMode()">🚨 MODO BÚNQUER (DEFCON 1)</button>
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
          <button class="tab-pill" style="border-color:#ef4444; color:#fca5a5; font-weight:800;" onclick="setFiltro('CRITICOS', this)">🚨 Apenas Críticos</button>
          <button class="tab-pill" onclick="setFiltro('FALHAS', this)">⚠️ Apenas Falhas</button>
          <button class="tab-pill" onclick="setFiltro('BLOQUEADOS', this)">⛔ Bloqueios Anti-Robô</button>
          <button class="tab-pill" onclick="setFiltro('SUCESSO', this)">✅ Sucessos</button>
          <input type="text" id="inpBusca" class="inp-search" placeholder="🔍 Buscar usuário ou IP..." oninput="filtrarLocal()" />
        </div>
      </div>

      <div style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Data / Horário</th>
              <th>Nível / Risco</th>
              <th>Sistema</th>
              <th>Usuário Tentado</th>
              <th>IP / Origem Tática (GeoIP &amp; ASN)</th>
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
        } else if (r.status_resultado.includes('HONEYPOT')) {
          stBadge = '<span class="badge badge-danger" style="background:#581c87; border-color:#a855f7;">🪤 HONEYPOT ATIVO</span>';
        }

        const score = r.score_risco || 1;
        const nivel = (r.nivel_risco || (score >= 8 ? 'CRÍTICO' : (score >= 4 ? 'MÉDIO' : 'BAIXO'))).toUpperCase();
        let rBadge = '<span class="badge badge-ok">🟢 BAIXO (1/10)</span>';
        if (nivel.includes('CRÍT') || score >= 8) {
          rBadge = `<span class="badge" style="background:#450a0a; color:#fca5a5; border:1px solid #ef4444; font-weight:800;">🔴 CRÍTICO (${score}/10)</span>`;
        } else if (nivel.includes('MÉD') || score >= 4) {
          rBadge = `<span class="badge" style="background:#451a03; color:#fde047; border:1px solid #f59e0b; font-weight:700;">🟡 MÉDIO (${score}/10)</span>`;
        } else {
          rBadge = `<span class="badge badge-ok">🟢 BAIXO (${score}/10)</span>`;
        }

        const isLocal = (r.ip_origem === '127.0.0.1' || r.ip_origem === '::1');
        const btnBlock = isLocal ? '' : `<button class="btn btn-danger" style="padding:2px 6px; font-size:10px;" data-ip="${_escapeHtml(r.ip_origem)}" onclick="bloquearIpManual(this.dataset.ip)">⛔ Bloquear</button>`;
        const btnSafe = isLocal ? '' : `<button class="btn" style="padding:2px 6px; font-size:10px; background:#0284c7; border-color:#38bdf8; color:#fff; margin-left:4px;" data-ip="${_escapeHtml(r.ip_origem)}" onclick="adicionarIpWhitelistRapido(this.dataset.ip)">🛡️ Whitelist</button>`;

        return `
          <tr>
            <td style="white-space:nowrap; font-weight:bold;">${_escapeHtml(r.data_hora)}</td>
            <td>${rBadge}</td>
            <td><span class="badge badge-sys">${_escapeHtml(r.tipo_sistema)}</span></td>
            <td><b style="color:#e2e8f0;">${_escapeHtml(r.usuario_tentado)}</b></td>
            <td>
              <code>${_escapeHtml(r.ip_origem)}</code><br/>
              <span style="font-size:10px; color:#94a3b8; display:inline-flex; align-items:center; gap:3px; margin-top:2px;">
                ${r.geo_bandeira || '🌐'} <b>${_escapeHtml(r.geo_pais || 'Brasil')}</b> &bull; ${_escapeHtml(r.geo_tipo_rede || 'Rede')}
              </span>
            </td>
            <td>${stBadge}</td>
            <td style="max-width:240px; color:#cbd5e1;">${_escapeHtml(r.motivo_detalhado || '-')}</td>
            <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; color:var(--muted);" title="${_escapeHtml(r.user_agent)}">
              ${_escapeHtml(r.user_agent ? r.user_agent.slice(0, 32) + '...' : '-')}
            </td>
            <td style="white-space:nowrap;">${btnBlock}${btnSafe}</td>
          </tr>
        `;
      }).join('');
    }

    
    // ==========================================
    
    // ==========================================
    // CONTROLE TÁTICO DEFCON & MODO BÚNQUER
    // ==========================================
    let DEFCON_NIVEL_ATUAL = 5;

    async function carregarDefcon() {
      try {
        const res = await fetch('/api/supervisorio/defcon').then(r => r.json());
        if (res.ok && res.defcon) {
          DEFCON_NIVEL_ATUAL = res.defcon.nivel;
          atualizarUiDefcon(res.defcon);
        }
      } catch (e) {
        console.error('Erro ao ler DEFCON:', e);
      }
    }

    function atualizarUiDefcon(d) {
      const b = document.getElementById('badgeDefconVisual');
      const dot = document.getElementById('dotDefcon');
      const lbl = document.getElementById('lblDefconNome');
      const mot = document.getElementById('lblDefconMotivo');
      const meta = document.getElementById('lblDefconMeta');
      const btnBunker = document.getElementById('btnAtivarBunker');

      lbl.textContent = d.rotulo || `DEFCON ${d.nivel}`;
      mot.textContent = d.motivo || 'Operação ativa';
      meta.textContent = `Atualizado por: ${d.atualizado_por || 'SISTEMA'} • ${d.atualizado_em || ''}`;

      if (d.nivel === 5) {
        b.style.background = '#064e3b'; b.style.color = '#34d399'; b.style.borderColor = '#059669';
        dot.style.background = '#34d399'; dot.style.boxShadow = '0 0 10px #34d399';
        btnBunker.textContent = '🚨 MODO BÚNQUER (DEFCON 1)';
        btnBunker.style.background = '#dc2626';
      } else if (d.nivel === 4) {
        b.style.background = '#075985'; b.style.color = '#7dd3fc'; b.style.borderColor = '#0284c7';
        dot.style.background = '#38bdf8'; dot.style.boxShadow = '0 0 10px #38bdf8';
        btnBunker.textContent = '🚨 MODO BÚNQUER (DEFCON 1)';
      } else if (d.nivel === 3) {
        b.style.background = '#78350f'; b.style.color = '#fde047'; b.style.borderColor = '#b45309';
        dot.style.background = '#f59e0b'; dot.style.boxShadow = '0 0 10px #f59e0b';
        btnBunker.textContent = '🚨 MODO BÚNQUER (DEFCON 1)';
      } else if (d.nivel === 2) {
        b.style.background = '#7f1d1d'; b.style.color = '#fca5a5'; b.style.borderColor = '#ef4444';
        dot.style.background = '#ef4444'; dot.style.boxShadow = '0 0 10px #ef4444';
        btnBunker.textContent = '🚨 MODO BÚNQUER (DEFCON 1)';
      } else if (d.nivel === 1) {
        b.style.background = '#450a0a'; b.style.color = '#fca5a5'; b.style.borderColor = '#dc2626';
        b.style.animation = 'pulse 1.5s infinite';
        dot.style.background = '#dc2626'; dot.style.boxShadow = '0 0 15px #dc2626';
        btnBunker.textContent = '🟢 DESATIVAR BÚNQUER (DEFCON 5)';
        btnBunker.style.background = '#15803d';
      }
    }

    async function mudarDefcon(nivel) {
      const nomes = {5: "DEFCON 5 (Normal)", 4: "DEFCON 4 (Atenção)", 3: "DEFCON 3 (Elevado)", 2: "DEFCON 2 (Crítico)", 1: "DEFCON 1 (Modo Búnquer)"};
      const motivo = prompt(`Alterar nível de prontidão tática para ${nomes[nivel]}?\nInforme a justificativa do SOC:`, `Ajuste operacional de rotina`) || '';
      if (!motivo) return;
      try {
        const res = await fetch('/api/supervisorio/defcon/alterar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ nivel, motivo })
        }).then(r => r.json());
        alert(res.msg || 'Nível DEFCON alterado.');
        carregarDefcon();
      } catch (e) {
        alert('Erro ao alterar nível DEFCON.');
      }
    }

    async function toggleBunkerMode() {
      if (DEFCON_NIVEL_ATUAL === 1) {
        if (!confirm('Deseja desativar o Modo Búnquer e restaurar o sistema para DEFCON 5 (Normal)?')) return;
        mudarDefcon(5);
      } else {
        if (!confirm('🚨 ALERTA MÁXIMO DE DEFESA CIBERNÉTICA:\n\nAtivar o MODO BÚNQUER (DEFCON 1)?\n\nO servidor fechará o acesso externo para TODOS os IPs da Internet, atendendo EXCLUSIVAMENTE os IPs da Lista Branca do Gestor NETTO.')) return;
        mudarDefcon(1);
      }
    }

    // ==========================================
    // RADAR DE SESSÕES ATIVAS & KILL-SWITCH
    // ==========================================
    async function abrirModalSessoes() {
      document.getElementById('modalSessoes').style.display = 'flex';
      carregarSessoesAtivas();
    }

    function fecharModalSessoes() {
      document.getElementById('modalSessoes').style.display = 'none';
    }

    async function carregarSessoesAtivas() {
      const tb = document.getElementById('tbodySessoes');
      tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:10px; color:var(--muted);">Varrendo conexões ativas...</td></tr>';
      try {
        const res = await fetch('/api/supervisorio/sessoes/listar').then(r => r.json());
        if (!res.ok || !res.sessoes || res.sessoes.length === 0) {
          tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:12px; color:var(--muted);">Nenhuma sessão ativa nos últimos minutos.</td></tr>';
          return;
        }
        tb.innerHTML = res.sessoes.map(s => `
          <tr>
            <td>
              <b style="color:#e2e8f0;">${_escapeHtml(s.usuario)}</b><br/>
              <span class="badge badge-sys" style="font-size:9.5px;">${_escapeHtml(s.perfil)}</span>
            </td>
            <td>
              <code>${_escapeHtml(s.ip_origem)}</code><br/>
              <span style="font-size:10px; color:#94a3b8;">${s.bandeira || '🌐'} ${_escapeHtml(s.pais || '')} &bull; ${_escapeHtml(s.tipo_rede || '')}</span>
            </td>
            <td style="white-space:nowrap; font-size:11px; color:#34d399;"><b>${_escapeHtml(s.tempo_relativo)}</b></td>
            <td style="max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:10.5px; color:var(--muted);" title="${_escapeHtml(s.user_agent)}">
              ${_escapeHtml(s.user_agent ? s.user_agent.slice(0, 30) + '...' : '-')}
            </td>
            <td style="text-align:right;">
              <button class="btn btn-danger" style="padding:2px 7px; font-size:10px; font-weight:800;" data-hash="${_escapeHtml(s.token_hash)}" data-usr="${_escapeHtml(s.usuario)}" onclick="revogarSessao(this.dataset.hash, this.dataset.usr)">
                ⚡ Kill Session
              </button>
            </td>
          </tr>
        `).join('');
      } catch (e) {
        tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:10px; color:#f87171;">Erro ao rastrear sessões.</td></tr>';
      }
    }

    async function revogarSessao(hash, usr) {
      if (!confirm(`Deseja derrubar e revogar imediatamente a sessão do usuário ${usr}? O dispositivo será desconectado no próximo comando.`)) return;
      try {
        const res = await fetch('/api/supervisorio/sessoes/revogar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ token_hash: hash })
        }).then(r => r.json());
        alert(res.msg || 'Sessão revogada.');
        carregarSessoesAtivas();
      } catch (e) {
        alert('Erro ao revogar sessão.');
      }
    }

    // ==========================================
    // MONITOR DE INTEGRIDADE FIM (SHA-256)
    // ==========================================
    async function abrirModalFim() {
      document.getElementById('modalFim').style.display = 'flex';
      carregarStatusFim();
    }

    function fecharModalFim() {
      document.getElementById('modalFim').style.display = 'none';
    }

    async function carregarStatusFim() {
      const tb = document.getElementById('tbodyFim');
      tb.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:10px; color:var(--muted);">Calculando hashes SHA-256...</td></tr>';
      try {
        const res = await fetch('/api/supervisorio/fim/status').then(r => r.json());
        const kpi = document.getElementById('kpiFimVal');
        const kpiSub = document.getElementById('kpiFimSub');
        if (res.status === 'INVIOLADO') {
          kpi.textContent = 'INVIOLADO';
          kpi.style.color = '#34d399';
          kpiSub.textContent = `${res.total_arquivos}/${res.total_arquivos} Arquivos Autênticos`;
        } else {
          kpi.textContent = 'VIOLAÇÃO!';
          kpi.style.color = '#ef4444';
          kpiSub.textContent = `🚨 ${res.violacoes} arquivo(s) adulterado(s)`;
        }

        tb.innerHTML = (res.detalhes || []).map(f => {
          const isOk = (f.status === 'INVIOLADO' || f.status === 'BASELINE_INICIALIZADO');
          const badge = isOk ? '<span class="badge badge-ok">✅ INVIOLADO</span>' : '<span class="badge badge-danger">🚨 ADULTERADO</span>';
          return `
            <tr>
              <td><b style="color:#e2e8f0;">${_escapeHtml(f.arquivo)}</b></td>
              <td>${badge}</td>
              <td><code style="font-size:10px; color:#38bdf8;">${_escapeHtml(f.hash ? f.hash.slice(0, 20) + '...' : '-')}</code></td>
              <td style="font-size:11px; color:var(--muted);">${f.tamanho ? Math.round(f.tamanho / 1024) + ' KB' : '-'}</td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        tb.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:10px; color:#f87171;">Erro ao checar FIM.</td></tr>';
      }
    }

    async function atualizarBaselineFim() {
      if (!confirm('Deseja homologar a versão atual dos arquivos de código como o novo Baseline oficial?\nOs hashes SHA-256 atuais se tornarão o padrão de integridade.')) return;
      try {
        const res = await fetch('/api/supervisorio/fim/atualizar-baseline', { method: 'POST' }).then(r => r.json());
        alert(res.msg || 'Baseline atualizado.');
        carregarStatusFim();
      } catch (e) {
        alert('Erro ao atualizar baseline.');
      }
    }

    // FUNÇÕES DA LISTA BRANCA ANTI-LOCKOUT
    // ==========================================
    async function abrirModalWhitelist() {
      document.getElementById('modalWhitelist').style.display = 'flex';
      carregarListaWhitelist();
    }

    function fecharModalWhitelist() {
      document.getElementById('modalWhitelist').style.display = 'none';
    }

    async function carregarListaWhitelist() {
      const tb = document.getElementById('tbodyWhitelist');
      tb.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:10px; color:var(--muted);">Carregando...</td></tr>';
      try {
        const res = await fetch('/api/supervisorio/whitelist').then(r => r.json());
        if (!res.ok || !res.whitelist || res.whitelist.length === 0) {
          tb.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:12px; color:var(--muted);">Nenhum IP na Lista Branca além dos padrões.</td></tr>';
          return;
        }
        tb.innerHTML = res.whitelist.map(w => `
          <tr>
            <td><code style="color:#38bdf8; font-weight:bold;">${_escapeHtml(w.ip)}</code></td>
            <td style="color:#cbd5e1;">${_escapeHtml(w.descricao || '-')}</td>
            <td style="font-size:11px; color:var(--muted);">${_escapeHtml(w.adicionado_em || '-')}</td>
            <td style="text-align:right;">
              <button class="btn btn-danger" style="padding:2px 7px; font-size:10px;" data-ip="${_escapeHtml(w.ip)}" onclick="removerIpWhitelist(this.dataset.ip)">✕ Remover</button>
            </td>
          </tr>
        `).join('');
      } catch(e) {
        tb.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:10px; color:#f87171;">Erro ao carregar lista branca.</td></tr>';
      }
    }

    async function salvarIpWhitelist() {
      const ip = document.getElementById('inpWlIp').value.trim();
      const descricao = document.getElementById('inpWlDesc').value.trim();
      if (!ip) {
        alert('Informe o endereço IP que deseja proteger contra bloqueios.');
        return;
      }
      try {
        const res = await fetch('/api/supervisorio/whitelist/adicionar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ ip, descricao: descricao || 'IP Seguro Cadastrado' })
        }).then(r => r.json());
        alert(res.msg || 'IP adicionado com sucesso!');
        document.getElementById('inpWlIp').value = '';
        document.getElementById('inpWlDesc').value = '';
        carregarListaWhitelist();
      } catch(e) {
        alert('Erro ao cadastrar IP na lista branca.');
      }
    }

    async function adicionarIpWhitelistRapido(ip) {
      const desc = prompt(`Adicionar o IP ${ip} à Lista Branca Anti-Lockout (Imune a Bloqueios)?\nInforme a identificação:`, 'Dispositivo Seguro / Escritório') || '';
      if (!desc) return;
      try {
        const res = await fetch('/api/supervisorio/whitelist/adicionar', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ ip, descricao: desc })
        }).then(r => r.json());
        alert(res.msg || 'IP protegido na Lista Branca com sucesso!');
        carregarAuditoria();
      } catch(e) {
        alert('Erro ao salvar IP na Lista Branca.');
      }
    }

    async function removerIpWhitelist(ip) {
      if (!confirm(`Deseja remover o IP ${ip} da Lista Branca? Ele voltará a ser monitorado normalmente.`)) return;
      try {
        const res = await fetch('/api/supervisorio/whitelist/remover', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ ip })
        }).then(r => r.json());
        alert(res.msg || 'Removido com sucesso');
        carregarListaWhitelist();
      } catch(e) {
        alert('Erro ao remover IP.');
      }
    }

    // ==========================================
    // FUNÇÕES DA CENTRAL DE ALERTAS SOC WHATSAPP
    // ==========================================
    let CACHE_ALERTAS_SOC = [];

    async function abrirModalAlertasSoc() {
      document.getElementById('modalAlertasSoc').style.display = 'flex';
      carregarAlertasSoc();
    }

    function fecharModalAlertasSoc() {
      document.getElementById('modalAlertasSoc').style.display = 'none';
    }

    async function carregarAlertasSoc() {
      const tb = document.getElementById('tbodyAlertasSoc');
      tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:10px; color:var(--muted);">Carregando alertas...</td></tr>';
      try {
        const res = await fetch('/api/supervisorio/alertas-soc').then(r => r.json());
        if (!res.ok || !res.alertas || res.alertas.length === 0) {
          tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:12px; color:var(--muted);">Nenhum alerta crítico ativo no momento. Tudo seguro!</td></tr>';
          return;
        }
        CACHE_ALERTAS_SOC = res.alertas;
        tb.innerHTML = res.alertas.map(a => `
          <tr>
            <td style="white-space:nowrap; font-size:11px;">${_escapeHtml(a.data_hora)}</td>
            <td><span class="badge" style="background:#450a0a; color:#fca5a5; border:1px solid #ef4444; font-weight:800;">🔴 ${a.nivel}</span></td>
            <td><b>${_escapeHtml(a.titulo)}</b><br><small style="color:var(--muted);">${_escapeHtml(a.mensagem || a.detalhes || '')}</small></td>
            <td><code>${_escapeHtml(a.ip_origem || '-')}</code></td>
            <td style="white-space:nowrap;">
              <button class="btn" style="background:#22c55e; color:#052e16; font-size:10px; font-weight:800; padding:2px 6px;"
                data-titulo="${_escapeHtml(a.titulo)}" data-detalhes="${_escapeHtml(a.mensagem || a.detalhes || '')}" data-ip="${_escapeHtml(a.ip_origem)}"
                onclick="dispararWhatsAppIncidente(this.dataset.titulo, this.dataset.detalhes, this.dataset.ip)">
                📲 Wpp NETTO
              </button>
            </td>
          </tr>
        `).join('');
      } catch(e) {
        tb.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:10px; color:#f87171;">Erro ao carregar alertas.</td></tr>';
      }
    }

    function dispararWhatsAppIncidente(titulo, detalhes, ip) {
      const msg = `🚨 *[ALERTA SOC eMED - INCIDENTE CRÍTICO]*%0A%0A*Ameaça:* ${encodeURIComponent(titulo)}%0A*IP Invasor:* ${encodeURIComponent(ip)}%0A*Detalhes:* ${encodeURIComponent(detalhes)}%0A%0A*Ação Tomada:* O IP foi isolado preventivamente. Verifique o console supervisório:%0Ahttps://emedservice.med.br/supervisorio`;
      window.open(`https://wa.me/5585999150273?text=${msg}`, '_blank');
    }

    function enviarAlertaResumoWhatsApp() {
      const qtd = CACHE_ALERTAS_SOC.length;
      const msg = `🛡️ *[eMED SOC - RESUMO DE SEGURANÇA]*%0A%0AOlá Gestor NETTO,%0AO sistema registrou *${qtd} alerta(s) crítico(s)* nas últimas horas.%0AServidor eMED operando com Honeypot ativo e bloqueio automático.%0A%0AAcesse o painel para auditar:%0Ahttps://emedservice.med.br/supervisorio`;
      window.open(`https://wa.me/5585999150273?text=${msg}`, '_blank');
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

  <!-- MODAL DE SESSÕES ATIVAS & KILL-SWITCH SOC -->
  <div id="modalSessoes" class="modal-backdrop">
    <div class="modal-box" style="max-width:750px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:16px; font-weight:800; color:#c084fc; display:flex; align-items:center; gap:8px;">
          <span>⚡ Radar de Sessões Ativas &amp; Kill-Switch Instantâneo</span>
        </h3>
        <button class="btn" onclick="fecharModalSessoes()" style="padding:4px 8px;">✕</button>
      </div>

      <div style="background:#2e1065; border-left:4px solid #8b5cf6; padding:10px 12px; border-radius:6px; font-size:11.5px; color:#ddd6fe; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <b>Controle Operacional de Acessos:</b> Monitoramento em tempo real de tokens autenticados. Caso um celular seja extraviado ou um técnico desligado, encerre o acesso imediatamente pelo botão Kill-Switch.
        </div>
        <button class="btn" style="background:#8b5cf6; color:#fff; font-size:11px; font-weight:bold;" onclick="carregarSessoesAtivas()">🔄 Atualizar</button>
      </div>

      <div style="max-height:280px; overflow-y:auto; border:1px solid var(--card-border); border-radius:8px;">
        <table>
          <thead>
            <tr>
              <th>Usuário / Perfil</th>
              <th>IP / Localização</th>
              <th>Último Batimento</th>
              <th>Dispositivo / Navegador</th>
              <th style="text-align:right;">Kill-Switch</th>
            </tr>
          </thead>
          <tbody id="tbodySessoes">
            <tr><td colspan="5" style="text-align:center; padding:12px; color:var(--muted);">Carregando radar de sessões...</td></tr>
          </tbody>
        </table>
      </div>

      <div style="margin-top:14px; text-align:right;">
        <button class="btn" onclick="fecharModalSessoes()">Fechar</button>
      </div>
    </div>
  </div>

  <!-- MODAL DE INTEGRIDADE FIM (FILE INTEGRITY MONITORING) -->
  <div id="modalFim" class="modal-backdrop">
    <div class="modal-box" style="max-width:760px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:16px; font-weight:800; color:#34d399; display:flex; align-items:center; gap:8px;">
          <span>🔒 Monitor de Integridade de Arquivos Núcleo (FIM SHA-256)</span>
        </h3>
        <button class="btn" onclick="fecharModalFim()" style="padding:4px 8px;">✕</button>
      </div>

      <div style="background:#064e3b; border-left:4px solid #10b981; padding:10px 12px; border-radius:6px; font-size:11.5px; color:#a7f3d0; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <b>Anti-Adulteração Criptográfica:</b> Compara os hashes SHA-256 dos arquivos executáveis com o baseline homologado em cofre. Se qualquer byte for alterado clandestinamente, o SOC soa o alarme vermelho.
        </div>
        <button class="btn" style="background:#059669; color:#fff; font-size:11px; font-weight:bold;" onclick="atualizarBaselineFim()">🔄 Homologar Novo Baseline</button>
      </div>

      <div style="max-height:280px; overflow-y:auto; border:1px solid var(--card-border); border-radius:8px;">
        <table>
          <thead>
            <tr>
              <th>Arquivo Núcleo</th>
              <th>Status</th>
              <th>Hash SHA-256 Atual</th>
              <th>Tamanho</th>
            </tr>
          </thead>
          <tbody id="tbodyFim">
            <tr><td colspan="4" style="text-align:center; padding:12px; color:var(--muted);">Verificando integridade dos arquivos...</td></tr>
          </tbody>
        </table>
      </div>

      <div style="margin-top:14px; display:flex; justify-content:space-between; align-items:center;">
        <button class="btn" onclick="carregarStatusFim()" style="font-size:11px;">🔍 Reverificar Hashes</button>
        <button class="btn" onclick="fecharModalFim()">Fechar</button>
      </div>
    </div>
  </div>

  <!-- MODAL DE LISTA BRANCA ANTI-LOCKOUT -->
  <div id="modalWhitelist" class="modal-backdrop">
    <div class="modal-box" style="max-width:680px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:16px; font-weight:800; color:#38bdf8; display:flex; align-items:center; gap:8px;">
          <span>🛡️ Lista Branca Anti-Lockout (IPs Imunes a Bloqueio)</span>
        </h3>
        <button class="btn" onclick="fecharModalWhitelist()" style="padding:4px 8px;">✕</button>
      </div>

      <div style="background:#082f49; border-left:4px solid #38bdf8; padding:10px 12px; border-radius:6px; font-size:11.5px; color:#bae6fd; margin-bottom:14px;">
        <b>Proteção de Acesso:</b> IPs e usuários cadastrados nesta lista <u>nunca serão bloqueados</u> pela proteção de Auto-Ban contra Brute-Force, garantindo que o Gestor NETTO e filiais autorizadas mantenham acesso contínuo.
      </div>

      <!-- FORMULÁRIO DE ADIÇÃO DE IP -->
      <div style="display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap;">
        <input type="text" id="inpWlIp" class="inp-search" placeholder="Endereço IP (ex: 201.24.55.12)" style="flex:1; min-width:180px;" />
        <input type="text" id="inpWlDesc" class="inp-search" placeholder="Descrição / Identificação (ex: PC Escritório NETTO)" style="flex:1.5; min-width:200px;" />
        <button class="btn btn-primary" onclick="salvarIpWhitelist()" style="background:#0284c7; font-weight:700;">+ Adicionar à Lista</button>
      </div>

      <!-- TABELA DE IPS NA WHITELIST -->
      <div style="max-height:260px; overflow-y:auto; border:1px solid var(--card-border); border-radius:8px;">
        <table>
          <thead>
            <tr>
              <th>IP Seguro</th>
              <th>Descrição / Finalidade</th>
              <th>Cadastrado Em</th>
              <th style="text-align:right;">Ação</th>
            </tr>
          </thead>
          <tbody id="tbodyWhitelist">
            <tr><td colspan="4" style="text-align:center; padding:12px; color:var(--muted);">Carregando Lista Branca...</td></tr>
          </tbody>
        </table>
      </div>

      <div style="margin-top:14px; text-align:right;">
        <button class="btn" onclick="fecharModalWhitelist()">Fechar</button>
      </div>
    </div>
  </div>

  <!-- MODAL DE ALERTAS SOC WHATSAPP -->
  <div id="modalAlertasSoc" class="modal-backdrop">
    <div class="modal-box" style="max-width:700px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
        <h3 style="font-size:16px; font-weight:800; color:#4ade80; display:flex; align-items:center; gap:8px;">
          <span>📲 Central de Alertas SOC WhatsApp (Gestor NETTO)</span>
        </h3>
        <button class="btn" onclick="fecharModalAlertasSoc()" style="padding:4px 8px;">✕</button>
      </div>

      <div style="background:#052e16; border-left:4px solid #22c55e; padding:10px 12px; border-radius:6px; font-size:11.5px; color:#bbf7d0; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <b>Notificações Críticas de Segurança:</b> Alertas em tempo real enviados diretamente ao telefone do Gestor NETTO (<b>85 99915-0273</b>).
        </div>
        <button class="btn" style="background:#22c55e; color:#052e16; font-weight:900; font-size:11px;" onclick="enviarAlertaResumoWhatsApp()">📲 Enviar Resumo ao WhatsApp</button>
      </div>

      <!-- TABELA DE INCIDENTES CRÍTICOS -->
      <div style="font-weight:700; font-size:12px; color:#cbd5e1; margin-bottom:6px;">Últimos Incidentes Críticos Registrados:</div>
      <div style="max-height:280px; overflow-y:auto; border:1px solid var(--card-border); border-radius:8px;">
        <table>
          <thead>
            <tr>
              <th>Horário</th>
              <th>Nível</th>
              <th>Título / Ameaça</th>
              <th>IP Origem</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody id="tbodyAlertasSoc">
            <tr><td colspan="5" style="text-align:center; padding:12px; color:var(--muted);">Carregando alertas do SOC...</td></tr>
          </tbody>
        </table>
      </div>

      <div style="margin-top:14px; display:flex; justify-content:space-between; align-items:center;">
        <button class="btn" onclick="carregarAlertasSoc()" style="font-size:11px;">🔄 Atualizar Lista</button>
        <button class="btn" onclick="fecharModalAlertasSoc()">Fechar</button>
      </div>
    </div>
  </div>

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




async def api_supervisorio_whitelist_listar(request: web.Request) -> web.Response:
    """Lista todos os IPs cadastrados na Lista Branca Anti-Lockout."""
    db_name = _obter_db_path(request.app)
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM ips_whitelist_seguranca ORDER BY id ASC").fetchall()]
    return web.json_response({"ok": True, "total": len(rows), "whitelist": rows})


async def api_supervisorio_whitelist_adicionar(request: web.Request) -> web.Response:
    """Adiciona um IP confiável à Lista Branca para imunidade de Auto-Ban."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    ip = str(body.get("ip", "")).strip()
    desc = str(body.get("descricao", "IP Confiável")).strip()
    if not ip or len(ip) < 3:
        return web.json_response({"ok": False, "msg": "Informe um IP válido."}, status=400)
    agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.execute("INSERT OR REPLACE INTO ips_whitelist_seguranca (ip, descricao, adicionado_em) VALUES (?, ?, ?)", (ip, desc, agora_str))
        conn.commit()
    # Remove de eventual quarentena
    _IPS_BLOQUEADOS_CACHE.pop(ip, None)
    return web.json_response({"ok": True, "msg": f"IP {ip} adicionado à Lista Branca com sucesso (Imune a bloqueio)."})


async def api_supervisorio_whitelist_remover(request: web.Request) -> web.Response:
    """Remove um IP da Lista Branca."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    ip = str(body.get("ip", "")).strip()
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.execute("DELETE FROM ips_whitelist_seguranca WHERE ip = ?", (ip,))
        conn.commit()
    return web.json_response({"ok": True, "msg": f"IP {ip} removido da Lista Branca."})



async def api_supervisorio_defcon_status(request: web.Request) -> web.Response:
    """Retorna o nível DEFCON atual e o relatório de prontidão cibernética."""
    db_name = _obter_db_path(request.app)
    obter_defcon_nivel(db_name)
    return web.json_response({"ok": True, "defcon": _DEFCON_INFO})


async def api_supervisorio_defcon_alterar(request: web.Request) -> web.Response:
    """Altera o nível DEFCON do sistema com registro de auditoria."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    nivel = int(body.get("nivel", 5))
    motivo = str(body.get("motivo", "Alteração tática solicitada pelo Gestor")).strip()
    user = getattr(request, "_emed_user", None) or {}
    gestor_nome = user.get("nome", "GESTOR_NETTO") if isinstance(user, dict) else "GESTOR_NETTO"
    info = definir_defcon_nivel(nivel, motivo, gestor_nome, db_name)
    return web.json_response({"ok": True, "defcon": info, "msg": f"Prontidão cibernética ajustada para {info['rotulo']}."})


async def api_supervisorio_fim_status(request: web.Request) -> web.Response:
    """Retorna o status do monitor de integridade de arquivos vitais (FIM)."""
    db_name = _obter_db_path(request.app)
    fim_res = verificar_integridade_fim(db_name)
    return web.json_response(fim_res)


async def api_supervisorio_fim_atualizar(request: web.Request) -> web.Response:
    """Atualiza o baseline de integridade criptográfica após deploy homologado."""
    db_name = _obter_db_path(request.app)
    res = atualizar_baseline_fim(db_name)
    return web.json_response(res)


async def api_supervisorio_sessoes_listar(request: web.Request) -> web.Response:
    """Retorna a lista de sessões de técnicos e gestores ativas nas últimas 2 horas."""
    db_name = _obter_db_path(request.app)
    limite_epoch = time.time() - 7200
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("""
            SELECT token_hash, usuario, perfil, ip_origem, user_agent, criado_em, ultimo_ping, ultimo_ping_epoch, revogado
            FROM sessoes_ativas_rastreamento
            WHERE ultimo_ping_epoch >= ? AND revogado = 0
            ORDER BY ultimo_ping_epoch DESC LIMIT 100
        """, (limite_epoch,)).fetchall()]
    for r in rows:
        intel = analisar_inteligencia_ip(r["ip_origem"], db_name)
        r["bandeira"] = intel["bandeira"]
        r["pais"] = intel["pais"]
        r["tipo_rede"] = intel["tipo_rede"]
        minutos = max(0, int((time.time() - r["ultimo_ping_epoch"]) / 60))
        r["tempo_relativo"] = "Agora mesmo" if minutos == 0 else f"{minutos} min atrás"
    return web.json_response({"ok": True, "total": len(rows), "sessoes": rows})


async def api_supervisorio_sessoes_revogar(request: web.Request) -> web.Response:
    """Kill-Switch: Revoga uma sessão ativa instantaneamente."""
    db_name = _obter_db_path(request.app)
    body = await request.json()
    token_hash = str(body.get("token_hash", "")).strip()
    if not token_hash:
        return web.json_response({"ok": False, "msg": "Hash de sessão inválido."}, status=400)
    sucesso = revogar_sessao_soc(token_hash, db_name)
    return web.json_response({"ok": sucesso, "msg": "Sessão sumariamente cancelada pelo SOC. Dispositivo desconectado."})


async def api_supervisorio_alertas_soc(request: web.Request) -> web.Response:
    """Retorna alertas de incidentes críticos para notificação do Gestor."""
    db_name = _obter_db_path(request.app)
    with sqlite3.connect(db_name) as conn:
        garantir_schema_supervisorio(conn)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute("SELECT * FROM alertas_seguranca_soc ORDER BY id DESC LIMIT 20").fetchall()]
    return web.json_response({"ok": True, "total": len(rows), "alertas": rows})


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
    app.router.add_get("/api/supervisorio/whitelist", api_supervisorio_whitelist_listar)
    app.router.add_post("/api/supervisorio/whitelist/adicionar", api_supervisorio_whitelist_adicionar)
    app.router.add_post("/api/supervisorio/whitelist/remover", api_supervisorio_whitelist_remover)
    app.router.add_get("/api/supervisorio/defcon", api_supervisorio_defcon_status)
    app.router.add_post("/api/supervisorio/defcon/alterar", api_supervisorio_defcon_alterar)
    app.router.add_get("/api/supervisorio/fim/status", api_supervisorio_fim_status)
    app.router.add_post("/api/supervisorio/fim/atualizar-baseline", api_supervisorio_fim_atualizar)
    app.router.add_get("/api/supervisorio/sessoes/listar", api_supervisorio_sessoes_listar)
    app.router.add_post("/api/supervisorio/sessoes/revogar", api_supervisorio_sessoes_revogar)
    app.router.add_get("/api/supervisorio/alertas-soc", api_supervisorio_alertas_soc)

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
