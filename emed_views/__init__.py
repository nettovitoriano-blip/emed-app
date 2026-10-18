from emed_views.portal_qr import verificar_e_renderizar_portal_qr
from emed_views.mural_despacho import render_mural_despacho, render_minhas_pendencias
from emed_views.bi_analytics import render_graficos_bi
from emed_views.comercial_orcamentos import render_followup_orcamentos
from emed_views.clientes_parque import render_clientes_equipamentos
from emed_views.chamados_os import render_chamados_os
from emed_views.logistica_estoque import (
    render_gestao_pendencias,
    render_solicitacao_pecas,
    render_mapa_rotas,
    render_gestao_estoque,
)
from emed_views.administracao import (
    render_gestao_administracao,
    render_atualizar_km,
    render_editor_planilha,
)

VIEW_ROUTER = {
    "📊 Mural & Despacho WhatsApp": render_mural_despacho,
    "📋 Minhas Pendências (Técnico)": render_minhas_pendencias,
    "📈 Gráficos & BI": render_graficos_bi,
    "⏳ Follow-up de Orçamentos": render_followup_orcamentos,
    "👥 Clientes & Equipamentos": render_clientes_equipamentos,
    "🎫 Abertura de Chamados & OS": render_chamados_os,
    "🚨 Gestão de Pendências": render_gestao_pendencias,
    "📦 Solicitação de Peças & Ferramentas": render_solicitacao_pecas,
    "🗺️ Mapa & Planeamento de Rotas": render_mapa_rotas,
    "📦 Gestão de Estoque & Peças": render_gestao_estoque,
    "⚙️ Gestão & Administração": render_gestao_administracao,
    "🚗 Atualizar Quilometragem (Opcional)": render_atualizar_km,
    "📝 Editor Direto da Planilha": render_editor_planilha,
}

__all__ = [
    "verificar_e_renderizar_portal_qr",
    "render_mural_despacho",
    "render_minhas_pendencias",
    "render_graficos_bi",
    "render_followup_orcamentos",
    "render_clientes_equipamentos",
    "render_chamados_os",
    "render_gestao_pendencias",
    "render_solicitacao_pecas",
    "render_mapa_rotas",
    "render_gestao_estoque",
    "render_gestao_administracao",
    "render_atualizar_km",
    "render_editor_planilha",
    "VIEW_ROUTER",
]
