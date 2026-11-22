# Auftrag A03 – Modulgraph: Gradle, Kotlin-Importe, JNI und Zyklen

**Etappe:** 2, zweiter Teil · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** A02 ist nach `main` gemergt. Branch `auftrag/a03-modulgraph` von `main`.

## Ziel

`daidalos scan` liefert danach den vollständigen Strukturgraphen auf drei Ebenen (Modul, Paket, Datei) mit Kanten und Zyklen:

- Gradle-Module mit ihren Abhängigkeiten,
- jede Datei mit Modul, Quellsatz, Rolle (produktiv oder test) und Paket,
- Kotlin-Verbindungen zwischen Dateien, zu Paket- und Modulkanten verdichtet,
- JNI-Verbindungen zwischen Kotlin und C,
- Zyklen auf jeder Ebene als Befunde, mit Einstiegen und günstigster Trennstelle.

Lies vorher `CLAUDE.md`, `docs/architektur.md`, `docs/datenformat.md` und als Faktenquelle `lokal/A01-steckbrief-sketchorus.md` (nicht committen, nichts daraus ins Repo übernehmen außer allgemeinen Regeln).

## Entscheidungen, die schon feststehen

1. **Tests** werden voll gemessen. Jede Datei und jede Kante trägt eine Rolle, damit die Karte Tests später standardmäßig ausblenden kann.
2. **Fremdcode** (`fremd: true` aus A02) bleibt im Graphen, aber Zyklen und andere Befunde werden für ihn nicht gemeldet.
3. **JNI** kommt schon jetzt dazu, nicht erst in Etappe 8.
4. **Dateien außerhalb von Modulen** (in Sketchorus `werkzeuge/`) hängen an einem Ordner-Knoten, nicht an einem Modul.
5. **Markierungen** (`@Strichpfad` usw.) sind nicht Teil dieses Auftrags. Wenn später, dann nur über den vollen Namen.

## Abhängigkeiten

- `tree-sitter` (Python-Bindung, aktuelle Version) mit den Grammatiken für Kotlin und C als eigene Wheels (`tree-sitter-kotlin`, `tree-sitter-c`). Falls es für Kotlin kein brauchbares Wheel für Windows und Linux gibt, `tree-sitter-language-pack` nehmen und im Bericht begründen.
- `networkx` für Graphen.
- Versionen in `pyproject.toml` mit Untergrenze festlegen, `uv.lock` committen.

## Schritte

### 1. Datenmodell erweitern (`docs/datenformat.md` zuerst)

Additiv, `schema` bleibt 1 (noch keine Veröffentlichung). Neu:

**Knotenarten**
- `modul`: `id` `modul:<gradle-pfad>`, `pfad` (Ordner), `gradle_pfad`, `plugins` (Liste der Plugin-Aliase bzw. -Ids aus dem `plugins { }`-Block, roh und sortiert).
- `paket`: `id` `paket:<gradle-pfad>/<paketname>`, `modul`, `name`.
- `ordner`: für Dateien außerhalb jedes Moduls, `id` `ordner:<erster Pfadteil>`, Dateien direkt im Wurzelordner unter `ordner:.`.

**Neue Felder an `datei`**
- `modul` (Id oder fehlt), `ordner` (Id, nur wenn kein Modul), `quellsatz` (z. B. `commonMain`, `jvmTest`, `main`, `testMessung`; abgeleitet aus `<modul>/src/<quellsatz>/`, sonst fehlt), `rolle` (`produktiv` oder `test`; `test`, wenn der Quellsatz `test` oder `Test` enthält oder `androidTest` ist), `paket` (Id, nur Kotlin mit `package`-Zeile).

**Kantenarten**
| art | von → nach | Bedeutung |
| --- | --- | --- |
| `gradle-api`, `gradle-impl`, `gradle-test`, `gradle-compileonly`, `gradle-plugin`, `gradle-sonstige` | modul → modul | Projekt-Abhängigkeit aus den Build-Skripten |
| `nutzt` | datei → datei | Kotlin-Bezug (Import, gleiches Paket, voll qualifiziert) |
| `nutzt` | paket → paket, modul → modul | Verdichtung der Datei-Kanten |
| `jni` | datei (Kotlin) → datei (C) | `external fun` zu `Java_…` |
| `enthaelt` | modul → paket, paket → datei, modul/ordner → datei | Hierarchie |

**Neue Kantenfelder**
- `gewicht`: bei `nutzt` die Zahl der verschiedenen genutzten Symbole; bei Verdichtungen die Summe.
- `rolle`: `produktiv` oder `test`, nach der Rolle der Quelldatei. Verdichtete Kanten werden **getrennt nach Rolle** erzeugt, also bis zu zwei Kanten je Paar.
- `sicher`: `true` oder `false`.
- `beleg`: Liste von `{ "symbol": …, "zeile": …, "herkunft": "import" | "gleiches-paket" | "voll-qualifiziert" }`, sortiert, nur an Datei-Kanten. Bei Gradle-Kanten `{ "datei": "core-labor/build.gradle.kts", "zeile": 12, "konfiguration": "api", "quellsatz": "commonMain", "bedingt": false }`.
- Die Kanten-Id ist `kante:<art>:<von>-><nach>[:<rolle>]`.

**Befunde**
- `zyklus` (je Ebene `datei`, `paket`, `modul`, getrennt für „nur produktiv“ und „mit Tests“). Id stabil aus Ebene, Rolle und den sortierten Mitgliedern, z. B. `befund:zyklus:datei:produktiv:<erste 12 Zeichen eines SHA-256 über die Mitglieder-Ids>`. Beleg: `knoten` (sortiert), `kanten` (Ids im Zyklus), `einstiege` (Mitglieder mit eingehender Kante von außerhalb des Zyklus, mit diesen Quellen), `trennstelle` (siehe Schritt 6).
- `jni-ohne-gegenstueck` (Schwere `hinweis`), für `external fun` ohne C-Funktion und umgekehrt.
- `unaufgeloest` (Schwere `hinweis`), je Datei die Importe mit `de.`-artigen internen Präfixen, die nicht aufgelöst werden konnten. Welche Präfixe intern sind, ergibt sich aus den gefundenen Paketen.

### 2. Gradle-Adapter (`daidalos/adapter/gradle.py`)

Die `.kts`-Dateien sind Kotlin. Lies sie deshalb mit tree-sitter-kotlin und nicht mit regulären Ausdrücken, damit Verschachtelung und Bedingungen erkannt werden.

- **`settings.gradle.kts`:** alle `include(...)`-Aufrufe mit allen String-Argumenten. Modulordner aus dem Gradle-Pfad (`:a:b` → `a/b`). `project(":x").projectDir = …` erkennen und anwenden, falls einfach (String-Literal), sonst Warnung. Gibt es nur `settings.gradle` (Groovy): einfache Textauswertung der `include`-Zeilen und Warnung, dass Groovy nur grob unterstützt ist.
- **`build.gradle.kts` je Modul:** jeden Aufruf der Form `<konfiguration>(project(":x"))` finden, egal wo er steht.
  - Konfiguration: `api` → `gradle-api`; `implementation` → `gradle-impl`; alles mit `test`/`Test` im Namen (`testImplementation`, `androidTestImplementation`, `commonTest…`) → `gradle-test`; `compileOnly` → `gradle-compileonly`; sonst `gradle-sonstige` mit der Konfiguration im Beleg.
  - Steht der Aufruf in `sourceSets { <name>.dependencies { … } }` oder `val <name> by getting { dependencies { … } }`, ist `<name>` der Quellsatz im Beleg. Ein Quellsatz mit `Test` im Namen macht die Kante zu `gradle-test`.
  - Steht der Aufruf innerhalb eines `if`, `when` oder eines Lambdas, das kein `dependencies`/`sourceSets`-Block ist, dann `bedingt: true`.
  - `plugins { }`: `alias(libs.plugins.x.y)` → `x.y`, `id("…")` → die Id.
- **Wurzel-`build.gradle.kts`:** `dependencies.add("<konfiguration>", project(":x"))` innerhalb von `subprojects { }`, `allprojects { }` oder `plugins.withType<…> { }` bedeutet: Kante von **jedem** Modul (außer `:x` selbst) nach `:x`. Für `detektPlugins` ist das `gradle-plugin`. Im Beleg `"quelle": "wurzel"`.
- Task-Abhängigkeiten (`dependsOn(":x:task")`) werden nicht erfasst.

### 3. Zuordnung der Dateien

- Modul: der Modulordner mit dem **längsten passenden Pfadpräfix** (verschachtelte Module sind so abgedeckt). Kein Paket-Präfix verwenden, die Labor-Pakete liegen unter dem Kern-Paket.
- Quellsatz und Rolle wie in Schritt 1.
- Dateien ohne Modul: `ordner`-Knoten.
- `enthaelt`-Kanten erzeugen.

### 4. Kotlin-Adapter (`daidalos/adapter/kotlin.py`)

Je `.kt`-Datei (nicht `.kts`) mit tree-sitter:
- `package`, Importe (voller Name, Alias, Zeile).
- Top-Level-Deklarationen: `class`, `interface`, `object`, `enum class`, `annotation class`, `typealias`, `fun` (auch Erweiterungsfunktionen), `val`/`var`. Dazu verschachtelte Klassen und Objekt-Mitglieder (Funktionen und Eigenschaften in `object` und `companion object`), weil Importe auch darauf zeigen (`import a.b.TestHilfen.kennung`).
- Verwendete Namen außerhalb von Kommentaren und Strings: Typ-Bezeichner und einfache Bezeichner, jeweils mit Zeile. Dazu voll qualifizierte Ausdrücke, die mit einem bekannten internen Paket beginnen.
- Zwischenergebnis je Datei als Dataclass. Einzeln testbar, ohne Auflöser.

### 5. Auflöser (`daidalos/aufloeser.py`)

- **Symbolverzeichnis:** voller Name → Liste von Dateien (meist eine). Schlüssel für Top-Level-Deklarationen `paket.Name`, für Verschachteltes `paket.Aussen.Innen` und `paket.Objekt.mitglied`.
- **Importe:** längstes Präfix des Imports, das im Verzeichnis steht. Ein Alias zählt als Name des Ziels. Treffer in genau einer Datei → `sicher: true`. Mehrere Dateien (z. B. gleichnamige Top-Level-Funktion in zwei Dateien eines Pakets) → Kante zu jeder, `sicher: false`. Externe Importe (kein internes Paket) erzeugen keine Kante.
- **Gleiches Paket ohne Import:** Verwendete Namen, die im selben Paket (in irgendeinem Quellsatz desselben Moduls) als Top-Level-Deklaration einer anderen Datei vorkommen und nicht durch einen Import oder eine lokale Deklaration gleichen Namens verdeckt sind. Großgeschriebene Namen (Typen, Objekte) → `sicher: true`, kleingeschriebene (Funktionen, Eigenschaften) → `sicher: false`.
- **Voll qualifiziert:** wie Importe auflösen, `herkunft: voll-qualifiziert`.
- Kanten von einer Datei auf sich selbst entfallen.
- Eine Datei-Kante ist `sicher`, wenn mindestens ein Beleg sicher ist.
- **Verdichtung:** Datei-Kanten zu Paket- und Modul-Kanten (`nutzt`), getrennt nach Rolle. Kanten innerhalb desselben Pakets bzw. Moduls entfallen auf der höheren Ebene.

### 6. JNI (`daidalos/adapter/jni.py`)

- Kotlin: `external fun` mit vollem Namen der umgebenden Klasse bzw. des Objekts.
- C/C++: Funktionsdefinitionen, deren Name mit `Java_` beginnt (tree-sitter-c; für `.cpp` reicht dieselbe Erkennung über den Namen).
- Abgleich über die JNI-Namensregel: `Java_` + Paket mit `_` statt `.` + `_` + Klasse + `_` + Methode, wobei `_` in Namen als `_1` kodiert ist (weitere Escapes `_2`, `_3`, `_0xxxx` beachten). Überladene Varianten mit `__<Signatur>` ebenfalls erkennen.
- Kante `jni` von der Kotlin-Datei zur C-Datei, Gewicht = Zahl der Funktionen, Beleg je Funktion mit beiden Zeilen.
- Ungepaarte Seiten als Befund `jni-ohne-gegenstueck`. Fremdcode ausgenommen.

### 7. Zyklen und Trennstelle (`daidalos/analysen/zyklen.py`)

- Starke Zusammenhangskomponenten mit mindestens zwei Knoten (networkx) auf Datei-, Paket- und Modulebene, jeweils für den Graphen nur aus `produktiv`-Kanten und für den Graphen mit allen Kanten. Auf Modulebene die Gradle-Kanten und die `nutzt`-Kanten getrennt betrachten.
- Nur `nutzt` und `jni` zählen für Datei- und Paket-Zyklen, unsichere Kanten zählen mit, die Befunde vermerken aber, ob eine unsichere Kante beteiligt ist.
- Fremdcode-Knoten werden vorher entfernt.
- **Einstiege:** Mitglieder mit eingehender Kante von außerhalb, samt Quellen.
- **Trennstelle:** die Kante im Zyklus mit dem kleinsten Gewicht, nach deren Entfernen die Komponente nicht mehr stark zusammenhängt. Gleichstand nach Id auflösen. Gibt es keine einzelne solche Kante, `trennstelle: null` und stattdessen `kleinste_trennmenge`, falls die Komponente höchstens 8 Kanten hat (durchprobieren), sonst weglassen.

### 8. CLI und Zusammenfassung

Die Zusammenfassung von `daidalos scan` ergänzen: Module, Pakete, Datei-Kanten (sicher und unsicher), JNI-Paare und Zyklen je Ebene und Rolle.

### 9. Tests

Das Beispielprojekt um die Fälle erweitern, die Sketchorus hat (alles erfunden):
- ein KMP-Modul mit `commonMain.dependencies { api(project(":kern")) }` und einem `commonTest`-Quellsatz,
- eine Wurzel-`build.gradle.kts`, die per `dependencies.add("detektPlugins", project(":regeln"))` in `subprojects { }` ein Regelmodul an alle hängt,
- eine bedingte Abhängigkeit hinter `if (hasProperty("x"))`,
- ein Labor-Modul, dessen Paketwurzel unter der des Kernmoduls liegt (`beispiel.kern.labor` in `:kern-labor`),
- einen Import mit Alias, einen Import auf ein Objekt-Mitglied, eine Top-Level-Funktion, einen Bezug im gleichen Paket ohne Import und einen voll qualifizierten Bezug,
- einen absichtlichen Zyklus aus drei Dateien und einen aus zwei Paketen, je mit einer eindeutigen Trennstelle,
- ein JNI-Paar mit einem `_` im Methodennamen sowie eine `external fun` ohne Gegenstück,
- eine Datei unter `werkzeug/` außerhalb aller Module,
- einen Fremdcode-Ordner, der an einem Zyklus beteiligt wäre, wenn er zählen würde.

Dazu Einzeltests für Gradle-Adapter, Kotlin-Adapter, Auflöser, JNI-Namensregel (mit Escapes) und Zyklen/Trennstelle, und das Golden-File aktualisieren.

### 10. Probe an Sketchorus (nur lokal, eingefrorene Kopie)

`uv run daidalos scan lokal\sketchorus-kopie --konfiguration lokal\sketchorus\daidalos.toml --ausgabe lokal\sketchorus\daidalos.json`, zweimal, byte-gleich.

Gegenproben mit den Zahlen aus A01. Ergebnisse nur als Zahlen in den Bericht:
- **Module und Gradle-Kanten:** genau die Tabelle aus Steckbrief Abschnitt 2 (7 Module, `core-labor → core` als `gradle-api`, alle Module → `detekt-regeln` als `gradle-plugin`, die bedingte Abhängigkeit in `app` ist extern und erzeugt keine Modulkante).
- **Datei-Kanten:** Floorplan fand 1 888 aufgelöste Datei-Importe. Daidalos sollte in derselben Größenordnung liegen. Die Abweichung im Bericht erklären.
- **Plausibilität:** Jede modulübergreifende `nutzt`-Kante muss durch eine Gradle-Kante gedeckt sein (bei Test-Kanten auch durch die Test-Konfiguration). Erwartet sind 0 Verstöße. Jeder Verstoß weist auf einen Auflöser-Fehler hin und wird untersucht. Diese Prüfung ist eine Testhilfe und **kein** Befund in `daidalos.json`, denn die Modulregeln prüft der Build.
- **Zyklen:** Die eigene Auswertung aus A01 fand 11 Datei-Zyklen mit 2 bis 4 Dateien im Floorplan-Graphen (`lokal/floorplan-ausgabe/graph.json`). Vergleiche die Mengen. Jede Abweichung erklären, z. B. zusätzliche Kanten aus gleichem Paket oder JNI.
- **JNI:** 26 Paare erwartet, 0 ungepaarte.
- Laufzeit.

### 11. Kleinigkeiten aus A02

- `.sql` bekommt die Sprache `sql`. Lockfiles bleiben `unbekannt`.
- Optionaler Schlüssel `[projekt] name` in `daidalos.toml`. Fehlt er, bleibt `ziel.name` der Ordnername. Grund: Die eingefrorene Kopie heißt `sketchorus-kopie`, das Original `Sketchorus`, und beide sollen gleich benannt sein können. In die Probe-Konfiguration `name = "Sketchorus"` eintragen.
- Verschachtelte `.gitignore` im Durchlauf ohne Git und Groß-/Kleinschreibung der Muster unter Windows bleiben offen (Etappe 10, Feinschliff). Der Git-Modus ist der Normalfall.

### 12. Abschluss

- Branch `auftrag/a03-modulgraph`, pushen, nicht mergen.
- Bericht `docs/auftraege/A03-bericht.md` (ohne Sketchorus-Inhalte).
- Antwort an mich mit höchstens 10 Zeilen.

## Abnahmekriterien

- [ ] CI grün auf Linux und Windows.
- [ ] `docs/datenformat.md` beschreibt alle neuen Knoten, Kanten, Felder und Befunde.
- [ ] Sketchorus: Modul- und Gradle-Kanten stimmen mit dem Steckbrief überein, 0 Plausibilitäts-Verstöße, 26 JNI-Paare, Zyklen gegen die 11 aus A01 abgeglichen und erklärt, zwei Läufe byte-gleich.
- [ ] Für jeden Zyklus gibt es Einstiege und eine Trennstelle oder eine kleinste Trennmenge.
- [ ] Nichts aus Sketchorus im Repo.

## Nicht in diesem Auftrag

Karte und `render` (A04), Skill (A05), Funktionsebene und Aufrufgraph, Markierungen, detekt-SARIF, ADRs, git-Historie, `#include`-Graph für C.
