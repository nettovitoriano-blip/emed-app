# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Painel do Almoxarifado: Cautela de Ferramentas & Calibração RBC
Controle operacional para o almoxarife gerenciar a saída e devolução de instrumentos
de precisão (multímetros, osciloscópios, phantoms) e monitorar a validade da calibração RBC.
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def obter_painel_cautela_ferramentas(db_name: str) -> Dict[str, Any]:
    """Retorna inventário completo de ferramentas, status de cautela e alertas RBC."""
    ferramentas = []
    hoje = datetime.date.today()
    totais = {"total": 0, "disponiveis": 0, "em_uso": 0, "calibracao_vencendo": 0, "vencidas": 0}

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, codigo_ferramenta, nome_ferramenta, status, 
                       tecnico_responsavel, destino_cliente, os_id, 
                       data_saida, data_retorno_previsto, data_devolucao, 
                       numero_serie, localizacao, data_validade_calibracao, 
                       certificado_calibracao, observacao
                FROM ferramentas_cautela
                ORDER BY status ASC, id ASC
            """)
            for row in cur.fetchall():
                f_id, cod, nome, st, tec, cli, os_id, dt_saida, dt_ret_prev, dt_dev, serie, loc, val_calib, cert, obs = row
                st_norm = (st or "DISPONIVEL").upper()
                
                # Análise da Calibração RBC
                status_rbc = "EM_DIA"
                cor_rbc = "#16a34a"
                lbl_rbc = "🟢 RBC Válida"
                dias_para_vencer = 999

                if val_calib:
                    try:
                        if "/" in val_calib:
                            d, m, y = val_calib.split("/")[:3]
                            dt_calib = datetime.date(int(y), int(m), int(d))
                        else:
                            dt_calib = datetime.datetime.strptime(val_calib[:10], "%Y-%m-%d").date()
                        
                        dias_para_vencer = (dt_calib - hoje).days
                        if dias_para_vencer < 0:
                            status_rbc = "VENCIDA"
                            cor_rbc = "#dc2626"
                            lbl_rbc = f"🔴 Vencida ({abs(dias_para_vencer)}d atrás)"
                            totais["vencidas"] += 1
                        elif dias_para_vencer <= 30:
                            status_rbc = "VENCENDO"
                            cor_rbc = "#d97706"
                            lbl_rbc = f"🟡 Vence em {dias_para_vencer}d"
                            totais["calibracao_vencendo"] += 1
                        else:
                            lbl_rbc = f"🟢 Válida ({val_calib})"
                    except Exception:
                        pass

                totais["total"] += 1
                if st_norm in ["DISPONIVEL", "DISPONÍVEL"]:
                    totais["disponiveis"] += 1
                else:
                    totais["em_uso"] += 1

                ferramentas.append({
                    "id": f_id,
                    "codigo": cod,
                    "nome": nome,
                    "status": st_norm,
                    "tecnico": tec or "",
                    "cliente": cli or "",
                    "os_id": os_id or "",
                    "data_saida": dt_saida or "",
                    "data_devolucao": dt_dev or "",
                    "numero_serie": serie or "S/N",
                    "localizacao": loc or "ALMOXARIFADO CENTRAL",
                    "validade_calibracao": val_calib or "N/D",
                    "dias_para_vencer": dias_para_vencer,
                    "certificado_rbc": cert or "RBC HOMOLOGADO",
                    "status_rbc": status_rbc,
                    "cor_rbc": cor_rbc,
                    "lbl_rbc": lbl_rbc,
                    "observacao": obs or ""
                })
    except Exception as e:
        print(f"Erro ao listar ferramentas de cautela: {e}")

    return {"ok": True, "totais": totais, "ferramentas": ferramentas}

def registrar_movimento_cautela(db_name: str, dados: Dict[str, Any]) -> Dict[str, Any]:
    """Registra retirada ou devolução de ferramenta ao almoxarifado."""
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        f_id = int(dados.get("ferramenta_id", 0))
        acao = dados.get("acao", "SAIDA").upper() # SAIDA ou DEVOLUCAO
        tecnico = dados.get("tecnico", "").strip().upper()
        cliente = dados.get("cliente", "").strip().upper()
        os_id = str(dados.get("os_id", "")).strip()
        obs = dados.get("observacao", "").strip()
        operador = dados.get("operador", "ALMOXARIFE").strip().upper()

        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT codigo_ferramenta, nome_ferramenta FROM ferramentas_cautela WHERE id = ?", (f_id,))
            row_f = cur.fetchone()
            if not row_f:
                return {"ok": False, "msg": f"Ferramenta ID #{f_id} não localizada."}
            
            cod_ferr, nome_ferr = row_f

            if acao == "SAIDA":
                cur.execute("""
                    UPDATE ferramentas_cautela
                    SET status = 'EM_USO',
                        tecnico_responsavel = ?,
                        destino_cliente = ?,
                        os_id = ?,
                        data_saida = ?,
                        data_devolucao = '',
                        observacao = ?
                    WHERE id = ?
                """, (tecnico, cliente, os_id, agora, obs, f_id))
            else: # DEVOLUCAO
                cur.execute("""
                    UPDATE ferramentas_cautela
                    SET status = 'DISPONIVEL',
                        tecnico_responsavel = '',
                        destino_cliente = '',
                        os_id = '',
                        data_devolucao = ?,
                        observacao = ?
                    WHERE id = ?
                """, (agora, obs or "Devolvido ao almoxarifado central", f_id))

            # Registra no histórico de auditoria
            cur.execute("""
                INSERT INTO historico_cautela_ferramentas
                (codigo_ferramenta, nome_ferramenta, tipo_acao, tecnico, destino_cliente, os_id, operador, data_hora, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cod_ferr, nome_ferr, acao, tecnico, cliente, os_id, operador, agora, obs))
            conn.commit()

        return {
            "ok": True,
            "msg": f"Movimentação de {acao} da ferramenta {cod_ferr} registrada com sucesso!",
            "data_hora": agora
        }
    except Exception as e:
        return {"ok": False, "msg": f"Erro na cautela: {str(e)}"}
