@echo off
cd /d "%~dp0"

echo [1/4] Cleaning old build files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec

echo [2/4] Generating icon...
python make_icon.py
if errorlevel 1 (
    echo ERROR: icon generation failed.
    pause
    exit /b 1
)

echo [3/4] Running PyInstaller...
pyinstaller --onefile --name TreeChat --icon icon.ico --add-data "index.html;." --add-data "lib;lib" app.py

if errorlevel 1 (
    echo ERROR: build failed.
    pause
    exit /b 1
)

echo [4/4] Cleaning temp files...
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec
if exist icon.ico del /q icon.ico

echo.
echo Done^^!  Output: dist\TreeChat.exe
pause
