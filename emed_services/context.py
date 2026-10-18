from dataclasses import dataclass
from typing import Dict, Any
import pandas as pd


@dataclass
class AppContext:
    base_dir: str
    db_name: str
    caminho_excel: str
    hoje: pd.Timestamp
    usuario_atual: str
    perfil_atual: str
    df: pd.DataFrame
    df_tecnicos: pd.DataFrame
    df_veiculos: pd.DataFrame
    df_estoque: pd.DataFrame
    df_internos: pd.DataFrame
    equipa_tecnica: Dict[str, Dict[str, Any]]
