@echo off
title Vridhi Analytics Server
cd /d "%~dp0"
chcp 65001 > nul

echo ===================================================
echo   Starting Vridhi Analytics Local Server...
echo ===================================================
echo.

set PYTHONPATH=src
set PYTHONUTF8=1

python -m vridhi_sim.api_cli

echo.
echo ===================================================
echo   Server stopped. Press any key to exit.
echo ===================================================
pause
