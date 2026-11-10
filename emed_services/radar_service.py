# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Serviço de Radares e Alertas de Velocidade Offline
Calcula aproximação de radares fixos/semáforos utilizando Haversine de alta performance
e emite alertas visuais/sonoros para a cabine do técnico.
"""

import math
import sqlite3
from typing import List, Dict, Any, Optional

def _haversine_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0  # Raio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

RADARES_CORREDOR_CE_RN = [
    # Natal / RN e Região Metropolitana (Ladeira do Sol, Via Costeira, BR-101, BR-304)
    ("RN", "Natal", "Av. Pres. Getúlio Vargas (Ladeira do Sol)", -5.783611, -35.192778, 50, "FIXO", "AMBOS"),
    ("RN", "Natal", "Av. Sen. Salgado Filho próx. Midway", -5.811822, -35.207311, 60, "FIXO", "AMBOS"),
    ("RN", "Natal", "Av. Eng. Roberto Freire (Ponta Negra)", -5.872410, -35.183420, 60, "FIXO", "AMBOS"),
    ("RN", "Natal", "Via Costeira km 4", -5.834190, -35.184310, 70, "FIXO", "AMBOS"),
    ("RN", "Parnamirim", "BR-101 Sul km 105", -5.918450, -35.263120, 80, "FIXO", "SUL"),
    ("RN", "Macaíba", "BR-304 km 298", -5.862410, -35.341200, 60, "LOMBADA_ELETRONICA", "AMBOS"),
    ("RN", "Lajes", "BR-304 km 205", -5.701230, -36.241200, 80, "FIXO", "AMBOS"),
    ("RN", "Mossoró", "BR-304 km 45 (Contorno)", -5.191200, -37.341200, 60, "FIXO", "AMBOS"),
    
    # Ceará - BR-304 / BR-116 / Aracati / Russas / Eusébio / Fortaleza
    ("CE", "Aracati", "BR-304 km 68", -4.561230, -37.771200, 60, "LOMBADA_ELETRONICA", "AMBOS"),
    ("CE", "Russas", "BR-116 km 162", -4.931200, -37.971200, 60, "FIXO", "AMBOS"),
    ("CE", "Pacajus", "BR-116 km 50", -4.171200, -38.461200, 60, "FIXO", "AMBOS"),
    ("CE", "Eusébio", "CE-040 km 8 (Frente Shopping Eusébio)", -3.882140, -38.451200, 60, "FIXO", "AMBOS"),
    ("CE", "Eusébio", "Av. Washington Soares / CE-040 km 4", -3.854120, -38.461200, 60, "FIXO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Aguanambi km 2", -3.754120, -38.528410, 60, "FIXO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Bezerra de Menezes próx. North Shopping", -3.734120, -38.561200, 50, "SEMAFORO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Eng. Santana Júnior / Iguatemi", -3.751200, -38.484120, 60, "FIXO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Santos Dumont próx. Hospital São Carlos", -3.738120, -38.487120, 50, "SEMAFORO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Raul Barbosa próx. Aeroporto", -3.771200, -38.511200, 60, "FIXO", "AMBOS"),
    ("CE", "Fortaleza", "Av. Alberto Craveiro (Castelão)", -3.801200, -38.521200, 60, "FIXO", "AMBOS")
]

def inicializar_banco_radares(db_name: str):
    """Garante a tabela frota_banco_radares e semeia a malha CE-RN se vazia."""
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS frota_banco_radares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uf TEXT,
                municipio TEXT,
                rodovia_via TEXT,
                latitude REAL,
                longitude REAL,
                velocidade_kmh INTEGER,
                tipo TEXT,
                sentido TEXT
            )
        """)
        cur.execute("SELECT COUNT(*) FROM frota_banco_radares")
        qtd = cur.fetchone()[0]
        if qtd == 0:
            cur.executemany("""
                INSERT INTO frota_banco_radares (uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo, sentido)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, RADARES_CORREDOR_CE_RN)
            conn.commit()

def verificar_radares_proximos(
    db_name: str,
    lat_atual: float,
    lon_atual: float,
    velocidade_kmh: float = 0.0,
    raio_max_metros: float = 1200.0
) -> List[Dict[str, Any]]:
    inicializar_banco_radares(db_name)
    radares_encontrados = []
    delta_deg = raio_max_metros / 111000.0 * 1.5
    min_lat, max_lat = lat_atual - delta_deg, lat_atual + delta_deg
    min_lon, max_lon = lon_atual - delta_deg, lon_atual + delta_deg

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo, sentido
            FROM frota_banco_radares
            WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
        """, (min_lat, max_lat, min_lon, max_lon))
        candidatos = cur.fetchall()

    for row in candidatos:
        r_id, uf, mun, via, r_lat, r_lon, vel_limite, tipo, sentido = row
        dist = _haversine_metros(lat_atual, lon_atual, r_lat, r_lon)
        if dist <= raio_max_metros:
            em_excesso = (velocidade_kmh > vel_limite) if velocidade_kmh > 0 else False
            radares_encontrados.append({
                "id": r_id,
                "uf": uf,
                "municipio": mun,
                "via": via,
                "distancia_metros": round(dist),
                "distancia_formatada": f"{int(dist)}m" if dist < 1000 else f"{dist/1000:.1f} km",
                "velocidade_limite": vel_limite,
                "tipo": tipo,
                "sentido": sentido,
                "velocidade_atual": round(velocidade_kmh),
                "em_excesso": em_excesso,
                "nivel_alerta": "PERIGO" if (em_excesso and dist < 350) else ("ATENCAO" if dist < 500 else "AVISO")
            })

    radares_encontrados.sort(key=lambda x: x["distancia_metros"])
    return radares_encontrados

def obter_todos_radares(db_name: str) -> List[Dict[str, Any]]:
    inicializar_banco_radares(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo, sentido
            FROM frota_banco_radares
            ORDER BY uf, municipio
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "uf": r[1], "municipio": r[2], "via": r[3],
                "latitude": r[4], "longitude": r[5], "velocidade_limite": r[6],
                "tipo": r[7], "sentido": r[8]
            }
            for r in rows
        ]

def adicionar_radar_campo(db_name: str, uf: str, municipio: str, via: str, lat: float, lon: float, vel: int, tipo: str = "FIXO") -> int:
    inicializar_banco_radares(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO frota_banco_radares (uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo, sentido)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'AMBOS')
        """, (uf.upper().strip(), municipio.strip(), via.strip(), lat, lon, vel, tipo))
        conn.commit()
        return cur.lastrowid

def obter_estatisticas_radares(db_name: str) -> Dict[str, Any]:
    inicializar_banco_radares(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM frota_banco_radares")
        total = cur.fetchone()[0]
        cur.execute("SELECT DISTINCT uf FROM frota_banco_radares")
        ufs = [r[0] for r in cur.fetchall()]
    return {
        "total_radares": total,
        "ufs_cobertas": ufs,
        "modo_offline": True
    }
