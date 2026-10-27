# INSTRUÇÃO DE TRABALHO: TROCA DE TUBO DE RAIO-X & CALIBRAÇÃO INTEGRAL

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-001`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## 1. Objetivo e Escopo

Esta Instrução de Trabalho (IT) padroniza o procedimento de **substituição mecânica, elétrica e calibração de pós-instalação do tubo de Raio-X** no tomógrafo computadorizado **GE Brivo CT385 Series**, garantindo:
1. Integridade física dos técnicos e operadores contra choques elétricos de alta tensão (> 140 kV) e acidentes com o conjunto giratório do gantry;
2. Preservação dos cabos e receptáculos de alta tensão contra quebras e descargas dielétricas (arcing);
3. Execução estrita dos torques mecânicos e alinhamentos ópticos para evitar vibrações e desbalanceamento rotacional a altas velocidades;
4. Realização da esteira completa de calibrações de filamento, detectores e controle de qualidade (QA) para liberação diagnóstica.

* **Tempo Estimado:** 1 hora preliminar / 7 horas de execução, alinhamentos e calibrações.
* **Mão de Obra Mínima:** 2 Técnicos Especializados em Tomografia Computadorizada.

---

## 2. Ferramentas, Instrumentos Especiais & Consumíveis

> [!IMPORTANT]
> O uso de ferramentas inadequadas ou reaproveitamento de parafusos de fixação é estritamente proibido pela GE Healthcare, sob risco de desprendimento do tubo em rotação centrífuga e perda total do gantry.

### 2.1. Ferramental Especial (com Part Number Oficial GE)
| Instrumento / Dispositivo Especial | Part Number GE | Quantidade | Finalidade Técnica |
| :--- | :---: | :---: | :--- |
| **Braço de Içamento (Hoist Arm)** | `2282509-2` | 1 un. | Estrutura de sustentação da talha de içamento |
| **Tubo Longo de Fixação (Hoist Long Tube)** | `2282510-2` | 1 un. | Suporte de engate da talha no topo do gantry |
| **Talha de Corrente (Chain Block Assembly)** | `2268140` | 1 un. | Içamento e descida controlada do tubo (peso ~100 kg) |
| **Kit Descarregador de Alta Tensão (HV Bleeder)** | `2345332` | 1 un. | Aterramento e drenagem de cargas residuais dos cabos |
| **Suporte do Dispositivo de Alinhamento (JIG Holder)** | `5371128` | 1 un. | Fixação do JIG óptico na abertura do gantry |
| **Dispositivo de Alinhamento Óptico (Alignment JIG)** | `5371129` | 1 un. | Alinhamento de feixe BOW, CBF e POR |
| **Relógio Comparador com Base Magnética** | Comercial | 2 un. | Medição milimétrica de folgas e deflexões no gantry |
| **Chave Especial para Anel de Alta Tensão (Spanner Wrench)** | Comercial | 1 un. | Aperto e desaperto do anel de vedação dos cabos HV |
| **Torquímetro de Precisão (10 a 100 N·m)** | Calibrado | 1 un. | Aperto controlado dos parafusos M10 e M12 |

### 2.2. Peças de Reposição e Parafusos Críticos
* **Tubo de Raio-X GE Brivo CT385:** P/N `5363417` (comprado novo / revisado com certificado).
* **Parafusos da Placa de Fixação:** 4 parafusos **M10 x 1.5 x 20 mm** novos (**Torque: 38,4 N·m**).
* **Parafusos de Fixação do Tubo ao Gantry:** 4 parafusos **M12 x 1.75 x 40 mm** novos (**Torque: 66,4 N·m**).
* *REGRA DE OURO:* Os 8 parafusos retirados do tubo velho **DEVEM SER DESCARTADOS IMEDIATAMENTE**. Nunca reutilize parafusos submetidos à fadiga mecânica.

### 2.3. Consumíveis Obrigatórios
* **Óleo Isolante de Alta Tensão (Tube Oil):** Óleo mineral dielétrico desaerado para preenchimento dos poços dos conectores de alta tensão.
* **Abraçadeiras Plásticas (Tie-wraps):** Resistentes a temperatura para fixação dos cabos HV na rotação original.
* **Lenços de Limpeza de Precisão (Kimwipes):** Livres de fiapos e resíduos para secagem dos conectores e poços.

---

## 3. Protocolos de Segurança & Bloqueio LOTO (Lockout / Tagout)

> [!CAUTION]
> **RISCO DE CHOQUE ELÉTRICO LETAL (> 140 kV) E ESMAGAMENTO MECÂNICO**
> 1. Desligue a alimentação do disjuntor principal da sala antes de tocar em qualquer borne de potência.
> 2. Aguarde no mínimo **15 minutos** após o último disparo de Raio-X para dissipação de calor e descarga dos capacitores do tanque de alta tensão.
> 3. É **OBRIGATÓRIO** travar o gantry com o **Pino de Trava de Rotação (Rotational Lock Pin)** antes de soltar qualquer parafuso do tubo.
> 4. **Raio Mínimo de Curvatura dos Cabos HV:** **6,35 cm (2,5")**. Dobras acentuadas danificam a blindagem interna e provocam perfuração dielétrica.

---

## 4. Passo a Passo Operacional (Execução em Campo)

### FASE 1: Entrada Prévia de Dados no Software (Crítico)
> [!WARNING]
> Esta etapa deve ser executada obrigatoriamente **ANTES** da remoção física do tubo. Se a entrada for feita após a troca física, o software da GE assume temperatura interna máxima e bloqueia o sistema por várias horas!

1. No console de controle, abra o **[SERVICE DESKTOP]**.
2. Navegue até: `[REPLACEMENT]` -> `[NEW TUBE CONFIG]`.
3. Selecione o motivo da falha (*Tube Unit Failure Code*).
4. Digite com atenção o **Insert Serial #** e o **Housing Serial #** impressos na placa de identificação do novo tubo.
5. Clique em **OK** para salvar os parâmetros na EEPROM do sistema.

---

### FASE 2: Preparação e Desmontagem Mecânica
1. **Posicionamento da Mesa:** Abaixe a mesa de exames até o fim de curso inferior.
2. **Remoção de Carenagens:** Remova a carenagem lateral esquerda do gantry para acessar o painel de serviço.
3. **Desligamento das Chaves de Serviço:** No painel de chaves de serviço do gantry (*Service Switch Panel*), desligue:
   * `AXIAL DRIVE` -> OFF
   * `HVDC` -> OFF
   * `120VAC` -> OFF
4. Remova as carenagens frontal, superior e laterais do gantry e a tampa do pedal da mesa.
5. Ligue temporariamente a chave `120VAC` e rotacione o gantry manualmente/via controle até que o tubo de Raio-X fique posicionado na **posição das 3 horas (3 o'clock)**.
6. **Inserir o Pino de Trava de Rotação (Rotational Lock Pin)** no disco do gantry. Em seguida, desligue a chave `120VAC`.
7. **Montagem da Talha:**
   * Encaixe o tubo longo (*Hoist Long Tube P/N 2282510-2*) e o braço de sustentação (*Hoist Arm P/N 2282509-2*).
   * Conecte a corrente da talha (*Chain Block P/N 2268140*) nos olhais do tubo de Raio-X e puxe a corrente até ficar totalmente tensionada (sem folga).

---

### FASE 3: Desconexão Elétrica e Remoção do Tubo Usado
1. Desconecte o cabo amarelo de alimentação da bomba de óleo (`5179363`) e o conector de controle do rotor (`5432032`).
2. Corte com alicate de corte rente as abraçadeiras plásticas que fixam os cabos de alta tensão (observe a rotação original dos cabos).
3. Com a **chave Spanner**, desaperte os anéis rosqueados dos receptáculos de alta tensão (Anodo e Catodo).
4. Puxe os terminais dos cabos HV com cuidado para não danificar as pontas de silicone.
5. **Aterre imediatamente os terminais dos cabos na estrutura metálica do gantry** utilizando o cabo terra do kit de alta tensão.
6. Limpe qualquer excesso de óleo das pontas e insira lenços Kimwipes dentro dos receptáculos do tubo velho para evitar vazamentos durante a movimentação.
7. Solte o parafuso de ajuste POR (*Plane of Rotation*) localizado no colimador.
8. Com a talha sustentando o peso, solte os **4 parafusos de fixação M12**. **Descarte estes parafusos no lixo técnico**.
9. Opere a talha lentamente descendo o tubo usado até o chão sobre um calço acolchoado.
10. Remova a placa de montagem (*Tube Mounting Plate P/N 5403961*) soltando os **4 parafusos M10**. **Descarte estes parafusos**. Limpe a placa com álcool isopropílico.

---

### FASE 4: Instalação do Tubo Novo
1. Posicione a placa de montagem no tubo de Raio-X novo e fixe com **4 parafusos M10 novos** com arruelas novas.
   * **TORQUE OBRIGATÓRIO: 38,4 N·m** (utilizar torquímetro calibrado).
2. Engate os ganchos da talha nos olhais do tubo novo e ice-o suavemente até o alinhamento com a sede do rotor.
3. Fixe o tubo ao gantry utilizando **4 parafusos M12 novos** com arruelas novas.
   * **TORQUE OBRIGATÓRIO: 66,4 N·m** (aperto cruzado em estrela).
4. **Tratamento Dielétrico dos Receptáculos de Alta Tensão:**
   * Remova as proteções dos poços do tubo novo.
   * **Injete óleo mineral isolante (Tube Oil)** nos poços dos receptáculos até preencher a cavidade do fundo. *Objetivo:* Eliminar qualquer bolha de ar na inserção do conector, prevenindo queima por efeito corona.
   * Insira firmemente os conectores de alta tensão (Anodo e Catodo) e aperte os anéis metálicos com a chave Spanner até o batente de vedação.
   * Limpe todo o óleo excedente com lenço Kimwipes.
5. Reconecte o cabo amarelo da bomba e o conector do rotor.
6. Amarre os cabos de alta tensão com novas abraçadeiras plásticas seguindo rigorosamente a curvatura mínima (> 6,35 cm) e os pontos de fixação originais.
7. Desmonte a talha, o braço e o tubo longo de içamento.
8. **Remova o Pino de Trava de Rotação (Rotational Lock Pin)** do gantry.
9. **Inspeção de Óleo:** Verifique visualmente se há qualquer sinal de gotejamento de óleo. Se houver, dê um leve aperto adicional no anel sem forçar a rosca.
10. **Pré-Energização:**
    * Ligue a chave `120VAC` no painel de serviço.
    * Verifique se as ventoinhas do radiador do tubo e da unidade de potência JEDI entram em funcionamento normal.
    * Ligue as chaves `AXIAL DRIVE` e `HVDC`.
    * **Aguarde no mínimo 10 minutos** para estabilização térmica e aquecimento prévio do filamento antes de qualquer disparo.

---

## 5. Sequência Obrigatória de Calibrações e Retestes (18 Passos)

Após a montagem física, o técnico deve executar os 18 procedimentos de software e hardware na ordem exata descrita abaixo (cada um possui seu documento específico na pasta do sistema):

| Sequência | Código / Documento | Procedimento de Calibração | Objetivo Técnico |
| :---: | :--- | :--- | :--- |
| **01** | `Gantry Rotation Safety Check.pdf` | Checagem de Segurança da Rotação | Testa frenagem, sensores de tampa e parada de emergência. |
| **02** | `Reset TnT.pdf` | Reset de Dados TnT (Generator Tool) | Zera os contadores térmicos do tubo e tanque de óleo. |
| **03** | `Plane of Rotation (POR) Alignment.pdf` | Alinhamento do Plano de Rotação | Ajusta a inclinação mecânica do tubo em relação ao plano de corte. |
| **04** | `Beam on Window (BOW) Alignment.pdf` | Alinhamento Beam on Window | Centraliza o feixe de raios-X na janela de entrada dos detectores. |
| **05** | `CBF_SAG Alignment Process.pdf` | Alinhamento CBF / SAG | Corrige o arqueamento do feixe por gravidade nas rotações. |
| **06** | `ISO Alignment Process.pdf` | Alinhamento do Isocentro | Garante coincidência óptica entre laser de posicionamento e feixe. |
| **07** | `Meter Verification (16, Ultra, Plus).pdf` | Verificação dos Medidores de kV/mA | Aferição dos divisores de tensão e circuitos de leitura. |
| **08** | `HV Tank Feedback Resistor Verification.pdf` | Verificação dos Resistores de Feedback | Mede resistência dos circuitos de feedback do tanque de alta tensão. |
| **09** | `Filament Calibration.pdf` | Calibração do Filamento | Calibra curvas de emissão mA para foco fino (*Small*) e foco grosso (*Large*). |
| **10** | `HHS Scans (Adv).pdf` | Disparos de Alta Capacidade Térmica | Estabilização e desgaseificação do tubo em carga térmica progressiva. |
| **11** | `Gantry Balance Procedure.pdf` | Balanceamento Dinâmico do Gantry | Ajuste de contrapesos estáticos e dinâmicos para eliminar vibração rotacional. |
| **12** | `HOT ISO Alignment.pdf` | Alinhamento de Isocentro a Quente | Revalidação do alinhamento geométrico com o tubo aquecido em regime. |
| **13** | `Collimator Calibration.pdf` | Calibração do Colimador | Calibração dos motores de abertura das lâminas de colimação pré-paciente. |
| **14** | `Detailed Calibration.pdf` | Calibração Detalhada de Detectores | Ganhos, offsets e calibração de ar (*Air Cal*) para cada kV/espessura. |
| **15** | *N Number Check* | Conferência dos Coeficientes N | Verificação de uniformidade numérica dos canais do detector. |
| **16** | `System Scanning Test.pdf` | Teste Completo de Varredura | Varredura clínica em modos axial e helicoidal em todas as velocidades. |
| **17** | `Quality Assurance Test.pdf` | Teste de Controle de Qualidade (QA) | Varredura com phantom de água (número de Hounsfield 0 ± 4 HU, ruído, MTF). |
| **18** | `Save System State` | Salvamento do Estado do Sistema | Gravação do backup integral das novas tabelas de calibração no disco e pendrive. |

---

## 6. Critérios de Aceite e Liberação Clínica

O tomógrafo GE Brivo CT385 somente será liberado para uso em pacientes quando:
1. Todos os 18 testes de reteste e calibração forem concluídos com status **PASSED** sem códigos de erro no log do sistema;
2. O teste de QA com phantom padrão apresentar:
   * Água: **0 ± 4 HU**
   * Ruído (*Noise*): Dentro dos desvios especificados no manual de aceitação;
   * Uniformidade espacial: Diferença centro-borda < 2 HU;
3. Gantry girando a velocidade máxima (ex: 0.8s / 1.0s) suavemente, sem vibrações anômalas ou alarmes de balanceamento;
4. Termo de Conclusão de Serviço e Backup do Sistema assinados pelos técnicos responsáveis.

---
*eMED Eletromedicina Ltda. • Engenharia Clínica • Suporte Técnico Autorizado*
