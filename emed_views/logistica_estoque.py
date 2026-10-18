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

    st.markdown("### 📦 Formulário de Solicitação de Peças, Consumíveis e Instrumentos")
    st.info(
        "Marque os itens necessários para o atendimento. O sistema valida e reserva as quantidades "
        "online na base de dados em tempo real para impedir conflitos entre técnicos."
    )

    df_est_atual = carregar_estoque(ctx.db_name)
    lista_t_sol = sorted(list(equipa_tecnica.keys()))
    clientes_sol = sorted([c for c in df['cliente'].unique() if str(c).strip() != '' and "NENHUM" not in str(c).upper()])

    with st.form("form_solicitacao_almoxarifado"):
        c_sol1, c_sol2 = st.columns(2)
        with c_sol1:
            usr_sol_up = ctx.usuario_atual.upper()
            idx_sol_u = lista_t_sol.index(usr_sol_up) if usr_sol_up in lista_t_sol else 0
            tec_solicitante = st.selectbox("Técnico Solicitante", lista_t_sol, index=idx_sol_u)
        with c_sol2:
            cli_destino_sol = st.selectbox("Hospital / Cliente ou Setor de Destino", ["USO GERAL / VIATURA"] + clientes_sol)

        st.markdown("#### ☑️ Ticagem de Materiais e Peças Disponíveis em Estoque")
        itens_ticados = []
        if df_est_atual.empty:
            st.warning("Nenhum item registado no estoque.")
        else:
            for _, r_item in df_est_atual.iterrows():
                cod_i = r_item['codigo']
                nome_i = r_item['nome_peca']
                qtd_disp_i = limpar_int(r_item.get('quantidade'), 0)
                tipo_i = limpar_texto(r_item.get('tipo_item'), 'PEÇA COMERCIAL (OS)')

                c_it1, c_it2 = st.columns([3.5, 1])
                with c_it1:
                    marcado = st.checkbox(
                        f"[{cod_i}] {nome_i} — ({tipo_i}) | Saldo Online: {qtd_disp_i} un.",
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

        instrumentos_extras_sol = st.text_area(
            "📐 Instrumentos de Medição / Ferramentas Especiais Solicitadas",
            placeholder="EX: ANALISADOR DE RAIOS-X, MULTÍMETRO FLUKE, MALA DE FERRAMENTAS 02..."
        )

        if st.form_submit_button("🚀 Confirmar Reserva no Estoque & Enviar ao Almoxarifado", type="primary"):
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
                            "RESERVADO / ENVIADO AO ESTOQUE", data_ped_agora
                        ))

                if erro_conflito:
                    st.error(erro_conflito)
                else:
                    st.cache_data.clear()
                    inst_txt_msg = instrumentos_extras_sol.strip().upper() if instrumentos_extras_sol.strip() else 'NENHUM'
                    msg_almox = (
                        f"📦 *NOVA SOLICITAÇÃO DE MATERIAL & INSTRUMENTOS - EMED*\n\n"
                        f"👨‍🔧 *Técnico:* {tec_solicitante}\n"
                        f"🏥 *Destino:* {cli_destino_sol}\n"
                        f"📅 *Data/Hora:* {data_ped_agora}\n\n"
                        f"🛠️ *Materiais Reservados no Sistema:*\n{resumo_itens_str}\n\n"
                        f"📐 *Instrumentos Solicitados:*\n{inst_txt_msg}\n"
                    )
                    link_wpp_est = f"https://wa.me/558593333333?text={urllib.parse.quote(msg_almox)}"
                    st.success("✅ Estoque atualizado em tempo real! Os itens foram reservados para si.")
                    st.markdown(f"""
                        <a href="{link_wpp_est}" target="_blank" style="background:#25d366; color:white; padding:12px 24px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block; margin-top:8px;">
                            📲 Enviar Mensagem de Separação para o Estoque (WhatsApp)
                        </a>
                    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📋 Histórico Recente & Gestão Circular de Reservas do Almoxarifado")
    df_sol_hist = carregar_solicitacoes(ctx.db_name)
    st.dataframe(df_sol_hist, use_container_width=True, hide_index=True)

    if not df_sol_hist.empty:
        with st.expander("🔄 Gerir Status de Reserva (Confirmar Entrega / Aplicação ou Estornar Peças ao Estoque)"):
            with st.form("form_gestao_status_reserva"):
                opcoes_ped = [
                    f"#{r['id']} | {r['tecnico']} -> {r['destino_cliente']} ({r['itens_solicitados']}) [{r['status_pedido']}]"
                    for _, r in df_sol_hist.iterrows()
                ]
                ped_escolhido = st.selectbox("Selecione o Pedido de Reserva:", opcoes_ped)
                novo_st_ped = st.selectbox(
                    "Nova Situação do Pedido:",
                    [
                        "ENTREGUE / APLICADO EM CAMPO",
                        "CANCELADO / ESTORNADO (DEVOLVIDO AO ESTOQUE)",
                        "RESERVADO / ENVIADO AO ESTOQUE"
                    ]
                )
                if st.form_submit_button("💾 Atualizar Status da Reserva", type="primary"):
                    id_ped_alvo = int(ped_escolhido.split("|")[0].replace("#", "").strip())
                    ok_st, msg_st = atualizar_status_solicitacao_peca(ctx.db_name, id_ped_alvo, novo_st_ped)
                    if ok_st:
                        st.cache_data.clear()
                        st.success(msg_st)
                        st.rerun()
                    else:
                        st.error(msg_st)


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
    st.markdown("### 📦 Controlo do Almoxarifado, Peças Comerciais & Consumíveis Internos EMED")

    st.markdown("#### 📋 Listagem Geral de Peças e Consumíveis em Almoxarifado")
    df_est_view = carregar_estoque(ctx.db_name)
    if df_est_view.empty:
        st.info("Nenhuma peça registada no estoque.")
    else:
        df_est_mostra = df_est_view.copy()
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
