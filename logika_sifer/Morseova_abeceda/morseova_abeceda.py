"""Implementace šifry Morseova abeceda pro Šifrátor Mraveniště.

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

MORSE_TABLE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".",
    "F": "..-.", "G": "--.", "H": "....", "I": "..", "J": ".---",
    "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.", "S": "...", "T": "-",
    "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--",
    "Z": "--..",

    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",

    ".": ".-.-.-", ",": "--..--", "?": "..--..", "!": "-.-.--",
    ":": "---...", ";": "-.-.-.", "-": "-....-", "/": "-..-.",
    "(": "-.--.", ")": "-.--.-", "\"": ".-..-.", "'": ".----.",
    "=": "-...-", "+": ".-.-.", "@": ".--.-.",
}

REVERSE_MORSE_TABLE = {value: key for key, value in MORSE_TABLE.items()}

CZECH_TRANSLATION_TABLE = str.maketrans({
    "Á": "A", "Ä": "A", "Č": "C", "Ď": "D", "É": "E", "Ě": "E",
    "Í": "I", "Ň": "N", "Ó": "O", "Ö": "O", "Ř": "R", "Š": "S",
    "Ť": "T", "Ú": "U", "Ů": "U", "Ü": "U", "Ý": "Y", "Ž": "Z",
    "á": "A", "ä": "A", "č": "C", "ď": "D", "é": "E", "ě": "E",
    "í": "I", "ň": "N", "ó": "O", "ö": "O", "ř": "R", "š": "S",
    "ť": "T", "ú": "U", "ů": "U", "ü": "U", "ý": "Y", "ž": "Z",
})


def normalize_text(text: str) -> str:
    """Převede českou diakritiku na základní znaky vhodné pro Morseovu abecedu."""
    return text.translate(CZECH_TRANSLATION_TABLE).upper()


def encrypt(text: str) -> str:
    """Zašifruje text do Morseovy abecedy.

    Výstup:
    - jednotlivá písmena jsou oddělená znakem |
    - slova jsou oddělená znaky ||
    """
    normalized = normalize_text(text)

    encoded_words = []

    for word in normalized.split():
        encoded_letters = []

        for char in word:
            if char in MORSE_TABLE:
                encoded_letters.append(MORSE_TABLE[char])
            else:
                # Neznámé znaky zachováme, aby uživatel viděl, co se nepřevedlo.
                encoded_letters.append(f"[{char}]")

        encoded_words.append("|".join(encoded_letters))

    return "||".join(encoded_words)


def decrypt(text: str) -> str:
    """Dešifruje Morseovu abecedu zpět na text.

    Primární formát:
    - písmena: |
    - slova: ||

    Kvůli pohodlí umí přečíst i starší zápis:
    - mezera mezi písmeny
    - / mezi slovy
    - | mezi slovy ze staršího stylu
    """
    cleaned = text.strip()

    if not cleaned:
        return ""

    # Sjednocení mezer okolo oddělovačů.
    cleaned = cleaned.replace(" || ", "||")
    cleaned = cleaned.replace("|| ", "||")
    cleaned = cleaned.replace(" ||", "||")

    cleaned = cleaned.replace(" | ", "|")
    cleaned = cleaned.replace("| ", "|")
    cleaned = cleaned.replace(" |", "|")

    # Podpora staršího oddělovače slov.
    cleaned = cleaned.replace(" / ", "||")
    cleaned = cleaned.replace("/", "||")

    decoded_words = []

    for raw_word in cleaned.split("||"):
        raw_word = raw_word.strip()

        if not raw_word:
            continue

        # Nový formát: .-|....|---|.---
        if "|" in raw_word:
            symbols = [symbol.strip() for symbol in raw_word.split("|") if symbol.strip()]
        else:
            # Starší formát: .- .... --- .---
            symbols = raw_word.split()

        decoded_chars = []

        for symbol in symbols:
            decoded_chars.append(REVERSE_MORSE_TABLE.get(symbol, f"[{symbol}]"))

        decoded_words.append("".join(decoded_chars))

    return " ".join(decoded_words)
