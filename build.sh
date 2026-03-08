#!/bin/bash

# Combined build script for Orbus Launcher
# This script builds for both Linux and Windows (Wine)

set -e

echo "Orbus Launcher Combined Build Script"
echo "====================================="

# Function to run a build script and check its success
run_build() {
    local script_name="$1"
    local platform_name="$2"
    
    echo ""
    echo "========================================"
    echo "Building for $platform_name..."
    echo "========================================"
    
    if [ ! -f "$script_name" ]; then
        echo "Error: $script_name not found!"
        return 1
    fi
    
    if ! bash "$script_name"; then
        echo "Error: $platform_name build failed!"
        return 1
    fi
    
    echo "$platform_name build completed successfully!"
    return 0
}

# Build for Linux
if ! run_build "build-linux.sh" "Linux"; then
    echo "Linux build failed. Aborting."
    exit 1
fi

# Build for Windows (Wine)
if ! run_build "build-windows-wine.sh" "Windows"; then
    echo "Windows build failed. Aborting."
    exit 1
fi

echo ""
echo "========================================"
echo "All builds completed successfully!"
echo "========================================"

# Show final package contents
echo ""
echo "Final packages created:"
if [ -d "packages" ]; then
    for dir in packages/OrbusLauncher-*/; do
        if [ -d "$dir" ]; then
            platform=$(basename "$dir")
            echo "  - $platform"
            ls -la "$dir" | grep -E "\.(exe|sh)$" || echo "    (no executable found)"
        fi
    done
else
    echo "  No packages directory found!"
fi

echo ""
echo "Build process completed!"
