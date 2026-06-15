# -*- coding: utf-8 -*-

"""Implementace šifry Záměna písmen za čísla (A=01, Z=26) pro Šifrátor Mraveniště.

Modul obsahuje logiku pro šifrování, dešifrování a případnou přípravu dat
pro grafický klíč šifry. Kód je navržený tak, aby šel používat samostatně
i jako součást hlavní aplikace.
Modul je čistě textový a nevyžaduje grafické závislosti.

Základní pravidla implementace:
- vstupní text se před zpracováním normalizuje podle potřeb konkrétní šifry,
- běžné mezery, interpunkce a nepodporované symboly se zachovávají tam,
  kde to dává pro danou šifru smysl,
- veřejné funkce encrypt() a decrypt() tvoří stabilní rozhraní pro main.py,
- pomocné funkce jsou oddělené od UI vrstvy, aby se logika dala snadno testovat.
"""


import unicodedata

# Základní abeceda používaná danou šifrou.
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LETTER_TO_CODE = {letter: f"{index:02d}" for index, letter in enumerate(ALPHABET, start=1)}
CODE_TO_LETTER = {code: letter for letter, code in LETTER_TO_CODE.items()}


def remove_diacritics(text: str) -> str:
    """Odstraní českou diakritiku, aby šlo psát Á jako A, Č jako C atd."""
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def encrypt(text: str) -> str:
    """Zašifruje text do čísel A=01 až Z=26."""
    result = []

    for char in remove_diacritics(text):
        upper = char.upper()

        if upper in LETTER_TO_CODE:
            result.append(LETTER_TO_CODE[upper])
        else:
            # Mezery, otazníky, tečky, čárky, pomlčky, čísla atd. zůstanou beze změny.
            result.append(char)

    return "".join(result)


def decrypt(text: str) -> str:
    """Dešifruje dvojice čísel 01 až 26 zpět na písmena."""
    result = []
    index = 0
    source = text or ""

    while index < len(source):
        char = source[index]

        if char.isdigit() and index + 1 < len(source) and source[index + 1].isdigit():
            code = source[index:index + 2]

            if code in CODE_TO_LETTER:
                result.append(CODE_TO_LETTER[code])
                index += 2
                continue

        # Symboly, mezery i neplatné číslice zůstanou beze změny.
        result.append(char)
        index += 1

    return "".join(result)
