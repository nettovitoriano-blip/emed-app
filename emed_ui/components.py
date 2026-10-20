import os
import streamlit as st
import streamlit.components.v1 as components
from emed_core import limpar_texto


ATALHOS_DESKTOP_META = {
    "🤖 EmedOnline (Triagem & Rota)": ("🤖", "EmedOnline"),
    "⏰ Alarmes de Calibração & Créditos": ("⏰", "Alarmes Calibração"),
    "📊 Mural & Despacho WhatsApp": ("📊", "Mural & WhatsApp"),
    "📋 Minhas Pendências (Técnico)": ("📋", "Minhas Pendências"),
    "📚 Manuais & Procedimentos": ("📚", "Manuais & POPs"),
    "🎫 Abertura de Chamados & OS": ("🎫", "Chamados & OS"),
    "📦 Solicitação de Peças & Ferramentas": ("📦", "Pedir Peças / Instr."),
    "👥 Clientes & Equipamentos": ("🏥", "Clientes & QR Code"),
    "🗺️ Mapa & Planeamento de Rotas": ("🗺️", "Mapa & Rotas"),
    "📈 Gráficos & BI": ("📈", "Gráficos & BI"),
    "⏳ Follow-up de Orçamentos": ("⏳", "Follow-up Orçam."),
    "🧾 Faturamento & Notas Fiscais": ("🧾", "Notas Fiscais (NF)"),
    "📦 Gestão de Estoque & Peças": ("🏭", "Almoxarifado / Est."),
    "🚨 Gestão de Pendências": ("🚨", "Direcionar Pend."),
    "⚙️ Gestão & Administração": ("⚙️", "Equipe & Frota"),
    "🚗 Atualizar Quilometragem (Opcional)": ("🚗", "Atualizar KM"),
    "📝 Editor Direto da Planilha": ("📝", "Editor da Base"),
}


def _selecionar_atalho_desktop(opcao_escolhida: str):
    """Callback executado antes da re-renderização para sincronizar a grade de ícones e a sidebar."""
    st.session_state.menu_acao_ativa = opcao_escolhida
    st.session_state.nav_sync_id = st.session_state.get("nav_sync_id", 0) + 1


def _alternar_aba_lateral():
    """Alterna o estado visível/oculto da aba lateral esquerda."""
    st.session_state.aba_lateral_oculta = not st.session_state.get("aba_lateral_oculta", False)


def _alternar_area_trabalho_horizontal():
    """Alterna o recolhimento/abertura da Área de Trabalho Rápida horizontal."""
    st.session_state.area_trabalho_aberta = not st.session_state.get("area_trabalho_aberta", True)


def _alternar_modo_edicao_atalhos():
    """Alterna o modo de edição/exclusão de botões superiores e garante a área aberta."""
    novo_estado = not st.session_state.get("modo_edicao_atalhos", False)
    st.session_state.modo_edicao_atalhos = novo_estado
    if novo_estado:
        st.session_state.area_trabalho_aberta = True


def renderizar_area_trabalho_icones(
    opcoes_menu: list,
    acao_atual: str,
    perfil_atual: str,
    usuario_atual: str = "NETTO",
    db_name: str = "",
):
    """Renderiza os 3 botões de controlo minimalistas (apenas ícones, próximos à esquerda e sem background):
    1. ▶️ / ◀️ (Abrir/Esconder Aba Lateral Esquerda)
    2. 🔽 🖥️ / ▶️ 🖥️ (Abrir/Recolher Área de Trabalho Rápida)
    3. 🛠️ (Configurar/Excluir Botões da Página Principal por Utilizador)
    """
    from emed_services import (
        DB_NAME as DEFAULT_DB_NAME,
        carregar_atalhos_excluidos_usuario,
        salvar_atalhos_excluidos_usuario,
    )

    caminho_db = db_name or DEFAULT_DB_NAME
    usr_key = limpar_texto(usuario_atual, "NETTO").upper()

    if "aba_lateral_oculta" not in st.session_state:
        st.session_state.aba_lateral_oculta = False

    if "area_trabalho_aberta" not in st.session_state:
        st.session_state.area_trabalho_aberta = True

    if "modo_edicao_atalhos" not in st.session_state:
        st.session_state.modo_edicao_atalhos = False

    if st.session_state.aba_lateral_oculta:
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] {
                display: none !important;
                width: 0px !important;
                min-width: 0px !important;
                max-width: 0px !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    excluidos_usuario = carregar_atalhos_excluidos_usuario(caminho_db, usr_key)
    opcoes_visiveis = [op for op in opcoes_menu if op not in excluidos_usuario]
    modo_edicao = st.session_state.modo_edicao_atalhos

    # Três botões somente com ícones, alinhados totalmente à esquerda e sem background (type="tertiary")
    with st.container(horizontal=True, horizontal_alignment="left", vertical_alignment="center", gap="small"):
        icone_aba = "▶️" if st.session_state.aba_lateral_oculta else "◀️"
        st.button(
            icone_aba,
            key="btn_barra_toggle_sidebar_main",
            type="tertiary",
            help="Abrir / Esconder Aba Lateral Esquerda",
            on_click=_alternar_aba_lateral,
        )
        seta_horiz = "🔽" if st.session_state.area_trabalho_aberta else "▶️"
        st.button(
            f"{seta_horiz} 🖥️",
            key="btn_barra_toggle_desktop_horiz",
            type="tertiary",
            help="Abrir / Recolher Área de Trabalho Rápida",
            on_click=_alternar_area_trabalho_horizontal,
        )
        icone_cfg = "🟢🛠️" if modo_edicao else "🛠️"
        st.button(
            icone_cfg,
            key="btn_barra_toggle_edicao",
            type="tertiary",
            help=f"Editar / Excluir Botões da Área de Trabalho ({usr_key})",
            on_click=_alternar_modo_edicao_atalhos,
        )

    if st.session_state.area_trabalho_aberta:
        with st.container():
            if modo_edicao:
                st.caption(
                    f"✏️ **Edição de Atalhos (`{usr_key}`):** Toque em **❌** para ocultar qualquer botão superior "
                    "*(os botões da aba lateral esquerda são fixos e nunca são removidos)*."
                )

            if not opcoes_visiveis:
                st.caption(
                    "✨ Área de Trabalho clean! Clique no ícone **🛠️** acima para restaurar atalhos ou use a Aba Lateral Esquerda."
                )
            else:
                colunas_por_linha = 3 if modo_edicao else (4 if perfil_atual == "Gestor" else 3)
                cols = st.columns(colunas_por_linha)
                for idx, opcao in enumerate(opcoes_visiveis):
                    icone, rotulo_curto = ATALHOS_DESKTOP_META.get(opcao, ("📌", opcao))
                    ativo = opcao == acao_atual
                    prefixo_ativo = "🟢 " if ativo else ""
                    idx_global = opcoes_menu.index(opcao)
                    with cols[idx % colunas_por_linha]:
                        if modo_edicao:
                            c_btn, c_del = st.columns([4.2, 1.0])
                            with c_btn:
                                clicou = st.button(
                                    f"{prefixo_ativo}{icone} {rotulo_curto}",
                                    key=f"desk_tile_{idx_global}",
                                    type="primary" if ativo else "secondary",
                                    use_container_width=True,
                                    on_click=_selecionar_atalho_desktop,
                                    args=(opcao,),
                                )
                                if clicou and st.session_state.get("menu_acao_ativa") != opcao:
                                    _selecionar_atalho_desktop(opcao)
                                    st.rerun()
                            with c_del:
                                if st.button(
                                    "❌",
                                    key=f"del_tile_{idx_global}",
                                    type="tertiary",
                                    help=f"Excluir '{rotulo_curto}' da página principal de {usr_key}",
                                ):
                                    nova_lista = list(set(excluidos_usuario + [opcao]))
                                    salvar_atalhos_excluidos_usuario(caminho_db, usr_key, nova_lista)
                                    st.rerun()
                        else:
                            clicou = st.button(
                                f"{prefixo_ativo}{icone} {rotulo_curto}",
                                key=f"desk_tile_{idx_global}",
                                type="primary" if ativo else "secondary",
                                use_container_width=True,
                                on_click=_selecionar_atalho_desktop,
                                args=(opcao,),
                            )
                            if clicou and st.session_state.get("menu_acao_ativa") != opcao:
                                _selecionar_atalho_desktop(opcao)
                                st.rerun()

            if modo_edicao:
                st.markdown("---")
                c_preset1, c_preset2 = st.columns(2)
                with c_preset1:
                    if st.button(
                        "⭐ Deixar Apenas os 5 Mais Usados (Mural, Pendências, OS, Clientes, NF)",
                        key="btn_preset_mais_usados",
                        use_container_width=True,
                    ):
                        favoritos = {
                            "📊 Mural & Despacho WhatsApp",
                            "📋 Minhas Pendências (Técnico)",
                            "🎫 Abertura de Chamados & OS",
                            "👥 Clientes & Equipamentos",
                            "🧾 Faturamento & Notas Fiscais",
                        }
                        excluidos_auto = [op for op in opcoes_menu if op not in favoritos]
                        salvar_atalhos_excluidos_usuario(caminho_db, usr_key, excluidos_auto)
                        st.rerun()
                with c_preset2:
                    if st.button(
                        "🔄 Restaurar Todos os Botões Padrão da Área de Trabalho",
                        key="btn_restaurar_todos_atalhos",
                        use_container_width=True,
                    ):
                        salvar_atalhos_excluidos_usuario(caminho_db, usr_key, [])
                        st.rerun()

                if excluidos_usuario:
                    st.caption(f"📦 **Botões ocultados da Área de Trabalho de `{usr_key}` (clique para restaurar individualmente):**")
                    cols_rest = st.columns(4)
                    excluidos_validos = [op for op in excluidos_usuario if op in opcoes_menu]
                    for r_idx, op_exc in enumerate(excluidos_validos):
                        icone_e, rot_e = ATALHOS_DESKTOP_META.get(op_exc, ("📌", op_exc))
                        with cols_rest[r_idx % 4]:
                            if st.button(
                                f"➕ Restaurar: {icone_e} {rot_e}",
                                key=f"rest_tile_{r_idx}",
                                use_container_width=True,
                            ):
                                nova_lista = [x for x in excluidos_usuario if x != op_exc]
                                salvar_atalhos_excluidos_usuario(caminho_db, usr_key, nova_lista)
                                st.rerun()


def estilizar_grafico(fig):
    fig.update_layout(
        font=dict(color="white"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickfont=dict(color="white"), title_font=dict(color="white")),
        yaxis=dict(tickfont=dict(color="white"), title_font=dict(color="white")),
        legend=dict(font=dict(color="white"))
    )
    return fig


def renderizar_rubrica_tecnico(nome_tec, equipa_dict):
    nome_up = limpar_texto(nome_tec, "TÉCNICO").upper()
    info_t = equipa_dict.get(nome_up, {})
    ass_cft = limpar_texto(info_t.get("assinatura"), f"{nome_up} - CFT")
    caminho_rub = limpar_texto(info_t.get("rubrica_img"), "")

    st.markdown(f"""
        <div style="background: #0b132b; border: 1.5px solid #64dfdf; border-radius: 10px; padding: 14px; text-align: center;">
            <span style="background: #10b981; color: #0b132b; font-weight: bold; font-size: 11px; padding: 3px 10px; border-radius: 12px;">
                ✅ RUBRICA TÉCNICA PRÉ-SALVA & AUTENTICADA
            </span>
            <div style="font-family: 'Brush Script MT', 'Segoe Script', 'Lucida Handwriting', cursive; font-size: 28px; color: #64dfdf; margin: 10px 0 4px 0; letter-spacing: 1px;">
                {nome_up.title()}
            </div>
            <hr style="border: 0; border-top: 1px dashed #3a506b; width: 80%; margin: 6px auto;">
            <p style="margin: 2px 0; font-size: 13px; font-weight: bold; color: #ffffff !important;">{ass_cft}</p>
            <p style="margin: 0; font-size: 11px; color: #94a3b8 !important;">Responsável Técnico EMED Eletromedicina</p>
        </div>
    """, unsafe_allow_html=True)
    if caminho_rub and os.path.exists(caminho_rub):
        st.image(caminho_rub, caption=f"Rubrica Digital — {ass_cft}", width=220)


def renderizar_quadro_assinatura_cliente(idx_key):
    label_alvo = f"Código Digital da Rubrica do Cliente #{idx_key}"
    html_pad = f"""
    <div style="background:#1c2541; border:1px solid #3a506b; border-radius:10px; padding:10px; color:#fff; font-family:Arial, sans-serif;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-size:13px; font-weight:bold; color:#64dfdf;">📱 Assine com o dedo na tela abaixo (Cliente / Hospital):</span>
            <span id="status_sig_{idx_key}" style="font-size:12px; color:#fbbf24;">Aguardando rubrica...</span>
        </div>
        <canvas id="canvas_sig_{idx_key}" width="520" height="155"
            style="width:100%; height:155px; background:#0b132b; border:1.5px dashed #64dfdf; border-radius:8px; touch-action:none; cursor:crosshair;">
        </canvas>
        <div style="display:flex; gap:10px; margin-top:8px;">
            <button type="button" onclick="limparSig_{idx_key}()"
                style="flex:1; padding:9px; background:#3a506b; color:#fff; border:1px solid #64dfdf; border-radius:6px; font-weight:bold; cursor:pointer;">
                🧹 Limpar Quadro
            </button>
            <button type="button" onclick="confirmarSig_{idx_key}()"
                style="flex:2; padding:9px; background:#10b981; color:#0b132b; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">
                ✅ Fixar Assinatura do Cliente na OS
            </button>
        </div>
    </div>
    <script>
        (function() {{
            const canvas = document.getElementById('canvas_sig_{idx_key}');
            const ctx = canvas.getContext('2d');
            let desenhando = false;
            let temTraco = false;

            function ajustarEscala() {{
                const rect = canvas.getBoundingClientRect();
                if (rect.width > 0 && canvas.width !== Math.floor(rect.width)) {{
                    canvas.width = Math.floor(rect.width);
                    canvas.height = 155;
                }}
                ctx.strokeStyle = '#64dfdf';
                ctx.lineWidth = 2.6;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
            }}
            setTimeout(ajustarEscala, 150);

            function obterPos(e) {{
                const rect = canvas.getBoundingClientRect();
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                return {{
                    x: (clientX - rect.left) * (canvas.width / rect.width),
                    y: (clientY - rect.top) * (canvas.height / rect.height)
                }};
            }}

            function iniciar(e) {{
                e.preventDefault();
                desenhando = true;
                temTraco = true;
                ctx.strokeStyle = '#64dfdf';
                ctx.lineWidth = 2.6;
                ctx.lineCap = 'round';
                const p = obterPos(e);
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
            }}

            function mover(e) {{
                if (!desenhando) return;
                e.preventDefault();
                const p = obterPos(e);
                ctx.lineTo(p.x, p.y);
                ctx.stroke();
            }}

            function parar(e) {{
                if (!desenhando) return;
                e.preventDefault();
                desenhando = false;
            }}

            canvas.addEventListener('mousedown', iniciar);
            canvas.addEventListener('mousemove', mover);
            window.addEventListener('mouseup', parar);
            canvas.addEventListener('touchstart', iniciar, {{passive: false}});
            canvas.addEventListener('touchmove', mover, {{passive: false}});
            canvas.addEventListener('touchend', parar, {{passive: false}});

            window.limparSig_{idx_key} = function() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                temTraco = false;
                document.getElementById('status_sig_{idx_key}').innerHTML = 'Quadro limpo.';
                document.getElementById('status_sig_{idx_key}').style.color = '#fbbf24';
            }};

            window.confirmarSig_{idx_key} = function() {{
                if (!temTraco) {{
                    alert('Por favor, peça ao cliente para assinar com o dedo no quadro antes de fixar!');
                    return;
                }}
                const dataUrl = canvas.toDataURL('image/png');
                try {{
                    const parentDoc = window.parent.document;
                    const inputAlvo = parentDoc.querySelector('input[aria-label="{label_alvo}"]');
                    if (inputAlvo) {{
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
                        nativeSetter.call(inputAlvo, dataUrl);
                        inputAlvo.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        inputAlvo.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        inputAlvo.focus();
                        inputAlvo.blur();
                    }}
                }} catch (err) {{
                    console.log('Aviso de sincronizacao:', err);
                }}
                document.getElementById('status_sig_{idx_key}').innerHTML = '✅ Assinatura capturada com sucesso!';
                document.getElementById('status_sig_{idx_key}').style.color = '#10b981';
            }};
        }})();
    </script>
    """
    components.html(html_pad, height=245)
    return label_alvo
