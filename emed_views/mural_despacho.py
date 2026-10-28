import datetime
import urllib.parse
import pandas as pd
import streamlit as st
from emed_core import limpar_texto, obter_id_os, acionar_separacao_automatica_almoxarifado
from emed_services import AppContext, salvar_dados_seguro


def render_mural_despacho(ctx: AppContext):
    df = ctx.df
    hoje = ctx.hoje
    equipa_tecnica = ctx.equipa_tecnica

    total_eq = len(df[~df['equipamento'].astype(str).str.contains("Nenhum|Aguardando", case=False, na=False)])
    count_alertas = 0
    count_confirmados = 0
    count_concluidos = len(df[df['status'].astype(str).str.upper() == 'CONCLUÍDO'])
    tecnicos_agenda = {}

    for _, row in df.iterrows():
        cliente = limpar_texto(row.get('cliente'), '').upper()
        cidade = limpar_texto(row.get('cidade'), '').upper()
        estado = limpar_texto(row.get('estado'), '').upper()
        equipamento = limpar_texto(row.get('equipamento'), '').upper()
        endereco = limpar_texto(row.get('endereco'), f"{cidade} - {estado}").upper()
        resp_cliente = limpar_texto(row.get('responsavel_hospital'), 'NÃO INFORMADO').upper()

        raw_tel = limpar_texto(row.get('contato_responsavel'), '')
        if raw_tel.endswith('.0'):
            raw_tel = raw_tel[:-2]
        tel_cliente = raw_tel

        raw_agend = row.get('data_agendamento', None)
        if pd.notna(raw_agend) and str(raw_agend).lower() not in ['nan', 'nat', 'none', '']:
            data_agend = pd.to_datetime(raw_agend, errors='coerce')
        else:
            data_agend = hoje
        if pd.isna(data_agend):
            data_agend = hoje

        tecnico_resp = limpar_texto(row.get('tecnico_responsavel'), 'A DEFINIR').upper()
        confirmado = limpar_texto(row.get('confirmado'), 'NÃO').upper()
        pendencias = limpar_texto(row.get('pendencias'), '').upper()
        instrumento = limpar_texto(row.get('instrumento_necessario'), '').upper()
        etapa_prev = limpar_texto(row.get('etapa_preventiva'), '').upper()
        tipo_srv = limpar_texto(row.get('tipo_servico'), 'PREVENTIVA').upper()

        query_mapa = urllib.parse.quote(f"{cliente} {endereco}")
        link_maps = f"https://www.google.com/maps/search/?api=1&query={query_mapa}"
        link_waze = f"https://waze.com/ul?q={query_mapa}&navigate=yes"

        if 0 <= (data_agend.normalize() - hoje).days <= 15:
            count_alertas += 1

        if confirmado.strip() in ["SIM", "YES", "S"]:
            count_confirmados += 1
            if tecnico_resp != 'A DEFINIR':
                if tecnico_resp not in tecnicos_agenda:
                    tecnicos_agenda[tecnico_resp] = []
                os_id_item = str(row.get('id', idx))
                tecnicos_agenda[tecnico_resp].append({
                    'id': os_id_item,
                    'cliente': cliente, 'cidade': cidade, 'estado': estado,
                    'equipamento': equipamento, 'data': data_agend, 'pendencias': pendencias,
                    'instrumento': instrumento, 'etapa_preventiva': etapa_prev,
                    'endereco': endereco, 'resp': resp_cliente, 'tel': tel_cliente,
                    'maps': link_maps, 'waze': link_waze, 'tipo_servico': tipo_srv
                })

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏥 Total de Equipamentos / OS", total_eq)
    k2.metric("⏰ Alertas Próximos (15d)", count_alertas)
    k3.metric("✅ Atendimentos Confirmados", count_confirmados)
    k4.metric("🏁 OS Concluídas", count_concluidos)

    st.markdown("---")
    st.markdown("### 💬 Despacho Consolidado para o WhatsApp dos Técnicos")

    if not tecnicos_agenda:
        st.warning("⚠️ Nenhum atendimento marcado como CONFIRMADO ('SIM') com técnico atribuído no momento.")
    else:
        if ctx.perfil_atual == "Gestor":
            itens_a_exibir = tecnicos_agenda.items()
        else:
            usr_up = ctx.usuario_atual.upper()
            itens_a_exibir = [(usr_up, tecnicos_agenda.get(usr_up, []))]

        mensagem_grupo_geral = "📢 *RESUMO CONSOLIDADO DE CHAMADOS CONFIRMADOS - EMED*\n\n"

        for tec, itens in itens_a_exibir:
            if not itens and ctx.perfil_atual != "Gestor":
                st.info(f"Olá {tec}, não existem atendimentos confirmados atribuídos a si no momento.")
                continue
            if not itens:
                continue

            texto_msg = f"Olá *{tec}*, aqui está o seu cronograma oficial consolidado de atendimentos EMED:\n\n"
            mensagem_grupo_geral += f"👨‍🔧 *{tec}* ({len(itens)} OS):\n"

            for idx, i in enumerate(itens, 1):
                d_str = i['data'].strftime('%d/%m/%Y') if pd.notna(i['data']) else "-"
                texto_msg += f"*{idx}. Hospital: {i['cliente']} ({i['cidade']}-{i['estado']})*\n"
                texto_msg += f"🛠️ Tipo de Serviço: {i['tipo_servico']}\n"
                if i['etapa_preventiva']:
                    texto_msg += f"📋 Foco/Etapa Preventiva: {i['etapa_preventiva']}\n"
                texto_msg += f"⚙️ Equipamento: {i['equipamento']}\n"
                if i['pendencias']:
                    texto_msg += f"🚨 Pendência / Relato: {i['pendencias']}\n"
                if i['instrumento']:
                    texto_msg += f"📐 Instrumento / Material Necessário: {i['instrumento']}\n"
                texto_msg += f"📍 Endereço: {i['endereco']}\n"
                texto_msg += f"👤 Responsável: {i['resp']} ({i['tel']})\n"
                texto_msg += f"📅 Data: {d_str}\n"
                texto_msg += f"🗺️ Maps: {i['maps']}\n"
                texto_msg += f"🚗 Waze: {i['waze']}\n"
                os_id_link = i.get('id', '')
                texto_msg += f"👉 🚗 *Atender / Iniciar Rota:* https://emed-app-6ofv.onrender.com/?acao=atender&os={os_id_link}\n-----------------------------------\n"

                mensagem_grupo_geral += f"• {d_str} - {i['cliente']} ({i['cidade']}) | {i['equipamento']} [{i['tipo_servico']}]\n"

            mensagem_grupo_geral += "\n"

            encoded_msg = urllib.parse.quote(texto_msg)
            tel_raw = equipa_tecnica.get(tec, {}).get("tel", "")
            if tel_raw.endswith('.0'):
                tel_raw = tel_raw[:-2]
            tel_limpo = ''.join(filter(str.isdigit, tel_raw))
            whatsapp_link = f"https://wa.me/{tel_limpo}?text={encoded_msg}" if tel_limpo else "#"

            with st.expander(f"👷 Técnico: {tec} ({len(itens)} atendimento(s) confirmado(s))", expanded=True):
                st.text_area(f"Mensagem formatada para {tec}:", value=texto_msg, height=200, key=f"txt_wpp_{tec}")

                c_lk1, c_lk2 = st.columns(2)
                with c_lk1:
                    if tel_limpo:
                        st.markdown(f"""
                            <a href="{whatsapp_link}" target="_blank" style="background: #25d366; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 15px; display: inline-block; margin-top: 5px;">
                                📲 Enviar Escala via WhatsApp para {tec}
                            </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Telefone não registado.")

                with c_lk2:
                    for i_at in itens:
                        cli_lbl = i_at['cliente']
                        mp_url = i_at['maps']
                        wz_url = i_at['waze']
                        st.markdown(f"🗺️ **[{cli_lbl} - Google Maps]({mp_url})** | 🚗 **[Waze]({wz_url})**")

                # Acionamento Automático do Almoxarifado para os Materiais/Kits deste Técnico
                itens_com_materiais = [it for it in itens if str(it.get('instrumento', '')).strip()]
                if itens_com_materiais:
                    st.markdown("---")
                    st.markdown(f"##### 📦 Almoxarifado: Materiais & Kits a Separar para {tec}")
                    for idx_m, it_m in enumerate(itens_com_materiais, 1):
                        st.markdown(f"• **{it_m['cliente']}** ({it_m['equipamento']}): `{it_m['instrumento']}`")

                    c_alm1, c_alm2 = st.columns(2)
                    with c_alm1:
                        if st.button(f"⚡ Acionar Almoxarifado para {tec} (Status: A SEPARAR)", key=f"btn_acionar_almox_{tec}"):
                            qtd_acionados = 0
                            for it_m in itens_com_materiais:
                                ok_a, _ = acionar_separacao_automatica_almoxarifado(
                                    ctx.db_name,
                                    tec,
                                    it_m['cliente'],
                                    it_m['equipamento'],
                                    it_m['tipo_servico'],
                                    it_m['instrumento']
                                )
                                if ok_a:
                                    qtd_acionados += 1
                            st.success(f"✅ Almoxarifado acionado com sucesso para {tec}! Pedidos em fila 'A SEPARAR'.")
                            st.rerun()

                    with c_alm2:
                        msg_almox_tec = f"📦 *ORDEM DE SEPARAÇÃO - ALMOXARIFADO EMED*\n\n👨‍🔧 *Técnico Escalado:* {tec}\n📅 *Data:* {datetime.date.today().strftime('%d/%m/%Y')}\n\n"
                        for idx_m, it_m in enumerate(itens_com_materiais, 1):
                            msg_almox_tec += f"*{idx_m}. {it_m['cliente']}* ({it_m['equipamento']})\n🛠️ *Materiais/Kit:* {it_m['instrumento']}\n\n"
                        link_wpp_almox = f"https://wa.me/558593333333?text={urllib.parse.quote(msg_almox_tec)}"
                        st.markdown(f"""
                            <a href="{link_wpp_almox}" target="_blank" style="background: #0284c7; color: white; padding: 10px 18px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px; display: inline-block;">
                                📲 Avisar Estoque/Almoxarifado (WhatsApp)
                            </a>
                        """, unsafe_allow_html=True)

        if ctx.perfil_atual == "Gestor":
            st.markdown("---")
            st.markdown("#### 📋 Resumo Geral para Copiar e Colar no Grupo da Empresa")
            mensagem_grupo_geral += "🔗 *Sistema EMED - Gestão de Equipamentos e Frota*"
            st.text_area("Mensagem Global para o Grupo EMED:", value=mensagem_grupo_geral, height=200, key="msg_grupo_geral")

            encoded_grupo = urllib.parse.quote(mensagem_grupo_geral)
            link_grupo_wpp = f"https://wa.me/?text={encoded_grupo}"
            st.markdown(f"""
                <a href="{link_grupo_wpp}" target="_blank" style="background: #25d366; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block; margin-top: 10px;">
                    📢 Compartilhar Todos os Serviços no Grupo da Empresa (WhatsApp)
                </a>
            """, unsafe_allow_html=True)


def render_minhas_pendencias(ctx: AppContext):
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown(f"### 📋 Minhas Pendências & Chamados Ativos — Técnico: {ctx.usuario_atual}")
    st.info("Painel individual do técnico: consulte aqui todas as ordens de serviço, pendências em aberto e instrumentos necessários.")

    if ctx.perfil_atual == "Gestor":
        lista_filtro_t = ["TODOS (VISÃO GESTOR)"] + sorted(list(equipa_tecnica.keys()))
        usr_atual = ctx.usuario_atual.upper()
        idx_padrao = lista_filtro_t.index(usr_atual) if usr_atual in lista_filtro_t else 0
        tec_foco = st.selectbox("Filtrar Pendências por Técnico:", lista_filtro_t, index=idx_padrao)
    else:
        tec_foco = ctx.usuario_atual.upper()

    df_ativas_tec = df[df['status'].fillna('ATIVO').astype(str).str.upper() == 'ATIVO']
    if tec_foco != "TODOS (VISÃO GESTOR)":
        df_ativas_tec = df_ativas_tec[df_ativas_tec['tecnico_responsavel'].astype(str).str.upper() == tec_foco]

    if df_ativas_tec.empty:
        st.success(f"🎉 Nenhuma pendência ativa registada para {tec_foco} no momento!")
    else:
        for idx_mp, row_mp in df_ativas_tec.iterrows():
            id_os_mp = obter_id_os(idx_mp, row_mp)
            cli_mp = limpar_texto(row_mp.get('cliente'), 'N/D')
            eq_mp = limpar_texto(row_mp.get('equipamento'), 'N/D')
            pend_mp = limpar_texto(row_mp.get('pendencias'), 'Sem descrição')
            inst_mp = limpar_texto(row_mp.get('instrumento_necessario'), 'Nenhum instrumento especial especificado')
            etapa_mp = limpar_texto(row_mp.get('etapa_preventiva'), 'Geral / Não aplicável')
            cid_est_mp = f"{limpar_texto(row_mp.get('cidade'))} - {limpar_texto(row_mp.get('estado'))}"
            end_mp = limpar_texto(row_mp.get('endereco'), cid_est_mp)
            tec_resp_mp = limpar_texto(row_mp.get('tecnico_responsavel'), 'A DEFINIR')
            srv_mp = limpar_texto(row_mp.get('tipo_servico'), 'PREVENTIVA')

            st.markdown(f"""
                <div style="background: #1c2541; border-left: 6px solid #f59e0b; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                    <h4 style="margin: 0 0 6px 0; color: #64dfdf;">🏥 OS #{id_os_mp} | {cli_mp} — ⚙️ {eq_mp}</h4>
                    <p style="margin: 4px 0;"><strong>Técnico Responsável:</strong> {tec_resp_mp} | <strong>Serviço:</strong> {srv_mp}</p>
                    <p style="margin: 4px 0;"><strong>Etapa / Foco da Preventiva:</strong> <span style="color: #93c5fd;">{etapa_mp}</span></p>
                    <p style="margin: 4px 0;"><strong>Pendência / Instrução:</strong> <span style="color: #fca5a5;">{pend_mp}</span></p>
                    <p style="margin: 4px 0; color: #64dfdf;"><strong>📐 Instrumento / Material Necessário:</strong> {inst_mp}</p>
                    <p style="margin: 4px 0;">📍 <strong>Endereço:</strong> {end_mp}</p>
                </div>
            """, unsafe_allow_html=True)

            with st.expander(f"🔄 Atualizar / Assumir ou Transferir OS #{id_os_mp} ({cli_mp})"):
                with st.form(f"form_rapido_mp_{idx_mp}"):
                    lista_t_mp = sorted(list(equipa_tecnica.keys()))
                    tec_atual_mp = tec_resp_mp.upper()
                    idx_t_mp = lista_t_mp.index(tec_atual_mp) if tec_atual_mp in lista_t_mp else 0
                    novo_tec_mp = st.selectbox(
                        "Técnico Responsável (Mudar se outro técnico assumir o serviço)",
                        lista_t_mp,
                        index=idx_t_mp
                    )
                    nova_pend_mp = st.text_input("Atualizar Pendência / Observação", value=pend_mp)
                    val_inst_padrao = "" if inst_mp == "Nenhum instrumento especial especificado" else inst_mp
                    novo_inst_mp = st.text_input("Atualizar Instrumento / Material Necessário", value=val_inst_padrao)

                    if st.form_submit_button("💾 Guardar Atualização da Pendência", type="primary"):
                        df.at[idx_mp, 'tecnico_responsavel'] = novo_tec_mp
                        df.at[idx_mp, 'telefone_tecnico'] = equipa_tecnica.get(novo_tec_mp, {}).get("tel", "")
                        df.at[idx_mp, 'pendencias'] = nova_pend_mp.strip().upper()
                        df.at[idx_mp, 'instrumento_necessario'] = novo_inst_mp.strip().upper()
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success("✅ Pendência e técnico atualizados com sucesso!")
                            st.rerun()
