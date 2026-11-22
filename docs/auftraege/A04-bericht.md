# Bericht A04 – Erste Karte: `daidalos render`, `karte.html`, `KARTE.md` und `daidalos pfad`

Stand 2026-11-22. Branch `auftrag/a04-erste-karte`, nicht nach `main` gemergt.

## Was gemacht wurde

| Schritt | Ergebnis |
| --- | --- |
| 1. Messung | `metriken` (`fan_in`, `fan_out`, `instabilitaet`) an allen Modul-, Paket-, Datei- und Ordner-Knoten; `zeilen`, `dateien` und Gruppen-`hash` an Modul, Paket und Ordner; Zyklen „mit Tests“ nur noch, wenn neu, sonst mit `enthaelt_produktiv`. Datenformat und Golden-Dateien nachgetragen. |
| 2. `deutung.json` | Format `schema: 1` in `docs/datenformat.md`; Leser `deutung.py` mit Abgleich (veraltet, tote Verweise als Warnung). Erfundene Deutung für `mini_modulgraph` unter `tests/beispiele/mini_modulgraph/docs/daidalos/deutung.json` (veraltete Beschreibung, tote Verweise auf Knoten, Befund, Kante und im Bereich, `</script>` im Text). |
| 3. `daidalos render` | `render.py`; Vorlage, CSS und Skript getrennt unter `src/daidalos/karte/`, beim Rendern zu einer Datei zusammengesetzt. Messung und Deutung als `application/json` eingebettet. Exit 2 bei fehlender Messung, falschem `schema` oder ungültiger Deutung. |
| 4. Bibliotheken | Cytoscape.js 3.28.1, elkjs 0.9.3, cytoscape-elk 2.4.0 unter `vendor/` mit `HERKUNFT.md` und Lizenztexten; `werkzeuge/hole_vendor.py` holt sie und prüft feste SHA-256-Summen (`--pruefen` ohne Netz). Lizenztexte stehen als Kommentar in `karte.html`. `.gitattributes` hält die Dateien byte-genau. |
| 5. Karte | Aufbau und Farb-Tokens wie im Prototyp (Kopfzeile, Werkzeugleiste, Fläche, Seitenleiste; Dunkel Standard, Dunkel/Hell/System gemerkt in `localStorage` mit `try/catch`). Ebenen Module/Pakete/Dateien mit ELK-Schichtlayout von oben nach unten, Layout je Zustand einmal berechnet und gemerkt. Filter Rolle, Kantenarten, Zyklen; Fremdcode als Kasten „Fremd · n“ je Modul; bei mehr als 150 Dateien Aus- und Einklappen von Modulen. Zyklus-Befund: Mitglieder und Ring hervorgehoben, Einstiege mit eigener Randfarbe (dazu die eingehenden Kanten), Trennstelle dick mit Beschriftung, Zoom auf den Zyklus. Seitenleiste mit Überblick, Befunden, Bereichen, Knoten- und Befund-Details, „gemessen“ und „gedeutet“ getrennt gekennzeichnet. Sprungadressen `#knoten=`, `#befund=`, `#ebene=`. |
| 6. `KARTE.md` | Kopf, Überblick, Modultabelle (plus Ordner), Gradle-Abhängigkeiten, Bereiche, Einschätzungen, alle Zyklen je Ebene mit Mitgliedern, Einstiegen und Trennstelle, übrige Befunde gezählt; jeder Knoten und Befund verlinkt in die Karte. |
| 7. `daidalos pfad` | `pfad.py`: Id oder Suchbegriff (Pfadendung, `:modul`, Modulordner, Paketname), mehrdeutig → Treffer und Exit 2; Breitensuche über `nutzt` (Modulebene zusätzlich Gradle), je Schritt die ersten 3 Belege; `--mit-tests`, `--ebene`, `--json`. |
| 8. Tests | 174 Tests (1 unter Windows übersprungen wie bisher). Neu: `test_render.py` (Golden `KARTE.md` und Prüfsumme der eingebetteten Daten je Beispiel, Struktur, kein Netz, keine absoluten Pfade, Determinismus, Maskierung, Deutung, Exit-Codes), `test_pfad.py`, Metrik- und Zyklus-Tests in `test_struktur.py`, Browser-Probe `test_browser.py` (Marker `browser`). CI: Chromium nur unter Ubuntu, ein eigener Schritt bricht ab, wenn die Browser-Probe dort übersprungen würde. |

Lokal unter Windows: `ruff check`, `ruff format --check`, `pytest` (inklusive Browser-Probe mit
Chromium) grün. CI grün unter Ubuntu (mit Browser-Probe, 5 Tests gelaufen) und Windows.

## Probe an der eingefrorenen Kopie (nur Zahlen)

Gemessen auf diesem Rechner mit Playwright/Chromium (headless, Fenster 1600 × 1000). „Layout“ ist
die Zeit für den ELK-Lauf im Browser, „bis die Ebene steht“ die Zeit vom Klick bis zum fertigen
Bild.

| Größe | Wert |
| --- | --- |
| `karte.html` | 3,73 MiB (3 913 646 Bytes); davon rund 2 MiB Bibliotheken |
| Zwei Läufe `render` | byte-gleich |
| Laufzeit `render` | 0,02 s |
| Seite laden bis Modulebene steht | 0,2 bis 0,5 s |
| Modulebene | 13 Knoten, 17 Kanten; Layout 93 ms, steht nach 0,07 s (zweiter Besuch, gemerkt) |
| Paketebene | 58 Knoten, 161 Kanten; Layout 190 ms, steht nach 0,24 s |
| Dateiebene (Standard: größtes Modul ausgeklappt) | 123 Knoten, 337 Kanten; Layout 336 ms, steht nach 0,38 s |
| Dateien auf der Karte | 483 (davon produktiv und nicht fremd 274), also Aus- und Einklappen aktiv |
| Datei-Zyklen | 11, alle per Klick anklickbar; Mitglieder, Einstiege und Trennstelle in allen 11 Fällen richtig hervorgehoben; je Zyklus 0,4 bis 1,0 s inklusive Ausklappen der Module |
| Paket-Zyklen | 5 produktiv + 1 „mit Tests“ (verschmilzt 2 produktive, `enthaelt_produktiv`); die 11 doppelten Datei-Zyklen „mit Tests“ entfallen |
| Tests ausgeblendet, Fremdcode eingeklappt | ja (Standard „nur produktiv“, Fremdcode als Kasten je Modul) |
| Konsolenfehler, Netzzugriffe | keine |

`daidalos pfad`:
- `:app :core` → 1 Schritt über `gradle-impl` und `nutzt` (Gewicht 54), Belege
  `app/build.gradle.kts:75` und zwei Importe; `:core :app` → „Kein Weg“.
- `HauptActivity.kt app/strich/KernThread.kt` → 2 Schritte über `StrichAnlage.kt` mit Belegen.
  `KernThread.kt` allein ist mehrdeutig (app und labor), die Treffer werden aufgelistet, Exit 2.
- Paketebene `de.sketchorus.app de.sketchorus.core` → 1 Schritt.

Bildschirmfotos: `lokal/A04-{modul,paket,datei}-{dunkel,hell}.png` und `lokal/A04-zyklus-dunkel.png`
(größter Zyklus, 7 Dateien).

## Abweichungen vom Auftrag und Entscheidungen

1. **Branch von A03, nicht von `main`.** A03 war noch nicht nach `main` gemergt. Der Branch zweigt
   daher von `auftrag/a03-modulgraph` ab und enthält dessen Commits.
2. **Ordner auf der Modulebene.** Bisher fielen Dateien in Ordnern außerhalb der Module bei der
   Verdichtung zu Modulkanten weg, Ordner hätten also immer Fan-in/Fan-out 0. Jetzt werden sie wie
   Module verdichtet (`nutzt` modul/ordner → modul/ordner). Das verändert Modulkanten und kann
   Modul-Zyklen mit Ordnern ergeben; für Sketchorus bleibt es bei 0 Modul-Zyklen.
3. **`zeilen`, `dateien`, `hash` stehen oben am Knoten**, nicht in `metriken`, wie `zeilen` und
   `hash` bei Dateien. `metriken` enthält nur die Kopplung.
4. **Maskierung:** Statt nur `</` → `<\/` wird jedes `<` als `<` geschrieben. Das deckt
   `</script>` und `<!--` ab, bleibt gültiges JSON und liefert nach `JSON.parse` denselben Text.
5. **Welche Dateien die Dateiebene zeigt:** Quellcode (`kotlin`, `java`, `c`, `cpp`) und jede Datei
   mit einer Kante. Gradle-Skripte, Markdown usw. stehen nicht als Kästen auf der Karte (in
   Sketchorus wären das über 500 zusätzliche Kästen ohne Kanten). Die Grenze 150 gilt für diese
   Dateien.
6. **Kantenarten je Ebene:** Die Schalter Gradle/nutzt/JNI merken sich ihren Zustand je Ebene. Auf
   der Modulebene ist Gradle an und nutzt aus (Standard „gradle-*“), beides lässt sich zuschalten.
   Nicht passende Schalter sind ausgegraut (Gradle nur auf der Modulebene, JNI nur auf der
   Dateiebene).
7. **Leere Kästen:** Auf Paket- und Dateiebene fallen Module und Ordner ohne sichtbaren Inhalt weg
   (z. B. der Wurzelordner mit nur Gradle-Skripten). Auf der Modulebene stehen alle.
8. **Fremdcode auf der Paketebene** als Kasten „Fremd · n Pakete“ je Modul, entsprechend der
   Dateiebene.
9. **Zyklus anklicken bei großen Projekten** klappt genau die Module des Zyklus aus (und klappt
   andere ein). Beim Hinzufügen statt Ersetzen wuchs die Dateiebene nach einigen Zyklen auf
   4 Module und über 2 s.
10. **`daidalos pfad`:** „Kein Weg“ endet mit Exit-Code 0 (es ist eine Antwort, kein Fehler); VON
    und NACH auf verschiedenen Ebenen enden mit Exit-Code 2. Auf der Dateiebene zählen nur
    `nutzt`-Kanten, wie im Auftrag, JNI nicht. Ordner gelten als Modulebene.
11. **Ungültige `deutung.json`** (kein JSON, anderes `schema`) beendet `render` mit Exit-Code 2,
    statt sie still zu übergehen.
12. **elkjs 0.9.3 statt der neuesten Version:** cytoscape-elk 2.4.0 verlangt `elkjs ^0.9.3`.
13. **Kantenverlauf:** Kanten sind Bézier-Linien zwischen den ELK-Positionen, nicht ELKs eigene
    Kantenführung. Dadurch laufen Kanten teils über Knoten. ELKs Kantenführung würde als
    Bypass-Stil gesetzt und vertrüge sich schlecht mit dem gemerkten Layout. Kandidat für A05.
14. **Bildschirmfotos und Zeiten mit Playwright.** Der Browser-Bereich der App kann keine
    `file://`-Adressen öffnen. Die Zeiten stammen deshalb aus headless Chromium auf diesem
    Rechner.

## Offene Fragen

- **Lizenz elkjs (EPL-2.0):** `karte.html` enthält elkjs samt Lizenztext. Die Datei liegt
  committet in Zielrepos und im Daidalos-Repo (MIT). EPL-2.0 erlaubt die Weitergabe mit
  Lizenzhinweis; bitte trotzdem bestätigen, dass das passt. Sonst wäre Dagre (MIT) die
  Alternative, mit schwächerer Hierarchie-Unterstützung.
- Paket- und Dateiebene sind bei Sketchorus im Überblick dicht (161 bzw. 337 Kanten). Der
  abgestufte Fokus aus A05 sollte das deutlich entschärfen; ob zusätzlich Kanten innerhalb eines
  Pakets standardmäßig blasser werden sollen, wäre zu entscheiden.

## Nächste sinnvolle Schritte

- A05 auf dem Gerüst: `karte.js` stellt `window.daidalos` mit `cy`, `zustand`, `zeichne`,
  `zeigeBefund`, `zeigeKnoten` bereit; Hervorhebung (Abschnitt 6) und Seitenleiste (Abschnitt 7)
  sind die Stellen für Fokus-Stufen, Fluss-Animation, klickbare Listen und Kanten-Infos
  (`D.kanten` wird schon eingebettet und abgeglichen).
- ELK-Kantenführung prüfen (siehe Abweichung 13).
- A06: Der Skill kann die Gruppen-Hashes direkt in `beschreibungen` übernehmen; `render` meldet
  tote Verweise schon.
