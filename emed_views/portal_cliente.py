# -*- coding: utf-8 -*-
"""
Módulo Portal do Cliente (Área Restrita) para o Sistema EMED.
Permite que clínicas e hospitais acessem seu ambiente exclusivo via CNPJ ou seleção autenticada,
visualizem seu parque de equipamentos, acompanhem status de OS em tempo real, abram chamados
com a triagem cirúrgica inteligente, paguem via PIX e realizem avaliação pós-atendimento.
"""

import os
import sqlite3
import datetime
import pandas as pd
import streamlit as st
from emed_core import limpar_texto, obter_id_os
from emed_services import AppContext, salvar_dados_seguro
from emed_views.emedonline import _obter_perguntas_triagem_dinamica, _detectar_modalidade
from emed_views.chamados_os import _gerar_html_os_formatada
from emed_views.conciliacao_pix import gerar_payload_pix, gerar_qr_code_pix_base64
from emed_views.pesquisa_satisfacao import registrar_pesquisa, URL_GOOGLE_REVIEW_OFICIAL, obter_url_google_review


def render_portal_cliente(ctx: AppContext):
    """Renderiza a Área Restrita e Portal de Autoatendimento do Cliente."""
    df = ctx.df
    db_name = ctx.db_name

    # Obter lista de clientes cadastrados a partir do SQLite clientes_equipamentos e da base de chamados
    with sqlite3.connect(db_name) as conn:
        try:
            df_cad = pd.read_sql_query("SELECT DISTINCT cliente, cnpj, cidade FROM clientes_equipamentos WHERE cliente IS NOT NULL AND cliente != ''", conn)
        except Exception:
            df_cad = pd.DataFrame(columns=["cliente", "cnpj", "cidade"])

    # Mescla com os clientes de chamados
    clientes_unicos = sorted(list(set(
        [limpar_texto(c, "") for c in df["cliente"].dropna().unique() if limpar_texto(c, "")] +
        [limpar_texto(c, "") for c in df_cad["cliente"].dropna().unique() if limpar_texto(c, "")]
    )))

    # Sessão de autenticação do cliente
    if "portal_cliente_autenticado" not in st.session_state:
        st.session_state["portal_cliente_autenticado"] = False
        st.session_state["portal_cliente_nome"] = ""
        st.session_state["portal_cliente_cnpj"] = ""

    # TELA DE LOGIN / AUTENTICAÇÃO
    if not st.session_state["portal_cliente_autenticado"]:
        st.markdown("""
            <div style="background: linear-gradient(135deg, #091e3a 0%, #17325c 60%, #1e40af 100%);
                        border-radius: 14px; padding: 26px 30px; border: 2px solid #3b82f6;
                        box-shadow: 0 6px 20px rgba(0,0,0,0.4); margin-bottom: 24px; text-align: center;">
                <h1 style="color: #60a5fa; margin: 0; font-size: 28px; font-weight: 800;">
                    🏥 PORTAL DO CLIENTE — ÁREA RESTRITA
                </h1>
                <p style="color: #cbd5e1; margin: 8px 0 0 0; font-size: 15px;">
                    Acesso exclusivo para hospitais, clínicas e unidades de diagnóstico credenciadas da EMED.
                </p>
            </div>
        """, unsafe_allow_html=True)

        col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
        with col_l2:
            st.markdown("#### 🔐 Identificação da Unidade Hospitalar")
            cli_escolhido = st.selectbox(
                "Selecione sua Instituição / Hospital:",
                clientes_unicos,
                index=0 if clientes_unicos else None,
                help="Escolha sua unidade na lista de clientes cadastrados da EMED."
            )

            # Busca CNPJ se houver
            cnpj_sugerido = ""
            if not df_cad.empty:
                match_cad = df_cad[df_cad["cliente"].str.upper() == cli_escolhido.upper()]
                if not match_cad.empty:
                    cnpj_sugerido = limpar_texto(match_cad.iloc[0].get("cnpj"), "")

            cnpj_input = st.text_input("CNPJ da Instituição:", value=cnpj_sugerido, placeholder="00.000.000/0001-00")
            cod_acesso = st.text_input("Código de Acesso do Cliente / PIN:", type="password", value="1234", help="Código padrão para acesso: 1234")

            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("🚀 Entrar no Portal do Cliente", type="primary", use_container_width=True):
                if not cli_escolhido:
                    st.error("Por favor, selecione uma instituição hospitalar.")
                else:
                    st.session_state["portal_cliente_autenticado"] = True
                    st.session_state["portal_cliente_nome"] = cli_escolhido
                    st.session_state["portal_cliente_cnpj"] = cnpj_input
                    st.success(f"Bem-vindo(a), {cli_escolhido}!")
                    st.rerun()
        return

    # AMBIENTE AUTENTICADO DO CLIENTE
    cliente_atual = st.session_state["portal_cliente_nome"]
    cnpj_atual = st.session_state["portal_cliente_cnpj"]

    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown(f"""
            <div style="background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
                        border-left: 6px solid #10b981; padding: 16px 20px; border-radius: 10px; margin-bottom: 20px;">
                <div style="color: #6ee7b7; font-size: 13px; font-weight: 800;">🏥 CLIENTE AUTENTICADO — ÁREA RESTRITA</div>
                <h2 style="color: #f8fafc; margin: 4px 0 0 0; font-size: 24px;">{cliente_atual}</h2>
                <div style="color: #94a3b8; font-size: 13px; margin-top: 4px;">CNPJ: {cnpj_atual or 'Credenciamento Oficial EMED'} | Status: <b>CONTRATO ATIVO</b></div>
            </div>
        """, unsafe_allow_html=True)
    with col_h2:
        if st.button("🚪 Sair do Portal", type="secondary", use_container_width=True):
            st.session_state["portal_cliente_autenticado"] = False
            st.session_state["portal_cliente_nome"] = ""
            st.session_state["portal_cliente_cnpj"] = ""
            st.rerun()

    # Filtra chamados e equipamentos deste cliente
    df_meus_chamados = df[df["cliente"].astype(str).str.strip().str.upper() == cliente_atual.strip().upper()]

    with sqlite3.connect(db_name) as conn:
        try:
            df_meus_equip = pd.read_sql_query(
                "SELECT * FROM clientes_equipamentos WHERE UPPER(TRIM(cliente)) = ?",
                conn,
                params=(cliente_atual.strip().upper(),)
            )
        except Exception:
            df_meus_equip = pd.DataFrame()

    tab_os, tab_novo, tab_parque, tab_pix, tab_feedback = st.tabs([
        "📋 1. Meus Chamados & Status em Tempo Real",
        "🎫 2. Abrir Novo Chamado (Triagem Rápida)",
        "🏥 3. Meu Parque de Equipamentos",
        "💳 4. Minhas Faturas & Pagamento PIX",
        "⭐ 5. Avaliar Atendimento (Google Review)",
    ])

    # =========================================================================
    # TAB 1: MEUS CHAMADOS & STATUS EM TEMPO REAL
    # =========================================================================
    with tab_os:
        st.markdown("#### 📋 Acompanhamento de Ordens de Serviço")
        if df_meus_chamados.empty:
            st.info("Nenhum chamado registrado para esta unidade hospitalar até o momento. Abra uma solicitação na aba 2.")
        else:
            for idx_os, r_os in df_meus_chamados.iterrows():
                num_os = obter_id_os(idx_os, r_os)
                st_os = limpar_texto(r_os.get("status"), "ATIVO").upper()
                equip_os = limpar_texto(r_os.get("equipamento"), "EQUIPAMENTO HOSPITALAR")
                tec_os = limpar_texto(r_os.get("tecnico_responsavel"), "A DEFINIR / EM DESPACHO")
                dt_os = limpar_texto(r_os.get("data_agendamento"), "N/D")
                srv_os = limpar_texto(r_os.get("tipo_servico"), "CORRETIVA")
                defeito_os = limpar_texto(r_os.get("defeito_relatado", r_os.get("pendencias")), "Sem observações")

                if st_os == "CONCLUÍDO":
                    cor_status = "#10b981"
                    status_lbl = "🟢 CONCLUÍDO / LIBERADO PARA EXAMES"
                elif "OBSERVA" in st_os:
                    cor_status = "#8b5cf6"
                    status_lbl = "🔬 EM OBSERVAÇÃO TÉCNICA"
                elif "PEÇA" in st_os or "PECA" in st_os:
                    cor_status = "#f59e0b"
                    status_lbl = "📦 AGUARDANDO PEÇA / ALMOXARIFADO"
                elif st_os == "EM ATENDIMENTO":
                    cor_status = "#38bdf8"
                    status_lbl = "🔧 TÉCNICO NO LOCAL / EM ATENDIMENTO"
                else:
                    cor_status = "#ef4444"
                    status_lbl = "🚨 CHAMADO ATIVO / EQUIPE EM DESPACHO"

                st.markdown(f"""
                    <div style="background: #1e293b; border-left: 6px solid {cor_status}; padding: 16px 20px; border-radius: 8px; margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                            <span style="color: #60a5fa; font-weight: 800; font-size: 17px;">OS #{num_os} — {equip_os}</span>
                            <span style="background: rgba(255,255,255,0.08); padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 13px; color: {cor_status};">{status_lbl}</span>
                        </div>
                        <div style="color: #cbd5e1; font-size: 13.5px; margin-top: 6px;">
                            <b>Tipo:</b> {srv_os} | <b>Data:</b> {dt_os} | <b>Técnico Designado:</b> {tec_os}
                        </div>
                        <div style="background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 6px; margin-top: 8px; font-size: 13px; color: #e2e8f0;">
                            <b>Defeito Relatado:</b> {defeito_os}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                if "CONCLU" in st_os:
                    html_os = _gerar_html_os_formatada(str(num_os), r_os, getattr(ctx, "equipa_tecnica", {}))
                    st.download_button(
                        label="📄 Baixar Folha de OS Assinada (PDF/HTML)",
                        data=html_os,
                        file_name=f"OS_{num_os}.html",
                        mime="text/html",
                        key=f"dl_os_cliente_{idx_os}_{num_os}",
                        use_container_width=True,
                    )

    # =========================================================================
    # TAB 2: ABRIR NOVO CHAMADO
    # =========================================================================
    with tab_novo:
        st.markdown("#### 🎫 Abertura Ágil de Chamado com Triagem Cirúrgica")
        
        # Puxa equipamentos deste cliente
        lista_equip_opcoes = []
        if not df_meus_equip.empty:
            lista_equip_opcoes = df_meus_equip["equipamento"].dropna().unique().tolist()
        if not lista_equip_opcoes:
            lista_equip_opcoes = df_meus_chamados["equipamento"].dropna().unique().tolist()
        if not lista_equip_opcoes:
            lista_equip_opcoes = ["TOMOGRAFO - GE - BRIGHTSPEED", "MAMOGRAFO - HOLOGIC - LORAD SELENIA", "RAIO-X FIXO - SHIMADZU - RADSPEED"]

        col_c1, col_c2 = st.columns([2, 1])
        with col_c1:
            equip_cli_sel = st.selectbox("Selecione o Equipamento com Falha: *", lista_equip_opcoes)
        with col_c2:
            urg_cli_sel = st.selectbox("Condição Operacional: *", ["🚨 Equipamento Parado (Emergência)", "⚠️ Operando com Restrições", "📅 Preventiva / Revisão"])

        # Atalhos de sintomas
        st.markdown("<div style='font-size: 13px; color: #94a3b8; margin-bottom: 6px;'>💡 <b>Atalhos rápidos para sintomas comuns</b> (clique para preencher na hora):</div>", unsafe_allow_html=True)
        c_ch1, c_ch2, c_ch3, c_ch4 = st.columns(4)
        if "txt_defeito_portal" not in st.session_state:
            st.session_state["txt_defeito_portal"] = ""

        with c_ch1:
            if st.button("🛏️ Mesa UP/DOWN", key="btn_cli_mesa", use_container_width=True):
                st.session_state["txt_defeito_portal"] = "MESA TRAVANDO O MOVIMENTO DE UP E DOWN."
                st.rerun()
        with c_ch2:
            if st.button("💥 Tubo / Disparo", key="btn_cli_tubo", use_container_width=True):
                st.session_state["txt_defeito_portal"] = "TUBO NÃO DISPARA / ERRO DE ALTA TENSÃO NO GERADOR"
                st.rerun()
        with c_ch3:
            if st.button("🗜️ Compressor Mamo", key="btn_cli_mamo", use_container_width=True):
                st.session_state["txt_defeito_portal"] = "COMPRESSOR TRAVADO / FALHA NO PEDAL DE ELEVAÇÃO"
                st.rerun()
        with c_ch4:
            if st.button("🔬 Artefato Imagem", key="btn_cli_art", use_container_width=True):
                st.session_state["txt_defeito_portal"] = "ARTEFATO DE LINHAS NA IMAGEM / FALHA NO PHANTOM"
                st.rerun()

        defeito_cli_input = st.text_area(
            "Descreva com suas palavras o defeito apresentado ou código de erro: *",
            value=st.session_state["txt_defeito_portal"],
            placeholder="Ex: O gantry emitiu sinal sonoro de alarme e a mesa não se move...",
            height=90,
            key="area_portal_defeito"
        )
        st.session_state["txt_defeito_portal"] = defeito_cli_input

        # Triagem Dinâmica Cirúrgica
        modalidade_detectada = _detectar_modalidade(equip_cli_sel, defeito_cli_input)
        info_triagem = _obter_perguntas_triagem_dinamica(modalidade_detectada, defeito_cli_input, equip_cli_sel)

        st.markdown(f"##### 🎯 {info_triagem['icone']} {info_triagem['categoria']}")
        st.caption(info_triagem["desc"])

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            chk_1_cli = st.radio(info_triagem["p1"]["pergunta"], info_triagem["p1"]["opcoes"], key="radio_p1_cli")
            chk_2_cli = st.radio(info_triagem["p2"]["pergunta"], info_triagem["p2"]["opcoes"], key="radio_p2_cli")
        with col_t2:
            chk_3_cli = st.radio(info_triagem["p3"]["pergunta"], info_triagem["p3"]["opcoes"], key="radio_p3_cli")

        # Regra Todas Não
        def _is_neg(op):
            o = (op or "").upper()
            return "NENHUMA DAS OPÇÕES" in o or o.startswith("⚪ NÃO") or "NÃO / NENHUMA" in o or "NÃO SE APLICA" in o

        todas_nao_portal = _is_neg(chk_1_cli) and _is_neg(chk_2_cli) and _is_neg(chk_3_cli)
        if todas_nao_portal:
            st.info("ℹ️ Você selecionou 'Não / Nenhuma das opções'. Ao abrir o chamado, nossa equipe técnica entrará em contato para mais informações sobre o problema.")

        col_sol1, col_sol2 = st.columns(2)
        with col_sol1:
            solicitante_nome = st.text_input("Seu Nome / Cargo:", placeholder="Ex: Dra. Juliana / Biomédico Carlos")
        with col_sol2:
            solicitante_contato = st.text_input("Seu WhatsApp / Telefone Direto:", placeholder="(85) 99999-9999")

        if st.button("🚀 Confirmar Abertura de Chamado Técnico", type="primary", use_container_width=True):
            if not defeito_cli_input.strip() or not solicitante_nome.strip():
                st.error("⚠️ Por favor, descreva o defeito e informe o seu nome para contato.")
            else:
                novo_registro = {
                    "cliente": cliente_atual.strip().upper(),
                    "cidade": "FORTALEZA",
                    "estado": "CE",
                    "equipamento": equip_cli_sel.strip().upper(),
                    "endereco": "UNIDADE HOSPITALAR",
                    "tipo_servico": "CORRETIVA",
                    "data_agendamento": datetime.datetime.now().strftime("%Y-%m-%d"),
                    "tecnico_responsavel": "EQUIPE EMED PLANTÃO",
                    "tecnico_auxiliar": "NENHUM (INDIVIDUAL)",
                    "telefone_tecnico": "(85) 3254-2929",
                    "responsavel_hospital": solicitante_nome.strip().upper(),
                    "contato_responsavel": solicitante_contato.strip(),
                    "confirmado": "SIM",
                    "pendencias": f"[PORTAL CLIENTE] {defeito_cli_input.strip().upper()}",
                    "status": "ATIVO",
                    "checkin_hora": "",
                    "checkout_hora": "",
                    "tempo_atendimento": "",
                    "checklist_pop": f"{chk_1_cli[:20]} | {chk_2_cli[:20]} | {chk_3_cli[:20]}",
                    "assinatura_cliente": "",
                    "assinatura_tecnico": "",
                    "pre_atendimento": f"[PORTAL DO CLIENTE] {defeito_cli_input.strip()} | Solicitante: {solicitante_nome}",
                    "foto_evidencia": "",
                    "video_evidencia": "",
                    "formulario_anexo": "",
                    "cnpj": cnpj_atual,
                    "cep": "",
                    "email": "",
                    "whatsapp": solicitante_contato,
                    "endereco_fiscal": "",
                    "tipo_contrato": "CONTRATO MANUTENÇÃO",
                    "instrumento_necessario": "MALETA PADRÃO EMED",
                    "etapa_preventiva": "",
                    "orcamento_anexo": "",
                    "condicao_pagamento": "",
                    "valor_os": 0.0,
                    "defeito_relatado": defeito_cli_input.strip().upper(),
                    "condicao_inicial": "PARADO" if "Parado" in urg_cli_sel else "OPERANDO COM FALHA",
                    "problemas_encontrados": "",
                    "causa_raiz": "",
                    "servico_executado": "",
                    "parametros_medidos": "",
                    "observacoes_gerais": f"Aberto pelo Portal do Cliente em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}.",
                    "condicao_final": "EM ATENDIMENTO",
                    "foto_depois": "",
                    "assinatura_cliente_img": "",
                    "peca_baixada_ref": "",
                }
                df_atualizado = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
                if salvar_dados_seguro(df_atualizado, ctx.db_name, ctx.caminho_excel):
                    st.cache_data.clear()
                    novo_idx = df_atualizado.index[-1]
                    os_gerada = obter_id_os(novo_idx, pd.Series(novo_registro))
                    if todas_nao_portal:
                        st.success(f"✅ **O chamado foi aberto com sucesso e a equipe técnica entrará em contato para mais informações sobre o problema.** (OS #{os_gerada})")
                    else:
                        st.success(f"🎉 **Chamado Aberto com Sucesso! Ordem de Serviço Nº #{os_gerada} emitida.**")
                    st.balloons()

    # =========================================================================
    # TAB 3: MEU PARQUE DE EQUIPAMENTOS
    # =========================================================================
    with tab_parque:
        st.markdown("#### 🏥 Equipamentos Cadastrados sob Contrato")
        if df_meus_equip.empty:
            st.info("Nenhum equipamento formalmente listado na base de contratos desta unidade.")
        else:
            for _, r_eq in df_meus_equip.iterrows():
                eq_n = r_eq.get("equipamento", "Equipamento")
                mod_n = r_eq.get("modalidade", "N/D")
                mod_m = r_eq.get("modelo", "Padrão")
                fab_n = r_eq.get("fabricante", "EMED")
                num_s = r_eq.get("numero_serie", "N/D")
                setor = r_eq.get("setor", "Setor Geral / Radiologia")
                calib = r_eq.get("calibracao_vencimento", "EM DIA")

                st.markdown(f"""
                    <div style="background: #1e293b; border-left: 5px solid #38bdf8; padding: 14px 18px; border-radius: 8px; margin-bottom: 12px;">
                        <h4 style="color: #38bdf8; margin: 0 0 4px 0;">{eq_n}</h4>
                        <div style="color: #cbd5e1; font-size: 13px;">
                            <b>Fabricante:</b> {fab_n} | <b>Modelo:</b> {mod_m} | <b>Série:</b> {num_s}
                        </div>
                        <div style="color: #94a3b8; font-size: 12.5px; margin-top: 3px;">
                            <b>Setor:</b> {setor} | <b>Status de Calibração:</b> <span style="color: #10b981; font-weight: bold;">{calib}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    # =========================================================================
    # TAB 4: FATURAS & PAGAMENTO PIX
    # =========================================================================
    with tab_pix:
        st.markdown("#### 💳 Faturas e Quitação via PIX Oficial")
        with sqlite3.connect(db_name) as conn:
            df_nf_cli = pd.read_sql_query(
                "SELECT * FROM notas_fiscais WHERE UPPER(TRIM(cliente)) = ?",
                conn,
                params=(cliente_atual.strip().upper(),)
            )
        if df_nf_cli.empty:
            st.info("Nenhuma fatura em aberto encontrada para esta instituição.")
        else:
            for _, r_nf in df_nf_cli.iterrows():
                os_nf = r_nf.get("os_id", "N/D")
                val_nf = float(r_nf.get("valor_liquido", 0.0) or 1500.0)
                st_nf = limpar_texto(r_nf.get("status_fiscal"), "AGUARDANDO PAGAMENTO").upper()
                cor_nf = "#10b981" if "PAGO" in st_nf else "#f59e0b"

                col_nf_txt, col_nf_qr = st.columns([2, 1])
                with col_nf_txt:
                    st.markdown(f"""
                        <div style="background: #1e293b; border-left: 6px solid {cor_nf}; padding: 14px; border-radius: 8px;">
                            <h4 style="color: #f8fafc; margin:0;">Fatura OS #{os_nf} — R$ {val_nf:,.2f}</h4>
                            <div style="color: {cor_nf}; font-weight: bold; margin: 4px 0;">Status: {st_nf}</div>
                            <div style="color: #94a3b8; font-size: 12px;">Chave PIX: financeiro@emed.med.br (EMED HOSPITALAR)</div>
                        </div>
                    """, unsafe_allow_html=True)

                with col_nf_qr:
                    payload_nf = gerar_payload_pix("financeiro@emed.med.br", "EMED HOSPITALAR", "FORTALEZA", val_nf, f"OS{os_nf}")
                    img_qr_nf = gerar_qr_code_pix_base64(payload_nf)
                    st.image(img_qr_nf, width=130)

    # =========================================================================
    # TAB 5: AVALIAR ATENDIMENTO (GOOGLE REVIEW)
    # =========================================================================
    with tab_feedback:
        st.markdown("#### ⭐ Avaliação de Atendimento & Google Review")
        st.markdown("Sua opinião é fundamental para garantir a excelência técnica contínua dos nossos serviços.")
        
        col_fb1, col_fb2 = st.columns([1.5, 1.5])
        with col_fb1:
            nota_cli = st.select_slider("Como você avalia nosso suporte geral?", options=[1, 2, 3, 4, 5], value=5)
            coment_cli = st.text_area("Deixe seu comentário ou sugestão:", placeholder="Ex: Atendimento excelente e rápido...", height=80)
            if st.button("Enviar Avaliação", type="primary"):
                ok, msg = registrar_pesquisa(
                    db_name=db_name,
                    os_id="PORTAL_CLIENTE",
                    cliente=cliente_atual,
                    cnpj=cnpj_atual,
                    tecnico="PLANTÃO EMED",
                    nota=nota_cli,
                    tags=["Portal do Cliente"],
                    comentario=coment_cli,
                    clicou_google=1 if nota_cli >= 4 else 0
                )
                if ok:
                    st.success("Obrigado pelo seu feedback!")
                    st.balloons()
        with col_fb2:
            url_g_client = obter_url_google_review(ctx.db_name)
            if nota_cli >= 4:
                st.markdown(f"""
                    <div style="background: #172554; border: 1.5px solid #3b82f6; border-radius: 10px; padding: 18px; text-align: center;">
                        <h4 style="color: #93c5fd; margin: 0 0 6px 0;">🌟 Ajude-nos no Google!</h4>
                        <p style="color: #cbd5e1; font-size: 13px;">Compartilhe sua avaliação pública na página da EMED no Google Meu Negócio em apenas 1 clique:</p>
                        <a href="{url_g_client}" target="_blank" style="display: inline-block; background: #fbbf24; color: #000; font-weight: 800; padding: 10px 18px; border-radius: 6px; text-decoration: none;">
                            ⭐ Avaliar no Google Meu Negócio
                        </a>
                    </div>
                """, unsafe_allow_html=True)
