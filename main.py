import os
import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QRectF, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QPen,
    QBrush,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QGridLayout,
)

try:
    from PIL import Image
except Exception:
    Image = None


@dataclass
class Rects:
    board: QRect
    header_left: QRect
    header_right: QRect
    logo: QRect
    left_title: QRect
    right_title: QRect
    left_body: QRect
    right_body: QRect


class Colors:
    GOLD = "#cfa55e"
    GOLD_LIGHT = "#f1d79b"
    GOLD_TEXT = "#efbf67"
    GOLD_DARK = "#6b431a"
    BLUE_MAIN = "#0d2a43"
    BLUE_HEADER = "#153d5f"
    BLUE_ITEM = "#1c4c74"
    BLUE_ITEM_HOVER = "#255d8d"
    BLUE_BORDER = "#34617f"
    DARK_BOX = "#03111c"
    TEXT_LIGHT = "#f4f4f4"
    PLACEHOLDER = "#9fb0be"
    STATUS = "#143b5b"
    BUTTON_TEXT = "#3a220d"


class LogoOverlay(QWidget):
    """Vrstva s logem. Je transparentní a kreslí pouze pixmapu loga."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")

    def set_pixmap(self, pixmap: QPixmap):
        self.pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self.pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        target = QRectF(0, 0, self.width(), self.height())
        scaled = self.pixmap.scaled(
            self.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


class GoldButton(QPushButton):
    """Vlastní zlaté tlačítko podobnější grafickému návrhu."""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(58)
        self.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.setStyleSheet("background: transparent; border: none;")
        self._hovered = False

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

        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        radius = 20

        grad = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
        if self._hovered:
            grad.setColorAt(0, QColor("#f0cf86"))
            grad.setColorAt(1, QColor("#d0a151"))
        else:
            grad.setColorAt(0, QColor("#e7c373"))
            grad.setColorAt(1, QColor("#cfa55e"))

        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        painter.fillPath(path, QBrush(grad))

        painter.setPen(QPen(QColor(Colors.GOLD_LIGHT), 2))
        painter.drawRoundedRect(r, radius, radius)

        # Vnitřní linka
        inner = r.adjusted(6, 6, -6, -6)
        painter.setPen(QPen(QColor("#9a6b30"), 1))
        painter.drawLine(int(inner.left() + 45), int(inner.bottom() - 2), int(inner.right() - 20), int(inner.bottom() - 2))

        # Malé boční šipky jako v návrhu
        painter.setPen(QPen(QColor("#9a6b30"), 2))
        painter.drawText(QRectF(8, 0, 18, self.height()), Qt.AlignCenter, "‹")
        painter.drawText(QRectF(self.width() - 25, 0, 18, self.height()), Qt.AlignCenter, "›")

        painter.setPen(QPen(QColor(Colors.BUTTON_TEXT)))
        painter.setFont(self.font())
        painter.drawText(r, Qt.AlignCenter, self.text())


class CipherButton(QPushButton):
    def __init__(self, text, name, parent=None):
        super().__init__(text, parent)
        self.cipher_name = name
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setFont(QFont("Segoe UI", 12))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.refresh_style()

    def set_selected(self, selected: bool):
        self.selected = selected
        self.refresh_style()

    def refresh_style(self):
        if self.selected:
            border = Colors.GOLD
            bg = "#35536d"
            width = 2
        else:
            border = "#4b7692"
            bg = Colors.BLUE_ITEM
            width = 1

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {Colors.TEXT_LIGHT};
                border: {width}px solid {border};
                border-radius: 8px;
                padding-left: 12px;
                padding-right: 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {Colors.BLUE_ITEM_HOVER};
            }}
        """)


class PirateCentralWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.assets_path = os.path.dirname(os.path.abspath(__file__))
        self.bg_path = self.find_asset(["BG.png", "bg.png", "background.png"])
        self.logo_path = self.find_asset(["logo.png", "logo(1).png", "logo_cropped.png"])

        self.bg_pixmap = QPixmap(self.bg_path) if self.bg_path else QPixmap()
        self.logo_pixmap = self.load_logo_pixmap(self.logo_path) if self.logo_path else QPixmap()

        self.selected_cipher = "Morseova abeceda"
        self.cipher_buttons = []
        self.rects = None

        self.setMinimumSize(1200, 700)
        self.setAutoFillBackground(False)

        self.create_widgets()
        self.update_layout_positions()

    def find_asset(self, names):
        for name in names:
            path = os.path.join(self.assets_path, name)
            if os.path.exists(path):
                return path
        return None

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

    def create_widgets(self):
        # Horní panely
        self.header_left = QFrame(self)
        self.header_right = QFrame(self)
        for frame in (self.header_left, self.header_right):
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.BLUE_HEADER};
                    border-radius: 14px;
                }}
            """)

        self.sun_icon = QLabel("☼", self.header_left)
        self.sun_icon.setFont(QFont("Segoe UI Symbol", 30))
        self.sun_icon.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")
        self.sun_icon.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.anchor_top = QLabel("⚓", self.header_right)
        self.anchor_top.setFont(QFont("Segoe UI Symbol", 31))
        self.anchor_top.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")
        self.anchor_top.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Titulkové pásy
        self.left_title_frame = QFrame(self)
        self.right_title_frame = QFrame(self)
        for frame in (self.left_title_frame, self.right_title_frame):
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.BLUE_HEADER};
                    border: 1px solid {Colors.BLUE_BORDER};
                    border-radius: 14px;
                }}
            """)

        self.left_title = QLabel("VYBER SI ŠIFRU (28)", self.left_title_frame)
        self.right_title = QLabel("TEXT K ZAŠIFROVÁNÍ", self.right_title_frame)
        for label in (self.left_title, self.right_title):
            label.setFont(QFont("Segoe UI", 18, QFont.Bold))
            label.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.right_title_anchor = QLabel("⚓", self.right_title_frame)
        self.right_title_anchor.setFont(QFont("Segoe UI Symbol", 20))
        self.right_title_anchor.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")
        self.right_title_anchor.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Levý panel se šiframi
        self.left_body = QFrame(self)
        self.left_body.setStyleSheet(f"""
            QFrame {{
                background-color: #092137;
                border: 1px solid {Colors.BLUE_BORDER};
                border-radius: 14px;
            }}
        """)

        self.scroll_area = QScrollArea(self.left_body)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: #092137;
                border: none;
            }}
            QScrollBar:vertical {{
                background: #0a2034;
                width: 10px;
                margin: 4px 0px 4px 0px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #6d7d86;
                min-height: 45px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #092137;")
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.scroll_area.setWidget(self.scroll_content)

        ciphers = [
            ("⚙  Šifrátor 3.0", "Šifrátor 3.0"),
            ("0110\n0011  Binární čtverce", "Binární čtverce"),
            ("⠿  Braillovo písmo", "Braillovo písmo"),
            ("🇬🇧  Britská vlajka", "Britská vlajka"),
            ("▦  Hebrejský kříž", "Hebrejský kříž"),
            ("✚  Malý polský kříž", "Malý polský kříž"),
            ("📱  Mobil", "Mobil"),
            ("☾  Mobiž", "Mobiž"),
            ("☽  Moonovo písmo", "Moonovo písmo"),
            ("⋯−  Morseova abeceda", "Morseova abeceda"),
            ("⛰  Morseova abeceda – hory", "Morseova abeceda – hory"),
            ("🕺  Tančící figurky I/II", "Tančící figurky I/II"),
            ("🕺  Tančící figurky II", "Tančící figurky II"),
            ("△  Zednářská šifra", "Zednářská šifra"),
            ("A↔Z  Záměna písmen (A=Z)", "Záměna písmen (A=Z)"),
            ("A=B\nA=Z  Záměna písmen za čísla", "Záměna písmen za čísla"),
            ("A→B\nA=Z  Záměna písmen za čísla", "Záměna písmen za čísla 2"),
            ("♯  Zlomky", "Zlomky"),
            ("▣  Mobilová šifra", "Mobilová šifra"),
            ("✦  Souřadnice", "Souřadnice"),
        ]

        for index, (text, name) in enumerate(ciphers):
            btn = CipherButton(text, name, self.scroll_content)
            btn.clicked.connect(lambda checked=False, n=name: self.select_cipher(n))
            self.grid.addWidget(btn, index // 2, index % 2)
            self.cipher_buttons.append(btn)

        # Pravá část
        self.input_text = QTextEdit(self)
        self.input_text.setPlaceholderText("Zadej tajnou zprávu...")
        self.input_text.setFont(QFont("Segoe UI", 14))
        self.input_text.setStyleSheet(self.text_edit_style())

        self.encrypt_button = GoldButton("🔒  ZAŠIFROVAT", self)
        self.decrypt_button = GoldButton("🔓  DEŠIFROVAT", self)
        self.encrypt_button.clicked.connect(self.encrypt_action)
        self.decrypt_button.clicked.connect(self.decrypt_action)

        self.result_title = QLabel("VÝSLEDEK", self)
        self.result_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.result_title.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")

        self.output_text = QTextEdit(self)
        self.output_text.setPlaceholderText("Zašifrovaný text se objeví zde...")
        self.output_text.setFont(QFont("Segoe UI", 14))
        self.output_text.setStyleSheet(self.text_edit_style())
        self.output_text.setPlainText("Zašifrovaný text se objeví zde...")

        self.output_star = QLabel("✦", self)
        self.output_star.setFont(QFont("Segoe UI Symbol", 46))
        self.output_star.setStyleSheet("color: rgba(190, 210, 230, 170); background: transparent;")
        self.output_star.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # Spodní status
        self.status = QLabel(self)
        self.status.setFont(QFont("Segoe UI", 10))
        self.status.setStyleSheet(f"background-color: {Colors.STATUS}; color: #f0f0f0; padding-left: 4px;")
        self.status.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        # Logo jako opravdová překryvná vrstva
        self.logo_overlay = LogoOverlay(self)
        self.logo_overlay.set_pixmap(self.logo_pixmap)

        self.refresh_cipher_styles()
        self.update_status()

    def text_edit_style(self):
        return f"""
            QTextEdit {{
                background-color: {Colors.DARK_BOX};
                color: {Colors.TEXT_LIGHT};
                border: 1px solid {Colors.BLUE_BORDER};
                border-radius: 10px;
                padding: 12px;
                selection-background-color: {Colors.GOLD};
                selection-color: #111111;
            }}
        """

    def compute_rects(self) -> Rects:
        w = self.width()
        h = self.height()

        status_h = 24
        board_x = max(20, int(w * 0.016))
        board_y = 28
        board_w = w - board_x * 2
        board_h = h - board_y - status_h - 18

        board = QRect(board_x, board_y, board_w, board_h)
        center_x = board.center().x()

        inner = 18
        logo_size = min(230, max(190, int(board_w * 0.17)))
        logo_rect = QRect(center_x - logo_size // 2, board_y - 6, logo_size, logo_size)

        logo_gap = logo_size + 42
        header_y = board_y + 20
        header_h = 90
        header_w = int((board_w - logo_gap - inner * 2) / 2)
        header_left = QRect(board_x + inner, header_y, header_w, header_h)
        header_right = QRect(center_x + logo_gap // 2, header_y, header_w, header_h)

        left_x = board_x + 46
        right_gap = 26
        content_w = board_w - 92
        left_w = int((content_w - right_gap) * 0.49)
        right_w = content_w - right_gap - left_w
        right_x = left_x + left_w + right_gap

        title_y = board_y + 138
        title_h = 54
        body_y = title_y + 62
        body_h = board.bottom() - body_y - 62

        # Titulky jsou zkrácené směrem k logu, aby pod ním nebyl velký widget.
        title_cut = min(110, int(logo_size * 0.48))
        left_title = QRect(left_x, title_y, left_w - title_cut, title_h)
        right_title = QRect(right_x + title_cut, title_y, right_w - title_cut, title_h)

        left_body = QRect(left_x, body_y, left_w, body_h)
        right_body = QRect(right_x, body_y, right_w, body_h)

        return Rects(
            board=board,
            header_left=header_left,
            header_right=header_right,
            logo=logo_rect,
            left_title=left_title,
            right_title=right_title,
            left_body=left_body,
            right_body=right_body,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_layout_positions()

    def update_layout_positions(self):
        r = self.compute_rects()
        self.rects = r

        self.header_left.setGeometry(r.header_left)
        self.header_right.setGeometry(r.header_right)
        self.sun_icon.setGeometry(20, 0, 80, r.header_left.height())
        self.anchor_top.setGeometry(r.header_right.width() - 80, 0, 60, r.header_right.height())

        self.left_title_frame.setGeometry(r.left_title)
        self.right_title_frame.setGeometry(r.right_title)
        self.left_title.setGeometry(18, 0, r.left_title.width() - 36, r.left_title.height())
        self.right_title.setGeometry(18, 0, r.right_title.width() - 80, r.right_title.height())
        self.right_title_anchor.setGeometry(r.right_title.width() - 58, 0, 40, r.right_title.height())

        self.left_body.setGeometry(r.left_body)
        self.scroll_area.setGeometry(8, 8, r.left_body.width() - 16, r.left_body.height() - 16)

        # Pravé prvky
        rb = r.right_body
        self.input_text.setGeometry(rb.x(), rb.y(), rb.width(), 102)

        btn_y = rb.y() + 122
        btn_gap = 24
        btn_w = (rb.width() - btn_gap) // 2
        self.encrypt_button.setGeometry(rb.x(), btn_y, btn_w, 62)
        self.decrypt_button.setGeometry(rb.x() + btn_w + btn_gap, btn_y, btn_w, 62)

        result_y = btn_y + 82
        self.result_title.setGeometry(rb.x(), result_y, rb.width(), 30)
        out_y = result_y + 38
        self.output_text.setGeometry(rb.x(), out_y, rb.width(), max(120, r.board.bottom() - out_y - 66))
        self.output_star.setGeometry(rb.right() - 76, self.output_text.geometry().bottom() - 76, 54, 54)
        self.output_star.raise_()

        self.status.setGeometry(0, self.height() - 24, self.width(), 24)

        self.logo_overlay.setGeometry(r.logo)
        self.logo_overlay.raise_()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Pozadí pergamenu
        if not self.bg_pixmap.isNull():
            scaled = self.bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(self.rect(), QColor("#1d1712"))

        if not self.rects:
            return

        board = QRectF(self.rects.board)

        # Stín
        painter.setBrush(QColor(0, 0, 0, 85))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(board.adjusted(6, 7, 6, 7), 24, 24)

        # Hlavní modrý panel
        grad = QLinearGradient(board.left(), board.top(), board.right(), board.bottom())
        grad.setColorAt(0, QColor("#103452"))
        grad.setColorAt(0.45, QColor(Colors.BLUE_MAIN))
        grad.setColorAt(1, QColor("#092036"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(Colors.GOLD), 3))
        painter.drawRoundedRect(board, 24, 24)

        # Jemné vnitřní linky jako v referenci
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.drawRoundedRect(board.adjusted(12, 12, -12, -12), 18, 18)
        painter.setPen(QPen(QColor(Colors.BLUE_BORDER), 1))
        painter.drawLine(board.left() + 20, board.top() + 92, board.right() - 20, board.top() + 92)

        # Dekorační body a kotvy
        painter.setPen(QPen(QColor(Colors.GOLD_TEXT), 2))
        painter.setFont(QFont("Segoe UI Symbol", 16))
        painter.drawText(int(board.left() + 13), int(board.top() + 25), "•")
        painter.drawText(int(board.right() - 28), int(board.top() + 28), "×")
        painter.drawText(int(board.left() + 12), int(board.bottom() - 12), "⊙")
        painter.drawText(int(board.right() - 42), int(board.bottom() - 12), "⚓")

    def select_cipher(self, name):
        self.selected_cipher = name
        self.refresh_cipher_styles()
        self.update_status()

    def refresh_cipher_styles(self):
        for btn in self.cipher_buttons:
            btn.set_selected(btn.cipher_name == self.selected_cipher)

    def update_status(self):
        self.status.setText(
            f"VYBRÁNÁ ŠIFRA: {self.selected_cipher} | Logování: Vypnuto | SRC složka nalezena."
        )

    def get_input_text(self):
        return self.input_text.toPlainText().strip()

    def encrypt_action(self):
        text = self.get_input_text()
        if not text:
            self.output_text.setPlainText("Nejdřív zadej text k zašifrování.")
            return

        # Zde napojíš vlastní logiku šifrování.
        self.output_text.setPlainText(
            f"Vybraná šifra: {self.selected_cipher}\n\nZašifrovaný text:\n{text}"
        )

    def decrypt_action(self):
        text = self.get_input_text()
        if not text:
            self.output_text.setPlainText("Nejdřív zadej text k dešifrování.")
            return

        # Zde napojíš vlastní logiku dešifrování.
        self.output_text.setPlainText(
            f"Vybraná šifra: {self.selected_cipher}\n\nDešifrovaný text:\n{text}"
        )


class SifratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ŠIFRÁTOR MRAVENIŠTĚ - PIRÁTI Z KARIBIKU")
        self.resize(1408, 768)
        self.setMinimumSize(1200, 700)

        central = PirateCentralWidget()
        self.setCentralWidget(central)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Šifrátor Mraveniště")

    window = SifratorWindow()
    window.show()

    sys.exit(app.exec())
