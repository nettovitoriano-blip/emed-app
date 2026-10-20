import io
import os
import base64
import urllib.parse
import pandas as pd
import streamlit as st
from datetime import datetime
from emed_core import (
    limpar_texto,
    obter_id_os,
    obter_kit_por_servico,
)
from emed_services import (
    AppContext,
    salvar_dados_seguro,
    calcular_distancia,
)


def _gerar_qrcode_base64(url: str) -> str:
    """Gera um QR Code em base64 diretamente em memória."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0B3B60", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception:
        return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(url)}"


def _buscar_cliente_por_cnpj_ou_nome(df: pd.DataFrame, termo_busca: str):
    """Busca clientes por CNPJ limpo ou nome parcial."""
    if not termo_busca or df.empty:
        return pd.DataFrame()
    
    termo = limpar_texto(termo_busca, "").upper().replace(".", "").replace("/", "").replace("-", "")
    
    # Busca por CNPJ
    def _match_cnpj(val):
        c_limpo = limpar_texto(val, "").replace(".", "").replace("/", "").replace("-", "")
        return termo in c_limpo if termo else False

    # Busca por Nome
    def _match_nome(val):
        n_limpo = limpar_texto(val, "").upper()
        return termo_busca.strip().upper() in n_limpo if termo_busca.strip() else False

    mascara = df["cnpj"].astype(str).apply(_match_cnpj) | df["cliente"].astype(str).apply(_match_nome)
    return df[mascara]


def _detectar_modalidade(nome_equip: str, texto_defeito: str = "") -> str:
    """Classifica a modalidade do equipamento para triagem técnica personalizada conforme a taxonomia da EMED."""
    texto = (str(nome_equip) + " " + str(texto_defeito)).upper()
    if any(k in texto for k in ["TOMOGRA", "CT", "BRIGHTSPEED", "SOMATOM", "OPTIMA", "REVOLUTION", "LIGHTSPEED", "EMOTION", "GANTRY", "CHILLER"]):
        return "TOMOGRAFIA"
    if any(k in texto for k in ["ARCO", "C-ARM", "BV PULSERA", "BV ENDURA", "ZIEHM", "OEC", "FLUORO"]):
        return "ARCO CIRÚRGICO"
    if any(k in texto for k in ["MAMO", "SENOGRAPHE", "SELENIA", "MAMMOMAT", "DIAMOND", "COMPRESSOR", "PLUMBIFERO"]):
        return "MAMOGRAFIA"
    if any(k in texto for k in ["DENSITO", "LUNAR", "PRODIGY", "DPX", "HOLOGIC", "DISCOVERY", "SHUTTER"]):
        return "DENSITOMETRIA"
    if any(k in texto for k in ["RAIO", "RX", "ESTATIVA", "BUCKY", "COLIMADOR", "GERADOR", "TUBO", "MULTIX", "XR", "RAD", "FREIO", "MESA"]):
        return "RAIO-X"
    return "OUTROS"


def _obter_dica_rapida_it(equipamento: str, relato: str) -> str:
    """Verifica se há orientações de primeiro nível baseadas nos POPs e ITs da EMED."""
    txt = (str(equipamento) + " " + str(relato)).upper()
    
    if any(w in txt for w in ["FREIO", "ESTATIVA", "PORTA TUBO", "PORTA-TUBO", "DESTRAV", "TRILHO", "HORIZONTAL", "VERTICAL", "SOLTO", "LIVRE"]):
        return (
            "💡 **Orientação da Engenharia Clínica EMED (Estativa & Eletrofreios):** "
            "Se o freio não estiver segurando (movimento livre) ou travar no trilho, verifique se ao apertar o botão da manopla escuta-se o estalo da bobina solenoide. "
            "Se **todos** os freios da sala (mesa e estativa) estiverem inoperantes, a falha provável é na fonte de alimentação dos freios. "
            "Se for **apenas um movimento específico**, nossa equipe levará a bobina solenoide e o botão de acionamento para substituição imediata."
        )
    elif "BRIVO" in txt or "TOMO" in txt or "CT385" in txt or "BRIGHTSPEED" in txt or "SOMATOM" in txt or "OPTIMA" in txt:
        if any(w in txt for w in ["TRAV", "REINIC", "COMUNIC", "GANTRY", "ERRO", "CHILLER"]):
            return (
                "💡 **Dica da Engenharia Clínica EMED (POP-03 / IT-05):** "
                "Para tomógrafos, verifique se o disjuntor de emergência do console ou a chave geral do Gantry "
                "não foram acionados acidentalmente. Um ciclo de reinicialização de 60 segundos "
                "no PDU costuma restaurar o barramento de comunicação."
            )
    elif "RAIO" in txt or "LOTUS" in txt or "HF500" in txt or "RX" in txt or "MULTIX" in txt:
        if any(w in txt for w in ["DISPAR", "COLIM", "EMISS", "GERADOR", "KV", "MAS", "FEIXE"]):
            return (
                "💡 **Dica da Engenharia Clínica EMED (POP-Lotus HF500 / IT-RX):** "
                "Para sistemas de Raio-X, confirme se o botão de disparo de 2 estágios está com o cabo íntegro "
                "e se o intertravamento das portas da sala de exame está fechado corretamente antes do chamado."
            )
    elif "ARCO" in txt or "C-ARM" in txt or "PULSERA" in txt or "ZIEHM" in txt:
        return (
            "💡 **Orientação Técnica EMED (Arco Cirúrgico):** "
            "Verifique se o cabo umbilical entre o carrinho dos monitores e o estativo em C está bem fixado "
            "e se os freios manuais das articulações orbitais estão soltos manualmente."
        )
    elif "MAMO" in txt or "SELENIA" in txt or "SENOGRAPHE" in txt:
        return (
            "💡 **Orientação Técnica EMED (Mamografia):** "
            "Se o compressor não responder, verifique se a liberação de emergência manual foi girada "
            "e teste o pedal alternativo."
        )
    elif "DENSITO" in txt or "LUNAR" in txt or "PRODIGY" in txt:
        return (
            "💡 **Orientação Técnica EMED (Densitometria Óssea):** "
            "Verifique se o braço C desliza livremente sobre a mesa de exames e se a comunicação "
            "com o computador do software está ativa."
        )
            
    return ""
            
    return ""


def render_emedonline(ctx: AppContext):
    """Módulo EmedOnline: Triagem Técnica Humanizada, Pré-Atendimento e Roteamento Inteligente."""
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0b132b 0%, #1c2541 60%, #102a43 100%); 
                    border-radius: 12px; padding: 18px 24px; border: 1.5px solid #3a506b; 
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="color: #64dfdf; margin: 0; font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        🤖 EMEDONLINE <span style="font-size: 14px; background: #059669; color: #fff; padding: 2px 8px; border-radius: 6px;">IA & Atendimento Ágil</span>
                    </h2>
                    <p style="color: #cbd5e1; margin: 6px 0 0 0; font-size: 13.5px;">
                        Triagem direta para clínicas e hospitais. Sem robôs amarrados: pré-preenche a OS, identifica falhas e despacha equipes por rota.
                    </p>
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">CENTRAL EMED 24H</div>
                    <div style="font-size: 14px; font-weight: 800; color: #64dfdf;">📞 (85) 3254-2929</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    query_params = st.query_params
    qr_eq_param = query_params.get("equipamento_qr", query_params.get("eq", ""))
    qr_cli_param = query_params.get("cliente_qr", query_params.get("cli", ""))
    qr_cnpj_param = query_params.get("cnpj", "")

    aba_portal, aba_despacho, aba_etiquetas, aba_instrucoes = st.tabs([
        "🏥 1. Portal do Cliente (Abrir Chamado)",
        "🗺️ 2. Central de Despacho & Rotas",
        "🏷️ 3. Gerador de Etiquetas QR Code",
        "ℹ️ 4. Como Funciona (Guia Rápido)",
    ])

    # =========================================================================
    # ABA 1: PORTAL DO CLIENTE (TRIAGEM ÁGIL E HUMANIZADA)
    # =========================================================================
    with aba_portal:
        if qr_eq_param and (qr_cli_param or qr_cnpj_param):
            st.markdown(
                f"""
                <div style="background: linear-gradient(90deg, #064e3b 0%, #022c22 100%); border: 1.5px solid #10b981; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
                    <div style="font-weight: 800; color: #6ee7b7; font-size: 14px;">
                        🏷️ EQUIPAMENTO IDENTIFICADO POR QR CODE
                    </div>
                    <div style="color: #f1f5f9; font-size: 13px; margin-top: 4px;">
                        <b>Cliente:</b> {qr_cli_param} {f'({qr_cnpj_param})' if qr_cnpj_param else ''}<br/>
                        <b>Equipamento:</b> {qr_eq_param}
                    </div>
                    <div style="color: #a7f3d0; font-size: 12px; margin-top: 4px;">
                        ⚡ Cadastro identificado automaticamente. Pule direto para o relato da falha e foto abaixo!
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 📋 Solicitação de Atendimento Técnico")
        st.caption("Identifique a sua instituição e relate o problema. Os dados alimentarão diretamente a Ordem de Serviço.")

        col_id1, col_id2 = st.columns([2.5, 1.5])
        with col_id1:
            valor_padrao_busca = qr_cnpj_param or qr_cli_param or ""
            termo_cli = st.text_input(
                "1. Digite o CNPJ ou Nome da Clínica / Hospital *",
                value=valor_padrao_busca,
                placeholder="Ex: 03.611.974/0001-08 ou Hospital São Mateus",
                help="Você pode digitar apenas os números do CNPJ ou o nome da instituição."
            )
        
        cliente_selecionado = None
        linhas_cliente = pd.DataFrame()

        if termo_cli:
            linhas_cliente = _buscar_cliente_por_cnpj_ou_nome(df, termo_cli)
            if linhas_cliente.empty:
                st.warning("⚠️ Instituição não localizada no cadastro imediato. Você pode prosseguir digitando o nome completo abaixo:")
                cliente_manual = st.text_input("Nome da Instituição:", value=termo_cli.strip().upper())
                cliente_selecionado = cliente_manual
            else:
                clientes_unicos = linhas_cliente["cliente"].dropna().unique().tolist()
                if len(clientes_unicos) == 1:
                    cliente_selecionado = clientes_unicos[0]
                    st.success(f"✅ **Instituição Identificada:** {cliente_selecionado}")
                else:
                    cliente_selecionado = st.selectbox(
                        "Selecione a Unidade Encontrada:",
                        clientes_unicos,
                    )
        else:
            # Lista de apoio
            clientes_todos = sorted([c for c in df["cliente"].dropna().unique() if str(c).strip() and "NENHUM" not in str(c).upper()])
            cliente_selecionado = st.selectbox(
                "Ou escolha na lista de clientes cadastrados:",
                [""] + clientes_todos,
            )

        if cliente_selecionado:
            dados_cli = df[df["cliente"] == cliente_selecionado]
            primeira_linha = dados_cli.iloc[0] if not dados_cli.empty else {}
            
            cnpj_cli = limpar_texto(primeira_linha.get("cnpj"), "Não cadastrado")
            end_cli = limpar_texto(primeira_linha.get("endereco"), "Fortaleza - CE")
            cid_cli = limpar_texto(primeira_linha.get("cidade"), "FORTALEZA")
            uf_cli = limpar_texto(primeira_linha.get("estado"), "CE")
            resp_cli = limpar_texto(primeira_linha.get("responsavel_hospital"), "")
            tel_cli = limpar_texto(primeira_linha.get("contato_responsavel"), limpar_texto(primeira_linha.get("whatsapp"), ""))

            st.markdown(
                f"""
                <div style="background: #1e293b; border-left: 4px solid #38bdf8; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 10px 0;">
                    <b>📍 Endereço Cadastrado:</b> {end_cli} — {cid_cli}/{uf_cli} | <b>CNPJ:</b> {cnpj_cli}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("---")
            st.markdown("#### 2. Qual o equipamento que precisa de intervenção?")

            eqs_cadastrados = [
                e for e in dados_cli["equipamento"].dropna().unique().tolist()
                if str(e).strip() and not str(e).lower().startswith(("nenhum", "aguardando"))
            ]

            if not eqs_cadastrados:
                eqs_cadastrados = ["OUTRO / EQUIPAMENTO AVULSO"]

            col_eq1, col_eq2 = st.columns([2.5, 1.5])
            with col_eq1:
                opcoes_eq_totais = eqs_cadastrados + ["➕ Outro Equipamento"]
                idx_eq_padrao = 0
                if qr_eq_param:
                    for i_cand, cand in enumerate(opcoes_eq_totais):
                        if qr_eq_param.upper() in cand.upper():
                            idx_eq_padrao = i_cand
                            break
                equip_escolhido = st.selectbox(
                    "Selecione o equipamento alvo *",
                    opcoes_eq_totais,
                    index=idx_eq_padrao,
                )
                if equip_escolhido == "➕ Outro Equipamento":
                    equip_escolhido = st.text_input("Especifique o Fabricante, Modelo e Sala do Equipamento:")
            
            with col_eq2:
                estado_operacional = st.radio(
                    "Estado atual do equipamento: *",
                    [
                        "🔴 Totalmente Parado / Fora de Uso (Urgente)",
                        "🟡 Operando com Limitações / Mensagem de Erro",
                        "🟢 Funcionando (Preventiva / Calibração)",
                    ],
                    index=0,
                )

            st.markdown("---")
            st.markdown("#### 3. O que está acontecendo com o equipamento?")

            defeito_digitado = st.text_area(
                "Descreva com suas palavras o defeito apresentado ou código de erro na tela: *",
                placeholder="Ex: O tomógrafo parou de emitir feixe no meio do exame e apareceu mensagem de erro de comunicação do gantry...",
                height=100,
            )

            # Dica Técnica Inteligente (baseada nas ITs e POPs da EMED)
            if defeito_digitado and equip_escolhido:
                dica_it = _obter_dica_rapida_it(equip_escolhido, defeito_digitado)
                if dica_it:
                    st.info(dica_it)

            st.markdown("---")
            modalidade = _detectar_modalidade(equip_escolhido, defeito_digitado)

            if modalidade == "RAIO-X":
                st.markdown("#### ⚡ 3.1 Triagem Técnica Específica para Sistema de Raio-X (Checklist em 5 Segundos)")
                st.caption("Perguntas diretas sobre alimentação, estativa porta-tubo e eletrofreios:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Alimentação Elétrica"
                    chk_1 = st.radio(
                        "⚡ 1. Alimentação Elétrica (Quadro de Força):",
                        [
                            "🟢 Não foi observada oscilação (Fornecimento elétrico normal)",
                            "🟡 Houve oscilações na rede elétrica, mas o quadro já estabilizou",
                            "🔴 Sim, houve desarme de disjuntor no quadro de força",
                        ],
                        index=0,
                        help="Houve oscilação na rede elétrica? Se sim, algum disjuntor desarmou?"
                    )
                    nome_p2 = "Estativa & Eletrofreio"
                    chk_2 = st.radio(
                        "🧲 2. Estativa Porta-Tubo & Eletrofreio:",
                        [
                            "🟢 Movimento normal (Freio atuando e segurando)",
                            "⚠️ Movimento totalmente solto / livre (o freio não segura a estativa)",
                            "⚠️ O movimento chega a travar em algum ponto do trilho ou patina?",
                            "🚨 Todos os freios da sala (estativa e mesa) pararam de atuar (possível fonte de alimentação)",
                        ],
                        index=1 if any(w in (defeito_digitado or "").upper() for w in ["FREIO", "ESTATIVA", "TRAVA", "HORIZONTAL", "VERTICAL", "SOLTO", "LIVRE"]) else 0,
                        help="Identifica se o freio não segura (estativa solta), se emperra no trilho ou se é falha geral da fonte de alimentação."
                    )

                with c_chk2:
                    nome_p3 = "Botão & Resposta Sonora"
                    chk_3 = st.radio(
                        "🔊 3. Botão de Acionamento & Resposta Sonora do Freio:",
                        [
                            "🟢 Escuta o estalo/clique da bobina solenoide ao apertar o botão",
                            "🔇 Não escuta nenhum clique/ruído ao apertar o botão (sem resposta elétrica)",
                            "⚠️ Escuta ruído contínuo, zumbido anormal ou vibração",
                            "❌ Botão de comando com defeito físico, solto ou emperrado",
                        ],
                        index=0,
                        help="Determina se a falha é elétrica no botão/cabo ou mecânica no eletrofreio/ajuste."
                    )

            elif modalidade == "TOMOGRAFIA":
                st.markdown("#### ⚡ 3.1 Triagem Técnica Específica para Tomógrafo (Checklist em 5 Segundos)")
                st.caption("Perguntas focadas em Quadro de Força, PDU, Gantry, Mesa e Console:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Quadro / PDU / Estabilizador"
                    chk_1 = st.radio(
                        "⚡ 1. Alimentação Elétrica (Quadro de Força, PDU / Estabilizador):",
                        [
                            "🟢 Fornecimento normal (PDU e Nobreak/Estabilizador operacionais)",
                            "🟡 Houve oscilações de rede / gerador, mas já estabilizou",
                            "🔴 Disjuntor principal do PDU caiu ou Nobreak em alarme sonoro",
                        ],
                        index=0,
                    )
                    nome_p2 = "Gantry & Mesa"
                    chk_2 = st.radio(
                        "🌀 2. Gantry & Mesa de Exames:",
                        [
                            "🟢 Gantry energizado, rotação livre e mesa movimenta normalmente",
                            "⚠️ Gantry bloqueado por interlock/comunicação ou parada de emergência",
                            "🚨 Mesa travada ou ruído anormal/vibração durante a rotação do Gantry",
                        ],
                        index=0,
                    )

                with c_chk2:
                    nome_p3 = "Console de Operação"
                    chk_3 = st.radio(
                        "🖥️ 3. Console de Operação & Software:",
                        [
                            "🟢 Console inicializa normalmente e abre tela de exames",
                            "🔄 Reiniciamos a console e a mensagem de erro persiste",
                            "❌ Console congelada / Não carrega o software de exame",
                        ],
                        index=0,
                    )

            elif modalidade == "ARCO CIRÚRGICO":
                st.markdown("#### ⚡ 3.1 Triagem Técnica para Arco Cirúrgico (C-Arm)")
                st.caption("Perguntas focadas em alimentação, braço em C, pedal e carrinho dos monitores:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Alimentação & Cabo"
                    chk_1 = st.radio(
                        "⚡ 1. Alimentação Elétrica & Cabo Umbilical / Interligação:",
                        [
                            "🟢 Cabo e conexões elétricas normais (Carrinho energizado)",
                            "🟡 Oscilação na rede da sala cirúrgica",
                            "🔴 Aparelho sem força / Nobreak do carrinho em alarme",
                        ],
                        index=0,
                    )
                    nome_p2 = "Braço em C"
                    chk_2 = st.radio(
                        "🦾 2. Braço em C (Movimentos Orbitais & Freios Manuais):",
                        [
                            "🟢 Todos os freios e movimentos orbitais/angulares livres",
                            "⚠️ Freio orbital ou angular específico duro/travado",
                            "🚨 Braço em C totalmente bloqueado em todos os eixos",
                        ],
                        index=0,
                    )

                with c_chk2:
                    nome_p3 = "Monitores & Pedal"
                    chk_3 = st.radio(
                        "🦶 3. Carrinho dos Monitores & Pedal de Disparo:",
                        [
                            "🟢 Imagem nítida nos monitores e pedal acionando normalmente",
                            "⚠️ Pedal falhando intermitente ou cabo com mau contato",
                            "❌ Sem sinal de vídeo nos monitores ou erro de fluoroscopia",
                        ],
                        index=0,
                    )

            elif modalidade == "MAMOGRAFIA":
                st.markdown("#### ⚡ 3.1 Triagem Técnica para Mamógrafo")
                st.caption("Perguntas focadas em Quadro de Força, Gantry, Compressor e Painel:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Quadro de Força"
                    chk_1 = st.radio(
                        "⚡ 1. Quadro de Força & Alimentação Elétrica:",
                        [
                            "🟢 Alimentação normal e disjuntores ligados",
                            "🟡 Instabilidade momentânea na rede elétrica",
                            "🔴 Disjuntor desarmou no quadro de força / Sistema apagado",
                        ],
                        index=0,
                    )
                    nome_p2 = "Gantry & Compressor"
                    chk_2 = st.radio(
                        "🗜️ 2. Gantry & Sistema de Compressão da Mama:",
                        [
                            "🟢 Compressor sobe e desce suavemente",
                            "⚠️ Prato de compressão duro ou não sobe",
                            "🚨 Descompressão automática travada ou acionada em emergência",
                        ],
                        index=0,
                    )

                with c_chk2:
                    nome_p3 = "Painel & Biombo"
                    chk_3 = st.radio(
                        "🖥️ 3. Painel de Operação & Vidro Plumbífero:",
                        [
                            "🟢 Painel respondendo e intertravamento de segurança íntegro",
                            "⚠️ Mensagem de erro no painel ou botão com mau contato",
                            "❌ Painel travado / Sem resposta aos comandos de exposição",
                        ],
                        index=0,
                    )

            elif modalidade == "DENSITOMETRIA":
                st.markdown("#### ⚡ 3.1 Triagem Técnica para Densitometria Óssea")
                st.caption("Perguntas focadas em Fonte HV, Mesa, Braço C, Shutter e Software:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Fonte HV & Alimentação"
                    chk_1 = st.radio(
                        "⚡ 1. Fonte de Alta Tensão & Alimentação Elétrica:",
                        [
                            "🟢 Alimentação estável e fonte de alta tensão sem desarme",
                            "🟡 Oscilação momentânea na rede elétrica",
                            "🔴 Fonte de alta tensão desarmada / Sem alimentação",
                        ],
                        index=0,
                    )
                    nome_p2 = "Mesa, Braço C & Shutter"
                    chk_2 = st.radio(
                        "🦴 2. Mesa de Exames & Braço C (Shutter/Colimador):",
                        [
                            "🟢 Braço C desliza suavemente sobre a mesa e shutter abre normal",
                            "⚠️ Movimento do braço C pesado/patinando ou shutter emperrado",
                            "🚨 Braço C totalmente travado ou colimador bloqueado",
                        ],
                        index=0,
                    )

                with c_chk2:
                    nome_p3 = "Computador & Cabos HV"
                    chk_3 = st.radio(
                        "💻 3. Computador com Software & Cabos de Alta Tensão:",
                        [
                            "🟢 Software comunica normalmente com o equipamento",
                            "⚠️ Erro de comunicação serial/USB entre computador e mesa",
                            "❌ Software trava na calibração diária ou falha nos cabos HV",
                        ],
                        index=0,
                    )

            else:
                st.markdown("#### ⚡ 3.1 Triagem Rápida de Campo (Checklist em 5 Segundos)")
                st.caption("Marque as condições básicas observadas para direcionar o diagnóstico técnico:")

                c_chk1, c_chk2 = st.columns(2)
                with c_chk1:
                    nome_p1 = "Alimentação Elétrica"
                    chk_1 = st.radio(
                        "⚡ 1. Alimentação Elétrica (Quadro de Força):",
                        [
                            "🟢 Não foi observada oscilação (Fornecimento normal)",
                            "🟡 Sim, houve oscilações / queda, mas a rede já estabilizou",
                            "🔴 Sim, houve desarme de disjuntor no quadro",
                        ],
                        index=0,
                    )
                    nome_p2 = "Mecânica & Estrutura"
                    chk_2 = st.radio(
                        "⚙️ 2. Funcionamento Mecânico & Estrutural:",
                        [
                            "🟢 Movimentação mecânica normal",
                            "⚠️ Travamento ou folga em movimento específico",
                            "🚨 Equipamento totalmente imobilizado",
                        ],
                        index=0,
                    )

                with c_chk2:
                    nome_p3 = "Painel & Comandos"
                    chk_3 = st.radio(
                        "🖥️ 3. Painel de Controle & Comandos:",
                        [
                            "🟢 Comandos e botões respondendo normalmente",
                            "🔄 Reiniciamos o equipamento e o erro persistiu",
                            "❌ Painel inoperante ou travado na inicialização",
                        ],
                        index=0,
                    )

            st.markdown("---")
            st.markdown("#### 📸 3.2 Foto do Painel & Dados do Solicitante")
            col_foto1, col_foto2 = st.columns(2)
            with col_foto1:
                arquivo_foto = st.file_uploader(
                    "📸 Anexar Foto do Painel / Código de Erro (Câmera ou Galeria)",
                    type=["jpg", "jpeg", "png"],
                    help="Tire uma foto do display onde o erro aparece. Ela será anexada automaticamente na Folha de OS oficial.",
                )
            with col_foto2:
                nome_solicitante = st.text_input(
                    "Nome de quem está solicitando o chamado:",
                    value=resp_cli,
                    placeholder="Ex: Dra. Mariana / Enf. Carlos / Biomédico",
                )
                contato_solicitante = st.text_input(
                    "Telefone / WhatsApp para contato da equipe técnica:",
                    value=tel_cli,
                    placeholder="(85) 99999-9999",
                )

            st.markdown("<br/>", unsafe_allow_html=True)
            
            # Botão de Envio de Chamado
            col_b1, col_b2 = st.columns([1.5, 2.5])
            with col_b1:
                confirmou_envio = st.button(
                    "🚀 Confirmar Abertura de Chamado Emergencial",
                    type="primary",
                    use_container_width=True,
                )

            if confirmou_envio:
                if not defeito_digitado.strip():
                    st.error("⚠️ Por favor, informe o defeito apresentado pelo equipamento para abrir o chamado.")
                else:
                    # Salva a foto se houver
                    pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                    os.makedirs(pasta_uploads, exist_ok=True)
                    caminho_foto_final = ""
                    if arquivo_foto is not None:
                        nome_arq_foto = f"FOTO_EMEDONLINE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo_foto.name}"
                        caminho_foto_final = os.path.join(pasta_uploads, nome_arq_foto)
                        with open(caminho_foto_final, "wb") as f:
                            f.write(arquivo_foto.getbuffer())

                    # Define a criticidade
                    is_urgente = "Totalmente Parado" in estado_operacional
                    tag_prioridade = "P1 - EMERGÊNCIA MÉDICA" if is_urgente else "P2 - PROGRAMADO"
                    cond_ini = "PARADO (INOPERANTE)" if is_urgente else "OPERANDO COM FALHA"

                    # Verifica equipe próxima por cidade
                    tec_sugerido = "EQUIPE EMED PLANTÃO"
                    for t_nome, t_dados in equipa_tecnica.items():
                        cidade_tec = t_dados.get("sede", "FORTALEZA").upper()
                        if cidade_tec in cid_cli.upper():
                            tec_sugerido = t_nome
                            break

                    kit_sugerido = obter_kit_por_servico("CORRETIVA", defeito_digitado)
                    checklist_resumo = (
                        f"[{nome_p1}: {chk_1}] "
                        f"[{nome_p2}: {chk_2}] "
                        f"[{nome_p3}: {chk_3}]"
                    )

                    novo_chamado = {
                        "cliente": cliente_selecionado.strip().upper(),
                        "cidade": cid_cli.upper(),
                        "estado": uf_cli.upper(),
                        "equipamento": equip_escolhido.strip().upper(),
                        "endereco": end_cli.strip().upper(),
                        "tipo_servico": "CORRETIVA",
                        "data_agendamento": datetime.now().strftime("%Y-%m-%d"),
                        "tecnico_responsavel": tec_sugerido,
                        "tecnico_auxiliar": "NENHUM (INDIVIDUAL)",
                        "telefone_tecnico": equipa_tecnica.get(tec_sugerido, {}).get("telefone", "(85) 3254-2929"),
                        "responsavel_hospital": (nome_solicitante or resp_cli).strip().upper(),
                        "contato_responsavel": (contato_solicitante or tel_cli).strip(),
                        "confirmado": "SIM",
                        "pendencias": f"[{tag_prioridade}] {defeito_digitado.strip().upper()}",
                        "status": "ATIVO",
                        "checkin_hora": "",
                        "checkout_hora": "",
                        "tempo_atendimento": "",
                        "checklist_pop": f"{nome_p1[:10]}: {chk_1[:25]} | {nome_p2[:10]}: {chk_2[:25]} | {nome_p3[:10]}: {chk_3[:25]}",
                        "assinatura_cliente": "",
                        "assinatura_tecnico": f"{tec_sugerido} - CFT",
                        "pre_atendimento": f"[EMEDONLINE - {modalidade}] {defeito_digitado.strip()} | {checklist_resumo} | Solicitante: {nome_solicitante}",
                        "foto_evidencia": caminho_foto_final,
                        "video_evidencia": "",
                        "formulario_anexo": "",
                        "cnpj": cnpj_cli,
                        "cep": limpar_texto(primeira_linha.get("cep"), ""),
                        "email": limpar_texto(primeira_linha.get("email"), ""),
                        "whatsapp": contato_solicitante or tel_cli,
                        "endereco_fiscal": end_cli,
                        "tipo_contrato": limpar_texto(primeira_linha.get("tipo_contrato"), "CONTRATO"),
                        "instrumento_necessario": kit_sugerido.get("nome", "MALETA DE CALIBRAÇÃO PADRÃO"),
                        "etapa_preventiva": f"CORRETIVA EMEDONLINE ({modalidade})",
                        "orcamento_anexo": "",
                        "condicao_pagamento": "",
                        "valor_os": 0.0,
                        "defeito_relatado": defeito_digitado.strip().upper(),
                        "condicao_inicial": cond_ini,
                        "problemas_encontrados": "",
                        "causa_raiz": "",
                        "servico_executado": "",
                        "parametros_medidos": "",
                        "observacoes_gerais": f"Chamado aberto via EmedOnline ({modalidade}) em {datetime.now().strftime('%d/%m/%Y %H:%M')}.",
                        "condicao_final": "EM ATENDIMENTO",
                        "foto_depois": "",
                        "assinatura_cliente_img": "",
                        "peca_baixada_ref": "",
                    }

                    df_novo = pd.concat([df, pd.DataFrame([novo_chamado])], ignore_index=True)
                    if salvar_dados_seguro(df_novo, ctx.db_name, ctx.caminho_excel):
                        st.cache_data.clear()
                        novo_idx = df_novo.index[-1]
                        num_os_gerada = obter_id_os(novo_idx, pd.Series(novo_chamado))
                        
                        st.balloons()
                        st.success(f"🎉 **Chamado Aberto com Sucesso! Ordem de Serviço Nº #{num_os_gerada} emitida.**")
                        
                        # Mensagem objetiva para despacho e alinhamento da equipe
                        msg_whats = (
                            f"🚨 *CHAMADO EMEDONLINE • OS #{num_os_gerada}*\n"
                            f"Cliente: {cliente_selecionado}\n"
                            f"Equipamento: {equip_escolhido} ({modalidade})\n"
                            f"Prioridade: {cond_ini}\n"
                            f"Defeito: {defeito_digitado.strip()}\n\n"
                            f"*TRIAGEM TÉCNICA ({modalidade}):*\n"
                            f"• {nome_p1}: {chk_1}\n"
                            f"• {nome_p2}: {chk_2}\n"
                            f"• {nome_p3}: {chk_3}\n\n"
                            f"🧰 Kit Sugerido: {kit_sugerido.get('nome')}\n"
                            f"Solicitante: {nome_solicitante} ({contato_solicitante})\n"
                            f"Técnico Programado: {tec_sugerido}\n"
                            f"Local: {end_cli}"
                        )
                        link_wpp = f"https://wa.me/558532542929?text={urllib.parse.quote(msg_whats)}"
                        
                        st.markdown(
                            f"""
                            <div style="background: #064e3b; border: 1.5px solid #10b981; border-radius: 8px; padding: 14px; margin-top: 10px;">
                                <h4 style="color: #6ee7b7; margin:0 0 6px 0;">✅ O que acontece agora?</h4>
                                <ul style="color: #e2e8f0; font-size: 13.5px; margin: 0 0 10px 0; padding-left: 20px;">
                                    <li>A OS já foi pré-preenchida com os dados do cliente, defeito e foto.</li>
                                    <li>O técnico designado (<b>{tec_sugerido}</b>) foi notificado para encaixe em rota.</li>
                                    <li>No local, o técnico precisará apenas lançar o serviço executado e as peças utilizadas.</li>
                                </ul>
                                <a href="{link_wpp}" target="_blank" style="display: inline-block; background: #25d366; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none;">
                                    💬 Notificar Central EMED via WhatsApp
                                </a>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    # =========================================================================
    # ABA 2: CENTRAL DE DESPACHO & ROTAS (VISÃO GESTOR / LOGÍSTICA)
    # =========================================================================
    with aba_despacho:
        st.markdown("### 🗺️ Gestão de Corretivas & Otimização de Rotas")
        st.caption("Acompanhe os chamados abertos e reordene as rotas dos técnicos em tempo real.")

        df_ativos = df[df["status"].astype(str).str.upper().isin(["ATIVO", "EM ATENDIMENTO"])]
        
        if df_ativos.empty:
            st.info("ℹ️ Não existem chamados pendentes de atendimento no momento.")
        else:
            st.markdown(f"**Total de Chamados Ativos:** `{len(df_ativos)}`")
            
            for idx_a, row_a in df_ativos.iterrows():
                id_os_a = obter_id_os(idx_a, row_a)
                cli_a = limpar_texto(row_a.get("cliente"), "N/D")
                eq_a = limpar_texto(row_a.get("equipamento"), "N/D")
                def_a = limpar_texto(row_a.get("defeito_relatado"), limpar_texto(row_a.get("pendencias"), "-"))
                tec_a = limpar_texto(row_a.get("tecnico_responsavel"), "A DEFINIR")
                cid_a = limpar_texto(row_a.get("cidade"), "FORTALEZA")
                end_a = limpar_texto(row_a.get("endereco"), "")
                cond_ini_a = limpar_texto(row_a.get("condicao_inicial"), "OPERACIONAL")
                foto_a = limpar_texto(row_a.get("foto_evidencia"), "")

                cor_borda = "#ef4444" if "PARADO" in cond_ini_a.upper() else "#38bdf8"
                badge_status = "🔴 MÁQUINA PARADA" if "PARADO" in cond_ini_a.upper() else "🟡 FALHA PARCIAL"

                with st.expander(f"OS #{id_os_a} | {badge_status} | {cli_a} — {eq_a} [Técnico: {tec_a}]"):
                    c_det1, c_det2 = st.columns([2.5, 1.5])
                    with c_det1:
                        st.markdown(f"**Cliente:** `{cli_a}` | **Cidade:** `{cid_a}`")
                        st.markdown(f"**Endereço:** {end_a}")
                        st.markdown(f"**Defeito Relatado:** {def_a}")
                        pre_at_txt = limpar_texto(row_a.get("pre_atendimento"), "")
                        if "REDE ELÉTRICA" in pre_at_txt or "ENERGIA:" in pre_at_txt:
                            st.caption(f"⚡ **Diagnóstico Preliminar:** {pre_at_txt}")
                        st.markdown(f"**Técnico Atual Designado:** `{tec_a}`")
                        
                        # Link para Waze / Google Maps
                        if end_a:
                            end_encoded = urllib.parse.quote(f"{end_a}, {cid_a}")
                            st.markdown(
                                f"""
                                <div style="margin-top: 10px;">
                                    <a href="https://www.google.com/maps/search/?api=1&query={end_encoded}" target="_blank" style="text-decoration: none; background: #0f766e; color: #fff; padding: 6px 12px; border-radius: 5px; font-size: 12px; font-weight: bold; margin-right: 8px;">
                                        📍 Ver no Google Maps
                                    </a>
                                    <a href="https://waze.com/ul?q={end_encoded}" target="_blank" style="text-decoration: none; background: #0284c7; color: #fff; padding: 6px 12px; border-radius: 5px; font-size: 12px; font-weight: bold;">
                                        🚗 Navegar pelo Waze
                                    </a>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    with c_det2:
                        if foto_a and os.path.exists(foto_a):
                            st.image(foto_a, caption="Foto do Erro / Painel enviada na triagem", use_container_width=True)
                        else:
                            st.caption("Sem foto anexada pelo solicitante.")

    # =========================================================================
    # ABA 3: GERADOR DE ETIQUETAS QR CODE POR EQUIPAMENTO
    # =========================================================================
    with aba_etiquetas:
        st.markdown("### 🏷️ Gerador de Etiquetas QR Code por Equipamento")
        st.caption("Gere a etiqueta técnica para colar no chassi do equipamento. Ao escanear, a EmedOnline já abre com CNPJ e Equipamento 100% preenchidos!")

        col_et1, col_et2 = st.columns(2)
        with col_et1:
            clientes_cadastrados = sorted([c for c in df["cliente"].dropna().unique() if str(c).strip() and "NENHUM" not in str(c).upper()])
            cli_etiqueta = st.selectbox("1. Selecione o Cliente / Hospital:", clientes_cadastrados, key="sel_cli_etiqueta")
        
        with col_et2:
            df_cli_et = df[df["cliente"] == cli_etiqueta]
            eqs_cli_et = [e for e in df_cli_et["equipamento"].dropna().unique() if str(e).strip() and "NENHUM" not in str(e).upper()]
            if not eqs_cli_et:
                eqs_cli_et = ["EQUIPAMENTO PADRÃO"]
            eq_etiqueta = st.selectbox("2. Selecione o Equipamento Alvo:", eqs_cli_et, key="sel_eq_etiqueta")

        cnpj_etiqueta = limpar_texto(df_cli_et.iloc[0].get("cnpj") if not df_cli_et.empty else "", "03.611.974/0001-08")
        
        # URL da nuvem permanente da EMED com auto-preenchimento
        base_url_cloud = "https://emed-app.streamlit.app"
        url_chamado_qr = f"{base_url_cloud}/?cliente_qr={urllib.parse.quote(cli_etiqueta)}&equipamento_qr={urllib.parse.quote(eq_etiqueta)}&cnpj={urllib.parse.quote(cnpj_etiqueta)}"
        
        # Link WhatsApp direto pré-formatado
        msg_wpp_direto = (
            f"🚨 *CHAMADO TÉCNICO • EMEDONLINE*\n"
            f"Equipamento: {eq_etiqueta}\n"
            f"Cliente: {cli_etiqueta}\n"
            f"CNPJ: {cnpj_etiqueta}\n\n"
            f"Defeito apresentado: "
        )
        url_wpp_direto = f"https://wa.me/558532542929?text={urllib.parse.quote(msg_wpp_direto)}"

        qr_base64 = _gerar_qrcode_base64(url_chamado_qr)

        st.markdown("---")
        col_preview, col_inst = st.columns([1.8, 2.2])
        with col_preview:
            st.markdown("#### 🖨️ Pré-Visualização da Etiqueta Técnica:")
            st.markdown(
                f"""
                <div style="background: #ffffff; color: #0b132b; border: 3px solid #0b132b; border-radius: 12px; padding: 18px; max-width: 380px; box-shadow: 0 4px 15px rgba(0,0,0,0.25); font-family: Arial, sans-serif;">
                    <div style="border-bottom: 2px solid #0b132b; padding-bottom: 8px; margin-bottom: 10px;">
                        <div style="font-size: 15px; font-weight: 900; color: #0b132b; letter-spacing: 0.5px;">🏥 EMED ELETROMEDICINA</div>
                        <div style="font-size: 10px; color: #334155; font-weight: bold;">SUPORTE TÉCNICO & MANUTENÇÃO</div>
                    </div>
                    <div style="text-align: center; margin: 10px 0;">
                        <img src="{qr_base64}" style="width: 175px; height: 175px; display: inline-block; border: 1px solid #cbd5e1; padding: 4px; border-radius: 6px;" alt="QR Code"/>
                        <div style="font-size: 12px; font-weight: 800; color: #0284c7; margin-top: 6px;">APONTE A CÂMERA DO CELULAR</div>
                        <div style="font-size: 10px; color: #64748b;">Abertura Direta em 10 Segundos</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 11px; margin-top: 8px; line-height: 1.4;">
                        <div><b>EQUIPAMENTO:</b> {eq_etiqueta}</div>
                        <div><b>CLIENTE:</b> {cli_etiqueta}</div>
                        <div><b>CNPJ:</b> {cnpj_etiqueta}</div>
                        <div><b>CENTRAL 24H:</b> (85) 3254-2929</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col_inst:
            st.markdown("#### ⚡ Como funciona para o cliente em campo:")
            st.markdown(
                f"""
                1. **Adesive a etiqueta** diretamente no chassi do Tomógrafo, Raio-X ou Ultrassom.
                2. Quando o aparelho apresentar qualquer anomalia ou código de erro, o operador do hospital apenas aponta a câmera do celular para o adesivo.
                3. **O sistema já abre no celular com Hospital, CNPJ e Equipamento 100% preenchidos!**
                4. O cliente apenas descreve o defeito, tira a foto do display e clica em **Chamar Equipe**.
                """
            )
            st.markdown(f"**🔗 Link Direto Integrado:**")
            st.code(url_chamado_qr, language="text")
            
            st.markdown(
                f"""
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="{url_chamado_qr}" target="_blank" style="display: inline-block; background: #0284c7; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px;">
                        🧪 Testar Link do Equipamento
                    </a>
                    <a href="{url_wpp_direto}" target="_blank" style="display: inline-block; background: #25d366; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px;">
                        💬 Abrir via WhatsApp Direto
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

    # =========================================================================
    # ABA 4: COMO FUNCIONA (GUIA TÉCNICO & PROCEDIMENTOS)
    # =========================================================================
    with aba_instrucoes:
        st.markdown("### 📘 Fluxo de Trabalho EmedOnline & Fechamento de OS")
        st.markdown(
            """
            O objetivo da **EmedOnline** é cortar a burocracia e acelerar o tempo de resposta médica para equipamentos de diagnóstico por imagem:

            1. **O Cliente / Hospital relata:**
               - Informa o CNPJ ou nome da instituição.
               - Seleciona o equipamento e relata o defeito com 1 foto do display de erro.
            2. **O Sistema automatiza:**
               - Classifica se é parada total de hospital (Prioridade 1) ou falha pontual.
               - Sugere orientações preliminares das **Instruções de Trabalho (ITs) e POPs da EMED**.
               - Encaixa na rota da equipe técnica mais próxima.
            3. **O que sobra para o Técnico preencher em campo (Aba Chamados & OS)?**
               - 🛠️ **Serviço Executado** (o diagnóstico real e o conserto feito).
               - 📦 **Peças Utilizadas** (baixa no estoque e geração de cobrança).
               - 🚨 **Pendências Técnicas** (se alguma peça ficou sob encomenda).
               - 📝 **Observações & Assinatura** do cliente no vidro do celular.
            """
        )
