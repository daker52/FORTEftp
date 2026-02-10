@echo off
echo ========================================
echo FORTEftp - Instalace zavislosti
echo ========================================
echo.

echo Kontrola pythonu...
python --version
if errorlevel 1 (
    echo CHYBA: Python neni nainstalovan!
    echo Stahnete si Python z https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Instalace zavislosti...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo CHYBA pri instalaci!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Instalace dokoncena!
echo ========================================
echo.
echo Spusteni aplikace: python FORTEftp.py
echo Vytvoreni .exe: python build_exe.py
echo.
pause
