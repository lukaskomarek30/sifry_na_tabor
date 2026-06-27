# Šifrátor Mraveniště – první spuštění

Tento návod slouží pro první spuštění aplikace **Sifrator_Mraveniste** na Windows a macOS.

---

## 1. Stažení správné verze

Na GitHub Releases stáhni správný ZIP podle systému:

| Systém | Soubor |
|---|---|
| Windows 10/11 64-bit | `Sifrator_Mraveniste_windows-x64_vX.X.X.zip` |
| Mac s Apple Silicon / Apple A18 Pro / M1 / M2 / M3 / M4 | `Sifrator_Mraveniste_macos-arm64_vX.X.X.zip` |
| Mac s procesorem Intel | `Sifrator_Mraveniste_macos-x64_vX.X.X.zip` |

Na Macu zjistíš typ procesoru v Terminálu příkazem:

```bash
uname -m
```

Výsledek:

```text
arm64  = stáhni macos-arm64
x86_64 = stáhni macos-x64
```

---

# Windows – první spuštění

1. Stáhni ZIP pro Windows.
2. ZIP rozbal například na plochu.
3. Otevři rozbalenou složku.
4. Spusť soubor:

```text
Sifrator_Mraveniste.exe
```

Pokud Windows zobrazí varování SmartScreen, zvol:

```text
Další informace → Přesto spustit
```

---

# macOS – první spuštění

macOS může aplikaci zablokovat, protože aplikace zatím není podepsaná placeným Apple Developer certifikátem. To je očekávané chování.

## Doporučený postup

1. Stáhni správný ZIP pro svůj Mac.
2. ZIP rozbal.
3. Přesuň aplikaci:

```text
Sifrator_Mraveniste.app
```

do složky:

```text
Applications / Aplikace
```

Doporučené umístění:

```text
/Applications/Sifrator_Mraveniste.app
```

---

## Varianta A – otevření přes Finder

1. Otevři složku **Applications / Aplikace**.
2. Najdi **Sifrator_Mraveniste.app**.
3. Klikni na aplikaci pravým tlačítkem.
4. Zvol **Open / Otevřít**.
5. Pokud se zobrazí potvrzovací okno, klikni na **Open / Otevřít**.

---

## Varianta B – přes Privacy & Security

Při prvním spuštění se může zobrazit toto okno:

![macOS blocked unidentified developer](docs/img/macos_01_blocked_unidentified_developer.png)

Klikni na **OK**.

Potom otevři:

```text
System Settings → Privacy & Security
```

Dole v části **Security** se zobrazí informace, že aplikace byla zablokována.

Klikni na:

```text
Open Anyway
```

![macOS Privacy & Security Open Anyway](docs/img/macos_03_privacy_security_open_anyway.png)

Potom se zobrazí potvrzovací okno. Klikni na:

```text
Open
```

![macOS Open confirmation](docs/img/macos_02_open_confirmation.png)

Od této chvíle by se aplikace měla spouštět normálně.

---

## Varianta C – Terminal, když macOS píše, že aplikace je poškozená

Pokud macOS napíše něco jako:

```text
aplikace je poškozená a nelze ji otevřít
```

nebo:

```text
cannot be opened because Apple cannot check it for malicious software
```

spusť v Terminálu:

```bash
xattr -dr com.apple.quarantine "/Applications/Sifrator_Mraveniste.app"
chmod -R u+x "/Applications/Sifrator_Mraveniste.app/Contents/MacOS"
open "/Applications/Sifrator_Mraveniste.app"
```

Pokud aplikace zůstala ve stažených souborech, použij místo toho:

```bash
cd ~/Downloads
xattr -dr com.apple.quarantine "Sifrator_Mraveniste.app"
chmod -R u+x "Sifrator_Mraveniste.app/Contents/MacOS"
open "Sifrator_Mraveniste.app"
```

Lepší je ale aplikaci přesunout do **Applications / Aplikace**.

---

# Aktualizace aplikace

Aplikace při startu kontroluje novou verzi podle souboru `update.json` na GitHubu.

Pokud je dostupná nová verze, zobrazí se okno s nabídkou aktualizace.

Na macOS doporučuji mít aplikaci ve složce:

```text
/Applications/Sifrator_Mraveniste.app
```

Když se aplikace spouští přímo ze stažené složky nebo z dočasné cesty, macOS může použít App Translocation a automatická aktualizace nemusí přepsat skutečnou aplikaci.

---

# Logování a diagnostika

V aplikaci je dole ve stavovém řádku položka:

```text
LOGOVÁNÍ: Vypnuto
```

Kliknutím se otevře okno s live logy a stav se změní na:

```text
LOGOVÁNÍ: Zapnuto
```

Po zavření okna se logování vypne.

Diagnostické logy aktualizací jsou zde:

## Windows

```text
%TEMP%\sifrator_update_debug.log
```

## macOS

```text
/tmp/sifrator_update_debug.log
/tmp/sifrator_update_install.log
```

Na Macu je zobrazíš příkazy:

```bash
cat /tmp/sifrator_update_debug.log
cat /tmp/sifrator_update_install.log
```

---

# Když aplikace nejde spustit

Zkontroluj:

1. Máš správný balíček pro svůj systém.
2. Na Macu používáš `macos-arm64` pro Apple Silicon / A18 Pro / M1 / M2 / M3 / M4.
3. Aplikace je rozbalená ze ZIPu.
4. Na Macu je ideálně přesunutá do složky `/Applications`.
5. Na Macu jsi povolil spuštění v **Privacy & Security**.
6. Pokud je potřeba, odstranil jsi quarantine atribut přes `xattr`.

---

# Rychlé příkazy pro macOS

```bash
uname -m
xattr -dr com.apple.quarantine "/Applications/Sifrator_Mraveniste.app"
chmod -R u+x "/Applications/Sifrator_Mraveniste.app/Contents/MacOS"
open "/Applications/Sifrator_Mraveniste.app"
```
