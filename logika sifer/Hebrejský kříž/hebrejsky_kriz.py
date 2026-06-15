# ============================================================
# Hebrejský kříž - logika + větší kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Hebrejský kříž\hebrejsky_kriz.py
#
# Klíč podle obrázku:
#
# 1. mřížka bez tečky:
# A B C
# D E F
# G H Ch
#
# CH se zde NEPOUŽÍVÁ jako jeden znak.
# Pokud napíšeš "ch", zašifruje se jako C + H.
#
# 2. mřížka s jednou tečkou:
# I J K
# L M N
# O P Q
#
# 3. mřížka se dvěma tečkami:
# R S T
# U V W
# X Y Z
#
# Symboly jako ?, . , - ! : ; / zůstávají symboly.
#
# Soubor obsahuje:
# - encrypt(text)
# - decrypt(text)
# - HebrejskyKrizOutputWidget pro kreslený výstup
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget


# Mapování: písmeno -> (sloupec, řádek, počet teček)
# sloupec/řádek je v mřížce 3×3.
# Pozice Ch v první mřížce se nepoužívá.
HEBREW_CROSS_MAP = {
    "A": (0, 0, 0),
    "B": (1, 0, 0),
    "C": (2, 0, 0),
    "D": (0, 1, 0),
    "E": (1, 1, 0),
    "F": (2, 1, 0),
    "G": (0, 2, 0),
    "H": (1, 2, 0),

    "I": (0, 0, 1),
    "J": (1, 0, 1),
    "K": (2, 0, 1),
    "L": (0, 1, 1),
    "M": (1, 1, 1),
    "N": (2, 1, 1),
    "O": (0, 2, 1),
    "P": (1, 2, 1),
    "Q": (2, 2, 1),

    "R": (0, 0, 2),
    "S": (1, 0, 2),
    "T": (2, 0, 2),
    "U": (0, 1, 2),
    "V": (1, 1, 2),
    "W": (2, 1, 2),
    "X": (0, 2, 2),
    "Y": (1, 2, 2),
    "Z": (2, 2, 2),
}

REVERSE_HEBREW_CROSS_MAP = {value: key for key, value in HEBREW_CROSS_MAP.items()}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Hebrejský kříž."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Dešifrování pro textový / interní zápis.

    Protože kreslený výstup není obyčejný text, podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
    - souřadnicový zápis: (0,0,0)(1,2,0)(0,2,1)(1,0,1)? -> AHOJ?
      formát je (sloupec,řádek,počet_teček)
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
                parts = [part.strip() for part in token.split(",")]
                if len(parts) == 3 and all(part.isdigit() for part in parts):
                    key = (int(parts[0]), int(parts[1]), int(parts[2]))
                    decoded = REVERSE_HEBREW_CROSS_MAP.get(key)
                    if decoded is not None:
                        result.append(decoded)
                        index = end + 1
                        continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))


class HebrejskyKrizOutputWidget(QWidget):
    """Kreslený výstup šifry Hebrejský kříž.

    Tato verze kreslí symboly větší a do pevné mřížky, aby nebyly malé
    ani rozházené. Widget je určený do QScrollArea.
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
        # Větší buňka = čitelnější symbol.
        cell_w = max(54, int(74 * self.scale_value))
        cell_h = max(48, int(66 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(18, int(26 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, _, _ = self.get_cell_metrics()

        if char in HEBREW_CROSS_MAP:
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

            if char in HEBREW_CROSS_MAP:
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
        col, row, dot_count = HEBREW_CROSS_MAP[letter]

        shadow = QColor(0, 0, 0, 170)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        # Vykreslíme přímo velký "tvar buňky", ne malý kousek z celé 3×3 mřížky.
        # Tím symbol není mikroskopický a působí jako v klíči.
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

        # Pigpen princip:
        # col 0 => kreslí se pravá stěna, col 1 => levá i pravá, col 2 => levá.
        # row 0 => kreslí se spodní stěna, row 1 => horní i spodní, row 2 => horní.
        if col > 0:
            lines.append((QPointF(left, top), QPointF(left, bottom)))
        if col < 2:
            lines.append((QPointF(right, top), QPointF(right, bottom)))
        if row > 0:
            lines.append((QPointF(left, top), QPointF(right, top)))
        if row < 2:
            lines.append((QPointF(left, bottom), QPointF(right, bottom)))

        line_w = max(2.8, rect.height() * 0.075)

        # Stín.
        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w)
        shadow_pen.setCapStyle(Qt.SquareCap)
        shadow_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(shadow_pen)

        for p1, p2 in lines:
            painter.drawLine(p1 + QPointF(1.4, 1.4), p2 + QPointF(1.4, 1.4))

        # Hlavní zlaté čáry.
        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        main_pen.setCapStyle(Qt.SquareCap)
        main_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(main_pen)

        for p1, p2 in lines:
            painter.drawLine(p1, p2)

        # Jemné světlo.
        inner_pen = QPen(gold_light)
        inner_pen.setWidthF(max(0.9, rect.height() * 0.022))
        inner_pen.setCapStyle(Qt.SquareCap)
        inner_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(inner_pen)

        for p1, p2 in lines:
            painter.drawLine(p1, p2)

        if dot_count > 0:
            self.draw_dots(painter, glyph, dot_count)

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
    sample = "ahok jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
