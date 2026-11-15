# -*- coding: utf-8 -*-
"""
Gerador de Mensagens e Briefings Diários Operacionais da EMED Eletromedicina.
Atualiza dinamicamente 1x por dia com base no dia do ano, proporcionando
recomendações técnicas de alta complexidade, segurança clínica e engajamento.
"""

from datetime import datetime

BRIEFINGS_DIARIOS = [
    {
        "tema": "⚡ Segurança Elétrica Hospitalar (NBR IEC 60601-1)",
        "dica": "Em ambientes cirúrgicos e hemodinâmica, teste a resistência do condutor de proteção (terra) e a corrente de fuga do chassi antes de liberar qualquer equipamento crítico. Rigor técnico salva vidas!",
        "missao": "Garantir 100% de conformidade de isolamento elétrico nas OSs de hoje."
    },
    {
        "tema": "🎯 Calibração de Alta Tensão & Geradores HF",
        "dica": "Ao checar geradores de raios-X, verifique a curva de subida do kVp com dosímetro ou osciloscópio atenuado. Oscilações de tensão desgastam prematuramente o filamento do tubo.",
        "missao": "Validar estabilidade de kVp e tempo de exposição em todas as manutenções preventivas."
    },
    {
        "tema": "🛡️ Proteção Radiológica & RDC 611/2022",
        "dica": "O alinhamento do colimador luminoso com o feixe de radiação deve ter desvio inferior a 2% da DFF. Colimador descalibrado expõe o paciente a doses espúrias desnecessárias.",
        "missao": "Aferir alinhamento de campo luminoso e feixe de raios-X em cada equipamento atendido."
    },
    {
        "tema": "🔍 Tomografia Computadorizada — Alinhamento & Hot Iso",
        "dica": "Na substituição de tubo de CT ou manutenção periódica, valide o Hot Isocenter mecânico e o detector. Um alinhamento micrométrico elimina anéis e ruídos nas imagens axiais.",
        "missao": "Executar QA e calibração de água/ar antes de devolver a máquina para uso clínico."
    },
    {
        "tema": "🧰 Cautela e Preservação de Instrumentos RBC",
        "dica": "Multímetros True-RMS e dosímetros são o coração da nossa precisão. Desconecte baterias 9V após as medições e mantenha os instrumentos protegidos em suas maletas de transporte.",
        "missao": "Checar validade dos certificados RBC e estado dos cabos e pontas de prova."
    },
    {
        "tema": "🤝 Excelência no Relacionamento Hospitalar",
        "dica": "Ao finalizar a OS, realize sempre o disparo de teste na presença do operador do hospital e colha a assinatura digital na tela com o nome legível do responsável. Confiança é nosso maior ativo.",
        "missao": "Coletar aceite formal e assinatura touch em 100% dos laudos emitidos hoje."
    },
    {
        "tema": "🩺 Mamografia — Calibração do AEC & Compressão",
        "dica": "A força de compressão mecânica deve estar calibrada entre 15 kg e 20 kg, com desligamento automático suave para conforto e segurança da paciente.",
        "missao": "Verificar balança de compressão e espessura com phantom padrão em mamógrafos."
    },
    {
        "tema": "💡 Manutenção Preventiva em Arco Cirúrgico",
        "dica": "Limpeza e lubrificação das guias do braço em 'C' e teste das travas eletromagnéticas evitam paradas repentinas durante procedimentos cirúrgicos complexos.",
        "missao": "Checar travas, rotação orbital e integridade dos cabos do intensificador/flat panel."
    },
    {
        "tema": "🚀 Agilidade e Conexão em Tempo Real",
        "dica": "Sincronize o aplicativo logo no início do dia para carregar suas rotas e peças separadas. Em caso de dúvidas no campo, acerte as ITs oficiais no menu de Manuais.",
        "missao": "Manter status de check-in e check-out atualizados para otimização da frota."
    },
    {
        "tema": "🔬 Termografia e Pontos Quentes em Painéis",
        "dica": "Em no-breaks e transformadores de alta potência, utilize o termovisor infravermelho para detectar conexões frouxas ou oxidação antes que provoquem desarme geral.",
        "missao": "Inspecionar bornes de alimentação trifásica dos geradores e chillers."
    },
    {
        "tema": "🧼 Limpeza e Higienização Técnica",
        "dica": "Utilize apenas álcool isopropílico e panos de microfibra em placas eletrônicas e ópticas. Solventes abrasivos podem danificar os revestimentos anti-reflexo dos detectores.",
        "missao": "Garantir limpeza técnica impecável em gabinetes, filtros de ar e túneis de ventilação."
    },
    {
        "tema": "📊 Documentação e Laudos de 1 Página",
        "dica": "Descreva claramente a ação corretiva executada e as peças substituídas. O laudo técnico em PDF gerado no app é o histórico pericial da instituição de saúde.",
        "missao": "Detalhamento técnico claro e conciso em cada relatório finalizado."
    },
    {
        "tema": "🔋 No-Breaks e Bancos de Bateria em Diagnóstico",
        "dica": "Teste a tensão individual de cada bateria sob carga. Uma única célula sulfatada derruba a autonomia do no-break durante uma queda de energia no hospital.",
        "missao": "Registrar medição de tensão de flutuação e temperatura dos bancos de bateria."
    },
    {
        "tema": "⚙️ Mecânica de Precisão e Torque",
        "dica": "Utilize torquímetro calibrado nos parafusos de fixação do tubo e do anel deslizante (slip ring). Aperto excessivo espana roscas; aperto insuficiente causa vibração e ruído.",
        "missao": "Seguir fielmente as especificações de torque da IT oficial do fabricante."
    },
    {
        "tema": "🏥 Humanização e Impacto do Nosso Trabalho",
        "dica": "Por trás de cada tomógrafo ou raio-X funcionando, há um paciente esperando por um diagnóstico que pode salvar sua vida. Cada minuto economizado faz a diferença.",
        "missao": "Trabalhar com orgulho e consciência do impacto direto na saúde das pessoas."
    }
]

def obter_briefing_diario() -> dict:
    agora = datetime.now()
    dia_ano = agora.timetuple().tm_yday
    idx = dia_ano % len(BRIEFINGS_DIARIOS)
    item = BRIEFINGS_DIARIOS[idx]
    
    hora = agora.hour
    if 5 <= hora < 12:
        saudacao = "Bom dia, Família eMED! ☀️"
        slogan = "Que o dia seja abençoado, produtivo e com máxima segurança nos atendimentos!"
    elif 12 <= hora < 18:
        saudacao = "Boa tarde, Guerreiros eMED! ⚡"
        slogan = "Seguimos com excelência técnica e foco na pontualidade das OSs!"
    else:
        saudacao = "Boa noite, Equipe eMED! ⭐"
        slogan = "Dever cumprido com maestria! Bom descanso e retorno seguro para casa."

    return {
        "saudacao": saudacao,
        "slogan": slogan,
        "mensagem": f"{item['tema']}: {item['dica']}",
        "tema": item["tema"],
        "dica_tecnica": item["dica"],
        "missao_do_dia": item["missao"],
        "dia_do_ano": dia_ano,
        "data_formatada": agora.strftime("%d/%m/%Y"),
        "atualizado_uma_vez_ao_dia": True
    }
