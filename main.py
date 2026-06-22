APP_VERSION = "0.0.2"
APP_NAME = "Sifrator_Mraveniste"

import os
import sys
import tempfile
import time
import ctypes
import unicodedata
import importlib.util
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap, QTextOption, QPen, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QWidget,
    QGridLayout,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
)

from PySide6.QtWidgets import QComboBox, QSpinBox, QAbstractSpinBox

try:
    from PIL import Image
except Exception:
    Image = None

import update_manager

# Aktualizační modul je importovaný samostatně, aby bylo možné udržovat
# kontrolu nových verzí odděleně od hlavní logiky uživatelského rozhraní.


# ============================================================
# ŠIFRÁTOR MRAVENIŠTĚ – hlavní okno aplikace
#
# Modul řeší kompletní uživatelské rozhraní aplikace, načítání
# externích modulů jednotlivých šifer, vykreslování textových i
# grafických výstupů, tisk a napojení na aktualizační mechanismus.
#
# Grafické rozhraní je postavené nad hotovým skinem icons/BG.png.
# QPainter se používá pouze pro funkční a dynamické prvky, nikoli
# pro překreslování statického pozadí aplikace.
#
# Podporované režimy spuštění:
# - vývojové spuštění přímo z Pythonu,
# - Windows onedir build vytvořený přes PyInstaller,
# - macOS .app balíček vytvořený přes PyInstaller.
# ============================================================


BASE_W = 1672
BASE_H = 941



def get_app_dir():
    """Vrátí kořenovou složku běžící aplikace.

    Ve vývojovém režimu se používá adresář s main.py.
    U sestavené aplikace se používá adresář se spustitelným souborem.
    Díky tomu lze assety a podpůrné soubory hledat stejným způsobem
    ve vývoji i v produkčním buildu.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(__file__))


def get_script_dir():
    """Vrátí adresář zdrojového souboru main.py."""
    return os.path.dirname(os.path.abspath(__file__))


def get_pyinstaller_bundle_dir():
    """Vrátí interní dočasný adresář PyInstaller bundlu, pokud je dostupný."""
    return getattr(sys, "_MEIPASS", "")


def get_icons_dir():
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

    # macOS .app používá standardní strukturu Contents/MacOS -> Contents/Resources.
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        candidates.append(os.path.join(contents_dir, "Resources", "icons"))

    for path in candidates:
        if path and os.path.isdir(path):
            return path

    return os.path.join(get_app_dir(), "icons")



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


def get_cipher_logic_file(*parts):
    """Vrátí cestu k souboru v logika sifer/... vedle main.py / EXE.

    Podporuje normální české názvy složek i fallback názvy ve tvaru #Uxxxx,
    aby build fungoval stejně z Windows, GitHub ZIPu i GitHub Actions.
    """
    roots = [
        os.path.join(get_app_dir(), "logika sifer"),
        os.path.join(get_script_dir(), "logika sifer"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        roots.append(os.path.join(bundle_dir, "logika sifer"))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        roots.append(os.path.join(contents_dir, "Resources", "logika sifer"))

    for root in roots:
        if root and os.path.isdir(root):
            candidate = _path_with_unicode_fallback(root, *parts)
            if os.path.exists(candidate):
                return candidate

    return os.path.join(get_app_dir(), "logika sifer", *parts)


def get_morse_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Morseova abeceda/morseova_abeceda.py"""
    logic_file = get_cipher_logic_file("Morseova abeceda", "morseova_abeceda.py")
    return load_python_module_from_path("morseova_abeceda_logic", logic_file)


MORSE_LOGIC = None


def get_morse_logic():
    """Lazy načtení Morseovy logiky, aby aplikace startovala i při chybě souboru."""
    global MORSE_LOGIC

    if MORSE_LOGIC is None:
        MORSE_LOGIC = get_morse_logic_module()

    return MORSE_LOGIC


def get_binary_squares_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Binární čtverce/binarni_ctverce.py"""
    logic_file = get_cipher_logic_file("Binární čtverce", "binarni_ctverce.py")
    return load_python_module_from_path("binarni_ctverce_logic", logic_file)


BINARY_SQUARES_LOGIC = None


def get_binary_squares_logic():
    """Odloženě načte logiku Binárních čtverců až při prvním použití."""
    global BINARY_SQUARES_LOGIC

    if BINARY_SQUARES_LOGIC is None:
        BINARY_SQUARES_LOGIC = get_binary_squares_logic_module()

    return BINARY_SQUARES_LOGIC


def get_braille_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Brailovo písmo/brailovo_pismo.py"""
    logic_file = get_cipher_logic_file("Brailovo písmo", "brailovo_pismo.py")
    return load_python_module_from_path("brailovo_pismo_logic", logic_file)


BRAILLE_LOGIC = None


def get_braille_logic():
    """Odloženě načte logiku Braillova písma až při prvním použití."""
    global BRAILLE_LOGIC

    if BRAILLE_LOGIC is None:
        BRAILLE_LOGIC = get_braille_logic_module()

    return BRAILLE_LOGIC


def get_british_flag_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Britská vlajka/britska_vlajka.py"""
    logic_file = get_cipher_logic_file("Britská vlajka", "britska_vlajka.py")
    return load_python_module_from_path("britska_vlajka_logic", logic_file)


BRITISH_FLAG_LOGIC = None


def get_british_flag_logic():
    """Odloženě načte logiku a vykreslovacího widgetu Britské vlajky až při prvním použití."""
    global BRITISH_FLAG_LOGIC

    if BRITISH_FLAG_LOGIC is None:
        BRITISH_FLAG_LOGIC = get_british_flag_logic_module()

    return BRITISH_FLAG_LOGIC


def get_british_flag_widget_class():
    """Vrátí třídu BritishFlagOutputWidget načtenou z externího modulu britska_vlajka.py."""
    module = get_british_flag_logic()

    if module is None:
        return None

    return getattr(module, "BritishFlagOutputWidget", None)


def get_ctverec_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Čtverec/ctverec.py"""
    logic_file = get_cipher_logic_file("Čtverec", "ctverec.py")
    return load_python_module_from_path("ctverec_logic", logic_file)


CTVEREC_LOGIC = None


def get_ctverec_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Čtverec až při prvním použití."""
    global CTVEREC_LOGIC

    if CTVEREC_LOGIC is None:
        CTVEREC_LOGIC = get_ctverec_logic_module()

    return CTVEREC_LOGIC


def get_ctverec_widget_class():
    """Vrátí třídu CtverecOutputWidget načtenou z externího modulu ctverec.py."""
    module = get_ctverec_logic()

    if module is None:
        return None

    return getattr(module, "CtverecOutputWidget", None)


def get_hebrew_cross_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Hebrejský kříž/hebrejsky_kriz.py"""
    logic_file = get_cipher_logic_file("Hebrejský kříž", "hebrejsky_kriz.py")
    return load_python_module_from_path("hebrejsky_kriz_logic", logic_file)


HEBREW_CROSS_LOGIC = None


def get_hebrew_cross_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Hebrejský kříž až při prvním použití."""
    global HEBREW_CROSS_LOGIC

    if HEBREW_CROSS_LOGIC is None:
        HEBREW_CROSS_LOGIC = get_hebrew_cross_logic_module()

    return HEBREW_CROSS_LOGIC


def get_hebrew_cross_widget_class():
    """Vrátí třídu HebrejskyKrizOutputWidget načtenou z externího modulu hebrejsky_kriz.py."""
    module = get_hebrew_cross_logic()

    if module is None:
        return None

    return getattr(module, "HebrejskyKrizOutputWidget", None)


def get_small_polish_cross_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Malý polský kříž/maly_polsky_kriz.py"""
    logic_file = get_cipher_logic_file("Malý polský kříž", "maly_polsky_kriz.py")
    return load_python_module_from_path("maly_polsky_kriz_logic", logic_file)


SMALL_POLISH_CROSS_LOGIC = None


def get_small_polish_cross_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Malý polský kříž až při prvním použití."""
    global SMALL_POLISH_CROSS_LOGIC

    if SMALL_POLISH_CROSS_LOGIC is None:
        SMALL_POLISH_CROSS_LOGIC = get_small_polish_cross_logic_module()

    return SMALL_POLISH_CROSS_LOGIC


def get_small_polish_cross_widget_class():
    """Vrátí třídu MalyPolskyKrizOutputWidget načtenou z externího modulu maly_polsky_kriz.py."""
    module = get_small_polish_cross_logic()

    if module is None:
        return None

    return getattr(module, "MalyPolskyKrizOutputWidget", None)


def get_mobile_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Mobil/mobil.py"""
    logic_file = get_cipher_logic_file("Mobil", "mobil.py")
    return load_python_module_from_path("mobil_logic", logic_file)


MOBILE_LOGIC = None


def get_mobile_logic():
    """Odloženě načte logiku šifry Mobil až při prvním použití."""
    global MOBILE_LOGIC

    if MOBILE_LOGIC is None:
        MOBILE_LOGIC = get_mobile_logic_module()

    return MOBILE_LOGIC


def get_moon_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Moonovo písmo/moonovo_pismo.py"""
    logic_file = get_cipher_logic_file("Moonovo písmo", "moonovo_pismo.py")
    return load_python_module_from_path("moonovo_pismo_logic", logic_file)


MOON_LOGIC = None


def get_moon_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Moonovo písmo až při prvním použití."""
    global MOON_LOGIC

    if MOON_LOGIC is None:
        MOON_LOGIC = get_moon_logic_module()

    return MOON_LOGIC


def get_moon_widget_class():
    """Vrátí třídu MoonovoPismoOutputWidget načtenou z externího modulu moonovo_pismo.py."""
    module = get_moon_logic()

    if module is None:
        return None

    return getattr(module, "MoonovoPismoOutputWidget", None)


def get_morse_hory_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Morseova abeceda – hory/morseova_abeceda_hory.py"""
    logic_file = get_cipher_logic_file("Morseova abeceda – hory", "morseova_abeceda_hory.py")
    return load_python_module_from_path("morseova_abeceda_hory_logic", logic_file)


MORSE_HORY_LOGIC = None


def get_morse_hory_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Morseova abeceda – hory až při prvním použití."""
    global MORSE_HORY_LOGIC

    if MORSE_HORY_LOGIC is None:
        MORSE_HORY_LOGIC = get_morse_hory_logic_module()

    return MORSE_HORY_LOGIC


def get_morse_hory_widget_class():
    """Vrátí třídu MorseHoryOutputWidget načtenou z externího modulu morseova_abeceda_hory.py."""
    module = get_morse_hory_logic()

    if module is None:
        return None

    return getattr(module, "MorseHoryOutputWidget", None)


def get_morse_pila_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Morseova abeceda – pila/morseova_abeceda_pila.py"""
    logic_file = get_cipher_logic_file("Morseova abeceda – pila", "morseova_abeceda_pila.py")
    return load_python_module_from_path("morseova_abeceda_pila_logic", logic_file)


MORSE_PILA_LOGIC = None


def get_morse_pila_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Morseova abeceda – pila až při prvním použití."""
    global MORSE_PILA_LOGIC

    if MORSE_PILA_LOGIC is None:
        MORSE_PILA_LOGIC = get_morse_pila_logic_module()

    return MORSE_PILA_LOGIC


def get_morse_pila_widget_class():
    """Vrátí třídu MorsePilaOutputWidget načtenou z externího modulu morseova_abeceda_pila.py."""
    module = get_morse_pila_logic()

    if module is None:
        return None

    return getattr(module, "MorsePilaOutputWidget", None)


def get_morse_stromy_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Morseova abeceda – stromy/morseova_abeceda_stromy.py"""
    logic_file = get_cipher_logic_file("Morseova abeceda – stromy", "morseova_abeceda_stromy.py")
    return load_python_module_from_path("morseova_abeceda_stromy_logic", logic_file)


MORSE_STROMY_LOGIC = None


def get_morse_stromy_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Morseova abeceda – stromy až při prvním použití."""
    global MORSE_STROMY_LOGIC

    if MORSE_STROMY_LOGIC is None:
        MORSE_STROMY_LOGIC = get_morse_stromy_logic_module()

    return MORSE_STROMY_LOGIC


def get_morse_stromy_widget_class():
    """Vrátí třídu MorseStromyOutputWidget načtenou z externího modulu morseova_abeceda_stromy.py."""
    module = get_morse_stromy_logic()

    if module is None:
        return None

    return getattr(module, "MorseStromyOutputWidget", None)


def get_mriz_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Mříž/mriz.py"""
    logic_file = get_cipher_logic_file("Mříž", "mriz.py")
    return load_python_module_from_path("mriz_logic", logic_file)


MRIZ_LOGIC = None


def get_mriz_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Mříž až při prvním použití."""
    global MRIZ_LOGIC

    if MRIZ_LOGIC is None:
        MRIZ_LOGIC = get_mriz_logic_module()

    return MRIZ_LOGIC


def get_mriz_widget_class():
    """Vrátí třídu MrizOutputWidget načtenou z externího modulu mriz.py."""
    module = get_mriz_logic()

    if module is None:
        return None

    return getattr(module, "MrizOutputWidget", None)


def get_okno_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Okno/okno.py"""
    logic_file = get_cipher_logic_file("Okno", "okno.py")
    return load_python_module_from_path("okno_logic", logic_file)


OKNO_LOGIC = None


def get_okno_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Okno až při prvním použití."""
    global OKNO_LOGIC

    if OKNO_LOGIC is None:
        OKNO_LOGIC = get_okno_logic_module()

    return OKNO_LOGIC


def get_okno_widget_class():
    """Vrátí třídu OknoOutputWidget načtenou z externího modulu okno.py."""
    module = get_okno_logic()

    if module is None:
        return None

    return getattr(module, "OknoOutputWidget", None)


def get_pavouci_sit_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Pavoučí síť/pavouci_sit.py"""
    logic_file = get_cipher_logic_file("Pavoučí síť", "pavouci_sit.py")
    return load_python_module_from_path("pavouci_sit_logic", logic_file)


PAVOUCI_SIT_LOGIC = None


def get_pavouci_sit_logic():
    """Odloženě načte logiku šifry Pavoučí síť až při prvním použití."""
    global PAVOUCI_SIT_LOGIC

    if PAVOUCI_SIT_LOGIC is None:
        PAVOUCI_SIT_LOGIC = get_pavouci_sit_logic_module()

    return PAVOUCI_SIT_LOGIC


def get_posunkova_abeceda_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Posunková abeceda/posunkova_abeceda.py"""
    logic_file = get_cipher_logic_file("Posunková abeceda", "posunkova_abeceda.py")
    return load_python_module_from_path("posunkova_abeceda_logic", logic_file)


POSUNKOVA_ABECEDA_LOGIC = None


def get_posunkova_abeceda_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Posunková abeceda až při prvním použití."""
    global POSUNKOVA_ABECEDA_LOGIC

    if POSUNKOVA_ABECEDA_LOGIC is None:
        POSUNKOVA_ABECEDA_LOGIC = get_posunkova_abeceda_logic_module()

    return POSUNKOVA_ABECEDA_LOGIC


def get_posunkova_abeceda_widget_class():
    """Vrátí třídu PosunkovaAbecedaOutputWidget načtenou z externího modulu posunkova_abeceda.py."""
    module = get_posunkova_abeceda_logic()

    if module is None:
        return None

    return getattr(module, "PosunkovaAbecedaOutputWidget", None)


def get_pseudo_cina_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Pseudo-Čína/pseudo_cina.py"""
    logic_file = get_cipher_logic_file("Pseudo-Čína", "pseudo_cina.py")
    return load_python_module_from_path("pseudo_cina_logic", logic_file)


PSEUDO_CINA_LOGIC = None


def get_pseudo_cina_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Pseudo-Čína až při prvním použití."""
    global PSEUDO_CINA_LOGIC

    if PSEUDO_CINA_LOGIC is None:
        PSEUDO_CINA_LOGIC = get_pseudo_cina_logic_module()

    return PSEUDO_CINA_LOGIC


def get_pseudo_cina_widget_class():
    """Vrátí třídu PseudoCinaOutputWidget načtenou z externího modulu pseudo_cina.py."""
    module = get_pseudo_cina_logic()

    if module is None:
        return None

    return getattr(module, "PseudoCinaOutputWidget", None)


def get_semafor_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Semafor/semafor.py"""
    logic_file = get_cipher_logic_file("Semafor", "semafor.py")
    return load_python_module_from_path("semafor_logic", logic_file)


SEMAFOR_LOGIC = None


def get_semafor_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Semafor až při prvním použití."""
    global SEMAFOR_LOGIC

    if SEMAFOR_LOGIC is None:
        SEMAFOR_LOGIC = get_semafor_logic_module()

    return SEMAFOR_LOGIC


def get_semafor_widget_class():
    """Vrátí třídu SemaforOutputWidget načtenou z externího modulu semafor.py."""
    module = get_semafor_logic()

    if module is None:
        return None

    return getattr(module, "SemaforOutputWidget", None)


def get_superkrychle_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/SuperKrychle/superkrychle.py"""
    logic_file = get_cipher_logic_file("SuperKrychle", "superkrychle.py")
    return load_python_module_from_path("superkrychle_logic", logic_file)


SUPERKRYCHLE_LOGIC = None


def get_superkrychle_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry SuperKrychle až při prvním použití."""
    global SUPERKRYCHLE_LOGIC

    if SUPERKRYCHLE_LOGIC is None:
        SUPERKRYCHLE_LOGIC = get_superkrychle_logic_module()

    return SUPERKRYCHLE_LOGIC


def get_superkrychle_widget_class():
    """Vrátí třídu SuperKrychleOutputWidget načtenou z externího modulu superkrychle.py."""
    module = get_superkrychle_logic()

    if module is None:
        return None

    return getattr(module, "SuperKrychleOutputWidget", None)


def get_tancici_figurky_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Tančící figurky/tancici_figurky.py"""
    logic_file = get_cipher_logic_file("Tančící figurky", "tancici_figurky.py")
    return load_python_module_from_path("tancici_figurky_logic", logic_file)


TANCICI_FIGURKY_LOGIC = None


def get_tancici_figurky_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Tančící figurky až při prvním použití."""
    global TANCICI_FIGURKY_LOGIC

    if TANCICI_FIGURKY_LOGIC is None:
        TANCICI_FIGURKY_LOGIC = get_tancici_figurky_logic_module()

    return TANCICI_FIGURKY_LOGIC


def get_tancici_figurky_widget_class():
    """Vrátí třídu TanciciFigurkyOutputWidget načtenou z externího modulu tancici_figurky.py."""
    module = get_tancici_figurky_logic()

    if module is None:
        return None

    return getattr(module, "TanciciFigurkyOutputWidget", None)


def get_tancici_figurky_ii_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Tančící figurky II/tancici_figurky_2.py"""
    logic_file = get_cipher_logic_file("Tančící figurky II", "tancici_figurky_2.py")
    return load_python_module_from_path("tancici_figurky_ii_logic", logic_file)


TANCICI_FIGURKY_II_LOGIC = None


def get_tancici_figurky_ii_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Tančící figurky II až při prvním použití."""
    global TANCICI_FIGURKY_II_LOGIC

    if TANCICI_FIGURKY_II_LOGIC is None:
        TANCICI_FIGURKY_II_LOGIC = get_tancici_figurky_ii_logic_module()

    return TANCICI_FIGURKY_II_LOGIC


def get_tancici_figurky_ii_widget_class():
    """Vrátí třídu TanciciFigurkyIIOutputWidget načtenou z externího modulu tancici_figurky_2.py."""
    module = get_tancici_figurky_ii_logic()

    if module is None:
        return None

    return getattr(module, "TanciciFigurkyIIOutputWidget", None)


def get_velky_polsky_kriz_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Velký polský kříž/velky_polsky_kriz.py"""
    logic_file = get_cipher_logic_file("Velký polský kříž", "velky_polsky_kriz.py")
    return load_python_module_from_path("velky_polsky_kriz_logic", logic_file)


VELKY_POLSKY_KRIZ_LOGIC = None


def get_velky_polsky_kriz_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Velký polský kříž až při prvním použití."""
    global VELKY_POLSKY_KRIZ_LOGIC

    if VELKY_POLSKY_KRIZ_LOGIC is None:
        VELKY_POLSKY_KRIZ_LOGIC = get_velky_polsky_kriz_logic_module()

    return VELKY_POLSKY_KRIZ_LOGIC


def get_velky_polsky_kriz_widget_class():
    """Vrátí třídu VelkyPolskyKrizOutputWidget načtenou z externího modulu velky_polsky_kriz.py."""
    module = get_velky_polsky_kriz_logic()

    if module is None:
        return None

    return getattr(module, "VelkyPolskyKrizOutputWidget", None)


def get_velky_polsky_kriz_26_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Velký polský kříž (26 znaků)/velky_polsky_kriz_26.py"""
    logic_file = get_cipher_logic_file("Velký polský kříž (26 znaků)", "velky_polsky_kriz_26.py")
    return load_python_module_from_path("velky_polsky_kriz_26_logic", logic_file)


VELKY_POLSKY_KRIZ_26_LOGIC = None


def get_velky_polsky_kriz_26_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Velký polský kříž (26 znaků) až při prvním použití."""
    global VELKY_POLSKY_KRIZ_26_LOGIC

    if VELKY_POLSKY_KRIZ_26_LOGIC is None:
        VELKY_POLSKY_KRIZ_26_LOGIC = get_velky_polsky_kriz_26_logic_module()

    return VELKY_POLSKY_KRIZ_26_LOGIC


def get_velky_polsky_kriz_26_widget_class():
    """Vrátí třídu VelkyPolskyKriz26OutputWidget načtenou z externího modulu velky_polsky_kriz_26.py."""
    module = get_velky_polsky_kriz_26_logic()

    if module is None:
        return None

    return getattr(module, "VelkyPolskyKriz26OutputWidget", None)


def get_vlcacka_sifra_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Vlčácká šifra/vlcacka_sifra.py"""
    logic_file = get_cipher_logic_file("Vlčácká šifra", "vlcacka_sifra.py")
    return load_python_module_from_path("vlcacka_sifra_logic", logic_file)


VLCACKA_SIFRA_LOGIC = None


def get_vlcacka_sifra_logic():
    """Odloženě načte logiku šifry Vlčácká šifra až při prvním použití."""
    global VLCACKA_SIFRA_LOGIC

    if VLCACKA_SIFRA_LOGIC is None:
        VLCACKA_SIFRA_LOGIC = get_vlcacka_sifra_logic_module()

    return VLCACKA_SIFRA_LOGIC



def get_zamena_pismen_a_z_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Záměna písmen (A=Z)/zamena_pismen_a_z.py"""
    logic_file = get_cipher_logic_file("Záměna písmen (A=Z)", "zamena_pismen_a_z.py")
    return load_python_module_from_path("zamena_pismen_a_z_logic", logic_file)


ZAMENA_PISMEN_A_Z_LOGIC = None


def get_zamena_pismen_a_z_logic():
    """Odloženě načte logiku šifry Záměna písmen (A=Z) až při prvním použití."""
    global ZAMENA_PISMEN_A_Z_LOGIC

    if ZAMENA_PISMEN_A_Z_LOGIC is None:
        ZAMENA_PISMEN_A_Z_LOGIC = get_zamena_pismen_a_z_logic_module()

    return ZAMENA_PISMEN_A_Z_LOGIC


def get_zamena_cisla_a01_z26_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Záměna písmen za čísla (A=01, Z=26)/zamena_cisla_a01_z26.py"""
    logic_file = get_cipher_logic_file("Záměna písmen za čísla (A=01, Z=26)", "zamena_cisla_a01_z26.py")
    return load_python_module_from_path("zamena_cisla_a01_z26_logic", logic_file)


ZAMENA_CISLA_A01_Z26_LOGIC = None


def get_zamena_cisla_a01_z26_logic():
    """Odloženě načte logiku šifry Záměna písmen za čísla (A=01, Z=26) až při prvním použití."""
    global ZAMENA_CISLA_A01_Z26_LOGIC

    if ZAMENA_CISLA_A01_Z26_LOGIC is None:
        ZAMENA_CISLA_A01_Z26_LOGIC = get_zamena_cisla_a01_z26_logic_module()

    return ZAMENA_CISLA_A01_Z26_LOGIC


def get_zamena_cisla_a26_z01_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Záměna písmen za čísla (A=26, Z=01)/zamena_cisla_a26_z01.py"""
    logic_file = get_cipher_logic_file("Záměna písmen za čísla (A=26, Z=01)", "zamena_cisla_a26_z01.py")
    return load_python_module_from_path("zamena_cisla_a26_z01_logic", logic_file)


ZAMENA_CISLA_A26_Z01_LOGIC = None


def get_zamena_cisla_a26_z01_logic():
    """Odloženě načte logiku šifry Záměna písmen za čísla (A=26, Z=01) až při prvním použití."""
    global ZAMENA_CISLA_A26_Z01_LOGIC

    if ZAMENA_CISLA_A26_Z01_LOGIC is None:
        ZAMENA_CISLA_A26_Z01_LOGIC = get_zamena_cisla_a26_z01_logic_module()

    return ZAMENA_CISLA_A26_Z01_LOGIC


def get_zlomky_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Zlomky/zlomky.py"""
    logic_file = get_cipher_logic_file("Zlomky", "zlomky.py")
    return load_python_module_from_path("zlomky_logic", logic_file)


ZLOMKY_LOGIC = None


def get_zlomky_logic():
    """Odloženě načte logiku šifry Zlomky až při prvním použití."""
    global ZLOMKY_LOGIC

    if ZLOMKY_LOGIC is None:
        ZLOMKY_LOGIC = get_zlomky_logic_module()

    return ZLOMKY_LOGIC


def get_caesar_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Caesarova šifra/caesarova_sifra.py"""
    logic_file = get_cipher_logic_file("Caesarova šifra", "caesarova_sifra.py")
    return load_python_module_from_path("caesarova_sifra_logic", logic_file)


CAESAR_LOGIC = None


def get_caesar_logic():
    """Odloženě načte logiku šifry Caesarova šifra až při prvním použití."""
    global CAESAR_LOGIC

    if CAESAR_LOGIC is None:
        CAESAR_LOGIC = get_caesar_logic_module()

    return CAESAR_LOGIC


# ============================================================
# SPOLEČNÝ RENDERER KLÍČŮ ŠIFER
# ============================================================

def get_pirate_key_renderer_file():
    """Vyhledá společný modul pro generování grafických klíčů šifer.

    Cesty jsou řazené tak, aby fungovaly ve vývoji, ve Windows onedir buildu
    i v macOS .app balíčku.
    """
    candidates = [
        os.path.join(get_app_dir(), "pirate_key_renderer.py"),
        os.path.join(get_script_dir(), "pirate_key_renderer.py"),
        os.path.join(get_app_dir(), "logika sifer", "spolecne", "pirate_key_renderer.py"),
        os.path.join(get_script_dir(), "logika sifer", "spolecne", "pirate_key_renderer.py"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "pirate_key_renderer.py"))
        candidates.append(os.path.join(bundle_dir, "logika sifer", "spolecne", "pirate_key_renderer.py"))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        resources_dir = os.path.join(contents_dir, "Resources")
        candidates.append(os.path.join(resources_dir, "pirate_key_renderer.py"))
        candidates.append(os.path.join(resources_dir, "logika sifer", "spolecne", "pirate_key_renderer.py"))

    for path in candidates:
        if path and os.path.exists(path):
            return path

    return os.path.join(get_app_dir(), "pirate_key_renderer.py")


PIRATE_KEY_RENDERER = None


def get_pirate_key_renderer():
    """Odloženě načte společný renderer klíčů až při jeho prvním použití."""
    global PIRATE_KEY_RENDERER

    if PIRATE_KEY_RENDERER is None:
        PIRATE_KEY_RENDERER = load_python_module_from_path(
            "pirate_key_renderer_logic",
            get_pirate_key_renderer_file(),
        )

    return PIRATE_KEY_RENDERER


class Colors:
    GOLD = "#c89a4c"
    GOLD_LIGHT = "#f3d79a"
    GOLD_TEXT = "#e7c681"
    DARK_TEXT = "#1f1205"
    TEXT_LIGHT = "#ead8b3"
    PLACEHOLDER = "#a8a295"
    SELECT_CYAN = "#15c1cc"



@dataclass
class CipherItem:
    name: str
    icon: str


class TransparentActionButton(QPushButton):
    """Transparentní akční tlačítko vykreslované nad grafickým skinem.

    Popisek i ikona zámku se kreslí ručně, aby zůstaly přesně zarovnané
    vůči dekorativnímu tlačítku v pozadí.
    """

    def __init__(self, text: str, icon_path: str = "", parent=None):
        super().__init__("", parent)
        self.full_text = text
        self.lock_pixmap = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        self._hovered = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Georgia", 20, QFont.Bold))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Hover efekt je záměrně jemný, aby nepřekrýval grafický skin tlačítka.
        if self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 120, 28))
            painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 10, 10)

        painter.setFont(self.font())
        fm = painter.fontMetrics()

        # Velikost ikony se dopočítává relativně k výšce tlačítka.
        icon_size = max(46, min(74, int(self.height() * 0.88)))
        gap = max(14, int(self.width() * 0.040))
        text_w = fm.horizontalAdvance(self.full_text)

        center_y = self.height() // 2
        vertical_shift = max(2, int(self.height() * 0.04))

        # Text je opticky centrovaný vůči dekorativní ploše tlačítka.
        # Jemný vertikální posun kompenzuje optiku dekorativního tlačítka.
        text_x = int((self.width() - text_w) / 2)
        icon_x = int(text_x - gap - icon_size)

        # U úzkého tlačítka se ikona a text zarovnají jako jeden společný blok.
        if icon_x < 8:
            total_w = icon_size + gap + text_w
            group_x = int((self.width() - total_w) / 2)
            icon_x = group_x
            text_x = group_x + icon_size + gap

        # Ikona zámku se škáluje plynule podle aktuální velikosti tlačítka.
        if not self.lock_pixmap.isNull():
            scaled = self.lock_pixmap.scaled(
                QSize(icon_size, icon_size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            draw_icon_x = icon_x + (icon_size - scaled.width()) // 2
            draw_icon_y = center_y - scaled.height() // 2 + vertical_shift
            painter.drawPixmap(draw_icon_x, draw_icon_y, scaled)

        text_color = QColor("#fff0bd") if self._hovered else QColor(Colors.GOLD_LIGHT)
        painter.setPen(QPen(text_color))
        text_rect = QRect(
            text_x,
            vertical_shift,
            text_w + 10,
            self.height() - vertical_shift,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.full_text)


class CipherButton(QPushButton):
    def __init__(self, item: CipherItem, icon_path: str, parent=None):
        super().__init__(item.name, parent)
        self.item = item
        self.full_text = item.name
        self.selected = False

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(50)
        self.setMinimumWidth(0)
        self.setFont(QFont("Georgia", 12))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(38, 38))

        self.refresh_style()
        self.update_elided_text()

    def minimumSizeHint(self):
        return QSize(40, self.minimumHeight())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elided_text()

    def update_elided_text(self):
        icon_w = self.iconSize().width() if not self.icon().isNull() else 0
        available = max(35, self.width() - icon_w - 34)
        shown = self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, available)

        if self.text() != shown:
            self.setText(shown)

        self.setToolTip(self.full_text)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.refresh_style()

    def refresh_style(self):
        if self.selected:
            border = Colors.SELECT_CYAN
            bg = "rgba(0, 120, 130, 105)"
            width = 2
        else:
            border = "rgba(165, 113, 49, 120)"
            bg = "rgba(7, 18, 22, 155)"
            width = 1

        self.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_LIGHT};
                text-align: left;
                border: {width}px solid {border};
                border-radius: 8px;
                padding-left: 8px;
                padding-right: 4px;
                background-color: {bg};
            }}
            QPushButton:hover {{
                border: 2px solid {Colors.GOLD_LIGHT};
                background-color: rgba(20, 45, 50, 180);
            }}
        """)
        self.update_elided_text()


class SifratorSkinWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Poznámka k produkčnímu buildu a aktualizacím:
        # assets_path ukazuje na kořen aplikace, icons_path na adresář s grafickými prostředky.
        self.assets_path = get_app_dir()
        self.icons_path = get_icons_dir()

        # Statické pozadí rozhraní se načítá z icons/BG.png.
        self.skin_path = self.find_asset(["BG.png", "bg.png"])
        self.logo_path = self.find_asset(["logo.png", "Logo.png"])

        self.skin_pixmap = QPixmap(self.skin_path) if self.skin_path else QPixmap()
        self.logo_pixmap = self.load_logo_pixmap(self.logo_path) if self.logo_path else QPixmap()

        self.ciphers = self.build_cipher_list()
        # Aplikace startuje bez předvybrané šifry.
        # Výběr šifry tak vždy probíhá vědomě přes levý seznam.
        self.selected_cipher = None
        self.result_mode = None
        self.cipher_buttons = []

        # Minimální velikost samotného skinu je snížená kvůli malým displejům.
        # Skutečná čitelnost na malých oknech se řeší přes scrollovací obal v SifratorWindow.
        self.setMinimumSize(800, 600)
        self.create_widgets()
        self.print_missing_assets()
        self.update_layout_positions()

    # ------------------------------------------------------------
    # Geometrie rozhraní a vyhledávání assetů
    # ------------------------------------------------------------

    def sx(self):
        return self.width() / BASE_W

    def sy(self):
        return self.height() / BASE_H

    def sc(self):
        return min(self.sx(), self.sy())

    def sr(self, x, y, w, h):
        return QRect(
            int(x * self.sx()),
            int(y * self.sy()),
            int(w * self.sx()),
            int(h * self.sy()),
        )

    def fs(self, size):
        return max(8, int(size * self.sc()))

    def find_asset(self, names):
        search_folders = [
            self.icons_path,
            self.assets_path,
            get_script_dir(),
        ]

        bundle_dir = get_pyinstaller_bundle_dir()
        if bundle_dir:
            search_folders.append(bundle_dir)
            search_folders.append(os.path.join(bundle_dir, "icons"))

        used = set()
        for folder in search_folders:
            if not folder or folder in used:
                continue

            used.add(folder)

            for name in names:
                path = os.path.join(folder, name)
                if os.path.exists(path):
                    return path

        return None

    def icon_path(self, file_name):
        return self.find_icon_path(file_name)

    def find_icon_path(self, file_name):
        file_names = [file_name]
        encoded_name = _hash_unicode_component(file_name) if '_hash_unicode_component' in globals() else file_name
        if encoded_name != file_name:
            file_names.append(encoded_name)

        folders = [
            self.icons_path,
            os.path.join(get_app_dir(), "icons"),
            os.path.join(get_script_dir(), "icons"),
        ]

        bundle_dir = get_pyinstaller_bundle_dir()
        if bundle_dir:
            folders.append(os.path.join(bundle_dir, "icons"))

        for folder in folders:
            for name in file_names:
                path = os.path.join(folder, name)
                if path and os.path.exists(path):
                    return path

        return os.path.join(self.icons_path, file_name)

    def load_pixmap(self, file_name):
        path = self.find_icon_path(file_name)
        if os.path.exists(path):
            return QPixmap(path)
        return QPixmap()

    def load_logo_pixmap(self, path):
        if not path:
            return QPixmap()

        if Image is None:
            return QPixmap(path)

        try:
            img = Image.open(path).convert("RGBA")
            bbox = img.getchannel("A").getbbox()
            if bbox:
                img = img.crop(bbox)

            w, h = img.size
            raw = img.tobytes("raw", "RGBA")
            qimg = QImage(raw, w, h, QImage.Format_RGBA8888).copy()
            return QPixmap.fromImage(qimg)
        except Exception:
            return QPixmap(path)

    def print_missing_assets(self):
        required = ["BG.png", "logo.png", "lock_closed.png", "lock_open.png"]
        required += [item.icon for item in self.ciphers]

        missing = []
        for file_name in required:
            if not os.path.exists(self.find_icon_path(file_name)):
                missing.append(file_name)

        if missing:
            print("\nCHYBĚJÍCÍ SOUBORY VE SLOŽCE icons:")
            for file_name in missing:
                print(" -", file_name)
            print()
        else:
            print("Všechny potřebné soubory ve složce icons byly nalezeny.")

    # ------------------------------------------------------------
    # Definice dostupných šifer
    # ------------------------------------------------------------

    def build_cipher_list(self):
        items = [
            CipherItem("Binární čtverce", "binarni_ctverce.png"),
            CipherItem("Brailovo písmo", "brailovo_pismo.png"),
            CipherItem("Britská vlajka", "britska_vlajka.png"),
            CipherItem("Caesarova šifra", "Cesarova šifra.png"),
            CipherItem("Čtverec", "ctverec.png"),
            CipherItem("Hebrejský kříž", "hebrejsky_kriz.png"),
            CipherItem("Malý polský kříž", "maly_polsky_kriz.png"),
            CipherItem("Mobil", "mobil.png"),
            CipherItem("Moonovo písmo", "moonovo_pismo.png"),
            CipherItem("Morseova abeceda", "morseova_abeceda.png"),
            CipherItem("Morseova abeceda – hory", "morseova_hory.png"),
            CipherItem("Morseova abeceda – pila", "morseova_pila.png"),
            CipherItem("Morseova abeceda – stromy", "morseova_stromy.png"),
            CipherItem("Mříž", "mriz.png"),
            CipherItem("Okno", "okno.png"),
            CipherItem("Pavoučí síť", "pavouci_sit.png"),
            CipherItem("Posunková abeceda", "posunkova_abeceda.png"),
            CipherItem("Pseudo-Čína", "pseudo_cina.png"),
            CipherItem("Semafor", "semafor.png"),
            CipherItem("SuperKrychle", "superkrychle.png"),
            CipherItem("Tančící figurky", "tancici_figurky.png"),
            CipherItem("Tančící figurky II", "tancici_figurky_2.png"),
            CipherItem("Velký polský kříž", "velky_polsky_kriz.png"),
            CipherItem("Velký polský kříž (26 znaků)", "velky_polsky_kriz_26.png"),
            CipherItem("Vlčácká šifra", "vlcacka_sifra.png"),
            CipherItem("Záměna písmen (A=Z)", "zamena_pismen_a_z.png"),
            CipherItem("Záměna písmen za čísla (A=01, Z=26)", "zamena_cisla_a01_z26.png"),
            CipherItem("Záměna písmen za čísla (A=26, Z=01)", "zamena_cisla_a26_z01.png"),
            CipherItem("Zednářská šifra", "zednarska_sifra.png"),
            CipherItem("Zlomky", "zlomky.png"),
        ]

        def sort_key(item):
            text = unicodedata.normalize("NFKD", item.name.lower())
            return "".join(ch for ch in text if not unicodedata.combining(ch))

        return sorted(items, key=sort_key)


    def selected_icon_file(self):
        for item in self.ciphers:
            if item.name == self.selected_cipher:
                return item.icon
        return ""

    # ------------------------------------------------------------
    # Inicializace uživatelského rozhraní
    # ------------------------------------------------------------

    def create_widgets(self):
        self.logo_label = QLabel(self)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent;")

        self.title_left = QLabel(f"VYBER SI ŠIFRU ({len(self.ciphers)})", self)
        self.title_left.setStyleSheet(f"color: {Colors.GOLD_LIGHT}; background: transparent;")

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Hledej šifru...")
        self.search_edit.textChanged.connect(self.filter_ciphers)

        self.search_icon = QLabel("⌕", self)
        self.search_icon.setAlignment(Qt.AlignCenter)
        self.search_icon.setStyleSheet(f"color: {Colors.GOLD}; background: transparent;")

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(8, 8, 10, 8)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(6)
        self.grid.setAlignment(Qt.AlignTop)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.scroll_area.setWidget(self.scroll_content)

        for index, item in enumerate(self.ciphers):
            btn = CipherButton(item, self.icon_path(item.icon), self.scroll_content)
            btn.clicked.connect(lambda checked=False, name=item.name: self.select_cipher(name))
            self.grid.addWidget(btn, index // 2, index % 2, alignment=Qt.AlignTop)
            self.cipher_buttons.append(btn)

        self.selected_title = QLabel(self)
        self.selected_title.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        self.selected_title.setStyleSheet("color: #f0d19a; background: transparent;")

        self.selected_icon = QLabel(self)
        self.selected_icon.setAlignment(Qt.AlignCenter)
        self.selected_icon.setStyleSheet("background: transparent;")

        self.input_label = QLabel("ZADEJ TAJNOU ZPRÁVU", self)
        self.input_label.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        self.input_label.setStyleSheet(f"color: {Colors.GOLD_LIGHT}; background: transparent;")

        self.input_text = QTextEdit(self)
        self.input_text.setPlaceholderText("Zadej tajnou zprávu...")
        # Text se přepočítává automaticky při změně vstupu, bez nutnosti ručního potvrzení.
        self.input_text.textChanged.connect(self.auto_encrypt_action)

        self.encrypt_button = TransparentActionButton("ZAŠIFROVAT", self.icon_path("lock_closed.png"), self)
        self.decrypt_button = TransparentActionButton("DEŠIFROVAT", self.icon_path("lock_open.png"), self)
        self.encrypt_button.clicked.connect(self.encrypt_action)
        self.decrypt_button.clicked.connect(self.decrypt_action)

        self.key_button = QPushButton("KLÍČ", self)
        self.key_button.setCursor(Qt.PointingHandCursor)
        self.key_button.clicked.connect(self.show_cipher_key)
        self.key_button.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.GOLD_LIGHT};
                background-color: rgba(7, 18, 22, 155);
                border: 1px solid rgba(200, 154, 76, 180);
                border-radius: 9px;
                padding-left: 12px;
                padding-right: 12px;
            }}
            QPushButton:hover {{
                color: #fff0bd;
                border: 2px solid {Colors.GOLD_LIGHT};
                background-color: rgba(20, 45, 50, 185);
            }}
            QPushButton:disabled {{
                color: rgba(230, 210, 170, 90);
                border: 1px solid rgba(165, 113, 49, 70);
                background-color: rgba(7, 18, 22, 80);
            }}
        """)
        self.key_button.setEnabled(False)

        self.result_title = QLabel("VÝSLEDEK", self)
        self.result_title.setStyleSheet(f"color: {Colors.GOLD_LIGHT}; background: transparent;")

        self.output_text = QTextEdit(self)
        self.output_text.setPlaceholderText("Zašifrovaný text se objeví zde...")
        self.output_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.output_text.setWordWrapMode(QTextOption.WrapAnywhere)

        # Grafický výstup Britské vlajky je vložen do samostatné scrollovací oblasti.
        # Kreslicí widget dynamicky upravuje výšku podle rozsahu výsledku.
        self.british_flag_canvas = self.create_british_flag_canvas()

        self.british_flag_scroll = QScrollArea(self)
        self.british_flag_scroll.setWidgetResizable(False)
        self.british_flag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.british_flag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.british_flag_scroll.setFrameShape(QScrollArea.NoFrame)
        self.british_flag_scroll.setWidget(self.british_flag_canvas)
        self.british_flag_scroll.hide()

        # Grafický výstup šifry Čtverec.
        # Implementace používá stejný princip jako Britská vlajka: widget uvnitř QScrollArea.
        self.ctverec_canvas = self.create_ctverec_canvas()

        self.ctverec_scroll = QScrollArea(self)
        self.ctverec_scroll.setWidgetResizable(False)
        self.ctverec_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.ctverec_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ctverec_scroll.setFrameShape(QScrollArea.NoFrame)
        self.ctverec_scroll.setWidget(self.ctverec_canvas)
        self.ctverec_scroll.hide()

        # Grafický výstup šifry Hebrejský kříž.
        # Implementace využívá stejný QScrollArea mechanismus jako ostatní grafické šifry.
        self.hebrew_cross_canvas = self.create_hebrew_cross_canvas()

        self.hebrew_cross_scroll = QScrollArea(self)
        self.hebrew_cross_scroll.setWidgetResizable(False)
        self.hebrew_cross_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.hebrew_cross_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.hebrew_cross_scroll.setFrameShape(QScrollArea.NoFrame)
        self.hebrew_cross_scroll.setWidget(self.hebrew_cross_canvas)
        self.hebrew_cross_scroll.hide()

        # Grafický výstup šifry Malý polský kříž.
        # Výstup je zpracovaný jednotným scrollovacím mechanismem pro grafické šifry.
        self.small_polish_cross_canvas = self.create_small_polish_cross_canvas()

        self.small_polish_cross_scroll = QScrollArea(self)
        self.small_polish_cross_scroll.setWidgetResizable(False)
        self.small_polish_cross_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.small_polish_cross_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.small_polish_cross_scroll.setFrameShape(QScrollArea.NoFrame)
        self.small_polish_cross_scroll.setWidget(self.small_polish_cross_canvas)
        self.small_polish_cross_scroll.hide()

        # Grafický výstup šifry Moonovo písmo.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.moon_canvas = self.create_moon_canvas()

        self.moon_scroll = QScrollArea(self)
        self.moon_scroll.setWidgetResizable(False)
        self.moon_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.moon_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.moon_scroll.setFrameShape(QScrollArea.NoFrame)
        self.moon_scroll.setWidget(self.moon_canvas)
        self.moon_scroll.hide()

        # Grafický výstup šifry Morseova abeceda – hory.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.morse_hory_canvas = self.create_morse_hory_canvas()

        self.morse_hory_scroll = QScrollArea(self)
        self.morse_hory_scroll.setWidgetResizable(False)
        self.morse_hory_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.morse_hory_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.morse_hory_scroll.setFrameShape(QScrollArea.NoFrame)
        self.morse_hory_scroll.setWidget(self.morse_hory_canvas)
        self.morse_hory_scroll.hide()

        # Grafický výstup šifry Morseova abeceda – pila.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.morse_pila_canvas = self.create_morse_pila_canvas()

        self.morse_pila_scroll = QScrollArea(self)
        self.morse_pila_scroll.setWidgetResizable(False)
        self.morse_pila_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.morse_pila_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.morse_pila_scroll.setFrameShape(QScrollArea.NoFrame)
        self.morse_pila_scroll.setWidget(self.morse_pila_canvas)
        self.morse_pila_scroll.hide()

        # Grafický výstup šifry Morseova abeceda – stromy.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.morse_stromy_canvas = self.create_morse_stromy_canvas()

        self.morse_stromy_scroll = QScrollArea(self)
        self.morse_stromy_scroll.setWidgetResizable(False)
        self.morse_stromy_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.morse_stromy_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.morse_stromy_scroll.setFrameShape(QScrollArea.NoFrame)
        self.morse_stromy_scroll.setWidget(self.morse_stromy_canvas)
        self.morse_stromy_scroll.hide()

        # Grafický výstup šifry Mříž.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.mriz_canvas = self.create_mriz_canvas()

        self.mriz_scroll = QScrollArea(self)
        self.mriz_scroll.setWidgetResizable(False)
        self.mriz_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mriz_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mriz_scroll.setFrameShape(QScrollArea.NoFrame)
        self.mriz_scroll.setWidget(self.mriz_canvas)
        self.mriz_scroll.hide()

        # Grafický výstup šifry Okno.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.okno_canvas = self.create_okno_canvas()

        self.okno_scroll = QScrollArea(self)
        self.okno_scroll.setWidgetResizable(False)
        self.okno_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.okno_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.okno_scroll.setFrameShape(QScrollArea.NoFrame)
        self.okno_scroll.setWidget(self.okno_canvas)
        self.okno_scroll.hide()

        # Grafický výstup šifry Posunková abeceda.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.posunkova_abeceda_canvas = self.create_posunkova_abeceda_canvas()

        self.posunkova_abeceda_scroll = QScrollArea(self)
        self.posunkova_abeceda_scroll.setWidgetResizable(False)
        self.posunkova_abeceda_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.posunkova_abeceda_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.posunkova_abeceda_scroll.setFrameShape(QScrollArea.NoFrame)
        self.posunkova_abeceda_scroll.setWidget(self.posunkova_abeceda_canvas)
        self.posunkova_abeceda_scroll.hide()

        # Grafický výstup šifry Pseudo-Čína.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.pseudo_cina_canvas = self.create_pseudo_cina_canvas()

        self.pseudo_cina_scroll = QScrollArea(self)
        self.pseudo_cina_scroll.setWidgetResizable(False)
        self.pseudo_cina_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pseudo_cina_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.pseudo_cina_scroll.setFrameShape(QScrollArea.NoFrame)
        self.pseudo_cina_scroll.setWidget(self.pseudo_cina_canvas)
        self.pseudo_cina_scroll.hide()

        # Grafický výstup šifry Semafor.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.semafor_canvas = self.create_semafor_canvas()

        self.semafor_scroll = QScrollArea(self)
        self.semafor_scroll.setWidgetResizable(False)
        self.semafor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.semafor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.semafor_scroll.setFrameShape(QScrollArea.NoFrame)
        self.semafor_scroll.setWidget(self.semafor_canvas)
        self.semafor_scroll.hide()

        # Grafický výstup šifry SuperKrychle.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.superkrychle_canvas = self.create_superkrychle_canvas()

        self.superkrychle_scroll = QScrollArea(self)
        self.superkrychle_scroll.setWidgetResizable(False)
        self.superkrychle_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.superkrychle_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.superkrychle_scroll.setFrameShape(QScrollArea.NoFrame)
        self.superkrychle_scroll.setWidget(self.superkrychle_canvas)
        self.superkrychle_scroll.hide()

        # Grafický výstup šifry Tančící figurky.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.tancici_figurky_canvas = self.create_tancici_figurky_canvas()

        self.tancici_figurky_scroll = QScrollArea(self)
        self.tancici_figurky_scroll.setWidgetResizable(False)
        self.tancici_figurky_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tancici_figurky_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tancici_figurky_scroll.setFrameShape(QScrollArea.NoFrame)
        self.tancici_figurky_scroll.setWidget(self.tancici_figurky_canvas)
        self.tancici_figurky_scroll.hide()

        # Grafický výstup šifry Tančící figurky II.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.tancici_figurky_ii_canvas = self.create_tancici_figurky_ii_canvas()

        self.tancici_figurky_ii_scroll = QScrollArea(self)
        self.tancici_figurky_ii_scroll.setWidgetResizable(False)
        self.tancici_figurky_ii_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tancici_figurky_ii_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tancici_figurky_ii_scroll.setFrameShape(QScrollArea.NoFrame)
        self.tancici_figurky_ii_scroll.setWidget(self.tancici_figurky_ii_canvas)
        self.tancici_figurky_ii_scroll.hide()

        # Grafický výstup šifry Velký polský kříž.
        # Všechny grafické šifry používají jednotný model: vlastní widget vložený do QScrollArea.
        self.velky_polsky_kriz_canvas = self.create_velky_polsky_kriz_canvas()

        self.velky_polsky_kriz_scroll = QScrollArea(self)
        self.velky_polsky_kriz_scroll.setWidgetResizable(False)
        self.velky_polsky_kriz_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.velky_polsky_kriz_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.velky_polsky_kriz_scroll.setFrameShape(QScrollArea.NoFrame)
        self.velky_polsky_kriz_scroll.setWidget(self.velky_polsky_kriz_canvas)
        self.velky_polsky_kriz_scroll.hide()

        # Grafický výstup šifry Velký polský kříž (26 znaků).
        self.velky_polsky_kriz_26_canvas = self.create_velky_polsky_kriz_26_canvas()

        self.velky_polsky_kriz_26_scroll = QScrollArea(self)
        self.velky_polsky_kriz_26_scroll.setWidgetResizable(False)
        self.velky_polsky_kriz_26_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.velky_polsky_kriz_26_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.velky_polsky_kriz_26_scroll.setFrameShape(QScrollArea.NoFrame)
        self.velky_polsky_kriz_26_scroll.setWidget(self.velky_polsky_kriz_26_canvas)
        self.velky_polsky_kriz_26_scroll.hide()

        self.status = QLabel(self)
        self.status.setStyleSheet("background: transparent; color: #d9c697;")

        self.apply_static_styles()
        self.refresh_cipher_styles()
        self.update_selected_header()
        self.update_status()

    def apply_static_styles(self):
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                color: {Colors.TEXT_LIGHT};
                background: rgba(0, 0, 0, 0);
                border: none;
                padding-left: 16px;
                padding-right: 58px;
                selection-background-color: {Colors.GOLD};
                selection-color: #111111;
            }}
            QLineEdit::placeholder {{
                color: {Colors.PLACEHOLDER};
            }}
        """)

        input_text_style = f"""
            QTextEdit {{
                color: {Colors.TEXT_LIGHT};
                background: rgba(0, 0, 0, 0);
                border: none;
                padding: 0px;
                selection-background-color: {Colors.GOLD};
                selection-color: #111111;
            }}
            QTextEdit::placeholder {{
                color: {Colors.PLACEHOLDER};
            }}
        """
        output_text_style = f"""
            QTextEdit {{
                color: {Colors.TEXT_LIGHT};
                background: rgba(0, 0, 0, 0);
                border: none;
                padding: 0px;
                selection-background-color: {Colors.GOLD};
                selection-color: #111111;
            }}
            QTextEdit::placeholder {{
                color: {Colors.PLACEHOLDER};
            }}
        """
        self.input_text.setStyleSheet(input_text_style)
        self.output_text.setStyleSheet(output_text_style)

        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: rgba(0, 0, 0, 0);
                border: none;
            }}
            QScrollBar:vertical {{
                background: rgba(20, 17, 12, 130);
                width: 10px;
                margin: 4px 2px 4px 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #9a8768;
                min-height: 42px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        if hasattr(self, "british_flag_scroll"):
            self.british_flag_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "ctverec_scroll"):
            self.ctverec_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "hebrew_cross_scroll"):
            self.hebrew_cross_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "small_polish_cross_scroll"):
            self.small_polish_cross_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "moon_scroll"):
            self.moon_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "morse_hory_scroll"):
            self.morse_hory_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "morse_pila_scroll"):
            self.morse_pila_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "morse_stromy_scroll"):
            self.morse_stromy_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "mriz_scroll"):
            self.mriz_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "okno_scroll"):
            self.okno_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "posunkova_abeceda_scroll"):
            self.posunkova_abeceda_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "pseudo_cina_scroll"):
            self.pseudo_cina_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "semafor_scroll"):
            self.semafor_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "superkrychle_scroll"):
            self.superkrychle_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "tancici_figurky_scroll"):
            self.tancici_figurky_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "tancici_figurky_ii_scroll"):
            self.tancici_figurky_ii_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "velky_polsky_kriz_scroll"):
            self.velky_polsky_kriz_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

        if hasattr(self, "velky_polsky_kriz_26_scroll"):
            self.velky_polsky_kriz_26_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background: rgba(0, 0, 0, 0);
                    border: none;
                }}
                QScrollBar:vertical {{
                    background: rgba(20, 17, 12, 130);
                    width: 11px;
                    margin: 4px 2px 4px 2px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #b89b68;
                    min-height: 42px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
            """)

    def update_layout_positions(self):
        # Logo je cíleně škálované a centrované do horního kruhového prvku ve skinu.
        # Rozměry a pozice zohledňují kolize s navazujícími textovými prvky.
        self.logo_label.setGeometry(self.sr(740, 38, 195, 190))
        if not self.logo_pixmap.isNull():
            pix = self.logo_pixmap.scaled(
                self.logo_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        self.logo_label.raise_()

        # Levý panel se seznamem šifer
        self.title_left.setGeometry(self.sr(120, 94, 520, 42))
        self.search_edit.setGeometry(self.sr(98, 145, 565, 42))
        self.search_icon.setGeometry(self.sr(606, 145, 48, 42))
        self.scroll_area.setGeometry(self.sr(86, 210, 615, 610))

        # Pravý horní informační panel
        self.selected_title.setGeometry(self.sr(965, 77, 622, 58))
        self.selected_icon.setGeometry(self.sr(1518, 76, 70, 70))

        # Vstupní část je zarovnaná na střed horního rámečku nad textovým polem.
        # Posun kompenzuje prostor zabraný kruhovým logem ve skinu.
        self.input_label.setGeometry(self.sr(1015, 182, 500, 34))
        self.input_text.setGeometry(self.sr(728, 265, 822, 126))

        self.encrypt_button.setGeometry(self.sr(728, 399, 405, 79))
        self.decrypt_button.setGeometry(self.sr(1168, 399, 438, 79))

        # Nadpis výsledku je samostatný prvek nad výstupním polem.
        self.result_title.setGeometry(self.sr(770, 540, 420, 34))
        self.key_button.setGeometry(self.sr(1218, 534, 310, 42))
        self.output_text.setGeometry(self.sr(735, 585, 855, 232))
        if hasattr(self, "british_flag_scroll"):
            self.british_flag_scroll.setGeometry(self.output_text.geometry())
            self.british_flag_scroll.raise_()
            self.resize_british_flag_canvas_to_content()
        if hasattr(self, "ctverec_scroll"):
            self.ctverec_scroll.setGeometry(self.output_text.geometry())
            self.ctverec_scroll.raise_()
            self.resize_ctverec_canvas_to_content()
        if hasattr(self, "hebrew_cross_scroll"):
            self.hebrew_cross_scroll.setGeometry(self.output_text.geometry())
            self.hebrew_cross_scroll.raise_()
            self.resize_hebrew_cross_canvas_to_content()
        if hasattr(self, "small_polish_cross_scroll"):
            self.small_polish_cross_scroll.setGeometry(self.output_text.geometry())
            self.small_polish_cross_scroll.raise_()
            self.resize_small_polish_cross_canvas_to_content()
        if hasattr(self, "moon_scroll"):
            self.moon_scroll.setGeometry(self.output_text.geometry())
            self.moon_scroll.raise_()
            self.resize_moon_canvas_to_content()
        if hasattr(self, "morse_hory_scroll"):
            self.morse_hory_scroll.setGeometry(self.output_text.geometry())
            self.morse_hory_scroll.raise_()
            self.resize_morse_hory_canvas_to_content()
        if hasattr(self, "morse_pila_scroll"):
            self.morse_pila_scroll.setGeometry(self.output_text.geometry())
            self.morse_pila_scroll.raise_()
            self.resize_morse_pila_canvas_to_content()
        if hasattr(self, "morse_stromy_scroll"):
            self.morse_stromy_scroll.setGeometry(self.output_text.geometry())
            self.morse_stromy_scroll.raise_()
            self.resize_morse_stromy_canvas_to_content()
        if hasattr(self, "mriz_scroll"):
            self.mriz_scroll.setGeometry(self.output_text.geometry())
            self.mriz_scroll.raise_()
            self.resize_mriz_canvas_to_content()
        if hasattr(self, "okno_scroll"):
            self.okno_scroll.setGeometry(self.output_text.geometry())
            self.okno_scroll.raise_()
            self.resize_okno_canvas_to_content()
        if hasattr(self, "posunkova_abeceda_scroll"):
            self.posunkova_abeceda_scroll.setGeometry(self.output_text.geometry())
            self.posunkova_abeceda_scroll.raise_()
            self.resize_posunkova_abeceda_canvas_to_content()
        if hasattr(self, "pseudo_cina_scroll"):
            self.pseudo_cina_scroll.setGeometry(self.output_text.geometry())
            self.pseudo_cina_scroll.raise_()
            self.resize_pseudo_cina_canvas_to_content()
        if hasattr(self, "semafor_scroll"):
            self.semafor_scroll.setGeometry(self.output_text.geometry())
            self.semafor_scroll.raise_()
            self.resize_semafor_canvas_to_content()
        if hasattr(self, "superkrychle_scroll"):
            self.superkrychle_scroll.setGeometry(self.output_text.geometry())
            self.superkrychle_scroll.raise_()
            self.resize_superkrychle_canvas_to_content()
        if hasattr(self, "tancici_figurky_scroll"):
            self.tancici_figurky_scroll.setGeometry(self.output_text.geometry())
            self.tancici_figurky_scroll.raise_()
            self.resize_tancici_figurky_canvas_to_content()
        if hasattr(self, "tancici_figurky_ii_scroll"):
            self.tancici_figurky_ii_scroll.setGeometry(self.output_text.geometry())
            self.tancici_figurky_ii_scroll.raise_()
            self.resize_tancici_figurky_ii_canvas_to_content()
        if hasattr(self, "velky_polsky_kriz_scroll"):
            self.velky_polsky_kriz_scroll.setGeometry(self.output_text.geometry())
            self.velky_polsky_kriz_scroll.raise_()
            self.resize_velky_polsky_kriz_canvas_to_content()
        if hasattr(self, "velky_polsky_kriz_26_scroll"):
            self.velky_polsky_kriz_26_scroll.setGeometry(self.output_text.geometry())
            self.velky_polsky_kriz_26_scroll.raise_()
            self.resize_velky_polsky_kriz_26_canvas_to_content()

        self.status.setGeometry(self.sr(52, 881, 950, 22))

        self.apply_responsive_fonts()
        self.update_text_editor_margins()
        self.update_selected_header()
        self.update_status()

    def apply_responsive_fonts(self):
        self.title_left.setFont(QFont("Georgia", self.fs(22), QFont.Bold))
        self.search_edit.setFont(QFont("Georgia", self.fs(14)))
        self.search_icon.setFont(QFont("Georgia", self.fs(27), QFont.Bold))

        for btn in self.cipher_buttons:
            btn.setFont(QFont("Georgia", self.fs(13)))
            icon_size = max(24, self.fs(38))
            btn.setIconSize(QSize(icon_size, icon_size))
            btn.setMinimumHeight(max(36, self.fs(50)))
            btn.update_elided_text()

        self.selected_title.setFont(QFont("Georgia", self.fs(20), QFont.Bold))
        self.input_label.setFont(QFont("Georgia", self.fs(17), QFont.Bold))
        self.input_text.setFont(QFont("Georgia", self.fs(14)))
        self.input_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.input_text.setWordWrapMode(QTextOption.WrapAnywhere)
        self.output_text.setFont(QFont("Georgia", self.fs(14)))
        # Výstup musí podporovat zalomení dlouhých řetězců bez mezer.
        # To řeší například dlouhé výstupy Caesarovy šifry bez přirozených mezer.
        self.output_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.output_text.setWordWrapMode(QTextOption.WrapAnywhere)
        self.encrypt_button.setFont(QFont("Georgia", self.fs(19), QFont.Bold))
        self.decrypt_button.setFont(QFont("Georgia", self.fs(19), QFont.Bold))
        self.key_button.setFont(QFont("Georgia", self.fs(14), QFont.Bold))
        self.result_title.setFont(QFont("Georgia", self.fs(18), QFont.Bold))
        self.status.setFont(QFont("Georgia", self.fs(10)))

        self.update_output_font()
        if hasattr(self, "british_flag_canvas") and hasattr(self.british_flag_canvas, "set_scale"):
            self.british_flag_canvas.set_scale(self.sc())
        if hasattr(self, "british_flag_scroll"):
            self.resize_british_flag_canvas_to_content()
        if hasattr(self, "ctverec_canvas") and hasattr(self.ctverec_canvas, "set_scale"):
            self.ctverec_canvas.set_scale(self.sc())
        if hasattr(self, "ctverec_scroll"):
            self.resize_ctverec_canvas_to_content()
        if hasattr(self, "hebrew_cross_canvas") and hasattr(self.hebrew_cross_canvas, "set_scale"):
            self.hebrew_cross_canvas.set_scale(self.sc())
        if hasattr(self, "hebrew_cross_scroll"):
            self.resize_hebrew_cross_canvas_to_content()
        if hasattr(self, "small_polish_cross_canvas") and hasattr(self.small_polish_cross_canvas, "set_scale"):
            self.small_polish_cross_canvas.set_scale(self.sc())
        if hasattr(self, "small_polish_cross_scroll"):
            self.resize_small_polish_cross_canvas_to_content()
        if hasattr(self, "moon_canvas") and hasattr(self.moon_canvas, "set_scale"):
            self.moon_canvas.set_scale(self.sc())
        if hasattr(self, "moon_scroll"):
            self.resize_moon_canvas_to_content()
        if hasattr(self, "morse_hory_canvas") and hasattr(self.morse_hory_canvas, "set_scale"):
            self.morse_hory_canvas.set_scale(self.sc())
        if hasattr(self, "morse_hory_scroll"):
            self.resize_morse_hory_canvas_to_content()
        if hasattr(self, "morse_pila_canvas") and hasattr(self.morse_pila_canvas, "set_scale"):
            self.morse_pila_canvas.set_scale(self.sc())
        if hasattr(self, "morse_pila_scroll"):
            self.resize_morse_pila_canvas_to_content()
        if hasattr(self, "morse_stromy_canvas") and hasattr(self.morse_stromy_canvas, "set_scale"):
            self.morse_stromy_canvas.set_scale(self.sc())
        if hasattr(self, "morse_stromy_scroll"):
            self.resize_morse_stromy_canvas_to_content()
        if hasattr(self, "mriz_canvas") and hasattr(self.mriz_canvas, "set_scale"):
            self.mriz_canvas.set_scale(self.sc())
        if hasattr(self, "mriz_scroll"):
            self.resize_mriz_canvas_to_content()
        if hasattr(self, "okno_canvas") and hasattr(self.okno_canvas, "set_scale"):
            self.okno_canvas.set_scale(self.sc())
        if hasattr(self, "okno_scroll"):
            self.resize_okno_canvas_to_content()
        if hasattr(self, "posunkova_abeceda_canvas") and hasattr(self.posunkova_abeceda_canvas, "set_scale"):
            self.posunkova_abeceda_canvas.set_scale(self.sc())
        if hasattr(self, "posunkova_abeceda_scroll"):
            self.resize_posunkova_abeceda_canvas_to_content()
        if hasattr(self, "pseudo_cina_canvas") and hasattr(self.pseudo_cina_canvas, "set_scale"):
            self.pseudo_cina_canvas.set_scale(self.sc())
        if hasattr(self, "pseudo_cina_scroll"):
            self.resize_pseudo_cina_canvas_to_content()
        if hasattr(self, "semafor_canvas") and hasattr(self.semafor_canvas, "set_scale"):
            self.semafor_canvas.set_scale(self.sc())
        if hasattr(self, "semafor_scroll"):
            self.resize_semafor_canvas_to_content()
        if hasattr(self, "superkrychle_canvas") and hasattr(self.superkrychle_canvas, "set_scale"):
            self.superkrychle_canvas.set_scale(self.sc())
        if hasattr(self, "superkrychle_scroll"):
            self.resize_superkrychle_canvas_to_content()
        if hasattr(self, "tancici_figurky_canvas") and hasattr(self.tancici_figurky_canvas, "set_scale"):
            self.tancici_figurky_canvas.set_scale(self.sc())
        if hasattr(self, "tancici_figurky_scroll"):
            self.resize_tancici_figurky_canvas_to_content()
        if hasattr(self, "tancici_figurky_ii_canvas") and hasattr(self.tancici_figurky_ii_canvas, "set_scale"):
            self.tancici_figurky_ii_canvas.set_scale(self.sc())
        if hasattr(self, "tancici_figurky_ii_scroll"):
            self.resize_tancici_figurky_ii_canvas_to_content()
        if hasattr(self, "velky_polsky_kriz_canvas") and hasattr(self.velky_polsky_kriz_canvas, "set_scale"):
            self.velky_polsky_kriz_canvas.set_scale(self.sc())
        if hasattr(self, "velky_polsky_kriz_scroll"):
            self.resize_velky_polsky_kriz_canvas_to_content()
        if hasattr(self, "velky_polsky_kriz_26_canvas") and hasattr(self.velky_polsky_kriz_26_canvas, "set_scale"):
            self.velky_polsky_kriz_26_canvas.set_scale(self.sc())
        if hasattr(self, "velky_polsky_kriz_26_scroll"):
            self.resize_velky_polsky_kriz_26_canvas_to_content()

        # Ikony zámků vykresluje TransparentActionButton dynamicky podle výšky tlačítka.
        # Zde se nastavuje pouze font; velikost ikony se řeší v paintEvent().
        self.update_text_editor_margins()

    def update_text_editor_margins(self):
        """Nastaví okraje textových editorů s rezervou pro dekorativní prvek vpravo."""
        left = max(8, self.fs(14))
        top = max(6, self.fs(10))
        bottom = max(6, self.fs(10))
        # Rezerva pro dekorativní kalamář s perem na pravé straně
        right = max(110, int(170 * self.sx()))

        self.input_text.setViewportMargins(left, top, right, bottom)
        self.input_text.document().setDocumentMargin(0)

        out_left = max(8, self.fs(14))
        out_top = max(6, self.fs(10))
        out_right = max(8, self.fs(14))
        out_bottom = max(6, self.fs(10))
        self.output_text.setViewportMargins(out_left, out_top, out_right, out_bottom)
        self.output_text.document().setDocumentMargin(0)

    # ------------------------------------------------------------
    # Aplikační logika a napojení šifer
    # ------------------------------------------------------------

    def create_british_flag_canvas(self):
        """Vytvoří vykreslovací widget pro Britskou vlajku z externě načteného modulu."""
        widget_class = get_british_flag_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Britská vlajka")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_ctverec_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Čtverec z externě načteného modulu."""
        widget_class = get_ctverec_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Čtverec")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_hebrew_cross_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Hebrejský kříž z externě načteného modulu."""
        widget_class = get_hebrew_cross_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Hebrejský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_small_polish_cross_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Malý polský kříž z externě načteného modulu."""
        widget_class = get_small_polish_cross_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Malý polský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_moon_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Moonovo písmo z externě načteného modulu."""
        widget_class = get_moon_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Moonovo písmo")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_hory_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – hory z externě načteného modulu."""
        widget_class = get_morse_hory_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – hory")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_pila_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – pila z externě načteného modulu."""
        widget_class = get_morse_pila_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – pila")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_stromy_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – stromy z externě načteného modulu."""
        widget_class = get_morse_stromy_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – stromy")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_mriz_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Mříž z externě načteného modulu."""
        widget_class = get_mriz_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Mříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_okno_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Okno z externě načteného modulu."""
        widget_class = get_okno_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Okno")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_posunkova_abeceda_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Posunková abeceda z externě načteného modulu."""
        widget_class = get_posunkova_abeceda_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Posunková abeceda")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_pseudo_cina_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Pseudo-Čína z externě načteného modulu."""
        widget_class = get_pseudo_cina_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Pseudo-Čína")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_semafor_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Semafor z externě načteného modulu."""
        widget_class = get_semafor_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Semafor")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_superkrychle_canvas(self):
        """Vytvoří vykreslovací widget pro šifru SuperKrychle z externě načteného modulu."""
        widget_class = get_superkrychle_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul SuperKrychle")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_tancici_figurky_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Tančící figurky z externě načteného modulu."""
        widget_class = get_tancici_figurky_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Tančící figurky")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_tancici_figurky_ii_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Tančící figurky II z externě načteného modulu."""
        widget_class = get_tancici_figurky_ii_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Tančící figurky II")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_velky_polsky_kriz_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Velký polský kříž z externě načteného modulu."""
        widget_class = get_velky_polsky_kriz_widget_class()

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Velký polský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_velky_polsky_kriz_26_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Velký polský kříž (26 znaků) z externě načteného modulu."""
        widget_class = get_velky_polsky_kriz_26_widget_class()

        if widget_class is not None:
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Velký polský kříž (26 znaků)")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def show_plain_output(self, text: str):
        """Zobrazí normální textový výstup a schová kreslené výstupy."""
        if hasattr(self, "british_flag_scroll"):
            self.british_flag_scroll.hide()
        elif hasattr(self, "british_flag_canvas"):
            self.british_flag_canvas.hide()

        if hasattr(self, "ctverec_scroll"):
            self.ctverec_scroll.hide()
        elif hasattr(self, "ctverec_canvas"):
            self.ctverec_canvas.hide()

        if hasattr(self, "hebrew_cross_scroll"):
            self.hebrew_cross_scroll.hide()
        elif hasattr(self, "hebrew_cross_canvas"):
            self.hebrew_cross_canvas.hide()

        if hasattr(self, "small_polish_cross_scroll"):
            self.small_polish_cross_scroll.hide()
        elif hasattr(self, "small_polish_cross_canvas"):
            self.small_polish_cross_canvas.hide()

        if hasattr(self, "moon_scroll"):
            self.moon_scroll.hide()
        elif hasattr(self, "moon_canvas"):
            self.moon_canvas.hide()

        if hasattr(self, "morse_hory_scroll"):
            self.morse_hory_scroll.hide()
        elif hasattr(self, "morse_hory_canvas"):
            self.morse_hory_canvas.hide()

        if hasattr(self, "morse_pila_scroll"):
            self.morse_pila_scroll.hide()
        elif hasattr(self, "morse_pila_canvas"):
            self.morse_pila_canvas.hide()

        if hasattr(self, "morse_stromy_scroll"):
            self.morse_stromy_scroll.hide()
        elif hasattr(self, "morse_stromy_canvas"):
            self.morse_stromy_canvas.hide()

        if hasattr(self, "mriz_scroll"):
            self.mriz_scroll.hide()
        elif hasattr(self, "mriz_canvas"):
            self.mriz_canvas.hide()

        if hasattr(self, "okno_scroll"):
            self.okno_scroll.hide()
        elif hasattr(self, "okno_canvas"):
            self.okno_canvas.hide()

        if hasattr(self, "posunkova_abeceda_scroll"):
            self.posunkova_abeceda_scroll.hide()
        elif hasattr(self, "posunkova_abeceda_canvas"):
            self.posunkova_abeceda_canvas.hide()

        if hasattr(self, "pseudo_cina_scroll"):
            self.pseudo_cina_scroll.hide()
        elif hasattr(self, "pseudo_cina_canvas"):
            self.pseudo_cina_canvas.hide()

        if hasattr(self, "semafor_scroll"):
            self.semafor_scroll.hide()
        elif hasattr(self, "semafor_canvas"):
            self.semafor_canvas.hide()

        if hasattr(self, "superkrychle_scroll"):
            self.superkrychle_scroll.hide()
        elif hasattr(self, "superkrychle_canvas"):
            self.superkrychle_canvas.hide()

        if hasattr(self, "tancici_figurky_scroll"):
            self.tancici_figurky_scroll.hide()
        elif hasattr(self, "tancici_figurky_canvas"):
            self.tancici_figurky_canvas.hide()

        if hasattr(self, "tancici_figurky_ii_scroll"):
            self.tancici_figurky_ii_scroll.hide()
        elif hasattr(self, "tancici_figurky_ii_canvas"):
            self.tancici_figurky_ii_canvas.hide()

        if hasattr(self, "velky_polsky_kriz_scroll"):
            self.velky_polsky_kriz_scroll.hide()
        elif hasattr(self, "velky_polsky_kriz_canvas"):
            self.velky_polsky_kriz_canvas.hide()

        if hasattr(self, "velky_polsky_kriz_26_scroll"):
            self.velky_polsky_kriz_26_scroll.hide()
        elif hasattr(self, "velky_polsky_kriz_26_canvas"):
            self.velky_polsky_kriz_26_canvas.hide()

        self.output_text.show()
        self.output_text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.output_text.setWordWrapMode(QTextOption.WrapAnywhere)
        self.output_text.setPlainText(text)

    def normalize_draw_text_for_size(self, text: str) -> str:
        """Normalizuje text stejně jako šifra pro výpočet velikosti grafického výstupu."""
        normalized = unicodedata.normalize("NFKD", text or "")
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return normalized.upper()

    def estimate_british_flag_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu Britské vlajky.

        Díky tomu se vykreslovací widget zvětší a QScrollArea může scrollovat.
        """
        if not hasattr(self, "british_flag_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.british_flag_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(34, int(58 * scale))
        cell_h = max(24, int(40 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(18, int(30 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.british_flag_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.british_flag_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.british_flag_scroll.height(), y + cell_h + 24)

    def resize_british_flag_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "british_flag_scroll") or not hasattr(self, "british_flag_canvas"):
            return

        viewport_width = self.british_flag_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_british_flag_height(text)

        self.british_flag_canvas.setMinimumSize(width, height)
        self.british_flag_canvas.resize(width, height)

        if hasattr(self.british_flag_canvas, "update_content_size"):
            self.british_flag_canvas.update_content_size()

    def estimate_ctverec_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Čtverec."""
        if not hasattr(self, "ctverec_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.ctverec_canvas, "cipher_text", "")
        )

        # Šifra Čtverec neobsahuje W, proto se pro grafický výstup normalizuje na V.
        source_text = source_text.replace("W", "V")

        scale = self.sc()
        cell_w = max(30, int(44 * scale))
        cell_h = max(30, int(44 * scale))
        letter_gap = max(7, int(10 * scale))
        word_gap = max(18, int(30 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.ctverec_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.ctverec_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if char in "ABCDEFGHIJKLMNOPQRSTUVXYZ":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.ctverec_scroll.height(), y + cell_h + 24)

    def resize_ctverec_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Čtverec, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "ctverec_scroll") or not hasattr(self, "ctverec_canvas"):
            return

        viewport_width = self.ctverec_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_ctverec_height(text)

        self.ctverec_canvas.setMinimumSize(width, height)
        self.ctverec_canvas.resize(width, height)

        if hasattr(self.ctverec_canvas, "update_content_size"):
            self.ctverec_canvas.update_content_size()

    def estimate_hebrew_cross_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Hebrejský kříž."""
        if not hasattr(self, "hebrew_cross_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.hebrew_cross_canvas, "cipher_text", "")
        )

        scale = self.sc()
        # Hebrejský kříž používá zvětšené symboly pro lepší čitelnost ve výstupu.
        # Parametry musí zůstat kompatibilní s HebrejskyKrizOutputWidget v modulu hebrejsky_kriz.py.
        cell_w = max(54, int(74 * scale))
        cell_h = max(48, int(66 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(18, int(26 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.hebrew_cross_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.hebrew_cross_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.hebrew_cross_scroll.height(), y + cell_h + 24)

    def resize_hebrew_cross_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Hebrejský kříž, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "hebrew_cross_scroll") or not hasattr(self, "hebrew_cross_canvas"):
            return

        viewport_width = self.hebrew_cross_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_hebrew_cross_height(text)

        self.hebrew_cross_canvas.setMinimumSize(width, height)
        self.hebrew_cross_canvas.resize(width, height)

        if hasattr(self.hebrew_cross_canvas, "update_content_size"):
            self.hebrew_cross_canvas.update_content_size()

    def estimate_small_polish_cross_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Malý polský kříž."""
        if not hasattr(self, "small_polish_cross_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.small_polish_cross_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(54, int(74 * scale))
        cell_h = max(48, int(66 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(18, int(26 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.small_polish_cross_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.small_polish_cross_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.small_polish_cross_scroll.height(), y + cell_h + 24)

    def resize_small_polish_cross_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Malý polský kříž, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "small_polish_cross_scroll") or not hasattr(self, "small_polish_cross_canvas"):
            return

        viewport_width = self.small_polish_cross_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_small_polish_cross_height(text)

        self.small_polish_cross_canvas.setMinimumSize(width, height)
        self.small_polish_cross_canvas.resize(width, height)

        if hasattr(self.small_polish_cross_canvas, "update_content_size"):
            self.small_polish_cross_canvas.update_content_size()

    def estimate_moon_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Moonovo písmo."""
        if not hasattr(self, "moon_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.moon_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(52, int(70 * scale))
        cell_h = max(50, int(68 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(18, int(28 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.moon_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.moon_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.moon_scroll.height(), y + cell_h + 24)

    def resize_moon_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Moonovo písmo, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "moon_scroll") or not hasattr(self, "moon_canvas"):
            return

        viewport_width = self.moon_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_moon_height(text)

        self.moon_canvas.setMinimumSize(width, height)
        self.moon_canvas.resize(width, height)

        if hasattr(self.moon_canvas, "update_content_size"):
            self.moon_canvas.update_content_size()

    def estimate_morse_hory_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Morseova abeceda – hory."""
        if not hasattr(self, "morse_hory_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.morse_hory_canvas, "cipher_text", "")
        )

        scale = self.sc()
        dot_w = max(13, int(18 * scale))
        dash_w = max(23, int(32 * scale))
        inside_gap = max(2, int(4 * scale))
        letter_gap = max(12, int(18 * scale))
        word_gap = max(26, int(42 * scale))
        line_gap = max(14, int(22 * scale))
        cell_h = max(44, int(62 * scale))

        morse_widths = {
            "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
            "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
            "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
            "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
            "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
            "Z": "--..",
        }

        viewport_width = self.morse_hory_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.morse_hory_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if char in morse_widths:
                marks = morse_widths[char]
                char_w = 0
                for index, mark in enumerate(marks):
                    char_w += dot_w if mark == "." else dash_w
                    if index < len(marks) - 1:
                        char_w += inside_gap
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.morse_hory_scroll.height(), y + cell_h + 24)

    def resize_morse_hory_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Morseova abeceda – hory, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "morse_hory_scroll") or not hasattr(self, "morse_hory_canvas"):
            return

        viewport_width = self.morse_hory_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_morse_hory_height(text)

        self.morse_hory_canvas.setMinimumSize(width, height)
        self.morse_hory_canvas.resize(width, height)

        if hasattr(self.morse_hory_canvas, "update_content_size"):
            self.morse_hory_canvas.update_content_size()

    def estimate_morse_pila_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Morseova abeceda – pila."""
        if not hasattr(self, "morse_pila_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.morse_pila_canvas, "cipher_text", "")
        )

        scale = self.sc()
        dot_w = max(13, int(18 * scale))
        dash_w = max(24, int(34 * scale))
        inside_gap = max(2, int(4 * scale))
        letter_gap = max(12, int(18 * scale))
        word_gap = max(26, int(42 * scale))
        line_gap = max(14, int(22 * scale))
        cell_h = max(44, int(62 * scale))
        tail = max(8, int(12 * scale))

        morse_widths = {
            "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
            "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
            "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
            "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
            "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
            "Z": "--..",
        }

        viewport_width = self.morse_pila_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.morse_pila_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            if char in morse_widths:
                marks = morse_widths[char]
                char_w = 0
                for index, mark in enumerate(marks):
                    char_w += dot_w if mark == "." else dash_w
                    if index < len(marks) - 1:
                        char_w += inside_gap
                char_w += tail
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.morse_pila_scroll.height(), y + cell_h + 24)

    def resize_morse_pila_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Morseova abeceda – pila, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "morse_pila_scroll") or not hasattr(self, "morse_pila_canvas"):
            return

        viewport_width = self.morse_pila_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_morse_pila_height(text)

        self.morse_pila_canvas.setMinimumSize(width, height)
        self.morse_pila_canvas.resize(width, height)

        if hasattr(self.morse_pila_canvas, "update_content_size"):
            self.morse_pila_canvas.update_content_size()

    def estimate_morse_stromy_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Morseova abeceda – stromy."""
        if not hasattr(self, "morse_stromy_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.morse_stromy_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(36, int(52 * scale))
        cell_h = max(62, int(86 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(26, int(42 * scale))
        line_gap = max(14, int(22 * scale))

        viewport_width = self.morse_stromy_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.morse_stromy_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.morse_stromy_scroll.height(), y + cell_h + 24)

    def resize_morse_stromy_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Morseova abeceda – stromy, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "morse_stromy_scroll") or not hasattr(self, "morse_stromy_canvas"):
            return

        viewport_width = self.morse_stromy_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_morse_stromy_height(text)

        self.morse_stromy_canvas.setMinimumSize(width, height)
        self.morse_stromy_canvas.resize(width, height)

        if hasattr(self.morse_stromy_canvas, "update_content_size"):
            self.morse_stromy_canvas.update_content_size()

    def estimate_mriz_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Mříž."""
        if not hasattr(self, "mriz_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.mriz_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(58, int(82 * scale))
        cell_h = max(48, int(66 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.mriz_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.mriz_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.mriz_scroll.height(), y + cell_h + 24)

    def resize_mriz_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Mříž, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "mriz_scroll") or not hasattr(self, "mriz_canvas"):
            return

        viewport_width = self.mriz_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_mriz_height(text)

        self.mriz_canvas.setMinimumSize(width, height)
        self.mriz_canvas.resize(width, height)

        if hasattr(self.mriz_canvas, "update_content_size"):
            self.mriz_canvas.update_content_size()

    def estimate_okno_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Okno."""
        if not hasattr(self, "okno_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.okno_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(46, int(64 * scale))
        cell_h = max(44, int(60 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.okno_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.okno_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(24 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

        return max(self.okno_scroll.height(), y + cell_h + 24)

    def resize_okno_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Okno, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "okno_scroll") or not hasattr(self, "okno_canvas"):
            return

        viewport_width = self.okno_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_okno_height(text)

        self.okno_canvas.setMinimumSize(width, height)
        self.okno_canvas.resize(width, height)

        if hasattr(self.okno_canvas, "update_content_size"):
            self.okno_canvas.update_content_size()

    def estimate_posunkova_abeceda_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Posunková abeceda."""
        if not hasattr(self, "posunkova_abeceda_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.posunkova_abeceda_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(54, int(78 * scale))
        cell_h = max(64, int(92 * scale))
        letter_gap = max(6, int(9 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.posunkova_abeceda_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.posunkova_abeceda_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(26 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.posunkova_abeceda_scroll.height(), y + cell_h + 24)

    def resize_posunkova_abeceda_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Posunková abeceda, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "posunkova_abeceda_scroll") or not hasattr(self, "posunkova_abeceda_canvas"):
            return

        viewport_width = self.posunkova_abeceda_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_posunkova_abeceda_height(text)

        self.posunkova_abeceda_canvas.setMinimumSize(width, height)
        self.posunkova_abeceda_canvas.resize(width, height)

        if hasattr(self.posunkova_abeceda_canvas, "update_content_size"):
            self.posunkova_abeceda_canvas.update_content_size()

    def estimate_pseudo_cina_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Pseudo-Čína."""
        if not hasattr(self, "pseudo_cina_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.pseudo_cina_canvas, "cipher_text", "")
        ).replace("Q", "KV")

        scale = self.sc()
        cell_w = max(40, int(58 * scale))
        cell_h = max(42, int(60 * scale))
        letter_gap = max(5, int(8 * scale))
        word_gap = max(22, int(34 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.pseudo_cina_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.pseudo_cina_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(26 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.pseudo_cina_scroll.height(), y + cell_h + 24)

    def resize_pseudo_cina_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Pseudo-Čína, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "pseudo_cina_scroll") or not hasattr(self, "pseudo_cina_canvas"):
            return

        viewport_width = self.pseudo_cina_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_pseudo_cina_height(text)

        self.pseudo_cina_canvas.setMinimumSize(width, height)
        self.pseudo_cina_canvas.resize(width, height)

        if hasattr(self.pseudo_cina_canvas, "update_content_size"):
            self.pseudo_cina_canvas.update_content_size()

    def estimate_semafor_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Semafor."""
        if not hasattr(self, "semafor_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.semafor_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(60, int(86 * scale))
        cell_h = max(72, int(104 * scale))
        letter_gap = max(4, int(7 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(10, int(16 * scale))

        viewport_width = self.semafor_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.semafor_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(28 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.semafor_scroll.height(), y + cell_h + 24)

    def resize_semafor_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Semafor, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "semafor_scroll") or not hasattr(self, "semafor_canvas"):
            return

        viewport_width = self.semafor_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_semafor_height(text)

        self.semafor_canvas.setMinimumSize(width, height)
        self.semafor_canvas.resize(width, height)

        if hasattr(self.semafor_canvas, "update_content_size"):
            self.semafor_canvas.update_content_size()

    def estimate_superkrychle_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry SuperKrychle."""
        if not hasattr(self, "superkrychle_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.superkrychle_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(44, int(66 * scale))
        cell_h = max(44, int(66 * scale))
        letter_gap = max(10, int(15 * scale))
        word_gap = max(30, int(46 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.superkrychle_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.superkrychle_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(28 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.superkrychle_scroll.height(), y + cell_h + 24)

    def resize_superkrychle_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu SuperKrychle, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "superkrychle_scroll") or not hasattr(self, "superkrychle_canvas"):
            return

        viewport_width = self.superkrychle_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_superkrychle_height(text)

        self.superkrychle_canvas.setMinimumSize(width, height)
        self.superkrychle_canvas.resize(width, height)

        if hasattr(self.superkrychle_canvas, "update_content_size"):
            self.superkrychle_canvas.update_content_size()

    def estimate_tancici_figurky_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Tančící figurky."""
        if not hasattr(self, "tancici_figurky_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.tancici_figurky_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(50, int(72 * scale))
        cell_h = max(66, int(94 * scale))
        letter_gap = max(6, int(10 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(10, int(16 * scale))

        viewport_width = self.tancici_figurky_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.tancici_figurky_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(30 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.tancici_figurky_scroll.height(), y + cell_h + 24)

    def resize_tancici_figurky_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Tančící figurky, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "tancici_figurky_scroll") or not hasattr(self, "tancici_figurky_canvas"):
            return

        viewport_width = self.tancici_figurky_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_tancici_figurky_height(text)

        self.tancici_figurky_canvas.setMinimumSize(width, height)
        self.tancici_figurky_canvas.resize(width, height)

        if hasattr(self.tancici_figurky_canvas, "update_content_size"):
            self.tancici_figurky_canvas.update_content_size()

    def estimate_tancici_figurky_ii_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Tančící figurky II."""
        if not hasattr(self, "tancici_figurky_ii_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.tancici_figurky_ii_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(48, int(68 * scale))
        cell_h = max(62, int(88 * scale))
        letter_gap = max(6, int(10 * scale))
        word_gap = max(24, int(38 * scale))
        line_gap = max(10, int(16 * scale))

        viewport_width = self.tancici_figurky_ii_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.tancici_figurky_ii_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif char in "AÁBCČDĎEÉĚFGHIÍJKLMNŇOÓPQRŘSŠTŤUÚŮVWXYÝZŽ1234567890":
                char_w = cell_w
            else:
                char_w = max(18, int(30 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.tancici_figurky_ii_scroll.height(), y + cell_h + 24)

    def resize_tancici_figurky_ii_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Tančící figurky II, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "tancici_figurky_ii_scroll") or not hasattr(self, "tancici_figurky_ii_canvas"):
            return

        viewport_width = self.tancici_figurky_ii_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_tancici_figurky_ii_height(text)

        self.tancici_figurky_ii_canvas.setMinimumSize(width, height)
        self.tancici_figurky_ii_canvas.resize(width, height)

        if hasattr(self.tancici_figurky_ii_canvas, "update_content_size"):
            self.tancici_figurky_ii_canvas.update_content_size()

    def estimate_velky_polsky_kriz_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Velký polský kříž."""
        if not hasattr(self, "velky_polsky_kriz_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.velky_polsky_kriz_canvas, "cipher_text", "")
        )

        # Dvojice CH se zpracovává jako jeden samostatný symbol.
        source_text = source_text.replace("CH", "X")

        scale = self.sc()
        cell_w = max(48, int(72 * scale))
        cell_h = max(42, int(60 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(26, int(42 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.velky_polsky_kriz_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.velky_polsky_kriz_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(30 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.velky_polsky_kriz_scroll.height(), y + cell_h + 24)

    def resize_velky_polsky_kriz_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Velký polský kříž, aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "velky_polsky_kriz_scroll") or not hasattr(self, "velky_polsky_kriz_canvas"):
            return

        viewport_width = self.velky_polsky_kriz_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_velky_polsky_kriz_height(text)

        self.velky_polsky_kriz_canvas.setMinimumSize(width, height)
        self.velky_polsky_kriz_canvas.resize(width, height)

        if hasattr(self.velky_polsky_kriz_canvas, "update_content_size"):
            self.velky_polsky_kriz_canvas.update_content_size()

    def estimate_velky_polsky_kriz_26_height(self, text: str | None = None) -> int:
        """Spočítá potřebnou výšku grafického výstupu šifry Velký polský kříž (26 znaků)."""
        if not hasattr(self, "velky_polsky_kriz_26_scroll"):
            return 180

        source_text = self.normalize_draw_text_for_size(
            text if text is not None else getattr(self.velky_polsky_kriz_26_canvas, "cipher_text", "")
        )

        scale = self.sc()
        cell_w = max(48, int(72 * scale))
        cell_h = max(42, int(60 * scale))
        letter_gap = max(8, int(12 * scale))
        word_gap = max(26, int(42 * scale))
        line_gap = max(12, int(18 * scale))

        viewport_width = self.velky_polsky_kriz_26_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        content_width = max(140, viewport_width - 24)

        if not source_text:
            return max(self.velky_polsky_kriz_26_scroll.height(), 170)

        x = 0
        y = 0

        for char in source_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                char_w = word_gap
            elif "A" <= char <= "Z":
                char_w = cell_w
            else:
                char_w = max(18, int(30 * scale) + 10)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
                x += letter_gap

        return max(self.velky_polsky_kriz_26_scroll.height(), y + cell_h + 24)

    def resize_velky_polsky_kriz_26_canvas_to_content(self, text: str | None = None):
        """Nastaví velikost vykreslovacího widgetu Velký polský kříž (26 znaků), aby se dlouhý výsledek dal scrollovat."""
        if not hasattr(self, "velky_polsky_kriz_26_scroll") or not hasattr(self, "velky_polsky_kriz_26_canvas"):
            return

        viewport_width = self.velky_polsky_kriz_26_scroll.viewport().width()
        if viewport_width <= 20:
            viewport_width = self.output_text.width()

        width = max(250, viewport_width)
        height = self.estimate_velky_polsky_kriz_26_height(text)

        self.velky_polsky_kriz_26_canvas.setMinimumSize(width, height)
        self.velky_polsky_kriz_26_canvas.resize(width, height)

        if hasattr(self.velky_polsky_kriz_26_canvas, "update_content_size"):
            self.velky_polsky_kriz_26_canvas.update_content_size()

    def set_result_output(self, result: str):
        """Zobrazí výsledek podle aktuální šifry.

        Britská vlajka, Čtverec, Hebrejský kříž, Malý polský kříž, Moonovo písmo, Morseova abeceda – hory, Morseova abeceda – pila, Morseova abeceda – stromy, Mříž, Okno, Posunková abeceda, Pseudo-Čína, Semafor, SuperKrychle a Tančící figurky při šifrování používají grafický výstup ve scrollovací oblasti.
        Ostatní šifry používají QTextEdit.
        """
        if self.is_british_flag_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            self.british_flag_scroll.show()
            self.british_flag_scroll.raise_()
            self.british_flag_scroll.verticalScrollBar().setValue(0)

            self.resize_british_flag_canvas_to_content(result)

            if hasattr(self.british_flag_canvas, "set_cipher_text"):
                self.british_flag_canvas.set_cipher_text(result)
            elif hasattr(self.british_flag_canvas, "setText"):
                self.british_flag_canvas.setText(result)

            self.resize_british_flag_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_british_flag_canvas_to_content(result))
            return

        if self.is_ctverec_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()

            self.ctverec_scroll.show()
            self.ctverec_scroll.raise_()
            self.ctverec_scroll.verticalScrollBar().setValue(0)

            self.resize_ctverec_canvas_to_content(result)

            if hasattr(self.ctverec_canvas, "set_cipher_text"):
                self.ctverec_canvas.set_cipher_text(result)
            elif hasattr(self.ctverec_canvas, "setText"):
                self.ctverec_canvas.setText(result)

            self.resize_ctverec_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_ctverec_canvas_to_content(result))
            return

        if self.is_hebrew_cross_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()

            self.hebrew_cross_scroll.show()
            self.hebrew_cross_scroll.raise_()
            self.hebrew_cross_scroll.verticalScrollBar().setValue(0)

            self.resize_hebrew_cross_canvas_to_content(result)

            if hasattr(self.hebrew_cross_canvas, "set_cipher_text"):
                self.hebrew_cross_canvas.set_cipher_text(result)
            elif hasattr(self.hebrew_cross_canvas, "setText"):
                self.hebrew_cross_canvas.setText(result)

            self.resize_hebrew_cross_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_hebrew_cross_canvas_to_content(result))
            return

        if self.is_small_polish_cross_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()

            self.small_polish_cross_scroll.show()
            self.small_polish_cross_scroll.raise_()
            self.small_polish_cross_scroll.verticalScrollBar().setValue(0)

            self.resize_small_polish_cross_canvas_to_content(result)

            if hasattr(self.small_polish_cross_canvas, "set_cipher_text"):
                self.small_polish_cross_canvas.set_cipher_text(result)
            elif hasattr(self.small_polish_cross_canvas, "setText"):
                self.small_polish_cross_canvas.setText(result)

            self.resize_small_polish_cross_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_small_polish_cross_canvas_to_content(result))
            return

        if self.is_moon_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()

            self.moon_scroll.show()
            self.moon_scroll.raise_()
            self.moon_scroll.verticalScrollBar().setValue(0)

            self.resize_moon_canvas_to_content(result)

            if hasattr(self.moon_canvas, "set_cipher_text"):
                self.moon_canvas.set_cipher_text(result)
            elif hasattr(self.moon_canvas, "setText"):
                self.moon_canvas.setText(result)

            self.resize_moon_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_moon_canvas_to_content(result))
            return

        if self.is_morse_hory_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()

            self.morse_hory_scroll.show()
            self.morse_hory_scroll.raise_()
            self.morse_hory_scroll.verticalScrollBar().setValue(0)

            self.resize_morse_hory_canvas_to_content(result)

            if hasattr(self.morse_hory_canvas, "set_cipher_text"):
                self.morse_hory_canvas.set_cipher_text(result)
            elif hasattr(self.morse_hory_canvas, "setText"):
                self.morse_hory_canvas.setText(result)

            self.resize_morse_hory_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_morse_hory_canvas_to_content(result))
            return

        if self.is_morse_pila_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()

            self.morse_pila_scroll.show()
            self.morse_pila_scroll.raise_()
            self.morse_pila_scroll.verticalScrollBar().setValue(0)

            self.resize_morse_pila_canvas_to_content(result)

            if hasattr(self.morse_pila_canvas, "set_cipher_text"):
                self.morse_pila_canvas.set_cipher_text(result)
            elif hasattr(self.morse_pila_canvas, "setText"):
                self.morse_pila_canvas.setText(result)

            self.resize_morse_pila_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_morse_pila_canvas_to_content(result))
            return

        if self.is_morse_stromy_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()

            self.morse_stromy_scroll.show()
            self.morse_stromy_scroll.raise_()
            self.morse_stromy_scroll.verticalScrollBar().setValue(0)

            self.resize_morse_stromy_canvas_to_content(result)

            if hasattr(self.morse_stromy_canvas, "set_cipher_text"):
                self.morse_stromy_canvas.set_cipher_text(result)
            elif hasattr(self.morse_stromy_canvas, "setText"):
                self.morse_stromy_canvas.setText(result)

            self.resize_morse_stromy_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_morse_stromy_canvas_to_content(result))
            return

        if self.is_mriz_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()

            self.mriz_scroll.show()
            self.mriz_scroll.raise_()
            self.mriz_scroll.verticalScrollBar().setValue(0)

            self.resize_mriz_canvas_to_content(result)

            if hasattr(self.mriz_canvas, "set_cipher_text"):
                self.mriz_canvas.set_cipher_text(result)
            elif hasattr(self.mriz_canvas, "setText"):
                self.mriz_canvas.setText(result)

            self.resize_mriz_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_mriz_canvas_to_content(result))
            return

        if self.is_okno_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()

            self.okno_scroll.show()
            self.okno_scroll.raise_()
            self.okno_scroll.verticalScrollBar().setValue(0)

            self.resize_okno_canvas_to_content(result)

            if hasattr(self.okno_canvas, "set_cipher_text"):
                self.okno_canvas.set_cipher_text(result)
            elif hasattr(self.okno_canvas, "setText"):
                self.okno_canvas.setText(result)

            self.resize_okno_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_okno_canvas_to_content(result))
            return

        if self.is_posunkova_abeceda_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()

            self.posunkova_abeceda_scroll.show()
            self.posunkova_abeceda_scroll.raise_()
            self.posunkova_abeceda_scroll.verticalScrollBar().setValue(0)

            self.resize_posunkova_abeceda_canvas_to_content(result)

            if hasattr(self.posunkova_abeceda_canvas, "set_cipher_text"):
                self.posunkova_abeceda_canvas.set_cipher_text(result)
            elif hasattr(self.posunkova_abeceda_canvas, "setText"):
                self.posunkova_abeceda_canvas.setText(result)

            self.resize_posunkova_abeceda_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_posunkova_abeceda_canvas_to_content(result))
            return

        if self.is_pseudo_cina_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()

            self.pseudo_cina_scroll.show()
            self.pseudo_cina_scroll.raise_()
            self.pseudo_cina_scroll.verticalScrollBar().setValue(0)

            self.resize_pseudo_cina_canvas_to_content(result)

            if hasattr(self.pseudo_cina_canvas, "set_cipher_text"):
                self.pseudo_cina_canvas.set_cipher_text(result)
            elif hasattr(self.pseudo_cina_canvas, "setText"):
                self.pseudo_cina_canvas.setText(result)

            self.resize_pseudo_cina_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_pseudo_cina_canvas_to_content(result))
            return

        if self.is_semafor_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()

            self.semafor_scroll.show()
            self.semafor_scroll.raise_()
            self.semafor_scroll.verticalScrollBar().setValue(0)

            self.resize_semafor_canvas_to_content(result)

            if hasattr(self.semafor_canvas, "set_cipher_text"):
                self.semafor_canvas.set_cipher_text(result)
            elif hasattr(self.semafor_canvas, "setText"):
                self.semafor_canvas.setText(result)

            self.resize_semafor_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_semafor_canvas_to_content(result))
            return

        if self.is_superkrychle_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()
            if hasattr(self, "semafor_scroll"):
                self.semafor_scroll.hide()

            self.superkrychle_scroll.show()
            self.superkrychle_scroll.raise_()
            self.superkrychle_scroll.verticalScrollBar().setValue(0)

            self.resize_superkrychle_canvas_to_content(result)

            if hasattr(self.superkrychle_canvas, "set_cipher_text"):
                self.superkrychle_canvas.set_cipher_text(result)
            elif hasattr(self.superkrychle_canvas, "setText"):
                self.superkrychle_canvas.setText(result)

            self.resize_superkrychle_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_superkrychle_canvas_to_content(result))
            return

        if self.is_tancici_figurky_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()
            if hasattr(self, "semafor_scroll"):
                self.semafor_scroll.hide()
            if hasattr(self, "superkrychle_scroll"):
                self.superkrychle_scroll.hide()

            self.tancici_figurky_scroll.show()
            self.tancici_figurky_scroll.raise_()
            self.tancici_figurky_scroll.verticalScrollBar().setValue(0)

            self.resize_tancici_figurky_canvas_to_content(result)

            if hasattr(self.tancici_figurky_canvas, "set_cipher_text"):
                self.tancici_figurky_canvas.set_cipher_text(result)
            elif hasattr(self.tancici_figurky_canvas, "setText"):
                self.tancici_figurky_canvas.setText(result)

            self.resize_tancici_figurky_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_tancici_figurky_canvas_to_content(result))
            return

        if self.is_tancici_figurky_ii_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()
            if hasattr(self, "semafor_scroll"):
                self.semafor_scroll.hide()
            if hasattr(self, "superkrychle_scroll"):
                self.superkrychle_scroll.hide()
            if hasattr(self, "tancici_figurky_scroll"):
                self.tancici_figurky_scroll.hide()

            self.tancici_figurky_ii_scroll.show()
            self.tancici_figurky_ii_scroll.raise_()
            self.tancici_figurky_ii_scroll.verticalScrollBar().setValue(0)

            self.resize_tancici_figurky_ii_canvas_to_content(result)

            if hasattr(self.tancici_figurky_ii_canvas, "set_cipher_text"):
                self.tancici_figurky_ii_canvas.set_cipher_text(result)
            elif hasattr(self.tancici_figurky_ii_canvas, "setText"):
                self.tancici_figurky_ii_canvas.setText(result)

            self.resize_tancici_figurky_ii_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_tancici_figurky_ii_canvas_to_content(result))
            return

        if self.is_velky_polsky_kriz_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()
            if hasattr(self, "semafor_scroll"):
                self.semafor_scroll.hide()
            if hasattr(self, "superkrychle_scroll"):
                self.superkrychle_scroll.hide()
            if hasattr(self, "tancici_figurky_scroll"):
                self.tancici_figurky_scroll.hide()
            if hasattr(self, "tancici_figurky_ii_scroll"):
                self.tancici_figurky_ii_scroll.hide()

            self.velky_polsky_kriz_scroll.show()
            self.velky_polsky_kriz_scroll.raise_()
            self.velky_polsky_kriz_scroll.verticalScrollBar().setValue(0)

            self.resize_velky_polsky_kriz_canvas_to_content(result)

            if hasattr(self.velky_polsky_kriz_canvas, "set_cipher_text"):
                self.velky_polsky_kriz_canvas.set_cipher_text(result)
            elif hasattr(self.velky_polsky_kriz_canvas, "setText"):
                self.velky_polsky_kriz_canvas.setText(result)

            self.resize_velky_polsky_kriz_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_velky_polsky_kriz_canvas_to_content(result))
            return

        if self.is_velky_polsky_kriz_26_selected() and self.result_mode == "encrypt":
            self.output_text.clear()
            self.output_text.hide()

            if hasattr(self, "british_flag_scroll"):
                self.british_flag_scroll.hide()
            if hasattr(self, "ctverec_scroll"):
                self.ctverec_scroll.hide()
            if hasattr(self, "hebrew_cross_scroll"):
                self.hebrew_cross_scroll.hide()
            if hasattr(self, "small_polish_cross_scroll"):
                self.small_polish_cross_scroll.hide()
            if hasattr(self, "moon_scroll"):
                self.moon_scroll.hide()
            if hasattr(self, "morse_hory_scroll"):
                self.morse_hory_scroll.hide()
            if hasattr(self, "morse_pila_scroll"):
                self.morse_pila_scroll.hide()
            if hasattr(self, "morse_stromy_scroll"):
                self.morse_stromy_scroll.hide()
            if hasattr(self, "mriz_scroll"):
                self.mriz_scroll.hide()
            if hasattr(self, "okno_scroll"):
                self.okno_scroll.hide()
            if hasattr(self, "posunkova_abeceda_scroll"):
                self.posunkova_abeceda_scroll.hide()
            if hasattr(self, "pseudo_cina_scroll"):
                self.pseudo_cina_scroll.hide()
            if hasattr(self, "semafor_scroll"):
                self.semafor_scroll.hide()
            if hasattr(self, "superkrychle_scroll"):
                self.superkrychle_scroll.hide()
            if hasattr(self, "tancici_figurky_scroll"):
                self.tancici_figurky_scroll.hide()
            if hasattr(self, "tancici_figurky_ii_scroll"):
                self.tancici_figurky_ii_scroll.hide()
            if hasattr(self, "velky_polsky_kriz_scroll"):
                self.velky_polsky_kriz_scroll.hide()

            self.velky_polsky_kriz_26_scroll.show()
            self.velky_polsky_kriz_26_scroll.raise_()
            self.velky_polsky_kriz_26_scroll.verticalScrollBar().setValue(0)

            self.resize_velky_polsky_kriz_26_canvas_to_content(result)

            if hasattr(self.velky_polsky_kriz_26_canvas, "set_cipher_text"):
                self.velky_polsky_kriz_26_canvas.set_cipher_text(result)
            elif hasattr(self.velky_polsky_kriz_26_canvas, "setText"):
                self.velky_polsky_kriz_26_canvas.setText(result)

            self.resize_velky_polsky_kriz_26_canvas_to_content(result)
            QTimer.singleShot(0, lambda: self.resize_velky_polsky_kriz_26_canvas_to_content(result))
            return

        self.show_plain_output(result)







    def update_output_widget_mode(self):
        """Přepne mezi textovým výstupem a kreslenými výstupy."""
        has_british = hasattr(self, "british_flag_scroll")
        has_ctverec = hasattr(self, "ctverec_scroll")
        has_hebrew = hasattr(self, "hebrew_cross_scroll")
        has_small_polish = hasattr(self, "small_polish_cross_scroll")
        has_moon = hasattr(self, "moon_scroll")
        has_morse_hory = hasattr(self, "morse_hory_scroll")
        has_morse_pila = hasattr(self, "morse_pila_scroll")
        has_morse_stromy = hasattr(self, "morse_stromy_scroll")
        has_mriz = hasattr(self, "mriz_scroll")
        has_okno = hasattr(self, "okno_scroll")
        has_posunkova_abeceda = hasattr(self, "posunkova_abeceda_scroll")
        has_pseudo_cina = hasattr(self, "pseudo_cina_scroll")
        has_semafor = hasattr(self, "semafor_scroll")
        has_superkrychle = hasattr(self, "superkrychle_scroll")
        has_tancici_figurky = hasattr(self, "tancici_figurky_scroll")
        has_tancici_figurky_ii = hasattr(self, "tancici_figurky_ii_scroll")
        has_velky_polsky_kriz = hasattr(self, "velky_polsky_kriz_scroll")
        has_velky_polsky_kriz_26 = hasattr(self, "velky_polsky_kriz_26_scroll")

        def hide_all_draw_outputs():
            if has_british:
                self.british_flag_scroll.hide()
            if has_ctverec:
                self.ctverec_scroll.hide()
            if has_hebrew:
                self.hebrew_cross_scroll.hide()
            if has_small_polish:
                self.small_polish_cross_scroll.hide()
            if has_moon:
                self.moon_scroll.hide()
            if has_morse_hory:
                self.morse_hory_scroll.hide()
            if has_morse_pila:
                self.morse_pila_scroll.hide()
            if has_morse_stromy:
                self.morse_stromy_scroll.hide()
            if has_mriz:
                self.mriz_scroll.hide()
            if has_okno:
                self.okno_scroll.hide()
            if has_posunkova_abeceda:
                self.posunkova_abeceda_scroll.hide()
            if has_pseudo_cina:
                self.pseudo_cina_scroll.hide()
            if has_semafor:
                self.semafor_scroll.hide()
            if has_superkrychle:
                self.superkrychle_scroll.hide()
            if has_tancici_figurky:
                self.tancici_figurky_scroll.hide()
            if has_tancici_figurky_ii:
                self.tancici_figurky_ii_scroll.hide()
            if has_velky_polsky_kriz:
                self.velky_polsky_kriz_scroll.hide()
            if has_velky_polsky_kriz_26:
                self.velky_polsky_kriz_26_scroll.hide()

        if self.is_british_flag_selected() and self.result_mode == "encrypt" and has_british:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.british_flag_scroll.show()
            self.british_flag_scroll.raise_()
            self.resize_british_flag_canvas_to_content()
            return

        if self.is_ctverec_selected() and self.result_mode == "encrypt" and has_ctverec:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.ctverec_scroll.show()
            self.ctverec_scroll.raise_()
            self.resize_ctverec_canvas_to_content()
            return

        if self.is_hebrew_cross_selected() and self.result_mode == "encrypt" and has_hebrew:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.hebrew_cross_scroll.show()
            self.hebrew_cross_scroll.raise_()
            self.resize_hebrew_cross_canvas_to_content()
            return

        if self.is_small_polish_cross_selected() and self.result_mode == "encrypt" and has_small_polish:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.small_polish_cross_scroll.show()
            self.small_polish_cross_scroll.raise_()
            self.resize_small_polish_cross_canvas_to_content()
            return

        if self.is_moon_selected() and self.result_mode == "encrypt" and has_moon:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.moon_scroll.show()
            self.moon_scroll.raise_()
            self.resize_moon_canvas_to_content()
            return

        if self.is_morse_hory_selected() and self.result_mode == "encrypt" and has_morse_hory:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.morse_hory_scroll.show()
            self.morse_hory_scroll.raise_()
            self.resize_morse_hory_canvas_to_content()
            return

        if self.is_morse_pila_selected() and self.result_mode == "encrypt" and has_morse_pila:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.morse_pila_scroll.show()
            self.morse_pila_scroll.raise_()
            self.resize_morse_pila_canvas_to_content()
            return

        if self.is_morse_stromy_selected() and self.result_mode == "encrypt" and has_morse_stromy:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.morse_stromy_scroll.show()
            self.morse_stromy_scroll.raise_()
            self.resize_morse_stromy_canvas_to_content()
            return

        if self.is_mriz_selected() and self.result_mode == "encrypt" and has_mriz:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.mriz_scroll.show()
            self.mriz_scroll.raise_()
            self.resize_mriz_canvas_to_content()
            return

        if self.is_okno_selected() and self.result_mode == "encrypt" and has_okno:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.okno_scroll.show()
            self.okno_scroll.raise_()
            self.resize_okno_canvas_to_content()
            return

        if self.is_posunkova_abeceda_selected() and self.result_mode == "encrypt" and has_posunkova_abeceda:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.posunkova_abeceda_scroll.show()
            self.posunkova_abeceda_scroll.raise_()
            self.resize_posunkova_abeceda_canvas_to_content()
            return

        if self.is_pseudo_cina_selected() and self.result_mode == "encrypt" and has_pseudo_cina:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.pseudo_cina_scroll.show()
            self.pseudo_cina_scroll.raise_()
            self.resize_pseudo_cina_canvas_to_content()
            return

        if self.is_semafor_selected() and self.result_mode == "encrypt" and has_semafor:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.semafor_scroll.show()
            self.semafor_scroll.raise_()
            self.resize_semafor_canvas_to_content()
            return

        if self.is_superkrychle_selected() and self.result_mode == "encrypt" and has_superkrychle:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.superkrychle_scroll.show()
            self.superkrychle_scroll.raise_()
            self.resize_superkrychle_canvas_to_content()
            return

        if self.is_tancici_figurky_selected() and self.result_mode == "encrypt" and has_tancici_figurky:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.tancici_figurky_scroll.show()
            self.tancici_figurky_scroll.raise_()
            self.resize_tancici_figurky_canvas_to_content()
            return

        if self.is_tancici_figurky_ii_selected() and self.result_mode == "encrypt" and has_tancici_figurky_ii:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.tancici_figurky_ii_scroll.show()
            self.tancici_figurky_ii_scroll.raise_()
            self.resize_tancici_figurky_ii_canvas_to_content()
            return

        if self.is_velky_polsky_kriz_selected() and self.result_mode == "encrypt" and has_velky_polsky_kriz:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.velky_polsky_kriz_scroll.show()
            self.velky_polsky_kriz_scroll.raise_()
            self.resize_velky_polsky_kriz_canvas_to_content()
            return

        if self.is_velky_polsky_kriz_26_selected() and self.result_mode == "encrypt" and has_velky_polsky_kriz_26:
            self.output_text.hide()
            hide_all_draw_outputs()
            self.velky_polsky_kriz_26_scroll.show()
            self.velky_polsky_kriz_26_scroll.raise_()
            self.resize_velky_polsky_kriz_26_canvas_to_content()
            return

        hide_all_draw_outputs()
        self.output_text.show()

    def normalize_search_text(self, text):
        """Vyhledávání bez rozlišování diakritiky a velikosti písmen."""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in text if not unicodedata.combining(ch))

    def filter_ciphers(self, query):
        """Vyfiltruje šifry a znovu je naskládá kompaktně od prvního řádku."""
        normalized_query = self.normalize_search_text(query)

        # Layout se nejprve vyčistí; widgety se pouze odeberou z pozic, nemažou se.
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.scroll_content)

        visible_buttons = []
        for btn in self.cipher_buttons:
            normalized_name = self.normalize_search_text(btn.full_text)
            visible = normalized_query in normalized_name
            btn.setVisible(visible)
            if visible:
                visible_buttons.append(btn)

        # Filtrované výsledky se znovu vloží od začátku do dvousloupcové mřížky.
        for index, btn in enumerate(visible_buttons):
            row = index // 2
            col = index % 2
            self.grid.addWidget(btn, row, col, alignment=Qt.AlignTop)

        # Skryté widgety se nesmí podílet na výpočtu rozložení.
        for btn in self.cipher_buttons:
            if btn not in visible_buttons:
                btn.hide()

        self.grid.invalidate()
        self.scroll_content.adjustSize()
        self.scroll_area.verticalScrollBar().setValue(0)

    def select_cipher(self, name):
        self.selected_cipher = name
        self.refresh_cipher_styles()
        self.update_selected_header()
        self.update_status()
        self.update_output_widget_mode()
        # Po změně šifry se výsledek okamžitě přepočítá podle aktuálního vstupu.
        self.auto_encrypt_action()

    def refresh_cipher_styles(self):
        for btn in self.cipher_buttons:
            btn.set_selected(btn.item.name == self.selected_cipher)

    def update_selected_header(self):
        if not self.selected_cipher:
            text = "VYBER ŠIFRU"
            self.selected_title.setText(text)
            self.selected_title.setToolTip(text)
            self.selected_icon.clear()
            if hasattr(self, "key_button"):
                self.key_button.setEnabled(False)
            self.update_output_font()
            return

        if hasattr(self, "key_button"):
            self.key_button.setEnabled(True)

        text = f"ŠIFRA – {self.selected_cipher.upper()}"

        # Rezerva pro pravostrannou ikonu.
        available = max(80, self.selected_title.width() - int(90 * self.sx()))
        shown = self.selected_title.fontMetrics().elidedText(text, Qt.ElideRight, available)
        self.selected_title.setText(shown)
        self.selected_title.setToolTip(text)

        icon_file = self.selected_icon_file()
        pix = self.load_pixmap(icon_file)
        if not pix.isNull():
            size = max(42, self.fs(64))
            scaled = pix.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.selected_icon.setPixmap(scaled)
        else:
            self.selected_icon.clear()

        self.update_output_font()

    def get_selected_logic_module(self):
        """Vrátí modul logiky aktuálně vybrané šifry."""
        if not self.selected_cipher:
            return None

        logic_getters = {
            "Binární čtverce": get_binary_squares_logic,
            "Brailovo písmo": get_braille_logic,
            "Britská vlajka": get_british_flag_logic,
            "Caesarova šifra": get_caesar_logic,
            "Čtverec": get_ctverec_logic,
            "Hebrejský kříž": get_hebrew_cross_logic,
            "Malý polský kříž": get_small_polish_cross_logic,
            "Mobil": get_mobile_logic,
            "Moonovo písmo": get_moon_logic,
            "Morseova abeceda": get_morse_logic,
            "Morseova abeceda – hory": get_morse_hory_logic,
            "Morseova abeceda – pila": get_morse_pila_logic,
            "Morseova abeceda – stromy": get_morse_stromy_logic,
            "Mříž": get_mriz_logic,
            "Okno": get_okno_logic,
            "Pavoučí síť": get_pavouci_sit_logic,
            "Posunková abeceda": get_posunkova_abeceda_logic,
            "Pseudo-Čína": get_pseudo_cina_logic,
            "Semafor": get_semafor_logic,
            "SuperKrychle": get_superkrychle_logic,
            "Tančící figurky": get_tancici_figurky_logic,
            "Tančící figurky II": get_tancici_figurky_ii_logic,
            "Velký polský kříž": get_velky_polsky_kriz_logic,
            "Velký polský kříž (26 znaků)": get_velky_polsky_kriz_26_logic,
            "Vlčácká šifra": get_vlcacka_sifra_logic,
            "Záměna písmen (A=Z)": get_zamena_pismen_a_z_logic,
            "Záměna písmen za čísla (A=01, Z=26)": get_zamena_cisla_a01_z26_logic,
            "Záměna písmen za čísla (A=26, Z=01)": get_zamena_cisla_a26_z01_logic,
            "Zednářská šifra": get_zednarska_sifra_logic,
            "Zlomky": get_zlomky_logic,
        }

        getter = logic_getters.get(self.selected_cipher)
        if getter is None:
            return None

        try:
            return getter()
        except Exception as error:
            print(f"CHYBA při načítání logiky pro klíč {self.selected_cipher}: {error}")
            return None

    def show_cipher_key(self):
        """Zobrazí pirátský klíč aktuálně vybrané šifry."""
        if not self.selected_cipher:
            QMessageBox.information(self, "Klíč šifry", "Nejdřív vyber šifru.")
            return

        renderer = get_pirate_key_renderer()
        if renderer is None:
            QMessageBox.critical(
                self,
                "Chybí generátor klíčů",
                "Chybí soubor:\n"
                "pirate_key_renderer.py",
            )
            return

        logic_module = self.get_selected_logic_module()
        if logic_module is None:
            QMessageBox.information(
                self,
                "Klíč šifry",
                "Pro tuto šifru se nepodařilo načíst soubor logiky.",
            )
            return

        key_context = self.get_current_key_context() if hasattr(self, "get_current_key_context") else None

        try:
            renderer.show_key_dialog(self, self.selected_cipher, logic_module, key_context)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Chyba klíče",
                f"Klíč se nepodařilo zobrazit:\n\n{error}",
            )

    def get_current_key_context(self):
        return self.get_current_key_context_for_cipher(self.selected_cipher)

    def get_current_key_context_for_cipher(self, cipher_name):
        context = {}
        if cipher_name == "Caesarova šifra":
            try:
                shift = int(self.get_caesar_shift()) if hasattr(self, "get_caesar_shift") else 3
            except Exception:
                shift = 3
            direction = "dopředu"
            if hasattr(self, "get_caesar_direction"):
                try:
                    raw = str(self.get_caesar_direction())
                    direction = "dozadu" if "dozadu" in raw.lower() else "dopředu"
                except Exception:
                    direction = "dopředu"
            context["caesar_shift"] = shift
            context["caesar_direction"] = direction
        return context

    def update_status(self):
        selected_text = self.selected_cipher if self.selected_cipher else "Žádná"
        self.status.setText(
            f"VYBRANÁ ŠIFRA:  {selected_text}   |   LOGOVÁNÍ:  Vypnuto   |   SRC SLOŽKA:  Nalezena"
        )

    def update_output_font(self):
        if self.selected_cipher in (
            "Binární čtverce",
            "Mobil",
            "Záměna písmen za čísla (A=01, Z=26)",
        ):
            self.output_text.setFont(QFont("Courier New", self.fs(14)))
        else:
            self.output_text.setFont(QFont("Georgia", self.fs(14)))

    def apply_output_line_spacing(self, tight: bool):
        block_format = QTextBlockFormat()
        block_format.setLineHeight(90 if tight else 100, QTextBlockFormat.ProportionalHeight)

        cursor = self.output_text.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.mergeBlockFormat(block_format)
        cursor.clearSelection()
        self.output_text.setTextCursor(cursor)

    def update_result_title(self, mode=None):
        if mode is not None:
            self.result_mode = mode

        if self.result_mode == "encrypt":
            self.result_title.setText("VÝSLEDEK ŠIFROVÁNÍ")
        elif self.result_mode == "decrypt":
            self.result_title.setText("VÝSLEDEK DEŠIFROVÁNÍ")
        else:
            self.result_title.setText("VÝSLEDEK")

        self.update_output_widget_mode()

    def get_input_text(self):
        return self.input_text.toPlainText().strip()

    def is_morse_cipher_selected(self):
        """Vrátí True pro běžnou Morseovku i její varianty."""
        return bool(self.selected_cipher) and self.selected_cipher.startswith("Morseova abeceda")

    def is_morse_hory_selected(self):
        return self.selected_cipher == "Morseova abeceda – hory"

    def is_morse_pila_selected(self):
        return self.selected_cipher == "Morseova abeceda – pila"

    def is_morse_stromy_selected(self):
        return self.selected_cipher == "Morseova abeceda – stromy"

    def is_mriz_selected(self):
        return self.selected_cipher == "Mříž"

    def is_okno_selected(self):
        return self.selected_cipher == "Okno"

    def is_pavouci_sit_selected(self):
        return self.selected_cipher == "Pavoučí síť"

    def is_posunkova_abeceda_selected(self):
        return self.selected_cipher == "Posunková abeceda"

    def is_pseudo_cina_selected(self):
        return self.selected_cipher == "Pseudo-Čína"

    def is_semafor_selected(self):
        return self.selected_cipher == "Semafor"

    def is_superkrychle_selected(self):
        return self.selected_cipher == "SuperKrychle"

    def is_tancici_figurky_selected(self):
        return self.selected_cipher == "Tančící figurky"

    def is_tancici_figurky_ii_selected(self):
        return self.selected_cipher == "Tančící figurky II"

    def is_velky_polsky_kriz_selected(self):
        return self.selected_cipher == "Velký polský kříž"

    def is_velky_polsky_kriz_26_selected(self):
        return self.selected_cipher == "Velký polský kříž (26 znaků)"

    def is_vlcacka_sifra_selected(self):
        return self.selected_cipher == "Vlčácká šifra"

    def is_zamena_pismen_a_z_selected(self):
        return self.selected_cipher == "Záměna písmen (A=Z)"

    def is_zamena_cisla_a01_z26_selected(self):
        return self.selected_cipher == "Záměna písmen za čísla (A=01, Z=26)"

    def is_zamena_cisla_a26_z01_selected(self):
        return self.selected_cipher == "Záměna písmen za čísla (A=26, Z=01)"


    def is_zlomky_selected(self):
        return self.selected_cipher == "Zlomky"

    def is_caesar_selected(self):
        return self.selected_cipher == "Caesarova šifra"

    def is_binary_squares_selected(self):
        return self.selected_cipher == "Binární čtverce"

    def is_braille_selected(self):
        return self.selected_cipher == "Brailovo písmo"

    def is_british_flag_selected(self):
        return self.selected_cipher == "Britská vlajka"

    def is_ctverec_selected(self):
        return self.selected_cipher == "Čtverec"

    def is_hebrew_cross_selected(self):
        return self.selected_cipher == "Hebrejský kříž"

    def is_small_polish_cross_selected(self):
        return self.selected_cipher == "Malý polský kříž"

    def is_mobile_selected(self):
        return self.selected_cipher == "Mobil"

    def is_moon_selected(self):
        return self.selected_cipher == "Moonovo písmo"

    def encrypt_selected_cipher(self, text: str) -> str:
        """Zde se postupně napojují jednotlivé šifry."""
        if not self.selected_cipher:
            return "Nejdřív vyber šifru."



        if self.is_caesar_selected():
            caesar_logic = get_caesar_logic()

            if caesar_logic is None:
                return (
                    "Chybí soubor s logikou šifry Caesarova šifra:\n"
                    "logika sifer/Caesarova šifra/caesarova_sifra.py"
                )

            return caesar_logic.encrypt(text)

        if self.is_zlomky_selected():
            zlomky_logic = get_zlomky_logic()

            if zlomky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Zlomky:\n"
                    "logika sifer/Zlomky/zlomky.py"
                )

            return zlomky_logic.encrypt(text)

        if self.is_zamena_cisla_a26_z01_selected():
            zamena_cisla_logic = get_zamena_cisla_a26_z01_logic()

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=26, Z=01):\n"
                    "logika sifer/Záměna písmen za čísla (A=26, Z=01)/zamena_cisla_a26_z01.py"
                )

            return zamena_cisla_logic.encrypt(text)

        if self.is_zamena_cisla_a01_z26_selected():
            zamena_cisla_logic = get_zamena_cisla_a01_z26_logic()

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=01, Z=26):\n"
                    "logika sifer/Záměna písmen za čísla (A=01, Z=26)/zamena_cisla_a01_z26.py"
                )

            return zamena_cisla_logic.encrypt(text)

        if self.is_zamena_pismen_a_z_selected():
            zamena_pismen_a_z_logic = get_zamena_pismen_a_z_logic()

            if zamena_pismen_a_z_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen (A=Z):\n"
                    "logika sifer/Záměna písmen (A=Z)/zamena_pismen_a_z.py"
                )

            return zamena_pismen_a_z_logic.encrypt(text)

        if self.is_vlcacka_sifra_selected():
            vlcacka_sifra_logic = get_vlcacka_sifra_logic()

            if vlcacka_sifra_logic is None:
                return (
                    "Chybí soubor s logikou šifry Vlčácká šifra:\n"
                    "logika sifer/Vlčácká šifra/vlcacka_sifra.py"
                )

            return vlcacka_sifra_logic.encrypt(text)

        if self.is_velky_polsky_kriz_26_selected():
            velky_polsky_kriz_26_logic = get_velky_polsky_kriz_26_logic()

            if velky_polsky_kriz_26_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž (26 znaků):\n"
                    "logika sifer/Velký polský kříž (26 znaků)/velky_polsky_kriz_26.py"
                )

            return velky_polsky_kriz_26_logic.encrypt(text)

        if self.is_velky_polsky_kriz_selected():
            velky_polsky_kriz_logic = get_velky_polsky_kriz_logic()

            if velky_polsky_kriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž:\n"
                    "logika sifer/Velký polský kříž/velky_polsky_kriz.py"
                )

            return velky_polsky_kriz_logic.encrypt(text)

        if self.is_tancici_figurky_ii_selected():
            tancici_figurky_ii_logic = get_tancici_figurky_ii_logic()

            if tancici_figurky_ii_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky II:\n"
                    "logika sifer/Tančící figurky II/tancici_figurky_2.py"
                )

            return tancici_figurky_ii_logic.encrypt(text)

        if self.is_tancici_figurky_selected():
            tancici_figurky_logic = get_tancici_figurky_logic()

            if tancici_figurky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky:\n"
                    "logika sifer/Tančící figurky/tancici_figurky.py"
                )

            return tancici_figurky_logic.encrypt(text)

        if self.is_superkrychle_selected():
            superkrychle_logic = get_superkrychle_logic()

            if superkrychle_logic is None:
                return (
                    "Chybí soubor s logikou šifry SuperKrychle:\n"
                    "logika sifer/SuperKrychle/superkrychle.py"
                )

            return superkrychle_logic.encrypt(text)

        if self.is_semafor_selected():
            semafor_logic = get_semafor_logic()

            if semafor_logic is None:
                return (
                    "Chybí soubor s logikou šifry Semafor:\n"
                    "logika sifer/Semafor/semafor.py"
                )

            return semafor_logic.encrypt(text)

        if self.is_pseudo_cina_selected():
            pseudo_cina_logic = get_pseudo_cina_logic()

            if pseudo_cina_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pseudo-Čína:\n"
                    "logika sifer/Pseudo-Čína/pseudo_cina.py"
                )

            return pseudo_cina_logic.encrypt(text)

        if self.is_posunkova_abeceda_selected():
            posunkova_abeceda_logic = get_posunkova_abeceda_logic()

            if posunkova_abeceda_logic is None:
                return (
                    "Chybí soubor s logikou šifry Posunková abeceda:\n"
                    "logika sifer/Posunková abeceda/posunkova_abeceda.py"
                )

            return posunkova_abeceda_logic.encrypt(text)

        if self.is_pavouci_sit_selected():
            pavouci_sit_logic = get_pavouci_sit_logic()

            if pavouci_sit_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pavoučí síť:\n"
                    "logika sifer/Pavoučí síť/pavouci_sit.py"
                )

            return pavouci_sit_logic.encrypt(text)

        if self.is_okno_selected():
            okno_logic = get_okno_logic()

            if okno_logic is None:
                return (
                    "Chybí soubor s logikou šifry Okno:\n"
                    "logika sifer/Okno/okno.py"
                )

            return okno_logic.encrypt(text)

        if self.is_mriz_selected():
            mriz_logic = get_mriz_logic()

            if mriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mříž:\n"
                    "logika sifer/Mříž/mriz.py"
                )

            return mriz_logic.encrypt(text)

        if self.is_morse_stromy_selected():
            morse_stromy_logic = get_morse_stromy_logic()

            if morse_stromy_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – stromy:\n"
                    "logika sifer/Morseova abeceda – stromy/morseova_abeceda_stromy.py"
                )

            return morse_stromy_logic.encrypt(text)

        if self.is_morse_pila_selected():
            morse_pila_logic = get_morse_pila_logic()

            if morse_pila_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – pila:\n"
                    "logika sifer/Morseova abeceda – pila/morseova_abeceda_pila.py"
                )

            return morse_pila_logic.encrypt(text)

        if self.is_morse_hory_selected():
            morse_hory_logic = get_morse_hory_logic()

            if morse_hory_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – hory:\n"
                    "logika sifer/Morseova abeceda – hory/morseova_abeceda_hory.py"
                )

            return morse_hory_logic.encrypt(text)

        if self.is_moon_selected():
            moon_logic = get_moon_logic()

            if moon_logic is None:
                return (
                    "Chybí soubor s logikou šifry Moonovo písmo:\n"
                    "logika sifer/Moonovo písmo/moonovo_pismo.py"
                )

            return moon_logic.encrypt(text)

        if self.is_mobile_selected():
            mobile_logic = get_mobile_logic()

            if mobile_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mobil:\n"
                    "logika sifer/Mobil/mobil.py"
                )

            return mobile_logic.encrypt(text)

        if self.is_small_polish_cross_selected():
            small_polish_logic = get_small_polish_cross_logic()

            if small_polish_logic is None:
                return (
                    "Chybí soubor s logikou šifry Malý polský kříž:\n"
                    "logika sifer/Malý polský kříž/maly_polsky_kriz.py"
                )

            return small_polish_logic.encrypt(text)

        if self.is_hebrew_cross_selected():
            hebrew_logic = get_hebrew_cross_logic()

            if hebrew_logic is None:
                return (
                    "Chybí soubor s logikou šifry Hebrejský kříž:\n"
                    "logika sifer/Hebrejský kříž/hebrejsky_kriz.py"
                )

            return hebrew_logic.encrypt(text)

        if self.is_ctverec_selected():
            ctverec_logic = get_ctverec_logic()

            if ctverec_logic is None:
                return (
                    "Chybí soubor s logikou šifry Čtverec:\n"
                    "logika sifer/Čtverec/ctverec.py"
                )

            return ctverec_logic.encrypt(text)

        if self.is_british_flag_selected():
            british_logic = get_british_flag_logic()

            if british_logic is None:
                return (
                    "Chybí soubor s logikou Britské vlajky:\n"
                    "logika sifer/Britská vlajka/britska_vlajka.py"
                )

            return british_logic.encrypt(text)

        if self.is_binary_squares_selected():
            binary_logic = get_binary_squares_logic()

            if binary_logic is None:
                return (
                    "Chybí soubor s logikou Binárních čtverců:\n"
                    "logika sifer/Binární čtverce/binarni_ctverce.py"
                )

            return binary_logic.encrypt(text)

        if self.is_morse_cipher_selected():
            morse_logic = get_morse_logic()

            if morse_logic is None:
                return (
                    "Chybí soubor s logikou Morseovy abecedy:\n"
                    "logika sifer/Morseova abeceda/morseova_abeceda.py"
                )

            return morse_logic.encrypt(text)

        if self.is_braille_selected():
            braille_logic = get_braille_logic()

            if braille_logic is None:
                return (
                    "Chybí soubor s logikou Braillova písma:\n"
                    "logika sifer/Brailovo písmo/brailovo_pismo.py"
                )

            return braille_logic.encrypt(text)

        return (
            f"Tato šifra zatím nemá napojenou logiku:\n"
            f"{self.selected_cipher}\n\n"
            f"Původní text:\n{text}"
        )

    def decrypt_selected_cipher(self, text: str) -> str:
        """Zde se postupně napojují jednotlivé šifry."""
        if not self.selected_cipher:
            return "Nejdřív vyber šifru."



        if self.is_caesar_selected():
            caesar_logic = get_caesar_logic()

            if caesar_logic is None:
                return (
                    "Chybí soubor s logikou šifry Caesarova šifra:\n"
                    "logika sifer/Caesarova šifra/caesarova_sifra.py"
                )

            return caesar_logic.decrypt(text)

        if self.is_zlomky_selected():
            zlomky_logic = get_zlomky_logic()

            if zlomky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Zlomky:\n"
                    "logika sifer/Zlomky/zlomky.py"
                )

            return zlomky_logic.decrypt(text)

        if self.is_zamena_cisla_a01_z26_selected():
            zamena_cisla_logic = get_zamena_cisla_a01_z26_logic()

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=01, Z=26):\n"
                    "logika sifer/Záměna písmen za čísla (A=01, Z=26)/zamena_cisla_a01_z26.py"
                )

            return zamena_cisla_logic.decrypt(text)

        if self.is_zamena_cisla_a26_z01_selected():
            zamena_cisla_logic = get_zamena_cisla_a26_z01_logic()

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=26, Z=01):\n"
                    "logika sifer/Záměna písmen za čísla (A=26, Z=01)/zamena_cisla_a26_z01.py"
                )

            return zamena_cisla_logic.decrypt(text)

        if self.is_zamena_pismen_a_z_selected():
            zamena_pismen_a_z_logic = get_zamena_pismen_a_z_logic()

            if zamena_pismen_a_z_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen (A=Z):\n"
                    "logika sifer/Záměna písmen (A=Z)/zamena_pismen_a_z.py"
                )

            return zamena_pismen_a_z_logic.decrypt(text)

        if self.is_vlcacka_sifra_selected():
            vlcacka_sifra_logic = get_vlcacka_sifra_logic()

            if vlcacka_sifra_logic is None:
                return (
                    "Chybí soubor s logikou šifry Vlčácká šifra:\n"
                    "logika sifer/Vlčácká šifra/vlcacka_sifra.py"
                )

            return vlcacka_sifra_logic.decrypt(text)

        if self.is_velky_polsky_kriz_26_selected():
            velky_polsky_kriz_26_logic = get_velky_polsky_kriz_26_logic()

            if velky_polsky_kriz_26_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž (26 znaků):\n"
                    "logika sifer/Velký polský kříž (26 znaků)/velky_polsky_kriz_26.py"
                )

            return velky_polsky_kriz_26_logic.decrypt(text)

        if self.is_velky_polsky_kriz_selected():
            velky_polsky_kriz_logic = get_velky_polsky_kriz_logic()

            if velky_polsky_kriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž:\n"
                    "logika sifer/Velký polský kříž/velky_polsky_kriz.py"
                )

            return velky_polsky_kriz_logic.decrypt(text)

        if self.is_tancici_figurky_ii_selected():
            tancici_figurky_ii_logic = get_tancici_figurky_ii_logic()

            if tancici_figurky_ii_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky II:\n"
                    "logika sifer/Tančící figurky II/tancici_figurky_2.py"
                )

            return tancici_figurky_ii_logic.decrypt(text)

        if self.is_tancici_figurky_selected():
            tancici_figurky_logic = get_tancici_figurky_logic()

            if tancici_figurky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky:\n"
                    "logika sifer/Tančící figurky/tancici_figurky.py"
                )

            return tancici_figurky_logic.decrypt(text)

        if self.is_superkrychle_selected():
            superkrychle_logic = get_superkrychle_logic()

            if superkrychle_logic is None:
                return (
                    "Chybí soubor s logikou šifry SuperKrychle:\n"
                    "logika sifer/SuperKrychle/superkrychle.py"
                )

            return superkrychle_logic.decrypt(text)

        if self.is_semafor_selected():
            semafor_logic = get_semafor_logic()

            if semafor_logic is None:
                return (
                    "Chybí soubor s logikou šifry Semafor:\n"
                    "logika sifer/Semafor/semafor.py"
                )

            return semafor_logic.decrypt(text)

        if self.is_pseudo_cina_selected():
            pseudo_cina_logic = get_pseudo_cina_logic()

            if pseudo_cina_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pseudo-Čína:\n"
                    "logika sifer/Pseudo-Čína/pseudo_cina.py"
                )

            return pseudo_cina_logic.decrypt(text)

        if self.is_posunkova_abeceda_selected():
            posunkova_abeceda_logic = get_posunkova_abeceda_logic()

            if posunkova_abeceda_logic is None:
                return (
                    "Chybí soubor s logikou šifry Posunková abeceda:\n"
                    "logika sifer/Posunková abeceda/posunkova_abeceda.py"
                )

            return posunkova_abeceda_logic.decrypt(text)

        if self.is_pavouci_sit_selected():
            pavouci_sit_logic = get_pavouci_sit_logic()

            if pavouci_sit_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pavoučí síť:\n"
                    "logika sifer/Pavoučí síť/pavouci_sit.py"
                )

            return pavouci_sit_logic.decrypt(text)

        if self.is_okno_selected():
            okno_logic = get_okno_logic()

            if okno_logic is None:
                return (
                    "Chybí soubor s logikou šifry Okno:\n"
                    "logika sifer/Okno/okno.py"
                )

            return okno_logic.decrypt(text)

        if self.is_mriz_selected():
            mriz_logic = get_mriz_logic()

            if mriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mříž:\n"
                    "logika sifer/Mříž/mriz.py"
                )

            return mriz_logic.decrypt(text)

        if self.is_morse_stromy_selected():
            morse_stromy_logic = get_morse_stromy_logic()

            if morse_stromy_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – stromy:\n"
                    "logika sifer/Morseova abeceda – stromy/morseova_abeceda_stromy.py"
                )

            return morse_stromy_logic.decrypt(text)

        if self.is_morse_pila_selected():
            morse_pila_logic = get_morse_pila_logic()

            if morse_pila_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – pila:\n"
                    "logika sifer/Morseova abeceda – pila/morseova_abeceda_pila.py"
                )

            return morse_pila_logic.decrypt(text)

        if self.is_morse_hory_selected():
            morse_hory_logic = get_morse_hory_logic()

            if morse_hory_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – hory:\n"
                    "logika sifer/Morseova abeceda – hory/morseova_abeceda_hory.py"
                )

            return morse_hory_logic.decrypt(text)

        if self.is_moon_selected():
            moon_logic = get_moon_logic()

            if moon_logic is None:
                return (
                    "Chybí soubor s logikou šifry Moonovo písmo:\n"
                    "logika sifer/Moonovo písmo/moonovo_pismo.py"
                )

            return moon_logic.decrypt(text)

        if self.is_mobile_selected():
            mobile_logic = get_mobile_logic()

            if mobile_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mobil:\n"
                    "logika sifer/Mobil/mobil.py"
                )

            return mobile_logic.decrypt(text)

        if self.is_small_polish_cross_selected():
            small_polish_logic = get_small_polish_cross_logic()

            if small_polish_logic is None:
                return (
                    "Chybí soubor s logikou šifry Malý polský kříž:\n"
                    "logika sifer/Malý polský kříž/maly_polsky_kriz.py"
                )

            return small_polish_logic.decrypt(text)

        if self.is_hebrew_cross_selected():
            hebrew_logic = get_hebrew_cross_logic()

            if hebrew_logic is None:
                return (
                    "Chybí soubor s logikou šifry Hebrejský kříž:\n"
                    "logika sifer/Hebrejský kříž/hebrejsky_kriz.py"
                )

            return hebrew_logic.decrypt(text)

        if self.is_ctverec_selected():
            ctverec_logic = get_ctverec_logic()

            if ctverec_logic is None:
                return (
                    "Chybí soubor s logikou šifry Čtverec:\n"
                    "logika sifer/Čtverec/ctverec.py"
                )

            return ctverec_logic.decrypt(text)

        if self.is_british_flag_selected():
            british_logic = get_british_flag_logic()

            if british_logic is None:
                return (
                    "Chybí soubor s logikou Britské vlajky:\n"
                    "logika sifer/Britská vlajka/britska_vlajka.py"
                )

            return british_logic.decrypt(text)

        if self.is_binary_squares_selected():
            binary_logic = get_binary_squares_logic()

            if binary_logic is None:
                return (
                    "Chybí soubor s logikou Binárních čtverců:\n"
                    "logika sifer/Binární čtverce/binarni_ctverce.py"
                )

            return binary_logic.decrypt(text)

        if self.is_morse_cipher_selected():
            morse_logic = get_morse_logic()

            if morse_logic is None:
                return (
                    "Chybí soubor s logikou Morseovy abecedy:\n"
                    "logika sifer/Morseova abeceda/morseova_abeceda.py"
                )

            return morse_logic.decrypt(text)

        if self.is_braille_selected():
            braille_logic = get_braille_logic()

            if braille_logic is None:
                return (
                    "Chybí soubor s logikou Braillova písma:\n"
                    "logika sifer/Brailovo písmo/brailovo_pismo.py"
                )

            return braille_logic.decrypt(text)

        return (
            f"Tato šifra zatím nemá napojenou logiku:\n"
            f"{self.selected_cipher}\n\n"
            f"Původní text:\n{text}"
        )

    def auto_encrypt_action(self):
        """Automaticky šifruje při psaní nebo při změně vybrané šifry."""
        text = self.get_input_text()

        if not self.selected_cipher:
            self.result_mode = None
            self.update_result_title()
            self.show_plain_output("")
            return

        self.update_result_title("encrypt")

        if not text:
            self.show_plain_output("")
            return

        result = self.encrypt_selected_cipher(text)
        self.set_result_output(result)

        if (
            not self.is_british_flag_selected()
            and not self.is_ctverec_selected()
            and not self.is_hebrew_cross_selected()
            and not self.is_small_polish_cross_selected()
            and not self.is_moon_selected()
            and not self.is_morse_hory_selected()
            and not self.is_morse_pila_selected()
            and not self.is_morse_stromy_selected()
            and not self.is_mriz_selected()
            and not self.is_okno_selected()
            and not self.is_posunkova_abeceda_selected()
            and not self.is_pseudo_cina_selected()
            and not self.is_semafor_selected()
            and not self.is_superkrychle_selected()
            and not self.is_tancici_figurky_selected()
            and not self.is_tancici_figurky_ii_selected()
            and not self.is_velky_polsky_kriz_selected()
            and not self.is_velky_polsky_kriz_26_selected()
            and not self.is_pavouci_sit_selected()
        ):
            self.apply_output_line_spacing(self.is_binary_squares_selected())

    def encrypt_action(self):
        # Tlačítko zůstává jako ruční přepočet, automatický režim ale pracuje průběžně.
        self.auto_encrypt_action()

    def decrypt_action(self):
        self.update_result_title("decrypt")

        text = self.get_input_text()
        if not text:
            self.show_plain_output("Nejdřív zadej text k dešifrování.")
            return

        result = self.decrypt_selected_cipher(text)
        self.set_result_output(result)
        self.apply_output_line_spacing(self.is_binary_squares_selected())

    # ------------------------------------------------------------
    # Události okna a systémová inicializace
    # ------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout_positions()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if not self.skin_pixmap.isNull():
            scaled = self.skin_pixmap.scaled(
                self.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
            painter.drawPixmap(0, 0, scaled)
        else:
            painter.fillRect(self.rect(), QColor("#06131b"))




# ============================================================
# ROZŠÍŘENÍ: Zednářská šifra
# Tato část je oddělená jako samostatná integrace, aby nebylo nutné
# neúměrně rozšiřovat původní metody hlavního widgetu.
# ============================================================

def get_zednarska_sifra_logic_module():
    """Načte modul logiky šifry z cesty: logika sifer/Zednářská šifra/zednarska_sifra.py"""
    logic_file = get_cipher_logic_file("Zednářská šifra", "zednarska_sifra.py")
    return load_python_module_from_path("zednarska_sifra_logic", logic_file)


ZEDNARSKA_SIFRA_LOGIC = None


def get_zednarska_sifra_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Zednářská šifra až při prvním použití."""
    global ZEDNARSKA_SIFRA_LOGIC

    if ZEDNARSKA_SIFRA_LOGIC is None:
        ZEDNARSKA_SIFRA_LOGIC = get_zednarska_sifra_logic_module()

    return ZEDNARSKA_SIFRA_LOGIC


def get_zednarska_sifra_widget_class():
    """Vrátí třídu ZednarskaSifraOutputWidget načtenou z externího modulu zednarska_sifra.py."""
    module = get_zednarska_sifra_logic()

    if module is None:
        return None

    return getattr(module, "ZednarskaSifraOutputWidget", None)


def _zednarska_sifra_is_selected(self):
    return self.selected_cipher == "Zednářská šifra"


def _zednarska_sifra_create_canvas(self):
    widget_class = get_zednarska_sifra_widget_class()

    if widget_class is not None:
        return widget_class()

    fallback = QLabel("Chybí kreslicí modul Zednářská šifra")
    fallback.setStyleSheet("background: transparent; color: #f3d79a;")
    return fallback


def _zednarska_sifra_resize_canvas_to_content(self, text: str | None = None):
    if not hasattr(self, "zednarska_sifra_scroll") or not hasattr(self, "zednarska_sifra_canvas"):
        return

    viewport_width = self.zednarska_sifra_scroll.viewport().width()
    if viewport_width <= 20:
        viewport_width = self.output_text.width()

    width = max(250, viewport_width)

    if hasattr(self.zednarska_sifra_canvas, "calculate_required_height"):
        height = max(
            self.zednarska_sifra_scroll.height(),
            self.zednarska_sifra_canvas.calculate_required_height(width),
        )
    else:
        height = max(self.zednarska_sifra_scroll.height(), 170)

    self.zednarska_sifra_canvas.setMinimumSize(width, height)
    self.zednarska_sifra_canvas.resize(width, height)

    if hasattr(self.zednarska_sifra_canvas, "update_content_size"):
        self.zednarska_sifra_canvas.update_content_size()


def _zednarska_sifra_hide_other_draw_outputs(self):
    """Schová všechny kreslené výstupy kromě Zednářské šifry."""
    for attr_name in dir(self):
        if not attr_name.endswith("_scroll"):
            continue

        if attr_name == "zednarska_sifra_scroll":
            continue

        widget = getattr(self, attr_name, None)
        if hasattr(widget, "hide"):
            widget.hide()


def _zednarska_sifra_scroll_style():
    return """
        QScrollArea {
            background: rgba(0, 0, 0, 0);
            border: none;
        }
        QScrollBar:vertical {
            background: rgba(20, 17, 12, 130);
            width: 11px;
            margin: 4px 2px 4px 2px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background: #b89b68;
            min-height: 42px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """


_ORIGINAL_CREATE_WIDGETS = SifratorSkinWidget.create_widgets
_ORIGINAL_UPDATE_LAYOUT_POSITIONS = SifratorSkinWidget.update_layout_positions
_ORIGINAL_APPLY_RESPONSIVE_FONTS = SifratorSkinWidget.apply_responsive_fonts
_ORIGINAL_SHOW_PLAIN_OUTPUT = SifratorSkinWidget.show_plain_output
_ORIGINAL_SET_RESULT_OUTPUT = SifratorSkinWidget.set_result_output
_ORIGINAL_UPDATE_OUTPUT_WIDGET_MODE = SifratorSkinWidget.update_output_widget_mode
_ORIGINAL_ENCRYPT_SELECTED_CIPHER = SifratorSkinWidget.encrypt_selected_cipher
_ORIGINAL_DECRYPT_SELECTED_CIPHER = SifratorSkinWidget.decrypt_selected_cipher


def _PATCHED_CREATE_WIDGETS(self):
    _ORIGINAL_CREATE_WIDGETS(self)

    self.zednarska_sifra_canvas = self.create_zednarska_sifra_canvas()

    self.zednarska_sifra_scroll = QScrollArea(self)
    self.zednarska_sifra_scroll.setWidgetResizable(False)
    self.zednarska_sifra_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.zednarska_sifra_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.zednarska_sifra_scroll.setFrameShape(QScrollArea.NoFrame)
    self.zednarska_sifra_scroll.setWidget(self.zednarska_sifra_canvas)
    self.zednarska_sifra_scroll.setStyleSheet(_zednarska_sifra_scroll_style())
    self.zednarska_sifra_scroll.hide()


def _PATCHED_UPDATE_LAYOUT_POSITIONS(self):
    _ORIGINAL_UPDATE_LAYOUT_POSITIONS(self)

    if hasattr(self, "zednarska_sifra_scroll"):
        self.zednarska_sifra_scroll.setGeometry(self.output_text.geometry())
        self.zednarska_sifra_scroll.raise_()
        self.resize_zednarska_sifra_canvas_to_content()


def _PATCHED_APPLY_RESPONSIVE_FONTS(self):
    _ORIGINAL_APPLY_RESPONSIVE_FONTS(self)

    if hasattr(self, "zednarska_sifra_canvas") and hasattr(self.zednarska_sifra_canvas, "set_scale"):
        self.zednarska_sifra_canvas.set_scale(self.sc())

    if hasattr(self, "zednarska_sifra_scroll"):
        self.resize_zednarska_sifra_canvas_to_content()


def _PATCHED_SHOW_PLAIN_OUTPUT(self, text: str):
    if hasattr(self, "zednarska_sifra_scroll"):
        self.zednarska_sifra_scroll.hide()

    return _ORIGINAL_SHOW_PLAIN_OUTPUT(self, text)


def _PATCHED_SET_RESULT_OUTPUT(self, result: str):
    if self.is_zednarska_sifra_selected() and self.result_mode == "encrypt":
        self.output_text.clear()
        self.output_text.hide()

        self.zednarska_sifra_hide_other_draw_outputs()

        self.zednarska_sifra_scroll.show()
        self.zednarska_sifra_scroll.raise_()
        self.zednarska_sifra_scroll.verticalScrollBar().setValue(0)

        self.resize_zednarska_sifra_canvas_to_content(result)

        if hasattr(self.zednarska_sifra_canvas, "set_cipher_text"):
            self.zednarska_sifra_canvas.set_cipher_text(result)
        elif hasattr(self.zednarska_sifra_canvas, "setText"):
            self.zednarska_sifra_canvas.setText(result)

        self.resize_zednarska_sifra_canvas_to_content(result)
        QTimer.singleShot(0, lambda: self.resize_zednarska_sifra_canvas_to_content(result))
        return

    if hasattr(self, "zednarska_sifra_scroll"):
        self.zednarska_sifra_scroll.hide()

    return _ORIGINAL_SET_RESULT_OUTPUT(self, result)


def _PATCHED_UPDATE_OUTPUT_WIDGET_MODE(self):
    _ORIGINAL_UPDATE_OUTPUT_WIDGET_MODE(self)

    if self.is_zednarska_sifra_selected() and self.result_mode == "encrypt" and hasattr(self, "zednarska_sifra_scroll"):
        self.output_text.hide()
        self.zednarska_sifra_hide_other_draw_outputs()
        self.zednarska_sifra_scroll.show()
        self.zednarska_sifra_scroll.raise_()
        self.resize_zednarska_sifra_canvas_to_content()
        return

    if hasattr(self, "zednarska_sifra_scroll"):
        self.zednarska_sifra_scroll.hide()


def _PATCHED_ENCRYPT_SELECTED_CIPHER(self, text: str) -> str:
    if self.is_zednarska_sifra_selected():
        zednarska_sifra_logic = get_zednarska_sifra_logic()

        if zednarska_sifra_logic is None:
            return (
                "Chybí soubor s logikou šifry Zednářská šifra:\n"
                "logika sifer/Zednářská šifra/zednarska_sifra.py"
            )

        return zednarska_sifra_logic.encrypt(text)

    return _ORIGINAL_ENCRYPT_SELECTED_CIPHER(self, text)


def _PATCHED_DECRYPT_SELECTED_CIPHER(self, text: str) -> str:
    if self.is_zednarska_sifra_selected():
        zednarska_sifra_logic = get_zednarska_sifra_logic()

        if zednarska_sifra_logic is None:
            return (
                "Chybí soubor s logikou šifry Zednářská šifra:\n"
                "logika sifer/Zednářská šifra/zednarska_sifra.py"
            )

        return zednarska_sifra_logic.decrypt(text)

    return _ORIGINAL_DECRYPT_SELECTED_CIPHER(self, text)


SifratorSkinWidget.is_zednarska_sifra_selected = _zednarska_sifra_is_selected
SifratorSkinWidget.create_zednarska_sifra_canvas = _zednarska_sifra_create_canvas
SifratorSkinWidget.resize_zednarska_sifra_canvas_to_content = _zednarska_sifra_resize_canvas_to_content
SifratorSkinWidget.zednarska_sifra_hide_other_draw_outputs = _zednarska_sifra_hide_other_draw_outputs

SifratorSkinWidget.create_widgets = _PATCHED_CREATE_WIDGETS
SifratorSkinWidget.update_layout_positions = _PATCHED_UPDATE_LAYOUT_POSITIONS
SifratorSkinWidget.apply_responsive_fonts = _PATCHED_APPLY_RESPONSIVE_FONTS
SifratorSkinWidget.show_plain_output = _PATCHED_SHOW_PLAIN_OUTPUT
SifratorSkinWidget.set_result_output = _PATCHED_SET_RESULT_OUTPUT
SifratorSkinWidget.update_output_widget_mode = _PATCHED_UPDATE_OUTPUT_WIDGET_MODE
SifratorSkinWidget.encrypt_selected_cipher = _PATCHED_ENCRYPT_SELECTED_CIPHER
SifratorSkinWidget.decrypt_selected_cipher = _PATCHED_DECRYPT_SELECTED_CIPHER



# ============================================================
# UI ROZŠÍŘENÍ PRO CAESAROVU ŠIFRU
#
# Rozšíření se aktivuje pouze pro Caesarovu šifru:
# - levá akční oblast slouží pro volbu směru posunu,
# - pravá akční oblast slouží pro nastavení velikosti posunu,
# - ostatní šifry zachovávají standardní akční tlačítka.
# ============================================================

_CAESAR_UI_ORIGINAL_CREATE_WIDGETS = SifratorSkinWidget.create_widgets
_CAESAR_UI_ORIGINAL_UPDATE_LAYOUT_POSITIONS = SifratorSkinWidget.update_layout_positions
_CAESAR_UI_ORIGINAL_APPLY_RESPONSIVE_FONTS = SifratorSkinWidget.apply_responsive_fonts
_CAESAR_UI_ORIGINAL_SELECT_CIPHER = SifratorSkinWidget.select_cipher
_CAESAR_UI_ORIGINAL_ENCRYPT_SELECTED_CIPHER = SifratorSkinWidget.encrypt_selected_cipher
_CAESAR_UI_ORIGINAL_DECRYPT_SELECTED_CIPHER = SifratorSkinWidget.decrypt_selected_cipher


class CaesarDirectionCombo(QComboBox):
    """Skutečný rozevírací seznam, ale vykreslený jako text uprostřed tlačítka."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        if self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 120, 26))
            painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 10, 10)

        painter.setFont(self.font())
        painter.setPen(QColor(Colors.GOLD_LIGHT if not self._hovered else "#fff0bd"))

        # Text je centrovaný přes celou plochu původního grafického tlačítka.
        # Vpravo zůstává pouze minimální prostor pro decentní indikaci rozbalení.
        text_rect = self.rect().adjusted(26, 0, -54, 0)
        painter.drawText(text_rect, Qt.AlignCenter, self.currentText())

        # Vlastní indikátor šipky zachovává vzhled skinu a současně naznačuje rozbalovací prvek.
        arrow_font = QFont(self.font())
        arrow_font.setPointSize(max(10, int(self.font().pointSize() * 0.58)))
        painter.setFont(arrow_font)
        arrow_rect = QRect(self.width() - 56, 0, 38, self.height())
        painter.drawText(arrow_rect, Qt.AlignCenter, "▼")


def _caesar_ui_is_selected(self):
    return self.selected_cipher == "Caesarova šifra"


def _caesar_ui_style():
    # Ovládací prvky jsou položeny přímo na grafický skin původních tlačítek.
    # Bez dodatečných rámečků, aby vizuálně navazovaly na původní tlačítka.
    return f"""
        QComboBox, QSpinBox {{
            color: {Colors.GOLD_LIGHT};
            background: rgba(0, 0, 0, 0);
            border: none;
            padding: 0px;
            margin: 0px;
            selection-background-color: {Colors.GOLD};
            selection-color: #111111;
        }}
        QComboBox:hover, QSpinBox:hover {{
            color: #fff0bd;
            background: rgba(255, 220, 120, 22);
            border: none;
            border-radius: 10px;
        }}
        QComboBox::drop-down {{
            border: none;
            background: transparent;
            width: 0px;
        }}
        QComboBox::down-arrow {{
            image: none;
            width: 0px;
            height: 0px;
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 0px;
            height: 0px;
            border: none;
            background: transparent;
        }}
        QLineEdit {{
            color: {Colors.GOLD_LIGHT};
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        }}
        QComboBox QAbstractItemView {{
            color: {Colors.GOLD_LIGHT};
            background: rgba(7, 18, 22, 248);
            border: 2px solid {Colors.GOLD};
            selection-background-color: rgba(200, 154, 76, 155);
            selection-color: #fff0bd;
            outline: 0px;
            padding: 8px;
        }}
    """


def _caesar_ui_create_widgets(self):
    _CAESAR_UI_ORIGINAL_CREATE_WIDGETS(self)

    self.caesar_direction_combo = CaesarDirectionCombo(self)
    self.caesar_direction_combo.addItems(["DOPŘEDU", "DOZADU"])
    self.caesar_direction_combo.setCursor(Qt.PointingHandCursor)
    self.caesar_direction_combo.setEditable(False)
    self.caesar_direction_combo.setMaxVisibleItems(2)
    self.caesar_direction_combo.setStyleSheet(_caesar_ui_style())
    self.caesar_direction_combo.view().setStyleSheet(_caesar_ui_style())
    self.caesar_direction_combo.currentIndexChanged.connect(self.auto_encrypt_action)
    self.caesar_direction_combo.hide()

    self.caesar_shift_input = QSpinBox(self)
    self.caesar_shift_input.setRange(0, 999)
    self.caesar_shift_input.setValue(3)
    self.caesar_shift_input.setPrefix("O KOLIK: ")
    self.caesar_shift_input.setAlignment(Qt.AlignCenter)
    self.caesar_shift_input.setKeyboardTracking(True)
    self.caesar_shift_input.setFrame(False)
    self.caesar_shift_input.setButtonSymbols(QAbstractSpinBox.NoButtons)
    self.caesar_shift_input.lineEdit().setAlignment(Qt.AlignCenter)
    self.caesar_shift_input.lineEdit().setStyleSheet(
        f"color: {Colors.GOLD_LIGHT}; background: transparent; border: none; padding: 0px; margin: 0px;"
    )
    self.caesar_shift_input.setStyleSheet(_caesar_ui_style())
    self.caesar_shift_input.valueChanged.connect(self.auto_encrypt_action)
    self.caesar_shift_input.hide()

    self.update_caesar_controls_visibility()


def _caesar_ui_update_layout_positions(self):
    _CAESAR_UI_ORIGINAL_UPDATE_LAYOUT_POSITIONS(self)

    # Využívá se plocha původních tlačítek s malou bezpečnostní rezervou,
    # aby text vizuálně nekolidoval s dekorativním okrajem skinu.
    inner_x = max(3, int(8 * self.sx()))
    inner_y = max(2, int(5 * self.sy()))

    if hasattr(self, "caesar_direction_combo"):
        rect = self.encrypt_button.geometry().adjusted(inner_x, inner_y, -inner_x, -inner_y)
        self.caesar_direction_combo.setGeometry(rect)
        self.caesar_direction_combo.raise_()

    if hasattr(self, "caesar_shift_input"):
        rect = self.decrypt_button.geometry().adjusted(inner_x, inner_y, -inner_x, -inner_y)
        self.caesar_shift_input.setGeometry(rect)
        self.caesar_shift_input.raise_()
        if self.caesar_shift_input.lineEdit() is not None:
            self.caesar_shift_input.lineEdit().setAlignment(Qt.AlignCenter)

    self.update_caesar_controls_visibility()


def _caesar_ui_apply_responsive_fonts(self):
    _CAESAR_UI_ORIGINAL_APPLY_RESPONSIVE_FONTS(self)

    # Velikost textu je opticky sjednocená s původními akčními tlačítky.
    font = QFont("Georgia", self.fs(20), QFont.Bold)
    if hasattr(self, "caesar_direction_combo"):
        self.caesar_direction_combo.setFont(font)
        self.caesar_direction_combo.update()
    if hasattr(self, "caesar_shift_input"):
        self.caesar_shift_input.setFont(font)
        if self.caesar_shift_input.lineEdit() is not None:
            self.caesar_shift_input.lineEdit().setFont(font)
            self.caesar_shift_input.lineEdit().setAlignment(Qt.AlignCenter)


def _caesar_ui_update_controls_visibility(self):
    is_caesar = self.is_caesar_selected()

    # U Caesarovy šifry se dvě akční oblasti přepnou na konfiguraci směru a posunu.
    # U ostatních šifer se zachová standardní režim tlačítek.
    if hasattr(self, "encrypt_button"):
        self.encrypt_button.setVisible(not is_caesar)
    if hasattr(self, "decrypt_button"):
        self.decrypt_button.setVisible(not is_caesar)

    if hasattr(self, "caesar_direction_combo"):
        self.caesar_direction_combo.setVisible(is_caesar)
        self.caesar_direction_combo.setEnabled(is_caesar)
        if is_caesar:
            self.caesar_direction_combo.raise_()
    if hasattr(self, "caesar_shift_input"):
        self.caesar_shift_input.setVisible(is_caesar)
        self.caesar_shift_input.setEnabled(is_caesar)
        if is_caesar:
            self.caesar_shift_input.raise_()


def _caesar_ui_select_cipher(self, name):
    # Původní select_cipher se nepoužívá přímo, protože při změně šifry
    # spouští auto_encrypt_action dříve, než se přepnou Caesarovy ovládací prvky.
    # Nejprve se nastaví viditelnost prvků a až poté se přepočítá výsledek.
    self.selected_cipher = name
    self.refresh_cipher_styles()
    self.update_selected_header()
    self.update_status()
    self.update_caesar_controls_visibility()
    self.update_output_widget_mode()
    self.auto_encrypt_action()
    self.update_caesar_controls_visibility()


def _caesar_ui_get_shift(self):
    if hasattr(self, "caesar_shift_input"):
        return int(self.caesar_shift_input.value())
    return 3


def _caesar_ui_get_direction(self):
    if hasattr(self, "caesar_direction_combo"):
        text = self.caesar_direction_combo.currentText().strip().lower()
        if "dozadu" in text:
            return "dozadu"
    return "dopredu"


def _caesar_ui_encrypt_selected_cipher(self, text: str) -> str:
    if self.is_caesar_selected():
        caesar_logic = get_caesar_logic()

        if caesar_logic is None:
            return (
                "Chybí soubor s logikou šifry Caesarova šifra:\n"
                "logika sifer/Caesarova šifra/caesarova_sifra.py"
            )

        shift = self.get_caesar_shift()
        direction = self.get_caesar_direction()
        signed_shift = -shift if direction == "dozadu" else shift
        return caesar_logic.encrypt(text, signed_shift)

    return _CAESAR_UI_ORIGINAL_ENCRYPT_SELECTED_CIPHER(self, text)


def _caesar_ui_decrypt_selected_cipher(self, text: str) -> str:
    if self.is_caesar_selected():
        caesar_logic = get_caesar_logic()

        if caesar_logic is None:
            return (
                "Chybí soubor s logikou šifry Caesarova šifra:\n"
                "logika sifer/Caesarova šifra/caesarova_sifra.py"
            )

        shift = self.get_caesar_shift()
        direction = self.get_caesar_direction()
        signed_shift = -shift if direction == "dozadu" else shift
        return caesar_logic.decrypt(text, signed_shift)

    return _CAESAR_UI_ORIGINAL_DECRYPT_SELECTED_CIPHER(self, text)


SifratorSkinWidget.is_caesar_selected = _caesar_ui_is_selected
SifratorSkinWidget.create_widgets = _caesar_ui_create_widgets
SifratorSkinWidget.update_layout_positions = _caesar_ui_update_layout_positions
SifratorSkinWidget.apply_responsive_fonts = _caesar_ui_apply_responsive_fonts
SifratorSkinWidget.select_cipher = _caesar_ui_select_cipher
SifratorSkinWidget.update_caesar_controls_visibility = _caesar_ui_update_controls_visibility
SifratorSkinWidget.get_caesar_shift = _caesar_ui_get_shift
SifratorSkinWidget.get_caesar_direction = _caesar_ui_get_direction
SifratorSkinWidget.encrypt_selected_cipher = _caesar_ui_encrypt_selected_cipher
SifratorSkinWidget.decrypt_selected_cipher = _caesar_ui_decrypt_selected_cipher


# ============================================================
# ROZŠÍŘENÍ TISKU
# Do rozhraní se doplňuje tlačítko TISK s ikonou icons/tiskarna.png.
# Tlačítko spustí tisk aktuálně zobrazeného výsledku.
# Podporován je textový výstup i grafické výstupy umístěné ve scrollovací oblasti.
# ============================================================

_PRINT_ORIGINAL_CREATE_WIDGETS = SifratorSkinWidget.create_widgets
_PRINT_ORIGINAL_UPDATE_LAYOUT_POSITIONS = SifratorSkinWidget.update_layout_positions
_PRINT_ORIGINAL_APPLY_RESPONSIVE_FONTS = SifratorSkinWidget.apply_responsive_fonts


def _print_create_widgets(self):
    _PRINT_ORIGINAL_CREATE_WIDGETS(self)

    self.print_button = QPushButton("TISK", self)
    self.print_button.setCursor(Qt.PointingHandCursor)
    self.print_button.setToolTip("Vytisknout aktuální výsledek")
    self.print_button.setFocusPolicy(Qt.NoFocus)

    printer_icon_path = self.icon_path("tiskarna.png")
    if printer_icon_path and os.path.exists(printer_icon_path):
        self.print_button.setIcon(QIcon(printer_icon_path))
        self.print_button.setIconSize(QSize(24, 24))

    self.print_button.clicked.connect(self.print_current_result)
    self.print_button.setStyleSheet(f"""
        QPushButton {{
            color: {Colors.GOLD_LIGHT};
            background: rgba(7, 18, 22, 145);
            border: 1px solid rgba(200, 154, 76, 170);
            border-radius: 8px;
            padding-left: 8px;
            padding-right: 8px;
            text-align: center;
        }}
        QPushButton:hover {{
            color: #fff0bd;
            background: rgba(20, 45, 50, 185);
            border: 2px solid {Colors.GOLD_LIGHT};
        }}
        QPushButton:pressed {{
            background: rgba(200, 154, 76, 75);
        }}
    """)
    self.print_button.hide()


def _print_update_layout_positions(self):
    _PRINT_ORIGINAL_UPDATE_LAYOUT_POSITIONS(self)

    if hasattr(self, "print_button"):
        # Tlačítko je umístěné nad výsledkem tak, aby neomezovalo čitelnost výstupu.
        # Pozice se odvozuje od output_text, proto zůstává responzivní při změně velikosti okna.
        out_rect = self.output_text.geometry()
        title_rect = self.result_title.geometry()
        btn_w = max(92, int(122 * self.sx()))
        btn_h = max(28, int(38 * self.sy()))
        x = out_rect.right() - btn_w + 1
        y = title_rect.y() - max(2, int(2 * self.sy()))
        self.print_button.setGeometry(x, y, btn_w, btn_h)
        self.print_button.raise_()
        self.print_button.show()


def _print_apply_responsive_fonts(self):
    _PRINT_ORIGINAL_APPLY_RESPONSIVE_FONTS(self)

    if hasattr(self, "print_button"):
        self.print_button.setFont(QFont("Georgia", self.fs(12), QFont.Bold))
        self.print_button.setIconSize(QSize(max(18, self.fs(24)), max(18, self.fs(24))))


def _print_find_visible_draw_widget(self):
    """Vrátí aktuálně viditelný grafický výstup umístěný ve scrollovací oblasti."""
    for name, widget in self.__dict__.items():
        if name == "scroll_area":
            continue
        if not name.endswith("_scroll"):
            continue
        if isinstance(widget, QScrollArea) and widget.isVisible():
            drawn_widget = widget.widget()
            if drawn_widget is not None:
                return drawn_widget
    return None


def _print_current_result(self):
    """Spustí tisk aktuálně zobrazeného textového nebo grafického výsledku."""
    try:
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
    except Exception as error:
        QMessageBox.warning(
            self,
            "Tisk není dostupný",
            f"Nepodařilo se načíst podporu tisku:\n{error}",
        )
        return

    has_plain_text = bool(self.output_text.toPlainText().strip())
    drawn_widget = self.print_find_visible_draw_widget()

    if not has_plain_text and drawn_widget is None:
        QMessageBox.information(self, "Není co tisknout", "Nejdřív vytvoř výsledek šifrování nebo dešifrování.")
        return

    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintDialog(printer, self)
    dialog.setWindowTitle("Tisk výsledku")

    if dialog.exec() != 1:
        return

    # Textové šifry se tisknou přímo z obsahu QTextEdit.
    if self.output_text.isVisible() and has_plain_text:
        self.output_text.print_(printer)
        return

    # Grafické šifry se tisknou jako rastrový výstup celého vykreslovacího widgetu.
    if drawn_widget is not None:
        pixmap = drawn_widget.grab()
        if pixmap.isNull():
            QMessageBox.warning(self, "Tisk se nezdařil", "Nepodařilo se připravit kreslený výsledek pro tisk.")
            return

        painter = QPainter(printer)
        try:
            try:
                page_rect = printer.pageLayout().paintRectPixels(printer.resolution())
            except Exception:
                try:
                    page_rect = printer.pageRect(QPrinter.DevicePixel)
                except Exception:
                    page_rect = printer.pageRect()

            if hasattr(page_rect, "toRect"):
                page_rect = page_rect.toRect()

            scaled = pixmap.scaled(
                page_rect.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            x = page_rect.x() + (page_rect.width() - scaled.width()) // 2
            y = page_rect.y()
            painter.drawPixmap(x, y, scaled)
        finally:
            painter.end()


SifratorSkinWidget.create_widgets = _print_create_widgets
SifratorSkinWidget.update_layout_positions = _print_update_layout_positions
SifratorSkinWidget.apply_responsive_fonts = _print_apply_responsive_fonts
SifratorSkinWidget.print_find_visible_draw_widget = _print_find_visible_draw_widget
SifratorSkinWidget.print_current_result = _print_current_result


# ============================================================
# TISKOVÝ DIALOG S VOLBAMI
# Po kliknutí na tlačítko TISK vyskočí okénko se zaškrtávátky:
#   - klíč šifry
#   - text k zašifrování
#   - zašifrovaný / výsledný text
# ============================================================

def _print_options_escape_html(value: str) -> str:
    import html
    return html.escape(value or "").replace("\n", "<br>")


def _print_options_get_key_image_path(self):
    """Najde obrázek klíče šifry, pokud existuje.

    Hledá například:
        icons/klic_caesarova_sifra.png
        icons/Cesarova šifra_klic.png
        icons/Cesarova šifra.png

    Když speciální klíč neexistuje, použije alespoň ikonu vybrané šifry.
    """
    icon_file = self.selected_icon_file() if hasattr(self, "selected_icon_file") else ""
    if not icon_file:
        return ""

    base, ext = os.path.splitext(icon_file)
    candidates = [
        f"klic_{icon_file}",
        f"klíč_{icon_file}",
        f"{base}_klic{ext}",
        f"{base}_klíč{ext}",
        f"{base}_key{ext}",
        icon_file,
    ]

    for file_name in candidates:
        image_path = self.icon_path(file_name)
        if image_path and os.path.exists(image_path):
            return image_path

    return ""


def _print_options_key_html(self):
    cipher_name = self.selected_cipher or "Nevybraná šifra"
    safe_cipher_name = _print_options_escape_html(cipher_name)

    parts = [f"<p><b>Vybraná šifra:</b> {safe_cipher_name}</p>"]

    # U Caesarovy šifry vytiskneme opravdu klíč: směr, posun a přemapování abecedy.
    try:
        is_caesar = bool(hasattr(self, "is_caesar_selected") and self.is_caesar_selected())
    except Exception:
        is_caesar = False

    if is_caesar:
        shift = int(self.get_caesar_shift()) if hasattr(self, "get_caesar_shift") else 3
        direction = self.get_caesar_direction() if hasattr(self, "get_caesar_direction") else "dopredu"
        signed_shift = -shift if direction == "dozadu" else shift
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        shifted = alphabet[signed_shift % 26:] + alphabet[:signed_shift % 26]
        direction_label = "DOZADU" if direction == "dozadu" else "DOPŘEDU"
        parts.append(f"<p><b>Směr:</b> {direction_label}<br><b>Posun:</b> {shift}</p>")
        parts.append("<table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse;'>")
        parts.append("<tr><td><b>Původní abeceda</b></td><td style='font-family:monospace;'>" + alphabet + "</td></tr>")
        parts.append("<tr><td><b>Posunutá abeceda</b></td><td style='font-family:monospace;'>" + shifted + "</td></tr>")
        parts.append("</table>")
        return "".join(parts)

    # U Zlomků vypíšeme číselný klíč podle tabulky 1/1 až 5/5.
    if cipher_name == "Zlomky":
        groups = ["ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVXYZ"]
        parts.append("<table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse;'>")
        for denominator, letters in enumerate(groups, start=1):
            row = []
            for numerator, letter in enumerate(letters, start=1):
                row.append(f"<td><b>{letter}</b><br>{numerator}/{denominator}</td>")
            parts.append("<tr>" + "".join(row) + "</tr>")
        parts.append("</table>")
        return "".join(parts)

    image_path = _print_options_get_key_image_path(self)
    if image_path:
        safe_path = _print_options_escape_html(image_path)
        parts.append(f"<p><img src='cipher_key_image' width='120'></p>")

    parts.append("<p style='color:#555;'>Pro tuto šifru se tiskne název a dostupný obrázek/ikona klíče. "
                 "Pokud chceš tisknout vlastní klíč, vlož do složky icons obrázek například ve tvaru "
                 "<b>název_ikony_klic.png</b>.</p>")
    return "".join(parts)


def _print_options_dialog(self, has_input: bool, has_output: bool):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox

    dialog = QDialog(self)
    dialog.setWindowTitle("Co chceš vytisknout?")
    dialog.setModal(True)
    dialog.setMinimumWidth(360)

    layout = QVBoxLayout(dialog)
    title = QLabel("Zaškrtni, co chceš vytisknout:", dialog)
    title.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(title)

    key_check = QCheckBox("Klíč šifry", dialog)
    input_check = QCheckBox("Text k zašifrování", dialog)
    output_check = QCheckBox("Zašifrovaný text", dialog)

    key_check.setChecked(True)
    input_check.setChecked(has_input)
    output_check.setChecked(has_output)

    input_check.setEnabled(has_input)
    output_check.setEnabled(has_output)

    layout.addWidget(key_check)
    layout.addWidget(input_check)
    layout.addWidget(output_check)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
    buttons.button(QDialogButtonBox.Ok).setText("Pokračovat")
    buttons.button(QDialogButtonBox.Cancel).setText("Zrušit")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.Accepted:
        return None

    return {
        "key": key_check.isChecked(),
        "input": input_check.isChecked(),
        "output": output_check.isChecked(),
    }




def _print_page_size_points(paper_name: str, orientation_name: str):
    """Převede zvolený formát stránky na typografické body používané při tisku."""
    from PySide6.QtCore import QSizeF

    sizes = {
        "A5": QSizeF(420, 595),
        "A4": QSizeF(595, 842),
        "A3": QSizeF(842, 1191),
        "Letter": QSizeF(612, 792),
        "Legal": QSizeF(612, 1008),
    }
    size = sizes.get(paper_name or "A4", sizes["A4"])
    if orientation_name == "Na šířku":
        return QSizeF(size.height(), size.width())
    return size



def _print_settings_value(settings: dict, key: str, default):
    if not isinstance(settings, dict):
        return default
    return settings.get(key, default)



def _print_crop_image_to_content(image: QImage, margin: int = 18) -> QImage:
    """Ořízne prázdné okolí grafického výstupu, aby šla měnit jeho velikost.

    Kreslené šifry jsou často vložené ve velkém widgetu. Bez ořezu vypadá
    samotný symbol pořád malý, i když se obrázek zvětšuje. Tady najdeme pixely,
    které nejsou průhledné / bílé, a vytvoříme těsnější obrázek.
    """
    if image.isNull():
        return image

    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return image

    left = width
    top = height
    right = -1
    bottom = -1

    # Pro rychlost přeskočíme úplně bílé/průhledné pixely.
    for y in range(height):
        for x in range(width):
            color = image.pixelColor(x, y)
            if color.alpha() <= 8:
                continue

            # Bílé nebo skoro bílé pozadí nepočítáme jako kresbu.
            if color.red() > 245 and color.green() > 245 and color.blue() > 245:
                continue

            # Velmi světle šedé pozadí také nepočítáme.
            if color.red() > 235 and color.green() > 235 and color.blue() > 235:
                continue

            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)

    if right < left or bottom < top:
        return image

    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(width - 1, right + margin)
    bottom = min(height - 1, bottom + margin)

    return image.copy(left, top, right - left + 1, bottom - top + 1)



def _print_section_start(html_parts, title: str, show_heading: bool, framed: bool, heading_size: int):
    if framed:
        html_parts.append("<div class='section'>")
    else:
        html_parts.append("<div class='section plain-section'>")
    if show_heading and title:
        html_parts.append(f"<h2 style='font-size:{int(heading_size)}pt;'>" + _print_options_escape_html(title) + "</h2>")



def _print_section_end(html_parts):
    html_parts.append("</div>")




def _print_image_on_white(image: QImage) -> QImage:
    """Vrátí kopii obrázku se světlým pozadím místo průhlednosti.

    QTextDocument někdy při tisku / náhledu tisku zobrazí průhledné pixely černě.
    Proto kreslené výstupy před vložením do tisku podložíme bílým papírem.
    """
    if image.isNull():
        return image

    result = QImage(image.size(), QImage.Format_RGB32)
    result.fill(QColor("#fffdf8"))

    painter = QPainter(result)
    painter.drawImage(0, 0, image)
    painter.end()

    return result


def _print_image_black_on_white(image: QImage) -> QImage:
    """Tiskový převod grafické šifry na čistou černou na bílém papíru.

    Používá se jen pro tisk. UI zůstane barevné/průhledné.
    """
    if image.isNull():
        return image

    source = image.convertToFormat(QImage.Format_ARGB32)
    result = QImage(source.size(), QImage.Format_RGB32)
    result.fill(QColor("#ffffff"))

    for y in range(source.height()):
        for x in range(source.width()):
            color = source.pixelColor(x, y)
            alpha = color.alpha()
            if alpha <= 8:
                continue

            # Ignoruj bílé / skoro bílé pozadí, kdyby ho některý widget přece jen kreslil.
            if alpha > 245 and color.red() > 245 and color.green() > 245 and color.blue() > 245:
                continue

            result.setPixelColor(x, y, QColor(0, 0, 0))

    return result


def _print_options_build_document(self, options: dict, drawn_widget, paper_name="A4", orientation_name="Na výšku", settings=None):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument

    settings = settings or {}

    document = QTextDocument()
    document.setDefaultFont(QFont("Georgia", 11))
    page_size = _print_page_size_points(paper_name, orientation_name)
    document.setPageSize(page_size)

    content_width = max(350.0, page_size.width() - 72.0)

    show_headings = bool(_print_settings_value(settings, "show_headings", True))
    show_frames = bool(_print_settings_value(settings, "show_frames", True))
    heading_size = int(_print_settings_value(settings, "heading_size", 20))
    key_font_size = int(_print_settings_value(settings, "key_font_size", 12))
    story_font_size = int(_print_settings_value(settings, "story_font_size", 12))
    input_font_size = int(_print_settings_value(settings, "input_font_size", 13))
    output_font_size = int(_print_settings_value(settings, "output_font_size", 13))
    cipher_scale = int(_print_settings_value(settings, "cipher_scale", 85))
    show_cipher_name = bool(_print_settings_value(settings, "show_cipher_name", False))

    key_title = str(_print_settings_value(settings, "key_title", "Klíč šifry"))
    story_title = str(_print_settings_value(settings, "story_title", "Vlastní text / příběh"))
    input_title = str(_print_settings_value(settings, "input_title", "Text k zašifrování"))
    output_title = str(_print_settings_value(settings, "output_title", "Zašifrovaný text"))
    story_text = str(_print_settings_value(settings, "story_text", ""))

    image_width = int(max(0, min(content_width * 2.0, content_width * cipher_scale / 100.0)))

    html_parts = [
        "<html><head><meta charset='utf-8'>",
        "<style>",
        "body { font-family: Georgia, serif; font-size: 12pt; color: #111; margin: 18px; }",
        "h2 { margin: 0 0 12px 0; color: #10223a; }",
        ".cipher-name { color: #555; font-size: 10pt; text-align: right; margin-bottom: 10px; }",
        ".section { border: 1px solid #777; border-radius: 8px; padding: 14px; margin: 16px 0; }",
        ".plain-section { border: none; padding: 0; margin: 14px 0; }",
        ".textbox { white-space: pre-wrap; border: 1px solid #999; padding: 10px; border-radius: 6px; }",
        ".textbox.no-border { border: none; padding: 0; }",
        "table { border-collapse: collapse; margin-top: 8px; }",
        "td, th { border: 1px solid #666; padding: 6px 8px; }",
        "</style></head>",
        "<body>",
    ]

    # Bez horní hlavičky. Volitelně jen malý název šifry, když si ho uživatel zapne.
    if show_cipher_name and self.selected_cipher:
        html_parts.append(f"<div class='cipher-name'>Šifra: {_print_options_escape_html(self.selected_cipher)}</div>")

    if options.get("key"):
        key_image_path = _print_options_get_key_image_path(self)
        if key_image_path and os.path.exists(key_image_path):
            image = QImage(key_image_path)
            if not image.isNull():
                document.addResource(QTextDocument.ImageResource, QUrl("cipher_key_image"), image)

        _print_section_start(html_parts, key_title, show_headings, show_frames, heading_size)
        html_parts.append(f"<div style='font-size:{key_font_size}pt;'>")
        html_parts.append(_print_options_key_html(self))
        html_parts.append("</div>")
        _print_section_end(html_parts)

    if options.get("story"):
        _print_section_start(html_parts, story_title, show_headings, show_frames, heading_size)
        box_class = "textbox" if show_frames else "textbox no-border"
        html_parts.append(f"<div class='{box_class}' style='font-size:{story_font_size}pt;'>")
        html_parts.append(_print_options_escape_html(story_text))
        html_parts.append("</div>")
        _print_section_end(html_parts)

    if options.get("input"):
        input_text = self.input_text.toPlainText() if hasattr(self, "input_text") else ""
        _print_section_start(html_parts, input_title, show_headings, show_frames, heading_size)
        box_class = "textbox" if show_frames else "textbox no-border"
        html_parts.append(f"<div class='{box_class}' style='font-size:{input_font_size}pt;'>")
        html_parts.append(_print_options_escape_html(input_text))
        html_parts.append("</div>")
        _print_section_end(html_parts)

    if options.get("output"):
        _print_section_start(html_parts, output_title, show_headings, show_frames, heading_size)
        if self.output_text.isVisible() and self.output_text.toPlainText().strip():
            output_text = self.output_text.toPlainText()
            box_class = "textbox" if show_frames else "textbox no-border"
            html_parts.append(f"<div class='{box_class}' style='font-size:{output_font_size}pt;'>")
            html_parts.append(_print_options_escape_html(output_text))
            html_parts.append("</div>")
        elif drawn_widget is not None:
            if cipher_scale <= 0:
                # 0 % = kreslený výsledek se do tisku vůbec nevloží.
                pass
            else:
                # NEMRZNOUCÍ NÁHLED: tady už nikdy nevoláme drawn_widget.grab().
                # Grabování velkých kreslených widgetů umí na pár sekund zastavit celé GUI.
                # Náhled použije jen hotovou cache; když není hotová, zobrazí informaci
                # a cache se připraví později přes QTimer.
                image = QImage()
                try:
                    if '_print_cache_peek_drawn_result_image' in globals():
                        image = _print_cache_peek_drawn_result_image(self, drawn_widget)
                    elif '_print_cache_get_drawn_result_image' in globals():
                        image = _print_cache_get_drawn_result_image(self, drawn_widget, force=False)
                except Exception:
                    image = QImage()
                if not image.isNull():
                    document.addResource(QTextDocument.ImageResource, QUrl("drawn_result_image"), image)
                    html_parts.append(f"<p><img src='drawn_result_image' width='{image_width}'></p>")
                else:
                    html_parts.append("<p><i>Kreslený výsledek se připravuje na pozadí. Náhled se po chvíli obnoví.</i></p>")
                    try:
                        self._print_preview_needs_refresh = True
                    except Exception:
                        pass
                    try:
                        if '_schedule_print_cache_preload' in globals():
                            _schedule_print_cache_preload(self, 120)
                    except Exception:
                        pass
        else:
            html_parts.append("<p><i>Není vytvořený žádný výsledek.</i></p>")
        _print_section_end(html_parts)

    html_parts.append("</body></html>")
    document.setHtml("".join(html_parts))
    return document


def _print_current_result_with_options(self):
    """Zobrazí okno s volbami a potom vlastní náhled tisku.

    Windowsové systémové okno tisku neumí u PySide/Qt aplikace vždy zobrazit náhled.
    Proto se nejdřív otevře QPrintPreviewDialog přímo z aplikace. V něm je možné
    výsledek zkontrolovat a potom kliknout na ikonu tiskárny pro skutečný tisk.
    """
    try:
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
    except Exception as error:
        QMessageBox.warning(
            self,
            "Tisk není dostupný",
            f"Nepodařilo se načíst podporu tisku:\n{error}",
        )
        return

    input_text = self.input_text.toPlainText().strip() if hasattr(self, "input_text") else ""
    has_input = bool(input_text)
    has_plain_output = bool(self.output_text.toPlainText().strip()) if hasattr(self, "output_text") else False
    drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
    has_output = bool(has_plain_output or drawn_widget is not None)

    if not has_input and not has_output:
        QMessageBox.information(self, "Není co tisknout", "Nejdřív zadej text nebo vytvoř výsledek šifrování.")
        return

    options = _print_options_dialog(self, has_input=has_input, has_output=has_output)
    if options is None:
        return

    if not any(options.values()):
        QMessageBox.information(self, "Nic není vybráno", "Zaškrtni alespoň jednu položku k tisku.")
        return

    document = _print_options_build_document(self, options, drawn_widget)

    printer = QPrinter(QPrinter.HighResolution)
    preview = QPrintPreviewDialog(printer, self)
    preview.setWindowTitle("Náhled tisku")
    try:
        screen = self.window().screen() if hasattr(self, "window") and self.window() is not None else QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is not None:
            preview.resize(min(1100, int(available.width() * 0.92)), min(800, int(available.height() * 0.88)))
            preview.setMinimumSize(min(760, preview.width()), min(540, preview.height()))
        else:
            preview.resize(1100, 800)
    except Exception:
        preview.resize(1100, 800)

    def render_preview(target_printer):
        document.print_(target_printer)

    preview.paintRequested.connect(render_preview)
    preview.exec()


SifratorSkinWidget.print_current_result = _print_current_result_with_options
SifratorSkinWidget.print_options_dialog = _print_options_dialog
SifratorSkinWidget.print_options_build_document = _print_options_build_document


# ============================================================
# TISK – PŘÍMÝ NÁHLED S VOLBAMI
# Po kliknutí na TISK se rovnou otevře jedno okno, kde jsou:
#   - zaškrtávátka vlevo
#   - živý náhled vpravo
# Náhled se okamžitě mění podle toho, co je zaškrtnuté.
# ============================================================



def _print_current_result_with_live_preview(self):
    """Otevře tematický náhled tisku s možností úpravy rozvržení před tiskem."""
    try:
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        from PySide6.QtGui import QPageSize, QPageLayout
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QCheckBox,
            QTextEdit,
            QPushButton,
            QFrame,
            QComboBox,
            QFormLayout,
            QLineEdit,
            QSpinBox,
            QScrollArea,
        )
    except Exception as error:
        QMessageBox.warning(
            self,
            "Tisk není dostupný",
            f"Nepodařilo se načíst podporu tisku:\n{error}",
        )
        return

    input_text = self.input_text.toPlainText().strip() if hasattr(self, "input_text") else ""
    has_input = bool(input_text)
    has_plain_output = bool(self.output_text.toPlainText().strip()) if hasattr(self, "output_text") else False
    drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
    has_output = bool(has_plain_output or drawn_widget is not None)

    if not has_input and not has_output:
        QMessageBox.information(self, "Není co tisknout", "Nejdřív zadej text nebo vytvoř výsledek šifrování.")
        return

    dialog = QDialog(self)
    dialog.setWindowTitle("Náhled tisku – Šifrátor Mraveniště")
    dialog.setModal(True)

    # Responzivní velikost náhledu tisku podle aktuální obrazovky.
    try:
        screen = self.window().screen() if hasattr(self, "window") and self.window() is not None else QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
    except Exception:
        available = None

    if available is not None:
        dialog_w = min(1280, max(760, int(available.width() * 0.94)))
        dialog_h = min(850, max(560, int(available.height() * 0.90)))
    else:
        dialog_w, dialog_h = 1280, 850

    compact_print_preview = dialog_w < 1080 or dialog_h < 720
    dialog.resize(dialog_w, dialog_h)
    dialog.setMinimumSize(min(760, dialog_w), min(540, dialog_h))
    dialog.setStyleSheet("""
        QDialog {
            background-color: #0a1626;
            color: #f3ddaa;
        }
        QLabel {
            color: #f3ddaa;
            background: transparent;
        }
        QFrame#sidePanel, QFrame#pageFrame {
            background-color: rgba(10, 20, 34, 230);
            border: 1px solid #9b6b2f;
            border-radius: 12px;
        }
        QFrame#sectionFrame {
            background-color: rgba(11, 31, 52, 200);
            border: 1px solid rgba(179, 130, 55, 160);
            border-radius: 10px;
        }
        QCheckBox {
            spacing: 10px;
            padding: 3px 0;
            font-size: 13px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QCheckBox::indicator:unchecked {
            border: 1px solid #d4ae67;
            background: #10263e;
        }
        QCheckBox::indicator:checked {
            border: 1px solid #d4ae67;
            background: #0f8aa8;
        }
        QComboBox, QSpinBox, QLineEdit {
            background-color: #10263e;
            color: #f6e7bf;
            border: 1px solid #c49344;
            border-radius: 8px;
            padding: 6px 8px;
            min-height: 20px;
        }
        QComboBox QAbstractItemView {
            background-color: #10263e;
            color: #f6e7bf;
            border: 1px solid #c49344;
            selection-background-color: #155d75;
        }
        QTextEdit#storyEditor {
            background-color: #071626;
            color: #fff0bd;
            border: 1px solid #c49344;
            border-radius: 8px;
            padding: 8px;
            selection-background-color: #155d75;
        }
        QTextEdit#previewEdit {
            background: white;
            color: black;
            border: 1px solid #c49344;
            border-radius: 8px;
            padding: 18px;
            selection-background-color: #1d6fa5;
        }
        QScrollArea {
            background: transparent;
            border: none;
        }
        QPushButton {
            background-color: #10263e;
            color: #f6e7bf;
            border: 1px solid #c49344;
            border-radius: 10px;
            padding: 10px 18px;
            font-weight: bold;
            min-height: 22px;
        }
        QPushButton:hover {
            background-color: #144a63;
        }
        QPushButton#cancelButton {
            background-color: #4a1520;
            border-color: #b56a5c;
        }
        QPushButton#cancelButton:hover {
            background-color: #6a1b2c;
        }
    """)

    main_layout = QVBoxLayout(dialog)
    main_layout.setContentsMargins(16, 16, 16, 16)
    main_layout.setSpacing(12)

    title = QLabel("Uprav si tisk – náhled se mění hned:", dialog)
    title.setStyleSheet("font-weight: 700; font-size: 18px; color: #f8e8c2;")
    main_layout.addWidget(title)

    content_layout = QVBoxLayout() if compact_print_preview else QHBoxLayout()
    content_layout.setSpacing(10 if compact_print_preview else 14)
    main_layout.addLayout(content_layout, 1)

    side_scroll = QScrollArea(dialog)
    side_scroll.setWidgetResizable(True)
    side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    if compact_print_preview:
        side_scroll.setMinimumWidth(0)
        side_scroll.setMaximumWidth(16777215)
        side_scroll.setMinimumHeight(min(220, max(170, int(dialog_h * 0.28))))
        side_scroll.setMaximumHeight(min(330, max(220, int(dialog_h * 0.38))))
    else:
        side_w_min = min(350, max(300, int(dialog_w * 0.27)))
        side_w_max = min(410, max(330, int(dialog_w * 0.32)))
        side_scroll.setMinimumWidth(side_w_min)
        side_scroll.setMaximumWidth(side_w_max)

    side_panel = QFrame()
    side_panel.setObjectName("sidePanel")
    side_layout = QVBoxLayout(side_panel)
    side_layout.setContentsMargins(14, 14, 14, 14)
    side_layout.setSpacing(12)
    side_scroll.setWidget(side_panel)

    def make_block(title_text):
        frame = QFrame(side_panel)
        frame.setObjectName("sectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        label = QLabel(title_text, frame)
        label.setStyleSheet("font-weight: 700; font-size: 15px;")
        layout.addWidget(label)
        return frame, layout

    block_print, block_print_layout = make_block("Co tisknout")
    key_check = QCheckBox("Klíč šifry", block_print)
    story_check = QCheckBox("Vlastní text / příběh", block_print)
    input_check = QCheckBox("Text k zašifrování", block_print)
    output_check = QCheckBox("Zašifrovaný text", block_print)
    key_check.setChecked(True)
    story_check.setChecked(False)
    input_check.setChecked(has_input)
    output_check.setChecked(has_output)
    input_check.setEnabled(has_input)
    output_check.setEnabled(has_output)
    for widget in (key_check, story_check, input_check, output_check):
        block_print_layout.addWidget(widget)
    side_layout.addWidget(block_print)

    block_titles, block_titles_layout = make_block("Nadpisy a názvy")
    show_headings_check = QCheckBox("Zobrazit nadpisy", block_titles)
    show_frames_check = QCheckBox("Zobrazit rámečky sekcí", block_titles)
    show_cipher_name_check = QCheckBox("Zobrazit malý název šifry nahoře", block_titles)
    show_headings_check.setChecked(True)
    show_frames_check.setChecked(True)
    show_cipher_name_check.setChecked(False)
    block_titles_layout.addWidget(show_headings_check)
    block_titles_layout.addWidget(show_frames_check)
    block_titles_layout.addWidget(show_cipher_name_check)

    title_form = QFormLayout()
    title_form.setHorizontalSpacing(8)
    title_form.setVerticalSpacing(8)
    key_title_edit = QLineEdit("Klíč šifry", block_titles)
    story_title_edit = QLineEdit("Vlastní text / příběh", block_titles)
    input_title_edit = QLineEdit("Text k zašifrování", block_titles)
    output_title_edit = QLineEdit("Zašifrovaný text", block_titles)
    title_form.addRow("Klíč:", key_title_edit)
    title_form.addRow("Příběh:", story_title_edit)
    title_form.addRow("Text:", input_title_edit)
    title_form.addRow("Šifra:", output_title_edit)
    block_titles_layout.addLayout(title_form)
    side_layout.addWidget(block_titles)

    block_story, block_story_layout = make_block("Vlastní text / příběh")
    story_edit = QTextEdit(block_story)
    story_edit.setObjectName("storyEditor")
    story_edit.setPlaceholderText("Sem napiš příběh, poznámku nebo instrukce...")
    story_edit.setMinimumHeight(95)
    block_story_layout.addWidget(story_edit)
    side_layout.addWidget(block_story)

    block_page, block_page_layout = make_block("Nastavení stránky")
    page_form = QFormLayout()
    page_form.setHorizontalSpacing(10)
    page_form.setVerticalSpacing(10)
    paper_combo = QComboBox(block_page)
    paper_combo.addItems(["A4", "A5", "A3", "Letter", "Legal"])
    paper_combo.setCurrentText("A4")
    orientation_combo = QComboBox(block_page)
    orientation_combo.addItems(["Na výšku", "Na šířku"])
    orientation_combo.setCurrentText("Na výšku")
    page_form.addRow("Papír:", paper_combo)
    page_form.addRow("Orientace:", orientation_combo)
    block_page_layout.addLayout(page_form)
    side_layout.addWidget(block_page)

    block_sizes, block_sizes_layout = make_block("Velikost a měřítko")
    size_form = QFormLayout()
    size_form.setHorizontalSpacing(8)
    size_form.setVerticalSpacing(8)

    def make_spin(minimum, maximum, value, suffix=" pt"):
        spin = QSpinBox(block_sizes)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(True)
        spin.setCorrectionMode(QAbstractSpinBox.CorrectToNearestValue)
        spin.setButtonSymbols(QAbstractSpinBox.UpDownArrows)
        return spin

    heading_size_spin = make_spin(8, 40, 20)
    key_size_spin = make_spin(8, 30, 12)
    story_size_spin = make_spin(8, 40, 12)
    input_size_spin = make_spin(8, 40, 13)
    output_size_spin = make_spin(8, 60, 13)
    cipher_scale_spin = make_spin(0, 300, 85, " %")

    size_form.addRow("Nadpisy:", heading_size_spin)
    size_form.addRow("Klíč:", key_size_spin)
    size_form.addRow("Příběh:", story_size_spin)
    size_form.addRow("Text:", input_size_spin)
    size_form.addRow("Zašif. text:", output_size_spin)
    size_form.addRow("Kreslená šifra:", cipher_scale_spin)
    block_sizes_layout.addLayout(size_form)

    hint_size = QLabel("Kreslená šifra mění měřítko obrázku. Textové šifry se řídí velikostí zašifrovaného textu.", block_sizes)
    hint_size.setWordWrap(True)
    hint_size.setStyleSheet("color: #d8c392; font-size: 12px;")
    block_sizes_layout.addWidget(hint_size)
    side_layout.addWidget(block_sizes)

    side_hint = QLabel(
        "Všechno vlevo můžeš upravit. Náhled vpravo ukazuje finální tisk.",
        side_panel,
    )
    side_hint.setWordWrap(True)
    side_hint.setStyleSheet("color: #cdb57e; font-size: 12px;")
    side_layout.addWidget(side_hint)
    side_layout.addStretch(1)

    content_layout.addWidget(side_scroll)

    page_frame = QFrame(dialog)
    page_frame.setObjectName("pageFrame")
    page_layout = QVBoxLayout(page_frame)
    page_layout.setContentsMargins(10 if compact_print_preview else 18, 10 if compact_print_preview else 18, 10 if compact_print_preview else 18, 10 if compact_print_preview else 18)
    page_layout.setSpacing(8 if compact_print_preview else 10)
    preview_header = QLabel("Náhled stránky", page_frame)
    preview_header.setStyleSheet("font-size: 16px; font-weight: 700;")
    page_layout.addWidget(preview_header)
    preview = QTextEdit(page_frame)
    preview.setObjectName("previewEdit")
    preview.setReadOnly(True)
    preview.setLineWrapMode(QTextEdit.WidgetWidth)
    page_layout.addWidget(preview, 1)
    content_layout.addWidget(page_frame, 1)

    buttons_layout = QHBoxLayout()
    buttons_layout.addStretch(1)
    print_button = QPushButton("Tisknout", dialog)
    cancel_button = QPushButton("Zrušit", dialog)
    cancel_button.setObjectName("cancelButton")
    print_button.setMinimumWidth(150)
    cancel_button.setMinimumWidth(120)
    buttons_layout.addWidget(print_button)
    buttons_layout.addWidget(cancel_button)
    main_layout.addLayout(buttons_layout)

    def current_options():
        return {
            "key": key_check.isChecked(),
            "story": story_check.isChecked(),
            "input": input_check.isChecked(),
            "output": output_check.isChecked(),
        }

    def current_page_setup():
        return paper_combo.currentText(), orientation_combo.currentText()

    def current_settings():
        # DŮLEŽITÉ: když uživatel napíše číslo ručně, QSpinBox ho nemusí
        # hned převést na hodnotu. interpretText() ho vynutí ještě před
        # sestavením náhledu i před tiskem.
        for spin in [heading_size_spin, key_size_spin, story_size_spin, input_size_spin, output_size_spin, cipher_scale_spin]:
            try:
                spin.interpretText()
            except Exception:
                pass

        return {
            "show_headings": show_headings_check.isChecked(),
            "show_frames": show_frames_check.isChecked(),
            "show_cipher_name": show_cipher_name_check.isChecked(),
            "key_title": key_title_edit.text().strip(),
            "story_title": story_title_edit.text().strip(),
            "input_title": input_title_edit.text().strip(),
            "output_title": output_title_edit.text().strip(),
            "story_text": story_edit.toPlainText(),
            "heading_size": heading_size_spin.value(),
            "key_font_size": key_size_spin.value(),
            "story_font_size": story_size_spin.value(),
            "input_font_size": input_size_spin.value(),
            "output_font_size": output_size_spin.value(),
            "cipher_scale": cipher_scale_spin.value(),
        }

    def update_preview():
        try:
            self._print_preview_needs_refresh = False
        except Exception:
            pass
        options = current_options()
        print_button.setEnabled(any(options.values()))
        paper_name, orientation_name = current_page_setup()

        if not any(options.values()):
            preview.setHtml(
                "<html><body style='font-family: Georgia; font-size: 13pt;'>"
                "<h2>Nic není vybráno</h2>"
                "<p>Zaškrtni alespoň jednu položku vlevo.</p>"
                "</body></html>"
            )
            return

        document = _print_options_build_document(
            self,
            options,
            drawn_widget,
            paper_name=paper_name,
            orientation_name=orientation_name,
            settings=current_settings(),
        )
        preview.setDocument(document)
        cursor = preview.textCursor()
        cursor.movePosition(QTextCursor.Start)
        preview.setTextCursor(cursor)
        try:
            if getattr(self, "_print_preview_needs_refresh", False):
                preview_timer.start(1600)
        except Exception:
            pass

    # Náhled nepřekreslujeme při každém drobném signálu okamžitě.
    # Krátký timer sesbírá rychlé změny do jednoho překreslení.
    preview_timer = QTimer(dialog)
    preview_timer.setSingleShot(True)
    preview_timer.timeout.connect(update_preview)

    def schedule_update_preview(*_args):
        preview_timer.start(900)

    widgets_to_update = [
        key_check,
        story_check,
        input_check,
        output_check,
        show_headings_check,
        show_frames_check,
        show_cipher_name_check,
    ]
    for widget in widgets_to_update:
        widget.toggled.connect(schedule_update_preview)

    for edit in [key_title_edit, story_title_edit, input_title_edit, output_title_edit]:
        edit.textChanged.connect(schedule_update_preview)

    story_edit.textChanged.connect(schedule_update_preview)
    paper_combo.currentTextChanged.connect(schedule_update_preview)
    orientation_combo.currentTextChanged.connect(schedule_update_preview)

    for spin in [heading_size_spin, key_size_spin, story_size_spin, input_size_spin, output_size_spin, cipher_scale_spin]:
        spin.valueChanged.connect(schedule_update_preview)
        try:
            spin.lineEdit().textEdited.connect(lambda _text, s=spin: (s.interpretText(), schedule_update_preview()))
            spin.editingFinished.connect(lambda s=spin: (s.interpretText(), schedule_update_preview()))
        except Exception:
            pass

    cancel_button.clicked.connect(dialog.reject)

    def do_print():
        options = current_options()
        if not any(options.values()):
            QMessageBox.information(dialog, "Nic není vybráno", "Zaškrtni alespoň jednu položku k tisku.")
            return

        paper_name, orientation_name = current_page_setup()
        document = _print_options_build_document(
            self,
            options,
            drawn_widget,
            paper_name=paper_name,
            orientation_name=orientation_name,
            settings=current_settings(),
        )

        printer = QPrinter(QPrinter.HighResolution)
        page_size_map = {
            "A5": QPageSize.A5,
            "A4": QPageSize.A4,
            "A3": QPageSize.A3,
            "Letter": QPageSize.Letter,
            "Legal": QPageSize.Legal,
        }
        printer.setPageSize(QPageSize(page_size_map.get(paper_name, QPageSize.A4)))
        printer.setPageOrientation(QPageLayout.Landscape if orientation_name == "Na šířku" else QPageLayout.Portrait)

        print_dialog = QPrintDialog(printer, dialog)
        print_dialog.setWindowTitle("Tisk")
        if print_dialog.exec() != QDialog.Accepted:
            return

        document.print_(printer)
        dialog.accept()

    print_button.clicked.connect(do_print)
    preview.setHtml("<html><body style='font-family: Georgia; font-size: 13pt;'><p>Připravuji náhled…</p></body></html>")
    schedule_update_preview()
    dialog.exec()


# Přepíše staré chování: už se neotevře nejdřív malé okno se zaškrtávátky,
# ale rovnou velký dialog s volbami a živým náhledem.
SifratorSkinWidget.print_current_result = _print_current_result_with_live_preview



# ============================================================
# OPRAVA BINÁRNÍCH ČTVERCŮ + KLÍČE V TISKU
# - Binární čtverce se zobrazují jako skutečná kreslená mřížka,
#   přesněji jako na vzoru: písmena ve slově na sebe navazují.
# - Tlačítko klíče je jen "KLÍČ" a je menší, aby se nekřížilo s TISK.
# - Do tisku se propisuje skutečný generovaný klíč z get_key_data().
# ============================================================

def _fixed_get_logic_module_for_print_key(self):
    """Vrátí modul logiky shodný s tím, který používá generování klíče šifry."""
    if hasattr(self, "get_selected_logic_module"):
        try:
            return self.get_selected_logic_module()
        except Exception as error:
            print(f"CHYBA při načítání logiky pro tisk klíče: {error}")
    return None


def _fixed_key_image_file_url(path: str) -> str:
    """Převede cestu k PNG souboru na URL vhodnou pro vložení do QTextDocument."""
    try:
        from pathlib import Path as _Path
        return _Path(path).resolve().as_uri()
    except Exception:
        return "file:///" + str(path).replace("\\", "/")


# Přepíšeme tiskový HTML blok klíče tak, aby nepoužíval jen ikonu šifry,
# ale skutečný pirátský generátor z pirate_key_renderer.py.
_ORIGINAL_PRINT_OPTIONS_KEY_HTML_FIXED = _print_options_key_html


def _print_options_key_html(self):
    cipher_name = self.selected_cipher or "Nevybraná šifra"
    parts = [f"<p><b>Vybraná šifra:</b> {_print_options_escape_html(cipher_name)}</p>"]

    renderer = get_pirate_key_renderer()
    logic_module = _fixed_get_logic_module_for_print_key(self)

    if renderer is not None and logic_module is not None:
        try:
            # Renderer si data vezme buď z get_key_data(), nebo nouzově z get_key_table().
            data = None
            if hasattr(renderer, "make_key_data_from_module"):
                key_context = self.get_current_key_context_for_cipher(cipher_name) if hasattr(self, "get_current_key_context_for_cipher") else None
                data = renderer.make_key_data_from_module(cipher_name, logic_module, key_context)

            if data:
                import tempfile
                safe_name = "".join(ch if ch.isalnum() else "_" for ch in cipher_name).strip("_") or "klic"
                image_path = os.path.join(tempfile.gettempdir(), f"sifrator_klic_{safe_name}.png")

                saved = False
                if hasattr(renderer, "save_key_png_for_module"):
                    saved = bool(renderer.save_key_png_for_module(cipher_name, logic_module, image_path, width=1400, context=key_context, print_mode=True))
                elif hasattr(renderer, "PirateKeyWidget"):
                    data = dict(data)
                    data["_print_mode"] = True
                    widget = renderer.PirateKeyWidget(data)
                    widget.resize(1400, widget.estimate_height(1400) if hasattr(widget, "estimate_height") else 900)
                    pixmap = QPixmap(widget.size())
                    pixmap.fill(QColor("#ffffff"))
                    widget.render(pixmap)
                    saved = pixmap.save(image_path, "PNG")

                if saved and os.path.exists(image_path):
                    url = _fixed_key_image_file_url(image_path)
                    parts.append(
                        "<p style='margin-top:10px;'>"
                        f"<img src='{_print_options_escape_html(url)}' width='690'>"
                        "</p>"
                    )
                    return "".join(parts)
        except Exception as error:
            parts.append(
                "<p style='color:#8a2d1f;'><b>Klíč se nepodařilo vložit do tisku:</b><br>"
                + _print_options_escape_html(str(error))
                + "</p>"
            )
            return "".join(parts)

    # Původní speciální klíče jako Caesar / Zlomky necháme jako zálohu.
    try:
        return _ORIGINAL_PRINT_OPTIONS_KEY_HTML_FIXED(self)
    except Exception:
        parts.append(
            "<p style='color:#555;'>Pro tuto šifru zatím není připravený generovaný klíč. "
            "Do logiky šifry doplň funkci <b>get_key_data()</b>.</p>"
        )
        return "".join(parts)


def get_binary_squares_widget_class():
    module = get_binary_squares_logic()
    if module is None:
        return None
    return getattr(module, "BinarySquaresOutputWidget", None)


def _binary_squares_create_canvas(self):
    widget_class = get_binary_squares_widget_class()
    if widget_class is not None:
        return widget_class()

    fallback = QLabel("Chybí kreslicí modul Binární čtverce")
    fallback.setStyleSheet("background: transparent; color: #f3d79a;")
    return fallback


def _binary_squares_resize_canvas_to_content(self, text: str | None = None):
    if not hasattr(self, "binary_squares_scroll") or not hasattr(self, "binary_squares_canvas"):
        return

    viewport_w = max(200, self.binary_squares_scroll.viewport().width())
    if hasattr(self.binary_squares_canvas, "set_available_width"):
        self.binary_squares_canvas.set_available_width(viewport_w)

    if text is None:
        text = self.get_input_text() if hasattr(self, "get_input_text") else ""

    if hasattr(self.binary_squares_canvas, "set_plain_text"):
        self.binary_squares_canvas.set_plain_text(text)
    elif hasattr(self.binary_squares_canvas, "set_cipher_text"):
        self.binary_squares_canvas.set_cipher_text(text)
    elif hasattr(self.binary_squares_canvas, "setText"):
        self.binary_squares_canvas.setText(text)

    hint = self.binary_squares_canvas.sizeHint()
    self.binary_squares_canvas.resize(max(viewport_w, hint.width()), max(hint.height(), self.binary_squares_scroll.viewport().height()))
    self.binary_squares_canvas.update()


def _binary_squares_hide_all_draw_outputs(self, keep_name: str | None = None):
    for name, widget in list(self.__dict__.items()):
        if name == keep_name:
            continue
        if name == "scroll_area":
            continue
        if name.endswith("_scroll") and isinstance(widget, QScrollArea):
            widget.hide()


_BINARY_ORIGINAL_CREATE_WIDGETS = SifratorSkinWidget.create_widgets
_BINARY_ORIGINAL_UPDATE_LAYOUT_POSITIONS = SifratorSkinWidget.update_layout_positions
_BINARY_ORIGINAL_APPLY_RESPONSIVE_FONTS = SifratorSkinWidget.apply_responsive_fonts
_BINARY_ORIGINAL_UPDATE_OUTPUT_WIDGET_MODE = SifratorSkinWidget.update_output_widget_mode
_BINARY_ORIGINAL_SET_RESULT_OUTPUT = SifratorSkinWidget.set_result_output


def _binary_squares_create_widgets(self):
    _BINARY_ORIGINAL_CREATE_WIDGETS(self)

    # Vlastní grafický výstup pro Binární čtverce.
    self.binary_squares_canvas = _binary_squares_create_canvas(self)
    self.binary_squares_scroll = QScrollArea(self)
    self.binary_squares_scroll.setWidgetResizable(False)
    self.binary_squares_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.binary_squares_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.binary_squares_scroll.setFrameShape(QScrollArea.NoFrame)
    self.binary_squares_scroll.setWidget(self.binary_squares_canvas)
    self.binary_squares_scroll.setStyleSheet("""
        QScrollArea {
            background: #fffdf8;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background: #fffdf8;
        }
        QScrollBar:vertical {
            background: rgba(20, 17, 12, 130);
            width: 11px;
            margin: 4px 2px 4px 2px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background: #b89b68;
            min-height: 42px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """)
    self.binary_squares_scroll.hide()

    # Text tlačítka klíče zkrátíme hned po vytvoření.
    if hasattr(self, "key_button"):
        self.key_button.setText("KLÍČ")
        self.key_button.setToolTip("Zobrazit klíč vybrané šifry")
        self.key_button.setMinimumWidth(0)


def _binary_squares_update_layout_positions(self):
    _BINARY_ORIGINAL_UPDATE_LAYOUT_POSITIONS(self)

    if hasattr(self, "binary_squares_scroll"):
        self.binary_squares_scroll.setGeometry(self.output_text.geometry())
        self.binary_squares_scroll.raise_()
        _binary_squares_resize_canvas_to_content(self)

    # Oprava překrývání KLÍČ / TISK. Obě tlačítka držíme na pravé straně nad výsledkem.
    if hasattr(self, "key_button"):
        out_rect = self.output_text.geometry()
        title_rect = self.result_title.geometry()
        key_w = max(72, int(92 * self.sx()))
        btn_h = max(26, int(36 * self.sy()))
        gap = max(7, int(10 * self.sx()))

        if hasattr(self, "print_button"):
            print_w = max(86, int(112 * self.sx()))
            print_x = out_rect.right() - print_w + 1
            y = title_rect.y() - max(2, int(2 * self.sy()))
            self.print_button.setGeometry(print_x, y, print_w, btn_h)
            self.print_button.raise_()
            self.print_button.show()

            key_x = max(out_rect.x(), print_x - gap - key_w)
            self.key_button.setGeometry(key_x, y, key_w, btn_h)
        else:
            self.key_button.setGeometry(out_rect.right() - key_w + 1, title_rect.y(), key_w, btn_h)

        self.key_button.raise_()
        self.key_button.show()


def _binary_squares_apply_responsive_fonts(self):
    _BINARY_ORIGINAL_APPLY_RESPONSIVE_FONTS(self)
    if hasattr(self, "key_button"):
        self.key_button.setFont(QFont("Georgia", self.fs(12), QFont.Bold))
    if hasattr(self, "print_button"):
        self.print_button.setFont(QFont("Georgia", self.fs(12), QFont.Bold))
        self.print_button.setIconSize(QSize(max(16, self.fs(21)), max(16, self.fs(21))))


def _binary_squares_update_output_widget_mode(self):
    _BINARY_ORIGINAL_UPDATE_OUTPUT_WIDGET_MODE(self)

    if self.is_binary_squares_selected() and self.result_mode == "encrypt" and hasattr(self, "binary_squares_scroll"):
        self.output_text.hide()
        _binary_squares_hide_all_draw_outputs(self, "binary_squares_scroll")
        self.binary_squares_scroll.show()
        self.binary_squares_scroll.raise_()
        _binary_squares_resize_canvas_to_content(self)


def _binary_squares_set_result_output(self, result: str):
    if self.is_binary_squares_selected() and self.result_mode == "encrypt" and hasattr(self, "binary_squares_scroll"):
        self.output_text.clear()
        self.output_text.hide()
        _binary_squares_hide_all_draw_outputs(self, "binary_squares_scroll")
        self.binary_squares_scroll.show()
        self.binary_squares_scroll.raise_()
        self.binary_squares_scroll.verticalScrollBar().setValue(0)
        _binary_squares_resize_canvas_to_content(self, self.get_input_text())
        QTimer.singleShot(0, lambda: _binary_squares_resize_canvas_to_content(self, self.get_input_text()))
        return

    return _BINARY_ORIGINAL_SET_RESULT_OUTPUT(self, result)


SifratorSkinWidget.create_widgets = _binary_squares_create_widgets
SifratorSkinWidget.update_layout_positions = _binary_squares_update_layout_positions
SifratorSkinWidget.apply_responsive_fonts = _binary_squares_apply_responsive_fonts
SifratorSkinWidget.update_output_widget_mode = _binary_squares_update_output_widget_mode
SifratorSkinWidget.set_result_output = _binary_squares_set_result_output
SifratorSkinWidget.resize_binary_squares_canvas_to_content = _binary_squares_resize_canvas_to_content


def set_windows_app_id():
    """Nastaví vlastní Windows AppUserModelID pro správné zobrazení ikony aplikace."""
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Komarek.SifratorMraveniste.PiratiZKaribiku"
            )
        except Exception:
            pass


def make_app_icon_from_logo(icons_path):
    """Vytvoří icons/app_icon.ico z icons/logo.png a vrátí cestu k ikoně.

    Windows pro ikonu okna / hlavního panelu nejlépe pracuje s .ico souborem.
    Pokud app_icon.ico už existuje, použije se rovnou.
    """
    logo_png = os.path.join(icons_path, "logo.png")
    logo_png_alt = os.path.join(icons_path, "Logo.png")
    ico_path = os.path.join(icons_path, "app_icon.ico")

    if os.path.exists(ico_path):
        return ico_path

    if not os.path.exists(logo_png) and os.path.exists(logo_png_alt):
        logo_png = logo_png_alt

    if not os.path.exists(logo_png):
        return ""

    if Image is None:
        return logo_png

    try:
        img = Image.open(logo_png).convert("RGBA")

        bbox = img.getchannel("A").getbbox()
        if bbox:
            img = img.crop(bbox)

        size = max(img.size)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)

        canvas.save(
            ico_path,
            format="ICO",
            sizes=[
                (16, 16),
                (24, 24),
                (32, 32),
                (48, 48),
                (64, 64),
                (128, 128),
                (256, 256),
            ],
        )
        return ico_path

    except Exception:
        return logo_png


class SifratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ŠIFRÁTOR MRAVENIŠTĚ - PIRÁTI Z KARIBIKU v{APP_VERSION}")

        # Responzivní obal pro celé pirátské UI.
        # Důvod: samotný skin má poměr 1672 × 941 a na menších MacBoocích / noteboocích
        # se původně okno nevešlo na obrazovku. ScrollArea nechá zachovat vzhled, ale
        # zároveň dovolí použití i na 800 × 600 bez oříznuté pravé části.
        self.central = SifratorSkinWidget()
        self.central.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.ui_scroll_area = QScrollArea(self)
        self.ui_scroll_area.setWidget(self.central)
        self.ui_scroll_area.setWidgetResizable(False)
        self.ui_scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.ui_scroll_area.setAlignment(Qt.AlignCenter)
        self.ui_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ui_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ui_scroll_area.setStyleSheet("""
            QScrollArea {
                background: #06131b;
                border: none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: rgba(20, 17, 12, 160);
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar:vertical { width: 12px; }
            QScrollBar:horizontal { height: 12px; }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #b89b68;
                border-radius: 5px;
                min-height: 34px;
                min-width: 34px;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
                height: 0px;
            }
        """)
        self.setCentralWidget(self.ui_scroll_area)

        self.setMinimumSize(800, 600)
        self.resize(*self._initial_window_size())
        self._apply_responsive_canvas_size()

        # Ikona celé aplikace z icons/logo.png / icons/app_icon.ico.
        app_icon_path = make_app_icon_from_logo(self.central.icons_path)
        if app_icon_path and os.path.exists(app_icon_path):
            app_icon = QIcon(app_icon_path)
            self.setWindowIcon(app_icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(app_icon)

        # Na malých obrazovkách se aplikace otevře rovnou maximalizovaná, aby se
        # využila celá dostupná plocha mimo horní lištu a Dock.
        QTimer.singleShot(0, self._maximize_on_small_screen_if_needed)

        # Kontrola aktualizací až po zobrazení okna.
        # Když není internet nebo není novější verze, nic nevyskočí.
        QTimer.singleShot(1500, self.check_updates_after_start)

    def _available_screen_geometry(self):
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return QRect(0, 0, BASE_W, BASE_H)
        return screen.availableGeometry()

    def _initial_window_size(self):
        available = self._available_screen_geometry()
        # Okno se na startu nikdy nesnaží být větší než dostupná plocha obrazovky.
        # Na 4K a větších monitorech zůstane rozumně velké, aby UI nebylo obří.
        target_w = min(BASE_W, max(800, int(available.width() * 0.96)))
        target_h = min(BASE_H, max(600, int(available.height() * 0.92)))
        return target_w, target_h

    def _responsive_canvas_size(self):
        viewport = self.ui_scroll_area.viewport().size() if hasattr(self, "ui_scroll_area") else self.size()
        viewport_w = max(1, viewport.width())
        viewport_h = max(1, viewport.height())

        # Malý režim: UI se drží čitelnější minimální pracovní plochy a okno dostane scroll.
        if viewport_w < 1000 or viewport_h < 620:
            return QSize(1050, 650)

        # Kompaktní notebookový režim: vejde se na menší MacBooky / HD displeje bez oříznutí.
        if viewport_w < 1300 or viewport_h < 760:
            return QSize(max(1050, viewport_w), max(650, viewport_h))

        # Normální režim: UI se přizpůsobí oknu až do původního návrhu.
        if viewport_w < BASE_W or viewport_h < BASE_H:
            return QSize(max(1200, viewport_w), max(675, viewport_h))

        # Velké a 4K monitory: držíme původní rozumný návrh uprostřed obrazovky.
        return QSize(BASE_W, BASE_H)

    def _apply_responsive_canvas_size(self):
        if not hasattr(self, "central"):
            return
        size = self._responsive_canvas_size()
        if self.central.size() != size:
            self.central.setFixedSize(size)
        self.central.update_layout_positions()
        self.central.update()

    def _maximize_on_small_screen_if_needed(self):
        available = self._available_screen_geometry()
        if available.width() < 1300 or available.height() < 760:
            self.showMaximized()
        self._apply_responsive_canvas_size()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._apply_responsive_canvas_size)

    def check_updates_after_start(self):
        update_data = update_manager.check_for_update(APP_VERSION)

        if not update_data:
            return

        remote_version = update_data.get("version", "")
        notes = update_data.get("notes", "")

        message = (
            f"Je dostupná nová verze {remote_version}.\n\n"
            f"Aktuální verze: {APP_VERSION}\n\n"
            f"{notes}\n\n"
            "Chceš aplikaci aktualizovat?"
        )

        answer = QMessageBox.question(
            self,
            "Dostupná aktualizace",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if answer == QMessageBox.Yes:
            try:
                update_manager.download_and_install_update(update_data)
            except Exception as error:
                QMessageBox.critical(
                    self,
                    "Chyba aktualizace",
                    f"Aktualizaci se nepodařilo dokončit:\n\n{error}",
                )

# ============================================================
# FINÁLNÍ OPRAVA: čitelné klíče + průhledné UI + bílý tisk
# ============================================================

# Přesměrování na nový renderer vedle main.py.
def get_pirate_key_renderer_file():
    """Vyhledá společný modul pro generování grafických klíčů šifer.

    Cesty jsou řazené tak, aby fungovaly ve vývoji, ve Windows onedir buildu
    i v macOS .app balíčku.
    """
    candidates = [
        os.path.join(get_app_dir(), "pirate_key_renderer.py"),
        os.path.join(get_script_dir(), "pirate_key_renderer.py"),
        os.path.join(get_app_dir(), "logika sifer", "spolecne", "pirate_key_renderer.py"),
        os.path.join(get_script_dir(), "logika sifer", "spolecne", "pirate_key_renderer.py"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "pirate_key_renderer.py"))
        candidates.append(os.path.join(bundle_dir, "logika sifer", "spolecne", "pirate_key_renderer.py"))

    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        macos_dir = os.path.dirname(sys.executable)
        contents_dir = os.path.dirname(macos_dir)
        resources_dir = os.path.join(contents_dir, "Resources")
        candidates.append(os.path.join(resources_dir, "pirate_key_renderer.py"))
        candidates.append(os.path.join(resources_dir, "logika sifer", "spolecne", "pirate_key_renderer.py"))

    for path in candidates:
        if path and os.path.exists(path):
            return path

    return os.path.join(get_app_dir(), "pirate_key_renderer.py")


def _reload_pirate_key_renderer():
    global PIRATE_KEY_RENDERER
    PIRATE_KEY_RENDERER = None
    return get_pirate_key_renderer()


# Binární čtverce: když přepnu na jinou šifru, starý binární widget se musí vždy schovat.
def _binary_squares_update_output_widget_mode_fixed(self):
    if self.is_binary_squares_selected() and self.result_mode == "encrypt" and hasattr(self, "binary_squares_scroll"):
        self.output_text.hide()
        _binary_squares_hide_all_draw_outputs(self, "binary_squares_scroll")
        self.binary_squares_scroll.show()
        self.binary_squares_scroll.raise_()
        _binary_squares_resize_canvas_to_content(self)
        return

    if hasattr(self, "binary_squares_scroll"):
        self.binary_squares_scroll.hide()

    return _BINARY_ORIGINAL_UPDATE_OUTPUT_WIDGET_MODE(self)


def _binary_squares_set_result_output_fixed(self, result: str):
    if self.is_binary_squares_selected() and self.result_mode == "encrypt" and hasattr(self, "binary_squares_scroll"):
        self.output_text.clear()
        self.output_text.hide()
        _binary_squares_hide_all_draw_outputs(self, "binary_squares_scroll")
        self.binary_squares_scroll.show()
        self.binary_squares_scroll.raise_()
        self.binary_squares_scroll.verticalScrollBar().setValue(0)
        _binary_squares_resize_canvas_to_content(self, self.get_input_text())
        QTimer.singleShot(0, lambda: _binary_squares_resize_canvas_to_content(self, self.get_input_text()))
        return

    if hasattr(self, "binary_squares_scroll"):
        self.binary_squares_scroll.hide()

    return _BINARY_ORIGINAL_SET_RESULT_OUTPUT(self, result)


# Binární čtverce: v UI má být průhledná plocha, ne bílý papír.
_PREV_CREATE_WIDGETS_TRANSPARENT_UI = SifratorSkinWidget.create_widgets


def _create_widgets_transparent_binary_ui(self):
    _PREV_CREATE_WIDGETS_TRANSPARENT_UI(self)
    if hasattr(self, "binary_squares_scroll"):
        self.binary_squares_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: rgba(20, 17, 12, 130);
                width: 11px;
                margin: 4px 2px 4px 2px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #b89b68;
                min-height: 42px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        viewport = self.binary_squares_scroll.viewport()
        if viewport is not None:
            viewport.setStyleSheet("background: transparent;")


SifratorSkinWidget.create_widgets = _create_widgets_transparent_binary_ui
SifratorSkinWidget.update_output_widget_mode = _binary_squares_update_output_widget_mode_fixed
SifratorSkinWidget.set_result_output = _binary_squares_set_result_output_fixed





# ============================================================
# RYCHLÉ PŘEDNAČÍTÁNÍ KLÍČŮ A NÁHLEDU TISKU NA POZADÍ
# ============================================================

# Důležité: QPixmap a QWidget renderování musí běžet v hlavním Qt vlákně.
# Proto se nepoužívá Python thread, ale QTimer. Po šifrování se UI nejdřív
# překreslí a až potom se v krátké pauze připraví cache pro KLÍČ a TISK.


def _print_cache_safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "")).strip("_") or "cache"


def _print_cache_freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((str(k), _print_cache_freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_print_cache_freeze(v) for v in value)
    return str(value)


def _print_cache_context_signature(self):
    try:
        context = self.get_current_key_context_for_cipher(self.selected_cipher) if hasattr(self, "get_current_key_context_for_cipher") else {}
    except Exception:
        context = {}
    return _print_cache_freeze(context)


def _print_cache_logic_signature(self):
    logic_module = None
    try:
        logic_module = self.get_selected_logic_module() if hasattr(self, "get_selected_logic_module") else None
    except Exception:
        logic_module = None

    logic_file = getattr(logic_module, "__file__", "") if logic_module is not None else ""
    logic_mtime = 0
    try:
        if logic_file and os.path.exists(logic_file):
            logic_mtime = int(os.path.getmtime(logic_file))
    except Exception:
        logic_mtime = 0

    renderer_file = ""
    renderer_mtime = 0
    try:
        renderer_file = get_pirate_key_renderer_file()
        if renderer_file and os.path.exists(renderer_file):
            renderer_mtime = int(os.path.getmtime(renderer_file))
    except Exception:
        pass

    return logic_module, (logic_file, logic_mtime, renderer_file, renderer_mtime)


def _print_cache_current_signature(self, drawn_widget=None):
    input_text = self.input_text.toPlainText() if hasattr(self, "input_text") else ""
    output_text = self.output_text.toPlainText() if hasattr(self, "output_text") else ""
    drawn_size = ""
    if drawn_widget is not None:
        try:
            drawn_size = f"{drawn_widget.width()}x{drawn_widget.height()}"
        except Exception:
            drawn_size = "drawn"
    _logic_module, logic_sig = _print_cache_logic_signature(self)
    return (
        str(self.selected_cipher or ""),
        str(getattr(self, "result_mode", "")),
        input_text,
        output_text,
        drawn_size,
        _print_cache_context_signature(self),
        logic_sig,
    )


def _print_cache_get_key_image_path(self, force: bool = False, print_mode: bool = True) -> str:
    if not getattr(self, "selected_cipher", None):
        return ""

    renderer = get_pirate_key_renderer()
    logic_module, logic_sig = _print_cache_logic_signature(self)
    if renderer is None or logic_module is None:
        return ""

    cipher_name = self.selected_cipher or "Nevybraná šifra"
    key_context = self.get_current_key_context_for_cipher(cipher_name) if hasattr(self, "get_current_key_context_for_cipher") else None
    sig = ("key_png", cipher_name, _print_cache_context_signature(self), logic_sig, 1400, bool(print_mode))

    cache = getattr(self, "_print_key_image_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        self._print_key_image_cache = cache

    cached_path = cache.get(sig)
    if not force and cached_path and os.path.exists(cached_path):
        return cached_path

    import tempfile
    safe_name = _print_cache_safe_name(cipher_name)
    suffix = "print" if print_mode else "ui"
    image_path = os.path.join(tempfile.gettempdir(), f"sifrator_klic_cache_{safe_name}_{suffix}_{abs(hash(sig))}.png")

    try:
        if hasattr(renderer, "save_key_png_for_module"):
            saved = bool(renderer.save_key_png_for_module(cipher_name, logic_module, image_path, width=1400, context=key_context, print_mode=print_mode))
        else:
            saved = False
        if saved and os.path.exists(image_path):
            # Necháme v cache více verzí, aby přepnutí náhledu nebo opakované otevření bylo okamžité.
            if len(cache) > 30:
                cache.clear()
            cache[sig] = image_path
            return image_path
    except Exception as error:
        print(f"CHYBA cache klíče: {error}")

    return ""


def _print_cache_get_drawn_result_image(self, drawn_widget=None, force: bool = False) -> QImage:
    if drawn_widget is None:
        drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
    if drawn_widget is None:
        return QImage()

    sig = ("drawn", _print_cache_current_signature(self, drawn_widget))
    cache = getattr(self, "_print_drawn_image_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        self._print_drawn_image_cache = cache

    cached = cache.get(sig)
    if not force and isinstance(cached, QImage) and not cached.isNull():
        return cached

    try:
        pixmap = drawn_widget.grab()
        if pixmap.isNull():
            return QImage()
        image = _print_crop_image_to_content(pixmap.toImage())
        image = _print_image_black_on_white(image)
        if len(cache) > 20:
            cache.clear()
        cache[sig] = image
        return image
    except Exception as error:
        print(f"CHYBA cache kresleného výsledku: {error}")
        return QImage()


# Přepíšeme tiskový HTML klíč tak, aby nejdřív použil přednačtený PNG z cache.
def _print_options_key_html(self):
    cipher_name = self.selected_cipher or "Nevybraná šifra"
    parts = [f"<p><b>Vybraná šifra:</b> {_print_options_escape_html(cipher_name)}</p>"]

    image_path = _print_cache_get_key_image_path(self, force=False, print_mode=True)
    if image_path and os.path.exists(image_path):
        url = _fixed_key_image_file_url(image_path) if '_fixed_key_image_file_url' in globals() else image_path
        parts.append(
            "<p style='margin-top:10px;'>"
            f"<img src='{_print_options_escape_html(url)}' width='690'>"
            "</p>"
        )
        return "".join(parts)

    try:
        return _ORIGINAL_PRINT_OPTIONS_KEY_HTML_FIXED(self)
    except Exception:
        parts.append("<p style='color:#555;'>Klíč se nepodařilo připravit.</p>")
        return "".join(parts)


# Cache celého QTextDocumentu pro první náhled. Těžké obrázky jsou už uložené,
# takže otevření okna TISK nemusí znovu generovat klíč ani kreslenou šifru.
try:
    _PRINT_PRELOAD_ORIGINAL_BUILD_DOCUMENT = _print_options_build_document

    def _print_options_build_document(self, options: dict, drawn_widget, paper_name="A4", orientation_name="Na výšku", settings=None):
        settings = settings or {}
        sig = (
            "document",
            _print_cache_freeze(options),
            str(paper_name),
            str(orientation_name),
            _print_cache_freeze(settings),
            _print_cache_current_signature(self, drawn_widget),
        )
        cache = getattr(self, "_print_document_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._print_document_cache = cache

        cached = cache.get(sig)
        if cached is not None:
            return cached

        document = _PRINT_PRELOAD_ORIGINAL_BUILD_DOCUMENT(
            self,
            options,
            drawn_widget,
            paper_name=paper_name,
            orientation_name=orientation_name,
            settings=settings,
        )
        if len(cache) > 8:
            cache.clear()
        cache[sig] = document
        return document
except Exception:
    pass


def _print_cache_default_options(self):
    has_input = bool(self.input_text.toPlainText().strip()) if hasattr(self, "input_text") else False
    has_output = False
    try:
        drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
        has_output = bool(
            (hasattr(self, "output_text") and self.output_text.isVisible() and self.output_text.toPlainText().strip())
            or drawn_widget is not None
        )
    except Exception:
        has_output = bool(hasattr(self, "output_text") and self.output_text.toPlainText().strip())
    return {
        "key": True,
        "story": False,
        "input": has_input,
        "output": has_output,
    }


def _print_cache_default_settings(self):
    return {
        "show_headings": True,
        "show_frames": True,
        "show_cipher_name": False,
        "key_title": "Klíč šifry",
        "story_title": "Vlastní text / příběh",
        "input_title": "Text k zašifrování",
        "output_title": "Zašifrovaný text",
        "story_text": "",
        "heading_size": 20,
        "key_font_size": 12,
        "story_font_size": 12,
        "input_font_size": 13,
        "output_font_size": 13,
        "cipher_scale": 85,
    }


def _print_cache_preload_now(self, token=None):
    if token is not None and token != getattr(self, "_print_cache_preload_token", None):
        return
    if not getattr(self, "selected_cipher", None):
        return

    drawn_widget = None
    try:
        drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
    except Exception:
        drawn_widget = None

    # 1) Tiskový klíč – bez pergamenu, černobílý.
    try:
        _print_cache_get_key_image_path(self, force=False, print_mode=True)
    except Exception as error:
        print(f"CHYBA přednačítání tiskového klíče: {error}")

    # 2) Normální klíč – jen pro zahřátí rendereru a symbolové cache.
    try:
        _print_cache_get_key_image_path(self, force=False, print_mode=False)
    except Exception:
        pass

    # 3) Kreslený výsledek pro tisk – černě na bílo.
    try:
        if drawn_widget is not None:
            _print_cache_get_drawn_result_image(self, drawn_widget, force=False)
    except Exception as error:
        print(f"CHYBA přednačítání grafické šifry: {error}")

    # 4) Základní dokument náhledu tisku s výchozími volbami.
    try:
        if '_PRINT_PRELOAD_ORIGINAL_BUILD_DOCUMENT' in globals():
            _print_options_build_document(
                self,
                _print_cache_default_options(self),
                drawn_widget,
                paper_name="A4",
                orientation_name="Na výšku",
                settings=_print_cache_default_settings(self),
            )
    except Exception as error:
        print(f"CHYBA přednačítání náhledu tisku: {error}")


def _schedule_print_cache_preload(self, delay_ms: int = 350):
    try:
        self._print_cache_preload_token = int(getattr(self, "_print_cache_preload_token", 0)) + 1
        token = self._print_cache_preload_token
        QTimer.singleShot(delay_ms, lambda: _print_cache_preload_now(self, token))
    except Exception:
        pass


def _clear_print_preload_cache(self):
    for attr in ("_print_key_image_cache", "_print_drawn_image_cache", "_print_document_cache"):
        try:
            cache = getattr(self, attr, None)
            if isinstance(cache, dict):
                cache.clear()
        except Exception:
            pass


# Otevření tisku ještě před oknem TISK zkusí cache dotáhnout. Když už je hotová,
# je to okamžité. Když hotová není, připraví se alespoň teď a náhled už ji použije.
try:
    _PRELOAD_ORIGINAL_PRINT_CURRENT_RESULT = SifratorSkinWidget.print_current_result

    def _preload_print_current_result(self):
        try:
            _print_cache_preload_now(self)
        except Exception:
            pass
        return _PRELOAD_ORIGINAL_PRINT_CURRENT_RESULT(self)

    SifratorSkinWidget.print_current_result = _preload_print_current_result
except Exception:
    pass


# Po výběru jiné šifry cache smažeme a připravíme novou.
try:
    _PRELOAD_ORIGINAL_SELECT_CIPHER = SifratorSkinWidget.select_cipher

    def _preload_select_cipher(self, name):
        result = _PRELOAD_ORIGINAL_SELECT_CIPHER(self, name)
        _clear_print_preload_cache(self)
        _schedule_print_cache_preload(self, 250)
        return result

    SifratorSkinWidget.select_cipher = _preload_select_cipher
except Exception:
    pass


# Po každém šifrování/dešifrování se cache připraví sama s malým zpožděním.
try:
    _PRELOAD_ORIGINAL_AUTO_ENCRYPT_ACTION = SifratorSkinWidget.auto_encrypt_action

    def _preload_auto_encrypt_action(self):
        result = _PRELOAD_ORIGINAL_AUTO_ENCRYPT_ACTION(self)
        _schedule_print_cache_preload(self, 250)
        return result

    SifratorSkinWidget.auto_encrypt_action = _preload_auto_encrypt_action
except Exception:
    pass

try:
    _PRELOAD_ORIGINAL_ENCRYPT_ACTION = SifratorSkinWidget.encrypt_action

    def _preload_encrypt_action(self):
        result = _PRELOAD_ORIGINAL_ENCRYPT_ACTION(self)
        _schedule_print_cache_preload(self, 250)
        return result

    SifratorSkinWidget.encrypt_action = _preload_encrypt_action
except Exception:
    pass

try:
    _PRELOAD_ORIGINAL_DECRYPT_ACTION = SifratorSkinWidget.decrypt_action

    def _preload_decrypt_action(self):
        result = _PRELOAD_ORIGINAL_DECRYPT_ACTION(self)
        _schedule_print_cache_preload(self, 250)
        return result

    SifratorSkinWidget.decrypt_action = _preload_decrypt_action
except Exception:
    pass



# ============================================================
# OPRAVA ZASEKÁVÁNÍ – šetrné přednačítání cache
# ============================================================
# Důvod:
# Qt neumí bezpečně renderovat QWidget/QPixmap v běžném Python vlákně.
# Proto se přednačítání dělá v hlavním GUI vlákně přes QTimer.
# Aby se aplikace nezasekávala, těžké části se rozdělí do menších kroků
# a spouští se až po delší pauze po psaní / změně šifry.

_PRINT_PRELOAD_MIN_DELAY_MS = 1200
_PRINT_PRELOAD_STEP_DELAY_MS = 80


def _print_cache_preload_now(self, token=None):
    """Šetrné přednačtení cache bez dlouhého jednorázového záseku GUI.

    Nepředgenerovává celý QTextDocument, protože to je nejčastější příčina
    zasekávání při psaní. Dokument se vytvoří až při skutečném otevření náhledu.
    """
    if token is not None and token != getattr(self, "_print_cache_preload_token", None):
        return
    if getattr(self, "_print_cache_preload_running", False):
        return
    if not getattr(self, "selected_cipher", None):
        return

    self._print_cache_preload_running = True

    def token_valid():
        return token is None or token == getattr(self, "_print_cache_preload_token", None)

    def finish():
        try:
            self._print_cache_preload_running = False
        except Exception:
            pass

    def get_drawn_widget():
        try:
            return self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
        except Exception:
            return None

    steps = []

    # 1) Tiskový klíč – nejdůležitější pro náhled tisku.
    def preload_print_key():
        if not token_valid():
            finish()
            return
        try:
            _print_cache_get_key_image_path(self, force=False, print_mode=True)
        except Exception as error:
            print(f"CHYBA přednačítání tiskového klíče: {error}")

    steps.append(preload_print_key)

    # 2) Kreslený výsledek pro tisk – jen pokud je vidět grafický výstup.
    def preload_drawn_result():
        if not token_valid():
            finish()
            return
        try:
            drawn_widget = get_drawn_widget()
            if drawn_widget is not None:
                _print_cache_get_drawn_result_image(self, drawn_widget, force=False)
        except Exception as error:
            print(f"CHYBA přednačítání grafické šifry: {error}")

    steps.append(preload_drawn_result)

    # 3) Běžný klíč pro dialog KLÍČ – nízká priorita, až po tisku.
    def preload_ui_key():
        if not token_valid():
            finish()
            return
        try:
            _print_cache_get_key_image_path(self, force=False, print_mode=False)
        except Exception:
            pass

    steps.append(preload_ui_key)

    def run_step(index=0):
        if not token_valid():
            finish()
            return
        if index >= len(steps):
            finish()
            return
        try:
            steps[index]()
        finally:
            if token_valid():
                QTimer.singleShot(_PRINT_PRELOAD_STEP_DELAY_MS, lambda: run_step(index + 1))
            else:
                finish()

    QTimer.singleShot(0, lambda: run_step(0))


def _schedule_print_cache_preload(self, delay_ms: int = 1200):
    """Naplánuje přednačítání až po pauze.

    Původních cca 250 ms bylo moc krátké: při psaní se preload spouštěl
    téměř hned po každém znaku a tím blokoval GUI.
    """
    try:
        self._print_cache_preload_token = int(getattr(self, "_print_cache_preload_token", 0)) + 1
        token = self._print_cache_preload_token
        delay = max(int(delay_ms or 0), _PRINT_PRELOAD_MIN_DELAY_MS)
        QTimer.singleShot(delay, lambda: _print_cache_preload_now(self, token))
    except Exception:
        pass



# ============================================================
# NEMRZNOUCÍ TISK A KLÍČ – finální bezpečná vrstva
# ============================================================
# Důležité:
# - kliknutí na TISK už nesmí nejdřív generovat klíč ani grabovat grafický výstup.
# - kliknutí na KLÍČ otevře dialog hned a teprve potom se klíč doplní.
# - náhled tisku používá jen hotovou cache; když cache není, zobrazí text „připravuje se“.


def _print_cache_peek_key_image_path(self, print_mode: bool = True) -> str:
    """Vrátí pouze již existující obrázek klíče z cache bez spouštění generování."""
    try:
        if not getattr(self, "selected_cipher", None):
            return ""
        logic_module, logic_sig = _print_cache_logic_signature(self)
        if logic_module is None:
            return ""
        cipher_name = self.selected_cipher or "Nevybraná šifra"
        sig = ("key_png", cipher_name, _print_cache_context_signature(self), logic_sig, 1400, bool(print_mode))
        cache = getattr(self, "_print_key_image_cache", None)
        if isinstance(cache, dict):
            path = cache.get(sig)
            if path and os.path.exists(path):
                return path
    except Exception:
        pass
    return ""


def _print_cache_peek_drawn_result_image(self, drawn_widget=None) -> QImage:
    """Vrátí pouze již připravený grafický výsledek z cache bez volání grab()."""
    try:
        if drawn_widget is None:
            drawn_widget = self.print_find_visible_draw_widget() if hasattr(self, "print_find_visible_draw_widget") else None
        if drawn_widget is None:
            return QImage()
        sig = ("drawn", _print_cache_current_signature(self, drawn_widget))
        cache = getattr(self, "_print_drawn_image_cache", None)
        if isinstance(cache, dict):
            image = cache.get(sig)
            if isinstance(image, QImage) and not image.isNull():
                return image
    except Exception:
        pass
    return QImage()


# Přepíšeme HTML klíče: použije hotový obrázek, nebo jen placeholder.
def _print_options_key_html(self):
    cipher_name = self.selected_cipher or "Nevybraná šifra"
    parts = [f"<p><b>Vybraná šifra:</b> {_print_options_escape_html(cipher_name)}</p>"]

    image_path = _print_cache_peek_key_image_path(self, print_mode=True)
    if image_path and os.path.exists(image_path):
        url = _fixed_key_image_file_url(image_path) if '_fixed_key_image_file_url' in globals() else image_path
        parts.append(
            "<p style='margin-top:10px;'>"
            f"<img src='{_print_options_escape_html(url)}' width='690'>"
            "</p>"
        )
        return "".join(parts)

    parts.append("<p><i>Klíč se připravuje na pozadí. Náhled se po chvíli obnoví.</i></p>")
    try:
        self._print_preview_needs_refresh = True
    except Exception:
        pass
    try:
        if '_schedule_print_cache_preload' in globals():
            _schedule_print_cache_preload(self, 120)
    except Exception:
        pass
    return "".join(parts)


# Otevření TISK nesmí spouštět synchronní preload před otevřením okna.
try:
    SifratorSkinWidget.print_current_result = _print_current_result_with_live_preview
except Exception:
    pass


# Otevření KLÍČ: použij async dialog z rendereru, pokud je dostupný.
try:
    _NONBLOCK_ORIGINAL_SHOW_CIPHER_KEY = SifratorSkinWidget.show_cipher_key

    def _nonblocking_show_cipher_key(self):
        if not self.selected_cipher:
            QMessageBox.information(self, "Klíč šifry", "Nejdřív vyber šifru.")
            return

        renderer = get_pirate_key_renderer()
        if renderer is None:
            QMessageBox.critical(self, "Chybí generátor klíčů", "Chybí soubor:\npirate_key_renderer.py")
            return

        logic_module = self.get_selected_logic_module() if hasattr(self, "get_selected_logic_module") else None
        if logic_module is None:
            QMessageBox.information(self, "Klíč šifry", "Pro tuto šifru se nepodařilo načíst soubor logiky.")
            return

        key_context = self.get_current_key_context() if hasattr(self, "get_current_key_context") else None

        try:
            if hasattr(renderer, "show_key_dialog_nonblocking"):
                renderer.show_key_dialog_nonblocking(self, self.selected_cipher, logic_module, key_context)
            else:
                # Fallback: otevře původní dialog.
                renderer.show_key_dialog(self, self.selected_cipher, logic_module, key_context)
        except Exception as error:
            QMessageBox.critical(self, "Chyba klíče", f"Klíč se nepodařilo zobrazit:\n\n{error}")

    SifratorSkinWidget.show_cipher_key = _nonblocking_show_cipher_key
except Exception:
    pass




# ============================================================
# PATCHE: spodní klikací LOGOVÁNÍ + AKTUALIZACE + live log okno
# ============================================================

_FOOTER_ORIGINAL_CREATE_WIDGETS = SifratorSkinWidget.create_widgets
_FOOTER_ORIGINAL_UPDATE_STATUS = SifratorSkinWidget.update_status
_FOOTER_ORIGINAL_UPDATE_LAYOUT_POSITIONS = SifratorSkinWidget.update_layout_positions


def _sifrator_debug_log(message: str) -> None:
    """Zapíše diagnostickou zprávu do aktualizačního logu, pokud je dostupný."""
    try:
        if hasattr(update_manager, "_debug_log"):
            update_manager._debug_log(str(message))
            return
    except Exception:
        pass

    try:
        path = os.path.join(tempfile.gettempdir(), "sifrator_update_debug.log")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _sifrator_debug_log_path() -> str:
    try:
        if hasattr(update_manager, "get_debug_log_path"):
            return update_manager.get_debug_log_path()
    except Exception:
        pass
    try:
        return os.path.join(tempfile.gettempdir(), "sifrator_update_debug.log")
    except Exception:
        return "sifrator_update_debug.log"


class LiveLogDialog(QDialog):
    """Jednoduché okno s live výpisem diagnostických logů aplikace/updateru."""

    def __init__(self, owner_window):
        super().__init__(owner_window)
        self.owner_window = owner_window
        self.setWindowTitle("Živé logování – Šifrátor Mraveniště")
        self.resize(880, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.info_label = QLabel(self)
        self.info_label.setText(
            "Live logy aktualizací a aplikace. "
            "Po zavření tohoto okna se logování automaticky vypne."
        )
        self.info_label.setStyleSheet("color: #ead8b3;")
        layout.addWidget(self.info_label)

        self.log_edit = QTextEdit(self)
        self.log_edit.setReadOnly(True)
        self.log_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.log_edit.setStyleSheet("""
            QTextEdit {
                color: #f0e2c0;
                background: #071018;
                border: 1px solid #8a6938;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Menlo, Monaco, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_edit, 1)

        button_row = QHBoxLayout()
        self.path_label = QLabel(self)
        self.path_label.setText(_sifrator_debug_log_path())
        self.path_label.setStyleSheet("color: #a8a295;")
        button_row.addWidget(self.path_label, 1)

        self.clear_button = QPushButton("Vyčistit log", self)
        self.refresh_button = QPushButton("Obnovit", self)
        self.close_button = QPushButton("Zavřít", self)
        button_row.addWidget(self.clear_button)
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.clear_button.clicked.connect(self.clear_log)
        self.refresh_button.clicked.connect(self.refresh_log)
        self.close_button.clicked.connect(self.close)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_log)
        self.timer.start(700)
        self.refresh_log()

    def clear_log(self):
        path = _sifrator_debug_log_path()
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write("")
        except Exception as error:
            self.log_edit.setPlainText(f"Log se nepodařilo vyčistit:\n{error}")
            return
        _sifrator_debug_log("Log byl vyčištěn z okna LOGOVÁNÍ.")
        self.refresh_log()

    def refresh_log(self):
        path = _sifrator_debug_log_path()
        self.path_label.setText(path)
        try:
            if not os.path.exists(path):
                self.log_edit.setPlainText("Log zatím neexistuje. Spusť kontrolu aktualizací nebo proveď akci v aplikaci.")
                return

            with open(path, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()

            if not content.strip():
                content = "Log je zatím prázdný."

            # Nezobrazujeme nekonečně dlouhý soubor, poslední část stačí pro živou diagnostiku.
            max_chars = 80000
            if len(content) > max_chars:
                content = "... zkráceno na posledních 80000 znaků ...\n" + content[-max_chars:]

            old_bar = self.log_edit.verticalScrollBar().value()
            was_at_bottom = old_bar >= self.log_edit.verticalScrollBar().maximum() - 8
            self.log_edit.setPlainText(content)
            if was_at_bottom:
                self.log_edit.verticalScrollBar().setValue(self.log_edit.verticalScrollBar().maximum())
        except Exception as error:
            self.log_edit.setPlainText(f"Log se nepodařilo načíst:\n{error}")

    def closeEvent(self, event):
        try:
            self.timer.stop()
        except Exception:
            pass
        if self.owner_window is not None and hasattr(self.owner_window, "set_live_logging_enabled"):
            self.owner_window.set_live_logging_enabled(False)
        super().closeEvent(event)


def _footer_prepare_links(self):
    """Připraví samostatné klikací texty ve spodním řádku."""
    if hasattr(self, "log_status_link") and hasattr(self, "update_status_link"):
        return

    base_style = "background: transparent; color: #d9c697;"
    link_style = "background: transparent; color: #f3d79a;"

    self.log_status_link = QLabel(self)
    self.log_status_link.setStyleSheet(link_style)
    self.log_status_link.setCursor(Qt.PointingHandCursor)
    self.log_status_link.setToolTip("Kliknutím zapneš logování a otevřeš live logy.")
    self.log_status_link.mousePressEvent = lambda event: _footer_log_clicked(self, event)

    self.src_status_label = QLabel(self)
    self.src_status_label.setStyleSheet(base_style)

    self.update_status_link = QLabel(self)
    self.update_status_link.setStyleSheet(link_style)
    self.update_status_link.setCursor(Qt.PointingHandCursor)
    self.update_status_link.setToolTip("Ručně zkontrolovat aktualizace.")
    self.update_status_link.mousePressEvent = lambda event: _footer_update_clicked(self, event)

    for label in (self.log_status_link, self.src_status_label, self.update_status_link):
        label.show()
        label.raise_()


def _footer_window(self):
    try:
        window = self.window()
        if isinstance(window, SifratorWindow):
            return window
    except Exception:
        pass
    return None


def _footer_log_clicked(self, event=None):
    window = _footer_window(self)
    if window is not None and hasattr(window, "show_live_log_window"):
        window.show_live_log_window()


def _footer_update_clicked(self, event=None):
    window = _footer_window(self)
    if window is not None and hasattr(window, "manual_check_updates"):
        window.manual_check_updates()


def _footer_create_widgets(self):
    _FOOTER_ORIGINAL_CREATE_WIDGETS(self)
    _footer_prepare_links(self)
    self.update_status()


def _footer_layout_status(self):
    _footer_prepare_links(self)

    y_rect = self.sr(52, 881, 950, 22)
    x = y_rect.x()
    y = y_rect.y()
    h = y_rect.height()
    max_right = max(x + self.sr(0, 0, 1560, 0).width(), self.width() - self.fs(20))

    font = QFont("Georgia", self.fs(10))
    for label in (self.status, self.log_status_link, self.src_status_label, self.update_status_link):
        label.setFont(font)
        label.setFixedHeight(h)

    fm = self.status.fontMetrics()
    available_total = max(300, max_right - x)
    log_text = self.log_status_link.text()
    src_text = self.src_status_label.text()
    update_text = self.update_status_link.text()
    fixed_w = fm.horizontalAdvance(log_text) + fm.horizontalAdvance(src_text) + fm.horizontalAdvance(update_text) + self.fs(58)
    max_selected_w = max(self.fs(130), available_total - fixed_w)

    selected_text = self.status.property("full_status_text") or self.status.text()
    selected_text = fm.elidedText(str(selected_text), Qt.ElideRight, max_selected_w)
    self.status.setText(selected_text)

    for label in (self.status, self.log_status_link, self.src_status_label, self.update_status_link):
        label.adjustSize()

    gap = self.fs(10)
    for label in (self.status, self.log_status_link, self.src_status_label, self.update_status_link):
        width = min(label.width() + self.fs(4), max(40, max_right - x))
        label.setGeometry(x, y, width, h)
        label.show()
        label.raise_()
        x += width + gap


def _footer_update_status(self):
    _footer_prepare_links(self)
    selected_text = self.selected_cipher if self.selected_cipher else "Žádná"

    window = _footer_window(self)
    logging_enabled = bool(window and hasattr(window, "is_live_logging_enabled") and window.is_live_logging_enabled())
    logging_text = "Zapnuto" if logging_enabled else "Vypnuto"

    self.status.setProperty("full_status_text", f"VYBRANÁ ŠIFRA:  {selected_text}   |")
    self.status.setText(f"VYBRANÁ ŠIFRA:  {selected_text}   |")
    self.log_status_link.setText(f"LOGOVÁNÍ:  {logging_text}   |")
    self.src_status_label.setText("SRC SLOŽKA:  Nalezena   |")
    self.update_status_link.setText("AKTUALIZACE")
    self.log_status_link.setToolTip(
        "Kliknutím otevřeš live logy. Zavřením okna se logování vypne."
        if logging_enabled else
        "Kliknutím zapneš logování a otevřeš live logy."
    )
    _footer_layout_status(self)


def _footer_update_layout_positions(self):
    _FOOTER_ORIGINAL_UPDATE_LAYOUT_POSITIONS(self)
    _footer_layout_status(self)


SifratorSkinWidget.create_widgets = _footer_create_widgets
SifratorSkinWidget.update_status = _footer_update_status
SifratorSkinWidget.update_layout_positions = _footer_update_layout_positions


_AUTOMATIC_ORIGINAL_CHECK_UPDATES = SifratorWindow.check_updates_after_start


def _window_is_live_logging_enabled(self) -> bool:
    return bool(getattr(self, "_live_logging_enabled", False))


def _window_set_live_logging_enabled(self, enabled: bool):
    self._live_logging_enabled = bool(enabled)
    try:
        if hasattr(self, "central"):
            self.central.update_status()
    except Exception:
        pass


def _window_write_live_log(self, message: str):
    _sifrator_debug_log(message)
    try:
        dialog = getattr(self, "_live_log_dialog", None)
        if dialog is not None:
            dialog.refresh_log()
    except Exception:
        pass


def _window_show_live_log_window(self):
    dialog = getattr(self, "_live_log_dialog", None)
    if dialog is not None and dialog.isVisible():
        dialog.raise_()
        dialog.activateWindow()
        return

    self.set_live_logging_enabled(True)
    self._live_log_dialog = LiveLogDialog(self)
    self.write_live_log("Logování bylo zapnuto přes spodní stavový řádek.")
    self._live_log_dialog.show()
    self._live_log_dialog.raise_()
    self._live_log_dialog.activateWindow()


def _window_show_update_offer(self, update_data: dict, manual: bool = False):
    remote_version = update_data.get("version", "")
    notes = update_data.get("notes", "")
    platform_key = update_data.get("platform_key", "")
    file_name = update_data.get("file_name", "")

    message = (
        f"Je dostupná nová verze {remote_version}.\n\n"
        f"Aktuální verze: {APP_VERSION}\n"
        f"Platforma: {platform_key}\n"
        f"Balíček: {file_name}\n\n"
        f"{notes}\n\n"
        "Chceš aplikaci aktualizovat?"
    )

    answer = QMessageBox.question(
        self,
        "Dostupná aktualizace",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes,
    )

    if answer == QMessageBox.Yes:
        try:
            self.write_live_log(f"Uživatel potvrdil aktualizaci na verzi {remote_version}.")
            update_manager.download_and_install_update(update_data)
        except Exception as error:
            self.write_live_log(f"Chyba aktualizace: {type(error).__name__}: {error}")
            QMessageBox.critical(
                self,
                "Chyba aktualizace",
                f"Aktualizaci se nepodařilo dokončit:\n\n{error}",
            )
    else:
        self.write_live_log("Uživatel aktualizaci odmítl.")


def _window_check_updates_common(self, manual: bool = False):
    platform_key = update_manager.get_platform_key() if hasattr(update_manager, "get_platform_key") else "unknown"
    self.write_live_log(
        ("Ruční" if manual else "Automatická") +
        f" kontrola aktualizací: current={APP_VERSION}, platform={platform_key}"
    )

    update_data = update_manager.check_for_update(APP_VERSION)
    if update_data:
        self.write_live_log(
            f"Aktualizace dostupná: version={update_data.get('version')}, "
            f"platform={update_data.get('platform_key')}, file={update_data.get('file_name')}"
        )
        _window_show_update_offer(self, update_data, manual=manual)
        return

    self.write_live_log("Aktualizace není dostupná nebo se nepodařilo načíst update.json.")

    if manual:
        log_path = _sifrator_debug_log_path()
        QMessageBox.information(
            self,
            "Aktualizace",
            "Novější verze nebyla nalezena.\n\n"
            f"Aktuální verze: {APP_VERSION}\n"
            f"Platforma: {platform_key}\n\n"
            f"Diagnostický log:\n{log_path}",
        )


def _window_check_updates_after_start(self):
    _window_check_updates_common(self, manual=False)


def _window_manual_check_updates(self):
    _window_check_updates_common(self, manual=True)


SifratorWindow.is_live_logging_enabled = _window_is_live_logging_enabled
SifratorWindow.set_live_logging_enabled = _window_set_live_logging_enabled
SifratorWindow.write_live_log = _window_write_live_log
SifratorWindow.show_live_log_window = _window_show_live_log_window
SifratorWindow.manual_check_updates = _window_manual_check_updates
SifratorWindow.check_updates_after_start = _window_check_updates_after_start


# ============================================================
# TRVALÁ CACHE KLÍČŮ PODLE VERZE APLIKACE
# ============================================================
# Renderer dostane aktuální APP_VERSION. Pokud se po aktualizaci verze změní,
# pirate_key_renderer.py automaticky smaže starou diskovou cache klíčů.

try:
    _PERSISTENT_CACHE_ORIGINAL_GET_RENDERER = get_pirate_key_renderer

    def get_pirate_key_renderer():
        renderer = _PERSISTENT_CACHE_ORIGINAL_GET_RENDERER()
        try:
            if renderer is not None and hasattr(renderer, "set_persistent_cache_version"):
                renderer.set_persistent_cache_version(APP_VERSION)
        except Exception as error:
            try:
                _sifrator_debug_log(f"Cache klíčů: nastavení verze selhalo: {type(error).__name__}: {error}")
            except Exception:
                pass
        return renderer
except Exception:
    pass


def _clear_persistent_key_cache_from_main() -> bool:
    """Ručně smaže trvalou cache klíčů, pokud ji renderer podporuje."""
    try:
        renderer = get_pirate_key_renderer()
        if renderer is not None and hasattr(renderer, "clear_persistent_key_cache"):
            ok = bool(renderer.clear_persistent_key_cache())
            try:
                _sifrator_debug_log("Cache klíčů byla vyčištěna ručně." if ok else "Cache klíčů se nepodařilo vyčistit.")
            except Exception:
                pass
            return ok
    except Exception as error:
        try:
            _sifrator_debug_log(f"Ruční čištění cache klíčů selhalo: {type(error).__name__}: {error}")
        except Exception:
            pass
    return False


# Do okna LOGOVÁNÍ přidáme tlačítko pro ruční vyčištění cache klíčů.
try:
    _CACHE_DIALOG_ORIGINAL_INIT = LiveLogDialog.__init__

    def _cache_dialog_init(self, owner_window):
        _CACHE_DIALOG_ORIGINAL_INIT(self, owner_window)
        try:
            self.clear_cache_button = QPushButton("Vyčistit cache klíčů", self)
            self.clear_cache_button.setToolTip("Smaže uložené PNG klíče. Při dalším použití se vytvoří znovu.")
            self.clear_cache_button.clicked.connect(self.clear_key_cache)

            # Tlačítko vložíme vedle ostatních tlačítek ve spodním řádku dialogu.
            layout = self.layout()
            if layout is not None:
                row = layout.itemAt(layout.count() - 1)
                if row is not None and row.layout() is not None:
                    row.layout().insertWidget(max(0, row.layout().count() - 1), self.clear_cache_button)
        except Exception:
            pass

    def _cache_dialog_clear_key_cache(self):
        ok = _clear_persistent_key_cache_from_main()
        if ok:
            QMessageBox.information(self, "Cache klíčů", "Cache klíčů byla vyčištěna.")
        else:
            QMessageBox.warning(self, "Cache klíčů", "Cache klíčů se nepodařilo vyčistit.")
        try:
            self.refresh_log()
        except Exception:
            pass

    LiveLogDialog.__init__ = _cache_dialog_init
    LiveLogDialog.clear_key_cache = _cache_dialog_clear_key_cache
except Exception:
    pass

def run_smoke_test() -> int:
    """Rychlý test pro GitHub Actions bez otevření hlavního okna aplikace."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("Smoke test: start")
    print(f"APP_NAME: {APP_NAME}")
    print(f"APP_VERSION: {APP_VERSION}")
    print(f"APP_DIR: {get_app_dir()}")
    print(f"ICONS_DIR: {get_icons_dir()}")

    errors = []

    def check(condition: bool, ok_message: str, error_message: str) -> None:
        if condition:
            print(f"OK: {ok_message}")
        else:
            errors.append(error_message)

    check(os.path.isdir(get_icons_dir()), "icons", "Chybi slozka icons")
    check(os.path.isdir(os.path.join(get_app_dir(), "logika sifer")) or os.path.isdir(os.path.join(get_script_dir(), "logika sifer")), "logika sifer", "Chybi slozka logika sifer")
    check(os.path.exists(get_pirate_key_renderer_file()), "pirate_key_renderer.py", "Chybi pirate_key_renderer.py")

    try:
        renderer = get_pirate_key_renderer()
        check(renderer is not None, "pirate_key_renderer import", "Nepodarilo se nacist pirate_key_renderer.py")
    except Exception as error:
        errors.append(f"Chyba pirate_key_renderer.py: {error}")

    logic_tests = [
        ("Binarni ctverce", get_binary_squares_logic),
        ("Brailovo pismo", get_braille_logic),
        ("Britska vlajka", get_british_flag_logic),
        ("Caesarova sifra", get_caesar_logic),
        ("Ctverec", get_ctverec_logic),
        ("Hebrejsky kriz", get_hebrew_cross_logic),
        ("Maly polsky kriz", get_small_polish_cross_logic),
        ("Mobil", get_mobile_logic),
        ("Moonovo pismo", get_moon_logic),
        ("Morseova abeceda", get_morse_logic),
        ("Morseova abeceda hory", get_morse_hory_logic),
        ("Morseova abeceda pila", get_morse_pila_logic),
        ("Morseova abeceda stromy", get_morse_stromy_logic),
        ("Mriz", get_mriz_logic),
        ("Okno", get_okno_logic),
        ("Pavouci sit", get_pavouci_sit_logic),
        ("Posunkova abeceda", get_posunkova_abeceda_logic),
        ("Pseudo-Cina", get_pseudo_cina_logic),
        ("Semafor", get_semafor_logic),
        ("SuperKrychle", get_superkrychle_logic),
        ("Tancici figurky", get_tancici_figurky_logic),
        ("Tancici figurky II", get_tancici_figurky_ii_logic),
        ("Velky polsky kriz", get_velky_polsky_kriz_logic),
        ("Velky polsky kriz 26", get_velky_polsky_kriz_26_logic),
        ("Vlcacka sifra", get_vlcacka_sifra_logic),
        ("Zamena pismen A=Z", get_zamena_pismen_a_z_logic),
        ("Zamena cisel A01-Z26", get_zamena_cisla_a01_z26_logic),
        ("Zamena cisel A26-Z01", get_zamena_cisla_a26_z01_logic),
        ("Zednarska sifra", get_zednarska_sifra_logic),
        ("Zlomky", get_zlomky_logic),
    ]

    for name, getter in logic_tests:
        try:
            module = getter()
            if module is None:
                errors.append(f"Nepodarilo se nacist logiku: {name}")
            else:
                print(f"OK: {name}")
        except Exception as error:
            errors.append(f"Chyba logiky {name}: {error}")

    if errors:
        print("Smoke test: CHYBA")
        for error in errors:
            print(" -", str(error))
        return 1

    print("Smoke test: OK")
    return 0


if "--smoke-test" in sys.argv:
    sys.exit(run_smoke_test())

if __name__ == "__main__":
    # Musí být před QApplication, jinak si Windows může držet ikonu python.exe.
    set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Šifrátor Mraveniště")
    app.setApplicationDisplayName("Šifrátor Mraveniště")

    window = SifratorWindow()
    window.show()

    sys.exit(app.exec())
