# -*- coding: utf-8 -*-
"""Implementace šifry Binární čtverce.

Modul obsahuje kompletní logiku pro převod textu na binární čtverce
a zpětné dešifrování do běžného textu. Součástí je také Qt widget,
který zajišťuje grafické vykreslení výsledku přímo v aplikaci.

Umístění v projektu:
    logika sifer/Binární čtverce/binarni_ctverce.py

Princip šifry:
- písmena A–Z jsou mapována na 5bitový binární kód,
- hodnota 1 se vykresluje jako plný čtverec,
- hodnota 0 se vykresluje jako prázdný čtverec,
- sloupec se čte odspoda nahoru, takže poslední bit je vizuálně nahoře,
- česká diakritika se před šifrováním normalizuje na základní písmeno,
- mezery a běžné symboly zůstávají ve výstupu zachované.

Příklad:
    A = 00001
    Při vykreslení je poslední bit nahoře, takže horní čtverec je plný.
"""

from __future__ import annotations

import re
import unicodedata

# Základní vizuální symboly a podporovaná abeceda šifry.
FILLED = "■"
EMPTY = "□"
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Mapování písmen na 5bitový kód začíná od 1, aby A odpovídalo hodnotě 00001.
LETTER_TO_BITS = {
    letter: format(index, "05b")
    for index, letter in enumerate(ALPHABET, start=1)
}
# Reverzní mapa se používá při dešifrování všech podporovaných vstupních formátů.
BITS_TO_LETTER = {bits: letter for letter, bits in LETTER_TO_BITS.items()}

# Explicitní převod českých znaků řeší případy, které samotné unicodedata nemusí normalizovat spolehlivě.
CZECH_TRANSLATION = str.maketrans({
    "Á": "A", "Č": "C", "Ď": "D", "É": "E", "Ě": "E",
    "Í": "I", "Ň": "N", "Ó": "O", "Ř": "R", "Š": "S",
    "Ť": "T", "Ú": "U", "Ů": "U", "Ý": "Y", "Ž": "Z",
    "á": "A", "č": "C", "ď": "D", "é": "E", "ě": "E",
    "í": "I", "ň": "N", "ó": "O", "ř": "R", "š": "S",
    "ť": "T", "ú": "U", "ů": "U", "ý": "Y", "ž": "Z",
})


def _normalize_char(char: str) -> str:
    """Normalizuje jeden vstupní znak na velké písmeno bez diakritiky."""
    if not char:
        return ""

    translated = char.translate(CZECH_TRANSLATION)
    decomposed = unicodedata.normalize("NFKD", translated)
    without_marks = "".join(
        part for part in decomposed
        if not unicodedata.combining(part)
    )
    return without_marks.upper()[:1]


def _bits_to_visual_column(bits: str) -> list[str]:
    """Převede validní 5bitový kód na vizuální sloupec čtverců.

    Bitový zápis je uložen ve směru zdola nahoru, zatímco vykreslení probíhá
    po řádcích shora dolů. Z toho důvodu se pořadí bitů před vykreslením obrací.
    """
    bits = bits.strip()
    if len(bits) != 5 or any(bit not in "01" for bit in bits):
        raise ValueError(f"Neplatný binární kód: {bits!r}")

    return [FILLED if bit == "1" else EMPTY for bit in reversed(bits)]


def _visual_column_to_bits(column: list[str]) -> str | None:
    """Převede vizuální sloupec pěti čtverců zpět na původní 5bitový kód."""
    if len(column) != 5:
        return None

    normalized: list[str] = []
    for item in column:
        if item == FILLED or item in ("█", "■", "1", "#", "X", "x"):
            normalized.append("1")
        elif item == EMPTY or item in ("□", "0", ".", "_"):
            normalized.append("0")
        else:
            return None

    # Vizuální pořadí je shora dolů, proto se při převodu zpět obnoví původní směr bitů zdola nahoru.
    return "".join(reversed(normalized))


def letter_to_bits(letter: str) -> str:
    """Vrátí 5bitový kód pro písmeno A–Z po normalizaci vstupu."""
    normalized = _normalize_char(letter)
    return LETTER_TO_BITS.get(normalized, "")


def letter_to_visual_rows(letter: str) -> list[str]:
    """Vrátí pět vizuálních řádků reprezentujících jedno zašifrované písmeno."""
    bits = letter_to_bits(letter)
    if not bits:
        return ["", "", "", "", ""]
    return _bits_to_visual_column(bits)


def encrypt(text: str) -> str:
    """Zašifruje vstupní text do formátu Binárních čtverců.

    Písmena jsou převedena na svislé sloupce z pěti čtverců. Znaky mimo
    podporovanou abecedu se ve výstupu ponechávají jako symboly, aby se
    neztratila interpunkce ani struktura původní zprávy.
    """
    if text is None:
        return ""

    result_blocks: list[str] = []

    for source_line in str(text).splitlines() or [str(text)]:
        rows = ["", "", "", "", ""]
        has_content = False
        need_separator = False

        for original_char in source_line:
            if original_char.isspace():
                # Větší mezera odděluje slova a umožňuje jejich zpětnou rekonstrukci při dešifrování.
                if has_content:
                    for row_index in range(5):
                        rows[row_index] += "     "
                    need_separator = False
                continue

            normalized = _normalize_char(original_char)

            if normalized in LETTER_TO_BITS:
                glyph_rows = _bits_to_visual_column(LETTER_TO_BITS[normalized])
            else:
                # Nepodporované znaky se ponechávají jako symboly a zarovnávají se do středového řádku.
                glyph_rows = [" ", " ", original_char, " ", " "]

            if need_separator:
                for row_index in range(5):
                    rows[row_index] += " "

            for row_index in range(5):
                rows[row_index] += glyph_rows[row_index]

            has_content = True
            need_separator = True

        result_blocks.append("\n".join(row.rstrip() for row in rows))

    return "\n\n".join(result_blocks).rstrip()


def _decrypt_5bit_codes(text: str) -> str | None:
    """Dešifruje čistý 5bitový textový zápis, například: 00001 01000 01111 01010."""
    if not re.search(r"[01]{5}", text):
        return None

    output: list[str] = []
    index = 0
    text_len = len(text)

    while index < text_len:
        chunk = text[index:index + 5]

        if len(chunk) == 5 and all(char in "01" for char in chunk):
            output.append(BITS_TO_LETTER.get(chunk, "?"))
            index += 5
            continue

        char = text[index]
        if char.isspace():
            if output and output[-1] != " ":
                output.append(" ")
        else:
            output.append(char)
        index += 1

    return "".join(output).strip()


def _decrypt_compact_squares(text: str) -> str | None:
    """Dešifruje kompaktní jednořádkový zápis složený z pěti čtverců na znak.

    Příklad podporovaného formátu:
        ■□□□□ □□□■□
    """
    if FILLED not in text and EMPTY not in text:
        return None

    # Více neprázdných řádků indikuje plný kreslený výstup, který zpracovává samostatný dekodér.
    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if len(non_empty_lines) >= 5:
        return None

    output: list[str] = []
    tokens = re.split(r"(\s+)", text.strip())

    for token in tokens:
        if not token:
            continue
        if token.isspace():
            if output and output[-1] != " ":
                output.append(" ")
            continue

        if len(token) == 5 and all(char in (FILLED, EMPTY, "█", "■", "□") for char in token):
            bits = _visual_column_to_bits(list(token))
            output.append(BITS_TO_LETTER.get(bits or "", "?"))
        else:
            output.append(token)

    return "".join(output).strip()


def _split_visual_blocks(text: str) -> list[list[str]]:
    """Rozdělí víceřádkový kreslený výstup na samostatné bloky po pěti řádcích."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.strip() == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line.rstrip("\n"))

        if len(current) == 5:
            blocks.append(current)
            current = []

    if current:
        blocks.append(current)

    return blocks


def _decrypt_visual(text: str) -> str | None:
    """Dešifruje standardní pětřádkový kreslený výstup vytvořený funkcí encrypt()."""
    if FILLED not in text and EMPTY not in text and "█" not in text:
        return None

    blocks = _split_visual_blocks(text)
    if not blocks:
        return None

    decoded_blocks: list[str] = []

    for block in blocks:
        if len(block) != 5:
            continue

        width = max(len(line) for line in block)
        rows = [line.ljust(width) for line in block]
        output: list[str] = []
        x = 0

        while x < width:
            column = [rows[row_index][x] for row_index in range(5)]

            # Sloupec představující běžné písmeno.
            bits = _visual_column_to_bits(column)
            if bits is not None:
                output.append(BITS_TO_LETTER.get(bits, "?"))
                x += 1
                continue

            # Sloupec obsahující původní symbol, například interpunkci.
            symbol_chars = [
                char for char in column
                if char.strip() and char not in (FILLED, EMPTY, "█", "■", "□")
            ]
            if symbol_chars:
                output.append(symbol_chars[0])
                x += 1
                continue

            # Prázdné sloupce slouží jako oddělovače.
            # Jeden prázdný sloupec odděluje znaky, širší mezera reprezentuje mezeru mezi slovy.
            gap_start = x
            while x < width:
                gap_column = [rows[row_index][x] for row_index in range(5)]
                if any(char.strip() for char in gap_column):
                    break
                x += 1

            gap_width = x - gap_start
            if gap_width >= 3 and output and output[-1] != " ":
                output.append(" ")

        decoded = "".join(output).strip()
        if decoded:
            decoded_blocks.append(decoded)

    if not decoded_blocks:
        return None

    return "\n".join(decoded_blocks).strip()


def decrypt(text: str) -> str:
    """Dešifruje Binární čtverce zpět na běžný text.

    Funkce automaticky rozpoznává tři podporované vstupní formáty:
    1) pětřádkový kreslený výstup z encrypt(),
    2) textové 5bitové kódy typu 00001 01000 01111,
    3) kompaktní čtvercový zápis typu ■□□□□ □□□■□.
    """
    if text is None:
        return ""

    source = str(text)
    if not source.strip():
        return ""

    # Dekodéry se zkouší od nejkonkrétnějšího formátu po jednodušší textové varianty.
    for decoder in (_decrypt_visual, _decrypt_5bit_codes, _decrypt_compact_squares):
        decoded = decoder(source)
        if decoded is not None:
            return decoded

    return source


def get_key_data() -> dict:
    """Vrátí datovou strukturu pro společný generátor grafického klíče šifry."""
    return {
        "title": "Klíč šifry – Binární čtverce",
        "subtitle": "1 = plný čtvereček, 0 = prázdný čtvereček",
        "description": "Každé písmeno je jeden svislý sloupec z pěti čtverců. Čte se odspoda nahoru, takže poslední bit je nahoře.",
        "type": "binary_squares",
        "columns": 7,
        "items": [(letter, bits) for letter, bits in LETTER_TO_BITS.items()],
    }


def get_key_table() -> dict[str, str]:
    """Vrátí základní mapovací tabulku A–Z na odpovídající 5bitový kód."""
    return dict(LETTER_TO_BITS)


# Jednoduchý ruční test modulu při samostatném spuštění souboru.
if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    print(encrypted)
    print()
    print(decrypt(encrypted))



# ============================================================
# Grafický Qt výstup pro aplikaci
# ============================================================

try:
    from PySide6.QtCore import Qt, QRect, QSize
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import QWidget
except Exception:  # Modul zůstává použitelný i bez PySide6; v takovém režimu funguje pouze textová logika encrypt/decrypt.
    QWidget = None


if QWidget is not None:
    class BinarySquaresOutputWidget(QWidget):
        """Qt widget pro vizuální vykreslení šifry Binární čtverce.

        Widget vykresluje písmena jednoho slova jako souvislou mřížku,
        mezi slovy používá větší mezery a nepodporované znaky zachovává
        ve formě původních symbolů.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._text = ""
            self._available_width = 780
            self._cell = 24
            self._word_gap = 42
            self._symbol_gap = 18
            self._line_gap = 36
            self.setMinimumSize(260, 150)
            # V aplikačním UI se widget vykresluje s průhledným pozadím, aby plynule navazoval na grafický skin.
            # Bílé pozadí se doplňuje až při tisku nebo exportu v main.py.
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAutoFillBackground(False)

        def set_available_width(self, width: int) -> None:
            self._available_width = max(260, int(width or 780))
            self.updateGeometry()

        def set_plain_text(self, text: str) -> None:
            self._text = text or ""
            self.updateGeometry()
            self.update()

        def set_cipher_text(self, text: str) -> None:
            # main.py předává do widgetu původní text, nikoliv už hotový ASCII výstup.
            self.set_plain_text(text)

        def sizeHint(self) -> QSize:
            width = max(260, self._available_width)
            height = self._layout_size(width)[1]
            return QSize(width, max(140, height))

        def _tokens(self):
            tokens = []
            current = ""
            for char in self._text:
                normalized = _normalize_char(char)
                if normalized in LETTER_TO_BITS:
                    current += normalized
                    continue

                if current:
                    tokens.append(("word", current))
                    current = ""

                if char.isspace():
                    if not tokens or tokens[-1][0] != "space":
                        tokens.append(("space", " "))
                else:
                    tokens.append(("symbol", char))

            if current:
                tokens.append(("word", current))

            # Okrajové mezery se nebudou vykreslovat, protože by zbytečně posouvaly obsah výstupu.
            while tokens and tokens[0][0] == "space":
                tokens.pop(0)
            while tokens and tokens[-1][0] == "space":
                tokens.pop()
            return tokens

        def _token_width(self, token) -> int:
            kind, value = token
            if kind == "word":
                return len(value) * self._cell
            if kind == "space":
                return self._word_gap
            return int(self._cell * 2.15)

        def _layout(self, width: int):
            tokens = self._tokens()
            max_w = max(240, width - 20)
            lines = []
            line = []
            x = 0
            for token in tokens:
                token_w = self._token_width(token)
                if token[0] == "space":
                    # Mezera se nevykresluje jako znak; pouze zvětšuje horizontální odsazení dalšího bloku.
                    if line:
                        line.append(token)
                        x += token_w
                    continue

                if line and x + token_w > max_w:
                    while line and line[-1][0] == "space":
                        line.pop()
                    lines.append(line)
                    line = []
                    x = 0

                line.append(token)
                x += token_w

            if line:
                while line and line[-1][0] == "space":
                    line.pop()
                lines.append(line)

            return lines or [[]]

        def _layout_size(self, width: int):
            lines = self._layout(width)
            line_h = self._cell * 5
            total_h = 12 + len(lines) * line_h + max(0, len(lines) - 1) * self._line_gap + 12
            return width, total_h

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            # Pozadí se zde záměrně nekreslí, protože widget má být v UI transparentní.
            # Export nebo tisk si podklad doplní samostatně v hlavním aplikačním modulu.

            cell = self._cell
            line_h = cell * 5
            lines = self._layout(max(260, self.width()))
            y = 10

            for line in lines:
                x = 10
                for token in line:
                    kind, value = token
                    if kind == "space":
                        x += self._word_gap
                        continue

                    if kind == "word":
                        self._draw_word(painter, x, y, value)
                        x += len(value) * cell
                        continue

                    if kind == "symbol":
                        x += self._symbol_gap // 2
                        self._draw_symbol(painter, x, y, value)
                        x += int(cell * 2.15)

                y += line_h + self._line_gap

        def _draw_word(self, painter, x: int, y: int, word: str) -> None:
            cell = self._cell
            grid_pen = QPen(QColor("#6d6d6d"), max(1, int(cell * 0.045)))
            fill_dark = QColor("#3f3f3f")
            fill_light = QColor(255, 253, 248, 230)

            painter.setPen(grid_pen)
            for col, letter in enumerate(word):
                bits = LETTER_TO_BITS.get(letter, "00000")
                top_to_bottom = list(reversed(bits))
                for row, bit in enumerate(top_to_bottom):
                    rect = QRect(x + col * cell, y + row * cell, cell, cell)
                    painter.fillRect(rect, fill_dark if bit == "1" else fill_light)
                    painter.drawRect(rect)

        def _draw_symbol(self, painter, x: int, y: int, symbol: str) -> None:
            cell = self._cell
            font = QFont("Georgia", int(cell * 3.5))
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#3d3d3d"))
            rect = QRect(x, y - int(cell * 0.15), int(cell * 2.5), cell * 5 + int(cell * 0.3))
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, symbol)
