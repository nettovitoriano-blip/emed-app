# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Gerador de Cartão de Visita Digital Executivo do Técnico
Renderiza crachá digital interativo com QR Code, botão de Salvar Contato (vCard .vcf),
ligação e WhatsApp direto com identidade corporativa de alta credibilidade hospitalar.
"""

import io
import base64
import qrcode
from typing import Dict, Any, Optional

def gerar_vcard_texto(
    nome: str,
    cargo: str,
    telefone: str,
    email: str = "contato@emed.med.br",
    empresa: str = "EMED Eletromedicina Ltda.",
    site: str = "https://emed.med.br",
    cidade: str = "Fortaleza / CE"
) -> str:
    tel_limpo = "".join([c for c in telefone if c.isdigit() or c == '+'])
    if not tel_limpo.startswith("+") and len(tel_limpo) >= 10:
        tel_limpo = f"+55{tel_limpo}"

    vcard = (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        f"FN:{nome} - EMED Hospitalar\r\n"
        f"N:{nome};;;;\r\n"
        f"ORG:{empresa}\r\n"
        f"TITLE:{cargo}\r\n"
        f"TEL;TYPE=CELL,VOICE:{tel_limpo}\r\n"
        f"EMAIL;TYPE=WORK,INTERNET:{email}\r\n"
        f"URL:{site}\r\n"
        f"ADR;TYPE=WORK:;;Fortaleza;CE;;Brasil\r\n"
        f"NOTE:Engenharia Clínica e Manutenção Hospitalar Especializada - Suporte EMED\r\n"
        "END:VCARD\r\n"
    )
    return vcard

def gerar_qrcode_base64_vcard(conteudo: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#03045e", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def render_cartao_html(dados_tecnico: Dict[str, Any], qr_b64: str) -> str:
    import urllib.parse
    nome = dados_tecnico.get("nome", "Técnico Especialista")
    cargo = dados_tecnico.get("cargo", "Engenheiro / Técnico Clínico")
    telefone = dados_tecnico.get("telefone", "(85) 99999-9999")
    email = dados_tecnico.get("email", "suporte@emed.med.br")
    registro = dados_tecnico.get("registro_profissional", "CFT/CREA Ativo")
    especialidades = dados_tecnico.get("especialidades", "Diagnóstico por Imagem • Centro Cirúrgico • UTI")
    tel_link = "".join([c for c in telefone if c.isdigit()])
    nome_sanitizado = "".join([c for c in nome if c.isalnum() or c in (" ", "_")]).strip().replace(" ", "_")
    vcard_raw = gerar_vcard_texto(nome, cargo, telefone, email)
    vcard_encoded_placeholder = urllib.parse.quote(vcard_raw)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cartão Digital - {nome} | EMED Hospitalar</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0b132b 0%, #1c2541 50%, #0f172a 100%);
            color: #f8fafc;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }}
        .card {{
            background: #1e293b;
            border: 1.5px solid #00b4d8;
            border-radius: 20px;
            width: 100%;
            max-width: 420px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
            text-align: center;
        }}
        .header-banner {{
            background: linear-gradient(135deg, #0077b6 0%, #00b4d8 100%);
            padding: 25px 20px 50px 20px;
            position: relative;
        }}
        .logo-txt {{
            font-size: 22px;
            font-weight: 900;
            letter-spacing: 1.5px;
            color: #ffffff;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        .sub-logo {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #e0f2fe;
            margin-top: 3px;
            font-weight: 600;
        }}
        .avatar-wrap {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            border: 4px solid #1e293b;
            background: #0f172a;
            margin: -50px auto 12px auto;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.4);
        }}
        .badge-verified {{
            position: absolute;
            bottom: 2px;
            right: 2px;
            background: #10b981;
            color: white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            font-size: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #1e293b;
        }}
        .nome {{ font-size: 20px; font-weight: 800; color: #f8fafc; margin-bottom: 4px; }}
        .cargo {{ font-size: 13.5px; color: #38bdf8; font-weight: 600; margin-bottom: 6px; }}
        .reg {{ font-size: 11.5px; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 4px 12px; border-radius: 20px; display: inline-block; margin-bottom: 16px; }}
        .especialidades {{ font-size: 12px; color: #cbd5e1; padding: 0 24px; line-height: 1.5; margin-bottom: 20px; }}
        .actions {{ padding: 0 24px 20px 24px; display: flex; flex-direction: column; gap: 10px; }}
        .btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 13px 20px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 700;
            font-size: 14px;
            transition: all 0.2s;
            border: none;
            cursor: pointer;
        }}
        .btn-salvar {{ background: #00b4d8; color: #03045e; }}
        .btn-salvar:hover {{ background: #48cae4; }}
        .btn-wa {{ background: #22c55e; color: #ffffff; }}
        .btn-wa:hover {{ background: #16a34a; }}
        .btn-tel {{ background: rgba(255,255,255,0.1); color: #f8fafc; border: 1px solid rgba(255,255,255,0.2); }}
        .btn-tel:hover {{ background: rgba(255,255,255,0.15); }}
        .qr-section {{
            background: #0f172a;
            border-top: 1px solid #334155;
            padding: 18px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .qr-img {{ width: 75px; height: 75px; border-radius: 8px; border: 2px solid #00b4d8; }}
        .qr-info {{ text-align: left; font-size: 11.5px; color: #94a3b8; line-height: 1.4; }}
        .qr-info strong {{ color: #e2e8f0; font-size: 12.5px; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header-banner">
            <div class="logo-txt">EMED HOSPITALAR</div>
            <div class="sub-logo">Engenharia Clínica Especializada</div>
        </div>
        <div class="avatar-wrap">
            👨‍⚕️
            <div class="badge-verified">✓</div>
        </div>
        <div class="nome">{nome}</div>
        <div class="cargo">{cargo}</div>
        <div class="reg">{registro}</div>
        <div class="especialidades">{especialidades}</div>

        <div class="actions">
            <a href="data:text/vcard;charset=utf-8,{vcard_encoded_placeholder}" download="{nome_sanitizado}_EMED.vcf" class="btn btn-salvar">
                📲 Salvar Contato na Agenda
            </a>
            <a href="https://wa.me/55{tel_link}?text=Ol%C3%A1%20{nome}%2C%20estou%20entrando%20em%20contato%20atrav%C3%A9s%20do%20seu%20Cart%C3%A3o%20Digital%20EMED." target="_blank" class="btn btn-wa">
                💬 Conversar no WhatsApp
            </a>
            <a href="tel:{tel_link}" class="btn btn-tel">
                📞 Ligar: {telefone}
            </a>
        </div>

        <div class="qr-section">
            <div class="qr-info">
                <strong>Credencial Técnica Oficial</strong><br>
                Apresente na portaria hospitalar para validação de acesso.
            </div>
            <img class="qr-img" src="data:image/png;base64,{qr_b64}" alt="QR Code">
        </div>
    </div>
</body>
</html>"""
