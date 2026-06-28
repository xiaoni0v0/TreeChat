#!/bin/bash
# TreeChat - Linux/macOS build script
set -e
cd "$(dirname "$0")"

echo "[1/4] Cleaning old build files..."
rm -rf dist build TreeChat.spec

echo "[2/4] Generating icon..."
python3 make_icon.py
if [ $? -ne 0 ]; then
    echo "ERROR: icon generation failed."
    exit 1
fi

echo "[3/4] Running PyInstaller..."
pyinstaller --onefile --name TreeChat --icon icon.ico --add-data "index.html:." --add-data "lib:lib" app.py

if [ $? -ne 0 ]; then
    echo "ERROR: build failed."
    exit 1
fi

echo "[4/4] Cleaning temp files..."
rm -rf build TreeChat.spec icon.ico

echo ""
echo "Done! Output: dist/TreeChat"
