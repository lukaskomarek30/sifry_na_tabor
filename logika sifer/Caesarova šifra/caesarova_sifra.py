# -*- coding: utf-8 -*-
"""Caesarova šifra pro Šifrátor Mraveniště.

Podporuje volitelný posun dopředu i dozadu.
Symboly, mezery, čísla a interpunkce zůstávají beze změny.
Česká diakritika se před šifrováním převede na základní písmeno:
Á -> A, Č -> C, Š -> S atd.
"""

from __future__ import annotations

import unicodedata

SHIFT = 3
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _remove_diacritics(char: str) -> str:
    """Vrátí znak bez diakritiky, například Č -> C."""
    normalized = unicodedata.normalize("NFKD", char)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks[:1] if without_marks else char


def _shift_char(char: str, shift: int) -> str:
    base = _remove_diacritics(char)
    upper = base.upper()

    if upper not in ALPHABET:
        return char

    old_index = ALPHABET.index(upper)
    new_index = (old_index + shift) % len(ALPHABET)
    shifted = ALPHABET[new_index]

    if char.islower():
        return shifted.lower()

    return shifted


def _normalize_shift(shift: int | str | None) -> int:
    try:
        return int(shift)
    except Exception:
        return SHIFT


def encrypt(text: str, shift: int | str = SHIFT) -> str:
    """Zašifruje text Caesarovou šifrou.

    Kladný posun = dopředu, záporný posun = dozadu.
    """
    real_shift = _normalize_shift(shift)
    return "".join(_shift_char(char, real_shift) for char in text)


def decrypt(text: str, shift: int | str = SHIFT) -> str:
    """Dešifruje text Caesarovou šifrou."""
    real_shift = _normalize_shift(shift)
    return "".join(_shift_char(char, -real_shift) for char in text)


# Volitelné aliasy, kdyby main.py používal jiné názvy.
zasifrovat = encrypt
desifrovat = decrypt
