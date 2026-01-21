@echo off
setlocal

cd /d "%~dp0"

python -m pip install --upgrade pip
python -m pip install -r requirement.txt
python -m pip install pyinstaller

pyinstaller ^
  --noconsole ^
  --name "TAHA College Detail Bot" ^
  --add-data "web;web" ^
  --add-data "templates;templates" ^
  --add-data "drivers;drivers" ^
  --add-data "data;data" ^
  --clean ^
  --noconfirm ^
  taha_college_detail.py

echo.
echo Build complete. Check: dist\TAHA College Detail Bot\TAHA College Detail Bot.exe
