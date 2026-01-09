@echo off
echo Stopping all MoneyBot services...
echo.

REM Stop all Python processes
echo Stopping all Python processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1

REM Stop Ngrok
echo Stopping Ngrok...
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM ngrok >nul 2>&1

REM Close service command windows opened by start_all_services.bat
echo Closing service windows...
taskkill /F /FI "WINDOWTITLE eq Main API" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Command Hub" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Desktop Agent" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DTMS API Server" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ChatGPT Bot" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Ngrok" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq News Feed Fetcher" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Breaking News Scraper" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq News Sentiment Fetcher" /IM cmd.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Root API (8010)" /IM cmd.exe >nul 2>&1

REM Force close any remaining cmd windows that might be service windows
echo Force closing remaining command windows...
taskkill /F /IM cmd.exe >nul 2>&1

echo.
echo All services have been stopped.
timeout /t 2 /nobreak >nul
