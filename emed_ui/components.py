import os
import streamlit as st
import streamlit.components.v1 as components
from emed_core import limpar_texto


ATALHOS_DESKTOP_META = {
    "📊 Mural & Despacho WhatsApp": ("📊", "Mural & WhatsApp"),
    "📋 Minhas Pendências (Técnico)": ("📋", "Minhas Pendências"),
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


def _injetar_barra_vertical_sidebar():
    """Injeta uma barra vertical retrátil idêntica à barra horizontal do expander,
    colada na borda da aba lateral esquerda para fechar e abrir a aba com 1 toque no celular ou PC.
    """
    html_barra_vertical = """
    <script>
    (function() {
        try {
            const parentDoc = window.parent.document;
            if (!parentDoc || !parentDoc.body) return;

            let bar = parentDoc.getElementById('emed-vertical-sidebar-bar');
            if (!bar) {
                bar = parentDoc.createElement('div');
                bar.id = 'emed-vertical-sidebar-bar';
                bar.title = 'Clique em qualquer ponto desta barra vertical para Fechar ou Abrir a Aba Lateral';
                parentDoc.body.appendChild(bar);
            }

            bar.style.cssText = [
                'position: fixed',
                'top: 16vh',
                'height: 68vh',
                'width: 28px',
                'background-color: #1c2541',
                'border: 1.5px solid #3a506b',
                'border-right: 2px solid #64dfdf',
                'border-left: none',
                'border-radius: 0 10px 10px 0',
                'z-index: 999998',
                'cursor: pointer',
                'display: flex',
                'flex-direction: column',
                'align-items: center',
                'justify-content: space-between',
                'padding: 14px 0',
                'box-shadow: 4px 0 14px rgba(0, 0, 0, 0.6)',
                'transition: left 0.18s ease, background-color 0.18s ease, width 0.15s ease',
                'user-select: none',
                '-webkit-user-select: none'
            ].join(';');

            function isSidebarOpen() {
                const sb = parentDoc.querySelector('section[data-testid="stSidebar"]');
                if (!sb) return false;
                const expanded = sb.getAttribute('aria-expanded');
                const rect = sb.getBoundingClientRect();
                return expanded === 'true' && rect.right > 60;
            }

            function atualizarEstadoVisual() {
                const sb = parentDoc.querySelector('section[data-testid="stSidebar"]');
                const aberta = isSidebarOpen();
                if (aberta && sb) {
                    const rect = sb.getBoundingClientRect();
                    bar.style.left = Math.max(0, Math.floor(rect.right - 2)) + 'px';
                    bar.innerHTML = `
                        <span style="color:#64dfdf; font-size:13px; font-weight:bold;">❮</span>
                        <span style="writing-mode:vertical-rl; transform:rotate(180deg); color:#64dfdf; font-family:sans-serif; font-size:11px; font-weight:700; letter-spacing:1.2px; white-space:nowrap;">
                            🖥️ ABA LATERAL — TOQUE P/ FECHAR
                        </span>
                        <span style="color:#64dfdf; font-size:13px; font-weight:bold;">❮</span>
                    `;
                } else {
                    bar.style.left = '0px';
                    bar.innerHTML = `
                        <span style="color:#64dfdf; font-size:13px; font-weight:bold;">❯</span>
                        <span style="writing-mode:vertical-rl; transform:rotate(180deg); color:#64dfdf; font-family:sans-serif; font-size:11px; font-weight:700; letter-spacing:1.2px; white-space:nowrap;">
                            🖥️ ABA LATERAL — TOQUE P/ ABRIR
                        </span>
                        <span style="color:#64dfdf; font-size:13px; font-weight:bold;">❯</span>
                    `;
                }
            }

            bar.onmouseenter = function() {
                bar.style.backgroundColor = '#25335a';
                bar.style.width = '32px';
            };
            bar.onmouseleave = function() {
                bar.style.backgroundColor = '#1c2541';
                bar.style.width = '28px';
            };

            bar.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                const aberta = isSidebarOpen();
                if (aberta) {
                    const btnClose = parentDoc.querySelector('[data-testid="stSidebarCollapseButton"] button')
                        || parentDoc.querySelector('button[data-testid="stSidebarCollapseButton"]')
                        || parentDoc.querySelector('[data-testid="stSidebarHeader"] button')
                        || parentDoc.querySelector('section[data-testid="stSidebar"] button');
                    if (btnClose) btnClose.click();
                } else {
                    const btnOpen = parentDoc.querySelector('button[data-testid="stExpandSidebarButton"]')
                        || parentDoc.querySelector('[data-testid="stExpandSidebarButton"] button')
                        || parentDoc.querySelector('[data-testid="stExpandSidebarButton"]')
                        || parentDoc.querySelector('[data-testid="stSidebarCollapsedControl"] button')
                        || parentDoc.querySelector('[data-testid="collapsedControl"] button');
                    if (btnOpen) btnOpen.click();
                }
                setTimeout(atualizarEstadoVisual, 60);
                setTimeout(atualizarEstadoVisual, 220);
                setTimeout(atualizarEstadoVisual, 450);
            };

            atualizarEstadoVisual();
            if (window.parent._emedSidebarInterval) {
                clearInterval(window.parent._emedSidebarInterval);
            }
            window.parent._emedSidebarInterval = setInterval(atualizarEstadoVisual, 250);
        } catch (err) {
            console.log('Aviso barra vertical:', err);
        }
    })();
    </script>
    """
    components.html(html_barra_vertical, height=0)


def renderizar_area_trabalho_icones(opcoes_menu: list, acao_atual: str, perfil_atual: str):
    """Renderiza uma grade de ícones estilo Área de Trabalho do Windows / App Launcher
    para facilitar a navegação rápida com 1 toque no celular e no computador, além da barra vertical da sidebar.
    """
    _injetar_barra_vertical_sidebar()

    with st.expander(
        "🖥️ ÁREA DE TRABALHO RÁPIDA (ÍCONES DE ATALHO — TOQUE PARA ABRIR / RECOLHER)",
        expanded=True,
    ):
        st.caption(
            "💡 **Navegação Rápida (Celular & PC):** Toque diretamente num ícone abaixo para mudar de módulo (ou use a barra vertical na borda esquerda para fechar/abrir o menu lateral):"
        )
        colunas_por_linha = 4 if perfil_atual == "Gestor" else 3
        cols = st.columns(colunas_por_linha)
        for idx, opcao in enumerate(opcoes_menu):
            icone, rotulo_curto = ATALHOS_DESKTOP_META.get(opcao, ("📌", opcao))
            ativo = opcao == acao_atual
            prefixo_ativo = "🟢 " if ativo else ""
            with cols[idx % colunas_por_linha]:
                clicou = st.button(
                    f"{prefixo_ativo}{icone} {rotulo_curto}",
                    key=f"desk_tile_{idx}",
                    type="primary" if ativo else "secondary",
                    use_container_width=True,
                    on_click=_selecionar_atalho_desktop,
                    args=(opcao,),
                )
                if clicou and st.session_state.get("menu_acao_ativa") != opcao:
                    _selecionar_atalho_desktop(opcao)
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
