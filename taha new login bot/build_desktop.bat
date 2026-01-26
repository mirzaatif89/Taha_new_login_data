@echo off
setlocal enabledelayedexpansion

:: Always run relative to this script (handles spaces in path)
cd /d "%~dp0"

set APP_NAME=TAHA_College_Detail_Bot
set MAIN_SCRIPT=taha_college_detail.py

:: Install deps (uses system python). Swap to your venv if preferred: call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

:: Collect static assets into the bundle
set DATA_ARGS=^
 --add-data "%~dp0web;web"^
 --add-data "%~dp0templates;templates"^
 --add-data "%~dp0drivers;drivers"^
 --add-data "%~dp0data;data"

:: Build windowed app (no console)
pyinstaller --noconsole --onedir --name "%APP_NAME%" %DATA_ARGS% --clean --noconfirm "%MAIN_SCRIPT%"

echo(
echo Build complete. Check dist\%APP_NAME%\%APP_NAME%.exe
