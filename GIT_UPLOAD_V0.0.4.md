# Publikace aktualizace v0.0.4 na GitHub

Tento projektový adresář už obsahuje zdrojový kód připravený jako verze `0.0.4`.

Ověřeno 5. srpna 2026: veřejná větev `main` na GitHubu má v `main.py` a `update.json` stále verzi `0.0.2`. Proto je nutné nahrát celý současný lokální projekt, ne jen soubory přidané v posledním kroku.

## Co nahrát

Nejbezpečnější je na GitHub nahrát **celý obsah složky projektu** `sifry_na_tabor-main`, aby nechyběl žádný obrázek, test ani buildovací soubor. Zvlášť zkontroluj, že se nahrály i skryté workflow soubory ve složce `.github`.

Pro tuto aktualizaci jsou nezbytné zejména:

- `.github/workflows/build-release.yml`
- `.github/workflows/test-buildy.yml`
- `main.py`
- `home_menu.py`
- `diploma.py`
- `diploma_print.py`
- `groups.py`
- `groups_data.py`
- `update_manager.py`
- `requirements.txt`
- `README.md`
- `README_PRVNI_SPUSTENI.md`
- `README_PRVNI_SPUSTENI.txt`
- `CHANGELOG.md`
- `THIRD_PARTY_NOTICES.md`
- `GIT_UPLOAD_V0.0.4.md`
- `test_diploma_print.py`
- `test_groups_data.py`
- `test_groups_ui.py`
- celý adresář `vendor/`, hlavně `vendor/xlrd/` a jeho `LICENSE.txt`
- `icons/diplomas/sports_d.png`
- celý adresář `icons/documents/` se soubory:
  - `daily_a.png`
  - `daily_b.png`
  - `cleaning_award_a.png`
  - `cleaning_award_b.png`
  - `meal_a.png`
  - `meal_b.png`

Protože na GitHubu ještě nejsou předchozí lokální změny v0.0.3, nahraj opravdu celý projekt včetně `sports_day.py`, `sports_day_print.py`, `icons/`, `cache/key_cache/`, `logika_sifer/`, `docs/`, `tools/` a všech ostatních zdrojových souborů.

## Co nenahrávat

- `.git/`
- `__pycache__/` a `*.pyc`
- `.pytest_cache/`
- `output/`
- `build/`, `dist/`, lokální ZIPy a EXE
- dočasné vývojové náhledy
- původní podklady z plochy; aplikace už používá očištěné kopie v `icons/`

Současné `update.json` a `SHA256SUMS.txt` mohou před vydáním stále popisovat poslední veřejnou verzi. Neupravuj v nich ručně odkazy ani kontrolní součty. Release workflow je po úspěšném sestavení v0.0.4 vytvoří z hotových balíčků, nahraje k vydání a commitne zpět do hlavní větve.

## Jak vydat aktualizaci

1. Nahraj uvedené změny do hlavní větve repozitáře.
2. Otevři na GitHubu `Actions` → `Build release` → `Run workflow`.
3. Do `version` zadej přesně `0.0.4`. Nepoužívej tentokrát `auto`, protože veřejná verze je stále `v0.0.2` a automatika by mohla vytvořit pouze `v0.0.3`.
4. Zvol `mode: release_after_approval`.
5. Potvrď chráněné prostředí `release-approval`, pokud si ho workflow vyžádá.
6. Po dokončení zkontroluj nové vydání `v0.0.4`, tři ZIP balíčky, `update.json` a `SHA256SUMS.txt`.

Starší nainstalovaná aplikace pak při své další kontrole načte nové `update.json` a nabídne aktualizaci na v0.0.4.
