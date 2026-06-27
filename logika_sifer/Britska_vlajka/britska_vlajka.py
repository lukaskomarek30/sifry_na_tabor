"""Implementace šifry Britská vlajka pro Šifrátor Mraveniště.

Modul obsahuje textovou logiku šifry a Qt widget pro grafické vykreslení
výsledku pomocí QPainteru. Každé písmeno je reprezentované sadou čar,
které se kreslí podle předdefinovaných segmentů v rámci jedné buňky.

Umístění v projektu:
    logika sifer/Britská vlajka/britska_vlajka.py

Hlavní části modulu:
- normalize_text(text) připraví text pro interní zpracování,
- encrypt(text) převede vstup do normalizovaného tvaru pro kreslení,
- decrypt(text) zpracuje interní textový zápis zpět do normalizovaného textu,
- BritishFlagOutputWidget vykresluje šifru do responzivního Qt widgetu.

Widget je navržený pro vložení do QScrollArea. Při delším výsledku si
automaticky přepočítá potřebnou výšku, aby bylo možné výstup plynule posouvat.
"""

# Unicode normalizace se používá pro odstranění diakritiky před šifrováním.
import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


def normalize_text(text: str) -> str:
    """Normalizuje vstupní text na velká písmena bez diakritiky.

    Šifra pracuje s mapováním A–Z, proto se před vykreslením odstraní
    diakritika a text se převede na jednotný velký tvar.
    """
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Vrátí normalizovaný text určený pro vykreslení šifry Britská vlajka."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Převede textový nebo interní zápis zpět do normalizovaného textu.

    Funkce podporuje i jednoduchý tokenový zápis ve tvaru [A], který se může
    objevit při interní práci s jednotlivými znaky.
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


# Normalizované segmenty jedné kreslicí buňky.
# Souřadnice jsou uvedené relativně v rozsahu 0–1, aby bylo možné buňku libovolně škálovat.
SEGMENTS = {
    "top": ((0.12, 0.16), (0.88, 0.16)),
    "mid": ((0.12, 0.50), (0.88, 0.50)),
    "bot": ((0.12, 0.84), (0.88, 0.84)),
    "left": ((0.12, 0.16), (0.12, 0.84)),
    "right": ((0.88, 0.16), (0.88, 0.84)),
    "center": ((0.50, 0.16), (0.50, 0.84)),

    "diag_down": ((0.12, 0.16), (0.88, 0.84)),
    "diag_up": ((0.12, 0.84), (0.88, 0.16)),

    "tl_c": ((0.12, 0.16), (0.50, 0.50)),
    "c_br": ((0.50, 0.50), (0.88, 0.84)),
    "bl_c": ((0.12, 0.84), (0.50, 0.50)),
    "c_tr": ((0.50, 0.50), (0.88, 0.16)),

    "t_c": ((0.50, 0.16), (0.50, 0.50)),
    "c_b": ((0.50, 0.50), (0.50, 0.84)),
    "l_c": ((0.12, 0.50), (0.50, 0.50)),
    "c_r": ((0.50, 0.50), (0.88, 0.50)),
}


# Mapování písmen na segmenty podle grafického klíče šifry.
# Normalizované segmenty jedné kreslicí buňky.
# Souřadnice jsou uvedené relativně v rozsahu 0–1, aby bylo možné buňku libovolně škálovat.
LETTER_SEGMENTS = {
    "A": ["diag_down", "diag_up", "mid"],
    "B": ["top", "mid", "bot", "left", "right", "tl_c"],
    "C": ["diag_down", "diag_up", "center", "c_r"],
    "D": ["top", "mid", "bot", "right", "center"],
    "E": ["diag_down", "diag_up", "center"],
    "F": ["diag_down", "diag_up", "top", "right"],
    "G": ["diag_down", "diag_up", "l_c", "t_c"],
    "H": ["top", "mid", "bot", "diag_down", "diag_up"],
    "I": ["top", "bot", "left", "right", "diag_down", "diag_up"],
    "J": ["top", "tl_c", "bl_c", "c_r"],
    "K": ["top", "mid", "bot", "left", "right"],
    "L": ["top", "right", "diag_down", "diag_up"],
    "M": ["top", "mid", "bot", "center"],
    "N": ["top", "mid", "bot", "center", "l_c"],
    "O": ["diag_down", "diag_up", "l_c", "c_r"],
    "P": ["top", "right", "bot", "diag_down", "diag_up"],
    "Q": ["diag_down", "diag_up", "c_r"],
    "R": ["top", "left", "bot", "bl_c", "c_tr"],
    "S": ["diag_down", "diag_up", "l_c", "c_r"],
    "T": ["top", "bot", "diag_down", "diag_up"],
    "U": ["top", "mid", "bot", "center", "diag_down", "diag_up"],
    "V": ["top", "right", "bot", "diag_down"],
    "W": ["top", "mid", "bot", "center"],
    "X": ["top", "mid", "bot", "left", "right"],
    "Y": ["top", "bot", "left", "right", "diag_down", "diag_up"],
    "Z": ["left", "right", "tl_c", "c_br", "bl_c", "c_tr"],
}


class BritishFlagOutputWidget(QWidget):
    """Qt widget pro vykreslení šifry Britská vlajka.

    Widget je určený pro použití uvnitř QScrollArea. Na základě aktuální
    šířky a délky textu si automaticky dopočítává minimální výšku, aby se
    dlouhý výstup neztrácel mimo viditelnou oblast.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(180)

    def set_scale(self, scale: float):
        """Nastaví měřítko vykreslení a přepočítá velikost obsahu."""
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        """Nastaví text pro vykreslení a aktualizuje rozměry widgetu."""
        self.cipher_text = normalize_text(text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        """Vymaže aktuální obsah widgetu."""
        self.cipher_text = ""
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_content_size()

    def get_cell_metrics(self):
        """Vrátí rozměry buňky a mezery odvozené od aktuálního měřítka."""
        cell_w = max(34, int(58 * self.scale_value))
        cell_h = max(24, int(40 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(18, int(30 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        """Vrátí šířku potřebnou pro vykreslení jednoho znaku."""
        cell_w, _, _, _, _ = self.get_cell_metrics()

        if char in LETTER_SEGMENTS:
            return cell_w

        return max(18, int(24 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        """Spočítá potřebnou výšku widgetu podle dostupné šířky a délky textu."""
        margin_left = 12
        margin_right = 12
        margin_top = 8
        margin_bottom = 16

        content_width = max(120, available_width - margin_left - margin_right)
        cell_w, cell_h, letter_gap, word_gap, line_gap = self.get_cell_metrics()

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
        """Aktualizuje minimální velikost widgetu podle aktuálního obsahu a šířky viewportu."""
        parent = self.parentWidget()
        width = self.width()

        # Při vložení do QScrollArea je parent typicky viewport, jehož šířka určuje reálný kreslicí prostor.
        if parent is not None and parent.width() > 20:
            width = parent.width()

        width = max(250, width)
        needed_height = self.calculate_required_height(width)

        self.setMinimumSize(width, needed_height)
        if self.width() != width or self.height() != needed_height:
            self.resize(width, needed_height)

    def paintEvent(self, event):
        """Vykreslí celý zašifrovaný text do aktuální plochy widgetu."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

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

            # Kreslení pokračuje i mimo původní viditelnou oblast; posun zajišťuje nadřazená QScrollArea.

            if char in LETTER_SEGMENTS:
                self.draw_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Vykreslí znak, který není definovaný v mapě segmentů."""
        font = QFont("Georgia", max(14, int(24 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def draw_letter(self, painter: QPainter, rect: QRectF, letter: str):
        """Vykreslí jedno písmeno jako sadu čar podle segmentové mapy."""
        shadow_pen = QPen(QColor(0, 0, 0, 150))
        shadow_pen.setWidthF(max(1.3, rect.height() * 0.075))
        shadow_pen.setCapStyle(Qt.RoundCap)
        shadow_pen.setJoinStyle(Qt.RoundJoin)

        main_pen = QPen(QColor("#f3d79a"))
        main_pen.setWidthF(max(1.4, rect.height() * 0.060))
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)

        inner_pen = QPen(QColor("#fff0bd"))
        inner_pen.setWidthF(max(0.8, rect.height() * 0.025))
        inner_pen.setCapStyle(Qt.RoundCap)
        inner_pen.setJoinStyle(Qt.RoundJoin)

        segments = LETTER_SEGMENTS.get(letter, [])

        # Písmeno se kreslí ve třech vrstvách: stín, hlavní čára a světlý vnitřní tah.
        for pen, offset in (
            (shadow_pen, QPointF(1.4, 1.4)),
            (main_pen, QPointF(0, 0)),
            (inner_pen, QPointF(0, 0)),
        ):
            painter.setPen(pen)

            for segment_name in segments:
                start, end = SEGMENTS[segment_name]
                p1 = QPointF(
                    rect.left() + start[0] * rect.width(),
                    rect.top() + start[1] * rect.height(),
                ) + offset
                p2 = QPointF(
                    rect.left() + end[0] * rect.width(),
                    rect.top() + end[1] * rect.height(),
                ) + offset
                painter.drawLine(p1, p2)

        # Středový uzel vizuálně sjednocuje jednotlivé segmenty písmene.
        node_size = max(3.0, rect.height() * 0.10)
        center = QPointF(
            rect.left() + 0.5 * rect.width(),
            rect.top() + 0.5 * rect.height(),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#f3d79a"))
        painter.drawEllipse(center, node_size, node_size)
