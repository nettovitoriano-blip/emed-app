# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-012)

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-012`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## Checagem de Segurança de Rotação, Varreduras Térmicas HHS & Teste de Estabilidade
### Tomógrafos GE Healthcare (Linhas Brivo CT385 e BrightSpeed Series)
*Baseado nos manuais oficiais GE Direction 5438996-8EN / 5181178 (Procedimentos Oficiais 15, 16 e 17)*

---

### 1. OBJETIVO & ESCOPO
Padronizar a checagem das travas de segurança de rotação do Gantry (*Gantry Rotation Safety Check*), a execução dos disparos de condicionamento térmico anódico em alta rotação (*HHS - High Heat Storage Scans*) e o teste de varredura e estabilidade contínua (*System Scanning Test*).

---

### 2. PROCEDIMENTO 1: CHECAGEM DE SEGURANÇA DE ROTAÇÃO DO GANTRY

Antes de autorizar qualquer rotação contínua em velocidade máxima ($0,5\text{ s}$ por volta), é obrigatório checar os dispositivos de intertravamento de emergência:

```
                  +-----------------------------------+
                  |  CIRCUITO DE PARADA DE EMERGÊNCIA |
                  +-----------------+-----------------+
                                    |
             +----------------------+----------------------+
             |                                             |
   [ Botoeiras de Emergência ]                   [ Microchaves das Tampas ]
   (Console, Gantry e Mesa)                      (Sensores de Fechamento)
```

1. **Teste das Botoeiras de Emergência (E-Stop):**
   * Pressione o botão vermelho de emergência do console do operador durante uma rotação de teste: o freio eletromagnético axial deve atuar imediatamente, parando o Gantry em menos de **$3\text{ segundos}$**;
   * Repita o teste para as botoeiras instaladas nas laterais do Gantry e na base da mesa;
2. **Teste das Microchaves de Fechamento das Coberturas (Cover Interlocks):**
   * Com o Gantry estacionário, abra levemente uma das tampas plásticas frontais: o sistema deve indicar no painel do gantry e no console `Cover Open` e desabilitar o contator de potência da rotação.

---

### 3. PROCEDIMENTO 2: VARREDURAS DE CONDICIONAMENTO TÉRMICO HHS (HIGH HEAT STORAGE)

As varreduras HHS submetem o tubo de Raio-X a uma carga térmica progressiva e controlada, estabilizando a pressão de vácuo interna do invólucro do tubo e assentando os mancais do ânodo giratório em alta rotação.

1. No Service Desktop, abra o utilitário **[Diagnostics]** $\rightarrow$ **[X-Ray Generation]** $\rightarrow$ **[HHS Scans]**.
2. **Ciclo de Disparos Progressivos:**
   * **Nível 1 (Carga Leve):** $100\text{ kV}, 80\text{ mA}, 1,0\text{ s}$ (Rotação de $1,0\text{ s}$);
   * **Nível 2 (Carga Média):** $120\text{ kV}, 150\text{ mA}, 1,0\text{ s}$ (Rotação de $0,8\text{ s}$);
   * **Nível 3 (Carga Alta):** $120\text{ kV}, 250\text{ mA}, 1,0\text{ s}$ (Rotação de $0,6\text{ s}$);
   * **Nível 4 (Carga Máxima de Estresse):** $140\text{ kV}, 300\text{ mA}, 1,0\text{ s}$ (Rotação de $0,5\text{ s}$).
3. **Monitoramento de Temperatura:** Acompanhe a barra gráfica de calor do tubo no monitor. Ela deve subir uniformemente até $70-80\%$ e a taxa de resfriamento do trocador de calor de óleo (*Oil Heat Exchanger*) deve manter o gradiente sem alarmes de temperatura de óleo (`T-Oil Alarm`).
4. Clique em **[HHS Report]** e salve o laudo de estabilidade térmica.

---

### 4. PROCEDIMENTO 3: TESTE DE VARREDURA E ESTABILIDADE DO SISTEMA (SYSTEM SCANNING TEST)

O teste de estabilidade simula uma rotina pesada de exames de pronto-socorro / hospital geral:
1. Monte o phantom de água no centro do gantry;
2. Programe uma rotina de **20 exames contínuos** simulando protocolos de Crânio, Tórax e Abdome Total;
3. Execute a sequência completa;
4. **Critérios de Aprovação:**
   * Zero interrupções por erro de comunicação HSDCD / Slip Ring;
   * Zero erros de sincronismo do inversor de alta tensão (*Inverter Trip*);
   * Todas as imagens reconstruídas no PACS sem artefatos ou travamento da fila de reconstrução DICOM.

---

### 5. CHECKLIST DE ENCERRAMENTO
* [ ] Todas as botoeiras de emergência e travas de tampas testadas e aprovadas;
* [ ] Varreduras HHS concluídas sem arco elétrico (*spit*) ou ruído anormal no ânodo;
* [ ] Sequência contínua de varreduras finalizada com sucesso e laudo anexado ao chamado eMED.
