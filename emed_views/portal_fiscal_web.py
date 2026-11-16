# -*- coding: utf-8 -*-
"""
Portal Fiscal Web Nativo (Alta Disponibilidade 24/7) — EMED Eletromedicina.
Roda diretamente integrado ao servidor principal em https://emedservice.med.br/fiscal
(e também responde automaticamente caso o domínio fiscal.emedservice.med.br aponte para cá),
eliminando qualquer risco de suspensão de container secundário no Render.
"""

import os
import json
import time
import uuid
import base64
from pathlib import Path
from aiohttp import web

from emed_fiscal import (
    FiscalManager,
    CertificadoManager,
    _get_db_connection,
    _registrar_log_fiscal,
)

USUARIOS_FISCAL = {
    "netto": {"senha": "12345", "role": "admin", "cargo": "Diretoria & Controladoria"},
    "vitor": {"senha": "12345", "role": "admin", "cargo": "Diretoria & Gestão Geral"},
    "faturamento": {"senha": "123", "role": "faturamento", "cargo": "Faturamento & Emissão Fiscal"},
    "financeiro": {"senha": "123", "role": "financeiro", "cargo": "Financeiro & Contabilidade"},
}


def _obter_icone_azul_b64() -> str:
    p = Path(__file__).resolve().parent.parent / "assets" / "icone_fiscal_azul.png"
    if p.is_file():
        return base64.b64encode(p.read_bytes()).decode("ascii")
    return ""


def _obter_logo_b64() -> str:
    root = Path(__file__).resolve().parent.parent
    for c in [root / "assets" / "emed_logo_user_dark.png", root / "emed_logo_user_dark.png", root / "emed_logo_oficial.png"]:
        if c.is_file():
            return base64.b64encode(c.read_bytes()).decode("ascii")
    return ""


async def api_fiscal_v2_login(request: web.Request) -> web.Response:
    body = await request.json()
    u = str(body.get("username", "")).strip().lower()
    p = str(body.get("password", "")).strip()
    token_qr = str(body.get("token", "")).strip()

    if token_qr:
        try:
            raw = base64.urlsafe_b64decode(token_qr.encode("ascii")).decode("utf-8")
            data = json.loads(raw)
            usr = str(data.get("username", "")).strip().lower()
            is_perm = bool(data.get("perm"))
            ts = float(data.get("ts", 0))
            ttl = float(data.get("ttl", 1800))
            if (is_perm or (time.time() - ts <= ttl)) and usr in USUARIOS_FISCAL:
                info = USUARIOS_FISCAL[usr]
                return web.json_response({
                    "ok": True,
                    "username": usr,
                    "role": info["role"],
                    "cargo": info["cargo"],
                })
        except Exception as e:
            return web.json_response({"ok": False, "msg": f"Token QR inválido: {e}"}, status=400)

    if u in USUARIOS_FISCAL and USUARIOS_FISCAL[u]["senha"] == p:
        info = USUARIOS_FISCAL[u]
        return web.json_response({
            "ok": True,
            "username": u,
            "role": info["role"],
            "cargo": info["cargo"],
        })
    return web.json_response({"ok": False, "msg": "Usuário ou senha inválidos."}, status=401)


async def api_fiscal_v2_dados(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    filial = request.query.get("filial", "FILIAL_DF").upper()
    os_id_param = request.query.get("os_id", "")

    manager = FiscalManager(db_name)
    cfg_df = manager.get_filial_config("FILIAL_DF")
    cfg_ce = manager.get_filial_config("MATRIZ_CE")
    cfg_ativa = cfg_df if filial == "FILIAL_DF" else cfg_ce
    cod_cert = filial if filial != "CONSOLIDADO" else "FILIAL_DF"
    st_cert = CertificadoManager.status_certificado(cod_cert, db_name)

    where_os = "WHERE UPPER(c.status) LIKE '%CONCLU%'"
    if filial == "FILIAL_DF":
        where_os += " AND (UPPER(TRIM(COALESCE(c.estado, ''))) = 'DF' OR UPPER(COALESCE(c.cidade, '')) LIKE '%BRASIL%' OR n.filial_emissora = 'FILIAL_DF')"
    elif filial == "MATRIZ_CE":
        where_os += " AND ((UPPER(TRIM(COALESCE(c.estado, 'CE'))) != 'DF' AND UPPER(COALESCE(c.cidade, '')) NOT LIKE '%BRASIL%') OR n.filial_emissora = 'MATRIZ_CE')"

    sql_os = f"""
        SELECT c.id, c.cliente, c.cidade, c.estado, c.equipamento, c.valor_os,
               c.peca_baixada_ref, n.status_fiscal, n.numero_nf, n.valor_liquido
        FROM clientes_equipamentos c
        LEFT JOIN notas_fiscais n ON c.id = n.os_id
        {where_os}
        ORDER BY c.id DESC
    """
    with _get_db_connection(db_name) as conn:
        rows_os = conn.execute(sql_os).fetchall()

        filtro_sql = ""
        params_tot = []
        if filial != "CONSOLIDADO":
            filtro_sql = "WHERE filial_emissora = ?"
            params_tot.append(filial)

        cur_tot = conn.execute(f"""
            SELECT 
                COUNT(*) as total_nf,
                SUM(CASE WHEN (UPPER(status_fiscal) LIKE '%AUTORIZ%' OR UPPER(status_fiscal) LIKE '%EMITID%' OR UPPER(status_fiscal) LIKE '%LIQUIDAD%') AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%' THEN 1 ELSE 0 END) as emitidas,
                SUM(CASE WHEN (UPPER(status_fiscal) LIKE '%AUTORIZ%' OR UPPER(status_fiscal) LIKE '%EMITID%' OR UPPER(status_fiscal) LIKE '%LIQUIDAD%') AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%' THEN COALESCE(valor_liquido, 0) ELSE 0 END) as total_faturar
            FROM notas_fiscais {filtro_sql}
        """, tuple(params_tot)).fetchone()

        sql_h = """
            SELECT id, os_id, numero_nf, serie, cliente, valor_liquido,
                   data_emissao, status_fiscal, chave_acesso, filial_emissora, tipo_nota, cfop
            FROM notas_fiscais
            WHERE numero_nf IS NOT NULL AND numero_nf != ''
        """
        params_h = []
        if filial != "CONSOLIDADO":
            sql_h += " AND filial_emissora = ?"
            params_h.append(filial)
        sql_h += " ORDER BY id DESC LIMIT 30"
        rows_hist = conn.execute(sql_h, tuple(params_h)).fetchall()

    total_nf, emitidas, total_faturar = cur_tot if cur_tot else (0, 0, 0.0)
    pendentes_fila = sum(1 for r in rows_os if not r[8] or "CANCELAD" in str(r[7] or "").upper())

    fila_os = []
    for r in rows_os:
        fila_os.append({
            "id": r[0],
            "cliente": r[1] or "",
            "cidade": r[2] or "",
            "estado": r[3] or "",
            "equipamento": r[4] or "",
            "valor_os": float(r[5] or 0.0),
            "peca": r[6] or "Nenhuma",
            "status_fiscal": r[7] or "AGUARDANDO EMISSÃO",
            "numero_nf": r[8] or "",
            "valor_liquido": float(r[9] or r[5] or 0.0),
        })

    os_id_alvo = int(os_id_param) if os_id_param.isdigit() else (fila_os[0]["id"] if fila_os else None)
    dados_os_sel = None
    if os_id_alvo is not None:
        try:
            dados_os_sel = manager.fetch_os_complete_data(os_id_alvo, cod_cert)
        except Exception:
            if fila_os:
                try:
                    dados_os_sel = manager.fetch_os_complete_data(fila_os[0]["id"], cod_cert)
                except Exception:
                    pass

    historico = []
    for rh in rows_hist:
        historico.append({
            "id": rh[0],
            "os_id": rh[1],
            "numero_nf": rh[2],
            "serie": rh[3],
            "cliente": rh[4],
            "valor_liquido": float(rh[5] or 0.0),
            "data_emissao": str(rh[6] or "")[:16],
            "status_fiscal": rh[7] or "",
            "chave_acesso": rh[8] or "",
            "filial": "DF" if rh[9] == "FILIAL_DF" else "CE",
            "tipo_nota": rh[10] or "NFS-e",
            "cfop": rh[11] or "",
        })

    return web.json_response({
        "ok": True,
        "filial": filial,
        "cfg_ativa": cfg_ativa,
        "certificado": st_cert,
        "kpis": {
            "pendentes": pendentes_fila,
            "emitidas": int(emitidas or 0),
            "total_faturar": float(total_faturar or 0.0),
        },
        "fila_os": fila_os,
        "os_selecionada": dados_os_sel,
        "historico": historico,
    })


async def api_fiscal_v2_salvar_config(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    filial = str(body.get("filial", "FILIAL_DF")).upper()
    if filial == "CONSOLIDADO":
        filial = "FILIAL_DF"

    manager = FiscalManager(db_name)
    cfg = manager.get_filial_config(filial)
    cfg.update({
        "cnpj": str(body.get("cnpj", cfg.get("cnpj", ""))).strip(),
        "inscricao_municipal": str(body.get("inscricao_municipal", cfg.get("inscricao_municipal", ""))).strip(),
        "razao_social": str(body.get("razao_social", cfg.get("razao_social", ""))).strip(),
        "endereco": str(body.get("endereco", cfg.get("endereco", ""))).strip(),
        "serie_padrao": str(body.get("serie_padrao", cfg.get("serie_padrao", "1"))).strip(),
        "aliquota_iss_padrao": float(body.get("aliquota_iss_padrao", cfg.get("aliquota_iss_padrao", 5.0))),
        "telefone": str(body.get("telefone", cfg.get("telefone", ""))).strip(),
        "email": str(body.get("email", cfg.get("email", ""))).strip(),
    })
    manager.save_filial_config(filial, cfg)

    msg_cert = ""
    cert_b64 = body.get("cert_b64")
    senha_cert = str(body.get("senha_cert", "")).strip()
    replicar = bool(body.get("replicar_todas", True))
    if cert_b64 and senha_cert:
        raw_bytes = base64.b64decode(cert_b64)
        ok_c, msg_c = CertificadoManager.salvar_certificado(filial, raw_bytes, senha_cert, db_name, replicar_todas=replicar)
        msg_cert = " | " + msg_c

    _registrar_log_fiscal("CONFIG_FILIAL", f"Parâmetros salvos para {filial} (ISS: {cfg['aliquota_iss_padrao']}%){msg_cert}", str(body.get("usuario", "netto")))
    return web.json_response({"ok": True, "msg": f"✅ Parâmetros de {cfg.get('nome')} salvos com sucesso!{msg_cert}"})


async def api_fiscal_v2_emitir(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    os_id = int(body.get("os_id"))
    filial = str(body.get("filial_emissora", "FILIAL_DF")).upper()
    if filial == "CONSOLIDADO":
        filial = "FILIAL_DF"

    tipo_op = str(body.get("tipo_nota", "🛠️ PRESTAÇÃO DE SERVIÇOS & PEÇAS (FATURAMENTO DE MANUTENÇÃO)"))
    uf_tom = str(body.get("tomador_uf", "DF")).strip().upper()
    nat_op = "TRIBUTAÇÃO NO MUNICÍPIO / DF"
    cfop = ""
    if "DIAGNÓSTICO" in tipo_op:
        nat_op = "PRESTAÇÃO DE SERVIÇO DE DIAGNÓSTICO TÉCNICO"
    elif "DEVOLUÇÃO" in tipo_op:
        nat_op = "RETORNO DE MERCADORIA/BEM RECEBIDO PARA CONSERTO"
        cfop = "5916" if uf_tom in ("DF", "CE") else "6916"
    elif "REMESSA" in tipo_op:
        nat_op = "REMESSA DE BEM PARA CONSERTO/REPARO"
        cfop = "5915" if uf_tom in ("DF", "CE") else "6915"

    payload_salvar = {
        "cliente": str(body.get("cliente", "")).strip(),
        "cnpj_tomador": str(body.get("cnpj_tomador", "")).strip(),
        "tomador_endereco": str(body.get("tomador_endereco", "")).strip(),
        "tomador_cidade": str(body.get("tomador_cidade", "")).strip(),
        "tomador_uf": uf_tom,
        "email_cliente": str(body.get("email_cliente", "")).strip(),
        "tipo_nota": tipo_op,
        "natureza_operacao": nat_op,
        "cfop": cfop,
        "discriminacao_servico": str(body.get("discriminacao_servico", "")).strip(),
        "valor_servicos": float(body.get("valor_servicos") or 0.0),
        "valor_pecas": float(body.get("valor_pecas") or 0.0),
        "valor_desconto": float(body.get("valor_desconto") or 0.0),
        "aliquota_iss": float(body.get("aliquota_iss") or 0.0),
        "filial_emissora": filial,
        "usuario_operador": str(body.get("usuario", "netto")),
    }

    manager = FiscalManager(db_name)
    res_nota = manager.emitir_nota(os_id, filial, payload_salvar)
    danfe_html = ""
    hp = res_nota.get("html_path")
    if hp and os.path.exists(hp):
        danfe_html = Path(hp).read_text(encoding="utf-8")

    return web.json_response({
        "ok": True,
        "nota": res_nota,
        "danfe_html": danfe_html,
    })


async def api_fiscal_v2_cancelar(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    id_nf = int(body.get("id"))
    justificativa = str(body.get("justificativa", "")).strip()
    usuario = str(body.get("usuario", "netto")).strip()

    if len(justificativa) < 8:
        return web.json_response({"ok": False, "msg": "Informe uma justificativa legal com no mínimo 8 caracteres."}, status=400)

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT numero_nf FROM notas_fiscais WHERE id = ?", (id_nf,)).fetchone()
        num_nf = row[0] if row else f"#{id_nf}"
        conn.execute("""
            UPDATE notas_fiscais
            SET status_fiscal = 'CANCELADA',
                atualizado_em = datetime('now'),
                discriminacao_servico = COALESCE(discriminacao_servico, '') || '\n\n[CANCELADA: ' || ? || ']'
            WHERE id = ?
        """, (justificativa, id_nf))
        conn.commit()

    _registrar_log_fiscal("CANCELAMENTO_NF", f"NF {num_nf} (ID #{id_nf}) cancelada | Motivo: {justificativa}", usuario)
    return web.json_response({"ok": True, "msg": f"✅ Nota Fiscal {num_nf} cancelada com sucesso!"})


async def api_fiscal_v2_criar_os_teste(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    manager = FiscalManager(db_name)
    nova_id = manager.criar_os_teste_brasilia()
    return web.json_response({"ok": True, "os_id": nova_id, "msg": f"✅ OS #{nova_id} de Brasília (Hospital Santa Lúcia) criada para teste!"})


async def api_fiscal_v2_xml_download(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    os_id = request.match_info.get("os_id", "0")
    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT xml_path, numero_nf FROM notas_fiscais WHERE os_id = ?", (os_id,)).fetchone()
    if row and row[0] and os.path.exists(row[0]):
        num = row[1] or f"OS_{os_id}"
        return web.Response(
            body=Path(row[0]).read_bytes(),
            content_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="NFS_{num}.xml"'},
        )
    return web.Response(text="Arquivo XML não encontrado para esta OS.", status=404)


async def handle_pagina_fiscal_nativa(request: web.Request) -> web.Response:
    icon_b64 = _obter_icone_azul_b64()
    logo_b64 = _obter_logo_b64()
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EMED Fiscal – Faturamento & NFS-e Multi-Filial</title>
  <link rel="icon" type="image/png" href="data:image/png;base64,{icon_b64}">
  <style>
    :root {{
      --bg: #0b132b;
      --card: #1c2541;
      --border: #334155;
      --cyan: #64dfdf;
      --blue: #0284c7;
      --text: #f8fafc;
      --muted: #94a3b8;
    }}
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); min-height: 100vh; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    .header-bar {{ display: flex; justify-content: space-between; align-items: center; background: rgba(30,41,59,0.85); border: 1px solid var(--border); padding: 12px 18px; border-radius: 12px; margin-bottom: 18px; flex-wrap: wrap; gap: 10px; }}
    .badge {{ background: var(--blue); color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
    .card-highlight {{ border: 1.5px solid var(--cyan); }}
    .grid-3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    label {{ display: block; font-size: 11.5px; color: #cbd5e1; font-weight: 700; margin-bottom: 4px; }}
    input, select, textarea {{ width: 100%; background: #0f172a; color: #fff; border: 1px solid #475569; border-radius: 6px; padding: 9px 11px; font-size: 13px; }}
    input:focus, select:focus, textarea:focus {{ outline: none; border-color: var(--cyan); }}
    .btn {{ cursor: pointer; border: none; border-radius: 6px; padding: 10px 16px; font-weight: 800; font-size: 13px; transition: 0.15s; display: inline-flex; align-items: center; justify-content: center; gap: 6px; text-decoration: none; }}
    .btn-primary {{ background: var(--cyan); color: #0b132b; width: 100%; }}
    .btn-primary:hover {{ filter: brightness(1.08); }}
    .btn-blue {{ background: var(--blue); color: #fff; }}
    .btn-danger {{ background: #dc2626; color: #fff; }}
    .btn-outline {{ background: transparent; border: 1px solid #475569; color: #e2e8f0; }}
    .radio-bar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }}
    .radio-pill {{ background: #0f172a; border: 1.5px solid #334155; color: #cbd5e1; padding: 8px 14px; border-radius: 8px; cursor: pointer; font-weight: 700; font-size: 13px; }}
    .radio-pill.active {{ border-color: var(--cyan); background: #1e293b; color: var(--cyan); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
    th, td {{ border-bottom: 1px solid #334155; padding: 8px 10px; text-align: left; }}
    th {{ background: #0f172a; color: var(--cyan); font-weight: 800; }}
    .kpi-num {{ font-size: 26px; font-weight: 900; color: var(--cyan); margin-top: 4px; }}
    #loginBox {{ max-width: 440px; margin: 60px auto; }}
  </style>
</head>
<body>
  <div class="wrap">
    <!-- TELA DE LOGIN -->
    <div id="loginBox" class="card card-highlight" style="display:none;">
      <div style="text-align:center; margin-bottom:18px;">
        {f'<img src="data:image/png;base64,{logo_b64}" style="max-width:220px;margin-bottom:10px;">' if logo_b64 else ''}
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;">
          {f'<img src="data:image/png;base64,{icon_b64}" width="38" height="38">' if icon_b64 else '🧾'}
          <h2 style="margin:0;color:#38bdf8;">EMED Fiscal • Módulo NF</h2>
        </div>
        <p style="font-size:12.5px;color:var(--muted);margin-top:6px;">Portal de Faturamento, Emissão de Notas &amp; Gestão Tributária 24/7</p>
      </div>
      <div style="margin-bottom:12px;">
        <label>Usuário</label>
        <input id="loginUser" placeholder="Digite seu usuário (ex: netto, vitor ou faturamento)" />
      </div>
      <div style="margin-bottom:16px;">
        <label>Senha</label>
        <input id="loginPass" type="password" placeholder="Digite sua senha" onkeydown="if(event.key==='Enter') fazerLoginFiscal()" />
      </div>
      <button class="btn btn-primary" onclick="fazerLoginFiscal()">🔐 Entrar no Portal Fiscal</button>
      <div id="loginMsg" style="color:#f87171;font-size:12px;margin-top:10px;text-align:center;"></div>
    </div>

    <!-- APLICAÇÃO LOGADA -->
    <div id="appBox" style="display:none;">
      <div class="header-bar">
        <div style="display:flex;align-items:center;gap:12px;">
          {f'<img src="data:image/png;base64,{icon_b64}" width="40" height="40">' if icon_b64 else '🧾'}
          <div>
            <h3 style="margin:0;font-size:18px;">EMED Fiscal • Módulo Tributário Multi-Filial</h3>
            <div style="font-size:12px;color:var(--muted);">Operador: <b id="lblOperador" style="color:#38bdf8;">NETTO</b> &bull; Cargo: <span id="lblCargo" style="color:#a5f3fc;">Diretoria &amp; Controladoria</span></div>
          </div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <span class="badge">ALTA DISPONIBILIDADE 24/7 ATIVA</span>
          <a href="/" class="btn btn-outline" style="padding:6px 12px;font-size:12px;">🏠 Voltar ao Sistema Principal</a>
          <button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" onclick="logoutFiscal()">🚪 Sair</button>
        </div>
      </div>

      <!-- SELETOR DE FILIAL -->
      <div class="radio-bar">
        <div id="pill_FILIAL_DF" class="radio-pill active" onclick="selecionarFilial('FILIAL_DF')">🏢 Filial Brasília (DF)</div>
        <div id="pill_MATRIZ_CE" class="radio-pill" onclick="selecionarFilial('MATRIZ_CE')">🏛️ Matriz (Eusébio - CE)</div>
        <div id="pill_CONSOLIDADO" class="radio-pill" onclick="selecionarFilial('CONSOLIDADO')">🌐 Visão Consolidada (Geral)</div>
      </div>

      <!-- CARD DA UNIDADE ATIVA -->
      <div class="card card-highlight" id="cardUnidadeInfo"></div>

      <!-- CONFIGURAÇÃO & CERTIFICADO A1 -->
      <details class="card" style="cursor:pointer;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;" id="tituloExpanderCfg">⚙️ Configurar Dados Fiscais &amp; Certificado Digital A1</summary>
        <div style="margin-top:14px;cursor:default;">
          <div id="bannerCertStatus" style="margin-bottom:12px;"></div>
          <div class="grid-2">
            <div><label id="lblCnpjUnidade">CNPJ da Unidade:</label><input id="cfgCnpj" /></div>
            <div><label>Série da Nota Fiscal:</label><input id="cfgSerie" /></div>
            <div><label>Inscrição Municipal / CF/DF:</label><input id="cfgIm" /></div>
            <div><label id="lblAliqUnidade">Alíquota ISS Padrão (%):</label><input id="cfgAliq" type="number" step="0.1" /></div>
            <div><label>Razão Social Completa:</label><input id="cfgRazao" /></div>
            <div><label>Telefone da Unidade:</label><input id="cfgFone" /></div>
            <div><label>Endereço Completo:</label><input id="cfgEnd" /></div>
            <div><label>E-mail Financeiro:</label><input id="cfgEmail" /></div>
          </div>
          <h4 style="margin:14px 0 8px 0;color:var(--cyan);">🔐 Certificado Digital A1 (.pfx / .p12)</h4>
          <div class="grid-2">
            <div><label>Arquivo do Certificado A1 (.pfx):</label><input id="cfgCertFile" type="file" accept=".pfx,.p12" /></div>
            <div><label>Senha do Certificado:</label><input id="cfgCertPass" type="password" placeholder="Senha do arquivo .pfx" /></div>
          </div>
          <label style="display:flex;align-items:center;gap:8px;margin-top:10px;cursor:pointer;">
            <input type="checkbox" id="cfgReplicarCert" checked style="width:auto;" />
            🔗 Aplicar este mesmo Certificado A1 da EMED para todas as unidades (Matriz e Filial)
          </label>
          <div style="margin-top:12px;">
            <button class="btn btn-blue" id="btnSalvarCfgUnidade" onclick="salvarConfigFilial()">💾 Salvar Parâmetros da Unidade</button>
          </div>
        </div>
      </details>

      <!-- KPIs -->
      <div class="grid-3">
        <div class="card"><div style="font-size:12px;color:var(--muted);">Total em Fila Fiscal</div><div class="kpi-num" id="kpiFila">0 OSs</div></div>
        <div class="card"><div style="font-size:12px;color:var(--muted);">Notas Fiscais Emitidas</div><div class="kpi-num" id="kpiEmitidas">0 NFs</div></div>
        <div class="card"><div style="font-size:12px;color:var(--muted);" id="lblKpiFaturado">Total Faturado</div><div class="kpi-num" id="kpiTotal">R$ 0,00</div></div>
      </div>

      <!-- FILA DE OSs -->
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
          <h4 style="margin:0;color:var(--cyan);">📋 Fila de Faturamento &amp; Ordens de Serviço Concluídas</h4>
          <button class="btn btn-outline" style="padding:6px 12px;font-size:12px;" onclick="criarOsTesteBrasilia()">🏥 Criar OS de Teste em Brasília (DF)</button>
        </div>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr><th>OS #</th><th>Cliente / Hospital</th><th>Local</th><th>Equipamento</th><th>Peça</th><th>Valor Total</th><th>Situação Fiscal</th></tr>
            </thead>
            <tbody id="tbodyFilaOs"></tbody>
          </table>
        </div>
      </div>

      <!-- FORMULÁRIO DE EMISSÃO -->
      <div class="card card-highlight">
        <h4 style="margin:0 0 12px 0;color:var(--cyan);" id="tituloFormEmissao">🚀 Emissão de Nota Fiscal em 1 Clique</h4>
        <div class="grid-2" style="margin-bottom:12px;">
          <div>
            <label>Selecione a Ordem de Serviço Concluída:</label>
            <select id="selOsEmissao" onchange="aoTrocarOsEmissao(this.value)"></select>
          </div>
          <div>
            <label>📌 Tipo de Operação &amp; Finalidade da Nota Fiscal:</label>
            <select id="selTipoOperacao" onchange="aplicarTemplateFinalidadeNota()">
              <option value="🛠️ PRESTAÇÃO DE SERVIÇOS & PEÇAS (FATURAMENTO DE MANUTENÇÃO)">🛠️ PRESTAÇÃO DE SERVIÇOS &amp; PEÇAS (FATURAMENTO DE MANUTENÇÃO)</option>
              <option value="🔬 NOTA DE DIAGNÓSTICO TÉCNICO & LAUDO PERICIAL">🔬 NOTA DE DIAGNÓSTICO TÉCNICO &amp; LAUDO PERICIAL</option>
              <option value="📦 DEVOLUÇÃO / RETORNO DE REMESSA PARA CONSERTO (CFOP 5916 / 6916)">📦 DEVOLUÇÃO / RETORNO DE REMESSA PARA CONSERTO (CFOP 5916 / 6916)</option>
              <option value="🚚 REMESSA PARA CONSERTO OU CALIBRAÇÃO (CFOP 5915 / 6915)">🚚 REMESSA PARA CONSERTO OU CALIBRAÇÃO (CFOP 5915 / 6915)</option>
            </select>
          </div>
        </div>

        <div class="grid-3" style="margin-bottom:10px;">
          <div><label>Razão Social do Tomador:</label><input id="nfCliente" /></div>
          <div><label>CNPJ do Tomador:</label><input id="nfCnpj" /></div>
          <div><label>E-mail para Envio da Nota:</label><input id="nfEmail" /></div>
          <div><label>Endereço do Hospital:</label><input id="nfEnd" /></div>
          <div><label>Município:</label><input id="nfCid" /></div>
          <div><label>UF:</label><input id="nfUf" /></div>
        </div>

        <div style="margin-bottom:10px;">
          <label>2. Discriminação dos Serviços &amp; Operação Fiscal (Texto Oficial da Nota):</label>
          <textarea id="nfDiscriminacao" rows="4"></textarea>
        </div>

        <div class="grid-4" style="margin-bottom:10px;">
          <div><label>Valor Mão de Obra / Serviços (R$):</label><input id="nfValSrv" type="number" step="0.01" oninput="recalcularTotaisFormNf()" /></div>
          <div><label>Valor Peças / Produtos (R$):</label><input id="nfValPec" type="number" step="0.01" oninput="recalcularTotaisFormNf()" /></div>
          <div><label id="lblFormAliqIss">Alíquota ISS (%):</label><input id="nfAliqIss" type="number" step="0.1" oninput="recalcularTotaisFormNf()" /></div>
          <div><label>Desconto Concedido (R$):</label><input id="nfDesconto" type="number" step="0.01" value="0" oninput="recalcularTotaisFormNf()" /></div>
        </div>

        <div id="barraResumoIss" style="background:#0f172a;padding:10px 14px;border-radius:6px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;font-size:13px;"></div>

        <button class="btn btn-primary" id="btnEmitirNf" onclick="emitirNotaFiscalAgora()">🚀 EMITIR NOTA FISCAL EM 1 CLIQUE</button>
        <div id="boxResultadoEmissao" style="margin-top:14px;"></div>
      </div>

      <!-- HISTÓRICO & CANCELAMENTO -->
      <div class="card">
        <h4 style="margin:0 0 10px 0;color:var(--cyan);">📜 Histórico de Notas Fiscais Emitidas</h4>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr><th>NFS-e</th><th>Série</th><th>OS #</th><th>Cliente</th><th>Filial</th><th>Tipo / CFOP</th><th>Valor</th><th>Emissão</th><th>Status</th><th>Ações</th></tr>
            </thead>
            <tbody id="tbodyHistoricoNf"></tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h4 style="margin:0 0 10px 0;color:#f87171;">🚫 Cancelamento de Nota Fiscal Homologada</h4>
        <div class="grid-3" style="align-items:end;">
          <div><label>Selecione a Nota Fiscal Ativa:</label><select id="selNotaCancelar"></select></div>
          <div><label>Justificativa Legal do Cancelamento:</label><input id="inpJustificativaCanc" value="Emissão realizada em ambiente de simulação e testes de homologação" /></div>
          <div><button class="btn btn-danger" style="width:100%;" onclick="cancelarNotaSelecionada()">🚫 Confirmar Cancelamento</button></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let FILIAL_ATIVA = "FILIAL_DF";
    let DADOS_ATUAIS = null;
    let USUARIO_FISCAL = null;

    async function initPortalFiscal() {{
      const params = new URLSearchParams(window.location.search);
      const token = params.get("token");
      if (token) {{
        const res = await fetch("/api/fiscal/v2/login", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ token }})
        }}).then(r => r.json());
        if (res.ok) {{
          localStorage.setItem("emed_fiscal_user", JSON.stringify(res));
          window.history.replaceState({{}}, document.title, window.location.pathname);
        }}
      }}
      const saved = localStorage.getItem("emed_fiscal_user");
      if (saved) {{
        try {{
          USUARIO_FISCAL = JSON.parse(saved);
          mostrarAppFiscal();
          return;
        }} catch(e) {{}}
      }}
      document.getElementById("loginBox").style.display = "block";
    }}

    async function fazerLoginFiscal() {{
      const username = document.getElementById("loginUser").value;
      const password = document.getElementById("loginPass").value;
      const res = await fetch("/api/fiscal/v2/login", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ username, password }})
      }}).then(r => r.json());
      if (res.ok) {{
        USUARIO_FISCAL = res;
        localStorage.setItem("emed_fiscal_user", JSON.stringify(res));
        document.getElementById("loginBox").style.display = "none";
        mostrarAppFiscal();
      }} else {{
        document.getElementById("loginMsg").textContent = res.msg || "Credenciais inválidas.";
      }}
    }}

    function logoutFiscal() {{
      localStorage.removeItem("emed_fiscal_user");
      window.location.href = window.location.pathname;
    }}

    function mostrarAppFiscal() {{
      document.getElementById("appBox").style.display = "block";
      document.getElementById("lblOperador").textContent = (USUARIO_FISCAL?.username || "netto").toUpperCase();
      document.getElementById("lblCargo").textContent = USUARIO_FISCAL?.cargo || "Diretoria & Controladoria";
      carregarDadosFiscais();
    }}

    function selecionarFilial(cod) {{
      FILIAL_ATIVA = cod;
      ["FILIAL_DF", "MATRIZ_CE", "CONSOLIDADO"].forEach(c => {{
        document.getElementById("pill_" + c)?.classList.toggle("active", c === cod);
      }});
      carregarDadosFiscais();
    }}

    async function carregarDadosFiscais(osId = "") {{
      const url = `/api/fiscal/v2/dados?filial=${{encodeURIComponent(FILIAL_ATIVA)}}&os_id=${{encodeURIComponent(osId)}}`;
      const res = await fetch(url).then(r => r.json());
      if (!res.ok) return;
      DADOS_ATUAIS = res;
      const cfg = res.cfg_ativa || {{}};
      const cert = res.certificado || {{}};
      const tipoUn = FILIAL_ATIVA === "MATRIZ_CE" ? "Matriz" : "Filial";

      document.getElementById("cardUnidadeInfo").innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div>
            <span style="font-size:16px;font-weight:900;color:var(--cyan);">${{cfg.razao_social || ''}}</span>
            <span class="badge" style="margin-left:8px;">${{cfg.sigla || ''}}</span>
          </div>
          <div style="font-size:12px;color:#a5f3fc;font-weight:800;">🔐 ${{cert.modo || ''}}</div>
        </div>
        <div style="font-size:12.5px;color:#cbd5e1;margin-top:8px;line-height:1.5;">
          <b>CNPJ:</b> ${{cfg.cnpj || ''}} &bull; <b>Inscrição (CF/DF ou IM):</b> ${{cfg.inscricao_municipal || ''}} &bull; <b>Série NF:</b> ${{cfg.serie_padrao || ''}}<br/>
          <b>Endereço:</b> ${{cfg.endereco || ''}}, ${{cfg.cidade || ''}} - ${{cfg.uf || ''}} (CEP: ${{cfg.cep || ''}}) &bull; <b>Fone:</b> ${{cfg.telefone || ''}}<br/>
          <b>Órgão Fiscal:</b> ${{cfg.orgao_fiscal || ''}} &bull; <b>Alíquota ISS Padrão:</b> ${{cfg.aliquota_iss_padrao || 5.0}}%
        </div>
      `;

      document.getElementById("tituloExpanderCfg").textContent = `⚙️ Configurar Dados Fiscais & Certificado Digital A1 (${{cfg.nome || tipoUn}})`;
      document.getElementById("lblCnpjUnidade").textContent = `CNPJ da ${{tipoUn}}:`;
      document.getElementById("lblAliqUnidade").textContent = `Alíquota ISS Padrão da ${{tipoUn}} (%):`;
      document.getElementById("btnSalvarCfgUnidade").textContent = `💾 Salvar Parâmetros da ${{tipoUn}}`;
      document.getElementById("cfgCnpj").value = cfg.cnpj || "";
      document.getElementById("cfgSerie").value = cfg.serie_padrao || "";
      document.getElementById("cfgIm").value = cfg.inscricao_municipal || "";
      document.getElementById("cfgAliq").value = cfg.aliquota_iss_padrao ?? 5.0;
      document.getElementById("cfgRazao").value = cfg.razao_social || "";
      document.getElementById("cfgFone").value = cfg.telefone || "";
      document.getElementById("cfgEnd").value = cfg.endereco || "";
      document.getElementById("cfgEmail").value = cfg.email || "";

      document.getElementById("bannerCertStatus").innerHTML = cert.instalado
        ? `<div style="background:#064e3b;border:1px solid #10b981;padding:10px 14px;border-radius:6px;font-size:12px;color:#ecfdf5;">
             <b>🔒 CERTIFICADO DIGITAL A1 GRAVADO &amp; ATIVO PARA A ${{tipoUn.toUpperCase()}}!</b><br/>
             O certificado já está salvo permanentemente no sistema. Não é necessário reenviar ao trocar de unidade.
           </div>`
        : `<div style="background:#1e293b;border:1px solid #475569;padding:10px 14px;border-radius:6px;font-size:12px;color:#cbd5e1;">
             💡 Carregue o arquivo <b>.pfx</b> abaixo para ativar a transmissão em Produção SEFAZ.
           </div>`;

      document.getElementById("kpiFila").textContent = `${{res.kpis.pendentes}} OSs`;
      document.getElementById("kpiEmitidas").textContent = `${{res.kpis.emitidas}} NFs`;
      document.getElementById("lblKpiFaturado").textContent = `Total Faturado (${{cfg.sigla || ''}})`;
      document.getElementById("kpiTotal").textContent = `R$ ${{Number(res.kpis.total_faturar || 0).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;

      const tbFila = document.getElementById("tbodyFilaOs");
      tbFila.innerHTML = (res.fila_os || []).map(o => `
        <tr>
          <td><b>#${{o.id}}</b></td>
          <td>${{o.cliente}}</td>
          <td>${{o.cidade}} - ${{o.estado}}</td>
          <td>${{o.equipamento}}</td>
          <td>${{o.peca}}</td>
          <td>R$ ${{Number(o.valor_liquido).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}</td>
          <td>${{o.numero_nf ? '✅ ' + o.numero_nf : o.status_fiscal}}</td>
        </tr>
      `).join("") || `<tr><td colspan="7" style="text-align:center;color:var(--muted);">Nenhuma OS concluída nesta unidade.</td></tr>`;

      const selOs = document.getElementById("selOsEmissao");
      selOs.innerHTML = (res.fila_os || []).map(o =>
        `<option value="${{o.id}}" ${{res.os_selecionada && String(res.os_selecionada.os_id) === String(o.id) ? 'selected' : ''}}>
          OS #${{o.id}} – ${{o.cliente}} (${{o.equipamento}}) [Total: R$ ${{Number(o.valor_liquido).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}]
        </option>`
      ).join("");

      preencherFormularioComOs(res.os_selecionada, cfg);

      const tbHist = document.getElementById("tbodyHistoricoNf");
      tbHist.innerHTML = (res.historico || []).map(h => `
        <tr>
          <td><b>${{h.numero_nf}}</b></td>
          <td>${{h.serie}}</td>
          <td>#${{h.os_id}}</td>
          <td>${{h.cliente}}</td>
          <td>${{h.filial}}</td>
          <td style="font-size:11px;">${{h.cfop ? 'CFOP ' + h.cfop : 'NFS-e'}}</td>
          <td>R$ ${{Number(h.valor_liquido).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}</td>
          <td>${{h.data_emissao}}</td>
          <td>${{h.status_fiscal}}</td>
          <td>
            <a href="/api/fiscal/danfe/${{h.os_id}}" target="_blank" class="btn btn-blue" style="padding:4px 8px;font-size:11px;">🖨️ DANFE</a>
            <a href="/api/fiscal/v2/xml/${{h.os_id}}" class="btn btn-outline" style="padding:4px 8px;font-size:11px;">📥 XML</a>
          </td>
        </tr>
      `).join("") || `<tr><td colspan="10" style="text-align:center;color:var(--muted);">Nenhuma nota fiscal emitida registrada ainda nesta unidade.</td></tr>`;

      const selCanc = document.getElementById("selNotaCancelar");
      const ativas = (res.historico || []).filter(h => !String(h.status_fiscal).toUpperCase().includes("CANCELAD"));
      selCanc.innerHTML = ativas.map(h => `<option value="${{h.id}}">NFS-e Nº ${{h.numero_nf}} — ${{h.cliente}} (R$ ${{Number(h.valor_liquido).toFixed(2)}})</option>`).join("")
        || `<option value="">-- Nenhuma nota ativa para cancelar --</option>`;
    }}

    function preencherFormularioComOs(d, cfg) {{
      if (!d) return;
      document.getElementById("nfCliente").value = d.cliente || "";
      document.getElementById("nfCnpj").value = d.cnpj_tomador || "";
      document.getElementById("nfEmail").value = d.email_cliente || "";
      document.getElementById("nfEnd").value = d.tomador_endereco || "";
      document.getElementById("nfCid").value = d.tomador_cidade || "";
      document.getElementById("nfUf").value = d.tomador_uf || "";
      document.getElementById("nfDiscriminacao").value = d.discriminacao_servico || "";
      document.getElementById("nfValSrv").value = d.valor_servicos ?? 0;
      document.getElementById("nfValPec").value = d.valor_pecas ?? 0;
      document.getElementById("nfAliqIss").value = d.aliquota_iss ?? (cfg?.aliquota_iss_padrao || 5.0);
      document.getElementById("nfDesconto").value = d.valor_desconto ?? 0;
      document.getElementById("lblFormAliqIss").textContent = `Alíquota ISS (${{cfg?.uf || 'DF'}}) (%):`;
      document.getElementById("btnEmitirNf").textContent = `🚀 EMITIR NOTA FISCAL (${{cfg?.sigla || 'EMED'}}) EM 1 CLIQUE`;
      recalcularTotaisFormNf();
    }}

    function aoTrocarOsEmissao(osId) {{
      carregarDadosFiscais(osId);
    }}

    function aplicarTemplateFinalidadeNota() {{
      const d = DADOS_ATUAIS?.os_selecionada;
      if (!d) return;
      const tipo = document.getElementById("selTipoOperacao").value;
      if (tipo.includes("DIAGNÓSTICO")) {{
        document.getElementById("nfDiscriminacao").value =
          `Prestação de serviços técnicos especializados de DIAGNÓSTICO TÉCNICO, ENSAIOS E AVALIAÇÃO PERICIAL no equipamento médico ${{d.equipamento || 'MÉDICO-HOSPITALAR'}}. Atendimento referente à Ordem de Serviço #${{d.os_id}}. Emissão de laudo técnico de conformidade, ensaios elétricos e testes de viabilidade operacional. Cliente: ${{d.cliente}} (${{d.tomador_cidade}} - ${{d.tomador_uf}}).`;
        document.getElementById("nfAliqIss").value = DADOS_ATUAIS?.cfg_ativa?.aliquota_iss_padrao || 5.0;
      }} else if (tipo.includes("DEVOLUÇÃO")) {{
        document.getElementById("nfDiscriminacao").value =
          `RETORNO / DEVOLUÇÃO DE MERCADORIA OU BEM RECEBIDO PARA CONSERTO OU REPARO. Equipamento: ${{d.equipamento || 'MÉDICO-HOSPITALAR'}}. Referente à OS #${{d.os_id}}. Operação ao abrigo de não-incidência / suspensão de tributos conforme legislação vigente (CFOP 5916/6916). Destinatário: ${{d.cliente}}.`;
        document.getElementById("nfAliqIss").value = 0;
        document.getElementById("nfValPec").value = 0;
      }} else if (tipo.includes("REMESSA")) {{
        document.getElementById("nfAliqIss").value = 0;
      }} else {{
        document.getElementById("nfDiscriminacao").value = d.discriminacao_servico || "";
        document.getElementById("nfAliqIss").value = DADOS_ATUAIS?.cfg_ativa?.aliquota_iss_padrao || 5.0;
      }}
      recalcularTotaisFormNf();
    }}

    function recalcularTotaisFormNf() {{
      const vSrv = parseFloat(document.getElementById("nfValSrv").value || 0);
      const vPec = parseFloat(document.getElementById("nfValPec").value || 0);
      const aliq = parseFloat(document.getElementById("nfAliqIss").value || 0);
      const desc = parseFloat(document.getElementById("nfDesconto").value || 0);
      const total = Math.max(0, (vSrv + vPec) - desc);
      const iss = vSrv * (aliq / 100.0);
      document.getElementById("barraResumoIss").innerHTML = `
        <div><b>Base de Cálculo ISS:</b> R$ ${{vSrv.toFixed(2)}} &bull; <b>Valor ISS Estimado:</b> R$ ${{iss.toFixed(2)}}</div>
        <div style="font-size:16px;font-weight:900;color:var(--cyan);">TOTAL DA NOTA: R$ ${{total.toFixed(2)}}</div>
      `;
    }}

    async function salvarConfigFilial() {{
      const fileInp = document.getElementById("cfgCertFile");
      let cert_b64 = null;
      if (fileInp.files && fileInp.files[0]) {{
        const buf = await fileInp.files[0].arrayBuffer();
        let binary = "";
        const bytes = new Uint8Array(buf);
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        cert_b64 = btoa(binary);
      }}
      const res = await fetch("/api/fiscal/v2/salvar-config", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          filial: FILIAL_ATIVA,
          cnpj: document.getElementById("cfgCnpj").value,
          serie_padrao: document.getElementById("cfgSerie").value,
          inscricao_municipal: document.getElementById("cfgIm").value,
          aliquota_iss_padrao: document.getElementById("cfgAliq").value,
          razao_social: document.getElementById("cfgRazao").value,
          telefone: document.getElementById("cfgFone").value,
          endereco: document.getElementById("cfgEnd").value,
          email: document.getElementById("cfgEmail").value,
          cert_b64,
          senha_cert: document.getElementById("cfgCertPass").value,
          replicar_todas: document.getElementById("cfgReplicarCert").checked,
          usuario: USUARIO_FISCAL?.username || "netto"
        }})
      }}).then(r => r.json());
      alert(res.msg || "Configurações salvas!");
      carregarDadosFiscais();
    }}

    async function emitirNotaFiscalAgora() {{
      const osId = document.getElementById("selOsEmissao").value;
      if (!osId) {{ alert("Selecione uma Ordem de Serviço."); return; }}
      const res = await fetch("/api/fiscal/v2/emitir", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          os_id: osId,
          filial_emissora: FILIAL_ATIVA,
          tipo_nota: document.getElementById("selTipoOperacao").value,
          cliente: document.getElementById("nfCliente").value,
          cnpj_tomador: document.getElementById("nfCnpj").value,
          email_cliente: document.getElementById("nfEmail").value,
          tomador_endereco: document.getElementById("nfEnd").value,
          tomador_cidade: document.getElementById("nfCid").value,
          tomador_uf: document.getElementById("nfUf").value,
          discriminacao_servico: document.getElementById("nfDiscriminacao").value,
          valor_servicos: document.getElementById("nfValSrv").value,
          valor_pecas: document.getElementById("nfValPec").value,
          aliquota_iss: document.getElementById("nfAliqIss").value,
          valor_desconto: document.getElementById("nfDesconto").value,
          usuario: USUARIO_FISCAL?.username || "netto"
        }})
      }}).then(r => r.json());
      if (res.ok) {{
        const n = res.nota;
        const msgWpp = encodeURIComponent(`🧾 *EMED ELETROMEDICINA • NOTA FISCAL EMITIDA*\\n🏥 *Cliente:* ${{n.cliente}}\\n📋 *NFS-e Nº:* ${{n.numero_nf}} (OS #${{osId}})\\n💰 *Valor:* R$ ${{Number(n.valor_liquido||0).toFixed(2)}}\\n🔐 *Chave:* ${{n.chave_acesso}}`);
        document.getElementById("boxResultadoEmissao").innerHTML = `
          <div style="background:#14532d;border:1.5px solid #22c55e;border-radius:8px;padding:14px;color:#fff;">
            <div style="font-weight:900;font-size:15px;margin-bottom:6px;">🎉 NOTA FISCAL AUTORIZADA COM SUCESSO!</div>
            <b>Número da NFS-e:</b> ${{n.numero_nf}} &bull; <b>Série:</b> ${{n.serie}}<br/>
            <b>Chave de Acesso:</b> <span style="font-family:monospace;">${{n.chave_acesso}}</span><br/>
            <b>Protocolo SEFAZ:</b> ${{n.protocolo}} &bull; <b>Status:</b> ${{n.status}}
            <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap;">
              <a href="/api/fiscal/danfe/${{osId}}" target="_blank" class="btn btn-blue">🖨️ Abrir / Imprimir Espelho DANFE</a>
              <a href="/api/fiscal/v2/xml/${{osId}}" class="btn btn-outline">📥 Baixar Arquivo XML (SEFAZ)</a>
              <a href="https://wa.me/?text=${{msgWpp}}" target="_blank" class="btn" style="background:#16a34a;color:#fff;">📲 Enviar via WhatsApp</a>
            </div>
          </div>
        `;
        carregarDadosFiscais(osId);
      }} else {{
        alert("Erro ao emitir: " + (res.msg || "Falha interna"));
      }}
    }}

    async function cancelarNotaSelecionada() {{
      const id = document.getElementById("selNotaCancelar").value;
      const just = document.getElementById("inpJustificativaCanc").value;
      if (!id) {{ alert("Nenhuma nota ativa selecionada."); return; }}
      const res = await fetch("/api/fiscal/v2/cancelar", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ id, justificativa: just, usuario: USUARIO_FISCAL?.username || "netto" }})
      }}).then(r => r.json());
      alert(res.msg || "Operação concluída");
      if (res.ok) carregarDadosFiscais();
    }}

    async function criarOsTesteBrasilia() {{
      const res = await fetch("/api/fiscal/v2/criar-os-teste", {{ method: "POST" }}).then(r => r.json());
      alert(res.msg);
      if (res.ok) carregarDadosFiscais(String(res.os_id));
    }}

    initPortalFiscal();
  </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


def registrar_rotas_portal_fiscal(app: web.Application) -> None:
    app.router.add_get("/fiscal", handle_pagina_fiscal_nativa)
    app.router.add_post("/api/fiscal/v2/login", api_fiscal_v2_login)
    app.router.add_get("/api/fiscal/v2/dados", api_fiscal_v2_dados)
    app.router.add_post("/api/fiscal/v2/salvar-config", api_fiscal_v2_salvar_config)
    app.router.add_post("/api/fiscal/v2/emitir", api_fiscal_v2_emitir)
    app.router.add_post("/api/fiscal/v2/cancelar", api_fiscal_v2_cancelar)
    app.router.add_post("/api/fiscal/v2/criar-os-teste", api_fiscal_v2_criar_os_teste)
    app.router.add_get("/api/fiscal/v2/xml/{os_id}", api_fiscal_v2_xml_download)
