@'
@echo off
setlocal EnableExtensions

REM ============================================================
REM Build release ZIP for Sifrator Mraveniste
REM Run this from project folder:
REM C:\Users\komarek\Desktop\Sifry
REM ============================================================

set "VERSION=0.0.1"
set "APP_EXE=dist\Sifrator_Mraveniste.exe"
set "RELEASE_DIR=release_%VERSION%"
set "ZIP_NAME=Sifrator_Mraveniste_%VERSION%.zip"

echo.
echo === Checking EXE ===
if not exist "%APP_EXE%" (
    echo ERROR: File not found: %APP_EXE%
    echo First run build_exe.bat.
    pause
    exit /b 1
)

echo.
echo === Cleaning old release files ===
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
if exist "%ZIP_NAME%" del /q "%ZIP_NAME%"

mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\icons"

echo.
echo === Copying EXE and icons ===
copy "%APP_EXE%" "%RELEASE_DIR%\Sifrator_Mraveniste.exe" >nul
xcopy "icons" "%RELEASE_DIR%\icons" /E /I /Y >nul

echo.
echo === Creating ZIP package ===
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '.\%RELEASE_DIR%\*' -DestinationPath '.\%ZIP_NAME%' -Force"

echo.
echo === SHA256 hash ===
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-FileHash '.\%ZIP_NAME%' -Algorithm SHA256"

echo.
echo DONE:
echo %ZIP_NAME%
echo.
echo Upload this ZIP to GitHub Release v%VERSION%.
echo Copy SHA256 hash into update.json.
echo.

pause
endlocal
'@ | Set-Content -Path ".\build_release_zip.bat" -Encoding ASCII