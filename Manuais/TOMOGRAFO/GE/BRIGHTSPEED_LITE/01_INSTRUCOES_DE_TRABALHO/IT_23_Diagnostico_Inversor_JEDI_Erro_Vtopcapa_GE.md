# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-023)

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-023`<br>**VERSÃO:** `1.0 Homologada`<br>**DATA:** `26/11/2026`<br>**NORMA:** `ANVISA RDC 611 / NBR IEC 60601` |
|:---:|:---|:---|

---

## Diagnóstico Avançado de Falha no Inversor JEDI, Barramento DC e Curto-Circuito em Módulos de Potência (IGBTs/MOSFETs)
### Tomógrafos GE Healthcare (Revolution ACT, Brivo CT385, BrightSpeed e Optima Series)
*Baseado em intervenção técnica de campo EMED & Manuais GE Service Directions (5438996-8EN / 5181178)*

---

### 1. SINTOMATOLOGIA CLÍNICA & CÓDIGOS DE ERRO

* **Comportamento Relatado:** 
  O equipamento realiza o ciclo de aquecimento de tubo (*Tube Warm-up*) normalmente. No entanto, no momento de iniciar o exame com paciente (ao armar a rotação ou iniciar a varredura do Scout/Axial), a emissão é abortada e a Gantry para imediatamente.
* **Mensagem no Console (Common Service Desktop / Error Log):**
  ```text
  Thu Nov 26 09:14:43 2026
  Host: Jedi Ermes #: 260118522
  Exception Class: Abort  Severity: Secondary
  File: gen_exec.cxx  Line#: 3220
  Function: No System Function Reported
  Scan Type: Axial Scan: 50004/1/1
  (587h)Input Stage: Top Capacitor Voltage is too high [Vtopcapa > 400V].
  Z6Z7= 90h,1hl (Vtopcapa = Z7Z6)
  
  Host: orp   Proc: orp_subsys   Error: 260118522 / 260118359
  Host: On Board Rotating Processor  Ermes #: 260118359
  ```

---

### 2. FLUXOGRAMA DE AFERIÇÃO & DIAGNÓSTICO EM CAMPO

#### 2.1 Aferição da Tensão de Alimentação da Rede (AC)
1. Medir a tensão de entrada trifásica nas barras de distribuição da PDU / Trafo de Isolamento:
   * **Fase R-S:** 380 VAC
   * **Fase S-T:** 384 VAC
   * **Fase T-R:** 379 VAC
   * *Status:* Alimentação da concessionária balanceada e dentro da tolerância nominal de ±5%.

#### 2.2 Aferição do Barramento CC (DC Bus - Banco de Capacitores)
1. **Tensão Total do Barramento DC:** Medida em **520 VDC** (Padrão esperado para retificação trifásica de 380 VAC: $380 \times \sqrt{2} \approx 537\text{ VDC}$).
2. **Tensão nos Capacitores Individuais (Divisão Simétrica):**
   * Capacitor Superior ($C_{\text{top}}$): **260 VDC**
   * Capacitor Inferior ($C_{\text{bot}}$): **260 VDC**
   * *Conclusão:* Divisão de tensão perfeitamente simétrica ($260\text{V} + 260\text{V} = 520\text{VDC}$). O banco de capacitores e os resistores de equalização estão intactos.
3. **Tensão na Entrada do Gerador JEDI:** Medida em **519 VDC**, confirmando que a condução pelas pistas do Slip Ring e escovas de alta potência está 100% íntegra.

#### 2.3 Diagnóstico da Placa Inversora de Potência (Linha DC)
1. **Fusível de Proteção Principal de Alta Tensão:**
   * Especificação: **1000V x 20A** (Classe cerâmica ultrarrápida aR).
   * **Teste com Multímetro (Continuidade):** Fusível encontrado **ABERTO (Queimado)**.
   * > [!WARNING]
     > **NUNCA substitua apenas o fusível de 1000V 20A sem antes testar os semicondutores de potência!** Se o fusível abriu, houve curto-circuito severo a jusante. Ligar o gerador com fusível novo sob curto destruirá a trilha da placa ou a controladora de gate (*Gate Driver*).

2. **Teste de Curto-Circuito nos Módulos de Potência (IGBTs / MOSFETs):**
   * Com o banco de capacitores totalmente descarregado (verificar $0.0\text{ V}$ com multímetro):
   * Testar a junção Coletor-Emissor (ou Dreno-Source) de cada semicondutor na escala de diodo:
   * **Resultado de Campo:** Identificados **dois semicondutores (IGBTs/MOSFETs) em curto franco (0.000V / bipe contínuo)**.
   * **Explicação do Erro `Vtopcapa > 400V`:** Com um braço da ponte H em curto e o fusível aberto, a leitura diferencial do sensor de tensão no estágio de entrada entra em saturação espúria de medição, disparando o alarme de segurança *(587h)*.

---

### 3. PROCEDIMENTO DE INTERVENÇÃO & REPARO

1. **Desenergização e Bloqueio (LOTO):**
   * Desligar disjuntor principal da sala e travar na PDU.
   * Aguardar 10 minutos para descarga natural dos capacitores de alta energia e confirmar $0.0\text{ VDC}$ nas pontas de prova.
2. **Remoção e Limpeza da Placa de Potência:**
   * Desconectar barramentos de cobre e cabos de sinal dos drivers de gate.
   * Remover os módulos danificados do dissipador térmico de alumínio.
   * Limpar resíduos de pasta térmica ressecada com álcool isopropílico.
3. **Substituição dos Componentes Homologados:**
   * Instalar o novo par de semicondutores de potência (IGBTs/MOSFETs) de especificações rigorosamente idênticas.
   * Aplicar camada fina e uniforme de pasta térmica de alta condutividade ($> 3.0\text{ W/mK}$).
   * Respeitar o torque especificado de fixação nos parafusos do dissipador para evitar empenamento da pastilha interna.
   * Instalar novo fusível original homologado **1000V x 20A cerâmico ultrarrápido**.
4. **Inspeção Adicional de Proteção:**
   * Medir os diodos de retorno (*freewheeling diodes*) e circuitos snubbers associados.
   * Verificar se não há resistores de gate abertos ou com valor alterado.

---

### 4. RECOMISSIONAMENTO & TESTES DE LIBERAÇÃO NO CONSOLE

1. **Energização Gradual:**
   * Ligar disjuntor e acompanhar a rampa de pré-carga do barramento DC até atingir os ~520 VDC nominais.
2. **Acesso ao Common Service Desktop:**
   * Abrir: `[DIAGNOSTICS]` -> `[X-RAY GENERATION]` -> `GenToolShell (Generator Tool - JEDI)`.
   * Executar: `[kV Diagnostics]` e disparos de teste em `[kV & mA X-Ray Gen]`.
3. **Ciclo de Homologação Clínica:**
   * Executar o ciclo completo de *Tube Warm-up* (Aquecimento do Tubo).
   * Executar a *Air Calibration* (Calibração de Ar para correção de detectores).
   * Liberar o Tomógrafo para rotina de exames com pacientes.

---
*EMED ELETROMEDICINA — Centro de Treinamento Técnico e Manuais de Serviço Especializado.*
