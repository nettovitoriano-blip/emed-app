@echo off
chcp 65001 >nul
title EMED — Voltar para Versao Anterior Estavel (Rollback 1-Clique)
color 0e

cd /d "%~dp0"

echo ============================================================================
echo   EMED ELETROMEDICINA — VOLTAR VERSAO ANTERIOR (DAR UM PASSO ATRAS)
echo ============================================================================
echo.
echo Ultimas 5 atualizacoes enviadas ao sistema:
echo.
git log -n 5 --oneline
echo.
echo ============================================================================
echo Deseja desfazer a ULTIMA atualizacao e restaurar o sistema imediatamente?
echo   [1] SIM - Desfazer a ultima alteracao e reenviar para o Render (Seguro)
echo   [2] Apenas rodar a verificacao de erros (Python + JavaScript)
echo   [0] Cancelar e sair
echo ============================================================================
echo.
set /p OPCAO="Escolha uma opcao (1, 2 ou 0): "

if "%OPCAO%"=="1" (
    echo.
    echo [1/3] Revertendo a ultima alteracao com seguranca...
    git revert HEAD --no-edit
    if errorlevel 1 (
        echo ❌ Nao foi possivel reverter automaticamente. Abortando revert...
        git revert --abort >nul 2>&1
        pause
        exit /b 1
    )
    echo [2/3] Validando Python e JavaScript antes de enviar...
    python verificar_antes_de_subir.py
    if errorlevel 1 (
        echo ❌ Erro na validacao!
        pause
        exit /b 1
    )
    echo [3/3] Enviando versao restaurada para o Render...
    git push origin main
    echo.
    echo ✅ PRONTO! O Render vai restaurar o sistema em ~1 a 2 minutos.
    pause
    exit /b 0
)

if "%OPCAO%"=="2" (
    echo.
    python verificar_antes_de_subir.py
    pause
    exit /b 0
)

echo Operacao cancelada.
pause
