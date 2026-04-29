@echo off
set TASK_NAME=AutoStock_AssetBot
set BAT_PATH=C:\Users\hankook\Desktop\Automation_Stock\Auto_start_stock.bat

schtasks /delete /tn "%TASK_NAME%" /f > nul 2>&1

schtasks /create /tn "%TASK_NAME%" /tr "%BAT_PATH%" /sc ONLOGON /delay 0001:00 /rl HIGHEST /f

if %errorlevel% == 0 (
    echo [OK] Task Scheduler registered successfully.
    echo Task: %TASK_NAME%
    echo Runs: 1 minute after login
) else (
    echo [FAIL] Run as Administrator.
)

pause
