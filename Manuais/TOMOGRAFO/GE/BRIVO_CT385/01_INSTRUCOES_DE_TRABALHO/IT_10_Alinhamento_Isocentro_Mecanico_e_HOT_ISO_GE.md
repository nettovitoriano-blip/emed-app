# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-010)
## Alinhamento do Isocentro Mecânico (ISO) & Alinhamento com Feixe Ativo (HOT ISO)
### Tomógrafos GE Healthcare (Linhas Brivo CT385 e BrightSpeed Series)
*Baseado nos manuais oficiais GE Direction 5438996-8EN / 5181178 (Procedimentos Oficiais 09 e 10)*

---

### 1. OBJETIVO & ESCOPO
Padronizar o alinhamento da linha de centro do feixe de Raio-X em relação ao **Isocentro Físico de Rotação (ISO)** e a validação sob emissão ativa com aquecimento térmico do ânodo (**HOT ISO**).

---

### 2. FERRAMENTAS & INSTRUMENTOS EXIGIDOS
* **Pino Centralizador de Isocentro GE (ISO Alignment Pin)** com suporte de mesa;
* **Nível Óptico / Mira Centralizadora do Colimador**;
* **Torquímetros de Precisão** (M8 e M10 para chassi do detector e suportes do tubo);
* **Console de Serviço (Service Desktop)** com módulo de diagnóstico de imagem ativo.

---

### 3. PROCEDIMENTO 1: ALINHAMENTO DO ISOCENTRO MECÂNICO (ISO ALIGNMENT)

```
                 [ TUBO DE RAIO-X (0 Graus) ]
                              |
                     (Feixe Central de RX)
                              v
             +------- [ PINO DE ISOCENTRO ] -------+
             |         (Centro da Abertura)        |
                              v
       =================================================
       [ Matriz Central do Detector Multislice          ]
       =================================================
```

#### 3.1 Instalação e Varredura Axial
1. Instale o pino de alinhamento ISO no suporte fixado na cabeceira da mesa do paciente.
2. Com as luzes laser de alinhamento, posicione o pino exatamente no centro do gantry (eixos X=0, Y=0).
3. No Service Desktop, acerte o menu **Diagnostics** $\rightarrow$ **ISO Alignment Process**.
4. O tomógrafo executará disparos estáticos nas posições de $0^\circ, 90^\circ, 180^\circ$ e $270^\circ$.
5. O software calcula o centro de gravidade da sombra radiográfica do pino em relação ao canal central do detector.

#### 3.2 Tolerâncias e Ajuste
* **Especificação de Desvio Central:** O centro do feixe deve coincidir com o isocentro com tolerância máxima de **$\pm 0,25\text{ mm}$**.
* Se o resultado estiver fora de especificação:
  * Ajuste os parafusos de empuxo lateral do colimador primário;
  * Repita a varredura até obter status **PASS** (verde) na tela.

---

### 4. PROCEDIMENTO 2: ALINHAMENTO HOT ISO (SOB EMISSÃO ATIVA E AQUECIMENTO)

Durante a rotação e aquecimento contínuo do tubo, a dilatação térmica do ânodo e o estresse mecânico podem causar uma leve deflexão focal (*focal spot drift*). O procedimento **HOT ISO** quantifica e compensa essa deflexão.

1. No Service Desktop, selecione **HOT ISO Alignment**.
2. **Ciclo de Aquecimento Térmico:** O tomógrafo executa uma rotina de pré-aquecimento do tubo de Raio-X elevando a capacidade térmica para aproximadamente **$50\%$ a $60\%$ de Joules**.
3. Imediatamente após o aquecimento, o software dispara a sequência de varreduras rápidas HOT ISO.
4. O algoritmo compara a posição do ponto focal a quente com a posição a frio gravada no teste ISO inicial.
5. Se o desvio térmico for inferior a **$0,08\text{ mm}$**, o sistema aprova automaticamente e grava a matriz de correção térmica na NVRAM.

---

### 5. CHECKLIST FINAL
* [ ] ISO Alignment aprovado com desvio $\le 0,25\text{ mm}$;
* [ ] HOT ISO executado com tubo aquecido e correção térmica salva;
* [ ] Pino de alinhamento removido da mesa e guardado no estojo de ferramentas.
