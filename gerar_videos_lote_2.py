import os
import sys
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = r"C:\Users\vitor\OneDrive\Desktop\Sistema Emed"
VIDEOS_DIR = os.path.join(BASE_DIR, "Videos_Treinamento_ITs")
TEMP_DIR = os.path.join(BASE_DIR, "temp_batch_its_2")
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

FFMPEG_BIN = r"C:\Users\vitor\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
VOICE = "pt-BR-AntonioNeural"

ITS_DEFINITIONS_LOTE_2 = [
    {
        "id": "IT_06",
        "code": "IT-TOMO-GE-006",
        "filename": "Video_IT06_Alinhamentos_Opticos_Colimador_Detector_GE.mp4",
        "title": "IT-06: ALINHAMENTOS ÓPTICOS DO COLIMADOR & DETECTOR",
        "equip": "Tomógrafos GE Brivo CT385 & BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO & INSTRUMENTAÇÃO ÓPTICA",
                "badge": "ALINHAMENTO GEOMÉTRICO (BOW & CBF)",
                "narration": "Olá, técnico da eMed! Bem-vindo à IT-06 para alinhamentos ópticos no GE BrightSpeed e Brivo 385. O Paulo no Almoxarifado separa o kit óptico oficial com relógio comparador micrométrico, ferramenta CBF e torquímetro de precisão.",
                "points": [
                    "• Alinhamento do feixe na janela do detector: Beam on Window (BOW)",
                    "• Alinhamento do filtro bow-tie e sag do colimador (CBF / SAG)",
                    "• Kit do Paulo: Relógio comparador (Dial Indicator) e Ajustador Z-axis",
                    "• Torquímetro calibrado: Parafusos M14 (96 N·m) e Flange M8 (30.5 N·m)"
                ],
                "alert": "GEOMETRIA CRÍTICA: Desalinhamentos ópticos geram sombras e degradação severa no MTF."
            },
            {
                "subtitle": "FASE 2: TESTE BOW & AJUSTE DOS CALÇOS MICROMÉTRICOS",
                "badge": "BEAM ON WINDOW (BOW) NO SERVICE DESKTOP",
                "narration": "Acesse no Service Desktop o teste Beam on Window. Execute disparos axiais de calibração monitorando a curva gaussiana do feixe. Utilize a chave micrométrica nos calços Z até o centro da curva coincidir perfeitamente com o detector.",
                "points": [
                    "• Acesso: Service Desktop -> Diagnostics -> Beam on Window (BOW)",
                    "• Leitura do perfil de radiação nos canais centrais e periféricos do DAS",
                    "• Ajuste mecânico dos calços de inclinação Z com relógio comparador",
                    "• Tolerância: Desvio máximo do feixe menor que 0.1 milímetros no eixo Z"
                ],
                "alert": "CUIDADO: Aperte os parafusos M14 em cruz ao torque de 96 N·m após o ajuste fino."
            },
            {
                "subtitle": "FASE 3: ALINHAMENTO CBF DO FILTRO & ENTREGA NA OS",
                "badge": "FILTRO BOW-TIE & FINALIZAÇÃO",
                "narration": "Ajuste a lâmina de sombra do filtro bow-tie através do parafuso CBF. Valide a simetria de dose bilateral no console. Finalize a OS no sistema registrando os relatórios de alinhamento e confirme a devolução dos instrumentos ao Almoxarifado.",
                "points": [
                    "• Alinhamento do filtro conformador de feixe (Collimator Beam Filter - CBF)",
                    "• Verificação de ausência de vinhetamento nos canais extremos do arco detector",
                    "• Varredura axial com phantom de água para validação de homogeneidade",
                    "• Baixa na OS técnica e encaminhamento do laudo de calibração ao cliente"
                ],
                "alert": "CONCLUSÃO: Sistema calibrado com alta fidelidade e resolução geométrica homologada."
            }
        ]
    },
    {
        "id": "IT_07",
        "code": "IT-TOMO-GE-007",
        "filename": "Video_IT07_Guia_Ferramenta_Gerador_JEDI_GE.mp4",
        "title": "IT-07: GUIA OPERACIONAL DO GERADOR JEDI (GEN TOOL)",
        "equip": "Tomógrafos GE Brivo CT385, BrightSpeed & Optima Series",
        "scenes": [
            {
                "subtitle": "FASE 1: ACESSO AO COMMON SERVICE DESKTOP & GENTOOLSHELL",
                "badge": "INTERFACE DO GERADOR JEDI",
                "narration": "Esta é a IT-07, o guia definitivo para operar o utilitário JEDI Generator Tool nos tomógrafos GE. No console Linux do operador, acesse a aba Diagnostics, selecione X-Ray Generation e abra a janela mestre GenToolShell.",
                "points": [
                    "• Utilitário central de controle e diagnóstico do subsistema de alta tensão",
                    "• Acesso: Common Service Desktop -> Diagnostics -> X-Ray Generation",
                    "• Arquitetura em 3 colunas: Tube Install, JEDI Tests e Database Management",
                    "• Comunicação via barramento CAN Bus entre console e placas do Gantry"
                ],
                "alert": "ATENÇÃO: Mantenha o Gantry parado e sem pacientes na sala ao abrir o GenToolShell."
            },
            {
                "subtitle": "FASE 2: MENU TUBE INSTALL & RESET DE TNT",
                "badge": "INSTALAÇÃO DE TUBO & DADOS TNT",
                "narration": "Na coluna Tube Install, selecione o modelo do tubo inserindo número de série e part number. Execute a rotina Reset TnT Data para zerar os contadores térmicos de vida útil após a substituição do tubo pelo técnico em campo.",
                "points": [
                    "• Seleção do modelo do tubo (ex: Solarix 5.0 ou Performix 6.3 MHU)",
                    "• Inserção do Serial Number e data de fabricação do tubo novo",
                    "• Execução do comando Reset TnT Data (Track and Trace) no banco SQL",
                    "• Gravação dos coeficientes de condutância e capacidade de dissipação anódica"
                ],
                "alert": "CRÍTICO: Nunca execute o TnT Reset se o tubo antigo estiver mantido no equipamento."
            },
            {
                "subtitle": "FASE 3: JEDI TESTS & DATABASE MANAGEMENT",
                "badge": "DIAGNÓSTICO DE KV, FILAMENTO & BANCO",
                "narration": "A coluna central JEDI Tests permite diagnosticar as formas de onda de kV, corrente de filamento e inversores ressonantes. Na coluna Database, efetue o backup das tabelas de calibração para garantir a integridade dos dados.",
                "points": [
                    "• kV Diagnostics: Análise de sobretensão, ripple e tempo de subida dos inversores",
                    "• Filament Calibration: Curvas de emissão de pequeno e grande foco (mA Steps)",
                    "• Database Management: Backup e restauração das tabelas do gerador em pen drive",
                    "• Atualização do status na OS e validação completa do subsistema gerador"
                ],
                "alert": "EFICIÊNCIA: Ferramenta indispensável para diagnóstico rápido de falhas de arco e filamento."
            }
        ]
    },
    {
        "id": "IT_08",
        "code": "IT-TOMO-GE-008",
        "filename": "Video_IT08_Verificacao_Tanque_HV_e_QA_GE.mp4",
        "title": "IT-08: VERIFICAÇÃO ELÉTRICA DO TANQUE HV & QA FINAL",
        "equip": "Tomógrafos GE Brivo CT385, BrightSpeed & Optima Series",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO & INSTRUMENTOS DE ALTA TENSÃO",
                "badge": "CIRCUITO HV BLEEDER & RESISTORES",
                "narration": "Bem-vindo à IT-08 para medições elétricas no Tanque de Alta Tensão e teste de garantia da qualidade. Confirme com o Paulo no Almoxarifado a retirada do osciloscópio isolado de 100 megahertz, divisores de teste e phantom de água.",
                "points": [
                    "• Verificação dos resistores de realimentação (feedback bleeder resistors)",
                    "• Equipamentos do Almoxarifado: Osciloscópio Fluke/Tektronix, pontas 10X e phantom QA",
                    "• Inspeção física do tanque HV quanto a vazamento de óleo dielétrico e estufamento",
                    "• Aplicação das regras de segurança LOTO antes de abrir os poços dos cabos"
                ],
                "alert": "PERIGO DE ALTA TENSÃO: O tanque opera com até 140 kilovolts. Sempre aterre as carcaças."
            },
            {
                "subtitle": "FASE 2: MEDIÇÃO DAS FORMAS DE ONDA & FEEDBACK DE KV/MA",
                "badge": "PONTOS DE TESTE CP & OSCILOSCÓPIO",
                "narration": "Conecte os canais do osciloscópio nos pontos de teste da placa de controle de kV. Dispare em 120 kV e 200 mA em modo de calibração. A forma de onda deve ser plana, com tempo de subida menor que 2 milissegundos e ripple inferior a 1.5%.",
                "points": [
                    "• Conexão nas tomadas de teste kV Monitor e mA Monitor com aterramento coaxial",
                    "• Disparo de teste com gerador em modo de calibração no console",
                    "• Análise do tempo de subida (Rise Time < 2.0 ms) e estabilidade de platô",
                    "• Tolerância de medição: Tensão medida deve coincidir em ± 1.0% do valor programado"
                ],
                "alert": "PRECISÃO: Oscilações excessivas no sinal indicam degradação nos capacitores do tanque."
            },
            {
                "subtitle": "FASE 3: TESTE DE QA COM PHANTOM DE ÁGUA & LAUDO",
                "badge": "CONTROLE DE QUALIDADE CLÍNICO (QA)",
                "narration": "Instale o phantom de água oficial GE no centro do Gantry. Execute a rotina de controle de qualidade diária e semanal. O número CT da água pura deve registrar zero mais ou menos quatro unidades Hounsfield com ruído dentro dos padrões.",
                "points": [
                    "• Posicionamento do Phantom de Água GE no suporte de cabeça da mesa",
                    "• Varredura axial padrão: 120 kV, 200 mA, espessura de corte de 5mm",
                    "• Critério de Aceitação: ROI central = 0.0 ± 4.0 HU | Desvio Padrão (Ruído) < 3.2 HU",
                    "• Emissão automática do relatório de QA, anexação na OS e entrega ao hospital"
                ],
                "alert": "CONFORMIDADE: O laudo de QA assinado é o documento que autoriza o uso clínico com pacientes."
            }
        ]
    },
    {
        "id": "IT_09",
        "code": "IT-TOMO-GE-009",
        "filename": "Video_IT09_Alinhamento_Plano_de_Rotacao_POR_GE.mp4",
        "title": "IT-09: ALINHAMENTO DO PLANO DE ROTAÇÃO (POR)",
        "equip": "Tomógrafos GE Brivo CT385 & BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: CONCEITO DE POR & QUANDO EXECUTAR",
                "badge": "PLANE OF ROTATION (POR)",
                "narration": "Nesta IT-09, abordamos o alinhamento do Plano de Rotação POR do Gantry em relação ao eixo da mesa do paciente. Este ajuste é obrigatório após nivelamento do Gantry no piso da sala ou substituição do rolamento principal.",
                "points": [
                    "• Conceito: O anel giratório deve ser perfeitamente ortogonal ao eixo Z de avanço da mesa",
                    "• Indicações: Troca do rolamento do gantry, reinstalação do chassi ou vibração crônica",
                    "• Kit do Paulo: Dispositivo POR (Alignment Fixture), relógio comparador e calços de latão",
                    "• Tolerância máxima permitida pela GE: Paralelismo dentro de 0.15 milímetros"
                ],
                "alert": "IMPORTÂNCIA: Desalinhamento do POR provoca cortes oblíquos e artefatos de fatiamento 3D."
            },
            {
                "subtitle": "FASE 2: MEDIÇÃO COM RELÓGIO COMPARADOR EM 4 PONTOS",
                "badge": "LEITURA DE DEFLEXÃO ANGULAR",
                "narration": "Instale o dispositivo com o relógio comparador na mesa e apoie a haste na pista usinada do anel rotativo. Gire o Gantry manualmente e meça o desvio nos ângulos de zero, noventa, cento e oitenta e duzentos e setenta graus.",
                "points": [
                    "• Montagem do suporte magnético articulado na extremidade da calha da mesa",
                    "• Zere o relógio comparador na posição de 12 horas (0 graus)",
                    "• Giro manual lento do rotor registrando o ponteiro nas 4 posições cardeais",
                    "• Cálculo da inclinação mecânica axial e identificação do ponto de apoio"
                ],
                "alert": "CUIDADO: Trave o freio de rotação antes de se apoiar ou soltar os parafusos da base."
            },
            {
                "subtitle": "FASE 3: INSERÇÃO DE CALÇOS (SHIMS) & TORQUE DOS PARAFUSOS",
                "badge": "CALÇOS DE PRECISÃO & FECHAMENTO",
                "narration": "Afrouxe os parafusos de ancoragem M16 da base do Gantry. Insira os calços metálicos de espessura calculada sob as sapatas até a variação do relógio ficar abaixo de 0.15 milímetros. Aperte com torquímetro ao torque especificado de fábrica.",
                "points": [
                    "• Utilização de macaco mecânico para alívio de peso das sapatas do Gantry",
                    "• Inserção dos calços calibrados (Shims de 0.05mm a 1.0mm) nas sapatas dianteiras ou traseiras",
                    "• Releitura completa de 360 graus confirmando desvio menor que 0.15 mm",
                    "• Aperto final dos parafusos chumbadores com torquímetro e registro na OS"
                ],
                "alert": "SUCESSO: Gantry perfeitamente esquadrejado com a mesa para reconstruções tomográficas perfeitas."
            }
        ]
    },
    {
        "id": "IT_10",
        "code": "IT-TOMO-GE-010",
        "filename": "Video_IT10_Alinhamento_Isocentro_Mecanico_e_HOT_ISO_GE.mp4",
        "title": "IT-10: ALINHAMENTO DO ISOCENTRO (ISO & HOT ISO)",
        "equip": "Tomógrafos GE Brivo CT385 & BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: CONCEITO DE ISOCENTRO MECÂNICO E TÉRMICO",
                "badge": "CENTRALIZAÇÃO DO FOCO DE RAIO-X",
                "narration": "Olá, técnico eMed! Esta é a IT-10 de alinhamento do Isocentro Mecânico e HOT ISO. O feixe de radiação deve cruzar exatamente o centro de rotação sob condições estáticas e também sob carga térmica pesada com o ânodo aquecido.",
                "points": [
                    "• Isocentro Mecânico (ISO): Linha central de mira do feixe cruzando o eixo do gantry",
                    "• Isocentro Ativo (HOT ISO): Compensação de expansão mecânica quando o tubo atinge 60% térmico",
                    "• Kit solicitado ao Paulo: Pino oficial centralizador ISO e suporte indexador da mesa",
                    "• Obrigatório após substituição de tubo, motor de tilt ou base do detector"
                ],
                "alert": "IMPACTO CLÍNICO: Erro de isocentro degrada a calibração de hounsfield e borra detalhes finos."
            },
            {
                "subtitle": "FASE 2: ALINHAMENTO MECÂNICO DO PINO ISO",
                "badge": "PINO CENTRALIZADOR & LASER DE MIRA",
                "narration": "Monte o pino de Isocentro na mesa e posicione-o exatamente na interseção das luzes laser de alinhamento sagital, coronal e transversal. No Service Desktop, execute o algoritmo ISO Alignment para medir a deflexão mecânica.",
                "points": [
                    "• Fixação do dispositivo com pino de tungstênio no berço da mesa de exames",
                    "• Centralização com os feixes laser do teto e laterais do Gantry",
                    "• Disparo de scout e varreduras axiais com baixa dose para capturar o pino",
                    "• Ajuste mecânico dos parafusos de posicionamento do tubo em coordenadas X e Y"
                ],
                "alert": "TOLERÂNCIA: O desvio do pino em relação ao centro de rotação deve ser inferior a 0.5 mm."
            },
            {
                "subtitle": "FASE 3: ROTINA HOT ISO COM AQUECIMENTO & REFINAMENTO",
                "badge": "WARM-UP ANÓDICO & VALIDAÇÃO DINÂMICA",
                "narration": "Execute disparos contínuos de aquecimento até a capacidade térmica do tubo atingir 50 por cento. Em seguida, acione o teste HOT ISO. O software calcula o desvio dinâmico e aplica a compensação de software para estabilidade clínica total.",
                "points": [
                    "• Aquecimento escalonado do anódio de raio-X até 50% de calor acumulado (HU Heat)",
                    "• Aquisição imediata do teste HOT ISO sob dilatação térmica dos mancais do tubo",
                    "• Gravação dos fatores de correção geométrica no banco de dados da estação",
                    "• Finalização da instrução de trabalho e conclusão formal da OS no sistema"
                ],
                "alert": "EXCELÊNCIA: O equipamento eMed garante precisão micrométrica sob qualquer volume de exames."
            }
        ]
    },
    {
        "id": "IT_11",
        "code": "IT-TOMO-GE-011",
        "filename": "Video_IT11_Calibracao_Colimador_e_Detailed_Cal_GE.mp4",
        "title": "IT-11: CALIBRAÇÃO DO COLIMADOR & DETAILED CALIBRATION",
        "equip": "Tomógrafos GE Brivo CT385 & BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO DA CALIBRAÇÃO DETALHADA DO SISTEMA",
                "badge": "MAPEAMENTO COMPLETO DE CANAIS",
                "narration": "Bem-vindo à IT-11. A calibração de aberturas do colimador e a Detailed Calibration mapeiam a sensibilidade de todos os canais e fatias multislice. Certifique-se de que a sala esteja entre 20 e 24 graus Celsius e o túnel completamente vazio.",
                "points": [
                    "• Calibração eletromecânica dos atuadores de fatiamento do colimador (Cam Motors)",
                    "• Detailed Cal: Mapeamento de ganho e linearidade de 0.625 mm até 10 mm de corte",
                    "• Condições obrigatórias: Temperatura ambiente estável entre 20°C e 24°C",
                    "• Túnel do Gantry totalmente livre e mesa recuada até a extremidade máxima"
                ],
                "alert": "AR LIVRE OBRIGATÓRIO: Qualquer objeto ou cabo no túnel corrompe as tabelas de ganho."
            },
            {
                "subtitle": "FASE 2: CALIBRAÇÃO DOS MOTORES DE ABERTURA DO COLIMADOR",
                "badge": "APERTURE CALIBRATION NO CONSOLE",
                "narration": "No console do operador, acesse Collimator Aperture Calibration. O sistema movimentará os motores de passo dos shutters de tungstênio, gravando a contagem de encoders para cada espessura de corte clí­nico.",
                "points": [
                    "• Acesso: Service Desktop -> Calibrations -> Collimator Aperture Cal",
                    "• Movimentação automática dos shutters superior e inferior de corte",
                    "• Mapeamento dos micropassos dos motores em relação à abertura do feixe",
                    "• Verificação de torque suave sem travamento mecânico nas buchas guia"
                ],
                "alert": "PRECISÃO: Se houver poeira ou atrito na fita do encoder, limpe com álcool isopropílico."
            },
            {
                "subtitle": "FASE 3: EXECUÇÃO DA DETAILED CALIBRATION & CONCLUSÃO",
                "badge": "VARREDURA MULTI-KV & RECONSTRUÇÃO",
                "narration": "Inicie a Detailed Calibration selecionando todas as combinações de kV e rotações. O processo realiza múltiplos disparos a ar por aproximadamente 40 minutos. Concluída a calibração, execute o QA de teste e encerre a OS no celular.",
                "points": [
                    "• Disparos sequenciais a ar em 80, 100, 120 e 140 kV para todas as espessuras de corte",
                    "• Gravação automática dos arquivos de compensação de feixe no disco do host",
                    "• Verificação de aprovação verde em 100% dos modos examinados",
                    "• Liberação final da máquina para a equipe médica e fechamento no Sistema eMed"
                ],
                "alert": "ENTREGA DE QUALIDADE: Imagens médicas sem artefatos e contraste radiológico calibrado."
            }
        ]
    },
    {
        "id": "IT_12",
        "code": "IT-TOMO-GE-012",
        "filename": "Video_IT12_Seguranca_Rotacao_Gantry_e_Varreduras_HHS_GE.mp4",
        "title": "IT-12: SEGURANÇA DE ROTAÇÃO & VARREDURAS HHS",
        "equip": "Tomógrafos GE Brivo CT385 & BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: CIRCUITO DE EMERGÊNCIA & INTERTRAVAMENTOS",
                "badge": "CIRCUITO DE PARADA & MICROCHAVES",
                "narration": "Atenção técnica! Esta é a IT-12 para teste dos circuitos de segurança de rotação do Gantry e varreduras térmicas HHS. Antes de liberar rotações de alta velocidade a 120 RPM, é obrigatório testar individualmente cada botoeira de emergência.",
                "points": [
                    "• Teste funcional das 4 botoeiras de parada de emergência (Console, Gantry e Mesa)",
                    "• Verificação das microchaves de contato das tampas frontais, traseiras e superiores",
                    "• Interrupção instantânea da rotação mecânica e queda da contatora de alta tensão",
                    "• Procedimento obrigatório após qualquer manutenção preventiva ou corretiva interna"
                ],
                "alert": "SEGURANÇA DE VIDA: Nunca burle chaves de fim de curso ou feche contatos em definitivo."
            },
            {
                "subtitle": "FASE 2: VARREDURAS HHS (HIGH HEAT STORAGE SCANS)",
                "badge": "CONDICIONAMENTO TÉRMICO EM ROTAÇÃO",
                "narration": "As varreduras HHS condicionam o tubo de raios-X e o circuito de refrigeração sob rotação de meio segundo por volta. Acione o protocolo HHS no console e monitore os manômetros de pressão e temperatura do trocador de calor de óleo.",
                "points": [
                    "• Disparos cíclicos de alta energia com o Gantry rodando a 0.5s por rotação",
                    "• Monitoramento da temperatura do óleo dielétrico e fluxo da bomba de circulação",
                    "• Alívio de tensões térmicas e desgaseificação residual na ampola de raio-X",
                    "• Verificação de ausência de ruído anormal nas mangueiras e conexões hidráulicas"
                ],
                "alert": "TERMAL: Se a temperatura do óleo ultrapassar 75 graus, o interlock térmico deve atuar."
            },
            {
                "subtitle": "FASE 3: SYSTEM SCANNING TEST & LIBERAÇÃO CLÍNICA",
                "badge": "TESTE DE ESTABILIDADE CONTÍNUA",
                "narration": "Execute o System Scanning Test com 20 rotações contínuas em modo helicoidal. Confirme a estabilidade dos transceptores do Slip Ring sem perda de sincronismo. Finalize a OS com o hospital e registre o sucesso no sistema.",
                "points": [
                    "• Teste de estresse: Aquisições helicoidais simulando uma rotina pesada de emergência",
                    "• Verificação de ausência de mensagens de erro no Error Log do Linux",
                    "• Fechamento seguro de todas as tampas externas com parafusos originais",
                    "• Assinatura do termo de entrega técnica pelo coordenador da radiologia"
                ],
                "alert": "EQUIPAMENTO HOMOLOGADO: Gantry 100% seguro e pronto para salvar vidas no pronto-socorro."
            }
        ]
    },
    {
        "id": "IT_13",
        "code": "IT-TOMO-GE-013",
        "filename": "Video_IT13_Substituicao_Placa_KV_Control_Board_GE.mp4",
        "title": "IT-13: SUBSTITUIÇÃO DA PLACA KV CONTROL BOARD",
        "equip": "Tomógrafos GE BrightSpeed Series (Lite, Select & 16)",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO & DESENERGIZAÇÃO LOTO NA POWER UNIT",
                "badge": "PLACA CONTROLADORA DE KV JEDI",
                "narration": "Bem-vindo à IT-13 para substituição da placa KV Control Board na Power Unit do Gantry. O Paulo no Almoxarifado fornece a placa programada e a pulseira de proteção antiestática. Siga rigorosamente o travamento de energia LOTO.",
                "points": [
                    "• Função: Placa mestre de regulação de alta tensão e disparo do gerador JEDI",
                    "• Materiais do Almoxarifado: Placa KV Control Board GE, pulseira ESD e chave de fenda",
                    "• Desenergização total: Chave do Gantry em OFF e bloqueio no disjuntor geral da sala",
                    "• Aguardar 10 minutos para descarga total dos bancos de capacitores internos"
                ],
                "alert": "ESTÁTICA: O manuseio da placa exige pulseira antiestática para não danificar os processadores."
            },
            {
                "subtitle": "FASE 2: TROCA FÍSICA & CONEXÃO DOS CONECTORES J",
                "badge": "SUBSTITUIÇÃO MECÂNICA & CABEAMENTO",
                "narration": "Desconecte cuidadosamente os conectores de fita e chicotes de fibra óptica da placa danificada. Remova os parafusos de fixação no chassi metálico, instale a nova placa KV Control e reconecte todos os conectores conferindo a pinagem.",
                "points": [
                    "• Desconexão dos conectores J1 a J8 e transceptores de fibra óptica do gatilho de kV",
                    "• Remoção dos parafusos de retenção com arruelas isolantes originais",
                    "• Fixação da nova placa no rack da Power Unit garantindo bom aterramento metálico",
                    "• Encaixe firme de todos os conectores com trava plástica e chicotes organizados"
                ],
                "alert": "FIBRA ÓPTICA: Nunca dobre os cabos de fibra óptica em raio inferior a 30 milímetros."
            },
            {
                "subtitle": "FASE 3: FLASH FIRMWARE DOWNLOAD & CALIBRAÇÃO DE MA",
                "badge": "CARGA DE FIRMWARE & VALIDAÇÃO NA OS",
                "narration": "Ligue o sistema e abra a JEDI Generator Tool. Execute a recarga de firmware pelo menu Flash Download. Em seguida, calibre a corrente de filamento em mA Calibration. Se a proposta da placa foi aprovada, dê baixa definitiva na OS.",
                "points": [
                    "• Procedimento de Flash Firmware: Atualização da ROM da placa via GenToolShell",
                    "• Calibração automática de corrente de filamento (mA Calibration) em 80 a 140 kV",
                    "• Verificação de status verde nos LEDs diagnósticos de alimentação da placa",
                    "• Finalização da OS: Selecione 'Instalação Definitiva' para baixa do estoque e faturamento"
                ],
                "alert": "BAIXA AUTOMÁTICA: O sistema atualiza o estoque de peças do Paulo e avisa o financeiro."
            }
        ]
    },
    {
        "id": "IT_14",
        "code": "IT-TOMO-GE-014",
        "filename": "Video_IT14_Substituicao_Controlador_Axial_Drive_GE.mp4",
        "title": "IT-14: SUBSTITUIÇÃO DO CONTROLADOR AXIAL DRIVE",
        "equip": "Tomógrafos GE BrightSpeed Series (Driver Titan / Danaher)",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO & DESENERGIZAÇÃO DO POWER PAN",
                "badge": "DRIVER DE ROTAÇÃO AXIAL (P/N 5344401)",
                "narration": "Esta é a IT-14 de substituição do Controlador de Rotação Axial Drive no Power Pan inferior do Gantry. O Paulo no Almoxarifado prepara o inversor Titan Danaher código 5344401 e o torquímetro com soquetes isolados.",
                "points": [
                    "• Componente: 2010 Axial Drive Controller (Driver Titan / Danaher Motion)",
                    "• Localização: Power Pan na base fixa do Gantry abaixo do anel rotativo",
                    "• Risco de Choque: Barramento interno opera com 350 Volts DC retificados",
                    "• Desenergização LOTO e medição de tensão zero nos bornes DC+ e DC- antes da remoção"
                ],
                "alert": "ENERGIA RESIDUAL: O barramento DC dos capacitores leva até 5 minutos para descarregar."
            },
            {
                "subtitle": "FASE 2: DESCONEXÃO DE FORÇA & FIXAÇÃO ESTRUTURAL",
                "badge": "BORNE DE FORÇA & CABOS DE COMUNICAÇÃO",
                "narration": "Identifique e solte as três fases do motor trifásico U, V e W, e a alimentação de 208 Volts trifásica. Desconecte o cabo serial de comunicação e retire os quatro parafusos que fixam a carcaça de alumínio do inversor.",
                "points": [
                    "• Desconexão dos cabos de potência do motor nos terminais U, V, W e Terra PE",
                    "• Desconexão da alimentação de entrada trifásica e cabos de freio de retenção",
                    "• Desconexão do cabo de controle do encoder e comunicação serial RS-485",
                    "• Remoção do inversor antigo e instalação da nova unidade no suporte metálico"
                ],
                "alert": "SEQUÊNCIA DE FASES: Respeite a ordem U-V-W para não inverter o sentido de giro do gantry."
            },
            {
                "subtitle": "FASE 3: DISPLAY DE STATUS, ROTAÇÃO DE TESTE & FECHO NA OS",
                "badge": "DISPLAY DE 7 SEGMENTOS & RETORNO",
                "narration": "Ao religar, confira o display de 7 segmentos do inversor: ele deve exibir o dígito 4 indicando modo de espera pronto. Execute o teste de rampa de aceleração suave até a velocidade máxima e conclua a OS dando baixa no material.",
                "points": [
                    "• Inicialização: Display numérico exibe '0' durante boot e estabiliza em '4' (Ready)",
                    "• Teste funcional de aceleração de 0.8s, 0.6s e 0.5s via Service Desktop",
                    "• Verificação de temperatura térmica das aletas do dissipador de calor",
                    "• Conclusão na OS móvel e entrega do inversor avariado para processo de reparo eMed"
                ],
                "alert": "MISSÃO CUMPRIDA: Rotação suave, silenciosa e com torque dinâmico totalmente restabelecido."
            }
        ]
    },
    {
        "id": "IT_15",
        "code": "IT-TOMO-GE-015",
        "filename": "Video_IT15_Caracterizacao_Mesa_Paciente_e_Tilt_GE.mp4",
        "title": "IT-15: CARACTERIZAÇÃO DA MESA DO PACIENTE & TILT",
        "equip": "Tomógrafos GE BrightSpeed & Brivo CT385",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO DOS TRÊS EIXOS MECÂNICOS",
                "badge": "CINEMÁTICA DA MESA & TILT DO GANTRY",
                "narration": "Bem-vindo à IT-15 de caracterização da mesa do paciente e calibração de inclinação Tilt. O Paulo no Almoxarifado fornece o kit com blocos de caracterização de calha, trena milimétrica e multímetro calibrado.",
                "points": [
                    "• Eixo Longitudinal IN/OUT: Calibração dos passos do encoder e batentes de fim de curso",
                    "• Eixo Vertical UP/DOWN: Calibração de cotas de precisão a 950 mm e 650 mm de altura",
                    "• Eixo Angular (Tilt): Calibração de centro a 0 graus (2.5V DC) e extremos a ±30 graus",
                    "• Obrigatório após substituição de motores da mesa, encoder, potenciômetros ou cabos"
                ],
                "alert": "PRECISÃO MILIMÉTRICA: A reprodutibilidade dos cortes tomográficos depende desta calibração."
            },
            {
                "subtitle": "FASE 2: CARACTERIZAÇÃO LONGITUDINAL & VERTICAL DA MESA",
                "badge": "BLOCOS DA CALHA & COTAS DE ALTURA",
                "narration": "Instale os blocos de caracterização nos trilhos da calha. No Service Desktop, inicie a rotina Table Characterization. O berço avançará automaticamente mapeando o curso útil. Em seguida, meça com trena as cotas de altura para gravar a elevação.",
                "points": [
                    "• Encaixe dos batentes de calibração nas extremidades do curso útil da mesa",
                    "• Execução automática de avanço e recuo com leitura de pulsos do encoder óptico",
                    "• Posicionamento da mesa nas alturas de referência: 950 mm e 650 mm com trena",
                    "• Confirmação dos valores milimétricos no console e gravação na memória NVRAM"
                ],
                "alert": "SEGURANÇA: Mantenha as mãos afastadas das tesouras mecânicas de elevação da mesa."
            },
            {
                "subtitle": "FASE 3: CALIBRAÇÃO DO POTENCIÔMETRO DE TILT A ZERO GRAUS",
                "badge": "ALINHAMENTO DE 2.5V DC & FECHO NA OS",
                "narration": "Com o Gantry nivelado a zero graus, meça com o multímetro a tensão do potenciômetro de inclinação: ela deve ser exatamente 2.50 Volts contínuos. Teste o tilt a mais 30 e menos 30 graus. Finalize a OS no sistema com sucesso.",
                "points": [
                    "• Medição da tensão no pino central do potenciômetro de tilt com multímetro DC",
                    "• Ajuste mecânico fino da engrenagem do potenciômetro até ler exatos 2.500 V DC",
                    "• Teste das chaves limites de inclinação máxima em +30° e -30°",
                    "• Fechamento formal da OS técnica no aplicativo móvel e retorno das ferramentas"
                ],
                "alert": "CONCLUÍDO: Movimentação mecânica e geométrica homologada com tolerância zero de erro."
            }
        ]
    },
    {
        "id": "IT_RXM_003",
        "code": "IT-RXM-SHIM-003",
        "filename": "Video_IT_RXM_SHIM003_Instalacao_Montagem_MobileDaRt_MX8.mp4",
        "title": "IT-RXM-003: INSTALAÇÃO & COMISSIONAMENTO MOBILEDART",
        "equip": "Raio-X Móvel Digital Shimadzu MobileDaRt Evolution MX8",
        "scenes": [
            {
                "subtitle": "FASE 1: RECEBIMENTO, TRAVAS DE TRANSPORTE & REDE ELÉTRICA",
                "badge": "DESEMBALAGEM & TAPS DE REDE",
                "narration": "Atenção equipe de campo eMed! Esta é a IT-RXM-003 para instalação, montagem e comissionamento do raio-X móvel Shimadzu MobileDaRt MX8. Ao desembalar a máquina, desmonte as travas mecânicas de transporte pintadas em vermelho.",
                "points": [
                    "• Remoção das travas de fixação mecânica do braço telescópico e coluna giratória",
                    "• Verificação da tensão da tomada do hospital com multímetro (110V ou 220V AC)",
                    "• Seleção correta dos Taps do transformador de entrada na placa de potência",
                    "• Inspeção visual geral de acabamentos, cabos e integridade do mastro telescópico"
                ],
                "alert": "ATENÇÃO DE REDE: Conectar o equipamento com o tap de 110V numa rede 220V queima os fusíveis."
            },
            {
                "subtitle": "FASE 2: MONTAGEM DO FLAT PANEL DETECTOR & COMUNICAÇÃO",
                "badge": "CHASSI DIGITAL CANON & REDE WI-FI",
                "narration": "Instale a caixa berço para o detector digital Canon CXDI. Conecte o cabo de rede Ethernet dedicado e configure a conexão Wi-Fi de alta velocidade. Valide o sincronismo do sinal de disparo entre o console do operador e o detector.",
                "points": [
                    "• Fixação do compartimento protetor de armazenamento do Flat Panel Detector (FPD Box)",
                    "• Conexão do cabo de recarga e interface do detector Canon CXDI",
                    "• Pareamento via Access Point sem fio de baixa latência embutido no móvel",
                    "• Teste de integração do sinal 'X-Ray Ready' e captura digital instantânea"
                ],
                "alert": "MANUSEIO: O detector digital é de alta sensibilidade; nunca sofra quedas ou choques físicos."
            },
            {
                "subtitle": "FASE 3: WARM-UP DO TUBO, TESTE CLÍNICO & ENTREGA TÉCNICA",
                "badge": "CONDICIONAMENTO & PROTOCOLO DE ENTREGA",
                "narration": "Realize o procedimento de Warm-up de aquecimento gradual do tubo de raios-X em passos de 60, 80, 100 e 120 kV. Realize um disparo de teste na placa padrão, colete a assinatura do médico radiologista e conclua o comissionamento na OS.",
                "points": [
                    "• Condicionamento de filamento e anódio através da rotina escalonada de Warm-up",
                    "• Verificação da colimação luminosa e abertura dos diafragmas de chumbo com trena",
                    "• Teste prático de tração motorizada e paradas nos corredores e leitos de UTI",
                    "• Entrega técnica formal, treinamento básico da enfermagem e encerramento da OS"
                ],
                "alert": "COMISSIONAMENTO COMPLETO: MobileDaRt MX8 entregue com excelência e qualidade eMed."
            }
        ]
    }
]

def get_audio_duration(audio_path):
    cmd = [FFMPEG_BIN, "-i", audio_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in res.stderr.splitlines():
        if "Duration:" in line:
            time_part = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = time_part.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 8.0

async def generate_narration(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE, rate="+4%", pitch="+1Hz")
    await communicate.save(output_path)

def create_slide_image(it_info, scene, output_image_path):
    canvas = Image.new("RGB", (1920, 1080), "#0a1128")
    draw = ImageDraw.Draw(canvas)
    
    # Top Header
    draw.rectangle([0, 0, 1920, 110], fill="#1c2541")
    draw.rectangle([0, 107, 1920, 110], fill="#64dfdf")
    
    try:
        font_logo = ImageFont.truetype("arialbd.ttf", 26)
        font_sub = ImageFont.truetype("arialbd.ttf", 15)
        font_title = ImageFont.truetype("arialbd.ttf", 24)
        font_badge = ImageFont.truetype("arialbd.ttf", 15)
        font_sec = ImageFont.truetype("arialbd.ttf", 22)
        font_body = ImageFont.truetype("arial.ttf", 21)
        font_alert = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_logo = font_sub = font_title = font_badge = font_sec = font_body = font_alert = ImageFont.load_default()
        
    # Logo & Top Labels
    draw.text((45, 22), "eMED", fill="#64dfdf", font=font_logo)
    draw.text((120, 27), f"ELETROMEDICINA | {it_info['code']}", fill="#94a3b8", font=font_sub)
    draw.text((45, 62), it_info["title"], fill="#ffffff", font=font_title)
    
    badge_text = f"★ {scene['badge']}"
    badge_w = len(badge_text) * 9 + 30
    draw.rounded_rectangle([1920 - 45 - badge_w, 32, 1920 - 45, 75], radius=8, fill="#7209b7")
    draw.text((1920 - 45 - badge_w + 15, 45), badge_text, fill="#ffffff", font=font_badge)
    
    # Main Content Area: Subtitle & Equipment
    draw.text((50, 140), f"📍 {scene['subtitle']}", fill="#4cc9f0", font=font_sec)
    draw.text((50, 175), f"⚙️ Equipamento Alvo: {it_info['equip']}", fill="#cbd5e1", font=font_sub)
    
    # Points Card
    card_top = 220
    card_bot = 880
    draw.rounded_rectangle([50, card_top, 1870, card_bot], radius=14, fill="#131e3a", outline="#334155", width=2)
    
    y_text = card_top + 45
    for pt in scene["points"]:
        draw.text((90, y_text), pt, fill="#f8fafc", font=font_body)
        y_text += 70
        
    # Alert Box
    alert_top = 905
    alert_bot = 995
    draw.rounded_rectangle([50, alert_top, 1870, alert_bot], radius=10, fill="#2b1122", outline="#f72585", width=2)
    draw.text((80, alert_top + 32), f"⚠️ ATENÇÃO TÉCNICA: {scene['alert']}", fill="#f72585", font=font_alert)
    
    # Bottom Footer
    draw.rectangle([0, 1020, 1920, 1080], fill="#070c1e")
    draw.text((50, 1040), "SISTEMA EMED • VÍDEO OFICIAL DE SUPORTE EM CAMPO • ENGENHARIA CLÍNICA", fill="#64748b", font=font_sub)
    draw.text((1600, 1040), "PROCEDIMENTO PADRÃO", fill="#64dfdf", font=font_sub)
    
    canvas.save(output_image_path, quality=95)

async def build_video_for_it(it_info):
    print(f"\n=======================================================")
    print(f"🎬 GERANDO VÍDEO PARA: {it_info['code']} - {it_info['title']}")
    print(f"=======================================================")
    
    clip_files = []
    
    for s_idx, scene in enumerate(it_info["scenes"]):
        scene_prefix = f"{it_info['id']}_scene_{s_idx+1}"
        audio_path = os.path.join(TEMP_DIR, f"{scene_prefix}.mp3")
        image_path = os.path.join(TEMP_DIR, f"{scene_prefix}.png")
        clip_path = os.path.join(TEMP_DIR, f"{scene_prefix}.mp4")
        
        # 1. Áudio Narração
        print(f"  • Gravando áudio TTS (Cena {s_idx+1}/{len(it_info['scenes'])})...")
        await generate_narration(scene["narration"], audio_path)
        duration = get_audio_duration(audio_path) + 0.6
        
        # 2. Imagem / Slide
        create_slide_image(it_info, scene, image_path)
        
        # 3. Compilação do Clip
        cmd_clip = [
            FFMPEG_BIN, "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-shortest",
            clip_path
        ]
        res = subprocess.run(cmd_clip, capture_output=True, text=True)
        if res.returncode != 0:
            print("Erro no ffmpeg:", res.stderr)
            return None
            
        clip_files.append(clip_path)
        
    # Concatenação final
    concat_list_path = os.path.join(TEMP_DIR, f"concat_{it_info['id']}.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for c in clip_files:
            f.write(f"file '{os.path.abspath(c)}'\n")
            
    final_output = os.path.join(VIDEOS_DIR, it_info["filename"])
    cmd_concat = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        final_output
    ]
    res_con = subprocess.run(cmd_concat, capture_output=True, text=True)
    if res_con.returncode != 0:
        print("Erro na concatenação:", res_con.stderr)
        return None
        
    file_size_mb = os.path.getsize(final_output) / (1024 * 1024)
    print(f"✅ Vídeo gerado com sucesso: {it_info['filename']} ({file_size_mb:.2f} MB)")
    return final_output

async def main():
    print("=== INICIANDO PRODUÇÃO EM LOTE DOS VÍDEOS (LOTE 2 - ITs 06 a 15 + RXM 003) ===")
    total = len(ITS_DEFINITIONS_LOTE_2)
    sucessos = []
    
    for idx, it_info in enumerate(ITS_DEFINITIONS_LOTE_2, 1):
        print(f"\nProgresso Geral: {idx}/{total}")
        res = await build_video_for_it(it_info)
        if res:
            sucessos.append(res)
            
    print("\n=======================================================")
    print(f"🎉 PRODUÇÃO CONCLUÍDA: {len(sucessos)}/{total} vídeos criados com sucesso!")
    print(f"Local: {VIDEOS_DIR}")
    print("=======================================================")

if __name__ == "__main__":
    asyncio.run(main())
