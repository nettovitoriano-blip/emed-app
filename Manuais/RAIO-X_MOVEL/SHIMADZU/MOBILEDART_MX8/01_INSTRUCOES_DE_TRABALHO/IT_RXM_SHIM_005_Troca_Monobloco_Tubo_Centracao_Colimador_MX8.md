# INSTRUÇÃO DE TRABALHO TÉCNICA - eMED BIOMEDICAL

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RXM-SHIM-005`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## IT-RXM-SHIM-005: Substituição do Monobloco do Tubo de Raios-X e Centralização do Colimador (Shimadzu MobileDaRt MX8)
**Equipamento:** Shimadzu MobileDaRt Evolution / MX8 Version (Raio-X Móvel Motorizado)  
**Subsistema:** Monobloco de Raio-X, Braço Telescópico e Colimador R-20J  
**Documentos Base de Fábrica:** Manual de Instalação e Serviço Shimadzu M503-E410 (Seção 11.5)  
**Nível de Acesso:** Engenharia Clínica / Técnico de Campo Especializado  
**Revisão:** 1.0 - Procedimento de Substituição do Cabeçote e Alinhamento Óptico  

---

### 1. OBJETIVO E ESCOPO
Padronizar a desmontagem física, sustentação mecânica, conexão de cabos de alta tensão e aterramento de segurança para a substituição do **Conjunto do Tubo de Raios-X (*X-Ray Tube Assembly*)**, seguida pelo alinhamento e centralização mecânica entre o ponto focal do anodo e o centro da lâmpada do colimador óptico (*Centering the Collimator and X-Ray Focus*) no Shimadzu MobileDaRt MX8.

---

### 2. FERRAMENTAS E DISPOSITIVOS ESPECIAIS NECESSÁRIOS
* Alicate especial para porcas de fixação *FU Lock Nut AW04*.
* Parafuso Allen M8x16 (usado no travamento do suporte do tubo).
* Chaves Allen de precisão ($2,5\text{ mm}$ a $8\text{ mm}$) e chave de torque.
* Dinamômetro de tração com gancho (*Spring Gauge* - capacidade até $50\text{ N}$) para balanceamento do braço.
* Dispositivo de mira e alinhamento radiológico com retículo e esfera de chumbo.
* Graxa técnica e graxa dielétrica de alta isolação para conectores HV.

---

### 3. PROCEDIMENTO DE DESMONTAGEM E SUBSTITUIÇÃO DO MONOBLOCO

#### ETAPA 1: Travamento Mecânico do Braço Telescópico
> [!CAUTION]
> **PERIGO DE LANÇAMENTO BRUSCO DO BRAÇO:**  
> O braço do MobileDaRt possui molas internas de contrapeso sob fortíssima tensão.  
> Ao remover o peso do monobloco do tubo, **o braço tenderá a subir com extrema violência**.  
> **Trave o braço rigidamente** com os parafusos de retenção mecânica e cinta antes de soltar o tubo!

1. Abaixe o braço até a posição horizontal e posicione um calço de madeira/espuma firme sob o cabeçote.
2. Desligue o disjuntor principal da máquina e descarregue os capacitores internos (conector CN1 no DISCHARGE da placa `MUX CAPACITOR`).
3. Remova a carenagem plástica de proteção do cabeçote e os suportes laterais.
4. Desconecte com cuidado os cabos de alta tensão catódico e anódico, cobrindo os terminais com sacos plásticos limpos para evitar poeira no silicone isolante.
5. Desconecte o chicote do sensor térmico do tubo (*thermal switch*) e os cabos do estator de rotação do anodo.
6. Solte o colimador óptico desaparafusando o anel de montagem superior e apoie-o em local seguro.
7. Com o auxílio de um segundo técnico, solte as porcas de fixação do munhão do tubo utilizando o alicate para porcas *FU Lock Nut AW04*.
8. Remova o tubo defeituoso e posicione o novo tubo de raios-X original Shimadzu no suporte articulado.
9. Reaperte a porca de fixação e trave o anel de segurança.
10. Remonte o colimador óptico no flange inferior do novo tubo.
11. Reconecte os cabos de alta tensão aplicando uma película uniforme de óleo/silicone dielétrico livre de bolhas de ar nos receptáculos.

---

#### ETAPA 2: Centralização do Colimador e Ponto Focal de Raio-X (Seção 11.5)
1. Conecte a alimentação e ligue o equipamento.
2. Posicione a placa de teste de centralização com esfera de chumbo no centro da mesa/detector a $100\text{ cm}$ de distância (DFF).
3. Acenda a lâmpada do colimador: centralize rigorosamente a sombra da esfera de chumbo sobre o retículo luminoso em cruz.
4. Execute uma exposição radiográfica de teste em **$55\text{ kV} / 5\text{ mAs}$**.
5. Analise a imagem radiográfica obtida no detector digital:
   - Verifique a posição da imagem radiográfica da esfera em relação ao centro geométrico da colimação.
   - O desvio entre o centro do feixe de raios-X e o centro do campo luminoso **não pode ultrapassar $\pm 1,0\text{ mm}$**.
6. Caso haja desvio:
   - Afrouxe ligeiramente os 4 parafusos de fixação do colimador no flange do tubo.
   - Desloque o colimador suavemente nos eixos $X$ e $Y$ para compensar o desvio medido.
   - Reaperte os parafusos de fixação e repita o disparo de conferência até atingir alinhamento perfeito.

---

#### ETAPA 3: Aquecimento do Novo Tubo (Warm-Up Obrigatório)
* Execute a rotina de 13 passos escalonados (**`tUbeUP`** de $60\text{ kV}$ a $133\text{ kV}$) com as lâminas do colimador 100% fechadas, conforme detalhado na IT-RXM-SHIM-003.

---

### 4. CHECKLIST DE LIBERAÇÃO
- [ ] Porca FU Lock Nut travada e munhão articulado sem folgas axiais.
- [ ] Conectores de alta tensão limpos, com silicone dielétrico e sem vazamentos.
- [ ] Cabo de terra de proteção do tubo rigidamente parafusado ao chassi ($< 0,1\ \Omega$).
- [ ] Sensor de sobretemperatura do tubo (termostato) testado e operacional.
- [ ] Centralização do foco de raio-X com o colimador comprovada em $< 1,0\text{ mm}$.
- [ ] Ciclo de Warm-Up completo executado sem arcos de alta tensão.
