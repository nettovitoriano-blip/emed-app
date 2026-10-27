# emed_services/pdf_engine.py
# Motor Biomédico de Geração de PDFs Homologados, Laudos Técnicos e Vinculação de ITs
import os
import re
import urllib.parse
import pymupdf
import pandas as pd


def clean_latex(text: str) -> str:
    """Substitui sintaxes LaTeX brutas por caracteres Unicode limpos."""
    replacements = [
        (r'\\le\b', '≤'),
        (r'\\ge\b', '≥'),
        (r'\\pm\b', '±'),
        (r'\\times\b', '×'),
        (r'\\cdot\b', '·'),
        (r'\\Omega\b', 'Ω'),
        (r'\\mu\b', 'µ'),
        (r'\\sigma\b', 'σ'),
        (r'\\circ\b', '°'),
        (r'\\approx\b', '≈'),
        (r'\\%', '%'),
        (r'\^2\b', '²'),
        (r'\^3\b', '³'),
        (r'\\text\{([^}]*)\}', r'\1'),
        (r'\\\s+', ' '),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    # Remove delimitadores de inline math $...$
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    text = text.replace(r'\%', '%').replace(r'\_', '_').replace(r'\$', '$').replace(r'\ ', ' ')
    return text


def markdown_to_html(md_text: str, doc_title: str = "Instrução de Trabalho eMED") -> str:
    """Converte Markdown estruturado de Engenharia Clínica para HTML A4 timbrado e estilizado."""
    css = """
    <style>
        @page {
            size: A4;
            margin: 22mm 18mm 22mm 18mm;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            line-height: 1.5;
            font-size: 9.5pt;
        }
        .header-box {
            border-bottom: 2.5px solid #0077b6;
            padding-bottom: 8px;
            margin-bottom: 16px;
        }
        .header-title {
            color: #0077b6;
            font-size: 15pt;
            font-weight: bold;
            margin: 0;
            line-height: 1.25;
        }
        .header-sub {
            color: #64748b;
            font-size: 8.5pt;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        h1 {
            color: #0f172a;
            font-size: 12.5pt;
            border-bottom: 1.5px solid #cbd5e1;
            padding-bottom: 4px;
            margin-top: 16px;
            margin-bottom: 6px;
        }
        h2 {
            color: #0369a1;
            font-size: 11pt;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 3px;
            margin-top: 12px;
            margin-bottom: 5px;
        }
        h3 {
            color: #0284c7;
            font-size: 9.5pt;
            margin-top: 10px;
            margin-bottom: 4px;
        }
        p {
            margin: 4px 0 5px 0;
        }
        ul, ol {
            margin: 4px 0 6px 18px;
            padding-left: 0;
        }
        li {
            margin-bottom: 2px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 8.5pt;
        }
        th {
            background-color: #0284c7;
            color: white;
            border: 1px solid #0284c7;
            padding: 5px 7px;
            text-align: left;
            font-weight: bold;
        }
        td {
            border: 1px solid #cbd5e1;
            padding: 4px 6px;
        }
        tr:nth-child(even) td {
            background-color: #f8fafc;
        }
        .alert-box {
            background-color: #fef2f2;
            border-left: 4px solid #ef4444;
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 8.5pt;
        }
        .alert-title {
            color: #b91c1c;
            font-weight: bold;
            font-size: 9.5pt;
            margin-bottom: 4px;
        }
        .info-box {
            background-color: #f0f9ff;
            border-left: 4px solid #0284c7;
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 8.5pt;
        }
        .info-title {
            color: #0369a1;
            font-weight: bold;
            font-size: 9.5pt;
            margin-bottom: 4px;
        }
        code {
            background-color: #f1f5f9;
            color: #0f172a;
            padding: 1px 4px;
            border-radius: 3px;
            font-family: Consolas, monospace;
            font-size: 8.5pt;
        }
        .footer-note {
            margin-top: 24px;
            border-top: 1px solid #cbd5e1;
            padding-top: 6px;
            font-size: 7.5pt;
            color: #94a3b8;
            text-align: center;
        }
    </style>
    """

    import base64
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    logo_html = ""
    for nome_logo, mime in [("emed_svg-1.png", "image/png"), ("emed1.jpg", "image/jpeg"), ("logo_emed.png", "image/png")]:
        p_logo = os.path.join(base_dir, nome_logo)
        if os.path.exists(p_logo):
            try:
                with open(p_logo, "rb") as fl:
                    b64_logo = base64.b64encode(fl.read()).decode("utf-8")
                logo_html = f"<img src='data:{mime};base64,{b64_logo}' style='height:46px; max-width:135px; object-fit:contain;' />"
                break
            except Exception:
                pass

    if not logo_html:
        logo_html = "<div style='font-size:16pt; font-weight:900; color:#0077b6;'>🏥 eMED</div>"

    # Extrai o código da IT se presente no doc_title ou no markdown
    m_cod = re.search(r'(IT[_-][A-Z0-9_-]+)', doc_title, re.IGNORECASE)
    cod_doc = m_cod.group(1).replace("_", "-").upper() if m_cod else "POP/IT-EMED"
    if cod_doc.startswith("IT-") and len(cod_doc.split("-")) == 2 and cod_doc.split("-")[1].isdigit():
        cod_doc = f"IT-TOMO-GE-{int(cod_doc.split('-')[1]):03d}"

    doc_title_display = doc_title.replace("_", " ").strip()
    for l in md_text.splitlines()[:5]:
        if l.strip().startswith("# "):
            doc_title_display = l.strip().lstrip("#").strip()
            break

    body_html = [
        "<div class='header-box' style='border-bottom: 2.5px solid #0077b6; padding-bottom: 8px; margin-bottom: 14px;'>",
        "<table style='width:100%; border:none; margin:0; border-collapse:collapse; table-layout:fixed;'>",
        "<tr style='background:transparent;'>",
        f"<td style='border:none; width:120px; vertical-align:middle; padding:0 6px 0 0;'>{logo_html}</td>",
        "<td style='border:none; vertical-align:middle; padding:0 8px; overflow:hidden;'>",
        "<div style='font-size:10pt; font-weight:800; color:#0b132b; letter-spacing:0.3px;'>EMED ELETROMEDICINA LTDA.</div>",
        "<div style='font-size:7pt; color:#64748b; font-weight:600;'>ENGENHARIA CLÍNICA • DIAGNÓSTICO POR IMAGEM • CNPJ: 03.611.974/0001-08</div>",
        f"<div class='header-title' style='color:#0077b6; font-size:10pt; font-weight:bold; margin-top:2px; line-height:1.25;'>{clean_latex(doc_title_display)}</div>",
        "</td>",
        "<td style='border:none; width:155px; vertical-align:middle; text-align:right; padding:0;'>",
        "<div style='background:#f8fafc; border:1.2px solid #0077b6; border-radius:4px; padding:3px 6px; text-align:left; font-size:7pt; line-height:1.25;'>",
        f"<b>CÓDIGO:</b> <span style='color:#0077b6; font-weight:bold;'>{cod_doc}</span><br/>",
        "<b>VERSÃO:</b> <span style='color:#0284c7; font-weight:bold;'>2.4 Homologada</span><br/>",
        "<b>REVISÃO:</b> Rev. 02 | 26/10/2026<br/>",
        "<b>NORMA:</b> ANVISA RDC 611",
        "</div>",
        "</td>",
        "</tr></table>",
        "</div>"
    ]

    raw_lines = md_text.splitlines()
    in_table = False
    table_html = []
    in_alert = False
    alert_type = "info"
    alert_lines = []

    # Ignora metadados iniciais (H1, tabela de versão, réguas) pois o cabeçalho PDF oficial já os renderiza
    idx_content_start = 0
    ignoring_top_meta = True
    for idx_line, line in enumerate(raw_lines):
        s_test = line.strip()
        if ignoring_top_meta:
            if s_test.startswith("# ") or s_test.startswith("|") or s_test.startswith("---") or s_test == "":
                continue
            else:
                idx_content_start = idx_line
                ignoring_top_meta = False
                break

    lines = raw_lines[idx_content_start:]

    for line in lines:
        s = line.strip()

        # Alertas do estilo GitHub
        if s.startswith("> [!WARNING]") or s.startswith("> [!CAUTION]"):
            if in_alert:
                box_class = "alert-box" if alert_type == "caution" else "info-box"
                body_html.append(f"<div class='{box_class}'>{''.join(alert_lines)}</div>")
            in_alert = True
            alert_type = "caution"
            alert_lines = ["<div class='alert-title'>⚠️ AVISO DE SEGURANÇA E PROTEÇÃO RADIOLÓGICA</div>"]
            continue
        elif s.startswith("> [!IMPORTANT]") or s.startswith("> [!NOTE]") or s.startswith("> [!TIP]"):
            if in_alert:
                box_class = "alert-box" if alert_type == "caution" else "info-box"
                body_html.append(f"<div class='{box_class}'>{''.join(alert_lines)}</div>")
            in_alert = True
            alert_type = "info"
            alert_lines = ["<div class='info-title'>ℹ️ NOTA TÉCNICA BIOMÉDICA</div>"]
            continue

        if in_alert:
            if s.startswith(">"):
                content = clean_latex(s[1:].strip())
                content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)
                content = re.sub(r'\*(.*?)\*', r'<i>\1</i>', content)
                content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)
                alert_lines.append(f"<p>{content}</p>")
                continue
            else:
                box_class = "alert-box" if alert_type == "caution" else "info-box"
                body_html.append(f"<div class='{box_class}'>{''.join(alert_lines)}</div>")
                in_alert = False
                alert_lines = []

        # Tabelas Markdown
        if s.startswith("|") and s.endswith("|"):
            cells = [clean_latex(c.strip()) for c in s.split("|")[1:-1]]
            if re.match(r'^[\s:-|]+$', s):
                continue
            if not in_table:
                in_table = True
                table_html = ["<table><thead><tr>"]
                for cell in cells:
                    cell_fmt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', cell)
                    table_html.append(f"<th>{cell_fmt}</th>")
                table_html.append("</tr></thead><tbody>")
            else:
                table_html.append("<tr>")
                for cell in cells:
                    cell_fmt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', cell)
                    cell_fmt = re.sub(r'\*(.*?)\*', r'<i>\1</i>', cell_fmt)
                    cell_fmt = re.sub(r'`(.*?)`', r'<code>\1</code>', cell_fmt)
                    table_html.append(f"<td>{cell_fmt}</td>")
                table_html.append("</tr>")
            continue
        else:
            if in_table:
                table_html.append("</tbody></table>")
                body_html.append("".join(table_html))
                in_table = False
                table_html = []

        if not s:
            continue

        s = clean_latex(s)
        if s.startswith("### "):
            body_html.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            body_html.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            body_html.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("- [ ] "):
            txt = s[6:]
            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
            body_html.append(f"<p style='margin-left: 14px;'>☐ {txt}</p>")
        elif s.startswith("- [x] ") or s.startswith("- [X] "):
            txt = s[6:]
            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
            body_html.append(f"<p style='margin-left: 14px;'>☑ <b>{txt}</b></p>")
        elif s.startswith("- ") or s.startswith("* "):
            txt = s[2:]
            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
            txt = re.sub(r'\*(.*?)\*', r'<i>\1</i>', txt)
            txt = re.sub(r'`(.*?)`', r'<code>\1</code>', txt)
            body_html.append(f"<ul><li>{txt}</li></ul>")
        elif re.match(r'^\d+\.\s+', s):
            txt = re.sub(r'^\d+\.\s+', '', s)
            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
            txt = re.sub(r'\*(.*?)\*', r'<i>\1</i>', txt)
            txt = re.sub(r'`(.*?)`', r'<code>\1</code>', txt)
            body_html.append(f"<p style='margin-left: 14px;'><b>•</b> {txt}</p>")
        else:
            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)
            txt = re.sub(r'\*(.*?)\*', r'<i>\1</i>', txt)
            txt = re.sub(r'`(.*?)`', r'<code>\1</code>', txt)
            body_html.append(f"<p>{txt}</p>")

    if in_alert:
        box_class = "alert-box" if alert_type == "caution" else "info-box"
        body_html.append(f"<div class='{box_class}'>{''.join(alert_lines)}</div>")

    if in_table:
        table_html.append("</tbody></table>")
        body_html.append("".join(table_html))

    full_html = (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>{css}</head><body>"
        f"{''.join(body_html)}"
        f"<div class='footer-note'>eMED Engenharia Clínica & Manutenção Hospitalar • Procedimento Técnico Homologado • Confidencial</div>"
        f"</body></html>"
    )
    return full_html


def render_markdown_to_pdf(md_file_path: str, output_pdf_path: str) -> str:
    """Compila um arquivo Markdown em PDF de alta resolução usando pymupdf.Story."""
    with open(md_file_path, "r", encoding="utf-8", errors="ignore") as f:
        md_text = f.read()

    doc_title = os.path.splitext(os.path.basename(md_file_path))[0]
    html_content = markdown_to_html(md_text, doc_title)

    story = pymupdf.Story(html=html_content)
    writer = pymupdf.DocumentWriter(output_pdf_path)
    mediabox = pymupdf.Rect(0, 0, 595, 842) # A4
    content_rect = pymupdf.Rect(32, 32, 595 - 32, 842 - 32)

    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, filled = story.place(content_rect)
        story.draw(dev)
        writer.end_page()

    writer.close()
    return output_pdf_path


def converter_html_para_pdf_bytes(html_content: str) -> bytes:
    """Converte conteúdo HTML diretamente para bytes de PDF na memória."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        story = pymupdf.Story(html=html_content)
        writer = pymupdf.DocumentWriter(tmp_path)
        mediabox = pymupdf.Rect(0, 0, 595, 842)
        content_rect = pymupdf.Rect(28, 28, 595 - 28, 842 - 28)
        more = 1
        while more:
            dev = writer.begin_page(mediabox)
            more, filled = story.place(content_rect)
            story.draw(dev)
            writer.end_page()
        writer.close()

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        return pdf_bytes
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def vincular_it_ao_equipamento(equipamento_nome: str, tipo_servico: str = "", base_manuais: str = None) -> dict:
    """
    Localiza a IT mais compatível, seu PDF homologado e o vídeo co-localizado
    a partir da string do equipamento e tipo de serviço.
    """
    if base_manuais is None:
        base_manuais = r"c:\Users\vitor\OneDrive\Desktop\Sistema Emed\Manuais"

    eq_upper = str(equipamento_nome or "").upper()
    srv_upper = str(tipo_servico or "").upper()

    # Dicionário de regras prioritárias
    mapa_regras = [
        # SHIMADZU MOBILDART
        (
            ["SHIMADZU", "MOBILEDART", "MX8", "MX9"],
            "IT_RXM_SHIM_006_Protocolo_Geral_Calibracao_FVR_Baterias_Colimador_FPD_MX8_MX9.md" if "CALIBRA" in srv_upper else "IT_RXM_SHIM_004_Roteiro_Mestre_Instalacao_Comissionamento_31_Passos_MX8_MX9.md",
            "Video_IT_RXM_SHIM002_Calibracao_Manopla_Sensor_Braco_MX8.mp4"
        ),
        # LOTUS HF500M
        (
            ["LOTUS", "HF500", "HF-500", "HF500M"],
            "IT_RX_LOT_001_Vistoria_Pre_Instalacao_Adequacao_Sala_HF500M.md" if ("VISTORIA" in srv_upper or "PRE" in srv_upper) else "IT_RX_LOT_002_Calibracao_kV_mA_Tempo_Manutencao_Familia_HF.md",
            "Video_IT_RX_LOT001_Vistoria_Pre_Instalacao_HF500M.mp4"
        ),
        # NEUSOFT NEUVISION
        (
            ["NEUSOFT", "NEUVISION", "550M", "DR"],
            "IT_RXD_NEU_001_Instalacao_Software_Configuracao_DR_NeuVision550M.md",
            "Video_IT_RXD_NEU001_Instalacao_Software_DR_NeuVision550M.mp4"
        ),
        # GE BRIGHTSPEED
        (
            ["BRIGHTSPEED", "BRIGTHSPEED", "GE CT"],
            "IT_21_Instalacao_e_Recarga_de_Software_LFC_GE_BrightSpeed.md" if ("SOFTWARE" in srv_upper or "INSTAL" in srv_upper or "LFC" in srv_upper) else ("IT_02_Manutencao_Preventiva_GE_BrightSpeed.md" if "PREVENTIVA" in srv_upper else "IT_03_Troca_de_Tubo_GE_BrightSpeed.md"),
            "Video_IT21_Instalacao_Software_LFC_BrightSpeed.mp4" if ("SOFTWARE" in srv_upper or "INSTAL" in srv_upper or "LFC" in srv_upper) else "Video_IT02_Manutencao_Preventiva_BrightSpeed.mp4"
        ),
        # GE BRIVO 385
        (
            ["BRIVO", "385"],
            "IT_01_Troca_de_Tubo_GE_Brivo385.md",
            "Video_IT01_Troca_Tubo_GE_Brivo385.mp4"
        ),
        # MAMÓGRAFO SIEMENS / VMI
        (
            ["MAMOMAT", "MAMÓGRAFO", "MAMOGRAFO", "MM"],
            "IT_MM_SIEM_001_Calibracao_Qualidade_Imagem_Compressao_Mamomat.md",
            "Video_Apresentacao_Sistema_Emed_PRO.mp4"
        ),
        # RAIO-X FIXO GERAL (PHILIPS, VMI, INTERCAL)
        (
            ["RAIO-X", "RX", "PHILIPS", "VMI", "ALTUS", "COMPACTO"],
            "IT_RX_LOT_002_Calibracao_kV_mA_Tempo_Manutencao_Familia_HF.md",
            "Video_Tutorial_Solicitacao_Pecas_Baseada_na_IT.mp4"
        ),
    ]

    for keywords, it_target_name, vid_target_name in mapa_regras:
        if any(k in eq_upper for k in keywords):
            # Busca o arquivo de IT na base de Manuais
            for root, dirs, files in os.walk(base_manuais):
                if it_target_name in files:
                    p_md = os.path.join(root, it_target_name)
                    p_pdf = os.path.splitext(p_md)[0] + ".pdf"
                    
                    # Localiza o vídeo
                    p_vid = None
                    base_root = os.path.abspath(os.path.join(base_manuais, ".."))
                    for vroot, vdirs, vfiles in os.walk(base_root):
                        if vid_target_name in vfiles:
                            p_vid = os.path.join(vroot, vid_target_name)
                            break

                    return {
                        "encontrado": True,
                        "codigo_it": os.path.splitext(it_target_name)[0],
                        "nome_arquivo": it_target_name,
                        "caminho_md": p_md,
                        "caminho_pdf": p_pdf if os.path.exists(p_pdf) else None,
                        "caminho_video": p_vid if (p_vid and os.path.exists(p_vid)) else None,
                        "video_nome": vid_target_name
                    }

    return {"encontrado": False, "codigo_it": None, "caminho_md": None, "caminho_pdf": None, "caminho_video": None}


def gerar_link_whatsapp(telefone: str, mensagem: str) -> str:
    """Gera link de WhatsApp seguro com codificação percentual de caracteres e quebras de linha."""
    num_wa_limpo = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    if num_wa_limpo and not num_wa_limpo.startswith("55") and len(num_wa_limpo) in (10, 11):
        num_wa_limpo = "55" + num_wa_limpo
    base_wa = f"https://wa.me/{num_wa_limpo}" if num_wa_limpo else "https://wa.me/"
    return f"{base_wa}?text={urllib.parse.quote(mensagem)}"
