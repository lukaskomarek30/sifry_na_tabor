# ============================================================
# Mobil - logika šifrování a dešifrování
# Umístění:
# C:\Users\lukas\Desktop\Šifry\logika sifer\Mobil\mobil.py
#
# Klíč:
#
# 2 = A B C
# 3 = D E F
# 4 = G H I
# 5 = J K L
# 6 = M N O
# 7 = P Q R S
# 8 = T U V
# 9 = W X Y Z
#
# Princip:
# A = 2
# B = 22
# C = 222
#
# Formát výstupu podle požadavku:
# - čísla jednoho písmene jsou u sebe
# - písmena jsou bez mezery
# - slova od sebe mají jednu mezeru
#
# Příklad:
# Ahoj jak se máš?
# 2446665 5255 777733 627777?
#
# Symboly jako ?, . , - ! : ; / zůstávají symboly.
# Číslice ve vstupu se zapisují jako [1], [2], aby se nepletly se šifrou.
#
# Důležité:
# Bez mezer mezi písmeny není dešifrování vždy jednoznačné.
# Například 222 může znamenat C, nebo AB, nebo BA, nebo AAA.
# Dešifrování proto používá nejdelší možný platný zápis.
# ============================================================

import unicodedata


KEYPAD = {
    "2": "ABC",
    "3": "DEF",
    "4": "GHI",
    "5": "JKL",
    "6": "MNO",
    "7": "PQRS",
    "8": "TUV",
    "9": "WXYZ",
}

LETTER_TO_CODE = {}
CODE_TO_LETTER = {}

for key, letters in KEYPAD.items():
    for index, letter in enumerate(letters, start=1):
        code = key * index
        LETTER_TO_CODE[letter] = code
        CODE_TO_LETTER[code] = letter


def normalize_text(text: str) -> str:
    """Převede českou diakritiku pryč a text na velká písmena."""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return normalized.upper()


def encode_char(char: str) -> str:
    """Převede jeden znak na mobilní šifru."""
    if char in LETTER_TO_CODE:
        return LETTER_TO_CODE[char]

    if char.isdigit():
        return f"[{char}]"

    return char


def encrypt(text: str) -> str:
    """Zašifruje text do mobilní šifry.

    Výstup:
    - písmena jsou bez mezery
    - slova jsou oddělená jednou mezerou
    """
    normalized = normalize_text(text)
    words: list[str] = []
    current_word: list[str] = []

    for char in normalized:
        if char.isspace():
            if current_word:
                words.append("".join(current_word))
                current_word = []
            continue

        current_word.append(encode_char(char))

    if current_word:
        words.append("".join(current_word))

    return " ".join(words)


def decode_token(token: str) -> str:
    """Dešifruje jeden token."""
    if not token:
        return ""

    if token.startswith("[") and token.endswith("]"):
        return token[1:-1]

    if token in CODE_TO_LETTER:
        return CODE_TO_LETTER[token]

    return token


def split_compact_mobile_word(raw_word: str) -> list[str]:
    """Rozdělí slovo bez mezer na mobilní tokeny.

    Používá nejdelší možné platné tokeny pro jednotlivé skupiny stejných číslic.
    Například:
    7777 -> S
    666 -> O
    44 -> H
    2222 -> C A
    """
    tokens: list[str] = []
    index = 0

    while index < len(raw_word):
        char = raw_word[index]

        # Mobilní čísla 2-9.
        if char in KEYPAD:
            end = index + 1
            while end < len(raw_word) and raw_word[end] == char:
                end += 1

            run = raw_word[index:end]
            max_len = len(KEYPAD[char])

            while len(run) > max_len:
                tokens.append(run[:max_len])
                run = run[max_len:]

            if run:
                tokens.append(run)

            index = end
            continue

        # Původní číslice v hranaté závorce, třeba [1].
        if char == "[":
            end = raw_word.find("]", index + 1)
            if end != -1:
                tokens.append(raw_word[index:end + 1])
                index = end + 1
                continue

        # Symboly necháme tak, jak jsou.
        tokens.append(char)
        index += 1

    return tokens


def decrypt(text: str) -> str:
    """Dešifruje mobilní šifru zpět na text.

    Doporučený vstup:
    2446665 5255 777733 627777?

    Podporuje i starší formáty:
    2 44 666 5  5 2 55
    2|44|666|5||5|2|55
    """
    cleaned = text.strip()

    if not cleaned:
        return ""

    # Starý formát s || nebo lomítkem převedeme na jednu mezeru mezi slovy.
    cleaned = cleaned.replace(" || ", " ")
    cleaned = cleaned.replace("||", " ")
    cleaned = cleaned.replace(" / ", " ")
    cleaned = cleaned.replace("/ ", " ")
    cleaned = cleaned.replace(" /", " ")
    cleaned = cleaned.replace("/", " ")

    decoded_words: list[str] = []

    for raw_word in cleaned.split():
        raw_word = raw_word.strip()

        if not raw_word:
            continue

        # Starší formát s | mezi písmeny.
        if "|" in raw_word:
            tokens = [token for token in raw_word.split("|") if token]
        else:
            tokens = split_compact_mobile_word(raw_word)

        decoded_word = "".join(decode_token(token) for token in tokens)
        decoded_words.append(decoded_word)

    return " ".join(decoded_words)


if __name__ == "__main__":
    sample = "Ahoj jak se máš? 123"
    encrypted = encrypt(sample)
    decrypted = decrypt(encrypted)

    print("Vstup:", sample)
    print("Zašifrováno:", encrypted)
    print("Dešifrováno:", decrypted)
