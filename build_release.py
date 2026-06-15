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

APP_NAME_DEFAULT = "Sifrator_Mraveniste"
REPO_OWNER = "lukaskomarek30"
REPO_NAME = "sifry_na_tabor"

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / "build_log.txt"


def log(message: str = "") -> None:
    print(message)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
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
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def get_current_version(main_py: Path) -> str:
    s = read_text(main_py)
    m = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', s, re.MULTILINE)
    return m.group(1).strip() if m else ""


def get_app_name(main_py: Path) -> str:
    s = read_text(main_py)
    m = re.search(r'^APP_NAME\s*=\s*["\']([^"\']+)["\']', s, re.MULTILINE)
    return m.group(1).strip() if m else APP_NAME_DEFAULT


def set_version(main_py: Path, version: str) -> None:
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
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def get_platform_key() -> str:
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
    separator = ";" if os.name == "nt" else ":"
    return f"{src}{separator}{dst}"


def zip_folder_contents(src_dir: Path, zip_path: Path) -> None:
    """Zabalí obsah složky přímo do kořene ZIPu."""
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in src_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir))


def zip_path_with_root(src_path: Path, zip_path: Path, root_name: str | None = None) -> None:
    """Zabalí soubor/složku tak, aby v ZIPu zůstala kořenová složka.

    Používá se hlavně pro macOS .app balíček.
    """
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
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def make_icons(venv_python: Path) -> tuple[Path | None, Path | None]:
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
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_platform_update_json(path: Path, version: str, platform_key: str, package_url: str, sha: str, zip_name: str) -> dict:
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
    LOG_PATH.write_text("==== BUILD LOG - Sifrator Mraveniste ====\n", encoding="utf-8")

    platform_key = get_platform_key()

    log("============================================================")
    log(" SIFRATOR MRAVENISTE - VYDANI NOVE VERZE")
    log("============================================================")
    log(f"Projekt:   {ROOT}")
    log(f"Platforma: {platform_key}")
    log(f"Log:       {LOG_PATH}")
    log("")

    if platform_key not in ("windows-x64", "macos-arm64", "macos-x64"):
        raise RuntimeError(f"Tento build skript je pripraveny pro Windows/macOS. Detekovana platforma: {platform_key}")

    main_py = ROOT / "main.py"
    update_manager_py = ROOT / "update_manager.py"
    pirate_key_renderer_py = ROOT / "pirate_key_renderer.py"

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

    if not venv_python.exists():
        log(f"\nVytvarim virtualni prostredi: {venv_dir}")
        run([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        log(f"\nOK: virtualni prostredi uz existuje: {venv_dir}")

    log("\nInstaluji / kontroluji knihovny...")
    run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(venv_python), "-m", "pip", "install", "--no-cache-dir", "pyinstaller", "PySide6", "Pillow"])

    ico_path, icns_path = make_icons(venv_python)

    temp_update_json = ROOT / "update.json"
    if not temp_update_json.exists():
        temp_update_json.write_text(json.dumps({"version": version, "notes": "", "platforms": {}}, ensure_ascii=False, indent=2), encoding="utf-8")
        log("Vytvoren docasny update.json")

    for old in [ROOT / "build", ROOT / "dist"]:
        if old.exists():
            log(f"Mazu stare: {old.name}")
            shutil.rmtree(old, ignore_errors=True)

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

    # Na Windows chceme, aby icons/ a logika sifer/ byly vedle EXE,
    # protože tak funguje aktualizace přes robocopy /MIR.
    if os.name == "nt":
        cmd.extend(["--contents-directory", "."])

    if icon_for_build and icon_for_build.exists():
        cmd.extend(["--icon", str(icon_for_build)])

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

    run(cmd)

    if platform_key == "windows-x64":
        dist_payload = ROOT / "dist" / app_name
        exe_path = dist_payload / f"{app_name}.exe"
        if not exe_path.exists():
            raise RuntimeError(f"EXE nebylo vytvoreno: {exe_path}")
    else:
        dist_payload = ROOT / "dist" / f"{app_name}.app"
        if not dist_payload.exists():
            raise RuntimeError(f"macOS .app nebyl vytvoren: {dist_payload}")

    release_dir = ROOT / "release" / f"v {version}" / platform_key
    release_dir.mkdir(parents=True, exist_ok=True)

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

    if platform_key == "windows-x64":
        zip_folder_contents(dist_payload, zip_path)
    else:
        zip_path_with_root(dist_payload, zip_path, dist_payload.name)

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

    sha = sha256_file(zip_path)
    (release_dir / f"sha256_{platform_key}_v{version}.txt").write_text(sha, encoding="utf-8")

    tag_name = f"v{version}"
    package_url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{tag_name}/{zip_name}"

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
