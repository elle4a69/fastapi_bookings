@echo off
echo ===================================================
echo 🧹 Clearing ports 5191 (Frontend) and 8026 (Backend)...
echo ===================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0clear_ports.ps1"

echo.
echo ===================================================
echo 🚀 Starting Backend Server on port 8026...
echo ===================================================
start "Assistant UI Backend (Port 8026)" cmd /k "cd /d %~dp0backend && set PORT=8026 && .venv\Scripts\python.exe main.py"

echo.
echo ===================================================
echo 🚀 Starting Frontend Dev Server on port 5191...
echo ===================================================
cd /d %~dp0frontend
npm run dev -- --port 5191
