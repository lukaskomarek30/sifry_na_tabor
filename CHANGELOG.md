# Přehled změn

## v0.0.4 – 5. srpna 2026

### Tiskoviny a editor

- Do diplomu za sportovní den přibyla čtvrtá světlá varianta podle dodaného olympijského vzoru.
- Přidány samostatné tiskoviny **Denní program**, **Diplom za úklid** a **Jídelníček**; každá obsahuje dodaný motiv i novou pirátskou variantu.
- Denní program a jídelníček se tisknou na celý A4 na výšku, diplom za úklid jako dvě stejné A5 na jednom A4.
- Všechny nové tiskoviny nabízejí plnobarevný i šetrný tisk a volitelné logo.
- Společný editor textových polí je dostupný ve všech tiskovinách sekce Diplomy včetně hodnocení úklidu.
- Textová pole lze přímo v náhledu vybírat, přesouvat, měnit jejich velikost, kopírovat, odstraňovat a doplňovat.
- Každé pole podporuje vlastní text, font, Pirata One, velikost, barvu, tučnost, kurzívu, podtržení, přeškrtnutí, zarovnání, mezery znaků, šířku, průhlednost, stín, natočení a pořadí vrstev.
- U tabulky hodnocení úklidu jsou samostatně upravitelné také názvy třinácti chatek, všechna data, součet, pořadí, horní a spodní text.
- Šetrný tisk dokáže zesvětlit i plnobarevnou variantu, takže zůstane jemný motiv a výrazně klesne spotřeba inkoustu.

### Oddíly a Excel

- Čtečka staršího formátu `.xls` je přibalená přímo ve složce `vendor/xlrd`; starší instalace už nemusí knihovnu ručně doinstalovávat.
- Opakovaný import stejného Excelu nevytváří duplicitní oddíly ani osoby.
- Změněný Excel aktualizuje odpovídající záznamy, přidá nové osoby a zachová ručně doplněná pole, například telefon.
- Import na závěr ukazuje počet nových, aktualizovaných, nezměněných a zachovaných záznamů.

### Vydání a kontrola kvality

- Verze aplikace zvýšena na `0.0.4`.
- Buildy pro Windows i macOS balí přibalenou čtečku XLS a všechny nové grafické podklady.
- Smoke test ověřuje dostupnost nových tiskovin i XLS podpory.
- Přidány testy slučovacího importu bez duplicit a společného tiskového editoru.

## v0.0.3 – 4. srpna 2026

### Nové moduly a vzhled

- Přidána moderní **Velitelská paluba** s animovaným přechodem do všech částí aplikace.
- Každý hlavní modul používá vlastní pirátské pozadí a efekty plápolajícího ohně.
- Přidány samostatné obrazovky pro plánovač, hromadné šifrování, přehled šifer a historii zpráv.

### Oddíly a import Excelu

- Přidána dlaždice **Oddíly** s vlastním moderním pirátským pozadím a průhlednými kartami.
- Každý list stejně strukturovaného souboru `.xls` nebo `.xlsx` se automaticky načte jako samostatný oddíl bez omezení počtu oddílů, dětí nebo vedoucích.
- Dlaždice ukazují vedoucí, počet dětí a automaticky počítaný věkový průměr dětí.
- Přidáno vyhledávání všech osob s našeptáváním a přímým otevřením nalezené osobní karty.
- V detailu oddílu zůstávají vedoucí stále viditelní a děti mají přehled všech importovaných údajů.
- Osobní karty dovolují měnit všechny údaje, přidávat vlastní položky (například telefon), měnit zařazení dítě/vedoucí a osobu odstranit.
- Přidán export všech oddílů nebo jednoho vybraného oddílu do přehledného Excelu včetně vlastních doplněných údajů.
- Jména z Oddílů se automaticky nabízejí při zakládání soutěžícího ve Sportovním dni.

### Šifrátor a klíče

- Klíče všech podporovaných šifer se zobrazují v jednotném pirátském stylu a s příslušným symbolem šifry.
- Tisk klíčů zůstává čistý, bílý a bez dekorativního pozadí či loga.
- Přidána a předgenerována trvalá cache klíčů pro rychlejší první otevření.

### Sportovní den

- Přidána správa výzev, věkových kategorií a posádky.
- Kartu každého piráta lze otevřít a upravit včetně poznámek a výsledků všech výzev.
- Přidán žebříček, celkový poklad, filtrování a posuvníky pro dlouhé seznamy.
- Výsledky a poklad lze seřadit animovaným bublinkovým řazením.
- Remízy používají husté sdílené pořadí `1-1-2-2-3` a shodní soutěžící získají stejné body.
- Časy ve formátu `mm:ss` odmítají neplatné sekundy a záporné hodnoty.
- Normalizace bodů je volitelná a maximum za první místo lze nastavit přímo v rozhraní.
- Duplicitní výzvy, kategorie a jména pirátů ve stejné kategorii jsou blokována s vysvětlením.

### Tisk sportovního dne

- Přidáno moderní tiskové studio s živým náhledem, PDF a fyzickým tiskem.
- Podporovány jsou formáty A3, A4, A5, A6, Letter a Legal na výšku i na šířku.
- Každý formát má vlastní přesně připravené pirátské a šetrné pozadí.
- Tabulky používají průhledné buňky, aby zůstalo viditelné pozadí.
- Lze samostatně zapnout šetrný tisk, logo, nadpis, souhrnné dlaždice a rámečky.
- Přidán tisk A6 kartiček: všechny výzvy jsou na jedné kartě a čtyři stejné karty se tisknou na A4.

### Diplomy a táborové listiny

- Přidány tři varianty diplomu za tábor a tři varianty diplomu za sportovní den.
- Jeden diplom má formát A5; na jednom A4 se tisknou dva stejné diplomy.
- Veškerý text diplomu lze upravit v živém náhledu jako samostatná průhledná textová pole.
- Textová pole lze vybírat přímo na diplomu, přesouvat myší, měnit jejich velikost, přidávat, kopírovat a odstraňovat.
- Každé pole má vlastní styl písma, velikost, tučnost, kurzívu, podtržení, zarovnání a natočení; stejné úpravy se přesně přenesou do PDF a tisku.
- Doplněna vlastní barva písma s možností návratu k automatické kontrastní barvě podle pozadí.
- Přidáno přeškrtnutí, svislé zarovnání, převod velikosti písmen, mezery mezi znaky, roztažení písma, průhlednost, jemný stín a pořadí textových vrstev.
- Formát vybraného textu i celé výchozí rozložení lze samostatně obnovit.
- Levý editor diplomu byl rozšířen, názvy voleb jsou vždy nad ovládáním a vodorovný posuv byl odstraněn, takže se menu už samo neschovává doprava.
- Přidán font Pirata One s českou diakritikou; titul a jméno ho používají automaticky a na libovolné pole jej lze použít samostatným tlačítkem.
- Font je přibalen včetně původní licence SIL Open Font License 1.1.
- Přidána A4 tabulka hodnocení úklidu třinácti chatek pro období 9.–22. srpna.
- Každý tisk nabízí plnobarevnou a šetrnou variantu a volitelné zobrazení loga.

### Vnitřní změny

- Tisk sportovního dne byl oddělen do `sports_day_print.py`.
- Přidány automatické testy bodování, remíz, validace času, normalizační stupnice a duplicit.
- Uživatelská data sportovního dne se ukládají mimo instalační složku a aktualizace je zachová.

## v0.0.2

- Poslední veřejně vydaná verze před rozšířením aplikace o Velitelskou palubu a sportovní den.
