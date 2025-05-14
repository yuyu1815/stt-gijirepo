@echo off
chcp 65001
echo Checking if PyInstaller is installed...

REM PyInstallerがインストールされているか確認
if not exist .venv\Scripts\pyinstaller.exe (
    echo PyInstaller not found. Installing...
    .venv\Scripts\pip.exe install pyinstaller
    if %ERRORLEVEL% neq 0 (
        echo Failed to install PyInstaller.
        exit /b 1
    )
    echo PyInstaller installed successfully.
) else (
    echo PyInstaller is already installed.
)

echo Building executable file...

REM specファイルが存在するか確認
if exist upload_and_transcribe.spec (
    echo Using existing spec file: upload_and_transcribe.spec
    .venv\Scripts\pyinstaller.exe upload_and_transcribe.spec
) else (
    echo Creating new executable file with --onefile option
    .venv\Scripts\pyinstaller.exe --onefile upload_and_transcribe.py
)

if %ERRORLEVEL% neq 0 (
    echo Build failed with error code %ERRORLEVEL%.
    exit /b 1
)

echo.
if exist dist\upload_and_transcribe.exe (
    echo Build completed.
    echo Executable file created successfully: dist\upload_and_transcribe.exe
) else (
    echo Build completed but executable file was not found.
    echo Please check the output for errors.
)

pause