# -*- coding: utf-8 -*-
"""
Módulo de Checklists Técnicos Especializados por Equipamento e Fabricante
Sistema eMED Eletromedicina - Engenharia Clínica Hospitalar

Diferencia com precisão:
- RAIO-X FIXO (Mesa flutuante, estativa de parede, bucky mural, trilhos)
- RAIO-X TRANSPORTÁVEL / MÓVEL (Baterias de tração, rodízios, freios dead-man, braço articulado, cabo de disparo retrátil)
- TOMÓGRAFO (Slip ring, brush block, rolamento gantry, DAS, Mylar, filtros, phanton ROI)
- MAMÓGRAFO (Compressor, pás, freios de rotação, palhetas Mo/Rh, pedais de descompressão)
- DENSITOMETRIA ÓSSEA (Shutter, esteiras porta cabos, QA diário bloco padrão, eixos X/Y)
- CR / DIGITALIZADOR (Trilhos, leitora laser, cassetes, espelhos ópticos, nobreak)
- ARCO CIRÚRGICO (Braço em C, intensificador/FPD, íris/colimador circular, pedal duplo)
- ULTRASSONOGRAFIA (Lentes acústicas, transdutores, TGC, encoders, trackball, filtros)
"""

CHECKLISTS_ESPECIALIZADOS = {
    "TOMÓGRAFO": {
        "titulo": "Checklist Preventivo Oficial — Tomografia Computadorizada",
        "aplicavel": ["TOMÓGRAFO", "TOMOGRAFO", "TC", "CT"],
        "itens": [
            {"item": "Verificação do funcionamento das luzes, lasers de alinhamento e displays do Gantry", "grupo": "Gantry & Iluminação"},
            {"item": "Verificação dos sensores de posicionamento e segurança do paciente", "grupo": "Segurança do Paciente"},
            {"item": "Verificação mecânica e eletrônica do funcionamento do TILT (angulação do Gantry)", "grupo": "Gantry & Mecânica"},
            {"item": "Verificação do funcionamento dos botões de emergência (Gantry, Mesa e Console)", "grupo": "Segurança & Parada Emergencial"},
            {"item": "Verificação da parte rotacional, acoplamento e sistema de acionamento", "grupo": "Gantry Rotacional"},
            {"item": "Limpeza das carenagens e verificação rigorosa do SLIP RING e BRUSH BLOCK", "grupo": "Gantry Rotacional"},
            {"item": "Limpeza e desobstrução dos filtros de ar e ventiladores do gerador de alta tensão", "grupo": "Gerador de Alta Tensão"},
            {"item": "Limpeza dos filtros, grelhas de entrada de ar e ventiladores do Gantry", "grupo": "Refrigeração do Gantry"},
            {"item": "Verificação e aplicação de graxa técnica no rolamento principal do Gantry", "grupo": "Gantry Rotacional"},
            {"item": "Limpeza dos filtros de ar e ventiladores do sistema de aquisição de dados (DAS)", "grupo": "DAS & Detectores"},
            {"item": "Limpeza do detector na janela de aquisição (MYLAR) com material apropriado", "grupo": "DAS & Detectores"},
            {"item": "Limpeza e verificação do radiador, filtros, fluído térmico e ventiladores do tubo de raios-X", "grupo": "Tubo de Raios-X"},
            {"item": "Limpeza, alinhamento e lubrificação da mecânica e trilhos da mesa de exames", "grupo": "Mesa de Paciente"},
            {"item": "Verificação de tensão e integridade do cabo de aço do potenciômetro da mesa", "grupo": "Mesa de Paciente"},
            {"item": "Verificação e leitura de logs de erros do sistema operacional e hardware", "grupo": "Software & Diagnóstico"},
            {"item": "Verificação do número de pacientes cadastrados e total de rotações/disparos do tubo", "grupo": "Contadores & Tubo"},
            {"item": "Inspeção física, escovas e limpeza dos motores de avanço e rotação", "grupo": "Motores de Tração"},
            {"item": "Limpeza interna, ventoinhas e verificação dos computadores (Console e Recon)", "grupo": "Console & Processamento"},
            {"item": "Verificação e teste de comunicação com o SCAN BOX", "grupo": "Interface & Scan Box"},
            {"item": "Realização do teste de calibração com phanton de água e análise de ruído com ROI", "grupo": "Controle de Qualidade"},
            {"item": "Realização de limpeza interna geral, externa e testes funcionais de exposição", "grupo": "Finalização & Higienização"}
        ]
    },

    "RAIOS-X FIXO": {
        "titulo": "Checklist Preventivo Oficial — Raio-X Fixo de Alta Resolução",
        "aplicavel": ["RAIOS-X FIXO", "RAIOS X FIXO", "RAIO-X FIXO", "RX FIXO", "RAIOS-X ANALOGICO", "RAIOS-X DIGITAL", "SALA DE RAIO-X"],
        "itens": [
            {"item": "Verificação da rede elétrica trifásica/bifásica (+- 10%) e aterramento de segurança (PE)", "grupo": "Alimentação & Rede"},
            {"item": "Verificação da integridade dos cabos elétricos de força, neutro e chicotes de comando", "grupo": "Alimentação & Rede"},
            {"item": "Verificação dos cabos blindados de alta tensão (HT cables) e conectores do anodo/catodo", "grupo": "Alta Tensão"},
            {"item": "Verificação da integridade, fixação e tensão dos cabos de aço e contrapesos da estativa", "grupo": "Estativa & Mecânica"},
            {"item": "Verificação do funcionamento do painel de controle principal e console do gerador", "grupo": "Console & Controle"},
            {"item": "Verificação do funcionamento dos freios mecânicos e eletromagnéticos da estativa e mesa", "grupo": "Freios & Travas"},
            {"item": "Verificação do funcionamento do colimador manual/motorizado e temporizador da lâmpada", "grupo": "Colimação & Radiação"},
            {"item": "Verificação mecânica de trilhos de piso e teto (alinhamento, lubrificação e travas de fim de curso)", "grupo": "Trilhos & Guias"},
            {"item": "Verificação do balanceamento mecânico e alinhamento perpendicular da estativa de parede", "grupo": "Estativa Bucky Mural"},
            {"item": "Verificação de acionamento da lâmpada de sinalização de radiação externa à sala (luz vermelha)", "grupo": "Radioproteção"},
            {"item": "Verificação da centralização exata da luz de colimação com o feixe de radiação e cruz central", "grupo": "Colimação & Radiação"},
            {"item": "Verificação do funcionamento do bucky mural e bucky mesa (oscilação e disparo)", "grupo": "Bucky & Grades"},
            {"item": "Verificação da integridade física e alinhamento da grade anti-difusora", "grupo": "Bucky & Grades"},
            {"item": "Verificação da integridade mecânica, travas e tampo de acrílico flutuante da mesa", "grupo": "Mesa de Exames"},
            {"item": "Verificação do funcionamento e travas das bandejas de receptores/chassis", "grupo": "Mesa & Bucky"},
            {"item": "Verificação de avarias na pintura, soldas e carenagens protetoras", "grupo": "Estrutura & Carenagens"},
            {"item": "Backup completo das configurações do gerador, curvas de kV/mAs e parâmetros de fábrica", "grupo": "Backup & Software"},
            {"item": "Verificação de espaço em disco, logs do sistema e comunicação DICOM/Worklist", "grupo": "Console & Imagem"},
            {"item": "Limpeza do console de operação, monitor de laudo, teclado e mouse", "grupo": "Console & Imagem"},
            {"item": "Teste de funcionamento e autonomia do nobreak e estabilizador de linha", "grupo": "Alimentação & Rede"}
        ]
    },

    "RAIOS-X MÓVEL / TRANSPORTÁVEL": {
        "titulo": "Checklist Preventivo Oficial — Raio-X Móvel / Transportável (Leito & UTI)",
        "aplicavel": ["RAIOS-X MOVEL", "RAIOS-X MÓVEL", "RAIOS-X TRANSPORTAVEL", "RAIOS-X TRANSPORTÁVEL", "RX MOVEL", "RX MÓVEL", "RX TRANSP", "AQUILA", "PEGASO", "MOBILEDART", "TITANIUM"],
        "itens": [
            {"item": "Verificação do banco de baterias de tração, conexões e indicador de nível de carga no display", "grupo": "Baterias & Tração"},
            {"item": "Verificação do acionamento e suavidade da tração motorizada (avanço e recuo)", "grupo": "Baterias & Tração"},
            {"item": "Verificação do sistema de freio de estacionamento mecânico (Dead-Man) e rodízios direcionais", "grupo": "Freios & Rodízios"},
            {"item": "Verificação da trava mecânica de transporte do braço telescópico e travamento da coluna", "grupo": "Segurança de Transporte"},
            {"item": "Verificação do balanceamento do braço articulado e rotação do cabeçote (0º a 180º)", "grupo": "Braço & Articulação"},
            {"item": "Verificação das esteiras protetoras e cabos de alta tensão retráteis", "grupo": "Alta Tensão"},
            {"item": "Verificação do cabo espiral retrátil do disparador à distância (extensão de segurança > 2m)", "grupo": "Radioproteção & Disparo"},
            {"item": "Verificação do colimador manual integrado com trena métrica retrátil para conferência do DFO", "grupo": "Colimação & Foco"},
            {"item": "Verificação da lâmpada de campo luminoso e desligamento automático do temporizador", "grupo": "Colimação & Foco"},
            {"item": "Verificação da coincidência do campo de luz e radiação em 100 cm (DFO padrão)", "grupo": "Colimação & Foco"},
            {"item": "Verificação da integridade do compartimento de guarda e transporte de detectores FPD/chassis", "grupo": "Acessórios"},
            {"item": "Verificação do cabo de força AC, enrolador automático e plugue de carga de rede (110V/220V)", "grupo": "Alimentação & Carga"},
            {"item": "Verificação do painel digital sensível ao toque, membranas e seleção de parâmetros kV/mAs", "grupo": "Painel de Comando"},
            {"item": "Verificação dos botões de parada de emergência e sensores anticolisão do para-choque", "grupo": "Segurança Operacional"},
            {"item": "Verificação de acionamento do alarme sonoro e aviso visual luminoso de emissão de raios-X", "grupo": "Radioproteção & Disparo"},
            {"item": "Verificação de trincas, folgas mecânicas e integridade das carenagens de proteção", "grupo": "Estrutura & Carenagens"},
            {"item": "Limpeza técnica e assepsia das superfícies para conformidade hospitalar de UTI/Isolamento", "grupo": "Assepsia Hospitalar"},
            {"item": "Teste de emissão de raios-X com medição de parâmetros de exposição de tórax no leito", "grupo": "Testes Funcionais"}
        ]
    },

    "MAMÓGRAFO": {
        "titulo": "Checklist Preventivo Oficial — Mamógrafo de Alta Resolução",
        "aplicavel": ["MAMÓGRAFO", "MAMOGRAFO", "MM", "MAMOGRAFIA", "SENOGRAPHE", "LILYUM", "DELICATA", "DIAMOND", "AURORA"],
        "itens": [
            {"item": "Verificação das ligações elétricas, terminais de aterramento e cabos de sinal entre placas", "grupo": "Eletrônica & Alimentação"},
            {"item": "Verificação do transformador de alta tensão e tanques geradores", "grupo": "Alta Tensão"},
            {"item": "Verificação dos cabos blindados de alta tensão e conectores isolados", "grupo": "Alta Tensão"},
            {"item": "Verificação de acionamento da lâmpada indicadora de emissão de radiação", "grupo": "Radioproteção"},
            {"item": "Verificação de funcionamento do console de comando e displays digitais", "grupo": "Console & Displays"},
            {"item": "Verificação de suavidade e freios de rotação do braço em C (movimentos CC e MLO)", "grupo": "Braço em C & Rotação"},
            {"item": "Verificação do funcionamento do colimador e comutação das palhetas de filtro (Molibdênio/Ródio)", "grupo": "Colimação & Filtros"},
            {"item": "Verificação da integridade mecânica das pás de compressão (18x24 e 24x30) sem trincas", "grupo": "Compressão"},
            {"item": "Aferição da força de compressão motorizada (limite de 15 a 20 daN) e manual com dinamômetro", "grupo": "Compressão"},
            {"item": "Verificação do funcionamento e deslizamento do bucky mamográfico e grade anti-difusora", "grupo": "Bucky & Imagem"},
            {"item": "Verificação dos freios eletromagnéticos de travamento vertical e angular", "grupo": "Freios & Movimentos"},
            {"item": "Verificação do funcionamento dos pedais duplos de compressão e liberação emergencial", "grupo": "Pedais & Segurança"},
            {"item": "Verificação dos botões de liberação rápida de compressão e parada de emergência", "grupo": "Segurança do Paciente"},
            {"item": "Verificação de avarias na pintura, acabamentos e protetores de face do paciente", "grupo": "Carenagens & Conforto"},
            {"item": "Realização de limpeza interna técnica, externa e lubrificação das guias de compressão", "grupo": "Finalização & Higienização"}
        ]
    },

    "DENSITOMETRIA ÓSSEA": {
        "titulo": "Checklist Preventivo Oficial — Densitometria Óssea",
        "aplicavel": ["DENSITOMETRIA", "DENSITOMETRO", "DO", "LUNAR", "PRODIGY", "DPX", "PRIMUS"],
        "itens": [
            {"item": "Verificação dos cabos de alta tensão e conectores do tubo de raios-X", "grupo": "Alta Tensão"},
            {"item": "Verificação dos cabos de sinal, esteira porta-cabos e cabeamento do detector", "grupo": "Sinal & Comunicação"},
            {"item": "Verificação e medição das tensões de saída das fontes de alimentação DC", "grupo": "Fontes de Alimentação"},
            {"item": "Verificação e teste do obturador (shutter) de radiação e colimador", "grupo": "Feixe & Radiação"},
            {"item": "Verificação do funcionamento dos botões de parada de emergência", "grupo": "Segurança"},
            {"item": "Verificação da integridade física e nivelamento do tampo acolchoado da mesa", "grupo": "Mesa de Exame"},
            {"item": "Verificação da integridade das esteiras flexíveis e chicotes de movimentação", "grupo": "Mecânica & Guias"},
            {"item": "Realização de limpeza interna, externa e lubrificação dos eixos de varredura X e Y", "grupo": "Mecânica & Guias"},
            {"item": "Verificação de avarias na pintura, alinhamento do laser e estrutura da máquina", "grupo": "Estrutura & Carenagens"},
            {"item": "Realização do teste de controle de qualidade diário (QA com bloco padrão de calibração)", "grupo": "Controle de Qualidade"}
        ]
    },

    "CR / DIGITALIZADOR": {
        "titulo": "Checklist Preventivo Oficial — Sistema de Radiografia Computadorizada (CR)",
        "aplicavel": ["CR", "DIGITALIZADOR", "REGIUS", "AERODR", "DRY", "COMPUTE RADIOGRAPHIC"],
        "itens": [
            {"item": "Verificação mecânica e lubrificação dos trilhos e roletes de transporte do cassete", "grupo": "Mecânica & Transporte"},
            {"item": "Verificação do movimento de precisão da unidade de leitura óptica a laser", "grupo": "Leitora Óptica"},
            {"item": "Limpeza interna e aspiração de poeira e resíduos do interior do equipamento", "grupo": "Higienização Interna"},
            {"item": "Limpeza técnica dos espelhos ópticos, guias de luz e lentes da fotomultiplicadora", "grupo": "Óptica & Fotomultiplicadora"},
            {"item": "Inspeção física, limpeza e eliminação de artefatos nas placas de fósforo e cassetes", "grupo": "Placas de Fósforo"},
            {"item": "Backup completo das configurações do software de aquisição e curvas de sensibilidade", "grupo": "Software & Calibração"},
            {"item": "Verificação de espaço em disco, banco de dados DICOM e integridade de rede PACS", "grupo": "TI & Conectividade"},
            {"item": "Limpeza e higienização do console de operação, monitor touchscreen e leitor de código de barras", "grupo": "Console & Periféricos"},
            {"item": "Teste de autonomia de carga e transferência de rede do nobreak dedicado", "grupo": "Alimentação & Nobreak"}
        ]
    },

    "ARCO CIRÚRGICO": {
        "titulo": "Checklist Preventivo Oficial — Arco Cirúrgico Fluoroscópico",
        "aplicavel": ["ARCO CIRÚRGICO", "ARCO CIRURGICO", "C-ARM", "OEC", "BRIVO", "EVERVIEW", "CIOS", "PULSERA"],
        "itens": [
            {"item": "Verificação dos movimentos orbitais, balanceamento e rotação livre do braço em C", "grupo": "Mecânica do Braço"},
            {"item": "Verificação de travamento mecânico e freios de retenção do posicionamento cirúrgico", "grupo": "Mecânica do Braço"},
            {"item": "Verificação e teste de resolução do intensificador de imagem ou detector plano FPD", "grupo": "Imagem & Intensificador"},
            {"item": "Verificação do colimador circular / íris e palhetas de sombreamento de corte", "grupo": "Colimação & Radiação"},
            {"item": "Verificação da integridade do cabo de interligação flexível de alta tensão entre as unidades", "grupo": "Cabeamento & Força"},
            {"item": "Verificação do pedal multifunção de disparo (fluoroscopia contínua, pulsada e radiografia)", "grupo": "Comandos & Pedais"},
            {"item": "Verificação da articulação, calibração e brilho dos monitores médicos de centro cirúrgico", "grupo": "Monitores & Carrinho"},
            {"item": "Verificação dos botões de emergência e alarme sonoro regulamentar de 5 minutos", "grupo": "Segurança & Radioproteção"},
            {"item": "Verificação dos rodízios direcionais, freio de transporte e protetores de cabo de piso", "grupo": "Rodízios & Transporte"},
            {"item": "Teste funcional de exposição em baixa dose e calibração de imagem fluoroscópica", "grupo": "Testes Funcionais"}
        ]
    },

    "ULTRASSONOGRAFIA": {
        "titulo": "Checklist Preventivo Oficial — Ultrassonografia Diagnóstica",
        "aplicavel": ["ULTRASSONOGRAFIA", "ULTRASSOM", "USG", "ECOCARDIOGRAMA"],
        "itens": [
            {"item": "Inspeção visual minuciosa da carcaça, lentes acústicas e cabos dos transdutores", "grupo": "Transdutores"},
            {"item": "Verificação de pinos, travas de travamento mecânico e conectores dos transdutores", "grupo": "Transdutores"},
            {"item": "Verificação de funcionamento do painel alfanumérico, encoders de ganho (TGC) e trackball", "grupo": "Painel de Controle"},
            {"item": "Verificação da articulação e mecanismo pneumático de elevação/rotação do monitor", "grupo": "Monitor & Braço"},
            {"item": "Limpeza e desobstrução dos filtros de ar e ventiladores de refrigeração da fonte de alimentação", "grupo": "Refrigeração & Fonte"},
            {"item": "Verificação dos freios das rodas e sistema de trava direcional do equipamento", "grupo": "Mecânica & Rodízios"},
            {"item": "Teste com fantoma de ultrassom para avaliação de sensibilidade, resolução axial e lateral", "grupo": "Controle de Qualidade"},
            {"item": "Backup das configurações do equipamento, presets médicos e biblioteca de medidas", "grupo": "Backup & Software"},
            {"item": "Limpeza externa, higienização dos suportes de transdutores e compartimento do gel", "grupo": "Finalização & Higienização"}
        ]
    }
}

def identificar_categoria_checklist(nome_equipamento: str, categoria_sugerida: str = "") -> str:
    """Identifica com alta precisão qual o checklist correto para a máquina informada."""
    nome_norm = f"{nome_equipamento} {categoria_sugerida}".upper()
    
    # 1. Tomógrafo
    if any(k in nome_norm for k in ["TOMÓGRAFO", "TOMOGRAFO", "BRIGHTSPEED", "BRIVO 385", "BRIVO 325", "REVOLUTION", "ALEXION", "ASTEION", "NEUVIZ", "SOMATOM", "AQUILION"]):
        return "TOMÓGRAFO"
        
    # 2. Raio-X Móvel / Transportável (REGRA ESSENCIAL: Prioridade sobre fixo!)
    if any(k in nome_norm for k in ["MÓVEL", "MOVEL", "TRANSPORTÁVEL", "TRANSPORTAVEL", "TRANSP", "AQUILA", "AQUILLA", "PEGASO", "MOBILEDART", "TITANIUM", "LEITO", "PORTATIL", "PORTÁTIL", "POLYMOBIL", "MX8", "NEUVISION 550M"]):
        return "RAIOS-X MÓVEL / TRANSPORTÁVEL"
        
    # 3. Raio-X Fixo
    if any(k in nome_norm for k in ["RAIOS-X", "RAIOS X", "RAIO-X", "RAIO X", "RX", "ALTUS", "COMPACTO PLUS", "COMPACT PLUS", "XR 6000", "MULTIX", "INTECAL", "RAYTEC", "TD 500", "ROENTAX"]):
        return "RAIOS-X FIXO"
        
    # 4. Mamógrafo
    if any(k in nome_norm for k in ["MAMÓGRAFO", "MAMOGRAFO", "MAMOGRAFIA", "MM", "SENOGRAPHE", "LILYUM", "DELICATA", "DIAMOND", "AURORA", "AFFINITY", "M-IV", "PERFORMA", "MAMMOMAT"]):
        return "MAMÓGRAFO"
        
    # 5. Densitometria Óssea
    if any(k in nome_norm for k in ["DENSITOMETRIA", "DENSITOMETRO", "DENSITÔMETRO", "DO", "LUNAR", "PRODIGY", "DPX", "PRIMUS", "OSTEOSYS"]):
        return "DENSITOMETRIA ÓSSEA"
        
    # 6. CR / Digitalizador
    if any(k in nome_norm for k in ["CR", "DIGITALIZADOR", "REGIUS", "AERODR", "AERO DR", "DRY", "DRYPRO", "COMPUTE RADIOGRAPHIC", "VIVIX"]):
        return "CR / DIGITALIZADOR"
        
    # 7. Arco Cirúrgico
    if any(k in nome_norm for k in ["ARCO CIRÚRGICO", "ARCO CIRURGICO", "C-ARM", "OEC", "BRIVO 850", "EVERVIEW", "CIOS", "PULSERA", "ZENITION"]):
        return "ARCO CIRÚRGICO"
        
    # 8. Ultrassonografia
    if any(k in nome_norm for k in ["ULTRASSONOGRAFIA", "ULTRASSOM", "USG", "ECOCARDIOGRAMA", "VOLUSON", "LOGIQ"]):
        return "ULTRASSONOGRAFIA"
        
    return "RAIOS-X FIXO"

def obter_checklist_oficial(nome_equipamento: str, categoria: str = "") -> dict:
    """Retorna o checklist completo e estruturado para o equipamento indicado."""
    cat = identificar_categoria_checklist(nome_equipamento, categoria)
    return CHECKLISTS_ESPECIALIZADOS.get(cat, CHECKLISTS_ESPECIALIZADOS["RAIOS-X FIXO"])
