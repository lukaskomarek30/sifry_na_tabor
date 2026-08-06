"""Animované plameny a společný skleněný základ pirátských modulů."""

import math
import os

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPalette, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QLineEdit,
    QListWidget,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QWidget,
)


class FireFlicker:
    """Vykresluje nepravidelně se měnící plameny nad statickým pozadím.

    Kotva má podobu ``(x, y, velikost)``. Souřadnice x/y jsou poměry vůči
    původnímu obrázku, takže efekt zůstane na lucerně i při změně velikosti
    nebo ořezu okna.
    """

    def __init__(self, widget, anchors, base_width: int = 1672, interval_ms: int = 82):
        self.widget = widget
        self.anchors = tuple(anchors)
        self.base_width = max(1, int(base_width))
        self.phase = 0.0

        self.timer = QTimer(widget)
        self.timer.setInterval(max(45, int(interval_ms)))
        self.timer.setTimerType(Qt.CoarseTimer)
        self.timer.timeout.connect(self._advance)
        self.timer.start()

    def _advance(self):
        self.phase = (self.phase + 0.31) % (math.tau * 1000.0)
        self.widget.update()

    def paint(self, painter: QPainter, scaled_width: int, scaled_height: int, crop_x=0, crop_y=0):
        if not self.anchors or scaled_width <= 0 or scaled_height <= 0:
            return

        image_scale = scaled_width / self.base_width
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_Screen)

        for index, (normal_x, normal_y, size_factor) in enumerate(self.anchors):
            phase = self.phase + index * 1.73
            irregular = (
                0.82
                + 0.12 * math.sin(phase * 0.91)
                + 0.07 * math.sin(phase * 2.37 + 0.8)
                + 0.04 * math.sin(phase * 4.11 + index)
            )
            intensity = max(0.58, min(1.08, irregular))
            radius = max(3.2, 15.0 * float(size_factor) * image_scale)
            sway = math.sin(phase * 1.67) * radius * 0.20 + math.sin(phase * 3.29) * radius * 0.08

            center_x = float(normal_x) * scaled_width - float(crop_x) + sway
            center_y = float(normal_y) * scaled_height - float(crop_y)

            glow_radius = radius * (3.3 + intensity * 0.55)
            glow = QRadialGradient(center_x, center_y, glow_radius)
            glow.setColorAt(0.0, QColor(255, 208, 92, int(105 * intensity)))
            glow.setColorAt(0.22, QColor(255, 142, 37, int(72 * intensity)))
            glow.setColorAt(0.58, QColor(226, 74, 16, int(26 * intensity)))
            glow.setColorAt(1.0, QColor(255, 80, 0, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QRectF(
                center_x - glow_radius,
                center_y - glow_radius,
                glow_radius * 2.0,
                glow_radius * 2.0,
            ))

            flame_top = center_y - radius * (1.35 + 0.38 * intensity)
            flame_bottom = center_y + radius * 0.72
            flame = QPainterPath()
            flame.moveTo(center_x, flame_bottom)
            flame.cubicTo(
                center_x - radius * 0.86,
                center_y + radius * 0.28,
                center_x - radius * 0.58 + sway * 0.18,
                center_y - radius * 0.68,
                center_x + sway * 0.36,
                flame_top,
            )
            flame.cubicTo(
                center_x + radius * 0.16,
                center_y - radius * 0.70,
                center_x + radius * 0.82,
                center_y + radius * 0.18,
                center_x,
                flame_bottom,
            )
            flame.closeSubpath()

            flame_gradient = QLinearGradient(center_x, flame_top, center_x, flame_bottom)
            flame_gradient.setColorAt(0.0, QColor(255, 246, 171, int(165 * intensity)))
            flame_gradient.setColorAt(0.34, QColor(255, 190, 61, int(220 * intensity)))
            flame_gradient.setColorAt(0.76, QColor(255, 94, 18, int(205 * intensity)))
            flame_gradient.setColorAt(1.0, QColor(155, 30, 5, 25))
            painter.setBrush(flame_gradient)
            painter.drawPath(flame)

            inner_radius = radius * 0.46
            inner = QPainterPath()
            inner.moveTo(center_x, center_y + inner_radius * 0.74)
            inner.cubicTo(
                center_x - inner_radius * 0.70,
                center_y + inner_radius * 0.20,
                center_x - inner_radius * 0.28,
                center_y - inner_radius * 0.65,
                center_x + sway * 0.14,
                center_y - inner_radius * (1.08 + intensity * 0.18),
            )
            inner.cubicTo(
                center_x + inner_radius * 0.50,
                center_y - inner_radius * 0.34,
                center_x + inner_radius * 0.58,
                center_y + inner_radius * 0.22,
                center_x,
                center_y + inner_radius * 0.74,
            )
            inner.closeSubpath()
            painter.setBrush(QColor(255, 245, 170, int(185 * intensity)))
            painter.drawPath(inner)

        painter.restore()


_MODULE_GLASS_STYLE = """
    QDialog {
        background: transparent;
        color: #f3ddaa;
    }
    QLabel {
        color: #ead8b3;
        background: transparent;
        font-family: Georgia;
    }
    QLineEdit, QComboBox, QSpinBox, QDateEdit {
        color: #f0e2c0;
        background-color: rgba(2, 14, 22, 118);
        border: 1px solid rgba(205, 159, 78, 190);
        border-radius: 9px;
        padding: 6px;
        selection-background-color: rgba(23, 108, 118, 190);
        selection-color: #fff0bd;
    }
    QTextEdit, QListWidget {
        color: #f0e2c0;
        background-color: rgba(2, 13, 21, 26);
        border: 1px solid rgba(205, 159, 78, 178);
        border-radius: 11px;
        padding: 7px;
        selection-background-color: rgba(23, 108, 118, 185);
        selection-color: #fff0bd;
    }
    QListWidget::item {
        padding: 6px;
        background: rgba(3, 20, 29, 36);
        border-radius: 6px;
    }
    QListWidget::item:alternate {
        background: rgba(10, 47, 57, 42);
    }
    QListWidget::item:selected {
        color: #fff0bd;
        background: rgba(18, 82, 89, 184);
    }
    QComboBox QAbstractItemView {
        color: #f0e2c0;
        background-color: #071720;
        border: 1px solid #a47a3e;
        selection-background-color: #176c76;
    }
    QPushButton {
        color: #f4dea4;
        background-color: rgba(13, 64, 75, 190);
        border: 1px solid rgba(220, 174, 86, 220);
        border-radius: 10px;
        padding: 8px 12px;
        font-family: Georgia;
        font-weight: bold;
    }
    QPushButton:hover {
        color: #fff0bd;
        background-color: rgba(20, 86, 96, 220);
        border: 2px solid #f3d79a;
    }
    QCheckBox {
        color: #ead8b3;
        background: transparent;
    }
    QScrollBar:vertical, QScrollBar:horizontal {
        background: rgba(3, 14, 22, 90);
        border-radius: 5px;
        margin: 2px;
    }
    QScrollBar:vertical { width: 11px; }
    QScrollBar:horizontal { height: 11px; }
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
        background: #9b7a45;
        min-height: 32px;
        min-width: 32px;
        border-radius: 5px;
    }
    QScrollBar::add-line, QScrollBar::sub-line {
        width: 0px;
        height: 0px;
    }
"""


class PirateModuleDialog(QDialog):
    """QDialog s vlastním tematickým pozadím, sklem a živými světly."""

    def __init__(self, owner_window, background_name: str, fire_anchors):
        super().__init__(owner_window)
        self.owner_window = owner_window
        central = getattr(owner_window, "central", None)
        icons_path = str(getattr(central, "icons_path", "") or "")
        background_path = os.path.join(icons_path, background_name) if icons_path else ""
        if not background_path or not os.path.exists(background_path):
            background_path = os.path.join(icons_path, "menu_BG.png") if icons_path else ""
        self.module_background = (
            QPixmap(background_path) if background_path and os.path.exists(background_path) else QPixmap()
        )
        self.fire_flicker = FireFlicker(self, fire_anchors)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        scaled = QPixmap()
        crop_x = crop_y = 0
        if not self.module_background.isNull():
            scaled = self.module_background.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            crop_x = max(0, (scaled.width() - self.width()) // 2)
            crop_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(
                self.rect(), scaled, QRect(crop_x, crop_y, self.width(), self.height())
            )
        else:
            painter.fillRect(self.rect(), QColor("#06131b"))
        painter.fillRect(self.rect(), QColor(1, 8, 13, 25))
        if not scaled.isNull():
            self.fire_flicker.paint(
                painter, scaled.width(), scaled.height(), crop_x, crop_y
            )

    def apply_pirate_glass(self):
        """Přebarví i prvky s vlastním starším stylem na lehké průhledné sklo."""
        self.setStyleSheet(self.styleSheet() + _MODULE_GLASS_STYLE)

        editor_style = """
            QTextEdit {
                color: #f0e2c0;
                background-color: rgba(2, 13, 21, 22);
                border: 1px solid rgba(205, 159, 78, 178);
                border-radius: 11px;
                padding: 7px;
                selection-background-color: rgba(23, 108, 118, 185);
            }
        """
        list_style = """
            QListWidget {
                color: #f0e2c0;
                background-color: rgba(2, 13, 21, 48);
                border: 1px solid rgba(205, 159, 78, 178);
                border-radius: 11px;
                padding: 6px;
            }
            QListWidget::item { padding: 6px; background: rgba(3, 20, 29, 32); }
            QListWidget::item:selected { color: #fff0bd; background: rgba(18, 82, 89, 184); }
        """
        field_style = """
            QLineEdit, QComboBox, QSpinBox, QDateEdit {
                color: #f0e2c0;
                background-color: rgba(2, 14, 22, 118);
                border: 1px solid rgba(205, 159, 78, 190);
                border-radius: 9px;
                padding: 6px;
            }
        """

        for editor in self.findChildren(QTextEdit):
            editor.setStyleSheet(editor.styleSheet() + editor_style)
            editor.setAttribute(Qt.WA_TranslucentBackground, True)
            editor.viewport().setAutoFillBackground(False)
            editor.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
            editor.viewport().setStyleSheet("background: transparent;")
            viewport_palette = editor.viewport().palette()
            viewport_palette.setColor(QPalette.Base, QColor(0, 0, 0, 0))
            viewport_palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
            editor.viewport().setPalette(viewport_palette)
        for list_widget in self.findChildren(QListWidget):
            list_widget.setStyleSheet(list_widget.styleSheet() + list_style)
            list_widget.viewport().setAutoFillBackground(False)
        for field_type in (QLineEdit, QComboBox, QSpinBox, QDateEdit):
            for field in self.findChildren(field_type):
                field.setStyleSheet(field.styleSheet() + field_style)
        for area in self.findChildren(QScrollArea):
            area.setStyleSheet(
                area.styleSheet()
                + "QScrollArea { background: transparent; border: 1px solid rgba(205,159,78,155); border-radius: 11px; }"
            )
            area.setAutoFillBackground(False)
            area.viewport().setAutoFillBackground(False)
            area.viewport().setStyleSheet("background: rgba(2, 13, 21, 28);")

        for panel in self.findChildren(QWidget):
            if panel.objectName() == "plannerRightPanel":
                panel.setStyleSheet(
                    panel.styleSheet()
                    + "QWidget#plannerRightPanel { background: rgba(2,13,21,58); "
                    "border: 1px solid rgba(205,159,78,170); border-radius: 12px; }"
                )
