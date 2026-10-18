import json


def gerar_html_coletor_offline(df_base, equipa_dict, os_especifica=None):
    mapa_clientes = {}
    for _, r in df_base.iterrows():
        cli = str(r.get('cliente', '')).strip().upper()
        if not cli:
            continue
        if cli not in mapa_clientes:
            mapa_clientes[cli] = {
                "cidade": str(r.get('cidade', '')).strip().upper(),
                "estado": str(r.get('estado', '')).strip().upper(),
                "endereco": str(r.get('endereco', '')).strip().upper(),
                "equipamentos": []
            }
        eq = str(r.get('equipamento', '')).strip().upper()
        if eq and eq not in mapa_clientes[cli]["equipamentos"]:
            mapa_clientes[cli]["equipamentos"].append(eq)

    mapa_rubricas_tecs = {
        k: v.get("assinatura", f"{k} - CFT")
        for k, v in equipa_dict.items()
    }
    lista_tecs = list(equipa_dict.keys())
    dados_os_pre = os_especifica if os_especifica else {}

    html_code = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EMED - Coletor de OS Offline Modular</title>
    <style>
        * {{ box-sizing: border-box; font-family: Arial, sans-serif; }}
        body {{ background-color: #0b132b; color: #ffffff; margin: 0; padding: 15px; }}
        .container {{
            max-width: 680px; margin: 0 auto; background: #1c2541;
            padding: 20px; border-radius: 12px; border: 1px solid #3a506b;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        }}
        h2 {{ color: #64dfdf; text-align: center; margin-top: 0; }}
        .sec-title {{
            background: #0b132b; color: #64dfdf; padding: 8px 12px;
            border-left: 4px solid #64dfdf; border-radius: 6px;
            font-weight: bold; margin-top: 18px; font-size: 14px;
        }}
        .badge-offline {{
            background: #f59e0b; color: #000; font-weight: bold;
            padding: 4px 10px; border-radius: 20px; font-size: 12px;
            display: inline-block; margin-bottom: 15px;
        }}
        label {{ display: block; margin-top: 10px; font-weight: bold; color: #cbd5e1; font-size: 13px; }}
        input[type="text"], select, textarea {{
            width: 100%; padding: 10px; margin-top: 5px;
            background: #0b132b; color: #fff; border: 1px solid #3a506b;
            border-radius: 8px; font-size: 14px; text-transform: uppercase;
        }}
        .btn-row {{ display: flex; gap: 10px; margin-top: 12px; }}
        button {{ flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer; }}
        .btn-checkin {{ background: #3a506b; color: #64dfdf; border: 1px solid #64dfdf; }}
        .btn-save {{ background: #10b981; color: #0b132b; width: 100%; margin-top: 20px; font-size: 16px; padding: 15px; }}
        .stamp-box {{
            background: #0b132b; border: 1px dashed #64dfdf; border-radius: 8px;
            padding: 10px; text-align: center; margin-top: 8px; color: #64dfdf;
        }}
        canvas {{
            width: 100%; height: 150px; background: #0b132b;
            border: 1.5px dashed #64dfdf; border-radius: 8px;
            touch-action: none; margin-top: 6px;
        }}
    </style>
</head>
<body>
<div class="container">
    <div style="text-align:center;"><span class="badge-offline">📴 MODO CAMPO 100% OFFLINE MODULAR</span></div>
    <h2>🏥 EMED - Ordem de Serviço</h2>
    <input type="hidden" id="os_id" value="{dados_os_pre.get('os_id', '')}">

    <div class="sec-title">1. IDENTIFICAÇÃO & TEMPOS</div>
    <label>Técnico Responsável *</label><select id="tecnico" onchange="atualizarRubricaTec()"></select>
    <div class="stamp-box" id="carimbo_tec">✅ Rubrica Técnica Pré-Salva</div>
    <label>Hospital / Unidade *</label><select id="cliente" onchange="atualizarEquipamentos()"></select>
    <label>Equipamento *</label><select id="equipamento"></select>
    <div class="btn-row">
        <button type="button" class="btn-checkin" onclick="marcarHora('checkin')">📍 Marcar Check-in</button>
        <button type="button" class="btn-checkin" onclick="marcarHora('checkout')">🏁 Marcar Check-out</button>
    </div>
    <div class="btn-row">
        <input type="text" id="checkin" placeholder="Início" readonly>
        <input type="text" id="checkout" placeholder="Fim" readonly>
    </div>

    <div class="sec-title">2. DEFEITO RELATADO & PROBLEMAS ENCONTRADOS</div>
    <label>Condição Inicial na Chegada</label>
    <select id="condicao_inicial">
        <option value="OPERACIONAL">OPERACIONAL</option>
        <option value="OPERANDO COM RESTRIÇÃO">OPERANDO COM RESTRIÇÃO</option>
        <option value="PARADO / INOPERANTE">PARADO / INOPERANTE</option>
    </select>
    <label>Defeito Relatado pelo Cliente</label><input type="text" id="defeito_relatado" placeholder="Ex: Aparelho não dispara / erro no painel">
    <label>Problemas Encontrados / Diagnóstico Técnico *</label><textarea id="problemas_encontrados" rows="2"></textarea>
    <label>Parâmetros / Medições (Tensão F-N, Terra, Temp. Sala)</label><input type="text" id="parametros_medidos" placeholder="Ex: 220V F-N | 0.8V T-N | 21°C">

    <div class="sec-title">3. SERVIÇO EXECUTADO, PENDÊNCIAS & OBSERVAÇÕES</div>
    <label>Serviço Executado / Solução Aplicada *</label><textarea id="relatorio" rows="3"></textarea>
    <label>Status Final do Atendimento *</label>
    <select id="status_os">
        <option value="CONCLUÍDO">CONCLUÍDO (EQUIPAMENTO LIBERADO)</option>
        <option value="ATIVO">ATIVO / COM PENDÊNCIA ABERTA</option>
    </select>
    <label>Observações Gerais & Recomendações ao Hospital</label><input type="text" id="observacoes_gerais">
    <label>Instrumento / Peça Necessária p/ Próxima Visita (se pendente)</label><input type="text" id="instrumento">

    <div class="sec-title">4. ASSINATURA DO CLIENTE NA TELA DO CELULAR</div>
    <label>Nome e Cargo do Responsável no Hospital *</label><input type="text" id="assinatura_cliente" placeholder="EX: DR. CARLOS - RADIOLOGIA">
    <label>Rubrica do Cliente (Assine com o dedo abaixo) *</label>
    <canvas id="sig_canvas" width="500" height="150"></canvas>
    <div class="btn-row">
        <button type="button" class="btn-checkin" onclick="limparAssinatura()">🧹 Limpar Assinatura</button>
    </div>

    <button type="button" class="btn-save" onclick="exportarOS()">💾 GUARDAR E BAIXAR OS COMPLETA (.JSON)</button>
</div>
<script>
    const clientesDB = {json.dumps(mapa_clientes, ensure_ascii=False)};
    const tecnicosDB = {json.dumps(lista_tecs, ensure_ascii=False)};
    const rubricasDB = {json.dumps(mapa_rubricas_tecs, ensure_ascii=False)};
    const canvas = document.getElementById('sig_canvas');
    const ctx = canvas.getContext('2d');
    let desenhando = false;
    let assinou = false;

    function configurarCanvas() {{
        ctx.strokeStyle = '#64dfdf';
        ctx.lineWidth = 2.5;
        ctx.lineCap = 'round';
        const pos = (e) => {{
            const r = canvas.getBoundingClientRect();
            const cx = e.touches ? e.touches[0].clientX : e.clientX;
            const cy = e.touches ? e.touches[0].clientY : e.clientY;
            return {{ x: (cx - r.left) * (canvas.width / r.width), y: (cy - r.top) * (canvas.height / r.height) }};
        }};
        const ini = (e) => {{ e.preventDefault(); desenhando = true; assinou = true; const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); }};
        const mov = (e) => {{ if(!desenhando) return; e.preventDefault(); const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); }};
        const fim = (e) => {{ desenhando = false; }};
        canvas.addEventListener('mousedown', ini); canvas.addEventListener('mousemove', mov); window.addEventListener('mouseup', fim);
        canvas.addEventListener('touchstart', ini, {{passive:false}}); canvas.addEventListener('touchmove', mov, {{passive:false}}); canvas.addEventListener('touchend', fim);
    }}
    function limparAssinatura() {{ ctx.clearRect(0, 0, canvas.width, canvas.height); assinou = false; }}
    function atualizarRubricaTec() {{
        const t = document.getElementById('tecnico').value;
        document.getElementById('carimbo_tec').innerHTML = "✅ Rubrica Pré-Salva do Técnico: <strong>" + (rubricasDB[t] || t) + "</strong>";
    }}
    function inicializar() {{
        const selTec = document.getElementById('tecnico');
        tecnicosDB.forEach(t => {{
            let o = document.createElement('option');
            o.value = t;
            o.textContent = t;
            selTec.appendChild(o);
        }});
        const selCli = document.getElementById('cliente');
        Object.keys(clientesDB).sort().forEach(c => {{
            let o = document.createElement('option');
            o.value = c;
            o.textContent = c;
            selCli.appendChild(o);
        }});
        atualizarEquipamentos();
        atualizarRubricaTec();
        configurarCanvas();
    }}
    function atualizarEquipamentos() {{
        const cli = document.getElementById('cliente').value;
        const selEq = document.getElementById('equipamento');
        selEq.innerHTML = "";
        if (clientesDB[cli] && clientesDB[cli].equipamentos) {{
            clientesDB[cli].equipamentos.forEach(eq => {{
                let o = document.createElement('option');
                o.value = eq;
                o.textContent = eq;
                selEq.appendChild(o);
            }});
        }}
    }}
    function marcarHora(campo) {{
        document.getElementById(campo).value = new Date().toLocaleString('pt-BR');
    }}
    function exportarOS() {{
        const cli = document.getElementById('cliente').value;
        const rel = document.getElementById('relatorio').value.trim().toUpperCase();
        const assCli = document.getElementById('assinatura_cliente').value.trim().toUpperCase();
        if(!rel || !assCli) {{
            alert("Preencha o Serviço Executado e o Nome do Responsável no Hospital!");
            return;
        }}
        const tecSel = document.getElementById('tecnico').value;
        const dados = {{
            os_id: document.getElementById('os_id').value,
            tecnico: tecSel,
            cliente: cli,
            equipamento: document.getElementById('equipamento').value,
            checkin_hora: document.getElementById('checkin').value,
            checkout_hora: document.getElementById('checkout').value,
            condicao_inicial: document.getElementById('condicao_inicial').value,
            defeito_relatado: document.getElementById('defeito_relatado').value.trim().toUpperCase(),
            problemas_encontrados: document.getElementById('problemas_encontrados').value.trim().toUpperCase(),
            parametros_medidos: document.getElementById('parametros_medidos').value.trim().toUpperCase(),
            servico_executado: rel,
            observacoes_gerais: document.getElementById('observacoes_gerais').value.trim().toUpperCase(),
            status: document.getElementById('status_os').value,
            relatorio: rel,
            instrumento_necessario: document.getElementById('instrumento').value.trim().toUpperCase(),
            assinatura_cliente: assCli,
            assinatura_cliente_img: assinou ? canvas.toDataURL('image/png') : "",
            assinatura_tecnico: rubricasDB[tecSel] || tecSel,
            data_sincronizacao: new Date().toLocaleString('pt-BR')
        }};
        const blob = new Blob([JSON.stringify(dados, null, 2)], {{type: "application/json"}});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = "OS_OFFLINE_" + cli.replace(/[^a-zA-Z0-9]/g, '_') + ".json";
        a.click();
    }}
    window.onload = inicializar;
</script>
</body>
</html>"""
    return html_code
