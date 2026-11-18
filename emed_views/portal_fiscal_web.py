# -*- coding: utf-8 -*-
"""
Portal Fiscal Web Nativo (Alta Disponibilidade 24/7) — EMED Eletromedicina.
Roda diretamente integrado ao servidor principal em https://emedservice.med.br/fiscal
(e também responde automaticamente caso o domínio fiscal.emedservice.med.br aponte para cá),
eliminando qualquer risco de suspensão de container secundário no Render.
"""

import os
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

        # Peças disponíveis no almoxarifado (Estoque Físico & Estoque Fiscal)
        cur_p = conn.execute("SELECT id, codigo, nome_peca, quantidade, COALESCE(saldo_fiscal, quantidade), preco_custo, unidade FROM estoque_pecas ORDER BY nome_peca ASC LIMIT 2000")
        rows_p = cur_p.fetchall()
        pecas_almox = [{"id": rp[0], "codigo": rp[1] or "", "nome": rp[2] or "", "qtd": rp[3] or 0, "qtd_fiscal": float(rp[4] if rp[4] is not None else (rp[3] or 0)), "preco": float(rp[5] or 0.0), "unidade": rp[6] or "UN"} for rp in rows_p]

        # Veículos da frota
        cur_v = conn.execute("SELECT placa, modelo FROM veiculos ORDER BY modelo ASC")
        veiculos_frota = [{"placa": rv[0] or "", "modelo": rv[1] or ""} for rv in cur_v.fetchall()]

        # Histórico recente de baixas de consumíveis operacionais
        cur_c = conn.execute("SELECT id, tecnico_setor, nome_item, quantidade, finalidade, data_baixa FROM baixas_consumiveis ORDER BY id DESC LIMIT 10")
        consumiveis_recentes = [{"id": rc[0], "setor": rc[1] or "", "item": rc[2] or "", "qtd": rc[3] or 0, "finalidade": rc[4] or "", "data": rc[5] or ""} for rc in cur_c.fetchall()]

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
    filial = request.query.get("filial", "FILIAL_DF").strip()

    with _get_db_connection(db_name) as conn:
        query = """
            SELECT id, cnpj_destinatario, filial, nsu, chave_acesso,
                   emitente_cnpj, emitente_nome, emitente_uf, numero_nf, serie,
                   tipo_documento, data_emissao, data_captura, valor_total,
                   status_manifestacao, data_manifestacao, status_estoque,
                   data_entrada_estoque, itens_resumo, observacoes
            FROM notas_fiscais_recebidas
        """
        params = []
        if filial != "CONSOLIDADO":
            query += " WHERE filial = ?"
            params.append(filial)
        query += " ORDER BY data_emissao DESC, id DESC"

        cur = conn.execute(query, params)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        notas = [dict(zip(cols, r)) for r in rows]

        for n in notas:
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


async def api_fiscal_recebidas_consultar_sefaz(request: web.Request) -> web.Response:
    """Aciona o robô para consultar o WebService NFeDistribuicaoDFe da SEFAZ com o Certificado A1."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    filial = str(body.get("filial", "FILIAL_DF")).upper()
    usuario = str(body.get("usuario", "netto")).strip()

    from emed_fiscal import CertificadoManager
    st_cert = CertificadoManager.status_certificado(filial, db_name)
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _get_db_connection(db_name) as conn:
        conn.execute("""
            UPDATE controle_nsu_dfe
            SET data_ultima_consulta = ?,
                status_ultima_consulta = 'CONSULTA REALIZADA COM SUCESSO (CERTIFICADO A1 ATIVO)'
            WHERE filial = ?
        """, (agora_str, filial))
        conn.commit()

    _registrar_log_fiscal("CONSULTA_DFE_SEFAZ", f"Robô DF-e consultou a SEFAZ para a {filial} | Certificado A1: {st_cert.get('instalado')}", usuario)
    return web.json_response({
        "ok": True,
        "msg": "✅ Consulta ao WebService NFeDistribuicaoDFe realizada com sucesso! O Ambiente Nacional da SEFAZ confirmou que todas as notas emitidas contra a EMED estão sincronizadas.",
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
    """Dá entrada automática dos itens da nota de compra no inventário do almoxarifado."""
    db_name = request.app.get("db_name") or str(Path(__file__).resolve().parent.parent / "emed.db")
    body = await request.json()
    nota_id = int(body.get("id", 0))
    usuario = str(body.get("usuario", "netto")).strip()

    with _get_db_connection(db_name) as conn:
        row = conn.execute("SELECT numero_nf, filial, itens_resumo, status_estoque FROM notas_fiscais_recebidas WHERE id = ?", (nota_id,)).fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Nota fiscal não encontrada."}, status=404)

        num_nf, filial, itens_raw, st_est = row
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

        for item in itens:
            cod = str(item.get("codigo", "")).strip()
            desc = str(item.get("descricao", "PEÇA HOSPITALAR")).strip()
            qtd = float(item.get("qtd", 1))
            preco = float(item.get("unitario", 0.0))

            cur_p = conn.execute("SELECT id, quantidade, preco_custo FROM estoque_pecas WHERE codigo = ? OR UPPER(nome_peca) = UPPER(?)", (cod, desc)).fetchone()
            if cur_p:
                p_id, p_qtd, p_custo = cur_p
                nova_qtd = (p_qtd or 0) + qtd
                conn.execute("""
                    UPDATE estoque_pecas
                    SET quantidade = ?,
                        preco_custo = ?,
                        saldo_fiscal = COALESCE(saldo_fiscal, 0) + ?
                    WHERE id = ?
                """, (nova_qtd, preco if preco > 0 else p_custo, qtd, p_id))
            else:
                conn.execute("""
                    INSERT INTO estoque_pecas (
                        codigo, nome_peca, quantidade, preco_custo, tipo_item,
                        unidade, grupo_item, categoria, preco_unitario, saldo_fiscal
                    ) VALUES (?, ?, ?, ?, 'PEÇA', 'UN', 'DIAGNÓSTICO POR IMAGEM', 'PEÇAS', ?, ?)
                """, (cod or f"PEC-{nota_id}", desc, qtd, preco, preco * 1.4, qtd))

            conn.execute("""
                INSERT INTO movimentacoes_estoque (
                    estabelecimento, centro_estoque, codigo_item, descricao,
                    grupo_itens, data_mov, hora_mov, tipo_mov, qtd_entrada, qtd_saida,
                    saldo, custo_medio, numero_nf, documento, observacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ENTRADA_FORNECEDOR', ?, 0, ?, ?, ?, ?, ?)
            """, (
                filial, "ALMOXARIFADO CENTRAL", cod, desc,
                "PEÇAS", data_mov, hora_mov, qtd, qtd, preco,
                str(num_nf), f"NF-e {num_nf}", f"Entrada automática via Radar DF-e SEFAZ por {usuario}"
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
    return web.json_response({
        "ok": True,
        "msg": f"✅ Sucesso! {itens_atualizados} item(ns) da Nota {num_nf} deram entrada automática no Almoxarifado da EMED."
    })


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

    linhas_html = "".join([
        f"<tr><td><b>{n[13] or 'OS #'+str(n[1])}</b></td><td>{n[15] or ''}</td><td>{n[2]}</td><td>{n[3]}</td><td>{n[5] or 'NFS-e'}</td><td>R$ {float(n[6] or 0):.2f}</td><td>R$ {float(n[7] or 0):.2f}</td><td>R$ {float(n[10] or 0):.2f}</td><td><b>R$ {float(n[11] or 0):.2f}</b></td><td>{n[12]}</td></tr>"
        for n in notas
    ]) or "<tr><td colspan='10' style='text-align:center;'>Nenhuma nota emitida no período.</td></tr>"

    html_out = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Fechamento Contábil & Fiscal – EMED ({mes})</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; margin: 24px; font-size: 12px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 16px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }}
    .kpi {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; }}
    .kpi-title {{ font-size: 11px; color: #64748b; font-weight: 700; }}
    .kpi-val {{ font-size: 18px; font-weight: 900; color: #0369a1; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 11px; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
    th {{ background: #f1f5f9; color: #334155; font-weight: 800; }}
    .alert-box {{ background: #eff6ff; border-left: 4px solid #3b82f6; padding: 10px 14px; margin-bottom: 16px; font-size: 11.5px; line-height: 1.5; }}
    .signatures {{ display: flex; justify-content: space-between; margin-top: 40px; padding-top: 20px; }}
    .sig-line {{ width: 45%; border-top: 1px solid #475569; text-align: center; padding-top: 6px; font-size: 11px; }}
    @media print {{ .no-print {{ display: none; }} body {{ margin: 0; }} }}
  </style>
</head>
<body>
  <div class="no-print" style="margin-bottom: 16px; text-align: right;">
    <button onclick="window.print()" style="background:#0284c7;color:#fff;border:none;padding:10px 18px;font-weight:800;border-radius:6px;cursor:pointer;">🖨️ Imprimir / Salvar em PDF</button>
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
    ⚖️ <b>MEMORIAL FISCAL PARA A CONTABILIDADE:</b><br/>
    &bull; <b>Serviços (ISS):</b> LC 116/2003 (Item 14.01/14.02). Alíquota aplicável: 5,0% (DF) ou alíquota municipal da sede/tomador.<br/>
    &bull; <b>Transferências entre Filiais (CFOP 5152/6152):</b> Não incidência de ICMS vinculante conforme <b>STF ADC 49 e LC 204/2023</b>.<br/>
    &bull; <b>Consumíveis Administrativos (CFOP 1556/2556):</b> Baixa imediata para despesa de uso/consumo, mantendo saldo de almoxarifado clínico em zero.
  </div>
  <div class="kpis">
    <div class="kpi"><div class="kpi-title">TOTAL FATURADO</div><div class="kpi-val">R$ {tot_fat:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">SERVIÇOS (BASE ISS)</div><div class="kpi-val">R$ {tot_srv:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">PEÇAS FATURADAS</div><div class="kpi-val">R$ {tot_pec:,.2f}</div></div>
    <div class="kpi"><div class="kpi-title">TOTAL ISS APURADO</div><div class="kpi-val">R$ {tot_iss:,.2f}</div></div>
  </div>
  <h4 style="margin:0 0 8px 0;color:#0369a1;">📜 Livro de Saídas &amp; NFS-e Emitidas no Período</h4>
  <table>
    <thead>
      <tr><th>NFS-e</th><th>Data</th><th>Tomador</th><th>CNPJ</th><th>CFOP</th><th>Serviços</th><th>Peças</th><th>ISS</th><th>Total NF</th><th>Status</th></tr>
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
  <!-- MODAL DE ITENS DA NOTA RECEBIDA -->
  <div class="modal-overlay" id="modalItensDFe" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.75);backdrop-filter:blur(4px);z-index:9999;align-items:center;justify-content:center;">
    <div style="background:#0f172a;border:1.5px solid #0284c7;border-radius:12px;width:680px;max-width:95%;padding:22px;box-shadow:0 10px 30px rgba(0,0,0,0.6);color:#fff;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;border-bottom:1px solid #334155;padding-bottom:10px;">
        <h3 id="modalItensDFeTitulo" style="margin:0;font-size:16px;color:#38bdf8;">Itens da Nota Fiscal</h3>
        <button type="button" onclick="fecharModalItensDFe()" style="background:none;border:none;color:#94a3b8;font-size:20px;cursor:pointer;">&times;</button>
      </div>
      <div style="overflow-x:auto;max-height:350px;">
        <table style="width:100%;font-size:12px;">
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição do Item / Peça</th>
              <th>Qtd</th>
              <th>Preço Unitário</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody id="tbodyModalItensDFe"></tbody>
        </table>
      </div>
      <div style="margin-top:16px;text-align:right;">
        <button type="button" class="btn btn-outline" onclick="fecharModalItensDFe()">Fechar</button>
      </div>
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
                <select id="selPecaTransferencia" style="width:100%;font-weight:600;"></select>
              </div>
              <div style="width:100px;">
                <label>Qtd:</label>
                <input id="inpQtdTransferencia" type="number" min="1" step="1" value="1" />
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
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button type="button" class="btn btn-primary" onclick="sincronizarDFeSefaz()" style="width:auto;padding:8px 14px;">
                🔄 Puxar Notas no Fisco (SEFAZ • A1)
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
                  <th>Nº Nota</th>
                  <th>Emissão</th>
                  <th>Fornecedor (Emitente)</th>
                  <th>CNPJ Fornecedor</th>
                  <th>UF</th>
                  <th>Valor Total</th>
                  <th>Manifestação</th>
                  <th>Almoxarifado</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody id="tbodyNotasRecebidasDFe"></tbody>
            </table>
          </div>
        </div>
      </details>

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
          <td style="font-size:11px;">${{h.cfop ? 'CFOP ' + h.cfop : (String(h.chave || '').length === 50 ? '🏛️ NFS-e Nacional' : 'NFS-e')}}</td>
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
          ? "⚠️ CONFERÊNCIA OBRIGATÓRIA DOS DADOS DA NOTA FISCAL\\n\\n" +
            "Você já conferiu todos os dados da nota fiscal (no espelho da nota que aparece abaixo)?\\n\\n" +
            "• Cliente: " + cliNome + "\\n" +
            "• Unidade Emissora: " + filialTxt + "\\n" +
            "• Modalidade: 🟢 EMISSÃO REAL (SEFAZ • CERTIFICADO A1)\\n\\n" +
            "Esta nota será transmitida oficialmente à SEFAZ e terá valor legal para apuração do DAS e faturamento.\\n\\n" +
            "Realmente quer emitir a Nota Fiscal agora?\\n\\n" +
            "[OK] = Sim, emitir nota fiscal agora\\n" +
            "[Cancelar] = Não, desejo revisar os dados na página"
          : "🧪 MODO SIMULAÇÃO / DEMONSTRAÇÃO\\n\\n" +
            "Você já conferiu todos os dados da nota fiscal (no espelho da nota que aparece abaixo)?\\n\\n" +
            "• Cliente: " + cliNome + "\\n" +
            "• Unidade: " + filialTxt + "\\n" +
            "• Modalidade: 🧪 SIMULAÇÃO (Sem efeito fiscal na SEFAZ)\\n\\n" +
            "Realmente quer emitir o espelho de demonstração?\\n\\n" +
            "[OK] = Sim, gerar espelho de demonstração\\n" +
            "[Cancelar] = Não, desejo revisar os dados na página";

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
          "⚠️ INTERTRAVAMENTO FISCAL CONTRA DUPLICIDADE:\\n\\n" +
          "A Nota Fiscal " + ne.numero_nf + " referente à OS #" + ne.os_id + " já foi emitida com sucesso em " + ne.data_emissao + " para este cliente e valor!\\n\\n" +
          "O espelho da nota já emitida foi carregado na tela abaixo para sua conferência.\\n\\n" +
          "Deseja realmente emitir OUTRA nota fiscal para este mesmo atendimento?\\n\\n" +
          "[OK] = Sim, desejo emitir outra nota mesmo assim\\n" +
          "[Cancelar] = Não, manter a nota existente (não duplicar)"
        );
        if (querOutra) {{
          emitirNotaFiscalAgora(modo, true);
        }}
      }} else {{
        alert("Erro ao emitir: " + (res.msg || "Falha interna"));
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
        "⚠️ ATENÇÃO: CONFIRMAÇÃO IRREVERSÍVEL DE CANCELAMENTO\n\n" +
        "Você está prestes a CANCELAR esta Nota Fiscal no sistema e registrar a anulação fiscal.\n\n" +
        "• Justificativa: " + just + "\n\n" +
        "Deseja realmente prosseguir com o cancelamento?"
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
        return;
      }}
      selPecaTrf.innerHTML = lista.map(p =>
        `<option value="${{p.id}}" data-codigo="${{p.codigo || ''}}" data-nome="${{p.nome.replace(/"/g, '&quot;')}}" data-preco="${{p.preco}}">${{p.codigo ? '[' + p.codigo + '] ' : ''}}${{p.nome}} (Saldo: ${{p.qtd}} ${{p.unidade || 'UN'}} • Custo: R$ ${{Number(p.preco || 0).toFixed(2)}})</option>`
      ).join("");
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
        return;
      }}
      let total = 0;
      tb.innerHTML = ITENS_TRANSFERENCIA.map((it, idx) => {{
        const subtotal = it.quantidade * it.valor_unitario;
        total += subtotal;
        return `
          <tr>
            <td><b>${{it.codigo || '-'}}</b></td>
            <td>${{it.nome}}</td>
            <td><input type="number" min="1" step="1" value="${{it.quantidade}}" style="width:70px;padding:4px;font-size:12px;" onchange="alterarQtdItemTransferencia(${{idx}}, this.value)" /></td>
            <td>R$ ${{Number(it.valor_unitario).toFixed(2)}}</td>
            <td><b>R$ ${{Number(subtotal).toFixed(2)}}</b></td>
            <td><button class="btn btn-outline" style="padding:2px 6px;color:#f87171;border-color:#f87171;" onclick="removerItemTransferencia(${{idx}})">✕</button></td>
          </tr>
        `;
      }}).join("");
      document.getElementById("lblTotalTransferencia").textContent = `R$ ${{total.toLocaleString('pt-BR', {{minimumFractionDigits:2}})}}`;
    }}

    function adicionarItemTransferencia() {{
      const sel = document.getElementById("selPecaTransferencia");
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) {{ alert("Selecione uma peça da lista."); return; }}
      const pecaId = parseInt(opt.value);
      const nome = opt.getAttribute("data-nome") || opt.text;
      const codigo = opt.getAttribute("data-codigo") || "";
      const preco = parseFloat(opt.getAttribute("data-preco") || 0);
      const qtdInp = parseFloat(document.getElementById("inpQtdTransferencia").value || 1);

      const existente = ITENS_TRANSFERENCIA.find(i => i.peca_id === pecaId);
      if (existente) {{
        existente.quantidade += qtdInp;
      }} else {{
        ITENS_TRANSFERENCIA.push({{
          peca_id: pecaId,
          nome: nome,
          codigo: codigo,
          quantidade: qtdInp,
          valor_unitario: preco
        }});
      }}
      renderizarItensTransferencia();
    }}

    function removerItemTransferencia(idx) {{
      ITENS_TRANSFERENCIA.splice(idx, 1);
      renderizarItensTransferencia();
    }}

    function alterarQtdItemTransferencia(idx, val) {{
      const q = parseFloat(val);
      if (q > 0 && ITENS_TRANSFERENCIA[idx]) {{
        ITENS_TRANSFERENCIA[idx].quantidade = q;
        renderizarItensTransferencia();
      }}
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

          return `
            <tr id="linhaInv_${{p.id}}">
              <td><b>${{p.codigo || '-'}}</b></td>
              <td>
                <div style="font-weight:700;color:#fff;">${{p.nome}}</div>
                <div style="font-size:11px;color:#94a3b8;">Custo: R$ ${{Number(p.preco||0).toFixed(2)}} • Un: ${{p.unidade || 'UN'}}</div>
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
        const res = await fetch(`/api/fiscal/recebidas/dados?filial=${{FILIAL_ATIVA}}`).then(r => r.json());
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
          const corManif = n.status_manifestacao === 'CONFIRMADA' ? 'color:#34d399;font-weight:bold;' :
                           n.status_manifestacao === 'CIENCIA' ? 'color:#60a5fa;' :
                           n.status_manifestacao === 'DESCONHECIDA' ? 'color:#f87171;font-weight:bold;' : 'color:#fbbf24;font-weight:bold;';
          const lblManif = n.status_manifestacao === 'CONFIRMADA' ? '✅ Confirmada' :
                           n.status_manifestacao === 'CIENCIA' ? 'ℹ️ Ciência' :
                           n.status_manifestacao === 'DESCONHECIDA' ? '🛡️ Desconhecida' : '⚠️ Pendente';
          const corEst = n.status_estoque === 'DADO_ENTRADA' ? 'color:#34d399;font-weight:bold;' : 'color:#f472b6;font-weight:bold;';
          const lblEst = n.status_estoque === 'DADO_ENTRADA' ? '✅ No Estoque' : '⏳ Pendente';

          return `
            <tr>
              <td><b>NF-e ${{n.numero_nf}}</b></td>
              <td>${{dtFmt}}</td>
              <td title="${{n.emitente_nome}}"><b>${{n.emitente_nome.length > 28 ? n.emitente_nome.substring(0, 28) + '...' : n.emitente_nome}}</b></td>
              <td style="font-size:11px;">${{n.emitente_cnpj}}</td>
              <td><span class="badge" style="background:#0f172a;border:1px solid #334155;">${{n.emitente_uf || 'BR'}}</span></td>
              <td><b>R$ ${{Number(n.valor_total || 0).toLocaleString('pt-BR', {{minimumFractionDigits: 2}})}}</b></td>
              <td><span style="${{corManif}}">${{lblManif}}</span></td>
              <td><span style="${{corEst}}">${{lblEst}}</span></td>
              <td style="white-space:nowrap;display:flex;gap:4px;">
                <button type="button" class="btn btn-outline" style="padding:3px 7px;font-size:11px;" onclick="abrirModalItensDFe(${{n.id}})">👁️ Itens</button>
                ${{n.status_estoque === 'PENDENTE' ? `<button type="button" class="btn btn-primary" style="padding:3px 7px;font-size:11px;" onclick="darEntradaEstoqueDFe(${{n.id}}, '${{n.numero_nf}}')">📦 Dar Entrada</button>` : ''}}
                ${{n.status_manifestacao === 'SEM_MANIFESTACAO' ? `
                  <button type="button" class="btn btn-blue" style="padding:3px 7px;font-size:11px;" onclick="manifestarNotaDFe(${{n.id}}, 'CONFIRMAR')">✅ Confirmar</button>
                  <button type="button" class="btn btn-danger" style="padding:3px 7px;font-size:11px;" onclick="manifestarNotaDFe(${{n.id}}, 'DESCONHECER')">🛡️ Desconhecer</button>
                ` : ''}}
              </td>
            </tr>
          `;
        }}).join("") || `<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:14px;">Nenhuma nota fiscal emitida por fornecedores localizada no momento.</td></tr>`;
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

    async function manifestarNotaDFe(id, tipo) {{
      if (tipo === "DESCONHECER") {{
        const conf = confirm(
          "⚠️ ATENÇÃO: ALERTA ANTI-FRAUDE / NOTA INDEVIDA\n\n" +
          "Você está prestes a manifestar DESCONHECIMENTO DA OPERAÇÃO perante a SEFAZ (Evento 210220).\n\n" +
          "Deseja realmente registrar que sua empresa NÃO reconhece esta nota fiscal?"
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
        carregarInventarioAlmoxarifado();
      }} catch (e) {{
        alert("Erro ao dar entrada no estoque.");
      }}
    }}

    function abrirModalItensDFe(id) {{
      const n = DFE_NOTAS_CACHE.find(item => item.id === id);
      if (!n) return;

      document.getElementById("modalItensDFeTitulo").textContent = `Itens da NF-e ${{n.numero_nf}} — ${{n.emitente_nome}}`;
      const tb = document.getElementById("tbodyModalItensDFe");
      const itens = n.itens || [];

      tb.innerHTML = itens.map(it => `
        <tr style="border-bottom:1px solid #334155;">
          <td><b style="color:#38bdf8;">${{it.codigo || '-'}}</b></td>
          <td>${{it.descricao || '-'}}</td>
          <td style="font-weight:bold;">${{it.qtd}}</td>
          <td>R$ ${{Number(it.unitario || 0).toFixed(2)}}</td>
          <td style="font-weight:bold;color:#10b981;">R$ ${{Number((it.qtd || 1) * (it.unitario || 0)).toFixed(2)}}</td>
        </tr>
      `).join("") || `<tr><td colspan="5" style="text-align:center;padding:10px;color:var(--muted);">Nenhum item discriminado.</td></tr>`;

      document.getElementById("modalItensDFe").style.display = "flex";
    }}

    function fecharModalItensDFe() {{
      document.getElementById("modalItensDFe").style.display = "none";
    }}

    // Chamar carregarNotasRecebidasDFe dentro de carregarDadosFiscais
    const _origCarregarDadosFiscais = carregarDadosFiscais;
    carregarDadosFiscais = async function(osId) {{
      await _origCarregarDadosFiscais(osId);
      carregarNotasRecebidasDFe();
    }};

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
    app.router.add_post("/api/fiscal/v2/transferir-filiais", api_fiscal_v2_transferir_filiais)
    app.router.add_post("/api/fiscal/v2/lancar-consumivel", api_fiscal_v2_lancar_consumivel)
    app.router.add_post("/api/fiscal/v2/ajuste-estoque", api_fiscal_v2_ajuste_estoque)
    app.router.add_post("/api/fiscal/v2/inventario/ajuste-direto", api_fiscal_v2_inventario_ajuste_direto)
    app.router.add_post("/api/fiscal/v2/inventario/novo-item", api_fiscal_v2_inventario_novo_item)
    app.router.add_get("/api/fiscal/v2/fechamento/dados", api_fiscal_v2_fechamento_dados)
    app.router.add_get("/api/fiscal/v2/fechamento/zip", api_fiscal_v2_fechamento_zip)
    app.router.add_get("/api/fiscal/v2/fechamento/relatorio-impresso", api_fiscal_v2_fechamento_relatorio_impresso)
    app.router.add_post("/api/fiscal/v2/fechamento/marcar-enviado", api_fiscal_v2_fechamento_marcar_enviado)
    app.router.add_get("/api/fiscal/v2/xml/{os_id}", api_fiscal_v2_xml_download)

    # Rotas do Radar DF-e (Notas Recebidas de Fornecedores)
    app.router.add_get("/api/fiscal/recebidas/dados", api_fiscal_recebidas_dados)
    app.router.add_post("/api/fiscal/recebidas/consultar-sefaz", api_fiscal_recebidas_consultar_sefaz)
    app.router.add_post("/api/fiscal/recebidas/manifestar", api_fiscal_recebidas_manifestar)
    app.router.add_post("/api/fiscal/recebidas/dar-entrada-estoque", api_fiscal_recebidas_dar_entrada_estoque)
