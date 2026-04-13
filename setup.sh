#!/bin/bash
# Orbus Launcher Setup Script
# Sets up Python virtual environment and installs dependencies

set -e

echo "==================================="
echo "Orbus Launcher Setup"
echo "==================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

echo "Python version:"
python3 --version
echo ""

# Create backend virtual environment if it doesn't exist
if [ ! -d "backend/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv backend/venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Installing Python dependencies..."

# Detect platform and use correct activation method
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    backend/venv/Scripts/pip install minecraft-launcher-lib requests
else
    # Linux/macOS
    backend/venv/bin/pip install minecraft-launcher-lib requests
fi

echo "✓ Dependencies installed"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "WARNING: Node.js is not installed"
    echo "Please install Node.js 18 or higher to run the Electron frontend"
    echo "Visit: https://nodejs.org/"
else
    echo "Node.js version:"
    node --version
    echo ""
    
    # Install npm dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        echo "Installing Node.js dependencies..."
        npm install
        echo "✓ Node.js dependencies installed"
    else
        echo "✓ Node.js dependencies already installed"
    fi
fi

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "To start the launcher, run:"
echo "  npm run dev     # Development mode"
echo "  npm start       # Production mode"
echo ""
