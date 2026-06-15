"""Logika šifry Brailovo písmo pro Šifrátor Mraveniště.

Umístění v projektu:
    logika sifer/Brailovo písmo/brailovo_pismo.py

Co modul umí:
- encrypt(text)  -> převede text na vizuální braillovu mřížku z koleček
- decrypt(text)  -> umí přečíst výstup vytvořený funkcí encrypt()
- symboly ?, . , - ! : ; / ( ) apod. zůstávají jako symboly
- podporuje česká písmena podle přiloženého klíče: Á, Č, Ď, É, Ě, Í, Ň, Ó, Ř, Š, Ť, Ú, Ů, Ý, Ž
- čísla se zapisují jako braillovský číselný znak + A-J, takže mají šířku 4 sloupce

Poznámka:
Soubor obsahuje i třídu BrailleOutputWidget pro případné budoucí napojení na kreslený
Qt výstup stejně jako Britská vlajka. Aktuální main.py ale zatím Braillovo písmo zobrazuje
přes běžné QTextEdit pole, takže hlavní jsou funkce encrypt/decrypt.
"""

from __future__ import annotations

import unicodedata
from typing import Iterable, List, Sequence, Tuple, Union

DotTuple = Tuple[int, ...]
GlyphPart = Union[DotTuple, str]

FILLED = "●"
EMPTY = "○"
LETTER_GAP = " "
WORD_GAP = "      "

# Pozice braillova bodu:
# 1 4
# 2 5
# 3 6
#
# Hodnoty níže odpovídají klíči z obrázku.
CHAR_TO_DOTS: dict[str, DotTuple] = {
    "A": (1,),
    "Á": (1, 6),
    "B": (1, 2),
    "C": (1, 4),
    "Č": (1, 4, 6),
    "D": (1, 4, 5),
    "Ď": (1, 4, 5, 6),
    "E": (1, 5),
    "É": (3, 5, 6),
    "Ě": (1, 2, 6),
    "F": (1, 2, 4),
    "G": (1, 2, 4, 5),
    "H": (1, 2, 5),
    "I": (2, 4),
    "Í": (3, 4),
    "J": (2, 4, 5),
    "K": (1, 3),
    "L": (1, 2, 3),
    "M": (1, 3, 4),
    "N": (1, 3, 4, 5),
    "Ň": (1, 2, 4, 6),
    "O": (1, 3, 5),
    "Ó": (2, 4, 6),
    "P": (1, 2, 3, 4),
    "Q": (1, 2, 3, 4, 5),
    "R": (1, 2, 3, 5),
    "Ř": (2, 4, 5, 6),
    "S": (2, 3, 4),
    "Š": (1, 5, 6),
    "T": (2, 3, 4, 5),
    "Ť": (1, 2, 5, 6),
    "U": (1, 3, 6),
    "Ú": (3, 4, 6),
    "Ů": (2, 3, 4, 5, 6),
    "V": (1, 2, 3, 6),
    "W": (2, 4, 5, 6),
    "X": (1, 3, 4, 6),
    "Y": (1, 3, 4, 5, 6),
    "Ý": (1, 2, 3, 4, 5, 6),
    "Z": (1, 3, 5, 6),
    "Ž": (2, 3, 4, 6),
}

DOTS_TO_CHAR: dict[DotTuple, str] = {dots: char for char, dots in CHAR_TO_DOTS.items()}

# Číselný znak v Braillově písmu: body 3, 4, 5, 6.
NUMBER_PREFIX: DotTuple = (3, 4, 5, 6)
DIGIT_TO_LETTER: dict[str, str] = {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "E",
    "6": "F",
    "7": "G",
    "8": "H",
    "9": "I",
    "0": "J",
}
LETTER_TO_DIGIT: dict[str, str] = {letter: digit for digit, letter in DIGIT_TO_LETTER.items()}

# Znaky, které se nešifrují a zůstanou ve výstupu jako běžný symbol.
PASSTHROUGH_SYMBOLS = set("?.!,;:-_+/\\|()[]{}<>@#&%*=\"'„“‚‘`~^°\n\t")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_char(char: str) -> str:
    """Převede znak na tvar použitelný v tabulce.

    Česká diakritika zůstane zachovaná, protože ji šifra podle klíče podporuje.
    U ostatních diakritických znaků se použije základní písmeno.
    """
    if not char:
        return char

    upper = char.upper()
    if upper in CHAR_TO_DOTS:
        return upper

    stripped = _strip_accents(upper)
    if stripped in CHAR_TO_DOTS:
        return stripped

    return upper


def dot_to_rows(dots: Sequence[int]) -> list[str]:
    dots_set = set(dots)
    return [
        (FILLED if 1 in dots_set else EMPTY) + (FILLED if 4 in dots_set else EMPTY),
        (FILLED if 2 in dots_set else EMPTY) + (FILLED if 5 in dots_set else EMPTY),
        (FILLED if 3 in dots_set else EMPTY) + (FILLED if 6 in dots_set else EMPTY),
    ]


def rows_to_dots(rows: Sequence[str]) -> DotTuple | None:
    if len(rows) != 3:
        return None

    # Segment musí být přesně jeden braillovský znak 2 × 3.
    if any(len(row) != 2 for row in rows):
        return None

    dots: list[int] = []
    if rows[0][0] == FILLED:
        dots.append(1)
    if rows[1][0] == FILLED:
        dots.append(2)
    if rows[2][0] == FILLED:
        dots.append(3)
    if rows[0][1] == FILLED:
        dots.append(4)
    if rows[1][1] == FILLED:
        dots.append(5)
    if rows[2][1] == FILLED:
        dots.append(6)

    if any(ch not in (FILLED, EMPTY) for row in rows for ch in row):
        return None

    return tuple(dots)


def glyph_parts_for_char(char: str) -> list[GlyphPart] | None:
    """Vrátí části jednoho znaku.

    Písmeno má jednu braillovu buňku.
    Číslo má dvě buňky: číselný znak + písmeno A-J.
    Symbol se vrací jako běžný znak.
    """
    if char.isdigit():
        letter = DIGIT_TO_LETTER[char]
        return [NUMBER_PREFIX, CHAR_TO_DOTS[letter]]

    normalized = normalize_char(char)
    if normalized in CHAR_TO_DOTS:
        return [CHAR_TO_DOTS[normalized]]

    if char in PASSTHROUGH_SYMBOLS or not char.isalnum():
        return [char]

    return None


def parts_to_rows(parts: Sequence[GlyphPart]) -> list[str]:
    rows = ["", "", ""]

    for part in parts:
        if isinstance(part, tuple):
            part_rows = dot_to_rows(part)
        else:
            # Symbol necháme jako symbol. Zobrazí se uprostřed výšky braillovy buňky.
            symbol = part if part != "\t" else "    "
            width = max(1, len(symbol))
            part_rows = [" " * width, symbol, " " * width]

        for index in range(3):
            rows[index] += part_rows[index]

    return rows


def encrypt(text: str) -> str:
    """Zašifruje text do vizuálního Braillova písma.

    Výstup jsou tři řádky pro každý textový řádek. Písmena ve slově navazují vedle sebe,
    mezi slovy je větší mezera a symboly zůstávají jako symboly.
    """
    if text is None:
        return ""

    output_lines: list[str] = []

    for source_line in str(text).splitlines() or [""]:
        rows = ["", "", ""]
        pending_gap = False

        for char in source_line:
            if char.isspace():
                # Více mezer po sobě nedělá nekonečnou mezeru, stačí jedna mezera mezi slovy.
                if rows[0] and not rows[0].endswith(WORD_GAP):
                    for index in range(3):
                        rows[index] += WORD_GAP
                pending_gap = False
                continue

            parts = glyph_parts_for_char(char)
            if parts is None:
                # Neznámý znak necháme jako běžný symbol, aby se nic neztratilo.
                parts = [char]

            if pending_gap:
                for index in range(3):
                    rows[index] += LETTER_GAP

            glyph_rows = parts_to_rows(parts)
            for index in range(3):
                rows[index] += glyph_rows[index]

            pending_gap = True

        output_lines.extend(line.rstrip() for line in rows)
        output_lines.append("")

    while output_lines and output_lines[-1] == "":
        output_lines.pop()

    return "\n".join(output_lines)


def _split_visual_segments(row0: str, row1: str, row2: str) -> list[tuple[str, list[str]]]:
    """Rozdělí tři řádky zašifrovaného výstupu na segmenty.

    Vrací položky:
    - ("glyph", [r0, r1, r2]) pro znak
    - ("space", []) pro mezeru mezi slovy
    """
    width = max(len(row0), len(row1), len(row2))
    rows = [row0.ljust(width), row1.ljust(width), row2.ljust(width)]

    segments: list[tuple[str, list[str]]] = []
    col = 0
    empty_run = 0

    while col < width:
        column_empty = rows[0][col] == " " and rows[1][col] == " " and rows[2][col] == " "

        if column_empty:
            start = col
            while col < width and rows[0][col] == " " and rows[1][col] == " " and rows[2][col] == " ":
                col += 1
            empty_run = col - start
            if empty_run >= 4:
                if segments and segments[-1][0] != "space":
                    segments.append(("space", []))
            continue

        # Symbol, který je jen v prostředním řádku.
        if rows[0][col] == " " and rows[2][col] == " " and rows[1][col] not in (" ", FILLED, EMPTY):
            segments.append(("glyph", [" ", rows[1][col], " "]))
            col += 1
            continue

        # Braillova buňka má šířku 2. Číslo má dvě buňky vedle sebe, tedy šířku 4.
        # Tady bereme vždy buňku po buňce. Dvojice prefix + A-J se spojí až v decrypt().
        part = [rows[0][col:col + 2], rows[1][col:col + 2], rows[2][col:col + 2]]
        if all(len(row) == 2 for row in part):
            segments.append(("glyph", part))
            col += 2
        else:
            col += 1

    return segments


def _decrypt_visual_block(row0: str, row1: str, row2: str) -> str:
    segments = _split_visual_segments(row0, row1, row2)
    result: list[str] = []
    index = 0

    while index < len(segments):
        kind, value = segments[index]

        if kind == "space":
            if result and result[-1] != " ":
                result.append(" ")
            index += 1
            continue

        # Běžný symbol z prostředního řádku.
        if value and len(value[0]) == 1 and len(value[1]) == 1 and len(value[2]) == 1:
            if value[1] not in (" ", FILLED, EMPTY):
                result.append(value[1])
                index += 1
                continue

        dots = rows_to_dots(value)
        if dots is None:
            index += 1
            continue

        # Číslo: prefix 3456 + další buňka A-J.
        if dots == NUMBER_PREFIX and index + 1 < len(segments):
            next_kind, next_value = segments[index + 1]
            next_dots = rows_to_dots(next_value) if next_kind == "glyph" else None
            next_char = DOTS_TO_CHAR.get(next_dots or tuple())
            if next_char in LETTER_TO_DIGIT:
                result.append(LETTER_TO_DIGIT[next_char])
                index += 2
                continue

        result.append(DOTS_TO_CHAR.get(dots, "?"))
        index += 1

    return "".join(result).strip()


def decrypt(text: str) -> str:
    """Dešifruje výstup vytvořený funkcí encrypt().

    Funkce očekává třířádkový vizuální zápis z koleček. Symboly nechává jako symboly.
    """
    if text is None:
        return ""

    raw_lines = str(text).splitlines()
    if not raw_lines:
        return ""

    result_lines: list[str] = []
    buffer: list[str] = []

    for line in raw_lines + [""]:
        if line.strip() == "":
            if buffer:
                while len(buffer) < 3:
                    buffer.append("")
                # Bereme vždy první tři řádky bloku. To odpovídá encrypt().
                result_lines.append(_decrypt_visual_block(buffer[0], buffer[1], buffer[2]))
                buffer = []
            continue

        buffer.append(line.rstrip("\n"))
        if len(buffer) == 3:
            result_lines.append(_decrypt_visual_block(buffer[0], buffer[1], buffer[2]))
            buffer = []

    return "\n".join(line for line in result_lines if line != "")


# ------------------------------------------------------------
# Volitelný kreslený Qt widget pro budoucí napojení do main.py
# ------------------------------------------------------------

try:
    from PySide6.QtCore import Qt, QSize
    from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
    from PySide6.QtWidgets import QWidget
except Exception:  # pragma: no cover - aby šla logika použít i bez PySide6
    QWidget = object  # type: ignore
    Qt = None  # type: ignore
    QSize = None  # type: ignore
    QColor = None  # type: ignore
    QPainter = None  # type: ignore
    QPen = None  # type: ignore
    QBrush = None  # type: ignore
    QFont = None  # type: ignore


class BrailleOutputWidget(QWidget):  # type: ignore[misc]
    """Kreslený výstup Braillova písma.

    Třída je připravená pro napojení podobně jako BritishFlagOutputWidget.
    Aktuální main.py ji ale musí začít používat přes vlastní QScrollArea.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._scale = 1.0
        if hasattr(self, "setMinimumSize"):
            self.setMinimumSize(400, 220)

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.45, float(scale or 1.0))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str) -> None:
        # Když main.py pošle už zašifrovanou mřížku, zkusíme ji vrátit na text a kreslit čistě.
        if FILLED in str(text) or EMPTY in str(text):
            plain = decrypt(text)
        else:
            plain = str(text or "")
        self._text = plain
        self.update_content_size()
        self.update()

    def setText(self, text: str) -> None:  # kompatibilita s main.py
        self.set_cipher_text(text)

    def sizeHint(self):
        if QSize is None:
            return None
        return QSize(760, 260)

    def _layout_items(self, width: int):
        scale = self._scale
        margin = int(22 * scale)
        dot = max(4, int(7 * scale))
        dot_gap_x = max(7, int(12 * scale))
        dot_gap_y = max(7, int(12 * scale))
        cell_gap = max(10, int(14 * scale))
        word_gap = max(28, int(38 * scale))
        line_gap = max(28, int(42 * scale))

        cell_w = dot * 2 + dot_gap_x
        cell_h = dot * 3 + dot_gap_y * 2

        x = margin
        y = margin
        items = []

        words = self._text.split(" ") if self._text else []
        for w_index, word in enumerate(words):
            glyphs = []
            for char in word:
                parts = glyph_parts_for_char(char) or [char]
                glyph_w = 0
                for part in parts:
                    glyph_w += cell_w if isinstance(part, tuple) else max(cell_w, int(18 * scale))
                glyphs.append((char, parts, glyph_w))

            word_w = sum(glyph_w for _, _, glyph_w in glyphs)
            if glyphs:
                word_w += cell_gap * max(0, len(glyphs) - 1)

            if x > margin and x + word_w > max(width - margin, margin + 1):
                x = margin
                y += cell_h + line_gap

            for char, parts, glyph_w in glyphs:
                items.append((x, y, parts))
                x += glyph_w + cell_gap

            if w_index < len(words) - 1:
                x += word_gap

        total_h = y + cell_h + margin
        return items, total_h, (dot, dot_gap_x, dot_gap_y, cell_w)

    def update_content_size(self) -> None:
        if not hasattr(self, "width"):
            return
        width = max(400, self.width())
        _, total_h, _ = self._layout_items(width)
        self.setMinimumHeight(max(180, total_h))

    def paintEvent(self, event):  # noqa: N802 - Qt metoda
        if QPainter is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        items, total_h, dims = self._layout_items(max(400, self.width()))
        dot, dot_gap_x, dot_gap_y, cell_w = dims

        pen_empty = QPen(QColor(165, 165, 165), max(1, int(1.5 * self._scale)))
        brush_empty = QBrush(QColor(255, 255, 255, 0))
        pen_filled = QPen(QColor(40, 40, 40), max(1, int(1.0 * self._scale)))
        brush_filled = QBrush(QColor(45, 45, 45))

        def draw_cell(x: int, y: int, dots: Sequence[int]) -> None:
            positions = {
                1: (x, y),
                2: (x, y + dot + dot_gap_y),
                3: (x, y + (dot + dot_gap_y) * 2),
                4: (x + dot + dot_gap_x, y),
                5: (x + dot + dot_gap_x, y + dot + dot_gap_y),
                6: (x + dot + dot_gap_x, y + (dot + dot_gap_y) * 2),
            }
            dots_set = set(dots)
            for number in (1, 2, 3, 4, 5, 6):
                px, py = positions[number]
                if number in dots_set:
                    painter.setPen(pen_filled)
                    painter.setBrush(brush_filled)
                else:
                    painter.setPen(pen_empty)
                    painter.setBrush(brush_empty)
                painter.drawEllipse(px, py, dot, dot)

        for x, y, parts in items:
            part_x = x
            for part in parts:
                if isinstance(part, tuple):
                    draw_cell(part_x, y, part)
                    part_x += cell_w
                else:
                    painter.setPen(QColor(45, 45, 45))
                    painter.setFont(QFont("Georgia", max(12, int(22 * self._scale))))
                    painter.drawText(part_x, y, max(cell_w, 20), int(45 * self._scale), Qt.AlignCenter, part)
                    part_x += max(cell_w, int(20 * self._scale))


def get_key_data() -> dict:
    """Vrátí data pro společný pirátský generátor klíčů."""
    items = [(char, dots) for char, dots in CHAR_TO_DOTS.items()]
    for digit in "1234567890":
        letter = DIGIT_TO_LETTER[digit]
        items.append((digit, [NUMBER_PREFIX, CHAR_TO_DOTS[letter]]))

    return {
        "title": "Klíč šifry – Brailovo písmo",
        "subtitle": "Plná kolečka značí aktivní body Braillova znaku",
        "description": "Písmena se kreslí jako buňka 2 × 3 body. Čísla se zobrazují jako číselný znak + příslušné písmeno A-J.",
        "type": "braille",
        "columns": 9,
        "items": items,
    }


if __name__ == "__main__":
    sample = "Ahoj jak se máš? 123"
    encrypted = encrypt(sample)
    print(encrypted)
    print("---")
    print(decrypt(encrypted))
