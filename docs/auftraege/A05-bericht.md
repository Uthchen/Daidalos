# Bericht A05 – Bedienung der Karte wie im Prototyp

Stand 2026-11-22. Branch `auftrag/a05-bedienung`, nicht nach `main` gemergt.

## Was gemacht wurde

| Teil | Ergebnis |
| --- | --- |
| A1 Weitere Ordner | Ordner ohne Dateien der Karte und ohne Kanten werden auf der Modulebene ein Kasten „Weitere Ordner · n Ordner · m Dateien“ (Id `sammel:ordner`). Ein Klick listet sie mit Dateien und Zeilen, jede Datei aufklappbar mit Editor-Link. Sketchorus: `(Wurzel)`, `.claude/`, `config/`, `docs/`, `gradle/` → „5 Ordner · 467 Dateien“; `werkzeuge/` bleibt einzeln. |
| A2 Plugin-Kanten | `gradle-plugin` standardmäßig aus, am Ziel die Zeile „Plugin für n Module“ (Sketchorus: `:detekt-regeln`, 6). Schalter „Plugins“ (nur Modulebene mit Gradle); Plugin-Kanten gepunktet. |
| A3 Kanten im Paket | Dateiebene: Kanten zwischen Dateien desselben Pakets mit Deckkraft 0,32 (Klasse `innen`); in Fokus, Zyklus und Pfad gilt die Stufe des Fokus bzw. volle Deckkraft. |
| A4 Start der Dateiebene | Fallen Dateinamen beim Einpassen unter 9 px, zeigt die Dateiebene das größte Paket (meiste Dateien) lesbar (Zoom ≥ 0,82); „Einpassen“ zeigt alles. `min-zoomed-font-size`: Dateien 8, Pakete 4, Module 3, Kanten 6. |
| A5 Kantenführung | ELKs orthogonale Führung über `useElkEdgeGeometry` von cytoscape-elk 2.4.0 (ohne Änderung an `vendor/`). Begründung und Vergleich siehe unten. Die Routen werden mit dem Layout gemerkt; Kanten an verschobenen Knoten fallen auf Bézier zurück. |
| B1 Sperren, Positionen | Alles standardmäßig gesperrt; Schloss oben rechts an jedem Kasten (offen und farbig, wenn entsperrt), globales Schloss oben rechts mit „alle gesperrt“ / „alle entsperrt“ / „n entsperrt“. Gruppen samt Inhalt verschiebbar, ausdrücklich gesperrte Elemente darin bleiben stehen. Positionen in `localStorage` (`try/catch`) je Projekt, Ebene und Knoten-Id; „Anordnung zurücksetzen“ löscht die Ebene. Sperrzustand bleibt über Ebenenwechsel. |
| B2 Fokus | Gewählt 1, direkte Nachbarn `--o-n1`, zwei Verbindungen `--o-n2`, Rest `--o-blass` (hell 0,75/0,4/0,14, dunkel 0,82/0,5/0,22). Kanten bekommen die Stufe des blasseren Endes, Kanten zum gewählten Knoten voll. Zoom auf gewählten Knoten und direkte Nachbarn; Klick ins Leere oder `Esc` hebt auf. Behälter werden nie über `opacity` abgeblendet (Cytoscape multipliziert sie in die Kinder), sondern nur an Rand, Fläche und Schrift. |
| B3 Fluss | Ein `requestAnimationFrame`-Takt (~30 Schritte/s), nur auf hervorgehobenen Kanten. Stufe 1: direkte Kanten (ausgehend Akzentfarbe, eingehend Textfarbe); Stufe 2 feiner und langsamer, nur Ketten durch den gewählten Knoten. Zählzeile wie im Prototyp. Zyklus: endlos im Ring; Pfad: vom Start zum Ziel. `prefers-reduced-motion`: stehende Striche. |
| B4 Kanten | Klick auf eine Kante: Art, Von/Nach (klickbar), Gewicht, Rolle, sicher/unsicher, Grenze, „einzige Verbindung“ der Pakete bzw. Module (aus `dateikanten` der verdichteten Kanten), Belege mit Editor-Link je Zeile (Datei-Kanten: Symbol/Zeile/Herkunft; JNI: Kotlin- und C-Zeile; Gradle: Build-Datei, Zeile, Konfiguration, Quellsatz, bedingt). Verdichtete Kanten: tragende Datei-Kanten, klickbar, nach Gewicht. Gradle-Kanten: die `nutzt`-Kanten, die sie verwenden. Zyklus-Bezug mit Link, „günstigste Trennstelle“, „Wegfall allein löst den Zyklus“. Deutungstext aus `deutung.json` als „gedeutet“. |
| B5 Klickbare Listen | Nutzt / Wird genutzt von (Knoten und Kantenart), Mitglieder, Einstiege, Trennstelle und lösende Kanten eines Zyklus, Bereiche, Knoten in Kanten-Details und Befunden. Ein Klick wechselt bei Bedarf Ebene und Rolle, klappt Module aus und setzt den Fokus. Jede Auswahl ist ein Eintrag im Browser-Verlauf (`pushState`), Zurück führt zur vorherigen. |
| B6 Pfad-Suche | „Warum hängt [Von] an [Nach]“ mit zwei Suchfeldern (`datalist` mit den Knoten der Ebene; Eingabe auch als eindeutiger Namensteil) und „Kette zeigen“. Gleiche Logik wie `daidalos pfad`. Ergebnis hervorgehoben, animiert, Infozeile mit der Kette oder „… hängt nicht an …“. |
| B7 Editor | Code-, Editor- und Schloss-Symbol an jedem Datei-Kasten; Code ausgegraut (Hinweis „kommt mit `daidalos serve`“). Link aus `[editor].link`, Repo-Wurzel aus der eigenen `file://`-Adresse plus eingebettetem relativem Weg, Segmente URL-kodiert. Ohne `file://` oder ohne Wurzel ausgegraut mit Hinweis. Dieselben Knöpfe in den Datei-Details. |
| C1 `loesende_kanten` | Im Zyklus-Beleg alle Kanten, deren Wegfall allein die Komponente löst, nach Id sortiert; `trennstelle` ist die leichteste davon. Datenformat und Golden-Dateien nachgetragen (`schema` bleibt 1, das Feld ist neu und optional für Leser). |
| C2 Editor-Link | `[editor] link` (Standard `vscode://file/{pfad}:{zeile}`), `render --konfiguration`, eigener Block `daidalos-einstellungen` in `karte.html` (nicht in `daidalos.json`). |
| Tests | 198 Tests (1 unter Windows übersprungen wie bisher), davon 22 in der Browser-Probe: Sperren/Verschieben/Neuladen/Zurücksetzen/globales Schloss, Gruppe mit gesperrtem Kind, Fokus-Stufen hell und dunkel, Fluss an/aus und Stufe 2, `reduced-motion`, Kantenklick (echter Mausklick), verdichtete und Gradle-Kante, Sprung mit Ebenenwechsel und Zurück, Sprung mit Ausklappen (künstlich großes Projekt), Pfad-Suche für alle Knotenpaare aller Ebenen gegen `pfad.suche_weg` und über die Leiste gegen `daidalos pfad --json`, Editor-Link aus `file://` (Pfad mit Leerzeichen und Umlaut) und ausgegraut ohne `file://`, Weitere Ordner, Plugin-Kanten, blasse Paket-Kanten. Python: `loesende_kanten`, `[editor].link`, Einbettung, `wurzel`. |

Lokal unter Windows: `ruff check`, `ruff format --check`, `pytest` (mit Browser-Probe) grün. CI
grün unter Ubuntu (mit Browser-Probe) und Windows (Lauf 45050665404).

## Kantenführung (A5)

Verglichen an Sketchorus auf allen drei Ebenen: `lokal/A05-kantenfuehrung-{modul,paket,datei}-{elk,taxi,bezier}.png`.

- **ELK orthogonal** (gewählt): Kanten laufen in Kanälen zwischen den Kästen, nicht über sie. Ein
  Zyklus lässt sich als Ring verfolgen (`A05-zyklus-ring.png`), mit dem Fluss sieht man die
  Richtung. Nachteil: parallele Kanten bündeln sich zu „Kabelsträngen“, auf der Paketebene im
  Überblick dicht.
- **`taxi`**: rechtwinklig, aber ohne Wissen über die Kästen; senkrechte Abschnitte laufen quer
  durch Dateikästen, verschiedene Kanten legen sich übereinander und sind nicht mehr
  auseinanderzuhalten.
- **Bézier** (A04): kreuzt Kästen am stärksten.

Gemerkte Positionen: Kanten an einem verschobenen Knoten verlieren die ELK-Route und werden
Bézier, alle anderen behalten sie. Die Variante lässt sich zum Vergleich über
`daidalos.zustand.kantenfuehrung = 'taxi' | 'bezier'` und `daidalos.zeichne()` umstellen (kein
Schalter in der Leiste).

## Probe an Sketchorus (nur lokal)

Scan und Render der eingefrorenen Kopie nach `lokal/sketchorus/` mit `[editor]`-Standard, für den
Editor-Link zusätzlich in den Standardordner der Kopie (`docs/daidalos/`). Gemessen mit
Playwright/Chromium headless, Fenster 1600 × 1000.

| Größe | Wert |
| --- | --- |
| `karte.html` | 3,79 MiB; zwei Läufe byte-gleich; kein absoluter Pfad enthalten |
| Dateiebene öffnen (Layout neu) | 0,51 s, 123 Knoten, 337 Kanten; Start im Paket `de.sketchorus.core.pinsel`, Zoom 0,82 |
| Fokus setzen | erster Fokus 0,41 s (Datei mit 22 Nutzern), danach 0,12–0,19 s |
| Ebenenwechsel mit Fokus | Datei → Paket 0,19 s, Paket → Datei 0,12 s (Layout gemerkt) |
| Bildrate während der Animation (Dateiebene, 22 + 68 animierte Kanten) | 60 Bilder/s, längster Abstand 16,8 ms |
| Größter Zyklus (7 Dateien) | 0,36 s inkl. Ausklappen; 15 Kanten, 6 davon lösen ihn allein |
| Pfad-Suche `HauptActivity.kt` → `app/strich/KernThread.kt` | `HauptActivity.kt → StrichAnlage.kt → KernThread.kt`, wie `daidalos pfad` in A04 |
| Konsolenfehler, Netzzugriffe | keine |

Editor-Link (aus `lokal/sketchorus-kopie/docs/daidalos/karte.html`), angezeigt für
`Strichpfad.kt`:
`vscode://file/E:/Repositories/Daidalos/lokal/sketchorus-kopie/core/src/commonMain/kotlin/de/sketchorus/core/strichpfad/Strichpfad.kt:1`.
Die dekodierte Adresse zeigt auf eine vorhandene Datei. Ob VS Code sie öffnet, bitte von Hand
prüfen (Karte im Browser öffnen, Editor-Symbol klicken); VS Code habe ich nicht ohne Rückfrage
gestartet.

Bildschirmfotos: `lokal/A05-modul.png`, `A05-weitere-ordner.png`, `A05-datei-start.png`,
`A05-fokus-datei.png` (Fokus mit Zoom auf alle Nachbarn), `A05-fokus-datei-nah.png` (derselbe
Fokus näher, Stufen und Fluss sichtbar), `A05-fokus-datei-hell.png`, `A05-zyklus-ring.png`,
`A05-kante.png`, `A05-kante-paket.png`, `A05-pfad.png`, `A05-kantenfuehrung-*.png`.

## Abweichungen vom Auftrag und Entscheidungen

1. **Branch von A04, nicht von `main`.** `main` steht noch bei A02; A03 und A04 sind nicht
   gemergt. Der Branch zweigt von `auftrag/a04-erste-karte` ab und enthält dessen Commits.
2. **Sperren in Gruppen.** Ohne eigenen Zustand erbt ein Element den des nächsten Behälters
   (sonst den globalen). Ein entsperrtes Paket lässt sich so samt Inhalt ziehen; wer darin
   ein Element ausdrücklich wieder sperrt, behält es an seinem Platz (die Karte setzt es beim
   Ziehen zurück). „n entsperrt“ zählt die tatsächlich verschiebbaren Kästen der Ebene.
3. **Pfad-Suche über die Messung, nicht über die gezeichneten Kanten.** Damit sie genau
   `daidalos pfad` entspricht (Kantenarten je Ebene, Rolle nach dem Schalter „nur produktiv /
   mit Tests“). Nötige Kantenarten, Plugins und ausgeklappte Module schaltet die Karte für die
   Anzeige dazu. Getestet für alle Knotenpaare aller Ebenen beider Rollen.
4. **`{pfad}` ohne führenden Schrägstrich** (`E:/…`, unter Linux `home/…`), damit der Standard
   `vscode://file/{pfad}:{zeile}` auf beiden Systemen eine gültige Adresse ergibt. Der Weg zur
   Repo-Wurzel ist eingebettet (`wurzel`, im Standardordner `../..`), weil `render --ausgabe`
   auch woanders hin schreiben kann. Liegt die Ausgabe nicht im Zielrepo (wie
   `lokal/sketchorus/`), ist `wurzel` `null` und die Editor-Symbole sind ausgegraut.
5. **Gradle-Skripte (`*.gradle.kts`) sind keine Dateien der Karte**, obwohl die Endungstabelle
   `.kts` als `kotlin` führt. Sonst stand `gradle/` wegen `native-pruefungen.gradle.kts` einzeln.
   Das ist nur Darstellung; die Messung ist unverändert (siehe offene Fragen).
6. **„Weitere Ordner“ auch bei nur einem Ordner** (`mini_modulgraph`: Wurzelordner), damit die
   Modulebene immer gleich aufgebaut ist.
7. **Zählzeile zählt Knoten**, nicht Kanten: „3 direkt“ sind drei Dateien. Stufe 2 zählt nur
   Knoten, die nicht schon direkt anliegen.
8. **Kante gewählt:** Fokus auf beide Enden wie verlangt, gezoomt aber nur auf Kante und Enden
   (alle Nachbarn beider Enden ergaben bei Sketchorus eine unlesbare Übersicht).
9. **Fokus auf Behälter** (Modul oder Paket als Kasten mit Inhalt): ihr Inhalt gilt als gewählt.
10. **Neue Sprungadressen** `#ebene=…&kante=…` und `#ebene=…&von=…&nach=…`, damit Zurück auch
    Kanten- und Pfad-Auswahlen wiederherstellt.
11. **Positionen je Ebene**, unabhängig von Rolle und Kantenarten (wie im Auftrag); nach einem
    Wechsel der Schalter stehen gemerkte Knoten im neuen Layout an ihrer alten Stelle.
12. **Klick auf Symbole hat Vorrang vor Kanten**, die über den Kasten laufen (sonst traf ein
    Klick auf das Schloss eines Pakets oft eine Kante).

## Offene Fragen

- **Fokus-Zoom bei Sketchorus:** Das ELK-Schichtlayout ist hoch; direkte Nachbarn liegen oft weit
  auseinander (z. B. `Merkmalsliste.kt`: 7 Nachbarn über 3 600 Einheiten). „Alle direkten Nachbarn
  ins Bild“ ergibt dann Zoom 0,2 und ausgeblendete Namen. Vorschlag: Mindestzoom (etwa 0,6) mit dem
  gewählten Knoten in der Mitte; Nachbarn stehen ohnehin in der Seitenleiste und der Zählzeile.
- **`.kts` in der Endungstabelle:** Soll `*.gradle.kts` allgemein `gradle-kotlin` werden (Messung,
  ändert `sprache` und Zählungen)? Dann entfällt die Sonderregel in der Karte.
- **Gemerkte Positionen unter `file://`:** Chromium teilt `localStorage` für alle `file://`-Seiten.
  Der Schlüssel enthält daher `ziel.name`; zwei Projekte mit gleichem Namen teilen sich die
  Positionen.
- **Kanten-Fokus:** Weil der Fokus für beide Enden gilt, laufen bei viel genutzten Dateien sehr
  viele Kanten gleichzeitig. Falls das stört: Fluss nur auf der gewählten Kante.

## Nächste sinnvolle Schritte

- A06 Skill: `deutung.json` mit `kanten`-Texten füllen; die Karte zeigt sie schon in den
  Kanten-Details.
- Fokus-Zoom gemäß der offenen Frage nachziehen, falls gewünscht (kleine Änderung in `fokus()`).
- Feinschliff-Liste: `.gradle.kts` in `sprachen.py`, ELK-Abstände für die Paketebene (weniger
  Kabelstränge, z. B. `elk.layered.mergeEdges`).
