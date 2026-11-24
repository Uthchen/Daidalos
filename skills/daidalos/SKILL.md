---
name: daidalos
description: "Zeichnet und deutet die Daidalos-Karte einer Codebase: misst mit dem Programm daidalos, wie Module, Pakete und Dateien verflochten sind, benennt Bereiche, beschreibt Module, Pakete, wichtige Dateien und wichtige Funktionen in je einem Satz, gewichtet Befunde wie Zyklen mit Begründung und Vorschlag und rendert karte.html und KARTE.md. Verwenden bei „Karte erstellen“, „Codebase-Karte aktualisieren“, „daidalos“, „Architektur-Karte“, „was hängt woran“, „warum hängt X an Y“, „wo sind Zyklen“, und führt auf Zuruf Schritt für Schritt durch die Karte („führe mich …“, „zeig mir den Weg von … bis …“, „erklär mir, wie … abläuft“), auch wenn das Wort Daidalos nicht fällt."
argument-hint: "[zielrepo]"
---

# Daidalos deuten

Das Programm `daidalos` misst, du deutest. Du schreibst nur, was sich aus der Messung und aus
Code ergibt, den du gelesen hast. Das Programm setzt Hashes ein, prüft Ids und speichert; die
Texte schreibst du.

Ziel ist das Argument, sonst das aktuelle Verzeichnis (Zielrepo). Alle Ausgaben liegen in
`docs/daidalos/` des Zielrepos.

> **Nur für die Entwicklung im Daidalos-Repo:** Nennt der Benutzer ein Ziel aus `lokal/ziele.toml`,
> zuerst `uv run python werkzeuge/ziel_auffrischen.py NAME` laufen lassen und die Pfade aus dessen
> letzter Zeile verwenden (Klon als Ziel, `--daten`, `--deutung`, `--ausgabe`, `--konfiguration`).

## Feste Regeln

- **Keine Zahl erfinden.** Zahlen stammen aus Zusammenfassung, Arbeitsblatt oder `daidalos pfad`
  und werden in Texten höchstens zitiert.
- **Nur über Gelesenes schreiben.** Über Code, den du nicht gelesen hast (Arbeitsblatt oder Datei),
  schreibst du nichts. Im Zweifel kürzer.
- **Jede Aussage hängt an einer Id** (Knoten, Befund, Kante). Ids kopierst du aus den Ausgaben des
  Programms, du baust sie nie selbst zusammen.
- **Leser sind menschliche Entwickler.** Deutsch, schlicht, ohne Marketing, ohne Füllwörter.
- **Schreiben nur in `docs/daidalos/`** des Zielrepos (Entwurf, `deutung.json`, Karte). Du
  committest nicht und änderst keinen Code.

## 0. Programm prüfen

```
daidalos --version
```

Fehlt es, halte an und nenne die Installation (Python ≥ 3.12 und uv nötig):

```
uv tool install git+https://github.com/Uthchen/Daidalos
```

Für die Entwicklung aus einem lokalen Klon: `uv tool install -e <pfad-zum-klon>`.

## 1. Messen und Überblick

Im Zielrepo:

```
daidalos scan
daidalos zusammenfassung
```

Die Zusammenfassung (Markdown, meist unter 300 Zeilen) enthält Zahlen, Module und Ordner, Pakete,
**wichtige Dateien** mit Grund der Aufnahme, **wichtige Funktionen** (seit A09), Befunde und den
Abschnitt **Offen**. Lies nicht
`daidalos.json` selbst; sie ist groß. `daidalos zusammenfassung --json` gibt dasselbe als JSON.

Liegen Messung und Deutung nicht im Standardordner, gib sie an allen Befehlen mit
`--daten DATEI` und `--deutung DATEI` an (auch bei `arbeitsblatt` und `deutung`); dann schreibt
`daidalos scan --ausgabe DATEI` die Messung und `daidalos render --ausgabe ORDNER` die Karte
dorthin. Eine `daidalos.toml` außerhalb des Zielrepos gibst du mit `--konfiguration DATEI` an.

## 2. Nur Offenes deuten

Gedeutet wird nur, was unter **Offen** steht; beim ersten Lauf ist das alles. Die Spalte „Deutung“
zeigt je Knoten `ok`, `fehlt`, `veraltet` oder `fremd` (Fremdcode wird nicht beschrieben).

- `fehlt`: neu beschreiben.
- `veraltet`: Der Inhalt hat sich geändert. Arbeitsblatt ansehen, Text prüfen und neu übernehmen,
  auch wenn er gleich bleibt (dann stimmt der Hash wieder).
- Befunde ohne Einschätzung: einschätzen (Schritt 6).
- Tote Verweise: über `entfernen` im Entwurf streichen (Schritt 8).

Steht unter Offen nichts, weiter mit Schritt 8 nur für `deutung pruefen` und `render`.

## 3. Arbeitsblätter und gezieltes Lesen

Für jedes offene Modul (und jeden offenen Ordner) ein Arbeitsblatt, bei Bedarf je Paket:

```
daidalos arbeitsblatt modul::core
daidalos arbeitsblatt paket::core/de.beispiel.zeichnen
daidalos arbeitsblatt datei:core/src/main/kotlin/de/beispiel/Strich.kt
```

`KNOTEN` ist eine Id oder ein eindeutiger Suchbegriff (`:core`, Paketname, Dateiname oder
Pfadende wie `zeichnen/Strich.kt`). Ist er mehrdeutig, nennt das Programm die Treffer; dann
die Id nehmen. Ein Arbeitsblatt zeigt je Datei: was sie deklariert, die erste KDoc-Zeile (ohne
KDoc den Kopfkommentar, etwa `// Prototyp, nicht übernehmen …`), was sie nutzt und wer sie nutzt (mit Gewicht
und Belegzeilen), ADR-Nummern in Kommentaren. Große Module zeigen nur die wichtigen Dateien voll;
die übrigen stehen als Kurzzeile mit erster Kommentarzeile da, alles Weitere im Arbeitsblatt je
Paket.

Für Beschreibungen reichen meist Kopfzeile, „deklariert“ und die Kurzzeilen; die Listen „nutzt“
und „genutzt von“ brauchst du vor allem für Befunde und Kantentexte. Ein Satz, der mehr behauptet
als Kommentar und Deklarationen hergeben, braucht einen Blick in die Datei.

Dann **gezielt** Code lesen:
- die Dateien, die das Arbeitsblatt als wichtig zeigt, wenn KDoc und Deklarationen nicht reichen;
- bei Zyklen und anderen Befunden genau die Belegzeilen der beteiligten Kanten;
- ADRs (`docs/adr/` o. Ä.) nur, wenn das Arbeitsblatt Nummern nennt und die Frage es braucht.

Lies nicht ganze Module von vorn bis hinten. Bei sehr vielen offenen Knoten kannst du die Pakete
auf parallele Hilfsagenten verteilen, wenn du welche hast; jeder liefert Texte für seine Ids.

## 4. Bereiche

3 bis 8 Bereiche: Gruppen von Paketen oder Dateien (auch über Modulgrenzen), die zusammen eine
Aufgabe erfüllen, z. B. „Zeichen-Pipeline“. Je Bereich `id` (`bereich:<kurzname>`), `name`, ein
Satz `beschreibung` und `knoten` (Ids von Modulen, Ordnern, Paketen oder Dateien).

## 5. Beschreibungen

Je offenem Modul, Ordner, Paket und wichtiger Datei **ein** Satz in einfacher Sprache. Er sagt,
wofür das Teil da ist, nicht wie es heißt. Nicht „StrichPuffer ist ein Puffer für Striche“,
sondern „Hält die Punkte des laufenden Strichs, bis die Zeichenschicht sie abholt.“

**Wichtige Funktionen** (Abschnitt in der Zusammenfassung: die 20 mit dem höchsten Fan-in und
jede markierte Funktion mit Grenzkante) bekommen ebenfalls einen Satz; Schlüssel ist die
Funktions-Id. Der Satz kommt aus dem **Körper der Funktion**: Lies ihn im Code an den Zeilen, die
die Zusammenfassung (Spalte „Zeilen“) und das Arbeitsblatt der Datei (`Z. von–bis`) nennen, und
sage, was die Funktion bewirkt, nicht wie sie heißt. Signatur und Name allein reichen nicht. Hash
und `veraltet` laufen wie bei Dateien über den Hash des Funktionsknotens.

## 6. Einschätzungen

Jeder Befund braucht eine Einschätzung, sonst bleibt er offen.

- **3 bis 10** Befunde bekommen eine `prioritaet` (1 = zuerst), einen `titel`, eine `begruendung`
  und einen konkreten `vorschlag`. Die Priorität richtet sich nach **Wirkung** (wie viele Teile
  betroffen sind, liegt es auf einem zeitkritischen oder zentralen Pfad, Produktiv- oder Testcode)
  und **Aufwand** (eine Trennstelle mit Gewicht 1 ist billig, keine einzelne Trennstelle ist
  teuer).
- Alle übrigen Befunde bekommen eine Einschätzung **ohne** `prioritaet`: `titel` und eine kurze
  `begruendung`, warum sie nachrangig sind; `vorschlag` ist dann freiwillig.
- **detekt-Befunde** (`quelle: detekt`) brauchen keine Einschätzung; sie haben schon eine Regel mit
  eigener Begründung. Die Zusammenfassung zählt sie unter „Messung“ je Regel.

**Grenzkanten der Markierungs-Kette** (`markierung-verlassen`): Eine markierte Funktion (`von`)
ruft eine unmarkierte (`nach`), dahinter hängt die `kette`. Lies sie zuerst mit

```
daidalos markierung --datei DATEI
daidalos aufrufe NACH-ID --tiefe 3
```

und lies `nach` im Code. Die Einschätzung nennt in der `begruendung`, **warum** `nach` wohl
unmarkiert ist: reine Hilfsfunktion ohne Zustand (Rechnung, Konstante, Formatierung), vergessen
(sie gehört sichtbar zum markierten Ablauf) oder absichtlich (Randfall, Protokollierung,
Plattformgrenze). Der `vorschlag` sagt, ob `nach` **markiert**, als **Ausnahme** annotiert oder
**umgebaut** werden sollte (etwa den unmarkierten Teil aus dem markierten Pfad herausziehen), und
belegt das mit dem Ergebnis von `daidalos aufrufe`. Kurze, nachrangige Einschätzungen sind erlaubt,
wenn viele Grenzkanten dasselbe Muster zeigen; dann genügt ein Satz je Grenzkante mit Verweis auf
die priorisierte, die das Muster erklärt. Steht `unsicher` im Beleg, sagst du, dass die Kante nur
unsicher ist. Über Code, den du nicht gelesen hast, behauptest du nichts.

## 7. Kanten-Texte

Nur wo es etwas zu sagen gibt: Trennstellen von Zyklen, überraschende Modulkanten, JNI-Brücken.
Ein Satz je Kante, Schlüssel ist die Kanten-Id aus Zusammenfassung oder Arbeitsblatt.

## 8. Entwurf übernehmen, prüfen, rendern

Schreibe den Entwurf nach `docs/daidalos/entwurf.json`. Format wie `deutung.json`, aber **ohne**
`hash`; jeder Teil ist optional. Vorlage: `vorlagen/entwurf-beispiel.json` neben dieser Datei.

```json
{
  "schema": 1,
  "beschreibungen": { "<knoten-id>": { "text": "Ein Satz." } },
  "bereiche": [
    { "id": "bereich:kurzname", "name": "Name", "beschreibung": "Ein Satz.", "knoten": ["<id>"] }
  ],
  "einschaetzungen": [
    { "befund": "<befund-id>", "prioritaet": 1, "titel": "…", "begruendung": "…",
      "vorschlag": "…" }
  ],
  "kanten": { "<kanten-id>": { "text": "Ein Satz." } },
  "entfernen": ["<id eines Eintrags, der wegfallen soll>"]
}
```

Dann:

```
daidalos deutung uebernehmen docs/daidalos/entwurf.json
daidalos deutung pruefen
daidalos render
```

- `uebernehmen` setzt die Hashes ein, prüft alle Ids und führt den Entwurf mit der bestehenden
  `deutung.json` zusammen (Einträge mit gleicher Id ersetzen alte, alles andere bleibt). Bei
  unbekannten Ids oder fehlenden Texten endet es mit Exit-Code 2, nennt jedes Problem und schreibt
  nichts: Entwurf korrigieren und erneut übernehmen.
- `pruefen` endet mit 0, wenn nichts mehr offen ist, sonst mit 1 und einer Liste. Was dort steht,
  in einem weiteren Entwurf nachtragen.
- Den Entwurf danach löschen; er ist nur ein Zwischenschritt.

## 9. Bericht

Kurz an den Nutzer: was neu gedeutet wurde (Zahl der Beschreibungen, Bereiche, Einschätzungen),
die drei wichtigsten Einschätzungen in je einem Satz, wo die Karte liegt
(`docs/daidalos/karte.html`, `docs/daidalos/KARTE.md`). Hinweis, dass nichts committet wurde.

## Fragen beantworten

„Warum hängt X an Y?“ beantwortest du mit

```
daidalos pfad X Y
```

(`--mit-tests` für Testkanten, `--ebene modul|paket|datei`, `--json`). Nenne die Schritte mit
Belegzeilen und verlinke die Sprungadresse der Karte: `docs/daidalos/karte.html#ebene=<ebene>&von=<id>&nach=<id>`
(Ids URL-kodiert). Für einen Knoten `karte.html#knoten=<id>`, für einen Befund `karte.html#befund=<id>`.

„Was ruft diese Funktion auf?“ bzw. „Wer ruft sie?“ beantwortest du mit

```
daidalos aufrufe ID --tiefe 3
```

(`--rueckwaerts` für die Aufrufer, `--unsicher` auch für unsichere Kanten; Funktions-Ids stehen im
Arbeitsblatt einer Datei). `daidalos pfad` nimmt auch Funktions-Ids und folgt dann `ruft`-Kanten.
Unsichere Kanten nennst du immer als unsicher. In der Karte zeigt `karte.html#funktion=<id>` eine
Funktion, `&weg=vor&tiefe=3` ihren Wirkungsweg.

„Wo verlässt markierter Code die Markierung?“ beantwortest du mit `daidalos markierung`
(`--datei D` für eine Datei, `--unsicher` auch für Grenzkanten, die nur unsicher sind).

## Führung erstellen

Bei Bitten wie „führe mich vom aufgelegten Stift bis zum Strich“, „zeig mir den Weg von … bis …“
oder „erklär mir, wie … abläuft“ schreibst du eine **Führung**: 3 bis 15 Schritte, die die Karte
der Reihe nach zeigt und erklärt. Eine Führung ist Deutung; es gelten alle festen Regeln oben.

1. **Frage klären und Namen wählen.** Eine Frage in einem Satz, dazu ein `name` aus
   Kleinbuchstaben, Ziffern und `-` (etwa `stift-bis-strich`). Ist die Frage zu weit („erklär mir
   alles“), frage nach oder wähle einen Ablauf und sage welchen.
2. **Den Weg finden, dann lesen.** Mit der Zusammenfassung und Arbeitsblättern die beteiligten
   Module und Dateien finden, mit

   ```
   daidalos pfad VON NACH
   daidalos aufrufe ID --tiefe 3
   daidalos markierung --datei DATEI
   ```

   den Weg zwischen den Funktionen. Dann die **Körper** der beteiligten Funktionen im Code lesen
   (Zeilen aus Arbeitsblatt oder `daidalos aufrufe`). Ein Schritt erklärt nur, was du gelesen hast.
3. **Ansichten zuordnen.** Jeder Schritt hat eine `ansicht`: eine Sprungadresse der Karte, wie ein
   Mensch sie selbst aufruft. Wechsle zwischen Überblick und Nähe:
   - Überblick: `#ebene=modul`, `#knoten=<modul-, paket- oder datei-id>`, `#befund=<id>`;
   - Nähe: `#funktion=<id>`, `#funktion=<id>&weg=vor&tiefe=2` (Wirkungsweg, `rueck` für Aufrufer),
     `#datei-funktionen=<pfad>`, `#grenze=<befund-id>` (Grenzkante der Markierung),
     `#ebene=funktion&von=<id>&nach=<id>` (Weg zwischen zwei Funktionen).

   Werte URL-kodiert wie in der Karte (`:` als `%3A`, `/` als `%2F`, `#` als `%23`). Dazu je Schritt
   `hervorheben`: 1 bis 8 Ids (Knoten, Befunde, Kanten), die die Karte nacheinander hervorhebt, in
   der Reihenfolge, in der du sie erklärst. Eine Kante zwischen Funktionen heißt
   `kante:ruft:<von-id>-><nach-id>:<rolle>`.
4. **Texte schreiben.** Je Schritt ein `titel` (wenige Wörter) und ein `text` aus ein bis drei
   kurzen Sätzen in einfacher Sprache. Fachwörter nur mit kurzer Erklärung. Keine Zahl, die nicht
   aus der Messung stammt. Jeder Schritt hat mindestens einen Beleg `{"datei": "<pfad>", "zeile":
   <n>}` auf die Stelle, die du gelesen hast. Die Texte werden auf Wunsch vorgelesen: Schreibe so,
   wie man spricht, ohne Klammern und Listen.
5. **Übernehmen und rendern.** Entwurf nach `docs/daidalos/fuehrung-entwurf.json` schreiben
   (Vorlage: `vorlagen/fuehrung-beispiel.json` neben dieser Datei; **ohne** `hashes`), dann

   ```
   daidalos fuehrung uebernehmen docs/daidalos/fuehrung-entwurf.json
   daidalos fuehrung pruefen
   daidalos render
   ```

   `uebernehmen` prüft Ids und Sprungadressen gegen die Messung, setzt die Hashes ein und schreibt
   `docs/daidalos/fuehrungen/<name>.json`. Bei Problemen endet es mit Exit-Code 2, nennt jedes und
   schreibt nichts: korrigieren und erneut übernehmen. Den Entwurf danach löschen.
   `daidalos fuehrung liste` zeigt alle Führungen mit Stand. Liegen Messung und Ausgabe nicht im
   Standardordner: `--daten DATEI` und `--ausgabe ORDNER` (der Ordner mit `fuehrungen/`).
6. **Link nennen.** Dem Benutzer `docs/daidalos/karte.html#fuehrung=<name>` nennen, dazu die Zahl
   der Schritte und wie viele Funktionskörper du gelesen hast. Hinweis: Weiter mit → oder
   Leertaste, „Vorlesen“ liest mit einer Stimme des eigenen Rechners vor.

**Veraltet und kaputt:** `daidalos fuehrung pruefen` meldet Schritte, deren Code sich geändert hat
(veraltet: Text prüfen, Führung neu übernehmen) oder deren Ids fehlen (kaputt: Schritt neu
schreiben). Die Zusammenfassung nennt solche Führungen unter **Offen**.

Feste Regel auch hier: Schreiben nur in `docs/daidalos/`, nichts committen, keinen Code ändern.
