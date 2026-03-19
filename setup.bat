@echo off
title Local RAG Agent — Setup
color 0A
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     Local RAG Agent — First-Time Setup   ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Download from https://python.org
    pause & exit /b 1
)
echo [OK] Python found.

:: Check Ollama
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Ollama not found.
    echo        Download and install from: https://ollama.com
    echo        Then re-run this setup.
    pause & exit /b 1
)
echo [OK] Ollama found.

:: Create venv
if not exist "venv\" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)
echo [OK] Virtual environment ready.

:: Install requirements
echo [INFO] Installing Python packages (this may take a few minutes)...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo [OK] Packages installed.

:: Pull Ollama models
echo [INFO] Pulling Ollama models (this may take several minutes)...
ollama pull mxbai-embed-large
ollama pull qwen2.5:7b
echo [OK] Models ready.

:: Create desktop shortcut
echo [INFO] Creating desktop shortcut...
set SCRIPT_DIR=%~dp0
set SHORTCUT=%USERPROFILE%\Desktop\RAG Agent.bat
echo @echo off > "%SHORTCUT%"
echo title Local RAG Agent >> "%SHORTCUT%"
echo cd /d "%SCRIPT_DIR%" >> "%SHORTCUT%"
echo call venv\Scripts\activate.bat >> "%SHORTCUT%"
echo python app.py >> "%SHORTCUT%"
echo [OK] Desktop shortcut created: "RAG Agent.bat"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║         Setup Complete!                  ║
echo  ║                                          ║
echo  ║  Double-click "RAG Agent" on Desktop     ║
echo  ║  or run: python app.py                   ║
echo  ╚══════════════════════════════════════════╝
echo.
pause
