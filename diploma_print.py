"""Vykreslování, PDF a tisk pirátských diplomů a úklidové listiny."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPageLayout,
    QPageSize,
    QPainter,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSizePolicy, QWidget


A4_PREVIEW_SIZE = QSize(1400, 990)
A5_REFERENCE_HEIGHT = 595.0


@lru_cache(maxsize=16)
def _cached_pixmap(path: str) -> QPixmap:
    return QPixmap(path)


def _draw_background(painter: QPainter, rect: QRectF, path: str, economical=False):
    rect = QRectF(rect)
    image = _cached_pixmap(path)
    if image.isNull():
        painter.fillRect(rect, QColor("#071923"))
        return
    painter.drawPixmap(rect, image, QRectF(image.rect()))
    # Nové podklady nepotřebují samostatný druhý soubor. Šetrná varianta
    # ponechá obrys motivu, ale velkou část plochy zesvětlí pro úsporu inkoustu.
    if economical and "_eco" not in str(path).casefold():
        painter.fillRect(rect, QColor(255, 253, 247, 205))


def _fitted_font(text: str, rect: QRectF, maximum: int, minimum: int = 8, bold=True) -> QFont:
    font = QFont("Georgia")
    font.setBold(bold)
    for size in range(maximum, minimum - 1, -1):
        font.setPixelSize(size)
        metrics = QFontMetrics(font)
        if metrics.horizontalAdvance(text or " ") <= rect.width() and metrics.height() <= rect.height():
            return font
    font.setPixelSize(minimum)
    return font


def _draw_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    color: QColor,
    maximum: int,
    minimum: int = 8,
    bold=True,
    flags=Qt.AlignCenter,
):
    painter.setPen(color)
    painter.setFont(_fitted_font(text, rect, maximum, minimum, bold))
    painter.drawText(rect, flags, text or "")


def _draw_logo(painter: QPainter, page: QRectF, logo_path: str, compact=False):
    logo = _cached_pixmap(logo_path)
    if logo.isNull():
        return
    height = page.height() * (0.090 if compact else 0.145)
    width = height * logo.width() / max(1, logo.height())
    if compact:
        target = QRectF(
            page.left() + page.width() * 0.035,
            page.top() + page.height() * 0.035,
            width,
            height,
        )
    else:
        target = QRectF(page.center().x() - width / 2, page.top() + page.height() * 0.045, width, height)
    painter.drawPixmap(target, logo, QRectF(logo.rect()))


def _text_box_rect(page: QRectF, box: dict) -> QRectF:
    """Převede relativní souřadnice textového pole na souřadnice diplomu A5."""
    return QRectF(
        page.left() + page.width() * float(box.get("x", 0.1)),
        page.top() + page.height() * float(box.get("y", 0.1)),
        page.width() * float(box.get("width", 0.8)),
        page.height() * float(box.get("height", 0.08)),
    )


def _text_box_flags(box: dict):
    alignments = {
        "left": Qt.AlignLeft,
        "right": Qt.AlignRight,
        "center": Qt.AlignHCenter,
    }
    vertical_alignments = {
        "top": Qt.AlignTop,
        "middle": Qt.AlignVCenter,
        "bottom": Qt.AlignBottom,
    }
    return (
        alignments.get(str(box.get("align", "center")), Qt.AlignHCenter)
        | vertical_alignments.get(str(box.get("vertical_align", "middle")), Qt.AlignVCenter)
        | Qt.TextWordWrap
    )


def _display_text(box: dict):
    text = str(box.get("text", ""))
    transform = str(box.get("case_transform", "none"))
    if transform == "upper":
        return text.upper()
    if transform == "lower":
        return text.lower()
    if transform == "title":
        return text.title()
    return text


def _text_box_color(box: dict, primary: QColor, secondary: QColor):
    automatic = primary if box.get("tone", "primary") == "primary" else secondary
    requested = str(box.get("color", "auto"))
    color = QColor(requested) if requested and requested != "auto" else QColor(automatic)
    if not color.isValid():
        color = QColor(automatic)
    color.setAlphaF(max(0.05, min(1.0, float(box.get("opacity", 100)) / 100.0)))
    return color


def _paint_text_box(painter: QPainter, page: QRectF, box: dict, primary: QColor, secondary: QColor):
    """Vykreslí uživatelsky upravitelné průhledné textové pole."""
    text = _display_text(box)
    if not text and not box.get("blank_line", False):
        return
    rect = _text_box_rect(page, box)
    font = QFont(str(box.get("font_family", "Georgia")) or "Georgia")
    font.setPixelSize(max(2, round(float(box.get("font_size", 18.0)) * page.height() / A5_REFERENCE_HEIGHT)))
    font.setBold(bool(box.get("bold", False)))
    font.setItalic(bool(box.get("italic", False)))
    font.setUnderline(bool(box.get("underline", False)))
    font.setStrikeOut(bool(box.get("strikeout", False)))
    font.setLetterSpacing(QFont.PercentageSpacing, max(50.0, min(300.0, float(box.get("letter_spacing", 100)))))
    font.setStretch(max(50, min(200, int(box.get("font_stretch", 100)))))

    text_color = _text_box_color(box, primary, secondary)

    painter.save()
    painter.setPen(text_color)
    painter.setFont(font)
    center = rect.center()
    painter.translate(center)
    painter.rotate(float(box.get("rotation", 0.0)))
    local_rect = QRectF(-rect.width() / 2.0, -rect.height() / 2.0, rect.width(), rect.height())
    if text:
        if box.get("shadow", False):
            shadow_color = QColor("#000000")
            shadow_color.setAlphaF(min(0.75, text_color.alphaF() * 0.65))
            shadow_offset = max(1.0, 1.7 * page.height() / A5_REFERENCE_HEIGHT)
            painter.setPen(shadow_color)
            painter.drawText(local_rect.translated(shadow_offset, shadow_offset), _text_box_flags(box), text)
            painter.setPen(text_color)
        painter.drawText(local_rect, _text_box_flags(box), text)
    if box.get("blank_line", False):
        line_y = local_rect.bottom() - max(2.0, local_rect.height() * 0.16)
        painter.setPen(QPen(text_color, max(1.0, page.width() * 0.0012)))
        painter.drawLine(local_rect.left(), line_y, local_rect.right(), line_y)
    painter.restore()


def _paint_editable_text_boxes(
    painter: QPainter,
    page: QRectF,
    boxes: list,
    primary: QColor,
    secondary: QColor,
):
    for box in boxes:
        if isinstance(box, dict):
            _paint_text_box(painter, page, box, primary, secondary)


def paint_diploma_page(
    painter: QPainter,
    page: QRectF,
    values: dict,
    background_path: str,
    logo_path: str,
):
    """Vykreslí jeden diplom A5 na libovolný cílový obdélník."""
    painter.save()
    painter.setClipRect(page)
    _draw_background(painter, page, background_path, values.get("economical_print", False))

    variant = str(values.get("variant", ""))
    light_background = bool(values.get("light_background")) or bool(values.get("economical_print")) or variant.endswith("_ECO")
    primary = QColor("#3d200d") if light_background else QColor("#f3d08a")
    secondary = primary
    line_color = QColor(91, 48, 17, 190) if light_background else QColor(211, 166, 82, 210)

    if values.get("show_logo", True):
        _draw_logo(
            painter,
            page,
            logo_path,
            compact=str(values.get("layout", "two_a5_portrait")) != "two_a5_portrait",
        )

    text_boxes = values.get("text_boxes")
    if isinstance(text_boxes, list):
        _paint_editable_text_boxes(painter, page, text_boxes, primary, secondary)
        painter.restore()
        return

    # Jemný podklad zajišťuje čitelnost a přitom nechává vlastní BG prosvítat.
    if not light_background:
        panel = QRectF(
            page.left() + page.width() * 0.12,
            page.top() + page.height() * 0.19,
            page.width() * 0.76,
            page.height() * 0.60,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(2, 15, 24, 72))
        painter.drawRoundedRect(panel, page.width() * 0.025, page.width() * 0.025)

    w, h = page.width(), page.height()
    x = page.left()
    y = page.top()

    _draw_text(
        painter,
        QRectF(x + w * 0.10, y + h * 0.205, w * 0.80, h * 0.065),
        values.get("title", ""),
        primary,
        max(14, int(h * 0.040)),
        max(9, int(h * 0.020)),
    )
    _draw_text(
        painter,
        QRectF(x + w * 0.16, y + h * 0.280, w * 0.68, h * 0.036),
        values.get("lead", ""),
        secondary,
        max(11, int(h * 0.022)),
        max(8, int(h * 0.014)),
        bold=False,
    )

    name_rect = QRectF(x + w * 0.09, y + h * 0.330, w * 0.82, h * 0.085)
    _draw_text(
        painter,
        name_rect,
        values.get("name", ""),
        primary,
        max(18, int(h * 0.055)),
        max(11, int(h * 0.025)),
    )
    painter.setPen(QPen(line_color, max(1.0, w * 0.002)))
    painter.drawLine(
        x + w * 0.20,
        y + h * 0.425,
        x + w * 0.80,
        y + h * 0.425,
    )

    award_font = QFont("Georgia")
    award_font.setItalic(True)
    award_font.setPixelSize(max(10, int(h * 0.021)))
    painter.setFont(award_font)
    painter.setPen(secondary)
    painter.drawText(
        QRectF(x + w * 0.13, y + h * 0.455, w * 0.74, h * 0.105),
        Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
        values.get("award", ""),
    )

    _draw_text(
        painter,
        QRectF(x + w * 0.12, y + h * 0.575, w * 0.76, h * 0.038),
        values.get("footer", ""),
        secondary,
        max(10, int(h * 0.020)),
        max(7, int(h * 0.013)),
        bold=False,
    )

    details_top = 0.635
    if values.get("kind") == "sports":
        label_width = w * 0.24
        value_width = w * 0.44
        for offset, label_key, value_key in (
            (0.00, "discipline_label", "discipline"),
            (0.055, "placement_label", "placement"),
        ):
            _draw_text(
                painter,
                QRectF(x + w * 0.13, y + h * (details_top + offset), label_width, h * 0.035),
                values.get(label_key, ""),
                secondary,
                max(9, int(h * 0.017)),
                max(7, int(h * 0.012)),
                bold=False,
                flags=Qt.AlignLeft | Qt.AlignVCenter,
            )
            _draw_text(
                painter,
                QRectF(x + w * 0.37, y + h * (details_top + offset), value_width, h * 0.035),
                values.get(value_key, ""),
                primary,
                max(10, int(h * 0.019)),
                max(7, int(h * 0.012)),
                bold=True,
                flags=Qt.AlignLeft | Qt.AlignVCenter,
            )
            painter.setPen(QPen(line_color, max(1.0, w * 0.0015)))
            painter.drawLine(
                x + w * 0.37,
                y + h * (details_top + offset + 0.036),
                x + w * 0.81,
                y + h * (details_top + offset + 0.036),
            )
        footer_y = 0.770
    else:
        footer_y = 0.680

    left_text = f"{values.get('date_label', '')}  {values.get('date', '')}".strip()
    right_text = f"{values.get('signature_label', '')}  {values.get('signature', '')}".strip()
    _draw_text(
        painter,
        QRectF(x + w * 0.105, y + h * footer_y, w * 0.385, h * 0.046),
        left_text,
        primary,
        max(11, int(h * 0.021)),
        max(8, int(h * 0.014)),
        bold=True,
        flags=Qt.AlignLeft | Qt.AlignVCenter,
    )
    _draw_text(
        painter,
        QRectF(x + w * 0.510, y + h * footer_y, w * 0.385, h * 0.046),
        right_text,
        primary,
        max(11, int(h * 0.021)),
        max(8, int(h * 0.014)),
        bold=True,
        flags=Qt.AlignRight | Qt.AlignVCenter,
    )
    painter.restore()


def paint_diploma_a4_sheet(
    painter: QPainter,
    page: QRectF,
    values: dict,
    background_path: str,
    logo_path: str,
    show_cut_line=True,
):
    """A4 na šířku se dvěma totožnými A5 na výšku."""
    half = page.width() / 2.0
    left = QRectF(page.left(), page.top(), half, page.height())
    right = QRectF(page.left() + half, page.top(), half, page.height())
    paint_diploma_page(painter, left, values, background_path, logo_path)
    paint_diploma_page(painter, right, values, background_path, logo_path)
    if show_cut_line:
        painter.save()
        painter.setPen(QPen(QColor(245, 222, 164, 170), max(1.0, page.width() * 0.001), Qt.DashLine))
        painter.drawLine(page.center().x(), page.top(), page.center().x(), page.bottom())
        painter.restore()


def paint_two_a5_landscape_sheet(
    painter: QPainter,
    page: QRectF,
    values: dict,
    background_path: str,
    logo_path: str,
    show_cut_line=True,
):
    """A4 na výšku se dvěma totožnými A5 na šířku."""
    half = page.height() / 2.0
    top = QRectF(page.left(), page.top(), page.width(), half)
    bottom = QRectF(page.left(), page.top() + half, page.width(), half)
    paint_diploma_page(painter, top, values, background_path, logo_path)
    paint_diploma_page(painter, bottom, values, background_path, logo_path)
    if show_cut_line:
        painter.save()
        painter.setPen(QPen(QColor(110, 78, 35, 175), max(1.0, page.width() * 0.001), Qt.DashLine))
        painter.drawLine(page.left(), page.center().y(), page.right(), page.center().y())
        painter.restore()


def _normalized_list(values, count: int, fallback_prefix: str):
    result = [str(value).strip() for value in values if str(value).strip()]
    while len(result) < count:
        result.append(f"{fallback_prefix} {len(result) + 1}")
    return result[:count]


def paint_cleaning_a4_sheet(
    painter: QPainter,
    page: QRectF,
    values: dict,
    background_path: str,
    logo_path: str,
):
    """Jedna úklidová listina B na A4 na šířku."""
    painter.save()
    painter.setClipRect(page)
    _draw_background(painter, page, background_path, values.get("economical_print", False))
    w, h = page.width(), page.height()
    x, y = page.left(), page.top()

    logo = _cached_pixmap(logo_path)
    if values.get("show_logo", True) and not logo.isNull():
        logo_h = h * 0.125
        logo_w = logo_h * logo.width() / max(1, logo.height())
        painter.drawPixmap(
            QRectF(x + w * 0.045, y + h * 0.045, logo_w, logo_h),
            logo,
            QRectF(logo.rect()),
        )

    ink = QColor("#3b2513")
    editable = isinstance(values.get("text_boxes"), list)
    if not editable:
        _draw_text(
            painter,
            QRectF(x + w * 0.265, y + h * 0.052, w * 0.470, h * 0.060),
            values.get("title", ""),
            ink,
            max(18, int(h * 0.045)),
            max(10, int(h * 0.025)),
        )
        _draw_text(
            painter,
            QRectF(x + w * 0.275, y + h * 0.112, w * 0.450, h * 0.036),
            values.get("subtitle", ""),
            ink,
            max(10, int(h * 0.022)),
            max(7, int(h * 0.014)),
            bold=True,
        )

    cabins = _normalized_list(values.get("cabins", []), 13, "Chatka")
    dates = _normalized_list(values.get("dates", []), 14, "Den")
    headers = [values.get("cabin_header", "Chatka"), *dates, values.get("total_header", "Součet"), values.get("rank_header", "Pořadí")]
    table = QRectF(x + w * 0.145, y + h * 0.185, w * 0.710, h * 0.670)
    name_weight = 1.70
    regular_weight = 1.0
    total_weight = 1.25
    rank_weight = 1.25
    weights = [name_weight] + [regular_weight] * 14 + [total_weight, rank_weight]
    unit = table.width() / sum(weights)
    row_height = table.height() / 14.0

    painter.setPen(QPen(QColor(91, 54, 21, 205), max(1.0, w * 0.0008)))
    header_fill = QColor(230, 201, 147, 205)
    body_fill = QColor(246, 220, 169, 76)
    header_text = ink
    body_text = ink
    painter.setBrush(Qt.NoBrush)

    left = table.left()
    column_rects = []
    for weight in weights:
        column_rects.append(QRectF(left, table.top(), unit * weight, table.height()))
        left += unit * weight

    for column, column_rect in enumerate(column_rects):
        cell = QRectF(column_rect.left(), table.top(), column_rect.width(), row_height)
        painter.fillRect(cell, header_fill)
        painter.drawRect(cell)
        if not editable:
            _draw_text(
                painter,
                cell.adjusted(2, 1, -2, -1),
                headers[column],
                header_text,
                max(7, int(h * 0.016)),
                max(5, int(h * 0.010)),
            )

    for row in range(13):
        top = table.top() + row_height * (row + 1)
        for column, column_rect in enumerate(column_rects):
            cell = QRectF(column_rect.left(), top, column_rect.width(), row_height)
            painter.fillRect(cell, body_fill)
            painter.drawRect(cell)
            if column == 0 and not editable:
                _draw_text(
                    painter,
                    cell.adjusted(3, 1, -2, -1),
                    cabins[row],
                    body_text,
                    max(7, int(h * 0.016)),
                    max(5, int(h * 0.010)),
                    flags=Qt.AlignLeft | Qt.AlignVCenter,
                )

    if editable:
        _paint_editable_text_boxes(painter, page, values.get("text_boxes", []), ink, ink)
    else:
        _draw_text(
            painter,
            QRectF(x + w * 0.275, y + h * 0.876, w * 0.450, h * 0.036),
            values.get("footer", ""),
            ink,
            max(9, int(h * 0.019)),
            max(6, int(h * 0.012)),
            bold=True,
        )
    painter.restore()


def configure_a4_printer(printer: QPrinter, layout="two_a5_portrait"):
    printer.setPageSize(QPageSize(QPageSize.A4))
    orientation = (
        QPageLayout.Portrait
        if layout in ("a4_portrait", "two_a5_landscape")
        else QPageLayout.Landscape
    )
    printer.setPageOrientation(orientation)
    printer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
    printer.setFullPage(True)


def paint_to_printer(
    printer: QPrinter,
    kind: str,
    values: dict,
    background_path: str,
    logo_path: str,
):
    layout = str(values.get("layout") or ("a4_landscape" if kind == "cleaning" else "two_a5_portrait"))
    configure_a4_printer(printer, layout)
    painter = QPainter(printer)
    if not painter.isActive():
        return False
    page = QRectF(printer.pageRect(QPrinter.DevicePixel))
    if kind == "cleaning":
        paint_cleaning_a4_sheet(painter, page, values, background_path, logo_path)
    elif layout == "two_a5_landscape":
        paint_two_a5_landscape_sheet(painter, page, values, background_path, logo_path, show_cut_line=True)
    elif layout == "a4_portrait" or layout == "a4_landscape":
        paint_diploma_page(painter, page, values, background_path, logo_path)
    else:
        paint_diploma_a4_sheet(painter, page, values, background_path, logo_path, show_cut_line=True)
    painter.end()
    return True


class DiplomaSheetPreview(QWidget):
    """Živý náhled A4 s přímým přesouváním textových polí na diplomu."""

    textBoxSelected = Signal(str)
    textBoxGeometryChanged = Signal(str, float, float, float, float)
    textBoxDeleteRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kind = "camp"
        self.values = {}
        self.background_path = ""
        self.logo_path = ""
        self.selected_text_box_id = ""
        self._page_rect = QRectF()
        self._active_half = 0
        self._drag_mode = ""
        self._drag_start = QPointF()
        self._drag_geometry = (0.0, 0.0, 0.0, 0.0)
        self.setMinimumSize(480, 370)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setToolTip(
            "Kliknutím vyber text. Tažením ho přesuň, tažením pravého dolního rohu změň jeho velikost."
        )

    def set_document(self, kind: str, values: dict, background_path: str, logo_path: str):
        self.kind = kind
        self.values = dict(values)
        self.background_path = background_path
        self.logo_path = logo_path
        if self.selected_text_box_id and self._box_by_id(self.selected_text_box_id) is None:
            self.selected_text_box_id = ""
        self.update()

    def set_selected_text_box(self, box_id: str):
        self.selected_text_box_id = str(box_id or "")
        self.update()

    def _boxes(self):
        boxes = self.values.get("text_boxes", [])
        return boxes if isinstance(boxes, list) else []

    def _box_by_id(self, box_id: str):
        for box in self._boxes():
            if isinstance(box, dict) and str(box.get("id", "")) == str(box_id):
                return box
        return None

    def _layout(self):
        return str(self.values.get("layout") or ("a4_landscape" if self.kind == "cleaning" else "two_a5_portrait"))

    def _document_page(self, index: int) -> QRectF:
        if self._page_rect.isEmpty():
            return QRectF()
        layout = self._layout()
        if layout == "two_a5_portrait":
            half_width = self._page_rect.width() / 2.0
            return QRectF(
                self._page_rect.left() + half_width * int(bool(index)),
                self._page_rect.top(), half_width, self._page_rect.height(),
            )
        if layout == "two_a5_landscape":
            half_height = self._page_rect.height() / 2.0
            return QRectF(
                self._page_rect.left(),
                self._page_rect.top() + half_height * int(bool(index)),
                self._page_rect.width(), half_height,
            )
        return QRectF(self._page_rect)

    def _document_page_count(self):
        return 2 if self._layout().startswith("two_a5") else 1

    def _hit_test(self, point: QPointF):
        if self._page_rect.isEmpty() or not self._page_rect.contains(point):
            return "", 0, ""
        page_index = 0
        for index in range(self._document_page_count()):
            if self._document_page(index).contains(point):
                page_index = index
                break
        document_page = self._document_page(page_index)
        for box in reversed(self._boxes()):
            if not isinstance(box, dict):
                continue
            rect = _text_box_rect(document_page, box)
            center = rect.center()
            transform = QTransform()
            transform.translate(center.x(), center.y())
            transform.rotate(float(box.get("rotation", 0.0)))
            inverse, invertible = transform.inverted()
            local_point = inverse.map(point) if invertible else QPointF(point)
            local_rect = QRectF(-rect.width() / 2.0, -rect.height() / 2.0, rect.width(), rect.height())
            handle_size = max(8.0, min(rect.width(), rect.height()) * 0.16)
            handle = QRectF(
                local_rect.right() - handle_size,
                local_rect.bottom() - handle_size,
                handle_size * 1.5,
                handle_size * 1.5,
            )
            if handle.contains(local_point):
                return str(box.get("id", "")), page_index, "resize"
            if local_rect.adjusted(-4, -4, 4, 4).contains(local_point):
                return str(box.get("id", "")), page_index, "move"
        return "", page_index, ""

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        box_id, half, mode = self._hit_test(event.position())
        self._active_half = half
        self.setFocus(Qt.MouseFocusReason)
        if not box_id:
            self.selected_text_box_id = ""
            self.textBoxSelected.emit("")
            self.update()
            event.accept()
            return
        self.selected_text_box_id = box_id
        self.textBoxSelected.emit(box_id)
        box = self._box_by_id(box_id)
        if box is not None:
            self._drag_mode = mode
            self._drag_start = QPointF(event.position())
            self._drag_geometry = (
                float(box.get("x", 0.1)),
                float(box.get("y", 0.1)),
                float(box.get("width", 0.8)),
                float(box.get("height", 0.08)),
            )
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_mode and self.selected_text_box_id:
            page = self._document_page(self._active_half)
            if page.isEmpty():
                return
            dx = (event.position().x() - self._drag_start.x()) / max(1.0, page.width())
            dy = (event.position().y() - self._drag_start.y()) / max(1.0, page.height())
            x, y, width, height = self._drag_geometry
            if self._drag_mode == "resize":
                width = max(0.04, min(1.0 - x, width + dx))
                height = max(0.025, min(1.0 - y, height + dy))
            else:
                x = max(0.0, min(1.0 - width, x + dx))
                y = max(0.0, min(1.0 - height, y + dy))
            box = self._box_by_id(self.selected_text_box_id)
            if box is not None:
                box.update({"x": x, "y": y, "width": width, "height": height})
                self.textBoxGeometryChanged.emit(
                    self.selected_text_box_id, x, y, width, height
                )
            self.setCursor(Qt.SizeFDiagCursor if self._drag_mode == "resize" else Qt.ClosedHandCursor)
            self.update()
            event.accept()
            return
        box_id, _half, mode = self._hit_test(event.position())
        if box_id:
            self.setCursor(Qt.SizeFDiagCursor if mode == "resize" else Qt.OpenHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_mode:
            self._drag_mode = ""
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        box = self._box_by_id(self.selected_text_box_id)
        if box is not None and event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 0.001 if event.modifiers() & Qt.ShiftModifier else 0.005
            x = float(box.get("x", 0.1))
            y = float(box.get("y", 0.1))
            width = float(box.get("width", 0.8))
            height = float(box.get("height", 0.08))
            if event.key() == Qt.Key_Left:
                x -= step
            elif event.key() == Qt.Key_Right:
                x += step
            elif event.key() == Qt.Key_Up:
                y -= step
            else:
                y += step
            x = max(0.0, min(1.0 - width, x))
            y = max(0.0, min(1.0 - height, y))
            box.update({"x": x, "y": y})
            self.textBoxGeometryChanged.emit(self.selected_text_box_id, x, y, width, height)
            self.update()
            event.accept()
            return
        if box is not None and event.key() == Qt.Key_Delete:
            self.textBoxDeleteRequested.emit(self.selected_text_box_id)
            event.accept()
            return
        super().keyPressEvent(event)

    def _draw_selection(self, painter: QPainter):
        box = self._box_by_id(self.selected_text_box_id)
        if box is None:
            return
        rect = _text_box_rect(self._document_page(self._active_half), box)
        center = rect.center()
        painter.save()
        painter.translate(center)
        painter.rotate(float(box.get("rotation", 0.0)))
        local_rect = QRectF(-rect.width() / 2.0, -rect.height() / 2.0, rect.width(), rect.height())
        pen_width = max(1.0, self.width() * 0.0015)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor("#59d6e5"), pen_width, Qt.DashLine))
        painter.drawRect(local_rect)
        handle = max(7.0, min(rect.width(), rect.height()) * 0.14)
        painter.setPen(QPen(QColor("#f7d27b"), pen_width))
        painter.setBrush(QColor("#123b46"))
        painter.drawRect(
            QRectF(local_rect.right() - handle / 2.0, local_rect.bottom() - handle / 2.0, handle, handle)
        )
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#07131b"))
        available = QRectF(self.rect()).adjusted(14, 14, -14, -14)
        portrait = self._layout() in ("a4_portrait", "two_a5_landscape")
        ratio = (
            A4_PREVIEW_SIZE.height() / A4_PREVIEW_SIZE.width()
            if portrait else A4_PREVIEW_SIZE.width() / A4_PREVIEW_SIZE.height()
        )
        width = min(available.width(), available.height() * ratio)
        height = width / ratio
        if height > available.height():
            height = available.height()
            width = height * ratio
        page = QRectF(
            available.center().x() - width / 2,
            available.center().y() - height / 2,
            width,
            height,
        )
        self._page_rect = QRectF(page)
        painter.fillRect(page.adjusted(5, 5, 8, 8), QColor(0, 0, 0, 105))
        layout = self._layout()
        if self.kind == "cleaning":
            paint_cleaning_a4_sheet(painter, page, self.values, self.background_path, self.logo_path)
            self._draw_selection(painter)
        elif layout == "two_a5_landscape":
            paint_two_a5_landscape_sheet(
                painter, page, self.values, self.background_path, self.logo_path, show_cut_line=True
            )
            self._draw_selection(painter)
        elif layout in ("a4_portrait", "a4_landscape"):
            paint_diploma_page(painter, page, self.values, self.background_path, self.logo_path)
            self._draw_selection(painter)
        else:
            paint_diploma_a4_sheet(
                painter,
                page,
                self.values,
                self.background_path,
                self.logo_path,
                show_cut_line=True,
            )
            self._draw_selection(painter)


def save_document_pdf(parent, kind: str, values: dict, background_path: str, logo_path: str):
    default_names = {
        "cleaning": "hodnoceni_uklidu_A4.pdf",
        "cleaning_award": "diplom_za_uklid_2x_A5_na_A4.pdf",
        "daily": "denni_program_A4.pdf",
        "meal": "jidelnicek_A4.pdf",
    }
    default_name = default_names.get(kind, f"diplom_{kind}_2x_A5_na_A4.pdf")
    path, _filter = QFileDialog.getSaveFileName(parent, "Uložit PDF", default_name, "PDF (*.pdf)")
    if not path:
        return False
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    if not paint_to_printer(printer, kind, values, background_path, logo_path):
        QMessageBox.warning(parent, "PDF", "PDF se nepodařilo vytvořit.")
        return False
    return True


def print_document(parent, kind: str, values: dict, background_path: str, logo_path: str):
    printer = QPrinter(QPrinter.HighResolution)
    configure_a4_printer(printer, str(values.get("layout") or "two_a5_portrait"))
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Tisk pirátské listiny")
    if dialog.exec() != QPrintDialog.Accepted:
        return False
    return paint_to_printer(printer, kind, values, background_path, logo_path)
