# IT-21: Procedimento Mestre de Instalação e Recarga de Software do Sistema (LFC - Load From Cold) — GE BrightSpeed & Discovery / Optima Series

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Engenharia Clínica & Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-021`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## 1. OBJETIVO & APLICAÇÃO CLÍNICA
Esta Instrução de Trabalho (IT) padroniza o procedimento oficial de **Instalação do Sistema Operacional (OS Load)**, **Software de Aplicação (Application SW Load)**, **Service Packs**, **Opções Clínicas** e **Calibração de Firmware (Flash Download)** na linha de tomógrafos computadorizados GE Healthcare:
- **GE BrightSpeed Series:** Select, Elite, Edge, Excel, Velocity (4 e 16 cortes).
- **GE Optima Series:** CT580 e CT540.
- **GE Discovery Series:** CT590 RT.
- **Consoles:** True-In-One (TIO) e All-In-One (AIO) equipados com Host Computer HP xw8600 ou Z800 e torre de periféricos DVD-RAM.

> [!WARNING]
> **Risco Crítico de Perda de Dados de Pacientes:**
> Este procedimento formata e sobrescreve integralmente os discos do Host Computer. Antes de iniciar, certifique-se de que a fila do PACS (Network Queue) e a fila de arquivamento (Archive Queue) estejam 100% vazias e que todos os exames clínicos tenham sido transferidos com sucesso.

---

## 2. FERRAMENTAS, MÍDIAS & MATERIAIS NECESSÁRIOS
- **Kit Oficial de Discos de Instalação:**
  1. Disco 1: DVD do Sistema Operacional Linux (OS Media — ex: CTT 6.3.10 P/N 5372915).
  2. Disco 2: DVD do Software de Aplicação (ex: 09BW35.11 P/N 5372914 ou 09HW30.4).
  3. Disco 3: CD de Service Pack / Patches aplicáveis (ex: SP 1.7 ou superior).
  4. Disco 4: DVD/MOD de Opções Permanentes de Software (Software Option Keys).
- **Mídias Graváveis virgens:**
  - Pelo menos 2 discos DVD-RAM sem cartucho (bare media) compatíveis com a New Media Tower (P/N 5270510-10).
- **Service Key:** Dongle físico Classe C ou Classe M da GE para acesso administrativo e comandos de terminal.

---

## 3. ETAPA 1: CAPTURA DE DADOS & BACKUP MANDATÓRIO (PRÉ-REQUISITOS)

### 3.1 Coleta de Dados de Rede e Configuração (INFO Sheet)
1. No console com o software ativo, abra um terminal Unix Shell através da Toolchest:
   ```bash
   cat /usr/g/config/INFO
   ```
2. Anote detalhadamente ou tire foto dos parâmetros exibidos:
   - Host Name, Endereço IP do Tomógrafo, Máscara de Sub-rede e Gateway padrão.
   - Endereço IP e porta DICOM dos nós PACS, Workstations AW e impressoras de filme.
   - Posição do volume da voz automática (AutoVoice Volume - atalho `<ALT-F3>`).
3. Verifique a configuração de divisão de exames (Exam Split Mode):
   ```bash
   su -
   # Senha padrão de fábrica: #bigguy
   ls -l ~ctuser/ves/.hesMode
   ```
   - Se o arquivo existir: o sistema opera em modo **HES (Hard Exam Split)**.
   - Se retornar *"No such file or directory"*: o sistema opera em modo **VES (Virtual Exam Split)**.

### 3.2 Backup dos Parâmetros de Runtime do Gerador JEDI
1. Acesse: `Service Desktop` -> `Hardware / Diagnostics` -> `HV Subsystem Utilities` -> `JEDI Generator Tool`.
2. Selecione a função `Save JEDI Runtime Parameters` e confirme o salvamento.

### 3.3 Execução do Duplo "Save System State"
> [!IMPORTANT]
> Devem ser realizadas obrigatoriamente **duas gravações de System State**:
> 1. Gravado no DVD-RAM original do cliente e rotulado como *"Linux System State Backup Reversão"*.
> 2. Gravado em um novo DVD-RAM virgem rotulado com a nova versão de software instalada.

**Passo a passo no Service Desktop:**
1. Insira o disco DVD-RAM na unidade da torre de periféricos.
2. Selecione `Service Desktop` -> `Utilities` (ou `PM`) -> `System State`.
3. Clique em `ALL` para marcar todas as calibrações, perfis e caracterizações.
4. Clique em `SAVE`. Aguarde a mensagem:  
   `Save/restore system state: completed successfully`.
5. Clique em `DISMISS` apenas uma vez.

---

## 4. ETAPA 2: CARGA DO SISTEMA OPERACIONAL (OS LOAD)

1. **Isolamento de Rede:** Remova o cabo de rede hospitalar (Hospital Backbone) no painel traseiro do console (Console Bulkhead Assembly) para evitar conflitos de IP ou broadcast durante o LFC.
2. Remova a tampa frontal do console para ter acesso direto ao drive de DVD do Host PC.
3. Insira o **DVD do Sistema Operacional (OS)** no drive interno do Host PC.
4. Desligue e reinicie o console de forma limpa:
   - Se o software estiver ativo: clique em `Shut Down` -> `Restart`.
   - Se o software estiver caído, execute no terminal:
     ```bash
     sync; sync; halt
     ```
   - Aguarde 30 segundos com a chave desligada para acomodação mecânica do disco rígido e ligue novamente.
5. **Prompt de Inicialização (Boot Prompt):**
   - Durante a inicialização do BIOS (HP xw8600 / Z800), o sistema exibirá o prompt `boot:`.
   - Digite exatamente:
     ```bash
     GEHC2
     ```
     *(Pressione `<Enter>`. **ATENÇÃO:** O comando `GEHC2` é mandatório para consoles com dois monitores; digitar apenas `GEHC` resultará na unificação das telas em um único monitor, exigindo novo LFC).*
6. O processo de partição e formatação automática leva aproximadamente **20 minutos**.
7. Ao término, o disco de OS será ejetado automaticamente e um botão vermelho `[Reboot]` será exibido na tela.
8. Retire o disco e pressione `<Enter>` para reiniciar.

---

## 5. ETAPA 3: RESTAURAÇÃO DO ARQUIVO INFO E DADOS DE CONFIGURAÇÃO

1. Após o reinício, o monitor abrirá a janela de terminal com o prompt `[root@localhost root]#`.
2. Insira o DVD-RAM do **System State** no drive do Host PC.
3. Execute a cópia dos arquivos críticos de calibração para a raiz:
   ```bash
   cp -p /mnt/cdrom/service_mod_data/system_state/INFO /
   cp -p /mnt/cdrom/service_mod_data/system_state/scanRx.db /
   ```
4. Ejete o disco de System State do drive do Host PC.

---

## 6. ETAPA 4: INSTALAÇÃO DO SOFTWARE DE APLICAÇÃO (APPLICATION SW LOAD)

> [!CAUTION]
> **Risco de Danos à Placa DCB e Downtime:**
> A seleção incorreta do tipo de hardware de Gantry ou Detector/DAS provocará queima ou incompatibilidade de firmware durante o Flash Download. Verifique rigorosamente a plaqueta de identificação do gantry antes de confirmar.

1. Insira o **DVD do Software de Aplicação** (ex: 09BW35.11) no drive do Host PC.
2. Em cerca de 15 segundos, o pop-up de execução automática será exibido. Caso não apareça em até 2 minutos, execute:
   ```bash
   mount /media/cdrom
   /media/cdrom/autorun
   ```
3. Na janela `Installation Utility`, selecione **`Load`**.
4. Configure os parâmetros essenciais:
   - **Aba System:** Configure o fuso horário local (`America/Sao_Paulo`), valide o próximo número de exame (`Next Patient Exam #`) restaurado do INFO e os dados do hospital.
   - **Aba Preferences:**
     - Unidade de peso: `kg`.
     - Idioma: Selecione provisoriamente **`English`** durante a instalação (o idioma Português do Brasil deve ser aplicado após o término do LFC para evitar falhas em pacotes de imagem avançada).
     - `Preferred FastCal kV`: Selecione todos os kVs clínicos utilizados pelo serviço (80, 100, 120 e 140 kVp).
     - `Dose Information Display`: Ative em **`ON`** (atendimento normativo ANVISA RDC 611 / IEC 60601-2-44).
     - `Dose Record`: Selecione **`ON`** (geração automática de DICOM Radiation Dose Structured Report - RDSR).
   - **Aba Hardware:** Confirme o modelo de Gantry, modelo de mesa de exames e o detector GDAS-16 cortes.
5. Clique em `Start Install`. O processo levará aproximadamente **40 minutos**.

---

## 7. ETAPA 5: INSTALAÇÃO DE SERVICE PACK & ATUALIZAÇÕES

1. Após o término da aplicação e reinicialização, abra um terminal Unix Shell:
   ```bash
   cleanMon
   su -
   # Digite a senha administrativa
   start_udev
   ```
2. Insira o CD de **Service Pack** no drive. Aguarde 15 segundos após o retorno `OK` e execute:
   ```bash
   patch_install -c
   ```
3. O instalador listará cada patch e solicitará confirmação: `I will install update [Patch Name], is this ok? [y/n]`. Digite **`y`** para todos os patches oficiais.
4. Verifique a instalação:
   ```bash
   showprods | grep -i ServicePack
   ```
5. Reinicie a estação de trabalho:
   ```bash
   reboot
   ```

---

## 8. ETAPA 6: INSTALAÇÃO DE OPÇÕES DE SOFTWARE & RESTORE SYSTEM STATE

### 8.1 Chaves Permanentes de Opções (Software Option Keys)
1. Insira o disco de opções no drive da torre de periféricos.
2. Acesse: `Service Desktop` -> `Configuration` -> `Install Options` -> `Install`.
3. Selecione `Permanent` -> `MEDIA`.
4. Instale as opções obedecendo rigorosamente à **ordem oficial de precedência da GE**:
   1. `VolumeViewer` (Visualização 3D/MIP/MPR)
   2. `CardIQ2` (Pacote cardíaco)
   3. `CardEP` (Eletrofisiologia)
   4. `Connect pro (enable pps)` (Lista de trabalho DICOM Modality Worklist)
   5. `Exam Split` (Conforme modo anotado no pré-requisito: VES ou HES)
   6. Demais opções clínicas (SmartPrep, Helical Tilt, AutoMA, etc.).
5. Clique em `Quit` e **aguarde 5 minutos** sem acionar outros comandos para a gravação nas memórias não voláteis.

### 8.2 Restauração das Calibrações e Arquivo de Estado
1. No terminal, verifique o barramento SCSI: `scsistat`.
2. Insira o DVD-RAM de System State gravado na Etapa 1.
3. Acesse `Service Desktop` -> `Utilities` -> `System State` -> `ALL` -> `RESTORE`.
4. Ao término bem-sucedido, se surgir a mensagem *"Scan Hardware Reset?"*, selecione obrigatoriamente **`[NO]`** (o reset de hardware será executado durante o Flash Download a seguir).

---

## 9. ETAPA 7: ATUALIZAÇÃO DE FIRMWARE (FLASH DOWNLOAD) & RECONFIGURAÇÃO

1. Teste a comunicação de rede interna com os módulos do gantry:
   ```bash
   ping -c 3 orp
   ping -c 3 tgp
   ```
2. Acesse: `Service Desktop` -> `Utilities` -> `FLASH DOWNLOAD` -> `UPDATE`.
3. Quando solicitado, insira o número de série do Colimador Motorizado e confirme a gravação do arquivo CCB (`Yes`).
4. **Alerta de Gerador JEDI:** Se surgir a mensagem *"The entire Generator database has been reset"*, acione a restauração dos parâmetros JEDI salvos no passo 3.2 e programe a calibração de filamento.
5. Execute a reconfiguração final:
   ```bash
   su -
   reconfig
   ```
   Clique em `[config]`. O sistema executará o reboot completo.

---

## 10. ETAPA 8: CERTIFICAÇÃO DO TUBO DE RAIOS-X (TUBE IDENTIFICATION)
1. Durante a primeira inicialização após o Flash Download, surgirá a tela da ferramenta **Tube Install Certification Tool**.
2. Verifique a etiqueta de identificação do tubo no monobloco:
   - Se for tubo original GE (Performix Pro / Solarix): clique em **`[GE MEDICAL SYSTEM TUBE]`**.
   - Se for tubo recondicionado ou de terceiros: clique em **`[ALL OTHERS]`**.
3. Confirme e salve.

---

## 11. ETAPA 9: TESTES DE SANIDADE DO SISTEMA, RECONSTRUÇÃO & LIBERAÇÃO

1. **Reconexão de Rede:** Reconecte o cabo do Hospital Backbone no painel bulkhead traseiro.
2. **Disparos de Teste (Sanity Scans):**
   - Realize 1 varredura de **Scout (Topograma)** com phantom de água centralizado.
   - Realize 1 varredura **Axial** de 16 cortes em 120 kVp.
   - Realize 1 varredura **Helicoidal** com pitch padrão.
3. **Teste de Reconstrução Retroativa (Retro Recon):**
   - Acesse `Recon Management` -> `RETRO RECON` -> selecione a série modelo `rat gold` -> clique em `Confirm`.
   - Confirme a renderização da imagem na tela e apague as imagens de teste via Image Works.
4. **Calibração de Início de Turno (FastCal):**
   - Execute o procedimento de aquecimento e `FastCal` para estabilização de ganho dos canais do detector GDAS.
5. **Gravação do Disco Final de System State Atualizado:**
   - Realize um novo `Save System State: ALL -> SAVE` no disco definitivo, etiquetando com a data, versão de software e assinatura técnica.

---

## 12. CHECKLIST DE CONFORMIDADE ANVISA RDC 611 / LIBERAÇÃO
- [ ] Fila de exames do PACS vazia antes do LFC (zero perda de dados).
- [ ] Particionamento e carga do Linux GEHC2 com dois monitores operacionais.
- [ ] Software de aplicação e Service Pack instalados sem erros no log.
- [ ] Chaves de opções (VolumeViewer, Worklist, etc.) reativadas e validadas.
- [ ] Calibrações de Gantry e Detector recuperadas via Restore System State.
- [ ] Flash Download executado com comunicação estável (ORP e TGP).
- [ ] Certificação do Tubo de Raios-X realizada.
- [ ] Disparos de Scout, Axial e Helicoidal realizados com sucesso.
- [ ] Backup final de System State gravado em DVD-RAM e guardado no console.
- [ ] Equipamento 100% liberado para uso clínico com emissão de Laudo Técnico.
