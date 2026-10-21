# emed_views/manuais_tecnicos.py - Módulo de Consulta de Manuais, ITs e Procedimentos Técnicos
import os
import re
import base64
import datetime
import webbrowser
import streamlit as st
from emed_services import AppContext


DICIONARIO_VIDEOS_ITS = {
    "IT_01_Troca_de_Tubo_GE_Brivo385.md": "Video_IT01_Troca_Tubo_GE_Brivo385.mp4",
    "IT_02_Manutencao_Preventiva_GE_BrightSpeed.md": "Video_IT02_Manutencao_Preventiva_BrightSpeed.mp4",
    "IT_03_Troca_de_Tubo_GE_BrightSpeed.md": "Video_IT03_Troca_Tubo_BrightSpeed.mp4",
    "IT_04_Balanceamento_Gantry_GE.md": "Video_IT04_Balanceamento_Gantry_GE.mp4",
    "IT_05_Diagnostico_Ajuste_SlipRing_GE.md": "Video_IT05_Diagnostico_Ajuste_SlipRing_GE.mp4",
    "IT_06_Alinhamentos_Opticos_Colimador_Detector_GE.md": "Video_IT06_Alinhamentos_Opticos_Colimador_Detector_GE.mp4",
    "IT_07_Guia_Ferramenta_Gerador_JEDI_GE.md": "Video_IT07_Guia_Ferramenta_Gerador_JEDI_GE.mp4",
    "IT_08_Verificacao_Tanque_HV_e_QA_GE.md": "Video_IT08_Verificacao_Tanque_HV_e_QA_GE.mp4",
    "IT_09_Alinhamento_Plano_de_Rotacao_POR_GE.md": "Video_IT09_Alinhamento_Plano_de_Rotacao_POR_GE.mp4",
    "IT_10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.md": "Video_IT10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.mp4",
    "IT_11_Calibracao_Colimador_Aberturas_e_Detailed_Cal_GE.md": "Video_IT11_Calibracao_Colimador_e_Detailed_Cal_GE.mp4",
    "IT_12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.md": "Video_IT12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.mp4",
    "IT_13_Substituicao_Placa_KV_Control_Board_GE_BrightSpeed.md": "Video_IT13_Substituicao_Placa_KV_Control_Board_GE.mp4",
    "IT_14_Substituicao_Controlador_Rotacao_Axial_Drive_GE_BrightSpeed.md": "Video_IT14_Substituicao_Controlador_Axial_Drive_GE.mp4",
    "IT_15_Caracterizacao_Mesa_Paciente_e_Tilt_Gantry_GE_BrightSpeed.md": "Video_IT15_Caracterizacao_Mesa_Paciente_e_Tilt_GE.mp4",
    "IT_RXM_SHIM_001_Manutencao_Descarga_Capacitores_MobileDaRt_MX8.md": "Video_IT_RXM_SHIM001_Descarga_Capacitores_MobileDaRt_MX8.mp4",
    "IT_RXM_SHIM_002_Calibracao_Manopla_Balanca_Sensor_Braco_MX8.md": "Video_IT_RXM_SHIM002_Calibracao_Manopla_Sensor_Braco_MX8.mp4",
    "IT_RXM_SHIM_003_Instalacao_Montagem_Comissionamento_MobileDaRt_MX8.md": "Video_IT_RXM_SHIM003_Instalacao_Montagem_MobileDaRt_MX8.mp4",
    "IT_RXD_NEU_001_Instalacao_Software_Configuracao_DR_NeuVision550M.md": "Video_IT_RXD_NEU001_Instalacao_Software_DR_NeuVision550M.mp4"
}


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
    "IT_13_Substituicao_Placa_KV_Control_Board_GE_BrightSpeed.md": "⚡ IT-13: Substituição da Placa Controladora de Alta Tensão (KV Control Board GE)",
    "IT_14_Substituicao_Controlador_Rotacao_Axial_Drive_GE_BrightSpeed.md": "⚙️ IT-14: Substituição do Controlador de Rotação do Gantry (Axial Drive Controller GE)",
    "IT_15_Caracterizacao_Mesa_Paciente_e_Tilt_Gantry_GE_BrightSpeed.md": "📐 IT-15: Caracterização da Mesa do Paciente (IN/OUT, UP/DOWN) & Calibração do Tilt do Gantry (GE)",
    "IT_16_Substituicao_Modulos_IGBT_Inversor_Alta_Tensao_GE_BrightSpeed.md": "⚡ IT-16: Diagnóstico & Substituição dos Módulos IGBT no Inversor JEDI (GE)",
    "IT_17_Guia_Comandos_Linux_Terminal_e_Diagnostico_GE_CT.md": "💻 IT-17: Guia de Comandos Linux, Scripts de Serviço & Diagnóstico Avançado (GE CT)",
    "IT_18_Calibracao_e_Troca_Detector_DAS_Pancake_GE_CT.md": "🔬 IT-18: Substituição, Conexões e Calibração do Detector Pancake DAS - PDAS (GE CT)",
    "IT_19_Substituicao_Alinhamento_Colimador_Motorizado_GE_CT.md": "🎯 IT-19: Substituição, Montagem com Guincho e Alinhamento do Colimador Motorizado (GE CT)",
    "IT_20_Manutencao_Troca_Fluido_Motor_Hidraulico_Tilt_GE_CT.md": "🔧 IT-20: Manutenção, Verificação de Nível, Sangria e Ajuste de Velocidade do Tilt Hidráulico (GE CT)",
    
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
    "IT_RXM_SHIM_003_Instalacao_Montagem_Comissionamento_MobileDaRt_MX8.md": "🚀 IT-03: Roteiro Completo de Instalação, Montagem Mecânica & Comissionamento (Shimadzu MX8)",
    "IT_RXM_SHIM_004_Troca_Baterias_Calibracao_Tensao_MobileDaRt_MX8.md": "🔋 IT-04: Procedimento de Substituição do Banco de Baterias & Calibração de Tensão Mode 7 (Shimadzu MX8)",
    "IT_RXM_SHIM_005_Troca_Monobloco_Tubo_Centracao_Colimador_MX8.md": "🎯 IT-05: Substituição do Monobloco do Tubo de Raio-X & Centração Óptica do Colimador (Shimadzu MX8)",

    # Lotus Raio-X Fixo (HF500M / Família HF)
    "01_Manual_Usuario_Familia_HF_Parte_1.pdf": "📖 Manual do Usuário e Operação - Família HF Raio-X Fixo (Lotus)",
    "IT_RX_LOT_001_Vistoria_Pre_Instalacao_Adequacao_Sala_HF500M.md": "🏗️ IT-01: Vistoria Pré-Instalação, Infraestrutura Elétrica & Adequação da Sala (Lotus HF500M)",
    "IT_RX_LOT_002_Calibracao_kV_mA_Tempo_Manutencao_Familia_HF.md": "🔬 IT-02: Calibração de kV, mA, Tempo e Alinhamento Óptico do Colimador (Família HF)",

    # Neusoft NeuVision 550M
    "01_Manual_Instalacao_Software_NeuVision_550M_Plus.pdf": "💻 Manual de Instalação do Software DR NeuVision 550M Plus (Fábrica Neusoft)",
    "IT_RXD_NEU_001_Instalacao_Software_Configuracao_DR_NeuVision550M.md": "💻 IT-01: Instalação de Software, Configuração Sedecal & Wi-Fi Canon (NeuVision 550M/Plus)",
    "IT_RXD_NEU_002_Calibracao_Flat_Field_Ganho_Offset_Canon_CXDI.md": "🔬 IT-02: Calibração de Campo Plano (Flat Field), Ganho, Offset e Mapeamento de Pixels Defeituosos Canon CXDI"
}

DICIONARIO_SUBGRUPOS = {
    "01_INSTRUCOES_DE_TRABALHO": "📋 INSTRUÇÕES DE TRABALHO (ITs)",
    "02_CALIBRACOES_E_PROCEDIMENTOS_OFICIAIS": "🔬 CALIBRAÇÕES E PROCEDIMENTOS OFICIAIS",
    "03_SOFTWARE_E_UTILITARIOS_LINUX": "💻 SOFTWARE E UTILITÁRIOS LINUX",
    "03_SOFTWARE_E_UTILITARIOS": "💻 SOFTWARE & UTILITÁRIOS",
    "02_PORTAL_INTERATIVO_SERVICE_METHODS": "🌐 PORTAL INTERATIVO SERVICE METHODS",
    "02_MANUAIS_DE_SERVICO_E_INSTALACAO": "📚 MANUAIS DE SERVIÇO & INSTALAÇÃO",
    "02_MANUAIS_DE_SERVICO": "📘 MANUAIS DE SERVIÇO TÉCNICO",
    "02_MANUAIS_OFICIAIS_PDF": "📚 MANUAIS DE FÁBRICA OFICIAIS (PDF)",
    "02_MANUAIS_DE_OPERACAO": "📖 MANUAIS DE OPERAÇÃO",
    "01_MANUAIS_DE_OPERACAO": "📖 MANUAIS DE OPERAÇÃO",
    "01_MANUAIS_DE_SOFTWARE_DR": "📚 MANUAIS DE FÁBRICA OFICIAIS (PDF)",
    "04_ESQUEMAS_ELETRICOS": "⚡ ESQUEMAS ELÉTRICOS & DIAGRAMAS",
    "05_NOTAS_TECNICAS": "📝 NOTAS TÉCNICAS & ALERTAS DE FÁBRICA",
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
    """Retorna um título claro e elegante para a aba do submenu."""
    if raw_subgrupo in DICIONARIO_SUBGRUPOS:
        return DICIONARIO_SUBGRUPOS[raw_subgrupo]
    limpo = re.sub(r'^\d+[\s_-]*', '', raw_subgrupo).replace("_", " ").upper()
    if "INSTRU" in limpo or "IT" in limpo:
        return f"📋 {limpo}"
    elif "MANUAL" in limpo or "OFICIA" in limpo:
        return f"📚 {limpo}"
    elif "CALIBR" in limpo or "PROCED" in limpo:
        return f"🔬 {limpo}"
    elif "SOFT" in limpo or "UTIL" in limpo:
        return f"💻 {limpo}"
    elif "ESQUEMA" in limpo or "ELETR" in limpo:
        return f"⚡ {limpo}"
    elif "VISTORIA" in limpo or "PRE" in limpo:
        return f"🏗️ {limpo}"
    return limpo


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
                if len(partes) >= 5:
                    categoria = f"{partes[0].replace('_', ' ').upper()} ({partes[1].upper()})"
                    modelo = partes[2].replace("_", " ").upper()
                    raw_sub = partes[3]
                    subgrupo = _formatar_subgrupo_amigavel(raw_sub)
                elif len(partes) == 4:
                    if partes[1].upper() in ("GE", "SIEMENS", "PHILIPS", "CANON", "TOSHIBA", "SHIMADZU", "LOTUS", "NEUSOFT", "HOLOGIC", "MINDRAY", "SEDECAL", "VMI", "ZIEHM", "CARESTREAM", "AGFA", "HITACHI", "SAMSUNG", "DRAEGER"):
                        categoria = f"{partes[0].replace('_', ' ').upper()} ({partes[1].upper()})"
                        modelo = partes[2].replace("_", " ").upper()
                        subgrupo = "📚 MANUAIS DE FÁBRICA OFICIAIS (PDF)"
                    else:
                        categoria = partes[0].replace("_", " ").upper()
                        modelo = partes[1].replace("_", " ").upper()
                        subgrupo = _formatar_subgrupo_amigavel(partes[2])
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
    """Exibe o leitor de PDF inline com busca interna de texto, navegação rápida e renderização de alta fidelidade."""
    try:
        import pymupdf
        doc_pdf = pymupdf.open(caminho_pdf)
        total_paginas = len(doc_pdf)

        sess_key_pag = f"pag_{doc_key}"
        if sess_key_pag not in st.session_state:
            st.session_state[sess_key_pag] = 0

        # Barra Superior de Controles e Paginação
        col_win, col_prev, col_info, col_next, col_jump = st.columns([1.5, 0.9, 1.3, 0.9, 1.4])

        with col_win:
            if st.button("🖥️ Abrir no App do Windows", key=f"btn_win_{doc_key}", use_container_width=True):
                _abrir_no_sistema_operacional(caminho_pdf)
                st.toast("Manual aberto no leitor do Windows!", icon="📄")

        pag_atual = st.session_state[sess_key_pag] + 1

        with col_prev:
            if st.button("⬅️ Anterior", key=f"prev_{doc_key}", use_container_width=True, disabled=(st.session_state[sess_key_pag] <= 0)):
                st.session_state[sess_key_pag] -= 1
                st.rerun()

        with col_info:
            st.markdown(
                f"<div style='text-align: center; padding-top: 8px; font-weight: 700; color: #00b4d8; font-size: 0.95rem;'>"
                f"Página {pag_atual} de {total_paginas}"
                f"</div>",
                unsafe_allow_html=True
            )

        with col_next:
            if st.button("Próxima ➡️", key=f"next_{doc_key}", use_container_width=True, disabled=(st.session_state[sess_key_pag] >= total_paginas - 1)):
                st.session_state[sess_key_pag] += 1
                st.rerun()

        with col_jump:
            num_alvo = st.number_input(
                "Ir para pág:",
                min_value=1,
                max_value=total_paginas,
                value=pag_atual,
                key=f"jump_{doc_key}",
                label_visibility="collapsed"
            )
            if num_alvo != pag_atual:
                st.session_state[sess_key_pag] = num_alvo - 1
                st.rerun()

        # BUSCADOR INTERNO NO DOCUMENTO PDF
        st.markdown(
            """
            <div style="background: rgba(0, 180, 216, 0.08); border-left: 3px solid #00b4d8; padding: 6px 12px; margin: 8px 0; border-radius: 4px;">
                <span style="font-weight: 600; color: #caf0f8; font-size: 0.88rem;">🔎 Localizador no Manual: Busque códigos de erro, chaves, calibrações ou palavras-chave</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        termo_busca_pdf = st.text_input(
            "Buscar palavra ou código dentro deste PDF:",
            placeholder="Ex: SW7, cxdiadmin, reset, error, calibração, torque, 192.168...",
            key=f"search_pdf_{doc_key}",
            label_visibility="collapsed"
        )

        if termo_busca_pdf and termo_busca_pdf.strip():
            termo = termo_busca_pdf.strip().lower()
            paginas_encontradas = []
            for i in range(total_paginas):
                page_obj = doc_pdf[i]
                txt = page_obj.get_text("text").lower()
                if termo in txt:
                    # Encontra trecho do snippet
                    pos = txt.find(termo)
                    inicio_snip = max(0, pos - 25)
                    fim_snip = min(len(txt), pos + len(termo) + 40)
                    snippet = txt[inicio_snip:fim_snip].replace("\n", " ").strip()
                    paginas_encontradas.append((i + 1, snippet))

            if paginas_encontradas:
                st.success(f"🎯 O termo **'{termo_busca_pdf}'** foi localizado em **{len(paginas_encontradas)} página(s)**! Clique para ir direto:")
                cols_botoes = st.columns(min(len(paginas_encontradas), 8))
                for idx_btn, (p_num, snip) in enumerate(paginas_encontradas[:8]):
                    with cols_botoes[idx_btn % len(cols_botoes)]:
                        destaque = "primary" if p_num == pag_atual else "secondary"
                        if st.button(f"Pág {p_num}", key=f"btn_p_{p_num}_{doc_key}", type=destaque, use_container_width=True, help=f"Trecho: ...{snip}..."):
                            st.session_state[sess_key_pag] = p_num - 1
                            st.rerun()
                if len(paginas_encontradas) > 8:
                    st.caption(f"Mais páginas com resultados: {', '.join([f'Pág {p[0]}' for p in paginas_encontradas[8:20]])}")
            else:
                st.info(f"Nenhuma ocorrência do termo '{termo_busca_pdf}' neste documento.")

        # Renderização da página selecionada em alta nitidez (DPI 150)
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


def _renderizar_leitor_markdown(caminho_md: str, doc_key: str = "it"):
    """Lê e renderiza um documento Markdown de Instrução de Trabalho formatado com busca rápida."""
    try:
        with open(caminho_md, "r", encoding="utf-8") as f:
            conteudo = f.read()

        col_it_info, col_it_busca = st.columns([1.5, 2.5])
        with col_it_info:
            st.markdown(
                """
                <div style="background: rgba(0, 180, 216, 0.1); border-left: 3px solid #00b4d8; padding: 6px 12px; border-radius: 4px; font-weight: 600; color: #caf0f8; font-size: 0.88rem;">
                    📋 Instrução de Trabalho em Português
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_it_busca:
            busca_it = st.text_input(
                "Buscar termo nesta IT:",
                placeholder="Ex: torque, SW7, cxdiadmin, IP, 192.168, erro...",
                key=f"search_md_{doc_key}",
                label_visibility="collapsed"
            )

        if busca_it and busca_it.strip():
            termo = busca_it.strip()
            ocorrencias = conteudo.lower().count(termo.lower())
            if ocorrencias > 0:
                st.success(f"🎯 O termo **'{termo}'** foi encontrado **{ocorrencias} vez(es)** na instrução abaixo:")
            else:
                st.info(f"O termo '{termo}' não foi encontrado nesta instrução.")

        # Verificação e Exibição do Vídeo Oficial de Treinamento da IT
        nome_arq_md = os.path.basename(caminho_md)
        video_nome = DICIONARIO_VIDEOS_ITS.get(nome_arq_md)
        pasta_doc = os.path.dirname(caminho_md)
        caminho_video = None
        curr = pasta_doc
        while curr and len(curr) > 5:
            possivel_pasta = os.path.join(curr, "Videos_Treinamento_ITs")
            if os.path.exists(possivel_pasta):
                if video_nome and os.path.exists(os.path.join(possivel_pasta, video_nome)):
                    caminho_video = os.path.join(possivel_pasta, video_nome)
                    break
            curr = os.path.dirname(curr)

        if caminho_video and os.path.exists(caminho_video):
            st.markdown(
                """
                <div style="background: linear-gradient(135deg, #101c3d, #1a2c5b); border: 2px solid #7209b7; padding: 14px 18px; border-radius: 10px; margin: 15px 0 10px 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.8rem;">🎬</span>
                            <div>
                                <h4 style="margin: 0; color: #64dfdf; font-weight: 700;">Vídeo Oficial de Treinamento & Apoio em Campo (Full HD 1080p)</h4>
                                <span style="font-size: 0.85rem; color: #cbd5e1;">Passo a passo narrado em português, torques de fábrica, EPIs e procedimento oficial eMed</span>
                            </div>
                        </div>
                        <span style="background: #7209b7; color: white; padding: 4px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 700;">1080p HD</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.video(caminho_video)

        # Resolução e Embutimento Automático de Imagens Locais (assets) em Base64
        pasta_doc = os.path.dirname(caminho_md)
        def _sub_img(match):
            alt_txt = match.group(1)
            img_rel = match.group(2)
            caminho_img = os.path.normpath(os.path.join(pasta_doc, img_rel))
            if os.path.exists(caminho_img):
                ext = os.path.splitext(caminho_img)[1].lower().replace(".", "")
                if ext == "jpg":
                    ext = "jpeg"
                mime = f"image/{ext}"
                try:
                    with open(caminho_img, "rb") as f_img:
                        b64 = base64.b64encode(f_img.read()).decode("utf-8")
                    return f'<div style="text-align: center; margin: 18px 0;"><img src="data:{mime};base64,{b64}" style="max-width: 95%; border: 2px solid #00b4d8; border-radius: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.6);"><br><span style="display: inline-block; margin-top: 6px; font-size: 0.88rem; color: #caf0f8; font-weight: 600; background: rgba(0, 180, 216, 0.15); padding: 2px 10px; border-radius: 4px;">📷 {alt_txt}</span></div>'
                except Exception:
                    pass
            return match.group(0)

        conteudo_render = re.sub(r'!\[(.*?)\]\((.*?)\)', _sub_img, conteudo)

        st.markdown(
            f"""
            <div style="background: #111a36; border: 1px solid #3a506b; padding: 25px; border-radius: 8px; margin-top: 10px;">
            """,
            unsafe_allow_html=True
        )
        st.markdown(conteudo_render, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao ler instrução de trabalho: {e}")



# ==============================================================================
# CATALOGO OFICIAL DE VIDEOS DE TREINAMENTO TECNICO & OPERACIONAL eMED
# ==============================================================================

def _obter_catalogo_videos(base_dir: str) -> list:
    """Retorna a lista completa e estruturada dos 30 vídeos de treinamento e tutoriais da eMED."""
    pasta_its_videos = os.path.join(base_dir, "Videos_Treinamento_ITs")

    catalogo = [
        # --- TREINAMENTOS TECNICOS DE ITS DE CAMPO ---
        {
            "id": "VID_IT_01",
            "codigo_it": "IT_01",
            "arquivo": "Video_IT01_Troca_Tubo_GE_Brivo385.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-01: Troca do Tubo de Raio-X & Pipeline Completo de Calibração",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE Brivo CT385 / BrightSpeed",
            "it_arquivo": "IT_01_Troca_de_Tubo_GE_Brivo385.md",
            "duracao_aprox": "03:45",
            "descricao": "Roteiro prático passo a passo para içamento com guincho, fixação dos parafusos M10 e M12 com torquímetro calibrado, conexão dos receptáculos de alta tensão com óleo dielétrico e calibração completa no Service Desktop (mA, Filamento, POR, BOW, ISO e QA Fantom).",
            "tags": ["tubo", "ge", "brivo", "brightspeed", "calibração", "alinhamento", "loto", "gantry"]
        },
        {
            "id": "VID_IT_02",
            "codigo_it": "IT_02",
            "arquivo": "Video_IT02_Manutencao_Preventiva_BrightSpeed.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-02: Manutenção Preventiva Programada (PM Schedules A, B, C e D)",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE BrightSpeed Series",
            "it_arquivo": "IT_02_Manutencao_Preventiva_GE_BrightSpeed.md",
            "duracao_aprox": "02:15",
            "descricao": "Procedimento completo de revisão preventiva periódica: lubrificação de guias, filtros de ar do duto e gantry, vedações térmicas, verificação das baterias de backup e testes de segurança de rotação.",
            "tags": ["preventiva", "pm", "brightspeed", "limpeza", "filtros", "baterias", "revisão"]
        },
        {
            "id": "VID_IT_03",
            "codigo_it": "IT_03",
            "arquivo": "Video_IT03_Troca_Tubo_BrightSpeed.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-03: Troca de Tubo de Raio-X & Alinhamento Óptico",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE BrightSpeed Lite & Select",
            "it_arquivo": "IT_03_Troca_de_Tubo_GE_BrightSpeed.md",
            "duracao_aprox": "02:10",
            "descricao": "Procedimento de substituição do tubo no BrightSpeed com foco nas conexões de refrigeração de óleo, torque de sustentação mecânica, reset de contadores de exposição e alinhamento óptico do colimador.",
            "tags": ["tubo", "brightspeed", "colimador", "óptico", "refrigeração"]
        },
        {
            "id": "VID_IT_04",
            "codigo_it": "IT_04",
            "arquivo": "Video_IT04_Balanceamento_Gantry_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-04: Balanceamento Estático & Dinâmico do Gantry",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_04_Balanceamento_Gantry_GE.md",
            "duracao_aprox": "01:50",
            "descricao": "Medição de vibração angular com sensor de aceleração, cálculo da matriz de distribuição de massa nos anéis de latão e torqueamento dos parafusos de fixação a 160 N·m.",
            "tags": ["balanceamento", "gantry", "vibração", "torque", "pesos", "latão"]
        },
        {
            "id": "VID_IT_05",
            "codigo_it": "IT_05",
            "arquivo": "Video_IT05_Diagnostico_Ajuste_SlipRing_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-05: Diagnóstico, Limpeza & Ajuste do Slip Ring e HSDCD",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_05_Diagnostico_Ajuste_SlipRing_GE.md",
            "duracao_aprox": "01:45",
            "descricao": "Inspeção do desgaste das escovas de grafite (limite útil 5 mm), calibração do entreferro (air-gap) de 1,41 mm da antena HSDCD e higienização a seco exclusivamente com aspirador com filtro HEPA.",
            "tags": ["slipring", "escovas", "hsdcd", "airgap", "antena", "grafite", "750v"]
        },
        {
            "id": "VID_IT_06",
            "codigo_it": "IT_06",
            "arquivo": "Video_IT06_Alinhamentos_Opticos_Colimador_Detector_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-06: Alinhamentos Ópticos do Colimador & Detector (BOW / CBF)",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_06_Alinhamentos_Opticos_Colimador_Detector_GE.md",
            "duracao_aprox": "01:55",
            "descricao": "Centralização do feixe de raios-X ativo sobre a janela do colimador (Beam on Window - BOW) e alinhamento micrométrico dos filtros anatômicos Bowtie (CBF) e rastreamento sagital (SAG).",
            "tags": ["colimador", "detector", "bow", "cbf", "óptico", "bowtie"]
        },
        {
            "id": "VID_IT_07",
            "codigo_it": "IT_07",
            "arquivo": "Video_IT07_Guia_Ferramenta_Gerador_JEDI_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-07: Guia Prático da Ferramenta de Calibração do Gerador JEDI",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Gerador de Alta Tensão JEDI (GE CT)",
            "it_arquivo": "IT_07_Guia_Ferramenta_Gerador_JEDI_GE.md",
            "duracao_aprox": "01:40",
            "descricao": "Operação passo a passo do utilitário JEDI Generator Tool: conexão serial, calibração de corrente de filamento (mA), curvas de resposta térmica e rotinas de backup e restauração de parâmetros da NVRAM.",
            "tags": ["jedi", "gerador", "alta tensão", "filamento", "ma", "nvram", "backup"]
        },
        {
            "id": "VID_IT_08",
            "codigo_it": "IT_08",
            "arquivo": "Video_IT08_Verificacao_Tanque_HV_e_QA_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-08: Verificação do Tanque HV, Medidores & Teste Final de QA",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_08_Verificacao_Tanque_HV_e_QA_GE.md",
            "duracao_aprox": "01:50",
            "descricao": "Medição dos resistores divisores de feedback de alta tensão, verificação da escala de kV/mA e protocolo final de aceitação no phantom de água (Número de CT da água em 0 ± 4 HU e uniformidade espacial).",
            "tags": ["tanque", "alta tensão", "qa", "phantom", "água", "hu", "ruído"]
        },
        {
            "id": "VID_IT_09",
            "codigo_it": "IT_09",
            "arquivo": "Video_IT09_Alinhamento_Plano_de_Rotacao_POR_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-09: Alinhamento do Plano de Rotação (Plane of Rotation - POR)",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_09_Alinhamento_Plano_de_Rotacao_POR_GE.md",
            "duracao_aprox": "01:45",
            "descricao": "Instalação da ferramenta de alinhamento com relógio comparador para garantir paralelismo estrito do tubo em relação ao plano de rotação dos detectores com deflexão máxima de 0,08 mm.",
            "tags": ["por", "plano de rotação", "geometria", "calços", "relógio comparador"]
        },
        {
            "id": "VID_IT_10",
            "codigo_it": "IT_10",
            "arquivo": "Video_IT10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-10: Alinhamento do Isocentro Mecânico & HOT ISO Ativo",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.md",
            "duracao_aprox": "01:50",
            "descricao": "Ajuste de coincidência entre os projetores de luz laser (sagital, coronal e axial), o centro mecânico do túnel da gantry e o feixe de raios-X em emissão ativa (HOT ISO Alignment).",
            "tags": ["isocentro", "laser", "hot iso", "geometria", "centro mecânico"]
        },
        {
            "id": "VID_IT_11",
            "codigo_it": "IT_11",
            "arquivo": "Video_IT11_Calibracao_Colimador_e_Detailed_Cal_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-11: Calibração de Aberturas do Colimador & Detailed Calibration",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_11_Calibracao_Colimador_Aberturas_e_Detailed_Cal_GE.md",
            "duracao_aprox": "01:45",
            "descricao": "Calibração dos motores de passo do colimador para todas as aberturas nominais de espessura de corte (0,625 mm a 20 mm) e execução da rotina automatizada Detailed Calibration no console.",
            "tags": ["colimador", "aberturas", "detailed cal", "espessura de corte"]
        },
        {
            "id": "VID_IT_12",
            "codigo_it": "IT_12",
            "arquivo": "Video_IT12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-12: Segurança de Rotação do Gantry & Varreduras HHS",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafos GE (Brivo CT385 & BrightSpeed)",
            "it_arquivo": "IT_12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.md",
            "duracao_aprox": "01:50",
            "descricao": "Conferência prévia de desengate da trava mecânica de rotação, verificação das chaves de intertravamento de segurança e execução de sequências de alta potência HHS para estabilização térmica.",
            "tags": ["segurança", "rotação", "hhs", "estresse", "intertravamento", "gantry lock"]
        },
        {
            "id": "VID_IT_13",
            "codigo_it": "IT_13",
            "arquivo": "Video_IT13_Substituicao_Placa_KV_Control_Board_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-13: Substituição da Placa KV Control Board (JEDI)",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE BrightSpeed Series",
            "it_arquivo": "IT_13_Substituicao_Placa_KV_Control_Board_GE_BrightSpeed.md",
            "duracao_aprox": "01:45",
            "descricao": "Procedimento detalhado de desmontagem da tampa frontal da Power Unit, backup dos parâmetros de calibração via JEDI Tool, troca física da placa, download do firmware Flash e restauração.",
            "tags": ["kv control", "jedi", "placa", "power unit", "firmware", "loto"]
        },
        {
            "id": "VID_IT_14",
            "codigo_it": "IT_14",
            "arquivo": "Video_IT14_Substituicao_Controlador_Axial_Drive_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-14: Substituição do Controlador Axial Drive (Titan 2010)",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE BrightSpeed Series",
            "it_arquivo": "IT_14_Substituicao_Controlador_Rotacao_Axial_Drive_GE_BrightSpeed.md",
            "duracao_aprox": "01:45",
            "descricao": "Substituição do inversor de frequência do motor de rotação P/N 5344401, reconexão dos bornes X1 a X12, torque M6 de 8,0 N·m e checagem do status operacional 'o2' no display frontal.",
            "tags": ["axial drive", "titan", "motor", "giro", "inversor", "5344401"]
        },
        {
            "id": "VID_IT_15",
            "codigo_it": "IT_15",
            "arquivo": "Video_IT15_Caracterizacao_Mesa_Paciente_e_Tilt_GE.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-15: Caracterização da Mesa do Paciente & Calibração do Tilt",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Tomógrafo GE BrightSpeed Series",
            "it_arquivo": "IT_15_Caracterizacao_Mesa_Paciente_e_Tilt_Gantry_GE_BrightSpeed.md",
            "duracao_aprox": "01:50",
            "descricao": "Procedimento com blocos de batente para caracterização de contagem longitudinal do berço (18,3 µm/count), pontos de elevação vertical (950 mm e 650 mm) e centralização de tensão do potenciômetro de Tilt (2,50V com chave S4).",
            "tags": ["mesa", "tilt", "potenciômetro", "elevação", "berço", "s4", "caracterização"]
        },
        {
            "id": "VID_IT_RXD_01",
            "codigo_it": "IT_RXD_01",
            "arquivo": "Video_IT_RXD_NEU001_Instalacao_Software_DR_NeuVision550M.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-RXD-01: Instalação Software DR & Rede Wi-Fi Canon",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Raio-X Digital Neusoft NeuVision 550M Plus",
            "it_arquivo": "IT_RXD_NEU_001_Instalacao_Software_Configuracao_DR_NeuVision550M.md",
            "duracao_aprox": "01:50",
            "descricao": "Configuração completa da estação de aquisição DR: credenciais de acesso, comutação da chave de serviço Sedecal SW7, pareamento óptico infravermelho e configuração de rede Wi-Fi 5GHz da Canon.",
            "tags": ["neusoft", "dr", "canon", "sedecal", "wi-fi", "sw7", "infravermelho"]
        },
        {
            "id": "VID_IT_RXM_01",
            "codigo_it": "IT_RXM_01",
            "arquivo": "Video_IT_RXM_SHIM001_Descarga_Capacitores_MobileDaRt_MX8.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-RXM-01: Manutenção & Descarga Segura de Capacitores de 32kW",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Raio-X Móvel Shimadzu MobileDaRt Evolution MX8",
            "it_arquivo": "IT_RXM_SHIM_001_Manutencao_Descarga_Capacitores_MobileDaRt_MX8.md",
            "duracao_aprox": "02:30",
            "descricao": "Protocolo obrigatório de segurança contra choques de alta energia: isolamento das baterias, conexão do plugue de descarga resistiva CN1 e comprovação de tensão residual menor que 5V com voltímetro.",
            "tags": ["shimadzu", "mx8", "capacitores", "descarga", "segurança", "alta tensão"]
        },
        {
            "id": "VID_IT_RXM_02",
            "codigo_it": "IT_RXM_02",
            "arquivo": "Video_IT_RXM_SHIM002_Calibracao_Manopla_Sensor_Braco_MX8.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-RXM-02: Calibração da Manopla com Balança FSR & Sensor do Braço",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Raio-X Móvel Shimadzu MobileDaRt Evolution MX8",
            "it_arquivo": "IT_RXM_SHIM_002_Calibracao_Manopla_Balanca_Sensor_Braco_MX8.md",
            "duracao_aprox": "01:50",
            "descricao": "Calibração dos resistores de sensibilidade à força (FSR) da manopla com dinamômetro de tração para avanço/recuo proporcional e ajuste da barreira óptica PH1 de travamento do braço articulado.",
            "tags": ["shimadzu", "mx8", "manopla", "fsr", "tração", "braço", "dinamômetro"]
        },
        {
            "id": "VID_IT_RXM_03",
            "codigo_it": "IT_RXM_03",
            "arquivo": "Video_IT_RXM_SHIM003_Instalacao_Montagem_MobileDaRt_MX8.mp4",
            "pasta": pasta_its_videos,
            "titulo": "IT-RXM-03: Instalação Mecânica, Montagem & Comissionamento",
            "categoria": "🔬 Treinamentos Técnicos de ITs (Campo)",
            "equipamento": "Raio-X Móvel Shimadzu MobileDaRt Evolution MX8",
            "it_arquivo": "IT_RXM_SHIM_003_Instalacao_Montagem_Comissionamento_MobileDaRt_MX8.md",
            "duracao_aprox": "01:50",
            "descricao": "Roteiro para descarregamento, remoção dos suportes e cintas de transporte, ajuste dos taps do autotransformador P1/P2 para rede 220V e aquecimento prévio de tubo tUbeUP em 13 passos.",
            "tags": ["shimadzu", "mx8", "instalação", "taps", "warm-up", "comissionamento"]
        },

        # --- LOGISTICA, KITS & ALMOXARIFADO ---
        {
            "id": "VID_LOG_01",
            "arquivo": "Video_Tutorial_Fluxo_Kits_Separacao_Entrega_Devolucao.mp4",
            "pasta": base_dir,
            "titulo": "Fluxo de Kits de Ferramentas: Separação, Envio, Entrega e Devolução",
            "categoria": "🧰 Peças, Kits & Almoxarifado",
            "equipamento": "Almoxarifado & Ferramentaria eMED",
            "duracao_aprox": "04:50",
            "descricao": "Protocolo operacional de ponta a ponta: requisição da maleta de calibração pelo técnico, separação com checklist de itens e lacre de segurança, entrega em campo e conferência rigorosa de devolução.",
            "tags": ["kits", "ferramentas", "almoxarifado", "logística", "devolução", "lacre"]
        },
        {
            "id": "VID_LOG_02",
            "arquivo": "Video_Tutorial_Solicitacao_Pecas_Baseada_na_IT.mp4",
            "pasta": base_dir,
            "titulo": "Solicitação de Peças e Insumos Críticos com Base na IT",
            "categoria": "🧰 Peças, Kits & Almoxarifado",
            "equipamento": "Sistema eMED / Gestão de Peças",
            "duracao_aprox": "02:20",
            "descricao": "Como o engenheiro ou técnico de campo localiza os Part Numbers oficiais catalogados nas tabelas das Instruções de Trabalho e abre a requisição com prioridade e previsão de entrega.",
            "tags": ["peças", "requisição", "part number", "estoque", "it", "almoxarifado"]
        },

        # --- SISTEMA EMED & GESTAO DE OS ---
        {
            "id": "VID_SIS_01",
            "arquivo": "Video_Apresentacao_Sistema_Emed_PRO.mp4",
            "pasta": base_dir,
            "titulo": "Apresentação Geral e Arquitetura do Sistema eMED PRO",
            "categoria": "💻 Operação do Sistema eMED & OS",
            "equipamento": "Plataforma eMED",
            "duracao_aprox": "03:25",
            "descricao": "Visão geral das capacidades do ecossistema eMED: triagem inteligente por IA, painel de despacho automático via WhatsApp, relatórios de BI, controle de SLA e rastreabilidade total de manutenções.",
            "tags": ["sistema", "apresentação", "visão geral", "pro", "bi", "sla"]
        },
        {
            "id": "VID_SIS_02",
            "arquivo": "Video_Apresentacao_Sistema_Emed_Real.mp4",
            "pasta": base_dir,
            "titulo": "Demonstração do Sistema eMED em Operação Real",
            "categoria": "💻 Operação do Sistema eMED & OS",
            "equipamento": "Plataforma eMED",
            "duracao_aprox": "03:00",
            "descricao": "Demonstração prática do fluxo de trabalho diário: entrada de chamado crítico de hospital, alocação do técnico mais próximo pela rota, atualização de status de campo e encerramento com laudo.",
            "tags": ["operação real", "atendimento", "demonstração", "chamados", "hospital"]
        },
        {
            "id": "VID_SIS_03",
            "arquivo": "Video_Tutorial_Abertura_OS_Manual.mp4",
            "pasta": base_dir,
            "titulo": "Tutorial: Abertura e Gestão Manual de Ordens de Serviço (OS)",
            "categoria": "💻 Operação do Sistema eMED & OS",
            "equipamento": "Módulo de Ordens de Serviço",
            "duracao_aprox": "02:30",
            "descricao": "Como preencher uma Ordem de Serviço completa: dados do cliente, modalidade, sintomas relatados, prioridade, vínculo com contrato de manutenção e despacho para o corpo técnico.",
            "tags": ["os", "ordem de serviço", "abertura", "preventiva", "corretiva", "despacho"]
        },
        {
            "id": "VID_SIS_04",
            "arquivo": "Video_Tutorial_Cliente_Abertura_EmedOnline.mp4",
            "pasta": base_dir,
            "titulo": "Tutorial do Cliente: Abertura de Chamados via eMED Online",
            "categoria": "💻 Operação do Sistema eMED & OS",
            "equipamento": "Portal do Cliente / eMED Online",
            "duracao_aprox": "02:30",
            "descricao": "Treinamento para os clientes hospitalares: como acessar o portal web dedicado, relatar paradas de equipamentos de imagem, anexar registros fotográficos de códigos de erro e acompanhar o SLA.",
            "tags": ["cliente", "portal", "abertura", "triagem", "online", "chamado"]
        },

        # --- MODULO FISCAL & FATURAMENTO ---
        {
            "id": "VID_FISC_01",
            "arquivo": "Video_Guia_Completo_Cliente_EmedOnline_Com_NotaFiscal.mp4",
            "pasta": base_dir,
            "titulo": "Guia Completo: Portal do Cliente com Módulo Fiscal Integrado",
            "categoria": "🧾 Módulo Fiscal & Portal do Cliente",
            "equipamento": "Portal do Cliente & Fiscal",
            "duracao_aprox": "03:30",
            "descricao": "Fluxo integrado que conecta o cliente ao setor financeiro: aprovação do relatório técnico de visita, geração da fatura e disponibilização da Nota Fiscal de Serviços (NFS-e) para download.",
            "tags": ["fiscal", "faturamento", "cliente", "nfs-e", "ciclo", "financeiro"]
        },
        {
            "id": "VID_FISC_02",
            "arquivo": "Video_Tutorial_Emissao_Nota_Fiscal.mp4",
            "pasta": base_dir,
            "titulo": "Tutorial: Emissão de Notas Fiscais e Faturamento Desacoplado",
            "categoria": "🧾 Módulo Fiscal & Portal do Cliente",
            "equipamento": "Módulo Fiscal eMED",
            "duracao_aprox": "01:45",
            "descricao": "Como o setor financeiro seleciona as ordens de serviço executadas, aplica alíquotas de impostos (ISS, PIS, COFINS, IRRF), transmite a NFS-e e emite boletos de cobrança.",
            "tags": ["nota fiscal", "fiscal", "nfs-e", "faturamento", "impostos", "iss"]
        },

        # --- GESTAO DE FROTAS & KM ---
        {
            "id": "VID_FROT_01",
            "arquivo": "Video_Gestao_Frota_KM_e_Incentivo_ao_Zelo.mp4",
            "pasta": base_dir,
            "titulo": "Gestão de Frota, Apontamento de KM & Programa de Zelo com Veículos",
            "categoria": "🚗 Gestão de Frotas & KM",
            "equipamento": "Gestão de Frotas eMED",
            "duracao_aprox": "03:10",
            "descricao": "Políticas da frota de veículos eMED: rotina de apontamento de quilometragem, check de calibragem e nível de óleo, condução segura e funcionamento do Programa de Incentivo ao Zelo.",
            "tags": ["frota", "km", "veículos", "zelo", "combustível", "premiação"]
        },
        {
            "id": "VID_FROT_02",
            "arquivo": "Video_Rotina_Semanal_Frota_KM_eMed.mp4",
            "pasta": base_dir,
            "titulo": "Rotina Semanal de Controle e Auditoria de KM da Frota",
            "categoria": "🚗 Gestão de Frotas & KM",
            "equipamento": "Gestão de Frotas eMED",
            "duracao_aprox": "02:05",
            "descricao": "Metodologia de fechamento semanal dos trajetos dos técnicos, conciliação de cartões de combustível com rotas hospitalares e identificação de desvios operacionais.",
            "tags": ["rotina semanal", "auditoria", "km", "frota", "controle", "combustível"]
        },
        {
            "id": "VID_FROT_03",
            "arquivo": "Video_Tutorial_Gestao_Frota_KM.mp4",
            "pasta": base_dir,
            "titulo": "Tutorial Rápido: Apontamento de Quilometragem no Aplicativo",
            "categoria": "🚗 Gestão de Frotas & KM",
            "equipamento": "Módulo de Quilometragem",
            "duracao_aprox": "01:50",
            "descricao": "Tutorial direto para o técnico no smartphone: como tirar a foto do painel do carro, digitar o hodômetro de saída e chegada e submeter a rota em menos de 1 minuto.",
            "tags": ["hodômetro", "km", "apontamento", "app", "rápido", "celular"]
        }
    ]

    for v in catalogo:
        caminho_completo = os.path.join(v["pasta"], v["arquivo"])
        v["caminho"] = caminho_completo
        if os.path.exists(caminho_completo):
            v["tamanho_mb"] = os.path.getsize(caminho_completo) / (1024 * 1024)
            v["existe"] = True
        else:
            v["tamanho_mb"] = 0.0
            v["existe"] = False

    return catalogo


def _render_videoteca_tecnica(ctx: AppContext):
    """Renderiza a Central Oficial de Vídeos de Treinamento e Tutoriais do Sistema eMED."""
    catalogo_videos = _obter_catalogo_videos(ctx.base_dir)

    st.markdown("### 🎬 Videoteca de Treinamento Técnico & Operacional eMED")
    st.markdown(
        "Acervo multimídia com **30 produções audiovisuais narradas com inteligência artificial neural e passo a passo visual**, "
        "focadas em instruções de trabalho de campo (ITs), rotinas de calibração, operação de ferramentas e protocolos do sistema."
    )

    # Painel de Métricas Rápidas
    total_videos = len(catalogo_videos)
    qtd_its = sum(1 for v in catalogo_videos if "ITs" in v["categoria"])
    qtd_pecas = sum(1 for v in catalogo_videos if "Peças" in v["categoria"] or "Kits" in v["categoria"])
    qtd_sistema = sum(1 for v in catalogo_videos if "Sistema" in v["categoria"])
    qtd_frota_fiscal = sum(1 for v in catalogo_videos if "Frota" in v["categoria"] or "Fiscal" in v["categoria"])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🎥 Total de Vídeos", f"{total_videos} Aulas")
    m2.metric("🔬 ITs de Campo", f"{qtd_its} Procedimentos")
    m3.metric("🧰 Peças & Kits", f"{qtd_pecas} Tutoriais")
    m4.metric("💻 Sistema eMED", f"{qtd_sistema} Guias")
    m5.metric("🚗 Frota & Fiscal", f"{qtd_frota_fiscal} Protocolos")

    st.markdown("<hr style='border: 0.5px solid #1e293b; margin: 15px 0;'>", unsafe_allow_html=True)

    # Filtros e Pesquisa
    c_cat, c_busca = st.columns([1.6, 2.4])
    with c_cat:
        categorias_lista = [
            "TODAS AS CATEGORIAS",
            "🔬 Treinamentos Técnicos de ITs (Campo)",
            "🧰 Peças, Kits & Almoxarifado",
            "💻 Operação do Sistema eMED & OS",
            "🧾 Módulo Fiscal & Portal do Cliente",
            "🚗 Gestão de Frotas & KM"
        ]
        cat_escolhida = st.selectbox("🎯 Filtrar por Categoria", categorias_lista, key="sb_cat_video")

    with c_busca:
        termo_v = st.text_input("🔍 Pesquisar na Videoteca...", placeholder="Ex: tubo, slipring, alinhamento, mx8, brivo, km, nota fiscal, kits...", key="txt_busca_video").strip().lower()

    # Filtragem dos Vídeos
    videos_filtrados = []
    for v in catalogo_videos:
        if cat_escolhida != "TODAS AS CATEGORIAS" and v["categoria"] != cat_escolhida:
            continue
        if termo_v:
            texto_busca = f"{v['titulo']} {v['descricao']} {v.get('equipamento', '')} {' '.join(v.get('tags', []))}".lower()
            if termo_v not in texto_busca:
                continue
        videos_filtrados.append(v)

    # Inicialização do Vídeo em Destaque
    if "video_destaque_id" not in st.session_state:
        st.session_state.video_destaque_id = "VID_IT_01"

    # Vídeo em Destaque / Player Principal ("Cinema Mode")
    vid_destaque = next((v for v in catalogo_videos if v["id"] == st.session_state.video_destaque_id), None)
    if not vid_destaque and videos_filtrados:
        vid_destaque = videos_filtrados[0]

    if vid_destaque and vid_destaque.get("existe"):
        with st.container():
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #091322, #132238); border: 2px solid #00b4d8; border-radius: 10px; padding: 18px 22px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                    <span style="background: #00b4d8; color: #020c1b; font-weight: 700; font-size: 0.8rem; padding: 3px 12px; border-radius: 12px; text-transform: uppercase;">
                        {vid_destaque['categoria']}
                    </span>
                    <span style="color: #94a3b8; font-size: 0.85rem;">
                        ⏱️ Duração: <b>{vid_destaque.get('duracao_aprox', '02:30')}</b> &nbsp;|&nbsp; 💾 Arquivo: <b>{vid_destaque['tamanho_mb']:.2f} MB</b>
                    </span>
                </div>
                <h3 style="color: #f8fafc; margin: 10px 0 6px 0; font-weight: 700;">{vid_destaque['titulo']}</h3>
                <p style="color: #cbd5e1; font-size: 0.95rem; margin-bottom: 12px; line-height: 1.5;">{vid_destaque['descricao']}</p>
                <div style="color: #38bdf8; font-size: 0.88rem; font-weight: 600; margin-bottom: 12px;">
                    🔬 Equipamento / Escopo: <span style="color: #e2e8f0; font-weight: 400;">{vid_destaque.get('equipamento', 'Geral')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_vid_play, col_vid_actions = st.columns([3.2, 1.2])
            with col_vid_play:
                st.video(vid_destaque["caminho"])

            with col_vid_actions:
                st.markdown("##### Opções de Estudo")
                try:
                    with open(vid_destaque["caminho"], "rb") as f_vdown:
                        bytes_v = f_vdown.read()
                    st.download_button(
                        label="📥 Baixar MP4 Offline",
                        data=bytes_v,
                        file_name=vid_destaque["arquivo"],
                        mime="video/mp4",
                        key="btn_dl_destaque",
                        use_container_width=True,
                        help="Baixe este vídeo para assistir no celular durante viagens de atendimento sem sinal 4G."
                    )
                except Exception as e:
                    st.error(f"Erro ao carregar download: {e}")

                if vid_destaque.get("it_arquivo"):
                    st.info(f"📄 **IT Relacionada:**\n`{vid_destaque['it_arquivo']}`\n\nConsulte o roteiro completo com todas as tolerâncias na aba **Acervo de Manuais & POPs**.")

    st.markdown("<hr style='border: 0.5px solid #1e293b; margin: 25px 0 15px 0;'>", unsafe_allow_html=True)
    st.markdown(f"#### 📺 Catálogo Geral de Vídeos ({len(videos_filtrados)} encontrados)")

    if not videos_filtrados:
        st.info("Nenhum vídeo encontrado para os filtros selecionados.")
        return

    # Renderiza os cards de vídeos em lista limpa
    for idx_v, vid in enumerate(videos_filtrados):
        with st.container():
            c_icon, c_info, c_btns = st.columns([0.4, 3.2, 1.4])

            with c_icon:
                st.markdown("### 🎬")

            with c_info:
                st.markdown(f"##### **{vid['titulo']}**")
                st.markdown(
                    f"<span style='background: #1e293b; color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 600;'>{vid['categoria']}</span> &nbsp;|&nbsp; "
                    f"🏥 <span style='color: #cbd5e1; font-size: 0.85rem;'>{vid.get('equipamento', 'Geral')}</span> &nbsp;|&nbsp; "
                    f"⏱️ `{vid.get('duracao_aprox', '02:00')}` &nbsp;|&nbsp; "
                    f"💾 `{vid['tamanho_mb']:.2f} MB`",
                    unsafe_allow_html=True
                )
                st.markdown(f"<p style='color: #94a3b8; font-size: 0.9rem; margin-top: 6px; line-height: 1.4;'>{vid['descricao']}</p>", unsafe_allow_html=True)

            with c_btns:
                # Botão para reproduzir no topo (Cinema Mode)
                if st.button("🎬 Assistir no Topo", key=f"btn_destaque_{vid['id']}", use_container_width=True):
                    st.session_state.video_destaque_id = vid["id"]
                    st.rerun()

                # Botão de visualização inline
                chave_inline = f"inline_vid_{vid['id']}"
                if chave_inline not in st.session_state:
                    st.session_state[chave_inline] = False

                lbl_inline = "Fechar Vídeo" if st.session_state[chave_inline] else "▶️ Reproduzir Aqui"
                if st.button(lbl_inline, key=f"btn_inline_{vid['id']}", use_container_width=True):
                    st.session_state[chave_inline] = not st.session_state[chave_inline]
                    st.rerun()

                # Botão de Download
                try:
                    with open(vid["caminho"], "rb") as f_dl:
                        dados_v = f_dl.read()
                    st.download_button(
                        label="📥 Baixar MP4",
                        data=dados_v,
                        file_name=vid["arquivo"],
                        mime="video/mp4",
                        key=f"btn_dl_card_{vid['id']}",
                        use_container_width=True
                    )
                except Exception:
                    pass

            if st.session_state.get(chave_inline, False):
                st.markdown(f"<div style='margin-top: 10px; border-top: 1px dashed #334155; padding-top: 12px;'>", unsafe_allow_html=True)
                st.video(vid["caminho"])
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<hr style='border: 0.5px solid #1e293b; margin: 12px 0;'>", unsafe_allow_html=True)


def _render_central_upload(pasta_manuais: str):
    """Renderiza a Central de Ingestão e Organização Automática de Novos Manuais e Procedimentos."""
    st.markdown("### 📤 Central de Ingestão e Organização Automática de Novos Manuais")
    st.markdown(
        "Utilize este assistente para cadastrar e categorizar novos manuais de serviço, catálogos e "
        "procedimentos na arquitetura padrão do Sistema eMED. Os arquivos serão organizados "
        "automaticamente na estrutura de pastas físicas e indexados em tempo real na biblioteca."
    )

    with st.form("form_upload_manual", clear_on_submit=True):
        arquivos_up = st.file_uploader(
            "Selecione um ou mais manuais/documentos (PDF, Markdown, DOCX ou ZIP)",
            type=["pdf", "md", "doc", "docx", "zip"],
            accept_multiple_files=True
        )

        c_u1, c_u2 = st.columns(2)
        with c_u1:
            tipo_eqp = st.selectbox(
                "Tipo de Equipamento (Modalidade)",
                [
                    "TOMOGRAFO",
                    "RAIO-X",
                    "RAIO-X_DIGITAL",
                    "RAIO-X_MOVEL",
                    "ARCO_CIRURGICO",
                    "MAMOGRAFO",
                    "ULTRASSOM",
                    "RESSONANCIA_MAGNETICA",
                    "HEMODINAMICA",
                    "OUTRO"
                ]
            )
            if tipo_eqp == "OUTRO":
                tipo_eqp_custom = st.text_input("Especifique a Nova Modalidade", placeholder="Ex: DENSITOMETRO")
                tipo_final = tipo_eqp_custom.strip().upper().replace(" ", "_") if tipo_eqp_custom else "OUTRO"
            else:
                tipo_final = tipo_eqp

        with c_u2:
            fab_opcoes = [
                "GE",
                "SIEMENS",
                "PHILIPS",
                "SHIMADZU",
                "LOTUS",
                "NEUSOFT",
                "CANON",
                "TOSHIBA",
                "HOLOGIC",
                "MINDRAY",
                "SEDECAL",
                "VMI",
                "ZIEHM",
                "CARESTREAM",
                "AGFA",
                "HITACHI",
                "SAMSUNG",
                "DRAEGER",
                "OUTRO"
            ]
            fab_sel = st.selectbox("Fabricante", fab_opcoes)
            if fab_sel == "OUTRO":
                fab_custom = st.text_input("Especifique o Fabricante", placeholder="Ex: KONICA_MINOLTA")
                fab_final = fab_custom.strip().upper().replace(" ", "_") if fab_custom else "GERAL"
            else:
                fab_final = fab_sel

        c_m1, c_m2 = st.columns(2)
        with c_m1:
            modelo_nome = st.text_input("Nome do Modelo / Família", placeholder="Ex: OPTIMA_CT540, MAGNETOM_ESSENZA, CIOS_SELECT...")
        with c_m2:
            sub_sel = st.selectbox(
                "Subgrupo / Destino",
                [
                    "01_INSTRUCOES_DE_TRABALHO",
                    "02_MANUAIS_OFICIAIS_PDF",
                    "02_MANUAIS_DE_SERVICO_E_INSTALACAO",
                    "02_MANUAIS_DE_OPERACAO",
                    "03_SOFTWARE_E_UTILITARIOS",
                    "04_ESQUEMAS_ELETRICOS",
                    "05_NOTAS_TECNICAS",
                    "OUTRO"
                ]
            )
            if sub_sel == "OUTRO":
                sub_custom = st.text_input("Nome da Pasta do Subgrupo", placeholder="Ex: 06_CALIBRACOES_ESPECIAIS")
                sub_final = sub_custom.strip().upper().replace(" ", "_") if sub_custom else "02_MANUAIS_OFICIAIS_PDF"
            else:
                sub_final = sub_sel

        submeter = st.form_submit_button("📥 Processar e Organizar na Biblioteca", type="primary")

        if submeter and arquivos_up:
            mod_limpo = modelo_nome.strip().upper().replace(" ", "_") if modelo_nome else "GERAL"
            pasta_destino = os.path.join(pasta_manuais, tipo_final, fab_final, mod_limpo, sub_final)
            os.makedirs(pasta_destino, exist_ok=True)

            salvos = []
            for arq in arquivos_up:
                caminho_salvo = os.path.join(pasta_destino, arq.name)
                with open(caminho_salvo, "wb") as f_out:
                    f_out.write(arq.getbuffer())
                salvos.append(arq.name)

            st.success(f"✅ Sucesso! {len(salvos)} documento(s) salvo(s) e indexado(s) em `{tipo_final}/{fab_final}/{mod_limpo}/{sub_final}`: {', '.join(salvos)}")
            st.rerun()


def _render_acervo_manuais(ctx: AppContext, pasta_manuais: str, catalogo: list):
    """Renderiza a navegação, filtros e catálogo de manuais e ITs."""
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

    col_mod, col_busca, col_deep = st.columns([1, 1.8, 1.2])
    with col_mod:
        if modelos_disponiveis:
            mod_selecionado = st.selectbox("🔬 Modelo do Equipamento", ["TODOS OS MODELOS"] + modelos_disponiveis)
        else:
            mod_selecionado = "TODOS OS MODELOS"

    with col_busca:
        termo_busca = st.text_input("🔍 Buscador Geral da Biblioteca Técnica...", placeholder="Ex: SW7, cxdiadmin, Tubo, Balanceamento, Slip Ring, MX8, 550M...")

    with col_deep:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        busca_profunda = st.checkbox("🔎 Conteúdo Completo", value=False, help="Pesquisa profunda também dentro do texto dos PDFs e das Instruções de Trabalho")

    # Filtra pelos seletores e busca
    docs_filtrados = []
    ocorrencias_busca = {}
    termo_limpo = termo_busca.strip().lower() if termo_busca else ""

    for d in docs_cat:
        if mod_selecionado != "TODOS OS MODELOS" and d["modelo"] != mod_selecionado:
            continue

        match_direto = False
        if not termo_limpo:
            match_direto = True
        else:
            # 1. Busca por Metadados (Nome, Título, Categoria, Subgrupo)
            if (termo_limpo in d["titulo_amigavel"].lower() or
                termo_limpo in d["nome_arquivo"].lower() or
                termo_limpo in d["subgrupo"].lower() or
                termo_limpo in d["categoria"].lower()):
                match_direto = True

            # 2. Busca Profunda no Conteúdo (Texto do PDF e Markdown)
            if not match_direto and busca_profunda:
                try:
                    if d["tipo"] == "MARKDOWN":
                        with open(d["caminho"], "r", encoding="utf-8", errors="ignore") as f_txt:
                            conteudo_txt = f_txt.read().lower()
                            cnt = conteudo_txt.count(termo_limpo)
                            if cnt > 0:
                                match_direto = True
                                ocorrencias_busca[d["caminho"]] = cnt
                    elif d["tipo"] == "PDF":
                        import pymupdf
                        doc_temp = pymupdf.open(d["caminho"])
                        cnt = 0
                        for p in doc_temp:
                            if termo_limpo in p.get_text("text").lower():
                                cnt += 1
                        doc_temp.close()
                        if cnt > 0:
                            match_direto = True
                            ocorrencias_busca[d["caminho"]] = cnt
                except Exception:
                    pass

        if match_direto:
            docs_filtrados.append(d)

    # Caminho do frameset do Portal Service Methods
    caminho_portal_bs = os.path.join(pasta_manuais, "TOMOGRAFO", "GE", "BRIGHTSPEED_LITE", "02_PORTAL_INTERATIVO_SERVICE_METHODS", "frameset.htm")
    tem_portal_bs = os.path.exists(caminho_portal_bs)

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
                    _render_lista_cards(docs_do_grupo, ocorrencias_busca)
    elif len(lista_abas) == 1:
        if lista_abas[0] == "🌐 PORTAL INTERATIVO SERVICE METHODS":
            _render_card_portal_service_methods(caminho_portal_bs)
        else:
            _render_lista_cards(docs_filtrados, ocorrencias_busca)
    else:
        st.info("Nenhum manual encontrado para os filtros selecionados.")


def render_manuais_tecnicos(ctx: AppContext):
    """Renderiza a View de Consulta de Manuais Técnicos e Procedimentos com navegação em sub-abas limpas."""
    st.markdown("## 📚 Biblioteca Técnica & Videoteca de Treinamento eMED")
    st.markdown(
        "Acesso integrado a Manuais de Fábrica, Instruções de Trabalho (ITs), "
        "Procedimentos de Calibração e **Videoteca Oficial com 30 Vídeos Narrados de Treinamento**."
    )

    pasta_manuais = _obter_caminho_manuais(ctx)
    catalogo = _escanear_arvore_manuais(pasta_manuais)

    tab_manuais, tab_videoteca, tab_upload = st.tabs([
        "📚 Acervo de Manuais & POPs",
        "🎬 Videoteca & Treinamentos de Campo (30 Vídeos)",
        "📤 Central de Ingestão & Upload"
    ])

    with tab_manuais:
        _render_acervo_manuais(ctx, pasta_manuais, catalogo)

    with tab_videoteca:
        _render_videoteca_tecnica(ctx)

    with tab_upload:
        _render_central_upload(pasta_manuais)

def _garantir_servidor_portal_ge(caminho_frameset: str):
    """Garante a execução de um micro-servidor HTTP local para permitir a navegação por frames sem bloqueio de segurança."""
    global _SERVER_THREAD
    pasta_portal = os.path.dirname(os.path.abspath(caminho_frameset))
    if _SERVER_THREAD is not None and _SERVER_THREAD.is_alive():
        return
    import http.server
    import socketserver
    import threading

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=pasta_portal, **kwargs)

        def log_message(self, format, *args):
            pass

    def run_server():
        try:
            # Allow address reuse to prevent bind errors on hot-reload
            socketserver.TCPServer.allow_reuse_address = True
            with socketserver.TCPServer(("127.0.0.1", _SERVER_PORT), QuietHandler) as httpd:
                httpd.serve_forever()
        except Exception:
            pass

    _SERVER_THREAD = threading.Thread(target=run_server, daemon=True)
    _SERVER_THREAD.start()


def _render_card_portal_service_methods(caminho_frameset: str):
    """Renderiza o card oficial e o portal interativo embarcado GE Service Methods."""
    _garantir_servidor_portal_ge(caminho_frameset)
    url_portal = f"http://127.0.0.1:{_SERVER_PORT}/frameset.htm"

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0d1b2a, #1b263b); border: 2px solid #00b4d8; padding: 20px; border-radius: 12px; margin: 15px 0;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <span style="font-size: 2.8rem;">🌐</span>
                <div>
                    <h3 style="margin: 0; color: #caf0f8; font-weight: 700;">Portal de Manuais de Serviço GE BrightSpeed Lite & Select (100% Funcional)</h3>
                    <p style="margin: 6px 0 0 0; color: #e0e1dd; font-size: 0.95rem; line-height: 1.5;">
                        Documentação eletrônica completa de fábrica com mais de <b>4.300 tópicos</b>, esquemáticos elétricos dinâmicos, 
                        árvore de navegação à esquerda, peças sobressalentes e sistema de busca indexada.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_btn1, col_btn2 = st.columns([1.6, 2.4])
    with col_btn1:
        if st.button("🚀 Abrir em Nova Aba do Navegador (Tela Cheia)", type="primary", use_container_width=True):
            _abrir_no_sistema_operacional(url_portal)
            st.toast("Portal GE aberto no navegador!", icon="🌐")

    with col_btn2:
        st.markdown(
            f"""
            <a href="{url_portal}" target="_blank" style="display: inline-block; padding: 9px 18px; background: #0077b6; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 0.9rem;">
                🔗 Clique Aqui para Acesso Direto (Link Web)
            </a>
            """,
            unsafe_allow_html=True
        )

    # Visualização Integrada do Portal Interativo Diretamente no Sistema
    with st.expander("🖥️ Visualizar Portal Interativo Embutido Aqui no Sistema", expanded=True):
        st.components.v1.iframe(url_portal, height=850, scrolling=True)


def _render_lista_cards(docs: list, ocorrencias_busca: dict = None):
    """Renderiza a lista de documentos em cards informativos, elegantes e padronizados com suporte a busca de conteúdo."""
    if not docs:
        st.info("Nenhum documento encontrado nesta seção.")
        return

    if ocorrencias_busca is None:
        ocorrencias_busca = {}

    for idx, doc in enumerate(docs):
        with st.container():
            col_icon, col_det, col_acoes = st.columns([0.35, 3.25, 1.4])

            with col_icon:
                st.markdown("### 📋" if doc["tipo"] == "MARKDOWN" else "### 📑")

            with col_det:
                st.markdown(f"#### **{doc['titulo_amigavel']}**")
                tipo_badge = "📖 INSTRUÇÃO DE TRABALHO eMED (IT)" if doc["tipo"] == "MARKDOWN" else "📑 MANUAL OFICIAL PDF"
                badge_busca = ""
                if doc["caminho"] in ocorrencias_busca:
                    badge_busca = f" &nbsp;|&nbsp; <span style='background: #e76f51; color: white; padding: 2px 7px; border-radius: 4px; font-size: 0.82rem; font-weight: 700;'>🎯 {ocorrencias_busca[doc['caminho']]} ocorrência(s) no conteúdo</span>"

                st.markdown(
                    f"`{tipo_badge}` &nbsp;|&nbsp; "
                    f"💾 `{doc['tamanho_mb']:.2f} MB` &nbsp;|&nbsp; "
                    f"🕒 Atualizado em: `{doc['data_mod']}`"
                    f"{badge_busca}",
                    unsafe_allow_html=True
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
                elif "kv_control" in doc["nome_arquivo"].lower() or "it_13" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos da KV Control Board (GE BrightSpeed)"):
                        st.markdown(r"""
                        * **Fixação Física:** 12 parafusos na tampa frontal da Power Unit + 7 porcas sextavadas da placa + 2 cabos flat ribbon.
                        * **Backup Prévio Obrigatório:** JEDI Generator Tool -> *Save Runtime Parameters* (antes de desligar o sistema).
                        * **Desenergização LOTO:** Desligar PDU + 3 chaves do Service Switch Panel (Axial Drive, HVDC, 120VAC).
                        * **Firmware:** Executar *Flash Download* após religar para gravar firmware na NVRAM da nova placa.
                        * **Restauração de Parâmetros:** *Restore Runtime Parameters* (ou *Initialize Database* se sem backup).
                        * **Calibrações Mandatórias:** Rotation Safety Check, Meter Verification, Filament Calibration, HHS Scans e QA Fantom H2O ($0 \pm 4\text{ HU}$).
                        """)
                elif "axial_drive" in doc["nome_arquivo"].lower() or "it_14" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos do Axial Drive / Rotação (GE BrightSpeed)"):
                        st.markdown(r"""
                        * **Part Number Oficial GE:** `5344401` (Controlador Titan 2010).
                        * **Torque Parafusos M6 (Suporte Inferior):** **$8,0\text{ N}\cdot\text{m}$ ($70\text{ lb}\cdot\text{in}$)**.
                        * **Conexões de Potência:** X4 (Alimentação da régua), X3 (Resistor de Frenagem), X2 (Motor Axial).
                        * **Conexões de Sinal/KIM:** X10 (Resolver/Feedback), X1 (Comando KIM), X7/X8 (Comunicação), X12 (Comunicação 3ª via).
                        * **Confirmação no Display:** O display digital DEVE exibir **`o2`** ao ligar a chave 120VAC.
                        * **Aviso de Queimadura:** O resistor de frenagem dinâmica atinge temperaturas altíssimas; aguarde esfriar antes de tocar.
                        """)
                elif "caracterizacao_mesa" in doc["nome_arquivo"].lower() or "it_15" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos de Caracterização da Mesa e Tilt (GE BrightSpeed)"):
                        st.markdown(r"""
                        * **Mesa Longitudinal (IN / OUT):** Instalar blocos frontal e traseiro no trilho direito -> Placa GTCB `MODE_SEL` em SERVICE -> LED `CRDL` -> ABS count $\approx 18,3\ \mu\text{m/count}$.
                        * **Mesa Elevação (UP / DOWN):** Ponto 1 = $950,0 \pm 0,5\text{ mm}$ | Ponto 2 = $650,0 \pm 0,5\text{ mm}$ | Limite mecânico inferior | LED `POT_ADJ UP` verde no topo.
                        * **Tilt do Gantry (Potenciômetro):** Tensão de centro a $0^\circ$ = $2,50 \pm 0,20\text{V DC}$ (ajuste mecânico na polia de 32 dentes).
                        * **Calibração de Tilt no Console:** *Mechanical Calibration* -> Ativar chave **`S4` em ON** no Gantry para passo fino (Obrigatório retornar a **OFF** ao final!).
                        """)
                elif "igbt" in doc["nome_arquivo"].lower() or "it_16" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos dos Módulos IGBT / Inversor JEDI (GE BrightSpeed)"):
                        st.markdown(r"""
                        * **Topologia:** Inversor hipo-ressonante (2 IGBTs em Half-Bridge para Lite / 4 IGBTs em paralelo para Select/16).
                        * **Barramento DC:** Tensão de até **$750\text{V DC}$** (LOTO obrigatório; comprovar $V_{DC} < 5\text{V}$ com multímetro antes de tocar).
                        * **Torque Base IGBT / Dissipador:** Etapa 1 a **$1,5\text{ N}\cdot\text{m}$** -> Etapa 2 cruzada a **$3,0$ a $3,5\text{ N}\cdot\text{m}$**.
                        * **Torque Bornes de Barramento (M5/M6):** **$2,5$ a $3,0\text{ N}\cdot\text{m}$**.
                        * **Pasta Térmica:** Película ultrafina uniforme ($50-100\ \mu\text{m}$) aplicada com espátula plástica.
                        * **Teste Obrigatório Pós-Troca:** *No Load kV Test* em rampa escalonada ($60\text{ kV} \rightarrow 140\text{ kV}$) antes de liberar filamento.
                        """)
                elif "linux" in doc["nome_arquivo"].lower() or "it_17" in doc["nome_arquivo"].lower():
                    with st.expander("💻 Comandos de Terminal & Diagnóstico Linux GE CT"):
                        st.markdown(r"""
                        * **Diagnóstico de Hardware:** `checkHW` (status geral), `showRev` (versões de firmware), `ping_nodes` (comunicação CAN/Ethernet gantry).
                        * **Controle de Processos do Scanner:** `stopall` (derruba todos os daemons de aquisição), `starthost` (reinicia stack completa do host).
                        * **Logs & Monitoramento:** `tail -f /usr/g/service/log/syslog` | `viewErrorLog` | `dmesg | grep -i err`.
                        * **Reset Rápido de Nós:** `reset_gantry_nodes` (reinicializa nós do Slipring, Colimador, Gerador JEDI sem reiniciar o Linux).
                        """)
                elif "pancake" in doc["nome_arquivo"].lower() or "detector" in doc["nome_arquivo"].lower() or "it_18" in doc["nome_arquivo"].lower():
                    with st.expander("🔬 Parâmetros Críticos do Pancake DAS & Detector (GE BrightSpeed / Brivo)"):
                        st.markdown(r"""
                        * **Part Numbers:** DCB `5317077` | Módulos Conversores ADB Kit `2344539` | Fonte PDAS `5488054`.
                        * **Cuidado Antiestático:** Uso de Field ESD Kit + **Ferramenta de Extração Flex** obrigatória (NUNCA puxar flex manualmente).
                        * **Torques:** Parafusos M4 ADB = **$2,3\text{ N}\cdot\text{m}$** | M8 Fonte = **$19,2\text{ N}\cdot\text{m}$** | M10 Filtro = **$38,4\text{ N}\cdot\text{m}$**.
                        * **Estabilização Térmica Obrigatória:** Mínimo de **1 hora (60 min)** de gantry ligada antes de rodar `DAS Tools` ou calibrações. Placas frias reprovam em *Offset Drift* / *Pop Noise*.
                        * **Critério de Ruído:** Desvio padrão de ruído dos canais $\sigma_{\text{ruído}} < 1,20\ \text{LSB}$ no teste de ruído estático.
                        """)
                elif "colimador" in doc["nome_arquivo"].lower() or "it_19" in doc["nome_arquivo"].lower():
                    with st.expander("🎯 Parâmetros Críticos do Colimador Motorizado (GE BrightSpeed / Brivo)"):
                        st.markdown(r"""
                        * **Part Number Colimador:** `5140001-6` | CCB Control Board `2189441` | Peso $\approx 25\text{ kg}$ (Guincho obrigatório).
                        * **Torque Parafusos Estruturais (6x M14):** Pré-carga **$40\text{ N}\cdot\text{m}$** -> Aperto final em cruz **$110\text{ N}\cdot\text{m} \pm 5\text{ N}\cdot\text{m}$** com Loctite 242.
                        * **Conexões CCB:** J2 (Came e microchaves), J3 (Motor do filtro Bowtie), J11 (Alimentação e barramento de dados).
                        * **Alinhamentos Ópticos Obrigatórios:** POR (Plano de rotação $\le 0,08\text{ mm}$), BOW (Feixe na janela, assimetria $\le 1,5\%$), CBF/SAG.
                        * **Calibração de Software:** `Collimator Calibration` -> `Detailed Calibration` -> `Fast Calibration`.
                        """)
                elif "fluido" in doc["nome_arquivo"].lower() or "it_20" in doc["nome_arquivo"].lower():
                    with st.expander("🔧 Parâmetros Críticos do Tilt Hidráulico (GE BrightSpeed / Brivo)"):
                        st.markdown(r"""
                        * **Posição Obrigatória de Checagem/Enchimento:** Gantry totalmente inclinada para trás (**$-30^\circ$ / Full Backward**). Se aberta em pé ou para frente, haverá derramamento de óleo pressurizado!
                        * **Fluido Oficial:** Óleo mineral GE P/N `2227239` (vermelho).
                        * **Nível na Vareta (Dipstick):** Chave Allen de 5 mm limpa com álcool -> **$15\text{ mm} \pm 2\text{ mm}$** na haste.
                        * **Vedação:** Exatamente 2 voltas completas de fita Teflon nova na rosca do bujão M6.
                        * **Velocidade Nominal:** **$1,0^\circ/\text{s} \pm 0,05^\circ/\text{s}$** ($25\text{ s}$ para $25^\circ$). Ajustar válvulas de avanço (Forward) e recuo (Backward).
                        """)
                elif "lot_001" in doc["nome_arquivo"].lower() or "adequacao_sala" in doc["nome_arquivo"].lower():
                    with st.expander("🏗️ Parâmetros Elétricos & Sala de Exames (Lotus HF500M)"):
                        st.markdown(r"""
                        * **Potência & Alimentação:** Rede trifásica $380\text{V} \pm 10\%$, Transformador dedicado $\ge 60\text{ kVA}$.
                        * **Proteção & Cabos:** Disjuntor termomagnético Curva C de **$100\text{A}$** | Condutores de alimentação $\ge 25\text{ mm}^2$ (cobre).
                        * **Aterramento:** Resistência máxima $\le 5,0\ \Omega$ (preferencialmente $< 2,0\ \Omega$, livre de ruído elétrico).
                        * **Blindagem Radiológica:** Baritagem ou chumbo $\ge 2,0\text{ mm Pb}$ nas paredes e porta radiológica com visor plumbífero.
                        """)
                elif "lot_002" in doc["nome_arquivo"].lower() or "familia_hf" in doc["nome_arquivo"].lower():
                    with st.expander("🔬 Tolerâncias de Calibração & Manutenção (Lotus Família HF)"):
                        st.markdown(r"""
                        * **Tolerância de Tensão ($kV_p$):** Erro máximo $\le \pm 5\%$ do valor nominal programado no console.
                        * **Reprodutibilidade do Tempo:** Coeficiente de variação $CV \le 0,05$ entre 10 disparos consecutivos.
                        * **Alinhamento do Campo Óptico x Radiação:** Desvio total de bordas $\le 2\%$ da distância foco-filme (DFF $100\text{ cm} \rightarrow \le 20\text{ mm}$).
                        * **Linearidade da Corrente ($mA$ / $mAs$):** Coeficiente de linearidade $CL \le 0,10$.
                        """)
                elif "neu_002" in doc["nome_arquivo"].lower() or "flat_field" in doc["nome_arquivo"].lower():
                    with st.expander("🔬 Calibração de Campo Plano e Defeitos (Canon CXDI / NeuVision 550M)"):
                        st.markdown(r"""
                        * **Condições Iniciais:** Detector ligado há no mínimo 30 minutos em temperatura ambiente estabilizada ($20-25^\circ\text{C}$).
                        * **Offset / Dark Current:** Calibração sem radiação (medição de corrente de fuga e ruído de fundo dos sensores).
                        * **Flat Field Gain Calibration:** 5 disparos homogêneos a $70\text{ kV}$, $200\text{ mA}$, $100\text{ ms}$ com filtro de cobre de $1,5\text{ mm Cu}$ no colimador.
                        * **Defect Pixel Map:** Mapeamento de pixels mortos/quentes e interpolação bi-linear (nenhum cluster $> 3\times 3$ no centro da imagem).
                        """)
                elif "shim_004" in doc["nome_arquivo"].lower() or "baterias" in doc["nome_arquivo"].lower():
                    with st.expander("🔋 Parâmetros Críticos do Banco de Baterias (Shimadzu MobileDaRt MX8)"):
                        st.markdown(r"""
                        * **Banco de Baterias:** 20 baterias seladas chumbo-ácido de alta corrente ($12\text{V}$ cada em série, nominal $240\text{V DC}$).
                        * **Torque dos Terminais:** **$4,0\text{ a }4,5\text{ N}\cdot\text{m}$** (aperto uniforme com chave dinamométrica isolada).
                        * **Calibração de Tensão Mode 7.6:** Entrar no modo de serviço do MX8, medir tensão real com multímetro calibrado e inserir valor exato no painel.
                        * **Registro do Novo Banco Mode 7.11:** Resetar contador de vida útil e inserir código da nova data de fabricação das baterias.
                        """)
                elif "shim_005" in doc["nome_arquivo"].lower() or "monobloco" in doc["nome_arquivo"].lower():
                    with st.expander("🎯 Parâmetros Críticos do Tubo & Colimador (Shimadzu MobileDaRt MX8)"):
                        st.markdown(r"""
                        * **Porca de Fixação do Braço Telescópico:** FU Lock Nut AW04 (torque de pré-carga e ajuste de folga axial).
                        * **Equalização de Balanço da Mola:** Aferir esforço vertical com balança de mola: força de elevação/descida deve ser $\le 15\text{ N}$ em todo o curso.
                        * **Alinhamento Óptico do Colimador:** Erro de coincidência entre campo luminoso e campo de raios-X $\le 1,0\text{ mm}$ a $1\text{ m}$ DFF.
                        * **Iluminância do Campo de Luz:** Mínimo de **$160\text{ lux}$** a $1\text{ metro}$ de distância focal.
                        """)
                elif "neuvision" in doc["nome_arquivo"].lower() or "neu_001" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos e Senhas (Neusoft NeuVision 550M Plus)"):
                        st.markdown(r"""
                        * **Logon Windows (SO):** `cxdiadmin` / Senha: `nmsadmin`
                        * **Canon Service Tool:** `cxdiadmin` / Senha: `Canononac`
                        * **Chave de Serviço Gerador Sedecal:** **SW7** (ON: modo de serviço/alarme sonoro contínuo; OFF: operação clínica normal).
                        * **Postos de Trabalho (WS):** WS1 = Bucky 1, Tube 1, RAD | WS2 = direct, Tube 1, RAD.
                        * **Rede AP Wi-Fi Canon:** IP Local `192.168.100.10` | Alvo `192.168.100.200` | RX IF `192.168.100.96` | ESSID `NMSAP` | Wi-Fi 5 GHz `149ch - 5745MHz`.
                        * **Link Infravermelho Detector:** Distância $\le 30\text{ cm}$, ângulo $< 10^\circ$ (LEDs Azul e Verde acesos).
                        """)
                elif "mobiledart" in doc["nome_arquivo"].lower() or "shim_" in doc["nome_arquivo"].lower():
                    with st.expander("⚡ Parâmetros Críticos de Instalação e Manutenção (Shimadzu MobileDaRt MX8)"):
                        st.markdown(r"""
                        * **Ajuste de Tensão (Obrigatório!):** P1 = `A0` e P2 = `A220` para tomadas $220\text{V} \pm 10\%$ (Padrão de fábrica é 100V!).
                        * **Travas de Transporte:** Remover suportes metálicos do braço, parafusos de parada do colimador e 2 cintas plásticas PP (Guardar suportes com o cliente!).
                        * **Aquecimento do Tubo (Warm-Up):** Modo `tUbeUP` no visor (13 passos de $60\text{ kV}$ até $133\text{ kV}$ com colimador fechado).
                        * **Descarga de Capacitores (32kW):** Medir nos bornes do banco até que $V_{DC} < 5\text{V}$ (conector CN1 no DISCHARGE da placa MUX CAPACITOR).
                        * **Calibração da Manopla (FSR) & Braço:** Sensor óptico PH1 no catcher da base e balança de tração calibrada para tração proporcional.
                        * **Carga Inicial:** Mínimo de 12 horas contínuas antes do primeiro uso clínico.
                        """)

            with col_acoes:
                # Botão de Download
                try:
                    with open(doc["caminho"], "rb") as f_down:
                        dados_bytes = f_down.read()
                    st.download_button(
                        label="📥 Baixar Documento (.pdf / .md)",
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

                # Botão de Vídeo da IT
                nome_arq_it = doc["nome_arquivo"]
                video_it_nome = DICIONARIO_VIDEOS_ITS.get(nome_arq_it)
                caminho_vid_it = None
                if video_it_nome:
                    base_p = r"c:\Users\vitor\OneDrive\Desktop\Sistema Emed"
                    p1 = os.path.join(base_p, "Videos_Treinamento_ITs", video_it_nome)
                    p2 = os.path.join(base_p, video_it_nome)
                    if os.path.exists(p1):
                        caminho_vid_it = p1
                    elif os.path.exists(p2):
                        caminho_vid_it = p2

                if caminho_vid_it:
                    chave_vid = f"view_vid_{doc['rel_path']}_{idx}"
                    if chave_vid not in st.session_state:
                        st.session_state[chave_vid] = False
                    lbl_vid = "Ocultar Vídeo" if st.session_state[chave_vid] else "🎬 Vídeo da IT"
                    if st.button(lbl_vid, key=f"btn_vid_{doc['rel_path']}_{idx}", use_container_width=True):
                        st.session_state[chave_vid] = not st.session_state[chave_vid]
                        st.rerun()

            # Área de exibição inline de Vídeo da IT
            if caminho_vid_it and st.session_state.get(chave_vid, False):
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #091322, #16243b); border-left: 4px solid #00b4d8; padding: 12px 18px; border-radius: 6px; margin: 10px 0;">
                    <span style="color: #38bdf8; font-weight: 700; font-size: 0.95rem;">🎬 Vídeo-Treinamento Narrado:</span>
                    <span style="color: #f1f5f9; font-size: 0.95rem; margin-left: 8px;">{doc['titulo_amigavel']}</span>
                </div>
                """, unsafe_allow_html=True)
                st.video(caminho_vid_it)

            # Área de exibição inline do Documento
            if st.session_state.get(chave_view, False):
                if doc["tipo"] == "MARKDOWN":
                    _renderizar_leitor_markdown(doc["caminho"], f"{doc['rel_path']}_{idx}")
                else:
                    _renderizar_leitor_pdf(doc["caminho"], f"{doc['rel_path']}_{idx}")

            st.markdown("<hr style='border: 0.5px solid #233554; margin: 12px 0;'>", unsafe_allow_html=True)
