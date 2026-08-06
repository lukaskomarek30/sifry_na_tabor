"""Graficka domovska obrazovka pro piratskou taborovou aplikaci."""

import os

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QGridLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fire_effects import FireFlicker


GOLD = QColor("#c99b4e")
GOLD_LIGHT = QColor("#f4dea4")
TEXT_LIGHT = QColor("#ead8b3")
PIRATE_FONT_FAMILY = "Pirata One"


def _ensure_pirate_font(icons_path: str = ""):
    """Načte přibalený Pirata One a vrátí dostupnou pirátskou rodinu písma."""
    families = set(QFontDatabase.families())
    if PIRATE_FONT_FAMILY not in families:
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
                    return registered[0]

    if PIRATE_FONT_FAMILY in QFontDatabase.families():
        return PIRATE_FONT_FAMILY

    # Georgia zůstává čitelnou zálohou pro neobvyklá prostředí.
    if "Georgia" in QFontDatabase.families():
        return "Georgia"

    windows_dir = os.environ.get("WINDIR", "C:\\Windows")
    fonts_dir = os.path.join(windows_dir, "Fonts")
    for file_name in ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"):
        path = os.path.join(fonts_dir, file_name)
        if os.path.exists(path):
            QFontDatabase.addApplicationFont(path)
    return "Georgia"


class PirateMenuCard(QPushButton):
    """Velka obrazkova navigacni karta s vlastnim piratskym vykreslovanim."""

    def __init__(self, title: str, description: str, icon_path: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.description = description
        self.icon_pixmap = QPixmap(icon_path) if icon_path and os.path.exists(icon_path) else QPixmap()
        self._hovered = False
        self._pressed = False

        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumSize(150, 158)
        self.setMaximumSize(350, 184)
        self.setStyleSheet("background: transparent; border: none;")
        self.setToolTip(f"{title} – {description}")
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)

    def sizeHint(self):
        return QSize(320, 184)

    def hitButton(self, position):
        """Cela viditelna plocha karty je klikaci, vcetne ikony a textu."""
        return self.rect().contains(position)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def focusInEvent(self, event):
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.update()
        super().focusOutEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        outer = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self._pressed:
            outer.translate(0, 2)

        # Pri najeti nebo ovladani klavesnici se rozsviti pouze ramecek.
        # Ani aktivni karta nesmi prekryt obrazkove pozadi paluby.
        if self._hovered or self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(234, 184, 80, 82), 4))
            painter.drawRoundedRect(outer.adjusted(-2, -2, 2, 2), 18, 18)

        # Karta nema vlastni tmavou vypln. Pozadi hlavni paluby tak zustava
        # viditelne pres celou plochu dlazdice a ramecek pouze vymezuje klikaci oblast.
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(GOLD_LIGHT if self._hovered else GOLD, 2.4 if self._hovered else 1.4))
        painter.drawRoundedRect(outer, 16, 16)

        # Dvojita vnitrni linka pripomina mosazny ram puvodniho sifratoru.
        inner = outer.adjusted(7, 7, -7, -7)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(210, 158, 72, 82), 1))
        painter.drawRoundedRect(inner, 12, 12)

        width = max(1, self.width())
        height = max(1, self.height())
        icon_size = int(max(58, min(94, height * 0.43, width * 0.34)))
        icon_top = int(13 if height < 195 else 16)

        if not self.icon_pixmap.isNull():
            scaled = self.icon_pixmap.scaled(
                QSize(icon_size, icon_size),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            icon_x = (width - scaled.width()) // 2
            painter.drawPixmap(icon_x, icon_top, scaled)

        title_top = icon_top + icon_size + (3 if height < 195 else 7)
        title_text = self.title.upper()
        title_size = max(9, min(17, int(width / 16)))
        title_font = QFont("Georgia", title_size, QFont.Bold)
        title_font.setLetterSpacing(QFont.AbsoluteSpacing, 0.5)
        while title_size > 9 and QFontMetrics(title_font).horizontalAdvance(title_text) > width - 26:
            title_size -= 1
            title_font.setPointSize(title_size)
        painter.setFont(title_font)
        painter.setPen(GOLD_LIGHT if self._hovered else QColor("#efd59a"))
        painter.drawText(
            QRectF(14, title_top, width - 28, 28),
            Qt.AlignHCenter | Qt.AlignVCenter,
            title_text,
        )

        description_top = title_top + 28
        action_height = 27
        description_bottom = height - action_height - 12
        if description_bottom > description_top + 8:
            description_font = QFont("Georgia", max(8, min(10, int(width / 25))))
            painter.setFont(description_font)
            painter.setPen(QColor(225, 213, 184, 205))
            option = QTextOption(Qt.AlignHCenter | Qt.AlignTop)
            option.setWrapMode(QTextOption.WordWrap)
            painter.drawText(
                QRectF(18, description_top + 1, width - 36, description_bottom - description_top),
                self.description,
                option,
            )

        painter.setPen(QPen(QColor(200, 154, 76, 105), 1))
        painter.drawLine(outer.left() + 18, height - action_height - 6, outer.right() - 18, height - action_height - 6)

        action_font = QFont("Georgia", 9, QFont.Bold)
        action_font.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        painter.setFont(action_font)
        painter.setPen(QColor("#fff0bd") if self._hovered else QColor("#cfae71"))
        painter.drawText(
            QRectF(12, height - action_height - 2, width - 24, action_height),
            Qt.AlignCenter,
            "OTEVŘÍT  ›",
        )


class PirateHomeWidget(QWidget):
    """Moderni uvodni menu postavene ze stejnych podkladu jako sifrator."""

    navigate_requested = Signal(str)

    def __init__(self, icons_path: str, app_version: str = "", parent=None):
        super().__init__(parent)
        _ensure_pirate_font()
        self.icons_path = icons_path
        self.app_version = app_version
        self.background = self._load_pixmap("menu_BG.png")
        if self.background.isNull():
            self.background = self._load_pixmap("BG.png")
        self.logo = self._load_pixmap("logo.png")
        self.cards = []
        self.diploma_choice_cards = []
        self._menu_mode = "main"
        self._menu_transitioning = False
        self._menu_animation = None
        self._active_effects = []
        self.fire_flicker = FireFlicker(
            self,
            (
                (0.058, 0.404, 0.48),
                (0.949, 0.838, 1.25),
            ),
        )

        self.setObjectName("pirateHome")
        self.setMinimumSize(760, 560)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()

    def _path(self, file_name: str) -> str:
        return os.path.join(self.icons_path, file_name)

    def _load_pixmap(self, file_name: str) -> QPixmap:
        path = self._path(file_name)
        return QPixmap(path) if os.path.exists(path) else QPixmap()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(58, 22, 58, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(22)
        header.addStretch(1)

        self.logo_label = QLabel(self)
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setFixedSize(118, 118)
        if not self.logo.isNull():
            self.logo_label.setPixmap(self.logo.scaled(112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.setStyleSheet("background: transparent;")
        header.addWidget(self.logo_label, 0, Qt.AlignVCenter)

        title_column = QVBoxLayout()
        title_column.setSpacing(1)

        self.header_eyebrow = QLabel("PIRÁTSKÉ VELITELSTVÍ", self)
        self.header_eyebrow.setAlignment(Qt.AlignCenter)
        self.header_eyebrow.setStyleSheet(
            "color: #c99b4e; background: transparent; font-family: Georgia; "
            "font-size: 12px; font-weight: bold; letter-spacing: 4px;"
        )
        title_column.addWidget(self.header_eyebrow)

        self.header_title = QLabel("VELITELSKÁ PALUBA", self)
        self.header_title.setAlignment(Qt.AlignCenter)
        self.header_title.setStyleSheet(
            "color: #f4dea4; background: transparent; font-family: Georgia; "
            "font-size: 32px; font-weight: bold; letter-spacing: 2px;"
        )
        title_column.addWidget(self.header_title)

        self.header_subtitle = QLabel("Vyber si, kam dnes vyplujeme", self)
        self.header_subtitle.setAlignment(Qt.AlignCenter)
        self.header_subtitle.setStyleSheet(
            "color: #ead8b3; background: transparent; font-family: Georgia; "
            "font-size: 14px; font-style: italic;"
        )
        title_column.addWidget(self.header_subtitle)
        header.addLayout(title_column)
        header.addStretch(1)
        root.addLayout(header)

        separator = QWidget(self)
        separator.setFixedHeight(2)
        separator.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 rgba(200,154,76,0), stop:0.25 rgba(200,154,76,150), "
            "stop:0.5 rgba(243,215,154,230), stop:0.75 rgba(200,154,76,150), "
            "stop:1 rgba(200,154,76,0));"
        )
        root.addWidget(separator)

        self.grid_holder = QWidget(self)
        self.grid_holder.setMinimumSize(620, 350)
        self.grid_holder.setMaximumSize(1320, 440)
        self.grid_holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.grid_holder.setAutoFillBackground(False)
        self.grid_holder.setAttribute(Qt.WA_TranslucentBackground, True)
        self.grid_holder.setStyleSheet("background: transparent; border: none;")
        self.menu_grid = QGridLayout(self.grid_holder)
        self.menu_grid.setHorizontalSpacing(18)
        self.menu_grid.setVerticalSpacing(20)
        self.menu_grid.setContentsMargins(0, 2, 0, 0)
        # Osm pomocnych sloupcu dovoli vystredit tri spodni dlazdice pod
        # ctverici hornich a pritom zachovat stejnou sirku vsech karet.
        for column in range(8):
            self.menu_grid.setColumnStretch(column, 1)
        self.menu_grid.setRowStretch(0, 1)
        self.menu_grid.setRowStretch(1, 1)

        entries = [
            ("cipher", "Šifrátor", "Šifruj, dešifruj a připravuj klíče", "lock_closed.png", 0, 0),
            ("planner", "Plánovač tábora", "Kalendář programu, šifer a táborových dnů", "compass.png", 0, 2),
            ("batch", "Hromadné šifrování", "Připrav více stanovišť a výtisků najednou", "tiskarna.png", 0, 4),
            ("diploma", "Diplom", "Připrav pirátský diplom pro členy posádky", "pirate_coin.png", 0, 6),
            ("groups", "Oddíly", "Importuj posádky, vedoucí a osobní karty z Excelu", "tancici_figurky.png", 1, 0),
            ("overview", "Přehled šifer", "Obtížnost, věk, použití a poznámky", "anchor.png", 1, 2),
            ("history", "Historie zpráv", "Vrať se k dříve vytvořeným šifrám", "logo.png", 1, 4),
            ("sports", "Sportovní den", "Naplánuj disciplíny, týmy a průběh dne", "semafor.png", 1, 6),
        ]

        for route, title, description, icon_file, row, column in entries:
            card = PirateMenuCard(title, description, self._path(icon_file), self)
            if route == "diploma":
                card.clicked.connect(lambda checked=False: self.show_diploma_choices(animated=True))
            else:
                card.clicked.connect(
                    lambda checked=False, key=route: self.navigate_with_animation(key)
                )
            self.menu_grid.addWidget(card, row, column, 1, 2, Qt.AlignCenter)
            self.cards.append(card)

        sports_diploma = PirateMenuCard(
            "Diplom za sportovní den",
            "Ocenění za výkon, umístění nebo sportovní výzvy",
            self._path("semafor.png"),
            self,
        )
        sports_diploma.setMinimumSize(250, 150)
        sports_diploma.setMaximumSize(400, 185)
        sports_diploma.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_sports")
        )
        self.menu_grid.addWidget(sports_diploma, 0, 1, 1, 2, Qt.AlignCenter)

        camp_diploma = PirateMenuCard(
            "Diplom za tábor",
            "Ocenění za dobrodružství, spolupráci a práci pro posádku",
            self._path("logo.png"),
            self,
        )
        camp_diploma.setMinimumSize(250, 150)
        camp_diploma.setMaximumSize(400, 185)
        camp_diploma.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_camp")
        )
        self.menu_grid.addWidget(camp_diploma, 0, 3, 1, 2, Qt.AlignCenter)

        cleaning_sheet = PirateMenuCard(
            "Hodnocení úklidu",
            "Lodní deník čistoty pro 13 chatek a každý táborový den",
            self._path("pirate_coin.png"),
            self,
        )
        cleaning_sheet.setMinimumSize(250, 150)
        cleaning_sheet.setMaximumSize(400, 185)
        cleaning_sheet.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_cleaning")
        )
        self.menu_grid.addWidget(cleaning_sheet, 0, 5, 1, 2, Qt.AlignCenter)

        cleaning_award = PirateMenuCard(
            "Diplom za úklid",
            "Ocenění pro nejčistší srub nebo posádku",
            self._path("anchor.png"),
            self,
        )
        cleaning_award.setMinimumSize(250, 150)
        cleaning_award.setMaximumSize(400, 185)
        cleaning_award.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_cleaning_award")
        )
        self.menu_grid.addWidget(cleaning_award, 1, 1, 1, 2, Qt.AlignCenter)

        daily_program = PirateMenuCard(
            "Denní program",
            "Upravitelný rozkaz dne pro celou táborovou posádku",
            self._path("compass.png"),
            self,
        )
        daily_program.setMinimumSize(250, 150)
        daily_program.setMaximumSize(400, 185)
        daily_program.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_daily")
        )
        self.menu_grid.addWidget(daily_program, 1, 3, 1, 2, Qt.AlignCenter)

        meal_plan = PirateMenuCard(
            "Jídelníček",
            "Pirátská nabídka snídaně, svačin, oběda a večeře",
            self._path("tiskarna.png"),
            self,
        )
        meal_plan.setMinimumSize(250, 150)
        meal_plan.setMaximumSize(400, 185)
        meal_plan.clicked.connect(
            lambda checked=False: self.navigate_with_animation("diploma_meal")
        )
        self.menu_grid.addWidget(meal_plan, 1, 5, 1, 2, Qt.AlignCenter)
        self.diploma_choice_cards = [
            sports_diploma, camp_diploma, cleaning_sheet,
            cleaning_award, daily_program, meal_plan,
        ]

        self.diploma_back_button = QPushButton("‹  ZPĚT NA HLAVNÍ MENU", self.grid_holder)
        self.diploma_back_button.setCursor(Qt.PointingHandCursor)
        self.diploma_back_button.setFixedHeight(38)
        self.diploma_back_button.setStyleSheet("""
            QPushButton {
                color: #f3d79a;
                background-color: rgba(5, 25, 35, 205);
                border: 1px solid #c89a4c;
                border-radius: 9px;
                padding: 6px 13px;
                font-family: Georgia;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #fff0bd;
                background-color: rgba(13, 63, 72, 235);
                border: 2px solid #f3d79a;
            }
        """)
        self.diploma_back_button.clicked.connect(
            lambda checked=False: self.show_main_menu(animated=True)
        )
        self.menu_grid.addWidget(
            self.diploma_back_button,
            0,
            0,
            1,
            1,
            Qt.AlignLeft | Qt.AlignTop,
        )

        for widget in self.diploma_choice_cards + [self.diploma_back_button]:
            widget.hide()

        root.addWidget(self.grid_holder, 1, Qt.AlignCenter)

        footer_text = "LETNÍ TÁBOR MRAVENIŠTĚ  •  TÉMA: PIRÁTI Z KARIBIKU"
        if self.app_version:
            footer_text += f"  •  v{self.app_version}"
        footer = QLabel(footer_text, self)
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(
            "color: rgba(231,198,129,185); background: transparent; "
            "font-family: Georgia; font-size: 10px; font-weight: bold; letter-spacing: 2px;"
        )
        root.addWidget(footer)

    def _set_header_mode(self, mode: str):
        if mode == "diploma":
            self.header_eyebrow.setText("PIRÁTSKÁ SÍŇ SLÁVY")
            self.header_title.setText("VYBER TÁBOROVOU LISTINU")
            self.header_subtitle.setText("Diplomy, úklidová listina, denní program a jídelníček v jednom tiskovém studiu")
            return
        self.header_eyebrow.setText("PIRÁTSKÉ VELITELSTVÍ")
        self.header_title.setText("VELITELSKÁ PALUBA")
        self.header_subtitle.setText("Vyber si, kam dnes vyplujeme")

    def _fade_widgets(self, widgets, start_opacity: float, end_opacity: float, duration: int, finished):
        group = QParallelAnimationGroup(self)
        effects = []
        for widget in widgets:
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            effect.setOpacity(start_opacity)
            widget.show()
            animation = QPropertyAnimation(effect, b"opacity", group)
            animation.setDuration(duration)
            animation.setStartValue(start_opacity)
            animation.setEndValue(end_opacity)
            animation.setEasingCurve(QEasingCurve.InOutCubic)
            group.addAnimation(animation)
            effects.append((widget, effect))

        self._menu_animation = group
        self._active_effects = effects

        def complete_transition():
            for widget, _effect in effects:
                widget.setGraphicsEffect(None)
            self._active_effects = []
            if finished is not None:
                finished()

        group.finished.connect(complete_transition)
        group.start()

    def show_diploma_choices(self, animated=True):
        if self._menu_transitioning or self._menu_mode == "diploma":
            return
        self._menu_transitioning = True

        def reveal_choices():
            for card in self.cards:
                card.hide()
            self._set_header_mode("diploma")

            def done():
                self._menu_mode = "diploma"
                self._menu_transitioning = False

            self._fade_widgets(
                self.diploma_choice_cards + [self.diploma_back_button],
                0.0,
                1.0,
                260,
                done,
            )

        if animated:
            self._fade_widgets(self.cards, 1.0, 0.0, 210, reveal_choices)
        else:
            for card in self.cards:
                card.hide()
            self._set_header_mode("diploma")
            for widget in self.diploma_choice_cards + [self.diploma_back_button]:
                widget.show()
                widget.setGraphicsEffect(None)
            self._menu_mode = "diploma"
            self._menu_transitioning = False

    def navigate_with_animation(self, route: str):
        """Nejprve schova aktivni dlazdice a az potom otevre zvolenou cast aplikace."""
        if self._menu_transitioning or self._menu_mode == "hidden":
            return
        self._menu_transitioning = True
        if self._menu_mode == "diploma":
            visible_widgets = self.diploma_choice_cards + [self.diploma_back_button]
        else:
            visible_widgets = self.cards

        def open_destination():
            for widget in visible_widgets:
                widget.hide()
            self._menu_mode = "hidden"
            self._menu_transitioning = False
            self.navigate_requested.emit(route)

        self._fade_widgets(visible_widgets, 1.0, 0.0, 230, open_destination)

    def show_main_menu(self, animated=True):
        if self._menu_transitioning or self._menu_mode == "main":
            return
        self._menu_transitioning = True
        choices = self.diploma_choice_cards + [self.diploma_back_button]

        if self._menu_mode == "hidden":
            for widget in choices:
                widget.hide()
            self._set_header_mode("main")

            if not animated:
                for card in self.cards:
                    card.show()
                    card.setGraphicsEffect(None)
                self._menu_mode = "main"
                self._menu_transitioning = False
                return

            def restored():
                self._menu_mode = "main"
                self._menu_transitioning = False

            self._fade_widgets(self.cards, 0.0, 1.0, 280, restored)
            return

        def reveal_main_menu():
            for widget in choices:
                widget.hide()
            self._set_header_mode("main")

            def done():
                self._menu_mode = "main"
                self._menu_transitioning = False

            self._fade_widgets(self.cards, 0.0, 1.0, 260, done)

        if animated:
            self._fade_widgets(choices, 1.0, 0.0, 190, reveal_main_menu)
        else:
            for widget in choices:
                widget.hide()
            self._set_header_mode("main")
            for card in self.cards:
                card.show()
                card.setGraphicsEffect(None)
            self._menu_mode = "main"
            self._menu_transitioning = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        scaled = QPixmap()
        x = y = 0
        if not self.background.isNull():
            scaled = self.background.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(self.rect(), scaled, QRect(x, y, self.width(), self.height()))
        else:
            painter.fillRect(self.rect(), QColor("#06131b"))

        # Ztmaveni sjednocuje velmi detailni puvodni pozadi a zlepsuje citelnost karet.
        overlay = QLinearGradient(0, 0, 0, self.height())
        overlay.setColorAt(0, QColor(2, 9, 14, 88))
        overlay.setColorAt(0.5, QColor(2, 12, 18, 42))
        overlay.setColorAt(1, QColor(1, 6, 10, 105))
        painter.fillRect(self.rect(), overlay)

        if not scaled.isNull():
            self.fire_flicker.paint(painter, scaled.width(), scaled.height(), x, y)
