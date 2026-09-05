@echo off
chcp 65001 >nul
title DEVIL CHAT - Private Ephemeral P2P

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo                     [!] PYTHON NOT FOUND [!]
    echo ======================================================================
    echo.
    echo Python 3 is required to run DEVIL CHAT, but was not found on your PATH.
    echo.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo Make sure to check the box: "Add python.exe to PATH" during installation.
    echo.
    echo ======================================================================
    pause
    exit /b 1
)

:: Install / verify dependencies
python -c "import cryptography, colorama" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing required dependencies...
    pip install -r "%~dp0requirements.txt"
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Warning: Failed to install dependencies automatically.
        echo Please run: pip install -r requirements.txt
        pause
    )
)

:: Launch DEVIL CHAT
python "%~dp0devil_chat.py"
