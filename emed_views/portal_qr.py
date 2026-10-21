import datetime
import os
import urllib.parse
import pandas as pd
import streamlit as st
from emed_core import limpar_texto, obter_id_os
from emed_services import AppContext, salvar_dados_seguro


def verificar_e_renderizar_portal_qr(ctx: AppContext):
    query_params = st.query_params
    eq_qrcode_url = query_params.get("equipamento_qr", None)
    cli_qrcode_url = query_params.get("cliente_qr", None)

    if "simulando_qr_eq" not in st.session_state:
        st.session_state.simulando_qr_eq = None
    if "simulando_qr_cli" not in st.session_state:
        st.session_state.simulando_qr_cli = None

    eq_portal_ativo = eq_qrcode_url or st.session_state.simulando_qr_eq
    cli_portal_ativo = cli_qrcode_url or st.session_state.simulando_qr_cli

    if not eq_portal_ativo:
        return

    df = ctx.df
    col_p1, col_p2, col_p3 = st.columns([1.5, 3, 1.5])
    with col_p2:
        caminho_logo = os.path.join(ctx.base_dir, "emed1.jpg")
        if os.path.exists(caminho_logo):
            st.image(caminho_logo, use_container_width=True)

    if st.session_state.simulando_qr_eq:
        if st.button("⬅️ Voltar ao Painel Principal EMED", type="primary"):
            st.session_state.simulando_qr_eq = None
            st.session_state.simulando_qr_cli = None
            st.rerun()

    nome_unid_qr = limpar_texto(cli_portal_ativo, 'UNIDADE CREDENCIADA')
    st.markdown(f"""
        <div style="background: #1c2541; border: 2px solid #64dfdf; padding: 22px; border-radius: 12px; margin-bottom: 20px;">
            <h2 style="color: #64dfdf; margin-top:0;">🏥 PORTAL DE ATENDIMENTO POR QR CODE - EMED</h2>
            <p style="font-size: 16px; margin: 4px 0;"><strong>Unidade / Hospital:</strong> {nome_unid_qr}</p>
            <p style="font-size: 16px; margin: 4px 0;"><strong>Equipamento Identificado:</strong> {eq_portal_ativo}</p>
        </div>
    """, unsafe_allow_html=True)

    aba_qr1, aba_qr2 = st.tabs([
        "📜 Histórico de Manutenções & OS do Equipamento",
        "🎫 Solicitar Abertura de Chamado para este Equipamento"
    ])

    with aba_qr1:
        st.markdown("#### 📜 Intervenções Realizadas e Ordens de Serviço deste Equipamento")
        filtro_hist_qr = df[df['equipamento'].astype(str).str.upper() == str(eq_portal_ativo).upper()]
        if cli_portal_ativo:
            filtro_cli_temp = filtro_hist_qr[filtro_hist_qr['cliente'].astype(str).str.upper() == str(cli_portal_ativo).upper()]
            if not filtro_cli_temp.empty:
                filtro_hist_qr = filtro_cli_temp

        if filtro_hist_qr.empty:
            st.info("Nenhum histórico de intervenção registado para este equipamento até ao momento.")
        else:
            for idx_hq, r_hq in filtro_hist_qr.iterrows():
                id_os_hq = obter_id_os(idx_hq, r_hq)
                st_hq = limpar_texto(r_hq.get('status'), 'ATIVO').upper()
                cor_hq = "#10b981" if st_hq == "CONCLUÍDO" else "#f59e0b"
                etapa_hq = limpar_texto(r_hq.get('etapa_preventiva'), '')
                txt_etapa = f" | <strong>Etapa:</strong> {etapa_hq}" if etapa_hq else ""
                srv_hq = limpar_texto(r_hq.get('tipo_servico'), 'MANUTENÇÃO')
                dt_hq = limpar_texto(r_hq.get('data_agendamento'), 'N/D')
                tec_hq = limpar_texto(r_hq.get('tecnico_responsavel'), 'A DEFINIR')
                pend_hq = limpar_texto(r_hq.get('pendencias'), 'Sem observações')
                resp_hq = limpar_texto(r_hq.get('assinatura_cliente'), r_hq.get('responsavel_hospital', 'N/D'))

                st.markdown(f"""
                    <div style="background: #1c2541; border-left: 6px solid {cor_hq}; padding: 15px; border-radius: 8px; margin-bottom: 12px;">
                        <h4 style="margin:0 0 6px 0; color:#64dfdf;">OS #{id_os_hq} — {srv_hq} [{st_hq}]</h4>
                        <p style="margin:3px 0;"><strong>Data:</strong> {dt_hq} | <strong>Técnico:</strong> {tec_hq}{txt_etapa}</p>
                        <p style="margin:3px 0;"><strong>Relatório / Detalhes:</strong> {pend_hq}</p>
                        <p style="margin:3px 0;"><strong>Responsável Local:</strong> {resp_hq}</p>
                    </div>
                """, unsafe_allow_html=True)

    with aba_qr2:
        st.markdown("#### 🎫 Abrir Novo Chamado Técnico Direto para este Equipamento")
        with st.form("form_abertura_qr_cliente"):
            q_hosp = st.text_input("Hospital / Unidade *", value=limpar_texto(cli_portal_ativo, ''))
            q_resp = st.text_input("Seu Nome e Setor / Cargo *", placeholder="EX: ENF. MARIA / DR. CARLOS - RADIOLOGIA")
            q_tel = st.text_input("Telemóvel / WhatsApp para Contacto *", placeholder="5585999999999")
            q_urg = st.selectbox("Nível de Urgência", ["NORMAL", "URGENTE / EQUIPAMENTO PARADO", "CRÍTICO (EMERGÊNCIA)"])
            q_erro = st.text_input("Código de Erro no Painel (Se houver)", placeholder="EX: ERR-402")
            q_relato = st.text_area("Descreva o Problema / Solicitação *", placeholder="Explique o que está a acontecer com o equipamento...")

            if st.form_submit_button("🚀 Enviar Solicitação de Chamado para a EMED", type="primary"):
                if not q_hosp.strip() or not q_resp.strip() or not q_relato.strip():
                    st.error("⚠️ Preencha o Hospital, o seu Nome e a Descrição da falha!")
                else:
                    base_match = df[df['cliente'].astype(str).str.upper() == q_hosp.strip().upper()]
                    cid_qr = limpar_texto(base_match.iloc[0].get('cidade'), 'FORTALEZA') if not base_match.empty else 'FORTALEZA'
                    uf_qr = limpar_texto(base_match.iloc[0].get('estado'), 'CE') if not base_match.empty else 'CE'
                    end_qr = limpar_texto(base_match.iloc[0].get('endereco'), '') if not base_match.empty else ''
                    cond_ini_qr = "PARADO / INOPERANTE" if "PARADO" in q_urg or "CRÍTICO" in q_urg else "OPERANDO COM RESTRIÇÃO"

                    nova_os_qr = {
                        'cliente': q_hosp.strip().upper(),
                        'cidade': cid_qr.upper(),
                        'estado': uf_qr.upper(),
                        'equipamento': str(eq_portal_ativo).strip().upper(),
                        'endereco': end_qr.upper(),
                        'tipo_servico': 'CORRETIVA (ABERTA VIA QR CODE)',
                        'data_agendamento': datetime.date.today().strftime('%Y-%m-%d'),
                        'tecnico_responsavel': 'A DEFINIR',
                        'telefone_tecnico': '',
                        'responsavel_hospital': q_resp.strip().upper(),
                        'contato_responsavel': q_tel.strip(),
                        'confirmado': 'SIM',
                        'pendencias': f"[QR CODE - {q_urg}] {q_relato.strip().upper()}",
                        'defeito_relatado': q_relato.strip().upper(),
                        'condicao_inicial': cond_ini_qr,
                        'status': 'ATIVO',
                        'pre_atendimento': f"[ERRO: {q_erro.strip().upper() if q_erro else 'N/D'}]",
                        'tipo_contrato': 'CONTRATO'
                    }
                    # Trava anti-duplicação: checa se já existe chamado ativo idêntico para o cliente e equipamento
                    chamado_duplicado = df[
                        (df['cliente'].astype(str).str.strip().str.upper() == q_hosp.strip().upper()) &
                        (df['equipamento'].astype(str).str.strip().str.upper() == str(eq_portal_ativo).strip().upper()) &
                        (df['status'].astype(str).str.upper().isin(['ATIVO', 'EM ATENDIMENTO'])) &
                        (df['defeito_relatado'].astype(str).str.strip().str.upper() == q_relato.strip().upper())
                    ]
                    if not chamado_duplicado.empty:
                        idx_exist = chamado_duplicado.index[-1]
                        id_exist = obter_id_os(idx_exist, chamado_duplicado.iloc[-1])
                        st.warning(f"⚠️ **Atenção:** Já existe um chamado ativo em andamento para este equipamento (**OS #{id_exist}**). Abertura duplicada bloqueada.")
                    else:
                        df = pd.concat([df, pd.DataFrame([nova_os_qr])], ignore_index=True)
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success("✅ Chamado registado com sucesso na central da EMED!")
                            msg_wpp_qr = (
                                f"🚨 *NOVO CHAMADO VIA QR CODE - EMED*\n"
                                f"🏥 *Hospital:* {q_hosp.upper()}\n"
                                f"⚙️ *Equipamento:* {eq_portal_ativo}\n"
                                f"⚠️ *Urgência:* {q_urg}\n"
                                f"👤 *Solicitante:* {q_resp.upper()} ({q_tel})\n"
                                f"📝 *Relato:* {q_relato.upper()}"
                            )
                            link_wpp_central = f"https://wa.me/5585988888888?text={urllib.parse.quote(msg_wpp_qr)}"
                            st.markdown(f"""
                                <a href="{link_wpp_central}" target="_blank" style="background:#25d366; color:white; padding:10px 20px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block;">
                                    📲 Notificar Plantão EMED no WhatsApp
                                </a>
                            """, unsafe_allow_html=True)
    st.stop()
