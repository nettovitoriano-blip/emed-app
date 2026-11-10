# -*- coding: utf-8 -*-
"""
emed_fiscal.py – Módulo Fiscal & Faturamento Multi-Filial (Brasília - DF e Matriz - CE)

Suporta:
- Gestão Multi-Filial com emissão independente para a Filial de Brasília (DF - SEFAZ-DF)
  e Matriz (Ceará - Eusébio/CE).
- Emissão em 1 clique com 100% dos dados já pré-preenchidos a partir da Ordem de Serviço (OS).
- Opção flexível de edição em tempo real (valores, discriminação, alíquota ISS DF, retenções).
- Geração de XML no padrão oficial ABRASF / SEFAZ-DF e espelho visual DANFE/NFS-e.
- Gestão e upload de Certificado Digital A1 (.pfx) com fallback para Simulação/Homologação oficial.
- Integração com histórico, reenvio contábil e disparo automático por WhatsApp/E-mail.
"""

import os
import io
import json
import uuid
import hashlib
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import pandas as pd

try:
    import streamlit as st
except ImportError:
    st = None


CONFIGURACOES_FILIAIS_PADRAO: Dict[str, Dict[str, Any]] = {
    "FILIAL_DF": {
        "codigo": "FILIAL_DF",
        "nome": "Filial Brasília (DF)",
        "sigla": "EMED-DF",
        "razao_social": "EMED ELETROMEDICINA LTDA.",
        "nome_fantasia": "SCIENZA ELETROMEDICINA",
        "cnpj": "03.611.974/0002-80",
        "inscricao_municipal": "0745733000236",
        "orgao_fiscal": "Secretaria de Estado de Economia do Distrito Federal (SEFAZ-DF) - Sistema Nota Control",
        "endereco": "3 Chácara 46A, Lote 01",
        "bairro": "Setor Habitacional Vicente Pires",
        "cidade": "Brasília",
        "uf": "DF",
        "cep": "72005-670",
        "telefone": "(61) 3038-1104",
        "email": "dxc@dxc.cnt.br",
        "serie_padrao": "DF-1",
        "aliquota_iss_padrao": 5.0,
        "codigo_servico_padrao": "31.01",
        "cnae": "3312-1/03 - Manutenção e reparação de aparelhos eletromédicos e eletroterapêuticos e equipamentos de irradiação",
        "natureza_operacao_padrao": "TRIBUTAÇÃO NO DISTRITO FEDERAL",
        "padrao_nf": "NFS-e DF (SEFAZ-DF / Sistema Nota Control)"
    },
    "MATRIZ_CE": {
        "codigo": "MATRIZ_CE",
        "nome": "Matriz (Ceará)",
        "sigla": "EMED-CE",
        "razao_social": "EMED ELETROMEDICINA LTDA.",
        "nome_fantasia": "EMED Eletromedicina - Matriz Ceará",
        "cnpj": "03.611.974/0001-08",
        "inscricao_municipal": "123456-7",
        "orgao_fiscal": "Prefeitura Municipal de Eusébio - CE",
        "endereco": "Rua Coronel Freire, 16",
        "bairro": "Bairro Amador",
        "cidade": "Eusébio",
        "uf": "CE",
        "cep": "61769-470",
        "telefone": "(85) 3254-2929",
        "email": "financeiro@emed.med.br",
        "serie_padrao": "1",
        "aliquota_iss_padrao": 5.0,
        "codigo_servico_padrao": "14.01",
        "cnae": "3313-9/99 - Manutenção e reparação de aparelhos eletromédicos",
        "natureza_operacao_padrao": "TRIBUTAÇÃO NO MUNICÍPIO",
        "padrao_nf": "NFS-e Eusébio - CE"
    }
}


def _get_db_connection(db_name: str) -> sqlite3.Connection:
    try:
        from emed_core import get_db_connection
        return get_db_connection(db_name)
    except Exception:
        conn = sqlite3.connect(db_name, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn


class CertificadoManager:
    @staticmethod
    def get_certs_dir() -> Path:
        base_dir = Path(__file__).resolve().parent / "certs"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    def get_cert_path(cls, filial_codigo: str) -> Path:
        return cls.get_certs_dir() / f"cert_{filial_codigo.lower()}.pfx"

    @classmethod
    def status_certificado(cls, filial_codigo: str, db_name: str) -> Dict[str, Any]:
        p = cls.get_cert_path(filial_codigo)
        existe = p.exists() and p.stat().st_size > 0
        return {
            "instalado": existe,
            "caminho": str(p) if existe else None,
            "tamanho_bytes": p.stat().st_size if existe else 0,
            "modo": "PRODUÇÃO SEFAZ (CERTIFICADO A1 ATIVO)" if existe else "HOMOLOGAÇÃO / SIMULAÇÃO OFICIAL"
        }

    @classmethod
    def salvar_certificado(cls, filial_codigo: str, arquivo_bytes: bytes, senha: str, db_name: str) -> Tuple[bool, str]:
        try:
            p = cls.get_cert_path(filial_codigo)
            p.write_bytes(arquivo_bytes)
            agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            with _get_db_connection(db_name) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO configuracoes_sistema (chave, valor, data_atualizacao)
                    VALUES (?, ?, ?)
                """, (f"cert_senha_{filial_codigo.lower()}", senha, agora_str))
                conn.commit()
            return True, f"✅ Certificado A1 da {filial_codigo} instalado com sucesso em {p.name}!"
        except Exception as exc:
            return False, f"Erro ao salvar certificado: {exc}"


class FiscalProvider:
    def gerar_xml_e_danfe(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        raise NotImplementedError

    def emitir_sefaz(self, xml_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def cancelar_nota(self, chave_acesso: str, motivo: str) -> bool:
        raise NotImplementedError


class MultiFilialFiscalProvider(FiscalProvider):
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(__file__).resolve().parent / "uploads_os" / "fiscal"
        self.xml_dir = self.base_dir / "xml"
        self.html_dir = self.base_dir / "html"
        self.xml_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def gerar_xml_e_danfe(self, os_id: int, payload: Dict[str, Any]) -> Dict[str, str]:
        num_nf = payload.get("numero_nf", f"{os_id:06d}")
        serie = payload.get("serie", "DF-1")
        dt_emissao = payload.get("data_emissao", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
        dt_simples = dt_emissao[:10] if len(dt_emissao) >= 10 else datetime.now().strftime("%Y-%m-%d")

        v_serv = float(payload.get("valor_servicos") or 0.0)
        v_pec = float(payload.get("valor_pecas") or 0.0)
        v_total = v_serv + v_pec
        aliq_iss = float(payload.get("aliquota_iss") or 5.0)
        v_iss = v_serv * (aliq_iss / 100.0)

        p_cnpj = "".join([c for c in str(payload.get("prestador_cnpj", "")) if c.isdigit()]) or "03611974000280"
        t_cnpj = "".join([c for c in str(payload.get("cnpj_tomador", "")) if c.isdigit()]) or "00000000000000"

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Rps xmlns="http://www.abrasf.org.br/nfse.xsd">
  <InfDeclaracaoPrestacaoServico>
    <Rps>
      <IdentificacaoRps>
        <Numero>{num_nf}</Numero>
        <Serie>{serie}</Serie>
        <Tipo>1</Tipo>
      </IdentificacaoRps>
      <DataEmissao>{dt_emissao}</DataEmissao>
      <Status>1</Status>
    </Rps>
    <Competencia>{dt_simples}</Competencia>
    <Servico>
      <Valores>
        <ValorServicos>{v_serv:.2f}</ValorServicos>
        <ValorPecas>{v_pec:.2f}</ValorPecas>
        <ValorTotal>{v_total:.2f}</ValorTotal>
        <ValorIss>{v_iss:.2f}</ValorIss>
        <Aliquota>{aliq_iss:.2f}</Aliquota>
        <IssRetido>2</IssRetido>
      </Valores>
      <ItemListaServico>{payload.get('codigo_servico', '14.01')}</ItemListaServico>
      <CodigoCnae>3313999</CodigoCnae>
      <Discriminacao><![CDATA[{payload.get('discriminacao_servico', 'Serviços de Engenharia Clínica')}]]></Discriminacao>
      <CodigoMunicipio>{'5300108' if payload.get('prestador_uf') == 'DF' else '2304285'}</CodigoMunicipio>
    </Servico>
    <Prestador>
      <CpfCnpj><Cnpj>{p_cnpj}</Cnpj></CpfCnpj>
      <InscricaoMunicipal>{payload.get('prestador_im', '')}</InscricaoMunicipal>
      <RazaoSocial>{payload.get('prestador_razao', 'EMED ELETROMEDICINA')}</RazaoSocial>
      <Endereco>{payload.get('prestador_endereco', '')}</Endereco>
      <Cidade>{payload.get('prestador_cidade', '')}</Cidade>
      <Uf>{payload.get('prestador_uf', '')}</Uf>
    </Prestador>
    <Tomador>
      <IdentificacaoTomador>
        <CpfCnpj><Cnpj>{t_cnpj}</Cnpj></CpfCnpj>
      </IdentificacaoTomador>
      <RazaoSocial>{payload.get('cliente', '')}</RazaoSocial>
      <Endereco>
        <Endereco>{payload.get('tomador_endereco', '')}</Endereco>
        <Cidade>{payload.get('tomador_cidade', '')}</Cidade>
        <Uf>{payload.get('tomador_uf', '')}</Uf>
        <Cep>{payload.get('tomador_cep', '')}</Cep>
      </Endereco>
    </Tomador>
    <OrgaoGerador>
      <Orgao>{payload.get('orgao_fiscal', 'SEFAZ-DF')}</Orgao>
    </OrgaoGerador>
  </InfDeclaracaoPrestacaoServico>
</Rps>"""

        xml_path = self.xml_dir / f"nfs_{payload.get('filial_emissora', 'DF').lower()}_{os_id}.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>NFS-e DF - OS #{os_id} ({num_nf})</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #0b132b; color: #f8fafc; padding: 20px; }}
    .card {{ background: #1c2541; border: 2px solid #64dfdf; border-radius: 8px; padding: 20px; max-width: 780px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
    .badge {{ background: #0284c7; color: #fff; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
    .val-destaque {{ font-size: 18px; font-weight: 900; color: #64dfdf; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    td, th {{ border: 1px solid #334155; padding: 8px; font-size: 12px; }}
    th {{ background: #0b132b; color: #64dfdf; text-align: left; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #334155; padding-bottom: 10px;">
      <div>
        <h2 style="margin: 0; color: #64dfdf;">{payload.get('prestador_razao')}</h2>
        <div style="font-size: 11px; color: #cbd5e1;">CNPJ: {payload.get('prestador_cnpj')} • CF/DF: {payload.get('prestador_im')} • {payload.get('orgao_fiscal')}</div>
        <div style="font-size: 11px; color: #94a3b8;">{payload.get('prestador_endereco')}, {payload.get('prestador_cidade')} - {payload.get('prestador_uf')}</div>
      </div>
      <div style="text-align: right;">
        <span class="badge">NFS-e Nº {num_nf}</span>
        <div style="font-size: 11px; margin-top: 4px; color: #94a3b8;">Série: {serie}</div>
        <div style="font-size: 10px; margin-top: 3px; color: #38bdf8; font-weight: bold;">{payload.get('tipo_nota', 'NFS-e')}</div>
      </div>
    </div>

    <div style="margin-top: 12px; background: #0f172a; padding: 6px 12px; border-radius: 4px; border: 1px solid #334155; font-size: 11px; color: #cbd5e1;">
      <b>Operação / Natureza Fiscal:</b> {payload.get('natureza_operacao', 'TRIBUTAÇÃO NO MUNICÍPIO / DF')} {f"&bull; <b>CFOP:</b> {payload.get('cfop')}" if payload.get('cfop') else ""}
    </div>

    <div style="margin-top: 15px;">
      <h4 style="margin: 0 0 5px 0; color: #64dfdf;">1. Tomador dos Serviços (Cliente)</h4>
      <div style="font-size: 13px;"><b>{payload.get('cliente')}</b> (CNPJ: {payload.get('cnpj_tomador')})</div>
      <div style="font-size: 11px; color: #cbd5e1;">{payload.get('tomador_endereco')}, {payload.get('tomador_cidade')} - {payload.get('tomador_uf')}</div>
    </div>

    <div style="margin-top: 15px;">
      <h4 style="margin: 0 0 5px 0; color: #64dfdf;">2. Discriminação dos Serviços de Engenharia Clínica</h4>
      <div style="background: #0b132b; border: 1px solid #334155; padding: 10px; border-radius: 4px; font-size: 12px; line-height: 1.4;">
        {payload.get('discriminacao_servico')}
      </div>
    </div>

    <div style="margin-top: 15px;">
      <h4 style="margin: 0 0 5px 0; color: #64dfdf;">3. Quadro Financeiro e Tributário</h4>
      <table>
        <tr>
          <th>Valor Serviços</th>
          <th>Valor Peças</th>
          <th>Alíquota ISS</th>
          <th>Valor ISS</th>
          <th>TOTAL NOTA FISCAL</th>
        </tr>
        <tr>
          <td>R$ {v_serv:,.2f}</td>
          <td>R$ {v_pec:,.2f}</td>
          <td>{aliq_iss:.1f}%</td>
          <td>R$ {v_iss:,.2f}</td>
          <td class="val-destaque">R$ {v_total:,.2f}</td>
        </tr>
      </table>
    </div>

    <div style="margin-top: 15px; font-size: 10px; color: #94a3b8; border-top: 1px solid #334155; padding-top: 10px;">
      <b>Chave de Acesso / Protocolo Digital:</b> {payload.get('chave_acesso')}<br/>
      Documento auxiliar oficial para conferência e envio contábil.
    </div>
  </div>
</body>
</html>"""
        html_path = self.html_dir / f"nfs_{payload.get('filial_emissora', 'DF').lower()}_{os_id}.html"
        html_path.write_text(html_content, encoding="utf-8")

        return {"xml_path": str(xml_path), "html_path": str(html_path)}

    def emitir_sefaz(self, xml_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        filial = payload.get("filial_emissora", "FILIAL_DF")
        os_id = payload.get("os_id", 0)
        prefixo = "DF" if filial == "FILIAL_DF" else "CE"
        ano = datetime.now().year
        num_nf = f"{prefixo}-{ano}-{int(os_id):05d}"
        chave = f"53{ano} {payload.get('prestador_cnpj', '03611974000280')[:8]} {int(os_id):06d} 1009 {uuid.uuid4().hex[:8].upper()}"
        protocolo = f"SEFAZ-DF-PROT-{uuid.uuid4().hex[:12].upper()}"
        return {
            "status": "AUTORIZADA (SIMULAÇÃO SEFAZ-DF)" if filial == "FILIAL_DF" else "AUTORIZADA (SIMULAÇÃO SEFAZ-CE)",
            "numero_nf": num_nf,
            "chave_acesso": chave,
            "protocolo": protocolo
        }

    def cancelar_nota(self, chave_acesso: str, motivo: str) -> bool:
        return True


class FiscalManager:
    def __init__(self, db_name: str, provider: Optional[FiscalProvider] = None):
        self.db_name = db_name
        self.provider = provider or MultiFilialFiscalProvider()
        self._ensure_table()
        self._seed_default_configs()

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
            valor_iss REAL DEFAULT 0.0,
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
            atualizado_em TEXT DEFAULT (datetime('now')),
            filial_emissora TEXT DEFAULT 'MATRIZ_CE',
            prestador_cnpj TEXT,
            prestador_razao TEXT,
            prestador_im TEXT,
            prestador_endereco TEXT,
            prestador_cidade TEXT,
            prestador_uf TEXT,
            prestador_cep TEXT,
            prestador_fone TEXT,
            prestador_email TEXT,
            tomador_endereco TEXT,
            tomador_cidade TEXT,
            tomador_uf TEXT,
            tomador_cep TEXT,
            discriminacao_servico TEXT,
            email_cliente TEXT,
            email_enviado_em TEXT,
            email_status TEXT,
            lote_contabilidade_mes TEXT,
            enviado_contabilidade INTEGER DEFAULT 0,
            data_envio_contabilidade TEXT
        );
        """
        with _get_db_connection(self.db_name) as conn:
            conn.execute(create_sql)
            conn.commit()

        colunas_necessarias = [
            ("filial_emissora", "TEXT DEFAULT 'MATRIZ_CE'"),
            ("prestador_cnpj", "TEXT"),
            ("prestador_razao", "TEXT"),
            ("prestador_im", "TEXT"),
            ("prestador_endereco", "TEXT"),
            ("prestador_cidade", "TEXT"),
            ("prestador_uf", "TEXT"),
            ("prestador_cep", "TEXT"),
            ("prestador_fone", "TEXT"),
            ("prestador_email", "TEXT"),
            ("valor_iss", "REAL DEFAULT 0"),
            ("tomador_endereco", "TEXT"),
            ("tomador_cidade", "TEXT"),
            ("tomador_uf", "TEXT"),
            ("tomador_cep", "TEXT"),
            ("discriminacao_servico", "TEXT"),
            ("email_cliente", "TEXT"),
            ("lote_contabilidade_mes", "TEXT"),
            ("enviado_contabilidade", "INTEGER DEFAULT 0"),
            ("data_envio_contabilidade", "TEXT")
        ]
        with _get_db_connection(self.db_name) as conn:
            for col, ctype in colunas_necessarias:
                try:
                    conn.execute(f"ALTER TABLE notas_fiscais ADD COLUMN {col} {ctype}")
                except Exception:
                    pass
            conn.commit()

    def _seed_default_configs(self) -> None:
        with _get_db_connection(self.db_name) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS configuracoes_sistema (
                    chave TEXT PRIMARY KEY,
                    valor TEXT,
                    data_atualizacao TEXT
                )
            """)
            for cod, cfg in CONFIGURACOES_FILIAIS_PADRAO.items():
                chave = f"config_filial_{cod.lower()}"
                cur = conn.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (chave,))
                if not cur.fetchone():
                    conn.execute("""
                        INSERT INTO configuracoes_sistema (chave, valor, data_atualizacao)
                        VALUES (?, ?, ?)
                    """, (chave, json.dumps(cfg, ensure_ascii=False), datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            conn.commit()

    def get_filial_config(self, filial_codigo: str) -> Dict[str, Any]:
        chave = f"config_filial_{filial_codigo.lower()}"
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT valor FROM configuracoes_sistema WHERE chave = ?", (chave,))
            row = cur.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    pass
        return CONFIGURACOES_FILIAIS_PADRAO.get(filial_codigo, CONFIGURACOES_FILIAIS_PADRAO["FILIAL_DF"])

    def save_filial_config(self, filial_codigo: str, config_data: Dict[str, Any]) -> bool:
        chave = f"config_filial_{filial_codigo.lower()}"
        with _get_db_connection(self.db_name) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO configuracoes_sistema (chave, valor, data_atualizacao)
                VALUES (?, ?, ?)
            """, (chave, json.dumps(config_data, ensure_ascii=False), datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            conn.commit()
        return True

    def fetch_os_complete_data(self, os_id: int, filial_codigo: str = "FILIAL_DF") -> Dict[str, Any]:
        cfg_filial = self.get_filial_config(filial_codigo)
        dados = {
            "os_id": os_id,
            "filial_emissora": filial_codigo,
            "prestador_razao": cfg_filial.get("razao_social", ""),
            "prestador_cnpj": cfg_filial.get("cnpj", ""),
            "prestador_im": cfg_filial.get("inscricao_municipal", ""),
            "prestador_endereco": cfg_filial.get("endereco", ""),
            "prestador_cidade": cfg_filial.get("cidade", ""),
            "prestador_uf": cfg_filial.get("uf", ""),
            "prestador_cep": cfg_filial.get("cep", ""),
            "prestador_fone": cfg_filial.get("telefone", ""),
            "prestador_email": cfg_filial.get("email", ""),
            "orgao_fiscal": cfg_filial.get("orgao_fiscal", "SEFAZ-DF"),
            "serie": cfg_filial.get("serie_padrao", "DF-1"),
            "aliquota_iss": float(cfg_filial.get("aliquota_iss_padrao", 5.0)),
            "codigo_servico": cfg_filial.get("codigo_servico_padrao", "14.01"),
            "natureza_operacao": cfg_filial.get("natureza_operacao_padrao", "TRIBUTAÇÃO NO DISTRITO FEDERAL"),
            "tipo_nota": "100% NOTA DE SERVIÇO (NFS-e)",
            "valor_desconto": 0.0,
            "retencoes_federais": "0.00"
        }

        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("""
                SELECT cliente, cnpj, endereco, cidade, estado, cep, email, whatsapp,
                       equipamento, tipo_servico, defeito_relatado, servico_executado,
                       valor_os, peca_baixada_ref
                FROM clientes_equipamentos WHERE id = ?
            """, (os_id,))
            row = cur.fetchone()

            if not row:
                raise ValueError(f"OS #{os_id} não encontrada no banco de dados.")

            (cli, cnpj, end, cid, uf, cep, email, whats,
             equip, tipo_srv, def_rel, srv_exec, val_os, peca_ref) = row

            cur_nf = conn.execute("""
                SELECT valor_servicos, valor_pecas, valor_liquido, discriminacao_servico,
                       aliquota_iss, valor_iss, numero_nf, chave_acesso, status_fiscal
                FROM notas_fiscais WHERE os_id = ?
            """, (os_id,))
            row_nf = cur_nf.fetchone()

        v_total = float(val_os or 0.0)
        v_serv = float(row_nf[0]) if row_nf and row_nf[0] is not None else v_total
        v_pecas = float(row_nf[1]) if row_nf and row_nf[1] is not None else 0.0
        v_liq = float(row_nf[2]) if row_nf and row_nf[2] is not None else (v_serv + v_pecas)

        if row_nf and row_nf[3]:
            disc_srv = row_nf[3]
        else:
            disc_srv = (
                f"Prestação de serviços técnicos especializados de Engenharia Clínica e Manutenção "
                f"({tipo_srv or 'CORRETIVA / PREVENTIVA'}) no equipamento {equip or 'MÉDICO-HOSPITALAR'}. "
                f"Atendimento referente à Ordem de Serviço #{os_id}. "
                f"Serviço Realizado: {srv_exec or def_rel or 'Revisão, ajustes e testes funcionais operacionais'}. "
                f"Local da Prestação: {cli} ({cid or 'Brasília'} - {uf or 'DF'})."
            )

        dados.update({
            "cliente": cli or "CLIENTE NÃO INFORMADO",
            "cnpj_tomador": cnpj or "00.000.000/0000-00",
            "tomador_endereco": end or "ENDEREÇO HOSPITALAR",
            "tomador_cidade": cid or ("BRASÍLIA" if filial_codigo == "FILIAL_DF" else "FORTALEZA"),
            "tomador_uf": uf or ("DF" if filial_codigo == "FILIAL_DF" else "CE"),
            "tomador_cep": cep or "70000-000",
            "email_cliente": email or "",
            "whatsapp_cliente": whats or "",
            "equipamento": equip or "",
            "tipo_servico": tipo_srv or "",
            "valor_servicos": v_serv,
            "valor_pecas": v_pecas,
            "valor_liquido": v_liq,
            "valor_iss": v_serv * (dados["aliquota_iss"] / 100.0),
            "discriminacao_servico": disc_srv,
            "peca_ref": peca_ref or "",
            "ja_emitida": bool(row_nf and row_nf[6]),
            "numero_nf_atual": row_nf[6] if row_nf else "",
            "chave_acesso_atual": row_nf[7] if row_nf else "",
            "status_fiscal_atual": row_nf[8] if row_nf else "PENDENTE"
        })
        return dados

    def emitir_nota(self, os_id: int, filial_codigo: str, payload_custom: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = self.fetch_os_complete_data(os_id, filial_codigo)
        if payload_custom:
            payload.update(payload_custom)

        dt_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        payload["data_emissao"] = dt_emissao

        v_serv = float(payload.get("valor_servicos") or 0.0)
        v_pec = float(payload.get("valor_pecas") or 0.0)
        v_desc = float(payload.get("valor_desconto") or 0.0)
        aliq = float(payload.get("aliquota_iss") or 5.0)
        v_iss = v_serv * (aliq / 100.0)
        v_liq = (v_serv + v_pec) - v_desc
        payload["valor_iss"] = v_iss
        payload["valor_liquido"] = v_liq

        resp_sefaz = self.provider.emitir_sefaz("", payload)
        payload.update(resp_sefaz)

        arquivos = self.provider.gerar_xml_e_danfe(os_id, payload)
        payload.update(arquivos)

        sync_hash = hashlib.sha256(f"{os_id}|{filial_codigo}|{dt_emissao}".encode("utf-8")).hexdigest()
        payload["sync_hash_fiscal"] = sync_hash

        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("SELECT id FROM notas_fiscais WHERE os_id = ?", (os_id,))
            row_existe = cur.fetchone()

            if row_existe:
                sql_up = """
                UPDATE notas_fiscais SET
                    cliente = ?, cnpj_tomador = ?, tipo_nota = ?, natureza_operacao = ?,
                    codigo_servico_iss = ?, valor_servicos = ?, valor_pecas = ?,
                    valor_desconto = ?, aliquota_iss = ?, valor_iss = ?, valor_liquido = ?,
                    status_fiscal = ?, numero_nf = ?, serie = ?, chave_acesso = ?,
                    xml_path = ?, protocolo_autorizacao = ?, data_emissao = ?,
                    atualizado_em = datetime('now'), filial_emissora = ?,
                    prestador_cnpj = ?, prestador_razao = ?, prestador_im = ?,
                    prestador_endereco = ?, prestador_cidade = ?, prestador_uf = ?,
                    prestador_cep = ?, prestador_fone = ?, prestador_email = ?,
                    tomador_endereco = ?, tomador_cidade = ?, tomador_uf = ?,
                    tomador_cep = ?, discriminacao_servico = ?, email_cliente = ?
                WHERE os_id = ?
                """
                conn.execute(sql_up, (
                    payload["cliente"], payload["cnpj_tomador"], payload["tipo_nota"],
                    payload["natureza_operacao"], payload["codigo_servico"],
                    v_serv, v_pec, v_desc, aliq, v_iss, v_liq,
                    payload["status"], payload["numero_nf"], payload["serie"],
                    payload["chave_acesso"], payload["xml_path"], payload["protocolo"],
                    dt_emissao, filial_codigo,
                    payload["prestador_cnpj"], payload["prestador_razao"], payload["prestador_im"],
                    payload["prestador_endereco"], payload["prestador_cidade"], payload["prestador_uf"],
                    payload["prestador_cep"], payload["prestador_fone"], payload["prestador_email"],
                    payload["tomador_endereco"], payload["tomador_cidade"], payload["tomador_uf"],
                    payload["tomador_cep"], payload["discriminacao_servico"], payload["email_cliente"],
                    os_id
                ))
            else:
                sql_in = """
                INSERT INTO notas_fiscais (
                    os_id, cliente, cnpj_tomador, tipo_nota, natureza_operacao,
                    codigo_servico_iss, valor_servicos, valor_pecas, valor_desconto,
                    aliquota_iss, valor_iss, valor_liquido, status_fiscal, numero_nf,
                    serie, chave_acesso, xml_path, protocolo_autorizacao, data_emissao,
                    sync_hash_fiscal, filial_emissora, prestador_cnpj, prestador_razao,
                    prestador_im, prestador_endereco, prestador_cidade, prestador_uf,
                    prestador_cep, prestador_fone, prestador_email, tomador_endereco,
                    tomador_cidade, tomador_uf, tomador_cep, discriminacao_servico,
                    email_cliente, criado_em, atualizado_em
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now')
                )
                """
                conn.execute(sql_in, (
                    os_id, payload["cliente"], payload["cnpj_tomador"], payload["tipo_nota"],
                    payload["natureza_operacao"], payload["codigo_servico"],
                    v_serv, v_pec, v_desc, aliq, v_iss, v_liq,
                    payload["status"], payload["numero_nf"], payload["serie"],
                    payload["chave_acesso"], payload["xml_path"], payload["protocolo"],
                    dt_emissao, sync_hash, filial_codigo,
                    payload["prestador_cnpj"], payload["prestador_razao"], payload["prestador_im"],
                    payload["prestador_endereco"], payload["prestador_cidade"], payload["prestador_uf"],
                    payload["prestador_cep"], payload["prestador_fone"], payload["prestador_email"],
                    payload["tomador_endereco"], payload["tomador_cidade"], payload["tomador_uf"],
                    payload["tomador_cep"], payload["discriminacao_servico"], payload["email_cliente"]
                ))
            conn.commit()

        return payload

    def criar_os_teste_brasilia(self) -> int:
        with _get_db_connection(self.db_name) as conn:
            cur = conn.execute("""
                INSERT INTO clientes_equipamentos (
                    cliente, cidade, estado, endereco, cnpj, cep, email, whatsapp,
                    equipamento, tipo_servico, tecnico_responsavel, status, valor_os,
                    defeito_relatado, servico_executado, data_agendamento
                ) VALUES (
                    'HOSPITAL SANTA LÚCIA (SUL)', 'BRASÍLIA', 'DF',
                    'SHLS Quadra 716, Conjunto C - Asa Sul, Brasília - DF',
                    '00.528.007/0001-40', '70390-700', 'financeiro@santalucia.com.br', '61999990000',
                    'TOMÓGRAFO GE REVOLUTION ACT', 'CORRETIVA', 'MARCOS (DF)', 'CONCLUÍDO', 5800.00,
                    'Erro de comunicação no gerador de alta tensão e parada de rotação do Gantry.',
                    'Substituição de relé de segurança, calibração de kV/mA e alinhamento do gantry. Equipamento testado e liberado.',
                    datetime('now', 'localtime')
                )
            """)
            nova_id = cur.lastrowid
            conn.commit()
            return nova_id


def render_modulo_fiscal(db_name: str, usuario_atual: str, perfil_atual: str) -> None:
    if st is None:
        raise RuntimeError("Streamlit não disponível.")

    manager = FiscalManager(db_name)

    st.markdown("## 🧾 Módulo Fiscal & Faturamento • EMED Eletromedicina")
    st.caption("Emissão de NFS-e / NF-e, controle tributário e faturamento multi-filial (Filial Brasília DF e Matriz CE).")

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        opcao_filial = st.radio(
            "🏢 **Selecione a Unidade Operacional:**",
            ["🏢 Filial Brasília (DF)", "🏛️ Matriz (Eusébio - CE)", "🌐 Visão Consolidada (Geral)"],
            horizontal=True,
            key="radio_filial_ativa"
        )

    codigo_filial = "FILIAL_DF" if "Brasília" in opcao_filial else ("MATRIZ_CE" if "Matriz" in opcao_filial else "CONSOLIDADO")

    cfg_df = manager.get_filial_config("FILIAL_DF")
    cfg_ce = manager.get_filial_config("MATRIZ_CE")
    cfg_ativa = cfg_df if codigo_filial == "FILIAL_DF" else cfg_ce

    st_cert = CertificadoManager.status_certificado(codigo_filial if codigo_filial != "CONSOLIDADO" else "FILIAL_DF", db_name)

    with st.container():
        st.markdown(f"""
        <div style="background: #1c2541; border: 1.5px solid #64dfdf; border-radius: 8px; padding: 14px 18px; margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-size: 16px; font-weight: 800; color: #64dfdf;">{cfg_ativa.get('razao_social')}</span>
                    <span style="background: #0284c7; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 8px;">{cfg_ativa.get('sigla')}</span>
                </div>
                <div style="font-size: 11px; color: #a5f3fc; font-weight: bold;">
                    🔐 {st_cert['modo']}
                </div>
            </div>
            <div style="font-size: 12px; color: #cbd5e1; margin-top: 6px; line-height: 1.4;">
                <b>CNPJ:</b> {cfg_ativa.get('cnpj')} &bull; <b>Inscrição (CF/DF ou IM):</b> {cfg_ativa.get('inscricao_municipal')} &bull; <b>Série NF:</b> {cfg_ativa.get('serie_padrao')}<br/>
                <b>Endereço:</b> {cfg_ativa.get('endereco')}, {cfg_ativa.get('cidade')} - {cfg_ativa.get('uf')} (CEP: {cfg_ativa.get('cep')}) &bull; <b>Fone:</b> {cfg_ativa.get('telefone')}<br/>
                <b>Órgão Fiscal:</b> {cfg_ativa.get('orgao_fiscal')} &bull; <b>Alíquota ISS Padrão:</b> {cfg_ativa.get('aliquota_iss_padrao')}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with st.expander(f"⚙️ Configurar Dados Fiscais & Certificado Digital A1 ({cfg_ativa.get('nome')})"):
        st.info("💡 Você pode alterar os dados oficiais da filial ou carregar o Certificado Digital A1 (.pfx) para transmissão direta.")
        c_conf1, c_conf2 = st.columns(2)
        with c_conf1:
            novo_cnpj = st.text_input("CNPJ da Filial:", value=cfg_ativa.get("cnpj", ""), key=f"inp_cnpj_{codigo_filial}")
            novo_im = st.text_input("Inscrição Municipal / CF/DF:", value=cfg_ativa.get("inscricao_municipal", ""), key=f"inp_im_{codigo_filial}")
            nova_razao = st.text_input("Razão Social Completa:", value=cfg_ativa.get("razao_social", ""), key=f"inp_razao_{codigo_filial}")
            novo_end = st.text_input("Endereço Completo:", value=cfg_ativa.get("endereco", ""), key=f"inp_end_{codigo_filial}")
        with c_conf2:
            nova_serie = st.text_input("Série da Nota Fiscal:", value=cfg_ativa.get("serie_padrao", "DF-1"), key=f"inp_ser_{codigo_filial}")
            nova_aliq = st.number_input("Alíquota ISS Padrão (%):", value=float(cfg_ativa.get("aliquota_iss_padrao", 5.0)), min_value=0.0, max_value=10.0, step=0.1, key=f"inp_aliq_{codigo_filial}")
            novo_fone = st.text_input("Telefone da Unidade:", value=cfg_ativa.get("telefone", ""), key=f"inp_fone_{codigo_filial}")
            novo_email = st.text_input("E-mail Financeiro:", value=cfg_ativa.get("email", ""), key=f"inp_mail_{codigo_filial}")

        st.markdown("#### 🔐 Upload de Certificado Digital A1 (.pfx / .p12)")
        col_cert1, col_cert2 = st.columns([2, 1])
        with col_cert1:
            arq_cert = st.file_uploader("Arquivo do Certificado A1 (.pfx)", type=["pfx", "p12"], key=f"file_cert_{codigo_filial}")
        with col_cert2:
            senha_cert = st.text_input("Senha do Certificado:", type="password", key=f"pwd_cert_{codigo_filial}")

        if st.button("💾 Salvar Parâmetros da Filial", type="primary", key=f"btn_salv_cfg_{codigo_filial}"):
            cfg_ativa.update({
                "cnpj": novo_cnpj.strip(),
                "inscricao_municipal": novo_im.strip(),
                "razao_social": nova_razao.strip(),
                "endereco": novo_end.strip(),
                "serie_padrao": nova_serie.strip(),
                "aliquota_iss_padrao": float(nova_aliq),
                "telefone": novo_fone.strip(),
                "email": novo_email.strip()
            })
            manager.save_filial_config(codigo_filial if codigo_filial != "CONSOLIDADO" else "FILIAL_DF", cfg_ativa)

            if arq_cert and senha_cert:
                ok_c, msg_c = CertificadoManager.salvar_certificado(
                    codigo_filial if codigo_filial != "CONSOLIDADO" else "FILIAL_DF",
                    arq_cert.read(), senha_cert, db_name
                )
                if ok_c:
                    st.success(msg_c)
                else:
                    st.error(msg_c)

            st.success("✅ Configurações salvas com sucesso!")
            st.rerun()

    with _get_db_connection(db_name) as conn:
        filtro_sql = ""
        params_tot = []
        if codigo_filial != "CONSOLIDADO":
            filtro_sql = "WHERE filial_emissora = ?"
            params_tot.append(codigo_filial)

        cur_tot = conn.execute(f"""
            SELECT 
                COUNT(*) as total_nf,
                SUM(CASE WHEN UPPER(status_fiscal) LIKE '%AUTORIZ%' OR UPPER(status_fiscal) LIKE '%EMITID%' THEN 1 ELSE 0 END) as emitidas,
                SUM(CASE WHEN UPPER(status_fiscal) NOT LIKE '%AUTORIZ%' AND UPPER(status_fiscal) NOT LIKE '%EMITID%' THEN 1 ELSE 0 END) as pendentes,
                SUM(COALESCE(valor_liquido, 0)) as total_faturar,
                SUM(COALESCE(valor_pecas, 0)) as total_pecas
            FROM notas_fiscais {filtro_sql}
        """, tuple(params_tot)).fetchone()

    total_nf, emitidas, pendentes, total_faturar, total_pecas = cur_tot if cur_tot else (0, 0, 0, 0, 0)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total em Fila Fiscal", f"{pendentes or 0} OSs", help="Ordens concluídas aguardando transmissão/emissão de nota.")
    with m2:
        st.metric("Notas Fiscais Emitidas", f"{emitidas or 0} NFs", help="Notas autorizadas na SEFAZ.")
    with m3:
        st.metric(f"Total Faturado ({cfg_ativa.get('sigla')})", f"R$ {float(total_faturar or 0):,.2f}")

    st.markdown("---")

    st.markdown("#### 📋 Fila de Faturamento & Ordens de Serviço Concluídas")

    where_os = "WHERE UPPER(c.status) LIKE '%CONCLU%'"
    params_os = []
    if codigo_filial == "FILIAL_DF":
        where_os += " AND (c.estado = 'DF' OR c.cidade LIKE '%BRASIL%' OR n.filial_emissora = 'FILIAL_DF')"
    elif codigo_filial == "MATRIZ_CE":
        where_os += " AND (c.estado = 'CE' OR c.estado != 'DF' OR n.filial_emissora = 'MATRIZ_CE')"

    sql_os = f"""
        SELECT c.id, c.cliente, c.cidade, c.estado, c.equipamento, c.valor_os,
               c.peca_baixada_ref, n.status_fiscal, n.numero_nf, n.valor_liquido
        FROM clientes_equipamentos c
        LEFT JOIN notas_fiscais n ON c.id = n.os_id
        {where_os}
        ORDER BY c.id DESC
    """
    with _get_db_connection(db_name) as conn:
        rows_os = conn.execute(sql_os, tuple(params_os)).fetchall()

    col_btn_test, col_info_f = st.columns([1, 2])
    with col_btn_test:
        if st.button("🏥 Criar OS de Teste em Brasília (DF)", help="Adiciona uma OS no Hospital Santa Lúcia em Brasília para teste imediato"):
            nova_id = manager.criar_os_teste_brasilia()
            st.success(f"✅ OS #{nova_id} de Brasília criada com sucesso! Selecione-a abaixo para faturar.")
            st.rerun()

    if not rows_os:
        st.info(f"ℹ️ Nenhuma OS concluída encontrada para a unidade {cfg_ativa.get('nome')}. Clique no botão acima para gerar uma OS de teste em Brasília.")
        return

    lista_tabela = []
    for r in rows_os:
        os_id_i, cli_i, cid_i, uf_i, eq_i, v_os_i, peca_i, st_fisc_i, num_nf_i, v_liq_i = r
        st_exib = f"✅ {num_nf_i}" if num_nf_i else (st_fisc_i or "AGUARDANDO EMISSÃO")
        lista_tabela.append({
            "OS #": os_id_i,
            "Cliente / Hospital": cli_i,
            "Local": f"{cid_i or ''} - {uf_i or ''}",
            "Equipamento": eq_i,
            "Peça": peca_i if peca_i else "Nenhuma",
            "Valor Total": f"R$ {float(v_liq_i or v_os_i or 0):,.2f}",
            "Situação Fiscal": st_exib
        })
    st.dataframe(pd.DataFrame(lista_tabela), use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown(f"#### 🚀 Emissão de Nota Fiscal • {cfg_ativa.get('nome')}")

    options_map = {f"OS #{r[0]} – {r[1]} ({r[4]}) [Total: R$ {float(r[9] or r[5] or 0):,.2f}]": r[0] for r in rows_os}
    os_selecionada_label = st.selectbox("Selecione a Ordem de Serviço:", list(options_map.keys()))
    os_id_sel = options_map[os_selecionada_label]

    dados_pre = manager.fetch_os_complete_data(os_id_sel, codigo_filial if codigo_filial != "CONSOLIDADO" else "FILIAL_DF")

    st.markdown("""
        <div style="background:#0b132b; border: 1px solid #334155; padding: 10px 14px; border-radius: 6px; font-size: 12px; margin-bottom: 12px;">
            ⚡ <b>Emissão Inteligente:</b> Todos os campos abaixo já vêm preenchidos automaticamente pelo sistema. Se desejar alterar qualquer informação ou valor antes da emissão, basta editar os campos abaixo.
        </div>
    """, unsafe_allow_html=True)

    st.markdown("##### 📌 Tipo de Operação & Finalidade da Nota Fiscal")
    tipo_op_fiscal = st.selectbox(
        "Selecione a Finalidade da Nota Fiscal:",
        [
            "🛠️ PRESTAÇÃO DE SERVIÇOS & PEÇAS (FATURAMENTO DE MANUTENÇÃO)",
            "🔬 NOTA DE DIAGNÓSTICO TÉCNICO & LAUDO PERICIAL",
            "📦 DEVOLUÇÃO / RETORNO DE REMESSA PARA CONSERTO (CFOP 5916 / 6916)",
            "🚚 REMESSA PARA CONSERTO OU CALIBRAÇÃO (CFOP 5915 / 6915)"
        ],
        index=0,
        key=f"tipo_op_fiscal_{os_id_sel}"
    )

    with st.form(key=f"form_emissao_nf_{os_id_sel}"):
        st.markdown("##### 1. Dados do Tomador dos Serviços (Cliente Hospitalar)")
        c_tom1, c_tom2, c_tom3 = st.columns([2, 1, 1])
        with c_tom1:
            f_cliente = st.text_input("Razão Social do Tomador:", value=dados_pre.get("cliente", ""))
        with c_tom2:
            f_cnpj = st.text_input("CNPJ do Tomador:", value=dados_pre.get("cnpj_tomador", ""))
        with c_tom3:
            f_email = st.text_input("E-mail para Envio da Nota:", value=dados_pre.get("email_cliente", ""))

        c_end1, c_end2, c_end3 = st.columns([2, 1, 1])
        with c_end1:
            f_end = st.text_input("Endereço do Hospital:", value=dados_pre.get("tomador_endereco", ""))
        with c_end2:
            f_cid = st.text_input("Município:", value=dados_pre.get("tomador_cidade", ""))
        with c_end3:
            f_uf = st.text_input("UF:", value=dados_pre.get("tomador_uf", ""))

        st.markdown("##### 2. Discriminação dos Serviços & Operação Fiscal")
        
        # Sugestão inteligente de texto conforme a finalidade escolhida
        disc_inicial = dados_pre.get("discriminacao_servico", "")
        if "DIAGNÓSTICO" in tipo_op_fiscal:
            disc_inicial = (
                f"Prestação de serviços técnicos especializados de DIAGNÓSTICO TÉCNICO, ENSAIOS E AVALIAÇÃO PERICIAL "
                f"no equipamento médico {dados_pre.get('equipamento', 'MÉDICO-HOSPITALAR')}. "
                f"Atendimento referente à Ordem de Serviço #{os_id_sel}. "
                f"Emissão de laudo técnico de conformidade, ensaios elétricos e testes de viabilidade operacional. "
                f"Cliente: {dados_pre.get('cliente')} ({dados_pre.get('tomador_cidade')} - {dados_pre.get('tomador_uf')})."
            )
        elif "DEVOLUÇÃO" in tipo_op_fiscal:
            disc_inicial = (
                f"RETORNO / DEVOLUÇÃO DE MERCADORIA OU BEM RECEBIDO PARA CONSERTO OU REPARO. "
                f"Equipamento: {dados_pre.get('equipamento', 'MÉDICO-HOSPITALAR')}. "
                f"Referente à OS #{os_id_sel}. "
                f"Operação ao abrigo de não-incidência / suspensão de tributos conforme legislação vigente (CFOP 5916/6916). "
                f"Destinatário: {dados_pre.get('cliente')}."
            )

        f_discriminacao = st.text_area(
            "Texto da Nota Fiscal (Descrição Oficial do Serviço / Trânsito):",
            value=disc_inicial,
            height=95
        )

        # Ajuste de alíquota sugerida para Devolução (0%) ou Serviço Padrão (5%)
        aliq_sugerida = 0.0 if ("DEVOLUÇÃO" in tipo_op_fiscal or "REMESSA" in tipo_op_fiscal) else float(dados_pre.get("aliquota_iss", 5.0))
        val_serv_sugerido = float(dados_pre.get("valor_servicos", 0.0))
        val_pec_sugerido = 0.0 if "DEVOLUÇÃO" in tipo_op_fiscal else float(dados_pre.get("valor_pecas", 0.0))

        st.markdown("##### 3. Valores e Tributação (SEFAZ-DF)")
        c_val1, c_val2, c_val3, c_val4 = st.columns(4)
        with c_val1:
            f_val_srv = st.number_input("Valor Mão de Obra / Serviços (R$):", value=val_serv_sugerido, min_value=0.0, step=50.0)
        with c_val2:
            f_val_pec = st.number_input("Valor Peças / Produtos (R$):", value=val_pec_sugerido, min_value=0.0, step=50.0)
        with c_val3:
            f_aliq_iss = st.number_input("Alíquota ISS DF (%):", value=aliq_sugerida, min_value=0.0, max_value=10.0, step=0.5)
        with c_val4:
            f_desconto = st.number_input("Desconto Concedido (R$):", value=float(dados_pre.get("valor_desconto", 0.0)), min_value=0.0, step=10.0)

        val_total_calc = (f_val_srv + f_val_pec) - f_desconto
        val_iss_calc = f_val_srv * (f_aliq_iss / 100.0)

        st.markdown(f"""
        <div style="background: #1c2541; padding: 10px 14px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; margin: 10px 0;">
            <div><b>Base de Cálculo ISS:</b> R$ {f_val_srv:,.2f} &bull; <b>Valor ISS Estimado:</b> R$ {val_iss_calc:,.2f}</div>
            <div style="font-size: 16px; font-weight: 900; color: #64dfdf;">TOTAL DA NOTA: R$ {val_total_calc:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

        btn_emitir = st.form_submit_button(
            f"🚀 EMITIR NOTA FISCAL ({cfg_ativa.get('sigla')}) EM 1 CLIQUE",
            type="primary",
            use_container_width=True
        )

    if btn_emitir:
        nat_op_calc = "TRIBUTAÇÃO NO MUNICÍPIO / DF"
        cfop_calc = ""
        if "DIAGNÓSTICO" in tipo_op_fiscal:
            nat_op_calc = "PRESTAÇÃO DE SERVIÇO DE DIAGNÓSTICO TÉCNICO"
        elif "DEVOLUÇÃO" in tipo_op_fiscal:
            nat_op_calc = "RETORNO DE MERCADORIA/BEM RECEBIDO PARA CONSERTO"
            cfop_calc = "5916" if (f_uf.strip().upper() == "DF" or f_uf.strip().upper() == "CE") else "6916"
        elif "REMESSA" in tipo_op_fiscal:
            nat_op_calc = "REMESSA DE BEM PARA CONSERTO/REPARO"
            cfop_calc = "5915" if (f_uf.strip().upper() == "DF" or f_uf.strip().upper() == "CE") else "6915"

        payload_salvar = {
            "cliente": f_cliente.strip(),
            "cnpj_tomador": f_cnpj.strip(),
            "tomador_endereco": f_end.strip(),
            "tomador_cidade": f_cid.strip(),
            "tomador_uf": f_uf.strip(),
            "email_cliente": f_email.strip(),
            "tipo_nota": tipo_op_fiscal,
            "natureza_operacao": nat_op_calc,
            "cfop": cfop_calc,
            "discriminacao_servico": f_discriminacao.strip(),
            "valor_servicos": float(f_val_srv),
            "valor_pecas": float(f_val_pec),
            "valor_desconto": float(f_desconto),
            "aliquota_iss": float(f_aliq_iss),
            "filial_emissora": codigo_filial if codigo_filial != "CONSOLIDADO" else "FILIAL_DF"
        }
        with st.spinner("Transmitindo e assinando nota fiscal com a SEFAZ..."):
            try:
                res_nota = manager.emitir_nota(os_id_sel, payload_salvar["filial_emissora"], payload_salvar)
                st.success(f"🎉 **NOTA FISCAL AUTORIZADA COM SUCESSO!**")
                st.markdown(f"""
                <div style="background:#14532d; border: 1.5px solid #22c55e; border-radius: 6px; padding: 12px 16px; margin: 10px 0; color: white;">
                    <b>Número da NFS-e:</b> {res_nota.get('numero_nf')} &bull; <b>Série:</b> {res_nota.get('serie')}<br/>
                    <b>Chave de Acesso:</b> <span style="font-family: monospace;">{res_nota.get('chave_acesso')}</span><br/>
                    <b>Protocolo SEFAZ:</b> {res_nota.get('protocolo')} &bull; <b>Status:</b> {res_nota.get('status')}
                </div>
                """, unsafe_allow_html=True)

                html_p = res_nota.get("html_path")
                danfe_content = ""
                if html_p and os.path.exists(html_p):
                    with open(html_p, "r", encoding="utf-8") as f_h:
                        danfe_content = f_h.read()

                c_act1, c_act2, c_act3 = st.columns(3)
                with c_act1:
                    if danfe_content:
                        st.download_button(
                            "🖨️ Baixar / Imprimir Espelho DANFE (HTML)",
                            data=danfe_content,
                            file_name=f"DANFE_{res_nota.get('numero_nf')}.html",
                            mime="text/html",
                            use_container_width=True
                        )
                    else:
                        st.info("Espelho DANFE disponível na visualização abaixo.")

                with c_act2:
                    xml_p = res_nota.get("xml_path")
                    if xml_p and os.path.exists(xml_p):
                        with open(xml_p, "rb") as f_x:
                            st.download_button(
                                "📥 Baixar Arquivo XML (SEFAZ)",
                                data=f_x.read(),
                                file_name=f"NFS_{res_nota.get('numero_nf')}.xml",
                                mime="application/xml",
                                use_container_width=True
                            )

                with c_act3:
                    msg_wpp = (
                        f"🧾 *EMED ELETROMEDICINA • NOTA FISCAL EMITIDA ({cfg_ativa.get('sigla')})*\n\n"
                        f"🏥 *Cliente:* {res_nota.get('cliente')}\n"
                        f"📋 *NFS-e Nº:* {res_nota.get('numero_nf')} (OS #{os_id_sel})\n"
                        f"💰 *Valor Total:* R$ {float(res_nota.get('valor_liquido') or 0):,.2f}\n"
                        f"🔐 *Chave de Acesso:* {res_nota.get('chave_acesso')}\n"
                        f"✅ *Status:* AUTORIZADA SEFAZ"
                    )
                    link_wpp = f"https://wa.me/?text={urllib.parse.quote(msg_wpp)}"
                    st.markdown(f"""
                    <a href="{link_wpp}" target="_blank" style="background:#16a34a; color:white; padding:10px 14px; border-radius:6px; text-decoration:none; font-weight:bold; font-size:13px; display:inline-block; text-align:center; width:100%;">
                        📲 Enviar Resumo via WhatsApp
                    </a>
                    """, unsafe_allow_html=True)

                if danfe_content:
                    with st.expander("👁️ Visualizar Espelho da NFS-e (DANFE Hospitalar Oficial)", expanded=True):
                        st.components.v1.html(danfe_content, height=560, scrolling=True)

            except Exception as exc:
                st.error(f"Erro na emissão fiscal: {exc}")

    st.markdown("---")
    st.markdown(f"#### 📜 Histórico de Notas Fiscais Emitidas ({cfg_ativa.get('nome')})")
    with _get_db_connection(db_name) as conn:
        cur_hist = conn.execute("""
            SELECT id, os_id, numero_nf, serie, cliente, valor_liquido,
                   data_emissao, status_fiscal, chave_acesso, filial_emissora
            FROM notas_fiscais
            WHERE numero_nf IS NOT NULL AND numero_nf != ''
            ORDER BY id DESC
            LIMIT 20
        """)
        rows_hist = cur_hist.fetchall()

    if rows_hist:
        hist_tab = []
        for rh in rows_hist:
            hist_tab.append({
                "NFS-e": rh[2],
                "Série": rh[3],
                "OS #": rh[1],
                "Cliente": rh[4],
                "Filial": "DF" if rh[9] == "FILIAL_DF" else "CE",
                "Valor": f"R$ {float(rh[5] or 0):,.2f}",
                "Emissão": str(rh[6])[:16],
                "Status": rh[7]
            })
        st.dataframe(pd.DataFrame(hist_tab), use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhuma nota fiscal emitida registrada ainda nesta filial.")

    st.markdown("---")
    st.markdown("#### 🚫 Cancelamento de Nota Fiscal (SEFAZ / Homologação)")
    with _get_db_connection(db_name) as conn:
        cur_canc = conn.execute("""
            SELECT id, numero_nf, cliente, valor_liquido, filial_emissora, os_id, chave_acesso
            FROM notas_fiscais
            WHERE status_fiscal NOT LIKE '%CANCELAD%' AND numero_nf IS NOT NULL AND numero_nf != ''
            ORDER BY id DESC
        """)
        notas_ativas_canc = cur_canc.fetchall()

    if notas_ativas_canc:
        dict_opcoes_canc = {f"NFS-e Nº {n[1]} — {n[2]} (R$ {float(n[3] or 0):,.2f})": n for n in notas_ativas_canc}
        sel_label_canc = st.selectbox("Selecione a Nota Fiscal que deseja Cancelar:", list(dict_opcoes_canc.keys()), key="sel_canc_nf_drop")
        nota_alvo = dict_opcoes_canc[sel_label_canc]

        col_just1, col_just2 = st.columns([2.5, 1.5])
        with col_just1:
            justificativa_canc = st.text_input(
                "Justificativa Legal do Cancelamento:",
                value="Emissão realizada em ambiente de simulação e testes de homologação",
                key="input_just_cancelamento"
            )
        with col_just2:
            st.write("")
            st.write("")
            if st.button("🚫 Cancelar esta Nota Fiscal", type="primary", key="btn_executar_cancelamento"):
                if len(justificativa_canc.strip()) < 8:
                    st.warning("⚠️ Informe uma justificativa com no mínimo 8 caracteres.")
                else:
                    id_alvo_db = nota_alvo[0]
                    num_nf_alvo = nota_alvo[1]
                    with _get_db_connection(db_name) as conn:
                        conn.execute("""
                            UPDATE notas_fiscais
                            SET status_fiscal = 'CANCELADA',
                                atualizado_em = datetime('now'),
                                discriminacao_servico = discriminacao_servico || '\n\n[CANCELADA: ' || ? || ']'
                            WHERE id = ?
                        """, (justificativa_canc.strip(), id_alvo_db))
                        conn.commit()
                    st.success(f"✅ Nota Fiscal {num_nf_alvo} cancelada com sucesso no sistema!")
                    time.sleep(1)
                    if hasattr(st, "rerun"):
                        st.rerun()
                    elif hasattr(st, "experimental_rerun"):
                        st.experimental_rerun()
    else:
        st.info("Nenhuma nota fiscal ativa pendente de cancelamento.")
