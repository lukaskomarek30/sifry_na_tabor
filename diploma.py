"""Pirátské studio diplomů A5 a úklidové listiny A4."""

from __future__ import annotations

import copy
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QFrame,
    QFontComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from diploma_print import DiplomaSheetPreview, print_document, save_document_pdf
from fire_effects import PirateModuleDialog
from home_menu import PIRATE_FONT_FAMILY, PirateMenuCard, _ensure_pirate_font


DOCUMENT_DEFAULTS = {
    "camp": {
        "title": "DIPLOM ZA TÁBOR",
        "lead": "uděluje se",
        "name": "JMÉNO PIRÁTA",
        "award": "za statečnost, spolupráci a dobrodružství",
        "footer": "Tábor Mraveniště • Piráti z Karibiku",
        "date_label": "Datum:",
        "date": "",
        "signature_label": "Kapitán:",
        "signature": "",
    },
    "sports": {
        "title": "DIPLOM ZA SPORTOVNÍ DEN",
        "lead": "uděluje se",
        "name": "JMÉNO PIRÁTA",
        "award": "za skvělý výkon a bojovnost",
        "footer": "Pirátský sportovní den • Tábor Mraveniště",
        "discipline_label": "Disciplína:",
        "discipline": "",
        "placement_label": "Umístění:",
        "placement": "",
        "date_label": "Datum:",
        "date": "",
        "signature_label": "Vedoucí:",
        "signature": "",
    },
    "cleaning": {
        "title": "LODNÍ DENÍK ČISTOTY",
        "subtitle": "Hodnocení úklidu chatek • 9. 8.–22. 8.",
        "cabin_header": "Chatka",
        "cabins_text": "\n".join(f"Chatka {index}" for index in range(1, 14)),
        "dates_text": "\n".join(f"{day}. 8." for day in range(9, 23)),
        "total_header": "Součet",
        "rank_header": "Pořadí",
        "footer": "Body zapisuje vedoucí každý den po kontrole úklidu.",
    },
    "cleaning_award": {
        "title": "DIPLOM ZA ÚKLID",
        "placement": "1. MÍSTO",
        "lead": "uděluje se",
        "name": "JMÉNO CHATKY / POSÁDKY",
        "award": "za nejlépe uklizený srub",
        "cabin_label": "Srub:",
        "cabin": "",
        "date_label": "Datum:",
        "date": "",
        "signature_label": "Kapitán:",
        "signature": "",
    },
    "daily": {
        "title": "DENNÍ PROGRAM",
        "subtitle": "Rozkaz dne pro celou pirátskou posádku",
        "date": "",
        "schedule": (
            "7.30  Budíček\n7.35  Rozcvička\n7.45–8.00  Ranní hygiena\n"
            "8.00  Snídaně\n8.30–9.00  Úklid srubů a příprava\n9.00  Nástup tábora\n"
            "9.10–12.15  Dopolední program\n12.15–12.30  Příprava na oběd\n"
            "12.30  Oběd\n13.00–14.00  Polední klid\n14.00  Nástup tábora\n"
            "14.10–18.00  Odpolední program\n18.00–18.30  Příprava na večeři\n"
            "18.30  Večeře\n19.00  Večerní nástup\n19.30–21.30  Večerní program\n"
            "21.30–22.00  Příprava na večerku\n22.00  Večerka"
        ),
        "footer": "Program může kapitán upravit podle počasí a situace na palubě.",
    },
    "meal": {
        "title": "JÍDELNÍČEK",
        "date_label": "Den:",
        "date": "",
        "breakfast_label": "Snídaně:",
        "breakfast": "",
        "snack1_label": "Dopolední svačina:",
        "snack1": "",
        "lunch_label": "Oběd:",
        "lunch": "",
        "snack2_label": "Odpolední svačina:",
        "snack2": "",
        "dinner_label": "Večeře:",
        "dinner": "",
        "footer": "Dobrou chuť, posádko!",
    },
}


VARIANTS = {
    "camp": (
        ("A", "A • Pergamenová mapa"),
        ("B", "B • Admirálská noční listina"),
        ("C", "C • Slavnostní zlatý diplom"),
    ),
    "sports": (
        ("A", "A • Vítězný věnec a pohár"),
        ("B", "B • Stadion, kompas a stopky"),
        ("C", "C • Medaile a kapitánské šavle"),
        ("D", "D • Olympiáda Piráti z Karibiku"),
    ),
    "cleaning": (("B", "B • Lodní deník čistoty"),),
    "cleaning_award": (
        ("A", "A • Veselý pergamen uklízečů"),
        ("B", "B • Admirálská listina čistoty"),
    ),
    "daily": (
        ("A", "A • Ručně psaný denní rozkaz"),
        ("B", "B • Noční kapitánský plán"),
    ),
    "meal": (
        ("A", "A • Lodní kuchařská listina"),
        ("B", "B • Admirálská lodní kuchyně"),
    ),
}


DOCUMENT_LAYOUTS = {
    "camp": "two_a5_portrait",
    "sports": "two_a5_portrait",
    "cleaning": "a4_landscape",
    "cleaning_award": "two_a5_landscape",
    "daily": "a4_portrait",
    "meal": "a4_portrait",
}


FIELD_LABELS = {
    "title": "Hlavní nadpis",
    "lead": "Text nad jménem",
    "name": "Jméno piráta",
    "award": "Text ocenění",
    "footer": "Spodní text",
    "discipline_label": "Popisek disciplíny",
    "discipline": "Disciplína",
    "placement_label": "Popisek umístění",
    "placement": "Umístění",
    "date_label": "Popisek data",
    "date": "Datum",
    "signature_label": "Popisek podpisu",
    "signature": "Podpis / vedoucí",
    "subtitle": "Podnadpis",
    "cabin_header": "Nadpis chatek",
    "cabins_text": "Názvy 13 chatek",
    "dates_text": "Datumy 9. 8.–22. 8.",
    "total_header": "Nadpis součtu",
    "rank_header": "Nadpis pořadí",
    "placement": "Umístění",
    "cabin_label": "Popisek srubu",
    "cabin": "Srub / chatka",
    "schedule": "Program dne",
    "breakfast_label": "Popisek snídaně",
    "breakfast": "Snídaně",
    "snack1_label": "Popisek dopolední svačiny",
    "snack1": "Dopolední svačina",
    "lunch_label": "Popisek oběda",
    "lunch": "Oběd",
    "snack2_label": "Popisek odpolední svačiny",
    "snack2": "Odpolední svačina",
    "dinner_label": "Popisek večeře",
    "dinner": "Večeře",
}


def _text_box(
    box_id: str,
    label: str,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: int,
    *,
    bold=False,
    italic=False,
    underline=False,
    align="center",
    vertical_align="middle",
    tone="primary",
    source_key=None,
    blank_line=False,
    font_family="Georgia",
):
    return {
        "id": box_id,
        "label": label,
        "text": str(text or ""),
        "x": float(x),
        "y": float(y),
        "width": float(width),
        "height": float(height),
        "font_family": str(font_family or "Georgia"),
        "font_size": int(font_size),
        "bold": bool(bold),
        "italic": bool(italic),
        "underline": bool(underline),
        "strikeout": False,
        "align": align,
        "vertical_align": vertical_align,
        "rotation": 0,
        "color": "auto",
        "opacity": 100,
        "letter_spacing": 100,
        "font_stretch": 100,
        "case_transform": "none",
        "shadow": False,
        "tone": tone,
        "source_key": source_key,
        "blank_line": bool(blank_line),
    }


def default_diploma_text_boxes(kind: str, values: dict):
    """Výchozí rozložení všech pohyblivých textů na jednom diplomu A5."""
    common = [
        _text_box("title", "Hlavní nadpis", values.get("title", ""), 0.10, 0.205, 0.80, 0.065, 25, bold=True, source_key="title", font_family=PIRATE_FONT_FAMILY),
        _text_box("lead", "Text nad jménem", values.get("lead", ""), 0.16, 0.280, 0.68, 0.038, 13, source_key="lead"),
        _text_box("name", "Jméno piráta", values.get("name", ""), 0.09, 0.330, 0.82, 0.085, 34, bold=True, source_key="name", font_family=PIRATE_FONT_FAMILY),
        _text_box("award", "Text ocenění", values.get("award", ""), 0.13, 0.455, 0.74, 0.105, 13, italic=True, source_key="award"),
        _text_box("footer", "Spodní text", values.get("footer", ""), 0.12, 0.575, 0.76, 0.042, 12, source_key="footer"),
    ]
    if kind == "sports":
        common.extend(
            [
                _text_box("discipline_label", "Popisek disciplíny", values.get("discipline_label", ""), 0.13, 0.635, 0.23, 0.038, 10, align="left", source_key="discipline_label"),
                _text_box("discipline", "Disciplína", values.get("discipline", ""), 0.37, 0.635, 0.44, 0.038, 11, bold=True, align="left", source_key="discipline", blank_line=True),
                _text_box("placement_label", "Popisek umístění", values.get("placement_label", ""), 0.13, 0.690, 0.23, 0.038, 10, align="left", source_key="placement_label"),
                _text_box("placement", "Umístění", values.get("placement", ""), 0.37, 0.690, 0.44, 0.038, 11, bold=True, align="left", source_key="placement", blank_line=True),
                _text_box("date_label", "Popisek data", values.get("date_label", ""), 0.105, 0.770, 0.135, 0.046, 11, bold=True, align="left", source_key="date_label"),
                _text_box("date", "Datum", values.get("date", ""), 0.240, 0.770, 0.250, 0.046, 11, align="left", source_key="date", blank_line=True),
                _text_box("signature_label", "Popisek podpisu", values.get("signature_label", ""), 0.510, 0.770, 0.155, 0.046, 11, bold=True, align="right", source_key="signature_label"),
                _text_box("signature", "Podpis / vedoucí", values.get("signature", ""), 0.665, 0.770, 0.230, 0.046, 11, align="left", source_key="signature", blank_line=True),
            ]
        )
    else:
        common.extend(
            [
                _text_box("date_label", "Popisek data", values.get("date_label", ""), 0.105, 0.680, 0.135, 0.046, 11, bold=True, align="left", source_key="date_label"),
                _text_box("date", "Datum", values.get("date", ""), 0.240, 0.680, 0.250, 0.046, 11, align="left", source_key="date", blank_line=True),
                _text_box("signature_label", "Popisek podpisu", values.get("signature_label", ""), 0.510, 0.680, 0.155, 0.046, 11, bold=True, align="right", source_key="signature_label"),
                _text_box("signature", "Podpis / vedoucí", values.get("signature", ""), 0.665, 0.680, 0.230, 0.046, 11, align="left", source_key="signature", blank_line=True),
            ]
        )
    return common


def _default_cleaning_text_boxes(values: dict):
    """Všechna viditelná data tabulky jako samostatně pohyblivé texty."""
    boxes = [
        _text_box("title", "Hlavní nadpis", values.get("title", ""), 0.265, 0.052, 0.470, 0.060, 25, bold=True, source_key="title", font_family=PIRATE_FONT_FAMILY),
        _text_box("subtitle", "Podnadpis", values.get("subtitle", ""), 0.275, 0.112, 0.450, 0.036, 12, bold=True, source_key="subtitle"),
        _text_box("footer", "Spodní text", values.get("footer", ""), 0.275, 0.876, 0.450, 0.036, 11, bold=True, source_key="footer"),
    ]
    table_x, table_y, table_w, table_h = 0.145, 0.185, 0.710, 0.670
    weights = [1.70] + [1.0] * 14 + [1.25, 1.25]
    unit = table_w / sum(weights)
    row_h = table_h / 14.0
    x_positions = []
    cursor = table_x
    for weight in weights:
        x_positions.append((cursor, unit * weight))
        cursor += unit * weight

    headers = [values.get("cabin_header", "Chatka")]
    headers.extend([line.strip() for line in values.get("dates_text", "").splitlines() if line.strip()][:14])
    while len(headers) < 15:
        headers.append(f"Den {len(headers)}")
    headers.extend([values.get("total_header", "Součet"), values.get("rank_header", "Pořadí")])
    header_ids = ["cabin_header"] + [f"date_{index}" for index in range(1, 15)] + ["total_header", "rank_header"]
    for index, (text, box_id) in enumerate(zip(headers, header_ids)):
        x, width = x_positions[index]
        source_key = box_id if box_id in ("cabin_header", "total_header", "rank_header") else None
        boxes.append(_text_box(box_id, f"Záhlaví • {text}", text, x, table_y, width, row_h, 8, bold=True, source_key=source_key))

    cabins = [line.strip() for line in values.get("cabins_text", "").splitlines() if line.strip()][:13]
    while len(cabins) < 13:
        cabins.append(f"Chatka {len(cabins) + 1}")
    first_x, first_width = x_positions[0]
    for index, cabin in enumerate(cabins, 1):
        boxes.append(
            _text_box(
                f"cabin_{index}", f"Řádek chatky {index}", cabin,
                first_x, table_y + row_h * index, first_width, row_h, 8,
                bold=True, align="left",
            )
        )
    return boxes


def default_document_text_boxes(kind: str, values: dict):
    if kind in ("camp", "sports"):
        return default_diploma_text_boxes(kind, values)
    if kind == "cleaning":
        return _default_cleaning_text_boxes(values)
    if kind == "cleaning_award":
        return [
            _text_box("title", "Hlavní nadpis", values.get("title", ""), 0.18, 0.12, 0.64, 0.13, 30, bold=True, source_key="title", font_family=PIRATE_FONT_FAMILY),
            _text_box("placement", "Umístění", values.get("placement", ""), 0.25, 0.265, 0.50, 0.10, 25, bold=True, source_key="placement"),
            _text_box("lead", "Text nad jménem", values.get("lead", ""), 0.30, 0.375, 0.40, 0.055, 14, source_key="lead"),
            _text_box("name", "Jméno chatky / posádky", values.get("name", ""), 0.22, 0.445, 0.62, 0.12, 28, bold=True, source_key="name", blank_line=True, font_family=PIRATE_FONT_FAMILY),
            _text_box("award", "Text ocenění", values.get("award", ""), 0.22, 0.590, 0.62, 0.08, 16, bold=True, italic=True, source_key="award"),
            _text_box("cabin_label", "Popisek srubu", values.get("cabin_label", ""), 0.22, 0.735, 0.13, 0.065, 12, bold=True, align="right", source_key="cabin_label"),
            _text_box("cabin", "Srub / chatka", values.get("cabin", ""), 0.36, 0.735, 0.22, 0.065, 13, bold=True, align="left", source_key="cabin", blank_line=True),
            _text_box("date_label", "Popisek data", values.get("date_label", ""), 0.61, 0.735, 0.13, 0.065, 12, bold=True, align="right", source_key="date_label"),
            _text_box("date", "Datum", values.get("date", ""), 0.75, 0.735, 0.18, 0.065, 13, align="left", source_key="date", blank_line=True),
            _text_box("signature_label", "Popisek podpisu", values.get("signature_label", ""), 0.40, 0.835, 0.15, 0.055, 11, bold=True, align="right", source_key="signature_label"),
            _text_box("signature", "Podpis", values.get("signature", ""), 0.56, 0.835, 0.24, 0.055, 12, align="left", source_key="signature", blank_line=True),
        ]
    if kind == "daily":
        return [
            _text_box("title", "Hlavní nadpis", values.get("title", ""), 0.14, 0.075, 0.72, 0.09, 30, bold=True, source_key="title", font_family=PIRATE_FONT_FAMILY),
            _text_box("subtitle", "Podnadpis", values.get("subtitle", ""), 0.16, 0.165, 0.68, 0.055, 14, italic=True, source_key="subtitle"),
            _text_box("date", "Datum / název dne", values.get("date", ""), 0.25, 0.225, 0.50, 0.055, 14, bold=True, source_key="date", blank_line=True),
            _text_box("schedule", "Program dne", values.get("schedule", ""), 0.12, 0.295, 0.76, 0.545, 15, align="center", vertical_align="top", source_key="schedule"),
            _text_box("footer", "Spodní text", values.get("footer", ""), 0.12, 0.875, 0.76, 0.065, 11, italic=True, source_key="footer"),
        ]
    if kind == "meal":
        boxes = [
            _text_box("title", "Hlavní nadpis", values.get("title", ""), 0.18, 0.065, 0.64, 0.09, 31, bold=True, source_key="title", font_family=PIRATE_FONT_FAMILY),
            _text_box("date_label", "Popisek dne", values.get("date_label", ""), 0.25, 0.155, 0.16, 0.052, 13, bold=True, align="right", source_key="date_label"),
            _text_box("date", "Den / datum", values.get("date", ""), 0.42, 0.155, 0.33, 0.052, 13, align="left", source_key="date", blank_line=True),
        ]
        rows = (
            ("breakfast", 0.235), ("snack1", 0.365), ("lunch", 0.495),
            ("snack2", 0.625), ("dinner", 0.755),
        )
        for key, y in rows:
            label_key = f"{key}_label"
            boxes.append(_text_box(label_key, FIELD_LABELS[label_key], values.get(label_key, ""), 0.13, y, 0.74, 0.045, 15, bold=True, align="left", source_key=label_key, font_family=PIRATE_FONT_FAMILY))
            boxes.append(_text_box(key, FIELD_LABELS[key], values.get(key, ""), 0.16, y + 0.045, 0.68, 0.075, 13, align="left", vertical_align="top", source_key=key, blank_line=True))
        boxes.append(_text_box("footer", "Spodní text", values.get("footer", ""), 0.15, 0.910, 0.70, 0.050, 12, bold=True, italic=True, source_key="footer"))
        return boxes
    return []


class DiplomaDialog(PirateModuleDialog):
    """Moderní editor, živý A4 náhled, PDF a tisk táborových listin."""

    def __init__(self, owner_window, icons_path: str):
        pirate_font_family = _ensure_pirate_font(icons_path)
        super().__init__(
            owner_window,
            "menu_BG.png",
            (
                (0.058, 0.404, 0.48),
                (0.949, 0.838, 1.25),
            ),
        )
        self.icons_path = icons_path
        self.pirate_font_family = pirate_font_family
        self.document_values = copy.deepcopy(DOCUMENT_DEFAULTS)
        self.selected_variants = {
            "camp": "A", "sports": "A", "cleaning": "B",
            "cleaning_award": "A", "daily": "A", "meal": "A",
        }
        self.economical_print = {kind: False for kind in self.document_values}
        self.show_logo = {kind: True for kind in self.document_values}
        self.text_boxes = {
            kind: default_document_text_boxes(kind, values)
            for kind, values in self.document_values.items()
        }
        self.selected_text_box = {kind: "title" for kind in self.document_values}
        self._custom_text_counter = 0
        self._updating_text_controls = False
        self.diploma_kind = "camp"
        self.field_widgets = {}
        self._rebuilding_form = False
        self.setWindowTitle("Pirátské tiskové studio")
        self.setMinimumSize(940, 620)
        self.resize(1380, 820)
        self._build_ui()
        self.apply_pirate_glass()
        self.show_choices()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.page_stack = QStackedWidget(self)
        self.page_stack.setStyleSheet("QStackedWidget { background:transparent; border:none; }")
        self.choice_page = self._create_choice_page()
        self.editor_page = self._create_editor_page()
        self.page_stack.addWidget(self.choice_page)
        self.page_stack.addWidget(self.editor_page)
        root.addWidget(self.page_stack)

    def _create_choice_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(42, 32, 42, 36)
        layout.setSpacing(12)

        title = QLabel("DIPLOMY A TÁBOROVÉ LISTINY", page)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "color:#f4dea4; background:transparent; font-family:Georgia; "
            "font-size:29px; font-weight:bold; letter-spacing:2px;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Vyber listinu, uprav všechny texty a připrav finální A4 k tisku.", page)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "color:#d9c49a; background:transparent; font-family:Georgia; "
            "font-size:13px; font-style:italic;"
        )
        layout.addWidget(subtitle)
        layout.addStretch(1)

        cards = QGridLayout()
        cards.setHorizontalSpacing(20)
        cards.setVerticalSpacing(16)
        choices = (
            ("sports", "Diplom za sportovní den", "4 motivy • volitelný šetrný tisk • 2× A5 na A4", "semafor.png"),
            ("camp", "Diplom za tábor", "3 motivy • volitelný šetrný tisk • 2× A5 na A4", "logo.png"),
            ("cleaning", "Hodnocení úklidu", "Varianta B • volitelný šetrný tisk • jeden list A4", "pirate_coin.png"),
            ("cleaning_award", "Diplom za úklid", "2 motivy • šetrný tisk • 2× A5 na A4", "anchor.png"),
            ("daily", "Denní program", "2 motivy • upravitelný A4 program dne", "compass.png"),
            ("meal", "Jídelníček", "2 motivy • upravitelný A4 jídelní lístek", "tiskarna.png"),
        )
        for index, (kind, heading, description, icon) in enumerate(choices):
            card = PirateMenuCard(heading, description, os.path.join(self.icons_path, icon), page)
            card.setMinimumSize(230, 150)
            card.setMaximumSize(370, 180)
            if kind == "sports":
                card.clicked.connect(self.show_sports_diploma)
            elif kind == "camp":
                card.clicked.connect(self.show_camp_diploma)
            elif kind == "cleaning":
                card.clicked.connect(self.show_cleaning_sheet)
            elif kind == "cleaning_award":
                card.clicked.connect(self.show_cleaning_award)
            elif kind == "daily":
                card.clicked.connect(self.show_daily_program)
            else:
                card.clicked.connect(self.show_meal_plan)
            cards.addWidget(card, index // 3, index % 3, Qt.AlignCenter)
        layout.addLayout(cards)
        layout.addStretch(2)
        return page

    def _create_editor_page(self):
        page = QWidget(self)
        page.setStyleSheet("background:transparent;")
        root = QVBoxLayout(page)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(10)

        heading_row = QHBoxLayout()
        back_button = QPushButton("‹  ZPĚT NA VÝBĚR", page)
        back_button.setCursor(Qt.PointingHandCursor)
        back_button.setFixedHeight(38)
        back_button.clicked.connect(self.show_choices)
        heading_row.addWidget(back_button, 0, Qt.AlignTop)

        heading_column = QVBoxLayout()
        self.editor_title = QLabel("PIRÁTSKÉ TISKOVÉ STUDIO", page)
        self.editor_title.setStyleSheet(
            "color:#f4dea4; background:transparent; font-family:Georgia; "
            "font-size:24px; font-weight:bold; letter-spacing:2px;"
        )
        self.editor_subtitle = QLabel("Všechny nápisy vlevo se okamžitě mění ve finálním náhledu.", page)
        self.editor_subtitle.setStyleSheet(
            "color:#d9c49a; background:transparent; font-family:Georgia; "
            "font-size:11px; font-style:italic;"
        )
        heading_column.addWidget(self.editor_title)
        heading_column.addWidget(self.editor_subtitle)
        heading_row.addLayout(heading_column, 1)
        root.addLayout(heading_row)

        body = QHBoxLayout()
        body.setSpacing(16)

        form_panel = QFrame(page)
        form_panel.setObjectName("diplomaFormPanel")
        form_panel.setMinimumWidth(410)
        form_panel.setMaximumWidth(510)
        form_panel.setStyleSheet(
            "QFrame#diplomaFormPanel { background:rgba(3,20,29,190); "
            "border:1px solid rgba(205,159,78,195); border-radius:14px; }"
        )
        form_box = QVBoxLayout(form_panel)
        form_box.setContentsMargins(15, 14, 15, 14)
        form_box.setSpacing(9)

        self.output_hint = QLabel("", form_panel)
        self.output_hint.setWordWrap(True)
        self.output_hint.setStyleSheet(
            "color:#f3d79a; background:rgba(10,47,58,120); border:1px solid rgba(205,159,78,120); "
            "border-radius:8px; padding:8px; font-family:Georgia; font-size:11px; font-weight:bold;"
        )
        form_box.addWidget(self.output_hint)

        scroll = QScrollArea(form_panel)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.fields_scroll = scroll
        self.fields_page = QWidget(scroll)
        self.fields_page.setStyleSheet("background:transparent;")
        self.fields_layout = QFormLayout(self.fields_page)
        self.fields_layout.setContentsMargins(4, 3, 10, 4)
        self.fields_layout.setVerticalSpacing(7)
        self.fields_layout.setHorizontalSpacing(5)
        self.fields_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        self.fields_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.fields_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignBottom)
        scroll.setWidget(self.fields_page)
        form_box.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        save_button = QPushButton("ULOŽIT PDF", form_panel)
        save_button.clicked.connect(self._save_pdf)
        print_button = QPushButton("TISKNOUT", form_panel)
        print_button.setObjectName("primaryButton")
        print_button.clicked.connect(self._print_document)
        button_row.addWidget(save_button)
        button_row.addWidget(print_button)
        form_box.addLayout(button_row)
        body.addWidget(form_panel)

        preview_frame = QFrame(page)
        preview_frame.setObjectName("diplomaPreviewFrame")
        preview_frame.setStyleSheet(
            "QFrame#diplomaPreviewFrame { background:rgba(2,13,21,145); "
            "border:1px solid rgba(205,159,78,180); border-radius:14px; }"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(9, 9, 9, 9)
        preview_label = QLabel("ŽIVÝ NÁHLED FINÁLNÍHO LISTU A4", preview_frame)
        preview_label.setStyleSheet(
            "color:#f3d79a; background:transparent; border:none; font-family:Georgia; "
            "font-size:13px; font-weight:bold; padding-left:4px;"
        )
        preview_layout.addWidget(preview_label)
        self.preview = DiplomaSheetPreview(preview_frame)
        self.preview.textBoxSelected.connect(self._preview_text_box_selected)
        self.preview.textBoxGeometryChanged.connect(self._preview_text_box_geometry_changed)
        self.preview.textBoxDeleteRequested.connect(self._delete_selected_text_box)
        preview_layout.addWidget(self.preview, 1)
        body.addWidget(preview_frame, 1)
        root.addLayout(body, 1)
        return page

    def _clear_fields(self):
        while self.fields_layout.rowCount():
            self.fields_layout.removeRow(0)
        self.field_widgets = {}

    def _field_label(self, text: str):
        label = QLabel(text, self.fields_page)
        label.setWordWrap(True)
        label.setStyleSheet(
            "color:#ead8b3; background:transparent; border:none; "
            "font-family:Georgia; font-size:10px; font-weight:bold;"
        )
        return label

    def _add_line_field(self, key: str):
        field = QLineEdit(self.fields_page)
        field.setText(str(self.document_values[self.diploma_kind].get(key, "")))
        field.textChanged.connect(lambda text, field_key=key: self._field_changed(field_key, text))
        self.field_widgets[key] = field
        self.fields_layout.addRow(self._field_label(FIELD_LABELS[key]), field)

    def _add_multiline_field(self, key: str, height: int):
        field = QPlainTextEdit(self.fields_page)
        field.setPlainText(str(self.document_values[self.diploma_kind].get(key, "")))
        field.setFixedHeight(height)
        field.textChanged.connect(
            lambda field_key=key, widget=field: self._field_changed(field_key, widget.toPlainText())
        )
        self.field_widgets[key] = field
        self.fields_layout.addRow(self._field_label(FIELD_LABELS[key]), field)

    def _text_box_by_id(self, box_id: str):
        if self.diploma_kind not in self.text_boxes:
            return None
        for box in self.text_boxes[self.diploma_kind]:
            if str(box.get("id", "")) == str(box_id):
                return box
        return None

    def _current_text_box(self):
        return self._text_box_by_id(self.selected_text_box.get(self.diploma_kind, ""))

    @staticmethod
    def _text_box_combo_label(box: dict):
        label = str(box.get("label", "Text"))
        text = " ".join(str(box.get("text", "")).split())
        if text and text.casefold() != label.casefold():
            label += f" — {text[:28]}" + ("…" if len(text) > 28 else "")
        return label

    def _control_pair(self, first_label: str, first_widget, second_label: str, second_widget):
        row = QWidget(self.fields_page)
        row.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        first = QLabel(first_label, row)
        second = QLabel(second_label, row)
        for label in (first, second):
            label.setStyleSheet("color:#d9c49a; background:transparent; border:none; font-size:9px;")
        layout.addWidget(first)
        layout.addWidget(first_widget, 1)
        layout.addWidget(second)
        layout.addWidget(second_widget, 1)
        return row

    def _add_text_editor_controls(self):
        help_label = QLabel(
            "Klikni na text přímo v náhledu a táhni ho. Tyrkysový rámeček je jen pomůcka a netiskne se.",
            self.fields_page,
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet(
            "color:#a9e2e7; background:rgba(8,45,55,110); border:1px solid rgba(74,188,199,100); "
            "border-radius:7px; padding:7px; font-size:10px;"
        )
        self.fields_layout.addRow(help_label)

        self.text_box_combo = QComboBox(self.fields_page)
        self.text_box_combo.currentIndexChanged.connect(self._text_box_combo_changed)
        self.fields_layout.addRow(self._field_label("Vybrané textové pole"), self.text_box_combo)

        self.text_content = QPlainTextEdit(self.fields_page)
        self.text_content.setFixedHeight(70)
        self.text_content.setPlaceholderText("Napiš text, který se má objevit na tiskovině…")
        self.text_content.setStyleSheet(
            "QPlainTextEdit { color:#f0e2c0; background:rgba(2,14,22,118); "
            "border:1px solid rgba(205,159,78,190); border-radius:9px; padding:6px; "
            "selection-background-color:rgba(23,108,118,190); }"
        )
        self.text_content.textChanged.connect(self._text_content_changed)
        self.fields_layout.addRow(self._field_label("Text"), self.text_content)

        self.font_combo = QFontComboBox(self.fields_page)
        self.font_combo.currentFontChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(self._field_label("Styl písma"), self.font_combo)

        self.pirate_font_button = QPushButton("☠  POUŽÍT PIRÁTSKÉ PÍSMO — PIRATA ONE", self.fields_page)
        self.pirate_font_button.setToolTip("Nastaví na vybraný text přibalené písmo Pirata One.")
        self.pirate_font_button.clicked.connect(self._use_pirate_font)
        self.fields_layout.addRow(self.pirate_font_button)

        self.font_size_spin = QSpinBox(self.fields_page)
        self.font_size_spin.setRange(6, 96)
        self.font_size_spin.setSuffix(" b")
        self.font_size_spin.valueChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(self._field_label("Velikost písma"), self.font_size_spin)

        color_row = QWidget(self.fields_page)
        color_row.setStyleSheet("background:transparent;")
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(5)
        self.text_color_button = QPushButton("VYBRAT BARVU", color_row)
        self.text_color_button.clicked.connect(self._choose_text_color)
        self.auto_color_button = QPushButton("AUTOMATICKÁ", color_row)
        self.auto_color_button.setToolTip("Použije světlou nebo tmavou barvu podle zvoleného pozadí.")
        self.auto_color_button.clicked.connect(self._use_automatic_text_color)
        color_layout.addWidget(self.text_color_button, 1)
        color_layout.addWidget(self.auto_color_button, 1)
        self.fields_layout.addRow(self._field_label("Barva písma"), color_row)

        style_row = QWidget(self.fields_page)
        style_row.setStyleSheet("background:transparent;")
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.setSpacing(5)
        self.bold_button = QToolButton(style_row)
        self.bold_button.setText("B")
        self.bold_button.setToolTip("Tučné písmo")
        self.bold_button.setCheckable(True)
        tool_style = (
            "QToolButton { color:#f4dea4; background:rgba(5,35,44,150); "
            "border:1px solid rgba(205,159,78,180); border-radius:7px; min-width:32px; min-height:28px; } "
            "QToolButton:hover { background:rgba(17,79,88,190); } "
            "QToolButton:checked { color:#fff4c7; background:rgba(171,111,31,205); border-color:#f0c66b; }"
        )
        self.bold_button.setStyleSheet(tool_style + " QToolButton { font-weight:bold; }")
        self.italic_button = QToolButton(style_row)
        self.italic_button.setText("I")
        self.italic_button.setToolTip("Kurzíva")
        self.italic_button.setCheckable(True)
        self.italic_button.setStyleSheet(tool_style + " QToolButton { font-style:italic; }")
        self.underline_button = QToolButton(style_row)
        self.underline_button.setText("U")
        self.underline_button.setToolTip("Podtržené písmo")
        self.underline_button.setCheckable(True)
        self.underline_button.setStyleSheet(tool_style + " QToolButton { text-decoration:underline; }")
        self.strike_button = QToolButton(style_row)
        self.strike_button.setText("S")
        self.strike_button.setToolTip("Přeškrtnuté písmo")
        self.strike_button.setCheckable(True)
        self.strike_button.setStyleSheet(tool_style + " QToolButton { text-decoration:line-through; }")
        for button in (self.bold_button, self.italic_button, self.underline_button, self.strike_button):
            button.toggled.connect(self._text_style_changed)
            style_layout.addWidget(button)
        self.align_combo = QComboBox(style_row)
        self.align_combo.addItem("Vlevo", "left")
        self.align_combo.addItem("Na střed", "center")
        self.align_combo.addItem("Vpravo", "right")
        self.align_combo.currentIndexChanged.connect(self._text_style_changed)
        style_layout.addWidget(self.align_combo, 1)
        self.fields_layout.addRow(self._field_label("Formátování"), style_row)

        self.vertical_align_combo = QComboBox(self.fields_page)
        self.vertical_align_combo.addItem("Nahoru", "top")
        self.vertical_align_combo.addItem("Doprostřed", "middle")
        self.vertical_align_combo.addItem("Dolů", "bottom")
        self.vertical_align_combo.currentIndexChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(self._field_label("Svislé zarovnání"), self.vertical_align_combo)

        self.case_combo = QComboBox(self.fields_page)
        self.case_combo.addItem("Beze změny", "none")
        self.case_combo.addItem("VELKÁ PÍSMENA", "upper")
        self.case_combo.addItem("malá písmena", "lower")
        self.case_combo.addItem("Velká Počáteční Písmena", "title")
        self.case_combo.currentIndexChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(self._field_label("Velikost písmen"), self.case_combo)

        self.letter_spacing_spin = QSpinBox(self.fields_page)
        self.letter_spacing_spin.setRange(50, 300)
        self.letter_spacing_spin.setSuffix(" %")
        self.letter_spacing_spin.setToolTip("Rozestup mezi jednotlivými písmeny")
        self.letter_spacing_spin.valueChanged.connect(self._text_style_changed)
        self.font_stretch_spin = QSpinBox(self.fields_page)
        self.font_stretch_spin.setRange(50, 200)
        self.font_stretch_spin.setSuffix(" %")
        self.font_stretch_spin.setToolTip("Vodorovné zúžení nebo roztažení znaků")
        self.font_stretch_spin.valueChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(
            self._field_label("Tvar písma"),
            self._control_pair("Mezery", self.letter_spacing_spin, "Šířka", self.font_stretch_spin),
        )

        self.opacity_spin = QSpinBox(self.fields_page)
        self.opacity_spin.setRange(5, 100)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.valueChanged.connect(self._text_style_changed)
        self.shadow_checkbox = QCheckBox("Jemný stín pod písmem", self.fields_page)
        self.shadow_checkbox.toggled.connect(self._text_style_changed)
        effects = QWidget(self.fields_page)
        effects.setStyleSheet("background:transparent;")
        effects_layout = QVBoxLayout(effects)
        effects_layout.setContentsMargins(0, 0, 0, 0)
        effects_layout.setSpacing(4)
        effects_layout.addWidget(self.opacity_spin)
        effects_layout.addWidget(self.shadow_checkbox)
        self.fields_layout.addRow(self._field_label("Průhlednost a efekt"), effects)

        self.rotation_spin = QSpinBox(self.fields_page)
        self.rotation_spin.setRange(-180, 180)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.valueChanged.connect(self._text_style_changed)
        self.fields_layout.addRow(self._field_label("Natočení"), self.rotation_spin)

        self.position_x_spin = QSpinBox(self.fields_page)
        self.position_y_spin = QSpinBox(self.fields_page)
        self.width_spin = QSpinBox(self.fields_page)
        self.height_spin = QSpinBox(self.fields_page)
        for control in (self.position_x_spin, self.position_y_spin):
            control.setRange(0, 100)
            control.setSuffix(" %")
            control.valueChanged.connect(self._text_geometry_control_changed)
        for control in (self.width_spin, self.height_spin):
            control.setRange(2, 100)
            control.setSuffix(" %")
            control.valueChanged.connect(self._text_geometry_control_changed)
        self.fields_layout.addRow(
            self._field_label("Pozice"),
            self._control_pair("X", self.position_x_spin, "Y", self.position_y_spin),
        )
        self.fields_layout.addRow(
            self._field_label("Velikost pole"),
            self._control_pair("Š", self.width_spin, "V", self.height_spin),
        )

        button_row = QWidget(self.fields_page)
        button_row.setStyleSheet("background:transparent;")
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 2, 0, 0)
        button_layout.setSpacing(5)
        add_button = QPushButton("+ PŘIDAT", button_row)
        add_button.setToolTip("Přidat nové textové pole")
        add_button.clicked.connect(self._add_text_box)
        duplicate_button = QPushButton("KOPIE", button_row)
        duplicate_button.setToolTip("Vytvořit kopii vybraného pole")
        duplicate_button.clicked.connect(self._duplicate_selected_text_box)
        delete_button = QPushButton("ODSTRANIT", button_row)
        delete_button.setToolTip("Odstranit vybrané textové pole")
        delete_button.clicked.connect(lambda: self._delete_selected_text_box())
        button_layout.addWidget(add_button)
        button_layout.addWidget(duplicate_button)
        button_layout.addWidget(delete_button)
        self.fields_layout.addRow(button_row)

        layer_row = QWidget(self.fields_page)
        layer_row.setStyleSheet("background:transparent;")
        layer_layout = QHBoxLayout(layer_row)
        layer_layout.setContentsMargins(0, 0, 0, 0)
        layer_layout.setSpacing(5)
        self.send_backward_button = QPushButton("O VRSTVU NÍŽ", layer_row)
        self.send_backward_button.clicked.connect(lambda: self._move_selected_text_layer(-1))
        self.bring_forward_button = QPushButton("O VRSTVU VÝŠ", layer_row)
        self.bring_forward_button.clicked.connect(lambda: self._move_selected_text_layer(1))
        layer_layout.addWidget(self.send_backward_button)
        layer_layout.addWidget(self.bring_forward_button)
        self.fields_layout.addRow(self._field_label("Pořadí textů"), layer_row)

        reset_format_button = QPushButton("OBNOVIT FORMÁT VYBRANÉHO TEXTU", self.fields_page)
        reset_format_button.clicked.connect(self._reset_selected_text_format)
        self.reset_format_button = reset_format_button
        self.fields_layout.addRow(reset_format_button)

        reset_button = QPushButton("OBNOVIT VÝCHOZÍ ROZLOŽENÍ TEXTŮ", self.fields_page)
        reset_button.clicked.connect(self._reset_text_box_layout)
        self.fields_layout.addRow(reset_button)
        self._refresh_text_box_combo()

    def _refresh_text_box_combo(self):
        if not hasattr(self, "text_box_combo") or self.diploma_kind not in self.text_boxes:
            return
        selected = self.selected_text_box.get(self.diploma_kind, "")
        self.text_box_combo.blockSignals(True)
        self.text_box_combo.clear()
        for box in self.text_boxes[self.diploma_kind]:
            self.text_box_combo.addItem(self._text_box_combo_label(box), box.get("id", ""))
        index = self.text_box_combo.findData(selected)
        if index < 0 and self.text_box_combo.count():
            index = 0
            self.selected_text_box[self.diploma_kind] = str(self.text_box_combo.itemData(0))
        self.text_box_combo.setCurrentIndex(index)
        self.text_box_combo.blockSignals(False)
        self._load_selected_text_box()

    def _set_text_controls_enabled(self, enabled: bool):
        for name in (
            "text_content", "font_combo", "font_size_spin", "bold_button", "italic_button",
            "underline_button", "strike_button", "align_combo", "vertical_align_combo",
            "case_combo", "letter_spacing_spin", "font_stretch_spin", "opacity_spin",
            "shadow_checkbox", "rotation_spin", "position_x_spin", "position_y_spin",
            "width_spin", "height_spin", "pirate_font_button", "text_color_button",
            "auto_color_button", "send_backward_button", "bring_forward_button",
            "reset_format_button",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(enabled)

    def _load_selected_text_box(self):
        box = self._current_text_box()
        self._updating_text_controls = True
        self._set_text_controls_enabled(box is not None)
        if box is not None:
            self.text_content.setPlainText(str(box.get("text", "")))
            self.font_combo.setCurrentFont(QFont(str(box.get("font_family", "Georgia"))))
            self.font_size_spin.setValue(int(round(float(box.get("font_size", 18)))))
            self.bold_button.setChecked(bool(box.get("bold", False)))
            self.italic_button.setChecked(bool(box.get("italic", False)))
            self.underline_button.setChecked(bool(box.get("underline", False)))
            self.strike_button.setChecked(bool(box.get("strikeout", False)))
            align_index = self.align_combo.findData(str(box.get("align", "center")))
            self.align_combo.setCurrentIndex(max(0, align_index))
            vertical_index = self.vertical_align_combo.findData(str(box.get("vertical_align", "middle")))
            self.vertical_align_combo.setCurrentIndex(max(0, vertical_index))
            case_index = self.case_combo.findData(str(box.get("case_transform", "none")))
            self.case_combo.setCurrentIndex(max(0, case_index))
            self.letter_spacing_spin.setValue(int(round(float(box.get("letter_spacing", 100)))))
            self.font_stretch_spin.setValue(int(round(float(box.get("font_stretch", 100)))))
            self.opacity_spin.setValue(int(round(float(box.get("opacity", 100)))))
            self.shadow_checkbox.setChecked(bool(box.get("shadow", False)))
            self.rotation_spin.setValue(int(round(float(box.get("rotation", 0)))))
            self.position_x_spin.setValue(int(round(float(box.get("x", 0)) * 100)))
            self.position_y_spin.setValue(int(round(float(box.get("y", 0)) * 100)))
            self.width_spin.setValue(int(round(float(box.get("width", 0.5)) * 100)))
            self.height_spin.setValue(int(round(float(box.get("height", 0.08)) * 100)))
            self._refresh_text_color_button(box)
        self._updating_text_controls = False
        if hasattr(self, "preview"):
            self.preview.set_selected_text_box(self.selected_text_box.get(self.diploma_kind, ""))

    def _text_box_combo_changed(self):
        if self._rebuilding_form or self._updating_text_controls:
            return
        self.selected_text_box[self.diploma_kind] = str(self.text_box_combo.currentData() or "")
        self._load_selected_text_box()

    def _text_content_changed(self):
        if self._updating_text_controls or self._rebuilding_form:
            return
        box = self._current_text_box()
        if box is None:
            return
        box["text"] = self.text_content.toPlainText()
        source_key = box.get("source_key")
        if source_key:
            self.document_values[self.diploma_kind][source_key] = box["text"]
        current_index = self.text_box_combo.currentIndex()
        if current_index >= 0:
            self.text_box_combo.setItemText(current_index, self._text_box_combo_label(box))
        self._update_preview()

    def _text_style_changed(self, *_args):
        if self._updating_text_controls or self._rebuilding_form:
            return
        box = self._current_text_box()
        if box is None:
            return
        box.update(
            {
                "font_family": self.font_combo.currentFont().family(),
                "font_size": self.font_size_spin.value(),
                "bold": self.bold_button.isChecked(),
                "italic": self.italic_button.isChecked(),
                "underline": self.underline_button.isChecked(),
                "strikeout": self.strike_button.isChecked(),
                "align": self.align_combo.currentData() or "center",
                "vertical_align": self.vertical_align_combo.currentData() or "middle",
                "case_transform": self.case_combo.currentData() or "none",
                "letter_spacing": self.letter_spacing_spin.value(),
                "font_stretch": self.font_stretch_spin.value(),
                "opacity": self.opacity_spin.value(),
                "shadow": self.shadow_checkbox.isChecked(),
                "rotation": self.rotation_spin.value(),
            }
        )
        self._update_preview()

    def _use_pirate_font(self):
        if self._current_text_box() is None:
            return
        self.font_combo.setCurrentFont(QFont(self.pirate_font_family or PIRATE_FONT_FAMILY))
        self._text_style_changed()

    def _refresh_text_color_button(self, box=None):
        if not hasattr(self, "text_color_button"):
            return
        box = box or self._current_text_box()
        requested = str((box or {}).get("color", "auto"))
        if requested == "auto" or not QColor(requested).isValid():
            self.text_color_button.setText("VYBRAT BARVU…")
            self.text_color_button.setStyleSheet("")
            return
        color = QColor(requested)
        foreground = "#081118" if color.lightness() > 150 else "#fff4d0"
        self.text_color_button.setText(color.name().upper())
        self.text_color_button.setStyleSheet(
            f"QPushButton {{ background:{color.name()}; color:{foreground}; border:2px solid #e6bd68; }}"
        )

    def _choose_text_color(self):
        box = self._current_text_box()
        if box is None:
            return
        current = QColor(str(box.get("color", "")))
        if not current.isValid():
            current = QColor("#f3d08a")
        selected = QColorDialog.getColor(current, self, "Vyber barvu písma")
        if not selected.isValid():
            return
        box["color"] = selected.name()
        self._refresh_text_color_button(box)
        self._update_preview()

    def _use_automatic_text_color(self):
        box = self._current_text_box()
        if box is None:
            return
        box["color"] = "auto"
        self._refresh_text_color_button(box)
        self._update_preview()

    def _move_selected_text_layer(self, direction: int):
        box = self._current_text_box()
        if box is None:
            return
        boxes = self.text_boxes[self.diploma_kind]
        index = boxes.index(box)
        target = max(0, min(len(boxes) - 1, index + (1 if direction > 0 else -1)))
        if target == index:
            return
        boxes.insert(target, boxes.pop(index))
        self._refresh_text_box_combo()
        self._update_preview()

    def _reset_selected_text_format(self):
        box = self._current_text_box()
        if box is None:
            return
        default_box = next(
            (
                item
                for item in default_document_text_boxes(
                    self.diploma_kind, self.document_values[self.diploma_kind]
                )
                if item.get("id") == box.get("id")
            ),
            None,
        )
        formatting_keys = (
            "font_family", "font_size", "bold", "italic", "underline", "strikeout",
            "align", "vertical_align", "rotation", "color", "opacity", "letter_spacing",
            "font_stretch", "case_transform", "shadow",
        )
        if default_box is None:
            default_box = _text_box(
                "format", "Text", "", 0, 0, 0.5, 0.08, 18,
                bold=True, font_family=self.pirate_font_family,
            )
        for key in formatting_keys:
            box[key] = copy.deepcopy(default_box.get(key))
        self._load_selected_text_box()
        self._update_preview()

    def _text_geometry_control_changed(self, *_args):
        if self._updating_text_controls or self._rebuilding_form:
            return
        box = self._current_text_box()
        if box is None:
            return
        width = max(0.02, self.width_spin.value() / 100.0)
        height = max(0.02, self.height_spin.value() / 100.0)
        x = min(self.position_x_spin.value() / 100.0, 1.0 - width)
        y = min(self.position_y_spin.value() / 100.0, 1.0 - height)
        x = max(0.0, x)
        y = max(0.0, y)
        box.update({"x": x, "y": y, "width": width, "height": height})
        self._updating_text_controls = True
        self.position_x_spin.setValue(int(round(x * 100)))
        self.position_y_spin.setValue(int(round(y * 100)))
        self._updating_text_controls = False
        self._update_preview()

    def _preview_text_box_selected(self, box_id: str):
        if self.diploma_kind not in self.text_boxes:
            return
        self.selected_text_box[self.diploma_kind] = str(box_id or "")
        if hasattr(self, "text_box_combo"):
            self._updating_text_controls = True
            self.text_box_combo.setCurrentIndex(self.text_box_combo.findData(box_id))
            self._updating_text_controls = False
            self._load_selected_text_box()

    def _preview_text_box_geometry_changed(self, box_id: str, x: float, y: float, width: float, height: float):
        box = self._text_box_by_id(box_id)
        if box is None:
            return
        box.update({"x": x, "y": y, "width": width, "height": height})
        self._updating_text_controls = True
        self.position_x_spin.setValue(int(round(x * 100)))
        self.position_y_spin.setValue(int(round(y * 100)))
        self.width_spin.setValue(int(round(width * 100)))
        self.height_spin.setValue(int(round(height * 100)))
        self._updating_text_controls = False
        self._update_preview()

    def _next_custom_text_id(self):
        self._custom_text_counter += 1
        return f"custom_{self._custom_text_counter}"

    def _select_text_box(self, box_id: str):
        self.selected_text_box[self.diploma_kind] = str(box_id)
        self._refresh_text_box_combo()
        self._update_preview()

    def _add_text_box(self):
        box_id = self._next_custom_text_id()
        box = _text_box(
            box_id, "Vlastní text", "NOVÝ TEXT", 0.25, 0.500, 0.50, 0.075, 18,
            bold=True, source_key=None, font_family=self.pirate_font_family,
        )
        self.text_boxes[self.diploma_kind].append(box)
        self._select_text_box(box_id)

    def _duplicate_selected_text_box(self):
        source = self._current_text_box()
        if source is None:
            return
        box = copy.deepcopy(source)
        box_id = self._next_custom_text_id()
        box["id"] = box_id
        box["label"] = "Kopie textu"
        box["source_key"] = None
        box["x"] = min(1.0 - float(box.get("width", 0.5)), float(box.get("x", 0.2)) + 0.025)
        box["y"] = min(1.0 - float(box.get("height", 0.08)), float(box.get("y", 0.2)) + 0.025)
        self.text_boxes[self.diploma_kind].append(box)
        self._select_text_box(box_id)

    def _delete_selected_text_box(self, box_id: str = ""):
        if self.diploma_kind not in self.text_boxes:
            return
        target = str(box_id or self.selected_text_box.get(self.diploma_kind, ""))
        boxes = self.text_boxes[self.diploma_kind]
        removed = self._text_box_by_id(target)
        if removed is None:
            return
        source_key = removed.get("source_key")
        if source_key:
            self.document_values[self.diploma_kind][source_key] = ""
        self.text_boxes[self.diploma_kind] = [box for box in boxes if str(box.get("id", "")) != target]
        self.selected_text_box[self.diploma_kind] = (
            str(self.text_boxes[self.diploma_kind][0].get("id", "")) if self.text_boxes[self.diploma_kind] else ""
        )
        self._refresh_text_box_combo()
        self._update_preview()

    def _reset_text_box_layout(self):
        custom_boxes = [
            copy.deepcopy(box)
            for box in self.text_boxes.get(self.diploma_kind, [])
            if not box.get("source_key")
        ]
        self.text_boxes[self.diploma_kind] = (
            default_document_text_boxes(self.diploma_kind, self.document_values[self.diploma_kind])
            + custom_boxes
        )
        self.selected_text_box[self.diploma_kind] = "title"
        self._refresh_text_box_combo()
        self._update_preview()

    def _rebuild_fields(self):
        self._rebuilding_form = True
        self._clear_fields()

        self.variant_combo = QComboBox(self.fields_page)
        for variant, label in VARIANTS[self.diploma_kind]:
            self.variant_combo.addItem(label, variant)
        current = self.selected_variants[self.diploma_kind]
        index = self.variant_combo.findData(current)
        self.variant_combo.setCurrentIndex(max(0, index))
        self.variant_combo.currentIndexChanged.connect(self._variant_changed)
        self.fields_layout.addRow(self._field_label("Grafická varianta"), self.variant_combo)

        self.economical_checkbox = QCheckBox(
            "Šetrný tisk • světlý podklad a menší spotřeba inkoustu",
            self.fields_page,
        )
        self.economical_checkbox.setChecked(self.economical_print[self.diploma_kind])
        self.economical_checkbox.toggled.connect(self._economical_print_changed)
        self.logo_checkbox = QCheckBox("Zobrazit logo", self.fields_page)
        self.logo_checkbox.setChecked(self.show_logo[self.diploma_kind])
        self.logo_checkbox.toggled.connect(self._show_logo_changed)

        modifications = QWidget(self.fields_page)
        modifications.setStyleSheet("background:transparent;")
        modifications_layout = QVBoxLayout(modifications)
        modifications_layout.setContentsMargins(0, 0, 0, 0)
        modifications_layout.setSpacing(4)
        modifications_layout.addWidget(self.economical_checkbox)
        modifications_layout.addWidget(self.logo_checkbox)
        self.fields_layout.addRow(self._field_label("Modifikace tisku"), modifications)

        self._add_text_editor_controls()

        self._rebuilding_form = False
        self.fields_scroll.horizontalScrollBar().setValue(0)
        self.fields_scroll.verticalScrollBar().setValue(0)

    def _field_changed(self, key: str, value: str):
        if self._rebuilding_form:
            return
        self.document_values[self.diploma_kind][key] = value
        self._update_preview()

    def _variant_changed(self):
        if self._rebuilding_form:
            return
        self.selected_variants[self.diploma_kind] = self.variant_combo.currentData() or "A"
        self._refresh_output_hint()
        self._update_preview()

    def _economical_print_changed(self, checked: bool):
        if self._rebuilding_form:
            return
        self.economical_print[self.diploma_kind] = bool(checked)
        self._refresh_output_hint()
        self._update_preview()

    def _show_logo_changed(self, checked: bool):
        if self._rebuilding_form:
            return
        self.show_logo[self.diploma_kind] = bool(checked)
        self._refresh_output_hint()
        self._update_preview()

    def _current_values(self):
        values = dict(self.document_values[self.diploma_kind])
        values["kind"] = self.diploma_kind
        values["variant"] = self.selected_variants[self.diploma_kind]
        values["economical_print"] = self.economical_print[self.diploma_kind]
        values["show_logo"] = self.show_logo[self.diploma_kind]
        values["layout"] = self._document_layout()
        values["light_background"] = self.economical_print[self.diploma_kind] or (
            (self.diploma_kind, self.selected_variants[self.diploma_kind])
            in {
                ("camp", "A"), ("sports", "D"), ("cleaning", "B"),
                ("cleaning_award", "A"), ("daily", "A"), ("meal", "A"),
            }
        )
        if self.diploma_kind in self.text_boxes:
            values["text_boxes"] = copy.deepcopy(self.text_boxes[self.diploma_kind])
        if self.diploma_kind == "cleaning":
            values["cabins"] = values.get("cabins_text", "").splitlines()
            values["dates"] = values.get("dates_text", "").splitlines()
        return values

    def _document_layout(self):
        if self.diploma_kind == "sports" and self.selected_variants["sports"] == "D":
            return "two_a5_landscape"
        return DOCUMENT_LAYOUTS[self.diploma_kind]

    def _background_path(self):
        variant = self.selected_variants[self.diploma_kind].lower()
        suffix = "_eco" if self.economical_print[self.diploma_kind] else ""
        filename = f"{self.diploma_kind}_{variant}{suffix}.png"
        folder = "diplomas" if self.diploma_kind in ("camp", "sports", "cleaning") else "documents"
        path = os.path.join(self.icons_path, folder, filename)
        if suffix and not os.path.exists(path):
            path = os.path.join(self.icons_path, folder, f"{self.diploma_kind}_{variant}.png")
        return path

    def _logo_path(self):
        return os.path.join(self.icons_path, "logo.png")

    def show_choices(self):
        self.page_stack.setCurrentWidget(self.choice_page)

    def show_sports_diploma(self):
        self._show_editor(
            "sports",
            "DIPLOM ZA SPORTOVNÍ DEN",
            "Vyber motiv A/B/C a případně zaškrtni Šetrný tisk. Finální A4 obsahuje dvě stejné A5 na výšku.",
        )

    def show_camp_diploma(self):
        self._show_editor(
            "camp",
            "DIPLOM ZA TÁBOR",
            "Vyber motiv A/B/C a případně zaškrtni Šetrný tisk. Finální A4 obsahuje dvě stejné A5 na výšku.",
        )

    def show_cleaning_sheet(self):
        self._show_editor(
            "cleaning",
            "HODNOCENÍ ÚKLIDU CHATEK",
            "Varianta B • volitelný Šetrný tisk • jeden celý list A4 na šířku • 13 chatek • 9. 8.–22. 8.",
        )

    def show_cleaning_award(self):
        self._show_editor(
            "cleaning_award",
            "DIPLOM ZA ÚKLID",
            "Vyber motiv A/B. Finální A4 na výšku obsahuje dva stejné diplomy A5 na šířku.",
        )

    def show_daily_program(self):
        self._show_editor(
            "daily",
            "DENNÍ PROGRAM",
            "Jeden celý list A4 na výšku • všechny texty lze přesouvat, přidávat a formátovat.",
        )

    def show_meal_plan(self):
        self._show_editor(
            "meal",
            "JÍDELNÍČEK",
            "Jeden celý list A4 na výšku • upravitelná jídla, datum, nadpisy i vlastní texty.",
        )

    def _refresh_output_hint(self):
        layout = self._document_layout()
        if layout == "a4_landscape":
            base = "VÝSTUP: 1× úklidová tabulka na A4 na šířku"
        elif layout == "a4_portrait":
            base = "VÝSTUP: 1× tiskovina na celý A4 na výšku"
        elif layout == "two_a5_landscape":
            base = "VÝSTUP: 2× listina A5 na šířku na jednom A4 na výšku • středová linka"
        else:
            base = "VÝSTUP: 2× diplom A5 na jednom A4 na šířku • středová linka pro rozstřižení"
        if self.economical_print[self.diploma_kind]:
            base += "\nŠETRNÝ TISK: světlé pirátské pozadí s nízkou spotřebou inkoustu"
        base += "\nLOGO: zobrazeno" if self.show_logo[self.diploma_kind] else "\nLOGO: skryto"
        self.output_hint.setText(base)

    def _show_editor(self, kind: str, title: str, subtitle: str):
        self.diploma_kind = kind
        self.editor_title.setText(title)
        self.editor_subtitle.setText(subtitle)
        self._refresh_output_hint()
        self._rebuild_fields()
        self.page_stack.setCurrentWidget(self.editor_page)
        self._update_preview()

    def _update_preview(self):
        if not hasattr(self, "preview"):
            return
        self.preview.set_document(
            self.diploma_kind,
            self._current_values(),
            self._background_path(),
            self._logo_path(),
        )
        self.preview.set_selected_text_box(self.selected_text_box.get(self.diploma_kind, ""))

    def _save_pdf(self):
        if save_document_pdf(
            self,
            self.diploma_kind,
            self._current_values(),
            self._background_path(),
            self._logo_path(),
        ):
            QMessageBox.information(self, "PDF", "PDF bylo úspěšně vytvořeno.")

    def _print_document(self):
        print_document(
            self,
            self.diploma_kind,
            self._current_values(),
            self._background_path(),
            self._logo_path(),
        )
