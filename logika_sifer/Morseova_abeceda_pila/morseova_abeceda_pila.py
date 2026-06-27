"""Implementace šifry Morseova abeceda – pila pro Šifrátor Mraveniště.

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


# Mapování Morseovy abecedy pro základní textovou logiku.
MORSE_CODE = {
    "A": ".-",
    "B": "-...",
    "C": "-.-.",
    "D": "-..",
    "E": ".",
    "F": "..-.",
    "G": "--.",
    "H": "....",
    "I": "..",
    "J": ".---",
    "K": "-.-",
    "L": ".-..",
    "M": "--",
    "N": "-.",
    "O": "---",
    "P": ".--.",
    "Q": "--.-",
    "R": ".-.",
    "S": "...",
    "T": "-",
    "U": "..-",
    "V": "...-",
    "W": ".--",
    "X": "-..-",
    "Y": "-.--",
    "Z": "--..",
}

MORSE_TO_LETTER = {value: key for key, value in MORSE_CODE.items()}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Morseova abeceda – pila.

    Vrací normalizovaný text, samotnou pilu kreslí MorsePilaOutputWidget.
    """
    return normalize_text(text)


def normalize_morse_token(token: str) -> str:
    """Převede různé zápisy teček/čárek na . a -."""
    token = token.strip()
    result = []

    for char in token:
        if char in {".", "·", "∙", "•"}:
            result.append(".")
        elif char in {"-", "–", "—", "_"}:
            result.append("-")
        else:
            result.append(char)

    return "".join(result)


def decrypt(text: str) -> str:
    """Dešifruje textový zápis Morseovky zpět na text.

    Podporuje například:
    .- .... --- .---  .--- .- -.-

    Podporuje také:
    .-|....|---|.---||.---|.-|-.-

    Symboly, které nejsou Morseův kód, nechá beze změny.
    """
    cleaned = text.strip()

    if not cleaned:
        return ""

    cleaned = cleaned.replace(" || ", "||")
    cleaned = cleaned.replace("|| ", "||")
    cleaned = cleaned.replace(" ||", "||")

    cleaned = cleaned.replace(" / ", "||")
    cleaned = cleaned.replace("/ ", "||")
    cleaned = cleaned.replace(" /", "||")
    cleaned = cleaned.replace("/", "||")

    cleaned = cleaned.replace(" | ", "|")
    cleaned = cleaned.replace("| ", "|")
    cleaned = cleaned.replace(" |", "|")

    decoded_words = []

    if "||" in cleaned or "|" in cleaned:
        raw_words = cleaned.split("||")
        for raw_word in raw_words:
            raw_word = raw_word.strip()
            if not raw_word:
                continue

            if "|" in raw_word:
                tokens = [token for token in raw_word.split("|") if token.strip()]
            else:
                tokens = [token for token in raw_word.split() if token.strip()]

            decoded_word = []
            for token in tokens:
                normalized = normalize_morse_token(token)
                decoded_word.append(MORSE_TO_LETTER.get(normalized, token))

            decoded_words.append("".join(decoded_word))

        return " ".join(decoded_words)

    # Dvě a více mezer bereme jako mezery mezi slovy.
    raw_words = []
    current = []
    parts = cleaned.split(" ")
    empty_count = 0

    for part in parts:
        if part == "":
            empty_count += 1
            continue

        if empty_count >= 1 and current:
            raw_words.append(current)
            current = []

        empty_count = 0
        current.append(part)

    if current:
        raw_words.append(current)

    if not raw_words:
        raw_words = [[cleaned]]

    for word_tokens in raw_words:
        decoded_word = []
        for token in word_tokens:
            normalized = normalize_morse_token(token)
            decoded_word.append(MORSE_TO_LETTER.get(normalized, token))
        decoded_words.append("".join(decoded_word))

    return " ".join(decoded_words)



# Grafická vrstva pro vykreslení výsledku v Qt rozhraní.
class MorsePilaOutputWidget(QWidget):
    """Kreslený výstup šifry Morseova abeceda – pila.

    Každé písmeno je jedna skupina zubů pily:
    - tečka = malý zub
    - čárka = velký zub
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

    def get_metrics(self):
        """Pomocná funkce používaná interní logikou šifry."""
        dot_w = max(13, int(18 * self.scale_value))
        dash_w = max(24, int(34 * self.scale_value))
        tooth_h = max(27, int(40 * self.scale_value))
        inside_gap = max(2, int(4 * self.scale_value))
        letter_gap = max(12, int(18 * self.scale_value))
        word_gap = max(26, int(42 * self.scale_value))
        line_gap = max(14, int(22 * self.scale_value))
        cell_h = max(44, int(62 * self.scale_value))
        return dot_w, dash_w, tooth_h, inside_gap, letter_gap, word_gap, line_gap, cell_h

    def letter_width(self, char: str) -> int:
        """Pomocná funkce používaná interní logikou šifry."""
        dot_w, dash_w, _, inside_gap, _, _, _, _ = self.get_metrics()

        if char in MORSE_CODE:
            code = MORSE_CODE[char]
            width = 0
            for index, mark in enumerate(code):
                width += dot_w if mark == "." else dash_w
                if index < len(code) - 1:
                    width += inside_gap
            # Krátká vodorovná patka na konci, aby to připomínalo pilový graf z klíče.
            width += max(8, int(12 * self.scale_value))
            return max(width, dot_w)

        return max(22, int(28 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        """Spočítá minimální výšku potřebnou pro zobrazení celého obsahu."""
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, _, _, _, letter_gap, word_gap, line_gap, cell_h = self.get_metrics()
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

            if char == " ":
                x += word_gap
                continue

            char_w = self.letter_width(char)

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

        _, _, _, _, letter_gap, word_gap, line_gap, cell_h = self.get_metrics()

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

            char_w = self.letter_width(char)

            if x > rect.left() and x + char_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if char in MORSE_CODE:
                self.draw_morse_saw(painter, QRectF(x, y, char_w, cell_h), MORSE_CODE[char])
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)

            x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Pomocná funkce používaná interní logikou šifry."""
        font = QFont("Georgia", max(16, int(28 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def draw_morse_saw(self, painter: QPainter, rect: QRectF, code: str):
        """Pomocná funkce používaná interní logikou šifry."""
        dot_w, dash_w, tooth_h, inside_gap, _, _, _, _ = self.get_metrics()

        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")
        shadow = QColor(0, 0, 0, 170)

        baseline_y = rect.top() + rect.height() * 0.78
        x = rect.left()

        path = QPainterPath()
        path.moveTo(QPointF(x, baseline_y))

        for mark in code:
            if mark == ".":
                width = dot_w
                height = tooth_h * 0.36
            else:
                width = dash_w
                height = tooth_h

            # Pilový zub: prudce nahoru, šikmo dolů, krátká základna.
            peak_x = x + width * 0.32
            peak_y = baseline_y - height
            end_x = x + width

            path.lineTo(QPointF(peak_x, peak_y))
            path.lineTo(QPointF(end_x, baseline_y))

            x = end_x + inside_gap
            path.lineTo(QPointF(x, baseline_y))

        # Krátká vodorovná patka na konci.
        tail = max(8, int(12 * self.scale_value))
        path.lineTo(QPointF(x + tail, baseline_y))

        line_w = max(2.0, rect.height() * 0.045)

        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w + 1.8)
        shadow_pen.setCapStyle(Qt.RoundCap)
        shadow_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(shadow_pen)
        painter.drawPath(path.translated(1.3, 1.3))

        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(main_pen)
        painter.drawPath(path)

        light_pen = QPen(gold_light)
        light_pen.setWidthF(max(0.8, line_w * 0.36))
        light_pen.setCapStyle(Qt.RoundCap)
        light_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(light_pen)
        painter.drawPath(path)

        # Jemné šrafování u velkých zubů.
        hatch_pen = QPen(QColor(60, 42, 24, 145))
        hatch_pen.setWidthF(max(0.7, line_w * 0.25))
        painter.setPen(hatch_pen)

        x = rect.left()
        for mark in code:
            width = dot_w if mark == "." else dash_w
            height = tooth_h * 0.36 if mark == "." else tooth_h
            if mark == "-":
                painter.drawLine(
                    QPointF(x + width * 0.24, baseline_y - height * 0.14),
                    QPointF(x + width * 0.47, baseline_y - height * 0.62),
                )
                painter.drawLine(
                    QPointF(x + width * 0.48, baseline_y - height * 0.10),
                    QPointF(x + width * 0.70, baseline_y - height * 0.44),
                )
            x += width + inside_gap


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(".- .... --- .---  .--- .- -.-")

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
