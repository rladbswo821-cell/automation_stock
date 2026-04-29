@echo off
tasklist /fi "imagename eq pythonw.exe" | find /i "pythonw.exe" > nul
if %errorlevel% == 0 (
    taskkill /f /im pythonw.exe
    echo [%date% %time%] Bot stopped >> startup_log.txt
    echo [OK] Bot stopped.
) else (
    echo [INFO] Bot is not running.
)
pause
