# Šifrátor Mraveniště

Desktopová aplikace pro šifrování a dešifrování textů vytvořená pro **Letní tábor Mraveniště**.

Aplikace má pirátské grafické rozhraní, podporuje více druhů šifer, umí zobrazovat klíče šifer, tisknout výstupy a automaticky se aktualizovat na Windows i macOS.

---

## Stažení aplikace

Hotové instalační balíčky jsou v části **Releases**.

Vyber správný soubor podle systému:

| Systém | Soubor |
|---|---|
| Windows 10 / 11 x64 | `windows-x64` |
| macOS Apple Silicon | `macos-arm64` |
| macOS Intel | `macos-x64` |

Po stažení ZIP rozbal a spusť aplikaci.

---

## Podporované systémy

| Platforma | Stav |
|---|---|
| Windows 10 / 11 x64 | Podporováno |
| macOS Apple Silicon | Podporováno |
| macOS Intel | Podporováno |

---

## Hlavní funkce

- výběr šifry ze seznamu,
- šifrování a dešifrování tajné zprávy,
- grafické zobrazení výsledku u vybraných šifer,
- kopírování výsledku,
- zobrazení klíče šifry,
- tisk textu i klíče,
- automatická kontrola aktualizací,
- ruční kontrola aktualizací,
- logovací okno,
- podpora Windows a macOS buildů přes GitHub Actions.

---

## Podporované šifry

Aplikace obsahuje například:

- Binární čtverce,
- Braillovo písmo,
- Britská vlajka,
- Caesarova šifra,
- Čtverec,
- Hebrejský kříž,
- Malý polský kříž,
- Mobil,
- Moonovo písmo,
- Morseova abeceda,
- Morseova abeceda – hory,
- Morseova abeceda – pila,
- Morseova abeceda – stromy,
- Mříž,
- Okno,
- Pavoučí síť,
- Posunková abeceda,
- Pseudo-Čína,
- Semafor,
- SuperKrychle,
- Tančící figurky,
- Tančící figurky II,
- Velký polský kříž,
- Velký polský kříž (26 znaků),
- Vlčácká šifra,
- Záměna písmen,
- Záměna písmen za čísla,
- Zednářská šifra,
- Zlomky.

---

## První spuštění

Podrobný návod pro první spuštění je v souboru:

```text
README_PRVNI_SPUSTENI.md
```

Na macOS může být při prvním spuštění potřeba povolit aplikaci v nastavení zabezpečení, protože aplikace zatím není podepsaná placeným Apple Developer certifikátem.

Základní oprava blokace na macOS:

```bash
xattr -dr com.apple.quarantine "/Applications/Sifrator_Mraveniste.app"
chmod -R u+x "/Applications/Sifrator_Mraveniste.app/Contents/MacOS"
open "/Applications/Sifrator_Mraveniste.app"
```

---

## Automatické aktualizace

Aplikace používá soubor:

```text
update.json
```

Ten obsahuje:

- aktuální verzi,
- odkazy na balíčky pro Windows a macOS,
- SHA256 kontrolní součty,
- názvy instalačních souborů.

Podporované aktualizační platformy:

```text
windows-x64
macos-arm64
macos-x64
```

---

## Vývojové spuštění

Instalace knihoven:

```bash
python -m pip install -r requirements.txt
```

Spuštění aplikace:

```bash
python main.py
```

Smoke test:

```bash
python main.py --smoke-test
```

---

## Build a release

Buildy pro Windows a macOS se vytváří přes GitHub Actions.

Používané workflow soubory:

```text
.github/workflows/build-release.yml
.github/workflows/test-buildy.yml
```

Vydání nové verze:

```text
Actions → Build release → Run workflow
version: auto
mode: release_after_approval
```

Workflow vytvoří:

- Windows ZIP,
- macOS Apple Silicon ZIP,
- macOS Intel ZIP,
- `update.json`,
- `SHA256SUMS.txt`,
- GitHub Release poznámky.

---

## Struktura projektu

```text
.
├─ .github/
│  └─ workflows/
├─ docs/
│  └─ img/
├─ icons/
├─ logika sifer/
├─ README.md
├─ README_PRVNI_SPUSTENI.md
├─ README_PRVNI_SPUSTENI.txt
├─ SHA256SUMS.txt
├─ main.py
├─ pirate_key_renderer.py
├─ requirements.txt
├─ update.json
└─ update_manager.py
```

---

## Stav projektu

První stabilní verze:

```text
v0.0.1
```

Další plánovaná vylepšení:

- trvalá cache klíčů šifer,
- test všech šifer,
- postupné rozdělení velkého `main.py`,
- čistší registry šifer,
- lepší interní struktura projektu.

---

## Autor

Projekt vytvořil **Lukáš Komárek** pro Letní tábor Mraveniště.
