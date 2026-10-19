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


def _gerar_html_os_formatada(id_os_c: str, row_c: pd.Series, equipa_tecnica: dict) -> str:
    """Gera o documento HTML/A4 oficial da Ordem de Serviço Fechada (pronto para impressão/PDF e anexo de e-mail)."""
    cliente = limpar_texto(row_c.get("cliente"), "N/D")
    cnpj = limpar_texto(row_c.get("cnpj"), "N/D")
    endereco = limpar_texto(row_c.get("endereco"), "N/D")
    cidade = limpar_texto(row_c.get("cidade"), "FORTALEZA")
    estado = limpar_texto(row_c.get("estado"), "CE")
    email_cli = limpar_texto(row_c.get("email"), "N/D")
    resp_hosp = limpar_texto(row_c.get("responsavel_hospital"), "N/D")
    equipamento = limpar_texto(row_c.get("equipamento"), "N/D")
    tipo_srv = limpar_texto(row_c.get("tipo_servico"), "MANUTENÇÃO")
    etapa_prev = limpar_texto(row_c.get("etapa_preventiva"), "GERAL")
    tec_princ = limpar_texto(row_c.get("tecnico_responsavel"), "N/D")
    tec_aux = limpar_texto(row_c.get("tecnico_auxiliar"), "NENHUM (INDIVIDUAL)")
    dt_agend = limpar_texto(row_c.get("data_agendamento"), "-")
    cin = limpar_texto(row_c.get("checkin_hora"), "-")
    cout = limpar_texto(row_c.get("checkout_hora"), "-")
    dur = limpar_texto(row_c.get("tempo_atendimento"), "-")
    def_rel = limpar_texto(row_c.get("defeito_relatado"), "-")
    prob_enc = limpar_texto(row_c.get("problemas_encontrados"), "-")
    causa_r = limpar_texto(row_c.get("causa_raiz"), "-")
    srv_exec = limpar_texto(row_c.get("servico_executado"), limpar_texto(row_c.get("pendencias"), "-"))
    chk_pop = limpar_texto(row_c.get("checklist_pop"), "N/A")
    param_m = limpar_texto(row_c.get("parametros_medidos"), "-")
    obs_ger = limpar_texto(row_c.get("observacoes_gerais"), "SEM OBSERVAÇÕES ADICIONAIS")
    pend_txt = limpar_texto(row_c.get("pendencias"), "SEM PENDÊNCIAS")
    cond_fin = limpar_texto(row_c.get("condicao_final"), "LIBERADO PARA USO NORMAL")
    cond_pag = limpar_texto(row_c.get("condicao_pagamento"), "-")
    ass_tec = limpar_texto(row_c.get("assinatura_tecnico"), f"{tec_princ} - CFT")
    ass_cli = limpar_texto(row_c.get("assinatura_cliente"), resp_hosp)
    img_sig = limpar_texto(row_c.get("assinatura_cliente_img"), "")

    bloco_img_cli = (
        f'<img src="{img_sig}" style="max-height:70px; max-width:220px;" alt="Assinatura Cliente"/>'
        if img_sig.startswith("data:image")
        else '<div style="height:50px; line-height:50px; color:#64748b;">(Assinatura Digital Registada)</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Ordem de Serviço #{id_os_c} - EMED Eletromedicina</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; color: #0f172a; margin: 24px; background: #ffffff; }}
  .os-box {{ border: 2px solid #0b132b; border-radius: 8px; padding: 20px; max-width: 860px; margin: auto; }}
  .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0b132b; padding-bottom: 12px; margin-bottom: 14px; }}
  .title {{ font-size: 20px; font-weight: bold; color: #0b132b; }}
  .badge {{ background: #10b981; color: #fff; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 13px; }}
  .sec-title {{ background: #1c2541; color: #64dfdf; padding: 6px 10px; font-weight: bold; font-size: 13px; border-radius: 4px; margin-top: 12px; margin-bottom: 8px; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 6px; }}
  td, th {{ border: 1px solid #cbd5e1; padding: 7px 9px; text-align: left; vertical-align: top; }}
  .label {{ font-weight: bold; color: #334155; width: 22%; background: #f8fafc; }}
  .sigs {{ display: flex; gap: 20px; margin-top: 18px; }}
  .sig-card {{ flex: 1; border: 1px solid #94a3b8; border-radius: 6px; padding: 12px; text-align: center; font-size: 12px; }}
  @media print {{ .no-print {{ display: none; }} body {{ margin: 0; }} }}
</style>
</head>
<body>
<div class="os-box">
  <div class="header">
    <div>
      <div class="title">🏥 EMED ELETROMEDICINA LTDA.</div>
      <div style="font-size:12px; color:#475569;">Engenharia Clínica, Manutenção Preventiva, Corretiva e Calibração</div>
    </div>
    <div style="text-align:right;">
      <div class="title">ORDEM DE SERVIÇO Nº #{id_os_c}</div>
      <span class="badge">STATUS: CONCLUÍDA</span>
    </div>
  </div>

  <div class="sec-title">1. Dados do Cliente, Endereço & Tipo de Serviço</div>
  <table>
    <tr>
      <td class="label">Nome do Cliente:</td><td><b>{cliente}</b> (CNPJ: {cnpj})</td>
      <td class="label">Tipo de Serviço:</td><td><b>{tipo_srv}</b></td>
    </tr>
    <tr>
      <td class="label">Endereço do Cliente:</td><td>{endereco} — {cidade}/{estado}</td>
      <td class="label">Equipamento:</td><td><b>{equipamento}</b></td>
    </tr>
    <tr>
      <td class="label">Responsável / E-mail:</td><td>{resp_hosp} ({email_cli})</td>
      <td class="label">Data / Horários:</td><td>Data: {dt_agend} | In: {cin} | Out: {cout} ({dur})</td>
    </tr>
    <tr>
      <td class="label">Técnico Principal:</td><td><b>{tec_princ}</b></td>
      <td class="label">Técnico(s) Auxiliar(es):</td><td><b>{tec_aux}</b></td>
    </tr>
  </table>

  <div class="sec-title">2. Serviços Executados, Diagnóstico & Formulários (POP/IT)</div>
  <table>
    <tr><td class="label">Defeito Relatado:</td><td colspan="3">{def_rel}</td></tr>
    <tr><td class="label">Problemas / Causa:</td><td colspan="3">{prob_enc} (Causa Raiz: {causa_r})</td></tr>
    <tr><td class="label">Serviços Executados:</td><td colspan="3"><b>{srv_exec}</b></td></tr>
    <tr><td class="label">Formulário Checklist POP:</td><td colspan="3">{chk_pop} (Etapa: {etapa_prev})</td></tr>
    <tr><td class="label">Parâmetros Medidos:</td><td colspan="3">{param_m}</td></tr>
  </table>

  <div class="sec-title">3. Observações, Pendências & Condição Final</div>
  <table>
    <tr><td class="label">Observações Gerais:</td><td colspan="3">{obs_ger}</td></tr>
    <tr><td class="label">Pendências / Histórico:</td><td colspan="3">{pend_txt}</td></tr>
    <tr>
      <td class="label">Condição na Saída:</td><td><b>{cond_fin}</b></td>
      <td class="label">Faturamento:</td><td>{cond_pag}</td>
    </tr>
  </table>

  <div class="sec-title">4. Assinaturas e Validação Técnica</div>
  <div class="sigs">
    <div class="sig-card">
      <div style="font-family:'Brush Script MT',cursive; font-size:22px; color:#0f766e;">{tec_princ.title()}</div>
      <hr style="border:0; border-top:1px solid #94a3b8; margin:6px 0;"/>
      <b>{ass_tec}</b><br/>
      Técnico Auxiliar: {tec_aux}<br/>
      <span style="color:#64748b;">Equipa Técnica EMED Eletromedicina</span>
    </div>
    <div class="sig-card">
      {bloco_img_cli}
      <hr style="border:0; border-top:1px solid #94a3b8; margin:6px 0;"/>
      <b>{ass_cli}</b><br/>
      <span style="color:#64748b;">Assinatura do Cliente / Responsável Local</span>
    </div>
  </div>
</div>
</body>
</html>"""


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
            chamado_cliente = st.selectbox("1. Nome do Cliente (Unidade / Hospital ou Setor Interno) *", clientes_disponiveis)
            linhas_cli_sel = df[df['cliente'] == chamado_cliente]
            info_cli_sel = linhas_cli_sel.iloc[0] if not linhas_cli_sel.empty else {}
            end_padrao_cli = limpar_texto(info_cli_sel.get('endereco'), 'SEDE EMED')
            email_padrao_cli = limpar_texto(info_cli_sel.get('email'), '')

            endereco_abertura = st.text_input("1.1 Endereço do Cliente / Local de Atendimento *", value=end_padrao_cli)
            email_abertura = st.text_input("1.2 E-mail do Cliente (para envio da OS)", value=email_padrao_cli, placeholder="contato@hospital.com.br")

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
            chamado_tec = st.selectbox("5. Técnico Responsável Principal", lista_tecs_ch, index=idx_tec_def)
            chamado_tec_aux = st.multiselect(
                "5.1 Técnico(s) Auxiliar(es) (Opcional — quando sair mais de uma pessoa)",
                options=lista_tecs_ch,
                default=[],
                help="Selecione um ou mais técnicos auxiliares caso a intervenção exija equipa dupla/múltipla."
            )
            instrumento_abertura = st.text_input(
                "5.2 Instrumento / Ferramenta Especial Necessária",
                placeholder="EX: MULTÍMETRO FLUKE, FANTOMA, CHAVE DINAMOMÉTRICA"
            )

        st.markdown("#### 🔬 Pré-Atendimento, Defeito Relatado, Formulários & Anexos (Foto / Vídeo)")
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
            formulario_abertura = st.file_uploader("📋 Anexar Formulário Técnico / POP / Checklist (PDF/DOCX/XLSX/Imagem)", type=["pdf", "docx", "xlsx", "png", "jpg", "jpeg"])
            obs_abertura = st.text_input("Observações de Acesso / Horário / Sala (Opcional)", placeholder="EX: PROCURAR ENF. CHEFE NO 2º ANDAR")

        chamado_relato = st.text_area("6. Defeito Relatado pelo Cliente / Escopo do Serviço *", placeholder="Descreva o defeito relatado pelo hospital ou os pontos a verificar...")
        c_mid1, c_mid2 = st.columns(2)
        with c_mid1:
            foto_arquivo = st.file_uploader("📸 Anexar Foto Inicial / Evidência (Opcional)", type=["png", "jpg", "jpeg"])
        with c_mid2:
            video_arquivo = st.file_uploader("🎥 Anexar Vídeo do Equipamento / Defeito (MP4/MOV/WEBM/AVI - Opcional)", type=["mp4", "mov", "webm", "avi"])
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
                aux_lista_limpa = [t for t in chamado_tec_aux if t != chamado_tec]
                str_tec_aux = ", ".join(aux_lista_limpa)

                pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                os.makedirs(pasta_uploads, exist_ok=True)

                caminho_foto_salva = ""
                if foto_arquivo is not None:
                    caminho_foto_salva = os.path.join(pasta_uploads, foto_arquivo.name)
                    with open(caminho_foto_salva, "wb") as f:
                        f.write(foto_arquivo.getbuffer())

                caminho_video_salvo = ""
                if video_arquivo is not None:
                    caminho_video_salvo = os.path.join(pasta_uploads, f"VID_{video_arquivo.name}")
                    with open(caminho_video_salvo, "wb") as f:
                        f.write(video_arquivo.getbuffer())

                caminho_form_salvo = ""
                if formulario_abertura is not None:
                    caminho_form_salvo = os.path.join(pasta_uploads, f"FORM_{formulario_abertura.name}")
                    with open(caminho_form_salvo, "wb") as f:
                        f.write(formulario_abertura.getbuffer())

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
                    'endereco': endereco_abertura.strip().upper() or limpar_texto(info_cli_base.get('endereco'), 'SEDE EMED').upper(),
                    'tipo_servico': chamado_tipo.upper(),
                    'data_agendamento': pd.to_datetime(chamado_data).strftime('%Y-%m-%d'),
                    'tecnico_responsavel': chamado_tec.upper(),
                    'tecnico_auxiliar': str_tec_aux.upper(),
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
                    'video_evidencia': caminho_video_salvo,
                    'formulario_anexo': caminho_form_salvo,
                    'cnpj': limpar_texto(info_cli_base.get('cnpj'), ''),
                    'cep': limpar_texto(info_cli_base.get('cep'), ''),
                    'email': email_abertura.strip() or limpar_texto(info_cli_base.get('email'), ''),
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
    import urllib.parse
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("#### 📁 Ordens de Serviço Fechadas (Formatadas, E-mail, Fotos/Vídeo, Formulários & Reabertura)")
    df_os_concluidas = df[df['status'].astype(str).str.upper() == 'CONCLUÍDO']
    if df_os_concluidas.empty:
        st.info("ℹ️ Ainda não existem ordens de serviço concluídas.")
    else:
        for idx_c, row_c in df_os_concluidas.iterrows():
            id_os_c = obter_id_os(idx_c, row_c)
            tec_hist_c = limpar_texto(row_c.get('tecnico_responsavel'), 'N/D')
            tec_aux_c = limpar_texto(row_c.get('tecnico_auxiliar'), '')
            txt_aux_header = f" + Aux: {tec_aux_c}" if tec_aux_c else ""
            tipo_srv_c = limpar_texto(row_c.get('tipo_servico'), 'MANUTENÇÃO')
            titulo_exp_c = (
                f"✅ OS #{id_os_c} | {row_c['cliente']} — {row_c['equipamento']} "
                f"[{tipo_srv_c}] [Técnico: {tec_hist_c}{txt_aux_header}]"
            )
            with st.expander(titulo_exp_c, expanded=(idx_c == df_os_concluidas.index[0])):
                cli_nome_c = limpar_texto(row_c.get('cliente'), '-')
                cli_end_c = limpar_texto(row_c.get('endereco'), 'ENDEREÇO NÃO INFORMADO')
                cli_cid_c = limpar_texto(row_c.get('cidade'), 'FORTALEZA')
                cli_uf_c = limpar_texto(row_c.get('estado'), 'CE')
                cli_cnpj_c = limpar_texto(row_c.get('cnpj'), 'N/D')
                cli_email_c = limpar_texto(row_c.get('email'), '')
                cli_resp_c = limpar_texto(row_c.get('responsavel_hospital'), '-')
                laudo_hist = limpar_texto(row_c.get('pendencias'), '-')
                etapa_hist = limpar_texto(row_c.get('etapa_preventiva'), 'GERAL')
                ass_cli_hist = limpar_texto(row_c.get('assinatura_cliente'), cli_resp_c)
                def_rel_h = limpar_texto(row_c.get('defeito_relatado'), '-')
                prob_enc_h = limpar_texto(row_c.get('problemas_encontrados'), '-')
                srv_exec_h = limpar_texto(row_c.get('servico_executado'), laudo_hist)
                obs_ger_h = limpar_texto(row_c.get('observacoes_gerais'), 'SEM OBSERVAÇÕES ADICIONAIS')
                param_h = limpar_texto(row_c.get('parametros_medidos'), '-')
                cond_f_h = limpar_texto(row_c.get('condicao_final'), 'LIBERADO PARA USO NORMAL')
                chk_pop_h = limpar_texto(row_c.get('checklist_pop'), '')
                dt_ag_h = limpar_texto(row_c.get('data_agendamento'), '-')
                cin_h = limpar_texto(row_c.get('checkin_hora'), '-')
                cout_h = limpar_texto(row_c.get('checkout_hora'), '-')
                dur_h = limpar_texto(row_c.get('tempo_atendimento'), '-')

                # CARTÃO VISUAL DA OS FECHADA FORMATADA
                st.markdown(
                    f"""
                    <div style="background:#141c35; border:1.5px solid #64dfdf; border-radius:12px; padding:18px; margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #3a506b; padding-bottom:10px; margin-bottom:12px;">
                            <div>
                                <span style="font-size:18px; font-weight:800; color:#64dfdf !important;">🏥 ORDEM DE SERVIÇO FECHADA Nº #{id_os_c}</span><br/>
                                <span style="font-size:12px; color:#94a3b8 !important;">📅 Data: {dt_ag_h} | 📍 Check-in: {cin_h} | 🏁 Check-out: {cout_h} ({dur_h})</span>
                            </div>
                            <div style="text-align:right;">
                                <span style="background:#0f766e; color:#64dfdf !important; border:1px solid #10b981; padding:4px 10px; border-radius:8px; font-weight:700; font-size:12px;">
                                    🔧 TIPO DE SERVIÇO: {tipo_srv_c}
                                </span>
                            </div>
                        </div>
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; font-size:13px;">
                            <div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b;">
                                <b style="color:#64dfdf !important;">🏥 NOME E ENDEREÇO DO CLIENTE:</b><br/>
                                <b>Cliente:</b> {cli_nome_c} (CNPJ: {cli_cnpj_c})<br/>
                                <b>Endereço:</b> {cli_end_c} — {cli_cid_c}/{cli_uf_c}<br/>
                                <b>Responsável Local:</b> {cli_resp_c} | <b>E-mail:</b> {cli_email_c or 'Não informado'}
                            </div>
                            <div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b;">
                                <b style="color:#64dfdf !important;">👷 EQUIPA TÉCNICA & EQUIPAMENTO:</b><br/>
                                <b>Equipamento:</b> {row_c['equipamento']}<br/>
                                <b>Técnico Principal:</b> {tec_hist_c}<br/>
                                <b>Técnico(s) Auxiliar(es):</b> {tec_aux_c if tec_aux_c else 'NENHUM (ATENDIMENTO INDIVIDUAL)'}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                ch1, ch2 = st.columns(2)
                with ch1:
                    st.markdown("##### 🛠️ Serviços Executados & Diagnóstico")
                    st.markdown(f"**📢 Defeito Relatado:** {def_rel_h}")
                    st.markdown(f"**🔍 Problemas Encontrados:** {prob_enc_h}")
                    st.markdown(f"**🛠️ Serviços Executados:** {srv_exec_h}")
                    st.markdown(f"**⚡ Parâmetros / Medições:** `{param_h}`")
                with ch2:
                    st.markdown("##### 📝 Observações, Pendências & Formulários")
                    st.markdown(f"**📝 Observações:** {obs_ger_h}")
                    st.markdown(f"**🚨 Pendência / Histórico:** {laudo_hist}")
                    st.markdown(f"**🏁 Condição Final:** `{cond_f_h}`")
                    st.markdown(f"**📋 Formulário Checklist POP/IT ({etapa_hist}):** `{chk_pop_h if chk_pop_h else 'Padrão Concluído'}`")
                    if limpar_texto(row_c.get('condicao_pagamento')):
                        st.markdown(f"💰 **Faturamento:** `{row_c.get('condicao_pagamento')}`")

                # Anexos de Formulários e Orçamentos
                form_anexo_c = limpar_texto(row_c.get('formulario_anexo'), '')
                orc_anexo_c = limpar_texto(row_c.get('orcamento_anexo'), '')
                if form_anexo_c or orc_anexo_c:
                    c_anx1, c_anx2 = st.columns(2)
                    with c_anx1:
                        if form_anexo_c and os.path.exists(form_anexo_c):
                            with open(form_anexo_c, "rb") as ff:
                                st.download_button(
                                    f"📋 Baixar Formulário Anexado ({os.path.basename(form_anexo_c)})",
                                    data=ff,
                                    file_name=os.path.basename(form_anexo_c),
                                    key=f"dl_form_c_{idx_c}",
                                )
                    with c_anx2:
                        if orc_anexo_c and os.path.exists(orc_anexo_c):
                            with open(orc_anexo_c, "rb") as fo:
                                st.download_button(
                                    f"📄 Baixar Orçamento Aprovado ({os.path.basename(orc_anexo_c)})",
                                    data=fo,
                                    file_name=os.path.basename(orc_anexo_c),
                                    key=f"dl_orc_c_{idx_c}",
                                )

                # Fotos e Vídeos da Intervenção
                f_ant_c = limpar_texto(row_c.get('foto_evidencia'), '')
                f_dep_c = limpar_texto(row_c.get('foto_depois'), '')
                vid_c = limpar_texto(row_c.get('video_evidencia'), '')
                if (f_ant_c and os.path.exists(f_ant_c)) or (f_dep_c and os.path.exists(f_dep_c)) or (vid_c and os.path.exists(vid_c)):
                    st.markdown("---")
                    st.markdown("##### 📸 Anexo de Fotos & 🎥 Vídeo da Intervenção")
                    cf1, cf2, cf3 = st.columns(3)
                    with cf1:
                        if f_ant_c and os.path.exists(f_ant_c):
                            st.image(f_ant_c, caption="Foto Antes / Evidência Inicial", width=240)
                    with cf2:
                        if f_dep_c and os.path.exists(f_dep_c):
                            st.image(f_dep_c, caption="Foto Depois / Serviço Concluído", width=240)
                    with cf3:
                        if vid_c and os.path.exists(vid_c):
                            st.video(vid_c)
                            st.caption(f"🎥 Vídeo: {os.path.basename(vid_c)}")

                st.markdown("---")
                st.markdown("##### ✍️ Assinatura Técnica (Principal + Auxiliar) & Assinatura do Cliente")
                ca_h1, ca_h2 = st.columns(2)
                with ca_h1:
                    renderizar_rubrica_tecnico(tec_hist_c, equipa_tecnica)
                    if tec_aux_c:
                        st.caption(f"🤝 **Técnico(s) Auxiliar(es) Participante(s):** `{tec_aux_c}`")
                with ca_h2:
                    st.markdown(f"**Responsável no Cliente:** `{ass_cli_hist}`")
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
                    else:
                        st.caption("ℹ️ Assinatura validada nominalmente pelo responsável local.")

                # OPÇÃO DE ENVIO POR E-MAIL & FICHA OFICIAL A4
                st.markdown("---")
                st.markdown("##### 📧 Envio da OS por E-mail ao Cliente & Impressão da Ficha Oficial")
                c_em1, c_em2, c_em3 = st.columns([2.2, 1.4, 1.4])
                with c_em1:
                    email_dest_in = st.text_input(
                        "E-mail do Cliente / Destinatário",
                        value=cli_email_c,
                        placeholder="engenharia@hospital.com.br",
                        key=f"em_dest_c_{idx_c}",
                    )
                assunto_email = f"Ordem de Servico #{id_os_c} Concluida - EMED Eletromedicina ({cli_nome_c})"
                corpo_email = (
                    f"Prezado(a) {cli_resp_c} ({cli_nome_c}),\n\n"
                    f"Segue o resumo da Ordem de Serviço #{id_os_c} concluída pela EMED Eletromedicina:\n\n"
                    f"• Cliente: {cli_nome_c}\n"
                    f"• Endereço: {cli_end_c} - {cli_cid_c}/{cli_uf_c}\n"
                    f"• Equipamento: {row_c['equipamento']}\n"
                    f"• Tipo de Serviço: {tipo_srv_c} ({etapa_hist})\n"
                    f"• Técnico Principal: {tec_hist_c} | Técnico Auxiliar: {tec_aux_c or 'Nenhum'}\n"
                    f"• Serviços Executados: {srv_exec_h}\n"
                    f"• Formulário / Checklist POP: {chk_pop_h or 'Realizado'}\n"
                    f"• Observações: {obs_ger_h}\n"
                    f"• Pendências / Status Final: {cond_f_h}\n"
                    f"• Assinatura Responsável Local: {ass_cli_hist}\n\n"
                    f"Atenciosamente,\nEMED Eletromedicina Ltda."
                )
                link_mailto = (
                    f"mailto:{urllib.parse.quote(email_dest_in.strip())}?"
                    f"subject={urllib.parse.quote(assunto_email)}&"
                    f"body={urllib.parse.quote(corpo_email)}"
                )
                html_ficha_os = _gerar_html_os_formatada(str(id_os_c), row_c, equipa_tecnica)

                with c_em2:
                    if st.button("📧 Enviar OS por E-mail Agora", key=f"btn_send_em_{idx_c}", type="primary", use_container_width=True):
                        if not email_dest_in.strip():
                            st.warning("⚠️ Informe o endereço de e-mail do cliente no campo ao lado!")
                        else:
                            df.at[idx_c, 'email'] = email_dest_in.strip()
                            salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                            st.success(f"✅ E-mail da OS #{id_os_c} preparado/registado para **{email_dest_in.strip()}**!")
                            st.markdown(
                                f'<a href="{link_mailto}" target="_blank" style="display:inline-block; background:#10b981; color:#0b132b; font-weight:bold; padding:8px 14px; border-radius:6px; text-decoration:none; margin-top:4px;">📨 Clique aqui para abrir no seu Cliente de E-mail já preenchido</a>',
                                unsafe_allow_html=True,
                            )
                with c_em3:
                    st.download_button(
                        label="🖨️ Baixar Ficha da OS (A4/PDF)",
                        data=html_ficha_os.encode("utf-8"),
                        file_name=f"OS_{id_os_c}_{limpar_texto(cli_nome_c, 'EMED').replace(' ', '_')}.html",
                        mime="text/html",
                        key=f"dl_html_os_{idx_c}",
                        use_container_width=True,
                    )

                st.markdown("---")
                st.markdown("##### 🔄 Reabrir OS / Transferir Pendência para Outro Técnico")
                with st.form(f"form_reabrir_os_{idx_c}"):
                    lista_t_reab = sorted(list(equipa_tecnica.keys()))
                    c_r1, c_r2 = st.columns(2)
                    with c_r1:
                        tec_reab = st.selectbox("Selecionar Novo Técnico Responsável", lista_t_reab, key=f"reab_t_{idx_c}")
                    with c_r2:
                        tec_aux_reab = st.multiselect("Técnico(s) Auxiliar(es) na Reabertura (Opcional)", lista_t_reab, key=f"reab_aux_{idx_c}")
                    motivo_reab = st.text_input(
                        "Pendência / O que falta realizar (Ficará visível junto ao histórico anterior)",
                        key=f"reab_m_{idx_c}"
                    )
                    inst_reab = st.text_input("Instrumento / Material Necessário para levar", key=f"reab_i_{idx_c}")
                    if st.form_submit_button("🔓 Reabrir OS no Nome do Novo Técnico", type="primary"):
                        df.at[idx_c, 'status'] = 'ATIVO'
                        df.at[idx_c, 'tecnico_responsavel'] = tec_reab
                        df.at[idx_c, 'tecnico_auxiliar'] = ", ".join([t for t in tec_aux_reab if t != tec_reab])
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

            tec_aux_os_atual = limpar_texto(row_os.get('tecnico_auxiliar'), '')
            end_os_atual = limpar_texto(row_os.get('endereco'), 'SEDE EMED')
            cid_os_atual = limpar_texto(row_os.get('cidade'), 'FORTALEZA')
            uf_os_atual = limpar_texto(row_os.get('estado'), 'CE')
            email_os_atual = limpar_texto(row_os.get('email'), '')
            txt_aux_ativo = f" + Aux: {tec_aux_os_atual}" if tec_aux_os_atual else ""

            titulo_os_ativa = f"🛠️ OS #{id_os_ativa} | {cli_os_atual} — Equipamento: {eq_os_atual} [{srv_os_atual}] [Técnico: {tec_resp_os}{txt_aux_ativo}]"
            with st.expander(titulo_os_ativa):
                st.markdown(
                    f"""
                    <div style="background:#141c35; border-left:4px solid #64dfdf; border-radius:8px; padding:10px 14px; margin-bottom:10px; font-size:13px;">
                        <b>🏥 Cliente:</b> {cli_os_atual} &nbsp;|&nbsp; <b>📍 Endereço:</b> {end_os_atual} ({cid_os_atual}/{uf_os_atual}) &nbsp;|&nbsp;
                        <b>🔧 Tipo de Serviço:</b> <span style="color:#64dfdf !important; font-weight:bold;">{srv_os_atual}</span> &nbsp;|&nbsp;
                        <b>📅 Data:</b> {dt_os_atual}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                c_top1, c_top2, c_top3 = st.columns([2.4, 1.3, 1.3])
                with c_top1:
                    if inst_os_atual:
                        st.markdown(f"📐 **Instrumento / Material Requerido:** `{inst_os_atual}`")
                    lista_tecs_exec = sorted(list(equipa_tecnica.keys()))
                    idx_t_exec = lista_tecs_exec.index(tec_resp_os) if tec_resp_os in lista_tecs_exec else 0
                    c_t1, c_t2 = st.columns(2)
                    with c_t1:
                        novo_tec_exec = st.selectbox(
                            "👷 Técnico Responsável Principal",
                            lista_tecs_exec,
                            index=idx_t_exec,
                            key=f"sel_tec_exec_{idx_os}"
                        )
                    with c_t2:
                        aux_salvos_lista = [
                            x.strip().upper()
                            for x in tec_aux_os_atual.split(",")
                            if x.strip().upper() in lista_tecs_exec
                        ]
                        novos_tecs_aux = st.multiselect(
                            "🤝 Técnico(s) Auxiliar(es) (Se sair +1 pessoa)",
                            options=lista_tecs_exec,
                            default=aux_salvos_lista,
                            key=f"sel_tec_aux_{idx_os}",
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
                    "📢 1. Cliente & Defeito",
                    "🔍 2. Problemas Encontrados",
                    "🛠️ 3. Serviços & Formulários",
                    "🚨 4. Pendências & Obs.",
                    "📸 5. Fotos, Vídeo & Anexos",
                    "✍️ 6. Assinatura, E-mail & Fecho"
                ])

                with m_tab1:
                    st.markdown("##### 🏥 Dados do Cliente, Endereço, Tipo de Serviço & Defeito Relatado")
                    c_cli1, c_cli2, c_cli3 = st.columns([2.0, 1.5, 1.5])
                    with c_cli1:
                        endereco_exec_in = st.text_input(
                            "📍 Endereço do Cliente / Local do Atendimento",
                            value=end_os_atual,
                            key=f"end_exec_{idx_os}",
                        )
                    with c_cli2:
                        email_exec_in = st.text_input(
                            "📧 E-mail do Cliente (para envio da OS)",
                            value=email_os_atual,
                            placeholder="engenharia@hospital.com.br",
                            key=f"em_exec_{idx_os}",
                        )
                    with c_cli3:
                        opcoes_tipo_srv_exec = [
                            "PREVENTIVA (COM CHECKLIST POP/IT)",
                            "CORRETIVA (FALHA / PARADA)",
                            "INSTALAÇÃO",
                            "CALIBRAÇÃO",
                            "SERVIÇO INTERNO EMED",
                        ]
                        if srv_os_atual.upper() not in opcoes_tipo_srv_exec:
                            opcoes_tipo_srv_exec.insert(0, srv_os_atual.upper())
                        tipo_srv_exec_in = st.selectbox(
                            "🔧 Tipo de Serviço",
                            opcoes_tipo_srv_exec,
                            index=opcoes_tipo_srv_exec.index(srv_os_atual.upper()),
                            key=f"tsrv_exec_{idx_os}",
                        )

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
                    st.markdown("##### 🛠️ Serviços Executados, Formulários (Checklist POP/IT) & Aplicação de Peças")
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
                            "📋 Formulário / Checklist POP de Procedimentos Realizados",
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
                        "🛠️ Serviços Executados / Solução Técnica Aplicada *",
                        value=srv_exec_atual,
                        placeholder="Relate todos os serviços executados, ajustes, reparos e testes finais...",
                        height=110,
                        key=f"obs_f_{idx_os}"
                    )

                with m_tab4:
                    st.markdown("##### 🚨 Status de Pendências, Condição de Saída & Observações ao Cliente")
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
                        "📐 Pendência / Instrumento ou Peça necessária para a próxima visita (se ficar pendente)",
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
                    st.markdown("##### 📸 Anexo de Fotos (Antes / Depois), 🎥 Vídeo, 📋 Formulários & 📄 Orçamento")
                    cf_up1, cf_up2 = st.columns(2)
                    with cf_up1:
                        foto_antes_up = st.file_uploader(
                            "📸 Foto Antes / Defeito (PNG/JPG)",
                            type=["png", "jpg", "jpeg"],
                            key=f"f_ant_up_{idx_os}"
                        )
                        f_ant_salva = limpar_texto(row_os.get('foto_evidencia'), '')
                        if f_ant_salva and os.path.exists(f_ant_salva):
                            st.image(f_ant_salva, caption="Foto Inicial Salva", width=200)

                        video_exec_up = st.file_uploader(
                            "🎥 Anexo de Vídeo da Intervenção / Teste (MP4/MOV/WEBM/AVI)",
                            type=["mp4", "mov", "webm", "avi"],
                            key=f"vid_up_{idx_os}"
                        )
                        vid_salvo_at = limpar_texto(row_os.get('video_evidencia'), '')
                        if vid_salvo_at and os.path.exists(vid_salvo_at):
                            st.video(vid_salvo_at)
                    with cf_up2:
                        foto_depois_up = st.file_uploader(
                            "📸 Foto Depois / Serviço Pronto (PNG/JPG)",
                            type=["png", "jpg", "jpeg"],
                            key=f"f_dep_up_{idx_os}"
                        )
                        f_dep_salva = limpar_texto(row_os.get('foto_depois'), '')
                        if f_dep_salva and os.path.exists(f_dep_salva):
                            st.image(f_dep_salva, caption="Foto Final Salva", width=200)

                        formulario_exec_up = st.file_uploader(
                            "📋 Anexar Formulário Técnico / Checklist / Certificado (PDF/DOCX/XLSX/Imagem)",
                            type=["pdf", "docx", "xlsx", "png", "jpg", "jpeg"],
                            key=f"form_up_{idx_os}"
                        )
                        form_salvo_at = limpar_texto(row_os.get('formulario_anexo'), '')
                        if form_salvo_at:
                            st.caption(f"📋 Formulário atual: `{os.path.basename(form_salvo_at)}`")

                        orcamento_fecho_up = st.file_uploader(
                            "📄 Orçamento Aprovado (PDF/Imagem)",
                            type=["pdf", "png", "jpg", "jpeg"],
                            key=f"orc_up_{idx_os}"
                        )
                        orc_salvo_at = limpar_texto(row_os.get('orcamento_anexo'), '')
                        if orc_salvo_at:
                            st.caption(f"📎 Orçamento atual: `{os.path.basename(orc_salvo_at)}`")

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
                        aux_limpos_display = [t for t in novos_tecs_aux if t != novo_tec_exec]
                        if aux_limpos_display:
                            st.caption(f"🤝 **Técnico(s) Auxiliar(es):** `{', '.join(aux_limpos_display)}`")
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
                        st.error("⚠️ Preencha os Serviços Executados (Aba 3) e o Nome do Responsável no Hospital (Aba 6)!")
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

                            if video_exec_up is not None:
                                caminho_vid_exec = os.path.join(pasta_uploads, f"VID_OS{id_os_ativa}_{video_exec_up.name}")
                                with open(caminho_vid_exec, "wb") as f:
                                    f.write(video_exec_up.getbuffer())
                                df.at[idx_os, 'video_evidencia'] = caminho_vid_exec

                            if formulario_exec_up is not None:
                                caminho_form_exec = os.path.join(pasta_uploads, f"FORM_OS{id_os_ativa}_{formulario_exec_up.name}")
                                with open(caminho_form_exec, "wb") as f:
                                    f.write(formulario_exec_up.getbuffer())
                                df.at[idx_os, 'formulario_anexo'] = caminho_form_exec

                            if orcamento_fecho_up is not None:
                                caminho_orc_fecho = os.path.join(pasta_uploads, f"ORC_OS{id_os_ativa}_{orcamento_fecho_up.name}")
                                with open(caminho_orc_fecho, "wb") as f:
                                    f.write(orcamento_fecho_up.getbuffer())
                                df.at[idx_os, 'orcamento_anexo'] = caminho_orc_fecho

                            fechar_definitivo = "CONCLUÍDO" in status_fecho_escolha
                            resumo_pag = f"{opcao_faturamento} — VALOR FINAL: R$ {valor_final_faturar:,.2f}"
                            str_aux_final = ", ".join([t for t in novos_tecs_aux if t != novo_tec_exec])

                            df.at[idx_os, 'endereco'] = endereco_exec_in.strip().upper()
                            df.at[idx_os, 'email'] = email_exec_in.strip()
                            df.at[idx_os, 'tipo_servico'] = tipo_srv_exec_in.strip().upper()
                            df.at[idx_os, 'tecnico_responsavel'] = novo_tec_exec
                            df.at[idx_os, 'tecnico_auxiliar'] = str_aux_final
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
