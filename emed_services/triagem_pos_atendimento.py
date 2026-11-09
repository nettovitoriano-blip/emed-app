# -*- coding: utf-8 -*-
"""
Módulo de Triagem Pós-Atendimento e Liberação de OS ao Cliente
Regra de Negócio EMED:
1. Ao fechar em campo pelo técnico, a OS vai primeiro para o servidor para auditoria da Gestão/Financeiro.
2. O Gestor avalia se gera cobrança (Contrato, Boleto, PIX, Garantia) ou pendências de retorno.
3. Se houver peças aplicadas, executa BAIXA AUTOMÁTICA no Kardex de Estoque e sinaliza reposição se atingir estoque mínimo.
4. Após aprovação formal, o cliente recebe o Laudo Oficial via WhatsApp/E-mail.
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def obter_fila_triagem_pos_atendimento(db_name: str) -> List[Dict[str, Any]]:
    """Retorna todas as OSs que foram concluídas em campo mas ainda aguardam triagem/liberação."""
    fila = []
    try:
        with sqlite3.connect(db_name) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = """
                SELECT 
                    id, cliente, cidade, equipamento, tipo_servico, etapa_preventiva,
                    tecnico_responsavel, data_agendamento, checkin_hora, checkout_hora,
                    tempo_atendimento, servico_executado, pendencias, status,
                    triagem_concluida, triagem_data, valor_os, peca_baixada_ref
                FROM clientes_equipamentos
                WHERE (
                    UPPER(status) LIKE '%AGUARDANDO TRIAGEM%' 
                    OR UPPER(status) LIKE '%TRIAGEM%'
                    OR (triagem_concluida = 0 AND UPPER(status) LIKE '%CONCLU%')
                )
                ORDER BY id DESC
            """
            cur.execute(query)
            rows = cur.fetchall()
            for r in rows:
                fila.append({
                    "id": r["id"],
                    "cliente": r["cliente"] or "Hospital/Clínica",
                    "cidade": r["cidade"] or "",
                    "equipamento": r["equipamento"] or "Equipamento Médico",
                    "tipo_servico": r["tipo_servico"] or "CORRETIVA",
                    "etapa_preventiva": r["etapa_preventiva"] or "",
                    "tecnico": r["tecnico_responsavel"] or "Não Atribuído",
                    "data": r["data_agendamento"] or "",
                    "checkin": r["checkin_hora"] or "--:--",
                    "checkout": r["checkout_hora"] or "--:--",
                    "duracao": r["tempo_atendimento"] or "Em análise",
                    "servico_executado": r["servico_executado"] or "",
                    "pendencias": r["pendencias"] or "",
                    "valor_os": r["valor_os"] or 0.0,
                    "peca_aplicada": r["peca_baixada_ref"] or "",
                    "status": r["status"]
                })
    except Exception as e:
        print(f"Erro ao listar fila de triagem: {e}")
    return fila

def aprovar_triagem_os(db_name: str, os_id: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    """Aprova a OS na triagem, efetua baixa automática no Kardex de estoque e libera o laudo."""
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        data_hoje = datetime.datetime.now().strftime("%d/%m/%Y")
        hora_hoje = datetime.datetime.now().strftime("%H:%M")
        responsavel = dados.get("responsavel", "GESTOR")
        cobranca_tipo = dados.get("cobranca_tipo", "INCLUSO_CONTRATO")
        cobranca_valor = float(dados.get("cobranca_valor", 0.0) or 0.0)
        pendencia_obs = dados.get("pendencia_obs", "").strip()
        gerar_proforma = 1 if dados.get("gerar_proforma") else 0
        
        status_final = "CONCLUÍDO / LIBERADO AO CLIENTE"
        if pendencia_obs and "PENDENTE" in pendencia_obs.upper():
            status_final = "CONCLUÍDO COM PENDÊNCIA (RETORNO AGENDADO)"

        alerta_compras = None
        baixa_estoque_info = None

        with sqlite3.connect(db_name) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # 1. Atualizar status e campos de triagem da OS
            cur.execute("""
                UPDATE clientes_equipamentos
                SET status = ?,
                    triagem_concluida = 1,
                    triagem_data = ?,
                    triagem_responsavel = ?,
                    triagem_cobranca_tipo = ?,
                    triagem_cobranca_valor = ?,
                    triagem_pendencia_obs = ?,
                    triagem_proforma_gerada = ?,
                    triagem_laudo_enviado_cliente = 1,
                    valor_os = CASE WHEN ? > 0 THEN ? ELSE valor_os END
                WHERE id = ? OR rowid = ?
            """, (status_final, agora, responsavel, cobranca_tipo, cobranca_valor, 
                  pendencia_obs, gerar_proforma, cobranca_valor, cobranca_valor, os_id, os_id))
            
            # 2. Obter dados da OS e peça aplicada
            cur.execute("""
                SELECT cliente, equipamento, contato_responsavel, whatsapp, email, peca_baixada_ref 
                FROM clientes_equipamentos 
                WHERE id = ? OR rowid = ?
            """, (os_id, os_id))
            row_cli = cur.fetchone()
            
            cli_nome = row_cli["cliente"] if row_cli else "Cliente"
            equip = row_cli["equipamento"] if row_cli else "Equipamento"
            tel = (row_cli["contato_responsavel"] or row_cli["whatsapp"] or "") if row_cli else ""
            email = row_cli["email"] or "" if row_cli else ""
            peca_aplicada = (row_cli["peca_baixada_ref"] or "").strip() if row_cli else ""

            # 3. BAIXA AUTOMÁTICA NO ALMOXARIFADO & KARDEX
            if peca_aplicada and peca_aplicada.upper() not in ["NENHUMA", "NENHUMA PEÇA", "SEM PEÇA", ""]:
                # Localizar no estoque_pecas
                cur.execute("""
                    SELECT id, codigo, nome_peca, quantidade, estoque_minimo, preco_custo
                    FROM estoque_pecas
                    WHERE UPPER(nome_peca) = UPPER(?) 
                       OR UPPER(codigo) = UPPER(?)
                       OR UPPER(nome_peca) LIKE ?
                    LIMIT 1
                """, (peca_aplicada, peca_aplicada, f"%{peca_aplicada[:15]}%"))
                
                peca_row = cur.fetchone()
                if peca_row:
                    p_id = peca_row["id"]
                    p_cod = peca_row["codigo"] or "PEC-AUT"
                    p_nome = peca_row["nome_peca"]
                    saldo_atual = int(peca_row["quantidade"] or 0)
                    est_min = int(peca_row["estoque_minimo"] or 1)
                    custo_un = float(peca_row["preco_custo"] or 0.0)
                    
                    novo_saldo = max(0, saldo_atual - 1)
                    
                    # Atualiza saldo em estoque_pecas
                    cur.execute("UPDATE estoque_pecas SET quantidade = ? WHERE id = ?", (novo_saldo, p_id))
                    
                    # Insere movimentação formal no Kardex (movimentacoes_estoque)
                    cur.execute("""
                        INSERT INTO movimentacoes_estoque (
                            codigo_item, descricao, tipo_mov, qtd_saida, saldo, 
                            custo_medio, documento, data_mov, hora_mov, observacao
                        ) VALUES (?, ?, 'SAIDA_OS', 1, ?, ?, ?, ?, ?, ?)
                    """, (
                        p_cod, p_nome, novo_saldo, custo_un, f"OS #{os_id}",
                        data_hoje, hora_hoje, f"Baixa automática na Triagem - Cliente: {cli_nome} ({equip})"
                    ))
                    
                    baixa_estoque_info = {
                        "peca": p_nome,
                        "codigo": p_cod,
                        "saldo_anterior": saldo_atual,
                        "novo_saldo": novo_saldo
                    }
                    
                    # Se atingir ou passar do estoque mínimo, dispara alerta de reposição
                    if novo_saldo <= est_min:
                        alerta_compras = (
                            f"🚨 ALERTA DE COMPRAS: A peça '{p_nome}' atingiu o estoque mínimo "
                            f"(Saldo: {novo_saldo} un | Mínimo: {est_min} un). Solicitar cotação de reposição!"
                        )

            conn.commit()

        # Prepara texto formatado para envio no WhatsApp do cliente
        msg_cliente = (
            f"🏥 *EMED ELETROMEDICINA — LAUDO TÉCNICO OFICIAL*\n\n"
            f"Prezado(a) *{cli_nome}*,\n\n"
            f"Informamos que a Ordem de Serviço *OS #{os_id}*, referente ao equipamento *{equip}*, "
            f"foi devidamente concluída e homologada pela nossa Engenharia Clínica em {agora}.\n\n"
            f"📋 *Resumo da Intervenção:*\n"
            f"- Status Operacional: *Equipamento Liberado para Uso Normal*\n"
            f"- Faturamento / Contrato: *{cobranca_tipo}*" + (f" (R$ {cobranca_valor:,.2f})" if cobranca_valor > 0 else "") + "\n"
        )
        if pendencia_obs:
            msg_cliente += f"- Observação Técnica: {pendencia_obs}\n"

        msg_cliente += (
            f"\n🔗 Acesse o Laudo Completo Timbrado em PDF:\n"
            f"https://emed-app-6ofv.onrender.com/api/imprimir/{os_id}\n\n"
            f"Agradecemos a confiança e seguimos à disposição 24 horas!\n"
            f"📞 Plantão Técnico EMED: (85) 99915-0273"
        )

        return {
            "ok": True,
            "msg": f"OS #{os_id} avaliada e liberada com sucesso!",
            "os_id": os_id,
            "status": status_final,
            "mensagem_cliente": msg_cliente,
            "telefone_cliente": tel,
            "email_cliente": email,
            "baixa_estoque": baixa_estoque_info,
            "alerta_compras": alerta_compras
        }
    except Exception as e:
        return {"ok": False, "msg": f"Erro na triagem da OS: {str(e)}"}
