# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Prontuário Digital do Equipamento por QR Code
Permite ao hospital escanear a etiqueta do aparelho e ver todo o histórico de manutenções.
"""

import sqlite3
import datetime
import io
import base64
import qrcode
from typing import Dict, Any

def gerar_qrcode_base64(texto: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b132b", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def obter_historico_anual_equipamento(db_name: str, equip_id: int) -> Dict[str, Any]:
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, cliente, equipamento, modelo, numero_serie, tag, status, local_instalacao FROM clientes_equipamentos WHERE id = ?", (equip_id,))
        row = cur.fetchone()
        if not row:
            return {"ok": False, "msg": f"Equipamento #{equip_id} não localizado"}

        # Histórico de intervenções / OS
        cur.execute("SELECT id, data_abertura, tipo_servico, defeito_reclamado, status FROM clientes_equipamentos WHERE numero_serie = ? ORDER BY id DESC LIMIT 10", (row[4],))
        historico = cur.fetchall()

    return {
        "ok": True,
        "id": row[0],
        "cliente": row[1] or "Hospital Parceiro",
        "equipamento": row[2] or "Equipamento Biomédico",
        "modelo": row[3] or "Padrão",
        "numero_serie": row[4] or "S/N",
        "tag": row[5] or f"EMED-{row[0]}",
        "status": row[6] or "OPERACIONAL",
        "local": row[7] or "Setor Hospitalar",
        "historico": [{"id": h[0], "data": h[1], "tipo": h[2], "defeito": h[3], "status": h[4]} for h in historico]
    }

def gerar_pagina_prontuario_equipamento(dados: Dict[str, Any]) -> str:
    equip = dados.get("equipamento", "")
    mod = dados.get("modelo", "")
    serie = dados.get("numero_serie", "")
    hosp = dados.get("cliente", "")
    tag = dados.get("tag", "")
    status = dados.get("status", "OPERACIONAL")

    linhas_hist = ""
    for item in dados.get("historico", []):
        linhas_hist += f"<tr><td>{item.get('data', '-')}</td><td>{item.get('tipo', 'Manutenção')}</td><td>{item.get('defeito', 'Preventiva periódica')}</td><td><span style='color:green;font-weight:bold;'>{item.get('status', 'CONCLUÍDO')}</span></td></tr>"

    if not linhas_hist:
        linhas_hist = "<tr><td colspan='4' style='text-align:center;'>Nenhum histórico anterior registrado. Equipamento com calibração em dia.</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Prontuário Digital EMED - {equip}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; max-width: 650px; margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }}
        .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #00b4d8; padding-bottom: 15px; margin-bottom: 20px; }}
        .badge {{ background: #00b4d8; color: #03045e; padding: 4px 10px; border-radius: 20px; font-weight: 800; font-size: 13px; }}
        .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }}
        .info-item {{ background: #0f172a; padding: 12px; border-radius: 8px; border: 1px solid #334155; }}
        .label {{ font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; }}
        .value {{ font-size: 15px; font-weight: 700; color: #e2e8f0; margin-top: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <div>
                <h2 style="margin:0;color:#38bdf8;">EMED Eletromedicina</h2>
                <div style="font-size:13px;color:#94a3b8;">Prontuário Digital do Equipamento</div>
            </div>
            <div class="badge">{status}</div>
        </div>

        <div class="info-grid">
            <div class="info-item"><div class="label">Hospital / Cliente</div><div class="value">{hosp}</div></div>
            <div class="info-item"><div class="label">Tag / Patrimônio</div><div class="value">{tag}</div></div>
            <div class="info-item"><div class="label">Equipamento</div><div class="value">{equip}</div></div>
            <div class="info-item"><div class="label">Modelo / Série</div><div class="value">{mod} (S/N: {serie})</div></div>
        </div>

        <h4 style="color:#38bdf8;margin:20px 0 10px 0;">Histórico Recente de Intervenções</h4>
        <table>
            <thead><tr><th>Data</th><th>Tipo</th><th>Descrição</th><th>Status</th></tr></thead>
            <tbody>{linhas_hist}</tbody>
        </table>
    </div>
</body>
</html>"""

def gerar_etiqueta_qrcode_html(dados: Dict[str, Any], qr_b64: str) -> str:
    equip = dados.get("equipamento", "")
    serie = dados.get("numero_serie", "")
    tag = dados.get("tag", "")
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Etiqueta QR Code - {tag}</title>
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; display: flex; justify-content: center; }}
        .etiqueta {{ width: 320px; border: 2px solid #0f172a; border-radius: 8px; padding: 12px; display: flex; align-items: center; gap: 12px; }}
        .qr {{ width: 100px; height: 100px; }}
        .info {{ font-size: 11px; }}
        .brand {{ font-weight: bold; font-size: 13px; color: #0284c7; margin-bottom: 4px; }}
        .tag {{ font-weight: bold; font-size: 14px; margin-bottom: 2px; }}
    </style>
</head>
<body>
    <div class="etiqueta">
        <img class="qr" src="data:image/png;base64,{qr_b64}">
        <div class="info">
            <div class="brand">EMED HOSPITALAR</div>
            <div class="tag">{tag}</div>
            <div><strong>Item:</strong> {equip}</div>
            <div><strong>Série:</strong> {serie}</div>
            <div style="font-size:9px;color:#64748b;margin-top:4px;">Acesse o prontuário escaneando o QR Code.</div>
        </div>
    </div>
</body>
</html>"""
