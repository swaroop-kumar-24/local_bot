@echo off
title Local RAG Agent — Update
color 0B
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║      Local RAG Agent — Update Tool       ║
echo  ╚══════════════════════════════════════════╝
echo.
cd /d "%~dp0"

:: Check git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git not found. Download from https://git-scm.com
    pause & exit /b 1
)

:: Show current version
echo [INFO] Current version:
git log -1 --format="  Commit: %%h  |  Date: %%ad  |  %%s" --date=short
echo.

:: Pull latest changes
echo [INFO] Pulling latest changes from GitHub...
git pull origin main
if %errorlevel% neq 0 (
    echo.
    echo [WARN] Git pull failed. Possible reasons:
    echo   - You have local changes conflicting with the update
    echo   - No internet connection
    echo   - Remote branch is different
    echo.
    echo   To force update (OVERWRITES local changes):
    echo   git fetch origin ^& git reset --hard origin/main
    echo.
    pause & exit /b 1
)

:: Activate venv
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

:: Install any new packages
echo [INFO] Checking for new dependencies...
pip install -r requirements.txt --upgrade
echo [OK] Dependencies up to date.

:: Show what changed
echo.
echo [INFO] Changes applied:
git log -5 --format="  %%ad  %%s" --date=short
echo.

echo  ╔══════════════════════════════════════════╗
echo  ║   Update complete! Run app via run.bat   ║
echo  ╚══════════════════════════════════════════╝
echo.
pause
