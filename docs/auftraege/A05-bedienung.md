# Auftrag A05 – Bedienung der Karte wie im Prototyp

**Etappe:** 3, zweiter Teil · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** A04 ist nach `main` gemergt. Branch `auftrag/a05-bedienung` von `main`.

## Ziel

Die Karte aus A04 bekommt die Bedienung, die Manu im Prototyp (`docs/prototyp/karte-prototyp.html`) festgelegt hat, und die Korrekturen aus der Durchsicht der A04-Bildschirmfotos. Danach kann man sich durch Sketchorus hangeln: Datei wählen, sehen, was direkt und was eine Stufe weiter dranhängt, Verbindungen anklicken und ihre Belege lesen, zur nächsten Datei springen und die Stelle in VS Code öffnen.

Baue auf dem Gerüst aus A04 auf (`karte.js`, Abschnitte 1 bis 9, `window.daidalos`). Der Prototyp ist die Richtschnur für Verhalten und Aussehen. Probiere ihn im Browser aus, bevor du anfängst.

## Rahmen

Wie bisher: offline, deterministische Ausgabe, keine absoluten Pfade in `karte.html`, keine neuen Messungen im Browser (nur Darstellung). Was die Messung liefern muss, kommt in Python dazu (Teil C).

## Teil A – Korrekturen aus der Durchsicht von A04

1. **Weitere Ordner zusammenfassen.** Auf der Modulebene stehen bei Sketchorus sieben Ordner-Kästen ohne Verbindung in einer Reihe (`docs/`, `.claude/`, `gradle/`, `config/`, Wurzel …). Ordner ohne Kartendateien und ohne Kanten werden zu **einem** Kasten „Weitere Ordner · n Ordner · m Dateien“ zusammengefasst. Ein Klick listet sie in der Seitenleiste mit Dateien und Zeilen. Ordner mit Code oder Kanten (bei Sketchorus `werkzeuge/`) bleiben einzeln.
2. **Plugin-Kanten.** `gradle-plugin`-Kanten (bei Sketchorus sechs Pfeile auf `detekt-regeln`, die nur „gilt für alle“ bedeuten) sind standardmäßig ausgeblendet. Am Zielmodul steht stattdessen ein Vermerk „Plugin für n Module“. Ein eigener Schalter „Plugins“ blendet die Kanten ein.
3. **Kanten innerhalb eines Pakets blasser.** Auf der Dateiebene werden Kanten zwischen Dateien desselben Pakets mit geringerer Deckkraft gezeichnet. Sind sie Teil eines Fokus, eines Zyklus oder eines Pfads, werden sie normal gezeichnet.
4. **Lesbarer Start der Dateiebene.** Wenn „Einpassen“ alles so klein macht, dass Dateinamen unter etwa 9 px fallen, zeigt die Dateiebene beim Öffnen stattdessen das größte Paket des ausgeklappten Moduls in lesbarer Größe. „Einpassen“ zeigt weiter alles. Zu klein gewordene Beschriftungen blendet Cytoscape aus (`min-zoomed-font-size`), Paket- und Modulnamen bleiben länger sichtbar als Dateinamen.
5. **Kantenführung.** Kanten laufen derzeit als Bézier-Linien teils quer über Kästen. Probiere zwei Wege aus und nimm den, der bei Sketchorus besser liest: (a) Cytoscape-Kurvenstil `taxi` passend zur Schichtrichtung, (b) ELKs eigene Kantenführung (orthogonal oder Spline) als `segments`-Kanten übernommen. Vergleichs-Bildschirmfotos nach `lokal/`, Begründung in den Bericht. Gemerkte Positionen (Teil B1) dürfen die Kantenführung nicht kaputt machen. Notfalls fallen verschobene Knoten auf Bézier zurück.

## Teil B – Bedienung aus dem Prototyp

### B1. Sperren und gemerkte Positionen
- Alle Elemente sind **standardmäßig gesperrt**.
- Jedes Element (Datei, Paket, Modul, Ordner, Fremd-Kasten) hat oben rechts ein **Schloss**. Ein Klick darauf entsperrt nur dieses Element, das Schloss wird offen und farbig. Ein zweiter Klick sperrt wieder. Der Klick auf das Schloss wählt das Element nicht aus.
- Oben rechts auf der Fläche sitzt das **globale Schloss**. Es zeigt „alle gesperrt“, „alle entsperrt“ oder „n entsperrt“. Ein Klick entsperrt alles, und wenn etwas offen ist, sperrt er wieder alles.
- **Gruppen:** Ein entsperrtes Modul, Paket oder Ordner lässt sich samt Inhalt verschieben. Gesperrte Elemente darin bleiben an ihrem Platz. Wenn Cytoscape das bei Verbundknoten nicht sauber hergibt, die naheliegende Lösung bauen und im Bericht erklären.
- **Positionen merken:** Verschobene Positionen merkt sich der Browser je Projekt, Ebene und Knoten-Id (`localStorage` in `try/catch`). Beim nächsten Öffnen und nach einem neuen `render` stehen die Knoten wieder dort. Knoten, die es nicht mehr gibt, werden ignoriert. Neue Knoten legt das Layout. Ein Knopf „Anordnung zurücksetzen“ löscht die gemerkten Positionen der aktuellen Ebene.
- Sperrzustand und Positionen bleiben beim Wechsel der Ebenen erhalten.

### B2. Abgestufter Fokus
- Wird ein Knoten gewählt, ist er voll sichtbar. **Direkte Nachbarn** (über sichtbare Kanten, beide Richtungen) haben 75 % Deckkraft, **zwei Verbindungen entfernt** 40 %, **alles andere** 14 %. Im dunklen Modus gelten 82, 50 und 22 % (Tokens `--o-n1`, `--o-n2`, `--o-blass` wie im Prototyp).
- Kanten bekommen die Stufe ihres blasseren Endes. Kanten vom gewählten Knoten zu direkten Nachbarn sind voll sichtbar.
- Die Ansicht zoomt so, dass der gewählte Knoten und alle direkten Nachbarn ins Bild passen.
- Klick ins Leere oder `Esc` hebt den Fokus auf.

### B3. Fluss-Animation
Hervorgehobene Verbindungen bewegen sich in Pfeilrichtung (gestrichelte Linie mit wanderndem Versatz), aber **nur auf Wunsch**: bei gewähltem Knoten, Befund oder Pfad. Die ruhende Karte bleibt still.
- **Stufe 1:** die direkten Kanten des gewählten Knotens. Ausgehende Kanten („worauf baut er“) in Akzentfarbe, eingehende Kanten („wer nutzt ihn“) in Textfarbe.
- **Stufe 2:** nur Kanten, die eine Kette **durch** den gewählten Knoten fortsetzen. Aufwärts sind das die Nutzer der Nutzer, abwärts das, worauf die Abhängigkeiten bauen. Stufe 2 läuft langsamer und mit feineren Strichen.
- **Nicht animiert** werden Kanten zwischen zwei Nachbarn, die nicht über den gewählten Knoten laufen.
- Oben auf der Fläche steht eine Zählzeile wie im Prototyp, etwa „wer Strich.kt nutzt: 3 direkt, 3 eine Stufe weiter · worauf Strich.kt baut: 2 direkt, 4 eine Stufe weiter“.
- **Zyklus:** Beim Klick auf einen Zyklus-Befund läuft der Fluss endlos im Ring über die Zyklus-Kanten. Einstiege und Trennstelle bleiben wie in A04 markiert.
- **Pfad:** Der gefundene Weg (B6) läuft vom Start zum Ziel.
- `prefers-reduced-motion`: stehende Striche statt Bewegung.
- Animiert werden nur die hervorgehobenen Kanten, über `requestAnimationFrame` und ein einziges Taktsignal. Die Karte muss dabei flüssig bleiben.

### B4. Klickbare Verbindungen
Ein Klick auf eine Kante zeigt in der Seitenleiste ihre eigenen Informationen:
- Art, Von und Nach (klickbar), Gewicht, Rolle, sicher oder unsicher.
- **Grenze:** innerhalb eines Pakets, zwischen Paketen desselben Moduls oder über eine Modulgrenze. Dazu, ob sie die **einzige Verbindung** zwischen den beiden Paketen bzw. Modulen ist (aus den vorhandenen verdichteten Kanten ablesbar).
- **Belege** (Symbol, Zeile, Herkunft) bei Datei-Kanten, jeweils mit Editor-Symbol (B7) für genau diese Zeile. Bei Gradle-Kanten Build-Datei, Zeile, Konfiguration, Quellsatz, „bedingt“.
- **Verdichtete Kanten** (Paket, Modul, eingeklappt): die tragenden Datei-Kanten als klickbare Liste, nach Gewicht sortiert. Bei Gradle-Kanten zusätzlich die `nutzt`-Kanten, die diese Abhängigkeit tatsächlich verwenden.
- **Zyklus:** Ist die Kante Teil eines Zyklus, ein Link zum Befund. Außerdem, ob sie die günstigste Trennstelle ist und ob ihr Wegfall allein den Zyklus löst (aus Teil C1).
- Deutungstext zur Kante aus `deutung.json` (`kanten`), gekennzeichnet als „gedeutet“.
- Die gewählte Kante wird hervorgehoben, und der Fokus gilt für ihre beiden Enden.

### B5. Klickbare Listen
„Nutzt“, „Wird genutzt von“, Mitglieder und Einstiege eines Zyklus, Knoten eines Bereichs und alle Knoten in Belegen sind klickbar. Ein Klick springt zum Knoten: Wenn nötig, wechselt die Ebene, das Modul wird ausgeklappt, und der Fokus wird gesetzt. Die Sprungadresse folgt. Mit Zurück im Browser kommt man zur vorherigen Auswahl.

### B6. Pfad-Suche in der Karte
In der Werkzeugleiste wie im Prototyp: „Warum hängt [Von] an [Nach]“ mit zwei Suchfeldern mit Vorschlagsliste (Knoten der aktuellen Ebene, Suche nach Namensteil) und dem Knopf „Kette zeigen“. Ergebnis: kürzester Weg über die sichtbaren Kanten, hervorgehoben und animiert, oben eine Infozeile mit der Kette. Gibt es keinen Weg, sagt die Infozeile das. Dieselbe Logik wie `daidalos pfad` (Kantenarten je Ebene, Rolle), damit beide dasselbe Ergebnis zeigen. Dafür einen Test schreiben, der beide vergleicht.

### B7. Im Editor öffnen
- Jeder Datei-Kasten trägt neben dem Schloss ein **Editor-Symbol** (Pfeil aus dem Kasten, wie im Prototyp). Das Code-Symbol `</>` erscheint ebenfalls, ist aber ausgegraut mit dem Hinweis „Code-Ansicht kommt mit `daidalos serve`“.
- Klick öffnet die Datei über einen Editor-Link. Standard ist `vscode://file/{pfad}:{zeile}`, einstellbar in `daidalos.toml` unter `[editor] link` (Teil C2).
- **Absoluter Pfad zur Laufzeit:** Die Karte liegt unter `<repo>/docs/daidalos/karte.html`. Die Seite bestimmt die Repo-Wurzel aus ihrer eigenen Adresse (`file://`-URL, zwei Ordner nach oben) und setzt den relativen Pfad daran. So steht in `karte.html` kein absoluter Pfad. Unter Windows muss daraus `vscode://file/E:/Repositories/.../datei.kt:12` werden. Leerzeichen und Umlaute korrekt kodieren. Wird die Karte nicht über `file://` geöffnet (etwa in einer Vorschau), sind die Editor-Symbole ausgegraut mit Hinweis.
- Zeile: bei einem Datei-Kasten Zeile 1 (Funktionszeilen kommen mit Etappe 4), bei einem Beleg genau dessen Zeile.
- Dieselben Knöpfe stehen oben in den Datei-Details der Seitenleiste.

## Teil C – Ergänzungen in Python

1. **Lösende Kanten je Zyklus:** Der Zyklus-Befund bekommt `loesende_kanten`, also alle Kanten, deren Wegfall allein die Komponente auflöst, sortiert. Die Trennstelle ist davon die mit dem kleinsten Gewicht. Die Berechnung gibt es schon für die Trennstelle, sie muss nur alle Treffer behalten. Datenformat und Golden-Dateien nachtragen.
2. **Editor-Link in die Karte:** `daidalos render` liest `[editor] link` aus `daidalos.toml` (Option `--konfiguration` wie bei `scan`, Standard `<ZIEL>/daidalos.toml`) und bettet die Vorlage als eigenes Einstellungs-JSON in `karte.html` ein. Das ist eine Einstellung und keine Messung, deshalb steht sie nicht in `daidalos.json`. Standard `vscode://file/{pfad}:{zeile}`.

## Tests

Browser-Probe (Marker `browser`) auf den Beispielprojekten, mindestens:
- Standard gesperrt, ein Element entsperren und verschieben, globales Schloss, gemerkte Position nach Neuladen, „Anordnung zurücksetzen“.
- Fokus: Deckkraft-Stufen für gewählten Knoten, direkte Nachbarn, zwei Stufen und Rest in beiden Modi.
- Animation an bei Auswahl, aus ohne Auswahl, keine Bewegung bei emuliertem `prefers-reduced-motion`. Stufe 2 enthält nur Kanten durch den gewählten Knoten.
- Kantenklick zeigt Belege, Grenze, „einzige Verbindung“ und den Zyklus-Bezug. Verdichtete Kante listet tragende Datei-Kanten.
- Klick in „Nutzt“ springt mit Ebenenwechsel und Ausklappen. Browser-Zurück funktioniert.
- Pfad-Suche liefert denselben Weg wie `daidalos pfad --json`.
- Editor-Link: korrekte `vscode://`-Adresse aus einer `file://`-Seite, ausgegraut ohne `file://`.
- Weitere Ordner zusammengefasst, Plugin-Kanten aus mit Vermerk.

Python-Tests für `loesende_kanten` und das Einbetten des Editor-Links.

## Probe an Sketchorus (nur lokal)

- Scan und Render der eingefrorenen Kopie nach `lokal\sketchorus\`, mit `[editor]`-Standard.
- Bildschirmfotos nach `lokal\A05-*.png`: Modulebene, Dateiebene beim Öffnen, Fokus auf einer Datei mit Animation (Standbild reicht), Zyklus im Ring, Kanten-Info, Pfad-Suche, Vergleich der Kantenführung (Teil A5).
- Prüfen, dass das Editor-Symbol einer Datei in VS Code die richtige Datei öffnet, auf Manus Rechner von Hand oder per angezeigter Adresse.
- Zeiten: Fokus setzen, Ebenenwechsel mit Fokus, Bildrate während der Animation auf der Dateiebene grob (Ziel: flüssig, keine sichtbaren Ruckler).

## Abschluss

- Branch `auftrag/a05-bedienung`, pushen, nicht mergen.
- Bericht `docs/auftraege/A05-bericht.md`.
- Antwort an mich mit höchstens 10 Zeilen.

## Abnahmekriterien

- [ ] CI grün mit Browser-Probe.
- [ ] Alle Punkte aus Teil A und B an Sketchorus nachvollziehbar, belegt durch Bildschirmfotos.
- [ ] Pfad-Suche in der Karte und `daidalos pfad` liefern dieselben Wege.
- [ ] Editor-Link öffnet die richtige Datei und Zeile, ohne dass ein absoluter Pfad in `karte.html` steht.
- [ ] `karte.html` bleibt byte-gleich bei gleichen Eingaben.

## Nicht in diesem Auftrag

Code-Vorschau und `daidalos serve` (Etappe 7), Funktionsebene (Etappe 4), Führungen (Etappe 5), Bereiche als Kartenebene, Skill (A06).
