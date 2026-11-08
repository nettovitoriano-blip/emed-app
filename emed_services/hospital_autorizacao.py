# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Credenciamento e Autorização Formal de Entrada em Hospitais
Gera documento formal (HTML/PDF) e mensagem WhatsApp para portaria hospitalar.
"""

import sqlite3
import datetime
from typing import Dict, Any

def obter_dados_credenciamento_os(db_name: str, os_id: int) -> Dict[str, Any]:
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, cliente, equipamento, modelo, numero_serie, tecnico_responsavel, data_abertura, status FROM clientes_equipamentos WHERE id = ?", (os_id,))
        row = cur.fetchone()
        if not row:
            # Tenta buscar em clientes ou clientes_internos
            return {"ok": False, "msg": f"OS #{os_id} não localizada"}

    return {
        "ok": True,
        "os_id": row[0],
        "hospital": row[1] or "HOSPITAL / CLÍNICA",
        "equipamento": row[2] or "Equipamento Médico",
        "modelo": row[3] or "",
        "numero_serie": row[4] or "",
        "tecnico": row[5] or "Técnico Especialista EMED",
        "data": row[6] or datetime.datetime.now().strftime("%d/%m/%Y"),
        "status": row[7] or "ABERTA"
    }

def gerar_texto_whatsapp_portaria(dados: Dict[str, Any]) -> str:
    hosp = dados.get("hospital", "Hospital")
    tec = dados.get("tecnico", "Técnico EMED")
    equip = dados.get("equipamento", "Equipamento")
    os_id = dados.get("os_id", "")
    return (
        f"🏥 *COMUNICADO DE AUTORIZAÇÃO DE ENTRADA — EMED ELETROMEDICINA*\n\n"
        f"Prezada Portaria / Engenharia Clínica do *{hosp}*,\n\n"
        f"Informamos que o profissional *{tec}*, portando credencial técnica da EMED, "
        f"está designado para atendimento presencial da *OS #{os_id}* referente ao equipamento *{equip}*.\n\n"
        f"Solicitamos a gentileza de autorizar seu acesso às dependências técnicas."
    )

def gerar_html_autorizacao_entrada(dados: Dict[str, Any]) -> str:
    hosp = dados.get("hospital", "Hospital")
    tec = dados.get("tecnico", "Técnico EMED")
    equip = dados.get("equipamento", "Equipamento")
    mod = dados.get("modelo", "")
    serie = dados.get("numero_serie", "")
    os_id = dados.get("os_id", "")
    dt = dados.get("data", datetime.datetime.now().strftime("%d/%m/%Y"))

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Autorização de Entrada - OS #{os_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #1e293b; line-height: 1.6; }}
        .header {{ border-bottom: 3px solid #00b4d8; padding-bottom: 15px; margin-bottom: 25px; display: flex; justify-content: space-between; }}
        .title {{ font-size: 20px; font-weight: bold; color: #0f172a; }}
        .box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .row {{ margin: 8px 0; }}
        .label {{ font-weight: bold; color: #475569; }}
        .footer {{ margin-top: 50px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 15px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="title">EMED ELETROMEDICINA LTDA.</div>
            <div>Engenharia Clínica e Manutenção Hospitalar</div>
        </div>
        <div style="text-align: right;">
            <strong>OS #{os_id}</strong><br>
            <span>{dt}</span>
        </div>
    </div>

    <h3>TERMO DE CREDENCIAMENTO E AUTORIZAÇÃO DE ACESSO TÉCNICO</h3>
    <p>Declaramos para os devidos fins de controle de acesso portaria e segurança predial do <strong>{hosp}</strong> que o colaborador abaixo está formalmente designado e habilitado pela EMED para execução dos serviços técnicos:</p>

    <div class="box">
        <div class="row"><span class="label">Técnico Designado:</span> {tec}</div>
        <div class="row"><span class="label">Empresa:</span> EMED Eletromedicina Ltda.</div>
        <div class="row"><span class="label">Equipamento Alvo:</span> {equip} {mod} (Série: {serie})</div>
        <div class="row"><span class="label">Objetivo:</span> Manutenção preventiva / corretiva e calibração biomédica</div>
    </div>

    <div class="footer">
        EMED Eletromedicina Ltda. • Fortaleza / CE • Suporte Operacional: (85) 3000-0000
    </div>
</body>
</html>"""
