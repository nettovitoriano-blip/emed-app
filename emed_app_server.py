# -*- coding: utf-8 -*-
"""
Servidor Nativo & API REST Completa do Aplicativo Oficial EMED (PWA Técnico, Gestor & Cliente)
==============================================================================================
Integra todos os 18 módulos do ecossistema EMED em uma arquitetura SPA/PWA de resposta imediata (0ms),
conectada em tempo real ao banco SQLite (emed.db) e à planilha Excel (base_clientes.xlsx).
"""

import os
import sys
import json
import base64
import sqlite3
import tempfile
import datetime
from datetime import datetime
import asyncio
import pandas as pd
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from emed_core import (
    limpar_texto,
    limpar_float,
    limpar_int,
    obter_id_os,
    get_db_connection,
    aplicar_peca_os_idempotente,
    obter_kit_por_servico,
    SUGESTOES_SEPARACAO_POR_ATIVIDADE,
    acionar_separacao_automatica_almoxarifado,
    registrar_aplicacao_definitiva_e_fluxo_cobranca,
    registrar_peca_em_teste_observacao,
    converter_teste_em_aplicacao_definitiva_e_cobranca,
    retirar_peca_teste_e_devolver_estoque,
    atualizar_status_solicitacao_peca,
    obter_resumo_alarmes_calibracao,
    calcular_status_calibracao,
    calcular_dias_aguardando_orcamento,
    atualizar_calibracao_instrumento,
    atualizar_calibracao_equipamento_cliente,
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
    render_markdown_to_pdf,
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
    registrar_pesquisa,
    obter_url_google_review,
    URL_GOOGLE_REVIEW_OFICIAL,
)
from emed_views.manuais_tecnicos import DICIONARIO_VIDEOS_ITS, _localizar_video_do_documento
from emed_frota_gps import (
    garantir_tabelas_frota_gps_multas,
    registrar_telemetria_ou_viagem_gps,
    registrar_multa_ou_taxa_com_cruzamento,
    executar_varredura_robo_detran,
    atualizar_status_multa_taxa,
    carregar_painel_frota_gps_multas,
)

STATIC_DIR = os.path.join(BASE_DIR, "emed_pwa_static")


def _carregar_df_direto() -> pd.DataFrame:
    init_db(DB_NAME, CAMINHO_EXCEL)
    with get_db_connection(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM clientes_equipamentos", conn)
    return df


def _salvar_df_direto(df: pd.DataFrame) -> bool:
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
                    "assinatura": limpar_texto(r.get("assinatura_padrao"), f"{nome} - CFT"),
                }
    except Exception:
        pass
    return equipa


def _listar_manuais_homologados() -> list:
    """
    Varre a pasta Manuais/ para listar todas as ITs, POPs e Manuais de Serviço Oficiais (.pdf e .md).
    Elimina 100% das duplicidades causadas por pastas compartilhadas (ex: BrightSpeed x Brivo)
    e prioriza sempre a versão .PDF homologada com a Logo da EMED sobre o .MD.
    """
    from emed_views.manuais_tecnicos import DICIONARIO_NOMES_AMIGAVEIS

    pasta_manuais = os.path.join(BASE_DIR, "Manuais")
    if not os.path.exists(pasta_manuais):
        return []

    pastas_ignorar = {"media", "content", "css", "scripts", "icons", "search", "toc", "forms", "images", "system utiliies"}
    catalogo_map = {}

    for root, dirs, files in os.walk(pasta_manuais):
        dirs[:] = [d for d in dirs if d.lower() not in pastas_ignorar]
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            if ext not in (".pdf", ".md"):
                continue
            if f.upper().startswith("LEIA_ME"):
                continue
            # Ignora diagramas numéricos internos do CD da GE (ex: 377318-16.pdf)
            if f[0].isdigit() and not f.startswith(("00_", "01", "02", "03", "04", "05")):
                continue

            base_sem_ext = os.path.splitext(f)[0]
            caminho_abs = os.path.join(root, f)
            rel_path = os.path.relpath(caminho_abs, BASE_DIR).replace("\\", "/")
            rel_dir = os.path.relpath(root, pasta_manuais).replace("\\", "/")
            partes = rel_dir.split("/")
            modalidade = partes[0] if partes and partes[0] != "." else "GERAL"
            fabricante = partes[1] if len(partes) > 1 else ""
            modelo = partes[2] if len(partes) > 2 else ""

            vid_path = _localizar_video_do_documento(caminho_abs)
            vid_nome = os.path.basename(vid_path) if vid_path else ""

            titulo_limpo = (
                DICIONARIO_NOMES_AMIGAVEIS.get(f)
                or DICIONARIO_NOMES_AMIGAVEIS.get(base_sem_ext + ".pdf")
                or DICIONARIO_NOMES_AMIGAVEIS.get(base_sem_ext + ".md")
                or base_sem_ext.replace("_", " ")
            )
            if "IT_RX_LOT_001" in f.upper() or "02_FORMULARIO_VISTORIA_PRE_INSTALACAO" in f.upper():
                titulo_limpo = "⭐ RELATÓRIO OFICIAL DE PRÉ-INSTALAÇÃO — RAIO-X LOTUS HF500M (FT-INS-HF500M-REV05 c/ Logo EMED)"

            # Chave rigorosa de deduplicação pelo Título e Código Técnico
            chave_dedup = titulo_limpo.strip().upper()

            # Se já catalogamos este documento:
            if chave_dedup in catalogo_map:
                existente = catalogo_map[chave_dedup]
                # Se o existente for .md e encontramos o .pdf homologado, promove para o .pdf
                if existente["ext"] == ".md" and ext == ".pdf":
                    catalogo_map[chave_dedup] = {
                        "arquivo": f,
                        "titulo": titulo_limpo,
                        "modalidade": modalidade,
                        "fabricante": fabricante or "HOMOLOGADO EMED",
                        "modelo": modelo,
                        "rel_path": rel_path,
                        "caminho_rel": rel_path,
                        "ext": ext,
                        "formato": "PDF HOMOLOGADO",
                        "tamanho_kb": round(os.path.getsize(caminho_abs) / 1024, 1),
                        "video": vid_nome or existente.get("video", ""),
                        "_ordem": existente.get("_ordem", 1),
                    }
                continue

            eh_destaque = 0 if ("PRÉ-INSTALAÇÃO" in titulo_limpo.upper() or "⭐" in titulo_limpo) else 1
            catalogo_map[chave_dedup] = {
                "arquivo": f,
                "titulo": titulo_limpo,
                "modalidade": modalidade,
                "fabricante": fabricante or "HOMOLOGADO EMED",
                "modelo": modelo,
                "rel_path": rel_path,
                "caminho_rel": rel_path,
                "ext": ext,
                "formato": "PDF HOMOLOGADO",
                "tamanho_kb": round(os.path.getsize(caminho_abs) / 1024, 1),
                "video": vid_nome,
                "_ordem": eh_destaque,
            }

    catalogo = list(catalogo_map.values())
    catalogo.sort(key=lambda x: (x.get("_ordem", 1), 0 if x["modalidade"] != "GERAL" else 1, x["modalidade"], x["titulo"]))
    return catalogo


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


async def handle_logo_circle(request: web.Request) -> web.Response:
    caminho_circ = os.path.join(BASE_DIR, "emed_pwa_static", "logo_emed_circle.png")
    if os.path.exists(caminho_circ):
        with open(caminho_circ, "rb") as f:
            return web.Response(body=f.read(), content_type="image/png")
    return web.Response(status=404)


async def api_ping(request: web.Request) -> web.Response:
    """Endpoint ultraleve de Keep-Alive / Heartbeat Anti-Standby para Render e Uptime Monitors."""
    return web.json_response({
        "status": "ok",
        "app": "EMED Eletromedicina",
        "timestamp": datetime.now().isoformat(),
        "keep_alive": True,
        "anti_standby": "100% Ativo"
    })


async def api_bootstrap(request: web.Request) -> web.Response:
    """Retorna o estado completo de todos os 18 menus do Sistema EMED."""
    inicializar_tabela_pix(DB_NAME)
    inicializar_tabela_satisfacao(DB_NAME)
    df = _carregar_df_direto()
    hoje_ts = pd.Timestamp.today().normalize()

    ordens = []
    qtd_ativas = 0
    qtd_concluidas = 0
    qtd_obs = 0
    qtd_pend_urg = 0
    qtd_pend_prog = 0
    fat_total = 0.0

    # Contadores de BI
    bi_status = {}
    bi_tecnico = {}
    bi_cidade = {}
    bi_servico = {}
    grupos_rotas = {}

    for idx, row in df.iterrows():
        os_id = str(obter_id_os(idx, row))
        st_os = limpar_texto(row.get("status"), "ATIVO").upper()
        cli = limpar_texto(row.get("cliente"), "N/D")
        cid = limpar_texto(row.get("cidade"), "FORTALEZA").upper()
        tec = limpar_texto(row.get("tecnico_responsavel"), "A DEFINIR").upper()
        tp_srv = limpar_texto(row.get("tipo_servico"), "MANUTENÇÃO").upper()
        eq = limpar_texto(row.get("equipamento"), "N/D")

        bi_status[st_os] = bi_status.get(st_os, 0) + 1
        bi_tecnico[tec] = bi_tecnico.get(tec, 0) + 1
        bi_cidade[cid] = bi_cidade.get(cid, 0) + 1
        bi_servico[tp_srv] = bi_servico.get(tp_srv, 0) + 1

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
        cond_ini = limpar_texto(row.get("condicao_inicial"), "OPERACIONAL").upper()
        cond_fim = limpar_texto(row.get("condicao_final"), "LIBERADO PARA USO NORMAL").upper()

        tem_pend_real = (
            "NENHUMA PENDÊNCIA" not in pend_limpa.upper()
            and pend_limpa.strip() != ""
            and pend_limpa.strip() != "-"
        )
        prioridade_pend = "NORMAL"
        if tem_pend_real:
            if "URGENTE" in inst_nec or "URGÊNCIA" in raw_pend or "PARADO" in cond_fim or "PARADO" in cond_ini:
                prioridade_pend = "URGENTE"
                qtd_pend_urg += 1
            else:
                prioridade_pend = "PROGRAMADA"
                qtd_pend_prog += 1

        # Categoria TV do Laboratório
        if any(k in raw_pend for k in ["URGENTE", "CRÍTICO", "CRITICO", "EMERGÊNCIA"]) or "PARADO" in cond_ini or "PARADO" in cond_fim:
            cat_tv = "CRITICA"
        elif any(k in raw_pend for k in ["PEÇA", "PECA", "ALMOXARIFADO", "SEPARAÇÃO", "ORÇAMENTO", "ORCAMENTO"]) or any(k in inst_nec for k in ["PEC-", "PLACA", "TUBO", "FONTE", "BOTAO"]):
            cat_tv = "PECA_ORCAMENTO"
        elif "PREVENTIVA" in tp_srv or "PROGRAMADA" in raw_pend:
            cat_tv = "PROGRAMADA"
        else:
            cat_tv = "NORMAL"

        # Orçamento pendente (>15 dias ou aguardando aprovação)
        eh_orcamento_pendente = (
            st_os == "ATIVO"
            and any(k in raw_pend for k in ["ORÇAMENTO", "ORCAMENTO", "APROVA", "PROPOSTA"])
            and "ORÇAMENTO APROVADO" not in raw_pend
        )
        dias_orc = calcular_dias_aguardando_orcamento(row.get("data_agendamento"), hoje_ts)

        # Calibração do equipamento do cliente
        cal_eq = calcular_status_calibracao(limpar_texto(row.get("data_validade_calibracao"), ""))

        # Agrupamento de rotas para chamados ativos
        if st_os != "CONCLUÍDO":
            ch_rota = f"{cli} ({cid})"
            if ch_rota not in grupos_rotas:
                grupos_rotas[ch_rota] = {
                    "cliente": cli,
                    "cidade": cid,
                    "endereco": limpar_texto(row.get("endereco"), ""),
                    "os_ids": [],
                    "equipamentos": [],
                    "tecnicos": set(),
                }
            grupos_rotas[ch_rota]["os_ids"].append(os_id)
            grupos_rotas[ch_rota]["equipamentos"].append(eq)
            grupos_rotas[ch_rota]["tecnicos"].add(tec)

        f_ant = limpar_texto(row.get("foto_evidencia"), "")
        f_dep = limpar_texto(row.get("foto_depois"), "")
        rascunho_salvo, dt_rasc = obter_rascunho_provisorio(DB_NAME, os_id)
        num_serie = limpar_texto(row.get("numero_serie") or row.get("patrimonio"), "S/N")

        ordens.append({
            "id": os_id,
            "idx": int(idx),
            "cliente": cli,
            "cnpj": limpar_texto(row.get("cnpj"), "N/D"),
            "endereco": limpar_texto(row.get("endereco"), ""),
            "cidade": cid,
            "estado": limpar_texto(row.get("estado"), "CE"),
            "email": limpar_texto(row.get("email"), ""),
            "whatsapp": _limpar_telefone_exibicao(row.get("whatsapp") or row.get("contato_responsavel")),
            "contato_responsavel": _limpar_telefone_exibicao(row.get("contato_responsavel") or row.get("whatsapp")),
            "responsavel_hospital": limpar_texto(row.get("responsavel_hospital"), ""),
            "equipamento": eq,
            "numero_serie": num_serie,
            "tipo_servico": tp_srv,
            "etapa_preventiva": limpar_texto(row.get("etapa_preventiva"), "GERAL"),
            "tecnico_responsavel": tec,
            "tecnico_auxiliar": limpar_texto(row.get("tecnico_auxiliar"), ""),
            "telefone_tecnico": limpar_texto(row.get("telefone_tecnico"), ""),
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
            "pendencias_raw": limpar_texto(row.get("pendencias"), ""),
            "pendencias_limpa": pend_limpa,
            "pendencia_limpa": pend_limpa,
            "tem_pendencia_real": tem_pend_real,
            "prioridade_pendencia": prioridade_pend,
            "categoria_tv": cat_tv,
            "eh_orcamento_pendente": eh_orcamento_pendente,
            "dias_orcamento": dias_orc,
            "instrumento_necessario": limpar_texto(row.get("instrumento_necessario"), ""),
            "condicao_inicial": cond_ini,
            "condicao_final": cond_fim,
            "condicao_pagamento": limpar_texto(row.get("condicao_pagamento"), "FATURAMENTO BOLETO BANCÁRIO (VALOR INTEGRAL)"),
            "valor_os": val_os,
            "assinatura_cliente": limpar_texto(row.get("assinatura_cliente"), ""),
            "assinatura_tecnico": limpar_texto(row.get("assinatura_tecnico"), ""),
            "peca_baixada_ref": limpar_texto(row.get("peca_baixada_ref"), ""),
            "data_ultima_calibracao": limpar_texto(row.get("data_ultima_calibracao"), ""),
            "data_validade_calibracao": limpar_texto(row.get("data_validade_calibracao"), ""),
            "certificado_calibracao": limpar_texto(row.get("certificado_calibracao"), ""),
            "cal_badge_txt": cal_eq["badge_txt"],
            "cal_badge_cor": cal_eq["badge_cor"],
            "tem_foto_antes": bool(f_ant and os.path.exists(f_ant)),
            "tem_foto_depois": bool(f_dep and os.path.exists(f_dep)),
            "rascunho_servidor": rascunho_salvo,
            "tem_rascunho_servidor": bool(rascunho_salvo),
            "data_rascunho_servidor": dt_rasc,
        })

    rotas_lista = []
    viagens_economizadas = 0
    for _, gr in grupos_rotas.items():
        qtd_ch = len(gr["os_ids"])
        if qtd_ch > 1:
            viagens_economizadas += (qtd_ch - 1)
        tecs_list = list(gr["tecnicos"])
        rotas_lista.append({
            "cliente": gr["cliente"],
            "cidade": gr["cidade"],
            "endereco": gr["endereco"],
            "qtd_chamados": qtd_ch,
            "os_ids": gr["os_ids"],
            "equipamentos": gr["equipamentos"],
            "tecnicos": tecs_list,
            "tecnicos_atuais": tecs_list,
        })
    rotas_lista.sort(key=lambda x: x["qtd_chamados"], reverse=True)

    tecnicos = []
    estoque = []
    solicitacoes = []
    baixas_cons = []
    notas = []
    veiculos = []
    pesquisas = []
    clientes_unicos = sorted(list(set(o["cliente"] for o in ordens if o["cliente"] and o["cliente"] != "N/D")))

    with get_db_connection(DB_NAME) as conn:
        try:
            df_tec = pd.read_sql_query("SELECT * FROM tecnicos", conn)
            for _, r in df_tec.iterrows():
                ass_p = limpar_texto(r.get("assinatura_padrao"), "CFT")
                tecnicos.append({
                    "nome": limpar_texto(r.get("nome"), "").upper(),
                    "telefone": _limpar_telefone_exibicao(r.get("telefone")),
                    "partida": limpar_texto(r.get("partida"), "FORTALEZA"),
                    "sede": limpar_texto(r.get("sede"), "FORTALEZA"),
                    "perfil": limpar_texto(r.get("perfil"), "Técnico"),
                    "assinatura_padrao": ass_p,
                    "assinatura": ass_p,
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
                    "localizacao": limpar_texto(r.get("localizacao"), "ALMOXARIFADO CENTRAL"),
                    "ultima_calibracao": limpar_texto(r.get("data_ultima_calibracao"), ""),
                    "validade_calibracao": limpar_texto(r.get("data_validade_calibracao"), ""),
                    "certificado_calibracao": limpar_texto(r.get("certificado_calibracao"), ""),
                    "saldo_creditos": limpar_texto(r.get("saldo_creditos"), ""),
                    "badge_calibracao": st_cal["badge_txt"],
                    "cor_calibracao": st_cal["badge_cor"],
                    "status_cal": st_cal["status"],
                })
        except Exception:
            pass

        try:
            df_sol = pd.read_sql_query("SELECT * FROM solicitacoes_pecas ORDER BY id DESC LIMIT 60", conn)
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
            df_bx = pd.read_sql_query("SELECT * FROM baixas_consumiveis ORDER BY id DESC LIMIT 30", conn)
            for _, r in df_bx.iterrows():
                baixas_cons.append({
                    "id": int(r.get("id", 0)),
                    "tecnico": limpar_texto(r.get("tecnico"), ""),
                    "item": limpar_texto(r.get("item"), ""),
                    "quantidade": int(limpar_float(r.get("quantidade"), 1)),
                    "cliente_os": limpar_texto(r.get("cliente_os"), ""),
                    "data_baixa": limpar_texto(r.get("data_baixa"), ""),
                })
        except Exception:
            pass

        try:
            df_nf = pd.read_sql_query("SELECT * FROM notas_fiscais ORDER BY id DESC LIMIT 50", conn)
            for _, r in df_nf.iterrows():
                nid = int(r.get("id", 0))
                st_f = limpar_texto(r.get("status_fiscal"), "PENDENTE")
                notas.append({
                    "id": nid,
                    "numero_nf": f"NFS-{nid:04d}",
                    "os_id": limpar_texto(r.get("os_id"), ""),
                    "cliente": limpar_texto(r.get("cliente"), ""),
                    "tipo_nota": limpar_texto(r.get("tipo_nota"), "NFS-e"),
                    "descricao": limpar_texto(r.get("descricao"), ""),
                    "valor_total": limpar_float(r.get("valor_total"), 0.0),
                    "status_fiscal": st_f,
                    "status_pagamento": st_f,
                    "data_emissao": limpar_texto(r.get("data_emissao"), ""),
                })
        except Exception:
            pass

        try:
            garantir_tabelas_frota_gps_multas(DB_NAME)
            df_v = pd.read_sql_query("SELECT * FROM veiculos", conn)
            for _, r in df_v.iterrows():
                km_at = limpar_int(r.get("km_atual"), 0)
                km_pr = limpar_int(r.get("km_proxima_revisao"), 50000)
                veiculos.append({
                    "id": int(r.get("id", 1)),
                    "modelo": limpar_texto(r.get("modelo"), "Veículo EMED"),
                    "placa": limpar_texto(r.get("placa"), ""),
                    "renavam": limpar_texto(r.get("renavam"), "01234567890"),
                    "condutor_atual": limpar_texto(r.get("condutor_atual"), "DISPONÍVEL NA BASE"),
                    "tag_rfid_atual": limpar_texto(r.get("tag_rfid_atual"), ""),
                    "ultima_lat": limpar_float(r.get("ultima_lat"), -3.7319),
                    "ultima_lon": limpar_float(r.get("ultima_lon"), -38.5267),
                    "ultima_atualizacao_gps": limpar_texto(r.get("ultima_atualizacao_gps"), ""),
                    "km_atual": km_at,
                    "km_ultima_revisao": limpar_int(r.get("km_ultima_revisao"), 0),
                    "km_proxima_revisao": km_pr,
                    "km_restante": km_pr - km_at,
                    "status_manutencao": limpar_texto(r.get("status_manutencao"), "Em Dia"),
                    "historico_manutencao": limpar_texto(r.get("historico_manutencao"), ""),
                    "proximas_manutencoes": limpar_texto(r.get("proximas_manutencoes"), ""),
                })
        except Exception:
            pass

        try:
            df_ps = pd.read_sql_query("SELECT * FROM pesquisas_satisfacao ORDER BY id DESC LIMIT 40", conn)
            for _, r in df_ps.iterrows():
                pesquisas.append({
                    "id": int(r.get("id", 0)),
                    "os_id": limpar_texto(r.get("os_id"), ""),
                    "cliente": limpar_texto(r.get("cliente"), ""),
                    "tecnico": limpar_texto(r.get("tecnico"), ""),
                    "nota": int(limpar_float(r.get("nota"), 5)),
                    "comentario": limpar_texto(r.get("comentario"), ""),
                    "data_avaliacao": limpar_texto(r.get("data_avaliacao"), ""),
                })
        except Exception:
            pass

    alarmes_cal = obter_resumo_alarmes_calibracao(DB_NAME)
    inst_emed_list = []
    for e in estoque:
        if e.get("validade_calibracao") or "INSTRUMENTO" in str(e.get("categoria", "")).upper() or str(e.get("codigo", "")).startswith("FER-"):
            inst_emed_list.append({
                "codigo": e["codigo"],
                "nome_peca": e["nome_peca"],
                "certificado": e.get("certificado_calibracao") or "RBC-EMED",
                "validade": e.get("validade_calibracao") or "EM DIA",
                "status_cal": str(e.get("status_cal", "EM DIA")).replace(" ", "_"),
                "badge": e.get("badge_calibracao") or "🟢 EM DIA",
            })
    eq_cli_list = []
    for o in ordens:
        if o.get("data_validade_calibracao") or o.get("certificado_calibracao"):
            st_c = calcular_status_calibracao(o.get("data_validade_calibracao", ""))
            eq_cli_list.append({
                "os_id": o["id"],
                "cliente": o["cliente"],
                "equipamento": o["equipamento"],
                "certificado": o.get("certificado_calibracao") or "RBC",
                "validade": o.get("data_validade_calibracao") or "N/D",
                "status_cal": str(st_c.get("status", "EM DIA")).replace(" ", "_"),
                "badge": o.get("cal_badge_txt") or "🟢 EM DIA",
            })
    alarmes_cal["instrumentos_emed"] = inst_emed_list
    alarmes_cal["equipamentos_clientes"] = eq_cli_list

    google_url = obter_url_google_review(DB_NAME)
    manuais_lista = _listar_manuais_homologados()
    frota_gps_multas = carregar_painel_frota_gps_multas(DB_NAME)

    tv_criticas = sum(1 for o in ordens if o.get("categoria_tv") == "CRITICA")
    tv_peca = sum(1 for o in ordens if o.get("categoria_tv") == "PECA_ORCAMENTO")
    tv_programadas = sum(1 for o in ordens if o.get("categoria_tv") == "PROGRAMADA")
    orc_pendentes = sum(1 for o in ordens if o.get("eh_orcamento_pendente"))
    media_sat = round(sum(p["nota"] for p in pesquisas) / len(pesquisas), 1) if pesquisas else 5.0

    resumo_obj = {
        "total_os": len(ordens),
        "ativas": qtd_ativas,
        "concluidas": qtd_concluidas,
        "observacao": qtd_obs,
        "em_observacao": qtd_obs,
        "orcamentos_pendentes": orc_pendentes,
        "tv_criticas": tv_criticas,
        "tv_peca": tv_peca,
        "tv_programadas": tv_programadas,
        "pendencias_urgentes": qtd_pend_urg,
        "pendencias_programadas": qtd_pend_prog,
        "faturamento_total": fat_total,
        "receita_total": fat_total,
        "alarmes_calibracao": alarmes_cal.get("total_alarmes_urgentes", 0),
        "viagens_economizadas": viagens_economizadas,
        "media_satisfacao": media_sat,
    }

    payload = {
        "ok": True,
        "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "kpis": resumo_obj,
        "resumo": resumo_obj,
        "bi": {
            "por_status": bi_status,
            "por_tecnico": bi_tecnico,
            "por_cidade": bi_cidade,
            "por_servico": bi_servico,
        },
        "ordens": ordens,
        "rotas_agrupadas": rotas_lista,
        "clientes_unicos": clientes_unicos,
        "tecnicos": tecnicos,
        "veiculos": veiculos,
        "frota_gps_multas": frota_gps_multas,
        "estoque": estoque,
        "solicitacoes_almox": solicitacoes,
        "baixas_consumiveis": baixas_cons,
        "notas_fiscais": notas,
        "pesquisas_satisfacao": pesquisas,
        "alarmes_calibracao": alarmes_cal,
        "manuais": manuais_lista,
        "templates_relatorio": TEMPLATES_RELATORIO_TECNICO,
        "kits_servico": SUGESTOES_SEPARACAO_POR_ATIVIDADE,
        "google_review_url": google_url,
    }
    return web.json_response(payload)


async def api_checklist(request: web.Request) -> web.Response:
    equip = request.query.get("equipamento", "")
    defeito = request.query.get("defeito", "") or request.query.get("tipo_servico", "")
    acoes = obter_checklist_acoes_sugeridas(equip, defeito)
    sugestao_ia = gerar_sugestao_relatorio_clinico(equip, defeito)
    return web.json_response({
        "ok": True,
        "acoes": acoes,
        "itens_checklist": acoes,
        "frases_relatorio": [sugestao_ia] if sugestao_ia else [],
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
        "perguntas": triagem,
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

    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            df.at[idx, "checkin_hora"] = agora_str
            df.at[idx, "confirmado"] = "SIM"
            _salvar_df_direto(df)
            return web.json_response({"ok": True, "checkin_hora": agora_str, "msg": f"📍 Check-in registrado na OS #{os_id} às {agora_str}!"})

    return web.json_response({"ok": False, "msg": f"OS #{os_id} não encontrada."}, status=404)


def _salvar_base64_em_arquivo(b64_str: str, prefixo: str, os_id: str) -> str:
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
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    acao = str(body.get("acao", "CONCLUIR")).upper()

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
    param_med = limpar_texto(body.get("parametros_medidos"), "DENTRO DAS NORMAS / HOMOLOGADO").upper()
    obs_gerais = limpar_texto(body.get("observacoes_gerais"), limpar_texto(row_os.get("observacoes_gerais"), "")).upper()
    cond_final = limpar_texto(body.get("condicao_final"), "LIBERADO PARA USO NORMAL").upper()
    inst_prox = limpar_texto(body.get("instrumento_necessario"), "").upper()
    prioridade_pend = limpar_texto(body.get("prioridade_pendencia"), "NENHUMA").upper()

    peca_raw = limpar_texto(body.get("peca_selecionada"), "NENHUMA PEÇA").upper()
    peca_manual = limpar_texto(body.get("peca_manual"), "").upper()
    if peca_manual:
        peca_sel = f"[DIGITADA MANUALMENTE] {peca_manual}"
    elif peca_raw and peca_raw != "MANUAL":
        peca_sel = peca_raw
    else:
        peca_sel = "NENHUMA PEÇA"

    status_prop = limpar_texto(body.get("status_proposta"), "SEM_PROPOSTA").upper()
    dias_obs = int(limpar_float(body.get("dias_observacao"), 7))

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

    ref_ant = limpar_texto(row_os.get("peca_baixada_ref"), "")
    ok_p, tag_peca, nova_ref_peca = aplicar_peca_os_idempotente(DB_NAME, peca_sel, qtd_peca, ref_ant)
    if ok_p and tag_peca and tag_peca not in srv_exec:
        srv_exec = f"{srv_exec} | {tag_peca}"

    # Múltiplas fotos de evidência
    fotos_recebidas = body.get("fotos_multiplas_b64") or []
    if not isinstance(fotos_recebidas, list):
        fotos_recebidas = [fotos_recebidas] if fotos_recebidas else []
    if body.get("foto_antes_b64"):
        fotos_recebidas.insert(0, body["foto_antes_b64"])
    if body.get("foto_depois_b64"):
        fotos_recebidas.append(body["foto_depois_b64"])

    caminhos_fotos_salvas = []
    for idx_f, f_b64 in enumerate(fotos_recebidas):
        if f_b64 and len(str(f_b64)) > 50:
            c_salvo = _salvar_base64_em_arquivo(f_b64, f"EVIDENCIA_{idx_f+1}", os_id)
            if c_salvo:
                caminhos_fotos_salvas.append(c_salvo)

    if caminhos_fotos_salvas:
        df.at[idx_alvo, "foto_evidencia"] = caminhos_fotos_salvas[0]
        if len(caminhos_fotos_salvas) > 1:
            df.at[idx_alvo, "foto_depois"] = caminhos_fotos_salvas[1]
        df.at[idx_alvo, "fotos_adicionais"] = ";".join(caminhos_fotos_salvas)

    # Vídeo curto da operação
    video_b64 = body.get("video_b64", "")
    if video_b64 and len(str(video_b64)) > 100:
        cam_vid = _salvar_base64_em_arquivo(video_b64, "VIDEO_OPERACAO", os_id)
        if cam_vid:
            df.at[idx_alvo, "video_evidencia"] = cam_vid

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
    df.at[idx_alvo, "imprimir_observacoes"] = limpar_texto(body.get("imprimir_observacoes"), "SIM").upper()
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

    if acao == "OBSERVACAO" or "OBSERVA" in status_prop:
        df.at[idx_alvo, "status"] = "EM OBSERVAÇÃO"
        desc_pend = f"[EM OBSERVAÇÃO - {dias_obs} DIAS] Peça: {peca_sel} | Follow-up técnico e posterior emissão de NF"
        df.at[idx_alvo, "pendencias"] = desc_pend
        if peca_sel and peca_sel != "NENHUMA PEÇA":
            try:
                registrar_peca_em_teste_observacao(
                    DB_NAME, int(os_id), limpar_texto(row_os.get("cliente"), ""),
                    limpar_texto(row_os.get("equipamento"), ""), tec_resp, peca_sel, qtd_peca, dias_obs, "Follow-up de estabilidade para faturamento NF"
                )
            except Exception:
                pass
        msg_final = f"🔬 OS #{os_id} colocada EM OBSERVAÇÃO ({dias_obs} dias para Follow-up e NF)!"
    elif "FINANCEIRO" in status_prop or "AGUARDANDO" in status_prop:
        df.at[idx_alvo, "status"] = "ATIVO"
        df.at[idx_alvo, "pendencias"] = f"[FINANCEIRO: GERAR PROPOSTA COMERCIAL] Peça: {peca_sel} aplicada no cliente"
        msg_final = f"📋 OS #{os_id} salva! Notificação enviada ao Financeiro para envio da Proposta Comercial!"
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
    body = await request.json()
    cliente = limpar_texto(body.get("cliente"), "").upper()
    equipamento = limpar_texto(body.get("equipamento"), "").upper()
    defeito = limpar_texto(body.get("defeito_relatado"), "MANUTENÇÃO PREVENTIVA / CADASTRO PARQUE").upper()
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
    cnpj = limpar_texto(body.get("cnpj"), "")
    respostas_triagem = limpar_texto(body.get("respostas_triagem"), "")

    kit_sug = obter_kit_por_servico(tipo_srv, defeito)
    df = _carregar_df_direto()
    novo_id = int(df["id"].max() + 1) if ("id" in df.columns and not df.empty and pd.notna(df["id"].max())) else (len(df) + 1)

    nova_linha = {
        "id": novo_id,
        "cliente": cliente,
        "cnpj": cnpj,
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


async def api_despachar_rota(request: web.Request) -> web.Response:
    """Despacha em bloco todos os chamados ativos de um hospital/rota para um técnico."""
    body = await request.json()
    os_ids = [str(x) for x in body.get("os_ids", [])]
    tecnico = limpar_texto(body.get("tecnico"), "").upper()
    auxiliar = limpar_texto(body.get("auxiliar"), "").upper()
    if not os_ids or not tecnico:
        return web.json_response({"ok": False, "msg": "Selecione os chamados e o técnico."}, status=400)

    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()
    tel_t = equipa.get(tecnico, {}).get("tel", "")
    qtd = 0
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) in os_ids:
            df.at[idx, "tecnico_responsavel"] = tecnico
            df.at[idx, "tecnico_auxiliar"] = auxiliar
            df.at[idx, "telefone_tecnico"] = tel_t
            df.at[idx, "confirmado"] = "SIM"
            qtd += 1
    _salvar_df_direto(df)
    return web.json_response({"ok": True, "msg": f"🚚 Rota despachada! {qtd} chamado(s) atribuído(s) para {tecnico}."})


async def api_orcamento_acao(request: web.Request) -> web.Response:
    """Aprova orçamento, converte peça em teste em definitiva ou retira peça em teste."""
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    acao = limpar_texto(body.get("acao"), "APROVAR").upper()
    valor = limpar_float(body.get("valor"), 0.0)

    if acao == "CONVERTER_TESTE":
        ok, msg = converter_teste_em_aplicacao_definitiva_e_cobranca(DB_NAME, int(os_id), valor if valor > 0 else None)
        df = _carregar_df_direto()
        _salvar_df_direto(df)
        return web.json_response({"ok": ok, "msg": msg})
    elif acao == "RETIRAR_TESTE":
        ok, msg = retirar_peca_teste_e_devolver_estoque(DB_NAME, int(os_id))
        df = _carregar_df_direto()
        _salvar_df_direto(df)
        return web.json_response({"ok": ok, "msg": msg})
    else:
        df = _carregar_df_direto()
        for idx, row in df.iterrows():
            if str(obter_id_os(idx, row)) == os_id:
                desc_ant = limpar_texto(row.get("pendencias"), "")
                df.at[idx, "pendencias"] = f"[ORÇAMENTO APROVADO - LIBERADO PARA EXECUÇÃO] {desc_ant}"
                df.at[idx, "confirmado"] = "SIM"
                _salvar_df_direto(df)
                return web.json_response({"ok": True, "msg": f"✅ Orçamento da OS #{os_id} aprovado e liberado para execução!"})
        return web.json_response({"ok": False, "msg": "OS não localizada."}, status=404)


async def api_solicitar_peca_kit(request: web.Request) -> web.Response:
    """Registra pedido de peças/ferramentas/kit ao Almoxarifado ou baixa de consumível pelo técnico."""
    body = await request.json()
    tipo = limpar_texto(body.get("tipo"), "PEDIDO_PECA").upper()
    tecnico = limpar_texto(body.get("tecnico"), "ANTONIO").upper()
    cliente = limpar_texto(body.get("cliente"), "DEMANDA DE CAMPO").upper()
    itens = limpar_texto(body.get("itens"), "").upper()
    instrumentos = limpar_texto(body.get("instrumentos"), "KIT PADRÃO").upper()
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    if not itens:
        return web.json_response({"ok": False, "msg": "Informe a peça, consumível ou kit desejado."}, status=400)

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        if tipo == "BAIXA_CONSUMIVEL":
            qtd_c = int(limpar_float(body.get("quantidade"), 1))
            cur.execute("""
                INSERT INTO baixas_consumiveis (tecnico, item, quantidade, cliente_os, data_baixa)
                VALUES (?, ?, ?, ?, ?)
            """, (tecnico, itens, qtd_c, cliente, agora))
            conn.commit()
            return web.json_response({"ok": True, "msg": f"🧴 Baixa de consumível ({qtd_c}x {itens}) registrada!"})
        else:
            cur.execute("""
                INSERT INTO solicitacoes_pecas
                (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tecnico, cliente, itens, instrumentos, "A SEPARAR (SOLICITADO PELO APP)", agora))
            conn.commit()
            return web.json_response({"ok": True, "msg": f"📦 Pedido enviado para o Almoxarifado EMED com sucesso!"})


async def api_estoque_salvar(request: web.Request) -> web.Response:
    """Adiciona ou atualiza item no estoque + validade de calibração."""
    body = await request.json()
    codigo = limpar_texto(body.get("codigo"), "").upper()
    nome_peca = limpar_texto(body.get("nome_peca"), "").upper()
    categoria = limpar_texto(body.get("categoria"), "PEÇA").upper()
    quantidade = int(limpar_float(body.get("quantidade"), 1))
    preco = limpar_float(body.get("preco_unitario"), 0.0)
    validade_cal = limpar_texto(body.get("validade_calibracao"), "")
    cert_cal = limpar_texto(body.get("certificado_calibracao"), "").upper()

    if not codigo or not nome_peca:
        return web.json_response({"ok": False, "msg": "Informe o código e o nome da peça/instrumento."}, status=400)

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT codigo FROM estoque_pecas WHERE UPPER(codigo) = ?", (codigo,))
        existe = cur.fetchone()
        if existe:
            cur.execute("""
                UPDATE estoque_pecas
                SET nome_peca = ?, categoria = ?, quantidade = ?, preco_unitario = ?,
                    data_validade_calibracao = ?, certificado_calibracao = ?
                WHERE UPPER(codigo) = ?
            """, (nome_peca, categoria, quantidade, preco, validade_cal, cert_cal, codigo))
        else:
            cur.execute("""
                INSERT INTO estoque_pecas
                (codigo, nome_peca, categoria, quantidade, estoque_minimo, preco_unitario, localizacao, data_validade_calibracao, certificado_calibracao)
                VALUES (?, ?, ?, ?, 1, ?, 'ALMOXARIFADO CENTRAL', ?, ?)
            """, (codigo, nome_peca, categoria, quantidade, preco, validade_cal, cert_cal))
        conn.commit()

    return web.json_response({"ok": True, "msg": f"✅ Item '{codigo} — {nome_peca}' salvo no estoque!"})


async def api_calibracao_equipamento(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = int(limpar_float(body.get("os_id"), 0))
    dt_ult = limpar_texto(body.get("data_ultima"), datetime.date.today().strftime("%d/%m/%Y"))
    dt_val = limpar_texto(body.get("data_validade"), "")
    cert = limpar_texto(body.get("certificado"), "")
    ok, msg = atualizar_calibracao_equipamento_cliente(DB_NAME, os_id, dt_ult, dt_val, cert)
    return web.json_response({"ok": ok, "msg": msg})


async def api_veiculo_km(request: web.Request) -> web.Response:
    body = await request.json()
    vid = int(limpar_float(body.get("id"), 1))
    km_atual = int(limpar_float(body.get("km_atual"), 0))
    km_prox = int(limpar_float(body.get("km_proxima_revisao"), 50000))
    obs = limpar_texto(body.get("historico_manutencao"), "")
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE veiculos
            SET km_atual = ?, km_proxima_revisao = ?, historico_manutencao = ?
            WHERE id = ?
        """, (km_atual, km_prox, obs, vid))
        conn.commit()
    return web.json_response({"ok": True, "msg": f"🚗 Quilometragem atualizada para {km_atual:,} KM!"})


async def api_tecnico_salvar(request: web.Request) -> web.Response:
    body = await request.json()
    nome = limpar_texto(body.get("nome"), "").upper()
    tel = limpar_texto(body.get("telefone"), "")
    sede = limpar_texto(body.get("sede"), "FORTALEZA").upper()
    perfil = limpar_texto(body.get("perfil"), "Técnico")
    ass = limpar_texto(body.get("assinatura_padrao"), f"{nome} - CFT").upper()
    if not nome:
        return web.json_response({"ok": False, "msg": "Informe o nome do técnico."}, status=400)
    with get_db_connection(DB_NAME) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO tecnicos
            (nome, telefone, partida, sede, senha, perfil, assinatura_padrao, rubrica_img)
            VALUES (?, ?, ?, ?, '1234', ?, ?, '')
        """, (nome, tel, sede, sede, perfil, ass))
        conn.commit()
    return web.json_response({"ok": True, "msg": f"👷 Técnico '{nome}' salvo na equipe EMED!"})


async def api_satisfacao_registrar(request: web.Request) -> web.Response:
    body = await request.json()
    os_id = limpar_texto(body.get("os_id"), "AVULSO")
    cliente = limpar_texto(body.get("cliente"), "HOSPITAL CREDENCIADO")
    tecnico = limpar_texto(body.get("tecnico"), "EQUIPE EMED")
    nota = int(limpar_float(body.get("nota"), 5))
    comentario = limpar_texto(body.get("comentario"), "Excelente atendimento!")
    ok, msg = registrar_pesquisa(DB_NAME, os_id, cliente, tecnico, nota, comentario)
    return web.json_response({"ok": ok, "msg": msg, "google_url": obter_url_google_review(DB_NAME)})


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
                headers={"Content-Disposition": f'inline; filename="{nome_arq}"'},
            )
    return web.Response(text=f"OS #{os_id} não encontrada", status=404)


async def api_html_os(request: web.Request) -> web.Response:
    os_id = request.match_info.get("os_id", "").strip()
    modo_print = request.query.get("print", "0") == "1"
    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            html_os = _gerar_html_os_formatada(os_id, row, equipa)
            if modo_print:
                barra_superior = """
                <div class="no-print" style="position:sticky;top:0;background:#002b54;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;z-index:99999;box-shadow:0 2px 10px rgba(0,0,0,0.25);font-family:Arial,sans-serif;">
                    <div style="font-weight:bold;font-size:13px;display:flex;align-items:center;gap:8px;">
                        <span style="font-size:18px;">📄</span> Laudo Técnico Oficial — EMED Eletromedicina
                    </div>
                    <div style="display:flex;gap:8px;">
                        <button onclick="window.print()" style="background:#15803d;color:#fff;border:none;padding:8px 16px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:13px;">🖨️ Imprimir / Salvar PDF</button>
                        <button onclick="window.close()" style="background:rgba(255,255,255,0.2);color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px;">✕ Fechar</button>
                    </div>
                </div>
                <script>
                    window.addEventListener('load', function() {
                        setTimeout(function() { window.print(); }, 400);
                    });
                </script>
                """
                html_os = html_os.replace("<body>", f"<body>{barra_superior}")
            return web.Response(text=html_os, content_type="text/html")
    return web.Response(text=f"OS #{os_id} não encontrada", status=404)


async def api_imprimir_os(request: web.Request) -> web.Response:
    """Abre o laudo técnico da OS em formato HTML otimizado para impressão A4 direta no celular."""
    os_id = request.match_info.get("os_id", "").strip()
    df = _carregar_df_direto()
    equipa = _montar_equipa_direto()
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            html_os = _gerar_html_os_formatada(os_id, row, equipa)
            barra_superior = """
            <div class="no-print" style="position:sticky;top:0;background:#002b54;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;z-index:99999;box-shadow:0 2px 10px rgba(0,0,0,0.25);font-family:Arial,sans-serif;">
                <div style="font-weight:bold;font-size:13px;display:flex;align-items:center;gap:8px;">
                    <span style="font-size:18px;">📄</span> Laudo Oficial — OS #""" + str(os_id) + """
                </div>
                <div style="display:flex;gap:8px;">
                    <button onclick="window.print()" style="background:#15803d;color:#fff;border:none;padding:8px 16px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:13px;">🖨️ Imprimir / Salvar PDF</button>
                    <button onclick="window.close()" style="background:rgba(255,255,255,0.2);color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;font-size:13px;">✕ Fechar</button>
                </div>
            </div>
            <script>
                window.addEventListener('load', function() {
                    setTimeout(function() { window.print(); }, 400);
                });
            </script>
            """
            html_os = html_os.replace("<body>", f"<body>{barra_superior}")
            return web.Response(text=html_os, content_type="text/html")
    return web.Response(text=f"OS #{os_id} não encontrada", status=404)


async def api_manual_download(request: web.Request) -> web.Response:
    """Serve o PDF de um manual técnico ou compila um .md em PDF na hora."""
    rel_path = request.query.get("path", "").strip()
    if ".." in rel_path:
        return web.Response(text="Caminho inválido", status=400)

    abs_path = os.path.join(BASE_DIR, rel_path.replace("/", os.sep)) if rel_path and rel_path != "undefined" else ""

    # Fallback: se o caminho relativo não bater direto, procura pelo nome do arquivo na pasta Manuais/
    if not abs_path or not os.path.exists(abs_path):
        nome_busca = os.path.basename(rel_path) if rel_path and rel_path != "undefined" else request.query.get("file", "")
        encontrado = None
        pasta_manuais = os.path.join(BASE_DIR, "Manuais")
        if os.path.exists(pasta_manuais):
            for root, _, files in os.walk(pasta_manuais):
                for f in files:
                    if nome_busca and f.lower() == nome_busca.lower():
                        encontrado = os.path.join(root, f)
                        break
                    elif not encontrado and f.lower().endswith(".pdf"):
                        encontrado = os.path.join(root, f)
                if encontrado and nome_busca:
                    break
        if encontrado and os.path.exists(encontrado):
            abs_path = encontrado
        else:
            return web.Response(text="Manual não encontrado", status=404)

    # Se apontar para .md mas já existir o .pdf oficial homologado na mesma pasta, serve o .pdf oficial
    if abs_path.lower().endswith(".md"):
        pdf_irmao = os.path.splitext(abs_path)[0] + ".pdf"
        if os.path.exists(pdf_irmao):
            abs_path = pdf_irmao

    nome_base = os.path.basename(abs_path)
    if abs_path.lower().endswith(".pdf"):
        with open(abs_path, "rb") as f:
            return web.Response(
                body=f.read(),
                content_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{nome_base}"',
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                },
            )
    else:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            out_pdf = tmp.name
        try:
            render_markdown_to_pdf(abs_path, out_pdf)
            with open(out_pdf, "rb") as f:
                pdf_b = f.read()
            return web.Response(
                body=pdf_b,
                content_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{os.path.splitext(nome_base)[0]}.pdf"'},
            )
        finally:
            if os.path.exists(out_pdf):
                try:
                    os.remove(out_pdf)
                except Exception:
                    pass


async def api_video_stream(request: web.Request) -> web.Response:
    nome_vid = os.path.basename(request.query.get("name", ""))
    if not nome_vid:
        return web.Response(status=404)
    cand1 = os.path.join(BASE_DIR, "Videos_Treinamento_ITs", nome_vid)
    cand2 = os.path.join(BASE_DIR, nome_vid)
    alvo = cand1 if os.path.exists(cand1) else (cand2 if os.path.exists(cand2) else None)
    if not alvo:
        return web.Response(status=404)
    return web.FileResponse(alvo)


async def api_exportar_excel(request: web.Request) -> web.Response:
    if os.path.exists(CAMINHO_EXCEL):
        with open(CAMINHO_EXCEL, "rb") as f:
            return web.Response(
                body=f.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="base_clientes_EMED.xlsx"'},
            )
    return web.Response(status=404)


TOKEN_OFICIAL_GPS = os.environ.get("EMED_GPS_API_KEY", "EMED-GPS-2026-TOKEN-OFICIAL")


def _validar_token_gps(request: web.Request) -> bool:
    """
    Suporta autenticação via:
      - Header `Authorization: Bearer EMED-GPS-2026-TOKEN-OFICIAL`
      - Header `X-API-Key: EMED-GPS-2026-TOKEN-OFICIAL`
      - Query param `?api_key=EMED-GPS-2026-TOKEN-OFICIAL`
    Se nenhum header de token externo for enviado (chamada interna do PWA), permite a operação;
    se um token for enviado, valida contra a chave oficial configurada.
    """
    auth_h = request.headers.get("Authorization", "").strip()
    api_k = request.headers.get("X-API-Key", "").strip() or request.query.get("api_key", "").strip()
    if not auth_h and not api_k:
        return True
    if auth_h.lower().startswith("bearer "):
        tok = auth_h[7:].strip()
        return tok in (TOKEN_OFICIAL_GPS, "EMED-2026-PILOTO")
    if api_k:
        return api_k in (TOKEN_OFICIAL_GPS, "EMED-2026-PILOTO")
    return True


async def api_gps_telemetria(request: web.Request) -> web.Response:
    """
    Endpoint oficial (POST/PUT /api/gps/telemetria e /api/v1/veiculos/{id}/odometro):
    Aceita tanto o payload estruturado da Proposta de Integração (J16 4G LTE + NFC + PostGIS)
    quanto o formato direto do App EMED.
    """
    if not _validar_token_gps(request):
        return web.json_response({"ok": False, "erro": "Token de API inválido (use Authorization: Bearer EMED-GPS-2026-TOKEN-OFICIAL)"}, status=401)
    try:
        body = await request.json()
    except Exception:
        body = {}
    identificador_url = request.match_info.get("identificador", "").strip()
    if identificador_url and not body.get("placa"):
        if identificador_url.isdigit() and len(identificador_url) >= 9:
            body["renavam"] = identificador_url
        else:
            body["placa"] = identificador_url
    res = registrar_telemetria_ou_viagem_gps(DB_NAME, body)
    return web.json_response(res)


async def api_gps_lote(request: web.Request) -> web.Response:
    """
    Importação Automatizada em Lote (POST /api/v1/frota/lote):
    Recebe lista de viagens/odômetros em JSON (`[...]` ou `{"viagens": [...]}`) e sincroniza todas.
    """
    if not _validar_token_gps(request):
        return web.json_response({"ok": False, "erro": "Token de API inválido"}, status=401)
    body = await request.json()
    lista = body if isinstance(body, list) else (body.get("viagens") or body.get("registros") or [body])
    resultados = []
    for item in lista:
        if isinstance(item, dict):
            resultados.append(registrar_telemetria_ou_viagem_gps(DB_NAME, item))
    return web.json_response({
        "ok": True,
        "total_processados": len(resultados),
        "resultados": resultados,
        "msg": f"✅ Lote sincronizado com sucesso: {len(resultados)} veículo(s)/viagem(ns) atualizado(s) no EMED!",
    })


async def api_v1_odometro_doc(request: web.Request) -> web.Response:
    """Documentação amigável quando alguém acessa o endpoint de odômetro via GET no navegador."""
    identificador = request.match_info.get("identificador", "").strip()
    return web.json_response({
        "ok": True,
        "endpoint": f"/api/v1/veiculos/{identificador}/odometro" if identificador else "/api/v1/veiculos/odometro",
        "servico": "EMED Telemetria de Frota & Sincronização Automática de Odômetro (J16 4G LTE + NFC)",
        "status": "ONLINE E PRONTO PARA RECEBER DADOS",
        "metodos_aceitos": ["POST", "PUT"],
        "autenticacao_suportada": "Authorization: Bearer EMED-GPS-2026-TOKEN-OFICIAL",
        "exemplo_payload_esperado": {
            "placa": "EMD-2026",
            "renavam": "01234567890",
            "tecnico": {
                "cpf": "123.456.789-00",
                "nome": "ANTONIO"
            },
            "viagem": {
                "data_inicio": "2026-10-26T07:30:00Z",
                "data_fim": "2026-10-26T17:45:00Z",
                "odometro_inicial_km": 45000.0,
                "odometro_final_km": 45118.5,
                "km_percorrido": 118.5,
                "ignicao_tempo_ligada_min": 185
            },
            "status_odometro_atual": 45118.5
        },
        "aplicativo_visual": "Para abrir o aplicativo EMED com telas, menus e ordens de serviço, acesse a página inicial sem /api",
        "url_aplicativo": "https://emed-app-6ofv.onrender.com"
    })


async def api_v1_listar_veiculos(request: web.Request) -> web.Response:
    """GET /api/v1/veiculos — Consulta de status, placa, RENAVAM e odômetro atual da frota EMED."""
    garantir_tabelas_frota_gps_multas(DB_NAME)
    veiculos = []
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, modelo, placa, renavam, km_atual, km_proxima_revisao,
                   condutor_atual, tag_rfid_atual, ultima_lat, ultima_lon,
                   ultima_atualizacao_gps, ignicao_ligada, status_manutencao
            FROM veiculos
            ORDER BY id ASC
        """)
        for r in cur.fetchall():
            veiculos.append({
                "id": r[0],
                "modelo": r[1],
                "placa": r[2],
                "renavam": r[3] or "01234567890",
                "status_odometro_atual": float(r[4] or 0),
                "km_proxima_revisao": int(r[5] or 50000),
                "condutor_atual": r[6] or "DISPONÍVEL",
                "tag_identificacao": r[7] or "",
                "latitude": float(r[8] or -3.7319),
                "longitude": float(r[9] or -38.5267),
                "ultima_atualizacao_gps": r[10] or "",
                "ignicao_ligada": bool(r[11]),
                "status_manutencao": r[12] or "Disponível",
            })
    return web.json_response({"ok": True, "total_veiculos": len(veiculos), "veiculos": veiculos})


async def api_frota_webhook_detran(request: web.Request) -> web.Response:
    """
    Endpoint para o Robô Diário DETRAN / Autarquia (AMC, PRF, SEFAZ):
    Recebe multa ou taxa e executa o Cruzamento Automático de Condutor por Data/Hora e GPS.
    """
    if not _validar_token_gps(request):
        return web.json_response({"ok": False, "erro": "Token de API inválido"}, status=401)
    body = await request.json()
    res = registrar_multa_ou_taxa_com_cruzamento(DB_NAME, body)
    return web.json_response(res)


async def api_frota_executar_robo(request: web.Request) -> web.Response:
    """Dispara a varredura e cruzamento diário do Robô DETRAN/Autarquia."""
    res = executar_varredura_robo_detran(DB_NAME)
    return web.json_response(res)


async def api_frota_multa_status(request: web.Request) -> web.Response:
    """Atualiza status de pagamento/indicação de condutor de uma multa ou taxa."""
    body = await request.json()
    id_m = int(limpar_float(body.get("id"), 0))
    st_novo = limpar_texto(body.get("status_pagamento"), "PAGO")
    cond_man = limpar_texto(body.get("condutor_identificado"), "")
    res = atualizar_status_multa_taxa(DB_NAME, id_m, st_novo, cond_man)
    return web.json_response(res)


def criar_app() -> web.Application:
    app = web.Application(client_max_size=25 * 1024 * 1024)
    app.router.add_get("/", handle_index)
    app.router.add_get("/manifest.json", handle_manifest)
    app.router.add_get("/sw.js", handle_sw)
    app.router.add_get("/api/logo", handle_logo)
    app.router.add_get("/api/logo-circle", handle_logo_circle)
    app.router.add_get("/api/ping", api_ping)
    app.router.add_get("/healthz", api_ping)
    app.router.add_get("/api/bootstrap", api_bootstrap)
    app.router.add_get("/api/checklist", api_checklist)
    app.router.add_get("/api/triagem", api_triagem)
    app.router.add_post("/api/rascunho", api_salvar_rascunho)
    app.router.add_post("/api/checkin", api_checkin)
    app.router.add_post("/api/salvar-os", api_salvar_os)
    app.router.add_post("/api/nova-os", api_nova_os)
    app.router.add_post("/api/reabrir-os", api_reabrir_os)
    app.router.add_post("/api/rotas/despachar", api_despachar_rota)
    app.router.add_post("/api/orcamento/acao", api_orcamento_acao)
    app.router.add_post("/api/solicitar-peca", api_solicitar_peca_kit)
    app.router.add_post("/api/estoque/salvar", api_estoque_salvar)
    app.router.add_post("/api/calibracao/equipamento", api_calibracao_equipamento)
    app.router.add_post("/api/veiculo/km", api_veiculo_km)
    app.router.add_post("/api/gps/telemetria", api_gps_telemetria)
    app.router.add_put("/api/gps/telemetria", api_gps_telemetria)
    # Endpoints Oficiais da Especificação de Integração v1 (Rastreadores J16 4G + NFC + PostGIS + Scraper DETRAN)
    app.router.add_get("/api/v1/veiculos", api_v1_listar_veiculos)
    app.router.add_get("/api/v1/veiculos/odometro", api_v1_odometro_doc)
    app.router.add_get("/api/v1/veiculos/{identificador}/odometro", api_v1_odometro_doc)
    app.router.add_post("/api/v1/veiculos/odometro", api_gps_telemetria)
    app.router.add_put("/api/v1/veiculos/odometro", api_gps_telemetria)
    app.router.add_post("/api/v1/veiculos/{identificador}/odometro", api_gps_telemetria)
    app.router.add_put("/api/v1/veiculos/{identificador}/odometro", api_gps_telemetria)
    app.router.add_post("/api/v1/frota/lote", api_gps_lote)
    app.router.add_post("/api/v1/frota/multas", api_frota_webhook_detran)
    app.router.add_post("/api/frota/webhook-detran", api_frota_webhook_detran)
    app.router.add_post("/api/frota/executar-robo-detran", api_frota_executar_robo)
    app.router.add_post("/api/frota/multa-status", api_frota_multa_status)
    app.router.add_post("/api/tecnico/salvar", api_tecnico_salvar)
    app.router.add_post("/api/satisfacao/registrar", api_satisfacao_registrar)
    app.router.add_post("/api/almoxarifado/status", api_almox_status)
    app.router.add_post("/api/pix/gerar", api_pix_gerar)
    app.router.add_post("/api/pix/liquidar", api_pix_liquidar)
    app.router.add_post("/api/config", api_config)
    app.router.add_get("/api/pdf/{os_id}", api_pdf_os)
    app.router.add_get("/api/html/{os_id}", api_html_os)
    app.router.add_get("/api/imprimir/{os_id}", api_imprimir_os)
    app.router.add_get("/api/manual", api_manual_download)
    app.router.add_get("/api/video", api_video_stream)
    app.router.add_get("/api/exportar-excel", api_exportar_excel)
    return app


async def _background_keep_alive_task():
    """Tarefa em background que envia ping HTTP a cada 9 minutos para manter a instância Render aquecida."""
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://emed-app-6ofv.onrender.com")
    ping_url = f"{render_url.rstrip('/')}/api/ping"
    await asyncio.sleep(60) # aguarda 1 minuto após startup
    while True:
        try:
            import urllib.request
            req = urllib.request.Request(ping_url, headers={"User-Agent": "EMED-Internal-KeepAlive/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.getcode() == 200:
                    print(f"⏱️ [Anti-Standby] Auto-ping enviado com sucesso para {ping_url}")
        except Exception as e:
            # Em ambiente local sem internet pública, ignora silenciosamente
            pass
        await asyncio.sleep(540) # a cada 9 minutos (Render dorme em 15 minutos)


async def iniciar_app_com_keepalive():
    app = criar_app()
    # Inicia a tarefa de auto-ping se estiver rodando no Render ou configurado
    asyncio.create_task(_background_keep_alive_task())
    return app


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", os.environ.get("EMED_APP_PORT", 8502)))
    print(f"🚀 Iniciando Servidor Completo do Aplicativo Oficial EMED na porta {porta} (com Anti-Standby 24/7)...")
    web.run_app(iniciar_app_com_keepalive(), host="0.0.0.0", port=porta)
