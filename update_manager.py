"""Správa aktualizací aplikace Šifrátor Mraveniště.

Modul řeší kompletní aktualizační proces aplikace:
- kontrolu dostupné verze přes update.json,
- výběr správného instalačního balíčku podle platformy,
- stažení a kontrolu ZIP balíčku,
- instalaci aktualizace se zobrazením průběhu.

Podporované platformy:
- Windows x64,
- macOS Apple Silicon (arm64),
- macOS Intel (x64).

Preferovaný formát update.json:
{
  "version": "0.0.3",
  "notes": "...",
  "platforms": {
    "windows-x64": {"package_url": "...", "sha256": "..."},
    "macos-arm64": {"package_url": "...", "sha256": "..."},
    "macos-x64": {"package_url": "...", "sha256": "..."}
  }
}

Z důvodu zpětné kompatibility je podporovaný také starší formát,
kde jsou hodnoty package_url a sha256 uložené přímo v kořeni JSONu.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from typing import Callable


UPDATE_JSON_URL = "https://raw.githubusercontent.com/lukaskomarek30/sifry_na_tabor/main/update.json"

ProgressCallback = Callable[[int, str], None]


class UpdateError(RuntimeError):
    pass


class UpdateCancelled(UpdateError):
    pass


def parse_version(version: str) -> tuple[int, ...]:
    """Normalizuje textovou verzi do číselné podoby vhodné pro porovnání."""
    value = (version or "").strip().lower().replace("v", "")
    parts: list[int] = []
    for part in value.split("."):
        number = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(number or "0"))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except Exception:
        return False


def get_platform_key() -> str:
    """Vrátí identifikátor platformy používaný v update.json."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "windows-x64"

    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "macos-arm64"
        return "macos-x64"

    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x64"
        if machine in ("arm64", "aarch64"):
            return "linux-arm64"
        return "linux"

    return system or "unknown"


def get_app_dir() -> str:
    """Vrátí pracovní složku aktuálně spuštěné aplikace.

    U sestavené aplikace se používá cesta ke spuštěnému binárnímu souboru.
    Při spuštění ze zdrojového kódu se používá složka tohoto modulu.
    Cílová cesta pro samotnou aktualizaci se řeší samostatně pomocí get_update_target_path().
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_current_run_path() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def get_macos_app_bundle_path() -> str:
    """Vrátí kořenový adresář macOS .app balíčku, pokud je aplikace spuštěná z bundle."""
    run_path = os.path.abspath(get_current_run_path())
    parts = run_path.split(os.sep)

    for index, part in enumerate(parts):
        if part.endswith(".app"):
            return os.sep.join(parts[: index + 1]) or os.sep

    return ""


def get_update_target_path() -> str:
    """Vrátí cílovou cestu, do které se má nainstalovat nová verze aplikace."""
    if platform.system().lower() == "darwin":
        app_bundle = get_macos_app_bundle_path()
        if app_bundle:
            return app_bundle

    return get_app_dir()


def _emit_progress(progress_callback: ProgressCallback | None, value: int, message: str) -> None:
    if progress_callback is not None:
        progress_callback(max(0, min(100, int(value))), message)


def download_text(url: str, timeout: int = 6) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def download_file(url: str, output_path: str, timeout: int = 120, progress_callback: ProgressCallback | None = None) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        total_header = response.headers.get("Content-Length")
        total_size = int(total_header) if total_header and total_header.isdigit() else 0
        downloaded = 0
        chunk_size = 1024 * 256

        with open(output_path, "wb") as file:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break

                file.write(chunk)
                downloaded += len(chunk)

                if total_size > 0:
                    percent = int(downloaded * 100 / total_size)
                    value = 5 + int(percent * 0.65)
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    _emit_progress(progress_callback, value, f"Stahuji aktualizaci... {mb_done:.1f} / {mb_total:.1f} MB")
                else:
                    mb_done = downloaded / (1024 * 1024)
                    _emit_progress(progress_callback, 25, f"Stahuji aktualizaci... {mb_done:.1f} MB")


def sha256_file(path: str, progress_callback: ProgressCallback | None = None) -> str:
    sha = hashlib.sha256()
    total_size = os.path.getsize(path)
    done = 0

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
            done += len(chunk)
            if total_size > 0:
                percent = int(done * 100 / total_size)
                value = 70 + int(percent * 0.10)
                _emit_progress(progress_callback, value, "Ověřuji stažený balíček...")

    return sha.hexdigest().lower()


def _select_platform_data(update_json: dict) -> dict | None:
    """Vybere metadata aktualizačního balíčku odpovídající aktuální platformě.

    Funkce vrací kopii vstupního JSONu rozšířenou o package_url, sha256,
    file_name a platform_key. Navazující část aktualizačního procesu tak může
    pracovat se sjednocenou strukturou bez ohledu na původní formát update.json.
    """
    if not isinstance(update_json, dict):
        return None

    remote_version = str(update_json.get("version", "")).strip()
    if not remote_version:
        return None

    platform_key = get_platform_key()
    platforms = update_json.get("platforms")

    # Preferovaný formát s oddělenými balíčky pro jednotlivé platformy.
    if isinstance(platforms, dict):
        selected = platforms.get(platform_key)

        # Platforma musí mít v update.json vlastní konfigurační blok.
        # Tím se zabrání instalaci nesprávného balíčku pro jinou architekturu.
        if not isinstance(selected, dict):
            return None

        package_url = str(selected.get("package_url", "")).strip()
        if not package_url:
            return None

        result = dict(update_json)
        result["platform_key"] = platform_key
        result["package_url"] = package_url
        result["sha256"] = str(selected.get("sha256", "")).strip().lower()
        result["file_name"] = str(selected.get("file_name", "")).strip()
        return result

    # Starší formát se zpracuje kvůli zachování kompatibility s původními releasy.
    package_url = str(update_json.get("package_url", "")).strip()
    if package_url:
        result = dict(update_json)
        result["platform_key"] = platform_key
        result["sha256"] = str(result.get("sha256", "")).strip().lower()
        return result

    return None


def check_for_update(current_version: str) -> dict | None:
    """Zkontroluje dostupnost nové verze a vrátí metadata aktualizace pro aktuální platformu."""
    try:
        raw_json = download_text(UPDATE_JSON_URL)
        data = json.loads(raw_json)

        remote_version = str(data.get("version", "")).strip()
        if not remote_version:
            return None

        if not is_newer_version(remote_version, current_version):
            return None

        selected_data = _select_platform_data(data)
        if not selected_data:
            return None

        return selected_data
    except Exception:
        return None


def download_update_package(update_data: dict, progress_callback: ProgressCallback | None = None) -> str:
    package_url = str(update_data.get("package_url", "")).strip()
    if not package_url:
        raise UpdateError("V update.json chybí package_url pro tuto platformu.")

    expected_sha256 = str(update_data.get("sha256", "")).strip().lower()

    temp_zip = os.path.join(tempfile.gettempdir(), f"sifrator_update_package_{get_platform_key()}.zip")
    if os.path.exists(temp_zip):
        os.remove(temp_zip)

    _emit_progress(progress_callback, 3, "Připravuji stažení aktualizace...")
    download_file(package_url, temp_zip, progress_callback=progress_callback)

    _emit_progress(progress_callback, 70, "Kontroluji ZIP balíček...")
    if not zipfile.is_zipfile(temp_zip):
        raise UpdateError("Stažený soubor není ZIP balíček aktualizace.")

    if expected_sha256:
        real_sha256 = sha256_file(temp_zip, progress_callback=progress_callback)
        if real_sha256 != expected_sha256:
            raise UpdateError(
                "Stažený balíček nesedí s kontrolním SHA256 hashem.\n"
                "Aktualizace byla zastavena, aby nedošlo k poškození aplikace."
            )
    else:
        _emit_progress(progress_callback, 80, "SHA256 není vyplněný, pokračuji bez kontroly...")

    return temp_zip


def _find_payload_dir(extract_dir: str) -> str:
    """Vyhledá adresář s obsahem aplikace uvnitř rozbaleného aktualizačního balíčku.

    Podporuje balíček se soubory přímo v kořeni i balíček zabalený do jedné hlavní složky.
    """
    items = [os.path.join(extract_dir, name) for name in os.listdir(extract_dir)]
    dirs = [path for path in items if os.path.isdir(path)]
    files = [path for path in items if os.path.isfile(path)]

    if files:
        return extract_dir

    if len(dirs) == 1:
        return dirs[0]

    return extract_dir


def _find_macos_app_payload(extract_dir: str, target_path: str) -> str:
    """Vyhledá macOS .app bundle v rozbaleném aktualizačním balíčku."""
    target_name = os.path.basename(target_path.rstrip(os.sep))

    app_dirs: list[str] = []
    for root, dirs, _files in os.walk(extract_dir):
        for dirname in dirs:
            if dirname.endswith(".app"):
                app_dirs.append(os.path.join(root, dirname))

    for app_dir in app_dirs:
        if os.path.basename(app_dir) == target_name:
            return app_dir

    if app_dirs:
        return app_dirs[0]

    return _find_payload_dir(extract_dir)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _extract_zip_with_progress(zip_path: str, extract_dir: str, progress_callback: ProgressCallback | None = None) -> None:
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        members = zip_file.infolist()
        total = max(1, len(members))

        for index, member in enumerate(members, start=1):
            zip_file.extract(member, extract_dir)
            percent = int(index * 100 / total)
            value = 80 + int(percent * 0.15)
            _emit_progress(progress_callback, value, f"Rozbaluji aktualizaci... {index} / {total}")


def _install_update_windows(zip_path: str, target_dir: str, run_file_name: str, progress_callback: ProgressCallback | None = None) -> None:
    temp_root = tempfile.gettempdir()
    temp_extract_dir = os.path.join(temp_root, "sifrator_update_extract")
    ps1_path = os.path.join(temp_root, "sifrator_update.ps1")

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    _emit_progress(progress_callback, 80, "Rozbaluji aktualizaci...")
    _extract_zip_with_progress(zip_path, temp_extract_dir, progress_callback=progress_callback)

    payload_dir = _find_payload_dir(temp_extract_dir)

    current_pid = os.getpid()
    run_path_after_update = os.path.join(target_dir, run_file_name)
    backup_dir = os.path.join(temp_root, f"sifrator_backup_{int(time.time())}")

    source_q = _ps_quote(payload_dir)
    target_q = _ps_quote(target_dir)
    run_q = _ps_quote(run_path_after_update)
    backup_q = _ps_quote(backup_dir)

    _emit_progress(progress_callback, 96, "Připravuji restart aplikace...")

    powershell_script = f"""
$ErrorActionPreference = "Stop"

$pidToWait = {current_pid}
$source = {source_q}
$target = {target_q}
$runFile = {run_q}
$backup = {backup_q}

$host.UI.RawUI.WindowTitle = "Šifrátor Mraveniště - instalace aktualizace"
Write-Host "Instaluji aktualizaci Šifrátoru Mraveniště..."
Write-Host "Nezavírej toto okno."
Write-Host ""

try {{
    Wait-Process -Id $pidToWait -Timeout 30
}} catch {{
    Start-Sleep -Seconds 2
}}

if (!(Test-Path $source)) {{
    throw "Zdroj aktualizace neexistuje: $source"
}}

if (!(Test-Path $target)) {{
    throw "Cílová složka aplikace neexistuje: $target"
}}

Write-Progress -Activity "Aktualizace Šifrátoru" -Status "Vytvářím zálohu..." -PercentComplete 20
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -Path (Join-Path $target '*') -Destination $backup -Recurse -Force -ErrorAction SilentlyContinue

Write-Progress -Activity "Aktualizace Šifrátoru" -Status "Kopíruji novou verzi..." -PercentComplete 50

$robocopyArgs = @(
    $source,
    $target,
    "/MIR",
    "/R:3",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS"
)

& robocopy @robocopyArgs
$robocopyCode = $LASTEXITCODE

if ($robocopyCode -ge 8) {{
    throw "Robocopy aktualizace selhala. Kód: $robocopyCode"
}}

Write-Progress -Activity "Aktualizace Šifrátoru" -Status "Spouštím novou verzi..." -PercentComplete 95
Start-Sleep -Milliseconds 800

if (Test-Path $runFile) {{
    Start-Process $runFile
}} else {{
    Start-Process explorer.exe $target
}}

Write-Progress -Activity "Aktualizace Šifrátoru" -Completed
"""

    with open(ps1_path, "w", encoding="utf-8") as file:
        file.write(powershell_script)

    _emit_progress(progress_callback, 100, "Aktualizace je připravená. Aplikace se restartuje...")
    time.sleep(0.4)

    subprocess.Popen([
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ps1_path,
    ], shell=False)

    sys.exit(0)


def _install_update_macos(zip_path: str, target_path: str, progress_callback: ProgressCallback | None = None) -> None:
    temp_root = tempfile.gettempdir()
    temp_extract_dir = os.path.join(temp_root, "sifrator_update_extract")
    sh_path = os.path.join(temp_root, "sifrator_update.sh")

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    _emit_progress(progress_callback, 80, "Rozbaluji aktualizaci...")
    _extract_zip_with_progress(zip_path, temp_extract_dir, progress_callback=progress_callback)

    if target_path.endswith(".app"):
        payload_path = _find_macos_app_payload(temp_extract_dir, target_path)
    else:
        payload_path = _find_payload_dir(temp_extract_dir)

    current_pid = os.getpid()
    backup_path = os.path.join(temp_root, f"sifrator_backup_{int(time.time())}")

    source_q = _sh_quote(payload_path)
    target_q = _sh_quote(target_path)
    backup_q = _sh_quote(backup_path)

    _emit_progress(progress_callback, 96, "Připravuji restart aplikace...")

    shell_script = f"""#!/bin/sh
set -eu

PID_TO_WAIT={current_pid}
SOURCE={source_q}
TARGET={target_q}
BACKUP={backup_q}

echo "Instaluji aktualizaci Šifrátoru Mraveniště..."
echo "Nezavírej toto okno."

while kill -0 "$PID_TO_WAIT" 2>/dev/null; do
    sleep 1
done

if [ ! -e "$SOURCE" ]; then
    echo "Zdroj aktualizace neexistuje: $SOURCE"
    exit 1
fi

if [ ! -e "$TARGET" ]; then
    echo "Cílová aplikace neexistuje: $TARGET"
    exit 1
fi

mkdir -p "$BACKUP"

if [ -d "$TARGET" ]; then
    /usr/bin/ditto "$TARGET" "$BACKUP/$(basename "$TARGET")" || true
else
    cp -p "$TARGET" "$BACKUP/" || true
fi

if [ -d "$SOURCE" ] && [ -d "$TARGET" ]; then
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$SOURCE"/ "$TARGET"/
    else
        rm -rf "$TARGET"
        /usr/bin/ditto "$SOURCE" "$TARGET"
    fi
else
    cp -p "$SOURCE" "$TARGET"
fi

sleep 1

case "$TARGET" in
    *.app)
        /usr/bin/open "$TARGET"
        ;;
    *)
        /usr/bin/open "$(dirname "$TARGET")"
        ;;
esac
"""

    with open(sh_path, "w", encoding="utf-8") as file:
        file.write(shell_script)

    try:
        os.chmod(sh_path, 0o755)
    except Exception:
        pass

    _emit_progress(progress_callback, 100, "Aktualizace je připravená. Aplikace se restartuje...")
    time.sleep(0.4)

    subprocess.Popen(["/bin/sh", sh_path], shell=False)
    sys.exit(0)


def install_update_package(zip_path: str, target_path: str, run_file_name: str = "", progress_callback: ProgressCallback | None = None) -> None:
    system = platform.system().lower()

    if system == "windows":
        _install_update_windows(zip_path, target_path, run_file_name, progress_callback=progress_callback)
        return

    if system == "darwin":
        _install_update_macos(zip_path, target_path, progress_callback=progress_callback)
        return

    raise UpdateError(f"Aktualizace pro tento systém zatím není podporovaná: {system}")


class _QtProgress:
    """Jednoduché modální okno zobrazující průběh aktualizace."""

    def __init__(self) -> None:
        self.dialog = None
        self.cancelled = False

        try:
            from PySide6.QtWidgets import QApplication, QProgressDialog
            from PySide6.QtCore import Qt

            self.QApplication = QApplication
            self.dialog = QProgressDialog("Připravuji aktualizaci...", "Zrušit", 0, 100)
            self.dialog.setWindowTitle("Aktualizace Šifrátoru Mraveniště")
            self.dialog.setWindowModality(Qt.ApplicationModal)
            self.dialog.setMinimumDuration(0)
            self.dialog.setAutoClose(False)
            self.dialog.setAutoReset(False)
            self.dialog.setValue(0)
            self.dialog.setMinimumWidth(460)
            self.dialog.canceled.connect(self._cancel)
            self.dialog.show()
            QApplication.processEvents()
        except Exception:
            self.QApplication = None
            self.dialog = None

    def _cancel(self) -> None:
        self.cancelled = True

    def update(self, value: int, message: str) -> None:
        if self.dialog is None:
            print(f"Aktualizace {value}% - {message}")
            return

        self.dialog.setValue(max(0, min(100, int(value))))
        self.dialog.setLabelText(message)
        self.QApplication.processEvents()

        if self.cancelled:
            raise UpdateCancelled("Aktualizace byla zrušena uživatelem.")

    def close(self) -> None:
        if self.dialog is not None:
            self.dialog.close()
            self.QApplication.processEvents()


def download_and_install_update(update_data: dict) -> None:
    """Stáhne a nainstaluje aktualizační balíček se zobrazením průběhu.

    Veřejné rozhraní funkce zůstává kompatibilní s voláním z main.py:
        update_manager.download_and_install_update(update_data)
    """
    progress = _QtProgress()

    try:
        target_path = get_update_target_path()
        current_run_path = get_current_run_path()
        run_file_name = os.path.basename(current_run_path)

        progress.update(1, "Připravuji aktualizaci...")
        zip_path = download_update_package(update_data, progress_callback=progress.update)
        install_update_package(zip_path, target_path, run_file_name, progress_callback=progress.update)
    except UpdateCancelled:
        progress.close()
        raise
    except Exception:
        progress.close()
        raise
