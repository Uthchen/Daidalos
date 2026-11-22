# Auftrag A04 – Erste Karte: `daidalos render`, `karte.html`, `KARTE.md` und `daidalos pfad`

**Etappe:** 3, erster Teil · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** A03 ist nach `main` gemergt. Branch `auftrag/a04-erste-karte` von `main`.

## Ziel

Aus `daidalos.json` (und, falls vorhanden, `deutung.json`) entsteht eine **eigenständige, offline lauffähige Karte** `docs/daidalos/karte.html` und ein Kurzbericht `docs/daidalos/KARTE.md`. Dazu kommt der Abfragebefehl `daidalos pfad`. Am Ende kann Manu die Karte von Sketchorus im Browser öffnen, zwischen Modulen, Paketen und Dateien wechseln, die 11 Zyklen anklicken und sehen, wer an wem hängt.

Die Bedienung aus dem Prototyp kommt in **zwei Schritten**. A04 baut das tragfähige Gerüst mit Daten, Ebenen, Layout, Seitenleiste und Befunden. A05 ergänzt danach Schlösser, abgestuften Fokus, Fluss-Animation, klickbare Kanten mit Infos und das Öffnen im Editor. Baue A04 so, dass A05 nur ergänzt und nichts umbaut.

**Vorlage:** `docs/prototyp/karte-prototyp.html` liegt schon im Repo. Das ist der fertige Klick-Prototyp mit erfundenen Daten. Übernimm daraus Aufbau, Farben und Abstände (Werkzeugleiste oben, Fläche links, Seitenleiste rechts), die Farb-Tokens für Hell und Dunkel, die Fokus-Stufen und die Bedienelemente. Den Code aus dem Prototyp **nicht** einfach kopieren, er ist ein Wegwerf-Entwurf mit fest eingebauten Daten. Die Seite ist die Richtschnur für das Aussehen, nicht für die Struktur.

## Rahmen

- **Messen und Deuten bleiben getrennt.** `render` rechnet nichts Neues aus. Was die Karte zeigt, steht in `daidalos.json` oder `deutung.json`. Ausnahmen sind reine Darstellungsrechnungen im Browser (Layout, kürzester Weg bei der Pfad-Suche, Nachbarschaften für den Fokus).
- **Offline:** Die Karte lädt nichts aus dem Netz. Keine Google Fonts, Systemschriften (`system-ui`, `Segoe UI`, `Cascadia Code`, `Consolas`, `monospace`).
- **Determinismus:** Gleiche Eingaben ergeben byte-gleiche `karte.html` und `KARTE.md`. Keine Zeitstempel, keine absoluten Pfade.
- **Öffentliches Repo:** Testdaten weiterhin erfunden. Bildschirmfotos von Sketchorus nur nach `lokal/`.

## Schritte

### 1. Vorarbeiten in der Messung (Python)

1. **Kopplung je Knoten:** In `daidalos.json` bekommt jeder Knoten der Arten `modul`, `paket`, `datei` und `ordner` ein Feld `metriken` mit `fan_in`, `fan_out` und `instabilitaet` = `fan_out / (fan_in + fan_out)` (auf 3 Nachkommastellen gerundet, `null` bei 0/0). Gezählt werden verschiedene Nachbarn über `nutzt`-Kanten der Rolle `produktiv` auf derselben Ebene. Zusätzlich `zeilen` und `dateien` für Modul, Paket und Ordner als Summe der eigenen, nicht fremden Dateien.
2. **Hash für Gruppen:** `modul`, `paket` und `ordner` bekommen einen `hash` = SHA-256 über die sortierten Paare `(pfad, hash)` ihrer Dateien. Damit kann die Deutung erkennen, ob ihre Beschreibung einer Gruppe veraltet ist.
3. **Zyklen „mit Tests“ nur, wenn neu:** Ein Zyklus-Befund mit Rolle `mit-tests` entfällt, wenn es einen produktiven Zyklus mit genau derselben Mitgliedermenge gibt. Verschmilzt ein Test-Zyklus produktive Zyklen, bleibt er erhalten und bekommt `enthaelt_produktiv: [<befund-ids>]`.
4. `docs/datenformat.md` nachtragen, Golden-Dateien aktualisieren.

### 2. Format von `deutung.json` festlegen (nur lesen)

Den Skill gibt es erst in A06, aber `render` muss seine Datei schon lesen können. Lege das Format in `docs/datenformat.md` fest. Vorschlag, schema 1:

```json
{
  "schema": 1,
  "beschreibungen": {
    "modul::core": { "text": "Fachlicher Kern ohne Android.", "hash": "sha256:…" }
  },
  "bereiche": [
    { "id": "bereich:zeichen-pipeline", "name": "Zeichen-Pipeline", "beschreibung": "…", "knoten": ["paket::core/…"] }
  ],
  "einschaetzungen": [
    { "befund": "befund:zyklus:datei:produktiv:…", "prioritaet": 1, "titel": "…", "begruendung": "…", "vorschlag": "…" }
  ],
  "kanten": {
    "kante:nutzt:datei:…->datei:…:produktiv": { "text": "Diese Verbindung schließt den Zyklus …" }
  }
}
```

- Eine Beschreibung gilt als **veraltet**, wenn ihr `hash` nicht mehr zum aktuellen Hash des Knotens passt. Die Karte zeigt sie dann trotzdem, aber mit dem Vermerk „veraltet“.
- Verweise auf Ids, die es nicht mehr gibt, werden übersprungen. `render` meldet sie als Warnung auf stderr.
- `bereiche` zeigt A04 nur in der Seitenleiste als Liste. Als Ebene auf der Karte kommen sie später.
- Für die Tests eine erfundene `deutung.json` zu `mini_modulgraph` von Hand schreiben, darunter eine veraltete Beschreibung und ein Verweis ins Leere.

### 3. `daidalos render`

```
daidalos render [ZIEL] [--daten DATEI] [--deutung DATEI] [--ausgabe ORDNER]
```

- Standard: `<ZIEL>/docs/daidalos/daidalos.json`, `<ZIEL>/docs/daidalos/deutung.json` (optional), Ausgabe nach `<ZIEL>/docs/daidalos/`.
- Exit-Code 2, wenn `daidalos.json` fehlt oder ein anderes `schema` hat.
- `karte.html` entsteht aus einer Vorlage im Paket (`src/daidalos/karte/`: `vorlage.html`, `karte.css`, `karte.js`) plus eingebetteten Bibliotheken plus den Daten. Die Dateien liegen getrennt im Repo, damit sie lesbar und testbar bleiben, und werden beim Rendern zu einer Datei zusammengesetzt.
- Die Daten werden als `<script type="application/json" id="daidalos-daten">` eingebettet, jeweils für Messung und Deutung. **`</` im JSON maskieren** (`<\/`), damit Inhalte das Script-Tag nicht beenden können. Dafür einen Test schreiben.
- Code wird **nicht** eingebettet (Architektur: keine Kopie des Quelltexts im Repo).

### 4. Bibliotheken

- **Cytoscape.js 3.28.1** (MIT).
- **Layout: ELK** über `elkjs` und `cytoscape-elk` (Schichtlayout, Richtung von oben nach unten, damit „app oben, core unten“ wie die Abhängigkeitsrichtung liest). Begründung: deterministisch und für gerichtete Abhängigkeiten gemacht. Floorplan nutzt es ebenfalls.
- Die Bibliotheken liegen als Dateien unter `src/daidalos/karte/vendor/` im Repo, mit Version, Quelle und Lizenz in `src/daidalos/karte/vendor/HERKUNFT.md` und den Lizenztexten daneben. Sie werden **einmal** von Hand bzw. mit einem kleinen Skript `werkzeuge/hole_vendor.py` heruntergeladen und committet, nicht zur Laufzeit. Das Skript prüft eine festgelegte SHA-256-Prüfsumme.
- Lizenzhinweise der Bibliotheken als Kommentar mit in `karte.html` übernehmen.

### 5. Die Karte

**Aufbau wie im Prototyp:** Kopfzeile (Projektname aus `ziel.name`, Commit kurz, „mit nicht committeten Änderungen“, falls `git_aenderungen`), Werkzeugleiste, Fläche, Seitenleiste. Dunkel ist Standard, Umschalter Dunkel/Hell/System, die Wahl wird im Browser gemerkt (`localStorage` in `try/catch`, ohne Speicher muss alles funktionieren).

**Ebenen:**
- **Module:** Module und Ordner-Knoten als Kästen, Kanten wahlweise `gradle-*` (Standard) oder verdichtete `nutzt`-Kanten. Kantenstärke nach Gewicht, Beschriftung mit Art und Gewicht.
- **Pakete:** Pakete in ihren Modulen bzw. Ordnern als Gruppen, `nutzt`-Kanten auf Paketebene.
- **Dateien:** Dateien in Paketen in Modulen, `nutzt`- und `jni`-Kanten. **Bei mehr als 150 Dateien** zeigt die Datei-Ebene nicht alles auf einmal, sondern nur die ausgeklappten Module. Standardmäßig ist das Modul ausgeklappt, das zuletzt gewählt war, sonst das erste mit den meisten Dateien. Kanten zu Dateien in eingeklappten Modulen enden am Modul-Kasten (verdichtet, gestrichelt). Ein Doppelklick auf ein Modul klappt es aus oder ein.
- Doppelklick auf ein Modul in der Modulebene springt in die Paketebene dieses Moduls, Doppelklick auf ein Paket in die Dateiebene.

**Filter in der Werkzeugleiste:**
- Rolle: „nur produktiv“ (Standard) oder „mit Tests“. Test-Dateien und Test-Kanten sind im Standard ausgeblendet.
- Kantenarten: Gradle, nutzt, JNI. Unsichere Kanten werden gestrichelt gezeichnet.
- Fremdcode: je Modul ein eingeklappter Kasten „Fremd · n Dateien“, keine Einzeldateien.

**Überlagerung Zyklen:** Kanten in einem Zyklus rot. Klick auf einen Zyklus-Befund hebt seine Knoten und Kanten hervor, markiert die **Einstiege** (eigene Randfarbe) und die **Trennstelle** (dicker, mit Beschriftung „günstigste Trennstelle“) und zoomt auf den Zyklus. Die Animation im Ring kommt in A05.

**Seitenleiste:**
- Ohne Auswahl: Kurzüberblick (Zahlen aus `daidalos.json`), die Befunde als Liste und, falls vorhanden, die Bereiche. Befunde mit Einschätzung aus der Deutung stehen nach Priorität vorn mit Titel, Begründung und Vorschlag. Die übrigen folgen nach Art: erst Zyklen (größte zuerst), dann JNI-Hinweise, dann unaufgelöste Importe.
- Mit Auswahl eines Knotens: Name, Pfad, Beschreibung aus der Deutung (mit „veraltet“-Vermerk), Zahlen (Zeilen, Dateien, Fan-in, Fan-out, Instabilität), „Nutzt“ und „Wird genutzt von“ als Listen mit Gewicht, Befunde an diesem Knoten. Die Einträge in den Listen sind in A04 noch **nicht** klickbar, das kommt in A05.
- Was aus der Messung und was aus der Deutung stammt, ist wie im Prototyp unterscheidbar (Farbe und Kennzeichnung „gemessen“ bzw. „gedeutet“).

**Sprungadressen:** `karte.html#knoten=<id>`, `#befund=<id>`, `#ebene=paket`. Die Adresse folgt der Auswahl, damit man sie kopieren kann. Ids in der Adresse URL-kodiert.

**Leistung:** Auf Manus Rechner soll jede Ebene von Sketchorus in höchstens 2 s stehen. Läuft ELK zu langsam, Layout je Ebene einmal berechnen und im Speicher halten.

**Barrierearmut:** `prefers-reduced-motion` beachten, Bedienelemente per Tastatur erreichbar, ausreichender Kontrast in beiden Modi.

### 6. `KARTE.md`

Für GitHub und Git-Diff, deutsch, kurz, deterministisch:
1. Kopf: Projekt, Commit, Hinweis auf `karte.html`.
2. Module als Tabelle: Modul, Dateien, Zeilen, Fan-in, Fan-out, Instabilität, Beschreibung (falls gedeutet).
3. Gradle-Abhängigkeiten als Liste.
4. Bereiche, falls gedeutet.
5. Befunde: erst die Einschätzungen nach Priorität, dann alle Zyklen je Ebene mit Mitgliedern, Einstiegen und Trennstelle, dann die übrigen Befunde gezählt.
6. Jede Erwähnung eines Knotens oder Befunds verlinkt auf die Sprungadresse in `karte.html`.

### 7. `daidalos pfad`

```
daidalos pfad VON NACH [--ebene modul|paket|datei] [--mit-tests] [--daten DATEI]
```

- `VON` und `NACH` sind Ids oder eindeutige Suchbegriffe (Endung eines Pfads, Modulname wie `:app`, Paketname). Bei mehrdeutigen Begriffen die Treffer auflisten und mit Exit-Code 2 enden.
- Ausgabe: der kürzeste Weg über `nutzt`-Kanten (bei `--ebene modul` zusätzlich Gradle), je Schritt mit den ersten Belegen (Symbol und Zeile). Gibt es keinen Weg, das klar sagen.
- `--json` gibt dasselbe maschinenlesbar aus, für den Skill und für Führungen.
- Ebene ergibt sich aus den Ids, wenn nicht angegeben.

### 8. Tests

- Python: `render` auf beiden Beispielprojekten, Golden-Dateien für `KARTE.md`. Für `karte.html` nur die **Prüfsumme der eingebetteten Daten** und die Struktur prüfen, nicht die ganze Datei als Golden (zu groß). Determinismus (zweimal rendern, byte-gleich). Keine `http://` oder `https://`-Ladebefehle in der Ausgabe. Maskierung von `</script>`. `deutung.json` mit veralteter Beschreibung und totem Verweis. `pfad` mit eindeutigem, mehrdeutigem und unerreichbarem Ziel.
- **Browser-Probe mit Playwright** (Python-Paket `playwright` als Entwicklungsabhängigkeit, Chromium): Karte des Beispiels öffnen, keine Konsolenfehler, alle drei Ebenen umschalten, Knotenzahlen je Ebene stimmen mit den Daten überein, Klick auf einen Zyklus-Befund hebt die richtigen Knoten hervor, Sprungadresse `#befund=…` funktioniert, „nur produktiv“ blendet Testdateien aus. Diese Tests bekommen die Markierung `browser` und laufen in der CI nur unter Ubuntu (dort `uv run playwright install --with-deps chromium`). Lokal laufen sie, wenn Chromium installiert ist, sonst werden sie übersprungen.

### 9. Probe an Sketchorus (nur lokal)

- `daidalos scan` und `daidalos render` auf der eingefrorenen Kopie, Ausgabe nach `lokal\sketchorus\`.
- Karte im Browser öffnen. Bildschirmfotos aller drei Ebenen in beiden Modi und eines hervorgehobenen Zyklus nach `lokal\A04-*.png`.
- Laufzeit je Ebene messen (Zeit bis das Layout steht).
- Größe von `karte.html`.
- `daidalos pfad :app :core` und ein Datei-Beispiel ausprobieren.
- Ergebnisse als Zahlen in den Bericht. Die Bildschirmfotos schaut sich die Leitung lokal an.

### 10. Abschluss

- Branch `auftrag/a04-erste-karte`, pushen, nicht mergen.
- Bericht `docs/auftraege/A04-bericht.md`.
- Antwort an mich mit höchstens 10 Zeilen.

## Abnahmekriterien

- [ ] CI grün, inklusive Browser-Probe unter Ubuntu.
- [ ] `karte.html` läuft ohne Netz, rendert byte-gleich, enthält keinen Quelltext und keine absoluten Pfade.
- [ ] Sketchorus: alle drei Ebenen stehen in höchstens 2 s, die 11 Datei-Zyklen sind anklickbar mit Einstiegen und Trennstelle, Tests sind standardmäßig ausgeblendet, Fremdcode ist eingeklappt.
- [ ] `KARTE.md` liest sich auf GitHub und verlinkt in die Karte.
- [ ] `daidalos pfad` findet Wege auf allen Ebenen.
- [ ] `docs/datenformat.md` beschreibt `metriken`, Gruppen-Hash, die Zyklus-Regel und `deutung.json`.

## Nicht in diesem Auftrag

Schlösser und Verschieben, abgestufter Fokus, Fluss-Animation, Infos beim Klick auf Kanten, klickbare Nutzt-Listen, Pfad-Suche in der Karte, Öffnen im Editor (alles A05). Skill und Zusammenfassung für den Skill (A06). Code-Vorschau und `daidalos serve` (Etappe 7).
