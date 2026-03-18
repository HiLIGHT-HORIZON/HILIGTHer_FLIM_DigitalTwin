@echo off
SETLOCAL EnableDelayedExpansion
TITLE HILIGHTer Digital Twin - Orchestrator

:: --- CONFIGURATION ---
SET BACKEND_DIR=backend
SET FRONTEND_DIR=frontend
SET PYTHON_EXE=python
SET NPM_EXE=npm

:: --- COLORS (Standard CMD) ---
SET GREEN=[OK]
SET RED=[ERROR]
SET YELLOW=[INFO]

:MENU
cls
echo ======================================================
echo    HILIGHTer: MATLAB to Python Digital Twin
echo ======================================================
echo.
echo  [1] DEPLOY (Install Backend and Frontend Dependencies)
echo  [2] START  (Run Full Ecosystem - Backend and UI)
echo  [3] CLEAN  (Remove node_modules and cache)
echo  [4] EXIT
echo.
set /p choice="Select an option [1-4]: "

if "%choice%"=="1" goto DEPLOY
if "%choice%"=="2" goto START
if "%choice%"=="3" goto CLEAN
if "%choice%"=="4" exit
goto MENU

:DEPLOY
echo.
echo %YELLOW% Setting up Backend (Python)...
%PYTHON_EXE% -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo %RED% Failed to install Python dependencies.
    pause
    goto MENU
)

echo.
echo %YELLOW% Setting up Frontend (Node.js)...
pushd %FRONTEND_DIR%
call %NPM_EXE% install
if %ERRORLEVEL% NEQ 0 (
    echo %RED% Failed to install Node.js dependencies.
    popd
    pause
    goto MENU
)
popd
echo.
echo %GREEN% Deployment Complete!
pause
goto MENU

:START
echo.
echo %YELLOW% Launching Backend Service (FastAPI)...
start "HILIGHTer Backend" cmd /k "%PYTHON_EXE% -m uvicorn backend.main:app --reload --port 8000"

echo.
echo %YELLOW% Launching Frontend Dashboard (Vite)...
pushd %FRONTEND_DIR%
start "HILIGHTer Frontend" cmd /k "npm run dev"
popd

echo.
echo %GREEN% Both services are starting in separate windows.
echo API: http://localhost:8000
echo UI:  http://localhost:5173
echo.
pause
goto MENU

:CLEAN
echo.
echo %YELLOW% Cleaning environments...
if exist "%FRONTEND_DIR%\node_modules" (
    echo Deleting %FRONTEND_DIR%\node_modules...
    rmdir /s /q "%FRONTEND_DIR%\node_modules"
)
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "%BACKEND_DIR%\__pycache__" rmdir /s /q "%BACKEND_DIR%\__pycache__"
echo %GREEN% Cleanup complete.
pause
goto MENU
