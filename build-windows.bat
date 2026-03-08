@echo off
REM Windows build script for Orbus Launcher

echo Orbus Launcher Windows Build Script
echo ==================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests

REM Run the build script
echo Building executable...
python build.py

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo Build completed successfully!
echo Check the 'packages' directory for the output.
pause
