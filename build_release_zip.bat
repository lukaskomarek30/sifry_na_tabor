@echo off
chcp 65001 >nul
setlocal

set VERSION=0.0.1
set APP_EXE=dist\Sifrator_Mraveniste.exe
set RELEASE_DIR=release_%VERSION%
set ZIP_NAME=Sifrator_Mraveniste_%VERSION%.zip

echo.
echo === Kontrola EXE ===
if not exist "%APP_EXE%" (
    echo CHYBA: Nenalezen %APP_EXE%.
    echo Nejdřív vytvoř EXE přes PyInstaller.
    pause
    exit /b 1
)

echo.
echo === Čištění staré release složky ===
rmdir /s /q "%RELEASE_DIR%" 2>nul
del /q "%ZIP_NAME%" 2>nul

mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\icons"

echo.
echo === Kopírování EXE a icons ===
copy "%APP_EXE%" "%RELEASE_DIR%\Sifrator_Mraveniste.exe" >nul
xcopy "icons" "%RELEASE_DIR%\icons" /E /I /Y >nul

echo.
echo === Vytvoření ZIP balíčku ===
powershell -Command "Compress-Archive -Path '.\%RELEASE_DIR%\*' -DestinationPath '.\%ZIP_NAME%' -Force"

echo.
echo === SHA256 hash ===
powershell -Command "Get-FileHash '.\%ZIP_NAME%' -Algorithm SHA256"

echo.
echo HOTOVO:
echo %ZIP_NAME%
echo Tento ZIP nahraj do GitHub Release v%VERSION%.
echo SHA256 zkopíruj do update.json.
pause
endlocal
