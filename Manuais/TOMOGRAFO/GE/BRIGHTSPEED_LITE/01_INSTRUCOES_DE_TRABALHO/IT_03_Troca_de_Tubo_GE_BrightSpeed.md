# INSTRUÇÃO DE TRABALHO: TROCA DE TUBO DE RAIO-X

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-003`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## 1. Objetivo e Escopo

Esta Instrução de Trabalho (IT) padroniza o procedimento de **remoção, inspeção óptica de filtros, substituição mecânica/elétrica e calibração de tubo de Raio-X** no tomógrafo computadorizado **GE BrightSpeed Lite / Select Series**.

* **Tempo Médio Estimado:** 1 hora de preparação / 6 a 8 horas de alinhamentos e calibrações.
* **Mão de Obra Mínima:** 2 Técnicos Especialistas em Tomografia Computadorizada.

---

## 2. Ferramentas, Instrumentos Especiais & Consumíveis

### 2.1. Ferramental Especial (com Part Number Oficial GE)
| Instrumento / Dispositivo Especial | Part Number GE | Quantidade | Finalidade Técnica |
| :--- | :---: | :---: | :--- |
| **Ponta de Torquímetro Crowfoot 18 mm** | `5263871` (Proto 4918M) | 1 un. | Montagem a 90° em torquímetro 3/8" para parafusos M12 do tubo |
| **Torquímetro de Precisão (3/8" drive)** | Comercial | 1 un. | Aperto controlado dos parafusos de sustentação |
| **Braço e Poste de Içamento (Lifting Post & Boom)** | Oficial GE | 1 un. | Estrutura de fixação da talha no gantry |
| **Talha de Corrente (Chain Hoist)** | Oficial GE | 1 un. | Içamento controlado do conjunto do tubo (~100 kg) |
| **Chave Especial de Alta Tensão (Spanner Wrench)** | Oficial GE | 1 un. | Aperto do anel de vedação dos cabos anodo e catodo |
| **Lanterna LED de Alta Potência** | Comercial | 1 un. | Inspeção óptica do filtro de cobre (*Copper Filter*) e *Bowtie Filter* |
| **Kit Descarregador de Alta Tensão** | `2345332` | 1 un. | Aterramento das pontas dos cabos HV na carcaça do gantry |

### 2.2. Peças e Consumíveis Críticos
* **Tubo de Raio-X Novo:** Compatível com BrightSpeed Lite (Performix Lite / Solarix).
* **Parafusos e Arruelas de Montagem M12:** 4 parafusos novos (**descarte obrigatório dos parafusos usados**).
* **Óleo Mineral Dielétrico (Tube Oil):** Para eliminação de bolsas de ar nos conectores HV.
* **Abraçadeiras Plásticas (Tie-wraps):** Para recapeamento dos cabos nos pontos originais.
* **Lenços Kimwipes e Álcool Isopropílico 99.8%:** Para descontaminação do colimador e lentes.

---

## 3. Protocolos de Segurança Críticos & Bloqueio LOTO

> [!CAUTION]
> **PERIGO DE MORTE: ROTAÇÃO VIOLENTA DO GANTRY POR DESBALANCEAMENTO**
> O tubo de Raio-X é o componente individual mais pesado do rotor. **Se a trava mecânica de rotação do gantry (Rotational Lock) não estiver firmemente engatada, ao retirar o tubo o gantry girará violentamente devido ao desbalanço de peso, com risco de mutilação ou morte do técnico**.
> *Regra de Ouro:* Antes de soltar a talha ou os parafusos M12, force manualmente o gantry em ambos os sentidos para ter certeza absoluta de que o pino de trava está travado!

> [!WARNING]
> **CUIDADOS COM O FILTRO DE COBRE (COPPER FILTER) E BOWTIE:**
> O filtro primário de cobre e o filtro bowtie no colimador são extremamente sensíveis. **Qualquer risco, arranhão, marca de dedo ou poeira provocará artefatos circulares em anel (Ring Artifacts) nas imagens dos pacientes**. A inspeção visual detalhada com lanterna é obrigatória antes de colocar o tubo novo.

---

## 4. Passo a Passo Operacional (Execução em Campo)

### FASE 1: Registro Obrigatório de Dados no Software (ANTES DE DESMONTAR)
> [!IMPORTANT]
> A entrada dos dados do tubo novo no software DEVE ser realizada **ANTES** da troca física. Caso contrário, o sistema registrará acúmulo de calor de 100% no tubo velho e bloqueará disparos por horas!

1. No console de controle, abra o **[SERVICE DESKTOP]**.
2. Acesse: `[REPLACEMENT]` -> `[TUBE CHANGE]` -> `[NEW TUBE CONFIG]`.
3. Selecione o motivo de falha (*Tube Unit Failure Code*).
4. Digite com atenção o **Insert Serial #** e o **Housing Serial #** da etiqueta do novo tubo.
5. Clique em **OK** para salvar na base do tomógrafo.

---

### FASE 2: Desmontagem Mecânica e Travamento
1. Desative as chaves no painel de serviço (*Service Switch Panel*):
   * `AXIAL DRIVE ENABLE` -> OFF
   * `HVDC ENABLE` -> OFF
   * `120VAC` -> OFF
2. Desligue a alimentação do disjuntor principal da sala (PDU) e aplique cadeado/etiqueta LOTO.
3. Remova as carenagens lateral, superior e frontal do gantry.
4. Gire manualmente o gantry até que o tubo fique na **posição das 2 horas (2 o'clock)**.
5. Remova os **2 parafusos M12 e arruelas do lado direito do tubo** (visto pela frente do gantry).
6. Continue girando o gantry até que o tubo atinja a **posição exata das 3 horas (3 o'clock / 90 graus)**.
7. **Engate o pino de trava mecânica de rotação (Gantry Rotational Lock)**. Force o gantry manualmente para confirmar travamento total!
8. Monte o poste de sustentação, o braço e a talha de corrente. Engate os ganchos nos olhais do tubo e tensione a corrente sem folgas.

---

### FASE 3: Desconexões e Içamento
1. Desconecte o cabo de identificação do tubo (12 pinos) no topo da carcaça.
2. Desconecte o conector de 4 pinos de alimentação da bomba de circulação e ventoinha.
3. Corte com alicate rente as abraçadeiras dos cabos de alta tensão.
4. Com a **chave Spanner**, solte os anéis metálicos dos conectores HV (Anodo e Catodo).
5. Puxe os terminais dos cabos HV para fora dos poços e **aterre imediatamente as pontas na carcaça metálica do gantry** para dissipar cargas capacitivas residuais.
6. Limpe qualquer óleo derramado com lenços Kimwipes e tampe os orifícios do tubo velho.
7. Remova os **outros 2 parafusos de montagem M12**. **Descarte os 4 parafusos velhos no lixo técnico**.
8. Acione a talha lentamente e balance suavemente o tubo liberando-o do rotor do gantry.
9. Desça o tubo até o chão sobre um estrado acolchoado.

---

### FASE 4: Inspeção Óptica dos Filtros Primários (Anti-Artefatos)
1. **Inspeção do Filtro de Cobre (Primary Copper Filter):**
   * Com uma lanterna LED brilhante, inspecione a superfície do filtro de cobre montado na boca do colimador.
   * O filtro deve estar totalmente limpo, brilhante, sem amassados, riscos, impressões digitais ou poeiras.
2. **Inspeção do Filtro Bowtie:**
   * Remova a tampa de chapa da placa de controle do colimador (*Collimator Control Board Cover*).
   * Verifique se as lentes do filtro bowtie estão desobstruídas e sem trincas. *Atenção:* Nunca force o filtro com a mão para não quebrar a chave de fim de curso ou o parafuso de avanço do micromotor.

---

### FASE 5: Instalação do Tubo Novo
1. Se o tubo novo já veio de fábrica com a placa de fixação instalada, **NÃO REMOVA A PLACA**.
2. Engate a talha no tubo novo e ice-o suavemente até a sede no rotor do gantry.
3. Encaixe o tubo na posição das 3 horas e aponte os **4 parafusos M12 novos** com arruelas novas.
4. Monte a ponta especial Crowfoot de 18 mm (`Proto 4918M / P/N 5263871`) no torquímetro de 3/8" **em ângulo de 90 graus** em relação ao cabo para manter a calibragem exata do braço de alavanca.
5. Aperte os parafusos M12 com o torque especificado em padrão cruzado.
6. **Tratamento dos Conectores HV:**
   * Injete óleo isolante de alta tensão nos poços do tubo novo.
   * Insira firmemente os conectores de alta tensão e aperte os anéis com a chave Spanner até o batente.
7. Reconecte o cabo de 12 pinos do ID do tubo e o cabo de 4 pinos da bomba/cooler.
8. Amarre os cabos de alta tensão com novas abraçadeiras plásticas respeitando o raio mínimo de curvatura ($> 6,35\text{ cm}$).
9. Desmonte a talha e **remova o pino de trava de rotação do gantry**.
10. Religue o disjuntor da sala e ligue as chaves `120VAC`, `AXIAL DRIVE` e `HVDC` no painel de serviço.
11. Aguarde **no mínimo 10 minutos** com o filamento aquecendo antes de iniciar os disparos de teste.

---

## 5. Sequência Oficial de Calibração e QA
Conclua executando a esteira de calibrações no software de serviço:
1. `Gantry Rotation Safety Check`
2. `Reset TnT Data`
3. `Alinhamentos Ópticos (BOW, CBF, SAG, POR, ISO)`
4. `Calibração de Filamento (Small e Large Focus)`
5. `Balanceamento Dinâmico do Gantry`
6. `Air Cal & Detailed Calibration`
7. `QA Test Final com Phantom (Água: 0 ± 4 HU)`.

---
*eMED Eletromedicina Ltda. • Suporte Técnico e Diagnóstico por Imagem*
