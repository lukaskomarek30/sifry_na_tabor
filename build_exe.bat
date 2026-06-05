@echo off
chcp 65001 >nul
setlocal

set APP_NAME=Sifrator_Mraveniste
set MAIN_FILE=main.py
set ICON_PNG=icons\logo.png
set ICON_ICO=icons\app_icon.ico

echo.
echo === Instalace / aktualizace balicku ===
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller pillow

echo.
echo === Vytvoreni ikony %ICON_ICO% z %ICON_PNG% ===
if not exist "%ICON_PNG%" (
    echo CHYBA: Nenalezeno %ICON_PNG%.
    pause
    exit /b 1
)

python -c "from PIL import Image; img=Image.open(r'%ICON_PNG%').convert('RGBA'); bbox=img.getchannel('A').getbbox(); img=img.crop(bbox) if bbox else img; s=max(img.size); canvas=Image.new('RGBA',(s,s),(0,0,0,0)); canvas.paste(img,((s-img.width)//2,(s-img.height)//2),img); canvas.save(r'%ICON_ICO%',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo.
echo === Cisteni stareho buildu ===
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q "%APP_NAME%.spec" 2>nul

echo.
echo === Build EXE ===
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --icon "%ICON_ICO%" ^
  "%MAIN_FILE%"

echo.
if exist "dist\%APP_NAME%.exe" (
    echo HOTOVO:
    echo dist\%APP_NAME%.exe
) else (
    echo CHYBA: EXE nebylo vytvoreno.
)

pause
endlocal
