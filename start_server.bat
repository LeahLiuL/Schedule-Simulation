@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   Shipping Schedule Server
echo ========================================
echo.
python "%~dp0data_server.py"
pause
