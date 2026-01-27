@echo off
setlocal enabledelayedexpansion

:: Always run relative to this script (handles spaces in path)
cd /d "%~dp0"

set APP_NAME=TAHA_College_Detail_Bot
set MAIN_SCRIPT=taha_college_detail.py

:: Prefer the project's venv if it exists; fall back to system Python
set "VENV_DIR=%~dp0..\\venv"
if exist "%VENV_DIR%\\Scripts\\python.exe" (
    set "PYTHON=%VENV_DIR%\\Scripts\\python.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" -m pip install --upgrade pip
"%PYTHON%" -m pip install -r requirements.txt
"%PYTHON%" -m pip install pyinstaller

:: Collect static assets into the bundle
set DATA_ARGS=^
 --add-data "%~dp0web;web"^
 --add-data "%~dp0templates;templates"^
 --add-data "%~dp0drivers;drivers"^
 --add-data "%~dp0data;data"

:: Build windowed app (no console)
"%PYTHON%" -m PyInstaller --noconsole --onedir --name "%APP_NAME%" %DATA_ARGS% --clean --noconfirm "%MAIN_SCRIPT%"

echo(
echo Build complete. Check dist\%APP_NAME%\%APP_NAME%.exe
