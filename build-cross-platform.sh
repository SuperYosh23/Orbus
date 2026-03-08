#!/bin/bash

# Cross-platform build script for Orbus Launcher
# This script sets up environments for both Windows and Linux builds

set -e

echo "Orbus Launcher Cross-Platform Build Script"
echo "=========================================="

# Custom Wine command - modify this if your Wine setup is different
WINE_CMD="osu-wine --wine"

# Check if we're on Linux (for cross-compilation)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux system"
    
    # Check if custom Wine command is available
    if ! command -v osu-wine &> /dev/null; then
        echo "Error: osu-wine not found. Please install or check your Wine setup."
        echo "Current command: $WINE_CMD"
        exit 1
    fi
    
    echo "Using custom Wine command: $WINE_CMD"
    
    # Install Python for Windows
    if [ ! -d "/home/$USER/.wine/drive_c/python" ]; then
        echo "Installing Python for Windows..."
        wget https://www.python.org/ftp/python/3.11.0/python-3.11.0-amd64.exe
        $WINE_CMD python-3.11.0-amd64.exe /quiet InstallAllUsers=1 TargetDir="C:\\python"
        rm python-3.11.0-amd64.exe
    fi
    
fi

# Function to build for specific platform
build_platform() {
    local platform=$1
    echo "Building for $platform..."
    
    if [ "$platform" = "windows" ]; then
        # Use custom Wine to build for Windows
        WINE_PYTHON="$WINE_CMD C:\\python\\python.exe"
        $WINE_PYTHON -m pip install --upgrade pip
        $WINE_PYTHON -m pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests
        $WINE_PYTHON build.py
    else
        # Build for current platform (Linux)
        python3 -m pip install --upgrade pip
        python3 -m pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests
        python3 build.py
    fi
}

# Parse command line arguments
PLATFORM=${1:-"all"}

case $PLATFORM in
    "windows")
        build_platform "windows"
        ;;
    "linux")
        build_platform "linux"
        ;;
    "all")
        echo "Building for all platforms..."
        build_platform "linux"
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            build_platform "windows"
        else
            echo "Cross-compilation for Windows requires Linux system"
        fi
        ;;
    *)
        echo "Usage: $0 [windows|linux|all]"
        echo ""
        echo "Note: This script is configured to use '$WINE_CMD' for Wine."
        echo "If you need to use a different Wine command, edit the WINE_CMD variable in this script."
        exit 1
        ;;
esac

echo "Build process completed!"
