import datetime
import urllib.parse
import pandas as pd
import streamlit as st
from emed_core import (
    limpar_texto,
    limpar_float,
    limpar_int,
    get_db_connection,
    obter_id_os,
    atualizar_status_solicitacao_peca,
    SUGESTOES_SEPARACAO_POR_ATIVIDADE,
    KITS_INSTRUMENTOS_POR_SITUACAO,
)
from emed_services import (
    AppContext,
    carregar_estoque,
    carregar_solicitacoes,
    carregar_baixas_consumiveis,
    calcular_distancia,
    formatar_tempo,
    salvar_dados_seguro,
)


def render_gestao_pendencias(ctx: AppContext):
    if ctx.perfil_atual != "Gestor":
        st.warning("⚠️ Acesso restrito ao perfil Gestor.")
        return

    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("### 🚨 Painel Central de Pendências & Direcionamento de Técnicos (Modo Gestor)")
    st.info("Visão exclusiva da Gestão: acompanhe todas as pendências abertas e direcione-as rapidamente para o técnico disponível.")

    df_pend = df[df['status'].fillna('ATIVO').astype(str).str.upper() == 'ATIVO']
    if df_pend.empty:
        st.success("🎉 Sem pendências ativas no momento.")
    else:
        for idx_p, row_p in df_pend.iterrows():
            id_os_p = obter_id_os(idx_p, row_p)
            cli_p = limpar_texto(row_p.get('cliente'), 'N/D')
            eq_p = limpar_texto(row_p.get('equipamento'), 'N/D')
            tec_p = limpar_texto(row_p.get('tecnico_responsavel'), 'A DEFINIR')
            pend_p = limpar_texto(row_p.get('pendencias'), 'Sem descrição')
            inst_p = limpar_texto(row_p.get('instrumento_necessario'), 'Nenhum especificado')
            etapa_p = limpar_texto(row_p.get('etapa_preventiva'), 'Geral')

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid #f59e0b; padding: 15px; border-radius: 8px; margin-bottom: 8px;">
                    <h4 style="margin: 0 0 5px 0; color: #64dfdf;">🏥 OS #{id_os_p} | {cli_p} — ⚙️ {eq_p}</h4>
                    <p style="margin: 4px 0;"><strong>Técnico Atual:</strong> {tec_p} | <strong>Etapa Preventiva:</strong> {etapa_p}</p>
                    <p style="margin: 4px 0;"><strong>Pendência:</strong> <span style="color: #fca5a5;">{pend_p}</span></p>
                    <p style="margin: 4px 0; color: #64dfdf;"><strong>📐 Instrumento / Material Requerido:</strong> {inst_p}</p>
                </div>
            """, unsafe_allow_html=True)

            with st.expander(f"👉 Direcionar / Mudar Técnico ou Instrumento da OS #{id_os_p} ({cli_p})"):
                with st.form(f"form_gestor_dir_{idx_p}"):
                    c_gd1, c_gd2 = st.columns(2)
                    lista_t_gestor = sorted(list(equipa_tecnica.keys()))
                    with c_gd1:
                        idx_tg = lista_t_gestor.index(tec_p.upper()) if tec_p.upper() in lista_t_gestor else 0
                        novo_t_dir = st.selectbox(
                            "Direcionar para o Técnico:",
                            lista_t_gestor,
                            index=idx_tg,
                            key=f"gd_tec_{idx_p}"
                        )
                        novo_inst_dir = st.text_input(
                            "Instrumento / Ferramenta Obrigatória:",
                            value="" if inst_p == "Nenhum especificado" else inst_p,
                            key=f"gd_inst_{idx_p}"
                        )
                    with c_gd2:
                        nova_desc_dir = st.text_input(
                            "Atualizar Instrução da Pendência:",
                            value=pend_p,
                            key=f"gd_desc_{idx_p}"
                        )
                        confirmar_dir = st.selectbox("Marcar como Confirmado na Escala?", ["SIM", "NÃO"], index=0, key=f"gd_conf_{idx_p}")

                    if st.form_submit_button("💾 Direcionar OS para o Técnico", type="primary"):
                        df.at[idx_p, 'tecnico_responsavel'] = novo_t_dir
                        df.at[idx_p, 'telefone_tecnico'] = equipa_tecnica.get(novo_t_dir, {}).get("tel", "")
                        df.at[idx_p, 'instrumento_necessario'] = novo_inst_dir.strip().upper()
                        df.at[idx_p, 'pendencias'] = nova_desc_dir.strip().upper()
                        df.at[idx_p, 'confirmado'] = confirmar_dir
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success(f"✅ Pendência direcionada para {novo_t_dir} com sucesso!")
                            st.rerun()


def render_solicitacao_pecas(ctx: AppContext):
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("### 🧰 Quadro de Ferramentas & Kits em Tempo Real")
    st.info("💡 **Consulte antes de se deslocar à empresa:** saiba instantaneamente se o kit está disponível no Almoxarifado ou em posse de outro colega em campo, evitando viagens perdidas!")

    df_est_quadro = carregar_estoque(ctx.db_name)
    df_sol_ativas = carregar_solicitacoes(ctx.db_name)
    if not df_sol_ativas.empty:
        df_sol_ativas = df_sol_ativas[~df_sol_ativas['status_pedido'].fillna('').str.contains('DEVOLVIDO|CANCELADO|ESTORNADO|APLICADO', case=False)]

    if not df_est_quadro.empty:
        df_ferramentas = df_est_quadro[df_est_quadro['tipo_item'].fillna('').str.contains('INSTRUMENTO|FERRAMENTA', case=False)]
        if not df_ferramentas.empty:
            total_ferr = len(df_ferramentas)
            disp_ferr = sum(1 for _, r in df_ferramentas.iterrows() if limpar_int(r.get('quantidade'), 0) > 0)
            uso_ferr = total_ferr - disp_ferr

            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.metric("Total de Ferramentas & Kits Cadastrados", f"{total_ferr} itens")
            with m_col2:
                st.metric("🟢 Disponíveis no Almoxarifado", f"{disp_ferr} itens")
            with m_col3:
                st.metric("🔴 Em Uso com Técnicos", f"{uso_ferr} itens")

            filtro_busca_ferr = st.text_input("🔍 Pesquisar ferramenta, kit ou instrumento no quadro:", placeholder="Ex: Multímetro, Mamografia, Colimador, Furadeira, Talha, Osciloscópio...")
            
            df_exibicao_f = df_ferramentas
            if filtro_busca_ferr.strip():
                df_exibicao_f = df_ferramentas[
                    df_ferramentas['nome_peca'].str.contains(filtro_busca_ferr, case=False, na=False) |
                    df_ferramentas['codigo'].str.contains(filtro_busca_ferr, case=False, na=False)
                ]

            cols_q = st.columns(4)
            for idx_f, (_, r_ferr) in enumerate(df_exibicao_f.iterrows()):
                nome_f = r_ferr['nome_peca']
                cod_f = r_ferr['codigo']
                qtd_f = limpar_int(r_ferr.get('quantidade'), 0)

                # Identifica qual técnico está com este kit ou ferramenta
                tecs_com_item = []
                if not df_sol_ativas.empty:
                    for _, r_sol in df_sol_ativas.iterrows():
                        txt_itens = (str(r_sol.get('itens_solicitados', '')) + " " + str(r_sol.get('instrumentos_solicitados', ''))).upper()
                        if cod_f.upper() in txt_itens or nome_f.upper() in txt_itens:
                            tecs_com_item.append(str(r_sol.get('tecnico', '')).upper())

                if tecs_com_item:
                    disp_cor = "#ef4444"
                    disp_bg = "rgba(239, 68, 68, 0.15)"
                    tecs_unicos = ", ".join(sorted(list(set(tecs_com_item))))
                    disp_txt = f"🔴 COM: {tecs_unicos}"
                elif qtd_f > 0:
                    disp_cor = "#10b981"
                    disp_bg = "rgba(16, 185, 129, 0.12)"
                    disp_txt = f"🟢 NO ALMOXARIFADO ({qtd_f} un.)"
                else:
                    disp_cor = "#ef4444"
                    disp_bg = "rgba(239, 68, 68, 0.12)"
                    disp_txt = "🔴 EM USO NO CAMPO"

                with cols_q[idx_f % 4]:
                    st.markdown(f"""
                        <div style="background: #1e293b; border-radius: 8px; padding: 12px; margin-bottom: 12px; border: 1px solid #334155; border-top: 3px solid {disp_cor}; min-height: 110px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 11px; color: #94a3b8; font-weight: bold;">{cod_f}</span>
                                <span style="background: {disp_bg}; color: {disp_cor}; font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 4px;">{disp_txt}</span>
                            </div>
                            <div style="font-size: 12px; font-weight: 700; color: #f8fafc; margin: 6px 0 6px 0; line-height: 1.3;">{nome_f[:55]}</div>
                        </div>
                    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### ✋ Pegar / Retirar Ferramenta ou Peça (Registrar Posse)")
    st.caption("Sem burocracia ou comprovantes: apenas selecione quem está pegando e tique os itens para que toda a equipe saiba onde a ferramenta está.")

    df_est_atual = carregar_estoque(ctx.db_name)
    lista_t_sol = sorted(list(equipa_tecnica.keys()))

    with st.form("form_solicitacao_almoxarifado"):
        usr_sol_up = ctx.usuario_atual.upper()
        idx_sol_u = lista_t_sol.index(usr_sol_up) if usr_sol_up in lista_t_sol else 0
        tec_solicitante = st.selectbox(
            "👨‍🔧 Técnico com o Material / Responsável pela Retirada *",
            lista_t_sol,
            index=idx_sol_u,
            help="Tique o técnico que está saindo ou trabalhando com este material."
        )
        cli_destino_sol = f"COM O TÉCNICO ({tec_solicitante})"

        st.markdown("#### ☑️ Ticagem de Materiais, Instrumentos e Peças em Estoque")
        itens_ticados = []
        if df_est_atual.empty:
            st.warning("Nenhum item registado no estoque.")
        else:
            # 1. INSTRUMENTOS E FERRAMENTARIA
            df_inst = df_est_atual[df_est_atual['tipo_item'].fillna('').str.contains('INSTRUMENTO|FERRAMENTA', case=False)]
            if not df_inst.empty:
                st.markdown("##### 🔬 Instrumentos de Medição & Ferramentas Calibradas")
                for _, r_item in df_inst.iterrows():
                    cod_i = r_item['codigo']
                    nome_i = r_item['nome_peca']
                    qtd_disp_i = limpar_int(r_item.get('quantidade'), 0)
                    c_it1, c_it2 = st.columns([3.8, 1])
                    with c_it1:
                        marcado = st.checkbox(
                            f"🔬 [{cod_i}] {nome_i} | Saldo Almoxarifado: {qtd_disp_i} un.",
                            disabled=(qtd_disp_i <= 0),
                            key=f"chk_item_{cod_i}"
                        )
                    with c_it2:
                        qtd_ped = st.number_input(
                            "Qtd",
                            min_value=1,
                            max_value=max(1, qtd_disp_i),
                            value=1,
                            disabled=(qtd_disp_i <= 0),
                            key=f"num_item_{cod_i}"
                        )
                    if marcado and qtd_disp_i > 0:
                        itens_ticados.append({"codigo": cod_i, "nome": nome_i, "qtd": int(qtd_ped)})

            # 2. PEÇAS DE REPOSIÇÃO
            df_pec = df_est_atual[df_est_atual['tipo_item'].fillna('').str.contains('COMERCIAL|PEÇA', case=False)]
            if not df_pec.empty:
                st.markdown("##### ⚙️ Peças de Reposição & Componentes Sobressalentes")
                for _, r_item in df_pec.iterrows():
                    cod_i = r_item['codigo']
                    nome_i = r_item['nome_peca']
                    qtd_disp_i = limpar_int(r_item.get('quantidade'), 0)
                    c_it1, c_it2 = st.columns([3.8, 1])
                    with c_it1:
                        marcado = st.checkbox(
                            f"⚙️ [{cod_i}] {nome_i} | Saldo Almoxarifado: {qtd_disp_i} un.",
                            disabled=(qtd_disp_i <= 0),
                            key=f"chk_item_{cod_i}"
                        )
                    with c_it2:
                        qtd_ped = st.number_input(
                            "Qtd",
                            min_value=1,
                            max_value=max(1, qtd_disp_i),
                            value=1,
                            disabled=(qtd_disp_i <= 0),
                            key=f"num_item_{cod_i}"
                        )
                    if marcado and qtd_disp_i > 0:
                        itens_ticados.append({"codigo": cod_i, "nome": nome_i, "qtd": int(qtd_ped)})

            # 3. CONSUMÍVEIS E LIMPEZA
            df_con = df_est_atual[df_est_atual['tipo_item'].fillna('').str.contains('CONSUM|LIMPEZA', case=False)]
            if not df_con.empty:
                st.markdown("##### 🧪 Consumíveis & Limpeza Técnica")
                for _, r_item in df_con.iterrows():
                    cod_i = r_item['codigo']
                    nome_i = r_item['nome_peca']
                    qtd_disp_i = limpar_int(r_item.get('quantidade'), 0)
                    c_it1, c_it2 = st.columns([3.8, 1])
                    with c_it1:
                        marcado = st.checkbox(
                            f"🧪 [{cod_i}] {nome_i} | Saldo Almoxarifado: {qtd_disp_i} un.",
                            disabled=(qtd_disp_i <= 0),
                            key=f"chk_item_{cod_i}"
                        )
                    with c_it2:
                        qtd_ped = st.number_input(
                            "Qtd",
                            min_value=1,
                            max_value=max(1, qtd_disp_i),
                            value=1,
                            disabled=(qtd_disp_i <= 0),
                            key=f"num_item_{cod_i}"
                        )
                    if marcado and qtd_disp_i > 0:
                        itens_ticados.append({"codigo": cod_i, "nome": nome_i, "qtd": int(qtd_ped)})

        st.markdown("#### 📋 Sugestão de Separação por Atividade (Checklist Rápido do Almoxarifado)")
        lista_opcoes_sug = ["-- Seleção Livre Direta no Estoque --"] + list(SUGESTOES_SEPARACAO_POR_ATIVIDADE.keys())
        sug_rapida = st.selectbox(
            "Selecione uma Sugestão de Carga por Atividade (Opcional):",
            lista_opcoes_sug,
            help="Carrega instantaneamente a lista de instrumentos e materiais sugeridos para o tipo de intervenção técnica."
        )
        texto_sug_padrao = ""
        if sug_rapida != "-- Seleção Livre Direta no Estoque --":
            sug_dados = SUGESTOES_SEPARACAO_POR_ATIVIDADE[sug_rapida]
            texto_sug_padrao = f"[{sug_dados['nome']}]\n" + "\n".join(f"• {it}" for it in sug_dados["itens"])
            st.caption(f"✨ **Recomendados para {sug_dados['nome']}:** " + ", ".join(sug_dados["itens"]))

        instrumentos_extras_sol = st.text_area(
            "📐 Instrumentos & Ferramentas a Separar pelo Almoxarifado:",
            value=texto_sug_padrao,
            placeholder="EX: MULTÍMETRO 1000V, OSCILOSCÓPIO, FANTOMA DE RESOÇÃO, TALHA, NÍVEL LASER...",
            height=110
        )

        if st.form_submit_button("✅ Pegar Ferramenta / Registrar Saída", type="primary"):
            if not itens_ticados and not instrumentos_extras_sol.strip():
                st.error("⚠️ Selecione pelo menos um material ou indique o instrumento necessário!")
            else:
                erro_conflito = None
                resumo_itens_str = "NENHUMA PEÇA DE ESTOQUE"
                data_ped_agora = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

                with get_db_connection(ctx.db_name) as conn_res:
                    cur_res = conn_res.cursor()
                    for it in itens_ticados:
                        cur_res.execute("SELECT quantidade FROM estoque_pecas WHERE codigo = ?", (it['codigo'],))
                        linha_q = cur_res.fetchone()
                        saldo_real_agora = int(linha_q[0]) if linha_q else 0
                        if it['qtd'] > saldo_real_agora:
                            erro_conflito = (
                                f"⚠️ Conflito de Estoque Online! O item '{it['nome']}' possui apenas "
                                f"{saldo_real_agora} un. disponíveis (outro técnico acabou de reservar)."
                            )
                            break

                    if not erro_conflito:
                        if itens_ticados:
                            resumo_itens_str = ", ".join([f"{i['qtd']}x {i['nome']} ({i['codigo']})" for i in itens_ticados])
                        for it in itens_ticados:
                            cur_res.execute(
                                "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE codigo = ?",
                                (it['qtd'], it['codigo'])
                            )
                        cur_res.execute("""
                            INSERT INTO solicitacoes_pecas
                            (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            tec_solicitante, cli_destino_sol, resumo_itens_str,
                            instrumentos_extras_sol.strip().upper(),
                            "ENTREGUE AO TÉCNICO / EM CAMPO", data_ped_agora
                        ))

                if erro_conflito:
                    st.error(erro_conflito)
                else:
                    st.cache_data.clear()
                    st.success(f"✅ Registrado com sucesso! Agora toda a equipe já sabe que o material está com **{tec_solicitante}**.")
                    st.rerun()

    st.markdown("---")
    st.markdown("#### 🔄 Ferramentas em Campo & Devolução Rápida ao Almoxarifado")
    st.caption("Ao devolver a ferramenta ou sobra de peça à empresa, clique em 'Devolver' para restabelecer imediatamente a disponibilidade no quadro.")
    df_sol_hist = carregar_solicitacoes(ctx.db_name)
    if not df_sol_hist.empty:
        df_em_campo = df_sol_hist[~df_sol_hist['status_pedido'].fillna('').str.contains('DEVOLVIDO|CANCELADO|ESTORNADO', case=False)]
        if not df_em_campo.empty:
            st.markdown("##### 🔴 Materiais Atualmente com Técnicos (Clique para Devolver):")
            for _, r_campo in df_em_campo.iterrows():
                id_c = r_campo['id']
                tec_c = r_campo['tecnico']
                itens_c = r_campo['itens_solicitados']
                data_c = r_campo.get('data_pedido', '')
                col_info_c, col_btn_c = st.columns([3.8, 1.4])
                with col_info_c:
                    st.markdown(f"**👨‍🔧 {tec_c}** | `{data_c}` | 🛠️ {itens_c}")
                with col_btn_c:
                    if st.button("📥 Devolver ao Almoxarifado", key=f"btn_dev_rapido_{id_c}", type="primary"):
                        ok_dev, msg_dev = atualizar_status_solicitacao_peca(ctx.db_name, id_c, "DEVOLVIDO AO ESTOQUE / BAIXA DE RETORNO")
                        if ok_dev:
                            st.cache_data.clear()
                            st.success(f"✅ Material de {tec_c} devolvido com sucesso! O quadro foi liberado.")
                            st.rerun()
                        else:
                            st.error(msg_dev)
        else:
            st.success("🟢 Todas as ferramentas e kits estão no Almoxarifado no momento! Nenhuma em campo.")

        with st.expander("📋 Ver Histórico Geral de Movimentações"):
            df_sol_vis = df_sol_hist.copy()
            cols_renomear = {
                "id": "#",
                "tecnico": "Técnico",
                "itens_solicitados": "Itens Retirados",
                "status_pedido": "Situação",
                "data_pedido": "Data Retirada"
            }
            cols_exibir = [c for c in cols_renomear.keys() if c in df_sol_vis.columns]
            st.dataframe(df_sol_vis[cols_exibir].rename(columns=cols_renomear), use_container_width=True, hide_index=True)


def render_mapa_rotas(ctx: AppContext):
    df = ctx.df

    st.markdown("### 🗺️ Mapa Operacional & Planeamento de Rotas")
    coordenadas_cidades = {
        "fortaleza": (-3.7172, -38.5433), "juazeiro": (-7.2009, -39.3148),
        "araripina": (-7.4811, -40.4994), "petrolina": (-9.3875, -40.5028),
        "taua": (-6.0044, -40.2934), "sobral": (-3.6895, -40.3486),
        "crato": (-7.2347, -39.4069), "eusebio": (-3.8856, -38.4614),
        "brasilia": (-15.7975, -47.8919), "iguatu": (-6.3594, -39.2986),
        "mossoro": (-5.1878, -37.3442), "catole": (-6.3439, -37.7467),
        "poranga": (-4.7450, -40.9256)
    }
    cores_hex = ["#64dfdf", "#f72585", "#7209b7", "#4cc9f0", "#ff9f1c", "#2ec4b6", "#e71d36", "#ffb703"]
    pontos_mapa = []
    clientes_ordenados = sorted([
        c for c in df['cliente'].unique()
        if str(c).strip() != '' and "NENHUM (AGUARDANDO" not in str(c).upper()
    ])

    for idx_c, cliente_nome in enumerate(clientes_ordenados):
        grupo = df[df['cliente'] == cliente_nome]
        primeira = grupo.iloc[0]
        cidade_str = str(primeira.get('cidade', '')).strip().lower()
        lat, lon = -3.7172, -38.5433
        for cid_key, coords in coordenadas_cidades.items():
            if cid_key in cidade_str:
                lat, lon = coords
                break
        pontos_mapa.append({
            'lat': lat, 'lon': lon, 'cliente': cliente_nome,
            'cidade': str(primeira.get('cidade', '')).upper(),
            'color': cores_hex[idx_c % len(cores_hex)]
        })

    clientes_selecionados_rota = st.multiselect("Selecione os clientes para a rota:", options=clientes_ordenados)
    if clientes_selecionados_rota:
        pts_filtrados = [p for p in pontos_mapa if p['cliente'] in clientes_selecionados_rota]
        st.map(pd.DataFrame(pts_filtrados), latitude="lat", longitude="lon", size=400, color="color", zoom=7)
        if len(pts_filtrados) >= 2:
            km_total = 0.0
            for i_r in range(len(pts_filtrados) - 1):
                km_total += calcular_distancia(
                    pts_filtrados[i_r]['lat'], pts_filtrados[i_r]['lon'],
                    pts_filtrados[i_r+1]['lat'], pts_filtrados[i_r+1]['lon']
                )
            st.info(f"🛣️ **Distância Estimada da Rota:** {km_total:.1f} KM | ⏱️ **Tempo Estimado de Deslocamento:** {formatar_tempo(km_total)}")
    else:
        st.map(pd.DataFrame(pontos_mapa), latitude="lat", longitude="lon", size=400, color="color", zoom=6)


def render_gestao_estoque(ctx: AppContext):
    st.markdown("### 📦 Controlo do Almoxarifado, Ferramentas & Peças Comerciais EMED")

    df_est_view = carregar_estoque(ctx.db_name)
    if df_est_view.empty:
        st.info("Nenhuma peça registada no estoque.")
    else:
        # Métricas de Categorias do Almoxarifado
        qtd_total = len(df_est_view)
        qtd_inst = len(df_est_view[df_est_view['tipo_item'].fillna('').str.contains('INSTRUMENTO|FERRAMENTA', case=False)])
        qtd_pec = len(df_est_view[df_est_view['tipo_item'].fillna('').str.contains('COMERCIAL|PEÇA', case=False)])
        qtd_con = len(df_est_view[df_est_view['tipo_item'].fillna('').str.contains('CONSUM|LIMPEZA', case=False)])

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("📦 Total de Itens", f"{qtd_total} itens")
        m_col2.metric("🔬 Instrumentos & Ferramentas", f"{qtd_inst} un.")
        m_col3.metric("⚙️ Peças de Reposição (OS)", f"{qtd_pec} un.")
        m_col4.metric("🧪 Consumíveis & Limpeza", f"{qtd_con} un.")

        st.markdown("#### 📋 Catálogo Geral do Almoxarifado")
        filtro_aba_est = st.radio(
            "Filtrar Visualização do Almoxarifado:",
            ["TODOS OS ITENS", "🔬 INSTRUMENTOS & FERRAMENTARIA", "⚙️ PEÇAS DE REPOSIÇÃO (OS)", "🧪 CONSUMÍVEIS & LIMPEZA"],
            horizontal=True
        )

        df_filtrado_view = df_est_view.copy()
        if "INSTRUMENTOS" in filtro_aba_est:
            df_filtrado_view = df_filtrado_view[df_filtrado_view['tipo_item'].fillna('').str.contains('INSTRUMENTO|FERRAMENTA', case=False)]
        elif "PEÇAS" in filtro_aba_est:
            df_filtrado_view = df_filtrado_view[df_filtrado_view['tipo_item'].fillna('').str.contains('COMERCIAL|PEÇA', case=False)]
        elif "CONSUMÍVEIS" in filtro_aba_est:
            df_filtrado_view = df_filtrado_view[df_filtrado_view['tipo_item'].fillna('').str.contains('CONSUM|LIMPEZA', case=False)]

        df_est_mostra = df_filtrado_view.copy()
        custo_num = pd.to_numeric(df_est_mostra['preco_custo'], errors='coerce').fillna(0.0)
        mc_num = pd.to_numeric(df_est_mostra['margem_contrato'], errors='coerce').fillna(30.0)
        ma_num = pd.to_numeric(df_est_mostra['margem_avulso'], errors='coerce').fillna(60.0)
        df_est_mostra['Preço Venda Contrato (R$)'] = (custo_num * (1 + mc_num / 100.0)).round(2)
        df_est_mostra['Preço Venda Avulso (R$)'] = (custo_num * (1 + ma_num / 100.0)).round(2)
        st.dataframe(df_est_mostra, use_container_width=True, hide_index=True)

    st.markdown("---")
    aba_est1, aba_est2 = st.tabs([
        "➕ Cadastrar / Editar Peça ou Consumível",
        "🔧 Dar Baixa de Consumível (Uso Interno / Sem Nota de Saída)"
    ])

    with aba_est1:
        if not df_est_view.empty:
            lista_pecas_fmt = (df_est_view['codigo'].astype(str) + " - " + df_est_view['nome_peca'].astype(str)).tolist()
            opcoes_pecas_ed = ["➕ CADASTRAR NOVO ITEM"] + lista_pecas_fmt
        else:
            opcoes_pecas_ed = ["➕ CADASTRAR NOVO ITEM"]

        escolha_peca_ed = st.selectbox("Selecione um Item para Editar/Somar Estoque ou Cadastre um Novo:", opcoes_pecas_ed)

        row_p_ed = None
        if escolha_peca_ed != "➕ CADASTRAR NOVO ITEM":
            cod_sel_ed = escolha_peca_ed.split(" - ")[0].strip()
            row_p_ed = df_est_view[df_est_view['codigo'] == cod_sel_ed].iloc[0]

        with st.form("form_novo_ou_editar_peca"):
            cp1, cp2 = st.columns(2)
            with cp1:
                cod_p = st.text_input(
                    "Código do Item *",
                    value=limpar_texto(row_p_ed['codigo']) if row_p_ed is not None else "",
                    placeholder="EX: PEC-005 ou CON-003"
                )
                nome_p = st.text_input(
                    "Nome / Descrição *",
                    value=limpar_texto(row_p_ed['nome_peca']) if row_p_ed is not None else "",
                    placeholder="EX: ESTABILIZADOR DE FILAMENTO ou ABRAÇADEIRA"
                )
                idx_cat_p = 0 if row_p_ed is None or "COMERCIAL" in str(row_p_ed.get('tipo_item', '')) else 1
                tipo_item_p = st.selectbox(
                    "Categoria do Item *",
                    ["PEÇA COMERCIAL (OS)", "CONSUMÍVEL INTERNO (USO DIÁRIO / SEM NF SAÍDA)", "INSTRUMENTO / FERRAMENTA"],
                    index=idx_cat_p
                )
            with cp2:
                qtd_p = st.number_input(
                    "Quantidade Total em Estoque *",
                    min_value=0,
                    value=limpar_int(row_p_ed['quantidade'], 1) if row_p_ed is not None else 1
                )
                custo_p = st.number_input(
                    "Preço de Custo Unitário (R$)",
                    min_value=0.0,
                    value=limpar_float(row_p_ed['preco_custo'], 100.0) if row_p_ed is not None else 100.0,
                    step=10.0
                )
                val_mc = limpar_float(row_p_ed.get('margem_contrato'), 30.0) if row_p_ed is not None else 30.0
                val_ma = limpar_float(row_p_ed.get('margem_avulso'), 60.0) if row_p_ed is not None else 60.0
                m_cont_p = st.number_input("Margem Contrato (%)", min_value=0.0, value=val_mc, step=5.0)
                m_avul_p = st.number_input("Margem Avulso (%)", min_value=0.0, value=val_ma, step=5.0)

            c_bp1, c_bp2 = st.columns(2)
            with c_bp1:
                btn_salvar_peca = st.form_submit_button("💾 Registar / Atualizar Item no Estoque", type="primary")
            with c_bp2:
                btn_excluir_peca = st.form_submit_button("🗑️ Excluir Item do Estoque")

            if btn_salvar_peca:
                if not cod_p.strip() or not nome_p.strip():
                    st.error("⚠️ Preencha o código e o nome do item!")
                else:
                    try:
                        with get_db_connection(ctx.db_name) as conn_ip:
                            conn_ip.execute("""
                                INSERT OR REPLACE INTO estoque_pecas
                                (codigo, nome_peca, quantidade, preco_custo, margem_contrato, margem_avulso, tipo_item)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                cod_p.strip().upper(), nome_p.strip().upper(),
                                int(qtd_p), float(custo_p), float(m_cont_p), float(m_avul_p), tipo_item_p
                            ))
                        st.cache_data.clear()
                        st.success(f"✅ Item '{nome_p.strip().upper()}' guardado e tabela atualizada com sucesso!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao salvar item: {ex}")

            if btn_excluir_peca and row_p_ed is not None:
                with get_db_connection(ctx.db_name) as conn_ip:
                    conn_ip.execute("DELETE FROM estoque_pecas WHERE codigo = ?", (row_p_ed['codigo'],))
                st.cache_data.clear()
                st.success("🗑️ Item excluído do estoque!")
                st.rerun()

    with aba_est2:
        st.markdown("##### 🔧 Baixa de Consumíveis para Manutenções do Dia a Dia ou Uso Interno na Empresa")
        st.caption("Utilize para dar saída em abraçadeiras, fitas isolantes, álcool isopropílico, parafusos, solda, etc., sem nota fiscal de saída.")
        if df_est_view.empty:
            st.info("Cadastre itens no estoque primeiro.")
        else:
            with st.form("form_baixa_consumivel"):
                cb1, cb2 = st.columns(2)
                with cb1:
                    opcoes_cons_lista = (
                        df_est_view['codigo'] + " - " + df_est_view['nome_peca']
                        + " (Saldo: " + df_est_view['quantidade'].astype(str) + ")"
                    ).tolist()
                    item_cons_sel = st.selectbox("Selecione o Consumível / Material", opcoes_cons_lista)
                    qtd_cons_baixa = st.number_input("Quantidade Consumida", min_value=1, value=1)
                with cb2:
                    setor_tec_cons = st.text_input("Técnico ou Setor que Utilizou *", value=ctx.usuario_atual)
                    finalidade_cons = st.text_input(
                        "Finalidade / Onde foi aplicado *",
                        placeholder="EX: ORGANIZAÇÃO DE CABOS EM INSTALAÇÃO / BANCADA INTERNA"
                    )

                if st.form_submit_button("📉 Confirmar Baixa por Consumo Interno", type="primary"):
                    cod_c_alvo = item_cons_sel.split(" - ")[0].strip()
                    row_c_alvo = df_est_view[df_est_view['codigo'] == cod_c_alvo].iloc[0]
                    if qtd_cons_baixa > limpar_int(row_c_alvo['quantidade'], 0):
                        st.error("⚠️ Quantidade superior ao saldo disponível em estoque!")
                    elif not finalidade_cons.strip():
                        st.error("⚠️ Informe a finalidade do consumo!")
                    else:
                        with get_db_connection(ctx.db_name) as conn_bc:
                            conn_bc.execute(
                                "UPDATE estoque_pecas SET quantidade = quantidade - ? WHERE codigo = ?",
                                (int(qtd_cons_baixa), cod_c_alvo)
                            )
                            conn_bc.execute("""
                                INSERT INTO baixas_consumiveis
                                (tecnico_setor, codigo_item, nome_item, quantidade, finalidade, data_baixa)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                setor_tec_cons.strip().upper(), cod_c_alvo, row_c_alvo['nome_peca'],
                                int(qtd_cons_baixa), finalidade_cons.strip().upper(),
                                datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                            ))
                        st.cache_data.clear()
                        st.success("✅ Baixa de consumível registada com sucesso!")
                        st.rerun()

        st.markdown("###### 📜 Histórico de Consumo Interno")
        st.dataframe(carregar_baixas_consumiveis(ctx.db_name), use_container_width=True, hide_index=True)
