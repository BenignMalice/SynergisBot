@echo off
echo Starting all services...

REM Start app/main_api.py on port 8000 (Multi-Timeframe Streamer, DTMS, Liquidity Sweep, Auto-execution)
REM This is the main API server that ChatGPT calls for auto-execution
REM Includes: Multi-Timeframe Streamer, DTMS, Liquidity Sweep, Auto-execution router
start "App API (8000)" cmd /k ".venv\Scripts\activate.bat && python start_api_server.py"

REM Start root main_api.py on port 8010 (Micro-Scalp Monitor)
REM This server runs the micro-scalp monitoring system
REM NOTE: Both servers share MT5 connection and database - this is OK as they use different ports
start "Root API (8010)" cmd /k ".venv\Scripts\activate.bat && python start_api_server.py 8010"

REM Start hub/command_hub.py in a new window
start "Command Hub" cmd /k ".venv\Scripts\activate.bat && python hub/command_hub.py"

REM Start desktop_agent.py in a new window
start "Desktop Agent" cmd /k ".venv\Scripts\activate.bat && python desktop_agent.py"

REM Start dtms_api_server.py in a new window
start "DTMS API Server" cmd /k ".venv\Scripts\activate.bat && python dtms_api_server.py"

REM Start chatgpt_bot.py in a new window
start "ChatGPT Bot" cmd /k ".venv\Scripts\activate.bat && python chatgpt_bot.py"

REM Start ngrok in a new window
start "Ngrok" cmd /k ".venv\Scripts\activate.bat && ngrok http 8000 --url=verbally-faithful-monster.ngrok-free.app"

REM Start news feed fetcher in a new window
start "News Feed Fetcher" cmd /k ".venv\Scripts\activate.bat && python fetch_news_feed.py"

REM Start breaking news scraper in a new window
start "Breaking News Scraper" cmd /k ".venv\Scripts\activate.bat && python priority2_breaking_news_scraper.py"

REM Start news sentiment fetcher in a new window
start "News Sentiment Fetcher" cmd /k ".venv\Scripts\activate.bat && python fetch_news_sentiment.py"

REM Open main dashboard in default browser
start "" "http://localhost:8000/"

REM Open ChatGPT Forex Trade Analyst in default browser
start "" "https://chatgpt.com/g/g-682f469ad4b08191b6d8828a2a6ff9ac-forex-trade-analyst"

echo All services started in separate windows.
timeout /t 2 /nobreak >nul

