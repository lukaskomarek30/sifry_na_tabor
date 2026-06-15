"""Implementace šifry Vlčácká šifra pro Šifrátor Mraveniště.

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

import re
import unicodedata

GROUPS = {
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


# Některé české znaky se přes NFKD nerozloží vždy tak, jak chceme.
SPECIAL_TRANSLATION = str.maketrans({
    "Đ": "D", "đ": "d",
    "Ł": "L", "ł": "l",
})


def normalize_text(text: str) -> str:
    """Odstraní diakritiku a převede text na velká písmena."""
    text = text.translate(SPECIAL_TRANSLATION)
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def tokenize_text(text: str) -> list[str]:
    """Rozdělí text na tokeny. CH je jeden token."""
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
    """Zašifruje text do Vlčácké šifry.

    Příklad:
        Ahoj jak se máš? -> 11 32 61 42  42 11 43  72 22  52 11 72?

    Výstup:
    - písmena ve slově mají mezi sebou jednu mezeru
    - slova mají mezi sebou dvě mezery
    - interpunkce zůstává připojená k místu, kde byla napsaná
    """
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

        # Symboly a nepodporované znaky ponecháme beze změny.
        # Pokud je symbol za písmenem, připojí se k předchozímu kódu.
        # Například S? -> 72?
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
    """Dešifruje Vlčáckou šifru zpět na text.

    Podporuje nový zápis:
        11 32 61 42  42 11 43  72 22  52 11 72?

    A také starší kompaktní zápis:
        11326142 421143 7222 521172?
    """
    cleaned = text.strip()
    if not cleaned:
        return ""

    # Nový zápis: dvě a více mezer oddělují slova, jednoduché mezery uvnitř slov oddělují písmena.
    if re.search(r"\s{2,}", cleaned):
        raw_words = re.split(r"\s{2,}", cleaned)
        decoded_words: list[str] = []

        for raw_word in raw_words:
            raw_word = raw_word.strip()
            if not raw_word:
                continue

            # Uvnitř slova ignorujeme jednoduché mezery mezi kódy.
            compact = re.sub(r"(?<=\d{2})\s+(?=\d{2})", "", raw_word)
            decoded_words.append(re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), compact))

        return " ".join(decoded_words).strip()

    # Pokud jsou v textu jednoduché mezery mezi dvojicemi, ale nejsou tam dvojité mezery,
    # bereme je jako oddělovače písmen v jednom slově.
    if re.search(r"\d{2}\s+\d{2}", cleaned):
        compact = re.sub(r"(?<=\d{2})\s+(?=\d{2})", "", cleaned)
        return re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), compact).strip()

    # Starší standardní výstup: slova jsou oddělena jednou mezerou, uvnitř slov mezery nejsou.
    return re.sub(r"\d+", lambda m: _decode_digit_run(m.group(0)), cleaned)


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    print("Vstup:", sample)
    print("Šifra:", encrypted)
    print("Zpět:", decrypt(encrypted))
