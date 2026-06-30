#!/bin/bash
# TreeChat - Linux/macOS build script
set -e
cd "$(dirname "$0")"

echo "[1/5] Cleaning old build files..."
rm -rf dist build TreeChat.spec

echo "[2/5] Writing VERSION file..."
if [ -n "$TREECHAT_VERSION" ]; then
    echo "$TREECHAT_VERSION" > VERSION
elif tag=$(git describe --tags --exact-match HEAD 2>/dev/null); then
    echo "$tag" > VERSION
elif commit=$(git rev-parse --short HEAD 2>/dev/null); then
    echo "$commit" > VERSION
else
    echo "unknown" > VERSION
fi

echo "[3/5] Generating icon..."
python3 make_icon.py
if [ $? -ne 0 ]; then
    echo "ERROR: icon generation failed."
    rm -f VERSION
    exit 1
fi

echo "[4/5] Running PyInstaller..."
pyinstaller --onefile --name TreeChat --icon icon.ico --add-data "index.html:." --add-data "lib:lib" --add-data "VERSION:." app.py

if [ $? -ne 0 ]; then
    echo "ERROR: build failed."
    rm -f VERSION
    exit 1
fi

echo "[5/5] Cleaning temp files..."
rm -rf build TreeChat.spec icon.ico VERSION

echo ""
echo "Done! Output: dist/TreeChat"
