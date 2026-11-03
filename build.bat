@echo off
setlocal
cd /d "%~dp0"
pushd ui
call npm ci
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
popd
if not exist .venv\Scripts\python.exe py -3.11 -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt -r build-requirements.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m unittest discover -s tests
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name CareWare --icon assets\careware.ico --manifest assets\careware.manifest --collect-all customtkinter --collect-all reportlab --collect-all webview --add-data "ui\dist;ui/dist" --hidden-import=psutil main.py
if errorlevel 1 exit /b 1
echo.
echo Build complete: dist\CareWare\CareWare.exe
echo No elevated rights are forced. Windows may request administrator rights only when a technician chooses a privileged action.
pause
