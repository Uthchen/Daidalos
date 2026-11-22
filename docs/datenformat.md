# Datenformat

Stand 2026-11-22 (A04). Diese Datei beschreibt `daidalos.json` (Ausgabe des Programms) und
`daidalos.toml` (Konfiguration im Zielrepo). Jede Änderung am Format wird hier nachgetragen;
inkompatible Änderungen erhöhen `schema`.

## `daidalos.json`, `schema: 1`

Ablage: `<zielrepo>/docs/daidalos/daidalos.json`. Die Datei enthält nur Gemessenes, keine Deutungen.

### Aufbau

```json
{
  "befunde": [],
  "daidalos": "0.1.0",
  "kanten": [],
  "knoten": [
    {
      "art": "datei",
      "bytes": 3456,
      "hash": "sha256:9c1e…",
      "id": "datei:core/src/main/kotlin/a/b/Strich.kt",
      "pfad": "core/src/main/kotlin/a/b/Strich.kt",
      "sprache": "kotlin",
      "zeilen": 120
    }
  ],
  "schema": 1,
  "ziel": {
    "git_aenderungen": false,
    "git_commit": "3f2a…",
    "name": "Beispiel"
  }
}
```

| Feld | Bedeutung |
| --- | --- |
| `schema` | Formatversion, derzeit `1` |
| `daidalos` | Version des Programms, das die Datei geschrieben hat |
| `ziel.name` | `[projekt].name` aus `daidalos.toml`, sonst Name des Zielordners (nur der letzte Pfadteil, kein absoluter Pfad) |
| `ziel.git_commit` | HEAD des Zielrepos (volle Länge); `null` ohne Git oder ohne Commit |
| `ziel.git_aenderungen` | ob eine **erfasste** Datei nicht committete Änderungen hat; nicht getrackte, aber erfasste Dateien zählen als Änderung; `null` ohne Git |
| `knoten` | Knoten aller Arten, sortiert nach `id` |
| `kanten` | Kanten, sortiert nach `(von, nach, art, id)` |
| `befunde` | Befunde, sortiert nach `id` |

„Mit Git“ heißt: Das Zielverzeichnis enthält selbst `.git` (Ordner oder Datei) und `git` ist
aufrufbar. Ein Unterordner eines anderen Repos zählt nicht als Git-Repo.

### Id-Schema für alle Knotenarten

Alle späteren Kanten und Befunde verweisen über diese Ids auf Knoten.

| Art | Id | Beispiel |
| --- | --- | --- |
| datei | `datei:<pfad>` | `datei:core/src/main/kotlin/a/b/Strich.kt` |
| modul | `modul:<gradle-pfad>` | `modul::core`, `modul::platform-labor` |
| paket | `paket:<gradle-pfad>/<paketname>` | `paket::core/de.beispiel.zeichnen` |
| paket außerhalb von Modulen | `paket:<ordner-id>/<paketname>` | `paket:ordner:werkzeug/werkzeug` |
| ordner | `ordner:<erster Pfadteil>`, Wurzel `ordner:.` | `ordner:werkzeuge`, `ordner:.` |
| funktion | `funktion:<dateipfad>#<Klasse>.<name>/<stelligkeit>` | `funktion:core/.../Strich.kt#Strich.fuegeHinzu/1` |

- Pfade sind relativ zum Zielrepo und verwenden `/`.
- Pakete tragen den Modulpfad, weil derselbe Paketname in mehreren Modulen vorkommen kann.
- Die Funktions-Id ist vorläufig und wird in Etappe 4 festgezurrt.
- Seit A03 entstehen Knoten der Arten `datei`, `modul`, `paket` und `ordner`.

Kanten und Befunde haben ebenfalls stabile Ids:

| Objekt | Id | Beispiel |
| --- | --- | --- |
| Kante | `kante:<art>:<von>-><nach>[:<rolle>]` | `kante:gradle-api:modul::core-labor->modul::core` |
| Kante mit Rolle | Rolle angehängt bei `nutzt` und `jni` | `kante:nutzt:paket::app/de.a->paket::core/de.b:test` |
| Befund `zyklus` | `befund:zyklus:<ebene>[:<kantenart>]:<rolle>:<hash12>` | `befund:zyklus:datei:produktiv:3fa2c81b0d4e` |
| Befund `unaufgeloest` | `befund:unaufgeloest:<pfad>` | |
| Befund `jni-ohne-gegenstueck` | `befund:jni-ohne-gegenstueck:<pfad>:<name>` | |

`<hash12>` sind die ersten 12 Hex-Zeichen von SHA-256 über die sortierten Mitglieder-Ids, mit
Zeilenumbruch verbunden.

### Datei-Knoten

| Feld | Typ | Bedeutung |
| --- | --- | --- |
| `id` | Text | `datei:<pfad>` |
| `art` | Text | `"datei"` |
| `pfad` | Text | relativ zum Zielrepo, mit `/` |
| `sprache` | Text | siehe Tabelle unten; `"binaer"` bei Binärdateien, sonst `"unbekannt"` |
| `zeilen` | Zahl | Anzahl Zeilen nach Umwandlung von CRLF und CR in LF. Zählung: Anzahl `\n`, plus 1, wenn die Datei nicht mit `\n` endet; leere Datei = 0. **Fehlt** bei Binärdateien, bei Dateien über 5 MiB und bei Lesefehlern |
| `bytes` | Zahl | Größe auf der Platte |
| `hash` | Text | `sha256:<64 Hex-Zeichen>`. Bei Textdateien über den Inhalt **nach** Umwandlung der Zeilenenden, bei Binärdateien über die rohen Bytes. **Fehlt** bei Lesefehlern |
| `fremd` | `true` | nur vorhanden, wenn die Datei auf ein `[scan].fremd`-Muster passt |
| `lesefehler` | `true` | nur vorhanden, wenn die Datei nicht gelesen werden konnte |
| `modul` | Text | Id des Moduls; fehlt außerhalb von Modulen |
| `ordner` | Text | Id des Ordner-Knotens; nur, wenn die Datei zu keinem Modul gehört |
| `quellsatz` | Text | aus `<modul>/src/<quellsatz>/…`, z. B. `commonMain`, `jvmTest`, `main`, `testMessung`; fehlt sonst |
| `rolle` | Text | `test`, wenn der Quellsatz `test` oder `Test` enthält (auch `androidTest`), sonst `produktiv` |
| `paket` | Text | Id des Pakets; nur bei Kotlin-Dateien (`.kt`) mit `package`-Zeile |
| `metriken` | Objekt | Kopplung, siehe [Metriken](#metriken) |

**Modul einer Datei:** der Modulordner mit dem längsten passenden Pfadpräfix (verschachtelte
Module). Paketnamen werden dafür nicht herangezogen.

Binär ist eine Datei, wenn die ersten 8 KiB ein Null-Byte enthalten.

### Sprachen

Volle Dateinamen haben Vorrang vor Endungen; Endungen werden ohne Rücksicht auf Groß- und
Kleinschreibung verglichen.

| Sprache | Dateinamen / Endungen |
| --- | --- |
| `gradle-kotlin` | `build.gradle.kts`, `settings.gradle.kts` |
| `groovy-gradle` | `build.gradle`, `settings.gradle`, `.gradle` |
| `cmake` | `CMakeLists.txt`, `.cmake` |
| `kotlin` | `.kt`, `.kts` |
| `java` | `.java` |
| `c` | `.c` |
| `cpp` | `.cpp .cc .cxx .h .hpp .hh .inl` |
| `csharp` | `.cs` |
| `python` | `.py .pyi` |
| `verse` | `.verse` |
| `markdown` | `.md .markdown` |
| `json` | `.json` |
| `toml` | `.toml` |
| `yaml` | `.yaml .yml` |
| `xml` | `.xml` |
| `ini` | `.ini` |
| `shell` | `.sh .bash` |
| `powershell` | `.ps1 .psm1 .psd1` |
| `batch` | `.bat .cmd` |
| `properties` | `.properties` |
| `text` | `.txt` |
| `sql` | `.sql` |

### Modul-Knoten

Aus `settings.gradle.kts` (`include(...)` mit allen String-Argumenten, einfache
`project(":x").projectDir = file("…")`). Für `settings.gradle` (Groovy) gibt es nur eine grobe
Auswertung der `include`-Zeilen, mit Warnung.

| Feld | Bedeutung |
| --- | --- |
| `id` | `modul:<gradle-pfad>` |
| `art` | `"modul"` |
| `pfad` | Modulordner relativ zum Zielrepo (`:a:b` → `a/b`) |
| `gradle_pfad` | z. B. `:core` |
| `plugins` | aus dem `plugins { }`-Block, sortiert: `alias(libs.plugins.x.y)` → `x.y`, `id("…")` → die Id, `kotlin("jvm")` → `org.jetbrains.kotlin.jvm` |
| `metriken`, `zeilen`, `dateien`, `hash` | siehe [Metriken](#metriken) und [Gruppen-Hash](#gruppen-hash) |

### Paket-Knoten

| Feld | Bedeutung |
| --- | --- |
| `id` | `paket:<gradle-pfad>/<name>` bzw. `paket:<ordner-id>/<name>` |
| `art` | `"paket"` |
| `name` | Paketname, z. B. `de.beispiel.zeichnen` |
| `modul` | Modul-Id; bei Paketen außerhalb von Modulen stattdessen `ordner` |
| `fremd` | `true`, wenn alle Dateien des Pakets fremd sind |
| `metriken`, `zeilen`, `dateien`, `hash` | siehe [Metriken](#metriken) und [Gruppen-Hash](#gruppen-hash) |

### Ordner-Knoten

Für Dateien außerhalb jedes Moduls: `id` `ordner:<erster Pfadteil>`, Dateien direkt im
Wurzelordner unter `ordner:.`. Felder `id`, `art` (`"ordner"`), `pfad` (erster Pfadteil oder `.`),
`fremd` wie bei Paketen sowie `metriken`, `zeilen`, `dateien` und `hash` wie bei Modulen.
Ordner stehen auf der Modulebene neben den Modulen: Ihre Dateien werden wie Moduldateien zu
`nutzt`-Kanten der Modulebene verdichtet.

### Metriken

Seit A04 tragen alle Knoten der Arten `modul`, `paket`, `datei` und `ordner` das Feld `metriken`:

```json
"metriken": { "fan_in": 2, "fan_out": 1, "instabilitaet": 0.333 }
```

| Feld | Bedeutung |
| --- | --- |
| `fan_in` | Zahl der **verschiedenen** Knoten mit einer `nutzt`-Kante der Rolle `produktiv` auf diesen Knoten |
| `fan_out` | Zahl der verschiedenen Knoten, auf die dieser Knoten eine solche Kante hat |
| `instabilitaet` | `fan_out / (fan_in + fan_out)`, auf 3 Nachkommastellen gerundet; `null` bei 0/0 |

Gezählt wird auf derselben Ebene: Datei-Kanten für Dateien, Paket-Kanten für Pakete,
Modul-Kanten (Module und Ordner) für Module und Ordner. Gradle-, `jni`- und Test-Kanten zählen
nicht mit.

Module, Pakete und Ordner tragen zusätzlich:

| Feld | Bedeutung |
| --- | --- |
| `dateien` | Zahl der eigenen, nicht fremden Dateien (Test-Dateien zählen mit) |
| `zeilen` | Summe der `zeilen` dieser Dateien (Dateien ohne `zeilen` zählen 0) |
| `hash` | Gruppen-Hash, siehe unten |

### Gruppen-Hash

`hash` eines Moduls, Pakets oder Ordners ist `sha256:` + SHA-256 (hex) über die Zeilen
`<pfad> <hash>` aller seiner Dateien (auch fremde und Test-Dateien), sortiert und mit `
`
verbunden, UTF-8. Dateien ohne `hash` (Lesefehler) gehen mit leerem Hash ein. Ändert sich eine
Datei, kommt hinzu oder fällt weg, ändert sich der Gruppen-Hash. Die Deutung erkennt daran
veraltete Beschreibungen.

### Kanten

| art | von → nach | Bedeutung |
| --- | --- | --- |
| `gradle-api`, `gradle-impl`, `gradle-test`, `gradle-compileonly`, `gradle-plugin`, `gradle-sonstige` | modul → modul | Projekt-Abhängigkeit aus den Build-Skripten |
| `nutzt` | datei → datei | Kotlin-Bezug (Import, gleiches Paket, voll qualifiziert) |
| `nutzt` | paket → paket, modul/ordner → modul/ordner | Verdichtung der Datei-Kanten, getrennt nach Rolle |
| `jni` | datei (Kotlin) → datei (C/C++) | `external fun` zu `Java_…` |
| `enthaelt` | modul/ordner → paket, paket → datei, modul/ordner → datei | Hierarchie |

| Feld | bei | Bedeutung |
| --- | --- | --- |
| `id`, `art`, `von`, `nach` | allen | |
| `gewicht` | `nutzt` (Datei) | Zahl der verschiedenen genutzten Symbole |
| | `nutzt` (verdichtet) | Summe der Gewichte der Datei-Kanten |
| | `jni` | Zahl der Funktionspaare |
| | `gradle-*` | Zahl der Belege |
| `dateikanten` | `nutzt` (verdichtet) | Zahl der zugrunde liegenden Datei-Kanten |
| `rolle` | `nutzt`, `jni`, `gradle-*` | `produktiv` oder `test` nach der Rolle der Quelldatei; bei Gradle `test` genau für `gradle-test` |
| `sicher` | `nutzt`, `jni`, `gradle-*` | `true`, wenn mindestens ein Beleg sicher ist |
| `beleg` | `nutzt` (Datei), `jni`, `gradle-*` | Liste, siehe unten |

`enthaelt`-Kanten tragen nur `id`, `art`, `von`, `nach`.

**Beleg einer `nutzt`-Datei-Kante**, sortiert nach Zeile, Symbol, Herkunft:
`{ "herkunft": "import" | "gleiches-paket" | "voll-qualifiziert", "sicher": true, "symbol": "de.a.Satz", "zeile": 3 }`.
`symbol` ist der volle Name des Ziels (`paket.Name`, `paket.Aussen.Innen`, `paket.Objekt.mitglied`).

**Beleg einer Gradle-Kante:** `{ "bedingt": false, "datei": "core-labor/build.gradle.kts",
"konfiguration": "api", "quellsatz": "commonMain", "zeile": 12 }`; bei Abhängigkeiten aus
`subprojects { }`/`allprojects { }` im Wurzel-Build zusätzlich `"quelle": "wurzel"`.
`quellsatz` ist `null`, wenn der Aufruf in keinem Quellsatz-Block steht.

**Beleg einer `jni`-Kante:** `{ "funktion": "de.a.Insel.rechne", "zeile_c": 40, "zeile_kotlin": 12 }`.

#### Regeln für Gradle-Kanten

- Jeder Aufruf `<konfiguration>(project(":x"))`, auch umhüllt von `platform(…)`,
  `enforcedPlatform(…)` oder `testFixtures(…)`, und `dependencies.add("<konfiguration>", project(":x"))`.
  Nicht erfasst: `dependsOn`, `evaluationDependsOn` und andere Task-Bezüge.
- Art: Konfiguration oder Quellsatz mit `test`/`Test` → `gradle-test`; `api` → `gradle-api`;
  `implementation` → `gradle-impl`; `compileOnly` → `gradle-compileonly`; `detektPlugins` →
  `gradle-plugin`; sonst `gradle-sonstige`.
- Quellsatz aus `X.dependencies { }`, `val X by getting { }`, `getByName("X") { }` oder
  `sourceSets { X { dependencies { } } }`.
- `bedingt: true`, wenn der Aufruf in `if`/`when` oder in einem Lambda steht, das keiner der Blöcke
  `dependencies`, `sourceSets`, `kotlin`, `android`, `subprojects`, `allprojects`, `configure`,
  `withType`, `getting`, `creating`, `getByName`, `named`, `maybeCreate` oder ein Quellsatz ist.
- Wurzel-Build: Aufrufe in `subprojects { }`/`allprojects { }` gelten für jedes Modul außer dem Ziel
  selbst. Andere Aufrufe im Wurzel-Build entfallen, denn die Wurzel ist kein Modul.
- Ist das Ziel kein bekanntes Modul: Warnung, keine Kante. Kanten eines Moduls auf sich selbst
  entfallen.

#### Regeln für `nutzt`

- **Importe:** längstes Präfix des Imports, das im Symbolverzeichnis steht. Genau eine Zieldatei →
  sicher; mehrere → Kante zu jeder, unsicher. Ein Alias zählt als Name des Ziels. Externe Importe
  ergeben keine Kante.
- **Stern-Importe** eines bekannten Pakets: verwendete Namen werden gegen dessen oberste Ebene
  aufgelöst, Herkunft `import`, Sicherheit wie beim gleichen Paket.
- **Gleiches Paket ohne Import:** verwendete Namen, die im selben Paket desselben Moduls (beliebiger
  Quellsatz) auf oberster Ebene einer anderen Datei deklariert und nicht durch einen Import oder
  eine eigene Deklaration verdeckt sind. Großgeschrieben → sicher, kleingeschrieben → unsicher.
  Namen hinter einem Punkt (`x.name()`) werden gegen Erweiterungsfunktionen und -eigenschaften im
  gleichen Paket aufgelöst, immer unsicher.
- **Voll qualifiziert:** punktierte Ausdrücke, die mit einem internen Präfix beginnen, wie Importe.
- Produktiver Code sieht keinen Testcode: Ziele mit Rolle `test` entfallen für produktive
  Quelldateien (bei Importen nur, wenn es ein produktives Ziel gibt).
- Kommentare und String-Inhalte zählen nicht, Interpolationen schon.
- Kanten einer Datei auf sich selbst entfallen. Verdichtete Kanten innerhalb desselben Pakets bzw.
  Moduls entfallen.
- **Interne Präfixe** sind die ersten zwei Teile jedes gefundenen Pakets (z. B. `de.beispiel`).
- Wo die Kotlin-Grammatik eine Deklaration der obersten Ebene nicht erkennt (z. B. Annotationen auf
  eigenen Zeilen vor `annotation class`, Parse-Fehler), werden Zeilen ohne Einrückung im
  betroffenen Abschnitt über ein Textmuster als Deklaration erkannt.

#### Regeln für `jni`

Kotlin: `external fun` mit dem JVM-Namen der umgebenden Klasse (innere Klassen mit `$`, Companion
als `Klasse$Companion`, oberste Ebene als `<Datei>Kt` bzw. `@file:JvmName`). C/C++:
Funktionsdefinitionen (keine Deklarationen) mit Namen `Java_…`, gelesen mit tree-sitter-c.
Abgleich über die JNI-Namensregel mit den Escapes `_1`, `_2`, `_3`, `_0xxxx`; überladene Namen mit
`__<Signatur>` werden erkannt, die Signatur zählt für den Abgleich nicht.

### Befunde

| Feld | Bedeutung |
| --- | --- |
| `id` | siehe Id-Schema |
| `quelle` | `"daidalos"` |
| `regel` | `zyklus`, `jni-ohne-gegenstueck`, `unaufgeloest` |
| `schwere` | `warnung` (Zyklus) oder `hinweis` |
| `knoten` | betroffene Knoten-Ids, sortiert |
| `beleg` | je Regel, siehe unten |

Für Fremdcode werden keine Befunde gemeldet.

**Zyklen „mit Tests“ nur, wenn neu (seit A04):** Ein Zyklus-Befund mit Rolle `mit-tests` entfällt,
wenn es auf derselben Ebene (und Modulebene: derselben `kantenart`) einen produktiven Zyklus mit
genau derselben Mitgliedermenge gibt. Enthält ein Test-Zyklus produktive Zyklen (ihre Mitglieder
sind Teilmengen), bleibt er erhalten und bekommt im Beleg `enthaelt_produktiv` mit deren
Befund-Ids, sortiert.

**`zyklus`:** starke Zusammenhangskomponenten mit mindestens zwei Knoten, je Ebene `datei`, `paket`,
`modul` und Rolle `produktiv` (nur produktive Kanten) bzw. `mit-tests` (alle Kanten). Datei- und
Paketebene: Kanten `nutzt` und `jni`. Modulebene: `nutzt` und Gradle getrennt (`kantenart`
`nutzt` bzw. `gradle`). Unsichere Kanten zählen mit. Fremde Knoten (Dateien, sowie Pakete und
Ordner aus lauter Fremdcode) werden vorher entfernt.

| Feld im Beleg | Bedeutung |
| --- | --- |
| `ebene`, `rolle`, `kantenart` | wie oben; `kantenart` nur auf Modulebene |
| `knoten` | Mitglieder, sortiert |
| `kanten` | Ids der Kanten innerhalb der Komponente, sortiert |
| `einstiege` | `[{ "knoten": …, "quellen": [ … ] }]`: Mitglieder mit eingehender Kante von außerhalb |
| `trennstelle` | Kante mit dem kleinsten Gewicht (Gleichstand: Id), nach deren Entfernen die Komponente nicht mehr stark zusammenhängt; sonst `null` |
| `kleinste_trennmenge` | nur bei `trennstelle: null` und höchstens 8 Kanten: kleinste Kantenmenge (dann kleinstes Gesamtgewicht, dann Ids) mit derselben Wirkung |
| `unsicher` | ob eine unsichere Kante beteiligt ist |
| `enthaelt_produktiv` | nur bei Rolle `mit-tests`: Ids der produktiven Zyklen, die in diesem aufgehen |

**`jni-ohne-gegenstueck`:** `{ "funktion": …, "seite": "kotlin" | "c", "zeile": … }`; `funktion`
ist bei Kotlin der volle Name `paket.Klasse.methode`, bei C der `Java_…`-Name.

**`unaufgeloest`:** je Datei `{ "importe": [ { "import": …, "zeile": … } ] }` für Importe mit
internem Präfix, die nicht aufgelöst werden konnten.

### Determinismus

Gleicher Stand des Zielrepos ergibt eine byte-gleiche Datei: UTF-8 ohne BOM, Zeilenende LF,
Einrückung 2, Schlüssel sortiert, abschließender Zeilenumbruch. Keine Zeitstempel, keine absoluten
Pfade, keine Rechnernamen. Die Laufzeit erscheint nur auf stdout.

## `daidalos.toml`, Format v1

Optional, im Wurzelordner des Zielrepos; mit `--konfiguration` auch von anderswo.

```toml
[projekt]
# Anzeigename für ziel.name; ohne Angabe der Ordnername
name = "Beispiel"

[scan]
# gitwildmatch-Muster wie in .gitignore, relativ zum Zielrepo
ausschliessen = [".claude/worktrees/", "build/", "docs/prototypen/daten/"]

# Fremdcode (eingebundene Bibliotheken): wird erfasst, aber als fremd markiert
fremd = ["**/src/main/cpp/fremd/"]

[editor]
befehl = "code -g {datei}:{zeile}"
```

| Schlüssel | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `[projekt].name` | nicht leerer Text | Ordnername | Name in `ziel.name` |
| `[scan].ausschliessen` | Liste von Texten | `[]` | zusätzliche Ausschlüsse |
| `[scan].fremd` | Liste von Texten | `[]` | Dateien werden erfasst und bekommen `"fremd": true` |
| `[editor].befehl` | Text | `code -g {datei}:{zeile}` | wird erst später benutzt |

- Unbekannte Abschnitte und Schlüssel: Warnung auf stderr, kein Abbruch.
- Falsche Typen oder ungültiges TOML: Fehlermeldung mit Dateiname und Schlüssel, Exit-Code 2.

### Welche Dateien erfasst werden

1. **Mit Git:** `git -c core.quotepath=off ls-files --cached --others --exclude-standard -z`.
   `.gitignore` gilt damit genau wie bei Git. Einträge mit abschließendem `/` (verschachtelte Repos,
   Worktrees) und nicht mehr vorhandene Dateien werden übersprungen. Ist `git` nicht aufrufbar oder
   scheitert der Aufruf: Warnung und Rückfall auf den Durchlauf.
2. **Ohne Git:** Durchlauf des Verzeichnisses. Beachtet wird die `.gitignore` im Wurzelordner.
   Ausgeschlossene Ordner und Ordner mit eigenem `.git` werden gar nicht erst betreten.
3. Danach werden die eingebauten Ausschlüsse und `[scan].ausschliessen` angewendet (gitwildmatch).
4. Symlinks werden nicht verfolgt und nicht erfasst.

Eingebaute Ausschlüsse, die immer gelten: `.git/`, `.gradle/`, `.idea/`, `.vscode/`, `.kotlin/`,
`node_modules/`, `__pycache__/`, `build/`, `out/`, `Binaries/`, `Intermediate/`, `Saved/`,
`DerivedDataCache/` (in jeder Tiefe) und `/docs/daidalos/` (nur im Wurzelordner).
