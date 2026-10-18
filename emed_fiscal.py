# emed_fiscal.py – Módulo de Emissão Fiscal Desacoplado (Modo Simulação / Homologação Local)

"""Módulo de emissão de notas fiscais (NFS-e / NF-e) desacoplado para o Sistema EMED.
Consome os dados existentes no banco SQLite via `emed_core.get_db_connection` e
persiste o ciclo de vida fiscal na tabela `notas_fiscais`.
"""

import os
import uuid
import hashlib
import sqlite3
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None  # type: ignore


def _get_db_connection(db_name: str):
    """Importa dinamicamente `get_db_connection` de `emed_core`."""
    from emed_core import get_db_connection
    return get_db_connection(db_name)


class FiscalProvider:
    """Interface Adapter para provedores fiscais (Focus NFe, WebmaniaBR, eNotas, Nuvem Fiscal ou Mock)."""

    def gerar_pre_nota(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        raise NotImplementedError

    def enviar_nota(self, xml_path: str) -> Dict[str, Any]:
        raise NotImplementedError

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        raise NotImplementedError

    def cancelar_nota(self, chave_acesso: str) -> bool:
        raise NotImplementedError


class MockProvider(FiscalProvider):
    """Provider de Homologação/Simulação Local que gera XML e Espelho HTML (DANFSE/DANFE)."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent / "uploads_os" / "fiscal"
        self.xml_dir = self.base_dir / "xml"
        self.html_dir = self.base_dir / "html"
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def gerar_pre_nota(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        val_srv = float(payload.get("valor_servicos", 0.0))
        val_pec = float(payload.get("valor_pecas", 0.0))
        val_desc = float(payload.get("valor_desconto", 0.0))
        aliq_iss = float(payload.get("aliquota_iss", 5.0))
        val_iss = round(val_srv * (aliq_iss / 100.0), 2)
        val_liq = round(max(0.0, (val_srv + val_pec) - val_desc - val_iss), 2)

        xml_content = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<NotaFiscalEmed tipo="{payload.get("tipo_nota", "NFSE")}">\n'
            f'  <OSId>{os_id}</OSId>\n'
            f'  <Cliente>{payload.get("cliente", "")}</Cliente>\n'
            f'  <CNPJ>{payload.get("cnpj", "")}</CNPJ>\n'
            f'  <Equipamento>{payload.get("equipamento", "")}</Equipamento>\n'
            f'  <Discriminacao>{payload.get("discriminacao", "")}</Discriminacao>\n'
            f'  <CodigoServicoISS>{payload.get("codigo_servico_iss", "14.01")}</CodigoServicoISS>\n'
            f'  <ValorServicos>{val_srv:.2f}</ValorServicos>\n'
            f'  <ValorPecas>{val_pec:.2f}</ValorPecas>\n'
            f'  <ValorDesconto>{val_desc:.2f}</ValorDesconto>\n'
            f'  <AliquotaISS>{aliq_iss:.2f}</AliquotaISS>\n'
            f'  <ValorLiquido>{val_liq:.2f}</ValorLiquido>\n'
            f'  <DataEmissao>{payload.get("data_emissao", "")}</DataEmissao>\n'
            f'</NotaFiscalEmed>\n'
        )
        xml_path = self.xml_dir / f"pre_nota_{os_id}.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        html_content = f"""
        <div style="background:#1c2541; border:2px solid #64dfdf; border-radius:10px; padding:18px; color:#ffffff; font-family:Arial, sans-serif; margin-top:12px;">
            <div style="display:flex; justify-content:space-between; border-bottom:1px solid #3a506b; padding-bottom:10px; margin-bottom:12px;">
                <div>
                    <h3 style="margin:0; color:#64dfdf;">🧾 ESPELHO PRÉ-NOTA FISCAL ({payload.get('tipo_nota', 'NFSE')}) — OS #{os_id}</h3>
                    <span style="font-size:12px; color:#94a3b8;">EMED ELETROMEDICINA — AMBIENTE DE HOMOLOGAÇÃO / SIMULAÇÃO</span>
                </div>
                <div style="text-align:right;">
                    <span style="background:#10b981; color:#0b132b; padding:4px 10px; border-radius:12px; font-weight:bold; font-size:12px;">AUTORIZADA (SIMULAÇÃO)</span>
                </div>
            </div>
            <p style="margin:4px 0;"><strong>Tomador / Hospital:</strong> {payload.get('cliente', 'N/D')} | <strong>CNPJ:</strong> {payload.get('cnpj', 'N/D')}</p>
            <p style="margin:4px 0;"><strong>Equipamento Atendido:</strong> {payload.get('equipamento', 'N/D')}</p>
            <p style="margin:4px 0;"><strong>Código Serviço LC 116 / CFOP:</strong> {payload.get('codigo_servico_iss', '14.01 - Manutenção de Equipamentos Médicos')}</p>
            <p style="margin:4px 0;"><strong>Discriminação Técnica:</strong> {payload.get('discriminacao', 'Serviço de engenharia clínica conforme OS.')}</p>
            <hr style="border:0; border-top:1px dashed #3a506b; margin:10px 0;">
            <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:10px;">
                <span><strong>Valor Serviços:</strong> R$ {val_srv:,.2f}</span>
                <span><strong>Valor Peças:</strong> R$ {val_pec:,.2f}</span>
                <span><strong>Desconto:</strong> R$ {val_desc:,.2f}</span>
                <span><strong>ISS ({aliq_iss:.1f}%):</strong> R$ {val_iss:,.2f}</span>
                <span style="color:#64dfdf; font-size:16px;"><strong>Valor Líquido NF: R$ {val_liq:,.2f}</strong></span>
            </div>
        </div>
        """
        html_path = self.html_dir / f"pre_nota_{os_id}.html"
        html_path.write_text(html_content, encoding="utf-8")
        return {"xml_path": str(xml_path), "html_path": str(html_path)}

    def enviar_nota(self, xml_path: str) -> Dict[str, Any]:
        numero_nf = f"{uuid.uuid4().int % 1_000_000_000:09d}"
        chave = str(uuid.uuid4())
        protocolo = f"PROT-{uuid.uuid4().hex[:12].upper()}"
        return {
            "status": "AUTORIZADA",
            "numero_nf": numero_nf,
            "chave_acesso": chave,
            "protocolo": protocolo,
        }

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        return {"status": "AUTORIZADA", "chave_acesso": chave_acesso}

    def cancelar_nota(self, chave_acesso: str) -> bool:
        return True


class FiscalManager:
    """Gerencia a emissão idempotente e o ciclo de vida circular das notas fiscais."""

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
            aliquota_iss REAL DEFAULT 5.0,
            retencoes_federais TEXT,
            valor_liquido REAL,
            status_fiscal TEXT NOT NULL,
            numero_nf TEXT,
            serie TEXT DEFAULT '1',
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

    def _hash_fiscal(self, os_id: int, tipo_nota: str) -> str:
        """Hash determinístico por OS e Tipo de Nota para garantir idempotência."""
        return hashlib.sha256(f"EMED_FISCAL|{os_id}|{tipo_nota.strip().upper()}".encode("utf-8")).hexdigest()

    def _fetch_os_data(self, os_id: int) -> Dict[str, Any]:
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("PRAGMA table_info(clientes_equipamentos)")
            colunas_existentes = {r[1] for r in cur.fetchall()}

            cur_os = conn.execute("SELECT * FROM clientes_equipamentos WHERE id = ?", (os_id,))
            row = cur_os.fetchone()
            if not row:
                raise ValueError(f"OS id={os_id} não encontrada.")
            col_names = [d[0] for d in cur_os.description]
            os_dict = dict(zip(col_names, row))

            cliente = str(os_dict.get("cliente") or "CLIENTE NÃO INFORMADO").strip()
            cnpj = str(os_dict.get("cnpj") or "00.000.000/0001-00").strip()
            if not cnpj or cnpj.lower() in ("nan", "none"):
                cnpj = "00.000.000/0001-00"

            equipamento = str(os_dict.get("equipamento") or "").strip()
            discriminacao = str(
                os_dict.get("servico_executado")
                or os_dict.get("pendencias")
                or f"Manutenção técnica no equipamento {equipamento}"
            ).strip()

            if "valor_servicos" in colunas_existentes:
                valor_servicos = float(os_dict.get("valor_servicos") or 0.0)
                valor_pecas = float(os_dict.get("valor_pecas") or 0.0)
            else:
                valor_total_os = float(os_dict.get("valor_os") or 0.0)
                valor_pecas = 0.0
                ref_peca = str(os_dict.get("peca_baixada_ref") or "").strip()
                if ":" in ref_peca:
                    try:
                        nome_p, qtd_p = ref_peca.split(":", 1)
                        cur_p = conn.execute(
                            "SELECT preco_custo, margem_avulso FROM estoque_pecas WHERE UPPER(nome_peca) = ?",
                            (nome_p.strip().upper(),),
                        )
                        rp = cur_p.fetchone()
                        if rp:
                            custo = float(rp[0] or 0.0)
                            margem = float(rp[1] or 60.0)
                            valor_pecas = round(custo * (1.0 + margem / 100.0) * int(qtd_p), 2)
                    except Exception:
                        valor_pecas = 0.0
                valor_servicos = max(0.0, round(valor_total_os - valor_pecas, 2))

        return {
            "cliente": cliente,
            "cnpj": cnpj,
            "equipamento": equipamento,
            "discriminacao": discriminacao,
            "valor_servicos": valor_servicos,
            "valor_pecas": valor_pecas,
        }

    def create_pre_nota(
        self,
        os_id: int,
        tipo_nota: str = "NFSE",
        valor_servicos_override: Optional[float] = None,
        valor_pecas_override: Optional[float] = None,
        valor_desconto: float = 0.0,
        aliquota_iss: float = 5.0,
        codigo_servico_iss: str = "14.01",
    ) -> Dict[str, Any]:
        """Cria e autoriza a nota fiscal de forma idempotente via `sync_hash_fiscal`.
        Se já existir uma nota AUTORIZADA para a mesma OS e tipo_nota, retorna o registro existente sem duplicar.
        Se a nota anterior estiver CANCELADA, permite reemissão atualizando o registro.
        """
        data_emissao = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sync_hash = self._hash_fiscal(os_id, tipo_nota)

        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT * FROM notas_fiscais WHERE sync_hash_fiscal = ?", (sync_hash,))
            existing = cur.fetchone()
            if existing:
                col_names = [d[0] for d in cur.description]
                existing_dict = dict(zip(col_names, existing))
                if existing_dict.get("status_fiscal") != "CANCELADA":
                    return existing_dict

        payload = self._fetch_os_data(os_id)
        if valor_servicos_override is not None:
            payload["valor_servicos"] = float(valor_servicos_override)
        if valor_pecas_override is not None:
            payload["valor_pecas"] = float(valor_pecas_override)

        val_srv = float(payload["valor_servicos"])
        val_pec = float(payload["valor_pecas"])
        val_iss = round(val_srv * (float(aliquota_iss) / 100.0), 2)
        val_liq = round(max(0.0, (val_srv + val_pec) - float(valor_desconto) - val_iss), 2)

        payload.update({
            "tipo_nota": tipo_nota,
            "data_emissao": data_emissao,
            "valor_desconto": float(valor_desconto),
            "aliquota_iss": float(aliquota_iss),
            "codigo_servico_iss": codigo_servico_iss,
            "valor_liquido": val_liq,
        })

        gen = self.provider.gerar_pre_nota(os_id, payload)
        xml_path = gen["xml_path"]
        send_res = self.provider.enviar_nota(xml_path)

        with _get_db_connection(self.db_name) as conn:
            conn.execute(
                """
                INSERT INTO notas_fiscais (
                    os_id, cliente, cnpj_tomador, tipo_nota, codigo_servico_iss,
                    valor_servicos, valor_pecas, valor_desconto, aliquota_iss, valor_liquido,
                    status_fiscal, numero_nf, chave_acesso, protocolo_autorizacao,
                    xml_path, sync_hash_fiscal, data_emissao, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(sync_hash_fiscal) DO UPDATE SET
                    valor_servicos = excluded.valor_servicos,
                    valor_pecas = excluded.valor_pecas,
                    valor_desconto = excluded.valor_desconto,
                    aliquota_iss = excluded.aliquota_iss,
                    valor_liquido = excluded.valor_liquido,
                    status_fiscal = excluded.status_fiscal,
                    numero_nf = excluded.numero_nf,
                    chave_acesso = excluded.chave_acesso,
                    protocolo_autorizacao = excluded.protocolo_autorizacao,
                    xml_path = excluded.xml_path,
                    data_emissao = excluded.data_emissao,
                    atualizado_em = datetime('now')
                """,
                (
                    os_id,
                    payload["cliente"],
                    payload["cnpj"],
                    tipo_nota,
                    codigo_servico_iss,
                    val_srv,
                    val_pec,
                    float(valor_desconto),
                    float(aliquota_iss),
                    val_liq,
                    send_res["status"],
                    send_res["numero_nf"],
                    send_res["chave_acesso"],
                    send_res["protocolo"],
                    xml_path,
                    sync_hash,
                    data_emissao,
                ),
            )

            cur = conn.execute("SELECT * FROM notas_fiscais WHERE sync_hash_fiscal = ?", (sync_hash,))
            row = cur.fetchone()
            col_names = [d[0] for d in cur.description]
            return dict(zip(col_names, row))

    def cancelar_nota(self, chave_acesso: str) -> bool:
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT id FROM notas_fiscais WHERE chave_acesso = ?", (chave_acesso.strip(),))
            if not cur.fetchone():
                raise ValueError(f"Nota com chave '{chave_acesso}' não encontrada.")
        if self.provider.cancelar_nota(chave_acesso.strip()):
            with _get_db_connection(self.db_name) as conn:
                conn.execute(
                    "UPDATE notas_fiscais SET status_fiscal = ?, atualizado_em = datetime('now') WHERE chave_acesso = ?",
                    ("CANCELADA", chave_acesso.strip()),
                )
            return True
        return False

    def consultar_status(self, chave_acesso: str) -> Dict[str, Any]:
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute(
                "SELECT numero_nf, tipo_nota, cliente, valor_liquido, status_fiscal, protocolo_autorizacao, data_emissao "
                "FROM notas_fiscais WHERE chave_acesso = ?",
                (chave_acesso.strip(),),
            )
            row = cur.fetchone()
            if row:
                return {
                    "numero_nf": row[0],
                    "tipo_nota": row[1],
                    "cliente": row[2],
                    "valor_liquido": row[3],
                    "status": row[4],
                    "protocolo": row[5],
                    "data_emissao": row[6],
                    "chave_acesso": chave_acesso.strip(),
                }
        return self.provider.consultar_status(chave_acesso.strip())

    def listar_notas(self) -> pd.DataFrame:
        with _get_db_connection(self.db_name) as conn:
            return pd.read_sql_query("SELECT * FROM notas_fiscais ORDER BY id DESC", conn)


def render_modulo_fiscal(db_name: str, usuario_atual: str, perfil_atual: str) -> None:
    if st is None:
        raise RuntimeError("Streamlit não está instalado – UI indisponível.")

    st.markdown("### 🧾 Faturamento & Emissão de Notas Fiscais (NFS-e / NF-e)")
    st.info(
        f"👤 Operador Fiscal: **{usuario_atual}** (`{perfil_atual}`) — "
        "Módulo Fiscal Desacoplado operando em **Modo Homologação / Simulação Local** (Geração de RPS/Espelho HTML + XML e Controle Idempotente)."
    )

    manager = FiscalManager(db_name)

    with _get_db_connection(db_name) as conn:
        cur_cols = conn.execute("PRAGMA table_info(clientes_equipamentos)")
        cols_os = {r[1] for r in cur_cols.fetchall()}
        col_status = "status" if "status" in cols_os else "situacao"
        sql_os = f"""
            SELECT id, cliente, equipamento, valor_os
            FROM clientes_equipamentos
            WHERE UPPER(COALESCE({col_status}, '')) IN ('CONCLUÍDO', 'CONCLUIDO')
            ORDER BY id DESC
        """
        try:
            rows = conn.execute(sql_os).fetchall()
        except Exception:
            rows = conn.execute(
                f"SELECT id, cliente, '' as equipamento, 0.0 as valor_os FROM clientes_equipamentos WHERE UPPER(COALESCE({col_status}, '')) IN ('CONCLUÍDO', 'CONCLUIDO') ORDER BY id DESC"
            ).fetchall()

    aba_f1, aba_f2 = st.tabs([
        "🚀 Emitir Nova Nota Fiscal (A partir de OS Concluída)",
        "📋 Livro Fiscal, Consulta & Cancelamento / Estorno"
    ])

    with aba_f1:
        if not rows:
            st.warning("⚠️ Nenhuma Ordem de Serviço com status CONCLUÍDO encontrada para faturamento.")
        else:
            options = {
                f"OS #{r[0]} — {r[1]} | Equipamento: {r[2] or 'N/D'} (R$ {float(r[3] or 0.0):,.2f})": r[0]
                for r in rows
            }
            selected_label = st.selectbox("1. Selecione a Ordem de Serviço Concluída:", list(options.keys()))
            os_id = options[selected_label]
            dados_pre = manager._fetch_os_data(os_id)

            with st.form("form_emissao_fiscal_emed"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    tipo_nota_sel = st.selectbox(
                        "Modalidade Fiscal",
                        ["NFSE (Serviços Engenharia Clínica)", "NFE (Venda / Remessa de Peças)", "CONJUGADA (Serviço + Peças)"]
                    )
                    cod_iss = st.text_input("Código Serviço LC 116 / CFOP", value="14.01")
                with c2:
                    val_srv_in = st.number_input(
                        "Valor dos Serviços (R$)",
                        min_value=0.0,
                        value=float(dados_pre.get("valor_servicos", 0.0)),
                        step=50.0
                    )
                    val_pec_in = st.number_input(
                        "Valor das Peças (R$)",
                        min_value=0.0,
                        value=float(dados_pre.get("valor_pecas", 0.0)),
                        step=50.0
                    )
                with c3:
                    val_desc_in = st.number_input("Desconto Incondicional (R$)", min_value=0.0, value=0.0, step=10.0)
                    aliq_iss_in = st.number_input("Alíquota ISS (%)", min_value=0.0, max_value=15.0, value=5.0, step=0.5)

                btn_emitir = st.form_submit_button("🧾 Gerar e Autorizar Nota Fiscal (Idempotente)", type="primary")

            if btn_emitir:
                try:
                    sigla_tipo = tipo_nota_sel.split(" ")[0].strip()
                    nota = manager.create_pre_nota(
                        os_id=os_id,
                        tipo_nota=sigla_tipo,
                        valor_servicos_override=val_srv_in,
                        valor_pecas_override=val_pec_in,
                        valor_desconto=val_desc_in,
                        aliquota_iss=aliq_iss_in,
                        codigo_servico_iss=cod_iss.strip(),
                    )
                    st.success(
                        f"✅ Nota Fiscal **{nota.get('status_fiscal')}**! "
                        f"Número: **{nota.get('numero_nf')}** | Chave: `{nota.get('chave_acesso')}` | "
                        f"Protocolo: `{nota.get('protocolo_autorizacao')}`"
                    )
                    xml_p = str(nota.get("xml_path") or "")
                    html_path = xml_p.replace("xml", "html")
                    if os.path.exists(html_path):
                        with open(html_path, "r", encoding="utf-8") as f:
                            st.markdown(f.read(), unsafe_allow_html=True)
                    if os.path.exists(xml_p):
                        with open(xml_p, "rb") as fx:
                            st.download_button(
                                label="📥 Baixar XML da Nota Fiscal",
                                data=fx,
                                file_name=f"NF_{nota.get('numero_nf')}_OS_{os_id}.xml",
                                mime="application/xml",
                            )
                except Exception as exc:
                    st.error(f"⚠️ Erro ao emitir nota: {exc}")

    with aba_f2:
        st.markdown("#### 📋 Notas Fiscais Emitidas no Banco (`notas_fiscais`)")
        df_notas = manager.listar_notas()
        if df_notas.empty:
            st.info("Nenhuma nota fiscal emitida até o momento.")
        else:
            st.dataframe(df_notas, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### 🔍 Consulta de Status e Cancelamento / Estorno Circular")
        opcoes_chaves = (
            [f"{r['chave_acesso']} | NF {r['numero_nf']} - {r['cliente']} [{r['status_fiscal']}]" for _, r in df_notas.iterrows()]
            if not df_notas.empty else []
        )
        chave_sel = st.selectbox("Selecionar Nota Emitida (ou digite abaixo):", [""] + opcoes_chaves)
        chave_default = chave_sel.split("|")[0].strip() if chave_sel else ""
        chave = st.text_input("Chave de Acesso da Nota Fiscal", value=chave_default)

        c_b1, c_b2 = st.columns(2)
        with c_b1:
            if st.button("🔍 Consultar Status na SEFAZ/Prefeitura") and chave:
                st.json(manager.consultar_status(chave))
        with c_b2:
            if st.button("🚫 Cancelar / Estornar Nota Fiscal") and chave:
                try:
                    if manager.cancelar_nota(chave):
                        st.success("✅ Nota fiscal cancelada com sucesso! A OS correspondente está liberada para nova emissão.")
                        st.rerun()
                    else:
                        st.warning("⚠️ Cancelamento não concluído.")
                except Exception as e:
                    st.error(str(e))
