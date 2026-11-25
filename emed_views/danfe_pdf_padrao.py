# -*- coding: utf-8 -*-
"""Gerador de DANFE Padrão Oficial Brasileiro em PDF (FPDF2 + Code128)."""

import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fpdf import FPDF


def _txt(val: Any) -> str:
    """Normaliza texto para fonte Helvetica/Latin-1 do FPDF sem quebrar em caracteres especiais."""
    s = str(val or "")
    s = (
        s.replace("–", "-")
        .replace("—", "-")
        .replace("•", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
        .replace("\u00a0", " ")
    )
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _fmt_cnpj(doc: str) -> str:
    d = "".join(c for c in str(doc or "") if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return doc or ""


def _fmt_chave_44(chave: str) -> str:
    d = "".join(c for c in str(chave or "") if c.isdigit())
    if not d:
        return ""
    return " ".join(d[i : i + 4] for i in range(0, len(d), 4))


def _fmt_num_nf(num: str) -> str:
    d = "".join(c for c in str(num or "") if c.isdigit())
    if not d:
        return str(num or "000.000.000")
    d = d.zfill(9)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}"


def _fmt_moeda(v: Any) -> str:
    try:
        val = float(v or 0.0)
    except Exception:
        val = 0.0
    s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _gerar_barcode_png(chave_44: str) -> str | None:
    d = "".join(c for c in str(chave_44 or "") if c.isdigit())
    if len(d) < 10:
        return None
    try:
        import barcode
        from barcode.writer import ImageWriter

        code128 = barcode.get("code128", d, writer=ImageWriter())
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.close()
        out_path = code128.save(
            tmp.name[:-4],
            options={
                "module_width": 0.22,
                "module_height": 9.0,
                "quiet_zone": 1.5,
                "write_text": False,
                "dpi": 200,
            },
        )
        if os.path.exists(tmp.name) and tmp.name != out_path:
            try:
                os.remove(tmp.name)
            except Exception:
                pass
        return out_path
    except Exception:
        return None


class _DanfePDF(FPDF):
    def footer(self):
        pass


def gerar_danfe_padrao_pdf_bytes(nota: Dict[str, Any]) -> bytes:
    """Gera o arquivo PDF oficial da DANFE no layout padrão brasileiro (NF-e)."""
    pdf = _DanfePDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(6, 6, 6)
    pdf.add_page()
    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(0, 0, 0)
    pdf.set_line_width(0.25)

    W = 198.0  # largura útil (210 - 12)
    X0 = 6.0
    y = 6.0

    num_nf = _fmt_num_nf(nota.get("numero_nf", ""))
    serie = str(nota.get("serie") or "1").zfill(3)
    chave_raw = "".join(c for c in str(nota.get("chave_acesso") or "") if c.isdigit())
    chave_fmt = _fmt_chave_44(chave_raw) or "CHAVE DE ACESSO NÃO INFORMADA"
    nsu = str(nota.get("nsu") or "")
    protocolo = str(nota.get("protocolo") or (f"1{chave_raw[:2]}{nsu.zfill(12)}" if chave_raw else f"SEFAZ-DFE-{nsu}"))

    emit_nome = str(nota.get("emitente_nome") or "FORNECEDOR / EMITENTE").upper()
    emit_cnpj = _fmt_cnpj(nota.get("emitente_cnpj") or "")
    emit_uf = str(nota.get("emitente_uf") or "BR").upper()
    emit_end = str(nota.get("emitente_endereco") or f"Unidade Federativa: {emit_uf} - Consulta via SEFAZ Nacional")
    emit_ie = str(nota.get("emitente_ie") or "-")

    filial = str(nota.get("filial") or "MATRIZ_CE").upper()
    is_df = "DF" in filial
    dest_nome = "EMED ELETROMEDICINA LTDA"
    dest_cnpj = "03.611.974/0002-80" if is_df else "03.611.974/0001-08"
    dest_end = "ADE Conjunto 12, Lote 28" if is_df else "Rua Coronel Freire, 16 - Referencia: em frente ao polo"
    dest_bairro = "Aguas Claras" if is_df else "Amador"
    dest_cep = "71987360" if is_df else "61769470"
    dest_mun = "Brasilia" if is_df else "Eusebio"
    dest_uf = "DF" if is_df else "CE"
    dest_ie = "0824599400143" if is_df else "063678314"
    dest_fone = "(61) 3234-3647" if is_df else "(85) 3254-2929"

    dt_raw = str(nota.get("data_emissao") or "")
    if len(dt_raw) >= 10 and "-" in dt_raw[:10]:
        p = dt_raw[:10].split("-")
        dt_fmt = f"{p[2]}/{p[1]}/{p[0]}"
        hr_fmt = dt_raw[11:19] if len(dt_raw) >= 19 else "00:00:00"
    else:
        dt_fmt = dt_raw[:10] or "-"
        hr_fmt = "00:00:00"

    v_tot = float(nota.get("valor_total") or 0.0)
    nat_op = str(nota.get("natureza_operacao") or "Venda / Fornecimento de mercadorias").strip()
    obs = str(nota.get("observacoes") or "")

    itens: List[Dict[str, Any]] = nota.get("itens") or []
    if not itens and isinstance(nota.get("itens_resumo"), str) and nota.get("itens_resumo"):
        try:
            itens = json.loads(nota["itens_resumo"])
        except Exception:
            itens = []
    if not itens:
        itens = [{
            "codigo": f"NFE-{nota.get('numero_nf', '1')}",
            "descricao": f"MERCADORIA / SUPRIMENTO NF-e {nota.get('numero_nf', '')} ({emit_nome})",
            "ncm": "90229090",
            "cst": "000",
            "cfop": "2102" if emit_uf != dest_uf else "1102",
            "unidade": "UN",
            "qtd": 1,
            "unitario": v_tot,
            "total": v_tot,
        }]

    def box(bx, by, bw, bh, lbl="", val="", lbl_sz=5.2, val_sz=7.5, bold=False, align="L", valign="B"):
        pdf.rect(bx, by, bw, bh)
        if lbl:
            pdf.set_font("Helvetica", "", lbl_sz)
            pdf.set_xy(bx + 0.8, by + 0.5)
            pdf.cell(bw - 1.6, 2.6, _txt(lbl), align="L")
        if val != "":
            pdf.set_font("Helvetica", "B" if bold else "", val_sz)
            vy = by + (bh - 4.2 if valign == "B" else 2.8)
            pdf.set_xy(bx + 0.8, vy)
            pdf.cell(bw - 1.6, 3.8, _txt(val), align=align)

    # =========================================================
    # 1. CANHOTO NO TOPO
    # =========================================================
    h_can = 14.0
    w_can_dir = 34.0
    w_can_esq = W - w_can_dir
    pdf.rect(X0, y, w_can_esq, 6.0)
    pdf.set_font("Helvetica", "", 5.8)
    pdf.set_xy(X0 + 1.0, y + 1.0)
    pdf.multi_cell(
        w_can_esq - 2.0,
        2.5,
        _txt(f"RECEBEMOS DE {emit_nome} OS PRODUTOS CONSTANTES DA NOTA FISCAL INDICADA AO LADO"),
    )
    pdf.rect(X0, y + 6.0, 34.0, 8.0)
    pdf.set_font("Helvetica", "", 5.0)
    pdf.set_xy(X0 + 0.8, y + 6.5)
    pdf.cell(32.0, 2.5, _txt("DATA DE RECEBIMENTO"))

    pdf.rect(X0 + 34.0, y + 6.0, w_can_esq - 34.0, 8.0)
    pdf.set_xy(X0 + 34.8, y + 6.5)
    pdf.cell(w_can_esq - 36.0, 2.5, _txt("IDENTIFICACAO E ASSINATURA DO RECEBEDOR"))

    pdf.rect(X0 + w_can_esq, y, w_can_dir, h_can)
    pdf.set_font("Helvetica", "B", 8.0)
    pdf.set_xy(X0 + w_can_esq, y + 1.2)
    pdf.cell(w_can_dir, 3.5, _txt("NF-e"), align="C")
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(X0 + w_can_esq + 1.0, y + 5.2)
    pdf.cell(w_can_dir - 2.0, 3.5, _txt(f"N. {num_nf}"), align="C")
    pdf.set_xy(X0 + w_can_esq + 1.0, y + 9.2)
    pdf.cell(w_can_dir - 2.0, 3.5, _txt(f"SERIE {serie}"), align="C")

    y += h_can + 2.0
    # Linha tracejada do canhoto
    pdf.set_dash_pattern(dash=1.5, gap=1.2)
    pdf.line(X0, y - 1.0, X0 + W, y - 1.0)
    pdf.set_dash_pattern()

    # =========================================================
    # 2. CABEÇALHO PRINCIPAL (EMITENTE | DANFE | CÓDIGO DE BARRAS)
    # =========================================================
    h_cab = 32.0
    w_emit = 76.0
    w_danfe = 34.0
    w_bar = W - w_emit - w_danfe

    # Emitente
    pdf.rect(X0, y, w_emit, h_cab)

    # Marca d'água / carimbo oficial centralizado atrás dos dados
    p_wm = os.path.join(os.path.dirname(os.path.dirname(__file__)), "emed_pwa_static", "logo_emed_watermark.png")
    if os.path.exists(p_wm):
        try:
            pdf.image(p_wm, x=X0 + (w_emit - 24.0) / 2.0, y=y + 4.0, w=24.0)
        except Exception:
            pass

    pdf.set_font("Helvetica", "B", 8.8)
    pdf.set_xy(X0 + 1.5, y + 2.0)
    pdf.multi_cell(w_emit - 3.0, 3.6, _txt(emit_nome[:70]), align="C")

    emit_sub = str(nota.get("emitente_subtitulo") or "MANUTENCAO EM EQUIPAMENTOS DE DIAGNOSTICO POR IMAGEM").strip()
    pdf.set_font("Helvetica", "B", 5.5)
    pdf.set_xy(X0 + 1.5, y + 6.0)
    pdf.cell(w_emit - 3.0, 2.6, _txt(emit_sub), align="C")

    filial_tag = "FILIAL / DF" if is_df else "MATRIZ / CE"
    pdf.set_font("Helvetica", "B", 6.2)
    pdf.set_xy(X0 + 1.5, y + 9.2)
    pdf.cell(w_emit - 3.0, 3.0, _txt(f"CNPJ: {emit_cnpj} - {filial_tag}"), align="C")

    pdf.set_font("Helvetica", "", 6.0)
    pdf.set_xy(X0 + 2.0, y + 13.0)
    emit_txt_end = f"{emit_end}\nFone: {nota.get('emitente_fone', '(85) 3254-2929')}"
    pdf.multi_cell(w_emit - 4.0, 2.8, _txt(emit_txt_end), align="C")

    # Quadro DANFE central
    xd = X0 + w_emit
    pdf.rect(xd, y, w_danfe, h_cab)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_xy(xd, y + 1.5)
    pdf.cell(w_danfe, 4.2, _txt("DANFE"), align="C")
    pdf.set_font("Helvetica", "", 6.2)
    pdf.set_xy(xd + 1.0, y + 5.8)
    pdf.multi_cell(w_danfe - 2.0, 2.7, _txt("Documento Auxiliar da\nNota Fiscal Eletronica"), align="C")
    pdf.set_font("Helvetica", "", 6.8)
    pdf.set_xy(xd + 1.5, y + 12.0)
    pdf.multi_cell(18.0, 3.2, _txt("0: Entrada\n1: Saida"), align="L")
    pdf.rect(xd + 24.0, y + 12.2, 6.5, 6.0)
    pdf.set_font("Helvetica", "B", 9.0)
    pdf.set_xy(xd + 24.0, y + 13.4)
    pdf.cell(6.5, 3.8, "1", align="C")
    pdf.set_font("Helvetica", "B", 8.0)
    pdf.set_xy(xd + 1.5, y + 19.5)
    pdf.cell(w_danfe - 3.0, 3.8, _txt(f"N. {num_nf}"), align="L")
    pdf.set_xy(xd + 1.5, y + 23.3)
    pdf.cell(w_danfe - 3.0, 3.8, _txt(f"SERIE: {serie}"), align="L")
    pdf.set_font("Helvetica", "", 7.0)
    pdf.set_xy(xd + 1.5, y + 27.2)
    pdf.cell(w_danfe - 3.0, 3.5, _txt("Folha 1 de 1"), align="C")

    # Código de Barras + Chave de Acesso
    xb = xd + w_danfe
    pdf.rect(xb, y, w_bar, 13.5)
    bc_path = _gerar_barcode_png(chave_raw)
    if bc_path and os.path.exists(bc_path):
        try:
            pdf.image(bc_path, x=xb + 3.0, y=y + 1.5, w=w_bar - 6.0, h=10.5)
        finally:
            try:
                os.remove(bc_path)
            except Exception:
                pass
    else:
        pdf.set_font("Helvetica", "", 7.0)
        pdf.set_xy(xb, y + 5.0)
        pdf.cell(w_bar, 4.0, _txt("CONTROLE DO FISCO"), align="C")

    pdf.rect(xb, y + 13.5, w_bar, 9.0)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_xy(xb + 1.0, y + 14.0)
    pdf.cell(w_bar - 2.0, 2.5, _txt("CHAVE DE ACESSO"))
    pdf.set_font("Helvetica", "B", 6.8)
    pdf.set_xy(xb + 1.0, y + 17.5)
    pdf.cell(w_bar - 2.0, 4.0, _txt(chave_fmt), align="C")

    pdf.rect(xb, y + 22.5, w_bar, 9.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_xy(xb + 1.5, y + 24.0)
    pdf.multi_cell(
        w_bar - 3.0,
        3.2,
        _txt("Consulta de autenticidade no portal nacional da NF-e\nwww.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora"),
        align="C",
    )
    y += h_cab

    # Natureza da Operação + Protocolo
    box(X0, y, w_emit + w_danfe, 7.5, "NATUREZA DA OPERACAO", nat_op[:58], val_sz=7.5)
    box(xb, y, w_bar, 7.5, "PROTOCOLO DE AUTORIZACAO DE USO", f"{protocolo}  {dt_fmt} {hr_fmt}", val_sz=7.2)
    y += 7.5

    # IE / IE ST / CNPJ
    box(X0, y, 66.0, 7.5, "INSCRICAO ESTADUAL", emit_ie, val_sz=7.5)
    box(X0 + 66.0, y, 66.0, 7.5, "INSC. ESTADUAL DO SUBST. TRIBUTARIO", "", val_sz=7.5)
    box(X0 + 132.0, y, W - 132.0, 7.5, "CNPJ", emit_cnpj, val_sz=7.5)
    y += 7.5

    # =========================================================
    # 3. DESTINATÁRIO / REMETENTE
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("DESTINATARIO / REMETENTE"))
    y += 3.3

    box(X0, y, 118.0, 7.5, "NOME/RAZAO SOCIAL", dest_nome, val_sz=7.5, bold=True)
    box(X0 + 118.0, y, 48.0, 7.5, "C.N.P.J / C.P.F.", dest_cnpj, val_sz=7.5)
    box(X0 + 166.0, y, W - 166.0, 7.5, "DATA DA EMISSAO", dt_fmt, val_sz=7.5)
    y += 7.5

    box(X0, y, 92.0, 7.5, "ENDERECO", dest_end, val_sz=7.2)
    box(X0 + 92.0, y, 44.0, 7.5, "BAIRRO/DISTRITO", dest_bairro, val_sz=7.2)
    box(X0 + 136.0, y, 30.0, 7.5, "CEP", dest_cep, val_sz=7.2)
    box(X0 + 166.0, y, W - 166.0, 7.5, "DATA DA ENTRADA / SAIDA", dt_fmt, val_sz=7.5)
    y += 7.5

    box(X0, y, 64.0, 7.5, "MUNICIPIO", dest_mun, val_sz=7.5)
    box(X0 + 64.0, y, 30.0, 7.5, "FONE/FAX", dest_fone, val_sz=7.0)
    box(X0 + 94.0, y, 14.0, 7.5, "UF", dest_uf, val_sz=7.5)
    box(X0 + 108.0, y, 58.0, 7.5, "INSCRICAO ESTADUAL", dest_ie, val_sz=7.5)
    box(X0 + 166.0, y, W - 166.0, 7.5, "HORA DE SAIDA", hr_fmt, val_sz=7.5)
    y += 7.5

    # =========================================================
    # 4. FATURA / DUPLICATA
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("FATURA/DUPLICATA"))
    y += 3.3
    pdf.rect(X0, y, W, 6.5)
    y += 6.5

    # =========================================================
    # 5. CÁLCULO DO IMPOSTO
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("CALCULO DO IMPOSTO"))
    y += 3.3

    w5 = W / 5.0
    box(X0, y, w5, 7.5, "BASE DE CALCULO DO ICMS", "0,00", align="R")
    box(X0 + w5, y, w5, 7.5, "VALOR DO ICMS", "0,00", align="R")
    box(X0 + w5 * 2, y, w5, 7.5, "BASE DE CALCULO DO ICMS SUBSTITUICAO", "0,00", align="R")
    box(X0 + w5 * 3, y, w5, 7.5, "VALOR DO ICMS SUBSTITUICAO", "0,00", align="R")
    box(X0 + w5 * 4, y, w5, 7.5, "VALOR TOTAL DOS PRODUTOS", _fmt_moeda(v_tot), align="R")
    y += 7.5

    w6 = [31.0, 31.0, 29.0, 35.0, 32.0, W - 158.0]
    labels6 = [
        ("VALOR DO FRETE", "0,00"),
        ("VALOR DO SEGURO", "0,00"),
        ("DESCONTO", "0,00"),
        ("OUTRAS DESPESAS ACESSORIAS", "0,00"),
        ("VALOR DO IPI", "0,00"),
        ("VALOR TOTAL DA NOTA", _fmt_moeda(v_tot)),
    ]
    cx = X0
    for idx_c, (lbl6, val6) in enumerate(labels6):
        box(cx, y, w6[idx_c], 7.5, lbl6, val6, align="R", bold=(idx_c == 5))
        cx += w6[idx_c]
    y += 7.5

    # =========================================================
    # 6. TRANSPORTADOR / VOLUME
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("TRANSPORTADOR/VOLUME"))
    y += 3.3

    box(X0, y, 76.0, 7.5, "RAZAO SOCIAL", "POR CONTA DO EMITENTE / TRANSPORTADORA", val_sz=6.8)
    box(X0 + 76.0, y, 30.0, 7.5, "FRETE POR CONTA", "0 - Emitente", val_sz=7.0)
    box(X0 + 106.0, y, 22.0, 7.5, "CODIGO ANTT", "")
    box(X0 + 128.0, y, 22.0, 7.5, "PLACA DO VEICULO", "")
    box(X0 + 150.0, y, 10.0, 7.5, "UF", "")
    box(X0 + 160.0, y, W - 160.0, 7.5, "CNPJ/CPF", "")
    y += 7.5

    box(X0, y, 82.0, 7.5, "ENDERECO", "")
    box(X0 + 82.0, y, 68.0, 7.5, "MUNICIPIO", "")
    box(X0 + 150.0, y, 10.0, 7.5, "UF", "")
    box(X0 + 160.0, y, W - 160.0, 7.5, "INSCRICAO ESTADUAL", "")
    y += 7.5

    box(X0, y, 28.0, 7.5, "QUANTIDADE", str(len(itens)))
    box(X0 + 28.0, y, 34.0, 7.5, "ESPECIE", "VOLUMES")
    box(X0 + 62.0, y, 34.0, 7.5, "MARCA", "")
    box(X0 + 96.0, y, 42.0, 7.5, "NUMERACAO", "")
    box(X0 + 138.0, y, 30.0, 7.5, "PESO BRUTO", "0,000", align="R")
    box(X0 + 168.0, y, W - 168.0, 7.5, "PESO LIQUIDO", "0,000", align="R")
    y += 7.5

    # =========================================================
    # 7. LOCAL DE ENTREGA / RETIRADA
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("INFORMACOES DO LOCAL DE ENTREGA / RETIRADA"))
    y += 3.3
    box(X0, y, 124.0, 6.8, "NOME/RAZAO SOCIAL", "")
    box(X0 + 124.0, y, 40.0, 6.8, "C.N.P.J / C.P.F.", "")
    box(X0 + 164.0, y, W - 164.0, 6.8, "INSCRICAO ESTADUAL", "")
    y += 6.8
    box(X0, y, 110.0, 6.8, "ENDERECO", "")
    box(X0 + 110.0, y, 54.0, 6.8, "BAIRRO/DISTRITO", "")
    box(X0 + 164.0, y, W - 164.0, 6.8, "CEP", "")
    y += 6.8
    box(X0, y, 136.0, 6.8, "MUNICIPIO", "")
    box(X0 + 136.0, y, 16.0, 6.8, "UF", "")
    box(X0 + 152.0, y, W - 152.0, 6.8, "FONE/FAX", "")
    y += 6.8

    # =========================================================
    # 8. DADOS DO PRODUTO / SERVIÇOS
    # =========================================================
    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("DADOS DO PRODUTO / SERVICOS"))
    y += 3.3

    # 13 colunas padrão DANFE
    cols = [
        ("CODIGO\nPRODUTO", 19.0, "C"),
        ("DESCRICAO DOS PRODUTOS / SERVICOS", 59.0, "L"),
        ("NCM/SH", 15.0, "C"),
        ("CST", 8.0, "C"),
        ("CFOP", 9.0, "C"),
        ("UNID.", 9.0, "C"),
        ("QTD.", 11.0, "R"),
        ("VLR UNIT.", 14.0, "R"),
        ("VALOR TOTAL", 15.0, "R"),
        ("B. CALC.\nICMS", 12.0, "R"),
        ("VALOR\nICMS", 10.0, "R"),
        ("VALOR\nIPI", 8.0, "R"),
        ("ALIQ.\nICMS|IPI", W - 189.0, "C"),
    ]

    h_th = 6.5
    cx = X0
    pdf.set_font("Helvetica", "B", 5.0)
    for title, cw, _ in cols:
        pdf.rect(cx, y, cw, h_th)
        pdf.set_xy(cx + 0.3, y + 0.8)
        pdf.multi_cell(cw - 0.6, 2.4, _txt(title), align="C")
        cx += cw
    y += h_th

    # Altura disponível para itens até o ISSQN/Dados Adicionais no rodapé
    y_rodape = 244.0
    y_items_end = y_rodape - 1.5
    h_row = 5.5
    max_rows = max(1, int((y_items_end - y) / h_row))

    # Desenha grade vertical da tabela de itens
    box_items_h = max(h_row * min(len(itens), max_rows), 38.0)
    if y + box_items_h > y_items_end:
        box_items_h = y_items_end - y

    cx = X0
    for _, cw, _ in cols:
        pdf.rect(cx, y, cw, box_items_h)
        cx += cw

    pdf.set_font("Helvetica", "", 6.0)
    curr_y = y + 0.8
    for it in itens[:max_rows]:
        if curr_y + 4.2 > y + box_items_h:
            break
        cod = str(it.get("codigo") or "-")[:14]
        desc = str(it.get("descricao") or "MERCADORIA")[:42]
        ncm = str(it.get("ncm") or "90229090")[:10]
        cst = str(it.get("cst") or "000")[:4]
        cfop = str(it.get("cfop") or ("2102" if emit_uf != dest_uf else "1102"))[:4]
        unid = str(it.get("unidade") or "UN")[:4]
        qtd = float(it.get("qtd") or 1.0)
        v_un = float(it.get("unitario") or 0.0)
        v_sub = float(it.get("total") or (qtd * v_un))

        vals_row = [
            cod,
            desc,
            ncm,
            cst,
            cfop,
            unid,
            f"{qtd:g}",
            _fmt_moeda(v_un),
            _fmt_moeda(v_sub),
            "0,00",
            "0,00",
            "0,00",
            "0,00 | 0,00",
        ]
        cx = X0
        for idx_col, (_, cw, al) in enumerate(cols):
            pdf.set_xy(cx + 0.5, curr_y)
            pdf.cell(cw - 1.0, 4.0, _txt(vals_row[idx_col]), align=al)
            cx += cw
        curr_y += h_row

    # =========================================================
    # 9. CÁLCULO DO ISSQN + DADOS ADICIONAIS (RODAPÉ FIXO)
    # =========================================================
    y = y_rodape
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("CALCULO DO ISSQN"))
    y += 3.3
    w_iss = W / 4.0
    box(X0, y, w_iss, 6.8, "INSCRICAO MUNICIPAL", "")
    box(X0 + w_iss, y, w_iss, 6.8, "VALOR TOTAL DOS SERVICOS", "0,00", align="R")
    box(X0 + w_iss * 2, y, w_iss, 6.8, "BASE DE CALCULO DO ISSQN", "0,00", align="R")
    box(X0 + w_iss * 3, y, w_iss, 6.8, "VALOR DO ISSQN", "0,00", align="R")
    y += 6.8

    y += 1.2
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_xy(X0, y)
    pdf.cell(W, 3.2, _txt("DADOS ADICIONAIS"))
    y += 3.3

    h_add = 290.0 - y
    w_inf = 132.0
    pdf.rect(X0, y, w_inf, h_add)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_xy(X0 + 0.8, y + 0.5)
    pdf.cell(w_inf - 1.6, 2.5, _txt("INFORMACOES COMPLEMENTARES"))
    pdf.set_font("Helvetica", "", 6.2)
    pdf.set_xy(X0 + 1.0, y + 3.5)
    texto_add = (
        f"Documento sincronizado via Ambiente Nacional SEFAZ (NFeDistribuicaoDFe) - NSU {nsu or '-'}.\n"
        f"Chave de Acesso: {chave_raw or '-'}.\n"
        f"{obs}"
    )
    pdf.multi_cell(w_inf - 2.0, 3.0, _txt(texto_add[:420]))

    pdf.rect(X0 + w_inf, y, W - w_inf, h_add)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_xy(X0 + w_inf + 0.8, y + 0.5)
    pdf.cell(W - w_inf - 1.6, 2.5, _txt("RESERVADO AO FISCO"))

    out = pdf.output(dest="S")
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    return str(out).encode("latin-1")
