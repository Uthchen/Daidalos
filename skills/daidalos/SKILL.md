---
name: daidalos
description: "Zeichnet und deutet die Daidalos-Karte einer Codebase: misst mit dem Programm daidalos, wie Module, Pakete und Dateien verflochten sind, benennt Bereiche, beschreibt Module, Pakete und wichtige Dateien in je einem Satz, gewichtet Befunde wie Zyklen mit Begründung und Vorschlag und rendert karte.html und KARTE.md. Verwenden bei „Karte erstellen“, „Codebase-Karte aktualisieren“, „daidalos“, „Architektur-Karte“, „was hängt woran“, „warum hängt X an Y“, „wo sind Zyklen“, auch wenn das Wort Daidalos nicht fällt."
argument-hint: "[zielrepo]"
---

# Daidalos deuten

Das Programm `daidalos` misst, du deutest. Du schreibst nur, was sich aus der Messung und aus
Code ergibt, den du gelesen hast. Das Programm setzt Hashes ein, prüft Ids und speichert; die
Texte schreibst du.

Ziel ist das Argument, sonst das aktuelle Verzeichnis (Zielrepo). Alle Ausgaben liegen in
`docs/daidalos/` des Zielrepos.

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
**wichtige Dateien** mit Grund der Aufnahme, Befunde und den Abschnitt **Offen**. Lies nicht
`daidalos.json` selbst; sie ist groß. `daidalos zusammenfassung --json` gibt dasselbe als JSON.

Liegen Messung und Deutung nicht im Standardordner, gib sie an allen Befehlen mit
`--daten DATEI` und `--deutung DATEI` an (auch bei `arbeitsblatt` und `deutung`).

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

`KNOTEN` ist eine Id oder ein eindeutiger Suchbegriff (`:core`, Paketname, Dateiname). Ein
Arbeitsblatt zeigt je Datei: was sie deklariert, die erste KDoc-Zeile, was sie nutzt und wer sie
nutzt (mit Gewicht und Belegzeilen), ADR-Nummern in Kommentaren. Große Module zeigen nur die
wichtigen Dateien voll; der Rest steht im Arbeitsblatt je Paket.

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

## 6. Einschätzungen

Jeder Befund braucht eine Einschätzung, sonst bleibt er offen.

- **3 bis 10** Befunde bekommen eine `prioritaet` (1 = zuerst), einen `titel`, eine `begruendung`
  und einen konkreten `vorschlag`. Die Priorität richtet sich nach **Wirkung** (wie viele Teile
  betroffen sind, liegt es auf einem zeitkritischen oder zentralen Pfad, Produktiv- oder Testcode)
  und **Aufwand** (eine Trennstelle mit Gewicht 1 ist billig, keine einzelne Trennstelle ist
  teuer).
- Alle übrigen Befunde bekommen eine Einschätzung **ohne** `prioritaet`: `titel` und eine kurze
  `begruendung`, warum sie nachrangig sind; `vorschlag` ist dann freiwillig.

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
