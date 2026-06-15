# ============================================================
# Mříž - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Mříž\mriz.py
#
# KLÍČ:
#
#   A B C | D E | F G | H I
#   J K   | L M | N O | P Q
#   R S   | T U | V W | X Y Z
#
# OPRAVENÉ PRAVIDLO KRESLENÍ:
# - kreslí se přesně ta část mříže, ve které písmeno v klíči leží
# - horní řada má spodní vodorovnou linku
# - prostřední řada má horní i spodní vodorovnou linku
# - spodní řada má horní vodorovnou linku
# - první sloupcová oblast má pravou svislou linku
# - oblast DE/LM/TU má pravou dvojitou svislou linku
# - oblast FG/NO/VW má levou dvojitou svislou linku
# - ostatní svislé linky jsou jednoduché
# - tečka určuje přesnou pozici písmena v oblasti
#
# Symboly jako ?, . , - ! : ; / zůstávají symboly.
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget


GRID_ROWS = [
    ["ABC", "DE", "FG", "HI"],
    ["JK", "LM", "NO", "PQ"],
    ["RS", "TU", "VW", "XYZ"],
]

LETTER_INFO = {}
for row_index, row in enumerate(GRID_ROWS):
    for group_index, letters in enumerate(row):
        for pos_index, letter in enumerate(letters):
            LETTER_INFO[letter] = {
                "row": row_index,
                "group": group_index,
                "pos": pos_index,
                "count": len(letters),
            }


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Textové / interní dešifrování.

    Kreslený výstup nejde spolehlivě číst z obyčejného textu, proto podporuje:
    - běžný text: AHOJ? -> AHOJ?
    - hranatý zápis: [A][H][O][J]? -> AHOJ?
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

        result.append(char)
        index += 1

    return normalize_text("".join(result))


class MrizOutputWidget(QWidget):
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

    def get_metrics(self):
        # Menší a přesnější poměr než předchozí verze.
        # Cílem je, aby výstup vypadáním seděl na klíč i ukázku.
        cell_w = max(64, int(86 * self.scale_value))
        cell_h = max(46, int(62 * self.scale_value))
        letter_gap = max(5, int(8 * self.scale_value))
        word_gap = max(28, int(42 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if char == " ":
            return word_gap

        if char in LETTER_INFO:
            return cell_w

        return max(28, int(36 * self.scale_value))

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

            if char in LETTER_INFO:
                self.draw_mriz_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(18, int(32 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def make_pen(self, color: QColor, width: float) -> QPen:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.SquareCap)
        pen.setJoinStyle(Qt.MiterJoin)
        return pen

    def draw_line_with_shadow(self, painter: QPainter, p1: QPointF, p2: QPointF, line_w: float):
        shadow = QColor(0, 0, 0, 155)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        painter.setPen(self.make_pen(shadow, line_w + 1.4))
        painter.drawLine(p1 + QPointF(1.1, 1.1), p2 + QPointF(1.1, 1.1))

        painter.setPen(self.make_pen(gold, line_w))
        painter.drawLine(p1, p2)

        painter.setPen(self.make_pen(gold_light, max(0.6, line_w * 0.20)))
        painter.drawLine(p1, p2)

    def draw_double_vertical_line(self, painter: QPainter, x: float, top: float, bottom: float, line_w: float):
        """Nakreslí dvojitou svislou čáru jako ve vzoru / klíči.

        Používá se hlavně u středových oblastí, kde má být rámeček jasně
        ohraničený z obou stran. Dvě tenké čáry vedle sebe jsou čitelnější
        než jedna tlustá.
        """
        offset = max(3.0, line_w * 1.45)
        half = offset / 2

        self.draw_line_with_shadow(
            painter,
            QPointF(x - half, top),
            QPointF(x - half, bottom),
            line_w,
        )
        self.draw_line_with_shadow(
            painter,
            QPointF(x + half, top),
            QPointF(x + half, bottom),
            line_w,
        )

    def draw_mriz_letter(self, painter: QPainter, rect: QRectF, letter: str):
        info = LETTER_INFO[letter]
        row = info["row"]
        group = info["group"]
        pos = info["pos"]
        count = info["count"]

        # Souřadnice jedné oblasti mříže.
        left = rect.left() + rect.width() * 0.10
        right = rect.left() + rect.width() * 0.90
        top = rect.top() + rect.height() * 0.18
        bottom = rect.top() + rect.height() * 0.78
        center_y = (top + bottom) / 2

        line_w = max(2.6, rect.height() * 0.060)

        # ŘÁDKY:
        # horní řada => jen spodní linka
        # prostřední řada => horní i spodní linka
        # spodní řada => jen horní linka
        if row == 0:
            horizontal_lines = ["bottom"]
        elif row == 1:
            horizontal_lines = ["top", "bottom"]
        else:
            horizontal_lines = ["top"]

        # SLOUPCOVÉ OBLASTI:
        # první oblast => pravá linka
        # prostřední oblasti => levá i pravá linka
        # poslední oblast => levá linka
        if group == 0:
            vertical_lines = ["right"]
        elif group in (1, 2):
            vertical_lines = ["left", "right"]
        else:
            vertical_lines = ["left"]

        if "top" in horizontal_lines:
            self.draw_line_with_shadow(painter, QPointF(left, top), QPointF(right, top), line_w)
        if "bottom" in horizontal_lines:
            self.draw_line_with_shadow(painter, QPointF(left, bottom), QPointF(right, bottom), line_w)

        # Svislé čáry přesně podle klíče:
        #
        # ABC | DE || FG | HI
        # JK  | LM || NO | PQ
        # RS  | TU || VW | XYZ
        #
        # Dvojitá čára je jen mezi oblastmi DE a FG,
        # tedy:
        # - u skupiny DE / LM / TU je dvojitá pravá čára
        # - u skupiny FG / NO / VW je dvojitá levá čára
        # Ostatní svislé čáry jsou jednoduché.
        if "left" in vertical_lines:
            if group == 2:
                self.draw_double_vertical_line(painter, left, top, bottom, line_w)
            else:
                self.draw_line_with_shadow(painter, QPointF(left, top), QPointF(left, bottom), line_w)

        if "right" in vertical_lines:
            if group == 1:
                self.draw_double_vertical_line(painter, right, top, bottom, line_w)
            else:
                self.draw_line_with_shadow(painter, QPointF(right, top), QPointF(right, bottom), line_w)

        # Tečka přesně podle pořadí písmen v dané oblasti.
        if count == 1:
            dot_x = (left + right) / 2
        elif count == 2:
            dot_x = left + (right - left) * (0.28 if pos == 0 else 0.72)
        else:
            # A/B/C a X/Y/Z mají tři pozice.
            dot_x = left + (right - left) * [0.14, 0.50, 0.86][pos]

        if row == 0:
            dot_y = top + (bottom - top) * 0.54
        elif row == 1:
            dot_y = center_y
        else:
            dot_y = top + (bottom - top) * 0.46

        self.draw_dot(painter, QPointF(dot_x, dot_y), max(4.0, rect.height() * 0.076))

    def draw_dot(self, painter: QPainter, center: QPointF, radius: float):
        shadow = QColor(0, 0, 0, 165)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        painter.setPen(Qt.NoPen)

        painter.setBrush(QBrush(shadow))
        painter.drawEllipse(center + QPointF(1.1, 1.1), radius, radius)

        painter.setBrush(QBrush(gold))
        painter.drawEllipse(center, radius, radius)

        painter.setBrush(QBrush(gold_light))
        painter.drawEllipse(
            QPointF(center.x() - radius * 0.28, center.y() - radius * 0.28),
            radius * 0.26,
            radius * 0.26,
        )


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypt(sample))
    print("Dešifrování:", decrypt("[A][H][O][J] [J][A][K]"))
