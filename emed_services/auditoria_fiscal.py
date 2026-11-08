# -*- coding: utf-8 -*-
"""
Módulo de Auditoria Contínua e Avaliação de Conformidade Fiscal (EMED Eletromedicina).
Responsável por:
- Monitorar todas as alterações realizadas pelo setor fiscal (emissões, retificações, cancelamentos, envios).
- Executar o motor de compliance tributário e estabilidade de processos.
- Gerar histórico estruturado (Diff Antes vs Depois) para compliance e governança.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from emed_services.repositories import DB_NAME, get_db_connection


def avaliar_conformidade_fiscal(
    dados_nf: Dict[str, Any],
    dados_os: Optional[Dict[str, Any]] = None,
    historico_eventos: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Avalia a conformidade fiscal e processual de uma Nota Fiscal antes ou após a emissão/retificação.
    Retorna score de 0 a 100, status geral ('CONFORME', 'ALERTA', 'NAO_CONFORME') e lista de regras.
    """
    dados_os = dados_os or {}
    historico_eventos = historico_eventos or []
    
    score = 100
    regras = []
    
    val_servicos = float(dados_nf.get("valor_servicos") or 0.0)
    val_pecas = float(dados_nf.get("valor_pecas") or 0.0)
    total_nf = round(val_servicos + val_pecas, 2)
    tipo_nota = str(dados_nf.get("tipo_nota") or "").upper()
    regra_fiscal = str(dados_nf.get("regra_fiscal") or "").upper()
    
    # -------------------------------------------------------------
    # REGRA 1: Compliance de Peça Usada sem NF -> Faturamento 100% Serviço
    # -------------------------------------------------------------
    peca_desc = str(
        dados_os.get("peca_selecionada") or
        dados_os.get("peca_manual") or
        dados_os.get("peca_baixada_ref") or
        dados_os.get("peca") or
        dados_nf.get("peca_desc") or ""
    ).upper()
    tipo_peca_estoque = str(dados_os.get("tipo_peca_estoque") or dados_nf.get("tipo_peca_estoque") or "").upper()
    
    indicadores_usada = ["USAD", "REMANUF", "RECUPER", "SEMI-NOV", "DESMANCHE", "TESTADA", "SEM NF", "ESTOQUE PROPRIO"]
    eh_peca_usada = any(ind in peca_desc for ind in indicadores_usada) or "USAD" in tipo_peca_estoque
    
    if eh_peca_usada:
        if val_pecas > 0 and "100%" not in tipo_nota and regra_fiscal != "SERVICO_TOTAL":
            score -= 40
            regras.append({
                "codigo": "REG_01_PECA_USADA",
                "titulo": "Peça Usada sem NF faturada como Mercadoria",
                "status": "REPROVADO",
                "gravidade": "ALTA",
                "descricao": (
                    f"A OS utilizou peça usada/remanufaturada ({peca_desc[:40]}), porém a NF foi "
                    f"lançada com valor de mercadoria (R$ {val_pecas:,.2f}). Risco tributário de saída sem documento de entrada. "
                    f"Obrigatoriamente deve ser faturada como 100% Prestação de Serviço (NFS-e)."
                ),
                "recomendacao": "Retificar para '100% NOTA DE SERVIÇO (NFS-e)' incorporando o valor no serviço técnico."
            })
        else:
            regras.append({
                "codigo": "REG_01_PECA_USADA",
                "titulo": "Peça Usada faturada como 100% Serviço (Compliance OK)",
                "status": "APROVADO",
                "gravidade": "BAIXA",
                "descricao": "Peça usada/remanufaturada devidamente faturada embutida em serviço municipal (NFS-e), atendendo às normas fiscais.",
                "recomendacao": "Fluxo em conformidade."
            })
    else:
        regras.append({
            "codigo": "REG_01_PECA_USADA",
            "titulo": "Classificação de Mercadorias e Serviços",
            "status": "APROVADO",
            "gravidade": "BAIXA",
            "descricao": "Nenhuma aplicação de peça usada sem nota fiscal identificada.",
            "recomendacao": "Fluxo padrão."
        })

    # -------------------------------------------------------------
    # REGRA 2: Divergência Proposta Comercial Aprovada vs Total Faturado
    # -------------------------------------------------------------
    val_proposta = float(dados_os.get("valor_os") or dados_os.get("valor_proposta") or dados_os.get("valor_total") or 0.0)
    status_proposta = str(dados_os.get("status_proposta") or "").upper()
    
    if val_proposta > 0:
        dif_proposta = round(abs(total_nf - val_proposta), 2)
        if dif_proposta > 1.0:
            justificativa = dados_nf.get("motivo_retificacao") or dados_nf.get("justificativa_divergencia")
            if justificativa:
                score -= 10
                regras.append({
                    "codigo": "REG_02_DIVERGENCIA_PROPOSTA",
                    "titulo": "Divergência Proposta Comercial com Justificativa",
                    "status": "ALERTA",
                    "gravidade": "MEDIA",
                    "descricao": (
                        f"O valor faturado (R$ {total_nf:,.2f}) diverge da proposta aprovada (R$ {val_proposta:,.2f}) "
                        f"em R$ {dif_proposta:,.2f}. Justificativa registrada: '{justificativa}'."
                    ),
                    "recomendacao": "Verificar se cliente assinou aditivo comercial ou autorização de serviços adicionais."
                })
            else:
                score -= 25
                regras.append({
                    "codigo": "REG_02_DIVERGENCIA_PROPOSTA",
                    "titulo": "Divergência entre Proposta Comercial e NF sem Justificativa",
                    "status": "ALERTA",
                    "gravidade": "ALTA",
                    "descricao": (
                        f"O valor faturado (R$ {total_nf:,.2f}) diverge da proposta aprovada (R$ {val_proposta:,.2f}) "
                        f"em R$ {dif_proposta:,.2f} sem justificativa formal do fiscal."
                    ),
                    "recomendacao": "Informar a justificativa da variação contratual antes de validar a nota."
                })
        else:
            regras.append({
                "codigo": "REG_02_DIVERGENCIA_PROPOSTA",
                "titulo": "Conformidade com Proposta Comercial",
                "status": "APROVADO",
                "gravidade": "BAIXA",
                "descricao": f"Valor faturado (R$ {total_nf:,.2f}) coincide exatamente com o valor aprovado pelo cliente.",
                "recomendacao": "Nenhuma divergência identificada."
            })

    # -------------------------------------------------------------
    # REGRA 3: Estabilidade de Processo e Retificações Sucessivas
    # -------------------------------------------------------------
    retificacoes_anteriores = [e for e in historico_eventos if e.get("tipo_evento") == "RETIFICACAO"]
    qtd_retif = len(retificacoes_anteriores)
    
    if qtd_retif >= 2:
        score -= 20
        regras.append({
            "codigo": "REG_03_RETIFICACOES_SUCESSIVAS",
            "titulo": f"Instabilidade no Processo: {qtd_retif} Retificações Anteriores",
            "status": "ALERTA",
            "gravidade": "MEDIA",
            "descricao": (
                f"Esta OS já sofreu {qtd_retif} alterações fiscais anteriores. "
                "Retificações repetidas geram custos operacionais e retrabalho contábil."
            ),
            "recomendacao": "Alinhar processo de conferência prévia no laudo técnico antes de gerar a minuta da nota fiscal."
        })
    elif qtd_retif == 1:
        score -= 5
        regras.append({
            "codigo": "REG_03_RETIFICACOES_SUCESSIVAS",
            "titulo": "Nota Fiscal em Regime de Retificação (1ª Alteração)",
            "status": "ALERTA",
            "gravidade": "BAIXA",
            "descricao": "Primeira retificação fiscal registrada para a OS. Alteração em processo de auditoria.",
            "recomendacao": "Conferir dados antes da transmissão final à contabilidade."
        })
    else:
        regras.append({
            "codigo": "REG_03_RETIFICACOES_SUCESSIVAS",
            "titulo": "Estabilidade de Emissão",
            "status": "APROVADO",
            "gravidade": "BAIXA",
            "descricao": "Nota emitida em fluxo de primeira passagem, sem retrabalho prévio.",
            "recomendacao": "Processo estável."
        })

    # -------------------------------------------------------------
    # REGRA 4: Alíquota de ISS e Retenções Tributárias
    # -------------------------------------------------------------
    aliq_iss = float(dados_nf.get("aliquota_iss") or 5.0)
    if aliq_iss < 2.0 or aliq_iss > 5.0:
        score -= 15
        regras.append({
            "codigo": "REG_04_ALIQUOTA_ISS",
            "titulo": "Alíquota de ISS Fora dos Parâmetros Legais",
            "status": "ALERTA",
            "gravidade": "MEDIA",
            "descricao": f"A alíquota de ISS informada ({aliq_iss}%) está fora dos limites constitucionais municipais (2% a 5%).",
            "recomendacao": "Ajustar alíquota conforme código tributário do município do tomador/prestador."
        })
    else:
        regras.append({
            "codigo": "REG_04_ALIQUOTA_ISS",
            "titulo": "Alíquota de ISS Conforme Legislação",
            "status": "APROVADO",
            "gravidade": "BAIXA",
            "descricao": f"Alíquota de ISS aplicada ({aliq_iss}%) dentro dos parâmetros normativos.",
            "recomendacao": "Parâmetro regular."
        })

    # -------------------------------------------------------------
    # REGRA 5: Ciclo de Envio ao Cliente & Lote Contábil
    # -------------------------------------------------------------
    email_status = str(dados_nf.get("email_status") or "").upper()
    enviado_contab = bool(dados_nf.get("enviado_contabilidade") or False)
    
    if email_status == "ENVIADO" and enviado_contab:
        regras.append({
            "codigo": "REG_05_CICLO_OPERACIONAL",
            "titulo": "Ciclo Operacional Fiscal Completo",
            "status": "APROVADO",
            "gravidade": "BAIXA",
            "descricao": "Nota Fiscal enviada com sucesso ao cliente e transmitida no lote contábil mensal.",
            "recomendacao": "Processo 100% concluído."
        })
    elif email_status == "ENVIADO":
        regras.append({
            "codigo": "REG_05_CICLO_OPERACIONAL",
            "titulo": "Pendente de Transmissão Contábil de Fechamento",
            "status": "ALERTA",
            "gravidade": "BAIXA",
            "descricao": "Nota Fiscal já enviada ao cliente, aguardando consolidação no lote de fechamento contábil mensal.",
            "recomendacao": "Incluir na remessa contábil ao final do período."
        })
    else:
        score -= 5
        regras.append({
            "codigo": "REG_05_CICLO_OPERACIONAL",
            "titulo": "Pendente de Envio ao Cliente",
            "status": "ALERTA",
            "gravidade": "BAIXA",
            "descricao": "Nota emitida, mas ainda não enviada por e-mail para o tomador.",
            "recomendacao": "Disparar e-mail com DANFE/XML para o cliente após conferência."
        })

    # Limita o score entre 0 e 100
    score = max(0, min(100, score))
    
    if score >= 90:
        status_geral = "CONFORME"
    elif score >= 70:
        status_geral = "ALERTA"
    else:
        status_geral = "NAO_CONFORME"
        
    return {
        "score": score,
        "status_geral": status_geral,
        "regras": regras,
        "data_avaliacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }


def registrar_evento_auditoria_fiscal(
    os_id: str,
    numero_nf: str,
    tipo_evento: str,
    usuario: str = "SETOR_FISCAL",
    ip_origem: Optional[str] = None,
    dados_anteriores: Optional[Dict[str, Any]] = None,
    dados_novos: Optional[Dict[str, Any]] = None,
    diferenca_valores: float = 0.0,
    status_conformidade: str = "CONFORME",
    score_conformidade: int = 100,
    motivo_observacao: str = "",
    detalhes_regras: Optional[List[Dict[str, Any]]] = None,
    db_path: str = DB_NAME
) -> int:
    """
    Grava um evento imutável na tabela de auditoria_fiscal_eventos com snapshot antes/depois.
    """
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    dados_ant_json = json.dumps(dados_anteriores or {}, ensure_ascii=False) if dados_anteriores else None
    dados_nov_json = json.dumps(dados_novos or {}, ensure_ascii=False) if dados_novos else None
    detalhes_json = json.dumps(detalhes_regras or [], ensure_ascii=False) if detalhes_regras else None

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO auditoria_fiscal_eventos (
                os_id, numero_nf, tipo_evento, usuario, ip_origem,
                dados_anteriores_json, dados_novos_json, diferenca_valores,
                status_conformidade, score_conformidade, motivo_observacao,
                detalhes_regras_json, data_hora, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            str(os_id),
            str(numero_nf).upper(),
            str(tipo_evento).upper(),
            str(usuario),
            str(ip_origem or ""),
            dados_ant_json,
            dados_nov_json,
            float(diferenca_valores),
            str(status_conformidade).upper(),
            int(score_conformidade),
            str(motivo_observacao),
            detalhes_json,
            agora_str
        ))
        novo_id = cur.lastrowid
        return novo_id


def obter_historico_eventos_fiscais(
    os_id: Optional[str] = None,
    tipo_evento: Optional[str] = None,
    status_conformidade: Optional[str] = None,
    limit: int = 50,
    db_path: str = DB_NAME
) -> List[Dict[str, Any]]:
    """
    Retorna os eventos da auditoria com filtros flexíveis.
    """
    query = "SELECT id, os_id, numero_nf, tipo_evento, usuario, ip_origem, diferenca_valores, status_conformidade, score_conformidade, motivo_observacao, data_hora, criado_em FROM auditoria_fiscal_eventos WHERE 1=1"
    params = []
    
    if os_id:
        query += " AND os_id = ?"
        params.append(str(os_id))
    if tipo_evento:
        query += " AND tipo_evento = ?"
        params.append(str(tipo_evento).upper())
    if status_conformidade:
        query += " AND status_conformidade = ?"
        params.append(str(status_conformidade).upper())
        
    query += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
    resultado = []
    for r in rows:
        resultado.append({
            "id": r[0],
            "os_id": r[1],
            "numero_nf": r[2],
            "tipo_evento": r[3],
            "usuario": r[4],
            "ip_origem": r[5],
            "diferenca_valores": float(r[6] or 0.0),
            "status_conformidade": r[7],
            "score_conformidade": int(r[8] or 100),
            "motivo_observacao": r[9],
            "data_hora": r[10],
            "criado_em": r[11]
        })
    return resultado


def obter_detalhe_evento(evento_id: int, db_path: str = DB_NAME) -> Optional[Dict[str, Any]]:
    """
    Retorna os detalhes completos de um evento, incluindo dados anteriores, dados novos e regras.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, os_id, numero_nf, tipo_evento, usuario, ip_origem,
                   dados_anteriores_json, dados_novos_json, diferenca_valores,
                   status_conformidade, score_conformidade, motivo_observacao,
                   detalhes_regras_json, data_hora, criado_em
            FROM auditoria_fiscal_eventos
            WHERE id = ?
        """, (int(evento_id),))
        r = cur.fetchone()
        
    if not r:
        return None
        
    dados_ant = json.loads(r[6]) if r[6] else {}
    dados_nov = json.loads(r[7]) if r[7] else {}
    regras = json.loads(r[12]) if r[12] else []
    
    # Calcular diffs principais
    diffs = {}
    chaves = set(list(dados_ant.keys()) + list(dados_nov.keys()))
    for k in chaves:
        val_ant = dados_ant.get(k)
        val_nov = dados_nov.get(k)
        if val_ant != val_nov:
            diffs[k] = {"antes": val_ant, "depois": val_nov}
            
    return {
        "id": r[0],
        "os_id": r[1],
        "numero_nf": r[2],
        "tipo_evento": r[3],
        "usuario": r[4],
        "ip_origem": r[5],
        "dados_anteriores": dados_ant,
        "dados_novos": dados_nov,
        "diffs": diffs,
        "diferenca_valores": float(r[8] or 0.0),
        "status_conformidade": r[9],
        "score_conformidade": int(r[10] or 100),
        "motivo_observacao": r[11],
        "regras": regras,
        "data_hora": r[13],
        "criado_em": r[14]
    }


def obter_resumo_dashboard_fiscal(db_path: str = DB_NAME) -> Dict[str, Any]:
    """
    Calcula métricas agregadas para o painel de monitoramento do Fiscal e benfeitorias de processos.
    """
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        # Total de eventos
        cur.execute("SELECT COUNT(*), AVG(score_conformidade) FROM auditoria_fiscal_eventos")
        total_eventos, avg_score = cur.fetchone()
        total_eventos = total_eventos or 0
        avg_score = round(float(avg_score or 100.0), 1)
        
        # Eventos por tipo
        cur.execute("SELECT tipo_evento, COUNT(*) FROM auditoria_fiscal_eventos GROUP BY tipo_evento")
        por_tipo = {r[0]: r[1] for r in cur.fetchall()}
        
        # Eventos por conformidade
        cur.execute("SELECT status_conformidade, COUNT(*) FROM auditoria_fiscal_eventos GROUP BY status_conformidade")
        por_conformidade = {r[0]: r[1] for r in cur.fetchall()}
        
        # Retificações com variação de valor
        cur.execute("""
            SELECT COUNT(*), SUM(ABS(diferenca_valores))
            FROM auditoria_fiscal_eventos
            WHERE tipo_evento = 'RETIFICACAO' AND ABS(diferenca_valores) > 0
        """)
        qtd_retif_val, soma_var_val = cur.fetchone()
        
        # Alertas de pendências de envio contábil no mês atual
        mes_atual = datetime.now().strftime("%Y-%m")
        cur.execute("""
            SELECT COUNT(*) FROM notas_fiscais
            WHERE (data_emissao LIKE ? OR criado_em LIKE ?)
              AND status_fiscal = 'EMITIDA'
              AND (enviado_contabilidade IS NULL OR enviado_contabilidade = 0)
        """, (f"%/{datetime.now().strftime('%m/%Y')}%", f"{mes_atual}%"))
        pendentes_contabilidade = cur.fetchone()[0] or 0

        # Alertas de notas sem envio ao cliente
        cur.execute("""
            SELECT COUNT(*) FROM notas_fiscais
            WHERE status_fiscal = 'EMITIDA'
              AND (email_status IS NULL OR email_status != 'ENVIADO')
        """)
        pendentes_envio_cliente = cur.fetchone()[0] or 0
        
    return {
        "score_medio_conformidade": avg_score,
        "total_eventos": total_eventos,
        "emissoes": por_tipo.get("EMISSAO", 0),
        "retificacoes": por_tipo.get("RETIFICACAO", 0),
        "cancelamentos": por_tipo.get("CANCELAMENTO", 0),
        "envios_cliente": por_tipo.get("ENVIO_CLIENTE", 0),
        "envios_contabilidade": por_tipo.get("ENVIO_CONTABILIDADE", 0),
        "liberacoes_quarentena": por_tipo.get("LIBERACAO_QUARENTENA", 0),
        "conformes": por_conformidade.get("CONFORME", 0),
        "alertas": por_conformidade.get("ALERTA", 0),
        "nao_conformes": por_conformidade.get("NAO_CONFORME", 0),
        "retificacoes_com_variacao_valor": qtd_retif_val or 0,
        "total_variacao_retificacoes": round(float(soma_var_val or 0.0), 2),
        "pendentes_contabilidade": pendentes_contabilidade,
        "pendentes_envio_cliente": pendentes_envio_cliente,
        "data_extracao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }
