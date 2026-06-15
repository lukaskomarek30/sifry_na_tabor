# ============================================================
# Pseudo-Čína - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Pseudo-Čína\pseudo_cina.py
#
# Klíč:
# 1. řádek: A B C D E
# 2. řádek: F G H I J
# 3. řádek: K L M N O
# 4. řádek: P R S T U
# 5. řádek: V W X Y Z
#
# V tabulce chybí Q.
# Podle popisu se Q zapisuje jako kombinace K + V, proto encrypt()
# při šifrování převádí Q na KV.
#
# Princip:
# - počet vodorovných čar = řádek
# - počet svislých čar = sloupec
#
# Symboly jako ?, . , - ! : ; / zůstávají symboly.
# České znaky se převádí bez háčků a čárek.
# ============================================================

import math
import random
import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


GRID_ROWS = [
    "ABCDE",
    "FGHIJ",
    "KLMNO",
    "PRSTU",
    "VWXYZ",
]

LETTER_TO_COORDS = {}
COORDS_TO_LETTER = {}

for row_index, row_letters in enumerate(GRID_ROWS, start=1):
    for col_index, letter in enumerate(row_letters, start=1):
        LETTER_TO_COORDS[letter] = (row_index, col_index)
        COORDS_TO_LETTER[(row_index, col_index)] = letter


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Pseudo-Čína.

    Q v klíči chybí, proto se převede na KV.
    """
    normalized = normalize_text(text)
    return normalized.replace("Q", "KV")


def decrypt(text: str) -> str:
    """Textové / interní dešifrování.

    Kreslený výstup nejde spolehlivě číst z obyčejného textu, proto podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
    - souřadnice: 1,1 2,3 3,5 -> AHO
    - souřadnice s oddělovači: 1x1|2x3|3x5 -> AHO
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    # Hranatý zápis.
    if "[" in cleaned and "]" in cleaned:
        result = []
        index = 0

        while index < len(cleaned):
            char = cleaned[index]

            if char == "[":
                end = cleaned.find("]", index + 1)
                if end != -1:
                    token = cleaned[index + 1:end].strip()
                    normalized = normalize_text(token)
                    if len(normalized) == 1:
                        result.append(encrypt(normalized))
                        index = end + 1
                        continue

            result.append(char)
            index += 1

        return normalize_text("".join(result))

    # Souřadnicový zápis.
    tokens = (
        cleaned.replace(";", " ")
        .replace("|", " ")
        .replace("/", " ")
        .replace("x", ",")
        .replace("X", ",")
        .split()
    )

    if tokens and all("," in token for token in tokens):
        result = []
        for token in tokens:
            try:
                row_s, col_s = token.split(",", 1)
                row = int(row_s.strip())
                col = int(col_s.strip())
            except ValueError:
                result.append(f"[{token}]")
                continue

            result.append(COORDS_TO_LETTER.get((row, col), f"[{token}]"))

        return "".join(result)

    # Jinak vrátíme běžný normalizovaný text.
    return normalize_text(cleaned)


class PseudoCinaOutputWidget(QWidget):
    """Kreslený výstup šifry Pseudo-Čína."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(190)

    def set_scale(self, scale: float):
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        self.cipher_text = encrypt(text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        self.cipher_text = ""
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_content_size()

    def get_metrics(self):
        cell_w = max(40, int(58 * self.scale_value))
        cell_h = max(42, int(60 * self.scale_value))
        letter_gap = max(5, int(8 * self.scale_value))
        word_gap = max(22, int(34 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if char == " ":
            return word_gap

        if char in LETTER_TO_COORDS:
            return cell_w

        return max(22, int(30 * self.scale_value))

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, cell_h, letter_gap, _, line_gap = self.get_metrics()
        content_width = max(160, available_width - margin_left - margin_right)

        if not self.cipher_text:
            return max(170, cell_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for char in self.cipher_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            char_w = self.char_width(char)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w
            if char != " ":
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

        if not self.cipher_text:
            painter.setFont(QFont("Georgia", max(10, int(14 * self.scale_value))))
            painter.setPen(QColor("#a8a295"))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "Kreslený výsledek se objeví zde...")
            return

        cell_w, cell_h, letter_gap, _, line_gap = self.get_metrics()
        x = rect.left()
        y = rect.top()

        for char in self.cipher_text:
            if char == "\n":
                x = rect.left()
                y += cell_h + line_gap
                continue

            char_w = self.char_width(char)

            if x > rect.left() and x + char_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if char == " ":
                x += char_w
                continue

            if char in LETTER_TO_COORDS:
                self.draw_pseudo_cina_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def make_pen(self, color: QColor, width: float) -> QPen:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def draw_wobbly_line(self, painter: QPainter, p1: QPointF, p2: QPointF, line_w: float, seed: int):
        """Nakreslí lehce ručně vypadající čáru."""
        rng = random.Random(seed)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")
        shadow = QColor(0, 0, 0, 145)

        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = max(1.0, math.hypot(dx, dy))
        nx = -dy / length
        ny = dx / length

        points = []
        segments = 3
        wobble = max(0.8, line_w * 0.85)

        for i in range(segments + 1):
            t = i / segments
            base_x = p1.x() + dx * t
            base_y = p1.y() + dy * t
            offset = rng.uniform(-wobble, wobble)
            points.append(QPointF(base_x + nx * offset, base_y + ny * offset))

        def draw_polyline(color: QColor, width: float, shift_x: float = 0.0, shift_y: float = 0.0):
            painter.setPen(self.make_pen(color, width))
            for a, b in zip(points, points[1:]):
                painter.drawLine(
                    QPointF(a.x() + shift_x, a.y() + shift_y),
                    QPointF(b.x() + shift_x, b.y() + shift_y),
                )

        draw_polyline(shadow, line_w + 0.9, 0.9, 0.9)
        draw_polyline(gold, line_w)
        draw_polyline(gold_light, max(0.45, line_w * 0.22), -0.15, -0.15)

    def draw_pseudo_cina_letter(self, painter: QPainter, rect: QRectF, letter: str):
        row_count, col_count = LETTER_TO_COORDS[letter]

        line_w = max(1.15, rect.height() * 0.030)

        # Menší kresba uprostřed buňky.
        left = rect.left() + rect.width() * 0.14
        right = rect.right() - rect.width() * 0.14
        top = rect.top() + rect.height() * 0.16
        bottom = rect.bottom() - rect.height() * 0.16
        usable_w = right - left
        usable_h = bottom - top

        seed_base = ord(letter) * 7919

        # Vodorovné čáry: tolik, kolik je řádek.
        if row_count == 1:
            y_positions = [top + usable_h * 0.50]
        else:
            y_positions = [
                top + usable_h * (0.10 + i * 0.80 / max(1, row_count - 1))
                for i in range(row_count)
            ]

        for i, y in enumerate(y_positions):
            # Různě dlouhé čáry, aby to nepůsobilo jako strojová mřížka.
            start = left + usable_w * (0.02 + 0.05 * ((i + ord(letter)) % 3))
            end = right - usable_w * (0.02 + 0.05 * ((i + ord(letter) + 1) % 3))
            slant = usable_h * (0.04 * ((i % 3) - 1))
            self.draw_wobbly_line(
                painter,
                QPointF(start, y + slant),
                QPointF(end, y - slant),
                line_w,
                seed_base + 100 + i,
            )

        # Svislé čáry: tolik, kolik je sloupec.
        if col_count == 1:
            x_positions = [left + usable_w * 0.50]
        else:
            x_positions = [
                left + usable_w * (0.10 + i * 0.80 / max(1, col_count - 1))
                for i in range(col_count)
            ]

        for i, x in enumerate(x_positions):
            start = top + usable_h * (0.02 + 0.05 * ((i + ord(letter)) % 3))
            end = bottom - usable_h * (0.02 + 0.05 * ((i + ord(letter) + 2) % 3))
            slant = usable_w * (0.04 * (((i + 1) % 3) - 1))
            self.draw_wobbly_line(
                painter,
                QPointF(x + slant, start),
                QPointF(x - slant, end),
                line_w,
                seed_base + 200 + i,
            )

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(18, int(34 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


if __name__ == "__main__":
    sample = "abcdefghijklmnoprstuvwxyzq?"
    encrypted = encrypt(sample)
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypt("[A][B][C] 1,1 2,1 5,5"))
