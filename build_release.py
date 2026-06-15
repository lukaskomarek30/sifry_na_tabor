"""Buildovací skript pro vydání aplikace Šifrátor Mraveniště.

Skript automatizuje celý proces přípravy nové verze:
- načtení a případnou aktualizaci verze v main.py,
- vytvoření nebo použití samostatného buildovacího virtuálního prostředí,
- kontrolu a instalaci buildovacích závislostí,
- přípravu ikon aplikace pro Windows a macOS,
- sestavení aplikace přes PyInstaller,
- vytvoření release složky a ZIP balíčku,
- výpočet SHA256 kontrolního součtu,
- aktualizaci souboru update.json pro automatické aktualizace.

Výsledkem je platformně specifický balíček připravený k nahrání
do GitHub Releases a odpovídající update.json pro repozitář.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Základní identifikace aplikace a GitHub repozitáře.
APP_NAME_DEFAULT = "Sifrator_Mraveniste"
REPO_OWNER = "lukaskomarek30"
REPO_NAME = "sifry_na_tabor"

# Kořen projektu je vždy složka, ve které je uložen tento build skript.
ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "build_log.txt"


def log(message: str = "") -> None:
    """Zapíše zprávu současně do konzole i do build logu."""
    print(message)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Spustí externí příkaz, průběžně zaloguje výstup a volitelně kontroluje návratový kód."""
    text = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    log(f"\n> {text}")
    p = subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.stdout:
        print(p.stdout, end="")
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(p.stdout)
    if check and p.returncode != 0:
        raise RuntimeError(f"Prikaz selhal s kodem {p.returncode}: {text}")
    return p


def read_text(path: Path) -> str:
    """Načte textový soubor s podporou UTF-8 BOM, které může vzniknout při úpravách ve Windows editorech."""
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    """Zapíše textový soubor v čistém UTF-8 kódování."""
    path.write_text(text, encoding="utf-8")


def get_current_version(main_py: Path) -> str:
    """Načte aktuální hodnotu APP_VERSION ze souboru main.py."""
    s = read_text(main_py)
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', s, re.MULTILINE)
    return m.group(1).strip() if m else ""


def get_app_name(main_py: Path) -> str:
    """Načte název aplikace z APP_NAME, případně použije výchozí hodnotu."""
    s = read_text(main_py)
    m = re.search(r'^APP_NAME\s*=\s*["\']([^"\']+)["\']', s, re.MULTILINE)
    return m.group(1).strip() if m else APP_NAME_DEFAULT


def set_version(main_py: Path, version: str) -> None:
    """Aktualizuje hodnotu APP_VERSION v main.py; pokud chybí, doplní ji na začátek souboru."""
    s = read_text(main_py)
    s2, count = re.subn(
        r'^APP_VERSION\s*=\s*["\'].*?["\']',
        f'APP_VERSION = "{version}"',
        s,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        s2 = f'APP_VERSION = "{version}"\n' + s
    write_text(main_py, s2)


def sha256_file(path: Path) -> str:
    """Vypočítá SHA256 hash souboru po blocích, aby skript zvládl i větší ZIP balíčky."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def get_platform_key() -> str:
    """Vrátí normalizovaný klíč platformy používaný v update.json a názvech release balíčků."""
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


def add_data_arg(src: Path, dst: str) -> str:
    """Sestaví parametr --add-data pro PyInstaller se správným oddělovačem podle operačního systému."""
    separator = ";" if os.name == "nt" else ":"
    return f"{src}{separator}{dst}"


def zip_folder_contents(src_dir: Path, zip_path: Path) -> None:
    """Zabalí obsah složky přímo do kořene ZIP archivu.
    
    Tento formát se používá pro Windows build, kde updater očekává,
    že EXE a podpůrné složky budou po rozbalení přímo v kořeni balíčku."""
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in src_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir))


def zip_path_with_root(src_path: Path, zip_path: Path, root_name: str | None = None) -> None:
    """Zabalí soubor nebo složku do ZIP archivu včetně kořenové položky.
    
    Tento formát je důležitý hlavně pro macOS .app balíček, protože
    aplikace musí po rozbalení zůstat jako jeden kompletní .app adresář."""
    if zip_path.exists():
        zip_path.unlink()

    root_name = root_name or src_path.name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        if src_path.is_file():
            zf.write(src_path, root_name)
            return

        for path in src_path.rglob("*"):
            if path.is_file():
                zf.write(path, Path(root_name) / path.relative_to(src_path))


def copytree_fresh(src: Path, dst: Path) -> None:
    """Zkopíruje složku do cíle a předem odstraní případnou starší kopii."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def make_icons(venv_python: Path) -> tuple[Path | None, Path | None]:
    """Připraví aplikační ikony app.ico a app.icns z hlavního logo.png.
    
    Windows používá soubor ICO, macOS používá ICNS. Pokud ikony už existují,
    skript je znovu negeneruje a pouze je použije."""
    ico = ROOT / "icons" / "app.ico"
    icns = ROOT / "icons" / "app.icns"
    logo = ROOT / "icons" / "logo.png"

    if not logo.exists():
        raise RuntimeError("Chybi icons/logo.png, nelze vytvorit ikonu aplikace.")

    if not ico.exists():
        code_ico = (
            "from PIL import Image\n"
            "img=Image.open(r'icons/logo.png').convert('RGBA')\n"
            "img.thumbnail((256,256))\n"
            "canvas=Image.new('RGBA',(256,256),(0,0,0,0))\n"
            "canvas.paste(img,((256-img.width)//2,(256-img.height)//2),img)\n"
            "canvas.save(r'icons/app.ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])\n"
        )
        log("Vytvarim icons/app.ico z icons/logo.png...")
        run([str(venv_python), "-c", code_ico])
    else:
        log("OK: icons/app.ico uz existuje")

    if not icns.exists():
        code_icns = (
            "from PIL import Image\n"
            "img=Image.open(r'icons/logo.png').convert('RGBA')\n"
            "size=max(img.size)\n"
            "canvas=Image.new('RGBA',(size,size),(0,0,0,0))\n"
            "canvas.paste(img,((size-img.width)//2,(size-img.height)//2),img)\n"
            "canvas.save(r'icons/app.icns', format='ICNS')\n"
        )
        log("Vytvarim icons/app.icns z icons/logo.png...")
        p = run([str(venv_python), "-c", code_icns], check=False)
        if p.returncode != 0:
            log("UPOZORNENI: icons/app.icns se nepodarilo vytvorit. macOS build bude bez vlastni icns ikony.")
    else:
        log("OK: icons/app.icns uz existuje")

    return (ico if ico.exists() else None, icns if icns.exists() else None)


def load_existing_update_json(path: Path) -> dict:
    """Načte existující update.json a při chybě vrátí prázdnou konfiguraci."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_platform_update_json(path: Path, version: str, platform_key: str, package_url: str, sha: str, zip_name: str) -> dict:
    """Zapíše nebo aktualizuje položku aktuální platformy v update.json.
    
    Ostatní platformy v sekci platforms zůstávají zachované, aby bylo možné
    vydávat Windows a macOS balíčky postupně z různých systémů."""
    data = load_existing_update_json(path)

    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}

    platforms[platform_key] = {
        "package_url": package_url,
        "sha256": sha,
        "file_name": zip_name,
    }

    update_data = {
        "version": version,
        "notes": f"Nova verze {version}.",
        "platforms": platforms,
    }

    update_json_text = json.dumps(update_data, ensure_ascii=False, indent=2)
    path.write_text(update_json_text, encoding="utf-8")
    return update_data


def validate_project_files(main_py: Path, update_manager_py: Path, pirate_key_renderer_py: Path) -> None:
    """Ověří, že ve složce projektu existují všechny soubory potřebné pro sestavení a aktualizace."""
    if not main_py.exists():
        raise RuntimeError("V teto slozce neni main.py. Dej build_release.py do hlavni slozky projektu.")
    if not (ROOT / "icons").is_dir():
        raise RuntimeError("Chybi slozka icons.")
    if not (ROOT / "logika sifer").is_dir():
        raise RuntimeError("Chybi slozka logika sifer.")
    if not pirate_key_renderer_py.exists():
        raise RuntimeError("Chybi pirate_key_renderer.py. Dej ho do hlavni slozky projektu vedle main.py a build_release.py.")
    if not update_manager_py.exists():
        raise RuntimeError("Chybi update_manager.py. Pro aktualizace Windows/macOS je potreba pribalit update_manager.py.")


def main() -> int:
    """Provede kompletní build workflow pro aktuálně detekovanou platformu."""
    # Každý build začíná čistým logem, aby bylo možné jednoduše dohledat chyby z posledního sestavení.
    LOG_PATH.write_text("==== BUILD LOG - Sifrator Mraveniste ====\n", encoding="utf-8")

    platform_key = get_platform_key()

    log("============================================================")
    log(" SIFRATOR MRAVENISTE - VYDANI NOVE VERZE")
    log("============================================================")
    log(f"Projekt:   {ROOT}")
    log(f"Platforma: {platform_key}")
    log(f"Log:       {LOG_PATH}")
    log("")

    # Skript aktuálně vytváří oficiální release balíčky pouze pro Windows a macOS.
    if platform_key not in ("windows-x64", "macos-arm64", "macos-x64"):
        raise RuntimeError(f"Tento build skript je pripraveny pro Windows/macOS. Detekovana platforma: {platform_key}")

    main_py = ROOT / "main.py"
    update_manager_py = ROOT / "update_manager.py"
    pirate_key_renderer_py = ROOT / "pirate_key_renderer.py"

    # Před spuštěním buildu se ověří struktura projektu, aby se chyba neprojevila až v PyInstalleru.
    validate_project_files(main_py, update_manager_py, pirate_key_renderer_py)

    current_version = get_current_version(main_py)
    app_name = get_app_name(main_py)

    if current_version:
        log(f"Aktualni verze v main.py: {current_version}")
    else:
        log("Aktualni verze v main.py: NEPODARILO SE NACIST")
        log('Zkontroluj radek napr.: APP_VERSION = "0.0.7"')

    log("")
    log("Zadej novou verzi bez pismene v, napr. 0.0.7")
    log("Kdyz chces ponechat aktualni verzi, stiskni Enter.")
    version = input("Nova verze: ").strip()
    if not version:
        version = current_version
    if not version:
        raise RuntimeError("Verze nesmi byt prazdna.")
    if version.lower().startswith("v"):
        version = version[1:].strip()

    log(f"\nVerze pro toto vydani bude: {version}")
    set_version(main_py, version)
    log(f"APP_VERSION v main.py nastaveno na: {get_current_version(main_py)}")

    venv_dir = ROOT / ".venv_build"
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    # Build používá vlastní virtuální prostředí, aby nebyl závislý na knihovnách v běžném Pythonu uživatele.
    if not venv_python.exists():
        log(f"\nVytvarim virtualni prostredi: {venv_dir}")
        run([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        log(f"\nOK: virtualni prostredi uz existuje: {venv_dir}")

    log("\nInstaluji / kontroluji knihovny...")
    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python), "-m", "pip", "install", "--no-cache-dir", "pyinstaller", "PySide6", "Pillow"])

    # Ikony se připravují až po instalaci Pillow, protože generování ICO/ICNS používá PIL.
    ico_path, icns_path = make_icons(venv_python)

    # update.json se přibalí do aplikace, aby měl build vždy dostupnou základní aktualizační konfiguraci.
    temp_update_json = ROOT / "update.json"
    if not temp_update_json.exists():
        temp_update_json.write_text(json.dumps({"version": version, "notes": "", "platforms": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
        log("Vytvoren docasny update.json")

    # Staré PyInstaller výstupy se mažou kvůli opakovatelnosti buildu a prevenci zbytkových souborů.
    for old in [ROOT / "build", ROOT / "dist"]:
        if old.exists():
            log(f"Mazu stare: {old.name}")
            shutil.rmtree(old, ignore_errors=True)

    # Spec soubor se nechává generovat znovu, aby odpovídal aktuálním parametrům skriptu.
    spec = ROOT / f"{app_name}.spec"
    if spec.exists():
        spec.unlink()

    log("\nVytvarim aplikaci pres PyInstaller...")

    icon_for_build: Path | None = ico_path
    if platform_key.startswith("macos"):
        icon_for_build = icns_path

    cmd = [
        str(venv_python), "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", app_name,
    ]

    # Windows build musí mít podpůrné složky přímo vedle EXE.
    # Updater následně provádí zrcadlové přepsání přes robocopy /MIR.
    if os.name == "nt":
        cmd.extend(["--contents-directory", "."])

    # Platformní ikona se použije jen v případě, že se ji podařilo vytvořit nebo už existuje.
    if icon_for_build and icon_for_build.exists():
        cmd.extend(["--icon", str(icon_for_build)])

    # Do buildu se přibalují všechny runtime assety a moduly potřebné pro aktualizace i generování klíčů.
    cmd.extend([
        "--hidden-import", "pirate_key_renderer",
        "--hidden-import", "update_manager",
        "--add-data", add_data_arg(ROOT / "icons", "icons"),
        "--add-data", add_data_arg(ROOT / "logika sifer", "logika sifer"),
        "--add-data", add_data_arg(ROOT / "update.json", "."),
        "--add-data", add_data_arg(update_manager_py, "."),
        "--add-data", add_data_arg(pirate_key_renderer_py, "."),
        str(main_py),
    ])

    # Samotné sestavení aplikace přes PyInstaller.
    run(cmd)

    # Po buildu se ověří, že PyInstaller vytvořil očekávaný výstup pro aktuální platformu.
    if platform_key == "windows-x64":
        dist_payload = ROOT / "dist" / app_name
        exe_path = dist_payload / f"{app_name}.exe"
        if not exe_path.exists():
            raise RuntimeError(f"EXE nebylo vytvoreno: {exe_path}")
    else:
        dist_payload = ROOT / "dist" / f"{app_name}.app"
        if not dist_payload.exists():
            raise RuntimeError(f"macOS .app nebyl vytvoren: {dist_payload}")

    # Release výstupy se ukládají odděleně podle verze a platformy.
    release_dir = ROOT / "release" / f"v {version}" / platform_key
    release_dir.mkdir(parents=True, exist_ok=True)

    # Do release složky se ukládá i rozbalená aplikace pro rychlou ruční kontrolu.
    if platform_key == "windows-x64":
        release_app_dir = release_dir / app_name
        copytree_fresh(dist_payload, release_app_dir)
    else:
        release_app_dir = release_dir / dist_payload.name
        if release_app_dir.exists():
            shutil.rmtree(release_app_dir)
        shutil.copytree(dist_payload, release_app_dir, symlinks=True)

    zip_name = f"{app_name}_{platform_key}_v{version}.zip"
    zip_path = release_dir / zip_name
    log("\nVytvarim ZIP aktualizace...")

    # Windows a macOS mají rozdílnou strukturu ZIPu kvůli rozdílnému způsobu instalace aktualizace.
    if platform_key == "windows-x64":
        zip_folder_contents(dist_payload, zip_path)
    else:
        zip_path_with_root(dist_payload, zip_path, dist_payload.name)

    # ZIP se po vytvoření testovacím způsobem rozbalí a ověří se jeho očekávaná struktura.
    with tempfile.TemporaryDirectory(prefix="sifrator_zip_test_") as td:
        test_dir = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(test_dir)

        if platform_key == "windows-x64":
            if not (test_dir / f"{app_name}.exe").exists():
                raise RuntimeError("ZIP je spatne zabaleny. Uvnitr neni rovnou EXE.")
        else:
            if not (test_dir / f"{app_name}.app").exists():
                raise RuntimeError("ZIP je spatne zabaleny. Uvnitr neni .app balicek.")

    # SHA256 slouží updateru k ověření integrity staženého balíčku před instalací.
    sha = sha256_file(zip_path)
    (release_dir / f"sha256_{platform_key}_v{version}.txt").write_text(sha, encoding="utf-8")

    tag_name = f"v{version}"
    package_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{tag_name}/{zip_name}"

    # update.json ukazuje na GitHub Release balíček a obsahuje hash pro kontrolu staženého ZIPu.
    update_data = write_platform_update_json(
        ROOT / "update.json",
        version=version,
        platform_key=platform_key,
        package_url=package_url,
        sha=sha,
        zip_name=zip_name,
    )

    (release_dir / "update.json").write_text(json.dumps(update_data, ensure_ascii=False, indent=2), encoding="utf-8")

    log("\n============================================================")
    log(" HOTOVO")
    log("============================================================")
    log(f"Verze:        {version}")
    log(f"Platforma:    {platform_key}")
    log(f"Aplikace:     {release_app_dir}")
    log(f"ZIP:          {zip_path}")
    log(f"SHA256:       {sha}")
    log(f"update.json:  {release_dir / 'update.json'}")
    log("")
    log("Na GitHub Release nahraj ZIP:")
    log(str(zip_path))
    log("")
    log("Do repozitare commitni update.json:")
    log(str(ROOT / "update.json"))
    log("")
    log("Odkaz v update.json:")
    log(package_url)
    log("============================================================")
    return 0


# Standardní vstupní bod skriptu. Chyby se zapisují do logu a vrací se odpovídající návratový kód.
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("\nZruseno uzivatelem.")
        raise SystemExit(130)
    except Exception as e:
        log("\n============================================================")
        log(f"CHYBA: {e}")
        log("============================================================")
        raise SystemExit(1)
