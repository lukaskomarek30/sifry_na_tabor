# ============================================================
# Zlomky - logika šifrování, dešifrování + kreslený výstup
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Zlomky\zlomky.py
#
# Klíč podle obrázku:
# A B C D E  -> jmenovatel 1
# F G H I J  -> jmenovatel 2
# K L M N O  -> jmenovatel 3
# P Q R S T  -> jmenovatel 4
# U V X Y Z  -> jmenovatel 5
#
# Čitatel = pořadí písmene ve skupině 1-5
# Jmenovatel = číslo skupiny 1-5
#
# A = 1/1, H = 3/2, O = 5/3, J = 5/2
#
# DŮLEŽITÉ:
# encrypt() vrací interní zápis 1/1 3/2 ...
# ZlomkyOutputWidget tento zápis kreslí jako klasické zlomky:
#
#   1
#  ---
#   1
#
# Symboly jako ?,.-! zůstávají beze změny.
# ============================================================

from __future__ import annotations

import html
import re
import unicodedata

from PySide6.QtCore import Qt, QRectF, QTimer, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


GROUPS = [
    "ABCDE",
    "FGHIJ",
    "KLMNO",
    "PQRST",
    "UVXYZ",
]

LETTER_TO_CODE: dict[str, str] = {}
CODE_TO_LETTER: dict[str, str] = {}

for group_index, letters in enumerate(GROUPS, start=1):
    for position_index, letter in enumerate(letters, start=1):
        code = f"{position_index}/{group_index}"
        LETTER_TO_CODE[letter] = code
        CODE_TO_LETTER[code] = letter

# W v klíči není. Při šifrování se proto bere jako V.
LETTER_TO_CODE["W"] = LETTER_TO_CODE["V"]


def remove_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Zašifruje text do interního tvaru 1/1 3/2 ...

    Zobrazení jako skutečný zlomek dělá ZlomkyOutputWidget v tomto souboru.
    """
    normalized = remove_diacritics(text)
    result: list[str] = []
    need_letter_separator = False

    for char in normalized:
        if char == "\n":
            while result and result[-1] == " ":
                result.pop()
            result.append("\n")
            need_letter_separator = False
            continue

        if char.isspace():
            if not result:
                continue
            # dvě mezery = mezera mezi slovy
            if result[-1] == " ":
                result[-1] = "  "
            elif result[-1] != "  " and result[-1] != "\n":
                result.append("  ")
            need_letter_separator = False
            continue

        if char in LETTER_TO_CODE:
            if need_letter_separator and result and result[-1] not in (" ", "  ", "\n"):
                result.append(" ")
            result.append(LETTER_TO_CODE[char])
            need_letter_separator = True
            continue

        # Symboly jako ?, . , - ! : ; zůstávají stejné.
        result.append(char)
        need_letter_separator = True

    return "".join(result).rstrip()


def decrypt(text: str) -> str:
    """Dešifruje interní zápis 1/1 3/2 ... zpět na text.

    Jedna mezera odděluje písmena, dvě a více mezer oddělují slova.
    Symboly zůstávají zachované.
    """
    source = str(text or "")
    result: list[str] = []
    index = 0

    while index < len(source):
        char = source[index]

        if char == "\n":
            if result and result[-1] == " ":
                result.pop()
            result.append("\n")
            index += 1
            continue

        if char.isspace():
            start = index
            while index < len(source) and source[index].isspace() and source[index] != "\n":
                index += 1
            if index - start >= 2 and result and result[-1] not in (" ", "\n"):
                result.append(" ")
            continue

        if (
            index + 2 < len(source)
            and source[index].isdigit()
            and source[index + 1] == "/"
            and source[index + 2].isdigit()
        ):
            code = source[index:index + 3]
            if code in CODE_TO_LETTER:
                result.append(CODE_TO_LETTER[code])
                index += 3
                continue

        result.append(char)
        index += 1

    return "".join(result).rstrip()


def parse_cipher_tokens(cipher_text: str) -> list[str]:
    """Rozdělí interní zápis na tokeny pro kreslení.

    Tokeny jsou:
    - "1/1" až "5/5"
    - " " pro mezery mezi písmeny
    - "  " pro mezery mezi slovy
    - běžné symboly (?, . ...)
    - "\n"
    """
    source = str(cipher_text or "")
    tokens: list[str] = []
    index = 0

    while index < len(source):
        char = source[index]

        if char == "\n":
            tokens.append("\n")
            index += 1
            continue

        if char.isspace():
            start = index
            while index < len(source) and source[index].isspace() and source[index] != "\n":
                index += 1
            tokens.append("  " if index - start >= 2 else " ")
            continue

        match = re.match(r"(\d)/(\d)", source[index:])
        if match:
            tokens.append(match.group(0))
            index += len(match.group(0))
            continue

        tokens.append(char)
        index += 1

    return tokens


class ZlomkyOutputWidget(QWidget):
    """Kreslený výstup šifry Zlomky.

    Nepoužívá QTextEdit ani HTML. Každý zlomek se kreslí ručně přes QPainter,
    takže výsledek nebude nikdy obyčejný text 1/1.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.tokens: list[str] = []
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(180)

    def set_scale(self, scale: float):
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        self.cipher_text = str(text or "")
        self.tokens = parse_cipher_tokens(self.cipher_text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        self.cipher_text = ""
        self.tokens = []
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_content_size()

    def get_metrics(self):
        # Větší výška, aby bylo jasně vidět čitatel / čára / jmenovatel.
        frac_w = max(34, int(46 * self.scale_value))
        frac_h = max(58, int(78 * self.scale_value))
        letter_gap = max(7, int(10 * self.scale_value))
        word_gap = max(22, int(34 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return frac_w, frac_h, letter_gap, word_gap, line_gap

    def token_width(self, token: str) -> int:
        frac_w, _, _, word_gap, _ = self.get_metrics()

        if token == " ":
            return max(10, int(10 * self.scale_value))
        if token == "  ":
            return word_gap
        if re.fullmatch(r"\d/\d", token):
            return frac_w

        return max(22, int(32 * self.scale_value))

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 8
        margin_right = 8
        margin_top = 4
        margin_bottom = 16

        _, frac_h, letter_gap, _, line_gap = self.get_metrics()
        content_width = max(120, available_width - margin_left - margin_right)

        if not self.tokens:
            return max(170, frac_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for token in self.tokens:
            if token == "\n":
                x = 0
                y += frac_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > 0 and x + token_w > content_width:
                x = 0
                y += frac_h + line_gap

            x += token_w
            if token not in (" ", "  "):
                x += letter_gap

        return max(170, y + frac_h + margin_top + margin_bottom)

    def update_content_size(self):
        parent = self.parentWidget()
        width = self.width()

        if parent is not None and parent.width() > 20:
            width = parent.width()

        width = max(260, width)
        needed_height = self.calculate_required_height(width)

        self.setMinimumSize(width, needed_height)
        if self.width() != width or self.height() != needed_height:
            self.resize(width, needed_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = self.rect().adjusted(8, 4, -8, -8)

        if not self.tokens:
            painter.setFont(QFont("Georgia", max(10, int(14 * self.scale_value))))
            painter.setPen(QColor("#a8a295"))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "Kreslené zlomky se objeví zde...")
            return

        frac_w, frac_h, letter_gap, _, line_gap = self.get_metrics()
        x = rect.left()
        y = rect.top()

        for token in self.tokens:
            if token == "\n":
                x = rect.left()
                y += frac_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > rect.left() and x + token_w > rect.right():
                x = rect.left()
                y += frac_h + line_gap

            if token == " ":
                x += token_w
                continue

            if token == "  ":
                x += token_w
                continue

            if re.fullmatch(r"\d/\d", token):
                self.draw_fraction(painter, QRectF(x, y, frac_w, frac_h), token)
                x += frac_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, token_w, frac_h), token)
                x += token_w + letter_gap

    def draw_fraction(self, painter: QPainter, rect: QRectF, token: str):
        numerator, denominator = token.split("/", 1)
        color = QColor("#f3d79a")

        num_font = QFont("Georgia", max(14, int(24 * self.scale_value)), QFont.Normal)
        den_font = QFont("Georgia", max(14, int(24 * self.scale_value)), QFont.Normal)

        cx = rect.center().x()
        top = rect.top()
        bottom = rect.bottom()
        mid_y = rect.top() + rect.height() * 0.50

        num_rect = QRectF(rect.left(), top, rect.width(), rect.height() * 0.38)
        den_rect = QRectF(rect.left(), mid_y + rect.height() * 0.10, rect.width(), rect.height() * 0.38)

        painter.setPen(color)
        painter.setFont(num_font)
        painter.drawText(num_rect, Qt.AlignCenter, numerator)

        # Vodorovná čára zlomku.
        line_margin = rect.width() * 0.16
        pen_width = max(2, int(2.2 * self.scale_value))
        painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.SquareCap))
        painter.drawLine(
            QPointF(rect.left() + line_margin, mid_y),
            QPointF(rect.right() - line_margin, mid_y),
        )

        painter.setPen(color)
        painter.setFont(den_font)
        painter.drawText(den_rect, Qt.AlignCenter, denominator)

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(20, int(34 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


# Nechávám i HTML pomocnou funkci kvůli zpětné kompatibilitě,
# ale hlavní aplikace má používat ZlomkyOutputWidget.
def _html_fraction(numerator: str, denominator: str, color: str, font_size: int) -> str:
    n = html.escape(str(numerator))
    d = html.escape(str(denominator))
    line_color = html.escape(color)
    return (
        '<span style="display:inline-block; vertical-align:middle; text-align:center; '
        f'margin-right:{max(6, font_size // 3)}px; color:{line_color};">'
        f'<span style="display:block; font-size:{font_size}px; line-height:{font_size}px;">{n}</span>'
        f'<span style="display:block; border-top:2px solid {line_color}; height:1px; line-height:1px;"></span>'
        f'<span style="display:block; font-size:{font_size}px; line-height:{font_size}px;">{d}</span>'
        '</span>'
    )


def to_html(cipher_text: str, color: str = "#f3d79a", font_family: str = "Georgia", font_size: int = 28) -> str:
    source = str(cipher_text or "")
    font_family_safe = html.escape(font_family)
    color_safe = html.escape(color)
    font_size = int(max(16, font_size))

    parts: list[str] = []
    index = 0

    while index < len(source):
        char = source[index]
        if char == "\n":
            parts.append("<br>")
            index += 1
            continue

        if char.isspace():
            start = index
            while index < len(source) and source[index].isspace() and source[index] != "\n":
                index += 1
            parts.append("&nbsp;&nbsp;&nbsp;&nbsp;" if index - start >= 2 else "&nbsp;")
            continue

        match = re.match(r"(\d)/(\d)", source[index:])
        if match:
            parts.append(_html_fraction(match.group(1), match.group(2), color_safe, font_size))
            index += 3
            continue

        parts.append(
            f'<span style="font-size:{int(font_size * 1.55)}px; color:{color_safe}; '
            f'vertical-align:middle; margin-right:{max(4, font_size // 4)}px;">'
            f'{html.escape(char)}</span>'
        )
        index += 1

    return (
        '<html><head><meta charset="utf-8"></head>'
        f'<body style="background:transparent; color:{color_safe}; font-family:{font_family_safe}; '
        f'font-size:{font_size}px; margin:0; padding:0;">'
        + "".join(parts) +
        '</body></html>'
    )


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    print(encrypted)
    print(decrypt(encrypted))
