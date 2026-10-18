import datetime
import json
import os
import pandas as pd
import streamlit as st
from emed_core import (
    limpar_texto,
    limpar_float,
    obter_id_os,
    sincronizar_os_offline_idempotente,
    aplicar_peca_os_idempotente,
    sugerir_proxima_etapa_preventiva,
    agendar_proxima_etapa_circular,
)
from emed_services import (
    AppContext,
    carregar_clientes_internos,
    calcular_duracao_os,
    salvar_dados_seguro,
)
from emed_ui import (
    gerar_html_coletor_offline,
    renderizar_rubrica_tecnico,
    renderizar_quadro_assinatura_cliente,
)


def _render_modo_offline(ctx: AppContext):
    df = ctx.df
    col_off1, col_off2 = st.columns(2)

    with col_off1:
        st.markdown("#### 📥 1. Baixar Aplicativo Coletor Offline")
        st.info("Descarregue o Coletor Universal Offline para o telemóvel ou tablet para uso em bunkers/salas sem sinal.")
        html_universal = gerar_html_coletor_offline(df, ctx.equipa_tecnica)
        st.download_button(
            label="📲 Baixar Aplicativo Coletor Offline (EMED_Offline.html)",
            data=html_universal.encode('utf-8'),
            file_name="EMED_Coletor_Offline.html",
            mime="text/html",
            type="primary"
        )

    with col_off2:
        st.markdown("#### 📤 2. Sincronizar OS Preenchidas Offline")
        arquivos_offline = st.file_uploader("Selecione ficheiros .json de OS Offline", type=["json"], accept_multiple_files=True)
        if arquivos_offline:
            if st.button("🔄 Processar e Sincronizar no Sistema EMED", type="primary"):
                qtd_sinc = 0
                for arq in arquivos_offline:
                    try:
                        dados_json = json.loads(arq.read().decode('utf-8'))
                        df, _ = sincronizar_os_offline_idempotente(
                            df,
                            dados_json,
                            ctx.equipa_tecnica,
                            ctx.usuario_atual
                        )
                        qtd_sinc += 1
                    except Exception as e:
                        st.error(f"Erro ao ler ficheiro {arq.name}: {e}")

                if qtd_sinc > 0 and salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                    st.cache_data.clear()
                    st.success(f"🎉 {qtd_sinc} Ordem(ns) de Serviço sincronizada(s) de forma idempotente com sucesso!")
                    st.rerun()


def _render_criar_nova_os(ctx: AppContext):
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    clientes_externos = sorted([
        c for c in df['cliente'].unique()
        if str(c).strip() != '' and "NENHUM (AGUARDANDO" not in str(c).upper()
    ])
    setores_internos = [f"[INTERNO] {s}" for s in carregar_clientes_internos(ctx.db_name)['nome_setor'].tolist()]
    clientes_disponiveis = clientes_externos + setores_internos

    with st.form("form_abertura_chamado_estruturada"):
        col_ch1, col_ch2 = st.columns(2)
        with col_ch1:
            chamado_cliente = st.selectbox("1. Selecionar Unidade / Hospital ou Setor Interno *", clientes_disponiveis)
            eqs_do_cliente = df[df['cliente'] == chamado_cliente]['equipamento'].tolist()
            eqs_validos_cliente = [e for e in eqs_do_cliente if not str(e).lower().startswith(('nenhum', 'aguardando'))]
            opcoes_equipamento = eqs_validos_cliente + ["➕ Outro / Equipamento ou Serviço Interno Avulso"]
            escolha_equipamento = st.selectbox("2. Equipamento Alvo *", opcoes_equipamento)

            equipamento_final = escolha_equipamento
            if escolha_equipamento == "➕ Outro / Equipamento ou Serviço Interno Avulso":
                equipamento_final = st.text_input("Especifique o Equipamento ou Ativo Interno *")

            opcoes_etapas_abertura = [
                "NÃO APLICÁVEL / CORRETIVA GERAL",
                "ETAPA 1: MESA DE EXAMES, COMANDOS E CONSOLE",
                "ETAPA 2: GANTRY, PDU, QUADRO ELÉTRICO E CABEAMENTO",
                "ETAPA 3: TUBO, GERADOR DE ALTA TENSÃO E COLIMAÇÃO",
                "PREVENTIVA COMPLETA (CHECKLIST INTEGRAL POP/IT)"
            ]
            etapa_sugerida = sugerir_proxima_etapa_preventiva(df, chamado_cliente, equipamento_final)
            idx_etapa_sug = opcoes_etapas_abertura.index(etapa_sugerida) if etapa_sugerida in opcoes_etapas_abertura else 0
            etapa_preventiva_sel = st.selectbox(
                "2.1 Divisão / Etapa da Preventiva (Sugerida automaticamente pelo ciclo anterior)",
                opcoes_etapas_abertura,
                index=idx_etapa_sug
            )

        with col_ch2:
            chamado_tipo = st.selectbox(
                "3. Tipo de Serviço",
                ["PREVENTIVA (Com Checklist POP/IT)", "CORRETIVA (Falha / Parada)", "INSTALAÇÃO", "CALIBRAÇÃO", "SERVIÇO INTERNO EMED"]
            )
            chamado_prioridade = st.selectbox("4. Nível de Urgência", ["NORMAL", "URGENTE / HOSPITAL PARADO", "CRÍTICO (Emergência)"])

            lista_tecs_ch = sorted(list(equipa_tecnica.keys()))
            tec_default = ctx.usuario_atual.upper() if ctx.perfil_atual != "Gestor" else lista_tecs_ch[0]
            idx_tec_def = lista_tecs_ch.index(tec_default) if tec_default in lista_tecs_ch else 0
            chamado_tec = st.selectbox("5. Técnico Responsável", lista_tecs_ch, index=idx_tec_def)
            instrumento_abertura = st.text_input(
                "5.1 Instrumento / Ferramenta Especial Necessária",
                placeholder="EX: MULTÍMETRO FLUKE, FANTOMA, CHAVE DINAMOMÉTRICA"
            )

        st.markdown("#### 🔬 Pré-Atendimento, Defeito Relatado & Diagnóstico Prévio")
        col_pre1, col_pre2 = st.columns(2)
        with col_pre1:
            pre_codigo_erro = st.text_input("Código de Erro no Display (Ex: ERR-402, E-10)")
            pre_sintoma = st.selectbox(
                "Sintoma / Comportamento",
                ["FALHA DE LIGAÇÃO / FONTE", "ERRO DE SOFTWARE / TRAVAMENTO", "DEFEITO DE HARDWARE / PLACA", "RUÍDO ANÓMALO / MECÂNICO", "MANUTENÇÃO PROGRAMADA", "OUTROS"]
            )
            cond_ini_abertura = st.selectbox(
                "Condição Inicial Informada do Equipamento",
                ["OPERACIONAL", "OPERANDO COM RESTRIÇÃO", "PARADO / INOPERANTE", "EM BANCADA / DESMONTADO"]
            )
        with col_pre2:
            pre_testes_cliente = st.text_input("Testes já realizados pelo cliente no local")
            orcamento_aprovado_abertura = st.file_uploader("📄 Anexar Orçamento Aprovado (PDF/Imagem - Opcional)", type=["pdf", "png", "jpg", "jpeg"])
            obs_abertura = st.text_input("Observações de Acesso / Horário / Sala (Opcional)", placeholder="EX: PROCURAR ENF. CHEFE NO 2º ANDAR")

        chamado_relato = st.text_area("6. Defeito Relatado pelo Cliente / Escopo da Preventiva *", placeholder="Descreva o defeito relatado pelo hospital ou os pontos a verificar...")
        foto_arquivo = st.file_uploader("📸 Anexar Foto Inicial / Evidência do Defeito (Opcional)", type=["png", "jpg", "jpeg"])
        chamado_data = st.date_input("7. Data Prevista", value=datetime.date.today())

        btn_abrir_chamado = st.form_submit_button("🚀 Emitir Nova Ordem de Serviço", type="primary")

        if btn_abrir_chamado:
            if not equipamento_final or not chamado_relato:
                st.error("⚠️ Preencha o equipamento e o defeito relatado!")
            else:
                linhas_cli = df[df['cliente'] == chamado_cliente]
                info_cli_base = linhas_cli.iloc[0] if not linhas_cli.empty else {}
                tel_tec_val = equipa_tecnica.get(chamado_tec, {}).get("tel", "")
                ass_tec_padrao = equipa_tecnica.get(chamado_tec, {}).get("assinatura", f"{chamado_tec} - CFT")

                pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                os.makedirs(pasta_uploads, exist_ok=True)

                caminho_foto_salva = ""
                if foto_arquivo is not None:
                    caminho_foto_salva = os.path.join(pasta_uploads, foto_arquivo.name)
                    with open(caminho_foto_salva, "wb") as f:
                        f.write(foto_arquivo.getbuffer())

                caminho_orc_salvo = ""
                if orcamento_aprovado_abertura is not None:
                    caminho_orc_salvo = os.path.join(pasta_uploads, f"ORC_{orcamento_aprovado_abertura.name}")
                    with open(caminho_orc_salvo, "wb") as f:
                        f.write(orcamento_aprovado_abertura.getbuffer())

                cod_err_str = pre_codigo_erro.strip().upper() if pre_codigo_erro else 'N/D'
                tst_cli_str = pre_testes_cliente.strip().upper() if pre_testes_cliente else 'N/D'
                pre_atendimento_str = f"[CÓDIGO ERRO: {cod_err_str}] [SINTOMA: {pre_sintoma}] [TESTES: {tst_cli_str}]"

                nova_os = {
                    'cliente': chamado_cliente,
                    'cidade': limpar_texto(info_cli_base.get('cidade'), 'FORTALEZA').upper(),
                    'estado': limpar_texto(info_cli_base.get('estado'), 'CE').upper(),
                    'equipamento': equipamento_final.strip().upper(),
                    'endereco': limpar_texto(info_cli_base.get('endereco'), 'SEDE EMED').upper(),
                    'tipo_servico': chamado_tipo.upper(),
                    'data_agendamento': pd.to_datetime(chamado_data).strftime('%Y-%m-%d'),
                    'tecnico_responsavel': chamado_tec.upper(),
                    'telefone_tecnico': tel_tec_val,
                    'responsavel_hospital': limpar_texto(info_cli_base.get('responsavel_hospital'), 'RESPONSÁVEL LOCAL').upper(),
                    'contato_responsavel': limpar_texto(info_cli_base.get('contato_responsavel'), ''),
                    'confirmado': 'SIM',
                    'pendencias': f"[{chamado_prioridade.upper()}] {chamado_relato.strip().upper()}",
                    'status': 'ATIVO',
                    'checkin_hora': '',
                    'checkout_hora': '',
                    'tempo_atendimento': '',
                    'checklist_pop': '',
                    'assinatura_cliente': '',
                    'assinatura_tecnico': ass_tec_padrao,
                    'pre_atendimento': pre_atendimento_str,
                    'foto_evidencia': caminho_foto_salva,
                    'cnpj': limpar_texto(info_cli_base.get('cnpj'), ''),
                    'cep': limpar_texto(info_cli_base.get('cep'), ''),
                    'email': limpar_texto(info_cli_base.get('email'), ''),
                    'whatsapp': limpar_texto(info_cli_base.get('whatsapp'), ''),
                    'endereco_fiscal': limpar_texto(info_cli_base.get('endereco_fiscal'), ''),
                    'tipo_contrato': limpar_texto(info_cli_base.get('tipo_contrato'), 'CONTRATO'),
                    'instrumento_necessario': instrumento_abertura.strip().upper(),
                    'etapa_preventiva': "" if "NÃO APLICÁVEL" in etapa_preventiva_sel else etapa_preventiva_sel,
                    'orcamento_anexo': caminho_orc_salvo,
                    'condicao_pagamento': '',
                    'valor_os': 0.0,
                    'defeito_relatado': chamado_relato.strip().upper(),
                    'condicao_inicial': cond_ini_abertura,
                    'problemas_encontrados': '',
                    'causa_raiz': '',
                    'servico_executado': '',
                    'parametros_medidos': '',
                    'observacoes_gerais': obs_abertura.strip().upper(),
                    'condicao_final': 'LIBERADO PARA USO NORMAL',
                    'foto_depois': '',
                    'assinatura_cliente_img': ''
                }
                df = pd.concat([df, pd.DataFrame([nova_os])], ignore_index=True)
                if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                    st.cache_data.clear()
                    st.success("✅ Salvo com sucesso! Ordem de Serviço emitida.")
                    st.rerun()


def _render_historico_concluidas(ctx: AppContext):
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("#### 📁 Ordens de Serviço Fechadas / Faturamento & Reabertura para Outro Técnico")
    df_os_concluidas = df[df['status'].astype(str).str.upper() == 'CONCLUÍDO']
    if df_os_concluidas.empty:
        st.info("ℹ️ Ainda não existem ordens de serviço concluídas.")
    else:
        for idx_c, row_c in df_os_concluidas.iterrows():
            id_os_c = obter_id_os(idx_c, row_c)
            tec_hist_c = limpar_texto(row_c.get('tecnico_responsavel'))
            titulo_exp_c = f"✅ OS #{id_os_c} | {row_c['cliente']} — Equipamento: {row_c['equipamento']} [Técnico: {tec_hist_c}]"
            with st.expander(titulo_exp_c):
                laudo_hist = limpar_texto(row_c.get('pendencias'))
                etapa_hist = limpar_texto(row_c.get('etapa_preventiva'), 'GERAL')
                ass_cli_hist = limpar_texto(row_c.get('assinatura_cliente'), '-')
                def_rel_h = limpar_texto(row_c.get('defeito_relatado'), '-')
                prob_enc_h = limpar_texto(row_c.get('problemas_encontrados'), '-')
                srv_exec_h = limpar_texto(row_c.get('servico_executado'), laudo_hist)
                obs_ger_h = limpar_texto(row_c.get('observacoes_gerais'), '-')
                param_h = limpar_texto(row_c.get('parametros_medidos'), '-')
                cond_f_h = limpar_texto(row_c.get('condicao_final'), 'LIBERADO PARA USO NORMAL')

                ch1, ch2 = st.columns(2)
                with ch1:
                    st.markdown(f"**📢 Defeito Relatado:** {def_rel_h}")
                    st.markdown(f"**🔍 Problemas Encontrados:** {prob_enc_h}")
                    st.markdown(f"**🛠️ Serviço Executado / Laudo:** {srv_exec_h}")
                    st.markdown(f"**📋 Etapa Preventiva Executada:** `{etapa_hist}`")
                with ch2:
                    st.markdown(f"**⚡ Parâmetros / Medições:** `{param_h}`")
                    st.markdown(f"**🏁 Condição Final na Saída:** `{cond_f_h}`")
                    st.markdown(f"**📝 Observações Gerais:** {obs_ger_h}")
                    if limpar_texto(row_c.get('condicao_pagamento')):
                        st.markdown(f"💰 **Faturamento:** `{row_c.get('condicao_pagamento')}`")
                    if limpar_texto(row_c.get('orcamento_anexo')):
                        nome_arq_orc = os.path.basename(str(row_c.get('orcamento_anexo')))
                        st.markdown(f"📎 **Orçamento Aprovado Anexado:** `{nome_arq_orc}`")

                f_ant_c = limpar_texto(row_c.get('foto_evidencia'), '')
                f_dep_c = limpar_texto(row_c.get('foto_depois'), '')
                if (f_ant_c and os.path.exists(f_ant_c)) or (f_dep_c and os.path.exists(f_dep_c)):
                    st.markdown("##### 📸 Registo Fotográfico da Intervenção")
                    cf1, cf2 = st.columns(2)
                    with cf1:
                        if f_ant_c and os.path.exists(f_ant_c):
                            st.image(f_ant_c, caption="Foto Antes / Evidência Inicial", width=260)
                    with cf2:
                        if f_dep_c and os.path.exists(f_dep_c):
                            st.image(f_dep_c, caption="Foto Depois / Serviço Concluído", width=260)

                st.markdown("---")
                st.markdown("##### ✍️ Rubrica Pré-Salva do Técnico & Assinatura Digital do Cliente")
                ca_h1, ca_h2 = st.columns(2)
                with ca_h1:
                    renderizar_rubrica_tecnico(tec_hist_c, equipa_tecnica)
                with ca_h2:
                    st.markdown(f"**Responsável no Hospital:** `{ass_cli_hist}`")
                    img_sig_cli = limpar_texto(row_c.get('assinatura_cliente_img'), '')
                    if img_sig_cli.startswith("data:image"):
                        st.markdown(f"""
                            <div style="background:#0b132b; border:1px solid #64dfdf; border-radius:8px; padding:8px; text-align:center;">
                                <img src="{img_sig_cli}" style="max-width:260px; height:auto;" alt="Assinatura Cliente"/>
                                <p style="margin:2px 0 0 0; font-size:11px; color:#10b981 !important;">✅ Assinatura Coletada na Tela do Celular</p>
                            </div>
                        """, unsafe_allow_html=True)
                    elif img_sig_cli and os.path.exists(img_sig_cli):
                        st.image(img_sig_cli, caption="Rubrica do Cliente", width=240)

                st.markdown("---")
                st.markdown("##### 🔄 Reabrir OS / Transferir Pendência para Outro Técnico")
                with st.form(f"form_reabrir_os_{idx_c}"):
                    lista_t_reab = sorted(list(equipa_tecnica.keys()))
                    tec_reab = st.selectbox("Selecionar Novo Técnico Responsável", lista_t_reab, key=f"reab_t_{idx_c}")
                    motivo_reab = st.text_input(
                        "Pendência / O que falta realizar (Ficará visível junto ao histórico anterior)",
                        key=f"reab_m_{idx_c}"
                    )
                    inst_reab = st.text_input("Instrumento / Material Necessário para levar", key=f"reab_i_{idx_c}")
                    if st.form_submit_button("🔓 Reabrir OS no Nome do Novo Técnico", type="primary"):
                        df.at[idx_c, 'status'] = 'ATIVO'
                        df.at[idx_c, 'tecnico_responsavel'] = tec_reab
                        df.at[idx_c, 'telefone_tecnico'] = equipa_tecnica.get(tec_reab, {}).get("tel", "")
                        df.at[idx_c, 'pendencias'] = f"[REABERTA P/ {tec_reab}] {motivo_reab.strip().upper()} || HISTÓRICO ANTERIOR: {laudo_hist}"
                        df.at[idx_c, 'instrumento_necessario'] = inst_reab.strip().upper()
                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            st.cache_data.clear()
                            st.success(f"✅ Salvo com sucesso! OS #{id_os_c} reaberta para o técnico {tec_reab}!")
                            st.rerun()


def _render_execucao_os_ativas(ctx: AppContext):
    df = ctx.df
    df_estoque = ctx.df_estoque
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("#### 🛠️ Execução Modular de Ordem de Serviço em Campo (6 Módulos)")
    df_os_ativas = df[df['status'].astype(str).str.upper() == 'ATIVO']

    if df_os_ativas.empty:
        st.info("ℹ️ Não existem ordens de serviço ativas no momento.")
    else:
        for idx_os, row_os in df_os_ativas.iterrows():
            id_os_ativa = obter_id_os(idx_os, row_os)
            tec_resp_os = limpar_texto(row_os.get('tecnico_responsavel'), 'A DEFINIR').upper()
            cli_os_atual = limpar_texto(row_os.get('cliente'), '')
            eq_os_atual = limpar_texto(row_os.get('equipamento'), '')
            inst_os_atual = limpar_texto(row_os.get('instrumento_necessario'), '')
            etapa_os_atual = limpar_texto(row_os.get('etapa_preventiva'), '')
            srv_os_atual = limpar_texto(row_os.get('tipo_servico'), 'PREVENTIVA')
            dt_os_atual = limpar_texto(row_os.get('data_agendamento'), '-')
            pend_os_atual = limpar_texto(row_os.get('pendencias'))
            def_rel_atual = limpar_texto(row_os.get('defeito_relatado'), pend_os_atual)
            pre_at_atual = limpar_texto(row_os.get('pre_atendimento'), 'Sem registo prévio')
            prob_enc_atual = limpar_texto(row_os.get('problemas_encontrados'), '')
            srv_exec_atual = limpar_texto(row_os.get('servico_executado'), '')
            obs_ger_atual = limpar_texto(row_os.get('observacoes_gerais'), '')
            param_atual = limpar_texto(row_os.get('parametros_medidos'), '')

            titulo_os_ativa = f"🛠️ OS #{id_os_ativa} | {cli_os_atual} — Equipamento: {eq_os_atual} [Técnico: {tec_resp_os}]"
            with st.expander(titulo_os_ativa):
                c_top1, c_top2, c_top3 = st.columns([2.2, 1.4, 1.4])
                with c_top1:
                    st.markdown(f"**Serviço:** `{srv_os_atual}` | **Agendado:** `{dt_os_atual}`")
                    if inst_os_atual:
                        st.markdown(f"📐 **Instrumento / Material Requerido:** `{inst_os_atual}`")
                    lista_tecs_exec = sorted(list(equipa_tecnica.keys()))
                    idx_t_exec = lista_tecs_exec.index(tec_resp_os) if tec_resp_os in lista_tecs_exec else 0
                    novo_tec_exec = st.selectbox(
                        "👷 Técnico Executante (Altere se outro técnico assumir a OS)",
                        lista_tecs_exec,
                        index=idx_t_exec,
                        key=f"sel_tec_exec_{idx_os}"
                    )
                with c_top2:
                    if st.button("📍 Marcar Check-in (Chegada)", key=f"cin_{idx_os}", use_container_width=True):
                        hora_atual = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                        df.at[idx_os, 'checkin_hora'] = hora_atual
                        salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                        st.cache_data.clear()
                        st.rerun()
                    cin_val = limpar_texto(row_os.get('checkin_hora'))
                    st.caption(f"✅ **Chegada:** {cin_val if cin_val else 'Não registada'}")
                with c_top3:
                    if st.button("🏁 Marcar Check-out (Saída)", key=f"cout_{idx_os}", use_container_width=True):
                        hora_saida = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
                        df.at[idx_os, 'checkout_hora'] = hora_saida
                        dur_calc = calcular_duracao_os(row_os.get('checkin_hora', ''), hora_saida)
                        if dur_calc:
                            df.at[idx_os, 'tempo_atendimento'] = dur_calc
                        salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                        st.cache_data.clear()
                        st.rerun()
                    cout_val = limpar_texto(row_os.get('checkout_hora'))
                    dur_val = limpar_texto(row_os.get('tempo_atendimento'))
                    txt_dur = f" ({dur_val})" if dur_val else ""
                    st.caption(f"🏁 **Saída:** {cout_val if cout_val else 'Não registada'}{txt_dur}")

                st.markdown("---")

                m_tab1, m_tab2, m_tab3, m_tab4, m_tab5, m_tab6 = st.tabs([
                    "📢 1. Defeito Relatado",
                    "🔍 2. Problemas Encontrados",
                    "🛠️ 3. Serviço & Peças",
                    "🚨 4. Pendências & Obs.",
                    "📸 5. Fotos & Anexos",
                    "✍️ 6. Assinatura & Fecho"
                ])

                with m_tab1:
                    st.markdown("##### 📢 Defeito Relatado pelo Cliente & Estado Inicial na Chegada")
                    st.caption(f"🔬 **Dados de Pré-Atendimento / Erros:** {pre_at_atual}")
                    opcoes_cond_ini = ["OPERACIONAL", "OPERANDO COM RESTRIÇÃO", "PARADO / INOPERANTE", "EM BANCADA / DESMONTADO"]
                    cond_ini_atual = limpar_texto(row_os.get('condicao_inicial'), 'OPERACIONAL')
                    idx_ci = opcoes_cond_ini.index(cond_ini_atual) if cond_ini_atual in opcoes_cond_ini else 0
                    condicao_ini_os = st.selectbox(
                        "Condição do Equipamento na Chegada do Técnico",
                        opcoes_cond_ini,
                        index=idx_ci,
                        key=f"ci_os_{idx_os}"
                    )
                    defeito_relatado_in = st.text_area(
                        "Defeito Relatado pelo Hospital / Solicitação Original *",
                        value=def_rel_atual,
                        height=90,
                        key=f"def_rel_{idx_os}"
                    )

                    df_hist_prev = df[
                        (df['cliente'] == cli_os_atual) &
                        (df['equipamento'] == eq_os_atual) &
                        (df.index != idx_os)
                    ]
                    if not df_hist_prev.empty:
                        st.markdown("###### 📜 Histórico Recente deste Equipamento (Evita Retrabalho)")
                        for idx_hp, r_hp in df_hist_prev.tail(4).iterrows():
                            id_hp = obter_id_os(idx_hp, r_hp)
                            et_hp = limpar_texto(r_hp.get('etapa_preventiva'), 'ETAPA GERAL')
                            dt_hp = limpar_texto(r_hp.get('data_agendamento'), 'S/D')
                            tc_hp = limpar_texto(r_hp.get('tecnico_responsavel'))
                            pd_hp = limpar_texto(r_hp.get('pendencias'))
                            st.caption(f"• **OS #{id_hp}** ({dt_hp}) | **Técnico:** {tc_hp} | **Etapa:** {et_hp} | **Resumo:** {pd_hp}")

                with m_tab2:
                    st.markdown("##### 🔍 Problemas Encontrados em Campo, Causa Raiz & Medições")
                    opcoes_causa = [
                        "MANUTENÇÃO PREVENTIVA PROGRAMADA (SEM FALHA)",
                        "DESGASTE NATURAL DE COMPONENTE / PEÇA",
                        "OSCILAÇÃO / FALHA NA REDE ELÉTRICA DO HOSPITAL",
                        "FALHA DE REFRIGERAÇÃO / AR-CONDICIONADO DA SALA",
                        "DESCALIBRAÇÃO / DESAJUSTE TÉCNICO",
                        "FALHA DE OPERAÇÃO / MAU USO",
                        "FALHA DE SOFTWARE / SISTEMA / REDE DICOM",
                        "OUTRA CAUSA / EM ANÁLISE"
                    ]
                    causa_at = limpar_texto(row_os.get('causa_raiz'), opcoes_causa[0])
                    idx_cr = opcoes_causa.index(causa_at) if causa_at in opcoes_causa else 0
                    causa_raiz_in = st.selectbox(
                        "Causa Raiz Identificada (Engenharia Clínica)",
                        opcoes_causa,
                        index=idx_cr,
                        key=f"cr_os_{idx_os}"
                    )
                    problemas_encontrados_in = st.text_area(
                        "Problemas Encontrados / Diagnóstico Técnico Detalhado *",
                        value=prob_enc_atual,
                        placeholder="Descreva os defeitos constatados na inspeção técnica, placas/módulos afetados ou estado geral...",
                        height=100,
                        key=f"prob_enc_{idx_os}"
                    )
                    parametros_medidos_in = st.text_input(
                        "⚡ Parâmetros Técnicos & Medições Ambientais (Tensão F-N, Terra-Neutro, Temp. Sala °C, Disparos/Horas Tubo)",
                        value=param_atual,
                        placeholder="EX: F-N: 220V | T-N: 0.6V | TEMP SALA: 20°C | UMIDADE: 52% | TUBO: 45.200 DISPAROS",
                        key=f"param_med_{idx_os}"
                    )

                with m_tab3:
                    st.markdown("##### 🛠️ Serviço Executado, Checklist POP/IT & Aplicação de Peças")
                    c_s1, c_s2 = st.columns(2)
                    with c_s1:
                        etapa_executada_fecho = st.selectbox(
                            "Parte / Etapa do Equipamento Inspecionada nesta Visita",
                            [
                                limpar_texto(etapa_os_atual, "GERAL / CORRETIVA"),
                                "PARTE 1: MESA DE EXAMES, COMANDOS E CONSOLE (PRÓXIMA: GANTRY/PDU)",
                                "PARTE 2: GANTRY, PDU, QUADRO ELÉTRICO (PRÓXIMA: TUBO/GERADOR)",
                                "PARTE 3: TUBO, ALTA TENSÃO E CALIBRAÇÃO (PRÓXIMA: MESA/CONSOLE)",
                                "PREVENTIVA COMPLETA REALIZADA"
                            ],
                            key=f"et_f_{idx_os}"
                        )
                        itens_pop_opcoes = [
                            "LIMPEZA TÉCNICA INTERNA/EXTERNA",
                            "INSPEÇÃO DE CABOS, CONECTORES E ATERRAMENTO",
                            "VERIFICAÇÃO DE TRAVAS E SEGURANÇA MECÂNICA",
                            "LUBRIFICAÇÃO DE GUIAS E ROLAMENTOS",
                            "CALIBRAÇÃO / TESTES DE DISPARO E IMAGEM",
                            "TESTE FUNCIONAL COM OPERADOR LOCAL"
                        ]
                        pop_salvo = [x.strip() for x in limpar_texto(row_os.get('checklist_pop')).split(",") if x.strip() in itens_pop_opcoes]
                        checklist_pop_sel = st.multiselect(
                            "Checklist POP / Procedimentos Realizados",
                            options=itens_pop_opcoes,
                            default=pop_salvo,
                            key=f"chk_pop_ms_{idx_os}"
                        )
                    with c_s2:
                        pecas_disponiveis = df_estoque['nome_peca'].tolist() if not df_estoque.empty else []
                        peca_selecionada = st.selectbox(
                            "Selecione a Peça Aplicada do Estoque (Baixa Automática)",
                            ["NENHUMA PEÇA"] + pecas_disponiveis,
                            key=f"peca_{idx_os}"
                        )
                        qtd_aplicada = st.number_input("Quantidade Aplicada", min_value=1, value=1, key=f"qtd_peca_{idx_os}")

                    obs_tecnico_final = st.text_area(
                        "Descrição Detalhada do Serviço Executado / Solução Aplicada *",
                        value=srv_exec_atual,
                        placeholder="Relate todos os procedimentos executados, ajustes, reparos e testes finais...",
                        height=110,
                        key=f"obs_f_{idx_os}"
                    )

                with m_tab4:
                    st.markdown("##### 🚨 Status de Pendências, Condição de Saída & Observações ao Hospital")
                    status_fecho_escolha = st.radio(
                        "Resultado desta Intervenção:",
                        [
                            "✅ CONCLUÍDO (Fechar OS e Gerar Documento de Faturamento)",
                            "🚨 DEIXAR PENDÊNCIA ATIVA (Mantém alerta ligado para próxima intervenção)"
                        ],
                        horizontal=True,
                        key=f"rad_st_{idx_os}"
                    )
                    opcoes_cond_fim = [
                        "LIBERADO PARA USO NORMAL",
                        "LIBERADO COM RESTRIÇÃO OPERACIONAL",
                        "PARADO AGUARDANDO PEÇA / APROVAÇÃO DE ORÇAMENTO",
                        "INTERDITADO POR SEGURANÇA TÉCNICA"
                    ]
                    cond_fim_at = limpar_texto(row_os.get('condicao_final'), opcoes_cond_fim[0])
                    idx_cf = opcoes_cond_fim.index(cond_fim_at) if cond_fim_at in opcoes_cond_fim else 0
                    condicao_fim_os = st.selectbox(
                        "Condição Final do Equipamento na Saída do Técnico",
                        opcoes_cond_fim,
                        index=idx_cf,
                        key=f"cf_os_{idx_os}"
                    )
                    inst_prox_visita = st.text_input(
                        "📐 Instrumento, Ferramenta ou Peça necessária para a próxima visita (se ficar pendente)",
                        value=inst_os_atual,
                        placeholder="EX: LEVAR MULTÍMETRO FLUKE, FANTOMA E PLACA FONTE",
                        key=f"inst_prox_{idx_os}"
                    )
                    observacoes_gerais_in = st.text_area(
                        "📝 Observações Gerais & Recomendações Técnicas ao Hospital (Fica registado na OS)",
                        value=obs_ger_atual,
                        placeholder="EX: RECOMENDADO ADEQUAR CLIMATIZAÇÃO DA SALA / PROVIDENCIAR NOBREAK DEDICADO...",
                        height=85,
                        key=f"obs_ger_{idx_os}"
                    )
                    agendar_prox_ciclo = st.checkbox(
                        "🔄 Agendar automaticamente a próxima etapa circular da preventiva (+30 dias) ao concluir",
                        value=("PREVENTIVA" in srv_os_atual.upper()),
                        key=f"chk_ciclo_{idx_os}"
                    )

                with m_tab5:
                    st.markdown("##### 📸 Galeria de Fotos da OS (Antes / Depois) & Orçamento Aprovado")
                    cf_up1, cf_up2, cf_up3 = st.columns(3)
                    with cf_up1:
                        foto_antes_up = st.file_uploader(
                            "📸 Foto Antes / Defeito (PNG/JPG)",
                            type=["png", "jpg", "jpeg"],
                            key=f"f_ant_up_{idx_os}"
                        )
                        f_ant_salva = limpar_texto(row_os.get('foto_evidencia'), '')
                        if f_ant_salva and os.path.exists(f_ant_salva):
                            st.image(f_ant_salva, caption="Foto Inicial Salva", width=200)
                    with cf_up2:
                        foto_depois_up = st.file_uploader(
                            "📸 Foto Depois / Serviço Pronto (PNG/JPG)",
                            type=["png", "jpg", "jpeg"],
                            key=f"f_dep_up_{idx_os}"
                        )
                        f_dep_salva = limpar_texto(row_os.get('foto_depois'), '')
                        if f_dep_salva and os.path.exists(f_dep_salva):
                            st.image(f_dep_salva, caption="Foto Final Salva", width=200)
                    with cf_up3:
                        orcamento_fecho_up = st.file_uploader(
                            "📄 Orçamento Aprovado (PDF/Imagem)",
                            type=["pdf", "png", "jpg", "jpeg"],
                            key=f"orc_up_{idx_os}"
                        )
                        orc_salvo_at = limpar_texto(row_os.get('orcamento_anexo'), '')
                        if orc_salvo_at:
                            st.caption(f"📎 Anexo atual: `{os.path.basename(orc_salvo_at)}`")

                with m_tab6:
                    st.markdown("##### 💰 Faturamento & ✍️ Coleta de Assinatura")
                    c_fat1, c_fat2 = st.columns(2)
                    with c_fat1:
                        val_os_ant = limpar_float(row_os.get('valor_os'), 0.0)
                        valor_servico_os = st.number_input(
                            "Valor Total do Orçamento / Serviço + Peças (R$)",
                            min_value=0.0,
                            value=val_os_ant,
                            step=100.0,
                            key=f"val_os_{idx_os}"
                        )
                    with c_fat2:
                        opcao_faturamento = st.selectbox(
                            "💳 Condição de Faturamento (Ao fechar a OS)",
                            [
                                "FATURAMENTO BOLETO BANCÁRIO (VALOR INTEGRAL)",
                                "FATURAMENTO PIX À VISTA (COM 10% DE DESCONTO AUTOMÁTICO)",
                                "CORTESIA / COBERTO POR CONTRATO MENSAL"
                            ],
                            key=f"fat_op_{idx_os}"
                        )

                    if "PIX" in opcao_faturamento and valor_servico_os > 0:
                        valor_final_faturar = round(valor_servico_os * 0.90, 2)
                        st.info(f"⚡ **Desconto de 10% no PIX aplicado:** De R$ {valor_servico_os:,.2f} por **R$ {valor_final_faturar:,.2f}**")
                    else:
                        valor_final_faturar = valor_servico_os

                    st.markdown("---")
                    col_as1, col_as2 = st.columns([1.2, 1.8])
                    with col_as1:
                        st.markdown("###### 👨‍🔧 1. Rubrica do Técnico (Pré-Salva)")
                        ass_padrao_tec = equipa_tecnica.get(novo_tec_exec, {}).get("assinatura", f"{novo_tec_exec} - CFT")
                        renderizar_rubrica_tecnico(novo_tec_exec, equipa_tecnica)
                        st.caption("A rubrica e o registo CFT do técnico já estão salvos e são aplicados automaticamente.")

                    with col_as2:
                        st.markdown("###### 🏥 2. Assinatura do Cliente (Pelo Celular)")
                        assinatura_cliente_input = st.text_input(
                            "Nome e Cargo/Setor do Responsável no Hospital *",
                            value=limpar_texto(row_os.get('assinatura_cliente'), ''),
                            placeholder="EX: DR. CARLOS / ENF. MARIA - RADIOLOGIA",
                            key=f"as_cli_{idx_os}"
                        )
                        label_input_sig = renderizar_quadro_assinatura_cliente(idx_os)
                        sig_img_atual = limpar_texto(row_os.get('assinatura_cliente_img'), '')
                        assinatura_cli_b64 = st.text_input(
                            label_input_sig,
                            value=sig_img_atual,
                            placeholder="Gerado automaticamente ao clicar em 'Fixar Assinatura do Cliente na OS'",
                            key=f"sig_b64_{idx_os}"
                        )

                st.markdown("---")
                if st.button("💾 Gravar Ordem de Serviço Modular, Atualizar Estoque e Faturamento", key=f"btn_finalizar_os_{idx_os}", type="primary", use_container_width=True):
                    texto_relatorio_base = obs_tecnico_final.strip() or problemas_encontrados_in.strip()
                    if not assinatura_cliente_input.strip() or not texto_relatorio_base:
                        st.error("⚠️ Preencha o Serviço Executado (Aba 3) e o Nome do Responsável no Hospital (Aba 6)!")
                    else:
                        ref_peca_ant = limpar_texto(row_os.get('peca_baixada_ref'), '')
                        ok_peca, tag_peca, nova_ref_peca = aplicar_peca_os_idempotente(
                            ctx.db_name,
                            peca_selecionada,
                            int(qtd_aplicada),
                            ref_peca_ant
                        )
                        if not ok_peca:
                            st.error(tag_peca)
                        else:
                            if tag_peca and tag_peca not in texto_relatorio_base.upper():
                                relatorio_com_peca = f"{texto_relatorio_base.upper()} | {tag_peca}"
                            else:
                                relatorio_com_peca = texto_relatorio_base.upper()

                            pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                            os.makedirs(pasta_uploads, exist_ok=True)

                            if foto_antes_up is not None:
                                caminho_f_ant = os.path.join(pasta_uploads, f"ANTES_OS{id_os_ativa}_{foto_antes_up.name}")
                                with open(caminho_f_ant, "wb") as f:
                                    f.write(foto_antes_up.getbuffer())
                                df.at[idx_os, 'foto_evidencia'] = caminho_f_ant

                            if foto_depois_up is not None:
                                caminho_f_dep = os.path.join(pasta_uploads, f"DEPOIS_OS{id_os_ativa}_{foto_depois_up.name}")
                                with open(caminho_f_dep, "wb") as f:
                                    f.write(foto_depois_up.getbuffer())
                                df.at[idx_os, 'foto_depois'] = caminho_f_dep

                            if orcamento_fecho_up is not None:
                                caminho_orc_fecho = os.path.join(pasta_uploads, f"ORC_OS{id_os_ativa}_{orcamento_fecho_up.name}")
                                with open(caminho_orc_fecho, "wb") as f:
                                    f.write(orcamento_fecho_up.getbuffer())
                                df.at[idx_os, 'orcamento_anexo'] = caminho_orc_fecho

                            fechar_definitivo = "CONCLUÍDO" in status_fecho_escolha
                            resumo_pag = f"{opcao_faturamento} — VALOR FINAL: R$ {valor_final_faturar:,.2f}"

                            df.at[idx_os, 'tecnico_responsavel'] = novo_tec_exec
                            df.at[idx_os, 'telefone_tecnico'] = equipa_tecnica.get(novo_tec_exec, {}).get("tel", "")
                            df.at[idx_os, 'etapa_preventiva'] = etapa_executada_fecho
                            df.at[idx_os, 'checklist_pop'] = ", ".join(checklist_pop_sel)
                            df.at[idx_os, 'condicao_inicial'] = condicao_ini_os
                            df.at[idx_os, 'defeito_relatado'] = defeito_relatado_in.strip().upper()
                            df.at[idx_os, 'causa_raiz'] = causa_raiz_in
                            df.at[idx_os, 'problemas_encontrados'] = problemas_encontrados_in.strip().upper()
                            df.at[idx_os, 'parametros_medidos'] = parametros_medidos_in.strip().upper()
                            df.at[idx_os, 'servico_executado'] = relatorio_com_peca
                            df.at[idx_os, 'observacoes_gerais'] = observacoes_gerais_in.strip().upper()
                            df.at[idx_os, 'condicao_final'] = condicao_fim_os
                            df.at[idx_os, 'condicao_pagamento'] = resumo_pag
                            df.at[idx_os, 'valor_os'] = float(valor_final_faturar)
                            df.at[idx_os, 'assinatura_cliente'] = assinatura_cliente_input.strip().upper()
                            df.at[idx_os, 'assinatura_cliente_img'] = assinatura_cli_b64.strip()
                            df.at[idx_os, 'assinatura_tecnico'] = ass_padrao_tec.strip().upper()
                            df.at[idx_os, 'peca_baixada_ref'] = nova_ref_peca

                            resumo_diag = f" | [DIAGNÓSTICO: {problemas_encontrados_in.strip().upper()}]" if problemas_encontrados_in.strip() else ""
                            if fechar_definitivo:
                                df.at[idx_os, 'pendencias'] = f"[CONCLUÍDO - {etapa_executada_fecho}] {relatorio_com_peca}{resumo_diag} | [{resumo_pag}]"
                                df.at[idx_os, 'status'] = 'CONCLUÍDO'
                                df.at[idx_os, 'instrumento_necessario'] = ''
                                if agendar_prox_ciclo:
                                    df, _ = agendar_proxima_etapa_circular(
                                        df,
                                        df.loc[idx_os],
                                        etapa_executada_fecho,
                                        dias_ciclo=30
                                    )
                            else:
                                df.at[idx_os, 'pendencias'] = f"[PENDÊNCIA ATIVA - {novo_tec_exec}] {relatorio_com_peca}{resumo_diag} (ETAPA REALIZADA: {etapa_executada_fecho})"
                                df.at[idx_os, 'status'] = 'ATIVO'
                                df.at[idx_os, 'instrumento_necessario'] = inst_prox_visita.strip().upper()

                            if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                                st.cache_data.clear()
                                st.success("✅ Salvo com sucesso! Ordem de Serviço gravada e estoque atualizado!")
                                st.rerun()


def render_chamados_os(ctx: AppContext):
    st.markdown("### 🎫 Gestão de Ordens de Serviço (OS), Preventivas por Partes & Faturamento")
    st.markdown(
        "Preenchimento online ou **100% offline** com histórico de etapas da preventiva, "
        "reatribuição de técnico, anexo de orçamento aprovado e faturamento (Boleto ou Pix 10%)."
    )

    sub_os = st.radio(
        "Escolha a vista:",
        [
            "📋 Listar / Executar Ordens Abertas",
            "📴 Modo Campo Offline (Baixar / Sincronizar)",
            "📁 Histórico de OS Concluídas & Reabertura",
            "➕ Criar Nova OS"
        ],
        horizontal=True
    )
    st.markdown("---")

    if sub_os == "📴 Modo Campo Offline (Baixar / Sincronizar)":
        _render_modo_offline(ctx)
    elif sub_os == "➕ Criar Nova OS":
        _render_criar_nova_os(ctx)
    elif sub_os == "📁 Histórico de OS Concluídas & Reabertura":
        _render_historico_concluidas(ctx)
    else:
        _render_execucao_os_ativas(ctx)
