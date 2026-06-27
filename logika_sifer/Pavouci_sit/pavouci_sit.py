"""Implementace šifry Pavoučí síť pro Šifrátor Mraveniště.

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


ENCODE_MAP = {
    "A": "BC",
    "B": "AC",
    "C": "AB",

    "D": "EF",
    "E": "DF",
    "F": "DE",

    "G": "HI",
    "H": "GI",
    "I": "GH",

    "J": "KL",
    "K": "JL",
    "L": "JK",

    "M": "NO",
    "N": "MO",
    "O": "MN",

    "P": "RS",
    "Q": "O",
    "R": "PS",
    "S": "PR",

    "T": "UV",
    "U": "TV",
    "V": "TU",

    "W": "W",

    "X": "YZ",
    "Y": "XZ",
    "Z": "XY",
}

DECODE_MAP = {value: key for key, value in ENCODE_MAP.items()}


def normalize_text(text: str) -> str:
    """Převede českou diakritiku na základní znaky a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encrypt(text: str) -> str:
    """Zašifruje text pomocí šifry Pavoučí síť.

    Písmena se lepí za sebe bez oddělovačů.
    Slova jsou oddělená mezerou.
    Symboly zůstávají beze změny.
    """
    normalized = normalize_text(text)

    result = []
    previous_was_space = False

    for char in normalized:
        if char.isspace():
            if result and not previous_was_space:
                result.append(" ")
                previous_was_space = True
            continue

        previous_was_space = False

        if char in ENCODE_MAP:
            result.append(ENCODE_MAP[char])
        else:
            result.append(char)

    return "".join(result).strip()


def _decode_alpha_token(token: str) -> str:
    """Dešifruje jednu souvislou skupinu písmen bez mezer.

    Většina znaků je dvoupísmenná dvojice.
    Výjimky podle klíče:
    Q = O
    W = W

    Proto se čte zleva doprava a přednost mají dvoupísmenné dvojice.
    """
    token = normalize_text(token)
    result = []
    index = 0

    while index < len(token):
        two = token[index:index + 2]
        one = token[index:index + 1]

        if len(two) == 2 and two in DECODE_MAP:
            result.append(DECODE_MAP[two])
            index += 2
            continue

        if one in DECODE_MAP:
            result.append(DECODE_MAP[one])
            index += 1
            continue

        # Nepodporovaný znak necháme v hranaté závorce, aby bylo vidět, kde je chyba.
        result.append(f"[{one}]")
        index += 1

    return "".join(result)


def decrypt(text: str) -> str:
    """Dešifruje šifru Pavoučí síť zpět na text.

    Podporuje:
    BCGIMNKL KLBCJL PRDF NOBCPR?

    Také podporuje zápis s oddělovači:
    BC|GI|MN|KL||KL|BC|JL
    """
    cleaned = text.strip()

    if not cleaned:
        return ""

    cleaned = cleaned.replace(" || ", "||")
    cleaned = cleaned.replace("|| ", "||")
    cleaned = cleaned.replace(" ||", "||")
    cleaned = cleaned.replace(" | ", "|")
    cleaned = cleaned.replace("| ", "|")
    cleaned = cleaned.replace(" |", "|")

    # Zápis s oddělovači písmen a slov.
    if "||" in cleaned or "|" in cleaned:
        words = []
        for raw_word in cleaned.split("||"):
            raw_word = raw_word.strip()
            if not raw_word:
                continue

            chars = []
            for token in raw_word.split("|"):
                token = token.strip()
                if not token:
                    continue

                normalized = normalize_text(token)
                chars.append(DECODE_MAP.get(normalized, token))

            words.append("".join(chars))

        return " ".join(words)

    # Běžný zápis bez oddělovačů.
    # Rozdělíme na písmenové bloky a ostatní symboly.
    parts = re.findall(r"[A-Za-zÁ-ž]+|[^A-Za-zÁ-ž]+", cleaned)
    output = []

    for part in parts:
        if re.fullmatch(r"[A-Za-zÁ-ž]+", part):
            output.append(_decode_alpha_token(part))
        else:
            output.append(part)

    return "".join(output).strip()


if __name__ == "__main__":
    sample = "Ahoj jak se máš?"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Šifra:", encrypted)
    print("Dešifrováno:", decrypted)
