# -*- coding: utf-8 -*-
"""
Módulo de Telemetria de Aterramento & Detecção Precoce de Arco (Arc Guard & TLF).
EMED Eletromedicina - Proteção Preditiva de Ampolas de Tomografia, Raio-X e Mamografia.

Objetivos:
1. Monitorar impedância da malha de aterramento (Normas NBR 5410 e NBR IEC 60601-1: <= 1.0 Ohm).
2. Detectar transientes rápidos e microarcos (Arcing) no tanque de alta tensão (HV Tank) e tubo.
3. Acionar preventivas com unidade TLF (Tratamento Dielétrico, Desgaseificação e Troca de Óleo)
   semanas antes de queimar ampolas de R$ 80.000 a R$ 300.000.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(_BASE_DIR, "emed.db")


def get_db_connection(db_path: Optional[str] = None):
    conn = sqlite3.connect(db_path or DB_NAME, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_telemetria_db(db_path: Optional[str] = None):
    """Cria tabelas de telemetria preditiva caso ainda não existam."""
    with get_db_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_aterramento_arcos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipamento_id INTEGER,
                equipamento_nome TEXT NOT NULL,
                hospital_cliente TEXT NOT NULL,
                sala_setor TEXT,
                resistencia_terra_ohms REAL DEFAULT 0.0,
                pico_transiente_arco_v REAL DEFAULT 0.0,
                microarcos_por_hora INTEGER DEFAULT 0,
                rigidez_dieletrica_kv REAL DEFAULT 0.0,
                temperatura_oleo_c REAL DEFAULT 0.0,
                status_risco TEXT DEFAULT 'NORMAL', -- 'NORMAL', 'ALERTA', 'CRITICO'
                mensagem_alerta TEXT,
                recomendacao_tlf TEXT,
                data_medicao TEXT,
                criado_em TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def avaliar_risco_eletrico(
    equipamento_nome: str,
    hospital_cliente: str,
    resistencia_terra_ohms: float,
    microarcos_por_hora: int,
    rigidez_dieletrica_kv: float = 35.0,
    pico_transiente_arco_v: float = 0.0,
    temperatura_oleo_c: float = 40.0,
    equipamento_id: Optional[int] = None,
    sala_setor: str = "Sala de Exames"
) -> Dict[str, Any]:
    """
    Avalia os parâmetros físicos do equipamento e gera alertas preditivos inteligentes.
    """
    status_risco = "NORMAL"
    alertas = []
    recomendacoes = []

    # 1. Checagem de Impedância da Malha de Aterramento (NBR 5410 <= 1.0 Ohm)
    if resistencia_terra_ohms > 2.0:
        status_risco = "CRITICO"
        alertas.append(f"Resistência de terra excessiva ({resistencia_terra_ohms:.2f} Ω). Risco grave a operadores e fuga de ruído.")
    elif resistencia_terra_ohms > 1.0:
        if status_risco != "CRITICO":
            status_risco = "ALERTA"
        alertas.append(f"Aterramento limítrofe ({resistencia_terra_ohms:.2f} Ω, teto seguro: 1.0 Ω).")

    # 2. Detecção de Microarcos no Tubo / Tanque HV
    if microarcos_por_hora >= 5:
        status_risco = "CRITICO"
        alertas.append(f"Frequência severa de microarcos ({microarcos_por_hora} arcos/hora). Degradação acelerada do vácuo/óleo.")
    elif microarcos_por_hora >= 2:
        if status_risco != "CRITICO":
            status_risco = "ALERTA"
        alertas.append(f"Detecção de {microarcos_por_hora} microarcos nas últimas horas.")

    # 3. Rigidez Dielétrica do Óleo Isolante (Novo > 30 kV; Alerta < 25 kV; Crítico < 20 kV)
    if rigidez_dieletrica_kv > 0:
        if rigidez_dieletrica_kv < 20.0:
            status_risco = "CRITICO"
            alertas.append(f"Rigidez dielétrica crítica do óleo ({rigidez_dieletrica_kv:.1f} kV). Risco iminente de perfuração da ampola.")
        elif rigidez_dieletrica_kv < 25.0:
            if status_risco != "CRITICO":
                status_risco = "ALERTA"
            alertas.append(f"Rigidez dielétrica em declínio ({rigidez_dieletrica_kv:.1f} kV). Óleo com umidade/contaminação.")

    # Montar mensagem oficial EMED
    if status_risco == "CRITICO":
        msg_alerta = f"⚠️ ALERTA CRÍTICO: Detectado padrão de arco elétrico no {equipamento_nome} ({hospital_cliente}). Degradação iminente de isolamento. Agendar inspeção preventiva e mitigar custos."
        recomendacao = "Mobilizar equipe técnica com unidade TLF para revitalização de tubo, ensaio de rigidez dielétrica e troca/desgaseificação de óleo isolante."
    elif status_risco == "ALERTA":
        msg_alerta = f"⚡ ALERTA OPERACIONAL: Variação de aterramento/transientes no {equipamento_nome} ({hospital_cliente}). Acompanhar telemetria."
        recomendacao = "Revisar barramento equipotencial da sala e planejar coleta de amostra de óleo dielétrico para bancada TLF."
    else:
        msg_alerta = f"✅ Operação Estável: {equipamento_nome} com malha de aterramento e isolamento dentro das normas técnicas."
        recomendacao = "Manter rotina preventiva semestral."

    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Persistir no banco de dados
    try:
        init_telemetria_db()
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO telemetria_aterramento_arcos (
                    equipamento_id, equipamento_nome, hospital_cliente, sala_setor,
                    resistencia_terra_ohms, pico_transiente_arco_v, microarcos_por_hora,
                    rigidez_dieletrica_kv, temperatura_oleo_c, status_risco,
                    mensagem_alerta, recomendacao_tlf, data_medicao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                equipamento_id, equipamento_nome, hospital_cliente, sala_setor,
                float(resistencia_terra_ohms), float(pico_transiente_arco_v),
                int(microarcos_por_hora), float(rigidez_dieletrica_kv),
                float(temperatura_oleo_c), status_risco, msg_alerta, recomendacao, agora_iso
            ))
            novo_id = cur.lastrowid
            conn.commit()
    except Exception as e:
        novo_id = None

    return {
        "ok": True,
        "id": novo_id,
        "equipamento_nome": equipamento_nome,
        "hospital_cliente": hospital_cliente,
        "status_risco": status_risco,
        "mensagem_alerta": msg_alerta,
        "recomendacao_tlf": recomendacao,
        "alertas_detalhados": alertas,
        "data_medicao": agora_iso
    }


def obter_painel_telemetria(limite: int = 20, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retorna o resumo para o dashboard da EMED."""
    init_telemetria_db(db_path)
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        registros = cur.execute("""
            SELECT * FROM telemetria_aterramento_arcos
            ORDER BY id DESC LIMIT ?
        """, (limite,)).fetchall()

        total = cur.execute("SELECT COUNT(*) FROM telemetria_aterramento_arcos").fetchone()[0]
        criticos = cur.execute("SELECT COUNT(*) FROM telemetria_aterramento_arcos WHERE status_risco = 'CRITICO'").fetchone()[0]
        alertas = cur.execute("SELECT COUNT(*) FROM telemetria_aterramento_arcos WHERE status_risco = 'ALERTA'").fetchone()[0]
        normais = cur.execute("SELECT COUNT(*) FROM telemetria_aterramento_arcos WHERE status_risco = 'NORMAL'").fetchone()[0]

    return {
        "total_medicoes": total,
        "criticos": criticos,
        "alertas": alertas,
        "normais": normais,
        "historico": [dict(r) for r in registros]
    }
