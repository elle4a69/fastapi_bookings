@echo off
setlocal
cd /d "%~dp0dev-dashboard"
echo ==================================================
echo  Starting Bookings App Dev Dashboard...
echo  Dashboard will be active at: http://localhost:2310
echo ==================================================
node server.js
if %ERRORLEVEL% neq 0 (
    echo.
    echo Error starting the dashboard. Make sure Node.js is installed.
    pause
)
endlocal
