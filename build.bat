@echo off
chcp 65001
echo Checking if PyInstaller is installed...
if not exist .venv\Scripts\pyinstaller.exe (
    echo PyInstaller not found. Installing...
    .venv\Scripts\pip.exe install pyinstaller
    echo PyInstaller installed.
)
echo Building executable file...
.venv\Scripts\pyinstaller.exe --onefile upload_and_transcribe.spec
echo Build completed.
if exist dist\upload_and_transcribe.exe (
    echo Executable file created successfully: dist\upload_and_transcribe.exe
) else (
    echo Failed to create executable file.
)
pause
