# Šifrátor Mraveniště

Desktopová táborová aplikace vytvořená pro **Letní tábor Mraveniště**. Verze **v0.0.4** spojuje šifrátor, plánovač, oddíly, sportovní den, diplomy a tiskové nástroje do jednoho moderního pirátského rozhraní.

Aplikace podporuje více druhů šifer, generuje pirátské klíče, eviduje výsledky sportovního dne, připravuje diplomy a tiskové listiny a automaticky se aktualizuje na Windows i macOS.

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

- moderní hlavní menu s animovanými přechody a vlastními pirátskými pozadími,
- šifrování a dešifrování tajných zpráv,
- grafické zobrazení výsledků a pirátsky stylizované klíče šifer,
- čistý tisk šifrovacích klíčů bez dekorací a pozadí,
- plánovač táborového programu,
- hromadné šifrování, přehled šifer a historie zpráv,
- oddíly s dynamickým importem starších `.xls` i nových `.xlsx` souborů; čtečka starého XLS je přibalená přímo v aplikaci,
- opakovaný import stejného nebo změněného seznamu oddílů bezpečně sloučí změny, zachová ručně doplněné údaje a nevytváří duplicity,
- průhledné dlaždice oddílů s vedoucími, počtem dětí a věkovým průměrem,
- vyhledávání dětí i vedoucích s našeptáváním a upravitelnými osobními kartami,
- vlastní údaje osob (například telefon) a export všech nebo jednotlivých oddílů do Excelu,
- propojení jmen z oddílů s našeptáváním nového soutěžícího ve Sportovním dni,
- sportovní den s výzvami, věkovými kategoriemi, posádkou, výsledky a pokladem,
- sdílená pořadí při remíze a volitelná normalizace bodů s nastavitelným maximem,
- ochrana proti duplicitním názvům výzev, kategorií a jmen pirátů ve stejné kategorii,
- řazení výsledků a pokladu s animovaným bublinkovým efektem,
- tisk výsledků sportovního dne na různé formáty papíru,
- A6 kartičky výzev, čtyři stejné kartičky na jednom A4,
- diplomy za tábor a sportovní den v několika grafických variantách včetně světlého olympijského motivu,
- nové tiskoviny: diplom za úklid, denní program a jídelníček, vždy ve dvou grafických variantách,
- společný tiskový editor s pohyblivými průhlednými textovými poli, vlastní barvou písma, přidáváním dalších textů a změnou písma, velikosti, tučnosti, kurzívy, podtržení, přeškrtnutí, zarovnání i natočení,
- pokročilé typografické volby diplomů: rozestupy a šířka znaků, průhlednost, stín, změna velikosti písmen, svislé zarovnání a pořadí vrstev,
- přehledný široký editor diplomů bez vodorovného posouvání a ořezaných názvů voleb,
- přibalené pirátské písmo Pirata One s českou diakritikou a rychlým tlačítkem v editoru diplomů,
- A4 tabulka hodnocení úklidu třinácti chatek, ve které lze přesouvat a formátovat i nadpisy, data a názvy chatek,
- volitelný šetrný tisk, pirátské pozadí a zobrazení loga,
- živý náhled, ukládání do PDF a fyzický tisk,
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

Uživatelská data se neukládají do instalační složky aplikace, ale do profilu uživatele:

- Windows: `%APPDATA%\Sifrator_Mraveniste`
- macOS: `~/Library/Application Support/Sifrator_Mraveniste`
- Linux: `$XDG_DATA_HOME/Sifrator_Mraveniste` nebo `~/.local/share/Sifrator_Mraveniste`

Do této složky patří historie zpráv, plán tábora, importované a ručně upravené údaje oddílů, data sportovního dne, výsledky posádky, poznámky k šifrám, obrázky historie a lokálně vložené přílohy plánovače. Aktualizace programu proto může přepsat programové soubory, aniž by smazala uživatelský plán, oddíly, výsledky nebo poznámky.

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

Předgenerování cache klíčů pro rychlejší první spuštění vydané aplikace:

```bash
python main.py --prebuild-key-cache
```

Na Windows můžeš použít také:

```bat
predgenerovat_cache.bat
```

Soubory vzniknou ve složce `cache/key_cache`. Build workflow tuhle složku automaticky přibalí do Windows/macOS aplikace.

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

`update.json` a `SHA256SUMS.txt` v hlavní větvi vždy popisují poslední skutečně vydané balíčky. Před spuštěním release proto mohou ještě ukazovat starší veřejnou verzi; workflow je po úspěšném sestavení v0.0.4 samo aktualizuje a commitne.

Podrobný seznam změn je v souboru [`CHANGELOG.md`](CHANGELOG.md).

Přesný seznam souborů a postup publikace této aktualizace je v [`GIT_UPLOAD_V0.0.4.md`](GIT_UPLOAD_V0.0.4.md).

---

## Struktura projektu

```text
.
├─ .github/
│  └─ workflows/
├─ cache/
│  └─ key_cache/
├─ docs/
│  └─ img/
├─ icons/
│  ├─ diplomas/
│  ├─ documents/
│  ├─ fonts/
│  └─ print_backgrounds/
├─ logika_sifer/
├─ tools/
│  └─ build_sports_print_backgrounds.py
├─ vendor/
│  └─ xlrd/
├─ CHANGELOG.md
├─ diploma.py
├─ diploma_print.py
├─ fire_effects.py
├─ groups.py
├─ groups_data.py
├─ home_menu.py
├─ README.md
├─ README_PRVNI_SPUSTENI.md
├─ README_PRVNI_SPUSTENI.txt
├─ SHA256SUMS.txt
├─ main.py
├─ pirate_key_renderer.py
├─ requirements.txt
├─ sports_day.py
├─ sports_day_print.py
├─ test_sports_day_logic.py
├─ test_groups_data.py
├─ test_groups_ui.py
├─ test_diploma_print.py
├─ THIRD_PARTY_NOTICES.md
├─ update.json
└─ update_manager.py
```

---

## Aktuální verze zdrojového kódu

```text
v0.0.4
```

Hlavní změny v0.0.4:

- vestavěná podpora `.xls` bez nutnosti doinstalovávat knihovnu na starší instalaci,
- slučovací import oddílů bez duplikátů a bez ztráty ručních údajů,
- čtvrtá varianta diplomu za sportovní den podle světlého olympijského motivu,
- nové tiskoviny denního programu, diplomu za úklid a jídelníčku,
- dvě pirátské varianty a šetrný tisk každé nové tiskoviny,
- společný pohyblivý textový editor ve všech tiskovinách sekce Diplomy včetně hodnocení úklidu,
- nové automatické testy importu a tiskového studia.

---

## Autor

Projekt vytvořil **Lukáš Komárek** pro Letní tábor Mraveniště.
