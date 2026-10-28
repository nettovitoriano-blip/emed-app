# INSTRUÇÃO DE TRABALHO TÉCNICA

| <img src="emed_svg-1.png" width="160" alt="eMED" /> | **EMED ELETROMEDICINA LTDA.**<br>**Diagnóstico por Imagem**<br>CNPJ: 03.611.974/0001-08 | **CÓDIGO:** `IT-TOMO-GE-017`<br>**VERSÃO:** `2.4 Homologada`<br>**REVISÃO:** `Rev. 02 (26/10/2026)`<br>**NORMA:** `ANVISA RDC 611` |
|:---:|:---|:---|

---


## IT-TOMO-GE-017: Guia de Comandos do Terminal Linux, Diagnóstico de Rede e Recuperação de Nós (GE CT)
**Sistemas:** Tomógrafos GE BrightSpeed (Lite, Select, 16, Ultra, Plus) & Brivo CT385  
**Ambiente:** Sistema Operacional Linux Red Hat / CentOS Embarcado no Console (Host Computer)  
**Documento Base:** Manuais de Software GE 03_Comandos_Linux_GE & 04_Utilitarios_Diagnostico_Linux  
**Nível de Acesso:** Diagnóstico por Imagem / Especialista de Campo eMED  
**Revisão:** 1.0 - Guia Prático de Comandos CLI de Serviço  

---

### 1. OBJETIVO E ESCOPO
Fornecer um guia rápido, prático e padronizado dos comandos essenciais de linha de comando (CLI) executados no terminal Linux do console do tomógrafo GE para diagnóstico de hardware, reinicialização limpa de subsistemas travados, checagem de barramento de rede e análise de logs de erro em tempo real.

---

### 2. COMANDOS DE DIAGNÓSTICO E STATUS DO HARDWARE

| Comando Linux | Função Técnica em Campo | Observações / Parâmetros |
| :--- | :--- | :--- |
| **`checkHW`** | Executa teste abrangente de integridade de todos os nós de hardware do tomógrafo (Gantry, PDU, Mesa, Gerador, Detector) | Retorna status `PASS` ou `FAIL` por subsistema |
| **`show_sw_version`** | Exibe a versão exata do software clínico e pacotes instalados no sistema | Ex: `06MW29.7`, `07MWxx.x`, `11HWxx.x` |
| **`gantry_status`** | Mostra o estado atual das travas, tilt, velocidade de rotação e temperatura interna do Gantry | Monitoramento térmico em tempo real |
| **`recon_status`** | Exibe o status da fila de reconstrução e dos nós do Recon Engine / IG Board | Usado para diagnosticar filas de reconstrução travadas |
| **`df -h`** | Verifica o espaço livre em disco nas partições do sistema e imagens | Fundamental quando o console recusa salvar novos exames |

---

### 3. COMANDOS DE PARADA E INICIALIZAÇÃO LIMPA DO SISTEMA

> [!IMPORTANT]
> Quando o software do operador congelar ou houver travamento de comunicação com o Gantry, **NUNCA desligue o console no botão de força** (isso corrompe o banco de dados Sybase). Utilize os scripts de parada controlada abaixo:

1. **Parar todos os processos de software de forma limpa:**
   ```bash
   stopall
   ```
   *Aguarda a finalização ordenada das tarefas de aquisição, reconstrução e banco de dados.*

2. **Iniciar o software clínico do Host:**
   ```bash
   starthost
   ```
   *Reinicializa a interface gráfica do operador (GOC) e as conexões de rede locais.*

3. **Reinicializar os nós de controle do Gantry sem desligar o console:**
   ```bash
   reset_gantry_nodes
   ```

---

### 4. MONITORAMENTO DE LOGS EM TEMPO REAL

Para acompanhar o que o sistema está registrando durante a ocorrência de um erro ou disparo:
1. **Acompanhar o log do sistema em tempo de execução:**
   ```bash
   tail -f /usr/g/service/log/syslog
   ```
2. **Visualizar os últimos erros críticos do gerador JEDI:**
   ```bash
   grep -i "generator" /usr/g/service/log/syslog | tail -n 50
   ```
3. **Verificar erros do driver do kernel Linux:**
   ```bash
   dmesg | tail -n 40
   ```

---

### 5. DIAGNÓSTICO DE REDE E COMUNICAÇÃO DE NÓS
* **Testar comunicação com a placa do Gantry:**
  ```bash
  ping 192.168.0.10
  ```
* **Testar comunicação com a mesa do paciente (Table Node):**
  ```bash
  ping 192.168.0.11
  ```
* **Testar comunicação com o Recon Engine:**
  ```bash
  ping 192.168.0.2
  ```
* **Verificar portas e conexões DICOM abertas:**
  ```bash
  netstat -tuln | grep 104
  ```
