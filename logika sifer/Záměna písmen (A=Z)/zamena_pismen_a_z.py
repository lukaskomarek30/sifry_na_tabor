# ============================================================
# Záměna písmen (A=Z) / Atbash
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Záměna písmen (A=Z)\zamena_pismen_a_z.py
#
# Princip podle klíče:
# A=Z, B=Y, C=X, D=W, E=V, F=U, G=T, H=S, I=R,
# J=Q, K=P, L=O, M=N a opačně.
#
# Symboly jako ?, . , - ! zůstávají beze změny.
# Česká diakritika se převede na písmena bez háčků a čárek.
# Velikost písmen se zachová.
# ============================================================

import unicodedata

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
    return transform(text)


def decrypt(text: str) -> str:
    # A=Z je obousměrná záměna, takže dešifrování je stejné jako šifrování.
    return transform(text)


if __name__ == "__main__":
    sample = "Ahoj jak se máš ?"
    encrypted = encrypt(sample)
    print("Vstup:", sample)
    print("Zašifrováno:", encrypted)
    print("Dešifrováno:", decrypt(encrypted))
