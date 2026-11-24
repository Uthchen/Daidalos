# Auftrag A10 – Führungen durch die Karte

**Etappe:** 5 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A09b (`0c1bfec`). Branch `auftrag/a10-fuehrungen` von `main`.

## Ziel

Manus Wunsch aus der Planung: Claude führt auf Zuruf durch die Karte, zum Beispiel „vom aufgelegten Stift bis zum Strich“. Es hebt die beteiligten Teile der Reihe nach hervor und erklärt jeden Schritt in einfacher Sprache, auf Wunsch vorgelesen.

Die Aufgaben sind aufgeteilt wie beim Deuten:

- **Skill:** Er schreibt die Führung. Das ist Deutung, also läuft sie über einen Entwurf und Hashes.
- **Programm:** Es prüft die Führung, bettet sie ein und spielt sie ab.

Live-Steuerung (Claude zeigt während eines Gesprächs) kommt erst in Etappe 7 mit `daidalos serve`.

## Schritte

### 1. Format `docs/daidalos/fuehrungen/<name>.json` (`schema: 1`)

```json
{
  "schema": 1,
  "name": "stift-bis-strich",
  "titel": "Vom aufgelegten Stift bis zum Strich",
  "frage": "Was passiert zwischen Berührung und sichtbarem Strich?",
  "schritte": [
    {
      "ansicht": "#funktion=funktion:…&weg=vor&tiefe=2",
      "hervorheben": ["funktion:…", "datei:…"],
      "titel": "Die Berührung kommt an",
      "text": "Ein bis drei kurze Sätze in einfacher Sprache.",
      "belege": [{"datei": "…", "zeile": 42}],
      "hashes": {"funktion:…": "…"}
    }
  ]
}
```

- `ansicht` ist eine Sprungadresse der Karte, wie es sie schon gibt (`#knoten=`, `#befund=`, `#ebene=`, `#funktion=…&weg=…`, `#datei-funktionen=`, `#grenze=`, `&von=&nach=`). So nutzt die Führung genau die Ansichten, die ein Mensch auch selbst aufrufen kann.
- `hervorheben` enthält 1 bis 8 Ids von Knoten, Kanten oder Befunden. Kanten der Funktionsebene werden als `kante:ruft:<von>-><nach>:<rolle>` angegeben (Ableitung aus A08).
- `hashes` setzt das Programm ein (Schritt 2), nicht der Skill. Sie gelten für alle Knoten aus `hervorheben` und aus `belege`. Der Hash eines Belegs ist der der Datei.
- 3 bis 15 Schritte. `name` in Kleinbuchstaben mit `-`.
- Ins Datenformat eintragen.

### 2. Befehle

- `daidalos fuehrung uebernehmen ENTWURF.json [ZIEL] [--daten] [--ausgabe]`:
  - prüft Ids und Sprungadressen (gegen die Messung);
  - setzt `hashes` ein;
  - schreibt `fuehrungen/<name>.json` deterministisch.
  - Bei unbekannten Ids: Exit-Code 2, Liste, nichts wird geschrieben. Wie bei `deutung uebernehmen`.
- `daidalos fuehrung pruefen [NAME] [ZIEL]` meldet je Führung, welche Schritte **veraltet** sind (ein Hash stimmt nicht mehr) und welche **kaputt** sind (Id fehlt). Exit 0 bei nichts davon, 1 sonst.
- `daidalos fuehrung liste [ZIEL]`: Name, Titel, Zahl der Schritte, Stand (ok/veraltet/kaputt).
- Die Zusammenfassung bekommt unter „Offen“ eine Zeile je veralteter oder kaputter Führung.

### 3. Einbettung

- `render` bettet alle Führungen in `karte.html` ein, als eigener kleiner JSON-Block mit Stand je Schritt.
- In `KARTE.md` kommt ein Abschnitt „Führungen“ mit Titel, Frage, Link `karte.html#fuehrung=<name>` und den Schritt-Titeln als Liste.

### 4. Spieler in der Karte

- **Einstieg:** Knopf „Führungen“ in der Kopfleiste (nur wenn es welche gibt) öffnet eine Liste mit Titel, Frage und Zahl der Schritte. Sprungadresse `#fuehrung=<name>[&schritt=n]`.
- **Während einer Führung:**
  - Die Seitenleiste zeigt Titel, Schritt n von m, Text, Belege mit Editor-Link sowie die Knöpfe „Zurück“, „Weiter“ und „Beenden“.
  - Die Karte wechselt zur `ansicht` des Schritts. Die Kamera gleitet, statt zu springen, etwa 600 ms. Die Ids aus `hervorheben` werden **der Reihe nach** hervorgehoben (je etwa 400 ms versetzt, mit Rand und Fokus wie bei einer Auswahl). Die zuletzt hervorgehobenen bleiben stehen.
- **Veraltete Schritte** tragen einen Hinweis „Code hat sich geändert, Text evtl. veraltet“. **Kaputte Schritte** werden übersprungen, mit Hinweis.
- **Tastatur:** `→`/`Leertaste` weiter, `←` zurück, `Esc` beenden.
- **Vorlesen:**
  - Ein Schalter „Vorlesen“ nutzt die Web Speech API (`speechSynthesis`), Sprache `de-DE`.
  - Es dürfen **nur Stimmen mit `localService === true`** verwendet werden, wegen Leitplanke 4: In Chrome und Edge senden manche Stimmen den Text ins Netz. Gibt es keine lokale deutsche Stimme, ist der Schalter aus und nennt den Grund.
  - Mit „Automatisch“ geht es nach dem Ende des Vorlesens plus 1,5 s zum nächsten Schritt. Mit „Pause“ wird angehalten.
  - Die Stimmwahl wird in `localStorage` gemerkt, ebenso die Geschwindigkeit (0,8–1,4).
- Während der Führung sind Bedienung und Filter der Karte frei. Ein Klick auf „Weiter“ stellt die Ansicht des Schritts wieder her.

### 5. Skill: Führung erstellen

`SKILL.md` bekommt einen zweiten Ablauf „Führung erstellen“. Er greift bei Bitten wie „führe mich …“, „zeig mir den Weg von … bis …“ oder „erklär mir, wie … abläuft“.

1. Frage klären und `name` wählen.
2. Mit `daidalos pfad`, `daidalos aufrufe`, Arbeitsblättern und der Zusammenfassung den Weg finden, dann die Körper der beteiligten Funktionen **lesen**.
3. Den Schritten Ansichten zuordnen, möglichst wechselnd zwischen Überblick (Modul- oder Dateiebene) und Nähe (Funktionsansicht, Wirkungsweg).
4. Die Texte schreiben:
   - einfache Sprache, keine Fachwörter ohne kurze Erklärung;
   - nur Gelesenes, keine erfundenen Zahlen;
   - je Schritt ein Beleg mit Datei und Zeile.
5. Den Entwurf schreiben, `fuehrung uebernehmen`, `render`.
6. Dem Benutzer den Link `karte.html#fuehrung=<name>` nennen.

Feste Regel: Nur in `docs/daidalos/` schreiben, nichts committen.

`test_skill` prüft weiter, dass `SKILL.md` nur Befehle nennt, die es gibt.

### 6. Kleinigkeiten aus A09b

- „Einpassen“ im Wegmodus nutzt dieselbe Regel wie das Öffnen (Leiste, Lesegrenze, Startspalte, Hinweiszeile).
- Ein gebündelter Strang im Wegmodus trägt die Befundfarbe der Markierung, wenn eine Grenzkante darin läuft.
- Eine Hilfe `js(s, ausdruck)` für die Browser-Proben, die immer `void` voranstellt. Alle bestehenden `evaluate`-Aufrufe ohne nötigen Rückgabewert werden umgestellt.

## Tests

- **Format und Befehle:** Übernehmen mit Hashes, unbekannte Id und falsche Sprungadresse ergeben Exit 2 ohne Schreiben. Dazu `pruefen` (ok, veraltet nach Änderung einer Datei im Beispiel, kaputt nach Entfernen einer Funktion), `liste` und Determinismus.
- **Beispiel:** eine erfundene Führung mit 4 Schritten in `mini_aufrufe` (Golden).
- **Browser-Probe:**
  - Liste und Start;
  - Weiter, Zurück, Tastatur;
  - Ansicht wechselt;
  - Hervorhebung der Reihe nach (Reihenfolge prüfen);
  - veralteter Hinweis, kaputter Schritt übersprungen;
  - Sprungadresse mit `&schritt=`.
- **Vorlesen** mit einer Attrappe von `speechSynthesis` (eine lokale und eine Netzstimme): Nur die lokale wird gewählt; ohne lokale ist der Schalter aus. „Automatisch“ geht nach dem Ende weiter.
- `test_skill` für den neuen Ablauf.

## Probe an Sketchorus

- Claude Code erstellt im Klon nach dem neuen Skill-Ablauf zwei Führungen:
  - **„Vom aufgelegten Stift bis zum Strich“:** Eingabe → Kern-Thread → Ring → Darstellung. Etwa 8 bis 12 Schritte.
  - **Eine Führung über die Markierungs-Kette:** Was markiert ist, wo der Code die Markierung verlässt, was man tun könnte. 5 bis 8 Schritte.
- **Zu berichten:** Zeit, Zahl der Schritte, wie viele Funktionskörper gelesen wurden, und ob `pruefen` 0 meldet.
- **Bildschirmfotos:** `lokal/A10-liste.png` und `lokal/A10-schritt.png` (ein Schritt auf der Funktionsebene).
- **Hinweis für Manu:** Die Führungen liegen in `lokal/ziele/sketchorus/daidalos/fuehrungen/`. Manu hört sie sich mit „Vorlesen“ an und gibt der Leitung Rückmeldung. Das ist der eigentliche Test dieser Etappe.

## Abschluss

- Branch pushen, nicht mergen.
- Bericht `docs/auftraege/A10-bericht.md`.
- Antwort an mich mit höchstens 8 Zeilen.
- Keine Sketchorus-Inhalte im Repo.
