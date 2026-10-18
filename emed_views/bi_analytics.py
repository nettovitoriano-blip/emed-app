import plotly.express as px
import streamlit as st
from emed_services import AppContext, classificar_pendencia
from emed_ui import estilizar_grafico


def render_graficos_bi(ctx: AppContext):
    st.markdown("### 📈 Indicadores Operacionais & Análise de Gráficos em Tempo Real")

    df_graf = ctx.df.copy()
    df_graf['tipo_servico_clean'] = df_graf['tipo_servico'].fillna('NÃO DEFINIDO').astype(str).str.upper().str.strip()
    df_graf['tecnico_clean'] = df_graf['tecnico_responsavel'].fillna('A DEFINIR').astype(str).str.upper().str.strip()
    df_graf['cidade_clean'] = df_graf['cidade'].fillna('OUTRAS').astype(str).str.upper().str.strip()
    df_graf['status_clean'] = df_graf['status'].fillna('ATIVO').astype(str).str.upper().str.strip()
    df_graf['pendencia_cat'] = df_graf['pendencias'].apply(classificar_pendencia)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("##### 🛠️ Distribuição por Tipo de Serviço")
        df_serv_cont = df_graf['tipo_servico_clean'].value_counts().reset_index()
        df_serv_cont.columns = ['Serviço', 'Quantidade']
        if not df_serv_cont.empty:
            fig_pizza = px.pie(
                df_serv_cont,
                names='Serviço',
                values='Quantidade',
                hole=0.4,
                color='Serviço',
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_pizza = estilizar_grafico(fig_pizza)
            st.plotly_chart(fig_pizza, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem dados para o gráfico de serviços.")

    with col_g2:
        st.markdown("##### 👨‍🔧 Volume de Equipamentos / OS por Técnico")
        if "filtro_tec_grafico" not in st.session_state:
            st.session_state.filtro_tec_grafico = None

        df_tec_cont = df_graf[df_graf['tecnico_clean'] != ''].groupby('tecnico_clean').size().reset_index(name='Quantidade')
        if not df_tec_cont.empty:
            fig_tec = px.bar(
                df_tec_cont,
                x='tecnico_clean',
                y='Quantidade',
                color='tecnico_clean',
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_tec.update_layout(
                showlegend=False,
                xaxis_title="Técnico",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_tec.update_xaxes(fixedrange=True)
            fig_tec.update_yaxes(fixedrange=True)
            fig_tec = estilizar_grafico(fig_tec)

            evento_grafico = st.plotly_chart(
                fig_tec,
                use_container_width=True,
                on_select="rerun",
                config={'displayModeBar': False},
                key="grafico_tecnicos_interativo"
            )

            if evento_grafico and "selection" in evento_grafico and evento_grafico["selection"]["points"]:
                ponto_clicado = evento_grafico["selection"]["points"][0]
                if "x" in ponto_clicado:
                    tecnico_clicado = ponto_clicado["x"]
                    if st.session_state.filtro_tec_grafico != tecnico_clicado:
                        st.session_state.filtro_tec_grafico = tecnico_clicado
                        st.rerun()

            if st.session_state.filtro_tec_grafico:
                col_f_info, col_f_btn = st.columns([3, 1])
                with col_f_info:
                    st.info(f"🔍 A mostrar dados focados no técnico: **{st.session_state.filtro_tec_grafico}**")
                with col_f_btn:
                    if st.button("❌ Fechar"):
                        st.session_state.filtro_tec_grafico = None
                        st.rerun()
        else:
            st.info("Sem dados para o gráfico de técnicos.")

    st.markdown("---")
    col_g3, col_g4 = st.columns(2)
    with col_g3:
        st.markdown("##### 🚨 Análise de Pendências & Bloqueios Operacionais")
        df_pend_cont = df_graf[df_graf['status_clean'] == 'ATIVO']['pendencia_cat'].value_counts().reset_index()
        df_pend_cont.columns = ['Pendência', 'Quantidade']
        if not df_pend_cont.empty:
            fig_pend = px.bar(
                df_pend_cont,
                x='Pendência',
                y='Quantidade',
                color='Pendência',
                color_discrete_sequence=['#f59e0b', '#ef4444', '#3b82f6', '#10b981']
            )
            fig_pend.update_layout(
                showlegend=False,
                xaxis_title="Categoria de Pendência",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_pend.update_xaxes(fixedrange=True)
            fig_pend.update_yaxes(fixedrange=True)
            fig_pend = estilizar_grafico(fig_pend)
            st.plotly_chart(fig_pend, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem pendências ativas para categorizar.")

    with col_g4:
        st.markdown("##### 📍 Top Cidades em Volume de Atendimento")
        df_cid_cont = df_graf[df_graf['cidade_clean'] != ''].groupby('cidade_clean').size().reset_index(name='Quantidade').head(8)
        if not df_cid_cont.empty:
            fig_cid = px.bar(
                df_cid_cont,
                x='cidade_clean',
                y='Quantidade',
                color='cidade_clean',
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            fig_cid.update_layout(
                showlegend=False,
                xaxis_title="Cidade",
                yaxis_title="Quantidade",
                margin=dict(t=20, b=20, l=20, r=20),
                dragmode=False
            )
            fig_cid.update_xaxes(fixedrange=True)
            fig_cid.update_yaxes(fixedrange=True)
            fig_cid = estilizar_grafico(fig_cid)
            st.plotly_chart(fig_cid, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("Sem dados de cidades.")
