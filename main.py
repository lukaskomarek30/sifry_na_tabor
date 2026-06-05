APP_VERSION = "0.0.1"
APP_NAME = "Sifrator_Mraveniste"

import os
import sys
import ctypes
import unicodedata
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap, QTextOption, QPen
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
)

try:
    from PIL import Image
except Exception:
    Image = None

import update_manager


# ============================================================
# ŠIFRÁTOR MRAVENIŠTĚ – UI skin přes icons/BG.png
#
# Očekávaná struktura:
#
# C:\Users\komarek\Desktop\Šifry\
# ├── main.py
# └── icons\
#     ├── BG.png                    <- čistý UI skin / pozadí
#     ├── logo.png
#     ├── binarni_ctverce.png
#     ├── brailovo_pismo.png
#     ├── ...
#     ├── lock_closed.png
#     └── lock_open.png
#
# DŮLEŽITÉ:
# Tato verze už nekreslí modré rámečky přes QPainter.
# Bere čisté BG.png jako hotový grafický skin a přes něj
# pokládá jen funkční prvky: logo, seznam šifer, textová pole,
# tlačítka a status.
# ============================================================


BASE_W = 1672
BASE_H = 941



def get_app_dir():
    """Vrátí složku aplikace.

    Při spuštění z Pythonu:
        složka, kde leží main.py

    Při spuštění z EXE:
        složka, kde leží Sifrator_Mraveniste.exe

    Díky tomu hotová aplikace hledá složku icons vedle EXE.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(os.path.abspath(__file__))


def get_script_dir():
    """Vrátí složku skriptu main.py."""
    return os.path.dirname(os.path.abspath(__file__))


def get_pyinstaller_bundle_dir():
    """Vrátí dočasnou složku PyInstalleru, pokud aplikace běží jako EXE."""
    return getattr(sys, "_MEIPASS", "")


def get_icons_dir():
    """Najde složku icons.

    Hledá:
    1) vedle EXE / main.py
    2) vedle skriptu
    3) uvnitř PyInstaller balíčku, pokud by se icons někdy přibalily přes --add-data

    Pro automatické aktualizace je nejlepší varianta:
        Sifrator_Mraveniste.exe
        icons/
    """
    candidates = [
        os.path.join(get_app_dir(), "icons"),
        os.path.join(get_script_dir(), "icons"),
    ]

    bundle_dir = get_pyinstaller_bundle_dir()
    if bundle_dir:
        candidates.append(os.path.join(bundle_dir, "icons"))

    for path in candidates:
        if path and os.path.isdir(path):
            return path

    return os.path.join(get_app_dir(), "icons")


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
    """Klikací oblast nad grafickým tlačítkem ve skinu.

    Text a zámek se kreslí ručně, aby byly vždy přesně uprostřed tlačítka.
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

        # Jemný hover efekt, aby zůstal vidět grafický skin tlačítka.
        if self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 120, 28))
            painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 10, 10)

        painter.setFont(self.font())
        fm = painter.fontMetrics()

        # Větší zámek než předtím.
        icon_size = max(46, min(74, int(self.height() * 0.88)))
        gap = max(14, int(self.width() * 0.040))
        text_w = fm.horizontalAdvance(self.full_text)

        center_y = self.height() // 2
        vertical_shift = max(2, int(self.height() * 0.04))

        # Text bude mít střed přesně ve středu tlačítka.
        # Malý svislý posun dolů pomůže, aby opticky seděl přesněji do středu dekorativního tlačítka.
        text_x = int((self.width() - text_w) / 2)
        icon_x = int(text_x - gap - icon_size)

        # Kdyby bylo tlačítko při zmenšeném okně moc úzké, poskládáme ikonu+text jako skupinu.
        if icon_x < 8:
            total_w = icon_size + gap + text_w
            group_x = int((self.width() - total_w) / 2)
            icon_x = group_x
            text_x = group_x + icon_size + gap

        # Zvětšená ikona zámku.
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

        # DŮLEŽITÉ PRO EXE A AKTUALIZACE:
        # assets_path je složka aplikace a icons_path je složka icons vedle EXE.
        self.assets_path = get_app_dir()
        self.icons_path = get_icons_dir()

        # Čisté BG je přímo ve složce icons/BG.png.
        self.skin_path = self.find_asset(["BG.png", "bg.png"])
        self.logo_path = self.find_asset(["logo.png", "Logo.png"])

        self.skin_pixmap = QPixmap(self.skin_path) if self.skin_path else QPixmap()
        self.logo_pixmap = self.load_logo_pixmap(self.logo_path) if self.logo_path else QPixmap()

        self.ciphers = self.build_cipher_list()
        self.selected_cipher = "Morseova abeceda – hory"
        self.result_mode = None
        self.cipher_buttons = []

        self.setMinimumSize(1200, 675)
        self.create_widgets()
        self.print_missing_assets()
        self.update_layout_positions()

    # ------------------------------------------------------------
    # Souřadnice a assety
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
        candidates = [
            os.path.join(self.icons_path, file_name),
            os.path.join(get_app_dir(), "icons", file_name),
            os.path.join(get_script_dir(), "icons", file_name),
        ]

        bundle_dir = get_pyinstaller_bundle_dir()
        if bundle_dir:
            candidates.append(os.path.join(bundle_dir, "icons", file_name))

        for path in candidates:
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
    # Data šifer
    # ------------------------------------------------------------

    def build_cipher_list(self):
        return [
            CipherItem("Binární čtverce", "binarni_ctverce.png"),
            CipherItem("Brailovo písmo", "brailovo_pismo.png"),
            CipherItem("Britská vlajka", "britska_vlajka.png"),
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

    def selected_icon_file(self):
        for item in self.ciphers:
            if item.name == self.selected_cipher:
                return item.icon
        return ""

    # ------------------------------------------------------------
    # UI
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

        self.encrypt_button = TransparentActionButton("ZAŠIFROVAT", self.icon_path("lock_closed.png"), self)
        self.decrypt_button = TransparentActionButton("DEŠIFROVAT", self.icon_path("lock_open.png"), self)
        self.encrypt_button.clicked.connect(self.encrypt_action)
        self.decrypt_button.clicked.connect(self.decrypt_action)

        self.result_title = QLabel("VÝSLEDEK", self)
        self.result_title.setStyleSheet(f"color: {Colors.GOLD_LIGHT}; background: transparent;")

        self.output_text = QTextEdit(self)
        self.output_text.setPlaceholderText("Zašifrovaný text se objeví zde...")

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

    def update_layout_positions(self):
        # Logo – menší a přesně vycentrované do horního kruhu v BG.png.
        # Původně bylo moc nízko/velké a zasahovalo do textů vpravo.
        self.logo_label.setGeometry(self.sr(740, 38, 195, 190))
        if not self.logo_pixmap.isNull():
            pix = self.logo_pixmap.scaled(
                self.logo_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.logo_label.setPixmap(pix)
        self.logo_label.raise_()

        # Levá část
        self.title_left.setGeometry(self.sr(120, 94, 520, 42))
        self.search_edit.setGeometry(self.sr(98, 145, 565, 42))
        self.search_icon.setGeometry(self.sr(606, 145, 48, 42))
        self.scroll_area.setGeometry(self.sr(86, 210, 615, 610))

        # Pravá horní část
        self.selected_title.setGeometry(self.sr(965, 77, 622, 58))
        self.selected_icon.setGeometry(self.sr(1518, 76, 70, 70))

        # Vstupní část – nadpis je ve středovém horním rámečku nad vstupem.
        # Posunutý trochu níž a více doprava, aby nelezl pod kruhové logo.
        self.input_label.setGeometry(self.sr(1015, 182, 500, 34))
        self.input_text.setGeometry(self.sr(728, 265, 822, 126))

        self.encrypt_button.setGeometry(self.sr(728, 399, 405, 79))
        self.decrypt_button.setGeometry(self.sr(1168, 399, 438, 79))

        # Výsledek – nadpis je nad textovým polem, ne uvnitř něj.
        self.result_title.setGeometry(self.sr(770, 540, 420, 34))
        self.output_text.setGeometry(self.sr(735, 585, 855, 232))

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
        self.encrypt_button.setFont(QFont("Georgia", self.fs(19), QFont.Bold))
        self.decrypt_button.setFont(QFont("Georgia", self.fs(19), QFont.Bold))
        self.result_title.setFont(QFont("Georgia", self.fs(18), QFont.Bold))
        self.status.setFont(QFont("Georgia", self.fs(10)))

        # Ikony zámků kreslí TransparentActionButton ručně podle výšky tlačítka.
        # Tady necháváme jen font textu; samotná ikona je zvětšená v paintEvent().
        self.update_text_editor_margins()

    def update_text_editor_margins(self):
        """Využije co největší část rámečku, ale nechá vpravo rezervu na brko."""
        left = max(8, self.fs(14))
        top = max(6, self.fs(10))
        bottom = max(6, self.fs(10))
        # Rezerva na kalamář s perem vpravo
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
    # Logika
    # ------------------------------------------------------------

    def normalize_search_text(self, text):
        """Vyhledávání bez rozlišování diakritiky a velikosti písmen."""
        text = text.strip().lower()
        text = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in text if not unicodedata.combining(ch))

    def filter_ciphers(self, query):
        """Vyfiltruje šifry a znovu je naskládá kompaktně od prvního řádku."""
        normalized_query = self.normalize_search_text(query)

        # Nejdřív vyčistit layout. Widgety se nemažou, jen se vyndají z pozic.
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

        # Přidat výsledky znovu od začátku: 2 sloupce, řádek 0, 1, 2...
        for index, btn in enumerate(visible_buttons):
            row = index // 2
            col = index % 2
            self.grid.addWidget(btn, row, col, alignment=Qt.AlignTop)

        # Skryté widgety nesmí zabírat místo.
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

    def refresh_cipher_styles(self):
        for btn in self.cipher_buttons:
            btn.set_selected(btn.item.name == self.selected_cipher)

    def update_selected_header(self):
        text = f"ŠIFRA – {self.selected_cipher.upper()}"

        # Rezerva pro ikonku vpravo.
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

    def update_status(self):
        self.status.setText(
            f"VYBRANÁ ŠIFRA:  {self.selected_cipher}   |   LOGOVÁNÍ:  Vypnuto   |   SRC SLOŽKA:  Nalezena"
        )

    def update_result_title(self, mode=None):
        if mode is not None:
            self.result_mode = mode

        if self.result_mode == "encrypt":
            self.result_title.setText("VÝSLEDEK ŠIFROVÁNÍ")
        elif self.result_mode == "decrypt":
            self.result_title.setText("VÝSLEDEK DEŠIFROVÁNÍ")
        else:
            self.result_title.setText("VÝSLEDEK")

    def get_input_text(self):
        return self.input_text.toPlainText().strip()

    def encrypt_action(self):
        self.update_result_title("encrypt")

        text = self.get_input_text()
        if not text:
            self.output_text.setPlainText("Nejdřív zadej text k zašifrování.")
            return

        self.output_text.setPlainText(
            f"Zašifrovaný text:\n{text}"
        )

    def decrypt_action(self):
        self.update_result_title("decrypt")

        text = self.get_input_text()
        if not text:
            self.output_text.setPlainText("Nejdřív zadej text k dešifrování.")
            return

        self.output_text.setPlainText(
            f"Dešifrovaný text:\n{text}"
        )

    # ------------------------------------------------------------
    # Události
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



def set_windows_app_id():
    """Nastaví vlastní AppUserModelID, aby Windows nepoužil ikonu python.exe."""
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
        self.resize(BASE_W, BASE_H)
        self.setMinimumSize(1200, 675)

        self.central = SifratorSkinWidget()
        self.setCentralWidget(self.central)

        # Ikona celé aplikace z icons/logo.png / icons/app_icon.ico.
        app_icon_path = make_app_icon_from_logo(self.central.icons_path)
        if app_icon_path and os.path.exists(app_icon_path):
            app_icon = QIcon(app_icon_path)
            self.setWindowIcon(app_icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(app_icon)

        # Kontrola aktualizací až po zobrazení okna.
        # Když není internet nebo není novější verze, nic nevyskočí.
        QTimer.singleShot(1500, self.check_updates_after_start)

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


if __name__ == "__main__":
    # Musí být před QApplication, jinak si Windows může držet ikonu python.exe.
    set_windows_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("Šifrátor Mraveniště")
    app.setApplicationDisplayName("Šifrátor Mraveniště")

    window = SifratorWindow()
    window.show()

    sys.exit(app.exec())
