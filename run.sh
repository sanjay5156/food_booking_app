#!/usr/bin/env bash
# Linux / macOS launcher for the Food Booking System.
# First run: creates a virtual environment and installs dependencies.
# Every run: starts the app and opens it in your browser.

set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Setting up (first run only)..."
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip -q
  ./venv/bin/pip install -r requirements.txt -q
fi

./venv/bin/python app.py
