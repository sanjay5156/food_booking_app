@echo off
REM ============================================================
REM  Builds FoodBookingSystem.exe — a single file that runs the
REM  whole app with NO Python installation needed on the machine
REM  that runs it.
REM
REM  Run this ONCE, on any Windows PC that has Python installed.
REM  It produces dist\FoodBookingSystem.exe — copy that one file
REM  (nothing else) to any other Windows PC and double-click it.
REM ============================================================

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on this PC.
  echo Install Python from https://www.python.org/downloads/ ^(tick
  echo "Add Python to PATH" during setup^), then run this script again.
  pause
  exit /b 1
)

echo Setting up a temporary build environment...
python -m venv build_venv
build_venv\Scripts\pip install --upgrade pip -q
build_venv\Scripts\pip install -r requirements.txt -q
build_venv\Scripts\pip install pyinstaller -q

echo.
echo Building FoodBookingSystem.exe (this can take a minute or two)...
build_venv\Scripts\pyinstaller --noconfirm --onefile --name FoodBookingSystem ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import=openpyxl.cell._writer ^
  app.py

if exist dist\FoodBookingSystem.exe (
  echo.
  echo ============================================================
  echo  Done! Your standalone app is here:
  echo    dist\FoodBookingSystem.exe
  echo.
  echo  Copy just that one file to any Windows PC ^(no Python needed
  echo  there^) and double-click it to run the Food Booking System.
  echo  It will create its own data file next to wherever you place it.
  echo ============================================================
) else (
  echo.
  echo Something went wrong — scroll up for the PyInstaller error output.
)

pause
