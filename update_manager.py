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

PRESERVED_USER_DATA_FILES = (
    "historie_zprav.json",
    "plan_tabor_sifer.json",
    "poznamky_sifer.json",
)
PRESERVED_USER_DATA_DIRS = (
    "history_images",
    "planner_attachments",
    "Sifrator_Mraveniste",
    "user_data",
    "sifrator_data",
)


class UpdateError(RuntimeError):
    pass


class UpdateCancelled(UpdateError):
    pass



def get_debug_log_path() -> str:
    """Vrátí cestu k diagnostickému logu aktualizací.

    Log je užitečný hlavně na macOS, kde může HTTPS stažení přes urllib
    selhat kvůli certifikátům v PyInstaller buildu. Aplikace kvůli tomu
    uživateli nezahlcuje okno chybami, ale uloží důvod do dočasné složky.
    """
    return os.path.join(tempfile.gettempdir(), "sifrator_update_debug.log")


def get_update_install_log_path() -> str:
    """Vrátí cestu k instalačnímu logu macOS aktualizace."""
    return os.path.join(tempfile.gettempdir(), "sifrator_update_install.log")


def _debug_log(message: str) -> None:
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(get_debug_log_path(), "a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _curl_binary() -> str:
    """Vrátí systémový curl, pokud je dostupný."""
    if platform.system().lower() == "darwin" and os.path.exists("/usr/bin/curl"):
        return "/usr/bin/curl"
    return "curl"


def _download_text_with_curl(url: str, timeout: int = 12) -> str:
    curl = _curl_binary()
    completed = subprocess.run(
        [
            curl,
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            str(max(3, int(timeout))),
            "--max-time",
            str(max(8, int(timeout) + 6)),
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode != 0:
        raise UpdateError(
            "Stažení update.json přes curl selhalo.\n"
            f"Kód: {completed.returncode}\n"
            f"Chyba: {completed.stderr.strip()}"
        )

    return completed.stdout


def _download_file_with_curl(url: str, output_path: str, timeout: int = 300) -> None:
    curl = _curl_binary()
    completed = subprocess.run(
        [
            curl,
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--connect-timeout",
            "15",
            "--max-time",
            str(max(60, int(timeout))),
            "-o",
            output_path,
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.returncode != 0:
        raise UpdateError(
            "Stažení aktualizačního ZIPu přes curl selhalo.\n"
            f"Kód: {completed.returncode}\n"
            f"Chyba: {completed.stderr.strip()}"
        )


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


def is_macos_app_translocated() -> bool:
    """Zjistí, jestli macOS spustil aplikaci z dočasné AppTranslocation cesty.

    Když je aplikace translocovaná, updater by přepsal jen dočasnou kopii,
    takže po dalším spuštění by uživatel znovu viděl starou verzi.
    """
    if platform.system().lower() != "darwin":
        return False

    run_path = os.path.abspath(get_current_run_path())
    app_path = os.path.abspath(get_macos_app_bundle_path() or "")
    return "/AppTranslocation/" in run_path or "/AppTranslocation/" in app_path


def ensure_macos_update_target_is_valid() -> None:
    """Zastaví aktualizaci, pokud macOS běží z AppTranslocation."""
    if not is_macos_app_translocated():
        return

    run_path = os.path.abspath(get_current_run_path())
    raise UpdateError(
        "macOS spustil aplikaci z dočasné AppTranslocation cesty.\n\n"
        "V takovém režimu se aktualizace sice může stáhnout, ale přepíše jen "
        "dočasnou kopii aplikace. Po dalším spuštění by se proto znovu otevřela "
        "stará verze.\n\n"
        "Řešení:\n"
        "1) Ukonči aplikaci přes Cmd+Q.\n"
        "2) Přesuň Sifrator_Mraveniste.app do /Applications.\n"
        "3) V Terminálu spusť:\n"
        "   xattr -dr com.apple.quarantine /Applications/Sifrator_Mraveniste.app\n"
        "4) Spusť aplikaci z /Applications a aktualizaci zopakuj.\n\n"
        f"Aktuální dočasná cesta:\n{run_path}"
    )


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
    """Stáhne text s fallbackem pro macOS buildy.

    Na některých macOS PyInstaller buildech může urllib spadnout na SSL
    certifikátech. Proto se nejdřív zkusí urllib a při chybě systémový curl.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})

    try:
        _debug_log(f"Stahuji text přes urllib: {url}")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
            _debug_log(f"urllib OK, délka textu: {len(text)}")
            return text
    except Exception as error:
        _debug_log(f"urllib selhalo: {type(error).__name__}: {error}")

    _debug_log(f"Zkouším curl fallback: {url}")
    text = _download_text_with_curl(url, timeout=max(timeout, 12))
    _debug_log(f"curl OK, délka textu: {len(text)}")
    return text


def download_file(url: str, output_path: str, timeout: int = 120, progress_callback: ProgressCallback | None = None) -> None:
    """Stáhne soubor s fallbackem přes systémový curl.

    urllib zůstává primární kvůli průběhu stahování. Pokud ale na macOS selže
    HTTPS/certifikát, použije se curl, který je na macOS dostupný systémově.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "Sifrator-Mraveniste-Updater"})

    try:
        _debug_log(f"Stahuji soubor přes urllib: {url}")
        _emit_progress(progress_callback, 4, "Připojuji se k GitHubu...")
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

        _debug_log(f"urllib soubor OK: {output_path}, velikost: {os.path.getsize(output_path)}")
        return

    except Exception as error:
        _debug_log(f"urllib soubor selhal: {type(error).__name__}: {error}")

    _emit_progress(progress_callback, 10, "Stahuji aktualizaci přes systémový curl...")
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    _download_file_with_curl(url, output_path, timeout=max(timeout, 300))
    if not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
        raise UpdateError("Stažení aktualizačního balíčku přes curl nevytvořilo platný soubor.")

    _debug_log(f"curl soubor OK: {output_path}, velikost: {os.path.getsize(output_path)}")
    _emit_progress(progress_callback, 68, "Aktualizace byla stažena.")




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
        platform_key = get_platform_key()
        _debug_log(
            "Kontrola aktualizace: "
            f"current_version={current_version}, platform_key={platform_key}, url={UPDATE_JSON_URL}"
        )

        raw_json = download_text(UPDATE_JSON_URL)
        data = json.loads(raw_json)

        remote_version = str(data.get("version", "")).strip()
        _debug_log(f"Vzdálená verze: {remote_version}")

        if not remote_version:
            _debug_log("update.json neobsahuje platnou verzi.")
            return None

        if not is_newer_version(remote_version, current_version):
            _debug_log("Novější verze není dostupná.")
            return None

        selected_data = _select_platform_data(data)
        if not selected_data:
            platforms = data.get("platforms")
            keys = ", ".join(sorted(platforms.keys())) if isinstance(platforms, dict) else "bez platforms"
            _debug_log(f"Nenašel se balíček pro platformu {platform_key}. Dostupné klíče: {keys}")
            return None

        _debug_log(
            "Aktualizace dostupná: "
            f"version={selected_data.get('version')}, "
            f"platform={selected_data.get('platform_key')}, "
            f"file={selected_data.get('file_name')}"
        )
        return selected_data
    except Exception as error:
        _debug_log(f"check_for_update selhalo: {type(error).__name__}: {error}")
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



def _extract_macos_zip_with_ditto(zip_path: str, extract_dir: str, progress_callback: ProgressCallback | None = None) -> None:
    """Rozbalí macOS aktualizační ZIP přes systémové ditto.

    Pro macOS .app balíčky je to zásadní, protože Python zipfile neumí vždy
    správně obnovit symlinky uvnitř Contents/Frameworks. Když se symlink
    Contents/Frameworks/Python rozbalí špatně, PyInstaller aplikace pak končí
    chybou: Failed to load Python shared library.
    """
    if platform.system().lower() != "darwin" or not os.path.exists("/usr/bin/ditto"):
        _debug_log("macOS ditto není dostupné, používám Python zipfile fallback.")
        _extract_zip_with_progress(zip_path, extract_dir, progress_callback=progress_callback)
        return

    _emit_progress(progress_callback, 80, "Rozbaluji aktualizaci přes macOS ditto...")
    _debug_log(f"macOS ditto extract: ZIP={zip_path}, DIR={extract_dir}")

    completed = subprocess.run(
        ["/usr/bin/ditto", "-x", "-k", zip_path, extract_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if completed.stdout.strip():
        _debug_log("ditto stdout: " + completed.stdout.strip())
    if completed.stderr.strip():
        _debug_log("ditto stderr: " + completed.stderr.strip())

    if completed.returncode != 0:
        raise UpdateError(
            "Rozbalení macOS aktualizace přes ditto selhalo.\n"
            f"Kód: {completed.returncode}\n"
            f"Chyba: {completed.stderr.strip()}"
        )

    _emit_progress(progress_callback, 94, "Aktualizace byla rozbalena.")
    _debug_log("macOS ditto extract OK.")


def _validate_macos_app_payload(app_path: str) -> None:
    """Zkontroluje, že rozbalený macOS .app balíček vypadá použitelně."""
    if platform.system().lower() != "darwin":
        return

    if not app_path.endswith(".app"):
        raise UpdateError(f"Rozbalený macOS payload není .app balíček: {app_path}")

    contents_dir = os.path.join(app_path, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    frameworks_dir = os.path.join(contents_dir, "Frameworks")

    if not os.path.isdir(contents_dir):
        raise UpdateError(f"V .app balíčku chybí Contents: {contents_dir}")

    if not os.path.isdir(macos_dir):
        raise UpdateError(f"V .app balíčku chybí Contents/MacOS: {macos_dir}")

    executables = []
    try:
        for name in os.listdir(macos_dir):
            candidate = os.path.join(macos_dir, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                executables.append(candidate)
    except Exception:
        pass

    if not executables:
        # Některé ZIPy můžou po rozbalení ještě nemít executable bit, proto
        # zkusíme najít aspoň hlavní soubor podle názvu aplikace.
        fallback = os.path.join(macos_dir, os.path.basename(app_path).replace(".app", ""))
        if not os.path.isfile(fallback):
            raise UpdateError(f"V .app balíčku nebyl nalezen spustitelný soubor v {macos_dir}")

    if not os.path.isdir(frameworks_dir):
        _debug_log(f"Upozornění: v .app balíčku není Contents/Frameworks: {frameworks_dir}")
        return

    python_link = os.path.join(frameworks_dir, "Python")
    if os.path.lexists(python_link):
        if os.path.islink(python_link):
            target = os.readlink(python_link)
            _debug_log(f"Kontrola Python frameworku: symlink Contents/Frameworks/Python -> {target}")
            if not os.path.exists(python_link):
                raise UpdateError(f"Rozbitý symlink v .app balíčku: {python_link} -> {target}")
        elif os.path.isfile(python_link):
            try:
                completed = subprocess.run(
                    ["/usr/bin/file", "-b", python_link],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                description = (completed.stdout or completed.stderr or "").strip()
            except Exception as error:
                description = f"file kontrola selhala: {error}"

            _debug_log(f"Kontrola Python frameworku: {python_link}: {description}")
            if "Mach-O" not in description:
                raise UpdateError(
                    "Rozbalený macOS .app balíček má poškozený Python framework.\n"
                    "To obvykle znamená, že ZIP byl rozbalen špatným způsobem.\n"
                    f"Soubor: {python_link}\n"
                    f"file: {description}"
                )
    else:
        _debug_log("Contents/Frameworks/Python nebyl nalezen; pokračuji, protože struktura se může lišit podle PyInstalleru.")

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
    preserved_files_ps = "@(" + ", ".join(_ps_quote(item) for item in PRESERVED_USER_DATA_FILES) + ")"
    preserved_dirs_ps = "@(" + ", ".join(_ps_quote(item) for item in PRESERVED_USER_DATA_DIRS) + ")"

    _emit_progress(progress_callback, 96, "Připravuji restart aplikace...")

    powershell_script = f"""
$ErrorActionPreference = "Stop"

$pidToWait = {current_pid}
$source = {source_q}
$target = {target_q}
$runFile = {run_q}
$backup = {backup_q}
$userDataFiles = {preserved_files_ps}
$userDataDirs = {preserved_dirs_ps}

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

$excludedDirs = @()
foreach ($dirName in $userDataDirs) {{
    $excludedDirs += (Join-Path $target $dirName)
}}

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

if ($excludedDirs.Count -gt 0) {{
    $robocopyArgs += "/XD"
    $robocopyArgs += $excludedDirs
}}

if ($userDataFiles.Count -gt 0) {{
    $robocopyArgs += "/XF"
    $robocopyArgs += $userDataFiles
}}

& robocopy @robocopyArgs
$robocopyCode = $LASTEXITCODE

if ($robocopyCode -ge 8) {{
    throw "Robocopy aktualizace selhala. Kód: $robocopyCode"
}}

Write-Progress -Activity "Aktualizace Šifrátoru" -Status "Kontroluji uživatelská data..." -PercentComplete 82
$userDataItems = @($userDataFiles + $userDataDirs)
foreach ($itemName in $userDataItems) {{
    $backupItem = Join-Path $backup $itemName
    $targetItem = Join-Path $target $itemName
    if ((Test-Path $backupItem) -and !(Test-Path $targetItem)) {{
        Copy-Item -Path $backupItem -Destination $targetItem -Recurse -Force -ErrorAction SilentlyContinue
    }}
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
    """Nainstaluje aktualizaci na macOS automaticky bez ruční práce v Terminalu.

    Důležité:
    - pokud je aplikace v /Applications, macOS si může vyžádat admin heslo,
      protože běžná aplikace nesmí potichu přepsat /Applications,
    - uživatel ale nemusí nic kopírovat ani spouštět ručně,
    - instalaci spouští samostatný launcher skript, který přežije ukončení aplikace,
    - instalační skript jen kopíruje .app; nové spuštění provede launcher jako běžný uživatel,
      ne jako root. Tím se vyhne problémům, kdy se po admin instalaci aplikace znovu neotevře.
    """
    ensure_macos_update_target_is_valid()

    temp_root = tempfile.gettempdir()
    temp_extract_dir = os.path.join(temp_root, "sifrator_update_extract")
    sh_path = os.path.join(temp_root, "sifrator_update.sh")
    launcher_path = os.path.join(temp_root, "sifrator_update_launcher.sh")
    install_log = get_update_install_log_path()

    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    _emit_progress(progress_callback, 80, "Rozbaluji aktualizaci...")
    _debug_log(f"macOS instalace: ZIP={zip_path}, TARGET={target_path}")

    # macOS .app balíček se musí rozbalit přes ditto, ne přes Python zipfile.
    # zipfile neumí spolehlivě obnovit symlinky uvnitř Contents/Frameworks
    # a tím může rozbít PyInstaller Python runtime.
    _extract_macos_zip_with_ditto(zip_path, temp_extract_dir, progress_callback=progress_callback)

    if target_path.endswith(".app"):
        payload_path = _find_macos_app_payload(temp_extract_dir, target_path)
    else:
        payload_path = _find_payload_dir(temp_extract_dir)

    if not os.path.exists(payload_path):
        raise UpdateError(f"V rozbaleném ZIPu nebyla nalezena aplikace: {payload_path}")

    if target_path.endswith(".app") and not payload_path.endswith(".app"):
        raise UpdateError(f"V ZIPu nebyl nalezen .app balíček. Nalezeno: {payload_path}")

    if target_path.endswith(".app"):
        _validate_macos_app_payload(payload_path)

    current_pid = os.getpid()
    backup_path = os.path.join(temp_root, f"sifrator_backup_{int(time.time())}")

    source_q = _sh_quote(payload_path)
    target_q = _sh_quote(target_path)
    backup_q = _sh_quote(backup_path)
    log_q = _sh_quote(install_log)
    preserved_items_sh = " ".join(_sh_quote(item) for item in (PRESERVED_USER_DATA_FILES + PRESERVED_USER_DATA_DIRS))

    _emit_progress(progress_callback, 96, "Připravuji automatickou instalaci...")
    _debug_log(f"macOS payload: {payload_path}")
    _debug_log(f"macOS install log: {install_log}")
    _debug_log(f"macOS installer script: {sh_path}")
    _debug_log(f"macOS launcher script: {launcher_path}")

    # Tento skript běží buď přímo, nebo přes osascript s admin právy.
    # Záměrně už NEspouští aplikaci. Pouze přepíše .app a skončí.
    # Novou aplikaci otevře až launcher skript jako normální uživatel.
    installer_script = f'''#!/bin/sh
set -u

LOG={log_q}
PID_TO_WAIT={current_pid}
SOURCE={source_q}
TARGET={target_q}
BACKUP={backup_q}

exec >> "$LOG" 2>&1

echo "============================================================"
date
echo "Instaluji aktualizaci Sifrator Mraveniste"
echo "SOURCE=$SOURCE"
echo "TARGET=$TARGET"
echo "BACKUP=$BACKUP"
echo "PID_TO_WAIT=$PID_TO_WAIT"
echo "USER=$(id -un) UID=$(id -u)"

echo "Cekam na ukonceni puvodni aplikace..."
COUNT=0
while kill -0 "$PID_TO_WAIT" 2>/dev/null; do
    sleep 1
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -gt 45 ]; then
        echo "Aplikace se neukoncila do 45 s, pokracuji dal."
        break
    fi
done

if [ ! -e "$SOURCE" ]; then
    echo "CHYBA: Zdroj aktualizace neexistuje: $SOURCE"
    exit 10
fi

if [ ! -d "$SOURCE" ]; then
    echo "CHYBA: Zdroj aktualizace neni adresar .app: $SOURCE"
    exit 14
fi

TARGET_PARENT=$(dirname "$TARGET")
if [ ! -d "$TARGET_PARENT" ]; then
    echo "CHYBA: Cilova slozka neexistuje: $TARGET_PARENT"
    exit 11
fi

echo "Vytvarim zalohu..."
rm -rf "$BACKUP"
mkdir -p "$BACKUP"
if [ -e "$TARGET" ]; then
    /usr/bin/ditto "$TARGET" "$BACKUP/$(basename "$TARGET")" || echo "VAROVANI: zaloha se nepovedla"
else
    echo "Cilova aplikace jeste neexistuje, zaloha nebude."
fi

echo "Mazu starou aplikaci..."
rm -rf "$TARGET"

if [ -e "$TARGET" ]; then
    echo "CHYBA: Starou aplikaci se nepodarilo smazat: $TARGET"
    exit 12
fi

echo "Kopiruji novou aplikaci pres ditto..."
/usr/bin/ditto "$SOURCE" "$TARGET"
DITTO_CODE=$?
echo "ditto exit code: $DITTO_CODE"
if [ "$DITTO_CODE" -ne 0 ]; then
    echo "CHYBA: Kopirovani nove aplikace selhalo. Obnovuji zalohu."
    rm -rf "$TARGET"
    if [ -e "$BACKUP/$(basename "$TARGET")" ]; then
        /usr/bin/ditto "$BACKUP/$(basename "$TARGET")" "$TARGET" || true
    fi
    exit 13
fi

echo "Obnovuji pripadna legacy uzivatelska data..."
OLD_TARGET="$BACKUP/$(basename "$TARGET")"
OLD_DATA_BASE="$OLD_TARGET"
NEW_DATA_BASE="$TARGET"
if [ -d "$OLD_TARGET/Contents/MacOS" ] && [ -d "$TARGET/Contents/MacOS" ]; then
    OLD_DATA_BASE="$OLD_TARGET/Contents/MacOS"
    NEW_DATA_BASE="$TARGET/Contents/MacOS"
fi

for ITEM in {preserved_items_sh}; do
    if [ -e "$OLD_DATA_BASE/$ITEM" ] && [ ! -e "$NEW_DATA_BASE/$ITEM" ]; then
        echo "Obnovuji $ITEM"
        /usr/bin/ditto "$OLD_DATA_BASE/$ITEM" "$NEW_DATA_BASE/$ITEM" || echo "VAROVANI: $ITEM se nepodarilo obnovit"
    fi
done

echo "Nastavuji opravneni..."
chmod -R u+rwX "$TARGET" || true
if [ -d "$TARGET/Contents/MacOS" ]; then
    chmod -R a+x "$TARGET/Contents/MacOS" || true
fi

echo "Odstranuji quarantine atribut..."
/usr/bin/xattr -dr com.apple.quarantine "$TARGET" || true

echo "Kontrola vysledku:"
if [ ! -d "$TARGET" ]; then
    echo "CHYBA: Cilova aplikace po kopirovani neexistuje."
    exit 15
fi
if [ -d "$TARGET/Contents/MacOS" ]; then
    find "$TARGET/Contents/MacOS" -maxdepth 1 -type f -print || true
else
    echo "CHYBA: Chybi Contents/MacOS v nove aplikaci."
    exit 16
fi

echo "Kontrola Contents/Frameworks:"
if [ -d "$TARGET/Contents/Frameworks" ]; then
    ls -la "$TARGET/Contents/Frameworks" || true
else
    echo "VAROVANI: Chybi Contents/Frameworks."
fi

PYTHON_RUNTIME="$TARGET/Contents/Frameworks/Python"
if [ -e "$PYTHON_RUNTIME" ] || [ -L "$PYTHON_RUNTIME" ]; then
    echo "Kontrola Python runtime: $PYTHON_RUNTIME"
    ls -la "$PYTHON_RUNTIME" || true

    if [ -L "$PYTHON_RUNTIME" ]; then
        echo "Python runtime je symlink."
    else
        PYTHON_FILE_INFO=$(/usr/bin/file -b "$PYTHON_RUNTIME" 2>/dev/null || true)
        echo "file Python runtime: $PYTHON_FILE_INFO"
        case "$PYTHON_FILE_INFO" in
            *Mach-O*)
                echo "Python runtime vypada v poradku."
                ;;
            *)
                echo "CHYBA: Python runtime neni Mach-O soubor. Aplikace by po aktualizaci nesla spustit."
                echo "Obnovuji zalohu."
                rm -rf "$TARGET"
                if [ -e "$BACKUP/$(basename "$TARGET")" ]; then
                    /usr/bin/ditto "$BACKUP/$(basename "$TARGET")" "$TARGET" || true
                fi
                exit 17
                ;;
        esac
    fi
else
    echo "Python runtime Contents/Frameworks/Python nebyl nalezen; pokracuji, protoze struktura se muze lisit."
fi

date
echo "Instalace aktualizace dokoncena."
exit 0
'''

    with open(sh_path, "w", encoding="utf-8") as file:
        file.write(installer_script)

    try:
        os.chmod(sh_path, 0o755)
    except Exception:
        pass

    target_parent = os.path.dirname(os.path.abspath(target_path)) or "/"
    # /Applications obvykle vyžaduje admin práva. Když cílová složka není zapisovatelná,
    # použije se admin dialog také. Bez toho macOS starou aplikaci nepřepíše.
    use_admin = (
        os.path.abspath(target_path).startswith("/Applications/")
        or not os.access(target_parent, os.W_OK)
    )

    # AppleScript je záměrně ve tvaru: /bin/sh + quoted form of script path.
    # Předchozí varianta s ručně vloženými uvozovkami mohla v osascriptu selhat.
    apple_script = 'do shell script "/bin/sh " & quoted form of ' + json.dumps(sh_path) + ' with administrator privileges'
    apple_script_q = _sh_quote(apple_script)
    sh_path_q = _sh_quote(sh_path)
    target_q_for_launcher = _sh_quote(target_path)
    log_q_for_launcher = _sh_quote(install_log)

    # Launcher běží jako běžný uživatel, zapíše chyby osascriptu do logu,
    # po úspěšné instalaci znovu otevře aplikaci a při chybě zobrazí dialog.
    launcher_script = f'''#!/bin/sh
set -u

LOG={log_q_for_launcher}
TARGET={target_q_for_launcher}
INSTALLER={sh_path_q}
USE_ADMIN={1 if use_admin else 0}
APPLE_SCRIPT={apple_script_q}

exec >> "$LOG" 2>&1

echo "============================================================"
date
echo "Launcher aktualizace spusten"
echo "TARGET=$TARGET"
echo "INSTALLER=$INSTALLER"
echo "USE_ADMIN=$USE_ADMIN"

if [ "$USE_ADMIN" = "1" ]; then
    echo "Spoustim instalaci pres osascript s administrator privileges..."
    /usr/bin/osascript -e "$APPLE_SCRIPT"
    CODE=$?
else
    echo "Spoustim instalaci bez administrator privileges..."
    /bin/sh "$INSTALLER"
    CODE=$?
fi

echo "installer/osascript exit code: $CODE"

if [ "$CODE" -ne 0 ]; then
    echo "CHYBA: Instalace aktualizace selhala."
    /usr/bin/osascript -e 'display dialog "Aktualizace Šifrátoru Mraveniště se nepodařila. Podrobnosti jsou v instalačním logu." buttons {{"OK"}} default button "OK" with icon stop' >/dev/null 2>&1 || true
    exit "$CODE"
fi

echo "Instalace probehla, spoustim novou aplikaci..."
/usr/bin/xattr -dr com.apple.quarantine "$TARGET" >/dev/null 2>&1 || true
/usr/bin/open "$TARGET"
OPEN_CODE=$?
echo "open exit code: $OPEN_CODE"

if [ "$OPEN_CODE" -ne 0 ]; then
    /usr/bin/osascript -e 'display dialog "Aktualizace proběhla, ale aplikaci se nepodařilo automaticky znovu spustit. Otevři ji prosím z Applications." buttons {{"OK"}} default button "OK" with icon caution' >/dev/null 2>&1 || true
fi

date
echo "Launcher aktualizace dokoncen."
exit "$OPEN_CODE"
'''

    with open(launcher_path, "w", encoding="utf-8") as file:
        file.write(launcher_script)

    try:
        os.chmod(launcher_path, 0o755)
    except Exception:
        pass

    _emit_progress(progress_callback, 100, "Aktualizace je připravená. Aplikace se restartuje...")
    time.sleep(0.4)

    _debug_log(
        "Spouštím macOS launcher aktualizace. "
        f"use_admin={use_admin}, launcher={launcher_path}, installer={sh_path}"
    )

    # Launcher musí být samostatný proces, aby přežil ukončení aktuální aplikace.
    with open(install_log, "a", encoding="utf-8") as log_file:
        subprocess.Popen(
            ["/bin/sh", launcher_path],
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

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
        ensure_macos_update_target_is_valid()
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
