"""
cipher_registry.py – Registr šifer a jejich lazy načítání.

Nahrazuje ~30 trojic get_X_logic_module / X_LOGIC / get_X_logic / get_X_widget_class
z původního main.py jedním slovníkem a dvěma univerzálními funkcemi.

Použití:
    from cipher_registry import get_cipher_logic, get_cipher_widget_class

    logic = get_cipher_logic("Morseova abeceda")
    result = logic.encrypt("SOS")

    widget_cls = get_cipher_widget_class("Mříž")
    widget = widget_cls()
"""

from app_paths import get_cipher_logic_file, get_pirate_key_renderer_file, load_python_module_from_path


# ============================================================
# DEFINICE REGISTRU
# Každý záznam: název šifry → (složka, soubor, module_name, widget_class_name nebo None)
# ============================================================

_CIPHER_REGISTRY: dict[str, tuple[str, str, str, str | None]] = {
    "Binární čtverce":                        ("Binarni_ctverce",                       "binarni_ctverce.py",          "binarni_ctverce_logic",          None),
    "Brailovo písmo":                         ("Brailovo_pismo",                        "brailovo_pismo.py",           "brailovo_pismo_logic",           None),
    "Britská vlajka":                         ("Britska_vlajka",                        "britska_vlajka.py",           "britska_vlajka_logic",           "BritishFlagOutputWidget"),
    "Caesarova šifra":                        ("Caesarova_sifra",                       "caesarova_sifra.py",          "caesarova_sifra_logic",          None),
    "Čtverec":                                ("Ctverec",                               "ctverec.py",                  "ctverec_logic",                  "CtverecOutputWidget"),
    "Hebrejský kříž":                         ("Hebrejsky_kriz",                        "hebrejsky_kriz.py",           "hebrejsky_kriz_logic",           "HebrejskyKrizOutputWidget"),
    "Malý polský kříž":                       ("Maly_polsky_kriz",                      "maly_polsky_kriz.py",         "maly_polsky_kriz_logic",         "MalyPolskyKrizOutputWidget"),
    "Mobil":                                  ("Mobil",                                 "mobil.py",                    "mobil_logic",                    None),
    "Moonovo písmo":                          ("Moonovo_pismo",                         "moonovo_pismo.py",            "moonovo_pismo_logic",            "MoonovoPismoOutputWidget"),
    "Morseova abeceda":                       ("Morseova_abeceda",                      "morseova_abeceda.py",         "morseova_abeceda_logic",         None),
    "Morseova abeceda – hory":                ("Morseova_abeceda_hory",                 "morseova_abeceda_hory.py",    "morseova_abeceda_hory_logic",    "MorseHoryOutputWidget"),
    "Morseova abeceda – pila":                ("Morseova_abeceda_pila",                 "morseova_abeceda_pila.py",    "morseova_abeceda_pila_logic",    "MorsePilaOutputWidget"),
    "Morseova abeceda – stromy":              ("Morseova_abeceda_stromy",               "morseova_abeceda_stromy.py",  "morseova_abeceda_stromy_logic",  "MorseStromyOutputWidget"),
    "Mříž":                                   ("Mriz",                                  "mriz.py",                     "mriz_logic",                     "MrizOutputWidget"),
    "Okno":                                   ("Okno",                                  "okno.py",                     "okno_logic",                     "OknoOutputWidget"),
    "Pavoučí síť":                            ("Pavouci_sit",                           "pavouci_sit.py",              "pavouci_sit_logic",              None),
    "Posunková abeceda":                      ("Posunkova_abeceda",                     "posunkova_abeceda.py",        "posunkova_abeceda_logic",        "PosunkovaAbecedaOutputWidget"),
    "Pseudo-Čína":                            ("Pseudo_Cina",                           "pseudo_cina.py",              "pseudo_cina_logic",              "PseudoCinaOutputWidget"),
    "Semafor":                                ("Semafor",                               "semafor.py",                  "semafor_logic",                  "SemaforOutputWidget"),
    "SuperKrychle":                           ("SuperKrychle",                          "superkrychle.py",             "superkrychle_logic",             "SuperKrychleOutputWidget"),
    "Tančící figurky":                        ("Tancici_figurky",                       "tancici_figurky.py",          "tancici_figurky_logic",          "TanciciFigurkyOutputWidget"),
    "Tančící figurky II":                     ("Tancici_figurky_II",                    "tancici_figurky_2.py",        "tancici_figurky_ii_logic",       "TanciciFigurkyIIOutputWidget"),
    "Velký polský kříž":                      ("Velky_polsky_kriz",                     "velky_polsky_kriz.py",        "velky_polsky_kriz_logic",        "VelkyPolskyKrizOutputWidget"),
    "Velký polský kříž (26 znaků)":          ("Velky_polsky_kriz_26_znaku",            "velky_polsky_kriz_26.py",     "velky_polsky_kriz_26_logic",     "VelkyPolskyKriz26OutputWidget"),
    "Vlčácká šifra":                          ("Vlcacka_sifra",                         "vlcacka_sifra.py",            "vlcacka_sifra_logic",            None),
    "Záměna písmen (A=Z)":                   ("Zamena_pismen_A_Z",                     "zamena_pismen_a_z.py",        "zamena_pismen_a_z_logic",        None),
    "Záměna písmen za čísla (A=01, Z=26)":   ("Zamena_pismen_za_cisla_A01_Z26",        "zamena_cisla_a01_z26.py",     "zamena_cisla_a01_z26_logic",     None),
    "Záměna písmen za čísla (A=26, Z=01)":   ("Zamena_pismen_za_cisla_A26_Z01",        "zamena_cisla_a26_z01.py",     "zamena_cisla_a26_z01_logic",     None),
    "Zednářská šifra":                        ("Zednarska_sifra",                       "zednarska_sifra.py",          "zednarska_sifra_logic",          "ZednarskaSifraOutputWidget"),
    "Zlomky":                                 ("Zlomky",                                "zlomky.py",                   "zlomky_logic",                   None),
}

# Cache: klíč = název šifry, hodnota = načtený modul (nebo None pokud selhalo)
_module_cache: dict[str, object] = {}

# Cache pro pirate key renderer
_pirate_key_renderer = None


# ============================================================
# VEŘEJNÉ API
# ============================================================

def get_cipher_logic(cipher_name: str):
    """Lazy načtení logického modulu šifry podle jejího názvu.

    Výsledek je kešovaný – každý modul se načte nejvýše jednou za běh.
    Vrátí None pokud soubor neexistuje nebo načtení selže.
    """
    if cipher_name not in _CIPHER_REGISTRY:
        print(f"UPOZORNĚNÍ: Šifra '{cipher_name}' není v registru.")
        return None

    if cipher_name in _module_cache:
        return _module_cache[cipher_name]

    folder, filename, module_name, _ = _CIPHER_REGISTRY[cipher_name]
    logic_file = get_cipher_logic_file(folder, filename)
    module = load_python_module_from_path(module_name, logic_file)

    _module_cache[cipher_name] = module
    return module


def get_cipher_widget_class(cipher_name: str):
    """Vrátí třídu výstupního widgetu dané šifry, nebo None pokud nemá widget."""
    if cipher_name not in _CIPHER_REGISTRY:
        return None

    _, _, _, widget_class_name = _CIPHER_REGISTRY[cipher_name]
    if widget_class_name is None:
        return None

    module = get_cipher_logic(cipher_name)
    if module is None:
        return None

    return getattr(module, widget_class_name, None)


def get_pirate_key_renderer():
    """Odloženě načte společný renderer klíčů až při jeho prvním použití."""
    global _pirate_key_renderer

    if _pirate_key_renderer is None:
        _pirate_key_renderer = load_python_module_from_path(
            "pirate_key_renderer_logic",
            get_pirate_key_renderer_file(),
        )

    return _pirate_key_renderer


def list_cipher_names() -> list[str]:
    """Vrátí seznam názvů všech registrovaných šifer."""
    return list(_CIPHER_REGISTRY.keys())
