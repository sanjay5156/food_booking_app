@echo off
REM Windows launcher for the Food Booking System.
REM First run: creates a virtual environment and installs dependencies.
REM Every run: starts the app and opens it in your browser.

cd /d "%~dp0"

if not exist venv (
  echo Setting up ^(first run only^)...
  python -m venv venv
  venv\Scripts\pip install --upgrade pip -q
  venv\Scripts\pip install -r requirements.txt -q
)

venv\Scripts\python app.py
pause
