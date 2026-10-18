import os
import streamlit as st
from emed_core import limpar_texto, limpar_int, get_db_connection
from emed_services import (
    AppContext,
    carregar_tecnicos,
    carregar_veiculos,
    salvar_dados_seguro,
)


def render_gestao_administracao(ctx: AppContext):
    if ctx.perfil_atual != "Gestor":
        st.warning("⚠️ Acesso restrito ao perfil Gestor.")
        return

    st.markdown("### ⚙️ Painel de Gestão & Administração")
    sub_gestao = st.radio(
        "Selecione o módulo:",
        ["👷 Gestão de Técnicos", "🚗 Gestão de Veículos & Quilometragem"],
        horizontal=True
    )
    st.markdown("---")

    if sub_gestao == "👷 Gestão de Técnicos":
        st.markdown("#### 📋 Equipa Técnica Registada")
        df_tecs_adm = carregar_tecnicos(ctx.db_name)
        st.dataframe(df_tecs_adm, use_container_width=True, hide_index=True)

        st.markdown("---")

        if "abrir_painel_tecnico" not in st.session_state:
            st.session_state.abrir_painel_tecnico = False

        if st.button("➕ Adicionar / Editar ou Excluir Técnico"):
            st.session_state.abrir_painel_tecnico = not st.session_state.abrir_painel_tecnico
            st.rerun()

        if st.session_state.abrir_painel_tecnico:
            st.markdown("#### ✍️ Cadastro e Edição de Técnico")
            lista_nomes_adm = df_tecs_adm['nome'].tolist() if not df_tecs_adm.empty else []
            opcoes_tec_edicao = ["➕ CADASTRAR NOVO TÉCNICO"] + lista_nomes_adm
            tec_escolhido_edicao = st.selectbox(
                "Selecione o Técnico que deseja Editar (ou escolha '➕ CADASTRAR NOVO TÉCNICO'):",
                opcoes_tec_edicao
            )

            dados_tec_ed = None
            if tec_escolhido_edicao != "➕ CADASTRAR NOVO TÉCNICO":
                dados_tec_ed = df_tecs_adm[df_tecs_adm['nome'] == tec_escolhido_edicao].iloc[0]

            with st.form("form_cad_ed_tecnico"):
                ct1, ct2 = st.columns(2)
                with ct1:
                    t_nome = st.text_input(
                        "Nome do Técnico *",
                        value=limpar_texto(dados_tec_ed['nome']) if dados_tec_ed is not None else ""
                    ).upper()
                    t_tel = st.text_input(
                        "Telemóvel / WhatsApp (ex: 5585988888888)",
                        value=limpar_texto(dados_tec_ed['telefone']) if dados_tec_ed is not None else ""
                    )
                    t_partida = st.text_input(
                        "Local de Partida",
                        value=limpar_texto(dados_tec_ed['partida']) if dados_tec_ed is not None else "FORTALEZA"
                    )
                with ct2:
                    t_sede = st.text_input(
                        "Sede / Base",
                        value=limpar_texto(dados_tec_ed['sede']) if dados_tec_ed is not None else "FORTALEZA"
                    )
                    t_senha = st.text_input(
                        "Palavra-passe / PIN",
                        type="password",
                        value=limpar_texto(dados_tec_ed['senha'], "1234") if dados_tec_ed is not None else "1234"
                    )
                    perf_atual = limpar_texto(dados_tec_ed['perfil'], "Técnico") if dados_tec_ed is not None else "Técnico"
                    t_perfil = st.selectbox(
                        "Perfil de Acesso",
                        ["Técnico", "Gestor"],
                        index=1 if perf_atual == "Gestor" else 0
                    )

                ass_val_def = limpar_texto(dados_tec_ed.get('assinatura_padrao', ''), f"{t_nome} - CFT") if dados_tec_ed is not None else ""
                t_assinatura = st.text_input("Assinatura Padrão / Registo CFT (Carimbo Automático na OS)", value=ass_val_def)
                t_rubrica_up = st.file_uploader("✍️ Anexar Imagem da Rubrica do Técnico (PNG/JPG - Opcional)", type=["png", "jpg", "jpeg"])

                c_bt1, c_bt2, c_bt3 = st.columns(3)
                with c_bt1:
                    btn_guardar_t = st.form_submit_button("💾 Guardar Técnico", type="primary")
                with c_bt2:
                    btn_excluir_t = st.form_submit_button("🗑️ Excluir Técnico Selecionado")
                with c_bt3:
                    btn_fechar_t = st.form_submit_button("❌ Fechar Formulário")

                if btn_guardar_t:
                    if not t_nome.strip():
                        st.error("⚠️ O nome do técnico é obrigatório!")
                    else:
                        caminho_rub_tec = limpar_texto(dados_tec_ed.get('rubrica_img', '')) if dados_tec_ed is not None else ""
                        if t_rubrica_up is not None:
                            pasta_rub = os.path.join(ctx.base_dir, "uploads_os")
                            os.makedirs(pasta_rub, exist_ok=True)
                            caminho_rub_tec = os.path.join(pasta_rub, f"RUBRICA_{t_nome.strip().upper()}_{t_rubrica_up.name}")
                            with open(caminho_rub_tec, "wb") as f:
                                f.write(t_rubrica_up.getbuffer())

                        ass_final_t = t_assinatura.strip().upper() or f"{t_nome.strip().upper()} - CFT"
                        with get_db_connection(ctx.db_name) as conn_t:
                            cur_t = conn_t.cursor()
                            if dados_tec_ed is not None and dados_tec_ed['nome'] != t_nome.strip().upper():
                                cur_t.execute("DELETE FROM tecnicos WHERE nome = ?", (dados_tec_ed['nome'],))
                            cur_t.execute("""
                                INSERT OR REPLACE INTO tecnicos
                                (nome, telefone, partida, sede, senha, perfil, assinatura_padrao, rubrica_img)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                t_nome.strip().upper(), t_tel.strip(),
                                t_partida.strip().upper(), t_sede.strip().upper(),
                                t_senha.strip(), t_perfil, ass_final_t, caminho_rub_tec
                            ))
                        st.cache_data.clear()
                        st.session_state.abrir_painel_tecnico = False
                        st.success(f"✅ Salvo com sucesso! Técnico '{t_nome.strip().upper()}' e rubrica guardados!")
                        st.rerun()

                if btn_excluir_t and dados_tec_ed is not None:
                    with get_db_connection(ctx.db_name) as conn_t:
                        conn_t.execute("DELETE FROM tecnicos WHERE nome = ?", (dados_tec_ed['nome'],))
                    st.cache_data.clear()
                    st.success(f"🗑️ Técnico '{dados_tec_ed['nome']}' excluído com sucesso!")
                    st.rerun()

                if btn_fechar_t:
                    st.session_state.abrir_painel_tecnico = False
                    st.rerun()

    elif sub_gestao == "🚗 Gestão de Veículos & Quilometragem":
        st.markdown("#### 🚗 Frota de Veículos EMED, Fotos & Registos de Manutenção")
        df_v_list = carregar_veiculos(ctx.db_name)
        st.dataframe(df_v_list, use_container_width=True, hide_index=True)

        if not df_v_list.empty:
            cols_v_cards = st.columns(2)
            for idx_vc, r_vc in df_v_list.iterrows():
                with cols_v_cards[idx_vc % 2]:
                    km_at_v = limpar_int(r_vc.get('km_atual'), 0)
                    km_ul_v = limpar_int(r_vc.get('km_ultima_revisao'), 0)
                    km_pr_v = limpar_int(r_vc.get('km_proxima_revisao'), 50000)
                    alerta_rev = "🚨 REVISÃO VENCIDA / URGENTE" if km_at_v >= km_pr_v else f"🟢 Faltam {km_pr_v - km_at_v} KM p/ revisão"
                    mod_v_lbl = limpar_texto(r_vc.get('modelo'))
                    plc_v_lbl = limpar_texto(r_vc.get('placa'))
                    st_v_lbl = limpar_texto(r_vc.get('status_manutencao'), 'Disponível')
                    hm_v_lbl = limpar_texto(r_vc.get('historico_manutencao'), 'Sem registos')
                    pm_v_lbl = limpar_texto(r_vc.get('proximas_manutencoes'), 'Revisão periódica padrão')

                    st.markdown(f"""
                        <div class="client-card">
                            <h3>🚗 {mod_v_lbl} — Placa: {plc_v_lbl}</h3>
                            <p>🛣️ <strong>KM Atual:</strong> {km_at_v:,} KM | <strong>Última Revisão:</strong> {km_ul_v:,} KM</p>
                            <p>🔔 <strong>Próxima Revisão ({km_pr_v:,} KM):</strong> {alerta_rev}</p>
                            <p>🛠️ <strong>Status:</strong> {st_v_lbl}</p>
                            <p>📋 <strong>Histórico de Manutenções:</strong> {hm_v_lbl}</p>
                            <p>📅 <strong>Próximas Manutenções Programadas:</strong> {pm_v_lbl}</p>
                        </div>
                    """, unsafe_allow_html=True)
                    caminho_foto_v = limpar_texto(r_vc.get('foto_carro'), '')
                    if caminho_foto_v and os.path.exists(caminho_foto_v):
                        st.image(caminho_foto_v, caption=f"{mod_v_lbl} ({plc_v_lbl})", width=280)

        st.markdown("---")

        if "abrir_painel_veiculo" not in st.session_state:
            st.session_state.abrir_painel_veiculo = False

        if st.button("➕ Adicionar / Editar ou Excluir Veículo"):
            st.session_state.abrir_painel_veiculo = not st.session_state.abrir_painel_veiculo
            st.rerun()

        if st.session_state.abrir_painel_veiculo:
            st.markdown("#### ✍️ Registo Completo de Veículo, Fotos e Manutenções")
            if not df_v_list.empty:
                lista_veic_fmt = (df_v_list['modelo'] + " (" + df_v_list['placa'] + ")").tolist()
                opcoes_veic_ed = ["➕ CADASTRAR NOVO VEÍCULO"] + lista_veic_fmt
            else:
                opcoes_veic_ed = ["➕ CADASTRAR NOVO VEÍCULO"]

            veiculo_escolhido_ed = st.selectbox(
                "Selecione o Veículo para Editar/Excluir (ou '➕ CADASTRAR NOVO VEÍCULO'):",
                opcoes_veic_ed
            )

            v_atual_row = None
            if veiculo_escolhido_ed != "➕ CADASTRAR NOVO VEÍCULO":
                placa_sel = veiculo_escolhido_ed.split("(")[-1].replace(")", "").strip()
                v_atual_row = df_v_list[df_v_list['placa'] == placa_sel].iloc[0]

            with st.form("form_gestao_frota_completa"):
                cv1, cv2 = st.columns(2)
                with cv1:
                    v_mod = st.text_input(
                        "Modelo do Veículo *",
                        value=limpar_texto(v_atual_row['modelo']) if v_atual_row is not None else "",
                        placeholder="EX: RENAULT CAPTUR 1.6 16V SCE"
                    )
                    v_plc = st.text_input(
                        "Placa *",
                        value=limpar_texto(v_atual_row['placa']) if v_atual_row is not None else "",
                        placeholder="EX: EMD-2026"
                    )
                    val_km_at = limpar_int(v_atual_row['km_atual'], 45000) if v_atual_row is not None else 45000
                    v_km_at = st.number_input("Quilometragem Atual (KM)", min_value=0, value=val_km_at, step=100)
                    v_status_m = st.selectbox(
                        "Status Operacional",
                        ["Disponível", "Em Viagem / Campo", "Em Revisão / Oficina", "Indisponível"],
                        index=0
                    )
                with cv2:
                    val_km_ul = limpar_int(v_atual_row.get('km_ultima_revisao'), 40000) if v_atual_row is not None else 40000
                    val_km_pr = limpar_int(v_atual_row.get('km_proxima_revisao'), 50000) if v_atual_row is not None else 50000
                    v_km_ult = st.number_input("KM da Última Revisão", min_value=0, value=val_km_ul, step=500)
                    v_km_prox = st.number_input("KM da Próxima Revisão", min_value=0, value=val_km_pr, step=500)
                    v_foto_up = st.file_uploader("📸 Anexar / Atualizar Foto do Carro (PNG/JPG)", type=["png", "jpg", "jpeg"])

                v_hist_manut = st.text_area(
                    "🔧 Registo de Manutenções Realizadas (Peças trocadas, datas, oficina/mecânico)",
                    value=limpar_texto(v_atual_row.get('historico_manutencao', '')) if v_atual_row is not None else "",
                    placeholder="EX: 10/2026 - TROCA DE ÓLEO, FILTROS, VELAS E CORREIA COM MECÂNICO CÍCERO..."
                )
                v_prox_manut = st.text_area(
                    "📅 Próximas Manutenções Programadas / Alertas da Viatura",
                    value=limpar_texto(v_atual_row.get('proximas_manutencoes', '')) if v_atual_row is not None else "",
                    placeholder="EX: VERIFICAR PASTILHAS DE TRAVÃO E ALINHAMENTO AOS 50.000 KM..."
                )

                cbv1, cbv2, cbv3 = st.columns(3)
                with cbv1:
                    btn_salvar_v = st.form_submit_button("💾 Guardar Dados do Veículo", type="primary")
                with cbv2:
                    btn_excluir_v = st.form_submit_button("🗑️ Excluir Veículo da Frota")
                with cbv3:
                    btn_fechar_v = st.form_submit_button("❌ Fechar Formulário")

                if btn_salvar_v:
                    if not v_mod.strip() or not v_plc.strip():
                        st.error("⚠️ O Modelo e a Placa do veículo são obrigatórios!")
                    else:
                        caminho_foto_carro = limpar_texto(v_atual_row.get('foto_carro', '')) if v_atual_row is not None else ""
                        if v_foto_up is not None:
                            pasta_veiculos = os.path.join(ctx.base_dir, "uploads_veiculos")
                            os.makedirs(pasta_veiculos, exist_ok=True)
                            caminho_foto_carro = os.path.join(pasta_veiculos, f"{v_plc.strip().upper()}_{v_foto_up.name}")
                            with open(caminho_foto_carro, "wb") as f:
                                f.write(v_foto_up.getbuffer())

                        with get_db_connection(ctx.db_name) as conn_up:
                            cur_up = conn_up.cursor()
                            if v_atual_row is not None and v_atual_row['placa'] != v_plc.strip().upper():
                                cur_up.execute("DELETE FROM veiculos WHERE placa = ?", (v_atual_row['placa'],))
                            cur_up.execute("""
                                INSERT OR REPLACE INTO veiculos
                                (modelo, placa, km_atual, km_ultima_revisao, km_proxima_revisao, status_manutencao, foto_carro, historico_manutencao, proximas_manutencoes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                v_mod.strip().upper(), v_plc.strip().upper(),
                                int(v_km_at), int(v_km_ult), int(v_km_prox),
                                v_status_m, caminho_foto_carro,
                                v_hist_manut.strip().upper(), v_prox_manut.strip().upper()
                            ))
                        st.cache_data.clear()
                        st.success(f"✅ Veículo '{v_mod.strip().upper()} ({v_plc.strip().upper()})' guardado com sucesso!")
                        st.rerun()

                if btn_excluir_v and v_atual_row is not None:
                    with get_db_connection(ctx.db_name) as conn_del_v:
                        conn_del_v.execute("DELETE FROM veiculos WHERE placa = ?", (v_atual_row['placa'],))
                    st.cache_data.clear()
                    st.success(f"🗑️ Veículo '{v_atual_row['placa']}' removido da frota!")
                    st.rerun()

                if btn_fechar_v:
                    st.session_state.abrir_painel_veiculo = False
                    st.rerun()


def render_atualizar_km(ctx: AppContext):
    if ctx.perfil_atual != "Gestor":
        st.warning("⚠️ Acesso restrito ao perfil Gestor.")
        return

    st.markdown("### 🚗 Registo Rápido de Quilometragem")
    df_v = carregar_veiculos(ctx.db_name)
    if not df_v.empty:
        with st.form("form_km_opcional"):
            v_sel = st.selectbox("Veículo", df_v['modelo'] + " (" + df_v['placa'] + ")")
            km_inf = st.number_input("KM Atual", min_value=0, value=limpar_int(df_v.iloc[0]['km_atual'], 45000), step=100)
            if st.form_submit_button("🔄 Atualizar KM", type="primary"):
                placa_ext = v_sel.split("(")[-1].replace(")", "").strip()
                with get_db_connection(ctx.db_name) as conn_k:
                    conn_k.execute("UPDATE veiculos SET km_atual = ? WHERE placa = ?", (int(km_inf), placa_ext))
                st.cache_data.clear()
                st.success("✅ Quilometragem atualizada com sucesso!")
                st.rerun()


def render_editor_planilha(ctx: AppContext):
    if ctx.perfil_atual != "Gestor":
        st.warning("⚠️ Acesso restrito ao perfil Gestor.")
        return

    st.markdown("### 📝 Edição de Dados em Tempo Real")
    df_editado = st.data_editor(ctx.df, num_rows="dynamic", use_container_width=True)
    if st.button("💾 Guardar Alterações na Base", type="primary"):
        if salvar_dados_seguro(df_editado, ctx.db_name, ctx.caminho_excel):
            st.cache_data.clear()
            st.success("✅ Alterações gravadas com sucesso!")
            st.rerun()
