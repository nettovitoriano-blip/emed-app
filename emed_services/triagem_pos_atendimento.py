# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Triagem Pós-Atendimento e Fila de Liberação de OS ao Cliente
Garante que toda OS concluída pelo técnico passe primeiro pela avaliação da Gestão/Financeiro
para verificar cobrança, pendências e proforma de preventiva antes do envio automático ao cliente.
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def obter_fila_triagem_pos_atendimento(db_name: str) -> List[Dict[str, Any]]:
    """Retorna todas as OSs concluídas pelo técnico que aguardam triagem da gestão."""
    fila = []
    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, cliente, equipamento, tipo_servico, tecnico_responsavel, 
                       checkin_hora, checkout_hora, tempo_atendimento, valor_os, 
                       condicao_pagamento, servico_executado, pendencias, status, 
                       contato_responsavel, email, whatsapp, triagem_concluida,
                       foto_evidencia, foto_depois, etapa_preventiva, data_agendamento
                FROM clientes_equipamentos
                WHERE (status LIKE '%TRIAGEM%' OR (status LIKE '%CONCLU%' AND (triagem_concluida = 0 OR triagem_concluida IS NULL)))
                ORDER BY id DESC
            """)
            for row in cur.fetchall():
                fila.append({
                    "id": row[0],
                    "cliente": row[1] or "CLIENTE NÃO INFORMADO",
                    "equipamento": row[2] or "EQUIPAMENTO",
                    "tipo_servico": row[3] or "CORRETIVA",
                    "tecnico": row[4] or "TÉCNICO EMED",
                    "checkin": row[5] or "N/D",
                    "checkout": row[6] or "N/D",
                    "duracao": row[7] or "N/D",
                    "valor_os": row[8] or 0.0,
                    "condicao_pagamento": row[9] or "CONTRATO",
                    "servico_executado": row[10] or "",
                    "pendencias": row[11] or "",
                    "status": row[12] or "AGUARDANDO TRIAGEM",
                    "telefone": row[13] or row[15] or "",
                    "email": row[14] or "",
                    "triagem_concluida": row[16] or 0,
                    "tem_fotos": bool(row[17] or row[18]),
                    "etapa_preventiva": row[19] or "",
                    "data": row[20] or ""
                })
    except Exception as e:
        print(f"Erro ao listar fila de triagem: {e}")
    return fila

def aprovar_triagem_os(db_name: str, os_id: int, dados: Dict[str, Any]) -> Dict[str, Any]:
    """Aprova a OS na triagem, define cobrança/pendência e prepara liberação ao cliente."""
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        responsavel = dados.get("responsavel", "GESTOR")
        cobranca_tipo = dados.get("cobranca_tipo", "INCLUSO_CONTRATO")
        cobranca_valor = float(dados.get("cobranca_valor", 0.0) or 0.0)
        pendencia_obs = dados.get("pendencia_obs", "").strip()
        gerar_proforma = 1 if dados.get("gerar_proforma") else 0
        
        status_final = "CONCLUÍDO / LIBERADO AO CLIENTE"
        if pendencia_obs and "PENDENTE" in pendencia_obs.upper():
            status_final = "CONCLUÍDO COM PENDÊNCIA (RETORNO AGENDADO)"

        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
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
            
            cur.execute("SELECT cliente, equipamento, contato_responsavel, whatsapp, email FROM clientes_equipamentos WHERE id = ? OR rowid = ?", (os_id, os_id))
            row_cli = cur.fetchone()
            conn.commit()

        cli_nome = row_cli[0] if row_cli else "Cliente"
        equip = row_cli[1] if row_cli else "Equipamento"
        tel = row_cli[2] or row_cli[3] or ""
        email = row_cli[4] or ""

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
            "email_cliente": email
        }
    except Exception as e:
        return {"ok": False, "msg": f"Erro na triagem da OS: {str(e)}"}
