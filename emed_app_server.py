# -*- coding: utf-8 -*-
"""
Servidor Nativo & API REST do Aplicativo Oficial EMED (PWA Técnico & Gestor)
=============================================================================
Conecta-se diretamente ao banco SQLite (emed.db) e Excel (base_clientes.xlsx),
oferecendo duas interfaces dedicadas de altíssima velocidade (Zero Rerun):
1. App do Técnico de Campo (100% Offline-First, Checklist, Fotos, Assinatura Touch e PDF 1 Página)
2. App do Gestor Completo (Central de Comando, Despacho, TV do Laboratório, Almoxarifado, PIX e Triagem)
"""

import os
import sys
import json
import base64
import sqlite3
import datetime
import pandas as pd
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from emed_core import (
    limpar_texto,
    limpar_float,
    obter_id_os,
    get_db_connection,
    aplicar_peca_os_idempotente,
    obter_kit_por_servico,
    SUGESTOES_SEPARACAO_POR_ATIVIDADE,
    acionar_separacao_automatica_almoxarifado,
    registrar_aplicacao_definitiva_e_fluxo_cobranca,
    registrar_peca_em_teste_observacao,
    atualizar_status_solicitacao_peca,
    obter_resumo_alarmes_calibracao,
    calcular_status_calibracao,
    salvar_rascunho_provisorio,
    obter_rascunho_provisorio,
    limpar_rascunho_provisorio,
    obter_configuracao,
    salvar_configuracao,
    gerar_sugestao_relatorio_clinico,
    obter_checklist_acoes_sugeridas,
    TEMPLATES_RELATORIO_TECNICO,
    salvar_dataframe_transacional,
)
from emed_services import (
    DB_NAME,
    CAMINHO_EXCEL,
    init_db,
    converter_html_para_pdf_bytes,
    calcular_duracao_os,
)
from emed_views.chamados_os import (
    _gerar_html_os_formatada,
    _extrair_pendencia_limpa,
    _limpar_telefone_exibicao,
    _formatar_data_br,
)
from emed_views.emedonline import _detectar_modalidade, _obter_perguntas_triagem_dinamica
from emed_views.conciliacao_pix import (
    inicializar_tabela_pix,
    gerar_payload_pix,
    gerar_qr_code_pix_base64,
    liquidar_pagamento_pix,
)
from emed_views.pesquisa_satisfacao import (
    inicializar_tabela_satisfacao,
    obter_url_google_review,
    URL_GOOGLE_REVIEW_OFICIAL,
)

STATIC_DIR = os.path.join(BASE_DIR, "emed_pwa_static")


def _carregar_df_direto() -> pd.DataFrame:
    """Lê a tabela clientes_equipamentos diretamente do SQLite sem depender do contexto do Streamlit."""
    init_db(DB_NAME, CAMINHO_EXCEL)
    with get_db_connection(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM clientes_equipamentos", conn)
    return df


def _salvar_df_direto(df: pd.DataFrame) -> bool:
    """Persiste o DataFrame de forma transacional no SQLite e na planilha Excel."""
    backup_excel = os.path.join(BASE_DIR, "base_clientes_backup.xlsx")
    return salvar_dataframe_transacional(df, DB_NAME, CAMINHO_EXCEL, backup_excel)


def _montar_equipa_direto() -> dict:
    equipa = {}
    try:
        with get_db_connection(DB_NAME) as conn:
            df_t = pd.read_sql_query("SELECT * FROM tecnicos", conn)
        for _, r in df_t.iterrows():
            nome = limpar_texto(r.get("nome"), "").upper()
            if nome:
                equipa[nome] = {
                    "tel": limpar_texto(r.get("telefone"), ""),
                    "esp": limpar_texto(r.get("especialidade"), "GERAL"),
                    "assinatura": f"{nome} - {limpar_texto(r.get('registro_cft'), 'TÉCNICO CFT')}",
                }
    except Exception:
        pass
    return equipa


async def handle_index(request: web.Request) -> web.Response:
    caminho_html = os.path.join(STATIC_DIR, "index.html")
    with open(caminho_html, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return web.Response(text=conteudo, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def handle_manifest(request: web.Request) -> web.Response:
    caminho = os.path.join(STATIC_DIR, "manifest.json")
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return web.Response(text=conteudo, content_type="application/manifest+json")


async def handle_sw(request: web.Request) -> web.Response:
    caminho = os.path.join(STATIC_DIR, "sw.js")
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read()
    return web.Response(text=conteudo, content_type="application/javascript", headers={"Cache-Control": "no-cache"})


async def handle_logo(request: web.Request) -> web.Response:
    caminho_logo = os.path.join(BASE_DIR, "emed1.jpg")
    if os.path.exists(caminho_logo):
        with open(caminho_logo, "rb") as f:
            return web.Response(body=f.read(), content_type="image/jpeg")
    return web.Response(status=404)


async def api_bootstrap(request: web.Request) -> web.Response:
    """Retorna todo o estado atualizado do servidor EMED para o App do Técnico e App do Gestor."""
    inicializar_tabela_pix(DB_NAME)
    inicializar_tabela_satisfacao(DB_NAME)
    df = _carregar_df_direto()

    ordens = []
    qtd_ativas = 0
    qtd_concluidas = 0
    qtd_obs = 0
    qtd_pend_urg = 0
    qtd_pend_prog = 0
    fat_total = 0.0

    for idx, row in df.iterrows():
        os_id = str(obter_id_os(idx, row))
        st_os = limpar_texto(row.get("status"), "ATIVO").upper()
        if st_os == "CONCLUÍDO":
            qtd_concluidas += 1
        elif "OBSERVA" in st_os:
            qtd_obs += 1
        else:
            qtd_ativas += 1

        val_os = limpar_float(row.get("valor_os"), 0.0)
        if st_os == "CONCLUÍDO":
            fat_total += val_os

        pend_limpa = _extrair_pendencia_limpa(row)
        raw_pend = limpar_texto(row.get("pendencias"), "").upper()
        inst_nec = limpar_texto(row.get("instrumento_necessario"), "").upper()
        tem_pend_real = (
            "NENHUMA PENDÊNCIA" not in pend_limpa.upper()
            and pend_limpa.strip() != ""
            and pend_limpa.strip() != "-"
        )
        prioridade_pend = "NORMAL"
        if tem_pend_real:
            if "URGENTE" in inst_nec or "URGÊNCIA" in raw_pend or "PARADO" in limpar_texto(row.get("condicao_final"), "").upper():
                prioridade_pend = "URGENTE"
                qtd_pend_urg += 1
            else:
                prioridade_pend = "PROGRAMADA"
                qtd_pend_prog += 1

        f_ant = limpar_texto(row.get("foto_evidencia"), "")
        f_dep = limpar_texto(row.get("foto_depois"), "")
        rascunho_salvo, dt_rasc = obter_rascunho_provisorio(DB_NAME, os_id)

        ordens.append({
            "id": os_id,
            "idx": int(idx),
            "cliente": limpar_texto(row.get("cliente"), "N/D"),
            "cnpj": limpar_texto(row.get("cnpj"), "N/D"),
            "endereco": limpar_texto(row.get("endereco"), ""),
            "cidade": limpar_texto(row.get("cidade"), "FORTALEZA"),
            "estado": limpar_texto(row.get("estado"), "CE"),
            "email": limpar_texto(row.get("email"), ""),
            "whatsapp": _limpar_telefone_exibicao(row.get("whatsapp") or row.get("contato_responsavel")),
            "responsavel_hospital": limpar_texto(row.get("responsavel_hospital"), ""),
            "equipamento": limpar_texto(row.get("equipamento"), "N/D"),
            "tipo_servico": limpar_texto(row.get("tipo_servico"), "MANUTENÇÃO"),
            "etapa_preventiva": limpar_texto(row.get("etapa_preventiva"), "GERAL"),
            "tecnico_responsavel": limpar_texto(row.get("tecnico_responsavel"), "A DEFINIR"),
            "tecnico_auxiliar": limpar_texto(row.get("tecnico_auxiliar"), ""),
            "data_agendamento": limpar_texto(row.get("data_agendamento"), ""),
            "data_br": _formatar_data_br(row.get("data_agendamento")),
            "status": st_os,
            "checkin_hora": limpar_texto(row.get("checkin_hora"), ""),
            "checkout_hora": limpar_texto(row.get("checkout_hora"), ""),
            "tempo_atendimento": limpar_texto(row.get("tempo_atendimento"), ""),
            "defeito_relatado": limpar_texto(row.get("defeito_relatado"), ""),
            "problemas_encontrados": limpar_texto(row.get("problemas_encontrados"), ""),
            "causa_raiz": limpar_texto(row.get("causa_raiz"), "DESGASTE NATURAL DE COMPONENTE / PEÇA"),
            "servico_executado": limpar_texto(row.get("servico_executado"), ""),
            "checklist_pop": limpar_texto(row.get("checklist_pop"), ""),
            "parametros_medidos": limpar_texto(row.get("parametros_medidos"), ""),
            "observacoes_gerais": limpar_texto(row.get("observacoes_gerais"), ""),
            "pendencias_limpa": pend_limpa,
            "tem_pendencia_real": tem_pend_real,
            "prioridade_pendencia": prioridade_pend,
            "instrumento_necessario": limpar_texto(row.get("instrumento_necessario"), ""),
            "condicao_inicial": limpar_texto(row.get("condicao_inicial"), "OPERACIONAL"),
            "condicao_final": limpar_texto(row.get("condicao_final"), "LIBERADO PARA USO NORMAL"),
            "condicao_pagamento": limpar_texto(row.get("condicao_pagamento"), "FATURAMENTO BOLETO BANCÁRIO (VALOR INTEGRAL)"),
            "valor_os": val_os,
            "assinatura_cliente": limpar_texto(row.get("assinatura_cliente"), ""),
            "assinatura_tecnico": limpar_texto(row.get("assinatura_tecnico"), ""),
            "peca_baixada_ref": limpar_texto(row.get("peca_baixada_ref"), ""),
            "tem_foto_antes": bool(f_ant and os.path.exists(f_ant)),
            "tem_foto_depois": bool(f_dep and os.path.exists(f_dep)),
            "rascunho_servidor": rascunho_salvo,
            "data_rascunho_servidor": dt_rasc,
        })

    # Técnicos, Estoque, Solicitações, Notas Fiscais
    tecnicos = []
    estoque = []
    solicitacoes = []
    notas = []
    clientes_unicos = sorted(list(set(o["cliente"] for o in ordens if o["cliente"] and o["cliente"] != "N/D")))

    with get_db_connection(DB_NAME) as conn:
        try:
            df_tec = pd.read_sql_query("SELECT * FROM tecnicos", conn)
            for _, r in df_tec.iterrows():
                tecnicos.append({
                    "nome": limpar_texto(r.get("nome"), "").upper(),
                    "especialidade": limpar_texto(r.get("especialidade"), "GERAL"),
                    "telefone": limpar_texto(r.get("telefone"), ""),
                    "registro_cft": limpar_texto(r.get("registro_cft"), "CFT"),
                })
        except Exception:
            pass

        try:
            df_est = pd.read_sql_query("SELECT * FROM estoque_pecas", conn)
            for _, r in df_est.iterrows():
                st_cal = calcular_status_calibracao(limpar_texto(r.get("data_validade_calibracao"), ""))
                estoque.append({
                    "codigo": limpar_texto(r.get("codigo"), ""),
                    "nome_peca": limpar_texto(r.get("nome_peca"), ""),
                    "categoria": limpar_texto(r.get("categoria"), "PEÇA"),
                    "quantidade": int(limpar_float(r.get("quantidade"), 0)),
                    "estoque_minimo": int(limpar_float(r.get("estoque_minimo"), 1)),
                    "preco_unitario": limpar_float(r.get("preco_unitario"), 0.0),
                    "localizacao": limpar_texto(r.get("localizacao"), ""),
                    "validade_calibracao": limpar_texto(r.get("data_validade_calibracao"), ""),
                    "badge_calibracao": st_cal["badge_txt"],
                    "cor_calibracao": st_cal["badge_cor"],
                })
        except Exception:
            pass

        try:
            df_sol = pd.read_sql_query("SELECT * FROM solicitacoes_pecas ORDER BY id DESC LIMIT 50", conn)
            for _, r in df_sol.iterrows():
                solicitacoes.append({
                    "id": int(r.get("id", 0)),
                    "tecnico": limpar_texto(r.get("tecnico"), ""),
                    "destino_cliente": limpar_texto(r.get("destino_cliente"), ""),
                    "itens_solicitados": limpar_texto(r.get("itens_solicitados"), ""),
                    "instrumentos_solicitados": limpar_texto(r.get("instrumentos_solicitados"), ""),
                    "status_pedido": limpar_texto(r.get("status_pedido"), "PENDENTE"),
                    "data_pedido": limpar_texto(r.get("data_pedido"), ""),
                })
        except Exception:
            pass

        try:
            df_nf = pd.read_sql_query("SELECT * FROM notas_fiscais ORDER BY id DESC LIMIT 40", conn)
            for _, r in df_nf.iterrows():
                notas.append({
                    "id": int(r.get("id", 0)),
                    "os_id": limpar_texto(r.get("os_id"), ""),
                    "cliente": limpar_texto(r.get("cliente"), ""),
                    "tipo_nota": limpar_texto(r.get("tipo_nota"), "NFS-e"),
                    "descricao": limpar_texto(r.get("descricao"), ""),
                    "valor_total": limpar_float(r.get("valor_total"), 0.0),
                    "status_fiscal": limpar_texto(r.get("status_fiscal"), ""),
                    "data_emissao": limpar_texto(r.get("data_emissao"), ""),
                })
        except Exception:
            pass

    alarmes_cal = obter_resumo_alarmes_calibracao(DB_NAME)
    google_url = obter_url_google_review(DB_NAME)

    payload = {
        "ok": True,
        "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "kpis": {
            "ativas": qtd_ativas,
            "concluidas": qtd_concluidas,
            "observacao": qtd_obs,
            "pendencias_urgentes": qtd_pend_urg,
            "pendencias_programadas": qtd_pend_prog,
            "faturamento_total": fat_total,
            "alarmes_calibracao": alarmes_cal.get("total_alarmes_urgentes", 0),
        },
        "ordens": ordens,
        "clientes_unicos": clientes_unicos,
        "tecnicos": tecnicos,
        "estoque": estoque,
        "solicitacoes_almox": solicitacoes,
        "notas_fiscais": notas,
        "alarmes_calibracao": alarmes_cal,
        "templates_relatorio": TEMPLATES_RELATORIO_TECNICO,
        "kits_servico": SUGESTOES_SEPARACAO_POR_ATIVIDADE,
        "google_review_url": google_url,
    }
    return web.json_response(payload)


async def api_checklist(request: web.Request) -> web.Response:
    equip = request.query.get("equipamento", "")
    defeito = request.query.get("defeito", "")
    acoes = obter_checklist_acoes_sugeridas(equip, defeito)
    sugestao_ia = gerar_sugestao_relatorio_clinico(equip, defeito)
    return web.json_response({
        "ok": True,
        "acoes": acoes,
        "sugestao_ia": sugestao_ia,
    })


async def api_triagem(request: web.Request) -> web.Response:
    equip = request.query.get("equipamento", "")
    defeito = request.query.get("defeito", "")
    modalidade = _detectar_modalidade(equip, defeito)
    triagem = _obter_perguntas_triagem_dinamica(modalidade, defeito, equip)
    return web.json_response({
        "ok": True,
        "modalidade": modalidade,
        "triagem": triagem,
    })


async def api_salvar_rascunho(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    dados = body.get("dados", {})
    if not os_id:
        return web.json_response({"ok": False, "msg": "os_id ausente"}, status=400)
    ok, msg = salvar_rascunho_provisorio(DB_NAME, os_id, dados)
    return web.json_response({"ok": ok, "msg": msg})


async def api_checkin(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    df = _carregar_df_direto()
    agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    encontrou = False
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            df.at[idx, "checkin_hora"] = agora_str
            df.at[idx, "confirmado"] = "SIM"
            encontrou = True
            break

    if not encontrou:
        return web.json_response({"ok": False, "msg": f"OS #{os_id} não encontrada."}, status=404)

    _salvar_df_direto(df)
    return web.json_response({"ok": True, "checkin_hora": agora_str, "msg": f"📍 Check-in registrado na OS #{os_id} às {agora_str}!"})


def _salvar_base64_em_arquivo(b64_str: str, prefixo: str, os_id: str) -> str:
    """Decodifica uma imagem data:image/...;base64 e salva em uploads_os/."""
    if not b64_str or not str(b64_str).startswith("data:image"):
        return ""
    try:
        header, encoded = str(b64_str).split(",", 1)
        ext = "png" if "png" in header.lower() else "jpg"
        pasta = os.path.join(BASE_DIR, "uploads_os")
        os.makedirs(pasta, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho = os.path.join(pasta, f"{prefixo}_OS{os_id}_{ts}.{ext}")
        with open(caminho, "wb") as f:
            f.write(base64.b64decode(encoded))
        return caminho
    except Exception:
        return ""


async def api_salvar_os(request: web.Request) -> web.Response:
    """Grava ou conclui uma Ordem de Serviço a partir do App do Técnico ou App do Gestor."""
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    acao = str(body.get("acao", "CONCLUIR")).upper()  # CONCLUIR, OBSERVACAO, SALVAR_ABERTA

    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()

    idx_alvo = None
    row_os = None
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            idx_alvo = idx
            row_os = row
            break

    if idx_alvo is None:
        return web.json_response({"ok": False, "msg": f"OS #{os_id} não localizada no banco."}, status=404)

    agora_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    cin_atual = limpar_texto(row_os.get("checkin_hora"), "") or agora_str
    duracao_str = calcular_duracao_os(cin_atual, agora_str)

    tec_resp = limpar_texto(body.get("tecnico_responsavel"), limpar_texto(row_os.get("tecnico_responsavel"), "ANTONIO")).upper()
    tec_aux = limpar_texto(body.get("tecnico_auxiliar"), limpar_texto(row_os.get("tecnico_auxiliar"), "")).upper()
    tipo_srv = limpar_texto(body.get("tipo_servico"), limpar_texto(row_os.get("tipo_servico"), "CORRETIVA")).upper()
    etapa_prev = limpar_texto(body.get("etapa_preventiva"), limpar_texto(row_os.get("etapa_preventiva"), "GERAL")).upper()
    defeito_rel = limpar_texto(body.get("defeito_relatado"), limpar_texto(row_os.get("defeito_relatado"), "")).upper()
    prob_enc = limpar_texto(body.get("problemas_encontrados"), limpar_texto(row_os.get("problemas_encontrados"), "")).upper()
    causa_raiz = limpar_texto(body.get("causa_raiz"), limpar_texto(row_os.get("causa_raiz"), "DESGASTE NATURAL")).upper()
    srv_exec = limpar_texto(body.get("servico_executado"), limpar_texto(row_os.get("servico_executado"), "")).upper()
    if not srv_exec:
        srv_exec = "MANUTENÇÃO E REVISÃO TÉCNICA EXECUTADA CONFORME PROTOCOLO EMED."

    chk_pop = limpar_texto(body.get("checklist_pop"), limpar_texto(row_os.get("checklist_pop"), "POP PADRÃO CONCLUÍDO")).upper()
    param_med = limpar_texto(body.get("parametros_medidos"), limpar_texto(row_os.get("parametros_medidos"), "-")).upper()
    obs_gerais = limpar_texto(body.get("observacoes_gerais"), limpar_texto(row_os.get("observacoes_gerais"), "")).upper()
    cond_final = limpar_texto(body.get("condicao_final"), "LIBERADO PARA USO NORMAL").upper()
    inst_prox = limpar_texto(body.get("instrumento_necessario"), "").upper()
    prioridade_pend = limpar_texto(body.get("prioridade_pendencia"), "NENHUMA").upper()

    peca_sel = limpar_texto(body.get("peca_selecionada"), "NENHUMA PEÇA")
    qtd_peca = int(limpar_float(body.get("qtd_peca"), 1))
    valor_os = limpar_float(body.get("valor_os"), limpar_float(row_os.get("valor_os"), 0.0))
    opcao_fat = limpar_texto(body.get("condicao_pagamento"), "FATURAMENTO BOLETO BANCÁRIO (VALOR INTEGRAL)")
    if "PIX" in opcao_fat.upper() and valor_os > 0 and "VALOR FINAL:" not in opcao_fat.upper():
        val_calc = round(valor_os * 0.90, 2)
    else:
        val_calc = valor_os
    resumo_pag = opcao_fat if "VALOR FINAL" in opcao_fat.upper() else f"{opcao_fat} — VALOR FINAL: R$ {val_calc:,.2f}"

    ass_cli_nome = limpar_texto(body.get("assinatura_cliente"), limpar_texto(row_os.get("responsavel_hospital"), "RESPONSÁVEL LOCAL")).upper()
    ass_cli_img = limpar_texto(body.get("assinatura_cliente_img"), limpar_texto(row_os.get("assinatura_cliente_img"), ""))
    ass_tec = equipa.get(tec_resp, {}).get("assinatura", f"{tec_resp} - CFT")

    # Aplicação de peça no estoque (se selecionada)
    ref_ant = limpar_texto(row_os.get("peca_baixada_ref"), "")
    ok_p, tag_peca, nova_ref_peca = aplicar_peca_os_idempotente(DB_NAME, peca_sel, qtd_peca, ref_ant)
    if ok_p and tag_peca and tag_peca not in srv_exec:
        srv_exec = f"{srv_exec} | {tag_peca}"

    # Fotos Antes e Depois (se enviadas em Base64)
    foto_ant_b64 = body.get("foto_antes_b64", "")
    foto_dep_b64 = body.get("foto_depois_b64", "")
    if foto_ant_b64:
        cam_ant = _salvar_base64_em_arquivo(foto_ant_b64, "ANTES", os_id)
        if cam_ant:
            df.at[idx_alvo, "foto_evidencia"] = cam_ant
    if foto_dep_b64:
        cam_dep = _salvar_base64_em_arquivo(foto_dep_b64, "DEPOIS", os_id)
        if cam_dep:
            df.at[idx_alvo, "foto_depois"] = cam_dep

    # Atualiza campos na linha da OS
    if body.get("endereco"):
        df.at[idx_alvo, "endereco"] = limpar_texto(body.get("endereco")).upper()
    if body.get("email"):
        df.at[idx_alvo, "email"] = limpar_texto(body.get("email"))
    if body.get("whatsapp"):
        df.at[idx_alvo, "whatsapp"] = _limpar_telefone_exibicao(body.get("whatsapp"))

    df.at[idx_alvo, "tecnico_responsavel"] = tec_resp
    df.at[idx_alvo, "tecnico_auxiliar"] = tec_aux
    df.at[idx_alvo, "tipo_servico"] = tipo_srv
    df.at[idx_alvo, "etapa_preventiva"] = etapa_prev
    df.at[idx_alvo, "checkin_hora"] = cin_atual
    df.at[idx_alvo, "checkout_hora"] = agora_str
    df.at[idx_alvo, "tempo_atendimento"] = duracao_str
    df.at[idx_alvo, "defeito_relatado"] = defeito_rel
    df.at[idx_alvo, "problemas_encontrados"] = prob_enc
    df.at[idx_alvo, "causa_raiz"] = causa_raiz
    df.at[idx_alvo, "servico_executado"] = srv_exec
    df.at[idx_alvo, "checklist_pop"] = chk_pop
    df.at[idx_alvo, "parametros_medidos"] = param_med
    df.at[idx_alvo, "observacoes_gerais"] = obs_gerais
    df.at[idx_alvo, "condicao_final"] = cond_final
    df.at[idx_alvo, "condicao_pagamento"] = resumo_pag
    df.at[idx_alvo, "valor_os"] = float(val_calc)
    df.at[idx_alvo, "assinatura_cliente"] = ass_cli_nome
    df.at[idx_alvo, "assinatura_cliente_img"] = ass_cli_img
    df.at[idx_alvo, "assinatura_tecnico"] = ass_tec
    df.at[idx_alvo, "peca_baixada_ref"] = nova_ref_peca

    tem_pend_ativa = bool(inst_prox and inst_prox not in ["N/D", "NENHUM", "NENHUMA", "-"] and prioridade_pend != "NENHUMA")
    prio_almox = "URGENTE" if "URG" in prioridade_pend else "PROGRAMADA"

    if tem_pend_ativa:
        df.at[idx_alvo, "instrumento_necessario"] = f"[{prio_almox}] {inst_prox}"
        df.at[idx_alvo, "pendencias"] = f"[CONCLUÍDO COM PENDÊNCIA: {prio_almox}] {inst_prox}"
        try:
            with get_db_connection(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO solicitacoes_pecas
                    (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    tec_resp,
                    limpar_texto(row_os.get("cliente"), ""),
                    f"DEMANDA DE CAMPO [{prio_almox}]: {inst_prox}",
                    f"Equipamento: {limpar_texto(row_os.get('equipamento'), '')} | OS #{os_id}",
                    f"A SEPARAR ({prio_almox} - DEMANDA DE CAMPO)",
                    agora_str,
                ))
                conn.commit()
        except Exception:
            pass
    else:
        df.at[idx_alvo, "instrumento_necessario"] = ""
        df.at[idx_alvo, "pendencias"] = f"[CONCLUÍDO - {etapa_prev}] Sem pendências restantes."

    if acao == "OBSERVACAO":
        df.at[idx_alvo, "status"] = "EM OBSERVAÇÃO"
        if peca_sel and peca_sel != "NENHUMA PEÇA":
            try:
                registrar_peca_em_teste_observacao(
                    DB_NAME, int(os_id), limpar_texto(row_os.get("cliente"), ""),
                    limpar_texto(row_os.get("equipamento"), ""), tec_resp, peca_sel, qtd_peca, 3, "Validar estabilidade operacional"
                )
            except Exception:
                pass
        msg_final = f"🔬 OS #{os_id} colocada EM OBSERVAÇÃO com sucesso!"
    elif acao == "SALVAR_ABERTA":
        df.at[idx_alvo, "status"] = "ATIVO"
        msg_final = f"💾 Dados da OS #{os_id} salvos no servidor (OS mantida ATIVA)!"
    else:
        df.at[idx_alvo, "status"] = "CONCLUÍDO"
        try:
            registrar_aplicacao_definitiva_e_fluxo_cobranca(
                DB_NAME, int(os_id), limpar_texto(row_os.get("cliente"), ""),
                limpar_texto(row_os.get("equipamento"), ""), tec_resp, peca_sel, qtd_peca, float(val_calc),
                condicao_pagamento=resumo_pag,
                tipo_contrato=limpar_texto(row_os.get("tipo_contrato"), "CONTRATO"),
            )
        except Exception:
            pass
        limpar_rascunho_provisorio(DB_NAME, os_id)
        msg_final = f"🏁 OS #{os_id} CONCLUÍDA e salva com sucesso no servidor EMED!"

    _salvar_df_direto(df)
    return web.json_response({"ok": True, "os_id": os_id, "status": df.at[idx_alvo, "status"], "msg": msg_final})


async def api_nova_os(request: web.Request) -> web.Response:
    """Cria uma nova Ordem de Serviço (via Gestor ou Portal de Triagem) e aciona separação no Almoxarifado."""
    body = await request.json()
    cliente = limpar_texto(body.get("cliente"), "").upper()
    equipamento = limpar_texto(body.get("equipamento"), "").upper()
    defeito = limpar_texto(body.get("defeito_relatado"), "").upper()
    if not cliente or not equipamento:
        return web.json_response({"ok": False, "msg": "Informe o Cliente e o Equipamento."}, status=400)

    tipo_srv = limpar_texto(body.get("tipo_servico"), "CORRETIVA").upper()
    tec_resp = limpar_texto(body.get("tecnico_responsavel"), "ANTONIO").upper()
    tec_aux = limpar_texto(body.get("tecnico_auxiliar"), "NENHUM (INDIVIDUAL)").upper()
    data_ag = limpar_texto(body.get("data_agendamento"), datetime.date.today().strftime("%Y-%m-%d"))
    resp_hosp = limpar_texto(body.get("responsavel_hospital"), "").upper()
    contato = _limpar_telefone_exibicao(body.get("contato_responsavel") or body.get("whatsapp"))
    endereco = limpar_texto(body.get("endereco"), "UNIDADE HOSPITALAR").upper()
    cidade = limpar_texto(body.get("cidade"), "FORTALEZA").upper()
    respostas_triagem = limpar_texto(body.get("respostas_triagem"), "")

    kit_sug = obter_kit_por_servico(tipo_srv, defeito)
    df = _carregar_df_direto()
    novo_id = int(df["id"].max() + 1) if ("id" in df.columns and not df.empty and pd.notna(df["id"].max())) else (len(df) + 1)

    nova_linha = {
        "id": novo_id,
        "cliente": cliente,
        "cidade": cidade,
        "estado": "CE",
        "equipamento": equipamento,
        "endereco": endereco,
        "tipo_servico": tipo_srv,
        "data_agendamento": data_ag,
        "tecnico_responsavel": tec_resp,
        "tecnico_auxiliar": tec_aux,
        "responsavel_hospital": resp_hosp,
        "contato_responsavel": contato if contato != "N/D" else "",
        "whatsapp": contato if contato != "N/D" else "",
        "confirmado": "SIM",
        "pendencias": f"[CHAMADO ABERTO] {defeito}",
        "status": "ATIVO",
        "defeito_relatado": defeito,
        "pre_atendimento": respostas_triagem,
        "instrumento_necessario": kit_sug["nome"],
        "condicao_inicial": limpar_texto(body.get("condicao_inicial"), "OPERANDO COM FALHA").upper(),
        "condicao_final": "LIBERADO PARA USO NORMAL",
        "valor_os": 0.0,
    }
    df_novo = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
    _salvar_df_direto(df_novo)

    try:
        acionar_separacao_automatica_almoxarifado(
            DB_NAME, tec_resp, f"{cliente} ({equipamento}) [OS #{novo_id}]", tipo_srv, defeito
        )
    except Exception:
        pass

    return web.json_response({
        "ok": True,
        "os_id": str(novo_id),
        "kit_acionado": kit_sug["nome"],
        "msg": f"✅ Ordem de Serviço #{novo_id} emitida! Almoxarifado acionado com {kit_sug['nome']}.",
    })


async def api_reabrir_os(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    df = _carregar_df_direto()
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            df.at[idx, "status"] = "ATIVO"
            _salvar_df_direto(df)
            return web.json_response({"ok": True, "msg": f"🔓 OS #{os_id} reaberta e devolvida para a fila de OS Ativas!"})
    return web.json_response({"ok": False, "msg": "OS não encontrada."}, status=404)


async def api_almox_status(request: web.Request) -> web.Response:
    body = await request.json()
    id_ped = int(body.get("id", 0))
    novo_status = limpar_texto(body.get("novo_status"), "SEPARADO / ENTREGUE AO TÉCNICO")
    ok, msg = atualizar_status_solicitacao_peca(DB_NAME, id_ped, novo_status)
    return web.json_response({"ok": ok, "msg": msg})


async def api_pix_gerar(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = str(body.get("os_id", "AVULSO")).strip()
    valor = limpar_float(body.get("valor"), 0.0)
    chave_pix = limpar_texto(body.get("chave_pix"), "03611974000108")
    if valor <= 0:
        return web.json_response({"ok": False, "msg": "Informe um valor maior que R$ 0,00 para gerar o QR Code PIX."}, status=400)

    payload_emv = gerar_payload_pix(chave_pix, "EMED ELETROMEDICINA", "FORTALEZA", valor, f"OS{os_id}")
    qr_b64 = gerar_qr_code_pix_base64(payload_emv)
    return web.json_response({
        "ok": True,
        "payload_emv": payload_emv,
        "qr_base64": qr_b64,
        "valor": valor,
        "os_id": os_id,
    })


async def api_pix_liquidar(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    txid = f"PIX_APP_{os_id}_{datetime.datetime.now().strftime('%H%M%S')}"
    ok, msg = liquidar_pagamento_pix(DB_NAME, os_id, txid, metodo="APP_GESTOR_EMED")
    return web.json_response({"ok": ok, "msg": msg})


async def api_config(request: web.Request) -> web.Response:
    body = await request.json()
    url_g = limpar_texto(body.get("google_review_url"), "")
    if url_g:
        salvar_configuracao(DB_NAME, "google_review_url", url_g)
    return web.json_response({"ok": True, "google_review_url": obter_url_google_review(DB_NAME), "msg": "✅ Configuração salva no servidor EMED!"})


async def api_pdf_os(request: web.Request) -> web.Response:
    os_id = request.match_info.get("os_id", "").strip()
    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            html_os = _gerar_html_os_formatada(os_id, row, equipa)
            pdf_bytes = converter_html_para_pdf_bytes(html_os)
            cli_slug = limpar_texto(row.get("cliente"), "EMED").replace(" ", "_")
            nome_arq = f"Laudo_Tecnico_OS_{os_id}_{cli_slug}.pdf"
            return web.Response(
                body=pdf_bytes,
                content_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{nome_arq}"'},
            )
    return web.Response(text=f"OS #{os_id} não encontrada", status=404)


async def api_html_os(request: web.Request) -> web.Response:
    os_id = request.match_info.get("os_id", "").strip()
    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            html_os = _gerar_html_os_formatada(os_id, row, equipa)
            return web.Response(text=html_os, content_type="text/html")
    return web.Response(text=f"OS #{os_id} não encontrada", status=404)


def criar_app() -> web.Application:
    app = web.Application(client_max_size=25 * 1024 * 1024)  # Suporta upload de fotos de alta resolução (até 25MB)
    app.router.add_get("/", handle_index)
    app.router.add_get("/manifest.json", handle_manifest)
    app.router.add_get("/sw.js", handle_sw)
    app.router.add_get("/api/logo", handle_logo)
    app.router.add_get("/api/bootstrap", api_bootstrap)
    app.router.add_get("/api/checklist", api_checklist)
    app.router.add_get("/api/triagem", api_triagem)
    app.router.add_post("/api/rascunho", api_salvar_rascunho)
    app.router.add_post("/api/checkin", api_checkin)
    app.router.add_post("/api/salvar-os", api_salvar_os)
    app.router.add_post("/api/nova-os", api_nova_os)
    app.router.add_post("/api/reabrir-os", api_reabrir_os)
    app.router.add_post("/api/almoxarifado/status", api_almox_status)
    app.router.add_post("/api/pix/gerar", api_pix_gerar)
    app.router.add_post("/api/pix/liquidar", api_pix_liquidar)
    app.router.add_post("/api/config", api_config)
    app.router.add_get("/api/pdf/{os_id}", api_pdf_os)
    app.router.add_get("/api/html/{os_id}", api_html_os)
    return app


if __name__ == "__main__":
    porta = int(os.environ.get("EMED_APP_PORT", 8502))
    print(f"🚀 Iniciando Servidor do Aplicativo Oficial EMED (Técnico & Gestor) na porta {porta}...")
    web.run_app(criar_app(), host="0.0.0.0", port=porta)
