"""
app_paths.py – Pomocné funkce pro hledání cest k assetům a logice šifer.

Pokrývá vývojové spuštění, Windows onedir build (PyInstaller)
i macOS .app balíček s adresářem Resources.
"""

import importlib.util
import os
import shutil
import sys
import tempfile


APP_DATA_DIR_NAME = "Sifrator_Mraveniste"


# ============================================================
# ZÁKLADNÍ CESTY
# ============================================================

def get_app_dir() -> str:
    """Vrátí kořenovou složku běžící aplikace.

    Ve vývojovém režimu se používá adresář s main.py.
    U sestavené aplikace se používá adresář se spustitelným souborem.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_script_dir() -> str:
    """Vrátí adresář zdrojového souboru main.py."""
    return os.path.dirname(os.path.abspath(__file__))


def get_pyinstaller_bundle_dir() -> str:
    """Vrátí interní dočasný adresář PyInstaller bundlu, pokud je dostupný."""
    return getattr(sys, "_MEIPASS", "")


# ============================================================
# UŽIVATELSKÁ DATA A CACHE
# ============================================================

def _first_writable_base(candidates: list[str], fallback_name: str) -> str:
    """Vybere první použitelnou systémovou složku a případně spadne do tempu."""
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = os.path.abspath(os.path.expanduser(candidate))
            os.makedirs(path, exist_ok=True)
            return path
        except Exception:
            continue

    fallback = os.path.join(tempfile.gettempdir(), fallback_name)
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _user_data_base_dir() -> str:
    if sys.platform.startswith("win"):
        return _first_writable_base(
            [
                os.environ.get("APPDATA"),
                os.environ.get("LOCALAPPDATA"),
                os.path.join(os.path.expanduser("~"), "AppData", "Roaming"),
            ],
            "sifrator_user_data",
        )

    if sys.platform == "darwin":
        return _first_writable_base(
            [os.path.join(os.path.expanduser("~"), "Library", "Application Support")],
            "sifrator_user_data",
        )

    return _first_writable_base(
        [
            os.environ.get("XDG_DATA_HOME"),
            os.path.join(os.path.expanduser("~"), ".local", "share"),
        ],
        "sifrator_user_data",
    )


def _user_cache_base_dir() -> str:
    if sys.platform.startswith("win"):
        return _first_writable_base(
            [
                os.environ.get("LOCALAPPDATA"),
                os.environ.get("APPDATA"),
                os.path.join(os.path.expanduser("~"), "AppData", "Local"),
            ],
            "sifrator_user_cache",
        )

    if sys.platform == "darwin":
        return _first_writable_base(
            [os.path.join(os.path.expanduser("~"), "Library", "Caches")],
            "sifrator_user_cache",
        )

    return _first_writable_base(
        [
            os.environ.get("XDG_CACHE_HOME"),
            os.path.join(os.path.expanduser("~"), ".cache"),
        ],
        "sifrator_user_cache",
    )


def _join_app_subpath(base_dir: str, parts: tuple[str, ...], create: bool) -> str:
    cleaned = [str(part).strip("\\/") for part in parts if str(part or "").strip("\\/")]
    path = os.path.join(base_dir, APP_DATA_DIR_NAME, *cleaned)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def get_user_data_dir(*parts: str, create: bool = True) -> str:
    """Vrátí trvalou složku uživatelských dat mimo instalační adresář.

    Sem patří historie, plán tábora, poznámky a lokálně importované přílohy.
    Tato cesta se při aktualizaci aplikace nemá mazat ani přepisovat.
    """
    return _join_app_subpath(_user_data_base_dir(), parts, create)


def get_user_cache_dir(*parts: str, create: bool = True) -> str:
    """Vrátí uživatelskou cache složku mimo instalační adresář."""
    return _join_app_subpath(_user_cache_base_dir(), parts, create)


def _same_path(left: str, right: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))
    except Exception:
        return False


def _copy_missing_item(source: str, target: str) -> int:
    """Zkopíruje jen chybějící soubory, aby migrace nepřepsala novější data."""
    if not source or not os.path.exists(source) or _same_path(source, target):
        return 0

    copied = 0
    if os.path.isdir(source):
        os.makedirs(target, exist_ok=True)
        for current_root, _dirs, files in os.walk(source):
            relative = os.path.relpath(current_root, source)
            target_root = target if relative == "." else os.path.join(target, relative)
            os.makedirs(target_root, exist_ok=True)
            for file_name in files:
                source_file = os.path.join(current_root, file_name)
                target_file = os.path.join(target_root, file_name)
                if os.path.exists(target_file):
                    continue
                try:
                    shutil.copy2(source_file, target_file)
                    copied += 1
                except Exception:
                    continue
        return copied

    if os.path.isfile(source) and not os.path.exists(target):
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        shutil.copy2(source, target)
        return 1

    return copied


def migrate_user_data_items(legacy_roots: list[str], item_names: list[str], target_dir: str | None = None) -> int:
    """Přenese známé uživatelské soubory ze starých umístění do profilu uživatele."""
    target = target_dir or get_user_data_dir()
    os.makedirs(target, exist_ok=True)
    copied = 0
    seen: set[str] = set()

    for legacy_root in legacy_roots:
        if not legacy_root:
            continue
        root = os.path.abspath(os.path.expanduser(str(legacy_root)))
        key = os.path.normcase(root)
        if key in seen or _same_path(root, target) or not os.path.isdir(root):
            continue
        seen.add(key)

        for item_name in item_names:
            item = str(item_name or "").strip("\\/")
            if not item:
                continue
            source = os.path.join(root, item)
            destination = os.path.join(target, item)
            try:
                copied += _copy_missing_item(source, destination)
            except Exception:
                continue

    return copied


def get_icons_dir() -> str:
    """Vyhledá adresář s grafickými prostředky aplikace.

    Pořadí kandidátů pokrývá vývojové spuštění, Windows build,
    PyInstaller bundle i macOS .app strukturu s adresářem Resources.
    """
    candidates = [
        os.path.join(get_app_dir(), "icons"),
        os.path.join(get_script_dir(), "icons"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "icons"))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        candidates.append(os.path.join(contents_dir, "Resources", "icons"))

    for path in candidates:
        if path and os.path.isdir(path):
            return path

    return os.path.join(get_app_dir(), "icons")


# ============================================================
# UNICODE FALLBACK PRO NÁZVY SLOŽEK
# ============================================================

def _hash_unicode_component(text: str) -> str:
    """Vrátí název kompatibilní i s repozitáři, kde se diakritika uložila jako #Uxxxx."""
    result = []
    for ch in str(text):
        code = ord(ch)
        if code > 127:
            result.append(f"#U{code:04x}")
        else:
            result.append(ch)
    return "".join(result)


def _path_with_unicode_fallback(root: str, *parts: str) -> str:
    """Najde cestu nejdřív normálně a potom i s #Uxxxx fallback názvy."""
    variants = [list(parts)]
    encoded = [_hash_unicode_component(part) for part in parts]
    if encoded != list(parts):
        variants.append(encoded)

    if parts:
        for index, part in enumerate(parts):
            enc = _hash_unicode_component(part)
            if enc != part:
                current = list(parts)
                current[index] = enc
                variants.append(current)

    seen = set()
    for variant in variants:
        candidate = os.path.join(root, *variant)
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return os.path.join(root, *parts)


# ============================================================
# HLEDÁNÍ SOUBORŮ LOGIKY ŠIFER
# ============================================================

def get_cipher_logic_file(*parts) -> str:
    """Vrátí cestu k souboru v logika_sifer/... vedle main.py / EXE.

    Nové balíky používají ASCII názvy složek. Starý název "logika sifer"
    zůstává jako fallback pro starší rozbalené verze aplikace.
    """
    logic_dir_names = ("logika_sifer", "logika sifer")
    roots = []
    for logic_dir_name in logic_dir_names:
        roots.extend([
            os.path.join(get_app_dir(), logic_dir_name),
            os.path.join(get_script_dir(), logic_dir_name),
        ])

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        for logic_dir_name in logic_dir_names:
            roots.append(os.path.join(bundle_dir, logic_dir_name))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        for logic_dir_name in logic_dir_names:
            roots.append(os.path.join(contents_dir, "Resources", logic_dir_name))

    for root in roots:
        if root and os.path.isdir(root):
            candidate = _path_with_unicode_fallback(root, *parts)
            if os.path.exists(candidate):
                return candidate

    return os.path.join(get_app_dir(), "logika_sifer", *parts)


def get_pirate_key_renderer_file() -> str:
    """Vyhledá společný modul pro generování grafických klíčů šifer."""
    candidates = [
        os.path.join(get_app_dir(), "pirate_key_renderer.py"),
        os.path.join(get_script_dir(), "pirate_key_renderer.py"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "pirate_key_renderer.py"))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        candidates.append(os.path.join(contents_dir, "Resources", "pirate_key_renderer.py"))

    for path in candidates:
        if path and os.path.exists(path):
            return path

    return os.path.join(get_app_dir(), "pirate_key_renderer.py")


# ============================================================
# DYNAMICKÉ NAČÍTÁNÍ MODULŮ
# ============================================================

def load_python_module_from_path(module_name: str, file_path: str):
    """Dynamicky načte Python modul z konkrétní cesty v souborovém systému."""
    if not os.path.exists(file_path):
        return None

    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as error:
        print(f"CHYBA při načítání modulu {file_path}: {error}")
        return None
