@echo off
chcp 65001 >nul
title Agent S 启动器

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10-3.12
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b
)

:: 安装依赖（已安装的会自动跳过）
echo [提示] 正在检查并安装依赖...
pip install gui-agents pytesseract pyautogui -i https://pypi.tuna.tsinghua.edu.cn/simple -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试
    pause
    exit /b
)

:: 启动
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8
python "%~dp0launcher.py"
if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请截图以上错误信息
    pause
)
