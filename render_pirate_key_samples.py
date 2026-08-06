# -*- coding: utf-8 -*-
"""Vykreslí dvě ukázky moderního pirátského vzhledu klíčů."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from cipher_registry import get_cipher_logic, get_pirate_key_renderer, list_cipher_names


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


SAMPLES = (
    {
        "cipher": "Morseova abeceda",
        "background": os.path.join(PROJECT_DIR, "icons", "key_templates", "pirate_key_morse_template.png"),
        "output": os.path.join(PROJECT_DIR, "output", "key-previews", "pirate-key-morse-preview.png"),
        "subtitle": "KAPITÁNŮV KLÍČ • TAJNÁ ABECEDA",
        "description": "Tečka je krátký signál, čárka dlouhý. Čti zleva doprava.",
    },
    {
        "cipher": "Zednářská šifra",
        "background": os.path.join(PROJECT_DIR, "icons", "key_templates", "pirate_key_zednarska_template.png"),
        "output": os.path.join(PROJECT_DIR, "output", "key-previews", "pirate-key-zednarska-preview.png"),
        "subtitle": "KAPITÁNŮV KLÍČ • ZNAMENÍ CECHU",
        "description": "Každému písmenu náleží vlastní směrový znak.",
    },
)


def render_sample(renderer, sample: dict[str, str], width: int = 1400) -> str:
    module = get_cipher_logic(sample["cipher"])
    data = renderer.make_key_data_from_module(sample["cipher"], module)
    if not isinstance(data, dict):
        raise RuntimeError(f"Nepodařilo se připravit klíč: {sample['cipher']}")

    data = dict(data)
    data.update(
        {
            "theme": "pirate_modern",
            "background_path": sample["background"],
            "subtitle": sample["subtitle"],
            "description": sample["description"],
        }
    )

    widget = renderer.PirateKeyWidget(data)
    height = widget.estimate_height(width)
    widget.resize(width, height)
    widget.setMinimumSize(width, height)

    pixmap = QPixmap(widget.size())
    pixmap.fill(Qt.transparent)
    widget.render(pixmap)

    os.makedirs(os.path.dirname(sample["output"]), exist_ok=True)
    if not pixmap.save(sample["output"], "PNG"):
        raise RuntimeError(f"Nepodařilo se uložit ukázku: {sample['output']}")
    return sample["output"]


def verify_all_keys(renderer) -> None:
    errors: list[str] = []
    first_print_widget = None
    for cipher_name in list_cipher_names():
        module = get_cipher_logic(cipher_name)
        data = renderer.make_key_data_from_module(cipher_name, module)
        if not isinstance(data, dict):
            errors.append(f"{cipher_name}: chybí data")
            continue

        widget = renderer.PirateKeyWidget(data)
        if not widget.decorated_pirate_mode:
            errors.append(f"{cipher_name}: chybí pirátská obrazovková šablona")
        if widget.logo_pixmap.isNull():
            errors.append(f"{cipher_name}: chybí logo")

        print_data = dict(data)
        print_data["_print_mode"] = True
        print_widget = renderer.PirateKeyWidget(print_data)
        if not print_widget.plain_print_mode or print_widget.decorated_pirate_mode:
            errors.append(f"{cipher_name}: tisk není čistě bílý")
        if first_print_widget is None:
            first_print_widget = print_widget

    if first_print_widget is not None:
        width = 1000
        height = first_print_widget.estimate_height(width)
        first_print_widget.resize(width, height)
        print_pixmap = QPixmap(first_print_widget.size())
        print_pixmap.fill(Qt.magenta)
        first_print_widget.render(print_pixmap)
        image = print_pixmap.toImage()
        corners = (
            image.pixelColor(0, 0),
            image.pixelColor(image.width() - 1, 0),
            image.pixelColor(0, image.height() - 1),
            image.pixelColor(image.width() - 1, image.height() - 1),
        )
        if any(min(color.red(), color.green(), color.blue()) < 248 for color in corners):
            errors.append("Tisková kontrola: rohy výsledného obrázku nejsou bílé")

    if errors:
        raise RuntimeError("\n".join(errors))
    print(f"Ověřeno {len(list_cipher_names())} klíčů: pirátské UI, čistý tisk, vlastní logo.")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    renderer = get_pirate_key_renderer()
    if renderer is None:
        raise RuntimeError("Renderer klíčů není dostupný.")

    if "--verify-all" in sys.argv[1:]:
        verify_all_keys(renderer)
    else:
        for sample in SAMPLES:
            print(render_sample(renderer, sample))
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
