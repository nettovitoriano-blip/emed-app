# INSTRUÇÃO DE TRABALHO: MANUTENÇÃO PREVENTIVA PROGRAMADA (PM)
### Tomógrafo Computadorizado GE BrightSpeed Lite / Select Series
**DOCUMENTO:** `IT-TOMO-GE-002` | **REVISÃO:** 01 | **REF. FABRICANTE:** Direction 5181178-800 Rev 16  
**EMED ELETROMEDICINA LTDA. | ENGENHARIA CLÍNICA & SUPORTE ESPECIALIZADO EM CAMPO**

---

## 1. Objetivo e Escopo

Esta Instrução de Trabalho (IT) estabelece os critérios e a rotina técnica para a execução da **Manutenção Preventiva Programada (Planned Maintenance - PM)** nos tomógrafos **GE BrightSpeed Lite e BrightSpeed Select Series**.

O protocolo é dividido em 4 ciclos periódicos (**Schedules A, B, C e D**), cobrindo inspeções mecânicas, limpeza eletrostática de pistas de Slip Ring, integridade de alta tensão, lubrificação de guias e controle de qualidade radiológica (QA).

| Cronograma PM | Periodicidade | Tempo Estimado | Foco Principal |
| :---: | :---: | :---: | :--- |
| **Schedule A** | 1º Trimestre (3 meses) | 2,0 horas | Console GOC, limpeza de poeira de grafite do Slip Ring e filtros DAS. |
| **Schedule B** | 2º Trimestre (Semestral) | 2,0 horas | Inspeção de desgaste das escovas, lubrificação e botões de emergência. |
| **Schedule C** | 3º Trimestre (9 meses) | 2,0 horas | Reteste de filtros, checagem do trocador de calor do tubo e console. |
| **Schedule D** | 4º Trimestre (Anual Completo) | 3,2 horas | Revisão anual total: PDU, tanque HV, graxa do rolamento principal e calibrações. |

---

## 2. Ferramentas, Consumíveis e Equipamentos de Teste

### 2.1. Ferramental Especial
* Aspirador de pó hospitalar com filtro HEPA e bocal plástico não condutivo (obrigatório para Slip Ring).
* Paquímetro digital milimétrico (para medição do comprimento útil das escovas de carvão).
* Pano macio livre de fiapos (Kimwipes) e álcool isopropílico 99.8%.
* Pistola de graxa com graxa recomendada GE (Beacon 325 ou Klüber Microlube GL 261 para rolamento do gantry).
* Torquímetro dinamométrico calibrado com pontas sextavadas/Allen.
* Multímetro digital True-RMS Cat III 600V.
* Phantom de Controle de Qualidade GE QA Phantom com suporte de mesa.

---

## 3. Protocolos de Segurança & Bloqueio LOTO

> [!CAUTION]
> **RISCO DE CHOQUE ELÉTRICO LETAL E LESÃO POR ROTAÇÃO MECÂNICA DO GANTRY**
> 1. Antes de iniciar qualquer limpeza ou remoção de carenagens, desative no painel de chaves do gantry:
>    * `AXIAL DRIVE ENABLE` -> OFF
>    * `HVDC ENABLE` -> OFF
>    * `120VAC` -> OFF
> 2. No caso de intervenção na PDU ou no rolamento, desligue o disjuntor geral da sala e aplique o cadeado LOTO.
> 3. Nunca utilize ar comprimido para limpar poeira de carvão/grafite do Slip Ring. A dispersão de partículas condutoras causa curto-circuito catastrófico nas placas do gantry. **Utilize exclusivamente aspiração a vácuo com filtro HEPA**.

---

## 4. Roteiro Passo a Passo de Execução (Fases do PM)

### FASE 1: Inspeção do Console de Operação (GOC / LCGOC)
1. **Limpeza Externa e Filtros:** Remova e limpe os filtros de ar das entradas frontais do console e gabinete da CPU.
2. **Periféricos e Cabos:** Verifique conexões do teclado médico, mouse óptico, caixas de som de intercomunicação com o paciente e monitor LCD de diagnóstico.
3. **Espaço em Disco e Logs de Erro:**
   * No desktop de serviço, acesse: `[ERROR LOGS]` -> verificar se existem falhas reincidentes de comunicação ou arcing no tubo.
   * Verificar percentual livre nas partições `/usr`, `/export/home` e `/data`.

---

### FASE 2: Gantry & Sistema de Pistas do Slip Ring (Crítico)
*Referência Técnica: CTPM-1319 e CTPM-1323*

1. **Remoção de Carenagens:** Remova as tampas frontais e superiores do gantry.
2. **Aspiração de Poeira de Grafite (CTPM-1319):**
   * Com o gantry desligado e travado, utilize o aspirador com bocal de plástico para sugar toda a poeira de carvão acumulada sob as escovas e nas calhas coletoras.
   * Aspire os canais entre as pistas de cobre/prata do anel deslizante (Slip Ring).
3. **Inspeção de Desgaste das Escovas (CTPM-1323):**
   * Inspecione visualmente o bloco de escovas (SCHLEIFRING Brush Blocks).
   * Verifique a ponta de contato de cada escova quanto a desgaste irregular, trincas ou lascas.
   * **Critério de Substituição:** Se a linha de desgaste limite gravada na lateral da escova for atingida ou se o comprimento útil restante for inferior a **5,0 mm**, substitua o conjunto completo de escovas.
   * Verifique a tensão da mola de pressão de cada escova (devem pressionar suavemente as pistas sem folga).
4. **Limpeza das Pistas do Slip Ring (CTPM-1306):**
   * Se houver acúmulo de óleo ou resíduo pegajoso, umedeça um lenço Kimwipe com álcool isopropílico e limpe as pistas girando o gantry manualmente de forma lenta.
   * Deixe secar por 10 minutos antes de religar.
5. **Lubrificação do Rolamento Principal (CTPM-1308 - Schedule D):**
   * Localize os bicos de lubrificação (*grease nipples*) na pista do rolamento principal.
   * Aplique a quantidade especificada de graxa limpa através da engraxadeira manual enquanto rotaciona o gantry para distribuição homogênea.
6. **Limpeza dos Filtros de Ar do DAS (Detector):**
   * Remova os filtros de ar das ventoinhas do módulo DAS (*Pancake Fans*).
   * Lave com água morna e sabão neutro, seque 100% com pano limpo e reinstale.

---

### FASE 3: Sistema de Alta Tensão e Tubo de Raio-X
1. **Limpeza do Trocador de Calor do Tubo (CTPM-1432):**
   * Inspecione as aletas do radiador do circuito de resfriamento do tubo.
   * Remova poeiras com aspirador e pincel antiestático macio.
   * Verifique se as mangueiras de óleo apresentam ressecamento, rachaduras ou vazamentos nos engates rápidos.
2. **Verificação de Nível e Estanqueidade:**
   * Certifique-se de que não há gotejamento de óleo sob o tanque de alta tensão (HV Tank) ou nos receptáculos do tubo.
3. **Disparos HHS (High Heat Storage):**
   * Execute o protocolo de aquecimento e desgaseificação térmica progressiva via software de serviço.

---

### FASE 4: Mesa do Paciente (Patient Table Lite)
*Referência Técnica: CTPM-1707*

1. **Movimentação Longitudinal e Vertical:**
   * Teste todo o curso da mesa (elevação e avanço) observando suavidade, ausência de ruídos ou travamentos.
2. **Lubrificação das Guias e Fuso:**
   * Limpe os trilhos de rolamento e aplique fina camada de graxa sintética nos fusos de elevação mecânica/hidráulica.
3. **Calibração dos Potenciômetros de Posição:**
   * Verifique a leitura de posição longitudinal (Z) no display do gantry, comparando a cota marcada com a leitura real na régua física da mesa. Tolerância: $\le 1,0\text{ mm}$.

---

### FASE 5: Unidade de Distribuição de Força (PDU) & Segurança
*Referência Técnica: CTPM-1508 / CTPM-1601*

1. **Reaperto de Bornes na PDU:**
   * Com o disjuntor geral desenergizado, efetue o reaperto de todos os bornes de entrada e saída das fases, neutro e barramento terra da PDU.
2. **Teste de Botões de Parada de Emergência (E-Stop):**
   * Acione individualmente cada botão cogumelo de emergência (gantry frontal esquerdo, frontal direito e console).
   * Confirme se o gantry interrompe imediatamente o giro e desenergiza os circuitos de tração e alta tensão.

---

### FASE 6: Teste de Controle de Qualidade de Imagem (QA Test)
1. Instale o phantom padrão de controle de qualidade GE no suporte de mesa alinhado aos lasers do gantry.
2. Execute o protocolo automatizado de **QA Daily / Weekly**:
   * **Número de CT da Água:** Deve estar exatamente em **$0 \pm 4\text{ HU}$**.
   * **Ruído da Imagem (*Noise*):** Conforme limite do modelo (desvio padrão $\le 3.5\text{ HU}$).
   * **Uniformidade Espacial:** Diferença entre o centro do phantom e as 4 bordas (superior, inferior, esquerda e direita) **$\le 2,0\text{ HU}$**.
   * **Espessura de Corte (*Slice Thickness*):** Desvio inferior a $\pm 0,5\text{ mm}$.

---

## 5. Checklist de Conclusão & Registro de Manutenção

| Item | Procedimento Executado | Status | Observações / Parâmetros Lidos |
| :---: | :--- | :---: | :--- |
| **01** | Limpeza e aspiração de resíduos de grafite no Slip Ring | `[ ] OK` `[ ] NOK` | Pistas desobstruídas e limpas |
| **02** | Medição do comprimento das escovas do Slip Ring | `[ ] OK` `[ ] NOK` | Comprimento mínimo aferido: `_____ mm` |
| **03** | Limpeza dos filtros de ar do DAS e Gantry | `[ ] OK` `[ ] NOK` | Filtros lavados e secos |
| **04** | Limpeza das aletas do radiador do tubo de Raio-X | `[ ] OK` `[ ] NOK` | Isento de poeira e sem vazamentos |
| **05** | Lubrificação dos fusos e trilhos da mesa do paciente | `[ ] OK` `[ ] NOK` | Movimento macio sem ruído |
| **06** | Teste de todos os botões de emergência (*E-Stop*) | `[ ] OK` `[ ] NOK` | Frenagem instantânea confirmada |
| **07** | Reaperto das conexões elétricas e aterramento na PDU | `[ ] OK` `[ ] NOK` | Torque verificado em todos os bornes |
| **08** | Teste de QA com Phantom (Água em $0 \pm 4\text{ HU}$) | `[ ] OK` `[ ] NOK` | Valor central medido: `_____ HU` |

* **Técnico Responsável:** \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
* **Data da Execução:** \_\_\_\_ / \_\_\_\_ / 2026 &nbsp;&nbsp;|&nbsp;&nbsp; **Próximo Ciclo Recomendado:** Trimestral (Schedule posterior)

---
*eMED Eletromedicina Ltda. • Suporte Técnico e Engenharia de Campo Especializada*
