# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Gestão Semanal de Checklists de Frotas
Permite ao Gestor de Veículos inspecionar semanalmente (ou em intervalo configurável)
cada carro da frota (óleo, pneus, freios, estepe, arrefecimento, hodômetro).
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def obter_status_checklists_veiculos(db_name: str) -> List[Dict[str, Any]]:
    """Retorna todos os veículos com o status e tempo desde a última inspeção semanal."""
    veiculos_status = []
    hoje = datetime.date.today()
    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, modelo, placa, km_atual, condutor_atual, 
                       data_ultimo_checklist, dias_intervalo_checklist, cor, combustivel
                FROM veiculos
                ORDER BY id ASC
            """)
            for row in cur.fetchall():
                v_id, modelo, placa, km, condutor, dt_check, intervalo, cor, comb = row
                intervalo = intervalo or 7
                dias_passados = 999
                data_formatada = "NUNCA REALIZADO"
                
                if dt_check:
                    try:
                        # Tenta parsear no formato YYYY-MM-DD ou DD/MM/YYYY
                        if "-" in dt_check:
                            dt_obj = datetime.datetime.strptime(dt_check[:10], "%Y-%m-%d").date()
                        else:
                            dt_obj = datetime.datetime.strptime(dt_check[:10], "%d/%m/%Y").date()
                        dias_passados = (hoje - dt_obj).days
                        data_formatada = dt_obj.strftime("%d/%m/%Y")
                    except Exception:
                        pass

                # Status Semáforo
                if dias_passados <= (intervalo - 2):
                    status_semaforo = "EM_DIA"
                    cor_status = "#16a34a" # Verde
                    lbl_status = f"🟢 Em Dia ({dias_passados}d atrás)"
                elif dias_passados <= intervalo:
                    status_semaforo = "ATENCAO"
                    cor_status = "#d97706" # Amarelo
                    lbl_status = f"🟡 Vencendo ({dias_passados}d atrás)"
                else:
                    status_semaforo = "ATRASADO"
                    cor_status = "#dc2626" # Vermelho
                    lbl_status = f"🔴 Atrasado ({dias_passados}d sem checklist)" if dias_passados < 900 else "🔴 Checklist Pendente"

                # Busca últimas 3 inspeções
                cur.execute("""
                    SELECT data_hora, tecnico, km_atual, status_geral, nivel_oleo, pneus, freios, observacoes
                    FROM frota_checklists
                    WHERE veiculo_id = ? OR placa = ?
                    ORDER BY id DESC LIMIT 3
                """, (v_id, placa))
                historico = []
                for h in cur.fetchall():
                    historico.append({
                        "data_hora": h[0],
                        "gestor": h[1],
                        "km": h[2],
                        "status": h[3],
                        "oleo": h[4],
                        "pneus": h[5],
                        "freios": h[6],
                        "obs": h[7] or ""
                    })

                veiculos_status.append({
                    "id": v_id,
                    "modelo": modelo or "Fiat Argo",
                    "placa": placa or "EMD-2026",
                    "km_atual": km or 0,
                    "condutor": condutor or "Equipe EMED",
                    "ultimo_checklist": data_formatada,
                    "dias_passados": dias_passados,
                    "intervalo_dias": intervalo,
                    "status_semaforo": status_semaforo,
                    "cor_status": cor_status,
                    "lbl_status": lbl_status,
                    "cor": cor or "Branco",
                    "combustivel": comb or "Flex",
                    "historico": historico
                })
    except Exception as e:
        print(f"Erro ao listar status da frota: {e}")
    return veiculos_status

def salvar_checklist_veicular_gestor(db_name: str, dados: Dict[str, Any]) -> Dict[str, Any]:
    """Salva a inspeção semanal do gestor de frota e atualiza o hodômetro do veículo."""
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        hoje_iso = datetime.date.today().isoformat()
        
        v_id = int(dados.get("veiculo_id", 1))
        placa = dados.get("placa", "EMD-2026").strip().upper()
        gestor = dados.get("gestor", "GESTOR DE FROTAS").strip().upper()
        km_atual = int(dados.get("km_atual", 0) or 0)
        oleo = dados.get("nivel_oleo", "NORMAL").upper()
        freios = dados.get("freios", "NORMAL").upper()
        pneus = dados.get("pneus", "NORMAL (CALIBRADOS)").upper()
        luzes = dados.get("luzes", "FUNCIONANDO").upper()
        arrefecimento = dados.get("arrefecimento", "NORMAL").upper()
        ar_cond = dados.get("ar_condicionado", "FUNCIONANDO").upper()
        avarias = dados.get("avarias_sinistro", "NENHUMA").upper()
        obs = dados.get("observacoes", "").strip()
        status_geral = dados.get("status_geral", "APROVADO").upper()

        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO frota_checklists
                (veiculo_id, placa, data_hora, tecnico, km_atual, nivel_oleo, 
                 freios, pneus, luzes, arrefecimento, ar_condicionado, 
                 avarias_sinistro, observacoes, status_geral, data_criacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (v_id, placa, agora, gestor, km_atual, oleo, 
                  freios, pneus, luzes, arrefecimento, ar_cond, 
                  avarias, obs, status_geral, agora))
            
            # Atualiza hodômetro e data do último checklist no veículo
            cur.execute("""
                UPDATE veiculos
                SET data_ultimo_checklist = ?,
                    km_atual = CASE WHEN ? > 0 THEN ? ELSE km_atual END
                WHERE id = ? OR placa = ?
            """, (hoje_iso, km_atual, km_atual, v_id, placa))
            conn.commit()

        return {
            "ok": True, 
            "msg": f"Checklist semanal do veículo {placa} registrado com sucesso!",
            "data_hora": agora
        }
    except Exception as e:
        return {"ok": False, "msg": f"Erro ao salvar checklist veicular: {str(e)}"}
