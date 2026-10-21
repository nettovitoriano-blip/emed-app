import os
import sys
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = r"C:\Users\vitor\OneDrive\Desktop\Sistema Emed"
VIDEOS_DIR = os.path.join(BASE_DIR, "Videos_Treinamento_ITs")
TEMP_DIR = os.path.join(BASE_DIR, "temp_batch_its")
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

FFMPEG_BIN = r"C:\Users\vitor\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
VOICE = "pt-BR-AntonioNeural"

# Definição das ITs com roteiros técnicos passo a passo para apoio em campo
ITS_DEFINITIONS = [
    {
        "id": "IT_02",
        "code": "IT-TOMO-GE-002",
        "filename": "Video_IT02_Manutencao_Preventiva_BrightSpeed.mp4",
        "title": "IT-02: MANUTENÇÃO PREVENTIVA PROGRAMADA (PM)",
        "equip": "Tomógrafo GE BrightSpeed Lite & Select Series",
        "scenes": [
            {
                "subtitle": "FASE 1: ESCOPO DO PM & KITS DO ALMOXARIFADO",
                "badge": "PREVENTIVA PROGRAMADA (Schedules A, B, C e D)",
                "narration": "Olá, técnico da eMed! Bem-vindo à Instrução de Trabalho IT-02 de Manutenção Preventiva para tomógrafos GE BrightSpeed. O Paulo no Almoxarifado já separa para si o kit de graxa Klüber, Kimwipes, paquímetro digital para escovas e aspirador com filtro HEPA.",
                "points": [
                    "• Cronograma: Schedule A (Trimestral), B (Semestral), C (9 Meses) e D (Anual Completo)",
                    "• Materiais: Graxa Klüber GL261, Álcool Isopropílico 99.8%, Kimwipes e Paquímetro",
                    "• Aspirador HEPA Especial: Nunca use ar comprimido nas pistas do Slip Ring",
                    "• Acionamento Automático do Paulo no Almoxarifado para separação dos consumíveis"
                ],
                "alert": "RISCO: Partículas de grafite dispersas por ar comprimido provocam curtos letais nas placas."
            },
            {
                "subtitle": "FASE 2: PROTOCOLO LOTO & SEGURANÇA ELÉTRICA",
                "badge": "DESENERGIZAÇÃO & TRAVAMENTO LOTO",
                "narration": "Antes de remover qualquer tampa do Gantry, desative as chaves Axial Drive Enable, HVDC Enable e disjuntor de 120 Volts. Aplique o cadeado LOTO no disjuntor geral da sala para total segurança mecânica e elétrica.",
                "points": [
                    "• Chaves do Gantry: Axial Drive -> OFF | HVDC -> OFF | 120VAC -> OFF",
                    "• Desarme do Disjuntor Principal na PDU ou Quadro de Força do Hospital",
                    "• Aplicação de cadeado LOTO e etiqueta de manutenção técnica eMed",
                    "• Teste de Tensão Zero com Multímetro Cat III antes de encostar nas peças"
                ],
                "alert": "LOTO OBRIGATÓRIO: A rotação acidental do Gantry a alta velocidade é fatal."
            },
            {
                "subtitle": "FASE 3: SLIP RING & MEDIÇÃO DAS ESCOVAS DE CARVÃO",
                "badge": "INSPEÇÃO CRÍTICA DO SLIP RING",
                "narration": "Aspire toda a poeira de carvão do Slip Ring com bocal plástico. Em seguida, utilize o paquímetro digital para medir as escovas. Escovas com comprimento inferior ao limite mínimo devem ser substituídas imediatamente.",
                "points": [
                    "• Aspiração a vácuo com filtro HEPA ao redor das pistas e suportes de escovas",
                    "• Limpeza das pistas condutoras com Kimwipes embebidos em Álcool Isopropílico",
                    "• Medição do comprimento das escovas de sinal e potência com paquímetro digital",
                    "• Substituição obrigatória caso o desgaste ultrapasse o limite de segurança GE"
                ],
                "alert": "TOLERÂNCIA: Pistas riscadas ou escovas curtas geram ruído na imagem e erro de comunicação."
            },
            {
                "subtitle": "FASE 4: LUBRIFICAÇÃO DO ROLAMENTO PRINCIPAL & QA FINAL",
                "badge": "LUBRIFICAÇÃO & TESTE DE ÁGUA",
                "narration": "Aplique a graxa especificada com a pistola no rolamento principal do Gantry, girando manualmente para distribuição uniforme. Finalize com o teste de garantia da qualidade no phantom de água, validando zero mais ou menos quatro unidades Hounsfield.",
                "points": [
                    "• Engraxamento com pistola: graxa Klüber Microlube GL 261 no rolamento",
                    "• Rotação manual suave do Gantry de 360 graus para distribuição homogênea",
                    "• Posicionamento do Phantom GE QA na mesa com suporte oficial",
                    "• Varredura Axial de Controle: Água = 0 ± 4 HU | Ruído Desvio Padrão dentro do limite"
                ],
                "alert": "VALIDAÇÃO: Registrar o laudo de QA na OS e coletar a assinatura do cliente no celular."
            }
        ]
    },
    {
        "id": "IT_03",
        "code": "IT-TOMO-GE-003",
        "filename": "Video_IT03_Troca_Tubo_BrightSpeed.mp4",
        "title": "IT-03: TROCA DE TUBO DE RAIO-X & ALINHAMENTO ÓPTICO",
        "equip": "Tomógrafo GE BrightSpeed Series",
        "scenes": [
            {
                "subtitle": "FASE 1: PREPARAÇÃO DA CARGA & GUINCHO MECÂNICO",
                "badge": "FERRAMENTAL PESADO & LOGÍSTICA",
                "narration": "Esta é a IT-03 para substituição do Tubo de Raios-X no GE BrightSpeed. Para esta missão pesada, confirme com o Paulo no Almoxarifado o envio da talha guincho portátil, cabo de alta tensão, torquímetro e phantoms de calibração.",
                "points": [
                    "• Carga do Almoxarifado: Tubo de Raio-X Novo, Talha Guindaste e Chave Torquímetro",
                    "• Posicione o Gantry a 180 graus (Tubo na parte superior) para montagem do guincho",
                    "• Instale a trava mecânica de segurança (Pin Lock) para impedir rotação acidental",
                    "• Confirme a entrega do kit pelo Paulo com status ENTREGUE AO TÉCNICO"
                ],
                "alert": "PESO ELEVADO: O tubo pesa mais de 100 kg. Nunca faça o içamento sem a talha de suporte."
            },
            {
                "subtitle": "FASE 2: DESCONEXÕES DE ALTA TENSÃO & DRENAGEM TÉRMICA",
                "badge": "DESCONEXÃO HV & CIRCUITO DE ÓLEO",
                "narration": "Desconecte os cabos de alta tensão Catódio e Anódio, inspecionando pinos e orelhas de vedação. Drene o circuito de arrefecimento do trocador de calor e solte os parafusos estruturais de fixação do tubo.",
                "points": [
                    "• Remoção cuidadosa dos conectores federais de alta tensão (Cabo C e Cabo A)",
                    "• Desconexão dos engates rápidos do trocador de calor de óleo (Heat Exchanger)",
                    "• Soltura dos quatro parafusos estruturais com torquímetro calibrado",
                    "• Içamento do tubo antigo para fora do gantry e descida suave até a caixa de transporte"
                ],
                "alert": "VEDAÇÃO: Inspecione as borrachas O-rings dos conectores HV para evitar fuga dielétrica."
            },
            {
                "subtitle": "FASE 3: INSTALAÇÃO DO NOVO TUBO & CALIBRAÇÃO BEAM-ON-WINDOW",
                "badge": "CALIBRAÇÃO ÓPTICA DO FEIXE",
                "narration": "Com o novo tubo içado e parafusado ao torque de 55 Newton-metro, execute o alinhamento óptico do feixe na janela do colimador, conhecido como Beam on Window. Ajuste os calços micrométricos até a centralização perfeita.",
                "points": [
                    "• Fixação do tubo novo no torque padrão de 55 N·m em padrão cruzado",
                    "• Conexão dos cabos HV com pasta de silicone dielétrica limpa",
                    "• Alinhamento Beam-on-Window (BOW) no Service Desktop para centrar o feixe",
                    "• Ajuste mecânico dos calços de inclinação Z e X até leitura do detector estabilizar"
                ],
                "alert": "PRECISÃO: Erros de BOW produzem artefatos de anel (ring artifacts) nas imagens de pacientes."
            },
            {
                "subtitle": "FASE 4: CONDICIONAMENTO, RESET TNT & CONCLUSÃO DA OS",
                "badge": "WARM-UP, FILAMENTO & FECHO DA OS",
                "narration": "Execute o aquecimento gradual do tubo novo com disparos crescentes de 80 a 140 kV. Efetue o reset dos contadores TnT no Linux. Se a proposta foi aprovada, selecione Instalação Definitiva na OS para dar baixa no estoque e gerar cobrança.",
                "points": [
                    "• Procedimento de Seasoning / Tube Warm-up progressivo de kV e mA",
                    "• Calibração de corrente de filamento e ganhos do detector (mA Calibration)",
                    "• Reset do contador de tempo e disparos do tubo no console (TnT Reset)",
                    "• Finalização na OS com Baixa Definitiva e encaminhamento automático para Faturamento"
                ],
                "alert": "BAIXA AUTOMÁTICA: O sistema atualiza o estoque e avisa o financeiro para emissão da NF-e."
            }
        ]
    },
    {
        "id": "IT_04",
        "code": "IT-TOMO-GE-004",
        "filename": "Video_IT04_Balanceamento_Gantry_GE.mp4",
        "title": "IT-04: BALANCEAMENTO ESTÁTICO & DINÂMICO DO GANTRY",
        "equip": "Tomógrafos GE BrightSpeed Lite & Brivo CT385",
        "scenes": [
            {
                "subtitle": "FASE 1: CONCEITO & LIMITE CRÍTICO DE TORQUE",
                "badge": "EQUILÍBRIO MECÂNICO DO GANTRY",
                "narration": "Bem-vindo à IT-04 de Balanceamento de Gantry. Sempre que trocamos o tubo de raios-X, colimador ou componentes rotativos, o centro de massa é alterado. O limite máximo de desbalanceamento estático permitido pela GE é de 160 Newton-centímetro.",
                "points": [
                    "• O balanceamento incorreto destrói o rolamento principal e quebra correias de tração",
                    "• Ferramenta obrigatória: Chave dinamométrica de precisão com ponteiro de torque",
                    "• Tolerância Estática Máxima GE: Desbalanceamento menor que 160 N·cm",
                    "• Tolerância Dinâmica: Vibração do acelerômetro abaixo de 0.05 G na rotação máxima"
                ],
                "alert": "CRÍTICO: Um gantry girando a 0.5 segundos por volta sem balancear pode romper componentes."
            },
            {
                "subtitle": "FASE 2: MEDIÇÃO ESTÁTICA EM 4 QUADRANTES",
                "badge": "AFERIÇÃO DE TORQUE NOS 4 PONTOS",
                "narration": "Desacople a correia do motor de rotação. Posicione o rotor sucessivamente nas posições de 12 horas, 3 horas, 6 horas e 9 horas. Com a ferramenta dinamométrica no eixo central, meça a força necessária para iniciar o movimento em cada quadrante.",
                "points": [
                    "• Remoção da correia de tração principal para rotação totalmente livre do tambor",
                    "• Medição do torque resistente em 0°, 90°, 180° e 270°",
                    "• Cálculo do desequilíbrio: diferença entre os pontos mais pesados e mais leves",
                    "• Identificação do quadrante onde os pesos compensadores devem ser adicionados"
                ],
                "alert": "SEGURANÇA: Mantenha as mãos afastadas das frestas do tambor durante a medição livre."
            },
            {
                "subtitle": "FASE 3: ADIÇÃO DE PESOS COMPENSADORES & TESTE DINÂMICO",
                "badge": "AJUSTE FINO & ROTAÇÃO TOTAL",
                "narration": "Adicione as placas de contrapeso calibradas nos trilhos do lado oposto ao tubo, apertando com o torque correto. Recoloque a correia, reative o inversor e execute o teste dinâmico de centrifugação no Service Desktop até 120 rotações por minuto.",
                "points": [
                    "• Instalação de contrapesos de tungstênio/chumbo nas posições angulares calculadas",
                    "• Aperto dos parafusos dos contrapesos com trava química de rosca média",
                    "• Reinstalação e tensionamento correto da correia dentada de rotação",
                    "• Rotação gradual de 0.8s, 0.6s e 0.5s sem vibração anormal ou ruído de rolamento"
                ],
                "alert": "VALIDAÇÃO: Registrar no laudo da OS o valor final de torque estático inferior a 160 N·cm."
            }
        ]
    },
    {
        "id": "IT_05",
        "code": "IT-TOMO-GE-005",
        "filename": "Video_IT05_Diagnostico_Ajuste_SlipRing_GE.mp4",
        "title": "IT-05: DIAGNÓSTICO, LIMPEZA & AJUSTE DO SLIP RING",
        "equip": "Tomógrafos GE BrightSpeed & Brivo CT385",
        "scenes": [
            {
                "subtitle": "FASE 1: DIAGNÓSTICO DE RUÍDO & COMUNICAÇÃO ÓPTICA",
                "badge": "ANÉIS CONDUTORES & DADOS",
                "narration": "Esta é a IT-05 para manutenção do anel coletor Slip Ring. Falhas de comunicação no Gantry, erros de transceptor óptico e ruído de alta tensão geralmente decorrem de poeira de carvão acumulada entre as trilhas concêntricas.",
                "points": [
                    "• O Slip Ring transmite alta tensão, 120 VAC, terra e dados ópticos gigabit em movimento",
                    "• Sintomas de falha: Interrupção de varreduras, erros de transceptor de fibra e artefatos",
                    "• Kit solicitado ao Paulo: Pano Kimwipes, Álcool Isopropílico e aspirador hospitalar HEPA",
                    "• Desenergização obrigatória antes de tocar em qualquer trilha condutora"
                ],
                "alert": "PROIBIDO: Nunca use solventes aromáticos ou desengripantes comuns sobre as trilhas."
            },
            {
                "subtitle": "FASE 2: LIMPEZA DAS TRILHAS & AJUSTE DE PRESSÃO DAS ESCOVAS",
                "badge": "HIGIENIZAÇÃO & CALIBRAÇÃO DE PRESSÃO",
                "narration": "Limpe as trilhas de latão e ouro com álcool isopropílico até que os panos saiam brancos sem vestígios pretos. Verifique a pressão das molas dos blocos de escovas com dinamômetro de tração, garantindo contato firme sem desgaste excessivo.",
                "points": [
                    "• Limpeza manual detalhada de cada canal de latão girando o rotor lentamente",
                    "• Inspeção com lanterna para verificar riscos profundos ou marcas de centelhamento",
                    "• Medição da força das molas das escovas: deve estar entre 1.5 e 2.0 Newtons",
                    "• Substituição dos blocos de escovas desgastados com parafusos de retenção novos"
                ],
                "alert": "TOLERÂNCIA: Pressão fraca causa faíscas elétricas; pressão alta desgasta a trilha prematuramente."
            },
            {
                "subtitle": "FASE 3: TESTE DE FIBRA ÓPTICA & CONCLUSÃO NA OS",
                "badge": "TRANSMISSÃO DE DADOS & FECHO",
                "narration": "Limpe as lentes dos transceptores ópticos sem fio do canal de dados de imagem com haste de algodão limpa. Execute o teste de loopback no software GE e conclua a OS, devolvendo as ferramentas sobressalentes ao Almoxarifado.",
                "points": [
                    "• Limpeza cuidadosa do anel de transmissão óptica de dados do DAS",
                    "• Teste de taxa de erro de bits (Bit Error Rate - BER) no Service Desktop",
                    "• Varredura contínua de 50 rotações confirmando zero perda de pacotes de dados",
                    "• Finalização na OS no celular e baixa dos materiais com o Paulo no sistema"
                ],
                "alert": "SUCESSO: Equipamento liberado para rotina clínica com estabilidade total de comunicação."
            }
        ]
    },
    {
        "id": "IT_RXM_001",
        "code": "IT-RXM-SHIM-001",
        "filename": "Video_IT_RXM_SHIM001_Descarga_Capacitores_MobileDaRt_MX8.mp4",
        "title": "IT-RXM-001: DESCARGA SEGURA DE CAPACITORES & PM",
        "equip": "Raio-X Móvel Digital Shimadzu MobileDaRt Evolution MX8 & MX9",
        "scenes": [
            {
                "subtitle": "FASE 1: PROTOCOLO DE VIDA OU MORTE (> 100V DC RESIDUAIS)",
                "badge": "SEGURANÇA ELÉTRICA CRÍTICA",
                "narration": "Atenção máxima, técnico da eMed! Esta é a IT-RXM-001 do Shimadzu MobileDaRt MX8. Mesmo com a chave geral desligada e disjuntor em OFF, os capacitores do gerador de 32 kilowatts permanecem carregados com alta tensão letal. Siga rigorosamente este procedimento.",
                "points": [
                    "• Risco de Choque Fatal por tensão acumulada no banco de capacitores (> 100V DC)",
                    "• Desligue a chave de ignição Key Switch e desarme o disjuntor principal Main Breaker",
                    "• Remova as tampas de proteção inferiores com chave Allen isolada",
                    "• Localize a placa eletrônica MUX CAPACITOR BOARD"
                ],
                "alert": "PERIGO DE MORTE: Nunca toque em nenhum terminal elétrico sem descarregar o banco primeiro."
            },
            {
                "subtitle": "FASE 2: CONEXÃO NO PLUGUE DE DESCARGA & RESISTORES DE DRENAGEM",
                "badge": "ACIONAMENTO DO DISCHARGE SWITCH",
                "narration": "Desconecte o cabo interno do conector CN2 Normal e conecte-o no conector CN1 Discharge. O LED vermelho acenderá indicando carga presente. Mova a chave Discharge Switch para a posição superior e aguarde 5 minutos completos.",
                "points": [
                    "• Desconectar cabo CN1/CN2 do conector CN2 (NORMAL)",
                    "• Inserir o cabo no conector CN1 (DISCHARGE)",
                    "• LED Indicador Vermelho acende acusando carga residual nos capacitores",
                    "• Acionar a chave Discharge Switch para a posição SUPERIOR (ON/UP)",
                    "• Aguardar no mínimo 5 minutos cronometrados para queima térmica da energia nos resistores"
                ],
                "alert": "TEMPO DE ESPERA: Os resistores internos R3 e R4 aquecem durante a queima da carga."
            },
            {
                "subtitle": "FASE 3: AFERIÇÃO COM MULTÍMETRO & CRITÉRIO < 1.0V DC",
                "badge": "LIBERAÇÃO DE TENSÃO ZERO",
                "narration": "Com o multímetro na escala de corrente contínua, meça a tensão entre os pinos de teste CP1 e CP2 da placa MUX CAPACITOR. O critério obrigatório de segurança é tensão inferior a 1.0 Volt DC. Só então o equipamento está liberado para manutenção.",
                "points": [
                    "• Multímetro na escala DC: ponta preta no CP2, ponta vermelha no CP1",
                    "• Critério Obrigatório: Leitura deve ser estritamente inferior a 1,0 Volt DC",
                    "• Diagnóstico de erros comuns: F15 (queda de tensão de tubo), F24 (sobrecorrente filamento)",
                    "• Diagnóstico dos motores de tração: d24 (motor direito) e d25 (motor esquerdo)"
                ],
                "alert": "REGRA DE OURO: Se a tensão for maior que 1.0V, aguarde mais 3 minutos e repita a medição."
            },
            {
                "subtitle": "FASE 4: TESTES MOTORES, BATERIAS & FECHAMENTO NA OS",
                "badge": "TESTE DE TRAÇÃO & RETORNO AO ESTOQUE",
                "narration": "Inspecione a tensão individual das baterias de 12 Volts. Teste a tração motorizada e o freio eletromagnético. Na conclusão do serviço, finalize a OS no sistema e confirme com o Paulo no Almoxarifado o retorno de todas as ferramentas calibradas.",
                "points": [
                    "• Teste individual de carga das baterias com analisador sob descarga",
                    "• Teste dos comandos de tração na manopla frente e ré com parada de emergência no para-choque",
                    "• Reversão do cabo CN1 de volta ao conector CN2 NORMAL e travamento das tampas",
                    "• Registro na OS e devolução das ferramentas calibradas ao Paulo no Almoxarifado"
                ],
                "alert": "CONCLUSÃO: O MobileDaRt MX8 fica 100% operacional, seguro e documentado no Sistema eMed."
            }
        ]
    },
    {
        "id": "IT_RXM_002",
        "code": "IT-RXM-SHIM-002",
        "filename": "Video_IT_RXM_SHIM002_Calibracao_Manopla_Sensor_Braco_MX8.mp4",
        "title": "IT-RXM-002: CALIBRAÇÃO DA MANOPLA COM BALANÇA (FSR)",
        "equip": "Raio-X Móvel Digital Shimadzu MobileDaRt MX8",
        "scenes": [
            {
                "subtitle": "FASE 1: OBJETIVO & FERRAMENTA BALANÇA DIGITAL",
                "badge": "CALIBRAÇÃO DE TRAÇÃO ASSISTIDA",
                "narration": "Nesta IT-02 do Shimadzu MobileDaRt MX8, você aprenderá a calibrar os sensores de força FSR da manopla motorizada e o sensor de repouso do braço. Para esta calibração, separe com o Paulo no Almoxarifado o dinamômetro digital de gancho.",
                "points": [
                    "• Objetivo: Regular a resposta de aceleração frente e ré da manopla assistida",
                    "• O equipamento pesa 450 kg: sensores descalibrados causam arrancadas bruscas ou travamento",
                    "• Ferramental do Almoxarifado: Balança/Dinamômetro digital de gancho e chave Allen 3mm",
                    "• Posição de teste: Viatura nivelada e freios mecânicos liberados"
                ],
                "alert": "CUIDADO: Se o sensor estiver desregulado, o operador não consegue empurrar o móvel nos corredores."
            },
            {
                "subtitle": "FASE 2: ACESSO AO MODO DE SERVIÇO & AJUSTE FSR",
                "badge": "MODO TÉCNICO & FORÇA DE RESPOSTA",
                "narration": "Ligue o equipamento segurando os botões de serviço no painel para entrar no modo de calibração FSR. Prenda o dinamômetro na empunhadura e aplique tração controlada para frente até registrar 2.0 quilogramas de força.",
                "points": [
                    "• Entrada no Modo de Manutenção através da chave de bypass na placa CPU",
                    "• Fixação do dinamômetro de gancho exatamente no ponto central da empunhadura",
                    "• Aplicação de tração de avanço calibrada de 20 Newtons (2,0 kgf)",
                    "• Gravação do limiar analógico A/D no display do gerador pressionando STORE"
                ],
                "alert": "PRECISÃO: Ambos os sensores direito e esquerdo devem apresentar resposta idêntica."
            },
            {
                "subtitle": "FASE 3: CALIBRAÇÃO DO SENSOR DO BRAÇO NO CATCHER",
                "badge": "INTERLOCK DE BLOQUEIO DE TRAÇÃO",
                "narration": "O sensor óptico do braço no berço de repouso Catcher impede que o equipamento ande em alta velocidade com o braço articulado solto. Ajuste a distância do sensor indutivo para 1.5 milímetros e valide a troca de marcha de transporte para posicionamento.",
                "points": [
                    "• Ajuste da folga mecânica do sensor do braço no suporte de descanso (1,5 ± 0,3 mm)",
                    "• Com o braço travado no catcher: velocidade de transporte alta permitida até 5 km/h",
                    "• Com o braço fora do descanso: interlock reduz a tração para velocidade lenta de 1 km/h",
                    "• Teste da botoeira antiesmagamento no para-choque frontal com reversão automática"
                ],
                "alert": "SEGURANÇA HOSPITALAR: O travamento da velocidade alta fora do catcher evita tombamento do mastro."
            }
        ]
    },
    {
        "id": "IT_RXD_001",
        "code": "IT-RXD-NEU-001",
        "filename": "Video_IT_RXD_NEU001_Instalacao_Software_DR_NeuVision550M.mp4",
        "title": "IT-RXD-001: INSTALAÇÃO & CONFIGURAÇÃO DR NEUVISION 550M",
        "equip": "Raio-X Digital Neusoft NeuVision 550M & 550M Plus",
        "scenes": [
            {
                "subtitle": "FASE 1: ARQUITETURA DR, GERADOR SEDECAL & DETECTOR CANON",
                "badge": "SISTEMAS DIGITAIS RADIOLÓGICOS",
                "narration": "Bem-vindo à IT-01 do Raio-X Digital Neusoft NeuVision 550M. Este sistema integra a Workstation de aquisição, gerador de alta frequência Sedecal via cabo serial RS-232 e detector Flat Panel Canon via rede Wi-Fi dedicada.",
                "points": [
                    "• Componentes: Console Neusoft NeuVision, Gerador Sedecal SHF e Flat Panel Canon CXDI",
                    "• Rede Local dedicada: IP fixo da Workstation 192.168.100.10 e Máscara 255.255.255.0",
                    "• Comunicação Gerador: Cabo serial RS-232 no padrão 9600 bps na porta COM1",
                    "• Conexão Wi-Fi Canon: Access Point industrial com SSID oculto e criptografia WPA2"
                ],
                "alert": "REDE CRÍTICA: Nunca conecte o cabo de rede do hospital na mesma placa de rede dos detectores."
            },
            {
                "subtitle": "FASE 2: INSTALAÇÃO DO SOFTWARE DE AQUISIÇÃO & DRIVERS CANON",
                "badge": "WORKSTATION & DRIVER CXDI",
                "narration": "Instale os drivers CXDI da Canon no Windows e configure o software NeuVision. No arquivo de calibração, importe os mapas de defeitos de pixel e mapas de ganho fornecidos no pen drive oficial de calibração da fábrica.",
                "points": [
                    "• Instalação limpa dos utilitários CXDI Driver Setup com privilégios de Administrador",
                    "• Importação dos arquivos .DAT de calibração de fábrica do chassi digital",
                    "• Configuração do protocolo DICOM Print, Storage e Worklist conectado ao PACS do hospital",
                    "• Teste de sincronismo de disparo: Interlock de prontidão e sinal de integração de raio-X"
                ],
                "alert": "MAPA DE PIXELS: Sem os arquivos de correção de ganho, a imagem apresentará linhas mortas."
            },
            {
                "subtitle": "FASE 3: CALIBRAÇÃO DE DARK E FLAT FIELD & QA FINAL",
                "badge": "TESTE DE IMAGEM & ENTREGA",
                "narration": "Execute a calibração de campo escuro (Dark Current) sem exposição e calibração de campo claro (Flat Field) com disparo de 70 kV a 1.5 metros de distância. Conclua a OS com o cliente e registre a entrega técnica no Sistema eMed.",
                "points": [
                    "• Calibração Dark: aquisição de 5 frames com o feixe desligado para compensação térmica",
                    "• Calibração Flat Field: exposição homogênea com filtro de 20mm de Alumínio no colimador",
                    "• Aferição da resolução espacial com padrão de linhas: mínimo 3.1 pares de linhas por mm",
                    "• Conclusão da OS no tablet, assinatura do físico responsável e baixa no sistema"
                ],
                "alert": "HOMOLOGADO: O sistema NeuVision 550M é entregue com qualidade diagnóstica padrão ouro."
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
    print("=== INICIANDO PRODUÇÃO EM LOTE DOS VÍDEOS DE SUPORTE ÀS ITs ===")
    total = len(ITS_DEFINITIONS)
    sucessos = []
    
    for idx, it_info in enumerate(ITS_DEFINITIONS, 1):
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
