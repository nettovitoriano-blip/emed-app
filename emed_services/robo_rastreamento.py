# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Robô Autônomo de Rastreamento de Peças e Cargas (24x/dia)
Monitora pedidos de peças em trânsito (Correios, Azul Cargo, Braspress, etc.)
e dá entrada automática em estoque quando a entrega é concluída ou avisa retirada.
"""

import sqlite3
import datetime
from typing import Dict, Any, List

def garantir_schema_rastreio_completo(db_name: str):
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS robo_rastreio_historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                solicitacao_id INTEGER,
                codigo_rastreio TEXT,
                transportadora TEXT,
                status_encontrado TEXT,
                cidade TEXT,
                detalhes TEXT,
                deu_entrada_estoque INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def consultar_rastreio_online(codigo: str) -> Dict[str, Any]:
    """Consulta mock / online do rastreio de encomenda."""
    codigo = str(codigo or "").strip().upper()
    if not codigo:
        return {"entregue": False, "status": "SEM CÓDIGO", "cidade": "N/A"}
    if "ENTREGUE" in codigo:
        return {"entregue": True, "status": "Objeto entregue ao destinatário", "cidade": "Fortaleza / CE"}
    if "AEROPORTO" in codigo:
        return {"entregue": False, "status": "AGUARDANDO_RETIRADA", "cidade": "Fortaleza / CE"}
    return {"entregue": False, "status": "Em trânsito para a unidade de distribuição", "cidade": "Hub Logístico"}

def executar_ciclo_verificacao(db_name: str) -> Dict[str, Any]:
    garantir_schema_rastreio_completo(db_name)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    processados = 0
    entregues = 0

    try:
        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, codigo_rastreio, transportadora, peca_solicitada, quantidade FROM solicitacoes_pecas WHERE status_compra NOT IN ('ENTREGUE', 'CANCELADO') AND codigo_rastreio IS NOT NULL AND codigo_rastreio != ''")
            pedidos = cur.fetchall()

            for p in pedidos:
                ped_id, cod, transp, peca, qtd = p
                processados += 1
                info = consultar_rastreio_online(cod)
                status_txt = info.get("status", "Em trânsito")
                cidade = info.get("cidade", "Fortaleza / CE")

                if info.get("entregue"):
                    entregues += 1
                    cur.execute("UPDATE solicitacoes_pecas SET status_compra = 'ENTREGUE', status_pedido = 'ENTREGUE / DISPONÍVEL NO ESTOQUE' WHERE id = ?", (ped_id,))
                    cur.execute("INSERT INTO robo_rastreio_historico (data_hora, solicitacao_id, codigo_rastreio, transportadora, status_encontrado, cidade, detalhes, deu_entrada_estoque) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                                (agora, ped_id, cod, transp or "Transportadora", status_txt, cidade, f"Peça {peca} (Qtd: {qtd}) entrada automática"))
                else:
                    cur.execute("INSERT INTO robo_rastreio_historico (data_hora, solicitacao_id, codigo_rastreio, transportadora, status_encontrado, cidade, detalhes, deu_entrada_estoque) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                                (agora, ped_id, cod, transp or "Transportadora", status_txt, cidade, "Monitoramento em trânsito"))
            conn.commit()
    except Exception as e:
        print(f"Erro no ciclo do robo de rastreio: {e}")

    return {
        "ok": True,
        "ciclo": 1,
        "data_hora": agora,
        "itens_processados": processados,
        "itens_entregues": entregues
    }

def obter_status_robo(db_name: str) -> Dict[str, Any]:
    garantir_schema_rastreio_completo(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM robo_rastreio_historico")
        total = cur.fetchone()[0]
        cur.execute("SELECT data_hora, codigo_rastreio, status_encontrado FROM robo_rastreio_historico ORDER BY id DESC LIMIT 5")
        historico = cur.fetchall()

    return {
        "ativo": True,
        "frequencia": "24x/dia (a cada 60 min)",
        "total_verificacoes": total,
        "historico_recente": [{"data": h[0], "codigo": h[1], "status": h[2]} for h in historico]
    }

def gerar_mensagem_retirada_carga(db_name: str, ped_id: int) -> Dict[str, Any]:
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT peca_solicitada, quantidade, codigo_rastreio, transportadora FROM solicitacoes_pecas WHERE id = ?", (ped_id,))
        row = cur.fetchone()

    peca = row[0] if row else "Peça"
    qtd = row[1] if row else 1
    cod = row[2] if row else "N/A"
    msg = f"✈️ *EMED - GUIA DE RETIRADA DE CARGA*\n\n*Pedido:* #{ped_id}\n*Item:* {peca} (Qtd: {qtd})\n*AWB/Rastreio:* {cod}\n*Local:* Aeroporto Pinto Martins / TECA Cargas\n*Portador Autorizado:* Paulinho (EMED)"
    return {"ok": True, "pedido_id": ped_id, "mensagem_whatsapp": msg}

def confirmar_retirada_paulinho(db_name: str, ped_id: int, portador: str = "Paulinho") -> Dict[str, Any]:
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE solicitacoes_pecas
            SET status_compra = 'ENTREGUE',
                status_pedido = 'RETIRADO POR ' || ?,
                portador_retirada = ?,
                ultimo_rastreio_status = 'ENTREGUE_AO_PORTADOR',
                ultimo_rastreio_data = ?
            WHERE id = ?
        """, (portador, portador, agora, ped_id))
        conn.commit()
    return {"ok": True, "msg": f"Carga do Pedido #{ped_id} retirada com sucesso por {portador} e entrada efetuada!"}
