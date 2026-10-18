import streamlit as st


def inject_custom_css():
    st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)
    st.markdown("""
        <style>
        .stApp {
            background-color: #0b132b;
            color: #ffffff;
        }
        header[data-testid="stHeader"] {
            background-color: #0b132b !important;
        }
        .stApp > header {
            background-color: transparent !important;
        }
        p, span, label, div {
            color: #f8fafc !important;
        }        
        [data-testid="stSidebar"] {
            background-color: #1c2541;
            border-right: 1px solid #3a506b;
        }
        [data-testid="stSidebar"] .stRadio label {
            color: #ffffff !important;
            font-weight: 600 !important;
            font-size: 15px !important;
        }
        [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
            color: #cbd5e1 !important;
        }

        /* BOTÕES DE RECOLHER/ABRIR ABA LATERAL (SEM BORDA DUPLA) */
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {
            opacity: 1 !important;
            visibility: visible !important;
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"] button,
        [data-testid="stSidebarCollapsedControl"] button {
            opacity: 1 !important;
            visibility: visible !important;
            background-color: #1c2541 !important;
            border: 1px solid #64dfdf !important;
            border-radius: 8px !important;
            color: #64dfdf !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebarCollapseButton"] svg,
        [data-testid="stExpandSidebarButton"] svg,
        [data-testid="collapsedControl"] svg,
        [data-testid="stSidebarCollapsedControl"] svg {
            fill: #64dfdf !important;
            color: #64dfdf !important;
        }

        /* Caixas de Seleção (Selectbox / Multiselect / Dropdowns / Popovers) */
        div[data-baseweb="select"],
        div[data-baseweb="select"] > div,
        div[data-baseweb="select"] div {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border-color: #3a506b !important;
        }
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] input {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        div[data-baseweb="select"] svg {
            fill: #64dfdf !important;
            color: #64dfdf !important;
        }
        div[data-baseweb="tag"] {
            background-color: #3a506b !important;
            color: #ffffff !important;
            border: 1px solid #64dfdf !important;
        }
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[data-baseweb="menu"],
        div[role="listbox"],
        ul[data-baseweb="menu"],
        ul[role="listbox"] {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border: 1px solid #64dfdf !important;
        }
        ul[data-baseweb="menu"] li,
        li[role="option"],
        div[role="option"] {
            color: #ffffff !important;
            background-color: #1c2541 !important;
        }
        ul[data-baseweb="menu"] li:hover,
        li[role="option"]:hover,
        div[role="option"]:hover,
        li[aria-selected="true"],
        div[aria-selected="true"] {
            background-color: #3a506b !important;
            color: #64dfdf !important;
        }

        /* Calendário (DateInput Popover) */
        div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] * {
            background-color: #1c2541 !important;
            color: #ffffff !important;
        }

        /* Inputs Numéricos, de Texto, Textarea e Containers BaseWeb (incluindo desabilitados) */
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="textarea"] {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border: 1px solid #3a506b !important;
            border-radius: 8px !important;
        }
        .stNumberInput input,
        .stTextInput input,
        .stDateInput input,
        .stTextArea textarea,
        div[data-baseweb="input"] input,
        div[data-baseweb="base-input"] input,
        div[data-baseweb="textarea"] textarea {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            caret-color: #64dfdf !important;
            text-transform: uppercase !important;
        }
        input:disabled,
        textarea:disabled,
        input[disabled],
        textarea[disabled] {
            background-color: #151d36 !important;
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            opacity: 1 !important;
        }
        input::placeholder,
        textarea::placeholder {
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            opacity: 0.8 !important;
        }
        .stNumberInput button {
            background-color: #3a506b !important;
            color: #ffffff !important;
        }
        .stNumberInput button:hover {
            background-color: #64dfdf !important;
            color: #0b132b !important;
        }

        /* Formulários, Abas, Alertas, Métricas e Barra de Ferramentas */
        [data-testid="stForm"] {
            background-color: #141c35 !important;
            border: 1px solid #3a506b !important;
            border-radius: 10px !important;
            padding: 16px !important;
        }
        [data-testid="stElementToolbar"],
        [data-testid="stElementToolbar"] button {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border-color: #3a506b !important;
        }
        [data-testid="stAlert"] {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border: 1px solid #3a506b !important;
        }
        [data-testid="stMetric"] {
            background-color: #1c2541 !important;
            border: 1px solid #3a506b !important;
            border-radius: 10px !important;
            padding: 12px 16px !important;
        }
        button[data-baseweb="tab"] {
            background-color: transparent !important;
            color: #cbd5e1 !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: #64dfdf !important;
            border-bottom-color: #64dfdf !important;
        }

        /* Botões Gerais, Form Submit e Download */
        .stButton button,
        div.stButton > button,
        [data-testid="stFormSubmitButton"] > button,
        [data-testid="stDownloadButton"] > button,
        button[kind="secondary"],
        button[kind="secondaryFormSubmit"] {
            background-color: #1c2541 !important;
            color: #ffffff !important;
            border: 1px solid #64dfdf !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            padding: 0.5rem 1rem !important;
        }
        button[kind="primary"],
        button[kind="primaryFormSubmit"] {
            background: linear-gradient(135deg, #0f766e 0%, #1c2541 100%) !important;
            color: #64dfdf !important;
            border: 2px solid #10b981 !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.35) !important;
        }
        .stButton button:hover,
        div.stButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover,
        [data-testid="stDownloadButton"] > button:hover,
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover {
            background-color: #3a506b !important;
            border-color: #64dfdf !important;
            color: #64dfdf !important;
        }

        /* Expanders escuros (borda única nítida sem linha dupla) */
        [data-testid="stExpander"] {
            background-color: transparent !important;
            border: none !important;
            margin-bottom: 10px !important;
        }
        [data-testid="stExpander"] details {
            background-color: #1c2541 !important;
            border: 1px solid #3a506b !important;
            border-radius: 10px !important;
            color: #ffffff !important;
        }
        [data-testid="stExpanderDetails"] {
            background-color: #1c2541 !important;
            border: none !important;
            border-top: 1px solid #2b3a55 !important;
            border-radius: 0 0 10px 10px !important;
            color: #ffffff !important;
        }
        [data-testid="stExpander"] details summary {
            background-color: #1c2541 !important;
            color: #64dfdf !important;
            border-radius: 10px !important;
        }
        [data-testid="stExpander"] details summary:hover {
            background-color: #25335a !important;
        }
        [data-testid="stExpander"] details summary p,
        [data-testid="stExpander"] details summary span,
        [data-testid="stExpander"] details summary svg {
            color: #64dfdf !important;
            fill: #64dfdf !important;
            font-weight: 600 !important;
        }

        /* File Uploader escuro */
        [data-testid="stFileUploader"] section {
            background-color: #1c2541 !important;
            border: 1px dashed #64dfdf !important;
            color: #ffffff !important;
        }
        [data-testid="stFileUploader"] section button {
            background-color: #3a506b !important;
            color: #ffffff !important;
            border: 1px solid #64dfdf !important;
        }

        .client-card {
            background-color: #1c2541;
            border: 1px solid #3a506b;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .client-card h3 {
            color: #64dfdf !important;
            margin-top: 0;
            font-size: 18px;
            font-family: 'Courier New', Courier, monospace;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .client-card p {
            color: #cbd5e1 !important;
            margin: 4px 0;
            font-size: 14px;
        }

        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
        }
        
        p, span, label {
            color: #e2e8f0;
        }
        </style>
    """, unsafe_allow_html=True)
