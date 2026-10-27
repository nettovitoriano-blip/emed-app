# IT-RXM-SHIM-004: ROTEIRO MESTRE DE INSTALAÇÃO, MONTAGEM & COMISSIONAMENTO DIGITAL (31 PASSOS)

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-RXM-SHIM-004`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


**Sistema:** Raio-X Móvel Motorizado Digital Shimadzu MobileDaRt Evolution (Versões MX8 e MX9)  
**Documento eMED:** IT-RXM-SHIM-004 | **Revisão:** 2.0  
**Manuais de Referência:** Shimadzu M503-E404K (Common Section - 716p) & M503-E410L (DR Part & VXvue - 642p)  
**Validade:** Engenharia Clínica e Especialistas de Campo eMED  
**Classificação:** Procedimento Operacional Crítico de Alta Complexidade

---

> ### ⚠️ ALERTA DE SEGURANÇA E ALTA ENERGIA
> * O MobileDaRt MX8/MX9 armazena **32 kW** em seu banco de capacitores e possui baterias seladas de alta densidade energética ($240\text{V DC}$).
> * **LOTO Obrigatório:** Antes de qualquer intervenção mecânica ou elétrica nos TAPs e placas, desligue o disjuntor principal (*Main Circuit Breaker*) e certifique-se da descarga dos capacitores ($V_{DC} < 5\text{V}$).
> * **Equipamento Pesado:** O equipamento pesa aproximadamente **$440\text{ kg}$**. Mantenha o freio de emergência acionado e use 2 técnicos para movimentação na rampa de desembalagem.

---

## 📋 SUMÁRIO EXECUTIVO DO PIPELINE DE 31 PASSOS

| Passo | Descrição do Procedimento | Capítulo Oficial | Manual Base | Página (Man/PDF) |
| :---: | :--- | :---: | :---: | :---: |
| **01** | Desembalagem & Conferência de Acessórios | Cap. 3.2 | M503-E404 | 15 / 37 |
| **02** | Remoção das Travas Mecânicas de Transporte | Cap. 3.3 | M503-E404 | 16 / 38 |
| **03** | Remoção das Tampas Laterais e de Serviço | Cap. 3.5 | M503-E404 | 20 / 42 |
| **04** | Configuração dos TAPs de Tensão de Alimentação | Cap. 4.9 | M503-E404 | 102 / 124 |
| **05** | Configuração de DIP Switches na Placa XCONT-2018 | Cap. 6 | M503-E404 | 315 / 337 |
| **06** | Ajuste do Docking Mechanism do FPD (Vxvue) | Cap. 4.6 | M503-E404 | 85 / 107 |
| **07** | Calibração do FVR (Filament Voltage Reference) | Cap. 8.4 | M503-E404 | 436 / 458 |
| **08** | Preparação e Instalação do Sistema Digital DR | Cap. 5.0.0 | M503-E410 | 399 / 413 |
| **09** | Instalação de Acessórios e Módulos Opcionais | Cap. 5 | M503-E404 | 165 / 187 |
| **10** | Configuração e Confirmação dos Parâmetros da BIOS | Cap. 5.2.1 | M503-E410 | 400 / 414 |
| **11** | Restauração da Imagem Mestre do Sistema Operacional | Cap. 5.2.2 | M503-E410 | 402 / 416 |
| **12** | Primeiro Acesso e Configuração do Windows | Cap. 5.2.3 | M503-E410 | 408 / 422 |
| **13** | Registro e Validação da Licença do Windows (COA) | Cap. 5.2.4 | M503-E410 | 409 / 423 |
| **14** | Calibração Geométrica do Monitor Touchscreen | Cap. 6.6 | M503-E410 | 623 / 637 |
| **15** | Criação da Estrutura de Diretórios D:\TEMP | Cap. 5.2.7 | M503-E410 | 417 / 431 |
| **16** | Cópia dos Pacotes de Instalação VXvue e VSS | Cap. 5.2.7 | M503-E410 | 417 / 431 |
| **17** | Instalação e Parametrização do Software VXvue | Cap. 5.2.7 | M503-E410 | 418 / 432 |
| **18** | Instalação do VSS (Vieworks Service Software) | Cap. 5.2.7 | M503-E410 | 429 / 443 |
| **19** | Liberação de Portas e Regras no Windows Firewall | Cap. 5.2.7 | M503-E410 | 423 / 437 |
| **20** | Configuração do Roteador Wi-Fi Aruba Instant AP | Cap. 5.2.8 | M503-E410 | 483 / 497 |
| **21** | Configuração Padrão de Rede e IPs Vieworks | Cap. 5.2.8 | M503-E410 | 483 / 497 |
| **22** | Pareamento e Registro do Número de Série do FPD | Cap. 5.2.6 | M503-E410 | 446 / 460 |
| **23** | Configuração do Modo de Disparo do FPD (AED/Sync) | Cap. 5.2.6 | M503-E410 | 449 / 463 |
| **24** | Configuração do Perfil de FPD Padrão Shimadzu | Cap. 5.2.6 | M503-E410 | 450 / 463 |
| **25** | Otimização do Canal 5GHz do Aruba AP (Shimadzu) | Cap. 5.2.8 | M503-E410 | 486 / 500 |
| **26** | Calibração Completa do FPD (Offset, Ganho, Pixels) | Cap. 5.2.6 | M503-E410 | 455 / 469 |
| **27** | Backup de Segurança da Imagem Final (Ghost) | Cap. 5.6 | M503-E410 | 548 / 562 |
| **28** | Instalação do Antivírus McAfee Embedded Control (MEC) | Cap. 5.5 | M503-E410 | 532 / 546 |
| **29** | Geração da Whitelist de Arquivos e Executáveis | Cap. 5.5.2 | M503-E410 | 538 / 553 |
| **30** | Bloqueio do Sistema Operacional (To Lock PC) | Cap. 5.5.2 | M503-E410 | 540 / 554 |
| **31** | Protocolo de Desbloqueio do Sistema (To Unlock PC) | Cap. 5.5.2 | M503-E410 | 541 / 555 |

---

## 🔩 FASE 1: HARDWARE, MECÂNICA & INFRAESTRUTURA ELÉTRICA (PASSOS 01 A 07)

### PASSO 01: DESEMBALAGEM & CONFERÊNCIA DE ACESSÓRIOS
1. Posicione o caixote de madeira em piso nivelado. Remova a tampa superior e as 4 paredes laterais.
2. Monte a rampa de descida de madeira na parte frontal do pallet e trave com os parafusos fornecidos.
3. Inspecione o envelope de manutenção e confirme a presença dos itens sobressalentes:
   * **Fusíveis de Reposição:** 313.500P (1x), 313001P (1x), 313002P (1x), 313005P (1x), 3136.25 (1x), 313004P (1x), 326010XP (1x), 660CF-10 (1x) e FLM10 (1x).
   * **Etiquetas de Identificação de Tensão:** `Input Voltage Labels` (100V, 110V, 120V, 200V, 220V, 230V, 240V).
   * **CD/DVD de Recuperação MUX Recovery FD/CD.**
   * **Amortecedores de Borracha:** Cushions para FPD 14x17.

### PASSO 02: REMOÇÃO DAS TRAVAS MECÂNICAS DE TRANSPORTE
1. **Trava do Braço Articulado:** Remova os suportes metálicos pintados de amarelo que bloqueiam a coluna telescópica e o braço giratório.
2. **Batentes do Colimador:** Remova os 2 parafusos de retenção de transporte que impedem a rotação do colimador luminoso.
3. **Cintas Plásticas:** Corte as duas cintas plásticas de polipropileno (PP) que prendem o cabeçote.
4. *Nota de Campo eMED:* Guarde as travas metálicas no compartimento traseiro ou entregue ao responsável da clínica para transporte interestadual futuro.

### PASSO 03: REMOÇÃO DAS TAMPAS LATERAIS E DE SERVIÇO
1. Solte os fixadores Allen na base das tampas laterais direita e esquerda.
2. Deslize os painéis ligeiramente para cima para desengatar as travas plásticas superiores.
3. Desconecte o cabo terra de equalização potencial de cada tampa antes de afastá-la totalmente do chassi.

### PASSO 04: CONFIGURAÇÃO DOS TAPS DE TENSÃO DE ALIMENTAÇÃO (TRANSFORMADOR)
> **CRÍTICO:** O equipamento sai de fábrica configurado para rede japonesa de **100V**. A ligação direta em tomadas brasileiras de 220V sem a mudança dos TAPs causará **destruição imediata do autotransformador e fusíveis principais!**

1. Desligue o disjuntor principal (*Main Circuit Breaker*) na traseira da unidade.
2. Localize a régua de bornes do transformador na lateral direita do chassi.
3. Ajuste os conectores **P1** e **P2** de acordo com a tensão medida no multímetro na tomada hospitalar:

| Tensão Medida na Tomada | Conexão P1 | Conexão P2 | Etiqueta no Plugue |
| :---: | :---: | :---: | :---: |
| **100 V AC** | **A0** | **A100** | 100V |
| **110 V AC** | **A0** | **A110** | 110V |
| **120 V AC** | **A0** | **A120** | 120V |
| **200 V AC** | **A0** | **A200** | 200V |
| **220 V AC (Padrão eMED)** | **A0** | **A220** | **220V** |
| **230 V AC** | **A0** | **A230** | 230V |
| **240 V AC** | **A0** | **A240** | 240V |

4. Cole a etiqueta autoadesiva correspondente (Ex: `220V`) no cabo de força próximo ao plugue NBR 14136 / Cetac.
5. Ligue o disjuntor e confirme no display se não há código de erro `F5x`.

### PASSO 05: CONFIGURAÇÃO DE DIP SWITCHES (PLACA XCONT-2018)
1. Localize a placa principal de controle radiológico **XCONT-2018** (P/N `565-15000-xx`).
2. Configure os microinterruptores DIP switches conforme a tabela de homologação de fábrica:
   * **SW1-1 a SW1-8:** Seleção de modelo de tubo de raios-X (Shimadzu 0.7/1.3 U1443CS) e capacidade máxima de potência (32 kW).
   * **SW2-1 a SW2-4:** Seleção da versão de comunicação DR (Tipo VXvue digital).
   * **SW3:** Modo de operação e depuração de service interlock.
   * **SW4:** Baud rate da interface serial com a estação de trabalho (115200 bps).

### PASSO 06: DOCKING MECHANISM (FOR VXVUE)
1. Instale o berço de acoplamento do detector digital no compartimento frontal do MobileDaRt.
2. Regule a pressão dos roletes de retenção mecânica para que o FPD entre de forma suave, sem folga lateral e sem forçar os conectores elétricos de recarga rápida.
3. Aferir o acionamento do microswitch de detecção: o LED indicador de detector acoplado no painel do operador deve acender em verde contínuo.

### PASSO 07: CALIBRAÇÃO DO FVR (FILAMENT VOLTAGE REFERENCE)
O FVR determina a curva de tensão aplicada ao filamento catódico para gerar a corrente exata de tubo ($mA$).
1. **Inicialização:** Pressione a tecla de foco fino/grosso no painel de serviço para carregar a tabela padrão de FVR da ROM.
2. **Calibração em 2 Pontos (80 kV):**
   * Disparo no ponto mínimo de mA ($80\text{ kV}$, menor corrente): ajuste o FVR até que o mA medido coincida com o valor nominal ($\pm 2\%$).
   * Disparo no ponto máximo de mA ($80\text{ kV}$, corrente de pico): ajuste o FVR correspondente.
3. **Checagem nos 6 Patamares:** Execute disparos de verificação em **40 kV, 60 kV, 80 kV, 100 kV, 125 kV e 133 kV**.

---

## 💻 FASE 2: SISTEMA DIGITAL, WORKSTATION & VXVUE (PASSOS 08 A 19)

### PASSO 08: INSTALAÇÃO DO SISTEMA DIGITAL DR
1. Conecte a unidade óptica de DVD USB externa exclusivamente na **porta USB direita do chassi**.
   * *Atenção:* NUNCA conecte no hub USB esquerdo, pois causará sobrecarga de corrente na placa auxiliar.
2. Conecte o cabo de rede gigabit entre o PC embutido e a placa de sincronismo de raios-X.

### PASSO 09: INSTALAÇÃO DE OPCIONAIS
1. Monte o disparador manual adicional (*Hand Switch*) com cabo espiralado ou módulo wireless.
2. Caso aplicável, instale a câmara de ionização de medição de dose DAP (*Dose Area Product*) na saída do colimador e fixe o leitor digital.

### PASSO 10: CONFIGURAÇÕES DA BIOS DO COMPUTADOR
1. Ligue a workstation pressionando `Delete` ou `F2` continuamente para acessar o Setup da BIOS.
2. Configure as seguintes diretivas obrigatórias:
   * **Boot Option #1:** `UEFI / USB Hard Disk` (para recovery) | Boot Option #2: `Internal SSD`.
   * **AC Power Recovery:** `Power On` (para que o computador ligue automaticamente ao girar a chave do equipamento).
   * **Fast Boot:** `Disabled` (garante reconhecimento estável de todos os barramentos USB no boot).
   * Pressione `F10` para salvar e reiniciar.

### PASSO 11: INSTALAÇÃO DA IMAGEM DO SISTEMA
1. Insira o pendrive ou mídia de recuperação original Shimadzu.
2. Inicie o utilitário Ghost/Recovery e restaure o arquivo de imagem `.GHO` na unidade de armazenamento do sistema.
3. Aguarde o particionamento automático:
   * **Unidade C: (SO & Binários):** $150\text{ GB}$ (NTFS).
   * **Unidade D: (Imagens & Dados):** Espaço restante (NTFS).

### PASSO 12: ACESSO AO WINDOWS
1. O sistema efetuará o boot no Windows 10 IoT Enterprise.
2. Credenciais de Serviço Shimadzu:
   * **Usuário Administrador:** `Administrator` ou `service`
   * **Senha de Acesso:** `Shimadzu` (com "S" maiúsculo).

### PASSO 13: REGISTRO DA LICENÇA DO WINDOWS
1. Localize a etiqueta autoadesiva do COA (*Certificate of Authenticity*) colada na lateral do gabinete do computador.
2. Abra as Configurações do Windows -> Atualização e Segurança -> Ativação.
3. Insira a chave de produto de 25 caracteres e confirme a ativação digital offline/OEM.

### PASSO 14: CALIBRAÇÃO DO MONITOR TOUCHSCREEN
1. Abra o painel de calibração do driver da tela (*Touch Screen Utility*).
2. Execute o procedimento de calibração em 9 ou 16 pontos, tocando exatamente no centro dos alvos exibidos na tela LCD articulada.
3. Verifique a precisão do toque nos 4 cantos da área de trabalho.

### PASSO 15: CRIAÇÃO DA PASTA TEMP NA UNIDADE D:
1. Abra o Windows Explorer e navegue até a unidade de dados `D:\`.
2. Crie a pasta `D:\TEMP` caso ainda não exista.
3. Conceda permissão total (*Full Control*) para o grupo `Users` e `Everyone`.

### PASSO 16: CÓPIA DOS ARQUIVOS VXVUE E VSS
1. Conecte a mídia de instalação contendo os softwares de aplicação.
2. Copie para `D:\TEMP`:
   * Instalador do **VXvue** (Versão homologada Shimadzu).
   * Instalador do **VSS (Vieworks Service Software)**.
   * Arquivos de configuração de fábrica do detector (`.cal`, `.xml`).

### PASSO 17: INSTALAÇÃO DO VXVUE
1. Execute o instalador `Setup.exe` do VXvue como Administrador.
2. Selecione o perfil de equipamento: `Mobile System (Shimadzu MobileDaRt)`.
3. Configure o caminho do banco de dados de imagens para `D:\VXvue_Data\`.
4. Conclua o assistente e reinicie o computador.

### PASSO 18: INSTALAÇÃO DO VSS (VIEWORKS SERVICE SOFTWARE)
1. Instale o aplicativo VSS a partir de `D:\TEMP\VSS_Setup\`.
2. O VSS é a ferramenta exclusiva de engenharia para comunicação em baixo nível, leitura de temperatura do cintilador CsI e diagnóstico do hardware do painel.

### PASSO 19: CONFIGURAÇÃO DO FIREWALL DO WINDOWS
Abra o Prompt de Comando como Administrador e adicione as exceções de rede hospitalar:
* **Porta DICOM Store/Storage Commit:** TCP `104` e `11112`.
* **Porta de Comunicação com Gerador Shimadzu:** TCP/UDP `2100` a `2110`.
* **Broadcast do Detector Vieworks:** UDP `4000` a `4005`.
* Permita o tráfego nos perfis Privado e Domínio.

---

## 📡 FASE 3: REDE SEM FIO, DETECTOR FPD & CALIBRAÇÃO (PASSOS 20 A 26)

### PASSO 20: CONFIGURAÇÃO DO ROTEADOR ARUBA INSTANT AP
1. Conecte o cabo de rede ao ponto de acesso Aruba embutido.
2. Acesse a interface web do Aruba AP através do IP padrão de gerência `192.168.1.1` ou `192.168.100.1`.
3. Defina o modo do AP como **Standalone Access Point**.

### PASSO 21: CONFIGURAÇÃO DE REDE PADRÃO VIEWORKS
Atribua os endereços IP estáticos conforme a arquitetura oficial:

| Dispositivo / Interface | Endereço IP | Máscara de Sub-rede | Gateway / Observações |
| :--- | :---: | :---: | :--- |
| **Placa de Rede PC (LAN Local)** | `192.168.11.10` | `255.255.255.0` | Comunicação interna com gerador |
| **Placa Wi-Fi Workstation** | `192.168.12.10` | `255.255.255.0` | Enlace dedicado com o FPD |
| **Ponto de Acesso Aruba** | `192.168.12.1` | `255.255.255.0` | SSID: `MX8_DR_AP` |
| **Detector FPD (Vieworks)** | `192.168.12.100` | `255.255.255.0` | Porta de dados: `4000` |

### PASSO 22: REGISTRO DO FPD
1. Abra o utilitário de configuração do VXvue -> Menu *Detector Management*.
2. Clique em **Add New Detector**.
3. Digite o número de série exato impresso na carcaça traseira do detector (Ex: `FXRD-1417SAxxxx`).
4. Selecione o modelo correspondente: 14x17 polegadas ou 17x17 polegadas.

### PASSO 23: CONFIGURAÇÕES DO FPD (DISPARO & SINCRONISMO)
1. Defina o modo de sincronismo de exposição:
   * **Modo AED (Auto Exposure Detection):** O sensor detecta automaticamente o início da emissão de raios-X e dispara a integração de carga sem necessidade de cabos físicos.
   * **Modo Line Trigger (Cabo de Backup):** Ativado automaticamente quando o cabo tethered de emergência for conectado.
2. Configure o tempo de janela de integração (*Exposure Window*): $1.200\text{ ms}$.

### PASSO 24: CONFIGURAÇÕES FPD PADRÃO SHIMADZU
1. Defina a sensibilidade de disparo do AED para nível intermediário (Level 3), evitando disparos falsos causados por vibração mecânica durante o transporte do equipamento em corredores irregulares.
2. Habilite o modo de economia de energia (*Sleep Mode* após 15 minutos sem uso).

### PASSO 25: CONFIGURAÇÃO ARUBA PADRÃO SHIMADZU
1. Configure o rádio sem fio para a frequência de **5 GHz (802.11ac)** em canal fixo não sobreposto (Recomendado: Canal 149 - 5745 MHz ou Canal 153).
2. Desative a transmissão em 2.4 GHz para blindar a comunicação contra interferências de redes Wi-Fi hospitalares e celulares.
3. Segurança: WPA2-PSK com chave criptográfica robusta.

### PASSO 26: CALIBRAÇÃO COMPLETA DO FPD
> **Condição Prévia:** Ligue o detector 30 minutos antes da calibração para estabilização da temperatura dos módulos TFT/fotodiodos.

1. **Dark Calibration (Calibração de Offset):**
   * Realizada sem disparo de raios-X. Mede a corrente de fuga térmica de cada pixel.
2. **Gain Calibration (Flat Field):**
   * Posicione o tubo a $100\text{ cm}$ do detector no suporte.
   * Acople o filtro de cobre de $1,5\text{ mm Cu}$ ou alumínio de $20\text{ mm Al}$ no colimador.
   * Execute 5 disparos homogêneos a $70\text{ kV}$, $100\text{ mA}$, $100\text{ ms}$.
   * O software computará o mapa de ganho de todos os canais de leitura.
3. **Defect Pixel Correction Map:**
   * O software identifica pixels mortos ou linhas abertas e aplica algoritmo de interpolação bi-linear com pixels vizinhos.
   * Verifique se nenhum defeito em cluster ultrapassa $3 \times 3$ pixels na região central diagnóstica.

---

## 🔒 FASE 4: SEGURANÇA HOSPITALAR, BACKUP GHOST & BLOQUEIO (PASSOS 27 A 31)

### PASSO 27: REALIZAR BACKUP DA IMAGEM DO SISTEMA (GHOST FINAL)
1. Reinicie o computador conectando o pendrive de boot Shimadzu Ghost.
2. Execute a rotina de criação de imagem:
   * `Local -> Partition -> To Image`
   * Selecione a partição C: do SSD interno e salve o arquivo `MX8_COMMISSIONED_FINAL.GHO` na unidade D: e no pendrive do técnico.
3. Esse backup garante a restauração completa em menos de 10 minutos em caso de falha futura de hardware.

### PASSO 28: MCAFEE EMBEDDED CONTROL (MEC) - VISÃO GERAL
O McAfee Embedded Control (MEC / Application Control) é o sistema de proteção antivírus obrigatório da Shimadzu para equipamentos médicos baseados em Windows, que impede a execução de qualquer código não autorizado sem consumir recursos de CPU com varreduras em segundo plano.

### PASSO 29: CRIANDO A WHITE LIST
1. Na Área de Trabalho, clique duas vezes no atalho `MEC_menu.htm`.
2. No menu do navegador, clique em **[Create White List]**.
3. O Prompt de Comando será aberto automaticamente:
   * Quando solicitada a senha, digite: **`Shimadzu`** e pressione Enter.
4. O MEC iniciará o cálculo de hash criptográfico de todos os executáveis, DLLs, scripts e drivers presentes nas unidades C: e D:.
5. Aguarde até a mensagem: `White List creation completed successfully`.

### PASSO 30: TO LOCK PC (BLOQUEIO DO SISTEMA)
1. No menu `MEC_menu.htm`, clique no botão **[LockPC]**.
2. No Prompt de Comando, digite a senha: **`Shimadzu`** e pressione Enter.
3. O software mudará o status do sistema operacional para **`LOCKED`**.
4. Valide a proteção:
   * Abra o Prompt de Comando e execute: `sadmin status`
   * O status deve exibir:
     ```text
     McAfee Solidifier:           Enabled
     McAfee Solidifier Restart:   Enabled
     Status:                      Locked
     ```
5. Tente plugar um pendrive com um executável qualquer e tente abri-lo: o Windows bloqueará a execução imediatamente com mensagem de violação de política do MEC.

### PASSO 31: TO UNLOCK PC (PROCEDIMENTO DE DESBLOQUEIO PARA MANUTENÇÃO)
Sempre que um especialista da eMED precisar atualizar versões do VXvue, drivers ou aplicar patches no futuro, deve realizar o desbloqueio temporário:
1. Abra `MEC_menu.htm` e clique em **[UnLockPC]**.
2. Digite a senha oficial: **`Shimadzu`**.
3. O sistema entrará em modo desprotegido (`UNLOCKED`).
4. Execute as intervenções técnicas necessárias.
5. **OBRIGATÓRIO:** Ao finalizar, repita o **Passo 30 (To Lock PC)** para restabelecer a imunização do equipamento antes de devolvê-lo à operação clínica do hospital.

---

## 🎯 CHECKLIST FINAL DE ENTREGA TÉCNICA (COMISSIONAMENTO eMED)

- [ ] **TAPs de Alimentação:** Verificado jumper em P1=A0 e P2=A220 (220V medidos).
- [ ] **Travas de Transporte:** Todas as travas e batentes mecânicos removidos.
- [ ] **Corrente de Filamento (FVR):** Calibração de 2 pontos concluída com desvio $< 2\%$.
- [ ] **Warm-Up do Tubo:** Modo `tUbeUP` executado com sucesso nos 13 passos escalonados.
- [ ] **Enlace Wi-Fi Aruba:** Conexão 5GHz estável a mais de 15 metros sem perda de pacotes.
- [ ] **Calibração FPD:** Dark, Gain e Defect Map gerados e aprovados no VSS.
- [ ] **McAfee MEC:** Whitelist gerada e sistema confirmado no status **LOCKED**.
- [ ] **Backup Ghost:** Imagem final armazenada em `D:\BACKUP\` e no pendrive do cliente.
- [ ] **Assinatura do Técnico Responsável:** Comprovante de entrega técnica emitido.
