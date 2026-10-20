# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-009)
## Alinhamento do Plano de Rotação (Plane of Rotation - POR)
### Tomógrafos GE Healthcare (Linhas Brivo CT385 e BrightSpeed Series)
*Baseado no manual oficial GE Direction 5438996-8EN / 5181178 (Procedimento Oficial 07)*

---

### 1. OBJETIVO & ESCOPO
Padronizar a execução do procedimento de alinhamento do **Plano de Rotação (POR)** do anel rotativo do Gantry em relação ao eixo de translação da mesa do paciente (eixo Z). 

Este alinhamento é estritamente obrigatório após:
* Substituição ou reposicionamento do rolamento principal do Gantry (*Main Bearing*);
* Nivelamento e ancoragem do chassi do Gantry no piso da sala;
* Troca estrutural de componentes pesados que alterem a perpendicularidade do anel.

---

### 2. FERRAMENTAS & INSTRUMENTOS EXIGIDOS
* **Dispositivo Oficial de Fixação POR (POR Alignment Fixture / Pin)**;
* **Relógio Comparador de Precisão (*Dial Indicator*) com resolução de $0,01\text{ mm}$** e base magnética;
* **Calibre de Lâminas (*Feeler Gauge*)**;
* **Kit de Calços Metálicos de Precisão (*Alignment Shims*)** de espessuras variadas ($0,05\text{ mm}$ a $1,0\text{ mm}$);
* **Torquímetro calibrado para parafusos M16 / M20** da base de fixação do Gantry.

---

### 3. POSICIONAMENTO E PREPARAÇÃO
1. Desenergize o equipamento e trave a PDU com etiqueta de bloqueio (LOTO).
2. Remova as coberturas frontal e traseira do Gantry.
3. Posicione o relógio comparador fixado na carcaça estacionária com a ponta de contato perpendicular à pista de referência usinada do anel rotativo.
4. Zere o relógio comparador com o Gantry na posição **$0^\circ$ (12 horas / topo)**.

---

### 4. PROCEDIMENTO DE MEDIÇÃO NAS 4 POSIÇÕES CARDEAIS

```
                              [ 0 Graus - Topo ]
                                      |
       [ 270 Graus - Esquerda ] <-----+-----> [ 90 Graus - Direita ]
                                      |
                            [ 180 Graus - Fundo ]
```

1. Gire o Gantry manualmente e suavemente em sentido horário até a posição **$90^\circ$ (3 horas)**. Anote o valor $\Delta X_1$ exibido no relógio comparador.
2. Continue a rotação até **$180^\circ$ (6 horas)**. Anote o valor $\Delta Y$.
3. Avance para **$270^\circ$ (9 horas)**. Anote o valor $\Delta X_2$.
4. Retorne à posição **$0^\circ$** e confirme se o relógio voltou rigorosamente ao zero inicial.

#### 4.1 Critérios de Tolerância e Cálculo de Calços
* **Especificação de Desvio Máximo:** O batimento angular total do plano de rotação não pode exceder **$0,15\text{ mm}$** em todo o diâmetro de giro.
* Se a diferença entre $0^\circ$ e $180^\circ$ (plano vertical) for superior à tolerância:
  * Solte os parafusos de ancoragem traseiros da base do Gantry;
  * Insira calços (*shims*) sob os pés de nivelamento correspondentes até zerar o erro angular.
* Se a diferença entre $90^\circ$ e $270^\circ$ (plano horizontal) estiver fora de tolerância:
  * Ajuste os parafusos de empuxo lateral da base do Gantry.
* Aperte os parafusos de ancoragem com torquímetro certificado a **$140\text{ N}\cdot\text{m}$**.

---

### 5. CHECKLIST DE LIBERAÇÃO
* [ ] Batimento total do anel nas 4 posições $\le 0,15\text{ mm}$;
* [ ] Parafusos da base torquiados a $140\text{ N}\cdot\text{m}$;
* [ ] Relógio comparador e suportes magnéticos removidos do Gantry antes de religar.
