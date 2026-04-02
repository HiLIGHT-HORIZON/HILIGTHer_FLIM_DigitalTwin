@echo off
echo =======================================================
echo   HILIGHTer Digital Twin ^| Desktop Workspace (Qt)
echo =======================================================
echo.
cd /d "%~dp0"
cd python
echo [1/2] Checking and updating desktop dependencies...
echo       Status will be shown in this terminal and on the splash screen.
echo.
echo [2/2] Launching Native GUI...
python desktop_app.py

pause
