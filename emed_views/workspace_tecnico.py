# -*- coding: utf-8 -*-
"""
EMED Eletromedicina - Módulo de Workspace do Técnico, Caderno de Campo (Keep),
Fábrica de ITs, Cartão de Visita Digital e Navegação com Radares Offline.
"""

import io
import json
import urllib.parse
import streamlit as st
import pandas as pd
import sqlite3

from emed_services.context import AppContext
from emed_services.workspace_service import (
    salvar_nota_workspace,
    listar_notas_workspace,
    excluir_nota_workspace,
    converter_nota_em_it_oficial,
    listar_rascunhos_its,
    aprovar_e_publicar_it,
    CORES_CARDS_DISPONIVEIS
)
from emed_services.radar_service import (
    verificar_radares_proximos,
    obter_estatisticas_radares
)
from emed_services.cartao_visita_service import (
    gerar_vcard_texto,
    gerar_qrcode_base64_vcard,
    render_cartao_html
)

MODALIDADES_HOSPITALARES = [
    "Geral / Multimodal",
    "Mamografia Digital",
    "Raio-X Fixo & Móvel",
    "Arco Cirúrgico (C-Arm)",
    "Ultrassonografia",
    "Tomografia / Ressonância",
    "Centro Cirúrgico & Anestesia",
    "UTI & Monitores Multiparâmetros",
    "Autoclaves & Esterilização",
    "Odontologia Hospitalar"
]

def render_workspace_tecnico(ctx: AppContext):
    db_name = ctx.db_name
    tecnico_atual = ctx.usuario_atual or "Técnico EMED"
    perfil = ctx.perfil_atual or "Técnico"

    st.markdown("""
        <div style="background: linear-gradient(135deg, #092c3e 0%, #0e4b5c 50%, #1a365d 100%);
                    border-radius: 12px; padding: 18px 24px; border: 1.5px solid #00b4d8;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="color: #90e0ef; margin: 0; font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        🛠️ WORKSPACE DO TÉCNICO & FÁBRICA DE ITs
                        <span style="font-size: 13px; background: #00b4d8; color: #03045e; padding: 3px 8px; border-radius: 6px; font-weight: 800;">Produtividade & Campo</span>
                    </h2>
                    <p style="color: #caf0f8; margin: 6px 0 0 0; font-size: 13.5px;">
                        Caderno de campo estilo Keep, fotos de procedimentos, conversão automática em ITs, cartão de visita digital e navegação com radares offline.
                    </p>
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">PROFISSIONAL LOGADO</div>
                    <div style="font-size: 14px; font-weight: 800; color: #48cae4;">👨‍⚕️ {tecnico_atual} ({perfil})</div>
                </div>
            </div>
        </div>
    """.format(tecnico_atual=tecnico_atual, perfil=perfil), unsafe_allow_html=True)

    tab_keep, tab_its, tab_cartao, tab_gps = st.tabs([
        "📌 Caderno de Campo (Estilo Keep)",
        "⚡ Fábrica de ITs & Procedimentos",
        "📇 Cartão de Visita Digital",
        "🛰️ Navegação & Radares (GPS Carro)"
    ])

    # 1. KEEP
    with tab_keep:
        st.markdown("### 📌 Minhas Anotações & Procedimentos de Campo")
        with st.expander("➕ Criar Nova Anotação / Procedimento Rápido", expanded=False):
            with st.form("form_nova_nota_keep"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    nota_titulo = st.text_input("Título do Procedimento / Macete:", placeholder="Ex: Ajuste de Ganho no Mamógrafo Senographe")
                with c2:
                    nota_mod = st.selectbox("Modalidade:", MODALIDADES_HOSPITALARES)

                c3, c4 = st.columns(2)
                with c3:
                    nota_equip = st.text_input("Equipamento / Modelo Alvo:", placeholder="Ex: GE Senographe Crystal Nova")
                with c4:
                    nota_cor_label = st.selectbox("Cor do Card:", list(CORES_CARDS_DISPONIVEIS.keys()))
                    nota_cor_hex = CORES_CARDS_DISPONIVEIS[nota_cor_label]

                nota_conteudo = st.text_area(
                    "Descrição Técnica Detalhada do Procedimento / Falha & Solução:",
                    height=120,
                    placeholder="Descreva o sintoma observado, causa raiz identificada e o procedimento aplicado para resolver..."
                )
                nota_tags = st.text_input("Tags (separadas por vírgula):", placeholder="calibracao, fonte, erro-e04, fusivel")

                sub_nota = st.form_submit_button("💾 Salvar Anotação no Caderno", type="primary", use_container_width=True)
                if sub_nota:
                    if not nota_conteudo.strip():
                        st.error("Por favor, preencha a descrição do procedimento antes de salvar.")
                    else:
                        salvar_nota_workspace(
                            db_name=db_name,
                            tecnico=tecnico_atual,
                            titulo=nota_titulo.strip() or f"Procedimento {nota_equip}",
                            conteudo=nota_conteudo.strip(),
                            equipamento_modelo=nota_equip.strip(),
                            modalidade=nota_mod,
                            cor_card=nota_cor_hex,
                            tags=nota_tags.strip()
                        )
                        st.success("✅ Anotação salva com sucesso no seu caderno de campo!")
                        st.rerun()

        st.markdown("---")
        cf1, cf2 = st.columns([3, 1])
        with cf1:
            busca_termo = st.text_input("🔍 Buscar anotações por palavra-chave, equipamento ou tag:", placeholder="Digite para filtrar...")
        with cf2:
            filtro_mod = st.selectbox("Filtrar por Modalidade:", ["Todas"] + MODALIDADES_HOSPITALARES)

        notas = listar_notas_workspace(
            db_name=db_name,
            tecnico="TODOS" if perfil == "Gestor" else tecnico_atual,
            modalidade=None if filtro_mod == "Todas" else filtro_mod,
            busca=busca_termo
        )

        if not notas:
            st.info("Nenhuma anotação de campo cadastrada ainda. Use o formulário acima para registrar seu primeiro procedimento!")
        else:
            st.markdown(f"**Exibindo {len(notas)} nota(s) registradas:**")
            cols = st.columns(3)
            for idx, n in enumerate(notas):
                col_atual = cols[idx % 3]
                with col_atual:
                    status_badge = "🟢 IT GERADA" if n["status"] == "CONVERTIDO_IT" else "📝 RASCUNHO"
                    cor_bg = n.get("cor_card", "#1e293b")
                    
                    st.markdown(f"""
                        <div style="background: {cor_bg}; border-radius: 12px; padding: 16px; margin-bottom: 15px;
                                    border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 4px 10px rgba(0,0,0,0.3);">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                                <span style="font-size: 11px; background: rgba(255,255,255,0.15); color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold;">
                                    {n['modalidade']}
                                </span>
                                <span style="font-size: 10px; color: #94a3b8;">{status_badge}</span>
                            </div>
                            <h4 style="margin: 0 0 6px 0; color: #38bdf8; font-size: 16px;">{n['titulo']}</h4>
                            <div style="font-size: 12px; color: #cbd5e1; font-weight: 600; margin-bottom: 8px;">
                                ⚙️ {n['equipamento_modelo']}
                            </div>
                            <p style="font-size: 12.5px; color: #e2e8f0; line-height: 1.4; max-height: 120px; overflow-y: auto;">
                                {n['conteudo']}
                            </p>
                            <div style="font-size: 10.5px; color: #94a3b8; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 6px;">
                                👤 {n['tecnico']} • {n['data_criacao']}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    c_btn1, c_btn2 = st.columns([2, 1])
                    with c_btn1:
                        if st.button("⚡ Gerar IT Oficial", key=f"btn_it_{n['id']}", use_container_width=True, type="secondary"):
                            res_it = converter_nota_em_it_oficial(db_name, n["id"], tecnico_atual)
                            if res_it.get("ok"):
                                st.success(f"✅ {res_it.get('msg')}")
                                st.rerun()
                    with c_btn2:
                        if st.button("🗑️", key=f"btn_del_{n['id']}", help="Excluir esta nota"):
                            excluir_nota_workspace(db_name, n["id"])
                            st.rerun()

    # 2. ITs
    with tab_its:
        st.markdown("### ⚡ Central de Instruções de Trabalho (ITs) em Homologação")
        its = listar_rascunhos_its(db_name)
        if not its:
            st.info("Nenhuma minuta de IT em homologação no momento. Clique em '⚡ Gerar IT Oficial' em qualquer nota do Caderno de Campo para criar uma nova!")
        else:
            for it in its:
                with st.expander(f"📋 {it['codigo_it']} — {it['titulo']} ({it['status']})", expanded=(it["status"] == "EM_REVISAO")):
                    st.markdown(f"**Autor:** {it['autor_tecnico']} | **Equipamento:** {it['equipamento']} | **Envio:** {it['data_envio']}")
                    if it.get("aprovado_por"):
                        st.markdown(f"**Aprovado por:** {it['aprovado_por']} em {it['data_aprovacao']}")
                    st.markdown("---")
                    st.markdown(it["conteudo_markdown"])

                    if it["status"] == "EM_REVISAO":
                        st.markdown("---")
                        if perfil == "Gestor":
                            if st.button(f"✅ Aprovar & Publicar {it['codigo_it']} no Acervo Oficial", key=f"btn_aprov_{it['id']}", type="primary"):
                                aprovar_e_publicar_it(db_name, it["id"], tecnico_atual)
                                st.success(f"🎉 IT {it['codigo_it']} aprovada com sucesso! Agora disponível para todos os técnicos.")
                                st.rerun()
                        else:
                            st.info("⏳ Esta IT está em análise pela Engenharia Clínica / Gestor para publicação oficial.")

    # 3. CARTAO
    with tab_cartao:
        st.markdown("### 📇 Cartão de Visita Digital Executivo do Técnico")
        c_card_cfg, c_card_prev = st.columns([1, 1])

        with c_card_cfg:
            st.markdown("#### ⚙️ Dados do Cartão")
            cartao_nome = st.text_input("Nome Completo:", value=tecnico_atual)
            cartao_cargo = st.text_input("Cargo / Especialidade:", value="Especialista em Engenharia Clínica & Diagnóstico por Imagem")
            cartao_tel = st.text_input("WhatsApp / Telefone:", value="(85) 99106-5585")
            cartao_email = st.text_input("E-mail Profissional:", value=f"{tecnico_atual.lower().replace(' ', '.')}@emed.med.br")
            cartao_reg = st.text_input("Registro Profissional:", value="CFT/CREA 2026-EMED")
            cartao_esp = st.text_area("Áreas de Atuação:", value="Mamografia Digital • Raio-X • Tomografia • Centro Cirúrgico • Calibração Biomédica Rastreável", height=80)

            vcard_txt = gerar_vcard_texto(nome=cartao_nome, cargo=cartao_cargo, telefone=cartao_tel, email=cartao_email)

            st.download_button(
                label="📥 Baixar Contato (.vcf) para Enviar no WhatsApp",
                data=vcard_txt,
                file_name=f"{cartao_nome.replace(' ', '_')}_EMED.vcf",
                mime="text/vcard",
                type="primary",
                use_container_width=True
            )

        with c_card_prev:
            st.markdown("#### 📱 Visualização do Cartão")
            qr_b64 = gerar_qrcode_base64_vcard(vcard_txt)
            dados_t = {
                "nome": cartao_nome,
                "cargo": cartao_cargo,
                "telefone": cartao_tel,
                "email": cartao_email,
                "registro_profissional": cartao_reg,
                "especialidades": cartao_esp
            }
            vcard_encoded = urllib.parse.quote(vcard_txt)
            html_cartao = render_cartao_html(dados_t, qr_b64)
            html_cartao = html_cartao.replace("{vcard_encoded_placeholder}", vcard_encoded)
            html_cartao = html_cartao.replace("{nome_sanitizado}", cartao_nome.replace(" ", "_"))
            st.components.v1.html(html_cartao, height=580, scrolling=True)

    # 4. GPS & RADARES
    with tab_gps:
        st.markdown("### 🛰️ Navegação Híbrida & Radares com GPS do Carro")

        with sqlite3.connect(db_name) as conn:
            cur = conn.cursor()
            cur.execute("SELECT placa, modelo, km_atual, ultima_lat, ultima_lon, ultima_atualizacao_gps, condutor_atual FROM veiculos LIMIT 1")
            carro = cur.fetchone()

        c_v1, c_v2, c_v3 = st.columns(3)
        placa = carro[0] if carro else "EMD-2026"
        modelo = carro[1] if carro else "Renault Captur"
        km = carro[2] if carro else 0
        lat = carro[3] if carro else -5.784269
        lon = carro[4] if carro else -35.191667
        atualizacao = carro[5] if carro else "Ao vivo"
        condutor = carro[6] if carro else tecnico_atual

        with c_v1:
            st.metric("🚗 Veículo Vinculado", f"{placa}", f"{modelo}")
        with c_v2:
            st.metric("📍 Coordenadas do Carro", f"{lat:.4f}, {lon:.4f}", f"Atualizado: {atualizacao}")
        with c_v3:
            st.metric("👤 Condutor ao Volante", f"{condutor}", f"Odômetro: {km} KM")

        st.markdown("---")
        c_al1, c_al2 = st.columns([2, 1])
        with c_al1:
            modo_alerta = st.radio(
                "Configuração de Alertas de Radar na Cabine:",
                ["🔔 Alerta Completo (Visual + Sonoro a 400m)",
                 "⚠️ Alerta Discreto (Apenas se acima da velocidade da via)",
                 "🔕 Modo Silencioso (Apenas ícone no mapa)"],
                index=1,
                horizontal=True
            )
        with c_al2:
            raio_busca = st.slider("Raio de Detecção de Radares:", min_value=300, max_value=2500, value=1200, step=100, format="%d metros")

        radares = verificar_radares_proximos(
            db_name=db_name,
            lat_atual=lat,
            lon_atual=lon,
            velocidade_kmh=60.0,
            raio_max_metros=float(raio_busca)
        )

        st.markdown(f"#### 🚨 Radares Detectados no Raio de {raio_busca}m ({len(radares)} encontrados)")

        if not radares:
            st.success("🟢 Nenhum radar ou fiscalização eletrônica detectada nos próximos metros. Boa viagem!")
        else:
            for r in radares:
                cor_alerta = "#dc2626" if r["nivel_alerta"] == "PERIGO" else ("#f59e0b" if r["nivel_alerta"] == "ATENCAO" else "#0284c7")
                icone = "🛑" if r["tipo"] == "SEMAFORO" else ("⚡" if r["tipo"] == "LOMBADA_ELETRONICA" else "📷")
                st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.9); border-left: 6px solid {cor_alerta}; border-radius: 8px;
                                padding: 12px 18px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 15px; font-weight: bold; color: #f8fafc;">
                                {icone} {r['via']} — {r['municipio']}/{r['uf']}
                            </div>
                            <div style="font-size: 12.5px; color: #94a3b8; margin-top: 3px;">
                                Tipo: {r['tipo']} • Sentido: {r['sentido']} • Nível: <strong style="color: {cor_alerta};">{r['nivel_alerta']}</strong>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 20px; font-weight: 900; color: #f8fafc;">
                                🎯 {r['distancia_formatada']}
                            </div>
                            <div style="font-size: 12px; background: {cor_alerta}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; display: inline-block;">
                                Limite: {r['velocidade_limite']} km/h
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 🗺️ Abrir Rota Direta no Waze / Maps:")
        c_nav1, c_nav2 = st.columns(2)
        with c_nav1:
            waze_url = f"https://waze.com/ul?ll={lat},{lon}&navigate=yes"
            st.markdown(f"""
                <a href="{waze_url}" target="_blank" style="display: block; text-align: center; text-decoration: none;
                            background: #0284c7; color: #fff; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px;">
                    🚗 Abrir no Waze (Navegar a partir da Posição do Carro)
                </a>
            """, unsafe_allow_html=True)
        with c_nav2:
            maps_url = f"https://www.google.com/maps/dir/?api=1&origin={lat},{lon}"
            st.markdown(f"""
                <a href="{maps_url}" target="_blank" style="display: block; text-align: center; text-decoration: none;
                            background: #059669; color: #fff; padding: 12px; border-radius: 8px; font-weight: bold; font-size: 15px;">
                    🗺️ Abrir no Google Maps (Traçar Rota)
                </a>
            """, unsafe_allow_html=True)
