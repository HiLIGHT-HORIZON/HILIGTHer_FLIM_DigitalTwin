@echo off
echo =======================================================
echo   HILIGHTer Digital Twin ^| Desktop Workspace (Qt)
echo =======================================================
echo.
cd /d "%~dp0"
echo [1/2] Checking Dependencies...
pip install -r desktop_requirements.txt --quiet

echo [2/2] Launching Native GUI...
python desktop_app.py

pause
