# ============================================================
# Velký polský kříž - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Velký polský kříž\velky_polsky_kriz.py
#
# OPRAVA:
# Tato verze mapuje znaky přesně podle celé abecedy, kterou jsi poslal.
#
# Skupiny po třech znacích:
#   ABC | DEF | G H CH | IJK | LMN | OPQ | RST | UVW | XYZ
#
# Tvar skupiny:
#   ABC  = spodní čára + pravá svislá          (┘)
#   DEF  = levá + spodní + pravá               (∪)
#   G,H,CH = levá + spodní                     (└)
#   IJK  = horní + spodní + pravá              (⊐)
#   LMN  = obdélník                            (□)
#   OPQ  = levá + horní + spodní               (⊏)
#   RST  = horní + pravá                       (┐)
#   UVW  = levá + horní + pravá                (∩)
#   XYZ  = levá + horní                        (┌)
#
# Pozice tečky v rámci trojice:
#   1. znak = vlevo
#   2. znak = uprostřed
#   3. znak = vpravo
#
# Symboly jako ?, . , - ! : ; / zůstávají beze změny.
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QRectF, QTimer, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

# 9 skupin po 3 znacích přesně v pořadí klíče.
TOKEN_GROUPS = [
    ["A", "B", "C"],
    ["D", "E", "F"],
    ["G", "H", "CH"],
    ["I", "J", "K"],
    ["L", "M", "N"],
    ["O", "P", "Q"],
    ["R", "S", "T"],
    ["U", "V", "W"],
    ["X", "Y", "Z"],
]

# family_index -> které strany se kreslí
# top, right, bottom, left
FAMILY_LINES = {
    0: dict(top=False, right=True,  bottom=True,  left=False),  # ABC
    1: dict(top=False, right=True,  bottom=True,  left=True),   # DEF
    2: dict(top=False, right=False, bottom=True,  left=True),   # G H CH
    3: dict(top=True,  right=True,  bottom=True,  left=False),  # IJK
    4: dict(top=True,  right=True,  bottom=True,  left=True),   # LMN
    5: dict(top=True,  right=False, bottom=True,  left=True),   # OPQ
    6: dict(top=True,  right=True,  bottom=False, left=False),  # RST
    7: dict(top=True,  right=True,  bottom=False, left=True),   # UVW
    8: dict(top=True,  right=False, bottom=False, left=True),   # XYZ
}

POSITION_BY_TOKEN = {}
for family_index, family in enumerate(TOKEN_GROUPS):
    for dot_index, token in enumerate(family):
        POSITION_BY_TOKEN[token] = (family_index, dot_index)

SUPPORTED_TOKENS = set(POSITION_BY_TOKEN.keys())


def normalize_text(text: str) -> str:
    """Odstraní českou diakritiku a převede text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def tokenize_text(text: str) -> list[str]:
    """Rozdělí text na tokeny. CH je jeden token."""
    text = normalize_text(text)
    tokens: list[str] = []
    index = 0

    while index < len(text):
        if text[index:index + 2] == "CH":
            tokens.append("CH")
            index += 2
            continue

        tokens.append(text[index])
        index += 1

    return tokens


def encrypt(text: str) -> str:
    """Vrátí normalizovaný text pro kreslenou šifru."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Podpora interního dešifrování přes běžný nebo hranatý zápis."""
    cleaned = text.strip()
    if not cleaned:
        return ""

    result: list[str] = []
    index = 0

    while index < len(cleaned):
        char = cleaned[index]

        if char == "[":
            end = cleaned.find("]", index + 1)
            if end != -1:
                token = normalize_text(cleaned[index + 1:end].strip())
                if token in SUPPORTED_TOKENS or len(token) == 1:
                    result.append(token)
                    index = end + 1
                    continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))


class VelkyPolskyKrizOutputWidget(QWidget):
    """Kreslený výstup šifry Velký polský kříž."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.tokens: list[str] = []
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(175)

    def set_scale(self, scale: float):
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        self.cipher_text = normalize_text(text)
        self.tokens = tokenize_text(text)
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
        cell_w = max(48, int(72 * self.scale_value))
        cell_h = max(42, int(60 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(26, int(42 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def token_width(self, token: str) -> int:
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if token == " ":
            return word_gap

        if token in SUPPORTED_TOKENS:
            return cell_w

        return max(24, int(34 * self.scale_value))

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, cell_h, letter_gap, _, line_gap = self.get_metrics()
        content_width = max(160, available_width - margin_left - margin_right)

        if not self.tokens:
            return max(170, cell_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for token in self.tokens:
            if token == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > 0 and x + token_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += token_w
            if token != " ":
                x += letter_gap

        return max(170, y + cell_h + margin_top + margin_bottom)

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

        rect = self.rect().adjusted(14, 10, -14, -10)

        if not self.tokens:
            painter.setFont(QFont("Georgia", max(10, int(14 * self.scale_value))))
            painter.setPen(QColor("#a8a295"))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "Kreslený výsledek se objeví zde...")
            return

        cell_w, cell_h, letter_gap, _, line_gap = self.get_metrics()
        x = rect.left()
        y = rect.top()

        for token in self.tokens:
            if token == "\n":
                x = rect.left()
                y += cell_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > rect.left() and x + token_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if token == " ":
                x += token_w
                continue

            if token in SUPPORTED_TOKENS:
                self.draw_cross_token(painter, QRectF(x, y, cell_w, cell_h), token)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, token_w, cell_h), token)
                x += token_w + letter_gap

    def draw_cross_token(self, painter: QPainter, rect: QRectF, token: str):
        family_index, dot_index = POSITION_BY_TOKEN[token]
        family = FAMILY_LINES[family_index]

        color = QColor("#f3d79a")
        pen_width = max(3, int(5 * self.scale_value))
        pen = QPen(color, pen_width, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        left = rect.left() + rect.width() * 0.14
        right = rect.right() - rect.width() * 0.14
        top = rect.top() + rect.height() * 0.16
        bottom = rect.bottom() - rect.height() * 0.16
        mid_y = (top + bottom) / 2

        if family["top"]:
            painter.drawLine(QPointF(left, top), QPointF(right, top))
        if family["right"]:
            painter.drawLine(QPointF(right, top), QPointF(right, bottom))
        if family["bottom"]:
            painter.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        if family["left"]:
            painter.drawLine(QPointF(left, top), QPointF(left, bottom))

        if dot_index == 0:
            dot_x = left + (right - left) * 0.22
        elif dot_index == 1:
            dot_x = (left + right) / 2
        else:
            dot_x = right - (right - left) * 0.22

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        dot_r = max(4.0, rect.height() * 0.085)
        painter.drawEllipse(QPointF(dot_x, mid_y), dot_r, dot_r)

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(18, int(38 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


if __name__ == "__main__":
    sample = "Ahoj jak se máš? abc"
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypt(sample))
    print("Tokeny:", tokenize_text(sample))
