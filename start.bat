@echo off
setlocal

rem Run from the repository root so relative imports and files resolve correctly.
pushd "%~dp0"

echo [start] Starting FastAPI Backend on http://127.0.0.1:8000...
start "FastAPI Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo [start] Starting Vite Frontend on http://localhost:7070...
start "Vite Frontend" cmd /k "npm run dev --prefix frontend"

echo [start] Starting SMS Assistant API and UI...
start "SMS Assistant Suite" cmd /c call "integrations\assistant-ui-v2\start.bat"

echo.
echo ===================================================
echo 🚀 Booking and SMS Assistant services are launching!
echo.
echo - Booking admin is at: http://localhost:7070/admin
echo - SMS Assistant workspace: http://localhost:7070/admin/sms-assistant
echo - SMS Assistant UI: http://localhost:5191
echo - SMS Assistant API: http://localhost:8026
echo - API docs are at: http://localhost:8000/docs
echo ===================================================
echo.
echo Press any key to exit this startup launcher...
pause > nul

popd
endlocal
