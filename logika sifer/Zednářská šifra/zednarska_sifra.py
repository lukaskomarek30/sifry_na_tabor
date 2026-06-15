"""Implementace šifry Zednářská šifra pro Šifrátor Mraveniště.

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

from PySide6.QtCore import Qt, QRectF, QTimer, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


# Směry podle klíče:
# 0 = nahoře, 1 = vpravo, 2 = dole, 3 = vlevo
DIRECTION_BY_TOKEN = {
    "A": 0, "B": 1, "C": 2, "D": 3,
    "E": 0, "F": 1, "G": 2, "H": 3,
    "I": 0, "K": 1, "L": 2, "M": 3,
    "N": 4,
    "O": 0, "P": 1, "Q": 2, "R": 3,
    "S": 0, "T": 1, "U": 2, "V": 3,
    "W": 0, "X": 1, "Y": 2, "Z": 3,
}

# 1 = jednoduché zednářské šipky bez tečky
# 2 = trojúhelníky bez tečky
# 3 = štítky / kosočtvercové trojúhelníky bez tečky
# 4 = jednoduché zednářské šipky s tečkou
# 5 = trojúhelníky s tečkou
# 6 = štítky / kosočtvercové trojúhelníky s tečkou
STYLE_BY_TOKEN = {
    "A": 1, "B": 1, "C": 1, "D": 1,
    "E": 2, "F": 2, "G": 2, "H": 2,
    "I": 3, "K": 3, "L": 3, "M": 3,
    "N": 7,
    "O": 4, "P": 4, "Q": 4, "R": 4,
    "S": 5, "T": 5, "U": 5, "V": 5,
    "W": 6, "X": 6, "Y": 6, "Z": 6,
}

SUPPORTED_TOKENS = set(STYLE_BY_TOKEN.keys())


def normalize_text(text: str) -> str:
    """Převede text na velká písmena bez diakritiky.

    V klíči není samostatné J, proto se J převádí na I.
    """
    if text is None:
        return ""

    normalized = unicodedata.normalize("NFKD", str(text))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.upper()
    normalized = normalized.replace("J", "I")
    return normalized


def tokenize_text(text: str) -> list[str]:
    """Rozdělí text na tokeny pro kreslení."""
    normalized = normalize_text(text)
    return list(normalized)


def encrypt(text: str) -> str:
    """Vrátí normalizovaný text pro kreslený výstup.

    Samotné symboly kreslí až ZednarskaSifraOutputWidget.
    """
    return normalize_text(text)


def decrypt(text: str) -> str:
    """Textové / interní dešifrování.

    Kreslený výstup nejde spolehlivě číst z obyčejného textu, proto podporuje:
    - běžný text: AHOI? -> AHOI?
    - hranatý zápis: [A][H][O][I]? -> AHOI?
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    result: list[str] = []
    index = 0

    while index < len(cleaned):
        char = cleaned[index]

        if char == "[":
            end = cleaned.find("]", index + 1)
            if end != -1:
                token = normalize_text(cleaned[index + 1:end].strip())
                if len(token) == 1:
                    result.append(token)
                    index = end + 1
                    continue

        result.append(char)
        index += 1

    return normalize_text("".join(result))



# Grafická vrstva pro vykreslení výsledku v Qt rozhraní.
class ZednarskaSifraOutputWidget(QWidget):
    """Kreslený výstup Zednářské šifry."""

    def __init__(self, parent=None):
        """Pomocná funkce používaná interní logikou šifry."""
        super().__init__(parent)
        self.cipher_text = ""
        self.tokens: list[str] = []
        self.scale_value = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setMinimumHeight(175)

    def set_scale(self, scale: float):
        """Nastaví měřítko vykreslení a aktualizuje rozměry widgetu."""
        self.scale_value = max(0.55, float(scale))
        self.update_content_size()
        self.update()

    def set_cipher_text(self, text: str):
        """Nastaví text určený pro vykreslení a obnoví obsah widgetu."""
        self.cipher_text = normalize_text(text)
        self.tokens = tokenize_text(text)
        self.update_content_size()
        QTimer.singleShot(0, self.update_content_size)
        self.update()

    def clear(self):
        """Vymaže aktuální obsah widgetu a obnoví jeho vykreslení."""
        self.cipher_text = ""
        self.tokens = []
        self.update_content_size()
        self.update()

    def resizeEvent(self, event):
        """Reaguje na změnu velikosti widgetu a přepočítá rozložení obsahu."""
        super().resizeEvent(event)
        self.update_content_size()

    def get_metrics(self):
        """Pomocná funkce používaná interní logikou šifry."""
        cell_w = max(46, int(70 * self.scale_value))
        cell_h = max(54, int(82 * self.scale_value))
        letter_gap = max(8, int(13 * self.scale_value))
        word_gap = max(24, int(40 * self.scale_value))
        line_gap = max(10, int(18 * self.scale_value))
        return cell_w, cell_h, letter_gap, word_gap, line_gap

    def token_width(self, token: str) -> int:
        """Pomocná funkce používaná interní logikou šifry."""
        cell_w, _, _, word_gap, _ = self.get_metrics()

        if token == " ":
            return word_gap

        if token in SUPPORTED_TOKENS:
            return cell_w

        return max(24, int(34 * self.scale_value))

    def calculate_required_height(self, available_width: int) -> int:
        """Spočítá minimální výšku potřebnou pro zobrazení celého obsahu."""
        margin_left = 14
        margin_right = 14
        margin_top = 10
        margin_bottom = 18

        _, cell_h, letter_gap, _, line_gap = self.get_metrics()
        content_width = max(160, available_width - margin_left - margin_right)

        if not self.tokens:
            return max(170, cell_h + margin_top + margin_bottom)

        x = 0
        y = 0

        for token in self.tokens:
            if token == "\n":
                x = 0
                y += cell_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > 0 and x + token_w > content_width:
                x = 0
                y += cell_h + line_gap

            x += token_w
            if token != " ":
                x += letter_gap

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

        if not self.tokens:
            painter.setFont(QFont("Georgia", max(10, int(14 * self.scale_value))))
            painter.setPen(QColor("#a8a295"))
            painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, "Kreslený výsledek se objeví zde...")
            return

        cell_w, cell_h, letter_gap, _, line_gap = self.get_metrics()
        x = rect.left()
        y = rect.top()

        for token in self.tokens:
            if token == "\n":
                x = rect.left()
                y += cell_h + line_gap
                continue

            token_w = self.token_width(token)

            if x > rect.left() and x + token_w > rect.right():
                x = rect.left()
                y += cell_h + line_gap

            if token == " ":
                x += token_w
                continue

            if token in SUPPORTED_TOKENS:
                self.draw_masonic_token(painter, QRectF(x, y, cell_w, cell_h), token)
                x += cell_w + letter_gap
            else:
                self.draw_plain_symbol(painter, QRectF(x, y, token_w, cell_h), token)
                x += token_w + letter_gap

    def draw_masonic_token(self, painter: QPainter, rect: QRectF, token: str):
        """Pomocná funkce používaná interní logikou šifry."""
        style = STYLE_BY_TOKEN[token]
        direction = DIRECTION_BY_TOKEN[token]

        color = QColor("#f3d79a")
        pen_width = max(3, int(5 * self.scale_value))
        pen = QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if style == 7:
            self.draw_cross(painter, rect, color)
            return

        if style in (1, 4):
            self.draw_open_v(painter, rect, direction)
        elif style in (2, 5):
            self.draw_triangle(painter, rect, direction)
        elif style in (3, 6):
            self.draw_kite(painter, rect, direction)

        if style in (4, 5, 6):
            self.draw_dot(painter, rect, color, direction)

    def draw_cross(self, painter: QPainter, rect: QRectF, color: QColor):
        """Pomocná funkce používaná interní logikou šifry."""
        pen_width = max(3, int(5 * self.scale_value))
        painter.setPen(QPen(color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = rect.center().x()
        cy = rect.center().y()
        r = min(rect.width(), rect.height()) * 0.23
        painter.drawLine(QPointF(cx - r, cy - r), QPointF(cx + r, cy + r))
        painter.drawLine(QPointF(cx - r, cy + r), QPointF(cx + r, cy - r))

    def draw_open_v(self, painter: QPainter, rect: QRectF, direction: int):
        """Jednoduché otevřené klíny pro A-D a O-R.

        Tvar je schválně užší a vyšší, aby odpovídal štíhlému vzhledu z klíče.
        """
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()

        outer_x = w * 0.29
        outer_y = h * 0.36
        inner_x = w * 0.20
        inner_y = h * 0.24

        if direction == 0:      # nahoře: otevřené V, špička dolů ke středu
            p1 = QPointF(cx - outer_x, cy - outer_y)
            p2 = QPointF(cx,           cy + inner_y)
            p3 = QPointF(cx + outer_x, cy - outer_y)
        elif direction == 1:    # vpravo: špička doleva ke středu
            p1 = QPointF(cx + outer_x, cy - outer_y)
            p2 = QPointF(cx - inner_x, cy)
            p3 = QPointF(cx + outer_x, cy + outer_y)
        elif direction == 2:    # dole: špička nahoru ke středu
            p1 = QPointF(cx - outer_x, cy + outer_y)
            p2 = QPointF(cx,           cy - inner_y)
            p3 = QPointF(cx + outer_x, cy + outer_y)
        else:                   # vlevo: špička doprava ke středu
            p1 = QPointF(cx - outer_x, cy - outer_y)
            p2 = QPointF(cx + inner_x, cy)
            p3 = QPointF(cx - outer_x, cy + outer_y)

        painter.drawLine(p1, p2)
        painter.drawLine(p2, p3)

    def triangle_points(self, rect: QRectF, direction: int):
        """Trojúhelníky podle klíče.

        Jsou užší a delší než dříve, aby co nejvíc připomínaly ručně kreslený vzor.
        """
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()

        base_half_w = w * 0.18
        base_half_h = h * 0.18
        outer_y = h * 0.40
        outer_x = w * 0.40
        inner_y = h * 0.22
        inner_x = w * 0.22

        if direction == 0:      # nahoře: základna nahoře, špička dolů
            return [
                QPointF(cx - base_half_w, cy - outer_y),
                QPointF(cx + base_half_w, cy - outer_y),
                QPointF(cx,               cy + inner_y),
            ]
        if direction == 1:      # vpravo: základna vpravo, špička doprava
            return [
                QPointF(cx - inner_x, cy - base_half_h),
                QPointF(cx + outer_x, cy),
                QPointF(cx - inner_x, cy + base_half_h),
            ]
        if direction == 2:      # dole: základna dole, špička nahoru
            return [
                QPointF(cx - base_half_w, cy + outer_y),
                QPointF(cx + base_half_w, cy + outer_y),
                QPointF(cx,               cy - inner_y),
            ]

        # vlevo: základna vlevo, špička doleva
        return [
            QPointF(cx + inner_x, cy - base_half_h),
            QPointF(cx - outer_x, cy),
            QPointF(cx + inner_x, cy + base_half_h),
        ]

    def draw_triangle(self, painter: QPainter, rect: QRectF, direction: int):
        """Pomocná funkce používaná interní logikou šifry."""
        polygon = QPolygonF(self.triangle_points(rect, direction))
        painter.drawPolygon(polygon)

    def kite_points(self, rect: QRectF, direction: int):
        """Štítové dílky podle klíče pro I-M a W-Z.

        Tvar je zúžený a připomíná malý pětiúhelníkový štít: 
        kratší vnější hrana, dvě ramena a vnitřní špička do středu.
        """
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()

        outer_flat_half = w * 0.14
        outer_flat_half_h = h * 0.14
        shoulder_x = w * 0.24
        shoulder_y = h * 0.18
        outer_y = h * 0.40
        outer_x = w * 0.40
        inner_y = h * 0.24
        inner_x = w * 0.24

        if direction == 0:      # nahoře: plochá hrana nahoře, špička dolů
            return [
                QPointF(cx - outer_flat_half, cy - outer_y),
                QPointF(cx + outer_flat_half, cy - outer_y),
                QPointF(cx + shoulder_x,      cy - shoulder_y),
                QPointF(cx,                   cy + inner_y),
                QPointF(cx - shoulder_x,      cy - shoulder_y),
            ]
        if direction == 1:      # vpravo: plochá hrana vpravo, špička doleva
            return [
                QPointF(cx + outer_x,         cy - outer_flat_half_h),
                QPointF(cx + outer_x,         cy + outer_flat_half_h),
                QPointF(cx + shoulder_y,      cy + shoulder_x),
                QPointF(cx - inner_x,         cy),
                QPointF(cx + shoulder_y,      cy - shoulder_x),
            ]
        if direction == 2:      # dole: plochá hrana dole, špička nahoru
            return [
                QPointF(cx - outer_flat_half, cy + outer_y),
                QPointF(cx + outer_flat_half, cy + outer_y),
                QPointF(cx + shoulder_x,      cy + shoulder_y),
                QPointF(cx,                   cy - inner_y),
                QPointF(cx - shoulder_x,      cy + shoulder_y),
            ]

        # vlevo: plochá hrana vlevo, špička doprava
        return [
            QPointF(cx - outer_x,             cy - outer_flat_half_h),
            QPointF(cx - outer_x,             cy + outer_flat_half_h),
            QPointF(cx - shoulder_y,          cy + shoulder_x),
            QPointF(cx + inner_x,             cy),
            QPointF(cx - shoulder_y,          cy - shoulder_x),
        ]

    def draw_kite(self, painter: QPainter, rect: QRectF, direction: int):
        """Pomocná funkce používaná interní logikou šifry."""
        polygon = QPolygonF(self.kite_points(rect, direction))
        painter.drawPolygon(polygon)

    def draw_dot(self, painter: QPainter, rect: QRectF, color: QColor, direction: int | None = None):
        """Tečka je blíž k vnější straně symbolu, jako v klíči."""
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)

        dot_r = max(3.0, rect.height() * 0.05)
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()

        if direction == 0:
            point = QPointF(cx, cy - h * 0.24)
        elif direction == 1:
            point = QPointF(cx + w * 0.24, cy)
        elif direction == 2:
            point = QPointF(cx, cy + h * 0.24)
        elif direction == 3:
            point = QPointF(cx - w * 0.24, cy)
        else:
            point = rect.center()

        painter.drawEllipse(point, dot_r, dot_r)
        painter.setBrush(Qt.NoBrush)

    def draw_plain_symbol(self, painter: QPainter, rect: QRectF, symbol: str):
        """Pomocná funkce používaná interní logikou šifry."""
        font = QFont("Georgia", max(18, int(42 * self.scale_value)), QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#f3d79a"))
        painter.drawText(rect, Qt.AlignCenter, symbol)


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    print("Vstup:", sample)
    print("Data pro kreslení:", encrypt(sample))
    print("Tokeny:", tokenize_text(sample))
    print("Dešifrování:", decrypt("[A][H][O][I] [I][A][K] [S][E] [M][A][S]?"))
