# Použité komponenty třetích stran

## Pirata One

- Autoři: Rodrigo Fuenzalida a Nicolas Massi
- Soubor: `icons/fonts/PirataOne-Regular.ttf`
- Zdroj: Google Fonts, `google/fonts/ofl/pirataone`
- Licence: SIL Open Font License 1.1
- Úplné znění licence: `icons/fonts/PirataOne-OFL.txt`

Font je v aplikaci použit beze změn a je přibalen kvůli jednotnému pirátskému vzhledu diplomů na Windows i macOS.

## xlrd 2.0.2

- Autoři: xlrd contributors
- Soubory: `vendor/xlrd/`
- Účel: čtení staršího tabulkového formátu Microsoft Excel `.xls`
- Licence: BSD
- Úplné znění licence: `vendor/xlrd/LICENSE.txt`

Knihovna je přibalená jako záložní čtečka. Pokud je `xlrd` nainstalované v systému, použije se systémová verze; jinak aplikace automaticky použije tuto přibalenou kopii.
