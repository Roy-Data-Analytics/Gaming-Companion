@echo off
setlocal
cd /d "%~dp0"
python "ScreenShot_StableCore.py"
if errorlevel 1 (
    echo.
    echo Startup failed. See the error above. Run setup_dependencies.bat if dependencies are missing.
    pause
)
