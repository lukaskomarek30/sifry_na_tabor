# ============================================================
# Morseova abeceda – stromy - logika + kreslení přes QPainter
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Morseova abeceda – stromy\morseova_abeceda_stromy.py
#
# OPRAVENÝ PRINCIP PODLE KLÍČE:
# - tečka  .  = větev doleva
# - čárka  -  = větev doprava
# - pořadí Morseovky se kreslí ODSPODU NAHORU po kmenu
#
# Příklad podle klíče:
# A = .-   => spodní větev doleva, horní větev doprava
# H = .... => čtyři větve doleva
# O = ---  => tři větve doprava
# J = .--- => spodní větev doleva, ostatní větve doprava
#
# Pravidla:
# - česká diakritika se převede na základní znaky
# - symboly jako ?, . , - ! : ; / zůstávají symboly
# - výsledek se kreslí přes QPainter
#
# Soubor obsahuje:
# - encrypt(text)
# - decrypt(text)
# - MorseStromyOutputWidget pro kreslený výstup
# ============================================================

import unicodedata

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath
from PySide6.QtWidgets import QWidget


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
    """Připraví text pro kreslenou šifru Morseova abeceda – stromy."""
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


class MorseStromyOutputWidget(QWidget):
    """Kreslený výstup šifry Morseova abeceda – stromy.

    Význam podle klíče:
    . = větev doleva
    - = větev doprava
    pořadí Morseovky = odspodu nahoru
    """

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
        cell_w = max(44, int(64 * self.scale_value))
        cell_h = max(84, int(112 * self.scale_value))
        trunk_h = max(60, int(82 * self.scale_value))
        branch_len = max(20, int(30 * self.scale_value))
        branch_drop = max(10, int(15 * self.scale_value))
        letter_gap = max(8, int(12 * self.scale_value))
        word_gap = max(28, int(44 * self.scale_value))
        line_gap = max(16, int(24 * self.scale_value))
        return cell_w, cell_h, trunk_h, branch_len, branch_drop, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, _, _, _, word_gap, _ = self.get_metrics()

        if char == " ":
            return word_gap

        if char in MORSE_CODE:
            return cell_w

        return max(22, int(28 * self.scale_value) + 10)

    def calculate_required_height(self, available_width: int) -> int:
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, cell_h, _, _, _, letter_gap, _, line_gap = self.get_metrics()
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

        cell_w, cell_h, _, _, _, letter_gap, _, line_gap = self.get_metrics()

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

            if char in MORSE_CODE:
                self.draw_tree_letter(painter, QRectF(x, y, cell_w, cell_h), MORSE_CODE[char])
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(16, int(28 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)

    def draw_branch(self, painter: QPainter, start: QPointF, side: int, length: float, drop: float, line_w: float, shadow, gold, gold_light, gold_dark):
        """Nakreslí větev víc jako jehličnatý strom z klíče."""
        end = QPointF(start.x() + side * length, start.y() + drop)
        ctrl1 = QPointF(start.x() + side * length * 0.22, start.y() + drop * 0.10)
        ctrl2 = QPointF(start.x() + side * length * 0.72, start.y() + drop * 0.72)

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)

        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w + 1.8)
        shadow_pen.setCapStyle(Qt.RoundCap)
        shadow_pen.setJoinStyle(Qt.RoundJoin)

        main_pen = QPen(gold)
        main_pen.setWidthF(line_w)
        main_pen.setCapStyle(Qt.RoundCap)
        main_pen.setJoinStyle(Qt.RoundJoin)

        light_pen = QPen(gold_light)
        light_pen.setWidthF(max(0.7, line_w * 0.28))
        light_pen.setCapStyle(Qt.RoundCap)
        light_pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(shadow_pen)
        painter.drawPath(path.translated(1.1, 1.1))
        painter.setPen(main_pen)
        painter.drawPath(path)
        painter.setPen(light_pen)
        painter.drawPath(path)

        dark_pen = QPen(gold_dark)
        dark_pen.setWidthF(max(0.8, line_w * 0.34))
        dark_pen.setCapStyle(Qt.RoundCap)
        dark_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(dark_pen)

        # 2 menší větvičky po směru hlavní větve pro vzhled smrku.
        twig1 = QPointF(start.x() + side * length * 0.44, start.y() + drop * 0.42)
        twig1_end = QPointF(twig1.x() + side * length * 0.22, twig1.y() + drop * 0.18)
        painter.drawLine(twig1, twig1_end)

        twig2 = QPointF(start.x() + side * length * 0.62, start.y() + drop * 0.64)
        twig2_end = QPointF(twig2.x() + side * length * 0.18, twig2.y() + drop * 0.14)
        painter.drawLine(twig2, twig2_end)

    def draw_tree_letter(self, painter: QPainter, rect: QRectF, code: str):
        _, _, trunk_h, branch_len, branch_drop, _, _, _ = self.get_metrics()

        gold = QColor("#f3d79a")
        gold_light = QColor("#fff3c9")
        gold_dark = QColor("#8c622c")
        shadow = QColor(0, 0, 0, 175)

        center_x = rect.center().x()
        bottom_y = rect.top() + rect.height() * 0.90
        top_y = bottom_y - trunk_h

        line_w = max(2.2, rect.height() * 0.050)

        shadow_pen = QPen(shadow)
        shadow_pen.setWidthF(line_w + 1.8)
        shadow_pen.setCapStyle(Qt.RoundCap)
        shadow_pen.setJoinStyle(Qt.RoundJoin)

        trunk_pen = QPen(gold)
        trunk_pen.setWidthF(line_w)
        trunk_pen.setCapStyle(Qt.RoundCap)
        trunk_pen.setJoinStyle(Qt.RoundJoin)

        light_pen = QPen(gold_light)
        light_pen.setWidthF(max(0.7, line_w * 0.26))
        light_pen.setCapStyle(Qt.RoundCap)
        light_pen.setJoinStyle(Qt.RoundJoin)

        # Kmen.
        painter.setPen(shadow_pen)
        painter.drawLine(QPointF(center_x + 1.1, bottom_y + 1.1), QPointF(center_x + 1.1, top_y + 1.1))
        painter.setPen(trunk_pen)
        painter.drawLine(QPointF(center_x, bottom_y), QPointF(center_x, top_y))
        painter.setPen(light_pen)
        painter.drawLine(QPointF(center_x - line_w * 0.16, bottom_y), QPointF(center_x - line_w * 0.16, top_y))

        # Špička stromu.
        tip_len = max(7.0, trunk_h * 0.10)
        painter.setPen(trunk_pen)
        painter.drawLine(QPointF(center_x, top_y), QPointF(center_x, top_y - tip_len))
        painter.setPen(light_pen)
        painter.drawLine(QPointF(center_x - line_w * 0.12, top_y), QPointF(center_x - line_w * 0.12, top_y - tip_len))

        # Pořadí Morseovky se kreslí odspodu nahoru.
        count = max(1, len(code))
        step = trunk_h / (count + 1)

        for index, mark in enumerate(code):
            y = bottom_y - step * (index + 1)
            side = -1 if mark == "." else 1

            start = QPointF(center_x, y)
            length = branch_len * (1.10 - index * 0.05)
            drop = branch_drop * (1.00 - index * 0.03)

            self.draw_branch(
                painter,
                start,
                side,
                length,
                drop,
                line_w,
                shadow,
                gold,
                gold_light,
                gold_dark,
            )


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(".- .... --- .---  .--- .- -.-")

    print("Vstup:", sample)
    print("Data pro kreslení:", encrypted)
    print("Dešifrování:", decrypted)
