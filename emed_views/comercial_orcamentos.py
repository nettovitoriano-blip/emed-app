import urllib.parse
import streamlit as st
from emed_core import limpar_texto, obter_id_os, calcular_dias_aguardando_orcamento
from emed_services import AppContext, salvar_dados_seguro


def render_followup_orcamentos(ctx: AppContext):
    df = ctx.df
    hoje = ctx.hoje

    st.markdown("### ⏳ Follow-up de Orçamentos Pendentes (> 15 Dias)")
    st.info("Controlo automático de orçamentos emitidos que aguardam aprovação do hospital há mais de 15 dias.")

    df_orc = df.copy()
    df_orc['status_clean'] = df_orc['status'].fillna('ATIVO').astype(str).str.upper()
    df_orc['pendencias_clean'] = df_orc['pendencias'].fillna('').astype(str).str.upper()

    df_orcamentos_ativos = df_orc[
        (df_orc['status_clean'] == 'ATIVO') &
        (df_orc['pendencias_clean'].str.contains('ORÇAMENTO|ORCAMENTO|APROVA', na=False)) &
        (~df_orc['pendencias_clean'].str.contains('ORÇAMENTO APROVADO|ORCAMENTO APROVADO', na=False))
    ]

    if df_orcamentos_ativos.empty:
        st.success("🎉 Nenhum orçamento pendente de aprovação no momento.")
    else:
        for idx_o, row_o in df_orcamentos_ativos.iterrows():
            id_os_orc = obter_id_os(idx_o, row_o)
            cliente_o = limpar_texto(row_o.get('cliente'), 'N/D')
            cidade_o = limpar_texto(row_o.get('cidade'), 'N/D')
            eq_o = limpar_texto(row_o.get('equipamento'), 'N/D')
            desc_o = limpar_texto(row_o.get('pendencias'), 'N/D')
            resp_h_o = limpar_texto(row_o.get('responsavel_hospital'), 'N/D')
            tel_o = limpar_texto(row_o.get('contato_responsavel'), '')
            if tel_o.endswith('.0'):
                tel_o = tel_o[:-2]
            tel_limpo_o = ''.join(filter(str.isdigit, tel_o))
            tel_exib_o = tel_o if tel_o else 'Sem telefone'
            dias_orc = calcular_dias_aguardando_orcamento(row_o.get('data_agendamento'), hoje)
            cor_borda_orc = "#ef4444" if dias_orc >= 15 else "#f59e0b"
            badge_dias_orc = (
                f"<span style='background:#ef4444; color:#ffffff; padding:2px 8px; border-radius:12px; font-size:12px;'>🔴 {dias_orc} dias aguardando (&gt; 15 dias)</span>"
                if dias_orc >= 15 else
                f"<span style='background:#f59e0b; color:#0b132b; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:bold;'>🟡 {dias_orc} dias aguardando</span>"
            )

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid {cor_borda_orc}; padding: 15px; border-radius: 8px; margin-bottom: 12px;">
                    <h4 style="margin: 0 0 5px 0; color: #64dfdf;">🏥 OS #{id_os_orc} | {cliente_o} ({cidade_o}) — ⚙️ {eq_o} {badge_dias_orc}</h4>
                    <p style="margin: 4px 0;"><strong>Detalhes do Orçamento:</strong> {desc_o}</p>
                    <p style="margin: 4px 0;"><strong>Contacto do Hospital:</strong> {resp_h_o} ({tel_exib_o})</p>
                </div>
            """, unsafe_allow_html=True)

            msg_followup = (
                f"Olá! Entramos em contacto da *EMED Eletromedicina* para sabermos se há novidades "
                f"quanto à aprovação do orçamento referente ao equipamento *{eq_o}* em *{cliente_o}*. "
                f"Ficamos à disposição para esclarecer qualquer dúvida!"
            )
            encoded_fup = urllib.parse.quote(msg_followup)

            c_fup1, c_fup2 = st.columns([2, 1.5])
            with c_fup1:
                if tel_limpo_o:
                    link_wpp_fup = f"https://wa.me/{tel_limpo_o}?text={encoded_fup}"
                    st.markdown(f"""
                        <a href="{link_wpp_fup}" target="_blank" style="background: #25d366; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 14px; display: inline-block; margin-bottom: 15px;">
                            📲 Enviar Follow-up via WhatsApp ao Responsável
                        </a>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Telefone de contacto não preenchido para envio direto de WhatsApp.")
            with c_fup2:
                if st.button(f"✅ Aprovar Orçamento & Liberar Execução (OS #{id_os_orc})", key=f"btn_aprov_orc_{idx_o}", type="primary"):
                    df.at[idx_o, 'pendencias'] = f"[ORÇAMENTO APROVADO - LIBERADO PARA EXECUÇÃO] {desc_o}"
                    df.at[idx_o, 'confirmado'] = 'SIM'
                    if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                        st.cache_data.clear()
                        st.success(f"✅ Orçamento da OS #{id_os_orc} aprovado! Serviço liberado na escala técnica.")
                        st.rerun()
