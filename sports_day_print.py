"""Tiskové studio, tiskové náhledy a A6 kartičky pro sportovní den."""

import html
import os
from datetime import datetime

from PySide6.QtCore import QMarginsF, QRect, QRectF, QSize, QSizeF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImage, QPageLayout, QPageSize, QPainter, QPen, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from groups_data import normalized_label, roster_entries


PRINT_PAGE_SIZES = {
    "A5": QSizeF(420, 595),
    "A4": QSizeF(595, 842),
    "A3": QSizeF(842, 1191),
    "Letter": QSizeF(612, 792),
    "Legal": QSizeF(612, 1008),
}

SPORTS_PRINT_FONT_FAMILIES = {
    "default": {
        "label": "Původní / Segoe + Georgia",
        "qfont": "Segoe UI",
        "body_css": "'Segoe UI',Arial,sans-serif",
        "heading_css": "Georgia,'Times New Roman',serif",
    },
    "pirate": {
        "label": "Pirátské / Pirata One",
        "qfont": "Pirata One",
        "body_css": "'Pirata One',Georgia,serif",
        "heading_css": "'Pirata One',Georgia,serif",
    },
    "serif": {
        "label": "Klasické / Georgia",
        "qfont": "Georgia",
        "body_css": "Georgia,'Times New Roman',serif",
        "heading_css": "Georgia,'Times New Roman',serif",
    },
    "modern": {
        "label": "Moderní / Segoe UI",
        "qfont": "Segoe UI",
        "body_css": "'Segoe UI',Arial,sans-serif",
        "heading_css": "'Segoe UI',Arial,sans-serif",
    },
    "clean": {
        "label": "Jednoduché / Arial",
        "qfont": "Arial",
        "body_css": "Arial,Helvetica,sans-serif",
        "heading_css": "Arial,Helvetica,sans-serif",
    },
    "compact": {
        "label": "Kompaktní / Tahoma",
        "qfont": "Tahoma",
        "body_css": "Tahoma,Arial,sans-serif",
        "heading_css": "Tahoma,Arial,sans-serif",
    },
}

SPORTS_PRINT_FONT_STYLES = {
    "regular": {
        "label": "Normální",
        "bold": False,
        "italic": False,
        "body_weight": "400",
        "heading_weight": "700",
        "css_style": "normal",
    },
    "bold": {
        "label": "Tučné",
        "bold": True,
        "italic": False,
        "body_weight": "700",
        "heading_weight": "700",
        "css_style": "normal",
    },
    "italic": {
        "label": "Kurzíva",
        "bold": False,
        "italic": True,
        "body_weight": "400",
        "heading_weight": "700",
        "css_style": "italic",
    },
    "bold_italic": {
        "label": "Tučné kurzíva",
        "bold": True,
        "italic": True,
        "body_weight": "700",
        "heading_weight": "700",
        "css_style": "italic",
    },
}


def _sports_print_font_family(font_key: str | None, icons_path: str = "") -> dict:
    key = font_key if font_key in SPORTS_PRINT_FONT_FAMILIES else "default"
    family = dict(SPORTS_PRINT_FONT_FAMILIES[key])
    if key != "pirate":
        return family

    try:
        if family["qfont"] not in QFontDatabase.families():
            module_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = []
            if icons_path:
                candidates.append(os.path.join(icons_path, "fonts", "PirataOne-Regular.ttf"))
            candidates.append(os.path.join(module_dir, "icons", "fonts", "PirataOne-Regular.ttf"))
            for path in candidates:
                if not os.path.exists(path):
                    continue
                font_id = QFontDatabase.addApplicationFont(path)
                if font_id >= 0:
                    registered = QFontDatabase.applicationFontFamilies(font_id)
                    if registered:
                        family["qfont"] = registered[0]
                        family["body_css"] = f"'{registered[0]}',Georgia,serif"
                        family["heading_css"] = f"'{registered[0]}',Georgia,serif"
                        break
    except Exception:
        pass
    return family


def _sports_print_font_style(style_key: str | None) -> dict:
    return dict(SPORTS_PRINT_FONT_STYLES.get(style_key or "", SPORTS_PRINT_FONT_STYLES["regular"]))


def _sports_print_qfont(
    font_key: str | None,
    size: int,
    style_key: str | None = "regular",
    icons_path: str = "",
) -> QFont:
    family = _sports_print_font_family(font_key, icons_path)
    style = _sports_print_font_style(style_key)
    font = QFont(family["qfont"], int(size))
    font.setBold(bool(style["bold"]))
    font.setItalic(bool(style["italic"]))
    return font


def _sports_print_page_size(paper_name: str, orientation_name: str) -> QSizeF:
    size = PRINT_PAGE_SIZES.get(paper_name or "A4", PRINT_PAGE_SIZES["A4"])
    if orientation_name == "Na šířku":
        return QSizeF(size.height(), size.width())
    return QSizeF(size)


def _sports_print_page_label(paper_name: str, orientation_name: str) -> str:
    dimensions = {
        "A5": (148, 210),
        "A4": (210, 297),
        "A3": (297, 420),
        "Letter": (216, 279),
        "Legal": (216, 356),
    }
    width, height = dimensions.get(paper_name or "A4", dimensions["A4"])
    if orientation_name == "Na šířku":
        width, height = height, width
    return f"Papír: {paper_name or 'A4'}  •  {orientation_name or 'Na výšku'}  •  {width} × {height} mm"


class _SportsPrintPreviewWidget(QWidget):
    """Živý vícestránkový náhled výsledků ve stylu tiskového studia Šifrátoru."""

    def __init__(self, sports_dialog, parent=None):
        super().__init__(parent)
        self._sports_dialog = sports_dialog
        self._document = None
        self._use_background = True
        self._message = "Připravuji náhled…"
        self._scale = 1.0
        self._manual_scale = None
        self._page_count = 1
        self._page_gap = 28
        self._outer_margin = 28
        self._page_cache = []
        self._image_only = False
        self._forced_page_size = QSizeF(595, 842)
        self.setMinimumSize(280, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_message(self, message: str):
        self._document = None
        self._page_cache = []
        self._image_only = False
        self._message = message or ""
        self._refresh_geometry()

    def set_preview_document(self, document: QTextDocument, use_background: bool):
        self._document = document
        self._image_only = False
        self._use_background = bool(use_background)
        self._message = ""
        try:
            self._page_count = max(1, int(document.documentLayout().pageCount()))
        except Exception:
            self._page_count = 1
        self._page_cache = [
            self._sports_dialog._render_sports_print_page(document, index, self._use_background)
            for index in range(self._page_count)
        ]
        self._refresh_geometry()

    def set_page_images(self, images: list[QImage], page_size: QSizeF | None = None):
        self._document = None
        self._image_only = True
        self._message = ""
        self._page_cache = [QImage(image) for image in images if not image.isNull()]
        self._page_count = max(1, len(self._page_cache))
        self._forced_page_size = QSizeF(page_size or QSizeF(595, 842))
        self._refresh_geometry()

    def _page_size(self) -> QSizeF:
        if self._image_only:
            return QSizeF(self._forced_page_size)
        if self._document is not None and self._document.pageSize().isValid():
            return self._document.pageSize()
        return PRINT_PAGE_SIZES["A4"]

    def _viewport_width(self) -> int:
        parent = self.parentWidget()
        return max(280, parent.width() if parent is not None else self.width())

    def _refresh_geometry(self):
        page_size = self._page_size()
        if self._manual_scale is None:
            available = max(240, self._viewport_width() - self._outer_margin * 2)
            self._scale = max(0.28, min(1.25, available / max(1.0, page_size.width())))
        else:
            self._scale = max(0.25, min(2.5, self._manual_scale / 100.0))
        page_width = int(page_size.width() * self._scale)
        page_height = int(page_size.height() * self._scale)
        total_width = max(self._viewport_width(), page_width + self._outer_margin * 2)
        total_height = self._outer_margin * 2 + self._page_count * page_height + max(0, self._page_count - 1) * self._page_gap
        self.setMinimumSize(total_width, total_height)
        self.resize(total_width, total_height)
        self.update()

    def set_zoom_percent(self, percent):
        self._manual_scale = None if percent is None else max(25, min(250, int(percent)))
        self._refresh_geometry()

    def zoom_percent(self) -> int:
        return int(self._manual_scale if self._manual_scale is not None else round(self._scale * 100))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._manual_scale is None:
            self._refresh_geometry()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#06131c"))
        page_size = self._page_size()
        page_width = int(page_size.width() * self._scale)
        page_height = int(page_size.height() * self._scale)
        x = max(self._outer_margin, (self.width() - page_width) // 2)
        for page_index in range(max(1, self._page_count)):
            y = self._outer_margin + page_index * (page_height + self._page_gap)
            page_rect = QRect(x, y, page_width, page_height)
            painter.fillRect(page_rect.translated(7, 8), QColor(0, 0, 0, 115))
            painter.fillRect(page_rect, QColor("#ffffff"))
            if self._document is None and not self._page_cache:
                if page_index == 0 and self._message:
                    painter.setPen(QColor("#23313a"))
                    painter.setFont(QFont("Georgia", 13, QFont.Bold))
                    painter.drawText(page_rect.adjusted(25, 25, -25, -25), Qt.AlignCenter | Qt.TextWordWrap, self._message)
                continue
            if page_index < len(self._page_cache):
                painter.drawImage(page_rect, self._page_cache[page_index])
            painter.setPen(QPen(QColor("#c99b4e"), 1))
            painter.drawRect(page_rect.adjusted(0, 0, -1, -1))
        painter.end()


class SportsDayPrintMixin:
    """Tisková část SportsDayDialog bez vlastního stavu."""

    def _event_card_roster_people(self) -> list[dict]:
        """Vrátí osoby z modulu Oddíly ve tvaru použitelném pro A6 kartičky."""
        people = []
        for entry in roster_entries():
            name = " ".join(str(entry.get("name") or "").split())
            if not name:
                continue
            age = ""
            for label, value in (entry.get("fields") or {}).items():
                if normalized_label(label) == "vek":
                    age = " ".join(str(value or "").split())
                    break
            people.append(
                {
                    "name": name,
                    "age": age,
                    "group_name": " ".join(str(entry.get("group_name") or "").split()),
                    "role": " ".join(str(entry.get("role") or "").split()),
                }
            )
        return people

    def _draw_event_a6_card(
        self,
        painter: QPainter,
        card_rect: QRect,
        event: dict,
        writing_rows: int,
        show_logo: bool = True,
    ):
        """Nakreslí jednu fyzickou A6 kartičku určenou k popisování fixou."""
        painter.save()
        painter.setClipRect(card_rect)
        background = self._sports_print_background_image("A6", "Na výšku")
        painter.drawImage(card_rect, background)

        painter.translate(card_rect.topLeft())
        width, height = card_rect.width(), card_rect.height()
        painter.setPen(QPen(QColor("#d5a34c"), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRect(8, 8, width - 17, height - 17))

        if show_logo and not self.coin_pixmap.isNull():
            painter.drawPixmap(
                42,
                38,
                self.coin_pixmap.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation),
            )

        title = str(event.get("name") or "VÝZVA").upper()
        title_left = 112 if show_logo else 42
        title_rect = QRect(title_left, 30, width - title_left - 42, 92)
        title_size = 25
        while title_size > 16:
            title_font = QFont("Georgia", title_size, QFont.Bold)
            painter.setFont(title_font)
            if painter.fontMetrics().boundingRect(title_rect, Qt.TextWordWrap, title).height() <= title_rect.height():
                break
            title_size -= 1
        painter.setPen(QColor("#f4dea4"))
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, title)

        metric = self.METRICS.get(event.get("metric"), self.METRICS["time"])
        direction = "NEJNIŽŠÍ VYHRÁVÁ" if event.get("direction") == "asc" else "NEJVYŠŠÍ VYHRÁVÁ"
        meta_font = QFont("Georgia", 12, QFont.Bold)
        painter.setFont(meta_font)
        painter.setPen(QColor("#ead39b"))
        painter.drawText(QRect(44, 126, width - 88, 28), Qt.AlignLeft | Qt.AlignVCenter, f"MĚŘÍ SE: {metric['label'].upper()}")
        painter.drawText(QRect(44, 154, width - 88, 28), Qt.AlignLeft | Qt.AlignVCenter, direction)
        unit_font = QFont("Georgia", 10)
        painter.setFont(unit_font)
        painter.setPen(QColor("#d4c79f"))
        painter.drawText(QRect(44, 183, width - 88, 25), Qt.AlignLeft | Qt.AlignVCenter, f"ZAPISUJ: {metric['unit']}")

        # Světlý pergamen je záměrně neprůhledný: na vytištěnou či zalaminovanou
        # kartičku se musí dát pohodlně psát černým i barevným fixem.
        table_rect = QRect(42, 220, width - 84, height - 296)
        painter.setPen(QPen(QColor("#9a7132"), 3))
        painter.setBrush(QColor("#f6edcf"))
        painter.drawRoundedRect(table_rect, 9, 9)

        header_height = 48
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#0b4652"))
        painter.drawRect(QRect(table_rect.left() + 2, table_rect.top() + 2, table_rect.width() - 4, header_height))

        split_x = table_rect.left() + int(table_rect.width() * 0.64)
        row_height = (table_rect.height() - header_height) / max(1, writing_rows)
        painter.setPen(QPen(QColor("#9a7132"), 2))
        painter.drawLine(split_x, table_rect.top(), split_x, table_rect.bottom())
        for row in range(writing_rows + 1):
            y = round(table_rect.top() + header_height + row * row_height)
            painter.drawLine(table_rect.left(), y, table_rect.right(), y)

        painter.setFont(QFont("Georgia", 11, QFont.Bold))
        painter.setPen(QColor("#fff0bd"))
        painter.drawText(QRect(table_rect.left() + 10, table_rect.top(), split_x - table_rect.left() - 20, header_height), Qt.AlignVCenter, "PIRÁT / TÝM")
        painter.drawText(QRect(split_x + 10, table_rect.top(), table_rect.right() - split_x - 18, header_height), Qt.AlignCenter, "VÝSLEDEK")

        painter.setFont(QFont("Georgia", 10, QFont.Bold))
        painter.setPen(QColor("#ead39b"))
        footer_y = table_rect.bottom() + 14
        painter.drawText(QRect(44, footer_y, width - 88, 28), Qt.AlignLeft | Qt.AlignVCenter, "VÍTĚZ: __________________________________")
        painter.drawText(QRect(44, footer_y + 29, width - 88, 28), Qt.AlignLeft | Qt.AlignVCenter, "VEDOUCÍ: _________________________________")
        painter.restore()

    def _draw_event_list_a6_card(
        self,
        painter: QPainter,
        card_rect: QRect,
        events: list[dict],
        use_background: bool = True,
        economical_print: bool = False,
        show_logo: bool = True,
        card_person: dict | None = None,
        card_title: str = "PIRÁTSKÉ VÝZVY",
        show_title: bool = True,
        show_frames: bool = True,
        text_size: int = 10,
        heading_size: int = 23,
        font_family: str = "serif",
        font_style: str = "bold",
    ):
        """Jedna A6 karta obsahující všechny výzvy a pole pro ruční výsledky."""
        painter.save()
        painter.setClipRect(card_rect)
        if use_background:
            painter.drawImage(
                card_rect,
                self._sports_print_background_image("A6", "Na výšku", economical_print),
            )
        else:
            painter.fillRect(card_rect, QColor("#ffffff"))
        painter.translate(card_rect.topLeft())
        width, height = card_rect.width(), card_rect.height()

        light_style = economical_print or not use_background
        accent = QColor("#8a632c") if light_style else QColor("#d5a34c")
        title_color = QColor("#3d200d") if light_style else QColor("#f4dea4")
        text_color = QColor("#4a2d16") if light_style else QColor("#ead39b")
        grid_color = QColor("#8a632c") if light_style else QColor("#d5a34c")
        base_text_size = max(7, min(14, int(text_size or 10)))
        title_font_size = max(16, min(32, int(heading_size or 23)))
        icons_path = getattr(self, "icons_path", "")
        if show_frames:
            painter.setPen(QPen(accent, 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRect(8, 8, width - 17, height - 17))
        if show_logo and not self.coin_pixmap.isNull():
            painter.drawPixmap(38, 27, self.coin_pixmap.scaled(54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        title_left = 104 if show_logo else 40
        if show_title:
            painter.setFont(_sports_print_qfont(font_family, title_font_size, font_style, icons_path))
            painter.setPen(title_color)
            painter.drawText(
                QRect(title_left, 24, width - title_left - 40, 48),
                Qt.AlignLeft | Qt.AlignVCenter,
                str(card_title or "PIRÁTSKÉ VÝZVY").upper(),
            )
        painter.setFont(_sports_print_qfont(font_family, base_text_size, font_style, icons_path))
        painter.setPen(text_color)
        person_name = " ".join(str((card_person or {}).get("name") or "").split())
        person_age = " ".join(str((card_person or {}).get("age") or "").split())
        name_text = f"JMÉNO PIRÁTA: {person_name}" if person_name else "JMÉNO PIRÁTA: __________________________"
        age_text = f"VĚK: {person_age}" if person_age else "VĚK: ______"

        def draw_fitted(rect: QRect, text: str, start_size: int = base_text_size):
            size = start_size
            while size > 7:
                font = _sports_print_qfont(font_family, size, font_style, icons_path)
                painter.setFont(font)
                if painter.fontMetrics().horizontalAdvance(text) <= rect.width():
                    break
                size -= 1
            painter.drawText(
                rect,
                Qt.AlignLeft | Qt.AlignVCenter,
                painter.fontMetrics().elidedText(text, Qt.ElideRight, rect.width()),
            )

        draw_fitted(QRect(40, 78, width - 210, 29), name_text)
        draw_fitted(QRect(width - 195, 78, 155, 29), age_text)

        table_rect = QRect(38, 116, width - 76, height - 190)
        if show_frames:
            painter.setPen(QPen(grid_color, 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(table_rect, 8, 8)

        header_height = 42

        count = max(1, len(events))
        row_height = (table_rect.height() - header_height) / count
        number_x = table_rect.left() + 48
        result_x = table_rect.left() + int(table_rect.width() * 0.69)
        if show_frames:
            painter.setPen(QPen(grid_color, 2))
            painter.drawLine(number_x, table_rect.top(), number_x, table_rect.bottom())
            painter.drawLine(result_x, table_rect.top(), result_x, table_rect.bottom())
            for row in range(count + 1):
                y = round(table_rect.top() + header_height + row * row_height)
                painter.drawLine(table_rect.left(), y, table_rect.right(), y)

        painter.setFont(_sports_print_qfont(font_family, base_text_size, font_style, icons_path))
        painter.setPen(title_color)
        painter.drawText(QRect(table_rect.left(), table_rect.top(), 48, header_height), Qt.AlignCenter, "#")
        painter.drawText(QRect(number_x + 8, table_rect.top(), result_x - number_x - 16, header_height), Qt.AlignVCenter, "VÝZVA")
        painter.drawText(QRect(result_x + 5, table_rect.top(), table_rect.right() - result_x - 10, header_height), Qt.AlignCenter, "VÝSLEDEK")

        row_font_size = max(7, min(base_text_size + 1, int(row_height * 0.30)))
        painter.setFont(_sports_print_qfont(font_family, row_font_size, font_style, icons_path))
        painter.setPen(text_color)
        for index, event in enumerate(events):
            y = round(table_rect.top() + header_height + index * row_height)
            row_rect = QRect(table_rect.left(), y, table_rect.width(), max(1, round(row_height)))
            metric = self.METRICS.get(event.get("metric"), self.METRICS["time"])
            painter.drawText(QRect(row_rect.left(), row_rect.top(), 48, row_rect.height()), Qt.AlignCenter, str(index + 1))
            event_text = f"{event.get('name') or 'Výzva'}  •  {metric['label']}"
            painter.drawText(
                QRect(number_x + 8, row_rect.top(), result_x - number_x - 16, row_rect.height()),
                Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
                painter.fontMetrics().elidedText(event_text, Qt.ElideRight, result_x - number_x - 18),
            )

        painter.setFont(_sports_print_qfont(font_family, base_text_size, font_style, icons_path))
        painter.setPen(text_color)
        painter.drawText(QRect(40, table_rect.bottom() + 11, width - 80, 28), Qt.AlignLeft | Qt.AlignVCenter, "MINCE CELKEM: __________")
        painter.restore()

    def _build_event_card_sheets(
        self,
        cut_lines: bool = True,
        use_background: bool = True,
        economical_print: bool = False,
        show_logo: bool = True,
        card_people: list[dict] | None = None,
        card_title: str = "PIRÁTSKÉ VÝZVY",
        show_title: bool = True,
        show_frames: bool = True,
        text_size: int = 10,
        heading_size: int = 23,
        font_family: str = "serif",
        font_style: str = "bold",
    ):
        """A4 listy se čtyřmi A6 kartami; každá obsahuje všechny výzvy."""
        page_width, page_height = 1240, 1754
        card_width, card_height = page_width // 2, page_height // 2
        people = [
            {
                "name": " ".join(str((person or {}).get("name") or "").split()),
                "age": " ".join(str((person or {}).get("age") or "").split()),
            }
            for person in (card_people or [])
            if str((person or {}).get("name") or "").strip() or str((person or {}).get("age") or "").strip()
        ]
        if not people:
            people = [{} for _index in range(4)]
        else:
            missing_slots = (-len(people)) % 4
            people.extend({} for _index in range(missing_slots))

        sheets = []
        for page_start in range(0, len(people), 4):
            page_people = people[page_start:page_start + 4]
            page = QImage(page_width, page_height, QImage.Format_ARGB32_Premultiplied)
            page.fill(QColor("#ffffff"))
            painter = QPainter(page)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            for slot in range(4):
                column = slot % 2
                row = slot // 2
                card_rect = QRect(column * card_width, row * card_height, card_width, card_height)
                self._draw_event_list_a6_card(
                    painter,
                    card_rect,
                    self.events,
                    use_background,
                    economical_print,
                    show_logo,
                    page_people[slot] if slot < len(page_people) else {},
                    card_title,
                    show_title,
                    show_frames,
                    text_size,
                    heading_size,
                    font_family,
                    font_style,
                )
            if cut_lines:
                cut_pen = QPen(QColor(245, 219, 151, 225), 2, Qt.DashLine)
                painter.setPen(cut_pen)
                painter.drawLine(card_width, 0, card_width, page_height)
                painter.drawLine(0, card_height, page_width, card_height)
            painter.end()
            sheets.append(page)
        return sheets

    def _paint_event_card_sheets(self, printer, sheets: list[QImage]):
        try:
            from PySide6.QtPrintSupport import QPrinter

            painter = QPainter(printer)
            if not painter.isActive():
                return
            for page_index, sheet in enumerate(sheets):
                if page_index and not printer.newPage():
                    break
                try:
                    target = QRectF(printer.paperRect(QPrinter.DevicePixel))
                except Exception:
                    target = QRectF(printer.pageRect(QPrinter.DevicePixel))
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.drawImage(target, sheet)
            painter.end()
        except Exception as error:
            QMessageBox.warning(self, "Tisk se nezdařil", f"Kartičky se nepodařilo vykreslit:\n{error}")

    def _show_event_cards_print(self):
        if not self.events:
            QMessageBox.information(self, "Žádné výzvy", "Nejdřív vytvoř alespoň jednu výzvu.")
            return
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        except Exception as error:
            QMessageBox.warning(self, "Tisk není dostupný", f"Nepodařilo se načíst podporu tisku:\n{error}")
            return

        dialog = QDialog(self)
        dialog.setObjectName("eventCardsPrintDialog")
        dialog.setWindowTitle("Tisk kartiček výzev • A6 po čtyřech na A4")
        dialog.resize(1180, 820)
        dialog.setMinimumSize(860, 620)
        background_path = os.path.join(self.icons_path, "sports_day_BG.png").replace("\\", "/")
        dialog.setStyleSheet(
            self._style_sheet()
            + """
            QDialog#eventCardsPrintDialog { background:#061923; border-image:url("__BG__") 0 0 0 0 stretch stretch; }
            QFrame#cardPrintPanel { background:rgba(4,22,31,238); border:1px solid #a57b38; border-radius:12px; }
            QScrollArea#cardPaperArea { background:#07111f; border:1px solid #a57b38; border-radius:9px; }
            QScrollArea#cardControlsArea { background:transparent; border:none; }
            QLabel#cardPrintTitle { color:#f4dea4; font-size:20px; font-weight:bold; }
            """.replace("__BG__", background_path)
        )
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)
        roster_people = self._event_card_roster_people()

        title = QLabel("KARTIČKY VÝZEV A6 • 4 KARTIČKY NA JEDNOM A4", dialog)
        title.setObjectName("cardPrintTitle")
        outer.addWidget(title)
        subtitle = QLabel(
            f"Všech {len(self.events)} výzev je na každé kartičce A6. Jeden list A4 obsahuje čtyři kartičky. "
            "Každé další čtyři vyplněné osoby vytvoří další list. Po vytištění je rozstřihni podle středových linek.",
            dialog,
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#d8c392;font-size:12px;")
        outer.addWidget(subtitle)

        content = QHBoxLayout()
        content.setSpacing(12)
        outer.addLayout(content, 1)

        controls_scroll = QScrollArea(dialog)
        controls_scroll.setObjectName("cardControlsArea")
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(390)
        controls_scroll.setMaximumWidth(430)

        controls = QFrame(controls_scroll)
        controls.setObjectName("cardPrintPanel")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(10)
        controls_layout.addWidget(QLabel("RUČNÍ ZAPISOVÁNÍ", controls))
        challenge_count = QLabel(f"Každá A6 kartička: {len(self.events)} výzev a {len(self.events)} polí pro výsledky", controls)
        challenge_count.setWordWrap(True)
        challenge_count.setStyleSheet("color:#f4dea4;font-weight:bold;")
        controls_layout.addWidget(challenge_count)

        controls_layout.addWidget(QLabel("LIDÉ NA KARTIČKÁCH", controls))
        autofill_people = QCheckBox("Doplnit lidi automaticky z Oddílů", controls)
        autofill_people.setEnabled(bool(roster_people))
        if not roster_people:
            autofill_people.setToolTip("V modulu Oddíly zatím nejsou uložená žádná jména.")
        controls_layout.addWidget(autofill_people)

        person_status = QLabel("", controls)
        person_status.setWordWrap(True)
        person_status.setStyleSheet("color:#d8c392;font-size:12px;")
        controls_layout.addWidget(person_status)

        completion_people = {}
        completion_labels = []
        for person in roster_people:
            detail = " • ".join(
                part for part in (
                    person.get("group_name"),
                    person.get("role"),
                    f"{person.get('age')} let" if person.get("age") else "",
                )
                if part
            )
            base_label = f"{person.get('name')} - {detail}" if detail else str(person.get("name") or "")
            label = base_label
            duplicate = 2
            while label in completion_people:
                label = f"{base_label} ({duplicate})"
                duplicate += 1
            completion_people[label] = person
            completion_labels.append(label)

        refresh_preview = {"callback": None}

        def request_preview(*_args):
            callback = refresh_preview.get("callback")
            if callback is not None:
                callback()

        def attach_roster_completer(name_edit: QLineEdit, age_edit: QLineEdit):
            if not completion_labels:
                return
            completer = QCompleter(completion_labels, name_edit)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(QCompleter.PopupCompletion)

            def use_completion(label: str, target_name=name_edit, target_age=age_edit):
                person = completion_people.get(str(label))
                if person is None:
                    return
                name = str(person.get("name") or "")
                target_name.setText(name)
                target_name.setCursorPosition(len(name))
                target_age.setText(str(person.get("age") or ""))

            completer.activated.connect(use_completion)
            name_edit.setCompleter(completer)

        manual_people_scroll = QScrollArea(controls)
        manual_people_scroll.setWidgetResizable(True)
        manual_people_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        manual_people_scroll.setFixedHeight(210)
        manual_people_scroll.setStyleSheet("QScrollArea { background:rgba(6,28,38,170); border:1px solid #8d6830; border-radius:8px; }")
        manual_people_host = QWidget(manual_people_scroll)
        manual_people_host.setStyleSheet("background:transparent;")
        manual_people_layout = QVBoxLayout(manual_people_host)
        manual_people_layout.setContentsMargins(7, 7, 7, 7)
        manual_people_layout.setSpacing(5)

        people_header = QWidget(manual_people_host)
        people_header_layout = QHBoxLayout(people_header)
        people_header_layout.setContentsMargins(0, 0, 0, 0)
        people_header_layout.setSpacing(6)
        number_header = QLabel("#", people_header)
        number_header.setFixedWidth(24)
        name_header = QLabel("Jméno", people_header)
        age_header = QLabel("Věk", people_header)
        age_header.setFixedWidth(54)
        people_header_layout.addWidget(number_header)
        people_header_layout.addWidget(name_header, 1)
        people_header_layout.addWidget(age_header)
        people_header_layout.addSpacing(34)
        manual_people_layout.addWidget(people_header)
        manual_people_layout.addStretch(1)
        manual_people_scroll.setWidget(manual_people_host)
        controls_layout.addWidget(manual_people_scroll)

        manual_person_rows = []

        def refresh_person_row_numbers():
            for index, row in enumerate(manual_person_rows, 1):
                row["number"].setText(str(index))
                row["remove"].setEnabled(len(manual_person_rows) > 1)

        def add_person_row(person: dict | None = None, focus: bool = False):
            person = person or {}
            row_widget = QWidget(manual_people_host)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            number_label = QLabel("", row_widget)
            number_label.setAlignment(Qt.AlignCenter)
            number_label.setFixedWidth(24)
            name_edit = QLineEdit(row_widget)
            name_edit.setPlaceholderText("Jméno z Oddílů nebo vlastní")
            age_edit = QLineEdit(row_widget)
            age_edit.setPlaceholderText("Věk")
            age_edit.setFixedWidth(54)
            remove_button = QPushButton("×", row_widget)
            remove_button.setObjectName("dangerButton")
            remove_button.setFixedWidth(30)
            attach_roster_completer(name_edit, age_edit)
            name_edit.setText(str(person.get("name") or ""))
            age_edit.setText(str(person.get("age") or ""))
            row_layout.addWidget(number_label)
            row_layout.addWidget(name_edit, 1)
            row_layout.addWidget(age_edit)
            row_layout.addWidget(remove_button)
            row = {
                "widget": row_widget,
                "number": number_label,
                "name": name_edit,
                "age": age_edit,
                "remove": remove_button,
            }

            def remove_row(_checked=False, target=row):
                if target not in manual_person_rows:
                    return
                manual_person_rows.remove(target)
                manual_people_layout.removeWidget(target["widget"])
                target["widget"].deleteLater()
                if not manual_person_rows:
                    add_person_row()
                refresh_person_row_numbers()
                request_preview()

            remove_button.clicked.connect(remove_row)
            name_edit.textChanged.connect(request_preview)
            age_edit.textChanged.connect(request_preview)
            manual_person_rows.append(row)
            manual_people_layout.insertWidget(max(1, manual_people_layout.count() - 1), row_widget)
            refresh_person_row_numbers()
            if focus:
                name_edit.setFocus()
            return row

        def replace_person_rows(people: list[dict] | None = None, minimum_rows: int = 4):
            for row in list(manual_person_rows):
                manual_person_rows.remove(row)
                manual_people_layout.removeWidget(row["widget"])
                row["widget"].deleteLater()
            source = list(people or [])
            while len(source) < minimum_rows:
                source.append({})
            for person in source:
                add_person_row(person)
            refresh_person_row_numbers()
            request_preview()

        person_buttons = QHBoxLayout()
        add_person_button = QPushButton("PŘIDAT", controls)
        add_four_people_button = QPushButton("+4", controls)
        clear_people_button = QPushButton("VYČISTIT", controls)
        person_buttons.addWidget(add_person_button)
        person_buttons.addWidget(add_four_people_button)
        person_buttons.addWidget(clear_people_button)
        controls_layout.addLayout(person_buttons)

        controls_layout.addWidget(QLabel("MODIFIKACE TISKU", controls))
        appearance_combo = QComboBox(controls)
        appearance_combo.addItem("Pirátské pozadí • průhledná tabulka", "pirate")
        appearance_combo.addItem("Bez pozadí • čistě bílé", "simple")
        controls_layout.addWidget(appearance_combo)
        title_edit = QLineEdit("PIRÁTSKÉ VÝZVY", controls)
        title_edit.setPlaceholderText("Nadpis kartičky")
        controls_layout.addWidget(title_edit)
        font_family_combo = QComboBox(controls)
        for key, family in SPORTS_PRINT_FONT_FAMILIES.items():
            font_family_combo.addItem(family["label"], key)
        font_family_combo.setCurrentIndex(max(0, font_family_combo.findData("serif")))
        font_style_combo = QComboBox(controls)
        for key, style in SPORTS_PRINT_FONT_STYLES.items():
            font_style_combo.addItem(style["label"], key)
        font_style_combo.setCurrentIndex(max(0, font_style_combo.findData("bold")))
        type_grid = QGridLayout()
        type_grid.setContentsMargins(0, 0, 0, 0)
        type_grid.setHorizontalSpacing(8)
        type_grid.setVerticalSpacing(6)
        type_grid.addWidget(QLabel("Písmo:"), 0, 0)
        type_grid.addWidget(font_family_combo, 0, 1)
        type_grid.addWidget(QLabel("Styl:"), 1, 0)
        type_grid.addWidget(font_style_combo, 1, 1)
        controls_layout.addLayout(type_grid)
        economical_print = QCheckBox("Šetrný tisk • světlé pirátské pozadí", controls)
        economical_print.setChecked(False)
        controls_layout.addWidget(economical_print)
        show_logo = QCheckBox("Zobrazit logo / pirátský znak", controls)
        show_logo.setChecked(True)
        controls_layout.addWidget(show_logo)
        show_title = QCheckBox("Zobrazit nadpis kartičky", controls)
        show_title.setChecked(True)
        controls_layout.addWidget(show_title)
        show_frames = QCheckBox("Zobrazit rámečky a linky", controls)
        show_frames.setChecked(True)
        controls_layout.addWidget(show_frames)
        cut_lines = QCheckBox("Zobrazit stříhací linky", controls)
        cut_lines.setChecked(True)
        controls_layout.addWidget(cut_lines)
        sizes = QGridLayout()
        sizes.setContentsMargins(0, 0, 0, 0)
        sizes.setHorizontalSpacing(8)
        sizes.setVerticalSpacing(6)
        text_size = QSpinBox(controls)
        text_size.setRange(7, 14)
        text_size.setValue(10)
        text_size.setSuffix(" bodů")
        heading_size = QSpinBox(controls)
        heading_size.setRange(16, 32)
        heading_size.setValue(23)
        heading_size.setSuffix(" bodů")
        sizes.addWidget(QLabel("Text:"), 0, 0)
        sizes.addWidget(text_size, 0, 1)
        sizes.addWidget(QLabel("Nadpis:"), 1, 0)
        sizes.addWidget(heading_size, 1, 1)
        controls_layout.addLayout(sizes)
        note = QLabel(
            "Všechny výzvy jsou společně na jedné A6. Řádků může být libovolně; prázdné řádky se netisknou, pokud je vyplněný aspoň jeden člověk.",
            controls,
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#d8c392;font-size:12px;")
        controls_layout.addWidget(note)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(QLabel("MĚŘÍTKO NÁHLEDU", controls))
        zoom_row = QHBoxLayout()
        zoom_out = QPushButton("−", controls)
        zoom_in = QPushButton("+", controls)
        zoom_fit = QPushButton("PŘIZPŮSOBIT", controls)
        zoom_row.addWidget(zoom_out)
        zoom_row.addWidget(zoom_in)
        zoom_row.addWidget(zoom_fit, 1)
        controls_layout.addLayout(zoom_row)
        zoom_label = QLabel("", controls)
        zoom_label.setStyleSheet("color:#d8c392;")
        controls_layout.addWidget(zoom_label)
        controls_layout.addStretch(1)
        controls_scroll.setWidget(controls)
        content.addWidget(controls_scroll)

        preview_frame = QFrame(dialog)
        preview_frame.setObjectName("cardPrintPanel")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 10, 12, 12)
        preview_layout.addWidget(QLabel("ŽIVÝ NÁHLED LISTŮ A4", preview_frame))
        paper_scroll = QScrollArea(preview_frame)
        paper_scroll.setObjectName("cardPaperArea")
        paper_scroll.setWidgetResizable(False)
        paper_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        preview = _SportsPrintPreviewWidget(self, paper_scroll)
        paper_scroll.setWidget(preview)
        preview_layout.addWidget(paper_scroll, 1)
        content.addWidget(preview_frame, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close_button = QPushButton("ZRUŠIT", dialog)
        close_button.setObjectName("quietButton")
        pdf_button = QPushButton("ULOŽIT PDF", dialog)
        print_button = QPushButton("TISKNOUT KARTIČKY", dialog)
        print_button.setObjectName("printButton")
        buttons.addWidget(close_button)
        buttons.addWidget(pdf_button)
        buttons.addWidget(print_button)
        outer.addLayout(buttons)

        state = {"sheets": []}

        def current_card_people():
            return [
                {
                    "name": row["name"].text().strip(),
                    "age": row["age"].text().strip(),
                }
                for row in manual_person_rows
            ]

        def filled_person_count(people: list[dict]) -> int:
            return sum(
                1
                for person in people
                if str((person or {}).get("name") or "").strip()
                or str((person or {}).get("age") or "").strip()
            )

        def update_preview(*_args):
            card_people = current_card_people()
            sheets = self._build_event_card_sheets(
                cut_lines.isChecked(),
                appearance_combo.currentData() == "pirate",
                economical_print.isChecked(),
                show_logo.isChecked(),
                card_people,
                title_edit.text().strip() or "PIRÁTSKÉ VÝZVY",
                show_title.isChecked(),
                show_frames.isChecked(),
                text_size.value(),
                heading_size.value(),
                font_family_combo.currentData(),
                font_style_combo.currentData(),
            )
            state["sheets"] = sheets
            preview.set_page_images(sheets, QSizeF(595, 842))
            zoom_label.setText(f"Měřítko náhledu: {preview.zoom_percent()} %")
            count = filled_person_count(card_people)
            if autofill_people.isChecked():
                person_status.setText(f"Seznam z Oddílů: {count} lidí • {len(sheets)} listů A4. Jména i věk můžeš ještě upravit.")
            else:
                person_status.setText(f"Ručně: vyplněno {count} řádků z {len(manual_person_rows)} • {len(sheets)} listů A4.")
            print_button.setEnabled(bool(sheets))
            pdf_button.setEnabled(bool(sheets))

        refresh_preview["callback"] = update_preview

        def update_zoom_label():
            zoom_label.setText(f"Měřítko náhledu: {preview.zoom_percent()} %")

        def add_blank_rows(count: int = 1):
            if autofill_people.isChecked():
                autofill_people.setChecked(False)
            for index in range(max(1, int(count))):
                add_person_row(focus=index == 0)
            request_preview()

        def clear_people():
            autofill_people.blockSignals(True)
            autofill_people.setChecked(False)
            autofill_people.blockSignals(False)
            replace_person_rows([], 4)

        def fill_people_from_roster(checked: bool):
            if checked:
                replace_person_rows(roster_people, 4)
            else:
                request_preview()

        cut_lines.toggled.connect(update_preview)
        economical_print.toggled.connect(update_preview)
        show_logo.toggled.connect(update_preview)
        show_title.toggled.connect(lambda checked: (title_edit.setEnabled(checked), update_preview()))
        show_frames.toggled.connect(update_preview)
        appearance_combo.currentIndexChanged.connect(update_preview)
        font_family_combo.currentIndexChanged.connect(update_preview)
        font_style_combo.currentIndexChanged.connect(update_preview)
        title_edit.textChanged.connect(update_preview)
        text_size.valueChanged.connect(update_preview)
        heading_size.valueChanged.connect(update_preview)
        autofill_people.toggled.connect(fill_people_from_roster)
        add_person_button.clicked.connect(lambda: add_blank_rows(1))
        add_four_people_button.clicked.connect(lambda: add_blank_rows(4))
        clear_people_button.clicked.connect(clear_people)
        zoom_out.clicked.connect(lambda: (preview.set_zoom_percent(preview.zoom_percent() - 10), update_zoom_label()))
        zoom_in.clicked.connect(lambda: (preview.set_zoom_percent(preview.zoom_percent() + 10), update_zoom_label()))
        zoom_fit.clicked.connect(lambda: (preview.set_zoom_percent(None), update_zoom_label()))
        close_button.clicked.connect(dialog.reject)

        def prepare_printer():
            printer = QPrinter(QPrinter.HighResolution)
            self._apply_sports_print_page_setup(printer, "A4", "Na výšku")
            return printer

        def do_print():
            printer = prepare_printer()
            print_dialog = QPrintDialog(printer, dialog)
            print_dialog.setWindowTitle("Tisk kartiček výzev A6")
            if print_dialog.exec() == QDialog.Accepted:
                self._paint_event_card_sheets(printer, state["sheets"])

        def save_pdf():
            path, _ = QFileDialog.getSaveFileName(dialog, "Uložit kartičky výzev", "karticky-vyzev-A6.pdf", "PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            printer = prepare_printer()
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            self._paint_event_card_sheets(printer, state["sheets"])
            QMessageBox.information(dialog, "PDF uloženo", f"Kartičky byly uloženy do:\n{path}")

        print_button.clicked.connect(do_print)
        pdf_button.clicked.connect(save_pdf)
        replace_person_rows([], 4)
        dialog.exec()

    def _show_print_options(self):
        return self._show_sports_print_studio()

    def _show_sports_print_studio(self):
        """Jedno živé tiskové studio se stejným ovládáním jako tisk Šifrátoru."""
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        except Exception as error:
            QMessageBox.warning(self, "Tisk není dostupný", f"Nepodařilo se načíst podporu tisku:\n{error}")
            return

        dialog = QDialog(self)
        dialog.setObjectName("printOptionsDialog")
        dialog.setWindowTitle("Tiskové studio • Pirátský sportovní den")
        screen = self.window().screen() if self.window() is not None else None
        available = screen.availableGeometry() if screen is not None else QRect(0, 0, 1360, 860)
        dialog_width = min(1380, max(900, int(available.width() * 0.94)))
        dialog_height = min(900, max(650, int(available.height() * 0.92)))
        dialog.resize(dialog_width, dialog_height)
        dialog.setMinimumSize(min(900, dialog_width), min(630, dialog_height))

        print_background = os.path.join(self.icons_path, "sports_day_BG.png").replace("\\", "/")
        dialog.setStyleSheet(
            self._style_sheet()
            + """
            QDialog#printOptionsDialog {
                background-color: #061923;
                border-image: url("__PRINT_BACKGROUND__") 0 0 0 0 stretch stretch;
            }
            QFrame#printSide, QFrame#printPreviewFrame {
                background-color: rgba(4, 22, 31, 238);
                border: 1px solid #9d7839;
                border-radius: 13px;
            }
            QFrame#printBlock {
                background-color: rgba(8, 42, 52, 218);
                border: 1px solid rgba(190, 142, 61, 175);
                border-radius: 10px;
            }
            QLabel#printStudioTitle { color:#f4dea4; font-size:20px; font-weight:bold; letter-spacing:1px; }
            QLabel#printDetail { color:#d8c392; font-size:12px; }
            QScrollArea#printControls, QScrollArea#printPaperArea { background:transparent; border:none; }
            QScrollArea#printPaperArea { background-color:#07111f; border:1px solid #9d7839; border-radius:9px; }
            QSpinBox { min-width:88px; }
            QPushButton#pdfButton { background-color:rgba(94,55,19,225); }
            QPushButton#zoomButton { min-width:42px; padding:7px 10px; }
            """.replace("__PRINT_BACKGROUND__", print_background)
        )

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        heading_row = QHBoxLayout()
        coin_label = QLabel(dialog)
        coin_label.setFixedSize(52, 52)
        coin_label.setAlignment(Qt.AlignCenter)
        if not self.coin_pixmap.isNull():
            coin_label.setPixmap(self.coin_pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        heading_row.addWidget(coin_label)
        heading_text = QVBoxLayout()
        heading_text.setSpacing(1)
        studio_title = QLabel("TISKOVÉ STUDIO SPORTOVNÍHO DNE", dialog)
        studio_title.setObjectName("printStudioTitle")
        heading_text.addWidget(studio_title)
        studio_hint = QLabel("Všechny změny vlevo se okamžitě projeví v náhledu. Pozadí pokrývá celý zvolený papír.", dialog)
        studio_hint.setObjectName("printDetail")
        heading_text.addWidget(studio_hint)
        heading_row.addLayout(heading_text, 1)
        outer.addLayout(heading_row)

        content = QHBoxLayout()
        content.setSpacing(12)
        outer.addLayout(content, 1)

        controls_scroll = QScrollArea(dialog)
        controls_scroll.setObjectName("printControls")
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_scroll.setMinimumWidth(350)
        controls_scroll.setMaximumWidth(430)
        controls_root = QFrame(controls_scroll)
        controls_root.setObjectName("printSide")
        controls_layout = QVBoxLayout(controls_root)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)
        controls_scroll.setWidget(controls_root)
        content.addWidget(controls_scroll)

        def make_block(title_text):
            frame = QFrame(controls_root)
            frame.setObjectName("printBlock")
            layout = QGridLayout(frame)
            layout.setContentsMargins(11, 10, 11, 11)
            layout.setHorizontalSpacing(9)
            layout.setVerticalSpacing(7)
            title_label = QLabel(title_text, frame)
            title_label.setStyleSheet("color:#f4dea4;font-size:14px;font-weight:bold;")
            layout.addWidget(title_label, 0, 0, 1, 2)
            layout.setColumnStretch(1, 1)
            return frame, layout

        selection_block, selection = make_block("CO A KOHO TISKNOUT")
        scope_combo = QComboBox(selection_block)
        scope_combo.addItem("Všichni podle kategorií", "all_categories")
        scope_combo.addItem("Jedna věková kategorie", "category")
        scope_combo.addItem("Jen dívky", "girls")
        scope_combo.addItem("Jen kluci", "boys")
        scope_combo.addItem("Všichni v jednom pořadí", "all")
        category_combo = QComboBox(selection_block)
        for category in self.categories:
            category_combo.addItem(str(category.get("name") or ""), category.get("id"))
        category_combo.setEnabled(False)
        event_combo = QComboBox(selection_block)
        event_combo.addItem("Všechny výzvy", "all")
        for event in self.events:
            event_combo.addItem(str(event.get("name") or ""), event.get("id"))
        order_combo = QComboBox(selection_block)
        order_combo.addItem("Podle výsledků a mincí", "results")
        order_combo.addItem("Abecedně", "alphabetical")
        print_events = QCheckBox("Výsledky jednotlivých výzev", selection_block)
        print_events.setChecked(bool(self.events))
        print_events.setEnabled(bool(self.events))
        print_treasure = QCheckBox("Celkový poklad a mince", selection_block)
        print_treasure.setChecked(True)
        selection.addWidget(QLabel("Posádka:"), 1, 0)
        selection.addWidget(scope_combo, 1, 1)
        selection.addWidget(QLabel("Kategorie:"), 2, 0)
        selection.addWidget(category_combo, 2, 1)
        selection.addWidget(QLabel("Výzvy:"), 3, 0)
        selection.addWidget(event_combo, 3, 1)
        selection.addWidget(QLabel("Pořadí:"), 4, 0)
        selection.addWidget(order_combo, 4, 1)
        selection.addWidget(print_events, 5, 0, 1, 2)
        selection.addWidget(print_treasure, 6, 0, 1, 2)
        controls_layout.addWidget(selection_block)

        look_block, look = make_block("MODIFIKACE TISKU")
        appearance_combo = QComboBox(look_block)
        appearance_combo.addItem("Pirátské pozadí • přes celý papír", "pirate")
        appearance_combo.addItem("Bez pozadí • čistě bílý", "simple")
        title_edit = QLineEdit("PIRÁTSKÝ SPORTOVNÍ DEN", look_block)
        font_family_combo = QComboBox(look_block)
        for key, family in SPORTS_PRINT_FONT_FAMILIES.items():
            font_family_combo.addItem(family["label"], key)
        font_family_combo.setCurrentIndex(max(0, font_family_combo.findData("default")))
        font_style_combo = QComboBox(look_block)
        for key, style in SPORTS_PRINT_FONT_STYLES.items():
            font_style_combo.addItem(style["label"], key)
        font_style_combo.setCurrentIndex(max(0, font_style_combo.findData("regular")))
        economical_print = QCheckBox("Šetrný tisk • světlé pirátské pozadí", look_block)
        economical_print.setChecked(False)
        show_logo = QCheckBox("Zobrazit logo / pirátský znak", look_block)
        show_logo.setChecked(True)
        show_title = QCheckBox("Zobrazit hlavní nadpis", look_block)
        show_title.setChecked(True)
        show_summary = QCheckBox("Zobrazit souhrnné dlaždice", look_block)
        show_summary.setChecked(True)
        show_frames = QCheckBox("Zobrazit rámečky tabulek", look_block)
        show_frames.setChecked(True)
        look.addWidget(QLabel("Varianta:"), 1, 0)
        look.addWidget(appearance_combo, 1, 1)
        look.addWidget(QLabel("Nadpis:"), 2, 0)
        look.addWidget(title_edit, 2, 1)
        look.addWidget(QLabel("Písmo:"), 3, 0)
        look.addWidget(font_family_combo, 3, 1)
        look.addWidget(QLabel("Styl:"), 4, 0)
        look.addWidget(font_style_combo, 4, 1)
        look.addWidget(economical_print, 5, 0, 1, 2)
        look.addWidget(show_logo, 6, 0, 1, 2)
        look.addWidget(show_title, 7, 0, 1, 2)
        look.addWidget(show_summary, 8, 0, 1, 2)
        look.addWidget(show_frames, 9, 0, 1, 2)
        controls_layout.addWidget(look_block)

        page_block, page = make_block("NASTAVENÍ STRÁNKY")
        paper_combo = QComboBox(page_block)
        paper_combo.addItems(["A4", "A5", "A3", "Letter", "Legal"])
        orientation_combo = QComboBox(page_block)
        orientation_combo.addItems(["Na výšku", "Na šířku"])
        font_size = QSpinBox(page_block)
        font_size.setRange(8, 16)
        font_size.setValue(10)
        font_size.setSuffix(" bodů")
        heading_size = QSpinBox(page_block)
        heading_size.setRange(12, 30)
        heading_size.setValue(15)
        heading_size.setSuffix(" bodů")
        margin_size = QSpinBox(page_block)
        margin_size.setRange(6, 25)
        margin_size.setValue(11)
        margin_size.setSuffix(" mm")
        page.addWidget(QLabel("Papír:"), 1, 0)
        page.addWidget(paper_combo, 1, 1)
        page.addWidget(QLabel("Orientace:"), 2, 0)
        page.addWidget(orientation_combo, 2, 1)
        page.addWidget(QLabel("Text tabulek:"), 3, 0)
        page.addWidget(font_size, 3, 1)
        page.addWidget(QLabel("Nadpisy sekcí:"), 4, 0)
        page.addWidget(heading_size, 4, 1)
        page.addWidget(QLabel("Bezpečný okraj:"), 5, 0)
        page.addWidget(margin_size, 5, 1)
        controls_layout.addWidget(page_block)

        zoom_block, zoom = make_block("MĚŘÍTKO NÁHLEDU")
        zoom_row = QHBoxLayout()
        zoom_out = QPushButton("−", zoom_block)
        zoom_in = QPushButton("+", zoom_block)
        zoom_fit = QPushButton("PŘIZPŮSOBIT", zoom_block)
        for button in (zoom_out, zoom_in, zoom_fit):
            button.setObjectName("zoomButton")
        zoom_row.addWidget(zoom_out)
        zoom_row.addWidget(zoom_in)
        zoom_row.addWidget(zoom_fit, 1)
        zoom.addLayout(zoom_row, 1, 0, 1, 2)
        zoom_label = QLabel("Automaticky", zoom_block)
        zoom_label.setObjectName("printDetail")
        zoom.addWidget(zoom_label, 2, 0, 1, 2)
        controls_layout.addWidget(zoom_block)
        controls_layout.addStretch(1)

        preview_frame = QFrame(dialog)
        preview_frame.setObjectName("printPreviewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(12, 10, 12, 12)
        preview_layout.setSpacing(5)
        preview_title = QLabel("ŽIVÝ NÁHLED FINÁLNÍHO TISKU", preview_frame)
        preview_title.setObjectName("printStudioTitle")
        preview_layout.addWidget(preview_title)
        preview_detail = QLabel(_sports_print_page_label("A4", "Na výšku"), preview_frame)
        preview_detail.setObjectName("printDetail")
        preview_layout.addWidget(preview_detail)
        paper_scroll = QScrollArea(preview_frame)
        paper_scroll.setObjectName("printPaperArea")
        paper_scroll.setWidgetResizable(False)
        paper_scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        paper_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        paper_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        live_preview = _SportsPrintPreviewWidget(self, paper_scroll)
        paper_scroll.setWidget(live_preview)
        preview_layout.addWidget(paper_scroll, 1)
        content.addWidget(preview_frame, 1)

        button_row = QHBoxLayout()
        status_label = QLabel("", dialog)
        status_label.setObjectName("printDetail")
        button_row.addWidget(status_label, 1)
        close_button = QPushButton("ZRUŠIT", dialog)
        close_button.setObjectName("quietButton")
        pdf_button = QPushButton("ULOŽIT PDF", dialog)
        pdf_button.setObjectName("pdfButton")
        print_button = QPushButton("TISKNOUT", dialog)
        print_button.setObjectName("printButton")
        if not self.coin_pixmap.isNull():
            print_button.setIcon(QIcon(self.coin_pixmap))
            print_button.setIconSize(QSize(24, 24))
        button_row.addWidget(close_button)
        button_row.addWidget(pdf_button)
        button_row.addWidget(print_button)
        outer.addLayout(button_row)

        state = {"document": None, "options": None, "competitors": []}

        def current_options():
            return {
                "scope": scope_combo.currentData(),
                "category_id": category_combo.currentData(),
                "event_id": event_combo.currentData(),
                "order": order_combo.currentData(),
                "appearance": appearance_combo.currentData(),
                "economical_print": economical_print.isChecked(),
                "show_logo": show_logo.isChecked(),
                "print_events": print_events.isChecked(),
                "print_treasure": print_treasure.isChecked(),
                "paper_name": paper_combo.currentText(),
                "orientation": orientation_combo.currentText(),
                "title": title_edit.text().strip() or "PIRÁTSKÝ SPORTOVNÍ DEN",
                "show_title": show_title.isChecked(),
                "show_summary": show_summary.isChecked(),
                "show_frames": show_frames.isChecked(),
                "font_family": font_family_combo.currentData(),
                "font_style": font_style_combo.currentData(),
                "font_size": font_size.value(),
                "heading_size": heading_size.value(),
                "margin_mm": margin_size.value(),
            }

        def update_preview():
            category_combo.setEnabled(scope_combo.currentData() == "category")
            options = current_options()
            competitors = self._print_competitors(options)
            valid = bool(competitors and (options["print_events"] or options["print_treasure"]))
            print_button.setEnabled(valid)
            pdf_button.setEnabled(valid)
            title_edit.setEnabled(show_title.isChecked())
            detail_text = _sports_print_page_label(options["paper_name"], options["orientation"])
            if options["economical_print"]:
                detail_text += " • ŠETRNÝ TISK"
            preview_detail.setText(detail_text)
            if not competitors:
                status_label.setText("Pro tento výběr není v posádce žádný pirát.")
                live_preview.set_message("Výběr je prázdný.")
                state.update(document=None, options=options, competitors=[])
                return
            if not options["print_events"] and not options["print_treasure"]:
                status_label.setText("Vyber alespoň výsledky výzev nebo poklad.")
                live_preview.set_message("Není vybrán žádný obsah k tisku.")
                state.update(document=None, options=options, competitors=competitors)
                return
            mode_label = "šetrný tisk" if options["economical_print"] else "plnobarevný tisk"
            status_label.setText(
                f"Piráti: {len(competitors)}  •  {mode_label}  •  Náhled se aktualizuje živě"
            )
            document = self._build_sports_print_document(options, competitors)
            state.update(document=document, options=options, competitors=competitors)
            live_preview.set_preview_document(document, options["appearance"] == "pirate")
            zoom_label.setText(f"Měřítko náhledu: {live_preview.zoom_percent()} %")

        preview_timer = QTimer(dialog)
        preview_timer.setSingleShot(True)
        preview_timer.timeout.connect(update_preview)

        def schedule_preview(*_args):
            preview_timer.start(70)

        immediate_widgets = [
            scope_combo, category_combo, event_combo, order_combo, appearance_combo,
            font_family_combo, font_style_combo, paper_combo, orientation_combo,
        ]
        for combo in immediate_widgets:
            combo.currentIndexChanged.connect(update_preview)
        for checkbox in (
            print_events,
            print_treasure,
            economical_print,
            show_logo,
            show_title,
            show_summary,
            show_frames,
        ):
            checkbox.toggled.connect(update_preview)
        for spin in (font_size, heading_size, margin_size):
            spin.valueChanged.connect(schedule_preview)
        title_edit.textChanged.connect(schedule_preview)

        def update_zoom_label():
            zoom_label.setText(f"Měřítko náhledu: {live_preview.zoom_percent()} %")

        zoom_out.clicked.connect(lambda: (live_preview.set_zoom_percent(live_preview.zoom_percent() - 10), update_zoom_label()))
        zoom_in.clicked.connect(lambda: (live_preview.set_zoom_percent(live_preview.zoom_percent() + 10), update_zoom_label()))
        zoom_fit.clicked.connect(lambda: (live_preview.set_zoom_percent(None), update_zoom_label()))
        close_button.clicked.connect(dialog.reject)

        def ensure_document():
            preview_timer.stop()
            update_preview()
            return state.get("document"), state.get("options")

        def do_print():
            document, options = ensure_document()
            if document is None:
                return
            printer = QPrinter(QPrinter.HighResolution)
            self._apply_sports_print_page_setup(printer, options["paper_name"], options["orientation"])
            print_dialog = QPrintDialog(printer, dialog)
            print_dialog.setWindowTitle("Tisk sportovního dne")
            if print_dialog.exec() != QDialog.Accepted:
                return
            self._paint_sports_print_document(printer, document, options["appearance"] == "pirate")

        def save_pdf():
            document, options = ensure_document()
            if document is None:
                return
            path, _ = QFileDialog.getSaveFileName(dialog, "Uložit výsledky do PDF", "sportovni-den-vysledky.pdf", "PDF (*.pdf)")
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)
            self._apply_sports_print_page_setup(printer, options["paper_name"], options["orientation"])
            self._paint_sports_print_document(printer, document, options["appearance"] == "pirate")
            QMessageBox.information(dialog, "PDF uloženo", f"Výsledky byly uloženy do:\n{path}")

        print_button.clicked.connect(do_print)
        pdf_button.clicked.connect(save_pdf)
        live_preview.set_message("Připravuji pirátský tisk…")
        QTimer.singleShot(0, update_preview)
        dialog.exec()

    def _show_print_options_legacy(self):
        dialog = QDialog(self)
        dialog.setObjectName("printOptionsDialog")
        dialog.setWindowTitle("Tisk výsledků sportovního dne")
        dialog.resize(720, 610)
        dialog.setMinimumSize(650, 560)
        print_background = os.path.join(self.icons_path, "sports_day_BG.png").replace("\\", "/")
        print_style = """
            QDialog#printOptionsDialog {
                background-color: #071923;
                border-image: url("__PRINT_BACKGROUND__") 0 0 0 0 stretch stretch;
            }
            QLabel#printStats {
                color: #fff0bd;
                background-color: rgba(7, 48, 59, 205);
                border: 1px solid rgba(226, 177, 82, 210);
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }
        """.replace("__PRINT_BACKGROUND__", print_background)
        dialog.setStyleSheet(
            self._style_sheet()
            + print_style
        )
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        hero = QFrame(dialog)
        hero.setObjectName("sportsPanel")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(14, 12, 14, 12)
        print_coin = QLabel(hero)
        print_coin.setFixedSize(66, 66)
        print_coin.setAlignment(Qt.AlignCenter)
        if not self.coin_pixmap.isNull():
            print_coin.setPixmap(self.coin_pixmap.scaled(62, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        hero_layout.addWidget(print_coin)
        hero_text = QVBoxLayout()
        title = QLabel("TISK PIRÁTSKÝCH VÝSLEDKŮ", hero)
        title.setStyleSheet("color: #f4dea4; font-size: 22px; font-weight: bold; letter-spacing: 1px;")
        hero_text.addWidget(title)
        intro = QLabel(
            "Vyber část posádky, obsah a pořadí. Náhled bude moderně pirátský, ale papír zůstane čistě bílý.",
            hero,
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #d6c495; font-size: 12px;")
        hero_text.addWidget(intro)
        hero_layout.addLayout(hero_text, 1)
        outer.addWidget(hero)

        result_count = sum(
            1
            for event_results in self.results.values()
            if isinstance(event_results, dict)
            for value in event_results.values()
            if str(value or "").strip()
        )
        stats = QLabel(
            f"POSÁDKA  {len(self.competitors)}   •   VÝZVY  {len(self.events)}   •   VYPLNĚNÉ VÝSLEDKY  {result_count}",
            dialog,
        )
        stats.setObjectName("printStats")
        stats.setAlignment(Qt.AlignCenter)
        stats.setFixedHeight(44)
        outer.addWidget(stats)

        panel = QFrame(dialog)
        panel.setObjectName("sportsPanel")
        form = QGridLayout(panel)
        form.setContentsMargins(14, 13, 14, 14)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(9)

        scope_combo = QComboBox(panel)
        scope_combo.addItem("Všichni podle věkových kategorií", "all_categories")
        scope_combo.addItem("Jedna věková kategorie", "category")
        scope_combo.addItem("Jen dívky", "girls")
        scope_combo.addItem("Jen kluci", "boys")
        scope_combo.addItem("Všichni v jednom pořadí", "all")
        category_combo = QComboBox(panel)
        for category in self.categories:
            category_combo.addItem(str(category.get("name") or ""), category.get("id"))
        category_combo.setEnabled(False)
        scope_combo.currentIndexChanged.connect(
            lambda: category_combo.setEnabled(scope_combo.currentData() == "category")
        )

        event_combo = QComboBox(panel)
        event_combo.addItem("Všechny výzvy", "all")
        for event in self.events:
            event_combo.addItem(str(event.get("name") or ""), event.get("id"))
        event_combo.setEnabled(bool(self.events))

        order_combo = QComboBox(panel)
        order_combo.addItem("Podle výsledků a mincí", "results")
        order_combo.addItem("Abecedně", "alphabetical")

        appearance_combo = QComboBox(panel)
        appearance_combo.addItem("Pirátské pozadí • moderní", "pirate")
        appearance_combo.addItem("Jednoduchý bílý tisk • úsporný", "simple")

        form.addWidget(QLabel("KOHO VYTISKNOUT", panel), 0, 0)
        form.addWidget(scope_combo, 0, 1)
        form.addWidget(QLabel("VĚKOVÁ KATEGORIE", panel), 1, 0)
        form.addWidget(category_combo, 1, 1)
        form.addWidget(QLabel("KTERÉ VÝZVY", panel), 2, 0)
        form.addWidget(event_combo, 2, 1)
        form.addWidget(QLabel("POŘADÍ NA PAPÍŘE", panel), 3, 0)
        form.addWidget(order_combo, 3, 1)
        form.addWidget(QLabel("VZHLED TISKU", panel), 4, 0)
        form.addWidget(appearance_combo, 4, 1)
        form.setColumnStretch(1, 1)

        print_events = QCheckBox("Výsledky jednotlivých výzev", panel)
        print_events.setChecked(bool(self.events))
        print_events.setEnabled(bool(self.events))
        print_treasure = QCheckBox("Celkový poklad a získané mince", panel)
        print_treasure.setChecked(True)
        form.addWidget(print_events, 5, 0, 1, 2)
        form.addWidget(print_treasure, 6, 0, 1, 2)
        outer.addWidget(panel)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("ZRUŠIT", dialog)
        cancel.setObjectName("quietButton")
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        preview = QPushButton("OTEVŘÍT NÁHLED TISKU", dialog)
        preview.setObjectName("printButton")
        if not self.coin_pixmap.isNull():
            preview.setIcon(QIcon(self.coin_pixmap))
            preview.setIconSize(QSize(25, 25))
        preview.clicked.connect(dialog.accept)
        buttons.addWidget(preview)
        outer.addLayout(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        if not print_events.isChecked() and not print_treasure.isChecked():
            QMessageBox.information(self, "Nic není vybráno", "Vyber alespoň výsledky výzev nebo celkový poklad.")
            return

        options = {
            "scope": scope_combo.currentData(),
            "category_id": category_combo.currentData(),
            "event_id": event_combo.currentData(),
            "order": order_combo.currentData(),
            "appearance": appearance_combo.currentData(),
            "print_events": print_events.isChecked(),
            "print_treasure": print_treasure.isChecked(),
        }
        competitors = self._print_competitors(options)
        if not competitors:
            QMessageBox.information(self, "Prázdný výběr", "Pro tuto volbu není v posádce žádný pirát.")
            return
        self._open_sports_print_preview(
            self._build_sports_print_document(options, competitors),
            options.get("appearance") == "pirate",
        )

    def _print_competitors(self, options: dict):
        scope = options.get("scope")
        category_id = options.get("category_id")
        competitors = list(self.competitors)
        if scope == "category":
            competitors = [item for item in competitors if item.get("category_id") == category_id]
        elif scope == "girls":
            competitors = [item for item in competitors if item.get("gender", "M") == "F"]
        elif scope == "boys":
            competitors = [item for item in competitors if item.get("gender", "M") == "M"]
        return sorted(competitors, key=lambda item: str(item.get("name") or "").casefold())

    def _print_groups(self, options: dict, competitors: list):
        scope = options.get("scope")
        if scope == "all":
            return [("CELÁ POSÁDKA", competitors)]

        allowed_ids = {item.get("id") for item in competitors}
        groups = []
        for category in self.categories:
            category_rows = [
                item for item in competitors
                if item.get("id") in allowed_ids and item.get("category_id") == category.get("id")
            ]
            if not category_rows:
                continue
            if scope in ("girls", "boys"):
                groups.append((str(category.get("name") or ""), category_rows))
                continue
            for gender in ("M", "F"):
                rows = [item for item in category_rows if item.get("gender", "M") == gender]
                if rows:
                    groups.append((f"{category.get('name')}  •  {self.GENDERS[gender]['plural']}", rows))
        return groups

    def _print_scope_label(self, options: dict):
        labels = {
            "all_categories": "Všichni podle věkových kategorií",
            "category": f"Věková kategorie: {self._category_name(options.get('category_id'))}",
            "girls": "Dívky podle věkových kategorií",
            "boys": "Kluci podle věkových kategorií",
            "all": "Celá posádka",
        }
        return labels.get(options.get("scope"), "Celá posádka")

    def _sports_print_background_image(
        self,
        paper_name: str = "A4",
        orientation_name: str = "Na výšku",
        economical_print: bool = False,
    ):
        """Načte podklad vytvořený přesně pro zvolený papír a orientaci."""
        paper_key = str(paper_name or "A4").lower()
        orientation_key = "landscape" if orientation_name == "Na šířku" else "portrait"
        background_path = os.path.join(
            self.icons_path,
            "print_backgrounds",
            f"sports_print_{paper_key}_{orientation_key}{'_eco' if economical_print else ''}.jpg",
        )
        cache_key = (paper_key, orientation_key, bool(economical_print))
        cache = getattr(self, "_sports_print_background_cache", None)
        if cache is None:
            cache = {}
            self._sports_print_background_cache = cache
        if cache_key in cache:
            return QImage(cache[cache_key])
        if os.path.exists(background_path):
            exact_background = QImage(background_path)
            if not exact_background.isNull():
                cache[cache_key] = exact_background
                return QImage(exact_background)

        # Bezpečná záloha pro neúplnou instalaci staršího balíčku.
        canvas = QImage(595, 842, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(QColor("#fffdf8") if economical_print else QColor("#061923"))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if not economical_print and not self.background.isNull():
            # Tmavá aréna pokryje celý list. Samostatný spodní výřez zachová
            # pohár, vlajku, lucernu i loď, které by se při ořezu na A4 ztratily.
            scaled = self.background.scaled(canvas.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            source_x = max(0, (scaled.width() - canvas.width()) // 2)
            source_y = max(0, (scaled.height() - canvas.height()) // 2)
            painter.setOpacity(0.88)
            painter.drawPixmap(
                canvas.rect(),
                scaled,
                QRect(source_x, source_y, canvas.width(), canvas.height()),
            )
            full_scene = self.background.scaledToWidth(canvas.width(), Qt.SmoothTransformation)
            painter.setOpacity(0.72)
            painter.drawPixmap(0, canvas.height() - full_scene.height(), full_scene)

            source_top = QRect(0, 0, self.background.width(), max(1, int(self.background.height() * 0.13)))
            painter.setOpacity(0.92)
            painter.drawPixmap(QRect(0, 0, canvas.width(), 72), self.background, source_top)
            painter.setOpacity(1.0)
        painter.setPen(QPen(QColor(138, 99, 44, 215) if economical_print else QColor(212, 160, 71, 235), 5))
        painter.drawRect(canvas.rect().adjusted(6, 6, -7, -7))
        painter.setPen(QPen(QColor(177, 139, 78, 155) if economical_print else QColor(250, 220, 145, 165), 1))
        painter.drawRect(canvas.rect().adjusted(12, 12, -13, -13))
        painter.end()
        cache[cache_key] = canvas
        return canvas

    def _build_sports_print_document(self, options: dict, competitors: list):
        esc = lambda value: html.escape(str(value or ""))
        groups = self._print_groups(options, competitors)
        order_results = options.get("order") == "results"
        totals, per_event = self._standings_data()
        selected_event_id = options.get("event_id")
        selected_events = [
            event for event in self.events
            if selected_event_id == "all" or event.get("id") == selected_event_id
        ]
        selected_competitor_ids = {item.get("id") for item in competitors}
        filled_results = sum(
            1
            for event in selected_events
            for competitor_id, value in (self.results.get(event.get("id"), {}) or {}).items()
            if competitor_id in selected_competitor_ids and str(value or "").strip()
        )
        selected_treasure = sum(totals.get(item.get("id"), 0) for item in competitors)
        use_background = options.get("appearance", "pirate") == "pirate"
        economical_print = bool(options.get("economical_print"))
        show_logo = bool(options.get("show_logo", True))
        light_text = economical_print or not use_background
        # Pirátské pozadí kreslíme při tisku přímo pod každou stránku. Dokument
        # proto musí být průhledný; jinak by jeho bílá plocha motiv zakryla.
        paper_background = "background-color:transparent;" if use_background else "background-color:#ffffff;"
        secondary_text = "#74511d" if light_text else "#f4dea4"
        footer_text = "#6b4a21" if light_text else "#ead39b"
        # QTextDocument na Windows poloprůhledné CSS barvy buněk při tisku
        # skládá do téměř neprůhledné plochy. Skutečně průhledný výsledek proto
        # vyžaduje úplně odstranit výplň buněk a ponechat jen linky a text.
        if economical_print:
            panel_background = "transparent"
            alternate_background = "transparent"
            section_background = "transparent"
            mast_background = "transparent"
            table_header_background = "rgba(230,201,147,205)"
            table_header_text = "#3d200d"
        elif use_background:
            panel_background = "transparent"
            alternate_background = "transparent"
            section_background = "transparent"
            mast_background = "transparent"
            table_header_background = "transparent"
            table_header_text = "#f4dea4"
        else:
            panel_background = "#f7f3e9"
            alternate_background = "rgba(240,246,243,235)"
            section_background = "#edf3f1"
            mast_background = "#082d38"
            table_header_background = "#0b4652"
            table_header_text = "#fff4cf"
        panel_text = "#3d2a1a" if light_text else "#f6e8c0"
        panel_muted = "#7b6a54" if light_text else "#d8c392"
        section_text = "#3d200d" if light_text else "#f4dea4"
        group_text = "#76521d" if light_text else "#e5bd70"
        summary_value = "#4f3216" if light_text else "#f4dea4"
        summary_label = "#7b6235" if light_text else "#d8c392"
        main_title = "#3d200d" if light_text else "#fff0bd"
        mast_subtitle = "#74511d" if light_text else "#e4c47c"
        base_font_size = max(8, min(16, int(options.get("font_size", 10))))
        section_heading_size = max(12, min(30, int(options.get("heading_size", 15))))
        main_heading_size = max(18, min(34, section_heading_size + 7))
        font_family = _sports_print_font_family(
            options.get("font_family", "default"),
            getattr(self, "icons_path", ""),
        )
        font_style = _sports_print_font_style(options.get("font_style", "regular"))
        body_font_css = font_family["body_css"]
        heading_font_css = font_family["heading_css"]
        body_weight = font_style["body_weight"]
        heading_weight = font_style["heading_weight"]
        css_font_style = font_style["css_style"]
        frame_border = "1px solid #d4c49f" if options.get("show_frames", True) else "0"
        header_border = "1px solid #9d7a41" if options.get("show_frames", True) else "0"
        coin = "<img src='pirate_coin' width='18' height='18' style='vertical-align:middle;'>"
        pieces = [
            "<html><head><meta charset='utf-8'><style>",
            f"body{{font-family:{body_font_css};color:#102631;{paper_background}font-size:{base_font_size}pt;font-weight:{body_weight};font-style:{css_font_style};}}",
            f".mast{{border:0;border-bottom:2px solid #b48636;background:{mast_background};padding:13px 15px;margin-bottom:8px;}}",
            f"h1{{font-family:{heading_font_css};color:{main_title};font-size:{main_heading_size}pt;font-weight:{heading_weight};font-style:{css_font_style};letter-spacing:1.5px;margin:0 0 4px 0;}}",
            f".mast .sub{{color:{mast_subtitle};font-size:10pt;font-style:normal;}}",
            f".summary{{border:1px solid #b99a61;background:{panel_background};margin:0 0 15px 0;}}",
            f".summary td{{border:0;border-right:1px solid rgba(211,169,91,150);background:{panel_background};text-align:center;padding:8px 5px;}}",
            f".summary strong{{color:{summary_value};font-family:{heading_font_css};font-size:14pt;font-weight:{heading_weight};font-style:{css_font_style};}}",
            f".summary span{{color:{summary_label};font-size:7.5pt;letter-spacing:0.7px;}}",
            f".sub{{color:{secondary_text};font-size:9pt;font-style:italic;margin-bottom:7px;}}",
            ".section{margin:13px 0 17px 0;}",
            f"h2{{font-family:{heading_font_css};color:{section_text};background:{section_background};font-size:{section_heading_size}pt;font-weight:{heading_weight};font-style:{css_font_style};border-left:0;border-bottom:2px solid #b08032;padding:5px 0;margin:0 0 8px 0;}}",
            f"h3{{font-family:{heading_font_css};color:{group_text};font-size:11pt;font-weight:{heading_weight};font-style:{css_font_style};border-bottom:1px solid rgba(215,195,151,155);padding-bottom:3px;margin:11px 0 5px 0;}}",
            "table{width:100%;border-collapse:collapse;margin:0 0 9px 0;}",
            f"th{{background:{table_header_background};color:{table_header_text};border:{header_border};padding:7px;text-align:left;font-size:{max(7, base_font_size - 1)}pt;letter-spacing:0.3px;}}",
            f"td{{color:{panel_text};border:{frame_border};padding:7px;background:{panel_background};}}",
            f"tr.alt td{{background:{alternate_background};}}",
            f".num{{text-align:center;white-space:nowrap;font-weight:bold;color:{panel_text};}}.empty{{color:{panel_muted};font-style:italic;font-weight:normal;}}",
            f".footer{{border-top:2px solid #bda36e;color:{footer_text};font-size:8pt;margin-top:18px;padding-top:7px;text-align:center;letter-spacing:0.4px;}}",
            "</style></head><body>",
        ]

        if options.get("show_title", True):
            logo_cell = (
                f"<td style='border:0;width:58px;background:transparent'>{coin.replace('18', '48')}</td>"
                if show_logo
                else ""
            )
            pieces.extend([
                "<div class='mast'><table style='border:0;margin:0'><tr>",
                logo_cell,
                "<td style='border:0;background:transparent'>",
                f"<h1>{esc(options.get('title') or 'PIRÁTSKÝ SPORTOVNÍ DEN')}</h1>",
                f"<div class='sub'>{esc(self._print_scope_label(options))} &nbsp;•&nbsp; "
                f"{datetime.now().strftime('%d. %m. %Y')}</div></td></tr></table></div>",
            ])
        if options.get("show_summary", True):
            pieces.extend([
                "<table class='summary'><tr>",
                f"<td><strong>{len(competitors)}</strong><br><span>PIRÁTŮ</span></td>",
                f"<td><strong>{len(selected_events)}</strong><br><span>VÝZEV</span></td>",
                f"<td><strong>{filled_results}</strong><br><span>VÝSLEDKŮ</span></td>",
                f"<td><strong>{self._format_points_value(selected_treasure)}</strong><br><span>MINCÍ CELKEM</span></td>",
                "</tr></table>",
            ])

        if options.get("print_events"):
            for event in selected_events:
                metric = self.METRICS.get(event.get("metric"), self.METRICS["time"])
                event_results = self.results.get(event.get("id"), {}) or {}
                points = self._event_points(event)
                pieces.append(f"<div class='section'><h2>{esc(event.get('name'))}</h2>")
                pieces.append(
                    f"<div class='sub'>{esc(metric['label'])} • vítězí "
                    f"{'nejnižší' if event.get('direction') == 'asc' else 'nejvyšší'} hodnota</div>"
                )
                for group_label, group_rows in groups:
                    if order_results:
                        valid, missing = self._sorted_for_event(event, group_rows, event_results)
                        ordered = valid + sorted(missing, key=lambda item: str(item.get("name") or "").casefold())
                    else:
                        ordered = sorted(group_rows, key=lambda item: str(item.get("name") or "").casefold())
                        valid = []
                    pieces.append(f"<h3>{esc(group_label)}</h3><table><tr><th>Pořadí</th><th>Pirát</th><th>Výsledek</th><th>Jednotka</th><th>Mince</th></tr>")
                    parsed_values = [
                        self._parse_metric_value(
                            event_results.get(competitor.get("id"), ""),
                            event.get("metric", "time"),
                        )
                        for competitor in ordered
                    ]
                    ranks = self._competition_ranks(parsed_values) if order_results else [None] * len(ordered)
                    for index, (competitor, rank) in enumerate(zip(ordered, ranks)):
                        competitor_id = competitor.get("id")
                        raw = str(event_results.get(competitor_id, "")).strip()
                        rank_text = str(rank) if rank is not None else "–"
                        class_name = " class='alt'" if index % 2 else ""
                        result_html = esc(raw) if raw else "<span class='empty'>nezadáno</span>"
                        pieces.append(
                            f"<tr{class_name}><td class='num'>{rank_text}</td><td>{esc(competitor.get('name'))}</td>"
                            f"<td class='num'>{result_html}</td>"
                            f"<td>{esc(metric['unit'])}</td><td class='num'>{coin} "
                            f"{self._format_points_value(points.get(competitor_id, 0))}</td></tr>"
                        )
                    pieces.append("</table>")
                pieces.append("</div>")

        if options.get("print_treasure"):
            pieces.append("<div class='section'><h2>CELKOVÝ POKLAD</h2>")
            for group_label, group_rows in groups:
                if order_results:
                    ordered = sorted(
                        group_rows,
                        key=lambda item: (-totals.get(item.get("id"), 0), str(item.get("name") or "").casefold()),
                    )
                else:
                    ordered = sorted(group_rows, key=lambda item: str(item.get("name") or "").casefold())
                pieces.append(f"<h3>{esc(group_label)}</h3><table><tr><th>Pořadí</th><th>Pirát</th><th>Kategorie</th><th>Skupina</th><th>Poklad</th><th>Přehled výzev</th></tr>")
                ranks = (
                    self._competition_ranks([
                        totals.get(item.get("id"), 0)
                        if per_event.get(item.get("id"), {})
                        else None
                        for item in ordered
                    ])
                    if order_results
                    else [None] * len(ordered)
                )
                for index, (competitor, rank) in enumerate(zip(ordered, ranks)):
                    competitor_id = competitor.get("id")
                    breakdown = []
                    for event in self.events:
                        value = per_event.get(competitor_id, {}).get(event.get("id"))
                        if value:
                            breakdown.append(f"{event.get('name')}: {self._format_points_value(value)}")
                    rank_text = str(rank) if rank is not None else "–"
                    class_name = " class='alt'" if index % 2 else ""
                    pieces.append(
                        f"<tr{class_name}><td class='num'>{rank_text}</td><td>{esc(competitor.get('name'))}</td>"
                        f"<td>{esc(self._category_name(competitor.get('category_id', 'none')))}</td>"
                        f"<td>{esc(self.GENDERS[competitor.get('gender', 'M')]['singular'])}</td>"
                        f"<td class='num'>{coin} {self._format_points_value(totals.get(competitor_id, 0))}</td>"
                        f"<td>{esc(' • '.join(breakdown) if breakdown else 'Bez výsledků')}</td></tr>"
                    )
                pieces.append("</table>")
            pieces.append("</div>")

        pieces.append(
            "<div class='footer'>Táborová paluba Mraveniště • výsledková listina sportovního dne</div></body></html>"
        )
        document = QTextDocument(self)
        document.setDefaultFont(
            _sports_print_qfont(
                options.get("font_family", "default"),
                base_font_size,
                options.get("font_style", "regular"),
                getattr(self, "icons_path", ""),
            )
        )
        paper_name = options.get("paper_name", "A4")
        orientation_name = options.get("orientation", "Na výšku")
        document.setPageSize(_sports_print_page_size(paper_name, orientation_name))
        document.setProperty("sports_paper_name", paper_name)
        document.setProperty("sports_orientation", orientation_name)
        document.setProperty("sports_economical_print", economical_print)
        document.setProperty("sports_show_logo", show_logo)
        margin_mm = max(6, min(25, int(options.get("margin_mm", 11))))
        document.setDocumentMargin(margin_mm * 72.0 / 25.4)
        if not self.coin_pixmap.isNull():
            document.addResource(QTextDocument.ImageResource, QUrl("pirate_coin"), self.coin_pixmap.toImage())
        document.setHtml("".join(pieces))
        return document

    def _render_sports_print_page(self, document: QTextDocument, page_index: int, use_background: bool):
        """Vykreslí jednu stránku stejně jako živý náhled a skutečná tiskárna."""
        page_size = document.pageSize()
        page_width = max(1, int(round(page_size.width())))
        page_height = max(1, int(round(page_size.height())))
        page = QImage(page_width, page_height, QImage.Format_ARGB32_Premultiplied)
        page.fill(QColor("#fffdf8") if use_background else QColor("#ffffff"))

        painter = QPainter(page)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if use_background:
            paper_name = document.property("sports_paper_name") or "A4"
            orientation_name = document.property("sports_orientation") or "Na výšku"
            economical_print = bool(document.property("sports_economical_print"))
            painter.drawImage(
                page.rect(),
                self._sports_print_background_image(paper_name, orientation_name, economical_print),
            )
        painter.setClipRect(QRectF(0, 0, page_width, page_height))
        painter.translate(0, -page_index * page_size.height())
        document.drawContents(
            painter,
            QRectF(0, page_index * page_size.height(), page_size.width(), page_size.height()),
        )
        painter.end()
        return page

    def _apply_sports_print_page_setup(self, printer, paper_name: str, orientation_name: str):
        page_sizes = {
            "A5": QPageSize.A5,
            "A4": QPageSize.A4,
            "A3": QPageSize.A3,
            "Letter": QPageSize.Letter,
            "Legal": QPageSize.Legal,
        }
        printer.setPageSize(QPageSize(page_sizes.get(paper_name or "A4", QPageSize.A4)))
        printer.setPageOrientation(
            QPageLayout.Landscape if orientation_name == "Na šířku" else QPageLayout.Portrait
        )
        # Pozadí patří na celý list. Bez fullPage QPrinter vrátí pouze vnitřní
        # tisknutelný obdélník a v náhledu vznikne chybný široký bílý rám.
        try:
            printer.setFullPage(True)
            printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
        except Exception:
            pass

    def _paint_sports_print_document(self, printer, document: QTextDocument, use_background: bool):
        """Tiskne stránku po stránce, aby se zvolené pozadí spolehlivě objevilo i na papíře."""
        try:
            from PySide6.QtPrintSupport import QPrinter

            page_size = document.pageSize()
            page_count = max(1, int(document.documentLayout().pageCount()))
            painter = QPainter(printer)
            if not painter.isActive():
                return

            for page_index in range(page_count):
                if page_index and not printer.newPage():
                    break
                try:
                    target = QRectF(printer.paperRect(QPrinter.DevicePixel))
                except Exception:
                    target = QRectF(printer.pageRect(QPrinter.DevicePixel))
                painter.save()
                painter.setClipRect(target)
                painter.fillRect(target, QColor("#fffdf8") if use_background else QColor("#ffffff"))
                if use_background:
                    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                    paper_name = document.property("sports_paper_name") or "A4"
                    orientation_name = document.property("sports_orientation") or "Na výšku"
                    economical_print = bool(document.property("sports_economical_print"))
                    painter.drawImage(
                        target,
                        self._sports_print_background_image(paper_name, orientation_name, economical_print),
                    )
                painter.translate(target.left(), target.top())
                painter.scale(target.width() / page_size.width(), target.height() / page_size.height())
                painter.translate(0, -page_index * page_size.height())
                document.drawContents(
                    painter,
                    QRectF(0, page_index * page_size.height(), page_size.width(), page_size.height()),
                )
                painter.restore()
            painter.end()
        except Exception as error:
            QMessageBox.warning(self, "Tisk se nezdařil", f"Dokument se nepodařilo vykreslit:\n{error}")

    def _open_sports_print_preview(self, document: QTextDocument, use_background: bool = False):
        try:
            from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        except Exception as error:
            QMessageBox.warning(self, "Tisk není dostupný", f"Nepodařilo se načíst podporu tisku:\n{error}")
            return
        printer = QPrinter(QPrinter.HighResolution)
        self._apply_sports_print_page_setup(printer, "A4", "Na výšku")
        preview = QPrintPreviewDialog(printer, self)
        economical_print = bool(document.property("sports_economical_print"))
        if use_background and economical_print:
            appearance = "šetrný pirátský tisk"
        else:
            appearance = "pirátské pozadí" if use_background else "jednoduchý tisk"
        preview.setWindowTitle(f"Náhled tisku • Pirátský sportovní den • {appearance}")
        preview.resize(1120, 820)
        preview.setStyleSheet(
            """
                QPrintPreviewDialog { background-color: #061923; }
                QToolBar {
                    background-color: #082d38;
                    border: none;
                    border-bottom: 2px solid #a87b35;
                    spacing: 5px;
                    padding: 5px;
                }
                QToolButton {
                    color: #f4dea4;
                    background-color: rgba(13, 64, 75, 220);
                    border: 1px solid #9d7a41;
                    border-radius: 7px;
                    padding: 6px;
                }
                QToolButton:hover { background-color: #176c76; border-color: #efc66c; }
                QComboBox {
                    color: #f4dea4;
                    background-color: #0a3540;
                    border: 1px solid #9d7a41;
                    border-radius: 7px;
                    padding: 5px 8px;
                }
                QAbstractScrollArea { background-color: #263943; border: none; }
            """
        )
        preview.paintRequested.connect(
            lambda target_printer: self._paint_sports_print_document(target_printer, document, use_background)
        )
        preview.exec()
