# INSTRUÇÃO DE TRABALHO (IT-TOMO-GE-007)

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-007`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## Guia Operacional da Ferramenta do Gerador JEDI (JEDI Generator Tool)
### Tomógrafos GE Healthcare (Brivo CT385, BrightSpeed e Optima Series)
*Baseado no manual oficial GE Direction 5438996-8EN / 5181178*

---

### 1. INTRODUÇÃO & ACESSO AO APLICATIVO
A ferramenta **JEDI Generator Tool** é o utilitário mestre de serviço da GE para controle, diagnóstico, calibração e gerenciamento de banco de dados do subsistema de Geração de Alta Tensão (Gerador JEDI e Tubo de Raio-X).

* **Como Acessar no Console:**
  1. No console do operador (Host Computer), abra o **Common Service Desktop**;
  2. Clique na aba superior **[DIAGNOSTICS]**;
  3. Selecione a opção **[X-RAY GENERATION]**;
  4. A janela principal **GenToolShell (Generator Tool - JEDI)** será inicializada.

---

### 2. MAPEAMENTO COMPLETO DA INTERFACE (TELA PRINCIPAL)

A tela principal do utilitário é dividida em **3 colunas operacionais**:

```
+-----------------------------------------------------------------------------------+
|                              Generator Tool - JEDI                                |
+-------------------------+-------------------------+-------------------------------+
|    1. Tube Install      |      2. JEDI Tests      |    3. Database Management     |
|   (Instalação de Tubo)  |    (Testes do Gerador)  |    (Gerenciamento de Dados)   |
+-------------------------+-------------------------+-------------------------------+
|  [ Reset TnT Data ]     |  [ kV Diagnostics ]     |  [ Initialize Database ]      |
|  [ Filament Cal ]       |  [ kV & mA X-Ray Gen ]  |  [ Save Runtime Parameters ]  |
|  [ HHS Scans ]          |  [ Heater Diagnostics ] |  [ Restore Runtime Parameters]|
|  [ HHS Report ]         |  [ Rotor Diagnostics ]  |                               |
+-------------------------+-------------------------+-------------------------------+
```

---

### 3. COLUNA 1: PROCEDIMENTOS DE INSTALAÇÃO DO TUBO (TUBE INSTALL)

#### 3.1 [ Reset TnT Data ] — Zerar Dados de Disparos e Aquecimento do Tubo
* **Quando usar:** **OBRIGATÓRIO** imediatamente após a instalação física de um tubo de Raio-X novo ou recondicionado.
* **O que faz:** Zera os contadores acumulados de horas de filamento ligado, contagem total de exposições e curva térmica residual de Joules armazenados na placa controladora do gerador.
* **Passo a Passo:**
  1. Clique em **[Reset TnT Data]**;
  2. O sistema solicitará confirmação com aviso de substituição de tubo;
  3. Confirme em **[Yes / Confirm]**;
  4. Verifique a mensagem verde na área de status: `TnT Data Successfully Reset`.

#### 3.2 [ Filament Cal ] — Calibração da Corrente do Filamento
* **Quando usar:** Após troca de tubo, troca da placa de controle do filamento ou quando ocorrerem erros de subcorrente/sobrecorrente de filamento.
* **O que faz:** Calibra a relação entre a corrente de pré-aquecimento e a corrente real de emissão (mA) para os pontos focais Pequeno (*Small Focal Spot*) e Grande (*Large Focal Spot*).
* **Passo a Passo:**
  1. Selecione **[Filament Cal]**;
  2. Certifique-se de que a sala de exames esteja fechada e desobstruída;
  3. Pressione e segure o botão de disparo **[Scan]** no console quando solicitado;
  4. O sistema executará disparos sucessivos mapeando a curva de emissão;
  5. **Atenção:** Se o programa travar durante o processo, os dados anteriores da NVRAM não serão corrompidos. Basta reiniciar o utilitário.

#### 3.3 [ HHS Scans ] & [ HHS Report ] — Varreduras e Relatório de Alta Velocidade (High Speed Scans)
* **O que faz:** Executa uma sequência padronizada de disparos em rotação rápida para condicionamento térmico inicial da pista anódica do tubo e validação do sistema de balanceamento térmico (*High Heat Storage*).
* Ao término, clique em **[HHS Report]** para visualizar e salvar o laudo digital comprobatório da estabilidade do tubo.

---

### 4. COLUNA 2: DIAGNÓSTICOS DO GERADOR (JEDI TESTS)

#### 4.1 [ kV Diagnostics ] — Diagnóstico de Alta Tensão
* Realiza a checagem dos inversores de alta tensão sem necessidade de emissão de feixe contínuo. Avalia o chaveamento dos módulos IGBT e a simetria entre o semiciclo positivo e negativo do tanque de alta tensão.

#### 4.2 [ kV & mA X-Ray Gen ] — Disparo Diagnóstico Monitorado
* **O que faz:** Permite configurar manualmente um disparo de teste único e coletar em tempo real todos os parâmetros elétricos de alta tensão capturados pelos conversores A/D do gerador.
* **Parâmetros Medidos e Tolerâncias:**

| Parâmetro no Relatório | Significado Técnico | Tolerância / Critério de Aceitação |
| :--- | :--- | :--- |
| `*Total kV` | Tensão nominal aplicada | Valor selecionado $\pm 3\%$ |
| `*mA` | Corrente média medida no feixe | Valor selecionado $\pm 5\%$ |
| `*kV @ 5 msec` | Tensão medida no transitório inicial (5 ms) | Não deve apresentar sobretensão (*overshoot*) $> 8\%$ |
| `*mA @ 5 msec` | Corrente medida no transitório inicial (5 ms) | Estabilização rápida sem oscilação |
| `Filament Current (Preheat)` | Corrente de repouso no filamento antes do disparo | Dentro da tabela de pré-aquecimento do tubo |
| `Filament Current (Scan End)` | Corrente de filamento no instante final do corte de RX | Sem queda brusca de aquecimento |
| `Exposure Time` | Tempo real de exposição cronometrado | $\pm 1\text{ ms}$ em relação ao tempo programado |

#### 4.3 [ Heater Diagnostics ] — Diagnóstico do Circuito de Aquecimento do Filamento
* Testa a continuidade do circuito primário e secundário do transformador de filamento, impedância e sensoriamento de retorno da corrente de filamento em repouso.

#### 4.4 [ Rotor Diagnostics ] — Diagnóstico de Rotação do Ânodo (Rotor Drive)
* Avalia a rampa de aceleração do ânodo giratório (*Boost*), a frequência da corrente trifásica aplicada aos enrolamentos do estator do tubo e a frenagem dinâmica (*Brake*).
* Identifica precocemente rolamentos de ânodo presos, ruído mecânico excessivo ou falha nos capacitores de partida do rotor.

---

### 5. COLUNA 3: GERENCIAMENTO DE BANCO DE DADOS (DATABASE MANAGEMENT)

> [!IMPORTANT]
> **SALVAMENTO OBRIGATÓRIO NA NVRAM (MEMÓRIA NÃO-VOLÁTIL):**
> Todas as calibrações de filamento e ajustes realizados no gerador ficam inicialmente armazenados na memória volátil da placa de controle. Se o tomógrafo for desligado sem o salvamento manual, **todas as calibrações serão perdidas**!

* **[ Save Runtime Parameters ] (Salvar Parâmetros Operacionais):**
  * **Ação Obrigatória:** Clique neste botão sempre que concluir o `Filament Cal` ou ajustes de kV/mA. Ele transfere e grava todos os parâmetros na memória permanente (Flash/NVRAM) da placa controladora do gerador JEDI.
* **[ Restore Runtime Parameters ] (Restaurar Parâmetros Salvos):**
  * Faz o download dos parâmetros previamente salvos na Flash de volta para os registradores de trabalho. Caso o botão apareça desabilitado (*dimmed*), significa que nenhum salvamento prévio foi executado.
* **[ Initialize Database ] (Inicializar Banco de Dados Padrão):**
  * **Cuidado:** Restaura os valores de fábrica nominais do gerador para o modelo de tubo cadastrado. Deve ser utilizado apenas em caso de corrupção comprovada de dados ou ao instalar uma placa de controle nova sobressalente (*spare board*).

---

### 6. RESUMO DE LIBERAÇÃO DE SERVIÇO (CHECKLIST DO TÉCNICO)
1. [ ] Dados de TnT zerados com sucesso (`Reset TnT Data`);
2. [ ] Calibração de filamento (`Filament Cal`) concluída sem erros em Small e Large focal spots;
3. [ ] Disparo de teste executado no `kV & mA X-Ray Gen` com kV e mA dentro da tolerância de $5\%$;
4. [ ] Botão **[ Save Runtime Parameters ]** acionado para gravar a calibração na NVRAM;
5. [ ] Tomógrafo reinicializado e mensagem de confirmação de prontidão no console.
