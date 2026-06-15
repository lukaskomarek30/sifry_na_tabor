# ============================================================
# SuperKrychle - logika + kreslení přes QPainter/QPixmap
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\SuperKrychle\superkrychle.py
#
# Klíč je vložený přímo do souboru jako obrázkové znaky A-Z
# vyříznuté z dodaného klíče. Není potřeba žádný font ani externí obrázky.
#
# Pravidla:
# - česká diakritika se převede na základní znaky
# - symboly jako ?, . , - ! : ; / zůstávají symboly
# - výsledek se kreslí přes QPainter
#
# Soubor obsahuje:
# - encrypt(text)
# - decrypt(text)
# - SuperKrychleOutputWidget pro kreslený výstup
# ============================================================

import base64
import unicodedata

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


GLYPH_IMAGES = {
    "A": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAoElEQVR42u3WzQ2AIAwF4IdhFYdwByd0D1ZwBS9u4QB6MiEaI7+lmteEhBP5gNJitmWCxuigNAj7PWwHMGuEjQCGlrgnmPNwu7YcO3FogXtLfgfAtMCFvkrxkwuFiV9rTB0TxcUWWDFcSuUXwaW2pOq4nF5ZFZfbxKvhSvwurriUcQtbaIPOmxt+FAkjjDDCCCOsftiCa/VaYStzjLAvwQ53tyuppvP+vwAAAABJRU5ErkJggg==",
    "B": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAlCAYAAAAuqZsAAAAAi0lEQVR42u3Wuw3AIAwEUByx/wBZLINkAGgoUgWw8Qd0lmjRQwYf9D53ilhXClqAHQ8rbYWD0QcYrpWuuN4dc8ONXH4X3OirNMfNjAtT3OwcM8NxBqwJjjv51XGSSFLFSbNSDbcixFVw+SfEOVWEh+vCSICiKK3ERxEwwAADDLCTYXnhXoRWArYTrAJrkBOz/bhmPwAAAABJRU5ErkJggg==",
    "C": "iVBORw0KGgoAAAANSUhEUgAAABkAAAAmCAYAAAAxxTAbAAAAkklEQVR42u3WwQ2AIAwF0F/j0YXcwS3cyrgGK7iCgzAAXCTxAhRoTUzaBd6h/R/I3we0Z8IHY4gIEgBc2sgGYJWCcoiThEo7EYNqixeBONc1DHFPeAhqyUk31BrGN3RqJj5BOwCvWSsJWp52UOuuBKEGjRYkC5oLBdkzAQBxEeoE7GU0xBBDDMn8OkkbcbaT/yARAzIf/hhGryYAAAAASUVORK5CYII=",
    "D": "iVBORw0KGgoAAAANSUhEUgAAACcAAAAlCAYAAADBa/A+AAAAnElEQVR42u3WwQ2AIAwFUL5xFLdxQ+dwFw+O4QB66YEDiRShrcknabyRh0p/cR1birqmFHgR1xu3SIXEnVKrYq9bajgO8tyVQLN/zh34diFcgTW31Q1Y20pcgJo+Zw7UNmFTYEtCmAFb48sE+CVbc2DI4EcWXSGnEkQfmVAYADRVnIDmAQdGtDfHSZg44ogjjjji+gc/+FmJ+zvuAXb1HslYf9PyAAAAAElFTkSuQmCC",
    "E": "iVBORw0KGgoAAAANSUhEUgAAACcAAAAlCAYAAADBa/A+AAAAo0lEQVR42u3WwQ2AIAwFUGoYxSlcwQ2dwxlcwUEcAC+acMBISWlr/CSNJ8kTpB869iV4HUNwPID7FS5dNTPmut/pjqPruTKBattqDnz750yBNQfCDFh7Wk2AnFaiDuT2OVVgSxNWA7YmRA50GV+UJYPLbO0KlAh+0l65LQvymipdADg1lhDxATc1fGiSXklcNoEDDjjggANOdkTBuQjbCtzXcSfXnyu8TmdPDgAAAABJRU5ErkJggg==",
    "F": "iVBORw0KGgoAAAANSUhEUgAAABkAAAAlCAYAAAC3UUK1AAAAgklEQVR42u3VwQ2AIAwFUGq6/wAu5iAOoBcPXpD+9mNC8ptwAx6htNh57G12bO2HEEJBrmcg0V3TQ+y1cOp10aBRTihQJPFlKPq6ShDyhNMQWicpKFOMMJSteAiqtJUwVO1dIYjRIG00wT+aHS08ezrkYPoZhQgRsiLixL1MOVkHuQGJThOxa7Qu+AAAAABJRU5ErkJggg==",
    "G": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAAAhUlEQVR42mP8fH0Ww2AETAyDFIw6bNg77D8UkwLI0UOywxiRLBt0UTmgjiOUxgbMccQk/gFxHLG5ku6OI6W4oKvjSC3H6OY4cgpYZMd5D7aSH+a4LbRyHCVVErLjBl1dSbM0R41KnJEWIcZCJXMYkULtPzU8x0JFTzIOtqgcbSiOOgwfAABacxOW0CIXzwAAAABJRU5ErkJggg==",
    "H": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAAAf0lEQVR42mP8fH0Ww2AETAyDFIw6bNg77D8UkwLI0UOywxiRLBt0UTmgjiOUxgbMccQk/gFxHLG5ku6OI6W4oKvjSC3HYI47RmuHsZChhxGpzGIcbCU/zaOVkiqJpo6jtK6kmeOoUYkz0jPxUxIC/6nhORZ6hsJoQ3HUYYMJAAANlBReAVUzMAAAAABJRU5ErkJggg==",
    "I": "iVBORw0KGgoAAAANSUhEUgAAABkAAAAYCAYAAAAPtVbGAAAApUlEQVR42u2VwQ2DMAxFH4gjbMESsEKZpp2DDsAcZIV2hKpiDHpPL47EBRFD3EOFpVzz7Pzvn2x+DVhXzg/qhCSBeKBW3uXlREM6YAIulpM4AY3Aw1KTAGqOgraETwKKcdcSdLW0sAOeQL/HDJo9aYGbmEEFKpRN3YG3gD5AZbXxQaNybflSxUrQiBjQkexqZSKA2TIgl0+nFt6TsNYg2flp/TfkC532Hn18ktBaAAAAAElFTkSuQmCC",
    "J": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAwUlEQVR42u3Yyw2AIAwAUDCMoku7mBe3cAC8eDAapP82RBKOxhcs/ZiPbU0R15SCrh82PKxeOxws34DhPqUrrhdjbjhI8LvgoLfSHIdJF6Y4bB4zw1ESrAmOmvnVcZySpIrj1ko1nEQRV8FJdRfLo/hj92sVIdjeOMVw/ViNCBOJOa0TY+M0W2sWTrvnJ+MshhESzmpKQuMsxzcUznquBOM8Bl4QzmsS7+I8fxF84orCi7DPzNFOrNWZhIGlHzY07ATJsSynloy4JwAAAABJRU5ErkJggg==",
    "K": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAlCAYAAAAuqZsAAAAAvElEQVR42u3YOw6AIAwG4GIY9f6JF/MguuPi4CR98LeNoYmj8TNAH5Tz2CljLJQ0Juz3sPY86WDlBUy3lKG43h4Lw3E2fwiOeyrdcZJ04YqT5jE3nCbBuuC0mR+Os5QkKM5aK2G4EUUcgqsfRVwTzfhzXVgxoC4i2jL2Y+uIZUXAhuw5VAdrxiFbaxMO3fOrcR7DiArnNSWJcZ7jmwjnPVeycREDLwsXNYl3cZFXBJ+4CvjQkHfmbc+EoeMGn4Qgv/vSDTMAAAAASUVORK5CYII=",
    "L": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAxElEQVR42u3YwQ2AIAwFUDCO4jhO6B7O4sUtHAAvmnDStvB/G2MTj8YXKC01H9uSIsaQgsYP+zysXE84WK6A4bbSFfeWY244SfK74KSnko7TlAsqTlvHaDhLgaXgrJUfjmtpSVBca6+E4Xo0cQhufGjiligVFALLRlQ3HOo+ViLCuuQcasWaccirdRMOfec34xjDiAnHmpLUOOb4psKx58pZimPDVinOYxJfJdvq+YvgETcCPqR9Z4q2YnfsUWHph30adgLaDSO0jezX4gAAAABJRU5ErkJggg==",
    "M": "iVBORw0KGgoAAAANSUhEUgAAACcAAAAlCAYAAADBa/A+AAAAzElEQVR42u2YzQ2AIAyFKXEUtnFD53AXD47hAHqBhAOJlNrXJtKEcIJ8/PX1QdexBa8Rg+OYcL+Cu3NbGXOVMepwlPudCQg7VnPAtztnCtjzIMwAe1+rCSAnlcABuXkOCjiShGGAowoBAZTIVw3oUlupki6Xwk/eqxJqFACcllqTLkqLJk871yqfkke4smunNM1E5WMV5UHNMl0MqO0hRIAIgzMMiHJfQ4BIa8gGRPtWFqCFqe4GtHL8XYCW3xE1oLrw09dj5i/ThEPHAxXNKu1SXC6aAAAAAElFTkSuQmCC",
    "N": "iVBORw0KGgoAAAANSUhEUgAAACcAAAAlCAYAAADBa/A+AAAA1ElEQVR42u2YwQ2AIAxFwTiKU7gCGzqHM7iCB8dwAL1g0oOJLdDfJtKk8YS+gO3vJ577ErzGEBxHh/sV3JUzCd71rFGHi/m5CgFhx2oO+PXPmQJyCsIMkFutJoCSVgIHlPY5KGBJE4YBlioEBLBGviigS22NRLpcCn9E79xGhJyTNJI23Jx3RJKhdZFozXOrV7hmRaK1c00ANcf0akBtD1EFiDA4FHDy6L4ewEPSZpDWUDwsoH2rCNDCVLMBrRw/C9DyOoICvlbxqPCxZmv6LVOHQ8cNmgkq0gOHom8AAAAASUVORK5CYII=",
    "O": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAA2klEQVR42u2YwQ2DMAxFvyu26zbdowuwR2fpIO09vYCEONA49rcthKVInMzjJ7H9kc97RsW4oWhcYKcHawAeylxtWVQwAfD0fJHnVspGiXJnLA2u5/CnwPXeynA4TbkIhdPWsTC4kQIbAjda+elwlpZEhbP2ShqcRxMXhmKTUx7ZqNY8Ps5z7FmTf5dnzaIptleuWbeYMSi6XAjWBGuGY47WJjj2zD8MF2FGhuCiXJIaLtK+qeCifWU3XIbh7YLLcuJ/4TJ/ERzCTcgNAXCvptgar6pguMBODfYDvBEitZ9aS6MAAAAASUVORK5CYII=",
    "P": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAlCAYAAAAuqZsAAAAA60lEQVR42u2YzQ3CMAyFn5GvbAFDwAw9MgnjsEdXYIUeYAu4h0sOuVDy4z+hWqoqtVXzxX1x/Eqv5YaIsUPQ2MD+HiwBuDa+K+VDJPjLdcqDXACcPTLGK/eoyAJF0xgVnymc+F3galelOVxLuZjy+R4NbAZwBHCygOPG559Wq7W38qtrbmRLmgq4QySwucjcI+ImTpbiH9FOkpgcC2chAXgD2FuXi5qZi5QSjUZRpJRodbDDcJqt9RCcds/fDWdhRrrgrFxSM5ylfWuCs/aV1XAehrcKzsuJ/4Tz/EWwCsfwDYqYMUTU2AYmHh9mNCeCSqhe/wAAAABJRU5ErkJggg==",
    "Q": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAlCAYAAAAuqZsAAAAA4klEQVR42u2YzQ2DMAyFn1FWYYgyA0cm6TjdgxW6Qi9swQBwyYELNE78J4SlCAkQ+TAvjh+0/j6IGB2CxgN2e7ANwJv5rC0PkUgn5ylPMgEYPDKWLq7RIQsUTWN0+EzhxO8CV7oqzeE45WLMx280sBlAD+BlAZeY9y9Wq7W28qtrrmVLGjXhWsBmzcxJbOJkKX7zSl+aMaoYveRLSfZji6TmNBpFETitDrYZTrO1boLT7vmr4SzMSBWclUtiw1naNxacta8shvMwvEVwXk78L5znL4JLuATfoIgZQ0SNPWDisQNJXyWKN39ueQAAAABJRU5ErkJggg==",
    "R": "iVBORw0KGgoAAAANSUhEUgAAABkAAAAZCAYAAADE6YVjAAAAgElEQVR42mP8fH0WA60BEwMdwKglVLHkGAMDw38yMQZgwWGJJRKbkR7B9Z/WlvhQwyJClmylhkXEBBfFFhGbhCmyiJR8QrZFpGZGsiwiJ8eTbBG5xQpJFlFSdhFtEaUFJFEWUaMUJmgRE57iRJVEixiRLCOqFN5Kga9Gq98hYAkA1Dwqs8r8UrUAAAAASUVORK5CYII=",
    "S": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAZCAYAAABdEVzWAAAAf0lEQVR42u3W2w2AIAwFUNowilO7mD9s4QB1ArWA3N6Y9pOk5CTQh5zHXhhDC2kk7DewenNuYId4YTJwuU3mQ57SGGHyBU4X/xljrMopnIKqzdhgwzhUg+3GITt/Fw49kty4iFnpwkUN8Vdc5HbxiKsrNwRnzsa6j7XcYBMWERd1LxGe+8X9IgAAAABJRU5ErkJggg==",
    "T": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAZCAYAAABdEVzWAAAAhUlEQVR42mP8fH0Ww2AETAyDFIw6bNg4jAWH+H8KzGSkpcPIMfw/Es04WKPy/2B0GCM1HEerEKPYcbTMlRQ5jtbFBdmOo0c5Rpbj6FXAkuw4epb8JDmO3lUS0Y4biLqSKMcNVCVO0HED2brA6zgWKlqkSqbjvGntsDtk6ts62oIdddhAAABV+xOf5MbmnQAAAABJRU5ErkJggg==",
    "U": "iVBORw0KGgoAAAANSUhEUgAAABoAAAAlCAYAAABcZvm2AAAAhUlEQVR42u3VwQ2AMAgFUGgcxW3c0DncxUEcAC+aePAAfCQx+SRc+1rS/uqxr9JRQ5qKUDlkV3N0hAgRIlQIWaLnt4Umx2a0a3QmIsvX0H2aDcVGYHQQ5r11MBa53hAWfUdpLPNgU1g2GcIYEkEhDM06N1YRqi6sKr2fWChUFcD48f0UOgE8Xx3tC6dw9gAAAABJRU5ErkJggg==",
    "V": "iVBORw0KGgoAAAANSUhEUgAAACcAAAAlCAYAAADBa/A+AAAAn0lEQVR42u3WwQmAMAwF0FQcxSlcwQ07hzO4goM4QL1YKKLYNG0a4QdyFB8R8+OO3ZPVGshwAQfcR4WrMTnggAMOOOCA+xluS4I8t+8HAKenJ8T4gpsLr5JYzvJnDUS0WMTFqa1SYKvJVQG2/FvFwNarRATU2HPFQK0lXATUTAg2UDu+WMAe2ZoN7BX8WcCeV0kKZAW/5GXVnsGxCZx2nUkSK+BC8EHuAAAAAElFTkSuQmCC",
    "W": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAjklEQVR42u3WwQ2AMAgF0GK6nRu6h7M4iAPUi95MLVTgH/5PjCfjC00BOY+tIGYpoCGMsJe0+2HFCCOMMMIIIywgtTOQIWFi3C6et6AeZUOEyR84r4pN4zxv5RTOu12YcRF9zISLarBqXGTnV+GiR9IwLmNWDuGyhvgnLnO76OKqw4+036yo+9jODZawjFy0gxS06eVKrAAAAABJRU5ErkJggg==",
    "X": "iVBORw0KGgoAAAANSUhEUgAAABkAAAAmCAYAAAAxxTAbAAAAhUlEQVR42u3VwQ3AIAgF0A9xu27YPTqLg3QAeumhpwoCJk0h8eThRZQvnX1HdjEWVCEhiNyr2lVIIYX8FmmD/ZmQJC1CD4Ay20WO05juJARiQ48l+3W5IJ54NZI9J1MQO+ZAsifeBHliRQ15s0sFRQTkEIpK4VeoIa4IwLbiPznq+/0GcgFwYhO2azQt8gAAAABJRU5ErkJggg==",
    "Y": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAl0lEQVR42u3Wuw2AMAwE0DOiZQumZjEatoAeGgoKFJIYf4o7if4pMj7Lvi7ImAFJQxhhLznvjy9GGGGEEUYYYQ4ZC4WsKfPWSC1MFKgDwGT1Yr2Rx/kj2WZMfhgHs+FX4yz/ShXOel104zz2WBfOa8E24zw3fxPOu5KqcRFdWYWLKvFPXOR1UcSNiI0AmLPeYxsvWMIicgHPyRa3DDoX6gAAAABJRU5ErkJggg==",
    "Z": "iVBORw0KGgoAAAANSUhEUgAAACYAAAAmCAYAAACoPemuAAAAlklEQVR42u3WwQ2AIAwFUGoYxW3c0DlwFg+O4QB6kYSDYqCh/YffhPsLlP7Kua8BsaYAWoQR9lLXc3hjhBFGGGGEEWZQsRLIkDBRbhiC9pRSABe0Hsu4hNj8ou3Vkb9ShRs9LrpxFnOsC2c1YJtxlpO/CWcdSSVuRsvKjDsQQ/z3WT23iyouOi8R8pWpCPvYxg2WMI+6AfoGFLTB9YbKAAAAAElFTkSuQmCC",
}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Připraví text pro kreslenou šifru SuperKrychle."""
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


class SuperKrychleOutputWidget(QWidget):
    """Kreslený výstup šifry SuperKrychle."""

    _pixmap_cache = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cipher_text = ""
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(170)

    @classmethod
    def get_pixmap(cls, letter: str) -> QPixmap:
        if letter in cls._pixmap_cache:
            return cls._pixmap_cache[letter]

        pixmap = QPixmap()
        data = GLYPH_IMAGES.get(letter)
        if data:
            pixmap.loadFromData(base64.b64decode(data), "PNG")

        cls._pixmap_cache[letter] = pixmap
        return pixmap

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
        cell_w = max(44, int(66 * self.scale_value))
        cell_h = max(44, int(66 * self.scale_value))
        letter_gap = max(10, int(15 * self.scale_value))
        word_gap = max(30, int(46 * self.scale_value))
        line_gap = max(12, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def char_width(self, char: str) -> int:
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if char == " ":
            return word_gap

        if char in GLYPH_IMAGES:
            return cell_w

        return max(24, int(34 * self.scale_value))

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
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
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

            if char in GLYPH_IMAGES:
                self.draw_superkrychle_letter(painter, QRectF(x, y, cell_w, cell_h), char)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, char_w, cell_h), char)
                x += char_w + letter_gap

    def draw_superkrychle_letter(self, painter: QPainter, rect: QRectF, letter: str):
        pixmap = self.get_pixmap(letter)
        if pixmap.isNull():
            return

        target = pixmap.scaled(
            int(rect.width()),
            int(rect.height()),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        draw_x = rect.left() + (rect.width() - target.width()) / 2
        draw_y = rect.top() + (rect.height() - target.height()) / 2

        painter.drawPixmap(int(draw_x), int(draw_y), target)

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        font = QFont("Georgia", max(18, int(36 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypt(sample))
    print("Dešifrování:", decrypt("[A][H][O][J] [J][A][K] ?"))
