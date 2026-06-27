@echo off
setlocal

cd /d "%~dp0"

set "CACHE_DIR=%~dp0cache\key_cache"

if not exist "%CACHE_DIR%" (
    echo Vytvarim slozku cache: "%CACHE_DIR%"
    mkdir "%CACHE_DIR%"
)

where python >nul 2>nul
if "%ERRORLEVEL%"=="0" (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if "%ERRORLEVEL%"=="0" (
        set "PYTHON_CMD=py -3"
    ) else (
        echo Chyba: Python nebyl nalezen v PATH.
        echo Nainstaluj Python, nebo spust prikaz rucne v prostredi, kde Python funguje.
        pause
        exit /b 1
    )
)

echo Spoustim predgenerovani cache klicu...
echo Cilova slozka: "%CACHE_DIR%"
echo.

%PYTHON_CMD% main.py --prebuild-key-cache "%CACHE_DIR%"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Predgenerovani cache skoncilo chybou: %EXIT_CODE%
    pause
    exit /b %EXIT_CODE%
)

echo Hotovo.
pause
exit /b 0
