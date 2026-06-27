"""Implementace šifry Morseova abeceda – hory pro Šifrátor Mraveniště.

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

DOT_VISUALS = {"△", "▵", "▴", "▲", "∙", "·"}
DASH_VISUALS = {"▲", "▴"}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru Morseova abeceda – hory.

    Vrací normalizovaný text, samotné hory kreslí MorseHoryOutputWidget.
    """
    return normalize_text(text)


def normalize_morse_token(token: str) -> str:
    """Převede různé zápisy hor / teček / čárek na . a -."""
    token = token.strip()
    result = []

    for char in token:
        if char in {".", "·", "∙", "•", "△", "▵"}:
            result.append(".")
        elif char in {"-", "–", "—", "_", "▲", "▴"}:
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
class MorseHoryOutputWidget(QWidget):
    """Kreslený výstup šifry Morseova abeceda – hory.

    Každé písmeno je jedna skupina hor:
    - tečka = malá hora
    - čárka = velká hora
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
        dash_w = max(23, int(32 * self.scale_value))
        mountain_h = max(27, int(38 * self.scale_value))
        inside_gap = max(2, int(4 * self.scale_value))
        letter_gap = max(12, int(18 * self.scale_value))
        word_gap = max(26, int(42 * self.scale_value))
        line_gap = max(14, int(22 * self.scale_value))
        cell_h = max(44, int(62 * self.scale_value))
        return dot_w, dash_w, mountain_h, inside_gap, letter_gap, word_gap, line_gap, cell_h

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
                self.draw_morse_mountains(painter, QRectF(x, y, char_w, cell_h), MORSE_CODE[char])
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)

            x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Pomocná funkce používaná interní logikou šifry."""
        font = QFont("Georgia", max(16, int(28 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def draw_morse_mountains(self, painter: QPainter, rect: QRectF, code: str):
        """Pomocná funkce používaná interní logikou šifry."""
        dot_w, dash_w, mountain_h, inside_gap, _, _, _, _ = self.get_metrics()

        x = rect.left()
        base_y = rect.top() + rect.height() * 0.78

        for mark in code:
            if mark == ".":
                self.draw_mountain(painter, x, base_y, dot_w, mountain_h * 0.62, small=True)
                x += dot_w + inside_gap
            else:
                self.draw_mountain(painter, x, base_y, dash_w, mountain_h, small=False)
                x += dash_w + inside_gap

    def draw_mountain(self, painter: QPainter, x: float, base_y: float, width: float, height: float, small: bool):
        """Pomocná funkce používaná interní logikou šifry."""
        shadow = QColor(0, 0, 0, 175)
        gold = QColor("#f3d79a")
        gold_light = QColor("#fff0bd")
        gold_dark = QColor("#9b6b2e")

        peak = QPointF(x + width * 0.5, base_y - height)
        left = QPointF(x, base_y)
        right = QPointF(x + width, base_y)

        path = QPainterPath()
        path.moveTo(left)
        path.lineTo(peak)
        path.lineTo(right)
        path.closeSubpath()

        shadow_path = QPainterPath(path)
        shadow_path.translate(1.4, 1.4)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawPath(shadow_path)

        painter.setBrush(QBrush(gold))
        painter.drawPath(path)

        # Levá světlá hrana a pravá tmavší hrana dávají hoře čitelnost.
        edge_w = max(1.0, height * 0.07)

        pen_light = QPen(gold_light)
        pen_light.setWidthF(edge_w)
        pen_light.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_light)
        painter.drawLine(left, peak)

        pen_dark = QPen(gold_dark)
        pen_dark.setWidthF(edge_w)
        pen_dark.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_dark)
        painter.drawLine(peak, right)

        # Jemné šrafování jako v klíči.
        hatch_pen = QPen(QColor(60, 42, 24, 120))
        hatch_pen.setWidthF(max(0.8, height * 0.025))
        painter.setPen(hatch_pen)

        if not small:
            painter.drawLine(QPointF(x + width * 0.28, base_y - height * 0.22), QPointF(x + width * 0.55, base_y - height * 0.48))
            painter.drawLine(QPointF(x + width * 0.47, base_y - height * 0.18), QPointF(x + width * 0.73, base_y - height * 0.45))
        else:
            painter.drawLine(QPointF(x + width * 0.35, base_y - height * 0.18), QPointF(x + width * 0.60, base_y - height * 0.42))


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(".- .... --- .---  .--- .- -.-")

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
