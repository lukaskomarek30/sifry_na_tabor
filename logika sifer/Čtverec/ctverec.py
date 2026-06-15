# ============================================================
# Čtverec - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Čtverec\ctverec.py
#
# Klíč:
#
# A B C D E
# F G H I J
# K L M N O
# P Q R S T
# U V X Y Z
#
# W se zapisuje jako V.
# Symboly jako ?, . , - ! : ; / zůstávají jako symboly.
#
# Soubor obsahuje:
# - encrypt(text)
# - decrypt(text)
# - CtverecOutputWidget pro kreslený výstup
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget


SQUARE_POSITIONS = {
    "A": (0, 0), "B": (1, 0), "C": (2, 0), "D": (3, 0), "E": (4, 0),
    "F": (0, 1), "G": (1, 1), "H": (2, 1), "I": (3, 1), "J": (4, 1),
    "K": (0, 2), "L": (1, 2), "M": (2, 2), "N": (3, 2), "O": (4, 2),
    "P": (0, 3), "Q": (1, 3), "R": (2, 3), "S": (3, 3), "T": (4, 3),
    "U": (0, 4), "V": (1, 4), "X": (2, 4), "Y": (3, 4), "Z": (4, 4),
}

REVERSE_SQUARE_POSITIONS = {value: key for key, value in SQUARE_POSITIONS.items()}


def normalize_text(text: str) -> str:
    """Převede diakritiku pryč, text na velká písmena a W jako V."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.upper()
    normalized = normalized.replace("W", "V")
    return normalized


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Čtverec."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Dešifrování pro textový / interní zápis.

    Podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - W se převede na V
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
    - souřadnicový zápis: (0,0)(2,1)(4,2)(4,1)? -> AHOJ?
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
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    pos = (int(parts[0]), int(parts[1]))
                    decoded = REVERSE_SQUARE_POSITIONS.get(pos)
                    if decoded is not None:
                        result.append(decoded)
                        index = end + 1
                        continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))


class CtverecOutputWidget(QWidget):
    """Kreslený výstup šifry Čtverec.

    Důležitá oprava:
    Značka už není počítaná jednoduše jako 5 bodů přes celou buňku.
    Počítá se podle skutečné polohy vůči malému čtverci:
    - řádek/sloupec 0 je venku vlevo/nahoře,
    - řádek/sloupec 1 je uvnitř u levé/horní hrany,
    - řádek/sloupec 2 je uprostřed,
    - řádek/sloupec 3 je uvnitř u pravé/spodní hrany,
    - řádek/sloupec 4 je venku vpravo/dole.
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
        cell_w = max(32, int(46 * self.scale_value))
        cell_h = max(32, int(46 * self.scale_value))
        letter_gap = max(7, int(10 * self.scale_value))
        word_gap = max(20, int(32 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, _, _ = self.get_cell_metrics()

        if char in SQUARE_POSITIONS:
            return cell_w

        return max(18, int(24 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 12
        margin_right = 12
        margin_top = 8
        margin_bottom = 16

        content_width = max(120, available_width - margin_left - margin_right)
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

        width = max(250, width)
        needed_height = self.calculate_required_height(width)

        self.setMinimumSize(width, needed_height)
        if self.width() != width or self.height() != needed_height:
            self.resize(width, needed_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = self.rect().adjusted(12, 8, -12, -8)

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

            if char in SQUARE_POSITIONS:
                self.draw_cipher_symbol(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(14, int(24 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def marker_center_from_position(self, square: QRectF, marker_size: float, col: int, row: int) -> QPointF:
        """Vrátí střed značky pro souřadnici 5×5 podle klíče."""
        x_positions = [
            square.left() - marker_size * 0.55,
            square.left() + marker_size * 0.55,
            square.center().x(),
            square.right() - marker_size * 0.55,
            square.right() + marker_size * 0.55,
        ]

        y_positions = [
            square.top() - marker_size * 0.55,
            square.top() + marker_size * 0.55,
            square.center().y(),
            square.bottom() - marker_size * 0.55,
            square.bottom() + marker_size * 0.55,
        ]

        return QPointF(x_positions[col], y_positions[row])

    def draw_cipher_symbol(self, painter: QPainter, rect: QRectF, letter: str):
        col, row = SQUARE_POSITIONS[letter]

        shadow = QColor(0, 0, 0, 165)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        # Malý čtverec uprostřed symbolu.
        # Tohle je blíž k tvému referenčnímu výstupu.
        square_size = min(rect.width(), rect.height()) * 0.48
        square = QRectF(
            rect.center().x() - square_size / 2,
            rect.center().y() - square_size / 2 + rect.height() * 0.03,
            square_size,
            square_size,
        )

        line_w = max(1.2, rect.height() * 0.045)

        # Stín.
        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w)
        painter.setPen(shadow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(square.translated(1.2, 1.2))

        # Hlavní obrys čtverce.
        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        painter.setPen(main_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(square)

        # Jemné světlo.
        inner_pen = QPen(gold_light)
        inner_pen.setWidthF(max(0.6, rect.height() * 0.018))
        painter.setPen(inner_pen)
        painter.drawRect(square.adjusted(1.2, 1.2, -1.2, -1.2))

        # Malá vyplněná značka.
        marker_size = max(4.0, square_size * 0.30)
        marker_center = self.marker_center_from_position(square, marker_size, col, row)

        marker = QRectF(
            marker_center.x() - marker_size / 2,
            marker_center.y() - marker_size / 2,
            marker_size,
            marker_size,
        )

        # Stín značky.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawRect(marker.translated(1.1, 1.1))

        # Značka.
        painter.setBrush(QBrush(gold))
        painter.drawRect(marker)

        # Malé zvýraznění značky.
        highlight_size = marker_size * 0.35
        painter.setBrush(QBrush(gold_light))
        painter.drawRect(
            QRectF(
                marker.left(),
                marker.top(),
                highlight_size,
                highlight_size,
            )
        )


if __name__ == "__main__":
    sample = "ahoj jak se máš ? v w n"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
