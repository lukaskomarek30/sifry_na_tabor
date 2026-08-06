"""Pirátský sportovní den: výzvy, posádka, výsledky a celkové pořadí."""

import json
import math
import os
import unicodedata
import uuid

from PySide6.QtCore import QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_paths import get_user_data_dir
from fire_effects import FireFlicker
from groups_data import roster_entries
from sports_day_print import SportsDayPrintMixin


METRICS = {
    "time": {"label": "Čas", "unit": "sekundy nebo mm:ss"},
    "distance": {"label": "Vzdálenost", "unit": "metry"},
    "points": {"label": "Body", "unit": "body"},
}

GENDERS = {
    "M": {"singular": "Kluk", "plural": "Kluci"},
    "F": {"singular": "Holka", "plural": "Dívky"},
}


def _uid() -> str:
    return uuid.uuid4().hex[:10]


def _clean_name(value) -> str:
    """Sjednotí Unicode a mezery, ale zachová podobu jména pro zobrazení."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split())


def _name_key(value) -> str:
    """Klíč pro porovnání názvů bez ohledu na velikost písmen a nadbytečné mezery."""
    return _clean_name(value).casefold()


def _duplicate_named_item(items: list, name: str, exclude_id=None):
    key = _name_key(name)
    if not key:
        return None
    return next(
        (
            item
            for item in items
            if item.get("id") != exclude_id and _name_key(item.get("name")) == key
        ),
        None,
    )


def parse_metric_value(raw, metric: str):
    """Převede číslo nebo čas mm:ss na hodnotu vhodnou pro řazení."""
    if raw is None:
        return None
    text = str(raw).strip().replace(",", ".")
    if not text:
        return None

    try:
        if metric == "time" and ":" in text:
            parts = text.split(":")
            if len(parts) != 2:
                return None
            minutes = float(parts[0])
            seconds = float(parts[1])
            if not math.isfinite(minutes) or not math.isfinite(seconds):
                return None
            if minutes < 0 or seconds < 0 or seconds > 59.99:
                return None
            value = minutes * 60.0 + seconds
        else:
            value = float(text)
        if metric == "time" and value < 0:
            return None
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _competition_ranks(values: list) -> list:
    """Husté sdílené pořadí 1-1-2-2-3 pro seřazené hodnoty; None zůstává bez pořadí."""
    ranks = []
    previous_key = None
    current_rank = 0
    for value in values:
        if value is None:
            ranks.append(None)
            continue
        tie_key = round(float(value), 2)
        if previous_key is None or tie_key != previous_key:
            current_rank += 1
            previous_key = tie_key
        ranks.append(current_rank)
    return ranks


def _format_points_value(value) -> str:
    """Český stručný zápis celých i normalizovaných desetinných bodů."""
    try:
        number = round(float(value), 2)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def compute_event_points(event: dict, categories: list, competitors: list, results: dict) -> dict:
    """Body za husté sdílené umístění zvlášť pro každou kategorii a pohlaví."""
    event_results = results.get(event.get("id"), {}) or {}
    normalize_points = bool(event.get("_normalize_points", False))
    try:
        normalized_max = max(1.0, float(event.get("_normalized_points_max", 10.0)))
    except (TypeError, ValueError):
        normalized_max = 10.0
    points = {}
    for category in categories:
        category_id = category.get("id")
        for gender in ("M", "F"):
            rows = []
            for competitor in competitors:
                if competitor.get("category_id") != category_id or competitor.get("gender", "M") != gender:
                    continue
                raw = event_results.get(competitor.get("id"), "")
                parsed = parse_metric_value(raw, event.get("metric", "time"))
                if parsed is not None:
                    rows.append((competitor.get("id"), parsed))
            rows.sort(key=lambda item: item[1], reverse=event.get("direction") == "desc")
            count = len(rows)
            ranks = _competition_ranks([value for _competitor_id, value in rows])
            for (competitor_id, _value), rank in zip(rows, ranks):
                if normalize_points:
                    if count <= 1:
                        score = normalized_max
                    else:
                        score = normalized_max - (rank - 1) * (normalized_max - 1.0) / (count - 1)
                    score = round(max(1.0, score), 2)
                    points[competitor_id] = int(score) if score.is_integer() else score
                else:
                    points[competitor_id] = count - rank + 1
    return points


class SportsDayDialog(QDialog, SportsDayPrintMixin):
    """Kompletní desktopová verze rozhraní ze sportovni-den.jsx."""

    METRICS = METRICS
    GENDERS = GENDERS
    _parse_metric_value = staticmethod(parse_metric_value)
    _competition_ranks = staticmethod(_competition_ranks)
    _format_points_value = staticmethod(_format_points_value)

    def __init__(self, owner_window, icons_path: str):
        super().__init__(owner_window)
        self.owner_window = owner_window
        self.icons_path = icons_path
        self.data_dir = get_user_data_dir("sports_day")
        self.data_path = os.path.join(self.data_dir, "sportovni_den.json")
        self.legacy_data_path = os.path.join(self.data_dir, "plan.json")
        self._refreshing = False

        self.categories = [{"id": "none", "name": "Bez kategorie"}]
        self.competitors = []
        self.events = []
        self.results = {}
        self.normalize_points = True
        self.normalized_points_max = 10.0
        self.selected_event_id = None
        self.results_sort_mode = "alphabetical"
        self.standings_sort_mode = "alphabetical"
        self._results_order_ids = {}
        self._standings_order_ids = {}
        self._bubble_highlight = set()
        self._bubble_state = None
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setInterval(95)
        self._bubble_timer.timeout.connect(self._bubble_sort_step)

        background_path = os.path.join(self.icons_path, "sports_day_BG.png")
        if not os.path.exists(background_path):
            background_path = os.path.join(self.icons_path, "menu_BG.png")
        self.background = QPixmap(background_path) if os.path.exists(background_path) else QPixmap()
        coin_path = os.path.join(self.icons_path, "pirate_coin.png")
        self.coin_pixmap = QPixmap(coin_path) if os.path.exists(coin_path) else QPixmap()
        self.fire_flicker = FireFlicker(
            self,
            (
                (0.145, 0.391, 0.44),
                (0.308, 0.584, 0.34),
                (0.488, 0.585, 0.40),
                (0.968, 0.466, 0.24),
                (0.946, 0.831, 1.20),
            ),
        )

        self._load_data()
        self.setWindowTitle("Pirátský sportovní den")
        self.resize(1280, 790)
        self.setMinimumSize(980, 650)
        self.setStyleSheet(self._style_sheet())
        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Vzhled a základní rozložení
    # ------------------------------------------------------------------

    def _style_sheet(self) -> str:
        return """
            QDialog, QWidget#sportsRoot, QWidget#sportsPage {
                background: transparent;
                color: #ead8b3;
            }
            QLabel {
                color: #ead8b3;
                background: transparent;
                font-family: Georgia;
            }
            QFrame#sportsPanel {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(8, 38, 48, 112),
                    stop:0.55 rgba(3, 21, 30, 80),
                    stop:1 rgba(3, 13, 21, 58)
                );
                border: 1px solid rgba(225, 179, 91, 190);
                border-radius: 15px;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                color: #f0e2c0;
                background-color: rgba(2, 14, 22, 124);
                border: 1px solid rgba(196, 151, 76, 190);
                border-radius: 9px;
                padding: 6px;
                selection-background-color: #176c76;
                selection-color: #fff0bd;
                font-size: 12px;
            }
            QTableWidget {
                color: #f0e2c0;
                background-color: rgba(2, 13, 21, 34);
                border: 1px solid rgba(196, 151, 76, 175);
                border-radius: 11px;
                padding: 5px;
                selection-background-color: rgba(23, 108, 118, 190);
                selection-color: #fff0bd;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus, QTableWidget:focus {
                border: 2px solid #d2a451;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                color: #f0e2c0;
                background-color: #071720;
                border: 1px solid #a47a3e;
                selection-background-color: #176c76;
            }
            QTableWidget {
                gridline-color: rgba(161, 124, 63, 80);
                alternate-background-color: rgba(12, 47, 57, 58);
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
                background-color: transparent;
            }
            QHeaderView::section {
                color: #f4dea4;
                background-color: rgba(7, 42, 53, 148);
                border: none;
                border-right: 1px solid rgba(200, 154, 76, 100);
                border-bottom: 1px solid #a47a3e;
                padding: 8px;
                font-family: Georgia;
                font-weight: bold;
            }
            QPushButton {
                color: #f4dea4;
                background-color: rgba(13, 64, 75, 202);
                border: 1px solid rgba(220, 174, 86, 220);
                border-radius: 10px;
                padding: 8px 13px;
                font-family: Georgia;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #fff0bd;
                background-color: rgba(20, 86, 96, 245);
                border: 2px solid #f3d79a;
            }
            QPushButton#dangerButton {
                color: #f0c2ae;
                background-color: rgba(95, 30, 36, 168);
                border-color: #a95a55;
                padding: 5px 8px;
                min-width: 92px;
                font-size: 10px;
            }
            QPushButton#quietButton {
                color: #d9c697;
                background-color: rgba(4, 18, 27, 148);
            }
            QPushButton#pirateNameButton {
                color: #f2ddb0;
                background-color: rgba(8, 39, 48, 118);
                border: 1px solid rgba(190, 146, 72, 120);
                border-radius: 8px;
                padding: 6px 10px;
                text-align: left;
            }
            QPushButton#pirateNameButton:hover {
                color: #fff0bd;
                background-color: rgba(18, 82, 89, 205);
                border-color: #e0b15b;
            }
            QFrame#pirateDetail {
                background-color: rgba(4, 22, 31, 168);
                border: 1px solid rgba(214, 164, 77, 190);
                border-radius: 11px;
            }
            QPushButton#bubbleButton {
                color: #fff0bd;
                background-color: rgba(119, 75, 17, 205);
                border-color: #efc66c;
            }
            QPushButton#bubbleButton:disabled {
                color: #bda977;
                background-color: rgba(77, 59, 31, 150);
            }
            QPushButton#printButton {
                color: #fff3c6;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(14, 81, 91, 238),
                    stop:1 rgba(126, 79, 19, 235)
                );
                border: 1px solid #efc66c;
                border-radius: 11px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton#printButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(20, 104, 113, 250),
                    stop:1 rgba(155, 99, 27, 250)
                );
                border: 2px solid #ffe09a;
            }
            QTabWidget::pane {
                background: transparent;
                border: none;
                top: -1px;
            }
            QTabBar::tab {
                color: #cbb98f;
                background-color: rgba(4, 25, 34, 132);
                border: 1px solid rgba(141, 105, 53, 150);
                border-bottom: none;
                padding: 11px 24px;
                min-width: 125px;
                font-family: Georgia;
                font-size: 13px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                color: #fff0bd;
                background-color: rgba(18, 82, 89, 214);
                border-color: #d2a451;
            }
            QTabBar::tab:hover:!selected {
                color: #f3d79a;
                background-color: rgba(10, 52, 63, 186);
            }
            QStackedWidget {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(3, 14, 22, 105);
                width: 11px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #9b7a45;
                min-height: 35px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QCheckBox {
                color: #ead8b3;
                spacing: 8px;
                font-family: Georgia;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border: 1px solid #b88b45;
                border-radius: 4px;
                background: rgba(2, 14, 22, 175);
            }
            QCheckBox::indicator:checked {
                background: #187580;
                border: 2px solid #f0ca76;
            }
        """

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        scaled = QPixmap()
        x = y = 0
        if not self.background.isNull():
            scaled = self.background.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = max(0, (scaled.width() - self.width()) // 2)
            y = max(0, (scaled.height() - self.height()) // 2)
            painter.drawPixmap(self.rect(), scaled, QRect(x, y, self.width(), self.height()))
        else:
            painter.fillRect(self.rect(), QColor("#06131b"))
        painter.fillRect(self.rect(), QColor(1, 8, 13, 26))
        if not scaled.isNull():
            self.fire_flicker.paint(painter, scaled.width(), scaled.height(), x, y)

    def _build_ui(self):
        root_widget = QWidget(self)
        root_widget.setObjectName("sportsRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 16, 22, 18)
        outer.addWidget(root_widget)

        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(14)

        icon_label = QLabel(root_widget)
        icon_label.setFixedSize(76, 76)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_path = os.path.join(self.icons_path, "semafor.png")
        icon_pixmap = QPixmap(icon_path) if os.path.exists(icon_path) else QPixmap()
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap.scaled(70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(icon_label)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = QLabel("PIRÁTSKÝ SPORTOVNÍ DEN", root_widget)
        title.setStyleSheet("color: #f4dea4; font-size: 27px; font-weight: bold; letter-spacing: 2px;")
        titles.addWidget(title)
        subtitle = QLabel("Výzvy, posádka a kořist na jedné mapě", root_widget)
        subtitle.setStyleSheet("color: #d9c697; font-size: 13px; font-style: italic;")
        titles.addWidget(subtitle)
        titles.addStretch(1)
        header.addLayout(titles, 1)

        self.stats_label = QLabel(root_widget)
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.stats_label.setStyleSheet(
            "color: #f0d19a; background: rgba(3,18,27,88); border: 1px solid rgba(192,145,67,185); "
            "border-radius: 12px; padding: 9px 14px; font-weight: bold;"
        )
        header.addWidget(self.stats_label)
        root.addLayout(header)

        self.tabs = QTabWidget(root_widget)
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._build_events_page(), "VÝZVY")
        self.tabs.addTab(self._build_competitors_page(), "POSÁDKA")
        self.tabs.addTab(self._build_results_page(), "ŽEBŘÍČEK")
        self.tabs.addTab(self._build_standings_page(), "POKLAD")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.setAutoFillBackground(False)
        self.tabs.setAttribute(Qt.WA_TranslucentBackground, True)
        tab_stack = self.tabs.findChild(QStackedWidget)
        if tab_stack is not None:
            tab_stack.setAutoFillBackground(False)
            tab_stack.setAttribute(Qt.WA_TranslucentBackground, True)
            stack_palette = tab_stack.palette()
            stack_palette.setColor(QPalette.Window, QColor(0, 0, 0, 0))
            tab_stack.setPalette(stack_palette)
        self.tabs.setMinimumHeight(420)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        self.save_status = QLabel("Ukládá se automaticky", root_widget)
        self.save_status.setStyleSheet("color: rgba(234,216,179,170); font-size: 11px;")
        bottom.addWidget(self.save_status)
        bottom.addStretch(1)
        print_button = QPushButton("TISK VÝSLEDKŮ", root_widget)
        print_button.setObjectName("printButton")
        print_button.setFixedHeight(38)
        if not self.coin_pixmap.isNull():
            print_button.setIcon(QIcon(self.coin_pixmap))
            print_button.setIconSize(QSize(25, 25))
        print_button.clicked.connect(self._show_print_options)
        bottom.addWidget(print_button)
        close_button = QPushButton("ZPĚT NA PALUBU", root_widget)
        close_button.setObjectName("quietButton")
        close_button.clicked.connect(self._go_home)
        bottom.addWidget(close_button)
        root.addLayout(bottom)

    def _new_page(self):
        page = QWidget(self)
        page.setObjectName("sportsPage")
        page.setAutoFillBackground(False)
        page.setAttribute(Qt.WA_TranslucentBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        return page, layout

    def _new_panel(self, title_text: str):
        panel = QFrame(self)
        panel.setObjectName("sportsPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(13, 11, 13, 13)
        layout.setSpacing(8)
        title = QLabel(title_text, panel)
        title.setStyleSheet("color: #f3d79a; font-size: 14px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(title)
        return panel, layout

    @staticmethod
    def _field(label: str, widget: QWidget, parent: QWidget):
        box = QVBoxLayout()
        box.setSpacing(4)
        label_widget = QLabel(label, parent)
        label_widget.setStyleSheet("color: #cdbb91; font-size: 11px; font-weight: bold;")
        box.addWidget(label_widget)
        box.addWidget(widget)
        return box

    def _configure_table(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(39)
        table.setShowGrid(False)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setIconSize(QSize(25, 25))
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

    # ------------------------------------------------------------------
    # Výzvy
    # ------------------------------------------------------------------

    def _build_events_page(self):
        page, layout = self._new_page()
        panel, panel_layout = self._new_panel("NOVÁ VÝZVA")
        form = QHBoxLayout()
        form.setSpacing(9)
        self.event_name_edit = QLineEdit(panel)
        self.event_name_edit.setPlaceholderText("Například Běh na 60 m")
        form.addLayout(self._field("Název výzvy", self.event_name_edit, panel), 3)
        self.event_metric_combo = QComboBox(panel)
        for key, meta in METRICS.items():
            self.event_metric_combo.addItem(meta["label"], key)
        form.addLayout(self._field("Co se měří", self.event_metric_combo, panel), 2)
        self.event_direction_combo = QComboBox(panel)
        self.event_direction_combo.addItem("Nejnižší hodnota", "asc")
        self.event_direction_combo.addItem("Nejvyšší hodnota", "desc")
        form.addLayout(self._field("Vyhrává", self.event_direction_combo, panel), 2)
        add_button = QPushButton("+  PŘIDAT VÝZVU", panel)
        add_button.clicked.connect(self._add_event)
        self.event_name_edit.returnPressed.connect(self._add_event)
        form.addWidget(add_button, 0, Qt.AlignBottom)
        self.event_cards_print_button = QPushButton("TISK KARTIČEK A6", panel)
        self.event_cards_print_button.setObjectName("printButton")
        self.event_cards_print_button.clicked.connect(self._show_event_cards_print)
        form.addWidget(self.event_cards_print_button, 0, Qt.AlignBottom)
        panel_layout.addLayout(form)
        layout.addWidget(panel)

        self.events_empty = QLabel("Zatím žádné výzvy. Přidej první výše.", page)
        self.events_empty.setAlignment(Qt.AlignCenter)
        self.events_empty.setStyleSheet("color: #cbb98f; font-size: 13px; padding: 18px;")
        self.events_empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.events_empty, 1)

        self.events_table = QTableWidget(0, 4, page)
        self.events_table.setHorizontalHeaderLabels(("VÝZVA", "MĚŘÍ SE", "VYHRÁVÁ", ""))
        self._configure_table(self.events_table)
        header = self.events_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.events_table.itemChanged.connect(self._event_item_changed)
        self.events_table.setMinimumHeight(180)
        self.events_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.events_table, 1)
        return page

    # ------------------------------------------------------------------
    # Posádka
    # ------------------------------------------------------------------

    def _build_competitors_page(self):
        page, layout = self._new_page()
        top = QHBoxLayout()
        top.setSpacing(10)

        categories_panel, categories_layout = self._new_panel("VĚKOVÉ KATEGORIE")
        add_category = QHBoxLayout()
        self.category_name_edit = QLineEdit(categories_panel)
        self.category_name_edit.setPlaceholderText("Například 9–11 let")
        category_add_button = QPushButton("+", categories_panel)
        category_add_button.setFixedWidth(48)
        category_add_button.clicked.connect(self._add_category)
        self.category_name_edit.returnPressed.connect(self._add_category)
        add_category.addWidget(self.category_name_edit, 1)
        add_category.addWidget(category_add_button)
        categories_layout.addLayout(add_category)
        self.categories_table = QTableWidget(0, 2, categories_panel)
        self.categories_table.setHorizontalHeaderLabels(("KATEGORIE", ""))
        self._configure_table(self.categories_table)
        self.categories_table.setMaximumHeight(165)
        self.categories_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.categories_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.categories_table.itemChanged.connect(self._category_item_changed)
        categories_layout.addWidget(self.categories_table)
        top.addWidget(categories_panel, 2)

        add_panel, add_layout = self._new_panel("NOVÝ PIRÁT")
        competitor_form = QHBoxLayout()
        competitor_form.setSpacing(9)
        self.competitor_name_edit = QLineEdit(add_panel)
        self.competitor_name_edit.setPlaceholderText("Například Tomáš Novák")
        competitor_form.addLayout(self._field("Jméno piráta", self.competitor_name_edit, add_panel), 3)
        self.competitor_category_combo = QComboBox(add_panel)
        competitor_form.addLayout(self._field("Kategorie", self.competitor_category_combo, add_panel), 2)
        self.competitor_gender_combo = QComboBox(add_panel)
        self.competitor_gender_combo.addItem("Kluci", "M")
        self.competitor_gender_combo.addItem("Dívky", "F")
        competitor_form.addLayout(self._field("Pohlaví", self.competitor_gender_combo, add_panel), 1)
        competitor_add_button = QPushButton("+  PŘIDAT", add_panel)
        competitor_add_button.clicked.connect(self._add_competitor)
        self.competitor_name_edit.returnPressed.connect(self._add_competitor)
        competitor_form.addWidget(competitor_add_button, 0, Qt.AlignBottom)
        add_layout.addLayout(competitor_form)
        add_layout.addStretch(1)
        top.addWidget(add_panel, 3, Qt.AlignTop)
        layout.addLayout(top)

        filters_panel, filters_layout = self._new_panel("HLEDÁNÍ A FILTRY")
        filters = QHBoxLayout()
        self.competitor_search_edit = QLineEdit(filters_panel)
        self.competitor_search_edit.setPlaceholderText("Hledej piráta podle jména…")
        self.competitor_filter_category = QComboBox(filters_panel)
        self.competitor_filter_gender = QComboBox(filters_panel)
        self.competitor_filter_gender.addItem("Všichni", "all")
        self.competitor_filter_gender.addItem("Kluci", "M")
        self.competitor_filter_gender.addItem("Dívky", "F")
        filters.addLayout(self._field("Hledat", self.competitor_search_edit, filters_panel), 3)
        filters.addLayout(self._field("Kategorie", self.competitor_filter_category, filters_panel), 2)
        filters.addLayout(self._field("Pohlaví", self.competitor_filter_gender, filters_panel), 1)
        filters_layout.addLayout(filters)
        layout.addWidget(filters_panel)

        self.competitors_empty = QLabel("Posádka je zatím prázdná. Přidej prvního piráta výše.", page)
        self.competitors_empty.setAlignment(Qt.AlignCenter)
        self.competitors_empty.setStyleSheet("color: #cbb98f; font-size: 13px; padding: 12px;")
        layout.addWidget(self.competitors_empty)

        self.competitors_table = QTableWidget(0, 5, page)
        self.competitors_table.setHorizontalHeaderLabels(("PIRÁT", "KATEGORIE", "POHLAVÍ", "VÝSLEDKY", ""))
        self._configure_table(self.competitors_table)
        comp_header = self.competitors_table.horizontalHeader()
        comp_header.setSectionResizeMode(0, QHeaderView.Stretch)
        comp_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        comp_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        comp_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        comp_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.competitors_table.cellClicked.connect(self._competitor_table_clicked)
        self.competitors_table.setMinimumHeight(185)
        self.competitors_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.competitors_table, 1)

        self.competitor_search_edit.textChanged.connect(self._refresh_competitors_table)
        self.competitor_filter_category.currentIndexChanged.connect(self._refresh_competitors_table)
        self.competitor_filter_gender.currentIndexChanged.connect(self._refresh_competitors_table)
        return page

    # ------------------------------------------------------------------
    # Žebříček
    # ------------------------------------------------------------------

    def _build_results_page(self):
        page, layout = self._new_page()
        controls_panel, controls_layout = self._new_panel("VÝSLEDKY VÝZVY")
        controls = QHBoxLayout()
        self.results_event_combo = QComboBox(controls_panel)
        self.results_view_combo = QComboBox(controls_panel)
        self.results_view_combo.addItem("Podle kategorií", "category")
        self.results_view_combo.addItem("Celkově", "overall")
        self.results_gender_combo = QComboBox(controls_panel)
        self.results_gender_combo.addItem("Všichni", "all")
        self.results_gender_combo.addItem("Kluci", "M")
        self.results_gender_combo.addItem("Dívky", "F")
        controls.addLayout(self._field("Vyber výzvu", self.results_event_combo, controls_panel), 3)
        controls.addLayout(self._field("Zobrazení", self.results_view_combo, controls_panel), 2)
        controls.addLayout(self._field("Pohlaví", self.results_gender_combo, controls_panel), 1)
        controls_layout.addLayout(controls)
        result_sorting = QHBoxLayout()
        self.results_sort_status = QLabel("Výchozí pořadí: abecedně", controls_panel)
        self.results_sort_status.setStyleSheet("color: #d6c495; font-size: 11px;")
        result_sorting.addWidget(self.results_sort_status)
        result_sorting.addStretch(1)
        results_alpha_button = QPushButton("ABECEDNĚ", controls_panel)
        results_alpha_button.setObjectName("quietButton")
        results_alpha_button.clicked.connect(self._reset_results_sort)
        result_sorting.addWidget(results_alpha_button)
        self.results_bubble_button = QPushButton("SEŘADIT", controls_panel)
        self.results_bubble_button.setObjectName("bubbleButton")
        self.results_bubble_button.clicked.connect(self._start_results_bubble_sort)
        result_sorting.addWidget(self.results_bubble_button)
        controls_layout.addLayout(result_sorting)
        layout.addWidget(controls_panel)

        self.results_hint = QLabel(page)
        self.results_hint.setStyleSheet("color: #d6c495; font-size: 12px; padding-left: 4px;")
        layout.addWidget(self.results_hint)

        self.results_table = QTableWidget(0, 7, page)
        self.results_table.setHorizontalHeaderLabels(
            ("POŘADÍ", "PIRÁT", "KATEGORIE", "SKUPINA", "VÝSLEDEK", "JEDNOTKA", "MINCE")
        )
        self._configure_table(self.results_table)
        result_header = self.results_table.horizontalHeader()
        result_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(1, QHeaderView.Stretch)
        result_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.results_table.setMinimumHeight(210)
        self.results_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.results_table, 1)

        self.results_event_combo.currentIndexChanged.connect(self._results_event_changed)
        self.results_view_combo.currentIndexChanged.connect(self._reset_results_sort)
        self.results_gender_combo.currentIndexChanged.connect(self._reset_results_sort)
        return page

    # ------------------------------------------------------------------
    # Poklad
    # ------------------------------------------------------------------

    def _build_standings_page(self):
        page, layout = self._new_page()
        info_panel, info_layout = self._new_panel("PRAVIDLA KOŘISTI")
        explanation = QLabel(
            "Za každou výzvu získá pirát mince podle umístění ve své věkové kategorii a pohlaví. "
            "První místo získá nejvíc mincí, poslední jednu. Kořist ze všech výzev se sčítá.",
            info_panel,
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #d6c495; font-size: 12px;")
        info_layout.addWidget(explanation)
        normalization_row = QHBoxLayout()
        normalization_row.setContentsMargins(0, 0, 0, 0)
        normalization_row.setSpacing(10)
        self.normalize_points_checkbox = QCheckBox(
            "Normalizovat body podle velikosti kategorie",
            info_panel,
        )
        self.normalize_points_checkbox.setChecked(self.normalize_points)
        self.normalize_points_checkbox.setToolTip(
            "Zapnuto: každá skupina má stejnou zvolenou stupnici až k 1 bodu. "
            "Vypnuto: používá se původní vzorec počet soutěžících − pořadí + 1."
        )
        self.normalize_points_checkbox.toggled.connect(self._normalization_changed)
        normalization_row.addWidget(self.normalize_points_checkbox, 1)

        normalization_row.addWidget(QLabel("Maximum za 1. místo:", info_panel))
        self.normalized_points_max_spinbox = QDoubleSpinBox(info_panel)
        self.normalized_points_max_spinbox.setRange(1.0, 1000.0)
        self.normalized_points_max_spinbox.setDecimals(1)
        self.normalized_points_max_spinbox.setSingleStep(1.0)
        self.normalized_points_max_spinbox.setSuffix(" bodů")
        self.normalized_points_max_spinbox.setKeyboardTracking(False)
        self.normalized_points_max_spinbox.setMinimumWidth(115)
        self.normalized_points_max_spinbox.setValue(self.normalized_points_max)
        self.normalized_points_max_spinbox.setEnabled(self.normalize_points)
        self.normalized_points_max_spinbox.setToolTip(
            "Počet bodů za první místo při zapnuté normalizaci. Poslední místo získá 1 bod."
        )
        self.normalized_points_max_spinbox.valueChanged.connect(self._normalized_points_max_changed)
        normalization_row.addWidget(self.normalized_points_max_spinbox)
        info_layout.addLayout(normalization_row)
        layout.addWidget(info_panel)

        controls = QHBoxLayout()
        controls.addStretch(1)
        self.standings_view_combo = QComboBox(page)
        self.standings_view_combo.addItem("Podle kategorií", "category")
        self.standings_view_combo.addItem("Celkově", "overall")
        self.standings_gender_combo = QComboBox(page)
        self.standings_gender_combo.addItem("Všichni", "all")
        self.standings_gender_combo.addItem("Kluci", "M")
        self.standings_gender_combo.addItem("Dívky", "F")
        controls.addWidget(QLabel("Zobrazení:", page))
        controls.addWidget(self.standings_view_combo)
        controls.addWidget(QLabel("Pohlaví:", page))
        controls.addWidget(self.standings_gender_combo)
        layout.addLayout(controls)

        standings_sorting = QHBoxLayout()
        self.standings_sort_status = QLabel("Výchozí pořadí: abecedně", page)
        self.standings_sort_status.setStyleSheet("color: #d6c495; font-size: 11px;")
        standings_sorting.addWidget(self.standings_sort_status)
        standings_sorting.addStretch(1)
        standings_alpha_button = QPushButton("ABECEDNĚ", page)
        standings_alpha_button.setObjectName("quietButton")
        standings_alpha_button.clicked.connect(self._reset_standings_sort)
        standings_sorting.addWidget(standings_alpha_button)
        self.standings_bubble_button = QPushButton("SEŘADIT", page)
        self.standings_bubble_button.setObjectName("bubbleButton")
        self.standings_bubble_button.clicked.connect(self._start_standings_bubble_sort)
        standings_sorting.addWidget(self.standings_bubble_button)
        layout.addLayout(standings_sorting)

        self.standings_table = QTableWidget(0, 6, page)
        self.standings_table.setHorizontalHeaderLabels(
            ("POŘADÍ", "PIRÁT", "KATEGORIE", "SKUPINA", "MINCE", "PŘEHLED VÝZEV")
        )
        self._configure_table(self.standings_table)
        standings_header = self.standings_table.horizontalHeader()
        standings_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        standings_header.setSectionResizeMode(1, QHeaderView.Stretch)
        standings_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        standings_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        standings_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        standings_header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.standings_table.setMinimumHeight(220)
        self.standings_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.standings_table, 1)

        self.standings_view_combo.currentIndexChanged.connect(self._reset_standings_sort)
        self.standings_gender_combo.currentIndexChanged.connect(self._reset_standings_sort)
        return page

    # ------------------------------------------------------------------
    # Datový model a persistence
    # ------------------------------------------------------------------

    def _load_data(self):
        loaded = None
        for path in (self.data_path, self.legacy_data_path):
            try:
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as source:
                        candidate = json.load(source)
                    if isinstance(candidate, dict):
                        loaded = candidate
                        break
            except Exception:
                continue
        if not loaded:
            return

        if isinstance(loaded.get("categories"), list):
            categories = [item for item in loaded["categories"] if isinstance(item, dict)]
            if not any(item.get("id") == "none" for item in categories):
                categories.insert(0, {"id": "none", "name": "Bez kategorie"})
            self.categories = categories
            self.competitors = [item for item in loaded.get("competitors", []) if isinstance(item, dict)]
            self.events = [item for item in loaded.get("events", []) if isinstance(item, dict)]
            self.results = loaded.get("results", {}) if isinstance(loaded.get("results"), dict) else {}
            self.selected_event_id = loaded.get("selected_event_id")
            settings = loaded.get("settings", {}) if isinstance(loaded.get("settings"), dict) else {}
            self.normalize_points = bool(settings.get("normalize_points", True))
            try:
                self.normalized_points_max = max(1.0, float(settings.get("normalized_points_max", 10.0)))
            except (TypeError, ValueError):
                self.normalized_points_max = 10.0
            return

        # Migrace jednoduchého plánovače z předchozí verze.
        disciplines = loaded.get("disciplines") or []
        self.events = [
            {"id": _uid(), "name": str(name), "metric": "points", "direction": "desc"}
            for name in disciplines
            if str(name or "").strip()
        ]
        if self.events:
            self.selected_event_id = self.events[0]["id"]

    def _save_data(self):
        payload = {
            "version": 3,
            "categories": self.categories,
            "competitors": self.competitors,
            "events": self.events,
            "results": self.results,
            "selected_event_id": self.selected_event_id,
            "settings": {
                "normalize_points": self.normalize_points,
                "normalized_points_max": self.normalized_points_max,
            },
        }
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            temporary = self.data_path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as target:
                json.dump(payload, target, ensure_ascii=False, indent=2)
            os.replace(temporary, self.data_path)
            if hasattr(self, "save_status"):
                self.save_status.setText("Uloženo automaticky")
        except Exception as error:
            if hasattr(self, "save_status"):
                self.save_status.setText("Uložení se nezdařilo")
            print(f"Sportovní den: chyba ukládání: {error}")

    def _category_name(self, category_id: str) -> str:
        for category in self.categories:
            if category.get("id") == category_id:
                return str(category.get("name") or "")
        return "Bez kategorie"

    def _event_by_id(self, event_id: str):
        return next((event for event in self.events if event.get("id") == event_id), None)

    def _event_points(self, event: dict) -> dict:
        scoring_event = dict(event or {})
        scoring_event["_normalize_points"] = self.normalize_points
        scoring_event["_normalized_points_max"] = self.normalized_points_max
        return compute_event_points(scoring_event, self.categories, self.competitors, self.results)

    def _normalization_changed(self, checked: bool):
        if hasattr(self, "normalized_points_max_spinbox"):
            self.normalized_points_max_spinbox.setEnabled(bool(checked))
        if self._refreshing:
            return
        self.normalize_points = bool(checked)
        self._save_data()
        self._reset_results_sort(refresh=False)
        self._reset_standings_sort(refresh=False)
        self._refresh_results_table()
        self._refresh_standings_table()

    def _normalized_points_max_changed(self, value: float):
        if self._refreshing:
            return
        self.normalized_points_max = max(1.0, float(value))
        self._save_data()
        self._reset_results_sort(refresh=False)
        self._reset_standings_sort(refresh=False)
        self._refresh_results_table()
        self._refresh_standings_table()

    def _competitor_by_id(self, competitor_id: str):
        return next((item for item in self.competitors if item.get("id") == competitor_id), None)

    def _duplicate_competitor(self, name: str, category_id: str, exclude_id=None):
        key = _name_key(name)
        if not key:
            return None
        return next(
            (
                competitor
                for competitor in self.competitors
                if competitor.get("id") != exclude_id
                and competitor.get("category_id", "none") == category_id
                and _name_key(competitor.get("name")) == key
            ),
            None,
        )

    def _fill_combo(self, combo: QComboBox, values, selected=None, include_all=None):
        current = combo.currentData() if selected is None else selected
        combo.blockSignals(True)
        combo.clear()
        if include_all is not None:
            combo.addItem(include_all, "all")
        for label, value in values:
            combo.addItem(str(label), value)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else (0 if combo.count() else -1))
        combo.blockSignals(False)

    def refresh_all(self):
        self._refreshing = True
        try:
            self._refresh_stats()
            self._refresh_events_table()
            self._refresh_categories_table()
            self._refresh_category_combos()
            self._refresh_roster_completer()
            self._refresh_competitors_table()
            self._refresh_results_controls()
            self._refresh_results_table()
            self._refresh_standings_table()
        finally:
            self._refreshing = False

    def _refresh_stats(self):
        result_count = sum(
            1
            for event_results in self.results.values()
            if isinstance(event_results, dict)
            for value in event_results.values()
            if str(value or "").strip()
        )
        self.stats_label.setText(
            f"VÝZVY  {len(self.events)}   •   POSÁDKA  {len(self.competitors)}   •   VÝSLEDKY  {result_count}"
        )

    # ------------------------------------------------------------------
    # CRUD: výzvy
    # ------------------------------------------------------------------

    def _add_event(self):
        name = _clean_name(self.event_name_edit.text())
        if not name:
            self.event_name_edit.setFocus()
            return
        if _duplicate_named_item(self.events, name) is not None:
            QMessageBox.warning(
                self,
                "Duplicitní výzva",
                f"Výzva „{name}“ už existuje. Zvol pro disciplínu jiný název.",
            )
            self.event_name_edit.setFocus()
            self.event_name_edit.selectAll()
            return
        event = {
            "id": _uid(),
            "name": name,
            "metric": self.event_metric_combo.currentData() or "time",
            "direction": self.event_direction_combo.currentData() or "asc",
        }
        self.events.append(event)
        if not self.selected_event_id:
            self.selected_event_id = event["id"]
        self.event_name_edit.clear()
        self._save_data()
        self.refresh_all()

    def _remove_event(self, event_id: str):
        self.events = [event for event in self.events if event.get("id") != event_id]
        self.results.pop(event_id, None)
        if self.selected_event_id == event_id:
            self.selected_event_id = self.events[0]["id"] if self.events else None
        self._save_data()
        self.refresh_all()

    def _update_event(self, event_id: str, key: str, value):
        if self._refreshing:
            return
        event = self._event_by_id(event_id)
        if event is None:
            return
        if key == "name":
            name = _clean_name(value)
            if not name:
                self.refresh_all()
                return
            if _duplicate_named_item(self.events, name, event_id) is not None:
                QMessageBox.warning(
                    self,
                    "Duplicitní výzva",
                    f"Výzva „{name}“ už existuje. Původní název byl obnoven.",
                )
                self.refresh_all()
                return
            value = name
        event[key] = value
        self._save_data()
        self.refresh_all()

    def _event_item_changed(self, item: QTableWidgetItem):
        if item.column() == 0:
            self._update_event(item.data(Qt.UserRole), "name", item.text())

    def _refresh_events_table(self):
        self.events_table.blockSignals(True)
        self.events_table.setRowCount(len(self.events))
        for row, event in enumerate(self.events):
            name = QTableWidgetItem(str(event.get("name") or ""))
            name.setData(Qt.UserRole, event.get("id"))
            self.events_table.setItem(row, 0, name)

            metric = QComboBox(self.events_table)
            for key, meta in METRICS.items():
                metric.addItem(meta["label"], key)
            metric.setCurrentIndex(max(0, metric.findData(event.get("metric", "time"))))
            metric.currentIndexChanged.connect(
                lambda _index, event_id=event.get("id"), widget=metric: self._update_event(
                    event_id, "metric", widget.currentData()
                )
            )
            self.events_table.setCellWidget(row, 1, metric)

            direction = QComboBox(self.events_table)
            direction.addItem("Nejnižší", "asc")
            direction.addItem("Nejvyšší", "desc")
            direction.setCurrentIndex(max(0, direction.findData(event.get("direction", "asc"))))
            direction.currentIndexChanged.connect(
                lambda _index, event_id=event.get("id"), widget=direction: self._update_event(
                    event_id, "direction", widget.currentData()
                )
            )
            self.events_table.setCellWidget(row, 2, direction)

            remove = QPushButton("ODSTRANIT", self.events_table)
            remove.setObjectName("dangerButton")
            remove.setMinimumWidth(102)
            remove.setFixedHeight(30)
            remove.clicked.connect(lambda _checked=False, event_id=event.get("id"): self._remove_event(event_id))
            self.events_table.setCellWidget(row, 3, remove)
        self.events_table.blockSignals(False)
        self.events_empty.setVisible(not self.events)
        self.events_table.setVisible(bool(self.events))
        self.events_table.setMinimumHeight(180)
        self.event_cards_print_button.setEnabled(bool(self.events))

    # ------------------------------------------------------------------
    # CRUD: kategorie a posádka
    # ------------------------------------------------------------------

    def _add_category(self):
        name = _clean_name(self.category_name_edit.text())
        if not name:
            self.category_name_edit.setFocus()
            return
        if _duplicate_named_item(self.categories, name) is not None:
            QMessageBox.warning(
                self,
                "Duplicitní kategorie",
                f"Kategorie „{name}“ už existuje. Zvol jiný název.",
            )
            self.category_name_edit.setFocus()
            self.category_name_edit.selectAll()
            return
        self.categories.append({"id": _uid(), "name": name})
        self.category_name_edit.clear()
        self._save_data()
        self.refresh_all()

    def _remove_category(self, category_id: str):
        if category_id == "none":
            return
        destination_keys = {
            _name_key(competitor.get("name"))
            for competitor in self.competitors
            if competitor.get("category_id") == "none"
        }
        moving_names = set()
        collisions = []
        for competitor in self.competitors:
            if competitor.get("category_id") != category_id:
                continue
            key = _name_key(competitor.get("name"))
            if key in destination_keys or key in moving_names:
                collisions.append(_clean_name(competitor.get("name")))
            moving_names.add(key)
        if collisions:
            names = ", ".join(sorted(set(collisions), key=str.casefold))
            QMessageBox.warning(
                self,
                "Kategorii nelze odstranit",
                "Přesunem pirátů do kategorie „Bez kategorie“ by vznikla duplicitní jména: "
                f"{names}. Nejdříve piráty přejmenuj nebo přesuň.",
            )
            return
        self.categories = [category for category in self.categories if category.get("id") != category_id]
        for competitor in self.competitors:
            if competitor.get("category_id") == category_id:
                competitor["category_id"] = "none"
        self._save_data()
        self.refresh_all()

    def _category_item_changed(self, item: QTableWidgetItem):
        if self._refreshing or item.column() != 0:
            return
        category_id = item.data(Qt.UserRole)
        name = _clean_name(item.text())
        if category_id == "none" or not name:
            self.refresh_all()
            return
        if _duplicate_named_item(self.categories, name, category_id) is not None:
            QMessageBox.warning(
                self,
                "Duplicitní kategorie",
                f"Kategorie „{name}“ už existuje. Původní název byl obnoven.",
            )
            self.refresh_all()
            return
        for category in self.categories:
            if category.get("id") == category_id:
                category["name"] = name
                break
        self._save_data()
        self.refresh_all()

    def _refresh_categories_table(self):
        self.categories_table.blockSignals(True)
        self.categories_table.setRowCount(len(self.categories))
        for row, category in enumerate(self.categories):
            name = QTableWidgetItem(str(category.get("name") or ""))
            name.setData(Qt.UserRole, category.get("id"))
            if category.get("id") == "none":
                name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            self.categories_table.setItem(row, 0, name)
            if category.get("id") != "none":
                remove = QPushButton("×", self.categories_table)
                remove.setObjectName("dangerButton")
                remove.setFixedWidth(36)
                remove.clicked.connect(
                    lambda _checked=False, category_id=category.get("id"): self._remove_category(category_id)
                )
                self.categories_table.setCellWidget(row, 1, remove)
        self.categories_table.blockSignals(False)

    def _refresh_category_combos(self):
        values = [(category.get("name"), category.get("id")) for category in self.categories]
        self._fill_combo(self.competitor_category_combo, values)
        self._fill_combo(self.competitor_filter_category, values, include_all="Všechny kategorie")

    def _refresh_roster_completer(self):
        """Našeptává osoby importované v modulu Oddíly a po výběru vloží čisté jméno."""
        if not hasattr(self, "competitor_name_edit"):
            return
        previous = getattr(self, "_roster_completer", None)
        if previous is not None:
            previous.setWidget(None)
            previous.deleteLater()

        labels = []
        self._roster_completion_names = {}
        for entry in roster_entries():
            label = f"{entry['name']}  —  {entry['group_name']} • {entry['role']}"
            if label in self._roster_completion_names:
                label += f" • {len(labels) + 1}"
            labels.append(label)
            self._roster_completion_names[label] = entry["name"]
        completer = QCompleter(labels, self.competitor_name_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated.connect(self._use_roster_completion)
        self.competitor_name_edit.setCompleter(completer)
        self._roster_completer = completer

    def _use_roster_completion(self, label: str):
        name = self._roster_completion_names.get(str(label), str(label))
        self.competitor_name_edit.setText(name)
        self.competitor_name_edit.setCursorPosition(len(name))

    def _add_competitor(self):
        name = _clean_name(self.competitor_name_edit.text())
        if not name:
            self.competitor_name_edit.setFocus()
            return
        category_id = self.competitor_category_combo.currentData() or "none"
        if self._duplicate_competitor(name, category_id) is not None:
            QMessageBox.warning(
                self,
                "Duplicitní pirát",
                f"Pirát „{name}“ už v kategorii „{self._category_name(category_id)}“ existuje. "
                "Doplň příjmení nebo přezdívku, aby šel ve výsledcích jednoznačně poznat.",
            )
            self.competitor_name_edit.setFocus()
            self.competitor_name_edit.selectAll()
            return
        self.competitors.append(
            {
                "id": _uid(),
                "name": name,
                "category_id": category_id,
                "gender": self.competitor_gender_combo.currentData() or "M",
            }
        )
        self.competitor_name_edit.clear()
        self._save_data()
        self.refresh_all()

    def _remove_competitor(self, competitor_id: str):
        self.competitors = [item for item in self.competitors if item.get("id") != competitor_id]
        for event_results in self.results.values():
            if isinstance(event_results, dict):
                event_results.pop(competitor_id, None)
        self._save_data()
        self.refresh_all()

    def _filtered_competitors(self):
        search = self.competitor_search_edit.text().strip().casefold()
        category = self.competitor_filter_category.currentData() or "all"
        gender = self.competitor_filter_gender.currentData() or "all"
        return [
            competitor
            for competitor in self.competitors
            if (not search or search in str(competitor.get("name", "")).casefold())
            and (category == "all" or competitor.get("category_id") == category)
            and (gender == "all" or competitor.get("gender", "M") == gender)
        ]

    def _refresh_competitors_table(self):
        if not hasattr(self, "competitors_table"):
            return
        rows = sorted(
            self._filtered_competitors(),
            key=lambda item: str(item.get("name") or "").casefold(),
        )
        self.competitors_table.blockSignals(True)
        self.competitors_table.setRowCount(0)
        self.competitors_table.clearSpans()
        for competitor in rows:
            row = self.competitors_table.rowCount()
            self.competitors_table.insertRow(row)
            competitor_id = competitor.get("id")
            name_button = QPushButton(
                f"UPRAVIT PIRÁTA  •  {str(competitor.get('name') or '')}",
                self.competitors_table,
            )
            name_button.setObjectName("pirateNameButton")
            name_button.setToolTip("Otevřít piráta v samostatném okně a upravit všechny údaje")
            name_button.clicked.connect(
                lambda _checked=False, competitor_id=competitor_id: self._open_competitor_editor(competitor_id)
            )
            self.competitors_table.setCellWidget(row, 0, name_button)

            category_item = self._readonly_item(
                self._category_name(competitor.get("category_id", "none")), Qt.AlignCenter
            )
            category_item.setData(Qt.UserRole, competitor_id)
            category_item.setToolTip("Kliknutím otevřeš všechny údaje piráta")
            self.competitors_table.setItem(row, 1, category_item)

            gender_item = self._readonly_item(
                GENDERS[competitor.get("gender", "M")]["singular"], Qt.AlignCenter
            )
            gender_item.setData(Qt.UserRole, competitor_id)
            gender_item.setToolTip("Kliknutím otevřeš všechny údaje piráta")
            self.competitors_table.setItem(row, 2, gender_item)

            completed = sum(
                1
                for event in self.events
                if str((self.results.get(event.get("id"), {}) or {}).get(competitor_id, "")).strip()
            )
            count_item = QTableWidgetItem(f"{completed}/{len(self.events)}")
            count_item.setTextAlignment(Qt.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            count_item.setData(Qt.UserRole, competitor_id)
            count_item.setToolTip("Kliknutím otevřeš a upravíš výsledky všech výzev")
            self.competitors_table.setItem(row, 3, count_item)

            remove = QPushButton("ODSTRANIT", self.competitors_table)
            remove.setObjectName("dangerButton")
            remove.setMinimumWidth(102)
            remove.setFixedHeight(30)
            remove.clicked.connect(
                lambda _checked=False, competitor_id=competitor_id: self._remove_competitor(competitor_id)
            )
            self.competitors_table.setCellWidget(row, 4, remove)
        self.competitors_table.blockSignals(False)
        self.competitors_empty.setVisible(not rows)
        self.competitors_empty.setText(
            "Posádka je zatím prázdná. Přidej prvního piráta výše."
            if not self.competitors
            else "Žádný pirát neodpovídá vyhledávání ani filtru."
        )
        self.competitors_table.setVisible(bool(rows))
        self.competitors_table.setMinimumHeight(185)

    def _competitor_table_clicked(self, row: int, column: int):
        if column == 4:
            return
        item = self.competitors_table.item(row, column)
        competitor_id = item.data(Qt.UserRole) if item is not None else None
        if competitor_id:
            self._open_competitor_editor(competitor_id)

    def _open_competitor_editor(self, competitor_id: str):
        competitor = self._competitor_by_id(competitor_id)
        if competitor is None:
            return
        editor = self._create_competitor_editor(competitor)
        while editor.exec() == QDialog.Accepted:
            name = _clean_name(editor.name_edit.text())
            if not name:
                QMessageBox.information(editor, "Chybí jméno", "Každý pirát musí mít vyplněné jméno.")
                continue
            category_id = editor.category_combo.currentData() or "none"
            if self._duplicate_competitor(name, category_id, competitor_id) is not None:
                QMessageBox.warning(
                    editor,
                    "Duplicitní pirát",
                    f"Pirát „{name}“ už v kategorii „{self._category_name(category_id)}“ existuje. "
                    "Doplň příjmení nebo přezdívku.",
                )
                editor.name_edit.setFocus()
                editor.name_edit.selectAll()
                continue
            self._apply_competitor_editor(competitor, editor)
            return

    def _apply_competitor_editor(self, competitor: dict, editor: QDialog):
        competitor_id = competitor.get("id")
        competitor["name"] = _clean_name(editor.name_edit.text())
        competitor["category_id"] = editor.category_combo.currentData() or "none"
        competitor["gender"] = editor.gender_combo.currentData() or "M"
        competitor["notes"] = editor.notes_edit.toPlainText().strip()
        for event_id, result_editor in editor.result_editors.items():
            value = result_editor.text().strip()
            event_results = self.results.setdefault(event_id, {})
            if value:
                event_results[competitor_id] = value
            else:
                event_results.pop(competitor_id, None)

        self._save_data()
        self._reset_results_sort(refresh=False)
        self._reset_standings_sort(refresh=False)
        self.refresh_all()

    def _create_competitor_editor(self, competitor: dict):
        editor = QDialog(self)
        editor.setObjectName("pirateEditorDialog")
        editor.setWindowTitle(f"Karta piráta • {competitor.get('name', '')}")
        editor.setWindowModality(Qt.WindowModal)
        editor.resize(900, 740)
        editor.setMinimumSize(720, 560)
        popup_background = os.path.join(self.icons_path, "sports_day_BG.png").replace("\\", "/")
        popup_style = """
                QDialog#pirateEditorDialog {
                    background-color: #061923;
                    border-image: url("__POPUP_BACKGROUND__") 0 0 0 0 stretch stretch;
                }
                QScrollArea#pirateResultsScroll {
                    background: transparent;
                    border: 1px solid rgba(196, 151, 76, 150);
                    border-radius: 11px;
                }
                QTextEdit {
                    color: #f0e2c0;
                    background-color: rgba(2, 14, 22, 185);
                    border: 1px solid rgba(196, 151, 76, 190);
                    border-radius: 9px;
                    padding: 7px;
                    selection-background-color: #176c76;
                    selection-color: #fff0bd;
                    font-size: 12px;
                }
            """.replace("__POPUP_BACKGROUND__", popup_background)
        editor.setStyleSheet(
            self._style_sheet()
            + popup_style
        )
        outer = QVBoxLayout(editor)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)

        header = QHBoxLayout()
        coin = QLabel(editor)
        coin.setFixedSize(62, 62)
        coin.setAlignment(Qt.AlignCenter)
        if not self.coin_pixmap.isNull():
            coin.setPixmap(self.coin_pixmap.scaled(58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header.addWidget(coin)
        titles = QVBoxLayout()
        title = QLabel("KARTA PIRÁTA", editor)
        title.setStyleSheet("color: #f4dea4; font-size: 23px; font-weight: bold; letter-spacing: 2px;")
        titles.addWidget(title)
        subtitle = QLabel("Uprav osobní údaje, poznámku i všechny dosažené výsledky.", editor)
        subtitle.setStyleSheet("color: #d6c495; font-size: 12px; font-style: italic;")
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        outer.addLayout(header)

        identity_panel = QFrame(editor)
        identity_panel.setObjectName("sportsPanel")
        identity = QGridLayout(identity_panel)
        identity.setContentsMargins(14, 12, 14, 14)
        identity.setHorizontalSpacing(10)
        identity.setVerticalSpacing(7)
        identity_title = QLabel("OSOBNÍ ÚDAJE", identity_panel)
        identity_title.setStyleSheet("color: #f3d79a; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        identity.addWidget(identity_title, 0, 0, 1, 3)

        editor.name_edit = QLineEdit(identity_panel)
        editor.name_edit.setText(str(competitor.get("name") or ""))
        editor.name_edit.selectAll()
        editor.category_combo = QComboBox(identity_panel)
        for category in self.categories:
            editor.category_combo.addItem(str(category.get("name") or ""), category.get("id"))
        category_index = editor.category_combo.findData(competitor.get("category_id", "none"))
        editor.category_combo.setCurrentIndex(max(0, category_index))
        editor.gender_combo = QComboBox(identity_panel)
        editor.gender_combo.addItem("Kluk", "M")
        editor.gender_combo.addItem("Holka", "F")
        editor.gender_combo.setCurrentIndex(max(0, editor.gender_combo.findData(competitor.get("gender", "M"))))
        identity.addLayout(self._field("JMÉNO PIRÁTA", editor.name_edit, identity_panel), 1, 0)
        identity.addLayout(self._field("VĚKOVÁ KATEGORIE", editor.category_combo, identity_panel), 1, 1)
        identity.addLayout(self._field("POHLAVÍ", editor.gender_combo, identity_panel), 1, 2)
        identity.setColumnStretch(0, 3)
        identity.setColumnStretch(1, 2)
        identity.setColumnStretch(2, 1)

        editor.notes_edit = QTextEdit(identity_panel)
        editor.notes_edit.setPlaceholderText("Například silné stránky, zdravotní omezení nebo poznámka vedoucího…")
        editor.notes_edit.setPlainText(str(competitor.get("notes") or ""))
        editor.notes_edit.setFixedHeight(78)
        notes_label = QLabel("POZNÁMKA K PIRÁTOVI", identity_panel)
        notes_label.setStyleSheet("color: #cdbb91; font-size: 11px; font-weight: bold;")
        identity.addWidget(notes_label, 2, 0, 1, 3)
        identity.addWidget(editor.notes_edit, 3, 0, 1, 3)
        outer.addWidget(identity_panel)

        results_heading = QHBoxLayout()
        results_title = QLabel("VÝSLEDKY VŠECH VÝZEV", editor)
        results_title.setStyleSheet("color: #f3d79a; font-size: 14px; font-weight: bold; letter-spacing: 1px;")
        results_heading.addWidget(results_title)
        results_heading.addStretch(1)
        completed = sum(
            1
            for event in self.events
            if str((self.results.get(event.get("id"), {}) or {}).get(competitor.get("id"), "")).strip()
        )
        totals, _per_event = self._standings_data()
        completed_label = QLabel(
            f"VYPLNĚNO  {completed}/{len(self.events)}   •   POKLAD  {totals.get(competitor.get('id'), 0)}",
            editor,
        )
        completed_label.setStyleSheet(
            "color: #f0d19a; background: rgba(13,64,75,170); border: 1px solid #a47a3e; "
            "border-radius: 8px; padding: 6px 10px; font-weight: bold;"
        )
        results_heading.addWidget(completed_label)
        outer.addLayout(results_heading)

        scroll = QScrollArea(editor)
        scroll.setObjectName("pirateResultsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(210)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        results_page = QWidget(scroll)
        results_page.setObjectName("sportsPage")
        results_page.setAutoFillBackground(False)
        results_layout = QGridLayout(results_page)
        results_layout.setContentsMargins(13, 12, 13, 12)
        results_layout.setHorizontalSpacing(10)
        results_layout.setVerticalSpacing(8)
        editor.result_editors = {}

        if self.events:
            for column, label_text in enumerate(("VÝZVA", "PRAVIDLO", "VÝSLEDEK", "JEDNOTKA")):
                label = QLabel(label_text, results_page)
                label.setStyleSheet("color: #cdbb91; font-size: 10px; font-weight: bold;")
                results_layout.addWidget(label, 0, column)
            for row, event in enumerate(self.events, start=1):
                metric = METRICS.get(event.get("metric"), METRICS["time"])
                direction = "nejnižší vyhrává" if event.get("direction") == "asc" else "nejvyšší vyhrává"
                event_name = QLabel(str(event.get("name") or ""), results_page)
                event_name.setStyleSheet("color: #f0e2c0; font-weight: bold;")
                results_layout.addWidget(event_name, row, 0)
                rule = QLabel(f"{metric['label']} • {direction}", results_page)
                rule.setStyleSheet("color: #d6c495;")
                rule.setWordWrap(True)
                results_layout.addWidget(rule, row, 1)
                result_edit = QLineEdit(results_page)
                result_edit.setText(
                    str((self.results.get(event.get("id"), {}) or {}).get(competitor.get("id"), ""))
                )
                result_edit.setPlaceholderText("mm:ss" if event.get("metric") == "time" else metric["unit"])
                result_edit.setAlignment(Qt.AlignRight)
                editor.result_editors[event.get("id")] = result_edit
                results_layout.addWidget(result_edit, row, 2)
                unit = QLabel(metric["unit"], results_page)
                unit.setStyleSheet("color: #d6c495;")
                unit.setWordWrap(True)
                results_layout.addWidget(unit, row, 3)
        else:
            empty = QLabel("Zatím nejsou vytvořené žádné výzvy.", results_page)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #d6c495; font-style: italic; padding: 28px;")
            results_layout.addWidget(empty, 0, 0)

        results_layout.setColumnStretch(0, 3)
        results_layout.setColumnStretch(1, 2)
        results_layout.setColumnStretch(2, 2)
        results_layout.setColumnStretch(3, 2)
        results_layout.setRowStretch(results_layout.rowCount(), 1)
        scroll.setWidget(results_page)
        outer.addWidget(scroll, 1)

        footer = QHBoxLayout()
        hint = QLabel("Změny se uloží společně po potvrzení.", editor)
        hint.setStyleSheet("color: rgba(234,216,179,175); font-size: 11px;")
        footer.addWidget(hint)
        footer.addStretch(1)
        cancel = QPushButton("ZRUŠIT", editor)
        cancel.setObjectName("quietButton")
        cancel.clicked.connect(editor.reject)
        footer.addWidget(cancel)
        save = QPushButton("ULOŽIT VŠECHNY ZMĚNY", editor)
        save.clicked.connect(editor.accept)
        footer.addWidget(save)
        outer.addLayout(footer)
        editor.name_edit.setFocus()
        return editor

    # ------------------------------------------------------------------
    # Výsledky a pořadí
    # ------------------------------------------------------------------

    def _refresh_results_controls(self):
        event_values = [(event.get("name"), event.get("id")) for event in self.events]
        if self.selected_event_id not in [value for _label, value in event_values]:
            self.selected_event_id = event_values[0][1] if event_values else None
        self._fill_combo(self.results_event_combo, event_values, self.selected_event_id)

    def _results_event_changed(self):
        if self._refreshing:
            return
        self.selected_event_id = self.results_event_combo.currentData()
        self._reset_results_sort(refresh=False)
        self._save_data()
        self._refresh_results_table()

    @staticmethod
    def _sorted_for_event(event: dict, competitors: list, event_results: dict):
        valid = []
        missing = []
        for competitor in competitors:
            raw = event_results.get(competitor.get("id"), "")
            parsed = parse_metric_value(raw, event.get("metric", "time"))
            if parsed is None:
                missing.append(competitor)
            else:
                valid.append((competitor, parsed))
        valid.sort(key=lambda item: item[1], reverse=event.get("direction") == "desc")
        return [item[0] for item in valid], missing

    def _base_result_groups(self, event: dict):
        groups = []
        view = self.results_view_combo.currentData() or "category"
        gender_filter = self.results_gender_combo.currentData() or "all"
        if view == "overall":
            competitors = [
                item for item in self.competitors
                if gender_filter == "all" or item.get("gender", "M") == gender_filter
            ]
            competitors.sort(key=lambda item: str(item.get("name") or "").casefold())
            groups.append(("CELKOVÉ POŘADÍ", competitors))
            return groups

        for category in self.categories:
            for gender in ("M", "F"):
                if gender_filter != "all" and gender != gender_filter:
                    continue
                competitors = [
                    item for item in self.competitors
                    if item.get("category_id") == category.get("id") and item.get("gender", "M") == gender
                ]
                if not competitors:
                    continue
                competitors.sort(key=lambda item: str(item.get("name") or "").casefold())
                groups.append((f"{category.get('name')}  •  {GENDERS[gender]['plural']}", competitors))
        return groups

    def _result_groups(self, event: dict):
        groups = self._base_result_groups(event)
        if self.results_sort_mode != "results":
            return groups
        ordered_groups = []
        for label, competitors in groups:
            lookup = {item.get("id"): item for item in competitors}
            ordered = [lookup[item_id] for item_id in self._results_order_ids.get(label, ()) if item_id in lookup]
            ordered_ids = {item.get("id") for item in ordered}
            ordered.extend(item for item in competitors if item.get("id") not in ordered_ids)
            ordered_groups.append((label, ordered))
        return ordered_groups

    def _reset_results_sort(self, _value=None, refresh=True):
        self._cancel_bubble_sort()
        self.results_sort_mode = "alphabetical"
        self._results_order_ids = {}
        self._bubble_highlight = set()
        if hasattr(self, "results_sort_status"):
            self.results_sort_status.setText("Výchozí pořadí: abecedně")
        if refresh and hasattr(self, "results_table"):
            self._refresh_results_table()

    def _start_results_bubble_sort(self):
        event = self._event_by_id(self.selected_event_id)
        if event is None or not self.competitors:
            return
        event_results = self.results.get(event.get("id"), {}) or {}
        groups = self._base_result_groups(event)
        key_map = {}
        for _label, competitors in groups:
            for competitor in competitors:
                parsed = parse_metric_value(event_results.get(competitor.get("id"), ""), event.get("metric", "time"))
                directed = parsed if event.get("direction") == "asc" else (-parsed if parsed is not None else None)
                key_map[competitor.get("id")] = (
                    parsed is None,
                    directed if directed is not None else 0.0,
                    str(competitor.get("name") or "").casefold(),
                )
        self._start_bubble_sort("results", groups, key_map)

    def _start_bubble_sort(self, kind: str, groups: list, key_map: dict):
        self._cancel_bubble_sort()
        order_map = {label: [item.get("id") for item in competitors] for label, competitors in groups}
        if kind == "results":
            self.results_sort_mode = "results"
            self._results_order_ids = order_map
            button = self.results_bubble_button
            status = self.results_sort_status
            button.setText("BUBLINKY ŘADÍ…")
            status.setText("Bublinkové řazení porovnává sousední výsledky…")
        else:
            self.standings_sort_mode = "results"
            self._standings_order_ids = order_map
            button = self.standings_bubble_button
            status = self.standings_sort_status
            button.setText("ŘADÍM…")
            status.setText("Bublinkové řazení přesouvá největší poklady vzhůru…")
        button.setEnabled(False)
        self._bubble_highlight = set()
        self._bubble_state = {
            "kind": kind,
            "groups": [
                {"label": label, "ids": list(order_map.get(label, ())), "pass": 0, "index": 0, "swapped": False}
                for label, _competitors in groups
            ],
            "group_index": 0,
            "key_map": key_map,
        }
        if kind == "results":
            self._refresh_results_table()
        else:
            self._refresh_standings_table()
        self._bubble_timer.start()

    def _bubble_sort_step(self):
        state = self._bubble_state
        if not state:
            self._bubble_timer.stop()
            return

        # Jeden časový krok skončí nejvýše jednou viditelnou sousední výměnou.
        # Prázdná porovnání se přeskočí, aby animace nezdržovala u hotových úseků.
        for _attempt in range(256):
            group_index = state["group_index"]
            if group_index >= len(state["groups"]):
                self._finish_bubble_sort()
                return
            group = state["groups"][group_index]
            ids = group["ids"]
            limit = len(ids) - 1 - group["pass"]
            if limit <= 0:
                state["group_index"] += 1
                continue
            if group["index"] >= limit:
                if not group["swapped"]:
                    state["group_index"] += 1
                else:
                    group["pass"] += 1
                    group["index"] = 0
                    group["swapped"] = False
                continue

            index = group["index"]
            group["index"] += 1
            left_id, right_id = ids[index], ids[index + 1]
            if state["key_map"].get(left_id, ()) > state["key_map"].get(right_id, ()):
                ids[index], ids[index + 1] = right_id, left_id
                group["swapped"] = True
                self._bubble_highlight = {left_id, right_id}
                if state["kind"] == "results":
                    self._results_order_ids[group["label"]] = list(ids)
                    self._refresh_results_table()
                else:
                    self._standings_order_ids[group["label"]] = list(ids)
                    self._refresh_standings_table()
                return

    def _finish_bubble_sort(self):
        state = self._bubble_state
        if not state:
            return
        self._bubble_timer.stop()
        kind = state["kind"]
        self._bubble_state = None
        self._bubble_highlight = set()
        if kind == "results":
            self.results_bubble_button.setEnabled(True)
            self.results_bubble_button.setText("SEŘADIT")
            self.results_sort_status.setText("Seřazeno podle výsledků • hotovo bublinkovým řazením")
            self._refresh_results_table()
        else:
            self.standings_bubble_button.setEnabled(True)
            self.standings_bubble_button.setText("SEŘADIT")
            self.standings_sort_status.setText("Seřazeno podle mincí • hotovo bublinkovým řazením")
            self._refresh_standings_table()

    def _cancel_bubble_sort(self):
        state = self._bubble_state
        if not state:
            return
        self._bubble_timer.stop()
        kind = state.get("kind")
        self._bubble_state = None
        self._bubble_highlight = set()
        if kind == "results" and hasattr(self, "results_bubble_button"):
            self.results_bubble_button.setEnabled(True)
            self.results_bubble_button.setText("SEŘADIT")
        elif kind == "standings" and hasattr(self, "standings_bubble_button"):
            self.standings_bubble_button.setEnabled(True)
            self.standings_bubble_button.setText("SEŘADIT")

    def _set_result(self, event_id: str, competitor_id: str, editor: QLineEdit):
        value = editor.text().strip()
        event_results = self.results.setdefault(event_id, {})
        if value:
            event_results[competitor_id] = value
        else:
            event_results.pop(competitor_id, None)
        self._save_data()
        self._reset_results_sort(refresh=False)
        self._reset_standings_sort(refresh=False)
        self._refresh_stats()
        self._refresh_competitors_table()
        self._refresh_results_table()
        self._refresh_standings_table()

    def _section_row(self, table: QTableWidget, row: int, text: str, columns: int):
        table.insertRow(row)
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled)
        item.setForeground(QColor("#f3d79a"))
        item.setBackground(QColor(13, 65, 73, 92))
        font = QFont("Georgia", 11, QFont.Bold)
        item.setFont(font)
        table.setItem(row, 0, item)
        table.setSpan(row, 0, 1, columns)
        table.setRowHeight(row, 32)

    def _rank_item(self, rank, has_value=True):
        item = QTableWidgetItem(str(rank) if rank is not None else "–")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if has_value and rank and rank <= 3:
            # Barva pozadí buněk je řízena stylem celé tabulky, proto musí
            # pořadí zůstat kontrastní i bez medailového podkladu.
            medal_text_colors = ("#ffe39c", "#edf4f5", "#f2b36f")
            item.setForeground(QColor(medal_text_colors[rank - 1]))
            item.setFont(QFont("Georgia", 10, QFont.Bold))
        return item

    def _readonly_item(self, value, alignment=None):
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if alignment is not None:
            item.setTextAlignment(alignment)
        return item

    def _coin_item(self, count):
        item = self._readonly_item(_format_points_value(count) if count else "–", Qt.AlignCenter)
        if not self.coin_pixmap.isNull():
            item.setIcon(QIcon(self.coin_pixmap))
        item.setToolTip(f"{_format_points_value(count)} pirátských mincí")
        if count:
            item.setForeground(QColor("#f5cf71"))
            item.setFont(QFont("Georgia", 10, QFont.Bold))
        return item

    def _highlight_table_row(self, table: QTableWidget, row: int, columns: int, competitor_id: str):
        if competitor_id not in self._bubble_highlight:
            return
        for column in range(columns):
            item = table.item(row, column)
            if item is not None:
                item.setBackground(QColor(202, 147, 53, 92))

    def _refresh_results_table(self):
        if not hasattr(self, "results_table"):
            return
        event = self._event_by_id(self.selected_event_id)
        self.results_table.setRowCount(0)
        self.results_table.clearSpans()
        if event is None:
            self.results_hint.setText("Nejdřív přidej alespoň jednu výzvu v záložce Výzvy.")
            self.results_table.setMinimumHeight(210)
            return
        if not self.competitors:
            self.results_hint.setText("Nejdřív přidej piráty v záložce Posádka.")
            self.results_table.setMinimumHeight(210)
            return

        metric = self.METRICS.get(event.get("metric"), self.METRICS["time"])
        direction = "nejnižší" if event.get("direction") == "asc" else "nejvyšší"
        order_text = "abecedně" if self.results_sort_mode == "alphabetical" else "podle výsledků"
        self.results_hint.setText(
            f"{event.get('name')}  •  {metric['label']}  •  vítězí {direction} hodnota  •  "
            f"pořadí {order_text}  •  čas lze zadat jako sekundy nebo mm:ss"
        )
        event_results = self.results.get(event.get("id"), {}) or {}
        points = self._event_points(event)

        row = 0
        groups = self._result_groups(event)
        show_sections = self.results_view_combo.currentData() != "overall"
        for label, competitors in groups:
            if show_sections:
                self._section_row(self.results_table, row, label, 7)
                row += 1
            parsed_values = [
                parse_metric_value(
                    event_results.get(competitor.get("id"), ""),
                    event.get("metric", "time"),
                )
                for competitor in competitors
            ]
            ranks = (
                _competition_ranks(parsed_values)
                if self.results_sort_mode == "results"
                else [None] * len(competitors)
            )
            for competitor, parsed_value, rank in zip(competitors, parsed_values, ranks):
                competitor_id = competitor.get("id")
                has_value = parsed_value is not None
                self.results_table.insertRow(row)
                self.results_table.setItem(row, 0, self._rank_item(rank, has_value))
                self.results_table.setItem(row, 1, self._readonly_item(competitor.get("name", "")))
                self.results_table.setItem(
                    row, 2, self._readonly_item(self._category_name(competitor.get("category_id", "none")))
                )
                self.results_table.setItem(
                    row, 3, self._readonly_item(GENDERS[competitor.get("gender", "M")]["singular"])
                )
                editor = QLineEdit(self.results_table)
                editor.setPlaceholderText("mm:ss" if event.get("metric") == "time" else metric["unit"])
                editor.setText(str(event_results.get(competitor.get("id"), "")))
                editor.setAlignment(Qt.AlignRight)
                editor.editingFinished.connect(
                    lambda event_id=event.get("id"), competitor_id=competitor_id, widget=editor:
                    self._set_result(event_id, competitor_id, widget)
                )
                self.results_table.setCellWidget(row, 4, editor)
                self.results_table.setItem(row, 5, self._readonly_item(metric["unit"], Qt.AlignCenter))
                coins = points.get(competitor.get("id"), 0)
                self.results_table.setItem(row, 6, self._coin_item(coins))
                self._highlight_table_row(self.results_table, row, 7, competitor_id)
                row += 1
        self.results_table.setMinimumHeight(210)

    # ------------------------------------------------------------------
    # Celkový poklad
    # ------------------------------------------------------------------

    def _standings_data(self):
        totals = {competitor.get("id"): 0 for competitor in self.competitors}
        per_event = {competitor.get("id"): {} for competitor in self.competitors}
        for event in self.events:
            points = self._event_points(event)
            for competitor_id, value in points.items():
                totals[competitor_id] = totals.get(competitor_id, 0) + value
                per_event.setdefault(competitor_id, {})[event.get("id")] = value
        return totals, per_event

    def _base_standings_groups(self):
        view = self.standings_view_combo.currentData() or "category"
        gender_filter = self.standings_gender_combo.currentData() or "all"
        groups = []
        if view == "overall":
            rows = [
                item for item in self.competitors
                if gender_filter == "all" or item.get("gender", "M") == gender_filter
            ]
            rows.sort(key=lambda item: str(item.get("name") or "").casefold())
            groups.append(("CELKOVÁ KOŘIST – CELÁ POSÁDKA", rows))
            return groups

        for category in self.categories:
            for gender in ("M", "F"):
                if gender_filter != "all" and gender != gender_filter:
                    continue
                rows = [
                    item for item in self.competitors
                    if item.get("category_id") == category.get("id") and item.get("gender", "M") == gender
                ]
                if not rows:
                    continue
                rows.sort(key=lambda item: str(item.get("name") or "").casefold())
                groups.append((f"{category.get('name')}  •  {GENDERS[gender]['plural']}", rows))
        return groups

    def _standings_groups(self):
        groups = self._base_standings_groups()
        if self.standings_sort_mode != "results":
            return groups
        ordered_groups = []
        for label, competitors in groups:
            lookup = {item.get("id"): item for item in competitors}
            ordered = [lookup[item_id] for item_id in self._standings_order_ids.get(label, ()) if item_id in lookup]
            ordered_ids = {item.get("id") for item in ordered}
            ordered.extend(item for item in competitors if item.get("id") not in ordered_ids)
            ordered_groups.append((label, ordered))
        return ordered_groups

    def _reset_standings_sort(self, _value=None, refresh=True):
        self._cancel_bubble_sort()
        self.standings_sort_mode = "alphabetical"
        self._standings_order_ids = {}
        self._bubble_highlight = set()
        if hasattr(self, "standings_sort_status"):
            self.standings_sort_status.setText("Výchozí pořadí: abecedně")
        if refresh and hasattr(self, "standings_table"):
            self._refresh_standings_table()

    def _start_standings_bubble_sort(self):
        if not self.competitors:
            return
        totals, _per_event = self._standings_data()
        groups = self._base_standings_groups()
        key_map = {
            competitor.get("id"): (
                -totals.get(competitor.get("id"), 0),
                str(competitor.get("name") or "").casefold(),
            )
            for _label, competitors in groups
            for competitor in competitors
        }
        self._start_bubble_sort("standings", groups, key_map)

    def _refresh_standings_table(self):
        if not hasattr(self, "standings_table"):
            return
        self.standings_table.setRowCount(0)
        self.standings_table.clearSpans()
        if not self.competitors:
            self.standings_table.setMinimumHeight(220)
            return

        totals, per_event = self._standings_data()
        view = self.standings_view_combo.currentData() or "category"
        groups = self._standings_groups()

        row = 0
        show_sections = view != "overall"
        for label, competitors in groups:
            if show_sections:
                self._section_row(self.standings_table, row, label, 6)
                row += 1
            ranks = (
                _competition_ranks([
                    totals.get(item.get("id"), 0)
                    if per_event.get(item.get("id"), {})
                    else None
                    for item in competitors
                ])
                if self.standings_sort_mode == "results"
                else [None] * len(competitors)
            )
            for competitor, rank in zip(competitors, ranks):
                competitor_id = competitor.get("id")
                total = totals.get(competitor_id, 0)
                self.standings_table.insertRow(row)
                self.standings_table.setItem(row, 0, self._rank_item(rank, total > 0))
                self.standings_table.setItem(row, 1, self._readonly_item(competitor.get("name", "")))
                self.standings_table.setItem(
                    row, 2, self._readonly_item(self._category_name(competitor.get("category_id", "none")))
                )
                self.standings_table.setItem(
                    row, 3, self._readonly_item(GENDERS[competitor.get("gender", "M")]["singular"])
                )
                self.standings_table.setItem(row, 4, self._coin_item(total))
                breakdown = []
                event_points = per_event.get(competitor_id, {})
                for event in self.events:
                    value = event_points.get(event.get("id"))
                    if value:
                        breakdown.append(f"{event.get('name')}: {_format_points_value(value)}")
                self.standings_table.setItem(
                    row, 5, self._readonly_item("  •  ".join(breakdown) if breakdown else "Bez výsledků")
                )
                self._highlight_table_row(self.standings_table, row, 6, competitor_id)
                row += 1
        self.standings_table.setMinimumHeight(220)

    # ------------------------------------------------------------------
    # Navigace
    # ------------------------------------------------------------------

    def _tab_changed(self, index: int):
        # Záložky se roztahují podle aktuální velikosti okna. Na velkém monitoru
        # tak využijí celou dostupnou plochu a na menším zůstanou tabulky posuvné.
        if index == 2:
            self._refresh_results_table()
        elif index == 3:
            self._refresh_standings_table()

    def _go_home(self):
        if self.owner_window is not None and hasattr(self.owner_window, "show_home_page"):
            self.owner_window.show_home_page()
        else:
            self.close()

    def closeEvent(self, event):
        self._save_data()
        super().closeEvent(event)
