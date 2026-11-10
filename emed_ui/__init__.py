from emed_ui.styles import inject_custom_css
from emed_ui.components import (
    estilizar_grafico,
    renderizar_rubrica_tecnico,
    renderizar_quadro_assinatura_cliente,
    renderizar_area_trabalho_icones,
)
from emed_ui.offline_pwa import gerar_html_coletor_offline

__all__ = [
    "inject_custom_css",
    "estilizar_grafico",
    "renderizar_rubrica_tecnico",
    "renderizar_quadro_assinatura_cliente",
    "renderizar_area_trabalho_icones",
    "gerar_html_coletor_offline",
]
