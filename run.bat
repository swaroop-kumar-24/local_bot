@echo off
title Local RAG Agent
cd /d "%~dp0"
call venv\Scripts\activate.bat
python app.py
pause
