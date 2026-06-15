# -*- coding: utf-8 -*-
"""
Záměna písmen za čísla (A=26, Z=01)

Princip:
    A = 26
    B = 25
    C = 24
    ...
    Z = 01

Při šifrování:
    - písmena ve slově jsou psaná hned za sebou jako dvojciferná čísla,
    - mezera mezi slovy zůstává jako jedna mezera,
    - symboly jako ?,.-! zůstávají beze změny,
    - česká diakritika se převede na základní písmeno.

Příklad:
    Ahoj jak se máš?
    26191217 172616 0822 142608?
"""

import unicodedata


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

ENCRYPT_MAP = {
    letter: f"{26 - index:02d}"
    for index, letter in enumerate(ALPHABET)
}

DECRYPT_MAP = {
    f"{26 - index:02d}": letter
    for index, letter in enumerate(ALPHABET)
}


def _remove_diacritics(text: str) -> str:
    """Převede české znaky na základní písmena."""
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_plain_text(text: str) -> str:
    """Normalizuje text pro šifrování."""
    return _remove_diacritics(text).upper()


def encrypt(text: str) -> str:
    """Zašifruje text do číselné záměny A=26, Z=01."""
    normalized = _normalize_plain_text(text)

    result = []
    last_was_space = False

    for char in normalized:
        if char in ENCRYPT_MAP:
            result.append(ENCRYPT_MAP[char])
            last_was_space = False
        elif char.isspace():
            # Slova oddělíme jednou mezerou.
            if result and not last_was_space:
                result.append(" ")
                last_was_space = True
        else:
            # Interpunkce a ostatní symboly zůstanou beze změny.
            result.append(char)
            last_was_space = False

    return "".join(result).strip()


def _flush_digits(buffer: str) -> str:
    """Převede souvislý blok číslic po dvojicích zpět na písmena."""
    decoded = []

    i = 0
    while i < len(buffer):
        pair = buffer[i:i + 2]

        if len(pair) == 2 and pair in DECRYPT_MAP:
            decoded.append(DECRYPT_MAP[pair])
            i += 2
        elif len(pair) == 2:
            # Neznámou dvojici necháme zachovanou.
            decoded.append(pair)
            i += 2
        else:
            # Osamocenou číslici necháme zachovanou.
            decoded.append(pair)
            i += 1

    return "".join(decoded)


def decrypt(text: str) -> str:
    """Dešifruje číselnou záměnu A=26, Z=01 zpět na písmena."""
    result = []
    digit_buffer = []
    last_was_space = False

    for char in text or "":
        if char.isdigit():
            digit_buffer.append(char)
            last_was_space = False
            continue

        if digit_buffer:
            result.append(_flush_digits("".join(digit_buffer)))
            digit_buffer.clear()

        if char.isspace():
            if result and not last_was_space:
                result.append(" ")
                last_was_space = True
        else:
            # Interpunkce a ostatní symboly zůstanou beze změny.
            result.append(char)
            last_was_space = False

    if digit_buffer:
        result.append(_flush_digits("".join(digit_buffer)))

    return "".join(result).strip()
