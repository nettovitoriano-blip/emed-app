# INSTRUÇÃO DE TRABALHO TÉCNICA - eMED BIOMEDICAL
## IT-RX-LOT-001: Vistoria Técnica de Pré-Instalação, Adequação Elétrica e Blindagem Radiológica (Lotus HF500M)
**Equipamento:** Gerador e Sistema de Raio-X Fixo Lotus HF500M (50 kW / 500 mA)  
**Documento Base:** Manual Oficial de Pré-Instalação Lotus & Protocolo eMED Gatekeeper  
**Nível de Acesso:** Engenharia Clínica / Especialista de Infraestrutura Hospitalar  
**Revisão:** 1.0 - Procedimento de Liberação Predial Pré-Entrega  

---

### 1. OBJETIVO E ESCOPO
Padronizar a inspeção técnica presencial (*site survey*) para validação e liberação de salas de exames radiológicos destinadas a receber o equipamento Lotus HF500M, garantindo conformidade com a RDC 611/2022 (ANVISA), normas NBR 5410 / NBR IEC 60601 e requisitos do fabricante.

---

### 2. INFRAESTRUTURA ELÉTRICA OBRIGATÓRIA

> [!CAUTION]
> **CAPACIDADE DE POTÊNCIA DA SUBESTAÇÃO:**  
> O gerador HF500M exige potência instantânea de pico de **$60\text{ kVA}$** durante exposições radiográficas. Redes subdimensionadas causam queda brusca de tensão ($> 5\%$), gerando subexposição e alarmes de falha de kV no painel.

| Requisito Elétrico | Especificação Técnica Mandatória | Método de Validação |
| :--- | :--- | :--- |
| **Alimentação** | Trifásico $380\text{V AC} \pm 10\%$ (ou Bifásico $220\text{V}$ sob consulta) | Multímetro True-RMS entre fases |
| **Frequência** | $60\text{ Hz} \pm 1\text{ Hz}$ | Frequencímetro |
| **Disjuntor Geral** | Caixa moldada termomagnético de **$100\text{A}$** curva C | Inspeção visual no quadro da sala |
| **Bitola dos Cabos** | Mínimo **$25\text{ mm}^2$** (cobre eletrolítico 750V) | Verificação física da fiação no quadro |
| **Aterramento** | Malha de aterramento independente com resistência **$< 5\ \Omega$** | Terrômetro de quatro pontas |
| **Queda de Tensão Máxima** | Não exceder $3\%$ em carga plena de disparo | Medição em carga de teste |

---

### 3. DIMENSÕES DA SALA E PROTEÇÃO RADIOLÓGICA (BARITAMENTO)

* **Área Mínima Recomendada:** $\ge 18\text{ m}^2$ (com pé-direito mínimo de $2,70\text{ m}$ para elevação livre da coluna porta-tubo).
* **Blindagem das Paredes:**
  * Argamassa baritada com espessura mínima equivalente a **$2,0\text{ mm Pb}$** até a altura de $2,10\text{ m}$.
  * Portas de acesso blindadas com chapa de chumbo interna de **$2,0\text{ mm Pb}$** e batedor duplo.
* **Cabine de Comando:**
  * Anteparo fixo de proteção do operador com visor de **vidro plumbífero** ($2,0\text{ mm Pb}$) medindo no mínimo $30\times 40\text{ cm}$.
  * Botoeira de disparo instalada internamente à cabine, impedindo disparo fora da área protegida.

---

### 4. CANALETAS E PASSAGEM DE CABOS SUBTERRÂNEOS
* Canaletas embutidas no piso com dimensões mínimas de **$15\text{ cm}$ de largura por $10\text{ cm}$ de profundidade**, com tampas metálicas reforçadas.
* Separação física: os cabos de alta tensão e potência devem ser acomodados afastados de cabos lógicos de rede de dados e botoeira para evitar interferência eletromagnética (EMI).

---

### 5. CHECKLIST DE LIBERAÇÃO DE PRÉ-INSTALAÇÃO (GATEKEEPER eMED)

- [ ] Tensão entre fases medida e estável em $380\text{V} \pm 5\%$.
- [ ] Resistência de aterramento medida com terrômetro comprovada em $< 5\ \Omega$.
- [ ] Disjuntor termomagnético de 100A exclusivo instalado a no máximo 5 metros da mesa de comando.
- [ ] Canaletas subterrâneas limpas, secas e com guias de passagem instaladas.
- [ ] Parede baritada e porta de chumbo com laudo de radioproteção aprovado por físico médico.
- [ ] Iluminação de sinalização vermelha ("RAIO-X EM OPERAÇÃO") instalada sobre a porta externa e intertravada.
- [ ] Sala liberada para recebimento e desembalagem do equipamento Lotus HF500M.
