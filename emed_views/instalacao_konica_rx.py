"""
instalacao_konica_rx.py — Módulo Estruturado FR_SE00003_03 (Relatório de Instalação e Aceitação Equipamento de Raios X - Konica Minolta)
"""
import html as _h
import json
import sqlite3
from typing import Any, Dict, List, Tuple

ITENS_EMBALAGEM_KONICA: List[Tuple[str, str]] = [
    ("gerador_kv", "Gerador (kV: 150kV / 125kV / N/A)"),
    ("gerador_kw", "Gerador (kW: 54kW / 64kW / N/A)"),
    ("transformador", "Transformador"),
    ("tubo_rx", "Tubo Raios X"),
    ("colimador", "Colimador luminoso"),
    ("painel_comando", "Painel de Comando"),
    ("conjunto_mecanico", "Conjunto Mecânico (mesa, estativa porta tubo, estativa mural bucky)"),
    ("auto_trafo", "Auto Trafo 20KVA 220V/380-44 (se aplicável)"),
    ("grade_fixa", "Grade fixa (103L / 152L / 200L)"),
    ("cabo_alta", "Cabo de alta"),
    ("painel_aerodr", "Painel AeroDR"),
    ("battery_charger", "Battery Charger"),
    ("diu_giu", "DIU / GIU"),
    ("aruba", "Aruba (se aplicável)"),
    ("switch", "Switch"),
    ("cabo_xg", "Cabo XG"),
    ("if_cable_3", "IF Cable 3"),
    ("stitching", "STITCHING"),
    ("monitor", "Monitor"),
    ("cpu_perifericos", "CPU + teclado + Mouse (ou notebook)"),
    ("camara_aec", "Câmara de ionização (AEC)"),
    ("vacudap", "VacuDap"),
]

BLOCOS_CHECKLIST_KONICA: List[Dict[str, Any]] = [
    {
        "id": "DOCUMENTOS",
        "titulo": "1. Documentos & Materiais Identificados (Pág. 2)",
        "opcoes": ["SIM", "NÃO", "N/A"],
        "itens": [
            ("doc_conj_mec", "Conjunto mecânico contendo mesa, mural, trilhos, estativa, painel de comando (freios), cabos e tubo"),
            ("doc_gerador", "Gerador de RX (Gabinete)"),
            ("doc_trafo", "Transformador de alta (Caixa de óleo)"),
            ("doc_console", "Console de comando (Controle de seleção de técnicas)"),
            ("doc_autotransf", "Autotransformador 220/380 (se aplicável)"),
            ("doc_quadro", "Quadro de força (se aplicável)"),
            ("doc_cabos_at", "Cabos de alta / Cabo do Giratório"),
            ("doc_expedicao", "Documentos: Expedição de Equipamentos / FR_PR00002"),
            ("doc_garantia", "Certificação de garantia"),
        ],
    },
    {
        "id": "QUADRO_FORCA",
        "titulo": "2. Quadro de Força & DPS (Págs. 2-3)",
        "opcoes": ["SIM", "NÃO", "N/A"],
        "itens": [
            ("qf_disj_63", "Disjuntor tripolar de 63A / 54kW"),
            ("qf_disj_80", "Disjuntor tripolar de 80A / 64kW"),
            ("qf_disj_10", "Disjuntor bipolar de 10A"),
            ("qf_fi", "Interruptor de corrente de fuga 'FI' 5SM1 346-6 (63A / 30mA)"),
            ("qf_contator", "Contator 3RT 1044"),
            ("qf_selo", "Contato 'selo': Contato auxiliar 3RH1921-1EA20 (NO)"),
            ("qf_cmd_porta", "Dispositivo de comando na porta (LIGA verde, DESLIGA fechadura, soco vermelho)"),
            ("qf_barras", "Barras de cobre para 04 saídas (terra e neutro isolado do terra)"),
            ("qf_botoeira", "Botoeira dupla Liga-Desliga e sinalização montados em caixa"),
            ("qf_desconectar", "Botão vermelho com fechadura de segurança 3SB30 00-1BA20 (Desconectar)"),
            ("qf_qdc", "Quadro de comando 'sobrepor ou embutir' QDC 50X40X20 cm"),
            ("qf_dps", "DPS Classe II trifásico com Neutro (Finder 7P.24.8.275.x020 — In 20kA / Imax 40kA)"),
        ],
    },
    {
        "id": "AMBIENTE",
        "titulo": "3. Ambiente — RDC 611 / RDC 50 ANVISA (Pág. 3)",
        "opcoes": ["SIM", "NÃO", "N/A"],
        "itens": [
            ("amb_area", "Área mínima recomendada para sala 24,75 m² (4,5 x 5,5 m)"),
            ("amb_altura", "Altura mínima recomendada para sala 2,70 m"),
            ("amb_porta", "Dimensões mínimas da porta: largura 100 cm, altura 210 cm"),
            ("amb_temp", "Temperatura da sala 23 °C ± 2 °C"),
            ("amb_umid", "Umidade do Ar 50% ± 10% sem condensação"),
            ("amb_ac", "Sistema de ar condicionado mantém temperatura e umidade controladas constantemente"),
            ("amb_blind", "Paredes, piso, teto e porta(s) com blindagem radiológica às áreas externas"),
            ("amb_cabine", "Cabine(s) de comando com proteção adequada ao operador e visibilidade ao paciente"),
            ("amb_sinal", "Sinalização luminosa externa de cor vermelha de operação do equipamento"),
        ],
    },
    {
        "id": "MONTAGEM_MECANICA",
        "titulo": "4. Montagem Mecânica / Posicionamento da Mesa (Pág. 4)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("mm_trilho", "Nivelar o trilho traseiro de estativa"),
            ("mm_dist_est", "Distância do Trilho da estativa conferida (ver campo cm)"),
            ("mm_dist_bucky", "Distância do Bucky mural conferida (ver campo cm)"),
            ("mm_prumo", "Ajuste de prumo da estativa"),
            ("mm_niv_mesa", "Nivelamento da mesa"),
            ("mm_pos_ger", "Posicionar Gerador e transformador"),
            ("mm_fix_painel", "Fixar painel (se solicitado pelo cliente)"),
        ],
    },
    {
        "id": "BUCKY_MESA_MURAL",
        "titulo": "5. Bucky Mesa / Mural (Pág. 4)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("bm_alca_mesa", "Montar a alça da grade removível mesa"),
            ("bm_alca_mural", "Montar a alça da grade removível mural"),
            ("bm_bandeja", "Bandeja"),
            ("bm_fim_curso", "Fim de curso"),
            ("bm_freio_mural", "Freio mural (deslocamento linear e funcionamento do manípulo)"),
            ("bm_freio_bucky", "Freio do bucky da mesa (botão/eletrofreio acionado e desligado)"),
            ("bm_freio_tampo", "Freio do tampo da mesa (pedal acionado/travado e deslocamento linear)"),
            ("bm_contrabal", "Sistema conjunto emissor e estativa porta tubo contrabalanceado"),
            ("bm_aec", "Instalação da câmara de ionização AEC"),
        ],
    },
    {
        "id": "CABOS_AT",
        "titulo": "6. Cabos de Alta Tensão (Pág. 4)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("at_limpeza", "Limpeza dos terminais do cabo de alta"),
            ("at_polaridade", "Identificação de polaridade"),
            ("at_silicone", "Utilização de silicone líquido / vaselina"),
            ("at_conexao", "Conexão do tubo ao trafo HV"),
            ("at_flange", "Verificar aperto do flange do cabo de HV com as vias (+) e (-) do trafo (sem folgas)"),
        ],
    },
    {
        "id": "CABOS_BT",
        "titulo": "7. Cabos de Baixa Tensão — Ligação ao Gerador (Pág. 5)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("bt_rede", "Rede trifásica"),
            ("bt_terra", "Aterramento"),
            ("bt_alim_mesa", "Alimentação da mesa"),
            ("bt_giratorio", "Cabo giratório como sensor do tubo"),
            ("bt_neutro", "Ligação do Neutro"),
            ("bt_lampada", "Lâmpada externa"),
            ("bt_sensor_porta", "Sensor de porta"),
        ],
    },
    {
        "id": "INTERLIGACOES",
        "titulo": "8. Interligações & Aterramentos (Pág. 5)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("int_mesa", "Cabo de alimentação da mesa"),
            ("int_estativa", "Cabo de alimentação da estativa porta tubo"),
            ("int_mural", "Cabo de alimentação do Mural Bucky"),
            ("int_colim", "Cabo de alimentação do colimador"),
            ("int_terra_colim", "Cabo de aterramento do colimador"),
            ("int_terra_painel", "Aterramento do painel"),
            ("int_prim_hv", "Cabo primário Trafo de HV"),
            ("int_cab01005", "Cab01005_Realimentação KV"),
            ("int_cab01004", "Cab01004_Alimentação Filamento"),
            ("int_cab01039", "Cab01039_Primário do filamento"),
            ("int_terra_hv", "Aterramento do Trafo de HV"),
            ("int_cab01016", "Cab01016_Alimentação 24V"),
            ("int_terra_mesa", "Aterramento da mesa"),
            ("int_terra_mural", "Aterramento do Mural Bucky (se com AEC)"),
            ("int_terra_est", "Aterramento da Estativa porta tubo"),
            ("int_terra_auto", "Terra do Auto Trafo (se aplicável)"),
            ("int_dap", "Cabo de alimentação do DAP (se aplicável)"),
            ("int_aec", "Cabo de comunicação da câmara de ionização AEC (se aplicável)"),
        ],
    },
    {
        "id": "NIVELAMENTO_COLIMADOR",
        "titulo": "9. Nivelamento, Centralização & Colimador (Pág. 5)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("nc_niv_mural", "Nivelamento do mural Bucky"),
            ("nc_cent_mural", "Centralizar Bucky mural com mesa"),
            ("nc_cent_colim", "Centralizar luz do colimador com centro da mesa"),
        ],
    },
    {
        "id": "CONDICOES_EXTERNAS",
        "titulo": "10. Condições Externas e Aparente do Equipamento (Pág. 10)",
        "opcoes": ["OK", "NÃO OK", "N/A"],
        "itens": [
            ("ce_pintura", "Pintura"),
            ("ce_func", "Funcionamento"),
            ("ce_mec", "Mecânica"),
            ("ce_rede", "Rede elétrica"),
            ("ce_acq", "Aquisição de Imagem"),
            ("ce_emb", "Embalagem"),
            ("ce_sala", "Sala"),
        ],
    },
]

FONTES_PCB01004: List[Tuple[str, str, str]] = [
    ("f5", "Fonte 5 VDC", "Entre 4,8 VDC e 5,2 VDC (Led D51 aceso)"),
    ("f15", "Fonte 15 VDC", "Entre 14,4 VDC e 15,6 VDC (Led D55 aceso)"),
    ("f12", "Fonte 12 VDC", "Entre 11,5 VDC e 12,5 VDC (Led D54 aceso)"),
    ("f_12", "Fonte -12 VDC", "Entre -11,5 VDC e -12,5 VDC (Led D53 aceso)"),
]

PREP_AQUECIMENTO: List[Tuple[str, str, str]] = [
    ("p1", "100mA; 40kV; 100ms", "TP16: 244 mV a 256 mV"),
    ("p2", "100mA; 65kV; 100ms", "TP16: 244 mV a 256 mV"),
    ("p3", "100mA; 80kV; 100ms", "TP16: 244 mV a 256 mV"),
    ("p4", "100mA; 120kV; 100ms", "TP16: 244 mV a 256 mV"),
    ("p5", "125mA; 40kV; 100ms (1)", "TP16: 305 mV a 320 mV"),
    ("p6", "125mA; 40kV; 100ms (2)", "TP16: 305 mV a 320 mV"),
    ("p7", "125mA; 40kV; 100ms (3)", "TP16: 305 mV a 320 mV"),
    ("p8", "125mA; 40kV; 100ms (4)", "TP16: 305 mV a 320 mV"),
]

# (mA, kV, ms, disparos, tp16_ref, tp28_ref)
AQUECIMENTO_TUBO: List[Tuple[int, int, int, int, str, str]] = [
    (100, 60, 100, 2, "0,25 V", "1,20 V"),
    (100, 70, 100, 2, "0,25 V", "1,40 V"),
    (100, 80, 100, 2, "0,25 V", "1,60 V"),
    (100, 90, 100, 2, "0,25 V", "1,80 V"),
    (100, 100, 100, 2, "0,25 V", "2,00 V"),
    (100, 110, 100, 2, "0,25 V", "2,20 V"),
    (100, 115, 100, 2, "0,25 V", "2,30 V"),
    (100, 120, 100, 2, "0,25 V", "2,40 V"),
    (100, 125, 100, 2, "0,25 V", "2,50 V"),
    (100, 130, 100, 2, "0,25 V", "2,60 V"),
    (125, 135, 100, 2, "0,31 V", "2,70 V"),
    (125, 140, 100, 2, "0,31 V", "2,80 V"),
    (125, 145, 100, 2, "0,31 V", "2,90 V"),
    (125, 150, 100, 2, "0,31 V", "3,00 V"),
]

# (mA, kV, ms, lim_inf, central, lim_sup, t125, t150)
CALIBRACAO_CORRENTES: List[Tuple[int, int, int, float, float, float, bool, bool]] = [
    (10, 41, 100, 0.244, 0.250, 0.256, True, True),
    (10, 65, 100, 0.244, 0.250, 0.256, True, True),
    (10, 80, 100, 0.244, 0.250, 0.256, True, True),
    (10, 120, 100, 0.244, 0.250, 0.256, True, True),
    (50, 41, 100, 1.188, 1.219, 1.250, True, True),
    (50, 65, 100, 1.188, 1.219, 1.250, True, True),
    (50, 80, 100, 1.188, 1.219, 1.250, True, True),
    (50, 120, 100, 1.188, 1.219, 1.250, True, True),
    (100, 40, 100, 0.244, 0.250, 0.256, True, True),
    (100, 65, 100, 0.244, 0.250, 0.256, True, True),
    (100, 80, 100, 0.244, 0.250, 0.256, True, True),
    (100, 120, 100, 0.244, 0.250, 0.256, True, True),
    (125, 40, 100, 0.305, 0.313, 0.320, True, True),
    (125, 65, 100, 0.305, 0.313, 0.320, True, True),
    (125, 80, 100, 0.305, 0.313, 0.320, True, True),
    (125, 110, 100, 0.305, 0.313, 0.320, True, False),
    (125, 120, 100, 0.305, 0.313, 0.320, False, True),
    (160, 40, 100, 0.390, 0.400, 0.410, True, True),
    (160, 65, 100, 0.390, 0.400, 0.410, True, True),
    (160, 80, 100, 0.390, 0.400, 0.410, False, True),
    (160, 90, 100, 0.390, 0.400, 0.410, True, False),
    (160, 120, 100, 0.390, 0.400, 0.410, False, True),
    (220, 50, 100, 0.523, 0.536, 0.550, True, True),
    (220, 65, 100, 0.523, 0.536, 0.550, True, True),
    (220, 80, 100, 0.523, 0.536, 0.550, True, True),
    (220, 120, 100, 0.523, 0.536, 0.550, True, False),
    (280, 55, 100, 0.683, 0.700, 0.718, True, True),
    (280, 65, 100, 0.683, 0.700, 0.718, True, True),
    (280, 80, 100, 0.683, 0.700, 0.718, True, True),
    (280, 110, 100, 0.683, 0.700, 0.718, True, False),
    (280, 120, 100, 0.683, 0.700, 0.718, False, True),
    (320, 55, 100, 0.780, 0.800, 0.820, True, True),
    (320, 65, 100, 0.780, 0.800, 0.820, True, True),
    (320, 80, 100, 0.780, 0.800, 0.820, False, True),
    (320, 100, 100, 0.780, 0.800, 0.820, True, False),
    (320, 120, 100, 0.780, 0.800, 0.820, False, True),
    (360, 57, 100, 0.878, 0.900, 0.923, True, True),
    (360, 65, 100, 0.878, 0.900, 0.923, True, True),
    (360, 80, 100, 0.878, 0.900, 0.923, False, True),
    (360, 90, 100, 0.878, 0.900, 0.923, True, False),
    (360, 120, 100, 0.878, 0.900, 0.923, False, True),
    (400, 60, 100, 0.950, 0.975, 1.000, False, True),
    (400, 80, 100, 0.950, 0.975, 1.000, False, True),
    (400, 110, 100, 0.950, 0.975, 1.000, False, True),
    (450, 60, 40, 1.069, 1.097, 1.125, True, False),
    (450, 70, 40, 1.069, 1.097, 1.125, True, False),
    (500, 65, 40, 1.188, 1.219, 1.250, False, True),
    (500, 80, 40, 1.188, 1.219, 1.250, False, True),
    (500, 100, 40, 1.188, 1.219, 1.250, False, True),
    (630, 60, 40, 1.457, 1.497, 1.537, True, False),
    (630, 65, 40, 1.457, 1.497, 1.537, False, True),
    (630, 70, 40, 1.457, 1.497, 1.537, True, False),
    (630, 80, 40, 1.457, 1.497, 1.537, False, True),
    (630, 100, 40, 1.457, 1.497, 1.537, False, True),
    (800, 70, 40, 1.850, 1.900, 1.950, False, True),
    (800, 80, 40, 1.850, 1.900, 1.950, False, True),
]

ALTA_POTENCIA: List[Tuple[int, int, int, float, float, float, bool, bool]] = [
    (10, 125, 5000, 0.244, 0.250, 0.256, True, False),
    (10, 130, 5000, 0.244, 0.250, 0.256, False, True),
    (50, 125, 4500, 1.188, 1.219, 1.250, True, False),
    (50, 130, 4500, 1.188, 1.219, 1.250, False, True),
    (100, 125, 400, 0.244, 0.250, 0.256, True, False),
    (100, 130, 1250, 0.244, 0.250, 0.256, False, True),
    (125, 125, 56, 0.305, 0.313, 0.320, True, False),
    (125, 150, 220, 0.305, 0.313, 0.320, False, True),
    (160, 106, 11, 0.390, 0.400, 0.410, True, False),
    (160, 150, 10, 0.390, 0.400, 0.410, False, True),
    (220, 125, 500, 0.523, 0.536, 0.550, True, False),
    (220, 97, 100, 0.523, 0.536, 0.550, False, True),
    (280, 125, 200, 0.683, 0.700, 0.718, True, False),
    (280, 130, 100, 0.683, 0.700, 0.718, False, True),
    (320, 125, 140, 0.780, 0.800, 0.820, True, False),
    (320, 125, 360, 0.780, 0.800, 0.820, False, True),
    (360, 120, 110, 0.878, 0.900, 0.923, True, False),
    (360, 120, 320, 0.878, 0.900, 0.923, False, True),
    (400, 116, 280, 0.950, 0.975, 1.000, False, True),
    (450, 120, 10, 1.069, 1.097, 1.125, True, False),
    (500, 108, 125, 1.188, 1.219, 1.250, False, True),
    (630, 85, 14, 1.457, 1.497, 1.537, False, True),
    (630, 100, 45, 1.457, 1.497, 1.537, False, True),
    (800, 80, 45, 1.850, 1.900, 1.950, False, True),
]

TEMPLATE_CODIGO = "KONICA_FR_SE00003_03"


def garantir_schema_formularios_tecnicos(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS os_formularios_tecnicos (
            os_id TEXT NOT NULL,
            template_codigo TEXT NOT NULL,
            dados_json TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            atualizado_por TEXT,
            PRIMARY KEY (os_id, template_codigo)
        )
    """)


def obter_schema_konica_rx() -> Dict[str, Any]:
    return {
        "template_codigo": TEMPLATE_CODIGO,
        "itens_embalagem": [{"id": k, "label": lbl} for k, lbl in ITENS_EMBALAGEM_KONICA],
        "blocos_checklist": [
            {"id": b["id"], "titulo": b["titulo"], "opcoes": b["opcoes"], "itens": [{"id": k, "label": l} for k, l in b["itens"]]}
            for b in BLOCOS_CHECKLIST_KONICA
        ],
        "fontes_pcb": [{"id": k, "label": l, "criterio": c} for k, l, c in FONTES_PCB01004],
        "prep_aquecimento": [{"id": k, "label": l, "criterio": c} for k, l, c in PREP_AQUECIMENTO],
        "aquecimento_tubo": [
            {"idx": i, "ma": r[0], "kv": r[1], "ms": r[2], "disp": r[3], "tp16": r[4], "tp28": r[5]}
            for i, r in enumerate(AQUECIMENTO_TUBO)
        ],
        "calibracao_correntes": [
            {"idx": i, "ma": r[0], "kv": r[1], "ms": r[2], "inf": r[3], "cen": r[4], "sup": r[5], "t125": r[6], "t150": r[7]}
            for i, r in enumerate(CALIBRACAO_CORRENTES)
        ],
        "alta_potencia": [
            {"idx": i, "ma": r[0], "kv": r[1], "ms": r[2], "inf": r[3], "cen": r[4], "sup": r[5], "t125": r[6], "t150": r[7]}
            for i, r in enumerate(ALTA_POTENCIA)
        ],
    }


def carregar_dados_konica_rx(conn: sqlite3.Connection, os_id: str) -> Dict[str, Any]:
    garantir_schema_formularios_tecnicos(conn)
    row = conn.execute(
        "SELECT dados_json, atualizado_em, atualizado_por FROM os_formularios_tecnicos WHERE os_id = ? AND template_codigo = ?",
        (str(os_id), TEMPLATE_CODIGO),
    ).fetchone()
    if row and row[0]:
        try:
            d = json.loads(row[0])
            d["_atualizado_em"] = row[1]
            d["_atualizado_por"] = row[2] or ""
            return d
        except Exception:
            pass

    # Pre-preenchimento automatico a partir da OS em clientes_equipamentos
    conn.row_factory = sqlite3.Row
    os_row = conn.execute("SELECT * FROM clientes_equipamentos WHERE CAST(id AS TEXT) = ?", (str(os_id),)).fetchone()
    if os_row:
        return {
            "cliente": os_row["cliente"] or "",
            "endereco": os_row["endereco"] or "",
            "cidade": os_row["cidade"] or "",
            "estado": os_row["estado"] or "",
            "contato": os_row["responsavel_hospital"] or "",
            "telefone": os_row["contato_responsavel"] or os_row["whatsapp"] or "",
            "email": os_row["email"] or "",
            "instalador": os_row["tecnico_responsavel"] or "",
            "modelo": "Altus",
            "gerador_kv_tipo": "125kV",
            "gerador_kw_tipo": "54kW",
            "grade_tipo": "103L",
            "rede_tipo": "380V",
            "tubo_tipo": "125kV",
            "series": {},
            "checks": {},
            "medicoes": {},
            "instrumentos": {},
            "fontes": {},
            "prep_aq": {},
            "aq_tp16": {},
            "aq_tp28": {},
            "cal_tp16": {},
            "ap_tp16": {},
            "intercorrencias": "",
        }
    return {"series": {}, "checks": {}, "medicoes": {}, "instrumentos": {}, "fontes": {}, "prep_aq": {}, "aq_tp16": {}, "aq_tp28": {}, "cal_tp16": {}, "ap_tp16": {}}


def salvar_dados_konica_rx(conn: sqlite3.Connection, os_id: str, dados: Dict[str, Any], agora: str, usuario: str) -> None:
    garantir_schema_formularios_tecnicos(conn)
    payload = json.dumps(dados or {}, ensure_ascii=False)
    conn.execute("""
        INSERT INTO os_formularios_tecnicos (os_id, template_codigo, dados_json, atualizado_em, atualizado_por)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(os_id, template_codigo) DO UPDATE SET
            dados_json = excluded.dados_json,
            atualizado_em = excluded.atualizado_em,
            atualizado_por = excluded.atualizado_por
    """, (str(os_id), TEMPLATE_CODIGO, payload, agora, usuario))
    conn.commit()


def gerar_html_konica_rx_fr_se00003(db_name: str, os_id: str) -> str:
    with sqlite3.connect(db_name) as conn:
        d = carregar_dados_konica_rx(conn, os_id)
        conn.row_factory = sqlite3.Row
        os_row = conn.execute("SELECT * FROM clientes_equipamentos WHERE CAST(id AS TEXT) = ?", (str(os_id),)).fetchone()

    def g(k: str, default: str = "") -> str:
        return _h.escape(str(d.get(k) or default))

    series = d.get("series") or {}
    checks = d.get("checks") or {}
    med = d.get("medicoes") or {}
    inst = d.get("instrumentos") or {}
    fontes = d.get("fontes") or {}
    prep_aq = d.get("prep_aq") or {}
    aq_tp16 = d.get("aq_tp16") or {}
    aq_tp28 = d.get("aq_tp28") or {}
    cal_tp16 = d.get("cal_tp16") or {}
    ap_tp16 = d.get("ap_tp16") or {}

    ass_cli_img = (os_row["assinatura_cliente_img"] if os_row and os_row["assinatura_cliente_img"] else "") or ""
    ass_cli_nome = _h.escape(str(d.get("aceite_nome") or (os_row["assinatura_cliente"] if os_row else "") or d.get("contato") or ""))
    ass_tec_nome = _h.escape(str(d.get("instalador") or (os_row["tecnico_responsavel"] if os_row else "") or ""))
    dt_aceite = _h.escape(str(d.get("aceite_data") or d.get("_atualizado_em") or "")[:10])
    local_aceite = _h.escape(f"{d.get('cidade', '')} - {d.get('estado', '')}".strip(" -"))

    def badge_chk(val: str) -> str:
        v = str(val or "").upper()
        if v in ("SIM", "OK"):
            return f'<span class="ok">{_h.escape(v)}</span>'
        if v in ("NÃO", "NAO", "NÃO OK", "NOK"):
            return f'<span class="nok">{_h.escape(v)}</span>'
        return f'<span class="na">{_h.escape(v or "-")}</span>'

    rows_emb = "".join(
        f"<tr><td>{_h.escape(lbl)}</td><td><b>{_h.escape(str(series.get(k) or '-'))}</b></td></tr>"
        for k, lbl in ITENS_EMBALAGEM_KONICA
    )

    blocos_html = ""
    for b in BLOCOS_CHECKLIST_KONICA:
        trs = "".join(
            f"<tr><td>{_h.escape(lbl)}</td><td style='width:80px;text-align:center;'>{badge_chk(checks.get(k, ''))}</td></tr>"
            for k, lbl in b["itens"]
        )
        blocos_html += f"""
        <div class="sec">
          <div class="sec-h">{_h.escape(b['titulo'])}</div>
          <table>{trs}</table>
        </div>"""

    rows_fontes = "".join(
        f"<tr><td>{_h.escape(lbl)}</td><td>{_h.escape(crit)}</td><td><b>{_h.escape(str((fontes.get(k) or {}).get('val') or '-'))} V</b></td><td style='text-align:center;'>{badge_chk((fontes.get(k) or {}).get('av', ''))}</td></tr>"
        for k, lbl, crit in FONTES_PCB01004
    )

    rows_prep = "".join(
        f"<tr><td>{_h.escape(lbl)}</td><td>{_h.escape(crit)}</td><td><b>{_h.escape(str((prep_aq.get(k) or {}).get('val') or '-'))} mV</b></td><td style='text-align:center;'>{badge_chk((prep_aq.get(k) or {}).get('av', ''))}</td></tr>"
        for k, lbl, crit in PREP_AQUECIMENTO
    )

    rows_aq = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[5]}</td><td><b>{_h.escape(str(aq_tp16.get(str(i)) or '-'))}</b></td><td><b>{_h.escape(str(aq_tp28.get(str(i)) or '-'))}</b></td></tr>"
        for i, r in enumerate(AQUECIMENTO_TUBO)
    )

    rows_cal = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]:.3f}</td><td>{r[4]:.3f}</td><td>{r[5]:.3f}</td><td>{'X' if r[6] else ''}</td><td>{'X' if r[7] else ''}</td><td><b>{_h.escape(str(cal_tp16.get(str(i)) or '-'))}</b></td></tr>"
        for i, r in enumerate(CALIBRACAO_CORRENTES)
    )

    rows_ap = "".join(
        f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]:.3f}</td><td>{r[4]:.3f}</td><td>{r[5]:.3f}</td><td>{'X' if r[6] else ''}</td><td>{'X' if r[7] else ''}</td><td><b>{_h.escape(str(ap_tp16.get(str(i)) or '-'))}</b></td></tr>"
        for i, r in enumerate(ALTA_POTENCIA)
    )

    ass_img_tag = f'<img src="{ass_cli_img}" style="max-height:46px;max-width:180px;" />' if ass_cli_img.startswith("data:image") else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>FR_SE00003_03 — Instalação Raios X Konica (OS #{_h.escape(str(os_id))})</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 9.5px; color: #0f172a; margin: 14px; background: #f8fafc; }}
  .wrap {{ max-width: 820px; margin: 0 auto; background: #fff; padding: 16px; border: 1px solid #cbd5e1; }}
  .top-bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }}
  .hdr {{ border: 1.5px solid #002b54; display:grid; grid-template-columns: 120px 1fr 120px; text-align:center; margin-bottom:10px; }}
  .hdr div {{ padding: 6px; border-right: 1px solid #002b54; display:flex; flex-direction:column; justify-content:center; }}
  .hdr div:last-child {{ border-right:none; }}
  .sec {{ margin-bottom: 10px; page-break-inside: avoid; }}
  .sec-h {{ background: #64748b; color: #fff; font-weight: 800; padding: 4px 8px; font-size: 9.5px; text-transform: uppercase; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 3.5px 6px; text-align: left; }}
  th {{ background: #f1f5f9; font-weight: 700; }}
  .ok {{ background:#dcfce7; color:#15803d; padding:1px 6px; border-radius:4px; font-weight:800; }}
  .nok {{ background:#fee2e2; color:#b91c1c; padding:1px 6px; border-radius:4px; font-weight:800; }}
  .na {{ color:#64748b; }}
  .page-break {{ page-break-before: always; margin-top: 14px; }}
  @media print {{ @page {{ size: A4; margin: 8mm; }} body {{ background:#fff; margin:0; }} .wrap {{ border:none; padding:0; }} .no-print {{ display:none; }} }}
</style></head>
<body>
  <div class="top-bar no-print">
    <b>📋 Relatório Oficial de Instalação Konica Minolta — FR_SE00003_03 (OS #{_h.escape(str(os_id))})</b>
    <button onclick="window.print()" style="background:#002b54;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-weight:bold;cursor:pointer;">🖨️ Imprimir / Salvar PDF</button>
  </div>
  <div class="wrap">
    <div class="hdr">
      <div><b>FR_SE00003_03</b><span>OS #{_h.escape(str(os_id))}</span></div>
      <div><b>FORMULÁRIO DE REGISTRO</b><span>RELATÓRIO DE INSTALAÇÃO E ACEITAÇÃO EQUIPAMENTO DE RAIOS X</span></div>
      <div><b style="color:#0369a1;">KONICA MINOLTA</b><span>EMED Service</span></div>
    </div>

    <div class="sec">
      <div class="sec-h">Informações do Cliente &amp; Representante</div>
      <table>
        <tr><td><b>Instituição:</b> {g('cliente')}</td><td><b>Cidade/UF:</b> {g('cidade')} / {g('estado')}</td></tr>
        <tr><td><b>Endereço:</b> {g('endereco')}</td><td><b>Contato / Fone:</b> {g('contato')} • {g('telefone')}</td></tr>
        <tr><td><b>Representante:</b> EMED ELETROMEDICINA</td><td><b>Instalador:</b> {g('instalador')}</td></tr>
        <tr><td><b>Modelo:</b> {g('modelo')}</td><td><b>Gerador / Grade:</b> {g('gerador_kv_tipo')} • {g('gerador_kw_tipo')} • Grade {g('grade_tipo')}</td></tr>
      </table>
    </div>

    <div class="sec">
      <div class="sec-h">Relação de Itens Identificados na Embalagem &amp; Nº de Série</div>
      <table><tr><th>Item</th><th style="width:180px;">Nº de Série</th></tr>{rows_emb}</table>
    </div>

    <div class="sec">
      <div class="sec-h">Entrada de Rede Local (Pág. 3)</div>
      <table>
        <tr><td><b>R-S:</b> {_h.escape(str(med.get('rs_v') or '-'))} V</td><td><b>R-T:</b> {_h.escape(str(med.get('rt_v') or '-'))} V</td><td><b>S-T:</b> {_h.escape(str(med.get('st_v') or '-'))} V</td><td><b>Rede:</b> {g('rede_tipo')}</td></tr>
        <tr><td><b>Cabo Subestação->Quadro:</b> {_h.escape(str(med.get('bitola_sub') or '-'))}</td><td><b>Quadro->Equip:</b> {_h.escape(str(med.get('bitola_eq') or '-'))}</td><td><b>Terra Equip:</b> {_h.escape(str(med.get('bitola_terra_eq') or '-'))}</td><td><b>Neutro:</b> {_h.escape(str(med.get('bitola_neutro') or '-'))}</td></tr>
      </table>
    </div>

    {blocos_html}

    <div class="sec">
      <div class="sec-h">Aferição do Gerador — Instrumentos &amp; Fontes PCB01004 (Pág. 6)</div>
      <table>
        <tr><td><b>Multímetro:</b> {_h.escape(str(inst.get('multimetro') or '-'))}</td><td><b>Validade:</b> {_h.escape(str(inst.get('multimetro_val') or '-'))}</td></tr>
        <tr><td><b>Osciloscópio:</b> {_h.escape(str(inst.get('osciloscopio') or '-'))}</td><td><b>Validade:</b> {_h.escape(str(inst.get('osciloscopio_val') or '-'))}</td></tr>
      </table>
      <table style="margin-top:4px;"><tr><th>Item</th><th>Critério</th><th>Resultado</th><th>Avaliação</th></tr>{rows_fontes}</table>
      <table style="margin-top:4px;"><tr><th>Preparação Aquecimento</th><th>Critério</th><th>TP16</th><th>Avaliação</th></tr>{rows_prep}</table>
    </div>

    <div class="sec">
      <div class="sec-h">Aquecimento do Tubo de Raios-X (Pág. 7)</div>
      <table><tr><th>mA</th><th>kV</th><th>ms</th><th>Disp</th><th>TP16 Ref</th><th>TP28 Ref</th><th>TP16 Medido (V)</th><th>TP28 Medido (V)</th></tr>{rows_aq}</table>
    </div>

    <div class="sec">
      <div class="sec-h">Calibração das Correntes do Tubo — Tubo {g('tubo_tipo')} (Págs. 7-8)</div>
      <table><tr><th>mA</th><th>kV</th><th>ms</th><th>Inf</th><th>Central</th><th>Sup</th><th>125kV</th><th>150kV</th><th>TP16 Medido (V)</th></tr>{rows_cal}</table>
    </div>

    <div class="sec">
      <div class="sec-h">Verificação das Técnicas de Alta Potência (Pág. 9)</div>
      <table><tr><th>mA</th><th>kV</th><th>ms</th><th>Inf</th><th>Central</th><th>Sup</th><th>125kV</th><th>150kV</th><th>TP16 Medido (V)</th></tr>{rows_ap}</table>
    </div>

    <div class="sec">
      <div class="sec-h">Relatório de Intercorrências &amp; Aceite (Pág. 10)</div>
      <div style="border:1px solid #cbd5e1;padding:6px;min-height:30px;margin-bottom:6px;">{g('intercorrencias', 'Sem intercorrências registradas.')}</div>
      <table>
        <tr><th>Instalador do Conjunto Radiológico</th><th>Proprietário Responsável</th></tr>
        <tr><td>Nome: <b>{ass_tec_nome}</b><br/>Data: {dt_aceite}</td><td>Nome: <b>{ass_cli_nome}</b><br/>Data: {dt_aceite}<br/>{ass_img_tag}</td></tr>
      </table>
    </div>

    <div class="page-break">
      <div class="hdr"><div><b>FR_SE00003_02</b><span>Pág. 11</span></div><div><b>TERMO DE ACEITE SALA</b><span>RDC 611/2022 • RDC 50 • RDC 307 • RDC 51</span></div><div><b style="color:#0369a1;">KONICA MINOLTA</b></div></div>
      <p style="line-height:1.45;">Caso a estrutura onde o equipamento será instalado não esteja de acordo com as especificações mínimas indicadas pelo fabricante e em conformidade com a RDC Nº 611/2022 e RDC 50/2002, o cliente declara estar ciente das possíveis limitações que a falta de espaço pode causar na utilização do equipamento e eventuais exigências dos órgãos de fiscalização, responsabilizando-se por adequações futuras.</p>
      <p><b>Local:</b> {local_aceite} &nbsp;&nbsp; <b>Data:</b> {dt_aceite} &nbsp;&nbsp; <b>Responsável:</b> {ass_cli_nome} &nbsp;&nbsp; <b>Doc:</b> {g('aceite_sala_doc', '-')}</p>
      {ass_img_tag}
      <hr style="margin:14px 0;border:none;border-top:1px dashed #cbd5e1;"/>
      <div class="hdr"><div><b>FR_SE00003_02</b><span>Pág. 12</span></div><div><b>TERMO DE ACEITE REDE ELÉTRICA</b><span>NBR 5410 • NBR 13534 • NBR IEC 60601-1</span></div><div><b style="color:#0369a1;">KONICA MINOLTA</b></div></div>
      <p style="line-height:1.45;">Caso a estrutura de rede elétrica onde o equipamento será instalado não esteja de acordo com as especificações mínimas indicadas pelo fabricante e normas NBR 5410, NBR 13534 e NBR IEC 60601-1, o cliente declara estar ciente das possíveis falhas intermitentes ou danos ao equipamento e da necessidade de adequação elétrica para garantia plena.</p>
      <p><b>Local:</b> {local_aceite} &nbsp;&nbsp; <b>Data:</b> {dt_aceite} &nbsp;&nbsp; <b>Responsável:</b> {ass_cli_nome} &nbsp;&nbsp; <b>Doc:</b> {g('aceite_rede_doc', '-')}</p>
      {ass_img_tag}
    </div>
  </div>
</body></html>"""
