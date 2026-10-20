# emed_views/manuais_tecnicos.py - Módulo de Consulta de Manuais, ITs e Procedimentos Técnicos
import os
import base64
import datetime
import webbrowser
import streamlit as st
from emed_services import AppContext


DICIONARIO_NOMES_AMIGAVEIS = {
    # Raio-X Lotus HF500M
    "01_Manual_Pre_Instalacao_Oficial_Lotus_HF500M.pdf": "📖 Manual Oficial de Pré-Instalação Lotus HF500M (Fábrica)",
    "02_Formulario_Vistoria_Pre_Instalacao_Lotus_HF500M_eMED.pdf": "📋 Formulário de Vistoria de Pré-Instalação HF500M (eMED Gatekeeper)",
    
    # ITs Principais
    "IT_01_Troca_de_Tubo_GE_Brivo385.md": "⚡ IT-01: Troca de Tubo & Pipeline Completo de Calibração (Brivo CT385)",
    "IT_02_Manutencao_Preventiva_GE_BrightSpeed.md": "🔧 IT-02: Manutenção Preventiva Periódica - PM Schedules A, B, C, D (BrightSpeed)",
    "IT_03_Troca_de_Tubo_GE_BrightSpeed.md": "⚡ IT-03: Troca de Tubo & Alinhamento Óptico do Colimador (BrightSpeed)",
    "IT_04_Balanceamento_Gantry_GE.md": "⚖️ IT-04: Balanceamento Estático & Dinâmico do Gantry (160 N·m / Matriz)",
    "IT_05_Diagnostico_Ajuste_SlipRing_GE.md": "📡 IT-05: Diagnóstico, Limpeza e Ajuste do Slip Ring e Antena HSDCD (750V DC)",
    "IT_06_Alinhamentos_Opticos_Colimador_Detector_GE.md": "🎯 IT-06: Alinhamentos Ópticos do Colimador e Detector (BOW, CBF/SAG)",
    "IT_07_Guia_Ferramenta_Gerador_JEDI_GE.md": "⚡ IT-07: Guia Operacional da Ferramenta do Gerador JEDI (Traduzido)",
    "IT_08_Verificacao_Tanque_HV_e_QA_GE.md": "🔬 IT-08: Verificação do Tanque HV, Medidores & Teste Final de QA (Água 0 ± 4 HU)",
    "IT_09_Alinhamento_Plano_de_Rotacao_POR_GE.md": "📐 IT-09: Alinhamento do Plano de Rotação (Plane of Rotation - POR)",
    "IT_10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.md": "🎯 IT-10: Alinhamento do Isocentro Mecânico (ISO) & Feixe Ativo (HOT ISO)",
    "IT_11_Calibracao_Colimador_Aberturas_e_Detailed_Cal_GE.md": "🔬 IT-11: Calibração das Aberturas do Colimador & Detailed Calibration",
    "IT_12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.md": "🛡️ IT-12: Segurança de Rotação, Varreduras Térmicas HHS & Estabilidade",
    
    # Brivo CT385 - Calibrações e Procedimentos
    "01_Procedimento_Troca_de_Tubo_Gantry.pdf": "01. Procedimento Oficial de Troca do Tubo de Raio-X no Gantry",
    "02_Configuracao_Novo_Tubo_Software.pdf": "02. Configuração do Novo Tubo no Software (Service Desktop)",
    "03_Reset_Contadores_TnT.pdf": "03. Reset dos Contadores de Tempo e Disparos (TnT)",
    "04_Verificacao_Resistores_Feedback_Tanque_HV.pdf": "04. Verificação de Resistores de Feedback do Tanque de Alta Tensão",
    "05_Verificacao_Medidores.pdf": "05. Verificação dos Medidores de Tensão e Corrente (Meter Verification)",
    "06_Calibracao_de_Filamento.pdf": "06. Calibração de Filamento e Corrente do Tubo (mA Calibration)",
    "07_Alinhamento_Plano_de_Rotacao_POR.pdf": "07. Alinhamento do Plano de Rotação (Plane of Rotation - POR)",
    "08_Alinhamento_Feixe_Janela_BOW.pdf": "08. Alinhamento do Feixe de Raio-X na Janela (Beam on Window - BOW)",
    "09_Alinhamento_ISO.pdf": "09. Alinhamento do Isocentro Mecânico (ISO Alignment)",
    "10_Alinhamento_HOT_ISO.pdf": "10. Alinhamento HOT ISO com Emissão de Raio-X Ativa",
    "11_Alinhamento_CBF_SAG.pdf": "11. Alinhamento de Filtros CBF e SAG do Colimador",
    "12_Calibracao_do_Colimador.pdf": "12. Calibração e Centralização das Aberturas do Colimador",
    "13_Calibracao_Detalhada_do_Sistema.pdf": "13. Calibração Detalhada do Sistema (Detailed Calibration)",
    "14_Procedimento_Balanceamento_Gantry.pdf": "14. Procedimento Oficial de Balanceamento de Gantry",
    "15_Checagem_Seguranca_Rotacao_Gantry.pdf": "15. Checagem de Segurança de Rotação do Gantry",
    "16_Varreduras_HHS_Avancadas.pdf": "16. Varreduras de Alta Resolução HHS Avançadas",
    "17_Teste_de_Varredura_do_Sistema.pdf": "17. Teste de Varredura e Estabilidade do Sistema",
    "18_Teste_Garantia_da_Qualidade_QA.pdf": "18. Teste Final de Garantia da Qualidade (QA Test H2O 0 ± 4 HU)",
    
    # Brivo CT385 - Software
    "01_Ferramenta_Gerador_JEDI.pdf": "01. Manual da Ferramenta de Calibração do Gerador JEDI",
    "02_Estatisticas_Uso_do_Tubo.pdf": "02. Estatísticas de Uso do Tubo de Raio-X (07MWxx.x)",
    "03_Comandos_Linux_GE.pdf": "03. Guia de Comandos do Terminal Linux GE Healthcare",
    "04_Utilitarios_Diagnostico_Linux.pdf": "04. Utilitários de Diagnóstico e Recuperação Linux",

    # Shimadzu MobileDaRt MX8
    "01_Manual_de_Servico_MobileDaRt_MX8_Shimadzu.pdf": "📘 Manual de Serviço Completo MobileDaRt Evolution MX8 (Shimadzu 344p)",
    "02_Manual_de_Instalacao_MobileDaRt_MX8_Shimadzu.pdf": "📑 Manual de Instalação e Montagem MobileDaRt MX8 (Shimadzu 560p)",
    "IT_RXM_SHIM_001_Manutencao_Descarga_Capacitores_MobileDaRt_MX8.md": "⚡ IT-01: Manutenção, Diagnóstico de Falhas & Descarga de Capacitores (Shimadzu MX8)",
    "IT_RXM_SHIM_002_Calibracao_Manopla_Balanca_Sensor_Braco_MX8.md": "🎯 IT-02: Calibração da Manopla com Balança (FSR) & Sensor do Braço no Catcher (Andar Frente/Trás)",

    # Lotus Família HF
    "01_Manual_Usuario_Familia_HF_Parte_1.pdf": "📖 Manual do Usuário e Operação - Família HF Raio-X Fixo (Lotus)",

    # Neusoft NeuVision 550M
    "01_Manual_Instalacao_Software_NeuVision_550M_Plus.pdf": "💻 Manual de Instalação do Software DR NeuVision 550M Plus (Neusoft)"
}

DICIONARIO_SUBGRUPOS = {
    "01_INSTRUCOES_DE_TRABALHO": "📋 INSTRUÇÕES DE TRABALHO (ITs)",
    "02_CALIBRACOES_E_PROCEDIMENTOS_OFICIAIS": "🔬 CALIBRAÇÕES E PROCEDIMENTOS OFICIAIS",
    "03_SOFTWARE_E_UTILITARIOS_LINUX": "💻 SOFTWARE E UTILITÁRIOS LINUX",
    "02_PORTAL_INTERATIVO_SERVICE_METHODS": "🌐 PORTAL INTERATIVO SERVICE METHODS",
    "02_MANUAIS_DE_SERVICO_E_INSTALACAO": "📚 MANUAIS DE SERVIÇO & INSTALAÇÃO",
    "01_MANUAIS_DE_OPERACAO": "📖 MANUAIS DE OPERAÇÃO",
    "01_MANUAIS_DE_SOFTWARE_DR": "💻 SOFTWARE DR & INSTALAÇÃO",
    "HF500M": "📄 MANUAIS E VISTORIA PRÉ-INSTALAÇÃO",
    "LOTUS": "📄 MANUAIS E VISTORIA PRÉ-INSTALAÇÃO"
}


def _obter_caminho_manuais(ctx: AppContext) -> str:
    """Retorna o caminho absoluto do diretório de Manuais."""
    caminho = os.path.join(ctx.base_dir, "Manuais")
    if not os.path.exists(caminho):
        os.makedirs(caminho, exist_ok=True)
    return caminho


def _formatar_nome_amigavel(nome_arquivo: str) -> str:
    """Retorna um nome descritivo e amigável em português para o documento."""
    if nome_arquivo in DICIONARIO_NOMES_AMIGAVEIS:
        return DICIONARIO_NOMES_AMIGAVEIS[nome_arquivo]
    # Limpeza padrão caso não mapeado
    nome_sem_ext = os.path.splitext(nome_arquivo)[0]
    return nome_sem_ext.replace("_", " ").title()


def _formatar_subgrupo_amigavel(raw_subgrupo: str) -> str:
    """Retorna um título claro para a aba do submenu."""
    return DICIONARIO_SUBGRUPOS.get(raw_subgrupo, raw_subgrupo.replace("_", " ").upper())


def _escanear_arvore_manuais(pasta_base: str):
    """Varre recursivamente a pasta de manuais, filtrando assets internos e organizando em catálogo."""
    catalogo = []
    if not os.path.exists(pasta_base):
        return catalogo

    extensoes_permitidas = (".pdf", ".md", ".docx", ".doc")
    pastas_ignoradas = {
        "media", "content", "css", "scripts", "icons", "search", 
        "toc", "forms", "images", "__pycache__", ".git", "system utiliies"
    }

    for root, dirs, files in os.walk(pasta_base):
        # Impede que o os.walk desça em pastas de assets internos do HTML
        dirs[:] = [d for d in dirs if d.lower() not in pastas_ignoradas]

        for f in files:
            if f.lower().endswith(extensoes_permitidas):
                caminho_completo = os.path.join(root, f)
                rel_path = os.path.relpath(caminho_completo, pasta_base)
                partes = rel_path.split(os.sep)

                # Tratamento de subdiretórios com Categoria / Fabricante / Modelo / Submenu
                # Ex: TOMOGRAFO / GE / BRIVO_CT385 / 01_INSTRUCOES_DE_TRABALHO / file.md (len = 5)
                # Ex: RAIO-X / LOTUS / HF500M / file.pdf (len = 4)
                if len(partes) >= 5 and partes[1].upper() in ("GE", "SIEMENS", "PHILIPS", "CANON", "TOSHIBA", "SHIMADZU", "LOTUS", "NEUSOFT"):
                    categoria = f"{partes[0].replace('_', ' ').upper()} ({partes[1].upper()})"
                    modelo = partes[2].replace("_", " ").upper()
                    raw_sub = partes[3]
                    subgrupo = _formatar_subgrupo_amigavel(raw_sub)
                elif len(partes) == 4 and partes[1].upper() in ("GE", "SIEMENS", "PHILIPS", "CANON", "TOSHIBA", "SHIMADZU", "LOTUS", "NEUSOFT"):
                    categoria = f"{partes[0].replace('_', ' ').upper()} ({partes[1].upper()})"
                    modelo = partes[2].replace("_", " ").upper()
                    subgrupo = "📄 MANUAIS E VISTORIA PRÉ-INSTALAÇÃO"
                elif len(partes) == 3:
                    categoria = partes[0].replace("_", " ").upper()
                    modelo = partes[1].replace("_", " ").upper()
                    subgrupo = _formatar_subgrupo_amigavel(partes[1])
                elif len(partes) >= 4:
                    categoria = partes[0].replace("_", " ").upper()
                    modelo = partes[1].replace("_", " ").upper()
                    subgrupo = _formatar_subgrupo_amigavel(partes[2])
                else:
                    categoria = partes[0].replace("_", " ").upper()
                    modelo = "GERAL"
                    subgrupo = "DOCUMENTOS DIVERSOS"

                catalogo.append({
                    "nome_arquivo": f,
                    "titulo_amigavel": _formatar_nome_amigavel(f),
                    "caminho": caminho_completo,
                    "rel_path": rel_path,
                    "categoria": categoria,
                    "modelo": modelo,
                    "subgrupo": subgrupo,
                    "tipo": "MARKDOWN" if f.lower().endswith(".md") else "PDF" if f.lower().endswith(".pdf") else "OUTRO",
                    "tamanho_mb": os.path.getsize(caminho_completo) / (1024 * 1024),
                    "data_mod": datetime.datetime.fromtimestamp(os.path.getmtime(caminho_completo)).strftime("%d/%m/%Y %H:%M")
                })
    return catalogo


def _abrir_no_sistema_operacional(caminho: str) -> bool:
    """Abre qualquer arquivo no visualizador nativo padrão de forma multi-plataforma e à prova de falhas."""
    try:
        if hasattr(os, "startfile"):
            os.startfile(caminho)
            return True
    except Exception:
        pass
    try:
        import webbrowser
        webbrowser.open(f"file:///{os.path.abspath(caminho)}")
        return True
    except Exception:
        pass
    try:
        import subprocess
        subprocess.Popen(f'start "" "{caminho}"', shell=True)
        return True
    except Exception:
        pass
    return False


def _renderizar_leitor_pdf(caminho_pdf: str, doc_key: str):
    """Exibe o leitor de PDF inline com renderização nativa via PyMuPDF e paginação de alta fidelidade."""
    # Botão de abertura externa desacoplado do try de renderização de páginas
    col_win, col_prev, col_info, col_next = st.columns([1.6, 1.2, 1.5, 1.2])

    with col_win:
        if st.button("🖥️ Abrir no App do Windows", key=f"btn_win_{doc_key}", use_container_width=True):
            _abrir_no_sistema_operacional(caminho_pdf)
            st.toast("Manual aberto no leitor do Windows!", icon="📄")

    try:
        import pymupdf
        doc_pdf = pymupdf.open(caminho_pdf)
        total_paginas = len(doc_pdf)

        sess_key_pag = f"pag_{doc_key}"
        if sess_key_pag not in st.session_state:
            st.session_state[sess_key_pag] = 0

        with col_prev:
            if st.button("⬅️ Anterior", key=f"prev_{doc_key}", use_container_width=True, disabled=(st.session_state[sess_key_pag] <= 0)):
                st.session_state[sess_key_pag] -= 1
                st.rerun()

        with col_info:
            pag_atual = st.session_state[sess_key_pag] + 1
            st.markdown(
                f"<div style='text-align: center; padding-top: 8px; font-weight: 600; color: #00b4d8; font-size: 0.95rem;'>"
                f"Página {pag_atual} de {total_paginas}"
                f"</div>",
                unsafe_allow_html=True
            )

        with col_next:
            if st.button("Próxima ➡️", key=f"next_{doc_key}", use_container_width=True, disabled=(st.session_state[sess_key_pag] >= total_paginas - 1)):
                st.session_state[sess_key_pag] += 1
                st.rerun()

        # Renderização da página em alta nitidez (DPI 150)
        idx_pag = min(max(0, st.session_state[sess_key_pag]), total_paginas - 1)
        pagina = doc_pdf.load_page(idx_pag)
        pix = pagina.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        
        st.markdown(
            """
            <div style="border: 2px solid #3a506b; border-radius: 8px; overflow: hidden; margin-top: 10px; background: #ffffff; text-align: center;">
            """,
            unsafe_allow_html=True
        )
        st.image(img_bytes, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        doc_pdf.close()
    except Exception as e:
        st.error(f"Erro ao renderizar pré-visualização na tela: {e}")
        st.info("💡 Você pode visualizar este manual em alta resolução clicando em **'Abrir no App do Windows'** acima ou em **'Baixar Arquivo'**.")


def _renderizar_leitor_markdown(caminho_md: str):
    """Lê e renderiza um documento Markdown de Instrução de Trabalho formatado."""
    try:
        with open(caminho_md, "r", encoding="utf-8") as f:
            conteudo = f.read()
        st.markdown(
            f"""
            <div style="background: #111a36; border: 1px solid #3a506b; padding: 25px; border-radius: 8px; margin-top: 10px;">
            """,
            unsafe_allow_html=True
        )
        st.markdown(conteudo)
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao ler instrução de trabalho: {e}")


def render_manuais_tecnicos(ctx: AppContext):
    """Renderiza a View de Consulta de Manuais Técnicos e Procedimentos com navegação em sub-abas limpas."""
    st.markdown("## 📚 Biblioteca Técnica Oficial: Manuais, POPs & ITs de Campo")
    st.markdown(
        "Acesso padronizado, catalogado e em língua portuguesa aos manuais de fábrica, instruções de "
        "trabalho (ITs) e roteiros de calibração para a equipe de engenharia clínica da **eMED Eletromedicina**."
    )

    pasta_manuais = _obter_caminho_manuais(ctx)
    catalogo = _escanear_arvore_manuais(pasta_manuais)

    if not catalogo:
        st.warning(f"Nenhum documento encontrado na pasta `{pasta_manuais}`.")
        return

    # Categorias Principais (Nível 1)
    categorias_disponiveis = sorted(list(set(doc["categoria"] for doc in catalogo)))
    cat_selecionada = st.selectbox("🏥 Categoria de Equipamento", ["TODAS AS CATEGORIAS"] + categorias_disponiveis)

    # Filtra pelo Nível 1
    docs_cat = [d for d in catalogo if (cat_selecionada == "TODAS AS CATEGORIAS" or d["categoria"] == cat_selecionada)]

    # Modelos / Sub-linhas (Nível 2)
    modelos_disponiveis = sorted(list(set(d["modelo"] for d in docs_cat if d["modelo"] != "GERAL")))
    
    col_mod, col_busca = st.columns([1, 2])
    with col_mod:
        if modelos_disponiveis:
            mod_selecionado = st.selectbox("🔬 Modelo do Equipamento", ["TODOS OS MODELOS"] + modelos_disponiveis)
        else:
            mod_selecionado = "TODOS OS MODELOS"

    with col_busca:
        termo_busca = st.text_input("🔍 Busca rápida de manual, calibração ou palavra-chave...", placeholder="Ex: Tubo, Balanceamento, Slip Ring, JEDI, POR, Lotus...")

    # Filtra pelos seletores e busca
    docs_filtrados = []
    for d in docs_cat:
        if mod_selecionado != "TODOS OS MODELOS" and d["modelo"] != mod_selecionado:
            continue
        if termo_busca:
            busca_termo = termo_busca.lower()
            if (busca_termo not in d["titulo_amigavel"].lower() and 
                busca_termo not in d["nome_arquivo"].lower() and 
                busca_termo not in d["subgrupo"].lower() and 
                busca_termo not in d["categoria"].lower()):
                continue
        docs_filtrados.append(d)

    # Caminho do frameset do Portal Service Methods
    caminho_portal_bs = os.path.join(pasta_manuais, "TOMOGRAFO", "GE", "BRIGHTSPEED_LITE", "02_PORTAL_INTERATIVO_SERVICE_METHODS", "frameset.htm")
    tem_portal_bs = os.path.exists(caminho_portal_bs)

    # Player de Vídeo de Treinamento Piloto (caso modelo Brivo ou Geral)
    caminho_video = os.path.join(ctx.base_dir, "Video_Treinamento_IT01_Piloto.mp4")
    if os.path.exists(caminho_video) and (mod_selecionado in ("TODOS OS MODELOS", "BRIVO CT385") or "TOMOGRAFO" in cat_selecionada):
        with st.expander("🎬 Assistir ao Vídeo de Treinamento Técnico: Procedimento IT-01 (Troca de Tubo Piloto)"):
            st.video(caminho_video)

    # Submenus / Abas Organizadoras
    subgrupos_presentes = sorted(list(set(d["subgrupo"] for d in docs_filtrados)))

    # Se estiver no BrightSpeed e o portal existir, adiciona a aba do Portal Interativo
    incluir_aba_portal = tem_portal_bs and (mod_selecionado in ("TODOS OS MODELOS", "BRIGHTSPEED LITE") or "TOMOGRAFO" in cat_selecionada)
    lista_abas = list(subgrupos_presentes)
    if incluir_aba_portal and "🌐 PORTAL INTERATIVO SERVICE METHODS" not in lista_abas:
        lista_abas.append("🌐 PORTAL INTERATIVO SERVICE METHODS")

    if len(lista_abas) > 1:
        abas = st.tabs(lista_abas)
        for aba, sg in zip(abas, lista_abas):
            with aba:
                if sg == "🌐 PORTAL INTERATIVO SERVICE METHODS":
                    _render_card_portal_service_methods(caminho_portal_bs)
                else:
                    docs_do_grupo = [d for d in docs_filtrados if d["subgrupo"] == sg]
                    _render_lista_cards(docs_do_grupo)
    elif len(lista_abas) == 1:
        if lista_abas[0] == "🌐 PORTAL INTERATIVO SERVICE METHODS":
            _render_card_portal_service_methods(caminho_portal_bs)
        else:
            _render_lista_cards(docs_filtrados)
    else:
        st.info("Nenhum manual encontrado para os filtros selecionados.")

    # Upload de Novo Manual com Organização Automática
    st.markdown("---")
    with st.expander("📤 Enviar Novo Manual ou Procedimento para a Biblioteca"):
        with st.form("form_upload_manual", clear_on_submit=True):
            st.markdown("##### Upload de Documento Técnico (PDF ou Markdown)")
            novo_arquivo = st.file_uploader("Selecione o arquivo do manual", type=["pdf", "md", "doc", "docx"])
            c_u1, c_u2 = st.columns(2)
            with c_u1:
                cat_up = st.text_input("Categoria Principal (ex: TOMOGRAFO/GE, RAIO-X/LOTUS)", value="TOMOGRAFO/GE")
            with c_u2:
                mod_up = st.text_input("Modelo e Pasta de Destino (ex: OPTIMA_540/01_INSTRUCOES_DE_TRABALHO)", value="OPTIMA_540/01_INSTRUCOES_DE_TRABALHO")
            
            submeter = st.form_submit_button("Salvar e Organizar na Base", type="primary")
            if submeter and novo_arquivo:
                partes_cat = [p.strip().upper().replace(" ", "_") for p in cat_up.split("/")]
                partes_mod = [p.strip().upper().replace(" ", "_") for p in mod_up.split("/")]
                pasta_alvo = os.path.join(pasta_manuais, *partes_cat, *partes_mod)
                os.makedirs(pasta_alvo, exist_ok=True)
                
                caminho_final = os.path.join(pasta_alvo, novo_arquivo.name)
                with open(caminho_final, "wb") as f_out:
                    f_out.write(novo_arquivo.getbuffer())
                
                st.success(f"✅ Arquivo `{novo_arquivo.name}` salvo e catalogado com sucesso em `{os.path.relpath(pasta_alvo, pasta_manuais)}`!")
                st.rerun()


def _render_card_portal_service_methods(caminho_frameset: str):
    """Renderiza o card oficial de acesso ao Service Methods da GE."""
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0d1b2a, #1b263b); border: 2px solid #00b4d8; padding: 24px; border-radius: 12px; margin: 15px 0;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <span style="font-size: 2.8rem;">🌐</span>
                <div>
                    <h3 style="margin: 0; color: #caf0f8; font-weight: 700;">Portal de Manuais de Serviço GE BrightSpeed Lite & Select</h3>
                    <p style="margin: 6px 0 0 0; color: #e0e1dd; font-size: 0.98rem; line-height: 1.5;">
                        Documentação eletrônica de fábrica com mais de <b>4.300 tópicos técnicos</b>, esquemáticos elétricos completos, 
                        árvore de navegação dinâmica, catálogo interativo de peças sobressalentes e sistema de busca indexada <i>dtSearch</i>.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    col_btn, _ = st.columns([1.5, 2.5])
    with col_btn:
        if st.button("🚀 Abrir Portal Interativo no Navegador (Chrome / Edge)", type="primary", use_container_width=True):
            webbrowser.open(f"file:///{os.path.abspath(caminho_frameset)}")
            st.toast("Portal GE Service Methods aberto no navegador padrão!", icon="🌐")


def _render_lista_cards(docs: list):
    """Renderiza a lista de documentos em cards informativos, elegantes e padronizados."""
    if not docs:
        st.info("Nenhum documento encontrado nesta seção.")
        return

    for idx, doc in enumerate(docs):
        with st.container():
            col_icon, col_det, col_acoes = st.columns([0.35, 3.25, 1.4])

            with col_icon:
                st.markdown("### 📋" if doc["tipo"] == "MARKDOWN" else "### 📑")

            with col_det:
                st.markdown(f"#### **{doc['titulo_amigavel']}**")
                tipo_badge = "📖 INSTRUÇÃO DE TRABALHO eMED (IT)" if doc["tipo"] == "MARKDOWN" else "📑 MANUAL OFICIAL PDF"
                st.markdown(
                    f"`{tipo_badge}` &nbsp;|&nbsp; "
                    f"💾 `{doc['tamanho_mb']:.2f} MB` &nbsp;|&nbsp; "
                    f"🕒 Atualizado em: `{doc['data_mod']}`"
                )

                # Destaque de parâmetros rápidos para ITs críticas
                if "troca_de_tubo" in doc["nome_arquivo"].lower() or "it_01" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos do Tubo (GE Brivo CT385)"):
                        st.markdown("""
                        * **P/N do Tubo Novo:** `5363417`
                        * **Torque Parafusos da Placa (M10):** **$38,4\\text{ N}\\cdot\\text{m}$** (Obrigatório novos!)
                        * **Torque Parafusos do Gantry (M12):** **$66,4\\text{ N}\\cdot\\text{m}$** (Obrigatório novos!)
                        * **Posição do Gantry para Remoção:** 3 horas (3 o'clock) com **pino de trava inserido**.
                        * **Preenchimento dos Receptáculos:** Injetar óleo dielétrico para eliminar microbolhas.
                        * **Raio de Curvatura Mínimo dos Cabos HV:** **$6,35\\text{ cm}$ ($2,5"$)**.
                        """)
                elif "balanceamento" in doc["nome_arquivo"].lower():
                    with st.expander("⚖️ Torques Críticos do Balanceamento (Gantry Balance)"):
                        st.markdown("""
                        * **Barras Roscadas a 180° (4 Porcas):** **$160,0\\text{ N}\\cdot\\text{m}$ ($118\\text{ ft}\\cdot\\text{lb}$)** com aperto cruzado.
                        * **Porcas M12 a 78°:** **$44,5\\text{ N}\\cdot\\text{m}$ ($32,8\\text{ ft}\\cdot\\text{lb}$)**.
                        * **Parafusos M12 a 78°:** **$66,4\\text{ N}\\cdot\\text{m}$ ($48,9\\text{ ft}\\cdot\\text{lb}$)**.
                        * **Kit de Pesos GE:** P/N `2381045` (Uso obrigatório de *DAS Debris Shields*).
                        """)
                elif "slipring" in doc["nome_arquivo"].lower() or "hsdcd" in doc["nome_arquivo"].lower():
                    with st.expander("📡 Limites de Ajuste do Slip Ring & HSDCD"):
                        st.markdown("""
                        * **Air-gap Antena HSDCD / Anel:** **$1,41\\text{ mm}$ ($0.060"$)** com ferramenta calibrada.
                        * **Tensão nas Pistas:** **$750\\text{V DC}$** (Inversor) e **$120\\text{V AC}$** (LOTO obrigatório).
                        * **Desgaste das Escovas:** Substituir conjunto se grafite útil for **$< 5,0\\text{ mm}$**.
                        * **Limpeza:** Apenas aspirador com filtro **HEPA** e álcool isopropílico $99,8\\%$. (Ar comprimido proibido!).
                        """)

            with col_acoes:
                # Botão de Download
                try:
                    with open(doc["caminho"], "rb") as f_down:
                        dados_bytes = f_down.read()
                    st.download_button(
                        label="📥 Baixar Arquivo",
                        data=dados_bytes,
                        file_name=doc["nome_arquivo"],
                        mime="text/markdown" if doc["tipo"] == "MARKDOWN" else "application/pdf",
                        key=f"btn_dl_{doc['rel_path']}_{idx}",
                        use_container_width=True
                    )
                except Exception as e:
                    st.error(f"Erro: {e}")

                # Botão de Leitura / Visualização Inline
                chave_view = f"view_doc_{doc['rel_path']}_{idx}"
                if chave_view not in st.session_state:
                    st.session_state[chave_view] = False

                lbl_btn = "Fechar Leitura" if st.session_state[chave_view] else ("Ler Instrução (IT)" if doc["tipo"] == "MARKDOWN" else "Visualizar PDF")
                if st.button(f"👁️ {lbl_btn}", key=f"btn_open_{doc['rel_path']}_{idx}", use_container_width=True):
                    st.session_state[chave_view] = not st.session_state[chave_view]
                    st.rerun()

            # Área de exibição inline
            if st.session_state.get(chave_view, False):
                if doc["tipo"] == "MARKDOWN":
                    _renderizar_leitor_markdown(doc["caminho"])
                else:
                    _renderizar_leitor_pdf(doc["caminho"], f"{doc['rel_path']}_{idx}")

            st.markdown("<hr style='border: 0.5px solid #233554; margin: 12px 0;'>", unsafe_allow_html=True)
