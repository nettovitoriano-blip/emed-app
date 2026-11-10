# -*- coding: utf-8 -*-
"""
Módulo PMP (Plano de Manutenção Preventiva) Anual EMED com Agrupamento Logístico por Polos Regionais
Regra: 3 Preventivas Anuais por Contrato (Ciclo Quadrimestral: 1ª, 2ª e 3ª Etapa)
Inteligência Logística: Agrupamento automático de preventivas do mesmo polo/região no mesmo período de viagem.
"""

import sqlite3
import datetime
import os
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "emed.db")

# Mapeamento de Polos Logísticos Estratégicos
POLOS_REGIONAIS = {
    "POLO_ARARIPE_PETROLINA": {
        "nome": "Polo Sertão do Araripe & Vale do São Francisco",
        "cidades": ["ARARIPINA", "PETROLINA", "OURICURI", "TRINDADE", "JUAZEIRO-BA", "BODOCO"],
        "distancia_base_km": 680,
        "custo_viagem_base": 1950.00
    },
    "POLO_CARIRI": {
        "nome": "Polo Cariri (Região Metropolitana do Cariri)",
        "cidades": ["JUAZEIRO DO NORTE", "CRATO", "BARBALHA", "BREJO SANTO", "MISSAO VELHA", "JARDIM"],
        "distancia_base_km": 520,
        "custo_viagem_base": 1550.00
    },
    "POLO_SERTAO_CENTRAL_INHAMUNS": {
        "nome": "Polo Sertão Central & Inhamuns",
        "cidades": ["TAUA", "QUIXADA", "QUIXERAMOBIM", "CRATEUS", "IGUATU"],
        "distancia_base_km": 360,
        "custo_viagem_base": 1150.00
    },
    "POLO_NORTE_IBIAPABA": {
        "nome": "Polo Norte & Serra da Ibiapaba",
        "cidades": ["SOBRAL", "TIANGUA", "ITAPIPOCA", "CAMOCIM", "URUBURETAMA"],
        "distancia_base_km": 240,
        "custo_viagem_base": 850.00
    },
    "POLO_GRANDE_FORTALEZA": {
        "nome": "Polo Metropolitano de Fortaleza",
        "cidades": ["FORTALEZA", "CAUCAIA", "MARACANAU", "EUSEBIO", "AQUIRAZ", "HORIZONTE", "PACAJUS"],
        "distancia_base_km": 40,
        "custo_viagem_base": 180.00
    }
}

def identificar_polo(cidade: str) -> str:
    cid_upper = (cidade or "").upper().strip()
    for polo_id, dados in POLOS_REGIONAIS.items():
        for c in dados["cidades"]:
            if c in cid_upper or cid_upper in c:
                return polo_id
    return "OUTRAS_REGIOES"

def obter_conexao():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def obter_grade_pmp_anual(ano_ref=None):
    if not ano_ref:
        ano_ref = datetime.datetime.now().year
    
    conn = obter_conexao()
    cursor = conn.cursor()
    
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
    
    if mes_atual <= 4:
        quadrimestre_atual = 1
    elif mes_atual <= 8:
        quadrimestre_atual = 2
    else:
        quadrimestre_atual = 3
        
    resultado_grade = []
    polos_agrupados = {}
    
    for r in rows:
        cliente = r["cliente"]
        equipamento = r["equipamento"]
        cidade = r["cidade"] or "FORTALEZA"
        tipo_contrato = r["tipo_contrato"] or "CONTRATO MENSAL"
        polo_id = identificar_polo(cidade)
        
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
            
        item_pmp = {
            "cliente": cliente,
            "cidade": cidade,
            "polo_id": polo_id,
            "polo_nome": POLOS_REGIONAIS.get(polo_id, {}).get("nome", "Região Diversa"),
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
        }
        
        resultado_grade.append(item_pmp)
        
        # Agrupamento para análise logística de polo
        if polo_id not in polos_agrupados:
            polos_agrupados[polo_id] = {
                "polo_id": polo_id,
                "polo_nome": POLOS_REGIONAIS.get(polo_id, {}).get("nome", "Região Diversa"),
                "equipamentos": [],
                "datas_agendadas": set()
            }
        polos_agrupados[polo_id]["equipamentos"].append(item_pmp)
        for et in [etapas[1], etapas[2], etapas[3]]:
            if et["data"]:
                polos_agrupados[polo_id]["datas_agendadas"].add(et["data"])
        
    conn.close()
    
    # Gerar Oportunidades de Roteiro Unificado por Polo
    oportunidades_roteiro = []
    for p_id, p_info in polos_agrupados.items():
        if p_id == "POLO_GRANDE_FORTALEZA" or p_id == "OUTRAS_REGIOES":
            continue
        
        qtd_equip = len(p_info["equipamentos"])
        if qtd_equip >= 2:
            datas = sorted(list(p_info["datas_agendadas"]))
            custo_base = POLOS_REGIONAIS.get(p_id, {}).get("custo_viagem_base", 1500.0)
            dist_base = POLOS_REGIONAIS.get(p_id, {}).get("distancia_base_km", 500)
            
            # Se houver data agendada, toma como referência
            data_sugerida = datas[0] if datas else f"{ano_ref}-11-16 (Semana Recomendada)"
            
            economia_estimada = (qtd_equip - 1) * custo_base * 0.65
            km_evitados = (qtd_equip - 1) * dist_base * 2
            
            oportunidades_roteiro.append({
                "polo_id": p_id,
                "polo_nome": p_info["polo_nome"],
                "total_equipamentos": qtd_equip,
                "clientes": list(set([e["cliente"] for e in p_info["equipamentos"]])),
                "data_sugerida_roteiro": data_sugerida,
                "economia_estimada_rs": round(economia_estimada, 2),
                "km_evitados": km_evitados,
                "recomendacao": (
                    f"🎯 Agrupar as preventivas deste polo na mesma semana ({data_sugerida}). "
                    f"Elimina viagens duplicadas partindo de Fortaleza com economia prevista de R$ {economia_estimada:,.2f} "
                    f"e ~{km_evitados} km de rodagem evitados!"
                )
            })
            
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
            "conformidade_geral_pct": round((total_em_dia / total_equip * 100) if total_equip > 0 else 100),
            "total_polos_estrategicos": len(oportunidades_roteiro)
        },
        "oportunidades_roteiro": oportunidades_roteiro,
        "grade": resultado_grade
    }
