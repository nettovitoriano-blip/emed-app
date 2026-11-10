# IT-RXM-SHIM-006: PROTOCOLO GERAL DE CALIBRAÇÃO E AJUSTES DE CAMPO

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RXM-SHIM-006`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## 1. OBJETIVO E ESCOPO
Padronizar o protocolo completo de calibração eletrônica, mecânica, radiométrica e digital do sistema móvel **Shimadzu MobileDaRt Evolution (MX8 e MX9)**, garantindo conformidade estrita com as tolerâncias de fábrica da Shimadzu Corp. e as exigências da RDC 611/2022 (ANVISA) e normas NBR IEC 60601-2-54.

O procedimento abrange os seguintes eixos metrológicos:
1. **Acesso ao Modo de Ajuste (Adjustment Mode)** pelo painel do operador.
2. **Calibração da Corrente do Tubo de Raios-X (FVR - Filament Voltage Reference)** em 2 pontos e patamares de 40 a 133 kV.
3. **Calibração do Sensor de Tensão do Banco de Baterias (240V DC)**.
4. **Calibração da Manopla Dinamométrica de Tração (FSR)** e controle de velocidade dos motores.
5. **Alinhamento Óptico do Colimador, Luminosidade e Coincidência Luz x Radiação**.
6. **Calibração Digital do Detector Flat Panel (FPD Vieworks / Shimadzu)**: Offset (Dark), Ganho (Flat Field) e Mapeamento de Pixels Defeituosos.

---

## 2. FERRAMENTAS E PADRÕES DE CALIBRAÇÃO OBRIGATÓRIOS
Para a execução deste protocolo, o especialista de campo eMED deve dispor das seguintes ferramentas calibradas com certificado RBC/Inmetro válido:
* **Multímetro Digital True-RMS** com pontas de prova isoladas CAT III 1000V (Fluke 87V ou superior).
* **Medidor Eletrônico de Não Invasivo de Tensão e Radiação** (Multifunção Radcal / RTI Piranha / Unfors RaySafe).
* **Dinamômetro de Tração com Mola (Spring Gauge)** calibrado de 0 a 100 N (ou 0 a 10 kgf).
* **Filtros Homogêneos de Radiação:** Placa de cobre puro de 1,5 mm Cu e placas de alumínio de alta pureza (20 mm Al).
* **Luxímetro Digital** para medição da iluminância do campo luminoso a 1 metro.
* **Trena milimétrica de precisão** e fita de chumbo de referência.

---

## 3. ACESSO AO MOTO DE AJUSTE (ADJUSTMENT MODE)

### 3.1 Método Direto pelo Painel de Comando (Sem Abertura de Tampas)
1. Com o sistema desligado na chave principal, pressione simultaneamente as teclas **[Collimator Lamp]** e **[APR Program]**.
2. Enquanto mantém as duas teclas pressionadas, gire a chave de ignição para a posição **ON**.
3. Mantenha as teclas pressionadas por 3 segundos até que o display de kV exiba a indicação piscante **`A d j`** e o display de mAs exiba a versão de firmware da placa XCONT-2018 (ex: `r 1 . 0 2`).
4. O equipamento está agora no **Modo de Calibração e Ajustes de Fábrica**.

### 3.2 Mapa de Funções do Modo de Ajuste

| Página de Ajuste | Tecla Ativa | Função de Calibração | Descrição Operacional |
| :---: | :---: | :--- | :--- |
| **Pág. 1** (Key 1 pisca) | **<5>** | Calibração de Tensão das Baterias | Aferição do divisor de tensão da placa de carga |
| **Pág. 1** (Key 1 pisca) | **<6>** | Calibração da Manopla (Handle FSR) | Ajuste da sensibilidade com dinamômetro de tração |
| **Pág. 1** (Key 1 pisca) | **<7>** | Calibração de FVR em 2 Pontos | Ajuste nos limites de 80 kV (mínimo e máximo mA) |
| **Pág. 1** (Key 1 pisca) | **<8>** | Calibração de FVR Ponto a Ponto | Ajuste fino individual nos 6 patamares de kV |
| **Pág. 1** (Key 1 pisca) | **<9>** | Teste de Queda de Tensão em Carga | Monitoramento da impedância interna do banco 240V |
| **Pág. 2** (INFO pisca) | **<1>** | Registro do Código de Bateria | Data de troca e capacidade em Ah |
| **Pág. 2** (INFO pisca) | **<2>** | Calibração da Câmara DAP | Ajuste do coeficiente cGy·cm² do colimador |
| **Pág. 3 / 4** | **<3>** | Zeramento de Horímetros e Contadores | Reset pós-troca de tubo, baterias ou motores |

---

## 4. CALIBRAÇÃO DA CORRENTE DO TUBO (FVR - FILAMENT VOLTAGE REFERENCE)

A curva de corrente de tubo ($mA$) no MobileDaRt é controlada por valores hexadecimais/analógicos gravados na NVRAM denominados **FVR**. Uma calibração inadequada gera subexposição (imagem ruidosa) ou sobrecarga térmica que encurta drasticamente a vida útil do ânodo giratório.

### 4.1 Inicialização dos Parâmetros de FVR
1. Caso a placa XCONT-2018 ou o monobloco tenham sido substituídos, entre no modo de ajuste e selecione a inicialização da tabela padrão de ROM.
2. Pressione a tecla de foco fino/grosso para carregar as curvas nominais de fábrica.

### 4.2 Calibração de FVR em 2 Pontos (Two-Point Adjustment - Modo Rápido)
1. No menu da Página 1, pressione a tecla **<7>**. O display exibirá `F 5 0` (Foco fino, 50 mA).
2. Conecte o detector não invasivo (RaySafe/Piranha) no centro do feixe a 100 cm de DFF com colimador aberto em 10x10 cm.
3. **Ponto 1 (80 kV / Menor mA):**
   * Realize um disparo no disparador manual.
   * Observe a leitura do medidor externo.
   * Pressione a tecla **[Filter]** para exibir o valor do FVR (ex: `FVR = 3.85`). A tecla Filter começará a piscar.
   * Utilize as teclas **kV [+]** ou **kV [-]** para ajustar:
     * Para **aumentar** o mA real medido: aumente o valor do FVR.
     * Para **diminuir** o mA real medido: diminua o valor do FVR.
   * Repita o disparo até que a corrente medida esteja exatamente dentro de **± 2%** do valor programado.
   * Pressione a tecla **[Registration]**: o display exibirá **`r e c o r d`**, confirmando a gravação permanente na memória.
4. **Ponto 2 (80 kV / Maior mA):**
   * Selecione o patamar de corrente máxima (ex: 160 mA ou 200 mA).
   * Repita o processo de disparo, leitura, correção do FVR e gravação com **[Registration]**.
5. O processador recalculará automaticamente todos os pontos intermediários da curva polinomial.

### 4.3 Verificação e Ajuste Fino nos 6 Patamares de Tensão
No modo **<8>** (Each Point Adjustment), execute disparos de checagem conforme a tabela abaixo:

| Tensão Programada | Tolerância de kVp | Corrente Alvo | Tolerância de mA | FVR Típico |
| :---: | :---: | :---: | :---: | :---: |
| **40 kV** | 38,5 a 41,5 kV (± 3%) | 100 mA | 96 a 104 mA | 3.65 ± 0.20 |
| **60 kV** | 58,2 a 61,8 kV (± 3%) | 125 mA | 120 a 130 mA | 3.78 ± 0.15 |
| **80 kV** | 77,6 a 82,4 kV (± 3%) | 160 mA | 155 a 165 mA | 3.92 ± 0.15 |
| **100 kV** | 97,0 a 103,0 kV (± 3%) | 160 mA | 155 a 165 mA | 4.05 ± 0.15 |
| **125 kV** | 121,2 a 128,8 kV (± 3%) | 125 mA | 120 a 130 mA | 4.18 ± 0.15 |
| **133 kV** | 129,0 a 137,0 kV (± 3%) | 100 mA | 96 a 104 mA | 4.25 ± 0.15 |

---

## 5. CALIBRAÇÃO DA TENSÃO DO BANCO DE BATERIAS (240V DC)
O MobileDaRt utiliza um banco com 20 baterias seladas chumbo-ácido de 12V em série. O circuito da placa de carga (MUX CHARGE) deve ler exatamente a mesma tensão real dos bornes para evitar sobrecarga ou subcarga.

1. No Modo de Ajuste, pressione a tecla **<5>** na Página 1.
2. O display exibirá a indicação `b A t t` e o valor de tensão interna lido pelo conversor A/D (ex: `2 4 2 . 5`).
3. Com o multímetro Fluke calibrado na escala DC 1000V, meça a tensão diretamente nos bornes positivo e negativo do conector principal do banco.
4. Se o multímetro indicar, por exemplo, **244.8V DC**:
   * Pressione as teclas **mAs [+]** ou **mAs [-]** no painel até que o display do equipamento indique exatamente **`2 4 4 . 8`**.
5. Pressione a tecla **[Registration]** para memorizar a calibração de offset e ganho do divisor de tensão.

---

## 6. CALIBRAÇÃO DA MANOPLA DINAMOMÉTRICA (DRIVE HANDLE / FSR)
A manopla de movimentação possui sensores de resistência variável por força (**FSR - Force Sensing Resistors**) que controlam a velocidade proporcional de avanço e recuo dos motores elétricos das rodas motrizes.

1. No Modo de Ajuste, pressione a tecla **<6>**. O display exibirá a indicação `H n d L` e a posição de calibração `P - 0`.
2. **Posição Neutra (P-0):**
   * Sem tocar na manopral (força zero), certifique-se de que os braços mecânicos estejam em repouso.
   * Pressione **[Registration]** para definir o ponto zero de repouso (offset neutro).
3. **Calibração de Tração para Frente (P-1 a P-3):**
   * Prenda a alça do dinamômetro de tração com mola no centro da empunhadura da manopla.
   * Aplique uma força contínua de tração para frente exatamente no valor especificado na tabela:
     * **Passo P-1 (Força Baixa):** Puxe com **$20\text{ N} \pm 1\text{ N}$** (2,0 kgf) -> Pressione **[Registration]**.
     * **Passo P-2 (Força Média):** Puxe com **$45\text{ N} \pm 2\text{ N}$** (4,5 kgf) -> Pressione **[Registration]**.
     * **Passo P-3 (Força Máxima):** Puxe com **$70\text{ N} \pm 3\text{ N}$** (7,0 kgf) -> Pressione **[Registration]**.
4. **Calibração de Recuo para Trás (P-4 a P-6):**
   * Aplique força de empurrão para trás nos mesmos valores escalonados (20 N, 45 N e 70 N) registrando cada patamar.
5. **Teste Dinâmico em Corredor:**
   * Saia do modo de ajuste, destrave os freios e teste a resposta de aceleração e desaceleração. A resposta deve ser linear, suave e parar imediatamente ao soltar as mãos.

---

## 7. ALINHAMENTO ÓPTICO DO COLIMADOR LUMINOSO
Conforme a NBR IEC 60601-2-54, o campo luminoso projetado pelo colimador deve coincidir com o feixe útil de raios-X emitido pelo tubo.

1. Posicione o cabeçote a uma Distância Foco-Filme (**DFF**) de exatamente **100 cm** da superfície do detector ou chassi de teste.
2. Ligue a lâmpada do colimador e ajuste os diafragmas para abrir um campo retangular de **$20 \times 20\text{ cm}$**.
3. **Medição de Iluminância:**
   * Posicione o sensor do luxímetro no centro e nos 4 quadrantes do campo luminoso.
   * A média das leituras com luz ambiente apagada deve ser **$\ge 160\text{ lux}$**.
   * Se $< 160\text{ lux}$, limpe os espelhos internos ou substitua a lâmpada halógena de 12V/100W (P/N 062-65003).
4. **Coincidência Óptica x Radiação:**
   * Coloque 4 marcadores radiopacos (clipes ou réguas de chumbo) nas 4 bordas exatas da luz projetada.
   * Realize um disparo de teste a $60\text{ kV}$, $5\text{ mAs}$.
   * Avalie a imagem radiográfica gerada:
     * O desvio entre a borda da luz e a borda da imagem de radiação não pode ultrapassar **$10\text{ mm}$** em nenhum dos lados ($1\%$ da DFF).
     * O erro total somado dos dois eixos perpendiculares não pode ultrapassar **$20\text{ mm}$** ($2\%$ da DFF).
   * Se houver desvio, solte os 4 parafusos de fixação do colimador e ajuste o espelho refletor interno até a coincidência perfeita.

---

## 8. CALIBRAÇÃO DIGITAL DO DETECTOR FLAT PANEL (FPD)
> Realizada através do software **VSS (Vieworks Service Software)** ou diretamente na interface de calibração do **VXvue**.

### 8.1 Condição Prévia Obrigatória
O detector deve estar ligado, conectado à rede Wi-Fi/cabo e repousando em temperatura estável há no mínimo **30 minutos** antes de iniciar as rotinas digitais.

### 8.2 Dark Calibration (Offset de Corrente Escura)
* Mede o ruído intrínseco e a corrente de fuga térmica de cada fotodiodo de silício amorfo (a-Si).
* **Procedimento:** Executado totalmente **sem radiação**. O software faz 16 leituras de integração consecutivas e grava o mapa de subtração de background.

### 8.3 Gain Calibration (Calibração de Ganho de Campo Plano)
* Equaliza as diferenças de sensibilidade e absorção do cintilador de Iodeto de Césio (CsI) em toda a área do painel.
* **Procedimento:**
  1. Posicione o tubo a $100\text{ cm}$ do detector montado na mesa ou suporte.
  2. Fixe o filtro de **cobre de 1,5 mm Cu** na saída do colimador.
  3. Abra os diafragmas para cobrir toda a área ativa do detector com margem de 2 cm.
  4. Dispare **5 exposições consecutivas** com a condição: **$70\text{ kV} / 100\text{ mA} / 100\text{ ms}$**.
  5. O software calculará o coeficiente de ganho multiplicativo para cada canal dos CIs de leitura.

### 8.4 Defect Pixel Map (Mapeamento de Pixels Mortos)
* Identifica pixels permanentemente desligados (Dead Pixels) ou saturados (Hot Pixels).
* O mapa corrige os defeitos aplicando interpolação bidimensional baseada na mediana dos 8 pixels adjacentes saudáveis.
* **Critério de Aceitação:** Nenhum cluster de pixels defeituosos pode ser maior que **$3 \times 3\text{ pixels}$** na região central de interesse diagnóstico.

---

## 9. PROTOCOLO DE LIBERAÇÃO METROLÓGICA (CHECKLIST FINAL)

- [ ] **Modo de Ajuste Finalizado:** Display retornou à operação clínica normal sem códigos de erro.
- [ ] **Tensão do Tubo (kVp):** Desvio inferior a $\pm 3\%$ em todos os patamares de 40 a 133 kV.
- [ ] **Corrente do Tubo (FVR):** Leituras em mA calibradas com erro $\le \pm 2\%$ e salvas com `record`.
- [ ] **Baterias:** Leitura do painel coincide exatamente com o multímetro nos bornes ($240\text{V DC}$).
- [ ] **Manopla FSR:** Dinamômetro registrou avanço e recuo proporcionais e frenagem instantânea.
- [ ] **Campo Luminoso:** Iluminância $\ge 160\text{ lux}$ e erro de coincidência com radiação $\le 10\text{ mm}$.
- [ ] **FPD Digital:** Dark, Gain e Defect Map aprovados com 100% de sucesso no VXvue/VSS.
- [ ] **Etiqueta de Calibração eMED:** Fixada na carcaça do equipamento com data da calibração e validade semestral.
