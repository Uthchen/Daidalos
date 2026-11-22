# Bericht A03 – Modulgraph: Gradle, Kotlin-Importe, JNI und Zyklen

Stand 2026-11-22. Branch `auftrag/a03-modulgraph`, nicht nach `main` gemergt.

## Was gemacht wurde

| Schritt | Ergebnis |
| --- | --- |
| Abhängigkeiten | `tree-sitter>=0.23`, `tree-sitter-kotlin>=1.0`, `tree-sitter-c>=0.23`, `networkx>=3.3`; `uv.lock` committet. `tree-sitter-kotlin` 1.1.0 hat abi3-Wheels für Windows und Linux, `tree-sitter-language-pack` war also nicht nötig. |
| 1. Datenformat | `docs/datenformat.md`: Knoten `modul`, `paket`, `ordner`, neue Datei-Felder, Kantenarten, Kantenfelder, Ids für Kanten und Befunde, Befunde `zyklus`, `jni-ohne-gegenstueck`, `unaufgeloest`, die Regeln für Gradle, `nutzt` und JNI. `schema` bleibt 1. |
| 2. Gradle-Adapter | `adapter/gradle.py`: `include(...)`, `projectDir`, Groovy-Rückfall mit Warnung; Projekt-Abhängigkeiten mit Konfiguration, Quellsatz (`X.dependencies`, `val X by getting`, `sourceSets { X { } }`), `bedingt`, Wurzel-`subprojects`/`allprojects`; Plugins. |
| 3. Zuordnung | `struktur.py`: längstes Pfadpräfix, Quellsatz, Rolle, Ordner-Knoten, `enthaelt`-Kanten. |
| 4. Kotlin-Adapter | `adapter/kotlin.py`: Paket, Importe (Alias, Stern), Deklarationen inkl. verschachtelter Klassen und Objekt-/Companion-Mitglieder, verwendete Namen ohne Kommentare und Strings, Namen hinter einem Punkt, punktierte Ausdrücke, `external fun`. Dataclass `KotlinDatei`, ohne Auflöser testbar. |
| 5. Auflöser | `aufloeser.py`: Symbolverzeichnis, Importe über längstes Präfix, gleiches Paket, Stern-Importe, voll qualifiziert, Sicherheit, `unaufgeloest`; Verdichtung zu Paket- und Modulkanten je Rolle in `struktur.py`. |
| 6. JNI | `adapter/jni.py`: Kodieren/Dekodieren mit `_1`, `_2`, `_3`, `_0xxxx` und `__<Signatur>`; C-Definitionen über tree-sitter-c (auch für `.cpp`). |
| 7. Zyklen | `analysen/zyklen.py`: SCCs je Ebene und Rolle, Einstiege, Trennstelle, kleinste Trennmenge (bis 8 Kanten), Vermerk `unsicher`. |
| 8. CLI | Zusammenfassung um Module, Gradle-Kanten, Pakete, Datei-Kanten (sicher/unsicher, unaufgelöste Importe), JNI-Paare und Zyklen je Ebene und Rolle. |
| 9. Tests | 136 Tests (1 unter Windows übersprungen wie in A02). Neues Beispiel `tests/beispiele/mini_modulgraph/` mit allen geforderten Fällen, Golden-Datei je Beispiel, Einzeltests `test_gradle`, `test_kotlin`, `test_aufloeser`, `test_jni`, `test_zyklen`, `test_struktur`. Testhilfe `tests/plausibilitaet.py`. |
| 11. Kleinigkeiten | `.sql` → `sql`; `[projekt] name` in `daidalos.toml`; Lockfiles bleiben `unbekannt`. |

Lokal unter Windows: `ruff check`, `ruff format --check`, `pytest` grün.

## Probe an der eingefrorenen Kopie (nur Zahlen)

Aufruf wie im Auftrag, `[projekt] name` in der lokalen Probe-Konfiguration eingetragen.

| Größe | Wert |
| --- | --- |
| Module / Gradle-Kanten | 7 / 17 (11 Code-Kanten + 6 × `gradle-plugin` auf das Regelmodul) |
| Pakete | 52 |
| Datei-Kanten `nutzt` | 1 638 (sicher 1 631, unsicher 7; produktiv 1 061, test 577) |
| Belege | 1 164 Import, 1 059 gleiches Paket, 13 voll qualifiziert |
| Unaufgelöste interne Importe | 0 |
| JNI | 26 Paare, 1 Kotlin-Funktion ohne Gegenstück (siehe unten), 0 ungepaarte C-Funktionen |
| Zyklen | Datei 11/11, Paket 5/4, Modul (nutzt) 0/0, Modul (Gradle) 0/0 (produktiv/mit Tests) |
| Zyklen ohne Trennstelle | 0 |
| Plausibilität | 0 Verstöße |
| Zwei Läufe | byte-gleich |
| Laufzeit | rund 1,9 s je Lauf |

**Module und Gradle-Kanten:** stimmen genau mit der Tabelle aus Steckbrief Abschnitt 2 überein:
das Labor-Kernmodul hängt per `gradle-api` (Quellsatz `commonMain`) am Kern, alle 6 übrigen Module
hängen per `gradle-plugin` (Beleg `quelle: wurzel`) am Regelmodul, das Regelmodul nicht an sich
selbst. Die bedingte Abhängigkeit in der App ist extern (`implementation("…")` ohne `project`) und
erzeugt keine Kante. Die Task-Kante `dependsOn(":…")` wird wie gefordert nicht erfasst.

**Datei-Kanten:** Floorplan meldete 1 888 aufgelöste Datei-Importe, zeigt aber nur 1 632 Links. Die
1 888 zählen Import-Zeilen (mehrere Zeilen zwischen denselben Dateien), die 1 632 sind
verschiedene Dateipaare. Daidalos kommt auf 1 638 Dateipaare, davon 1 630 auch bei Floorplan.
- Nur bei Daidalos (8): 6 voll qualifizierte Bezüge und 2 Bezüge im gleichen Paket, die Floorplan
  nicht sieht.
- Nur bei Floorplan (2): zwei Test-Dateien → eine Journal-Datei im gleichen Paket. Im Text der
  Testdateien kommt keiner der dort deklarierten Namen vor; ich halte die Floorplan-Kanten für
  falsch.
- Drei weitere Floorplan-Kanten fehlten zunächst: Aufrufe von Erweiterungsfunktionen im gleichen
  Paket (`x.erweiterung()`). Sie werden jetzt erkannt, als unsichere Kanten.

**Zyklen:** Die 11 Datei-Zyklen sind dieselben Mengen wie im Floorplan-Graphen (Abgleich der
Mitgliedermengen: 11 gleich, 0 Abweichungen), sowohl für „nur produktiv“ als auch „mit Tests“. Die
Testdateien bilden keine eigenen Zyklen. Hinweis zu A01: Die Größen sind 2, 3, 4 und einmal 7
Dateien, nicht nur 2 bis 4; die Mengen stimmen trotzdem überein. Keiner der Zyklen enthält eine
unsichere Kante, alle haben eine einzelne Trennstelle.

**Paket-Zyklen 5 produktiv / 4 mit Tests:** Mit Test-Kanten verschmelzen zwei produktive
Paket-Zyklen des Labor-Kernmoduls zu einem größeren (4 Pakete), daher eine Komponente weniger.

**JNI:** 26 Paare wie erwartet. Der eine Befund `jni-ohne-gegenstueck` ist eine echte
`external fun` in der Werkzeugdatei außerhalb der Module (Gegenfall-Sammlung für eine Prüfregel).
Sie hat tatsächlich keine C-Seite, der Hinweis ist also richtig. Die Erwartung „0 ungepaarte“ aus
dem Auftrag gilt für die 26 Funktionen der Module.

## Abweichungen vom Auftrag und Entscheidungen

1. **Eigenes Beispielprojekt `mini_modulgraph`** statt `mini_gradle` zu erweitern. So bleiben die
   A02-Tests und ihre Zählungen stabil, und die A03-Fälle stehen gesammelt an einer Stelle. Die
   Golden-Datei von `mini_gradle` enthält jetzt zusätzlich die Strukturdaten.
2. **Rückfall bei Parse-Lücken der Kotlin-Grammatik.** tree-sitter-kotlin liest Annotationen auf
   eigenen Zeilen vor `annotation class X` als Ausdruck, nicht als Deklaration (betraf die 4
   Markierungs-Annotationen); in 2 weiteren Dateien gibt es Parse-Fehler. Ohne Rückfall blieben
   54 Importe unaufgelöst. Lösung: In Knoten der obersten Ebene, die keine erkannte Deklaration
   sind, werden Zeilen ohne Einrückung über ein Textmuster als Deklaration gelesen. Danach 0
   unaufgelöste Importe. Das ist eng begrenzt (nur oberste Ebene, nur in nicht erkannten Knoten)
   und im Datenformat beschrieben.
3. **Produktiver Code sieht keinen Testcode.** Ziele mit Rolle `test` entfallen für produktive
   Quelldateien. Das ist keine Vermutung, sondern die Sichtbarkeit beim Kompilieren, und verhindert
   falsche Kanten über gleichnamige Test-Hilfen.
4. **Erweiterungsfunktionen im gleichen Paket** (`x.name()`) werden aufgelöst, immer unsicher.
   Das stand nicht ausdrücklich im Auftrag, die Kanten fehlten aber gegenüber Floorplan.
5. **Pakete außerhalb von Modulen** bekommen die Id `paket:<ordner-id>/<name>` und das Feld
   `ordner` statt `modul`. Der Auftrag nannte nur die Modul-Form.
6. **`bedingt`:** Neben `dependencies`/`sourceSets` gelten auch strukturelle Blöcke wie `kotlin`,
   `android`, `subprojects`, `getting`, `withType` als neutral. Sonst wäre jede KMP-Abhängigkeit
   (in `kotlin { }`) bedingt. Alle anderen Lambdas (z. B. `afterEvaluate`) und `if`/`when` machen
   `bedingt: true`.
7. **Kantenfelder:** Gradle-Kanten tragen `gewicht` (Zahl der Belege), `rolle` und `sicher`, damit
   die Trennstelle auf Modulebene ein Gewicht hat. Datei-Belege tragen zusätzlich `sicher`,
   verdichtete Kanten `dateikanten`. Die Rolle steht nur bei `nutzt`/`jni` in der Kanten-Id.
8. **`detektPlugins` → `gradle-plugin`** gilt überall, nicht nur im Wurzel-Build.
9. **`kotlin("jvm")`** im `plugins`-Block wird als `org.jetbrains.kotlin.jvm` erfasst.
10. **Fremdcode auf Paket- und Ordnerebene:** Ein Paket oder Ordner gilt als fremd (`fremd: true`),
    wenn alle seine Dateien fremd sind, und wird dann aus der Zyklensuche entfernt.
11. **Zwischen-Commits:** Die Commits sind thematisch geschnitten; einzelne Zwischenstände (z. B.
    Scanner vor Konfiguration) sind für sich nicht lauffähig, der Branch-Kopf schon.

## Offene Fragen

- Zyklus-Befunde „mit Tests“ wiederholen meist die produktiven (in Sketchorus alle 11 Datei-Zyklen).
  Soll die Karte doppelte Mengen zusammenfassen, oder soll das Programm nur zusätzliche
  „mit Tests“-Zyklen melden?
- Typsichere Projekt-Accessoren (`projects.core`) und Versionskataloge für Projekte werden nicht
  erkannt; Sketchorus nutzt sie nicht.
- Sichtbarkeit zwischen KMP-Quellsätzen (z. B. `jvmMain` sieht `androidMain` nicht) wird nicht
  ausgewertet, nur produktiv gegen test.
- Overloads einer `external fun` werden über Klasse und Methode gepaart, die Signatur zählt nicht.

## Nächste sinnvolle Schritte

- A04: Karte und `render` auf Basis der jetzt vorhandenen Ebenen; Test-Kanten standardmäßig
  ausblenden, Zyklen mit Einstiegen und Trennstelle zeigen.
- Den Rückfall aus Abweichung 2 im Blick behalten: Bei einer neueren tree-sitter-kotlin-Version
  prüfen, ob er überflüssig wird.
- Optional eine Warnung auf stderr, wenn eine Datei Parse-Fehler hat.
