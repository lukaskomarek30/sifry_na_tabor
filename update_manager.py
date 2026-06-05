import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


UPDATE_JSON_URL = "https://raw.githubusercontent.com/lukaskomarek30/sifry_na_tabor/main/update.json"


def parse_version(version: str):
    version = version.strip().lower().replace("v", "")
    return tuple(int(part) for part in version.split("."))


def is_newer_version(remote_version: str, current_version: str) -> bool:
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except Exception:
        return False


def get_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_current_exe_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])


def download_text(url: str, timeout: int = 6) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def download_file(url: str, output_path: str, timeout: int = 60):
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with open(output_path, "wb") as file:
            shutil.copyfileobj(response, file)


def sha256_file(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def check_for_update(current_version: str):
    try:
        raw_json = download_text(UPDATE_JSON_URL)
        data = json.loads(raw_json)

        remote_version = data.get("version", "").strip()
        package_url = data.get("package_url", "").strip()

        if not remote_version or not package_url:
            return None

        if not is_newer_version(remote_version, current_version):
            return None

        return data
    except Exception:
        return None


def download_update_package(update_data: dict) -> str:
    package_url = update_data["package_url"]
    expected_sha256 = update_data.get("sha256", "").strip().lower()

    temp_zip = os.path.join(tempfile.gettempdir(), "sifrator_update_package.zip")
    if os.path.exists(temp_zip):
        os.remove(temp_zip)

    download_file(package_url, temp_zip)

    if expected_sha256:
        real_sha256 = sha256_file(temp_zip).lower()
        if real_sha256 != expected_sha256:
            raise RuntimeError("Stažený balíček nesedí s kontrolním SHA256 hashem. Aktualizace byla zastavena.")

    return temp_zip


def install_update_package(zip_path: str, app_dir: str, exe_name: str):
    temp_extract_dir = os.path.join(tempfile.gettempdir(), "sifrator_update_extract")
    ps1_path = os.path.join(tempfile.gettempdir(), "sifrator_update.ps1")

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

    os.makedirs(temp_extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_file:
        zip_file.extractall(temp_extract_dir)

    exe_path_after_update = os.path.join(app_dir, exe_name)

    powershell_script = f"""
$ErrorActionPreference = "Stop"

Start-Sleep -Seconds 2

$source = "{temp_extract_dir}"
$target = "{app_dir}"
$exe = "{exe_path_after_update}"

Get-ChildItem -Path $target -Force | Remove-Item -Recurse -Force
Copy-Item -Path "$source\\*" -Destination $target -Recurse -Force

Start-Sleep -Milliseconds 500
Start-Process $exe
"""

    with open(ps1_path, "w", encoding="utf-8") as file:
        file.write(powershell_script)

    subprocess.Popen(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps1_path], shell=False)
    sys.exit(0)


def download_and_install_update(update_data: dict):
    app_dir = get_app_dir()
    current_exe = get_current_exe_path()
    exe_name = os.path.basename(current_exe)

    zip_path = download_update_package(update_data)
    install_update_package(zip_path, app_dir, exe_name)
