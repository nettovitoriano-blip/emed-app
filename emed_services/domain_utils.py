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
    try:
        dt_in = datetime.datetime.strptime(str(checkin_str).strip(), "%d/%m/%Y %H:%M")
        dt_out = datetime.datetime.strptime(str(checkout_str).strip(), "%d/%m/%Y %H:%M")
        diff = dt_out - dt_in
        minutos_tot = max(0, int(diff.total_seconds() // 60))
        horas = minutos_tot // 60
        mins = minutos_tot % 60
        return f"{horas}h {mins}min" if horas > 0 else f"{mins} min"
    except Exception:
        return ""
