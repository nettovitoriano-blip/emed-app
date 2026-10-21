import io
import urllib.parse
import pandas as pd
import streamlit as st
from emed_core import limpar_texto, get_db_connection
from emed_services import (
    AppContext,
    carregar_clientes_internos,
    obter_icone_equipamento,
    salvar_dados_seguro,
)


def render_clientes_equipamentos(ctx: AppContext):
    df = ctx.df

    st.markdown("### 📋 Gestão de Clientes (Hospitais Externos, Setores Internos & QR Code de Equipamentos)")

    tipo_visao_cli = st.radio(
        "Selecione o Módulo de Clientes:",
        [
            "🏥 Hospitais / Matrizes & Unidades (Externos)",
            "🏢 Clientes Internos (Estoque, Financeiro, Infraestrutura, etc.)"
        ],
        horizontal=True
    )
    st.markdown("---")

    if tipo_visao_cli == "🏢 Clientes Internos (Estoque, Financeiro, Infraestrutura, etc.)":
        st.markdown("#### 🏢 Setores / Clientes Internos da EMED")
        df_int_atual = carregar_clientes_internos(ctx.db_name)
        st.dataframe(df_int_atual, use_container_width=True, hide_index=True)

        if "mostrar_form_setor" not in st.session_state:
            st.session_state.mostrar_form_setor = False
        if st.button("➕ Adicionar / Editar Setor Interno"):
            st.session_state.mostrar_form_setor = not st.session_state.mostrar_form_setor
            st.rerun()

        if st.session_state.mostrar_form_setor:
            with st.form("form_cadastro_setor_interno"):
                lista_setores_nomes = list(df_int_atual['nome_setor']) if not df_int_atual.empty else []
                opcoes_setor_ed = ["➕ NOVO SETOR INTERNO"] + lista_setores_nomes
                setor_sel_ed = st.selectbox("Selecione para Editar (ou Novo)", opcoes_setor_ed)
                if setor_sel_ed != "➕ NOVO SETOR INTERNO":
                    row_si = df_int_atual[df_int_atual['nome_setor'] == setor_sel_ed].iloc[0]
                else:
                    row_si = None

                si_nome = st.text_input(
                    "Nome do Setor Interno *",
                    value=row_si['nome_setor'] if row_si is not None else "",
                    placeholder="EX: INFRAESTRUTURA & FROTA"
                )
                si_resp = st.text_input(
                    "Responsável pelo Setor *",
                    value=row_si['responsavel'] if row_si is not None else "",
                    placeholder="EX: PAULINHO"
                )
                si_wpp = st.text_input(
                    "WhatsApp / Ramal",
                    value=limpar_texto(row_si['ramal_whatsapp'] if row_si is not None else ""),
                    placeholder="5585999999999"
                )
                si_cc = st.text_input(
                    "Código Centro de Custo",
                    value=limpar_texto(row_si['centro_custo'] if row_si is not None else ""),
                    placeholder="CC-INF-03"
                )
                si_obs = st.text_input(
                    "Observações / Atribuições",
                    value=limpar_texto(row_si.get('observacoes', '') if row_si is not None else "")
                )

                c_si1, c_si2 = st.columns(2)
                with c_si1:
                    btn_sv_si = st.form_submit_button("💾 Guardar Setor Interno", type="primary")
                with c_si2:
                    btn_del_si = st.form_submit_button("🗑️ Excluir Setor Interno")

                if btn_sv_si and si_nome and si_resp:
                    with get_db_connection(ctx.db_name) as conn_si:
                        conn_si.execute("""
                            INSERT OR REPLACE INTO clientes_internos
                            (nome_setor, responsavel, ramal_whatsapp, centro_custo, observacoes)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            si_nome.strip().upper(), si_resp.strip().upper(),
                            si_wpp.strip(), si_cc.strip().upper(), si_obs.strip().upper()
                        ))
                    st.cache_data.clear()
                    st.session_state.mostrar_form_setor = False
                    st.success("✅ Setor Interno guardado com sucesso!")
                    st.rerun()

                if btn_del_si and row_si is not None:
                    with get_db_connection(ctx.db_name) as conn_si:
                        conn_si.execute("DELETE FROM clientes_internos WHERE nome_setor = ?", (row_si['nome_setor'],))
                    st.cache_data.clear()
                    st.session_state.mostrar_form_setor = False
                    st.success("🗑️ Setor Interno removido!")
                    st.rerun()

    else:
        with st.expander("🏢 Registar Nova Matriz / Grupo Faturado"):
            with st.form("form_nova_matriz"):
                c_mat1, c_mat2 = st.columns(2)
                with c_mat1:
                    matriz_nome = st.text_input("Nome do Grupo / Matriz *", placeholder="EX: GRUPO HOSPITALAR SÃO LUIZ")
                    matriz_cnpj = st.text_input("CNPJ (Matriz) *", placeholder="00.000.000/0001-00")
                    matriz_email = st.text_input("E-mail Financeiro / Gestão", placeholder="financeiro@hospitalsluiz.com")
                    matriz_regime = st.selectbox("Regime Comercial", ["CONTRATO", "AVULSO"])
                with c_mat2:
                    matriz_whatsapp = st.text_input("WhatsApp / Telefone Principal", placeholder="5585999999999")
                    matriz_cep = st.text_input("CEP Fiscal", placeholder="60000-000")
                    matriz_endereco = st.text_input("Endereço Fiscal Completo *", placeholder="AV. EXPEDICIONÁRIOS, 1000 - FORTALEZA/CE")

                btn_salvar_matriz = st.form_submit_button("💾 Salvar Nova Matriz / Grupo")
                if btn_salvar_matriz:
                    if not matriz_nome or not matriz_cnpj or not matriz_endereco:
                        st.error("⚠️ Preencha o Nome do Grupo, CNPJ e Endereço Fiscal!")
                    else:
                        nova_matriz_linha = {
                            'cliente': matriz_nome.strip().upper(),
                            'cidade': 'MATRIZ / GERAL',
                            'estado': 'CE',
                            'equipamento': 'NENHUM (AGUARDANDO UNIDADE)',
                            'endereco': matriz_endereco.strip().upper(),
                            'tipo_servico': 'PREVENTIVA',
                            'tecnico_responsavel': 'A DEFINIR',
                            'confirmado': 'NÃO',
                            'pendencias': 'CADASTRO DE MATRIZ EFETUADO',
                            'status': 'ATIVO',
                            'cnpj': matriz_cnpj.strip(),
                            'cep': matriz_cep.strip(),
                            'email': matriz_email.strip().upper(),
                            'whatsapp': matriz_whatsapp.strip(),
                            'endereco_fiscal': matriz_endereco.strip().upper(),
                            'tipo_contrato': matriz_regime
                        }
                        df = pd.concat([df, pd.DataFrame([nova_matriz_linha])], ignore_index=True)
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success(f"✅ Matriz '{matriz_nome.strip().upper()}' registada com sucesso!")
                            st.rerun()

        with st.expander("➕ Adicionar Unidade Operacional (Hospital/Clínica) & Equipamento"):
            lista_matrizes = sorted([c for c in df['cliente'].unique() if str(c).strip() != ''])
            with st.form("form_add_unidade_equipamento"):
                matriz_vinculada = st.selectbox("1. Selecionar Grupo / Matriz Faturada *", lista_matrizes)

                c_un1, c_un2 = st.columns(2)
                with c_un1:
                    unidade_nome = st.text_input("2. Nome da Unidade / Filial *", placeholder="EX: HOSPITAL SÃO LUIZ - UNIDADE MOSSORÓ")
                    unidade_cidade = st.text_input("3. Cidade da Unidade *", placeholder="MOSSORÓ")
                    unidade_estado = st.text_input("4. Estado (UF) *", value="RN")
                with c_un2:
                    unidade_endereco = st.text_input("5. Endereço Específico (para o Waze/Maps) *", placeholder="RUA DAS FLORES, 123 - CENTRO")
                    unidade_resp = st.text_input("6. Responsável na Unidade", placeholder="DR. CARLOS")
                    unidade_tel_resp = st.text_input("7. Contacto / WhatsApp da Unidade", placeholder="5584988888888")

                st.markdown("---")
                st.markdown("##### ⚙️ Dados do Equipamento Médico")
                eq_tipo_escolha = st.selectbox(
                    "Tipo de Equipamento *",
                    ["TOMÓGRAFO", "RAIO-X", "DENSITOMETRIA ÓSSEA", "MAMÓGRAFO", "MICRÓTOMO / PATOLOGIA", "OUTROS"]
                )
                eq_tipo_aparelho = eq_tipo_escolha
                if eq_tipo_escolha == "OUTROS":
                    eq_tipo_aparelho = st.text_input("Especifique o Aparelho *")

                eq_modelo = st.text_input("Fabricante / Modelo *", placeholder="EX: GE BRIGHTSPEED 16 CANAIS")

                c_eq1, c_eq2 = st.columns(2)
                with c_eq1:
                    eq_ns = st.text_input("Número de Série (N/S)")
                    eq_fabricacao = st.text_input("Ano de Fabricação")
                with c_eq2:
                    eq_local = st.text_input("Localização Física (Ex: Sala de Tomografia, UTI)")
                    eq_status_ativo = st.selectbox(
                        "Status Operacional",
                        ["EM FUNCIONAMENTO", "PARADO", "EM MANUTENÇÃO", "FAZER VISTORIA", "DESATIVADO"]
                    )

                eq_obs = st.text_area("Observações / Notas Técnicas")

                btn_salvar_unidade_eq = st.form_submit_button("💾 Registar Unidade & Equipamento")
                if btn_salvar_unidade_eq:
                    if not unidade_nome or not unidade_endereco or not eq_modelo:
                        st.error("⚠️ Preencha a Unidade, o Endereço e o Fabricante/Modelo do Equipamento!")
                    else:
                        cliente_final_os = f"{matriz_vinculada} - {unidade_nome.strip().upper()}"

                        nome_aparelho_final = (eq_tipo_aparelho if eq_tipo_escolha != "OUTROS" else eq_tipo_aparelho.strip()).upper()
                        desc_equipamento = f"{nome_aparelho_final} - {eq_modelo.strip().upper()}"

                        detalhes_extras = []
                        if eq_ns.strip():
                            detalhes_extras.append(f"N/S: {eq_ns.strip().upper()}")
                        if eq_fabricacao.strip():
                            detalhes_extras.append(f"Fab: {eq_fabricacao.strip().upper()}")
                        if eq_local.strip():
                            detalhes_extras.append(f"Local: {eq_local.strip().upper()}")
                        if eq_status_ativo:
                            detalhes_extras.append(f"Status: {eq_status_ativo}")

                        if detalhes_extras:
                            desc_equipamento += f" [{' | '.join(detalhes_extras)}]"

                        obs_final = eq_obs.strip().upper() if eq_obs.strip() else "SEM PENDENCIAS APARENTES"
                        matriz_info = df[df['cliente'] == matriz_vinculada].iloc[0]

                        nova_unidade_eq = {
                            'cliente': cliente_final_os,
                            'cidade': unidade_cidade.strip().upper(),
                            'estado': unidade_estado.strip().upper(),
                            'equipamento': desc_equipamento,
                            'endereco': unidade_endereco.strip().upper(),
                            'tipo_servico': 'PREVENTIVA',
                            'data_agendamento': None,
                            'tecnico_responsavel': 'A DEFINIR',
                            'telefone_tecnico': '',
                            'responsavel_hospital': unidade_resp.strip().upper() if unidade_resp else 'NÃO INFORMADO',
                            'contato_responsavel': unidade_tel_resp.strip(),
                            'confirmado': 'NÃO',
                            'pendencias': obs_final,
                            'status': 'ATIVO',
                            'cnpj': limpar_texto(matriz_info.get('cnpj')),
                            'cep': limpar_texto(matriz_info.get('cep')),
                            'email': limpar_texto(matriz_info.get('email')),
                            'whatsapp': limpar_texto(matriz_info.get('whatsapp')),
                            'endereco_fiscal': limpar_texto(matriz_info.get('endereco_fiscal')),
                            'tipo_contrato': limpar_texto(matriz_info.get('tipo_contrato'), 'CONTRATO')
                        }
                        df = pd.concat([df, pd.DataFrame([nova_unidade_eq])], ignore_index=True)
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success(f"✅ Unidade '{unidade_nome.strip().upper()}' e equipamento adicionados com sucesso!")
                            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        clientes_agrupados = sorted(list(df.groupby('cliente')), key=lambda x: x[0])
        colunas_cards = st.columns(2)
        card_idx = 0

        for cliente_nome, grupo in clientes_agrupados:
            if not str(cliente_nome).strip() or "NENHUM (AGUARDANDO" in str(cliente_nome).upper():
                continue
            col_atual = colunas_cards[card_idx % 2]
            primeira_linha = grupo.iloc[0]
            cidade = limpar_texto(primeira_linha.get('cidade'), '').upper()
            estado = limpar_texto(primeira_linha.get('estado'), '').upper()
            resp = limpar_texto(primeira_linha.get('responsavel_hospital'), 'Não informado').upper()
            tel_resp = limpar_texto(primeira_linha.get('contato_responsavel'), '')
            endereco = limpar_texto(primeira_linha.get('endereco'), f"{cidade} - {estado}").upper()
            cnpj_cli = limpar_texto(primeira_linha.get('cnpj'), 'N/D')

            equipamentos_validos = grupo[~grupo['equipamento'].astype(str).str.contains("Nenhum|Aguardando", case=False, na=False)]
            qtd_equipamentos = len(equipamentos_validos)

            with col_atual:
                st.markdown(f"""
                    <div class="client-card">
                        <h3>🏥 {cliente_nome}</h3>
                        <p>🏢 <strong>CNPJ:</strong> {cnpj_cli}</p>
                        <p>📍 <strong>Local / Cidade:</strong> {cidade} - {estado}</p>
                        <p>🏠 <strong>Endereço Operacional:</strong> {endereco}</p>
                        <p>👤 <strong>Contacto Local:</strong> {resp} ({tel_resp})</p>
                    </div>
                """, unsafe_allow_html=True)

                with st.expander(f"⚙️ Ver Equipamentos & QR Codes ({qtd_equipamentos} registados)"):
                    if equipamentos_validos.empty:
                        st.info("Nenhum equipamento registado nesta unidade.")
                    else:
                        for i_eq, r_eq in equipamentos_validos.iterrows():
                            eq_desc = limpar_texto(r_eq.get('equipamento'), '').upper()
                            icone = obter_icone_equipamento(eq_desc)

                            col_eq_txt, col_eq_qr, col_eq_ed, col_eq_del = st.columns([5, 1.5, 1.2, 1.2])
                            with col_eq_txt:
                                st.markdown(f"{icone} **{eq_desc}**")
                            with col_eq_qr:
                                if st.button("📱 QR", key=f"btn_qr_{i_eq}"):
                                    st.session_state[f"ver_qr_{i_eq}"] = not st.session_state.get(f"ver_qr_{i_eq}", False)
                            with col_eq_ed:
                                if st.button("✏️", key=f"btn_edit_{i_eq}"):
                                    st.session_state[f"editando_{i_eq}"] = True
                            with col_eq_del:
                                if st.button("🗑️", key=f"btn_del_{i_eq}"):
                                    df = df.drop(i_eq)
                                    if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                                        st.cache_data.clear()
                                        st.success("Equipamento excluído com sucesso!")
                                        st.rerun()

                            if st.session_state.get(f"ver_qr_{i_eq}", False):
                                q_eq = urllib.parse.quote(eq_desc)
                                q_cli = urllib.parse.quote(cliente_nome)
                                url_portal_qr = f"http://localhost:8501/?equipamento_qr={q_eq}&cliente_qr={q_cli}"
                                try:
                                    import qrcode
                                    qr_obj = qrcode.QRCode(version=1, box_size=6, border=2)
                                    qr_obj.add_data(url_portal_qr)
                                    qr_obj.make(fit=True)
                                    img_qr = qr_obj.make_image(fill_color="#0B3B60", back_color="white")
                                    buf = io.BytesIO()
                                    img_qr.save(buf, format="PNG")
                                    st.image(buf.getvalue(), width=150)
                                except Exception:
                                    img_qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={urllib.parse.quote(url_portal_qr)}"
                                    st.image(img_qr_api, width=150)
                                st.caption("📱 Etiqueta QR Code do Equipamento (Histórico de OS + Abertura de Chamado).")
                                if st.button("👁️ Testar Visão do Cliente (Abrir Portal QR)", key=f"sim_qr_{i_eq}"):
                                    st.session_state.simulando_qr_eq = eq_desc
                                    st.session_state.simulando_qr_cli = cliente_nome
                                    st.rerun()

                            if st.session_state.get(f"editando_{i_eq}", False):
                                with st.form(f"form_edit_{i_eq}"):
                                    novo_texto_eq = st.text_input("Editar Equipamento / Detalhes", value=eq_desc)
                                    col_sb1, col_sb2 = st.columns(2)
                                    with col_sb1:
                                        btn_salvar_ed = st.form_submit_button("💾 Salvar Alteração")
                                    with col_sb2:
                                        btn_cancelar_ed = st.form_submit_button("❌ Cancelar")

                                    if btn_salvar_ed:
                                        df.at[i_eq, 'equipamento'] = novo_texto_eq.strip().upper()
                                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                                            st.session_state[f"editando_{i_eq}"] = False
                                            st.cache_data.clear()
                                            st.success("Equipamento atualizado!")
                                            st.rerun()
                                    if btn_cancelar_ed:
                                        st.session_state[f"editando_{i_eq}"] = False
                                        st.rerun()
            card_idx += 1
