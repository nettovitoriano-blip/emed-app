# -*- coding: utf-8 -*-
"""
Módulo PMP (Plano de Manutenção Preventiva) Anual EMED
Regra: 3 Preventivas Anuais por Contrato (Ciclo Quadrimestral: 1ª, 2ª e 3ª Etapa)
Equipamentos Pesados: Raio-X, Tomografia, Mamografia, Arco Cirúrgico e Densitometria Óssea.
"""

import sqlite3
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "emed.db")

def obter_conexao():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def obter_grade_pmp_anual(ano_ref=None):
    if not ano_ref:
        ano_ref = datetime.datetime.now().year
    
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Busca clientes e equipamentos com contrato ativo
    query_contratos = """
        SELECT 
            ce.cliente,
            ce.cidade,
            ce.equipamento,
            ce.tipo_contrato,
            COUNT(ce.id) as total_historico
        FROM clientes_equipamentos ce
        WHERE UPPER(COALESCE(ce.tipo_contrato, '')) LIKE '%CONTRATO%' 
           OR UPPER(COALESCE(ce.tipo_servico, '')) LIKE '%PREVENTIVA%'
        GROUP BY ce.cliente, ce.equipamento
        ORDER BY ce.cliente ASC, ce.equipamento ASC
    """
    cursor.execute(query_contratos)
    rows = cursor.fetchall()
    
    hoje = datetime.date.today()
    mes_atual = hoje.month
    
    # Determina o quadrimestre atual
    # Q1: Jan a Abr (Meses 1 a 4)
    # Q2: Mai a Ago (Meses 5 a 8)
    # Q3: Set a Dez (Meses 9 a 12)
    if mes_atual <= 4:
        quadrimestre_atual = 1
    elif mes_atual <= 8:
        quadrimestre_atual = 2
    else:
        quadrimestre_atual = 3
        
    resultado_grade = []
    
    for r in rows:
        cliente = r["cliente"]
        equipamento = r["equipamento"]
        cidade = r["cidade"] or "FORTALEZA"
        tipo_contrato = r["tipo_contrato"] or "CONTRATO MENSAL"
        
        # Buscar todas as preventivas executadas neste ano para este cliente/equipamento
        cursor.execute("""
            SELECT id, status, data_agendamento, etapa_preventiva, tecnico_responsavel, servico_executado, checkout_hora
            FROM clientes_equipamentos
            WHERE cliente = ? 
              AND equipamento = ?
              AND (UPPER(tipo_servico) LIKE '%PREVENTIVA%' OR etapa_preventiva IS NOT NULL)
              AND data_agendamento LIKE ?
            ORDER BY data_agendamento ASC
        """, (cliente, equipamento, f"{ano_ref}%"))
        
        oss_preventivas = cursor.fetchall()
        
        # Mapear as 3 etapas anuais
        # Etapa 1: Quadrimestre 1 (Jan - Abr)
        # Etapa 2: Quadrimestre 2 (Mai - Ago)
        # Etapa 3: Quadrimestre 3 (Set - Dez)
        etapas = {
            1: {"numero": 1, "nome": "1ª Etapa (Jan-Abr)", "concluida": False, "os_id": None, "data": None, "tecnico": None, "status": "PENDENTE"},
            2: {"numero": 2, "nome": "2ª Etapa (Mai-Ago)", "concluida": False, "os_id": None, "data": None, "tecnico": None, "status": "PENDENTE"},
            3: {"numero": 3, "nome": "3ª Etapa (Set-Dez)", "concluida": False, "os_id": None, "data": None, "tecnico": None, "status": "PENDENTE"}
        }
        
        total_concluidas = 0
        
        for os_prev in oss_preventivas:
            etapa_str = (os_prev["etapa_preventiva"] or "").upper()
            status_os = (os_prev["status"] or "").upper()
            dt_str = os_prev["data_agendamento"] or ""
            
            num_etapa = None
            if "1" in etapa_str or "PRIMEIRA" in etapa_str:
                num_etapa = 1
            elif "2" in etapa_str or "SEGUNDA" in etapa_str:
                num_etapa = 2
            elif "3" in etapa_str or "TERCEIRA" in etapa_str:
                num_etapa = 3
            else:
                # Dedução pelo mês se não houver etapa explícita
                try:
                    mes = int(dt_str.split("-")[1])
                    if mes <= 4: num_etapa = 1
                    elif mes <= 8: num_etapa = 2
                    else: num_etapa = 3
                except:
                    num_etapa = total_concluidas + 1 if total_concluidas < 3 else 3
            
            if num_etapa in etapas:
                concluida = ("CONCLU" in status_os or "LIBERAD" in status_os)
                etapas[num_etapa]["os_id"] = os_prev["id"]
                etapas[num_etapa]["data"] = dt_str
                etapas[num_etapa]["tecnico"] = os_prev["tecnico_responsavel"]
                etapas[num_etapa]["status"] = "CONCLUÍDO" if concluida else "AGENDADO"
                etapas[num_etapa]["concluida"] = concluida
                if concluida:
                    total_concluidas += 1
        
        # Avaliação de Semáforo de Conformidade do Contrato
        if total_concluidas >= 3:
            semaforo = "VERDE"
            status_anual = "100% CUMPRIDO (3/3)"
        elif total_concluidas == 2:
            semaforo = "AZUL" if quadrimestre_atual <= 2 else "AMARELO"
            status_anual = f"67% CUMPRIDO (2/3) - Resta 3ª Etapa"
        elif total_concluidas == 1:
            semaforo = "AZUL" if quadrimestre_atual == 1 else ("AMARELO" if quadrimestre_atual == 2 else "VERMELHO")
            status_anual = f"33% CUMPRIDO (1/3) - Restam 2 Etapas"
        else:
            semaforo = "AMARELO" if quadrimestre_atual == 1 else "VERMELHO"
            status_anual = f"0% CUMPRIDO (0/3) - Atenção Imediata"
            
        resultado_grade.append({
            "cliente": cliente,
            "cidade": cidade,
            "equipamento": equipamento,
            "tipo_contrato": tipo_contrato,
            "ano": ano_ref,
            "quadrimestre_atual": quadrimestre_atual,
            "total_concluidas": total_concluidas,
            "total_previstas": 3,
            "percentual": round((total_concluidas / 3) * 100),
            "status_anual": status_anual,
            "semaforo": semaforo,
            "etapas": [etapas[1], etapas[2], etapas[3]]
        })
        
    conn.close()
    
    # Estatísticas globais do parque
    total_equip = len(resultado_grade)
    total_em_dia = len([x for x in resultado_grade if x["semaforo"] in ["VERDE", "AZUL"]])
    total_alerta = len([x for x in resultado_grade if x["semaforo"] == "AMARELO"])
    total_atraso = len([x for x in resultado_grade if x["semaforo"] == "VERMELHO"])
    
    return {
        "ok": True,
        "ano": ano_ref,
        "quadrimestre_atual": quadrimestre_atual,
        "resumo": {
            "total_equipamentos_contratados": total_equip,
            "em_dia": total_em_dia,
            "em_alerta": total_alerta,
            "atrasados": total_atraso,
            "conformidade_geral_pct": round((total_em_dia / total_equip * 100) if total_equip > 0 else 100)
        },
        "grade": resultado_grade
    }
