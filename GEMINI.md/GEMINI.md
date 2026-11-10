# Contexto do Projeto: Sistema EMED - Gestão de Equipamentos, OS, Estoque e Frota

## 1. Regra de Ouro de Desenvolvimento (CRÍTICO)
- **NUNCA apague, resuma ou simplifique funções existentes** no `app_emed.py`.
- Faça apenas alterações cirúrgicas e incrementais nas linhas necessárias, preservando 100% das abas, gráficos, tabelas SQLite e regras de negócio já implementadas.
- Evite linhas de código excessivamente longas em strings `f"..."` simples; prefira variáveis auxiliares ou `f"""..."""` para evitar erros de sintaxe.

## 2. Identidade Visual e UI (Streamlit)
- **Tema Escuro Nativo (`#0b132b` e `#1c2541`)** com destaques em ciano (`#64dfdf`) e texto claro (`#ffffff`).
- **Proibido botões brancos ou listas suspensas com fundo branco e letra branca:** Todo o CSS deve manter fundo escuro (`#1c2541`) e texto legível em `st.selectbox`, `st.multiselect`, `div[data-baseweb="popover"]`, `st.form_submit_button`, `st.expander`, `st.file_uploader` e `stElementToolbar`.
- **Feedback de Formulários:** Sempre que um cadastro ou edição (Carro, Cliente, OS, Técnico ou Estoque) for salvo, o formulário deve ser limpo/recolhido automaticamente e exibir uma mensagem clara de `"✅ Salvo com sucesso!"` no topo da tela.

## 3. Arquitetura do Banco de Dados (`emed.db` - SQLite WAL) e Núcleo Desacoplado (`emed_core.py`)
- `emed_core.py`: Módulo de domínio e repositório transacional (`WAL`, `busy_timeout=5000`, preservação de chave primária `id`, sincronização offline idempotente por `sync_hash`, baixa de estoque idempotente por `peca_baixada_ref`, estorno circular de reservas e progressão circular de etapas preventivas).
- `clientes_equipamentos`: Ordens de serviço com PK imutável `id`, matrizes/unidades, equipamentos, check-in/out, status (`ATIVO` / `CONCLUÍDO`), `tipo_contrato` (`CONTRATO` / `AVULSO`), `instrumento_necessario`, `etapa_preventiva`, `orcamento_anexo`, `condicao_pagamento`, `valor_os`, campos modulares de engenharia clínica, `sync_hash` e `peca_baixada_ref`.
- `clientes_internos`: Setores internos da empresa (Estoque/Almoxarifado, Financeiro, Infraestrutura & Frota, Laboratório Eletrónico) para abertura de OS internas e centros de custo.
- `tecnicos`: Cadastro da equipa técnica (`nome`, `telefone`, `sede`, `senha`, `perfil` [`Gestor` / `Técnico`], `assinatura_padrao`, `rubrica_img`).
- `veiculos`: Frota da empresa (`modelo`, `placa`, `km_atual`, `km_ultima_revisao`, `km_proxima_revisao`, `status_manutencao`, `foto_carro`, `historico_manutencao`, `proximas_manutencoes`).
- `estoque_pecas`: Peças comerciais e consumíveis (`codigo`, `nome_peca`, `quantidade`, `preco_custo`, `margem_contrato`, `margem_avulso`, `tipo_item` [`PEÇA COMERCIAL (OS)`, `CONSUMÍVEL INTERNO`, `INSTRUMENTO / FERRAMENTA`]).
- `solicitacoes_pecas`: Reservas online de peças e ferramentas solicitadas pelos técnicos, com gestão circular de entrega e estorno ao estoque.
- `baixas_consumiveis`: Saídas de consumíveis de uso diário (ex: abraçadeiras, fita isolante) sem necessidade de nota fiscal de saída.

## 4. Regras de Negócio Já Implementadas e Acordadas
1. **Gestão de Pendências & Painel do Técnico:**
   - A aba `🚨 Gestão de Pendências` aparece **apenas no perfil Gestor**, onde o gestor visualiza todas as pendências e direciona para o técnico disponível.
   - O técnico possui a aba própria `📋 Minhas Pendências (Técnico)` no seu login, evitando envio desnecessário de mensagens diárias no WhatsApp.
   - Existe opção de **Mudança / Reatribuição de Técnico** e **Reabertura de OS** no nome de outro técnico caso o responsável original esteja ocupado, mantendo o histórico da pendência e os instrumentos necessários visíveis na OS para evitar retrabalho.
2. **Preventivas Divididas por Etapas (POP / IT):**
   - As preventivas são divididas por partes do equipamento (ex: *Etapa 1: Mesa de exames e Console*, *Etapa 2: Gantry, PDU e Quadro*, *Etapa 3: Tubo e Alta Tensão*).
   - Na execução da OS, o sistema exibe o que foi feito nas intervenções anteriores daquele equipamento para o técnico saber exatamente qual parte inspecionar na visita atual.
3. **QR Code por Equipamento (Portal do Cliente):**
   - Cada equipamento gera um QR Code (`?equipamento_qr=...&cliente_qr=...`) que, ao ser escaneado pelo cliente, exibe o histórico de intervenções daquele aparelho e permite abrir um novo chamado técnico diretamente para ele.
4. **Orçamento Aprovado, Faturamento (Boleto vs. PIX 10%) e OS Modular (6 Abas):**
   - A execução de OS está organizada em **6 abas modulares** para facilitar o uso no celular e enriquecer a rastreabilidade de Engenharia Clínica:
     1. `📢 1. Defeito Relatado` (`defeito_relatado`, `condicao_inicial`, `pre_atendimento` e histórico das últimas intervenções).
     2. `🔍 2. Problemas Encontrados` (`problemas_encontrados`, `causa_raiz` e `parametros_medidos` como tensão F-N, Terra-Neutro, temp. da sala e disparos).
     3. `🛠️ 3. Serviço & Peças` (`etapa_preventiva`, `checklist_pop`, `servico_executado` e baixa automática de peças).
     4. `🚨 4. Pendências & Obs.` (Status Concluído vs. Pendência Ativa, `condicao_final`, `instrumento_necessario` e `observacoes_gerais` / recomendações ao hospital).
     5. `📸 5. Fotos & Anexos` (`foto_evidencia` Antes/Defeito, `foto_depois` Serviço Pronto e `orcamento_anexo`).
     6. `✍️ 6. Assinatura & Fecho` (Faturamento Boleto integral ou PIX com 10% de desconto, **Rubrica Pré-Salva do Técnico** aplicada automaticamente e **Quadro Touch HTML5 Canvas** para coletar apenas a assinatura do cliente com o dedo na tela do celular em `assinatura_cliente_img`, tanto online quanto no Coletor Offline).
5. **Solicitação Online de Peças e Consumíveis:**
   - Técnicos podem ticar peças e ferramentas num formulário que abate/reserva o saldo online no SQLite em tempo real (impedindo conflito se dois técnicos pedirem a última peça ao mesmo tempo).
   - Consumíveis internos têm aba própria para baixa rápida de uso diário na oficina ou em campo sem nota de saída.
6. **Gestão de Técnicos, Frota e Logística:**
   - Na aba de Técnicos: tabela na parte superior e botão limpo em baixo para abrir o formulário de adicionar/editar/excluir com `selectbox` de seleção do técnico e opção de salvar a rubrica (`rubrica_img` e `assinatura_padrao`). O **Ponto de Partida** não fica no cadastro do técnico, mas sim na aba de **Logística / Mapa (`🗺️ Mapa & Planeamento de Rotas`)**.
   - Na aba de Veículos (exclusiva para Gestor): tabela e cartões no topo, botão limpo em baixo para adicionar/editar/excluir veículo, upload de foto do carro, histórico de manutenções realizadas e próximas manutenções programadas.