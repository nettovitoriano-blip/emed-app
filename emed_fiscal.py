# emed_fiscal.py – Módulo de Emissão Fiscal (modo simulação)

"""Este módulo implementa a emissão de notas fiscais de forma desacoplada e simulada.
Ele consome os dados existentes no banco SQLite via `emed_core.get_db_connection` e
persiste as notas em uma nova tabela `notas_fiscais`.  A primeira versão usa um
`MockProvider` que gera XML/HTML de teste e simula respostas da SEFAZ.  Quando o
sistema estiver pronto para produção basta substituir o provider por uma
implementação real que assine o XML com o certificado A1 e envie ao web‑service
da SEFAZ.
"""

import os
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Dependência opcional: Streamlit – será importado apenas se estiver disponível
# ---------------------------------------------------------------------------
try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None  # type: ignore

# ---------------------------------------------------------------------------
# Helper – lazy import de get_db_connection de emed_core
# ---------------------------------------------------------------------------
def _get_db_connection(db_name: str) -> sqlite3.Connection:
    """Importa dinamicamente ``get_db_connection`` de ``emed_core``.
    Isso evita erro de importação caso o arquivo ainda não exista.
    """
    try:
        from emed_core import get_db_connection  # type: ignore
        return get_db_connection(db_name)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Não foi possível importar get_db_connection de emed_core. "
            f"Erro original: {exc}"
        )

# ---------------------------------------------------------------------------
# Provider interface – contrato para implementações reais ou simuladas
# ---------------------------------------------------------------------------
class FiscalProvider:
    """Interface básica para provedores fiscais."""

    def gerar_pre_nota(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        """Gera arquivos de pré‑nota (XML e HTML) sem enviá‑los.
        Retorna dict com chaves ``xml_path`` e ``html_path``.
        """
        raise NotImplementedError

    def enviar_nota(self, xml_path: str) -> Dict[str, Any]:
        """Envia a nota (real ou simulada) e devolve status.
        Espera‑se ao menos as chaves: ``status``, ``numero_nf``, ``chave_acesso``
        e ``protocolo``.
        """
        raise NotImplementedError

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        raise NotImplementedError

    def cancelar_nota(self, chave_acesso: str) -> bool:
        raise NotImplementedError

# ---------------------------------------------------------------------------
# MockProvider – implementação de simulação local
# ---------------------------------------------------------------------------
class MockProvider(FiscalProvider):
    """Provider que gera arquivos locais e devolve respostas estáticas."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent / "scratch"
        self.xml_dir = self.base_dir / "xml"
        self.html_dir = self.base_dir / "html"
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def gerar_pre_nota(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        xml_content = f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<NotaFiscal>\n  <OSId>{os_id}</OSId>\n  <Cliente>{payload.get('cliente')}</Cliente>\n  <CNPJ>{payload.get('cnpj')}</CNPJ>\n  <ValorServicos>{payload.get('valor_servicos'):.2f}</ValorServicos>\n  <ValorPecas>{payload.get('valor_pecas'):.2f}</ValorPecas>\n</NotaFiscal>\n"
        xml_path = self.xml_dir / f"pre_nota_{os_id}.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        html_content = f"<html><body><h2>Pré‑Nota Fiscal – OS {os_id}</h2>" \
                       f"<p>Cliente: {payload.get('cliente')}</p>" \
                       f"<p>CNPJ: {payload.get('cnpj')}</p>" \
                       f"<p>Valor Serviços: R$ {payload.get('valor_servicos'):.2f}</p>" \
                       f"<p>Valor Peças: R$ {payload.get('valor_pecas'):.2f}</p>" \
                       f"</body></html>"
        html_path = self.html_dir / f"pre_nota_{os_id}.html"
        html_path.write_text(html_content, encoding="utf-8")
        return {"xml_path": str(xml_path), "html_path": str(html_path)}

    def enviar_nota(self, xml_path: str) -> Dict[str, Any]:
        numero_nf = f"{uuid.uuid4().int % 1_000_000_000:09d}"
        chave = str(uuid.uuid4())
        protocolo = str(uuid.uuid4())
        return {"status": "AUTORIZADA", "numero_nf": numero_nf, "chave_acesso": chave, "protocolo": protocolo}

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        return {"status": "AUTORIZADA", "chave_acesso": chave_acesso}

    def cancelar_nota(self, chave_acesso: str) -> bool:
        return True

# ---------------------------------------------------------------------------
# FiscalManager – orquestra criação, persistência e ciclo de vida das notas
# ---------------------------------------------------------------------------
class FiscalManager:
    def __init__(self, db_name: str, provider: Optional[FiscalProvider] = None):
        self.db_name = db_name
        self.provider = provider or MockProvider()
        self._ensure_table()

    def _ensure_table(self) -> None:
        create_sql = """
        CREATE TABLE IF NOT EXISTS notas_fiscais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            os_id INTEGER NOT NULL,
            cliente TEXT NOT NULL,
            cnpj_tomador TEXT NOT NULL,
            tipo_nota TEXT NOT NULL,
            natureza_operacao TEXT,
            codigo_servico_iss TEXT,
            cfop TEXT,
            ncm TEXT,
            valor_servicos REAL NOT NULL,
            valor_pecas REAL NOT NULL,
            valor_desconto REAL DEFAULT 0,
            aliquota_iss REAL,
            retencoes_federais TEXT,
            valor_liquido REAL,
            status_fiscal TEXT NOT NULL,
            numero_nf TEXT,
            serie TEXT,
            chave_acesso TEXT,
            xml_path TEXT,
            pdf_path TEXT,
            protocolo_autorizacao TEXT,
            data_emissao TEXT,
            sync_hash_fiscal TEXT UNIQUE,
            criado_em TEXT DEFAULT (datetime('now')),
            atualizado_em TEXT DEFAULT (datetime('now'))
        );
        """
        with _get_db_connection(self.db_name) as conn:
            conn.execute(create_sql)
            conn.commit()

    def _hash_fiscal(self, os_id: int, tipo_nota: str, data_emissao: str) -> str:
        return hashlib.sha256(f"{os_id}|{tipo_nota}|{data_emissao}".encode('utf-8')).hexdigest()

    def _fetch_os_data(self, os_id: int) -> Dict[str, Any]:
        query = """SELECT cliente, cnpj, valor_os FROM clientes_equipamentos WHERE id = ?"""
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute(query, (os_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"OS id={os_id} não encontrada.")
            cliente, cnpj, valor_os = row
        v_total = float(valor_os or 0)
        return {
            "cliente": cliente,
            "cnpj": cnpj,
            "valor_servicos": v_total,
            "valor_pecas": 0.0,
        }

    def create_pre_nota(self, os_id: int, tipo_nota: str = "NFSE") -> Dict[str, Any]:
        """Cria a pré‑nota, persiste com status PROCESSANDO e simula envio.
        Garante idempotência via ``sync_hash_fiscal``.
        """
        data_emissao = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        sync_hash = self._hash_fiscal(os_id, tipo_nota, data_emissao)
        # Verifica existência pré‑via hash
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT * FROM notas_fiscais WHERE sync_hash_fiscal = ?", (sync_hash,))
            existing = cur.fetchone()
            if existing:
                col_names = [d[0] for d in cur.description]
                return dict(zip(col_names, existing))
        payload = self._fetch_os_data(os_id)
        payload.update({"tipo_nota": tipo_nota, "data_emissao": data_emissao})
        gen = self.provider.gerar_pre_nota(os_id, payload)
        xml_path = gen["xml_path"]
        # Insere registro inicial
        insert_sql = """
        INSERT INTO notas_fiscais (
            os_id, cliente, cnpj_tomador, tipo_nota, valor_servicos, valor_pecas,
            status_fiscal, xml_path, sync_hash_fiscal, data_emissao
        ) VALUES (?,?,?,?,?,?,?,?,?,?)
        """
        with _get_db_connection(self.db_name) as conn:
            conn.execute(insert_sql, (
                os_id,
                payload["cliente"],
                payload["cnpj"],
                tipo_nota,
                payload["valor_servicos"],
                payload["valor_pecas"],
                "PROCESSANDO",
                xml_path,
                sync_hash,
                data_emissao,
            ))
            conn.commit()
        # Simula envio imediato
        send_res = self.provider.enviar_nota(xml_path)
        update_sql = """
        UPDATE notas_fiscais SET
            status_fiscal = ?,
            numero_nf = ?,
            chave_acesso = ?,
            protocolo_autorizacao = ?,
            data_emissao = ?,
            atualizado_em = datetime('now')
        WHERE sync_hash_fiscal = ?
        """
        with _get_db_connection(self.db_name) as conn:
            conn.execute(update_sql, (
                send_res["status"],
                send_res["numero_nf"],
                send_res["chave_acesso"],
                send_res["protocolo"],
                data_emissao,
                sync_hash,
            ))
            conn.commit()
        # Retorna linha completa
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT * FROM notas_fiscais WHERE sync_hash_fiscal = ?", (sync_hash,))
            row = cur.fetchone()
            col_names = [d[0] for d in cur.description]
            return dict(zip(col_names, row))

    def cancelar_nota(self, chave_acesso: str) -> bool:
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT id FROM notas_fiscais WHERE chave_acesso = ?", (chave_acesso,))
            if not cur.fetchone():
                raise ValueError(f"Nota com chave {chave_acesso} não encontrada.")
        if self.provider.cancelar_nota(chave_acesso):
            with _get_db_connection(self.db_name) as conn:
                conn.execute("UPDATE notas_fiscais SET status_fiscal = ?, atualizado_em = datetime('now') WHERE chave_acesso = ?", ("CANCELADA", chave_acesso))
                conn.commit()
            return True
        return False

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        return self.provider.consultar_status(chave_acesso)

# ---------------------------------------------------------------------------
# UI – ponto de entrada para Streamlit
# ---------------------------------------------------------------------------
def render_modulo_fiscal(db_name: str, usuario_atual: str, perfil_atual: str) -> None:
    if st is None:
        raise RuntimeError("Streamlit não está instalado – UI indisponível.")
    st.title(":page_facing_up: Módulo Fiscal – Emissão Simulada")
    manager = FiscalManager(db_name)

    # Lista OS concluídas
    sql_os = """SELECT id, cliente, equipamento FROM clientes_equipamentos WHERE UPPER(status) LIKE '%CONCLU%' ORDER BY id DESC"""
    with _get_db_connection(db_name) as conn:
        rows = conn.execute(sql_os).fetchall()
    if not rows:
        st.info("Nenhuma OS concluída encontrada para emissão de nota.")
        return
    options = {f"OS #{r[0]} – {r[1]} ({r[2]})": r[0] for r in rows}
    selected_label = st.selectbox("Selecione a OS", list(options.keys()))
    os_id = options[selected_label]

    if st.button("Emitir Nota Fiscal (Simulação)"):
        try:
            nota = manager.create_pre_nota(os_id)
            st.success(f"Nota emitida! Número: {nota.get('numero_nf')} – Chave: {nota.get('chave_acesso')}")
            html_path = nota.get('xml_path').replace('xml', 'html').replace('.xml', '.html')
            if os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    st.markdown(f.read(), unsafe_allow_html=True)
        except Exception as exc:
            st.error(f"Erro ao emitir nota: {exc}")

    st.subheader(":mag_right: Consulta / Cancelamento")
    chave = st.text_input("Chave de acesso da nota")
    if st.button("Consultar Status") and chave:
        st.json(manager.consultar_status(chave))
    if st.button("Cancelar Nota") and chave:
        try:
            if manager.cancelar_nota(chave):
                st.success("Nota cancelada com sucesso.")
            else:
                st.warning("Cancelamento não concluído.")
        except Exception as e:
            st.error(str(e))

# ---------------------------------------------------------------------------
# Execução direta para depuração rápida
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Teste rápido do módulo fiscal (simulação)")
    parser.add_argument("--db", required=True, help="Caminho para emed_dados.db")
    args = parser.parse_args()
    fm = FiscalManager(args.db)
    print("FiscalManager iniciado. Use os métodos do objeto para testes.")
