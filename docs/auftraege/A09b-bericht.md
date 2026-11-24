# Bericht A09b – Nacharbeit Funktionsebene: Wegmodus und ELK-Hänger

Stand 2026-11-24. Branch `auftrag/a09b-nacharbeit` von `main` (`4f14647`, mit A09), nicht nach
`main` gemergt.

## Ursache des Hängers (offene Frage 1 aus A09)

**Kein ELK-Hänger, sondern ein Fehler im Test.** `test_fokus_zoom_haelt_dateinamen_lesbar` rief
`s.evaluate("daidalos.cy.resize()")` auf. `cy.resize()` gibt die Cytoscape-Instanz zurück, und
Playwright versucht, diesen Rückgabewert zu serialisieren: den ganzen Objektgraphen mit Renderer,
Canvas und DOM-Bezügen. Je nach Zustand der Seite dauert das ewig oder läuft in den Speicher.

Belege:

- Nachgestellt mit einem eigenen Skript (gleiche Schritte wie der Test): Der Seiten-Thread hing im
  `cy.resize()`-Aufruf, Chromium meldete nach 13 s `V8 javascript OOM (CALL_AND_RETRY_LAST)` bei
  2,1 GB Heap, danach „Target crashed“.
- Mit `Debugger.pause` (CDP) während des Hängers angehalten: Der oberste Rahmen lag im
  eingeschleusten Serialisierer von Playwright (Funktion ohne URL), nicht in ELK oder Cytoscape.
- Dieselben Schritte mit `cy.resize(); 1` liefen 120-mal ohne Hänger.
- Auf `main` (Code von A09, also noch mit ELK im Seiten-Thread) mit nur dieser Testkorrektur:
  10 von 10 Läufen grün (je etwa 1,7 s); vorher hingen 3 von 5 Einzelläufen.

Korrektur: `void daidalos.cy.resize()` an beiden Stellen; dazu die gleiche Falle in
`test_browser_funktionen.py` (`cy.fit(…)` als Rückgabe eines Pfeils). Die beiden anderen
Kandidaten aus dem Auftrag (zwei Layouts gleichzeitig nach einem Sprung aus der Seitenleiste; ein
Graph, den ELK orthogonal nicht schließt) waren nicht die Ursache: Der Sprung aus der Seitenleiste
im Test zeichnet gar nicht neu (gleiche Ebene), und der Hänger trat schon beim Verkleinern auf.

## Was gemacht wurde

### 1. ELK im Web Worker mit Zeitgrenze (Schritt 4)

- Statt `elk.bundled.js` (API und GWT-Code in einem Stück, rechnet im Seiten-Thread) sind jetzt
  `elk-api.js` und `elk-worker.min.js` aus elkjs 0.9.3 eingebettet, beide mit SHA-256 in
  `werkzeuge/hole_vendor.py` und `vendor/HERKUNFT.md`. Die Karte wird dadurch nicht größer
  (Worker-Teil 1 594 464 Bytes + API 8 591 statt 1 606 238 Bytes).
- Der Worker-Quelltext steht als Text in `<script type="text/plain" id="elk-worker">`; die neue
  Hülle `src/daidalos/karte/elk_lauf.js` startet daraus einen Worker über eine Blob-URL und setzt
  sich als `window.ELK` ein, bevor `cytoscape-elk.js` lädt. cytoscape-elk bleibt unverändert.
- Ein Worker für alle Layouts (der GWT-Code wird nur einmal geladen). cytoscape-elk hängt
  Cytoscape-Elemente an die ELK-Knoten (`_cyEle`); gesendet wird deshalb eine Kopie ohne Schlüssel
  mit `_`, das Ergebnis wird nach Id in den Ausgangsgraphen zurückgeschrieben (cytoscape-elk liest
  die Lage aus seinem eigenen Objekt).
- **Abbruch:** `zeichne()` bricht ein laufendes Layout ab, bevor es ein neues beginnt (Worker
  beenden, das alte Promise endet mit `false`). Das abgebrochene Layout setzt nichts mehr.
- **Zeitgrenze 5 s:** Danach wird der Worker beendet; es greift Cytoscape `breadthfirst` bzw.
  `grid` bei Rahmen (Kinder eines Rahmens nebeneinander) mit der Zeile „vereinfachte Anordnung: …“
  in der Infoleiste und `data-anordnung="ersatz"` am `<html>`. Ersatzanordnungen werden nicht
  zwischengespeichert, beim nächsten Mal versucht es ELK wieder. Gleiches gilt, wenn kein Worker
  startet oder ELK einen Fehler meldet (eigener Text).
- Testhaken `daidalosElk.testHaengen(true)`: der nächste Worker antwortet nie.
- Die Browser-Probe lässt `blob:`-Adressen zu (lokal, kein Netz).

### 2. Wegmodus zeigt den ganzen Weg (Schritt 1)

- Beim Öffnen wird auf den ganzen Weg eingepasst, mit 30 px Rand, unter der Infoleiste und über
  der Legende. Der Fokus-Mindestzoom aus A06 gilt hier nicht.
- Wäre die Schrift dabei kleiner als 9 px (Lesegrenze `LESBAR` wie beim Start der Dateiebene),
  steht die Startspalte bei diesem Zoom bündig am Rand (vorwärts links, rückwärts rechts, weil die
  Startspalte dort rechts liegt), senkrecht um die Start-Funktion; die Zeile „weiter rechts: N
  Funktionen“ (bei Bedarf auch „weiter links“, „darüber oder darunter“) folgt jedem Verschieben
  und Zoomen und verschwindet, wenn alles im Bild ist.
- **Wahl an Sketchorus:** Verglichen wurden „alles einpassen“ (`lokal/A09b-weg-eingepasst.png`:
  Funktionsnamen etwa 6 px, nicht lesbar, man sieht nur die Form) und „Startspalte links, lesbar“
  (`lokal/A09b-weg-nachher.png`). Die zweite liest besser: Start und erste Spalte sind ohne Zoom
  lesbar, und man fährt dem Weg nach rechts nach. Die Hinweiszeile sagt, wie viel fehlt.
- Start ist gewählt (Rand, Fokusstufen, „wer … nutzt“), aber **ohne Fluss** und ohne Fokus-Zoom.
  Der Fluss läuft, sobald man eine Kante oder eine andere Funktion wählt.
- Zählzeile, „wer … nutzt“, „weiter …“ und „vereinfachte Anordnung“ stehen in einer Leiste
  (`#infoleiste`) untereinander und überdecken sich nie.

### 3. Weniger Kabelstrang am Start (Schritt 2)

- Verglichen an Sketchorus (Einstieg wie `A09-weg.png`): ohne Änderung, ELK `mergeEdges`,
  verteilte Ports (`portConstraints: FIXED_SIDE`, engere `spacing.edgeEdge`) und `mergeEdges` mit
  engerem Abstand.
- **Genommen: `elk.layered.mergeEdges` nur im Wegmodus.** Die 18 Kanten des Starts laufen als ein
  Strang und fächern sich erst vor der Zielspalte auf. Verteilte Ports änderten fast nichts
  (`lokal/A09b-weg-ports.png`: weiter 18 Kanten nebeneinander). Nebenwirkung: Die erste Spalte
  steht als eine Säule untereinander, der Weg wird höher und schmaler; bei Sketchorus passt er
  damit in der Breite, über und unter dem Bild liegen 12 Funktionen.
- Vorher/Nachher: `lokal/A09b-weg-vorher.png` (Code von `main`) und `lokal/A09b-weg-nachher.png`,
  gleicher Einstieg wie `A09-weg.png` (Wirkungsweg vorwärts, Tiefe 3, ab der Darstellungsfunktion
  mit 18 Aufrufen).

### 4. Lesezugriffe ab markierter Funktion (Schritt 3)

- Startet ein Wirkungsweg an einer markierten Funktion, ist „Lesezugriffe“ dort an. Der Wegmodus
  hat dafür einen eigenen Stand (`wegLesen`), wie schon „unsicher“. Ab einer unmarkierten Funktion
  gilt der gemerkte Stand, und ein Umschalten dort wird gemerkt; ab einer markierten bleibt der
  gemerkte Stand unberührt. Gleicher Start mit anderer Tiefe behält die Wahl.
- An Sketchorus: ab dem Einstieg aus `A09-weg.png` jetzt 33 statt 22 Funktionen (27 markiert,
  6 unmarkiert), wie in A09 für „mit Lesezugriffen“ gezählt.

### 5. Wichtige Funktionen in `KARTE.md` (Schritt 5)

- Neuer Abschnitt „Wichtige Funktionen“ zwischen „Bereiche“ und „Befunde“: Tabelle mit Name (Link
  `karte.html#funktion=…`), `Datei:Zeile` und dem Satz aus der Deutung, `*(veraltet)*` wie üblich,
  sortiert nach Datei und Zeile. An Sketchorus 35 Zeilen.

## Tests

- Neu, Browser: Wegmodus mit allen Kästen im Bild, ohne Fluss beim Öffnen, Leiste ohne Überdeckung,
  Fluss nach Wahl einer anderen Funktion; zu schmale Fläche → Zoom = Lesegrenze, Startspalte bei
  20–40 px, „weiter rechts: N“ stimmt mit der Zählung überein; Lesezugriffe ab markierter Start-
  Funktion an, gemerkter Stand unberührt; ELK im Worker; Abbruch eines laufenden Layouts durch ein
  neues; Zeitgrenze mit hängendem Worker (Testhaken, Grenze im Test 300 ms) → Ersatzlayout mit
  Hinweis, danach wieder ELK.
- Neu, ohne Browser: Reihenfolge der eingebetteten Skripte (Worker-Text, API, Hülle,
  cytoscape-elk), Abschnitt „Wichtige Funktionen“ (Link, Ort, Satz, veraltet, Escaping), kein
  Abschnitt ohne Funktionsbeschreibungen.
- Gesamt: `uv run pytest` 349 bestanden, 1 übersprungen; ruff check und format sauber.

**Abnahme unter Windows, zehnmal hintereinander:**

| Lauf | Ergebnis |
| --- | --- |
| `test_fokus_zoom_haelt_dateinamen_lesbar` einzeln, 10× | 10 von 10 grün (1,7–10 s) |
| alte Browser-Probe `tests/test_browser.py` ganz, 10× | 10 von 10 grün, je 31 Tests in 23,0–23,3 s |
| Gegenprobe: `main` mit nur der Testkorrektur, Einzeltest 10× | 10 von 10 grün |

## Messung an Sketchorus

Gleicher Klon `b610477`, Median aus 5. „Vorher“ ist die Karte aus A09 (ELK im Seiten-Thread).

| Messgröße | vorher | nachher |
| --- | ---: | ---: |
| `karte.html` | 4 992 128 Bytes | 5 001 871 Bytes (+9,5 KiB) |
| Start bis „bereit“ | 178 ms | 175 ms |
| Funktionsansicht der Darstellungsdatei | 319 ms | 297 ms |
| Wirkungsweg vorwärts Tiefe 3 (Einstieg wie `A09-weg.png`) | 45 ms (22 Funktionen) | 63 ms (33 Funktionen, mit Lesezugriffen) |

Der Worker kostet keine messbare Startzeit; der Wirkungsweg ist länger, weil er jetzt mehr Kästen zeigt.

## Abweichungen vom Auftrag

- **Ursache war der Test.** Worker, Zeitgrenze und Abbruch sind trotzdem gebaut, wie verlangt; sie
  schützen künftig vor echten ELK-Hängern.
- **`elk.bundled.js` ersetzt statt ergänzt.** Der Auftrag nennt nur das neue Vendor-Stück
  `elk-worker.min.js`. Mit dem Bündel daneben hätte die Karte den GWT-Code zweimal enthalten
  (+1,6 MB); `elk-api.js` (8,6 KB) ist der API-Teil desselben Pakets.
- **Hinweiszeile auch links, oben, unten:** Der Auftrag nennt „weiter rechts“; rückwärts liegt
  der Rest links, und hohe Wege ragen nach oben und unten hinaus. Gezählt wird jede Richtung.
- **Einpassen im Wegmodus:** Gilt auch für den Weg zwischen zwei Funktionen („Warum hängt“); dort
  läuft der Fluss weiter auf allen Kanten, weil er den Weg selbst zeigt.
- **Ersatzlayout bei Rahmen:** `grid` setzt nur die Blätter; Rahmen umschließen ihre Kinder, die
  dank Sortierung nebeneinander liegen. Rahmen können sich dabei berühren („vereinfacht“).

## Offene Fragen

1. Der Knopf „Einpassen“ im Wegmodus passt weiter alles ohne Rücksicht auf Leiste und Lesegrenze
   ein. Soll er dort dieselbe Regel nutzen wie das Öffnen?
2. Mit `mergeEdges` sind Grenzkanten im Strang nicht mehr einzeln zu sehen, erst nach dem
   Auffächern. Reicht das, oder soll der Strang die Befundfarbe tragen, wenn eine Grenzkante darin
   läuft?

## Nächste sinnvolle Schritte

- Etappe 5 (Führungen) kann `#funktion=…&weg=…` als Schritt nutzen; die Ansicht ist jetzt
  vorhersehbar (ganzer Weg bzw. Startspalte).
- Weitere Tests auf `evaluate`-Rückgaben prüfen: Ein Ausdruck, der ein Cytoscape-Objekt
  zurückgibt, kann jede Probe einfrieren. Eine kleine Hilfe `js(s, ausdruck)` mit `void` wäre
  sicherer.
