"""Implementace šifry Moonovo písmo pro Šifrátor Mraveniště.

Modul obsahuje logiku pro šifrování, dešifrování a případnou přípravu dat
pro grafický klíč šifry. Kód je navržený tak, aby šel používat samostatně
i jako součást hlavní aplikace.
Součástí modulu je také Qt widget pro kreslené vykreslení výsledku v hlavním aplikačním rozhraní.

Základní pravidla implementace:
- vstupní text se před zpracováním normalizuje podle potřeb konkrétní šifry,
- běžné mezery, interpunkce a nepodporované symboly se zachovávají tam,
  kde to dává pro danou šifru smysl,
- veřejné funkce encrypt() a decrypt() tvoří stabilní rozhraní pro main.py,
- pomocné funkce jsou oddělené od UI vrstvy, aby se logika dala snadno testovat.
"""

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import QWidget


MOON_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Moonovo písmo."""
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Dešifrování pro textový / interní zápis.

    Kreslený výstup není obyčejný text, proto podporuje:
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



# Grafická vrstva pro vykreslení výsledku v Qt rozhraní.
class MoonovoPismoOutputWidget(QWidget):
    """Kreslený výstup šifry Moonovo písmo.

    Widget je určený do QScrollArea.
    Když je výsledek delší než viditelný rámeček, automaticky zvětší výšku.
    """

    def __init__(self, parent=None):
        """Pomocná funkce používaná interní logikou šifry."""
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(180)

    def set_scale(self, scale: float):
        """Nastaví měřítko vykreslení a aktualizuje rozměry widgetu."""
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        """Nastaví text určený pro vykreslení a obnoví obsah widgetu."""
        self.cipher_text = normalize_text(text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        """Vymaže aktuální obsah widgetu a obnoví jeho vykreslení."""
        self.cipher_text = ""
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        """Reaguje na změnu velikosti widgetu a přepočítá rozložení obsahu."""
        super().resizeEvent(event)
        self.update_content_size()

    def get_cell_metrics(self):
        """Vrátí rozměrové parametry buňky odvozené od aktuálního měřítka."""
        cell_w = max(52, int(70 * self.scale_value))
        cell_h = max(50, int(68 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(18, int(28 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        """Vrátí šířku potřebnou pro vykreslení jednoho znaku."""
        cell_w, _, _, _, _ = self.get_cell_metrics()

        if char in MOON_LETTERS:
            return cell_w

        return max(22, int(28 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        """Spočítá minimální výšku potřebnou pro zobrazení celého obsahu."""
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
        """Aktualizuje minimální velikost widgetu podle aktuálního obsahu."""
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
        """Vykreslí aktuální obsah widgetu pomocí QPainteru."""
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

            if char in MOON_LETTERS:
                self.draw_moon_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Pomocná funkce používaná interní logikou šifry."""
        font = QFont("Georgia", max(16, int(28 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def p(self, rect: QRectF, x: float, y: float) -> QPointF:
        """Pomocná funkce používaná interní logikou šifry."""
        return QPointF(rect.left() + rect.width() * x, rect.top() + rect.height() * y)

    def draw_path(self, painter: QPainter, path: QPainterPath, rect: QRectF):
        """Pomocná funkce používaná interní logikou šifry."""
        shadow = QColor(0, 0, 0, 175)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")

        line_w = max(4.0, rect.height() * 0.095)

        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w)
        shadow_pen.setCapStyle(Qt.RoundCap)
        shadow_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(shadow_pen)
        painter.drawPath(path.translated(1.5, 1.5))

        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(main_pen)
        painter.drawPath(path)

        inner_pen = QPen(gold_light)
        inner_pen.setWidthF(max(1.0, rect.height() * 0.025))
        inner_pen.setCapStyle(Qt.RoundCap)
        inner_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(inner_pen)
        painter.drawPath(path)

    def draw_lines(self, painter: QPainter, rect: QRectF, lines):
        """Pomocná funkce používaná interní logikou šifry."""
        path = QPainterPath()

        for start, end in lines:
            p1 = self.p(rect, *start)
            p2 = self.p(rect, *end)
            path.moveTo(p1)
            path.lineTo(p2)

        self.draw_path(painter, path, rect)

    def draw_curve_path(self, painter: QPainter, rect: QRectF, commands):
        """Pomocná funkce používaná interní logikou šifry."""
        path = QPainterPath()

        for cmd in commands:
            if cmd[0] == "M":
                path.moveTo(self.p(rect, cmd[1], cmd[2]))
            elif cmd[0] == "L":
                path.lineTo(self.p(rect, cmd[1], cmd[2]))
            elif cmd[0] == "Q":
                path.quadTo(self.p(rect, cmd[1], cmd[2]), self.p(rect, cmd[3], cmd[4]))
            elif cmd[0] == "C":
                path.cubicTo(
                    self.p(rect, cmd[1], cmd[2]),
                    self.p(rect, cmd[3], cmd[4]),
                    self.p(rect, cmd[5], cmd[6]),
                )

        self.draw_path(painter, path, rect)

    def draw_moon_letter(self, painter: QPainter, rect: QRectF, letter: str):
        # Vnitřní prostor symbolu.
        """Pomocná funkce používaná interní logikou šifry."""
        glyph = rect.adjusted(
            rect.width() * 0.13,
            rect.height() * 0.13,
            -rect.width() * 0.13,
            -rect.height() * 0.13,
        )

        if letter == "A":
            self.draw_lines(painter, glyph, [((0.12, 0.82), (0.50, 0.18)), ((0.50, 0.18), (0.88, 0.82))])
        elif letter == "B":
            self.draw_curve_path(painter, glyph, [("M", 0.28, 0.18), ("L", 0.28, 0.62), ("Q", 0.28, 0.86, 0.68, 0.72)])
        elif letter == "C":
            self.draw_curve_path(painter, glyph, [("M", 0.82, 0.22), ("C", 0.34, 0.16, 0.12, 0.42, 0.18, 0.58), ("C", 0.24, 0.76, 0.52, 0.82, 0.82, 0.74)])
        elif letter == "D":
            self.draw_curve_path(painter, glyph, [("M", 0.18, 0.22), ("C", 0.66, 0.16, 0.88, 0.42, 0.82, 0.58), ("C", 0.76, 0.76, 0.48, 0.82, 0.18, 0.74)])
        elif letter == "E":
            self.draw_lines(painter, glyph, [((0.22, 0.20), (0.22, 0.78)), ((0.22, 0.20), (0.78, 0.20))])
        elif letter == "F":
            self.draw_curve_path(painter, glyph, [("M", 0.28, 0.78), ("L", 0.28, 0.32), ("Q", 0.30, 0.14, 0.62, 0.20), ("L", 0.74, 0.34)])
        elif letter == "G":
            self.draw_curve_path(painter, glyph, [("M", 0.78, 0.78), ("L", 0.78, 0.36), ("Q", 0.76, 0.14, 0.44, 0.20), ("L", 0.28, 0.34)])
        elif letter == "H":
            self.draw_curve_path(painter, glyph, [("M", 0.50, 0.22), ("C", 0.22, 0.22, 0.18, 0.78, 0.50, 0.78), ("C", 0.82, 0.78, 0.78, 0.22, 0.50, 0.22)])
        elif letter == "I":
            self.draw_lines(painter, glyph, [((0.50, 0.18), (0.50, 0.82))])
        elif letter == "J":
            self.draw_curve_path(painter, glyph, [("M", 0.64, 0.18), ("L", 0.64, 0.62), ("Q", 0.62, 0.84, 0.34, 0.72), ("L", 0.22, 0.58)])
        elif letter == "K":
            self.draw_lines(painter, glyph, [((0.78, 0.20), (0.22, 0.50)), ((0.22, 0.50), (0.78, 0.80))])
        elif letter == "L":
            self.draw_lines(painter, glyph, [((0.22, 0.18), (0.22, 0.78)), ((0.22, 0.78), (0.78, 0.78))])
        elif letter == "M":
            self.draw_lines(painter, glyph, [((0.22, 0.20), (0.78, 0.20)), ((0.78, 0.20), (0.78, 0.78))])
        elif letter == "N":
            self.draw_lines(painter, glyph, [((0.22, 0.78), (0.22, 0.22)), ((0.22, 0.22), (0.78, 0.78)), ((0.78, 0.78), (0.78, 0.22))])
        elif letter == "O":
            self.draw_curve_path(painter, glyph, [("M", 0.50, 0.18), ("C", 0.18, 0.18, 0.18, 0.82, 0.50, 0.82), ("C", 0.82, 0.82, 0.82, 0.18, 0.50, 0.18)])
        elif letter == "P":
            self.draw_lines(painter, glyph, [((0.72, 0.28), (0.34, 0.62)), ((0.34, 0.62), (0.78, 0.62))])
        elif letter == "Q":
            self.draw_lines(painter, glyph, [((0.28, 0.62), (0.72, 0.62)), ((0.72, 0.62), (0.36, 0.28))])
        elif letter == "R":
            self.draw_lines(painter, glyph, [((0.24, 0.22), (0.76, 0.78))])
        elif letter == "S":
            self.draw_lines(painter, glyph, [((0.76, 0.22), (0.24, 0.78))])
        elif letter == "T":
            self.draw_lines(painter, glyph, [((0.22, 0.50), (0.78, 0.50))])
        elif letter == "U":
            self.draw_curve_path(painter, glyph, [("M", 0.22, 0.20), ("L", 0.22, 0.56), ("C", 0.22, 0.86, 0.78, 0.86, 0.78, 0.56), ("L", 0.78, 0.20)])
        elif letter == "V":
            self.draw_lines(painter, glyph, [((0.18, 0.20), (0.50, 0.82)), ((0.50, 0.82), (0.82, 0.20))])
        elif letter == "W":
            self.draw_curve_path(painter, glyph, [("M", 0.20, 0.78), ("C", 0.22, 0.20, 0.78, 0.20, 0.80, 0.78)])
        elif letter == "X":
            self.draw_lines(painter, glyph, [((0.22, 0.22), (0.80, 0.50)), ((0.80, 0.50), (0.22, 0.78))])
        elif letter == "Y":
            self.draw_lines(painter, glyph, [((0.78, 0.20), (0.78, 0.78)), ((0.78, 0.78), (0.24, 0.78))])
        elif letter == "Z":
            self.draw_lines(painter, glyph, [((0.22, 0.22), (0.78, 0.22)), ((0.78, 0.22), (0.28, 0.78)), ((0.28, 0.78), (0.78, 0.78))])
        else:
            self.draw_plain_symbol(painter, glyph, letter)


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
