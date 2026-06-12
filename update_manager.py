"""Jednoduchý správce aktualizací pro Šifrátor Mraveniště.

Princip:
1) Aplikace při startu stáhne update.json z GitHubu.
2) Pokud je v update.json vyšší verze než APP_VERSION v main.py, vrátí informace o aktualizaci.
3) Po potvrzení uživatelem stáhne ZIP balíček z GitHub Releases.
4) Ověří SHA256, pokud je v update.json vyplněné.
5) Spustí pomocný PowerShell skript, zavře aplikaci, zrcadlově přepíše celou složku aplikace a spustí novou verzi.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile


# Tady aplikace hledá informaci o nové verzi.
# Tento soubor update.json musí být v repozitáři na GitHubu.
UPDATE_JSON_URL = "https://raw.githubusercontent.com/lukaskomarek30/sifry_na_tabor/main/update.json"


class UpdateError(RuntimeError):
    pass


def parse_version(version: str) -> tuple[int, ...]:
    """Převede verzi typu 1.2.3 nebo v1.2.3 na tuple pro porovnání."""
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


def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_current_run_path() -> str:
    """Vrátí cestu k EXE, nebo k main.py při spuštění z Pythonu."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def download_text(url: str, timeout: int = 6) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def download_file(url: str, output_path: str, timeout: int = 120) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with open(output_path, "wb") as file:
            shutil.copyfileobj(response, file)


def sha256_file(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().lower()


def check_for_update(current_version: str) -> dict | None:
    """Vrátí data aktualizace, pokud existuje novější verze. Jinak vrátí None.

    Při výpadku internetu nebo chybě GitHubu se nic neukazuje a aplikace normálně pokračuje.
    """
    try:
        raw_json = download_text(UPDATE_JSON_URL)
        data = json.loads(raw_json)

        remote_version = str(data.get("version", "")).strip()
        package_url = str(data.get("package_url", "")).strip()

        if not remote_version or not package_url:
            return None

        if not is_newer_version(remote_version, current_version):
            return None

        return data
    except Exception:
        return None


def download_update_package(update_data: dict) -> str:
    package_url = str(update_data.get("package_url", "")).strip()
    if not package_url:
        raise UpdateError("V update.json chybí package_url.")

    expected_sha256 = str(update_data.get("sha256", "")).strip().lower()

    temp_zip = os.path.join(tempfile.gettempdir(), "sifrator_update_package.zip")
    if os.path.exists(temp_zip):
        os.remove(temp_zip)

    download_file(package_url, temp_zip)

    if not zipfile.is_zipfile(temp_zip):
        raise UpdateError("Stažený soubor není ZIP balíček aktualizace.")

    if expected_sha256:
        real_sha256 = sha256_file(temp_zip)
        if real_sha256 != expected_sha256:
            raise UpdateError(
                "Stažený balíček nesedí s kontrolním SHA256 hashem.\n"
                "Aktualizace byla zastavena, aby nedošlo k poškození aplikace."
            )

    return temp_zip


def _find_payload_dir(extract_dir: str) -> str:
    """Najde skutečnou složku s aplikací uvnitř rozbaleného ZIPu.

    Podporuje ZIP, kde jsou soubory rovnou v kořeni, i ZIP se složkou release_1.2.3/...
    """
    items = [os.path.join(extract_dir, name) for name in os.listdir(extract_dir)]
    dirs = [path for path in items if os.path.isdir(path)]
    files = [path for path in items if os.path.isfile(path)]

    if files:
        return extract_dir

    if len(dirs) == 1:
        return dirs[0]

    return extract_dir


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def install_update_package(zip_path: str, app_dir: str, run_file_name: str) -> None:
    temp_root = tempfile.gettempdir()
    temp_extract_dir = os.path.join(temp_root, "sifrator_update_extract")
    ps1_path = os.path.join(temp_root, "sifrator_update.ps1")

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(temp_extract_dir)

    payload_dir = _find_payload_dir(temp_extract_dir)

    # Pomocný skript se spustí mimo běžící aplikaci, počká na její ukončení,
    # překopíruje nové soubory a spustí aktualizovanou verzi.
    current_pid = os.getpid()
    run_path_after_update = os.path.join(app_dir, run_file_name)
    backup_dir = os.path.join(temp_root, f"sifrator_backup_{int(time.time())}")

    source_q = _ps_quote(payload_dir)
    target_q = _ps_quote(app_dir)
    run_q = _ps_quote(run_path_after_update)
    backup_q = _ps_quote(backup_dir)

    powershell_script = f"""
$ErrorActionPreference = "Stop"

$pidToWait = {current_pid}
$source = {source_q}
$target = {target_q}
$runFile = {run_q}
$backup = {backup_q}

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

# Záloha před přepsáním. Když se něco pokazí, dá se ručně obnovit z TEMP složky.
New-Item -ItemType Directory -Path $backup -Force | Out-Null
Copy-Item -Path (Join-Path $target '*') -Destination $backup -Recurse -Force -ErrorAction SilentlyContinue

# Přesné zrcadlení nové verze do instalační složky.
# DŮLEŽITÉ:
# Copy-Item jen přidává/přepisuje soubory, ale nesmaže soubory,
# které už v nové verzi nejsou. Proto starý BG.png zůstával.
# Robocopy /MIR udělá cílovou složku přesně stejnou jako novou verzi.
$robocopyArgs = @(
    $source,
    $target,
    "/MIR",
    "/R:3",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP"
)

& robocopy @robocopyArgs
$robocopyCode = $LASTEXITCODE

# Robocopy vrací 0-7 jako úspěch / změny provedeny, 8+ je chyba.
if ($robocopyCode -ge 8) {
    throw "Robocopy aktualizace selhala. Kód: $robocopyCode"
}

Start-Sleep -Milliseconds 500

if (Test-Path $runFile) {{
    Start-Process $runFile
}} else {{
    Start-Process explorer.exe $target
}}
"""

    with open(ps1_path, "w", encoding="utf-8") as file:
        file.write(powershell_script)

    subprocess.Popen([
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ps1_path,
    ], shell=False)

    sys.exit(0)


def download_and_install_update(update_data: dict) -> None:
    app_dir = get_app_dir()
    current_run_path = get_current_run_path()
    run_file_name = os.path.basename(current_run_path)

    zip_path = download_update_package(update_data)
    install_update_package(zip_path, app_dir, run_file_name)
