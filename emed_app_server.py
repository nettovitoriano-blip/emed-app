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
import urllib.parse



import base64



import sqlite3



import tempfile



import datetime



from datetime import datetime, timezone, timedelta



import asyncio



TZ_BRASIL = timezone(timedelta(hours=-3))



def obter_agora_brasil() -> datetime:

    """Retorna datetime no fuso oficial do Brasil (UTC-3 / Fortaleza / Brasília)."""

    return datetime.now(TZ_BRASIL)



def obter_agora_brasil_str(fmt: str = "%d/%m/%Y %H:%M") -> str:

    """Retorna string formatada da data/hora oficial do Brasil (UTC-3)."""

    return obter_agora_brasil().strftime(fmt)



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



    sincronizar_os_offline_idempotente,



    gerar_hash_os_offline,

    verificar_pendencias_financeiras_cliente,
    verificar_disponibilidade_ferramentas,
    obter_instrucao_ferramenta,
    INSTRUCOES_CUIDADO_FERRAMENTAS,



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
    conciliar_pagamento_bancario_duplo,



)
from emed_services.robo_rastreamento import (
    executar_ciclo_verificacao,
    obter_status_robo,
    consultar_rastreio_online,
    garantir_schema_rastreio_completo,
    gerar_mensagem_retirada_carga,
    confirmar_retirada_paulinho
)





from emed_services.hospital_autorizacao import (
    obter_dados_credenciamento_os,
    gerar_texto_whatsapp_portaria,
    gerar_html_autorizacao_entrada
)
from emed_services.equipamento_qrcode import (
    obter_historico_anual_equipamento,
    gerar_qrcode_base64,
    gerar_pagina_prontuario_equipamento,
    gerar_etiqueta_qrcode_html
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



        "timestamp": obter_agora_brasil().isoformat(),



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
            hoje_data = obter_agora_brasil().date()
            for _, r in df_tec.iterrows():
                ass_p = limpar_texto(r.get("assinatura_padrao"), "CFT")
                d_venc_raw = limpar_texto(r.get("data_vencimento_aso"), "")
                st_med = "PENDENTE"
                dias_rest = 0
                if d_venc_raw:
                    try:
                        if "/" in d_venc_raw:
                            dt_v = datetime.strptime(d_venc_raw[:10], "%d/%m/%Y").date()
                        else:
                            dt_v = datetime.strptime(d_venc_raw[:10], "%Y-%m-%d").date()
                        dias_rest = (dt_v - hoje_data).days
                        if dias_rest < 0:
                            st_med = "VENCIDO"
                        elif dias_rest <= 30:
                            st_med = "ALERTA"
                        else:
                            st_med = "EM_DIA"
                    except Exception:
                        st_med = "EM_DIA"

                tecnicos.append({
                    "id": int(r.get("id") or 0),
                    "nome": limpar_texto(r.get("nome"), "").upper(),
                    "telefone": _limpar_telefone_exibicao(r.get("telefone")),
                    "partida": limpar_texto(r.get("partida"), "FORTALEZA"),
                    "sede": limpar_texto(r.get("sede"), "FORTALEZA"),
                    "perfil": limpar_texto(r.get("perfil"), "Técnico"),
                    "assinatura_padrao": ass_p,
                    "assinatura": ass_p,
                    "data_ultimo_aso": limpar_texto(r.get("data_ultimo_aso"), ""),
                    "data_vencimento_aso": d_venc_raw,
                    "periodicidade_meses": int(r.get("periodicidade_meses") or 12),
                    "medico_examinador": limpar_texto(r.get("medico_examinador"), ""),
                    "clinica_medicina_trabalho": limpar_texto(r.get("clinica_medicina_trabalho"), ""),
                    "tipo_exame_aso": limpar_texto(r.get("tipo_exame_aso"), "PERIÓDICO"),
                    "parecer_aptidao": limpar_texto(r.get("parecer_aptidao"), "APTO"),
                    "observacoes_medicas": limpar_texto(r.get("observacoes_medicas"), ""),
                    "status_medico": st_med,
                    "dias_para_vencer": dias_rest,
                })



        except Exception:



            pass







        try:

            df_est = pd.read_sql_query("SELECT * FROM estoque_pecas ORDER BY quantidade DESC, nome_peca ASC", conn)

            for _, r in df_est.iterrows():

                st_cal = calcular_status_calibracao(limpar_texto(r.get("data_validade_calibracao"), ""))

                qtd_val = round(limpar_float(r.get("quantidade"), 0.0), 2)

                p_unit = limpar_float(r.get("preco_unitario") or r.get("preco_custo"), 0.0)

                v_tot = limpar_float(r.get("valor_total"), qtd_val * p_unit)

                estoque.append({

                    "codigo": limpar_texto(r.get("codigo"), ""),

                    "nome_peca": limpar_texto(r.get("nome_peca"), ""),

                    "categoria": limpar_texto(r.get("categoria"), "PEÇA DE REPOSIÇÃO"),

                    "tipo_item": limpar_texto(r.get("tipo_item"), "GERAL"),

                    "grupo_item": limpar_texto(r.get("grupo_item"), ""),

                    "unidade": limpar_texto(r.get("unidade"), "UND"),

                    "quantidade": qtd_val,

                    "estoque_minimo": round(limpar_float(r.get("estoque_minimo"), 1.0), 1),

                    "preco_unitario": p_unit,

                    "preco_custo": p_unit,

                    "valor_total": v_tot,

                    "localizacao": limpar_texto(r.get("localizacao"), "ALMOXARIFADO CENTRAL - FORTALEZA"),

                    "ultima_calibracao": limpar_texto(r.get("data_ultima_calibracao"), ""),

                    "validade_calibracao": limpar_texto(r.get("data_validade_calibracao"), ""),

                    "certificado_calibracao": limpar_texto(r.get("certificado_calibracao"), ""),

                    "saldo_creditos": limpar_texto(r.get("saldo_creditos"), ""),

                    "badge_calibracao": st_cal["badge_txt"],

                    "cor_calibracao": st_cal["badge_cor"],

                    "status_cal": st_cal["status"],

                })

        except Exception as e:

            print("Erro ao carregar estoque_pecas:", e)







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



                    "status_compra": limpar_texto(r.get("status_compra"), ""),



                    "previsao_entrega": limpar_texto(r.get("previsao_entrega"), ""),



                    "fornecedor": limpar_texto(r.get("fornecedor"), ""),



                    "codigo_peca": limpar_texto(r.get("codigo_peca"), ""),

                    "tipo_origem_peca": limpar_texto(r.get("tipo_origem_peca"), "NOVA_COM_NF"),

                    "os_id": str(r.get("os_id") or ""),
                    "motivo_recusa": limpar_texto(r.get("motivo_recusa"), ""),
                    "confirmado_em": limpar_texto(r.get("confirmado_em"), ""),
                    "recusado_em": limpar_texto(r.get("recusado_em"), ""),
                    "codigo_rastreio": limpar_texto(r.get("codigo_rastreio"), ""),
                    "transportadora": limpar_texto(r.get("transportadora"), ""),



                })



        except Exception:



            pass



        ferramentas = []

        try:

            df_fer = pd.read_sql_query("SELECT * FROM ferramentas_cautela ORDER BY id ASC", conn)

            for _, r in df_fer.iterrows():

                ferramentas.append({

                    "id": int(r.get("id", 0)),

                    "codigo": limpar_texto(r.get("codigo_ferramenta"), ""),

                    "nome": limpar_texto(r.get("nome_ferramenta"), ""),

                    "status": limpar_texto(r.get("status"), "DISPONIVEL").upper(),

                    "tecnico": limpar_texto(r.get("tecnico_responsavel"), "").upper(),

                    "cliente": limpar_texto(r.get("destino_cliente"), "").upper(),

                    "os_id": limpar_texto(r.get("os_id"), ""),

                    "data_saida": limpar_texto(r.get("data_saida"), ""),

                    "numero_serie": limpar_texto(r.get("numero_serie"), ""),

                    "localizacao": limpar_texto(r.get("localizacao"), "ALMOXARIFADO CENTRAL"),

                    "validade_calibracao": limpar_texto(r.get("data_validade_calibracao"), ""),

                    "certificado": limpar_texto(r.get("certificado_calibracao"), ""),

                    "observacao": limpar_texto(r.get("observacao"), "")

                })

        except Exception as e_fer:

            print("Aviso ao carregar ferramentas_cautela:", e_fer)







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



                num_nf = limpar_texto(r.get("numero_nf"), "") or f"NFS-{nid:04d}"

                val_tot = limpar_float(r.get("valor_total"), 0.0)

                val_srv = limpar_float(r.get("valor_servicos"), 0.0)

                val_pec = limpar_float(r.get("valor_pecas"), 0.0)

                if val_tot <= 0 and (val_srv > 0 or val_pec > 0):

                    val_tot = val_srv + val_pec



                notas.append({



                    "id": nid,



                    "numero_nf": num_nf,



                    "os_id": limpar_texto(r.get("os_id"), ""),



                    "cliente": limpar_texto(r.get("cliente"), ""),



                    "tipo_nota": limpar_texto(r.get("tipo_nota"), "NFS-e"),



                    "descricao": limpar_texto(r.get("descricao"), ""),



                    "valor_total": val_tot,

                    "valor_servicos": val_srv,

                    "valor_pecas": val_pec,

                    "regra_fiscal": limpar_texto(r.get("regra_fiscal"), "SERVICO_TOTAL"),

                    "chave_acesso": limpar_texto(r.get("chave_acesso"), ""),

                    "discriminacao_servico": limpar_texto(r.get("discriminacao_servico"), ""),



                    "status_fiscal": st_f,



                                        "status_pagamento": st_f,
                    "data_emissao": limpar_texto(r.get("data_emissao"), ""),
                    "data_liberacao_fiscal": limpar_texto(r.get("data_liberacao_fiscal"), ""),
                    "status_quarentena": limpar_texto(r.get("status_quarentena"), "LIBERADO"),
                    "feedback_cliente_status": limpar_texto(r.get("feedback_cliente_status"), ""),
                    "motivo_cancelamento": limpar_texto(r.get("motivo_cancelamento"), ""),
                    "data_cancelamento": limpar_texto(r.get("data_cancelamento"), ""),
                    "aliquota_iss": float(r.get("aliquota_iss", 5.0) or 5.0),
                    "cnpj_tomador": limpar_texto(r.get("cnpj_tomador"), ""),
                    "natureza_operacao": limpar_texto(r.get("natureza_operacao"), "PRESTAÇÃO DE SERVIÇOS TÉCNICOS HOSPITALARES"),
                    "cfop": limpar_texto(r.get("cfop"), "5.933"),
                })

        except Exception:
            pass

        remessas_lista = []
        try:
            df_rem = pd.read_sql_query("SELECT * FROM remessas_diagnostico ORDER BY id DESC LIMIT 60", conn)
            for _, r in df_rem.iterrows():
                remessas_lista.append({
                    "id": int(r.get("id", 0)),
                    "numero_remessa": limpar_texto(r.get("numero_remessa"), ""),
                    "os_id": limpar_texto(r.get("os_id"), ""),
                    "cliente_origem": limpar_texto(r.get("cliente_origem"), ""),
                    "cidade_origem": limpar_texto(r.get("cidade_origem"), ""),
                    "uf_origem": limpar_texto(r.get("uf_origem"), "CE"),
                    "cnpj_origem": limpar_texto(r.get("cnpj_origem"), ""),
                    "destinatario_nome": limpar_texto(r.get("destinatario_nome"), ""),
                    "destinatario_cnpj": limpar_texto(r.get("destinatario_cnpj"), ""),
                    "cidade_destino": limpar_texto(r.get("cidade_destino"), ""),
                    "uf_destino": limpar_texto(r.get("uf_destino"), "SP"),
                    "cfop": limpar_texto(r.get("cfop"), "6.915"),
                    "descricao_peca": limpar_texto(r.get("descricao_peca"), ""),
                    "numero_serie": limpar_texto(r.get("numero_serie"), ""),
                    "quantidade": int(r.get("quantidade", 1)),
                    "valor_declarado": float(r.get("valor_declarado", 0.0)),
                    "motivo_diagnostico": limpar_texto(r.get("motivo_diagnostico"), ""),
                    "modalidade_transporte": limpar_texto(r.get("modalidade_transporte"), "TRANSPORTADORA"),
                    "transportadora": limpar_texto(r.get("transportadora"), ""),
                    "codigo_rastreio": limpar_texto(r.get("codigo_rastreio"), ""),
                    "tecnico_portador": limpar_texto(r.get("tecnico_portador"), ""),
                    "status_remessa": limpar_texto(r.get("status_remessa"), "EM_TRANSITO"),
                    "data_envio": limpar_texto(r.get("data_envio"), ""),
                    "data_retorno_prevista": limpar_texto(r.get("data_retorno_prevista"), ""),
                    "data_retorno_real": limpar_texto(r.get("data_retorno_real"), ""),
                    "observacoes": limpar_texto(r.get("observacoes"), ""),
                })
        except Exception:
            pass

        despesas_lista = []
        try:
            df_desp = pd.read_sql_query("SELECT * FROM despesas_recorrentes ORDER BY dia_vencimento ASC", conn)
            for _, r in df_desp.iterrows():
                despesas_lista.append({
                    "id": int(r.get("id", 0)),
                    "categoria": limpar_texto(r.get("categoria"), "OUTROS"),
                    "descricao": limpar_texto(r.get("descricao"), ""),
                    "fornecedor": limpar_texto(r.get("fornecedor"), ""),
                    "valor_mensal_estimado": float(r.get("valor_mensal_estimado", 0.0) or 0.0),
                    "dia_vencimento": int(r.get("dia_vencimento", 10) or 10),
                    "forma_pagamento": limpar_texto(r.get("forma_pagamento"), "BOLETO"),
                    "status": limpar_texto(r.get("status"), "ATIVO"),
                    "observacoes": limpar_texto(r.get("observacoes"), ""),
                })
        except Exception:
            pass

        transportadoras_lista = []
        try:
            df_transp = pd.read_sql_query("SELECT * FROM transportadoras_parceiras ORDER BY possui_seguro_carga DESC, avaliacao_estrelas DESC, id ASC", conn)
            for _, r in df_transp.iterrows():
                transportadoras_lista.append({
                    "id": int(r.get("id", 0)),
                    "nome": limpar_texto(r.get("nome"), ""),
                    "cnpj": limpar_texto(r.get("cnpj"), ""),
                    "telefone": limpar_texto(r.get("telefone"), ""),
                    "whatsapp": limpar_texto(r.get("whatsapp"), ""),
                    "contato_responsavel": limpar_texto(r.get("contato_responsavel"), ""),
                    "cidades_atendidas": limpar_texto(r.get("cidades_atendidas"), ""),
                    "tipos_veiculo": limpar_texto(r.get("tipos_veiculo"), ""),
                    "possui_seguro_carga": int(r.get("possui_seguro_carga", 1) or 0),
                    "valor_cobertura_seguro": float(r.get("valor_cobertura_seguro", 0.0) or 0.0),
                    "avaliacao_estrelas": int(r.get("avaliacao_estrelas", 5) or 5),
                    "status": limpar_texto(r.get("status"), "ATIVO"),
                    "observacoes": limpar_texto(r.get("observacoes"), ""),
                })
        except Exception:
            pass

        cotacoes_lista = []
        try:
            df_cot = pd.read_sql_query("SELECT * FROM cotacoes_transporte ORDER BY id DESC LIMIT 100", conn)
            for _, r in df_cot.iterrows():
                cotacoes_lista.append({
                    "id": int(r.get("id", 0)),
                    "numero_cotacao": limpar_texto(r.get("numero_cotacao"), ""),
                    "os_id": limpar_texto(r.get("os_id"), ""),
                    "cliente": limpar_texto(r.get("cliente"), ""),
                    "carga_descricao": limpar_texto(r.get("carga_descricao"), ""),
                    "origem_cidade": limpar_texto(r.get("origem_cidade"), "FORTALEZA"),
                    "origem_uf": limpar_texto(r.get("origem_uf"), "CE"),
                    "destino_cidade": limpar_texto(r.get("destino_cidade"), ""),
                    "destino_uf": limpar_texto(r.get("destino_uf"), "CE"),
                    "tipo_veiculo": limpar_texto(r.get("tipo_veiculo"), "Caminhão Munck"),
                    "peso_kg": float(r.get("peso_kg", 0.0) or 0.0),
                    "dimensoes": limpar_texto(r.get("dimensoes"), ""),
                    "valor_declarado_carga": float(r.get("valor_declarado_carga", 0.0) or 0.0),
                    "exige_seguro": int(r.get("exige_seguro", 1) or 0),
                    "transportadora_escolhida": limpar_texto(r.get("transportadora_escolhida"), ""),
                    "valor_fechado": float(r.get("valor_fechado", 0.0) or 0.0),
                    "status_cotacao": limpar_texto(r.get("status_cotacao"), "EM COTAÇÃO"),
                    "data_cotacao": limpar_texto(r.get("data_cotacao"), ""),
                    "data_prevista_transporte": limpar_texto(r.get("data_prevista_transporte"), ""),
                    "observacoes": limpar_texto(r.get("observacoes"), ""),
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







    ordens_abertas = [o for o in ordens if not (o.get("status") or "").upper().startswith("CONCLU") and not (o.get("status") or "").upper().startswith("FINAL")]

    tv_criticas = sum(1 for o in ordens_abertas if o.get("categoria_tv") == "CRITICA")

    tv_peca = sum(1 for o in ordens_abertas if o.get("categoria_tv") == "PECA_ORCAMENTO")

    tv_programadas = len(ordens_abertas) - tv_criticas - tv_peca



    orc_pendentes = sum(1 for o in ordens if o.get("eh_orcamento_pendente"))



    media_sat = round(sum(p["nota"] for p in pesquisas) / len(pesquisas), 1) if pesquisas else 5.0



    pecas_zeradas = sum(1 for p in estoque if p["quantidade"] <= 0)



    pecas_abaixo_minimo = sum(1 for p in estoque if p["quantidade"] <= p.get("estoque_minimo", 1))



    pre_atendimentos_cont = sum(1 for o in ordens if o.get("pre_atendimento") and not (o.get("status") or "").upper().startswith("CONCLU"))







    banco_respostas = []



    try:



        with get_db_connection(DB_NAME) as conn:



            cur = conn.cursor()



            cur.execute("""



                CREATE TABLE IF NOT EXISTS banco_respostas_tecnicos (



                    id INTEGER PRIMARY KEY AUTOINCREMENT,



                    tecnico TEXT NOT NULL DEFAULT 'GERAL',



                    categoria TEXT NOT NULL DEFAULT 'SERVICOS_EXECUTADOS',



                    titulo TEXT NOT NULL,



                    texto TEXT NOT NULL,



                    equipamento_tipo TEXT DEFAULT 'TODOS',



                    criado_em TEXT DEFAULT CURRENT_TIMESTAMP



                )



            """)



            conn.commit()



            cur.execute("SELECT id, tecnico, categoria, titulo, texto, equipamento_tipo, criado_em FROM banco_respostas_tecnicos ORDER BY id DESC")



            for r in cur.fetchall():



                banco_respostas.append({



                    "id": r[0],



                    "tecnico": r[1],



                    "categoria": r[2],



                    "titulo": r[3],



                    "texto": r[4],



                    "equipamento_tipo": r[5],



                    "criado_em": r[6]



                })



    except Exception as e:



        print("Erro ao carregar banco_respostas no bootstrap:", e)







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



        "pecas_zeradas": sum(1 for p in estoque if p["quantidade"] <= 0),

        "pecas_abaixo_minimo": sum(1 for p in estoque if p["quantidade"] <= p.get("estoque_minimo", 1)),

        "total_itens_estoque": len(estoque),

        "itens_com_saldo": sum(1 for p in estoque if p["quantidade"] > 0),

        "valor_total_estoque": sum(p.get("valor_total", 0.0) for p in estoque),



        "pre_atendimentos_cont": pre_atendimentos_cont,



    }







    logs_auditoria = []
    try:
        df_aud = pd.read_sql_query("SELECT * FROM auditoria_exclusoes ORDER BY id DESC LIMIT 50", conn)
        for _, r in df_aud.iterrows():
            logs_auditoria.append({
                "id": int(r.get("id", 0)),
                "tabela": limpar_texto(r.get("tabela_alvo"), ""),
                "registro_id": limpar_texto(r.get("registro_id"), ""),
                "usuario": limpar_texto(r.get("usuario"), ""),
                "data_hora": limpar_texto(r.get("data_hora"), ""),
                "ip_origem": limpar_texto(r.get("ip_origem"), ""),
                "justificativa": limpar_texto(r.get("justificativa"), ""),
            })
    except Exception:
        pass

    payload = {
        "logs_auditoria": logs_auditoria,



        "ok": True,



        "timestamp": obter_agora_brasil_str("%d/%m/%Y %H:%M:%S"),



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

        "ferramentas": ferramentas,



        "baixas_consumiveis": baixas_cons,



        "notas_fiscais": notas,
        "remessas_diagnostico": remessas_lista,
        "despesas_recorrentes": despesas_lista,
        "transportadoras_parceiras": transportadoras_lista,
        "cotacoes_transporte": cotacoes_lista,



        "pesquisas_satisfacao": pesquisas,



        "alarmes_calibracao": alarmes_cal,



        "manuais": manuais_lista,



        "templates_relatorio": TEMPLATES_RELATORIO_TECNICO,



        "banco_respostas": banco_respostas,



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











async def api_iniciar_rota(request: web.Request) -> web.Response:

    """Registra início de deslocamento do técnico para o cliente e ativa rota (fuso Brasil)."""

    body = await request.json()

    os_id = str(body.get("os_id", "")).strip()

    df = _carregar_df_direto()

    hora_atual = obter_agora_brasil_str("%d/%m/%Y %H:%M")



    for idx, row in df.iterrows():

        if str(obter_id_os(idx, row)) == os_id:

            df.at[idx, "status"] = "A CAMINHO"

            df.at[idx, "deslocamento_inicio_hora"] = hora_atual

            _salvar_df_direto(df)

            return web.json_response({

                "ok": True,

                "os_id": os_id,

                "cliente": limpar_texto(row.get("cliente")),

                "equipamento": limpar_texto(row.get("equipamento")),

                "deslocamento_inicio_hora": hora_atual,

                "msg": f"🚗 Rota iniciada para {limpar_texto(row.get('cliente'))} às {hora_atual}!"

            })



    return web.json_response({"ok": False, "msg": f"OS #{os_id} não encontrada."}, status=404)





async def api_checkin(request: web.Request) -> web.Response:



    body = await request.json()



    os_id = str(body.get("os_id", "")).strip()



    df = _carregar_df_direto()



    # Prioriza o horário local do celular/dispositivo do técnico (UTC-3 Brasil)

    hora_cliente = str(body.get("hora_local", "")).strip()

    if hora_cliente and len(hora_cliente) >= 16 and "/" in hora_cliente and ":" in hora_cliente:

        agora_str = hora_cliente

    else:

        agora_str = obter_agora_brasil_str("%d/%m/%Y %H:%M")







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



        ts = obter_agora_brasil_str("%Y%m%d_%H%M%S")



        caminho = os.path.join(pasta, f"{prefixo}_OS{os_id}_{ts}.{ext}")



        with open(caminho, "wb") as f:



            f.write(base64.b64decode(encoded))



        return caminho



    except Exception:



        return ""












async def api_fiscal_danfe(request: web.Request) -> web.Response:
    os_id = request.match_info.get("os_id", "").strip()
    df = _carregar_df_direto()
    row_os = None
    for idx, row in df.iterrows():
        if str(obter_id_os(idx, row)) == os_id:
            row_os = row
            break

    dados_nf = {}
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM notas_fiscais WHERE os_id = ?", (os_id,))
        r = cur.fetchone()
        if r:
            cols = [d[0] for d in cur.description]
            dados_nf = dict(zip(cols, r))

    # Fallback caso não esteja na tabela notas_fiscais ainda
    cli_nome = limpar_texto(row_os.get("cliente") if row_os is not None else dados_nf.get("cliente", "CLIENTE EMED"), "CLIENTE EMED")
    cnpj_cli = limpar_texto(row_os.get("cnpj") if row_os is not None else dados_nf.get("cnpj_tomador", ""), "00.000.000/0000-00")
    end_cli = limpar_texto(row_os.get("endereco") if row_os is not None else "", "UNIDADE HOSPITALAR")
    cid_cli = limpar_texto(row_os.get("cidade") if row_os is not None else "", "FORTALEZA")
    uf_cli = limpar_texto(row_os.get("estado") if row_os is not None else "", "CE")
    equip_nome = limpar_texto(row_os.get("equipamento") if row_os is not None else "", "EQUIPAMENTO HOSPITALAR")
    tec_nome = limpar_texto(row_os.get("tecnico_responsavel") if row_os is not None else "", "MARCOS")
    srv_tipo = limpar_texto(row_os.get("tipo_servico") if row_os is not None else "", "CORRETIVA (GERAL)")

    num_nf = dados_nf.get("numero_nf") or (row_os.get("numero_nf") if row_os is not None else "") or f"NFS-{os_id.zfill(4)}"
    st_fiscal = dados_nf.get("status_fiscal") or (row_os.get("status_fiscal") if row_os is not None else "EMITIDA")
    tipo_nota = dados_nf.get("tipo_nota") or "100% NOTA DE SERVIÇO (NFS-e)"
    dt_emissao = dados_nf.get("data_emissao") or (row_os.get("data_agendamento") if row_os is not None else "") or obter_agora_brasil_str("%d/%m/%Y")
    chave = dados_nf.get("chave_acesso") or f"2326 1003 6119 7400 0108 5500 1000 {os_id.zfill(4)} 1004 8291 3824"
    val_srv = float(dados_nf.get("valor_servicos") or 0.0)
    val_pec = float(dados_nf.get("valor_pecas") or 0.0)
    if val_srv == 0 and val_pec == 0 and row_os is not None:
        val_total_os = float(row_os.get("valor_os") or 0.0)
        val_srv = val_total_os
    val_total = val_srv + val_pec
    descr = dados_nf.get("discriminacao_servico") or f"Prestação de serviços especializados de engenharia clínica e manutenção técnica no equipamento {equip_nome}. Atendimento OS #{os_id}."

    # Peças vinculadas
    pecas = []
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT itens_solicitados, codigo_peca, tipo_origem_peca FROM solicitacoes_pecas WHERE os_id = ?", (os_id,))
        for r_p in cur.fetchall():
            pecas.append({"item": r_p[0], "codigo": r_p[1] or "PEC", "origem": r_p[2] or "NOVA_COM_NF"})

    email_cli = limpar_texto(row_os.get("email") if row_os is not None else dados_nf.get("email_cliente", ""), "")
    whats_raw = row_os.get("whatsapp") if row_os is not None else ""
    whats_cli = _limpar_telefone_exibicao(whats_raw)
    whats_digits = "".join([c for c in str(whats_raw) if c.isdigit()])
    email_env_em = dados_nf.get("email_enviado_em", "")
    lote_mes = dados_nf.get("lote_contabilidade_mes") or obter_agora_brasil_str("%Y-%m")
    try:
        partes_l = lote_mes.split("-")
        lote_mes_fmt = f"{partes_l[1]}/{partes_l[0]}" if len(partes_l) == 2 else lote_mes
    except Exception:
        lote_mes_fmt = lote_mes
    enviado_contab = dados_nf.get("enviado_contabilidade", 0)
    data_envio_contab = dados_nf.get("data_envio_contabilidade", "")

    whats_msg = f"Olá, segue o espelho oficial da Nota Fiscal Eletrônica {num_nf} (OS #{os_id}) emitida pela EMED Eletromedicina: http://localhost:8502/api/fiscal/danfe/{os_id}"
    whats_msg_enc = urllib.parse.quote(whats_msg)

    badge_status_cliente = f"Enviada em {email_env_em}" if email_env_em else "Envio Pendente"
    badge_style_cliente = "background:#dcfce7;color:#15803d;border:1px solid #86efac;" if email_env_em else "background:#fef3c7;color:#b45309;border:1px solid #fde68a;"
    txt_contab = f"✅ Lote Transmitido à Contabilidade ({data_envio_contab})" if enviado_contab else "🟡 Na fila de envio contábil no final do mês"
    cor_contab = "color:#059669;" if enviado_contab else "color:#d97706;"

    html_danfe = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>DANFE / Espelho da Nota Fiscal — OS #{os_id} ({num_nf})</title>
  <style>
    @page {{ size: A4 portrait; margin: 10mm; }}
    * {{ box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{ background: #f8fafc; margin: 0; padding: 20px; color: #0b132b; }}
    .danfe-box {{ max-width: 820px; margin: 0 auto; background: #fff; border: 2px solid #002b54; border-radius: 8px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .no-print {{ background: #002b54; color: #fff; padding: 10px 16px; margin: -20px -20px 20px -20px; border-radius: 6px 6px 0 0; display: flex; justify-content: space-between; align-items: center; }}
    .btn-print {{ background: #0077b6; color: #fff; border: none; padding: 8px 16px; font-weight: bold; border-radius: 6px; cursor: pointer; }}
    .btn-print:hover {{ background: #023e8a; }}
    .header-tbl {{ width: 100%; border-bottom: 2px solid #002b54; padding-bottom: 12px; margin-bottom: 12px; }}
    .title-danfe {{ font-size: 16px; font-weight: 900; color: #002b54; text-transform: uppercase; }}
    .badge-nf {{ background: #dcfce7; color: #15803d; border: 1.5px solid #86efac; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 11px; }}
    .sec-header {{ background: #002b54; color: #fff; font-size: 11px; font-weight: 800; padding: 5px 8px; margin: 12px 0 4px 0; border-radius: 4px; text-transform: uppercase; }}
    .data-tbl {{ width: 100%; border-collapse: collapse; font-size: 11.5px; margin-bottom: 6px; }}
    .data-tbl td, .data-tbl th {{ border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; }}
    .data-tbl th {{ background: #f1f5f9; font-weight: 700; color: #334155; }}
    .val-destaque {{ font-size: 15px; font-weight: 900; color: #059669; }}
    @media print {{
      body {{ background: #fff; padding: 0; }}
      .danfe-box {{ border: 1px solid #000; box-shadow: none; max-width: 100%; padding: 12px; }}
      .no-print {{ display: none !important; }}
    }}
  </style>
</head>
<body>
  <div class="danfe-box">
    <div class="no-print">
      <div style="font-weight: bold; font-size: 14px;">🧾 Sistema Fiscal EMED — Espelho Oficial de Nota Fiscal</div>
      <div style="display:flex;gap:6px;align-items:center;">
        <button class="btn-print" onclick="window.print()">🖨️ Imprimir / PDF</button>
        <button class="btn-print" style="background:#059669;" onclick="document.getElementById('painelEnvioCliente').scrollIntoView({{behavior:'smooth'}})">📧 Enviar p/ Cliente</button>
        <button class="btn-print" style="background:#64748b;margin-left:6px;" onclick="window.close()">✕ Fechar</button>
      </div>
    </div>

    <!-- PAINEL DE CONFERÊNCIA, ENVIO POR E-MAIL E INTEGRAÇÃO CONTÁBIL -->
    <div id="painelEnvioCliente" class="no-print" style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
        <div style="flex:1;min-width:280px;">
          <div style="font-weight:900;color:#1e3a8a;font-size:13.5px;display:flex;align-items:center;gap:6px;">
            <span>✉️ Enviar Nota Fiscal para o Cliente</span>
            <span id="badgeEnvioCliente" style="font-size:10.5px;padding:2px 8px;border-radius:4px;font-weight:bold;{badge_style_cliente}">
              {badge_status_cliente}
            </span>
          </div>
          <div style="font-size:11.5px;color:#1e40af;margin-top:2px;margin-bottom:8px;">
            Confira as informações da nota fiscal e envie diretamente para o e-mail cadastrado do cliente hospitalar.
          </div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <input type="email" id="inputEmailCliente" value="{email_cli}" placeholder="ex: faturamento@hospital.com.br"
                   style="flex:1;min-width:240px;padding:8px 10px;font-size:12px;border:1.5px solid #93c5fd;border-radius:6px;font-weight:600;outline:none;" />
            <button type="button" id="btnDispararEnvio" onclick="enviarNotaParaCliente('{os_id}')"
                    style="background:#2563eb;color:#fff;border:none;padding:8px 16px;border-radius:6px;font-weight:bold;font-size:12px;cursor:pointer;">
              🚀 Disparar E-mail
            </button>
            <a id="btnMailto" href="mailto:{email_cli}?subject=Nota%20Fiscal%20Eletronica%20{num_nf}%20-%20EMED&body=Segue%20espelho%20da%20Nota%20Fiscal%20Eletronica%20{num_nf}%20referente%20a%20OS%20#{os_id}:%20http://localhost:8502/api/fiscal/danfe/{os_id}" target="_blank"
               style="background:#fff;color:#1d4ed8;border:1.5px solid #93c5fd;padding:7px 12px;border-radius:6px;font-weight:bold;font-size:11.5px;text-decoration:none;">
              📬 Outlook / Gmail
            </a>
            <a href="https://api.whatsapp.com/send?phone=55{whats_digits}&text={whats_msg_enc}" target="_blank"
               style="background:#16a34a;color:#fff;border:none;padding:7px 12px;border-radius:6px;font-weight:bold;font-size:11.5px;text-decoration:none;">
              📲 WhatsApp
            </a>
          </div>
          <div id="msgStatusEnvio" style="margin-top:8px;font-size:11.5px;font-weight:bold;display:none;"></div>
        </div>

        <div style="background:#fff;border:1.5px solid #bfdbfe;border-radius:6px;padding:10px 14px;min-width:240px;">
          <div style="font-size:10px;font-weight:800;color:#64748b;text-transform:uppercase;">Fechamento Contábil Oficial</div>
          <div style="font-size:13px;font-weight:900;color:#0284c7;margin:2px 0;">📁 Lote Contábil: {lote_mes_fmt}</div>
          <div style="font-size:11px;font-weight:bold;{cor_contab}">
            {txt_contab}
          </div>
          <div style="font-size:9.5px;color:#64748b;margin-top:3px;">
            A nota fiscal é automaticamente agrupada para a apuração mensal do DAS/ISS pela assessoria contábil.
          </div>
        </div>
      </div>
    </div>

    <!-- CABEÇALHO EMED -->
    <table class="header-tbl">
      <tr>
        <td style="width: 140px; vertical-align: middle;">
          <img src="/api/logo-circle" alt="EMED" style="width: 100px; height: auto;" onerror="this.src='/api/logo'" />
        </td>
        <td style="vertical-align: middle;">
          <div class="title-danfe">EMED ELETROMEDICINA LTDA.</div>
          <div style="font-size: 11px; color: #0077b6; font-weight: bold; margin-top: 1px;">Eletromedicina • Manutenção em Equipamentos de Diagnóstico por Imagem</div>
          <div style="font-size: 10px; color: #475569; margin-top: 3px; line-height: 1.35;">
            <b>CNPJ:</b> 03.611.974/0001-08 &bull; <b>Insc. Municipal:</b> 123456-7<br/>
            <b>Matriz (Ceará):</b> Rua Coronel Freire, 16 - Bairro Amador, Eusébio - CE, CEP: 61769-470 &bull; <b>Fone CE:</b> (85) 3254-2929<br/>
            <b>Base Brasília (DF):</b> Rua 3, Chácara 46A, Lote 01, Setor Habitacional, Brasília - DF, CEP: 72005-670 &bull; <b>Fone DF:</b> (61) 99658-5392<br/>
            <b>Site:</b> emed.med.br &bull; <b>E-mail:</b> manutencao@emed.med.br
          </div>
        </td>
        <td style="width: 220px; vertical-align: middle; text-align: right;">
          <div style="border: 2px solid #002b54; border-radius: 6px; padding: 8px; background: #f8fafc; text-align: center;">
            <div style="font-size: 10px; font-weight: 800; color: #002b54;">DOCUMENTO AUXILIAR DA NFS-e / NF-e</div>
            <div style="font-size: 16px; font-weight: 900; color: #0b132b; margin: 3px 0;">{num_nf}</div>
            <div class="badge-nf">STATUS: {st_fiscal}</div>
            <div style="font-size: 9.5px; color: #64748b; margin-top: 4px;">Emissão: <b>{dt_emissao}</b></div>
          </div>
        </td>
      </tr>
    </table>

    <div style="background: #f1f5f9; border: 1px solid #cbd5e1; padding: 6px 10px; border-radius: 4px; font-size: 10px; margin-bottom: 8px;">
      <b>Chave de Autenticação / Protocolo Digital:</b> <span style="font-family: monospace; letter-spacing: 0.5px;">{chave}</span>
    </div>

    <!-- TOMADOR DOS SERVIÇOS -->
    <div class="sec-header">1. Dados do Tomador / Cliente Hospitalar</div>
    <table class="data-tbl">
      <tr>
        <td colspan="2"><span style="color:#64748b;">Razão Social / Nome:</span> <b>{cli_nome}</b></td>
        <td><span style="color:#64748b;">CNPJ / CPF:</span> <b>{cnpj_cli}</b></td>
      </tr>
      <tr>
        <td colspan="2"><span style="color:#64748b;">Endereço:</span> <b>{end_cli}</b></td>
        <td><span style="color:#64748b;">Município / UF:</span> <b>{cid_cli} - {uf_cli}</b></td>
      </tr>
    </table>

    <!-- DADOS DA ORDEM DE SERVIÇO -->
    <div class="sec-header">2. Identificação da Ordem de Serviço & Atendimento Técnico</div>
    <table class="data-tbl">
      <tr>
        <td><span style="color:#64748b;">OS Vinculada:</span> <b>#{os_id}</b></td>
        <td><span style="color:#64748b;">Equipamento:</span> <b>{equip_nome}</b></td>
        <td><span style="color:#64748b;">Tipo de Serviço:</span> <b>{srv_tipo}</b></td>
        <td><span style="color:#64748b;">Técnico Responsável:</span> <b>{tec_nome}</b></td>
      </tr>
    </table>

    <!-- DISCRIMINAÇÃO DOS SERVIÇOS & PEÇAS -->
    <div class="sec-header">3. Discriminação dos Serviços de Engenharia Clínica & Peças</div>
    <div style="border: 1px solid #cbd5e1; padding: 10px; border-radius: 4px; font-size: 11.5px; background: #fafafa; min-height: 80px; line-height: 1.5; margin-bottom: 8px;">
      <b>{tipo_nota}</b><br/>
      {descr}<br/><br/>
      {"<b>Peças Aplicadas no Atendimento:</b><br/>" + "".join([f"&bull; [{p['origem']}] {p['item']} (Cód: {p['codigo']})<br/>" for p in pecas]) if pecas else "<i>Nenhuma peça faturada separadamente (mão de obra e insumos inclusos no serviço clínico).</i>"}
    </div>

    <!-- QUADRO DE VALORES -->
    <div class="sec-header">4. Valores e Tributação Consolidada</div>
    <table class="data-tbl">
      <thead>
        <tr>
          <th>Valor Mão de Obra / Serviços</th>
          <th>Valor Peças / Produtos</th>
          <th>Deduções / Descontos</th>
          <th>Base de Cálculo ISS</th>
          <th>VALOR TOTAL DA NOTA FISCAL</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style="font-weight: bold; font-size: 13px;">R$ {val_srv:,.2f}</td>
          <td style="font-weight: bold; font-size: 13px;">R$ {val_pec:,.2f}</td>
          <td>R$ 0,00</td>
          <td>R$ {val_srv:,.2f}</td>
          <td class="val-destaque">R$ {val_total:,.2f}</td>
        </tr>
      </tbody>
    </table>

    <!-- INFORMAÇÕES COMPLEMENTARES -->
    <div class="sec-header">5. Informações Complementares e Fiscais</div>
    <div style="border: 1px solid #cbd5e1; padding: 8px; border-radius: 4px; font-size: 10px; color: #475569; line-height: 1.4; background: #fff;">
      &bull; DOCUMENTO EMITIDO POR ME OU EPP OPTANTE PELO SIMPLES NACIONAL.<br/>
      &bull; NÃO GERA DIREITO A CRÉDITO FISCAL DE IPI / ICMS.<br/>
      &bull; Valor aproximado dos tributos federais e municipais (IBPT): R$ {(val_total * 0.1345):,.2f} (13,45%).<br/>
      &bull; Serviços de Manutenção Preventiva/Corretiva e Validação Metrológica de Equipamentos Médicos Hospitalares em conformidade com as normas ANVISA RDC 611 e ABNT NBR IEC 60601.
    </div>

    <div style="margin-top: 14px; text-align: center; font-size: 9.5px; color: #94a3b8; border-top: 1px dashed #cbd5e1; padding-top: 8px;">
      EMED Eletromedicina Ltda. &bull; Comprovante Digital de Faturamento Homologado &bull; Emitido pelo Sistema Oficial EMED
    </div>
  </div>
  <script>
    async function enviarNotaParaCliente(osId) {{
      var email = document.getElementById('inputEmailCliente').value.trim();
      if (!email || email.indexOf('@') === -1) {{
        alert('Por favor, informe um endereço de e-mail válido para o cliente.');
        return;
      }}
      var btn = document.getElementById('btnDispararEnvio');
      var msg = document.getElementById('msgStatusEnvio');
      btn.disabled = true;
      btn.innerText = 'Enviando...';
      try {{
        var res = await fetch('/api/fiscal/enviar-cliente', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ os_id: osId, email: email }})
        }});
        var data = await res.json();
        if (data.ok) {{
          msg.style.display = 'block';
          msg.style.color = '#15803d';
          msg.innerHTML = '✅ ' + data.msg + ' &bull; Vinculada ao Lote Contábil ' + (data.lote_contabilidade || '') + '.';
          var mailto = document.getElementById('btnMailto');
          if (mailto && data.mailto_url) mailto.href = data.mailto_url;
          var badge = document.getElementById('badgeEnvioCliente');
          if (badge) {{
            badge.innerText = 'Enviada em ' + data.email_enviado_em;
            badge.style.background = '#dcfce7';
            badge.style.color = '#15803d';
            badge.style.border = '1px solid #86efac';
          }}
        }} else {{
          msg.style.display = 'block';
          msg.style.color = '#dc2626';
          msg.innerText = '⚠️ ' + (data.msg || 'Erro ao enviar e-mail.');
        }}
      }} catch (err) {{
        msg.style.display = 'block';
        msg.style.color = '#dc2626';
        msg.innerText = '⚠️ Falha de comunicação: ' + err.message;
      }} finally {{
        btn.disabled = false;
        btn.innerText = '🚀 Disparar E-mail';
      }}
    }}
  </script>
</body>
</html>"""
    return web.Response(body=html_danfe, content_type="text/html", charset="utf-8")


async def api_tecnico_assinatura_salvar(request: web.Request) -> web.Response:
    body = await request.json()
    nome = limpar_texto(body.get("nome"), "").strip().upper()
    ass_img = str(body.get("assinatura_img") or "").strip()
    ass_padrao = limpar_texto(body.get("assinatura_padrao"), "").strip()

    if not nome:
        return web.json_response({"ok": False, "msg": "Nome do técnico é obrigatório."})

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE tecnicos
            SET rubrica_img = ?, assinatura_padrao = COALESCE(NULLIF(?, ''), assinatura_padrao)
            WHERE UPPER(nome) = ?
        """, (ass_img, ass_padrao, nome))
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO tecnicos (nome, perfil, assinatura_padrao, rubrica_img)
                VALUES (?, 'Técnico', ?, ?)
            """, (nome, ass_padrao, ass_img))
        conn.commit()

    return web.json_response({
        "ok": True,
        "msg": f"✍️ Assinatura digital do técnico {nome} cadastrada e homologada com sucesso!"
    })


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







    # Horário de checkout no fuso Brasil UTC-3

    hora_cliente = str(body.get("hora_local", "")).strip()

    if hora_cliente and len(hora_cliente) >= 16 and "/" in hora_cliente and ":" in hora_cliente:

        agora_str = hora_cliente

    else:

        agora_str = obter_agora_brasil_str("%d/%m/%Y %H:%M")



    cin_atual = limpar_texto(body.get("checkin_hora"), "") or limpar_texto(row_os.get("checkin_hora"), "") or agora_str



    duracao_str = calcular_duracao_os(cin_atual, agora_str)

    if acao == "CONCLUIR":
        tec_checagem = limpar_texto(body.get("tecnico_responsavel"), limpar_texto(row_os.get("tecnico_responsavel"), "")).strip().upper()
        if not tec_checagem or "A DEFINIR" in tec_checagem or "PENDENTE" in tec_checagem:
            return web.json_response({
                "ok": False,
                "msg": "⚠️ Não é permitido concluir uma Ordem de Serviço sem um Técnico Responsável atribuído! Defina o técnico antes do fechamento."
            })







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



    elif acao == "EQUIPAMENTO_EM_USO":



        df.at[idx_alvo, "status"] = "VISITA REALIZADA (EQUIP. EM USO)"



        df.at[idx_alvo, "condicao_final"] = "EM USO CLÍNICO"



        df.at[idx_alvo, "pendencias"] = f"[REAGENDAMENTO NECESSÁRIO] Visita presencial confirmada às {agora_str}. Intervenção técnica suspensa pelo hospital pois o equipamento estava em uso clínico."



        msg_final = f"🏥 Visita técnica registrada na OS #{os_id}! Equipamento registrado em uso clínico com assinatura coletada."



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

        # -------------------------------------------------------------
        # 1. BAIXA AUTOMÁTICA DE TODAS AS PEÇAS E PEDIDOS DO ALMOXARIFADO
        # -------------------------------------------------------------
        try:
            with get_db_connection(DB_NAME) as conn_b:
                cur_b = conn_b.cursor()
                cur_b.execute("""
                    UPDATE solicitacoes_pecas 
                    SET status_pedido = 'APLICADO EM DEFINITIVO NO CLIENTE / BAIXADO',
                        confirmado_em = COALESCE(NULLIF(confirmado_em, ''), ?)
                    WHERE (os_id = ? OR destino_cliente LIKE ? OR destino_cliente LIKE ?)
                      AND UPPER(status_pedido) NOT LIKE '%APLICADO%'
                      AND UPPER(status_pedido) NOT LIKE '%BAIXADO%'
                      AND UPPER(status_pedido) NOT LIKE '%RECUSADO%'
                """, (agora_str, str(os_id), f"%[OS #{os_id}]%", f"%OS #{os_id}%"))

                # -------------------------------------------------------------
                # 2. DELAY DE VALIDAÇÃO / FEEDBACK DO CLIENTE ANTES DE LIBERAR NF (24H)
                # -------------------------------------------------------------
                dt_lib = obter_agora_brasil() + timedelta(hours=24)
                data_lib_str = dt_lib.strftime("%d/%m/%Y %H:%M")
                cur_b.execute("""
                    UPDATE notas_fiscais
                    SET status_fiscal = 'QUARENTENA PÓS-SERVIÇO (AGUARDANDO FEEDBACK DO CLIENTE)',
                        status_quarentena = 'QUARENTENA_FEEDBACK',
                        data_liberacao_fiscal = ?,
                        feedback_cliente_status = 'PENDENTE_FEEDBACK'
                    WHERE os_id = ? AND (status_quarentena IS NULL OR status_quarentena = 'LIBERADO' OR status_quarentena = '')
                """, (data_lib_str, int(os_id)))
                conn_b.commit()
        except Exception as e_baixa:
            print("Aviso baixa automatica / quarentena:", e_baixa)

        limpar_rascunho_provisorio(DB_NAME, os_id)
        msg_final = f"🏁 OS #{os_id} CONCLUÍDA! Peça baixada no almoxarifado e fatura em período de feedback com o cliente (24h) antes da NF."







    _salvar_df_direto(df)



    return web.json_response({"ok": True, "os_id": os_id, "status": df.at[idx_alvo, "status"], "msg": msg_final})











async def api_nova_os(request: web.Request) -> web.Response:
    body = await request.json()
    cliente = limpar_texto(body.get('cliente'), '').upper()
    equipamento = limpar_texto(body.get('equipamento'), '').upper()
    defeito = limpar_texto(body.get('defeito_relatado'), 'MANUTENÇÃO PREVENTIVA / CADASTRO PARQUE').upper()
    if not cliente or not equipamento:
        return web.json_response({'ok': False, 'msg': 'Informe o Cliente e o Equipamento.'}, status=400)

    tipo_srv = limpar_texto(body.get('tipo_servico'), 'CORRETIVA').upper()
    tec_resp_raw = limpar_texto(body.get('tecnico_responsavel'), '').upper()
    tem_tecnico_definido = bool(tec_resp_raw and tec_resp_raw not in ['A DEFINIR', 'A DEFINIR / TRIAGEM PENDENTE', 'SEM TÉCNICO', 'N/D', 'NONE'])
    tec_resp = tec_resp_raw if tem_tecnico_definido else 'A DEFINIR / TRIAGEM PENDENTE'
    tec_aux = limpar_texto(body.get('tecnico_auxiliar'), 'NENHUM (INDIVIDUAL)').upper()
    data_ag = limpar_texto(body.get('data_agendamento'), obter_agora_brasil().strftime('%Y-%m-%d'))
    resp_hosp = limpar_texto(body.get('responsavel_hospital'), '').upper()
    contato = _limpar_telefone_exibicao(body.get('contato_responsavel') or body.get('whatsapp'))
    endereco = limpar_texto(body.get('endereco'), 'UNIDADE HOSPITALAR').upper()
    cidade = limpar_texto(body.get('cidade'), 'FORTALEZA').upper()
    cnpj = limpar_texto(body.get('cnpj'), '')
    respostas_triagem = limpar_texto(body.get('respostas_triagem'), '')

    # Triagem de ferramentas calibradas e materiais específicos de acordo com o chamado
    kit_sug = obter_kit_por_servico(tipo_srv, defeito, equipamento)
    itens_com_disp = verificar_disponibilidade_ferramentas(DB_NAME, kit_sug.get('itens', []))
    itens_mat_str = f'[{kit_sug["nome"]}] ' + ' | '.join(itens_com_disp)

    # 1. Auditoria Financeira Interna:
    # A OS NUNCA é bloqueada e NUNCA recebe diferenciação visual ou tag que suje o relato/laudo do cliente
    info_pend = verificar_pendencias_financeiras_cliente(DB_NAME, cliente, cnpj)
    tem_pendencia = info_pend.get('tem_pendencia', False)
    val_pend = info_pend.get('valor_total', 0.0)
    qtd_fat = info_pend.get('qtd_faturas', 0)
    faturas_lista = info_pend.get('faturas', [])

    df = _carregar_df_direto()
    novo_id = int(df['id'].max() + 1) if ('id' in df.columns and not df.empty and pd.notna(df['id'].max())) else (len(df) + 1)

    # OS 100% LIMPA: Discrição absoluta. Relato e campos operacionais sem nenhuma marcação para o técnico/cliente
    nova_linha = {
        'id': novo_id,
        'cliente': cliente,
        'cnpj': cnpj,
        'cidade': cidade,
        'estado': 'CE',
        'equipamento': equipamento,
        'endereco': endereco,
        'tipo_servico': tipo_srv,
        'data_agendamento': data_ag,
        'tecnico_responsavel': tec_resp,
        'tecnico_auxiliar': tec_aux,
        'responsavel_hospital': resp_hosp,
        'contato_responsavel': contato if contato != 'N/D' else '',
        'whatsapp': contato if contato != 'N/D' else '',
        'confirmado': 'SIM',
        'pendencias': f'[CHAMADO ABERTO] {defeito}',
        'status': 'ATIVO',
        'defeito_relatado': defeito,
        'pre_atendimento': respostas_triagem,
        'instrumento_necessario': itens_mat_str,
        'condicao_inicial': limpar_texto(body.get('condicao_inicial'), 'OPERANDO COM FALHA').upper(),
        'condicao_final': 'LIBERADO PARA USO NORMAL',
        'valor_os': 0.0,
    }
    df_novo = pd.concat([df, pd.DataFrame([nova_linha])], ignore_index=True)
    _salvar_df_direto(df_novo)

    # 2. Retaguarda do SETOR FINANCEIRO / COBRANÇA acionada internamente se houver pendências
    if tem_pendencia:
        try:
            with get_db_connection(DB_NAME) as conn:
                cur = conn.cursor()
                resumo_fats = ', '.join([f"{f.get('numero')} (R$ {f.get('valor', 0):,.2f})" for f in faturas_lista[:5]])
                cur.execute('''
                    INSERT INTO solicitacoes_pecas
                    (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido, os_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'SETOR FINANCEIRO / COBRANÇA',
                    f'{cliente} ({equipamento}) [OS #{novo_id}]',
                    f'COBRANÇA EMERGENCIAL: Cliente possui R$ {val_pend:,.2f} pendente em {qtd_fat} fatura(s)/OS.',
                    f'FATURAS EM ABERTO: {resumo_fats}',
                    'PENDENTE COBRANÇA FINANCEIRA',
                    obter_agora_brasil_str('%d/%m/%Y %H:%M'),
                    str(novo_id)
                ))
                conn.commit()
        except Exception:
            pass

    # 3. O sistema gera a solicitação de separação do material no Almoxarifado conforme a necessidade do chamado,
    # mesmo antes de definir o técnico de campo.
    try:
        acionar_separacao_automatica_almoxarifado(
            db_path=DB_NAME,
            tecnico=tec_resp if tem_tecnico_definido else 'AGUARDANDO DEFINIÇÃO TÉCNICO',
            cliente=cliente,
            equipamento=equipamento,
            tipo_servico=tipo_srv,
            instrumentos_materiais=itens_mat_str,
            pecas=defeito,
            os_id=novo_id
        )
    except Exception:
        pass

    msg_retorno = f'✅ Ordem de Serviço #{novo_id} emitida! Materiais solicitados ao Almoxarifado.'
    if tem_tecnico_definido:
        msg_retorno += f' Atribuído para {tec_resp}.'
    else:
        msg_retorno += ' Aguardando designação de técnico de campo.'

    return web.json_response({
        'ok': True,
        'os_id': str(novo_id),
        'kit_acionado': kit_sug['nome'],
        'itens_kit': itens_com_disp,
        'tem_pendencia_financeira': tem_pendencia,
        'valor_pendente': val_pend,
        'qtd_pendencias': qtd_fat,
        'msg': msg_retorno,
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

    """Despacha em bloco todos os chamados ativos de um hospital/rota para um técnico e aciona a triagem de materiais."""

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

    kits_acionados = []



    for idx, row in df.iterrows():

        oid = str(obter_id_os(idx, row))

        if oid in os_ids:

            df.at[idx, "tecnico_responsavel"] = tecnico

            df.at[idx, "tecnico_auxiliar"] = auxiliar

            df.at[idx, "telefone_tecnico"] = tel_t

            df.at[idx, "confirmado"] = "SIM"

            qtd += 1



            # Triagem de material e acionamento automático do Almoxarifado

            tipo_srv = limpar_texto(row.get("tipo_servico"), "CORRETIVA").upper()

            defeito = limpar_texto(row.get("defeito_relatado"), "").upper()

            cliente_os = limpar_texto(row.get("cliente"), "")

            equip_os = limpar_texto(row.get("equipamento"), "")

            kit_sug = obter_kit_por_servico(tipo_srv, defeito)

            df.at[idx, "instrumento_necessario"] = kit_sug["nome"]



            try:

                itens_mat = f"[{kit_sug['nome']}] " + ", ".join(kit_sug.get("itens", []))

                acionar_separacao_automatica_almoxarifado(

                    db_path=DB_NAME,

                    tecnico=tecnico,

                    cliente=cliente_os,

                    equipamento=equip_os,

                    tipo_servico=tipo_srv,

                    instrumentos_materiais=itens_mat,

                    pecas=defeito,

                    os_id=oid

                )

                kits_acionados.append(f"OS #{oid}: {kit_sug['nome']}")

            except Exception:

                pass



    _salvar_df_direto(df)

    msg_almox = f" (Triagem concluída: {', '.join(kits_acionados)})" if kits_acionados else ""

    return web.json_response({

        "ok": True,

        "msg": f"🚚 Rota despachada! {qtd} chamado(s) atribuído(s) para {tecnico}. Almoxarifado acionado com kits.{msg_almox}"

    })











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



    agora = obter_agora_brasil_str("%d/%m/%Y %H:%M")







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

    """Adiciona ou atualiza item no estoque + tabela de precificação dinâmica por consumidor + local."""

    body = await request.json()

    codigo = limpar_texto(body.get("codigo"), "").upper()

    nome_peca = limpar_texto(body.get("nome_peca"), "").upper()

    categoria = limpar_texto(body.get("categoria"), "PEÇA").upper()

    quantidade = int(limpar_float(body.get("quantidade"), 1))

    preco = limpar_float(body.get("preco_unitario"), 0.0)

    preco_custo = limpar_float(body.get("preco_custo"), preco)

    m_contrato = limpar_float(body.get("margem_contrato"), 30.0)

    m_avulso = limpar_float(body.get("margem_avulso"), 60.0)

    m_avista = limpar_float(body.get("margem_avista"), 20.0)

    m_desestimulo = limpar_float(body.get("margem_desestimulo"), 180.0)

    localizacao = limpar_texto(body.get("localizacao"), "ALMOXARIFADO CENTRAL").upper()

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

                SET nome_peca = ?, categoria = ?, quantidade = ?, preco_unitario = ?, preco_custo = ?,

                    margem_contrato = ?, margem_avulso = ?, margem_avista = ?, margem_desestimulo = ?,

                    localizacao = ?, data_validade_calibracao = ?, certificado_calibracao = ?

                WHERE UPPER(codigo) = ?

            """, (nome_peca, categoria, quantidade, preco, preco_custo, m_contrato, m_avulso, m_avista, m_desestimulo, localizacao, validade_cal, cert_cal, codigo))

        else:

            cur.execute("""

                INSERT INTO estoque_pecas

                (codigo, nome_peca, categoria, quantidade, estoque_minimo, preco_unitario, preco_custo,

                 margem_contrato, margem_avulso, margem_avista, margem_desestimulo,

                 localizacao, data_validade_calibracao, certificado_calibracao)

                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """, (codigo, nome_peca, categoria, quantidade, preco, preco_custo, m_contrato, m_avulso, m_avista, m_desestimulo, localizacao, validade_cal, cert_cal))

        conn.commit()



    return web.json_response({"ok": True, "msg": f"✅ Item '{codigo} — {nome_peca}' salvo com precificação por consumidor!"})





async def api_calibracao_equipamento(request: web.Request) -> web.Response:



    body = await request.json()



    os_id = int(limpar_float(body.get("os_id"), 0))



    dt_ult = limpar_texto(body.get("data_ultima"), obter_agora_brasil_str("%d/%m/%Y"))



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

    if ok and os_id and os_id != "AVULSO":
        try:
            with get_db_connection(DB_NAME) as conn_sat:
                cur_sat = conn_sat.cursor()
                os_num = int(os_id) if os_id.isdigit() else 0
                if nota >= 3:
                    cur_sat.execute("""
                        UPDATE notas_fiscais
                        SET status_quarentena = 'LIBERADO_PELO_CLIENTE',
                            status_fiscal = 'LIBERADO PARA EMISSÃO DE NOTA FISCAL (FEEDBACK OK)',
                            feedback_cliente_status = ?
                        WHERE os_id = ?
                    """, (f"APROVADO PELO CLIENTE ({nota}⭐)", os_num))
                else:
                    cur_sat.execute("""
                        UPDATE notas_fiscais
                        SET status_quarentena = 'BLOQUEADO_REVISAO',
                            status_fiscal = 'PAUSADO (CLIENTE SOLICITOU AJUSTE/REVISÃO)',
                            feedback_cliente_status = ?
                        WHERE os_id = ?
                    """, (f"ALERTA_REVISAO ({nota}⭐)", os_num))
                conn_sat.commit()
        except Exception:
            pass



    return web.json_response({"ok": ok, "msg": msg, "google_url": obter_url_google_review(DB_NAME)})













async def api_kardex(request: web.Request) -> web.Response:

    """Consulta o histórico de movimentações (Kardex) do Almoxarifado."""

    q = request.query.get("q", "").strip().upper()

    limite = int(request.query.get("limite", 60))

    movs = []

    with get_db_connection(DB_NAME) as conn:

        try:

            if q:

                df_k = pd.read_sql_query("""

                    SELECT * FROM movimentacoes_estoque 

                    WHERE UPPER(codigo_item) LIKE ? OR UPPER(descricao) LIKE ? OR UPPER(numero_nf) LIKE ?

                    ORDER BY id DESC LIMIT ?

                """, conn, params=(f"%{q}%", f"%{q}%", f"%{q}%", limite))

            else:

                df_k = pd.read_sql_query("SELECT * FROM movimentacoes_estoque ORDER BY id DESC LIMIT ?", conn, params=(limite,))

            for _, r in df_k.iterrows():

                movs.append({

                    "id": int(r.get("id", 0)),

                    "estabelecimento": limpar_texto(r.get("estabelecimento"), "FORTALEZA"),

                    "centro_estoque": limpar_texto(r.get("centro_estoque"), "ALMOXARIFADO"),

                    "codigo_item": limpar_texto(r.get("codigo_item"), ""),

                    "descricao": limpar_texto(r.get("descricao"), ""),

                    "grupo_itens": limpar_texto(r.get("grupo_itens"), ""),

                    "data_mov": limpar_texto(r.get("data_mov"), ""),

                    "hora_mov": limpar_texto(r.get("hora_mov"), ""),

                    "tipo_mov": limpar_texto(r.get("tipo_mov"), ""),

                    "qtd_entrada": limpar_float(r.get("qtd_entrada"), 0.0),

                    "qtd_saida": limpar_float(r.get("qtd_saida"), 0.0),

                    "saldo": limpar_float(r.get("saldo"), 0.0),

                    "custo_medio": limpar_float(r.get("custo_medio"), 0.0),

                    "numero_nf": limpar_texto(r.get("numero_nf"), ""),

                    "documento": limpar_texto(r.get("documento"), ""),

                    "observacao": limpar_texto(r.get("observacao"), ""),

                })

        except Exception as e:

            print("Erro ao consultar kardex:", e)

    return web.json_response({"ok": True, "total": len(movs), "movimentacoes": movs})







async def api_ferramentas_listar(request: web.Request) -> web.Response:

    """Retorna a lista atualizada de todas as ferramentas e instrumentos com seus status de cautela."""

    ferramentas = []

    with get_db_connection(DB_NAME) as conn:

        try:

            df_fer = pd.read_sql_query("SELECT * FROM ferramentas_cautela ORDER BY id ASC", conn)

            for _, r in df_fer.iterrows():

                ferramentas.append({

                    "id": int(r.get("id", 0)),

                    "codigo": limpar_texto(r.get("codigo_ferramenta"), ""),

                    "nome": limpar_texto(r.get("nome_ferramenta"), ""),

                    "status": limpar_texto(r.get("status"), "DISPONIVEL").upper(),

                    "tecnico": limpar_texto(r.get("tecnico_responsavel"), "").upper(),

                    "cliente": limpar_texto(r.get("destino_cliente"), "").upper(),

                    "os_id": limpar_texto(r.get("os_id"), ""),

                    "data_saida": limpar_texto(r.get("data_saida"), ""),

                    "numero_serie": limpar_texto(r.get("numero_serie"), ""),

                    "localizacao": limpar_texto(r.get("localizacao"), "ALMOXARIFADO CENTRAL"),

                    "validade_calibracao": limpar_texto(r.get("data_validade_calibracao"), ""),

                    "certificado": limpar_texto(r.get("certificado_calibracao"), ""),

                    "observacao": limpar_texto(r.get("observacao"), "")

                })

        except Exception as e:

            print("Erro ao listar ferramentas:", e)

    return web.json_response({"ok": True, "ferramentas": ferramentas})





async def api_ferramentas_acao(request: web.Request) -> web.Response:

    """Registra movimentação via leitor de código de barras ou manual do Paulo."""

    body = await request.json()

    codigo = limpar_texto(body.get("codigo"), "").upper()

    acao = limpar_texto(body.get("acao"), "RETIRADA").upper()

    tecnico = limpar_texto(body.get("tecnico"), "").upper()

    cliente = limpar_texto(body.get("cliente"), "").upper()

    os_id = str(body.get("os_id", "")).strip()

    obs = limpar_texto(body.get("observacao"), "")

    operador = limpar_texto(body.get("operador"), "PAULO (ALMOXARIFADO)").upper()

    agora = obter_agora_brasil_str("%d/%m/%Y %H:%M")



    with get_db_connection(DB_NAME) as conn:

        cur = conn.cursor()

        cur.execute("SELECT id, nome_ferramenta, status FROM ferramentas_cautela WHERE UPPER(codigo_ferramenta) = ? OR UPPER(numero_serie) = ?", (codigo, codigo))

        row = cur.fetchone()

        if not row:

            return web.json_response({"ok": False, "msg": f"❌ Ferramenta '{codigo}' não encontrada no cadastro do Almoxarifado!"}, status=404)



        f_id, f_nome, f_status = row[0], str(row[1]), str(row[2]).upper()



        if acao == "RETIRADA":

            if not tecnico:

                return web.json_response({"ok": False, "msg": "Selecione o técnico responsável pela retirada."}, status=400)

            cur.execute("""

                UPDATE ferramentas_cautela 

                SET status = 'EM_USO', tecnico_responsavel = ?, destino_cliente = ?, os_id = ?, data_saida = ?, observacao = ?

                WHERE id = ?

            """, (tecnico, cliente, os_id, agora, obs, f_id))

            cur.execute("""

                INSERT INTO historico_cautela_ferramentas (codigo_ferramenta, nome_ferramenta, tipo_acao, tecnico, destino_cliente, os_id, operador, data_hora, observacao)

                VALUES (?, ?, 'RETIRADA', ?, ?, ?, ?, ?, ?)

            """, (codigo, f_nome, tecnico, cliente, os_id, operador, agora, obs))

            msg = f"📤 Ferramenta {codigo} entregue para 👷 {tecnico} com sucesso!"



        elif acao == "DEVOLUCAO":
            aviso_entrega = obter_instrucao_ferramenta(codigo, "ENTREGA")
            cur.execute("""
                UPDATE ferramentas_cautela 
                SET status = 'DISPONIVEL', tecnico_responsavel = '', destino_cliente = '', os_id = '', data_devolucao = ?, observacao = ?
                WHERE id = ?
            """, (agora, obs, f_id))
            cur.execute("""
                INSERT INTO historico_cautela_ferramentas (codigo_ferramenta, nome_ferramenta, tipo_acao, tecnico, destino_cliente, os_id, operador, data_hora, observacao)
                VALUES (?, ?, 'DEVOLUCAO', '', '', '', ?, ?, ?)
            """, (codigo, f_nome, operador, agora, obs))
            msg = f"📥 Ferramenta {codigo} devolvida ao Almoxarifado! {aviso_entrega}"



        elif acao == "CALIBRACAO_BANCADA":

            cur.execute("""

                UPDATE ferramentas_cautela 

                SET status = 'CALIBRACAO_BANCADA', tecnico_responsavel = 'BANCADA / CALIBRAÇÃO RBC', destino_cliente = 'LABORATÓRIO', data_saida = ?, observacao = ?

                WHERE id = ?

            """, (agora, obs, f_id))

            cur.execute("""

                INSERT INTO historico_cautela_ferramentas (codigo_ferramenta, nome_ferramenta, tipo_acao, tecnico, destino_cliente, os_id, operador, data_hora, observacao)

                VALUES (?, ?, 'ENVIO_CALIBRACAO', 'LABORATÓRIO', 'BANCADA', '', ?, ?, ?)

            """, (codigo, f_nome, operador, agora, obs))

            msg = f"🔬 Ferramenta {codigo} encaminhada para Bancada / Calibração RBC!"



        elif acao == "RETORNO_CALIBRACAO":

            nova_val = limpar_texto(body.get("validade_calibracao"), "")

            novo_cert = limpar_texto(body.get("certificado"), "")

            cur.execute("""

                UPDATE ferramentas_cautela 

                SET status = 'DISPONIVEL', tecnico_responsavel = '', destino_cliente = '', os_id = '', data_devolucao = ?, 

                    data_validade_calibracao = CASE WHEN ? != '' THEN ? ELSE data_validade_calibracao END,

                    certificado_calibracao = CASE WHEN ? != '' THEN ? ELSE certificado_calibracao END,

                    observacao = ?

                WHERE id = ?

            """, (agora, nova_val, nova_val, novo_cert, novo_cert, obs, f_id))

            cur.execute("""

                INSERT INTO historico_cautela_ferramentas (codigo_ferramenta, nome_ferramenta, tipo_acao, operador, data_hora, observacao)

                VALUES (?, ?, 'RETORNO_CALIBRACAO', ?, ?, ?)

            """, (codigo, f_nome, operador, agora, obs))

            msg = f"🟢 Calibração/Manutenção da Ferramenta {codigo} concluída e liberada para uso!"



        else:

            return web.json_response({"ok": False, "msg": f"Ação '{acao}' não reconhecida."}, status=400)



        conn.commit()



    return web.json_response({"ok": True, "msg": msg, "novo_status": acao})







async def api_almox_compra_acao(request: web.Request) -> web.Response:

    """Gerencia a esteira de compra e chegada de peças/ferramentas sem saldo no Almoxarifado."""

    body = await request.json()

    id_ped = int(body.get("id", 0))

    acao = limpar_texto(body.get("acao"), "").upper()

    fornecedor = limpar_texto(body.get("fornecedor"), "")

    previsao = limpar_texto(body.get("previsao_entrega"), "")

    obs = limpar_texto(body.get("observacao"), "")

    agora = obter_agora_brasil_str("%d/%m/%Y %H:%M")



    with get_db_connection(DB_NAME) as conn:

        cur = conn.cursor()

        cur.execute("SELECT itens_solicitados, status_pedido, status_compra FROM solicitacoes_pecas WHERE id = ?", (id_ped,))

        row = cur.fetchone()

        if not row:

            return web.json_response({"ok": False, "msg": f"Pedido #{id_ped} não localizado."}, status=404)



        itens_str = str(row[0])



        if acao == "SOLICITAR_COMPRA":

            novo_st_compra = "AGUARDANDO_APROVACAO"

            novo_st_pedido = "AGUARDANDO APROVAÇÃO DE COMPRA"

            cur.execute("""

                UPDATE solicitacoes_pecas 

                SET status_compra = ?, status_pedido = ?, fornecedor = ?

                WHERE id = ?

            """, (novo_st_compra, novo_st_pedido, fornecedor, id_ped))

            msg = f"🛒 Solicitação de compra do Pedido #{id_ped} registrada com sucesso!"



        elif acao == "APROVAR_COMPRA":

            novo_st_compra = "COMPRA_APROVADA"

            novo_st_pedido = "COMPRA APROVADA (EM COTAÇÃO)"

            cur.execute("""

                UPDATE solicitacoes_pecas 

                SET status_compra = ?, status_pedido = ?

                WHERE id = ?

            """, (novo_st_compra, novo_st_pedido, id_ped))

            msg = f"✅ Compra do Pedido #{id_ped} aprovada pela diretoria/coordenação!"



        elif acao in ("MARCAR_ADQUIRIDO", "ATUALIZAR_RASTREIO"):
            codigo_rastreio = limpar_texto(body.get("codigo_rastreio"), "").strip()
            transportadora = limpar_texto(body.get("transportadora"), "").strip()
            novo_st_compra = "ADQUIRIDO_AGUARDANDO_CHEGAR"
            novo_st_pedido = f"PEÇA JÁ ADQUIRIDA (PREVISÃO: {previsao or 'EM TRÂNSITO'})"
            cur.execute("""
                UPDATE solicitacoes_pecas 
                SET status_compra = ?, status_pedido = ?, previsao_entrega = ?, fornecedor = ?, codigo_rastreio = ?, transportadora = ?
                WHERE id = ?
            """, (novo_st_compra, novo_st_pedido, previsao, fornecedor, codigo_rastreio, transportadora, id_ped))
            msg = f"🚚 Pedido #{id_ped} atualizado! Aguardando chegada ({previsao})."



        elif acao == "DAR_ENTRADA_CHEGOU":

            # Dá entrada física no estoque

            partes = [p.strip() for p in itens_str.split(",") if "x " in p and "(" in p]

            for p in partes:

                try:

                    qtd_str = p.split("x ")[0].strip()

                    cod_str = p.split("(")[-1].replace(")", "").strip()

                    qtd_ent = int(qtd_str)

                    cur.execute(

                        "UPDATE estoque_pecas SET quantidade = quantidade + ? WHERE codigo = ?",

                        (qtd_ent, cod_str)

                    )

                except Exception:

                    pass



            novo_st_compra = "RECEBIDO_ALMOXARIFADO"

            novo_st_pedido = "A SEPARAR / AGUARDANDO ALMOXARIFADO"

            itens_atualizados = itens_str.replace("(SEM SALDO)", "(SALDO DISPONÍVEL - CHEGOU)")

            cur.execute("""

                UPDATE solicitacoes_pecas 

                SET status_compra = ?, status_pedido = ?, itens_solicitados = ?

                WHERE id = ?

            """, (novo_st_compra, novo_st_pedido, itens_atualizados, id_ped))

            msg = f"📦 Peça recebida no Almoxarifado! Saldo adicionado ao estoque e separação liberada."



        else:

            return web.json_response({"ok": False, "msg": f"Ação '{acao}' não reconhecida."}, status=400)



        conn.commit()



    return web.json_response({
        "ok": True,
        "msg": msg,
        "novo_status_pedido": novo_st_pedido,
        "novo_status_compra": novo_st_compra,
        "previsao_entrega": previsao,
        "codigo_rastreio": locals().get("codigo_rastreio", ""),
        "transportadora": locals().get("transportadora", "")
    })





async def api_almox_status(request: web.Request) -> web.Response:



    body = await request.json()



    id_ped = int(body.get("id", 0))



    novo_status = limpar_texto(body.get("novo_status"), "SEPARADO / ENTREGUE AO TÉCNICO")



    tecnico = limpar_texto(body.get("tecnico"), "")



    tipo_origem = limpar_texto(body.get("tipo_origem") or body.get("tipo_origem_peca"), "")



    motivo_recusa = limpar_texto(body.get("motivo_recusa") or body.get("motivo"), "")

    ok, msg = atualizar_status_solicitacao_peca(DB_NAME, id_ped, novo_status, tecnico=tecnico, tipo_origem=tipo_origem, motivo_recusa=motivo_recusa)

    return web.json_response({"ok": ok, "msg": msg, "tecnico": tecnico, "novo_status": novo_status, "tipo_origem_peca": tipo_origem, "motivo_recusa": motivo_recusa})


async def api_auditoria_excluir(request: web.Request) -> web.Response:
    """Registra exclusão com rastreabilidade forense, usuário e snapshot antes de remover o dado."""
    body = await request.json()
    tabela = str(body.get("tabela", "")).strip().lower()
    reg_id = str(body.get("id", "")).strip()
    usuario = str(body.get("usuario", "ADMIN / AUDITOR")).strip()
    justificativa = str(body.get("justificativa", "")).strip()
    ip_origem = request.remote or "127.0.0.1"

    if not tabela or not reg_id:
        return web.json_response({"ok": False, "msg": "Tabela e ID do registro são obrigatórios."}, status=400)

    if not justificativa:
        return web.json_response({"ok": False, "msg": "Motivo/Justificativa obrigatória para registro de segurança e auditoria forense."}, status=400)

    tabelas_permitidas = ["solicitacoes_pecas", "clientes_equipamentos", "ferramentas_cautela", "notas_fiscais", "baixas_consumiveis", "ordens_servico"]
    if tabela not in tabelas_permitidas:
        return web.json_response({"ok": False, "msg": f"Tabela '{tabela}' não permitida para exclusão auditada."}, status=400)

    agora_str = obter_agora_brasil_str("%d/%m/%Y %H:%M:%S")

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {tabela} WHERE id = ?", (reg_id,))
        row = cur.fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": f"Registro #{reg_id} não encontrado na tabela {tabela}."}, status=404)

        col_names = [desc[0] for desc in cur.description]
        conteudo_dict = dict(zip(col_names, row))
        conteudo_json = json.dumps(conteudo_dict, ensure_ascii=False, default=str)

        cur.execute("""
            INSERT INTO auditoria_exclusoes (tabela_alvo, registro_id, usuario, data_hora, ip_origem, justificativa, conteudo_original_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tabela, reg_id, usuario, agora_str, ip_origem, justificativa, conteudo_json))

        cur.execute(f"DELETE FROM {tabela} WHERE id = ?", (reg_id,))
        conn.commit()

    if tabela == "clientes_equipamentos":
        try:
            df_ex = pd.read_excel(CAMINHO_EXCEL)
            if "id" in df_ex.columns:
                df_ex = df_ex[df_ex["id"].astype(str) != reg_id]
            else:
                idx_int = int(reg_id) - 1
                if 0 <= idx_int < len(df_ex):
                    df_ex = df_ex.drop(idx_int)
            df_ex.to_excel(CAMINHO_EXCEL, index=False)
        except Exception as e_ex:
            print("Aviso ao remover linha do Excel:", e_ex)

    return web.json_response({
        "ok": True, 
        "msg": f"🛡️ Registro #{reg_id} excluído com sucesso e carimbado no Log de Segurança Cibernética e Auditoria!",
        "auditoria": {
            "tabela": tabela,
            "id": reg_id,
            "usuario": usuario,
            "data_hora": agora_str,
            "justificativa": justificativa
        }
    })


async def api_auditoria_listar(request: web.Request) -> web.Response:
    """Retorna o log de auditoria com as exclusões realizadas."""
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, tabela_alvo, registro_id, usuario, data_hora, ip_origem, justificativa, criado_em FROM auditoria_exclusoes ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
        lista = []
        for r in rows:
            lista.append({
                "id": r[0],
                "tabela": r[1],
                "registro_id": r[2],
                "usuario": r[3],
                "data_hora": r[4],
                "ip_origem": r[5],
                "justificativa": r[6],
                "criado_em": str(r[7] or "")
            })
    return web.json_response({"ok": True, "logs": lista})











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



    txid = f"PIX_APP_{os_id}_{obter_agora_brasil_str('%H%M%S')}"



    ok, msg = liquidar_pagamento_pix(DB_NAME, os_id, txid, metodo="APP_GESTOR_EMED")



    return web.json_response({"ok": ok, "msg": msg})











async def api_config(request: web.Request) -> web.Response:



    body = await request.json()



    url_g = limpar_texto(body.get("google_review_url"), "")



    if url_g:



        salvar_configuracao(DB_NAME, "google_review_url", url_g)



    return web.json_response({"ok": True, "google_review_url": obter_url_google_review(DB_NAME), "msg": "✅ Configuração salva no servidor EMED!"})



















# ==============================================================================



# NOVAS ROTAS OFICIAIS: BANCO DE RESPOSTAS TÉCNICAS, NOTA FISCAL & PROPOSTAS COM ESTOQUE



# ==============================================================================







async def api_respostas_tecnicas_listar(request: web.Request) -> web.Response:



    tecnico = request.query.get("tecnico", "").strip().upper()



    categoria = request.query.get("categoria", "").strip().upper()



    lista = []



    with get_db_connection(DB_NAME) as conn:



        cur = conn.cursor()



        query = "SELECT id, tecnico, categoria, titulo, texto, equipamento_tipo, criado_em FROM banco_respostas_tecnicos WHERE 1=1"



        params = []



        if tecnico and tecnico != "TODOS":



            query += " AND (tecnico = ? OR tecnico = 'GERAL')"



            params.append(tecnico)



        if categoria and categoria != "TODAS":



            query += " AND categoria = ?"



            params.append(categoria)



        query += " ORDER BY id DESC"



        cur.execute(query, tuple(params))



        for r in cur.fetchall():



            lista.append({



                "id": r[0],



                "tecnico": r[1],



                "categoria": r[2],



                "titulo": r[3],



                "texto": r[4],



                "equipamento_tipo": r[5],



                "criado_em": r[6]



            })



    return web.json_response({"ok": True, "respostas": lista})











async def api_respostas_tecnicas_salvar(request: web.Request) -> web.Response:



    body = await request.json()



    resp_id = body.get("id")



    tecnico = limpar_texto(body.get("tecnico"), "GERAL").upper()



    categoria = limpar_texto(body.get("categoria"), "SERVICOS_EXECUTADOS").upper()



    titulo = limpar_texto(body.get("titulo"), "RESPOSTA TÉCNICA PERSONALIZADA").strip()



    texto = limpar_texto(body.get("texto"), "").strip()



    equipamento_tipo = limpar_texto(body.get("equipamento_tipo"), "TODOS").upper()







    if not texto:



        return web.json_response({"ok": False, "msg": "O texto da resposta não pode ficar vazio."}, status=400)







    with get_db_connection(DB_NAME) as conn:



        cur = conn.cursor()



        if resp_id:



            cur.execute("""



                UPDATE banco_respostas_tecnicos



                SET tecnico = ?, categoria = ?, titulo = ?, texto = ?, equipamento_tipo = ?



                WHERE id = ?



            """, (tecnico, categoria, titulo, texto, equipamento_tipo, resp_id))



            msg = f"✅ Resposta '{titulo}' atualizada com sucesso!"



        else:



            cur.execute("""



                INSERT INTO banco_respostas_tecnicos (tecnico, categoria, titulo, texto, equipamento_tipo)



                VALUES (?, ?, ?, ?, ?)



            """, (tecnico, categoria, titulo, texto, equipamento_tipo))



            resp_id = cur.lastrowid



            msg = f"✅ Nova resposta '{titulo}' salva no seu Banco de Respostas!"



        conn.commit()







    return web.json_response({"ok": True, "id": resp_id, "msg": msg})











async def api_respostas_tecnicas_deletar(request: web.Request) -> web.Response:



    resp_id = request.match_info.get("id") or request.query.get("id")



    if not resp_id:



        try:



            body = await request.json()



            resp_id = body.get("id")



        except Exception:



            pass



    if not resp_id:



        return web.json_response({"ok": False, "msg": "ID não informado."}, status=400)







    with get_db_connection(DB_NAME) as conn:



        cur = conn.cursor()



        cur.execute("DELETE FROM banco_respostas_tecnicos WHERE id = ?", (resp_id,))



        conn.commit()



    return web.json_response({"ok": True, "msg": "Modelo removido do banco de respostas."})











async def api_os_nf_salvar(request: web.Request) -> web.Response:



    body = await request.json()



    os_id = str(body.get("os_id", "")).strip()



    tipo_nota = limpar_texto(body.get("tipo_nota"), "100% NOTA DE SERVIÇO (NFS-e)")



    regra_fiscal = limpar_texto(body.get("regra_fiscal"), "SERVICO_TOTAL")



    discriminacao_servico = limpar_texto(body.get("discriminacao_servico"), "")



    numero_nf = limpar_texto(body.get("numero_nf"), "").upper()



    chave_acesso = limpar_texto(body.get("chave_acesso"), "")



    status_fiscal = limpar_texto(body.get("status_fiscal"), "EMITIDA").upper()



    valor_servicos = limpar_float(body.get("valor_servicos"), 0.0)



    valor_pecas = limpar_float(body.get("valor_pecas"), 0.0)



    data_emissao = limpar_texto(body.get("data_emissao"), obter_agora_brasil_str("%d/%m/%Y"))







    df = _carregar_df_direto()



    idx_alvo = None



    row_os = None



    for idx, row in df.iterrows():



        if str(obter_id_os(idx, row)) == os_id:



            idx_alvo = idx



            row_os = row



            break







    if idx_alvo is not None:



        df.at[idx_alvo, "numero_nf"] = numero_nf



        df.at[idx_alvo, "status_fiscal"] = status_fiscal



        _salvar_df_direto(df)







    with get_db_connection(DB_NAME) as conn:



        cur = conn.cursor()



        cur.execute("SELECT id, numero_nf, status_fiscal, valor_servicos, valor_pecas, data_emissao FROM notas_fiscais WHERE os_id = ?", (os_id,))
        row_nf_check = cur.fetchone()
        confirmar_retificacao = bool(body.get("confirmar_retificacao", False))
        if row_nf_check and row_nf_check[2] == "EMITIDA" and not confirmar_retificacao:
            return web.json_response({
                "ok": False,
                "duplicidade": True,
                "numero_nf": row_nf_check[1],
                "data_emissao": row_nf_check[5],
                "valor_total": float(row_nf_check[3] or 0) + float(row_nf_check[4] or 0),
                "msg": f"⚠️ A Nota Fiscal {row_nf_check[1]} já foi emitida para a OS #{os_id}! Confirme a retificação para prosseguir."
            })
        row_nf = row_nf_check



        row_nf = cur.fetchone()



        cli_nome = limpar_texto(row_os.get("cliente") if row_os is not None else "CLIENTE EMED", "CLIENTE EMED")



        cnpj_cli = limpar_texto(row_os.get("cnpj") if row_os is not None else "", "")



        if row_nf:



            cur.execute("""



                UPDATE notas_fiscais



                SET numero_nf = ?, chave_acesso = ?, status_fiscal = ?, valor_servicos = ?, valor_pecas = ?, data_emissao = ?, tipo_nota = ?, regra_fiscal = ?, discriminacao_servico = ?, atualizado_em = CURRENT_TIMESTAMP



                WHERE os_id = ?



            """, (numero_nf, chave_acesso, status_fiscal, valor_servicos, valor_pecas, data_emissao, tipo_nota, regra_fiscal, discriminacao_servico, os_id))



        else:



            cur.execute("""



                INSERT INTO notas_fiscais (os_id, cliente, cnpj_tomador, tipo_nota, numero_nf, chave_acesso, status_fiscal, valor_servicos, valor_pecas, data_emissao, regra_fiscal, discriminacao_servico, criado_em)



                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)



            """, (os_id, cli_nome, cnpj_cli, tipo_nota, numero_nf, chave_acesso, status_fiscal, valor_servicos, valor_pecas, data_emissao, regra_fiscal, discriminacao_servico))



        conn.commit()







    return web.json_response({"ok": True, "msg": f"🧾 Dados fiscais da OS #{os_id} atualizados (NF: {numero_nf})!"})











async def api_proposta_salvar(request: web.Request) -> web.Response:



    body = await request.json()



    os_id = str(body.get("os_id", "")).strip()



    cliente = limpar_texto(body.get("cliente"), "CLIENTE").upper()



    equipamento = limpar_texto(body.get("equipamento"), "EQUIPAMENTO").upper()



    peca_codigo = limpar_texto(body.get("peca_codigo"), "").upper()



    peca_nome = limpar_texto(body.get("peca_nome"), "").upper()



    quantidade = int(limpar_float(body.get("quantidade"), 1))



    valor_unitario = limpar_float(body.get("valor_unitario"), 0.0)



    valor_total = round(quantidade * valor_unitario, 2)



    condicao_pagamento = limpar_texto(body.get("condicao_pagamento"), "FATURAMENTO 28 DDL").upper()



    prazo_entrega = limpar_texto(body.get("prazo_entrega"), "IMEDIATO (EM ESTOQUE)").upper()



    observacoes = limpar_texto(body.get("observacoes"), "").upper()



    solicitar_compra = bool(body.get("solicitar_compra", False))







    saldo_disponivel = 0



    with get_db_connection(DB_NAME) as conn:



        cur = conn.cursor()



        cur.execute("SELECT quantidade FROM estoque_pecas WHERE UPPER(codigo) = ? OR UPPER(nome_peca) = ?", (peca_codigo, peca_nome))



        row_p = cur.fetchone()



        if row_p:



            saldo_disponivel = int(row_p[0] or 0)







        # Validação Comercial eMED: Se o cliente tiver pendência financeira em aberto,
        # sugere À VISTA / PIX ou requer opção de Autorização da Diretoria / Negociação
        autorizado_diretoria = bool(body.get("autorizado_diretoria", False)) or bool(body.get("autorizacao_diretoria", False))
        info_pend = verificar_pendencias_financeiras_cliente(DB_NAME, cliente)
        if info_pend.get("tem_pendencia", False):
            cond_up = condicao_pagamento.upper()
            eh_a_vista_pix = ("VISTA" in cond_up or "PIX" in cond_up or "ANTECIPADO" in cond_up)
            if not eh_a_vista_pix and not autorizado_diretoria:
                return web.json_response({
                    "ok": False,
                    "requer_autorizacao": True,
                    "valor_pendente": info_pend.get("valor_total", 0.0),
                    "msg": f"💡 Sugestão Comercial: O cliente {cliente} possui pendências anteriores (R$ {info_pend.get('valor_total', 0.0):,.2f}). Selecione 'À VISTA / PIX' ou marque a opção 'Autorizado pela Diretoria / Exceção Comercial' para liberar faturamento a prazo."
                }, status=400)
            elif autorizado_diretoria:
                observacoes = f"[AUTORIZADO PELA DIRETORIA / EXCEÇÃO COMERCIAL] {observacoes}".strip()

        # Validação impeditiva: não permitir venda com promessa de entrega imediata se o estoque estiver zerado/insuficiente sem pedido de compra

        if saldo_disponivel < quantidade and not solicitar_compra and "IMEDIATO" in prazo_entrega.upper():



            return web.json_response({



                "ok": False,



                "msg": f"⚠️ Saldo físico insuficiente no almoxarifado ({saldo_disponivel} un. disponível para {quantidade} un. solicitada)! Para prosseguir com entrega imediata, ajuste o estoque ou marque a opção 'Solicitar Compra'."



            }, status=400)







        if solicitar_compra or saldo_disponivel <= 0:



            agora_str = obter_agora_brasil_str("%d/%m/%Y %H:%M")



            cur.execute("""



                INSERT INTO solicitacoes_pecas (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)



                VALUES ('COMERCIAL / PROPOSTA', ?, ?, 'SOLICITAÇÃO DE COMPRA PARA PROPOSTA', 'PENDENTE DE COMPRA', ?)



            """, (f"{cliente} ({equipamento}) [OS #{os_id}]", f"{quantidade}x {peca_codigo} - {peca_nome} (SEM SALDO)", agora_str))



            conn.commit()







    if os_id:



        df = _carregar_df_direto()



        for idx, row in df.iterrows():



            if str(obter_id_os(idx, row)) == os_id:



                df.at[idx, "status_proposta"] = "PROPOSTA_GERADA"



                df.at[idx, "valor_os"] = float(valor_total)



                df.at[idx, "condicao_pagamento"] = condicao_pagamento



                _salvar_df_direto(df)



                break







    msg = f"📄 Proposta gerada com sucesso para {cliente}! Peça: {peca_nome}."



    if saldo_disponivel <= 0:



        msg += " ⚠️ Peça sem estoque físico: solicitação de compra interna acionada no Almoxarifado!"







    return web.json_response({



        "ok": True,



        "msg": msg,



        "saldo_disponivel": saldo_disponivel,



        "sem_estoque": (saldo_disponivel <= 0),



        "valor_total": valor_total



    })















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















async def api_importar_excel(request: web.Request) -> web.Response:

    """Importa planilha atualizada de clientes/equipamentos ou de estoque."""

    try:

        reader = await request.multipart()

        field = await reader.next()

        if not field:

            return web.json_response({"ok": False, "msg": "Nenhum arquivo enviado."}, status=400)

        filename = field.filename or "upload.xlsx"

        conteudo = await field.read()

        

        temp_path = os.path.join(tempfile.gettempdir(), f"emed_upload_{filename}")

        with open(temp_path, "wb") as f_tmp:

            f_tmp.write(conteudo)

            

        df_uploaded = pd.read_excel(temp_path)

        colunas = [str(c).lower().strip() for c in df_uploaded.columns]

        

        # Caso seja planilha de estoque

        if any(c in colunas for c in ["codigo", "nome_peca", "quantidade", "preco_custo", "saldo"]):

            with get_db_connection(DB_NAME) as conn:

                for _, row in df_uploaded.iterrows():

                    cod = limpar_texto(row.get("codigo") or row.get("código"), "").upper()

                    nome = limpar_texto(row.get("nome_peca") or row.get("peça") or row.get("descricao"), "").upper()

                    qtd = int(limpar_float(row.get("quantidade") or row.get("saldo") or row.get("estoque"), 0))

                    preco = limpar_float(row.get("preco_custo") or row.get("preco_unitario") or row.get("valor"), 0.0)

                    if cod:

                        conn.execute("""

                            INSERT INTO estoque_pecas (codigo, nome_peca, quantidade, preco_custo)

                            VALUES (?, ?, ?, ?)

                            ON CONFLICT(codigo) DO UPDATE SET

                                nome_peca = excluded.nome_peca,

                                quantidade = excluded.quantidade,

                                preco_custo = excluded.preco_custo

                        """, (cod, nome, qtd, preco))

                conn.commit()

            return web.json_response({"ok": True, "msg": f"✅ Estoque atualizado! {len(df_uploaded)} itens sincronizados com sucesso."})

        

        # Caso seja planilha de clientes/equipamentos

        else:

            if os.path.exists(CAMINHO_EXCEL):

                import shutil

                shutil.copyfile(CAMINHO_EXCEL, CAMINHO_EXCEL.replace(".xlsx", "_backup.xlsx"))

            df_uploaded.to_excel(CAMINHO_EXCEL, index=False)

            with get_db_connection(DB_NAME) as conn:

                df_uploaded.to_sql("clientes_equipamentos", conn, if_exists="replace", index=False)

            return web.json_response({"ok": True, "msg": f"✅ Base de clientes e equipamentos atualizada! {len(df_uploaded)} registros sincronizados."})

    except Exception as e:

        return web.json_response({"ok": False, "msg": f"Erro na importação da planilha: {str(e)}"}, status=500)





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













async def api_sync_offline(request: web.Request) -> web.Response:

    """Sincronização em lote ou individual de OS executadas offline com garantia de idempotência estrita."""

    try:

        body = await request.json()

    except Exception:

        return web.json_response({"ok": False, "msg": "Payload JSON inválido."}, status=400)

    

    pacotes = body if isinstance(body, list) else [body]

    if not pacotes:

        return web.json_response({"ok": False, "msg": "Nenhum pacote enviado."}, status=400)

    

    df = _carregar_df_direto()

    equipa = _montar_equipa_direto()

    

    resultados = []

    for item in pacotes:

        df, acao = sincronizar_os_offline_idempotente(df, item, equipa, "ANTONIO")

        s_hash = item.get("sync_hash") or gerar_hash_os_offline(item)

        resultados.append({"sync_hash": s_hash, "acao": acao, "os_id": item.get("os_id")})

    

    _salvar_df_direto(df)

    return web.json_response({"ok": True, "processados": len(resultados), "resultados": resultados})





async def api_ordens(request: web.Request) -> web.Response:

    """Multiplexador REST unificado para compatibilidade total com o contrato /api/ordens."""

    if request.method == "POST":

        try:

            body = await request.json()

        except Exception:

            return web.json_response({"ok": False, "msg": "Payload JSON inválido."}, status=400)

        

        # Se for pacote offline com sync_hash ou flag offline

        if body.get("sync_hash") or body.get("offline"):

            return await api_sync_offline(request)

        

        # Se tiver os_id e não for nova OS explícita, salva/atualiza

        if body.get("os_id") and not body.get("novo", False):

            return await api_salvar_os(request)

        else:

            return await api_nova_os(request)

    elif request.method == "GET":

        df = _carregar_df_direto()

        return web.json_response({"ok": True, "total": len(df), "ordens": df.to_dict(orient="records")})

    return web.json_response({"ok": False, "msg": "Método não permitido."}, status=405)






async def api_cliente_pendencias(request: web.Request) -> web.Response:
    """Consulta rápida para o formulário de propostas e telas gerenciais."""
    cli = limpar_texto(request.query.get("cliente", ""), "")
    cnpj = limpar_texto(request.query.get("cnpj", ""), "")
    info = verificar_pendencias_financeiras_cliente(DB_NAME, cli, cnpj)
    return web.json_response(info)



async def api_ferramentas_bipagem_lote(request: web.Request) -> web.Response:
    """
    Retirada rápida de itens pelo Almoxarifado via Bipador QR Code / Leitor de Código de Barras.
    O Almoxarife seleciona o técnico e vai bipando os itens. No final, salva e atualiza tudo de uma vez.
    """
    body = await request.json()
    tecnico = limpar_texto(body.get("tecnico"), "").upper()
    itens = body.get("itens", [])
    cliente = limpar_texto(body.get("cliente"), "HOSPITAL / ATENDIMENTO TÉCNICO").upper()
    os_id = str(body.get("os_id", "")).strip()
    operador = limpar_texto(body.get("operador"), "ALMOXARIFADO EMED").upper()
    agora = obter_agora_brasil_str("%d/%m/%Y %H:%M")

    if not tecnico:
        return web.json_response({"ok": False, "msg": "Selecione o técnico responsável pela retirada."}, status=400)
    if not itens:
        return web.json_response({"ok": False, "msg": "Nenhum item foi bipado."}, status=400)

    INSTRUMENTOS_9V = {"FER-001", "FER-002", "FER-008", "FER-011"}
    lembretes = []
    total_ferramentas = 0
    total_pecas = 0

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        for item_raw in itens:
            cod = str(item_raw).strip().upper()
            if not cod:
                continue

            # Se for ferramenta FER-...
            if cod.startswith("FER-"):
                cur.execute("SELECT id, nome_ferramenta FROM ferramentas_cautela WHERE UPPER(codigo_ferramenta) = ? OR UPPER(numero_serie) = ?", (cod, cod))
                r_fer = cur.fetchone()
                if r_fer:
                    cur.execute("""
                        UPDATE ferramentas_cautela
                        SET status = 'EM_USO', tecnico_responsavel = ?, destino_cliente = ?, os_id = ?, data_saida = ?
                        WHERE id = ?
                    """, (tecnico, cliente, os_id, agora, r_fer[0]))
                    cur.execute("""
                        INSERT INTO historico_cautela_ferramentas 
                        (codigo_ferramenta, nome_ferramenta, tipo_acao, tecnico, destino_cliente, os_id, operador, data_hora, observacao)
                        VALUES (?, ?, 'RETIRADA_BIPADA', ?, ?, ?, ?, ?, 'Retirada rápida por bipagem QR')
                    """, (cod, r_fer[1], tecnico, cliente, os_id, operador, agora))
                    total_ferramentas += 1
                    aviso_ret = obter_instrucao_ferramenta(cod, "RETIRADA")
                    lembretes.append(f"{cod}: {aviso_ret}")

            # Se for peça PEC-...
            elif cod.startswith("PEC-"):
                cur.execute("SELECT id, nome_peca, quantidade FROM estoque_pecas WHERE UPPER(codigo) = ?", (cod,))
                r_pec = cur.fetchone()
                if r_pec:
                    cur.execute("UPDATE estoque_pecas SET quantidade = max(0, quantidade - 1) WHERE id = ?", (r_pec[0],))
                    total_pecas += 1

        # Se houver OS vinculada, atualiza a solicitação no Almoxarifado para SEPARADO
        if os_id:
            cur.execute("""
                UPDATE solicitacoes_pecas 
                SET status_pedido = 'SEPARADO / ENTREGUE AO TÉCNICO', tecnico = ?
                WHERE (destino_cliente LIKE ? OR os_id = ?)
                  AND tecnico NOT IN ('SETOR FINANCEIRO / COBRANÇA', 'COMERCIAL / PROPOSTA')
            """, (tecnico, f"%[OS #{os_id}]%", str(os_id)))

        conn.commit()

    lembrete_txt = " | ".join(set(lembretes)) if lembretes else ""
    return web.json_response({
        "ok": True,
        "total_ferramentas": total_ferramentas,
        "total_pecas": total_pecas,
        "lembrete_bateria": lembrete_txt,
        "msg": f"✅ Retirada concluída! {total_ferramentas} ferramenta(s) e {total_pecas} peça(s) entregues para 👷 {tecnico}."
    })


async def api_ferramentas_minhas(request: web.Request) -> web.Response:
    """Retorna a lista de ferramentas que estão em posse do técnico logado no momento."""
    tecnico = limpar_texto(request.query.get("tecnico", ""), "").upper()
    if not tecnico:
        return web.json_response({"ok": True, "ferramentas": []})

    INSTRUMENTOS_9V = {"FER-001", "FER-002", "FER-008", "FER-011"}
    minhas = []

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, codigo_ferramenta, nome_ferramenta, data_saida, destino_cliente, os_id, localizacao
            FROM ferramentas_cautela
            WHERE UPPER(tecnico_responsavel) = ? AND status = 'EM_USO'
            ORDER BY id DESC
        """, (tecnico,))
        for r in cur.fetchall():
            cod = str(r[1] or "")
            usa_9v = cod in INSTRUMENTOS_9V
            aviso_ent = obter_instrucao_ferramenta(cod, "ENTREGA")
            minhas.append({
                "id": r[0],
                "codigo": cod,
                "nome": r[2],
                "data_saida": r[3],
                "cliente": r[4],
                "os_id": r[5],
                "localizacao": r[6],
                "usa_bateria_9v": usa_9v,
                "aviso_entrega": aviso_ent,
                "lembrete": aviso_ent
            })

    return web.json_response({"ok": True, "tecnico": tecnico, "ferramentas": minhas})



async def api_fiscal_liberar_quarentena(request: web.Request) -> web.Response:
    """Libera a emissão da NF antecipadamente a partir da validação manual do gestor ou cliente."""
    body = await request.json()
    os_id = int(body.get("os_id", 0))
    motivo = str(body.get("motivo", "LIBERAÇÃO MANUAL DO GESTOR")).strip()
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE notas_fiscais
            SET status_quarentena = 'LIBERADO',
                status_fiscal = 'LIBERADO PARA EMISSÃO DE NOTA FISCAL',
                feedback_cliente_status = ?
            WHERE os_id = ?
        """, (motivo, os_id))
        conn.commit()
        
    return web.json_response({
        "ok": True,
        "msg": f"✅ OS #{os_id} liberada da quarentena para emissão da Nota Fiscal!",
        "novo_status": "LIBERADO PARA EMISSÃO DE NOTA FISCAL"
    })

async def api_remessas_diagnostico_listar(request: web.Request) -> web.Response:
    """Retorna o histórico de remessas para conserto e diagnóstico externo."""
    with get_db_connection(DB_NAME) as conn:
        df_rem = pd.read_sql_query("SELECT * FROM remessas_diagnostico ORDER BY id DESC LIMIT 100", conn)
        return web.json_response({"ok": True, "remessas": df_rem.to_dict(orient="records")})

async def api_remessas_diagnostico_salvar(request: web.Request) -> web.Response:
    """Gera uma nova Nota/Guia de Remessa para Diagnóstico ou Conserto (CFOP 5.915 estadual ou 6.915 interestadual)."""
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    cliente_origem = limpar_texto(body.get("cliente_origem"), "HOSPITAL CREDENCIADO")
    cidade_origem = limpar_texto(body.get("cidade_origem"), "FORTALEZA")
    uf_origem = limpar_texto(body.get("uf_origem"), "CE").upper()
    cnpj_origem = limpar_texto(body.get("cnpj_origem"), "")
    
    destinatario_nome = limpar_texto(body.get("destinatario_nome"), "LABORATÓRIO MATRIZ EMED")
    destinatario_cnpj = limpar_texto(body.get("destinatario_cnpj"), "")
    cidade_destino = limpar_texto(body.get("cidade_destino"), "FORTALEZA")
    uf_destino = limpar_texto(body.get("uf_destino"), "CE").upper()
    
    # Determina CFOP: 5.915 se dentro do CE, 6.915 se interestadual
    cfop = "5.915" if uf_destino == uf_origem else "6.915"
    
    descricao_peca = limpar_texto(body.get("descricao_peca"), "PEÇA ELETROMÉDICA PARA DIAGNÓSTICO")
    numero_serie = limpar_texto(body.get("numero_serie"), "S/N")
    quantidade = int(limpar_float(body.get("quantidade"), 1))
    valor_declarado = float(limpar_float(body.get("valor_declarado"), 1000.0))
    motivo_diagnostico = limpar_texto(body.get("motivo_diagnostico"), "DIAGNÓSTICO AVANÇADO EM BANCADA")
    modalidade_transporte = limpar_texto(body.get("modalidade_transporte"), "TRANSPORTADORA").upper()
    transportadora = limpar_texto(body.get("transportadora"), "")
    codigo_rastreio = limpar_texto(body.get("codigo_rastreio"), "").strip()
    tecnico_portador = limpar_texto(body.get("tecnico_portador"), "")
    data_retorno_prevista = limpar_texto(body.get("data_retorno_prevista"), "")
    observacoes = limpar_texto(body.get("observacoes"), "")
    
    agora_brasil = obter_agora_brasil_str("%d/%m/%Y %H:%M")
    ano_atual = obter_agora_brasil().strftime("%Y")
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM remessas_diagnostico")
        total_rem = cur.fetchone()[0] + 1
        num_remessa = f"REM-{ano_atual}-{total_rem:04d}"
        
        cur.execute("""
            INSERT INTO remessas_diagnostico (
                numero_remessa, os_id, cliente_origem, cidade_origem, uf_origem, cnpj_origem,
                destinatario_nome, destinatario_cnpj, cidade_destino, uf_destino, cfop,
                descricao_peca, numero_serie, quantidade, valor_declarado, motivo_diagnostico,
                modalidade_transporte, transportadora, codigo_rastreio, tecnico_portador,
                status_remessa, data_envio, data_retorno_prevista, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            num_remessa, os_id, cliente_origem, cidade_origem, uf_origem, cnpj_origem,
            destinatario_nome, destinatario_cnpj, cidade_destino, uf_destino, cfop,
            descricao_peca, numero_serie, quantidade, valor_declarado, motivo_diagnostico,
            modalidade_transporte, transportadora, codigo_rastreio, tecnico_portador,
            "EM_TRANSITO", agora_brasil, data_retorno_prevista, observacoes
        ))
        
        # Registra espelho em notas_fiscais
        cur.execute("""
            INSERT INTO notas_fiscais (
                os_id, cliente, cnpj_tomador, tipo_nota, natureza_operacao, cfop,
                valor_servicos, valor_pecas, valor_liquido, status_fiscal, numero_nf,
                discriminacao_servico, data_emissao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(os_id) if os_id.isdigit() else 0,
            destinatario_nome, destinatario_cnpj, "REMESSA_DIAGNOSTICO",
            f"REMESSA DE MERCADORIA P/ CONSERTO OU DIAGNÓSTICO ({'INTERESTADUAL' if cfop == '6.915' else 'ESTADUAL'})",
            cfop, 0.0, valor_declarado, 0.0, "EMITIDA (EM TRÂNSITO FISCAL)", num_remessa,
            f"Item: {descricao_peca} (S/N: {numero_serie}) - Motivo: {motivo_diagnostico}. Não gera crédito de ICMS/ISS.",
            agora_brasil
        ))
        conn.commit()
        
    return web.json_response({
        "ok": True,
        "msg": f"✅ Nota de Remessa {num_remessa} emitida com sucesso (CFOP {cfop})!",
        "numero_remessa": num_remessa,
        "cfop": cfop
    })

async def api_remessas_diagnostico_retorno(request: web.Request) -> web.Response:
    """Registra o retorno físico da mercadoria/peça do conserto (CFOP 1.916 / 2.916)."""
    body = await request.json()
    id_rem = int(body.get("id", 0))
    obs_retorno = limpar_texto(body.get("observacao"), "Retorno de conserto concluído com sucesso.")
    agora_brasil = obter_agora_brasil_str("%d/%m/%Y %H:%M")
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE remessas_diagnostico
            SET status_remessa = 'RETORNADO',
                data_retorno_real = ?,
                observacoes = observacoes || ' | [RETORNO: ' || ? || ' às ' || ? || ']'
            WHERE id = ?
        """, (agora_brasil, obs_retorno, agora_brasil, id_rem))
        
        cur.execute("""
            UPDATE notas_fiscais
            SET status_fiscal = 'RETORNADO (CONSERTO FINALIZADO)'
            WHERE numero_nf = (SELECT numero_remessa FROM remessas_diagnostico WHERE id = ?)
        """, (id_rem,))
        conn.commit()
        
    return web.json_response({"ok": True, "msg": f"✅ Retorno da remessa #{id_rem} registrado com sucesso!"})

async def api_remessas_diagnostico_guia(request: web.Request) -> web.Response:
    """Renderiza a Guia de Transporte e Remessa para Diagnóstico com visual timbrado oficial EMED."""
    id_rem = int(request.match_info.get("id", 0))
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM remessas_diagnostico WHERE id = ?", (id_rem,))
        row = cur.fetchone()
        if not row:
            return web.Response(text="Guia de remessa não localizada.", status=404)
        
        col_names = [d[0] for d in cur.description]
        r = dict(zip(col_names, row))
        
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Guia de Remessa para Diagnóstico - {r.get('numero_remessa')}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 20px; color: #1e293b; background: #f8fafc; }}
  .container {{ max-width: 820px; margin: 0 auto; background: #fff; padding: 30px; border: 1.5px solid #cbd5e1; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0284c7; padding-bottom: 15px; margin-bottom: 20px; }}
  .logo {{ font-size: 24px; font-weight: 900; color: #0284c7; letter-spacing: 1px; }}
  .doc-title {{ text-align: right; }}
  .doc-title h1 {{ font-size: 16px; margin: 0; color: #0f172a; text-transform: uppercase; }}
  .doc-title span {{ font-size: 13px; font-weight: 800; color: #0284c7; }}
  .box-info {{ border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 15px; background: #f8fafc; }}
  .box-title {{ font-size: 12px; font-weight: 800; text-transform: uppercase; color: #475569; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
  .label {{ font-size: 11px; color: #64748b; font-weight: 600; text-transform: uppercase; }}
  .val {{ font-size: 13px; font-weight: 700; color: #0f172a; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th {{ background: #0284c7; color: #fff; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; }}
  td {{ border: 1px solid #e2e8f0; padding: 8px 10px; font-size: 12px; }}
  .cfop-badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-weight: 800; font-size: 12px; border: 1px solid #7dd3fc; }}
  .legal-notice {{ font-size: 10.5px; color: #64748b; background: #f1f5f9; padding: 10px; border-radius: 6px; margin-top: 20px; line-height: 1.4; border-left: 3px solid #0284c7; }}
  .signatures {{ display: flex; justify-content: space-between; margin-top: 40px; padding-top: 20px; }}
  .sig-line {{ width: 45%; border-top: 1px solid #94a3b8; text-align: center; font-size: 11px; color: #475569; padding-top: 5px; }}
  @media print {{ body {{ background: #fff; margin: 0; }} .container {{ border: none; box-shadow: none; padding: 0; }} .no-print {{ display: none; }} }}
</style>
</head>
<body>
<div class="container">
  <div class="no-print" style="margin-bottom: 15px; display: flex; justify-content: flex-end; gap: 8px;">
    <button onclick="window.print()" style="padding: 8px 16px; background: #0284c7; color: #fff; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir Guia / Salvar PDF</button>
  </div>
  
  <div class="header">
    <div>
      <div class="logo">🏥 eMED ELETROMEDICINA</div>
      <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Engenharia Clínica e Hospitalar Especializada</div>
    </div>
    <div class="doc-title">
      <h1>Guia de Remessa para Diagnóstico / Conserto</h1>
      <span>{r.get('numero_remessa')} &bull; CFOP {r.get('cfop')}</span>
    </div>
  </div>

  <div class="grid-2">
    <div class="box-info">
      <div class="box-title">📍 Unidade de Origem (Remetente)</div>
      <div class="label">Cliente / Hospital:</div>
      <div class="val">{r.get('cliente_origem')}</div>
      <div class="label" style="margin-top: 6px;">Município / UF:</div>
      <div class="val">{r.get('cidade_origem')} - {r.get('uf_origem')}</div>
      <div class="label" style="margin-top: 6px;">OS Vinculada:</div>
      <div class="val">OS #{r.get('os_id') or 'Avulsa'}</div>
    </div>

    <div class="box-info">
      <div class="box-title">🎯 Destino / Centro Técnico de Reparo</div>
      <div class="label">Destinatário:</div>
      <div class="val">{r.get('destinatario_nome')}</div>
      <div class="label" style="margin-top: 6px;">Município / UF de Destino:</div>
      <div class="val">{r.get('cidade_destino')} - {r.get('uf_destino')}</div>
      <div class="label" style="margin-top: 6px;">Enquadramento Tributário:</div>
      <div class="val"><span class="cfop-badge">CFOP {r.get('cfop')} - {'INTERESTADUAL' if r.get('uf_destino') != r.get('uf_origem') else 'ESTADUAL'}</span></div>
    </div>
  </div>

  <div class="box-info">
    <div class="box-title">🔩 Descrição do Bem / Peça em Trânsito</div>
    <table>
      <thead>
        <tr>
          <th>Item / Peça Eletromédica</th>
          <th>Nº de Série</th>
          <th>Qtd</th>
          <th>Valor Declarado (Seguro)</th>
          <th>Motivo do Envio / Laudo</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><b>{r.get('descricao_peca')}</b></td>
          <td><code>{r.get('numero_serie')}</code></td>
          <td style="text-align: center;">{r.get('quantidade')} UN</td>
          <td style="font-weight: 800; color: #047857;">R$ {float(r.get('valor_declarado', 0.0)):,.2f}</td>
          <td>{r.get('motivo_diagnostico')}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="box-info">
    <div class="box-title">🚚 Dados Logísticos &amp; Transporte</div>
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
      <div>
        <div class="label">Modalidade:</div>
        <div class="val">{r.get('modalidade_transporte')}</div>
      </div>
      <div>
        <div class="label">Transportadora / Operador:</div>
        <div class="val">{r.get('transportadora') or 'Veículo Oficial EMED'}</div>
      </div>
      <div>
        <div class="label">Código de Rastreamento:</div>
        <div class="val"><code>{r.get('codigo_rastreio') or 'Trânsito em Frota'}</code></div>
      </div>
      <div>
        <div class="label">Data de Emissão / Envio:</div>
        <div class="val">{r.get('data_envio')}</div>
      </div>
    </div>
  </div>

  <div class="legal-notice">
    <b>DISPOSITIVO LEGAL &amp; DECLARAÇÃO DE TRÂNSITO FISCAL:</b><br>
    Mercadoria destinada a conserto, diagnóstico e ensaios laboratoriais conforme Artigo correspondente do Regulamento do ICMS (RICMS) c/c CFOP {r.get('cfop')}. Operação ao abrigo de não-incidência / suspensão do ICMS. O valor acima destina-se exclusivamente para fins de cobertura de seguro de carga e fiscalização em trânsito rodoviário/aéreo.
  </div>

  <div class="signatures">
    <div class="sig-line">
      Responsável pela Expedição / Técnico EMED
    </div>
    <div class="sig-line">
      Transportadora / Recebedor do Laboratório
    </div>
  </div>
</div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html", charset="utf-8")


def garantir_schema_rastreio(db_path: str):
    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            for col in ['codigo_rastreio', 'transportadora']:
                try:
                    cur.execute(f"ALTER TABLE solicitacoes_pecas ADD COLUMN {col} TEXT DEFAULT ''")
                except Exception:
                    pass
            conn.commit()
    except Exception:
        pass


def garantir_schema_medicina_trabalho(db_path: str):
    """Garante as tabelas e colunas de medicina ocupacional (NR-7 / ASO) para os funcionários."""
    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            novas = [
                ("data_ultimo_aso", "TEXT DEFAULT ''"),
                ("data_vencimento_aso", "TEXT DEFAULT ''"),
                ("periodicidade_meses", "INTEGER DEFAULT 12"),
                ("medico_examinador", "TEXT DEFAULT ''"),
                ("clinica_medicina_trabalho", "TEXT DEFAULT ''"),
                ("tipo_exame_aso", "TEXT DEFAULT 'PERIÓDICO'"),
                ("parecer_aptidao", "TEXT DEFAULT 'APTO'"),
                ("observacoes_medicas", "TEXT DEFAULT ''"),
                ("aso_anexo_url", "TEXT DEFAULT ''")
            ]
            cols = [c[1] for c in cur.execute("PRAGMA table_info(tecnicos)").fetchall()]
            for col, tipo in novas:
                if col not in cols:
                    try:
                        cur.execute(f"ALTER TABLE tecnicos ADD COLUMN {col} {tipo}")
                    except Exception:
                        pass
            cur.execute("""
                CREATE TABLE IF NOT EXISTS historico_exames_medicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tecnico_id INTEGER,
                    nome_tecnico TEXT,
                    data_exame TEXT,
                    data_vencimento TEXT,
                    periodicidade_meses INTEGER DEFAULT 12,
                    tipo_exame TEXT,
                    medico_examinador TEXT,
                    clinica TEXT,
                    parecer_aptidao TEXT,
                    observacoes TEXT,
                    registrado_por TEXT,
                    criado_em TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except Exception as e:
        print("Aviso schema medicina do trabalho:", e)


async def api_tecnico_renovar_medico(request: web.Request) -> web.Response:
    """Registra a renovação formal do exame médico do trabalho (ASO) do funcionário."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "msg": "Payload JSON inválido."}, status=400)

    tid = body.get("tecnico_id") or body.get("id")
    nome = limpar_texto(body.get("nome"), "").strip().upper()
    data_exame = limpar_texto(body.get("data_exame"), "").strip()
    periodicidade = int(limpar_int(body.get("periodicidade_meses"), 12))
    medico = limpar_texto(body.get("medico_examinador"), "Dr. Roberto Arruda - CRM/CE 14258").strip()
    clinica = limpar_texto(body.get("clinica"), "MedWork Saúde Ocupacional").strip()
    tipo_exame = limpar_texto(body.get("tipo_exame"), "PERIÓDICO").strip().upper()
    parecer = limpar_texto(body.get("parecer_aptidao"), "APTO").strip().upper()
    obs = limpar_texto(body.get("observacoes"), "").strip()
    registrado_por = limpar_texto(body.get("registrado_por"), "GESTOR").strip().upper()

    if not data_exame:
        data_exame = obter_agora_brasil_str("%Y-%m-%d")

    data_vencimento = limpar_texto(body.get("data_vencimento"), "").strip()
    if not data_vencimento:
        try:
            if "/" in data_exame:
                dt = datetime.strptime(data_exame[:10], "%d/%m/%Y").date()
            else:
                dt = datetime.strptime(data_exame[:10], "%Y-%m-%d").date()
            ano_novo = dt.year + (dt.month + periodicidade - 1) // 12
            mes_novo = (dt.month + periodicidade - 1) % 12 + 1
            dia_novo = min(dt.day, 28)
            dt_venc = datetime(ano_novo, mes_novo, dia_novo).date()
            data_vencimento = dt_venc.strftime("%Y-%m-%d")
        except Exception:
            data_vencimento = data_exame

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        if tid:
            cur.execute("SELECT id, nome FROM tecnicos WHERE id = ?", (int(tid),))
        else:
            cur.execute("SELECT id, nome FROM tecnicos WHERE UPPER(nome) = ?", (nome,))
        row = cur.fetchone()
        if not row:
            return web.json_response({"ok": False, "msg": "Funcionário/técnico não localizado no cadastro."}, status=404)
        tec_id, tec_nome = row[0], row[1]

        cur.execute("""
            UPDATE tecnicos
            SET data_ultimo_aso = ?,
                data_vencimento_aso = ?,
                periodicidade_meses = ?,
                medico_examinador = ?,
                clinica_medicina_trabalho = ?,
                tipo_exame_aso = ?,
                parecer_aptidao = ?,
                observacoes_medicas = ?
            WHERE id = ?
        """, (data_exame, data_vencimento, periodicidade, medico, clinica, tipo_exame, parecer, obs, tec_id))

        cur.execute("""
            INSERT INTO historico_exames_medicos
            (tecnico_id, nome_tecnico, data_exame, data_vencimento, periodicidade_meses, tipo_exame,
             medico_examinador, clinica, parecer_aptidao, observacoes, registrado_por, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tec_id, tec_nome, data_exame, data_vencimento, periodicidade, tipo_exame, medico, clinica, parecer, obs, registrado_por, obter_agora_brasil_str("%d/%m/%Y %H:%M")))
        conn.commit()

    return web.json_response({
        "ok": True,
        "msg": f"🩺 Renovação do Médico do Trabalho registrada com sucesso para {tec_nome}!",
        "tecnico_id": tec_id,
        "nome": tec_nome,
        "data_exame": data_exame,
        "data_vencimento": data_vencimento,
        "parecer": parecer
    })


async def api_tecnico_historico_medico(request: web.Request) -> web.Response:
    """Retorna o histórico de exames médicos ocupacionais e ASOs do funcionário."""
    tid = request.match_info.get("id")
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tecnico_id, nome_tecnico, data_exame, data_vencimento, periodicidade_meses,
                   tipo_exame, medico_examinador, clinica, parecer_aptidao, observacoes, registrado_por, criado_em
            FROM historico_exames_medicos
            WHERE tecnico_id = ? OR UPPER(nome_tecnico) = ?
            ORDER BY id DESC
        """, (tid, str(tid).upper()))
        cols = [d[0] for d in cur.description]
        historico = [dict(zip(cols, r)) for r in cur.fetchall()]
        return web.json_response({"ok": True, "historico": historico})


def garantir_schema_fiscal_contabil(db_path: str):
    try:
        with get_db_connection(db_path) as conn:
            cur = conn.cursor()
            novas = [
                ("email_cliente", "TEXT DEFAULT ''"),
                ("email_enviado_em", "TEXT DEFAULT ''"),
                ("email_status", "TEXT DEFAULT 'PENDENTE'"),
                ("lote_contabilidade_mes", "TEXT DEFAULT ''"),
                ("enviado_contabilidade", "INTEGER DEFAULT 0"),
                ("data_envio_contabilidade", "TEXT DEFAULT ''")
            ]
            for col, tipo in novas:
                try:
                    cur.execute(f"ALTER TABLE notas_fiscais ADD COLUMN {col} {tipo}")
                except Exception:
                    pass
            try:
                cur.execute("UPDATE notas_fiscais SET lote_contabilidade_mes = strftime('%Y-%m', criado_em) WHERE lote_contabilidade_mes IS NULL OR lote_contabilidade_mes = ''")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        print("Aviso garantir_schema_fiscal_contabil:", e)


async def api_fiscal_enviar_cliente(request: web.Request) -> web.Response:
    """Registra e processa o envio da Nota Fiscal por e-mail para o cliente."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "msg": "Payload inválido."}, status=400)

    os_id = str(body.get("os_id", "")).strip()
    email_dest = str(body.get("email", "") or body.get("email_destino", "")).strip()
    if not os_id:
        return web.json_response({"ok": False, "msg": "ID da OS é obrigatório."}, status=400)
    if not email_dest or "@" not in email_dest:
        return web.json_response({"ok": False, "msg": "Informe um e-mail válido para o cliente."}, status=400)

    agora_brasil = obter_agora_brasil_str("%d/%m/%Y %H:%M")
    mes_competencia = obter_agora_brasil_str("%Y-%m")

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, numero_nf, cliente, valor_servicos, valor_pecas, chave_acesso FROM notas_fiscais WHERE os_id = ?", (os_id,))
        row_nf = cur.fetchone()
        num_nf = row_nf[1] if row_nf else f"NFS-{os_id.zfill(4)}"
        cliente_nome = row_nf[2] if row_nf else "Cliente"
        val_total = (float(row_nf[3] or 0) + float(row_nf[4] or 0)) if row_nf else 0.0
        chave_acesso = row_nf[5] if row_nf else ""

        cur.execute("""
            UPDATE notas_fiscais
            SET email_cliente = ?,
                email_enviado_em = ?,
                email_status = 'ENVIADO',
                lote_contabilidade_mes = COALESCE(NULLIF(lote_contabilidade_mes, ''), ?)
            WHERE os_id = ?
        """, (email_dest, agora_brasil, mes_competencia, os_id))
        conn.commit()

    try:
        df = _carregar_df_direto()
        for idx, row in df.iterrows():
            if str(obter_id_os(idx, row)) == os_id:
                if not df.at[idx, "email"]:
                    df.at[idx, "email"] = email_dest
                    _salvar_df_direto(df)
                break
    except Exception:
        pass

    assunto = f"Nota Fiscal Eletrônica {num_nf} - OS #{os_id} - EMED Eletromedicina"
    corpo = (
        f"Prezado(a) {cliente_nome},\n\n"
        f"Segue o comprovante oficial de emissão da Nota Fiscal Eletrônica referente ao atendimento técnico da OS #{os_id}.\n\n"
        f"📄 Número da Nota: {num_nf}\n"
        f"💰 Valor Total: R$ {val_total:,.2f}\n"
        f"🔑 Chave de Acesso: {chave_acesso}\n"
        f"📅 Emitida em: {agora_brasil}\n\n"
        f"🔗 Visualizar DANFE Oficial: http://localhost:8502/api/fiscal/danfe/{os_id}\n\n"
        f"Agradecemos a parceria!\n"
        f"EMED Eletromedicina Ltda.\n"
        f"Fone Ceará: (85) 3254-2929 | WhatsApp DF: (61) 99658-5392\n"
        f"Rua Coronel Freire, 16 - Bairro Amador, Eusébio - CE"
    )
    mailto_url = f"mailto:{urllib.parse.quote(email_dest)}?subject={urllib.parse.quote(assunto)}&body={urllib.parse.quote(corpo)}"

    return web.json_response({
        "ok": True,
        "msg": f"Nota Fiscal {num_nf} enviada com sucesso para {email_dest}!",
        "email_enviado_em": agora_brasil,
        "email_destino": email_dest,
        "lote_contabilidade": mes_competencia,
        "mailto_url": mailto_url
    })


async def api_fiscal_enviar_contabilidade(request: web.Request) -> web.Response:
    """Envia o lote consolidado de Notas Fiscais emitidas no mês para a assessoria contábil."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    agora = datetime.now()
    mes = str(body.get("mes", agora.month)).zfill(2)
    ano = str(body.get("ano", agora.year))
    comp = f"{ano}-{mes}"
    email_contab = str(body.get("email_contabilidade", "contabilidade@emed.med.br")).strip()
    obs = str(body.get("observacoes", "")).strip()
    agora_brasil = obter_agora_brasil_str("%d/%m/%Y %H:%M")

    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        padrao_data = f"/{mes}/{ano}"
        cur.execute("""
            SELECT id, os_id, cliente, cnpj_tomador, numero_nf, valor_servicos, valor_pecas, data_emissao, status_fiscal
            FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR criado_em LIKE ? OR lote_contabilidade_mes = ?)
              AND UPPER(status_fiscal) NOT LIKE '%CANCELADA%'
        """, (f"%{padrao_data}%", f"{comp}%", comp))
        notas = cur.fetchall()

        if not notas:
            return web.json_response({"ok": False, "msg": f"Nenhuma Nota Fiscal ativa encontrada para a competência {mes}/{ano}."})

        total_servicos = sum(float(n[5] or 0) for n in notas)
        total_pecas = sum(float(n[6] or 0) for n in notas)
        total_faturamento = total_servicos + total_pecas

        ids = [n[0] for n in notas]
        placeholders = ",".join("?" * len(ids))
        cur.execute(f"""
            UPDATE notas_fiscais
            SET enviado_contabilidade = 1,
                data_envio_contabilidade = ?,
                lote_contabilidade_mes = ?
            WHERE id IN ({placeholders})
        """, [agora_brasil, comp] + ids)
        conn.commit()

    assunto = f"Fechamento Fiscal & Lote Mensal de NFs - Competência {mes}/{ano} - EMED Eletromedicina"
    corpo = (
        f"Prezada Assessoria Contábil,\n\n"
        f"Encaminhamos o lote oficial consolidado de Notas Fiscais emitidas pela EMED Eletromedicina referente à competência {mes}/{ano}.\n\n"
        f"📊 Quantidade de Notas Fiscais: {len(notas)}\n"
        f"🛠️ Total Serviços (NFS-e): R$ {total_servicos:,.2f}\n"
        f"🔩 Total Peças/Insumos (NF-e): R$ {total_pecas:,.2f}\n"
        f"💰 Faturamento Bruto Consolidado: R$ {total_faturamento:,.2f}\n"
        f"📅 Data do Fechamento: {agora_brasil}\n"
        f"{f'📝 Observações: {obs}' if obs else ''}\n\n"
        f"🔗 Dossiê Contábil Completo: http://localhost:8502/api/financeiro/relatorio-contabil/imprimir?mes={int(mes)}&ano={ano}\n"
        f"📥 Planilha CSV para Importação: http://localhost:8502/api/fiscal/relatorio-contabil-csv?mes={int(mes)}&ano={ano}\n\n"
        f"EMED Eletromedicina Ltda. - CNPJ: 03.611.974/0001-08\n"
        f"Rua Coronel Freire, 16 - Bairro Amador, Eusébio - CE"
    )
    mailto_url = f"mailto:{urllib.parse.quote(email_contab)}?subject={urllib.parse.quote(assunto)}&body={urllib.parse.quote(corpo)}"

    return web.json_response({
        "ok": True,
        "msg": f"📦 Lote de {len(notas)} Nota(s) Fiscal(is) da competência {mes}/{ano} transmitido à contabilidade com sucesso!",
        "mes": mes,
        "ano": ano,
        "total_nfs": len(notas),
        "total_faturamento": total_faturamento,
        "data_envio": agora_brasil,
        "email_contabilidade": email_contab,
        "mailto_url": mailto_url
    })


async def api_fiscal_relatorio_contabil_csv(request: web.Request) -> web.Response:
    """Exporta arquivo CSV compatível com sistemas contábeis para importação de notas fiscais."""
    agora = datetime.now()
    mes_str = request.query.get("mes", str(agora.month))
    ano_str = request.query.get("ano", str(agora.year))
    try:
        mes = int(mes_str)
    except Exception:
        mes = agora.month
    try:
        ano = int(ano_str)
    except Exception:
        ano = agora.year

    padrao = f"/{mes:02d}/{ano}"
    comp = f"{ano}-{mes:02d}"

    with get_db_connection(DB_NAME) as conn:
        df_nfs = pd.read_sql_query("SELECT * FROM notas_fiscais", conn)

    df_filtradas = df_nfs[df_nfs["data_emissao"].astype(str).str.contains(padrao) | df_nfs["criado_em"].astype(str).str.contains(comp) | (df_nfs["lote_contabilidade_mes"].astype(str) == comp)]
    if df_filtradas.empty:
        df_filtradas = df_nfs

    linhas = ["NUMERO_NF;SERIE;DATA_EMISSAO;OS_ID;CLIENTE;CNPJ_TOMADOR;VALOR_SERVICOS;VALOR_PECAS;VALOR_TOTAL;ALIQUOTA_ISS;ISS_DEVIDO;TIPO_NOTA;CHAVE_ACESSO;STATUS_FISCAL;EMAIL_CLIENTE;EMAIL_ENVIADO_EM;LOTE_CONTABIL;ENVIADO_CONTABILIDADE"]
    for _, r in df_filtradas.iterrows():
        vs = float(r.get("valor_servicos") or 0.0)
        vp = float(r.get("valor_pecas") or 0.0)
        vt = vs + vp
        iss = round(vs * 0.05, 2)
        linhas.append(
            f"{r.get('numero_nf','')};"
            f"{r.get('serie','1')};"
            f"{r.get('data_emissao','')};"
            f"{r.get('os_id','')};"
            f"\"{str(r.get('cliente','')).replace(';', ' ')}\";"
            f"{r.get('cnpj_tomador','')};"
            f"{vs:.2f};"
            f"{vp:.2f};"
            f"{vt:.2f};"
            f"5.00;"
            f"{iss:.2f};"
            f"\"{r.get('tipo_nota','')}\";"
            f"{r.get('chave_acesso','')};"
            f"{r.get('status_fiscal','')};"
            f"{r.get('email_cliente','')};"
            f"{r.get('email_enviado_em','')};"
            f"{r.get('lote_contabilidade_mes','')};"
            f"{'SIM' if r.get('enviado_contabilidade') else 'NA_FILA'}"
        )

    conteudo_csv = "\r\n".join(linhas)
    nome_arquivo = f"EMED_Notas_Fiscais_Contabilidade_{ano}_{mes:02d}.csv"
    return web.Response(
        text=conteudo_csv,
        content_type="text/csv",
        charset="utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
    )


async def api_fiscal_cancelar_nota(request: web.Request) -> web.Response:
    """Cancela uma Nota Fiscal com registro formal de justificativa e histórico no banco de dados."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "msg": "Payload JSON inválido."}, status=400)
        
    nota_id = body.get("nota_id") or body.get("id")
    numero_nf = str(body.get("numero_nf", "")).strip()
    motivo = str(body.get("motivo", "")).strip()
    
    if not motivo:
        return web.json_response({"ok": False, "msg": "É obrigatório informar a justificativa/motivo do cancelamento."}, status=400)
        
    agora_brasil = obter_agora_brasil_str("%d/%m/%Y %H:%M")
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        row = None
        if nota_id:
            cur.execute("SELECT id, numero_nf, os_id, cliente, status_fiscal FROM notas_fiscais WHERE id = ?", (int(nota_id),))
            row = cur.fetchone()
        elif numero_nf:
            cur.execute("SELECT id, numero_nf, os_id, cliente, status_fiscal FROM notas_fiscais WHERE UPPER(numero_nf) = ? OR chave_acesso = ?", (numero_nf.upper(), numero_nf))
            row = cur.fetchone()
            
        if not row:
            return web.json_response({"ok": False, "msg": "Nota Fiscal não localizada no sistema."}, status=404)
            
        nid, num_nf, os_id, cliente, st_ant = row
        
        cur.execute("""
            UPDATE notas_fiscais
            SET status_fiscal = 'CANCELADA',
                status_quarentena = 'CANCELADA',
                motivo_cancelamento = ?,
                data_cancelamento = ?,
                atualizado_em = ?
            WHERE id = ?
        """, (motivo, agora_brasil, agora_brasil, nid))
        
        # Desvincula pendência na OS e registra observação
        if os_id:
            try:
                cur.execute("""
                    UPDATE clientes_equipamentos
                    SET observacao = COALESCE(observacao, '') || ' | [NF ' || ? || ' CANCELADA em ' || ? || ': ' || ? || ']'
                    WHERE id = ?
                """, (str(num_nf), agora_brasil, motivo, int(os_id)))
            except Exception:
                pass
                
        conn.commit()
        
    return web.json_response({
        "ok": True,
        "msg": f"Nota Fiscal #{num_nf} ({cliente}) cancelada com sucesso!",
        "nota_id": nid,
        "numero_nf": num_nf,
        "status_fiscal": "CANCELADA",
        "data_cancelamento": agora_brasil
    })


async def api_financeiro_relatorio_contabil(request: web.Request) -> web.Response:
    """Gera o consolidado mensal de impostos, faturamento e despesas recorrentes para contabilidade."""
    mes = request.query.get("mes") # Ex: "10"
    ano = request.query.get("ano", str(datetime.now().year))
    
    with get_db_connection(DB_NAME) as conn:
        df_nfs = pd.read_sql_query("SELECT * FROM notas_fiscais", conn)
        df_desp = pd.read_sql_query("SELECT * FROM despesas_recorrentes WHERE status = 'ATIVO' ORDER BY dia_vencimento ASC", conn)
        
    if mes:
        padrao = f"/{int(mes):02d}/{ano}"
        df_filtradas = df_nfs[df_nfs["data_emissao"].astype(str).str.contains(padrao) | df_nfs["criado_em"].astype(str).str.contains(f"{ano}-{int(mes):02d}")]
    else:
        df_filtradas = df_nfs
        
    nfs_ativas = df_filtradas[~df_filtradas["status_fiscal"].astype(str).str.upper().str.contains("CANCELADA")]
    nfs_canceladas = df_filtradas[df_filtradas["status_fiscal"].astype(str).str.upper().str.contains("CANCELADA")]
    
    total_servicos = float(nfs_ativas["valor_servicos"].sum() or 0.0)
    total_pecas = float(nfs_ativas["valor_pecas"].sum() or 0.0)
    total_bruto = total_servicos + total_pecas
    total_cancelado = float(nfs_canceladas["valor_servicos"].sum() + nfs_canceladas["valor_pecas"].sum())
    
    # Cálculos tributários:
    iss_devido = round(total_servicos * 0.05, 2)
    simples_nacional_estimado = round(total_servicos * 0.085 + total_pecas * 0.045, 2)
    pis_estimado = round(total_bruto * 0.0065, 2)
    cofins_estimado = round(total_bruto * 0.0300, 2)
    csll_estimada = round(total_servicos * 0.0100, 2)
    irpj_estimado = round(total_servicos * 0.0120, 2)
    total_tributos_federais = round(pis_estimado + cofins_estimado + csll_estimada + irpj_estimado, 2)
    
    total_despesas_recorrentes = float(df_desp["valor_mensal_estimado"].sum() or 0.0)
    saldo_liquido_operacional = round(total_bruto - simples_nacional_estimado - total_despesas_recorrentes, 2)
    
    return web.json_response({
        "ok": True,
        "competencia": f"{mes or 'TODOS'}/{ano}",
        "resumo": {
            "total_servicos": total_servicos,
            "total_pecas": total_pecas,
            "total_faturado_bruto": total_bruto,
            "total_cancelado": total_cancelado,
            "total_faturado_liquido": total_bruto,
            "iss_devido": iss_devido,
            "simples_nacional_estimado": simples_nacional_estimado,
            "pis_estimado": pis_estimado,
            "cofins_estimado": cofins_estimado,
            "csll_estimada": csll_estimada,
            "irpj_estimado": irpj_estimado,
            "total_tributos_federais": total_tributos_federais,
            "total_despesas_recorrentes": total_despesas_recorrentes,
            "saldo_liquido_operacional": saldo_liquido_operacional
        },
        "notas_ativas": nfs_ativas.to_dict(orient="records"),
        "notas_canceladas": nfs_canceladas.to_dict(orient="records"),
        "despesas_recorrentes": df_desp.to_dict(orient="records")
    })


async def api_financeiro_relatorio_contabil_imprimir(request: web.Request) -> web.Response:
    """Renderiza a visão oficial impressa/PDF do Fechamento Contábil & Tributário Mensal para o escritório de contabilidade."""
    mes_str = request.query.get("mes", str(datetime.now().month))
    ano_str = request.query.get("ano", str(datetime.now().year))
    try:
        mes = int(mes_str)
    except Exception:
        mes = datetime.now().month
    try:
        ano = int(ano_str)
    except Exception:
        ano = datetime.now().year
        
    with get_db_connection(DB_NAME) as conn:
        df_nfs = pd.read_sql_query("SELECT * FROM notas_fiscais", conn)
        df_desp = pd.read_sql_query("SELECT * FROM despesas_recorrentes WHERE status = 'ATIVO' ORDER BY dia_vencimento ASC", conn)
        
    padrao = f"/{mes:02d}/{ano}"
    df_filtradas = df_nfs[df_nfs["data_emissao"].astype(str).str.contains(padrao) | df_nfs["criado_em"].astype(str).str.contains(f"{ano}-{mes:02d}")]
    if df_filtradas.empty:
        df_filtradas = df_nfs
        
    nfs_ativas = df_filtradas[~df_filtradas["status_fiscal"].astype(str).str.upper().str.contains("CANCELADA")]
    nfs_canceladas = df_filtradas[df_filtradas["status_fiscal"].astype(str).str.upper().str.contains("CANCELADA")]
    
    total_servicos = float(nfs_ativas["valor_servicos"].sum() or 0.0)
    total_pecas = float(nfs_ativas["valor_pecas"].sum() or 0.0)
    total_bruto = total_servicos + total_pecas
    total_cancelado = float(nfs_canceladas["valor_servicos"].sum() + nfs_canceladas["valor_pecas"].sum())
    
    iss_devido = round(total_servicos * 0.05, 2)
    simples_estimado = round(total_servicos * 0.085 + total_pecas * 0.045, 2)
    total_despesas = float(df_desp["valor_mensal_estimado"].sum() or 0.0)
    saldo_liquido = round(total_bruto - simples_estimado - total_despesas, 2)
    
    linhas_nfs = ""
    for _, r in nfs_ativas.iterrows():
        linhas_nfs += f"""
        <tr>
          <td><b>{r.get('numero_nf')}</b></td>
          <td>OS #{r.get('os_id')}</td>
          <td>{r.get('cliente')}</td>
          <td>{r.get('data_emissao')}</td>
          <td>R$ {float(r.get('valor_servicos', 0.0)):,.2f}</td>
          <td>R$ {float(r.get('valor_pecas', 0.0)):,.2f}</td>
          <td><b>R$ {float(r.get('valor_liquido', 0.0) or (float(r.get('valor_servicos',0))+float(r.get('valor_pecas',0)))):,.2f}</b></td>
          <td><span style="color:#059669;font-weight:bold;">{r.get('status_fiscal')}</span></td>
        </tr>
        """
        
    linhas_canceladas = ""
    for _, r in nfs_canceladas.iterrows():
        linhas_canceladas += f"""
        <tr style="background:#fef2f2;color:#991b1b;">
          <td><b>{r.get('numero_nf')}</b></td>
          <td>OS #{r.get('os_id')}</td>
          <td>{r.get('cliente')}</td>
          <td>{r.get('data_cancelamento') or r.get('atualizado_em')}</td>
          <td colspan="2">Motivo: {r.get('motivo_cancelamento') or 'Cancelamento Solicitado'}</td>
          <td><b>R$ {float(r.get('valor_liquido', 0.0) or (float(r.get('valor_servicos',0))+float(r.get('valor_pecas',0)))):,.2f}</b></td>
          <td><span style="color:#dc2626;font-weight:bold;">CANCELADA</span></td>
        </tr>
        """
        
    linhas_despesas = ""
    for _, d in df_desp.iterrows():
        linhas_despesas += f"""
        <tr>
          <td><b>Dia {int(d.get('dia_vencimento', 10))}</b></td>
          <td>{d.get('categoria')}</td>
          <td>{d.get('descricao')}</td>
          <td>{d.get('fornecedor')}</td>
          <td>{d.get('forma_pagamento')}</td>
          <td><b>R$ {float(d.get('valor_mensal_estimado', 0.0)):,.2f}</b></td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Fechamento Contábil e Tributário - Competência {mes:02d}/{ano}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 20px; color: #1e293b; background: #f8fafc; }}
  .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 30px; border: 1.5px solid #cbd5e1; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2.5px solid #0f172a; padding-bottom: 15px; margin-bottom: 20px; }}
  .logo {{ font-size: 24px; font-weight: 900; color: #0284c7; letter-spacing: 1px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 25px; }}
  .kpi-card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: #f8fafc; text-align: center; }}
  .kpi-val {{ font-size: 16px; font-weight: 900; margin-top: 4px; color: #0f172a; }}
  .kpi-lbl {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 20px; font-size: 12px; }}
  th {{ background: #0f172a; color: #fff; text-align: left; padding: 8px 10px; font-size: 11px; text-transform: uppercase; }}
  td {{ border: 1px solid #e2e8f0; padding: 7px 10px; }}
  .section-title {{ font-size: 14px; font-weight: 900; color: #0f172a; text-transform: uppercase; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; margin-top: 25px; }}
  .signatures {{ display: flex; justify-content: space-between; margin-top: 45px; padding-top: 20px; }}
  .sig-line {{ width: 45%; border-top: 1px solid #94a3b8; text-align: center; font-size: 11px; color: #475569; padding-top: 5px; }}
  @media print {{ body {{ background: #fff; margin: 0; }} .container {{ border: none; box-shadow: none; padding: 0; }} .no-print {{ display: none; }} }}
</style>
</head>
<body>
<div class="container">
  <div class="no-print" style="margin-bottom: 15px; display: flex; justify-content: flex-end; gap: 8px;">
    <button onclick="window.print()" style="padding: 8px 16px; background: #0f172a; color: #fff; border: none; border-radius: 6px; font-weight: bold; cursor: pointer;">🖨️ Imprimir Relatório / Gerar PDF Contábil</button>
  </div>
  
  <div class="header">
    <div>
      <div class="logo">🏥 eMED ELETROMEDICINA</div>
      <div style="font-size: 11.5px; color: #475569; margin-top: 2px;">CNPJ: 07.842.190/0001-44 &bull; Engenharia Clínica &amp; Manutenção Hospitalar</div>
      <div style="font-size: 11px; color: #64748b;">Fortaleza - CE &bull; Tel: (85) 3299-4400</div>
    </div>
    <div style="text-align: right;">
      <h1 style="font-size: 15px; margin: 0; color: #0f172a; text-transform: uppercase;">Dossiê Contábil &amp; Fechamento Mensal</h1>
      <span style="font-size: 13px; font-weight: 800; color: #0284c7;">Competência: {mes:02d}/{ano}</span>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card" style="border-top: 3px solid #0284c7;">
      <div class="kpi-lbl">Faturamento Bruto</div>
      <div class="kpi-val" style="color: #0369a1;">R$ {total_bruto:,.2f}</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #b45309;">
      <div class="kpi-lbl">Simples / Tributos Est.</div>
      <div class="kpi-val" style="color: #b45309;">R$ {simples_estimado:,.2f}</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #dc2626;">
      <div class="kpi-lbl">Despesas Recorrentes</div>
      <div class="kpi-val" style="color: #dc2626;">R$ {total_despesas:,.2f}</div>
    </div>
    <div class="kpi-card" style="border-top: 3px solid #059669;">
      <div class="kpi-lbl">Resultado Pré-Contábil</div>
      <div class="kpi-val" style="color: #059669;">R$ {saldo_liquido:,.2f}</div>
    </div>
  </div>

  <div class="section-title">1. Notas Fiscais Emitidas &amp; Apuração de Tributos</div>
  <table>
    <thead>
      <tr>
        <th>Nº NF</th>
        <th>OS</th>
        <th>Tomador / Hospital</th>
        <th>Data Emissão</th>
        <th>Serviços</th>
        <th>Peças</th>
        <th>Total NF</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {linhas_nfs or '<tr><td colspan="8" style="text-align:center;color:#64748b;">Nenhuma nota fiscal emitida nesta competência.</td></tr>'}
    </tbody>
  </table>

  {f"""
  <div class="section-title" style="color:#991b1b;border-color:#fecaca;">2. Notas Fiscais Canceladas no Período (Estornos Fiscais)</div>
  <table>
    <thead>
      <tr style="background:#991b1b;">
        <th>Nº NF</th>
        <th>OS</th>
        <th>Tomador</th>
        <th>Cancelamento</th>
        <th colspan="2">Justificativa Formal</th>
        <th>Valor Estornado</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {linhas_canceladas}
    </tbody>
  </table>
  """ if linhas_canceladas else ''}

  <div class="section-title">3. Despesas Operacionais Recorrentes da Empresa (Custos Fixos)</div>
  <table>
    <thead>
      <tr>
        <th>Vencimento</th>
        <th>Categoria</th>
        <th>Descrição da Obrigação</th>
        <th>Fornecedor / Favorecido</th>
        <th>Forma Pagto</th>
        <th>Valor Mensal</th>
      </tr>
    </thead>
    <tbody>
      {linhas_despesas}
      <tr style="background:#f1f5f9;font-weight:bold;">
        <td colspan="5" style="text-align:right;">TOTAL DE DESPESAS OPERACIONAIS FIXAS:</td>
        <td style="color:#b91c1c;">R$ {total_despesas:,.2f}</td>
      </tr>
    </tbody>
  </table>

  <div class="section-title">4. Resumo de Encargos e Impostos Estimados para Guia (DAS / ISS)</div>
  <table style="width:70%;">
    <tr><td><b>ISS Municipal (Fortaleza 5.0% s/ Serviços):</b></td><td style="text-align:right;"><b>R$ {iss_devido:,.2f}</b></td></tr>
    <tr><td><b>Simples Nacional DAS Estimado (Serviços + Peças):</b></td><td style="text-align:right;"><b>R$ {simples_estimado:,.2f}</b></td></tr>
    <tr><td><b>PIS (0.65% Estimado s/ Faturamento):</b></td><td style="text-align:right;">R$ {round(total_bruto*0.0065, 2):,.2f}</td></tr>
    <tr><td><b>COFINS (3.00% Estimado s/ Faturamento):</b></td><td style="text-align:right;">R$ {round(total_bruto*0.03, 2):,.2f}</td></tr>
  </table>

  <div class="signatures">
    <div class="sig-line">
      <b>eMED ELETROMEDICINA LTDA</b><br>
      Diretoria Administrativa / Financeira
    </div>
    <div class="sig-line">
      <b>ASSESSORIA CONTÁBIL &amp; FISCAL</b><br>
      Contador Responsável / CRC-CE
    </div>
  </div>
</div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def api_transportadoras_listar(request: web.Request) -> web.Response:
    """Retorna o cadastro de transportadoras parceiras e operadores de carga pesada/munck."""
    with get_db_connection(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM transportadoras_parceiras ORDER BY possui_seguro_carga DESC, avaliacao_estrelas DESC, id ASC", conn)
        return web.json_response({"ok": True, "transportadoras": df.to_dict(orient="records")})


async def api_transportadoras_salvar(request: web.Request) -> web.Response:
    """Cadastra ou atualiza uma transportadora parceira."""
    body = await request.json()
    tid = body.get("id")
    nome = limpar_texto(body.get("nome"), "")
    if not nome:
        return web.json_response({"ok": False, "msg": "Nome da transportadora é obrigatório."}, status=400)
        
    cnpj = limpar_texto(body.get("cnpj"), "")
    telefone = limpar_texto(body.get("telefone"), "")
    whatsapp = limpar_texto(body.get("whatsapp"), "")
    contato = limpar_texto(body.get("contato_responsavel"), "")
    cidades = limpar_texto(body.get("cidades_atendidas"), "Fortaleza e Região Metropolitana")
    veiculos = limpar_texto(body.get("tipos_veiculo"), "Caminhão Munck, Plataforma Elevatória")
    possui_seguro = 1 if body.get("possui_seguro_carga") in [1, True, "1", "true"] else 0
    valor_seguro = float(limpar_float(body.get("valor_cobertura_seguro"), 500000.0))
    estrelas = int(limpar_int(body.get("avaliacao_estrelas"), 5))
    obs = limpar_texto(body.get("observacoes"), "")
    agora = obter_agora_brasil_str("%Y-%m-%d %H:%M:%S")
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        if tid:
            cur.execute("""
                UPDATE transportadoras_parceiras SET
                    nome = ?, cnpj = ?, telefone = ?, whatsapp = ?, contato_responsavel = ?,
                    cidades_atendidas = ?, tipos_veiculo = ?, possui_seguro_carga = ?,
                    valor_cobertura_seguro = ?, avaliacao_estrelas = ?, observacoes = ?
                WHERE id = ?
            """, (nome, cnpj, telefone, whatsapp, contato, cidades, veiculos, possui_seguro, valor_seguro, estrelas, obs, int(tid)))
            msg = f"Transportadora '{nome}' atualizada com sucesso!"
        else:
            cur.execute("""
                INSERT INTO transportadoras_parceiras (
                    nome, cnpj, telefone, whatsapp, contato_responsavel, cidades_atendidas,
                    tipos_veiculo, possui_seguro_carga, valor_cobertura_seguro, avaliacao_estrelas,
                    status, observacoes, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ATIVO', ?, ?)
            """, (nome, cnpj, telefone, whatsapp, contato, cidades, veiculos, possui_seguro, valor_seguro, estrelas, obs, agora))
            msg = f"Transportadora '{nome}' cadastrada com sucesso!"
        conn.commit()
        
    return web.json_response({"ok": True, "msg": msg})


async def api_cotacoes_transporte_listar(request: web.Request) -> web.Response:
    """Lista as cotações de transporte registradas."""
    with get_db_connection(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM cotacoes_transporte ORDER BY id DESC LIMIT 100", conn)
        return web.json_response({"ok": True, "cotacoes": df.to_dict(orient="records")})


async def api_cotacoes_transporte_salvar(request: web.Request) -> web.Response:
    """Registra uma nova cotação de transporte ou atualiza o status de aprovação."""
    body = await request.json()
    cid = body.get("id")
    carga = limpar_texto(body.get("carga_descricao"), "")
    if not carga:
        return web.json_response({"ok": False, "msg": "Descrição da carga é obrigatória."}, status=400)
        
    os_id = str(body.get("os_id", "")).strip()
    cliente = limpar_texto(body.get("cliente"), "")
    origem_cidade = limpar_texto(body.get("origem_cidade"), "FORTALEZA")
    origem_uf = limpar_texto(body.get("origem_uf"), "CE")
    destino_cidade = limpar_texto(body.get("destino_cidade"), "FORTALEZA")
    destino_uf = limpar_texto(body.get("destino_uf"), "CE")
    tipo_veiculo = limpar_texto(body.get("tipo_veiculo"), "Caminhão Munck")
    peso_kg = float(limpar_float(body.get("peso_kg"), 0.0))
    dimensoes = limpar_texto(body.get("dimensoes"), "")
    valor_declarado = float(limpar_float(body.get("valor_declarado_carga"), 0.0))
    exige_seguro = 1 if body.get("exige_seguro") in [1, True, "1", "true"] else 0
    transportadora = limpar_texto(body.get("transportadora_escolhida"), "")
    valor_fechado = float(limpar_float(body.get("valor_fechado"), 0.0))
    status_cotacao = limpar_texto(body.get("status_cotacao"), "EM COTAÇÃO")
    data_prevista = limpar_texto(body.get("data_prevista_transporte"), "")
    obs = limpar_texto(body.get("observacoes"), "")
    agora_br = obter_agora_brasil_str("%d/%m/%Y")
    agora_iso = obter_agora_brasil_str("%Y-%m-%d %H:%M:%S")
    ano_atual = datetime.now().year
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        if cid:
            cur.execute("""
                UPDATE cotacoes_transporte SET
                    carga_descricao = ?, destino_cidade = ?, destino_uf = ?, tipo_veiculo = ?,
                    peso_kg = ?, dimensoes = ?, valor_declarado_carga = ?, exige_seguro = ?,
                    transportadora_escolhida = ?, valor_fechado = ?, status_cotacao = ?,
                    data_prevista_transporte = ?, observacoes = ?
                WHERE id = ?
            """, (carga, destino_cidade, destino_uf, tipo_veiculo, peso_kg, dimensoes, valor_declarado, exige_seguro, transportadora, valor_fechado, status_cotacao, data_prevista, obs, int(cid)))
            msg = f"Cotação atualizada com sucesso!"
        else:
            cur.execute("SELECT COUNT(*) FROM cotacoes_transporte")
            tot = cur.fetchone()[0] + 1
            num_cot = f"COT-{ano_atual}-{tot:04d}"
            cur.execute("""
                INSERT INTO cotacoes_transporte (
                    numero_cotacao, os_id, cliente, carga_descricao, origem_cidade, origem_uf,
                    destino_cidade, destino_uf, tipo_veiculo, peso_kg, dimensoes,
                    valor_declarado_carga, exige_seguro, transportadora_escolhida, valor_fechado,
                    status_cotacao, data_cotacao, data_prevista_transporte, observacoes, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                num_cot, os_id, cliente, carga, origem_cidade, origem_uf,
                destino_cidade, destino_uf, tipo_veiculo, peso_kg, dimensoes,
                valor_declarado, exige_seguro, transportadora, valor_fechado,
                status_cotacao, agora_br, data_prevista, obs, agora_iso
            ))
            msg = f"Cotação #{num_cot} registrada com sucesso!"
        conn.commit()
        
    return web.json_response({"ok": True, "msg": msg})


async def api_despesas_recorrentes_salvar(request: web.Request) -> web.Response:
    """Salva ou atualiza uma despesa operacional recorrente da empresa."""
    body = await request.json()
    did = body.get("id")
    categoria = limpar_texto(body.get("categoria"), "OUTROS")
    descricao = limpar_texto(body.get("descricao"), "")
    if not descricao:
        return web.json_response({"ok": False, "msg": "Descrição da despesa é obrigatória."}, status=400)
        
    fornecedor = limpar_texto(body.get("fornecedor"), "")
    valor = float(limpar_float(body.get("valor_mensal_estimado"), 0.0))
    dia = int(limpar_int(body.get("dia_vencimento"), 10))
    forma = limpar_texto(body.get("forma_pagamento"), "BOLETO")
    status = limpar_texto(body.get("status"), "ATIVO")
    obs = limpar_texto(body.get("observacoes"), "")
    agora = obter_agora_brasil_str("%Y-%m-%d %H:%M:%S")
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        if did:
            cur.execute("""
                UPDATE despesas_recorrentes SET
                    categoria = ?, descricao = ?, fornecedor = ?, valor_mensal_estimado = ?,
                    dia_vencimento = ?, forma_pagamento = ?, status = ?, observacoes = ?
                WHERE id = ?
            """, (categoria, descricao, fornecedor, valor, dia, forma, status, obs, int(did)))
            msg = "Despesa recorrente atualizada!"
        else:
            cur.execute("""
                INSERT INTO despesas_recorrentes (
                    categoria, descricao, fornecedor, valor_mensal_estimado, dia_vencimento,
                    forma_pagamento, status, observacoes, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (categoria, descricao, fornecedor, valor, dia, forma, status, obs, agora))
            msg = "Despesa recorrente cadastrada!"
        conn.commit()
        
    return web.json_response({"ok": True, "msg": msg})



# ==============================================================================
# INTEGRAÇÃO BANCÁRIA PIX AUTOMÁTICA & ROBÔ DE RASTREAMENTO DE PEÇAS (24x/DIA)
# ==============================================================================

async def api_pix_webhook(request: web.Request) -> web.Response:
    """
    Webhook Oficial de Baixa Automática PIX / TED bancária.
    Recebe payloads de bancos (Itaú, Cora, Inter, Asaas, etc.) e processa conciliação
    automática em 3 níveis (txid, dupla checagem CNPJ + Valor, ou Nome + Valor).
    """
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"ok": False, "msg": "Payload JSON inválido."}, status=400)
    
    # Extração inteligente de campos compatível com BACEN e APIs bancárias
    txid = str(body.get("txid", "")).strip()
    valor = limpar_float(body.get("valor", 0.0))
    cnpj = str(body.get("cnpj", "") or body.get("cpf", "")).strip()
    nome = str(body.get("nome", "") or body.get("nome_pagador", "")).strip()
    e2e = str(body.get("end_to_end_id", "") or body.get("endToEndId", "")).strip()
    
    # Suporte ao formato aninhado BACEN: {"pix": [{"txid": "...", "valor": "...", "pagador": {...}}]}
    if "pix" in body and isinstance(body["pix"], list) and len(body["pix"]) > 0:
        pix_item = body["pix"][0]
        txid = txid or str(pix_item.get("txid", "")).strip()
        valor = valor or limpar_float(pix_item.get("valor", 0.0))
        e2e = e2e or str(pix_item.get("endToEndId", "")).strip()
        pagador = pix_item.get("pagador", {})
        if isinstance(pagador, dict):
            cnpj = cnpj or str(pagador.get("cnpj", "") or pagador.get("cpf", "")).strip()
            nome = nome or str(pagador.get("nome", "")).strip()

    resultado = conciliar_pagamento_bancario_duplo(
        DB_NAME,
        cnpj=cnpj,
        valor=valor,
        txid=txid,
        end_to_end_id=e2e,
        nome_pagador=nome
    )
    
    if resultado.get("conciliado"):
        # Notifica console do servidor e atualiza estado
        print(f"💰 [BAIXA AUTOMÁTICA PIX] OS #{resultado.get('os_id')} liquidada! Cliente: {resultado.get('cliente')} - R$ {resultado.get('valor'):.2f}")
    
    return web.json_response(resultado)


async def api_pix_simular_webhook(request: web.Request) -> web.Response:
    """Dispara uma simulação de webhook de baixa automática para testes do operador."""
    body = await request.json()
    os_id = str(body.get("os_id", "")).strip()
    valor = limpar_float(body.get("valor", 0.0))
    cnpj = str(body.get("cnpj", "")).strip()
    nome = str(body.get("nome", "")).strip()
    txid = str(body.get("txid", "")).strip()
    
    if os_id and not txid:
        txid = f"EMED-OS-{os_id}"
        
    resultado = conciliar_pagamento_bancario_duplo(
        DB_NAME,
        cnpj=cnpj,
        valor=valor,
        txid=txid,
        nome_pagador=nome
    )
    return web.json_response(resultado)


async def api_robo_rastreio_status(request: web.Request) -> web.Response:
    """Retorna o status atual, métricas e histórico recente do Robô de Rastreamento (24x/dia)."""
    status_dados = obter_status_robo(DB_NAME)
    return web.json_response({"ok": True, "robo": status_dados})


async def api_robo_rastreio_executar(request: web.Request) -> web.Response:
    """Executa manualmente 1 ciclo imediato do Robô de Rastreamento de Peças."""
    res = executar_ciclo_verificacao(DB_NAME)
    return web.json_response(res)


async def api_robo_rastreio_simular(request: web.Request) -> web.Response:
    """Simula a entrega de um pedido de compra para teste imediato de entrada em estoque."""
    body = await request.json()
    ped_id = int(body.get("id", 0))
    codigo = str(body.get("codigo_rastreio", "")).strip() or f"SIMULA_ENTREGUE_{ped_id}"
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE solicitacoes_pecas SET codigo_rastreio = ? WHERE id = ?", (codigo, ped_id))
        conn.commit()
        
    res = executar_ciclo_verificacao(DB_NAME)
    return web.json_response({"ok": True, "simulacao": res})


async def _robo_rastreamento_pecas_task():
    """Tarefa em segundo plano do Robô de Rastreamento: executa 24 vezes por dia (a cada 60 minutos = 3600s)."""
    await asyncio.sleep(20)  # Aguarda 20 segundos para estabilização do boot
    while True:
        try:
            print("🤖 [Robô de Rastreamento] Iniciando verificação programada de encomendas (24x/dia)...")
            res = executar_ciclo_verificacao(DB_NAME)
            print(f"🤖 [Robô de Rastreamento] Ciclo #{res.get('ciclo')} finalizado: {res.get('itens_processados')} pedidos monitorados, {res.get('itens_entregues')} entregas registradas.")
        except Exception as e:
            print(f"⚠️ [Robô de Rastreamento] Erro no ciclo: {e}")
        await asyncio.sleep(3600)  # 3600 segundos = 1 hora (24 verificações em 24 horas)


async def api_carga_guia_retirada(request: web.Request) -> web.Response:
    """Retorna os dados e mensagem formatada para WhatsApp de retirada no Aeroporto/Transportadora."""
    ped_id = int(request.match_info.get("id", 0))
    dados = gerar_mensagem_retirada_carga(DB_NAME, ped_id)
    return web.json_response(dados)


async def api_carga_confirmar_retirada(request: web.Request) -> web.Response:
    """Confirma que o portador (Paulinho) retirou a carga no aeroporto e dá entrada física no estoque."""
    body = await request.json()
    ped_id = int(body.get("id", 0))
    portador = limpar_texto(body.get("portador", "Paulinho"), "Paulinho")
    res = confirmar_retirada_paulinho(DB_NAME, ped_id, portador)
    return web.json_response(res)


async def api_carga_simular_aeroporto(request: web.Request) -> web.Response:
    """Simula que a carga aérea chegou no aeroporto de cargas (TECA) aguardando o Paulinho."""
    body = await request.json()
    ped_id = int(body.get("id", 0))
    codigo = str(body.get("codigo_rastreio", "")).strip() or f"AWB_AEROPORTO_{ped_id}"
    
    with get_db_connection(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE solicitacoes_pecas
            SET codigo_rastreio = ?,
                transportadora = 'Azul Cargo Express / Aeroporto',
                status_compra = 'AGUARDANDO_RETIRADA_AEROPORTO',
                status_pedido = '✈️ DISPONÍVEL P/ RETIRADA NO AEROPORTO (PORTADOR: PAULINHO)',
                tipo_entrega = 'RETIRADA_AEROPORTO',
                portador_retirada = 'Paulinho',
                local_retirada = 'Aeroporto Pinto Martins (TECA) / Fortaleza-CE',
                ultimo_rastreio_status = 'AGUARDANDO_RETIRADA',
                ultimo_rastreio_cidade = 'Fortaleza / CE',
                ultimo_rastreio_data = ?
            WHERE id = ?
        """, (codigo, obter_agora_brasil_str("%d/%m/%Y %H:%M"), ped_id))
        conn.commit()
        
    return web.json_response({
        "ok": True,
        "msg": f"✈️ Carga do Pedido #{ped_id} marcada como Disponível no Aeroporto para o Paulinho!"
    })


async def handle_simbolo_emed(request: web.Request) -> web.Response:
    """Serve o símbolo/logo oficial em alta resolução e fundo transparente da EMED."""
    candidatos = [
        os.path.join(BASE_DIR, "emed_pwa_static", "simbolo_emed_transparente.png"),
        os.path.join(BASE_DIR, "emed_pwa_static", "simbolo_emed_oficial.png"),
        os.path.join(BASE_DIR, "emed_pwa_static", "simbolo_emed.png"),
        os.path.join(BASE_DIR, "emed1.jpg")
    ]
    for c in candidatos:
        if os.path.exists(c):
            with open(c, "rb") as f:
                content_type = "image/png" if c.endswith(".png") else "image/jpeg"
                return web.Response(body=f.read(), content_type=content_type)
    return web.Response(status=404)


async def api_hospital_autorizacao(request: web.Request) -> web.Response:
    """Retorna dados do credenciamento e texto formatado para WhatsApp da portaria."""
    os_id = int(request.match_info.get("id", 0))
    dados = obter_dados_credenciamento_os(DB_NAME, os_id)
    if not dados.get("ok"):
        return web.json_response(dados, status=404)
    texto_wa = gerar_texto_whatsapp_portaria(dados)
    dados["texto_whatsapp"] = texto_wa
    return web.json_response(dados)


async def api_hospital_autorizacao_imprimir(request: web.Request) -> web.Response:
    """Gera o documento formal em HTML/PDF de Comunicação de Entrada no Hospital (ex: São Carlos)."""
    os_id = int(request.match_info.get("id", 0))
    dados = obter_dados_credenciamento_os(DB_NAME, os_id)
    if not dados.get("ok"):
        return web.Response(text="Ordem de serviço não encontrada.", status=404)
    html = gerar_html_autorizacao_entrada(dados)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def api_equipamento_historico(request: web.Request) -> web.Response:
    """Retorna os dados completos e histórico anual de manutenções do equipamento."""
    equip_id = int(request.match_info.get("id", 0))
    dados = obter_historico_anual_equipamento(DB_NAME, equip_id)
    return web.json_response(dados)


async def handle_qrcode_equipamento(request: web.Request) -> web.Response:
    """Exibe o prontuário digital anual do equipamento escaneado pelo QR Code."""
    equip_id = int(request.match_info.get("id", 0))
    dados = obter_historico_anual_equipamento(DB_NAME, equip_id)
    if not dados.get("ok"):
        return web.Response(text="Equipamento não localizado.", status=404)
    html = gerar_pagina_prontuario_equipamento(dados)
    return web.Response(text=html, content_type="text/html", charset="utf-8")


async def handle_qrcode_equipamento_etiqueta(request: web.Request) -> web.Response:
    """Gera a Etiqueta Física com QR Code para impressão e colagem no chassi da máquina."""
    equip_id = int(request.match_info.get("id", 0))
    dados = obter_historico_anual_equipamento(DB_NAME, equip_id)
    if not dados.get("ok"):
        return web.Response(text="Equipamento não localizado.", status=404)
        
    host = request.headers.get("Host", "127.0.0.1:8502")
    proto = "https" if request.secure or "render" in host.lower() else "http"
    url_publica = f"{proto}://{host}/qrcode/equipamento/{equip_id}"
    qr_b64 = gerar_qrcode_base64(url_publica)
    
    html = gerar_etiqueta_qrcode_html(dados, qr_b64)
    return web.Response(text=html, content_type="text/html", charset="utf-8")

def criar_app() -> web.Application:
    garantir_schema_rastreio_completo(DB_NAME)
    garantir_schema_fiscal_contabil(DB_NAME)
    garantir_schema_medicina_trabalho(DB_NAME)
    app = web.Application(client_max_size=25 * 1024 * 1024)

    # Webhook de Baixa Automatica PIX e Robo de Rastreamento 24x/dia
    app.router.add_post("/api/pix/webhook", api_pix_webhook)
    app.router.add_post("/api/pix/simular-webhook", api_pix_simular_webhook)
    app.router.add_get("/api/almoxarifado/rastreio/status", api_robo_rastreio_status)
    app.router.add_post("/api/almoxarifado/rastreio/executar-robo", api_robo_rastreio_executar)
    app.router.add_post("/api/almoxarifado/rastreio/simular", api_robo_rastreio_simular)
    app.router.add_get("/api/almoxarifado/carga/guia-retirada/{id}", api_carga_guia_retirada)
    # Símbolo Oficial, Credenciamento Hospitalar & QR Code Equipamento
    app.router.add_get("/api/simbolo-emed", handle_simbolo_emed)
    app.router.add_get("/api/hospital/autorizacao-entrada/{id}", api_hospital_autorizacao)
    app.router.add_get("/api/hospital/autorizacao-entrada/{id}/imprimir", api_hospital_autorizacao_imprimir)
    app.router.add_get("/api/equipamento/{id}/historico-anual", api_equipamento_historico)
    app.router.add_get("/qrcode/equipamento/{id}", handle_qrcode_equipamento)
    app.router.add_get("/qrcode/equipamento/{id}/etiqueta", handle_qrcode_equipamento_etiqueta)

    app.router.add_post("/api/almoxarifado/carga/confirmar-retirada", api_carga_confirmar_retirada)
    app.router.add_post("/api/almoxarifado/carga/simular-aeroporto", api_carga_simular_aeroporto)




    app.router.add_get("/", handle_index)



    app.router.add_get("/manifest.json", handle_manifest)



    app.router.add_get("/sw.js", handle_sw)



    app.router.add_get("/api/logo", handle_logo)



    app.router.add_get("/api/logo-circle", handle_logo_circle)



    app.router.add_get("/api/ping", api_ping)



    app.router.add_get("/healthz", api_ping)



    app.router.add_get("/api/bootstrap", api_bootstrap)

    app.router.add_get("/api/kardex", api_kardex)



    app.router.add_get("/api/checklist", api_checklist)



    app.router.add_get("/api/triagem", api_triagem)



    app.router.add_post("/api/rascunho", api_salvar_rascunho)



    app.router.add_post("/api/iniciar-rota", api_iniciar_rota)

    app.router.add_post("/api/checkin", api_checkin)



    app.router.add_post("/api/salvar-os", api_salvar_os)



    app.router.add_post("/api/nova-os", api_nova_os)

    app.router.add_get("/api/ordens", api_ordens)

    app.router.add_post("/api/ordens", api_ordens)

    app.router.add_post("/api/sync_offline", api_sync_offline)

    app.router.add_get("/api/cliente-pendencias", api_cliente_pendencias)
    app.router.add_post("/api/propostas", api_proposta_salvar)



    app.router.add_post("/api/reabrir-os", api_reabrir_os)



    app.router.add_post("/api/rotas/despachar", api_despachar_rota)

    app.router.add_post("/api/despachar-rota", api_despachar_rota)



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



    app.router.add_get("/api/ferramentas", api_ferramentas_listar)

    app.router.add_post("/api/ferramentas/acao", api_ferramentas_acao)
    app.router.add_post("/api/ferramentas/bipagem-lote", api_ferramentas_bipagem_lote)
    app.router.add_get("/api/ferramentas/minhas", api_ferramentas_minhas)

    app.router.add_post("/api/almoxarifado/compra-acao", api_almox_compra_acao)

    app.router.add_post("/api/almoxarifado/status", api_almox_status)
    app.router.add_post("/api/auditoria/excluir", api_auditoria_excluir)
    app.router.add_get("/api/auditoria/listar", api_auditoria_listar)



    app.router.add_post("/api/pix/gerar", api_pix_gerar)



    app.router.add_post("/api/pix/liquidar", api_pix_liquidar)



    app.router.add_post("/api/config", api_config)



    app.router.add_get("/api/respostas-tecnicas", api_respostas_tecnicas_listar)



    app.router.add_post("/api/respostas-tecnicas", api_respostas_tecnicas_salvar)



    app.router.add_delete("/api/respostas-tecnicas/{id}", api_respostas_tecnicas_deletar)



    app.router.add_post("/api/respostas-tecnicas/deletar", api_respostas_tecnicas_deletar)



    app.router.add_post("/api/os/nf-salvar", api_os_nf_salvar)
    app.router.add_get("/api/fiscal/danfe/{os_id}", api_fiscal_danfe)
    app.router.add_post("/api/fiscal/enviar-cliente", api_fiscal_enviar_cliente)
    app.router.add_post("/api/fiscal/enviar-contabilidade", api_fiscal_enviar_contabilidade)
    app.router.add_get("/api/fiscal/relatorio-contabil-csv", api_fiscal_relatorio_contabil_csv)
    app.router.add_post("/api/tecnico/assinatura-salvar", api_tecnico_assinatura_salvar)
    app.router.add_post("/api/tecnico/renovar-medico", api_tecnico_renovar_medico)
    app.router.add_get("/api/tecnico/historico-medico/{id}", api_tecnico_historico_medico)
    app.router.add_post("/api/fiscal/liberar-quarentena", api_fiscal_liberar_quarentena)
    app.router.add_post("/api/fiscal/cancelar-nota", api_fiscal_cancelar_nota)
    app.router.add_get("/api/financeiro/relatorio-contabil", api_financeiro_relatorio_contabil)
    app.router.add_get("/api/financeiro/relatorio-contabil/imprimir", api_financeiro_relatorio_contabil_imprimir)
    app.router.add_get("/api/transportadoras", api_transportadoras_listar)
    app.router.add_post("/api/transportadoras/salvar", api_transportadoras_salvar)
    app.router.add_get("/api/cotacoes-transporte", api_cotacoes_transporte_listar)
    app.router.add_post("/api/cotacoes-transporte/salvar", api_cotacoes_transporte_salvar)
    app.router.add_post("/api/despesas-recorrentes/salvar", api_despesas_recorrentes_salvar)
    app.router.add_get("/api/remessas-diagnostico", api_remessas_diagnostico_listar)
    app.router.add_post("/api/remessas-diagnostico/salvar", api_remessas_diagnostico_salvar)
    app.router.add_post("/api/remessas-diagnostico/retorno", api_remessas_diagnostico_retorno)
    app.router.add_get("/api/remessas-diagnostico/guia/{id}", api_remessas_diagnostico_guia)



    app.router.add_post("/api/proposta/salvar", api_proposta_salvar)



    app.router.add_get("/api/pdf/{os_id}", api_pdf_os)



    app.router.add_get("/api/html/{os_id}", api_html_os)



    app.router.add_get("/api/imprimir/{os_id}", api_imprimir_os)



    app.router.add_get("/api/manual", api_manual_download)



    app.router.add_get("/api/video", api_video_stream)



    app.router.add_get("/api/exportar-excel", api_exportar_excel)

    app.router.add_post("/api/importar-excel", api_importar_excel)



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



    web.run_app(criar_app(), host="0.0.0.0", port=porta, handle_signals=False)



