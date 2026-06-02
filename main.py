import os
import sys
from dataclasses import dataclass

# Verze v5 – horní pásy jsou jemnější, nižší a více zapuštěné do hlavního panelu.

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
    """Vlastní zlaté tlačítko kreslené přes QPainter.
    Nepoužívá emoji zámky, aby nebyly barevné jako systémové emoji.
    """

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(58)
        self.setFont(QFont("Segoe UI", 19, QFont.Bold))
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

        # Jemné vnitřní hrany jako na referenci.
        inner = r.adjusted(7, 7, -7, -7)
        painter.setPen(QPen(QColor("#9a6b30"), 1))
        painter.drawLine(int(inner.left() + 45), int(inner.bottom() - 2), int(inner.right() - 24), int(inner.bottom() - 2))
        painter.drawLine(int(inner.left() + 45), int(inner.top() + 2), int(inner.right() - 24), int(inner.top() + 2))

        # Malé boční šipky.
        painter.setPen(QPen(QColor("#9a6b30"), 2))
        painter.setFont(QFont("Segoe UI Symbol", 17, QFont.Bold))
        painter.drawText(QRectF(6, 0, 18, self.height()), Qt.AlignCenter, "‹")
        painter.drawText(QRectF(self.width() - 24, 0, 18, self.height()), Qt.AlignCenter, "›")

        # Text + ručně kreslený zámek, aby nebyl barevné emoji.
        text_font = QFont("Segoe UI", 19, QFont.Bold)
        painter.setFont(text_font)
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(self.text())
        total_w = text_w + 44
        start_x = r.center().x() - total_w / 2
        icon_x = start_x
        icon_y = r.center().y() - 9

        pen = QPen(QColor(Colors.BUTTON_TEXT), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        # Tělo zámku
        painter.drawRoundedRect(QRectF(icon_x + 5, icon_y + 8, 18, 17), 3, 3)
        # Oblouk zámku
        painter.drawArc(QRectF(icon_x + 8, icon_y - 1, 12, 18), 0, 180 * 16)
        # Díra zámku
        painter.setBrush(QBrush(QColor(Colors.BUTTON_TEXT)))
        painter.drawEllipse(QRectF(icon_x + 13, icon_y + 14, 3.5, 3.5))
        painter.drawRect(QRectF(icon_x + 14, icon_y + 17, 1.5, 5))

        painter.setPen(QPen(QColor(Colors.BUTTON_TEXT)))
        painter.setFont(text_font)
        painter.drawText(QRectF(start_x + 44, 0, text_w + 8, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())

class CipherButton(QPushButton):
    def __init__(self, text, name, parent=None):
        super().__init__(text, parent)
        self.cipher_name = name
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(43)
        self.setFont(QFont("Segoe UI", 13))
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
        # Horní panely jsou v této verzi kreslené přímo v paintEvent.
        # Tyto průhledné rámečky slouží jen jako držáky pro případný text/ikony.
        self.header_left = QFrame(self)
        self.header_right = QFrame(self)
        for frame in (self.header_left, self.header_right):
            frame.setAttribute(Qt.WA_TranslucentBackground, True)
            frame.setStyleSheet("background: transparent; border: none;")

        self.sun_icon = QLabel("", self.header_left)
        self.sun_icon.setStyleSheet("background: transparent;")

        self.anchor_top = QLabel("", self.header_right)
        self.anchor_top.setStyleSheet("background: transparent;")

        # Titulkové pásy jsou také kreslené v paintEvent, aby šel udělat výřez okolo loga.
        self.left_title_frame = QFrame(self)
        self.right_title_frame = QFrame(self)
        for frame in (self.left_title_frame, self.right_title_frame):
            frame.setAttribute(Qt.WA_TranslucentBackground, True)
            frame.setStyleSheet("background: transparent; border: none;")

        self.left_title = QLabel("VYBER SI ŠIFRU (28)", self.left_title_frame)
        self.right_title = QLabel("TEXT K ZAŠIFROVÁNÍ", self.right_title_frame)
        for label in (self.left_title, self.right_title):
            label.setFont(QFont("Segoe UI", 18, QFont.Bold))
            label.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.right_title_anchor = QLabel("", self.right_title_frame)
        self.right_title_anchor.setStyleSheet("background: transparent;")

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
        self.grid.setContentsMargins(10, 8, 10, 8)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(7)
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
            ("▯  Mobil", "Mobil"),
            ("☾  Mobiž", "Mobiž"),
            ("☽  Moonovo písmo", "Moonovo písmo"),
            ("⋯−  Morseova abeceda", "Morseova abeceda"),
            ("▲▲  Morseova abeceda – hory", "Morseova abeceda – hory"),
            ("♟  Tančící figurky I/II", "Tančící figurky I/II"),
            ("♟  Tančící figurky II", "Tančící figurky II"),
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

        self.encrypt_button = GoldButton("ZAŠIFROVAT", self)
        self.decrypt_button = GoldButton("DEŠIFROVAT", self)
        self.encrypt_button.clicked.connect(self.encrypt_action)
        self.decrypt_button.clicked.connect(self.decrypt_action)

        self.result_title = QLabel("VÝSLEDEK", self)
        self.result_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.result_title.setStyleSheet(f"color: {Colors.GOLD_TEXT}; background: transparent;")

        self.output_text = QTextEdit(self)
        self.output_text.setPlaceholderText("Zašifrovaný text se objeví zde...")
        self.output_text.setFont(QFont("Segoe UI", 14))
        self.output_text.setStyleSheet(self.text_edit_style())
        # Text nechávám jako placeholder; skutečný výstup se doplní po kliknutí.

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
        # V4: hlavní panel je posazený podobně jako v referenci –
        # není nalepený úplně k levému okraji a horní část má víc vzduchu.
        board_x = max(28, int(w * 0.020))
        board_y = 28
        board_w = w - board_x * 2
        board_h = h - board_y - status_h - 18

        board = QRect(board_x, board_y, board_w, board_h)
        center_x = board.center().x()

        # Logo podobně jako v referenci. Důležité je, že pod ním nejsou titulkové panely.
        # Logo v referenci sedí níž a není nalepené na horní rámeček.
        # Menší velikost pomáhá tomu, aby titulkové pásy nepůsobily useknutě.
        logo_size = min(212, max(190, int(board_w * 0.154)))
        logo_rect = QRect(center_x - logo_size // 2, board_y + 7, logo_size, logo_size)

        # Horní dekorativní panely.
        inner = 18
        logo_gap = logo_size + 52
        # Horní dekorativní pásy: v referenci nejsou výrazné vysoké bloky,
        # ale nízké, jemně zatmavené pruhy zapuštěné do hlavního panelu.
        header_y = board_y + 28
        header_h = 62
        header_w = int((board_w - logo_gap - inner * 2) / 2)
        header_left = QRect(board_x + inner, header_y, header_w, header_h)
        header_right = QRect(center_x + logo_gap // 2, header_y, header_w, header_h)

        # Hlavní pracovní část. Rozměry jsou laděné pro okno 1408×768
        # a zároveň se přepočítávají podle velikosti okna.
        left_x = board_x + 45
        right_margin = 50
        middle_gap = 28
        available = board_w - 45 - right_margin - middle_gap
        left_w = int(available * 0.504)
        right_w = available - left_w
        right_x = left_x + left_w + middle_gap

        # Titulkové pásy jsou níž – v referenci je mezi horní lištou a titulkem
        # delší tmavý přechod, ne hned další panel.
        title_y = board_y + 138
        title_h = 51
        left_body_y = title_y + 54
        left_body_h = board.bottom() - left_body_y - 64

        # Titulky jsou zkrácené uprostřed kvůli logu.
        title_cut = min(92, int(logo_size * 0.44))
        left_title = QRect(left_x, title_y, left_w - title_cut, title_h)
        right_title = QRect(right_x + title_cut, title_y, right_w - title_cut, title_h)

        left_body = QRect(left_x, left_body_y, left_w, left_body_h)

        # right_body je základní obdélník sloupce; jednotlivé pravé prvky se níže
        # rozmístí podobně jako v referenci. Vstupní pole začíná níž než levý seznam.
        right_body = QRect(right_x, left_body_y, right_w, left_body_h)

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

        # Pravé prvky – vstupní pole začíná níž než titulek, stejně jako v referenci.
        rb = r.right_body
        input_y = r.board.y() + 252
        self.input_text.setGeometry(rb.x(), input_y, rb.width(), 100)

        btn_y = input_y + 122
        btn_gap = 26
        btn_w = (rb.width() - btn_gap) // 2
        self.encrypt_button.setGeometry(rb.x(), btn_y, btn_w, 62)
        self.decrypt_button.setGeometry(rb.x() + btn_w + btn_gap, btn_y, btn_w, 62)

        result_y = btn_y + 84
        self.result_title.setGeometry(rb.x(), result_y, rb.width(), 30)
        out_y = result_y + 38
        self.output_text.setGeometry(rb.x(), out_y, rb.width(), max(120, r.board.bottom() - out_y - 40))
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
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.drawRoundedRect(board.adjusted(12, 12, -12, -12), 18, 18)
        painter.setPen(QPen(QColor(52, 97, 127, 165), 1))
        painter.drawLine(board.left() + 20, board.top() + 92, board.right() - 20, board.top() + 92)

        # Horní panely a titulkové pásy se kreslí jako grafika, ne jako obdélníkové widgety.
        self.draw_panel_round_rect(painter, self.rects.header_left, 15, False)
        self.draw_panel_round_rect(painter, self.rects.header_right, 15, False)
        self.draw_title_tab(painter, self.rects.left_title, "left")
        self.draw_title_tab(painter, self.rects.right_title, "right")

        # Dekorační body a kotvy
        deco = QColor(Colors.GOLD_TEXT)
        deco.setAlpha(210)
        painter.setPen(QPen(deco, 2))
        painter.setFont(QFont("Segoe UI Symbol", 16))
        painter.drawText(int(board.left() + 13), int(board.top() + 25), "•")
        painter.drawText(int(board.right() - 28), int(board.top() + 28), "×")
        painter.drawText(int(board.left() + 12), int(board.bottom() - 12), "⊙")
        # Dekorace kreslené ručně, aby nevznikaly barevné systémové emoji.
        if self.rects:
            self.draw_compass(painter, self.rects.header_left.left() + 42, self.rects.header_left.center().y(), 30, alpha=120)
            self.draw_anchor(painter, self.rects.header_right.right() - 43, self.rects.header_right.center().y(), 30, alpha=170)
            self.draw_anchor(painter, self.rects.right_title.right() - 34, self.rects.right_title.center().y(), 20, alpha=175)
            self.draw_anchor(painter, int(board.right() - 28), int(board.bottom() - 18), 18, alpha=205)


    def draw_panel_round_rect(self, painter, rect: QRect, radius=14, border=False):
        """Jemný horní pás.

        V referenci horní oblast nepůsobí jako samostatné výrazné tlačítko,
        ale jako velmi jemně zapuštěný pruh v hlavním modrém panelu.
        Proto používáme průhledné barvy a jen slabý vnitřní lesk.
        """
        rr = QRectF(rect)
        path = QPainterPath()
        path.addRoundedRect(rr, radius, radius)

        grad = QLinearGradient(rr.left(), rr.top(), rr.right(), rr.bottom())
        c1 = QColor("#164564"); c1.setAlpha(88)
        c2 = QColor("#10334f"); c2.setAlpha(58)
        c3 = QColor("#092338"); c3.setAlpha(42)
        grad.setColorAt(0.00, c1)
        grad.setColorAt(0.55, c2)
        grad.setColorAt(1.00, c3)
        painter.fillPath(path, QBrush(grad))

        # horní jemný odlesk
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawLine(int(rr.left() + radius), int(rr.top() + 1), int(rr.right() - radius), int(rr.top() + 1))

        # spodní linka je lehce viditelná, podobně jako v předloze
        painter.setPen(QPen(QColor(52, 97, 127, 55), 1))
        painter.drawLine(int(rr.left() + 8), int(rr.bottom()), int(rr.right() - 8), int(rr.bottom()))

        if border:
            pen_color = QColor(Colors.BLUE_BORDER)
            pen_color.setAlpha(70)
            painter.setPen(QPen(pen_color, 1))
            painter.drawPath(path)

    def draw_title_tab(self, painter, rect: QRect, side: str):
        """Kreslí titulkový panel s jemným zkosením u loga."""
        rr = QRectF(rect)
        r = 14
        notch = min(26, max(16, int(rect.width() * 0.05)))
        path = QPainterPath()

        if side == "left":
            path.moveTo(rr.left() + r, rr.top())
            path.lineTo(rr.right() - notch, rr.top())
            path.quadTo(rr.right(), rr.top(), rr.right(), rr.top() + r)
            path.lineTo(rr.right(), rr.bottom() - r)
            path.quadTo(rr.right(), rr.bottom(), rr.right() - r, rr.bottom())
            path.lineTo(rr.left() + r, rr.bottom())
            path.quadTo(rr.left(), rr.bottom(), rr.left(), rr.bottom() - r)
            path.lineTo(rr.left(), rr.top() + r)
            path.quadTo(rr.left(), rr.top(), rr.left() + r, rr.top())
        else:
            path.moveTo(rr.left() + r, rr.top())
            path.lineTo(rr.right() - r, rr.top())
            path.quadTo(rr.right(), rr.top(), rr.right(), rr.top() + r)
            path.lineTo(rr.right(), rr.bottom() - r)
            path.quadTo(rr.right(), rr.bottom(), rr.right() - r, rr.bottom())
            path.lineTo(rr.left() + notch, rr.bottom())
            path.quadTo(rr.left(), rr.bottom(), rr.left(), rr.bottom() - r)
            path.lineTo(rr.left(), rr.top() + r)
            path.quadTo(rr.left(), rr.top(), rr.left() + r, rr.top())

        grad = QLinearGradient(rr.left(), rr.top(), rr.right(), rr.bottom())
        grad.setColorAt(0, QColor("#164261"))
        grad.setColorAt(1, QColor("#123754"))
        painter.fillPath(path, QBrush(grad))
        painter.setPen(QPen(QColor(Colors.BLUE_BORDER), 1))
        painter.drawPath(path)

        # jemný vnitřní lesk
        inner = rr.adjusted(18, 7, -18, -7)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawLine(int(inner.left()), int(inner.top()), int(inner.right()), int(inner.top()))

    def draw_compass(self, painter, center_x, center_y, size, alpha=155):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        icon_color = QColor(Colors.GOLD_TEXT)
        icon_color.setAlpha(alpha)
        pen = QPen(icon_color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        r = size / 2
        painter.drawEllipse(QRectF(center_x - r, center_y - r, size, size))
        painter.drawEllipse(QRectF(center_x - r * 0.35, center_y - r * 0.35, r * 0.7, r * 0.7))
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0), (0.7, -0.7), (0.7, 0.7), (-0.7, 0.7), (-0.7, -0.7)]:
            painter.drawLine(int(center_x), int(center_y), int(center_x + dx * r * 1.28), int(center_y + dy * r * 1.28))
        painter.setFont(QFont("Segoe UI", max(7, int(size * 0.18)), QFont.Bold))
        painter.drawText(QRectF(center_x - 9, center_y - r - 18, 18, 14), Qt.AlignCenter, "N")
        painter.drawText(QRectF(center_x + r + 2, center_y - 7, 18, 14), Qt.AlignCenter, "E")
        painter.drawText(QRectF(center_x - 9, center_y + r + 2, 18, 14), Qt.AlignCenter, "S")
        painter.drawText(QRectF(center_x - r - 20, center_y - 7, 18, 14), Qt.AlignCenter, "W")
        painter.restore()

    def draw_anchor(self, painter, center_x, center_y, size, alpha=205):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        icon_color = QColor(Colors.GOLD_TEXT)
        icon_color.setAlpha(alpha)
        pen = QPen(icon_color, max(2, int(size * 0.08)))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        s = size
        # kruh nahoře
        painter.drawEllipse(QRectF(center_x - s * 0.10, center_y - s * 0.48, s * 0.20, s * 0.20))
        # dřík
        painter.drawLine(int(center_x), int(center_y - s * 0.28), int(center_x), int(center_y + s * 0.25))
        # příčka
        painter.drawLine(int(center_x - s * 0.22), int(center_y - s * 0.05), int(center_x + s * 0.22), int(center_y - s * 0.05))
        # spodní oblouk a háky
        path = QPainterPath()
        path.moveTo(center_x - s * 0.42, center_y + s * 0.08)
        path.cubicTo(center_x - s * 0.32, center_y + s * 0.45, center_x + s * 0.32, center_y + s * 0.45, center_x + s * 0.42, center_y + s * 0.08)
        painter.drawPath(path)
        painter.drawLine(int(center_x - s * 0.42), int(center_y + s * 0.08), int(center_x - s * 0.55), int(center_y + s * 0.18))
        painter.drawLine(int(center_x - s * 0.42), int(center_y + s * 0.08), int(center_x - s * 0.33), int(center_y + s * 0.26))
        painter.drawLine(int(center_x + s * 0.42), int(center_y + s * 0.08), int(center_x + s * 0.55), int(center_y + s * 0.18))
        painter.drawLine(int(center_x + s * 0.42), int(center_y + s * 0.08), int(center_x + s * 0.33), int(center_y + s * 0.26))
        painter.restore()

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
