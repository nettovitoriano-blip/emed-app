# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-006)
## Alinhamentos Ópticos & Calibrações do Colimador e Detector
### Tomógrafos GE Healthcare (Linhas Brivo CT385 e BrightSpeed Series)

---

### 1. OBJETIVO & ESCOPO
Padronizar o roteiro de alinhamento geométrico, centragem do feixe de Raio-X (*Beam on Window - BOW*), alinhamento do filtro e sag do colimador (*CBF/SAG*) e calibração de abertura após intervenções no tubo, colimador ou conjunto detector.

---

### 2. FERRAMENTAS & INSTRUMENTOS OBRIGATÓRIOS
* **Kit de Calibração Óptica GE:**
  * Relógio comparador (*Dial Indicator*) com suporte magnético articulado;
  * Ferramenta de ajuste de âncoras do Detector (Z-axis Anchor Adjuster);
  * Chave de ajuste do CBF (Collimator Beam Filter Adjuster).
* **Torquímetros de Precisão:**
  * Torquímetro para parafusos M14 (capacidade até **$96\text{ N}\cdot\text{m}$**);
  * Torquímetro padrão para parafusos de flange M8 (**$30,5\text{ N}\cdot\text{m}$**) e trava M6 (**$13,5\text{ N}\cdot\text{m}$**).
* **Fantoma de Alinhamento e Centralizador Laser** (Luzes de posicionamento validadas).

---

### 3. PROCEDIMENTO 1: ALINHAMENTO DO FEIXE NA JANELA (BEAM ON WINDOW - BOW)

O teste BOW alinha o feixe central emitido pelo ponto focal do tubo de Raio-X com a abertura sensível do conjunto detector ao longo do eixo longitudinal Z.

```
                  [ TUBO DE RAIO-X (0 Graus) ]
                              |
                              | Feixe de RX (Colimado)
                              v
       =================================================
       [ Abertura / Janela de Entrada do Detector (Z)   ]
       =================================================
```

#### 3.1 Execução no Software (Service Desktop)
1. Certifique-se de que as **luzes laser de posicionamento** estejam devidamente calibradas e aferidas.
2. Acesse o **Service Desktop** $\rightarrow$ **Diagnostics** $\rightarrow$ **Beam on Window (BOW) Alignment**.
3. Posicione o Gantry com o tubo em **$0^\circ$ (12 horas / 12 o'clock)**.
4. Clique em **[Scan]** para disparar a exposição de referência do BOW.
5. Clique em **[Calculate]**: o software processará o perfil de intensidade nos canais limítrofes do detector.
6. **Avaliação dos Resultados:**
   * Se o resultado exibir `IN SPECIFICATION`: O alinhamento do eixo Z está correto. Não requer ajustes mecânicos.
   * Se exibir `OUT OF SPECIFICATION`: O software indicará o valor de deslocamento em milímetros (*Offset*) e a quantidade de voltas nas âncoras.

#### 3.2 Ajuste Mecânico do Detector (Eixo Z)
1. **Segurança LOTO:** Desligue no painel de chaves de serviço (*Service Switch Panel*):
   * Chave `HVDC` $\rightarrow$ **OFF**;
   * Chave `Axial Enable` $\rightarrow$ **OFF**;
   * Chave `120VAC` $\rightarrow$ **OFF**.
2. Afrouxe o parafuso de trava M6 e os 2 parafusos sextavados de flange M8 do detector.
3. Ajuste os **3 reguladores de âncora (*Anchor Adjusters*)**:
   * **Regra de Conversão GE:** Cada volta completa no regulador desloca o detector em passos definidos na tela (siga rigorosamente a fração calculada).
4. **Torques de Travamento:**
   * Aperte os parafusos sextavados de flange M8 com torque de **$30,5\text{ N}\cdot\text{m}$ ($22,5\text{ ft}\cdot\text{lb}$)**;
   * Aperte o parafuso de trava M6 com torque de **$13,5\text{ N}\cdot\text{m}$ ($10,0\text{ ft}\cdot\text{lb}$)**.
5. Religue as chaves de serviço (`120VAC`, `Axial Enable`, `HVDC`).
6. Clique em **[Restart]** e execute nova varredura até obter aprovação (**PASS**).

---

### 4. PROCEDIMENTO 2: ALINHAMENTO CBF E SAG DO COLIMADOR

O alinhamento CBF (*Collimator Beam Filter*) assegura que os filtros de feixe de teflon/alumínio fiquem perfeitamente centrados no plano X-Y e que a deflexão mecânica (*SAG*) sob rotação seja compensada.

#### 4.1 Preparação do Relógio Comparador
* Fixe a base magnética do relógio comparador no corpo do Gantry.
* Posicione a ponta apalpadora do relógio **rigorosamente perpendicular** à superfície de medição do bloco do colimador.
* Zere o relógio comparador na posição de repouso.

#### 4.2 Medição e Compensação do Deslocamento
1. No Service Desktop, execute o aplicativo **CBF / SAG Alignment**.
2. O sistema executa exposições a $0^\circ$, $90^\circ$, $180^\circ$ e $270^\circ$ para mapear o vetor de gravidade e folga mecânica.
3. Se o desvio estiver fora da especificação:
   * **Se o deslocamento (*Collimator Shift*) for POSITIVO:** Gire o ajustador do CBF no **sentido HORÁRIO (CW)**;
   * **Se o deslocamento (*Collimator Shift*) for NEGATIVO:** Gire o ajustador do CBF no **sentido ANTI-HORÁRIO (CCW)**.
4. Acompanhe a leitura física no relógio comparador até coincidir com o valor solicitado pelo software.
5. **Aperto Final:** Aperte os parafusos de fixação M14 do suporte do colimador com torquímetro certificado a **$96,0\text{ N}\cdot\text{m}$ ($70,8\text{ ft}\cdot\text{lb}$)**.

---

### 5. PROCEDIMENTO 3: CALIBRAÇÃO DAS ABERTURAS DO COLIMADOR (APERTURE CAL)

1. No menu de calibrações, selecione **Collimator Calibration**.
2. O programa atuará os servomotores dos cames de abertura primária e secundária para todas as espessuras de corte nominal ($0.625\text{ mm}, 1.25\text{ mm}, 2.5\text{ mm}, 5.0\text{ mm}, 10.0\text{ mm}$).
3. **Critério de Aceitação:** Todas as espessuras de fatia devem apresentar perfil homogêneo sem sombras (*shadowing*) nas bordas do detector.
4. Salve o arquivo de calibração gerado no disco do host.

---

### 6. CHECKLIST FINAL DE LIBERAÇÃO
* [ ] BOW dentro da tolerância de fábrica (resultado verde na tela do console);
* [ ] Parafusos de fixação do detector torquiados a **$30,5\text{ N}\cdot\text{m}$** (M8) e **$13,5\text{ N}\cdot\text{m}$** (M6);
* [ ] Fixadores M14 do colimador torquiados a **$96,0\text{ N}\cdot\text{m}$**;
* [ ] Relógio comparador e suportes magnéticos removidos do Gantry antes de qualquer rotação rápida;
* [ ] Imagem do fantoma de QA livre de artefatos em anel (*ring artifacts*) ou bandas de sombreamento.
