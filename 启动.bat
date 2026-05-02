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

:: 检查依赖
python -c "import gui_agents" >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖，请稍候...
    pip install gui-agents pytesseract -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重试
        pause
        exit /b
    )
    echo [完成] 依赖安装成功
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
