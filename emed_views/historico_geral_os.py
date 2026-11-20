# -*- coding: utf-8 -*-
"""
Consulta Geral de Histórico de Ordens de Serviço — EMED Eletromedicina.
Unifica todas as Ordens de Serviço registradas no banco (histórico consolidado + OSs ativas)
em uma única interface de pesquisa, sem exibir nomes de sistemas anteriores.
"""
import sqlite3
from pathlib import Path
from aiohttp import web


def _get_conn(db_name: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_name, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt_data_ordenacao(dt_str: str) -> str:
    """Converte DD/MM/YYYY... ou YYYY-MM-DD... em chave ordenável YYYY-MM-DD HH:MM:SS."""
    s = (dt_str or "").strip()
    if not s:
        return "0000-00-00 00:00:00"
    # DD/MM/YYYY
    if len(s) >= 10 and s[2] == "/" and s[5] == "/":
        dd, mm, yyyy = s[0:2], s[3:5], s[6:10]
        resto = s[10:].strip()
        return f"{yyyy}-{mm}-{dd} {resto}".strip()
    return s


async def api_historico_geral_os(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    q = (request.query.get("q") or "").strip().lower()
    status_filtro = (request.query.get("status") or "TODOS").strip().upper()
    tecnico_filtro = (request.query.get("tecnico") or "").strip().lower()
    pagina = max(1, int(request.query.get("pagina") or 1))
    por_pagina = min(200, max(10, int(request.query.get("por_pagina") or 50)))

    itens = []
    with _get_conn(db_name) as conn:
        # 1. OSs Ativas / Recentes (clientes_equipamentos)
        try:
            rows_atuais = conn.execute("""
                SELECT id, cliente, cidade, estado, equipamento, tipo_servico,
                       tecnico_responsavel, tecnico_auxiliar, data_agendamento,
                       endereco, status, tempo_atendimento, defeito_relatado,
                       problemas_encontrados, servico_executado, observacoes_gerais,
                       pendencias, assinatura_cliente, cnpj, valor_os
                FROM clientes_equipamentos
            """).fetchall()
            for r in rows_atuais:
                dt = str(r["data_agendamento"] or "")[:19]
                end = str(r["endereco"] or "")
                if r["cidade"] and r["cidade"].lower() not in end.lower():
                    end = f"{end} - {r['cidade']}/{r['estado'] or ''}".strip(" -/")
                itens.append({
                    "uid": f"AT-{r['id']}",
                    "codigo_os": str(r["id"]),
                    "status": str(r["status"] or "ATIVO"),
                    "data_atendimento": dt,
                    "data_sort": _fmt_data_ordenacao(dt),
                    "data_finalizacao": "",
                    "cliente": str(r["cliente"] or ""),
                    "cpf_cnpj": str(r["cnpj"] or ""),
                    "endereco": end,
                    "equipamento": str(r["equipamento"] or ""),
                    "modelo": "",
                    "fabricante": "",
                    "numero_serie": "",
                    "tipo_servico": str(r["tipo_servico"] or ""),
                    "tecnico": str(r["tecnico_responsavel"] or ""),
                    "auxiliares": str(r["tecnico_auxiliar"] or ""),
                    "descricao": str(r["defeito_relatado"] or ""),
                    "servicos_executados": str(r["servico_executado"] or ""),
                    "problemas_encontrados": str(r["problemas_encontrados"] or ""),
                    "observacoes": str(r["observacoes_gerais"] or ""),
                    "pendencias": str(r["pendencias"] or ""),
                    "assinado_por": str(r["assinatura_cliente"] or ""),
                    "duracao": str(r["tempo_atendimento"] or ""),
                    "valor": float(r["valor_os"] or 0.0),
                    "link_documento": f"/api/imprimir/{r['id']}",
                    "link_anexos": "",
                })
        except Exception:
            pass

        # 2. Histórico Consolidado (historico_os_legado — sem expor origem_sistema)
        try:
            rows_hist = conn.execute("""
                SELECT id, codigo_os, status, data_abertura, data_atendimento, data_finalizacao,
                       cliente_nome, cliente_razao_social, cpf_cnpj, endereco,
                       equipamento, modelo, fabricante, numero_serie,
                       tipo_servico, ocorrencia, tecnico_responsavel, tecnicos_auxiliares,
                       descricao_trabalho, servicos_executados, problemas_encontrados,
                       observacoes, pendencias, assinado_por, duracao,
                       valor_servicos, receita_total, link_os_digital, link_anexos
                FROM historico_os_legado
            """).fetchall()
            for r in rows_hist:
                dt = str(r["data_atendimento"] or r["data_abertura"] or "")[:19]
                cli = str(r["cliente_nome"] or r["cliente_razao_social"] or "")
                eq = str(r["equipamento"] or "")
                if r["modelo"] and r["modelo"].lower() not in eq.lower():
                    eq = f"{eq} {r['modelo']}".strip()
                tserv = str(r["tipo_servico"] or r["ocorrencia"] or "")
                val = float(r["receita_total"] or r["valor_servicos"] or 0.0)
                itens.append({
                    "uid": f"HS-{r['id']}",
                    "codigo_os": str(r["codigo_os"] or r["id"]),
                    "status": str(r["status"] or "REGISTRADO"),
                    "data_atendimento": dt,
                    "data_sort": _fmt_data_ordenacao(dt),
                    "data_finalizacao": str(r["data_finalizacao"] or "")[:19],
                    "cliente": cli,
                    "cpf_cnpj": str(r["cpf_cnpj"] or ""),
                    "endereco": str(r["endereco"] or ""),
                    "equipamento": eq,
                    "modelo": str(r["modelo"] or ""),
                    "fabricante": str(r["fabricante"] or ""),
                    "numero_serie": str(r["numero_serie"] or ""),
                    "tipo_servico": tserv,
                    "tecnico": str(r["tecnico_responsavel"] or ""),
                    "auxiliares": str(r["tecnicos_auxiliares"] or ""),
                    "descricao": str(r["descricao_trabalho"] or ""),
                    "servicos_executados": str(r["servicos_executados"] or ""),
                    "problemas_encontrados": str(r["problemas_encontrados"] or ""),
                    "observacoes": str(r["observacoes"] or ""),
                    "pendencias": str(r["pendencias"] or ""),
                    "assinado_por": str(r["assinado_por"] or ""),
                    "duracao": str(r["duracao"] or ""),
                    "valor": val,
                    "link_documento": str(r["link_os_digital"] or ""),
                    "link_anexos": str(r["link_anexos"] or ""),
                })
        except Exception:
            pass

    # KPIs gerais
    total_geral = len(itens)
    clientes_unicos = len({i["cliente"].strip().upper() for i in itens if i["cliente"].strip()})
    equips_unicos = len({i["equipamento"].strip().upper() for i in itens if i["equipamento"].strip()})
    tecnicos_lista = sorted({i["tecnico"].strip() for i in itens if i["tecnico"].strip()})
    concluidas = sum(1 for i in itens if any(w in i["status"].upper() for w in ("CONCLU", "FINALIZ", "ENCERR", "FECHAD")))

    # Filtros
    filtrados = []
    for it in itens:
        if status_filtro == "CONCLUIDAS":
            if not any(w in it["status"].upper() for w in ("CONCLU", "FINALIZ", "ENCERR", "FECHAD")):
                continue
        elif status_filtro == "ABERTAS":
            if any(w in it["status"].upper() for w in ("CONCLU", "FINALIZ", "ENCERR", "FECHAD")):
                continue
        if tecnico_filtro and tecnico_filtro not in it["tecnico"].lower() and tecnico_filtro not in it["auxiliares"].lower():
            continue
        if q:
            hay = " ".join([
                it["codigo_os"], it["cliente"], it["cpf_cnpj"], it["equipamento"],
                it["numero_serie"], it["tipo_servico"], it["tecnico"], it["auxiliares"],
                it["descricao"], it["servicos_executados"], it["problemas_encontrados"],
                it["observacoes"], it["endereco"]
            ]).lower()
            if q not in hay:
                continue
        filtrados.append(it)

    filtrados.sort(key=lambda x: x["data_sort"], reverse=True)
    total_filtrado = len(filtrados)
    inicio = (pagina - 1) * por_pagina
    paginados = filtrados[inicio:inicio + por_pagina]

    return web.json_response({
        "ok": True,
        "kpis": {
            "total_geral": total_geral,
            "total_filtrado": total_filtrado,
            "clientes_unicos": clientes_unicos,
            "equips_unicos": equips_unicos,
            "concluidas": concluidas,
        },
        "tecnicos": tecnicos_lista,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": max(1, (total_filtrado + por_pagina - 1) // por_pagina),
        "itens": paginados,
    })


async def handle_pagina_historico_geral_os(request: web.Request) -> web.Response:
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Consulta Geral de Histórico de OS — EMED</title>
  <style>
    :root {
      --bg: #0b132b; --card: #131f3a; --border: #243456;
      --cyan: #38bdf8; --green: #34d399; --amber: #fbbf24; --text: #f1f5f9; --muted: #94a3b8;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: 'Segoe UI', Roboto, Arial, sans-serif; background: var(--bg); color: var(--text); }
    .wrap { max-width: 1420px; margin: 0 auto; padding: 18px; }
    .topbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 14px 18px; margin-bottom: 16px; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .kpi { background: var(--card); border: 1px solid var(--border); border-top: 3px solid var(--cyan); border-radius: 10px; padding: 14px; }
    .kpi .lbl { font-size: 11px; color: var(--muted); font-weight: 800; text-transform: uppercase; }
    .kpi .val { font-size: 26px; font-weight: 900; margin-top: 4px; color: var(--cyan); }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    .filters { display: grid; grid-template-columns: 2.2fr 1fr 1fr auto auto; gap: 10px; align-items: end; }
    @media (max-width: 900px) { .filters { grid-template-columns: 1fr; } }
    label { display: block; font-size: 11.5px; color: var(--muted); margin-bottom: 4px; font-weight: 700; }
    input, select { width: 100%; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; padding: 9px 11px; font-size: 13px; }
    .btn { border: none; border-radius: 8px; padding: 9px 15px; font-weight: 800; cursor: pointer; font-size: 12.5px; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; }
    .btn-primary { background: var(--cyan); color: #0b132b; }
    .btn-outline { background: transparent; color: #e2e8f0; border: 1px solid #475569; }
    .btn-green { background: #10b981; color: #0b132b; }
    table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
    th { text-align: left; padding: 10px 8px; background: #0f172a; color: var(--cyan); border-bottom: 1px solid #334155; position: sticky; top: 0; }
    td { padding: 9px 8px; border-bottom: 1px solid #1e293b; vertical-align: top; }
    tr:hover td { background: rgba(56, 189, 248, 0.06); }
    .badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 11px; font-weight: 800; background: #1e293b; color: #e2e8f0; border: 1px solid #334155; }
    .badge-ok { background: rgba(16,185,129,0.16); color: #34d399; border-color: #10b981; }
    .badge-warn { background: rgba(245,158,11,0.16); color: #fbbf24; border-color: #f59e0b; }
    .pager { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; flex-wrap: wrap; gap: 10px; }
    .modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.78); backdrop-filter: blur(4px); z-index: 9999; align-items: center; justify-content: center; padding: 16px; }
    .modal { background: #0f172a; border: 1.5px solid var(--cyan); border-radius: 14px; max-width: 820px; width: 100%; max-height: 90vh; overflow-y: auto; padding: 22px; }
    .detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin-bottom: 14px; }
    .detail-box { background: #131f3a; border: 1px solid #243456; border-radius: 8px; padding: 10px; }
    .detail-box .k { font-size: 10.5px; color: var(--muted); text-transform: uppercase; font-weight: 800; }
    .detail-box .v { font-size: 13px; color: #f8fafc; margin-top: 3px; white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h2 style="margin:0;color:var(--cyan);font-size:20px;">🔎 Consulta Geral de Histórico de Ordens de Serviço</h2>
        <div style="font-size:12.5px;color:var(--muted);margin-top:3px;">Base unificada de atendimentos técnicos, preventivas, corretivas, diagnósticos e relatos técnicos da EMED.</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a href="/fiscal" class="btn btn-outline">🧾 Portal Fiscal</a>
        <a href="/" class="btn btn-outline">🏠 Sistema Principal</a>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="lbl">Total de OSs no Histórico</div><div class="val" id="kpiTotal">0</div></div>
      <div class="kpi" style="border-top-color:#34d399;"><div class="lbl">OSs Concluídas / Finalizadas</div><div class="val" style="color:#34d399;" id="kpiConcluidas">0</div></div>
      <div class="kpi" style="border-top-color:#fbbf24;"><div class="lbl">Clientes Atendidos</div><div class="val" style="color:#fbbf24;" id="kpiClientes">0</div></div>
      <div class="kpi" style="border-top-color:#a78bfa;"><div class="lbl">Equipamentos no Histórico</div><div class="val" style="color:#a78bfa;" id="kpiEquips">0</div></div>
    </div>

    <div class="card">
      <div class="filters">
        <div>
          <label>Pesquisa Geral (Cliente, Equipamento, Nº OS, Técnico, CNPJ ou Relato Técnico):</label>
          <input id="inpBusca" placeholder="Ex: hospital, tomografo, tubo, placa, preventiva, netto..." onkeydown="if(event.key==='Enter') buscar(1)" />
        </div>
        <div>
          <label>Status:</label>
          <select id="selStatus" onchange="buscar(1)">
            <option value="TODOS">Todos os Status</option>
            <option value="CONCLUIDAS">Concluídas / Finalizadas</option>
            <option value="ABERTAS">Abertas / Em Andamento</option>
          </select>
        </div>
        <div>
          <label>Técnico Responsável:</label>
          <select id="selTecnico" onchange="buscar(1)">
            <option value="">Todos os Técnicos</option>
          </select>
        </div>
        <button class="btn btn-primary" onclick="buscar(1)">🔍 Pesquisar</button>
        <button class="btn btn-green" onclick="exportarCsv()">📥 CSV</button>
      </div>
    </div>

    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
        <div id="lblResultado" style="font-size:13px;color:var(--muted);font-weight:700;">Carregando histórico...</div>
      </div>
      <div style="overflow-x:auto;max-height:62vh;overflow-y:auto;">
        <table>
          <thead>
            <tr>
              <th style="width:95px;">Nº OS</th>
              <th style="width:130px;">Data</th>
              <th style="min-width:210px;">Cliente</th>
              <th style="min-width:190px;">Equipamento</th>
              <th style="width:140px;">Tipo de Serviço</th>
              <th style="width:130px;">Técnico</th>
              <th style="width:115px;">Status</th>
              <th style="min-width:220px;">Resumo / Relato Técnico</th>
              <th style="width:85px;text-align:center;">Detalhes</th>
            </tr>
          </thead>
          <tbody id="tbodyHist"></tbody>
        </table>
      </div>
      <div class="pager">
        <div id="lblPaginacao" style="font-size:12.5px;color:var(--muted);"></div>
        <div style="display:flex;gap:8px;">
          <button class="btn btn-outline" id="btnPrev" onclick="mudarPagina(-1)">⬅️ Anterior</button>
          <button class="btn btn-outline" id="btnNext" onclick="mudarPagina(1)">Próxima ➡️</button>
        </div>
      </div>
    </div>
  </div>

  <!-- MODAL DETALHES DA OS -->
  <div class="modal-bg" id="modalDetalhe" onclick="if(event.target===this) fecharModal()">
    <div class="modal">
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:10px;margin-bottom:14px;">
        <h3 id="mdTitulo" style="margin:0;color:var(--cyan);">Detalhes da Ordem de Serviço</h3>
        <button class="btn btn-outline" style="padding:5px 10px;" onclick="fecharModal()">✕ Fechar</button>
      </div>
      <div id="mdCorpo"></div>
    </div>
  </div>

  <script>
    let PAGINA_ATUAL = 1;
    let TOTAL_PAGINAS = 1;
    let ULTIMOS_ITENS = [];
    let TECNICOS_CARREGADOS = false;

    function esc(v) {
      return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    async function buscar(pag) {
      PAGINA_ATUAL = pag || 1;
      const q = document.getElementById("inpBusca").value.trim();
      const st = document.getElementById("selStatus").value;
      const tec = document.getElementById("selTecnico").value;
      const url = `/api/historico-geral-os?q=${encodeURIComponent(q)}&status=${encodeURIComponent(st)}&tecnico=${encodeURIComponent(tec)}&pagina=${PAGINA_ATUAL}&por_pagina=50`;
      const res = await fetch(url);
      const data = await res.json();
      if (!data.ok) return;

      document.getElementById("kpiTotal").textContent = (data.kpis.total_geral || 0).toLocaleString("pt-BR");
      document.getElementById("kpiConcluidas").textContent = (data.kpis.concluidas || 0).toLocaleString("pt-BR");
      document.getElementById("kpiClientes").textContent = (data.kpis.clientes_unicos || 0).toLocaleString("pt-BR");
      document.getElementById("kpiEquips").textContent = (data.kpis.equips_unicos || 0).toLocaleString("pt-BR");

      if (!TECNICOS_CARREGADOS && Array.isArray(data.tecnicos)) {
        TECNICOS_CARREGADOS = true;
        const sel = document.getElementById("selTecnico");
        sel.innerHTML = '<option value="">Todos os Técnicos</option>' + data.tecnicos.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
      }

      ULTIMOS_ITENS = data.itens || [];
      TOTAL_PAGINAS = data.total_paginas || 1;
      document.getElementById("lblResultado").textContent = `Exibindo ${ULTIMOS_ITENS.length} de ${(data.kpis.total_filtrado || 0).toLocaleString("pt-BR")} OSs encontradas`;
      document.getElementById("lblPaginacao").textContent = `Página ${PAGINA_ATUAL} de ${TOTAL_PAGINAS}`;
      document.getElementById("btnPrev").disabled = PAGINA_ATUAL <= 1;
      document.getElementById("btnNext").disabled = PAGINA_ATUAL >= TOTAL_PAGINAS;

      const tbody = document.getElementById("tbodyHist");
      if (!ULTIMOS_ITENS.length) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#94a3b8;padding:24px;">Nenhuma Ordem de Serviço encontrada para os filtros informados.</td></tr>';
        return;
      }

      tbody.innerHTML = ULTIMOS_ITENS.map((it, idx) => {
        const isOk = /CONCLU|FINALIZ|ENCERR|FECHAD/i.test(it.status || "");
        const resumo = (it.servicos_executados || it.descricao || it.observacoes || "-").slice(0, 120);
        return `
          <tr>
            <td style="font-weight:900;color:var(--cyan);">#${esc(it.codigo_os)}</td>
            <td style="font-size:12px;color:#cbd5e1;">${esc(it.data_atendimento || "-")}</td>
            <td style="font-weight:700;">${esc(it.cliente || "-")}</td>
            <td style="font-size:12px;">${esc(it.equipamento || "-")}</td>
            <td style="font-size:11.5px;color:#cbd5e1;">${esc(it.tipo_servico || "-")}</td>
            <td style="font-size:12px;">${esc(it.tecnico || "-")}</td>
            <td><span class="badge ${isOk ? 'badge-ok' : 'badge-warn'}">${esc(it.status || "-")}</span></td>
            <td style="font-size:11.5px;color:#cbd5e1;">${esc(resumo)}${(it.servicos_executados || it.descricao || "").length > 120 ? "..." : ""}</td>
            <td style="text-align:center;">
              <button class="btn btn-primary" style="padding:5px 10px;font-size:11.5px;" onclick="abrirModal(${idx})">Ver</button>
            </td>
          </tr>
        `;
      }).join("");
    }

    function mudarPagina(delta) {
      const nova = PAGINA_ATUAL + delta;
      if (nova >= 1 && nova <= TOTAL_PAGINAS) buscar(nova);
    }

    function abrirModal(idx) {
      const it = ULTIMOS_ITENS[idx];
      if (!it) return;
      document.getElementById("mdTitulo").textContent = `Ordem de Serviço #${it.codigo_os} — ${it.cliente}`;
      let linksHtml = "";
      if (it.link_documento) {
        linksHtml += `<a href="${esc(it.link_documento)}" target="_blank" class="btn btn-primary" style="margin-right:8px;">📄 Abrir Documento da OS</a>`;
      }
      if (it.link_anexos) {
        linksHtml += `<a href="${esc(it.link_anexos)}" target="_blank" class="btn btn-outline">📎 Abrir Anexos / Fotos</a>`;
      }

      document.getElementById("mdCorpo").innerHTML = `
        <div class="detail-grid">
          <div class="detail-box"><div class="k">Cliente</div><div class="v">${esc(it.cliente || "-")}</div></div>
          <div class="detail-box"><div class="k">CPF / CNPJ</div><div class="v">${esc(it.cpf_cnpj || "-")}</div></div>
          <div class="detail-box"><div class="k">Data de Atendimento</div><div class="v">${esc(it.data_atendimento || "-")}</div></div>
          <div class="detail-box"><div class="k">Status</div><div class="v">${esc(it.status || "-")}</div></div>
          <div class="detail-box"><div class="k">Equipamento</div><div class="v">${esc(it.equipamento || "-")} ${it.numero_serie ? '(Série: ' + esc(it.numero_serie) + ')' : ''}</div></div>
          <div class="detail-box"><div class="k">Tipo de Serviço</div><div class="v">${esc(it.tipo_servico || "-")}</div></div>
          <div class="detail-box"><div class="k">Técnico Responsável</div><div class="v">${esc(it.tecnico || "-")}</div></div>
          <div class="detail-box"><div class="k">Auxiliares / Duração</div><div class="v">${esc(it.auxiliares || "-")} ${it.duracao ? ' • ' + esc(it.duracao) : ''}</div></div>
        </div>
        <div class="detail-box" style="margin-bottom:10px;"><div class="k">Endereço</div><div class="v">${esc(it.endereco || "-")}</div></div>
        <div class="detail-box" style="margin-bottom:10px;"><div class="k">Descrição / Solicitação</div><div class="v">${esc(it.descricao || "-")}</div></div>
        <div class="detail-box" style="margin-bottom:10px;"><div class="k">Serviços Executados / Relato Técnico</div><div class="v">${esc(it.servicos_executados || "-")}</div></div>
        ${it.problemas_encontrados ? `<div class="detail-box" style="margin-bottom:10px;"><div class="k">Problemas Encontrados</div><div class="v">${esc(it.problemas_encontrados)}</div></div>` : ""}
        ${it.observacoes ? `<div class="detail-box" style="margin-bottom:10px;"><div class="k">Observações</div><div class="v">${esc(it.observacoes)}</div></div>` : ""}
        ${it.pendencias ? `<div class="detail-box" style="margin-bottom:10px;"><div class="k">Pendências</div><div class="v">${esc(it.pendencias)}</div></div>` : ""}
        ${it.assinado_por ? `<div class="detail-box" style="margin-bottom:10px;"><div class="k">Assinado Por</div><div class="v">${esc(it.assinado_por)}</div></div>` : ""}
        ${linksHtml ? `<div style="margin-top:14px;">${linksHtml}</div>` : ""}
      `;
      document.getElementById("modalDetalhe").style.display = "flex";
    }

    function fecharModal() {
      document.getElementById("modalDetalhe").style.display = "none";
    }

    function exportarCsv() {
      if (!ULTIMOS_ITENS.length) return;
      const head = ["Numero_OS", "Data", "Cliente", "CNPJ", "Equipamento", "Tipo_Servico", "Tecnico", "Status", "Relato_Servicos"];
      const rows = [head.join(";")].concat(ULTIMOS_ITENS.map(i => [
        i.codigo_os, i.data_atendimento, i.cliente, i.cpf_cnpj, i.equipamento, i.tipo_servico, i.tecnico, i.status,
        (i.servicos_executados || i.descricao || "").replace(/[\r\n;]+/g, " ")
      ].join(";")));
      const blob = new Blob(["\uFEFF" + rows.join("\n")], { type: "text/csv;charset=utf-8;" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "historico_geral_os_emed.csv";
      a.click();
    }

    buscar(1);
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


def registrar_rotas_historico_geral_os(app: web.Application) -> None:
    app.router.add_get("/historico-os", handle_pagina_historico_geral_os)
    app.router.add_get("/api/historico-geral-os", api_historico_geral_os)
