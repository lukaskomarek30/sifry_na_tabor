# -*- coding: utf-8 -*-
"""Univerzální pirátský generátor klíčů pro Šifrátor Mraveniště.

Umístění:
    C:\\Users\\lukas\\Desktop\\Šifry\\pirate_key_renderer.py

Cíl:
- tlačítko KLÍČ má fungovat u všech šifer,
- kreslené šifry se v klíči ukazují jako skutečné obrázky/symboly,
- běžné textové šifry se složí z jejich tabulek,
- klíč je responzivní a při tisku se vkládá jako PNG.
"""

from __future__ import annotations

import base64
import math
import os
import tempfile
from typing import Any, Iterable

from PySide6.QtCore import Qt, QRect, QRectF, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QWidget,
    QFileDialog,
    QMessageBox,
)

PARCHMENT = QColor("#f3dfad")
PARCHMENT_LIGHT = QColor("#fff1c9")
INK = QColor("#1c1208")
GOLD = QColor("#b88738")
BORDER = QColor("#2b1b0c")
BLACK = QColor("#111111")
WHITE = QColor("#fffdf5")
GRID = QColor("#3a2a18")
MUTED = QColor("#2b1b0c")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ============================================================
# Pomocné funkce
# ============================================================

def _normalize_items(items: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        if isinstance(item, dict):
            label = str(item.get("label", ""))
            value = item.get("value", item.get("bits", item.get("dots", "")))
            note = str(item.get("note", ""))
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            label = str(item[0])
            value = item[1]
            note = str(item[2]) if len(item) >= 3 else ""
        else:
            label = str(item)
            value = ""
            note = ""
        normalized.append({"label": label, "value": value, "note": note})
    return normalized


def _sort_items(items: list[tuple[Any, Any]]) -> list[tuple[Any, Any]]:
    def keyfn(item):
        key = str(item[0])
        if len(key) == 1 and key.isalpha():
            return (0, key)
        if len(key) == 1 and key.isdigit():
            return (1, key)
        return (2, key)
    return sorted(items, key=keyfn)


def _safe_columns(item_count: int, wanted: int, min_cols: int = 3, max_cols: int = 8) -> int:
    if item_count <= 0:
        return max(min_cols, min(wanted, max_cols))
    return max(min_cols, min(wanted, max_cols, item_count))


def _fit_font(painter: QPainter, rect: QRect, text: str, base_size: int, min_size: int, weight: int = QFont.Bold) -> QFont:
    size = int(base_size)
    while size >= int(min_size):
        font = QFont("Georgia", size, weight)
        painter.setFont(font)
        br = painter.boundingRect(rect, Qt.AlignCenter | Qt.TextWordWrap, str(text))
        if br.width() <= rect.width() and br.height() <= rect.height():
            return font
        size -= 1
    return QFont("Georgia", int(min_size), weight)


def _dots_from_value(value: Any) -> list[tuple[int, ...]]:
    if value is None:
        return [tuple()]
    if isinstance(value, str):
        return [tuple(int(ch) for ch in value if ch.isdigit())]
    if isinstance(value, tuple):
        return [tuple(int(x) for x in value)]
    if isinstance(value, list):
        if all(isinstance(x, int) for x in value):
            return [tuple(int(x) for x in value)]
        cells: list[tuple[int, ...]] = []
        for part in value:
            if isinstance(part, tuple):
                cells.append(tuple(int(x) for x in part))
            elif isinstance(part, list):
                cells.append(tuple(int(x) for x in part if isinstance(x, int)))
            elif isinstance(part, str):
                cells.append(tuple(int(ch) for ch in part if ch.isdigit()))
        return cells or [tuple()]
    return [tuple()]


def _pixmap_from_base64(data: str) -> QPixmap:
    pixmap = QPixmap()
    try:
        pixmap.loadFromData(base64.b64decode(data))
    except Exception:
        pass
    return pixmap


def _crop_pixmap_to_content(pixmap: QPixmap, margin: int = 8) -> QPixmap:
    """Ořízne průhledné okraje. Důležité pro kreslené symboly, aby nebyly malé."""
    if pixmap.isNull():
        return pixmap

    fmt = QImage.Format.Format_ARGB32 if hasattr(QImage, "Format") else QImage.Format_ARGB32
    image = pixmap.toImage().convertToFormat(fmt)
    w = image.width()
    h = image.height()
    if w <= 0 or h <= 0:
        return pixmap

    left, top, right, bottom = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if image.pixelColor(x, y).alpha() > 8:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)

    if right < left or bottom < top:
        return pixmap

    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(w - 1, right + margin)
    bottom = min(h - 1, bottom + margin)

    return QPixmap.fromImage(image.copy(left, top, right - left + 1, bottom - top + 1))



def _make_pixmap_black(pixmap: QPixmap, threshold: int = 5) -> QPixmap:
    """Přebarví neprůhledné části obrázku na černou.

    Používá se jen v generovaném KLÍČI, aby byly symboly na pergamenu dobře čitelné.
    Průhledné pozadí zůstane průhledné.
    """
    if pixmap.isNull():
        return pixmap

    fmt = QImage.Format.Format_ARGB32 if hasattr(QImage, "Format") else QImage.Format_ARGB32
    image = pixmap.toImage().convertToFormat(fmt)
    w = image.width()
    h = image.height()

    for y in range(h):
        for x in range(w):
            color = image.pixelColor(x, y)
            alpha = color.alpha()
            if alpha > threshold:
                # Ponecháme jemné okraje, ale uděláme je dost viditelné.
                new_alpha = max(alpha, 230)
                image.setPixelColor(x, y, QColor(0, 0, 0, new_alpha))
            else:
                image.setPixelColor(x, y, QColor(0, 0, 0, 0))

    return QPixmap.fromImage(image)

def _find_output_widget_class(module: Any):
    if module is None:
        return None
    preferred_names = [
        "BinarySquaresOutputWidget", "BrailleOutputWidget", "BritishFlagOutputWidget",
        "CtverecOutputWidget", "HebrejskyKrizOutputWidget", "MalyPolskyKrizOutputWidget",
        "MoonovoPismoOutputWidget", "MorseHoryOutputWidget", "MorsePilaOutputWidget",
        "MorseStromyOutputWidget", "MrizOutputWidget", "OknoOutputWidget",
        "PosunkovaAbecedaOutputWidget", "PseudoCinaOutputWidget", "SemaforOutputWidget",
        "SuperKrychleOutputWidget", "TanciciFigurkyOutputWidget", "TanciciFigurkyIIOutputWidget",
        "VelkyPolskyKrizOutputWidget", "VelkyPolskyKriz26OutputWidget",
        "ZednarskaSifraOutputWidget", "ZlomkyOutputWidget",
    ]
    for name in preferred_names:
        cls = getattr(module, name, None)
        if isinstance(cls, type):
            return cls
    for name in dir(module):
        if name.endswith("OutputWidget"):
            cls = getattr(module, name, None)
            if isinstance(cls, type):
                return cls
    return None


def _labels_from_module(module: Any) -> list[str]:
    """Najde rozumné znaky pro vizuální klíč."""
    if module is None:
        return list(ALPHABET)

    for attr in (
        "LETTER_TO_BITS", "CHAR_TO_DOTS", "MORSE_TABLE", "MORSE_CODE",
        "LETTER_TO_CODE", "ENCRYPT_MAP", "ENCODE_MAP", "HEBREW_CROSS_MAP",
        "SMALL_POLISH_CROSS_MAP", "LETTER_TO_COORDS", "SQUARE_POSITIONS",
        "LETTER_INFO", "POSITION_BY_TOKEN", "STYLE_BY_TOKEN", "DIRECTION_BY_TOKEN",
        "GLYPH_IMAGES",
    ):
        value = getattr(module, attr, None)
        if isinstance(value, dict) and value:
            keys = [str(k) for k in value.keys()]
            # pro klíč preferujeme písmena A-Z, čísla až za nimi
            letters = [k for k in keys if len(k) <= 2 and any(ch.isalpha() for ch in k)]
            digits = [k for k in keys if k.isdigit()]
            others = [k for k in keys if k not in letters and k not in digits and not k.startswith("REVERSE")]
            result = letters + digits + others
            if result:
                return sorted(result, key=lambda k: (0, k) if k.isalpha() else (1, k) if k.isdigit() else (2, k))

    return list(ALPHABET)


def _generic_data(cipher_name: str, mapping: dict[Any, Any], description: str = "") -> dict[str, Any]:
    items = _sort_items([(str(k), str(v)) for k, v in mapping.items()])
    count = len(items)
    columns = 7 if count >= 26 else 6 if count >= 18 else 5 if count >= 10 else 4
    return {
        "title": f"Klíč šifry – {cipher_name}",
        "type": "generic",
        "columns": columns,
        "items": items,
        "description": description,
    }


# ============================================================
# Widget klíče
# ============================================================

class PirateKeyWidget(QWidget):
    def __init__(self, key_data: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.key_data = key_data or {}
        self.items = _normalize_items(self.key_data.get("items", []))
        self.key_type = str(self.key_data.get("type", "generic"))
        self.print_mode = bool(self.key_data.get("print_mode") or self.key_data.get("_print_mode"))
        self.widget_class = self.key_data.get("widget_class")
        self._glyph_cache: dict[tuple[str, int, int], QPixmap] = {}
        self.setMinimumWidth(980)
        self.setMinimumHeight(self.estimate_height(1100))

    def sizeHint(self) -> QSize:
        width = max(980, self.width() or 1100)
        return QSize(width, self.estimate_height(width))

    def estimate_height(self, width: int) -> int:
        width = max(820, int(width or 1100))
        if self.key_type == "zlomky_key":
            return 360
        if self.key_type == "vlcacka_key":
            return 560
        cols = self.column_count(width)
        rows = max(1, math.ceil(len(self.items) / max(1, cols)))
        return 168 + rows * self.cell_height(width) + 62

    def column_count(self, width: int) -> int:
        forced = self.key_data.get("columns")
        if isinstance(forced, int) and forced > 0:
            return _safe_columns(len(self.items), forced, 2, 8)
        if self.key_type == "binary_squares":
            return _safe_columns(len(self.items), 7 if width >= 1250 else 5, 3, 7)
        if self.key_type == "braille":
            return _safe_columns(len(self.items), 7 if width >= 1250 else 5, 3, 7)
        if self.key_type in ("visual_widget", "image_map"):
            return _safe_columns(len(self.items), 5 if width >= 1250 else 4, 2, 5)
        if width >= 1450:
            return _safe_columns(len(self.items), 8, 3, 8)
        if width >= 1150:
            return _safe_columns(len(self.items), 6, 3, 7)
        return _safe_columns(len(self.items), 4, 3, 5)

    def cell_height(self, width: int) -> int:
        if self.key_type == "binary_squares":
            return 190
        if self.key_type == "braille":
            return 165
        if self.key_type in ("visual_widget", "image_map"):
            return 210 if width >= 1150 else 190
        return 120 if width >= 1000 else 132

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.estimate_height(max(980, self.width())))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = self.rect()

        if self.print_mode:
            # Tiskový režim: žádný pergamen, žádné zlaté pozadí.
            # Vykresluje se jen černý klíč na bílý papír.
            painter.fillRect(rect, WHITE)
            outer = rect.adjusted(12, 12, -12, -12)
        else:
            painter.fillRect(rect, PARCHMENT)
            painter.setPen(Qt.NoPen)
            for i in range(0, rect.height(), 54):
                painter.setBrush(QColor(255, 255, 255, 16 if (i // 54) % 2 == 0 else 8))
                painter.drawRect(0, i, rect.width(), 28)

            outer = rect.adjusted(12, 12, -12, -12)
            painter.setPen(QPen(BORDER, 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(outer, 18, 18)
            painter.setPen(QPen(GOLD, 2))
            painter.drawRoundedRect(outer.adjusted(8, 8, -8, -8), 12, 12)

        self._draw_header(painter, outer)
        self._draw_grid(painter, outer)

    def _draw_header(self, painter: QPainter, outer: QRect) -> None:
        title = str(self.key_data.get("title", "Klíč šifry"))
        subtitle = str(self.key_data.get("subtitle", "Šifrátor Mraveniště – pirátský klíč"))
        description = str(self.key_data.get("description", ""))

        title_rect = QRect(outer.left() + 28, outer.top() + 14, outer.width() - 56, 42)
        subtitle_rect = QRect(outer.left() + 28, outer.top() + 56, outer.width() - 56, 28)
        desc_rect = QRect(outer.left() + 44, outer.top() + 90, outer.width() - 88, 44)

        painter.setPen(INK)
        painter.setFont(_fit_font(painter, title_rect, title, 28, 17, QFont.Bold))
        painter.drawText(title_rect, Qt.AlignCenter, title)

        painter.setPen(MUTED)
        painter.setFont(_fit_font(painter, subtitle_rect, subtitle, 13, 9, QFont.Bold))
        painter.drawText(subtitle_rect, Qt.AlignCenter, subtitle)

        if description:
            painter.setPen(BLACK if self.print_mode else QColor("#3a2a18"))
            painter.setFont(_fit_font(painter, desc_rect, description, 11, 8, QFont.Normal))
            painter.drawText(desc_rect, Qt.AlignCenter | Qt.TextWordWrap, description)

        painter.setPen(QPen(BLACK if self.print_mode else GOLD, 2))
        painter.drawLine(outer.left() + 42, outer.top() + 144, outer.right() - 42, outer.top() + 144)

    def _draw_grid(self, painter: QPainter, outer: QRect) -> None:
        if self.key_type == "zlomky_key":
            self._draw_zlomky_key(painter, outer)
            return
        if self.key_type == "vlcacka_key":
            self._draw_vlcacka_key(painter, outer)
            return

        if not self.items:
            painter.setPen(INK)
            painter.setFont(QFont("Georgia", 18, QFont.Bold))
            painter.drawText(outer.adjusted(40, 170, -40, -40), Qt.AlignTop | Qt.AlignCenter, "Tato šifra zatím neposkytuje data klíče.")
            return

        left = outer.left() + 34
        top = outer.top() + 160
        width = outer.width() - 68
        cols = self.column_count(width)
        cell_w = width / max(1, cols)
        cell_h = self.cell_height(width)

        for index, item in enumerate(self.items):
            row = index // cols
            col = index % cols
            x = int(left + col * cell_w)
            y = int(top + row * cell_h)
            w = int(cell_w) + (1 if col == cols - 1 else 0)
            self._draw_cell(painter, QRect(x, y, w, int(cell_h)), item)

    def _draw_zlomky_key(self, painter: QPainter, outer: QRect) -> None:
        """Vykreslí klíč šifry Zlomky přesně jako tabulku ze vzoru.

        Horní řádek = písmena, prostřední řádek = čitatel 1–5,
        spodní řádek = jmenovatel / číslo skupiny 1–5.
        """
        groups = self.key_data.get("groups") or [
            list("ABCDE"),
            list("FGHIJ"),
            list("KLMNO"),
            list("PQRST"),
            list("UVXYZ"),
        ]

        left = outer.left() + 42
        top = outer.top() + 170
        width = outer.width() - 84

        # Responzivní výšky řádků.
        letter_h = 38
        numerator_h = 36
        denominator_h = 42
        table_h = letter_h + numerator_h + denominator_h

        y_letters = top
        y_numbers = top + letter_h
        y_denominator = top + letter_h + numerator_h
        bottom = top + table_h

        group_count = max(1, len(groups))
        group_w = width / group_count

        # Bílé/krémové pozadí tabulky, aby šlo dobře tisknout i číst.
        table_rect = QRect(int(left), int(top), int(width), int(table_h))
        painter.fillRect(table_rect, WHITE if self.print_mode else QColor("#fff1c9"))

        # Vnější rámeček a vodorovné čáry.
        painter.setPen(QPen(GRID, 2))
        painter.drawRect(table_rect)
        painter.drawLine(int(left), int(y_numbers), int(left + width), int(y_numbers))
        painter.drawLine(int(left), int(y_denominator), int(left + width), int(y_denominator))

        for group_index, letters in enumerate(groups):
            gx = left + group_index * group_w
            gx_i = int(gx)

            # Silnější svislá čára mezi skupinami.
            if group_index > 0:
                painter.setPen(QPen(GRID, 3))
                painter.drawLine(gx_i, int(top), gx_i, int(bottom))

            col_count = max(1, len(letters))
            col_w = group_w / col_count

            # Jemné svislé linky mezi písmeny v horní části.
            painter.setPen(QPen(GRID, 1))
            for col_index in range(1, col_count):
                x = int(gx + col_index * col_w)
                painter.drawLine(x, int(y_letters), x, int(y_denominator))

            # Písmena a čitatele.
            for col_index, letter in enumerate(letters):
                x = int(gx + col_index * col_w)
                w = int(col_w) + (1 if col_index == col_count - 1 else 0)

                letter_rect = QRect(x, int(y_letters), w, int(letter_h))
                num_rect = QRect(x, int(y_numbers), w, int(numerator_h))

                painter.setPen(INK)
                painter.setFont(_fit_font(painter, letter_rect.adjusted(2, 0, -2, 0), str(letter), 18, 10, QFont.Bold))
                painter.drawText(letter_rect, Qt.AlignCenter, str(letter))

                painter.setFont(_fit_font(painter, num_rect.adjusted(2, 0, -2, 0), str(col_index + 1), 16, 9, QFont.Bold))
                painter.drawText(num_rect, Qt.AlignCenter, str(col_index + 1))

            # Jmenovatel přes celou skupinu.
            denominator_rect = QRect(int(gx), int(y_denominator), int(group_w), int(denominator_h))
            painter.setPen(INK)
            painter.setFont(_fit_font(painter, denominator_rect.adjusted(2, 0, -2, 0), str(group_index + 1), 20, 11, QFont.Bold))
            painter.drawText(denominator_rect, Qt.AlignCenter, str(group_index + 1))

        # Pojistka: pravá silná hrana.
        painter.setPen(QPen(GRID, 2))
        painter.drawLine(int(left + width), int(top), int(left + width), int(bottom))


    def _draw_vlcacka_key(self, painter: QPainter, outer: QRect) -> None:
        """Vykreslí klíč Vlčácké šifry podle vzoru jako 3×3 skupiny.

        Každá skupina má nahoře čísla 1–3, pod nimi písmena a dole číslo
        skupiny 1–9. Znak CH se bere jako jeden znak.
        """
        groups = self.key_data.get("groups") or [
            ("1", ["A", "B", "C"]),
            ("2", ["D", "E", "F"]),
            ("3", ["G", "H", "CH"]),
            ("4", ["I", "J", "K"]),
            ("5", ["L", "M", "N"]),
            ("6", ["O", "P", "Q"]),
            ("7", ["R", "S", "T"]),
            ("8", ["U", "V", "W"]),
            ("9", ["X", "Y", "Z"]),
        ]

        normalized_groups: list[tuple[str, list[str]]] = []
        for item in groups:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                group_number = str(item[0])
                letters_source = item[1]
                if isinstance(letters_source, str):
                    # Pozor: CH je jeden znak, proto ho v textovém fallbacku ošetříme.
                    letters_source = letters_source.replace("CH", "#")
                    letters = [("CH" if ch == "#" else ch) for ch in letters_source]
                else:
                    letters = [str(x) for x in letters_source]
            else:
                continue
            normalized_groups.append((group_number, letters[:3]))

        if not normalized_groups:
            normalized_groups = [
                ("1", ["A", "B", "C"]), ("2", ["D", "E", "F"]), ("3", ["G", "H", "CH"]),
                ("4", ["I", "J", "K"]), ("5", ["L", "M", "N"]), ("6", ["O", "P", "Q"]),
                ("7", ["R", "S", "T"]), ("8", ["U", "V", "W"]), ("9", ["X", "Y", "Z"]),
            ]

        # Rozměry tabulky – drží se uprostřed a je responzivní.
        top = outer.top() + 170
        available_w = outer.width() - 120
        available_h = outer.height() - 230
        table_w = max(620, min(available_w, int(available_h * 1.65)))
        table_h = max(300, min(available_h, int(table_w * 0.52)))
        left = outer.center().x() - table_w // 2

        # Když je okno nízké, použijeme dostupné maximum a neposíláme kresbu mimo rámeček.
        if top + table_h > outer.bottom() - 45:
            table_h = max(260, outer.bottom() - 45 - top)
            table_w = min(available_w, int(table_h * 1.75))
            left = outer.center().x() - table_w // 2

        group_w = table_w / 3.0
        group_h = table_h / 3.0

        # Jemné světlé pozadí tabulky.
        table_rect = QRect(int(left), int(top), int(table_w), int(table_h))
        painter.fillRect(table_rect, WHITE if self.print_mode else QColor("#fff1c9"))

        # Linky 3×3 – podle vzoru výrazné černé/hnědé čáry.
        painter.setPen(QPen(BLACK, 3))
        for i in range(4):
            x = int(left + i * group_w)
            painter.drawLine(x, int(top), x, int(top + table_h))
        for i in range(4):
            y = int(top + i * group_h)
            painter.drawLine(int(left), y, int(left + table_w), y)

        number_color = BLACK if self.print_mode else QColor("#b88700")
        red = BLACK if self.print_mode else QColor("#d00000")

        for index, (group_number, letters) in enumerate(normalized_groups[:9]):
            row = index // 3
            col = index % 3
            gx = left + col * group_w
            gy = top + row * group_h

            # Vnitřní pozice ve skupině: 1,2,3 nahoře a písmena pod nimi.
            for pos in range(3):
                cx = gx + (pos + 0.5) * (group_w / 3.0)

                numerator_rect = QRect(
                    int(gx + pos * group_w / 3.0),
                    int(gy + group_h * 0.08),
                    int(group_w / 3.0),
                    int(group_h * 0.23),
                )
                letter_rect = QRect(
                    int(gx + pos * group_w / 3.0),
                    int(gy + group_h * 0.34),
                    int(group_w / 3.0),
                    int(group_h * 0.26),
                )

                painter.setPen(number_color)
                painter.setFont(_fit_font(painter, numerator_rect, str(pos + 1), 22, 12, QFont.Bold))
                painter.drawText(numerator_rect, Qt.AlignCenter, str(pos + 1))

                letter = letters[pos] if pos < len(letters) else ""
                painter.setPen(red if letter == "CH" else INK)
                painter.setFont(_fit_font(painter, letter_rect, letter, 18 if letter != "CH" else 15, 9, QFont.Bold))
                painter.drawText(letter_rect, Qt.AlignCenter, letter)

            # Číslo skupiny dole uprostřed.
            denominator_rect = QRect(
                int(gx),
                int(gy + group_h * 0.64),
                int(group_w),
                int(group_h * 0.30),
            )
            painter.setPen(number_color)
            painter.setFont(_fit_font(painter, denominator_rect, str(group_number), 25, 13, QFont.Bold))
            painter.drawText(denominator_rect, Qt.AlignCenter, str(group_number))


    def _draw_cell(self, painter: QPainter, cell: QRect, item: dict[str, Any]) -> None:
        header_h = 48
        painter.setPen(QPen(GRID, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(cell)

        header = QRect(cell.left(), cell.top(), cell.width(), header_h)
        painter.fillRect(header.adjusted(1, 1, -1, -1), WHITE if self.print_mode else PARCHMENT_LIGHT)
        painter.setPen(QPen(GRID, 2))
        painter.drawLine(cell.left(), cell.top() + header_h, cell.right(), cell.top() + header_h)

        painter.setPen(INK)
        painter.setFont(_fit_font(painter, header.adjusted(4, 2, -4, -2), item["label"], 22, 12, QFont.Bold))
        painter.drawText(header.adjusted(4, 2, -4, -2), Qt.AlignCenter, item["label"])

        body = QRect(cell.left() + 8, cell.top() + header_h + 6, cell.width() - 16, cell.height() - header_h - 12)
        if self.key_type == "binary_squares":
            self._draw_binary(painter, body, str(item.get("value", "")))
        elif self.key_type == "braille":
            self._draw_braille(painter, body, item.get("value"))
        elif self.key_type == "image_map":
            self._draw_image(painter, body, item.get("value"), str(item.get("note", "")))
        elif self.key_type == "visual_widget":
            self._draw_visual_widget(painter, body, item["label"])
        else:
            self._draw_generic(painter, body, item)

    def _draw_binary(self, painter: QPainter, body: QRect, bits: str) -> None:
        bits = "".join(ch for ch in bits if ch in "01")
        bits_rect = QRect(body.left(), body.top(), body.width(), 18)
        painter.setPen(INK)
        painter.setFont(_fit_font(painter, bits_rect, bits, 12, 8, QFont.Bold))
        painter.drawText(bits_rect, Qt.AlignCenter, bits)

        available_h = max(30, body.height() - 26)
        square = min(
            max(8, int(body.width() * 0.16)),
            max(8, int(available_h / 5)),
            22,
        )
        total_h = square * 5
        x = body.center().x() - square // 2
        y = body.top() + 24 + max(0, (available_h - total_h) // 2)
        visual_bits = list(reversed(bits)) if len(bits) == 5 else list(bits[:5])
        for row in range(5):
            value = visual_bits[row] if row < len(visual_bits) else "0"
            r = QRect(x, y + row * square, square, square)
            painter.setPen(QPen(QColor("#9b9b9b"), 1))
            painter.setBrush(BLACK if value == "1" else WHITE)
            painter.drawRect(r)

    def _draw_braille(self, painter: QPainter, body: QRect, value: Any) -> None:
        cells = _dots_from_value(value)
        radius = max(5, min(10, min(body.width() // 18, body.height() // 10)))
        gap_x = radius * 2 + 7
        gap_y = radius * 2 + 5
        one_cell_w = gap_x + radius * 2
        total_w = len(cells) * one_cell_w + max(0, len(cells) - 1) * 10
        total_h = gap_y * 2 + radius * 2
        start_x = body.center().x() - total_w // 2
        start_y = body.center().y() - total_h // 2
        positions = {1: (0, 0), 2: (0, 1), 3: (0, 2), 4: (1, 0), 5: (1, 1), 6: (1, 2)}
        for idx, dots in enumerate(cells):
            x0 = start_x + idx * (one_cell_w + 10)
            for number, (col, row) in positions.items():
                cx = x0 + col * gap_x + radius
                cy = start_y + row * gap_y + radius
                painter.setPen(QPen(QColor("#a8a8a8"), 1))
                painter.setBrush(BLACK if number in dots else WHITE)
                painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)

    def _draw_image(self, painter: QPainter, body: QRect, value: Any, note: str = "") -> None:
        pixmap = value if isinstance(value, QPixmap) else QPixmap()
        if pixmap.isNull() and isinstance(value, str):
            pixmap = _pixmap_from_base64(value)
        if not pixmap.isNull():
            pixmap = _crop_pixmap_to_content(pixmap, 6)
            pixmap = _make_pixmap_black(pixmap)
            target = body.adjusted(8, 8, -8, -22 if note else -8)
            scaled = pixmap.scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(target.center().x() - scaled.width() // 2, target.center().y() - scaled.height() // 2, scaled)
        if note:
            note_rect = QRect(body.left() + 4, body.bottom() - 20, body.width() - 8, 18)
            painter.setPen(MUTED)
            painter.setFont(_fit_font(painter, note_rect, note, 9, 7, QFont.Normal))
            painter.drawText(note_rect, Qt.AlignCenter, note)

    def _draw_visual_widget(self, painter: QPainter, body: QRect, label: str) -> None:
        if not isinstance(self.widget_class, type):
            self._draw_generic(painter, body, {"value": label})
            return

        cache_key = (label, max(1, body.width()), max(1, body.height()))
        pixmap = self._glyph_cache.get(cache_key)
        if pixmap is None:
            pixmap = self._render_visual_symbol(label, body)
            self._glyph_cache[cache_key] = pixmap

        if pixmap.isNull():
            self._draw_generic(painter, body, {"value": label})
            return

        target = body.adjusted(8, 8, -8, -8)
        scaled = pixmap.scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Pokud je symbol po poměrovém škálování pořád moc nízký, zvětšíme ho podle výšky
        # a případně ho omezíme na šířku buňky. To pomáhá hlavně u Morseových variant.
        min_h = int(target.height() * 0.42)
        if scaled.height() < min_h and pixmap.height() > 0:
            by_height = pixmap.scaledToHeight(min_h, Qt.SmoothTransformation)
            if by_height.width() <= target.width():
                scaled = by_height

        x = target.center().x() - scaled.width() // 2
        y = target.center().y() - scaled.height() // 2
        painter.drawPixmap(x, y, scaled)

    def _render_visual_symbol(self, label: str, body: QRect) -> QPixmap:
        try:
            widget = self.widget_class()
            # Velký pracovní canvas, symbol potom ořízneme podle obsahu.
            work_w = max(360, int(body.width() * 3.0))
            work_h = max(220, int(body.height() * 2.4))

            # Kreslené šifry mají vlastní měřítko. Pro klíč ho zvedneme.
            if hasattr(widget, "set_scale"):
                scale = max(1.15, min(3.0, body.height() / 72.0))
                try:
                    widget.set_scale(scale)
                except Exception:
                    pass

            if hasattr(widget, "set_available_width"):
                try:
                    widget.set_available_width(work_w)
                except Exception:
                    pass

            if hasattr(widget, "set_cipher_text"):
                widget.set_cipher_text(str(label))
            elif hasattr(widget, "set_plain_text"):
                widget.set_plain_text(str(label))
            elif hasattr(widget, "setText"):
                widget.setText(str(label))

            height = work_h
            if hasattr(widget, "calculate_required_height"):
                try:
                    height = max(work_h, int(widget.calculate_required_height(work_w)))
                except Exception:
                    pass
            widget.resize(work_w, height)
            widget.setMinimumSize(work_w, height)
            if hasattr(widget, "update_content_size"):
                try:
                    widget.update_content_size()
                except Exception:
                    pass

            pixmap = QPixmap(widget.size())
            pixmap.fill(Qt.transparent)
            widget.render(pixmap)
            cropped = _crop_pixmap_to_content(pixmap, 8)
            return _make_pixmap_black(cropped)
        except Exception:
            return QPixmap()

    def _draw_generic(self, painter: QPainter, body: QRect, item: dict[str, Any]) -> None:
        text = str(item.get("value", ""))
        if item.get("note"):
            text += "\n" + str(item.get("note"))
        painter.setPen(INK)
        rect = body.adjusted(8, 8, -8, -8)
        painter.setFont(_fit_font(painter, rect, text, 13, 7, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, text)


class PirateKeyDialog(QDialog):
    def __init__(self, key_data: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(str(key_data.get("title", "Klíč šifry")))
        self.resize(1180, 820)
        self.widget = PirateKeyWidget(key_data)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.widget)

        self.save_button = QPushButton("Uložit jako PNG")
        self.close_button = QPushButton("Zavřít")
        self.save_button.clicked.connect(self.save_png)
        self.close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addLayout(buttons)
        self.setStyleSheet("""
            QDialog { background: #1c1208; }
            QPushButton {
                color: #f3d79a;
                background: rgba(40, 28, 14, 230);
                border: 1px solid #c89a4c;
                border-radius: 8px;
                padding: 8px 18px;
                font: bold 13px Georgia;
            }
            QPushButton:hover { background: rgba(75, 48, 18, 240); }
        """)

    def save_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Uložit klíč jako PNG", "klic_sifry.png", "PNG obrázek (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        pixmap = QPixmap(self.widget.size())
        pixmap.fill(Qt.transparent)
        self.widget.render(pixmap)
        if pixmap.save(path, "PNG"):
            QMessageBox.information(self, "Uloženo", f"Klíč byl uložen:\n{path}")
        else:
            QMessageBox.warning(self, "Chyba", "Klíč se nepodařilo uložit.")


# ============================================================
# Vytvoření dat klíče pro všechny šifry
# ============================================================

def _make_vlcacka_key_data(cipher_name: str, module: Any) -> dict[str, Any] | None:
    """Vrátí speciální klíč pro Vlčáckou šifru jako 3×3 tabulku."""
    name = (cipher_name or "").strip().lower()
    groups = getattr(module, "GROUPS", None)
    has_char_to_code = isinstance(getattr(module, "CHAR_TO_CODE", None), dict)

    is_vlcacka = (
        "vlčáck" in name
        or "vlcack" in name
        or (has_char_to_code and isinstance(groups, dict) and set(str(k) for k in groups.keys()) >= set("123456789"))
    )
    if not is_vlcacka:
        return None

    if isinstance(groups, dict) and groups:
        normalized_groups = []
        for group_number in sorted(groups.keys(), key=lambda value: int(value) if str(value).isdigit() else str(value)):
            normalized_groups.append((str(group_number), [str(item) for item in groups[group_number]]))
    else:
        normalized_groups = [
            ("1", ["A", "B", "C"]),
            ("2", ["D", "E", "F"]),
            ("3", ["G", "H", "CH"]),
            ("4", ["I", "J", "K"]),
            ("5", ["L", "M", "N"]),
            ("6", ["O", "P", "Q"]),
            ("7", ["R", "S", "T"]),
            ("8", ["U", "V", "W"]),
            ("9", ["X", "Y", "Z"]),
        ]

    return {
        "title": f"Klíč šifry – {cipher_name}",
        "subtitle": "Šifrátor Mraveniště – pirátský klíč",
        "description": "Nahoře jsou čitatele 1–3, pod nimi písmena a dole číslo skupiny 1–9. CH je jeden znak.",
        "type": "vlcacka_key",
        "groups": normalized_groups,
        "items": [("Vlčácká šifra", "")],
    }


def _make_zlomky_key_data(cipher_name: str, module: Any) -> dict[str, Any] | None:
    """Vrátí speciální klíč pro šifru Zlomky.

    Nepoužívá kreslicí OutputWidget, protože ten pro běžné písmeno A vykreslí prostě A.
    Klíč musí být jako tabulka A–E / 1–5 / 1 podle vzoru.
    """
    name = (cipher_name or "").strip().lower()
    has_zlomky_widget = hasattr(module, "ZlomkyOutputWidget")
    groups = getattr(module, "GROUPS", None)

    if "zlomky" not in name and not has_zlomky_widget:
        return None

    if not isinstance(groups, (list, tuple)) or not groups:
        groups = ["ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVXYZ"]

    normalized_groups: list[list[str]] = []
    for group in groups:
        if isinstance(group, str):
            normalized_groups.append(list(group))
        else:
            normalized_groups.append([str(item) for item in group])

    return {
        "title": f"Klíč šifry – {cipher_name}",
        "subtitle": "Šifrátor Mraveniště – pirátský klíč",
        "description": "Nahoře jsou písmena, pod nimi čitatel 1–5 a dole jmenovatel / číslo skupiny 1–5.",
        "type": "zlomky_key",
        "groups": normalized_groups,
        "items": [("Zlomky", "")],
    }


def _make_image_key_data(cipher_name: str, module: Any) -> dict[str, Any] | None:
    images = getattr(module, "GLYPH_IMAGES", None)
    if not isinstance(images, dict) or not images:
        return None
    return {
        "title": f"Klíč šifry – {cipher_name}",
        "subtitle": "Šifrátor Mraveniště – pirátský klíč",
        "description": "Obrázkový klíč šifry.",
        "type": "image_map",
        "columns": 5,
        "items": [(str(k), v) for k, v in _sort_items(list(images.items()))],
    }


def _make_visual_key_data(cipher_name: str, module: Any) -> dict[str, Any] | None:
    widget_class = _find_output_widget_class(module)
    if widget_class is None:
        return None

    # Binární čtverce a Braille mají hezčí speciální get_key_data(), takže je necháme být.
    if hasattr(module, "LETTER_TO_BITS") or hasattr(module, "CHAR_TO_DOTS"):
        return None

    labels = _labels_from_module(module)
    if not labels:
        labels = list(ALPHABET)

    return {
        "title": f"Klíč šifry – {cipher_name}",
        "subtitle": "Šifrátor Mraveniště – pirátský klíč",
        "description": "Klíč je vykreslený stejnými symboly, jaké používá šifra ve výsledku.",
        "type": "visual_widget",
        "columns": 5,
        "widget_class": widget_class,
        "items": [(label, label) for label in labels],
    }


def _make_known_table_key_data(cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    # Caesarova šifra má být vždy podle aktuálního nastavení v UI.
    if (cipher_name or '').strip().lower() == 'caesarova šifra' and hasattr(module, 'encrypt') and hasattr(module, 'ALPHABET'):
        alphabet = str(getattr(module, 'ALPHABET', ALPHABET)) or ALPHABET
        shift = 3
        direction = 'dopředu'
        if isinstance(context, dict):
            try:
                shift = int(context.get('caesar_shift', 3))
            except Exception:
                shift = 3
            direction = str(context.get('caesar_direction', 'dopředu'))
        direction_norm = direction.strip().lower()
        is_back = 'dozadu' in direction_norm
        signed_shift = -shift if is_back else shift
        mapping: dict[str, str] = {}
        for letter in alphabet:
            try:
                mapping[letter] = str(module.encrypt(letter, signed_shift)).upper()
            except Exception:
                pass
        desc_dir = 'dozadu' if is_back else 'dopředu'
        return {
            'title': f'Klíč šifry – {cipher_name}',
            'subtitle': 'Šifrátor Mraveniště – pirátský klíč',
            'description': f'Aktuální klíč: posun o {shift} {desc_dir}.',
            'type': 'generic',
            'columns': 7,
            'items': _sort_items([(str(k), str(v)) for k, v in mapping.items()]),
        }

    # Textové šifry bez vlastního kresleného výstupu.
    if hasattr(module, "MORSE_TABLE"):
        return _generic_data(cipher_name, getattr(module, "MORSE_TABLE"), "Morseova abeceda.")

    if hasattr(module, "KEYPAD"):
        return _generic_data(cipher_name, getattr(module, "KEYPAD"), "Mobilní klávesnice: číslo určuje klávesu a počet opakování určuje písmeno.")

    if hasattr(module, "ENCODE_MAP"):
        return _generic_data(cipher_name, getattr(module, "ENCODE_MAP"), "Převod znaků podle klíče šifry.")

    if hasattr(module, "LETTER_TO_CODE"):
        return _generic_data(cipher_name, getattr(module, "LETTER_TO_CODE"), "Převod písmen na kód.")

    if hasattr(module, "ENCRYPT_MAP"):
        return _generic_data(cipher_name, getattr(module, "ENCRYPT_MAP"), "Převod písmen podle klíče.")

    # Caesar a Atbash často nemají hotový dict, vytvoříme ho ručně.
    if hasattr(module, "ALPHABET") and hasattr(module, "encrypt"):
        alphabet = str(getattr(module, "ALPHABET", ALPHABET))
        mapping: dict[str, str] = {}
        for letter in alphabet:
            try:
                mapping[letter] = str(module.encrypt(letter))
            except Exception:
                pass
        if mapping:
            return _generic_data(cipher_name, mapping, "Převod písmen podle aktuální logiky šifry.")

    return None


def _make_fallback_key_data(cipher_name: str, module: Any) -> dict[str, Any] | None:
    # Nouzově najdeme první neprázdný slovník v modulu.
    best_name = ""
    best_dict = None
    preferred = (
        "LETTER_TO_BITS", "MORSE_CODE", "MORSE_TABLE", "LETTER_TO_CODE", "ENCRYPT_MAP", "ENCODE_MAP",
        "HEBREW_CROSS_MAP", "SMALL_POLISH_CROSS_MAP", "LETTER_TO_COORDS", "SQUARE_POSITIONS",
        "LETTER_INFO", "POSITION_BY_TOKEN", "STYLE_BY_TOKEN", "DIRECTION_BY_TOKEN",
    )
    for name in preferred + tuple(dir(module)):
        if str(name).startswith("_") or str(name).startswith("REVERSE"):
            continue
        value = getattr(module, name, None)
        if isinstance(value, dict) and value:
            best_name = str(name)
            best_dict = value
            break

    if best_dict is None:
        return None

    mapping = {str(k): str(v) for k, v in best_dict.items()}
    return _generic_data(cipher_name, mapping, f"Náhradní klíč vytvořený automaticky z tabulky {best_name}.")


def make_key_data_from_module(cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if module is None:
        return None

    # 1) Ručně připravený klíč v logice šifry.
    if hasattr(module, "get_key_data"):
        try:
            data = module.get_key_data()
            if isinstance(data, dict):
                data.setdefault("title", f"Klíč šifry – {cipher_name}")
                data.setdefault("subtitle", "Šifrátor Mraveniště – pirátský klíč")
                return data
        except Exception:
            pass

    # 2) Jednoduchá tabulka get_key_table().
    if hasattr(module, "get_key_table"):
        try:
            table = module.get_key_table()
            if isinstance(table, dict) and table:
                return _generic_data(cipher_name, table, "Klíč vytvořený z get_key_table().")
        except Exception:
            pass

    # 3) Speciální ručně kreslený klíč pro Zlomky.
    data = _make_zlomky_key_data(cipher_name, module)
    if data:
        return data

    # 3b) Speciální ručně kreslený klíč pro Vlčáckou šifru.
    data = _make_vlcacka_key_data(cipher_name, module)
    if data:
        return data

    # 4) Obrázkové šifry – posunková, semafor, tančící figurky atd.
    data = _make_image_key_data(cipher_name, module)
    if data:
        return data

    # 4) Kreslené šifry – klíč zobrazíme stejným OutputWidgetem jako výsledek.
    data = _make_visual_key_data(cipher_name, module)
    if data:
        return data

    # 5) Známé textové tabulky.
    data = _make_known_table_key_data(cipher_name, module, context)
    if data:
        return data

    # 6) Nouzový fallback, aby se už neukazovalo „klíč není dostupný“.
    data = _make_fallback_key_data(cipher_name, module)
    if data:
        return data

    # 7) Poslední pojistka – alespoň A-Z, aby dialog nikdy nespadl.
    return {
        "title": f"Klíč šifry – {cipher_name}",
        "subtitle": "Šifrátor Mraveniště – pirátský klíč",
        "description": "Pro tuto šifru nebyla nalezena tabulka. Zobrazuje se základní abeceda jako náhradní klíč.",
        "type": "generic",
        "columns": 6,
        "items": [(letter, letter) for letter in ALPHABET],
    }


def show_key_dialog(parent: QWidget | None, cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> bool:
    data = make_key_data_from_module(cipher_name, module, context)
    if not data:
        data = {
            "title": f"Klíč šifry – {cipher_name}",
            "subtitle": "Šifrátor Mraveniště – pirátský klíč",
            "description": "Náhradní základní klíč, protože logika šifry neposkytla žádná data.",
            "type": "generic",
            "columns": 6,
            "items": [(letter, letter) for letter in ALPHABET],
        }
    dialog = PirateKeyDialog(data, parent)
    dialog.exec()
    return True


def save_key_png_for_module(cipher_name: str, module: Any, output_path: str, width: int = 1500, context: dict[str, Any] | None = None, print_mode: bool = False) -> bool:
    data = make_key_data_from_module(cipher_name, module, context)
    if not data:
        return False

    data = dict(data)
    if print_mode:
        data["_print_mode"] = True

    widget = PirateKeyWidget(data)
    width = max(1000, int(width or 1500))
    height = widget.estimate_height(width)
    widget.resize(width, height)
    widget.setMinimumSize(width, height)

    pixmap = QPixmap(widget.size())
    pixmap.fill(WHITE if print_mode else Qt.transparent)
    widget.render(pixmap)

    folder = os.path.dirname(output_path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    return bool(pixmap.save(output_path, "PNG"))


# ============================================================
# RYCHLEJŠÍ RENDERER – GLOBÁLNÍ CACHE SYMBOLŮ A PNG KLÍČŮ
# ============================================================

_GLOBAL_VISUAL_SYMBOL_CACHE = {}
_GLOBAL_KEY_DATA_CACHE = {}
_GLOBAL_KEY_PNG_CACHE = {}

try:
    _ORIGINAL_RENDER_VISUAL_SYMBOL_FAST = PirateKeyWidget._render_visual_symbol

    def _render_visual_symbol_fast_cached(self, label: str, body: QRect) -> QPixmap:
        widget_name = getattr(self.widget_class, "__name__", str(self.widget_class))
        cache_key = (
            widget_name,
            str(label),
            max(1, int(body.width() / 25)),
            max(1, int(body.height() / 25)),
            bool(getattr(self, "print_mode", False)),
        )
        pixmap = _GLOBAL_VISUAL_SYMBOL_CACHE.get(cache_key)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            return pixmap
        pixmap = _ORIGINAL_RENDER_VISUAL_SYMBOL_FAST(self, label, body)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            # Aby cache nerostla donekonečna.
            if len(_GLOBAL_VISUAL_SYMBOL_CACHE) > 900:
                _GLOBAL_VISUAL_SYMBOL_CACHE.clear()
            _GLOBAL_VISUAL_SYMBOL_CACHE[cache_key] = pixmap
        return pixmap

    PirateKeyWidget._render_visual_symbol = _render_visual_symbol_fast_cached
except Exception:
    pass


def _fast_context_key(context):
    if isinstance(context, dict):
        return tuple(sorted((str(k), str(v)) for k, v in context.items()))
    return str(context)


def _fast_module_key(module):
    path = getattr(module, "__file__", "") if module is not None else ""
    mtime = 0
    try:
        if path and os.path.exists(path):
            mtime = int(os.path.getmtime(path))
    except Exception:
        pass
    return (path, mtime)

try:
    _ORIGINAL_MAKE_KEY_DATA_FAST = make_key_data_from_module

    def make_key_data_from_module(cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        cache_key = (str(cipher_name), _fast_module_key(module), _fast_context_key(context))
        cached = _GLOBAL_KEY_DATA_CACHE.get(cache_key)
        if isinstance(cached, dict):
            return cached
        data = _ORIGINAL_MAKE_KEY_DATA_FAST(cipher_name, module, context)
        if isinstance(data, dict):
            if len(_GLOBAL_KEY_DATA_CACHE) > 200:
                _GLOBAL_KEY_DATA_CACHE.clear()
            _GLOBAL_KEY_DATA_CACHE[cache_key] = data
        return data
except Exception:
    pass

try:
    _ORIGINAL_SAVE_KEY_PNG_FAST = save_key_png_for_module

    def save_key_png_for_module(cipher_name: str, module: Any, output_path: str, width: int = 1500, context: dict[str, Any] | None = None, print_mode: bool = False) -> bool:
        cache_key = (str(cipher_name), _fast_module_key(module), _fast_context_key(context), int(width or 1500), bool(print_mode))
        cached_path = _GLOBAL_KEY_PNG_CACHE.get(cache_key)
        if cached_path and os.path.exists(cached_path):
            try:
                if os.path.abspath(cached_path) != os.path.abspath(output_path):
                    import shutil
                    shutil.copy2(cached_path, output_path)
                return True
            except Exception:
                pass

        ok = bool(_ORIGINAL_SAVE_KEY_PNG_FAST(cipher_name, module, output_path, width=width, context=context, print_mode=print_mode))
        if ok and os.path.exists(output_path):
            if len(_GLOBAL_KEY_PNG_CACHE) > 120:
                _GLOBAL_KEY_PNG_CACHE.clear()
            _GLOBAL_KEY_PNG_CACHE[cache_key] = output_path
        return ok
except Exception:
    pass



# ============================================================
# PŘEDNAČTENÍ KLÍČE PRO MAIN.PY
# ============================================================

def preload_key_cache_for_module(cipher_name: str, module: Any, context: dict[str, Any] | None = None, width: int = 1400) -> bool:
    """Předpřipraví cache klíče bez otevírání dialogu.

    Volá se z main.py přes QTimer po šifrování. Renderuje tiskovou i běžnou
    variantu do dočasného souboru, čímž se zahřeje cache symbolů a PNG.
    """
    try:
        import tempfile
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in str(cipher_name or "klic")).strip("_") or "klic"
        base = os.path.join(tempfile.gettempdir(), f"sifrator_preload_{safe_name}")
        ok_print = save_key_png_for_module(cipher_name, module, base + "_print.png", width=width, context=context, print_mode=True)
        ok_ui = save_key_png_for_module(cipher_name, module, base + "_ui.png", width=width, context=context, print_mode=False)
        return bool(ok_print or ok_ui)
    except Exception:
        return False

# ============================================================
# NEMRZNOUCÍ OTEVŘENÍ KLÍČE
# ============================================================
# Dialog se otevře okamžitě s textem „Připravuji klíč…“.
# Samotné sestavení a vykreslení klíče začne až po zobrazení okna.
# Díky tomu kliknutí na KLÍČ nepůsobí jako zamrznutí aplikace.

class AsyncPirateKeyDialog(QDialog):
    def __init__(self, cipher_name: str, module: Any, context: dict[str, Any] | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QTimer

        self.cipher_name = cipher_name
        self.module = module
        self.context = context
        self.widget = None
        self.scroll = None

        self.setWindowTitle(f"Klíč šifry – {cipher_name}")
        self.resize(1180, 820)

        self.loading_label = QLabel("Připravuji klíč…\n\nOkno je otevřené hned, aby aplikace nepůsobila zaseknutě.", self)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #f3d79a; background: #1c1208; font: bold 18px Georgia; padding: 40px;")

        self.save_button = QPushButton("Uložit jako PNG")
        self.close_button = QPushButton("Zavřít")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_png)
        self.close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)

        self.layout_root = QVBoxLayout(self)
        self.layout_root.addWidget(self.loading_label, 1)
        self.layout_root.addLayout(buttons)
        self.setStyleSheet("""
            QDialog { background: #1c1208; }
            QPushButton {
                color: #f3d79a;
                background: rgba(40, 28, 14, 230);
                border: 1px solid #c89a4c;
                border-radius: 8px;
                padding: 8px 18px;
                font: bold 13px Georgia;
            }
            QPushButton:hover { background: rgba(75, 48, 18, 240); }
        """)

        QTimer.singleShot(80, self._load_key)

    def _load_key(self):
        from PySide6.QtWidgets import QScrollArea
        try:
            data = make_key_data_from_module(self.cipher_name, self.module, self.context)
            if not data:
                data = {
                    "title": f"Klíč šifry – {self.cipher_name}",
                    "subtitle": "Šifrátor Mraveniště – pirátský klíč",
                    "description": "Náhradní základní klíč, protože logika šifry neposkytla žádná data.",
                    "type": "generic",
                    "columns": 6,
                    "items": [(letter, letter) for letter in ALPHABET],
                }

            self.widget = PirateKeyWidget(data)
            self.scroll = QScrollArea(self)
            self.scroll.setWidgetResizable(True)
            self.scroll.setWidget(self.widget)

            self.layout_root.removeWidget(self.loading_label)
            self.loading_label.deleteLater()
            self.layout_root.insertWidget(0, self.scroll, 1)
            self.save_button.setEnabled(True)
        except Exception as error:
            self.loading_label.setText(f"Klíč se nepodařilo připravit:\n\n{error}")

    def save_png(self) -> None:
        if self.widget is None:
            QMessageBox.information(self, "Klíč se připravuje", "Počkej, až se klíč dokončí.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Uložit klíč jako PNG", "klic_sifry.png", "PNG obrázek (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        pixmap = QPixmap(self.widget.size())
        pixmap.fill(Qt.transparent)
        self.widget.render(pixmap)
        if pixmap.save(path, "PNG"):
            QMessageBox.information(self, "Uloženo", f"Klíč byl uložen:\n{path}")
        else:
            QMessageBox.warning(self, "Chyba", "Klíč se nepodařilo uložit.")


def show_key_dialog_nonblocking(parent: QWidget | None, cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> bool:
    dialog = AsyncPirateKeyDialog(cipher_name, module, context, parent)
    dialog.exec()
    return True

# Původní volání show_key_dialog také přesměrujeme na nemrznoucí variantu.
def show_key_dialog(parent: QWidget | None, cipher_name: str, module: Any, context: dict[str, Any] | None = None) -> bool:
    return show_key_dialog_nonblocking(parent, cipher_name, module, context)

