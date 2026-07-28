@echo off
setlocal

rem Run from the repository root so relative imports and files resolve correctly.
pushd "%~dp0"

echo [start] Starting FastAPI Backend on http://127.0.0.1:8000...
start "FastAPI Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo [start] Starting Vite Frontend on http://localhost:7070...
start "Vite Frontend" cmd /k "npm run dev --prefix frontend"

echo.
echo ===================================================
echo 🚀 Both servers are launching in separate windows!
echo.
echo - Map page is at: http://localhost:7070/#/map
echo - API docs are at: http://localhost:8000/docs
echo ===================================================
echo.
echo Press any key to exit this startup launcher...
pause > nul

popd
endlocal