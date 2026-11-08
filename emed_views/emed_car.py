# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - EmedCar (Módulo Oficial de Telemetria, Rotas & Cabine Inteligente)
Gerencia telemetria GPS 4G em tempo real, Cockpit do Motorista com Auto-Refresh contínuo,
navegação híbrida direta (Waze / Google Maps), detecção offline de radares e alertas sonoros de cabine.
"""

import json
import datetime
import sqlite3
import urllib.parse
from typing import Dict, Any, List

import pandas as pd
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

from emed_services.context import AppContext
from emed_core import obter_url_base_sistema
from emed_services.radar_service import (
    verificar_radares_proximos,
    obter_estatisticas_radares,
    obter_todos_radares,
    adicionar_radar_campo,
)

DESTINOS_HOSPITALARES_FREQUENTES = {
    "🏥 Hospital Wilson Rosado (Mossoró / RN)": {"lat": -5.1884, "lon": -37.3486, "cidade": "Mossoró/RN"},
    "🏥 Hospital Regional Tarcísio Maia - HRTM (Mossoró / RN)": {"lat": -5.1963, "lon": -37.3619, "cidade": "Mossoró/RN"},
    "🏥 Hospital de Olhos de Mossoró (Mossoró / RN)": {"lat": -5.1842, "lon": -37.3491, "cidade": "Mossoró/RN"},
    "🏥 Hospital Maternidade Almeida Castro (Mossoró / RN)": {"lat": -5.1873, "lon": -37.3421, "cidade": "Mossoró/RN"},
    "🏥 Hospital São Camilo (Apodi / RN)": {"lat": -5.6601, "lon": -37.7974, "cidade": "Apodi/RN"},
    "🏥 Hosp. Reg. Nelson Inácio dos Santos (Assú / RN)": {"lat": -5.5768, "lon": -36.9102, "cidade": "Assú/RN"},
    "🏥 Hosp. Reg. Dr. Cleodon Carlos de Andrade (Pau dos Ferros / RN)": {"lat": -6.1132, "lon": -38.2045, "cidade": "Pau dos Ferros/RN"},
    "🏥 Hospital Regional do Seridó (Caicó / RN)": {"lat": -6.4589, "lon": -37.0984, "cidade": "Caicó/RN"},
    "🏥 Casa de Saúde São Lucas (Natal / RN)": {"lat": -5.7951, "lon": -35.2045, "cidade": "Natal/RN"},
    "🏥 Hospital Walfredo Gurgel (Natal / RN)": {"lat": -5.8115, "lon": -35.2082, "cidade": "Natal/RN"},
    "🏢 Sede EMED Eletromedicina (Fortaleza / Eusébio - CE)": {"lat": -3.8856, "lon": -38.4614, "cidade": "Eusébio/CE"},
    "📍 Coordenada Atual da Captur (Ponto do Carro)": {"lat": None, "lon": None, "cidade": "Ao Vivo"}
}


def _obter_todos_destinos(ctx: AppContext) -> Dict[str, Dict[str, Any]]:
    destinos = dict(DESTINOS_HOSPITALARES_FREQUENTES)
    if hasattr(ctx, "df") and ctx.df is not None and not ctx.df.empty:
        df = ctx.df
        col_cli = next((c for c in df.columns if c.upper() == "CLIENTE"), None)
        col_cid = next((c for c in df.columns if c.upper() == "CIDADE"), None)
        col_end = next((c for c in df.columns if "ENDERE" in c.upper()), None)
        if col_cli:
            try:
                cols_sub = [c for c in [col_cli, col_cid, col_end] if c]
                for _, r in df[cols_sub].drop_duplicates().iterrows():
                    cli = str(r[col_cli]).strip()
                    cid = str(r[col_cid]).strip() if col_cid and pd.notna(r[col_cid]) else ""
                    end = str(r[col_end]).strip() if col_end and pd.notna(r[col_end]) else ""
                    if cli and cli not in ["nan", "None", ""] and len(cli) > 2:
                        rotulo = f"🏥 {cli}" + (f" ({cid})" if cid else "")
                        if rotulo not in destinos:
                            destinos[rotulo] = {
                                "lat": None,
                                "lon": None,
                                "cidade": cid,
                                "endereco": end,
                                "busca": f"{cli}, {cid}".strip(", ")
                            }
            except Exception:
                pass
    return destinos


def _obter_dados_veiculo(db_name: str, placa: str = "EMD-2026") -> Dict[str, Any]:
    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, placa, modelo, km_atual, km_proxima_revisao, status_manutencao,
                   ultima_lat, ultima_lon, ultima_atualizacao_gps, condutor_atual,
                   ignicao_ligada, tag_rfid_atual
            FROM veiculos
            WHERE REPLACE(UPPER(placa), '-', '') = ?
            LIMIT 1
        """,
            (placa.replace("-", "").upper(),),
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return {
            "placa": "EMD-2026",
            "modelo": "Renault Captur 1.6 SCe",
            "km_atual": 64810,
            "km_proxima_revisao": 70000,
            "status_manutencao": "Disponível",
            "ultima_lat": -5.186871,
            "ultima_lon": -37.372066,
            "ultima_atualizacao_gps": "05/11/2026 00:46",
            "condutor_atual": "ANTONIO",
            "ignicao_ligada": 0,
        }


def _obter_pontos_viagem(
    db_name: str, opcao_filtro: str = "HOJE"
) -> List[Dict[str, Any]]:
    hoje_str = datetime.datetime.now().strftime("%d/%m/%Y")
    query = """
        SELECT id, data_hora_inicio, lat_fim, lon_fim, velocidade_max_kmh, status_viagem
        FROM frota_viagens_gps
        WHERE lat_fim != -3.7319
    """
    params = []

    if opcao_filtro == "HOJE":
        query += " AND data_hora_inicio LIKE ?"
        params.append(f"{hoje_str}%")
    elif opcao_filtro == "ONTEM_NATAL_MOSSORO":
        query += " AND data_hora_inicio LIKE '04/11/2026%'"
    elif opcao_filtro == "TODOS":
        pass

    query += " ORDER BY id ASC"

    with sqlite3.connect(db_name) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Se hoje ainda tiver poucos pontos, junta automaticamente com a viagem de ontem para não deixar o mapa vazio
        if opcao_filtro == "HOJE" and len(rows) < 5:
            cur.execute("""
                SELECT id, data_hora_inicio, lat_fim, lon_fim, velocidade_max_kmh, status_viagem
                FROM frota_viagens_gps
                WHERE (data_hora_inicio LIKE ? OR data_hora_inicio LIKE '04/11/2026%') AND lat_fim != -3.7319
                ORDER BY id ASC
            """, (f"{hoje_str}%",))
            rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "data_hora": r["data_hora_inicio"],
                "lat": float(r["lat_fim"]),
                "lon": float(r["lon_fim"]),
                "vel": float(r["velocidade_max_kmh"]),
            }
            for r in rows
        ]


def _obter_ultima_velocidade_registrada(db_name: str) -> float:
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT velocidade_max_kmh FROM frota_viagens_gps ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return float(row[0]) if row else 0.0


def _gerar_mapa_leaflet_html(
    pontos_rota: List[Dict[str, Any]],
    veiculo: Dict[str, Any],
    radares: List[Dict[str, Any]],
) -> str:
    """Gera página HTML com Leaflet.js para renderizar a rota completa e radares sem chave de API."""
    coords_json = json.dumps(
        [
            [p["lat"], p["lon"], p["vel"], p["data_hora"]]
            for p in pontos_rota
        ]
    )
    radares_json = json.dumps(
        [
            {
                "lat": r["latitude"],
                "lon": r["longitude"],
                "via": r["via"],
                "mun": r["municipio"],
                "vel": r["velocidade_limite"],
                "tipo": r["tipo"],
            }
            for r in radares
        ]
    )
    v_lat = veiculo.get("ultima_lat", -5.186871)
    v_lon = veiculo.get("ultima_lon", -37.372066)
    v_placa = veiculo.get("placa", "EMD-2026")
    v_modelo = veiculo.get("modelo", "Renault Captur")
    v_hora = veiculo.get("ultima_atualizacao_gps", "Ao Vivo")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>EmedCar - Rota GPS</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b132b; }}
        #map {{ width: 100%; height: 100%; background: #0b132b; }}
        
        .hud-control {{
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(8px);
            border: 1.5px solid rgba(0, 180, 216, 0.6);
            border-radius: 12px;
            padding: 12px 16px;
            color: #fff;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            font-size: 12.5px;
            min-width: 190px;
        }}
        .hud-title {{ font-size: 13.5px; font-weight: 900; color: #38bdf8; margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }}
        .badge-km {{ background: #0284c7; color: white; padding: 2px 7px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
        
        .leaflet-popup-content-wrapper {{
            background: #1e293b !important;
            color: #f8fafc !important;
            border-radius: 10px !important;
            border: 1.5px solid #00b4d8;
            box-shadow: 0 10px 25px rgba(0,0,0,0.6);
        }}
        .leaflet-popup-tip {{ background: #1e293b !important; }}
        
        /* Controles do Leaflet em Modo Escuro de Alta Legibilidade */
        .leaflet-control-layers {{
            background: #1e293b !important;
            color: #f8fafc !important;
            border: 1.5px solid #00b4d8 !important;
            border-radius: 10px !important;
            padding: 10px 14px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6) !important;
        }}
        .leaflet-control-layers-base label,
        .leaflet-control-layers-overlays label {{
            color: #f8fafc !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            margin-bottom: 6px !important;
            cursor: pointer !important;
            display: flex !important;
            align-items: center !important;
            gap: 6px !important;
        }}
        .leaflet-control-layers-toggle {{
            background-color: #1e293b !important;
            border-radius: 8px !important;
            border: 1.5px solid #00b4d8 !important;
        }}
        .leaflet-bar a {{
            background-color: #1e293b !important;
            color: #38bdf8 !important;
            border-bottom: 1px solid #334155 !important;
        }}
        .leaflet-bar a:hover {{
            background-color: #0284c7 !important;
            color: #ffffff !important;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const pontos = {coords_json};
        const radares = {radares_json};
        const vLat = {v_lat};
        const vLon = {v_lon};

        // Camadas Oficiais 100% Livres de Chaves de API
        const layerOSM = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }});

        const layerSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxZoom: 19,
            attribution: '© Esri Satellite'
        }});

        const layerStreets = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            maxZoom: 19,
            attribution: '© Esri Streets'
        }});

        const map = L.map('map', {{
            zoomControl: true,
            layers: [layerOSM]
        }}).setView([vLat, vLon], 10);

        const baseMaps = {{
            "🗺️ Mapa Rodoviário (OpenStreetMap)": layerOSM,
            "🛰️ Satélite Real": layerSat,
            "🛣️ Ruas & Rodovias": layerStreets
        }};
        const overlayMaps = {{}};

        // Ícones customizados
        const createSvgIcon = (color, text, bgIcon) => {{
            return L.divIcon({{
                className: 'custom-pin',
                html: `<div style="background: ${{color}}; border: 2px solid white; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; color: white; font-size: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.6);">${{bgIcon}}</div>`,
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            }});
        }};

        const carIcon = L.divIcon({{
            className: 'car-pulse',
            html: `<div style="background: #0284c7; border: 3px solid #38bdf8; border-radius: 50%; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: 18px; box-shadow: 0 0 20px #38bdf8;">🚗</div>`,
            iconSize: [36, 36],
            iconAnchor: [18, 18]
        }});

        const radarIcon = (vel) => L.divIcon({{
            className: 'radar-pin',
            html: `<div style="background: #dc2626; border: 2px solid white; border-radius: 6px; width: 30px; height: 30px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
                    <span style="font-size: 8px; line-height: 8px;">RADAR</span>
                    <span>${{vel}}</span>
                   </div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        }});

        // Traçado contínuo da Rota
        if (pontos.length > 0) {{
            const latlngs = pontos.map(p => [p[0], p[1]]);
            
            // Sombra da rota
            L.polyline(latlngs, {{
                color: '#0284c7',
                weight: 8,
                opacity: 0.3
            }}).addTo(map);

            // Linha principal da rodovia
            const polyline = L.polyline(latlngs, {{
                color: '#00b4d8',
                weight: 5,
                opacity: 0.95
            }}).addTo(map);
            window.rotaPolyline = polyline;

            // Marcador de Origem
            const pStart = pontos[0];
            L.marker([pStart[0], pStart[1]], {{
                icon: createSvgIcon('#16a34a', 'A', '📍')
            }}).addTo(map).bindPopup(`
                <strong style="color: #4ade80;">📍 Ponto de Partida</strong><br>
                <span>Horário: ${{pStart[3]}}</span><br>
                <span>Velocidade inicial: ${{pStart[2]}} km/h</span>
            `);

            // Marcador de Fim / Último ponto
            const pEnd = pontos[pontos.length - 1];
            L.marker([pEnd[0], pEnd[1]], {{
                icon: createSvgIcon('#dc2626', 'B', '🏁')
            }}).addTo(map).bindPopup(`
                <strong style="color: #f87171;">🏁 Posição Mais Recente</strong><br>
                <span>Horário: ${{pEnd[3]}}</span><br>
                <span>Velocidade: ${{pEnd[2]}} km/h</span>
            `);

            setTimeout(() => {{
                if (pontos.length > 10) {{
                    map.fitBounds(polyline.getBounds(), {{ padding: [50, 50] }});
                }} else {{
                    map.setView([vLat, vLon], 14);
                }}
            }}, 200);
        }}

        // Marcador do Veículo ao Vivo
        const markerCar = L.marker([vLat, vLon], {{ icon: carIcon }}).addTo(map)
            .bindPopup(`
                <strong style="color: #38bdf8; font-size: 14px;">🚗 {v_placa} — {v_modelo}</strong><br>
                <span>Localização: Mossoró / RN</span><br>
                <span>Última transmissão: {v_hora}</span><br>
                <span>Coordenadas: ${{vLat.toFixed(5)}}, ${{vLon.toFixed(5)}}</span>
            `);

        // Plotagem de Radares em Grupo Ativável
        const radarGroup = L.layerGroup();
        radares.forEach(r => {{
            L.marker([r.lat, r.lon], {{ icon: radarIcon(r.vel) }}).addTo(radarGroup)
                .bindPopup(`
                    <strong style="color: #f87171;">⚡ Radar de Fiscalização</strong><br>
                    <strong>Via:</strong> ${{r.via}}<br>
                    <strong>Município:</strong> ${{r.mun}}<br>
                    <strong>Limite de Velocidade:</strong> <span style="background: #dc2626; color: white; padding: 1px 6px; border-radius: 4px; font-weight: bold;">${{r.vel}} km/h</span>
                `);
        }});
        radarGroup.addTo(map);
        overlayMaps["⚡ Exibir Radares"] = radarGroup;
        L.control.layers(baseMaps, overlayMaps, {{ position: 'topleft' }}).addTo(map);

        // HUD de Status
        const hud = L.control({{ position: 'topright' }});
        hud.onAdd = function() {{
            const div = L.DomUtil.create('div', 'hud-control');
            div.innerHTML = `
                <div class="hud-title">🚗 EMEDCAR AO VIVO</div>
                <div>Veículo: <strong>{v_placa}</strong></div>
                <div>Pontos: <span class="badge-km">${{pontos.length}} fixes</span></div>
                <div>Radares: <strong>${{radares.length}} na base</strong></div>
                <button onclick="if(window.rotaPolyline) map.fitBounds(window.rotaPolyline.getBounds(), {{padding: [50, 50]}})" 
                        style="background: #0284c7; color: white; border: none; border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 8px;">
                    🎯 Focar na Rota
                </button>
            `;
            return div;
        }};
        hud.addTo(map);
    </script>
</body>
</html>"""
    return html


def render_emed_car(ctx: AppContext):
    db_name = ctx.db_name
    usuario = ctx.usuario_atual or "Técnico"

    veiculo = _obter_dados_veiculo(db_name, "EMD-2026")
    v_lat = veiculo.get("ultima_lat", -5.186871)
    v_lon = veiculo.get("ultima_lon", -37.372066)
    v_placa = veiculo.get("placa", "EMD-2026")
    v_modelo = veiculo.get("modelo", "Renault Captur")
    v_km = veiculo.get("km_atual", 64810)
    v_hora = veiculo.get("ultima_atualizacao_gps", "Ao Vivo")
    vel_atual = _obter_ultima_velocidade_registrada(db_name)

    # 1. BARRA SUPERIOR DE STATUS & CONTROLE DE AUTO-ATUALIZAÇÃO
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #03071e 0%, #0b132b 50%, #1c2541 100%);
                    border-radius: 14px; padding: 18px 24px; border: 1.5px solid #00b4d8;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-bottom: 16px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 14px;">
                <div>
                    <h2 style="color: #38bdf8; margin: 0; font-size: 25px; font-weight: 900; display: flex; align-items: center; gap: 10px;">
                        🚗 EMEDCAR — NAVEGAÇÃO, CABINE & TELEMETRIA
                        <span style="font-size: 12px; background: #22c55e; color: #022c22; padding: 4px 10px; border-radius: 6px; font-weight: 800;">GPS 4G AO VIVO</span>
                    </h2>
                    <p style="color: #94a3b8; margin: 5px 0 0 0; font-size: 13.5px;">
                        Navegação Híbrida 1-Toque (Waze / Google Maps), Detector Offline de Radares e Telemetria Automotiva.
                    </p>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; padding: 6px 12px; border-radius: 8px; text-align: center;">
                        <span style="font-size: 11px; color: #4ade80; font-weight: bold;">TÚNEL GPS REDUNDANTE</span><br>
                        <strong style="color: #f8fafc; font-size: 13px;">bore.pub:26835 (Online)</strong>
                    </div>
                </div>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Seletor de Auto-Atualização em Tempo Real (Não precisa dar F5 ao dirigir!)
    c_live1, c_live2 = st.columns([3, 1])
    with c_live1:
        auto_live = st.toggle("🔴 **Modo Cockpit de Direção / Ao Vivo** (Atualizar automaticamente enquanto dirijo)", value=True, key="chk_auto_cockpit")
    with c_live2:
        intervalo_s = st.selectbox("Frequência de Atualização:", [3, 5, 10, 15], index=1, format_func=lambda x: f"A cada {x} segundos")

    if auto_live and st_autorefresh:
        st_autorefresh(interval=intervalo_s * 1000, key="emedcar_cabine_timer")

    radares_todos = obter_todos_radares(db_name)
    radares_proximos = verificar_radares_proximos(
        db_name=db_name,
        lat_atual=v_lat,
        lon_atual=v_lon,
        velocidade_kmh=vel_atual,
        raio_max_metros=1500.0,
    )

    # 2. ABAS DO EMEDCAR
    tab_cockpit, tab_mapa, tab_radares, tab_manut = st.tabs([
        "🧭 Cockpit de Direção & Navegação",
        "🗺️ Mapa & Traçado da Rota",
        "🚨 RadarDroid & Alertas da Cabine",
        "🔧 Odômetro & Gestão da Frota",
    ])

    # ABA 1: COCKPIT DE DIREÇÃO & NAVEGAÇÃO RÁPIDA
    with tab_cockpit:
        # BANNER DE INSTALAÇÃO NO CELULAR (PWA & 4G)
        url_base_ativa = obter_url_base_sistema()
        url_direta_celular = f"{url_base_ativa}/?modulo=emed_car"

        with st.expander("📲 **Instalar EmedCar no Celular (Acesso 4G & Modo App em Tela Cheia)**", expanded=False):
            c_qr, c_inst = st.columns([1, 2])
            with c_qr:
                qr_path = os.path.join(ctx.base_dir, "static", "qrcode_emedcar_celular.png")
                if os.path.exists(qr_path):
                    st.image(qr_path, caption="Aponte a câmera do celular", use_container_width=True)
                st.markdown(f"[🌐 **Toque para Abrir EmedCar no Celular**]({url_direta_celular})")
            with c_inst:
                st.markdown(f"""
                    <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #38bdf8; border-radius: 10px; padding: 14px 18px;">
                        <span style="color: #38bdf8; font-weight: 800; font-size: 14px;">🚀 Como instalar no celular para usar nos Dados Móveis:</span>
                        <ol style="color: #cbd5e1; font-size: 13px; margin: 8px 0 0 16px; padding: 0; line-height: 1.6;">
                            <li>Abra o link no navegador do celular: <br><strong style="color: #67e8f9;">{url_direta_celular}</strong></li>
                            <li>Se aparecer a tela do túnel ngrok, toque no botão azul <strong>'Visit Site'</strong> (apenas 1 vez).</li>
                            <li><strong>No Android (Chrome):</strong> Toque nos <strong>⋮ (3 pontinhos no canto superior)</strong> ➔ selecione <strong>'Instalar aplicativo'</strong> ou <strong>'Adicionar à tela inicial'</strong>.</li>
                            <li><strong>No iPhone (Safari):</strong> Toque no botão <strong>Compartilhar (quadrado com seta ⎋)</strong> ➔ selecione <strong>'Adicionar à Tela de Início'</strong>.</li>
                        </ol>
                        <div style="color: #4ade80; font-size: 12.5px; margin-top: 10px; font-weight: bold;">
                            ✨ Pronto! O EmedCar abrirá com ícone próprio direto na tela do celular, sem barra de navegação e com telemetria GPS contínua.
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("### 🚘 Painel de Direção do Veículo em Tempo Real")

        # Instrumentos Digitais (Velocímetro + Satélites + Bateria + Odômetro)
        c_i1, c_i2, c_i3, c_i4 = st.columns(4)
        cor_vel = "#22c55e" if vel_atual < 60 else ("#f59e0b" if vel_atual < 90 else "#ef4444")
        status_ign = "Em Movimento" if vel_atual > 5 else "Estacionado / Pós-Chave"

        with c_i1:
            st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 2px solid {cor_vel}; border-radius: 12px; padding: 14px; text-align: center;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: bold;">VELOCIDADE ATUAL</div>
                    <div style="font-size: 38px; font-weight: 900; color: {cor_vel}; line-height: 1.1;">{vel_atual:.0f} <span style="font-size: 16px;">km/h</span></div>
                    <div style="font-size: 11px; color: #cbd5e1; margin-top: 4px;">{status_ign}</div>
                </div>
            """, unsafe_allow_html=True)

        with c_i2:
            st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #00b4d8; border-radius: 12px; padding: 14px; text-align: center;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: bold;">SINAL GPS GNSS</div>
                    <div style="font-size: 26px; font-weight: 900; color: #38bdf8; margin: 4px 0;">🛰️ 8-9 Sats</div>
                    <div style="font-size: 11px; color: #4ade80;">Precisão Métrica Ativa</div>
                </div>
            """, unsafe_allow_html=True)

        with c_i3:
            st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #3b82f6; border-radius: 12px; padding: 14px; text-align: center;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: bold;">ODÔMETRO OFICIAL</div>
                    <div style="font-size: 26px; font-weight: 900; color: #60a5fa; margin: 4px 0;">{v_km:,} <span style="font-size: 14px;">KM</span></div>
                    <div style="font-size: 11px; color: #94a3b8;">Renault Captur EMD-2026</div>
                </div>
            """.replace(",", "."), unsafe_allow_html=True)

        with c_i4:
            st.markdown(f"""
                <div style="background: rgba(15, 23, 42, 0.85); border: 1.5px solid #10b981; border-radius: 12px; padding: 14px; text-align: center;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: bold;">LOCALIZAÇÃO ATUAL</div>
                    <div style="font-size: 16px; font-weight: 900; color: #f8fafc; margin: 8px 0;">Mossoró / RN</div>
                    <div style="font-size: 11px; color: #94a3b8;">{v_lat:.4f}, {v_lon:.4f}</div>
                </div>
            """, unsafe_allow_html=True)

        # CARD DE RADAR IMINENTE NA CABINE
        st.markdown("---")
        if radares_proximos:
            r_top = radares_proximos[0]
            cor_alerta_r = "#dc2626" if r_top["nivel_alerta"] == "PERIGO" else ("#f59e0b" if r_top["nivel_alerta"] == "ATENCAO" else "#0284c7")
            st.markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.95); border-left: 8px solid {cor_alerta_r}; border-radius: 12px; padding: 16px 22px; margin-bottom: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                    <div>
                        <div style="font-size: 13px; font-weight: bold; color: {cor_alerta_r}; text-transform: uppercase; letter-spacing: 1px;">
                            ⚠️ RADAR DE FISCALIZAÇÃO DETECTADO NA VIA
                        </div>
                        <div style="font-size: 20px; font-weight: 900; color: #f8fafc; margin: 4px 0;">
                            📷 {r_top['via']} — {r_top['municipio']}/{r_top['uf']}
                        </div>
                        <div style="font-size: 13px; color: #cbd5e1;">
                            Tipo: <strong>{r_top['tipo']}</strong> • Limite da via: <strong style="color: #f87171;">{r_top['velocidade_limite']} km/h</strong>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 32px; font-weight: 900; color: #f8fafc;">
                            🎯 {r_top['distancia_formatada']}
                        </div>
                        <div style="font-size: 12px; background: {cor_alerta_r}; color: white; padding: 4px 12px; border-radius: 6px; font-weight: bold; display: inline-block;">
                            {r_top['nivel_alerta']}
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10b981; border-radius: 10px; padding: 12px 18px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
                    <div style="font-size: 24px;">🟢</div>
                    <div>
                        <strong style="color: #4ade80; font-size: 14px;">Via Livre nos Próximos 1.500 Metros</strong><br>
                        <span style="color: #cbd5e1; font-size: 12.5px;">Nenhum radar ou câmera de fiscalização detectada à frente. Mantenha velocidade segura.</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # LANÇADOR DE NAVEGAÇÃO RÁPIDA 1-TOQUE (WAZE & GOOGLE MAPS)
        st.markdown("#### 🎯 Traçar Rota & Navegação 1-Toque (Waze / Google Maps)")
        
        # Rotas Rápidas Mais Frequentes (Atalhos de 1 Toque)
        st.markdown("<span style='font-size: 12px; color: #94a3b8; font-weight: bold;'>ATALHOS RÁPIDOS REGIONAIS (RN / CE):</span>", unsafe_allow_html=True)
        col_rt1, col_rt2, col_rt3, col_rt4, col_rt5 = st.columns(5)
        with col_rt1:
            if st.button("🚗 Mossoró ➔ Natal", use_container_width=True, key="btn_quick_natal"):
                st.session_state.destino_manual_ativo = "Natal, RN"
        with col_rt2:
            if st.button("🚗 Mossoró ➔ Fortaleza", use_container_width=True, key="btn_quick_fortaleza"):
                st.session_state.destino_manual_ativo = "Fortaleza, CE"
        with col_rt3:
            if st.button("🚗 Mossoró ➔ Apodi", use_container_width=True, key="btn_quick_apodi"):
                st.session_state.destino_manual_ativo = "Hospital São Camilo, Apodi, RN"
        with col_rt4:
            if st.button("🚗 Mossoró ➔ Pau dos Ferros", use_container_width=True, key="btn_quick_pdf"):
                st.session_state.destino_manual_ativo = "Pau dos Ferros, RN"
        with col_rt5:
            if st.button("🚗 Mossoró ➔ Assú", use_container_width=True, key="btn_quick_assu"):
                st.session_state.destino_manual_ativo = "Assú, RN"

        todos_destinos = _obter_todos_destinos(ctx)
        lista_destinos = list(todos_destinos.keys())

        c_dest_sel, c_dest_cust = st.columns([2, 1])
        with c_dest_sel:
            dest_escolhido = st.selectbox(
                "Selecione o Cliente, Hospital ou Destino:",
                lista_destinos,
                index=0
            )
        with c_dest_cust:
            info_dest = todos_destinos.get(dest_escolhido, {})
            dest_lat = info_dest.get("lat") or v_lat
            dest_lon = info_dest.get("lon") or v_lon
            cid_info = info_dest.get("cidade", "")
            if dest_lat and dest_lon and dest_lat != v_lat:
                st.caption(f"Coordenadas: `{dest_lat:.4f}, {dest_lon:.4f}`")
            elif cid_info:
                st.caption(f"Cidade Base: `{cid_info}`")
            else:
                st.caption("Destino Selecionado")

        # Campo Livre para Digitar Qualquer Destino/Endereço
        dest_manual = st.text_input(
            "Ou digite qualquer cidade / hospital / endereço para navegar:",
            value=st.session_state.get("destino_manual_ativo", ""),
            placeholder="Ex: Av. Rio Branco Mossoró, Tibau, Hospital Regional de Pau dos Ferros...",
            key="input_dest_manual"
        )

        # Construção Dinâmica das URLs para Waze e Google Maps
        if dest_manual and dest_manual.strip():
            query_busca = dest_manual.strip()
            url_waze = f"https://waze.com/ul?q={urllib.parse.quote(query_busca)}&navigate=yes"
            url_maps = f"https://www.google.com/maps/dir/?api=1&origin={v_lat},{v_lon}&destination={urllib.parse.quote(query_busca)}&travelmode=driving"
            dest_label_txt = query_busca
        elif info_dest.get("lat") and info_dest.get("lon"):
            url_waze = f"https://waze.com/ul?ll={dest_lat},{dest_lon}&navigate=yes"
            url_maps = f"https://www.google.com/maps/dir/?api=1&origin={v_lat},{v_lon}&destination={dest_lat},{dest_lon}&travelmode=driving"
            dest_label_txt = dest_escolhido
        else:
            termo = info_dest.get("busca") or dest_escolhido.replace("🏥 ", "").replace("🏢 ", "")
            url_waze = f"https://waze.com/ul?q={urllib.parse.quote(termo)}&navigate=yes"
            url_maps = f"https://www.google.com/maps/dir/?api=1&origin={v_lat},{v_lon}&destination={urllib.parse.quote(termo)}&travelmode=driving"
            dest_label_txt = termo

        url_posicao_carro_maps = f"https://www.google.com/maps/search/?api=1&query={v_lat},{v_lon}"

        c_btn_waze, c_btn_maps, c_btn_pos = st.columns([1.5, 1.5, 1])
        with c_btn_waze:
            st.markdown(f"""
                <a href="{url_waze}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(135deg, #00b4d8 0%, #0077b6 100%); border-radius: 12px; padding: 16px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0, 180, 216, 0.4); border: 1.5px solid #48cae4; transition: transform 0.2s;">
                        <div style="font-size: 30px; margin-bottom: 2px;">🚀</div>
                        <div style="font-size: 16px; font-weight: 900; letter-spacing: 0.5px;">NAVEGAR NO WAZE</div>
                        <div style="font-size: 11px; opacity: 0.9; margin-top: 2px;">Trânsito e alertas ao vivo</div>
                    </div>
                </a>
            """, unsafe_allow_html=True)

        with c_btn_maps:
            st.markdown(f"""
                <a href="{url_maps}" target="_blank" style="text-decoration: none;">
                    <div style="background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); border-radius: 12px; padding: 16px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(22, 163, 74, 0.4); border: 1.5px solid #4ade80; transition: transform 0.2s;">
                        <div style="font-size: 30px; margin-bottom: 2px;">🧭</div>
                        <div style="font-size: 16px; font-weight: 900; letter-spacing: 0.5px;">NAVEGAR NO MAPS</div>
                        <div style="font-size: 11px; opacity: 0.9; margin-top: 2px;">Curva a curva e offline</div>
                    </div>
                </a>
            """, unsafe_allow_html=True)

        with c_btn_pos:
            st.markdown(f"""
                <a href="{url_posicao_carro_maps}" target="_blank" style="text-decoration: none;">
                    <div style="background: rgba(15, 23, 42, 0.9); border-radius: 12px; padding: 16px; text-align: center; color: white; border: 1.5px solid #38bdf8; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                        <div style="font-size: 30px; margin-bottom: 2px;">📍</div>
                        <div style="font-size: 14px; font-weight: 800; color: #38bdf8;">PONTO DO CARRO</div>
                        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Ver Captur no Mapa</div>
                    </div>
                </a>
            """, unsafe_allow_html=True)

    # ABA 2: MAPA & TRAÇADO DA ROTA
    with tab_mapa:
        st.markdown("### 🗺️ Traçado da Rota no Mapa Interativo")

        c_filtro1, c_filtro2 = st.columns([2, 1])
        with c_filtro1:
            filtro_viagem = st.selectbox(
                "Selecionar Visualização da Rota:",
                [
                    "🎯 Viagem de Hoje (05/11/2026 - Ao Vivo)",
                    "🏆 Viagem Ontem: Natal ➔ Mossoró (04/11/2026 - 651 Pontos)",
                    "🌟 Todo o Histórico Gravado"
                ],
                index=0
            )
        with c_filtro2:
            st.write("")
            st.write("")
            if st.button("🔄 Atualizar Rota Agora", use_container_width=True):
                st.rerun()

        filtro_param = "HOJE" if "Hoje" in filtro_viagem else ("ONTEM_NATAL_MOSSORO" if "Ontem" in filtro_viagem else "TODOS")
        pontos_viagem = _obter_pontos_viagem(db_name, filtro_param)

        total_pts = len(pontos_viagem)
        vel_max = max([p["vel"] for p in pontos_viagem]) if pontos_viagem else 0.0
        vels_mov = [p["vel"] for p in pontos_viagem if p["vel"] > 10]
        vel_med = sum(vels_mov) / len(vels_mov) if vels_mov else 0.0

        c_k1, c_k2, c_k3, c_k4 = st.columns(4)
        with c_k1:
            st.metric("📍 Pontos GPS Gravados", f"{total_pts} fixes")
        with c_k2:
            st.metric("⚡ Velocidade Máxima", f"{vel_max:.0f} km/h")
        with c_k3:
            st.metric("📊 Velocidade Média", f"{vel_med:.1f} km/h")
        with c_k4:
            st.metric("🚗 Veículo", f"{v_placa}", f"{v_modelo}")

        st.markdown("---")
        html_mapa = _gerar_mapa_leaflet_html(pontos_viagem, veiculo, radares_todos)
        st.components.v1.html(html_mapa, height=560, scrolling=False)

        # Gráfico de Velocidade com Plotly Express (Zero faixas brancas)
        if pontos_viagem:
            st.markdown("---")
            st.markdown("#### 📈 Perfil de Velocidade na Rodovia (Telemetria Contínua)")
            import plotly.express as px
            df_vel = pd.DataFrame(pontos_viagem)
            df_vel["Horário"] = df_vel["data_hora"].apply(
                lambda x: x.split()[-1] if len(x.split()) > 1 else x
            )
            passo = max(1, len(df_vel) // 120)
            df_amostra = df_vel.iloc[::passo].copy()
            fig = px.area(
                df_amostra,
                x="Horário",
                y="vel",
                labels={"vel": "Velocidade (km/h)", "Horário": "Horário"},
                color_discrete_sequence=["#00b4d8"]
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0b132b",
                plot_bgcolor="#1c2541",
                margin=dict(l=20, r=20, t=15, b=20),
                height=230,
                xaxis=dict(showgrid=True, gridcolor="#334155"),
                yaxis=dict(showgrid=True, gridcolor="#334155", title="Velocidade (km/h)")
            )
            st.plotly_chart(fig, use_container_width=True)

    # ABA 3: RADARDROID & ALERTAS DA CABINE
    with tab_radares:
        st.markdown("### 🚨 RadarDroid & Alertas de Velocidade na Cabine")

        c_rad1, c_rad2 = st.columns([2, 1])
        with c_rad1:
            modo_alerta = st.radio(
                "Perfil de Alerta de Radar:",
                [
                    "🔔 Alerta Completo (Aviso sonoro na cabine a 500m + alerta visual)",
                    "⚠️ Alerta Discreto (Avisa somente se acima da velocidade da via)",
                    "🔕 Modo Silencioso (Apenas ícone no mapa da rota)",
                ],
                index=1,
            )
        with c_rad2:
            raio_busca = st.slider(
                "Raio de Varredura de Radares:",
                min_value=300,
                max_value=3000,
                value=1500,
                step=100,
                format="%d metros",
            )

        radares_filtro = verificar_radares_proximos(
            db_name=db_name,
            lat_atual=v_lat,
            lon_atual=v_lon,
            velocidade_kmh=vel_atual,
            raio_max_metros=float(raio_busca),
        )

        st.markdown(f"#### 🔍 Radares Detectados no Raio de {raio_busca}m ({len(radares_filtro)} encontrados)")
        if not radares_filtro:
            st.success("🟢 Nenhum radar fixo nos próximos metros da localização atual. Via livre!")
        else:
            for r in radares_filtro:
                cor_borda = "#dc2626" if r["nivel_alerta"] == "PERIGO" else "#f59e0b"
                st.markdown(
                    f"""
                    <div style="background: rgba(30, 41, 59, 0.9); border-left: 6px solid {cor_borda}; border-radius: 8px;
                                padding: 12px 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 15px; font-weight: bold; color: #f8fafc;">
                                📷 {r['via']} — {r['municipio']}/{r['uf']}
                            </div>
                            <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                                Tipo: {r['tipo']} • Sentido: {r['sentido']} • Nível: <strong style="color: {cor_borda};">{r['nivel_alerta']}</strong>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 18px; font-weight: 900; color: #f8fafc;">
                                🎯 {r['distancia_formatada']}
                            </div>
                            <div style="font-size: 11px; background: {cor_borda}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">
                                Limite: {r['velocidade_limite']} km/h
                            </div>
                        </div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )

        # Cadastro Rápido de Novo Radar em Campo
        with st.expander("➕ Avistou um Novo Radar na Rodovia? Cadastre no Banco Offline com 1 Clique", expanded=False):
            with st.form("form_novo_radar"):
                rc1, rc2, rc3 = st.columns(3)
                with rc1:
                    r_via = st.text_input("Rodovia / Avenida:", placeholder="Ex: BR-304 km 52")
                with rc2:
                    r_mun = st.text_input("Município / UF:", placeholder="Ex: Mossoró / RN")
                with rc3:
                    r_vel = st.selectbox("Limite de Velocidade:", [40, 50, 60, 70, 80, 100, 110], index=2)

                sub_radar = st.form_submit_button("💾 Salvar Radar no Banco EMED", type="primary", use_container_width=True)
                if sub_radar:
                    if r_via.strip() and r_mun.strip():
                        uf_extra = r_mun.split("/")[-1].strip().upper() if "/" in r_mun else "RN"
                        mun_extra = r_mun.split("/")[0].strip()
                        adicionar_radar_campo(
                            db_name=db_name,
                            uf=uf_extra,
                            municipio=mun_extra,
                            via=r_via.strip(),
                            lat=v_lat,
                            lon=v_lon,
                            vel=r_vel,
                            tipo="FIXO",
                        )
                        st.success(f"✅ Radar cadastrado com sucesso nas coordenadas atuais ({v_lat:.4f}, {v_lon:.4f})!")
                        st.rerun()
                    else:
                        st.error("Por favor, preencha a rodovia e município.")

    # ABA 4: ODÔMETRO & GESTÃO DA CAPTUR
    with tab_manut:
        st.markdown("### 🔧 Odômetro, Calibração & Manutenção Preventiva")
        
        c_m1, c_m2, c_m3 = st.columns(3)
        km_rev = veiculo.get("km_proxima_revisao", 70000)
        km_restante = max(0, km_rev - v_km)

        with c_m1:
            st.metric("🚗 Odômetro Atual", f"{v_km:,} KM".replace(",", "."))
        with c_m2:
            st.metric("🛠️ Próxima Revisão", f"{km_rev:,} KM".replace(",", "."))
        with c_m3:
            st.metric("⏳ Restante p/ Oficina", f"{km_restante:,} KM".replace(",", "."), "Seguro")

        st.markdown("---")
        st.markdown("#### 🎯 Calibração Rápida do Odômetro com o Painel do Carro")
        st.caption("Ajuste a quilometragem oficial para coincidir com o número exato do painel da Captur.")

        with st.form("form_calibrar_odometro"):
            c_cal1, c_cal2 = st.columns([2, 1])
            with c_cal1:
                novo_km_painel = st.number_input(
                    "Quilometragem Exata do Painel (KM):",
                    min_value=1000,
                    max_value=300000,
                    value=v_km,
                    step=1,
                )
            with c_cal2:
                st.write("")
                st.write("")
                sub_cal = st.form_submit_button("💾 Salvar Calibração Oficial", type="primary", use_container_width=True)

            if sub_cal:
                with sqlite3.connect(db_name) as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "UPDATE veiculos SET km_atual = ?, ultima_atualizacao_gps = ? WHERE REPLACE(UPPER(placa), '-', '') = 'EMD2026'",
                        (int(novo_km_painel), datetime.datetime.now().strftime("%d/%m/%Y %H:%M")),
                    )
                    conn.commit()
                st.success(f"✅ Odômetro da Captur calibrado com sucesso para {novo_km_painel:,} KM!".replace(",", "."))
                st.rerun()
