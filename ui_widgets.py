"""
ui_widgets.py – Sdílené UI widgety pro Šifrátor Mraveniště.

Obsahuje:
  - Colors: konstanty barev aplikace
  - CipherItem: datová třída pro položku šifry
  - TransparentActionButton: hlavní tlačítko akcí (Šifrovat / Dešifrovat)
  - CipherButton: tlačítko v levém seznamu šifer
  - CaesarDirectionCombo: stylizovaný QComboBox pro Caesar šifru
"""

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPen
from PySide6.QtWidgets import QPushButton, QSizePolicy, QComboBox


# ============================================================
# BARVY
# ============================================================

class Colors:
    GOLD = "#c89a4c"
    GOLD_LIGHT = "#f3d79a"
    GOLD_TEXT = "#e7c681"
    DARK_TEXT = "#1f1205"
    TEXT_LIGHT = "#ead8b3"
    PLACEHOLDER = "#a8a295"
    SELECT_CYAN = "#15c1cc"


# ============================================================
# DATOVÉ TYPY
# ============================================================

@dataclass
class CipherItem:
    name: str
    icon: str


# ============================================================
# TLAČÍTKA
# ============================================================

class TransparentActionButton(QPushButton):
    """Transparentní akční tlačítko vykreslované nad grafickým skinem.

    Popisek i ikona zámku se kreslí ručně, aby zůstaly přesně zarovnané
    vůči dekorativnímu tlačítku v pozadí.
    """

    def __init__(self, text: str, icon_path: str = "", parent=None):
        super().__init__("", parent)
        self.full_text = text
        self.lock_pixmap = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        self._hovered = False

        self.setCursor(Qt.PointingHandCursor)
        self.setFont(QFont("Georgia", 20, QFont.Bold))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 120, 28))
            painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 10, 10)

        painter.setFont(self.font())
        fm = painter.fontMetrics()

        icon_size = max(46, min(74, int(self.height() * 0.88)))
        gap = max(14, int(self.width() * 0.040))
        text_w = fm.horizontalAdvance(self.full_text)

        center_y = self.height() // 2
        vertical_shift = max(2, int(self.height() * 0.04))

        text_x = int((self.width() - text_w) / 2)
        icon_x = int(text_x - gap - icon_size)

        if icon_x < 8:
            total_w = icon_size + gap + text_w
            group_x = int((self.width() - total_w) / 2)
            icon_x = group_x
            text_x = group_x + icon_size + gap

        if not self.lock_pixmap.isNull():
            scaled = self.lock_pixmap.scaled(
                QSize(icon_size, icon_size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            draw_icon_x = icon_x + (icon_size - scaled.width()) // 2
            draw_icon_y = center_y - scaled.height() // 2 + vertical_shift
            painter.drawPixmap(draw_icon_x, draw_icon_y, scaled)

        text_color = QColor("#fff0bd") if self._hovered else QColor(Colors.GOLD_LIGHT)
        painter.setPen(QPen(text_color))
        text_rect = QRect(
            text_x,
            vertical_shift,
            text_w + 10,
            self.height() - vertical_shift,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.full_text)


class CipherButton(QPushButton):
    """Tlačítko reprezentující jednu šifru v levém panelu seznamu."""

    def __init__(self, item: CipherItem, icon_path: str, parent=None):
        super().__init__(item.name, parent)
        self.item = item
        self.full_text = item.name
        self.selected = False

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(50)
        self.setMinimumWidth(0)
        self.setFont(QFont("Georgia", 12))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if icon_path and os.path.exists(icon_path):
            self.setIcon(QIcon(icon_path))
            self.setIconSize(QSize(38, 38))

        self.refresh_style()
        self.update_elided_text()

    def minimumSizeHint(self):
        return QSize(40, self.minimumHeight())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elided_text()

    def update_elided_text(self):
        icon_w = self.iconSize().width() if not self.icon().isNull() else 0
        available = max(35, self.width() - icon_w - 34)
        shown = self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, available)

        if self.text() != shown:
            self.setText(shown)

        self.setToolTip(self.full_text)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.refresh_style()

    def refresh_style(self):
        if self.selected:
            border = Colors.SELECT_CYAN
            bg = "rgba(0, 120, 130, 105)"
            width = 2
        else:
            border = "rgba(165, 113, 49, 120)"
            bg = "rgba(7, 18, 22, 155)"
            width = 1

        self.setStyleSheet(f"""
            QPushButton {{
                color: {Colors.TEXT_LIGHT};
                text-align: left;
                border: {width}px solid {border};
                border-radius: 8px;
                padding-left: 8px;
                padding-right: 4px;
                background-color: {bg};
            }}
            QPushButton:hover {{
                border: 2px solid {Colors.GOLD_LIGHT};
                background-color: rgba(20, 45, 50, 180);
            }}
        """)
        self.update_elided_text()


# ============================================================
# CAESAR – speciální combo widget
# ============================================================

class CaesarDirectionCombo(QComboBox):
    """Skutečný rozevírací seznam, ale vykreslený jako text uprostřed tlačítka."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        if self._hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 220, 120, 26))
            painter.drawRoundedRect(self.rect().adjusted(5, 5, -5, -5), 10, 10)

        painter.setFont(self.font())
        painter.setPen(QColor(Colors.GOLD_LIGHT if not self._hovered else "#fff0bd"))

        text_rect = self.rect().adjusted(26, 0, -54, 0)
        painter.drawText(text_rect, Qt.AlignCenter, self.currentText())

        arrow_font = QFont(self.font())
        arrow_font.setPointSize(max(10, int(self.font().pointSize() * 0.58)))
        painter.setFont(arrow_font)
        arrow_rect = QRect(self.width() - 56, 0, 38, self.height())
        painter.drawText(arrow_rect, Qt.AlignCenter, "▼")
