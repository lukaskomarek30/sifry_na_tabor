"""Implementace šifry Záměna písmen (A=Z) pro Šifrátor Mraveniště.

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
REVERSED = "ZYXWVUTSRQPONMLKJIHGFEDCBA"

ENCRYPT_TABLE_UPPER = str.maketrans(ALPHABET, REVERSED)
ENCRYPT_TABLE_LOWER = str.maketrans(ALPHABET.lower(), REVERSED.lower())


def remove_diacritics(text: str) -> str:
    """Převede české znaky na písmena bez háčků a čárek."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def transform(text: str) -> str:
    """Provede A=Z záměnu. Neznámé znaky, čísla a symboly nechá beze změny."""
    text = remove_diacritics(text)
    result: list[str] = []

    for char in text:
        if "A" <= char <= "Z":
            result.append(char.translate(ENCRYPT_TABLE_UPPER))
        elif "a" <= char <= "z":
            result.append(char.translate(ENCRYPT_TABLE_LOWER))
        else:
            result.append(char)

    return "".join(result)


def encrypt(text: str) -> str:
    """Zašifruje vstupní text podle pravidel konkrétní šifry."""
    return transform(text)


def decrypt(text: str) -> str:
    # A=Z je obousměrná záměna, takže dešifrování je stejné jako šifrování.
    """Dešifruje vstupní text zpět do běžné textové podoby."""
    return transform(text)


if __name__ == "__main__":
    sample = "Ahoj jak se máš ?"
    encrypted = encrypt(sample)
    print("Vstup:", sample)
    print("Zašifrováno:", encrypted)
    print("Dešifrováno:", decrypt(encrypted))
