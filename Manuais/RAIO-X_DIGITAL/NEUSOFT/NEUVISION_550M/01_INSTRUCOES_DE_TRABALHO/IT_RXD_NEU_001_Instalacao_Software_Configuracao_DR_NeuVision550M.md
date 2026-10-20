# INSTRUÇÃO DE TRABALHO TÉCNICA - eMED BIOMEDICAL
## IT-RXD-NEU-001: Instalação de Software, Configuração do Gerador e Rede DR Sem Fio - NeuVision 550M / 550M Plus
**Sistema:** Neusoft NeuVision 550M / NeuVision 550M Plus (Mobile DR)  
**Subsistemas:** Estação de Aquisição DR, Gerador Sedecal de Alta Tensão, Flat Panel Canon CXDI & AP Wi-Fi  
**Documento de Referência:** NPS-XR-0122E Rev. C  
**Nível de Acesso Técnico:** Engenharia Clínica / Field Service Engineer  

---

### 1. OBJETIVO E ESCOPO
Padronizar a rotina de reinstalação completa de software operacional, parametrização do software de serviço da geradora Sedecal de alta tensão e comutação da rede Wi-Fi / link infravermelho (IR) do Flat Panel Detector (FPD) sem fio Canon CXDI no equipamento móvel Neusoft NeuVision 550M / Plus.

---

### 2. CREDENCIAIS DE SERVIÇO E ACESSOS RESTRITOS

> [!IMPORTANT]
> Guarde as senhas técnicas abaixo para execução das ferramentas de diagnóstico e parametrização.

| Nível / Ferramenta | Usuário (Username) | Senha (Password) | Função |
| :--- | :--- | :--- | :--- |
| **Logon Windows (SO)** | `cxdiadmin` | `nmsadmin` | Acesso administrativo ao SO e drivers |
| **Canon Service Tool** | `cxdiadmin` | `Canononac` | Configuração de detectores, AP e calibração |
| **Código Ghost (Instalação)** | *Etiqueta interna* | *No compartimento do PC* | PN Code da imagem de restauração |

---

### 3. SEGURANÇA E PRECAUÇÕES DE HARDWARE

> [!CAUTION]
> **RISCO DE CHOQUE ELÉTRICO DE ALTA TENSÃO:**  
> Ao manipular a chave de serviço **SW7** na placa do gerador de alta tensão, o equipamento DEVE ser completamente desligado da rede elétrica e a alimentação de bateria desconectada.  
> Nunca toque nos barramentos de potência com o gerador energizado.

---

### 4. PROCEDIMENTO PASSO A PASSO

#### ETAPA 1: Restauração / Instalação do Sistema Operacional (Modo U-Disk / Pendrive)
1. Conecte o pendrive de boot fornecido pela Neusoft na porta USB de serviço do computador industrial (remova os dois parafusos de fixação da tampa de proteção se necessário).
2. Ligue o sistema e pressione repetidamente a tecla **Delete** para ingressar no BIOS do sistema.
3. No BIOS:
   - Navegue até `Security` -> `Secure Boot menu` -> Desative o Secure Boot se aplicável.
   - Navegue até `Boot` -> Defina a unidade USB como primeira prioridade de inicialização (`Boot Option #1`).
   - Pressione **F10** para salvar e reiniciar.
4. O assistente de partição e restauração Ghost iniciará automaticamente:
   - Selecione a partição primária e confirme a restauração da imagem do sistema correspondente ao modelo de tela/detector (com ou sem Interface Box).
   - Insira o código Ghost PN indicado na placa ou documentação do equipamento.
5. Ao término da descompactação, remova o pendrive e reinicie o PC normalmente.

---

#### ETAPA 2: Configuração de Orientação de Tela (Intel Graphics)
Caso a interface gráfica inicialize invertida em 180° após a reinstalação:
1. Pressione `Ctrl + Alt + Delete` -> clique em **Log off**.
2. Faça login com o usuário: `cxdiadmin` / senha: `nmsadmin`.
3. Clique com o botão direito na Área de Trabalho -> **Resolução de Tela** (*Screen Resolution*).
4. Clique em **Configurações Avançadas** (*Advanced settings*) -> Aba **Painel de Controle de Gráficos e Mídia Intel**.
5. Em *Rotação* (*Rotation*), selecione: **Girar 180 Graus** (*Rotate to 180 Degrees*) e confirme em **OK**.

---

#### ETAPA 3: Ativação do Modo de Serviço e Configuração do Gerador Sedecal
1. **Desligue totalmente o equipamento** (chave geral e disjuntores).
2. Na placa de controle do gerador Sedecal, localize a microchave dip switch **SW7** e comute-a para a posição **ON** (Modo Service Ativado).
3. Ligue o equipamento:
   > [!NOTE]
   > Um alarme sonoro contínuo (bip) será emitido. Isso é normal e esperado indicando que o modo de serviço do gerador está ativo.
4. Na tela inicial do software de aquisição Neusoft, clique em **Opções de Reinício** (*Restart Options*).
5. Pressione `Ctrl + Alt + Delete` -> clique em **Log off** -> entre com `cxdiadmin` / `nmsadmin`.
6. Abra o menu Iniciar do Windows:
   - Caminho: `Iniciar` -> `Sedecal TechService` -> `Tech Service`.
7. Na janela do software do gerador:
   - Clique em **RESET ERROR** (o som de alarme contínuo cessará imediatamente e o botão **CONFIGURATION** será habilitado).
   - Clique no botão **CONFIGURATION**.
8. Parametrização dos Postos de Trabalho (*Workstations*):
   - **Posto WS1 (Bucky / Mesa):**
     - `Tube`: **1**
     - `WM`: **Bucky 1**
     - `AEC IC`: **0**
     - `WS LOCK`: **0**
     - `RAD/RF`: **RAD**
   - **Posto WS2 (Exposição Direta / Sem Bucky):**
     - `Tube`: **1**
     - `WM`: **direct**
     - `AEC IC`: **0**
     - `WS LOCK`: **0**
     - `RAD/RF`: **RAD**
9. Clique novamente em **Configuration** para gravar os dados na EEPROM da placa do gerador (o sistema emitirá dois tons sonoros curtos de confirmação de gravação).
10. Feche o utilitário Sedecal e desligue o sistema.
11. **Retorne a chave SW7 para a posição OFF** para desativar o modo de serviço do gerador.

---

#### ETAPA 4: Configuração de Rede Wi-Fi do Access Point (AP)
1. Ligue o sistema e faça login como `cxdiadmin` / senha: `nmsadmin`.
2. Acesse o Gerenciador de Dispositivos do Windows (*Device Manager*) e verifique qual porta Serial COM física ou virtual está atribuída à interface do Access Point (ex: `COM1` ou `COM2`).
3. Abra a ferramenta de serviço Canon:
   - Caminho: `Iniciar` -> `Canon Service Tool`.
   - Usuário: `cxdiadmin` | Senha: `Canononac`.
4. No menu principal da ferramenta, clique em **AP/LINK**.
5. Selecione a porta COM idêntica à anotada no Gerenciador de Dispositivos e clique em **Next**.
6. Insira os parâmetros de rádio e IP do Access Point:
   - **Local IP Address:** `192.168.100.10`
   - **Target IP Address:** `192.168.100.200`
   - **Subnet Mask:** `255.255.255.0`
   - **X-ray IF IP Address:** `192.168.100.96`
   - **ESSID:** `NMSAP`
   - **PSK (Chave de Segurança):** `nosecret`
   - **Channel Range:** `1-13ch, WS2, W58_a`
   - **Canal 2.4 GHz:** **OFF**
   - **Canal 5.0 GHz:** **ON**
   - **Canal Alvo / Frequência:** `149ch - 5745MHz` (Channel Bonding: *Above 40MHz*)
7. Clique em **Send** e confirme com **OK** (aguarde aproximadamente 3 minutos para a transmissão e reinicialização interna do módulo AP).
8. Clique em **OK** ao término do upload.

---

#### ETAPA 5: Pareamento por Infravermelho (IR Link) do Detector Flat Panel
1. Localize a janela de comunicação infravermelho (IR) no equipamento e no painel detector.
2. Na bandeja do Windows (canto inferior direito), clique com o botão direito no ícone do *Detector Infrared Link* e selecione **Show**.
3. Posicione o detector em frente ao sensor infravermelho do equipamento:
   - **Distância máxima:** $\le 30\text{ cm}$
   - **Desvio angular:** $< 10^\circ$ de alinhamento frontal direto.
4. Ligue a chave de alimentação da bateria do detector Flat Panel.
5. Pressione o botão liga/desliga do detector:
   - A barra de progresso no software fará o pareamento automático das chaves criptográficas Wi-Fi.
   - O pareamento estará bem-sucedido quando **os LEDs azul e verde do detector acenderem simultaneamente e ficarem estáveis**.

---

#### ETAPA 6: Associação de Protocolos e Limpeza de Detectores Anteriores
1. Retorne à tela principal da **Canon Service Tool**.
2. Clique no botão **Protocol Editor** -> selecione a guia **Workspace**.
3. Na lista de detectores associados, altere o detector antigo para o novo número de série recém-registrado e confirme em **OK** -> confirme o salvamento com **Yes**.
4. Retorne ao menu principal da ferramenta e clique em **Detector**.
5. Caso o detector antigo desativado ainda conste na lista, selecione-o e clique em **DEL** para excluir o registro inativo, deixando apenas o detector atualmente em operação.
6. Confirme a exclusão com **Yes**.

---

### 5. CHECKLIST DE LIBERAÇÃO CLÍNICA
- [ ] O sistema inicializa direto no software operacional NeuVision sem erros de tela invertida.
- [ ] O gerador Sedecal não emite mais bipes contínuos de modo de serviço (chave SW7 em OFF).
- [ ] O detector sem fio comunica-se via 5 GHz com indicador de sinal estável na tela (ícone verde).
- [ ] Realizado disparo de teste em modo Bucky e modo Direto sem artefatos de imagem.
- [ ] Verificado envio de imagem de teste via DICOM Storage para o PACS hospitalar.
