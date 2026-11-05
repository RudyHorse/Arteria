@echo off
setlocal EnableExtensions
title Arteria Launcher
cd /d "%~dp0"

echo === Arteria ===
echo.

rem ---- Prerequisites ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js not found in PATH.
    pause
    exit /b 1
)

rem ---- Backend venv ----
cd /d "%~dp0backend"
if not exist "venv\Scripts\python.exe" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
    if errorlevel 1 pause & exit /b 1
) else (
    echo [1/4] Virtual environment found, skipping creation.
)

echo [2/4] Installing backend dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 pause & exit /b 1

rem ---- Frontend deps ----
cd /d "%~dp0frontend"
echo [3/4] Installing frontend dependencies...
call npm install
if errorlevel 1 pause & exit /b 1

rem ---- Start servers ----
cd /d "%~dp0"
echo [4/4] Starting servers...
start "Arteria-Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe main.py"
timeout /t 3 /nobreak >nul
start "Arteria-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo NOTE: s2t and Seis also use port 3000 - change in vite.config.js if needed.
echo Close the server windows to stop.
echo.
endlocal
