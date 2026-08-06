"""
skin_widget.py – SifratorSkinWidget: hlavní grafická plocha aplikace.

Obsahuje kompletní UI logiku hlavního okna šifrátoru – levý panel se seznamem
šifer, vstupní pole, výstupní pole, grafické canvasy všech šifer, napojení
na logiku šifrovacích modulů a přizpůsobivé škálování dle velikosti okna.

Závislosti:
    app_paths      – cesty k assetům
    cipher_registry – lazy loading logiky a widget tříd šifer
    ui_widgets     – Colors, CipherItem, CipherButton, TransparentActionButton
"""

import os
import unicodedata

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QTextOption, QPen, QTextBlockFormat, QTextCursor
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
    QComboBox,
    QSpinBox,
    QAbstractSpinBox,
)

try:
    from PIL import Image
except Exception:
    Image = None

from app_paths import (
    get_app_dir,
    get_script_dir,
    get_pyinstaller_bundle_dir,
    get_icons_dir,
    _hash_unicode_component,
)
from cipher_registry import get_cipher_logic, get_cipher_widget_class, get_pirate_key_renderer
from fire_effects import FireFlicker
from ui_widgets import Colors, CipherItem, CipherButton, TransparentActionButton

BASE_W = 1672
BASE_H = 941


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
        self.fire_flicker = FireFlicker(self, ((0.947, 0.842, 1.25),))

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
            CipherItem("Caesarova šifra", "caesarova_sifra.png"),
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
        widget_class = get_cipher_widget_class("Britská vlajka")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Britská vlajka")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_ctverec_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Čtverec z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Čtverec")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Čtverec")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_hebrew_cross_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Hebrejský kříž z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Hebrejský kříž")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Hebrejský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_small_polish_cross_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Malý polský kříž z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Malý polský kříž")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Malý polský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_moon_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Moonovo písmo z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Moonovo písmo")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Moonovo písmo")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_hory_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – hory z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Morseova abeceda – hory")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – hory")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_pila_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – pila z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Morseova abeceda – pila")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – pila")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_morse_stromy_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Morseova abeceda – stromy z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Morseova abeceda – stromy")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Morseova abeceda – stromy")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_mriz_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Mříž z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Mříž")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Mříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_okno_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Okno z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Okno")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Okno")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_posunkova_abeceda_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Posunková abeceda z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Posunková abeceda")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Posunková abeceda")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_pseudo_cina_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Pseudo-Čína z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Pseudo-Čína")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Pseudo-Čína")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_semafor_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Semafor z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Semafor")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Semafor")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_superkrychle_canvas(self):
        """Vytvoří vykreslovací widget pro šifru SuperKrychle z externě načteného modulu."""
        widget_class = get_cipher_widget_class("SuperKrychle")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul SuperKrychle")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_tancici_figurky_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Tančící figurky z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Tančící figurky")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Tančící figurky")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_tancici_figurky_ii_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Tančící figurky II z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Tančící figurky II")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Tančící figurky II")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_velky_polsky_kriz_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Velký polský kříž z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Velký polský kříž")

        if widget_class is not None:
            # Widget se vytváří bez parenta; vlastnictví následně převezme QScrollArea přes setWidget().
            return widget_class()

        fallback = QLabel("Chybí kreslicí modul Velký polský kříž")
        fallback.setStyleSheet("background: transparent; color: #f3d79a;")
        return fallback

    def create_velky_polsky_kriz_26_canvas(self):
        """Vytvoří vykreslovací widget pro šifru Velký polský kříž (26 znaků) z externě načteného modulu."""
        widget_class = get_cipher_widget_class("Velký polský kříž (26 znaků)")

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

        try:
            return get_cipher_logic(self.selected_cipher)
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
        height_type = QTextBlockFormat.ProportionalHeight
        if hasattr(height_type, "value"):
            height_type = height_type.value
        block_format.setLineHeight(float(90 if tight else 100), int(height_type))

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
            caesar_logic = get_cipher_logic("Caesarova šifra")

            if caesar_logic is None:
                return (
                    "Chybí soubor s logikou šifry Caesarova šifra:\n"
                    "logika_sifer/Caesarova_sifra/caesarova_sifra.py"
                )

            return caesar_logic.encrypt(text)

        if self.is_zlomky_selected():
            zlomky_logic = get_cipher_logic("Zlomky")

            if zlomky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Zlomky:\n"
                    "logika_sifer/Zlomky/zlomky.py"
                )

            return zlomky_logic.encrypt(text)

        if self.is_zamena_cisla_a26_z01_selected():
            zamena_cisla_logic = get_cipher_logic("Záměna písmen za čísla (A=26, Z=01)")

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=26, Z=01):\n"
                    "logika_sifer/Zamena_pismen_za_cisla_A26_Z01/zamena_cisla_a26_z01.py"
                )

            return zamena_cisla_logic.encrypt(text)

        if self.is_zamena_cisla_a01_z26_selected():
            zamena_cisla_logic = get_cipher_logic("Záměna písmen za čísla (A=01, Z=26)")

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=01, Z=26):\n"
                    "logika_sifer/Zamena_pismen_za_cisla_A01_Z26/zamena_cisla_a01_z26.py"
                )

            return zamena_cisla_logic.encrypt(text)

        if self.is_zamena_pismen_a_z_selected():
            zamena_pismen_a_z_logic = get_cipher_logic("Záměna písmen (A=Z)")

            if zamena_pismen_a_z_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen (A=Z):\n"
                    "logika_sifer/Zamena_pismen_A_Z/zamena_pismen_a_z.py"
                )

            return zamena_pismen_a_z_logic.encrypt(text)

        if self.is_vlcacka_sifra_selected():
            vlcacka_sifra_logic = get_cipher_logic("Vlčácká šifra")

            if vlcacka_sifra_logic is None:
                return (
                    "Chybí soubor s logikou šifry Vlčácká šifra:\n"
                    "logika_sifer/Vlcacka_sifra/vlcacka_sifra.py"
                )

            return vlcacka_sifra_logic.encrypt(text)

        if self.is_velky_polsky_kriz_26_selected():
            velky_polsky_kriz_26_logic = get_cipher_logic("Velký polský kříž (26 znaků)")

            if velky_polsky_kriz_26_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž (26 znaků):\n"
                    "logika_sifer/Velky_polsky_kriz_26_znaku/velky_polsky_kriz_26.py"
                )

            return velky_polsky_kriz_26_logic.encrypt(text)

        if self.is_velky_polsky_kriz_selected():
            velky_polsky_kriz_logic = get_cipher_logic("Velký polský kříž")

            if velky_polsky_kriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž:\n"
                    "logika_sifer/Velky_polsky_kriz/velky_polsky_kriz.py"
                )

            return velky_polsky_kriz_logic.encrypt(text)

        if self.is_tancici_figurky_ii_selected():
            tancici_figurky_ii_logic = get_cipher_logic("Tančící figurky II")

            if tancici_figurky_ii_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky II:\n"
                    "logika_sifer/Tancici_figurky_II/tancici_figurky_2.py"
                )

            return tancici_figurky_ii_logic.encrypt(text)

        if self.is_tancici_figurky_selected():
            tancici_figurky_logic = get_cipher_logic("Tančící figurky")

            if tancici_figurky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky:\n"
                    "logika_sifer/Tancici_figurky/tancici_figurky.py"
                )

            return tancici_figurky_logic.encrypt(text)

        if self.is_superkrychle_selected():
            superkrychle_logic = get_cipher_logic("SuperKrychle")

            if superkrychle_logic is None:
                return (
                    "Chybí soubor s logikou šifry SuperKrychle:\n"
                    "logika_sifer/SuperKrychle/superkrychle.py"
                )

            return superkrychle_logic.encrypt(text)

        if self.is_semafor_selected():
            semafor_logic = get_cipher_logic("Semafor")

            if semafor_logic is None:
                return (
                    "Chybí soubor s logikou šifry Semafor:\n"
                    "logika_sifer/Semafor/semafor.py"
                )

            return semafor_logic.encrypt(text)

        if self.is_pseudo_cina_selected():
            pseudo_cina_logic = get_cipher_logic("Pseudo-Čína")

            if pseudo_cina_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pseudo-Čína:\n"
                    "logika_sifer/Pseudo_Cina/pseudo_cina.py"
                )

            return pseudo_cina_logic.encrypt(text)

        if self.is_posunkova_abeceda_selected():
            posunkova_abeceda_logic = get_cipher_logic("Posunková abeceda")

            if posunkova_abeceda_logic is None:
                return (
                    "Chybí soubor s logikou šifry Posunková abeceda:\n"
                    "logika_sifer/Posunkova_abeceda/posunkova_abeceda.py"
                )

            return posunkova_abeceda_logic.encrypt(text)

        if self.is_pavouci_sit_selected():
            pavouci_sit_logic = get_cipher_logic("Pavoučí síť")

            if pavouci_sit_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pavoučí síť:\n"
                    "logika_sifer/Pavouci_sit/pavouci_sit.py"
                )

            return pavouci_sit_logic.encrypt(text)

        if self.is_okno_selected():
            okno_logic = get_cipher_logic("Okno")

            if okno_logic is None:
                return (
                    "Chybí soubor s logikou šifry Okno:\n"
                    "logika_sifer/Okno/okno.py"
                )

            return okno_logic.encrypt(text)

        if self.is_mriz_selected():
            mriz_logic = get_cipher_logic("Mříž")

            if mriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mříž:\n"
                    "logika_sifer/Mriz/mriz.py"
                )

            return mriz_logic.encrypt(text)

        if self.is_morse_stromy_selected():
            morse_stromy_logic = get_cipher_logic("Morseova abeceda – stromy")

            if morse_stromy_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – stromy:\n"
                    "logika_sifer/Morseova_abeceda_stromy/morseova_abeceda_stromy.py"
                )

            return morse_stromy_logic.encrypt(text)

        if self.is_morse_pila_selected():
            morse_pila_logic = get_cipher_logic("Morseova abeceda – pila")

            if morse_pila_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – pila:\n"
                    "logika_sifer/Morseova_abeceda_pila/morseova_abeceda_pila.py"
                )

            return morse_pila_logic.encrypt(text)

        if self.is_morse_hory_selected():
            morse_hory_logic = get_cipher_logic("Morseova abeceda – hory")

            if morse_hory_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – hory:\n"
                    "logika_sifer/Morseova_abeceda_hory/morseova_abeceda_hory.py"
                )

            return morse_hory_logic.encrypt(text)

        if self.is_moon_selected():
            moon_logic = get_cipher_logic("Moonovo písmo")

            if moon_logic is None:
                return (
                    "Chybí soubor s logikou šifry Moonovo písmo:\n"
                    "logika_sifer/Moonovo_pismo/moonovo_pismo.py"
                )

            return moon_logic.encrypt(text)

        if self.is_mobile_selected():
            mobile_logic = get_cipher_logic("Mobil")

            if mobile_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mobil:\n"
                    "logika_sifer/Mobil/mobil.py"
                )

            return mobile_logic.encrypt(text)

        if self.is_small_polish_cross_selected():
            small_polish_logic = get_cipher_logic("Malý polský kříž")

            if small_polish_logic is None:
                return (
                    "Chybí soubor s logikou šifry Malý polský kříž:\n"
                    "logika_sifer/Maly_polsky_kriz/maly_polsky_kriz.py"
                )

            return small_polish_logic.encrypt(text)

        if self.is_hebrew_cross_selected():
            hebrew_logic = get_cipher_logic("Hebrejský kříž")

            if hebrew_logic is None:
                return (
                    "Chybí soubor s logikou šifry Hebrejský kříž:\n"
                    "logika_sifer/Hebrejsky_kriz/hebrejsky_kriz.py"
                )

            return hebrew_logic.encrypt(text)

        if self.is_ctverec_selected():
            ctverec_logic = get_cipher_logic("Čtverec")

            if ctverec_logic is None:
                return (
                    "Chybí soubor s logikou šifry Čtverec:\n"
                    "logika_sifer/Ctverec/ctverec.py"
                )

            return ctverec_logic.encrypt(text)

        if self.is_british_flag_selected():
            british_logic = get_cipher_logic("Britská vlajka")

            if british_logic is None:
                return (
                    "Chybí soubor s logikou Britské vlajky:\n"
                    "logika_sifer/Britska_vlajka/britska_vlajka.py"
                )

            return british_logic.encrypt(text)

        if self.is_binary_squares_selected():
            binary_logic = get_cipher_logic("Binární čtverce")

            if binary_logic is None:
                return (
                    "Chybí soubor s logikou Binárních čtverců:\n"
                    "logika_sifer/Binarni_ctverce/binarni_ctverce.py"
                )

            return binary_logic.encrypt(text)

        if self.is_morse_cipher_selected():
            morse_logic = get_cipher_logic("Morseova abeceda")

            if morse_logic is None:
                return (
                    "Chybí soubor s logikou Morseovy abecedy:\n"
                    "logika_sifer/Morseova_abeceda/morseova_abeceda.py"
                )

            return morse_logic.encrypt(text)

        if self.is_braille_selected():
            braille_logic = get_cipher_logic("Brailovo písmo")

            if braille_logic is None:
                return (
                    "Chybí soubor s logikou Braillova písma:\n"
                    "logika_sifer/Brailovo_pismo/brailovo_pismo.py"
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
            caesar_logic = get_cipher_logic("Caesarova šifra")

            if caesar_logic is None:
                return (
                    "Chybí soubor s logikou šifry Caesarova šifra:\n"
                    "logika_sifer/Caesarova_sifra/caesarova_sifra.py"
                )

            return caesar_logic.decrypt(text)

        if self.is_zlomky_selected():
            zlomky_logic = get_cipher_logic("Zlomky")

            if zlomky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Zlomky:\n"
                    "logika_sifer/Zlomky/zlomky.py"
                )

            return zlomky_logic.decrypt(text)

        if self.is_zamena_cisla_a01_z26_selected():
            zamena_cisla_logic = get_cipher_logic("Záměna písmen za čísla (A=01, Z=26)")

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=01, Z=26):\n"
                    "logika_sifer/Zamena_pismen_za_cisla_A01_Z26/zamena_cisla_a01_z26.py"
                )

            return zamena_cisla_logic.decrypt(text)

        if self.is_zamena_cisla_a26_z01_selected():
            zamena_cisla_logic = get_cipher_logic("Záměna písmen za čísla (A=26, Z=01)")

            if zamena_cisla_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen za čísla (A=26, Z=01):\n"
                    "logika_sifer/Zamena_pismen_za_cisla_A26_Z01/zamena_cisla_a26_z01.py"
                )

            return zamena_cisla_logic.decrypt(text)

        if self.is_zamena_pismen_a_z_selected():
            zamena_pismen_a_z_logic = get_cipher_logic("Záměna písmen (A=Z)")

            if zamena_pismen_a_z_logic is None:
                return (
                    "Chybí soubor s logikou šifry Záměna písmen (A=Z):\n"
                    "logika_sifer/Zamena_pismen_A_Z/zamena_pismen_a_z.py"
                )

            return zamena_pismen_a_z_logic.decrypt(text)

        if self.is_vlcacka_sifra_selected():
            vlcacka_sifra_logic = get_cipher_logic("Vlčácká šifra")

            if vlcacka_sifra_logic is None:
                return (
                    "Chybí soubor s logikou šifry Vlčácká šifra:\n"
                    "logika_sifer/Vlcacka_sifra/vlcacka_sifra.py"
                )

            return vlcacka_sifra_logic.decrypt(text)

        if self.is_velky_polsky_kriz_26_selected():
            velky_polsky_kriz_26_logic = get_cipher_logic("Velký polský kříž (26 znaků)")

            if velky_polsky_kriz_26_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž (26 znaků):\n"
                    "logika_sifer/Velky_polsky_kriz_26_znaku/velky_polsky_kriz_26.py"
                )

            return velky_polsky_kriz_26_logic.decrypt(text)

        if self.is_velky_polsky_kriz_selected():
            velky_polsky_kriz_logic = get_cipher_logic("Velký polský kříž")

            if velky_polsky_kriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Velký polský kříž:\n"
                    "logika_sifer/Velky_polsky_kriz/velky_polsky_kriz.py"
                )

            return velky_polsky_kriz_logic.decrypt(text)

        if self.is_tancici_figurky_ii_selected():
            tancici_figurky_ii_logic = get_cipher_logic("Tančící figurky II")

            if tancici_figurky_ii_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky II:\n"
                    "logika_sifer/Tancici_figurky_II/tancici_figurky_2.py"
                )

            return tancici_figurky_ii_logic.decrypt(text)

        if self.is_tancici_figurky_selected():
            tancici_figurky_logic = get_cipher_logic("Tančící figurky")

            if tancici_figurky_logic is None:
                return (
                    "Chybí soubor s logikou šifry Tančící figurky:\n"
                    "logika_sifer/Tancici_figurky/tancici_figurky.py"
                )

            return tancici_figurky_logic.decrypt(text)

        if self.is_superkrychle_selected():
            superkrychle_logic = get_cipher_logic("SuperKrychle")

            if superkrychle_logic is None:
                return (
                    "Chybí soubor s logikou šifry SuperKrychle:\n"
                    "logika_sifer/SuperKrychle/superkrychle.py"
                )

            return superkrychle_logic.decrypt(text)

        if self.is_semafor_selected():
            semafor_logic = get_cipher_logic("Semafor")

            if semafor_logic is None:
                return (
                    "Chybí soubor s logikou šifry Semafor:\n"
                    "logika_sifer/Semafor/semafor.py"
                )

            return semafor_logic.decrypt(text)

        if self.is_pseudo_cina_selected():
            pseudo_cina_logic = get_cipher_logic("Pseudo-Čína")

            if pseudo_cina_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pseudo-Čína:\n"
                    "logika_sifer/Pseudo_Cina/pseudo_cina.py"
                )

            return pseudo_cina_logic.decrypt(text)

        if self.is_posunkova_abeceda_selected():
            posunkova_abeceda_logic = get_cipher_logic("Posunková abeceda")

            if posunkova_abeceda_logic is None:
                return (
                    "Chybí soubor s logikou šifry Posunková abeceda:\n"
                    "logika_sifer/Posunkova_abeceda/posunkova_abeceda.py"
                )

            return posunkova_abeceda_logic.decrypt(text)

        if self.is_pavouci_sit_selected():
            pavouci_sit_logic = get_cipher_logic("Pavoučí síť")

            if pavouci_sit_logic is None:
                return (
                    "Chybí soubor s logikou šifry Pavoučí síť:\n"
                    "logika_sifer/Pavouci_sit/pavouci_sit.py"
                )

            return pavouci_sit_logic.decrypt(text)

        if self.is_okno_selected():
            okno_logic = get_cipher_logic("Okno")

            if okno_logic is None:
                return (
                    "Chybí soubor s logikou šifry Okno:\n"
                    "logika_sifer/Okno/okno.py"
                )

            return okno_logic.decrypt(text)

        if self.is_mriz_selected():
            mriz_logic = get_cipher_logic("Mříž")

            if mriz_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mříž:\n"
                    "logika_sifer/Mriz/mriz.py"
                )

            return mriz_logic.decrypt(text)

        if self.is_morse_stromy_selected():
            morse_stromy_logic = get_cipher_logic("Morseova abeceda – stromy")

            if morse_stromy_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – stromy:\n"
                    "logika_sifer/Morseova_abeceda_stromy/morseova_abeceda_stromy.py"
                )

            return morse_stromy_logic.decrypt(text)

        if self.is_morse_pila_selected():
            morse_pila_logic = get_cipher_logic("Morseova abeceda – pila")

            if morse_pila_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – pila:\n"
                    "logika_sifer/Morseova_abeceda_pila/morseova_abeceda_pila.py"
                )

            return morse_pila_logic.decrypt(text)

        if self.is_morse_hory_selected():
            morse_hory_logic = get_cipher_logic("Morseova abeceda – hory")

            if morse_hory_logic is None:
                return (
                    "Chybí soubor s logikou šifry Morseova abeceda – hory:\n"
                    "logika_sifer/Morseova_abeceda_hory/morseova_abeceda_hory.py"
                )

            return morse_hory_logic.decrypt(text)

        if self.is_moon_selected():
            moon_logic = get_cipher_logic("Moonovo písmo")

            if moon_logic is None:
                return (
                    "Chybí soubor s logikou šifry Moonovo písmo:\n"
                    "logika_sifer/Moonovo_pismo/moonovo_pismo.py"
                )

            return moon_logic.decrypt(text)

        if self.is_mobile_selected():
            mobile_logic = get_cipher_logic("Mobil")

            if mobile_logic is None:
                return (
                    "Chybí soubor s logikou šifry Mobil:\n"
                    "logika_sifer/Mobil/mobil.py"
                )

            return mobile_logic.decrypt(text)

        if self.is_small_polish_cross_selected():
            small_polish_logic = get_cipher_logic("Malý polský kříž")

            if small_polish_logic is None:
                return (
                    "Chybí soubor s logikou šifry Malý polský kříž:\n"
                    "logika_sifer/Maly_polsky_kriz/maly_polsky_kriz.py"
                )

            return small_polish_logic.decrypt(text)

        if self.is_hebrew_cross_selected():
            hebrew_logic = get_cipher_logic("Hebrejský kříž")

            if hebrew_logic is None:
                return (
                    "Chybí soubor s logikou šifry Hebrejský kříž:\n"
                    "logika_sifer/Hebrejsky_kriz/hebrejsky_kriz.py"
                )

            return hebrew_logic.decrypt(text)

        if self.is_ctverec_selected():
            ctverec_logic = get_cipher_logic("Čtverec")

            if ctverec_logic is None:
                return (
                    "Chybí soubor s logikou šifry Čtverec:\n"
                    "logika_sifer/Ctverec/ctverec.py"
                )

            return ctverec_logic.decrypt(text)

        if self.is_british_flag_selected():
            british_logic = get_cipher_logic("Britská vlajka")

            if british_logic is None:
                return (
                    "Chybí soubor s logikou Britské vlajky:\n"
                    "logika_sifer/Britska_vlajka/britska_vlajka.py"
                )

            return british_logic.decrypt(text)

        if self.is_binary_squares_selected():
            binary_logic = get_cipher_logic("Binární čtverce")

            if binary_logic is None:
                return (
                    "Chybí soubor s logikou Binárních čtverců:\n"
                    "logika_sifer/Binarni_ctverce/binarni_ctverce.py"
                )

            return binary_logic.decrypt(text)

        if self.is_morse_cipher_selected():
            morse_logic = get_cipher_logic("Morseova abeceda")

            if morse_logic is None:
                return (
                    "Chybí soubor s logikou Morseovy abecedy:\n"
                    "logika_sifer/Morseova_abeceda/morseova_abeceda.py"
                )

            return morse_logic.decrypt(text)

        if self.is_braille_selected():
            braille_logic = get_cipher_logic("Brailovo písmo")

            if braille_logic is None:
                return (
                    "Chybí soubor s logikou Braillova písma:\n"
                    "logika_sifer/Brailovo_pismo/brailovo_pismo.py"
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
            self.fire_flicker.paint(painter, scaled.width(), scaled.height())
        else:
            painter.fillRect(self.rect(), QColor("#06131b"))




# ============================================================
# ROZŠÍŘENÍ: Zednářská šifra
# Tato část je oddělená jako samostatná integrace, aby nebylo nutné
# neúměrně rozšiřovat původní metody hlavního widgetu.
# ============================================================

def get_zednarska_sifra_logic_module():
    """Načte modul logiky šifry z cesty: logika_sifer/Zednarska_sifra/zednarska_sifra.py"""
    return get_cipher_logic("Zednářská šifra")


ZEDNARSKA_SIFRA_LOGIC = None


def get_zednarska_sifra_logic():
    """Odloženě načte logiku a vykreslovacího widgetu šifry Zednářská šifra až při prvním použití."""
    global ZEDNARSKA_SIFRA_LOGIC

    if ZEDNARSKA_SIFRA_LOGIC is None:
        ZEDNARSKA_SIFRA_LOGIC = get_zednarska_sifra_logic_module()

    return ZEDNARSKA_SIFRA_LOGIC


def get_zednarska_sifra_widget_class():
    """Vrátí třídu ZednarskaSifraOutputWidget načtenou z externího modulu zednarska_sifra.py."""
    return get_cipher_widget_class("Zednářská šifra")


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
                "logika_sifer/Zednarska_sifra/zednarska_sifra.py"
            )

        return zednarska_sifra_logic.encrypt(text)

    return _ORIGINAL_ENCRYPT_SELECTED_CIPHER(self, text)


def _PATCHED_DECRYPT_SELECTED_CIPHER(self, text: str) -> str:
    if self.is_zednarska_sifra_selected():
        zednarska_sifra_logic = get_zednarska_sifra_logic()

        if zednarska_sifra_logic is None:
            return (
                "Chybí soubor s logikou šifry Zednářská šifra:\n"
                "logika_sifer/Zednarska_sifra/zednarska_sifra.py"
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
