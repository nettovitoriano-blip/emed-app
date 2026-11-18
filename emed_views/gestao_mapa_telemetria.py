# -*- coding: utf-8 -*-
"""
Módulo de Gestão Geográfica, Telemetria TLF e Dossiê Radiológico RDC 611/2022
Desenvolvido para EMED Eletromedicina.

Recursos:
1. Mapa Interativo do Gestor (Passo 3):
   - Mapeamento dos 504 clientes (com e sem contrato)
   - Diagnóstico da infraestrutura elétrica (Rede Trifásica e Aterramento em Ohms)
   - Despacho, traçado de rotas e contato direto via WhatsApp
2. Telemetria TLF & Proteção do Tubo de Raios-X (Passo 4):
   - Monitoramento contínuo de Fuga no Terra (mA)
   - Monitoramento de desequilíbrio trifásico e surtos
   - Horímetro, aquecimento do anodo e scans acumulados
   - Alertas preditivos antes de queima do inversor
3. Repositório do Dossiê Radiológico (RDC 611 / ANVISA & Física Médica):
   - Levantamento Radiométrico, Laudos de CQ da Física Médica, EPIs de Chumbo,
     Relatórios de Preventiva com ART e Certificados de Calibração RBC
"""

import os
import json
import sqlite3
import datetime
from pathlib import Path
from aiohttp import web

def _get_db_path(request: web.Request) -> str:
    db = request.app.get("db_name")
    if db and os.path.exists(db):
        return str(db)
    cand = Path(__file__).resolve().parent.parent / "emed.db"
    return str(cand)

def _get_db_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ==============================================================================
# PASSO 3: APIS DO MAPA INTERATIVO DO GESTOR & INFRAESTRUTURA ELÉTRICA
# ==============================================================================

async def api_mapa_clientes_geolocalizados(request: web.Request) -> web.Response:
    """Retorna a lista georreferenciada de todos os clientes com dados de contrato e infraestrutura."""
    db_path = _get_db_path(request)
    filtro_uf = request.query.get("uf", "").strip().upper()
    filtro_tipo = request.query.get("tipo", "").strip().upper() # CONTRATO, AVULSO, TODOS
    filtro_infra = request.query.get("infra", "").strip().upper() # CRITICO, ATENCAO, EXCELENTE, NAO_AFERIDO

    with _get_db_connection(db_path) as conn:
        # Obter clientes com coordenadas
        query = """
            SELECT 
                c.id, c.codigo_cliente, c.nome, c.cpf_cnpj, c.razao_social,
                c.endereco, c.cidade, c.estado, c.telefone, c.email, c.contato,
                c.tipo_contrato, c.latitude, c.longitude, c.status,
                c.rede_trifasica_status, c.tensao_fases_v, c.resistencia_terra_ohms,
                c.status_infra_terra, c.data_ultima_afericao_eletrica, c.obs_infra_eletrica,
                (SELECT COUNT(*) FROM clientes_equipamentos ce WHERE (ce.cliente = c.nome OR ce.cnpj = c.cpf_cnpj) AND ce.status NOT IN ('CONCLUÍDO', 'CANCELADO')) as os_abertas,
                (SELECT COUNT(*) FROM clientes_equipamentos ce WHERE (ce.cliente = c.nome OR ce.cnpj = c.cpf_cnpj)) as total_os
            FROM clientes c
            WHERE c.latitude IS NOT NULL AND c.latitude != '' AND c.latitude != 'NAN'
        """
        params = []

        if filtro_uf:
            query += " AND c.estado = ?"
            params.append(filtro_uf)

        if filtro_tipo == "CONTRATO":
            query += " AND UPPER(c.tipo_contrato) LIKE '%CONTRATO%'"
        elif filtro_tipo == "AVULSO":
            query += " AND UPPER(c.tipo_contrato) LIKE '%AVULSO%'"

        if filtro_infra == "CRITICO":
            query += " AND c.status_infra_terra = 'CRÍTICO'"
        elif filtro_infra == "ATENCAO":
            query += " AND c.status_infra_terra = 'ATENÇÃO'"
        elif filtro_infra == "EXCELENTE":
            query += " AND c.status_infra_terra = 'EXCELENTE'"
        elif filtro_infra == "NAO_AFERIDO":
            query += " AND (c.status_infra_terra = 'NÃO AFERIDO' OR c.status_infra_terra IS NULL OR c.status_infra_terra = '')"

        rows = conn.execute(query, params).fetchall()

        clientes = []
        for r in rows:
            try:
                lat = float(str(r["latitude"]).replace(",", "."))
                lng = float(str(r["longitude"]).replace(",", "."))
            except (ValueError, TypeError):
                continue

            tipo = "CONTRATO" if "CONTRATO" in str(r["tipo_contrato"] or "").upper() else "AVULSO"
            status_terra = r["status_infra_terra"] or "NÃO AFERIDO"
            rede = r["rede_trifasica_status"] or "NÃO AFERIDA"

            # Determinar prioridade visual do alfinete:
            # 1. Vermelho: OS Aberta (Máquina com problema) ou Terra Crítico
            # 2. Amarelo: Terra em Atenção ou Rede Flutuante
            # 3. Verde: Contrato ativo & Terra estável/excelente
            # 4. Azul: Cliente Avulso
            if r["os_abertas"] > 0 or status_terra == "CRÍTICO":
                cor_marcador = "vermelho"
            elif status_terra == "ATENÇÃO" or rede == "FLUTUANTE":
                cor_marcador = "amarelo"
            elif tipo == "CONTRATO":
                cor_marcador = "verde"
            else:
                cor_marcador = "azul"

            clientes.append({
                "id": r["id"],
                "codigo": r["codigo_cliente"],
                "nome": r["nome"],
                "razao_social": r["razao_social"] or r["nome"],
                "cpf_cnpj": r["cpf_cnpj"],
                "endereco": r["endereco"],
                "cidade": r["cidade"],
                "estado": r["estado"],
                "telefone": r["telefone"],
                "email": r["email"],
                "contato": r["contato"],
                "tipo_contrato": tipo,
                "lat": lat,
                "lng": lng,
                "cor_marcador": cor_marcador,
                "os_abertas": r["os_abertas"],
                "total_os": r["total_os"],
                "rede_trifasica": rede,
                "tensao_fases": r["tensao_fases_v"] or "",
                "resistencia_terra_ohms": r["resistencia_terra_ohms"],
                "status_infra_terra": status_terra,
                "data_afericao": r["data_ultima_afericao_eletrica"] or "",
                "obs_infra": r["obs_infra_eletrica"] or ""
            })

    # Totalizadores para os KPIs superiores
    total_geral = len(clientes)
    total_contratos = sum(1 for c in clientes if c["tipo_contrato"] == "CONTRATO")
    total_avulsos = total_geral - total_contratos
    total_criticos_terra = sum(1 for c in clientes if c["status_infra_terra"] == "CRÍTICO")
    total_sem_afericao = sum(1 for c in clientes if c["status_infra_terra"] == "NÃO AFERIDO")

    return web.json_response({
        "ok": True,
        "total": total_geral,
        "kpis": {
            "total": total_geral,
            "contratos": total_contratos,
            "avulsos": total_avulsos,
            "criticos_terra": total_criticos_terra,
            "sem_afericao": total_sem_afericao
        },
        "clientes": clientes
    })


async def api_mapa_registrar_afericao(request: web.Request) -> web.Response:
    """Permite ao gestor ou técnico registrar aferição de terra e rede trifásica do cliente."""
    db_path = _get_db_path(request)
    body = await request.json()

    cliente_id = int(body.get("cliente_id", 0))
    resistencia = body.get("resistencia_terra_ohms")
    rede_status = str(body.get("rede_trifasica_status", "ESTÁVEL")).strip().upper()
    tensao = str(body.get("tensao_fases_v", "")).strip()
    obs = str(body.get("obs_infra_eletrica", "")).strip()
    data_afericao = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    res_val = None
    if resistencia is not None and str(resistencia).strip() != "":
        try:
            res_val = float(str(resistencia).replace(",", "."))
        except ValueError:
            return web.json_response({"ok": False, "msg": "Valor de resistência de terra inválido."}, status=400)

    # Classificação normativa do aterramento hospitalar/radiológico
    # <= 5 Ohms: Excelente (Padrão ouro para tomógrafos e angiografia)
    # 5.1 a 10 Ohms: Atenção (Aceitável para equipamentos menores, mas requer monitoramento)
    # > 10 Ohms: Crítico (Alto risco de queima de placas eletrônicas e inversor)
    if res_val is None:
        status_terra = "NÃO AFERIDO"
    elif res_val <= 5.0:
        status_terra = "EXCELENTE"
    elif res_val <= 10.0:
        status_terra = "ATENÇÃO"
    else:
        status_terra = "CRÍTICO"

    with _get_db_connection(db_path) as conn:
        conn.execute("""
            UPDATE clientes
            SET rede_trifasica_status = ?,
                tensao_fases_v = ?,
                resistencia_terra_ohms = ?,
                status_infra_terra = ?,
                data_ultima_afericao_eletrica = ?,
                obs_infra_eletrica = ?
            WHERE id = ?
        """, (rede_status, tensao, res_val, status_terra, data_afericao, obs, cliente_id))
        conn.commit()

    return web.json_response({
        "ok": True,
        "msg": f"✅ Aferição registrada com sucesso! Status do terra: {status_terra} ({res_val or 0} Ω).",
        "status_infra_terra": status_terra
    })


# ==============================================================================
# PASSO 4: APIS DE TELEMETRIA TLF (FUGA NO TERRA & MONITORAMENTO DO TUBO DE RAIOS-X)
# ==============================================================================

async def api_telemetria_tlf_coletar(request: web.Request) -> web.Response:
    """Endpoint de ingestão para sensores e hardware TLF nos equipamentos dos clientes."""
    db_path = _get_db_path(request)
    body = await request.json()

    cliente_id = int(body.get("cliente_id", 0))
    cliente_nome = str(body.get("cliente_nome", "")).strip()
    equipamento = str(body.get("equipamento", "TOMÓGRAFO")).strip().upper()
    
    corrente_fuga = float(body.get("corrente_fuga_ma", 0.0))
    tensao_r = float(body.get("tensao_r", 220.0))
    tensao_s = float(body.get("tensao_s", 220.0))
    tensao_t = float(body.get("tensao_t", 220.0))
    temp_anodo = float(body.get("temperatura_anodo_c", 45.0))
    scans = int(body.get("scans_acumulados", 0))
    horimetro = float(body.get("horimetro_horas", 0.0))

    # Cálculo do desbalanceamento de tensão trifásica (%)
    media_tensao = (tensao_r + tensao_s + tensao_t) / 3.0
    desv_max = max(abs(tensao_r - media_tensao), abs(tensao_s - media_tensao), abs(tensao_t - media_tensao))
    desbalanceamento = (desv_max / media_tensao) * 100.0 if media_tensao > 0 else 0.0

    # Lógica de Diagnóstico Preditivo Inteligente:
    # Fuga de terra > 10 mA = Risco Crítico ao Inversor / Risco de Choque
    # Fuga de terra > 5 mA = Atenção
    # Desbalanceamento > 5% = Risco ao gerador de alta tensão
    status_alerta = "NORMAL"
    diagnostico_partes = []

    if corrente_fuga >= 10.0:
        status_alerta = "CRÍTICO"
        diagnostico_partes.append(f"Fuga no terra crítica ({corrente_fuga:.1f} mA > 10 mA). Risco iminente de queima do inversor.")
    elif corrente_fuga >= 5.0:
        status_alerta = "ATENÇÃO"
        diagnostico_partes.append(f"Fuga de terra em nível de atenção ({corrente_fuga:.1f} mA).")

    if desbalanceamento >= 5.0:
        if status_alerta != "CRÍTICO":
            status_alerta = "ATENÇÃO"
        diagnostico_partes.append(f"Desbalanceamento trifásico elevado ({desbalanceamento:.1f}% > 5%).")

    if temp_anodo >= 75.0:
        status_alerta = "CRÍTICO"
        diagnostico_partes.append(f"Superaquecimento do anodo ({temp_anodo:.1f} ºC). Pausa térmica recomendada.")

    if not diagnostico_partes:
        diagnostico_partes.append("Operação nominal normal. Parâmetros elétricos e térmicos estáveis.")

    diag_final = " | ".join(diagnostico_partes)
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO telemetria_tlf_leituras (
                cliente_id, cliente_nome, equipamento, data_hora,
                corrente_fuga_ma, tensao_r, tensao_s, tensao_t, desbalanceamento_perc,
                temperatura_anodo_c, scans_acumulados, horimetro_horas,
                status_alerta, mensagem_diagnostico, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cliente_id, cliente_nome, equipamento, agora,
            corrente_fuga, tensao_r, tensao_s, tensao_t, desbalanceamento,
            temp_anodo, scans, horimetro, status_alerta, diag_final, json.dumps(body)
        ))
        conn.commit()

    return web.json_response({
        "ok": True,
        "msg": "Leitura de telemetria recebida e gravada com sucesso.",
        "status_alerta": status_alerta,
        "diagnostico": diag_final
    })


async def api_telemetria_tlf_painel(request: web.Request) -> web.Response:
    """Retorna o resumo das leituras de telemetria dos equipamentos monitorados."""
    db_path = _get_db_path(request)

    with _get_db_connection(db_path) as conn:
        # Últimas 50 leituras
        rows = conn.execute("""
            SELECT id, cliente_id, cliente_nome, equipamento, data_hora,
                   corrente_fuga_ma, tensao_r, tensao_s, tensao_t, desbalanceamento_perc,
                   temperatura_anodo_c, scans_acumulados, horimetro_horas,
                   status_alerta, mensagem_diagnostico
            FROM telemetria_tlf_leituras
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()

        leituras = [dict(r) for r in rows]

        # Resumo por equipamento mais recente
        equipamentos_agrupados = conn.execute("""
            SELECT cliente_nome, equipamento,
                   status_alerta, corrente_fuga_ma, desbalanceamento_perc,
                   temperatura_anodo_c, scans_acumulados, horimetro_horas,
                   data_hora, mensagem_diagnostico
            FROM telemetria_tlf_leituras
            WHERE id IN (
                SELECT MAX(id) FROM telemetria_tlf_leituras GROUP BY cliente_id, equipamento
            )
            ORDER BY 
                CASE status_alerta 
                    WHEN 'CRÍTICO' THEN 1 
                    WHEN 'ATENÇÃO' THEN 2 
                    ELSE 3 
                END
        """).fetchall()

        cards_status = [dict(r) for r in equipamentos_agrupados]

    return web.json_response({
        "ok": True,
        "total_leituras": len(leituras),
        "equipamentos_monitorados": cards_status,
        "historico_recente": leituras
    })


async def api_telemetria_tlf_simular(request: web.Request) -> web.Response:
    """Simula uma rajada de leituras de telemetria TLF para demonstração comercial / técnica."""
    db_path = _get_db_path(request)
    import random

    clientes_teste = [
        (1, "A FOCUS DIAGNÓSTICO POR IMAGEM E APOIO ADMINISTRATIVO LTDA", "TOMÓGRAFO GE REVOLUTION ACT"),
        (2, "A G S CLINICA MEDICA", "RAIO-X FIXO DIGITAL HF500M"),
        (4, "AHBB", "TOMÓGRAFO PHILIPS INGENUITY"),
        (5, "CLÍNICA SANTA CLARA", "ARCO CIRÚRGICO GE OEC 9900")
    ]

    leituras_geradas = []
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_db_connection(db_path) as conn:
        for cid, nome, equip in clientes_teste:
            fuga = round(random.uniform(1.2, 14.5), 1)
            tr = round(random.uniform(216.0, 224.0), 1)
            ts = round(random.uniform(215.0, 225.0), 1)
            tt = round(random.uniform(214.0, 226.0), 1)
            temp = round(random.uniform(38.0, 68.0), 1)
            scans = random.randint(85000, 210000)
            horimetro = round(scans / 45.0, 1)

            # status
            if fuga >= 10.0:
                st = "CRÍTICO"
                msg = f"ALERTA TLF: Fuga no condutor de terra ({fuga} mA). Necessária intervenção técnica preventiva no aterramento."
            elif fuga >= 5.0:
                st = "ATENÇÃO"
                msg = f"Aviso TLF: Nível de fuga elevado ({fuga} mA). Fases R={tr}V, S={ts}V, T={tt}V."
            else:
                st = "NORMAL"
                msg = f"Telemetria nominal. Fuga={fuga} mA, Temp={temp} ºC, Rede balanceada."

            media = (tr + ts + tt) / 3.0
            desbal = round((max(abs(tr - media), abs(ts - media), abs(tt - media)) / media) * 100.0, 2)

            conn.execute("""
                INSERT INTO telemetria_tlf_leituras (
                    cliente_id, cliente_nome, equipamento, data_hora,
                    corrente_fuga_ma, tensao_r, tensao_s, tensao_t, desbalanceamento_perc,
                    temperatura_anodo_c, scans_acumulados, horimetro_horas,
                    status_alerta, mensagem_diagnostico
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, nome, equip, agora, fuga, tr, ts, tt, desbal, temp, scans, horimetro, st, msg))

            leituras_geradas.append({"cliente": nome, "equipamento": equip, "fuga_ma": fuga, "status": st})

        conn.commit()

    return web.json_response({
        "ok": True,
        "msg": f"✅ {len(leituras_geradas)} telemetrias em tempo real simuladas e gravadas!",
        "leituras": leituras_geradas
    })


# ==============================================================================
# DOSSIÊ RADIOLÓGICO RDC 611/2022 (VIGILÂNCIA SANITÁRIA & FÍSICA MÉDICA)
# ==============================================================================

async def api_dossie_documentos_listar(request: web.Request) -> web.Response:
    """Lista os documentos de conformidade sanitária e radiológica de um cliente ou gerais."""
    db_path = _get_db_path(request)
    cliente_id = request.query.get("cliente_id", "").strip()

    with _get_db_connection(db_path) as conn:
        query = """
            SELECT id, cliente_id, cliente_nome, equipamento, categoria, titulo,
                   numero_documento, orgao_emissor, responsavel_tecnico, registro_profissional,
                   data_emissao, data_validade, status_validade, arquivo_path, arquivo_nome, observacoes
            FROM dossie_radiologico_documentos
        """
        params = []
        if cliente_id:
            query += " WHERE cliente_id = ?"
            params.append(cliente_id)

        query += " ORDER BY data_validade ASC"
        rows = conn.execute(query, params).fetchall()

        docs = []
        hoje = datetime.date.today()
        for r in rows:
            d = dict(r)
            # Calcular dias até expirar
            dias_restantes = None
            if d.get("data_validade"):
                try:
                    dt_val = datetime.datetime.strptime(d["data_validade"][:10], "%Y-%m-%d").date()
                    dias_restantes = (dt_val - hoje).days
                except Exception:
                    pass

            d["dias_restantes"] = dias_restantes
            if dias_restantes is not None:
                if dias_restantes < 0:
                    d["status_alerta"] = "VENCIDO"
                elif dias_restantes <= 30:
                    d["status_alerta"] = "VENCENDO"
                else:
                    d["status_alerta"] = "VÁLIDO"
            else:
                d["status_alerta"] = "VÁLIDO"

            docs.append(d)

    return web.json_response({
        "ok": True,
        "total": len(docs),
        "documentos": docs
    })


async def api_dossie_documentos_salvar(request: web.Request) -> web.Response:
    """Registra um novo documento no repositório do Dossiê Radiológico."""
    db_path = _get_db_path(request)
    body = await request.json()

    cliente_id = int(body.get("cliente_id", 0))
    cliente_nome = str(body.get("cliente_nome", "")).strip()
    equipamento = str(body.get("equipamento", "")).strip()
    categoria = str(body.get("categoria", "CONTROLE_QUALIDADE_FISICA")).strip()
    titulo = str(body.get("titulo", "")).strip()
    numero_doc = str(body.get("numero_documento", "")).strip()
    orgao = str(body.get("orgao_emissor", "EMED FÍSICA MÉDICA")).strip()
    resp_tec = str(body.get("responsavel_tecnico", "")).strip()
    reg_prof = str(body.get("registro_profissional", "")).strip()
    dt_emissao = str(body.get("data_emissao", "")).strip()
    dt_validade = str(body.get("data_validade", "")).strip()
    obs = str(body.get("observacoes", "")).strip()

    if not titulo or not dt_validade:
        return web.json_response({"ok": False, "msg": "Título e data de validade são obrigatórios."}, status=400)

    with _get_db_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO dossie_radiologico_documentos (
                cliente_id, cliente_nome, equipamento, categoria, titulo,
                numero_documento, orgao_emissor, responsavel_tecnico, registro_profissional,
                data_emissao, data_validade, status_validade, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ATIVO', ?)
        """, (cliente_id, cliente_nome, equipamento, categoria, titulo, numero_doc, orgao, resp_tec, reg_prof, dt_emissao, dt_validade, obs))
        conn.commit()

    return web.json_response({"ok": True, "msg": "✅ Documento inserido no Dossiê da RDC 611 com sucesso!"})


# ==============================================================================
# PÁGINA WEB INTEGRADA: MAPA INTERATIVO DO GESTOR & TELEMETRIA TLF
# ==============================================================================

async def handle_pagina_gestao_mapa_telemetria(request: web.Request) -> web.Response:
    """Entrega a aplicação web do Mapa Interativo com Leaflet.js e Painel TLF."""
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EMED • Mapa Interativo do Gestor & Telemetria TLF</title>
  
  <!-- Leaflet CSS & JS para Mapa de Alta Performance -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  
  <!-- Estilos Premium EMED Dark/Blue -->
  <style>
    :root {
      --bg: #0b1329;
      --card-bg: #132247;
      --card-border: #1e3a8a;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --green: #10b981;
      --amber: #f59e0b;
      --red: #ef4444;
      --blue: #3b82f6;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

    /* Topbar */
    header {
      background: linear-gradient(90deg, #091227 0%, #172554 100%);
      padding: 12px 24px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 1000;
    }
    .logo-area { display: flex; align-items: center; gap: 12px; }
    .logo-area h1 { font-size: 1.15rem; font-weight: 700; color: #fff; letter-spacing: 0.5px; }
    .logo-area span { background: #1e3a8a; color: var(--accent); font-size: 0.75rem; padding: 3px 8px; border-radius: 9999px; font-weight: 600; }
    
    .tabs-nav { display: flex; gap: 8px; }
    .tab-btn {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      color: var(--text-muted);
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s ease;
      font-weight: 600;
    }
    .tab-btn.active, .tab-btn:hover {
      background: var(--accent);
      color: #091227;
      border-color: var(--accent);
    }

    /* Main Container */
    .app-body {
      display: flex;
      flex: 1;
      height: calc(100vh - 58px);
      position: relative;
    }

    /* Sidebar de Filtros & KPIs */
    .sidebar {
      width: 360px;
      background: var(--card-bg);
      border-right: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      z-index: 999;
      box-shadow: 4px 0 15px rgba(0,0,0,0.3);
    }
    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      margin-top: 10px;
    }
    .kpi-pill {
      background: rgba(0,0,0,0.25);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 8px 10px;
      border-radius: 8px;
      text-align: center;
    }
    .kpi-pill .val { font-size: 1.1rem; font-weight: 800; }
    .kpi-pill .lbl { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; margin-top: 2px; }

    .sidebar-filters {
      padding: 14px 16px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .filter-group label {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      margin-bottom: 4px;
      display: block;
    }
    .filter-select, .filter-input {
      width: 100%;
      background: #091227;
      border: 1px solid #1e3a8a;
      color: #fff;
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
    }
    .filter-select:focus, .filter-input:focus { border-color: var(--accent); }

    .sidebar-list {
      flex: 1;
      overflow-y: auto;
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .client-card {
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      padding: 10px 12px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .client-card:hover {
      background: rgba(56, 189, 248, 0.1);
      border-color: var(--accent);
      transform: translateY(-1px);
    }
    .client-card-title {
      font-size: 0.85rem;
      font-weight: 700;
      color: #fff;
      margin-bottom: 4px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .badge {
      font-size: 0.65rem;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .badge-contrato { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .badge-avulso { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid #3b82f6; }
    .badge-critico { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .badge-atencao { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    
    .client-card-loc { font-size: 0.75rem; color: var(--text-muted); }
    .client-card-infra {
      display: flex;
      gap: 12px;
      margin-top: 6px;
      font-size: 0.72rem;
      border-top: 1px dashed rgba(255,255,255,0.1);
      padding-top: 6px;
    }

    /* Área do Mapa */
    #map {
      flex: 1;
      height: 100%;
      background: #060d1f;
      z-index: 1;
    }

    /* Painel de Telemetria TLF */
    .view-container {
      display: none;
      flex: 1;
      height: 100%;
      overflow-y: auto;
      padding: 24px 32px;
      background: var(--bg);
    }
    .view-container.active { display: block; }

    .grid-tlf {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      margin-top: 16px;
    }
    .card-tlf {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .card-tlf-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }
    .tlf-val-large {
      font-size: 2rem;
      font-weight: 800;
      color: #fff;
    }
    .tlf-val-large span { font-size: 0.9rem; font-weight: 600; color: var(--text-muted); }

    /* Modal de Aferição */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
      backdrop-filter: blur(4px);
      z-index: 9999;
      align-items: center;
      justify-content: center;
    }
    .modal-box {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      width: 440px;
      padding: 24px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .modal-header h3 { font-size: 1.1rem; color: #fff; }
    .btn-close { background: none; border: none; color: var(--text-muted); font-size: 1.2rem; cursor: pointer; }
    .btn-salvar {
      background: var(--accent);
      color: #091227;
      font-weight: 700;
      border: none;
      padding: 10px 16px;
      border-radius: 6px;
      cursor: pointer;
      width: 100%;
      margin-top: 12px;
    }
    .btn-salvar:hover { background: var(--accent-hover); }

    /* Botão Rápido Flutuante */
    .btn-simular-tlf {
      background: linear-gradient(135deg, #38bdf8 0%, #3b82f6 100%);
      color: #091227;
      border: none;
      font-weight: 700;
      font-size: 0.85rem;
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
    }
    .btn-simular-tlf:hover { opacity: 0.9; }

    /* Custom Leaflet Dark Popups */
    .leaflet-popup-content-wrapper {
      background: #0f1c3f !important;
      color: #f8fafc !important;
      border: 1px solid #2563eb !important;
      border-radius: 10px !important;
      padding: 6px !important;
    }
    .leaflet-popup-tip { background: #0f1c3f !important; }
    .popup-content h4 { color: #38bdf8; font-size: 0.95rem; margin-bottom: 4px; font-weight: 700; }
    .popup-content p { font-size: 0.8rem; color: #cbd5e1; margin-bottom: 6px; }
    .popup-actions { display: flex; gap: 6px; margin-top: 10px; }
    .popup-btn {
      flex: 1;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      text-decoration: none;
      text-align: center;
      cursor: pointer;
      border: none;
    }
    .popup-btn-waze { background: #00d2d3; color: #000; }
    .popup-btn-wpp { background: #25d366; color: #000; }
    .popup-btn-aferir { background: #3b82f6; color: #fff; }
  </style>
</head>
<body>

  <!-- Topbar -->
  <header>
    <div class="logo-area">
      <h1>EMED ELETROMEDICINA</h1>
      <span>GESTOR PRO • PASSO 3 & 4</span>
    </div>
    
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="alternarAba('mapa')">🗺️ Mapa de Clientes (504)</button>
      <button class="tab-btn" onclick="alternarAba('tlf')">📡 Telemetria TLF & Tubo</button>
      <button class="tab-btn" onclick="alternarAba('dossie')">🛡️ Dossiê RDC 611 / ANVISA</button>
    </div>
  </header>

  <!-- Corpo Principal -->
  <div class="app-body">
    
    <!-- ABA 1: MAPA INTERATIVO (PASSO 3) -->
    <div id="viewMapa" style="display:flex; flex:1; height:100%;">
      <!-- Sidebar de Filtros -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <div style="font-size:0.9rem; font-weight:700;">Base Geográfica de Clientes</div>
          <div style="font-size:0.75rem; color:var(--text-muted);">Alfinetes georreferenciados para despacho e rotas</div>
          
          <div class="kpi-row">
            <div class="kpi-pill"><div class="val" id="kpiTotal" style="color:var(--accent);">--</div><div class="lbl">Total Mapeado</div></div>
            <div class="kpi-pill"><div class="val" id="kpiContratos" style="color:var(--green);">--</div><div class="lbl">Com Contrato</div></div>
            <div class="kpi-pill"><div class="val" id="kpiAvulsos" style="color:var(--blue);">--</div><div class="lbl">Clientes Avulsos</div></div>
            <div class="kpi-pill"><div class="val" id="kpiCriticosTerra" style="color:var(--red);">--</div><div class="lbl">Terra Crítico (>10Ω)</div></div>
          </div>
        </div>

        <div class="sidebar-filters">
          <div class="filter-group">
            <label>Buscar Hospital / Clínica:</label>
            <input type="text" class="filter-input" id="filtroTexto" placeholder="Digite nome ou cidade..." oninput="filtrarClientesLocal()" />
          </div>

          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
            <div class="filter-group">
              <label>Tipo:</label>
              <select class="filter-select" id="filtroTipo" onchange="carregarClientesMapa()">
                <option value="TODOS">Todos</option>
                <option value="CONTRATO">Contrato (65)</option>
                <option value="AVULSO">Avulso (439)</option>
              </select>
            </div>

            <div class="filter-group">
              <label>Aterramento:</label>
              <select class="filter-select" id="filtroInfra" onchange="carregarClientesMapa()">
                <option value="">Todos</option>
                <option value="CRITICO">Crítico (>10Ω)</option>
                <option value="ATENCAO">Atenção (5-10Ω)</option>
                <option value="EXCELENTE">Excelente (≤5Ω)</option>
                <option value="NAO_AFERIDO">Não Aferido</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Lista de Clientes -->
        <div class="sidebar-list" id="listaClientesSidebar">
          <!-- Renderizado dinamicamente -->
        </div>
      </aside>

      <!-- Elemento do Mapa Leaflet -->
      <div id="map"></div>
    </div>

    <!-- ABA 2: TELEMETRIA TLF & PROTEÇÃO DO TUBO (PASSO 4) -->
    <div id="viewTlf" class="view-container">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
          <h2 style="font-size:1.3rem; font-weight:800; color:#fff;">📡 Telemetria Preditiva TLF & Monitoramento do Tubo de Raios-X</h2>
          <p style="color:var(--text-muted); font-size:0.85rem; margin-top:4px;">
            Vigilância contínua da corrente de fuga no terra (mA), desbalanceamento trifásico e carga térmica do tubo para prevenir queima do inversor.
          </p>
        </div>
        <button class="btn-simular-tlf" onclick="simularTelemetriaTLF()">⚡ Simular Leitura em Tempo Real</button>
      </div>

      <div class="grid-tlf" id="gridCardsTlf">
        <!-- Cards dos Equipamentos Monitorados -->
      </div>
    </div>

    <!-- ABA 3: DOSSIÊ RADIOLÓGICO RDC 611 / ANVISA -->
    <div id="viewDossie" class="view-container">
      <div style="margin-bottom:16px;">
        <h2 style="font-size:1.3rem; font-weight:800; color:#fff;">🛡️ Dossiê de Conformidade Sanitária & Radiológica (RDC 611/2022)</h2>
        <p style="color:var(--text-muted); font-size:0.85rem; margin-top:4px;">
          Repositório integrado de Levantamento Radiométrico, Laudos da Física Médica, Integridade de EPIs e Calibrações com alarmes automáticos.
        </p>
      </div>

      <div style="background:var(--card-bg); border:1px solid var(--card-border); border-radius:12px; padding:16px; overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
          <thead>
            <tr style="border-bottom:1px solid rgba(255,255,255,0.1); text-align:left; color:var(--text-muted);">
              <th style="padding:10px;">CLIENTE / HOSPITAL</th>
              <th style="padding:10px;">EQUIPAMENTO</th>
              <th style="padding:10px;">TIPO DE LAUDO / NORMA</th>
              <th style="padding:10px;">ÓRGÃO / FÍSICO MÉDICO</th>
              <th style="padding:10px;">EMISSÃO</th>
              <th style="padding:10px;">VALIDADE</th>
              <th style="padding:10px;">SITUAÇÃO</th>
            </tr>
          </thead>
          <tbody id="tabelaDossieCorpo">
            <!-- Renderizado dinamicamente -->
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <!-- Modal para Aferição Rápida de Rede & Terra -->
  <div class="modal-overlay" id="modalAfericao">
    <div class="modal-box">
      <div class="modal-header">
        <h3 id="modalClienteNome">Aferição de Infraestrutura</h3>
        <button class="btn-close" onclick="fecharModalAfericao()">&times;</button>
      </div>
      
      <input type="hidden" id="modalClienteId" />

      <div class="filter-group" style="margin-bottom:12px;">
        <label>Resistência de Terra Medida (Ohms Ω):</label>
        <input type="number" step="0.1" class="filter-input" id="inpTerraOhms" placeholder="Ex: 3.2 (≤ 5Ω é o ideal para tomógrafo)" />
        <small style="color:var(--text-muted); font-size:0.7rem; margin-top:2px; display:block;">
          • ≤ 5Ω: Excelente | • 5 a 10Ω: Atenção | • > 10Ω: Crítico (risco de queima)
        </small>
      </div>

      <div class="filter-group" style="margin-bottom:12px;">
        <label>Qualidade da Rede Trifásica:</label>
        <select class="filter-select" id="selRedeTrifasica">
          <option value="ESTÁVEL">Estável (Fases equilibradas)</option>
          <option value="FLUTUANTE">Flutuante (Oscilações frequentes)</option>
          <option value="CRÍTICA">Crítica (Queda de fase / surtos)</option>
          <option value="NÃO AFERIDA">Não Aferida</option>
        </select>
      </div>

      <div class="filter-group" style="margin-bottom:12px;">
        <label>Tensão das Fases Medidas (V):</label>
        <input type="text" class="filter-input" id="inpTensaoFases" placeholder="Ex: 220V - 220V - 219V ou 380V" />
      </div>

      <div class="filter-group" style="margin-bottom:12px;">
        <label>Observações do Técnico / Gestor:</label>
        <textarea class="filter-input" id="inpObsInfra" rows="2" placeholder="Local sem profissional local para aferir, aterramento antigo, etc."></textarea>
      </div>

      <button class="btn-salvar" onclick="salvarAfericaoEletrica()">💾 Salvar Diagnóstico de Infraestrutura</button>
    </div>
  </div>

  <!-- Script da Aplicação -->
  <script>
    let MAPA = null;
    let MARKERS_LAYER = null;
    let TODOS_CLIENTES = [];

    // Inicialização do Mapa Leaflet
    function inicializarMapa() {
      // Centro aproximado do Brasil (Brasília)
      MAPA = L.map('map', { zoomControl: true }).setView([-15.7801, -47.9292], 5);

      // Camada CartoDB Dark Matter para harmonia visual
      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
      }).addTo(MAPA);

      MARKERS_LAYER = L.layerGroup().addTo(MAPA);
    }

    // Gerador de Ícone Customizado com Cores
    function criarIconeColorido(cor) {
      const coresHex = {
        'verde': '#10b981',    // Contrato ativo
        'azul': '#3b82f6',     // Avulso
        'vermelho': '#ef4444', // OS Aberta ou Terra Crítico
        'amarelo': '#f59e0b'   // Atenção
      };
      const c = coresHex[cor] || '#3b82f6';
      
      const svgPin = `
        <svg width="28" height="38" viewBox="0 0 28 38" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 0C6.268 0 0 6.268 0 14C0 24.5 14 38 14 38C14 38 28 24.5 28 14C28 6.268 21.732 0 14 0Z" fill="${c}"/>
          <circle cx="14" cy="14" r="6" fill="#091227"/>
        </svg>
      `;
      return L.divIcon({
        className: 'custom-pin',
        html: svgPin,
        iconSize: [28, 38],
        iconAnchor: [14, 38],
        popupAnchor: [0, -36]
      });
    }

    // Carregar Clientes da API
    async function carregarClientesMapa() {
      const tipo = document.getElementById('filtroTipo').value;
      const infra = document.getElementById('filtroInfra').value;

      try {
        const res = await fetch(`/api/mapa/clientes-geolocalizados?tipo=${tipo}&infra=${infra}`).then(r => r.json());
        if (!res.ok) return;

        TODOS_CLIENTES = res.clientes || [];
        
        // Atualizar KPIs
        document.getElementById('kpiTotal').textContent = res.kpis.total;
        document.getElementById('kpiContratos').textContent = res.kpis.contratos;
        document.getElementById('kpiAvulsos').textContent = res.kpis.avulsos;
        document.getElementById('kpiCriticosTerra').textContent = res.kpis.criticos_terra;

        renderizarMarcadoresNoMapa(TODOS_CLIENTES);
        renderizarListaSidebar(TODOS_CLIENTES);
      } catch (err) {
        console.error("Erro ao carregar clientes do mapa:", err);
      }
    }

    // Renderizar Marcadores no Mapa Leaflet
    function renderizarMarcadoresNoMapa(lista) {
      if (!MARKERS_LAYER) return;
      MARKERS_LAYER.clearLayers();

      lista.forEach(cli => {
        const icone = criarIconeColorido(cli.cor_marcador);
        const marker = L.marker([cli.lat, cli.lng], { icon: icone });

        // Popup com ações ricas
        const popupHtml = `
          <div class="popup-content">
            <h4>${cli.nome}</h4>
            <p><strong>Cidade:</strong> ${cli.cidade} - ${cli.estado} | <strong>Tipo:</strong> ${cli.tipo_contrato}</p>
            <p><strong>Aterramento:</strong> ${cli.status_infra_terra} (${cli.resistencia_terra_ohms ? cli.resistencia_terra_ohms + ' Ω' : 'Não aferido'})</p>
            <p><strong>Rede Trifásica:</strong> ${cli.rede_trifasica} ${cli.tensao_fases ? '(' + cli.tensao_fases + ')' : ''}</p>
            
            <div class="popup-actions">
              <a href="https://www.waze.com/ul?ll=${cli.lat},${cli.lng}&navigate=yes" target="_blank" class="popup-btn popup-btn-waze">🚗 Waze</a>
              <a href="https://www.google.com/maps/dir/?api=1&destination=${cli.lat},${cli.lng}" target="_blank" class="popup-btn" style="background:#4285F4; color:#fff;">📍 Google</a>
              <button onclick="abrirModalAfericao(${cli.id}, '${cli.nome.replace(/'/g, "\\'")}', '${cli.resistencia_terra_ohms || ''}', '${cli.rede_trifasica}', '${cli.tensao_fases}', '${cli.obs_infra}')" class="popup-btn popup-btn-aferir">⚡ Aferir Terra</button>
            </div>
          </div>
        `;
        marker.bindPopup(popupHtml);
        MARKERS_LAYER.addLayer(marker);
      });
    }

    // Renderizar Lista na Sidebar
    function renderizarListaSidebar(lista) {
      const box = document.getElementById('listaClientesSidebar');
      if (!lista.length) {
        box.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:0.85rem;">Nenhum cliente encontrado com os filtros selecionados.</div>`;
        return;
      }

      box.innerHTML = lista.map(c => `
        <div class="client-card" onclick="focarNoCliente(${c.lat}, ${c.lng})">
          <div class="client-card-title">
            <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:210px;">${c.nome}</span>
            <span class="badge ${c.tipo_contrato === 'CONTRATO' ? 'badge-contrato' : 'badge-avulso'}">${c.tipo_contrato}</span>
          </div>
          <div class="client-card-loc">📍 ${c.cidade} - ${c.estado}</div>
          <div class="client-card-infra">
            <span>⚡ Terra: <b style="color:${c.status_infra_terra === 'CRÍTICO' ? 'var(--red)' : (c.status_infra_terra === 'EXCELENTE' ? 'var(--green)' : 'var(--amber)')}">${c.status_infra_terra}</b></span>
            <span>Rede: <b>${c.rede_trifasica}</b></span>
          </div>
        </div>
      `).join('');
    }

    // Focar no Cliente no Mapa ao Clicar na Sidebar
    function focarNoCliente(lat, lng) {
      if (MAPA) {
        MAPA.flyTo([lat, lng], 14, { duration: 1.2 });
      }
    }

    // Filtro Local por Texto na Sidebar
    function filtrarClientesLocal() {
      const q = document.getElementById('filtroTexto').value.toLowerCase().trim();
      if (!q) {
        renderizarListaSidebar(TODOS_CLIENTES);
        return;
      }
      const filtrados = TODOS_CLIENTES.filter(c => 
        c.nome.toLowerCase().includes(q) || 
        c.cidade.toLowerCase().includes(q) || 
        c.estado.toLowerCase().includes(q)
      );
      renderizarListaSidebar(filtrados);
    }

    // Modal de Aferição Elétrica
    function abrirModalAfericao(id, nome, ohms, rede, tensao, obs) {
      document.getElementById('modalClienteId').value = id;
      document.getElementById('modalClienteNome').textContent = 'Aferir: ' + nome;
      document.getElementById('inpTerraOhms').value = ohms;
      document.getElementById('selRedeTrifasica').value = rede || 'ESTÁVEL';
      document.getElementById('inpTensaoFases').value = tensao;
      document.getElementById('inpObsInfra').value = obs;
      document.getElementById('modalAfericao').style.display = 'flex';
    }

    function fecharModalAfericao() {
      document.getElementById('modalAfericao').style.display = 'none';
    }

    async function salvarAfericaoEletrica() {
      const id = document.getElementById('modalClienteId').value;
      const ohms = document.getElementById('inpTerraOhms').value;
      const rede = document.getElementById('selRedeTrifasica').value;
      const tensao = document.getElementById('inpTensaoFases').value;
      const obs = document.getElementById('inpObsInfra').value;

      try {
        const res = await fetch('/api/mapa/registrar-afericao', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cliente_id: id,
            resistencia_terra_ohms: ohms,
            rede_trifasica_status: rede,
            tensao_fases_v: tensao,
            obs_infra_eletrica: obs
          })
        }).then(r => r.json());

        alert(res.msg || "Diagnóstico salvo com sucesso!");
        fecharModalAfericao();
        carregarClientesMapa();
      } catch (err) {
        alert("Erro ao gravar aferição.");
      }
    }

    // ==========================================
    // ABA TELEMETRIA TLF (PASSO 4)
    // ==========================================
    async function carregarTelemetriaTLF() {
      try {
        const res = await fetch('/api/telemetria/tlf/painel').then(r => r.json());
        if (!res.ok) return;

        const grid = document.getElementById('gridCardsTlf');
        grid.innerHTML = (res.equipamentos_monitorados || []).map(eq => {
          const cor = eq.status_alerta === 'CRÍTICO' ? 'var(--red)' : (eq.status_alerta === 'ATENÇÃO' ? 'var(--amber)' : 'var(--green)');
          return `
            <div class="card-tlf" style="border-top: 4px solid ${cor};">
              <div class="card-tlf-header">
                <div>
                  <h3 style="font-size:1rem; font-weight:700; color:#fff;">${eq.equipamento}</h3>
                  <div style="font-size:0.75rem; color:var(--text-muted);">${eq.cliente_nome}</div>
                </div>
                <span class="badge" style="background:${cor}22; color:${cor}; border:1px solid ${cor};">${eq.status_alerta}</span>
              </div>

              <div style="display:flex; justify-content:space-between; align-items:flex-end;">
                <div>
                  <div style="font-size:0.75rem; color:var(--text-muted);">Corrente de Fuga no Terra</div>
                  <div class="tlf-val-large" style="color:${cor};">${eq.corrente_fuga_ma} <span>mA</span></div>
                </div>
                <div style="text-align:right;">
                  <div style="font-size:0.75rem; color:var(--text-muted);">Temp. Anodo</div>
                  <div style="font-size:1.2rem; font-weight:800; color:#fff;">${eq.temperatura_anodo_c} ºC</div>
                </div>
              </div>

              <div style="background:rgba(0,0,0,0.25); border-radius:6px; padding:8px; font-size:0.75rem;">
                <div><strong>Scans do Tubo:</strong> ${eq.scans_acumulados.toLocaleString('pt-BR')} scans | <strong>Horímetro:</strong> ${eq.horimetro_horas} h</div>
                <div style="color:var(--text-muted); margin-top:4px;"><strong>Diagnóstico Preditivo:</strong> ${eq.mensagem_diagnostico}</div>
              </div>

              <div style="font-size:0.7rem; color:var(--text-muted); text-align:right;">Última leitura: ${eq.data_hora}</div>
            </div>
          `;
        }).join('');
      } catch (err) {
        console.error("Erro ao carregar telemetria:", err);
      }
    }

    async function simularTelemetriaTLF() {
      try {
        const res = await fetch('/api/telemetria/tlf/simular', { method: 'POST' }).then(r => r.json());
        alert(res.msg || "Telemetrias simuladas com sucesso!");
        carregarTelemetriaTLF();
      } catch (err) {
        alert("Erro ao simular telemetria.");
      }
    }

    // ==========================================
    // ABA DOSSIÊ RADIOLÓGICO RDC 611
    // ==========================================
    async function carregarDossieRDC() {
      try {
        const res = await fetch('/api/dossie/documentos').then(r => r.json());
        if (!res.ok) return;

        const tbody = document.getElementById('tabelaDossieCorpo');
        tbody.innerHTML = (res.documentos || []).map(d => `
          <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
            <td style="padding:10px; font-weight:600; color:#fff;">${d.cliente_nome}</td>
            <td style="padding:10px;">${d.equipamento}</td>
            <td style="padding:10px;"><strong style="color:var(--accent);">${d.titulo}</strong><br><small style="color:var(--text-muted);">${d.categoria}</small></td>
            <td style="padding:10px;">${d.orgao_emissor}<br><small style="color:var(--text-muted);">${d.responsavel_tecnico || ''}</small></td>
            <td style="padding:10px;">${d.data_emissao || '--'}</td>
            <td style="padding:10px; font-weight:700;">${d.data_validade || '--'}</td>
            <td style="padding:10px;">
              <span class="badge ${d.status_alerta === 'VENCIDO' ? 'badge-critico' : (d.status_alerta === 'VENCENDO' ? 'badge-atencao' : 'badge-contrato')}">
                ${d.status_alerta} (${d.dias_restantes !== null ? d.dias_restantes + ' dias' : 'OK'})
              </span>
            </td>
          </tr>
        `).join('');
      } catch (err) {
        console.error("Erro ao carregar dossiê:", err);
      }
    }

    // Navegação por Abas
    function alternarAba(aba) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-container').forEach(v => v.classList.remove('active'));
      document.getElementById('viewMapa').style.display = 'none';

      if (aba === 'mapa') {
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.getElementById('viewMapa').style.display = 'flex';
        setTimeout(() => { if (MAPA) MAPA.invalidateSize(); }, 200);
      } else if (aba === 'tlf') {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('viewTlf').classList.add('active');
        carregarTelemetriaTLF();
      } else if (aba === 'dossie') {
        document.querySelectorAll('.tab-btn')[2].classList.add('active');
        document.getElementById('viewDossie').classList.add('active');
        carregarDossieRDC();
      }
    }

    // Ao Carregar Página
    window.addEventListener('DOMContentLoaded', () => {
      inicializarMapa();
      carregarClientesMapa();
    });
  </script>
</body>
</html>
"""
    return web.Response(text=html, content_type="text/html", charset="utf-8")


def registrar_rotas_gestao_mapa_telemetria(app: web.Application) -> None:
    """Registra as rotas HTTP e endpoints do Mapa do Gestor, Telemetria TLF e Dossiê RDC 611."""
    app.router.add_get("/mapa-gestor", handle_pagina_gestao_mapa_telemetria)
    app.router.add_get("/gestao/mapa", handle_pagina_gestao_mapa_telemetria)
    app.router.add_get("/telemetria", handle_pagina_gestao_mapa_telemetria)
    app.router.add_get("/dossie-rdc", handle_pagina_gestao_mapa_telemetria)
    
    # APIs do Mapa & Infraestrutura
    app.router.add_get("/api/mapa/clientes-geolocalizados", api_mapa_clientes_geolocalizados)
    app.router.add_post("/api/mapa/registrar-afericao", api_mapa_registrar_afericao)

    # APIs da Telemetria TLF & Tubo de Raios-X
    app.router.add_post("/api/telemetria/tlf/coletar", api_telemetria_tlf_coletar)
    app.router.add_get("/api/telemetria/tlf/painel", api_telemetria_tlf_painel)
    app.router.add_post("/api/telemetria/tlf/simular", api_telemetria_tlf_simular)

    # APIs do Dossiê Radiológico RDC 611
    app.router.add_get("/api/dossie/documentos", api_dossie_documentos_listar)
    app.router.add_post("/api/dossie/documentos/salvar", api_dossie_documentos_salvar)

