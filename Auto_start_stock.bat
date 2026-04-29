@echo off

ping -n 6 127.0.0.1 > nul

cd /d "C:\Users\hankook\Desktop\Automation_Stock"

powershell -Command "Get-CimInstance Win32_Process -Filter 'name=\"pythonw.exe\"' | Where-Object { $_.CommandLine -like '*asset_master_bot*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

ping -n 3 127.0.0.1 > nul

start "" "C:\Users\hankook\AppData\Local\Python\bin\pythonw.exe" asset_master_bot.pyw

echo [%date% %time%] started >> startup_log.txt

exit
