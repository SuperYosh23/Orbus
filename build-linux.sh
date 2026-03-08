#!/bin/bash

# Linux build script for Orbus Launcher

echo "Orbus Launcher Linux Build Script"
echo "=================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "Warning: Not running in a virtual environment"
    echo "It's recommended to use a virtual environment"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests

# Run the build script
echo "Building executable..."
python3 build.py

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo "Build completed successfully!"
echo "Check the 'packages' directory for the output."
