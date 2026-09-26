@echo off
title Vridhi Analytics - Multi-Bank Dedicated Server Launcher
color 0A

echo ======================================================================
echo   VRIDHI ANALYTICS -- MULTI-BANK DEDICATED SERVERS LAUNCHER
echo ======================================================================
echo   Starting all isolated bank servers on your laptop:
echo    - Gateway Router : http://127.0.0.1:8000/app/
echo    - SBI Server Node : http://127.0.0.1:8001/
echo    - MAHB Server Node: http://127.0.0.1:8002/
echo    - CBIN Server Node: http://127.0.0.1:8003/
echo ======================================================================

set PYTHONPATH=src
start http://127.0.0.1:8000/app/
python scripts/run_all_bank_nodes.py

pause
