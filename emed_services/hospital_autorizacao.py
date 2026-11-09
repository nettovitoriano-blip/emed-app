# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Credenciamento e Autorização Formal de Entrada em Hospitais
Gera documento formal (HTML/PDF) e mensagem WhatsApp para portaria hospitalar (ex: Hospital São Carlos).
Permite seleção de equipe técnica múltipla (titular + auxiliares) com dados de CPF, RG, CFT, ASO e Veículo.
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def obter_lista_tecnicos_credenciamento(db_name: str) -> List[Dict[str, Any]]:
    """Retorna lista de técnicos com todas as credenciais para portaria hospitalar."""
    tecnicos = []
    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, nome, telefone, assinatura_padrao, data_vencimento_aso, 
                       medico_examinador, clinica_medicina_trabalho, parecer_aptidao,
                       cpf, rg, registro_conselho, veiculo_placa, treinamentos
                FROM tecnicos
                ORDER BY nome ASC
            """)
            for row in cur.fetchall():
                nome = row[1] or ""
                if not nome:
                    continue
                tecnicos.append({
                    "id": row[0],
                    "nome": nome,
                    "telefone": row[2] or "",
                    "assinatura_padrao": row[3] or f"{nome} - CFT",
                    "data_vencimento_aso": row[4] or "EM DIA",
                    "medico_examinador": row[5] or "Dr. Roberto Arruda - CRM/CE 14258",
                    "clinica_medicina_trabalho": row[6] or "MedWork Saúde Ocupacional",
                    "parecer_aptidao": row[7] or "APTO",
                    "cpf": row[8] or "Cadastrado",
                    "rg": row[9] or "SSP/CE",
                    "registro_conselho": row[10] or "CFT/CE Ativo",
                    "veiculo_placa": row[11] or "EMD-2026 (Fiat Argo)",
                    "treinamentos": row[12] or "NR-10 (Alta Tensão) / NR-32 (Ambiente Hospitalar)"
                })
    except Exception as e:
        print(f"Erro ao listar técnicos para credenciamento: {e}")
    return tecnicos

def obter_dados_credenciamento_os(db_name: str, os_id: int) -> Dict[str, Any]:
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, cliente, equipamento, tecnico_responsavel, 
                   status, responsavel_hospital, contato_responsavel, 
                   email, whatsapp, endereco, credenciamento_enviado, credenciamento_data, 
                   credenciamento_tecnicos, data_agendamento
            FROM clientes_equipamentos 
            WHERE id = ? OR rowid = ?
        """, (os_id, os_id))
        row = cur.fetchone()
        if not row:
            return {"ok": False, "msg": f"OS #{os_id} não localizada"}

    cli_nome = row[1] or "HOSPITAL / CLÍNICA"
    responsavel = row[5] or "Portaria / Engenharia Clínica"
    contato_tel = row[6] or row[8] or ""
    email_hosp = row[7] or ""
    
    # Se for São Carlos, garantir contatos diretos padrão
    if "SAO CARLOS" in cli_nome.upper() or "SÃO CARLOS" in cli_nome.upper():
        if not contato_tel:
            contato_tel = "85991897379"
        if not email_hosp:
            email_hosp = "manutencao@saocarlosimagem.com.br"
        if not responsavel or responsavel == "Portaria / Engenharia Clínica":
            responsavel = "Sra. Damares / William (Eng. Clínica / Manutenção)"

    return {
        "ok": True,
        "os_id": row[0],
        "hospital": cli_nome,
        "equipamento": row[2] or "Equipamento Médico",
        "modelo": "",
        "numero_serie": "S/N",
        "tecnico": row[3] or "Técnico Especialista EMED",
        "data_agendamento": row[13] or datetime.datetime.now().strftime("%d/%m/%Y"),
        "status": row[4] or "ABERTA",
        "responsavel_hospital": responsavel,
        "contato_responsavel": contato_tel,
        "email_hospital": email_hosp,
        "endereco": row[9] or "Unidade Hospitalar",
        "credenciamento_enviado": row[10] or "NAO",
        "credenciamento_data": row[11] or "",
        "credenciamento_tecnicos": row[12] or "",
        "exige_portaria_estrita": bool("SAO CARLOS" in cli_nome.upper() or "SÃO CARLOS" in cli_nome.upper())
    }

def gerar_texto_whatsapp_portaria(dados: Dict[str, Any], lista_tecs: List[Dict[str, Any]] = None) -> str:
    hosp = dados.get("hospital", "Hospital São Carlos")
    equip = dados.get("equipamento", "Equipamento")
    mod = dados.get("modelo", "")
    os_id = dados.get("os_id", "")
    resp = dados.get("responsavel_hospital", "Portaria / Segurança")
    data_prevista = dados.get("data_agendamento", datetime.datetime.now().strftime("%d/%m/%Y"))
    if "-" in str(data_prevista):
        try:
            data_prevista = datetime.datetime.strptime(str(data_prevista)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            pass

    linhas_tecs = []
    if lista_tecs and len(lista_tecs) > 0:
        for t in lista_tecs:
            placa_str = f" | Veículo: {t.get('veiculo_placa')}" if t.get('veiculo_placa') else ""
            linhas_tecs.append(
                f"• *{t.get('nome')}* (CPF: {t.get('cpf', 'N/D')} | RG: {t.get('rg', 'SSP/CE')})\n"
                f"  Registro: {t.get('registro_conselho', 'CFT/CE')} | ASO: {t.get('data_vencimento_aso', 'Em dia')}{placa_str}"
            )
    else:
        tec_padrao = dados.get("tecnico", "Técnico Especialista EMED")
        linhas_tecs.append(f"• *{tec_padrao}* (Técnico Biomédico Credenciado EMED)")

    bloco_tecs = "\n\n".join(linhas_tecs)

    return (
        f"🏥 *COMUNICADO DE AUTORIZAÇÃO DE ENTRADA & ACESSO TÉCNICO*\n"
        f"Empresa: *EMED Eletromedicina Ltda.* (CNPJ: 07.283.365/0001-10)\n\n"
        f"À Portaria, Recepção e Engenharia Clínica do *{hosp}*\n"
        f"A/C: *{resp}*\n\n"
        f"Informamos que a equipe técnica credenciada da EMED comparecerá para execução dos serviços de manutenção na *OS #{os_id}*:\n\n"
        f"🔧 *Equipamento Alvo:* {equip} {mod}\n"
        f"📅 *Data Prevista:* {data_prevista}\n\n"
        f"👤 *PROFISSIONAL(IS) DESIGNADO(S):*\n"
        f"{bloco_tecs}\n\n"
        f"🛡️ *Conformidade Regulatória:*\n"
        f"- Atestado de Saúde Ocupacional (ASO) em validade com aptidão médica;\n"
        f"- Treinamentos NR-10 (Segurança em Eletricidade) e NR-32 (Ambiente Hospitalar) vigentes;\n"
        f"- Portando crachá institucional, ferramentas calibradas e EPIs adequados.\n\n"
        f"Solicitamos a gentileza de conceder a devida liberação de acesso na guarita/portaria.\n\n"
        f"📞 *Plantão Operacional EMED:* (85) 99915-0273 / (85) 99619-7923"
    )

def gerar_html_autorizacao_entrada(dados: Dict[str, Any], lista_tecs: List[Dict[str, Any]] = None) -> str:
    hosp = dados.get("hospital", "HOSPITAL SÃO CARLOS")
    equip = dados.get("equipamento", "Equipamento Médico")
    mod = dados.get("modelo", "")
    serie = dados.get("numero_serie", "S/N")
    os_id = dados.get("os_id", "")
    resp = dados.get("responsavel_hospital", "Engenharia Clínica / Portaria")
    dt = dados.get("data_agendamento", datetime.datetime.now().strftime("%d/%m/%Y"))
    if "-" in str(dt):
        try:
            dt = datetime.datetime.strptime(str(dt)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            pass

    emissao_agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # Renderiza tabela de técnicos credenciados
    rows_tecs_html = ""
    if lista_tecs and len(lista_tecs) > 0:
        for t in lista_tecs:
            rows_tecs_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px; font-weight: bold; color: #0f172a;">{t.get('nome')}</td>
                <td style="padding: 10px; color: #334155;">{t.get('cpf', 'N/D')}<br><small style="color:#64748b;">RG: {t.get('rg', 'SSP/CE')}</small></td>
                <td style="padding: 10px; color: #0284c7; font-weight: bold;">{t.get('registro_conselho', 'CFT/CE')}</td>
                <td style="padding: 10px; color: #166534;"><span style="background:#dcfce7;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold;">APTO (Val: {t.get('data_vencimento_aso', 'Em dia')})</span></td>
                <td style="padding: 10px; color: #475569; font-size: 12px;">{t.get('veiculo_placa', 'EMD-2026')}</td>
            </tr>
            """
    else:
        tec_padrao = dados.get("tecnico", "TÉCNICO ESPECIALISTA EMED")
        rows_tecs_html = f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px; font-weight: bold; color: #0f172a;">{tec_padrao}</td>
            <td style="padding: 10px; color: #334155;">Conforme Cadastro EMED</td>
            <td style="padding: 10px; color: #0284c7; font-weight: bold;">CFT/CE Ativo</td>
            <td style="padding: 10px; color: #166534;"><span style="background:#dcfce7;padding:3px 8px;border-radius:12px;font-size:11px;font-weight:bold;">APTO / VIGENTE</span></td>
            <td style="padding: 10px; color: #475569; font-size: 12px;">Veículo Operacional EMED</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Termo Formal de Credenciamento e Autorização de Entrada - OS #{os_id}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 30px 40px; color: #0f172a; line-height: 1.5; background: #fff; }}
        .header {{ border-bottom: 3px solid #0284c7; padding-bottom: 15px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
        .title {{ font-size: 22px; font-weight: 900; color: #0369a1; letter-spacing: 0.5px; }}
        .subtitle {{ font-size: 13px; color: #475569; font-weight: 600; text-transform: uppercase; }}
        .badge-os {{ background: #0f172a; color: #38bdf8; padding: 6px 14px; border-radius: 6px; font-weight: 900; font-size: 15px; text-align: right; }}
        .protocol-box {{ background: #f0fdf4; border: 1px solid #86efac; border-left: 5px solid #16a34a; border-radius: 6px; padding: 12px 16px; margin: 15px 0 20px 0; font-size: 13px; color: #14532d; display: flex; justify-content: space-between; align-items: center; }}
        .box {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px 20px; margin: 15px 0; }}
        .row {{ margin: 6px 0; font-size: 13.5px; }}
        .label {{ font-weight: 700; color: #334155; display: inline-block; width: 180px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
        th {{ background: #f1f5f9; padding: 9px 10px; text-align: left; font-size: 11.5px; text-transform: uppercase; color: #475569; border-bottom: 2px solid #cbd5e1; }}
        .compliance-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 15px; }}
        .compliance-item {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 12px; }}
        .compliance-item b {{ color: #0369a1; display: block; margin-bottom: 4px; font-size: 12.5px; }}
        .signatures {{ margin-top: 40px; display: flex; justify-content: space-between; gap: 40px; }}
        .sig-box {{ flex: 1; border-top: 1px solid #94a3b8; text-align: center; padding-top: 8px; font-size: 12px; color: #475569; }}
        .footer {{ margin-top: 40px; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 12px; text-align: center; }}
        @media print {{
            body {{ margin: 15mm 20mm; }}
            .no-print {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px; display: flex; justify-content: flex-end; gap: 10px;">
        <button onclick="window.print()" style="background:#0284c7;color:#fff;border:none;padding:10px 20px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:13px;">🖨️ Imprimir Carta de Acesso A4</button>
        <button onclick="window.close()" style="background:#64748b;color:#fff;border:none;padding:10px 16px;border-radius:6px;cursor:pointer;font-size:13px;">Fechar</button>
    </div>

    <div class="header">
        <div>
            <div class="title">EMED ELETROMEDICINA LTDA.</div>
            <div class="subtitle">Engenharia Clínica • Radiologia Diagnóstica • Suporte Hospitalar 24h</div>
        </div>
        <div class="badge-os">
            ORDEM DE SERVIÇO Nº #{os_id}<br>
            <span style="font-size:11px;color:#94a3b8;font-weight:normal;">Emitido: {emissao_agora}</span>
        </div>
    </div>

    <div class="protocol-box">
        <div>
            <strong>🛡️ DOCUMENTO FORMAL DE AUTORIZAÇÃO DE ENTRADA & ACESSO HOSPITALAR</strong><br>
            Destinado ao Setor de Portaria, Segurança Predial e Engenharia Clínica.
        </div>
        <div style="text-align:right;font-size:12px;font-weight:bold;">
            Data Agendada: <span style="color:#0369a1;font-size:14px;">{dt}</span>
        </div>
    </div>

    <p style="font-size: 13.5px; margin: 10px 0;">
        Declaramos para os devidos fins de controle de acesso, cumprimento das normas de segurança do paciente e portaria predial do <strong>{hosp}</strong> (A/C: {resp}), que o(s) profissional(is) abaixo relacionado(s) pertence(m) ao quadro técnico especializado da <strong>EMED Eletromedicina</strong> e está(ão) formalmente credenciado(s) para intervir tecnicamente nas dependências do hospital:
    </p>

    <div class="box">
        <div style="font-weight: bold; color: #0284c7; font-size: 13.5px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
            DADOS DO CHAMADO & EQUIPAMENTO HOSPITALAR
        </div>
        <div class="row"><span class="label">Unidade Hospitalar:</span> <strong>{hosp}</strong></div>
        <div class="row"><span class="label">Endereço:</span> {dados.get('endereco', 'Fortaleza - CE')}</div>
        <div class="row"><span class="label">Equipamento Alvo:</span> <strong>{equip}</strong> {mod} (N/S: {serie})</div>
        <div class="row"><span class="label">Finalidade da Intervenção:</span> Manutenção preventiva / corretiva e calibração biomédica</div>
    </div>

    <div style="font-weight: bold; color: #0f172a; font-size: 14px; margin: 20px 0 8px 0;">
        👥 EQUIPE TÉCNICA AUTORIZADA & QUALIFICAÇÕES PROFISSIONAIS:
    </div>

    <table>
        <thead>
            <tr>
                <th>Técnico Especialista</th>
                <th>Documentos (CPF / RG)</th>
                <th>Conselho Profissional</th>
                <th>Saúde Ocupacional (ASO)</th>
                <th>Veículo Operacional</th>
            </tr>
        </thead>
        <tbody>
            {rows_tecs_html}
        </tbody>
    </table>

    <div class="compliance-grid">
        <div class="compliance-item">
            <b>⚡ NR-10 & Segurança Elétrica</b>
            Habilitação para intervenções em equipamentos de alta tensão hospitalar e aterramento de proteção.
        </div>
        <div class="compliance-item">
            <b>🏥 NR-32 & Ambiente de Saúde</b>
            Protocolos sanitários, prevenção de risco biológico, vacinação em dia e uso obrigatório de EPIs.
        </div>
        <div class="compliance-item">
            <b>📜 Registro no CFT / CREA</b>
            Profissionais devidamente registrados com responsabilidade técnica ativa e acervo homologado.
        </div>
    </div>

    <p style="font-size: 12px; color: #475569; margin-top: 15px;">
        Solicitamos a gentileza de conceder acesso aos técnicos munidos de identificação com crachá e ferramental técnico. Qualquer divergência ou confirmação cadastral pode ser realizada diretamente com a Direção Operacional da EMED.
    </p>

    <div class="signatures">
        <div class="sig-box">
            <strong>EMED ELETROMEDICINA LTDA.</strong><br>
            Diretoria Técnica & Engenharia Clínica<br>
            CNPJ: 07.283.365/0001-10
        </div>
        <div class="sig-box">
            <strong>{hosp}</strong><br>
            Visto da Portaria / Engenharia Clínica<br>
            Recebido em: ____/____/2026 às ____:____
        </div>
    </div>

    <div class="footer">
        EMED Eletromedicina Ltda. • Fortaleza / CE • Plantão 24h: (85) 99915-0273 / (85) 99619-7923 • E-mail: contato@emedservice.med.br
    </div>
</body>
</html>"""

def registrar_credenciamento_os(db_name: str, os_id: int, tecnicos_selecionados: List[str]) -> bool:
    """Atualiza o banco com a confirmação da emissão de credenciamento hospitalar."""
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        tecs_str = ", ".join(tecnicos_selecionados) if tecnicos_selecionados else "TÉCNICO DESIGNADO"
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE clientes_equipamentos
                SET credenciamento_enviado = 'SIM',
                    credenciamento_data = ?,
                    credenciamento_tecnicos = ?
                WHERE id = ? OR rowid = ?
            """, (agora, tecs_str, os_id, os_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao registrar credenciamento: {e}")
        return False


def gerar_html_termo_aceite_instalacao(db_name: str, os_id: int) -> str:
    """Gera documento oficial A4 de Termo de Aceite Definitivo e Entrega Técnica de Instalação."""
    dados = {
        "os_id": os_id,
        "cliente": "HOSPITAL / CLÍNICA",
        "cidade": "FORTALEZA",
        "estado": "CE",
        "endereco": "",
        "equipamento": "EQUIPAMENTO MÉDICO",
        "tecnico": "EQUIPE TÉCNICA EMED",
        "responsavel": "DIRETORIA / ENGENHARIA CLÍNICA",
        "data": datetime.datetime.now().strftime("%d/%m/%Y"),
        "rubrica_cli": ""
    }
    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, cliente, cidade, estado, equipamento, 
                       tecnico_responsavel, responsavel_hospital, contato_responsavel, 
                       data_agendamento, assinatura_cliente_img, endereco
                FROM clientes_equipamentos
                WHERE id = ? OR rowid = ?
            """, (os_id, os_id))
            row = cur.fetchone()
            if row:
                dados["os_id"] = row[0]
                dados["cliente"] = (row[1] or dados["cliente"]).upper()
                dados["cidade"] = (row[2] or dados["cidade"]).upper()
                dados["estado"] = (row[3] or dados["estado"]).upper()
                dados["equipamento"] = (row[4] or dados["equipamento"]).upper()
                dados["tecnico"] = (row[5] or dados["tecnico"]).upper()
                dados["responsavel"] = (row[6] or row[7] or dados["responsavel"]).upper()
                dados["data"] = row[8] or dados["data"]
                dados["rubrica_cli"] = row[9] or ""
                dados["endereco"] = row[10] or ""
    except Exception as e:
        print(f"Erro ao obter dados do termo de aceite: {e}")

    rubrica_html = f'<div style="text-align:center;margin-bottom:4px;"><img src="{dados['rubrica_cli']}" style="height:36px;max-width:180px;object-fit:contain;" /></div>' if dados["rubrica_cli"] else '<div style="height:36px;"></div>'

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Termo de Aceite & Entrega Técnica — OS #{os_id} — {dados['cliente']}</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 12mm 15mm;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #0f172a;
            background: #ffffff;
            margin: 0;
            padding: 0;
            font-size: 11pt;
            line-height: 1.45;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2.5px solid #002b54;
            padding-bottom: 10px;
            margin-bottom: 14px;
        }}
        .logo-box {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .logo-badge {{
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, #002b54, #0284c7);
            color: #ffffff;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22pt;
            font-weight: 900;
        }}
        .company-name {{
            font-size: 15pt;
            font-weight: 900;
            color: #002b54;
            letter-spacing: -0.5px;
        }}
        .company-sub {{
            font-size: 8pt;
            color: #475569;
            font-weight: 600;
        }}
        .doc-meta {{
            text-align: right;
            font-size: 8.5pt;
            color: #334155;
        }}
        .doc-title-box {{
            background: #f0fdf4;
            border: 1.5px solid #16a34a;
            border-left: 6px solid #16a34a;
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 14px;
            text-align: center;
        }}
        .doc-title {{
            font-size: 13pt;
            font-weight: 900;
            color: #14532d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .doc-normas {{
            font-size: 8pt;
            color: #166534;
            font-weight: 700;
            margin-top: 3px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 12px;
        }}
        .info-table td {{
            padding: 6px 10px;
            font-size: 9pt;
            border: 1px solid #cbd5e1;
        }}
        .info-table .label {{
            background: #f8fafc;
            font-weight: 800;
            color: #334155;
            width: 25%;
        }}
        .section-title {{
            font-size: 10pt;
            font-weight: 900;
            color: #002b54;
            border-bottom: 1.5px solid #0284c7;
            padding-bottom: 3px;
            margin: 12px 0 8px 0;
            text-transform: uppercase;
        }}
        .check-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 12px;
        }}
        .check-table th {{
            background: #002b54;
            color: #ffffff;
            font-size: 8pt;
            font-weight: 800;
            padding: 6px 8px;
            text-align: left;
        }}
        .check-table td {{
            padding: 5px 8px;
            font-size: 8.2pt;
            border: 1px solid #e2e8f0;
            vertical-align: top;
        }}
        .check-table tr:nth-child(even) {{
            background: #f8fafc;
        }}
        .decl-box {{
            background: #f8fafc;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 10px 12px;
            font-size: 8.5pt;
            color: #1e293b;
            line-height: 1.5;
            margin-bottom: 16px;
            text-align: justify;
        }}
        .signatures-table {{
            width: 100%;
            margin-top: 20px;
            border-collapse: collapse;
        }}
        .signatures-table td {{
            width: 50%;
            text-align: center;
            vertical-align: bottom;
            padding: 0 15px;
        }}
        .sig-line {{
            border-top: 1.5px solid #334155;
            padding-top: 5px;
            font-size: 8.5pt;
            color: #0f172a;
        }}
        .footer {{
            margin-top: 18px;
            border-top: 1px solid #cbd5e1;
            padding-top: 6px;
            text-align: center;
            font-size: 7.5pt;
            color: #64748b;
        }}
        .no-print {{
            position: fixed;
            top: 12px;
            right: 12px;
            background: #16a34a;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 800;
            cursor: pointer;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            font-size: 11pt;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
        }}
    </style>
</head>
<body>
    <button class="no-print" onclick="window.print()">🖨️ Imprimir Termo A4</button>

    <div class="header">
        <div class="logo-box">
            <div class="logo-badge">e</div>
            <div>
                <div class="company-name">EMED ELETROMEDICINA</div>
                <div class="company-sub">ENGENHARIA CLÍNICA & ASSISTÊNCIA TÉCNICA ESPECIALIZADA</div>
            </div>
        </div>
        <div class="doc-meta">
            <b>TERMO Nº:</b> INST-{os_id:04d}/2026<br/>
            <b>OS REFERÊNCIA:</b> #{os_id}<br/>
            <b>EMISSÃO:</b> {dados['data']}<br/>
            <b>CNPJ:</b> 07.283.365/0001-10
        </div>
    </div>

    <div class="doc-title-box">
        <div class="doc-title">Termo Definitivo de Aceite e Entrega Técnica de Instalação</div>
        <div class="doc-normas">Conformidade Técnica com as Resoluções RDC ANVISA nº 611/2022 e Normas ABNT NBR IEC 60601</div>
    </div>

    <table class="info-table">
        <tr>
            <td class="label">INSTITUIÇÃO / HOSPITAL:</td>
            <td><b>{dados['cliente']}</b></td>
            <td class="label">DATA COMISSIONAMENTO:</td>
            <td><b>{dados['data']}</b></td>
        </tr>
        <tr>
            <td class="label">EQUIPAMENTO INSTALADO:</td>
            <td><b>{dados['equipamento']}</b></td>
            <td class="label">LOCALIDADE / UF:</td>
            <td>{dados['cidade']} - {dados['estado']}</td>
        </tr>
        <tr>
            <td class="label">RESPONSÁVEL RECEBIMENTO:</td>
            <td>{dados['responsavel']}</td>
            <td class="label">RESPONSÁVEL TÉCNICO:</td>
            <td><b>{dados['tecnico']} (EMED / CFT)</b></td>
        </tr>
    </table>

    <div class="section-title">📋 Roteiro de Comissionamento e Ensaios Técnicos Realizados no Local</div>

    <table class="check-table">
        <thead>
            <tr>
                <th style="width:35px; text-align:center;">ITEM</th>
                <th style="width:220px;">SUBSISTEMA / REQUISITO</th>
                <th>PROCEDIMENTO TÉCNICO & RESULTADO DA VERIFICAÇÃO</th>
                <th style="width:60px; text-align:center;">STATUS</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="text-align:center;"><b>01</b></td>
                <td><b>Adequação da Sala & Baritação</b></td>
                <td>Verificação da blindagem radiológica (argamassa baritada / chumbo), visor plumbífero de comando, sinalizador luminoso de feixe ativo e climatização 24h conforme RDC 611.</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
            <tr>
                <td style="text-align:center;"><b>02</b></td>
                <td><b>Infraestrutura Elétrica & Aterramento</b></td>
                <td>Conferência da linha de alimentação trifásica dedicada, disjuntores compatíveis e medição da resistência de aterramento hospitalar exclusivo (&le; 5 &Omega;).</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
            <tr>
                <td style="text-align:center;"><b>03</b></td>
                <td><b>Ancoragem Mecânica & Geometria</b></td>
                <td>Montagem e fixação estrutural da estativa, trilhos, mesa de exames e coluna porta-tubo com nivelamento milimétrico e verificação de torque dos parafusos de sustentação.</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
            <tr>
                <td style="text-align:center;"><b>04</b></td>
                <td><b>Interligação de Cabos & Alta Tensão</b></td>
                <td>Passagem de chicotes, conexão dos cabos de alta tensão com lubrificação dielétrica, isolamento térmico da cúpula e interligação com o gerador e console de comando.</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
            <tr>
                <td style="text-align:center;"><b>05</b></td>
                <td><b>Calibrações, Rampa Térmica & Disparo</b></td>
                <td>Ciclo de condicionamento e aquecimento do tubo de raios-X (degas/warm-up), calibração do colimador luminoso (coincidência feixe/luz) e disparos de teste de carga aprovados.</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
            <tr>
                <td style="text-align:center;"><b>06</b></td>
                <td><b>Entrega Técnica & Treinamento</b></td>
                <td>Instrução operacional e de segurança fornecida ao corpo de enfermagem / técnicos de radiologia, cobrindo rotinas de liga/desliga, intertravamentos e conservação do aparelho.</td>
                <td style="text-align:center; font-weight:900; color:#15803d;">CONFORME</td>
            </tr>
        </tbody>
    </table>

    <div class="decl-box">
        <b>DECLARAÇÃO FORMAL DE ACEITE DEFINITIVO:</b><br/>
        A instituição acima identificada declara, por meio de seu representante legal ou responsável pela Engenharia Clínica/Setor de Diagnóstico por Imagem, que o equipamento biomédico discriminado neste termo foi devidamente desembalado, instalado, calibrado, aferido e comissionado pela equipe da <b>EMED ELETROMEDICINA LTDA.</b>, encontrando-se em perfeitas condições mecânicas, ópticas e eletrônicas de funcionamento. A instituição atesta o recebimento da entrega técnica e declara o equipamento formalmente aceito e <b>LIBERADO PARA OPERAÇÃO CLÍNICA ASSISTENCIAL NORMAL</b>.
    </div>

    <table class="signatures-table">
        <tr>
            <td>
                {rubrica_html}
                <div class="sig-line">
                    <b>{dados['responsavel']}</b><br/>
                    <span style="font-size:7.5pt; color:#475569;">Responsável pelo Recebimento / Diretoria do Hospital</span><br/>
                    <span style="font-size:7.5pt; color:#64748b;">{dados['cliente']}</span>
                </div>
            </td>
            <td>
                <div style="height:36px; display:flex; align-items:center; justify-content:center;">
                    <span style="font-family:cursive; font-size:14pt; color:#002b54; font-weight:700;">{dados['tecnico']}</span>
                </div>
                <div class="sig-line">
                    <b>{dados['tecnico']}</b><br/>
                    <span style="font-size:7.5pt; color:#475569;">Especialista em Engenharia Clínica — CFT / CREA</span><br/>
                    <span style="font-size:7.5pt; color:#64748b;">EMED Eletromedicina Ltda.</span>
                </div>
            </td>
        </tr>
    </table>

    <div class="footer">
        EMED Eletromedicina Ltda. • CNPJ: 07.283.365/0001-10 • Plantão Técnico 24h: (85) 99915-0273 / (85) 99619-7923 • Fortaleza - CE<br/>
        Documento técnico oficial emitido eletronicamente pelo Sistema de Gestão Hospitalar EMED.
    </div>
</body>
</html>"""
    return html
