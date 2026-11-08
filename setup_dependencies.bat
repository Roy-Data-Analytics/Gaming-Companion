@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Check that Python 3.13 is installed and available on PATH.
    pause
    exit /b 1
)
echo Dependencies installed. Run Start_SteamGamingCompanion.bat.
pause
