# Auftrag A09b – Nacharbeit Funktionsebene: Wegmodus und ELK-Hänger

**Etappe:** 4 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A09 (`4f14647`). Branch `auftrag/a09b-nacharbeit` von `main`. Kleiner Auftrag.

## Ziel

Die Funktionsansicht einer Datei ist gut (siehe `lokal/A09-datei.png`). Im Wegmodus fallen auf `lokal/A09-weg.png` aber drei Dinge auf. Dazu kommen die beiden offenen Fragen aus dem Bericht.

## Schritte

1. **Wegmodus zeigt den ganzen Weg.**
   - **Befund:** Auf `A09-weg.png` ist nur die Startfunktion zu sehen. Die erreichten Funktionen liegen außerhalb des Bildes (Kanten laufen nach oben hinaus, rechts sind Kästen abgeschnitten). Dazu läuft der Fluss auf allen Kanten.
   - **Neu:** Beim Öffnen des Wegmodus wird auf **den ganzen Weg** eingepasst, mit Rand. Der lesbare Mindestzoom aus A06 gilt hier **nicht**, denn er gilt nur für den Fokus auf einen Knoten. Wird der Zoom dadurch kleiner als die Lesegrenze, dann:
     - die Startspalte links bündig setzen,
     - so weit zoomen, dass die Schrift lesbar bleibt,
     - eine Zeile „weiter rechts: N Funktionen“ zeigen.

     Probiere aus, was an Sketchorus besser liest, und begründe die Wahl.
   - Die Startfunktion ist gewählt, aber ohne Fluss-Animation auf allen Kanten. Der Fluss läuft erst, wenn man eine Kante oder eine andere Funktion wählt.
   - Die Bannerzeile „wer … nutzt“ darf die Zählzeile des Wegmodus nicht verdecken. Beide gehören in eine Leiste.
2. **Weniger Kabelstrang am Start.** Vom Startknoten laufen 18 Kanten aus einem Punkt nebeneinander hoch. Im Wegmodus gilt deshalb:
   - Kanten gleicher Quelle und gleicher Zielspalte zu einem Strang bündeln, der sich erst vor der Zielspalte auffächert (ELK `mergeEdges` nur im Wegmodus probieren).
   - Oder die Ports auf der Quellseite verteilen (`portConstraints`, `spacing.edgeEdge`).

   Die Lösung, die an Sketchorus besser liest, wird genommen. Vorher-Nachher-Bild.
3. **Lesezugriffe im Wegmodus ab markierter Funktion** (offene Frage 2): Startet ein Wirkungsweg an einer **markierten** Funktion, ist der Schalter „Lesezugriffe“ dort standardmäßig an. Der Grund: Die Markierungs-Kette zählt sie mit. Sonst gilt der gemerkte Stand.
4. **ELK-Hänger** (offene Frage 1). Das Layout darf die Seite nie einfrieren.
   - ELK läuft in einem **Web Worker**. elkjs bringt dafür `elk-worker.min.js` mit. Der Worker wird aus einem `Blob` des eingebetteten Quelltexts erzeugt, weil `file://` keine Worker-Datei laden darf. Das neue Vendor-Stück kommt mit Prüfsumme in `HERKUNFT.md` und `hole_vendor.py`.
   - **Zeitgrenze:** 5 s je Layout. Danach wird der Worker beendet, und es greift ein Ersatzlayout (Cytoscape `breadthfirst` bzw. `grid` für Rahmen) mit dem Hinweis „vereinfachte Anordnung“.
   - Die Ursache des Hängers suchen und im Bericht nennen. Kandidaten:
     - Sprung aus der Seitenleiste während eines laufenden Layouts (zwei Layouts gleichzeitig),
     - ein Graph, den ELK orthogonal nicht schließt.

     Laufende Layouts werden abgebrochen, wenn ein neues beginnt.
   - **Abnahme:** Der bisher hängende Test `test_fokus_zoom_haelt_dateinamen_lesbar` und die ganze alte Browser-Probe laufen unter Windows **zehnmal hintereinander** durch. Das Ergebnis kommt in den Bericht.
5. **Beschreibungen wichtiger Funktionen in `KARTE.md`** (nächster Schritt aus dem Bericht): ein kurzer Abschnitt „Wichtige Funktionen“ mit Name, Datei:Zeile und Satz.

## Tests

Browser-Probe:

- Wegmodus: Nach dem Öffnen liegen alle Kästen des Wegs im Bild, oder es gilt die Regel aus Schritt 1 mit Hinweiszeile. Die Animation ist beim Öffnen aus.
- Lesezugriffe ab markierter Start-Funktion an.
- Abbruch eines laufenden Layouts durch ein neues.
- Zeitgrenze mit einem künstlich hängenden Worker (Testhaken) führt zum Ersatzlayout mit Hinweis.

## Abschluss

- Branch pushen, nicht mergen.
- Bericht `docs/auftraege/A09b-bericht.md`.
- Antwort an mich mit höchstens 8 Zeilen.
- Bildschirmfotos `lokal/A09b-weg-vorher.png` und `lokal/A09b-weg-nachher.png` (gleicher Einstieg wie `A09-weg.png`).
