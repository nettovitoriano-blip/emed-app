# INSTRUÇÃO DE TRABALHO TÉCNICA - eMED BIOMEDICAL

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RXD-NEU-002`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## IT-RXD-NEU-002: Calibração de Campo Plano (Flat Field), Ganho, Offset e Mapa de Defeitos (Canon CXDI / NeuVision 550M)
**Equipamento:** Neusoft NeuVision 550M / NeuVision 550M Plus (DR Móvel)  
**Subsistema:** Flat Panel Detector (FPD) sem fio Canon CXDI & Canon Service Tool  
**Documento Base:** Canon CXDI Service Manual & Neusoft Integration Manual NPS-XR-0122E  
**Nível de Acesso:** Diagnóstico por Imagem / Field Service Specialist  
**Revisão:** 1.0 - Procedimento Semestral de Calibração da Cadeia de Imagem Digital  

---

### 1. OBJETIVO E ESCOPO
Padronizar a rotina técnica de calibração eletrônica e correção de não uniformidade da matriz de fotodiodos de silício amorfo (a-Si) do detector digital Canon CXDI no sistema Neusoft NeuVision 550M Plus, eliminando artefatos de imagem, linhas de ruído, sombreamentos e pixels mortos.

---

### 2. CONDIÇÕES PRÉVIAS OBRIGATÓRIAS
* O detector deve permanecer ligado e estabilizado termicamente por no mínimo **20 minutos** antes de iniciar a calibração.
* O colimador do raio-X móvel deve ser aberto para cobrir 100% da área útil do detector.
* A distância foco-detector (DFD) deve ser ajustada para **$100\text{ cm}$**.
* Nenhuma grade antidifusora ou objeto atenuador pode estar presente sobre o detector durante as etapas de campo aberto (*Flat Field*).

---

### 3. PROCEDIMENTO PASSO A PASSO NO CANON SERVICE TOOL

#### ETAPA 1: Acesso ao Utilitário de Serviço
1. Faça login na conta de serviço do Windows: usuário `cxdiadmin` / senha: `nmsadmin`.
2. Abra a ferramenta oficial: `Iniciar` $\rightarrow$ `Canon Service Tool`.
3. Insira as credenciais da ferramenta: usuário `cxdiadmin` / senha: `Canononac`.
4. Selecione o botão **`[Calibration]`** no menu principal.

---

#### ETAPA 2: Calibração de Corrente de Escuro (Dark Current / Offset Calibration)
1. Certifique-se de que o colimador esteja fechado ou sem emissão de raios-X.
2. No menu de calibração, selecione **`[Offset Calibration]`**.
3. Clique em **`[Start]`**:
   - O detector realizará a leitura sucessiva de 16 frames no escuro total sem emissão de radiação.
   - O software calculará o mapa de ruído térmico residual de cada pixel da matriz a-Si.
4. Aguarde a mensagem verde: `Offset Calibration Completed Successfully`.

---

#### ETAPA 3: Calibração de Ganho (Gain / Flat Field Calibration)
1. Abra totalmente as lâminas do colimador de modo que o feixe luminoso ultrapasse as bordas do detector em todos os lados.
2. Posicione uma placa homogênea de filtração de alumínio ($1,0\text{ mm Al}$ ou $2,0\text{ mm Al}$, se requerido pelo protocolo) na saída do colimador.
3. No painel do gerador Sedecal, ajuste a técnica radiográfica conforme solicitado na tela do Service Tool:
   * **$70\text{ kV} \pm 2\text{ kV}$**
   * **$10\text{ mAs}$ a $16\text{ mAs}$** (garantindo dose média de aproximadamente $2,5\ \mu\text{Gy}$ a $5,0\ \mu\text{Gy}$ no detector).
4. Selecione **`[Gain Calibration]`** no software.
5. Quando a tela indicar `Ready for Exposure`, acione a botoeira de disparo do raio-X mantendo pressionada até o bip de término.
6. O software solicitará sucessivos disparos (normalmente de 3 a 5 exposições) para cálculo da curva média de sensibilidade de cada canal da matriz.
7. Aguarde a mensagem: `Gain Calibration Completed Successfully`.

---

#### ETAPA 4: Mapeamento de Pixels Defeituosos (Defective Pixel Map)
1. Selecione a opção **`[Defect Map Creation / Update]`**.
2. O algoritmo analisa os dados brutos de ganho e offset para identificar:
   - Pixels inoperantes permanentes (*dead pixels*);
   - Pixels saturados (*hot pixels*);
   - Linhas ou colunas com ganho anômalo (*line defects*).
3. O software atualiza a tabela de interpolação matemática interna do detector, corrigindo em tempo real os pixels faltantes a partir da média ponderada dos vizinhos circunvizinhos.
4. Clique em **`[Save & Upload to Detector EEPROM]`** para gravar os coeficientes de calibração na memória interna não volátil do detector Flat Panel.

---

### 4. CHECKLIST DE LIBERAÇÃO DE IMAGEM
- [ ] Imagem de teste homogênea sem linhas verticais/horizontais ou faixas de ganho.
- [ ] Índice de Ruído Residual (Noise Standard Deviation) $< 1,5\%$.
- [ ] Teste de resolução espacial com padrão de linhas (*bar pattern*) atingindo no mínimo **$3,4\text{ lp/mm}$**.
- [ ] Envio de imagem radiográfica de teste via DICOM para a estação de laudo/PACS confirmado sem artefatos.
