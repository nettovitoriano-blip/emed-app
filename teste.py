import pandas as pd
import os

print("--- DIAGNÓSTICO DO SISTEMA EMED ---")
print("Pasta onde o Python está a procurar:", os.getcwd())

if os.path.exists("base_clientes.xlsx"):
    df = pd.read_excel("base_clientes.xlsx", engine="openpyxl")
    print(f"✅ Sucesso! O Excel foi encontrado com {len(df)} linhas.")
    print("\nLinhas da planilha:")
    print(df[['cliente', 'equipamento', 'ultima_preventiva']])
else:
    print("❌ ERRO: O ficheiro base_clientes.xlsx NÃO foi encontrado nesta pasta!")