@echo off
title Song Analyzer
cd /d "%~dp0"
echo Starting Song Analyzer...
echo.
echo Opening http://127.0.0.1:5000 in your browser...
start "" http://127.0.0.1:5000
venv\Scripts\python.exe app.py
