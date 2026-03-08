#!/bin/bash

# Windows build script using custom Wine setup
# This script builds only for Windows using your osu-wine setup

set -e

echo "Orbus Launcher Windows Build (Wine)"
echo "===================================="

# Custom Wine command - modify this if your Wine setup is different
WINE_CMD="osu-wine --wine"

# Check if custom Wine command is available
if ! command -v osu-wine &> /dev/null; then
    echo "Error: osu-wine not found. Please install or check your Wine setup."
    echo "Current command: $WINE_CMD"
    exit 1
fi

echo "Using custom Wine command: $WINE_CMD"

# Check if Python for Windows is installed
if [ ! -d "/home/$USER/.wine/drive_c/python" ]; then
    echo "Installing Python for Windows..."
    wget https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe
    $WINE_CMD python-3.11.0-amd64.exe /quiet InstallAllUsers=1 TargetDir="C:\\python"
    rm python-3.11.0-amd64.exe
else
    echo "Python for Windows already installed"
fi

# Use the full path to Python in Wine
WINE_PYTHON="$WINE_CMD C:\\python\\python.exe"

# Install dependencies in Wine environment
echo "Installing dependencies in Wine environment..."
$WINE_PYTHON -m pip install --upgrade pip
$WINE_PYTHON -m pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests

# Build the Windows executable
echo "Building Windows executable..."
$WINE_PYTHON build.py

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo "Windows build completed successfully!"
echo "Check the 'packages' directory for the Windows output."

# Show the Windows package if it exists
if [ -d "packages/OrbusLauncher-windows-amd64" ]; then
    echo ""
    echo "Windows package contents:"
    ls -la packages/OrbusLauncher-windows-amd64/
fi
