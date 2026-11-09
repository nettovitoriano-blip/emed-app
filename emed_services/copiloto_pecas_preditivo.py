# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Copiloto Preditivo de Peças & Almoxarifado Inteligente
Cruza o defeito relatado/sintoma da máquina com o modelo e sugere automaticamente
as peças compatíveis em estoque com quantidade, localização e probabilidade de uso.
"""

import sqlite3
import re
from typing import Dict, Any, List

# Matriz de correlação clínica de falhas em diagnóstico por imagem
MAPA_CORRELACAO_DEFEITOS = {
    "TUBO": ["AMPOLA", "FILAMENTO", "ALTA TENSÃO", "CABO", "ÓLEO", "COLIMADOR", "RELE"],
    "DISPAR": ["AMPOLA", "RELE", "PLACA", "CABO", "BATERIA", "CONTATOR", "FUSÍVEL"],
    "ANODO": ["ROTOR", "STATOR", "BOBINA", "ROLAMENTO", "CABO", "CAPACITOR"],
    "GERADOR": ["PLACA", "INVERSOR", "IGBT", "CAPACITOR", "RELE", "FUSÍVEL", "FONTE"],
    "SLIP RING": ["ESCOVA", "BRUSHBLOCK", "PISTA", "LIMPEZA", "DESOXIDANTE"],
    "MESA": ["MOTOR", "POTENCIÔMETRO", "FUSÍVEL", "FREIO", "CABO", "SENSOR"],
    "COLIMADOR": ["LÂMPADA", "ESPELHO", "OBTURADOR", "TIMER", "FONTE"],
    "COMPRESSOR": ["PEDAL", "CÉLULA", "POTENCIÔMETRO", "CABO", "FUSÍVEL"],
    "ARTEFATO": ["DETECTOR", "DAS", "CABO ÓPTICO", "CALIBRAÇÃO", "FONTE"],
    "RUÍDO": ["ROLAMENTO", "COOLER", "VENTOINHA", "FONTE", "GRAXA"],
    "AQUECIMENTO": ["COOLER", "BOMBA", "ÓLEO", "RADIADOR", "TERMOSTATO", "FILTRO"]
}

def sugerir_pecas_por_defeito(db_name: str, equipamento: str, defeito_sintoma: str) -> List[Dict[str, Any]]:
    """Busca no estoque as peças recomendadas com base no sintoma e modelo."""
    sugestoes = []
    texto_busca = f"{equipamento} {defeito_sintoma}".upper()
    
    # Identifica termos chave de busca
    palavras_chave = []
    for gatilho, termos in MAPA_CORRELACAO_DEFEITOS.items():
        if gatilho in texto_busca:
            palavras_chave.extend(termos)

    # Se não achou gatilho específico, usa palavras da queixa
    if not palavras_chave:
        palavras_chave = [w for w in re.findall(r'\b[A-Z]{3,}\b', texto_busca) if w not in ["NAO", "COM", "PARA", "ESTA", "PELO", "QUE"]]

    palavras_chave = list(dict.fromkeys(palavras_chave))[:6]

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            
            for termo in palavras_chave:
                cur.execute("""
                    SELECT id, codigo, nome_peca, quantidade, preco_unitario, localizacao, tipo_item
                    FROM estoque_pecas
                    WHERE nome_peca LIKE ?
                    ORDER BY quantidade DESC LIMIT 3
                """, (f"%{termo}%",))
                
                for r in cur.fetchall():
                    # Evita duplicatas
                    if not any(s["id"] == r[0] for s in sugestoes):
                        sugestoes.append({
                            "id": r[0],
                            "codigo": r[1] or "PEC-EMED",
                            "nome": r[2] or "Peça",
                            "saldo": r[3] or 0,
                            "preco": r[4] or 0.0,
                            "localizacao": r[5] or "ALMOXARIFADO CENTRAL - FORTALEZA",
                            "tipo": r[6] or "PEÇA",
                            "compatibilidade": "ALTA" if r[3] > 0 else "SOB ENCOMENDA",
                            "termo_correlato": termo
                        })
            
            # Se ainda tem poucas sugestões, busca itens de consumo comum
            if len(sugestoes) < 3:
                cur.execute("""
                    SELECT id, codigo, nome_peca, quantidade, preco_unitario, localizacao, tipo_item
                    FROM estoque_pecas
                    WHERE quantidade > 0 AND (nome_peca LIKE '%CABO%' OR nome_peca LIKE '%RELE%' OR nome_peca LIKE '%BATERIA%')
                    LIMIT 3
                """)
                for r in cur.fetchall():
                    if not any(s["id"] == r[0] for s in sugestoes):
                        sugestoes.append({
                            "id": r[0],
                            "codigo": r[1] or "PEC-EMED",
                            "nome": r[2] or "Peça",
                            "saldo": r[3] or 0,
                            "preco": r[4] or 0.0,
                            "localizacao": r[5] or "ALMOXARIFADO CENTRAL",
                            "tipo": r[6] or "PEÇA",
                            "compatibilidade": "GERAL",
                            "termo_correlato": "CONSUMO"
                        })
    except Exception as e:
        print(f"Erro no copiloto de peças: {e}")

    return sugestoes[:6]
