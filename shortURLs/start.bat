@echo off
setlocal

rem Run from shortURLs root directory
pushd "%~dp0"

echo ===================================================
echo 🔗 Starting URL Shortener Microservice
echo ===================================================

echo [cleanup] Checking for existing processes on port 8002...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002\>"') do (
    echo [cleanup] Terminating process %%a on port 8002...
    taskkill /F /PID %%a /T >nul 2>&1
)

rem Ensure MongoDB is up on port 27017
netstat -aon | findstr ":27017\>" >nul 2>&1
if errorlevel 1 (
    echo [db] MongoDB is not running. Starting MongoDB container via Docker...
    docker compose up -d db
)

echo.
echo ===================================================
echo  - Local API:     http://127.0.0.1:8002
echo  - Swagger Docs:  http://127.0.0.1:8002/docs
echo  - Metrics:       http://127.0.0.1:8002/metrics
echo ===================================================
echo.

cd src
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002

popd
endlocal
