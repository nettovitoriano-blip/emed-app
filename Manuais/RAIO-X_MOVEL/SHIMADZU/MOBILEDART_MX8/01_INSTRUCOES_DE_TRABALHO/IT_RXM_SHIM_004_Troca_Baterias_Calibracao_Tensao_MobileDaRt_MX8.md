# INSTRUÇÃO DE TRABALHO TÉCNICA - eMED BIOMEDICAL

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RXM-SHIM-004`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## IT-RXM-SHIM-004: Substituição do Banco de Baterias e Calibração do Circuito de Detecção de Tensão (Shimadzu MobileDaRt MX8)
**Equipamento:** Shimadzu MobileDaRt Evolution / MX8 Version (Raio-X Móvel Motorizado)  
**Subsistema:** Banco de Baterias Seladas Chumbo-Ácido, Placa MUX CHARGE & Placa XCONT-2018  
**Documentos Base de Fábrica:** Manual de Serviço Shimadzu M503-E410 (Modos 7.6 e 7.11)  
**Nível de Acesso:** Diagnóstico por Imagem / Técnico de Campo Especializado  
**Revisão:** 1.0 - Procedimento de Substituição, Configuração de Código e Calibração de Tensão  

---

### 1. OBJETIVO E ESCOPO
Padronizar a rotina de desativação segura, substituição do conjunto de baterias seladas recarregáveis chumbo-ácido de tração e exposição, calibração eletrônica do conversor A/D de medição de tensão do banco (*Battery Voltage Detection Circuit Adjustment - Modo 7.6*) e parametrização do código de bateria (*Battery Code Setting - Modo 7.11*) no equipamento Shimadzu MobileDaRt MX8.

---

### 2. PRECAUÇÕES CRÍTICAS DE SEGURANÇA ELÉTRICA

> [!CAUTION]
> **RISCO DE CURTO-CIRCUITO DE ALTA ENERGIA E ARCO ELÉTRICO:**  
> O banco de baterias do MobileDaRt armazena corrente de curto-circuito superior a **$1000\text{A}$**.  
> Um toque acidental entre bornes e o chassi com ferramentas metálicas causará explosão e queima imediata.
> 1. Use **ferramentas isoladas a 1000V**;
> 2. Desligue o **Disjuntor Principal** (*Main Circuit Breaker*) na frente da máquina;
> 3. Remova primeiro o fusível principal de proteção (*Battery Fuse*) antes de soltar os cabos de interligação entre os blocos de baterias.

---

### 3. PROCEDIMENTO DE TROCA FÍSICA DAS BATERIAS
1. Estacione o equipamento em piso plano e aplique o freio de estacionamento.
2. Desligue a chave geral (*Key switch*) e desative o disjuntor principal (*Main Breaker* $\rightarrow$ **OFF**).
3. Remova as tampas laterais direita e esquerda e a tampa superior da base.
4. Retire o fusível de proteção de bateria do suporte para interromper o circuito em série.
5. Fotografe ou esquematize o posicionamento exato dos cabos de interligação em série/paralelo e chicotes de balanceamento térmico.
6. Solte os terminais e remova os blocos de baterias antigos um a um, observando o limite de peso ergonômico.
7. Limpe os suportes metálicos internos da base contra resíduos ou oxidação.
8. Acondicione o novo banco de baterias originais/homologadas de mesma capacidade nominal (Ah) e tecnologia.
9. Reconecte os cabos de interligação respeitando rigorosamente a polaridade (positivo vermelho / negativo preto) e aperte os parafusos dos bornes com torque firme de $\approx 4,0\text{ N}\cdot\text{m}$.
10. Reinstale o fusível principal de proteção de bateria.
11. Ligue o disjuntor principal (*Main Breaker* $\rightarrow$ **ON**).

---

### 4. PROCEDIMENTO DE CALIBRAÇÃO ELETRÔNICA NO PAINEL

#### ETAPA 1: Configuração do Código de Bateria (Modo de Ajuste 7.11)
1. Com o equipamento desligado, ingresse no **Modo de Serviço/Ajuste**:
   - Pressione e mantenha pressionada a tecla de seleção de programa radiográfico enquanto gira a chave *Key switch* para **ON**.
2. No display de parâmetros, navegue até o **Modo 7.11 (*Battery Code Setting Mode*)**.
3. Verifique o código exibido no display:
   - Configure o código exato correspondente ao modelo e fabricante das baterias recém-instaladas (conforme tabela fornecida pela Shimadzu).
4. Pressione a tecla de gravação (*Memory / Store*) para gravar os dados na NVRAM da placa controladora.

---

#### ETAPA 2: Calibração do Circuito de Leitura de Tensão da Bateria (Modo 7.6)
1. Com um multímetro digital True-RMS de alta precisão calibrado, meça a tensão real contínua diretamente nos bornes principais do banco de baterias:
   - Exemplo de leitura medida: $V_{\text{real}} = 144,8\text{V DC}$.
2. No painel de serviço, selecione o **Modo 7.6 (*Battery Voltage Detection Circuit Adjustment*)**.
3. O display exibirá o valor que o circuito da placa `XCONT-2018` está calculando no momento.
4. Utilizando as teclas de incremento `kV [+]` e decremento `kV [-]`, ajuste o valor exibido no painel de modo que coincida rigorosamente com o valor real medido com o multímetro ($144,8\text{V}$).
5. Pressione a tecla de confirmação para gravar o fator de calibração do conversor A/D.
6. Desligue a chave geral e religue normalmente para sair do modo de serviço.

---

### 5. CHECKLIST DE LIBERAÇÃO
- [ ] Tensão do banco medida nos bornes com equipamento desligado e em carga de flutuação.
- [ ] Todos os LEDs da barra indicadora de bateria (*Battery Indicator*) acesos de forma estável.
- [ ] Teste de tração motorizada e aceleração sem queda abrupta na leitura de carga de bateria.
- [ ] Equipamento conectado na tomada de 220V para carga inicial de equalização (12 horas).
