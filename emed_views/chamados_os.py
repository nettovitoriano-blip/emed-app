import base64
import datetime
import json
import os
import urllib.parse
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
    KITS_INSTRUMENTOS_POR_SITUACAO,
    obter_kit_por_servico,
    acionar_separacao_automatica_almoxarifado,
    registrar_aplicacao_definitiva_e_fluxo_cobranca,
    registrar_peca_em_teste_observacao,
    converter_teste_em_aplicacao_definitiva_e_cobranca,
    retirar_peca_teste_e_devolver_estoque,
    salvar_rascunho_provisorio,
    obter_rascunho_provisorio,
    limpar_rascunho_provisorio,
    obter_configuracao,
    salvar_configuracao,
    gerar_sugestao_relatorio_clinico,
    obter_checklist_acoes_sugeridas,
    TEMPLATES_RELATORIO_TECNICO,
)
from emed_services import (
    AppContext,
    carregar_clientes_internos,
    calcular_duracao_os,
    salvar_dados_seguro,
    vincular_it_ao_equipamento,
    converter_html_para_pdf_bytes,
    gerar_link_whatsapp,
)
from emed_ui import (
    gerar_html_coletor_offline,
    renderizar_rubrica_tecnico,
    renderizar_quadro_assinatura_cliente,
)
from emed_views.pesquisa_satisfacao import URL_GOOGLE_REVIEW_OFICIAL


def _obter_logo_base64() -> str:
    """Retorna o base64 da logo oficial da EMED (emed1.jpg) para renderização inline sem quebras em HTML e Streamlit."""
    caminhos = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "emed1.jpg"),
        os.path.join(os.getcwd(), "emed1.jpg"),
        "emed1.jpg",
    ]
    for c in caminhos:
        if os.path.exists(c):
            try:
                with open(c, "rb") as f:
                    return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            except Exception:
                pass
    return ""


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


def _limpar_telefone_exibicao(val: str) -> str:
    """Remove sufixo '.0' de telefones lidos como float pelo pandas/Excel."""
    s = limpar_texto(val, "")
    if s.endswith(".0"):
        s = s[:-2]
    return s.strip() or "N/D"


def _formatar_data_br(dt_str: str) -> str:
    """Converte datas YYYY-MM-DD para DD/MM/AAAA."""
    s = limpar_texto(dt_str, "-")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        partes = s[:10].split("-")
        if len(partes) == 3:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return s


def _extrair_pendencia_limpa(row_c: pd.Series) -> str:
    """Extrai apenas a pendência técnica real, sem duplicar o relatório de serviço executado ou faturamento."""
    inst_nec = limpar_texto(row_c.get("instrumento_necessario"), "")
    raw_pend = limpar_texto(row_c.get("pendencias"), "")

    if inst_nec and inst_nec.upper() not in ["-", "N/D", "NENHUM", "NENHUMA", "MALETA PADRÃO EMED"]:
        return inst_nec

    if not raw_pend or raw_pend.upper() in ["[CONCLUÍDO]", "CONCLUIDO", "CONCLUÍDO", "NENHUMA", "SEM PENDÊNCIAS", "-"]:
        return "Nenhuma pendência técnica. Equipamento liberado para uso normal."

    # Se foi gravado no formato composto "[CONCLUÍDO - ...] RELATORIO | [DIAGNÓSTICO...] | [FATURAMENTO...]"
    if raw_pend.upper().startswith("[CONCLUÍDO -"):
        return "Nenhuma pendência técnica. Equipamento liberado para uso normal."

    if "|" in raw_pend:
        primeiro_seg = raw_pend.split("|")[0].strip()
        if "CONCLUÍDO COM PENDÊNCIA" in primeiro_seg.upper():
            limpo = primeiro_seg.replace("[CONCLUÍDO COM PENDÊNCIA:", "[PENDÊNCIA:").strip()
            return limpo
        if primeiro_seg.upper().startswith("[CONCLUÍDO"):
            return "Nenhuma pendência técnica. Equipamento liberado para uso normal."
        return primeiro_seg

    return raw_pend


def _carregar_imagem_base64(caminho_img: str) -> str:
    """Converte uma imagem local de evidência (Foto Antes/Depois) em data URI base64 para embutir na OS/PDF."""
    c_str = limpar_texto(caminho_img, "")
    if not c_str:
        return ""
    if c_str.startswith("data:image"):
        return c_str
    base_dir = os.path.dirname(os.path.dirname(__file__))
    candidatos = [c_str, os.path.join(base_dir, c_str), os.path.join(os.getcwd(), c_str)]
    for cand in candidatos:
        if os.path.exists(cand) and os.path.isfile(cand):
            try:
                ext = os.path.splitext(cand)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                with open(cand, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                return f"data:{mime};base64,{b64}"
            except Exception:
                pass
    return ""


def _gerar_html_os_formatada(id_os_c, row_c: pd.Series = None, equipa_tecnica: dict = None) -> str:
    """Gera o documento HTML/A4 oficial da Ordem de Serviço Fechada (compatível com PDF pymupdf.Story e navegadores mobile/PC)."""
    if row_c is None and isinstance(id_os_c, (pd.Series, dict)):
        row_c = pd.Series(id_os_c)
        id_os_c = str(obter_id_os(0, row_c))
    if equipa_tecnica is None:
        equipa_tecnica = {}
    id_os_c = str(id_os_c)
    cliente = limpar_texto(row_c.get("cliente"), "N/D")
    cnpj = limpar_texto(row_c.get("cnpj"), "N/D")
    endereco = limpar_texto(row_c.get("endereco"), "N/D")
    cidade = limpar_texto(row_c.get("cidade"), "FORTALEZA")
    estado = limpar_texto(row_c.get("estado"), "CE")
    email_cli = limpar_texto(row_c.get("email"), "N/D")
    whats_cli = _limpar_telefone_exibicao(row_c.get("whatsapp") or row_c.get("contato_responsavel"))
    resp_hosp = limpar_texto(row_c.get("responsavel_hospital"), "N/D")
    equipamento = limpar_texto(row_c.get("equipamento"), "N/D")
    tipo_srv = limpar_texto(row_c.get("tipo_servico"), "MANUTENÇÃO")
    etapa_prev = limpar_texto(row_c.get("etapa_preventiva"), "GERAL")
    tec_princ = limpar_texto(row_c.get("tecnico_responsavel"), "N/D")
    tec_aux = limpar_texto(row_c.get("tecnico_auxiliar"), "NENHUM (INDIVIDUAL)")
    dt_agend = _formatar_data_br(row_c.get("data_agendamento"))
    cin = limpar_texto(row_c.get("checkin_hora"), "-")
    cout = limpar_texto(row_c.get("checkout_hora"), "-")
    dur = limpar_texto(row_c.get("tempo_atendimento"), "-")
    def_rel = limpar_texto(row_c.get("defeito_relatado"), "-")
    prob_enc = limpar_texto(row_c.get("problemas_encontrados"), "-")
    causa_r = limpar_texto(row_c.get("causa_raiz"), "-")
    raw_srv = limpar_texto(row_c.get("servico_executado"), "")
    if not raw_srv or raw_srv.upper() in ["[CONCLUÍDO]", "CONCLUIDO", "CONCLUÍDO"]:
        srv_exec = "Manutenção preventiva / corretiva executada e validada operacionalmente conforme protocolos da EMED."
    else:
        srv_exec = raw_srv
    srv_exec_html = srv_exec.replace("\n", "<br/>")
    if prob_enc.strip().upper() == srv_exec.strip().upper():
        prob_enc = "Verificado e solucionado conforme descrição técnica abaixo"

    chk_pop = limpar_texto(row_c.get("checklist_pop"), "N/A")
    param_m = limpar_texto(row_c.get("parametros_medidos"), "-")
    obs_ger = limpar_texto(row_c.get("observacoes_gerais"), "SEM OBSERVAÇÕES ADICIONAIS")
    imp_obs = str(row_c.get("imprimir_observacoes", "SIM")).upper()

    sec_num = 4
    bloco_observacoes_html = ""
    if imp_obs not in ("NAO", "NÃO", "FALSE", "0") and obs_ger and obs_ger != "SEM OBSERVAÇÕES ADICIONAIS":
        bloco_observacoes_html = f"""
  <div class="sec-title">{sec_num}. Observações Gerais &amp; Recomendações Técnicas</div>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="100%" style="padding:4px 6px; background-color:#ffffff; font-size:7.5pt; color:#1e293b; line-height:1.3;">
        {obs_ger}
      </td>
    </tr>
  </table>"""
        sec_num += 1
    pend_txt = _extrair_pendencia_limpa(row_c)

    cond_fin = limpar_texto(row_c.get("condicao_final"), "LIBERADO PARA USO NORMAL")
    cond_pag = limpar_texto(row_c.get("condicao_pagamento"), "-")
    ass_tec = limpar_texto(row_c.get("assinatura_tecnico"), f"{tec_princ} - CFT")
    ass_cli = limpar_texto(row_c.get("assinatura_cliente"), resp_hosp)
    img_sig = limpar_texto(row_c.get("assinatura_cliente_img"), "")

    logo_b64 = _obter_logo_base64()
    bloco_logo = (
        f'<img src="{logo_b64}" width="86" height="38" style="width:86px; height:38px; object-fit:contain;" alt="Logo EMED"/>'
        if logo_b64
        else '<b style="font-size:14pt; color:#0b132b;">EMED</b>'
    )

    bloco_img_cli = (
        f'<img src="{img_sig}" width="135" height="36" style="width:135px; height:36px; object-fit:contain;" alt="Assinatura Cliente"/><br/>'
        if img_sig.startswith("data:image")
        else f'<div style="font-size:9pt; font-weight:bold; color:#0b132b; padding:6px 0;">(Assinatura Coletada: {ass_cli})</div>'
    )

    horario_atend_txt = f"{cin} às {cout} ({dur})" if cin != "-" and cin else "Horário comercial"

    # Evidências Fotográficas da Intervenção Técnica
    lista_fotos_b64 = []
    for c_foto in [row_c.get("foto_evidencia"), row_c.get("foto_depois"), row_c.get("fotos_adicionais")]:
        if c_foto:
            for item in str(c_foto).split(";"):
                b64_f = _carregar_imagem_base64(item.strip())
                if b64_f and b64_f not in lista_fotos_b64:
                    lista_fotos_b64.append(b64_f)

    bloco_fotos_html = ""
    if lista_fotos_b64:
        qtd_fotos = len(lista_fotos_b64)
        largura_td = f"{100 // min(qtd_fotos, 3)}%"
        celulas = []
        for idx_f, f_b64 in enumerate(lista_fotos_b64[:3]):
            celulas.append(
                f'<td width="{largura_td}" align="center" style="text-align:center; padding:4px;">'
                f'<div style="font-size:7pt; font-weight:bold; color:#0f766e; margin-bottom:2px;">EVIDÊNCIA TÉCNICA #{idx_f+1}</div>'
                f'<img src="{f_b64}" width="165" height="88" style="width:165px; height:88px; object-fit:contain; border:1px solid #cbd5e1; border-radius:3px;" alt="Evidência #{idx_f+1}"/>'
                f'</td>'
            )
        bloco_fotos_html = f"""
  <div class="sec-title">{sec_num}. Evidências Fotográficas da Intervenção Técnica</div>
  <table class="data-tbl" width="100%">
    <tr>{''.join(celulas)}</tr>
  </table>"""
        sec_num += 1

    num_sec_aceite = str(sec_num)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Ordem de Serviço #{id_os_c} - EMED Eletromedicina</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; color: #0f172a; margin: 6px; background: #ffffff; line-height: 1.25; font-size: 8pt; }}
  .os-box {{ border: 1.5px solid #0b132b; padding: 9px 11px; max-width: 820px; margin: auto; }}
  .hdr-tbl {{ width: 100%; border-collapse: collapse; margin-bottom: 2px; }}
  .hdr-tbl td {{ border: none; padding: 1px 3px; vertical-align: middle; }}
  .os-banner {{ width: 100%; border-collapse: collapse; margin-top: 3px; margin-bottom: 5px; }}
  .os-banner td {{ background-color: #0b132b; color: #ffffff; font-size: 10.5pt; font-weight: bold; text-align: center; padding: 4px 6px; border: 1px solid #0b132b; letter-spacing: 0.5px; }}
  .sec-title {{ background-color: #1c2541; color: #ffffff; padding: 2.5px 7px; font-weight: bold; font-size: 7.5pt; margin-top: 5px; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.4px; }}
  .data-tbl {{ width: 100%; border-collapse: collapse; font-size: 7.8pt; margin-bottom: 2px; }}
  .data-tbl td {{ border: 1px solid #cbd5e1; padding: 3px 5px; text-align: left; vertical-align: top; }}
  .lbl {{ font-weight: bold; color: #334155; text-transform: uppercase; font-size: 7.2pt; }}
  .exec-box {{ background-color: #f8fafc; border: 1px solid #0f766e; padding: 4px 7px; font-size: 8pt; line-height: 1.3; color: #0b132b; }}
  @media print {{ .no-print {{ display: none; }} body {{ margin: 0; }} }}
</style>
</head>
<body>
<div class="os-box">
  <table class="hdr-tbl" width="100%">
    <tr>
      <td width="17%" align="left" valign="middle">
        {bloco_logo}
      </td>
      <td width="55%" align="left" valign="middle">
        <div style="font-size:11pt; font-weight:bold; color:#0b132b; line-height:1.15;">EMED ELETROMEDICINA LTDA.</div>
        <div style="font-size:7.5pt; color:#0f766e; font-weight:bold;">Eletromedicina • Manutenção em Equipamentos de Diagnóstico por Imagem</div>
        <div style="font-size:7pt; color:#475569;">CNPJ: 03.611.974/0001-08 • Fone: (85) 3254-2929 • Site: emed.med.br • Fortaleza - CE</div>
      </td>
      <td width="28%" align="right" valign="top" style="text-align:right;">
        <div style="font-size:8.5pt; font-weight:bold; color:#0b132b;">Data: {dt_agend}</div>
        <div style="font-size:7pt; color:#475569; margin-top:2px;">Atendimento: {horario_atend_txt}</div>
        <div style="font-size:7pt; color:#047857; font-weight:bold; margin-top:1px;">STATUS: CONCLUÍDA</div>
      </td>
    </tr>
  </table>

  <table class="os-banner" width="100%">
    <tr>
      <td width="100%" align="center">ORDEM DE SERVIÇO Nº #{id_os_c}</td>
    </tr>
  </table>

  <div class="sec-title">1. Dados do Cliente &amp; Localização</div>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="58%"><span class="lbl">Cliente:</span> <b>{cliente}</b> &nbsp;<span style="color:#475569; font-size:7.5pt;">(CNPJ: {cnpj})</span></td>
      <td width="42%"><span class="lbl">Responsável Local:</span> <b>{resp_hosp}</b></td>
    </tr>
    <tr>
      <td width="58%"><span class="lbl">Endereço:</span> {endereco} — {cidade}/{estado}</td>
      <td width="42%"><span class="lbl">Contato:</span> {email_cli} | {whats_cli}</td>
    </tr>
  </table>

  <div class="sec-title">2. Identificação do Equipamento &amp; Equipe Técnica</div>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="58%"><span class="lbl">Equipamento / Ativo:</span> <b>{equipamento}</b></td>
      <td width="42%"><span class="lbl">Tipo de Serviço:</span> <b>{tipo_srv}</b> ({etapa_prev})</td>
    </tr>
    <tr>
      <td width="58%"><span class="lbl">Técnico Principal:</span> <b>{tec_princ}</b> (CFT/CREA) &nbsp;|&nbsp; <span class="lbl">Auxiliar:</span> {tec_aux}</td>
      <td width="42%"><span class="lbl">Condição na Saída:</span> <b style="color:#047857;">✅ {cond_fin}</b></td>
    </tr>
  </table>

  <div class="sec-title">3. Diagnóstico Técnico &amp; Serviços Executados</div>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="50%"><span class="lbl">Defeito Relatado / Causa:</span> {def_rel} (Causa: {causa_r})</td>
      <td width="50%"><span class="lbl">Diagnóstico / Problema Encontrado:</span> {prob_enc}</td>
    </tr>
  </table>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="100%" class="exec-box">
        <div style="font-size:7.5pt; font-weight:bold; color:#0f766e; text-transform:uppercase; margin-bottom:2px;">🛠️ Descrição Detalhada dos Serviços Executados:</div>
        <div>{srv_exec_html}</div>
      </td>
    </tr>
  </table>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="58%"><span class="lbl">Checklist POP / Protocolo:</span> {chk_pop} (Etapa: {etapa_prev})</td>
      <td width="42%"><span class="lbl">Parâmetros / Testes:</span> {param_m}</td>
    </tr>
  </table>

  {bloco_observacoes_html}
{bloco_fotos_html}
  <div class="sec-title">{num_sec_aceite}. Termo de Aceite &amp; Validação Técnica</div>
  <table class="data-tbl" width="100%">
    <tr>
      <td width="50%" align="center" style="text-align:center; padding:6px; background-color:#fafafa;">
        <div style="font-size:10pt; font-weight:bold; font-style:italic; color:#0f766e; padding:6px 0;">{tec_princ.title()}</div>
        <div style="border-top:1px solid #94a3b8; margin:3px 15px; padding-top:3px;">
          <b>{ass_tec}</b><br/>
          {f'<span style="font-size:7pt; color:#475569;">Auxiliar: {tec_aux}</span><br/>' if tec_aux and tec_aux.upper() != 'NENHUM (INDIVIDUAL)' else ''}
          <span style="font-size:7pt; color:#64748b;">Responsável Técnico EMED Eletromedicina</span>
        </div>
      </td>
      <td width="50%" align="center" style="text-align:center; padding:6px; background-color:#fafafa;">
        {bloco_img_cli}
        <div style="border-top:1px solid #94a3b8; margin:3px 15px; padding-top:3px;">
          <b>{ass_cli}</b><br/>
          <span style="font-size:7pt; color:#64748b;">Assinatura do Cliente / Responsável Local</span>
        </div>
      </td>
    </tr>
  </table>
</div>
</body>
</html>"""


def _render_criar_nova_os(ctx: AppContext):
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    if "aviso_almox_pendente" in st.session_state:
        av = st.session_state.pop("aviso_almox_pendente")
        msg_almox = (
            f"📦 *ORDEM DE SEPARAÇÃO • ALMOXARIFADO EMED*\n\n"
            f"Técnico: {av['tecnico']}\n"
            f"Cliente: {av['cliente']}\n"
            f"Atividade: {av['tipo']}\n"
            f"Data Prevista: {av['data']}\n\n"
            f"*KIT REQUISITADO:*\n{av['kit']}\n\n"
            f"*FERRAMENTAS / INSTRUMENTOS:*\n" + "\n".join(f"• {it}" for it in av['itens'])
        )
        link_almox = f"https://wa.me/558532542929?text={urllib.parse.quote(msg_almox)}"
        st.markdown(
            f"""
            <div style="background: #0f2942; border: 1.5px solid #0284c7; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
                <div style="font-weight: bold; color: #38bdf8; font-size: 14px; margin-bottom: 6px;">
                    📦 OS Gerada! Notifique o Almoxarifado para Separar o Kit de Ferramentas:
                </div>
                <div style="color: #cbd5e1; font-size: 13px; margin-bottom: 10px;">
                    <b>{av['kit']}</b> ({len(av['itens'])} itens: {', '.join(av['itens'][:4])}...)
                </div>
                <a href="{link_almox}" target="_blank" style="display: inline-block; background: #25d366; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px;">
                    💬 Enviar Ordem de Separação no WhatsApp do Almoxarifado
                </a>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
            if chamado_tipo == "INSTALAÇÃO":
                caminho_pre = os.path.join(ctx.base_dir, "Manuais", "RAIO-X", "Formulario_Pre_Instalacao_Lotus_HF500M_Emed.pdf")
                if os.path.exists(caminho_pre):
                    try:
                        with open(caminho_pre, "rb") as f_pre:
                            dados_pre_pdf = f_pre.read()
                        st.download_button(
                            "📄 Baixar Formulário de Pré-Instalação (PDF)",
                            data=dados_pre_pdf,
                            file_name="Formulario_Pre_Instalacao_Lotus_HF500M_Emed.pdf",
                            mime="application/pdf",
                            key="btn_dl_pre_instalacao_abertura",
                            use_container_width=True,
                            help="Envie este formulário ao cliente para preenchimento prévio das condições da sala."
                        )
                    except Exception:
                        pass
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
            kit_sugerido = obter_kit_por_servico(chamado_tipo)
            instrumento_abertura = st.text_input(
                f"5.2 Sugestão de Instrumentos & Peças para o Atendimento ({kit_sugerido['nome']})",
                value=", ".join(kit_sugerido["itens"]),
                help="O Almoxarifado será acionado automaticamente pelo sistema com esta lista de materiais e ferramentas para separação imediata."
            )
            st.caption(f"⚡ **Acionamento Automático:** Ao emitir a OS, o Almoxarifado entra imediatamente em status **'A SEPARAR'** para o técnico **{chamado_tec}**.")

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
                # Trava anti-duplicação: checa se já existe chamado ativo idêntico para o cliente e equipamento
                chamado_duplicado = df[
                    (df['cliente'].astype(str).str.strip().str.upper() == chamado_cliente.strip().upper()) &
                    (df['equipamento'].astype(str).str.strip().str.upper() == equipamento_final.strip().upper()) &
                    (df['status'].astype(str).str.upper().isin(['ATIVO', 'EM ATENDIMENTO'])) &
                    (df['defeito_relatado'].astype(str).str.strip().str.upper() == chamado_relato.strip().upper())
                ]
                if not chamado_duplicado.empty:
                    idx_exist = chamado_duplicado.index[-1]
                    id_exist = obter_id_os(idx_exist, chamado_duplicado.iloc[-1])
                    st.warning(f"⚠️ **Atenção:** Já existe uma OS ativa idêntica em andamento para este equipamento (**OS #{id_exist}**). Abertura duplicada bloqueada.")
                else:
                    df = pd.concat([df, pd.DataFrame([nova_os])], ignore_index=True)
                    if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                        st.cache_data.clear()
                        novo_idx = df.index[-1]
                        id_os_gerada = obter_id_os(novo_idx, pd.Series(nova_os))

                        # Acionamento Automático do Almoxarifado para o Técnico Selecionado
                        ok_sep, msg_sep = acionar_separacao_automatica_almoxarifado(
                            ctx.db_name,
                            chamado_tec,
                            chamado_cliente,
                            equipamento_final,
                            chamado_tipo,
                            instrumento_abertura,
                            os_id=id_os_gerada
                        )

                        st.session_state.aviso_almox_pendente = {
                            "tecnico": chamado_tec,
                            "cliente": chamado_cliente,
                            "tipo": chamado_tipo,
                            "kit": kit_sugerido["nome"],
                            "itens": kit_sugerido["itens"],
                            "data": pd.to_datetime(chamado_data).strftime('%d/%m/%Y'),
                            "os_id": id_os_gerada,
                            "msg_sep": msg_sep,
                        }
                        st.success(f"✅ Salvo com sucesso! Ordem de Serviço #{id_os_gerada} emitida.")
                        if ok_sep:
                            st.info(f"📦 {msg_sep}")
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
                raw_srv_h = limpar_texto(row_c.get('servico_executado'), '')
                if not raw_srv_h or raw_srv_h.upper() in ['[CONCLUÍDO]', 'CONCLUIDO', 'CONCLUÍDO']:
                    srv_exec_h = "Manutenção preventiva / corretiva executada e validada operacionalmente conforme protocolos da EMED."
                else:
                    srv_exec_h = raw_srv_h

                obs_ger_h = limpar_texto(row_c.get('observacoes_gerais'), 'SEM OBSERVAÇÕES ADICIONAIS')
                param_h = limpar_texto(row_c.get('parametros_medidos'), '-')
                pend_h_txt = _extrair_pendencia_limpa(row_c)
                if prob_enc_h.strip().upper() == srv_exec_h.strip().upper():
                    prob_enc_h = "Verificado e solucionado conforme descrição técnica acima"
                srv_exec_h_html = srv_exec_h.replace("\n", "<br/>")

                cond_f_h = limpar_texto(row_c.get('condicao_final'), 'LIBERADO PARA USO NORMAL')
                chk_pop_h = limpar_texto(row_c.get('checklist_pop'), '')
                dt_ag_h = _formatar_data_br(row_c.get('data_agendamento'))
                cin_h = limpar_texto(row_c.get('checkin_hora'), '-')
                cout_h = limpar_texto(row_c.get('checkout_hora'), '-')
                dur_h = limpar_texto(row_c.get('tempo_atendimento'), '-')
                horario_h_txt = f"{cin_h} às {cout_h} ({dur_h})" if cin_h != "-" and cin_h else "Horário comercial"

                # FICHA TÉCNICA OFICIAL DA ORDEM DE SERVIÇO (RESPONSIVA PARA CELULAR E PC)
                logo_tela_b64 = _obter_logo_base64()
                bloco_logo_tela = (
                    f'<div style="background:#ffffff; padding:4px 8px; border-radius:6px; display:inline-flex; align-items:center; justify-content:center; flex-shrink:0; box-shadow:0 2px 5px rgba(0,0,0,0.25);">'
                    f'<img src="{logo_tela_b64}" style="height:44px; max-width:120px; object-fit:contain;" alt="Logo EMED"/>'
                    f'</div>'
                    if logo_tela_b64
                    else '<div style="background:#1c2541; padding:6px 10px; border-radius:6px; font-size:18px; font-weight:900; color:#64dfdf; border:1px solid #3a506b; flex-shrink:0;">🏥 EMED</div>'
                )

                cli_whats_c = _limpar_telefone_exibicao(row_c.get('whatsapp') or row_c.get('contato_responsavel'))
                if cli_whats_c == "N/D":
                    cli_whats_c = ""
                img_sig_cli = limpar_texto(row_c.get('assinatura_cliente_img'), '')
                bloco_img_cli_card = (
                    f'<img src="{img_sig_cli}" style="max-height:52px; max-width:210px; object-fit:contain;" alt="Assinatura Cliente"/>'
                    if img_sig_cli.startswith("data:image")
                    else f'<div style="min-height:40px; line-height:1.35; display:flex; align-items:center; justify-content:center; padding:4px 8px; font-weight:bold; color:#cbd5e1; font-size:12px;">(Assinatura Coletada: {ass_cli_hist})</div>'
                )

                # Verifica fotos anexadas para exibir dentro do card
                f_ant_b64_card = _carregar_imagem_base64(row_c.get('foto_evidencia'))
                f_dep_b64_card = _carregar_imagem_base64(row_c.get('foto_depois'))
                bloco_fotos_card_html = ""
                if f_ant_b64_card or f_dep_b64_card:
                    c_f1 = (
                        f'<div style="background:#0b132b; padding:8px; border-radius:6px; border:1px solid #233554; text-align:center;">'
                        f'<div style="font-size:10.5px; font-weight:bold; color:#cbd5e1; margin-bottom:4px;">📸 FOTO ANTES / EVIDÊNCIA INICIAL</div>'
                        f'<img src="{f_ant_b64_card}" style="max-height:170px; max-width:100%; border-radius:4px; object-fit:contain;" alt="Foto Antes"/>'
                        f'</div>'
                        if f_ant_b64_card else
                        '<div style="background:#0b132b; padding:16px; border-radius:6px; border:1px solid #233554; text-align:center; color:#64748b; font-size:11.5px;">Sem foto inicial anexada</div>'
                    )
                    c_f2 = (
                        f'<div style="background:#0b132b; padding:8px; border-radius:6px; border:1px solid #233554; text-align:center;">'
                        f'<div style="font-size:10.5px; font-weight:bold; color:#34d399; margin-bottom:4px;">📸 FOTO DEPOIS / SERVIÇO CONCLUÍDO</div>'
                        f'<img src="{f_dep_b64_card}" style="max-height:170px; max-width:100%; border-radius:4px; object-fit:contain;" alt="Foto Depois"/>'
                        f'</div>'
                        if f_dep_b64_card else
                        '<div style="background:#0b132b; padding:16px; border-radius:6px; border:1px solid #233554; text-align:center; color:#64748b; font-size:11.5px;">Sem foto final anexada</div>'
                    )
                    bloco_fotos_card_html = f"""<div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b; margin-bottom:10px;">
<div style="font-size:11px; font-weight:bold; color:#64dfdf; text-transform:uppercase; margin-bottom:6px;">📸 EVIDÊNCIAS FOTOGRÁFICAS DA INTERVENÇÃO</div>
<div class="emed-os-grid-2">{c_f1}{c_f2}</div>
</div>"""

                card_os_fechada_html = f"""<style>
.emed-os-card {{ background:#101935; border:1.8px solid #64dfdf; border-radius:12px; padding:14px; margin-bottom:14px; box-shadow:0 4px 16px rgba(0,0,0,0.35); }}
.emed-os-hdr-top {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:10px; }}
.emed-os-brand {{ display:flex; align-items:center; gap:10px; flex:1; min-width:0; }}
.emed-os-date-box {{ text-align:right; flex-shrink:0; background:#1c2541; padding:5px 10px; border-radius:6px; border:1px solid #3a506b; }}
.emed-os-center-banner {{ background:linear-gradient(90deg, #0b132b 0%, #1c2541 50%, #0b132b 100%); border:1.5px solid #64dfdf; border-radius:6px; padding:6px 10px; text-align:center; margin-bottom:10px; }}
.emed-os-grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:10px; }}
@media (max-width: 720px) {{
  .emed-os-grid-2 {{ grid-template-columns:1fr !important; gap:8px !important; }}
  .emed-os-hdr-top {{ flex-direction:row; align-items:flex-start; }}
  .emed-os-card {{ padding:10px !important; }}
}}
</style>
<div class="emed-os-card">
<div class="emed-os-hdr-top">
  <div class="emed-os-brand">
    {bloco_logo_tela}
    <div style="min-width:0;">
      <div style="font-size:15px; font-weight:900; color:#ffffff; line-height:1.2;">EMED ELETROMEDICINA LTDA.</div>
      <div style="font-size:11px; color:#64dfdf; font-weight:600; line-height:1.25;">Manutenção em Equipamentos de Diagnóstico por Imagem</div>
      <div style="font-size:10px; color:#94a3b8; line-height:1.25;">CNPJ: 03.611.974/0001-08 • (85) 3254-2929 • Fortaleza/CE</div>
    </div>
  </div>
  <div class="emed-os-date-box">
    <div style="font-size:12px; color:#ffffff; font-weight:bold;">📅 Data: {dt_ag_h}</div>
    <div style="font-size:10px; color:#34d399; font-weight:bold; margin-top:2px;">✅ CONCLUÍDA</div>
  </div>
</div>
<div class="emed-os-center-banner">
  <span style="font-size:17px; font-weight:900; color:#64dfdf; letter-spacing:0.6px;">ORDEM DE SERVIÇO Nº #{id_os_c}</span>
</div>
<div class="emed-os-grid-2" style="font-size:12px;">
  <div style="background:#1c2541; padding:9px 12px; border-radius:8px; border:1px solid #3a506b; border-left:3.5px solid #64dfdf;">
    <div style="font-size:10.5px; font-weight:bold; color:#64dfdf; text-transform:uppercase; margin-bottom:4px;">🏥 1. Dados do Cliente (Compacto)</div>
    <div style="font-size:12.5px; font-weight:bold; color:#ffffff;">{cli_nome_c} <span style="font-size:10.5px; color:#94a3b8; font-weight:normal;">(CNPJ: {cli_cnpj_c})</span></div>
    <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px;"><b>📍 Endereço:</b> {cli_end_c} — {cli_cid_c}/{cli_uf_c}</div>
    <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px;"><b>👤 Resp.:</b> {cli_resp_c} &nbsp;|&nbsp; <b>📞 Contato:</b> {cli_whats_c or cli_email_c or 'N/D'}</div>
  </div>
  <div style="background:#1c2541; padding:9px 12px; border-radius:8px; border:1px solid #3a506b; border-left:3.5px solid #38bdf8;">
    <div style="font-size:10.5px; font-weight:bold; color:#38bdf8; text-transform:uppercase; margin-bottom:4px;">🔬 2. Equipamento &amp; Equipe Técnica</div>
    <div style="font-size:12.5px; font-weight:bold; color:#ffffff;">{row_c['equipamento']} <span style="font-size:11px; color:#38bdf8;">[{tipo_srv_c} - {etapa_hist}]</span></div>
    <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px;"><b>👷 Técnico:</b> {tec_hist_c} (CFT/CREA) &nbsp;|&nbsp; <b>Aux:</b> {tec_aux_c if tec_aux_c else 'Individual'}</div>
    <div style="font-size:11.5px; color:#cbd5e1; margin-top:2px;"><b>⏱️ Atendimento:</b> {horario_h_txt}</div>
  </div>
</div>
<div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b; border-left:3.5px solid #10b981; margin-bottom:10px;">
  <div style="font-size:11px; font-weight:bold; color:#10b981; text-transform:uppercase; margin-bottom:6px;">🛠️ 3. Serviços Executados &amp; Procedimentos Técnicos</div>
  <div style="background:#0b132b; border:1px solid #3a506b; border-radius:6px; padding:9px 11px; margin-bottom:8px;">
    <div style="font-size:12.5px; color:#f8fafc; line-height:1.45; font-weight:500;">{srv_exec_h_html}</div>
  </div>
  <div class="emed-os-grid-2" style="font-size:11.5px; margin-bottom:0;">
    <div style="background:#0b132b; padding:7px 9px; border-radius:6px; border:1px solid #233554;">
      <b style="color:#f59e0b;">📢 Defeito Relatado:</b> {def_rel_h}<br/>
      <b style="color:#ef4444;">🔍 Diagnóstico:</b> {prob_enc_h}
    </div>
    <div style="background:#0b132b; padding:7px 9px; border-radius:6px; border:1px solid #233554;">
      <b style="color:#38bdf8;">📋 Checklist POP:</b> {chk_pop_h or 'Padrão Concluído'}<br/>
      <b style="color:#a78bfa;">⚡ Parâmetros / Testes:</b> {param_h}
    </div>
  </div>
</div>
<div class="emed-os-grid-2" style="font-size:12px;">
  <div style="background:#1c2541; padding:9px 12px; border-radius:8px; border:1px solid #3a506b;">
    <div style="font-size:10.5px; font-weight:bold; color:#cbd5e1; text-transform:uppercase; margin-bottom:3px;">📝 4. Pendências &amp; Observações</div>
    <div style="font-size:11.5px; color:#fbbf24;"><b>Pendências:</b> {pend_h_txt}</div>
    <div style="font-size:11.5px; color:#cbd5e1; margin-top:3px;"><b>Observações:</b> {obs_ger_h}</div>
  </div>
  <div style="background:#1c2541; padding:9px 12px; border-radius:8px; border:1px solid #3a506b; display:flex; flex-direction:column; justify-content:center;">
    <div style="font-size:10.5px; font-weight:bold; color:#cbd5e1; text-transform:uppercase; margin-bottom:4px;">🏁 Condição de Liberação &amp; Comercial</div>
    <div><span style="background:#064e3b; color:#34d399; border:1px solid #059669; padding:3px 10px; border-radius:5px; font-size:12px; font-weight:800; display:inline-block;">✅ {cond_f_h}</span></div>
    <div style="font-size:11px; color:#94a3b8; margin-top:4px;">Faturamento: <b>{row_c.get('condicao_pagamento') or 'Contrato Padrão'}</b></div>
  </div>
</div>
{bloco_fotos_card_html}
<div class="emed-os-grid-2" style="margin-bottom:0;">
  <div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b; text-align:center;">
    <div style="font-size:10.5px; font-weight:bold; color:#64dfdf; text-transform:uppercase; margin-bottom:4px;">✍️ Responsável Técnico EMED</div>
    <div style="font-family:'Brush Script MT',cursive; font-size:22px; color:#34d399; min-height:36px; line-height:36px;">{tec_hist_c.title()}</div>
    <hr style="border:0; border-top:1px solid #475569; margin:4px 16px;"/>
    <div style="font-size:11.5px; font-weight:bold; color:#ffffff;">{tec_hist_c}</div>
    <div style="font-size:10.5px; color:#94a3b8;">Registro Técnico CFT / CREA</div>
    {f'<div style="font-size:10.5px; color:#38bdf8; margin-top:2px;">Auxiliar: {tec_aux_c}</div>' if tec_aux_c else ''}
  </div>
  <div style="background:#1c2541; padding:10px 12px; border-radius:8px; border:1px solid #3a506b; text-align:center;">
    <div style="font-size:10.5px; font-weight:bold; color:#64dfdf; text-transform:uppercase; margin-bottom:4px;">✍️ Aceite do Cliente / Hospital</div>
    {bloco_img_cli_card}
    <hr style="border:0; border-top:1px solid #475569; margin:4px 16px;"/>
    <div style="font-size:11.5px; font-weight:bold; color:#ffffff;">{ass_cli_hist}</div>
    <div style="font-size:10.5px; color:#94a3b8;">Responsável no Estabelecimento</div>
  </div>
</div>
</div>"""

                st.markdown(card_os_fechada_html, unsafe_allow_html=True)

                # Seção de Fotos / Anexos Rápidos na OS Concluída (Permite anexar caso tenha esquecido antes de fechar)
                f_ant_c = limpar_texto(row_c.get('foto_evidencia'), '')
                f_dep_c = limpar_texto(row_c.get('foto_depois'), '')
                vid_c = limpar_texto(row_c.get('video_evidencia'), '')
                tem_foto_c = bool((f_ant_c and os.path.exists(f_ant_c)) or (f_dep_c and os.path.exists(f_dep_c)))
                lbl_exp_fotos = (
                    "📸 Fotos Anexadas na OS (Clique para ver ou substituir Fotos Antes/Depois)"
                    if tem_foto_c
                    else "📸 Nenhuma foto anexada nesta OS — Clique aqui se desejar anexar Fotos (Antes / Depois) para sair no PDF"
                )
                with st.expander(lbl_exp_fotos, expanded=False):
                    cf_add1, cf_add2 = st.columns(2)
                    with cf_add1:
                        up_f_ant_c = st.file_uploader("📸 Foto Antes / Evidência Inicial", type=["png", "jpg", "jpeg"], key=f"up_fant_c_{idx_c}_{id_os_c}")
                    with cf_add2:
                        up_f_dep_c = st.file_uploader("📸 Foto Depois / Equipamento Pronto", type=["png", "jpg", "jpeg"], key=f"up_fdep_c_{idx_c}_{id_os_c}")
                    if st.button("💾 Gravar Fotos na OS e Atualizar PDF/HTML", key=f"btn_grav_f_c_{idx_c}_{id_os_c}", type="primary", use_container_width=True):
                        if up_f_ant_c is None and up_f_dep_c is None:
                            st.warning("⚠️ Selecione pelo menos uma foto acima para anexar.")
                        else:
                            pasta_up_c = os.path.join(ctx.base_dir, "uploads_os")
                            os.makedirs(pasta_up_c, exist_ok=True)
                            if up_f_ant_c is not None:
                                p_ant_c = os.path.join(pasta_up_c, f"ANTES_OS{id_os_c}_{up_f_ant_c.name}")
                                with open(p_ant_c, "wb") as f:
                                    f.write(up_f_ant_c.getbuffer())
                                df.at[idx_c, "foto_evidencia"] = p_ant_c
                            if up_f_dep_c is not None:
                                p_dep_c = os.path.join(pasta_up_c, f"DEPOIS_OS{id_os_c}_{up_f_dep_c.name}")
                                with open(p_dep_c, "wb") as f:
                                    f.write(up_f_dep_c.getbuffer())
                                df.at[idx_c, "foto_depois"] = p_dep_c
                            salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                            st.cache_data.clear()
                            st.success("✅ Fotos gravadas e incluídas na Folha de OS (PDF e HTML)!")
                            st.rerun()
                    if vid_c and os.path.exists(vid_c):
                        st.video(vid_c)

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

                # OPÇÃO DE ENVIO POR E-MAIL, WHATSAPP & FICHA OFICIAL A4
                st.markdown("---")
                st.markdown("##### 📧 Envio da OS por E-mail, 💬 WhatsApp & 🖨️ Impressão da Ficha Oficial")
                cli_whats_c = _limpar_telefone_exibicao(row_c.get('whatsapp') or row_c.get('contato_responsavel'))
                if cli_whats_c == "N/D":
                    cli_whats_c = ""

                c_inp1, c_inp2 = st.columns(2)
                with c_inp1:
                    email_dest_in = st.text_input(
                        "📧 E-mail do Cliente / Destinatário",
                        value=cli_email_c,
                        placeholder="engenharia@hospital.com.br",
                        key=f"em_dest_c_{idx_c}",
                    )
                with c_inp2:
                    whats_dest_in = st.text_input(
                        "💬 WhatsApp do Cliente / Responsável (com DDD)",
                        value=cli_whats_c,
                        placeholder="5585999999999",
                        key=f"wa_dest_c_{idx_c}",
                    )

                link_aval_google = st.text_input(
                    "⭐ Link de Avaliação Google (Pesquisa de Satisfação)",
                    value=st.session_state.get("link_google_avaliacao", obter_configuracao(ctx.db_name, "google_review_url", URL_GOOGLE_REVIEW_OFICIAL)),
                    key=f"lk_aval_g_{idx_c}",
                    help="Cole aqui o link do seu perfil do Google Meu Negócio para o cliente avaliar e subir a nota da EMED."
                )
                if link_aval_google and link_aval_google.strip():
                    st.session_state.link_google_avaliacao = link_aval_google.strip()
                    salvar_configuracao(ctx.db_name, "google_review_url", link_aval_google.strip())

                bloco_aval_txt = f"\n\n⭐ *SUA AVALIAÇÃO É MUITO IMPORTANTE!*\nAjude a EMED a manter o padrão de excelência hospitalar avaliando nosso atendimento com 5 estrelas no Google:\n👉 {link_aval_google.strip()}" if link_aval_google.strip() else ""
                bloco_aval_em = f"\n\n⭐ SUA AVALIAÇÃO É MUITO IMPORTANTE!\nAvalie o atendimento da EMED no Google: {link_aval_google.strip()}" if link_aval_google.strip() else ""

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
                    f"• Assinatura Responsável Local: {ass_cli_hist}"
                    f"{bloco_aval_em}\n\n"
                    f"Atenciosamente,\n"
                    f"EMED ELETROMEDICINA LTDA.\n"
                    f"Eletromedicina, Manutenção em Equipamentos de Diagnóstico por Imagem\n"
                    f"CNPJ: 03.611.974/0001-08 • Fone: (85) 3254-2929\n"
                    f"Site: https://emed.med.br/"
                )
                link_mailto = (
                    f"mailto:{urllib.parse.quote(email_dest_in.strip())}?"
                    f"subject={urllib.parse.quote(assunto_email)}&"
                    f"body={urllib.parse.quote(corpo_email)}"
                )

                texto_whatsapp_os = (
                    f"🏥 *EMED ELETROMEDICINA LTDA.*\n"
                    f"_Eletromedicina, Manutenção em Equipamentos de Diagnóstico por Imagem_\n"
                    f"🌐 https://emed.med.br/ | 📞 (85) 3254-2929\n\n"
                    f"📋 *ORDEM DE SERVIÇO Nº #{id_os_c}*\n\n"
                    f"🏢 *Cliente:* {cli_nome_c}\n"
                    f"📍 *Endereço:* {cli_end_c} ({cli_cid_c}/{cli_uf_c})\n"
                    f"👤 *Responsável:* {cli_resp_c}\n\n"
                    f"🔬 *Equipamento:* {row_c['equipamento']}\n"
                    f"🔧 *Tipo de Serviço:* {tipo_srv_c} ({etapa_hist})\n"
                    f"👷 *Técnico Responsável:* {tec_hist_c}\n"
                    f"🤝 *Técnico Auxiliar:* {tec_aux_c or 'Atendimento Individual'}\n\n"
                    f"🛠️ *SERVIÇOS EXECUTADOS:*\n"
                    f"{srv_exec_h}\n\n"
                    f"📋 *Checklist POP/IT:* {chk_pop_h or 'Concluído'}\n"
                    f"📝 *Observações:* {obs_ger_h}\n"
                    f"🏁 *Condição Final:* {cond_f_h}\n"
                    f"✍️ *Recebido/Assinado por:* {ass_cli_hist}\n\n"
                    f"✅ *STATUS:* OS CONCLUÍDA"
                    f"{bloco_aval_txt}\n\n"
                    f"🌐 *CNPJ: 03.611.974/0001-08 — EMED Eletromedicina*"
                )
                num_wa_limpo = "".join(ch for ch in whats_dest_in if ch.isdigit())
                if num_wa_limpo and not num_wa_limpo.startswith("55") and len(num_wa_limpo) in (10, 11):
                    num_wa_limpo = "55" + num_wa_limpo
                base_wa = f"https://wa.me/{num_wa_limpo}" if num_wa_limpo else "https://wa.me/"
                link_whatsapp_os = f"{base_wa}?text={urllib.parse.quote(texto_whatsapp_os)}"


                html_ficha_os = _gerar_html_os_formatada(str(id_os_c), row_c, equipa_tecnica)

                pdf_laudo_bytes = None
                try:
                    pdf_laudo_bytes = converter_html_para_pdf_bytes(html_ficha_os)
                except Exception:
                    pdf_laudo_bytes = None

                c_bt1, c_bt2, c_bt3, c_bt4 = st.columns(4)
                with c_bt1:
                    if st.button("📧 Enviar OS por E-mail", key=f"btn_send_em_{idx_c}", type="primary", use_container_width=True):
                        if not email_dest_in.strip():
                            st.warning("⚠️ Informe o endereço de e-mail do cliente no campo acima!")
                        else:
                            df.at[idx_c, 'email'] = email_dest_in.strip()
                            salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                            st.success(f"✅ E-mail preparado para **{email_dest_in.strip()}**!")
                            st.markdown(
                                f'<a href="{link_mailto}" target="_blank" style="display:block; text-align:center; background:#10b981; color:#0b132b; font-weight:bold; padding:8px 12px; border-radius:6px; text-decoration:none; margin-top:4px;">📨 Abrir no Cliente de E-mail</a>',
                                unsafe_allow_html=True,
                            )
                with c_bt2:
                    if st.button("💬 Enviar no WhatsApp", key=f"btn_send_wa_{idx_c}", type="primary", use_container_width=True):
                        if whats_dest_in.strip():
                            df.at[idx_c, 'whatsapp'] = whats_dest_in.strip()
                            salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                        st.markdown(
                            f'<a href="{link_whatsapp_os}" target="_blank" style="display:block; text-align:center; background:#25D366; color:#0b132b; font-weight:bold; padding:8px 12px; border-radius:6px; text-decoration:none; margin-top:4px;">📲 Abrir Conversa no WhatsApp com a OS</a>',
                            unsafe_allow_html=True,
                        )
                with c_bt3:
                    if pdf_laudo_bytes:
                        st.download_button(
                            label="📄 Baixar Laudo Oficial (PDF)",
                            data=pdf_laudo_bytes,
                            file_name=f"Laudo_Tecnico_OS_{id_os_c}_{limpar_texto(cli_nome_c, 'EMED').replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_laudo_{idx_c}",
                            use_container_width=True,
                        )
                    else:
                        st.button("📄 PDF Indisponível", disabled=True, key=f"dl_pdf_dis_{idx_c}", use_container_width=True)
                with c_bt4:
                    st.download_button(
                        label="🌐 Baixar Ficha Web (HTML)",
                        data=html_ficha_os.encode("utf-8"),
                        file_name=f"OS_{id_os_c}_{limpar_texto(cli_nome_c, 'EMED').replace(' ', '_')}.html",
                        mime="text/html",
                        key=f"dl_html_os_{idx_c}",
                        use_container_width=True,
                    )

                st.markdown("---")
                st.markdown("##### 🧾 Fluxo de Cobrança, Peças Aplicadas & Faturamento (NFS-e / NF-e)")
                peca_concluida_ref = limpar_texto(row_c.get('peca_baixada_ref'), 'NENHUMA PEÇA EXTRA')
                val_total_c = limpar_float(row_c.get('valor_os'), 0.0)

                # Busca registro fiscal de cobrança se existente
                row_nf_dados = None
                try:
                    import sqlite3
                    with sqlite3.connect(ctx.db_name) as conn_nf_chk:
                        cur_nf_c = conn_nf_chk.cursor()
                        cur_nf_c.execute("""
                            SELECT valor_servicos, valor_pecas, valor_liquido, status_fiscal, numero_nf, chave_acesso, tipo_nota
                            FROM notas_fiscais WHERE os_id = ?
                        """, (int(id_os_c),))
                        row_nf_dados = cur_nf_c.fetchone()
                except Exception:
                    pass

                c_cob1, c_cob2 = st.columns([2, 1.2])
                with c_cob1:
                    if row_nf_dados:
                        v_srv_c, v_pec_c, v_liq_c, st_fisc_c, num_nf_c, chv_nf_c, tp_nf_c = row_nf_dados
                        st_cor = "#10b981" if "EMITID" in str(st_fisc_c).upper() else "#f59e0b"
                        st.markdown(f"""
                            <div style="background:#1e293b; border-left: 4px solid {st_cor}; padding: 10px 14px; border-radius: 6px;">
                                <div style="font-size:12px; font-weight:700; color:{st_cor};">SITUAÇÃO DO FATURAMENTO: {st_fisc_c}</div>
                                <div style="font-size:13px; color:#f8fafc; margin-top:4px;">
                                    ⚙️ <b>Peça Definitiva:</b> <code>{peca_concluida_ref}</code> (Baixada no Estoque)<br/>
                                    💵 <b>Peças:</b> R$ {float(v_pec_c or 0):,.2f} | 🛠️ <b>Mão de Obra:</b> R$ {float(v_srv_c or 0):,.2f} | 💰 <b>Total:</b> R$ {float(v_liq_c or 0):,.2f}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div style="background:#1e293b; border-left: 4px solid #64dfdf; padding: 10px 14px; border-radius: 6px;">
                                <div style="font-size:12px; font-weight:700; color:#64dfdf;">FATURAMENTO REGISTRADO</div>
                                <div style="font-size:13px; color:#f8fafc; margin-top:4px;">
                                    ⚙️ <b>Peça:</b> <code>{peca_concluida_ref}</code><br/>
                                    💰 <b>Valor Total:</b> R$ {val_total_c:,.2f}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

                with c_cob2:
                    msg_cobranca_wpp = (
                        f"🧾 *DEMONSTRATIVO DE FATURAMENTO / COBRANÇA - EMED*\n\n"
                        f"🏥 *Cliente:* {cli_nome_c}\n"
                        f"📋 *OS Concluída:* #{id_os_c} ({row_c['equipamento']})\n"
                        f"⚙️ *Peça Aplicada em Definitivo:* {peca_concluida_ref}\n"
                        f"💰 *Valor Total do Atendimento:* R$ {val_total_c:,.2f}\n"
                        f"💳 *Condição:* {limpar_texto(row_c.get('condicao_pagamento'), 'FATURAMENTO')}\n\n"
                        f"Para emissão de NFS-e ou boletos, estamos à disposição!\n"
                        f"EMED Eletromedicina • CNPJ: 03.611.974/0001-08"
                    )
                    link_wpp_cob = f"https://wa.me/?text={urllib.parse.quote(msg_cobranca_wpp)}"
                    st.markdown(f"""
                        <a href="{link_wpp_cob}" target="_blank" style="background:#0284c7; color:white; padding:9px 16px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px; display:inline-block; margin-top:4px;">
                            📲 Disparar Cobrança p/ Financeiro (WhatsApp)
                        </a>
                    """, unsafe_allow_html=True)

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
                            # Acionamento Automático do Almoxarifado para o Novo Técnico
                            ok_sep, msg_sep = acionar_separacao_automatica_almoxarifado(
                                ctx.db_name,
                                tec_reab,
                                row_c.get('cliente', ''),
                                row_c.get('equipamento', ''),
                                row_c.get('tipo_servico', ''),
                                inst_reab,
                                os_id=id_os_c
                            )
                            st.success(f"✅ Salvo com sucesso! OS #{id_os_c} reaberta para o técnico {tec_reab}!")
                            if ok_sep:
                                st.info(f"📦 {msg_sep}")
                            st.rerun()


def _render_execucao_os_ativas(ctx: AppContext):
    df = ctx.df
    df_estoque = ctx.df_estoque
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown("#### 🛠️ Execução Modular de Ordem de Serviço em Campo (6 Módulos)")
    df_os_ativas = df[df['status'].astype(str).str.upper() == 'ATIVO']

    if df_os_ativas.empty:
        st.info("ℹ️ Não existem ordens de serviço ativas no momento.")
        return

    # Seletor de Foco Rápido de OS (Abre a OS desejada em foco total com alta performance)
    opcoes_foco = ["📋 VER TODAS AS ORDENS ATIVAS (EXPANDERS)"] + [
        f"⚡ OS #{obter_id_os(i, r)} | {limpar_texto(r.get('cliente'))} — {limpar_texto(r.get('equipamento'))} [{limpar_texto(r.get('tipo_servico'))}]"
        for i, r in df_os_ativas.iterrows()
    ]

    col_foc1, col_foc2 = st.columns([3, 1])
    with col_foc1:
        foco_escolhido = st.selectbox(
            "🎯 Foco de Atendimento (Selecione a OS para abrir diretamente em tela cheia com alta velocidade):",
            opcoes_foco,
            index=0,
            key="sel_foco_os_ativa"
        )
    with col_foc2:
        st.caption(f"Total: **{len(df_os_ativas)} OS ativas** no sistema.")

    if foco_escolhido != "📋 VER TODAS AS ORDENS ATIVAS (EXPANDERS)":
        id_str = foco_escolhido.split("|")[0].replace("⚡ OS #", "").strip()
        df_os_render = df_os_ativas[df_os_ativas.index.astype(str) == id_str]
        if df_os_render.empty:
            df_os_render = df_os_ativas[df_os_ativas['id'].astype(str) == id_str]
        if df_os_render.empty:
            df_os_render = df_os_ativas
    else:
        df_os_render = df_os_ativas

        for idx_os, row_os in df_os_render.iterrows():
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

            # Recupera rascunho provisório offline/local se existir
            rascunho_salvo, dt_rascunho = obter_rascunho_provisorio(ctx.db_name, str(id_os_ativa))
            if rascunho_salvo:
                srv_exec_atual = rascunho_salvo.get('servico_executado', srv_exec_atual)
                prob_enc_atual = rascunho_salvo.get('problemas_encontrados', prob_enc_atual)
                def_rel_atual = rascunho_salvo.get('defeito_relatado', def_rel_atual)
                obs_ger_atual = rascunho_salvo.get('observacoes_gerais', obs_ger_atual)
                param_atual = rascunho_salvo.get('parametros_medidos', param_atual)
                inst_os_atual = rascunho_salvo.get('inst_prox_visita', inst_os_atual)
                end_os_atual = rascunho_salvo.get('endereco', end_os_atual)
                email_os_atual = rascunho_salvo.get('email', email_os_atual)

            titulo_os_ativa = f"🛠️ OS #{id_os_ativa} | {cli_os_atual} — Equipamento: {eq_os_atual} [{srv_os_atual}] [Técnico: {tec_resp_os}{txt_aux_ativo}]"
            with st.expander(titulo_os_ativa, expanded=(len(df_os_render) == 1)):
                if rascunho_salvo:
                    col_av1, col_av2 = st.columns([3.5, 1.5])
                    with col_av1:
                        st.info(f"💾 **Rascunho Provisório Ativo:** Salvo automaticamente em `{dt_rascunho}`. Seus dados estão 100% protegidos contra quedas de sinal!")
                    with col_av2:
                        if st.button("🗑️ Descartar Rascunho", key=f"btn_desc_rasc_{idx_os}_{id_os_ativa}"):
                            limpar_rascunho_provisorio(ctx.db_name, str(id_os_ativa))
                            st.rerun()
                logo_atv_b64 = _obter_logo_base64()
                bloco_logo_atv = (
                    f'<div style="background:#ffffff; padding:4px 8px; border-radius:6px; display:inline-flex; align-items:center;">'
                    f'<img src="{logo_atv_b64}" style="height:46px; max-width:130px; object-fit:contain;" alt="Logo EMED"/>'
                    f'</div>'
                    if logo_atv_b64
                    else '<span style="font-size:18px; font-weight:bold; color:#64dfdf;">🏥 EMED</span>'
                )
                card_os_ativa_html = f"""<div style="background:#101935; border:1.5px solid #64dfdf; border-radius:10px; padding:14px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; border-bottom:1px solid #3a506b; padding-bottom:10px; margin-bottom:10px;">
<div style="display:flex; align-items:center; gap:12px;">
{bloco_logo_atv}
<div>
<div style="font-size:16px; font-weight:900; color:#ffffff;">EMED ELETROMEDICINA LTDA.</div>
<div style="font-size:11px; color:#64dfdf; font-weight:600;">Eletromedicina, Manutenção em Equipamentos de Diagnóstico por Imagem</div>
<div style="font-size:10.5px; color:#94a3b8;">CNPJ: 03.611.974/0001-08 • Fone: (85) 3254-2929 • emed.med.br</div>
</div>
</div>
<div style="text-align:right;">
<div style="font-size:18px; font-weight:900; color:#64dfdf;"><b>OS ATIVA Nº #{id_os_ativa}</b></div>
<div style="font-size:11px; color:#cbd5e1;">📅 Data: <b>{dt_os_atual}</b> &nbsp;|&nbsp; 🔧 <b>{srv_os_atual}</b></div>
</div>
</div>
<div style="background:#1c2541; padding:8px 12px; border-radius:6px; font-size:12.5px; border-left:3px solid #64dfdf;">
<b>🏥 Cliente:</b> {cli_os_atual} &nbsp;|&nbsp; <b>📍 Endereço:</b> {end_os_atual} ({cid_os_atual}/{uf_os_atual}) &nbsp;|&nbsp; <b>🔬 Equipamento:</b> {eq_os_atual}
</div>
</div>"""
                st.markdown(card_os_ativa_html, unsafe_allow_html=True)

                # -------------------------------------------------------------
                # PROCEDIMENTO TÉCNICO VINCULADO (IT & VÍDEO DO EQUIPAMENTO)
                # -------------------------------------------------------------
                try:
                    info_it = vincular_it_ao_equipamento(eq_os_atual, srv_os_atual, os.path.join(ctx.base_dir, "Manuais"))
                except Exception:
                    info_it = {"encontrado": False}

                if info_it.get("encontrado"):
                    with st.expander(f"📘 Procedimento Operacional Vinculado: {info_it['codigo_it']}", expanded=True):
                        c_it_left, c_it_right = st.columns([1.6, 1.4])
                        with c_it_left:
                            st.markdown(f"**Manual Técnico / IT Homologada:** `{info_it['nome_arquivo']}`")
                            st.caption("Parâmetros de fábrica, rotinas de ajuste, calibração e segurança aplicáveis a este equipamento.")
                            c_it_b1, c_it_b2 = st.columns(2)
                            with c_it_b1:
                                if info_it.get("caminho_pdf") and os.path.exists(info_it["caminho_pdf"]):
                                    with open(info_it["caminho_pdf"], "rb") as f_it_p:
                                        st.download_button(
                                            "📄 Baixar IT em PDF",
                                            data=f_it_p.read(),
                                            file_name=os.path.basename(info_it["caminho_pdf"]),
                                            mime="application/pdf",
                                            key=f"dl_it_pdf_exec_{idx_os}_{id_os_ativa}",
                                            use_container_width=True
                                        )
                            with c_it_b2:
                                if info_it.get("caminho_pdf") and os.path.exists(info_it["caminho_pdf"]):
                                    if st.button("🖥️ Abrir no Windows", key=f"btn_open_it_win_{idx_os}_{id_os_ativa}", use_container_width=True):
                                        import webbrowser
                                        webbrowser.open(info_it["caminho_pdf"])
                                        st.toast("IT aberta no leitor nativo do sistema!", icon="📄")
                        with c_it_right:
                            if info_it.get("caminho_video") and os.path.exists(info_it["caminho_video"]):
                                st.markdown("**🎬 Vídeo de Treinamento Técnico Co-localizado:**")
                                st.video(info_it["caminho_video"])

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
                ], key=f"tabs_os_modular_{id_os_ativa}_{idx_os}")

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
                        st.markdown("###### 📦 Peça ou Componente Aplicado")
                        pecas_disponiveis = df_estoque['nome_peca'].tolist() if not df_estoque.empty else []

                        modo_peca = st.radio(
                            "Origem da Peça Utilizada:",
                            [
                                "📦 Estoque Cadastrado",
                                "✍️ Preenchimento Manual (Avulsa / Não Listada)",
                                "❌ Nenhuma Peça"
                            ],
                            horizontal=True,
                            key=f"modo_peca_{idx_os}"
                        )

                        if "Estoque" in modo_peca:
                            peca_selecionada = st.selectbox(
                                "Selecione a Peça do Estoque:",
                                ["NENHUMA PEÇA"] + pecas_disponiveis,
                                key=f"peca_{idx_os}"
                            )
                        elif "Manual" in modo_peca:
                            peca_man_val = st.text_input(
                                "Digite o Nome / Código da Peça Aplicada: *",
                                placeholder="Ex: BOBINA SOLENOIDE 24V, FUSÍVEL 15A CERÂMICO, TECLADO...",
                                key=f"peca_man_txt_{idx_os}"
                            )
                            peca_selecionada = peca_man_val.strip().upper() if peca_man_val.strip() else "NENHUMA PEÇA"
                        else:
                            peca_selecionada = "NENHUMA PEÇA"

                        if peca_selecionada != "NENHUMA PEÇA":
                            qtd_aplicada = st.number_input("Quantidade Aplicada", min_value=1, value=1, key=f"qtd_peca_{idx_os}")
                        else:
                            qtd_aplicada = 1

                        tipo_aplicacao_peca = "DEFINITIVA"
                        dias_obs_in = 3
                        criterio_obs_in = ""
                        if peca_selecionada != "NENHUMA PEÇA":
                            tipo_aplicacao_peca = st.radio(
                                "Finalidade da Aplicação da Peça:",
                                [
                                    "🟢 INSTALAÇÃO DEFINITIVA (Proposta/Orçamento Aprovado — Faturar)",
                                    "🟡 PEÇA EM TESTE / OBSERVAÇÃO (Diagnóstico em Aberto — Não Faturar Ainda)"
                                ],
                                key=f"tipo_app_peca_{idx_os}",
                                help="Selecione 'PEÇA EM TESTE' caso o equipamento precise rodar em observação clínica antes do cliente aprovar a proposta definitiva."
                            )
                            if "TESTE" in tipo_aplicacao_peca:
                                c_obs1, c_obs2 = st.columns(2)
                                with c_obs1:
                                    dias_obs_in = st.number_input("Prazo em Observação (dias):", min_value=1, max_value=30, value=3, key=f"dias_obs_{idx_os}")
                                with c_obs2:
                                    criterio_obs_in = st.text_input("Critério de Teste / Sintoma a Monitorar:", value="Validar ausência de falha sob carga", key=f"crit_obs_{idx_os}")

                    # Assistente Clínico com Checklist de Ações (Decisão 100% do Técnico)
                    st.markdown("###### 📋 Checklist de Ações Executadas & Assistente de Redação:")
                    with st.expander("✅ Abrir Checklist de Ações Técnicas (Marque o que foi feito na máquina)", expanded=False):
                        st.caption("O sistema sugere as ações técnicas recomendadas para este equipamento e defeito. Você seleciona exatamente o que realizou e insere no relatório:")
                        acoes_sugeridas_lista = obter_checklist_acoes_sugeridas(
                            eq_os_atual,
                            st.session_state.get(f"def_rel_{idx_os}", def_rel_atual)
                        )
                        col_ck1, col_ck2 = st.columns(2)
                        acoes_marcadas_usuario = []
                        for i_ac, ac_txt in enumerate(acoes_sugeridas_lista):
                            alvo_col = col_ck1 if i_ac % 2 == 0 else col_ck2
                            if alvo_col.checkbox(ac_txt, key=f"ck_it_{idx_os}_{id_os_ativa}_{i_ac}"):
                                acoes_marcadas_usuario.append(ac_txt)

                        col_act_ck1, col_act_ck2 = st.columns([2, 2])
                        with col_act_ck1:
                            if st.button("📝 Inserir Ações Marcadas no Relatório", key=f"btn_add_chk_{idx_os}_{id_os_ativa}", use_container_width=True):
                                if acoes_marcadas_usuario:
                                    txt_montado = "SERVIÇOS EXECUTADOS CONFORME PROTOCOLO TÉCNICO EMED:\n" + "\n".join([f"• {ac}" for ac in acoes_marcadas_usuario])
                                    atual_prev = st.session_state.get(f"obs_f_{idx_os}", srv_exec_atual)
                                    if atual_prev and atual_prev.strip():
                                        st.session_state[f"obs_f_{idx_os}"] = f"{atual_prev.strip()}\n\n{txt_montado}"
                                    else:
                                        st.session_state[f"obs_f_{idx_os}"] = txt_montado
                                    st.success(f"✅ {len(acoes_marcadas_usuario)} ações adicionadas ao relatório!")
                                    st.rerun()
                                else:
                                    st.warning("⚠️ Marque pelo menos uma ação no checklist acima.")
                        with col_act_ck2:
                            if st.button("⚡ Sugerir Texto Completo do Protocolo", key=f"btn_sug_ia_{idx_os}_{id_os_ativa}", use_container_width=True):
                                sugestao_texto = gerar_sugestao_relatorio_clinico(
                                    equipamento=eq_os_atual,
                                    defeito=st.session_state.get(f"def_rel_{idx_os}", def_rel_atual),
                                    tipo_servico=srv_os_atual,
                                    causa_raiz=st.session_state.get(f"cr_os_{idx_os}", "")
                                )
                                st.session_state[f"obs_f_{idx_os}"] = sugestao_texto
                                st.rerun()

                    # Modelos Rápidos Padronizados
                    col_tpl1, col_tpl2 = st.columns([1.5, 2.5])
                    with col_tpl1:
                        st.caption("Ou escolha um modelo pronto:")
                    with col_tpl2:
                        opcoes_templates_lista = ["📑 Selecione um Modelo Pronto (1-Toque)..."] + list(TEMPLATES_RELATORIO_TECNICO.keys())
                        tpl_sel = st.selectbox(
                            "Modelos Padronizados EMED:",
                            opcoes_templates_lista,
                            index=0,
                            key=f"sel_tpl_srv_{idx_os}_{id_os_ativa}",
                            label_visibility="collapsed"
                        )
                        if tpl_sel != "📑 Selecione um Modelo Pronto (1-Toque)...":
                            texto_tpl = TEMPLATES_RELATORIO_TECNICO[tpl_sel]
                            if st.button(f"📥 Aplicar Modelo: {tpl_sel.split()[1]}", key=f"btn_app_tpl_{idx_os}_{id_os_ativa}", use_container_width=True):
                                st.session_state[f"obs_f_{idx_os}"] = texto_tpl
                                st.rerun()

                    obs_tecnico_final = st.text_area(
                        "🛠️ Serviços Executados / Solução Técnica Aplicada *",
                        value=srv_exec_atual,
                        placeholder="Relate todos os serviços executados, ajustes, reparos e testes finais...",
                        height=110,
                        key=f"obs_f_{idx_os}"
                    )
                    
                    # Botão de salvamento rápido de rascunho provisório
                    if st.button("💾 Salvar Rascunho Provisório da OS (Sem Fechar)", key=f"btn_salvar_rasc_tab3_{idx_os}_{id_os_ativa}", use_container_width=True):
                        dados_r_tab3 = {
                            "servico_executado": obs_tecnico_final.strip(),
                            "problemas_encontrados": st.session_state.get(f"prob_enc_{idx_os}", prob_enc_atual),
                            "defeito_relatado": st.session_state.get(f"def_rel_{idx_os}", def_rel_atual),
                            "causa_raiz": st.session_state.get(f"cr_os_{idx_os}", row_os.get('causa_raiz', '')),
                            "condicao_inicial": st.session_state.get(f"ci_os_{idx_os}", row_os.get('condicao_inicial', '')),
                            "condicao_final": st.session_state.get(f"cf_os_{idx_os}", row_os.get('condicao_final', '')),
                            "parametros_medidos": st.session_state.get(f"param_med_{idx_os}", param_atual),
                            "inst_prox_visita": st.session_state.get(f"inst_prox_{idx_os}", inst_os_atual),
                            "observacoes_gerais": st.session_state.get(f"obs_g_{idx_os}", obs_ger_atual),
                            "endereco": st.session_state.get(f"end_exec_{idx_os}", end_os_atual),
                            "email": st.session_state.get(f"em_exec_{idx_os}", email_os_atual),
                            "valor_servico_os": st.session_state.get(f"val_os_{idx_os}", row_os.get('valor_os', 0.0)),
                            "modo_peca": st.session_state.get(f"modo_peca_{idx_os}", "❌ Nenhuma Peça"),
                            "peca_selecionada": peca_selecionada,
                            "qtd_aplicada": qtd_aplicada,
                        }
                        ok_s_r, msg_s_r = salvar_rascunho_provisorio(ctx.db_name, str(id_os_ativa), dados_r_tab3)
                        if ok_s_r:
                            st.success(f"✅ {msg_s_r}")
                            st.rerun()

                with m_tab4:
                    st.markdown("##### 🚨 Status de Pendências, Condição de Saída & Observações ao Cliente")
                    opcoes_fecho_lista = [
                        "✅ CONCLUÍDO (Fechar OS — Proposta Aprovada / Gerar Cobrança)",
                        "🔬 DEIXAR EM OBSERVAÇÃO (Equipamento / Peça em Teste de Diagnóstico — Não Faturar)",
                        "🚨 DEIXAR PENDÊNCIA ATIVA (Mantém alerta ligado para próxima intervenção)"
                    ]
                    idx_fecho_def = 1 if (peca_selecionada != "NENHUMA PEÇA" and "TESTE" in tipo_aplicacao_peca) else 0
                    status_fecho_escolha = st.radio(
                        "Resultado desta Intervenção:",
                        opcoes_fecho_lista,
                        index=idx_fecho_def,
                        horizontal=False,
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
                        placeholder="EX: LEVAR MULTÍMETRO FLUKE, PHANTOM E PLACA FONTE",
                        key=f"inst_prox_{idx_os}"
                    )
                    opcoes_gravidade_pend = [
                        "🟢 Nenhuma pendência restante (Equipamento 100% liberado)",
                        "🟡 PROGRAMADA (Equipamento funcional / aguarda até a próxima preventiva)",
                        "🔴 URGÊNCIA / CRÍTICA (Equipamento inoperante ou risco iminente de parada)"
                    ]
                    idx_grav_def = 0
                    if "PARADO" in condicao_fim_os or "INTERDITADO" in condicao_fim_os:
                        idx_grav_def = 2
                    elif "RESTRIÇÃO" in condicao_fim_os or (inst_prox_visita.strip() and inst_prox_visita.strip().upper() not in ["N/D", "NENHUM", ""]):
                        idx_grav_def = 1

                    gravidade_pendencia_sel = st.radio(
                        "🚨 Triagem da Pendência / Demanda Automática ao Almoxarifado:",
                        opcoes_gravidade_pend,
                        index=idx_grav_def,
                        key=f"grav_pend_{idx_os}",
                        help="Se houver peça necessária ou pendência restante, o Almoxarifado receberá a demanda automaticamente no fechamento com esta prioridade."
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

                    # Auto-persiste anexos assim que selecionados para evitar perda em campo
                    pasta_uploads_auto = os.path.join(ctx.base_dir, "uploads_os")
                    os.makedirs(pasta_uploads_auto, exist_ok=True)
                    auto_salvou_anexo = False
                    if foto_antes_up is not None:
                        p_f_ant_auto = os.path.join(pasta_uploads_auto, f"ANTES_OS{id_os_ativa}_{foto_antes_up.name}")
                        if limpar_texto(row_os.get('foto_evidencia'), '') != p_f_ant_auto or not os.path.exists(p_f_ant_auto):
                            with open(p_f_ant_auto, "wb") as f:
                                f.write(foto_antes_up.getbuffer())
                            df.at[idx_os, 'foto_evidencia'] = p_f_ant_auto
                            auto_salvou_anexo = True
                    if foto_depois_up is not None:
                        p_f_dep_auto = os.path.join(pasta_uploads_auto, f"DEPOIS_OS{id_os_ativa}_{foto_depois_up.name}")
                        if limpar_texto(row_os.get('foto_depois'), '') != p_f_dep_auto or not os.path.exists(p_f_dep_auto):
                            with open(p_f_dep_auto, "wb") as f:
                                f.write(foto_depois_up.getbuffer())
                            df.at[idx_os, 'foto_depois'] = p_f_dep_auto
                            auto_salvou_anexo = True
                    if auto_salvou_anexo:
                        salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                        st.toast("📸 Foto(s) salva(s) automaticamente na OS!", icon="✅")

                    st.markdown("<br/>", unsafe_allow_html=True)
                    if st.button("📸 Salvar Fotos e Vídeos Anexados Imediatamente", key=f"btn_salvar_fotos_tab5_{idx_os}", use_container_width=True):
                        pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                        os.makedirs(pasta_uploads, exist_ok=True)
                        salvou_anexo = False
                        if foto_antes_up is not None:
                            p_f_ant = os.path.join(pasta_uploads, f"ANTES_OS{id_os_ativa}_{foto_antes_up.name}")
                            with open(p_f_ant, "wb") as f:
                                f.write(foto_antes_up.getbuffer())
                            df.at[idx_os, 'foto_evidencia'] = p_f_ant
                            salvou_anexo = True
                        if foto_depois_up is not None:
                            p_f_dep = os.path.join(pasta_uploads, f"DEPOIS_OS{id_os_ativa}_{foto_depois_up.name}")
                            with open(p_f_dep, "wb") as f:
                                f.write(foto_depois_up.getbuffer())
                            df.at[idx_os, 'foto_depois'] = p_f_dep
                            salvou_anexo = True
                        if video_exec_up is not None:
                            p_vid = os.path.join(pasta_uploads, f"VID_OS{id_os_ativa}_{video_exec_up.name}")
                            with open(p_vid, "wb") as f:
                                f.write(video_exec_up.getbuffer())
                            df.at[idx_os, 'video_evidencia'] = p_vid
                            salvou_anexo = True
                        if formulario_exec_up is not None:
                            p_form = os.path.join(pasta_uploads, f"FORM_OS{id_os_ativa}_{formulario_exec_up.name}")
                            with open(p_form, "wb") as f:
                                f.write(formulario_exec_up.getbuffer())
                            df.at[idx_os, 'formulario_anexo'] = p_form
                            salvou_anexo = True
                        if orcamento_fecho_up is not None:
                            p_orc = os.path.join(pasta_uploads, f"ORC_OS{id_os_ativa}_{orcamento_fecho_up.name}")
                            with open(p_orc, "wb") as f:
                                f.write(orcamento_fecho_up.getbuffer())
                            df.at[idx_os, 'orcamento_anexo'] = p_orc
                            salvou_anexo = True

                        if salvou_anexo:
                            salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel)
                            st.cache_data.clear()
                            st.success("✅ Mídias e anexos gravados com sucesso nesta OS!")
                            st.rerun()
                        else:
                            st.warning("⚠️ Selecione ou fotografe pelo menos um arquivo antes de salvar.")

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
                        resp_pre_salvo = limpar_texto(row_os.get('assinatura_cliente'), limpar_texto(row_os.get('responsavel_hospital'), ''))
                        assinatura_cliente_input = st.text_input(
                            "Nome e Cargo/Setor do Responsável no Hospital *",
                            value=resp_pre_salvo,
                            placeholder="EX: DR. CARLOS / ENF. MARIA / SRA. DAMARES",
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
                    st.markdown("###### 🏁 Desfecho & Ação Imediata")
                    opcoes_fecho_tab6 = [
                        "✅ CONCLUÍDO (Fechar OS Agora — Equipamento Liberado & Faturar)",
                        "🔬 DEIXAR EM OBSERVAÇÃO (Equipamento / Peça em Teste — Não Faturar)",
                        "🚨 DEIXAR PENDÊNCIA ATIVA (Agendar Retorno da Equipe)"
                    ]
                    status_fecho_tab6 = st.radio(
                        "Status Final da Intervenção:",
                        opcoes_fecho_tab6,
                        index=0,
                        key=f"status_fecho_tab6_{idx_os}"
                    )

                    btn_concluir_tab6 = st.button(
                        f"🏁 Concluir e Fechar Ordem de Serviço #{id_os_ativa} Agora",
                        key=f"btn_concluir_tab6_{idx_os}",
                        type="primary",
                        use_container_width=True
                    )

                st.markdown("---")
                col_btn_sav1, col_btn_sav2 = st.columns([1, 1])
                with col_btn_sav1:
                    btn_rascunho_rapido = st.button(
                        f"💾 Salvar Rascunho Provisório (Não Fecha a OS)",
                        key=f"btn_rasc_rapido_bot_{idx_os}_{id_os_ativa}",
                        use_container_width=True,
                        help="Salva as informações digitadas sem exigir encerramento da OS ou dados de faturamento."
                    )
                with col_btn_sav2:
                    btn_finalizar_os = st.button(
                        f"💾 Salvar Modificações da OS #{id_os_ativa} (Gravar Todas as Abas)",
                        key=f"btn_finalizar_os_{idx_os}",
                        use_container_width=True
                    )

                if btn_rascunho_rapido:
                    dados_r_bot = {
                        "servico_executado": st.session_state.get(f"obs_f_{idx_os}", obs_tecnico_final),
                        "problemas_encontrados": problemas_encontrados_in.strip(),
                        "defeito_relatado": defeito_relatado_in.strip(),
                        "causa_raiz": causa_raiz_in,
                        "condicao_inicial": condicao_ini_os,
                        "condicao_final": condicao_fim_os,
                        "parametros_medidos": parametros_medidos_in.strip(),
                        "inst_prox_visita": inst_prox_visita.strip(),
                        "observacoes_gerais": observacoes_gerais_in.strip(),
                        "endereco": endereco_exec_in.strip(),
                        "email": email_exec_in.strip(),
                        "valor_servico_os": float(valor_final_faturar),
                        "opcao_faturamento": opcao_faturamento,
                        "assinatura_cliente_input": assinatura_cliente_input.strip(),
                        "assinatura_cliente_img": assinatura_cli_b64.strip(),
                        "peca_selecionada": peca_selecionada,
                        "qtd_aplicada": int(qtd_aplicada),
                    }
                    ok_r_bot, msg_r_bot = salvar_rascunho_provisorio(ctx.db_name, str(id_os_ativa), dados_r_bot)
                    if ok_r_bot:
                        st.success(f"✅ {msg_r_bot}")
                        st.rerun()

                if btn_concluir_tab6 or btn_finalizar_os:
                    status_escolhido_efetivo = status_fecho_tab6 if btn_concluir_tab6 else status_fecho_escolha
                    texto_relatorio_base = (
                        obs_tecnico_final.strip()
                        or problemas_encontrados_in.strip()
                        or def_rel_atual.strip()
                        or "MANUTENÇÃO E REVISÃO TÉCNICA EXECUTADA CONFORME PROTOCOLO EMED."
                    )
                    resp_final_cli = (
                        assinatura_cliente_input.strip()
                        or limpar_texto(row_os.get('responsavel_hospital'), '')
                        or "RESPONSÁVEL DO SETOR / HOSPITAL"
                    )

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

                        fechar_definitivo = ("CONCLUÍDO" in status_escolhido_efetivo) or btn_concluir_tab6
                        em_observacao = ("OBSERVAÇÃO" in status_escolhido_efetivo) and not btn_concluir_tab6
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
                        df.at[idx_os, 'assinatura_cliente'] = resp_final_cli.upper()
                        df.at[idx_os, 'assinatura_cliente_img'] = assinatura_cli_b64.strip()
                        df.at[idx_os, 'assinatura_tecnico'] = ass_padrao_tec.strip().upper()
                        df.at[idx_os, 'peca_baixada_ref'] = nova_ref_peca

                        resumo_diag = f" | [DIAGNÓSTICO: {problemas_encontrados_in.strip().upper()}]" if problemas_encontrados_in.strip() else ""
                        msg_cobranca_resumo = ""

                        # Triagem e disparo automático de demanda para o Almoxarifado/Estoque
                        tem_pendencia_ativa = (
                            "Nenhuma pendência" not in gravidade_pendencia_sel and
                            inst_prox_visita.strip() and
                            inst_prox_visita.strip().upper() not in ["N/D", "NENHUM", ""]
                        )
                        prioridade_almox = "URGENTE" if "URGÊNCIA" in gravidade_pendencia_sel else "PROGRAMADA"
                        if tem_pendencia_ativa:
                            status_demanda = f"A SEPARAR ({prioridade_almox} - DEMANDA DE CAMPO)"
                            try:
                                with get_db_connection(ctx.db_name) as conn:
                                    cur = conn.cursor()
                                    cur.execute("""
                                        INSERT INTO solicitacoes_pecas
                                        (tecnico, destino_cliente, itens_solicitados, instrumentos_solicitados, status_pedido, data_pedido)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (
                                        novo_tec_exec,
                                        row_os.get('cliente', ''),
                                        f"DEMANDA DE CAMPO [{prioridade_almox}]: {inst_prox_visita.strip().upper()}",
                                        f"Equipamento: {row_os.get('equipamento', '')} | OS #{id_os_ativa} | Triagem: {gravidade_pendencia_sel}",
                                        status_demanda,
                                        datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                                    ))
                                    conn.commit()
                            except Exception:
                                pass

                        if fechar_definitivo and not em_observacao:
                            if tem_pendencia_ativa:
                                df.at[idx_os, 'pendencias'] = f"[CONCLUÍDO COM PENDÊNCIA: {prioridade_almox}] {inst_prox_visita.strip().upper()} | {relatorio_com_peca}{resumo_diag} | [{resumo_pag}]"
                                df.at[idx_os, 'instrumento_necessario'] = f"[{prioridade_almox}] {inst_prox_visita.strip().upper()}"
                            else:
                                df.at[idx_os, 'pendencias'] = f"[CONCLUÍDO - {etapa_executada_fecho}] {relatorio_com_peca}{resumo_diag} | [{resumo_pag}]"
                                df.at[idx_os, 'condicao_final'] = 'LIBERADO PARA USO NORMAL'
                                df.at[idx_os, 'instrumento_necessario'] = ''
                            df.at[idx_os, 'status'] = 'CONCLUÍDO'

                            # Atualiza status na tabela clientes_equipamentos do SQLite
                            try:
                                with get_db_connection(ctx.db_name) as conn:
                                    cur = conn.cursor()
                                    cur.execute("UPDATE clientes_equipamentos SET status = 'CONCLUÍDO' WHERE id = ?", (int(id_os_ativa),))
                                    conn.commit()
                            except Exception:
                                pass

                            # 1. Baixa definitiva no estoque + atualização de status + sequência imediata ao fluxo de cobrança
                            try:
                                ok_cob, msg_cob = registrar_aplicacao_definitiva_e_fluxo_cobranca(
                                    ctx.db_name,
                                    id_os_ativa,
                                    row_os.get('cliente', ''),
                                    row_os.get('equipamento', ''),
                                    novo_tec_exec,
                                    peca_selecionada,
                                    int(qtd_aplicada),
                                    valor_final_faturar,
                                    condicao_pagamento=opcao_faturamento,
                                    tipo_contrato=row_os.get('tipo_contrato', 'CONTRATO')
                                )
                                msg_cobranca_resumo = msg_cob
                            except Exception as ex_cob:
                                msg_cobranca_resumo = f"⚠️ OS Concluída com sucesso! Faturamento em processamento paralelo: {ex_cob}"

                            if agendar_prox_ciclo:
                                df, _ = agendar_proxima_etapa_circular(
                                    df,
                                    df.loc[idx_os],
                                    etapa_executada_fecho,
                                    dias_ciclo=30
                                )
                        elif em_observacao:
                            df.at[idx_os, 'status'] = 'EM OBSERVAÇÃO'
                            df.at[idx_os, 'pendencias'] = f"[EM OBSERVAÇÃO - {dias_obs_in} DIAS] Peça {nova_ref_peca} em teste clínico. Critério: {criterio_obs_in}"
                            df.at[idx_os, 'instrumento_necessario'] = f"MONITORAR TESTE: {nova_ref_peca}"

                            ok_obs, msg_obs = registrar_peca_em_teste_observacao(
                                ctx.db_name,
                                id_os_ativa,
                                row_os.get('cliente', ''),
                                row_os.get('equipamento', ''),
                                novo_tec_exec,
                                peca_selecionada,
                                int(qtd_aplicada),
                                dias_observacao=dias_obs_in,
                                criterio_teste=criterio_obs_in
                            )
                            msg_cobranca_resumo = msg_obs
                        else:
                            pend_txt_base = f"[{prioridade_almox}] {inst_prox_visita.strip().upper()} | " if tem_pendencia_ativa else ""
                            df.at[idx_os, 'pendencias'] = f"{pend_txt_base}[ATENDIDO: {novo_tec_exec}] {relatorio_com_peca}{resumo_diag} (ETAPA REALIZADA: {etapa_executada_fecho})"
                            df.at[idx_os, 'status'] = 'ATIVO'
                            df.at[idx_os, 'instrumento_necessario'] = inst_prox_visita.strip().upper()

                        if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                            limpar_rascunho_provisorio(ctx.db_name, str(id_os_ativa))
                            st.cache_data.clear()
                            if fechar_definitivo:
                                st.success(f"🎉 ORDEM DE SERVIÇO #{id_os_ativa} CONCLUÍDA E FECHADA COM SUCESSO!")
                            else:
                                st.success(f"✅ Ordem de Serviço #{id_os_ativa} atualizada com sucesso!")
                            if tem_pendencia_ativa:
                                st.success(f"📦 Demanda de peça enviada automaticamente para o Almoxarifado com prioridade [{prioridade_almox}]!")
                            if msg_cobranca_resumo:
                                st.info(msg_cobranca_resumo)
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
