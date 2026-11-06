@echo off
chcp 65001 >nul
title Guardiao 24x7 - Servidor Oficial eMED (Porta 8502)
cd /d "%~dp0"
echo ============================================================================
echo   GUARDIAO 24/7 DO SISTEMA EMED ELETROMEDICINA (PORTA 8502)
echo   Auto-Restart Ativo: Se o servidor cair, reinicia sozinho em 2 segundos.
echo ============================================================================
python watchdog_servidor_24x7.py
