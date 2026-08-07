@echo off
chcp 65001 >nul 2>&1
title Vessel Departure Data Auto-Updater

echo ========================================
echo  Vessel Departure Data Auto-Updater
echo  Starting: %date% %time%
echo ========================================
echo.

REM ---- Configure paths ----
set PYTHON=C:\Users\culadmin\.workbuddy\binaries\python\envs\default\Scripts\python.exe
set SCRIPT=C:\Users\culadmin\WorkBuddy\2026-07-07-17-07-19\Schedule-Simulation\auto_update.py

REM ---- Run the update ----
"%PYTHON%" "%SCRIPT%"

echo.
echo ========================================
echo  Finished: %date% %time%
echo ========================================

REM ---- If double-clicked, pause so user can see result ----
if not defined PROMPT_FOR_TASK_SCHEDULER (
    echo.
    echo Press any key to close...
    pause >nul
)
