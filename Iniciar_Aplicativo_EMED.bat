@echo off
chcp 65001 >nul
title Aplicativo Oficial EMED (Servidor + App Tecnico & Gestor)
cd /d "%~dp0"
echo ============================================================================
echo   EMED ELETROMEDICINA LTDA. — SERVIDOR DO APLICATIVO OFICIAL (PWA + API)
echo ============================================================================
echo.
echo   - Versao do Tecnico (PC/Rede Local): http://localhost:8502/?modo=tecnico
echo   - Versao do Gestor  (PC/Rede Local): http://localhost:8502/?modo=gestor
echo   - Triagem Cliente   (PC/Rede Local): http://localhost:8502/?modo=cliente
echo.
start "" "http://localhost:8502/?modo=gestor"
python emed_app_server.py
pause
