@echo off
chcp 65001 >nul
title Sincronizador de Rede eMED (Notebook -> PC)
color 0b

echo ============================================================================
echo   EMED ELETROMEDICINA — SINCRONIZADOR DE REDE LOCAL (WI-FI)
echo ============================================================================
echo.

set "PC_IP=192.168.3.12"
set "SRC_NOTEBOOK=C:\Backup_Sistema_EMED\Sistema_EMED_Completo_2026-11-04_01h12m40s"
set "DEST_PC=\\%PC_IP%\Sistema_Emed"

echo Testando conexao com o PC (%PC_IP%)...
ping -n 1 %PC_IP% >nul
if errorlevel 1 (
    echo [AVISO] O PC nao respondeu no IP %PC_IP%. Verifique se ambos estao no mesmo Wi-Fi.
    echo.
    echo Tentando sincronizar via Git (Nuvem)...
    git pull origin main
    pause
    exit /b
)

echo [1/2] Sincronizando Banco de Dados e Arquivos com o PC via Wi-Fi...
robocopy "%DEST_PC%" "%SRC_NOTEBOOK%" "emed.db" "emed_app_server.py" "emed_fiscal.py" /R:1 /W:1 /NP /NFL /NDL

echo [2/2] Sincronizacao de Rede Local Concluida com Sucesso!
echo.
echo ============================================================================
echo   ✅ NOTEBOOK ATUALIZADO VIA REDE EM SEGUNDOS!
echo ============================================================================
pause
