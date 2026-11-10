# IT-MM-SIEM-001: Calibração de Força de Compressão, AEC e Qualidade de Imagem em Mamógrafos Siemens Mamomat

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-MM-SIEM-001`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## 1. OBJETIVO & ESCOPO
Padronizar a rotina de manutenção preventiva, calibração biomédica e testes de constância conforme as normas **ANVISA RDC 611** e **Instrução Normativa IN 92/2021** para a linha de mamógrafos Siemens Mamomat (Inspiration, Revelation e Novation).

## 2. FERRAMENTAL & PADRÕES REQUERIDOS
- Dinamômetro mecânico calibrado (0 a 300 N) com bloco atenuador de espuma.
- Phantom mamográfico padronizado de acrílico (PMMA 45 mm) conforme ICRU.
- Medidor de radiação multi-parâmetro para feixes de Molibdênio/Ródio (Mo/Mo, Mo/Rh, W/Rh).
- Trena métrica e nível laser de precisão.

## 3. PROCEDIMENTOS DE CALIBRAÇÃO PASSO A PASSO

### 3.1 Teste e Ajuste da Força de Compressão Motorizada e Manual
1. Posicionar o bloco atenuador de espuma no bucky de compressão.
2. Acionar a compressão motorizada através do pedal duplo até o travamento automático.
3. Verificar a indicação na escala digital do display:
   - Força motorizada máxima permitida: entre **150 N e 200 N** (15 kgf a 20 kgf).
   - Se a força ultrapassar 200 N, interromper imediatamente e ajustar o trimpot de torque no servo motor da torre.
4. Acionar a liberação de emergência mecânica e manual, garantindo destravamento instantâneo em caso de queda de energia.

### 3.2 Calibração do Controle Automático de Exposição (AEC)
1. Colocar o phantom de PMMA centralizado na posição da mama.
2. Posicionar o sensor da câmara de ionização na posição 2 (intermediária).
3. Selecionar modo AEC em 28 kVp feixe Mo/Mo.
4. Realizar 3 disparos consecutivos e anotar a reprodutibilidade da densidade óptica (DO):
   - Coeficiente de variação de DO deve ser $\le 0.05$.
   - A espessura comprimida indicada no display deve coincidir com $\pm 2	ext{ mm}$ do phantom.

### 3.3 Verificação de Alinhamento do Campo de Luz e Campo de Radiação
- A coincidência entre as bordas do feixe luminoso e o detector digital não pode exceder 1% da distância foco-receptor (DFR).

> [!CAUTION]
> Durante os disparos de teste, todo o pessoal não essencial deve permanecer fora da sala blindada com biombo de chumbo de pelo menos .5	ext{ mm Pb}$ equivalente.

## 4. CHECKLIST FINAL DE LIBERAÇÃO
- [ ] Força de compressão dentro da faixa segura (150 a 200 N).
- [ ] Liberação mecânica de emergência 100% operacional.
- [ ] Bucky livre de folgas ou resíduos biológicos.
- [ ] Reprodutibilidade de kerma no ar e kVp aprovada.
- [ ] Emissão de certificado de calibração anual conforme RDC 611.
