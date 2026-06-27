@echo off
cd /d "%~dp0"

echo [1/3] Cleaning old build files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec

echo [2/3] Running PyInstaller...
pyinstaller --onefile --name TreeChat --add-data "index.html;." --add-data "lib;lib" app.py

if errorlevel 1 (
    echo ERROR: build failed.
    pause
    exit /b 1
)

echo [3/3] Cleaning temp files...
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec

echo.
echo Done^^!  Output: dist\TreeChat.exe
pause
