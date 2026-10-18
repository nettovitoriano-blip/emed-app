import datetime
import pandas as pd
import os
import urllib.parse

def gerar_mural():
    caminho_excel = "base_clientes.xlsx"
    if not os.path.exists(caminho_excel):
        print("⚠️ Ficheiro base_clientes.xlsx não encontrado!")
        return

    df = pd.read_excel(caminho_excel, engine='openpyxl')
    print(f"✅ Total de linhas no Excel: {len(df)}")

    hoje = pd.Timestamp.today().normalize()
    linhas_tabela = ""
    cards_pendencias = ""
    alertas_agenda = ""
    despachos_tecnicos = ""
    
    count_alertas = 0
    count_confirmados = 0
    tecnicos_agenda = {}

    for _, row in df.iterrows():
        cliente = str(row.get('cliente', '')).strip()
        cidade = str(row.get('cidade', '')).strip()
        estado = str(row.get('estado', '')).strip()
        equipamento = str(row.get('equipamento', '')).strip()
        
        # Leitura explícita das colunas novas
        endereco = str(row.get('endereco', '')).strip()
        if not endereco or endereco.lower() == 'nan':
            endereco = f"{cidade} - {estado}"

        resp_cliente = str(row.get('responsavel_hospital', '')).strip()
        if not resp_cliente or resp_cliente.lower() == 'nan':
            resp_cliente = "Não informado"

        tel_cliente = str(row.get('contato_responsavel', '')).strip()
        if tel_cliente.lower() == 'nan':
            tel_cliente = ""

        # Debug no terminal para ver se leu o endereço do São Carlos
        if "Carlos" in cliente:
            print(f"🔍 [DEBUG] Cliente: {cliente} | Endereço lido: {endereco} | Resp: {resp_cliente} ({tel_cliente})")

        # Tratamento de datas seguras
        raw_prev = row.get('ultima_preventiva', None)
        ultima_prev = pd.to_datetime(raw_prev, errors='coerce') if pd.notna(raw_prev) else pd.NaT
        if pd.notna(ultima_prev) and ultima_prev.year <= 1970:
            ultima_prev = pd.NaT

        raw_agend = row.get('data_agendamento', None)
        data_agend = pd.to_datetime(raw_agend, errors='coerce') if pd.notna(raw_agend) else pd.NaT
        if pd.isna(data_agend) and pd.notna(ultima_prev):
            data_agend = ultima_prev + pd.Timedelta(days=90)
        elif pd.isna(data_agend):
            data_agend = hoje

        tecnico_ult = str(row.get('tecnico_ultima', 'Equipe Emed')).strip()
        tecnico_resp = str(row.get('tecnico_responsavel', 'A definir')).strip()
        tel_tec = str(row.get('telefone_tecnico', '')).strip()
        confirmado = str(row.get('confirmado', 'Não')).strip()
        status = str(row.get('status', 'Em dia')).strip()
        pendencias = str(row.get('pendencias', '')).strip()
        observacoes = str(row.get('observacoes', '')).strip()

        # Links de navegação GPS
        query_mapa = urllib.parse.quote(f"{cliente} {endereco}")
        link_maps = f"https://www.google.com/maps/search/?api=1&query={query_mapa}"
        link_waze = f"https://waze.com/ul?q={query_mapa}&navigate=yes"

        dias_restantes = (data_agend.normalize() - hoje).days
        alerta_ativo = 0 <= dias_restantes <= 15
        if alerta_ativo:
            count_alertas += 1
            alertas_agenda += f"""
            <div class="alerta-item">
                <strong>📞 LIGAR PARA AGENDAMENTO: {cliente} ({cidade} - {estado})</strong>
                <p>Equipamento: {equipamento} | Data Limite: <strong>{data_agend.strftime('%d/%m/%Y')}</strong> (Faltam {dias_restantes} dias)</p>
                <div style="font-size: 11px; margin-top: 4px; color: #9a3412;">Técnico Responsável: {tecnico_resp} | Confirmado: <b>{confirmado}</b></div>
            </div>"""

        if confirmado.lower() in ["sim", "yes", "s"]:
            count_confirmados += 1
            if tecnico_resp not in tecnicos_agenda:
                tecnicos_agenda[tecnico_resp] = []
            tecnicos_agenda[tecnico_resp].append({
                'cliente': cliente, 'cidade': cidade, 'estado': estado, 
                'equipamento': equipamento, 'data': data_agend, 'pendencias': pendencias,
                'endereco': endereco, 'resp': resp_cliente, 'tel': tel_cliente,
                'maps': link_maps, 'waze': link_waze
            })

        tag_class = "corretiva" if "corretiva" in status.lower() else ("urgente" if alerta_ativo else "preventiva")
        prev_str = ultima_prev.strftime('%d/%m/%Y') if pd.notna(ultima_prev) else "-"
        agend_str = data_agend.strftime('%d/%m/%Y') if pd.notna(data_agend) else "-"

        linhas_tabela += f"""
        <tr>
            <td><strong>{cliente}</strong><br><small style="color:#64748b">End: {endereco}</small></td>
            <td>{cidade} - {estado}</td>
            <td>{equipamento}</td>
            <td>{prev_str}<br><small style="color:#475569">Por: {tecnico_ult}</small></td>
            <td><strong>{agend_str}</strong> {'<span class="tag urgente">⚠️ Ligar (15d)</span>' if alerta_ativo else ''}</td>
            <td>{tecnico_resp}<br><small>Resp: {resp_cliente} ({tel_cliente})</small></td>
            <td><span class="tag {'preventiva' if confirmado.lower()=='sim' else 'urgente'}">Conf: {confirmado}</span></td>
            <td><span class="tag {tag_class}">{status}</span></td>
        </tr>"""

        if pendencias and pendencias.lower() != "nan" and pendencias.lower() != "sem pendencias aparentes":
            cards_pendencias += f"""
            <div class="pendencia-item">
                <div class="pendencia-header">
                    <strong>{cliente}</strong> ({cidade} - {estado})
                    <span class="tag urgente">{equipamento}</span>
                </div>
                <p><strong>Peças / Substituições:</strong> {pendencias}</p>
                <div class="pendencia-footer">Técnico: {tecnico_resp}</div>
            </div>"""

    if not cards_pendencias:
        cards_pendencias = "<p style='color: #64748b; font-size: 14px;'>Nenhuma peça pendente registada.</p>"
    if not alertas_agenda:
        alertas_agenda = "<p style='color: #166534; font-size: 14px;'>Nenhum cliente precisando de ligação de agendamento nos próximos 15 dias.</p>"

    for tec, itens in tecnicos_agenda.items():
        texto_msg = f"Olá {tec}, aqui está o seu cronograma oficial de atendimentos EMED confirmados:\n\n"
        for i in itens:
            d_str = i['data'].strftime('%d/%m/%Y') if pd.notna(i['data']) else "-"
            texto_msg += f"🏥 Cliente: {i['cliente']} ({i['cidade']}-{i['estado']})\n"
            texto_msg += f"📍 Endereço: {i['endereco']}\n"
            texto_msg += f"👤 Responsável: {i['resp']} ({i['tel']})\n"
            texto_msg += f"⚙️ Equipamento: {i['equipamento']}\n"
            texto_msg += f"📅 Data Agendada: {d_str}\n"
            texto_msg += f"🗺️ Google Maps: {i['maps']}\n"
            texto_msg += f"🚗 Waze: {i['waze']}\n"
            if i['pendencias'] and i['pendencias'].lower() != "nan":
                texto_msg += f"⚠️ Pendências: {i['pendencias']}\n"
            texto_msg += f"-----------------------------------\n"
        
        encoded_msg = urllib.parse.quote(texto_msg)
        df_temp = df[df['tecnico_responsavel'] == tec]
        tel_raw = str(df_temp['telefone_tecnico'].values[0]) if 'telefone_tecnico' in df.columns and len(df_temp) > 0 else ""
        tel_limpo = ''.join(filter(str.isdigit, tel_raw))
        whatsapp_link = f"https://wa.me/{tel_limpo}?text={encoded_msg}" if tel_limpo else "#"

        despachos_tecnicos += f"""
        <div class="despacho-card">
            <h4>👷 Técnico: {tec} <span>({len(itens)} Atendimentos Confirmados)</span></h4>
            <ul>"""
        for i in itens:
            d_str = i['data'].strftime('%d/%m/%Y') if pd.notna(i['data']) else "-"
            despachos_tecnicos += f"""<li><b>{d_str}</b> — {i['cliente']} ({i['cidade']}) [{i['equipamento']}]<br>
                <small>📍 {i['endereco']}<br>👤 Resp: {i['resp']} ({i['tel']}) | 
                <a href="{i['maps']}" target="_blank">🗺️ Maps</a> | 
                <a href="{i['waze']}" target="_blank">🚗 Waze</a></small>
            </li><br>"""
        despachos_tecnicos += f"""
            </ul>
            <div style="margin-top: 12px;">
                {f'<a href="{whatsapp_link}" target="_blank" class="btn-zap">💬 Enviar Cronograma via WhatsApp</a>' if tel_limpo else '<small style="color: #dc2626;">⚠️ Telemóvel do técnico não preenchido</small>'}
            </div>
        </div>"""

    if not despachos_tecnicos:
        despachos_tecnicos = "<p style='color: #64748b; font-size: 14px;'>Nenhum agendamento confirmado com 'Sim' na planilha ainda.</p>"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>EMED - Sistema de Gestão de Preventivas e Corretivas</title>
    <style>
        :root {{ --primary: #0f172a; --accent: #0284c7; --success: #10b981; --warning: #f59e0b; --danger: #ef4444; --bg: #f8fafc; --card-bg: #ffffff; --text: #334155; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        body {{ background-color: var(--bg); color: var(--text); padding: 20px; }}
        header {{ display: flex; justify-content: space-between; align-items: center; background: var(--primary); color: white; padding: 15px 30px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .logo-area {{ display: flex; align-items: center; gap: 20px; }}
        .logo-area img {{ height: 65px; background: #ffffff; padding: 6px 12px; border-radius: 8px; box-shadow: 0 3px 6px rgba(0,0,0,0.25); object-fit: contain; }}
        header h1 {{ font-size: 22px; font-weight: 600; }}
        header .badge {{ background: var(--accent); padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: 600; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 25px; }}
        .stat-card {{ background: var(--card-bg); padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid var(--accent); display: flex; flex-direction: column; }}
        .stat-card.success {{ border-left-color: var(--success); }}
        .stat-card.warning {{ border-left-color: var(--warning); }}
        .stat-card.danger {{ border-left-color: var(--danger); }}
        .stat-card h3 {{ font-size: 12px; color: #64748b; margin-bottom: 8px; text-transform: uppercase; }}
        .stat-card .value {{ font-size: 24px; font-weight: 700; color: var(--primary); }}
        .main-container {{ display: grid; grid-template-columns: 2fr 1fr; gap: 25px; }}
        @media(max-width: 1024px) {{ .main-container {{ grid-template-columns: 1fr; }} }}
        .card {{ background: var(--card-bg); border-radius: 12px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 25px; }}
        .card h2 {{ font-size: 18px; color: var(--primary); margin-bottom: 20px; display: flex; align-items: center; gap: 10px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
        th, td {{ padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f8fafc; color: #475569; font-weight: 600; }}
        tr:hover {{ background: #f1f5f9; }}
        .tag {{ padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; display: inline-block; }}
        .tag.preventiva {{ background: #dbeafe; color: #1e40af; }}
        .tag.corretiva {{ background: #fee2e2; color: #991b1b; }}
        .tag.urgente {{ background: #fef3c7; color: #92400e; }}
        .alerta-item {{ background: #fff7ed; border: 1px solid #ffedd5; border-left: 4px solid var(--warning); border-radius: 8px; padding: 12px; margin-bottom: 10px; font-size: 13px; color: #9a3412; }}
        .pendencia-item {{ background: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid var(--warning); border-radius: 8px; padding: 12px; margin-bottom: 10px; }}
        .despacho-card {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid var(--success); border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
        .btn-zap {{ display: inline-block; background: #25d366; color: white; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; }}
        .cluster-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
        .cluster-box h4 {{ color: var(--accent); margin-bottom: 8px; font-size: 15px; }}
        .cluster-box ul {{ padding-left: 20px; font-size: 13px; color: #475569; }}
        .checklist-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px; margin-top: 12px; }}
        .checklist-box h5 {{ color: #166534; margin-bottom: 5px; font-size: 13px; }}
        .checklist-box ul {{ padding-left: 18px; font-size: 12px; color: #15803d; }}
    </style>
</head>
<body>
    <header>
        <div class="logo-area">
            <img src="emed1.jpg" alt="Logo EMED" onerror="this.style.display='none'">
            <h1>EMED Eletromedicina — Mural de Operações</h1>
        </div>
        <div class="badge">Despacho Inteligente de Campo</div>
    </header>

    <div class="stats-grid">
        <div class="stat-card"><h3>Total Equipamentos</h3><div class="value">{len(df)}</div></div>
        <div class="stat-card warning"><h3>⚠️ Alertas (15d)</h3><div class="value">{count_alertas}</div></div>
        <div class="stat-card success"><h3>✅ Confirmados</h3><div class="value">{count_confirmados}</div></div>
        <div class="stat-card" style="border-left-color: #f59e0b;"><h3>Com Pendências</h3><div class="value">{sum(1 for _, r in df.iterrows() if pd.notna(r.get('pendencias')) and str(r.get('pendencias')) != 'nan' and str(r.get('pendencias')) != 'sem pendencias aparentes')}</div></div>
    </div>

    <div class="main-container">
        <div>
            <div class="card" style="border-top: 4px solid var(--success);">
                <h2>💬 Despacho de Cronogramas via WhatsApp para Técnicos</h2>
                {despachos_tecnicos}
            </div>
            <div class="card" style="border-top: 4px solid var(--warning);">
                <h2>⏰ Central de Alertas (Ligar para Agendamento - 15 dias)</h2>
                {alertas_agenda}
            </div>
            <div class="card" style="border-top: 4px solid var(--warning);">
                <h2>⚠️ Peças e Substituições Pendentes</h2>
                {cards_pendencias}
            </div>
            <div class="card">
                <h2>📋 Carteira de Equipamentos & Histórico Técnico</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Cliente / Obs</th>
                            <th>Cidade/UF</th>
                            <th>Equipamento</th>
                            <th>Última Prev. / Técnico</th>
                            <th>Data Agendamento</th>
                            <th>Resp. / Contato</th>
                            <th>Conf.</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {linhas_tabela}
                    </tbody>
                </table>
            </div>
        </div>

        <div>
            <div class="card">
                <h2>🗺️ Clusters e Logística de Viagem</h2>
                <div class="cluster-box">
                    <h4>📍 Fortaleza - CE</h4>
                    <ul><li>Hospitais e Clínicas da Capital</li></ul>
                    <div class="checklist-box">
                        <h5>🛠️ Kit Técnico Base:</h5>
                        <ul><li>Multímetro True RMS e Osciloscópio</li><li>Fusíveis de gerador e filtros de ar</li></ul>
                    </div>
                </div>
                <div class="cluster-box">
                    <h4>📍 Juazeiro do Norte - CE</h4>
                    <ul><li>Atendimento regional sul</li></ul>
                    <div class="checklist-box">
                        <h5>🛠️ Kit Técnico Base:</h5>
                        <ul><li>Nível digital e placa de teste</li></ul>
                    </div>
                </div>
                <div class="cluster-box">
                    <h4>📍 Araripina - PE</h4>
                    <ul><li>Atendimento regional oeste (Corretivas)</li></ul>
                    <div class="checklist-box">
                        <h5>🛠️ Kit Corretivo:</h5>
                        <ul><li>Osciloscópio portátil para alta tensão</li></ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

    with open("dashboard_emed.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✨ Mural HTML gerado com sucesso com os endereços e GPS!")

if __name__ == "__main__":
    gerar_mural()