# Building Orbus Launcher

This guide explains how to compile the Orbus Launcher into executable files for Windows and Linux.

## Prerequisites

### Common Requirements
- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Platform-Specific Requirements

#### Linux
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# For cross-compilation to Windows (optional)
sudo apt install wine
```

#### Windows
- Python 3.8+ from [python.org](https://www.python.org/)
- Git (optional, for cloning the repository)

## Quick Start

### Method 1: Automated Build Scripts

#### For Linux
```bash
# Clone the repository
git clone https://github.com/SuperYosh23/Orbus.git
cd Orbus

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Run the Linux build script
./build-linux.sh
```

#### For Windows
```batch
REM Clone the repository
git clone https://github.com/SuperYosh23/Orbus.git
cd Orbus

REM Create virtual environment
python -m venv .venv
.venv\Scripts\activate

REM Run the Windows build script
build-windows.bat
```

### Method 2: Manual Build

1. **Set up virtual environment:**
   ```bash
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install pyinstaller customtkinter minecraft-launcher-lib pillow requests
   ```

3. **Run the build:**
   ```bash
   python build.py
   ```

## Build Files

### Main Build Script
- `build.py` - Main Python build script that creates executables

### Platform Scripts
- `build-linux.sh` - Linux-specific build script
- `build-windows.bat` - Windows-specific build script
- `build-cross-platform.sh` - Cross-platform build (Linux only)

### Configuration
- `orbus.spec` - PyInstaller configuration file

## Output

After building, you'll find the executables in the `packages/` directory:

### Linux
- `OrbusLauncher-linux-x86_64/`
  - `OrbusLauncher` - Main executable
  - `launch.sh` - Launch script
  - `README.md` - Documentation (if available)

### Windows
- `OrbusLauncher-windows-amd64/`
  - `OrbusLauncher.exe` - Main executable
  - `README.md` - Documentation (if available)

## Cross-Platform Building

### From Linux to Windows
If you're on Linux and want to build for Windows:

#### Standard Wine Setup
1. Install Wine:
   ```bash
   sudo apt install wine
   ```

2. Run the cross-platform build:
   ```bash
   ./build-cross-platform.sh windows
   ```

#### Custom Wine Setup (osu-wine)
If you have a custom Wine setup like osu-wine:

1. Use the Windows-specific Wine build script:
   ```bash
   ./build-windows-wine.sh
   ```

2. Or modify the cross-platform script:
   - Edit `WINE_CMD` in `build-cross-platform.sh`
   - Change from `wine` to your custom command (e.g., `osu-wine --wine`)

3. Run the cross-platform build:
   ```bash
   ./build-cross-platform.sh windows
   ```

4. Or build for all platforms:
   ```bash
   ./build-cross-platform.sh all
   ```

**Note:** The build scripts are configured to detect and use `osu-wine --wine` if standard `wine` is not available.

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError" during build
- Ensure all dependencies are installed in the virtual environment
- Check the `orbus.spec` file for missing hidden imports

#### "Permission denied" on Linux
- Make build scripts executable: `chmod +x *.sh`
- Ensure virtual environment is activated

#### Large executable size
- PyInstaller includes all dependencies
- This is normal for GUI applications
- Typical size: 50-100MB

#### Antivirus false positives
- PyInstaller executables sometimes trigger antivirus software
- This is a known issue with PyInstaller
- Add the executable to antivirus exceptions

### Debug Mode

For debugging build issues, you can modify the `orbus.spec` file:

```python
# Change this line for debug mode
exe = EXE(
    # ... other parameters ...
    console=True,  # Set to True to see console output
    # ... other parameters ...
)
```

## Distribution

The built executables are standalone and don't require Python installation. You can distribute them by:

1. Zipping the platform-specific directory
2. Uploading to GitHub Releases
3. Creating installers (optional)

### Creating a ZIP Archive

```bash
# Linux
cd packages/OrbusLauncher-linux-x86_64/
zip -r OrbusLauncher-linux-x86_64.zip .

# Windows (in PowerShell)
cd packages\OrbusLauncher-windows-amd64\
Compress-Archive -Path * -DestinationPath OrbusLauncher-windows-amd64.zip
```

## Advanced Configuration

### Custom Icons
Place an `icon.png` file in the root directory. The build script will automatically:
- Create `icon.ico` for Windows
- Use the PNG for Linux

### Additional Files
Add files to include in the build by modifying the `build.py` script:

```python
additional_files = ['README.md', 'LICENSE', 'CHANGELOG.md']
```

### Optimizing Size
To reduce executable size, you can:
1. Use UPX compression (enabled by default)
2. Exclude unused modules in the spec file
3. Use `--exclude-module` flags

## Support

If you encounter issues:
1. Check the troubleshooting section
2. Ensure all dependencies are installed
3. Try building in debug mode
4. Check the PyInstaller documentation: https://pyinstaller.readthedocs.io/
