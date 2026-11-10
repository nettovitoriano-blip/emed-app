# INSTRUÇÃO DE TRABALHO TÉCNICA

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RX-LOT-002`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## IT-RX-LOT-002: Calibração de Parâmetros Radiológicos (kV, mA, Tempo) e Manutenção Preventiva (Família HF Lotus)
**Equipamento:** Aparelhos de Raios-X Fixos e Telecomandados Lotus Família HF  
**Documento Base:** Manual do Usuário e Operação Família HF & Rotina Preventiva eMED  
**Nível de Acesso:** Diagnóstico por Imagem / Técnico de Manutenção Especializado  
**Revisão:** 1.0 - Procedimento Anual de Calibração e Manutenção Preventiva  

---

### 1. OBJETIVO E ESCOPO
Estabelecer o protocolo de calibração metrológica de tensão de pico ($kV_p$), corrente de tubo ($mA$), produto corrente-tempo ($mAs$), reprodutibilidade do tempo de exposição e manutenção preventiva periódica para os equipamentos radiológicos da Família HF Lotus.

---

### 2. INSTRUMENTAL PADRÃO NECESSÁRIO
* Medidor Multiparâmetro não invasivo de Raios-X (ex: Radcal, RaySafe ou Piranha) calibrado pela RBC.
* Multímetro digital True-RMS e osciloscópio digital de memória com ponta de prova $100:1$.
* Dispositivo de teste de alinhamento de feixe luminoso e radiológico (placa de chumbo com orifícios calibrados).
* Phantom de alumínio para filtração equivalente ($2,5\text{ mm Al}$).

---

### 3. PROCEDIMENTO DE CALIBRAÇÃO PASSO A PASSO

#### ETAPA 1: Verificação da Tensão de Pico ($kV_p$)
1. Posicione o sensor do medidor de radiação sobre a mesa de exames a uma distância foco-filme (DFF) de **$100\text{ cm}$**, centralizado no retículo luminoso do colimador.
2. Selecione os níveis nominais no console de comando:
   * **$50\text{ kV}$ / $100\text{ mA}$ / $0,1\text{ s}$**
   * **$70\text{ kV}$ / $200\text{ mA}$ / $0,1\text{ s}$**
   * **$90\text{ kV}$ / $200\text{ mA}$ / $0,1\text{ s}$**
   * **$120\text{ kV}$ / $300\text{ mA}$ / $0,1\text{ s}$**
3. Realize 3 disparos para cada nível e calcule a média:
   $$\text{Erro de } kV_p = \left|\frac{kV_{\text{medido}} - kV_{\text{nominal}}}{kV_{\text{nominal}}}\right| \times 100\% \le 5\%$$
4. Caso o desvio ultrapasse $\pm 5\%$, ajuste os potenciômetros de ganho de realimentação na placa controladora do inversor.

---

#### ETAPA 2: Verificação do Tempo de Exposição e Reprodutibilidade
1. Programe tempos fixos de **$0,02\text{ s}$ ($20\text{ ms}$)**, **$0,05\text{ s}$ ($50\text{ ms}$)**, **$0,10\text{ s}$ ($100\text{ ms}$)** e **$0,50\text{ s}$ ($500\text{ ms}$)**.
2. O erro relativo entre o tempo medido no detector e o programado deve situar-se em **$\le 5\%$**.
3. O coeficiente de variação ($CV$) de 5 exposições sucessivas nas mesmas condições deve ser:
   $$CV = \frac{\sigma}{\bar{X}} \le 0,05$$

---

#### ETAPA 3: Alinhamento Campo de Luz x Campo de Radiação
1. Posicione o alinhador radiológico no centro do feixe a $100\text{ cm}$ de DFF.
2. Abra o colimador para a dimensão exata de $20 \times 20\text{ cm}$ delimitada pela cruz do alinhador.
3. Efetue um disparo em $60\text{ kV} / 10\text{ mAs}$ com detector digital ou filme.
4. Meça a diferença entre as bordas do campo luminoso e o campo radiado:
   * A discrepância em qualquer eixo **NÃO pode exceder $2\%$ da DFF** ($\le 2,0\text{ cm}$ em $100\text{ cm}$).
   * O desvio do centro do feixe deve ser $\le 1\%$ da DFF ($\le 1,0\text{ cm}$).

---

### 4. CHECKLIST DE MANUTENÇÃO PREVENTIVA (PM)
- [ ] Reaperto dos terminais elétricos da contatora principal e borneira de entrada.
- [ ] Medição dos cabos de alta tensão com megômetro ($> 1000\text{ M}\Omega$).
- [ ] Limpeza dos receptáculos de alta tensão e reposição de silicone/óleo dielétrico.
- [ ] Verificação do contrapeso da coluna porta-tubo e lubrificação das guias de rolamento.
- [ ] Teste de travamento dos freios eletromagnéticos da mesa e estativa vertical (*Bucky*).
- [ ] Verificação do temporizador de desligamento automático da lâmpada do colimador (~30s).
