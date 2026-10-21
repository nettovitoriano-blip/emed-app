import datetime
import urllib.parse
import pandas as pd
import streamlit as st
from emed_core import (
    limpar_texto,
    get_db_connection,
    calcular_status_calibracao,
    obter_resumo_alarmes_calibracao,
)
from emed_services import (
    AppContext,
    carregar_estoque,
    atualizar_calibracao_instrumento,
    atualizar_calibracao_equipamento_cliente,
)


def render_alarmes_calibracao(ctx: AppContext):
    st.markdown("### ⏰ Painel de Alarmes: Calibrações & Créditos Anuais")
    st.caption(
        "Monitoramento contínuo para garantir conformidade com normas ANVISA (RDC 611 / RDC 330) e física médica, "
        "além de prevenir paralisações de instrumentos e dosímetros por expiração de calibração ou falta de créditos anuais."
    )

    db_path = ctx.db_name
    resumo = obter_resumo_alarmes_calibracao(db_path)

    # 1. Totalizadores Globais (KPIs)
    total_vencidos = resumo["instrumentos_vencidos"] + resumo["equipamentos_vencidos"]
    total_a_vencer = resumo["instrumentos_a_vencer"] + resumo["equipamentos_a_vencer"]
    total_em_dia = resumo["instrumentos_em_dia"] + resumo["equipamentos_em_dia"]

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("🔴 Vencidos / Ação Urgente", f"{total_vencidos} itens", delta="- Crítico" if total_vencidos > 0 else "0", delta_color="inverse")
    with col_m2:
        st.metric("🟡 Vencem em até 30 Dias", f"{total_a_vencer} itens", delta="Atenção" if total_a_vencer > 0 else "0", delta_color="off")
    with col_m3:
        st.metric("🟢 Em Dia / Regularizados", f"{total_em_dia} itens")
    with col_m4:
        st.metric("🔔 Total de Alarmes Ativos", f"{resumo['total_alarmes_urgentes']} alertas")

    # Banner de Alerta Urgente
    if resumo["total_alarmes_urgentes"] > 0:
        st.markdown(f"""
            <div style="background: rgba(239, 68, 68, 0.15); border-left: 6px solid #ef4444; padding: 14px 18px; border-radius: 8px; margin: 15px 0 20px 0;">
                <h4 style="margin: 0 0 6px 0; color: #f87171;">🚨 ALERTA DE COMPLIANCE & CALIBRAÇÃO ATIVO ({resumo['total_alarmes_urgentes']} ocorrências)</h4>
                <p style="margin: 0; color: #cbd5e1; font-size: 13.5px;">
                    Existem <strong>{total_vencidos} itens vencidos</strong> e <strong>{total_a_vencer} itens vencendo nos próximos 30 dias</strong>. 
                    Providencie a renovação em laboratório credenciado ou a recarga de créditos para não perder os prazos legais e operacionais!
                </p>
            </div>
        """, unsafe_allow_html=True)

    aba1, aba2, aba3 = st.tabs([
        "🔬 Instrumentos & Ferramentas da EMED",
        "🏥 Equipamentos dos Clientes (ANVISA / RDC 611)",
        "📲 Disparar Alertas no WhatsApp"
    ])

    # -------------------------------------------------------------
    # ABA 1: INSTRUMENTOS & FERRAMENTAS DA EMED
    # -------------------------------------------------------------
    with aba1:
        st.markdown("#### 🔬 Instrumentos com Calibração Rastreável ou Créditos Anuais")
        st.caption("Acompanhe multímetros 1000V, osciloscópios, dong's de ativação/licença e instrumentos de calibração radiológica.")

        df_estoque = carregar_estoque(db_path)
        if not df_estoque.empty and "requer_calibracao" in df_estoque.columns:
            df_inst = df_estoque[(df_estoque["requer_calibracao"] == 1) | (df_estoque["requer_creditos"] == 1)].copy()
        else:
            df_inst = pd.DataFrame()

        if df_inst.empty:
            st.info("Nenhum instrumento configurado para calibração anual no momento.")
        else:
            # Processa status de cada instrumento
            lista_processada = []
            for _, r_inst in df_inst.iterrows():
                val_cal = str(r_inst.get("data_validade_calibracao", "")).strip()
                st_c = calcular_status_calibracao(val_cal)
                tipo_req = []
                if r_inst.get("requer_calibracao") == 1:
                    tipo_req.append("CALIBRAÇÃO ANUAL")
                if r_inst.get("requer_creditos") == 1:
                    tipo_req.append("CRÉDITOS ANUAIS")
                tipo_str = " & ".join(tipo_req) if tipo_req else "MONITORADO"

                lista_processada.append({
                    "codigo": r_inst["codigo"],
                    "nome_peca": r_inst["nome_peca"],
                    "tipo_alarme": tipo_str,
                    "ultima_calibracao": r_inst.get("data_ultima_calibracao", "N/D"),
                    "validade_calibracao": val_cal if val_cal else "Não informada",
                    "status": st_c["status"],
                    "dias_restantes": st_c["dias_restantes"],
                    "badge_txt": st_c["badge_txt"],
                    "badge_cor": st_c["badge_cor"],
                    "badge_bg": st_c["badge_bg"],
                    "certificado": r_inst.get("certificado_calibracao", "N/D"),
                    "saldo_creditos": r_inst.get("saldo_creditos", "")
                })

            df_proc_inst = pd.DataFrame(lista_processada).sort_values("dias_restantes")

            # Filtros Rápidos
            c_f1, c_f2 = st.columns([2, 2])
            with c_f1:
                filtro_st_inst = st.selectbox(
                    "Filtrar por Situação do Instrumento:",
                    ["TODOS OS INSTRUMENTOS", "🔴 VENCIDOS", "🟡 VENCENDO EM ATÉ 30 DIAS", "🟢 EM DIA"]
                )
            with c_f2:
                busca_inst = st.text_input("🔍 Buscar Instrumento:", placeholder="Ex: Multímetro, Osciloscópio, Dong's, Medidor...")

            df_filtrado_inst = df_proc_inst.copy()
            if "VENCIDOS" in filtro_st_inst:
                df_filtrado_inst = df_filtrado_inst[df_filtrado_inst["status"] == "VENCIDO"]
            elif "30 DIAS" in filtro_st_inst:
                df_filtrado_inst = df_filtrado_inst[df_filtrado_inst["status"] == "A VENCER"]
            elif "EM DIA" in filtro_st_inst:
                df_filtrado_inst = df_filtrado_inst[df_filtrado_inst["status"] == "EM DIA"]

            if busca_inst.strip():
                df_filtrado_inst = df_filtrado_inst[
                    df_filtrado_inst["nome_peca"].str.contains(busca_inst, case=False, na=False) |
                    df_filtrado_inst["codigo"].str.contains(busca_inst, case=False, na=False)
                ]

            for _, r_card in df_filtrado_inst.iterrows():
                cred_txt = f"<span style='color: #a78bfa; font-weight: bold;'>💳 Créditos: {r_card['saldo_creditos']}</span>" if r_card["saldo_creditos"] else ""
                st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; border: 1px solid #334155; border-left: 6px solid {r_card['badge_cor']};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 13px; font-weight: bold; color: #64dfdf;">[{r_card['codigo']}] {r_card['tipo_alarme']}</span>
                            <span style="background: {r_card['badge_bg']}; color: {r_card['badge_cor']}; font-size: 12px; font-weight: 800; padding: 4px 8px; border-radius: 4px;">{r_card['badge_txt']}</span>
                        </div>
                        <h4 style="margin: 6px 0 6px 0; color: #f8fafc; font-size: 15px;">{r_card['nome_peca']}</h4>
                        <div style="font-size: 13px; color: #94a3b8; line-height: 1.5;">
                            📅 <strong>Última Calibração:</strong> {r_card['ultima_calibracao']} &nbsp;|&nbsp; 
                            ⏳ <strong>Validade:</strong> <span style="color: #f1f5f9; font-weight: bold;">{r_card['validade_calibracao']}</span> &nbsp;|&nbsp; 
                            📜 <strong>Certificado/Laudo:</strong> {r_card['certificado']}
                            {f"<br>{cred_txt}" if cred_txt else ""}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            # Formulário para Renovar Calibração ou Inserir Créditos
            with st.expander("📝 Renovar Calibração / Inserir Créditos em um Instrumento", expanded=False):
                with st.form("form_renovar_calibracao_inst"):
                    opcoes_inst_form = [f"[{r['codigo']}] {r['nome_peca']}" for _, r in df_inst.iterrows()]
                    inst_escolhido = st.selectbox("Selecione o Instrumento:", opcoes_inst_form)

                    c_rc1, c_rc2 = st.columns(2)
                    with c_rc1:
                        hoje_fmt = datetime.date.today().strftime("%d/%m/%Y")
                        ano_que_vem_fmt = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%d/%m/%Y")
                        nova_d_ult = st.text_input("Data da Nova Calibração / Recarga (DD/MM/AAAA):", value=hoje_fmt)
                        novo_cert = st.text_input("Nº do Novo Certificado / Lote:", placeholder="EX: CERT-LNMRI-2027-01")
                    with c_rc2:
                        nova_d_val = st.text_input("Nova Data de Validade (DD/MM/AAAA):", value=ano_que_vem_fmt)
                        novo_saldo_cred = st.text_input("Saldo de Créditos Anuais (se aplicável):", placeholder="EX: 100 Medições / Licença Anual Ativa")

                    if st.form_submit_button("💾 Salvar Renovação no Instrumento", type="primary"):
                        cod_alvo = inst_escolhido.split("]")[0].replace("[", "").strip()
                        ok_att, msg_att = atualizar_calibracao_instrumento(
                            db_path, cod_alvo, nova_d_ult, nova_d_val, novo_cert, novo_saldo_cred
                        )
                        if ok_att:
                            st.cache_data.clear()
                            st.success(msg_att)
                            st.rerun()
                        else:
                            st.error(msg_att)

    # -------------------------------------------------------------
    # ABA 2: EQUIPAMENTOS DOS CLIENTES (RDC 611 / ANVISA)
    # -------------------------------------------------------------
    with aba2:
        st.markdown("#### 🏥 Equipamentos dos Clientes com Calibração & Laudo Anual (RDC 611 / 330)")
        st.caption("Controle de conformidade anual para Raios-X, Mamógrafos, Tomógrafos, Densitômetros e Arcos Cirúrgicos.")

        df_os_all = ctx.df
        df_eq_calib = df_os_all[df_os_all["data_validade_calibracao"].fillna("").astype(str).str.strip() != ""].copy()

        if df_eq_calib.empty:
            st.info("Nenhum equipamento de cliente cadastrado com data de calibração anual.")
        else:
            lista_proc_eq = []
            for idx_e, r_eq in df_eq_calib.iterrows():
                val_eq = str(r_eq.get("data_validade_calibracao", "")).strip()
                st_eq_c = calcular_status_calibracao(val_eq)
                cli_nome = limpar_texto(r_eq.get("cliente"), "N/D")
                eq_nome = limpar_texto(r_eq.get("equipamento"), "N/D")
                cidade_nome = limpar_texto(r_eq.get("cidade"), "FORTALEZA")
                cert_eq = limpar_texto(r_eq.get("certificado_calibracao"), "N/D")

                lista_proc_eq.append({
                    "id": r_eq.get("id", idx_e),
                    "cliente": cli_nome,
                    "equipamento": eq_nome,
                    "cidade": cidade_nome,
                    "ultima_calibracao": r_eq.get("data_ultima_calibracao", "N/D"),
                    "validade_calibracao": val_eq,
                    "status": st_eq_c["status"],
                    "dias_restantes": st_eq_c["dias_restantes"],
                    "badge_txt": st_eq_c["badge_txt"],
                    "badge_cor": st_eq_c["badge_cor"],
                    "badge_bg": st_eq_c["badge_bg"],
                    "certificado": cert_eq
                })

            df_proc_eq = pd.DataFrame(lista_proc_eq).sort_values("dias_restantes")

            # Filtros
            c_fe1, c_fe2 = st.columns([2, 2])
            with c_fe1:
                filtro_st_eq = st.selectbox(
                    "Filtrar por Situação do Equipamento:",
                    ["TODOS OS EQUIPAMENTOS", "🔴 VENCIDOS (RISCO DE INTERDIÇÃO)", "🟡 VENCENDO EM ATÉ 30 DIAS", "🟢 EM DIA"]
                )
            with c_fe2:
                busca_eq = st.text_input("🔍 Buscar Cliente ou Equipamento:", placeholder="Ex: Clemir, Uniclinic, Mamógrafo, Tomógrafo...")

            df_filtrado_eq = df_proc_eq.copy()
            if "VENCIDOS" in filtro_st_eq:
                df_filtrado_eq = df_filtrado_eq[df_filtrado_eq["status"] == "VENCIDO"]
            elif "30 DIAS" in filtro_st_eq:
                df_filtrado_eq = df_filtrado_eq[df_filtrado_eq["status"] == "A VENCER"]
            elif "EM DIA" in filtro_st_eq:
                df_filtrado_eq = df_filtrado_eq[df_filtrado_eq["status"] == "EM DIA"]

            if busca_eq.strip():
                df_filtrado_eq = df_filtrado_eq[
                    df_filtrado_eq["cliente"].str.contains(busca_eq, case=False, na=False) |
                    df_filtrado_eq["equipamento"].str.contains(busca_eq, case=False, na=False)
                ]

            for _, r_eq_card in df_filtrado_eq.iterrows():
                st.markdown(f"""
                    <div style="background: #1e293b; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px; border: 1px solid #334155; border-left: 6px solid {r_eq_card['badge_cor']};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 13px; font-weight: bold; color: #f59e0b;">🏥 {r_eq_card['cliente']} ({r_eq_card['cidade']})</span>
                            <span style="background: {r_eq_card['badge_bg']}; color: {r_eq_card['badge_cor']}; font-size: 12px; font-weight: 800; padding: 4px 8px; border-radius: 4px;">{r_eq_card['badge_txt']}</span>
                        </div>
                        <h4 style="margin: 6px 0 6px 0; color: #f8fafc; font-size: 15px;">⚙️ {r_eq_card['equipamento']}</h4>
                        <div style="font-size: 13px; color: #94a3b8; line-height: 1.5;">
                            📅 <strong>Última Calibração / Laudo:</strong> {r_eq_card['ultima_calibracao']} &nbsp;|&nbsp; 
                            ⏳ <strong>Validade do Laudo:</strong> <span style="color: #f1f5f9; font-weight: bold;">{r_eq_card['validade_calibracao']}</span> &nbsp;|&nbsp; 
                            📜 <strong>Nº do Laudo / Certificado:</strong> {r_eq_card['certificado']}
                        </div>
                    </div>
                """, unsafe_allow_html=True)

            # Formulário para Atualizar Laudo de Equipamento
            with st.expander("📝 Registrar Novo Laudo de Calibração / Controle de Qualidade Anual", expanded=False):
                with st.form("form_novo_laudo_cliente"):
                    opcoes_eq_form = [f"#{r['id']} | {r['cliente']} — {r['equipamento']}" for _, r in df_proc_eq.iterrows()]
                    eq_escolhido = st.selectbox("Selecione o Equipamento do Cliente:", opcoes_eq_form)

                    c_le1, c_le2 = st.columns(2)
                    with c_le1:
                        nova_d_ult_eq = st.text_input("Data do Novo Laudo (DD/MM/AAAA):", value=datetime.date.today().strftime("%d/%m/%Y"))
                        novo_cert_eq = st.text_input("Nº do Laudo / Certificado ANVISA:", placeholder="EX: LAUDO-ANUAL-2027-01")
                    with c_le2:
                        nova_d_val_eq = st.text_input("Nova Data de Validade Anual (DD/MM/AAAA):", value=(datetime.date.today() + datetime.timedelta(days=365)).strftime("%d/%m/%Y"))

                    if st.form_submit_button("💾 Salvar Novo Laudo do Equipamento", type="primary"):
                        id_eq_alvo = int(eq_escolhido.split("|")[0].replace("#", "").strip())
                        ok_att_eq, msg_att_eq = atualizar_calibracao_equipamento_cliente(
                            db_path, id_eq_alvo, nova_d_ult_eq, nova_d_val_eq, novo_cert_eq
                        )
                        if ok_att_eq:
                            st.cache_data.clear()
                            st.success(msg_att_eq)
                            st.rerun()
                        else:
                            st.error(msg_att_eq)

    # -------------------------------------------------------------
    # ABA 3: DISPARAR ALERTAS NO WHATSAPP
    # -------------------------------------------------------------
    with aba3:
        st.markdown("#### 📲 Disparo de Alertas & Lembretes no WhatsApp")
        st.caption("Envie o relatório instantâneo dos itens que precisam de atenção este mês diretamente no grupo de manutenção ou para o gestor.")

        itens_urgentes = resumo.get("itens_urgentes", [])
        if not itens_urgentes:
            st.success("🎉 Nenhuma calibração ou crédito com vencimento crítico no momento! Tudo regularizado.")
        else:
            msg_wpp_linhas = [
                "🚨 *ALERTA DE CALIBRAÇÕES & CRÉDITOS ANUAIS - EMED*",
                f"📅 *Data do Relatório:* {datetime.date.today().strftime('%d/%m/%Y')}",
                f"⚠️ *Total de Ocorrências:* {len(itens_urgentes)}\n",
                "*ITENS QUE NECESSITAM DE RENOVAÇÃO / CRÉDITOS:*"
            ]

            for idx_w, it_w in enumerate(itens_urgentes, 1):
                msg_wpp_linhas.append(
                    f"*{idx_w}. [{it_w['origem']}]* {it_w['nome']}\n"
                    f"   📌 Tipo: {it_w['tipo']}\n"
                    f"   ⏳ Validade: {it_w['validade']} ({it_w['badge_txt']})\n"
                )

            msg_wpp_linhas.append("🔔 *Ação recomendada:* Agendar envio para calibração ou recarga de créditos para não interromper a operação.")
            msg_final_wpp = "\n".join(msg_wpp_linhas)

            st.text_area("📋 Pré-visualização da Mensagem de Alerta:", value=msg_final_wpp, height=220)

            link_wpp_gestor = f"https://wa.me/5585988888888?text={urllib.parse.quote(msg_final_wpp)}"
            st.markdown(f"""
                <a href="{link_wpp_gestor}" target="_blank" style="background:#25d366; color:white; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:8px;">
                    📲 Enviar Alertas de Calibração para o Gestor (WhatsApp)
                </a>
            """, unsafe_allow_html=True)
