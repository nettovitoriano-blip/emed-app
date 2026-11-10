import datetime
import math


def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2)**2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2)**2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)


def formatar_tempo(km):
    horas_totais = km / 70.0
    horas = int(horas_totais)
    minutos = int(round((horas_totais - horas) * 60))
    if horas == 0:
        return f"{minutos} min"
    elif minutos == 0:
        return f"{horas}h"
    else:
        return f"{horas}h {minutos}min"


def obter_icone_equipamento(eq_str):
    eq_upper = str(eq_str).upper()
    if 'MAMÓGRAFO' in eq_upper or eq_upper.startswith('MM'):
        return '🎗️'
    elif 'TOMÓGRAFO' in eq_upper or eq_upper.startswith('TC'):
        return '🌀'
    elif 'RAIO-X' in eq_upper or eq_upper.startswith('RX'):
        return '⚡'
    elif 'DENSITOMETRIA' in eq_upper or eq_upper.startswith('DO'):
        return '🦴'
    elif 'RESSONÂNCIA' in eq_upper or eq_upper.startswith('RM'):
        return '🧲'
    elif 'ULTRASSOM' in eq_upper or eq_upper.startswith('US'):
        return '📡'
    else:
        return '⚙️'


def classificar_pendencia(texto_pend):
    txt = str(texto_pend).upper()
    if any(k in txt for k in ['PEÇA', 'PECAS', 'COMPONENTE', 'MODULO']):
        return '🛠️ AGUARDANDO PEÇAS'
    elif any(k in txt for k in ['APROVA', 'ORÇAMENTO', 'ORCAMENTO', 'VALOR', 'PREÇO', 'PRECO']):
        return '✍️ AGUARDANDO APROVAÇÃO'
    elif any(k in txt for k in ['INSTRUMENTO', 'CALIBRAÇÃO', 'CALIBRACAO', 'PADRÃO', 'PADRAO']):
        return '📐 AGUARDANDO INSTRUMENTO'
    else:
        return '📅 AGENDAMENTO'


def calcular_duracao_os(checkin_str, checkout_str):
    if not checkin_str or not checkout_str:
        return ""
    s_in = str(checkin_str).strip()
    s_out = str(checkout_str).strip()
    if not s_in or not s_out:
        return ""

    dt_in = None
    dt_out = None

    formatos_completos = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d"
    ]

    for fmt in formatos_completos:
        if dt_in is None:
            try:
                dt_in = datetime.datetime.strptime(s_in, fmt)
            except Exception:
                pass
        if dt_out is None:
            try:
                dt_out = datetime.datetime.strptime(s_out, fmt)
            except Exception:
                pass

    if dt_in is None or dt_out is None or dt_in == dt_out:
        import re
        m_in = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s_in)
        m_out = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", s_out)
        if m_in and m_out:
            h_in, min_in = int(m_in.group(1)), int(m_in.group(2))
            h_out, min_out = int(m_out.group(1)), int(m_out.group(2))
            base_date = datetime.date(2026, 1, 1)
            if dt_in is not None:
                base_date = dt_in.date()
            dt_in = datetime.datetime.combine(base_date, datetime.time(h_in, min_in))
            base_date_out = base_date
            if dt_out is not None and dt_out.date() > base_date:
                base_date_out = dt_out.date()
            dt_out = datetime.datetime.combine(base_date_out, datetime.time(h_out, min_out))
            if dt_out < dt_in:
                dt_out += datetime.timedelta(days=1)

    if dt_in and dt_out:
        diff = dt_out - dt_in
        minutos_tot = max(0, int(diff.total_seconds() // 60))
        if minutos_tot > 0:
            horas = minutos_tot // 60
            mins = minutos_tot % 60
            if horas > 0:
                return f"{horas}h {mins:02d}min" if mins > 0 else f"{horas}h"
            else:
                return f"{mins} min"

    return ""
