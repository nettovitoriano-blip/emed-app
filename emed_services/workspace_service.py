# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Serviço de Workspace do Técnico & Fábrica de ITs
Permite aos técnicos salvar notas de campo no estilo Google Keep (cards maleáveis com fotos)
e converter instantaneamente essas notas em Instruções de Trabalho (ITs) formais para aprovação.
"""

import sqlite3
import datetime
import json
from typing import List, Dict, Any, Optional

CORES_CARDS_DISPONIVEIS = {
    "Padrão Escuro": "#1e293b",
    "Azul Petróleo": "#0e4b5c",
    "Azul Marinho": "#1e3a8a",
    "Verde Sucesso": "#064e3b",
    "Amarelo Alerta": "#713f12",
    "Vermelho Crítico": "#7f1d1d",
    "Roxo Inovação": "#581c87"
}

def garantir_tabelas_workspace(db_name: str):
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workspace_tecnico_notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tecnico TEXT NOT NULL,
                titulo TEXT,
                conteudo TEXT,
                equipamento_modelo TEXT,
                modalidade TEXT,
                fotos_json TEXT,
                cor_card TEXT DEFAULT '#1e293b',
                tags TEXT,
                status TEXT DEFAULT 'RASCUNHO',
                data_criacao TEXT,
                data_atualizacao TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS it_rascunhos_desenvolvimento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nota_origem_id INTEGER,
                codigo_it TEXT,
                titulo TEXT,
                equipamento TEXT,
                autor_tecnico TEXT,
                conteudo_markdown TEXT,
                conteudo_html TEXT,
                status TEXT DEFAULT 'EM_REVISAO',
                aprovado_por TEXT,
                data_envio TEXT,
                data_aprovacao TEXT
            )
        """)
        conn.commit()

def salvar_nota_workspace(
    db_name: str,
    tecnico: str,
    titulo: str,
    conteudo: str,
    equipamento_modelo: str = "",
    modalidade: str = "Geral",
    fotos_list: Optional[List[str]] = None,
    cor_card: str = "#1e293b",
    tags: str = "",
    nota_id: Optional[int] = None
) -> Dict[str, Any]:
    garantir_tabelas_workspace(db_name)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    fotos_json = json.dumps(fotos_list or [])

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        if nota_id:
            cur.execute("""
                UPDATE workspace_tecnico_notas
                SET titulo = ?, conteudo = ?, equipamento_modelo = ?, modalidade = ?,
                    fotos_json = ?, cor_card = ?, tags = ?, data_atualizacao = ?
                WHERE id = ?
            """, (titulo, conteudo, equipamento_modelo, modalidade, fotos_json, cor_card, tags, agora, nota_id))
            target_id = nota_id
            acao = "atualizada"
        else:
            cur.execute("""
                INSERT INTO workspace_tecnico_notas (
                    tecnico, titulo, conteudo, equipamento_modelo, modalidade,
                    fotos_json, cor_card, tags, status, data_criacao, data_atualizacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RASCUNHO', ?, ?)
            """, (tecnico, titulo, conteudo, equipamento_modelo, modalidade, fotos_json, cor_card, tags, agora, agora))
            target_id = cur.lastrowid
            acao = "criada"
        conn.commit()

    return {"ok": True, "id": target_id, "msg": f"Nota {acao} com sucesso!"}

def listar_notas_workspace(
    db_name: str,
    tecnico: Optional[str] = None,
    modalidade: Optional[str] = None,
    busca: Optional[str] = None
) -> List[Dict[str, Any]]:
    garantir_tabelas_workspace(db_name)
    query = "SELECT id, tecnico, titulo, conteudo, equipamento_modelo, modalidade, fotos_json, cor_card, tags, status, data_criacao, data_atualizacao FROM workspace_tecnico_notas WHERE status != 'ARQUIVADO'"
    params = []

    if tecnico and tecnico.upper() != "TODOS":
        query += " AND UPPER(tecnico) = ?"
        params.append(tecnico.strip().upper())
    if modalidade and modalidade.upper() not in ("TODAS", "GERAL"):
        query += " AND UPPER(modalidade) = ?"
        params.append(modalidade.strip().upper())
    if busca and busca.strip():
        query += " AND (UPPER(titulo) LIKE ? OR UPPER(conteudo) LIKE ? OR UPPER(equipamento_modelo) LIKE ? OR UPPER(tags) LIKE ?)"
        b = f"%{busca.strip().upper()}%"
        params.extend([b, b, b, b])

    query += " ORDER BY id DESC"

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()

    notas = []
    for r in rows:
        try:
            fotos = json.loads(r[6]) if r[6] else []
        except:
            fotos = []
        notas.append({
            "id": r[0],
            "tecnico": r[1],
            "titulo": r[2] or "Sem título",
            "conteudo": r[3] or "",
            "equipamento_modelo": r[4] or "Geral",
            "modalidade": r[5] or "Geral",
            "fotos": fotos,
            "cor_card": r[7] or "#1e293b",
            "tags": r[8] or "",
            "status": r[9] or "RASCUNHO",
            "data_criacao": r[10],
            "data_atualizacao": r[11]
        })
    return notas

def excluir_nota_workspace(db_name: str, nota_id: int) -> bool:
    garantir_tabelas_workspace(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM workspace_tecnico_notas WHERE id = ?", (nota_id,))
        conn.commit()
    return True

def converter_nota_em_it_oficial(db_name: str, nota_id: int, autor_tecnico: str) -> Dict[str, Any]:
    garantir_tabelas_workspace(db_name)
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    ano = datetime.datetime.now().year

    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT titulo, conteudo, equipamento_modelo, modalidade, fotos_json FROM workspace_tecnico_notas WHERE id = ?", (nota_id,))
        nota = cur.fetchone()
        if not nota:
            return {"ok": False, "msg": "Nota de campo não localizada."}

        titulo_nota, conteudo_nota, eq_modelo, mod, fotos_raw = nota
        try:
            fotos = json.loads(fotos_raw) if fotos_raw else []
        except:
            fotos = []

        cur.execute("SELECT COUNT(*) FROM it_rascunhos_desenvolvimento")
        seq = cur.fetchone()[0] + 1
        codigo_it = f"IT-EMED-{ano}-{seq:03d}"

        markdown_it = f"""# EMED ELETROMEDICINA LTDA.
## INSTRUÇÃO DE TRABALHO TÉCNICA: {codigo_it}
### TÍTULO: {titulo_nota or 'PROCEDIMENTO TÉCNICO OPERACIONAL'}

---

**Equipamento Alvo:** {eq_modelo or 'Multimarca / Específico'}  
**Modalidade:** {mod or 'Engenharia Clínica'}  
**Autor do Procedimento:** {autor_tecnico}  
**Data de Elaboração:** {agora}  
**Status do Documento:** EM REVISÃO DA ENGENHARIA CLÍNICA  

---

### 1. OBJETIVO & APLICAÇÃO
Padronizar o método de intervenção técnica corretiva/preventiva para o equipamento **{eq_modelo}**, mitigando riscos operacionais e garantindo a conformidade biomédica.

### 2. SINTOMA / FALHA DE CAMPO OBSERVADA
{conteudo_nota}

### 3. FERRAMENTAL & EPIs OBRIGATÓRIOS
- Multímetro digital calibrado com pontas de prova de segurança Cat III;
- Pulseira antiestática e luvas de proteção;
- Conjunto de chaves de precisão (Torx, Phillips e Allen);
- Limpa-contatos isopropílico de secagem rápida;
- Kit de calibração biomédica específico da modalidade.

### 4. PROCEDIMENTO OPERACIONAL PASSO A PASSO
1. **Desenergização e Segurança:** Desligar a chave geral do equipamento e desconectar da rede elétrica hospitalar.
2. **Acesso ao Módulo Técnico:** Desmontar as carenagens de acesso com cautela para preservar os lacres de garantia.
3. **Inspeção Visual e Diagnóstico:**
   - Avaliar pontos de oxidação, folgas de aterramento e estado das conexões elétricas.
   - Conferir tensões secundárias da fonte de alimentação conforme especificação do manual de serviço.
4. **Execução do Ajuste / Reparo:**
   - Aplicar a correção técnica identificada em campo com rigor métrico.
5. **Remontagem e Testes Funcionais:**
   - Reconectar cabos internos garantindo o correto travamento dos cliques.
   - Executar checklist de segurança elétrica e teste funcional de liberação.

### 5. REGISTROS FOTOGRÁFICOS DE CAMPO
*Total de registros fotográficos capturados pelo técnico:* **{len(fotos)} evidência(s)** anexadas ao laudo digital.

### 6. CRITÉRIO DE ACEITE & VALIDAÇÃO
O equipamento somente será liberado para uso médico se atender integralmente:
- Parâmetros de calibração dentro da tolerância do fabricante (± 5%);
- Ausência de códigos de erro de boot;
- Teste de segurança elétrica e fuga de corrente aprovado.

---
*Documento gerado automaticamente pelo Sistema EMED a partir de nota de campo do técnico {autor_tecnico}.*
"""

        cur.execute("""
            INSERT INTO it_rascunhos_desenvolvimento (
                nota_origem_id, codigo_it, titulo, equipamento, autor_tecnico,
                conteudo_markdown, status, data_envio
            ) VALUES (?, ?, ?, ?, ?, ?, 'EM_REVISAO', ?)
        """, (nota_id, codigo_it, titulo_nota or f"Procedimento {eq_modelo}", eq_modelo, autor_tecnico, markdown_it, agora))
        it_id = cur.lastrowid

        cur.execute("UPDATE workspace_tecnico_notas SET status = 'CONVERTIDO_IT' WHERE id = ?", (nota_id,))
        conn.commit()

    return {
        "ok": True,
        "it_id": it_id,
        "codigo_it": codigo_it,
        "msg": f"Nova IT {codigo_it} gerada com sucesso e enviada para revisão da Engenharia!"
    }

def listar_rascunhos_its(db_name: str) -> List[Dict[str, Any]]:
    garantir_tabelas_workspace(db_name)
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, codigo_it, titulo, equipamento, autor_tecnico, status, data_envio, data_aprovacao, aprovado_por, conteudo_markdown FROM it_rascunhos_desenvolvimento ORDER BY id DESC")
        rows = cur.fetchall()

    return [{
        "id": r[0],
        "codigo_it": r[1],
        "titulo": r[2],
        "equipamento": r[3],
        "autor_tecnico": r[4],
        "status": r[5],
        "data_envio": r[6],
        "data_aprovacao": r[7],
        "aprovado_por": r[8],
        "conteudo_markdown": r[9]
    } for r in rows]

def aprovar_e_publicar_it(db_name: str, it_id: int, aprovador: str) -> Dict[str, Any]:
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    with sqlite3.connect(db_name) as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE it_rascunhos_desenvolvimento
            SET status = 'PUBLICADO',
                aprovado_por = ?,
                data_aprovacao = ?
            WHERE id = ?
        """, (aprovador, agora, it_id))
        conn.commit()
    return {"ok": True, "msg": f"IT #{it_id} aprovada e publicada no acervo oficial com sucesso!"}
