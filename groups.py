"""Moderní pirátský modul oddílů, osobních karet a importu z Excelu."""

from __future__ import annotations

import copy
import html
import math
import os
import re

from PySide6.QtCore import QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPageLayout, QPageSize, QPainter, QPen, QPixmap, QTextDocument, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_paths import get_user_data_dir
from fire_effects import PirateModuleDialog
from groups_data import (
    GroupsDataError,
    average_child_age,
    export_groups_workbook,
    load_groups_data,
    merge_groups_data,
    normalized_label,
    parse_groups_workbook,
    person_display_name,
    person_field,
    roster_entries,
    save_groups_data,
)


GOLD = QColor("#c99b4e")
GOLD_LIGHT = QColor("#f4dea4")


def _field_union(people: list[dict]) -> list[str]:
    labels = []
    known = set()
    for person in people:
        for label in (person.get("fields") or {}).keys():
            key = normalized_label(label)
            if key and key not in known:
                known.add(key)
                labels.append(str(label))
    return labels


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _clean_text(value) -> str:
    return " ".join(str(value or "").split())


def _parse_sort_number(value):
    match = re.search(r"-?\d+(?:[,.]\d+)?", str(value or ""))
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", "."))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _person_lookup(person: dict) -> dict:
    return {
        normalized_label(label): value
        for label, value in (person.get("fields") or {}).items()
    }


def _person_field_by_key(person: dict, key: str) -> str:
    lookup = _person_lookup(person)
    return _clean_text(lookup.get(normalized_label(key), ""))


def _iter_people(groups: list[dict]):
    for group in groups:
        for collection in ("children", "leaders"):
            for person in group.get(collection, []):
                if isinstance(person, dict):
                    yield person


def _sync_person_field_schema(groups: list[dict]) -> bool:
    """Doplní nově vytvořené položky osobní karty všem ostatním osobám."""
    schema = []
    known = set()
    for person in _iter_people(groups):
        fields = person.get("fields") or {}
        for label in fields.keys():
            key = normalized_label(label)
            if key and key not in known:
                known.add(key)
                schema.append(str(label))

    changed = False
    for person in _iter_people(groups):
        fields = person.get("fields")
        if not isinstance(fields, dict):
            fields = {}
            person["fields"] = fields
            changed = True
        person_keys = {
            normalized_label(label)
            for label in fields.keys()
            if normalized_label(label)
        }
        for label in schema:
            key = normalized_label(label)
            if key and key not in person_keys:
                fields[label] = ""
                person_keys.add(key)
                changed = True
    return changed


def _accommodation_people(groups: list[dict]) -> dict[str, list[dict]]:
    accommodations = {}
    for group in groups:
        group_name = _clean_text(group.get("name")) or "Oddíl"
        for collection, role_label in (("children", "Dítě"), ("leaders", "Vedoucí")):
            for person in group.get(collection, []):
                accommodation = _person_field_by_key(person, "Ubytování")
                if not accommodation:
                    continue
                accommodations.setdefault(accommodation, []).append(
                    {
                        "group_id": group.get("id"),
                        "group_name": group_name,
                        "person_id": person.get("id"),
                        "role": role_label,
                        "collection": collection,
                        "person": person,
                    }
                )
    for people in accommodations.values():
        people.sort(key=lambda item: person_display_name(item["person"]).casefold())
    return dict(sorted(accommodations.items(), key=lambda item: item[0].casefold()))


def _accommodation_export_groups(groups: list[dict], accommodation_name: str | None = None) -> list[dict]:
    result = []
    for name, people in _accommodation_people(groups).items():
        if accommodation_name is not None and name != accommodation_name:
            continue
        children = []
        leaders = []
        for item in people:
            person = copy.deepcopy(item["person"])
            fields = dict(person.get("fields") or {})
            fields.setdefault("Oddíl", item.get("group_name") or "")
            person["fields"] = fields
            if item.get("collection") == "leaders":
                leaders.append(person)
            else:
                children.append(person)
        result.append(
            {
                "id": f"accommodation-{normalized_label(name)}",
                "name": name,
                "children": children,
                "leaders": leaders,
            }
        )
    return result


class GroupCard(QPushButton):
    """Celoplošně klikací průhledná dlaždice oddílu."""

    def __init__(self, group: dict, icon_path: str, parent=None):
        super().__init__(parent)
        self.group = group
        self.icon = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        self.hovered = False
        self.pressed = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumSize(250, 176)
        self.setMaximumSize(430, 205)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet("background:transparent; border:none;")
        self.setAccessibleName(str(group.get("name") or "Oddíl"))

    def sizeHint(self):
        return QSize(330, 188)

    def hitButton(self, position):
        return self.rect().contains(position)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.pressed:
            rect.translate(0, 2)
        if self.hovered or self.hasFocus():
            painter.setPen(QPen(QColor(244, 222, 164, 90), 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 18, 18)
        painter.setPen(QPen(GOLD_LIGHT if self.hovered else GOLD, 2 if self.hovered else 1.3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 16, 16)
        painter.setPen(QPen(QColor(201, 155, 78, 85), 1))
        painter.drawRoundedRect(rect.adjusted(7, 7, -7, -7), 12, 12)

        if not self.icon.isNull():
            pixmap = self.icon.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - pixmap.width()) // 2, 14, pixmap)

        title = str(self.group.get("name") or "Oddíl").upper()
        title_font = QFont("Georgia", 17, QFont.Bold)
        while title_font.pointSize() > 10 and QFontMetrics(title_font).horizontalAdvance(title) > self.width() - 34:
            title_font.setPointSize(title_font.pointSize() - 1)
        painter.setFont(title_font)
        painter.setPen(GOLD_LIGHT)
        painter.drawText(QRectF(18, 72, self.width() - 36, 30), Qt.AlignCenter, title)

        leaders = ", ".join(
            person_display_name(person) for person in self.group.get("leaders", [])
        ) or "Vedoucí zatím nejsou zadaní"
        painter.setFont(QFont("Georgia", 9, QFont.Bold))
        painter.setPen(QColor("#ead8b3"))
        option = QTextOption(Qt.AlignHCenter | Qt.AlignTop)
        option.setWrapMode(QTextOption.WordWrap)
        painter.drawText(
            QRectF(20, 105, self.width() - 40, 38),
            "Vedoucí: " + leaders,
            option,
        )

        age = average_child_age(self.group)
        age_text = "—" if age is None else f"{age:.1f}".replace(".", ",") + " let"
        summary = f"{len(self.group.get('children', []))} dětí  •  věkový průměr {age_text}"
        painter.setFont(QFont("Georgia", 9))
        painter.setPen(QColor(224, 207, 169, 205))
        painter.drawText(QRectF(16, self.height() - 42, self.width() - 32, 24), Qt.AlignCenter, summary)


class AccommodationCard(QPushButton):
    """Klikací dlaždice přehledu ubytování a jednotlivých srubů."""

    def __init__(self, title: str, subtitle: str, summary: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.summary = summary
        self.icon = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        self.hovered = False
        self.pressed = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumSize(250, 176)
        self.setMaximumSize(430, 205)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet("background:transparent; border:none;")
        self.setAccessibleName(title)

    def sizeHint(self):
        return QSize(330, 188)

    def hitButton(self, position):
        return self.rect().contains(position)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.pressed:
            rect.translate(0, 2)
        glow = QColor(244, 222, 164, 88 if self.hovered else 36)
        painter.setPen(QPen(glow, 4 if self.hovered else 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 18, 18)
        painter.setPen(QPen(GOLD_LIGHT if self.hovered else GOLD, 2 if self.hovered else 1.3))
        painter.drawRoundedRect(rect, 16, 16)
        painter.setPen(QPen(QColor(201, 155, 78, 105), 1))
        painter.drawRoundedRect(rect.adjusted(7, 7, -7, -7), 12, 12)

        if not self.icon.isNull():
            pixmap = self.icon.scaled(62, 62, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap((self.width() - pixmap.width()) // 2, 13, pixmap)

        title = str(self.title or "Ubytování").upper()
        title_font = QFont("Georgia", 17, QFont.Bold)
        while title_font.pointSize() > 10 and QFontMetrics(title_font).horizontalAdvance(title) > self.width() - 34:
            title_font.setPointSize(title_font.pointSize() - 1)
        painter.setFont(title_font)
        painter.setPen(GOLD_LIGHT)
        painter.drawText(QRectF(18, 77, self.width() - 36, 30), Qt.AlignCenter, title)

        painter.setFont(QFont("Georgia", 9, QFont.Bold))
        painter.setPen(QColor("#fff0bd" if self.hovered else "#ead8b3"))
        option = QTextOption(Qt.AlignHCenter | Qt.AlignTop)
        option.setWrapMode(QTextOption.WordWrap)
        painter.drawText(QRectF(20, 111, self.width() - 40, 34), self.subtitle, option)

        painter.setFont(QFont("Georgia", 9))
        painter.setPen(QColor(224, 207, 169, 210))
        painter.drawText(QRectF(16, self.height() - 42, self.width() - 32, 24), Qt.AlignCenter, self.summary)


class PersonEditorDialog(QDialog):
    """Dynamická osobní karta se zcela upravitelnými položkami."""

    def __init__(self, person: dict, group_name: str, parent=None, *, is_new=False):
        super().__init__(parent)
        self.original = copy.deepcopy(person)
        self.payload = None
        self.delete_requested = False
        self.rows = []
        self.card_background = QPixmap()
        if parent is not None and hasattr(parent, "module_background"):
            self.card_background = QPixmap(parent.module_background)
        self.setWindowTitle("Karta osoby")
        self.setModal(True)
        self.resize(660, 610)
        self.setMinimumSize(540, 480)
        self.setStyleSheet(self._style_sheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)

        title = QLabel(person_display_name(person) if not is_new else "NOVÁ OSOBA", self)
        title.setObjectName("personTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        group_label = QLabel(f"{group_name}  •  všechny položky lze změnit nebo doplnit", self)
        group_label.setAlignment(Qt.AlignCenter)
        group_label.setObjectName("personSubtitle")
        root.addWidget(group_label)

        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Zařazení", self))
        self.role_combo = QComboBox(self)
        self.role_combo.addItem("Dítě", "child")
        self.role_combo.addItem("Vedoucí", "leader")
        self.role_combo.setCurrentIndex(0 if person.get("role") != "leader" else 1)
        role_row.addWidget(self.role_combo, 1)
        root.addLayout(role_row)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.fields_host = QWidget(scroll)
        self.fields_layout = QVBoxLayout(self.fields_host)
        self.fields_layout.setContentsMargins(4, 4, 4, 4)
        self.fields_layout.setSpacing(8)
        self.fields_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.fields_host)
        root.addWidget(scroll, 1)

        for label, value in (person.get("fields") or {}).items():
            self._add_field_row(str(label), str(value))
        if not self.rows:
            self._add_field_row("Jméno", "")
            self._add_field_row("Příjmení", "")

        add_button = QPushButton("+  PŘIDAT DALŠÍ ÚDAJ", self)
        add_button.clicked.connect(lambda: self._add_field_row("Nový údaj", ""))
        root.addWidget(add_button, 0, Qt.AlignLeft)

        buttons = QHBoxLayout()
        if not is_new:
            delete_button = QPushButton("ODSTRANIT OSOBU", self)
            delete_button.setObjectName("dangerButton")
            delete_button.clicked.connect(self._request_delete)
            buttons.addWidget(delete_button)
        buttons.addStretch(1)
        cancel_button = QPushButton("ZRUŠIT", self)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        save_button = QPushButton("ULOŽIT KARTU", self)
        save_button.setDefault(True)
        save_button.clicked.connect(self._save)
        buttons.addWidget(save_button)
        root.addLayout(buttons)

    def _style_sheet(self):
        return """
            QDialog { background:transparent; color:#ead8b3; }
            QLabel { color:#ead8b3; background:transparent; font-family:Georgia; font-weight:bold; }
            QLabel#personTitle { color:#f4dea4; font-size:25px; letter-spacing:2px; }
            QLabel#personSubtitle { color:#cdb98d; font-size:11px; font-style:italic; font-weight:normal; }
            QLineEdit, QComboBox {
                color:#f0e2c0; background:rgba(2,14,22,165); border:1px solid #a47a3e;
                border-radius:9px; padding:8px; selection-background-color:#176c76;
            }
            QScrollArea, QWidget { background:transparent; }
            QPushButton {
                color:#f4dea4; background:rgba(13,64,75,185); border:1px solid #c99b4e;
                border-radius:9px; padding:8px 12px; font-family:Georgia; font-weight:bold;
            }
            QPushButton:hover { color:#fff0bd; background:rgba(20,86,96,225); border:2px solid #f3d79a; }
            QPushButton#dangerButton { background:rgba(103,27,31,190); border-color:#c7776e; }
            QScrollBar:vertical { background:rgba(3,14,22,90); width:11px; }
            QScrollBar::handle:vertical { background:#9b7a45; min-height:30px; border-radius:5px; }
        """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if not self.card_background.isNull():
            scaled = self.card_background.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            crop_x = max(0, (scaled.width() - self.width()) // 2)
            crop_y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(
                self.rect(), scaled, QRect(crop_x, crop_y, self.width(), self.height())
            )
        else:
            painter.fillRect(self.rect(), QColor("#071923"))
        painter.fillRect(self.rect(), QColor(2, 10, 16, 82))

    def _add_field_row(self, label: str, value: str):
        row_widget = QWidget(self.fields_host)
        row_widget.setFixedHeight(46)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        label_edit = QLineEdit(label, row_widget)
        label_edit.setPlaceholderText("Název údaje, např. Telefon")
        value_edit = QLineEdit(value, row_widget)
        value_edit.setPlaceholderText("Hodnota")
        remove_button = QPushButton("×", row_widget)
        remove_button.setFixedWidth(40)
        remove_button.setObjectName("dangerButton")
        row.addWidget(label_edit, 2)
        row.addWidget(value_edit, 3)
        row.addWidget(remove_button)
        record = (row_widget, label_edit, value_edit)
        self.rows.append(record)
        remove_button.clicked.connect(lambda: self._remove_field_row(record))
        self.fields_layout.addWidget(row_widget)
        value_edit.setFocus()

    def _remove_field_row(self, record):
        if record not in self.rows:
            return
        self.rows.remove(record)
        record[0].deleteLater()

    def _request_delete(self):
        if QMessageBox.question(
            self,
            "Odstranit osobu",
            f"Opravdu chcete odstranit osobu {person_display_name(self.original)}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.delete_requested = True
            self.accept()

    def _save(self):
        fields = {}
        known = set()
        for _widget, label_edit, value_edit in self.rows:
            label = " ".join(label_edit.text().split())
            if not label:
                QMessageBox.warning(self, "Chybí název údaje", "Každá položka musí mít název.")
                label_edit.setFocus()
                return
            key = normalized_label(label)
            if key in known:
                QMessageBox.warning(self, "Duplicitní údaj", f"Položka „{label}“ je na kartě dvakrát.")
                label_edit.setFocus()
                return
            known.add(key)
            fields[label] = value_edit.text().strip()
        if not fields:
            QMessageBox.warning(self, "Prázdná karta", "Přidejte alespoň jeden údaj.")
            return
        self.payload = copy.deepcopy(self.original)
        self.payload["role"] = self.role_combo.currentData() or "child"
        self.payload["fields"] = fields
        self.accept()


class GroupsDialog(PirateModuleDialog):
    """Přehled oddílů, vyhledávání osob, osobní karty a Excel import/export."""

    def __init__(self, owner_window, icons_path: str):
        super().__init__(
            owner_window,
            "groups_BG.png",
            (
                (0.118, 0.255, 0.62),
                (0.945, 0.842, 1.18),
            ),
        )
        self.icons_path = icons_path
        self.section_visuals = {
            "groups": {
                "background": self._load_section_background("groups_BG.png"),
                "fire_anchors": (
                    (0.118, 0.255, 0.62),
                    (0.945, 0.842, 1.18),
                ),
            },
            "accommodation": {
                "background": self._load_section_background("accommodation_BG.png"),
                "fire_anchors": (
                    (0.027, 0.164, 0.25),
                    (0.069, 0.344, 0.36),
                    (0.039, 0.778, 1.05),
                    (0.735, 0.378, 0.34),
                    (0.960, 0.680, 0.86),
                ),
            },
        }
        self.data = load_groups_data()
        self.current_group_id = None
        self.current_accommodation_name = None
        self.children_sort = {"key": None, "reverse": False}
        self.accommodation_sort = {"key": None, "reverse": False}
        self.search_map = {}
        self.setWindowTitle("Pirátské oddíly a ubytování")
        self.setMinimumSize(960, 640)
        self.resize(1380, 820)
        self._build_ui()
        self.apply_pirate_glass()
        self._refresh_overview()

    def _load_section_background(self, file_name: str) -> QPixmap:
        path = os.path.join(self.icons_path, file_name)
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                return pixmap
        return QPixmap(self.module_background)

    def _set_section_background(self, section: str):
        visual = self.section_visuals.get(section, {})
        pixmap = visual.get("background")
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            self.module_background = QPixmap(pixmap)
        anchors = visual.get("fire_anchors", ())
        if hasattr(self, "fire_flicker"):
            self.fire_flicker.set_anchors(anchors)
        self.update()

    def _build_ui(self):
        self.setStyleSheet(self.styleSheet() + self._style_sheet())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(self)
        self.pages.setStyleSheet("QStackedWidget { background:transparent; border:none; }")
        self.overview_page = self._create_overview_page()
        self.detail_page = self._create_detail_page()
        self.accommodation_page = self._create_accommodation_page()
        self.accommodation_detail_page = self._create_accommodation_detail_page()
        self.pages.addWidget(self.overview_page)
        self.pages.addWidget(self.detail_page)
        self.pages.addWidget(self.accommodation_page)
        self.pages.addWidget(self.accommodation_detail_page)
        root.addWidget(self.pages)

    def _style_sheet(self):
        return """
            QFrame#groupsPanel {
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(7,34,44,118), stop:0.58 rgba(3,20,29,72), stop:1 rgba(2,13,21,48));
                border:1px solid rgba(205,159,78,188); border-radius:14px;
            }
            QLabel#groupsTitle { color:#f4dea4; font-family:Georgia; font-size:28px; font-weight:bold; letter-spacing:2px; }
            QLabel#groupsSubtitle { color:#d7c396; font-family:Georgia; font-size:12px; font-style:italic; }
            QLabel#groupsStats { color:#f4dea4; font-family:Georgia; font-size:12px; font-weight:bold; }
            QTableWidget {
                color:#f0e2c0; background:rgba(2,13,21,42); border:1px solid rgba(196,151,76,175);
                border-radius:11px; gridline-color:rgba(161,124,63,75); alternate-background-color:rgba(12,47,57,55);
            }
            QHeaderView::section {
                color:#f3d79a; background:rgba(9,42,52,218); border:none; border-right:1px solid rgba(201,155,78,100);
                padding:8px; font-family:Georgia; font-weight:bold;
            }
            QPushButton#personChip {
                text-align:left; background:rgba(4,24,33,76); border:1px solid rgba(205,159,78,175);
                min-height:50px; padding:8px 12px;
            }
            QPushButton#personChip:hover { background:rgba(18,82,89,160); border:2px solid #f3d79a; }
        """

    def _panel(self, parent=None):
        panel = QFrame(parent or self)
        panel.setObjectName("groupsPanel")
        return panel

    def _create_overview_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        root = QVBoxLayout(page)
        root.setContentsMargins(34, 25, 34, 28)
        root.setSpacing(12)

        title = QLabel("PIRÁTSKÉ ODDÍLY / UBYTOVÁNÍ", page)
        title.setObjectName("groupsTitle")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        subtitle = QLabel(
            "Posádky, děti, vedoucí a sruby na jednom místě • změna ubytování v kartě osoby se projeví všude",
            page,
        )
        subtitle.setObjectName("groupsSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        root.addWidget(subtitle)

        toolbar = self._panel(page)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 12, 14, 12)
        toolbar_layout.setSpacing(10)
        import_button = QPushButton("IMPORTOVAT EXCEL", toolbar)
        import_button.clicked.connect(self._import_excel)
        toolbar_layout.addWidget(import_button)
        export_button = QPushButton("EXPORTOVAT VŠECHNY", toolbar)
        export_button.clicked.connect(self._export_all)
        toolbar_layout.addWidget(export_button)
        clear_groups_button = QPushButton("SMAZAT ODDÍLY", toolbar)
        clear_groups_button.setObjectName("dangerButton")
        clear_groups_button.clicked.connect(self._clear_all_groups)
        toolbar_layout.addWidget(clear_groups_button)
        self.search_edit = QLineEdit(toolbar)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("Vyhledejte dítě nebo vedoucího…")
        self.search_edit.textChanged.connect(self._rebuild_group_cards)
        toolbar_layout.addWidget(self.search_edit, 1)
        self.stats_label = QLabel(toolbar)
        self.stats_label.setObjectName("groupsStats")
        toolbar_layout.addWidget(self.stats_label)
        root.addWidget(toolbar)

        self.groups_scroll = QScrollArea(page)
        self.groups_scroll.setWidgetResizable(True)
        self.groups_scroll.setFrameShape(QFrame.NoFrame)
        self.groups_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.groups_host = QWidget(self.groups_scroll)
        self.groups_host.setStyleSheet("background:transparent;")
        self.groups_grid = QGridLayout(self.groups_host)
        self.groups_grid.setContentsMargins(8, 8, 8, 8)
        self.groups_grid.setHorizontalSpacing(18)
        self.groups_grid.setVerticalSpacing(16)
        for column in range(3):
            self.groups_grid.setColumnStretch(column, 1)
        self.groups_scroll.setWidget(self.groups_host)
        root.addWidget(self.groups_scroll, 1)
        return page

    def _create_detail_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 21, 28, 25)
        root.setSpacing(10)

        heading = QHBoxLayout()
        back = QPushButton("‹  ZPĚT NA ODDÍLY / UBYTOVÁNÍ", page)
        back.clicked.connect(self.show_overview)
        heading.addWidget(back, 0, Qt.AlignTop)
        title_column = QVBoxLayout()
        self.detail_title = QLabel("ODDÍL", page)
        self.detail_title.setObjectName("groupsTitle")
        self.detail_title.setAlignment(Qt.AlignCenter)
        self.detail_stats = QLabel(page)
        self.detail_stats.setObjectName("groupsSubtitle")
        self.detail_stats.setAlignment(Qt.AlignCenter)
        title_column.addWidget(self.detail_title)
        title_column.addWidget(self.detail_stats)
        heading.addLayout(title_column, 1)
        rename = QPushButton("PŘEJMENOVAT ODDÍL", page)
        rename.clicked.connect(self._rename_group)
        heading.addWidget(rename, 0, Qt.AlignTop)
        root.addLayout(heading)

        leaders_panel = self._panel(page)
        leaders_layout = QVBoxLayout(leaders_panel)
        leaders_layout.setContentsMargins(13, 10, 13, 12)
        leaders_header = QHBoxLayout()
        leaders_title = QLabel("VEDOUCÍ ODDÍLU", leaders_panel)
        leaders_title.setObjectName("groupsStats")
        leaders_header.addWidget(leaders_title)
        leaders_header.addStretch(1)
        add_leader = QPushButton("+  PŘIDAT VEDOUCÍHO", leaders_panel)
        add_leader.clicked.connect(lambda: self._add_person("leader"))
        leaders_header.addWidget(add_leader)
        leaders_layout.addLayout(leaders_header)
        self.leaders_host = QWidget(leaders_panel)
        self.leaders_host.setStyleSheet("background:transparent;")
        self.leaders_grid = QGridLayout(self.leaders_host)
        self.leaders_grid.setContentsMargins(0, 0, 0, 0)
        self.leaders_grid.setSpacing(9)
        self.leaders_scroll = QScrollArea(leaders_panel)
        self.leaders_scroll.setWidgetResizable(True)
        self.leaders_scroll.setFrameShape(QFrame.NoFrame)
        self.leaders_scroll.setMinimumHeight(76)
        self.leaders_scroll.setMaximumHeight(165)
        self.leaders_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.leaders_scroll.setWidget(self.leaders_host)
        leaders_layout.addWidget(self.leaders_scroll)
        root.addWidget(leaders_panel)

        children_panel = self._panel(page)
        children_layout = QVBoxLayout(children_panel)
        children_layout.setContentsMargins(12, 10, 12, 12)
        children_header = QHBoxLayout()
        self.children_title = QLabel("DĚTI", children_panel)
        self.children_title.setObjectName("groupsStats")
        children_header.addWidget(self.children_title)
        children_header.addStretch(1)
        add_child = QPushButton("+  PŘIDAT DÍTĚ", children_panel)
        add_child.clicked.connect(lambda: self._add_person("child"))
        children_header.addWidget(add_child)
        export_group = QPushButton("EXPORTOVAT TENTO ODDÍL", children_panel)
        export_group.clicked.connect(self._export_current_group)
        children_header.addWidget(export_group)
        children_layout.addLayout(children_header)
        self.children_table = QTableWidget(0, 0, children_panel)
        self.children_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.children_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.children_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.children_table.setAlternatingRowColors(True)
        self.children_table.verticalHeader().setVisible(False)
        self.children_table.cellClicked.connect(self._child_row_clicked)
        child_header = self.children_table.horizontalHeader()
        child_header.setSectionsClickable(True)
        child_header.sectionClicked.connect(self._children_header_clicked)
        children_layout.addWidget(self.children_table, 1)
        root.addWidget(children_panel, 1)
        return page

    def _create_accommodation_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        root = QVBoxLayout(page)
        root.setContentsMargins(34, 25, 34, 28)
        root.setSpacing(12)

        heading = QHBoxLayout()
        back = QPushButton("‹  ZPĚT NA ODDÍLY / UBYTOVÁNÍ", page)
        back.clicked.connect(self.show_overview)
        heading.addWidget(back, 0, Qt.AlignTop)
        title_column = QVBoxLayout()
        title = QLabel("UBYTOVÁNÍ", page)
        title.setObjectName("groupsTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Sruby se skládají automaticky z položky Ubytování v osobních kartách.", page)
        subtitle.setObjectName("groupsSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        heading.addLayout(title_column, 1)
        export_all = QPushButton("EXPORTOVAT UBYTOVÁNÍ", page)
        export_all.clicked.connect(lambda: self._export_accommodations())
        heading.addWidget(export_all, 0, Qt.AlignTop)
        print_all = QPushButton("TISKNOUT UBYTOVÁNÍ", page)
        print_all.clicked.connect(lambda: self._print_accommodations())
        heading.addWidget(print_all, 0, Qt.AlignTop)
        root.addLayout(heading)

        self.accommodation_scroll = QScrollArea(page)
        self.accommodation_scroll.setWidgetResizable(True)
        self.accommodation_scroll.setFrameShape(QFrame.NoFrame)
        self.accommodation_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.accommodation_host = QWidget(self.accommodation_scroll)
        self.accommodation_host.setStyleSheet("background:transparent;")
        self.accommodation_grid = QGridLayout(self.accommodation_host)
        self.accommodation_grid.setContentsMargins(8, 8, 8, 8)
        self.accommodation_grid.setHorizontalSpacing(18)
        self.accommodation_grid.setVerticalSpacing(16)
        for column in range(3):
            self.accommodation_grid.setColumnStretch(column, 1)
        self.accommodation_scroll.setWidget(self.accommodation_host)
        root.addWidget(self.accommodation_scroll, 1)
        return page

    def _create_accommodation_detail_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 21, 28, 25)
        root.setSpacing(10)

        heading = QHBoxLayout()
        back = QPushButton("‹  ZPĚT NA UBYTOVÁNÍ", page)
        back.clicked.connect(self.show_accommodations)
        heading.addWidget(back, 0, Qt.AlignTop)
        title_column = QVBoxLayout()
        self.accommodation_title = QLabel("SRUB", page)
        self.accommodation_title.setObjectName("groupsTitle")
        self.accommodation_title.setAlignment(Qt.AlignCenter)
        self.accommodation_stats = QLabel(page)
        self.accommodation_stats.setObjectName("groupsSubtitle")
        self.accommodation_stats.setAlignment(Qt.AlignCenter)
        title_column.addWidget(self.accommodation_title)
        title_column.addWidget(self.accommodation_stats)
        heading.addLayout(title_column, 1)
        export_button = QPushButton("EXPORTOVAT SRUB", page)
        export_button.clicked.connect(lambda: self._export_accommodations(self.current_accommodation_name))
        heading.addWidget(export_button, 0, Qt.AlignTop)
        print_button = QPushButton("TISKNOUT SRUB", page)
        print_button.clicked.connect(lambda: self._print_accommodations(self.current_accommodation_name))
        heading.addWidget(print_button, 0, Qt.AlignTop)
        root.addLayout(heading)

        panel = self._panel(page)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 12)
        self.accommodation_people_table = QTableWidget(0, 5, panel)
        self.accommodation_people_table.setHorizontalHeaderLabels(("OSOBA", "ODDÍL", "VĚK", "POHLAVÍ", "ROLE"))
        self.accommodation_people_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.accommodation_people_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.accommodation_people_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.accommodation_people_table.setAlternatingRowColors(True)
        self.accommodation_people_table.verticalHeader().setVisible(False)
        self.accommodation_people_table.cellClicked.connect(self._accommodation_row_clicked)
        header = self.accommodation_people_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._accommodation_header_clicked)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        layout.addWidget(self.accommodation_people_table, 1)
        root.addWidget(panel, 1)
        return page

    def refresh_data(self):
        self.data = load_groups_data()
        self._refresh_overview()
        if self.current_group_id:
            self._refresh_detail()
        if hasattr(self, "accommodation_grid"):
            if self.pages.currentWidget() == self.accommodation_page:
                self._refresh_accommodations()
            if self.current_accommodation_name:
                self._refresh_accommodation_detail()
        if self.pages.currentWidget() == self.accommodation_page:
            self._refresh_accommodations()
        if self.current_accommodation_name:
            self._refresh_accommodation_detail()

    def show_overview(self):
        self._set_section_background("groups")
        self.data = load_groups_data()
        self.current_group_id = None
        self.current_accommodation_name = None
        self.search_edit.clear()
        self._refresh_overview()
        self.pages.setCurrentWidget(self.overview_page)

    def show_accommodations(self):
        self._set_section_background("accommodation")
        self.data = load_groups_data()
        self.current_group_id = None
        self.current_accommodation_name = None
        self._refresh_accommodations()
        self.pages.setCurrentWidget(self.accommodation_page)

    def show_accommodation(self, accommodation_name: str):
        if accommodation_name not in _accommodation_people(self.data.get("groups", [])):
            return
        self._set_section_background("accommodation")
        self.current_group_id = None
        self.current_accommodation_name = accommodation_name
        self._refresh_accommodation_detail()
        self.pages.setCurrentWidget(self.accommodation_detail_page)

    def _group(self, group_id=None):
        target = group_id or self.current_group_id
        return next((group for group in self.data.get("groups", []) if group.get("id") == target), None)

    def _refresh_overview(self):
        groups = self.data.get("groups", [])
        children = sum(len(group.get("children", [])) for group in groups)
        leaders = sum(len(group.get("leaders", [])) for group in groups)
        cabins = len(_accommodation_people(groups))
        self.stats_label.setText(f"ODDÍLY {len(groups)}  •  SRUBY {cabins}  •  DĚTI {children}  •  VEDOUCÍ {leaders}")
        self._refresh_completer()
        self._rebuild_group_cards()

    def _refresh_completer(self):
        self.search_map = {}
        labels = []
        for entry in roster_entries(self.data):
            label = f"{entry['name']}  —  {entry['group_name']} • {entry['role']}"
            if label in self.search_map:
                label += f" • {len(labels) + 1}"
            self.search_map[label] = (entry["group_id"], entry["person_id"], entry["role"])
            labels.append(label)
        completer = QCompleter(labels, self.search_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated.connect(self._search_activated)
        self.search_edit.setCompleter(completer)
        self.search_completer = completer

    def _search_activated(self, label: str):
        target = self.search_map.get(label)
        if not target:
            return
        group_id, person_id, role_label = target
        self.show_group(group_id)
        role = "leader" if role_label == "Vedoucí" else "child"
        QTimer.singleShot(0, lambda: self._open_person(person_id, role))

    def _group_matches(self, group: dict, query: str) -> bool:
        if not query:
            return True
        haystacks = [str(group.get("name") or "")]
        for person in list(group.get("leaders", [])) + list(group.get("children", [])):
            haystacks.append(person_display_name(person))
            haystacks.extend(str(value) for value in (person.get("fields") or {}).values())
        return any(query in value.casefold() for value in haystacks)

    def _rebuild_group_cards(self):
        _clear_layout(self.groups_grid)
        query = self.search_edit.text().strip().casefold() if hasattr(self, "search_edit") else ""
        groups = [group for group in self.data.get("groups", []) if self._group_matches(group, query)]
        position = 0
        if not query:
            accommodations = _accommodation_people(self.data.get("groups", []))
            people_count = sum(len(people) for people in accommodations.values())
            accommodation_card = AccommodationCard(
                "Ubytování",
                "Sruby podle položky Ubytování v osobních kartách",
                f"{len(accommodations)} srubů  •  {people_count} ubytovaných",
                os.path.join(self.icons_path, "ubytovani.png"),
                self.groups_host,
            )
            accommodation_card.clicked.connect(self.show_accommodations)
            self.groups_grid.addWidget(accommodation_card, 0, 0, Qt.AlignCenter)
            position = 1
        if not groups:
            message = (
                "Nikdo neodpovídá hledání."
                if query
                else "Zatím nejsou importované žádné oddíly. Klikněte na IMPORTOVAT EXCEL."
            )
            label = QLabel(message, self.groups_host)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color:#d8c49b; font-family:Georgia; font-size:15px; padding:40px;")
            self.groups_grid.addWidget(label, position // 3, position % 3, 1, max(1, 3 - (position % 3)))
            return
        icon_path = os.path.join(self.icons_path, "tancici_figurky.png")
        for index, group in enumerate(groups):
            card = GroupCard(group, icon_path, self.groups_host)
            card.clicked.connect(
                lambda _checked=False, group_id=group.get("id"): self.show_group(group_id)
            )
            cell = position + index
            self.groups_grid.addWidget(card, cell // 3, cell % 3, Qt.AlignCenter)

    def _refresh_accommodations(self):
        _clear_layout(self.accommodation_grid)
        accommodations = _accommodation_people(self.data.get("groups", []))
        if not accommodations:
            label = QLabel("Zatím není vyplněné žádné ubytování. Otevři osobu a doplň položku Ubytování.", self.accommodation_host)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color:#d8c49b; font-family:Georgia; font-size:15px; padding:40px;")
            self.accommodation_grid.addWidget(label, 0, 0, 1, 3)
            return
        icon_path = os.path.join(self.icons_path, "ubytovani.png")
        for index, (name, people) in enumerate(accommodations.items()):
            groups = sorted({item.get("group_name") or "Oddíl" for item in people}, key=str.casefold)
            subtitle = "Oddíly: " + ", ".join(groups[:3])
            if len(groups) > 3:
                subtitle += f" +{len(groups) - 3}"
            card = AccommodationCard(
                name,
                subtitle,
                f"{len(people)} ubytovaných",
                icon_path,
                self.accommodation_host,
            )
            card.clicked.connect(lambda _checked=False, cabin=name: self.show_accommodation(cabin))
            self.accommodation_grid.addWidget(card, index // 3, index % 3, Qt.AlignCenter)

    def _refresh_accommodation_detail(self):
        name = self.current_accommodation_name
        accommodations = _accommodation_people(self.data.get("groups", []))
        people = accommodations.get(name or "", [])
        if not people:
            self.current_accommodation_name = None
            self.show_accommodations()
            return
        self.accommodation_title.setText(str(name or "Srub").upper())
        group_count = len({item.get("group_id") for item in people})
        self.accommodation_stats.setText(f"{len(people)} ubytovaných  •  {group_count} oddílů")
        headers = ["OSOBA", "ODDÍL", "VĚK", "POHLAVÍ", "ROLE"]
        sorted_people = self._sorted_accommodation_people(people)
        self._accommodation_headers = headers
        self.accommodation_people_table.clear()
        self.accommodation_people_table.setColumnCount(len(headers))
        self.accommodation_people_table.setHorizontalHeaderLabels(
            self._accommodation_headers_with_sort_marker(headers)
        )
        self.accommodation_people_table.setRowCount(len(sorted_people))
        self.accommodation_row_refs = []
        for row, item in enumerate(sorted_people):
            person = item["person"]
            self.accommodation_row_refs.append(item)
            values = [
                person_display_name(person),
                item.get("group_name") or "",
                _person_field_by_key(person, "Věk"),
                _person_field_by_key(person, "Pohlaví"),
                item.get("role") or "",
            ]
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                if column in (2, 4):
                    table_item.setTextAlignment(Qt.AlignCenter)
                self.accommodation_people_table.setItem(row, column, table_item)
        header = self.accommodation_people_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(headers)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.accommodation_people_table.resizeRowsToContents()

    def show_group(self, group_id: str):
        if self._group(group_id) is None:
            return
        self._set_section_background("groups")
        self.current_group_id = group_id
        self.current_accommodation_name = None
        self._refresh_detail()
        self.pages.setCurrentWidget(self.detail_page)

    def _refresh_detail(self):
        group = self._group()
        if group is None:
            self.show_overview()
            return
        age = average_child_age(group)
        age_text = "—" if age is None else f"{age:.1f}".replace(".", ",") + " let"
        self.detail_title.setText(str(group.get("name") or "Oddíl").upper())
        self.detail_stats.setText(
            f"{len(group.get('children', []))} dětí  •  {len(group.get('leaders', []))} vedoucích  •  věkový průměr dětí {age_text}"
        )
        self._refresh_leaders(group)
        self._refresh_children(group)

    def _refresh_leaders(self, group: dict):
        _clear_layout(self.leaders_grid)
        leaders = group.get("leaders", [])
        if not leaders:
            label = QLabel("Vedoucí zatím nejsou zadaní.", self.leaders_host)
            self.leaders_grid.addWidget(label, 0, 0)
            return
        for index, leader in enumerate(leaders):
            phone = person_field(leader, "Telefon")
            text = person_display_name(leader)
            if phone:
                text += f"\nTelefon: {phone}"
            button = QPushButton(text, self.leaders_host)
            button.setObjectName("personChip")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, person_id=leader.get("id"): self._open_person(person_id, "leader")
            )
            self.leaders_grid.addWidget(button, index // 4, index % 4)
        for column in range(4):
            self.leaders_grid.setColumnStretch(column, 1)

    def _children_header_clicked(self, column: int):
        headers = getattr(self, "_children_headers", [])
        if not 0 <= column < len(headers):
            return
        header = headers[column]
        key = "name" if column == 0 else normalized_label(header)
        if self.children_sort.get("key") == key:
            self.children_sort["reverse"] = not bool(self.children_sort.get("reverse"))
        else:
            self.children_sort = {"key": key, "reverse": False}
        group = self._group()
        if group is not None:
            self._refresh_children(group)

    def _child_sort_value(self, child: dict, key: str):
        if key == "name":
            value = person_display_name(child)
        else:
            value = _person_field_by_key(child, key)
        if key in ("pocet", "vek"):
            number = _parse_sort_number(value)
            return number if number is not None else None
        return _clean_text(value).casefold() or None

    def _sorted_children(self, children: list[dict]) -> list[dict]:
        sort_key = self.children_sort.get("key")
        if not sort_key:
            return list(children)
        reverse = bool(self.children_sort.get("reverse"))
        with_values = []
        without_values = []
        for child in children:
            value = self._child_sort_value(child, sort_key)
            target = with_values if value is not None else without_values
            target.append((value, person_display_name(child).casefold(), child))
        with_values.sort(key=lambda item: (item[0], item[1]), reverse=reverse)
        without_values.sort(key=lambda item: item[1])
        return [item[2] for item in with_values + without_values]

    def _headers_with_sort_marker(self, headers: list[str]) -> list[str]:
        sort_key = self.children_sort.get("key")
        reverse = bool(self.children_sort.get("reverse"))
        marked = []
        for index, header in enumerate(headers):
            key = "name" if index == 0 else normalized_label(header)
            suffix = " ↓" if reverse else " ↑"
            marked.append(f"{header}{suffix}" if key == sort_key else header)
        return marked

    def _accommodation_header_clicked(self, column: int):
        headers = getattr(self, "_accommodation_headers", [])
        if not 0 <= column < len(headers):
            return
        key = {
            0: "name",
            1: "group",
            2: "vek",
            3: "pohlavi",
            4: "role",
        }.get(column)
        if not key:
            return
        if self.accommodation_sort.get("key") == key:
            self.accommodation_sort["reverse"] = not bool(self.accommodation_sort.get("reverse"))
        else:
            self.accommodation_sort = {"key": key, "reverse": False}
        self._refresh_accommodation_detail()

    def _accommodation_sort_value(self, item: dict, key: str):
        person = item.get("person") or {}
        if key == "name":
            value = person_display_name(person)
        elif key == "group":
            value = item.get("group_name") or ""
        elif key == "vek":
            value = _person_field_by_key(person, "Věk")
            number = _parse_sort_number(value)
            return number if number is not None else None
        elif key == "pohlavi":
            value = _person_field_by_key(person, "Pohlaví")
        elif key == "role":
            value = item.get("role") or ""
        else:
            value = ""
        return _clean_text(value).casefold() or None

    def _sorted_accommodation_people(self, people: list[dict]) -> list[dict]:
        sort_key = self.accommodation_sort.get("key")
        if not sort_key:
            return list(people)
        reverse = bool(self.accommodation_sort.get("reverse"))
        with_values = []
        without_values = []
        for item in people:
            value = self._accommodation_sort_value(item, sort_key)
            person_name = person_display_name(item.get("person") or {}).casefold()
            target = with_values if value is not None else without_values
            target.append((value, person_name, item))
        with_values.sort(key=lambda item: (item[0], item[1]), reverse=reverse)
        without_values.sort(key=lambda item: item[1])
        return [item[2] for item in with_values + without_values]

    def _accommodation_headers_with_sort_marker(self, headers: list[str]) -> list[str]:
        sort_key = self.accommodation_sort.get("key")
        reverse = bool(self.accommodation_sort.get("reverse"))
        keys = ("name", "group", "vek", "pohlavi", "role")
        marked = []
        for index, header in enumerate(headers):
            key = keys[index] if index < len(keys) else ""
            suffix = " ↓" if reverse else " ↑"
            marked.append(f"{header}{suffix}" if key == sort_key else header)
        return marked

    def _refresh_children(self, group: dict):
        children = group.get("children", [])
        fields = _field_union(children)
        visible_fields = [
            label for label in fields if normalized_label(label) not in ("jmeno", "prijmeni")
        ]
        headers = ["OSOBA"] + visible_fields
        sorted_children = self._sorted_children(children)
        self._children_headers = headers
        self.children_title.setText(f"DĚTI ODDÍLU  •  {len(children)}")
        self.children_table.clear()
        self.children_table.setColumnCount(len(headers))
        self.children_table.setHorizontalHeaderLabels(self._headers_with_sort_marker(headers))
        self.children_table.setRowCount(len(sorted_children))
        self.child_row_ids = []
        for row, child in enumerate(sorted_children):
            self.child_row_ids.append(child.get("id"))
            name_item = QTableWidgetItem(person_display_name(child))
            name_item.setData(Qt.UserRole, child.get("id"))
            name_item.setFont(QFont("Georgia", 10, QFont.Bold))
            self.children_table.setItem(row, 0, name_item)
            lookup = {normalized_label(label): value for label, value in (child.get("fields") or {}).items()}
            for column, label in enumerate(visible_fields, 1):
                self.children_table.setItem(row, column, QTableWidgetItem(str(lookup.get(normalized_label(label), ""))))
        header = self.children_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(headers)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.children_table.resizeRowsToContents()

    def _child_row_clicked(self, row: int, _column: int):
        if 0 <= row < len(getattr(self, "child_row_ids", [])):
            self._open_person(self.child_row_ids[row], "child")

    def _accommodation_row_clicked(self, row: int, _column: int):
        refs = getattr(self, "accommodation_row_refs", [])
        if not 0 <= row < len(refs):
            return
        item = refs[row]
        group = self._group(item.get("group_id"))
        if group is not None:
            self._open_person_in_group(group, item.get("person_id"))

    def _find_person(self, person_id: str):
        group = self._group()
        if group is None:
            return None, None
        collection, person = self._find_person_in_group(group, person_id)
        return collection, person

    @staticmethod
    def _find_person_in_group(group: dict, person_id: str):
        for collection in ("children", "leaders"):
            for person in group.get(collection, []):
                if person.get("id") == person_id:
                    return collection, person
        return None, None

    def _open_person(self, person_id: str, _role=None):
        group = self._group()
        if group is not None:
            self._open_person_in_group(group, person_id)

    def _open_person_in_group(self, group: dict, person_id: str):
        collection, person = self._find_person(person_id)
        if group is not self._group():
            collection, person = self._find_person_in_group(group, person_id)
        if group is None or person is None:
            return
        editor = PersonEditorDialog(person, str(group.get("name") or "Oddíl"), self)
        if editor.exec() != QDialog.Accepted:
            return
        if editor.delete_requested:
            group[collection] = [item for item in group.get(collection, []) if item.get("id") != person_id]
        elif editor.payload is not None:
            replacement = editor.payload
            target_collection = "leaders" if replacement.get("role") == "leader" else "children"
            group[collection] = [item for item in group.get(collection, []) if item.get("id") != person_id]
            group.setdefault(target_collection, []).append(replacement)
            _sync_person_field_schema(self.data.get("groups", []))
        self._save_and_refresh()

    def _add_person(self, role: str):
        group = self._group()
        if group is None:
            return
        person = {
            "id": os.urandom(6).hex(),
            "role": role,
            "fields": {"Jméno": "", "Příjmení": ""},
        }
        if role == "child":
            person["fields"].update({"Věk": "", "Ubytování": ""})
        editor = PersonEditorDialog(person, str(group.get("name") or "Oddíl"), self, is_new=True)
        if editor.exec() != QDialog.Accepted or editor.payload is None:
            return
        target = "leaders" if editor.payload.get("role") == "leader" else "children"
        group.setdefault(target, []).append(editor.payload)
        _sync_person_field_schema(self.data.get("groups", []))
        self._save_and_refresh()

    def _rename_group(self):
        group = self._group()
        if group is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Přejmenovat oddíl",
            "Název oddílu:",
            QLineEdit.Normal,
            str(group.get("name") or ""),
        )
        name = " ".join(name.split())
        if accepted and name:
            group["name"] = name
            self._save_and_refresh()

    def _save_and_refresh(self):
        try:
            save_groups_data(self.data)
        except OSError as error:
            QMessageBox.critical(self, "Uložení se nezdařilo", str(error))
            return
        self._refresh_overview()
        if self.current_group_id:
            self._refresh_detail()

    def _clear_all_groups(self):
        groups = self.data.get("groups", [])
        if not groups:
            QMessageBox.information(self, "Oddíly jsou prázdné", "Není co mazat.")
            return
        children = sum(len(group.get("children", [])) for group in groups)
        leaders = sum(len(group.get("leaders", [])) for group in groups)
        answer = QMessageBox.question(
            self,
            "Smazat všechny oddíly?",
            (
                "Opravdu chcete smazat všechny oddíly?\n\n"
                f"Smaže se {len(groups)} oddílů, {children} dětí a {leaders} vedoucích. "
                "Tato akce nejde vrátit zpět."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.data["groups"] = []
        self.current_group_id = None
        self.current_accommodation_name = None
        self.pages.setCurrentWidget(self.overview_page)
        self._save_and_refresh()

    def _import_excel(self):
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Importovat oddíly z Excelu",
            "",
            "Excel (*.xls *.xlsx);;Všechny soubory (*)",
        )
        if not path:
            return
        try:
            imported = parse_groups_workbook(path)
            merged, merge_stats = merge_groups_data(self.data, imported)
            save_groups_data(merged)
        except GroupsDataError as error:
            QMessageBox.critical(self, "Import se nezdařil", str(error))
            return
        except OSError as error:
            QMessageBox.critical(self, "Import se nezdařil", str(error))
            return
        self.data = merged
        self.current_group_id = None
        self.pages.setCurrentWidget(self.overview_page)
        self._refresh_overview()
        group_count = len(merged.get("groups", []))
        children = sum(len(group.get("children", [])) for group in merged.get("groups", []))
        leaders = sum(len(group.get("leaders", [])) for group in merged.get("groups", []))
        QMessageBox.information(
            self,
            "Import a sloučení dokončeno",
            (
                f"Aktuálně: {group_count} oddílů, {children} dětí a {leaders} vedoucích.\n\n"
                f"Nové osoby: {merge_stats['people_added']}\n"
                f"Aktualizované osoby: {merge_stats['people_updated']}\n"
                f"Beze změny: {merge_stats['people_unchanged']}\n"
                f"Zachované ruční záznamy: {merge_stats['people_retained']}\n\n"
                "Vlastní údaje, například telefon, zůstaly zachovány."
            ),
        )

    def _export_path(self, suggested: str):
        export_dir = get_user_data_dir("groups", "exports")
        return QFileDialog.getSaveFileName(
            self,
            "Exportovat oddíly do Excelu",
            os.path.join(export_dir, suggested),
            "Excel (*.xlsx)",
        )[0]

    def _export_all(self):
        path = self._export_path("oddily_export.xlsx")
        if not path:
            return
        self._perform_export(self.data.get("groups", []), path)

    def _export_current_group(self):
        group = self._group()
        if group is None:
            return
        safe = normalized_label(group.get("name")) or "oddil"
        path = self._export_path(f"{safe}.xlsx")
        if not path:
            return
        self._perform_export([group], path)

    def _export_accommodations(self, accommodation_name: str | None = None):
        export_groups = _accommodation_export_groups(self.data.get("groups", []), accommodation_name)
        if not export_groups:
            QMessageBox.information(self, "Ubytování je prázdné", "Není co exportovat. Nejdřív vyplň u osob položku Ubytování.")
            return
        suggested = f"ubytovani_{normalized_label(accommodation_name)}.xlsx" if accommodation_name else "ubytovani_export.xlsx"
        path = self._export_path(suggested)
        if not path:
            return
        self._perform_export(export_groups, path)

    def _perform_export(self, groups: list[dict], path: str):
        try:
            target = export_groups_workbook(groups, path)
        except GroupsDataError as error:
            QMessageBox.critical(self, "Export se nezdařil", str(error))
            return
        QMessageBox.information(self, "Export dokončen", f"Excel byl uložen:\n{target}")

    def _accommodations_print_html(self, accommodation_name: str | None = None) -> str:
        esc = lambda value: html.escape(str(value or ""))
        accommodations = _accommodation_people(self.data.get("groups", []))
        rows = [
            (name, people)
            for name, people in accommodations.items()
            if accommodation_name is None or name == accommodation_name
        ]
        pieces = [
            "<html><head><meta charset='utf-8'><style>",
            "body{font-family:'Segoe UI',Arial,sans-serif;color:#102631;font-size:10pt;}",
            "h1{font-family:Georgia,serif;color:#0b2632;font-size:23pt;margin:0 0 8px 0;}",
            "h2{font-family:Georgia,serif;color:#684819;font-size:15pt;border-bottom:2px solid #b08032;margin:16px 0 8px 0;}",
            "table{width:100%;border-collapse:collapse;margin-bottom:12px;}",
            "th{background:#0b4652;color:#fff4cf;padding:7px;text-align:left;border:1px solid #9d7a41;}",
            "td{padding:7px;border:1px solid #d4c49f;background:#fff7e4;}",
            "tr.alt td{background:#f3ead4;}",
            ".sub{color:#6f5931;margin-bottom:12px;}",
            "</style></head><body>",
            f"<h1>{'UBYTOVÁNÍ' if accommodation_name is None else esc(accommodation_name).upper()}</h1>",
            f"<div class='sub'>Sruby podle osobních karet • {sum(len(people) for _name, people in rows)} ubytovaných</div>",
        ]
        for name, people in rows:
            pieces.append(f"<h2>{esc(name)} • {len(people)} ubytovaných</h2>")
            pieces.append("<table><tr><th>Osoba</th><th>Oddíl</th><th>Věk</th><th>Pohlaví</th><th>Role</th></tr>")
            for index, item in enumerate(people):
                person = item["person"]
                class_name = " class='alt'" if index % 2 else ""
                pieces.append(
                    f"<tr{class_name}><td>{esc(person_display_name(person))}</td>"
                    f"<td>{esc(item.get('group_name'))}</td>"
                    f"<td>{esc(_person_field_by_key(person, 'Věk'))}</td>"
                    f"<td>{esc(_person_field_by_key(person, 'Pohlaví'))}</td>"
                    f"<td>{esc(item.get('role'))}</td></tr>"
                )
            pieces.append("</table>")
        pieces.append("</body></html>")
        return "".join(pieces)

    def _print_accommodations(self, accommodation_name: str | None = None):
        if not _accommodation_export_groups(self.data.get("groups", []), accommodation_name):
            QMessageBox.information(self, "Ubytování je prázdné", "Není co tisknout. Nejdřív vyplň u osob položku Ubytování.")
            return
        try:
            from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        except Exception as error:
            QMessageBox.warning(self, "Tisk není dostupný", f"Nepodařilo se načíst podporu tisku:\n{error}")
            return
        document = QTextDocument(self)
        document.setDefaultFont(QFont("Segoe UI", 10))
        document.setPageSize(QSize(595, 842))
        document.setDocumentMargin(32)
        document.setHtml(self._accommodations_print_html(accommodation_name))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Tisk ubytování")
        if dialog.exec() == QDialog.Accepted:
            document.print_(printer)
