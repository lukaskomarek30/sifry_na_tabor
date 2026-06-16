# -*- coding: utf-8 -*-
"""Logika pro šifru Vlčácká šifra.

Používá dvojčíselný zápis:
- první číslo = skupina 1 až 9
- druhé číslo = pozice znaku ve skupině 1 až 3

Příklad:
A = 11
B = 12
C = 13
D = 21
CH = 33
"""

from __future__ import annotations

import re
import unicodedata

GROUPS: dict[str, list[str]] = {
    "1": ["A", "B", "C"],
    "2": ["D", "E", "F"],
    "3": ["G", "H", "CH"],
    "4": ["I", "J", "K"],
    "5": ["L", "M", "N"],
    "6": ["O", "P", "Q"],
    "7": ["R", "S", "T"],
    "8": ["U", "V", "W"],
    "9": ["X", "Y", "Z"],
}

CHAR_TO_CODE: dict[str, str] = {}
CODE_TO_CHAR: dict[str, str] = {}

for group_number, letters in GROUPS.items():
    for index, letter in enumerate(letters, start=1):
        code = f"{group_number}{index}"
        CHAR_TO_CODE[letter] = code
        CODE_TO_CHAR[code] = letter

SPECIAL_TRANSLATION = str.maketrans({
    "Đ": "D",
    "đ": "d",
    "Ł": "L",
    "ł": "l",
})


def normalize_text(text: str) -> str:
    """Odstraní diakritiku a převede text na velká písmena."""
    text = str(text or "").translate(SPECIAL_TRANSLATION)
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def tokenize_text(text: str) -> list[str]:
    """Rozdělí text na tokeny. Dvojice CH se bere jako jeden znak."""
    text = normalize_text(text)
    tokens: list[str] = []
    index = 0

    while index < len(text):
        if text[index:index + 2] == "CH":
            tokens.append("CH")
            index += 2
            continue

        tokens.append(text[index])
        index += 1

    return tokens


def encrypt(text: str) -> str:
    """Zašifruje text do Vlčácké šifry."""
    tokens = tokenize_text(text)
    words: list[list[str]] = []
    current_word: list[str] = []

    for token in tokens:
        if token.isspace():
            if current_word:
                words.append(current_word)
                current_word = []
            continue

        if token in CHAR_TO_CODE:
            current_word.append(CHAR_TO_CODE[token])
            continue

        if current_word:
            current_word[-1] += token
        else:
            current_word.append(token)

    if current_word:
        words.append(current_word)

    return "  ".join(" ".join(word) for word in words).strip()


def _decode_digit_run(run: str) -> str:
    """Dekóduje souvislý blok číslic po dvojicích."""
    decoded: list[str] = []
    index = 0

    while index < len(run):
        pair = run[index:index + 2]
        if len(pair) == 2 and pair in CODE_TO_CHAR:
            decoded.append(CODE_TO_CHAR[pair])
            index += 2
        else:
            decoded.append(run[index])
            index += 1

    return "".join(decoded)


def decrypt(text: str) -> str:
    """Dešifruje Vlčáckou šifru zpět na text."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    if re.search(r"\s{2,}", cleaned):
        raw_words = re.split(r"\s{2,}", cleaned)
        decoded_words: list[str] = []

        for raw_word in raw_words:
            raw_word = raw_word.strip()
            if not raw_word:
                continue

            compact = re.sub(r"(?<=\d{2})\s+(?=\d{2})", "", raw_word)
            decoded_words.append(re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), compact))

        return " ".join(decoded_words).strip()

    if re.search(r"\d{2}\s+\d{2}", cleaned):
        compact = re.sub(r"(?<=\d{2})\s+(?=\d{2})", "", cleaned)
        return re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), compact).strip()

    return re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), cleaned).strip()


def get_key_data() -> dict:
    """Vrátí data pro univerzální renderer klíčů."""
    items = []
    for group_number, letters in GROUPS.items():
        for index, letter in enumerate(letters, start=1):
            items.append((letter, f"{group_number}{index}"))

    return {
        "title": "Klíč šifry – Vlčácká šifra",
        "type": "generic",
        "columns": 6,
        "items": items,
        "description": "První číslo je skupina, druhé číslo je pozice znaku ve skupině.",
    }


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    print("Vstup:", sample)
    print("Šifra:", encrypted)
    print("Zpět:", decrypt(encrypted))
