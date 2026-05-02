@echo off
title Agent S Launcher

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10-3.12
    echo https://www.python.org/downloads/
    pause
    exit /b
)

:: Install dependencies
echo [INFO] Checking dependencies...
pip install gui-agents pytesseract pyautogui -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your network.
    pause
    exit /b
)

:: Launch
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
python "%~dp0launcher.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Launch failed. Please screenshot the error above.
    pause
)
