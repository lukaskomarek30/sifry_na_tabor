# -*- coding: utf-8 -*-
"""Implementace Caesarovy šifry pro Šifrátor Mraveniště.

Modul obsahuje jednoduchou a samostatně použitelnou logiku pro šifrování
a dešifrování textu Caesarovou šifrou. Posun je možné nastavit kladnou
i zápornou hodnotou, takže stejná interní funkce pokrývá posun dopředu
i dozadu.

Vlastnosti:
- výchozí posun je definovaný konstantou SHIFT,
- podporovaná abeceda je A–Z bez diakritiky,
- česká diakritika se před šifrováním převádí na základní písmeno,
- mezery, čísla, interpunkce a nepodporované symboly zůstávají beze změny,
- velikost písmen se zachovává podle původního vstupu.

Příklad:
    encrypt("Ahoj", 3) -> "Dkrm"
    decrypt("Dkrm", 3) -> "Ahoj"
"""

from __future__ import annotations

import unicodedata

# Výchozí posun Caesarovy šifry. Hodnota 3 odpovídá klasické variantě Caesarovy šifry.
SHIFT = 3

# Základní abeceda používaná pro výpočet posunu.
# Diakritika se před zpracováním normalizuje, proto zde stačí čisté A–Z.
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _remove_diacritics(char: str) -> str:
    """Odstraní diakritiku z jednoho znaku pomocí Unicode normalizace.

    Funkce pracuje po jednom znaku, protože Caesarova šifra posouvá každý
    znak samostatně. Pokud normalizace nic nevrátí, zachová se původní znak.
    """
    normalized = unicodedata.normalize("NFKD", char)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return without_marks[:1] if without_marks else char


def _shift_char(char: str, shift: int) -> str:
    """Posune jeden znak v rámci definované abecedy.

    Znaky mimo ALPHABET se nemění. Díky tomu zůstávají zachované mezery,
    čísla, interpunkce i ostatní symboly.
    """
    base = _remove_diacritics(char)
    upper = base.upper()

    if upper not in ALPHABET:
        return char

    old_index = ALPHABET.index(upper)
    new_index = (old_index + shift) % len(ALPHABET)
    shifted = ALPHABET[new_index]

    # Zachování původní velikosti písmen zlepšuje čitelnost výsledku.
    if char.islower():
        return shifted.lower()

    return shifted


def _normalize_shift(shift: int | str | None) -> int:
    """Převede zadaný posun na celé číslo.

    Pokud vstup není možné převést, použije se výchozí hodnota SHIFT.
    To chrání aplikaci před pádem při neplatném vstupu z UI.
    """
    try:
        return int(shift)
    except Exception:
        return SHIFT


def encrypt(text: str, shift: int | str = SHIFT) -> str:
    """Zašifruje text Caesarovou šifrou.

    Kladný posun posouvá znaky dopředu v abecedě, záporný posun dozadu.
    Nepodporované znaky se ponechávají beze změny.
    """
    real_shift = _normalize_shift(shift)
    return "".join(_shift_char(char, real_shift) for char in text)


def decrypt(text: str, shift: int | str = SHIFT) -> str:
    """Dešifruje text Caesarovou šifrou.

    Dešifrování používá stejnou logiku jako šifrování, pouze s opačným
    znaménkem posunu.
    """
    real_shift = _normalize_shift(shift)
    return "".join(_shift_char(char, -real_shift) for char in text)


# Kompatibilní aliasy pro části aplikace, které mohou očekávat české názvy funkcí.
zasifrovat = encrypt
desifrovat = decrypt
