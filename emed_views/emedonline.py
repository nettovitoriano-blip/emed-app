import re
import io
import os
import base64
import hashlib
import urllib.parse
import pandas as pd
import streamlit as st
from datetime import datetime
from emed_core import (
    limpar_texto,
    obter_id_os,
    obter_kit_por_servico,
    acionar_separacao_automatica_almoxarifado,
)
from emed_services import (
    AppContext,
    salvar_dados_seguro,
    calcular_distancia,
)


def _gerar_qrcode_base64(url: str) -> str:
    """Gera um QR Code em base64 diretamente em memória."""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0B3B60", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"
    except Exception:
        return f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={urllib.parse.quote(url)}"


def _buscar_cliente_por_cnpj_ou_nome(df: pd.DataFrame, termo_busca: str):
    """Busca clientes por CNPJ limpo ou nome parcial."""
    if not termo_busca or df.empty:
        return pd.DataFrame()
    
    termo = limpar_texto(termo_busca, "").upper().replace(".", "").replace("/", "").replace("-", "")
    
    # Busca por CNPJ
    def _match_cnpj(val):
        c_limpo = limpar_texto(val, "").replace(".", "").replace("/", "").replace("-", "")
        return termo in c_limpo if termo else False

    # Busca por Nome
    def _match_nome(val):
        n_limpo = limpar_texto(val, "").upper()
        return termo_busca.strip().upper() in n_limpo if termo_busca.strip() else False

    mascara = df["cnpj"].astype(str).apply(_match_cnpj) | df["cliente"].astype(str).apply(_match_nome)
    return df[mascara]


def _detectar_modalidade(nome_equip: str, texto_defeito: str = "") -> str:
    """Classifica com rigor a modalidade do equipamento médico para triagem técnica personalizada conforme a taxonomia da EMED.
    Utiliza regex com limites de palavras (\b) para evitar falsos positivos (ex: 'COMPACTO' contendo 'CT').
    """
    nome_up = str(nome_equip or "").upper().strip()
    def_up = str(texto_defeito or "").upper().strip()

    # 1. Avaliação primária pelo Nome do Equipamento
    if nome_up:
        # Mamografia ('MM', 'MAMO', 'MAMÓGRAFO', 'SENOGRAPHE', 'MAMMOMAT', etc.)
        if re.search(r'\b(MM|MAMO|MAMOGRAFO|MAMÓGRAFO|SENOGRAPHE|SELENIA|MAMMOMAT|DIAMOND)\b', nome_up):
            return "MAMOGRAFIA"

        # Densitometria ('DO', 'DENSITO', 'DENSITOMETRIA', 'LUNAR', 'PRODIGY', etc.)
        if re.search(r'\b(DO|DENSITO|DENSITOMETRIA|DENSITOMETRO|DENSITÔMETRO|LUNAR|PRODIGY|DPX|HOLOGIC|DISCOVERY)\b', nome_up):
            return "DENSITOMETRIA"

        # Arco Cirúrgico ('ARCO', 'C-ARM', 'CARM', 'BV PULSERA', etc.)
        if re.search(r'\b(ARCO|C-ARM|CARM|BV PULSERA|BV ENDURA|ZIEHM|OEC|FLUORO|FLUOROSCOPIA)\b', nome_up):
            return "ARCO CIRÚRGICO"

        # Tomografia ('TC', 'TOMOGRA', 'TOMOGRAFO', 'BRIGHTSPEED', etc.)
        # JAMAIS casa com COMPACTO ou COMPACT
        if re.search(r'\b(TOMOGRA|TOMOGRAFO|TOMÓGRAFO|TOMOGRAFIA|BRIGHTSPEED|BRIGTHSPEED|SOMATOM|OPTIMA|REVOLUTION|LIGHTSPEED|EMOTION|GANTRY)\b', nome_up):
            return "TOMOGRAFIA"
        if re.search(r'\b(TC|CT)\b', nome_up) and not re.search(r'\b(COMPACTO|COMPACT)\b', nome_up):
            return "TOMOGRAFIA"

        # Sistema Digital puro (Flat Panel, Detector DR, etc.)
        if re.search(r'\b(FLAT PANEL|DETECTOR DR|DIGITALIZADOR CR|NEUVISION)\b', nome_up):
            return "SISTEMA DIGITAL (DR / CR)"

        # Raio-X Convencional / Móvel / Fixo
        if re.search(r'\b(RAIO|RAIO-X|RAIO X|RX|COMPACTO|ALTUS|INTERCAL|ESTATIVA|BUCKY|COLIMADOR|GERADOR|TUBO|MULTIX|XR|XR6000|TRANSP|MOVEL|MÓVEL)\b', nome_up):
            return "RAIO-X"

    # 2. Avaliação secundária pelo relato do defeito (se o equipamento for 'Outro' ou genérico)
    if re.search(r'\b(GANTRY|CHILLER|SLIPRING)\b', def_up):
        return "TOMOGRAFIA"
    if re.search(r'\b(COMPRESSOR|ACRILICO|CASSETE MAMO)\b', def_up):
        return "MAMOGRAFIA"
    if re.search(r'\b(ARCO|BRACO EM C|BRAÇO EM C)\b', def_up):
        return "ARCO CIRÚRGICO"
    if re.search(r'\b(ESTATIVA|COLIMADOR|BUCKY|FREIO|SOLENOIDE|PEDAL DE FREIO)\b', def_up):
        return "RAIO-X"
    if re.search(r'\b(FLAT PANEL|DETECTOR|CASSETE)\b', def_up):
        return "SISTEMA DIGITAL (DR / CR)"

    return "RAIO-X"


def _obter_dica_rapida_it(equipamento: str, relato: str) -> str:
    """Verifica se há orientações de primeiro nível baseadas nos POPs e ITs da EMED."""
    txt = (str(equipamento) + " " + str(relato)).upper()
    
    if any(w in txt for w in ["FREIO", "ESTATIVA", "PORTA TUBO", "PORTA-TUBO", "DESTRAV", "TRILHO", "HORIZONTAL", "VERTICAL", "SOLTO", "LIVRE"]):
        return (
            "💡 **Orientação da Engenharia Clínica EMED (Estativa & Eletrofreios):** "
            "Se o freio não estiver segurando (movimento livre) ou travar no trilho, verifique se ao apertar o botão da manopla escuta-se o estalo da bobina solenoide. "
            "Se **todos** os freios da sala (mesa e estativa) estiverem inoperantes, a falha provável é na fonte de alimentação dos freios. "
            "Se for **apenas um movimento específico**, nossa equipe levará a bobina solenoide e o botão de acionamento para substituição imediata."
        )
    elif any(w in txt for w in ["DR", "CR", "FLAT PANEL", "DETECTOR", "CHASSI", "CASSETE", "DIGITALIZADOR"]):
        return (
            "💡 **Orientação Técnica EMED (Sistemas Digitais DR / CR):** "
            "Para DR: verifique se a interface box está energizada e se o Wi-Fi do painel conectou na workstation. "
            "Para CR: verifique se o chassi foi inserido com a trava no sentido correto e se o leitor não está em ciclo de apagamento."
        )
    elif "BRIVO" in txt or "TOMO" in txt or "CT385" in txt or "BRIGHTSPEED" in txt or "SOMATOM" in txt or "OPTIMA" in txt:
        if any(w in txt for w in ["TRAV", "REINIC", "COMUNIC", "GANTRY", "ERRO", "CHILLER"]):
            return (
                "💡 **Dica da Engenharia Clínica EMED (POP-03 / IT-05):** "
                "Para tomógrafos, verifique se o disjuntor de emergência do console ou a chave geral do Gantry "
                "não foram acionados acidentalmente. Um ciclo de reinicialização de 60 segundos "
                "no PDU costuma restaurar o barramento de comunicação."
            )
    elif "RAIO" in txt or "LOTUS" in txt or "HF500" in txt or "RX" in txt or "MULTIX" in txt:
        if any(w in txt for w in ["DISPAR", "COLIM", "EMISS", "GERADOR", "KV", "MAS", "FEIXE", "FOTOCEL"]):
            return (
                "💡 **Dica da Engenharia Clínica EMED (POP-Lotus HF500 / IT-RX):** "
                "Para sistemas de Raio-X, confirme se o botão de disparo de 2 estágios está com o cabo íntegro "
                "e se o intertravamento das portas da sala de exame está fechado corretamente antes do chamado."
            )
    elif "ARCO" in txt or "C-ARM" in txt or "PULSERA" in txt or "ZIEHM" in txt:
        return (
            "💡 **Orientação Técnica EMED (Arco Cirúrgico):** "
            "Verifique se o cabo umbilical entre o carrinho dos monitores e o estativo em C está bem fixado "
            "e se os freios manuais das articulações orbitais estão soltos manualmente."
        )
    elif "MAMO" in txt or "SELENIA" in txt or "SENOGRAPHE" in txt:
        return (
            "💡 **Orientação Técnica EMED (Mamografia):** "
            "Se o compressor não responder, verifique se a liberação de emergência manual foi girada "
            "e teste o pedal alternativo."
        )
    elif "DENSITO" in txt or "LUNAR" in txt or "PRODIGY" in txt:
        return (
            "💡 **Orientação Técnica EMED (Densitometria Óssea):** "
            "Verifique se o braço C desliza livremente sobre a mesa de exames e se a comunicação "
            "com o computador do software está ativa."
        )
            
    return ""


def _organizar_rotas_inteligentes(df_ativos: pd.DataFrame, equipa_tecnica: dict):
    """
    Agrupa chamados ativos geograficamente por Hospital/Unidade e Polo Regional.
    Calcula economia de deslocamento, ferramentas consolidadas e técnico sugerido por proximidade.
    """
    if df_ativos.empty:
        return []

    df_temp = df_ativos.copy()
    df_temp["cli_norm"] = df_temp["cliente"].astype(str).str.strip().str.upper()
    df_temp["cid_norm"] = df_temp["cidade"].astype(str).str.strip().str.upper()

    grupos = []
    for (cli, cid), g in df_temp.groupby(["cli_norm", "cid_norm"]):
        qtd_chamados = len(g)
        primeira_linha = g.iloc[0]
        end = limpar_texto(primeira_linha.get("endereco"), "")
        uf = limpar_texto(primeira_linha.get("estado"), "CE")
        
        # Identifica se há máquina parada
        tem_parada = any("PARADO" in str(r.get("condicao_inicial", "")).upper() for _, r in g.iterrows())
        
        # Sugere técnico próximo por proximidade de sede/cidade
        tec_sugerido = "A DEFINIR"
        for t_nome, t_info in equipa_tecnica.items():
            s_cidade = str(t_info.get("sede", "")).upper()
            p_cidade = str(t_info.get("partida", "")).upper()
            if s_cidade in cid or p_cidade in cid or cid in s_cidade or cid in p_cidade:
                tec_sugerido = t_nome
                break
        
        if tec_sugerido == "A DEFINIR" and equipa_tecnica:
            tecs_atuais = [str(r.get("tecnico_responsavel", "")).strip().upper() for _, r in g.iterrows() if str(r.get("tecnico_responsavel", "")).strip().upper() not in ["A DEFINIR", "N/D", ""]]
            tec_sugerido = tecs_atuais[0] if tecs_atuais else list(equipa_tecnica.keys())[0]

        # Consolidar kits necessários para toda a rota sem duplicar
        kits_consolidados = []
        for _, r in g.iterrows():
            inst = str(r.get("instrumento_necessario", "")).strip()
            if inst and inst != "N/D" and inst not in kits_consolidados:
                kits_consolidados.append(inst)
            else:
                mod_it = _detectar_modalidade(r.get("equipamento", ""), r.get("defeito_relatado", ""))
                kit_auto = obter_kit_por_servico(r.get("tipo_servico", "CORRETIVA"), f"{mod_it} {r.get('equipamento', '')} {r.get('defeito_relatado', '')}")
                nome_k = kit_auto.get("nome", "MALETA DE CALIBRAÇÃO PADRÃO")
                if nome_k not in kits_consolidados:
                    kits_consolidados.append(nome_k)

        grupos.append({
            "cliente": cli,
            "cidade": cid,
            "estado": uf,
            "endereco": end,
            "qtd": qtd_chamados,
            "tem_parada": tem_parada,
            "indices": g.index.tolist(),
            "df_sub": g,
            "tec_sugerido": tec_sugerido,
            "kits": kits_consolidados,
            "economia_viagens": max(0, qtd_chamados - 1)
        })

    # Ordena: Rotas com mais chamados primeiro (maior economia de deslocamento), depois as com máquinas paradas
    grupos.sort(key=lambda x: (x["qtd"], 1 if x["tem_parada"] else 0), reverse=True)
    return grupos



def _obter_perguntas_triagem_dinamica(modalidade: str, defeito: str, equip: str):
    """Analisa o relato do cliente e gera perguntas cirúrgicas e específicas para o defeito relatado."""
    txt = (defeito or "").upper()
    eq_up = (equip or "").upper()

    # 1. Mamografia - Compressão e Pedais
    if re.search(r'\b(COMPRESSOR|COMPRESSAO|COMPRESSÃO|PEDAL|PRATO|DESCOMPRESSAO|DESCOMPRESSÃO|DAN|ESPESSURA)\b', txt) and ("MAMO" in modalidade or "MAMO" in eq_up):
        return {
            "categoria": "SISTEMA DE COMPRESSÃO & PEDAIS (MAMOGRAFIA)",
            "icone": "🗜️",
            "focada": True,
            "desc": "Perguntas adaptadas especificamente para acionamento por pedais, descompressão rápida e célula de carga:",
            "p1": {
                "nome": "Acionamento dos Pedais",
                "pergunta": "🦶 1. Resposta aos Pedais de Elevação/Descida:",
                "opcoes": [
                    "⚠️ Falha apenas no pedal esquerdo (o pedal direito e botões manuais do gantry operam)",
                    "⚠️ Falha apenas no pedal direito (o pedal esquerdo e botões manuais do gantry operam)",
                    "🚨 Ambos os pedais falham (apenas botões manuais do gantry respondem)",
                    "❌ Nem pedais nem botões manuais respondem (sistema de compressão inerte)",
                    "🟢 Movimento normal por pedais e botoeira",
                ],
                "help": "Identifica se o problema é microswitch/cabo do pedal ou circuito de potência da compressão."
            },
            "p2": {
                "nome": "Descompressão de Emergência",
                "pergunta": "🛑 2. Descompressão Rápida de Emergência:",
                "opcoes": [
                    "🟢 Botão vermelho de liberação destrava o acrílico imediatamente",
                    "⚠️ Descompressão mecânica pesada, emperrando ou lenta",
                    "🚨 Botão de emergência travado (risco de prender paciente)",
                    "⚪ Não testado / Não se aplica",
                ],
                "help": "Verifica item crítico de segurança biológica da paciente."
            },
            "p3": {
                "nome": "Medição de Força e Espessura",
                "pergunta": "🔢 3. Display Digital de Força (daN) e Espessura (mm):",
                "opcoes": [
                    "🟢 Display marca valores coerentes com a compressão aplicada",
                    "⚠️ Valores oscilam sem parar ou congelam durante o avanço",
                    "❌ Display zerado ou mensagem de erro de célula de carga / fotocélula",
                    "⚪ Não se aplica",
                ],
                "help": "Avalia o sensor de calibração radiométrica da mama."
            }
        }

    # 2. Qualidade de Imagem, Artefatos e Detectores
    if re.search(r'\b(ARTEFATO|ARTEFATOS|MANCHA|MANCHAS|RISCO|RISCOS|LISTRA|LISTRAS|LINHA|LINHAS|ANEL|ANEIS|ANÉIS|FANTOMA|PHANTOM|AIR CAL|CALIBRACAO|CALIBRAÇÃO|PIXEL|PIXELS)\b', txt):
        return {
            "categoria": "QUALIDADE DE IMAGEM & DETECTORES",
            "icone": "🔬",
            "focada": True,
            "desc": "Perguntas focadas em artefatos visuais, aquecimento diário e calibração de detectores:",
            "p1": {
                "nome": "Padrão Visual do Defeito",
                "pergunta": "🔬 1. Formato e Padrão Visual do Defeito:",
                "opcoes": [
                    "⚠️ Artefato em anel concêntrico circular (típico de canal de detector DAS / TC)",
                    "⚠️ Linhas retas pretas ou brancas verticais (típico de pixel defeituoso / Flat Panel)",
                    "⚠️ Mancha difusa, sombreamento ou perda homogênea de contraste",
                    "⚪ Outro padrão não listado / Não se aplica",
                ],
                "help": "Ajuda a distinguir falha de DAS/detector de desgaste de tubo."
            },
            "p2": {
                "nome": "Calibração Diária (Warm-up / Air Cal)",
                "pergunta": "🌀 2. Rotina de Calibração Diária (Warm-up / Air Calibration):",
                "opcoes": [
                    "🟢 Aquecimento de tubo e calibração de ar executados com sucesso hoje",
                    "⚠️ Erro interrompeu a calibração de ar no meio do processo",
                    "❌ Não foi possível realizar o Warm-up (tubo frio ou bloqueado)",
                    "⚪ Procedimento não realizado hoje",
                ],
                "help": "Verifica se a tabela de ganho e offset foi atualizada."
            },
            "p3": {
                "nome": "Comportamento com Phantom",
                "pergunta": "🎯 3. Comportamento no Phantom de Calibração Oficial:",
                "opcoes": [
                    "🚨 O defeito se reproduz claramente nas imagens do Phantom oficial",
                    "🟢 Artefato só aparece em pacientes específicos ou técnicas de alta dose",
                    "⚪ Phantom indisponível no momento para teste",
                ],
                "help": "Comprova a necessidade de calibração física pelo engenheiro."
            }
        }

    # 3. Disparo, Alta Tensão, Tubo e Gerador
    if re.search(r'\b(DISPARO|DISPARAR|DISPARANDO|NAO DISPARA|NÃO DISPARA|KV|KVP|MA|MAS|FILAMENTO|SOBRECORRENTE|OVERCURRENT|GERADOR|ALTA TENSAO|ALTA TENSÃO|TUBO|FAISCA|FAÍSCA|402|INTERLOCK)\b', txt):
        return {
            "categoria": "DISPARO, GERADOR & ALTA TENSÃO",
            "icone": "💥",
            "focada": True,
            "desc": "Perguntas cirúrgicas sobre aceleração de rotor, disparo de alta tensão e intertravamentos:",
            "p1": {
                "nome": "1º Estágio (Prep / Rotor)",
                "pergunta": "⚡ 1. Resposta ao 1º Estágio (Prep / Ready):",
                "opcoes": [
                    "🟢 Rotor acelera suavemente e luz de Pronto (Ready) acende no console",
                    "⚠️ Rotor acelera mas a luz de Ready não acende (bloqueio de interlock)",
                    "🔇 Não escuta o rotor acelerar ao pressionar o 1º estágio",
                    "⚪ Nenhuma das opções / Não se aplica",
                ],
                "help": "Distingue falha de partida de anodo de erro de disparo."
            },
            "p2": {
                "nome": "2º Estágio (Disparo / Emissão)",
                "pergunta": "💥 2. Resposta ao 2º Estágio (Disparo de Raios-X):",
                "opcoes": [
                    "⚠️ Acusa código de erro / alarme sonoro exatamente no momento do disparo",
                    "🔴 Queda imediata de disjuntor / Faíscamento perceptível no gerador ou cabos HV",
                    "🔇 Sem nenhum disparo, aviso de interlock persistente no painel",
                    "🟢 Disparo ocorre mas imagem sai totalmente branca/escura",
                ],
                "help": "Determina sobrecorrente, falha no inversor JEDI ou disparo em vazio."
            },
            "p3": {
                "nome": "Intertravamento de Segurança",
                "pergunta": "🛡️ 3. Sensores de Porta & Intertravamento de Segurança:",
                "opcoes": [
                    "🟢 Sensor da porta da sala fecha e comuta o circuito normalmente",
                    "⚠️ Alerta de 'Porta Aberta' ou 'Interlock Aberto' não apaga no console",
                    "⚪ Não se aplica / Não verificado",
                ],
                "help": "Impede deslocamento desnecessário por simples chave de porta solta."
            }
        }

    # 4. Movimentação, Mesa, Estativa e Freios
    if re.search(r'\b(FREIO|FREIOS|TRAVA|TRAVAS|TRAVOU|TRAVADO|TRAVADA|EMPERRADO|EMPERRADA|ESTATIVA|MESA|NAO SOBE|NÃO SOBE|NAO DESCE|NÃO DESCE|HORIZONTAL|VERTICAL|TILT|SOLTO|SOLTA|CURSO|TRILHO)\b', txt):
        return {
            "categoria": "MECÂNICA, MOVIMENTAÇÃO & FREIOS",
            "icone": "⚙️",
            "focada": True,
            "desc": "Perguntas adaptadas para acionamento de motores, eletrofreios e curso dos trilhos:",
            "p1": {
                "nome": "Comando de Movimento",
                "pergunta": "⚙️ 1. Resposta Elétrica ao Comando de Movimento (Botoeira / Pedal):",
                "opcoes": [
                    "🟢 Escuta o clique do relé/contator e o motor tenta girar",
                    "🔇 Silêncio total ao apertar o botão (sem resposta elétrica)",
                    "⚠️ Escuta zumbido contínuo ou o motor patina sem movimentar o conjunto",
                    "⚪ Nenhuma das opções / Não se aplica",
                ],
                "help": "Avalia botão, fonte de alimentação ou motor elétrico."
            },
            "p2": {
                "nome": "Eletrofreios e Travas",
                "pergunta": "🧲 2. Atuação dos Eletrofreios ou Travas Mecânicas:",
                "opcoes": [
                    "🟢 Freios liberam e seguram com firmeza",
                    "⚠️ Freio solto / livre (não segura o movimento, conjunto desliza sozinho)",
                    "🚨 Freio permanentemente bloqueado (não destrava nem com botão manual)",
                    "⚪ Nenhuma das opções / Outro comportamento",
                ],
                "help": "Diferencia bobina de freio queimada de desgaste de sapata."
            },
            "p3": {
                "nome": "Curso e Fim de Curso",
                "pergunta": "📏 3. Posição de Travamento no Curso / Trilhos:",
                "opcoes": [
                    "🟢 Curso livre em toda a extensão",
                    "⚠️ Travou exatamente no batente / fim de curso (chave fim-de-curso acionada)",
                    "🚨 Travamento no meio do percurso mecânico (possível obstáculo mecânico ou rolamento)",
                    "⚪ Não se aplica",
                ],
                "help": "Determina se a falha é mecânica ou microswitch fim-de-curso."
            }
        }

    # 5. Software, Console e Comunicação
    if re.search(r'\b(CONSOLE|SOFTWARE|MONITOR|TELA PRETA|BOOT|WINDOWS|LINUX|COMMUNICATION|REDE|WORKSTATION|HOST|DICOM)\b', txt) or ("TRAV" in txt and any(k in txt for k in ["CONSOLE", "TELA", "SOFTWARE"])):
        return {
            "categoria": "CONSOLE, SOFTWARE & COMUNICAÇÃO",
            "icone": "🖥️",
            "focada": True,
            "desc": "Perguntas específicas sobre inicialização do SO, mensagens de erro e barramento de rede:",
            "p1": {
                "nome": "Inicialização do Sistema",
                "pergunta": "💻 1. Inicialização do Sistema Operacional & Software:",
                "opcoes": [
                    "🟢 Computador liga e carrega o Windows/Linux normalmente",
                    "🔄 Computador liga, mas o software de aquisição médica não abre ou congela no boot",
                    "❌ Computador não dá vídeo / Tela preta / Bips contínuos na placa-mãe",
                    "⚪ Nenhuma das opções / Outro comportamento",
                ],
                "help": "Distingue problema de PC/hardware de falha na aplicação médica."
            },
            "p2": {
                "nome": "Código de Erro no Painel",
                "pergunta": "💬 2. Mensagem Exata de Erro no Painel / Console:",
                "opcoes": [
                    "⚠️ Erro de comunicação ('Communication Error' / 'Host unreachable' / 'Link Down')",
                    "⚠️ Erro de banco de dados DICOM ou disco cheio (Disk Full / Archive Error)",
                    "❌ Erro fatal de hardware de aquisição (Board Failure / Gantry Error)",
                    "⚪ Nenhuma mensagem de erro visível, apenas travamento silencioso",
                ],
                "help": "Direciona a IT correta para o técnico levar cabos ou placas."
            },
            "p3": {
                "nome": "Links de Fibra e Rede",
                "pergunta": "🔌 3. Cabos de Comunicação & Rede / Fibra Óptica:",
                "opcoes": [
                    "🟢 LEDs de rede/fibra óptica piscando normalmente entre console e gantry/gerador",
                    "🔴 LED de link apagado no cabo de fibra / placa de rede sem sinal",
                    "⚪ Não verificado / Não se aplica",
                ],
                "help": "Verifica integridade do barramento de dados."
            }
        }

    # 6. Temperatura, Chiller e Óleo
    if re.search(r'\b(AQUECENDO|QUENTE|TEMPERATURA|CHILLER|OLEO|ÓLEO|VAZAMENTO|FUMACA|FUMAÇA|CHEIRO|COOLER|OVERHEAT)\b', txt):
        return {
            "categoria": "ARREFECIMENTO, TEMPERATURA & FLUIDOS",
            "icone": "🌡️",
            "focada": True,
            "desc": "Perguntas adaptadas para monitoramento térmico, chiller e estanqueidade de óleo:",
            "p1": {
                "nome": "Alerta Térmico",
                "pergunta": "🌡️ 1. Alerta de Temperatura & Disparo do Sensor Térmico:",
                "opcoes": [
                    "⚠️ Alerta de temperatura alta surge após poucos exames consecutivos",
                    "🔴 Mensagem de superaquecimento (Overheat) surge logo ao ligar a frio",
                    "🟢 Alerta térmico não apareceu (sistema acusa erro diferente)",
                    "⚪ Não se aplica",
                ],
                "help": "Distingue superaquecimento real de termostato defeituoso."
            },
            "p2": {
                "nome": "Óleo e Vazamento",
                "pergunta": "💧 2. Nível de Fluido, Óleo Dielétrico & Vazamentos:",
                "opcoes": [
                    "🟢 Sem nenhum vestígio de vazamento no chão ou na carcaça",
                    "⚠️ Mancha de óleo dielétrico perceptível ou cheiro característico de queimado",
                    "🔴 Vazamento ativo visível com gotejamento pelo fole de dilatação do tubo",
                    "⚪ Não se aplica",
                ],
                "help": "Evita dano catastrófico ao monobloco por perda de isolamento."
            },
            "p3": {
                "nome": "Chiller e Ventilação",
                "pergunta": "❄️ 3. Chiller Externo & Circulação de Arrefecimento:",
                "opcoes": [
                    "🟢 Bomba do chiller e ventoinhas funcionando com fluxo normal",
                    "⚠️ Bomba do chiller não liga ou indicador de fluxo (flow switch) em alarme",
                    "⚪ Equipamento com arrefecimento passivo / sem chiller dedicado",
                ],
                "help": "Avalia o circuito externo de refrigeração líquida."
            }
        }

    # 7. Preventiva Programada
    if re.search(r'\b(PREVENTIVA|REVISAO|REVISÃO|ROTINA|ANUAL|PERIODICA|PERIÓDICA)\b', txt):
        return {
            "categoria": "REVISÃO PREVENTIVA PROGRAMADA",
            "icone": "📋",
            "focada": True,
            "desc": "Perguntas de alinhamento operacional para planejamento da manutenção preventiva:",
            "p1": {
                "nome": "Condição Operacional",
                "pergunta": "🏥 1. Condição Clínica Operacional Atual do Equipamento:",
                "opcoes": [
                    "🟢 100% Operacional (Realizando exames normalmente, sem falhas)",
                    "🟡 Operando com pequenas restrições ou ruídos que podem aguardar a revisão",
                    "🔴 Equipamento parado / inoperante precisando de manutenção corretiva urgente",
                ],
                "help": "Define se o técnico deve ir com kit de preventiva ou de emergência."
            },
            "p2": {
                "nome": "Disponibilidade da Sala",
                "pergunta": "⏱️ 2. Disponibilidade da Sala de Exames para a Manutenção:",
                "opcoes": [
                    "🟢 Sala estará totalmente liberada no horário agendado (sem pacientes)",
                    "🟡 Sala precisará ser compartilhada com plantão de urgência se houver",
                    "⚪ A definir com a coordenação médica do hospital",
                ],
                "help": "Garante aproveitamento máximo das horas técnicas."
            },
            "p3": {
                "nome": "Itens Secundários a Revisar",
                "pergunta": "📐 3. Itens Secundários a Revisar nesta Preventiva:",
                "opcoes": [
                    "🟢 Preventiva de rotina completa conforme POP padrão",
                    "⚠️ Incluir ajuste mecânico específico ou reaperto estrutural",
                    "⚠️ Incluir calibração radiométrica com Phantom e laudo de conformidade",
                ],
                "help": "Direciona ferramentas e Phantoms necessários para a rota."
            }
        }

    # Fallback Padrão por Modalidade
    mod_up = modalidade.upper()
    if "TOMOGRAF" in mod_up:
        cat_padrao = "TOMÓGRAFO (CT)"
        ico_padrao = "🌀"
    elif "MAMO" in mod_up:
        cat_padrao = "MAMÓGRAFO"
        ico_padrao = "🗜️"
    elif "ARCO" in mod_up:
        cat_padrao = "ARCO CIRÚRGICO (C-ARM)"
        ico_padrao = "🦾"
    elif "DENSITO" in mod_up:
        cat_padrao = "DENSITOMETRIA ÓSSEA"
        ico_padrao = "🦴"
    elif "DIGITAL" in mod_up or "DR" in mod_up or "CR" in mod_up:
        cat_padrao = "SISTEMAS DIGITAIS (DR / CR)"
        ico_padrao = "📸"
    else:
        cat_padrao = "SISTEMA DE RAIO-X"
        ico_padrao = "🩻"

    return {
        "categoria": f"CHECKLIST TÉCNICO - {cat_padrao}",
        "icone": ico_padrao,
        "focada": False,
        "desc": f"Checklist em 5 segundos focado nos componentes críticos de {cat_padrao}:",
        "p1": {
            "nome": "Alimentação Elétrica",
            "pergunta": "⚡ 1. Alimentação Elétrica (Quadro de Força / PDU):",
            "opcoes": [
                "🟢 Não foi observada oscilação (Fornecimento elétrico normal)",
                "🟡 Houve oscilações na rede elétrica, mas o quadro já estabilizou",
                "🔴 Sim, houve desarme de disjuntor no quadro de força ou PDU",
                "⚪ Nenhuma das opções / Não se aplica",
            ],
            "help": "Houve oscilação na rede elétrica? Se sim, algum disjuntor desarmou?"
        },
        "p2": {
            "nome": "Mecânica e Movimentação",
            "pergunta": f"{ico_padrao} 2. Funcionamento Mecânico & Estrutural:",
            "opcoes": [
                "🟢 Movimentação mecânica normal",
                "⚠️ Travamento ou folga em movimento específico",
                "🚨 Equipamento totalmente imobilizado",
                "⚪ Nenhuma das opções / Outro comportamento",
            ],
            "help": "Avalia integridade do trilho, colunas e gantry."
        },
        "p3": {
            "nome": "Painel de Controle e Comandos",
            "pergunta": "🖥️ 3. Painel de Controle & Comandos:",
            "opcoes": [
                "🟢 Comandos e botões respondendo normalmente",
                "🔄 Reiniciamos o equipamento e o erro persistiu",
                "❌ Painel inoperante ou travado na inicialização",
                "⚪ Nenhuma das opções / Não se aplica",
            ],
            "help": "Determina se a falha é de software ou botoeira física."
        }
    }


def render_emedonline(ctx: AppContext):
    """Módulo EmedOnline: Triagem Técnica Humanizada, Pré-Atendimento e Roteamento Inteligente."""
    df = ctx.df
    equipa_tecnica = ctx.equipa_tecnica

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #0b132b 0%, #1c2541 60%, #102a43 100%); 
                    border-radius: 12px; padding: 18px 24px; border: 1.5px solid #3a506b; 
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin-bottom: 20px;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h2 style="color: #64dfdf; margin: 0; font-size: 24px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
                        🤖 EMEDONLINE <span style="font-size: 14px; background: #059669; color: #fff; padding: 2px 8px; border-radius: 6px;">IA & Atendimento Ágil</span>
                    </h2>
                    <p style="color: #cbd5e1; margin: 6px 0 0 0; font-size: 13.5px;">
                        Triagem direta para clínicas e hospitais. Sem robôs amarrados: pré-preenche a OS, identifica falhas e despacha equipes por rota.
                    </p>
                </div>
                <div style="background: rgba(255,255,255,0.08); padding: 8px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); text-align: right;">
                    <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">CENTRAL EMED 24H</div>
                    <div style="font-size: 14px; font-weight: 800; color: #64dfdf;">📞 (85) 3254-2929</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    query_params = st.query_params
    qr_eq_param = query_params.get("equipamento_qr", query_params.get("eq", ""))
    qr_cli_param = query_params.get("cliente_qr", query_params.get("cli", ""))
    qr_cnpj_param = query_params.get("cnpj", "")

    aba_portal, aba_despacho, aba_etiquetas, aba_instrucoes = st.tabs([
        "🏥 1. Portal do Cliente (Abrir Chamado)",
        "🗺️ 2. Central de Despacho & Rotas",
        "🏷️ 3. Gerador de Etiquetas QR Code",
        "ℹ️ 4. Como Funciona (Guia Rápido)",
    ])

    # =========================================================================
    # ABA 1: PORTAL DO CLIENTE (TRIAGEM ÁGIL E HUMANIZADA)
    # =========================================================================
    with aba_portal:
        if qr_eq_param and (qr_cli_param or qr_cnpj_param):
            st.markdown(
                f"""
                <div style="background: linear-gradient(90deg, #064e3b 0%, #022c22 100%); border: 1.5px solid #10b981; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px;">
                    <div style="font-weight: 800; color: #6ee7b7; font-size: 14px;">
                        🏷️ EQUIPAMENTO IDENTIFICADO POR QR CODE
                    </div>
                    <div style="color: #f1f5f9; font-size: 13px; margin-top: 4px;">
                        <b>Cliente:</b> {qr_cli_param} {f'({qr_cnpj_param})' if qr_cnpj_param else ''}<br/>
                        <b>Equipamento:</b> {qr_eq_param}
                    </div>
                    <div style="color: #a7f3d0; font-size: 12px; margin-top: 4px;">
                        ⚡ Cadastro identificado automaticamente. Pule direto para o relato da falha e foto abaixo!
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### 📋 Solicitação de Atendimento Técnico")
        st.caption("Identifique a sua instituição e relate o problema. Os dados alimentarão diretamente a Ordem de Serviço.")

        col_id1, col_id2 = st.columns([2.5, 1.5])
        with col_id1:
            valor_padrao_busca = qr_cnpj_param or qr_cli_param or ""
            termo_cli = st.text_input(
                "1. Digite o CNPJ ou Nome da Clínica / Hospital *",
                value=valor_padrao_busca,
                placeholder="Ex: 03.611.974/0001-08 ou Hospital São Mateus",
                help="Você pode digitar apenas os números do CNPJ ou o nome da instituição."
            )
        
        cliente_selecionado = None
        linhas_cliente = pd.DataFrame()

        if termo_cli:
            linhas_cliente = _buscar_cliente_por_cnpj_ou_nome(df, termo_cli)
            if linhas_cliente.empty:
                st.warning("⚠️ Instituição não localizada no cadastro imediato. Você pode prosseguir digitando o nome completo abaixo:")
                cliente_manual = st.text_input("Nome da Instituição:", value=termo_cli.strip().upper())
                cliente_selecionado = cliente_manual
            else:
                clientes_unicos = linhas_cliente["cliente"].dropna().unique().tolist()
                if len(clientes_unicos) == 1:
                    cliente_selecionado = clientes_unicos[0]
                    st.success(f"✅ **Instituição Identificada:** {cliente_selecionado}")
                else:
                    cliente_selecionado = st.selectbox(
                        "Selecione a Unidade Encontrada:",
                        clientes_unicos,
                    )
        else:
            # Lista de apoio
            clientes_todos = sorted([c for c in df["cliente"].dropna().unique() if str(c).strip() and "NENHUM" not in str(c).upper()])
            cliente_selecionado = st.selectbox(
                "Ou escolha na lista de clientes cadastrados:",
                [""] + clientes_todos,
            )

        if cliente_selecionado:
            dados_cli = df[df["cliente"] == cliente_selecionado]
            primeira_linha = dados_cli.iloc[0] if not dados_cli.empty else {}
            
            cnpj_cli = limpar_texto(primeira_linha.get("cnpj"), "Não cadastrado")
            end_cli = limpar_texto(primeira_linha.get("endereco"), "Fortaleza - CE")
            cid_cli = limpar_texto(primeira_linha.get("cidade"), "FORTALEZA")
            uf_cli = limpar_texto(primeira_linha.get("estado"), "CE")
            resp_cli = limpar_texto(primeira_linha.get("responsavel_hospital"), "")
            tel_cli = limpar_texto(primeira_linha.get("contato_responsavel"), limpar_texto(primeira_linha.get("whatsapp"), ""))

            st.markdown(
                f"""
                <div style="background: #1e293b; border-left: 4px solid #38bdf8; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin: 10px 0;">
                    <b>📍 Endereço Cadastrado:</b> {end_cli} — {cid_cli}/{uf_cli} | <b>CNPJ:</b> {cnpj_cli}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("---")
            st.markdown("#### 2. Qual o equipamento que precisa de intervenção?")

            eqs_cadastrados = [
                e for e in dados_cli["equipamento"].dropna().unique().tolist()
                if str(e).strip() and not str(e).lower().startswith(("nenhum", "aguardando"))
            ]

            if not eqs_cadastrados:
                eqs_cadastrados = ["OUTRO / EQUIPAMENTO AVULSO"]

            col_eq1, col_eq2 = st.columns([2.5, 1.5])
            with col_eq1:
                opcoes_eq_totais = eqs_cadastrados + ["➕ Outro Equipamento"]
                idx_eq_padrao = 0
                if qr_eq_param:
                    for i_cand, cand in enumerate(opcoes_eq_totais):
                        if qr_eq_param.upper() in cand.upper():
                            idx_eq_padrao = i_cand
                            break
                equip_escolhido = st.selectbox(
                    "Selecione o equipamento alvo *",
                    opcoes_eq_totais,
                    index=idx_eq_padrao,
                )
                if equip_escolhido == "➕ Outro Equipamento":
                    equip_escolhido = st.text_input("Especifique o Fabricante, Modelo e Sala do Equipamento:")
            
            with col_eq2:
                estado_operacional = st.radio(
                    "Estado atual do equipamento: *",
                    [
                        "🔴 Totalmente Parado / Fora de Uso (Urgente)",
                        "🟡 Operando com Limitações / Mensagem de Erro",
                        "🟢 Funcionando (Preventiva / Calibração)",
                    ],
                    index=0,
                )

            st.markdown("---")
            st.markdown("#### 3. O que está acontecendo com o equipamento?")

            # Placeholder dinâmico e contextualizado pela modalidade do equipamento selecionado
            mod_sugerida = _detectar_modalidade(equip_escolhido, "")
            placeholders_por_mod = {
                "RAIO-X": "Ex: A estativa não para de descer / freio solto, movimento travando no trilho ou o equipamento não emite feixe de raios-x...",
                "TOMOGRAFIA": "Ex: Tomógrafo não emite feixe, erro de intertravamento no gantry ou PDU desarmado...",
                "MAMOGRAFIA": "Ex: Prato de compressão travado / não sobe, falha no pedal ou erro no biombo...",
                "ARCO CIRÚRGICO": "Ex: Movimento orbital do braço em C travando ou monitores sem sinal de fluoroscopia...",
                "DENSITOMETRIA": "Ex: Braço C não calibra na inicialização ou shutter/feixe colimado com falha...",
                "SISTEMA DIGITAL (DR / CR)": "Ex: Detector Flat Panel desconectado da workstation ou leitora CR com chassi preso...",
            }
            ph_texto = placeholders_por_mod.get(mod_sugerida, "Ex: Descreva o problema observado no equipamento...")

            defeito_digitado = st.text_area(
                "Descreva com suas palavras o defeito apresentado ou código de erro na tela: *",
                placeholder=ph_texto,
                height=100,
            )

            # Dica Técnica Inteligente (baseada nas ITs e POPs da EMED)
            if defeito_digitado and equip_escolhido:
                dica_it = _obter_dica_rapida_it(equip_escolhido, defeito_digitado)
                if dica_it:
                    st.info(dica_it)

            st.markdown("---")
            modalidade_auto = _detectar_modalidade(equip_escolhido, defeito_digitado)

            modalidades_opcoes = [
                "RAIO-X",
                "TOMOGRAFIA",
                "MAMOGRAFIA",
                "ARCO CIRÚRGICO",
                "DENSITOMETRIA",
                "SISTEMA DIGITAL (DR / CR)",
                "OUTRO",
            ]
            idx_mod_padrao = modalidades_opcoes.index(modalidade_auto) if modalidade_auto in modalidades_opcoes else 0

            col_mod_tit, col_mod_sel = st.columns([2.6, 1.4])
            with col_mod_tit:
                st.markdown(f"#### ⚡ 3.1 Triagem Técnica Específica — {modalidade_auto}")
                st.caption("Checklist em 5 segundos focado nos componentes críticos desta modalidade:")
            with col_mod_sel:
                modalidade = st.selectbox(
                    "Modalidade Detectada:",
                    modalidades_opcoes,
                    index=idx_mod_padrao,
                    help="Identificada automaticamente pelo modelo do equipamento. Você pode alterar manualmente caso deseje outro checklist."
                )

            triagem_info = _obter_perguntas_triagem_dinamica(modalidade, defeito_digitado, equip_escolhido)
            p1_dados = triagem_info["p1"]
            p2_dados = triagem_info["p2"]
            p3_dados = triagem_info["p3"]
            cat_nome = triagem_info["categoria"]
            cat_ico = triagem_info["icone"]
            cat_desc = triagem_info["desc"]
            is_focada = triagem_info.get("focada", False)

            if is_focada:
                st.markdown(f"""
                <div style="background: rgba(14, 165, 233, 0.15); border-left: 5px solid #0ea5e9; padding: 12px 16px; border-radius: 8px; margin-bottom: 14px;">
                    <div style="color: #38bdf8; font-weight: 800; font-size: 14px;">🎯 TRIAGEM CIRÚRGICA DETECTADA: {cat_ico} {cat_nome}</div>
                    <div style="color: #cbd5e1; font-size: 13px; margin-top: 3px;">{cat_desc}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"##### {cat_ico} {cat_nome}")
                st.caption(cat_desc)

            c_chk1, c_chk2 = st.columns(2)
            with c_chk1:
                nome_p1 = p1_dados["nome"]
                chk_1 = st.radio(
                    p1_dados["pergunta"],
                    p1_dados["opcoes"],
                    index=0,
                    help=p1_dados.get("help", "")
                )
                nome_p2 = p2_dados["nome"]
                chk_2 = st.radio(
                    p2_dados["pergunta"],
                    p2_dados["opcoes"],
                    index=0,
                    help=p2_dados.get("help", "")
                )
            with c_chk2:
                nome_p3 = p3_dados["nome"]
                chk_3 = st.radio(
                    p3_dados["pergunta"],
                    p3_dados["opcoes"],
                    index=0,
                    help=p3_dados.get("help", "")
                )
            st.markdown("---")
            st.markdown("#### 📸 3.2 Foto do Painel & Dados do Solicitante")
            col_foto1, col_foto2 = st.columns(2)
            with col_foto1:
                arquivo_foto = st.file_uploader(
                    "📸 Anexar Foto do Painel / Código de Erro (Câmera ou Galeria)",
                    type=["jpg", "jpeg", "png"],
                    help="Tire uma foto do display onde o erro aparece. Ela será anexada automaticamente na Folha de OS oficial.",
                )
            with col_foto2:
                nome_solicitante = st.text_input(
                    "Nome de quem está solicitando o chamado:",
                    value=resp_cli,
                    placeholder="Ex: Dra. Mariana / Enf. Carlos / Biomédico",
                )
                contato_solicitante = st.text_input(
                    "Telefone / WhatsApp para contato da equipe técnica:",
                    value=tel_cli,
                    placeholder="(85) 99999-9999",
                )

            st.markdown("<br/>", unsafe_allow_html=True)
            
            # Assinatura da solicitação para trava anti-duplicação e debounce de cliques
            hash_submissao = hashlib.md5(
                f"{cliente_selecionado.strip().upper()}|{equip_escolhido.strip().upper()}|{defeito_digitado.strip().upper()}".encode("utf-8")
            ).hexdigest()

            # Se já abriu esta OS nesta sessão, exibe o cartão de sucesso com opção de abrir outro chamado
            if st.session_state.get("ultimo_emedonline_hash") == hash_submissao:
                num_os_gerada = st.session_state.get("ultimo_emedonline_os", "N/D")
                info_chamado = st.session_state.get("ultimo_emedonline_info", {})
                tec_sugerido = info_chamado.get("tec_sugerido", "EQUIPE EMED PLANTÃO")
                link_wpp = info_chamado.get("link_wpp", "")
                msg_sep = info_chamado.get("msg_sep", "")
                ok_sep = info_chamado.get("ok_sep", False)

                st.success(f"🎉 **Chamado Aberto com Sucesso! Ordem de Serviço Nº #{num_os_gerada} emitida.**")
                if ok_sep and msg_sep:
                    st.info(f"📦 {msg_sep}")

                if link_wpp:
                    st.markdown(
                        f"""
                        <div style="background: #064e3b; border: 1.5px solid #10b981; border-radius: 8px; padding: 14px; margin-top: 10px;">
                            <h4 style="color: #6ee7b7; margin:0 0 6px 0;">✅ O que acontece agora?</h4>
                            <ul style="color: #e2e8f0; font-size: 13.5px; margin: 0 0 10px 0; padding-left: 20px;">
                                <li>A OS já foi pré-preenchida com os dados do cliente, defeito e foto.</li>
                                <li>O técnico designado (<b>{tec_sugerido}</b>) foi notificado para encaixe em rota.</li>
                                <li>No local, o técnico precisará apenas lançar o serviço executado e as peças utilizadas.</li>
                            </ul>
                            <a href="{link_wpp}" target="_blank" style="display: inline-block; background: #25d366; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none;">
                                💬 Notificar Central EMED via WhatsApp
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown("<br/>", unsafe_allow_html=True)
                if st.button("➕ Abrir Outro Chamado Técnico", type="secondary"):
                    st.session_state.pop("ultimo_emedonline_hash", None)
                    st.session_state.pop("ultimo_emedonline_os", None)
                    st.session_state.pop("ultimo_emedonline_info", None)
                    st.rerun()

            else:
                # Botão de Envio de Chamado Dinâmico conforme a Criticidade
                is_urgente = "Totalmente Parado" in estado_operacional
                is_preventiva = "Preventiva" in estado_operacional

                if is_urgente:
                    btn_label = "🚀 Confirmar Abertura de Chamado Emergencial"
                    btn_help = "Prioridade Máxima: Equipamento parado, sem atendimento a pacientes."
                elif is_preventiva:
                    btn_label = "📅 Confirmar Agendamento de Preventiva (com Reparo de Pendência)"
                    btn_help = "Prioridade P3: Equipamento funcional, pendência será tratada na rota da preventiva programada."
                else:
                    btn_label = "🔧 Confirmar Abertura de Chamado Técnico Programado"
                    btn_help = "Prioridade P2: Equipamento operando com restrições."

                col_b1, col_b2 = st.columns([2.0, 2.0])
                with col_b1:
                    confirmou_envio = st.button(
                        btn_label,
                        type="primary",
                        use_container_width=True,
                        help=btn_help,
                    )

                if confirmou_envio:
                    if not defeito_digitado.strip():
                        st.error("⚠️ Por favor, informe o defeito apresentado pelo equipamento para abrir o chamado.")
                    else:
                        # TRAVA ANTI-DUPLICAÇÃO: Checa se já existe chamado ativo idêntico (evita cliques rápidos / duplicidade)
                        chamado_duplicado = df[
                            (df["cliente"].astype(str).str.strip().str.upper() == cliente_selecionado.strip().upper()) &
                            (df["equipamento"].astype(str).str.strip().str.upper() == equip_escolhido.strip().upper()) &
                            (df["status"].astype(str).str.upper().isin(["ATIVO", "EM ATENDIMENTO"])) &
                            (df["defeito_relatado"].astype(str).str.strip().str.upper() == defeito_digitado.strip().upper())
                        ]
                        if not chamado_duplicado.empty:
                            idx_existente = chamado_duplicado.index[-1]
                            num_os_existente = obter_id_os(idx_existente, chamado_duplicado.iloc[-1])
                            st.session_state["ultimo_emedonline_hash"] = hash_submissao
                            st.session_state["ultimo_emedonline_os"] = num_os_existente
                            st.warning(f"⚠️ **Chamado já existente:** Já existe uma OS ativa em andamento para este equipamento com este mesmo relato (**OS #{num_os_existente}**). Criação duplicada evitada.")
                            st.rerun()
                        else:
                            # Salva a foto se houver
                            pasta_uploads = os.path.join(ctx.base_dir, "uploads_os")
                            os.makedirs(pasta_uploads, exist_ok=True)
                            caminho_foto_final = ""
                            if arquivo_foto is not None:
                                nome_arq_foto = f"FOTO_EMEDONLINE_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{arquivo_foto.name}"
                                caminho_foto_final = os.path.join(pasta_uploads, nome_arq_foto)
                                with open(caminho_foto_final, "wb") as f:
                                    f.write(arquivo_foto.getbuffer())

                            # Define a criticidade e classificação de serviço
                            if is_urgente:
                                tag_prioridade = "P1 - EMERGÊNCIA MÉDICA"
                                cond_ini = "PARADO (INOPERANTE)"
                                tipo_servico = "CORRETIVA"
                            elif is_preventiva:
                                tag_prioridade = "P3 - PREVENTIVA PROGRAMADA"
                                cond_ini = "OPERACIONAL COM PENDÊNCIA (AGUARDA PREVENTIVA)"
                                tipo_servico = "PREVENTIVA COM REPARO"
                            else:
                                tag_prioridade = "P2 - PROGRAMADO"
                                cond_ini = "OPERANDO COM FALHA"
                                tipo_servico = "CORRETIVA"

                            # Verifica equipe próxima por cidade
                            tec_sugerido = "EQUIPE EMED PLANTÃO"
                            for t_nome, t_dados in equipa_tecnica.items():
                                cidade_tec = t_dados.get("sede", "FORTALEZA").upper()
                                if cidade_tec in cid_cli.upper():
                                    tec_sugerido = t_nome
                                    break

                            # Kit sugerido inteligente considerando modalidade e defeito
                            kit_sugerido = obter_kit_por_servico(tipo_servico, f"{modalidade} {equip_escolhido} {defeito_digitado}")
                            checklist_resumo = (
                                f"[{nome_p1}: {chk_1}] "
                                f"[{nome_p2}: {chk_2}] "
                                f"[{nome_p3}: {chk_3}]"
                            )

                            novo_chamado = {
                                "cliente": cliente_selecionado.strip().upper(),
                                "cidade": cid_cli.upper(),
                                "estado": uf_cli.upper(),
                                "equipamento": equip_escolhido.strip().upper(),
                                "endereco": end_cli.strip().upper(),
                                "tipo_servico": tipo_servico,
                                "data_agendamento": datetime.now().strftime("%Y-%m-%d"),
                                "tecnico_responsavel": tec_sugerido,
                                "tecnico_auxiliar": "NENHUM (INDIVIDUAL)",
                                "telefone_tecnico": equipa_tecnica.get(tec_sugerido, {}).get("telefone", "(85) 3254-2929"),
                                "responsavel_hospital": (nome_solicitante or resp_cli).strip().upper(),
                                "contato_responsavel": (contato_solicitante or tel_cli).strip(),
                                "confirmado": "SIM",
                                "pendencias": f"[{tag_prioridade}] {defeito_digitado.strip().upper()}",
                                "status": "ATIVO",
                                "checkin_hora": "",
                                "checkout_hora": "",
                                "tempo_atendimento": "",
                                "checklist_pop": f"{nome_p1[:10]}: {chk_1[:25]} | {nome_p2[:10]}: {chk_2[:25]} | {nome_p3[:10]}: {chk_3[:25]}",
                                "assinatura_cliente": "",
                                "assinatura_tecnico": f"{tec_sugerido} - CFT",
                                "pre_atendimento": f"[EMEDONLINE - {modalidade}] {defeito_digitado.strip()} | {checklist_resumo} | Solicitante: {nome_solicitante}",
                                "foto_evidencia": caminho_foto_final,
                                "video_evidencia": "",
                                "formulario_anexo": "",
                                "cnpj": cnpj_cli,
                                "cep": limpar_texto(primeira_linha.get("cep"), ""),
                                "email": limpar_texto(primeira_linha.get("email"), ""),
                                "whatsapp": contato_solicitante or tel_cli,
                                "endereco_fiscal": end_cli,
                                "tipo_contrato": limpar_texto(primeira_linha.get("tipo_contrato"), "CONTRATO"),
                                "instrumento_necessario": kit_sugerido.get("nome", "MALETA DE CALIBRAÇÃO PADRÃO"),
                                "etapa_preventiva": f"PREVENTIVA / CALIBRAÇÃO ({modalidade})" if is_preventiva else f"CORRETIVA EMEDONLINE ({modalidade})",
                                "orcamento_anexo": "",
                                "condicao_pagamento": "",
                                "valor_os": 0.0,
                                "defeito_relatado": defeito_digitado.strip().upper(),
                                "condicao_inicial": cond_ini,
                                "problemas_encontrados": "",
                                "causa_raiz": "",
                                "servico_executado": "",
                                "parametros_medidos": "",
                                "observacoes_gerais": f"Chamado aberto via EmedOnline ({modalidade}) em {datetime.now().strftime('%d/%m/%Y %H:%M')}.",
                                "condicao_final": "EM ATENDIMENTO",
                                "foto_depois": "",
                                "assinatura_cliente_img": "",
                                "peca_baixada_ref": "",
                            }

                            df_novo = pd.concat([df, pd.DataFrame([novo_chamado])], ignore_index=True)
                            if salvar_dados_seguro(df_novo, ctx.db_name, ctx.caminho_excel):
                                st.cache_data.clear()
                                novo_idx = df_novo.index[-1]
                                num_os_gerada = obter_id_os(novo_idx, pd.Series(novo_chamado))

                                # Acionamento Automático do Almoxarifado para separação
                                itens_kit_str = ", ".join(kit_sugerido.get("itens", []))
                                ok_sep, msg_sep = acionar_separacao_automatica_almoxarifado(
                                    ctx.db_name,
                                    tec_sugerido,
                                    cliente_selecionado,
                                    equip_escolhido,
                                    "PREVENTIVA / CALIBRAÇÃO" if is_preventiva else "CORRETIVA / TRIAGEM",
                                    f"[{kit_sugerido.get('nome')}] {itens_kit_str}",
                                    os_id=num_os_gerada
                                )
                                
                                # Mensagem objetiva para despacho e alinhamento da equipe
                                if is_preventiva:
                                    titulo_whats = f"📅 *AGENDAMENTO PREVENTIVA COM PENDÊNCIA • OS #{num_os_gerada}*"
                                    status_whats = "Equipamento Operacional (Resolver na Preventiva)"
                                else:
                                    titulo_whats = f"🚨 *CHAMADO EMEDONLINE • OS #{num_os_gerada}*"
                                    status_whats = cond_ini

                                msg_whats = (
                                    f"{titulo_whats}\n"
                                    f"Cliente: {cliente_selecionado}\n"
                                    f"Equipamento: {equip_escolhido} ({modalidade})\n"
                                    f"Prioridade: {status_whats}\n"
                                    f"Defeito / Pendência: {defeito_digitado.strip()}\n\n"
                                    f"*TRIAGEM TÉCNICA ({modalidade}):*\n"
                                    f"• {nome_p1}: {chk_1}\n"
                                    f"• {nome_p2}: {chk_2}\n"
                                    f"• {nome_p3}: {chk_3}\n\n"
                                    f"🧰 Kit Sugerido: {kit_sugerido.get('nome')}\n"
                                    f"Solicitante: {nome_solicitante} ({contato_solicitante})\n"
                                    f"Técnico Programado: {tec_sugerido}\n"
                                    f"Local: {end_cli}"
                                )
                                link_wpp = f"https://wa.me/558532542929?text={urllib.parse.quote(msg_whats)}"
                                
                                # Salva na sessão para persistência e bloqueio de novos envios
                                st.session_state["ultimo_emedonline_hash"] = hash_submissao
                                st.session_state["ultimo_emedonline_os"] = num_os_gerada
                                st.session_state["ultimo_emedonline_info"] = {
                                    "tec_sugerido": tec_sugerido,
                                    "link_wpp": link_wpp,
                                    "ok_sep": ok_sep,
                                    "msg_sep": msg_sep,
                                }
                                st.balloons()
                                st.rerun()

    # =========================================================================
    # ABA 2: CENTRAL DE DESPACHO & ROTAS (VISÃO GESTOR / LOGÍSTICA)
    # =========================================================================
    with aba_despacho:
        st.markdown("### 🗺️ Gestão de Corretivas & Otimização de Rotas")
        st.caption("O sistema avalia a localização dos chamados ativos, agrupa atendimentos no mesmo local/polo e permite o despacho em bloco para o técnico disponível.")

        df_ativos = df[df["status"].astype(str).str.upper().isin(["ATIVO", "EM ATENDIMENTO"])]

        if df_ativos.empty:
            st.info("ℹ️ Não existem chamados pendentes de atendimento no momento.")
        else:
            rotas_agrupadas = _organizar_rotas_inteligentes(df_ativos, equipa_tecnica)
            total_economia = sum(r["economia_viagens"] for r in rotas_agrupadas)
            paradas_total = sum(1 for _, r in df_ativos.iterrows() if "PARADO" in str(r.get("condicao_inicial", "")).upper())

            # Indicadores no Topo
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            with col_kpi1:
                st.metric("Total de Chamados Ativos", len(df_ativos))
            with col_kpi2:
                st.metric("Rotas Geográficas Propostas", len(rotas_agrupadas))
            with col_kpi3:
                st.metric("Viagens Economizadas", f"⚡ {total_economia} viagens", help="Deslocamentos poupados ao agrupar múltiplos equipamentos no mesmo local/cidade.")
            with col_kpi4:
                st.metric("Máquinas Críticas Paradas", f"🚨 {paradas_total}")

            st.markdown("---")

            sub_aba_rotas, sub_aba_individual = st.tabs([
                "🧠 1. Rotas Otimizadas & Despacho em Bloco",
                "📋 2. Todos os Chamados Ativos (Visão Detalhada)"
            ])

            with sub_aba_rotas:
                st.markdown("#### 🚗 Sugestões de Rotas por Proximidade e Mesmo Estabelecimento")
                st.info("💡 **Inteligência de Rota:** Chamados para a mesma instituição ou cidade foram agrupados. Escolha o técnico disponível para despachar a rota inteira com 1 clique.")

                lista_tecnicos_nomes = sorted(list(equipa_tecnica.keys()))
                if not lista_tecnicos_nomes:
                    lista_tecnicos_nomes = ["NETTO", "ANTONIO", "GABRIEL", "SÉRGIO", "ARQUIMEDES", "TONY", "JAIR", "FELIPE"]

                for num_r, r_info in enumerate(rotas_agrupadas, 1):
                    cli_r = r_info["cliente"]
                    cid_r = r_info["cidade"]
                    uf_r = r_info["estado"]
                    end_r = r_info["endereco"]
                    qtd_r = r_info["qtd"]
                    df_r = r_info["df_sub"]
                    tec_sug_r = r_info["tec_sugerido"]

                    icone_alerta = "🚨" if r_info["tem_parada"] else "🟢"
                    badge_economia = f"⚡ Economia de {r_info['economia_viagens']} viagens!" if r_info['economia_viagens'] > 0 else "Atendimento Pontual"
                    titulo_card = (
                        f"Rota #{num_r}: {cli_r} — {cid_r}/{uf_r} ({qtd_r} Equipamentos | {badge_economia})"
                    )

                    with st.expander(f"{icone_alerta} {titulo_card}", expanded=(num_r <= 3)):
                        c_col1, c_col2 = st.columns([2.5, 1.5])
                        with c_col1:
                            st.markdown(f"**Instituição / Cliente:** `{cli_r}`")
                            st.markdown(f"📍 **Cidade / Polo:** `{cid_r} - {uf_r}` | **Endereço:** {end_r or 'Não informado'}")
                            
                            # Tabela de Equipamentos na Rota
                            st.markdown("##### ⚙️ Equipamentos agrupados nesta rota:")
                            itens_tabela = []
                            for idx_sub, row_sub in df_r.iterrows():
                                id_os_sub = obter_id_os(idx_sub, row_sub)
                                eq_sub = row_sub.get("equipamento", "N/D")
                                srv_sub = row_sub.get("tipo_servico", "CORRETIVA")
                                def_sub = limpar_texto(row_sub.get("defeito_relatado"), limpar_texto(row_sub.get("pendencias"), "-"))
                                cond_sub = "🔴 PARADO" if "PARADO" in str(row_sub.get("condicao_inicial", "")).upper() else "🟡 OPERANDO"
                                tec_atual_sub = row_sub.get("tecnico_responsavel", "A DEFINIR")
                                itens_tabela.append({
                                    "OS #": f"#{id_os_sub}",
                                    "Equipamento": eq_sub,
                                    "Serviço": srv_sub,
                                    "Condição": cond_sub,
                                    "Defeito Relatado": def_sub[:45] + ("..." if len(def_sub) > 45 else ""),
                                    "Técnico Atual": tec_atual_sub
                                })
                            st.dataframe(pd.DataFrame(itens_tabela), use_container_width=True, hide_index=True)

                            # Ferramentas consolidadas
                            kits_txt = "; ".join(r_info["kits"]) if r_info["kits"] else "Maleta Padrão"
                            st.markdown(f"🧰 **Ferramental & Kits a Separar para toda a rota:** `{kits_txt}`")

                        with c_col2:
                            st.markdown("##### 👤 Despacho da Rota Completa:")
                            st.caption(f"📍 Sugestão por proximidade geográfica: **{tec_sug_r}**")

                            idx_tec_default = lista_tecnicos_nomes.index(tec_sug_r) if tec_sug_r in lista_tecnicos_nomes else 0
                            tec_selecionado_rota = st.selectbox(
                                "Técnico disponível para a rota:",
                                lista_tecnicos_nomes,
                                index=idx_tec_default,
                                key=f"sel_tec_rota_{num_r}_{cli_r[:10]}"
                            )

                            btn_despachar_rota = st.button(
                                f"🚀 Despachar {qtd_r} Chamados para {tec_selecionado_rota}",
                                type="primary",
                                key=f"btn_despacho_rota_{num_r}_{cli_r[:10]}",
                                use_container_width=True
                            )

                            if btn_despachar_rota:
                                tel_novo = equipa_tecnica.get(tec_selecionado_rota, {}).get("tel", "558532542929")
                                for idx_os_m in r_info["indices"]:
                                    df.at[idx_os_m, "tecnico_responsavel"] = tec_selecionado_rota
                                    df.at[idx_os_m, "telefone_tecnico"] = tel_novo
                                    df.at[idx_os_m, "confirmado"] = "SIM"

                                if salvar_dados_seguro(df, ctx.db_name, ctx.caminho_excel):
                                    st.cache_data.clear()
                                    
                                    # Aciona separação consolidada no almoxarifado
                                    todos_eqs = ", ".join(df_r["equipamento"].dropna().unique())
                                    ok_s, msg_s = acionar_separacao_automatica_almoxarifado(
                                        ctx.db_name,
                                        tec_selecionado_rota,
                                        cli_r,
                                        todos_eqs,
                                        "ROTA CONSOLIDADA",
                                        kits_txt,
                                        os_id=f"ROTA-{num_r}"
                                    )
                                    
                                    st.success(f"🎉 **Rota {cli_r} ({qtd_r} Chamados) despachada com sucesso para {tec_selecionado_rota}!**")
                                    if ok_s:
                                        st.info(f"📦 {msg_s}")

                                    # Mensagem formatada para envio via WhatsApp
                                    msg_rota_wpp = (
                                        f"🚗 *ROTA OTIMIZADA EMED • {cli_r.upper()}*\n"
                                        f"📍 Cidade: {cid_r} - {uf_r}\n"
                                        f"👤 Técnico: {tec_selecionado_rota}\n"
                                        f"Total de Equipamentos na Rota: {qtd_r}\n\n"
                                        f"*SEQUÊNCIA DE ATENDIMENTOS:*\n"
                                    )
                                    for idx_sub, row_sub in df_r.iterrows():
                                        id_os_sub = obter_id_os(idx_sub, row_sub)
                                        eq_sub = row_sub.get("equipamento", "N/D")
                                        srv_sub = row_sub.get("tipo_servico", "CORRETIVA")
                                        cond_sub = "🔴 PARADO" if "PARADO" in str(row_sub.get("condicao_inicial", "")).upper() else "🟡 OPERANDO"
                                        msg_rota_wpp += f"• *OS #{id_os_sub}*: {eq_sub} [{srv_sub}] — {cond_sub}\n"

                                    msg_rota_wpp += f"\n🧰 *KITS A RETIRAR NO ALMOXARIFADO:*\n{kits_txt}\n"
                                    if end_r:
                                        msg_rota_wpp += f"\n📍 *Endereço:* {end_r}\n"
                                        link_map = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(f'{end_r}, {cid_r}')}"
                                        msg_rota_wpp += f"🗺️ *Navegação:* {link_map}"

                                    tel_limpo = tel_novo.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
                                    link_wpp_final = f"https://wa.me/{tel_limpo or '558532542929'}?text={urllib.parse.quote(msg_rota_wpp)}"

                                    st.markdown(f"""
                                        <div style="margin-top: 10px;">
                                            <a href="{link_wpp_final}" target="_blank" style="background:#25d366; color:white; padding:10px 14px; border-radius:8px; text-decoration:none; font-weight:bold; display:inline-block; font-size:13px;">
                                                📲 Enviar Rota Pronta no WhatsApp do Técnico
                                            </a>
                                        </div>
                                    """, unsafe_allow_html=True)
                                    st.rerun()

                            # Links de Navegação Waze / Maps
                            if end_r:
                                end_encoded = urllib.parse.quote(f"{end_r}, {cid_r}")
                                st.markdown(
                                    f"""
                                    <div style="margin-top: 12px;">
                                        <a href="https://www.google.com/maps/search/?api=1&query={end_encoded}" target="_blank" style="text-decoration: none; background: #0f766e; color: #fff; padding: 5px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; margin-right: 6px;">
                                            📍 Google Maps
                                        </a>
                                        <a href="https://waze.com/ul?q={end_encoded}" target="_blank" style="text-decoration: none; background: #0284c7; color: #fff; padding: 5px 10px; border-radius: 5px; font-size: 11px; font-weight: bold;">
                                            🚗 Waze
                                        </a>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

            # Aba 2: Todos os chamados individuais
            with sub_aba_individual:
                st.markdown("#### 📋 Todos os Chamados Ativos (Visão Detalhada)")
                for idx_a, row_a in df_ativos.iterrows():
                    id_os_a = obter_id_os(idx_a, row_a)
                    cli_a = limpar_texto(row_a.get("cliente"), "N/D")
                    eq_a = limpar_texto(row_a.get("equipamento"), "N/D")
                    def_a = limpar_texto(row_a.get("defeito_relatado"), limpar_texto(row_a.get("pendencias"), "-"))
                    tec_a = limpar_texto(row_a.get("tecnico_responsavel"), "A DEFINIR")
                    cid_a = limpar_texto(row_a.get("cidade"), "FORTALEZA")
                    end_a = limpar_texto(row_a.get("endereco"), "")
                    cond_ini_a = limpar_texto(row_a.get("condicao_inicial"), "OPERACIONAL")
                    foto_a = limpar_texto(row_a.get("foto_evidencia"), "")

                    badge_status = "🔴 MÁQUINA PARADA" if "PARADO" in cond_ini_a.upper() else "🟡 FALHA PARCIAL"

                    with st.expander(f"OS #{id_os_a} | {badge_status} | {cli_a} — {eq_a} [Técnico: {tec_a}]"):
                        c_det1, c_det2 = st.columns([2.5, 1.5])
                        with c_det1:
                            st.markdown(f"**Cliente:** `{cli_a}` | **Cidade:** `{cid_a}`")
                            st.markdown(f"**Endereço:** {end_a}")
                            st.markdown(f"**Defeito Relatado:** {def_a}")
                            pre_at_txt = limpar_texto(row_a.get("pre_atendimento"), "")
                            if "REDE ELÉTRICA" in pre_at_txt or "ENERGIA:" in pre_at_txt:
                                st.caption(f"⚡ **Diagnóstico Preliminar:** {pre_at_txt}")
                            st.markdown(f"**Técnico Atual Designado:** `{tec_a}`")
                            
                            if end_a:
                                end_encoded = urllib.parse.quote(f"{end_a}, {cid_a}")
                                st.markdown(
                                    f"""
                                    <div style="margin-top: 10px;">
                                        <a href="https://www.google.com/maps/search/?api=1&query={end_encoded}" target="_blank" style="text-decoration: none; background: #0f766e; color: #fff; padding: 6px 12px; border-radius: 5px; font-size: 12px; font-weight: bold; margin-right: 8px;">
                                            📍 Ver no Google Maps
                                        </a>
                                        <a href="https://waze.com/ul?q={end_encoded}" target="_blank" style="text-decoration: none; background: #0284c7; color: #fff; padding: 6px 12px; border-radius: 5px; font-size: 12px; font-weight: bold;">
                                            🚗 Navegar pelo Waze
                                        </a>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                        with c_det2:
                            if foto_a and os.path.exists(foto_a):
                                st.image(foto_a, caption="Foto do Erro / Painel enviada na triagem", use_container_width=True)
                            else:
                                st.caption("Sem foto anexada pelo solicitante.")

    # =========================================================================
    # ABA 3: GERADOR DE ETIQUETAS QR CODE POR EQUIPAMENTO
    # =========================================================================
    with aba_etiquetas:
        st.markdown("### 🏷️ Gerador de Etiquetas QR Code por Equipamento")
        st.caption("Gere a etiqueta técnica para colar no chassi do equipamento. Ao escanear, a EmedOnline já abre com CNPJ e Equipamento 100% preenchidos!")

        col_et1, col_et2 = st.columns(2)
        with col_et1:
            clientes_cadastrados = sorted([c for c in df["cliente"].dropna().unique() if str(c).strip() and "NENHUM" not in str(c).upper()])
            cli_etiqueta = st.selectbox("1. Selecione o Cliente / Hospital:", clientes_cadastrados, key="sel_cli_etiqueta")
        
        with col_et2:
            df_cli_et = df[df["cliente"] == cli_etiqueta]
            eqs_cli_et = [e for e in df_cli_et["equipamento"].dropna().unique() if str(e).strip() and "NENHUM" not in str(e).upper()]
            if not eqs_cli_et:
                eqs_cli_et = ["EQUIPAMENTO PADRÃO"]
            eq_etiqueta = st.selectbox("2. Selecione o Equipamento Alvo:", eqs_cli_et, key="sel_eq_etiqueta")

        cnpj_etiqueta = limpar_texto(df_cli_et.iloc[0].get("cnpj") if not df_cli_et.empty else "", "03.611.974/0001-08")
        
        # URL da nuvem permanente da EMED com auto-preenchimento
        base_url_cloud = "https://emed-app.streamlit.app"
        url_chamado_qr = f"{base_url_cloud}/?cliente_qr={urllib.parse.quote(cli_etiqueta)}&equipamento_qr={urllib.parse.quote(eq_etiqueta)}&cnpj={urllib.parse.quote(cnpj_etiqueta)}"
        
        # Link WhatsApp direto pré-formatado
        msg_wpp_direto = (
            f"🚨 *CHAMADO TÉCNICO • EMEDONLINE*\n"
            f"Equipamento: {eq_etiqueta}\n"
            f"Cliente: {cli_etiqueta}\n"
            f"CNPJ: {cnpj_etiqueta}\n\n"
            f"Defeito apresentado: "
        )
        url_wpp_direto = f"https://wa.me/558532542929?text={urllib.parse.quote(msg_wpp_direto)}"

        qr_base64 = _gerar_qrcode_base64(url_chamado_qr)

        st.markdown("---")
        col_preview, col_inst = st.columns([1.8, 2.2])
        with col_preview:
            st.markdown("#### 🖨️ Pré-Visualização da Etiqueta Técnica:")
            st.markdown(
                f"""
                <div style="background: #ffffff; color: #0b132b; border: 3px solid #0b132b; border-radius: 12px; padding: 18px; max-width: 380px; box-shadow: 0 4px 15px rgba(0,0,0,0.25); font-family: Arial, sans-serif;">
                    <div style="border-bottom: 2px solid #0b132b; padding-bottom: 8px; margin-bottom: 10px;">
                        <div style="font-size: 15px; font-weight: 900; color: #0b132b; letter-spacing: 0.5px;">🏥 EMED ELETROMEDICINA</div>
                        <div style="font-size: 10px; color: #334155; font-weight: bold;">SUPORTE TÉCNICO & MANUTENÇÃO</div>
                    </div>
                    <div style="text-align: center; margin: 10px 0;">
                        <img src="{qr_base64}" style="width: 175px; height: 175px; display: inline-block; border: 1px solid #cbd5e1; padding: 4px; border-radius: 6px;" alt="QR Code"/>
                        <div style="font-size: 12px; font-weight: 800; color: #0284c7; margin-top: 6px;">APONTE A CÂMERA DO CELULAR</div>
                        <div style="font-size: 10px; color: #64748b;">Abertura Direta em 10 Segundos</div>
                    </div>
                    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; font-size: 11px; margin-top: 8px; line-height: 1.4;">
                        <div><b>EQUIPAMENTO:</b> {eq_etiqueta}</div>
                        <div><b>CLIENTE:</b> {cli_etiqueta}</div>
                        <div><b>CNPJ:</b> {cnpj_etiqueta}</div>
                        <div><b>CENTRAL 24H:</b> (85) 3254-2929</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with col_inst:
            st.markdown("#### ⚡ Como funciona para o cliente em campo:")
            st.markdown(
                f"""
                1. **Adesive a etiqueta** diretamente no chassi do Tomógrafo, Raio-X ou Ultrassom.
                2. Quando o aparelho apresentar qualquer anomalia ou código de erro, o operador do hospital apenas aponta a câmera do celular para o adesivo.
                3. **O sistema já abre no celular com Hospital, CNPJ e Equipamento 100% preenchidos!**
                4. O cliente apenas descreve o defeito, tira a foto do display e clica em **Chamar Equipe**.
                """
            )
            st.markdown(f"**🔗 Link Direto Integrado:**")
            st.code(url_chamado_qr, language="text")
            
            st.markdown(
                f"""
                <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="{url_chamado_qr}" target="_blank" style="display: inline-block; background: #0284c7; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px;">
                        🧪 Testar Link do Equipamento
                    </a>
                    <a href="{url_wpp_direto}" target="_blank" style="display: inline-block; background: #25d366; color: #fff; font-weight: bold; padding: 8px 14px; border-radius: 6px; text-decoration: none; font-size: 13px;">
                        💬 Abrir via WhatsApp Direto
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

    # =========================================================================
    # ABA 4: COMO FUNCIONA (GUIA TÉCNICO & PROCEDIMENTOS)
    # =========================================================================
    with aba_instrucoes:
        st.markdown("### 📘 Fluxo de Trabalho EmedOnline & Fechamento de OS")
        st.markdown(
            """
            O objetivo da **EmedOnline** é cortar a burocracia e acelerar o tempo de resposta médica para equipamentos de diagnóstico por imagem:

            1. **O Cliente / Hospital relata:**
               - Informa o CNPJ ou nome da instituição.
               - Seleciona o equipamento e relata o defeito com 1 foto do display de erro.
            2. **O Sistema automatiza:**
               - Classifica se é parada total de hospital (Prioridade 1) ou falha pontual.
               - Sugere orientações preliminares das **Instruções de Trabalho (ITs) e POPs da EMED**.
               - Encaixa na rota da equipe técnica mais próxima.
            3. **O que sobra para o Técnico preencher em campo (Aba Chamados & OS)?**
               - 🛠️ **Serviço Executado** (o diagnóstico real e o conserto feito).
               - 📦 **Peças Utilizadas** (baixa no estoque e geração de cobrança).
               - 🚨 **Pendências Técnicas** (se alguma peça ficou sob encomenda).
               - 📝 **Observações & Assinatura** do cliente no vidro do celular.
            """
        )
