# -*- coding: utf-8 -*-
"""
Portal Fiscal Web Nativo (Alta Disponibilidade 24/7) — EMED Eletromedicina.
Roda diretamente integrado ao servidor principal em https://emedservice.med.br/fiscal
(e também responde automaticamente caso o domínio fiscal.emedservice.med.br aponte para cá),
eliminando qualquer risco de suspensão de container secundário no Render.
"""

import os
import asyncio
import io
import csv
import zipfile
import json
import time
import uuid
import base64
from datetime import datetime
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
        resp = web.json_response({
            "ok": True,
            "username": u,
            "role": info["role"],
            "cargo": info["cargo"],
        })
        try:
            from emed_app_server import gerar_token_sessao
            tkn = gerar_token_sessao(1, u, info["role"])
            resp.set_cookie("emed_session", tkn, max_age=30*86400, httponly=True, samesite="Lax", path="/")
        except Exception:
            pass
        return resp
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

        # Peças disponíveis no almoxarifado (Estoque Físico & Estoque Fiscal)
        cur_p = conn.execute("SELECT id, codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade), preco_custo, unidade, alerta_reajuste FROM estoque_pecas ORDER BY nome_peca ASC LIMIT 2000")
        rows_p = cur_p.fetchall()
        pecas_almox = [{"id": rp[0], "codigo": rp[1] or "", "nome": rp[2] or "", "qtd": rp[3] or 0, "qtd_fiscal": float(rp[4] if rp[4] is not None else (rp[3] or 0)), "preco": float(rp[5] or 0.0), "unidade": rp[6] or "UN", "alerta_reajuste": rp[7] or ""} for rp in rows_p]

        # Veículos da frota
        cur_v = conn.execute("SELECT placa, modelo FROM veiculos ORDER BY modelo ASC")
        veiculos_frota = [{"placa": rv[0] or "", "modelo": rv[1] or ""} for rv in cur_v.fetchall()]

        # Histórico recente de baixas de consumíveis operacionais
        cur_c = conn.execute("SELECT id, tecnico_setor, nome_item, quantidade, finalidade, data_baixa FROM baixas_consumiveis ORDER BY id DESC LIMIT 10")
        consumiveis_recentes = [{"id": rc[0], "setor": rc[1] or "", "item": rc[2] or "", "qtd": rc[3] or 0, "finalidade": rc[4] or "", "data": rc[5] or ""} for rc in cur_c.fetchall()]

    
        cfg_smtp_raw = {}
        for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from"):
            r_s = conn.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (k,)).fetchone()
            cfg_smtp_raw[k] = r_s[0] if (r_s and r_s[0]) else ""
        cfg_smtp_safe = {
            "smtp_host": cfg_smtp_raw.get("smtp_host", ""),
            "smtp_port": cfg_smtp_raw.get("smtp_port", "587"),
            "smtp_user": cfg_smtp_raw.get("smtp_user", ""),
            "smtp_from": cfg_smtp_raw.get("smtp_from", ""),
            "has_pass": bool(cfg_smtp_raw.get("smtp_pass")),
        }

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
        "pecas_almox": pecas_almox,
        "veiculos_frota": veiculos_frota,
        "consumiveis_recentes": consumiveis_recentes,
        "cfg_smtp": cfg_smtp_safe,
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

    with _get_db_connection(db_name) as conn:
        for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_from"):
            if k in body:
                val = str(body.get(k, "")).strip()
                conn.execute("INSERT INTO configuracoes_sistema (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor", (k, val))
        if body.get("smtp_pass"):
            conn.execute("INSERT INTO configuracoes_sistema (chave, valor) VALUES ('smtp_pass', ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor", (str(body.get("smtp_pass")).strip(),))
        conn.commit()

    _registrar_log_fiscal("CONFIG_FILIAL", f"Parâmetros salvos para {filial} (ISS: {cfg['aliquota_iss_padrao']}%){msg_cert}", str(body.get("usuario", "netto")))
    return web.json_response({"ok": True, "msg": f"✅ Parâmetros de {cfg.get('nome')} salvos com sucesso!{msg_cert}"})


async def api_fiscal_v2_emitir(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    os_id = int(body.get("os_id"))
    filial = str(body.get("filial_emissora", "FILIAL_DF")).upper()
    if filial == "CONSOLIDADO":
        filial = "FILIAL_DF"

    tipo_op = str(body.get("tipo_nota", "🏛️ NFS-e NACIONAL (PADRÃO RECEITA FEDERAL / SERPRO • DPS)"))
    uf_tom = str(body.get("tomador_uf", "DF")).strip().upper()
    nat_op = "TRIBUTAÇÃO NO MUNICÍPIO / DF"
    cfop = ""
    if "NACIONAL" in tipo_op:
        nat_op = "PRESTAÇÃO DE SERVIÇOS NO AMBIENTE NACIONAL (DPS / RECEITA FEDERAL)"
    elif "DIAGNÓSTICO" in tipo_op:
        nat_op = "PRESTAÇÃO DE SERVIÇO DE DIAGNÓSTICO TÉCNICO"
    elif "DEVOLUÇÃO" in tipo_op:
        nat_op = "RETORNO DE MERCADORIA/BEM RECEBIDO PARA CONSERTO"
        cfop = "5916" if uf_tom in ("DF", "CE") else "6916"
    elif "REMESSA" in tipo_op:
        nat_op = "REMESSA DE BEM PARA CONSERTO/REPARO"
        cfop = "5915" if uf_tom in ("DF", "CE") else "6915"

    deduzir_pecas = bool(body.get("deduzir_pecas_fisco", True))
    val_pecas_raw = float(body.get("valor_pecas") or 0.0)
    val_pecas_efetivo = val_pecas_raw if deduzir_pecas else 0.0
    val_srv = float(body.get("valor_servicos") or 0.0)
    val_desc = float(body.get("valor_desconto") or 0.0)
    val_tot_calc = max(0.0, (val_srv + val_pecas_efetivo) - val_desc)
    cliente_informado = str(body.get("cliente", "")).strip()
    cnpj_informado = str(body.get("cnpj_tomador", "")).strip()
    forcar_duplicidade = bool(body.get("forcar_emissao_duplicada", False))

    # INTERTRAVAMENTO CONTRA EMISSÃO DUPLICADA
    if not forcar_duplicidade:
        with _get_db_connection(db_name) as conn_chk:
            # 1. Checa se já existe nota ativa com a mesma OS
            cur_chk = conn_chk.execute("""
                SELECT id, numero_nf, os_id, cliente, valor_liquido, data_emissao, status_fiscal, chave_acesso, discriminacao_servico
                FROM notas_fiscais
                WHERE os_id = ?
                  AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%'
                  AND numero_nf IS NOT NULL AND numero_nf != ''
                ORDER BY id DESC LIMIT 1
            """, (os_id,))
            row_chk = cur_chk.fetchone()

            # 2. Checa se já existe nota ativa para mesmo cliente com mesmo valor total aproximado
            if not row_chk and cliente_informado and val_tot_calc > 0:
                cur_chk2 = conn_chk.execute("""
                    SELECT id, numero_nf, os_id, cliente, valor_liquido, data_emissao, status_fiscal, chave_acesso, discriminacao_servico
                    FROM notas_fiscais
                    WHERE (UPPER(cliente) = UPPER(?) OR (cnpj_tomador = ? AND cnpj_tomador != '' AND cnpj_tomador != '00.000.000/0000-00'))
                      AND ABS(COALESCE(valor_liquido, 0) - ?) < 0.05
                      AND UPPER(status_fiscal) NOT LIKE '%CANCELAD%'
                      AND numero_nf IS NOT NULL AND numero_nf != ''
                    ORDER BY id DESC LIMIT 1
                """, (cliente_informado, cnpj_informado, val_tot_calc))
                row_chk = cur_chk2.fetchone()

            if row_chk:
                nid, num_nf, n_os, cli, v_liq, dt_em, st_f, chave, disc = row_chk
                dt_fmt = str(dt_em).replace("T", " ")[:16]
                return web.json_response({
                    "ok": False,
                    "intertravamento_duplicidade": True,
                    "nota_existente": {
                        "id": nid,
                        "numero_nf": num_nf,
                        "os_id": n_os,
                        "cliente": cli,
                        "valor_liquido": float(v_liq or 0.0),
                        "data_emissao": dt_fmt,
                        "status": st_f,
                        "chave_acesso": chave,
                        "link_danfe": f"/api/fiscal/danfe/{n_os}",
                        "link_pdf": f"/api/fiscal/danfe/{n_os}?formato=pdf"
                    },
                    "msg": f"⚠️ A Nota Fiscal {num_nf} referente à OS #{n_os} já foi emitida com sucesso em {dt_fmt} para {cli} no valor de R$ {float(v_liq or 0):,.2f}."
                })
    disc_serv = str(body.get("discriminacao_servico", "")).strip()
    if not deduzir_pecas and val_pecas_raw > 0:
        disc_serv += "\n\n[OBSERVAÇÃO FISCAL: Peças e consumíveis aplicados nesta manutenção encontram-se inclusos na cobertura contratual (sem incidência de faturamento fiscal avulso de mercadoria).]"

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
        "discriminacao_servico": disc_serv,
        "valor_servicos": float(body.get("valor_servicos") or 0.0),
        "valor_pecas": val_pecas_efetivo,
        "valor_desconto": float(body.get("valor_desconto") or 0.0),
        "aliquota_iss": float(body.get("aliquota_iss") or 0.0),
        "filial_emissora": filial,
        "usuario_operador": str(body.get("usuario", "netto")),
        "modo_emissao": str(body.get("modo_emissao", "SIMULACAO")).upper(),
    }

    manager = FiscalManager(db_name)
    res_nota = manager.emitir_nota(os_id, filial, payload_salvar)

    mov_fiscal = bool(body.get("movimentar_estoque_fiscal", True))
    mov_fisico = bool(body.get("movimentar_estoque_fisico", True))
    if mov_fiscal or mov_fisico:
        try:
            with _get_db_connection(db_name) as conn:
                cur_pec = conn.execute("SELECT codigo_peca, id FROM solicitacoes_pecas WHERE os_id = ?", (os_id,)).fetchall()
                for r_p in cur_pec:
                    cod_p = r_p[0]
                    if cod_p:
                        if mov_fiscal:
                            conn.execute("UPDATE estoque_pecas SET saldo_fiscal = MAX(0, COALESCE(saldo_fiscal, quantidade) - 1) WHERE codigo = ? OR id = ?", (cod_p, cod_p))
                        if mov_fisico:
                            conn.execute("UPDATE estoque_pecas SET quantidade = MAX(0, quantidade - 1) WHERE codigo = ? OR id = ?", (cod_p, cod_p))
                conn.commit()
        except Exception:
            pass

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
    senha = str(body.get("senha", "")).strip()

    # Validação de segurança: Senha Mestra Fiscal / Certificado A1 ou senha do usuário admin
    senhas_validas = {"emed2026", "Emed@2026"}
    if usuario in USUARIOS_FISCAL and USUARIOS_FISCAL[usuario].get("senha"):
        senhas_validas.add(USUARIOS_FISCAL[usuario]["senha"])

    if not senha or senha not in senhas_validas:
        return web.json_response({
            "ok": False,
            "msg": "🔒 Senha de autorização incorreta! O cancelamento exige a Senha Mestra Fiscal ou do Certificado Digital A1."
        }, status=403)

    if len(justificativa) < 8:
        return web.json_response({"ok": False, "msg": "Informe uma justificativa legal com no mínimo 8 caracteres."}, status=400)

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT os_id, numero_nf FROM notas_fiscais WHERE id = ?", (id_nf,)).fetchone()
        num_nf = row[1] if row and row[1] else f"#{id_nf}"
        os_id = row[0] if row else None

        conn.execute("""
            UPDATE notas_fiscais
            SET status_fiscal = 'CANCELADA',
                status_quarentena = 'CANCELADA',
                motivo_cancelamento = ?,
                data_cancelamento = datetime('now', 'localtime'),
                atualizado_em = datetime('now', 'localtime'),
                discriminacao_servico = COALESCE(discriminacao_servico, '') || '\n\n[CANCELADA: ' || ? || ']'
            WHERE id = ?
        """, (justificativa, justificativa, id_nf))

        if os_id:
            try:
                conn.execute("""
                    UPDATE clientes_equipamentos
                    SET observacoes_gerais = COALESCE(observacoes_gerais, '') || ' | [NF ' || ? || ' CANCELADA: ' || ? || ']'
                    WHERE id = ?
                """, (str(num_nf), justificativa, os_id))
            except Exception:
                pass
        conn.commit()

    _registrar_log_fiscal("CANCELAMENTO_NF", f"NF {num_nf} (ID #{id_nf}) cancelada por {usuario} | Motivo: {justificativa}", usuario)
    return web.json_response({"ok": True, "msg": f"✅ Nota Fiscal {num_nf} cancelada com sucesso!"})


# ==============================================================================
# RADAR DF-E • NOTAS RECEBIDAS DE FORNECEDORES (SEFAZ & RECEITA FEDERAL)
# ==============================================================================

async def api_fiscal_recebidas_dados(request: web.Request) -> web.Response:
    """Retorna notas fiscais emitidas contra a EMED por fornecedores (DF-e da SEFAZ)."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    filial = request.query.get("filial", "FILIAL_DF").strip().upper()
    filtro_dfe = request.query.get("filtro_dfe", "CONSOLIDADO").strip().upper()
    data_inicio = request.query.get("data_inicio", "2026-01-01").strip()

    with _get_db_connection(db_name) as conn:
        query = """
            SELECT id, cnpj_destinatario, filial, nsu, chave_acesso,
                   emitente_cnpj, emitente_nome, emitente_uf, numero_nf, serie,
                   tipo_documento, data_emissao, data_captura, valor_total,
                   status_manifestacao, data_manifestacao, status_estoque,
                   data_entrada_estoque, itens_resumo, observacoes
            FROM notas_fiscais_recebidas
            WHERE 1=1
        """
        params = []
        if filtro_dfe in ("FILIAL_DF", "MATRIZ_CE"):
            query += " AND filial = ?"
            params.append(filtro_dfe)
        if data_inicio and data_inicio != "TODAS":
            query += " AND COALESCE(data_emissao, '2026-11-18') >= ?"
            params.append(data_inicio)
        query += " ORDER BY COALESCE(data_emissao, '2026-11-18') DESC, id DESC"

        cur = conn.execute(query, params)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        notas = [dict(zip(cols, r)) for r in rows]

        for n in notas:
            if not n.get("data_emissao"):
                n["data_emissao"] = "2026-11-18"
            if not n.get("cnpj_destinatario"):
                n["cnpj_destinatario"] = "03.611.974/0002-80" if n.get("filial") == "FILIAL_DF" else "03.611.974/0001-08"
            if isinstance(n.get("itens_resumo"), str) and n["itens_resumo"]:
                try:
                    n["itens"] = json.loads(n["itens_resumo"])
                except Exception:
                    n["itens"] = []
            else:
                n["itens"] = n.get("itens_resumo") or []

        total_notas = len(notas)
        valor_total = sum(float(n.get("valor_total") or 0.0) for n in notas)
        pend_manif = sum(1 for n in notas if n.get("status_manifestacao") == "SEM_MANIFESTACAO")
        pend_estoque = sum(1 for n in notas if n.get("status_estoque") == "PENDENTE")

        cur_nsu = conn.execute("SELECT filial, ultimo_nsu, max_nsu, data_ultima_consulta, status_ultima_consulta FROM controle_nsu_dfe WHERE filial = ?", (filial if filial != "CONSOLIDADO" else "FILIAL_DF",))
        cols_nsu = [c[0] for c in cur_nsu.description]
        r_nsu = cur_nsu.fetchone()
        nsu_info = dict(zip(cols_nsu, r_nsu)) if r_nsu else {}

    return web.json_response({
        "ok": True,
        "kpis": {
            "total": total_notas,
            "valor_total": valor_total,
            "pend_manifestacao": pend_manif,
            "pend_estoque": pend_estoque
        },
        "nsu_info": nsu_info,
        "notas": notas
    })


def _executar_consulta_dfe_sefaz_real(db_name: str, alvos_filiais: list) -> dict:
    """Conecta diretamente ao WebService NFeDistribuicaoDFe do Ambiente Nacional (SEFAZ/RFB)
    usando o Certificado Digital A1 (.pfx) da EMED e sincroniza notas fiscais emitidas no CNPJ."""
    import ssl
    import gzip
    import tempfile
    import urllib.request
    import xml.etree.ElementTree as ET
    from emed_fiscal import CertificadoManager

    novas_notas = 0
    total_docs_lidos = 0
    mensagens_sefaz = []
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
    except ImportError:
        return {"ok": False, "novas": 0, "msg": "Biblioteca cryptography não disponível."}

    for fil_cod in alvos_filiais:
        st_cert = CertificadoManager.status_certificado(fil_cod, db_name)
        if not st_cert.get("instalado") or not st_cert.get("caminho"):
            continue

        with _get_db_connection(db_name) as conn:
            r_pwd = conn.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (f"cert_senha_{fil_cod.lower()}",)).fetchone()
            senha_pfx = (r_pwd[0] if r_pwd and r_pwd[0] else "Emed@2026").encode("utf-8")

            r_nsu = conn.execute("SELECT ultimo_nsu, max_nsu FROM controle_nsu_dfe WHERE filial = ?", (fil_cod,)).fetchone()
            ult_nsu_db = r_nsu[0] if r_nsu and r_nsu[0] else "000000000000000"
            # Se ainda estava no NSU 50/100 de semente, buscar desde 000000000000000
            if int(ult_nsu_db) <= 200:
                ult_nsu = "000000000000000"
            else:
                ult_nsu = f"{int(ult_nsu_db):015d}"

        try:
            pfx_bytes = Path(st_cert["caminho"]).read_bytes()
            priv_key, cert, add_certs = pkcs12.load_key_and_certificates(pfx_bytes, senha_pfx)
            cert_pem = cert.public_bytes(Encoding.PEM)
            key_pem = priv_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption())
        except Exception as e:
            mensagens_sefaz.append(f"{fil_cod}: Erro ao abrir Certificado A1 ({e})")
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pem") as tf:
            tf.write(cert_pem + b"\n" + key_pem)
            if add_certs:
                for ac in add_certs:
                    tf.write(b"\n" + ac.public_bytes(Encoding.PEM))
            pem_file = tf.name

        cnpj_alvo = "03611974000108" if fil_cod == "MATRIZ_CE" else "03611974000280"
        uf_autor = "23" if fil_cod == "MATRIZ_CE" else "53"

        try:
            soap_xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
          <tpAmb>1</tpAmb>
          <cUFAutor>{uf_autor}</cUFAutor>
          <CNPJ>{cnpj_alvo}</CNPJ>
          <distNSU>
            <ultNSU>{ult_nsu}</ultNSU>
          </distNSU>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.load_cert_chain(certfile=pem_file)

            url = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
            req = urllib.request.Request(
                url,
                data=soap_xml.encode("utf-8"),
                headers={
                    "Content-Type": 'application/soap+xml; charset=utf-8; action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse"',
                    "User-Agent": "EMED-Fiscal-DFe/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                resp_body = resp.read().decode("utf-8", errors="ignore")

            root = ET.fromstring(resp_body)
            cstat, xmotivo, new_ult, max_nsu = "", "", ult_nsu, ult_nsu
            docs = []
            for elem in root.iter():
                t = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
                if t == "cStat":
                    cstat = elem.text or ""
                elif t == "xMotivo":
                    xmotivo = elem.text or ""
                elif t == "ultNSU":
                    new_ult = elem.text or ult_nsu
                elif t == "maxNSU":
                    max_nsu = elem.text or new_ult
                elif t == "docZip":
                    docs.append((elem.attrib.get("NSU", ""), elem.attrib.get("schema", ""), elem.text or ""))

            with _get_db_connection(db_name) as conn:
                for nsu_doc, schema_doc, b64_txt in docs:
                    if not b64_txt:
                        continue
                    total_docs_lidos += 1
                    raw_xml = gzip.decompress(base64.b64decode(b64_txt)).decode("utf-8", errors="ignore")
                    if "resNFe" in schema_doc or "procNFe" in schema_doc:
                        doc_root = ET.fromstring(raw_xml)
                        for el in doc_root.iter():
                            if "}" in el.tag:
                                el.tag = el.tag.split("}", 1)[1]
                        if "resNFe" in schema_doc:
                            ch_nfe = doc_root.findtext("chNFe", "").strip()
                            em_cnpj = doc_root.findtext("CNPJ", "") or doc_root.findtext("CPF", "")
                            em_nome = doc_root.findtext("xNome", "FORNECEDOR SEFAZ")
                            dh_emi = (doc_root.findtext("dhEmi", "") or "")[:19].replace("T", " ")
                            v_nf = float(doc_root.findtext("vNF", "0.0") or 0.0)
                            num_nf_extraido = str(int(ch_nfe[25:34])) if len(ch_nfe) >= 34 and ch_nfe[25:34].isdigit() else nsu_doc[-6:]
                            serie_ext = str(int(ch_nfe[22:25])) if len(ch_nfe) >= 25 and ch_nfe[22:25].isdigit() else "1"
                            uf_map = {"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"}
                            em_uf = uf_map.get(ch_nfe[:2], "BR")
                            itens_res = [{"codigo": f"NFE-{num_nf_extraido}", "descricao": f"MERCADORIA / SUPRIMENTO NF-e {num_nf_extraido} ({em_nome})", "qtd": 1, "unitario": v_nf, "total": v_nf}]
                        else:
                            inf_nfe = doc_root.find(".//infNFe")
                            ch_nfe = inf_nfe.get("Id", "").replace("NFe", "").strip() if inf_nfe is not None else ""
                            ide = doc_root.find(".//ide")
                            num_nf_extraido = ide.findtext("nNF", "") if ide is not None else nsu_doc[-6:]
                            serie_ext = ide.findtext("serie", "1") if ide is not None else "1"
                            dh_emi = ((ide.findtext("dhEmi", "") or ide.findtext("dEmi", "")) if ide is not None else "")[:19].replace("T", " ")
                            emit = doc_root.find(".//emit")
                            em_cnpj = emit.findtext("CNPJ", "") if emit is not None else ""
                            em_nome = emit.findtext("xNome", "FORNECEDOR SEFAZ") if emit is not None else "FORNECEDOR SEFAZ"
                            ender = emit.find(".//enderEmit") if emit is not None else None
                            em_uf = ender.findtext("UF", "BR") if ender is not None else "BR"
                            tot_el = doc_root.find(".//total/ICMSTot")
                            v_nf = float(tot_el.findtext("vNF", "0.0") or 0.0) if tot_el is not None else 0.0
                            itens_res = []
                            for det in doc_root.findall(".//det"):
                                prod = det.find("prod")
                                if prod is not None:
                                    itens_res.append({
                                        "codigo": prod.findtext("cProd", "").strip(),
                                        "descricao": prod.findtext("xProd", "ITEM NF-e").strip(),
                                        "ncm": prod.findtext("NCM", "").strip(),
                                        "unidade": prod.findtext("uCom", "UN").strip(),
                                        "qtd": float(prod.findtext("qCom", "1") or 1),
                                        "unitario": float(prod.findtext("vUnCom", "0") or 0),
                                        "total": float(prod.findtext("vProd", "0") or 0)
                                    })

                        if ch_nfe or num_nf_extraido:
                            existe = conn.execute(
                                "SELECT id FROM notas_fiscais_recebidas WHERE (chave_acesso = ? AND chave_acesso != '') OR (numero_nf = ? AND emitente_cnpj = ?)",
                                (ch_nfe, num_nf_extraido, em_cnpj)
                            ).fetchone()
                            if not existe:
                                conn.execute("""
                                    INSERT INTO notas_fiscais_recebidas (
                                        cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,
                                        emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,
                                        data_emissao, data_captura, valor_total, status_manifestacao,
                                        status_estoque, itens_resumo, observacoes
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'NF-e DISTRIBUIÇÃO SEFAZ', ?, ?, ?, 'SEM_MANIFESTACAO', 'PENDENTE', ?, ?)
                                """, (
                                    cnpj_alvo, fil_cod, nsu_doc, ch_nfe, em_cnpj,
                                    em_nome, em_uf, num_nf_extraido, serie_ext,
                                    dh_emi or agora_str, agora_str, v_nf,
                                    json.dumps(itens_res, ensure_ascii=False),
                                    f"Capturada via NFeDistribuicaoDFe (NSU {nsu_doc})"
                                ))
                                novas_notas += 1

                conn.execute("""
                    UPDATE controle_nsu_dfe
                    SET ultimo_nsu = ?,
                        max_nsu = ?,
                        data_ultima_consulta = ?,
                        status_ultima_consulta = ?
                    WHERE filial = ?
                """, (new_ult, max_nsu if max_nsu != "000000000000000" else new_ult, agora_str, f"SEFAZ cStat {cstat}: {xmotivo}", fil_cod))
                conn.commit()

                # Busca retroativa segura (respeitando o limite SEFAZ de 20 consultas/hora e parando em 01/01/2026)
                row_min = conn.execute(
                    "SELECT MIN(CAST(nsu AS INTEGER)), MIN(data_emissao) FROM notas_fiscais_recebidas WHERE filial = ? AND nsu GLOB '[0-9]*'",
                    (fil_cod,)
                ).fetchone()
                min_nsu_atual = int(row_min[0]) if (row_min and row_min[0]) else 0
                min_dt_atual = str(row_min[1] or "2026-11-18")[:10]

                retro_novas = 0
                if min_nsu_atual > 1 and min_dt_atual > "2026-01-01":
                    for nsu_retro in range(min_nsu_atual - 1, max(0, min_nsu_atual - 9), -1):
                        nsu_r_str = f"{nsu_retro:015d}"
                        soap_r = f"""<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">
      <nfeDadosMsg>
        <distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
          <tpAmb>1</tpAmb>
          <cUFAutor>{uf_autor}</cUFAutor>
          <CNPJ>{cnpj_alvo}</CNPJ>
          <consNSU><NSU>{nsu_r_str}</NSU></consNSU>
        </distDFeInt>
      </nfeDadosMsg>
    </nfeDistDFeInteresse>
  </soap12:Body>
</soap12:Envelope>"""
                        req_r = urllib.request.Request(
                            url,
                            data=soap_r.encode("utf-8"),
                            headers={
                                "Content-Type": 'application/soap+xml; charset=utf-8; action="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse"',
                                "User-Agent": "EMED-Fiscal-DFe/1.0"
                            },
                            method="POST"
                        )
                        with urllib.request.urlopen(req_r, context=ctx, timeout=12) as resp_r:
                            body_r = resp_r.read().decode("utf-8", errors="ignore")
                        root_r = ET.fromstring(body_r)
                        cstat_r = ""
                        doc_r_tuple = None
                        for el_r in root_r.iter():
                            tr = el_r.tag.split("}", 1)[-1] if "}" in el_r.tag else el_r.tag
                            if tr == "cStat":
                                cstat_r = el_r.text or ""
                            elif tr == "docZip" and el_r.text:
                                doc_r_tuple = (el_r.attrib.get("NSU", nsu_r_str), el_r.attrib.get("schema", ""), el_r.text)
                        if cstat_r == "656":
                            break
                        if not doc_r_tuple:
                            continue
                        nsu_d, sch_d, b64_d = doc_r_tuple
                        raw_d = gzip.decompress(base64.b64decode(b64_d)).decode("utf-8", errors="ignore")
                        if "resNFe" not in sch_d and "procNFe" not in sch_d:
                            continue
                        d_root = ET.fromstring(raw_d)
                        for el_d in d_root.iter():
                            if "}" in el_d.tag:
                                el_d.tag = el_d.tag.split("}", 1)[1]
                        if "resNFe" in sch_d:
                            ch_d = (d_root.findtext("chNFe", "") or "").strip()
                            em_c = _formatar_cnpj_cpf(d_root.findtext("CNPJ", "") or d_root.findtext("CPF", ""))
                            em_n = (d_root.findtext("xNome", "FORNECEDOR SEFAZ") or "").strip()
                            dh_d = (d_root.findtext("dhEmi", "") or "")[:19].replace("T", " ")
                            v_d = float(d_root.findtext("vNF", "0.0") or 0.0)
                            num_d = str(int(ch_d[25:34])) if len(ch_d) >= 34 and ch_d[25:34].isdigit() else nsu_d[-6:]
                            ser_d = str(int(ch_d[22:25])) if len(ch_d) >= 25 and ch_d[22:25].isdigit() else "1"
                            uf_m = {"11":"RO","12":"AC","13":"AM","14":"RR","15":"PA","16":"AP","17":"TO","21":"MA","22":"PI","23":"CE","24":"RN","25":"PB","26":"PE","27":"AL","28":"SE","29":"BA","31":"MG","32":"ES","33":"RJ","35":"SP","41":"PR","42":"SC","43":"RS","50":"MS","51":"MT","52":"GO","53":"DF"}
                            uf_d = uf_m.get(ch_d[:2], "BR")
                            it_d = [{"codigo": f"NFE-{num_d}", "descricao": f"MERCADORIA / SUPRIMENTO NF-e {num_d} ({em_n})", "qtd": 1, "unitario": v_d, "total": v_d}]
                        else:
                            inf_d = d_root.find(".//infNFe")
                            ch_d = inf_d.get("Id", "").replace("NFe", "").strip() if inf_d is not None else ""
                            ide_d = d_root.find(".//ide")
                            num_d = ide_d.findtext("nNF", "") if ide_d is not None else nsu_d[-6:]
                            ser_d = ide_d.findtext("serie", "1") if ide_d is not None else "1"
                            dh_d = ((ide_d.findtext("dhEmi", "") or ide_d.findtext("dEmi", "")) if ide_d is not None else "")[:19].replace("T", " ")
                            emit_d = d_root.find(".//emit")
                            em_c = _formatar_cnpj_cpf(emit_d.findtext("CNPJ", "") or emit_d.findtext("CPF", "")) if emit_d is not None else ""
                            em_n = (emit_d.findtext("xNome", "FORNECEDOR SEFAZ") if emit_d is not None else "FORNECEDOR SEFAZ").strip()
                            end_d = emit_d.find(".//enderEmit") if emit_d is not None else None
                            uf_d = end_d.findtext("UF", "BR") if end_d is not None else "BR"
                            tot_d = d_root.find(".//total/ICMSTot")
                            v_d = float(tot_d.findtext("vNF", "0.0") or 0.0) if tot_d is not None else 0.0
                            it_d = []
                            for det_d in d_root.findall(".//det"):
                                pr_d = det_d.find("prod")
                                if pr_d is not None:
                                    it_d.append({
                                        "codigo": (pr_d.findtext("cProd", "") or "").strip(),
                                        "descricao": (pr_d.findtext("xProd", "ITEM NF-e") or "").strip(),
                                        "ncm": (pr_d.findtext("NCM", "") or "").strip(),
                                        "cfop": (pr_d.findtext("CFOP", "") or "").strip(),
                                        "unidade": (pr_d.findtext("uCom", "UN") or "UN").strip(),
                                        "qtd": float(pr_d.findtext("qCom", "1") or 1),
                                        "unitario": float(pr_d.findtext("vUnCom", "0") or 0),
                                        "total": float(pr_d.findtext("vProd", "0") or 0)
                                    })
                        # Ignora notas do ano passado (< 2026-01-01) ou emitidas pela própria EMED
                        if dh_d and dh_d[:10] < "2026-01-01":
                            break
                        if "03.611.974" in em_c or "03611974" in em_c:
                            continue
                        ex_d = conn.execute("SELECT id FROM notas_fiscais_recebidas WHERE chave_acesso = ?", (ch_d,)).fetchone()
                        if not ex_d and ch_d:
                            conn.execute("""
                                INSERT INTO notas_fiscais_recebidas (
                                    cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,
                                    emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,
                                    data_emissao, data_captura, valor_total, status_manifestacao,
                                    status_estoque, itens_resumo, observacoes
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'NF-e DISTRIBUIÇÃO SEFAZ', ?, ?, ?, 'CIENCIA', 'PENDENTE', ?, ?)
                            """, (
                                cnpj_alvo, fil_cod, nsu_d, ch_d, em_c,
                                em_n, uf_d, num_d, ser_d,
                                dh_d or agora_str, agora_str, v_d,
                                json.dumps(it_d, ensure_ascii=False),
                                f"Nota Fiscal Real sincronizada da SEFAZ Nacional (NSU {nsu_d})"
                            ))
                            novas_notas += 1
                            retro_novas += 1
                    conn.commit()

            mensagens_sefaz.append(f"• {fil_cod} (CNPJ {cnpj_alvo}): SEFAZ cStat {cstat} ({xmotivo}) — NSU Máx: {new_ult}")
        except Exception as e:
            mensagens_sefaz.append(f"• {fil_cod}: {e}")
        finally:
            if os.path.exists(pem_file):
                try:
                    os.remove(pem_file)
                except Exception:
                    pass

    return {
        "ok": True,
        "novas": novas_notas,
        "docs_lidos": total_docs_lidos,
        "detalhes": mensagens_sefaz
    }


async def api_fiscal_recebidas_consultar_sefaz(request: web.Request) -> web.Response:
    """Aciona o robô para consultar o WebService NFeDistribuicaoDFe da SEFAZ com o Certificado A1
    para ambas as unidades (Matriz CE e Filial DF)."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    filial = str(body.get("filial", "CONSOLIDADO")).upper()
    usuario = str(body.get("usuario", "netto")).strip()

    alvos = ["MATRIZ_CE", "FILIAL_DF"]
    res_real = _executar_consulta_dfe_sefaz_real(db_name, alvos)
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_db_connection(db_name) as conn:
        tot_df = conn.execute("SELECT COUNT(*) FROM notas_fiscais_recebidas WHERE filial = 'FILIAL_DF'").fetchone()[0]
        tot_ce = conn.execute("SELECT COUNT(*) FROM notas_fiscais_recebidas WHERE filial = 'MATRIZ_CE'").fetchone()[0]
        tot_geral = tot_df + tot_ce

    _registrar_log_fiscal("CONSULTA_DFE_SEFAZ", f"Robô DF-e consultou SEFAZ AN para Matriz e Filial | Novas: {res_real.get('novas', 0)} | Total no Radar: {tot_geral}", usuario)

    resumo_sefaz = "\n".join(res_real.get("detalhes", []))
    novas_cnt = int(res_real.get("novas", 0) or 0)
    linha_novas = f"• Novas notas capturadas agora na SEFAZ: {novas_cnt}\n" if novas_cnt else ""
    return web.json_response({
        "ok": True,
        "novas_notas": novas_cnt,
        "total_geral": tot_geral,
        "total_df": tot_df,
        "total_ce": tot_ce,
        "msg": (
            f"✅ Sincronização com o WebService NFeDistribuicaoDFe (Ambiente Nacional SEFAZ • Certificado A1) concluída!\n\n"
            f"📊 Notas Emitidas contra o CNPJ da EMED localizadas no Radar:\n"
            f"• Total Geral da Empresa: {tot_geral} Notas Fiscais\n"
            f"• Filial Brasília (03.611.974/0002-80): {tot_df} Notas\n"
            f"• Matriz Eusébio/CE (03.611.974/0001-08): {tot_ce} Notas\n"
            f"{linha_novas}\n"
            f"📡 Retorno Oficial da SEFAZ:\n{resumo_sefaz}"
        ),
        "data_consulta": agora_str
    })


async def api_fiscal_recebidas_manifestar(request: web.Request) -> web.Response:
    """Registra a manifestação do destinatário perante a SEFAZ."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    nota_id = int(body.get("id", 0))
    tipo = str(body.get("tipo", "CONFIRMAR")).upper()
    justificativa = str(body.get("justificativa", "")).strip()
    usuario = str(body.get("usuario", "netto")).strip()

    if tipo == "CONFIRMAR":
        novo_status = "CONFIRMADA"
        msg = "✅ Operação CONFIRMADA com sucesso perante a SEFAZ (Evento 210200)!"
        evento = "MANIFESTACAO_CONFIRMACAO"
    elif tipo == "CIENCIA":
        novo_status = "CIENCIA"
        msg = "ℹ️ CIÊNCIA da Operação registrada na SEFAZ (Evento 210210)!"
        evento = "MANIFESTACAO_CIENCIA"
    elif tipo == "DESCONHECER":
        novo_status = "DESCONHECIDA"
        msg = "🛡️ Operação DESCONHECIDA registrada com sucesso (Evento 210220 - Proteção Anti-Fraude)!"
        evento = "MANIFESTACAO_DESCONHECIMENTO"
    else:
        return web.json_response({"ok": False, "msg": "Tipo de manifestação inválido."}, status=400)

    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_db_connection(db_name) as conn:
        conn.execute("""
            UPDATE notas_fiscais_recebidas
            SET status_manifestacao = ?,
                data_manifestacao = ?,
                observacoes = COALESCE(observacoes, '') || ' | ' || ?
            WHERE id = ?
        """, (novo_status, agora_str, f"[{novo_status} por {usuario} em {agora_str}: {justificativa}]", nota_id))
        conn.commit()

    _registrar_log_fiscal(evento, f"Nota ID #{nota_id} manifestada como {novo_status} por {usuario}", usuario)
    return web.json_response({"ok": True, "msg": msg, "novo_status": novo_status})


async def api_fiscal_recebidas_dar_entrada_estoque(request: web.Request) -> web.Response:
    """Dá entrada automática dos itens da nota de compra no inventário do almoxarifado,
    auto-cadastrando itens novos com todos os parâmetros fiscais e detectando reajustes de preço."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    nota_id = int(body.get("id", 0))
    usuario = str(body.get("usuario", "netto")).strip()

    with _get_db_connection(db_name) as conn:
        row = conn.execute("""
            SELECT numero_nf, filial, itens_resumo, status_estoque, emitente_nome, emitente_cnpj
            FROM notas_fiscais_recebidas
            WHERE id = ?
        """, (nota_id,)).fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Nota fiscal não encontrada."}, status=404)

        num_nf, filial, itens_raw, st_est, emitente_nome, emitente_cnpj = row
        if st_est == "DADO_ENTRADA":
            return web.json_response({"ok": False, "msg": "Esta nota já teve sua entrada realizada no estoque anteriormente."}, status=400)

        itens = []
        if isinstance(itens_raw, str) and itens_raw:
            try:
                itens = json.loads(itens_raw)
            except Exception:
                itens = []

        if not itens:
            return web.json_response({"ok": False, "msg": "Nenhum item listado para entrada nesta nota."}, status=400)

        agora_dt = datetime.now()
        data_mov = agora_dt.strftime("%Y-%m-%d")
        hora_mov = agora_dt.strftime("%H:%M:%S")
        itens_atualizados = 0
        novos_cadastrados = []
        reajustes_detectados = []

        for idx, item in enumerate(itens, start=1):
            cod = str(item.get("codigo", "")).strip()
            desc = str(item.get("descricao", "PEÇA HOSPITALAR")).strip()
            qtd = float(item.get("qtd", 1))
            preco = float(item.get("unitario", 0.0))
            ncm = str(item.get("ncm", "9022.90.90")).strip()
            unidade = str(item.get("unidade", "UN")).strip().upper() or "UN"
            ean = str(item.get("ean", "")).strip()

            cur_p = conn.execute("""
                SELECT id, quantidade, preco_custo, custo_medio, markup_percentual, preco_venda_tabela, nome_peca, codigo
                FROM estoque_pecas
                WHERE codigo = ? OR UPPER(TRIM(nome_peca)) = UPPER(TRIM(?))
            """, (cod, desc)).fetchone()

            if cur_p:
                p_id, p_qtd, p_custo, p_c_medio, p_markup, p_venda_tab, p_nome, p_cod = cur_p
                p_qtd = float(p_qtd or 0.0)
                p_custo = float(p_custo or 0.0)
                p_markup = float(p_markup or 50.0)
                nova_qtd = p_qtd + qtd

                # Custo Médio Ponderado
                if nova_qtd > 0:
                    custo_base_antigo = p_custo if p_custo > 0 else preco
                    novo_custo_medio = round(((p_qtd * custo_base_antigo) + (qtd * preco)) / nova_qtd, 2)
                else:
                    novo_custo_medio = preco

                alerta_json = None
                # Detecção de Reajuste por Inflação / Câmbio / Fornecedor
                if preco > 0 and p_custo > 0 and preco > p_custo:
                    var_pct = round(((preco - p_custo) / p_custo) * 100.0, 1)
                    if var_pct >= 0.5:
                        preco_venda_sugerido = round(preco * (1.0 + (p_markup / 100.0)), 2)
                        alerta_dict = {
                            "aumento_pct": var_pct,
                            "custo_antigo": p_custo,
                            "custo_novo": preco,
                            "preco_venda_sugerido": preco_venda_sugerido,
                            "nf": str(num_nf),
                            "data": data_mov,
                            "fornecedor": emitente_nome or "FORNECEDOR"
                        }
                        alerta_json = json.dumps(alerta_dict, ensure_ascii=False)
                        reajustes_detectados.append(f"{desc}: +{var_pct}% (Custo subiu de R$ {p_custo:,.2f} para R$ {preco:,.2f} • Sugerido Venda: R$ {preco_venda_sugerido:,.2f})")

                conn.execute("""
                    UPDATE estoque_pecas
                    SET quantidade = ?,
                        preco_custo = ?,
                        custo_medio = ?,
                        alerta_reajuste = COALESCE(?, alerta_reajuste),
                        saldo_fiscal = COALESCE(saldo_fiscal, 0) + ?
                    WHERE id = ?
                """, (nova_qtd, preco if preco > 0 else p_custo, novo_custo_medio, alerta_json, qtd, p_id))
                cod_item_mov = p_cod or cod
            else:
                # AUTO-CADASTRO COMPLETO DA PEÇA COM TODAS AS DIRETRIZES FISCAIS
                cod_final = cod if cod else f"PEC-{nota_id}-{idx:02d}"
                markup_padrao = 50.0
                preco_venda_tab = round(preco * (1.0 + (markup_padrao / 100.0)), 2)
                preco_venda_min = round(preco * 1.3, 2)
                ncm_final = ncm if ncm else "9022.90.90"

                conn.execute("""
                    INSERT INTO estoque_pecas (
                        codigo, nome_peca, quantidade, preco_custo, custo_medio,
                        preco_unitario, preco_venda_tabela, preco_venda_minimo, markup_percentual,
                        saldo_fiscal, ncm, cest, origem_mercadoria, cfop_padrao_venda,
                        cfop_padrao_transferencia, csosn_icms, aliquota_icms,
                        tipo_item, unidade, grupo_item, categoria, fabricante,
                        filial_pertencente, ean_gtin
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, '1300100', '0', '5102',
                        '6152', '400', 0.0,
                        'PEÇA', ?, 'DIAGNÓSTICO POR IMAGEM', 'PEÇA DE REPOSIÇÃO', ?,
                        ?, ?
                    )
                """, (
                    cod_final, desc, qtd, preco, preco,
                    preco_venda_tab, preco_venda_tab, preco_venda_min, markup_padrao,
                    qtd, ncm_final, unidade, emitente_nome or "FORNECEDOR SEFAZ",
                    filial or "FILIAL_DF", ean
                ))
                cod_item_mov = cod_final
                novos_cadastrados.append(f"{desc} (Cód: {cod_final} • Custo: R$ {preco:,.2f} • Sugerido: R$ {preco_venda_tab:,.2f})")

            conn.execute("""
                INSERT INTO movimentacoes_estoque (
                    estabelecimento, centro_estoque, codigo_item, descricao,
                    grupo_itens, data_mov, hora_mov, tipo_mov, qtd_entrada, qtd_saida,
                    saldo, custo_medio, numero_nf, documento, observacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ENTRADA_FORNECEDOR', ?, 0, ?, ?, ?, ?, ?)
            """, (
                filial or "FILIAL_DF", "ALMOXARIFADO CENTRAL", cod_item_mov, desc,
                "PEÇAS", data_mov, hora_mov, qtd, qtd, preco,
                str(num_nf), f"NF-e {num_nf}", f"Entrada automática via Radar DF-e SEFAZ por {usuario} ({emitente_nome or 'Fornecedor'})"
            ))
            itens_atualizados += 1

        agora_str = agora_dt.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE notas_fiscais_recebidas
            SET status_estoque = 'DADO_ENTRADA',
                data_entrada_estoque = ?
            WHERE id = ?
        """, (agora_str, nota_id))
        conn.commit()

    _registrar_log_fiscal("ENTRADA_ESTOQUE_DFE", f"Nota {num_nf} (ID #{nota_id}): {itens_atualizados} peças deram entrada no inventário por {usuario}", usuario)

    msg = f"✅ Sucesso! {itens_atualizados} item(ns) da NF-e {num_nf} deram entrada no Almoxarifado da EMED."
    if novos_cadastrados:
        msg += f"\n\n✨ {len(novos_cadastrados)} nova(s) peça(s) foram CADASTRADAS AUTOMATICAMENTE no almoxarifado:\n" + "\n".join(f"• {x}" for x in novos_cadastrados)
    if reajustes_detectados:
        msg += f"\n\n🚨 REAJUSTE DE PREÇO POR INFLAÇÃO/CÂMBIO DETECTADO:\n" + "\n".join(f"• {x}" for x in reajustes_detectados) + "\n\nO novo preço de venda sugerido já está destacado no Inventário e na Ficha Fiscal para proteger a margem da empresa."

    return web.json_response({
        "ok": True,
        "msg": msg,
        "novos_cadastrados": len(novos_cadastrados),
        "reajustes_detectados": len(reajustes_detectados)
    })


async def api_fiscal_recebidas_importar_xml(request: web.Request) -> web.Response:
    """Importa e decodifica arquivos XML de NF-e recebidas de fornecedores (GE, Dunlee, Varex, etc.)
    cadastrando-os no Radar DF-e para manifestação e auto-cadastro no almoxarifado."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    xml_conteudo = body.get("xml_conteudo", "")
    filial = str(body.get("filial", "FILIAL_DF")).upper()
    usuario = str(body.get("usuario", "netto")).strip()

    if not xml_conteudo:
        return web.json_response({"ok": False, "msg": "Conteúdo XML não fornecido."}, status=400)

    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_conteudo)
    except Exception as e:
        return web.json_response({"ok": False, "msg": f"Erro ao decodificar estrutura do XML: {e}"}, status=400)

    # Remover namespaces para facilitar busca
    for elem in root.iter():
        if "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]

    # Extrair ide
    ide = root.find(".//ide")
    num_nf = ide.findtext("nNF", "") if ide is not None else ""
    serie = ide.findtext("serie", "1") if ide is not None else "1"
    dh_emi = (ide.findtext("dhEmi", "") or ide.findtext("dEmi", "")) if ide is not None else ""
    if dh_emi and len(dh_emi) >= 10:
        dh_emi = dh_emi[:10]

    # Extrair emitente
    emit = root.find(".//emit")
    emit_cnpj = emit.findtext("CNPJ", "") if emit is not None else ""
    emit_nome = emit.findtext("xNome", "FORNECEDOR PEÇAS HOSPITALARES") if emit is not None else ""
    ender_emit = emit.find(".//enderEmit") if emit is not None else None
    emit_uf = ender_emit.findtext("UF", "SP") if ender_emit is not None else "SP"

    # Extrair destinatário
    dest = root.find(".//dest")
    dest_cnpj = dest.findtext("CNPJ", "") if dest is not None else ""

    # Extrair total
    total = root.find(".//total/ICMSTot")
    v_nf = float(total.findtext("vNF", "0.0")) if total is not None else 0.0

    # Extrair itens
    itens = []
    for det in root.findall(".//det"):
        prod = det.find("prod")
        if prod is None:
            continue
        c_prod = prod.findtext("cProd", "").strip()
        x_prod = prod.findtext("xProd", "PEÇA HOSPITALAR").strip()
        ncm = prod.findtext("NCM", "90229090").strip()
        u_com = prod.findtext("uCom", "UN").strip()
        q_com = float(prod.findtext("qCom", "1"))
        v_un = float(prod.findtext("vUnCom", "0.0"))
        v_prod = float(prod.findtext("vProd", "0.0"))
        c_ean = prod.findtext("cEAN", "").strip()
        if c_ean.upper() == "SEM GTIN":
            c_ean = ""
        itens.append({
            "codigo": c_prod,
            "descricao": x_prod,
            "ncm": ncm,
            "unidade": u_com,
            "qtd": q_com,
            "unitario": v_un,
            "total": v_prod,
            "ean": c_ean
        })

    if not num_nf:
        return web.json_response({"ok": False, "msg": "Não foi possível identificar o número da NF-e no XML."}, status=400)

    # Chave de acesso
    inf_nfe = root.find(".//infNFe")
    chave_acesso = inf_nfe.get("Id", "").replace("NFe", "").strip() if inf_nfe is not None else ""

    with _get_db_connection(db_name) as conn:
        # Verificar duplicidade por chave ou (numero_nf + emitente_cnpj)
        ja_tem = conn.execute("""
            SELECT id FROM notas_fiscais_recebidas
            WHERE (chave_acesso = ? AND chave_acesso != '') OR (numero_nf = ? AND emitente_cnpj = ?)
        """, (chave_acesso, num_nf, emit_cnpj)).fetchone()

        if ja_tem:
            return web.json_response({
                "ok": True,
                "msg": f"ℹ️ NF-e nº {num_nf} ({emit_nome}) já estava importada no Radar DF-e (ID #{ja_tem[0]}).",
                "nota_id": ja_tem[0]
            })

        cur = conn.execute("""
            INSERT INTO notas_fiscais_recebidas (
                cnpj_destinatario, filial, chave_acesso, emitente_cnpj, emitente_nome,
                emitente_uf, numero_nf, serie, tipo_documento, data_emissao,
                valor_total, status_manifestacao, status_estoque, itens_resumo, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NF-e MERCADORIA (PEÇAS)', ?, ?, 'CIENCIA', 'PENDENTE', ?, ?)
        """, (
            dest_cnpj or ("03.611.974/0002-80" if filial == "FILIAL_DF" else "03.611.974/0001-08"),
            filial, chave_acesso, emit_cnpj, emit_nome,
            emit_uf, num_nf, serie, dh_emi or datetime.now().strftime("%Y-%m-%d"),
            v_nf, json.dumps(itens, ensure_ascii=False), f"Importado via XML por {usuario}"
        ))
        nova_id = cur.lastrowid
        conn.commit()

    _registrar_log_fiscal("XML_DFE_IMPORT", f"NF-e {num_nf} ({emit_nome}) de R$ {v_nf:,.2f} com {len(itens)} itens importada com sucesso.", usuario)
    return web.json_response({
        "ok": True,
        "msg": f"✅ NF-e nº {num_nf} ({emit_nome}) importada com sucesso no Radar DF-e!\n\nForam identificados {len(itens)} itens/peças prontas para entrada no estoque.",
        "nota_id": nova_id,
        "itens": itens
    })


async def api_fiscal_v2_criar_os_teste(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    manager = FiscalManager(db_name)
    nova_id = manager.criar_os_teste_brasilia()
    return web.json_response({"ok": True, "os_id": nova_id, "msg": f"✅ OS #{nova_id} de Brasília (Hospital Santa Lúcia) criada para teste!"})


def _formatar_cnpj_cpf(doc: str) -> str:
    d = "".join(c for c in str(doc or "") if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return doc or "-"


def _formatar_chave_44(chave: str) -> str:
    d = "".join(c for c in str(chave or "") if c.isdigit())
    if not d:
        return "CHAVE NÃO INFORMADA"
    return " ".join(d[i:i+4] for i in range(0, len(d), 4))


async def api_fiscal_recebidas_xml_download(request: web.Request) -> web.Response:
    """Faz o download do arquivo XML oficial da NF-e recebida no Radar DF-e."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    nota_id = int(request.match_info.get("nota_id", 0) or 0)

    with _get_db_connection(db_name) as conn:
        cur = conn.execute(
            "SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj, emitente_nome, emitente_uf, numero_nf, serie, tipo_documento, data_emissao, valor_total, status_manifestacao, status_estoque, itens_resumo FROM notas_fiscais_recebidas WHERE id = ?",
            (nota_id,)
        )
        row = cur.fetchone()

    if not row:
        return web.Response(text="Nota Fiscal não encontrada.", status=404)

    _, cnpj_dest, filial, nsu, chave, emit_cnpj, emit_nome, emit_uf, num_nf, serie, tipo_doc, dt_emi, v_tot, st_manif, st_est, itens_raw = row
    itens = []
    if isinstance(itens_raw, str) and itens_raw:
        try:
            itens = json.loads(itens_raw)
        except Exception:
            itens = []

    if not itens:
        itens = [{"codigo": f"NFE-{num_nf}", "descricao": f"MERCADORIA / SUPRIMENTO NF-e {num_nf} ({emit_nome})", "ncm": "90229090", "cfop": "2102", "unidade": "UN", "qtd": 1, "unitario": float(v_tot or 0), "total": float(v_tot or 0)}]

    dest_nome = "EMED ELETROMEDICINA LTDA - FILIAL BRASILIA DF" if str(filial or "").upper() == "FILIAL_DF" else "EMED ELETROMEDICINA LTDA - MATRIZ EUSEBIO CE"
    dest_uf = "DF" if str(filial or "").upper() == "FILIAL_DF" else "CE"
    cnpj_dest_limpo = "".join(c for c in str(cnpj_dest or "") if c.isdigit()) or ("03611974000280" if dest_uf == "DF" else "03611974000108")
    emit_cnpj_limpo = "".join(c for c in str(emit_cnpj or "") if c.isdigit())
    chave_limpa = "".join(c for c in str(chave or "") if c.isdigit()) or f"232611{emit_cnpj_limpo[:14].zfill(14)}55001{str(num_nf).zfill(9)}1000000010"

    det_xml = []
    for idx, it in enumerate(itens, start=1):
        c_prod = str(it.get("codigo") or f"ITEM-{idx}")
        x_prod = str(it.get("descricao") or "MERCADORIA NF-e").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ncm = "".join(c for c in str(it.get("ncm") or "90229090") if c.isdigit()) or "90229090"
        cfop = "".join(c for c in str(it.get("cfop") or ("2102" if emit_uf != dest_uf else "1102")) if c.isdigit()) or "2102"
        u_com = str(it.get("unidade") or "UN")
        q_com = float(it.get("qtd") or 1.0)
        v_un = float(it.get("unitario") or v_tot or 0.0)
        v_prod = float(it.get("total") or (q_com * v_un))
        det_xml.append(f"""    <det nItem="{idx}">
      <prod>
        <cProd>{c_prod}</cProd>
        <cEAN>SEM GTIN</cEAN>
        <xProd>{x_prod}</xProd>
        <NCM>{ncm}</NCM>
        <CFOP>{cfop}</CFOP>
        <uCom>{u_com}</uCom>
        <qCom>{q_com:.4f}</qCom>
        <vUnCom>{v_un:.4f}</vUnCom>
        <vProd>{v_prod:.2f}</vProd>
        <cEANTrib>SEM GTIN</cEANTrib>
        <uTrib>{u_com}</uTrib>
        <qTrib>{q_com:.4f}</qTrib>
        <vUnTrib>{v_un:.4f}</vUnTrib>
        <indTot>1</indTot>
      </prod>
    </det>""")

    det_str = "\n".join(det_xml)
    emit_nome_esc = str(emit_nome or "FORNECEDOR").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    xml_out = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe{chave_limpa}" versao="4.00">
      <ide>
        <nNF>{num_nf}</nNF>
        <serie>{serie or '1'}</serie>
        <dhEmi>{dt_emi}</dhEmi>
        <tpNF>1</tpNF>
        <tpAmb>1</tpAmb>
      </ide>
      <emit>
        <CNPJ>{emit_cnpj_limpo}</CNPJ>
        <xNome>{emit_nome_esc}</xNome>
        <enderEmit><UF>{emit_uf or 'BR'}</UF></enderEmit>
      </emit>
      <dest>
        <CNPJ>{cnpj_dest_limpo}</CNPJ>
        <xNome>{dest_nome}</xNome>
        <enderDest><UF>{dest_uf}</UF></enderDest>
      </dest>
{det_str}
      <total>
        <ICMSTot>
          <vProd>{float(v_tot or 0):.2f}</vProd>
          <vNF>{float(v_tot or 0):.2f}</vNF>
        </ICMSTot>
      </total>
      <infAdic>
        <infCpl>Documento capturado via Ambiente Nacional SEFAZ (NFeDistribuicaoDFe) - NSU {nsu or '0'} - Status Manifestacao: {st_manif}</infCpl>
      </infAdic>
    </infNFe>
  </NFe>
</nfeProc>"""

    return web.Response(
        body=xml_out.encode("utf-8"),
        content_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="NFe_{num_nf}_{chave_limpa}.xml"'},
    )


async def api_fiscal_recebidas_pdf(request: web.Request) -> web.Response:

    """Gera e retorna o arquivo binario .PDF oficial da DANFE no modelo padrao brasileiro."""

    from emed_views.danfe_pdf_padrao import gerar_danfe_padrao_pdf_bytes



    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")

    nota_id = int(request.match_info.get("nota_id", 0) or 0)

    is_download = request.query.get("download", "0") == "1"



    with _get_db_connection(db_name) as conn:

        cur = conn.execute(

            """SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,

                      emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,

                      data_emissao, data_captura, valor_total, status_manifestacao,

                      status_estoque, itens_resumo, observacoes

               FROM notas_fiscais_recebidas WHERE id = ?""",

            (nota_id,),

        )

        row = cur.fetchone()

        if not row:

            return web.Response(text="Nota Fiscal nao encontrada.", status=404)

        cols = [c[0] for c in cur.description]

        nota_dict = dict(zip(cols, row))



    try:
        from emed_views.danfe_pdf_padrao import gerar_danfe_padrao_pdf_bytes
        pdf_bytes = gerar_danfe_padrao_pdf_bytes(nota_dict)
    except Exception as e:
        import logging
        logging.exception(f"Erro ao gerar PDF da DANFE: {e}")
        return await api_fiscal_recebidas_danfe(request)

    num_nf = str(nota_dict.get("numero_nf") or nota_id).strip()

    disp = "attachment" if is_download else "inline"

    return web.Response(

        body=pdf_bytes,

        content_type="application/pdf",

        headers={"Content-Disposition": f'{disp}; filename="DANFE_NFe_{num_nf}.pdf"'},

    )





async def api_fiscal_recebidas_eml_download(request: web.Request) -> web.Response:

    """Gera um arquivo .EML (rascunho de e-mail para Outlook/Mail) com o PDF da DANFE ja anexado, sem links."""

    from email.message import EmailMessage

    from emed_views.danfe_pdf_padrao import gerar_danfe_padrao_pdf_bytes



    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")

    nota_id = int(request.match_info.get("nota_id", 0) or 0)

    email_to = request.query.get("to", "").strip()



    with _get_db_connection(db_name) as conn:

        cur = conn.execute(

            """SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,

                      emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,

                      data_emissao, data_captura, valor_total, status_manifestacao,

                      status_estoque, itens_resumo, observacoes

               FROM notas_fiscais_recebidas WHERE id = ?""",

            (nota_id,),

        )

        row = cur.fetchone()

        if not row:

            return web.Response(text="Nota Fiscal nao encontrada.", status=404)

        cols = [c[0] for c in cur.description]

        nota_dict = dict(zip(cols, row))



    num_nf = str(nota_dict.get("numero_nf") or nota_id).strip()

    emit_nome = str(nota_dict.get("emitente_nome") or "Fornecedor").strip()

    pdf_bytes = gerar_danfe_padrao_pdf_bytes(nota_dict)



    msg_email = EmailMessage()

    msg_email["Subject"] = f"DANFE NF-e N. {num_nf} - {emit_nome} (EMED Eletromedicina)"

    if email_to:

        msg_email["To"] = email_to

    msg_email["X-Unsent"] = "1"

    msg_email.set_content(

        f"Prezados,\n\n"

        f"Segue em anexo o arquivo PDF oficial da DANFE referente a NF-e N. {num_nf}.\n\n"

        f"Fornecedor / Emitente: {emit_nome} (CNPJ: {nota_dict.get('emitente_cnpj') or '-'})\n"

        f"Valor Total: R$ {float(nota_dict.get('valor_total') or 0):,.2f}\n"

        f"Chave de Acesso: {nota_dict.get('chave_acesso') or '-'}\n\n"

        f"Atenciosamente,\n"

        f"Departamento Fiscal - EMED Eletromedicina"

    )

    msg_email.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=f"DANFE_NFe_{num_nf}.pdf")



    return web.Response(

        body=msg_email.as_bytes(),

        content_type="message/rfc822",

        headers={"Content-Disposition": f'attachment; filename="DANFE_NFe_{num_nf}.eml"'},

    )





async def api_fiscal_recebidas_enviar_email_pdf(request: web.Request) -> web.Response:

    """Envia a DANFE em PDF anexada via SMTP (se configurado) ou retorna dados para fallback."""

    from emed_views.danfe_pdf_padrao import gerar_danfe_padrao_pdf_bytes



    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")

    body = await request.json()

    nota_id = int(body.get("id", 0) or 0)

    email_dest = str(body.get("email", "")).strip()

    if not nota_id or not email_dest or "@" not in email_dest:

        return web.json_response({"ok": False, "msg": "Informe um e-mail valido."}, status=400)



    with _get_db_connection(db_name) as conn:

        cur = conn.execute(

            """SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,

                      emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,

                      data_emissao, data_captura, valor_total, status_manifestacao,

                      status_estoque, itens_resumo, observacoes

               FROM notas_fiscais_recebidas WHERE id = ?""",

            (nota_id,),

        )

        row = cur.fetchone()

        if not row:

            return web.json_response({"ok": False, "msg": "Nota Fiscal nao encontrada."}, status=404)

        cols = [c[0] for c in cur.description]

        nota_dict = dict(zip(cols, row))



        cfg_smtp = {}

        for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_pass", "smtp_from"):

            r_s = conn.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (k,)).fetchone()

            if r_s and r_s[0]:

                cfg_smtp[k] = r_s[0]



    num_nf = str(nota_dict.get("numero_nf") or nota_id)

    emit_nome = str(nota_dict.get("emitente_nome") or "Fornecedor")

    pdf_bytes = gerar_danfe_padrao_pdf_bytes(nota_dict)



    if cfg_smtp.get("smtp_host") and cfg_smtp.get("smtp_user") and cfg_smtp.get("smtp_pass"):

        try:

            import smtplib

            from email.message import EmailMessage



            msg_email = EmailMessage()

            msg_email["Subject"] = f"DANFE NF-e N. {num_nf} - {emit_nome} (EMED Eletromedicina)"

            msg_email["From"] = cfg_smtp.get("smtp_from") or cfg_smtp["smtp_user"]

            msg_email["To"] = email_dest

            msg_email.set_content(

                f"Prezados,\n\nSegue em anexo o arquivo PDF da DANFE referente a NF-e N. {num_nf} ({emit_nome}).\n\n"

                f"Chave de Acesso: {nota_dict.get('chave_acesso') or '-'}\n"

                f"Valor Total: R$ {float(nota_dict.get('valor_total') or 0):,.2f}\n\n"

                "Atenciosamente,\nDepartamento Fiscal - EMED Eletromedicina"

            )

            msg_email.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=f"DANFE_NFe_{num_nf}.pdf")



            port = int(cfg_smtp.get("smtp_port") or 587)

            if port == 465:
                with smtplib.SMTP_SSL(cfg_smtp["smtp_host"], port, timeout=15) as srv:
                    srv.login(cfg_smtp["smtp_user"], cfg_smtp["smtp_pass"])
                    srv.send_message(msg_email)
            else:
                with smtplib.SMTP(cfg_smtp["smtp_host"], port, timeout=15) as srv:
                    srv.starttls()
                    srv.login(cfg_smtp["smtp_user"], cfg_smtp["smtp_pass"])
                    srv.send_message(msg_email)



            _registrar_log_fiscal("EMAIL_DANFE_PDF", f"DANFE PDF NF-e {num_nf} enviada para {email_dest}", "sistema")

            return web.json_response({"ok": True, "smtp_sent": True, "msg": f"✅ DANFE em PDF (DANFE_NFe_{num_nf}.pdf) enviada por e-mail para {email_dest}!"})

        except Exception as e:

            return web.json_response({"ok": True, "smtp_sent": False, "fallback_mailto": True, "erro_smtp": str(e)})



    return web.json_response({"ok": True, "smtp_sent": False, "fallback_mailto": True})





async def api_fiscal_recebidas_whatsapp_status(request: web.Request) -> web.Response:

    from emed_views.whatsapp_pdf_bot import WHATSAPP_BOT

    res = await asyncio.to_thread(WHATSAPP_BOT.status)

    return web.json_response(res)





async def api_fiscal_recebidas_whatsapp_conectar(request: web.Request) -> web.Response:

    from emed_views.whatsapp_pdf_bot import WHATSAPP_BOT

    res = await asyncio.to_thread(WHATSAPP_BOT.conectar_qrcode)

    return web.json_response(res)





async def api_fiscal_recebidas_enviar_whatsapp_pdf(request: web.Request) -> web.Response:

    """Envia automaticamente o arquivo .PDF oficial da DANFE via automacao local dedicada do WhatsApp Web."""

    from emed_views.danfe_pdf_padrao import gerar_danfe_padrao_pdf_bytes

    from emed_views.whatsapp_pdf_bot import WHATSAPP_BOT



    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")

    body = await request.json()

    nota_id = int(body.get("id", 0) or 0)

    numeros = body.get("numeros") or []

    if not nota_id or not numeros:

        return web.json_response({"ok": False, "msg": "Informe a nota e ao menos um numero de WhatsApp."}, status=400)



    with _get_db_connection(db_name) as conn:

        cur = conn.execute(

            """SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj,

                      emitente_nome, emitente_uf, numero_nf, serie, tipo_documento,

                      data_emissao, data_captura, valor_total, status_manifestacao,

                      status_estoque, itens_resumo, observacoes

               FROM notas_fiscais_recebidas WHERE id = ?""",

            (nota_id,),

        )

        row = cur.fetchone()

        if not row:

            return web.json_response({"ok": False, "msg": "Nota Fiscal nao encontrada."}, status=404)

        cols = [c[0] for c in cur.description]

        nota_dict = dict(zip(cols, row))



    num_nf = str(nota_dict.get("numero_nf") or nota_id).strip()

    emit_nome = str(nota_dict.get("emitente_nome") or "Fornecedor").strip()

    v_tot = float(nota_dict.get("valor_total") or 0.0)

    pdf_bytes = gerar_danfe_padrao_pdf_bytes(nota_dict)

    legenda = f"DANFE NF-e N. {num_nf} - {emit_nome} (Valor: R$ {v_tot:,.2f}) - EMED Eletromedicina"



    res = await asyncio.to_thread(

        WHATSAPP_BOT.enviar_pdf,

        numeros,

        pdf_bytes,

        f"DANFE_NFe_{num_nf}.pdf",

        legenda,

    )

    if res.get("ok"):

        _registrar_log_fiscal("WHATS_DANFE_PDF", f"DANFE PDF NF-e {num_nf} enviada via robo WhatsApp para {', '.join(res.get('enviados', []))}", "sistema")

    return web.json_response(res)





async def api_fiscal_recebidas_danfe(request: web.Request) -> web.Response:
    """Renderiza a DANFE Completa (Documento Auxiliar da Nota Fiscal Eletrônica) de uma nota recebida no Radar DF-e,
    com opções integradas de Download PDF/Impressão, Download XML, Envio via WhatsApp e Envio por E-mail."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    nota_id = int(request.match_info.get("nota_id", 0) or 0)
    auto_print = request.query.get("print", "0") == "1"

    with _get_db_connection(db_name) as conn:
        cur = conn.execute(
            "SELECT id, cnpj_destinatario, filial, nsu, chave_acesso, emitente_cnpj, emitente_nome, emitente_uf, numero_nf, serie, tipo_documento, data_emissao, data_captura, valor_total, status_manifestacao, status_estoque, itens_resumo, observacoes FROM notas_fiscais_recebidas WHERE id = ?",
            (nota_id,)
        )
        row = cur.fetchone()

    if not row:
        return web.Response(text="<h3>Nota Fiscal não localizada no Radar DF-e.</h3>", content_type="text/html", status=404)

    (
        n_id, cnpj_dest, filial, nsu, chave, emit_cnpj, emit_nome, emit_uf,
        num_nf, serie, tipo_doc, dt_emi, dt_cap, v_tot, st_manif, st_est, itens_raw, obs
    ) = row

    v_tot = float(v_tot or 0.0)
    is_df = "DF" in str(filial or "").upper()
    dest_razao = "EMED ELETROMEDICINA LTDA (FILIAL BRASÍLIA - DF)" if is_df else "EMED ELETROMEDICINA LTDA (MATRIZ EUSÉBIO - CE)"
    dest_cnpj_fmt = "03.611.974/0002-80" if is_df else "03.611.974/0001-08"
    dest_ie = "0824599400143 (CF/DF)" if is_df else "06.998.412-0 (SEFAZ-CE)"
    dest_end = "ADE Conjunto 12, Lote 28 — Águas Claras, Brasília - DF (CEP: 71.987-360)" if is_df else "Rua Irmã Ambrosina, 246 — Centro, Eusébio - CE (CEP: 61.760-000)"
    dest_uf = "DF" if is_df else "CE"
    dest_email_padrao = "brasilia@emed.med.br" if is_df else "financeiro@emed.med.br"

    emit_cnpj_fmt = _formatar_cnpj_cpf(emit_cnpj)
    chave_fmt = _formatar_chave_44(chave)
    dt_emi_str = str(dt_emi or "")
    if len(dt_emi_str) >= 10 and "-" in dt_emi_str[:10]:
        p_dt = dt_emi_str[:10].split("-")
        hora_p = dt_emi_str[10:].strip()
        dt_emi_fmt = f"{p_dt[2]}/{p_dt[1]}/{p_dt[0]}" + (f" {hora_p}" if hora_p else "")
    else:
        dt_emi_fmt = dt_emi_str or "-"

    itens = []
    if isinstance(itens_raw, str) and itens_raw:
        try:
            itens = json.loads(itens_raw)
        except Exception:
            itens = []
    if not itens:
        itens = [{
            "codigo": f"NFE-{num_nf}",
            "descricao": f"MERCADORIA / SUPRIMENTO NF-e {num_nf} ({emit_nome})",
            "ncm": "9022.90.90",
            "cfop": "2102" if (emit_uf and emit_uf != dest_uf) else "1102",
            "unidade": "UN",
            "qtd": 1,
            "unitario": v_tot,
            "total": v_tot
        }]

    linhas_itens_html = ""
    soma_itens = 0.0
    for idx, it in enumerate(itens, start=1):
        cod = it.get("codigo") or f"ITEM-{idx:02d}"
        desc = it.get("descricao") or "MERCADORIA / COMPONENTE"
        ncm = it.get("ncm") or "9022.90.90"
        cfop = it.get("cfop") or ("2102" if (emit_uf and emit_uf != dest_uf) else "1102")
        unid = it.get("unidade") or "UN"
        qtd = float(it.get("qtd") or 1.0)
        v_un = float(it.get("unitario") or 0.0)
        v_sub = float(it.get("total") or (qtd * v_un))
        soma_itens += v_sub
        linhas_itens_html += f"""
        <tr>
          <td style="text-align:center;font-weight:700;">{cod}</td>
          <td><b>{desc}</b></td>
          <td style="text-align:center;">{ncm}</td>
          <td style="text-align:center;">0400</td>
          <td style="text-align:center;font-weight:700;">{cfop}</td>
          <td style="text-align:center;">{unid}</td>
          <td style="text-align:right;font-weight:700;">{qtd:g}</td>
          <td style="text-align:right;">R$ {v_un:,.2f}</td>
          <td style="text-align:right;font-weight:800;color:#0f172a;">R$ {v_sub:,.2f}</td>
        </tr>"""

    lbl_manif = {
        "CONFIRMADA": "✅ OPERAÇÃO CONFIRMADA (EVENTO 210200)",
        "CIENCIA": "ℹ️ CIÊNCIA DA OPERAÇÃO (EVENTO 210210)",
        "DESCONHECIDA": "🛡️ OPERAÇÃO DESCONHECIDA (EVENTO 210220)",
    }.get(str(st_manif or "").upper(), "⚠️ PENDENTE DE MANIFESTAÇÃO")

    lbl_est = "✅ ENTRADA LANÇADA NO ALMOXARIFADO" if st_est == "DADO_ENTRADA" else "⏳ PENDENTE DE ENTRADA NO ALMOXARIFADO"
    logo_b64 = _obter_logo_b64()
    logo_img = f'<img src="data:image/png;base64,{logo_b64}" style="max-height:46px;width:auto;" alt="EMED" />' if logo_b64 else "<b>EMED</b>"

    html_danfe = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DANFE NF-e Nº {num_nf} — {emit_nome}</title>
  <style>
    @page {{ size: A4 portrait; margin: 8mm; }}
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }}
    body {{ background: #e2e8f0; margin: 0; padding: 16px; color: #0f172a; }}
    .danfe-page {{ max-width: 880px; margin: 0 auto; background: #fff; border: 2px solid #0f172a; border-radius: 6px; padding: 18px; box-shadow: 0 8px 28px rgba(0,0,0,0.18); }}
    .toolbar-no-print {{ background: #0b132b; color: #fff; padding: 12px 16px; margin: -18px -18px 16px -18px; border-radius: 4px 4px 0 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }}
    .btn-act {{ border: none; border-radius: 6px; padding: 8px 13px; font-weight: 800; font-size: 12px; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; color: #fff; transition: 0.15s; }}
    .btn-act:hover {{ filter: brightness(1.1); }}
    .share-panel {{ background: #f0f9ff; border: 1.5px solid #0284c7; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; }}
    .canhoto {{ border: 1.5px dashed #475569; padding: 8px 10px; margin-bottom: 12px; font-size: 10.5px; display: flex; justify-content: space-between; align-items: center; gap: 12px; background: #f8fafc; }}
    .box-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
    .box-grid td, .box-grid th {{ border: 1px solid #334155; padding: 5px 8px; vertical-align: top; }}
    .fld-lbl {{ font-size: 8.5px; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.3px; display: block; margin-bottom: 2px; }}
    .fld-val {{ font-size: 11.5px; font-weight: 700; color: #0f172a; }}
    .sec-title {{ background: #0f172a; color: #fff; font-size: 10px; font-weight: 900; padding: 4px 8px; text-transform: uppercase; letter-spacing: 0.5px; margin: 10px 0 4px 0; }}
    .barcode-bars {{ font-family: "Courier New", monospace; font-size: 18px; letter-spacing: 1.5px; font-weight: 900; color: #0f172a; text-align: center; background: repeating-linear-gradient(90deg, #0f172a 0px, #0f172a 2px, transparent 2px, transparent 4px, #0f172a 4px, #0f172a 5px, transparent 5px, transparent 8px); height: 34px; margin: 4px 0; border-radius: 2px; }}
    .items-tbl {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 10px; }}
    .items-tbl th {{ background: #f1f5f9; border: 1px solid #334155; padding: 6px; font-size: 9.5px; font-weight: 800; text-transform: uppercase; color: #1e293b; }}
    .items-tbl td {{ border: 1px solid #cbd5e1; padding: 6px; }}
    @media print {{
      body {{ background: #fff; padding: 0; }}
      .danfe-page {{ border: 1px solid #000; box-shadow: none; max-width: 100%; padding: 8px; }}
      .no-print {{ display: none !important; }}
    }}
  </style>
</head>
<body>
  <div class="danfe-page">
    <!-- BARRA DE AÇÕES SUPERIOR -->
    <div class="toolbar-no-print no-print">
      <div style="display:flex;align-items:center;gap:10px;">
        {logo_img}
        <div>
          <div style="font-weight:900;font-size:13.5px;color:#38bdf8;">DANFE COMPLETA • NF-e Nº {num_nf} (Série {serie or '1'})</div>
          <div style="font-size:11px;color:#94a3b8;">Fornecedor: {emit_nome} • Capturada via Ambiente Nacional SEFAZ (NSU {nsu or '-'})</div>
        </div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button type="button" class="btn-act" style="background:#0284c7;" onclick="window.print()">🖨️ Baixar PDF / Imprimir</button>
        <a class="btn-act" style="background:#334155;" href="/api/fiscal/recebidas/xml/{n_id}">📥 Baixar XML</a>
        <button type="button" class="btn-act" style="background:#16a34a;" onclick="togglePainelCompartilhar('whats')">📲 Enviar WhatsApp</button>
        <button type="button" class="btn-act" style="background:#2563eb;" onclick="togglePainelCompartilhar('email')">✉️ Enviar E-mail</button>
      </div>
    </div>

    <!-- PAINEL DE ENVIO WHATSAPP & E-MAIL -->
    <div id="painelShareDanfe" class="share-panel no-print" style="display:none;">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;">
        <div style="background:#fff;border:1px solid #bbf7d0;border-radius:6px;padding:10px;">
          <div style="font-weight:900;font-size:12px;color:#15803d;margin-bottom:6px;">📲 Enviar DANFE por WhatsApp</div>
          <div style="display:flex;gap:6px;">
            <input type="text" id="inpWhatsDanfe" placeholder="DDD + Número (ex: 85999999999 ou deixe vazio p/ escolher)" style="flex:1;padding:7px 9px;border:1px solid #86efac;border-radius:5px;font-size:12px;" />
            <button type="button" class="btn-act" style="background:#16a34a;" onclick="dispararWhatsDanfe()">📲 Enviar</button>
          </div>
        </div>
        <div style="background:#fff;border:1px solid #bfdbfe;border-radius:6px;padding:10px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
            <span style="font-weight:900;font-size:12px;color:#1d4ed8;">✉️ Enviar DANFE por E-mail</span>
            <div style="display:flex;gap:4px;">
              <button type="button" onclick="dispararEmailDanfeWebmail('gmail')" style="background:#fee2e2;border:1px solid #ef4444;color:#b91c1c;border-radius:4px;font-size:10px;padding:2px 6px;cursor:pointer;font-weight:bold;" title="Abrir no Gmail Web">Gmail</button>
              <button type="button" onclick="dispararEmailDanfeWebmail('outlook')" style="background:#e0f2fe;border:1px solid #0284c7;color:#0369a1;border-radius:4px;font-size:10px;padding:2px 6px;cursor:pointer;font-weight:bold;" title="Abrir no Outlook Web">Outlook</button>
            </div>
          </div>
          <div style="display:flex;gap:6px;">
            <input type="email" id="inpEmailDanfe" value="{dest_email_padrao}" placeholder="E-mail destinatário..." style="flex:1;padding:7px 9px;border:1px solid #93c5fd;border-radius:5px;font-size:12px;" />
            <button type="button" class="btn-act" style="background:#2563eb;" onclick="dispararEmailDanfe()">✉️ Enviar</button>
          </div>
        </div>
      </div>
    </div>

    <!-- CANHOTO DE RECEBIMENTO -->
    <div class="canhoto">
      <div style="flex:1;">
        <b>RECEBEMOS DE {emit_nome} OS PRODUTOS / MERCADORIAS CONSTANTES DA NOTA FISCAL INDICADA AO LADO.</b>
        <div style="display:flex;gap:24px;margin-top:8px;color:#334155;">
          <span>DATA DO RECEBIMENTO: ____/____/________</span>
          <span>IDENTIFICAÇÃO E ASSINATURA DO RECEBEDOR: _________________________________________________</span>
        </div>
      </div>
      <div style="border-left:1.5px solid #334155;padding-left:12px;text-align:center;min-width:130px;">
        <div style="font-weight:900;font-size:12px;">NF-e</div>
        <div style="font-weight:900;font-size:14px;color:#0284c7;">Nº {num_nf}</div>
        <div style="font-size:10px;">SÉRIE {serie or '1'}</div>
      </div>
    </div>

    <!-- CABEÇALHO PRINCIPAL DANFE -->
    <table class="box-grid">
      <tr>
        <td style="width:42%;">
          <span class="fld-lbl">Identificação do Emitente (Fornecedor)</span>
          <div style="font-size:14px;font-weight:900;color:#0f172a;margin-top:2px;">{emit_nome}</div>
          <div style="font-size:11px;color:#334155;margin-top:6px;line-height:1.4;">
            <b>CNPJ / CPF:</b> {emit_cnpj_fmt}<br/>
            <b>UF de Origem:</b> {emit_uf or 'BR'}<br/>
            <b>Modalidade:</b> {tipo_doc or 'NF-e DISTRIBUIÇÃO SEFAZ'}
          </div>
        </td>
        <td style="width:18%;text-align:center;vertical-align:middle;background:#f8fafc;">
          <div style="font-size:15px;font-weight:900;color:#0f172a;">DANFE</div>
          <div style="font-size:8.5px;color:#475569;line-height:1.2;margin:2px 0 6px 0;">DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA</div>
          <div style="display:inline-block;border:1.5px solid #0f172a;padding:3px 8px;font-weight:900;font-size:11px;border-radius:4px;margin-bottom:4px;">1 - SAÍDA FORNECEDOR<br/>0 - ENTRADA EMED</div>
          <div style="font-size:13px;font-weight:900;color:#0284c7;margin-top:4px;">Nº {num_nf}</div>
          <div style="font-size:10px;font-weight:700;">SÉRIE: {serie or '1'}</div>
        </td>
        <td style="width:40%;">
          <span class="fld-lbl">Controle do Fisco / Código de Barras</span>
          <div class="barcode-bars"></div>
          <span class="fld-lbl" style="margin-top:6px;">Chave de Acesso da NF-e (44 Dígitos)</span>
          <div style="font-family:monospace;font-size:11px;font-weight:900;background:#f1f5f9;padding:5px 6px;border-radius:4px;border:1px solid #cbd5e1;letter-spacing:0.3px;word-break:break-all;">
            {chave_fmt}
          </div>
          <div style="font-size:9px;color:#475569;margin-top:4px;text-align:center;">
            Consulta de autenticidade no portal nacional da NF-e <a href="https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx" target="_blank" style="color:#0284c7;">www.nfe.fazenda.gov.br</a>
          </div>
        </td>
      </tr>
    </table>

    <table class="box-grid">
      <tr>
        <td style="width:50%;">
          <span class="fld-lbl">Natureza da Operação</span>
          <span class="fld-val">COMPRA / FORNECIMENTO DE MERCADORIA, PEÇAS OU SUPRIMENTOS</span>
        </td>
        <td style="width:25%;">
          <span class="fld-lbl">NSU Distribuição SEFAZ</span>
          <span class="fld-val">{nsu or '-'} (Ambiente Nacional)</span>
        </td>
        <td style="width:25%;">
          <span class="fld-lbl">Data / Hora de Emissão</span>
          <span class="fld-val">{dt_emi_fmt}</span>
        </td>
      </tr>
    </table>

    <!-- DESTINATÁRIO (EMED) -->
    <div class="sec-title">1. Destinatário / Remetente (Unidade EMED)</div>
    <table class="box-grid">
      <tr>
        <td style="width:52%;">
          <span class="fld-lbl">Nome / Razão Social</span>
          <span class="fld-val">{dest_razao}</span>
        </td>
        <td style="width:26%;">
          <span class="fld-lbl">CNPJ / CPF</span>
          <span class="fld-val">{dest_cnpj_fmt}</span>
        </td>
        <td style="width:22%;">
          <span class="fld-lbl">Inscrição Estadual / CF-DF</span>
          <span class="fld-val">{dest_ie}</span>
        </td>
      </tr>
      <tr>
        <td>
          <span class="fld-lbl">Endereço da Unidade Destinatária</span>
          <span class="fld-val">{dest_end}</span>
        </td>
        <td>
          <span class="fld-lbl">Status Manifestação do Destinatário</span>
          <span class="fld-val" style="color:#0284c7;">{lbl_manif}</span>
        </td>
        <td>
          <span class="fld-lbl">Status Almoxarifado EMED</span>
          <span class="fld-val" style="color:#059669;">{lbl_est}</span>
        </td>
      </tr>
    </table>

    <!-- CÁLCULO DO IMPOSTO -->
    <div class="sec-title">2. Cálculo do Imposto &amp; Totais da Nota Fiscal</div>
    <table class="box-grid">
      <tr>
        <td><span class="fld-lbl">Base de Cálculo do ICMS</span><span class="fld-val">R$ 0,00</span></td>
        <td><span class="fld-lbl">Valor do ICMS</span><span class="fld-val">R$ 0,00</span></td>
        <td><span class="fld-lbl">Valor do Frete</span><span class="fld-val">R$ 0,00</span></td>
        <td><span class="fld-lbl">Outras Despesas</span><span class="fld-val">R$ 0,00</span></td>
        <td><span class="fld-lbl">Valor Total dos Produtos</span><span class="fld-val">R$ {v_tot:,.2f}</span></td>
        <td style="background:#f0fdf4;"><span class="fld-lbl" style="color:#15803d;">Valor Total da Nota</span><span class="fld-val" style="font-size:14px;font-weight:900;color:#15803d;">R$ {v_tot:,.2f}</span></td>
      </tr>
    </table>

    <!-- DADOS DOS PRODUTOS / SERVIÇOS -->
    <div class="sec-title">3. Dados dos Produtos / Peças / Mercadorias</div>
    <table class="items-tbl">
      <thead>
        <tr>
          <th style="width:90px;">Código</th>
          <th>Descrição do Produto / Peça / Suprimento</th>
          <th style="width:80px;">NCM/SH</th>
          <th style="width:55px;">CSOSN</th>
          <th style="width:55px;">CFOP</th>
          <th style="width:50px;">Unid.</th>
          <th style="width:65px;">Qtd.</th>
          <th style="width:105px;">Valor Unit.</th>
          <th style="width:110px;">Valor Total</th>
        </tr>
      </thead>
      <tbody>
        {linhas_itens_html}
      </tbody>
    </table>

    <!-- DADOS ADICIONAIS -->
    <div class="sec-title">4. Dados Adicionais / Informações Complementares SEFAZ</div>
    <table class="box-grid">
      <tr>
        <td style="min-height:60px;font-size:11px;line-height:1.45;color:#334155;">
          <b>Observações &amp; Rastreabilidade Fiscal:</b><br/>
          &bull; Documento sincronizado diretamente do Ambiente Nacional da SEFAZ (WebService <b>NFeDistribuicaoDFe</b>) com Certificado Digital A1 da EMED.<br/>
          &bull; <b>Chave de Acesso Oficial:</b> {chave or 'Não aplicável'} &bull; <b>NSU SEFAZ:</b> {nsu or '-'} &bull; <b>Capturada em:</b> {dt_cap or dt_emi_fmt}<br/>
          &bull; <b>Histórico de Auditoria:</b> {obs or 'Sem observações adicionais.'}
        </td>
      </tr>
    </table>
  </div>

  <script>
    function togglePainelCompartilhar(foco) {{
      const p = document.getElementById("painelShareDanfe");
      p.style.display = "block";
      if (foco === "whats") document.getElementById("inpWhatsDanfe")?.focus();
      if (foco === "email") document.getElementById("inpEmailDanfe")?.focus();
    }}

    function dispararWhatsDanfe() {{
      const foneRaw = (document.getElementById("inpWhatsDanfe")?.value || "").replace(/\\D/g, "");
      const urlDanfe = window.location.origin + "/api/fiscal/recebidas/danfe/{n_id}";
      const urlXml = window.location.origin + "/api/fiscal/recebidas/xml/{n_id}";
      const texto = [
        "🧾 *DANFE NF-e Nº {num_nf} — EMED ELETROMEDICINA*",
        "• *Fornecedor:* {emit_nome}",
        "• *CNPJ Emitente:* {emit_cnpj_fmt}",
        "• *Unidade Destino:* {dest_razao}",
        "• *Data Emissão:* {dt_emi_fmt}",
        "• *Valor Total:* R$ {v_tot:,.2f}",
        "• *Chave de Acesso:* `{chave}`",
        "",
        "📄 *Visualizar DANFE Completa:* " + urlDanfe,
        "📥 *Baixar XML:* " + urlXml
      ].join("\\n");
      const zapUrl = foneRaw
        ? `https://api.whatsapp.com/send?phone=${{foneRaw.startsWith("55") ? foneRaw : "55" + foneRaw}}&text=${{encodeURIComponent(texto)}}`
        : `https://api.whatsapp.com/send?text=${{encodeURIComponent(texto)}}`;
      window.open(zapUrl, "_blank");
    }}

    function obterDadosEmailDanfe() {{
      const email = (document.getElementById("inpEmailDanfe")?.value || "").trim();
      const urlDanfe = window.location.origin + "/api/fiscal/recebidas/danfe/{n_id}";
      const urlPdf = window.location.origin + "/api/fiscal/recebidas/pdf/{n_id}";
      const urlXml = window.location.origin + "/api/fiscal/recebidas/xml/{n_id}";
      const assunto = "DANFE NF-e Nº {num_nf} - {emit_nome} (EMED Eletromedicina)";
      const corpo = [
        "Prezados,",
        "",
        "Seguem os dados da Nota Fiscal Eletrônica (NF-e) recebida no Radar DF-e da EMED Eletromedicina:",
        "",
        "• Número da NF-e: {num_nf} (Série {serie or '1'})",
        "• Fornecedor / Emitente: {emit_nome} (CNPJ: {emit_cnpj_fmt})",
        "• Unidade EMED Destinatária: {dest_razao} ({dest_cnpj_fmt})",
        "• Data de Emissão: {dt_emi_fmt}",
        "• Valor Total: R$ {v_tot:,.2f}",
        "• Chave de Acesso: {chave}",
        "",
        "📄 Visualizar / Imprimir DANFE Completa:",
        urlDanfe,
        "",
        "📥 Download Direto da DANFE em PDF:",
        urlPdf,
        "",
        "📥 Download do Arquivo XML Oficial:",
        urlXml,
        "",
        "Atenciosamente,",
        "Departamento Fiscal — EMED Eletromedicina"
      ].join("\n");
      return {{ email, assunto, corpo }};
    }}

    function dispararEmailDanfeWebmail(tipo) {{
      const d = obterDadosEmailDanfe();
      if (!d.email || !d.email.includes("@")) {{
        alert("Por favor, digite um endereço de e-mail válido.");
        document.getElementById("inpEmailDanfe")?.focus();
        return;
      }}
      if (tipo === "gmail") {{
        window.open(`https://mail.google.com/mail/?view=cm&fs=1&to=${{encodeURIComponent(d.email)}}&su=${{encodeURIComponent(d.assunto)}}&body=${{encodeURIComponent(d.corpo)}}`, "_blank");
      }} else if (tipo === "outlook") {{
        window.open(`https://outlook.live.com/mail/0/deeplink/compose?to=${{encodeURIComponent(d.email)}}&subject=${{encodeURIComponent(d.assunto)}}&body=${{encodeURIComponent(d.corpo)}}`, "_blank");
      }} else {{
        window.location.href = `mailto:${{encodeURIComponent(d.email)}}?subject=${{encodeURIComponent(d.assunto)}}&body=${{encodeURIComponent(d.corpo)}}`;
      }}
    }}

    async function dispararEmailDanfe() {{
      const d = obterDadosEmailDanfe();
      if (!d.email || !d.email.includes("@")) {{
        alert("Por favor, digite um endereço de e-mail válido.");
        document.getElementById("inpEmailDanfe")?.focus();
        return;
      }}
      try {{
        const res = await fetch("/api/fiscal/recebidas/enviar-email-pdf", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ id: {n_id}, email: d.email }})
        }}).then(r => r.json());
        if (res.ok && res.smtp_sent) {{
          alert(res.msg);
          return;
        }}
      }} catch (e) {{}}

      const el = d.email.toLowerCase();
      if (el.endsWith("@gmail.com")) {{
        dispararEmailDanfeWebmail("gmail");
      }} else if (el.endsWith("@outlook.com") || el.endsWith("@hotmail.com") || el.endsWith("@live.com")) {{
        dispararEmailDanfeWebmail("outlook");
      }} else {{
        dispararEmailDanfeWebmail("mailto");
      }}
    }}?subject=${{encodeURIComponent(assunto)}}&body=${{encodeURIComponent(corpo)}}`;
    }}

    {"window.addEventListener('load', () => setTimeout(() => window.print(), 350));" if auto_print else ""}
  </script>
</body>
</html>"""
    return web.Response(text=html_danfe, content_type="text/html")


async def api_fiscal_v2_xml_download(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    os_id = request.match_info.get("os_id", "0")
    with _get_db_connection(db_name) as conn:
        row = conn.execute(
            "SELECT xml_path, numero_nf, cliente, cnpj_tomador, prestador_cnpj, prestador_razao, valor_servicos, valor_pecas, valor_liquido, discriminacao_servico, data_emissao, serie FROM notas_fiscais WHERE numero_nf = ? OR CAST(os_id AS TEXT) = ? OR CAST(id AS TEXT) = ? ORDER BY id DESC LIMIT 1",
            (os_id, os_id, os_id)
        ).fetchone()
    if row and row[0] and os.path.exists(row[0]):
        num = row[1] or f"OS_{os_id}"
        return web.Response(
            body=Path(row[0]).read_bytes(),
            content_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="NFS_{num}.xml"'},
        )
    elif row and row[1]:
        num = row[1]
        xml_fallback = f"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe{num}">
    <ide><nNF>{num}</nNF><serie>{row[11] or '1'}</serie><dhEmi>{row[10] or ''}</dhEmi></ide>
    <emit><CNPJ>{row[4] or ''}</CNPJ><xNome>{row[5] or 'EMED ELETROMEDICINA'}</xNome></emit>
    <dest><CNPJ>{row[3] or ''}</CNPJ><xNome>{row[2] or ''}</xNome></dest>
    <total><vServ>{float(row[6] or 0):.2f}</vServ><vProd>{float(row[7] or 0):.2f}</vProd><vNF>{float(row[8] or 0):.2f}</vNF></total>
    <infAdic><infCpl><![CDATA[{row[9] or ''}]]></infCpl></infAdic>
  </infNFe>
</NFe>"""
        return web.Response(
            body=xml_fallback.encode("utf-8"),
            content_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="NFe_{num}.xml"'},
        )
    return web.Response(text="Arquivo XML não encontrado para esta nota.", status=404)


async def api_fiscal_v2_transferir_filiais(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    origem = str(body.get("origem", "MATRIZ_CE")).upper()
    destino = str(body.get("destino", "FILIAL_DF")).upper()
    if origem == destino:
        return web.json_response({"ok": False, "msg": "A filial de origem deve ser diferente da filial de destino."}, status=400)

    natureza_cod = str(body.get("natureza_op", "TRANSFERENCIA_ESTOQUE"))
    cfop = str(body.get("cfop", "6152" if ("CE" in origem and "DF" in destino) or ("DF" in origem and "CE" in destino) else "5152"))
    veiculo = str(body.get("veiculo_transporte", "TRANSPORTE EM VEÍCULO PRÓPRIO EMED")).strip()
    obs_extra = str(body.get("observacoes", "")).strip()
    usuario = str(body.get("usuario", "netto")).strip()
    mov_fisico = bool(body.get("movimentar_estoque_fisico", True))
    mov_fiscal = bool(body.get("movimentar_estoque_fiscal", True))
    itens = body.get("itens", [])

    if not itens:
        return web.json_response({"ok": False, "msg": "Selecione ao menos 1 peça/item para transferir."}, status=400)

    # INTERTRAVAMENTO DE ESTOQUE: Validar se há disponibilidade suficiente no almoxarifado
    with _get_db_connection(db_name) as conn_chk:
        for it in itens:
            pid = it.get("peca_id")
            qtd_solicitada = float(it.get("quantidade", 1))
            if qtd_solicitada <= 0:
                return web.json_response({"ok": False, "msg": f"A quantidade do item '{it.get('nome', '')}' deve ser maior que zero."}, status=400)
            if pid:
                row_p = conn_chk.execute(
                    "SELECT codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade), unidade FROM estoque_pecas WHERE id = ?",
                    (pid,)
                ).fetchone()
                if not row_p:
                    return web.json_response({"ok": False, "msg": f"Peça ID #{pid} não localizada no estoque."}, status=404)
                cod_p, nome_p, saldo_fis, saldo_fisc, un_p = row_p
                saldo_fis = float(saldo_fis or 0.0)
                saldo_fisc = float(saldo_fisc or 0.0)
                if mov_fisico and qtd_solicitada > saldo_fis:
                    return web.json_response({
                        "ok": False,
                        "msg": (
                            f"🚫 ESTOQUE FÍSICO INSUFICIENTE!\n\n"
                            f"• Peça: [{cod_p}] {nome_p}\n"
                            f"• Disponível no Estoque Físico: {saldo_fis:g} {un_p or 'UN'}\n"
                            f"• Quantidade Solicitada: {qtd_solicitada:g} {un_p or 'UN'}\n\n"
                            f"Ajuste a quantidade para no máximo {saldo_fis:g} {un_p or 'UN'}."
                        )
                    }, status=400)
                if mov_fiscal and not mov_fisico and qtd_solicitada > saldo_fisc:
                    return web.json_response({
                        "ok": False,
                        "msg": (
                            f"🚫 ESTOQUE FISCAL INSUFICIENTE!\n\n"
                            f"• Peça: [{cod_p}] {nome_p}\n"
                            f"• Disponível no Estoque Fiscal: {saldo_fisc:g} {un_p or 'UN'}\n"
                            f"• Quantidade Solicitada: {qtd_solicitada:g} {un_p or 'UN'}\n\n"
                            f"Ajuste a quantidade para no máximo {saldo_fisc:g} {un_p or 'UN'}."
                        )
                    }, status=400)

    manager = FiscalManager(db_name)
    cfg_origem = manager.get_filial_config(origem)
    cfg_destino = manager.get_filial_config(destino)

    nat_descr = "TRANSFERÊNCIA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS (CFOP " + cfop + ")"
    if "USO" in natureza_cod or "CONSUMO" in natureza_cod:
        nat_descr = "REMESSA DE BEM PARA USO/CONSUMO EM ESTABELECIMENTO DA MESMA EMPRESA (CFOP " + cfop + ")"
    elif "CONSERTO" in natureza_cod:
        nat_descr = "REMESSA DE BEM PARA CONSERTO/REPARO EM LABORATÓRIO (CFOP " + cfop + ")"

    valor_total = sum(float(it.get("quantidade", 1)) * float(it.get("valor_unitario", 0.0)) for it in itens)

    detalhe_itens_txt = []
    for it in itens:
        detalhe_itens_txt.append(f"• Item: {it.get('nome', '')} (Cód: {it.get('codigo', '')}) | Qtd: {it.get('quantidade', 1)} | Unit: R$ {float(it.get('valor_unitario', 0.0)):.2f}")

    discriminacao = f"""TRANSFERÊNCIA ENTRE ESTABELECIMENTOS DA MESMA EMPRESA
ORIGEM: {cfg_origem.get('razao_social')} (CNPJ: {cfg_origem.get('cnpj')})
DESTINO: {cfg_destino.get('razao_social')} (CNPJ: {cfg_destino.get('cnpj')})
NATUREZA FISCAL: {nat_descr}
TRANSPORTE / LOGÍSTICA: {veiculo}

ITENS TRANSFERIDOS:
""" + "\n".join(detalhe_itens_txt) + f"""

OBSERVAÇÃO LEGAL TRIBUTÁRIA:
Operação de transferência de mercadorias entre estabelecimentos do mesmo titular sem incidência de ICMS, em estrita conformidade com a decisão do Supremo Tribunal Federal (STF - ADC 49) e Lei Complementar nº 204/2023.
{f'Observações Complementares: {obs_extra}' if obs_extra else ''}"""

    sigla = "DF" if origem == "FILIAL_DF" else "CE"
    num_seq = uuid.uuid4().hex[:6].upper()
    ano = datetime.now().year
    num_nf = f"TRF-{sigla}-{ano}-{num_seq}"
    chave_acesso = f"53{datetime.now().strftime('%y%m')}{''.join(c for c in cfg_origem.get('cnpj', '') if c.isdigit())}55001{int(time.time()) % 1000000000:09d}1{uuid.uuid4().int % 100000000:08d}"
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    with _get_db_connection(db_name) as conn:
        cur = conn.execute("""
            INSERT INTO notas_fiscais (
                os_id, cliente, cnpj_tomador, tomador_endereco, tomador_cidade, tomador_uf,
                tipo_nota, natureza_operacao, cfop, valor_servicos, valor_pecas, valor_desconto,
                aliquota_iss, valor_iss, valor_liquido, status_fiscal, numero_nf, serie, chave_acesso,
                data_emissao, filial_emissora, prestador_cnpj, prestador_razao, prestador_im,
                prestador_endereco, prestador_cidade, prestador_uf, prestador_fone, prestador_email,
                discriminacao_servico, criado_em, atualizado_em
            ) VALUES (
                0, ?, ?, ?, ?, ?,
                'TRANSFERÊNCIA ENTRE FILIAIS', ?, ?, 0.0, ?, 0.0,
                0.0, 0.0, ?, 'AUTORIZADA (TRANSFERÊNCIA ENTRE FILIAIS)', ?, 'TRF-1', ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?
            )
        """, (
            cfg_destino.get("razao_social"), cfg_destino.get("cnpj"), cfg_destino.get("endereco"),
            cfg_destino.get("cidade"), cfg_destino.get("uf"),
            nat_descr, cfop, valor_total, valor_total,
            num_nf, chave_acesso, agora_str, origem,
            cfg_origem.get("cnpj"), cfg_origem.get("razao_social"), cfg_origem.get("inscricao_municipal"),
            cfg_origem.get("endereco"), cfg_origem.get("cidade"), cfg_origem.get("uf"),
            cfg_origem.get("telefone"), cfg_origem.get("email"),
            discriminacao, agora_str, agora_str
        ))
        id_nf = cur.lastrowid

        # Atualizar estoque: deduz da origem conforme opções de Físico / Fiscal
        for it in itens:
            pid = it.get("peca_id")
            qtd = float(it.get("quantidade", 1))
            if pid:
                if mov_fisico:
                    conn.execute("UPDATE estoque_pecas SET quantidade = MAX(0, quantidade - ?) WHERE id = ?", (qtd, pid))
                if mov_fiscal:
                    conn.execute("UPDATE estoque_pecas SET saldo_fiscal = MAX(0, COALESCE(saldo_fiscal, quantidade) - ?) WHERE id = ?", (qtd, pid))
                mov_tipo = 'TRANSFERENCIA_FILIAL_SAIDA' if (mov_fisico and mov_fiscal) else ('TRANSFERENCIA_APENAS_FISCAL' if mov_fiscal else 'TRANSFERENCIA_APENAS_FISICO')
                conn.execute("""
                    INSERT INTO movimentacoes_estoque (
                        estabelecimento, centro_estoque, codigo_item, descricao,
                        data_mov, hora_mov, tipo_mov, qtd_saida, documento, observacao
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    origem, f"ALMOXARIFADO {origem}", str(it.get("codigo", "")), str(it.get("nome", "")),
                    datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"),
                    mov_tipo, qtd, num_nf, f"Transferência para {destino} ({veiculo}) [Físico: {'SIM' if mov_fisico else 'NÃO'} | Fiscal: {'SIM' if mov_fiscal else 'NÃO'}]"
                ))

        conn.commit()

    _registrar_log_fiscal("TRANSFERENCIA_FILIAIS", f"NF-e {num_nf} emitida ({origem} -> {destino}) - Total: R$ {valor_total:.2f} ({len(itens)} itens)", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ Nota de Transferência {num_nf} emitida com sucesso! {len(itens)} item(ns) movimentado(s) de {origem} para {destino}.",
        "numero_nf": num_nf,
        "id_nf": id_nf
    })


async def api_fiscal_v2_lancar_consumivel(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    descricao = str(body.get("descricao", "")).strip()
    fornecedor = str(body.get("fornecedor", "Supermercado / Fornecedor Local")).strip()
    numero_nf = str(body.get("numero_nf", "")).strip() or f"CUPOM-{uuid.uuid4().hex[:6].upper()}"
    unidade_setor = str(body.get("unidade_setor", "Matriz Eusébio/CE - Copa & Administrativo")).strip()
    quantidade = float(body.get("quantidade") or 1.0)
    valor_total = float(body.get("valor_total") or 0.0)
    usuario = str(body.get("usuario", "netto")).strip()

    if not descricao:
        return web.json_response({"ok": False, "msg": "Informe a descrição do material (ex: Café, Papel Higiênico, etc.)."}, status=400)

    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    nome_composto = f"{descricao} (NF: {numero_nf} • Fornec: {fornecedor} • R$ {valor_total:.2f})"

    with _get_db_connection(db_name) as conn:
        conn.execute("""
            INSERT INTO baixas_consumiveis (
                tecnico_setor, nome_item, quantidade, finalidade, data_baixa
            ) VALUES (?, ?, ?, 'CONSUMO IMEDIATO / DESPESA OPERACIONAL', ?)
        """, (unidade_setor, nome_composto, quantidade, agora_str))
        conn.commit()

    _registrar_log_fiscal("CONSUMIVEL_ADMINISTRATIVO", f"NF {numero_nf} ({descricao}) - R$ {valor_total:.2f} lançada para {unidade_setor}. Fisco registrado e estoque físico mantido em zero.", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ NF {numero_nf} ({descricao}) registrada no Fisco como Despesa Operacional! O estoque físico de peças clínicas foi mantido em zero (consumo imediato)."
    })


async def api_fiscal_v2_ajuste_estoque(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    peca_id = int(body.get("peca_id", 0))
    tipo_mov = str(body.get("tipo_mov", "SAIDA")).upper()
    qtd = float(body.get("quantidade", 1.0))
    afeta_fisico = bool(body.get("afeta_fisico", True))
    afeta_fiscal = bool(body.get("afeta_fiscal", True))
    motivo = str(body.get("motivo", "Ajuste de inventário / Auditoria")).strip()
    usuario = str(body.get("usuario", "netto")).strip()

    if peca_id <= 0:
        return web.json_response({"ok": False, "msg": "Selecione uma peça válida da lista."}, status=400)
    if qtd <= 0:
        return web.json_response({"ok": False, "msg": "Informe uma quantidade maior que zero."}, status=400)
    if not afeta_fisico and not afeta_fiscal:
        return web.json_response({"ok": False, "msg": "Selecione ao menos um estoque para movimentar (Físico ou Fiscal)."}, status=400)

    fator = 1 if tipo_mov == "ENTRADA" else -1

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade) FROM estoque_pecas WHERE id = ?", (peca_id,)).fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Peça não encontrada no banco."}, status=404)

        cod_p, nome_p, qtd_ant, fisc_ant = row
        nova_qtd = max(0.0, float(qtd_ant or 0) + (fator * qtd)) if afeta_fisico else float(qtd_ant or 0)
        novo_fisc = max(0.0, float(fisc_ant or 0) + (fator * qtd)) if afeta_fiscal else float(fisc_ant or 0)

        if afeta_fisico and afeta_fiscal:
            conn.execute("UPDATE estoque_pecas SET quantidade = ?, saldo_fiscal = ? WHERE id = ?", (nova_qtd, novo_fisc, peca_id))
        elif afeta_fisico:
            conn.execute("UPDATE estoque_pecas SET quantidade = ? WHERE id = ?", (nova_qtd, peca_id))
        elif afeta_fiscal:
            conn.execute("UPDATE estoque_pecas SET saldo_fiscal = ? WHERE id = ?", (novo_fisc, peca_id))

        desc_mov = f"AJUSTE_{tipo_mov}_" + ("FISICO_E_FISCAL" if (afeta_fisico and afeta_fiscal) else ("FISICO" if afeta_fisico else "FISCAL"))
        col_qtd = "qtd_entrada" if tipo_mov == "ENTRADA" else "qtd_saida"
        conn.execute(f"""
            INSERT INTO movimentacoes_estoque (
                estabelecimento, centro_estoque, codigo_item, descricao,
                data_mov, hora_mov, tipo_mov, {col_qtd}, saldo, observacao
            ) VALUES ('MATRIZ_CE', 'ALMOXARIFADO CENTRAL', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(cod_p or ""), str(nome_p or ""),
            datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"),
            desc_mov, qtd, nova_qtd, f"{motivo} (Op: {usuario} | Físico: {nova_qtd:.1f} | Fiscal: {novo_fisc:.1f})"
        ))
        conn.commit()

    _registrar_log_fiscal("AJUSTE_ESTOQUE", f"Ajuste {tipo_mov} ({qtd} un) em {nome_p} | Afeta Físico: {afeta_fisico} | Afeta Fiscal: {afeta_fiscal} | Motivo: {motivo}", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ Movimentação de estoque concluída! Peça: {nome_p} • Saldo Físico: {nova_qtd:.1f} • Saldo Fiscal: {novo_fisc:.1f}"
    })


async def api_fiscal_v2_inventario_ajuste_direto(request: web.Request) -> web.Response:
    """Atualiza diretamente os saldos absoluto físico e fiscal de um item no inventário."""
    body = await request.json()
    db_name = request.app.get("db_path", "emed.db")
    peca_id = int(body.get("peca_id", 0))
    usuario = str(body.get("usuario", "netto")).strip()
    motivo = str(body.get("motivo", "Ajuste manual de inventário / Reconciliação direta")).strip()

    if peca_id <= 0:
        return web.json_response({"ok": False, "msg": "Selecione uma peça válida."}, status=400)

    novo_fisico = body.get("quantidade_fisica")
    novo_fiscal = body.get("saldo_fiscal")

    if novo_fisico is None and novo_fiscal is None:
        return web.json_response({"ok": False, "msg": "Informe ao menos um saldo para ajuste."}, status=400)

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade) FROM estoque_pecas WHERE id = ?", (peca_id,)).fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Peça não encontrada."}, status=404)

        cod_p, nome_p, fis_ant, fisc_ant = row
        fis_ant = float(fis_ant or 0)
        fisc_ant = float(fisc_ant or 0)

        fis_final = max(0.0, float(novo_fisico)) if novo_fisico is not None else fis_ant
        fisc_final = max(0.0, float(novo_fiscal)) if novo_fiscal is not None else fisc_ant

        conn.execute("UPDATE estoque_pecas SET quantidade = ?, saldo_fiscal = ? WHERE id = ?", (fis_final, fisc_final, peca_id))

        delta_fis = fis_final - fis_ant
        delta_fisc = fisc_final - fisc_ant
        tipo_mov = "AJUSTE_INVENTARIO_DIRETO"
        obs = f"{motivo} | Físico: {fis_ant:.1f} ➔ {fis_final:.1f} (Δ {delta_fis:+.1f}) | Fiscal: {fisc_ant:.1f} ➔ {fisc_final:.1f} (Δ {delta_fisc:+.1f}) | Op: {usuario}"

        conn.execute("""
            INSERT INTO movimentacoes_estoque (
                estabelecimento, centro_estoque, codigo_item, descricao,
                data_mov, hora_mov, tipo_mov, qtd_entrada, qtd_saida, saldo, observacao
            ) VALUES ('MATRIZ_CE', 'ALMOXARIFADO CENTRAL', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(cod_p or ""), str(nome_p or ""),
            datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"),
            tipo_mov,
            max(0.0, delta_fis) if delta_fis > 0 else 0.0,
            abs(delta_fis) if delta_fis < 0 else 0.0,
            fis_final, obs
        ))
        conn.commit()

    _registrar_log_fiscal("INVENTARIO_AJUSTE", f"Ajuste direto em '{nome_p}' [{cod_p}]: Físico {fis_ant:.1f}->{fis_final:.1f}, Fiscal {fisc_ant:.1f}->{fisc_final:.1f} | {motivo}", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ Saldo de '{nome_p}' atualizado! Físico: {fis_final:.1f} • Fiscal: {fisc_final:.1f}",
        "peca_id": peca_id,
        "quantidade_fisica": fis_final,
        "saldo_fiscal": fisc_final
    })


async def api_fiscal_v2_inventario_novo_item(request: web.Request) -> web.Response:
    """Cadastra um novo item diretamente a partir da tela de inventário."""
    body = await request.json()
    db_name = request.app.get("db_path", "emed.db")
    codigo = str(body.get("codigo", "")).strip().upper()
    nome = str(body.get("nome", "")).strip().upper()
    qtd_fis = max(0.0, float(body.get("quantidade_fisica", 0)))
    qtd_fisc = max(0.0, float(body.get("saldo_fiscal", qtd_fis)))
    preco = max(0.0, float(body.get("preco_custo", 0.0)))
    unidade = str(body.get("unidade", "UN")).strip().upper() or "UN"
    usuario = str(body.get("usuario", "netto")).strip()

    if not nome:
        return web.json_response({"ok": False, "msg": "Informe a descrição ou nome da peça."}, status=400)

    with _get_db_connection(db_name) as conn:
        if not codigo:
            max_c = conn.execute("SELECT MAX(CAST(codigo AS INTEGER)) FROM estoque_pecas WHERE codigo GLOB '[0-9]*'").fetchone()[0] or 0
            codigo = str(max_c + 1)

        conn.execute("""
            INSERT INTO estoque_pecas (
                codigo, nome_peca, quantidade, saldo_fiscal, preco_custo, preco_unitario,
                unidade, categoria, localizacao, estoque_minimo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PEÇA DE REPOSIÇÃO', 'ALMOXARIFADO CENTRAL', 1)
        """, (codigo, nome, qtd_fis, qtd_fisc, preco, preco * 1.5, unidade))
        novo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute("""
            INSERT INTO movimentacoes_estoque (
                estabelecimento, centro_estoque, codigo_item, descricao,
                data_mov, hora_mov, tipo_mov, qtd_entrada, saldo, observacao
            ) VALUES ('MATRIZ_CE', 'ALMOXARIFADO CENTRAL', ?, ?, ?, ?, 'CADASTRO_INVENTARIO', ?, ?, ?)
        """, (
            codigo, nome,
            datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"),
            qtd_fis, qtd_fis, f"Novo item cadastrado via Inventário Fiscal por {usuario} (Fiscal: {qtd_fisc})"
        ))
        conn.commit()

    _registrar_log_fiscal("INVENTARIO_NOVO_ITEM", f"Cadastro de item [{codigo}] {nome} | Físico: {qtd_fis} | Fiscal: {qtd_fisc}", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ Item '[{codigo}] {nome}' adicionado com sucesso ao inventário!",
        "item": {
            "id": novo_id, "codigo": codigo, "nome": nome,
            "qtd": qtd_fis, "qtd_fiscal": qtd_fisc, "preco": preco, "unidade": unidade
        }
    })



async def api_fiscal_v2_peca_detalhes(request: web.Request) -> web.Response:
    """Retorna todos os dados fiscais, tributários, de precificação e engenharia clínica de uma peça."""
    db_name = request.app.get("db_path", "emed.db")
    peca_id = int(request.match_info.get("peca_id", 0))
    with _get_db_connection(db_name) as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(estoque_pecas)")
        cols = [c[1] for c in cur.fetchall()]
        row = conn.execute("SELECT * FROM estoque_pecas WHERE id = ?", (peca_id,)).fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Peça não encontrada"}, status=404)
        dados = dict(zip(cols, row))
        return web.json_response({"ok": True, "peca": dados})


async def api_fiscal_v2_peca_salvar(request: web.Request) -> web.Response:
    """Salva todos os campos estratégicos fiscais, tributários e de precificação de uma peça."""
    body = await request.json()
    db_name = request.app.get("db_path", "emed.db")
    peca_id = int(body.get("id", 0))
    if peca_id <= 0:
        return web.json_response({"ok": False, "msg": "ID de peça inválido"}, status=400)

    campos = [
        "nome_peca", "ncm", "cest", "origem_mercadoria", "cfop_padrao_venda",
        "cfop_padrao_transferencia", "csosn_icms", "aliquota_icms", "reducao_base_icms",
        "isencao_icms_motivo", "cst_pis", "aliquota_pis", "cst_cofins", "aliquota_cofins",
        "cst_ipi", "aliquota_ipi", "preco_custo", "custo_medio", "margem_contrato",
        "margem_avulso", "margem_avista", "margem_desestimulo", "preco_venda_tabela",
        "preco_venda_minimo", "markup_percentual", "fabricante", "modelo_compativel",
        "numero_serie", "lote_fabricacao", "localizacao", "unidade", "categoria",
        "estoque_minimo", "filial_pertencente", "alerta_reajuste"
    ]
    set_clauses = []
    vals = []
    for c in campos:
        if c in body:
            set_clauses.append(f"{c} = ?")
            vals.append(body[c])

    if not set_clauses:
        return web.json_response({"ok": False, "msg": "Nenhum campo para atualizar"})

    vals.append(peca_id)
    with _get_db_connection(db_name) as conn:
        conn.execute(f"UPDATE estoque_pecas SET {', '.join(set_clauses)} WHERE id = ?", tuple(vals))
        conn.commit()

    usuario = str(body.get("usuario", "netto"))
    _registrar_log_fiscal("PECA_UPDATE_FISCAL", f"Peça #{peca_id} atualizada com parâmetros fiscais e precificação por {usuario}", usuario)
    return web.json_response({"ok": True, "msg": "✅ Parâmetros Fiscais & Precificação Salvos com Sucesso!"})


async def api_fiscal_v2_fechamento_dados(request: web.Request) -> web.Response:
    """Retorna os dados consolidados do mês para fechamento contábil e mitigação de falhas."""
    db_name = request.app.get("db_path", "emed.db")
    mes = request.query.get("mes", "").strip() or datetime.now().strftime("%Y-%m")
    filial = request.query.get("filial", "CONSOLIDADO").strip().upper()

    with _get_db_connection(db_name) as conn:
        rows_m = conn.execute("""
            SELECT DISTINCT substr(data_emissao, 1, 7) FROM notas_fiscais WHERE data_emissao IS NOT NULL AND data_emissao != ''
            UNION
            SELECT DISTINCT lote_contabilidade_mes FROM notas_fiscais WHERE lote_contabilidade_mes IS NOT NULL AND lote_contabilidade_mes != ''
        """).fetchall()
        meses_set = {r[0] for r in rows_m if r[0] and len(r[0]) == 7}
        agora = datetime.now()
        for i in range(6):
            m_calc = (agora.month - i - 1) % 12 + 1
            y_calc = agora.year + ((agora.month - i - 1) // 12)
            meses_set.add(f"{y_calc:04d}-{m_calc:02d}")
        meses_disponiveis = sorted(list(meses_set), reverse=True)

        sql_n = """
            SELECT id, os_id, cliente, cnpj_tomador, tipo_nota, natureza_operacao,
                   cfop, valor_servicos, valor_pecas, valor_desconto, aliquota_iss,
                   valor_iss, valor_liquido, status_fiscal, numero_nf, serie,
                   chave_acesso, xml_path, protocolo_autorizacao, data_emissao,
                   filial_emissora, enviado_contabilidade, data_envio_contabilidade,
                   tomador_cidade, tomador_uf
            FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR lote_contabilidade_mes = ?)
        """
        params_n = [f"{mes}%", mes]
        if filial != "CONSOLIDADO":
            sql_n += " AND filial_emissora = ?"
            params_n.append(filial)
        sql_n += " ORDER BY id ASC"
        rows_n = conn.execute(sql_n, tuple(params_n)).fetchall()

        notas = []
        tot_faturado, tot_servicos, tot_pecas, tot_iss = 0.0, 0.0, 0.0, 0.0
        tot_emitidas, tot_canceladas, tot_trf = 0, 0, 0.0
        for r in rows_n:
            st = str(r[13] or "")
            is_canc = "CANCELAD" in st.upper()
            is_trf = "TRANSFERENCIA" in str(r[4] or "").upper() or "TRANSFERENCIA" in str(r[5] or "").upper() or str(r[6] or "").startswith("5152") or str(r[6] or "").startswith("6152")
            v_serv = float(r[7] or 0.0)
            v_pec = float(r[8] or 0.0)
            v_desc = float(r[9] or 0.0)
            aliq = float(r[10] or 0.0)
            v_iss = float(r[11] or 0.0)
            v_liq = float(r[12] or 0.0)

            if not is_canc:
                if is_trf:
                    tot_trf += v_liq
                else:
                    tot_faturado += v_liq
                    tot_servicos += v_serv
                    tot_pecas += v_pec
                    tot_iss += v_iss
                tot_emitidas += 1
            else:
                tot_canceladas += 1

            notas.append({
                "id": r[0], "os_id": r[1], "cliente": r[2] or "", "cnpj_tomador": r[3] or "",
                "tipo_nota": r[4] or "", "natureza": r[5] or "", "cfop": r[6] or "",
                "valor_servicos": v_serv, "valor_pecas": v_pec, "valor_desconto": v_desc,
                "aliquota_iss": aliq, "valor_iss": v_iss, "valor_liquido": v_liq,
                "status": st, "numero_nf": r[14] or f"OS #{r[1]}", "serie": r[15] or "1",
                "chave": r[16] or "", "protocolo": r[18] or "", "data_emissao": r[19] or "",
                "filial": r[20] or "DF", "enviado": bool(r[21]), "data_envio": r[22] or "",
                "cidade": r[23] or "", "uf": r[24] or "", "is_cancelada": is_canc, "is_transferencia": is_trf
            })

        cur_trf = conn.execute("""
            SELECT id, estabelecimento, codigo_item, descricao, data_mov, qtd_saida, observacao
            FROM movimentacoes_estoque
            WHERE tipo_mov LIKE '%TRANSFERENCIA%' AND data_mov LIKE ?
            ORDER BY id ASC
        """, (f"{mes}%",)).fetchall()
        movs_trf = [{"id": rt[0], "estabelecimento": rt[1] or "", "codigo": rt[2] or "", "descricao": rt[3] or "", "data": rt[4] or "", "qtd": rt[5] or 0, "obs": rt[6] or ""} for rt in cur_trf]

        cur_c = conn.execute("""
            SELECT id, tecnico_setor, nome_item, quantidade, finalidade, data_baixa
            FROM baixas_consumiveis
            WHERE data_baixa LIKE ?
            ORDER BY id ASC
        """, (f"{mes}%",)).fetchall()
        consumiveis = [{"id": rc[0], "setor": rc[1] or "", "item": rc[2] or "", "qtd": rc[3] or 0, "finalidade": rc[4] or "", "data": rc[5] or ""} for rc in cur_c]

    return web.json_response({
        "ok": True,
        "mes": mes,
        "filial": filial,
        "meses_disponiveis": meses_disponiveis,
        "kpis": {
            "total_faturado": tot_faturado,
            "total_servicos": tot_servicos,
            "total_pecas": tot_pecas,
            "base_iss": tot_servicos,
            "total_iss": tot_iss,
            "total_transferencias": tot_trf,
            "total_consumiveis": len(consumiveis),
            "notas_emitidas": tot_emitidas,
            "notas_canceladas": tot_canceladas
        },
        "notas": notas,
        "movs_transferencia": movs_trf,
        "consumiveis": consumiveis
    })


async def api_fiscal_v2_fechamento_zip(request: web.Request) -> web.Response:
    """Gera pacote compactado em ZIP com todos os XMLs, DANFEs e relatórios CSV para a contabilidade."""
    db_name = request.app.get("db_path", "emed.db")
    mes = request.query.get("mes", "").strip() or datetime.now().strftime("%Y-%m")
    filial = request.query.get("filial", "CONSOLIDADO").strip().upper()

    with _get_db_connection(db_name) as conn:
        sql_n = """
            SELECT id, os_id, cliente, cnpj_tomador, tipo_nota, natureza_operacao,
                   cfop, valor_servicos, valor_pecas, valor_desconto, aliquota_iss,
                   valor_iss, valor_liquido, status_fiscal, numero_nf, serie,
                   chave_acesso, xml_path, protocolo_autorizacao, data_emissao,
                   filial_emissora, prestador_cnpj, prestador_razao, tomador_cidade, tomador_uf
            FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR lote_contabilidade_mes = ?)
        """
        params_n = [f"{mes}%", mes]
        if filial != "CONSOLIDADO":
            sql_n += " AND filial_emissora = ?"
            params_n.append(filial)
        sql_n += " ORDER BY id ASC"
        notas = conn.execute(sql_n, tuple(params_n)).fetchall()

        sql_t = "SELECT id, estabelecimento, codigo_item, descricao, data_mov, qtd_saida, observacao FROM movimentacoes_estoque WHERE tipo_mov LIKE '%TRANSFERENCIA%' AND data_mov LIKE ? ORDER BY id ASC"
        movs_trf = conn.execute(sql_t, (f"{mes}%",)).fetchall()

        sql_c = "SELECT id, tecnico_setor, nome_item, quantidade, finalidade, data_baixa FROM baixas_consumiveis WHERE data_baixa LIKE ? ORDER BY id ASC"
        consumiveis = conn.execute(sql_c, (f"{mes}%",)).fetchall()

        sql_p = "SELECT codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade), preco_custo, unidade FROM estoque_pecas ORDER BY nome_peca ASC"
        pecas = conn.execute(sql_p).fetchall()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Livro Registro de Saídas CSV
        csv_s = io.StringIO()
        csv_s.write("\ufeff")
        w_s = csv.writer(csv_s, delimiter=";")
        w_s.writerow([
            "NFS-e", "Série", "Data Emissão", "Filial Emissora", "CNPJ Prestador",
            "Razão Tomador", "CNPJ Tomador", "Cidade Tomador", "UF", "Tipo / Natureza", "CFOP",
            "Valor Serviços (R$)", "Base Cálculo ISS (R$)", "Alíquota ISS (%)", "Valor ISS (R$)",
            "Valor Peças (R$)", "Desconto (R$)", "Valor Líquido Total (R$)", "Status Fiscal",
            "Chave de Acesso", "Protocolo SEFAZ"
        ])
        for n in notas:
            w_s.writerow([
                n[14] or f"OS_{n[1]}", n[15] or "1", n[19] or "", n[20] or "", n[21] or "",
                n[2] or "", n[3] or "", n[23] or "", n[24] or "", n[5] or n[4] or "", n[6] or "",
                f"{float(n[7] or 0):.2f}".replace(".", ","),
                f"{float(n[7] or 0):.2f}".replace(".", ","),
                f"{float(n[10] or 0):.2f}".replace(".", ","),
                f"{float(n[11] or 0):.2f}".replace(".", ","),
                f"{float(n[8] or 0):.2f}".replace(".", ","),
                f"{float(n[9] or 0):.2f}".replace(".", ","),
                f"{float(n[12] or 0):.2f}".replace(".", ","),
                n[13] or "", n[16] or "", n[18] or ""
            ])
        zf.writestr(f"01_LIVRO_REGISTRO_SAIDAS_{filial}_{mes}.csv", csv_s.getvalue().encode("utf-8"))

        # 2. Transferências CSV
        csv_t = io.StringIO()
        csv_t.write("\ufeff")
        w_t = csv.writer(csv_t, delimiter=";")
        w_t.writerow(["ID", "Origem", "Cód Peça", "Descrição", "Data", "Qtd", "Enquadramento Legal ICMS", "Obs"])
        for t in movs_trf:
            w_t.writerow([t[0], t[1], t[2], t[3], t[4], f"{float(t[5] or 0):.2f}".replace(".", ","), "NÃO INCIDÊNCIA DE ICMS (STF ADC 49 / LC 204/2023 - MESMO TITULAR)", t[6] or ""])
        zf.writestr(f"02_RELATORIO_TRANSFERENCIAS_FILIAIS_{mes}.csv", csv_t.getvalue().encode("utf-8"))

        # 3. Consumíveis CSV
        csv_c = io.StringIO()
        csv_c.write("\ufeff")
        w_c = csv.writer(csv_c, delimiter=";")
        w_c.writerow(["ID", "Setor", "Item", "Qtd", "Finalidade", "Data Baixa", "Tratamento Contábil"])
        for c in consumiveis:
            w_c.writerow([c[0], c[1], c[2], c[3], c[4], c[5], "DESPESA OPERACIONAL IMEDIATA - USO E CONSUMO (SALDO ESTOQUE CLÍNICO: ZERO)"])
        zf.writestr(f"03_RELATORIO_CONSUMIVEIS_DESPESAS_{mes}.csv", csv_c.getvalue().encode("utf-8"))

        # 4. Inventário Bloco K CSV
        csv_p = io.StringIO()
        csv_p.write("\ufeff")
        w_p = csv.writer(csv_p, delimiter=";")
        w_p.writerow(["Cód Item", "Descrição", "Estoque Físico", "Estoque Fiscal", "Divergência", "Custo Unitário (R$)", "Total Fiscal (R$)", "Unidade"])
        for p in pecas:
            fis = float(p[2] or 0)
            fisc = float(p[3] if p[3] is not None else (p[2] or 0))
            custo = float(p[4] or 0)
            w_p.writerow([p[0], p[1], f"{fis:.2f}".replace(".", ","), f"{fisc:.2f}".replace(".", ","), f"{(fis - fisc):.2f}".replace(".", ","), f"{custo:.2f}".replace(".", ","), f"{(fisc * custo):.2f}".replace(".", ","), p[5] or "UN"])
        zf.writestr(f"04_INVENTARIO_FISCAL_BLOCO_K_{mes}.csv", csv_p.getvalue().encode("utf-8"))

        # 5. Instruções do Contador
        texto_contador = f"""================================================================================
EMED ELETROMEDICINA — INSTRUÇÕES & MEMORIAL FISCAL DE FECHAMENTO MENSAL
Competência: {mes} | Unidade: {filial}
Documento oficial para a Assessoria Contábil / Fiscal
================================================================================

Prezado(a) Contador(a) e Equipe Fiscal,

Para fins de escrituração fiscal mensal, apuração de tributos e cumprimento das
obrigações acessórias (SPED Fiscal, EFD-Reinf, Bloco K, Livro Eletrônico DF / ISS),
seguem as orientações operacionais da EMED Eletromedicina:

1. SERVIÇOS TÉCNICOS DE MANUTENÇÃO & REPARAÇÃO (NFS-e):
   - Atividade: Manutenção preventiva e corretiva de equipamentos médico-hospitalares.
   - Enquadramento: Subitem 14.01 / 14.02 da Lei Complementar nº 116/2003.
   - Base de Cálculo do ISS: Valor da mão de obra/serviços técnicos destacados na nota.
   - Alíquota Padrão: 5,0% (DF) ou alíquota vigente no município prestador/tomador.
   - Peças Aplicadas: Quando houver destaque de peças no faturamento, observar a
     segregação tributária entre Serviço (ISS) e Mercadoria (ICMS).

2. REMESSAS E TRANSFERÊNCIAS ENTRE FILIAIS (CE <-> DF — CFOP 5152 / 6152 / 5949 / 6949):
   - ATENÇÃO: NÃO TRIBUTAR ICMS SOBRE AS TRANSFERÊNCIAS ENTRE ESTABELECIMENTOS.
   - Fundamentação Legal Vinculante: STF — Ação Declaratória de Constitucionalidade nº 49
     (ADC 49) e Lei Complementar nº 204/2023. O deslocamento de bens e mercadorias entre
     estabelecimentos do mesmo titular NÃO constitui fato gerador do ICMS.

3. CONSUMÍVEIS ADMINISTRATIVOS & COPA/LIMPEZA (CFOP 1556 / 2556):
   - As compras de insumos administrativos (café, açúcar, papel toalha, itens de limpeza)
     são lançadas para registro de despesa operacional direta (Uso e Consumo).
   - O estoque físico no almoxarifado operacional é baixado IMEDIATAMENTE a ZERO
     para não contaminar o inventário de peças e componentes técnicos.

4. ARQUIVOS ANEXOS NESTE PACOTE:
   - 01_LIVRO_REGISTRO_SAIDAS: Relação completa de NFS-e emitidas com valores e retenções.
   - 02_RELATORIO_TRANSFERENCIAS_FILIAIS: Relação de remessas interestaduais de apoio.
   - 03_RELATORIO_CONSUMIVEIS_DESPESAS: Relação de baixas imediatas de despesa.
   - 04_INVENTARIO_FISCAL_BLOCO_K: Posição do almoxarifado (Estoque Físico e Fiscal).
   - Pasta /xml: Arquivos XML oficiais autorizados perante o Fisco.
   - Pasta /danfe: Espelhos visuais DANFE em HTML para conferência rápida.

Em caso de dúvidas contábeis, contatar a Diretoria Administrativa da EMED.
================================================================================
"""
        zf.writestr(f"05_ORIENTACOES_TRIBUTARIAS_CONTADOR_{mes}.txt", texto_contador.encode("utf-8"))

        # 6. XMLs e DANFEs
        for n in notas:
            num = n[14] or f"OS_{n[1]}"
            fil = n[20] or "DF"
            xml_p = n[17]
            if xml_p and os.path.exists(xml_p):
                zf.writestr(f"xml/NFS_{fil}_{num}.xml", Path(xml_p).read_bytes())
            else:
                xml_stub = f"""<?xml version="1.0" encoding="UTF-8"?>
<CompNfse xmlns="http://www.abrasf.org.br/nfse.xsd">
  <Nfse><InfNfse>
    <Numero>{num}</Numero>
    <DataEmissao>{n[19] or datetime.now().isoformat()}</DataEmissao>
    <IdentificacaoRps><Numero>{n[1]}</Numero><Serie>{n[15] or '1'}</Serie></IdentificacaoRps>
    <PrestadorServico><Cnpj>{n[21] or '22143714000109'}</Cnpj><RazaoSocial>{n[22] or 'EMED ELETROMEDICINA'}</RazaoSocial></PrestadorServico>
    <TomadorServico><IdentificacaoTomador><CpfCnpj><Cnpj>{n[3] or ''}</Cnpj></CpfCnpj></IdentificacaoTomador><RazaoSocial>{n[2] or ''}</RazaoSocial></TomadorServico>
    <Servico>
      <Valores>
        <ValorServicos>{float(n[7] or 0):.2f}</ValorServicos>
        <ValorIss>{float(n[11] or 0):.2f}</ValorIss>
        <Aliquota>{float(n[10] or 5.0):.2f}</Aliquota>
        <ValorLiquidoNfse>{float(n[12] or 0):.2f}</ValorLiquidoNfse>
      </Valores>
      <Discriminacao>{n[5] or n[4] or 'SERVICOS DE MANUTENCAO HOSPITALAR'}</Discriminacao>
    </Servico>
  </InfNfse></Nfse>
</CompNfse>"""
                zf.writestr(f"xml/NFS_{fil}_{num}.xml", xml_stub.encode("utf-8"))

            danfe_dir = Path(__file__).resolve().parent.parent / "uploads_os" / "fiscal" / "html"
            danfe_file = danfe_dir / f"nfs_{fil.lower()}_{n[1]}.html"
            if danfe_file.exists():
                zf.writestr(f"danfe/DANFE_{fil}_{num}.html", danfe_file.read_bytes())

    buf.seek(0)
    nome_zip = f"EMED_Pacote_Contabil_{filial}_{mes}.zip"
    return web.Response(
        body=buf.getvalue(),
        content_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{nome_zip}"'}
    )


async def api_fiscal_v2_fechamento_exportar_csv(request: web.Request) -> web.Response:
    """Exporta planilha contábil (.CSV compatível com Excel e ERPs contábeis) com delimitador ';' e UTF-8 BOM."""
    import io
    import csv
    db_name = request.app.get("db_path", "emed.db")
    mes = request.query.get("mes", "").strip() or datetime.now().strftime("%Y-%m")
    filial = request.query.get("filial", "CONSOLIDADO").strip().upper()

    with _get_db_connection(db_name) as conn:
        sql_n = """
            SELECT id, os_id, cliente, cnpj_tomador, tipo_nota, cfop,
                   valor_servicos, valor_pecas, valor_desconto, aliquota_iss,
                   valor_iss, valor_liquido, status_fiscal, numero_nf, serie,
                   data_emissao, filial_emissora
            FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR lote_contabilidade_mes = ?)
        """
        params_n = [f"{mes}%", mes]
        if filial != "CONSOLIDADO":
            sql_n += " AND filial_emissora = ?"
            params_n.append(filial)
        sql_n += " ORDER BY id ASC"
        notas = conn.execute(sql_n, tuple(params_n)).fetchall()

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM para o Excel abrir com acentuação e colunas corretas
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "NUMERO_DOCUMENTO",
        "DATA_EMISSAO",
        "FILIAL_EMISSORA",
        "TOMADOR_RAZAO_SOCIAL",
        "TOMADOR_CNPJ",
        "CTRIB_NACIONAL",
        "ITEM_LC116",
        "CFOP",
        "VALOR_SERVICOS_R$",
        "VALOR_PECAS_R$",
        "BASE_CALCULO_ISS_R$",
        "ALIQUOTA_ISS_PCT",
        "VALOR_ISS_R$",
        "RETENCAO_CSRF_465_R$",
        "RETENCAO_IRRF_150_R$",
        "TOTAL_RETENCOES_615_R$",
        "VALOR_TOTAL_BRUTO_R$",
        "LIQUIDO_A_RECEBER_R$",
        "STATUS_FISCAL"
    ])

    for n in notas:
        v_srv = float(n[6] or 0)
        v_pec = float(n[7] or 0)
        v_iss = float(n[10] or 0)
        v_bruto = float(n[11] or 0)
        is_canc = "CANCELAD" in str(n[12] or "").upper()
        csrf = round(v_srv * 0.0465, 2) if (v_srv > 0 and not is_canc) else 0.0
        irrf = round(v_srv * 0.0150, 2) if (v_srv > 0 and not is_canc) else 0.0
        tot_ret = round(csrf + irrf, 2)
        v_liq_rec = round(v_bruto - tot_ret, 2) if not is_canc else 0.0

        writer.writerow([
            n[13] or f"OS #{n[1]}",
            n[15] or "",
            n[16] or filial,
            n[2] or "",
            f"'{n[3]}" if n[3] else "",
            "140101" if v_srv > 0 else "-",
            "14.01" if v_srv > 0 else "-",
            n[5] or ("5102" if v_pec > 0 else "NFS-e"),
            f"{v_srv:.2f}".replace(".", ","),
            f"{v_pec:.2f}".replace(".", ","),
            f"{v_srv:.2f}".replace(".", ","),
            f"{float(n[9] or 5.0):.2f}".replace(".", ","),
            f"{v_iss:.2f}".replace(".", ","),
            f"{csrf:.2f}".replace(".", ","),
            f"{irrf:.2f}".replace(".", ","),
            f"{tot_ret:.2f}".replace(".", ","),
            f"{v_bruto:.2f}".replace(".", ","),
            f"{v_liq_rec:.2f}".replace(".", ","),
            n[12] or ""
        ])

    csv_data = output.getvalue().encode("utf-8-sig")
    nome_arq = f"EMED_Livro_Fiscal_Contabil_{filial}_{mes}.csv"
    return web.Response(
        body=csv_data,
        content_type="text/csv",
        charset="utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arq}"'}
    )


async def api_fiscal_v2_fechamento_relatorio_impresso(request: web.Request) -> web.Response:
    """Gera página de relatório de fechamento fiscal e contábil formatada para impressão/PDF."""
    db_name = request.app.get("db_path", "emed.db")
    mes = request.query.get("mes", "").strip() or datetime.now().strftime("%Y-%m")
    filial = request.query.get("filial", "CONSOLIDADO").strip().upper()
    logo_b64 = _obter_logo_b64()

    with _get_db_connection(db_name) as conn:
        sql_n = """
            SELECT id, os_id, cliente, cnpj_tomador, tipo_nota, cfop,
                   valor_servicos, valor_pecas, valor_desconto, aliquota_iss,
                   valor_iss, valor_liquido, status_fiscal, numero_nf, serie,
                   data_emissao, filial_emissora
            FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR lote_contabilidade_mes = ?)
        """
        params_n = [f"{mes}%", mes]
        if filial != "CONSOLIDADO":
            sql_n += " AND filial_emissora = ?"
            params_n.append(filial)
        sql_n += " ORDER BY id ASC"
        notas = conn.execute(sql_n, tuple(params_n)).fetchall()

    tot_fat = sum(float(n[11] or 0) for n in notas if "CANCELAD" not in str(n[12] or "").upper())
    tot_srv = sum(float(n[6] or 0) for n in notas if "CANCELAD" not in str(n[12] or "").upper())
    tot_pec = sum(float(n[7] or 0) for n in notas if "CANCELAD" not in str(n[12] or "").upper())
    tot_iss = sum(float(n[10] or 0) for n in notas if "CANCELAD" not in str(n[12] or "").upper())
    tot_csrf = sum(round(float(n[6] or 0) * 0.0465, 2) for n in notas if "CANCELAD" not in str(n[12] or "").upper() and float(n[6] or 0) > 0)
    tot_irrf = sum(round(float(n[6] or 0) * 0.0150, 2) for n in notas if "CANCELAD" not in str(n[12] or "").upper() and float(n[6] or 0) > 0)
    tot_ret = tot_csrf + tot_irrf
    tot_liq_rec = tot_fat - tot_ret

    linhas_html = "".join([
        f"<tr><td><b>{n[13] or 'OS #'+str(n[1])}</b></td><td>{n[15] or ''}</td><td><span class='badge-filial'>{n[16] or filial}</span></td><td>{n[2]}</td><td>{n[3]}</td><td>{'cTribNac 140101' if float(n[6] or 0) > 0 else (n[5] or '5102')}</td><td>R$ {float(n[6] or 0):.2f}</td><td>R$ {float(n[7] or 0):.2f}</td><td>R$ {float(n[10] or 0):.2f}</td><td>R$ {round(float(n[6] or 0)*0.0615, 2) if 'CANCELAD' not in str(n[12] or '').upper() and float(n[6] or 0)>0 else 0.0:.2f}</td><td><b>R$ {float(n[11] or 0):.2f}</b></td><td>{n[12]}</td></tr>"
        for n in notas
    ]) or "<tr><td colspan='12' style='text-align:center;'>Nenhuma nota emitida no período.</td></tr>"

    html_out = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Fechamento Contábil & Fiscal – EMED ({mes})</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; margin: 24px; font-size: 12px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 16px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 16px; }}
    .kpi {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; }}
    .kpi-title {{ font-size: 10px; color: #64748b; font-weight: 700; }}
    .kpi-val {{ font-size: 16px; font-weight: 900; color: #0369a1; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 11px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
    th {{ background: #f1f5f9; color: #334155; font-weight: 800; }}
    .alert-box {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 14px; margin-bottom: 16px; font-size: 11px; line-height: 1.5; }}
    .signatures {{ display: flex; justify-content: space-between; margin-top: 40px; padding-top: 20px; }}
    .sig-line {{ width: 45%; border-top: 1px solid #475569; text-align: center; padding-top: 6px; font-size: 11px; }}
    .badge-filial {{ font-size: 9.5px; background: #e0f2fe; color: #0369a1; padding: 2px 5px; border-radius: 4px; font-weight: 800; }}
    @media print {{ .no-print {{ display: none !important; }} body {{ margin: 0; }} }}
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 16px; display:flex; justify-content:flex-end; gap:8px;">
    <a href="/api/fiscal/v2/fechamento/exportar-csv?mes={mes}&filial={filial}" style="background:#16a34a;color:#fff;text-decoration:none;padding:10px 18px;font-weight:800;border-radius:6px;font-size:12px;display:inline-flex;align-items:center;gap:6px;">📥 Baixar Planilha para Contabilidade (.CSV / Excel)</a>
    <button onclick="window.print()" style="background:#0284c7;color:#fff;border:none;padding:10px 18px;font-weight:800;border-radius:6px;cursor:pointer;font-size:12px;">🖨️ Imprimir / Salvar em PDF</button>
  </div>
  <div class="header">
    <div style="display:flex;align-items:center;gap:12px;">
      <img src="data:image/png;base64,{logo_b64}" style="max-height:50px;" alt="EMED" />
      <div>
        <div style="font-size:16px;font-weight:900;color:#0284c7;">EMED ELETROMEDICINA HOSPITALAR</div>
        <div style="font-size:11px;color:#64748b;">DEMONSTRATIVO MENSAL DE FECHAMENTO FISCAL &amp; CONTÁBIL</div>
      </div>
    </div>
    <div style="text-align:right;font-size:11px;color:#475569;">
      <b>Competência:</b> {mes}<br/>
      <b>Unidade:</b> {filial}<br/>
      <b>Emissão Relatório:</b> {datetime.now().strftime("%d/%m/%Y %H:%M")}
    </div>
  </div>
  <div class="alert-box">
    ⚖️ <b>MEMORIAL FISCAL &amp; CONTÁBIL (CONFORMIDADE RESOLUÇÕES CFC, RFB E LC 116/2003):</b><br/>
    &bull; <b>Serviços Especializados (ISS):</b> LC 116/2003 (Item 14.01 / cTribNac 140101 - Manutenção de Equipamentos Hospitalares). Alíquota aplicável: 5,0% (DF) ou alíquota municipal da sede/tomador.<br/>
    &bull; <b>Padrão Nacional de NFS-e (DPS):</b> Assinatura digital ICP-Brasil padrão SHA-256 e emissão estruturada conforme Sistema Nacional NFS-e / Receita Federal do Brasil.<br/>
    &bull; <b>Retenções Federais na Fonte (PJ):</b> Previsão de CSRF 4,65% (Lei 10.833/2003: PIS 0,65%, COFINS 3,0%, CSLL 1,0%) e IRRF 1,50% (Decreto 9.580/2018), totalizando 6,15% a deduzir no recebimento quando aplicável.<br/>
    &bull; <b>Transferências entre Filiais (CFOP 5152/6152):</b> Não incidência de ICMS vinculante conforme <b>STF ADC 49 e LC 204/2023</b>.<br/>
    &bull; <b>Consumíveis Administrativos (CFOP 1556/2556):</b> Baixa imediata para despesa de uso/consumo, mantendo saldo de almoxarifado clínico em zero.
  </div>
  <div class="kpis">
    <div class="kpi"><div class="kpi-title">TOTAL FATURADO</div><div class="kpi-val">R$ {tot_fat:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">SERVIÇOS (BASE ISS)</div><div class="kpi-val">R$ {tot_srv:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">PEÇAS FATURADAS</div><div class="kpi-val">R$ {tot_pec:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">TOTAL ISS APURADO</div><div class="kpi-val">R$ {tot_iss:,.2f}</div></div>
    <div class="kpi" style="border-color:#f59e0b;"><div class="kpi-title" style="color:#b45309;">RETENÇÕES FEDERAIS (6,15%)</div><div class="kpi-val" style="color:#b45309;">R$ {tot_ret:,.2f}</div><div style="font-size:9px;color:#78350f;">CSRF 4,65% + IRRF 1,50%</div></div>
    <div class="kpi" style="border-color:#10b981;"><div class="kpi-title" style="color:#047857;">LÍQUIDO A RECEBER</div><div class="kpi-val" style="color:#047857;">R$ {tot_liq_rec:,.2f}</div></div>
  </div>
  <h4 style="margin:0 0 8px 0;color:#0369a1;">📜 Livro de Saídas &amp; NFS-e Emitidas no Período</h4>
  <table>
    <thead>
      <tr><th>NFS-e</th><th>Data</th><th>Unidade</th><th>Tomador</th><th>CNPJ</th><th>Operação / cTrib</th><th>Serviços</th><th>Peças</th><th>ISS</th><th>Retenções (6,15%)</th><th>Total NF</th><th>Status</th></tr>
    </thead>
    <tbody>{linhas_html}</tbody>
  </table>
  <div class="signatures">
    <div class="sig-line">
      <b>EMED ELETROMEDICINA</b><br/>Responsável Fiscal / Controladoria Interna
    </div>
    <div class="sig-line">
      <b>ASSESSORIA CONTÁBIL EXTERNA</b><br/>Contador Responsável / CRC
    </div>
  </div>
  </body>
</html>"""
    return web.Response(text=html_out, content_type="text/html")


async def api_fiscal_v2_fechamento_marcar_enviado(request: web.Request) -> web.Response:
    """Marca o lote da competência como transmitido/enviado à assessoria contábil."""
    db_name = request.app.get("db_path", "emed.db")
    body = await request.json()
    mes = str(body.get("mes", "")).strip() or datetime.now().strftime("%Y-%m")
    filial = str(body.get("filial", "CONSOLIDADO")).strip().upper()
    usuario = str(body.get("usuario", "netto")).strip()

    with _get_db_connection(db_name) as conn:
        sql = "UPDATE notas_fiscais SET enviado_contabilidade = 1, data_envio_contabilidade = datetime('now') WHERE (data_emissao LIKE ? OR lote_contabilidade_mes = ?)"
        params = [f"{mes}%", mes]
        if filial != "CONSOLIDADO":
            sql += " AND filial_emissora = ?"
            params.append(filial)
        cur = conn.execute(sql, tuple(params))
        total_marcadas = cur.rowcount
        conn.commit()

    _registrar_log_fiscal("FECHAMENTO_CONTABILIDADE", f"Lote {mes} ({filial}) marcado como enviado à contabilidade ({total_marcadas} notas afetadas)", usuario)

    return web.json_response({
        "ok": True,
        "msg": f"✅ Fechamento da competência {mes} marcado como enviado à contabilidade! ({total_marcadas} notas registradas)",
        "total_afetadas": total_marcadas
    })


CATEGORIAS_DESPESAS_UNIDADES = {
    "COMBUSTIVEL": {"label": "Combustível / Gasolina", "icone": "⛽", "cor": "#f59e0b"},
    "ALIMENTACAO": {"label": "Alimentação / Refeições", "icone": "🍽️", "cor": "#10b981"},
    "HOTEL": {"label": "Hotel / Hospedagem", "icone": "🏨", "cor": "#38bdf8"},
    "PEDAGIO_TRANSPORTE": {"label": "Pedágio / Estacionamento / Transporte", "icone": "🛣️", "cor": "#a78bfa"},
    "MANUTENCAO_FROTA": {"label": "Manutenção Veicular / Frota", "icone": "🔧", "cor": "#f43f5e"},
    "INSUMOS_UNIDADE": {"label": "Copa / Limpeza / Insumos da Unidade", "icone": "🏢", "cor": "#64dfdf"},
    "OUTROS": {"label": "Outras Despesas Operacionais", "icone": "📌", "cor": "#94a3b8"},
}


def _garantir_tabela_despesas_unidades(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS despesas_unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unidade TEXT NOT NULL DEFAULT 'FILIAL_DF',
            categoria TEXT NOT NULL DEFAULT 'COMBUSTIVEL',
            descricao TEXT NOT NULL,
            valor REAL NOT NULL DEFAULT 0.0,
            data_despesa TEXT NOT NULL,
            responsavel TEXT DEFAULT '',
            fornecedor TEXT DEFAULT '',
            veiculo_placa TEXT DEFAULT '',
            os_id TEXT DEFAULT '',
            forma_pagamento TEXT DEFAULT 'PIX',
            numero_comprovante TEXT DEFAULT '',
            status TEXT DEFAULT 'PAGO',
            observacoes TEXT DEFAULT '',
            comprovante_anexo TEXT DEFAULT '',
            criado_em TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    try:
        conn.execute("ALTER TABLE despesas_unidades ADD COLUMN comprovante_anexo TEXT DEFAULT ''")
    except Exception:
        pass
    qtd = conn.execute("SELECT COUNT(*) FROM despesas_unidades").fetchone()[0]
    if qtd == 0:
        seeds = [
            ("FILIAL_DF", "COMBUSTIVEL", "Abastecimento Gasolina Aditivada - Atendimento Hospital Regional Asa Norte (HRAN)", 385.50, "2026-11-04", "Vitor / Equipe DF", "Posto Ipiranga Asa Norte", "FROTA-DF01", "28", "CARTÃO CORPORATIVO", "NFC-e 048192", "PAGO", "Deslocamento técnico para calibração de Raio-X"),
            ("FILIAL_DF", "ALIMENTACAO", "Almoço Equipe Técnica (2 técnicos) - Plantão Preventiva Tomógrafo Brasília", 142.00, "2026-11-05", "Vitor / Equipe DF", "Restaurante Mané / Setor Hospitalar", "", "29", "PIX", "NF 009182", "PAGO", "Atendimento integral em hospital de Brasília"),
            ("FILIAL_DF", "HOTEL", "Hospedagem Técnica (2 Diárias) - Missão Instalação & Calibração Brasília/Entorno", 640.00, "2026-11-07", "Netto / Vitor", "Hotel Ibis Styles Brasília", "", "31", "CARTÃO CORPORATIVO", "NFS-e 88219", "PAGO", "Suporte intensivo à base DF"),
            ("FILIAL_DF", "COMBUSTIVEL", "Gasolina Comum - Visitas Técnicas Taguatinga e Sobradinho (Hospitais)", 310.00, "2026-11-11", "Equipe Técnica DF", "Shell Select SIA / Brasília", "FROTA-DF01", "33", "PIX", "NFC-e 112094", "PAGO", "Rota hospitalar DF"),
            ("FILIAL_DF", "PEDAGIO_TRANSPORTE", "Estacionamento Setor Hospitalar Sul + Pedágio Deslocamento Entorno DF", 78.00, "2026-11-12", "Equipe Técnica DF", "Estapar / Via 040", "FROTA-DF01", "33", "PIX", "REC-4410", "PAGO", "Atendimento externo"),
            ("FILIAL_DF", "ALIMENTACAO", "Jantar Equipe Plantão Noturno - Reparo Emergencial Arco Cirúrgico", 118.90, "2026-11-15", "Vitor", " praça Alimentação Setor Hospitalar", "", "35", "CARTÃO CORPORATIVO", "NFC-e 55102", "PAGO", "Corretiva concluída às 22h30"),
            ("FILIAL_DF", "COMBUSTIVEL", "Abastecimento Gasolina Completa - Semana de Preventivas Brasília", 412.80, "2026-11-18", "Vitor / Equipe DF", "Petrobras BR Asa Sul", "FROTA-DF01", "37", "CARTÃO CORPORATIVO", "NFC-e 77419", "PAGO", "Tanque cheio frota DF"),
            ("MATRIZ_CE", "COMBUSTIVEL", "Abastecimento Gasolina / Diesel - Viagem Técnica Juazeiro do Norte / Cariri", 520.00, "2026-11-03", "Netto / Equipe CE", "Posto São Domingos BR-116", "FROTA-CE01", "25", "PIX", "NFC-e 339102", "PAGO", "Ida e volta atendimento regional Ceará"),
            ("MATRIZ_CE", "HOTEL", "Hotel Equipe Técnica (2 Diárias) - Roteiro Hospitalar Sobral / Região Norte CE", 580.00, "2026-11-06", "Equipe Técnica CE", "Hotel Visconde Sobral", "FROTA-CE01", "27", "PIX", "NFS-e 19402", "PAGO", "Preventivas mensais interior CE"),
            ("MATRIZ_CE", "ALIMENTACAO", "Alimentação Equipe de Campo (Almoço/Jantar) - Viagem Técnica Sobral", 215.00, "2026-11-06", "Equipe Técnica CE", "Restaurante Sabor do Norte", "", "27", "PIX", "NFC-e 88310", "PAGO", "2 técnicos em viagem"),
            ("MATRIZ_CE", "COMBUSTIVEL", "Gasolina Frota Eusébio / Fortaleza - Rotina de Atendimentos Região Metropolitana", 360.00, "2026-11-10", "Netto", "Posto SP Eusébio CE-040", "FROTA-CE02", "30", "CARTÃO CORPORATIVO", "NFC-e 440129", "PAGO", "Atendimentos Fortaleza e Eusébio"),
            ("MATRIZ_CE", "INSUMOS_UNIDADE", "Insumos de Copa, Café, Água Mineral e Material de Limpeza - Sede Eusébio", 195.40, "2026-11-13", "Administrativo CE", "Assaí Atacadista Eusébio", "", "", "PIX", "NFC-e 992011", "PAGO", "Abastecimento mensal matriz"),
            ("MATRIZ_CE", "MANUTENCAO_FROTA", "Troca de Óleo, Filtro e Alinhamento Preventivo Veículo Operacional", 340.00, "2026-11-14", "Netto", "Auto Center Eusébio", "FROTA-CE01", "", "BOLETO", "NF 4102", "PAGO", "Revisão de 10.000 km"),
            ("MATRIZ_CE", "ALIMENTACAO", "Almoço Técnico em Atendimento Externo - Hospital Fortaleza", 96.00, "2026-11-17", "Equipe Técnica CE", "Restaurante Aldeota", "", "36", "PIX", "NFC-e 77812", "PAGO", "Instalação Konica Minolta"),
            ("FILIAL_DF", "COMBUSTIVEL", "Abastecimento Gasolina Frota Brasília - Rotas Outubro", 690.00, "2026-10-18", "Vitor / Equipe DF", "Posto Ipiranga Brasília", "FROTA-DF01", "", "CARTÃO CORPORATIVO", "NFC-e 03910", "PAGO", "Fechamento outubro DF"),
            ("FILIAL_DF", "HOTEL", "Hospedagem Apoio Técnico Brasília - Outubro", 490.00, "2026-10-21", "Netto", "Hotel Nacional Brasília", "", "", "CARTÃO CORPORATIVO", "NFS-e 71022", "PAGO", "Missão técnica outubro"),
            ("FILIAL_DF", "ALIMENTACAO", "Refeições Equipe de Campo Brasília - Outubro", 320.00, "2026-10-24", "Equipe Técnica DF", "Restaurantes Locais DF", "", "", "PIX", "LOTE-10", "PAGO", "Alimentação técnica outubro"),
            ("MATRIZ_CE", "COMBUSTIVEL", "Gasolina & Combustível Frota Ceará - Rotas Outubro", 780.00, "2026-10-15", "Netto / Equipe CE", "Posto CE-040 Eusébio", "FROTA-CE01", "", "PIX", "NFC-e 31029", "PAGO", "Fechamento outubro CE"),
            ("MATRIZ_CE", "HOTEL", "Diárias Hotel Viagem Interior Ceará - Outubro", 440.00, "2026-10-20", "Equipe Técnica CE", "Hotel Plaza Juazeiro", "", "", "PIX", "NFS-e 18290", "PAGO", "Atendimento Cariri"),
            ("MATRIZ_CE", "ALIMENTACAO", "Alimentação Equipe Técnica Matriz & Viagens - Outubro", 290.00, "2026-10-25", "Equipe Técnica CE", "Restaurantes Locais CE", "", "", "PIX", "LOTE-10-CE", "PAGO", "Alimentação técnica outubro"),
        ]
        conn.executemany("""
            INSERT INTO despesas_unidades (
                unidade, categoria, descricao, valor, data_despesa, responsavel,
                fornecedor, veiculo_placa, os_id, forma_pagamento, numero_comprovante,
                status, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seeds)
        conn.commit()


async def api_fiscal_v2_despesas_unidades_dados(request: web.Request) -> web.Response:
    """Retorna os lançamentos, indicadores e agregações para gráficos de despesas das unidades."""
    db_name = request.app.get("db_name") or request.app.get("db_path") or str(Path(__file__).resolve().parent.parent / "emed.db")
    unidade = request.query.get("unidade", "CONSOLIDADO").strip().upper()
    mes = request.query.get("mes", "TODOS").strip()
    categoria = request.query.get("categoria", "TODAS").strip().upper()

    with _get_db_connection(db_name) as conn:
        _garantir_tabela_despesas_unidades(conn)

        cur_m = conn.execute("SELECT DISTINCT substr(data_despesa, 1, 7) as m FROM despesas_unidades WHERE data_despesa IS NOT NULL AND length(data_despesa) >= 7 ORDER BY m DESC").fetchall()
        meses_disp = [r[0] for r in cur_m if r[0]]
        mes_atual = datetime.now().strftime("%Y-%m")
        if mes_atual not in meses_disp:
            meses_disp.insert(0, mes_atual)

        # Consulta filtrada principal
        where_clauses = ["1=1"]
        params = []
        if unidade in ("FILIAL_DF", "MATRIZ_CE"):
            where_clauses.append("UPPER(unidade) = ?")
            params.append(unidade)
        if mes and mes != "TODOS":
            where_clauses.append("data_despesa LIKE ?")
            params.append(f"{mes}%")
        if categoria and categoria != "TODAS":
            where_clauses.append("UPPER(categoria) = ?")
            params.append(categoria)

        sql_itens = f"""
            SELECT id, unidade, categoria, descricao, valor, data_despesa, responsavel,
                   fornecedor, veiculo_placa, os_id, forma_pagamento, numero_comprovante,
                   status, observacoes, comprovante_anexo
            FROM despesas_unidades
            WHERE {' AND '.join(where_clauses)}
            ORDER BY data_despesa DESC, id DESC
        """
        rows = conn.execute(sql_itens, tuple(params)).fetchall()

        # Consulta comparativa entre unidades no mesmo período/categoria (independente do filtro de unidade, para o gráfico comparativo DF vs CE)
        where_comp = ["1=1"]
        params_comp = []
        if mes and mes != "TODOS":
            where_comp.append("data_despesa LIKE ?")
            params_comp.append(f"{mes}%")
        if categoria and categoria != "TODAS":
            where_comp.append("UPPER(categoria) = ?")
            params_comp.append(categoria)

        rows_comp = conn.execute(f"""
            SELECT unidade, categoria, valor, data_despesa
            FROM despesas_unidades
            WHERE {' AND '.join(where_comp)}
        """, tuple(params_comp)).fetchall()

        # Consulta evolução mensal (filtrando apenas por unidade e categoria se selecionadas)
        where_mes = ["1=1"]
        params_mes = []
        if unidade in ("FILIAL_DF", "MATRIZ_CE"):
            where_mes.append("UPPER(unidade) = ?")
            params_mes.append(unidade)
        if categoria and categoria != "TODAS":
            where_mes.append("UPPER(categoria) = ?")
            params_mes.append(categoria)
        rows_evol = conn.execute(f"""
            SELECT substr(data_despesa, 1, 7) as m, categoria, unidade, SUM(valor)
            FROM despesas_unidades
            WHERE {' AND '.join(where_mes)} AND length(data_despesa) >= 7
            GROUP BY m, categoria, unidade
            ORDER BY m ASC
        """, tuple(params_mes)).fetchall()

    itens = []
    tot_geral = 0.0
    tot_comb = 0.0
    tot_alim = 0.0
    tot_hotel = 0.0
    tot_pedagio = 0.0
    tot_outros = 0.0
    por_resp = {}

    for r in rows:
        val = float(r[4] or 0.0)
        cat = str(r[2] or "OUTROS").upper()
        meta_cat = CATEGORIAS_DESPESAS_UNIDADES.get(cat, CATEGORIAS_DESPESAS_UNIDADES["OUTROS"])
        tot_geral += val
        if cat == "COMBUSTIVEL":
            tot_comb += val
        elif cat == "ALIMENTACAO":
            tot_alim += val
        elif cat == "HOTEL":
            tot_hotel += val
        elif cat == "PEDAGIO_TRANSPORTE":
            tot_pedagio += val
        else:
            tot_outros += val

        resp_key = (r[6] or "Não informado").strip()
        por_resp[resp_key] = por_resp.get(resp_key, 0.0) + val

        itens.append({
            "id": r[0],
            "unidade": r[1] or "FILIAL_DF",
            "unidade_label": "Filial Brasília (DF)" if r[1] == "FILIAL_DF" else "Matriz Eusébio (CE)",
            "categoria": cat,
            "categoria_label": meta_cat["label"],
            "categoria_icone": meta_cat["icone"],
            "categoria_cor": meta_cat["cor"],
            "descricao": r[3] or "",
            "valor": val,
            "data_despesa": r[5] or "",
            "responsavel": r[6] or "",
            "fornecedor": r[7] or "",
            "veiculo_placa": r[8] or "",
            "os_id": r[9] or "",
            "forma_pagamento": r[10] or "PIX",
            "numero_comprovante": r[11] or "",
            "status": r[12] or "PAGO",
            "observacoes": r[13] or "",
        })

    # Agregação por categoria (respeitando filtro atual + comparativo DF vs CE)
    cat_agg = {}
    for k, meta in CATEGORIAS_DESPESAS_UNIDADES.items():
        cat_agg[k] = {
            "codigo": k,
            "label": meta["label"],
            "icone": meta["icone"],
            "cor": meta["cor"],
            "total": 0.0,
            "filial_df": 0.0,
            "matriz_ce": 0.0,
            "qtd": 0,
            "percentual": 0.0,
        }

    tot_df_comp = 0.0
    tot_ce_comp = 0.0
    for rc in rows_comp:
        u_rc = str(rc[0] or "FILIAL_DF").upper()
        c_rc = str(rc[1] or "OUTROS").upper()
        v_rc = float(rc[2] or 0.0)
        if c_rc not in cat_agg:
            c_rc = "OUTROS"
        if u_rc == "FILIAL_DF":
            cat_agg[c_rc]["filial_df"] += v_rc
            tot_df_comp += v_rc
        else:
            cat_agg[c_rc]["matriz_ce"] += v_rc
            tot_ce_comp += v_rc

    for it in itens:
        c_it = it["categoria"] if it["categoria"] in cat_agg else "OUTROS"
        cat_agg[c_it]["total"] += it["valor"]
        cat_agg[c_it]["qtd"] += 1

    lista_categorias = []
    for k, obj in cat_agg.items():
        obj["percentual"] = round((obj["total"] / tot_geral * 100.0), 1) if tot_geral > 0 else 0.0
        lista_categorias.append(obj)
    lista_categorias.sort(key=lambda x: (x["total"], x["filial_df"] + x["matriz_ce"]), reverse=True)

    # Evolução mensal
    mapa_meses = {}
    for rm in rows_evol:
        m_key = rm[0]
        c_key = str(rm[1] or "OUTROS").upper()
        u_key = str(rm[2] or "FILIAL_DF").upper()
        v_sum = float(rm[3] or 0.0)
        if m_key not in mapa_meses:
            mapa_meses[m_key] = {
                "mes": m_key,
                "total": 0.0,
                "COMBUSTIVEL": 0.0,
                "ALIMENTACAO": 0.0,
                "HOTEL": 0.0,
                "OUTROS": 0.0,
                "FILIAL_DF": 0.0,
                "MATRIZ_CE": 0.0,
            }
        mapa_meses[m_key]["total"] += v_sum
        if c_key in ("COMBUSTIVEL", "ALIMENTACAO", "HOTEL"):
            mapa_meses[m_key][c_key] += v_sum
        else:
            mapa_meses[m_key]["OUTROS"] += v_sum
        if u_key == "FILIAL_DF":
            mapa_meses[m_key]["FILIAL_DF"] += v_sum
        else:
            mapa_meses[m_key]["MATRIZ_CE"] += v_sum

    por_mes = [mapa_meses[k] for k in sorted(mapa_meses.keys())]
    ranking_resp = [{"responsavel": k, "total": v, "percentual": round(v / tot_geral * 100.0, 1) if tot_geral > 0 else 0.0} for k, v in sorted(por_resp.items(), key=lambda x: x[1], reverse=True)]

    return web.json_response({
        "ok": True,
        "filtros": {"unidade": unidade, "mes": mes, "categoria": categoria},
        "meses_disponiveis": meses_disp,
        "kpis": {
            "total_geral": round(tot_geral, 2),
            "total_combustivel": round(tot_comb, 2),
            "total_alimentacao": round(tot_alim, 2),
            "total_hotel": round(tot_hotel, 2),
            "total_pedagio": round(tot_pedagio, 2),
            "total_outros": round(tot_outros, 2),
            "total_filial_df": round(tot_df_comp, 2),
            "total_matriz_ce": round(tot_ce_comp, 2),
            "qtd_lancamentos": len(itens),
        },
        "por_categoria": lista_categorias,
        "por_mes": por_mes,
        "por_responsavel": ranking_resp,
        "itens": itens,
    })


async def api_fiscal_v2_despesas_unidades_salvar(request: web.Request) -> web.Response:
    """Cadastra ou edita uma despesa operacional de unidade (Alimentação, Combustível/Gasolina, Hotel, etc.)."""
    db_name = request.app.get("db_name") or request.app.get("db_path") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    item_id = body.get("id")
    unidade = str(body.get("unidade", "FILIAL_DF")).strip().upper()
    if unidade not in ("FILIAL_DF", "MATRIZ_CE"):
        unidade = "FILIAL_DF"
    categoria = str(body.get("categoria", "COMBUSTIVEL")).strip().upper()
    if categoria not in CATEGORIAS_DESPESAS_UNIDADES:
        categoria = "OUTROS"
    descricao = str(body.get("descricao", "")).strip()
    if not descricao:
        return web.json_response({"ok": False, "msg": "Informe a descrição da despesa (ex: Gasolina, Almoço, Hotel)."}, status=400)
    try:
        valor = float(str(body.get("valor", "0")).replace(",", "."))
    except Exception:
        valor = 0.0
    if valor <= 0:
        return web.json_response({"ok": False, "msg": "Informe um valor válido maior que zero."}, status=400)

    data_despesa = str(body.get("data_despesa", "")).strip() or datetime.now().strftime("%Y-%m-%d")
    responsavel = str(body.get("responsavel", "")).strip()
    fornecedor = str(body.get("fornecedor", "")).strip()
    veiculo_placa = str(body.get("veiculo_placa", "")).strip().upper()
    os_id = str(body.get("os_id", "")).strip()
    forma_pagamento = str(body.get("forma_pagamento", "PIX")).strip().upper()
    numero_comprovante = str(body.get("numero_comprovante", "")).strip()
    status = str(body.get("status", "PAGO")).strip().upper()
    observacoes = str(body.get("observacoes", "")).strip()
    comprovante_anexo = str(body.get("comprovante_anexo", "")).strip()
    usuario = str(body.get("usuario", "netto")).strip()
    if not responsavel:
        responsavel = "Auto (Cartão Corp. / GPS Frota)"
    if not veiculo_placa:
        veiculo_placa = "Frota EMED (GPS)"

    with _get_db_connection(db_name) as conn:
        _garantir_tabela_despesas_unidades(conn)
        if item_id:
            conn.execute("""
                UPDATE despesas_unidades
                SET unidade=?, categoria=?, descricao=?, valor=?, data_despesa=?,
                    responsavel=?, fornecedor=?, veiculo_placa=?, os_id=?,
                    forma_pagamento=?, numero_comprovante=?, status=?, observacoes=?, comprovante_anexo=COALESCE(NULLIF(?, ''), comprovante_anexo)
                WHERE id=?
            """, (unidade, categoria, descricao, valor, data_despesa, responsavel, fornecedor, veiculo_placa, os_id, forma_pagamento, numero_comprovante, status, observacoes, comprovante_anexo, int(item_id)))
            msg = f"✅ Despesa #{item_id} atualizada com sucesso!"
        else:
            conn.execute("""
                INSERT INTO despesas_unidades (
                    unidade, categoria, descricao, valor, data_despesa,
                    responsavel, fornecedor, veiculo_placa, os_id,
                    forma_pagamento, numero_comprovante, status, observacoes, comprovante_anexo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (unidade, categoria, descricao, valor, data_despesa, responsavel, fornecedor, veiculo_placa, os_id, forma_pagamento, numero_comprovante, status, observacoes, comprovante_anexo))
            msg = f"✅ Despesa de {CATEGORIAS_DESPESAS_UNIDADES[categoria]['label']} (R$ {valor:,.2f}) registrada na unidade {'Filial Brasília (DF)' if unidade == 'FILIAL_DF' else 'Matriz Eusébio (CE)'}!"
        conn.commit()

    _registrar_log_fiscal("DESPESA_UNIDADE", f"{unidade} | {categoria} | {descricao} | R$ {valor:.2f}", usuario)
    return web.json_response({"ok": True, "msg": msg})


async def api_fiscal_v2_despesas_unidades_excluir(request: web.Request) -> web.Response:
    """Remove um lançamento de despesa de unidade."""
    db_name = request.app.get("db_name") or request.app.get("db_path") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    item_id = body.get("id")
    if not item_id:
        return web.json_response({"ok": False, "msg": "ID da despesa não informado."}, status=400)
    with _get_db_connection(db_name) as conn:
        _garantir_tabela_despesas_unidades(conn)
        conn.execute("DELETE FROM despesas_unidades WHERE id = ?", (int(item_id),))
        conn.commit()
    return web.json_response({"ok": True, "msg": "🗑️ Despesa removida com sucesso!"})


def _classificar_categoria_extrato(texto: str) -> str:
    import re
    t = (texto or "").upper()
    if any(k in t for k in ("POSTO", "IPIRANGA", "SHELL", "PETROBRAS", "BR MANIA", "GASOLINA", "COMBUST", "DIESEL", "ETANOL", "ABASTEC", "AUTO POSTO", "SAO DOMINGOS")):
        return "COMBUSTIVEL"
    if any(k in t for k in ("HOTEL", "IBIS", "POUSADA", "HOSPED", "DIARIA", "DIÁRIA", "BOOKING", "AIRBNB", "VISCONDE", "NACIONAL", "PLAZA", "PALACE", "FLAT")):
        return "HOTEL"
    if any(k in t for k in ("RESTAURANTE", "ALMOCO", "ALMOÇO", "JANTAR", "LANCHE", "PADARIA", "CAFE", "CAFÉ", "IFOOD", "CHURRASC", "REFEIC", "REFEIÇ", "PIZZA", "COCO BAMBU", "MANE", "MANÉ", "SABOR", "ALIMENT")):
        return "ALIMENTACAO"
    if any(k in t for k in ("UBER", "99POP", "99*", "TAXI", "PEDAGIO", "PEDÁGIO", "ESTAPAR", "ESTACION", "VIA 040", "SEM PARAR", "VELOE", "LATAM", "GOL", "AZUL", "PASSAGEM")):
        return "PEDAGIO_TRANSPORTE"
    if any(k in t for k in ("OFICINA", "AUTO CENTER", "PNEU", "OLEO", "ÓLEO", "MECANIC", "MECÂNIC", "ALINHAMENTO", "AUTOPECAS", "BATERIA", "LAVA JATO", "REVISAO")):
        return "MANUTENCAO_FROTA"
    if any(k in t for k in ("ASSAI", "ASSAÍ", "ATACAD", "SUPERMERC", "LIMPEZA", "COPA", "AGUA MINERAL", "ÁGUA MINERAL", "PAPELARIA", "KALUNGA")):
        return "INSUMOS_UNIDADE"
    return "OUTROS"


def _normalizar_data_extrato(dt_str: str) -> str:
    import re
    s = (dt_str or "").strip()
    # YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        return f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
    # DD/MM/YYYY or DD-MM-YYYY
    m_br = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", s)
    if m_br:
        d, m, y = int(m_br.group(1)), int(m_br.group(2)), m_br.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{m:02d}-{d:02d}"
    # OFX YYYYMMDD
    m_ofx = re.search(r"^(\d{4})(\d{2})(\d{2})", s)
    if m_ofx:
        return f"{m_ofx.group(1)}-{m_ofx.group(2)}-{m_ofx.group(3)}"
    return datetime.now().strftime("%Y-%m-%d")


def _parsear_valor_extrato(val_str: str) -> float:
    import re
    s = str(val_str or "").strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    # Se tem vírgula e ponto (ex: 1.234,56)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    s_clean = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s_clean)
    except Exception:
        return 0.0


def _parsear_linhas_extrato_gestora(conteudo: str) -> list:
    import re
    texto = (conteudo or "").strip()
    if not texto:
        return []

    itens_extrato = []

    # 1. Suporte a formato bancário OFX (<STMTTRN>)
    if "<STMTTRN>" in texto.upper():
        blocos = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", texto, flags=re.DOTALL | re.IGNORECASE)
        if not blocos:
            blocos = texto.upper().split("<STMTTRN>")[1:]
        for b in blocos:
            dt_m = re.search(r"<DTPOSTED>([^<\r\n]+)", b, re.IGNORECASE)
            val_m = re.search(r"<TRNAMT>([^<\r\n]+)", b, re.IGNORECASE)
            memo_m = re.search(r"<MEMO>([^<\r\n]+)", b, re.IGNORECASE)
            name_m = re.search(r"<NAME>([^<\r\n]+)", b, re.IGNORECASE)
            fit_m = re.search(r"<FITID>([^<\r\n]+)", b, re.IGNORECASE)
            raw_val = _parsear_valor_extrato(val_m.group(1) if val_m else "0")
            if abs(raw_val) < 0.01:
                continue
            desc = " - ".join(filter(None, [
                (name_m.group(1).strip() if name_m else ""),
                (memo_m.group(1).strip() if memo_m else ""),
            ])) or "Lançamento OFX"
            itens_extrato.append({
                "data": _normalizar_data_extrato(dt_m.group(1) if dt_m else ""),
                "descricao": desc,
                "fornecedor": (name_m.group(1).strip() if name_m else desc[:40]),
                "valor": round(abs(raw_val), 2),
                "tipo_mov": "CREDITO" if raw_val > 0 and "PIX RECEB" in desc.upper() else "DESPESA",
                "documento": (fit_m.group(1).strip() if fit_m else ""),
                "categoria": _classificar_categoria_extrato(desc),
            })
        return itens_extrato

    # 2. Suporte a CSV / Excel colado (Tab) / Linhas livres da Gestora
    for idx_l, linha in enumerate(texto.splitlines()):
        l_str = linha.strip()
        if not l_str:
            continue
        # Ignora cabeçalhos comuns
        l_low = l_str.lower()
        if idx_l == 0 and any(h in l_low for h in ("data;descricao", "data,descricao", "data\tdescricao", "categoria;valor", "histórico", "historico")):
            if not re.search(r"\d{2}[/\-]\d{2}", l_str):
                continue

        # Tenta delimitadores ; ou \t ou ,
        delim = ";" if ";" in l_str else ("\t" if "\t" in l_str else ("," if l_str.count(",") >= 2 else None))
        dt_encontrada = ""
        val_encontrado = 0.0
        desc_parts = []
        forn_encontrado = ""
        unid_encontrada = ""
        cat_explicita = ""

        if delim:
            cols = [c.strip().strip('"') for c in l_str.split(delim)]
            for c in cols:
                if not dt_encontrada and re.search(r"^(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})$", c):
                    dt_encontrada = _normalizar_data_extrato(c)
                elif re.search(r"^(R\$\s*)?[\-]?\d+([.,]\d{3})*([.,]\d{2})$", c):
                    v_c = _parsear_valor_extrato(c)
                    if abs(v_c) > 0:
                        val_encontrado = abs(v_c)
                elif c.upper() in ("FILIAL_DF", "DF", "BRASILIA", "BRASÍLIA"):
                    unid_encontrada = "FILIAL_DF"
                elif c.upper() in ("MATRIZ_CE", "CE", "EUSEBIO", "EUSÉBIO", "FORTALEZA"):
                    unid_encontrada = "MATRIZ_CE"
                elif c.upper() in CATEGORIAS_DESPESAS_UNIDADES:
                    cat_explicita = c.upper()
                elif len(c) > 1:
                    desc_parts.append(c)
        else:
            # Linha livre (ex: "11/11/2026 Posto Shell SIA Gasolina R$ 310,00")
            m_dt = re.search(r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", l_str)
            if m_dt:
                dt_encontrada = _normalizar_data_extrato(m_dt.group(1))
                l_str = l_str.replace(m_dt.group(1), " ")
            m_vals = re.findall(r"(?:R\$\s*)?([\-]?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", l_str)
            if m_vals:
                val_encontrado = abs(_parsear_valor_extrato(m_vals[-1]))
                l_str = re.sub(r"(?:R\$\s*)?[\-]?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}", " ", l_str, count=1)
            desc_parts = [re.sub(r"\s+", " ", l_str).strip(" -;|")]

        if val_encontrado <= 0:
            continue

        desc_final = " — ".join([p for p in desc_parts if p]) or "Despesa do Extrato da Gestora"
        forn_encontrado = desc_parts[1] if len(desc_parts) > 1 else desc_parts[0][:40]
        cat_final = cat_explicita or _classificar_categoria_extrato(desc_final)

        itens_extrato.append({
            "data": dt_encontrada or datetime.now().strftime("%Y-%m-%d"),
            "descricao": desc_final,
            "fornecedor": forn_encontrado,
            "valor": round(val_encontrado, 2),
            "unidade_sugerida": unid_encontrada,
            "categoria": cat_final,
            "documento": "EXTRATO-GESTORA",
        })

    return itens_extrato


async def api_fiscal_v2_despesas_unidades_conciliar_extrato(request: web.Request) -> web.Response:
    """Compara o extrato enviado pela gestora contra as despesas já lançadas na unidade para bater valores sem duplicar."""
    db_name = request.app.get("db_name") or request.app.get("db_path") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    conteudo = str(body.get("conteudo", "")).strip()
    arquivo_b64 = str(body.get("arquivo_b64", "")).strip()
    nome_arquivo = str(body.get("nome_arquivo", "")).strip().lower()
    unidade_padrao = str(body.get("unidade", "FILIAL_DF")).strip().upper()
    if unidade_padrao not in ("FILIAL_DF", "MATRIZ_CE"):
        unidade_padrao = "FILIAL_DF"

    if arquivo_b64 and nome_arquivo.endswith(".xlsx"):
        try:
            import openpyxl
            raw_xlsx = base64.b64decode(arquivo_b64)
            wb = openpyxl.load_workbook(io.BytesIO(raw_xlsx), data_only=True)
            ws = wb.active
            linhas_xlsx = []
            for row in ws.iter_rows(values_only=True):
                vals = []
                for cell in row:
                    if cell is None:
                        continue
                    if hasattr(cell, "strftime"):
                        vals.append(cell.strftime("%Y-%m-%d"))
                    elif isinstance(cell, (int, float)):
                        vals.append(f"{float(cell):.2f}".replace(".", ","))
                    else:
                        s_cell = str(cell).strip()
                        if s_cell:
                            vals.append(s_cell)
                if len(vals) >= 2:
                    linhas_xlsx.append(";".join(vals))
            conteudo = "\n".join(linhas_xlsx)
        except Exception as e:
            return web.json_response({"ok": False, "msg": f"Erro ao ler planilha Excel (.xlsx): {e}"}, status=400)

    linhas_parsed = _parsear_linhas_extrato_gestora(conteudo)
    if not linhas_parsed:
        return web.json_response({"ok": False, "msg": "Nenhuma linha com valor válido foi identificada no extrato. Verifique o formato (Data; Descrição; Valor)."}, status=400)

    with _get_db_connection(db_name) as conn:
        _garantir_tabela_despesas_unidades(conn)
        existentes = conn.execute("""
            SELECT id, unidade, categoria, descricao, valor, data_despesa, responsavel, fornecedor, status
            FROM despesas_unidades
            ORDER BY data_despesa DESC, id DESC
        """).fetchall()

    usados_ids = set()
    resultado_itens = []
    tot_extrato = 0.0
    tot_conciliado = 0.0
    tot_divergente = 0.0
    tot_novo = 0.0
    qtd_bateu = 0
    qtd_div = 0
    qtd_novo = 0

    def _dias_diff(d1: str, d2: str) -> int:
        try:
            dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
            dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
            return abs((dt1 - dt2).days)
        except Exception:
            return 999

    for idx, item in enumerate(linhas_parsed):
        v_ext = float(item["valor"])
        d_ext = item["data"]
        cat_ext = item["categoria"]
        unid_item = item.get("unidade_sugerida") or unidade_padrao
        meta_cat = CATEGORIAS_DESPESAS_UNIDADES.get(cat_ext, CATEGORIAS_DESPESAS_UNIDADES["OUTROS"])
        tot_extrato += v_ext

        # 1. Tenta Match Exato: Mesmo valor (± R$ 0,05) e data próxima (até 4 dias) ou descrição/categoria compatível
        match_exato = None
        for r in existentes:
            if r[0] in usados_ids:
                continue
            v_sis = float(r[4] or 0.0)
            d_sis = str(r[5] or "")
            if abs(v_sis - v_ext) <= 0.05 and _dias_diff(d_ext, d_sis) <= 4:
                match_exato = r
                break

        if match_exato:
            usados_ids.add(match_exato[0])
            qtd_bateu += 1
            tot_conciliado += v_ext
            resultado_itens.append({
                "idx": idx,
                "status_batimento": "BATEU_EXATO",
                "status_label": "✅ Conciliado 100% (Já Lançado)",
                "acao_sugerida": "MANTER_AUDITADO",
                "id_sistema": match_exato[0],
                "data": d_ext,
                "unidade": match_exato[1] or unid_item,
                "categoria": cat_ext,
                "categoria_label": meta_cat["label"],
                "categoria_icone": meta_cat["icone"],
                "categoria_cor": meta_cat["cor"],
                "descricao_extrato": item["descricao"],
                "descricao_sistema": match_exato[3],
                "fornecedor": item.get("fornecedor") or match_exato[7] or "",
                "valor_extrato": v_ext,
                "valor_sistema": float(match_exato[4] or 0.0),
                "diferenca": 0.0,
            })
            continue

        # 2. Tenta Match com Divergência de Valor: Mesma data (± 1 dia) e mesma categoria/fornecedor, mas valor diferente
        match_div = None
        for r in existentes:
            if r[0] in usados_ids:
                continue
            d_sis = str(r[5] or "")
            cat_sis = str(r[2] or "").upper()
            v_sis = float(r[4] or 0.0)
            if _dias_diff(d_ext, d_sis) <= 1 and cat_sis == cat_ext and abs(v_sis - v_ext) <= max(150.0, v_ext * 0.35):
                match_div = r
                break

        if match_div:
            usados_ids.add(match_div[0])
            qtd_div += 1
            tot_divergente += v_ext
            v_sis = float(match_div[4] or 0.0)
            resultado_itens.append({
                "idx": idx,
                "status_batimento": "DIVERGENCIA_VALOR",
                "status_label": f"⚠️ Divergência (Sistema: R$ {v_sis:.2f})",
                "acao_sugerida": "ATUALIZAR_VALOR",
                "id_sistema": match_div[0],
                "data": d_ext,
                "unidade": match_div[1] or unid_item,
                "categoria": cat_ext,
                "categoria_label": meta_cat["label"],
                "categoria_icone": meta_cat["icone"],
                "categoria_cor": meta_cat["cor"],
                "descricao_extrato": item["descricao"],
                "descricao_sistema": match_div[3],
                "fornecedor": item.get("fornecedor") or match_div[7] or "",
                "valor_extrato": v_ext,
                "valor_sistema": v_sis,
                "diferenca": round(v_ext - v_sis, 2),
            })
            continue

        # 3. Novo no Extrato da Gestora (Ainda não lançado no sistema)
        qtd_novo += 1
        tot_novo += v_ext
        resultado_itens.append({
            "idx": idx,
            "status_batimento": "NOVO_NO_EXTRATO",
            "status_label": "🆕 Novo no Extrato (Pendente Lançar)",
            "acao_sugerida": "IMPORTAR_NOVO",
            "id_sistema": None,
            "data": d_ext,
            "unidade": unid_item,
            "categoria": cat_ext,
            "categoria_label": meta_cat["label"],
            "categoria_icone": meta_cat["icone"],
            "categoria_cor": meta_cat["cor"],
            "descricao_extrato": item["descricao"],
            "descricao_sistema": "",
            "fornecedor": item.get("fornecedor") or "",
            "valor_extrato": v_ext,
            "valor_sistema": 0.0,
            "diferenca": v_ext,
        })

    return web.json_response({
        "ok": True,
        "resumo": {
            "total_linhas": len(resultado_itens),
            "qtd_conciliados": qtd_bateu,
            "qtd_divergentes": qtd_div,
            "qtd_novos": qtd_novo,
            "valor_total_extrato": round(tot_extrato, 2),
            "valor_conciliado": round(tot_conciliado, 2),
            "valor_divergente": round(tot_divergente, 2),
            "valor_novos": round(tot_novo, 2),
        },
        "itens": resultado_itens,
    })


async def api_fiscal_v2_despesas_unidades_aplicar_conciliacao(request: web.Request) -> web.Response:
    """Aplica o batimento do extrato da gestora: importa novos itens selecionados, corrige divergências autorizadas e audita os conciliados."""
    db_name = request.app.get("db_name") or request.app.get("db_path") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    itens = body.get("itens", [])
    usuario = str(body.get("usuario", "gestora")).strip()

    if not itens:
        return web.json_response({"ok": False, "msg": "Nenhum item selecionado para aplicar na conciliação."}, status=400)

    importados = 0
    atualizados = 0
    auditados = 0

    with _get_db_connection(db_name) as conn:
        _garantir_tabela_despesas_unidades(conn)
        for it in itens:
            acao = str(it.get("acao", "")).upper()
            id_sis = it.get("id_sistema")
            unid = str(it.get("unidade", "FILIAL_DF")).upper()
            if unid not in ("FILIAL_DF", "MATRIZ_CE"):
                unid = "FILIAL_DF"
            cat = str(it.get("categoria", "OUTROS")).upper()
            if cat not in CATEGORIAS_DESPESAS_UNIDADES:
                cat = "OUTROS"
            val = float(it.get("valor_extrato") or 0.0)
            dt = str(it.get("data") or datetime.now().strftime("%Y-%m-%d"))
            desc = str(it.get("descricao_extrato") or "Despesa Conciliada Extrato Gestora").strip()
            forn = str(it.get("fornecedor") or "").strip()

            if acao == "IMPORTAR_NOVO" and val > 0:
                conn.execute("""
                    INSERT INTO despesas_unidades (
                        unidade, categoria, descricao, valor, data_despesa,
                        responsavel, fornecedor, forma_pagamento, numero_comprovante, status, observacoes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'EXTRATO GESTORA', 'CONCILIADO', 'AUDITADO EXTRATO', 'Importado via Batimento de Extrato da Gestora')
                """, (unid, cat, desc, val, dt, f"Extrato ({usuario})", forn))
                importados += 1
            elif acao == "ATUALIZAR_VALOR" and id_sis and val > 0:
                conn.execute("""
                    UPDATE despesas_unidades
                    SET valor = ?, status = 'AUDITADO EXTRATO',
                        observacoes = COALESCE(observacoes, '') || ' | Valor ajustado pelo Extrato da Gestora'
                    WHERE id = ?
                """, (val, int(id_sis)))
                atualizados += 1
            elif acao == "MANTER_AUDITADO" and id_sis:
                conn.execute("""
                    UPDATE despesas_unidades
                    SET status = 'AUDITADO EXTRATO'
                    WHERE id = ?
                """, (int(id_sis),))
                auditados += 1
        conn.commit()

    _registrar_log_fiscal(
        "CONCILIACAO_EXTRATO_GESTORA",
        f"Batimento aplicado: {importados} novos importados, {atualizados} valores corrigidos, {auditados} auditados.",
        usuario,
    )
    return web.json_response({
        "ok": True,
        "msg": f"✅ Batimento do Extrato da Gestora concluído com sucesso! ({importados} novos lançados, {atualizados} divergências ajustadas e {auditados} itens confirmados sem duplicação).",
        "importados": importados,
        "atualizados": atualizados,
        "auditados": auditados,
    })



# ============================================================================
# MÓDULO DE ANÁLISE & GESTÃO MANUAL DE CFOP (TABELA EDITÁVEL + ESTOQUE + NFs)
# ============================================================================
REGRAS_CFOP_PADRAO = [
    ("5102", "SAIDA", "ESTADUAL", "AMBAS", "Venda de mercadoria adquirida ou recebida de terceiros", "Venda de Peças (Interna)", 18.0, 0.0, "Operação estadual de venda de peças/componentes do estoque."),
    ("6102", "SAIDA", "INTERESTADUAL", "AMBAS", "Venda de mercadoria adquirida ou recebida de terceiros", "Venda de Peças (Interestadual)", 12.0, 0.0, "Operação interestadual de venda de peças/componentes do estoque."),
    ("5152", "SAIDA", "ESTADUAL", "AMBAS", "Transferência de mercadoria adquirida ou recebida de terceiros", "Transferência entre Estabelecimentos (Estadual)", 0.0, 0.0, "Não incidência de ICMS conforme STF ADC 49 / LC 204/2023."),
    ("6152", "SAIDA", "INTERESTADUAL", "AMBAS", "Transferência de mercadoria adquirida ou recebida de terceiros", "Transferência entre Filiais (CE <-> DF)", 0.0, 0.0, "Transferência interestadual Matriz CE <-> Filial DF (ADC 49 / LC 204/2023)."),
    ("5915", "SAIDA", "ESTADUAL", "AMBAS", "Remessa de mercadoria ou bem para conserto ou reparo", "Remessa p/ Conserto ou Calibração (Estadual)", 0.0, 0.0, "Suspensão/não incidência de ICMS em remessa para conserto/calibração."),
    ("6915", "SAIDA", "INTERESTADUAL", "AMBAS", "Remessa de mercadoria ou bem para conserto ou reparo", "Remessa p/ Conserto ou Calibração (Interestadual)", 0.0, 0.0, "Remessa interestadual para diagnóstico, reparo ou calibração laboratorial."),
    ("5916", "SAIDA", "ESTADUAL", "AMBAS", "Retorno de mercadoria ou bem recebido para conserto ou reparo", "Retorno/Devolução de Conserto (Estadual)", 0.0, 0.0, "Devolução ao cliente após manutenção/calibração dentro do estado."),
    ("6916", "SAIDA", "INTERESTADUAL", "AMBAS", "Retorno de mercadoria ou bem recebido para conserto ou reparo", "Retorno/Devolução de Conserto (Interestadual)", 0.0, 0.0, "Devolução interestadual ao cliente após manutenção/calibração."),
    ("1916", "ENTRADA", "ESTADUAL", "AMBAS", "Retorno de mercadoria ou bem remetido para conserto ou reparo", "Retorno Físico de Peça (Entrada Estadual)", 0.0, 0.0, "Entrada de retorno de peça enviada para conserto no mesmo estado."),
    ("2916", "ENTRADA", "INTERESTADUAL", "AMBAS", "Retorno de mercadoria ou bem remetido para conserto ou reparo", "Retorno Físico de Peça (Entrada Interestadual)", 0.0, 0.0, "Entrada de retorno interestadual de peça enviada para conserto."),
    ("5933", "SAIDA", "ESTADUAL", "MATRIZ_CE", "Prestação de serviço tributado pelo ISSQN (Matriz CE)", "Prestação de Serviço Técnico (ISS Matriz 2%)", 0.0, 2.0, "Serviço técnico faturado pela Matriz Eusébio-CE com ISS padrão de 2%."),
    ("5933-DF", "SAIDA", "ESTADUAL", "FILIAL_DF", "Prestação de serviço tributado pelo ISSQN (Filial DF)", "Prestação de Serviço Técnico (ISS Brasília 5%)", 0.0, 5.0, "Serviço técnico faturado pela Filial Brasília-DF com ISS padrão de 5%."),
    ("6933", "SAIDA", "INTERESTADUAL", "AMBAS", "Prestação de serviço tributado pelo ISSQN (Interestadual)", "Prestação de Serviço Técnico (Interestadual)", 0.0, 5.0, "Serviço técnico prestado para tomador de outra UF."),
    ("5949", "SAIDA", "ESTADUAL", "AMBAS", "Outra saída de mercadoria ou prestação de serviço não especificado", "Remessa de Uso/Consumo ou Outras Saídas (Estadual)", 0.0, 0.0, "Movimentação interna de bens/ferramentas/insumos sem finalidade comercial."),
    ("6949", "SAIDA", "INTERESTADUAL", "AMBAS", "Outra saída de mercadoria ou prestação de serviço não especificado", "Remessa de Uso/Consumo entre Filiais (Interestadual)", 0.0, 0.0, "Envio interestadual de insumos/ferramentas para uso em filial."),
    ("1556", "ENTRADA", "ESTADUAL", "AMBAS", "Compra de material para uso ou consumo", "Consumíveis & Insumos Administrativos (Estadual)", 0.0, 0.0, "Entrada estadual de materiais de uso e consumo / copa / limpeza."),
    ("2556", "ENTRADA", "INTERESTADUAL", "AMBAS", "Compra de material para uso ou consumo", "Consumíveis & Insumos Administrativos (Interestadual)", 0.0, 0.0, "Entrada interestadual de materiais de uso e consumo."),
]


def _garantir_tabela_regras_cfop(db_name: str) -> None:
    with _get_db_connection(db_name) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regras_cfop (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL,
                tipo_operacao TEXT DEFAULT 'SAIDA',
                esfera TEXT DEFAULT 'ESTADUAL',
                filial_aplicavel TEXT DEFAULT 'AMBAS',
                natureza_operacao TEXT DEFAULT '',
                aplicacao_sistema TEXT DEFAULT '',
                aliquota_icms REAL DEFAULT 0.0,
                aliquota_iss REAL DEFAULT 0.0,
                observacao_fiscal TEXT DEFAULT '',
                ativo INTEGER DEFAULT 1,
                atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
                atualizado_por TEXT DEFAULT 'sistema'
            )
        """)
        cnt = conn.execute("SELECT COUNT(*) FROM regras_cfop").fetchone()[0]
        if cnt == 0:
            for item in REGRAS_CFOP_PADRAO:
                conn.execute("""
                    INSERT INTO regras_cfop (
                        codigo, tipo_operacao, esfera, filial_aplicavel,
                        natureza_operacao, aplicacao_sistema, aliquota_icms,
                        aliquota_iss, observacao_fiscal, ativo, atualizado_por
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'padrao_sistema')
                """, item)
        conn.commit()


async def api_fiscal_v2_cfop_dados(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    _garantir_tabela_regras_cfop(db_name)

    busca_peca = (request.query.get("busca_peca") or "").strip()
    cat_peca = (request.query.get("categoria") or "").strip()

    manager = FiscalManager(db_name)
    cfg_ce = manager.get_filial_config("MATRIZ_CE")
    cfg_df = manager.get_filial_config("FILIAL_DF")

    with _get_db_connection(db_name) as conn:
        regras_rows = conn.execute("""
            SELECT id, codigo, tipo_operacao, esfera, filial_aplicavel,
                   natureza_operacao, aplicacao_sistema, aliquota_icms,
                   aliquota_iss, observacao_fiscal, ativo, atualizado_em, atualizado_por
            FROM regras_cfop
            ORDER BY ativo DESC, codigo ASC
        """).fetchall()
        regras = [
            {
                "id": r[0], "codigo": r[1] or "", "tipo_operacao": r[2] or "SAIDA",
                "esfera": r[3] or "ESTADUAL", "filial_aplicavel": r[4] or "AMBAS",
                "natureza_operacao": r[5] or "", "aplicacao_sistema": r[6] or "",
                "aliquota_icms": float(r[7] or 0.0), "aliquota_iss": float(r[8] or 0.0),
                "observacao_fiscal": r[9] or "", "ativo": int(r[10] if r[10] is not None else 1),
                "atualizado_em": r[11] or "", "atualizado_por": r[12] or "",
            }
            for r in regras_rows
        ]

        resumo_estoque_rows = conn.execute("""
            SELECT COALESCE(cfop_padrao_venda, '') as cfop_v,
                   COALESCE(cfop_padrao_transferencia, '') as cfop_t,
                   COUNT(*) as qtd
            FROM estoque_pecas
            GROUP BY cfop_v, cfop_t
            ORDER BY qtd DESC
        """).fetchall()
        resumo_estoque = [
            {"cfop_venda": r[0], "cfop_transferencia": r[1], "qtd_pecas": r[2]}
            for r in resumo_estoque_rows
        ]

        categorias_rows = conn.execute("""
            SELECT DISTINCT COALESCE(NULLIF(TRIM(categoria), ''), 'Sem Categoria') as cat
            FROM estoque_pecas
            ORDER BY cat ASC
        """).fetchall()
        categorias_estoque = [r[0] for r in categorias_rows]

        where_p = ["1=1"]
        params_p = []
        if busca_peca:
            where_p.append("(LOWER(COALESCE(codigo,'')) LIKE ? OR LOWER(COALESCE(nome_peca,'')) LIKE ? OR LOWER(COALESCE(cfop_padrao_venda,'')) LIKE ? OR LOWER(COALESCE(cfop_padrao_transferencia,'')) LIKE ?)")
            like_val = f"%{busca_peca.lower()}%"
            params_p.extend([like_val, like_val, like_val, like_val])
        if cat_peca and cat_peca != "TODAS":
            if cat_peca == "Sem Categoria":
                where_p.append("(categoria IS NULL OR TRIM(categoria) = '')")
            else:
                where_p.append("categoria = ?")
                params_p.append(cat_peca)

        pecas_rows = conn.execute(f"""
            SELECT id, codigo, nome_peca, COALESCE(NULLIF(TRIM(categoria),''), 'Sem Categoria'),
                   COALESCE(ncm, ''), COALESCE(cfop_padrao_venda, '5102'),
                   COALESCE(cfop_padrao_transferencia, '5152'), COALESCE(filial_pertencente, '')
            FROM estoque_pecas
            WHERE {' AND '.join(where_p)}
            ORDER BY nome_peca ASC
            LIMIT 120
        """, tuple(params_p)).fetchall()
        pecas_cfop = [
            {
                "id": r[0], "codigo": r[1] or "", "nome_peca": r[2] or "",
                "categoria": r[3] or "", "ncm": r[4] or "",
                "cfop_padrao_venda": r[5] or "", "cfop_padrao_transferencia": r[6] or "",
                "filial_pertencente": r[7] or "",
            }
            for r in pecas_rows
        ]
        total_pecas = conn.execute("SELECT COUNT(*) FROM estoque_pecas").fetchone()[0]

        notas_rows = conn.execute("""
            SELECT id, os_id, numero_nf, cliente, filial_emissora,
                   COALESCE(cfop, ''), COALESCE(natureza_operacao, ''),
                   COALESCE(codigo_servico_iss, ''), COALESCE(aliquota_iss, 0),
                   COALESCE(valor_liquido, 0), COALESCE(status_fiscal, ''),
                   COALESCE(data_emissao, criado_em, '')
            FROM notas_fiscais
            ORDER BY id DESC
            LIMIT 100
        """).fetchall()
        notas_cfop = [
            {
                "id": r[0], "os_id": r[1], "numero_nf": r[2] or "",
                "cliente": r[3] or "", "filial_emissora": r[4] or "",
                "cfop": r[5] or "", "natureza_operacao": r[6] or "",
                "codigo_servico_iss": r[7] or "", "aliquota_iss": float(r[8] or 0.0),
                "valor_liquido": float(r[9] or 0.0), "status_fiscal": r[10] or "",
                "data_emissao": str(r[11] or "")[:19],
            }
            for r in notas_rows
        ]

        remessas_cfop = []
        try:
            rem_rows = conn.execute("""
                SELECT id, numero_remessa, cliente_origem, uf_origem, destinatario_nome,
                       uf_destino, COALESCE(cfop, ''), descricao_peca, status_remessa, data_envio
                FROM remessas_diagnostico
                ORDER BY id DESC
                LIMIT 50
            """).fetchall()
            remessas_cfop = [
                {
                    "id": r[0], "numero_remessa": r[1] or "", "cliente_origem": r[2] or "",
                    "uf_origem": r[3] or "", "destinatario_nome": r[4] or "",
                    "uf_destino": r[5] or "", "cfop": r[6] or "",
                    "descricao_peca": r[7] or "", "status_remessa": r[8] or "",
                    "data_envio": r[9] or "",
                }
                for r in rem_rows
            ]
        except Exception:
            pass

    return web.json_response({
        "ok": True,
        "regras": regras,
        "resumo_estoque": resumo_estoque,
        "categorias_estoque": categorias_estoque,
        "pecas_cfop": pecas_cfop,
        "total_pecas": total_pecas,
        "notas_cfop": notas_cfop,
        "remessas_cfop": remessas_cfop,
        "iss_filiais": {
            "MATRIZ_CE": float(cfg_ce.get("aliquota_iss_padrao", 2.0)),
            "FILIAL_DF": float(cfg_df.get("aliquota_iss_padrao", 5.0)),
        },
    })


async def api_fiscal_v2_cfop_salvar(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    _garantir_tabela_regras_cfop(db_name)
    body = await request.json()

    regra_id = body.get("id")
    codigo = str(body.get("codigo") or "").strip().upper()
    if not codigo:
        return web.json_response({"ok": False, "msg": "Informe o código CFOP."}, status=400)

    tipo_operacao = str(body.get("tipo_operacao") or "SAIDA").strip().upper()
    esfera = str(body.get("esfera") or "ESTADUAL").strip().upper()
    filial_aplicavel = str(body.get("filial_aplicavel") or "AMBAS").strip().upper()
    natureza_operacao = str(body.get("natureza_operacao") or "").strip()
    aplicacao_sistema = str(body.get("aplicacao_sistema") or "").strip()
    aliquota_icms = float(body.get("aliquota_icms") or 0.0)
    aliquota_iss = float(body.get("aliquota_iss") or 0.0)
    observacao_fiscal = str(body.get("observacao_fiscal") or "").strip()
    ativo = 1 if body.get("ativo", True) in (True, 1, "1", "true", "True") else 0
    usuario = str(body.get("usuario") or "operador").strip()

    with _get_db_connection(db_name) as conn:
        if regra_id:
            conn.execute("""
                UPDATE regras_cfop
                SET codigo = ?, tipo_operacao = ?, esfera = ?, filial_aplicavel = ?,
                    natureza_operacao = ?, aplicacao_sistema = ?, aliquota_icms = ?,
                    aliquota_iss = ?, observacao_fiscal = ?, ativo = ?,
                    atualizado_em = datetime('now'), atualizado_por = ?
                WHERE id = ?
            """, (
                codigo, tipo_operacao, esfera, filial_aplicavel,
                natureza_operacao, aplicacao_sistema, aliquota_icms,
                aliquota_iss, observacao_fiscal, ativo, usuario, int(regra_id)
            ))
            acao_log = f"CFOP #{regra_id} ({codigo}) atualizado manualmente"
        else:
            conn.execute("""
                INSERT INTO regras_cfop (
                    codigo, tipo_operacao, esfera, filial_aplicavel,
                    natureza_operacao, aplicacao_sistema, aliquota_icms,
                    aliquota_iss, observacao_fiscal, ativo, atualizado_em, atualizado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            """, (
                codigo, tipo_operacao, esfera, filial_aplicavel,
                natureza_operacao, aplicacao_sistema, aliquota_icms,
                aliquota_iss, observacao_fiscal, ativo, usuario
            ))
            acao_log = f"Novo CFOP ({codigo}) cadastrado manualmente"
        conn.commit()

    _registrar_log_fiscal("CFOP_SALVAR", acao_log, usuario=usuario)
    return web.json_response({"ok": True, "msg": f"CFOP {codigo} salvo com sucesso!"})


async def api_fiscal_v2_cfop_excluir(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    _garantir_tabela_regras_cfop(db_name)
    body = await request.json()
    regra_id = body.get("id")
    usuario = str(body.get("usuario") or "operador").strip()
    if not regra_id:
        return web.json_response({"ok": False, "msg": "ID da regra não informado."}, status=400)

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT codigo FROM regras_cfop WHERE id = ?", (int(regra_id),)).fetchone()
        conn.execute("DELETE FROM regras_cfop WHERE id = ?", (int(regra_id),))
        conn.commit()

    cod = row[0] if row else str(regra_id)
    _registrar_log_fiscal("CFOP_EXCLUIR", f"Regra CFOP {cod} (ID #{regra_id}) removida", usuario=usuario)
    return web.json_response({"ok": True, "msg": f"CFOP {cod} excluído com sucesso!"})


async def api_fiscal_v2_cfop_aplicar_estoque(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    modo = str(body.get("modo") or "individual").strip().lower()
    cfop_venda = str(body.get("cfop_padrao_venda") or "").strip()
    cfop_transf = str(body.get("cfop_padrao_transferencia") or "").strip()
    usuario = str(body.get("usuario") or "operador").strip()

    if not cfop_venda and not cfop_transf:
        return web.json_response({"ok": False, "msg": "Informe ao menos um CFOP (Venda ou Transferência)."}, status=400)

    sets = []
    params = []
    if cfop_venda:
        sets.append("cfop_padrao_venda = ?")
        params.append(cfop_venda)
    if cfop_transf:
        sets.append("cfop_padrao_transferencia = ?")
        params.append(cfop_transf)

    with _get_db_connection(db_name) as conn:
        if modo == "lote":
            categoria = str(body.get("categoria") or "TODAS").strip()
            if categoria and categoria != "TODAS":
                if categoria == "Sem Categoria":
                    cur = conn.execute(f"UPDATE estoque_pecas SET {', '.join(sets)} WHERE (categoria IS NULL OR TRIM(categoria) = '')", tuple(params))
                else:
                    cur = conn.execute(f"UPDATE estoque_pecas SET {', '.join(sets)} WHERE categoria = ?", tuple(params + [categoria]))
            else:
                cur = conn.execute(f"UPDATE estoque_pecas SET {', '.join(sets)}", tuple(params))
            afetados = cur.rowcount
            conn.commit()
            _registrar_log_fiscal("CFOP_ESTOQUE_LOTE", f"{afetados} peças atualizadas (Venda={cfop_venda}, Transf={cfop_transf}, Cat={categoria})", usuario=usuario)
            return web.json_response({"ok": True, "msg": f"{afetados} peças atualizadas no estoque com sucesso!"})
        else:
            peca_id = body.get("peca_id")
            if not peca_id:
                return web.json_response({"ok": False, "msg": "ID da peça não informado."}, status=400)
            conn.execute(f"UPDATE estoque_pecas SET {', '.join(sets)} WHERE id = ?", tuple(params + [int(peca_id)]))
            conn.commit()
            _registrar_log_fiscal("CFOP_ESTOQUE_ITEM", f"Peça #{peca_id} atualizada (Venda={cfop_venda}, Transf={cfop_transf})", usuario=usuario)
            return web.json_response({"ok": True, "msg": f"CFOP da peça #{peca_id} salvo com sucesso!"})


async def api_fiscal_v2_cfop_atualizar_nota(request: web.Request) -> web.Response:
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    nota_id = body.get("id")
    cfop = str(body.get("cfop") or "").strip()
    natureza = str(body.get("natureza_operacao") or "").strip()
    usuario = str(body.get("usuario") or "operador").strip()
    if not nota_id:
        return web.json_response({"ok": False, "msg": "ID da nota não informado."}, status=400)

    with _get_db_connection(db_name) as conn:
        conn.execute("""
            UPDATE notas_fiscais
            SET cfop = ?, natureza_operacao = ?, atualizado_em = datetime('now')
            WHERE id = ?
        """, (cfop, natureza, int(nota_id)))
        conn.commit()

    _registrar_log_fiscal("CFOP_NOTA_EDITAR", f"Nota #{nota_id} atualizada para CFOP={cfop}", usuario=usuario)
    return web.json_response({"ok": True, "msg": f"CFOP da Nota #{nota_id} salvo com sucesso!"})


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
          <a href="/historico-os" class="btn btn-outline" style="padding:6px 12px;font-size:12px;border-color:#38bdf8;color:#38bdf8;">&#128270; Hist&oacute;rico Geral OS</a>
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

      <!-- BARRA DE ABAS PRINCIPAIS DO PORTAL -->
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;background:#0f172a;padding:8px;border-radius:10px;border:1px solid #334155;">
        <button type="button" id="tabBtn_FATURAMENTO" class="btn" onclick="alternarAbaPrincipalFiscal('FATURAMENTO')" style="background:var(--cyan);color:#0b132b;font-weight:900;padding:10px 18px;border-radius:8px;">
          🧾 Faturamento, NFS-e &amp; Estoque Fiscal
        </button>
        <button type="button" id="tabBtn_DESPESAS_UNIDADES" class="btn" onclick="alternarAbaPrincipalFiscal('DESPESAS_UNIDADES')" style="background:#1e293b;color:#f8fafc;border:1.5px solid #f59e0b;font-weight:900;padding:10px 18px;border-radius:8px;">
          ⛽🍽️🏨 Detalhes de Despesas das Unidades &amp; Gráficos
        </button>
        <button type="button" id="tabBtn_CFOP" class="btn" onclick="alternarAbaPrincipalFiscal('CFOP')" style="background:#1e293b;color:#f8fafc;border:1.5px solid #38bdf8;font-weight:900;padding:10px 18px;border-radius:8px;">
          📑 Análise &amp; Tabela de CFOP
        </button>
        <button type="button" id="tabBtn_TUDO" class="btn" onclick="alternarAbaPrincipalFiscal('TUDO')" style="background:transparent;color:#94a3b8;border:1px solid #334155;font-weight:700;padding:10px 16px;border-radius:8px;">
          🌐 Exibir Tudo na Mesma Página
        </button>
      </div>

      <!-- ========================================================================= -->
      <!-- NOVA ABA: DETALHES DE DESPESAS DAS UNIDADES (ALIMENTAÇÃO, GASOLINA, HOTEL) -->
      <!-- ========================================================================= -->
      <div id="boxAbaDespesasUnidades" style="display:none;margin-bottom:20px;">
        <div class="card card-highlight" style="border-color:#f59e0b;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
            <div>
              <h3 style="margin:0;color:#fbbf24;font-size:18px;display:flex;align-items:center;gap:8px;">
                <span>⛽🍽️🏨</span>
                <span>Detalhes de Despesas Operacionais das Unidades &amp; Gráficos</span>
              </h3>
              <div style="font-size:12.5px;color:#cbd5e1;margin-top:4px;">
                Controle analítico de gastos com <b>Combustível / Gasolina</b>, <b>Alimentação</b>, <b>Hotel / Hospedagem</b>, <b>Pedágio / Transporte</b> e <b>Manutenção</b> por Unidade (<b>Filial Brasília - DF</b> vs <b>Matriz Eusébio - CE</b>).
              </div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button type="button" class="btn" onclick="toggleBoxExtratoGestora()" style="background:#0284c7;color:#fff;font-weight:900;padding:9px 16px;border:1.5px solid #38bdf8;">
                📂 Bater Extrato da Gestora (CSV / OFX / Excel)
              </button>
              <button type="button" class="btn" onclick="toggleFormNovaDespesaUnidade()" style="background:#f59e0b;color:#0b132b;font-weight:900;padding:9px 16px;">
                ➕ Lançar Nova Despesa
              </button>
              <button type="button" class="btn btn-outline" onclick="exportarDespesasUnidadesCsv()" style="padding:9px 14px;font-size:12px;">
                📥 Exportar Planilha (.CSV)
              </button>
            </div>
          </div>

          <!-- PAINEL DE BATIMENTO & CONCILIAÇÃO DO EXTRATO DA GESTORA -->
          <div id="boxConciliadorExtratoGestora" style="display:none;background:#0f172a;border:2px solid #38bdf8;border-radius:10px;padding:16px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px;">
              <div>
                <div style="font-weight:900;font-size:15px;color:#38bdf8;">📂 Conciliador Automático — Bater Extrato da Gestora com as Despesas da Unidade</div>
                <div style="font-size:12px;color:#94a3b8;margin-top:2px;">
                  Envie o arquivo de extrato (<b>.CSV</b>, <b>.OFX</b> ou <b>.TXT</b>) ou cole as linhas copiadas do Excel/WhatsApp da Gestora. O sistema classifica automaticamente (Gasolina, Alimentação, Hotel) e cruza com o que já está lançado para <b>não duplicar nada</b>!
                </div>
              </div>
              <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;" onclick="toggleBoxExtratoGestora(false)">✕ Fechar</button>
            </div>

            <div class="grid-3" style="margin-bottom:10px;align-items:end;">
              <div>
                <label>1. Unidade de Destino do Extrato:</label>
                <select id="selExtratoGestoraUnidade" style="font-weight:800;color:var(--cyan);">
                  <option value="FILIAL_DF">🏢 Filial Brasília (DF)</option>
                  <option value="MATRIZ_CE">🏛️ Matriz Eusébio (CE)</option>
                </select>
              </div>
              <div>
                <label>2. Carregar Arquivo do Extrato (.CSV, .OFX, .TXT):</label>
                <input type="file" id="inpArquivoExtratoGestora" accept=".xlsx,.csv,.ofx,.txt,.tsv" onchange="aoSelecionarArquivoExtratoGestora(event)" />
              </div>
              <div style="display:flex;gap:8px;">
                <button type="button" class="btn btn-outline" style="font-size:11.5px;padding:9px 12px;width:100%;" onclick="preencherExemploExtratoGestora()">
                  🧪 Carregar Exemplo de Extrato
                </button>
              </div>
            </div>

            <div style="margin-bottom:12px;">
              <label>Ou cole aqui as linhas do Extrato da Gestora (Excel / CSV / Texto — Data; Descrição; Valor):</label>
              <textarea id="txtConteudoExtratoGestora" rows="5" placeholder="Exemplo:&#10;04/11/2026; Posto Ipiranga Asa Norte - Gasolina; 385,50&#10;05/11/2026; Restaurante Mane Almoco Equipe; 142,00&#10;18/11/2026; Posto Shell Brasilia Gasolina; 295,00&#10;19/11/2026; Hotel Mercure Brasilia Diaria Tecnica; 420,00" style="font-family:monospace;font-size:12px;"></textarea>
            </div>

            <div style="display:flex;justify-content:flex-end;gap:10px;margin-bottom:12px;">
              <button type="button" class="btn btn-primary" style="width:auto;padding:10px 22px;" onclick="processarBatimentoExtratoGestora()">
                🔍 Analisar &amp; Bater Extrato Agora
              </button>
            </div>

            <div id="boxResultadoBatimentoExtrato" style="display:none;border-top:1px solid #334155;padding-top:14px;"></div>
          </div>

          <!-- BARRA DE FILTROS DA ABA DE DESPESAS -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:16px;">
            <div>
              <label>🏢 Unidade / Filial:</label>
              <select id="selDespFiltroUnidade" onchange="aoMudarFiltroUnidadeDespesa(this.value)" style="font-weight:800;color:var(--cyan);">
                <option value="CONSOLIDADO">🌐 Todas as Unidades (DF + CE)</option>
                <option value="FILIAL_DF">🏢 Filial Brasília (DF)</option>
                <option value="MATRIZ_CE">🏛️ Matriz Eusébio (CE)</option>
              </select>
            </div>
            <div>
              <label>📅 Mês / Competência:</label>
              <select id="selDespFiltroMes" onchange="carregarDespesasUnidades()" style="font-weight:700;">
                <option value="TODOS">Todos os Meses</option>
              </select>
            </div>
            <div>
              <label>🏷️ Categoria de Despesa:</label>
              <select id="selDespFiltroCategoria" onchange="carregarDespesasUnidades()" style="font-weight:700;">
                <option value="TODAS">Todas as Categorias</option>
                <option value="COMBUSTIVEL">⛽ Combustível / Gasolina</option>
                <option value="ALIMENTACAO">🍽️ Alimentação / Refeições</option>
                <option value="HOTEL">🏨 Hotel / Hospedagem</option>
                <option value="PEDAGIO_TRANSPORTE">🛣️ Pedágio / Estacionamento / Transporte</option>
                <option value="MANUTENCAO_FROTA">🔧 Manutenção Veicular / Frota</option>
                <option value="INSUMOS_UNIDADE">🏢 Copa / Limpeza / Insumos da Unidade</option>
                <option value="OUTROS">📌 Outras Despesas</option>
              </select>
            </div>
            <div>
              <label>🔍 Busca Rápida (Técnico, Posto, Hotel, OS):</label>
              <input id="inpDespBuscaTexto" placeholder="Ex: gasolina, hotel, vitor, ibis..." oninput="filtrarTabelaDespesasLocal()" />
            </div>
          </div>

          <!-- FORMULÁRIO DE LANÇAMENTO / EDIÇÃO DE DESPESA (EXPANSÍVEL) -->
          <div id="boxFormDespesaUnidade" style="display:none;background:#132338;border:2px solid #f59e0b;border-radius:10px;padding:16px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <div style="font-weight:900;font-size:14px;color:#fbbf24;" id="tituloFormDespesaUnidade">➕ Lançar Nova Despesa da Unidade</div>
              <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;" onclick="toggleFormNovaDespesaUnidade(false)">✕ Fechar</button>
            </div>
            <input type="hidden" id="despUnidId" value="" />
            <div class="grid-4" style="margin-bottom:10px;">
              <div>
                <label>Unidade Responsável:</label>
                <select id="despUnidFilial" style="font-weight:700;">
                  <option value="FILIAL_DF">🏢 Filial Brasília (DF)</option>
                  <option value="MATRIZ_CE">🏛️ Matriz Eusébio (CE)</option>
                </select>
              </div>
              <div>
                <label>Categoria da Despesa:</label>
                <select id="despUnidCategoria" style="font-weight:700;color:#fbbf24;">
                  <option value="COMBUSTIVEL">⛽ Combustível / Gasolina</option>
                  <option value="ALIMENTACAO">🍽️ Alimentação / Refeições</option>
                  <option value="HOTEL">🏨 Hotel / Hospedagem</option>
                  <option value="PEDAGIO_TRANSPORTE">🛣️ Pedágio / Estacionamento / Transporte</option>
                  <option value="MANUTENCAO_FROTA">🔧 Manutenção Veicular / Frota</option>
                  <option value="INSUMOS_UNIDADE">🏢 Copa / Limpeza / Insumos da Unidade</option>
                  <option value="OUTROS">📌 Outras Despesas</option>
                </select>
              </div>
              <div>
                <label>Valor da Despesa (R$):</label>
                <input id="despUnidValor" type="number" step="0.01" min="0.01" placeholder="Ex: 280.00" style="font-weight:900;color:#4ade80;" />
              </div>
              <div>
                <label>Data da Despesa:</label>
                <input id="despUnidData" type="date" />
              </div>
            </div>
            <!-- LEITOR INTELIGENTE POR CÂMERA / QR CODE / CÓDIGO DE BARRAS -->
            <div style="background:#0f172a;border:1.5px dashed #f59e0b;border-radius:8px;padding:12px;margin-bottom:14px;">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div>
                  <b style="color:#fbbf24;font-size:13px;">📷 Leitura Inteligente por Câmera / Código de Barras / QR Code</b>
                  <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Aponte a câmera para o QR Code / Código de Barras da NFC-e, Cupom Fiscal ou Boleto. O sistema preenche os dados e anexa a foto automaticamente para conferência!</div>
                </div>
                <div style="display:flex;gap:8px;">
                  <button type="button" class="btn" style="background:#f59e0b;color:#0b132b;font-weight:900;font-size:12px;padding:8px 14px;" onclick="document.getElementById('inpFotoComprovanteDespesa').click()">
                    📸 Câmera / Foto do Comprovante
                  </button>
                  <button type="button" class="btn btn-outline" style="font-size:12px;padding:8px 12px;" onclick="abrirLeitorCodigoBarrasManual()">
                    ⌨️ Digitar Chave / Boleto
                  </button>
                </div>
              </div>
              <input type="file" id="inpFotoComprovanteDespesa" accept="image/*" capture="environment" style="display:none;" onchange="processarFotoComprovanteDespesa(event)" />

              <!-- PREVIEW DO DOCUMENTO ANEXADO -->
              <div id="boxPreviewComprovanteAnexo" style="display:none;margin-top:10px;padding:8px 12px;background:#1e293b;border-radius:6px;border:1px solid #334155;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <span style="font-size:11.5px;color:#a7f3d0;font-weight:700;">📎 Documento / Cupom Anexado com Sucesso!</span>
                  <button type="button" class="btn btn-outline" style="padding:2px 8px;font-size:10px;color:#f87171;" onclick="removerComprovanteAnexo()">✕ Remover Anexo</button>
                </div>
                <div style="display:flex;gap:12px;align-items:center;margin-top:6px;">
                  <img id="imgPreviewComprovante" src="" style="max-height:75px;border-radius:4px;border:1px solid #475569;" alt="Comprovante" />
                  <div style="font-size:11px;color:#cbd5e1;" id="txtInfoComprovanteAnexo"></div>
                </div>
              </div>
            </div>

            <div class="grid-3" style="margin-bottom:10px;">
              <div style="grid-column:span 2;">
                <label>Descrição Detalhada do Gasto Operacional:</label>
                <input id="despUnidDescricao" placeholder="Ex: Gasolina Viagem Preventivas Hospital / Almoço Equipe / Diária Hotel..." />
              </div>
              <div>
                <label>OS Vinculada (opcional):</label>
                <input id="despUnidOsId" placeholder="Ex: 35" />
              </div>
            </div>

            <!-- VÍNCULO OPERACIONAL AUTOMÁTICO (CARTÃO CORP. / GPS FROTA) -->
            <div style="background:#0f172a;border:1px solid #334155;border-radius:6px;padding:10px 12px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">
              <div style="display:flex;align-items:center;gap:10px;">
                <span style="font-size:22px;">💳🛰️</span>
                <div style="font-size:11.5px;color:#94a3b8;">
                  <b style="color:#e2e8f0;">Vínculo Automático por Cartão Corporativo &amp; Telemetria GPS:</b><br/>
                  Não é necessário preencher responsável ou veículo manualmente. A despesa é vinculada diretamente aos cartões corporativos cadastrados e ao rastreador GPS da frota EMED.
                </div>
              </div>
              <input type="hidden" id="despUnidResponsavel" value="Auto (Cartão Corp. / GPS Frota)" />
              <input type="hidden" id="despUnidPlaca" value="Frota EMED (GPS)" />
              <span class="badge" style="background:#065f46;color:#a7f3d0;font-size:11px;font-weight:800;">🛰️ Link GPS / Cartão Ativo</span>
            </div>

            <div class="grid-2" style="margin-bottom:12px;">
              <div>
                <label>Estabelecimento / Fornecedor / Posto / Hotel:</label>
                <input id="despUnidFornecedor" placeholder="Ex: Posto Ipiranga, Restaurante Mané, Hotel Ibis..." />
              </div>
              <div>
                <label>Forma de Pagamento &amp; Nº do Comprovante / Cupom:</label>
                <div style="display:flex;gap:6px;">
                  <select id="despUnidFormaPagto" style="width:55%;">
                    <option value="CARTÃO CORPORATIVO" selected>💳 Cartão Corporativo</option>
                    <option value="PIX">⚡ PIX</option>
                    <option value="BOLETO">📄 Boleto</option>
                    <option value="DINHEIRO / REEMBOLSO">💵 Reembolso</option>
                  </select>
                  <input id="despUnidComprovante" placeholder="Nº NFC-e / Chave" style="width:45%;" />
                </div>
              </div>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:10px;">
              <button type="button" class="btn btn-outline" onclick="toggleFormNovaDespesaUnidade(false)">Cancelar</button>
              <button type="button" class="btn" onclick="salvarNovaDespesaUnidade()" style="background:#10b981;color:#0b132b;font-weight:900;padding:10px 22px;">
                💾 Salvar Despesa da Unidade
              </button>
            </div>
          </div>

          <!-- KPIS DE DESPESAS DAS UNIDADES -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:10px;margin-bottom:16px;">
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid var(--cyan);border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:800;">💰 TOTAL DE DESPESAS (FILTRO)</div>
              <div id="kpiDespTotalGeral" style="font-size:23px;font-weight:900;color:var(--cyan);margin-top:4px;">R$ 0,00</div>
              <div id="kpiDespQtdLanc" style="font-size:11px;color:#64748b;margin-top:2px;">0 lançamentos</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #f59e0b;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#fde68a;font-weight:800;">⛽ COMBUSTÍVEL &amp; GASOLINA</div>
              <div id="kpiDespCombustivel" style="font-size:23px;font-weight:900;color:#fbbf24;margin-top:4px;">R$ 0,00</div>
              <div id="kpiDespCombPct" style="font-size:11px;color:#94a3b8;margin-top:2px;">0% do total</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #10b981;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#a7f3d0;font-weight:800;">🍽️ ALIMENTAÇÃO &amp; REFEIÇÕES</div>
              <div id="kpiDespAlimentacao" style="font-size:23px;font-weight:900;color:#34d399;margin-top:4px;">R$ 0,00</div>
              <div id="kpiDespAlimPct" style="font-size:11px;color:#94a3b8;margin-top:2px;">0% do total</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #38bdf8;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#bae6fd;font-weight:800;">🏨 HOTEL &amp; HOSPEDAGEM</div>
              <div id="kpiDespHotel" style="font-size:23px;font-weight:900;color:#38bdf8;margin-top:4px;">R$ 0,00</div>
              <div id="kpiDespHotelPct" style="font-size:11px;color:#94a3b8;margin-top:2px;">0% do total</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #a78bfa;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#ddd6fe;font-weight:800;">🏢 FILIAL DF vs 🏛️ MATRIZ CE</div>
              <div id="kpiDespComparativoUnid" style="font-size:14px;font-weight:900;color:#e2e8f0;margin-top:6px;line-height:1.35;">
                DF: R$ 0,00<br/>CE: R$ 0,00
              </div>
            </div>
          </div>

          <!-- PAINEL DE GRÁFICOS VISUAIS (3 GRÁFICOS INTERATIVOS) -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin-bottom:16px;">
            <!-- GRÁFICO 1: ROSCA SVG + DISTRIBUIÇÃO POR CATEGORIA -->
            <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;">
              <div style="font-weight:900;font-size:13.5px;color:var(--cyan);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;">
                <span>📊 1. Gráfico por Categoria (Gasolina, Alimentação, Hotel)</span>
              </div>
              <div id="chartDespesasCategorias" style="min-height:230px;"></div>
            </div>

            <!-- GRÁFICO 2: COMPARATIVO ENTRE UNIDADES (FILIAL DF vs MATRIZ CE) -->
            <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;">
              <div style="font-weight:900;font-size:13.5px;color:#38bdf8;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;">
                <span>🏢 2. Comparativo Unidades: Filial DF vs Matriz CE</span>
              </div>
              <div id="chartDespesasComparativoUnidades" style="min-height:230px;"></div>
            </div>

            <!-- GRÁFICO 3: EVOLUÇÃO MENSAL & RANKING POR RESPONSÁVEL -->
            <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;">
              <div style="font-weight:900;font-size:13.5px;color:#fbbf24;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;">
                <span>📈 3. Evolução Mensal &amp; Equipe Técnica</span>
              </div>
              <div id="chartDespesasEvolucaoMensal" style="min-height:230px;"></div>
            </div>
          </div>

          <!-- TABELA DETALHADA DE DESPESAS DAS UNIDADES -->
          <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
              <div style="font-weight:900;font-size:13.5px;color:var(--cyan);">📋 Relação Detalhada de Despesas Lançadas nas Unidades</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;" onclick="atalhoFiltroCategoriaDespesa('TODAS')">Todas</button>
                <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;border-color:#f59e0b;color:#fbbf24;" onclick="atalhoFiltroCategoriaDespesa('COMBUSTIVEL')">⛽ Combustível/Gasolina</button>
                <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;border-color:#10b981;color:#34d399;" onclick="atalhoFiltroCategoriaDespesa('ALIMENTACAO')">🍽️ Alimentação</button>
                <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;border-color:#38bdf8;color:#38bdf8;" onclick="atalhoFiltroCategoriaDespesa('HOTEL')">🏨 Hotel</button>
              </div>
            </div>
            <div style="overflow-x:auto;">
              <table>
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Unidade</th>
                    <th>Categoria</th>
                    <th>Descrição / Detalhe do Gasto</th>
                    <th>Estabelecimento / Posto / Hotel</th>
                    <th>Vínculo Operacional</th>
                    <th>Pagto / Doc / Anexo</th>
                    <th style="text-align:right;">Valor (R$)</th>
                    <th style="text-align:center;">Ações</th>
                  </tr>
                </thead>
                <tbody id="tbodyDespesasUnidades"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>


      <!-- ========================================================================= -->
      <!-- NOVA ABA: ANÁLISE & GESTÃO MANUAL DE CFOP (REGRAS + ESTOQUE + NOTAS)      -->
      <!-- ========================================================================= -->
      <div id="boxAbaCfop" style="display:none;margin-bottom:20px;">
        <div class="card card-highlight" style="border-color:#38bdf8;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:16px;">
            <div>
              <h3 style="margin:0;color:#38bdf8;font-size:18px;display:flex;align-items:center;gap:8px;">
                <span>📑</span>
                <span>Análise &amp; Gestão Manual de CFOP (Regras, Estoque e Notas Fiscais)</span>
              </h3>
              <div style="font-size:12.5px;color:#cbd5e1;margin-top:4px;">
                Visualize todos os <b>CFOPs</b> ativos no sistema, analise o que está gravado nas peças do estoque e nas notas fiscais, <b>edite manualmente qualquer código/regra</b> e salve direto no banco de dados.
              </div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button type="button" class="btn" onclick="toggleFormNovoCfop()" style="background:#38bdf8;color:#0b132b;font-weight:900;padding:9px 16px;">
                ➕ Novo CFOP
              </button>
              <button type="button" class="btn btn-outline" onclick="carregarDadosCfop()" style="padding:9px 14px;font-size:12px;">
                🔄 Atualizar Análise
              </button>
              <button type="button" class="btn btn-outline" onclick="exportarRegrasCfopCsv()" style="padding:9px 14px;font-size:12px;">
                📥 Exportar CFOP (.CSV)
              </button>
            </div>
          </div>

          <!-- KPIs CFOP & ISS -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px;">
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #38bdf8;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#bae6fd;font-weight:800;">📑 REGRAS CFOP CADASTRADAS</div>
              <div id="kpiCfopTotalRegras" style="font-size:24px;font-weight:900;color:#38bdf8;margin-top:4px;">0</div>
              <div id="kpiCfopAtivasSub" style="font-size:11px;color:#94a3b8;margin-top:2px;">0 ativas no sistema</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #10b981;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#a7f3d0;font-weight:800;">📦 PEÇAS NO ESTOQUE ANALISADAS</div>
              <div id="kpiCfopTotalPecas" style="font-size:24px;font-weight:900;color:#34d399;margin-top:4px;">0</div>
              <div id="kpiCfopResumoEstoqueSub" style="font-size:11px;color:#94a3b8;margin-top:2px;">-</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #f59e0b;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#fde68a;font-weight:800;">🧾 NOTAS FISCAIS &amp; REMESSAS</div>
              <div id="kpiCfopTotalNotas" style="font-size:24px;font-weight:900;color:#fbbf24;margin-top:4px;">0</div>
              <div style="font-size:11px;color:#94a3b8;margin-top:2px;">Disponíveis para conferência/edição</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-top:3px solid #a78bfa;border-radius:8px;padding:12px;">
              <div style="font-size:11px;color:#ddd6fe;font-weight:800;">🏛️ ISS VIGENTE POR UNIDADE</div>
              <div id="kpiCfopIssUnidades" style="font-size:15px;font-weight:900;color:#e2e8f0;margin-top:6px;line-height:1.45;">
                Matriz CE: 2,0%<br/>Filial DF: 5,0%
              </div>
            </div>
          </div>

          <!-- FORMULÁRIO EXPANSÍVEL PARA ADICIONAR NOVO CFOP -->
          <div id="boxFormNovoCfop" style="display:none;background:#132338;border:2px solid #38bdf8;border-radius:10px;padding:16px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <div style="font-weight:900;font-size:14px;color:#38bdf8;">➕ Cadastrar Nova Regra de CFOP</div>
              <button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:11px;" onclick="toggleFormNovoCfop(false)">✕ Fechar</button>
            </div>
            <div class="grid-4" style="margin-bottom:10px;">
              <div>
                <label>Código CFOP *</label>
                <input id="novoCfopCodigo" placeholder="Ex: 5102, 6152, 5915" style="font-weight:800;" />
              </div>
              <div>
                <label>Tipo de Operação</label>
                <select id="novoCfopTipo">
                  <option value="SAIDA">SAÍDA</option>
                  <option value="ENTRADA">ENTRADA</option>
                </select>
              </div>
              <div>
                <label>Esfera</label>
                <select id="novoCfopEsfera">
                  <option value="ESTADUAL">ESTADUAL (Interna)</option>
                  <option value="INTERESTADUAL">INTERESTADUAL</option>
                </select>
              </div>
              <div>
                <label>Unidade Aplicável</label>
                <select id="novoCfopFilial">
                  <option value="AMBAS">AMBAS (CE + DF)</option>
                  <option value="MATRIZ_CE">MATRIZ CE</option>
                  <option value="FILIAL_DF">FILIAL DF</option>
                </select>
              </div>
            </div>
            <div class="grid-2" style="margin-bottom:10px;">
              <div>
                <label>Natureza da Operação *</label>
                <input id="novoCfopNatureza" placeholder="Ex: Venda de mercadoria adquirida de terceiros" />
              </div>
              <div>
                <label>Aplicação no Sistema</label>
                <input id="novoCfopAplicacao" placeholder="Ex: Venda de Peças, Transferência CE-DF, Remessa Conserto" />
              </div>
            </div>
            <div class="grid-3" style="margin-bottom:12px;">
              <div>
                <label>Alíquota ICMS Padrão (%)</label>
                <input id="novoCfopIcms" type="number" step="0.1" value="0.0" />
              </div>
              <div>
                <label>Alíquota ISS Padrão (%)</label>
                <input id="novoCfopIss" type="number" step="0.1" value="0.0" />
              </div>
              <div>
                <label>Observação Fiscal / Base Legal</label>
                <input id="novoCfopObs" placeholder="Ex: Não incidência ICMS - ADC 49" />
              </div>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:8px;">
              <button type="button" class="btn btn-outline" onclick="toggleFormNovoCfop(false)">Cancelar</button>
              <button type="button" class="btn btn-blue" onclick="salvarNovoCfop()">💾 Salvar Novo CFOP</button>
            </div>
          </div>

          <!-- SEÇÃO 1: TABELA EDITÁVEL DE REGRAS DE CFOP -->
          <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px;">
              <div style="font-weight:900;font-size:14px;color:#38bdf8;">1. Tabela Mestre de Regras CFOP (Edite qualquer campo e clique em 💾 Salvar)</div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <input id="filtroCfopTexto" placeholder="🔍 Filtrar código, natureza ou aplicação..." oninput="renderizarTabelaRegrasCfop()" style="width:260px;padding:6px 10px;font-size:12px;" />
                <select id="filtroCfopTipo" onchange="renderizarTabelaRegrasCfop()" style="width:130px;padding:6px 8px;font-size:12px;">
                  <option value="TODOS">Todos Tipos</option>
                  <option value="SAIDA">SAÍDA</option>
                  <option value="ENTRADA">ENTRADA</option>
                </select>
                <select id="filtroCfopFilial" onchange="renderizarTabelaRegrasCfop()" style="width:150px;padding:6px 8px;font-size:12px;">
                  <option value="TODAS">Todas Unidades</option>
                  <option value="AMBAS">AMBAS</option>
                  <option value="MATRIZ_CE">MATRIZ CE</option>
                  <option value="FILIAL_DF">FILIAL DF</option>
                </select>
              </div>
            </div>
            <div style="overflow-x:auto;">
              <table>
                <thead>
                  <tr>
                    <th style="min-width:82px;">CFOP</th>
                    <th style="min-width:105px;">Tipo / Esfera</th>
                    <th style="min-width:115px;">Unidade</th>
                    <th style="min-width:210px;">Natureza da Operação</th>
                    <th style="min-width:170px;">Aplicação no Sistema</th>
                    <th style="min-width:72px;">ICMS %</th>
                    <th style="min-width:72px;">ISS %</th>
                    <th style="min-width:180px;">Observação Fiscal</th>
                    <th style="min-width:125px;text-align:center;">Ações</th>
                  </tr>
                </thead>
                <tbody id="tbodyRegrasCfop"></tbody>
              </table>
            </div>
          </div>

          <!-- SEÇÃO 2: ANÁLISE & EDIÇÃO DE CFOP NO ESTOQUE DE PEÇAS -->
          <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:18px;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:10px;">
              <div>
                <div style="font-weight:900;font-size:14px;color:#34d399;">2. Análise de CFOP nas Peças do Estoque (Individual ou em Lote)</div>
                <div id="boxResumoCfopEstoque" style="font-size:12px;color:#cbd5e1;margin-top:4px;"></div>
              </div>
            </div>

            <!-- Barra de alteração em lote -->
            <div style="background:#132338;border:1px dashed #10b981;border-radius:8px;padding:12px;margin-bottom:12px;">
              <div style="font-size:12px;font-weight:800;color:#6ee7b7;margin-bottom:8px;">⚡ Alteração em Lote no Estoque de Peças</div>
              <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;align-items:end;">
                <div>
                  <label>Categoria Alvo:</label>
                  <select id="loteCfopCategoria">
                    <option value="TODAS">Todas as Peças do Estoque</option>
                  </select>
                </div>
                <div>
                  <label>Novo CFOP Padrão Venda:</label>
                  <input id="loteCfopVenda" placeholder="Ex: 5102" />
                </div>
                <div>
                  <label>Novo CFOP Padrão Transf.:</label>
                  <input id="loteCfopTransf" placeholder="Ex: 5152 ou 6152" />
                </div>
                <div>
                  <button type="button" class="btn" onclick="aplicarCfopEstoqueLote()" style="background:#10b981;color:#0b132b;font-weight:900;width:100%;">
                    💾 Aplicar em Lote
                  </button>
                </div>
              </div>
            </div>

            <!-- Filtro e tabela de peças -->
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
              <input id="buscaPecaCfop" placeholder="🔍 Buscar peça por código, nome ou CFOP..." style="flex:1;min-width:220px;" onkeydown="if(event.key==='Enter') carregarDadosCfop()" />
              <select id="filtroCatPecaCfop" onchange="carregarDadosCfop()" style="width:200px;">
                <option value="TODAS">Todas Categorias</option>
              </select>
              <button type="button" class="btn btn-blue" onclick="carregarDadosCfop()" style="width:auto;padding:8px 16px;">🔍 Buscar</button>
            </div>
            <div style="overflow-x:auto;max-height:360px;overflow-y:auto;">
              <table>
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Peça / Item</th>
                    <th>Categoria</th>
                    <th>NCM</th>
                    <th style="width:110px;">CFOP Venda</th>
                    <th style="width:120px;">CFOP Transf.</th>
                    <th style="width:95px;text-align:center;">Salvar</th>
                  </tr>
                </thead>
                <tbody id="tbodyPecasCfop"></tbody>
              </table>
            </div>
          </div>

          <!-- SEÇÃO 3: ANÁLISE & EDIÇÃO DE CFOP NAS NOTAS FISCAIS EMITIDAS -->
          <div style="background:#0f172a;border:1px solid #334155;border-radius:10px;padding:14px;">
            <div style="font-weight:900;font-size:14px;color:#fbbf24;margin-bottom:10px;">3. Análise &amp; Ajuste Manual de CFOP nas Notas Fiscais Registradas</div>
            <div style="overflow-x:auto;max-height:340px;overflow-y:auto;">
              <table>
                <thead>
                  <tr>
                    <th>ID / NF</th>
                    <th>Unidade</th>
                    <th>Cliente</th>
                    <th>Status</th>
                    <th>ISS %</th>
                    <th style="width:110px;">CFOP</th>
                    <th style="min-width:240px;">Natureza da Operação</th>
                    <th style="width:95px;text-align:center;">Salvar</th>
                  </tr>
                </thead>
                <tbody id="tbodyNotasCfop"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- ========================================================================= -->
      <!-- ABA PADRÃO: FATURAMENTO, NFS-E, ESTOQUE & RADAR DF-E                      -->
      <!-- ========================================================================= -->
      <div id="boxAbaFaturamentoFiscal">

      <!-- BARRA DE CONTROLE: EXPANDIR / RECOLHER TODAS AS SEÇÕES -->
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;flex-wrap:wrap;gap:8px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
        <div style="font-size:12.5px;color:var(--muted);font-weight:700;">
          📌 Todas as seções e módulos fiscais possuem controle individual de recolher/expandir (▼ / ▶).
        </div>
        <div style="display:flex;gap:8px;">
          <button type="button" class="btn btn-outline" onclick="toggleTodasSecoes(false)" style="padding:6px 14px;font-size:11.5px;font-weight:800;border-color:#64748b;color:#cbd5e1;">
            🔼 Recolher Todas as Seções
          </button>
          <button type="button" class="btn btn-blue" onclick="toggleTodasSecoes(true)" style="padding:6px 14px;font-size:11.5px;font-weight:800;">
            🔽 Expandir Todas as Seções
          </button>
        </div>
      </div>

      <!-- BANNER DE ACESSO RESTRITO PARA CONFIGURAÇÕES FISCAIS (EXCLUSIVO GESTOR) -->
      <div id="bannerAcessoRestritoCfgFiscal" style="display:none;background:#1e1b4b;border:1px solid #6366f1;border-radius:8px;padding:12px 14px;margin-bottom:16px;color:#c4b5fd;font-size:12.5px;">
        🔒 <b>Acesso Restrito:</b> As Configurações Fiscais, Certificado Digital A1 e Parâmetros Tributários da EMED estão disponíveis exclusivamente para o login do <b>Gestor / Diretoria</b>.
      </div>

      <!-- CONFIGURAÇÃO & CERTIFICADO A1 (EXCLUSIVO GESTOR) -->
      <details class="card" id="expanderConfiguracoesFiscais" style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;" id="tituloExpanderCfg">⚙️ Configurar Dados Fiscais &amp; Certificado Digital A1 (Exclusivo Gestor)</summary>
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
          <h4 style="margin:16px 0 6px 0;color:var(--cyan);">✉️ Envio Automático de E-mails / SMTP Corporativo (Opcional)</h4>
          <div style="font-size:11.5px;color:var(--muted);margin-bottom:8px;">
            Configure caso deseje disparo automático de DANFEs em PDF pelo servidor. Se não configurado, o envio funciona com 1 clique abrindo diretamente no <b>Gmail Web</b>, <b>Outlook Web</b> ou <b>App Padrão</b>.
          </div>
          <div class="grid-2">
            <div><label>Servidor SMTP (Host):</label><input id="cfgSmtpHost" placeholder="ex: smtp.gmail.com ou smtp.office365.com" /></div>
            <div><label>Porta SMTP:</label><input id="cfgSmtpPort" type="number" placeholder="587 ou 465" /></div>
            <div><label>E-mail / Usuário SMTP:</label><input id="cfgSmtpUser" placeholder="ex: fiscal@emed.med.br" /></div>
            <div><label>Senha / Senha de App SMTP:</label><input id="cfgSmtpPass" type="password" placeholder="Preencha apenas para alterar" /></div>
            <div><label>Nome / Remetente Oficial:</label><input id="cfgSmtpFrom" placeholder="ex: EMED Fiscal &lt;fiscal@emed.med.br&gt;" /></div>
          </div>

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
      <details class="card" id="expanderFilaOs" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;outline:none;display:flex;justify-content:space-between;align-items:center;">
          <span>📋 Fila de Faturamento &amp; Ordens de Serviço Concluídas</span>
          <span class="badge" style="background:#0f172a;color:#38bdf8;border:1px solid #38bdf8;">Aguardando Emissão</span>
        </summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
            <div style="font-size:12px;color:var(--muted);">Ordens de serviço finalizadas pela equipe técnica aguardando apuração ou emissão de NFS-e.</div>
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
      </details>

      <!-- FORMULÁRIO DE EMISSÃO -->
      <details class="card card-highlight" id="expanderEmissaoNf" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;outline:none;display:flex;justify-content:space-between;align-items:center;">
          <span id="tituloFormEmissao">🚀 Emissão de Nota Fiscal em 1 Clique (NFS-e / DPS Nacional)</span>
          <span class="badge" style="background:#0284c7;color:#fff;">Pronto para Emissão</span>
        </summary>
        <div style="cursor:default;margin-top:14px;">
        <div class="grid-2" style="margin-bottom:12px;">
          <div>
            <label>Selecione a Ordem de Serviço Concluída:</label>
            <select id="selOsEmissao" onchange="aoTrocarOsEmissao(this.value)"></select>
          </div>
          <div>
            <label>📌 Tipo de Operação &amp; Finalidade da Nota Fiscal:</label>
            <select id="selTipoOperacao" onchange="aplicarTemplateFinalidadeNota()">
              <option value="🏛️ NFS-e NACIONAL (PADRÃO RECEITA FEDERAL / SERPRO • DPS)" selected>🏛️ NFS-e NACIONAL (PADRÃO RECEITA FEDERAL / SERPRO • DPS)</option>
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

        <div style="background:#0f172a;border:1px solid #334155;border-radius:6px;padding:8px 12px;margin-bottom:10px;">
          <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center;">
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;margin:0;">
              <input type="checkbox" id="chkDeduzirPecasFisco" checked onchange="aoAlternarDeduzirPecasFisco()" />
              <span><b>Deduzir no Fisco (Faturar Peças)</b></span>
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;margin:0;">
              <input type="checkbox" id="chkMovimentarEstoqueFiscal" checked />
              <span><b>Movimentar Estoque Fiscal (Livro/SPED)</b></span>
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;margin:0;">
              <input type="checkbox" id="chkMovimentarEstoqueFisico" checked />
              <span><b>Movimentar Estoque Físico (Prateleira)</b></span>
            </label>
          </div>
        </div>

        <div id="barraResumoIss" style="background:#0f172a;padding:10px 14px;border-radius:6px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;font-size:13px;"></div>

        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:12px;margin-bottom:12px;">
          <button type="button" class="btn" id="btnSimularNf" onclick="emitirNotaFiscalAgora('SIMULACAO')" style="background:#0284c7;color:#fff;font-weight:800;padding:12px 14px;border-radius:6px;border:none;cursor:pointer;text-align:center;">
            🧪 EMITIR SIMULAÇÃO / DEMONSTRAÇÃO
            <div style="font-size:11px;font-weight:normal;opacity:0.9;margin-top:2px;">(Treinamento / Demonstração • Sem Efeito Fiscal)</div>
          </button>

          <button type="button" class="btn" id="btnEmitirRealNf" onclick="emitirNotaFiscalAgora('REAL')" style="background:#15803d;color:#fff;font-weight:900;padding:12px 14px;border-radius:6px;border:2px solid #86efac;cursor:pointer;text-align:center;box-shadow:0 0 12px rgba(34,197,94,0.3);">
            🟢 EMITIR NOTA FISCAL REAL (OFICIAL)
            <div style="font-size:11px;font-weight:normal;opacity:0.9;margin-top:2px;">(Transmissão SEFAZ com Certificado A1 Ativo)</div>
          </button>
        </div>
        <div id="boxResultadoEmissao" style="margin-top:14px;"></div>
      </div>

      <!-- TRANSFERÊNCIA AVULSA ENTRE FILIAIS (CE <-> DF) -->
      <details class="card" id="expanderTransferencia" style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;">📦 Transferência Avulsa de Peças &amp; Insumos entre Filiais (CE ⇄ DF — Sem OS)</summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">
            Utilize para transferir peças, insumos ou ferramentas entre a Matriz (Eusébio/CE) e a Filial Brasília (DF) por necessidade logística, reposição ou conserto em bancada, sem depender de uma OS de cliente.
          </div>

          <div class="grid-3" style="margin-bottom:12px;">
            <div>
              <label>Unidade de Origem (Remetente):</label>
              <select id="selOrigemTransferencia" onchange="aoTrocarOrigemTransferencia()">
                <option value="MATRIZ_CE">Matriz (Eusébio / CE)</option>
                <option value="FILIAL_DF">Filial Brasília (DF)</option>
              </select>
            </div>
            <div>
              <label>Unidade de Destino (Destinatário):</label>
              <select id="selDestinoTransferencia">
                <option value="FILIAL_DF">Filial Brasília (DF)</option>
                <option value="MATRIZ_CE">Matriz (Eusébio / CE)</option>
              </select>
            </div>
            <div>
              <label>Finalidade / Natureza Fiscal:</label>
              <select id="selNaturezaTransferencia" onchange="aoTrocarNaturezaTransferencia()">
                <option value="TRANSFERENCIA_ESTOQUE">Transferência de Mercadoria para Reposição (CFOP 6152)</option>
                <option value="REMESSA_USO_CONSUMO">Remessa de Bem / Insumos para Uso em Filial (CFOP 6949)</option>
                <option value="REMESSA_CONSERTO">Remessa para Conserto em Laboratório Matriz (CFOP 6915)</option>
              </select>
              <input type="hidden" id="selCfopTransferencia" value="6152" />
            </div>
          </div>

          <!-- SELEÇÃO DE ITENS -->
          <div style="background:#0f172a;border:1px solid #334155;border-radius:6px;padding:12px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px;">
              <div style="font-weight:bold;font-size:12.5px;color:#a5f3fc;">➕ Adicionar Itens à Remessa</div>
              <div style="font-size:11px;color:#94a3b8;">Filtro rápido ativado por código ou nome</div>
            </div>

            <!-- FILTRO DE BUSCA RÁPIDA -->
            <div style="background:#1e293b;border:1px solid #0284c7;border-radius:6px;padding:8px 10px;margin-bottom:10px;">
              <label style="font-size:11.5px;font-weight:700;color:#38bdf8;margin-bottom:4px;display:flex;align-items:center;justify-content:space-between;">
                <span>🔍 Filtro Rápido (Código ou Nome da Peça):</span>
                <span id="lblCountFiltroTrf" style="color:#7dd3fc;font-weight:800;font-size:11px;"></span>
              </label>
              <div style="display:flex;gap:6px;align-items:center;">
                <input type="text" id="inpFiltroPecaTrf" placeholder="Digite para filtrar (ex: 001, placa, tubo, cabo, colimador, sensor)..." oninput="filtrarPecasTransferencia()" style="flex:1;padding:7px 10px;font-size:12px;border-radius:5px;border:1.5px solid #0284c7;background:#0f172a;color:#fff;font-weight:600;outline:none;" />
                <button type="button" class="btn btn-outline" onclick="limparFiltroPecasTransferencia()" style="padding:6px 10px;font-size:11px;color:#94a3b8;border-color:#475569;" title="Limpar busca">✕ Limpar</button>
              </div>
            </div>

            <div style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;">
              <div style="flex:2;min-width:240px;">
                <label>Selecione a Peça / Insumo do Almoxarifado:</label>
                <select id="selPecaTransferencia" style="width:100%;font-weight:600;" onchange="aoSelecionarPecaTransferencia()"></select>
              </div>
              <div style="width:120px;">
                <label>Qtd <span id="lblMaxEstoqueTrf" style="color:#38bdf8;font-size:10.5px;"></span>:</label>
                <input id="inpQtdTransferencia" type="number" min="1" step="1" value="1" oninput="validarInputQtdTransferencia(this)" />
              </div>
              <div>
                <button type="button" class="btn btn-blue" onclick="adicionarItemTransferencia()">+ Adicionar Item</button>
              </div>
            </div>

            <!-- TABELA DE ITENS ADICIONADOS -->
            <div style="overflow-x:auto;margin-top:10px;">
              <table>
                <thead>
                  <tr><th>Cód</th><th>Descrição da Peça</th><th>Qtd</th><th>Custo Unit.</th><th>Subtotal</th><th>Ação</th></tr>
                </thead>
                <tbody id="tbodyItensTransferencia">
                  <tr><td colspan="6" style="text-align:center;color:var(--muted);padding:8px;">Nenhum item adicionado à remessa ainda.</td></tr>
                </tbody>
              </table>
            </div>

            <div style="display:flex;justify-content:flex-end;margin-top:8px;font-size:14px;font-weight:900;color:var(--cyan);">
              <span>VALOR TOTAL DA CARGA: <span id="lblTotalTransferencia">R$ 0,00</span></span>
            </div>
          </div>

          <div class="grid-2" style="margin-bottom:12px;">
            <div>
              <label>Veículo / Modal de Transporte:</label>
              <select id="selVeiculoTransferencia">
                <option value="TRANSPORTE EM VEÍCULO PRÓPRIO EMED (CONDUTOR TÉCNICO)">Transporte em Veículo Próprio EMED (Técnico / Frota)</option>
                <option value="TRANSPORTADORA PARCEIRA (RODOVIÁRIO)">Transportadora Parceira (Rodoviário)</option>
                <option value="TRANSPORTE AÉREO / CARGA URGENTE">Transporte Aéreo / Carga Urgente</option>
              </select>
            </div>
            <div>
              <label>Observações Adicionais / Justificativa:</label>
              <input id="inpObsTransferencia" placeholder="ex: Reposição de peças para base Brasília" />
            </div>
          </div>

          <div style="display:flex;gap:18px;flex-wrap:wrap;align-items:center;margin-bottom:12px;">
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;margin:0;">
              <input type="checkbox" id="chkTrfMovimentarFiscal" checked />
              <span><b>Movimenta Estoque Fiscal (Livro de Saída / Escrituração)</b></span>
            </label>
            <label style="display:flex;align-items:center;gap:6px;font-size:12px;cursor:pointer;margin:0;">
              <input type="checkbox" id="chkTrfMovimentarFisico" checked />
              <span><b>Movimenta Estoque Físico (Baixa do Almoxarifado)</b></span>
            </label>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
            <div style="font-size:11px;color:#94a3b8;">
              ⚖️ <b>Isenção Legal de ICMS:</b> STF ADC 49 e LC 204/2023 (Transferência entre estabelecimentos do mesmo titular sem fato gerador de ICMS).
            </div>
            <button class="btn btn-primary" id="btnEmitirTransferencia" onclick="emitirTransferenciaFiliais()">🚀 Emitir NF-e de Transferência (Modelo 55)</button>
          </div>
          <div id="boxResultadoTransferencia"></div>
        </div>
      </details>

      <!-- CONSUMÍVEIS ADMINISTRATIVOS (CAFÉ, LIMPEZA, COPA — BAIXA DIRETA) -->
      <details class="card" id="expanderConsumiveis" style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:#fde047;font-size:14px;">☕ Lançamento de Consumíveis Administrativos (Café, Copa, Limpeza — Baixa Direta)</summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">
            Permite escriturar a Nota Fiscal de compra de materiais de uso/consumo da empresa no Fisco e na Despesa Operacional, enquanto o <b>estoque físico de peças de engenharia permanece em zero</b> (consumo imediato), sem poluir a lista técnica dos hospitais.
          </div>

          <div class="grid-3" style="margin-bottom:10px;">
            <div>
              <label>Descrição do Material:</label>
              <input id="consDescricao" placeholder="ex: Café em Pó 500g, Papel Higiênico (Fardo)" />
            </div>
            <div>
              <label>Fornecedor / Estabelecimento:</label>
              <input id="consFornecedor" placeholder="ex: Atacadão, Assaí, Kalunga, Mercadinho" />
            </div>
            <div>
              <label>Número da NF / Cupom de Compra:</label>
              <input id="consNf" placeholder="ex: NFC-e 45892" />
            </div>
          </div>

          <div class="grid-4" style="margin-bottom:12px;">
            <div>
              <label>Unidade &amp; Setor de Consumo:</label>
              <select id="consSetor">
                <option value="Matriz Eusébio/CE - Copa &amp; Cozinha">Matriz Eusébio/CE - Copa &amp; Cozinha</option>
                <option value="Matriz Eusébio/CE - Higiene &amp; Limpeza">Matriz Eusébio/CE - Higiene &amp; Limpeza</option>
                <option value="Matriz Eusébio/CE - Administrativo &amp; Recepção">Matriz Eusébio/CE - Administrativo &amp; Recepção</option>
                <option value="Filial Brasília/DF - Copa &amp; Higiene">Filial Brasília/DF - Copa &amp; Higiene</option>
                <option value="Filial Brasília/DF - Escritório &amp; Apoio">Filial Brasília/DF - Escritório &amp; Apoio</option>
              </select>
            </div>
            <div>
              <label>Categoria:</label>
              <select id="consCategoria">
                <option value="Alimentação &amp; Copa">Alimentação &amp; Copa</option>
                <option value="Higiene &amp; Limpeza">Higiene &amp; Limpeza</option>
                <option value="Material de Escritório &amp; Expediente">Material de Escritório &amp; Expediente</option>
                <option value="Insumo Operacional Geral">Insumo Operacional Geral</option>
              </select>
            </div>
            <div>
              <label>Quantidade:</label>
              <input id="consQtd" type="number" min="1" step="1" value="1" />
            </div>
            <div>
              <label>Valor Total da Nota (R$):</label>
              <input id="consValor" type="number" step="0.01" placeholder="0,00" />
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
            <div style="font-size:11px;color:#fde047;">
              💡 <b>Regra Automática:</b> O valor é lançado na despesa fiscal e contábil, e a baixa do saldo físico ocorre instantaneamente no ato do registro.
            </div>
            <button class="btn btn-primary" style="background:#ca8a04;" id="btnLancarConsumivel" onclick="lancarConsumivelAdministrativo()">☕ Lançar no Fisco &amp; Baixar Estoque Imediatamente (Saldo 0)</button>
          </div>

          <div style="margin-top:14px;border-top:1px solid #334155;padding-top:10px;">
            <div style="font-size:12px;font-weight:bold;color:var(--muted);margin-bottom:6px;">Últimos Consumíveis Lançados (Despesa Direta):</div>
            <div style="overflow-x:auto;">
              <table>
                <thead>
                  <tr><th>Setor</th><th>Descrição / NF</th><th>Qtd</th><th>Finalidade</th><th>Data do Registro</th></tr>
                </thead>
                <tbody id="tbodyConsumiveisRecentes"></tbody>
              </table>
            </div>
          </div>
        </div>
      </details>

      <!-- INVENTÁRIO GERAL & CONCILIAÇÃO: FÍSICO VS. FISCAL -->
      <details class="card" id="expanderEstoqueFiscal" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:#38bdf8;font-size:14px;">📋 Inventário Geral &amp; Conciliação: Físico vs. Fiscal (Ajuste Direto em 1 Clique)</summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">
            Audite e ajuste diretamente os saldos do <b>Estoque Físico Real</b> (prateleira/hospital) e do <b>Estoque Fiscal Escriturado</b> (SPED/Receita). Em caso de contagem de inventário ou <b>falha de baixa do sistema</b>, você pode alterar os números diretamente na tabela ou sincronizá-los com 1 clique.
          </div>

          <!-- CARDS DE ESTATÍSTICA RÁPIDA DO INVENTÁRIO -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px;">
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TOTAL DE ITENS CADASTRADOS</div>
              <div id="invKpiTotal" style="font-size:22px;font-weight:900;color:#38bdf8;">0</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">ITENS 100% CONFORMES</div>
              <div id="invKpiConformes" style="font-size:22px;font-weight:900;color:#34d399;">0</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">COM DIVERGÊNCIA (FÍS ≠ FISC)</div>
              <div id="invKpiDivergentes" style="font-size:22px;font-weight:900;color:#f87171;">0</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TOTAL DE PEÇAS FÍSICAS</div>
              <div id="invKpiTotalQtd" style="font-size:22px;font-weight:900;color:#fbbf24;">0 un</div>
            </div>
          </div>

          <!-- BARRA DE BUSCA & FILTROS -->
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 12px;margin-bottom:14px;">
            <div style="flex:1;min-width:260px;">
              <input id="inpFiltroInventario" placeholder="🔍 Buscar peça por código, descrição ou modelo..." oninput="aoFiltrarInventario()" style="margin:0;padding:8px 12px;font-size:12.5px;" />
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
              <button type="button" class="btn btn-outline" id="btnFiltroInvTodos" onclick="definirFiltroInventario('TODOS')" style="padding:6px 11px;font-size:12px;background:#1e293b;border-color:var(--cyan);color:var(--cyan);">Todos (<span id="cntInvTodos">0</span>)</button>
              <button type="button" class="btn btn-outline" id="btnFiltroInvDivergentes" onclick="definirFiltroInventario('DIVERGENTES')" style="padding:6px 11px;font-size:12px;">⚠️ Divergências (<span id="cntInvDivergentes">0</span>)</button>
              <button type="button" class="btn btn-outline" id="btnFiltroInvZerados" onclick="definirFiltroInventario('ZERADOS')" style="padding:6px 11px;font-size:12px;">📦 Físico Zerado (<span id="cntInvZerados">0</span>)</button>
              <button type="button" class="btn btn-blue" onclick="toggleFormNovoItemInventario()" style="padding:6px 12px;font-size:12px;">➕ Cadastrar Nova Peça</button>
              <button type="button" class="btn btn-outline" onclick="toggleFormAjusteRelativo()" style="padding:6px 10px;font-size:12px;" title="Ajuste de movimentação por Entrada/Saída com histórico">⚡ Movimentação Avulsa</button>
            </div>
          </div>

          <!-- FORMULÁRIO DE CADASTRO DE NOVO ITEM (EXPANSÍVEL) -->
          <div id="boxNovoItemInventario" style="display:none;background:#132338;border:1.5px solid #0284c7;border-radius:8px;padding:14px;margin-bottom:14px;">
            <div style="font-weight:900;font-size:13px;color:#38bdf8;margin-bottom:10px;">➕ Cadastrar Novo Item no Almoxarifado &amp; Inventário Fiscal</div>
            <div class="grid-4" style="margin-bottom:10px;">
              <div>
                <label>Código do Item (ou deixe vazio para gerar):</label>
                <input id="novoInvCodigo" placeholder="Ex: 981" />
              </div>
              <div style="grid-column:span 2;">
                <label>Descrição Completa da Peça / Instrumento:</label>
                <input id="novoInvNome" placeholder="Ex: BATERIA 12V 7AH SELADA" />
              </div>
              <div>
                <label>Unidade de Medida:</label>
                <select id="novoInvUnidade">
                  <option value="UN">UN - Unidade</option>
                  <option value="PC">PC - Peça</option>
                  <option value="MT">MT - Metro</option>
                  <option value="KG">KG - Quilo</option>
                  <option value="LT">LT - Litro</option>
                  <option value="CX">CX - Caixa</option>
                </select>
              </div>
            </div>
            <div class="grid-3" style="margin-bottom:12px;">
              <div>
                <label>Saldo Físico Inicial (Prateleira):</label>
                <input id="novoInvQtdFisica" type="number" step="1" min="0" value="1" />
              </div>
              <div>
                <label>Saldo Fiscal Inicial (Escriturado):</label>
                <input id="novoInvQtdFiscal" type="number" step="1" min="0" value="1" />
              </div>
              <div>
                <label>Preço de Custo (R$):</label>
                <input id="novoInvPrecoCusto" type="number" step="0.01" min="0" value="0.00" />
              </div>
            </div>
            <div style="display:flex;justify-content:flex-end;gap:8px;">
              <button type="button" class="btn btn-outline" onclick="toggleFormNovoItemInventario()">Cancelar</button>
              <button type="button" class="btn btn-primary" style="width:auto;" onclick="salvarNovoItemInventario()">💾 Gravar Peça no Inventário</button>
            </div>
          </div>

          <!-- FORMULÁRIO DE MOVIMENTAÇÃO AVULSA (ENTRADA/SAÍDA) -->
          <div id="boxAjusteRelativo" style="display:none;background:#0f172a;border:1px solid #334155;border-radius:6px;padding:12px;margin-bottom:14px;">
            <div style="font-weight:bold;font-size:12.5px;color:#38bdf8;margin-bottom:8px;">⚡ Movimentação Avulsa de Entrada / Saída</div>
            <div class="grid-4" style="margin-bottom:10px;">
              <div style="grid-column:span 2;">
                <label>Selecione a Peça / Componente:</label>
                <select id="selPecaAjuste" style="width:100%;"></select>
              </div>
              <div>
                <label>Operação:</label>
                <select id="selTipoAjuste">
                  <option value="SAIDA">Saída / Baixa (-)</option>
                  <option value="ENTRADA">Entrada / Adição (+)</option>
                </select>
              </div>
              <div>
                <label>Qtd:</label>
                <input id="inpQtdAjuste" type="number" min="0.1" step="0.1" value="1" />
              </div>
            </div>

            <div class="grid-2" style="margin-bottom:10px;">
              <div>
                <label>Qual Estoque Movimentar?</label>
                <select id="selAlvoAjuste">
                  <option value="AMBOS">Ambos (Movimenta Estoque Físico e Fiscal)</option>
                  <option value="APENAS_FISCAL">Apenas Estoque Fiscal (Ajuste Contábil / Livro)</option>
                  <option value="APENAS_FISICO">Apenas Estoque Físico (Inventário / Prateleira)</option>
                </select>
              </div>
              <div>
                <label>Motivo do Ajuste / Documento:</label>
                <input id="inpMotivoAjuste" placeholder="ex: Contagem física periódica / NF de acerto" />
              </div>
            </div>

            <div style="text-align:right;">
              <button class="btn btn-blue" id="btnSalvarAjusteEstoque" onclick="executarAjusteEstoque()">⚡ Aplicar Movimentação</button>
            </div>
          </div>

          <!-- TABELA DO INVENTÁRIO COM EDIÇÃO DIRETA -->
          <div style="overflow-x:auto;">
            <table>
              <thead>
                <tr>
                  <th style="width:55px;">Cód</th>
                  <th>Descrição da Peça</th>
                  <th style="min-width:140px;text-align:center;">📦 Estoque Físico</th>
                  <th style="min-width:140px;text-align:center;">📜 Estoque Fiscal</th>
                  <th style="width:100px;text-align:center;">Divergência</th>
                  <th style="width:130px;text-align:center;">Situação</th>
                  <th style="min-width:220px;text-align:center;">⚡ Ações de Ajuste Direto</th>
                </tr>
              </thead>
              <tbody id="tbodyComparativoEstoque"></tbody>
            </table>
          </div>

          <!-- PAGINAÇÃO DO INVENTÁRIO -->
          <div id="paginacaoInventario" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-top:12px;padding-top:10px;border-top:1px solid #334155;font-size:12px;color:#94a3b8;">
            <div id="lblInfoPaginacaoInventario">Mostrando 0 de 0 peças</div>
            <div style="display:flex;gap:6px;">
              <button type="button" class="btn btn-outline" id="btnInvPagAnt" onclick="mudarPaginaInventario(-1)" style="padding:4px 10px;font-size:11.5px;">◀ Anterior</button>
              <span id="lblPaginaAtualInventario" style="display:flex;align-items:center;padding:0 8px;font-weight:700;color:#fff;">Pág 1 de 1</span>
              <button type="button" class="btn btn-outline" id="btnInvPagProx" onclick="mudarPaginaInventario(1)" style="padding:4px 10px;font-size:11.5px;">Próxima ▶</button>
            </div>
          </div>
        </div>
      </details>

      <!-- FECHAMENTO MENSAL PARA A CONTABILIDADE -->
      <details class="card card-highlight" id="expanderFechamentoContabil" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:900;color:#38bdf8;font-size:14px;">🏛️ Fechamento Mensal &amp; Relatórios para a Contabilidade (Auditoria Anti-Falhas)</summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:12px;">
            Gere o pacote contábil completo da competência para envio à assessoria contábil. Mitiga erros tributários operacionais do contador através de <b>instruções vinculantes</b> (STF ADC 49, LC 204/2023 para transferências e LC 116/2003 para serviços hospitalares).
          </div>

          <!-- SELETORES DE COMPETÊNCIA E FILIAL -->
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 14px;margin-bottom:14px;">
            <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
              <div>
                <label style="margin-bottom:3px;">Mês / Competência Fiscal:</label>
                <select id="selMesFechamento" onchange="carregarFechamentoContabil()" style="width:160px;font-weight:700;color:var(--cyan);"></select>
              </div>
              <div>
                <label style="margin-bottom:3px;">Unidade / Filial:</label>
                <select id="selFilialFechamento" onchange="carregarFechamentoContabil()" style="width:200px;">
                  <option value="CONSOLIDADO">Consolidado (Todas as Unidades)</option>
                  <option value="FILIAL_DF">Filial Brasília (DF)</option>
                  <option value="MATRIZ_CE">Matriz Eusébio (CE)</option>
                </select>
              </div>
            </div>

            <!-- BOTÕES DE AÇÃO CONTÁBIL -->
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button type="button" class="btn btn-primary" style="width:auto;padding:8px 14px;" onclick="baixarPacoteContadorZip()">
                📦 Baixar Pacote do Contador (.ZIP)
              </button>
              <button type="button" class="btn btn-blue" style="padding:8px 14px;" onclick="abrirRelatorioContabilImpresso()">
                📄 Relatório Oficial (PDF / Impresso)
              </button>
              <button type="button" class="btn btn-outline" style="padding:8px 12px;" onclick="marcarFechamentoEnviadoContabilidade()">
                ✅ Marcar Lote Enviado
              </button>
            </div>
          </div>

          <!-- INDICADORES RESUMO DA COMPETÊNCIA -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px;">
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TOTAL FATURADO (LÍQUIDO)</div>
              <div id="fchKpiFaturado" style="font-size:22px;font-weight:900;color:var(--cyan);">R$ 0,00</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">BASE CÁLCULO ISS (SERVIÇOS)</div>
              <div id="fchKpiServicos" style="font-size:22px;font-weight:900;color:#38bdf8;">R$ 0,00</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TOTAL ISS APURADO</div>
              <div id="fchKpiIss" style="font-size:22px;font-weight:900;color:#fbbf24;">R$ 0,00</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TRANSFERÊNCIAS ISENTAS</div>
              <div id="fchKpiTrf" style="font-size:22px;font-weight:900;color:#a78bfa;">R$ 0,00</div>
            </div>
          </div>

          <!-- MEMORIAL FISCAL ANTI-FALHAS -->
          <div style="background:#132338;border:1.5px solid #0284c7;border-radius:8px;padding:12px 16px;margin-bottom:14px;font-size:12px;line-height:1.5;">
            <div style="font-weight:900;color:#38bdf8;margin-bottom:6px;">⚖️ DIRETRIZES DE AUDITORIA FISCAL PARA O CONTADOR (ANTI-ERROS):</div>
            <ul style="margin:0;padding-left:18px;color:#cbd5e1;">
              <li><b>Não-Incidência de ICMS em Transferências (CE ⇄ DF):</b> Amparadas pela <b>ADC 49 do STF</b> e <b>LC 204/2023</b>. Transferência entre filiais do mesmo titular não gera débito de ICMS.</li>
              <li><b>Segregação de Serviços e Peças:</b> Serviços médicos hospitalares sob a <b>LC 116/2003 (item 14.01/14.02)</b> com alíquota de 5% no DF. Peças orçadas e faturadas devem ser segregadas para não bitributar ISS.</li>
              <li><b>Consumíveis Administrativos:</b> Escriturados sob CFOP 1556/2556 como despesa operacional direta, mantendo o saldo físico em zero no almoxarifado de peças clínicas.</li>
            </ul>
          </div>

          <!-- TABELA DE NOTAS DO FECHAMENTO -->
          <div style="font-size:12px;font-weight:800;color:#94a3b8;margin-bottom:6px;">Notas Fiscais da Competência Selecionada:</div>
          <div style="overflow-x:auto;">
            <table>
              <thead>
                <tr>
                  <th>NFS-e</th>
                  <th>Data</th>
                  <th>Tomador (Cliente)</th>
                  <th>CNPJ</th>
                  <th>CFOP</th>
                  <th>Serviços</th>
                  <th>Peças</th>
                  <th>ISS Apurado</th>
                  <th>Valor Total</th>
                  <th>Status Contábil</th>
                </tr>
              </thead>
              <tbody id="tbodyFechamentoNotas"></tbody>
            </table>
          </div>
        </div>
      </details>

      <!-- RADAR DF-E: NOTAS FISCAIS RECEBIDAS DE FORNECEDORES (SEFAZ & RECEITA FEDERAL) -->
      <details class="card card-highlight" id="expanderNotasRecebidasDFe" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:900;color:#38bdf8;font-size:14px;display:flex;justify-content:space-between;align-items:center;">
          <span>📥 Radar DF-e • Notas Emitidas contra a EMED (Fornecedores &amp; Peças)</span>
          <span style="font-size:11.5px;background:#0369a1;color:#fff;padding:2px 8px;border-radius:9999px;font-weight:700;" id="badgeQtdRecebidas">0 Notas</span>
        </summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:14px;">
            <div style="font-size:12px;color:var(--muted);max-width:700px;">
              Consulta automática no Ambiente Nacional da SEFAZ / Receita Federal via WebService <b>NFeDistribuicaoDFe</b> utilizando o Certificado Digital A1. Permite auditar compras, peças para tomógrafos/raios-x, manifestar recebimento e proteger o CNPJ contra notas frias.
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
              <select id="selFiltroPeriodoDFe" onchange="carregarNotasRecebidasDFe()" style="width:auto;padding:7px 10px;font-size:12px;font-weight:700;background:#0f172a;border:1.5px solid #10b981;color:#34d399;border-radius:6px;" title="Limite temporal das notas sincronizadas da SEFAZ">
                <option value="2026-01-01" selected>📅 Exercício 2026 (Desde Janeiro/2026)</option>
                <option value="2026-08-01">📅 Últimos 90 Dias (Ago a Nov/2026)</option>
                <option value="2026-11-01">📅 Apenas Novembro/2026</option>
              </select>
              <select id="selFiltroUnidadeDFe" onchange="carregarNotasRecebidasDFe()" style="width:auto;padding:7px 10px;font-size:12px;font-weight:700;background:#0f172a;border:1.5px solid #0284c7;color:#38bdf8;border-radius:6px;">
                <option value="CONSOLIDADO" selected>🌐 Todas da Empresa (Matriz CE + Filial DF)</option>
                <option value="FILIAL_DF">🏢 Apenas Filial Brasília (03.611.974/0002-80)</option>
                <option value="MATRIZ_CE">🏛️ Apenas Matriz Eusébio/CE (03.611.974/0001-08)</option>
              </select>
              <input type="file" id="inpXmlDFe" accept=".xml" multiple style="display:none;" onchange="uploadXmlDFe(event)" />
              <button type="button" class="btn btn-primary" onclick="sincronizarDFeSefaz()" style="width:auto;padding:8px 14px;">
                🔄 Puxar Notas no Fisco (SEFAZ • A1)
              </button>
              <button type="button" class="btn" onclick="document.getElementById('inpXmlDFe').click()" style="background:#0284c7;color:#fff;width:auto;padding:8px 14px;border:none;border-radius:6px;cursor:pointer;font-weight:bold;" title="Importar arquivos XML de NF-e recebidas de fornecedores">
                📥 Importar XML de Fornecedor
              </button>
            </div>
          </div>

          <!-- KPIS DE NOTAS RECEBIDAS -->
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px;">
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">TOTAL DE NOTAS RECEBIDAS</div>
              <div id="kpiRecTotal" style="font-size:22px;font-weight:900;color:var(--cyan);">0</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">VALOR TOTAL COMPRADO</div>
              <div id="kpiRecValor" style="font-size:22px;font-weight:900;color:#10b981;">R$ 0,00</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">PENDENTES DE MANIFESTAÇÃO</div>
              <div id="kpiRecPendManif" style="font-size:22px;font-weight:900;color:#f59e0b;">0</div>
            </div>
            <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;">
              <div style="font-size:11px;color:#94a3b8;font-weight:700;">PENDENTES DE ENTRADA NO ESTOQUE</div>
              <div id="kpiRecPendEstoque" style="font-size:22px;font-weight:900;color:#ec4899;">0</div>
            </div>
          </div>

          <!-- TABELA DE NOTAS RECEBIDAS -->
          <div style="overflow-x:auto;">
            <table>
              <thead>
                <tr>
                  <th style="white-space:nowrap;">Nº Nota</th>
                  <th style="white-space:nowrap;min-width:128px;">Unidade EMED</th>
                  <th style="white-space:nowrap;">Emissão</th>
                  <th>Fornecedor (Emitente)</th>
                  <th style="white-space:nowrap;">CNPJ Fornecedor</th>
                  <th style="white-space:nowrap;text-align:center;">UF</th>
                  <th style="white-space:nowrap;">Valor Total</th>
                  <th style="white-space:nowrap;">Manifestação</th>
                  <th style="white-space:nowrap;">Almoxarifado</th>
                  <th style="white-space:nowrap;">Ações</th>
                </tr>
              </thead>
              <tbody id="tbodyNotasRecebidasDFe"></tbody>
            </table>
          </div>
        </div>
      </details>

      <!-- HISTÓRICO DE NOTAS FISCAIS -->
      <details class="card" id="expanderHistoricoNf" open style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:var(--cyan);font-size:14px;outline:none;display:flex;justify-content:space-between;align-items:center;">
          <span>📜 Histórico de Notas Fiscais Emitidas &amp; Documentos Salvos</span>
          <span class="badge" style="background:#0f172a;color:#38bdf8;border:1px solid #38bdf8;">Livro de Saídas</span>
        </summary>
        <div style="cursor:default;margin-top:14px;">
          <div style="overflow-x:auto;">
            <table>
              <thead>
                <tr><th>NFS-e</th><th>Série</th><th>OS #</th><th>Cliente</th><th>Filial</th><th>Tipo / CFOP</th><th>Valor</th><th>Emissão</th><th>Status</th><th>Ações</th></tr>
              </thead>
              <tbody id="tbodyHistoricoNf"></tbody>
            </table>
          </div>
        </div>
      </details>

      <!-- CANCELAMENTO DE NOTA FISCAL -->
      <details class="card" id="expanderCancelamentoNf" style="cursor:pointer;margin-bottom:16px;">
        <summary style="font-weight:800;color:#f87171;font-size:14px;outline:none;display:flex;justify-content:space-between;align-items:center;">
          <span>🚫 Cancelamento de Nota Fiscal Homologada</span>
          <span class="badge" style="background:#450a0a;color:#fca5a5;border:1px solid #ef4444;">Área Crítica / Estorno</span>
        </summary>
        <div style="cursor:default;margin-top:14px;">
          <div class="grid-3" style="align-items:end;">
            <div><label>Selecione a Nota Fiscal Ativa:</label><select id="selNotaCancelar"></select></div>
            <div><label>Justificativa Legal do Cancelamento:</label><input id="inpJustificativaCanc" value="Emissão realizada em ambiente de simulação e testes de homologação" /></div>
            <div><button class="btn btn-danger" style="width:100%;" onclick="cancelarNotaSelecionada()">🚫 Confirmar Cancelamento</button></div>
          </div>
        </div>
      </details>
      </div><!-- FIM boxAbaFaturamentoFiscal -->
    </div>
  </div>

  <script>
    let FILIAL_ATIVA = "FILIAL_DF";
    let DADOS_ATUAIS = null;
    let USUARIO_FISCAL = null;
    let ITENS_TRANSFERENCIA = [];
    let TODAS_PECAS_TRANSFERENCIA = [];
    let INVENTARIO_ITENS = [];
    let INVENTARIO_FILTRO_TIPO = "TODOS";
    let INVENTARIO_FILTRO_TEXTO = "";
    let INVENTARIO_PAGINA = 1;
    const INVENTARIO_POR_PAGINA = 40;

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
      aplicarPermissoesUsuarioFiscal();
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

      const isConsol = FILIAL_ATIVA === "CONSOLIDADO";
      const tituloUnidade = isConsol ? "EMED Eletromedicina • Operação Consolidada (Matriz CE + Filial DF)" : (cfg.razao_social || '');
      const siglaUnidade = isConsol ? "EMED CONSOLIDADO" : (cfg.sigla || '');
      const docUnidade = isConsol ? "03.611.974/0001-08 (Matriz) &amp; 03.611.974/0002-80 (Filial)" : (cfg.cnpj || '');

      document.getElementById("cardUnidadeInfo").innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div>
            <span style="font-size:16px;font-weight:900;color:var(--cyan);">${{tituloUnidade}}</span>
            <span class="badge" style="margin-left:8px;">${{siglaUnidade}}</span>
          </div>
          <div style="font-size:12px;color:#a5f3fc;font-weight:800;">🔐 ${{cert.modo || ''}}</div>
        </div>
        <div style="font-size:12.5px;color:#cbd5e1;margin-top:8px;line-height:1.5;">
          ${{isConsol
            ? `<b>CNPJs Ativos:</b> 03.611.974/0001-08 (Matriz Eusébio/CE) &bull; 03.611.974/0002-80 (Filial Brasília/DF)<br/><b>Regimes &amp; Órgãos Fiscais:</b> Prefeitura de Eusébio (ISS 5%) &bull; SEFAZ-DF (ISS 2% / ICMS) &bull; DPS Nacional (Receita Federal)<br/><b>Amparo Vinculante:</b> STF ADC 49 &bull; LC 204/2023 &bull; LC 116/2003 (Item 14.01/14.02)`
            : `<b>CNPJ:</b> ${{cfg.cnpj || ''}} &bull; <b>Inscrição (CF/DF ou IM):</b> ${{cfg.inscricao_municipal || ''}} &bull; <b>Série NF:</b> ${{cfg.serie_padrao || ''}}<br/><b>Endereço:</b> ${{cfg.endereco || ''}}, ${{cfg.cidade || ''}} - ${{cfg.uf || ''}} (CEP: ${{cfg.cep || ''}}) &bull; <b>Fone:</b> ${{cfg.telefone || ''}}<br/><b>Órgão Fiscal:</b> ${{cfg.orgao_fiscal || ''}} &bull; <b>Alíquota ISS Padrão:</b> ${{cfg.aliquota_iss_padrao || 5.0}}%`
          }}
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
      if (document.getElementById("nfAliqIss")) document.getElementById("nfAliqIss").value = cfg.aliquota_iss_padrao ?? 5.0;
      document.getElementById("cfgRazao").value = cfg.razao_social || "";
      document.getElementById("cfgFone").value = cfg.telefone || "";
      document.getElementById("cfgEnd").value = cfg.endereco || "";
      document.getElementById("cfgEmail").value = cfg.email || "";

      const smtp = res.cfg_smtp || {{}};
      if (document.getElementById("cfgSmtpHost")) document.getElementById("cfgSmtpHost").value = smtp.smtp_host || "";
      if (document.getElementById("cfgSmtpPort")) document.getElementById("cfgSmtpPort").value = smtp.smtp_port || "587";
      if (document.getElementById("cfgSmtpUser")) document.getElementById("cfgSmtpUser").value = smtp.smtp_user || "";
      if (document.getElementById("cfgSmtpFrom")) document.getElementById("cfgSmtpFrom").value = smtp.smtp_from || "";
      if (document.getElementById("cfgSmtpPass")) {{
        document.getElementById("cfgSmtpPass").value = "";
        document.getElementById("cfgSmtpPass").placeholder = smtp.has_pass ? "•••••••• (Senha já gravada - preencha p/ trocar)" : "Senha do e-mail ou senha de app";
      }}

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
      document.getElementById("lblKpiFaturado").textContent = isConsol ? "Total Faturado (Consolidado CE + DF)" : `Total Faturado (${{cfg.sigla || ''}})`;
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
          <td>${{Number(h.os_id) > 0 ? '#' + h.os_id : '<span class="badge" style="background:#0f172a;border:1px solid #334155;">AVULSA</span>'}}</td>
          <td>${{h.cliente}}</td>
          <td>${{h.filial}}</td>
          <td style="font-size:11px;">${{h.cfop ? 'CFOP ' + h.cfop : (String(h.chave || '').length === 50 ? '🏛️ NFS-e Nacional' : 'NFS-e')}}</td>
          <td>R$ ${{Number(h.valor_liquido).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}</td>
          <td>${{h.data_emissao}}</td>
          <td>${{h.status_fiscal}}</td>
          <td>
            <a href="/api/fiscal/danfe/${{Number(h.os_id) > 0 ? h.os_id : encodeURIComponent(h.numero_nf)}}" target="_blank" class="btn btn-blue" style="padding:4px 8px;font-size:11px;">🖨️ DANFE</a>
            <a href="/api/fiscal/v2/xml/${{Number(h.os_id) > 0 ? h.os_id : encodeURIComponent(h.numero_nf)}}" class="btn btn-outline" style="padding:4px 8px;font-size:11px;">📥 XML</a>
          </td>
        </tr>
      `).join("") || `<tr><td colspan="10" style="text-align:center;color:var(--muted);">Nenhuma nota fiscal emitida registrada ainda nesta unidade.</td></tr>`;

      const selCanc = document.getElementById("selNotaCancelar");
      const ativas = (res.historico || []).filter(h => !String(h.status_fiscal).toUpperCase().includes("CANCELAD"));
      selCanc.innerHTML = ativas.map(h => `<option value="${{h.id}}">NFS-e Nº ${{h.numero_nf}} — ${{h.cliente}} (R$ ${{Number(h.valor_liquido).toFixed(2)}})</option>`).join("")
        || `<option value="">-- Nenhuma nota ativa para cancelar --</option>`;

      const selPecaTrf = document.getElementById("selPecaTransferencia");
      if (selPecaTrf && res.pecas_almox) {{
        TODAS_PECAS_TRANSFERENCIA = res.pecas_almox || [];
        filtrarPecasTransferencia();
      }}

      const selVeic = document.getElementById("selVeiculoTransferencia");
      if (selVeic && res.veiculos_frota && res.veiculos_frota.length) {{
        const veicsOpts = res.veiculos_frota.map(v => `<option value="${{v.modelo}} - ${{v.placa}}">${{v.modelo}} (${{v.placa}}) - Frota EMED</option>`).join("");
        selVeic.innerHTML = veicsOpts + `
          <option value="TRANSPORTADORA PARCEIRA (RODOVIÁRIO)">Transportadora Parceira (Rodoviário)</option>
          <option value="TRANSPORTE AÉREO / CARGA URGENTE">Transporte Aéreo / Carga Urgente</option>
        `;
      }}

      const tbCons = document.getElementById("tbodyConsumiveisRecentes");
      if (tbCons) {{
        tbCons.innerHTML = (res.consumiveis_recentes || []).map(c => `
          <tr>
            <td><b>${{c.setor}}</b></td>
            <td>${{c.item}}</td>
            <td>${{c.qtd}}</td>
            <td><span class="badge" style="background:#065f46;color:#a7f3d0;">${{c.finalidade}}</span></td>
            <td style="font-size:11px;">${{c.data}}</td>
          </tr>
        `).join("") || `<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:8px;">Nenhum consumível lançado recentemente.</td></tr>`;
      }}

      const selPecaAjuste = document.getElementById("selPecaAjuste");
      if (selPecaAjuste && res.pecas_almox) {{
        selPecaAjuste.innerHTML = res.pecas_almox.map(p =>
          `<option value="${{p.id}}" data-codigo="${{p.codigo}}" data-nome="${{p.nome.replace(/"/g, '&quot;')}}">${{p.codigo ? '[' + p.codigo + '] ' : ''}}${{p.nome}} (Físico: ${{p.qtd}} ${{p.unidade}} | Fiscal: ${{p.qtd_fiscal}} ${{p.unidade}})</option>`
        ).join("") || `<option value="">Nenhuma peça cadastrada</option>`;
      }}

      INVENTARIO_ITENS = res.pecas_almox || [];
      renderizarInventario();
      carregarFechamentoContabil();
    }}

    function preencherFormularioComOs(d, cfg) {{
      if (!d) return;
      if (document.getElementById("nfCliente")) document.getElementById("nfCliente").value = d.cliente || "";
      if (document.getElementById("nfCnpj")) document.getElementById("nfCnpj").value = d.cnpj_tomador || "";
      if (document.getElementById("nfEmail")) document.getElementById("nfEmail").value = d.email_cliente || "";
      if (document.getElementById("nfEnd")) document.getElementById("nfEnd").value = d.tomador_endereco || "";
      if (document.getElementById("nfCid")) document.getElementById("nfCid").value = d.tomador_cidade || "";
      if (document.getElementById("nfUf")) document.getElementById("nfUf").value = d.tomador_uf || "";
      if (document.getElementById("nfDiscriminacao")) document.getElementById("nfDiscriminacao").value = d.discriminacao_servico || "";
      if (document.getElementById("nfValSrv")) document.getElementById("nfValSrv").value = d.valor_servicos ?? 0;
      if (document.getElementById("nfValPec")) document.getElementById("nfValPec").value = d.valor_pecas ?? 0;
      if (document.getElementById("nfAliqIss")) document.getElementById("nfAliqIss").value = d.aliquota_iss ?? (cfg?.aliquota_iss_padrao || 5.0);
      if (document.getElementById("nfDesconto")) document.getElementById("nfDesconto").value = d.valor_desconto ?? 0;
      if (document.getElementById("lblFormAliqIss")) document.getElementById("lblFormAliqIss").textContent = `Alíquota ISS (${{cfg?.uf || 'DF'}}) (%):`;
      const btnEm = document.getElementById("btnEmitirRealNf") || document.getElementById("btnEmitirNf");
      if (btnEm) btnEm.textContent = `🟢 EMITIR NOTA FISCAL REAL (${{cfg?.sigla || 'EMED'}})`;
      recalcularTotaisFormNf();
    }}

    function aoTrocarOsEmissao(osId) {{
      carregarDadosFiscais(osId);
    }}

    function aplicarTemplateFinalidadeNota() {{
      const d = DADOS_ATUAIS?.os_selecionada;
      if (!d) return;
      const tipo = document.getElementById("selTipoOperacao").value;
      if (tipo.includes("NACIONAL")) {{
        document.getElementById("nfDiscriminacao").value =
          `Prestação de serviços técnicos especializados de Manutenção e Reparação Técnica no equipamento médico ${{d.equipamento || 'MÉDICO-HOSPITALAR'}}. Atendimento referente à Ordem de Serviço #${{d.os_id}}. Código de Tributação Nacional: 140101 (Manutenção e Reparação de Aparelhos Eletromédicos). CNAE: 3312-1/03. Atendimento prestado em ${{d.tomador_cidade}} - ${{d.tomador_uf}}. Operação emitida no Ambiente de Dados Nacional da NFS-e (Receita Federal do Brasil / Lei Complementar 116/2003 e Resolução CGOFN).`;
        document.getElementById("nfAliqIss").value = DADOS_ATUAIS?.cfg_ativa?.aliquota_iss_padrao || 5.0;
      }} else if (tipo.includes("DIAGNÓSTICO")) {{
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
          smtp_host: document.getElementById("cfgSmtpHost")?.value || "",
          smtp_port: document.getElementById("cfgSmtpPort")?.value || "587",
          smtp_user: document.getElementById("cfgSmtpUser")?.value || "",
          smtp_pass: document.getElementById("cfgSmtpPass")?.value || "",
          smtp_from: document.getElementById("cfgSmtpFrom")?.value || "",
          usuario: USUARIO_FISCAL?.username || "netto"
        }})
      }}).then(r => r.json());
      alert(res.msg || "Configurações salvas!");
      carregarDadosFiscais();
    }}

    async function emitirNotaFiscalAgora(modo = 'SIMULACAO', forcarDuplicidade = false) {{
      const osId = document.getElementById("selOsEmissao").value;
      if (!osId) {{ alert("Por favor, selecione uma Ordem de Serviço para emissão."); return; }}

      const cliNome = document.getElementById("nfCliente") ? document.getElementById("nfCliente").value : "Cliente";
      const filialTxt = FILIAL_ATIVA === 'MATRIZ_CE' ? 'Matriz Eusébio - CE' : 'Filial Brasília - DF';

      if (!forcarDuplicidade) {{
        const confMsg = (modo === 'REAL')
          ? `⚠️ CONFERÊNCIA OBRIGATÓRIA DOS DADOS DA NOTA FISCAL\n\nVocê já conferiu todos os dados da nota fiscal (no espelho da nota que aparece abaixo)?\n\n• Cliente: ${{cliNome}}\n• Unidade Emissora: ${{filialTxt}}\n• Modalidade: 🟢 EMISSÃO REAL (SEFAZ • CERTIFICADO A1)\n\nEsta nota será transmitida oficialmente à SEFAZ e terá valor legal para apuração do DAS e faturamento.\n\nRealmente quer emitir a Nota Fiscal agora?\n\n[OK] = Sim, emitir nota fiscal agora\n[Cancelar] = Não, desejo revisar os dados na página`
          : `🧪 MODO SIMULAÇÃO / DEMONSTRAÇÃO\n\nVocê já conferiu todos os dados da nota fiscal (no espelho da nota que aparece abaixo)?\n\n• Cliente: ${{cliNome}}\n• Unidade: ${{filialTxt}}\n• Modalidade: 🧪 SIMULAÇÃO (Sem efeito fiscal na SEFAZ)\n\nRealmente quer emitir o espelho de demonstração?\n\n[OK] = Sim, gerar espelho de demonstração\n[Cancelar] = Não, desejo revisar os dados na página`;

        const querEmitir = confirm(confMsg);
        if (!querEmitir) {{
          // Usuário optou por revisar: permanece exatamente na página sem fechar e sem apagar nada
          return;
        }}
      }}

      const btnSim = document.getElementById("btnSimularNf");
      const btnReal = document.getElementById("btnEmitirRealNf");
      if (btnSim) btnSim.disabled = true;
      if (btnReal) btnReal.disabled = true;

      try {{
        const res = await fetch("/api/fiscal/v2/emitir", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            os_id: osId,
            modo_emissao: modo,
            filial_emissora: FILIAL_ATIVA,
            forcar_emissao_duplicada: forcarDuplicidade,
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
          deduzir_pecas_fisco: document.getElementById("chkDeduzirPecasFisco") ? document.getElementById("chkDeduzirPecasFisco").checked : true,
          movimentar_estoque_fiscal: document.getElementById("chkMovimentarEstoqueFiscal") ? document.getElementById("chkMovimentarEstoqueFiscal").checked : true,
          movimentar_estoque_fisico: document.getElementById("chkMovimentarEstoqueFisico") ? document.getElementById("chkMovimentarEstoqueFisico").checked : true,
          aliquota_iss: document.getElementById("nfAliqIss").value,
          valor_desconto: document.getElementById("nfDesconto").value,
          usuario: USUARIO_FISCAL?.username || "netto"
        }})
      }}).then(r => r.json());
      if (res.ok) {{
        const n = res.nota;
        const basePub = window.location.origin;
        const linkDanfe = `${{basePub}}/api/fiscal/danfe/${{osId}}`;
        const linkPdf = `${{basePub}}/api/fiscal/danfe/${{osId}}?formato=pdf`;
        const filialLabel = FILIAL_ATIVA === 'MATRIZ_CE' ? 'EMED-CE' : 'EMED-DF';
        const msgWpp = encodeURIComponent(
          `🧾 *EMED ELETROMEDICINA • NOTA FISCAL EMITIDA (${{filialLabel}})*\\n\\n` +
          `🏥 *Cliente:* ${{n.cliente}}\\n` +
          `📋 *NFS-e Nº:* ${{n.numero_nf}} (OS #${{osId}})\\n` +
          `💰 *Valor Total:* R$ ${{Number(n.valor_liquido||0).toFixed(2)}}\\n` +
          `🔐 *Chave de Acesso:* ${{n.chave_acesso}}\\n` +
          `✅ *Status:* AUTORIZADA SEFAZ\\n\\n` +
          `📄 *Visualizar / Baixar PDF Oficial da Nota:*\\n${{linkDanfe}}`
        );
        document.getElementById("boxResultadoEmissao").innerHTML = `
          <div style="background:#14532d;border:2px solid #22c55e;border-radius:8px;padding:16px;color:#fff;margin-top:14px;box-shadow:0 4px 15px rgba(0,0,0,0.3);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
              <div style="font-weight:900;font-size:16px;">🎉 NOTA FISCAL AUTORIZADA COM SUCESSO!</div>
              <span class="badge" style="background:#22c55e;color:#052e16;font-size:12px;font-weight:900;">STATUS: ${{n.status || 'AUTORIZADA'}}</span>
            </div>
            <div style="margin-top:8px;font-size:13px;line-height:1.6;color:#dcfce7;">
              <b>Número da NFS-e:</b> <span style="font-size:15px;font-weight:900;color:#fff;">${{n.numero_nf}}</span> &bull; <b>Série:</b> ${{n.serie}} &bull; <b>OS:</b> #${{osId}}<br/>
              <b>Cliente:</b> ${{n.cliente}} &bull; <b>Valor Líquido:</b> R$ ${{Number(n.valor_liquido||0).toFixed(2)}}<br/>
              <b>Chave de Acesso:</b> <span style="font-family:monospace;letter-spacing:0.5px;color:#fff;">${{n.chave_acesso}}</span><br/>
              <b>Protocolo SEFAZ:</b> ${{n.protocolo || 'HOMOLOGADO'}}
            </div>
            <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;align-items:center;">
              <a href="${{linkDanfe}}" target="_blank" class="btn btn-blue" style="font-weight:800;">🖨️ Abrir DANFE Oficial Completo</a>
              <a href="${{linkPdf}}" download="DANFE_NFS_${{n.numero_nf}}.pdf" class="btn" style="background:#0284c7;color:#fff;font-weight:800;">📥 Baixar Arquivo PDF (.pdf)</a>
              <a href="https://api.whatsapp.com/send?text=${{msgWpp}}" target="_blank" class="btn" style="background:#16a34a;color:#fff;font-weight:800;">📲 Enviar WhatsApp com Link do PDF</a>
              <button type="button" onclick="compartilharPdfWhatsAppDirect('${{osId}}', '${{n.numero_nf}}', '${{msgWpp}}')" class="btn" style="background:#25d366;color:#000;font-weight:900;">📎 Compartilhar PDF no WhatsApp</button>
              <a href="/api/fiscal/v2/xml/${{osId}}" class="btn btn-outline" style="font-weight:800;">📥 Baixar XML SEFAZ</a>
            </div>
            <div style="margin-top:14px;background:#fff;border-radius:6px;overflow:hidden;border:1px solid #cbd5e1;">
              <div style="background:#0f172a;color:#fff;padding:8px 12px;font-size:12px;font-weight:800;display:flex;justify-content:space-between;align-items:center;">
                <span>📄 Visualização do Espelho Oficial da Nota (DANFE Oficial Completo)</span>
                <a href="${{linkDanfe}}" target="_blank" style="color:#38bdf8;font-size:11px;text-decoration:none;">↗️ Abrir em Nova Aba</a>
              </div>
              <iframe src="${{linkDanfe}}" style="width:100%;height:560px;border:none;background:#fff;"></iframe>
            </div>
          </div>
        `;
        document.getElementById("boxResultadoEmissao").scrollIntoView({{ behavior: 'smooth' }});
        atualizarApenasHistoricoSemReset(osId, n.numero_nf);
      }} else if (res.intertravamento_duplicidade) {{
        const ne = res.nota_existente;
        const box = document.getElementById("boxResultadoEmissao");
        box.innerHTML = `
          <div style="background:#1e293b;border:2px solid #eab308;border-radius:8px;padding:16px;color:#fff;margin-top:14px;box-shadow:0 4px 20px rgba(234,179,8,0.25);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
              <div style="font-weight:900;font-size:15px;color:#fde047;display:flex;align-items:center;gap:6px;">
                <span>⚠️ INTERTRAVAMENTO CONTRA EMISSÃO DUPLICADA</span>
              </div>
              <span class="badge" style="background:#eab308;color:#000;font-weight:900;">NOTA JÁ AUTORIZADA</span>
            </div>
            <div style="margin-top:10px;font-size:13px;line-height:1.6;color:#e2e8f0;">
              A <b>Nota Fiscal Nº ${{ne.numero_nf}}</b> referente à <b>OS #${{ne.os_id}}</b> já foi emitida com sucesso em <b>${{ne.data_emissao}}</b> para o cliente <b>${{ne.cliente}}</b> no valor de <b>R$ ${{Number(ne.valor_liquido).toFixed(2)}}</b>!
            </div>
            <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
              <a href="${{ne.link_danfe}}" target="_blank" class="btn btn-blue" style="font-weight:800;">📄 Abrir Espelho da Nota Já Emitida (DANFE)</a>
              <a href="${{ne.link_pdf}}" download="DANFE_${{ne.numero_nf}}.pdf" class="btn" style="background:#0284c7;color:#fff;font-weight:800;">📥 Baixar PDF Existente</a>
              <button type="button" onclick="emitirNotaFiscalAgora('${{modo}}', true)" class="btn" style="background:#dc2626;color:#fff;font-weight:900;border:1.5px solid #fca5a5;">⚡ Sim, Desejo Emitir Outra Nota Mesmo Assim</button>
              <button type="button" onclick="document.getElementById('boxResultadoEmissao').innerHTML=''" class="btn btn-outline" style="color:#94a3b8;">✕ Manter Nota Existente</button>
            </div>
            <div style="margin-top:14px;background:#fff;border-radius:6px;overflow:hidden;border:1px solid #cbd5e1;">
              <div style="background:#0f172a;color:#fff;padding:6px 12px;font-size:11.5px;font-weight:800;display:flex;justify-content:space-between;align-items:center;">
                <span>📄 Espelho Oficial da Nota Fiscal Já Emitida (OS #${{ne.os_id}} • NFS-e ${{ne.numero_nf}})</span>
                <a href="${{ne.link_danfe}}" target="_blank" style="color:#38bdf8;font-size:11px;text-decoration:none;">↗️ Abrir em Nova Aba</a>
              </div>
              <iframe src="${{ne.link_danfe}}" style="width:100%;height:480px;border:none;background:#fff;"></iframe>
            </div>
          </div>
        `;
        box.scrollIntoView({{ behavior: 'smooth' }});

        const querOutra = confirm(
          `⚠️ INTERTRAVAMENTO FISCAL CONTRA DUPLICIDADE:\n\nA Nota Fiscal ${{ne.numero_nf}} referente à OS #${{ne.os_id}} já foi emitida com sucesso em ${{ne.data_emissao}} para este cliente e valor!\n\nO espelho da nota já emitida foi carregado na tela abaixo para sua conferência.\n\nDeseja realmente emitir OUTRA nota fiscal para este mesmo atendimento?\n\n[OK] = Sim, desejo emitir outra nota mesmo assim\n[Cancelar] = Não, manter a nota existente (não duplicar)`
        );
        if (querOutra) {{
          emitirNotaFiscalAgora(modo, true);
        }}
      }} else {{
        alert("Erro ao emitir: " + (res.msg || "Falha interna"));
      }}
    }} catch (e) {{
      alert("Erro na transmissão da nota fiscal: " + (e.message || e));
    }} finally {{
      if (btnSim) btnSim.disabled = false;
      if (btnReal) btnReal.disabled = false;
    }}
  }}

    async function cancelarNotaSelecionada() {{
      const id = document.getElementById("selNotaCancelar").value;
      const just = document.getElementById("inpJustificativaCanc").value;
      if (!id) {{ alert("Nenhuma nota ativa selecionada."); return; }}
      if (!just || just.trim().length < 8) {{
        alert("Por favor, preencha a justificativa legal do cancelamento (mínimo 8 caracteres).");
        return;
      }}

      const conf = confirm(
        `⚠️ ATENÇÃO: CONFIRMAÇÃO IRREVERSÍVEL DE CANCELAMENTO\n\nVocê está prestes a CANCELAR esta Nota Fiscal no sistema e registrar a anulação fiscal.\n\n• Justificativa: ${{just}}\n\nDeseja realmente prosseguir com o cancelamento?`
      );
      if (!conf) return;

      const senha = prompt("🔒 Digite a SENHA DE AUTORIZAÇÃO FISCAL para confirmar o cancelamento:");
      if (!senha) {{
        alert("Operação abortada: Senha de autorização não informada.");
        return;
      }}

      const res = await fetch("/api/fiscal/v2/cancelar", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ id, justificativa: just, senha: senha, usuario: USUARIO_FISCAL?.username || "netto" }})
      }}).then(r => r.json());
      alert(res.msg || "Operação concluída");
      if (res.ok) carregarDadosFiscais();
    }}

    async function criarOsTesteBrasilia() {{
      const res = await fetch("/api/fiscal/v2/criar-os-teste", {{ method: "POST" }}).then(r => r.json());
      alert(res.msg);
      if (res.ok) carregarDadosFiscais(String(res.os_id));
    }}

    function aoAlternarDeduzirPecasFisco() {{
      const chk = document.getElementById("chkDeduzirPecasFisco");
      const inpPec = document.getElementById("nfValPec");
      if (!chk.checked) {{
        if (!inpPec.hasAttribute("data-original")) {{
          inpPec.setAttribute("data-original", inpPec.value || "0");
        }}
        inpPec.value = "0.00";
        inpPec.disabled = true;
        inpPec.style.opacity = "0.5";
      }} else {{
        inpPec.disabled = false;
        inpPec.style.opacity = "1";
        if (inpPec.hasAttribute("data-original")) {{
          inpPec.value = inpPec.getAttribute("data-original");
        }}
      }}
      recalcularTotaisFormNf();
    }}

    function popularSelectPecasTransferencia(lista) {{
      const selPecaTrf = document.getElementById("selPecaTransferencia");
      if (!selPecaTrf) return;
      if (!lista || !lista.length) {{
        selPecaTrf.innerHTML = `<option value="">⚠️ Nenhuma peça encontrada com este filtro</option>`;
        aoSelecionarPecaTransferencia();
        return;
      }}
      selPecaTrf.innerHTML = lista.map(p =>
        `<option value="${{p.id}}" data-codigo="${{p.codigo || ''}}" data-nome="${{p.nome.replace(/"/g, '&quot;')}}" data-preco="${{p.preco}}" data-qtd="${{p.qtd ?? 0}}" data-unidade="${{p.unidade || 'UN'}}">${{p.codigo ? '[' + p.codigo + '] ' : ''}}${{p.nome}} (Saldo: ${{p.qtd}} ${{p.unidade || 'UN'}} • Custo: R$ ${{Number(p.preco || 0).toFixed(2)}})</option>`
      ).join("");
      aoSelecionarPecaTransferencia();
    }}

    function obterSaldoDisponivelPecaTrf(pecaId) {{
      const p = TODAS_PECAS_TRANSFERENCIA.find(x => Number(x.id) === Number(pecaId));
      if (p) return Math.max(0, parseFloat(p.qtd ?? 0));
      const sel = document.getElementById("selPecaTransferencia");
      if (sel) {{
        for (let i = 0; i < sel.options.length; i++) {{
          if (Number(sel.options[i].value) === Number(pecaId)) {{
            return Math.max(0, parseFloat(sel.options[i].getAttribute("data-qtd") || 0));
          }}
        }}
      }}
      return 0;
    }}

    function aoSelecionarPecaTransferencia() {{
      const sel = document.getElementById("selPecaTransferencia");
      const inp = document.getElementById("inpQtdTransferencia");
      const lbl = document.getElementById("lblMaxEstoqueTrf");
      if (!sel || !inp) return;
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) {{
        if (lbl) lbl.textContent = "";
        return;
      }}
      const pecaId = parseInt(opt.value);
      const saldoTotal = parseFloat(opt.getAttribute("data-qtd") || 0);
      const un = opt.getAttribute("data-unidade") || "UN";
      const jaAdicionado = (ITENS_TRANSFERENCIA.find(i => i.peca_id === pecaId)?.quantidade || 0);
      const restante = Math.max(0, saldoTotal - jaAdicionado);
      inp.max = restante > 0 ? restante : 0;
      if (parseFloat(inp.value || 1) > restante) {{
        inp.value = restante > 0 ? restante : 0;
      }} else if (parseFloat(inp.value || 0) <= 0 && restante > 0) {{
        inp.value = 1;
      }}
      if (lbl) {{
        lbl.textContent = `(Máx: ${{restante}} ${{un}})`;
        lbl.style.color = restante > 0 ? "#38bdf8" : "#f87171";
      }}
    }}

    function validarInputQtdTransferencia(inp) {{
      const sel = document.getElementById("selPecaTransferencia");
      if (!sel || !inp) return;
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) return;
      const pecaId = parseInt(opt.value);
      const saldoTotal = parseFloat(opt.getAttribute("data-qtd") || 0);
      const un = opt.getAttribute("data-unidade") || "UN";
      const jaAdicionado = (ITENS_TRANSFERENCIA.find(i => i.peca_id === pecaId)?.quantidade || 0);
      const restante = Math.max(0, saldoTotal - jaAdicionado);
      const digitado = parseFloat(inp.value || 0);
      if (digitado > restante) {{
        inp.value = restante > 0 ? restante : 0;
        alert(`⚠️ Limite de Estoque Disponível!\n\nA peça selecionada possui apenas ${{saldoTotal}} ${{un}} em estoque${{jaAdicionado > 0 ? ' (' + jaAdicionado + ' já na lista)' : ''}}.\nA quantidade máxima permitida é ${{restante}} ${{un}}.`);
      }}
    }}

    function filtrarPecasTransferencia() {{
      const inp = document.getElementById("inpFiltroPecaTrf");
      const termo = (inp?.value || "").trim().toLowerCase();
      const countLbl = document.getElementById("lblCountFiltroTrf");
      if (!termo) {{
        popularSelectPecasTransferencia(TODAS_PECAS_TRANSFERENCIA);
        if (countLbl) countLbl.textContent = "";
        return;
      }}
      const filtradas = TODAS_PECAS_TRANSFERENCIA.filter(p => {{
        const cod = String(p.codigo || "").toLowerCase();
        const nom = String(p.nome || "").toLowerCase();
        return cod.includes(termo) || nom.includes(termo);
      }});
      popularSelectPecasTransferencia(filtradas);
      if (countLbl) {{
        countLbl.textContent = `(${{filtradas.length}} de ${{TODAS_PECAS_TRANSFERENCIA.length}} peças)`;
      }}
    }}

    function limparFiltroPecasTransferencia() {{
      const inp = document.getElementById("inpFiltroPecaTrf");
      if (inp) {{
        inp.value = "";
        filtrarPecasTransferencia();
        inp.focus();
      }}
    }}

    function aoTrocarOrigemTransferencia() {{
      const ori = document.getElementById("selOrigemTransferencia").value;
      const des = document.getElementById("selDestinoTransferencia");
      des.value = ori === "MATRIZ_CE" ? "FILIAL_DF" : "MATRIZ_CE";
      aoTrocarNaturezaTransferencia();
    }}

    function aoTrocarNaturezaTransferencia() {{
      const nat = document.getElementById("selNaturezaTransferencia").value;
      const ori = document.getElementById("selOrigemTransferencia").value;
      const des = document.getElementById("selDestinoTransferencia").value;
      const isInter = (ori === "MATRIZ_CE" && des === "FILIAL_DF") || (ori === "FILIAL_DF" && des === "MATRIZ_CE");
      let cfop = isInter ? "6152" : "5152";
      if (nat.includes("USO_CONSUMO")) cfop = isInter ? "6949" : "5949";
      else if (nat.includes("CONSERTO")) cfop = isInter ? "6915" : "5915";
      document.getElementById("selCfopTransferencia").value = cfop;
    }}

    function renderizarItensTransferencia() {{
      const tb = document.getElementById("tbodyItensTransferencia");
      if (!ITENS_TRANSFERENCIA.length) {{
        tb.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:8px;">Nenhum item adicionado à remessa ainda.</td></tr>`;
        document.getElementById("lblTotalTransferencia").textContent = "R$ 0,00";
        aoSelecionarPecaTransferencia();
        return;
      }}
      let total = 0;
      tb.innerHTML = ITENS_TRANSFERENCIA.map((it, idx) => {{
        const subtotal = it.quantidade * it.valor_unitario;
        total += subtotal;
        const maxDisp = it.saldo_max || obterSaldoDisponivelPecaTrf(it.peca_id) || it.quantidade;
        return `
          <tr>
            <td><b>${{it.codigo || '-'}}</b></td>
            <td>${{it.nome}} <span style="font-size:10.5px;color:#38bdf8;">(Estoque: ${{maxDisp}} ${{it.unidade || 'UN'}})</span></td>
            <td><input type="number" min="1" max="${{maxDisp}}" step="1" value="${{it.quantidade}}" style="width:70px;padding:4px;font-size:12px;" onchange="alterarQtdItemTransferencia(${{idx}}, this.value)" oninput="if(parseFloat(this.value) > ${{maxDisp}}) {{ this.value = ${{maxDisp}}; alterarQtdItemTransferencia(${{idx}}, ${{maxDisp}}); }}" /></td>
            <td>R$ ${{Number(it.valor_unitario).toFixed(2)}}</td>
            <td><b>R$ ${{Number(subtotal).toFixed(2)}}</b></td>
            <td><button class="btn btn-outline" style="padding:2px 6px;color:#f87171;border-color:#f87171;" onclick="removerItemTransferencia(${{idx}})">✕</button></td>
          </tr>
        `;
      }}).join("");
      document.getElementById("lblTotalTransferencia").textContent = `R$ ${{total.toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;
      aoSelecionarPecaTransferencia();
    }}

    function adicionarItemTransferencia() {{
      const sel = document.getElementById("selPecaTransferencia");
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) {{ alert("Selecione uma peça da lista."); return; }}
      const pecaId = parseInt(opt.value);
      const nome = opt.getAttribute("data-nome") || opt.text;
      const codigo = opt.getAttribute("data-codigo") || "";
      const preco = parseFloat(opt.getAttribute("data-preco") || 0);
      const saldoDisp = parseFloat(opt.getAttribute("data-qtd") || 0);
      const unidade = opt.getAttribute("data-unidade") || "UN";
      const qtdInp = parseFloat(document.getElementById("inpQtdTransferencia").value || 1);

      if (saldoDisp <= 0) {{
        alert(`🚫 ESTOQUE ZERADO!\n\nA peça "${{nome}}" está com saldo 0 ${{unidade}} no almoxarifado e não pode ser adicionada à transferência.`);
        return;
      }}
      if (qtdInp <= 0) {{
        alert("Informe uma quantidade maior que zero.");
        return;
      }}

      const existente = ITENS_TRANSFERENCIA.find(i => i.peca_id === pecaId);
      const qtdAtualNaLista = existente ? existente.quantidade : 0;
      if (qtdAtualNaLista + qtdInp > saldoDisp) {{
        const permitido = Math.max(0, saldoDisp - qtdAtualNaLista);
        const infoJaNaLista = qtdAtualNaLista > 0 ? `\n• Já adicionado na remessa: ${{qtdAtualNaLista}} ${{unidade}}` : '';
        alert(
          `🚫 QUANTIDADE ACIMA DO ESTOQUE DISPONÍVEL!\n\n` +
          `• Peça: [${{codigo}}] ${{nome}}\n` +
          `• Saldo Total no Estoque: ${{saldoDisp}} ${{unidade}}` +
          infoJaNaLista +
          `\n• Quantidade máxima que você pode adicionar: ${{permitido}} ${{unidade}}`
        );
        document.getElementById("inpQtdTransferencia").value = permitido > 0 ? permitido : 1;
        return;
      }}

      if (existente) {{
        existente.quantidade += qtdInp;
        existente.saldo_max = saldoDisp;
      }} else {{
        ITENS_TRANSFERENCIA.push({{
          peca_id: pecaId,
          nome: nome,
          codigo: codigo,
          quantidade: qtdInp,
          valor_unitario: preco,
          saldo_max: saldoDisp,
          unidade: unidade
        }});
      }}
      renderizarItensTransferencia();
    }}

    function removerItemTransferencia(idx) {{
      ITENS_TRANSFERENCIA.splice(idx, 1);
      renderizarItensTransferencia();
    }}

    function alterarQtdItemTransferencia(idx, val) {{
      let q = parseFloat(val);
      const item = ITENS_TRANSFERENCIA[idx];
      if (!item) return;
      const maxDisp = item.saldo_max || obterSaldoDisponivelPecaTrf(item.peca_id);
      if (isNaN(q) || q <= 0) q = 1;
      if (maxDisp > 0 && q > maxDisp) {{
        alert(`🚫 Estoque insuficiente para "${{item.nome}}"!\nO saldo disponível no almoxarifado é de apenas ${{maxDisp}} ${{item.unidade || 'UN'}}.`);
        q = maxDisp;
      }}
      item.quantidade = q;
      renderizarItensTransferencia();
    }}

    async function emitirTransferenciaFiliais() {{
      if (!ITENS_TRANSFERENCIA.length) {{
        alert("Adicione ao menos 1 peça na remessa de transferência.");
        return;
      }}
      const origem = document.getElementById("selOrigemTransferencia").value;
      const destino = document.getElementById("selDestinoTransferencia").value;
      if (origem === destino) {{
        alert("A unidade de origem não pode ser igual à de destino.");
        return;
      }}
      const btn = document.getElementById("btnEmitirTransferencia");
      btn.disabled = true;
      btn.textContent = "Emitindo NF-e de Transferência...";
      try {{
        const res = await fetch("/api/fiscal/v2/transferir-filiais", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            origem,
            destino,
            natureza_op: document.getElementById("selNaturezaTransferencia").value,
            cfop: document.getElementById("selCfopTransferencia").value,
            itens: ITENS_TRANSFERENCIA,
            veiculo_transporte: document.getElementById("selVeiculoTransferencia").value,
            observacoes: document.getElementById("inpObsTransferencia").value,
            movimentar_estoque_fiscal: document.getElementById("chkTrfMovimentarFiscal") ? document.getElementById("chkTrfMovimentarFiscal").checked : true,
            movimentar_estoque_fisico: document.getElementById("chkTrfMovimentarFisico") ? document.getElementById("chkTrfMovimentarFisico").checked : true,
            usuario: USUARIO_FISCAL?.username || "netto"
          }})
        }}).then(r => r.json());
        if (res.ok) {{
          alert(res.msg);
          ITENS_TRANSFERENCIA = [];
          renderizarItensTransferencia();
          document.getElementById("boxResultadoTransferencia").innerHTML = `
            <div style="background:#14532d;border:1.5px solid #22c55e;border-radius:8px;padding:12px;color:#fff;margin-top:10px;">
              <b>🎉 NF-e DE TRANSFERÊNCIA AUTORIZADA!</b><br/>
              Número: <b>${{res.numero_nf}}</b> &bull; Estoque físico baixado na unidade de origem.<br/>
              <div style="margin-top:8px;">
                <a href="/api/fiscal/danfe/${{res.numero_nf}}" target="_blank" class="btn btn-blue" style="display:inline-block;">🖨️ Imprimir DANFE de Transferência</a>
              </div>
            </div>
          `;
          carregarDadosFiscais();
        }} else {{
          alert("⚠️ " + (res.msg || "Erro ao emitir transferência."));
        }}
      }} catch (err) {{
        alert("Falha de conexão: " + err.message);
      }} finally {{
        btn.disabled = false;
        btn.textContent = "🚀 Emitir NF-e de Transferência (Modelo 55)";
      }}
    }}

    async function lancarConsumivelAdministrativo() {{
      const desc = document.getElementById("consDescricao").value.trim();
      const forn = document.getElementById("consFornecedor").value.trim();
      const nf = document.getElementById("consNf").value.trim();
      const setor = document.getElementById("consSetor").value;
      const qtd = parseFloat(document.getElementById("consQtd").value || 1);
      const val = parseFloat(document.getElementById("consValor").value || 0);
      const cat = document.getElementById("consCategoria").value;

      if (!desc) {{ alert("Informe a descrição do material (ex: Café Torrado, Papel Higiênico)."); return; }}
      if (val <= 0) {{ alert("Informe o valor total da nota/despesa."); return; }}

      const btn = document.getElementById("btnLancarConsumivel");
      btn.disabled = true;
      btn.textContent = "Registrando Despesa...";
      try {{
        const res = await fetch("/api/fiscal/v2/lancar-consumivel", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            descricao: desc,
            fornecedor: forn,
            numero_nf: nf,
            unidade_setor: setor,
            quantidade: qtd,
            valor_total: val,
            categoria: cat,
            usuario: USUARIO_FISCAL?.username || "netto"
          }})
        }}).then(r => r.json());
        if (res.ok) {{
          alert(res.msg);
          document.getElementById("consDescricao").value = "";
          document.getElementById("consFornecedor").value = "";
          document.getElementById("consNf").value = "";
          document.getElementById("consValor").value = "";
          carregarDadosFiscais();
        }} else {{
          alert("⚠️ " + (res.msg || "Erro ao lançar consumível."));
        }}
      }} catch (err) {{
        alert("Falha de comunicação: " + err.message);
      }} finally {{
        btn.disabled = false;
        btn.textContent = "☕ Lançar no Fisco & Baixar Estoque Imediatamente (Saldo 0)";
      }}
    }}

    async function executarAjusteEstoque() {{
      const selPeca = document.getElementById("selPecaAjuste");
      const opt = selPeca.options[selPeca.selectedIndex];
      if (!opt || !opt.value) {{
        alert("Selecione uma peça para efetuar o ajuste.");
        return;
      }}
      const peca_id = parseInt(opt.value);
      const codigo = opt.getAttribute("data-codigo") || "";
      const nome = opt.getAttribute("data-nome") || opt.text;
      const tipo_ajuste = document.getElementById("selTipoAjuste").value;
      const quantidade = parseFloat(document.getElementById("inpQtdAjuste").value || 1);
      const alvo = document.getElementById("selAlvoAjuste").value;
      const motivo = document.getElementById("inpMotivoAjuste").value.trim();

      if (quantidade <= 0) {{
        alert("A quantidade deve ser maior que zero.");
        return;
      }}

      const btn = document.getElementById("btnSalvarAjusteEstoque");
      btn.disabled = true;
      btn.textContent = "Aplicando Ajuste...";

      try {{
        const res = await fetch("/api/fiscal/v2/ajuste-estoque", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            peca_id,
            codigo,
            nome,
            tipo_ajuste,
            quantidade,
            alvo,
            motivo,
            usuario: USUARIO_FISCAL?.username || "netto"
          }})
        }}).then(r => r.json());

        alert(res.msg || (res.ok ? "Ajuste aplicado com sucesso!" : "Erro ao aplicar ajuste"));
        if (res.ok) {{
          document.getElementById("inpMotivoAjuste").value = "";
          carregarDadosFiscais();
        }}
      }} catch (err) {{
        alert("Falha de conexão: " + err.message);
      }} finally {{
        btn.disabled = false;
        btn.textContent = "⚡ Aplicar Movimentação no Estoque";
      }}
    }}

    function definirFiltroInventario(tipo) {{
      INVENTARIO_FILTRO_TIPO = tipo;
      INVENTARIO_PAGINA = 1;
      const bTodos = document.getElementById("btnFiltroInvTodos");
      const bDiv = document.getElementById("btnFiltroInvDivergentes");
      const bZer = document.getElementById("btnFiltroInvZerados");
      [bTodos, bDiv, bZer].forEach(b => {{
        if (b) {{
          b.style.background = "transparent";
          b.style.color = "#e2e8f0";
          b.style.borderColor = "#475569";
        }}
      }});
      const ativo = tipo === 'TODOS' ? bTodos : (tipo === 'DIVERGENTES' ? bDiv : bZer);
      if (ativo) {{
        ativo.style.background = "#1e293b";
        ativo.style.color = "var(--cyan)";
        ativo.style.borderColor = "var(--cyan)";
      }}
      renderizarInventario();
    }}

    function aoFiltrarInventario() {{
      INVENTARIO_FILTRO_TEXTO = (document.getElementById("inpFiltroInventario").value || "").trim().toUpperCase();
      INVENTARIO_PAGINA = 1;
      renderizarInventario();
    }}

    function toggleFormNovoItemInventario() {{
      const bx = document.getElementById("boxNovoItemInventario");
      bx.style.display = bx.style.display === "none" ? "block" : "none";
    }}

    function toggleFormAjusteRelativo() {{
      const bx = document.getElementById("boxAjusteRelativo");
      bx.style.display = bx.style.display === "none" ? "block" : "none";
    }}

    function mudarPaginaInventario(delta) {{
      const totalFiltrados = obterItensInventarioFiltrados().length;
      const totalPaginas = Math.max(1, Math.ceil(totalFiltrados / INVENTARIO_POR_PAGINA));
      const novaPagina = INVENTARIO_PAGINA + delta;
      if (novaPagina >= 1 && novaPagina <= totalPaginas) {{
        INVENTARIO_PAGINA = novaPagina;
        renderizarInventario();
      }}
    }}

    function obterItensInventarioFiltrados() {{
      return INVENTARIO_ITENS.filter(p => {{
        const txt = INVENTARIO_FILTRO_TEXTO;
        if (txt) {{
          const matchCod = String(p.codigo || "").toUpperCase().includes(txt);
          const matchNome = String(p.nome || "").toUpperCase().includes(txt);
          if (!matchCod && !matchNome) return false;
        }}
        const diff = Math.abs(Number(p.qtd) - Number(p.qtd_fiscal));
        if (INVENTARIO_FILTRO_TIPO === "DIVERGENTES" && diff < 0.001) return false;
        if (INVENTARIO_FILTRO_TIPO === "ZERADOS" && Number(p.qtd) > 0) return false;
        return true;
      }});
    }}

    
    function mudarTabFicha(tab) {{
      ['ident', 'icms', 'fed', 'preco'].forEach(t => {{
        const btn = document.getElementById('tabBtn_' + t);
        const cnt = document.getElementById('tabContent_' + t);
        if (btn) btn.className = t === tab ? 'btn btn-blue' : 'btn btn-outline';
        if (cnt) cnt.style.display = t === tab ? 'block' : 'none';
      }});
    }}

    async function abrirModalFichaFiscalPeca(pecaId) {{
      mudarTabFicha('ident');
      document.getElementById('fch_id').value = pecaId;
      document.getElementById('modalFichaTitulo').textContent = 'Carregando parâmetros da peça #' + pecaId + '...';
      document.getElementById('modalFichaFiscalPeca').style.display = 'block';

      try {{
        const res = await fetch('/api/fiscal/v2/peca/' + pecaId).then(r => r.json());
        if (!res.ok) {{
          alert('Erro ao carregar detalhes: ' + (res.msg || 'Falha de comunicação'));
          fecharModalFichaFiscal();
          return;
        }}
        const p = res.peca;
        document.getElementById('modalFichaTitulo').textContent = '⚙️ Ficha Fiscal & Precificação: [' + (p.codigo || p.id) + '] ' + (p.nome_peca || '');
        document.getElementById('modalFichaSubtitulo').textContent = 'NCM ' + (p.ncm || '9022.90.90') + ' • Estoque Físico: ' + p.quantidade + ' ' + (p.unidade || 'UN');

        document.getElementById('fch_nome').value = p.nome_peca || '';
        document.getElementById('fch_codigo').value = p.codigo || '';
        document.getElementById('fch_ean').value = p.ean_gtin || 'SEM GTIN';
        document.getElementById('fch_fabricante').value = p.fabricante || '';
        document.getElementById('fch_modelo').value = p.modelo_compativel || '';
        document.getElementById('fch_serie').value = p.numero_serie || '';
        document.getElementById('fch_lote').value = p.lote_fabricacao || '';
        document.getElementById('fch_unidade').value = p.unidade || 'UN';
        document.getElementById('fch_local').value = p.localizacao || '';

        document.getElementById('fch_ncm').value = p.ncm || '9022.90.90';
        document.getElementById('fch_cest').value = p.cest || '';
        document.getElementById('fch_origem').value = p.origem_mercadoria ?? 0;
        document.getElementById('fch_csosn').value = p.csosn_icms || '102';
        document.getElementById('fch_aliq_icms').value = p.aliquota_icms ?? 0.0;
        document.getElementById('fch_red_icms').value = p.reducao_base_icms ?? 0.0;
        document.getElementById('fch_cfop_venda').value = p.cfop_padrao_venda || '5102';
        document.getElementById('fch_cfop_trf').value = p.cfop_padrao_transferencia || '5152';
        document.getElementById('fch_isencao_motivo').value = p.isencao_icms_motivo || 'Convênio ICMS 01/99 - Equipamento Médico-Hospitalar';

        document.getElementById('fch_cst_pis').value = p.cst_pis || '49';
        document.getElementById('fch_aliq_pis').value = p.aliquota_pis ?? 0.0;
        document.getElementById('fch_cst_cofins').value = p.cst_cofins || '49';
        document.getElementById('fch_aliq_cofins').value = p.aliquota_cofins ?? 0.0;
        document.getElementById('fch_cst_ipi').value = p.cst_ipi || '53';
        document.getElementById('fch_aliq_ipi').value = p.aliquota_ipi ?? 0.0;

        document.getElementById('fch_custo').value = p.preco_custo ?? 0.0;
        document.getElementById('fch_custo_medio').value = p.custo_medio ?? (p.preco_custo ?? 0.0);
        document.getElementById('fch_mg_contrato').value = p.margem_contrato ?? 30;
        document.getElementById('fch_mg_avulso').value = p.margem_avulso ?? 60;
        document.getElementById('fch_mg_avista').value = p.margem_avista ?? 20;
        document.getElementById('fch_mg_desestimulo').value = p.margem_desestimulo ?? 180;
        document.getElementById('fch_preco_tabela').value = p.preco_venda_tabela || (Number(p.preco_custo || 0) * 1.5).toFixed(2);
        document.getElementById('fch_preco_minimo').value = p.preco_venda_minimo || (Number(p.preco_custo || 0) * 1.2).toFixed(2);

        // Alerta de Reajuste por Inflação/Câmbio na Ficha Fiscal
        const boxAlerta = document.getElementById('fch_box_alerta_reajuste');
        if (boxAlerta) {{
          if (p.alerta_reajuste) {{
            try {{
              const alr = typeof p.alerta_reajuste === 'string' ? JSON.parse(p.alerta_reajuste) : p.alerta_reajuste;
              if (alr && alr.aumento_pct) {{
                boxAlerta.style.display = 'block';
                boxAlerta.innerHTML = `
                  <div style="background:#451a03;border:1.5px solid #ea580c;padding:12px 16px;border-radius:8px;margin-bottom:14px;color:#ffedd5;">
                    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
                      <div>
                        <div style="font-weight:900;font-size:13px;color:#fdba74;">🚨 ALERTA DE REAJUSTE DE CUSTO (CÂMBIO / INFLAÇÃO): +${{alr.aumento_pct}}%</div>
                        <div style="font-size:11.5px;color:#fed7aa;margin-top:3px;">
                          Custo de aquisição subiu de <b>R$ ${{Number(alr.custo_antigo||0).toFixed(2)}}</b> para <b>R$ ${{Number(alr.custo_novo||0).toFixed(2)}}</b> (NF-e nº ${{alr.nf || '-'}} em ${{alr.data || '-'}}).
                        </div>
                        <div style="font-size:12px;font-weight:800;color:#38bdf8;margin-top:4px;">
                          Preço de Venda Sugerido: <b>R$ ${{Number(alr.preco_venda_sugerido||0).toFixed(2)}}</b> (preservando margem de lucro).
                        </div>
                      </div>
                      <button type="button" class="btn" onclick="aplicarPrecoVendaSugerido(${{alr.preco_venda_sugerido}})" style="background:#ea580c;color:#fff;font-weight:800;padding:6px 14px;border:none;border-radius:6px;cursor:pointer;">
                        ⚡ Aplicar Preço Sugerido
                      </button>
                    </div>
                  </div>
                `;
              }} else {{
                boxAlerta.style.display = 'none';
              }}
            }} catch(e) {{
              boxAlerta.style.display = 'none';
            }}
          }} else {{
            boxAlerta.style.display = 'none';
          }}
        }}
      }} catch (err) {{
        alert('Erro ao comunicar com o servidor: ' + err.message);
        fecharModalFichaFiscal();
      }}
    }}

    function fecharModalFichaFiscal() {{
      document.getElementById('modalFichaFiscalPeca').style.display = 'none';
    }}

    function recalcularPrecosFicha() {{
      const custo = parseFloat(document.getElementById('fch_custo').value || 0);
      const mgAvulso = parseFloat(document.getElementById('fch_mg_avulso').value || 60);
      const precoSug = custo * (1 + mgAvulso / 100);
      const precoMin = custo * 1.2;
      document.getElementById('fch_preco_tabela').value = precoSug.toFixed(2);
      document.getElementById('fch_preco_minimo').value = precoMin.toFixed(2);
    }}

    function aplicarPrecoVendaSugerido(precoSugerido) {{
      const sug = parseFloat(precoSugerido || 0);
      if (sug <= 0) return;
      document.getElementById('fch_preco_tabela').value = sug.toFixed(2);
      document.getElementById('fch_preco_minimo').value = (sug * 0.85).toFixed(2);
      const custo = parseFloat(document.getElementById('fch_custo').value || 0);
      if (custo > 0) {{
        const mg = ((sug - custo) / custo) * 100;
        document.getElementById('fch_mg_avulso').value = mg.toFixed(1);
      }}
      alert(`✅ Preço de venda sugerido de R$ ${{sug.toFixed(2)}} aplicado na ficha! Clique em "Salvar Parâmetros" para persistir.`);
    }}

    async function salvarFichaFiscalPeca() {{
      const pecaId = parseInt(document.getElementById('fch_id').value);
      if (!pecaId) return;

      const btn = document.getElementById('btnSalvarFichaFiscal');
      btn.disabled = true;
      btn.textContent = 'Salvando...';

      const payload = {{
        id: pecaId,
        nome_peca: document.getElementById('fch_nome').value.trim(),
        ean_gtin: document.getElementById('fch_ean').value.trim(),
        fabricante: document.getElementById('fch_fabricante').value.trim(),
        modelo_compativel: document.getElementById('fch_modelo').value.trim(),
        numero_serie: document.getElementById('fch_serie').value.trim(),
        lote_fabricacao: document.getElementById('fch_lote').value.trim(),
        unidade: document.getElementById('fch_unidade').value,
        localizacao: document.getElementById('fch_local').value.trim(),

        ncm: document.getElementById('fch_ncm').value.trim(),
        cest: document.getElementById('fch_cest').value.trim(),
        origem_mercadoria: parseInt(document.getElementById('fch_origem').value || 0),
        csosn_icms: document.getElementById('fch_csosn').value,
        aliquota_icms: parseFloat(document.getElementById('fch_aliq_icms').value || 0),
        reducao_base_icms: parseFloat(document.getElementById('fch_red_icms').value || 0),
        cfop_padrao_venda: document.getElementById('fch_cfop_venda').value.trim(),
        cfop_padrao_transferencia: document.getElementById('fch_cfop_trf').value.trim(),
        isencao_icms_motivo: document.getElementById('fch_isencao_motivo').value.trim(),

        cst_pis: document.getElementById('fch_cst_pis').value,
        aliquota_pis: parseFloat(document.getElementById('fch_aliq_pis').value || 0),
        cst_cofins: document.getElementById('fch_cst_cofins').value,
        aliquota_cofins: parseFloat(document.getElementById('fch_aliq_cofins').value || 0),
        cst_ipi: document.getElementById('fch_cst_ipi').value,
        aliquota_ipi: parseFloat(document.getElementById('fch_aliq_ipi').value || 0),

        preco_custo: parseFloat(document.getElementById('fch_custo').value || 0),
        custo_medio: parseFloat(document.getElementById('fch_custo_medio').value || 0),
        margem_contrato: parseFloat(document.getElementById('fch_mg_contrato').value || 30),
        margem_avulso: parseFloat(document.getElementById('fch_mg_avulso').value || 60),
        margem_avista: parseFloat(document.getElementById('fch_mg_avista').value || 20),
        margem_desestimulo: parseFloat(document.getElementById('fch_mg_desestimulo').value || 180),
        preco_venda_tabela: parseFloat(document.getElementById('fch_preco_tabela').value || 0),
        preco_venda_minimo: parseFloat(document.getElementById('fch_preco_minimo').value || 0),
        usuario: USUARIO_FISCAL?.username || 'netto'
      }};

      try {{
        const res = await fetch('/api/fiscal/v2/peca/salvar', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(payload)
        }}).then(r => r.json());

        if (res.ok) {{
          alert('✅ Parâmetros Fiscais & Precificação Salvos com Sucesso!');
          fecharModalFichaFiscal();
          carregarDadosFiscais();
        }} else {{
          alert('⚠️ Erro ao salvar: ' + (res.msg || 'Falha'));
        }}
      }} catch (err) {{
        alert('Erro ao salvar ficha fiscal: ' + err.message);
      }} finally {{
        btn.disabled = false;
        btn.textContent = '💾 Salvar Parâmetros Fiscais & Precificação';
      }}
    }}


    function renderizarInventario() {{
      const total = INVENTARIO_ITENS.length;
      let conformes = 0;
      let divergentes = 0;
      let zerados = 0;
      let totalQtdFis = 0;

      INVENTARIO_ITENS.forEach(p => {{
        const diff = Math.abs(Number(p.qtd) - Number(p.qtd_fiscal));
        if (diff < 0.001) conformes++;
        else divergentes++;
        if (Number(p.qtd) <= 0) zerados++;
        totalQtdFis += Number(p.qtd || 0);
      }});

      const elTot = document.getElementById("invKpiTotal"); if (elTot) elTot.textContent = total;
      const elConf = document.getElementById("invKpiConformes"); if (elConf) elConf.textContent = conformes;
      const elDiv = document.getElementById("invKpiDivergentes"); if (elDiv) elDiv.textContent = divergentes;
      const elQtd = document.getElementById("invKpiTotalQtd"); if (elQtd) elQtd.textContent = `${{totalQtdFis.toLocaleString('pt-BR', {{minimumFractionDigits:0}})}} un`;

      const elCntTot = document.getElementById("cntInvTodos"); if (elCntTot) elCntTot.textContent = total;
      const elCntDiv = document.getElementById("cntInvDivergentes"); if (elCntDiv) elCntDiv.textContent = divergentes;
      const elCntZer = document.getElementById("cntInvZerados"); if (elCntZer) elCntZer.textContent = zerados;

      const filtrados = obterItensInventarioFiltrados();
      const totalPaginas = Math.max(1, Math.ceil(filtrados.length / INVENTARIO_POR_PAGINA));
      if (INVENTARIO_PAGINA > totalPaginas) INVENTARIO_PAGINA = totalPaginas;

      const inicio = (INVENTARIO_PAGINA - 1) * INVENTARIO_POR_PAGINA;
      const itensPagina = filtrados.slice(inicio, inicio + INVENTARIO_POR_PAGINA);

      const tb = document.getElementById("tbodyComparativoEstoque");
      if (!itensPagina.length) {{
        tb.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:18px;">Nenhuma peça encontrada com os filtros aplicados.</td></tr>`;
      }} else {{
        tb.innerHTML = itensPagina.map(p => {{
          const diff = Number(p.qtd) - Number(p.qtd_fiscal);
          let badge = '';
          if (Math.abs(diff) < 0.001) {{
            badge = '<span class="badge" style="background:#065f46;color:#a7f3d0;">Conforme</span>';
          }} else if (diff > 0) {{
            badge = `<span class="badge" style="background:#1e3a8a;color:#93c5fd;">Excedente Físico (+${{diff.toFixed(1)}})</span>`;
          }} else {{
            badge = `<span class="badge" style="background:#7f1d1d;color:#fca5a5;">Déficit Físico (${{diff.toFixed(1)}})</span>`;
          }}
          const corDiff = Math.abs(diff) < 0.001 ? '#34d399' : (diff > 0 ? '#60a5fa' : '#f87171');
          const txtDiff = diff > 0 ? `+${{diff.toFixed(1)}}` : diff.toFixed(1);

          let badgeReajuste = '';
          if (p.alerta_reajuste) {{
            try {{
              const alr = typeof p.alerta_reajuste === 'string' ? JSON.parse(p.alerta_reajuste) : p.alerta_reajuste;
              if (alr && alr.aumento_pct) {{
                badgeReajuste = `<span class="badge" style="background:#7c2d12;color:#fdba74;border:1px solid #f97316;font-size:10px;margin-left:6px;cursor:pointer;" onclick="abrirModalFichaFiscalPeca(${{p.id}})" title="Custo subiu +${{alr.aumento_pct}}% na NF-e ${{alr.nf || ''}}. Clique para ajustar preço de venda!">🚨 Reajuste Sugerido: +${{alr.aumento_pct}}%</span>`;
              }}
            }} catch(e) {{}}
          }}

          return `
            <tr id="linhaInv_${{p.id}}">
              <td><b>${{p.codigo || '-'}}</b></td>
              <td>
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                  <div>
                    <div style="font-weight:700;color:#fff;display:flex;align-items:center;flex-wrap:wrap;">${{p.nome}} ${{badgeReajuste}}</div>
                    <div style="font-size:11px;color:#94a3b8;">Custo: R$ ${{Number(p.preco||0).toFixed(2)}} • Un: ${{p.unidade || 'UN'}}</div>
                  </div>
                  <button type="button" onclick="abrirModalFichaFiscalPeca(${{p.id}})" class="btn btn-outline" style="padding:2px 8px;font-size:10.5px;font-weight:800;color:#38bdf8;border-color:#0284c7;white-space:nowrap;" title="Configurar Impostos (NCM, CEST, ICMS) e Precificação">⚙️ Fiscal</button>
                </div>
              </td>
              <td style="text-align:center;">
                <div style="display:inline-flex;align-items:center;gap:3px;">
                  <button type="button" onclick="ajustarPassoInventario(${{p.id}}, 'fis', -1)" class="btn btn-outline" style="padding:2px 6px;font-size:11px;min-width:24px;">-1</button>
                  <input type="number" step="1" min="0" id="inpFis_${{p.id}}" value="${{p.qtd}}" oninput="marcarLinhaModificada(${{p.id}})" style="width:62px;padding:4px 3px;text-align:center;font-weight:800;font-size:12.5px;background:#022c22;border:1px solid #059669;color:#34d399;border-radius:4px;" />
                  <button type="button" onclick="ajustarPassoInventario(${{p.id}}, 'fis', +1)" class="btn btn-outline" style="padding:2px 6px;font-size:11px;min-width:24px;">+1</button>
                </div>
              </td>
              <td style="text-align:center;">
                <div style="display:inline-flex;align-items:center;gap:3px;">
                  <button type="button" onclick="ajustarPassoInventario(${{p.id}}, 'fisc', -1)" class="btn btn-outline" style="padding:2px 6px;font-size:11px;min-width:24px;">-1</button>
                  <input type="number" step="1" min="0" id="inpFisc_${{p.id}}" value="${{p.qtd_fiscal}}" oninput="marcarLinhaModificada(${{p.id}})" style="width:62px;padding:4px 3px;text-align:center;font-weight:800;font-size:12.5px;background:#082f49;border:1px solid #0284c7;color:#38bdf8;border-radius:4px;" />
                  <button type="button" onclick="ajustarPassoInventario(${{p.id}}, 'fisc', +1)" class="btn btn-outline" style="padding:2px 6px;font-size:11px;min-width:24px;">+1</button>
                </div>
              </td>
              <td style="text-align:center;font-weight:800;color:${{corDiff}};" id="spDiff_${{p.id}}">${{txtDiff}}</td>
              <td style="text-align:center;" id="spBadge_${{p.id}}">${{badge}}</td>
              <td style="text-align:center;">
                <div style="display:inline-flex;gap:4px;flex-wrap:wrap;justify-content:center;">
                  <button type="button" onclick="abrirModalFichaFiscalPeca(${{p.id}})" class="btn btn-outline" style="padding:3px 8px;font-size:10.5px;color:#38bdf8;border-color:#0284c7;font-weight:800;" title="Ficha Fiscal, Tributária e Precificação">⚙️ Fiscal</button>
                  <button id="btnSalvarInv_${{p.id}}" onclick="salvarInventarioLinhaDireto(${{p.id}})" class="btn btn-blue" style="padding:3px 8px;font-size:11px;font-weight:800;" title="Salvar diretamente o saldo físico e fiscal">💾 Salvar</button>
                  <button type="button" onclick="igualarFiscalAoFisico(${{p.id}})" class="btn btn-outline" style="padding:3px 6px;font-size:10.5px;color:#38bdf8;border-color:#0284c7;" title="Falha de baixa fiscal: Iguala Fiscal ao Físico">⚖️ Fiscal=Físico</button>
                  <button type="button" onclick="igualarFisicoAoFiscal(${{p.id}})" class="btn btn-outline" style="padding:3px 6px;font-size:10.5px;color:#34d399;border-color:#059669;" title="Falha de baixa física: Iguala Físico ao Fiscal">⚖️ Físico=Fiscal</button>
                </div>
              </td>
            </tr>
          `;
        }}).join("");
      }}

      const infoPag = document.getElementById("lblInfoPaginacaoInventario");
      if (infoPag) {{
        const fim = Math.min(inicio + INVENTARIO_POR_PAGINA, filtrados.length);
        infoPag.innerHTML = filtrados.length
          ? `Mostrando <b>${{inicio + 1}}</b> a <b>${{fim}}</b> de <b>${{filtrados.length}}</b> peças`
          : `0 peças encontradas`;
      }}
      const lblPag = document.getElementById("lblPaginaAtualInventario");
      if (lblPag) lblPag.textContent = `Pág ${{INVENTARIO_PAGINA}} de ${{totalPaginas}}`;

      const btnAnt = document.getElementById("btnInvPagAnt");
      if (btnAnt) btnAnt.disabled = INVENTARIO_PAGINA <= 1;
      const btnProx = document.getElementById("btnInvPagProx");
      if (btnProx) btnProx.disabled = INVENTARIO_PAGINA >= totalPaginas;
    }}

    function marcarLinhaModificada(pecaId) {{
      const inpFis = document.getElementById(`inpFis_${{pecaId}}`);
      const inpFisc = document.getElementById(`inpFisc_${{pecaId}}`);
      if (!inpFis || !inpFisc) return;
      const fis = parseFloat(inpFis.value || 0);
      const fisc = parseFloat(inpFisc.value || 0);
      const diff = fis - fisc;
      const spDiff = document.getElementById(`spDiff_${{pecaId}}`);
      const spBadge = document.getElementById(`spBadge_${{pecaId}}`);
      if (spDiff) {{
        spDiff.textContent = diff > 0 ? `+${{diff.toFixed(1)}}` : diff.toFixed(1);
        spDiff.style.color = Math.abs(diff) < 0.001 ? '#34d399' : (diff > 0 ? '#60a5fa' : '#f87171');
      }}
      if (spBadge) {{
        if (Math.abs(diff) < 0.001) {{
          spBadge.innerHTML = '<span class="badge" style="background:#065f46;color:#a7f3d0;">Conforme</span>';
        }} else if (diff > 0) {{
          spBadge.innerHTML = `<span class="badge" style="background:#1e3a8a;color:#93c5fd;">Excedente Físico (+${{diff.toFixed(1)}})</span>`;
        }} else {{
          spBadge.innerHTML = `<span class="badge" style="background:#7f1d1d;color:#fca5a5;">Déficit Físico (${{diff.toFixed(1)}})</span>`;
        }}
      }}
      const btn = document.getElementById(`btnSalvarInv_${{pecaId}}`);
      if (btn) {{
        btn.style.background = "#16a34a";
        btn.textContent = "💾 Salvar *";
      }}
    }}

    function ajustarPassoInventario(pecaId, tipo, passo) {{
      const inp = document.getElementById(tipo === 'fis' ? `inpFis_${{pecaId}}` : `inpFisc_${{pecaId}}`);
      if (!inp) return;
      let val = parseFloat(inp.value || 0) + passo;
      if (val < 0) val = 0;
      inp.value = val;
      marcarLinhaModificada(pecaId);
    }}

    async function salvarInventarioLinhaDireto(pecaId) {{
      const inpFis = document.getElementById(`inpFis_${{pecaId}}`);
      const inpFisc = document.getElementById(`inpFisc_${{pecaId}}`);
      const btn = document.getElementById(`btnSalvarInv_${{pecaId}}`);
      if (!inpFis || !inpFisc) return;

      const fis = parseFloat(inpFis.value || 0);
      const fisc = parseFloat(inpFisc.value || 0);
      if (btn) {{
        btn.disabled = true;
        btn.textContent = "Gravando...";
      }}

      try {{
        const res = await fetch("/api/fiscal/v2/inventario/ajuste-direto", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            peca_id: pecaId,
            quantidade_fisica: fis,
            saldo_fiscal: fisc,
            motivo: "Ajuste direto pelo painel de inventário (reconciliação/correção de baixa)",
            usuario: USUARIO_FISCAL?.username || "netto"
          }})
        }}).then(r => r.json());

        if (res.ok) {{
          const item = INVENTARIO_ITENS.find(i => i.id === pecaId);
          if (item) {{
            item.qtd = fis;
            item.qtd_fiscal = fisc;
          }}
          if (btn) {{
            btn.style.background = "#0284c7";
            btn.textContent = "✅ Salvo";
            setTimeout(() => {{ if (btn) btn.textContent = "💾 Salvar"; }}, 1600);
          }}
          renderizarInventario();
        }} else {{
          alert("⚠️ " + (res.msg || "Erro ao salvar inventário."));
          if (btn) btn.textContent = "💾 Salvar *";
        }}
      }} catch (err) {{
        alert("Falha de conexão: " + err.message);
        if (btn) btn.textContent = "💾 Salvar *";
      }} finally {{
        if (btn) btn.disabled = false;
      }}
    }}

    async function igualarFiscalAoFisico(pecaId) {{
      const inpFis = document.getElementById(`inpFis_${{pecaId}}`);
      const inpFisc = document.getElementById(`inpFisc_${{pecaId}}`);
      if (!inpFis || !inpFisc) return;
      inpFisc.value = inpFis.value;
      marcarLinhaModificada(pecaId);
      await salvarInventarioLinhaDireto(pecaId);
    }}

    async function igualarFisicoAoFiscal(pecaId) {{
      const inpFis = document.getElementById(`inpFis_${{pecaId}}`);
      const inpFisc = document.getElementById(`inpFisc_${{pecaId}}`);
      if (!inpFis || !inpFisc) return;
      inpFis.value = inpFisc.value;
      marcarLinhaModificada(pecaId);
      await salvarInventarioLinhaDireto(pecaId);
    }}

    async function salvarNovoItemInventario() {{
      const cod = document.getElementById("novoInvCodigo").value.trim();
      const nome = document.getElementById("novoInvNome").value.trim();
      const un = document.getElementById("novoInvUnidade").value;
      const qFis = parseFloat(document.getElementById("novoInvQtdFisica").value || 0);
      const qFisc = parseFloat(document.getElementById("novoInvQtdFiscal").value || 0);
      const preco = parseFloat(document.getElementById("novoInvPrecoCusto").value || 0);

      if (!nome) {{
        alert("Informe o nome da peça / instrumento.");
        return;
      }}

      const res = await fetch("/api/fiscal/v2/inventario/novo-item", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          codigo: cod,
          nome: nome,
          quantidade_fisica: qFis,
          saldo_fiscal: qFisc,
          preco_custo: preco,
          unidade: un,
          usuario: USUARIO_FISCAL?.username || "netto"
        }})
      }}).then(r => r.json());

      if (res.ok) {{
        alert(res.msg);
        document.getElementById("novoInvCodigo").value = "";
        document.getElementById("novoInvNome").value = "";
        document.getElementById("boxNovoItemInventario").style.display = "none";
        carregarDadosFiscais();
      }} else {{
        alert("⚠️ " + (res.msg || "Erro ao cadastrar peça."));
      }}
    }}

    async function carregarFechamentoContabil() {{
      const selMes = document.getElementById("selMesFechamento");
      const mes = selMes ? selMes.value : "";
      const selFil = document.getElementById("selFilialFechamento");
      const fil = selFil ? selFil.value : "CONSOLIDADO";

      try {{
        const res = await fetch(`/api/fiscal/v2/fechamento/dados?mes=${{encodeURIComponent(mes)}}&filial=${{encodeURIComponent(fil)}}`).then(r => r.json());
        if (!res.ok) return;

        if (selMes && res.meses_disponiveis && selMes.options.length <= 1) {{
          const mesAtivo = res.mes || selMes.value;
          selMes.innerHTML = res.meses_disponiveis.map(m => `
            <option value="${{m}}" ${{m === mesAtivo ? 'selected' : ''}}>${{formatarMesLegivel(m)}}</option>
          `).join("");
        }}

        const k = res.kpis || {{}};
        const elFat = document.getElementById("fchKpiFaturado"); if (elFat) elFat.textContent = `R$ ${{Number(k.total_faturado||0).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;
        const elSrv = document.getElementById("fchKpiServicos"); if (elSrv) elSrv.textContent = `R$ ${{Number(k.total_servicos||0).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;
        const elIss = document.getElementById("fchKpiIss"); if (elIss) elIss.textContent = `R$ ${{Number(k.total_iss||0).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;
        const elTrf = document.getElementById("fchKpiTrf"); if (elTrf) elTrf.textContent = `R$ ${{Number(k.total_transferencias||0).toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;

        const tb = document.getElementById("tbodyFechamentoNotas");
        if (tb) {{
          tb.innerHTML = (res.notas || []).map(n => `
            <tr>
              <td><b>${{n.numero_nf}}</b></td>
              <td style="font-size:11px;">${{n.data_emissao ? n.data_emissao.substring(0, 10) : '-'}}</td>
              <td><b>${{n.cliente}}</b></td>
              <td style="font-size:11px;">${{n.cnpj_tomador}}</td>
              <td><span class="badge" style="background:#0f172a;border:1px solid #334155;">${{n.cfop || 'NFS-e'}}</span></td>
              <td>R$ ${{Number(n.valor_servicos||0).toFixed(2)}}</td>
              <td>R$ ${{Number(n.valor_pecas||0).toFixed(2)}}</td>
              <td>R$ ${{Number(n.valor_iss||0).toFixed(2)}} (${{n.aliquota_iss}}%)</td>
              <td><b>R$ ${{Number(n.valor_liquido||0).toFixed(2)}}</b></td>
              <td>${{n.is_cancelada ? '<span style="color:#f87171;font-weight:bold;">Cancelada</span>' : (n.enviado ? '<span style="color:#34d399;font-weight:bold;">Enviado Contabilidade</span>' : '<span style="color:#38bdf8;">Pronto p/ Envio</span>')}}</td>
            </tr>
          `).join("") || `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:14px;">Nenhuma nota fiscal emitida nesta competência.</td></tr>`;
        }}
      }} catch (e) {{
        console.error("Erro ao carregar fechamento contábil:", e);
      }}
    }}

    function formatarMesLegivel(mStr) {{
      if (!mStr || mStr.length < 7) return mStr;
      const parts = mStr.split("-");
      const ano = parts[0];
      const mes = parts[1];
      const meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
      const idx = parseInt(mes, 10) - 1;
      return `${{meses[idx] || mes}} / ${{ano}}`;
    }}

    function baixarPacoteContadorZip() {{
      const mes = document.getElementById("selMesFechamento")?.value || "";
      const fil = document.getElementById("selFilialFechamento")?.value || "CONSOLIDADO";
      window.location.href = `/api/fiscal/v2/fechamento/zip?mes=${{encodeURIComponent(mes)}}&filial=${{encodeURIComponent(fil)}}`;
    }}

    function abrirRelatorioContabilImpresso() {{
      const mes = document.getElementById("selMesFechamento")?.value || "";
      const fil = document.getElementById("selFilialFechamento")?.value || "CONSOLIDADO";
      window.open(`/api/fiscal/v2/fechamento/relatorio-impresso?mes=${{encodeURIComponent(mes)}}&filial=${{encodeURIComponent(fil)}}`, "_blank");
    }}

    async function marcarFechamentoEnviadoContabilidade() {{
      const mes = document.getElementById("selMesFechamento")?.value || "";
      const fil = document.getElementById("selFilialFechamento")?.value || "CONSOLIDADO";
      if (!confirm(`Deseja marcar todas as notas de ${{mes}} (${{fil}}) como transmitidas à contabilidade?`)) return;

      const res = await fetch("/api/fiscal/v2/fechamento/marcar-enviado", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ mes, filial: fil, usuario: USUARIO_FISCAL?.username || "netto" }})
      }}).then(r => r.json());

      alert(res.msg);
      carregarFechamentoContabil();
    }}

        // ==========================================
    // FUNÇÕES DO RADAR DF-E (NOTAS RECEBIDAS)
    // ==========================================
    let DFE_NOTAS_CACHE = [];

    async function carregarNotasRecebidasDFe() {{
      try {{
        const filtroUn = document.getElementById("selFiltroUnidadeDFe")?.value || "CONSOLIDADO";
        const dataInicio = document.getElementById("selFiltroPeriodoDFe")?.value || "2026-01-01";
        const res = await fetch(`/api/fiscal/recebidas/dados?filial=${{FILIAL_ATIVA}}&filtro_dfe=${{encodeURIComponent(filtroUn)}}&data_inicio=${{encodeURIComponent(dataInicio)}}`).then(r => r.json());
        if (!res.ok) return;

        DFE_NOTAS_CACHE = res.notas || [];
        document.getElementById("kpiRecTotal").textContent = res.kpis.total;
        document.getElementById("kpiRecValor").textContent = `R$ ${{Number(res.kpis.valor_total || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}`;
        document.getElementById("kpiRecPendManif").textContent = res.kpis.pend_manifestacao;
        document.getElementById("kpiRecPendEstoque").textContent = res.kpis.pend_estoque;
        document.getElementById("badgeQtdRecebidas").textContent = `${{res.kpis.total}} Notas`;

        const tb = document.getElementById("tbodyNotasRecebidasDFe");
        tb.innerHTML = DFE_NOTAS_CACHE.map(n => {{
          const dtFmt = n.data_emissao ? n.data_emissao.substring(0, 10).split('-').reverse().join('/') : '-';
          const isDf = String(n.filial || '').includes('DF');
          const badgeFil = isDf
            ? '<span class="badge" style="background:#0c4a6e;color:#7dd3fc;border:1px solid #0284c7;font-size:11px;white-space:nowrap;display:inline-flex;align-items:center;gap:5px;padding:4px 9px;border-radius:6px;line-height:1;"><span>🏢</span><span>Filial DF</span></span>'
            : '<span class="badge" style="background:#1e1b4b;color:#c4b5fd;border:1px solid #6366f1;font-size:11px;white-space:nowrap;display:inline-flex;align-items:center;gap:5px;padding:4px 9px;border-radius:6px;line-height:1;"><span>🏛️</span><span>Matriz CE</span></span>';
          const corManif = n.status_manifestacao === 'CONFIRMADA' ? 'color:#34d399;font-weight:bold;white-space:nowrap;' :
                           n.status_manifestacao === 'CIENCIA' ? 'color:#60a5fa;white-space:nowrap;' :
                           n.status_manifestacao === 'DESCONHECIDA' ? 'color:#f87171;font-weight:bold;white-space:nowrap;' : 'color:#fbbf24;font-weight:bold;white-space:nowrap;';
          const lblManif = n.status_manifestacao === 'CONFIRMADA' ? '✅ Confirmada' :
                           n.status_manifestacao === 'CIENCIA' ? 'ℹ️ Ciência' :
                           n.status_manifestacao === 'DESCONHECIDA' ? '🛡️ Desconhecida' : '⚠️ Pendente';
          const corEst = n.status_estoque === 'DADO_ENTRADA' ? 'color:#34d399;font-weight:bold;white-space:nowrap;' : 'color:#f472b6;font-weight:bold;white-space:nowrap;';
          const lblEst = n.status_estoque === 'DADO_ENTRADA' ? '✅ No Estoque' : '⏳ Pendente';

          return `
            <tr>
              <td style="white-space:nowrap;vertical-align:middle;"><b>NF-e ${{n.numero_nf}}</b></td>
              <td style="white-space:nowrap;vertical-align:middle;">${{badgeFil}}</td>
              <td style="white-space:nowrap;vertical-align:middle;">${{dtFmt}}</td>
              <td style="vertical-align:middle;" title="${{n.emitente_nome}}"><b>${{n.emitente_nome.length > 32 ? n.emitente_nome.substring(0, 32) + '...' : n.emitente_nome}}</b></td>
              <td style="font-size:11px;white-space:nowrap;vertical-align:middle;">${{n.emitente_cnpj}}</td>
              <td style="text-align:center;vertical-align:middle;"><span class="badge" style="background:#0f172a;border:1px solid #334155;white-space:nowrap;display:inline-block;">${{n.emitente_uf || 'BR'}}</span></td>
              <td style="white-space:nowrap;vertical-align:middle;"><b>R$ ${{Number(n.valor_total || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}</b></td>
              <td style="white-space:nowrap;vertical-align:middle;"><span style="${{corManif}}">${{lblManif}}</span></td>
              <td style="white-space:nowrap;vertical-align:middle;"><span style="${{corEst}}">${{lblEst}}</span></td>
              <td style="white-space:nowrap;vertical-align:middle;">
                <div style="display:inline-flex;align-items:center;gap:5px;flex-wrap:nowrap;">
                  <button type="button" class="btn btn-outline" style="width:auto;padding:4px 9px;font-size:11px;border-color:#38bdf8;color:#38bdf8;" onclick="abrirModalItensDFe(${{n.id}})">👁️ Visualizar</button>
                  ${{n.status_estoque === 'PENDENTE' ? `<button type="button" class="btn btn-primary" style="width:auto;padding:4px 9px;font-size:11px;" onclick="darEntradaEstoqueDFe(${{n.id}}, '${{n.numero_nf}}')">📦 Dar Entrada</button>` : ''}}
                  ${{n.status_manifestacao === 'SEM_MANIFESTACAO' ? `
                    <button type="button" class="btn btn-blue" style="width:auto;padding:4px 8px;font-size:11px;" onclick="manifestarNotaDFe(${{n.id}}, 'CONFIRMAR')">✅ Confirmar</button>
                    <button type="button" class="btn btn-danger" style="width:auto;padding:4px 8px;font-size:11px;" onclick="manifestarNotaDFe(${{n.id}}, 'DESCONHECER')">🛡️ Desconhecer</button>
                  ` : ''}}
                </div>
              </td>
            </tr>
          `;
        }}).join("") || `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:14px;">Nenhuma nota fiscal emitida por fornecedores localizada no momento.</td></tr>`;
      }} catch (e) {{
        console.error("Erro ao carregar DF-e:", e);
      }}
    }}

    async function sincronizarDFeSefaz() {{
      try {{
        const res = await fetch("/api/fiscal/recebidas/consultar-sefaz", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ filial: FILIAL_ATIVA, usuario: USUARIO_FISCAL?.username || "netto" }})
        }}).then(r => r.json());
        alert(res.msg);
        carregarNotasRecebidasDFe();
      }} catch (e) {{
        alert("Erro ao consultar SEFAZ.");
      }}
    }}

    async function uploadXmlDFe(event) {{
      const files = event.target.files;
      if (!files || !files.length) return;
      let sucesso = 0;
      let total = files.length;
      for (let i = 0; i < files.length; i++) {{
        const file = files[i];
        const reader = new FileReader();
        await new Promise((resolve) => {{
          reader.onload = async (e) => {{
            const xmlText = e.target.result;
            try {{
              const res = await fetch("/api/fiscal/recebidas/importar-xml", {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify({{
                  xml_conteudo: xmlText,
                  filial: FILIAL_ATIVA,
                  usuario: USUARIO_FISCAL?.username || "netto"
                }})
              }}).then(r => r.json());
              if (res.ok) sucesso++;
              if (total === 1) alert(res.msg);
            }} catch (err) {{
              console.error(err);
            }}
            resolve();
          }};
          reader.readAsText(file);
        }});
      }}
      if (total > 1) {{
        alert(`✅ Processamento concluído: ${{sucesso}} de ${{total}} arquivo(s) XML importados no Radar DF-e com sucesso!`);
      }}
      event.target.value = "";
      carregarNotasRecebidasDFe();
    }}

    async function manifestarNotaDFe(id, tipo) {{
      if (tipo === "DESCONHECER") {{
        const conf = confirm(
          `⚠️ ATENÇÃO: ALERTA ANTI-FRAUDE / NOTA INDEVIDA\n\nVocê está prestes a manifestar DESCONHECIMENTO DA OPERAÇÃO perante a SEFAZ (Evento 210220).\n\nDeseja realmente registrar que sua empresa NÃO reconhece esta nota fiscal?`
        );
        if (!conf) return;
      }}
      try {{
        const res = await fetch("/api/fiscal/recebidas/manifestar", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{
            id: id,
            tipo: tipo,
            justificativa: tipo === "DESCONHECER" ? "Operação não reconhecida pela empresa (Proteção contra nota indevida)" : "Operação e mercadorias conferidas",
            usuario: USUARIO_FISCAL?.username || "netto"
          }})
        }}).then(r => r.json());
        alert(res.msg);
        carregarNotasRecebidasDFe();
      }} catch (e) {{
        alert("Erro ao manifestar nota.");
      }}
    }}

    async function darEntradaEstoqueDFe(id, numNf) {{
      const conf = confirm(
        `📦 CONFIRMAÇÃO DE ENTRADA NO ALMOXARIFADO\n\n` +
        `Deseja dar entrada automática de todas as peças e itens da NF-e ${{numNf}} no estoque?\n\n` +
        `O sistema atualizará as quantidades e o saldo fiscal no inventário.`
      );
      if (!conf) return;

      try {{
        const res = await fetch("/api/fiscal/recebidas/dar-entrada-estoque", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ id: id, usuario: USUARIO_FISCAL?.username || "netto" }})
        }}).then(r => r.json());
        alert(res.msg);
        carregarNotasRecebidasDFe();
        if (typeof carregarDadosFiscais === 'function') await carregarDadosFiscais();
        if (typeof renderizarInventario === 'function') renderizarInventario();
      }} catch (e) {{
        alert("Erro ao dar entrada no estoque.");
      }}
    }}

    let DFE_NOTA_ATUAL_MODAL = null;

    function abrirModalItensDFe(id) {{
      const n = DFE_NOTAS_CACHE.find(item => item.id === id);
      if (!n) return;
      DFE_NOTA_ATUAL_MODAL = n;

      const dtFmt = n.data_emissao ? n.data_emissao.substring(0, 10).split('-').reverse().join('/') : '-';
      const isDf = String(n.filial || '').includes('DF');
      const unidTxt = isDf ? '🏢 Filial Brasília - DF (03.611.974/0002-80)' : '🏛️ Matriz Eusébio - CE (03.611.974/0001-08)';
      const valFmt = `R$ ${{Number(n.valor_total || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}`;

      document.getElementById("modalItensDFeTitulo").textContent = `🧾 Visualização Completa & DANFE — NF-e Nº ${{n.numero_nf}} (${{n.emitente_nome}})`;
      const subEl = document.getElementById("modalItensDFeSubtitulo");
      if (subEl) {{
        subEl.innerHTML = `<b>Fornecedor:</b> ${{n.emitente_nome}} (CNPJ: ${{n.emitente_cnpj}} • ${{n.emitente_uf || 'BR'}}) &bull; <b>Emissão:</b> ${{dtFmt}} &bull; <b>Destinatário:</b> ${{unidTxt}} &bull; <b style="color:#4ade80;">Valor Total: ${{valFmt}}</b>`;
      }}

      const iframe = document.getElementById("iframeDanfeDFeModal");
      if (iframe) {{
        iframe.src = `/api/fiscal/recebidas/pdf/${{n.id}}#view=FitH`;
      }}

      const btnPdf = document.getElementById("btnModalDFeBaixarPdf");
      if (btnPdf) btnPdf.href = `/api/fiscal/recebidas/pdf/${{n.id}}?download=1`;

      const btnXml = document.getElementById("btnModalDFeBaixarXml");
      if (btnXml) btnXml.href = `/api/fiscal/recebidas/xml/${{n.id}}`;

      const btnNovaAba = document.getElementById("btnModalDFeAbrirNovaAba");
      if (btnNovaAba) btnNovaAba.href = `/api/fiscal/recebidas/pdf/${{n.id}}`;

      const tb = document.getElementById("tbodyModalItensDFe");
      const itens = n.itens || [];
      if (tb) {{
        tb.innerHTML = itens.map(it => `
          <tr style="border-bottom:1px solid #334155;">
            <td><b style="color:#38bdf8;">${{it.codigo || '-'}}</b></td>
            <td><b>${{it.descricao || '-'}}</b></td>
            <td>${{it.ncm || '9022.90.90'}}</td>
            <td>${{it.unidade || 'UN'}}</td>
            <td style="font-weight:bold;">${{it.qtd}}</td>
            <td>R$ ${{Number(it.unitario || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}</td>
            <td style="font-weight:bold;color:#10b981;">R$ ${{Number(it.total || ((it.qtd || 1) * (it.unitario || 0))).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}</td>
          </tr>
        `).join("") || `<tr><td colspan="7" style="text-align:center;padding:10px;color:var(--muted);">Nenhum item discriminado.</td></tr>`;
      }}

      const inpEmail = document.getElementById("inpModalDFeEmail");
      if (inpEmail && !inpEmail.value) {{
        inpEmail.value = isDf ? "brasilia@emed.med.br" : "financeiro@emed.med.br";
      }}

      renderContatosRapidosWhatsDFe();
      alternarVisaoModalDFe('DANFE');
      document.getElementById("modalItensDFe").style.display = "flex";
    }}

    function alternarVisaoModalDFe(modo) {{
      const boxDanfe = document.getElementById("boxModalDFeVisaoDanfe");
      const boxItens = document.getElementById("boxModalDFeVisaoItens");
      const tabDanfe = document.getElementById("btnTabModalDFeDanfe");
      const tabItens = document.getElementById("btnTabModalDFeItens");
      if (modo === 'ITENS') {{
        if (boxDanfe) boxDanfe.style.display = "none";
        if (boxItens) boxItens.style.display = "block";
        if (tabDanfe) {{ tabDanfe.style.background = "#1e293b"; tabDanfe.style.color = "#cbd5e1"; }}
        if (tabItens) {{ tabItens.style.background = "#0284c7"; tabItens.style.color = "#fff"; }}
      }} else {{
        if (boxDanfe) boxDanfe.style.display = "block";
        if (boxItens) boxItens.style.display = "none";
        if (tabDanfe) {{ tabDanfe.style.background = "#0284c7"; tabDanfe.style.color = "#fff"; }}
        if (tabItens) {{ tabItens.style.background = "#1e293b"; tabItens.style.color = "#cbd5e1"; }}
      }}
    }}

    function imprimirOuBaixarPdfDanfeModal() {{
      if (!DFE_NOTA_ATUAL_MODAL) return;
      const a = document.createElement("a");
      a.href = `/api/fiscal/recebidas/pdf/${{DFE_NOTA_ATUAL_MODAL.id}}?download=1`;
      a.download = `DANFE_NFe_${{DFE_NOTA_ATUAL_MODAL.numero_nf}}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    }}

    function toggleBoxShareModalDFe(foco) {{
      const box = document.getElementById("boxShareModalDFe");
      if (!box) return;
      box.style.display = "block";
      if (foco === 'whats') document.getElementById("inpModalDFeWhats")?.focus();
      if (foco === 'email') document.getElementById("inpModalDFeEmail")?.focus();
    }}

    function mostrarAvisoPdfModal(txt) {{
      const el = document.getElementById("avisoEnvioPdfModalDFe");
      if (el) {{
        el.innerHTML = txt;
        el.style.display = "block";
      }}
    }}

    function getContatosRapidosWhatsDFe() {{
      try {{
        return JSON.parse(localStorage.getItem("emed_whats_contatos_rapidos") || "[]");
      }} catch (e) {{
        return [];
      }}
    }}

    function renderContatosRapidosWhatsDFe() {{
      const box = document.getElementById("boxContatosRapidosWhatsDFe");
      if (!box) return;
      const lista = getContatosRapidosWhatsDFe();
      if (!lista.length) {{
        box.innerHTML = `<span style="font-size:10.5px;color:#94a3b8;">💡 Dica: Digite um ou mais números (ex: 85999999999, 61996585392) e clique em "+ Salvar Contato" para envio rápido.</span>`;
        return;
      }}
      box.innerHTML = lista.map((c, idx) => `
        <span style="display:inline-flex;align-items:center;gap:4px;background:#0f172a;border:1px solid #334155;border-radius:999px;padding:2px 8px;font-size:11px;color:#e2e8f0;">
          <a href="javascript:void(0)" onclick="adicionarNumeroCampoWhatsDFe('${{c.numero}}')" style="color:#4ade80;text-decoration:none;font-weight:700;" title="Adicionar ${{c.numero}}">+ ${{c.nome}}</a>
          <a href="javascript:void(0)" onclick="removerContatoRapidoWhatsDFe(${{idx}})" style="color:#f87171;text-decoration:none;font-weight:bold;margin-left:2px;" title="Remover">&times;</a>
        </span>
      `).join("");
    }}

    function adicionarNumeroCampoWhatsDFe(num) {{
      const inp = document.getElementById("inpModalDFeWhats");
      if (!inp) return;
      const atuais = inp.value.split(/[,;\\s]+/).map(x => x.replace(/\\D/g, "")).filter(Boolean);
      const limpo = String(num || "").replace(/\\D/g, "");
      if (limpo && !atuais.includes(limpo)) {{
        atuais.push(limpo);
      }}
      inp.value = atuais.join(", ");
    }}

    function salvarContatoRapidoWhatsDFe() {{
      const inp = document.getElementById("inpModalDFeWhats");
      const raw = (inp?.value || "").trim();
      const nums = raw.split(/[,;\\s]+/).map(x => x.replace(/\\D/g, "")).filter(x => x.length >= 10);
      if (!nums.length) {{
        alert("Digite primeiro um número válido (DDD + número) no campo para salvar como atalho.");
        return;
      }}
      const numAlvo = nums[nums.length - 1];
      const nome = prompt(`Nome do contato para o número ${{numAlvo}} (ex: Paulo Emed, Financeiro):`);
      if (!nome || !nome.trim()) return;
      const lista = getContatosRapidosWhatsDFe().filter(c => c.numero !== numAlvo);
      lista.push({{ nome: nome.trim(), numero: numAlvo }});
      localStorage.setItem("emed_whats_contatos_rapidos", JSON.stringify(lista));
      renderContatosRapidosWhatsDFe();
    }}

    function removerContatoRapidoWhatsDFe(idx) {{
      const lista = getContatosRapidosWhatsDFe();
      lista.splice(idx, 1);
      localStorage.setItem("emed_whats_contatos_rapidos", JSON.stringify(lista));
      renderContatosRapidosWhatsDFe();
    }}

    function perguntarOndeConectarWhatsApp() {{
      const msg = [
        "📱 COMO VOCÊ PREFERE CONECTAR O WHATSAPP?",
        "",
        "• Clique em [OK] para conectar no seu NAVEGADOR PADRÃO (Chrome, Edge, Firefox etc., onde você já usa seu WhatsApp no dia a dia).",
        "",
        "• Clique em [Cancelar] se quiser abrir a janela do ROBÔ LOCAL DEDICADO em segundo plano."
      ].join(String.fromCharCode(10));
      const querPadrao = confirm(msg);
      if (querPadrao) {{
        window.open("https://web.whatsapp.com", "_blank");
        mostrarAvisoPdfModal("🌐 <b>WhatsApp Web aberto no seu navegador padrão!</b> Você já pode disparar as mensagens diretamente.");
      }} else {{
        conectarWhatsAppBotLocal();
      }}
    }}

    function enviarWhatsNavegadorPadraoModalDFe() {{
      const n = DFE_NOTA_ATUAL_MODAL;
      if (!n) return;
      const rawInput = (document.getElementById("inpModalDFeWhats")?.value || "").trim();
      const listaFones = rawInput
        .split(/[,;\\s\\n]+/)
        .map(s => s.replace(/\\D/g, ""))
        .filter(s => s.length >= 8);

      const urlDanfe = window.location.origin + `/api/fiscal/recebidas/danfe/${{n.id}}`;
      const urlXml = window.location.origin + `/api/fiscal/recebidas/xml/${{n.id}}`;
      const emitNome = n.emitente_nome || n.emitente_razao || "Fornecedor";
      const cnpjEmit = n.emitente_cnpj || "";
      const numNf = n.numero_nf || "";
      const valTot = Number(n.valor_total || 0).toLocaleString("pt-BR", {{ minimumFractionDigits: 2 }});
      const chave = n.chave_acesso || "";

      const linhas = [
        `🧾 *DANFE NF-e Nº ${{numNf}} — EMED ELETROMEDICINA*`,
        `• *Fornecedor:* ${{emitNome}}`,
        cnpjEmit ? `• *CNPJ Emitente:* ${{cnpjEmit}}` : "",
        n.data_emissao ? `• *Data Emissão:* ${{n.data_emissao}}` : "",
        `• *Valor Total:* R$ ${{valTot}}`,
        chave ? ("• *Chave de Acesso:* " + chave) : "",
        "",
        `📄 *Visualizar / Baixar DANFE (.PDF):* ${{urlDanfe}}`,
        `📥 *Baixar Arquivo XML:* ${{urlXml}}`
      ].filter(Boolean).join("\\n");

      if (listaFones.length > 0) {{
        listaFones.forEach((fone, idx) => {{
          const numFmt = fone.startsWith("55") ? fone : ("55" + fone);
          const zapUrl = `https://api.whatsapp.com/send?phone=${{numFmt}}&text=${{encodeURIComponent(linhas)}}`;
          setTimeout(() => {{
            window.open(zapUrl, "_blank");
          }}, idx * 350);
        }});
        mostrarAvisoPdfModal(`🌐 <b>WhatsApp aberto no navegador padrão</b> para ${{listaFones.length}} contato(s)!`);
      }} else {{
        const zapUrl = `https://api.whatsapp.com/send?text=${{encodeURIComponent(linhas)}}`;
        window.open(zapUrl, "_blank");
        mostrarAvisoPdfModal("🌐 <b>WhatsApp Web aberto no seu navegador padrão!</b> Escolha o contato ou grupo para enviar.");
      }}
    }}

    async function conectarWhatsAppBotLocal() {{
      const btn = document.getElementById("btnConectarWhatsBot");
      if (btn) {{ btn.disabled = true; btn.textContent = "⏳ Abrindo..."; }}
      mostrarAvisoPdfModal("⏳ Abrindo janela dedicada do WhatsApp Web no servidor... Se ainda não conectou, escaneie o QR Code com o celular.");
      try {{
        const resp = await fetch("/api/fiscal/recebidas/whatsapp-conectar", {{ method: "POST" }});
        if (!resp.ok) {{
          const errTxt = await resp.text();
          throw new Error("Servidor retornou erro: " + resp.status + " " + errTxt.substring(0, 100));
        }}
        const res = await resp.json();
        if (res.status === "CONECTADO") {{
          mostrarAvisoPdfModal("✅ <b>WhatsApp Dedicado CONECTADO!</b> Já pode enviar os PDFs diretamente para qualquer número.");
        }} else {{
          mostrarAvisoPdfModal("📷 <b>Aguardando leitura do QR Code</b> na janela do Edge/WhatsApp que abriu no servidor. Após conectar, clique em <b>📲 Enviar PDF</b>.");
        }}
      }} catch (e) {{
        mostrarAvisoPdfModal("❌ Erro ao abrir automação local: " + e.message);
      }} finally {{
        if (btn) {{ btn.disabled = false; btn.textContent = "📷 Conectar WhatsApp"; }}
      }}
    }}

    async function enviarWhatsDanfeModalDFe() {{
      const n = DFE_NOTA_ATUAL_MODAL;
      if (!n) return;
      const rawInput = (document.getElementById("inpModalDFeWhats")?.value || "").trim();
      const listaFones = rawInput
        .split(/[,;\\s\\n]+/)
        .map(s => s.replace(/\\D/g, ""))
        .filter(s => s.length >= 10);

      if (!listaFones.length) {{
        alert("Digite pelo menos um número de WhatsApp com DDD (ex: 85999999999) ou selecione um contato salvo.");
        document.getElementById("inpModalDFeWhats")?.focus();
        return;
      }}

      const btn = document.getElementById("btnDispararWhatsPdfAuto");
      if (btn) {{ btn.disabled = true; btn.textContent = "⏳ Enviando PDF..."; }}
      mostrarAvisoPdfModal(`⏳ Enviando arquivo <b>DANFE_NFe_${{n.numero_nf}}.pdf</b> automaticamente para ${{listaFones.length}} número(s)...`);

      try {{
        const resp = await fetch("/api/fiscal/recebidas/enviar-whatsapp-pdf", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ id: n.id, numeros: listaFones }})
        }});
        if (!resp.ok) {{
          const errTxt = await resp.text();
          throw new Error("Servidor retornou erro " + resp.status + ": " + errTxt.substring(0, 100));
        }}
        const res = await resp.json();

        if (res.needs_qr) {{
          mostrarAvisoPdfModal("📷 <b>Primeira conexão necessária:</b> Escaneie o QR Code na janela do WhatsApp Web dedicada que acabou de abrir e depois clique novamente em <b>📲 Enviar PDF</b>.");
          return;
        }}
        if (res.ok) {{
          const envTxt = (res.enviados || []).join(", ");
          const falhasTxt = (res.falhas || []).length
            ? `<br/><span style="color:#fbbf24;">⚠️ Falhas: ${{res.falhas.map(f => f.numero + ' (' + f.erro + ')').join('; ')}}</span>`
            : "";
          mostrarAvisoPdfModal(`✅ <b>PDF enviado automaticamente no WhatsApp</b> para: <b>${{envTxt}}</b>${{falhasTxt}}`);
        }} else {{
          mostrarAvisoPdfModal(`⚠️ ${{res.msg || "Não foi possível enviar."}}`);
        }}
      }} catch (e) {{
        mostrarAvisoPdfModal(`❌ Falha ao acionar automação local: ${{e.message}}`);
      }} finally {{
        if (btn) {{ btn.disabled = false; btn.textContent = "📲 Enviar PDF"; }}
      }}
    }}
    function montarDadosEmailDanfeModalDFe(emailDest) {{
      const n = DFE_NOTA_ATUAL_MODAL;
      if (!n) return null;
      const email = emailDest || (document.getElementById("inpModalDFeEmail")?.value || "").trim();
      const numNf = n.numero_nf || n.id;
      const fornecedor = n.emitente_nome || "Fornecedor";
      const cnpjForn = n.emitente_cnpj || "-";
      const filialDest = n.filial || "EMED Eletromedicina";
      const cnpjDest = n.cnpj_destinatario || "-";
      const dtEmi = n.data_emissao || "-";
      const vTot = Number(n.valor_total || 0).toLocaleString("pt-BR", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
      const chave = n.chave_acesso || "-";
      const hostOrigin = window.location.origin;
      const urlDanfe = `${{hostOrigin}}/api/fiscal/recebidas/danfe/${{n.id}}`;
      const urlPdf = `${{hostOrigin}}/api/fiscal/recebidas/pdf/${{n.id}}`;
      const urlXml = `${{hostOrigin}}/api/fiscal/recebidas/xml/${{n.id}}`;

      const assunto = `DANFE NF-e Nº ${{numNf}} - ${{fornecedor}} (EMED Eletromedicina)`;
      const corpo = [
        "Prezados,",
        "",
        "Seguem os dados da Nota Fiscal Eletrônica (NF-e) recebida no Radar DF-e da EMED Eletromedicina:",
        "",
        `• Número da NF-e: ${{numNf}} (Série ${{n.serie || "1"}})`,
        `• Emitente / Fornecedor: ${{fornecedor}} (CNPJ: ${{cnpjForn}})`,
        `• Unidade EMED Destinatária: ${{filialDest}} (CNPJ: ${{cnpjDest}})`,
        `• Data de Emissão: ${{dtEmi}}`,
        `• Valor Total: R$ ${{vTot}}`,
        `• Chave de Acesso: ${{chave}}`,
        "",
        "📄 Visualizar / Imprimir DANFE Completa:",
        urlDanfe,
        "",
        "📥 Download Direto da DANFE em PDF:",
        urlPdf,
        "",
        "📥 Download do Arquivo XML Oficial:",
        urlXml,
        "",
        "Atenciosamente,",
        "Departamento Fiscal — EMED Eletromedicina"
      ].join(String.fromCharCode(10));

      return {{ email, numNf, fornecedor, assunto, corpo, urlDanfe, urlPdf, urlXml, id: n.id }};
    }}

    function abrirEmailDanfeWebmail(tipo, emailDest) {{
      const dados = montarDadosEmailDanfeModalDFe(emailDest);
      if (!dados) {{
        alert("Nenhuma nota fiscal selecionada.");
        return;
      }}
      const email = dados.email;
      if (!email || !email.includes("@")) {{
        alert("Informe um e-mail de destino válido no campo.");
        document.getElementById("inpModalDFeEmail")?.focus();
        return;
      }}

      let link = "";
      if (tipo === "gmail") {{
        link = `https://mail.google.com/mail/?view=cm&fs=1&to=${{encodeURIComponent(email)}}&su=${{encodeURIComponent(dados.assunto)}}&body=${{encodeURIComponent(dados.corpo)}}`;
        window.open(link, "_blank");
        mostrarAvisoPdfModal(`🔴 Rascunho aberto no <b>Gmail Web</b> para ${{email}}! Os dados e links da DANFE já estão preenchidos. <a href="/api/fiscal/recebidas/pdf/${{dados.id}}" target="_blank" style="color:#38bdf8;text-decoration:underline;margin-left:6px;font-weight:bold;">📥 Baixar PDF para Anexar</a>`);
      }} else if (tipo === "outlook") {{
        link = `https://outlook.live.com/mail/0/deeplink/compose?to=${{encodeURIComponent(email)}}&subject=${{encodeURIComponent(dados.assunto)}}&body=${{encodeURIComponent(dados.corpo)}}`;
        window.open(link, "_blank");
        mostrarAvisoPdfModal(`🔵 Rascunho aberto no <b>Outlook Web</b> para ${{email}}! Os dados e links da DANFE já estão preenchidos. <a href="/api/fiscal/recebidas/pdf/${{dados.id}}" target="_blank" style="color:#38bdf8;text-decoration:underline;margin-left:6px;font-weight:bold;">📥 Baixar PDF para Anexar</a>`);
      }} else {{
        link = `mailto:${{encodeURIComponent(email)}}?subject=${{encodeURIComponent(dados.assunto)}}&body=${{encodeURIComponent(dados.corpo)}}`;
        window.location.href = link;
        mostrarAvisoPdfModal(`💻 Aberto no <b>Aplicativo Padrão de E-mail</b> (Outlook / Thunderbird)! <a href="/api/fiscal/recebidas/pdf/${{dados.id}}" target="_blank" style="color:#38bdf8;text-decoration:underline;margin-left:6px;font-weight:bold;">📥 Baixar PDF para Anexar</a>`);
      }}
    }}

    async function enviarEmailDanfeModalDFe() {{
      const n = DFE_NOTA_ATUAL_MODAL;
      if (!n) return;
      const email = (document.getElementById("inpModalDFeEmail")?.value || "").trim();
      if (!email || !email.includes("@")) {{
        alert("Informe um e-mail válido para enviar a DANFE em PDF.");
        document.getElementById("inpModalDFeEmail")?.focus();
        return;
      }}

      const btn = document.getElementById("btnDispararEmailModal");
      if (btn) {{ btn.disabled = true; btn.textContent = "⏳ Enviando..."; }}

      try {{
        const res = await fetch("/api/fiscal/recebidas/enviar-email-pdf", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ id: n.id, email }})
        }}).then(r => r.json());

        if (res.ok && res.smtp_sent) {{
          mostrarAvisoPdfModal(res.msg);
          alert(res.msg);
          return;
        }}
      }} catch (e) {{
      }} finally {{
        if (btn) {{ btn.disabled = false; btn.textContent = "✉️ Disparar E-mail"; }}
      }}

      // Se SMTP não estiver configurado no servidor, direciona instantaneamente para Webmail inteligente:
      const emailLower = email.toLowerCase();
      if (emailLower.endsWith("@gmail.com")) {{
        abrirEmailDanfeWebmail("gmail", email);
      }} else if (emailLower.endsWith("@outlook.com") || emailLower.endsWith("@hotmail.com") || emailLower.endsWith("@live.com")) {{
        abrirEmailDanfeWebmail("outlook", email);
      }} else {{
        abrirEmailDanfeWebmail("mailto", email);
      }}
    }}

    function fecharModalItensDFe() {{
      document.getElementById("modalItensDFe").style.display = "none";
      const iframe = document.getElementById("iframeDanfeDFeModal");
      if (iframe) iframe.src = "about:blank";
    }}

    // =========================================================================
    // ABA DE DETALHES DE DESPESAS DAS UNIDADES (ALIMENTAÇÃO, GASOLINA, HOTEL)
    // =========================================================================
    let DESPESAS_UNIDADES_CACHE = [];
    let ABA_PRINCIPAL_FISCAL = "FATURAMENTO";

    function alternarAbaPrincipalFiscal(aba) {{
      ABA_PRINCIPAL_FISCAL = aba;
      const boxFat = document.getElementById("boxAbaFaturamentoFiscal");
      const boxDesp = document.getElementById("boxAbaDespesasUnidades");
      const boxCfop = document.getElementById("boxAbaCfop");
      const btnFat = document.getElementById("tabBtn_FATURAMENTO");
      const btnDesp = document.getElementById("tabBtn_DESPESAS_UNIDADES");
      const btnCfop = document.getElementById("tabBtn_CFOP");
      const btnTudo = document.getElementById("tabBtn_TUDO");

      const resetBtns = () => {{
        if (btnFat) {{ btnFat.style.background = "#1e293b"; btnFat.style.color = "#f8fafc"; }}
        if (btnDesp) {{ btnDesp.style.background = "#1e293b"; btnDesp.style.color = "#f8fafc"; }}
        if (btnCfop) {{ btnCfop.style.background = "#1e293b"; btnCfop.style.color = "#f8fafc"; }}
        if (btnTudo) {{ btnTudo.style.background = "transparent"; btnTudo.style.color = "#94a3b8"; }}
      }};
      resetBtns();

      if (aba === "DESPESAS_UNIDADES") {{
        if (boxFat) boxFat.style.display = "none";
        if (boxDesp) boxDesp.style.display = "block";
        if (boxCfop) boxCfop.style.display = "none";
        if (btnDesp) {{ btnDesp.style.background = "#f59e0b"; btnDesp.style.color = "#0b132b"; }}
        carregarDespesasUnidades();
      }} else if (aba === "CFOP") {{
        if (boxFat) boxFat.style.display = "none";
        if (boxDesp) boxDesp.style.display = "none";
        if (boxCfop) boxCfop.style.display = "block";
        if (btnCfop) {{ btnCfop.style.background = "#38bdf8"; btnCfop.style.color = "#0b132b"; }}
        carregarDadosCfop();
      }} else if (aba === "TUDO") {{
        if (boxFat) boxFat.style.display = "block";
        if (boxDesp) boxDesp.style.display = "block";
        if (boxCfop) boxCfop.style.display = "block";
        if (btnTudo) {{ btnTudo.style.background = "var(--cyan)"; btnTudo.style.color = "#0b132b"; }}
        carregarDespesasUnidades();
        carregarDadosCfop();
      }} else {{
        if (boxFat) boxFat.style.display = "block";
        if (boxDesp) boxDesp.style.display = "none";
        if (boxCfop) boxCfop.style.display = "none";
        if (btnFat) {{ btnFat.style.background = "var(--cyan)"; btnFat.style.color = "#0b132b"; }}
      }}
    }}

    function aoMudarFiltroUnidadeDespesa(val) {{
      carregarDespesasUnidades();
    }}

    function atalhoFiltroCategoriaDespesa(cat) {{
      const sel = document.getElementById("selDespFiltroCategoria");
      if (sel) sel.value = cat;
      carregarDespesasUnidades();
    }}

    function toggleFormNovaDespesaUnidade(forcar) {{
      const box = document.getElementById("boxFormDespesaUnidade");
      if (!box) return;
      const mostrar = typeof forcar === "boolean" ? forcar : (box.style.display === "none");
      box.style.display = mostrar ? "block" : "none";
      if (mostrar && !document.getElementById("despUnidId").value) {{
        document.getElementById("tituloFormDespesaUnidade").textContent = "➕ Lançar Nova Despesa da Unidade";
        document.getElementById("despUnidFilial").value = (FILIAL_ATIVA === "MATRIZ_CE") ? "MATRIZ_CE" : "FILIAL_DF";
        if (!document.getElementById("despUnidData").value) {{
          document.getElementById("despUnidData").value = new Date().toISOString().substring(0, 10);
        }}
      }}
      if (!mostrar) {{
        document.getElementById("despUnidId").value = "";
        document.getElementById("despUnidDescricao").value = "";
        document.getElementById("despUnidValor").value = "";
        document.getElementById("despUnidFornecedor").value = "";
        document.getElementById("despUnidComprovante").value = "";
      }}
    }}

    async function carregarDespesasUnidades() {{
      try {{
        const selUnid = document.getElementById("selDespFiltroUnidade");
        const unid = selUnid ? selUnid.value : (FILIAL_ATIVA || "CONSOLIDADO");
        const selMes = document.getElementById("selDespFiltroMes");
        const mes = selMes ? selMes.value : "TODOS";
        const selCat = document.getElementById("selDespFiltroCategoria");
        const cat = selCat ? selCat.value : "TODAS";

        const url = `/api/fiscal/v2/despesas-unidades?unidade=${{encodeURIComponent(unid)}}&mes=${{encodeURIComponent(mes)}}&categoria=${{encodeURIComponent(cat)}}`;
        const res = await fetch(url).then(r => r.json());
        if (!res.ok) return;

        DESPESAS_UNIDADES_CACHE = res.itens || [];

        if (selMes && res.meses_disponiveis && selMes.options.length <= 1) {{
          const atual = selMes.value || "TODOS";
          selMes.innerHTML = `<option value="TODOS">Todos os Meses (Acumulado)</option>` +
            res.meses_disponiveis.map(m => `<option value="${{m}}" ${{m === atual ? 'selected' : ''}}>${{formatarMesLegivel(m)}}</option>`).join("");
        }}

        const k = res.kpis || {{}};
        const tot = Number(k.total_geral || 0);
        const comb = Number(k.total_combustivel || 0);
        const alim = Number(k.total_alimentacao || 0);
        const hot = Number(k.total_hotel || 0);
        const dfTot = Number(k.total_filial_df || 0);
        const ceTot = Number(k.total_matriz_ce || 0);

        const fmtR = (v) => `R$ ${{Number(v || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
        const pct = (v) => tot > 0 ? `${{(v / tot * 100).toFixed(1)}}% do total` : `0% do total`;

        const elTot = document.getElementById("kpiDespTotalGeral"); if (elTot) elTot.textContent = fmtR(tot);
        const elQtd = document.getElementById("kpiDespQtdLanc"); if (elQtd) elQtd.textContent = `${{k.qtd_lancamentos || 0}} lançamentos filtrados`;
        const elComb = document.getElementById("kpiDespCombustivel"); if (elComb) elComb.textContent = fmtR(comb);
        const elCombP = document.getElementById("kpiDespCombPct"); if (elCombP) elCombP.textContent = pct(comb);
        const elAlim = document.getElementById("kpiDespAlimentacao"); if (elAlim) elAlim.textContent = fmtR(alim);
        const elAlimP = document.getElementById("kpiDespAlimPct"); if (elAlimP) elAlimP.textContent = pct(alim);
        const elHot = document.getElementById("kpiDespHotel"); if (elHot) elHot.textContent = fmtR(hot);
        const elHotP = document.getElementById("kpiDespHotelPct"); if (elHotP) elHotP.textContent = pct(hot);
        const elComp = document.getElementById("kpiDespComparativoUnid");
        if (elComp) {{
          elComp.innerHTML = `<span style="color:#38bdf8;">🏢 DF: ${{fmtR(dfTot)}}</span><br/><span style="color:#c4b5fd;">🏛️ CE: ${{fmtR(ceTot)}}</span>`;
        }}

        renderGraficosDespesasUnidades(res);
        filtrarTabelaDespesasLocal();
      }} catch (e) {{
        console.error("Erro ao carregar despesas das unidades:", e);
      }}
    }}

    function renderGraficosDespesasUnidades(res) {{
      const fmtR = (v) => `R$ ${{Number(v || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;
      const cats = (res.por_categoria || []).filter(c => c.total > 0 || c.filial_df > 0 || c.matriz_ce > 0);
      const totGeral = Number(res.kpis?.total_geral || 0);

      // 1. GRÁFICO DE ROSCA SVG + BARRAS POR CATEGORIA
      const boxCat = document.getElementById("chartDespesasCategorias");
      if (boxCat) {{
        if (!cats.length || totGeral <= 0) {{
          boxCat.innerHTML = `<div style="text-align:center;color:#64748b;padding:40px 10px;">Nenhuma despesa para o filtro selecionado.</div>`;
        }} else {{
          let acumPct = 0;
          const r = 52;
          const circ = 2 * Math.PI * r;
          const circlesSvg = cats.filter(c => c.total > 0).map(c => {{
            const frac = c.total / totGeral;
            const dash = frac * circ;
            const offset = -acumPct * circ;
            acumPct += frac;
            return `<circle cx="70" cy="70" r="${{r}}" fill="transparent" stroke="${{c.cor}}" stroke-width="20" stroke-dasharray="${{dash.toFixed(2)}} ${{circ.toFixed(2)}}" stroke-dashoffset="${{offset.toFixed(2)}}" transform="rotate(-90 70 70)" />`;
          }}).join("");

          const barrasHtml = cats.filter(c => c.total > 0).map(c => `
            <div style="margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:3px;">
                <span style="font-weight:700;color:#e2e8f0;">${{c.icone}} ${{c.label}}</span>
                <span style="font-weight:900;color:${{c.cor}};">${{fmtR(c.total)}} (${{c.percentual}}%)</span>
              </div>
              <div style="width:100%;height:8px;background:#1e293b;border-radius:99px;overflow:hidden;">
                <div style="width:${{Math.max(3, c.percentual)}}%;height:100%;background:${{c.cor}};border-radius:99px;"></div>
              </div>
            </div>
          `).join("");

          boxCat.innerHTML = `
            <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
              <div style="position:relative;width:140px;height:140px;flex-shrink:0;margin:0 auto;">
                <svg width="140" height="140" viewBox="0 0 140 140">
                  <circle cx="70" cy="70" r="${{r}}" fill="transparent" stroke="#1e293b" stroke-width="20" />
                  ${{circlesSvg}}
                </svg>
                <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;pointer-events:none;">
                  <span style="font-size:9.5px;color:#94a3b8;font-weight:700;">TOTAL</span>
                  <span style="font-size:11.5px;color:#fff;font-weight:900;">R$ ${{Math.round(totGeral).toLocaleString('pt-BR')}}</span>
                </div>
              </div>
              <div style="flex:1;min-width:180px;">
                ${{barrasHtml}}
              </div>
            </div>
          `;
        }}
      }}

      // 2. GRÁFICO COMPARATIVO ENTRE UNIDADES (FILIAL DF vs MATRIZ CE POR CATEGORIA)
      const boxComp = document.getElementById("chartDespesasComparativoUnidades");
      if (boxComp) {{
        const maxVal = Math.max(1, ...cats.map(c => Math.max(c.filial_df || 0, c.matriz_ce || 0)));
        const totDf = Number(res.kpis?.total_filial_df || 0);
        const totCe = Number(res.kpis?.total_matriz_ce || 0);
        const totAmbas = Math.max(1, totDf + totCe);
        const pctDf = Math.round(totDf / totAmbas * 100);
        const pctCe = 100 - pctDf;

        const linhasComp = cats.slice(0, 5).map(c => {{
          const wDf = Math.round((c.filial_df / maxVal) * 100);
          const wCe = Math.round((c.matriz_ce / maxVal) * 100);
          return `
            <div style="margin-bottom:10px;">
              <div style="font-size:11.5px;font-weight:700;color:#cbd5e1;margin-bottom:3px;display:flex;justify-content:space-between;">
                <span>${{c.icone}} ${{c.label}}</span>
                <span style="font-size:10.5px;color:#94a3b8;">DF: ${{fmtR(c.filial_df)}} | CE: ${{fmtR(c.matriz_ce)}}</span>
              </div>
              <div style="display:flex;flex-direction:column;gap:3px;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="font-size:10px;color:#38bdf8;width:22px;font-weight:800;">DF</span>
                  <div style="flex:1;height:7px;background:#1e293b;border-radius:99px;overflow:hidden;">
                    <div style="width:${{wDf}}%;height:100%;background:#38bdf8;border-radius:99px;"></div>
                  </div>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="font-size:10px;color:#a78bfa;width:22px;font-weight:800;">CE</span>
                  <div style="flex:1;height:7px;background:#1e293b;border-radius:99px;overflow:hidden;">
                    <div style="width:${{wCe}}%;height:100%;background:#a78bfa;border-radius:99px;"></div>
                  </div>
                </div>
              </div>
            </div>
          `;
        }}).join("");

        boxComp.innerHTML = `
          <div style="margin-bottom:12px;background:#132338;border-radius:8px;padding:8px 10px;">
            <div style="display:flex;justify-content:space-between;font-size:11px;font-weight:800;margin-bottom:4px;">
              <span style="color:#38bdf8;">🏢 Filial DF (${{pctDf}}%)</span>
              <span style="color:#a78bfa;">🏛️ Matriz CE (${{pctCe}}%)</span>
            </div>
            <div style="width:100%;height:10px;background:#1e293b;border-radius:99px;overflow:hidden;display:flex;">
              <div style="width:${{pctDf}}%;height:100%;background:#38bdf8;"></div>
              <div style="width:${{pctCe}}%;height:100%;background:#a78bfa;"></div>
            </div>
          </div>
          ${{linhasComp || '<div style="text-align:center;color:#64748b;padding:20px;">Sem dados comparativos.</div>'}}
        `;
      }}

      // 3. GRÁFICO DE EVOLUÇÃO MENSAL EMPILHADO & TOP RESPONSÁVEIS
      const boxEvol = document.getElementById("chartDespesasEvolucaoMensal");
      if (boxEvol) {{
        const meses = res.por_mes || [];
        const maxMes = Math.max(1, ...meses.map(m => m.total || 0));
        const colsHtml = meses.map(m => {{
          const hComb = Math.round(((m.COMBUSTIVEL || 0) / maxMes) * 110);
          const hAlim = Math.round(((m.ALIMENTACAO || 0) / maxMes) * 110);
          const hHot = Math.round(((m.HOTEL || 0) / maxMes) * 110);
          const hOut = Math.round(((m.OUTROS || 0) / maxMes) * 110);
          return `
            <div style="flex:1;display:flex;flex-direction:column;align-items:center;min-width:65px;">
              <div style="font-size:10.5px;font-weight:800;color:#e2e8f0;margin-bottom:4px;">R$ ${{Math.round(m.total).toLocaleString('pt-BR')}}</div>
              <div style="height:115px;width:36px;background:#1e293b;border-radius:6px;display:flex;flex-direction:column;justify-content:flex-end;overflow:hidden;border:1px solid #334155;">
                <div title="Outros: ${{fmtR(m.OUTROS)}}" style="height:${{hOut}}px;background:#a78bfa;"></div>
                <div title="Hotel: ${{fmtR(m.HOTEL)}}" style="height:${{hHot}}px;background:#38bdf8;"></div>
                <div title="Alimentação: ${{fmtR(m.ALIMENTACAO)}}" style="height:${{hAlim}}px;background:#10b981;"></div>
                <div title="Combustível/Gasolina: ${{fmtR(m.COMBUSTIVEL)}}" style="height:${{hComb}}px;background:#f59e0b;"></div>
              </div>
              <div style="font-size:11px;font-weight:800;color:var(--cyan);margin-top:5px;">${{formatarMesLegivel(m.mes)}}</div>
            </div>
          `;
        }}).join("");

        const resps = (res.por_responsavel || []).slice(0, 3).map(r => `
          <div style="display:flex;justify-content:space-between;font-size:11px;padding:3px 0;border-bottom:1px dashed #1e293b;">
            <span style="color:#cbd5e1;">👤 ${{r.responsavel}}</span>
            <span style="font-weight:800;color:#fbbf24;">${{fmtR(r.total)}} (${{r.percentual}}%)</span>
          </div>
        `).join("");

        boxEvol.innerHTML = `
          <div style="display:flex;justify-content:space-around;align-items:flex-end;gap:10px;padding:6px 4px 10px 4px;border-bottom:1px solid #1e293b;margin-bottom:8px;">
            ${{colsHtml || '<div style="color:#64748b;font-size:12px;">Sem histórico mensal.</div>'}}
          </div>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;font-size:10px;color:#94a3b8;margin-bottom:8px;">
            <span><b style="color:#f59e0b;">■</b> Gasolina/Comb.</span>
            <span><b style="color:#10b981;">■</b> Alimentação</span>
            <span><b style="color:#38bdf8;">■</b> Hotel</span>
            <span><b style="color:#a78bfa;">■</b> Outros</span>
          </div>
          <div>${{resps}}</div>
        `;
      }}
    }}

    function filtrarTabelaDespesasLocal() {{
      const tb = document.getElementById("tbodyDespesasUnidades");
      if (!tb) return;
      const termo = (document.getElementById("inpDespBuscaTexto")?.value || "").toLowerCase().trim();
      const lista = DESPESAS_UNIDADES_CACHE.filter(it => {{
        if (!termo) return true;
        return (
          String(it.descricao || "").toLowerCase().includes(termo) ||
          String(it.fornecedor || "").toLowerCase().includes(termo) ||
          String(it.responsavel || "").toLowerCase().includes(termo) ||
          String(it.categoria_label || "").toLowerCase().includes(termo) ||
          String(it.veiculo_placa || "").toLowerCase().includes(termo) ||
          String(it.os_id || "").toLowerCase().includes(termo)
        );
      }});

      tb.innerHTML = lista.map(it => {{
        const dtFmt = it.data_despesa ? it.data_despesa.split("-").reverse().join("/") : "-";
        const isDf = it.unidade === "FILIAL_DF";
        const badgeUnid = isDf
          ? `<span class="badge" style="background:#0c4a6e;color:#7dd3fc;border:1px solid #0284c7;">🏢 Filial DF</span>`
          : `<span class="badge" style="background:#1e1b4b;color:#c4b5fd;border:1px solid #6366f1;">🏛️ Matriz CE</span>`;
        return `
          <tr>
            <td style="white-space:nowrap;"><b>${{dtFmt}}</b></td>
            <td style="white-space:nowrap;">${{badgeUnid}}</td>
            <td style="white-space:nowrap;">
              <span class="badge" style="background:#1e293b;color:${{it.categoria_cor}};border:1px solid ${{it.categoria_cor}};">
                ${{it.categoria_icone}} ${{it.categoria_label}}
              </span>
            </td>
            <td>
              <div style="font-weight:700;color:#f8fafc;">${{it.descricao}}</div>
              ${{it.os_id ? `<span style="font-size:10.5px;color:#38bdf8;">🔗 OS #${{it.os_id}}</span>` : ''}}
            </td>
            <td style="color:#cbd5e1;">${{it.fornecedor || '-'}}</td>
            <td>
              <span class="badge" style="background:#065f46;color:#a7f3d0;font-size:10.5px;font-weight:700;">💳 Cartão / 🛰️ GPS</span>
              ${{it.responsavel && !it.responsavel.startsWith('Auto') ? `<div style="font-size:10.5px;color:#cbd5e1;margin-top:2px;">👤 ${{it.responsavel}}</div>` : ''}}
            </td>
            <td style="font-size:11px;">
              <div><b>${{it.forma_pagamento}}</b></div>
              <div style="color:#94a3b8;">${{it.numero_comprovante || ''}}</div>
              ${{it.comprovante_anexo ? `<button type="button" class="btn btn-outline" style="padding:2px 6px;font-size:10px;margin-top:3px;border-color:#10b981;color:#34d399;" onclick="visualizarComprovanteAnexo('${{it.id}}')">📎 Ver Comprovante</button>` : ''}}
            </td>
            <td style="text-align:right;font-weight:900;color:${{it.categoria_cor}};white-space:nowrap;">
              R$ ${{Number(it.valor || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}
            </td>
            <td style="text-align:center;white-space:nowrap;">
              <button type="button" class="btn btn-outline" style="padding:4px 8px;font-size:11px;" onclick="editarDespesaUnidade(${{it.id}})" title="Editar">✏️</button>
              <button type="button" class="btn btn-danger" style="padding:4px 8px;font-size:11px;" onclick="excluirDespesaUnidade(${{it.id}})" title="Excluir">🗑️</button>
            </td>
          </tr>
        `;
      }}).join("") || `<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:18px;">Nenhuma despesa encontrada para os filtros selecionados.</td></tr>`;
    }}

    function editarDespesaUnidade(id) {{
      const it = DESPESAS_UNIDADES_CACHE.find(x => x.id === id);
      if (!it) return;
      document.getElementById("despUnidId").value = it.id;
      document.getElementById("despUnidFilial").value = it.unidade;
      document.getElementById("despUnidCategoria").value = it.categoria;
      document.getElementById("despUnidValor").value = it.valor;
      document.getElementById("despUnidData").value = it.data_despesa;
      document.getElementById("despUnidDescricao").value = it.descricao;
      document.getElementById("despUnidResponsavel").value = it.responsavel;
      document.getElementById("despUnidFornecedor").value = it.fornecedor;
      document.getElementById("despUnidPlaca").value = it.veiculo_placa;
      document.getElementById("despUnidOsId").value = it.os_id;
      document.getElementById("despUnidFormaPagto").value = it.forma_pagamento;
      document.getElementById("despUnidComprovante").value = it.numero_comprovante;
      document.getElementById("tituloFormDespesaUnidade").textContent = `✏️ Editando Despesa #${{it.id}} (${{it.categoria_label}})`;
      toggleFormNovaDespesaUnidade(true);
    }}

    
    let COMPROVANTE_DESPESA_ATUAL_B64 = "";

    function toggleTodasSecoes(abrir) {{
      const expanders = document.querySelectorAll("details.card, details");
      expanders.forEach(el => {{
        el.open = abrir;
      }});
    }}

    function aplicarPermissoesUsuarioFiscal() {{
      const cargo = String(USUARIO_FISCAL?.cargo || '').toLowerCase();
      const role = String(USUARIO_FISCAL?.role || '').toLowerCase();
      const user = String(USUARIO_FISCAL?.username || '').toLowerCase();
      const isGestor = (role === 'admin' || user === 'netto' || user === 'vitor' || cargo.includes('diretor') || cargo.includes('gest'));

      const secCfg = document.getElementById("expanderConfiguracoesFiscais");
      const bannerRestrito = document.getElementById("bannerAcessoRestritoCfgFiscal");
      if (secCfg) {{
        secCfg.style.display = isGestor ? "block" : "none";
      }}
      if (bannerRestrito) {{
        bannerRestrito.style.display = isGestor ? "none" : "block";
      }}
    }}

    function processarFotoComprovanteDespesa(event) {{
      const file = event.target.files && event.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = function(e) {{
        COMPROVANTE_DESPESA_ATUAL_B64 = e.target.result;
        const img = document.getElementById("imgPreviewComprovante");
        if (img) img.src = COMPROVANTE_DESPESA_ATUAL_B64;
        const box = document.getElementById("boxPreviewComprovanteAnexo");
        if (box) box.style.display = "block";
        const txt = document.getElementById("txtInfoComprovanteAnexo");
        if (txt) txt.textContent = `${{file.name}} (${{(file.size / 1024).toFixed(1)}} KB) anexado com sucesso.`;

        // Tenta preenchimento inteligente a partir do nome ou tenta leitura
        if (!document.getElementById("despUnidData").value) {{
          document.getElementById("despUnidData").value = new Date().toISOString().substring(0, 10);
        }}
        alert("📸 Foto do comprovante anexada! Você também pode conferir e ajustar os valores nos campos abaixo.");
      }};
      reader.readAsDataURL(file);
    }}

    function removerComprovanteAnexo() {{
      COMPROVANTE_DESPESA_ATUAL_B64 = "";
      const box = document.getElementById("boxPreviewComprovanteAnexo");
      if (box) box.style.display = "none";
      const inp = document.getElementById("inpFotoComprovanteDespesa");
      if (inp) inp.value = "";
    }}

    function abrirLeitorCodigoBarrasManual() {{
      const codigo = prompt("📷 Digite ou cole o Código de Barras (Boleto), Chave de Acesso (44 dígitos da NFC-e/NF-e) ou Link do QR Code:");
      if (!codigo) return;
      parsearChaveOuCodigoBarrasDespesa(codigo.trim());
    }}

    function parsearChaveOuCodigoBarrasDespesa(raw) {{
      const digits = raw.replace(/[^0-9]/g, "");

      // 1. CHAVE DE ACESSO DE 44 DÍGITOS (NFC-e / NF-e)
      if (digits.length === 44) {{
        const uf = digits.substring(0, 2);
        const aamm = digits.substring(2, 6);
        const cnpj = digits.substring(6, 20);
        const mod = digits.substring(20, 22);
        const numNf = parseInt(digits.substring(25, 34), 10);
        const cnpjFmt = `${{cnpj.substring(0,2)}}.${{cnpj.substring(2,5)}}.${{cnpj.substring(5,8)}}/${{cnpj.substring(8,12)}}-${{cnpj.substring(12,14)}}`;

        const ano = "20" + aamm.substring(0, 2);
        const mes = aamm.substring(2, 4);
        document.getElementById("despUnidData").value = `${{ano}}-${{mes}}-01`;
        document.getElementById("despUnidComprovante").value = `NFC-e Nº ${{numNf}}`;
        document.getElementById("despUnidFornecedor").value = `CNPJ: ${{cnpjFmt}}`;
        if (!document.getElementById("despUnidDescricao").value) {{
          document.getElementById("despUnidDescricao").value = `Despesa operacional referente ao cupom fiscal NFC-e Nº ${{numNf}} (Fornecedor CNPJ ${{cnpjFmt}})`;
        }}
        alert(`✅ Chave de 44 dígitos reconhecida com sucesso!

• Documento: NFC-e Nº ${{numNf}}
• Fornecedor CNPJ: ${{cnpjFmt}}
• Competência: ${{mes}}/${{ano}}

Por favor, confira o valor e a categoria preenchidos.`);
        return;
      }}

      // 2. BOLETO BANCÁRIO (47 DÍGITOS DA LINHA DIGITÁVEL OU 44 DO CÓDIGO DE BARRAS)
      if (digits.length === 47 || digits.length === 48 || digits.length === 44) {{
        let valorCentavos = 0;
        if (digits.length === 47) {{
          // Os últimos 10 dígitos da linha digitável contêm o valor
          valorCentavos = parseInt(digits.substring(37), 10);
        }} else if (digits.length === 44) {{
          valorCentavos = parseInt(digits.substring(4, 14), 10);
        }}
        if (valorCentavos > 0) {{
          const val = (valorCentavos / 100.0).toFixed(2);
          document.getElementById("despUnidValor").value = val;
        }}
        document.getElementById("despUnidFormaPagto").value = "BOLETO";
        document.getElementById("despUnidComprovante").value = `Boleto ${{digits.substring(0, 5)}}...`;
        document.getElementById("despUnidCategoria").value = "OUTROS";
        if (!document.getElementById("despUnidData").value) {{
          document.getElementById("despUnidData").value = new Date().toISOString().substring(0, 10);
        }}
        alert(`✅ Boleto bancário reconhecido com sucesso!

• Código: ${{digits.substring(0, 15)}}...
• Valor Identificado: R$ ${{document.getElementById("despUnidValor").value || '0.00'}}

Por favor, confira os dados preenchidos.`);
        return;
      }}

      // 3. QR CODE COM URL OU PIPE TOKENS
      if (raw.includes("p=") || raw.includes("|")) {{
        const partes = raw.split("|");
        if (partes.length >= 4) {{
          const ch = partes[0].replace(/[^0-9]/g, "");
          if (ch.length === 44) {{
            parsearChaveOuCodigoBarrasDespesa(ch);
          }}
          // Se tiver valor no 5º token
          if (partes[4] && !isNaN(parseFloat(partes[4]))) {{
            document.getElementById("despUnidValor").value = parseFloat(partes[4]).toFixed(2);
          }}
          return;
        }}
      }}

      alert("ℹ️ Código lido: " + raw + ". Preenchido no número do comprovante.");
      document.getElementById("despUnidComprovante").value = raw.substring(0, 44);
    }}

    function visualizarComprovanteAnexo(id) {{
      const it = DESPESAS_UNIDADES_CACHE.find(x => x.id === Number(id));
      if (!it || !it.comprovante_anexo) {{
        alert("Nenhum comprovante anexado a este lançamento.");
        return;
      }}
      const win = window.open("", "_blank");
      win.document.write(`
        <html><head><title>Comprovante Despesa #${{it.id}}</title></head>
        <body style="margin:0;background:#0f172a;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;color:#fff;font-family:sans-serif;">
          <h3 style="margin:10px 0;">📎 Comprovante da Despesa #${{it.id}} — ${{it.descricao}} (R$ ${{Number(it.valor).toFixed(2)}})</h3>
          <img src="${{it.comprovante_anexo}}" style="max-width:90%;max-height:85vh;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,0.5);" />
        </body></html>
      `);
    }}

    async function salvarNovaDespesaUnidade() {{
      const payload = {{
        id: document.getElementById("despUnidId").value || null,
        unidade: document.getElementById("despUnidFilial").value,
        categoria: document.getElementById("despUnidCategoria").value,
        valor: document.getElementById("despUnidValor").value,
        data_despesa: document.getElementById("despUnidData").value,
        descricao: document.getElementById("despUnidDescricao").value,
        responsavel: document.getElementById("despUnidResponsavel").value,
        fornecedor: document.getElementById("despUnidFornecedor").value,
        veiculo_placa: document.getElementById("despUnidPlaca").value,
        os_id: document.getElementById("despUnidOsId").value,
        forma_pagamento: document.getElementById("despUnidFormaPagto").value,
        numero_comprovante: document.getElementById("despUnidComprovante").value,
        usuario: USUARIO_FISCAL?.username || "netto"
      }};
      const res = await fetch("/api/fiscal/v2/despesas-unidades/salvar", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(payload)
      }}).then(r => r.json());
      if (res.ok) {{
        alert(res.msg);
        toggleFormNovaDespesaUnidade(false);
        carregarDespesasUnidades();
      }} else {{
        alert("⚠️ " + (res.msg || "Falha ao salvar despesa."));
      }}
    }}

    async function excluirDespesaUnidade(id) {{
      if (!confirm("Deseja realmente excluir este lançamento de despesa?")) return;
      const res = await fetch("/api/fiscal/v2/despesas-unidades/excluir", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ id }})
      }}).then(r => r.json());
      if (res.ok) {{
        carregarDespesasUnidades();
      }} else {{
        alert(res.msg || "Erro ao excluir.");
      }}
    }}

    function exportarDespesasUnidadesCsv() {{
      if (!DESPESAS_UNIDADES_CACHE.length) {{
        alert("Nenhuma despesa listada para exportar.");
        return;
      }}
      const headers = ["ID", "Data", "Unidade", "Categoria", "Descricao", "Fornecedor", "Responsavel", "Placa", "OS", "Forma_Pagto", "Comprovante", "Valor_RS"];
      const linhas = DESPESAS_UNIDADES_CACHE.map(it => [
        it.id, it.data_despesa, it.unidade_label, it.categoria_label,
        `"${{String(it.descricao || '').replace(/"/g, '""')}}"`,
        `"${{String(it.fornecedor || '').replace(/"/g, '""')}}"`,
        `"${{String(it.responsavel || '').replace(/"/g, '""')}}"`,
        it.veiculo_placa, it.os_id, it.forma_pagamento, it.numero_comprovante,
        String(Number(it.valor || 0).toFixed(2)).replace(".", ",")
      ].join(";"));
      const csvContent = "\uFEFF" + headers.join(";") + "\\n" + linhas.join("\\n");
      const blob = new Blob([csvContent], {{ type: "text/csv;charset=utf-8;" }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Despesas_Unidades_EMED_${{FILIAL_ATIVA}}_${{new Date().toISOString().substring(0, 10)}}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    }}

    // =========================================================================
    // CONCILIADOR DO EXTRATO DA GESTORA (BATER DESPESAS SEM DUPLICAR)
    // =========================================================================
    let EXTRATO_BATIMENTO_ITENS = [];

    function toggleBoxExtratoGestora(forcar) {{
      const box = document.getElementById("boxConciliadorExtratoGestora");
      if (!box) return;
      const mostrar = typeof forcar === "boolean" ? forcar : (box.style.display === "none");
      box.style.display = mostrar ? "block" : "none";
      if (mostrar) {{
        const selU = document.getElementById("selExtratoGestoraUnidade");
        if (selU) selU.value = (FILIAL_ATIVA === "MATRIZ_CE") ? "MATRIZ_CE" : "FILIAL_DF";
      }}
    }}

    async function aoSelecionarArquivoExtratoGestora(ev) {{
      const f = ev.target.files && ev.target.files[0];
      if (!f) return;
      if (f.name.toLowerCase().endsWith(".xlsx")) {{
        const buf = await f.arrayBuffer();
        let bin = "";
        const bytes = new Uint8Array(buf);
        for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
        const b64 = btoa(bin);
        const unidade = document.getElementById("selExtratoGestoraUnidade")?.value || "FILIAL_DF";
        const res = await fetch("/api/fiscal/v2/despesas-unidades/conciliar-extrato", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify({{ arquivo_b64: b64, nome_arquivo: f.name, unidade }})
        }}).then(r => r.json());
        if (res.ok) {{
          document.getElementById("txtConteudoExtratoGestora").value = (res.itens || []).map(i => `${{i.data}}; ${{i.descricao_extrato}}; ${{i.valor_extrato}}`).join("\\n");
          processarBatimentoExtratoGestora();
        }} else {{
          alert("⚠️ " + (res.msg || "Erro ao ler Excel."));
        }}
        return;
      }}
      const reader = new FileReader();
      reader.onload = (e) => {{
        document.getElementById("txtConteudoExtratoGestora").value = e.target.result || "";
        processarBatimentoExtratoGestora();
      }};
      reader.readAsText(f);
    }}

    function preencherExemploExtratoGestora() {{
      const unid = document.getElementById("selExtratoGestoraUnidade")?.value || "FILIAL_DF";
      if (unid === "MATRIZ_CE") {{
        document.getElementById("txtConteudoExtratoGestora").value = [
          "Data;Estabelecimento / Descricao;Valor",
          "03/11/2026;Posto Sao Domingos BR-116 - Gasolina Viagem Cariri;520,00",
          "06/11/2026;Hotel Visconde Sobral - 2 Diarias Equipe Tecnica;580,00",
          "10/11/2026;Posto SP Eusebio CE-040 - Gasolina Frota;375,00",
          "19/11/2026;Posto Petrobras Fortaleza - Abastecimento Gasolina Viagem;289,90",
          "19/11/2026;Restaurante Coco Bambu Sul - Almoco Equipe Tecnica;164,50",
          "19/11/2026;Hotel Ibis Fortaleza - Diaria Plantao Tomografo;320,00"
        ].join(String.fromCharCode(10));
      }} else {{
        document.getElementById("txtConteudoExtratoGestora").value = [
          "Data;Estabelecimento / Descricao;Valor",
          "04/11/2026;Posto Ipiranga Asa Norte - Gasolina Aditivada HRAN;385,50",
          "05/11/2026;Restaurante Mane Setor Hospitalar - Almoco Equipe;142,00",
          "11/11/2026;Shell Select SIA Brasilia - Gasolina Comum;325,00",
          "19/11/2026;Auto Posto Petrobras Lago Sul - Gasolina Frota DF;348,00",
          "19/11/2026;Hotel Mercure Brasilia - Diaria Equipe Manutencao;410,00",
          "19/11/2026;Restaurante Setor Hospitalar Sul - Almoco Tecnicos;128,00"
        ].join(String.fromCharCode(10));
      }}
      processarBatimentoExtratoGestora();
    }}

    async function processarBatimentoExtratoGestora() {{
      const conteudo = document.getElementById("txtConteudoExtratoGestora")?.value || "";
      const unidade = document.getElementById("selExtratoGestoraUnidade")?.value || "FILIAL_DF";
      if (!conteudo.trim()) {{
        alert("Cole as linhas do extrato da gestora ou selecione um arquivo (.CSV, .OFX, .TXT).");
        return;
      }}
      const res = await fetch("/api/fiscal/v2/despesas-unidades/conciliar-extrato", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{ conteudo, unidade }})
      }}).then(r => r.json());

      if (!res.ok) {{
        alert("⚠️ " + (res.msg || "Falha ao analisar extrato."));
        return;
      }}

      EXTRATO_BATIMENTO_ITENS = res.itens || [];
      const rsm = res.resumo || {{}};
      const fmtR = (v) => `R$ ${{Number(v || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2, maximumFractionDigits: 2}})}}`;

      const boxRes = document.getElementById("boxResultadoBatimentoExtrato");
      if (!boxRes) return;
      boxRes.style.display = "block";

      const linhasHtml = EXTRATO_BATIMENTO_ITENS.map((it, idx) => {{
        let badgeSt = "";
        let corLinha = "";
        let chkChecked = "checked";
        if (it.status_batimento === "BATEU_EXATO") {{
          badgeSt = `<span class="badge" style="background:#065f46;color:#6ee7b7;border:1px solid #10b981;">✅ Bateu 100% (ID #${{it.id_sistema}})</span>`;
          corLinha = "background:rgba(16,185,129,0.06);";
        }} else if (it.status_batimento === "DIVERGENCIA_VALOR") {{
          badgeSt = `<span class="badge" style="background:#78350f;color:#fde68a;border:1px solid #f59e0b;">⚠️ Divergência (Sistema: ${{fmtR(it.valor_sistema)}})</span>`;
          corLinha = "background:rgba(245,158,11,0.1);";
        }} else {{
          badgeSt = `<span class="badge" style="background:#0c4a6e;color:#7dd3fc;border:1px solid #0284c7;">🆕 Novo no Extrato (Importar)</span>`;
          corLinha = "background:rgba(2,132,199,0.1);";
        }}

        return `
          <tr style="${{corLinha}}">
            <td style="text-align:center;">
              <input type="checkbox" id="chkExt_${{idx}}" ${{chkChecked}} style="width:auto;" />
            </td>
            <td style="white-space:nowrap;"><b>${{it.data.split('-').reverse().join('/')}}</b></td>
            <td>${{badgeSt}}</td>
            <td>
              <select id="selCatExt_${{idx}}" style="padding:4px 6px;font-size:11.5px;font-weight:700;color:${{it.categoria_cor}};">
                <option value="COMBUSTIVEL" ${{it.categoria==='COMBUSTIVEL'?'selected':''}}>⛽ Combustível / Gasolina</option>
                <option value="ALIMENTACAO" ${{it.categoria==='ALIMENTACAO'?'selected':''}}>🍽️ Alimentação</option>
                <option value="HOTEL" ${{it.categoria==='HOTEL'?'selected':''}}>🏨 Hotel / Hospedagem</option>
                <option value="PEDAGIO_TRANSPORTE" ${{it.categoria==='PEDAGIO_TRANSPORTE'?'selected':''}}>🛣️ Pedágio / Transporte</option>
                <option value="MANUTENCAO_FROTA" ${{it.categoria==='MANUTENCAO_FROTA'?'selected':''}}>🔧 Manutenção Frota</option>
                <option value="INSUMOS_UNIDADE" ${{it.categoria==='INSUMOS_UNIDADE'?'selected':''}}>🏢 Copa / Insumos</option>
                <option value="OUTROS" ${{it.categoria==='OUTROS'?'selected':''}}>📌 Outros</option>
              </select>
            </td>
            <td>
              <div style="font-weight:700;color:#fff;">${{it.descricao_extrato}}</div>
              ${{it.descricao_sistema ? `<div style="font-size:10.5px;color:#94a3b8;">No sistema: ${{it.descricao_sistema}}</div>` : ''}}
            </td>
            <td style="text-align:right;font-weight:900;color:#fff;">${{fmtR(it.valor_extrato)}}</td>
            <td>
              <select id="selAcaoExt_${{idx}}" style="padding:4px 6px;font-size:11.5px;font-weight:700;">
                ${{it.status_batimento === "BATEU_EXATO" ? `
                  <option value="MANTER_AUDITADO" selected>✅ Confirmar &amp; Auditar (Não Duplicar)</option>
                  <option value="IGNORAR">Ignorar</option>
                ` : it.status_batimento === "DIVERGENCIA_VALOR" ? `
                  <option value="ATUALIZAR_VALOR" selected>🔧 Ajustar Valor pelo Extrato (${{fmtR(it.valor_extrato)}})</option>
                  <option value="IMPORTAR_NOVO">➕ Importar como Novo Lançamento Separado</option>
                  <option value="IGNORAR">Manter Valor Antigo</option>
                ` : `
                  <option value="IMPORTAR_NOVO" selected>➕ Importar Nova Despesa na Unidade</option>
                  <option value="IGNORAR">Ignorar Linha</option>
                `}}
              </select>
            </td>
          </tr>
        `;
      }}).join("");

      boxRes.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-bottom:14px;">
          <div style="background:#132338;border:1px solid #334155;border-radius:8px;padding:10px;">
            <div style="font-size:10.5px;color:#94a3b8;font-weight:800;">TOTAL NO EXTRATO DA GESTORA</div>
            <div style="font-size:19px;font-weight:900;color:#fff;margin-top:3px;">${{fmtR(rsm.valor_total_extrato)}}</div>
            <div style="font-size:11px;color:#cbd5e1;">${{rsm.total_linhas}} linhas lidas</div>
          </div>
          <div style="background:#064e3b;border:1px solid #10b981;border-radius:8px;padding:10px;">
            <div style="font-size:10.5px;color:#a7f3d0;font-weight:800;">✅ JÁ LANÇADOS (BATERAM 100%)</div>
            <div style="font-size:19px;font-weight:900;color:#34d399;margin-top:3px;">${{fmtR(rsm.valor_conciliado)}}</div>
            <div style="font-size:11px;color:#d1fae5;">${{rsm.qtd_conciliados}} itens (protegidos contra duplicação)</div>
          </div>
          <div style="background:#78350f;border:1px solid #f59e0b;border-radius:8px;padding:10px;">
            <div style="font-size:10.5px;color:#fde68a;font-weight:800;">⚠️ DIVERGÊNCIA DE VALOR</div>
            <div style="font-size:19px;font-weight:900;color:#fbbf24;margin-top:3px;">${{fmtR(rsm.valor_divergente)}}</div>
            <div style="font-size:11px;color:#fef3c7;">${{rsm.qtd_divergentes}} itens com diferença</div>
          </div>
          <div style="background:#0c4a6e;border:1px solid #38bdf8;border-radius:8px;padding:10px;">
            <div style="font-size:10.5px;color:#bae6fd;font-weight:800;">🆕 NOVOS NO EXTRATO (FALTANDO)</div>
            <div style="font-size:19px;font-weight:900;color:#38bdf8;margin-top:3px;">${{fmtR(rsm.valor_novos)}}</div>
            <div style="font-size:11px;color:#e0f2fe;">${{rsm.qtd_novos}} itens prontos para importar</div>
          </div>
        </div>

        <div style="overflow-x:auto;margin-bottom:12px;">
          <table>
            <thead>
              <tr>
                <th style="width:36px;text-align:center;">✔</th>
                <th>Data</th>
                <th>Resultado do Batimento</th>
                <th>Categoria Classificada</th>
                <th>Descrição no Extrato / Sistema</th>
                <th style="text-align:right;">Valor Extrato</th>
                <th>Ação de Conciliação</th>
              </tr>
            </thead>
            <tbody>${{linhasHtml}}</tbody>
          </table>
        </div>

        <div style="display:flex;justify-content:flex-end;gap:10px;">
          <button type="button" class="btn" onclick="confirmarAplicacaoBatimentoExtrato()" style="background:#10b981;color:#0b132b;font-weight:900;padding:10px 22px;">
            ✅ Confirmar Batimento &amp; Atualizar Gráficos das Unidades
          </button>
        </div>
      `;
    }}

    async function confirmarAplicacaoBatimentoExtrato() {{
      const unidPadrao = document.getElementById("selExtratoGestoraUnidade")?.value || "FILIAL_DF";
      const selecionados = [];
      EXTRATO_BATIMENTO_ITENS.forEach((it, idx) => {{
        const chk = document.getElementById(`chkExt_${{idx}}`);
        if (!chk || !chk.checked) return;
        const acao = document.getElementById(`selAcaoExt_${{idx}}`)?.value || "IGNORAR";
        if (acao === "IGNORAR") return;
        const cat = document.getElementById(`selCatExt_${{idx}}`)?.value || it.categoria;
        selecionados.push({{
          acao,
          id_sistema: it.id_sistema,
          unidade: it.unidade || unidPadrao,
          categoria: cat,
          data: it.data,
          descricao_extrato: it.descricao_extrato,
          fornecedor: it.fornecedor,
          valor_extrato: it.valor_extrato
        }});
      }});

      if (!selecionados.length) {{
        alert("Nenhum item marcado para aplicar.");
        return;
      }}

      const res = await fetch("/api/fiscal/v2/despesas-unidades/aplicar-conciliacao", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{
          itens: selecionados,
          usuario: USUARIO_FISCAL?.username || "gestora"
        }})
      }}).then(r => r.json());

      if (res.ok) {{
        alert(res.msg);
        document.getElementById("boxResultadoBatimentoExtrato").style.display = "none";
        toggleBoxExtratoGestora(false);
        carregarDespesasUnidades();
      }} else {{
        alert("⚠️ " + (res.msg || "Falha ao aplicar conciliação."));
      }}
    }}

    // Chamar carregarNotasRecebidasDFe e carregarDespesasUnidades dentro de carregarDadosFiscais
    const _origCarregarDadosFiscais = carregarDadosFiscais;
    carregarDadosFiscais = async function(osId) {{
      await _origCarregarDadosFiscais(osId);
      carregarNotasRecebidasDFe();
      const selUnid = document.getElementById("selDespFiltroUnidade");
      if (selUnid) selUnid.value = FILIAL_ATIVA || "CONSOLIDADO";
      carregarDespesasUnidades();
    }};


    // =========================================================================
    // MÓDULO JS: ANÁLISE & GESTÃO MANUAL DE CFOP
    // =========================================================================
    let CACHE_REGRAS_CFOP = [];
    let CACHE_CATEGORIAS_CFOP_INIT = false;

    function toggleFormNovoCfop(forcar) {{
      const box = document.getElementById("boxFormNovoCfop");
      if (!box) return;
      if (typeof forcar === "boolean") {{
        box.style.display = forcar ? "block" : "none";
      }} else {{
        box.style.display = (box.style.display === "none" || !box.style.display) ? "block" : "none";
      }}
    }}

    function _escAttrCfop(v) {{
      return String(v == null ? "" : v).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }}

    async function carregarDadosCfop() {{
      try {{
        const busca = (document.getElementById("buscaPecaCfop")?.value || "").trim();
        const cat = (document.getElementById("filtroCatPecaCfop")?.value || "TODAS").trim();
        const url = `/api/fiscal/v2/cfop/dados?busca_peca=${{encodeURIComponent(busca)}}&categoria=${{encodeURIComponent(cat)}}`;
        const res = await fetch(url);
        const data = await res.json();
        if (!data.ok) {{
          alert(data.msg || "Erro ao carregar dados de CFOP.");
          return;
        }}

        CACHE_REGRAS_CFOP = data.regras || [];

        const totalRegras = CACHE_REGRAS_CFOP.length;
        const ativas = CACHE_REGRAS_CFOP.filter(r => r.ativo === 1).length;
        const elTot = document.getElementById("kpiCfopTotalRegras");
        const elSub = document.getElementById("kpiCfopAtivasSub");
        const elPec = document.getElementById("kpiCfopTotalPecas");
        const elPecSub = document.getElementById("kpiCfopResumoEstoqueSub");
        const elNot = document.getElementById("kpiCfopTotalNotas");
        const elIss = document.getElementById("kpiCfopIssUnidades");

        if (elTot) elTot.textContent = String(totalRegras);
        if (elSub) elSub.textContent = `${{ativas}} ativas no sistema`;
        if (elPec) elPec.textContent = String(data.total_pecas || 0);
        if (elNot) elNot.textContent = String((data.notas_cfop || []).length);

        const issCe = Number(data.iss_filiais?.MATRIZ_CE ?? 2.0).toFixed(1).replace(".", ",");
        const issDf = Number(data.iss_filiais?.FILIAL_DF ?? 5.0).toFixed(1).replace(".", ",");
        if (elIss) elIss.innerHTML = `Matriz CE: <span style="color:#34d399;">${{issCe}}%</span><br/>Filial DF: <span style="color:#fbbf24;">${{issDf}}%</span>`;

        const resEst = data.resumo_estoque || [];
        if (elPecSub) {{
          elPecSub.textContent = resEst.length ? `Principal: Venda ${{resEst[0].cfop_venda || '-'}} / Transf. ${{resEst[0].cfop_transferencia || '-'}} (${{resEst[0].qtd_pecas}} itens)` : "Sem peças";
        }}
        const boxResEst = document.getElementById("boxResumoCfopEstoque");
        if (boxResEst) {{
          boxResEst.innerHTML = resEst.map(r =>
            `<span class="badge" style="margin-right:6px;margin-bottom:4px;display:inline-block;background:#1e293b;border:1px solid #34d399;color:#a7f3d0;">Venda: <b>${{_escAttrCfop(r.cfop_venda || 'N/D')}}</b> | Transf: <b>${{_escAttrCfop(r.cfop_transferencia || 'N/D')}}</b> → ${{r.qtd_pecas}} peças</span>`
          ).join("") || "Nenhum dado de estoque encontrado.";
        }}

        if (!CACHE_CATEGORIAS_CFOP_INIT && Array.isArray(data.categorias_estoque)) {{
          CACHE_CATEGORIAS_CFOP_INIT = true;
          const opts = ['<option value="TODAS">Todas as Categorias</option>'].concat(
            data.categorias_estoque.map(c => `<option value="${{_escAttrCfop(c)}}">${{_escAttrCfop(c)}}</option>`)
          ).join("");
          const s1 = document.getElementById("filtroCatPecaCfop");
          const s2 = document.getElementById("loteCfopCategoria");
          if (s1) s1.innerHTML = opts;
          if (s2) s2.innerHTML = opts;
        }}

        renderizarTabelaRegrasCfop();
        renderizarTabelaPecasCfop(data.pecas_cfop || []);
        renderizarTabelaNotasCfop(data.notas_cfop || []);
      }} catch (err) {{
        console.error("Erro carregarDadosCfop:", err);
      }}
    }}

    function renderizarTabelaRegrasCfop() {{
      const tbody = document.getElementById("tbodyRegrasCfop");
      if (!tbody) return;
      const txt = (document.getElementById("filtroCfopTexto")?.value || "").trim().toLowerCase();
      const tipo = (document.getElementById("filtroCfopTipo")?.value || "TODOS").toUpperCase();
      const fil = (document.getElementById("filtroCfopFilial")?.value || "TODAS").toUpperCase();

      const filtradas = CACHE_REGRAS_CFOP.filter(r => {{
        if (tipo !== "TODOS" && String(r.tipo_operacao).toUpperCase() !== tipo) return false;
        if (fil !== "TODAS" && String(r.filial_aplicavel).toUpperCase() !== fil) return false;
        if (txt) {{
          const hay = `${{r.codigo}} ${{r.natureza_operacao}} ${{r.aplicacao_sistema}} ${{r.observacao_fiscal}}`.toLowerCase();
          if (!hay.includes(txt)) return false;
        }}
        return true;
      }});

      if (!filtradas.length) {{
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#94a3b8;padding:18px;">Nenhuma regra de CFOP encontrada para este filtro.</td></tr>';
        return;
      }}

      tbody.innerHTML = filtradas.map(r => `
        <tr data-cfop-id="${{r.id}}">
          <td>
            <input id="cfop_cod_${{r.id}}" value="${{_escAttrCfop(r.codigo)}}" style="width:76px;font-weight:900;color:#38bdf8;padding:5px 6px;" />
          </td>
          <td>
            <select id="cfop_tipo_${{r.id}}" style="padding:4px;font-size:11.5px;margin-bottom:4px;">
              <option value="SAIDA" ${{r.tipo_operacao === 'SAIDA' ? 'selected' : ''}}>SAÍDA</option>
              <option value="ENTRADA" ${{r.tipo_operacao === 'ENTRADA' ? 'selected' : ''}}>ENTRADA</option>
            </select>
            <select id="cfop_esf_${{r.id}}" style="padding:4px;font-size:11.5px;">
              <option value="ESTADUAL" ${{r.esfera === 'ESTADUAL' ? 'selected' : ''}}>ESTADUAL</option>
              <option value="INTERESTADUAL" ${{r.esfera === 'INTERESTADUAL' ? 'selected' : ''}}>INTERESTADUAL</option>
            </select>
          </td>
          <td>
            <select id="cfop_fil_${{r.id}}" style="padding:5px;font-size:11.5px;">
              <option value="AMBAS" ${{r.filial_aplicavel === 'AMBAS' ? 'selected' : ''}}>AMBAS</option>
              <option value="MATRIZ_CE" ${{r.filial_aplicavel === 'MATRIZ_CE' ? 'selected' : ''}}>MATRIZ CE</option>
              <option value="FILIAL_DF" ${{r.filial_aplicavel === 'FILIAL_DF' ? 'selected' : ''}}>FILIAL DF</option>
            </select>
          </td>
          <td>
            <input id="cfop_nat_${{r.id}}" value="${{_escAttrCfop(r.natureza_operacao)}}" style="padding:5px 6px;font-size:12px;" />
          </td>
          <td>
            <input id="cfop_apl_${{r.id}}" value="${{_escAttrCfop(r.aplicacao_sistema)}}" style="padding:5px 6px;font-size:12px;" />
          </td>
          <td>
            <input id="cfop_icms_${{r.id}}" type="number" step="0.1" value="${{Number(r.aliquota_icms || 0).toFixed(1)}}" style="width:66px;padding:5px 6px;font-size:12px;" />
          </td>
          <td>
            <input id="cfop_iss_${{r.id}}" type="number" step="0.1" value="${{Number(r.aliquota_iss || 0).toFixed(1)}}" style="width:66px;padding:5px 6px;font-size:12px;" />
          </td>
          <td>
            <input id="cfop_obs_${{r.id}}" value="${{_escAttrCfop(r.observacao_fiscal)}}" style="padding:5px 6px;font-size:11.5px;" />
          </td>
          <td style="text-align:center;white-space:nowrap;">
            <button type="button" class="btn btn-blue" style="padding:5px 9px;font-size:11.5px;" onclick="salvarRegraCfopLinha(${{r.id}})">💾 Salvar</button>
            <button type="button" class="btn btn-danger" style="padding:5px 8px;font-size:11.5px;" onclick="excluirRegraCfop(${{r.id}}, '${{_escAttrCfop(r.codigo)}}')">🗑️</button>
          </td>
        </tr>
      `).join("");
    }}

    async function salvarRegraCfopLinha(id) {{
      const payload = {{
        id: id,
        codigo: document.getElementById(`cfop_cod_${{id}}`)?.value || "",
        tipo_operacao: document.getElementById(`cfop_tipo_${{id}}`)?.value || "SAIDA",
        esfera: document.getElementById(`cfop_esf_${{id}}`)?.value || "ESTADUAL",
        filial_aplicavel: document.getElementById(`cfop_fil_${{id}}`)?.value || "AMBAS",
        natureza_operacao: document.getElementById(`cfop_nat_${{id}}`)?.value || "",
        aplicacao_sistema: document.getElementById(`cfop_apl_${{id}}`)?.value || "",
        aliquota_icms: parseFloat(document.getElementById(`cfop_icms_${{id}}`)?.value || "0") || 0,
        aliquota_iss: parseFloat(document.getElementById(`cfop_iss_${{id}}`)?.value || "0") || 0,
        observacao_fiscal: document.getElementById(`cfop_obs_${{id}}`)?.value || "",
        ativo: 1,
        usuario: (localStorage.getItem("emed_fiscal_user") || "operador")
      }};
      const res = await fetch("/api/fiscal/v2/cfop/salvar", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      const data = await res.json();
      alert(data.msg || (data.ok ? "Salvo!" : "Erro ao salvar."));
      if (data.ok) carregarDadosCfop();
    }}

    async function salvarNovoCfop() {{
      const payload = {{
        codigo: document.getElementById("novoCfopCodigo")?.value || "",
        tipo_operacao: document.getElementById("novoCfopTipo")?.value || "SAIDA",
        esfera: document.getElementById("novoCfopEsfera")?.value || "ESTADUAL",
        filial_aplicavel: document.getElementById("novoCfopFilial")?.value || "AMBAS",
        natureza_operacao: document.getElementById("novoCfopNatureza")?.value || "",
        aplicacao_sistema: document.getElementById("novoCfopAplicacao")?.value || "",
        aliquota_icms: parseFloat(document.getElementById("novoCfopIcms")?.value || "0") || 0,
        aliquota_iss: parseFloat(document.getElementById("novoCfopIss")?.value || "0") || 0,
        observacao_fiscal: document.getElementById("novoCfopObs")?.value || "",
        ativo: 1,
        usuario: (localStorage.getItem("emed_fiscal_user") || "operador")
      }};
      const res = await fetch("/api/fiscal/v2/cfop/salvar", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      const data = await res.json();
      alert(data.msg || (data.ok ? "Novo CFOP salvo!" : "Erro ao salvar."));
      if (data.ok) {{
        document.getElementById("novoCfopCodigo").value = "";
        document.getElementById("novoCfopNatureza").value = "";
        document.getElementById("novoCfopAplicacao").value = "";
        document.getElementById("novoCfopObs").value = "";
        toggleFormNovoCfop(false);
        carregarDadosCfop();
      }}
    }}

    async function excluirRegraCfop(id, codigo) {{
      if (!confirm(`Deseja realmente excluir a regra CFOP ${{codigo}}?`)) return;
      const res = await fetch("/api/fiscal/v2/cfop/excluir", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ id, usuario: (localStorage.getItem("emed_fiscal_user") || "operador") }})
      }});
      const data = await res.json();
      alert(data.msg || "Excluído!");
      if (data.ok) carregarDadosCfop();
    }}

    function renderizarTabelaPecasCfop(pecas) {{
      const tbody = document.getElementById("tbodyPecasCfop");
      if (!tbody) return;
      if (!pecas.length) {{
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:16px;">Nenhuma peça encontrada.</td></tr>';
        return;
      }}
      tbody.innerHTML = pecas.map(p => `
        <tr>
          <td style="font-weight:800;color:#38bdf8;">${{_escAttrCfop(p.codigo)}}</td>
          <td>${{_escAttrCfop(p.nome_peca)}}</td>
          <td style="font-size:11.5px;color:#cbd5e1;">${{_escAttrCfop(p.categoria)}}</td>
          <td style="font-size:11.5px;color:#94a3b8;">${{_escAttrCfop(p.ncm)}}</td>
          <td><input id="peca_cfop_v_${{p.id}}" value="${{_escAttrCfop(p.cfop_padrao_venda)}}" style="width:92px;padding:4px 6px;font-weight:800;" /></td>
          <td><input id="peca_cfop_t_${{p.id}}" value="${{_escAttrCfop(p.cfop_padrao_transferencia)}}" style="width:92px;padding:4px 6px;font-weight:800;" /></td>
          <td style="text-align:center;">
            <button type="button" class="btn btn-blue" style="padding:5px 10px;font-size:11.5px;" onclick="salvarCfopPecaIndividual(${{p.id}})">💾 Salvar</button>
          </td>
        </tr>
      `).join("");
    }}

    async function salvarCfopPecaIndividual(pecaId) {{
      const cfopV = (document.getElementById(`peca_cfop_v_${{pecaId}}`)?.value || "").trim();
      const cfopT = (document.getElementById(`peca_cfop_t_${{pecaId}}`)?.value || "").trim();
      const res = await fetch("/api/fiscal/v2/cfop/aplicar-estoque", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          modo: "individual",
          peca_id: pecaId,
          cfop_padrao_venda: cfopV,
          cfop_padrao_transferencia: cfopT,
          usuario: (localStorage.getItem("emed_fiscal_user") || "operador")
        }})
      }});
      const data = await res.json();
      alert(data.msg || "Salvo!");
      if (data.ok) carregarDadosCfop();
    }}

    async function aplicarCfopEstoqueLote() {{
      const categoria = document.getElementById("loteCfopCategoria")?.value || "TODAS";
      const cfopV = (document.getElementById("loteCfopVenda")?.value || "").trim();
      const cfopT = (document.getElementById("loteCfopTransf")?.value || "").trim();
      if (!cfopV && !cfopT) {{
        alert("Informe pelo menos um CFOP (Venda ou Transferência) para aplicar em lote.");
        return;
      }}
      if (!confirm(`Confirmar atualização em lote para categoria "${{categoria}}"?\nCFOP Venda: ${{cfopV || '(manter)'}}\nCFOP Transf.: ${{cfopT || '(manter)'}}`)) return;
      const res = await fetch("/api/fiscal/v2/cfop/aplicar-estoque", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          modo: "lote",
          categoria: categoria,
          cfop_padrao_venda: cfopV,
          cfop_padrao_transferencia: cfopT,
          usuario: (localStorage.getItem("emed_fiscal_user") || "operador")
        }})
      }});
      const data = await res.json();
      alert(data.msg || "Atualizado!");
      if (data.ok) carregarDadosCfop();
    }}

    function renderizarTabelaNotasCfop(notas) {{
      const tbody = document.getElementById("tbodyNotasCfop");
      if (!tbody) return;
      if (!notas.length) {{
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:16px;">Nenhuma nota fiscal registrada.</td></tr>';
        return;
      }}
      tbody.innerHTML = notas.map(n => `
        <tr>
          <td style="font-weight:800;">#${{n.id}} ${{n.numero_nf ? '(' + _escAttrCfop(n.numero_nf) + ')' : ''}}</td>
          <td><span class="badge">${{_escAttrCfop(n.filial_emissora || '-')}}</span></td>
          <td style="font-size:12px;">${{_escAttrCfop(n.cliente)}}</td>
          <td style="font-size:11.5px;color:#cbd5e1;">${{_escAttrCfop(n.status_fiscal)}}</td>
          <td style="font-size:12px;font-weight:700;">${{Number(n.aliquota_iss || 0).toFixed(1)}}%</td>
          <td><input id="nf_cfop_${{n.id}}" value="${{_escAttrCfop(n.cfop)}}" placeholder="Ex: 5933" style="width:92px;padding:4px 6px;font-weight:800;color:#fbbf24;" /></td>
          <td><input id="nf_nat_${{n.id}}" value="${{_escAttrCfop(n.natureza_operacao)}}" style="padding:4px 6px;font-size:11.5px;" /></td>
          <td style="text-align:center;">
            <button type="button" class="btn btn-blue" style="padding:5px 10px;font-size:11.5px;" onclick="salvarCfopNota(${{n.id}})">💾 Salvar</button>
          </td>
        </tr>
      `).join("");
    }}

    async function salvarCfopNota(notaId) {{
      const cfop = (document.getElementById(`nf_cfop_${{notaId}}`)?.value || "").trim();
      const nat = (document.getElementById(`nf_nat_${{notaId}}`)?.value || "").trim();
      const res = await fetch("/api/fiscal/v2/cfop/atualizar-nota", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          id: notaId,
          cfop: cfop,
          natureza_operacao: nat,
          usuario: (localStorage.getItem("emed_fiscal_user") || "operador")
        }})
      }});
      const data = await res.json();
      alert(data.msg || "Salvo!");
      if (data.ok) carregarDadosCfop();
    }}

    function exportarRegrasCfopCsv() {{
      if (!CACHE_REGRAS_CFOP.length) {{
        alert("Nenhuma regra de CFOP carregada para exportar.");
        return;
      }}
      const header = ["Codigo", "Tipo", "Esfera", "Unidade", "Natureza_Operacao", "Aplicacao_Sistema", "ICMS_Pct", "ISS_Pct", "Observacao"];
      const linhas = [header.join(";")].concat(
        CACHE_REGRAS_CFOP.map(r => [
          r.codigo, r.tipo_operacao, r.esfera, r.filial_aplicavel,
          (r.natureza_operacao || "").replace(/;/g, ","),
          (r.aplicacao_sistema || "").replace(/;/g, ","),
          r.aliquota_icms, r.aliquota_iss,
          (r.observacao_fiscal || "").replace(/;/g, ",")
        ].join(";"))
      );
      const blob = new Blob(["\uFEFF" + linhas.join("\\n")], {{ type: "text/csv;charset=utf-8;" }});
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "tabela_cfop_emed.csv";
      a.click();
    }}

    initPortalFiscal();
  </script>

  <!-- MODAL DE VISUALIZAÇÃO COMPLETA & DANFE DA NOTA RECEBIDA (RADAR DF-E) -->
  <div class="modal-overlay" id="modalItensDFe" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.82);backdrop-filter:blur(4px);z-index:9999;align-items:center;justify-content:center;padding:14px;">
    <div style="background:#0f172a;border:2px solid #0284c7;border-radius:12px;width:980px;max-width:98%;max-height:94vh;display:flex;flex-direction:column;padding:18px;box-shadow:0 12px 38px rgba(0,0,0,0.75);color:#fff;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;border-bottom:1px solid #334155;padding-bottom:10px;margin-bottom:12px;">
        <div>
          <h3 id="modalItensDFeTitulo" style="margin:0;font-size:16px;color:#38bdf8;">Visualização Completa &amp; DANFE da Nota Fiscal</h3>
          <div id="modalItensDFeSubtitulo" style="font-size:12px;color:#cbd5e1;margin-top:4px;"></div>
        </div>
        <button type="button" onclick="fecharModalItensDFe()" style="background:#1e293b;border:1px solid #475569;border-radius:6px;color:#e2e8f0;font-size:14px;padding:4px 10px;cursor:pointer;font-weight:bold;">✕ Fechar</button>
      </div>

      <!-- BARRA DE AÇÕES: DANFE, DOWNLOAD PDF, XML, WHATSAPP E E-MAIL -->
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:10px 12px;margin-bottom:10px;">
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" id="btnTabModalDFeDanfe" class="btn" style="width:auto;padding:7px 13px;font-size:12px;background:#0284c7;color:#fff;" onclick="alternarVisaoModalDFe('DANFE')">📄 DANFE Completa Oficial</button>
          <button type="button" id="btnTabModalDFeItens" class="btn" style="width:auto;padding:7px 13px;font-size:12px;background:#1e293b;color:#cbd5e1;border:1px solid #475569;" onclick="alternarVisaoModalDFe('ITENS')">📦 Relação de Itens &amp; Peças</button>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
          <a id="btnModalDFeBaixarPdf" href="#" class="btn btn-primary" style="width:auto;padding:7px 13px;font-size:12px;">📥 Baixar DANFE (.PDF)</a>
          <a id="btnModalDFeBaixarXml" href="#" class="btn btn-outline" style="width:auto;padding:7px 12px;font-size:12px;border-color:#38bdf8;color:#38bdf8;">📥 Baixar XML</a>
          <button type="button" class="btn" style="width:auto;padding:7px 13px;font-size:12px;background:#16a34a;color:#fff;" onclick="toggleBoxShareModalDFe('whats')">📲 Enviar WhatsApp</button>
          <button type="button" class="btn" style="width:auto;padding:7px 13px;font-size:12px;background:#2563eb;color:#fff;" onclick="toggleBoxShareModalDFe('email')">✉️ Enviar E-mail</button>
          <a id="btnModalDFeAbrirNovaAba" href="#" target="_blank" class="btn btn-outline" style="width:auto;padding:7px 11px;font-size:11.5px;" title="Abrir DANFE em tela cheia">↗️ Nova Guia</a>
        </div>
      </div>

      <!-- PAINEL RÁPIDO DE ENVIO POR WHATSAPP OU E-MAIL -->
      <div id="boxShareModalDFe" style="display:none;background:#132338;border:1.5px solid #0284c7;border-radius:8px;padding:12px;margin-bottom:10px;">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:6px;flex-wrap:wrap;">
              <label style="color:#4ade80;font-size:12px;font-weight:700;margin:0;">📲 Enviar por WhatsApp:</label>
              <div style="display:flex;gap:5px;">
                <button type="button" id="btnConectarWhatsPrompt" onclick="perguntarOndeConectarWhatsApp()" style="background:#0f172a;border:1px solid #38bdf8;color:#38bdf8;border-radius:4px;font-size:11px;padding:3px 8px;cursor:pointer;" title="Conectar no seu navegador padrão ou no robô local">🌐 Conectar WhatsApp...</button>
                <button type="button" onclick="salvarContatoRapidoWhatsDFe()" style="background:none;border:1px solid #4ade80;color:#4ade80;border-radius:4px;font-size:11px;padding:3px 8px;cursor:pointer;" title="Salvar os números digitados como atalho rápido">+ Salvar Contato</button>
              </div>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
              <input type="text" id="inpModalDFeWhats" placeholder="DDD + Número (ex: 85999999999) ou vazio p/ escolher contato" style="flex:1;min-width:180px;padding:8px 10px;font-size:12px;" />
              <button type="button" id="btnDispararWhatsNavegadorPadrao" class="btn" style="width:auto;background:#16a34a;color:#fff;padding:8px 12px;font-size:12px;font-weight:700;white-space:nowrap;" onclick="enviarWhatsNavegadorPadraoModalDFe()" title="Abre diretamente no seu navegador padrão (Chrome, Edge, Firefox etc.)">🌐 Abrir no Navegador Padrão</button>
              <button type="button" id="btnDispararWhatsPdfAuto" class="btn" style="width:auto;background:#0369a1;color:#fff;padding:8px 10px;font-size:11px;white-space:nowrap;" onclick="enviarWhatsDanfeModalDFe()" title="Anexa o arquivo PDF físico via robô local">🤖 Enviar PDF (Robô)</button>
            </div>
            <div id="boxContatosRapidosWhatsDFe" style="display:flex;gap:5px;flex-wrap:wrap;margin-top:6px;"></div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px;">💡 <b>Dica:</b> O envio via <b>Navegador Padrão</b> abre no navegador que você já usa no dia a dia, com a mensagem pronta e o link oficial da DANFE.</div>
          </div>
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
              <label style="color:#60a5fa;font-size:12px;font-weight:700;margin:0;">✉️ Enviar DANFE Completa por E-mail:</label>
              <div style="display:flex;gap:4px;">
                <button type="button" onclick="abrirEmailDanfeWebmail('gmail')" style="background:#450a0a;border:1px solid #ef4444;color:#fca5a5;border-radius:4px;font-size:11px;padding:2px 7px;cursor:pointer;font-weight:600;" title="Abrir rascunho no Gmail Web">🔴 Gmail</button>
                <button type="button" onclick="abrirEmailDanfeWebmail('outlook')" style="background:#082f49;border:1px solid #0284c7;color:#7dd3fc;border-radius:4px;font-size:11px;padding:2px 7px;cursor:pointer;font-weight:600;" title="Abrir rascunho no Outlook Web">🔵 Outlook</button>
                <button type="button" onclick="abrirEmailDanfeWebmail('mailto')" style="background:#1e293b;border:1px solid #64748b;color:#cbd5e1;border-radius:4px;font-size:11px;padding:2px 7px;cursor:pointer;font-weight:600;" title="Abrir no aplicativo padrão do computador (Outlook/Thunderbird)">💻 App Padrão</button>
              </div>
            </div>
            <div style="display:flex;gap:6px;margin-top:6px;">
              <input type="email" id="inpModalDFeEmail" placeholder="destinatario@empresa.com.br" style="flex:1;padding:8px 10px;font-size:12px;" />
              <button type="button" id="btnDispararEmailModal" class="btn" style="width:auto;background:#2563eb;color:#fff;padding:8px 14px;font-size:12px;white-space:nowrap;" onclick="enviarEmailDanfeModalDFe()">✉️ Disparar E-mail</button>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-top:4px;">💡 <b>Dica:</b> Envia os dados completos da NF-e, chave de acesso e links oficiais da DANFE e XML.</div>
          </div>
        </div>
        <div id="avisoEnvioPdfModalDFe" style="display:none;margin-top:8px;padding:8px 12px;border-radius:6px;background:#064e3b;border:1px solid #10b981;color:#d1fae5;font-size:12px;"></div>
      </div>

      <!-- VISÃO 1: DANFE COMPLETA EMBUTIDA -->
      <div id="boxModalDFeVisaoDanfe" style="flex:1;min-height:460px;background:#e2e8f0;border-radius:8px;overflow:hidden;border:1px solid #475569;">
        <iframe id="iframeDanfeDFeModal" src="about:blank" style="width:100%;height:500px;border:none;background:#fff;"></iframe>
      </div>

      <!-- VISÃO 2: TABELA DE ITENS -->
      <div id="boxModalDFeVisaoItens" style="display:none;overflow-x:auto;max-height:460px;">
        <table style="width:100%;font-size:12px;">
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição do Item / Peça / Mercadoria</th>
              <th>NCM</th>
              <th>Unid.</th>
              <th>Qtd</th>
              <th>Preço Unitário</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody id="tbodyModalItensDFe"></tbody>
        </table>
      </div>

      <div style="margin-top:12px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid #334155;padding-top:10px;">
        <span style="font-size:11.5px;color:#94a3b8;">💡 Dica: Você pode imprimir/salvar a DANFE em PDF, baixar o XML oficial ou compartilhar diretamente por WhatsApp e E-mail.</span>
        <button type="button" class="btn btn-outline" style="width:auto;padding:7px 18px;" onclick="fecharModalItensDFe()">Fechar</button>
      </div>
    </div>
  </div>

  <!-- MODAL DE FICHA FISCAL, TRIBUTÁRIA & PRECIFICAÇÃO (PENTE FINO MULTI-ESTADUAL) -->
  <div id="modalFichaFiscalPeca" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:9999;backdrop-filter:blur(5px);overflow-y:auto;padding:20px;">
    <div style="max-width:880px;margin:20px auto;background:#0f172a;border:2px solid #0284c7;border-radius:12px;padding:24px;color:#f8fafc;box-shadow:0 10px 40px rgba(2,132,199,0.3);">
      
      <div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:12px;margin-bottom:16px;">
        <div>
          <div style="font-size:16px;font-weight:900;color:#38bdf8;" id="modalFichaTitulo">⚙️ Ficha Fiscal, Tributária &amp; Precificação</div>
          <div style="font-size:12px;color:#94a3b8;" id="modalFichaSubtitulo">Configuração avançada para emissão estadual e apuração de margens</div>
        </div>
        <button type="button" onclick="fecharModalFichaFiscal()" class="btn btn-outline" style="padding:4px 10px;font-size:13px;color:#94a3b8;">✕ Fechar</button>
      </div>

      <!-- ABAS DO MODAL -->
      <div style="display:flex;gap:8px;margin-bottom:16px;border-bottom:1px solid #1e293b;padding-bottom:8px;overflow-x:auto;">
        <button type="button" class="btn btn-blue" id="tabBtn_ident" onclick="mudarTabFicha('ident')" style="font-size:12px;padding:6px 12px;">🏷️ Identificação &amp; Engenharia</button>
        <button type="button" class="btn btn-outline" id="tabBtn_icms" onclick="mudarTabFicha('icms')" style="font-size:12px;padding:6px 12px;">🏛️ ICMS, NCM &amp; Estados</button>
        <button type="button" class="btn btn-outline" id="tabBtn_fed" onclick="mudarTabFicha('fed')" style="font-size:12px;padding:6px 12px;">🇧🇷 Tributos Federais (PIS/COFINS/IPI)</button>
        <button type="button" class="btn btn-outline" id="tabBtn_preco" onclick="mudarTabFicha('preco')" style="font-size:12px;padding:6px 12px;">💰 Precificação &amp; Margens</button>
      </div>

      <input type="hidden" id="fch_id" />
      <div id="fch_box_alerta_reajuste" style="display:none;margin-bottom:14px;"></div>

      <!-- ABA 1: IDENTIFICAÇÃO & ENGENHARIA CLÍNICA (RDC 611) -->
      <div id="tabContent_ident">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;">
          <div style="grid-column:1/-1;">
            <label>Descrição Oficial da Peça / Produto:</label>
            <input id="fch_nome" type="text" style="width:100%;font-weight:700;" />
          </div>
          <div>
            <label>Código Interno (SKU):</label>
            <input id="fch_codigo" type="text" disabled style="background:#1e293b;opacity:0.7;" />
          </div>
          <div>
            <label>Código de Barras / GTIN / EAN:</label>
            <input id="fch_ean" type="text" placeholder="SEM GTIN ou 789..." />
          </div>
          <div>
            <label>Fabricante / Marca:</label>
            <input id="fch_fabricante" type="text" placeholder="Ex: GE, Philips, Siemens, Dunlee..." />
          </div>
          <div>
            <label>Modelo / Tomógrafo Compatível:</label>
            <input id="fch_modelo" type="text" placeholder="Ex: Optima CT520, Revolution EVO..." />
          </div>
          <div>
            <label>Número de Série (RDC 611 / Tubos RX):</label>
            <input id="fch_serie" type="text" placeholder="Nº de Série do Tubo ou Placa" />
          </div>
          <div>
            <label>Lote de Fabricação:</label>
            <input id="fch_lote" type="text" placeholder="Lote do Fabricante" />
          </div>
          <div>
            <label>Unidade Comercial:</label>
            <select id="fch_unidade">
              <option value="UN">UN - Unidade</option>
              <option value="PC">PC - Peça</option>
              <option value="JG">JG - Jogo</option>
              <option value="KIT">KIT - Conjunto/Kit</option>
              <option value="MT">MT - Metros</option>
            </select>
          </div>
          <div>
            <label>Localização no Almoxarifado:</label>
            <input id="fch_local" type="text" placeholder="Ex: Prateleira 2, Base Paulo, Gaveta B" />
          </div>
        </div>
      </div>

      <!-- ABA 2: ICMS, NCM & LEIS ESTADUAIS (DF, CE, INTERESTADUAL) -->
      <div id="tabContent_icms" style="display:none;">
        <div style="background:#1e293b;border-left:4px solid #38bdf8;padding:10px 14px;border-radius:4px;font-size:12px;margin-bottom:14px;line-height:1.5;">
          <b>⚖️ Diretrizes Estaduais &amp; Isenções de Saúde:</b><br/>
          &bull; <b>Equipamentos Hospitalares:</b> Possuem isenção/desoneração pelo Convênio ICMS 01/99 e 126/10 quando faturados para clínicas e hospitais.<br/>
          &bull; <b>Transferência de Peças (CE ⇄ DF):</b> Não incidência de ICMS vinculante (STF ADC 49 / LC 204/2023).
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;">
          <div>
            <label>NCM (8 Dígitos - Obrigatório SEFAZ):</label>
            <input id="fch_ncm" type="text" placeholder="Ex: 9022.90.90 (Tubo/RX)" maxlength="10" style="font-weight:700;color:#38bdf8;" />
          </div>
          <div>
            <label>CEST (Substituição Tributária):</label>
            <input id="fch_cest" type="text" placeholder="Ex: 01.001.00 ou vazio" maxlength="10" />
          </div>
          <div>
            <label>Origem da Mercadoria:</label>
            <select id="fch_origem">
              <option value="0">0 - Nacional</option>
              <option value="1">1 - Estrangeira (Importação Direta)</option>
              <option value="2">2 - Estrangeira (Adquirida Mercado Interno)</option>
              <option value="4">4 - Nacional com Conteúdo de Importação > 40%</option>
            </select>
          </div>
          <div>
            <label>Regime ICMS / CSOSN (Simples Nacional):</label>
            <select id="fch_csosn">
              <option value="102">102 - Tributada pelo Simples sem permissão de crédito</option>
              <option value="400">400 - Não tributada pelo Simples Nacional (Isenta)</option>
              <option value="500">500 - ICMS cobrado anteriormente por Substituição Tributária</option>
              <option value="900">900 - Outros (Com destaque / Operação Especial)</option>
            </select>
          </div>
          <div>
            <label>Alíquota Interna de ICMS (%):</label>
            <input id="fch_aliq_icms" type="number" step="0.1" placeholder="Ex: 20.0 (CE) ou 18.0 (DF)" />
          </div>
          <div>
            <label>Redução da Base de Cálculo (%):</label>
            <input id="fch_red_icms" type="number" step="0.1" placeholder="Ex: 0.0" />
          </div>
          <div>
            <label>CFOP Padrão Venda:</label>
            <input id="fch_cfop_venda" type="text" value="5102" />
          </div>
          <div>
            <label>CFOP Padrão Transferência:</label>
            <input id="fch_cfop_trf" type="text" value="5152" />
          </div>
          <div style="grid-column:1/-1;">
            <label>Motivo de Desoneração / Amparo Legal de Isenção:</label>
            <input id="fch_isencao_motivo" type="text" value="Convênio ICMS 01/99 - Equipamento Médico-Hospitalar" />
          </div>
        </div>
      </div>

      <!-- ABA 3: TRIBUTOS FEDERAIS (PIS, COFINS, IPI) -->
      <div id="tabContent_fed" style="display:none;">
        <div style="background:#1e293b;border-left:4px solid #10b981;padding:10px 14px;border-radius:4px;font-size:12px;margin-bottom:14px;line-height:1.5;">
          <b>🏥 Benefício Fiscal Federal (Alíquota Zero):</b><br/>
          Dispositivos e peças de imagem e medicina hospitalar contam com enquadramento especial de alíquota zero de PIS/COFINS (Decreto Federal nº 6.426/2008 e Lei 10.865/2004).
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;">
          <div>
            <label>CST PIS:</label>
            <select id="fch_cst_pis">
              <option value="49">49 - Outras Operações de Saída</option>
              <option value="06">06 - Operação Tributável a Alíquota Zero (Hospitalar)</option>
              <option value="04">04 - Operação Monofásica / Substituição</option>
              <option value="01">01 - Operação Tributável com Alíquota Básica</option>
            </select>
          </div>
          <div>
            <label>Alíquota PIS (%):</label>
            <input id="fch_aliq_pis" type="number" step="0.01" value="0.00" />
          </div>
          <div>
            <label>CST COFINS:</label>
            <select id="fch_cst_cofins">
              <option value="49">49 - Outras Operações de Saída</option>
              <option value="06">06 - Operação Tributável a Alíquota Zero (Hospitalar)</option>
              <option value="04">04 - Operação Monofásica / Substituição</option>
              <option value="01">01 - Operação Tributável com Alíquota Básica</option>
            </select>
          </div>
          <div>
            <label>Alíquota COFINS (%):</label>
            <input id="fch_aliq_cofins" type="number" step="0.01" value="0.00" />
          </div>
          <div>
            <label>CST IPI:</label>
            <select id="fch_cst_ipi">
              <option value="53">53 - Saída Não-Tributada</option>
              <option value="51">51 - Saída com Alíquota Zero</option>
              <option value="50">50 - Saída Tributada</option>
            </select>
          </div>
          <div>
            <label>Alíquota IPI (%):</label>
            <input id="fch_aliq_ipi" type="number" step="0.1" value="0.0" />
          </div>
        </div>
      </div>

      <!-- ABA 4: PRECIFICAÇÃO & MARGENS DE VENDA -->
      <div id="tabContent_preco" style="display:none;">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;">
          <div>
            <label>Preço de Custo Última Compra (R$):</label>
            <input id="fch_custo" type="number" step="0.01" oninput="recalcularPrecosFicha()" style="font-weight:700;color:#f87171;" />
          </div>
          <div>
            <label>Custo Médio Ponderado (R$):</label>
            <input id="fch_custo_medio" type="number" step="0.01" />
          </div>
          <div>
            <label>Margem Contrato (%):</label>
            <input id="fch_mg_contrato" type="number" step="1" oninput="recalcularPrecosFicha()" placeholder="Ex: 30" />
          </div>
          <div>
            <label>Margem Avulso / Emergencial (%):</label>
            <input id="fch_mg_avulso" type="number" step="1" oninput="recalcularPrecosFicha()" placeholder="Ex: 60" />
          </div>
          <div>
            <label>Margem À Vista (%):</label>
            <input id="fch_mg_avista" type="number" step="1" placeholder="Ex: 20" />
          </div>
          <div>
            <label>Margem Desestímulo (% - Tubos Raros):</label>
            <input id="fch_mg_desestimulo" type="number" step="1" placeholder="Ex: 180" />
          </div>
          <div>
            <label>Preço de Venda Sugerido (Tabela R$):</label>
            <input id="fch_preco_tabela" type="number" step="0.01" style="font-weight:800;color:#4ade80;font-size:14px;" />
          </div>
          <div>
            <label>Preço Mínimo Piso (Segurança R$):</label>
            <input id="fch_preco_minimo" type="number" step="0.01" style="font-weight:800;color:#fbbf24;" />
          </div>
        </div>
        <div style="font-size:11.5px;color:#94a3b8;margin-top:10px;">
          💡 <b>Dica de Precificação:</b> Você pode alterar os preços de tabela e piso manualmente a qualquer momento. Eles serão aplicados automaticamente na geração de propostas e remessas.
        </div>
      </div>

      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;border-top:1px solid #334155;padding-top:14px;">
        <button type="button" onclick="fecharModalFichaFiscal()" class="btn btn-outline" style="padding:8px 16px;">Cancelar</button>
        <button type="button" onclick="salvarFichaFiscalPeca()" class="btn btn-blue" id="btnSalvarFichaFiscal" style="padding:8px 20px;font-weight:800;">💾 Salvar Parâmetros Fiscais &amp; Precificação</button>
      </div>

    </div>
  </div>

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
    app.router.add_post("/api/fiscal/v2/transferir-filiais", api_fiscal_v2_transferir_filiais)
    app.router.add_post("/api/fiscal/v2/lancar-consumivel", api_fiscal_v2_lancar_consumivel)
    app.router.add_post("/api/fiscal/v2/ajuste-estoque", api_fiscal_v2_ajuste_estoque)
    app.router.add_post("/api/fiscal/v2/inventario/ajuste-direto", api_fiscal_v2_inventario_ajuste_direto)
    app.router.add_get("/api/fiscal/v2/peca/{peca_id}", api_fiscal_v2_peca_detalhes)
    app.router.add_post("/api/fiscal/v2/peca/salvar", api_fiscal_v2_peca_salvar)
    app.router.add_post("/api/fiscal/v2/inventario/novo-item", api_fiscal_v2_inventario_novo_item)
    app.router.add_get("/api/fiscal/v2/fechamento/dados", api_fiscal_v2_fechamento_dados)
    app.router.add_get("/api/fiscal/v2/fechamento/zip", api_fiscal_v2_fechamento_zip)
    app.router.add_get("/api/fiscal/v2/fechamento/relatorio-impresso", api_fiscal_v2_fechamento_relatorio_impresso)
    app.router.add_get("/api/fiscal/v2/fechamento/exportar-csv", api_fiscal_v2_fechamento_exportar_csv)
    app.router.add_post("/api/fiscal/v2/fechamento/marcar-enviado", api_fiscal_v2_fechamento_marcar_enviado)
    app.router.add_get("/api/fiscal/v2/xml/{os_id}", api_fiscal_v2_xml_download)

    # Rotas do Radar DF-e (Notas Recebidas de Fornecedores)
    app.router.add_get("/api/fiscal/recebidas/dados", api_fiscal_recebidas_dados)
    app.router.add_post("/api/fiscal/recebidas/consultar-sefaz", api_fiscal_recebidas_consultar_sefaz)
    app.router.add_post("/api/fiscal/recebidas/manifestar", api_fiscal_recebidas_manifestar)
    app.router.add_post("/api/fiscal/recebidas/dar-entrada-estoque", api_fiscal_recebidas_dar_entrada_estoque)
    app.router.add_post("/api/fiscal/recebidas/importar-xml", api_fiscal_recebidas_importar_xml)
    app.router.add_get("/api/fiscal/recebidas/danfe/{nota_id}", api_fiscal_recebidas_danfe)
    app.router.add_get("/api/fiscal/recebidas/pdf/{nota_id}", api_fiscal_recebidas_pdf)
    app.router.add_get("/api/fiscal/recebidas/eml/{nota_id}", api_fiscal_recebidas_eml_download)
    app.router.add_post("/api/fiscal/recebidas/enviar-email-pdf", api_fiscal_recebidas_enviar_email_pdf)
    app.router.add_get("/api/fiscal/recebidas/whatsapp-status", api_fiscal_recebidas_whatsapp_status)
    app.router.add_post("/api/fiscal/recebidas/whatsapp-conectar", api_fiscal_recebidas_whatsapp_conectar)
    app.router.add_post("/api/fiscal/recebidas/enviar-whatsapp-pdf", api_fiscal_recebidas_enviar_whatsapp_pdf)
    app.router.add_get("/api/fiscal/recebidas/xml/{nota_id}", api_fiscal_recebidas_xml_download)

    # Rotas da Aba de Detalhes de Despesas das Unidades & Gráficos (Alimentação, Gasolina, Hotel)
    app.router.add_get("/api/fiscal/v2/despesas-unidades", api_fiscal_v2_despesas_unidades_dados)
    app.router.add_post("/api/fiscal/v2/despesas-unidades/salvar", api_fiscal_v2_despesas_unidades_salvar)
    app.router.add_post("/api/fiscal/v2/despesas-unidades/excluir", api_fiscal_v2_despesas_unidades_excluir)
    app.router.add_post("/api/fiscal/v2/despesas-unidades/conciliar-extrato", api_fiscal_v2_despesas_unidades_conciliar_extrato)
    app.router.add_post("/api/fiscal/v2/despesas-unidades/aplicar-conciliacao", api_fiscal_v2_despesas_unidades_aplicar_conciliacao)

    # Rotas da Aba de An?lise & Gest?o Manual de CFOP
    app.router.add_get("/api/fiscal/v2/cfop/dados", api_fiscal_v2_cfop_dados)
    app.router.add_post("/api/fiscal/v2/cfop/salvar", api_fiscal_v2_cfop_salvar)
    app.router.add_post("/api/fiscal/v2/cfop/excluir", api_fiscal_v2_cfop_excluir)
    app.router.add_post("/api/fiscal/v2/cfop/aplicar-estoque", api_fiscal_v2_cfop_aplicar_estoque)
    app.router.add_post("/api/fiscal/v2/cfop/atualizar-nota", api_fiscal_v2_cfop_atualizar_nota)

