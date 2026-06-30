@echo off
cd /d "%~dp0"

echo [1/5] Cleaning old build files...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec

echo [2/5] Writing VERSION file...
if defined TREECHAT_VERSION (
    echo %TREECHAT_VERSION%> VERSION
) else (
    for /f "delims=" %%i in ('git describe --tags --exact-match HEAD 2^>nul') do set GIT_TAG=%%i
    if defined GIT_TAG (
        echo %GIT_TAG%> VERSION
    ) else (
        for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set GIT_HASH=%%i
        if defined GIT_HASH (
            echo %GIT_HASH%> VERSION
        ) else (
            echo unknown> VERSION
        )
    )
)

echo [3/5] Generating icon...
python make_icon.py
if errorlevel 1 (
    echo ERROR: icon generation failed.
    if exist VERSION del /q VERSION
    pause
    exit /b 1
)

echo [4/5] Running PyInstaller...
pyinstaller --onefile --name TreeChat --icon icon.ico --add-data "index.html;." --add-data "lib;lib" --add-data "VERSION;." app.py

if errorlevel 1 (
    echo ERROR: build failed.
    if exist VERSION del /q VERSION
    pause
    exit /b 1
)

echo [5/5] Cleaning temp files...
if exist build rmdir /s /q build
if exist TreeChat.spec del /q TreeChat.spec
if exist icon.ico del /q icon.ico
if exist VERSION del /q VERSION

echo.
echo Done^!  Output: dist\TreeChat.exe
pause
