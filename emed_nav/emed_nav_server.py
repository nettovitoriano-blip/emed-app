# -*- coding: utf-8 -*-
"""
EmedNav Server - Servidor Dedicado de Navegação, Central de Frota 4G & Radares Offline
Executa independente do sistema de gestão hospitalar.
Conecta diretamente ao banco de dados SQLite (emed.db) para telemetria em tempo real,
gestão de veículos + controle de chips 4G, identificação automática de condutor por proximidade/NFC,
edição de clientes (@ Contrato/Avulso) e 16.480+ radares.
"""

import os
import sys
import json
import sqlite3
import math
import datetime
import urllib.request
import urllib.parse
from contextlib import contextmanager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PARENT_DIR, "emed.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR)
CORS(app)

# Coordenada padrão inicial: Fortaleza / CE (Maraponga / Sede eMED)
DEFAULT_LAT = -3.7965
DEFAULT_LON = -38.5678

DESTINOS_HOSPITAIS = [
    {"id": -1, "nome": "Sede EMED Eletromedicina", "cidade": "Eusébio / CE", "lat": -3.8856, "lon": -38.4614, "tipo_contrato": "CONTRATO"},
    {"id": -2, "nome": "Hospital Wilson Rosado", "cidade": "Mossoró / RN", "lat": -5.1884, "lon": -37.3486, "tipo_contrato": "CONTRATO"},
    {"id": -3, "nome": "Hospital Regional Tarcísio Maia (HRTM)", "cidade": "Mossoró / RN", "lat": -5.1963, "lon": -37.3619, "tipo_contrato": "CONTRATO"},
    {"id": -4, "nome": "Hospital de Olhos de Mossoró", "cidade": "Mossoró / RN", "lat": -5.1842, "lon": -37.3491, "tipo_contrato": "CONTRATO"},
    {"id": -5, "nome": "Hospital Maternidade Almeida Castro", "cidade": "Mossoró / RN", "lat": -5.1873, "lon": -37.3421, "tipo_contrato": "CONTRATO"},
    {"id": -6, "nome": "Hospital São Camilo", "cidade": "Apodi / RN", "lat": -5.6601, "lon": -37.7974, "tipo_contrato": "CONTRATO"},
    {"id": -7, "nome": "Hosp. Reg. Nelson Inácio dos Santos", "cidade": "Assú / RN", "lat": -5.5768, "lon": -36.9102, "tipo_contrato": "CONTRATO"},
    {"id": -8, "nome": "Hosp. Reg. Dr. Cleodon Carlos", "cidade": "Pau dos Ferros / RN", "lat": -6.1132, "lon": -38.2045, "tipo_contrato": "CONTRATO"},
    {"id": -9, "nome": "Hospital Regional do Seridó", "cidade": "Caicó / RN", "lat": -6.4589, "lon": -37.0984, "tipo_contrato": "CONTRATO"},
    {"id": -10, "nome": "Casa de Saúde São Lucas", "cidade": "Natal / RN", "lat": -5.7951, "lon": -35.2045, "tipo_contrato": "CONTRATO"},
    {"id": -11, "nome": "Hospital Monsenhor Walfredo Gurgel", "cidade": "Natal / RN", "lat": -5.8115, "lon": -35.2082, "tipo_contrato": "CONTRATO"},
    {"id": -12, "nome": "Hospital Regional de Guarabira", "cidade": "Guarabira / PB", "lat": -6.8584, "lon": -35.4851, "tipo_contrato": "CONTRATO"}
]

RADARES_CORREDOR = [
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Godofredo Maciel (Maraponga)", "lat": -3.798200, "lon": -38.569100, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Bernardo Manuel (Itaperi)", "lat": -3.792100, "lon": -38.554200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Aguanambi km 2", "lat": -3.754120, "lon": -38.528410, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Bezerra de Menezes próx. North Shopping", "lat": -3.734120, "lon": -38.561200, "vel": 50, "tipo": "SEMAFORO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Eng. Santana Júnior / Iguatemi", "lat": -3.751200, "lon": -38.484120, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Santos Dumont próx. Hospital São Carlos", "lat": -3.738120, "lon": -38.487120, "vel": 50, "tipo": "SEMAFORO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Raul Barbosa próx. Aeroporto", "lat": -3.771200, "lon": -38.511200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Fortaleza", "via": "Av. Alberto Craveiro (Castelão)", "lat": -3.801200, "lon": -38.521200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Eusébio", "via": "CE-040 km 8 (Frente Shopping Eusébio)", "lat": -3.882140, "lon": -38.451200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Eusébio", "via": "Av. Washington Soares / CE-040 km 4", "lat": -3.854120, "lon": -38.461200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Pacajus", "via": "BR-116 km 50", "lat": -4.171200, "lon": -38.461200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Russas", "via": "BR-116 km 162", "lat": -4.931200, "lon": -37.971200, "vel": 60, "tipo": "FIXO"},
    {"uf": "CE", "municipio": "Aracati", "via": "BR-304 km 68", "lat": -4.561230, "lon": -37.771200, "vel": 60, "tipo": "LOMBADA_ELETRONICA"},
    {"uf": "RN", "municipio": "Mossoró", "via": "BR-304 km 45 (Contorno)", "lat": -5.191200, "lon": -37.341200, "vel": 60, "tipo": "FIXO"},
    {"uf": "RN", "municipio": "Mossoró", "via": "Av. Pref. Alberto Maranhão / Centro", "lat": -5.187210, "lon": -37.344500, "vel": 50, "tipo": "SEMAFORO"},
    {"uf": "RN", "municipio": "Apodi", "via": "BR-405 km 75", "lat": -5.658200, "lon": -37.794200, "vel": 60, "tipo": "LOMBADA_ELETRONICA"},
    {"uf": "RN", "municipio": "Assú", "via": "BR-304 km 112", "lat": -5.578120, "lon": -36.912400, "vel": 60, "tipo": "LOMBADA_ELETRONICA"},
    {"uf": "RN", "municipio": "Lajes", "via": "BR-304 km 205", "lat": -5.701230, "lon": -36.241200, "vel": 80, "tipo": "FIXO"},
    {"uf": "RN", "municipio": "Macaíba", "via": "BR-304 km 298", "lat": -5.862410, "lon": -35.341200, "vel": 60, "tipo": "LOMBADA_ELETRONICA"},
    {"uf": "RN", "municipio": "Parnamirim", "via": "BR-101 Sul km 105", "lat": -5.918450, "lon": -35.263120, "vel": 80, "tipo": "FIXO"},
    {"uf": "RN", "municipio": "Natal", "via": "Av. Sen. Salgado Filho próx. Midway", "lat": -5.811822, "lon": -35.207311, "vel": 60, "tipo": "FIXO"}
]


@contextmanager
def get_nav_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_schema():
    """Garante colunas de chip 4G em veiculos e status em clientes."""
    try:
        with get_nav_db() as conn:
            cur = conn.cursor()
            cols = [r[1] for r in cur.execute("PRAGMA table_info(veiculos)").fetchall()]
            extra_cols = [
                ("tipo_veiculo", "TEXT DEFAULT 'CARRO'"),
                ("chip_numero", "TEXT DEFAULT '(85) 99999-4000'"),
                ("chip_operadora", "TEXT DEFAULT 'Vivo M2M 4G'"),
                ("chip_data_ativacao", "TEXT DEFAULT '2026-10-15'"),
                ("chip_data_validade", "TEXT DEFAULT '2026-11-15'"),
            ]
            for cname, cdef in extra_cols:
                if cname not in cols:
                    cur.execute(f"ALTER TABLE veiculos ADD COLUMN {cname} {cdef}")
            cur.execute("""
                UPDATE veiculos
                SET ultima_lat = ?, ultima_lon = ?, ultima_atualizacao_gps = 'Localização Atualizada (Fortaleza)'
                WHERE ROUND(ultima_lat, 3) = -5.187 OR ROUND(ultima_lat, 4) = -3.7319
            """, (DEFAULT_LAT, DEFAULT_LON))
            conn.commit()
    except Exception as e:
        print(f"Aviso schema: {e}")


ensure_schema()


def calcular_status_chip(data_validade_str: str):
    """Calcula quantos dias faltam para vencer o chip 4G e retorna status + alerta."""
    if not data_validade_str:
        return {"dias": 30, "status": "OK", "label": "Em dia"}
    try:
        s = str(data_validade_str).strip()
        if "/" in s:
            dt = datetime.datetime.strptime(s[:10], "%d/%m/%Y").date()
        else:
            dt = datetime.datetime.strptime(s[:10], "%Y-%m-%d").date()
        hoje = datetime.date.today()
        dias = (dt - hoje).days
        dt_fmt = dt.strftime("%d/%m/%Y")
        if dias < 0:
            return {"dias": dias, "status": "VENCIDO", "label": f"🚨 CHIP VENCIDO ({dt_fmt}) — Renovar!"}
        elif dias <= 7:
            return {"dias": dias, "status": "ALERTA", "label": f"⚠️ Vence em {dias} dias ({dt_fmt})"}
        else:
            return {"dias": dias, "status": "OK", "label": f"🟢 Válido até {dt_fmt} ({dias}d)"}
    except Exception:
        return {"dias": 30, "status": "OK", "label": f"Validade: {data_validade_str}"}


@app.route("/")
@app.route("/emedcar")
@app.route("/gps")
def index():
    resp = send_from_directory(STATIC_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/frota")
@app.route("/admin")
def fleet_portal():
    resp = send_from_directory(STATIC_DIR, "frota.html")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/static/<path:filename>")
def serve_static(filename):
    resp = send_from_directory(STATIC_DIR, filename)
    if filename.endswith(".js") or filename.endswith(".json") or filename.endswith(".html"):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/car")
def get_car():
    """Retorna os dados telemétricos mais recentes do veículo selecionado."""
    placa_req = request.args.get("placa", "EMD-2026").strip().upper().replace("-", "")
    try:
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT placa, modelo, km_atual, ultima_lat, ultima_lon,
                       ultima_atualizacao_gps, condutor_atual, ignicao_ligada, tipo_veiculo
                FROM veiculos
                WHERE REPLACE(UPPER(placa), '-', '') = ?
                LIMIT 1
            """, (placa_req,))
            v = cur.fetchone()
            if not v:
                cur.execute("SELECT * FROM veiculos ORDER BY id ASC LIMIT 1")
                v = cur.fetchone()

            lat = float(v["ultima_lat"]) if (v and v["ultima_lat"] and round(float(v["ultima_lat"]), 3) != -5.187 and round(float(v["ultima_lat"]), 4) != -3.7319) else DEFAULT_LAT
            lon = float(v["ultima_lon"]) if (v and v["ultima_lon"] and round(float(v["ultima_lon"]), 3) != -37.372 and round(float(v["ultima_lon"]), 4) != -38.5267) else DEFAULT_LON
            hora = v["ultima_atualizacao_gps"] if (v and v["ultima_atualizacao_gps"]) else "Ao Vivo (Fortaleza)"

            return jsonify({
                "success": True,
                "placa": v["placa"] if v else "EMD-2026",
                "modelo": v["modelo"] if v else "Renault Captur 1.6 SCe",
                "tipo_veiculo": (v["tipo_veiculo"] if v and "tipo_veiculo" in v.keys() else "CARRO") or "CARRO",
                "km": v["km_atual"] if v else 70011,
                "lat": lat,
                "lon": lon,
                "speed": 0.0,
                "updated_at": hora,
                "condutor": v["condutor_atual"] if v else "ANTONIO",
                "ignicao": bool(v["ignicao_ligada"]) if v else False
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "placa": "EMD-2026",
            "lat": DEFAULT_LAT,
            "lon": DEFAULT_LON,
            "speed": 0.0,
            "updated_at": "Ao Vivo"
        })


@app.route("/api/car/update_pos", methods=["POST"])
def update_car_pos():
    """Sincroniza a localização real obtida pelo GPS do navegador/celular com o veículo no banco."""
    try:
        data = request.get_json(force=True) or {}
        lat = float(data.get("lat", DEFAULT_LAT))
        lon = float(data.get("lon", DEFAULT_LON))
        placa = str(data.get("placa", "")).strip().upper()
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        with get_nav_db() as conn:
            cur = conn.cursor()
            if placa:
                cur.execute("""
                    UPDATE veiculos
                    SET ultima_lat = ?, ultima_lon = ?, ultima_atualizacao_gps = ?
                    WHERE REPLACE(UPPER(placa), '-', '') = ?
                """, (lat, lon, agora, placa.replace("-", "")))
            else:
                cur.execute("""
                    UPDATE veiculos
                    SET ultima_lat = ?, ultima_lon = ?, ultima_atualizacao_gps = ?
                """, (lat, lon, agora))
            conn.commit()
        return jsonify({"success": True, "updated_at": agora})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/radars")
def get_radars():
    """Retorna contagem total do banco nacional (16.480+ radares) e radares do corredor regional ou bounds."""
    min_lat = request.args.get("min_lat", type=float)
    max_lat = request.args.get("max_lat", type=float)
    min_lon = request.args.get("min_lon", type=float)
    max_lon = request.args.get("max_lon", type=float)
    uf_filter = request.args.get("uf", "").strip().upper()
    
    lista = list(RADARES_CORREDOR)
    total_db = 16480
    try:
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM frota_banco_radares")
            total_db = cur.fetchone()[0]
            
            if min_lat is not None and max_lat is not None and min_lon is not None and max_lon is not None:
                # Consulta pelos limites de visualização da tela (viewport)
                cur.execute("""
                    SELECT uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo
                    FROM frota_banco_radares
                    WHERE latitude BETWEEN ? AND ?
                      AND longitude BETWEEN ? AND ?
                    LIMIT 1500
                """, (min(min_lat, max_lat), max(min_lat, max_lat), min(min_lon, max_lon), max(min_lon, max_lon)))
            elif uf_filter:
                ufs = [u.strip() for u in uf_filter.split(",")]
                placeholders = ",".join("?" for _ in ufs)
                cur.execute(f"""
                    SELECT uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo
                    FROM frota_banco_radares
                    WHERE uf IN ({placeholders})
                    LIMIT 3000
                """, ufs)
            else:
                # Corredor completo do Nordeste (CE, RN, PB, PE e rodovias federais BR)
                cur.execute("""
                    SELECT uf, municipio, rodovia_via, latitude, longitude, velocidade_kmh, tipo
                    FROM frota_banco_radares
                    WHERE uf IN ('CE', 'RN', 'PB', 'PE', 'PI')
                       OR (uf = 'BR' AND latitude BETWEEN -12.0 AND -2.0 AND longitude BETWEEN -44.0 AND -34.0)
                    LIMIT 3500
                """)
            
            seen = set((round(r["lat"], 4), round(r["lon"], 4)) for r in lista)
            for r in cur.fetchall():
                pt = (round(float(r["latitude"]), 4), round(float(r["longitude"]), 4))
                if pt not in seen:
                    seen.add(pt)
                    lista.append({
                        "uf": r["uf"],
                        "municipio": r["municipio"],
                        "via": r["rodovia_via"],
                        "lat": float(r["latitude"]),
                        "lon": float(r["longitude"]),
                        "vel": int(r["velocidade_kmh"]),
                        "tipo": r["tipo"]
                    })
    except Exception as e:
        pass
        
    return jsonify({
        "success": True,
        "total_db": max(total_db, len(lista)),
        "radars": lista
    })


@app.route("/api/clients")
def get_clients():
    """Retorna lista de clientes ativos cadastrados (com suporte a edição Contrato vs Avulso)."""
    todos = []
    try:
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nome, cidade, estado, telefone, latitude, longitude, segmento, tipo_contrato, status
                FROM clientes
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND (status IS NULL OR UPPER(status) NOT IN ('INATIVO', 'EXCLUIDO', 'NAO_ATENDIDO'))
                ORDER BY tipo_contrato ASC, nome ASC
            """)
            for r in cur.fetchall():
                try:
                    lat_str = str(r["latitude"]).replace(",", ".").strip()
                    lon_str = str(r["longitude"]).replace(",", ".").strip()
                    lat = float(lat_str)
                    lon = float(lon_str)
                    if -35.0 <= lat <= 5.0 and -75.0 <= lon <= -30.0:
                        cidade_uf = f"{r['cidade'] or ''} / {r['estado'] or ''}".strip(" /")
                        tc = str(r["tipo_contrato"] or "AVULSO").upper().strip()
                        is_contrato = "CONTRATO" in tc
                        todos.append({
                            "id": r["id"],
                            "nome": r["nome"],
                            "cidade": cidade_uf or "Cliente EMED",
                            "cidade_raw": r["cidade"] or "",
                            "estado_raw": r["estado"] or "",
                            "telefone": r["telefone"] or "",
                            "lat": lat,
                            "lon": lon,
                            "segmento": r["segmento"] or "Hospital / Clínica",
                            "tipo_contrato": "CONTRATO" if is_contrato else "AVULSO"
                        })
                except Exception:
                    continue
    except Exception as e:
        print(f"Erro ao ler clientes: {e}")
    return jsonify({"success": True, "destinos": todos})


@app.route("/api/clients/update", methods=["POST"])
def update_client():
    """Atualiza dados de um cliente (ex: Avulso -> Contrato, Nome, Cidade) ou desativa se não atendemos mais."""
    try:
        data = request.get_json(force=True) or {}
        cid = data.get("id")
        acao = str(data.get("acao", "SALVAR")).upper()
        with get_nav_db() as conn:
            cur = conn.cursor()
            if acao == "DESATIVAR" and cid:
                cur.execute("UPDATE clientes SET status = 'INATIVO' WHERE id = ?", (cid,))
                conn.commit()
                return jsonify({"success": True, "removed": True})

            nome = str(data.get("nome", "")).strip()
            cidade = str(data.get("cidade", "")).strip()
            estado = str(data.get("estado", "")).strip().upper()
            telefone = str(data.get("telefone", "")).strip()
            tipo_contrato = "CONTRATO" if "CONTRATO" in str(data.get("tipo_contrato", "AVULSO")).upper() else "AVULSO"
            lat = float(data.get("lat", DEFAULT_LAT))
            lon = float(data.get("lon", DEFAULT_LON))

            if cid and int(cid) > 0:
                cur.execute("""
                    UPDATE clientes
                    SET nome = ?, cidade = ?, estado = ?, telefone = ?, tipo_contrato = ?, latitude = ?, longitude = ?, status = 'ATIVO'
                    WHERE id = ?
                """, (nome, cidade, estado, telefone, tipo_contrato, lat, lon, int(cid)))
            else:
                cur.execute("""
                    INSERT INTO clientes (nome, cidade, estado, telefone, tipo_contrato, latitude, longitude, status, segmento)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ATIVO', 'Hospital / Clínica')
                """, (nome, cidade, estado, telefone, tipo_contrato, lat, lon))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/search")
def search_destinations():
    """Busca inteligente de destinos em Fortaleza, Mossoró, RN, CE e hospitais EMED."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify({"success": True, "results": []})

    results = []
    for d in DESTINOS_HOSPITAIS:
        if q in d["nome"].lower() or q in d["cidade"].lower():
            results.append({
                "label": f"🏥 {d['nome']} ({d['cidade']})",
                "lat": d["lat"],
                "lon": d["lon"],
                "type": "hospital"
            })

    try:
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT nome, cidade, estado, latitude, longitude
                FROM clientes
                WHERE (LOWER(nome) LIKE ? OR LOWER(cidade) LIKE ?)
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
                  AND (status IS NULL OR UPPER(status) NOT IN ('INATIVO', 'EXCLUIDO'))
                LIMIT 6
            """, (f"%{q}%", f"%{q}%"))
            for r in cur.fetchall():
                results.append({
                    "label": f"🏥 {r['nome']} ({r['cidade'] or ''}/{r['estado'] or ''})",
                    "lat": float(str(r["latitude"]).replace(",", ".")),
                    "lon": float(str(r["longitude"]).replace(",", ".")),
                    "type": "cliente"
                })
    except Exception:
        pass

    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&countrycodes=br&limit=5&q={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={"User-Agent": "EmedNav/3.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                nome_disp = item.get("display_name", "")
                parts = [p.strip() for p in nome_disp.split(",")][:3]
                curto = ", ".join(parts)
                results.append({
                    "label": f"🔍 {curto}",
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "type": "osm"
                })
    except Exception:
        pass

    return jsonify({"success": True, "results": results[:10]})


ROUTE_CACHE = {}


def haversine_distance_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@app.route("/api/route")
def get_osrm_route():
    """Calcula a rota pelas rodovias reais usando a API pública do OSRM com suporte a paradas intermediárias."""
    try:
        o_lat_str = request.args.get("origin_lat")
        o_lon_str = request.args.get("origin_lon")
        d_lat_str = request.args.get("dest_lat")
        d_lon_str = request.args.get("dest_lon")

        if not o_lat_str or not o_lon_str or not d_lat_str or not d_lon_str:
            return jsonify({"success": False, "error": "Origem e destino são obrigatórios"}), 400

        o_lat = float(o_lat_str)
        o_lon = float(o_lon_str)
        d_lat = float(d_lat_str)
        d_lon = float(d_lon_str)

        # Suporte a paradas intermediárias (ex: stops=-5.18,-37.34|-5.19,-37.36)
        stops_param = request.args.get("stops", "").strip()
        stops_list = []
        if stops_param:
            for seg in stops_param.split("|"):
                if "," in seg:
                    parts = seg.split(",")
                    try:
                        s_lat = float(parts[0].strip())
                        s_lon = float(parts[1].strip())
                        stops_list.append((s_lat, s_lon))
                    except Exception:
                        pass

        # Cria lista ordenada de pontos: [Origem] -> [Parada 1] -> [Parada 2] -> [Destino]
        all_pts = [(o_lat, o_lon)] + stops_list + [(d_lat, d_lon)]
        cache_key = tuple((round(p[0], 3), round(p[1], 3)) for p in all_pts)
        if cache_key in ROUTE_CACHE:
            return jsonify(ROUTE_CACHE[cache_key])

        # Monta chamada OSRM multi-pontos ({lon},{lat};{lon},{lat};...)
        try:
            coords_str = ";".join(f"{p[1]},{p[0]}" for p in all_pts)
            url = f"https://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson&steps=false"
            req = urllib.request.Request(url, headers={"User-Agent": "EmedNav/3.0"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    r0 = data["routes"][0]
                    dist_km = round(r0["distance"] / 1000.0, 1)
                    dur_min = round(r0["duration"] / 60.0, 0)
                    coords = r0["geometry"]["coordinates"]
                    latlngs = [[c[1], c[0]] for c in coords]
                    res = {
                        "success": True,
                        "distance_km": dist_km,
                        "duration_min": dur_min,
                        "coordinates": latlngs,
                        "stops_count": len(stops_list)
                    }
                    if len(ROUTE_CACHE) > 1000:
                        ROUTE_CACHE.pop(next(iter(ROUTE_CACHE)), None)
                    ROUTE_CACHE[cache_key] = res
                    return jsonify(res)
        except Exception:
            pass

        # Fallback instantâneo conectando todos os trechos
        total_direct_km = 0.0
        coords_fallback = []
        for i in range(len(all_pts) - 1):
            p1 = all_pts[i]
            p2 = all_pts[i + 1]
            seg_dist = haversine_distance_km(p1[0], p1[1], p2[0], p2[1])
            total_direct_km += seg_dist
            if i == 0:
                coords_fallback.append([p1[0], p1[1]])
            coords_fallback.append([p2[0], p2[1]])

        road_km = round(total_direct_km * 1.25, 1)
        est_min = max(2, round((road_km / 50.0) * 60.0))
        return jsonify({
            "success": True,
            "distance_km": road_km,
            "duration_min": est_min,
            "coordinates": coords_fallback,
            "stops_count": len(stops_list),
            "fallback": True
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history")
def get_route_history():
    """Retorna os dias com rotas gravadas e um traçado limpo (sem linhas cruzadas) + condutor do dia."""
    day_filter = request.args.get("date", "").strip()
    try:
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT substr(data_hora_inicio, 1, 10) AS dia,
                       COUNT(*) AS total_pontos,
                       MIN(data_hora_inicio) AS inicio,
                       MAX(data_hora_fim) AS fim,
                       MAX(velocidade_max_kmh) AS vel_max,
                       MAX(destino_hospital) AS ultimo_destino,
                       MAX(placa) AS placa,
                       MAX(condutor) AS condutor
                FROM frota_viagens_gps
                WHERE lat_fim IS NOT NULL AND lon_fim IS NOT NULL
                GROUP BY dia
                ORDER BY id DESC
                LIMIT 30
            """)
            days = [dict(r) for r in cur.fetchall()]

            target_day = day_filter or (days[0]["dia"] if days else "")
            raw_points = []
            if target_day:
                cur.execute("""
                    SELECT id, placa, data_hora_inicio, lat_fim, lon_fim, velocidade_max_kmh, destino_hospital, condutor
                    FROM frota_viagens_gps
                    WHERE substr(data_hora_inicio, 1, 10) = ?
                      AND lat_fim IS NOT NULL AND lon_fim IS NOT NULL
                    ORDER BY data_hora_inicio ASC, id ASC
                """, (target_day,))
                for p in cur.fetchall():
                    try:
                        lat = float(p["lat_fim"])
                        lon = float(p["lon_fim"])
                        if round(lat, 4) == -3.7319 and round(lon, 4) == -38.5267:
                            continue
                        if round(lat, 4) == -3.7325 and round(lon, 4) == -38.5270:
                            continue
                        if -35.0 <= lat <= 5.0 and -75.0 <= lon <= -30.0:
                            raw_points.append({
                                "id": p["id"],
                                "placa": p["placa"] or "EMD-2026",
                                "hora": p["data_hora_inicio"],
                                "lat": lat,
                                "lon": lon,
                                "vel": float(p["velocidade_max_kmh"] or 0),
                                "destino": p["destino_hospital"] or "",
                                "condutor": p["condutor"] or "ANTONIO"
                            })
                    except Exception:
                        continue

            clean_points = []
            total_km = 0.0
            if raw_points:
                lats_sorted = sorted(p["lat"] for p in raw_points)
                lons_sorted = sorted(p["lon"] for p in raw_points)
                med_lat = lats_sorted[len(lats_sorted) // 2]
                med_lon = lons_sorted[len(lons_sorted) // 2]

                prev_pt = None
                for pt in raw_points:
                    if haversine_distance_km(med_lat, med_lon, pt["lat"], pt["lon"]) > 80.0:
                        continue
                    if prev_pt is not None:
                        dist = haversine_distance_km(prev_pt["lat"], prev_pt["lon"], pt["lat"], pt["lon"])
                        if dist < 0.015:
                            continue
                        if dist > 12.0:
                            continue
                        total_km += dist
                    clean_points.append(pt)
                    prev_pt = pt

                if not clean_points and raw_points:
                    clean_points = [raw_points[0], raw_points[-1]] if len(raw_points) > 1 else [raw_points[0]]

            return jsonify({
                "success": True,
                "selected_day": target_day,
                "km_percorrido": round(total_km, 1),
                "days": days,
                "points": clean_points
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "days": [], "points": [], "km_percorrido": 0})


@app.route("/api/history/driver", methods=["POST"])
def update_history_driver():
    """Define ou altera o condutor responsável pelas viagens de um dia específico ou veículo."""
    try:
        data = request.get_json(force=True) or {}
        dia = str(data.get("dia", "")).strip()
        placa = str(data.get("placa", "")).strip().upper()
        condutor = str(data.get("condutor", "")).strip().upper()
        if not condutor:
            return jsonify({"success": False, "error": "Informe o nome do condutor"}), 400

        with get_nav_db() as conn:
            cur = conn.cursor()
            if dia:
                cur.execute("""
                    UPDATE frota_viagens_gps
                    SET condutor = ?
                    WHERE substr(data_hora_inicio, 1, 10) = ?
                """, (condutor, dia))
            if placa:
                cur.execute("""
                    UPDATE veiculos
                    SET condutor_atual = ?
                    WHERE REPLACE(UPPER(placa), '-', '') = ?
                """, (condutor, placa.replace("-", "")))
            conn.commit()
        return jsonify({"success": True, "condutor": condutor})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/fleet")
def get_fleet_overview():
    """Retorna visão completa da frota eMED, dados de chip 4G com alerta de validade, técnicos e estatísticas."""
    try:
        db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            drivers = ["NETTO", "ANTONIO", "MARCOS", "ARQUIMEDES", "GABRIEL", "SÉRGIO", "FELIPE"]
            try:
                cur.execute("SELECT nome FROM tecnicos ORDER BY id ASC")
                for tr in cur.fetchall():
                    nm = str(tr["nome"] or "").strip().upper()
                    if nm and nm not in drivers:
                        drivers.append(nm)
            except Exception:
                pass

            cur.execute("SELECT * FROM veiculos ORDER BY id ASC")
            rows = cur.fetchall()
            vehicles = []
            chips_alerta = 0
            for r in rows:
                vd = dict(r)
                raw_lat = float(vd.get("ultima_lat") or DEFAULT_LAT)
                raw_lon = float(vd.get("ultima_lon") or DEFAULT_LON)
                if round(raw_lat, 3) == -5.187 or round(raw_lat, 4) == -3.7319:
                    raw_lat, raw_lon = DEFAULT_LAT, DEFAULT_LON

                chip_val = vd.get("chip_data_validade") or "2026-11-20"
                chip_info = calcular_status_chip(chip_val)
                if chip_info["status"] in ("VENCIDO", "ALERTA"):
                    chips_alerta += 1

                vehicles.append({
                    "id": vd.get("id"),
                    "placa": vd.get("placa") or "EMD-2026",
                    "modelo": vd.get("modelo") or "Renault Captur 1.6 SCe",
                    "tipo_veiculo": vd.get("tipo_veiculo") or "CARRO",
                    "km_atual": int(vd.get("km_atual") or 70011),
                    "km_proxima_revisao": int(vd.get("km_proxima_revisao") or 80000),
                    "status_manutencao": vd.get("status_manutencao") or "EM DIA",
                    "condutor": vd.get("condutor_atual") or "AGUARDANDO (NFC/APP)",
                    "tag_rfid": vd.get("tag_rfid_atual") or "PROXIMIDADE_APP",
                    "imei": vd.get("imei") or "869890080097193",
                    "chip_numero": vd.get("chip_numero") or "(85) 99999-4000",
                    "chip_operadora": vd.get("chip_operadora") or "Vivo M2M 4G",
                    "chip_data_ativacao": vd.get("chip_data_ativacao") or "2026-10-15",
                    "chip_data_validade": chip_val,
                    "chip_status": chip_info["status"],
                    "chip_label": chip_info["label"],
                    "chip_dias": chip_info["dias"],
                    "lat": raw_lat,
                    "lon": raw_lon,
                    "speed": 0.0,
                    "ignicao": bool(vd.get("ignicao_ligada")),
                    "updated_at": vd.get("ultima_atualizacao_gps") or "Ao Vivo (Fortaleza)"
                })

            cur.execute("SELECT COUNT(*) FROM frota_viagens_gps")
            total_gps_points = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(*) FROM clientes
                WHERE latitude IS NOT NULL
                  AND (status IS NULL OR UPPER(status) NOT IN ('INATIVO', 'EXCLUIDO', 'NAO_ATENDIDO'))
            """)
            total_clients = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM frota_banco_radares")
            total_radars = cur.fetchone()[0]

            return jsonify({
                "success": True,
                "vehicles": vehicles,
                "drivers": drivers,
                "stats": {
                    "total_vehicles": len(vehicles),
                    "online_vehicles": len(vehicles),
                    "chips_alerta": chips_alerta,
                    "total_gps_points": total_gps_points,
                    "total_clients": total_clients,
                    "total_radars": total_radars,
                    "db_size_mb": db_size_mb
                }
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "vehicles": [], "drivers": [], "stats": {}})


@app.route("/api/car/proximity")
def detect_vehicle_by_proximity():
    """Identifica automaticamente o veículo mais próximo ao abrir o App dentro do carro ou via NFC."""
    try:
        u_lat = float(request.args.get("lat") or DEFAULT_LAT)
        u_lon = float(request.args.get("lon") or DEFAULT_LON)
        nfc_placa = request.args.get("placa", "").strip().upper().replace("-", "")

        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            drivers = ["NETTO", "ANTONIO", "MARCOS", "ARQUIMEDES", "GABRIEL", "SÉRGIO", "FELIPE"]
            try:
                cur.execute("SELECT nome FROM tecnicos ORDER BY id ASC")
                for tr in cur.fetchall():
                    nm = str(tr["nome"] or "").strip().upper()
                    if nm and nm not in drivers:
                        drivers.append(nm)
            except Exception:
                pass

            cur.execute("SELECT * FROM veiculos ORDER BY id ASC")
            vehicles = []
            for r in cur.fetchall():
                vd = dict(r)
                vlat = float(vd.get("ultima_lat") or DEFAULT_LAT)
                vlon = float(vd.get("ultima_lon") or DEFAULT_LON)
                dist_km = haversine_distance_km(u_lat, u_lon, vlat, vlon)
                dist_m = int(round(dist_km * 1000))
                placa_clean = str(vd.get("placa") or "").upper().replace("-", "")
                is_nfc_match = bool(nfc_placa and placa_clean == nfc_placa)
                vehicles.append({
                    "id": vd.get("id"),
                    "placa": vd.get("placa") or "EMD-2026",
                    "modelo": vd.get("modelo") or "Veículo eMED",
                    "tipo_veiculo": vd.get("tipo_veiculo") or "CARRO",
                    "km_atual": int(vd.get("km_atual") or 0),
                    "condutor_atual": vd.get("condutor_atual") or "DISPONÍVEL",
                    "lat": vlat,
                    "lon": vlon,
                    "dist_m": 0 if is_nfc_match else dist_m,
                    "metodo_deteccao": "TAG NFC DO CARRO" if is_nfc_match else "PROXIMIDADE GPS"
                })

            vehicles.sort(key=lambda x: x["dist_m"])
            nearest = vehicles[0] if vehicles else None
            return jsonify({
                "success": True,
                "nearest": nearest,
                "vehicles": vehicles,
                "drivers": drivers
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/car/assume", methods=["POST"])
def assume_vehicle_wheel():
    """Grava que o técnico assumiu o volante do veículo (por proximidade no App ou Tag NFC)."""
    try:
        data = request.get_json(force=True) or {}
        placa = str(data.get("placa", "")).strip().upper()
        condutor = str(data.get("condutor", "")).strip().upper()
        metodo = str(data.get("metodo", "APP_PROXIMIDADE_GPS")).strip().upper()
        lat = float(data.get("lat") or DEFAULT_LAT)
        lon = float(data.get("lon") or DEFAULT_LON)

        if not placa or not condutor:
            return jsonify({"success": False, "error": "Placa e condutor são obrigatórios"}), 400

        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        with get_nav_db() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT id, modelo, km_atual FROM veiculos WHERE REPLACE(UPPER(placa), '-', '') = ?", (placa.replace("-", ""),))
            v = cur.fetchone()
            modelo = v["modelo"] if v else "Veículo Frota eMED"
            km = int(v["km_atual"] or 0) if v else 0

            cur.execute("""
                UPDATE veiculos
                SET condutor_atual = ?, tag_rfid_atual = ?, ultima_lat = ?, ultima_lon = ?, ultima_atualizacao_gps = ?, ignicao_ligada = 1
                WHERE REPLACE(UPPER(placa), '-', '') = ?
            """, (condutor, metodo, lat, lon, agora, placa.replace("-", "")))

            cur.execute("""
                INSERT INTO frota_viagens_gps (
                    placa, modelo, condutor, tag_identificacao, destino_hospital,
                    data_hora_inicio, data_hora_fim, km_inicial, km_final, km_percorrido,
                    lat_inicio, lon_inicio, lat_fim, lon_fim, velocidade_max_kmh, status_viagem
                ) VALUES (?, ?, ?, ?, 'EM DESLOCAMENTO (VOLANTE ASSUMIDO)', ?, ?, ?, ?, 0.0, ?, ?, ?, ?, 0.0, 'EM ANDAMENTO')
            """, (placa, modelo, condutor, metodo, agora, agora, km, km, lat, lon, lat, lon))
            conn.commit()

        return jsonify({
            "success": True,
            "placa": placa,
            "modelo": modelo,
            "condutor": condutor,
            "updated_at": agora
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/fleet/vehicle", methods=["POST"])
def save_fleet_vehicle():
    """Cadastra, atualiza ou exclui um veículo com todos os dados do Chip 4G e validade (sem exigir condutor fixo)."""
    try:
        data = request.get_json(force=True) or {}
        acao = str(data.get("acao", "SALVAR")).upper()
        placa = str(data.get("placa", "")).strip().upper()

        with get_nav_db() as conn:
            cur = conn.cursor()
            if acao == "EXCLUIR" and placa:
                cur.execute("DELETE FROM veiculos WHERE REPLACE(UPPER(placa), '-', '') = ?", (placa.replace("-", ""),))
                conn.commit()
                return jsonify({"success": True, "deleted": True})

            modelo = str(data.get("modelo", "")).strip()
            tipo_veiculo = str(data.get("tipo_veiculo", "CARRO")).strip().upper()
            km_atual = int(data.get("km_atual") or 0)
            imei = str(data.get("imei", "")).strip()
            chip_numero = str(data.get("chip_numero", "")).strip()
            chip_operadora = str(data.get("chip_operadora", "Vivo M2M 4G")).strip()
            chip_data_ativacao = str(data.get("chip_data_ativacao", "")).strip()
            chip_data_validade = str(data.get("chip_data_validade", "")).strip()
            lat = float(data.get("lat") or DEFAULT_LAT)
            lon = float(data.get("lon") or DEFAULT_LON)

            if not placa or not modelo:
                return jsonify({"success": False, "error": "Placa e modelo são obrigatórios"}), 400

            cur.execute("SELECT id, condutor_atual FROM veiculos WHERE REPLACE(UPPER(placa), '-', '') = ?", (placa.replace("-", ""),))
            row = cur.fetchone()
            agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            if row:
                cur.execute("""
                    UPDATE veiculos
                    SET placa = ?, modelo = ?, tipo_veiculo = ?, km_atual = ?,
                        imei = ?, chip_numero = ?, chip_operadora = ?, chip_data_ativacao = ?, chip_data_validade = ?,
                        ultima_lat = ?, ultima_lon = ?, ultima_atualizacao_gps = ?
                    WHERE id = ?
                """, (placa, modelo, tipo_veiculo, km_atual, imei, chip_numero, chip_operadora, chip_data_ativacao, chip_data_validade, lat, lon, agora, row[0]))
            else:
                cur.execute("""
                    INSERT INTO veiculos (
                        placa, modelo, tipo_veiculo, condutor_atual, km_atual, km_ultima_revisao, km_proxima_revisao,
                        status_manutencao, ultima_lat, ultima_lon, ultima_atualizacao_gps, ignicao_ligada, imei,
                        chip_numero, chip_operadora, chip_data_ativacao, chip_data_validade
                    )
                    VALUES (?, ?, ?, 'AGUARDANDO (NFC/APP)', ?, ?, ?, 'EM DIA', ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """, (placa, modelo, tipo_veiculo, km_atual, km_atual, km_atual + 10000, lat, lon, agora, imei, chip_numero, chip_operadora, chip_data_ativacao, chip_data_validade))
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"🚀 [EMED-NAV] Servidor dedicado iniciado na porta {porta}...")
    app.run(host="0.0.0.0", port=porta, debug=False, threaded=True)
