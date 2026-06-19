Šifrátor Mraveniště – první spuštění

Tento soubor je textová verze návodu. Obrázková verze je v souboru:
README_PRVNI_SPUSTENI.md

============================================================
1. STAŽENÍ SPRÁVNÉ VERZE
============================================================

Windows 10/11 64-bit:
Sifrator_Mraveniste_windows-x64_vX.X.X.zip

Mac Apple Silicon / Apple A18 Pro / M1 / M2 / M3 / M4:
Sifrator_Mraveniste_macos-arm64_vX.X.X.zip

Mac Intel:
Sifrator_Mraveniste_macos-x64_vX.X.X.zip

Na Macu zjistíš typ procesoru v Terminálu:

uname -m

arm64  = stáhni macos-arm64
x86_64 = stáhni macos-x64


============================================================
WINDOWS – PRVNÍ SPUŠTĚNÍ
============================================================

1. Stáhni ZIP pro Windows.
2. ZIP rozbal například na plochu.
3. Otevři rozbalenou složku.
4. Spusť Sifrator_Mraveniste.exe.

Pokud Windows zobrazí SmartScreen:
Další informace → Přesto spustit


============================================================
macOS – PRVNÍ SPUŠTĚNÍ
============================================================

macOS může aplikaci zablokovat, protože aplikace zatím není podepsaná
placeným Apple Developer certifikátem. To je normální.

Doporučený postup:

1. Stáhni správný ZIP pro svůj Mac.
2. ZIP rozbal.
3. Přesuň Sifrator_Mraveniste.app do složky Applications / Aplikace.

Doporučená cesta:
/Applications/Sifrator_Mraveniste.app


------------------------------------------------------------
Varianta A – otevření přes Finder
------------------------------------------------------------

1. Otevři Applications / Aplikace.
2. Najdi Sifrator_Mraveniste.app.
3. Klikni na aplikaci pravým tlačítkem.
4. Zvol Open / Otevřít.
5. V potvrzovacím okně znovu klikni na Open / Otevřít.


------------------------------------------------------------
Varianta B – přes Privacy & Security
------------------------------------------------------------

Když se zobrazí hláška:

"Sifrator_Mraveniste" cannot be opened because it is from an unidentified developer.

Klikni na OK.

Potom otevři:

System Settings → Privacy & Security

Dole v části Security klikni na:

Open Anyway

Potom se zobrazí potvrzovací okno a klikni na:

Open

Od této chvíle by se aplikace měla spouštět normálně.


------------------------------------------------------------
Varianta C – Terminal
------------------------------------------------------------

Pokud macOS píše, že aplikace je poškozená nebo ji nelze ověřit,
spusť v Terminálu:

xattr -dr com.apple.quarantine "/Applications/Sifrator_Mraveniste.app"
chmod -R u+x "/Applications/Sifrator_Mraveniste.app/Contents/MacOS"
open "/Applications/Sifrator_Mraveniste.app"

Pokud aplikace zůstala ve stažených souborech:

cd ~/Downloads
xattr -dr com.apple.quarantine "Sifrator_Mraveniste.app"
chmod -R u+x "Sifrator_Mraveniste.app/Contents/MacOS"
open "Sifrator_Mraveniste.app"


============================================================
AKTUALIZACE APLIKACE
============================================================

Aplikace při startu kontroluje novou verzi podle update.json na GitHubu.

Na macOS doporučuji mít aplikaci ve složce:
/Applications/Sifrator_Mraveniste.app

Když se aplikace spouští přímo ze stažené složky nebo z dočasné cesty,
macOS může použít App Translocation a automatická aktualizace nemusí
přepsat skutečnou aplikaci.


============================================================
LOGOVÁNÍ A DIAGNOSTIKA
============================================================

V aplikaci je dole ve stavovém řádku:

LOGOVÁNÍ: Vypnuto

Kliknutím se otevře okno s live logy a stav se změní na:

LOGOVÁNÍ: Zapnuto

Po zavření okna se logování vypne.

Diagnostické logy:

Windows:
%TEMP%\sifrator_update_debug.log

macOS:
/tmp/sifrator_update_debug.log
/tmp/sifrator_update_install.log

Na Macu je zobrazíš:

cat /tmp/sifrator_update_debug.log
cat /tmp/sifrator_update_install.log


============================================================
RYCHLÉ PŘÍKAZY PRO macOS
============================================================

uname -m
xattr -dr com.apple.quarantine "/Applications/Sifrator_Mraveniste.app"
chmod -R u+x "/Applications/Sifrator_Mraveniste.app/Contents/MacOS"
open "/Applications/Sifrator_Mraveniste.app"
