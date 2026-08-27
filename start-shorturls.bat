@echo off
setlocal

rem Run from the repository root
pushd "%~dp0"

echo [cleanup] Checking for existing processes on port 8002...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002\>"') do (
    echo [cleanup] Terminating process %%a on port 8002...
    taskkill /F /PID %%a /T >nul 2>&1
)

rem Ensure MongoDB is up on port 27017
netstat -aon | findstr ":27017\>" >nul 2>&1
if errorlevel 1 (
    echo [db] Starting MongoDB container via Docker...
    cd shortURLs
    docker compose up -d db
    cd ..
)

echo [start] Starting URL Shortener Service on http://127.0.0.1:8002...
start "URL Shortener Service" cmd /k "cd shortURLs\src && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8002"

echo.
echo ===================================================
echo 🔗 URL Shortener Service launched!
echo - API:         http://127.0.0.1:8002
echo - Swagger UI:  http://127.0.0.1:8002/docs
echo ===================================================
echo.
echo Press any key to exit this launcher...
pause > nul

popd
endlocal
