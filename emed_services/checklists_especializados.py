# -*- coding: utf-8 -*-
"""
Módulo de Checklists Técnicos Especializados por Equipamento e Fabricante
Sistema eMED Eletromedicina - Engenharia Clínica Hospitalar

Consolidado a partir dos Procedimentos Oficiais e Histórico de OSs (Effort / Globalthings v3.0, v4.0, v6.0)
e Planilha de Engenharia Clínica CHECKLIST.xlsx da EMED.

Modalidades Atendidas:
- TOMÓGRAFO (Gantry, Slip Ring, Brush Block, Inverter JEDI, DAS, Mylar, Rolamento, Mesa, Console, Scan Box, PDU, Phantom ROI)
- RAIOS-X FIXO (Comando, Fontes DC, Transformador HT, Estativa Porta Tubo, Colimador, Bucky Mural, Mesa de Exame, Grade Antidifusora)
- RAIOS-X MÓVEL / TRANSPORTÁVEL (Baterias de Tração, Rodízios, Freios Dead-Man, Braço Telescópico, Disparador Retrátil, Trena DFO)
- MAMÓGRAFO (Comando, Estativa C, Compressores 18x24 e 24x30, Dinamômetro 15-20 daN, Buckys, Filtros Mo/Rh, Pedais, Emergência)
- DENSITOMETRIA ÓSSEA (Cabos HT, Sinal, Fontes DC, Shutter/Colimador Feixe Lápis/Leque, Eixos X/Y, QA com Bloco Padrão)
- CR / DIGITALIZADOR (Trilhos/Roletes, Leitor Óptico Laser, Fotomultiplicadora PMT, Cassetes/Placas de Fósforo, PACS/DICOM, Nobreak)
- ARCO CIRÚRGICO (Braço C Orbital, Intensificador/FPD, Íris/Colimador, Pedal Duplo Fluoroscopia, Monitores Médicos, Alarme 5 Min)
- ULTRASSONOGRAFIA (Lentes Acústicas, Transdutores, TGC, Encoders, Trackball, Refrigeração, Phantom Tecido Simulador)
- FÍSICA MÉDICA / PHANTOM (Controle de Qualidade em Mamografia/RX: Fibras >= 4, Calcificações >= 3, Massas >= 3, Artefatos)
"""

CHECKLISTS_ESPECIALIZADOS = {
    "TOMÓGRAFO": {
        "titulo": "Checklist Preventivo Oficial — Tomografia Computadorizada (v4.0)",
        "aplicavel": ["TOMÓGRAFO", "TOMOGRAFO", "TC", "CT", "BRIGHTSPEED", "BRIVO", "REVOLUTION", "LIGHTSPEED", "OPTIMA", "SOMATOM", "AQUILION", "NEUVIZ"],
        "itens": [
            # GANTRY
            {"item": "Simulação de exame helicoidal e axial pré-preventiva", "grupo": "Gantry & Dinâmica"},
            {"item": "Verificação do funcionamento das luzes, lasers de alinhamento e displays do Gantry", "grupo": "Gantry & Iluminação"},
            {"item": "Verificação dos sensores de posicionamento e segurança do paciente", "grupo": "Segurança do Paciente"},
            {"item": "Verificação mecânica e eletrônica do funcionamento do TILT (angulação do Gantry)", "grupo": "Gantry & Mecânica"},
            {"item": "Verificação e teste funcional dos botões de emergência do Gantry", "grupo": "Segurança & Emergência"},
            {"item": "Limpeza rigorosa das carenagens e proteção contra poeira do SLIP RING", "grupo": "Slip Ring & Brush Block"},
            {"item": "Inspeção visual e teste de pistas condutoras do SLIP RING", "grupo": "Slip Ring & Brush Block"},
            {"item": "Verificação do suporte BRUSH BLOCK e pressão das molas de assentamento", "grupo": "Slip Ring & Brush Block"},
            {"item": "Verificação e medição de desgaste de todas as escovas de contato elétrico", "grupo": "Slip Ring & Brush Block"},
            {"item": "Limpeza e desobstrução dos filtros de ar, ventiladores e grades do gerador HT", "grupo": "Gerador de Alta Tensão"},
            {"item": "Limpeza dos filtros de ar e ventiladores do sistema de aquisição de dados (DAS)", "grupo": "DAS & Detectores"},
            {"item": "Limpeza das grelhas, exaustores e ventiladores de refrigeração do Gantry", "grupo": "Refrigeração do Gantry"},
            {"item": "Limpeza do detector na janela de aquisição de raios-X (MYLAR) com material apropriado", "grupo": "DAS & Detectores"},
            {"item": "Limpeza técnica do SCAN WINDOW (janela óptica de varredura)", "grupo": "DAS & Detectores"},
            {"item": "Verificação da parte rotacional, correias, polias e sistema de acoplamento mecânico", "grupo": "Gantry Rotacional"},
            {"item": "Verificação e limpeza do radiador, filtros de ar, fluído térmico e ventiladores do tubo de raios-X", "grupo": "Tubo de Raios-X"},
            {"item": "Verificação e limpeza do ventilador e dissipadores do inversor do gerador (JEDI)", "grupo": "Gerador de Alta Tensão"},
            {"item": "Verificação e aplicação de graxa técnica homologada no rolamento principal do Gantry", "grupo": "Gantry Rotacional"},
            {"item": "Verificação dos parâmetros elétricos de kV, mA e tempo de rotação", "grupo": "Controle Elétrico"},
            
            # MESA PACIENTE
            {"item": "Limpeza técnica minuciosa da mecânica e guias de movimentação da mesa", "grupo": "Mesa de Paciente"},
            {"item": "Verificação da integridade, ancoragem e tensão do cabo de aço do potenciômetro da mesa", "grupo": "Mesa de Paciente"},
            {"item": "Verificação, aspiração e lubrificação dos trilhos de deslocamento horizontal e vertical", "grupo": "Mesa de Paciente"},
            {"item": "Limpeza técnica e despoeiramento da área de eletrônica e encoders da mesa", "grupo": "Mesa de Paciente"},
            
            # CONSOLE DE OPERAÇÃO
            {"item": "Verificação, extração e análise dos logs de erro do sistema operacional e hardware", "grupo": "Software & Diagnóstico"},
            {"item": "Verificação de logs e códigos de erro de comunicação da mesa com o Gantry", "grupo": "Software & Diagnóstico"},
            {"item": "Verificação e registro do número total de pacientes cadastrados e rotações do tubo", "grupo": "Contadores & Tubo"},
            {"item": "Inspeção visual e limpeza técnica dos monitores de aquisição e laudo médico", "grupo": "Console & Monitores"},
            {"item": "Limpeza dos filtros de ar, ventiladores e grelhas da workstation e rack de recon", "grupo": "Console & Processamento"},
            {"item": "Verificação interna e limpeza dos computadores (Host e Recon)", "grupo": "Console & Processamento"},
            {"item": "Verificação do tempo e estabilidade de inicialização do software operacional (Software Boot)", "grupo": "Software & Diagnóstico"},
            {"item": "Verificação de funcionamento de todos os botões físicos e iluminação do SCAN BOX", "grupo": "Interface & Scan Box"},
            {"item": "Verificação das luzes sinalizadoras de exposição no console e sala de exames", "grupo": "Radioproteção"},
            {"item": "Realização do teste de cortes com phanton de água e calibração de rotina", "grupo": "Controle de Qualidade"},
            {"item": "Utilização do teste de ruído e número de CT (Hounsfield) com ROI central e periférico", "grupo": "Controle de Qualidade"},
            
            # PDU & FINALIZAÇÃO
            {"item": "Teste do botão de parada de emergência do PDU / quadro elétrico", "grupo": "Segurança & Emergência"},
            {"item": "Limpeza da área externa, carenagens e organização do cabeamento do PDU", "grupo": "PDU & Alimentação"},
            {"item": "Realização de testes funcionais completos de exposição e liberação clínica", "grupo": "Finalização & Liberação"}
        ]
    },

    "RAIOS-X FIXO": {
        "titulo": "Checklist Preventivo Oficial — Raio-X Fixo de Alta Resolução (v6.0)",
        "aplicavel": ["RAIOS-X FIXO", "RAIOS X FIXO", "RAIO-X FIXO", "RX FIXO", "RAIOS-X ANALOGICO", "RAIOS-X DIGITAL", "SALA DE RAIO-X", "ALTUS", "COMPACTO PLUS", "XR 6000", "MULTIX", "INTECAL", "RAYTEC", "TD 500", "TDK 500", "ROENTAX", "LOTUS"],
        "itens": [
            # COMANDO
            {"item": "Verificação da rede elétrica (+- 10%) e conexões de aterramento de segurança (PE)", "grupo": "Alimentação & Rede"},
            {"item": "Verificação e integridade das ligações elétricas e flats entre placas de circuito", "grupo": "Eletrônica & Comando"},
            {"item": "Verificação e medição das tensões das fontes DC reguladas (+5V, +-12V, +-15V, +24V)", "grupo": "Eletrônica & Comando"},
            {"item": "Verificação do funcionamento do circuito de partida, rotação e freio do anodo giratório", "grupo": "Gerador & Tubo"},
            {"item": "Verificação das tensões e calibração do estabilizador de filamento do tubo", "grupo": "Gerador & Tubo"},
            {"item": "Verificação do funcionamento da lâmpada de sinalização de emissão de raios-X", "grupo": "Radioproteção"},
            {"item": "Verificação e teste visual de toda a sinalização e displays do painel de controle", "grupo": "Console & Painel"},
            {"item": "Verificação do transformador de alta tensão e tanques geradores de alta frequência", "grupo": "Alta Tensão"},
            {"item": "Verificação do cabo de aço e mecanismo motorizado de seleção de kV", "grupo": "Eletrônica & Comando"},
            {"item": "Verificação e aferição das chaves seletoras e encoders de kV, mA e mAs", "grupo": "Console & Painel"},
            {"item": "Teste de funcionamento dos bloqueios de segurança e intertravamento de disparos", "grupo": "Segurança Operacional"},
            {"item": "Verificação de avarias na pintura e carenagens do console de comando", "grupo": "Estrutura & Acabamento"},
            
            # ESTATIVA PORTA TUBO
            {"item": "Verificação da integridade, desgaste e fixação do cabo de aço da estativa porta-tubo", "grupo": "Estativa & Mecânica"},
            {"item": "Verificação da integridade dos cabos elétricos de força, comando e chicotes flexíveis", "grupo": "Estativa & Mecânica"},
            {"item": "Verificação do funcionamento dos freios mecânicos e eletromagnéticos da estativa", "grupo": "Freios & Movimentos"},
            {"item": "Verificação do funcionamento do tubo de raios-X e ausência de vazamento de óleo", "grupo": "Tubo de Raios-X"},
            {"item": "Verificação do funcionamento mecânico do colimador e temporizador do campo luminoso", "grupo": "Colimação & Radiação"},
            {"item": "Verificação do funcionamento de todo o sistema mecânico de elevação e translação", "grupo": "Estativa & Mecânica"},
            {"item": "Verificação, alinhamento, limpeza e lubrificação dos trilhos superior e inferior", "grupo": "Trilhos & Guias"},
            {"item": "Verificação do balanceamento mecânico da coluna e contrapesos da estativa", "grupo": "Estativa & Mecânica"},
            {"item": "Verificação dos cabos de alta tensão blindados (HT cables) e conectores de anodo/catodo", "grupo": "Alta Tensão"},
            {"item": "Limpeza externa técnica e lubrificação das engrenagens e rolamentos da estativa", "grupo": "Higienização & Lubrificação"},
            {"item": "Verificação e aferição da centralização exata da luz do colimador com o feixe de radiação", "grupo": "Colimação & Radiação"},
            {"item": "Verificação do desgaste da ampola de raios-X e estabilidade do ponto focal", "grupo": "Tubo de Raios-X"},
            {"item": "Verificação de avarias na pintura e integridade da carcaça da estativa", "grupo": "Estrutura & Acabamento"},
            
            # BUCKY VERTICAL / MURAL
            {"item": "Verificação do funcionamento de oscilação e acionamento do bucky vertical (mural)", "grupo": "Bucky Mural"},
            {"item": "Verificação da integridade física e alinhamento da grade anti-difusora mural", "grupo": "Bucky Mural"},
            {"item": "Verificação da integridade dos cabos elétricos e aterramento do bucky mural", "grupo": "Bucky Mural"},
            {"item": "Verificação do funcionamento dos freios de posicionamento vertical da estativa mural", "grupo": "Bucky Mural"},
            {"item": "Verificação da integridade do tampo de acrílico/fibra de carbono do bucky vertical", "grupo": "Bucky Mural"},
            {"item": "Verificação do travamento, molas e mecanismo da bandeja porta-cassete/detector", "grupo": "Bucky Mural"},
            {"item": "Verificação do sistema mecânico, roletes e guias do bucky mural", "grupo": "Bucky Mural"},
            {"item": "Verificação de avarias na pintura e estrutura do bucky mural", "grupo": "Estrutura & Acabamento"},
            {"item": "Verificação do cabo de aço e contrapesos do sistema de elevação mural", "grupo": "Bucky Mural"},
            {"item": "Limpeza interna, externa e lubrificação das colunas de deslizamento do bucky", "grupo": "Higienização & Lubrificação"},
            
            # MESA DE EXAME
            {"item": "Verificação do funcionamento de oscilação do bucky da mesa de exames", "grupo": "Mesa de Exames"},
            {"item": "Verificação da integridade física da grade anti-difusora da mesa", "grupo": "Mesa de Exames"},
            {"item": "Verificação da integridade dos cabos elétricos móveis da mesa", "grupo": "Mesa de Exames"},
            {"item": "Verificação do funcionamento dos freios eletromagnéticos de flutuação longitudinal/transversal", "grupo": "Mesa de Exames"},
            {"item": "Verificação da integridade física, trincas e fixação do tampo flutuante da mesa", "grupo": "Mesa de Exames"},
            {"item": "Verificação do funcionamento e travas da bandeja porta-cassete da mesa", "grupo": "Mesa de Exames"},
            {"item": "Limpeza interna, externa e lubrificação das guias e pedais da mesa de exame", "grupo": "Higienização & Lubrificação"},
            {"item": "Verificação de avarias na pintura e carenagens da mesa", "grupo": "Estrutura & Acabamento"},
            
            # TI & NOBREAK
            {"item": "Backup completo das configurações do gerador e parâmetros técnicos", "grupo": "Software & Backup"},
            {"item": "Verificação de espaço em disco e logs no console de operação", "grupo": "Console & Processamento"},
            {"item": "Limpeza do console de operação, monitor e periféricos", "grupo": "Console & Monitores"},
            {"item": "Teste de funcionamento, autonomia e transferência de carga do nobreak", "grupo": "Alimentação & Rede"}
        ]
    },

    "RAIOS-X MÓVEL / TRANSPORTÁVEL": {
        "titulo": "Checklist Preventivo Oficial — Raio-X Móvel / Transportável (Leito & UTI)",
        "aplicavel": ["RAIOS-X MOVEL", "RAIOS-X MÓVEL", "RAIOS-X TRANSPORTAVEL", "RAIOS-X TRANSPORTÁVEL", "RX MOVEL", "RX MÓVEL", "RX TRANSP", "AQUILA", "AQUILLA", "PEGASO", "MOBILEDART", "TITANIUM", "POLYMOBIL", "MX8", "NEUVISION 550M"],
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
        "titulo": "Checklist Preventivo Oficial — Mamógrafo de Alta Resolução (v3.0)",
        "aplicavel": ["MAMÓGRAFO", "MAMOGRAFO", "MAMOGRAFIA", "MM", "SENOGRAPHE", "LILYUM", "DELICATA", "DIAMOND", "AURORA", "AFFINITY", "M-IV", "PERFORMA", "MAMMOMAT", "ALPHA ST", "700T", "CRYSTAL"],
        "itens": [
            # COMANDO
            {"item": "Verificação das ligações elétricas entre placas, bornes e chicotes de comando", "grupo": "Comando & Eletrônica"},
            {"item": "Verificação do circuito de partida, rotação e freio do anodo do tubo de mamografia", "grupo": "Tubo & Gerador"},
            {"item": "Verificação do acionamento e visibilidade da lâmpada indicadora de radiação", "grupo": "Radioproteção"},
            {"item": "Verificação e teste visual de toda a sinalização e displays digitais do painel", "grupo": "Console & Painel"},
            {"item": "Verificação do transformador de alta tensão e isolamento do tanque", "grupo": "Alta Tensão"},
            {"item": "Verificação de avarias na pintura e integridade da carcaça do comando", "grupo": "Estrutura & Acabamento"},
            
            # ESTATIVA / BRAÇO C
            {"item": "Verificação da integridade e ancoragem dos cabos de aço da coluna e braço em C", "grupo": "Braço em C & Mecânica"},
            {"item": "Verificação da integridade de todos os cabos elétricos e chicotes flexíveis móveis", "grupo": "Eletrônica & Cabeamento"},
            {"item": "Verificação do funcionamento dos freios mecânicos e eletromagnéticos de rotação", "grupo": "Freios & Movimentos"},
            {"item": "Verificação do funcionamento do tubo de raios-X e refrigeração da cúpula", "grupo": "Tubo & Gerador"},
            {"item": "Verificação do funcionamento do colimador e comutação das palhetas de filtro (Molibdênio/Ródio)", "grupo": "Colimação & Filtros"},
            {"item": "Verificação do funcionamento de todo o sistema mecânico de elevação e rotação (CC e MLO)", "grupo": "Braço em C & Mecânica"},
            {"item": "Verificação do balanceamento mecânico da estativa e ausência de folgas", "grupo": "Braço em C & Mecânica"},
            {"item": "Verificação dos cabos blindados de alta tensão e conectores isolados", "grupo": "Alta Tensão"},
            {"item": "Realização de limpeza interna técnica, externa e lubrificação das guias", "grupo": "Higienização & Lubrificação"},
            {"item": "Verificação de avarias na pintura, protetores faciais e carenagens da estativa", "grupo": "Estrutura & Acabamento"},
            {"item": "Verificação do funcionamento e deslizamento dos buckys mamográficos 18x24 e 24x30", "grupo": "Bucky & Imagem"},
            {"item": "Verificação da integridade física e ausência de trincas nas pás de compressão 18x24 e 24x30", "grupo": "Compressão"},
            {"item": "Aferição da força de compressão motorizada (limite regulamentar 15 a 20 daN) e manual com dinamômetro", "grupo": "Compressão"},
            {"item": "Verificação do acionamento e suavidade dos pedais duplos de compressão e descompressão", "grupo": "Pedais & Segurança"},
            {"item": "Verificação dos botões de liberação rápida de compressão e parada de emergência", "grupo": "Segurança do Paciente"},
            {"item": "Teste de acionamento do controle automático de exposição (AEC) com simulador acrílico", "grupo": "Controle de Qualidade"}
        ]
    },

    "DENSITOMETRIA ÓSSEA": {
        "titulo": "Checklist Preventivo Oficial — Densitometria Óssea (v1.1)",
        "aplicavel": ["DENSITOMETRIA", "DENSITOMETRO", "DENSITÔMETRO", "DO", "LUNAR", "PRODIGY", "DPX", "PRIMUS", "OSTEOSYS"],
        "itens": [
            {"item": "Verificação dos cabos de alta tensão e conectores isolados do tubo de raios-X", "grupo": "Alta Tensão"},
            {"item": "Verificação dos cabos de sinal, esteiras porta-cabos flexíveis e cabeamento do detector", "grupo": "Sinal & Comunicação"},
            {"item": "Verificação e medição das tensões de saída das fontes de alimentação DC (+5V, +-12V, +24V, +48V)", "grupo": "Fontes de Alimentação"},
            {"item": "Verificação e teste do obturador (shutter) de radiação e colimador de feixe lápis/leque", "grupo": "Feixe & Colimação"},
            {"item": "Verificação do funcionamento dos botões de parada de emergência e sensores de fim de curso", "grupo": "Segurança"},
            {"item": "Verificação da integridade física, higienização e nivelamento do tampo acolchoado da mesa", "grupo": "Mesa de Exame"},
            {"item": "Verificação da integridade das esteiras flexíveis e chicotes de movimentação móvel", "grupo": "Mecânica & Guias"},
            {"item": "Realização de limpeza técnica interna, externa e lubrificação dos eixos de varredura X e Y", "grupo": "Mecânica & Guias"},
            {"item": "Verificação de avarias na pintura, alinhamento do laser de posicionamento e estrutura", "grupo": "Estrutura & Carenagens"},
            {"item": "Realização do teste de controle de qualidade diário (QA diário com bloco padrão de calibração)", "grupo": "Controle de Qualidade"}
        ]
    },

    "CR / DIGITALIZADOR": {
        "titulo": "Checklist Preventivo Oficial — Sistema de Radiografia Computadorizada (CR)",
        "aplicavel": ["CR", "DIGITALIZADOR", "110HQ", "REGIUS", "AERODR", "AERO DR", "DRY", "DRYPRO", "COMPUTE RADIOGRAPHIC", "VIVIX"],
        "itens": [
            {"item": "Verificação mecânica, alinhamento e lubrificação dos trilhos e roletes de transporte do cassete", "grupo": "Mecânica & Transporte"},
            {"item": "Verificação do movimento de precisão da unidade de leitura óptica a laser", "grupo": "Leitora Óptica"},
            {"item": "Limpeza interna e aspiração técnica de poeira e resíduos do interior do leitor CR", "grupo": "Higienização Interna"},
            {"item": "Limpeza técnica dos espelhos ópticos, guias de luz e lentes da fotomultiplicadora (PMT)", "grupo": "Óptica & Fotomultiplicadora"},
            {"item": "Inspeção física, limpeza e eliminação de artefatos nas placas de fósforo e cassetes", "grupo": "Placas de Fósforo"},
            {"item": "Backup completo das configurações do software de aquisição e curvas de sensibilidade", "grupo": "Software & Calibração"},
            {"item": "Verificação de espaço em disco, banco de dados local e integridade de envio de exames ao PACS", "grupo": "TI & Conectividade"},
            {"item": "Limpeza e higienização do console de operação, monitor touchscreen e leitor de código de barras", "grupo": "Console & Periféricos"},
            {"item": "Teste de autonomia de carga e transferência de rede do nobreak dedicado", "grupo": "Alimentação & Nobreak"}
        ]
    },

    "ARCO CIRÚRGICO": {
        "titulo": "Checklist Preventivo Oficial — Arco Cirúrgico Fluoroscópico",
        "aplicavel": ["ARCO CIRÚRGICO", "ARCO CIRURGICO", "C-ARM", "OEC", "BRIVO 850", "EVERVIEW", "CIOS", "PULSERA", "ZENITION"],
        "itens": [
            {"item": "Verificação dos movimentos orbitais, balanceamento e rotação livre do braço em C", "grupo": "Mecânica do Braço"},
            {"item": "Verificação de travamento mecânico e freios de retenção do posicionamento cirúrgico", "grupo": "Mecânica do Braço"},
            {"item": "Verificação e teste de resolução do intensificador de imagem ou detector plano FPD", "grupo": "Imagem & Intensificador"},
            {"item": "Verificação do colimador circular / íris e palhetas de sombreamento de corte", "grupo": "Colimação & Radiação"},
            {"item": "Verificação da integridade do cabo de interligação flexível de alta tensão entre as unidades", "grupo": "Cabeamento & Força"},
            {"item": "Verificação do pedal duplo de disparo (fluoroscopia contínua, pulsada e radiografia)", "grupo": "Comandos & Pedais"},
            {"item": "Verificação da articulação, calibração e brilho dos monitores médicos de centro cirúrgico", "grupo": "Monitores & Carrinho"},
            {"item": "Verificação dos botões de emergência e alarme sonoro regulamentar de 5 minutos (RDC 611 / IN 91)", "grupo": "Segurança & Radioproteção"},
            {"item": "Verificação dos rodízios direcionais, freio de transporte e protetores de cabo de piso", "grupo": "Rodízios & Transporte"},
            {"item": "Teste funcional de exposição em baixa dose e calibração de imagem fluoroscópica", "grupo": "Testes Funcionais"}
        ]
    },

    "ULTRASSONOGRAFIA": {
        "titulo": "Checklist Preventivo Oficial — Ultrassonografia Diagnóstica",
        "aplicavel": ["ULTRASSONOGRAFIA", "ULTRASSOM", "USG", "ECOCARDIOGRAMA", "VOLUSON", "LOGIQ"],
        "itens": [
            {"item": "Inspeção visual minuciosa da carcaça, lentes acústicas e cabos dos transdutores sem trincas", "grupo": "Transdutores"},
            {"item": "Verificação de pinos, travas de travamento mecânico e conectores dos transdutores", "grupo": "Transdutores"},
            {"item": "Verificação de funcionamento do painel alfanumérico, encoders de ganho (TGC) e trackball", "grupo": "Painel de Controle"},
            {"item": "Verificação da articulação e mecanismo pneumático de elevação/rotação do monitor", "grupo": "Monitor & Braço"},
            {"item": "Limpeza e desobstrução dos filtros de ar e ventiladores de refrigeração da fonte de alimentação", "grupo": "Refrigeração & Fonte"},
            {"item": "Verificação dos freios das rodas e sistema de trava direcional do equipamento", "grupo": "Mecânica & Rodízios"},
            {"item": "Teste com phantom de ultrassom para avaliação de sensibilidade, resolução axial e lateral", "grupo": "Controle de Qualidade"},
            {"item": "Backup das configurações do equipamento, presets médicos e biblioteca de medidas", "grupo": "Backup & Software"},
            {"item": "Limpeza externa, higienização dos suportes de transdutores e compartimento do gel", "grupo": "Finalização & Higienização"}
        ]
    },

    "FÍSICA MÉDICA / PHANTOM": {
        "titulo": "Checklist Oficial de Física Médica — Controle de Qualidade Phantom (v18.0)",
        "aplicavel": ["PHANTOM", "FISICA MEDICA", "FÍSICA MÉDICA", "CONTROLE DE QUALIDADE", "CQ"],
        "itens": [
            {"item": "Posicionamento correto do phantom padrão de acrílico no suporte de exame", "grupo": "Posicionamento"},
            {"item": "Realização da compressão padronizada (espessura de referência e força adequada)", "grupo": "Compressão"},
            {"item": "Inserção do receptor de imagem (cassete CR ou receptor digital FPD)", "grupo": "Receptor de Imagem"},
            {"item": "Verificação e posicionamento exato da câmara de ionização / fotocélula (AEC)", "grupo": "Câmara de Ionização"},
            {"item": "Seleção dos parâmetros técnicos de kV e mAs no modo automático (AEC)", "grupo": "Técnica Radiográfica"},
            {"item": "Verificação e anotação dos valores nominais de kV, mAs e tempo exibidos no disparo", "grupo": "Técnica Radiográfica"},
            {"item": "Leitura do cassete / aquisição da imagem digital no console de processamento", "grupo": "Aquisição & Imagem"},
            {"item": "Análise técnica minuciosa da imagem obtida com ajustes de brilho, contraste e zoom", "grupo": "Análise da Imagem"},
            {"item": "Contagem e avaliação do número de fibras musculares simuladas visíveis (Critério: >= 4 de 5)", "grupo": "Critérios RDC 611"},
            {"item": "Contagem e avaliação dos grupos de microcalcificações visíveis (Critério: >= 3 de 4)", "grupo": "Critérios RDC 611"},
            {"item": "Contagem e avaliação dos simuladores de massas tumorais visíveis (Critério: >= 3 de 4)", "grupo": "Critérios RDC 611"},
            {"item": "Verificação rigorosa da ausência de artefatos, riscos, manchas ou pixels mortos na imagem", "grupo": "Controle de Artefatos"}
        ]
    }
}

def identificar_categoria_checklist(nome_equipamento: str, categoria_sugerida: str = "") -> str:
    """Identifica com alta precisão qual o checklist correto para a máquina informada."""
    nome_norm = f"{nome_equipamento} {categoria_sugerida}".upper()

    # 1. Física Médica / Phantom
    if any(k in nome_norm for k in ["PHANTOM", "FISICA MEDICA", "FÍSICA MÉDICA", "CONTROLE DE QUALIDADE"]):
        return "FÍSICA MÉDICA / PHANTOM"
    
    # 2. Tomógrafo
    if any(k in nome_norm for k in ["TOMÓGRAFO", "TOMOGRAFO", "BRIGHTSPEED", "BRIVO 385", "BRIVO 325", "REVOLUTION", "ALEXION", "ASTEION", "NEUVIZ", "SOMATOM", "AQUILION", "LIGHTSPEED", "OPTIMA"]):
        return "TOMÓGRAFO"
        
    # 3. Raio-X Móvel / Transportável (REGRA ESSENCIAL: Prioridade sobre fixo!)
    if any(k in nome_norm for k in ["MÓVEL", "MOVEL", "TRANSPORTÁVEL", "TRANSPORTAVEL", "TRANSP", "AQUILA", "AQUILLA", "PEGASO", "MOBILEDART", "TITANIUM", "LEITO", "PORTATIL", "PORTÁTIL", "POLYMOBIL", "MX8", "NEUVISION 550M"]):
        return "RAIOS-X MÓVEL / TRANSPORTÁVEL"
        
    # 4. Raio-X Fixo
    if any(k in nome_norm for k in ["RAIOS-X", "RAIOS X", "RAIO-X", "RAIO X", "RX", "ALTUS", "COMPACTO PLUS", "COMPACT PLUS", "XR 6000", "MULTIX", "INTECAL", "RAYTEC", "TD 500", "TDK 500", "ROENTAX", "LOTUS"]):
        return "RAIOS-X FIXO"
        
    # 5. Mamógrafo
    if any(k in nome_norm for k in ["MAMÓGRAFO", "MAMOGRAFO", "MAMOGRAFIA", "MM", "SENOGRAPHE", "LILYUM", "DELICATA", "DIAMOND", "AURORA", "AFFINITY", "M-IV", "PERFORMA", "MAMMOMAT", "ALPHA ST", "700T", "CRYSTAL"]):
        return "MAMÓGRAFO"
        
    # 6. Densitometria Óssea
    if any(k in nome_norm for k in ["DENSITOMETRIA", "DENSITOMETRO", "DENSITÔMETRO", "DO", "LUNAR", "PRODIGY", "DPX", "PRIMUS", "OSTEOSYS"]):
        return "DENSITOMETRIA ÓSSEA"
        
    # 7. CR / Digitalizador
    if any(k in nome_norm for k in ["CR", "DIGITALIZADOR", "REGIUS", "AERODR", "AERO DR", "DRY", "DRYPRO", "COMPUTE RADIOGRAPHIC", "VIVIX", "110HQ"]):
        return "CR / DIGITALIZADOR"
        
    # 8. Arco Cirúrgico
    if any(k in nome_norm for k in ["ARCO CIRÚRGICO", "ARCO CIRURGICO", "C-ARM", "OEC", "BRIVO 850", "EVERVIEW", "CIOS", "PULSERA", "ZENITION"]):
        return "ARCO CIRÚRGICO"
        
    # 9. Ultrassonografia
    if any(k in nome_norm for k in ["ULTRASSONOGRAFIA", "ULTRASSOM", "USG", "ECOCARDIOGRAMA", "VOLUSON", "LOGIQ"]):
        return "ULTRASSONOGRAFIA"
        
    return "RAIOS-X FIXO"

def obter_checklist_oficial(nome_equipamento: str, categoria: str = "") -> dict:
    """Retorna o checklist completo e estruturado para o equipamento indicado."""
    cat = identificar_categoria_checklist(nome_equipamento, categoria)
    return CHECKLISTS_ESPECIALIZADOS.get(cat, CHECKLISTS_ESPECIALIZADOS["RAIOS-X FIXO"])
