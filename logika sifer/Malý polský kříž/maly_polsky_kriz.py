# ============================================================
# Malý polský kříž - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Malý polský kříž\maly_polsky_kriz.py
#
# Klíč podle obrázku:
#
# 1) Mřížka bez tečky:
# A B C
# D E F
# G H I
#
# 2) Mřížka s jednou tečkou:
# J K L
# M N O
# P Q R
#
# 3) Kříž X bez tečky:
#     S
#   T   U
#     V
#
# 4) Kříž X s jednou tečkou:
#     W
#   X   Y
#     Z
#
# Symboly jako ?, . , - ! : ; / zůstávají symboly.
#
# Soubor obsahuje:
# - encrypt(text)
# - decrypt(text)
# - MalyPolskyKrizOutputWidget pro kreslený výstup
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget


# Písmena v mřížce 3×3:
# hodnota = ("grid", sloupec, řádek, počet_teček)
GRID_MAP = {
    "A": ("grid", 0, 0, 0),
    "B": ("grid", 1, 0, 0),
    "C": ("grid", 2, 0, 0),
    "D": ("grid", 0, 1, 0),
    "E": ("grid", 1, 1, 0),
    "F": ("grid", 2, 1, 0),
    "G": ("grid", 0, 2, 0),
    "H": ("grid", 1, 2, 0),
    "I": ("grid", 2, 2, 0),

    "J": ("grid", 0, 0, 1),
    "K": ("grid", 1, 0, 1),
    "L": ("grid", 2, 0, 1),
    "M": ("grid", 0, 1, 1),
    "N": ("grid", 1, 1, 1),
    "O": ("grid", 2, 1, 1),
    "P": ("grid", 0, 2, 1),
    "Q": ("grid", 1, 2, 1),
    "R": ("grid", 2, 2, 1),
}

# Písmena v kříži X:
# hodnota = ("x", pozice, počet_teček)
# pozice: top, left, right, bottom
X_MAP = {
    "S": ("x", "top", 0),
    "T": ("x", "left", 0),
    "U": ("x", "right", 0),
    "V": ("x", "bottom", 0),

    "W": ("x", "top", 1),
    "X": ("x", "left", 1),
    "Y": ("x", "right", 1),
    "Z": ("x", "bottom", 1),
}

SMALL_POLISH_CROSS_MAP = {}
SMALL_POLISH_CROSS_MAP.update(GRID_MAP)
SMALL_POLISH_CROSS_MAP.update(X_MAP)

REVERSE_GRID_MAP = {
    (col, row, dots): letter
    for letter, (_, col, row, dots) in GRID_MAP.items()
}

REVERSE_X_MAP = {
    (position, dots): letter
    for letter, (_, position, dots) in X_MAP.items()
}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Malý polský kříž."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Dešifrování pro textový / interní zápis.

    Protože kreslený výstup není obyčejný text, podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
    - mřížkový zápis: (grid,0,0,0)(grid,1,2,0) -> AH
      formát je (grid,sloupec,řádek,počet_teček)
    - X zápis: (x,top,0)(x,left,1) -> SX
      formát je (x,pozice,počet_teček)
    """
    cleaned = text.strip()

    if not cleaned:
        return ""

    result = []
    index = 0

    while index < len(cleaned):
        char = cleaned[index]

        if char == "[":
            end = cleaned.find("]", index + 1)
            if end != -1:
                token = cleaned[index + 1:end].strip()
                if len(token) == 1:
                    result.append(normalize_text(token))
                    index = end + 1
                    continue

        if char == "(":
            end = cleaned.find(")", index + 1)
            if end != -1:
                token = cleaned[index + 1:end].strip()
                parts = [part.strip().lower() for part in token.split(",")]

                if len(parts) == 4 and parts[0] == "grid":
                    if parts[1].isdigit() and parts[2].isdigit() and parts[3].isdigit():
                        decoded = REVERSE_GRID_MAP.get(
                            (int(parts[1]), int(parts[2]), int(parts[3]))
                        )
                        if decoded is not None:
                            result.append(decoded)
                            index = end + 1
                            continue

                if len(parts) == 3 and parts[0] == "x":
                    position = parts[1]
                    if parts[2].isdigit():
                        decoded = REVERSE_X_MAP.get((position, int(parts[2])))
                        if decoded is not None:
                            result.append(decoded)
                            index = end + 1
                            continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))


class MalyPolskyKrizOutputWidget(QWidget):
    """Kreslený výstup šifry Malý polský kříž.

    Widget je určený do QScrollArea.
    Když je výsledek delší než viditelný rámeček, automaticky zvětší výšku.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(180)

    def set_scale(self, scale: float):
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        self.cipher_text = normalize_text(text)
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

    def get_cell_metrics(self):
        # Větší a čitelnější symboly.
        cell_w = max(54, int(74 * self.scale_value))
        cell_h = max(48, int(66 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(18, int(26 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, _, _ = self.get_cell_metrics()

        if char in SMALL_POLISH_CROSS_MAP:
            return cell_w

        return max(22, int(28 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        content_width = max(160, available_width - margin_left - margin_right)
        _, cell_h, letter_gap, word_gap, line_gap = self.get_cell_metrics()

        if not self.cipher_text:
            return max(170, cell_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for char in self.cipher_text:
            if char == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            char_w = self.char_width(char)

            if x > 0 and x + char_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += char_w + letter_gap

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

        cell_w, cell_h, letter_gap, word_gap, line_gap = self.get_cell_metrics()

        x = rect.left()
        y = rect.top()

        for char in self.cipher_text:
            if char == "\n":
                x = rect.left()
                y += cell_h + line_gap
                continue

            if char == " ":
                x += word_gap
                continue

            char_w = self.char_width(char)

            if x > rect.left() and x + char_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if char in SMALL_POLISH_CROSS_MAP:
                self.draw_cipher_symbol(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(16, int(28 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def draw_cipher_symbol(self, painter: QPainter, rect: QRectF, letter: str):
        data = SMALL_POLISH_CROSS_MAP[letter]

        if data[0] == "grid":
            _, col, row, dot_count = data
            self.draw_grid_symbol(painter, rect, col, row, dot_count)
            return

        if data[0] == "x":
            _, position, dot_count = data
            self.draw_x_symbol(painter, rect, position, dot_count)

    def draw_grid_symbol(self, painter: QPainter, rect: QRectF, col: int, row: int, dot_count: int):
        shadow = QColor(0, 0, 0, 170)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        glyph = rect.adjusted(
            rect.width() * 0.18,
            rect.height() * 0.18,
            -rect.width() * 0.18,
            -rect.height() * 0.18,
        )

        left = glyph.left()
        right = glyph.right()
        top = glyph.top()
        bottom = glyph.bottom()

        lines = []

        # Pigpen mřížka:
        # col 0 => pravá stěna, col 1 => levá i pravá, col 2 => levá
        # row 0 => spodní stěna, row 1 => horní i spodní, row 2 => horní
        if col > 0:
            lines.append((QPointF(left, top), QPointF(left, bottom)))
        if col < 2:
            lines.append((QPointF(right, top), QPointF(right, bottom)))
        if row > 0:
            lines.append((QPointF(left, top), QPointF(right, top)))
        if row < 2:
            lines.append((QPointF(left, bottom), QPointF(right, bottom)))

        self.draw_lines(painter, lines, rect.height(), shadow, gold, gold_light)

        if dot_count > 0:
            self.draw_dots(painter, glyph, dot_count)

    def draw_x_symbol(self, painter: QPainter, rect: QRectF, position: str, dot_count: int):
        shadow = QColor(0, 0, 0, 170)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        glyph = rect.adjusted(
            rect.width() * 0.14,
            rect.height() * 0.14,
            -rect.width() * 0.14,
            -rect.height() * 0.14,
        )

        center = glyph.center()

        top_left = QPointF(glyph.left(), glyph.top())
        top_right = QPointF(glyph.right(), glyph.top())
        bottom_left = QPointF(glyph.left(), glyph.bottom())
        bottom_right = QPointF(glyph.right(), glyph.bottom())

        # Kreslí se dvě stěny konkrétní výseče X.
        if position == "top":
            lines = [(center, top_left), (center, top_right)]
        elif position == "left":
            lines = [(center, top_left), (center, bottom_left)]
        elif position == "right":
            lines = [(center, top_right), (center, bottom_right)]
        else:  # bottom
            lines = [(center, bottom_left), (center, bottom_right)]

        self.draw_lines(painter, lines, rect.height(), shadow, gold, gold_light)

        if dot_count > 0:
            self.draw_dots(painter, glyph, dot_count)

    def draw_lines(self, painter: QPainter, lines, base_height: float, shadow: QColor, gold: QColor, gold_light: QColor):
        line_w = max(2.8, base_height * 0.075)

        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w)
        shadow_pen.setCapStyle(Qt.SquareCap)
        shadow_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(shadow_pen)

        for p1, p2 in lines:
            painter.drawLine(p1 + QPointF(1.4, 1.4), p2 + QPointF(1.4, 1.4))

        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        main_pen.setCapStyle(Qt.SquareCap)
        main_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(main_pen)

        for p1, p2 in lines:
            painter.drawLine(p1, p2)

        inner_pen = QPen(gold_light)
        inner_pen.setWidthF(max(0.9, base_height * 0.022))
        inner_pen.setCapStyle(Qt.SquareCap)
        inner_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(inner_pen)

        for p1, p2 in lines:
            painter.drawLine(p1, p2)

    def draw_dots(self, painter: QPainter, glyph: QRectF, dot_count: int):
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")
        shadow = QColor(0, 0, 0, 170)

        dot_radius = max(3.8, glyph.height() * 0.095)
        center = glyph.center()

        if dot_count == 1:
            positions = [center]
        else:
            offset = dot_radius * 1.65
            positions = [
                QPointF(center.x() - offset, center.y()),
                QPointF(center.x() + offset, center.y()),
            ]

        painter.setPen(Qt.NoPen)

        for point in positions:
            painter.setBrush(QBrush(shadow))
            painter.drawEllipse(point + QPointF(1.2, 1.2), dot_radius, dot_radius)

            painter.setBrush(QBrush(gold))
            painter.drawEllipse(point, dot_radius, dot_radius)

            painter.setBrush(QBrush(gold_light))
            painter.drawEllipse(
                QPointF(point.x() - dot_radius * 0.28, point.y() - dot_radius * 0.28),
                dot_radius * 0.35,
                dot_radius * 0.35,
            )


if __name__ == "__main__":
    sample = "ahoj jak se mas? stuvwxyz"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
