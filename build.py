#!/usr/bin/env python3
"""
Build script for Orbus Launcher
Creates executables for Windows and Linux platforms
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return False
        print("Success!")
        return True
    except Exception as e:
        print(f"Exception: {e}")
        return False

def create_icon_files():
    """Create icon files for different platforms"""
    print("Creating icon files...")
    
    # Check if we have a source icon
    source_icon = None
    for icon_name in ['icon.png', 'orbus_icon.png']:
        if os.path.exists(icon_name):
            source_icon = icon_name
            break
    
    if not source_icon:
        print("No source icon found, skipping icon creation")
        return
    
    try:
        from PIL import Image
        
        # Create Windows ICO file
        if os.path.exists(source_icon):
            img = Image.open(source_icon)
            
            # Create different sizes for ICO
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save('icon.ico', format='ICO', sizes=sizes)
            print("Created icon.ico for Windows")
            
    except ImportError:
        print("PIL not available, skipping icon creation")
    except Exception as e:
        print(f"Error creating icons: {e}")

def build_executable():
    """Build the executable using PyInstaller"""
    print("Building executable...")
    
    # Create icon files first
    create_icon_files()
    
    # Build using the spec file
    spec_file = "orbus.spec"
    if not os.path.exists(spec_file):
        print(f"Spec file {spec_file} not found, using default build")
        cmd = f"{sys.executable} -m PyInstaller --onefile --windowed --name OrbusLauncher launcher.py"
    else:
        cmd = f"{sys.executable} -m PyInstaller {spec_file}"
    
    if not run_command(cmd):
        print("Build failed!")
        return False
    
    return True

def create_package():
    """Create a distributable package"""
    print("Creating package...")
    
    # Create dist directory
    dist_dir = Path("dist")
    package_dir = Path("packages")
    package_dir.mkdir(exist_ok=True)
    
    # Determine platform
    system = platform.system().lower()
    architecture = platform.machine().lower()
    
    if system == "windows":
        platform_name = "windows"
        executable_name = "OrbusLauncher.exe"
    else:
        platform_name = "linux"
        executable_name = "OrbusLauncher"
    
    # Find the executable
    exe_path = dist_dir / executable_name
    if not exe_path.exists():
        print(f"Executable not found: {exe_path}")
        return False
    
    # Create platform-specific package
    package_name = f"OrbusLauncher-{platform_name}-{architecture}"
    package_path = package_dir / package_name
    
    if package_path.exists():
        shutil.rmtree(package_path)
    
    package_path.mkdir(parents=True)
    
    # Copy executable
    shutil.copy2(exe_path, package_path / executable_name)
    
    # Copy additional files
    additional_files = ['README.md', 'LICENSE']
    for file in additional_files:
        if os.path.exists(file):
            shutil.copy2(file, package_path / file)
    
    # Create a simple launch script for Linux
    if system == "linux":
        launch_script = package_path / "launch.sh"
        with open(launch_script, 'w') as f:
            f.write("""#!/bin/bash
# Orbus Launcher Launch Script

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Launch the application
"$DIR/OrbusLauncher" "$@"
""")
        launch_script.chmod(0o755)
        print(f"Created launch script: {launch_script}")
    
    print(f"Package created: {package_path}")
    return True

def main():
    """Main build function"""
    print("Orbus Launcher Build Script")
    print("=" * 40)
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Warning: Not running in a virtual environment")
    
    # Install dependencies if needed
    print("Checking dependencies...")
    dependencies = ['pyinstaller', 'customtkinter', 'minecraft-launcher-lib', 'pillow', 'requests']
    
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
        except ImportError:
            print(f"Installing {dep}...")
            run_command(f"{sys.executable} -m pip install {dep}")
    
    # Build the executable
    if not build_executable():
        print("Build failed!")
        sys.exit(1)
    
    # Create package
    if not create_package():
        print("Package creation failed!")
        sys.exit(1)
    
    print("\nBuild completed successfully!")
    print("Check the 'packages' directory for the output.")

if __name__ == "__main__":
    main()
