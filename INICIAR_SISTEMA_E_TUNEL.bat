@echo off
title Sistema EMED - Servidor & Tunel Mobile
echo ====================================================
echo      INICIANDO SISTEMA EMED & ACESSO CELULAR
echo ====================================================
echo.

cd /d "C:\Users\vitor\OneDrive\Desktop\Sistema Emed"

echo [1/2] Iniciando Servidor Streamlit...
start "" /b python -m streamlit run app_emed.py --server.port 8501 --server.headless true

timeout /t 3 /nobreak > nul

echo [2/2] Iniciando Tunel de Nuvem Cloudflare (4G/5G)...
echo.
echo ====================================================
echo O link e o QR Code serao gerados abaixo:
echo ====================================================
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8501
pause
