# 🗂️ Pasta Oficial de URLs do Sistema EMED

Esta pasta reúne todos os endereços (URLs) reais servidos pelo **Sistema EMED Eletromedicina** (`emed_app_server.py`).

- **Base Local (neste PC):** `http://127.0.0.1:8502`
- **Base Produção / Domínio:** `https://emedservice.med.br` (e app em `https://app.emedservice.med.br` / Render `https://emed-app-6ofv.onrender.com`)
- **Versão web interativa desta pasta:** `/urls` (restrita a Gestor/Admin autenticados) ou abrindo [Central_URLs_EMED.html](./Central_URLs_EMED.html) localmente.

---

## 1. Portais Principais & Login

| Módulo | Caminho (URL) | Quem Acessa | Descrição |
|---|---|---|---|
| **App Principal EMED (PWA)** | `/` | Colaborador / Gestor | Sistema principal (redireciona para login se não autenticado) |
| **App Modo Gestor** | `/?modo=gestor` | Gestor | Painel gerencial (Mural, Frota, Financeiro, Clientes, Equipe) |
| **App Modo Técnico** | `/?modo=tecnico` | Técnico | Visão de campo (OS, Check-in/Out, Assinatura, Peças) |
| **Tela de Login** | `/login` (ou `/login.html`) | Público | Autenticação PWA e liberação de aparelho (código 6 dígitos) |
| **Portal do Cliente / Gestor da Unidade** | `/portal-cliente` | Cliente (Login próprio) | PGTS RDC 509, Dossiê VISA RDC 611, EPIs, Equipe, DANFEs, Laudos PDF e Pedir Intervenção |
| **Portal Fiscal (NFS-e & Radar DF-e)** | `/fiscal` | Fiscal / Diretoria | Emissão, cancelamento, DANFEs, XMLs e fechamento contábil |
| **Sistema Supervisório SOC** | `/supervisorio` | Gestor / Admin | Auditoria de logins, bloqueio de IPs, varredura, Honeypot e **Gerador de Acesso de Clientes** |
| **Pasta Web de URLs** | `/urls` | Gestor / Admin | Central pesquisável com botões de copiar e abrir links |

> 🔐 **Como gerar/redefinir o Login do Portal do Cliente (`/portal-cliente`):**  
> Acesse `/supervisorio` -> **🔑 Gerar Acesso de Cliente**, ou no App principal em **Triagem / Portal do Cliente** -> **🔑 Gerar Acesso**. As credenciais ficam gravadas com hash **PBKDF2** na tabela `clientes_acessos_portal` do `emed.db`.

---

## 2. Mapas, Telemetria, Frota & Fabricantes

| Módulo | Caminho (URL) | Aliases | Descrição |
|---|---|---|---|
| **Mapa do Gestor / Telemetria / RDC 611** | `/mapa-gestor` | `/gestao/mapa`, `/telemetria`, `/dossie-rdc` | Mapa geolocalizado de unidades, telemetria TLF (Raio-X) e dossiê |
| **EmedNav GPS Veicular** | `/nav` | `/gps`, `/emedcar` | Navegador GPS veicular com radares e roteamento |
| **Painel de Frota** | `/frota` | — | Monitoramento dos veículos da frota EMED |
| **Central Konica Minolta** | `/konica-central` | `/api/konica/central` | Painel dedicado ao parque instalado e OS Konica Minolta |
| **Formulário Instalação Konica RX** | `/formulario-konica-rx` | `/api/instalacao/konica-rx` | Checklist `FR_SE00003_03` imprimível em 12 páginas |
| **Apresentação Institucional** | `/apresentacao` | — | Slides interativos do Sistema EMED |

---

## 3. Links Externos com QR Code / Token / ID

| Recurso | Caminho (URL) | Observação |
|---|---|---|
| **Prontuário QR do Equipamento** | `/qrcode/equipamento/{id}` | Abrir ao escanear etiqueta colada no equipamento |
| **Etiqueta QR do Equipamento** | `/qrcode/equipamento/{id}/etiqueta` | Etiqueta para impressão |
| **Rastreio Público de Laboratório QR** | `/lab/r/{token}` | Status em bancada compartilhado com o cliente |
| **Proposta / Orçamento Interativo** | `/proposta/{os_id}` | Aprovação/recusa de orçamento online |
| **Autorização de Entrada (Portaria)** | `/api/hospital/autorizacao-entrada/{id}/imprimir` | Carta de credenciamento para portaria hospitalar |
| **Protocolo Entrega / Devolução** | `/api/protocolo-entrega/imprimir/{id}` | Comprovante A4 com assinatura touch |
| **Etiquetas QR Laboratório (A4)** | `/api/lab/etiquetas-qr` | Folha A4 (requer login) |
| **Etiquetas QR Ferramentas (A4)** | `/api/ferramentas/etiquetas-qr` | Folha A4 (requer login) |

---

## 4. Relatórios A4, Documentos Fiscais, SST & Exportações

| Documento | Caminho (URL) | Permissão |
|---|---|---|
| **Laudo Técnico da OS (A4)** | `/api/imprimir/{os_id}` | Login EMED ou Cliente dono |
| **Download PDF da OS** | `/api/pdf/{os_id}` | Login EMED |
| **DANFE / NFS-e da OS ou Nota** | `/api/fiscal/danfe/{os_id}` / `/api/fiscal/danfe/nfe/{nota_id}` | Login EMED/Fiscal ou Cliente dono |
| **PGTS Completo da Unidade (RDC 509)** | `/api/unidade/pgts/imprimir?cliente={NOME}` | Login EMED ou Cliente dono |
| **Dossiê Vigilância Sanitária (RDC 611)** | `/api/cliente/dossie-radiologico/imprimir?cliente={NOME}` | Login EMED ou Cliente dono |
| **Ficha Completa SST do Colaborador (ASOs, EPIs, Treinamentos)** | `/api/equipe/colaborador/imprimir?nome={NOME}` | Login EMED |
| **Relatório PPR/CNEN Dosimetria EMED** | `/api/equipe/dosimetria/imprimir` | Login EMED |
| **Relatório Contábil (A4)** | `/api/financeiro/relatorio-contabil/imprimir` | Gestor |
| **Exportação Planilha Excel** | `/api/exportar-excel` | Login EMED |
| **Exportação CSV Auditoria Logins** | `/api/supervisorio/exportar-csv` | Gestor / Admin |

---

## 5. Saúde do Servidor, Telemetria, Webhooks & Segurança

| Endpoint | Caminho (URL) | Autenticação |
|---|---|---|
| **Healthcheck / Ping** | `/healthz` ou `/api/ping` | Público |
| **Telemetria GPS J16 (POST/PUT)** | `/api/gps/telemetria` / `/api/v1/veiculos/odometro` | `Authorization: Bearer <EMED_GPS_API_KEY>` |
| **Webhook Bancário PIX (POST)** | `/api/pix/webhook` | Header `X-Webhook-Secret` (`EMED_PIX_WEBHOOK_SECRET`) |
| **Honeypot Decoy (Armadilha)** | `/admin/dashboard` | ⚠️ Não usar para operação — isca para capturar invasores |
