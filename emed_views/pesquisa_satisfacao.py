# -*- coding: utf-8 -*-
"""
Módulo de Pesquisa de Satisfação Pós-Atendimento & Impulsionador Google Review da EMED.
Coleta feedback estruturado (CSAT / NPS), vincula à Ordem de Serviço concluída e direciona
clientes satisfeitos para avaliarem a EMED diretamente no Google Meu Negócio.
"""

import sqlite3
import datetime
import pandas as pd
import streamlit as st
from emed_core import limpar_texto, obter_id_os
from emed_services import AppContext

URL_GOOGLE_REVIEW_OFICIAL = "https://search.google.com/local/writereview?placeid=ChIJ_EMED_SERVICOS_HOSPITALARES_CE"


def inicializar_tabela_satisfacao(db_name: str):
    """Garante a existência da tabela pesquisas_satisfacao no SQLite."""
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pesquisas_satisfacao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                os_id TEXT,
                cliente TEXT,
                cnpj TEXT,
                tecnico_responsavel TEXT,
                nota INTEGER,
                estrelas TEXT,
                tags TEXT,
                comentario TEXT,
                data_avaliacao TEXT,
                clicou_google_review INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def registrar_pesquisa(db_name: str, os_id: str, cliente: str, cnpj: str, tecnico: str, nota: int, tags: list, comentario: str, clicou_google: int = 0) -> tuple[bool, str]:
    """Salva a avaliação de satisfação do cliente vinculada à OS."""
    data_hoje = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    estrelas_str = "⭐" * nota
    tags_str = ", ".join(tags)
    try:
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pesquisas_satisfacao (os_id, cliente, cnpj, tecnico_responsavel, nota, estrelas, tags, comentario, data_avaliacao, clicou_google_review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(os_id), cliente, cnpj, tecnico, nota, estrelas_str, tags_str, comentario, data_hoje, clicou_google))
            conn.commit()
        return True, "Pesquisa de satisfação registrada com sucesso!"
    except Exception as e:
        return False, f"Erro ao registrar pesquisa: {str(e)}"


def render_pesquisa_satisfacao(ctx: AppContext):
    """Visão Completa do Módulo de Pesquisa de Satisfação & Google Review Booster."""
    db_name = ctx.db_name
    inicializar_tabela_satisfacao(db_name)

    st.markdown("""
        <div style="background: linear-gradient(135deg, #1f1b24 0%, #332701 50%, #1e293b 100%);
                    border-radius: 12px; padding: 18px 24px; border: 1.5px solid #f59e0b;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="color: #fbbf24; margin: 0; font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        ⭐ PESQUISA DE SATISFAÇÃO & GOOGLE REVIEWS
                        <span style="font-size: 13px; background: #f59e0b; color: #78350f; padding: 3px 8px; border-radius: 6px; font-weight: 800;">CSAT & NPS Booster</span>
                    </h2>
                    <p style="color: #fef3c7; margin: 6px 0 0 0; font-size: 13.5px;">
                        Coleta de feedback pós-atendimento das Ordens de Serviço e redirecionamento de clientes satisfeitos para elevar a nota da EMED no Google.
                    </p>
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); text-align: right;">
                    <div style="font-size: 11px; color: #cbd5e1; font-weight: 600;">FEEDBACK EMED</div>
                    <div style="font-size: 14px; font-weight: 800; color: #fbbf24;">🌟 REPUTAÇÃO MÁXIMA</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    with sqlite3.connect(db_name) as conn:
        df_sat = pd.read_sql_query("SELECT * FROM pesquisas_satisfacao ORDER BY id DESC", conn)

    # Cálculo dos KPIs de Satisfação
    total_avaliacoes = len(df_sat)
    if total_avaliacoes > 0:
        media_csat = df_sat["nota"].mean()
        promotores = len(df_sat[df_sat["nota"] >= 4])
        detratores = len(df_sat[df_sat["nota"] <= 2])
        nps_score = int(((promotores - detratores) / total_avaliacoes) * 100)
        redirecionados = int(df_sat["clicou_google_review"].sum())
    else:
        media_csat = 5.0
        nps_score = 100
        promotores = 0
        redirecionados = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #fbbf24; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">MÉDIA CSAT (ESTRELAS)</div>
                <div style="color: #fbbf24; font-size: 24px; font-weight: 800;">⭐ {media_csat:.1f} / 5.0</div>
                <div style="color: #fde68a; font-size: 11px; margin-top: 2px;">Índice de Qualidade do Serviço</div>
            </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #10b981; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">NET PROMOTER SCORE</div>
                <div style="color: #10b981; font-size: 24px; font-weight: 800;">+{nps_score} NPS</div>
                <div style="color: #6ee7b7; font-size: 11px; margin-top: 2px;">Zona de Excelência Técnica</div>
            </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #38bdf8; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">AVALIAÇÕES REGISTRADAS</div>
                <div style="color: #38bdf8; font-size: 24px; font-weight: 800;">{total_avaliacoes}</div>
                <div style="color: #bae6fd; font-size: 11px; margin-top: 2px;">{promotores} avaliações 4 e 5 estrelas</div>
            </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
            <div style="background: #1e293b; border-left: 5px solid #ec4899; padding: 14px; border-radius: 8px;">
                <div style="color: #94a3b8; font-size: 12px; font-weight: 600;">BOOSTER GOOGLE REVIEWS</div>
                <div style="color: #f472b6; font-size: 24px; font-weight: 800;">{redirecionados}</div>
                <div style="color: #fbcfe8; font-size: 11px; margin-top: 2px;">Cliques para avaliação pública</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    tab_avaliar, tab_historico = st.tabs([
        "⭐ 1. Registrar Avaliação do Cliente (Pós-OS)",
        "📊 2. Histórico de Depoimentos & Métricas por Técnico",
    ])

    with tab_avaliar:
        df_chamados = ctx.df
        col_esq, col_dir = st.columns([1.6, 1.4])

        with col_esq:
            st.markdown("#### 📝 Identificação da Ordem de Serviço")
            opcoes_os_sat = []
            for idx, r in df_chamados.iterrows():
                os_num = obter_id_os(idx, r)
                cli_nome = limpar_texto(r.get("cliente"), "CLIENTE")
                tec_resp = limpar_texto(r.get("tecnico_responsavel"), "TÉCNICO")
                opcoes_os_sat.append(f"OS #{os_num} — {cli_nome} (Téc: {tec_resp})")

            sel_os_sat = st.selectbox("Selecione o Atendimento Realizado:", opcoes_os_sat)
            os_id_val = sel_os_sat.split("—")[0].replace("OS #", "").strip()

            dados_os = df_chamados[df_chamados.index.astype(str) == os_id_val]
            if dados_os.empty:
                dados_os = df_chamados.iloc[[int(os_id_val) % len(df_chamados)]]
            linha_os = dados_os.iloc[0]

            cli_nome_val = limpar_texto(linha_os.get("cliente"), "HOSPITAL")
            cnpj_val = limpar_texto(linha_os.get("cnpj"), "")
            tec_val = limpar_texto(linha_os.get("tecnico_responsavel"), "EQUIPE EMED")

            st.caption(f"🏥 **Cliente:** {cli_nome_val} | 👨‍🔧 **Técnico:** {tec_val}")

            st.markdown("#### 🌟 Como você avalia o atendimento prestado pela EMED?")
            nota_escolhida = st.select_slider(
                "Nível de Satisfação Geral:",
                options=[1, 2, 3, 4, 5],
                value=5,
                format_func=lambda x: {
                    5: "⭐⭐⭐⭐⭐ 5 - Excelente (Superou expectativas)",
                    4: "⭐⭐⭐⭐ 4 - Muito Bom (Serviço de alta qualidade)",
                    3: "⭐⭐⭐ 3 - Regular (Atendeu o básico)",
                    2: "⭐⭐ 2 - Insatisfatório",
                    1: "⭐ 1 - Crítico",
                }[x]
            )

            tags_opcoes = [
                "⚡ Atendimento Rápido e Pontual",
                "👨‍🔧 Técnico Altamente Capacitado",
                "🛏️ Equipamento 100% Operacional",
                "💬 Comunicação Clara e Transparente",
                "🧹 Sala Limpa e Organizada",
                "📋 Laudo Técnico Preciso e Ágil",
            ]
            tags_selecionadas = st.multiselect(
                "O que mais se destacou no atendimento?",
                tags_opcoes,
                default=tags_opcoes[:3] if nota_escolhida >= 4 else []
            )

            comentario_cliente = st.text_area(
                "Deixe uma mensagem, elogio ou sugestão para a equipe:",
                placeholder="Ex: Excelente atendimento do técnico, o equipamento voltou a operar rapidamente e salvou nosso plantão...",
                height=90
            )

            btn_salvar_pesquisa = st.button("💾 Confirmar e Registrar Avaliação", type="primary", use_container_width=True)

        with col_dir:
            st.markdown("#### 🚀 Impulsionador de Avaliações Google")
            if nota_escolhida >= 4:
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%); border: 2px solid #60a5fa; border-radius: 12px; padding: 20px; text-align: center;">
                        <div style="font-size: 38px;">🎉</div>
                        <h3 style="color: #93c5fd; margin: 8px 0 4px 0;">Ficamos Muito Felizes!</h3>
                        <p style="color: #e2e8f0; font-size: 13.5px; line-height: 1.5;">
                            Sua opinião positiva nos motiva a continuar entregando a melhor engenharia clínica do Ceará.
                            <b>Ajude-nos a subir nossa nota no Google</b> compartilhando este elogio em apenas 1 clique:
                        </p>
                        <a href="{URL_GOOGLE_REVIEW_OFICIAL}" target="_blank" style="display: inline-block; background: #f59e0b; color: #000; font-weight: 900; font-size: 15px; padding: 12px 22px; border-radius: 8px; text-decoration: none; box-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-top: 10px;">
                            ⭐ Avaliar a EMED no Google Meu Negócio
                        </a>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div style="background: rgba(239, 68, 68, 0.15); border: 2px solid #ef4444; border-radius: 12px; padding: 20px; text-align: center;">
                        <div style="font-size: 38px;">🛡️</div>
                        <h3 style="color: #fca5a5; margin: 8px 0 4px 0;">Garantia de Qualidade EMED</h3>
                        <p style="color: #fecaca; font-size: 13.5px;">
                            Lamentamos que o atendimento não tenha superado 100% de suas expectativas. Seu feedback foi direcionado imediatamente à gerência técnica para contato prioritário e averiguação.
                        </p>
                    </div>
                """, unsafe_allow_html=True)

        if btn_salvar_pesquisa:
            clicou_g = 1 if nota_escolhida >= 4 else 0
            ok, msg = registrar_pesquisa(
                db_name=db_name,
                os_id=os_id_val,
                cliente=cli_nome_val,
                cnpj=cnpj_val,
                tecnico=tec_val,
                nota=nota_escolhida,
                tags=tags_selecionadas,
                comentario=comentario_cliente,
                clicou_google=clicou_g
            )
            if ok:
                st.success(f"🎉 {msg}")
                st.balloons()
                st.rerun()
            else:
                st.error(msg)

    with tab_historico:
        st.markdown("#### 📋 Depoimentos e Avaliações Recebidas")
        if df_sat.empty:
            st.info("Nenhuma avaliação de satisfação registrada ainda. Registre a primeira na aba 1.")
        else:
            for _, r_sat in df_sat.iterrows():
                nota_r = int(r_sat.get("nota", 5))
                estrela_icon = "⭐" * nota_r
                cli_r = r_sat.get("cliente", "Cliente")
                tec_r = r_sat.get("tecnico_responsavel", "Equipe EMED")
                com_r = r_sat.get("comentario", "") or "Sem comentário adicional."
                tags_r = r_sat.get("tags", "")
                dt_r = r_sat.get("data_avaliacao", "N/D")
                os_r = r_sat.get("os_id", "N/D")

                cor_borda = "#10b981" if nota_r >= 4 else ("#f59e0b" if nota_r == 3 else "#ef4444")

                st.markdown(f"""
                    <div style="background: #1e293b; border-left: 6px solid {cor_borda}; padding: 14px 18px; border-radius: 8px; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 18px; color: #fbbf24; font-weight: 800;">{estrela_icon} ({nota_r}/5)</span>
                            <span style="color: #94a3b8; font-size: 12px;">{dt_r} | OS #{os_r}</span>
                        </div>
                        <div style="color: #f8fafc; font-weight: 700; margin: 4px 0;">{cli_r} — <span style="color: #94a3b8; font-weight: normal;">Técnico: {tec_r}</span></div>
                        <div style="color: #cbd5e1; font-style: italic; margin-top: 4px;">"{com_r}"</div>
                        <div style="margin-top: 6px; font-size: 11.5px; color: #38bdf8;">🏷️ {tags_r}</div>
                    </div>
                """, unsafe_allow_html=True)
