# Datenformat

Stand 2026-11-23 (A09). Diese Datei beschreibt `daidalos.json` (Ausgabe des Programms),
`deutung.json` (Ausgabe des Skills, vom Programm nur gelesen) und `daidalos.toml` (Konfiguration im
Zielrepo). Jede Änderung am Format wird hier nachgetragen;
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
| `ziel.detekt` | seit A08, nur mit `[detekt].sarif`: `{ "dateien": n, "ergebnisse": m }`, `n` = gültig gelesene SARIF-Dateien (auch leere), `m` = alle Ergebnisse darin (auch verworfene, vor dem Zusammenführen). Keine Zeitstempel, kein Dateialter |
| `knoten` | Knoten aller Arten, sortiert nach `id` |
| `kanten` | Kanten, sortiert nach `(von, nach, art, id)`; bei `ruft` gilt die abgeleitete Id |
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
| funktion | `funktion:<dateipfad>#<Behälter>.<name>/<stelligkeit>` | `funktion:core/.../Strich.kt#Strich.fuegeHinzu/1` |

- Pfade sind relativ zum Zielrepo und verwenden `/`.
- Pakete tragen den Modulpfad, weil derselbe Paketname in mehreren Modulen vorkommen kann.
- Seit A03 entstehen Knoten der Arten `datei`, `modul`, `paket` und `ordner`, seit A07 `funktion`.

**Funktions-Id (seit A07 endgültig):**

| Fall | Form | Beispiel |
| --- | --- | --- |
| Grundform | `funktion:<dateipfad>#<Behälter>.<name>/<stelligkeit>` | `…/Strich.kt#Strich.setze/1` |
| Behälter | Klassenkette relativ zur Datei (`Aussen.Innen`, `Klasse.Companion` bzw. der Name eines benannten Companion, `Enum.EINTRAG` bei Einträgen mit Körper); oberste Ebene leer | `…/Werkzeug.kt#fakultaet/1` |
| Konstruktoren | `<init>` | `…/Strich.kt#Strich.<init>/1` |
| Accessoren | `<get-feld>` bzw. `<set-feld>` | `…/Strich.kt#Strich.<get-laenge>/0` |
| Erweiterungsfunktionen | Empfängertyp wie geschrieben (ohne Leerzeichen) in eckigen Klammern vor dem Namen | `…#[Strich]laenge/0`, `…#Hilfen.[Strich]laenge/0` |
| Stelligkeit | Zahl der Parameter; der Empfänger zählt nicht, ein `vararg` zählt als 1 | |
| gleiche Stelligkeit | an **alle** betroffenen Ids die Parametertypen wie geschrieben, ohne Leerzeichen; fehlt ein Typ: `?` | `…#Strich.setze/2(Int,Float)`, `…#Strich.setze/2(Punkt,Float)` |
| danach noch gleich | zusätzlich `@<zeile_von>` | `…#f/1(Int)@12` |
| C (JNI) | Behälter leer, Name der C-Funktion, Stelligkeit = Zahl der C-Parameter | `…/insel.c#Java_de_a_Insel_rechne/3` |

Kanten und Befunde haben ebenfalls stabile Ids:

| Objekt | Id | Beispiel |
| --- | --- | --- |
| Kante | `kante:<art>:<von>-><nach>[:<rolle>]` | `kante:gradle-api:modul::core-labor->modul::core` |
| Kante mit Rolle | Rolle angehängt bei `nutzt`, `jni` und `ruft` | `kante:nutzt:paket::app/de.a->paket::core/de.b:test` |
| Kante `ruft` (seit A08 nicht gespeichert) | `kante:ruft:<von>-><nach>:<rolle>`; jeder Leser bildet sie selbst (`daidalos.ids.kanten_id`) | |
| Befund `zyklus` | `befund:zyklus:<ebene>[:<kantenart>]:<rolle>:<hash12>` | `befund:zyklus:datei:produktiv:3fa2c81b0d4e` |
| Befund `unaufgeloest` (Importe) | `befund:unaufgeloest:<pfad>` | |
| Befund `unaufgeloest` (Aufrufe, seit A07) | `befund:unaufgeloest:aufruf:<pfad>` | |
| Befund `jni-ohne-gegenstueck` | `befund:jni-ohne-gegenstueck:<pfad>:<name>` | |
| Befund `markierung-verlassen` (seit A08) | `befund:markierung:<von-id>-><nach-id>` | |
| Befund aus detekt (seit A08) | `befund:detekt:<regel>:<pfad>:<zeile>` | `befund:detekt:detekt.style.MagicNumber:core/…/A.kt:12` |

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
| `funktionen` | Zahl | seit A07: Zahl der Funktionsknoten der Datei (auch implizite Konstruktoren); bei Kotlin-Dateien und C/C++-Dateien mit `Java_…`-Funktionen |
| `klassen` | Liste | seit A07, nur Kotlin, siehe [Klassen](#klassen) |
| `annotationen` | Liste | seit A07, nur Kotlin: `@file:`-Annotationen, siehe [Annotationen](#annotationen) |
| `eigenschaften` | Liste | seit A07b, nur Kotlin: Eigenschaften der obersten Ebene, Aufbau wie bei [Klassen](#klassen) |

**Modul einer Datei:** der Modulordner mit dem längsten passenden Pfadpräfix (verschachtelte
Module). Paketnamen werden dafür nicht herangezogen.

Binär ist eine Datei, wenn die ersten 8 KiB ein Null-Byte enthalten.

### Sprachen

Volle Dateinamen haben Vorrang vor Endungen, die mehrteilige Endung `.gradle.kts` hat Vorrang vor
`.kts`; Endungen werden ohne Rücksicht auf Groß- und Kleinschreibung verglichen.

| Sprache | Dateinamen / Endungen |
| --- | --- |
| `gradle-kotlin` | `.gradle.kts` (seit A05b jede solche Datei, z. B. auch `gradle/x.gradle.kts`; vorher nur `build.gradle.kts` und `settings.gradle.kts`) |
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
`<pfad> <hash>` aller seiner Dateien (auch fremde und Test-Dateien), sortiert und mit `\n`
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
| `enthaelt` | modul/ordner → paket, paket → datei, modul/ordner → datei | Hierarchie; seit A07b **keine** Kante datei → funktion, die Datei steht seit A08 in der Id des Funktionsknotens |
| `ruft` | funktion → funktion | Aufruf, seit A07; siehe [Funktionsebene](#funktionsebene-seit-a07) |
| `ueberschreibt` | funktion → funktion | `override fun` → Funktion im internen Obertyp, seit A07 |
| `actual` | funktion → funktion | `actual fun` → `expect fun`, seit A07 |
| `jni` | funktion (Kotlin) → funktion (C) | seit A07 zusätzlich auf Funktionsebene |

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
| `quelle` | `"daidalos"`; seit A08 `"detekt"` für Ergebnisse aus SARIF |
| `regel` | `zyklus`, `jni-ohne-gegenstueck`, `unaufgeloest`, seit A08 `markierung-verlassen`; bei `quelle: detekt` die `ruleId` |
| `schwere` | `warnung` (Zyklus, sichere Grenzkante) oder `hinweis`; bei detekt auch `fehler` |
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
| `loesende_kanten` | seit A05: Ids aller Kanten der Komponente, deren Wegfall allein sie zerfallen lässt (nicht mehr stark zusammenhängend), nach Id sortiert; leer, wenn keine einzelne Kante genügt |
| `trennstelle` | die Kante aus `loesende_kanten` mit dem kleinsten Gewicht (Gleichstand: Id); sonst `null` |
| `kleinste_trennmenge` | nur bei `trennstelle: null` und höchstens 8 Kanten: kleinste Kantenmenge (dann kleinstes Gesamtgewicht, dann Ids) mit derselben Wirkung |
| `unsicher` | ob eine unsichere Kante beteiligt ist |
| `enthaelt_produktiv` | nur bei Rolle `mit-tests`: Ids der produktiven Zyklen, die in diesem aufgehen |

**`jni-ohne-gegenstueck`:** `{ "funktion": …, "seite": "kotlin" | "c", "zeile": … }`; `funktion`
ist bei Kotlin der volle Name `paket.Klasse.methode`, bei C der `Java_…`-Name.

**`unaufgeloest`:** je Datei `{ "importe": [ { "import": …, "zeile": … } ] }` für Importe mit
internem Präfix, die nicht aufgelöst werden konnten.

**`unaufgeloest` der Art `aufruf` (seit A07):** je Datei mit unaufgelösten Aufrufen
`{ "art": "aufruf", "anzahl": n, "namen": [ { "name", "grund", "anzahl" } ] }`, die zehn häufigsten
Namen (nach Anzahl absteigend, dann Name). Kein Problem des Zielcodes, sondern ein Maß für die
Abdeckung: nicht in Karte, `KARTE.md` und Befundliste der Zusammenfassung, braucht keine
Einschätzung und macht eine Datei nicht wichtig. Die Zusammenfassung zeigt ihn unter „Messung“.

### Funktionsebene (seit A07)

Nur Kotlin (`.kt`) und die C-Seite von JNI. Karte, `KARTE.md`, Zusammenfassung und der Abgleich
der Deutung arbeiten auf der **Strukturansicht**: der Messung ohne Funktionsknoten, ohne Kanten von
oder zu Funktionen, ohne Abdeckungsbefunde (`unaufgeloest` der Art `aufruf`) und ohne die
Datei-Felder `funktionen`, `klassen`, `annotationen` und `eigenschaften`. Für Messungen ohne
Funktionsebene ist sie gleich der Messung.

**Endgültig seit A09.** Die Funktionsebene (Funktionsknoten, `ruft`, `ueberschreibt`, `actual`,
`jni` auf Funktionsebene, die Datei-Felder `funktionen`, `klassen`, `annotationen`,
`eigenschaften` und der Abdeckungsbefund) war von A07 bis A09 vorläufig und durfte sich ohne
höheres `schema` ändern. Seit A09 gilt für sie wie für alles andere Leitplanke 6: Jede Änderung
steht hier, inkompatible Änderungen erhöhen `schema`. A09 hat `daidalos.json` nicht geändert; die
Liste unten hält fest, was sich in der vorläufigen Zeit geändert hat.

Änderungen in A08 (inkompatibel zu A07b):

- `ruft`-Kanten tragen keine `id` mehr; sie lautet `kante:ruft:<von>-><nach>:<rolle>`;
- Funktionsknoten tragen kein `datei` mehr; die Datei ist der Teil der Id vor `#` ohne
  `funktion:` (auch bei C-Knoten);
- neue Felder `ohne_koerper`, `markiert`, `ausnahme` und `metriken.delegiert_gelesen` (siehe
  [Markierungs-Kette](#markierungs-kette-seit-a08)).

Änderungen in A07b (inkompatibel zu A07):

- keine `enthaelt`-Kante Datei → Funktion mehr;
- `beleg` von `ruft` je (Herkunft, sicher, Grund) zusammengefasst, mit `zeilen` statt `zeile`;
- `parameter` nur noch als Liste der Typen, dazu `parameter_vorgabe` und `parameter_vararg`;
- leere Listen und `false` entfallen bei Funktionsknoten (Standardwerte in der Feldtabelle);
- neue Herkünfte `rueckgabe`, `konstruktor-ergebnis`, `initialisierer`, `cast`, `lesen`,
  `schreiben`; neues Feld `eigenschaften` an Klassen und Dateien.

#### Welche Funktionen Knoten werden

- jede `fun` auf oberster Ebene, in Klassen, Objekten, `companion object`, Schnittstellen und
  `enum`-Einträgen mit Körper, auch ohne Körper (abstrakt, Schnittstelle, `expect`, `external`);
- der primäre Konstruktor (`<init>`), sobald die Klasse (auch ein Objekt) `init`-Blöcke oder
  Initialisierer von Eigenschaften (auch `by`-Delegaten) mit Aufrufen hat. Seine Aufrufe stammen aus
  diesen Teilen, aus Vorgabewerten der Klassenparameter und aus dem Aufruf des
  Oberklassen-Konstruktors (`: Basis(…)`). Seine Zeilen reichen vom Klassenkopf bis zum letzten Teil.
  Seit A07b auch, wenn diese Teile keine Aufrufe, aber Zugriffe haben und mindestens ein Zugriff eine
  Kante ergibt oder ein Aufruf den Konstruktor trifft (dann ohne Oberklassen-Aufruf und Vorgabewerte);
- jeder sekundäre Konstruktor; `this(…)` und `super(…)` gelten als Aufruf eines Konstruktors;
- `get()`/`set()` mit Körper;
- **implizite Konstruktoren** (`implizit: true`): nur wenn ein Aufruf `Klasse(…)` eine Klasse ohne
  Konstruktorknoten trifft. Parameter aus dem primären Konstruktor, ohne `hash`, `zeile_von` =
  `zeile_bis` = Zeile der Klasse;
- C: jede Funktionsdefinition `Java_…` (wie bei `jni`).

Lokale Funktionen, Lambdas, anonyme Objekte und lokale Klassen gehören zur umgebenden Funktion.
Aufrufe in Initialisierern von Eigenschaften der obersten Ebene gehören zu keiner Funktion und werden
nicht gezählt.

#### Felder eines Funktionsknotens

Seit A07b **entfallen leere Listen und `false`** bei Funktionsknoten (nur dort). Ein fehlendes Feld
hat den Standardwert aus der Spalte „fehlt →“; „nie“ heißt, das Feld steht immer da.

| Feld | fehlt → | Bedeutung |
| --- | --- | --- |
| `id`, `art` (`"funktion"`) | nie | siehe Id-Schema |
| `sprache` | nie | `kotlin` oder `c` |
| `zeile_von`, `zeile_bis` | nie | erste (mit Annotationen und Modifikatoren) und letzte Zeile |
| `name`, `behaelter`, `stelligkeit` | nie | wie in der Id; `behaelter` auf oberster Ebene `""` |
| `sichtbarkeit` | nie | `public`, `internal`, `protected`, `private` (ohne Angabe `public`) |
| `modifikatoren` | `[]` | sortiert, aus `abstract`, `actual`, `expect`, `external`, `infix`, `inline`, `open`, `operator`, `override`, `suspend` |
| `erweiterung` | nie | Empfängertyp wie geschrieben oder `null` |
| `parameter` | `[]` | Typen der Parameter in Reihenfolge, wie geschrieben ohne Leerzeichen; `null` ohne Angabe (Setter). Parameternamen stehen nicht in der Messung |
| `parameter_vorgabe` | `[]` | Indizes (ab 0) der Parameter mit Vorgabewert, aufsteigend |
| `parameter_vararg` | `[]` | Index des `vararg`-Parameters |
| `rolle` | nie | wie bei der Datei |
| `quellsatz` | kein Quellsatz | wie bei der Datei |
| `annotationen` | `[]` | siehe [Annotationen](#annotationen); bei C immer leer |
| `metriken` | nie | siehe [Metriken je Funktion](#metriken-je-funktion) |
| `hash` | implizit | `sha256:` über den Text der Funktion nach CRLF→LF; beim primären Konstruktor über seine Teile, mit Zeilenumbruch verbunden; fehlt nur bei impliziten Konstruktoren |
| `implizit` | `false` | `true` bei impliziten Konstruktoren |
| `ohne_koerper` | `false` | seit A08: `true` bei `fun` ohne Körper (abstrakt, Schnittstelle, `expect`, `external`) |
| `markiert` | `false` | seit A08: siehe [Markierungs-Kette](#markierungs-kette-seit-a08) |
| `ausnahme` | `false` | seit A08: ebenda |

Die Datei einer Funktion ist der Teil der Id vor `#` ohne `funktion:` (seit A08 kein Feld `datei`).

#### Klassen

Je Kotlin-Datei `klassen`: `{ "name", "art", "zeile", "annotationen", "eigenschaften",
"obertypen" }`, sortiert nach `name`. `name` ist die Kette relativ zur Datei. `art` ist `klasse`, `schnittstelle`, `objekt`,
`companion`, `enum`, `annotation` oder `enum-eintrag` (nur Einträge mit Körper). `obertypen`:
`[{ "name": wie geschrieben ohne Typargumente, "voll": voller Name oder null }]`. `voll` ist
gesetzt, wenn der Name intern oder über einen expliziten Import aufgelöst wird.

`eigenschaften` (seit A07b): `[{ "delegiert": bool, "name", "zeile" }]` nach Zeile, dann Name: die
Eigenschaften im Klassenkörper (ohne Erweiterungseigenschaften) und die `val`/`var`-Parameter des
primären Konstruktors. `delegiert` ist `true` bei `by …` (etwa `by lazy`, `by mutableStateOf`);
solche Eigenschaften haben keinen Accessor-Knoten und ergeben keine Kante. Das Datei-Feld
`eigenschaften` listet ebenso die Eigenschaften der obersten Ebene. Hier entfallen leere Listen und
`false` nicht.

#### Annotationen

An Funktionen, Klassen und Dateien (`@file:`) als sortierte Liste `{ "name", "sicher" }`. Der Name
wird aufgelöst über Import und Alias, die eigene Datei, das gleiche Paket desselben Moduls und
Stern-Importe interner Pakete; voll qualifiziert Geschriebenes gilt als aufgelöst. Sonst bleibt der
Name wie geschrieben, mit `"sicher": false` (etwa `Suppress` oder `JvmName` ohne Import).
Ziel-Präfixe wie `@get:` und Argumente fallen weg. Annotationen auf eigener Zeile, die die Grammatik
als eigenen Knoten liest (`@A("x")` nach einer Ausdrucksfunktion), gehören zur nächsten Deklaration.
Es gibt keine Sonderregeln für bestimmte Namen; was als Markierung gilt, entscheidet A08.

#### Regeln für `ruft`

Ausgewertet wird jeder Aufruf in einem Funktionskörper, in Vorgabewerten von Parametern, Lambdas,
lokalen Funktionen und anonymen Objekten: `f(…)`, `x.f(…)`, `x?.f(…)`, `Klasse(…)`, `super.f(…)`,
`this.f(…)`, `this@A.f(…)` und Funktionsreferenzen `::f`, `X::f` (Herkunft `referenz`, jede
Stelligkeit passt). Kommentare und String-Inhalte zählen nicht, Interpolationen schon. Gezählt wird
die Zahl der Argumente; ein nachgestelltes Lambda zählt mit.

**Sichtbarkeit der Ziele:** Produktiver Code sieht keinen Testcode. Im selben Modul sieht ein
Quellsatz sich selbst und `commonMain`, ein Test-Quellsatz zusätzlich `commonTest`, `main` und seinen
`…Main`-Partner (`jvmTest` → `jvmMain`). Zwischen Modulen gilt nur, wovon das aufrufende Modul laut
Gradle abhängt (jede Gradle-Kante, transitiv); Ordner außerhalb von Modulen sehen alles. `private`
Funktionen anderer Dateien sind unsichtbar.

Auflösung; es gilt der erste Schritt, der greift:

1. **Empfänger mit bekanntem Typ:** `this` (auch implizit, mit äußeren Klassen und dem
   Erweiterungsempfänger), Parameter mit Typangabe, Eigenschaften mit Typangabe oder Initialisierer
   `= Klasse(…)` (der Klasse, ihrer Obertypen, der obersten Ebene), lokale `val`/`var` mit
   Typangabe oder `= Klasse(…)` (nur wenn vor dem Aufruf in einem umgebenden Block deklariert),
   Objekt-, Companion-, Klassen- und Enum-Namen sowie Ketten aus solchen **Eigenschaften**
   (`a.b.f()`, `Klasse.Companion.f()`, `Enum.EINTRAG.f()`; `Enum.entries` ist extern).
   Typparameter gelten als ihre Schranke. Seit A07b zusätzlich **Typen durch Nachschlagen**
   (siehe unten). Keine Smart-Casts. Gesucht wird in der Klasse und ihren
   internen Obertypen (Breite zuerst, überschriebene nur einmal), bei Klassennamen im Objekt bzw. im
   Companion. Gibt es eine Klasse unter dem vollen Namen mehrfach, sind alle Kanten unsicher
   (`unbekannter-empfaenger`); eine `expect`- und ihre `actual`-Klasse zählen als eine.
2. **Ohne Empfänger:** Mitglieder der impliziten Empfänger von innen nach außen (Lambdas von
   `apply`, `run` und `with`, Erweiterungsempfänger, anonyme Objekte, umgebende Klassen mit ihrem
   Companion). Eine gleichnamige Eigenschaft dort macht den Aufruf zum Aufruf eines Werts (keine
   Kante). Danach Erweiterungen, deren Empfänger ein impliziter Empfänger ist; dann dieselbe Datei auf
   oberster Ebene, Importe und Aliase, das gleiche Paket desselben Moduls und Stern-Importe interner
   Pakete. Lokale Funktionen und Funktionen anonymer Objekte gehören zur Funktion selbst (keine
   Kante), ebenso der Aufruf eines lokalen Werts oder Parameters (`aktion()`).
3. **Konstruktor:** `Name(…)`, wenn `Name` als Klasse aufgelöst wird. Ziel ist `<init>` mit passender
   Stelligkeit, sonst der implizite Konstruktor.
4. **Überladung:** Ein Kandidat passt, wenn Pflichtparameter ≤ Argumente ≤ Parameter gilt (mit
   `vararg` ohne Obergrenze). Genau einer: sicher. Mehrere: unsichere Kante zu jedem
   (`ueberladung`). `expect` und `actual` gleichen Namens zählen als einer; es gilt das `actual`, wenn
   es sichtbar ist.
5. **Erweiterungen** bei bekanntem Empfängertyp, wenn kein Mitglied passt: sichtbare Erweiterungen
   (eigene Datei, Import, gleiches Paket, Stern-Import) mit passender Stelligkeit. Sicher, wenn genau
   eine zum Typ oder einem internen Obertyp passt (bei externen Typen: gleicher einfacher Name);
   sonst unsicher (`erweiterung`) zu allen sichtbaren. Passt keine und hat der interne Typ nur
   interne Obertypen, ist der Aufruf extern.
6. **Empfänger mit unbekanntem Typ:** unsichere Kanten (`unbekannter-empfaenger`) zu allen sichtbaren
   Mitgliedern und Erweiterungen dieses Namens mit passender Stelligkeit, wenn es höchstens 5 sind;
   bei mehr `unaufgeloest` mit Grund `zu-viele-kandidaten`; bei keinem extern.
7. **Extern:** bekannter externer Empfängertyp ohne passende Erweiterung, oder ohne Empfänger intern
   nicht gefunden. Keine Kante, nur `metriken.externe_aufrufe`.

**Typen durch Nachschlagen (seit A07b).** Nur Typen, die ausdrücklich im Code stehen:

- **Rückgabetyp** (Herkunft `rueckgabe`): `f().g()`, `a.b().c()`, wenn der innere Aufruf genau
  ein sicheres Ziel hat und dieses einen ausgeschriebenen Rückgabetyp hat (Typparameter gelten als
  Schranke). Eine Ausdrucksfunktion ohne Rückgabetyp (`fun f() = …`) zählt nur, wenn ihr Ausdruck
  ein Konstruktoraufruf ist. Rückgabetypen externer Funktionen bleiben unbekannt.
- **Konstruktor-Ergebnis** (`konstruktor-ergebnis`): `Klasse(…).f()`. Die Klasse steht auch fest,
  wenn nur die Überladung des Konstruktors offen ist (Grund `ueberladung`). Ein externer
  großgeschriebener Aufruf ohne Empfänger gilt als externer Typ (wie `val x = Klasse()` in A07).
- **Initialisierer** (`initialisierer`): `val x = y`, `val p = feld`, `val k = liefere()` und
  Ketten wie `val i = a.b` übernehmen den Typ der rechten Seite, wenn er nach diesen Regeln oder
  denen aus A07 bekannt ist; für lokale Werte und Eigenschaften (Klasse, oberste Ebene). Die rechte
  Seite wird an ihrer eigenen Stelle aufgelöst. `= Klasse(…)` bleibt wie in A07 (Herkunft `lokal`
  bzw. `eigenschaft`).
- **Cast** (`cast`): `(x as T).f()`, `(x as? T)?.f()`.
- `x!!` und Klammern sind durchsichtig: `x!!.f()` hat die Herkunft von `x`. Ketten dürfen seit A07b
  auch `?.` enthalten (`a?.b.f()`).
- Nicht: Smart-Casts, Typargumente (`List<T>`, `it`), Rückgabetypen externer Funktionen, Typaliase,
  Überladungen nach Argumenttypen.

Der Beleg nennt die Herkunft des **letzten** Schritts: `a.b().c()` ist `rueckgabe`,
`f().feld.g()` ist `eigenschaft`, außer `feld` hat selbst keine Typangabe und übernimmt den Typ aus
seinem Initialisierer (`initialisierer`).

**Zugriffe auf Eigenschaften mit eigenem Accessor (seit A07b).** Hat eine interne Eigenschaft ein
`get()` mit Körper, ist jedes Lesen eine `ruft`-Kante zum Knoten `<get-x>` (Herkunft `lesen`); hat
sie ein `set()` mit Körper, ist jede Zuweisung (`=`, `+=` und andere, `++`, `--`) eine Kante zu
`<set-x>` (Herkunft `schreiben`). `+=`, `++` und `--` lesen zusätzlich. Als Lesen gilt ein Name als
Ausdruck, `a.x` (nicht als Kopf eines Aufrufs), `this.x` und `"$x"`; nicht Namen in Deklarationen,
Typen, Labels, Argumentnamen und Funktionsreferenzen. Lokale Werte und Parameter verdecken
Eigenschaften. Für den Empfänger gelten die Regeln der Aufrufe (`this`/implizit, Parameter,
Eigenschaft, lokal, Objekt, Ketten, Typen durch Nachschlagen, Erweiterungseigenschaften). Bei
unbekanntem Empfänger gibt es unsichere Kanten (`unbekannter-empfaenger`) zu allen sichtbaren
Accessoren dieses Namens, bei mehr als 5 keine Kante. Eigenschaften ohne eigenen Accessor und
delegierte Eigenschaften ergeben keine Kante. Zugriffe zählen nicht als Aufrufe, weder in
`externe_aufrufe` noch im Abdeckungsbefund. Mehrere Zugriffe einer Funktion auf dasselbe Ziel bilden
eine Kante mit `gewicht`.

**Abschwächungen:** Liegt zwischen Aufruf und Fundort ein impliziter Empfänger mit unbekanntem Typ
(Lambda von `apply`/`run`/`with` auf unbekanntem Empfänger, Lambda einer internen Funktion mit
Empfänger-Funktionstyp), werden alle Treffer unsicher (`unbekannter-empfaenger`). Liegt dort ein
Empfänger mit Mitgliedern, die Daidalos nicht kennt (externer Obertyp einer umgebenden Klasse,
externer Erweiterungsempfänger, Lambda als Argument einer externen Funktion außer bekannten ohne
Empfänger wie `let`, `map`, `forEach`, `remember`), werden Treffer **kleingeschriebener** Namen
außerhalb der Klassen (Datei, Import, Paket) unsicher (`kleingeschrieben`): Ein gleichnamiges
Mitglied hätte Vorrang.

Kante `ruft`: `gewicht` = Zahl der Aufruf- und Zugriffsstellen, `sicher` = mindestens ein Beleg
sicher, `rolle` nach der aufrufenden Datei. `beleg` (seit A07b zusammengefasst): je (Herkunft,
sicher, Grund) ein Eintrag `{ "herkunft", "sicher", "grund"?, "zeilen": [12, 40, 41] }`. `zeilen`
ist aufsteigend, mit Wiederholung bei mehreren Stellen in einer Zeile; die Summe der Längen ist
`gewicht`. Die Einträge sind nach erster Zeile, Herkunft, sicher vor unsicher und Grund sortiert. Eine
Zeile ist die Zeile des Funktions- bzw. Eigenschaftsnamens. `herkunft`: `this`, `parameter`,
`eigenschaft`, `lokal`, `objekt`, `ohne-empfaenger` (oberste Ebene derselben Datei), `import`,
`gleiches-paket`, `konstruktor`, `erweiterung`, `referenz`, `super`, `unbekannter-empfaenger`; seit
A07b `rueckgabe`, `konstruktor-ergebnis`, `initialisierer`, `cast`, `lesen`, `schreiben`.
`grund` nur bei unsicheren Belegen: `ueberladung`, `erweiterung`, `unbekannter-empfaenger`,
`kleingeschrieben`. Selbstaufrufe ergeben eine Kante auf sich selbst. `ruft` wird nicht auf Datei-
oder Paketebene verdichtet.

**`ueberschreibt`:** von `override fun` zur nächsten Funktion gleichen Namens, gleicher Stelligkeit
und gleichen Erweiterungsempfängers in den internen Obertypen (Breite zuerst; bei mehreren gleicher
Stelligkeit entscheiden die einfachen Typnamen der Parameter). Sicher, wenn es genau ein Ziel gibt
und alle Obertypen der Klasse intern aufgelöst sind. Felder `gewicht` (1), `rolle`, `sicher`.

**`actual`:** von `actual fun` zur `expect fun` mit gleichem vollen Namen, gleicher Stelligkeit und
gleichem Erweiterungsempfänger im selben Modul; sicher bei genau einer.

**`jni` auf Funktionsebene:** `external fun` → C-Funktion `Java_…`; Regeln und Beleg wie bei der
Datei-Kante, `gewicht` 1.

#### Metriken je Funktion

```json
"metriken": { "externe_aufrufe": 2, "fan_in": 1, "fan_in_unsicher": 2, "fan_out": 3,
              "fan_out_unsicher": 4, "komplexitaet": 3, "zeilen": 12 }
```

| Feld | Bedeutung |
| --- | --- |
| `zeilen` | Zeilen der Funktion mit mindestens einem Zeichen außerhalb von Kommentaren; Leerzeilen zählen nicht. Implizite Konstruktoren 0; C: nicht leere Zeilen |
| `komplexitaet` | zyklomatisch: **1 + Anzahl von `if`, jedem `when`-Zweig außer `else`, `for`, `while`, `do`, `catch`, `&&`, `\|\|`, `?:` und `?.let`/`?.run`/`?.also`/`?.apply`/`?.takeIf`**, gezählt im ganzen Text der Funktion samt Lambdas und lokaler Funktionen; `null` bei C |
| `fan_in`, `fan_out` | Zahl verschiedener Funktionen über **sichere** `ruft`-Kanten der Rolle `produktiv`, ohne die Funktion selbst |
| `fan_in_unsicher`, `fan_out_unsicher` | dasselbe einschließlich unsicherer Kanten |
| `externe_aufrufe` | Aufrufstellen mit externem Ziel (Schritt 7) |
| `delegiert_gelesen` | seit A08, nur an markierten Funktionen: Zahl der verschiedenen delegierten Eigenschaften (`by lazy` u. a.), die die Funktion sicher aufgelöst liest |

### Markierungs-Kette (seit A08)

Nur mit Abschnitt `[markierungen]` in `daidalos.toml`. detekt prüft markierte Funktionen in ihrem
eigenen Körper; die Kette meldet jede unmarkierte interne Funktion, die von markiertem Code aus
erreicht wird.

**Was zählt:** produktive Kotlin-Funktionen außerhalb von Fremdcode und außerhalb von
`[markierungen].ausgenommen`. Nur sichere Annotationen (aufgelöster voller Name) zählen.

- **markiert** (`markiert: true`): Eine Annotation aus `annotationen` steht an der Funktion selbst,
  an einer umgebenden Klasse, einem Objekt oder Companion (jede Ebene) oder an ihrer Datei
  (`@file:`). Ausnahme: ein `<init>` ist nur durch eine eigene Annotation markiert, nie durch Klasse
  oder Datei (`init`-Blöcke und Initialisierer stehen im Konstruktor). Accessoren `<get-x>`/`<set-x>`
  deckt die Klasse.
- **Ausnahme** (`ausnahme: true`): Eine Annotation aus `ausnahmen` steht an der Funktion oder einer
  umgebenden Klasse (nicht an der Datei). Eine Ausnahme ist kein Start, auch wenn sie markiert ist.
- **ohne Code:** Funktionen mit `ohne_koerper` und implizite Konstruktoren sind nie ein Verstoß.

**Folgen:** Start ist jede markierte Funktion, die keine Ausnahme ist. Gefolgt wird `ruft` (auch
`lesen`/`schreiben`). Jedes Ziel eines Aufrufs wird erweitert um alle Funktionen, die es über
`ueberschreibt` (rekursiv) überschreiben, und um die `actual` zu einer `expect`-Funktion (Schritt
`ueberschrieben-von` bzw. `actual`); das gilt auch, wenn das Ziel selbst markiert ist, denn der
Aufruf kann bei jeder Umsetzung landen. Eine erreichte Funktion, die zählt, Code hat und weder
markiert noch Ausnahme ist, ist ein **Verstoß**; von ihr aus wird weiter gefolgt. An markierten
Funktionen, Ausnahmen, Funktionen, die nicht zählen, und externen Zielen endet die Kette. `jni`-Kanten
werden nicht verfolgt.

**Grenzkante:** markierte Funktion → erster Verstoß. Je Paar ein Befund `markierung-verlassen`.
Die Kette läuft zuerst nur über sichere Kanten (`ruft`, `ueberschreibt`, `actual` mit
`sicher: true`, bei `ruft` nur die sicheren Belege). Grenzkanten, die es nur über unsichere Kanten
gibt, werden eigene Befunde mit `beleg.unsicher: true` und `schwere: hinweis`.

| Feld im Beleg | Bedeutung |
| --- | --- |
| `von`, `von_zeile` | die markierte Funktion und ihre erste Zeile |
| `nach`, `nach_zeile` | der erste Verstoß und seine erste Zeile |
| `markierung` | `{ "name": voller Annotationsname, "traeger": "funktion" \| "klasse" \| "datei" }` |
| `zeilen` | Aufrufstellen in `von`, aufsteigend |
| `kette` | alle ab `nach` erreichten Verstöße ohne `nach`: `{ "funktion", "tiefe", "von", "zeile", "schritt"?, "ueber"? }`, sortiert nach `tiefe`, dann `funktion`. `tiefe` = kürzester Abstand ab `nach`, `von` = Aufrufer auf diesem Weg, `zeile` = erste Zeile der Funktion; `schritt`/`ueber` nur bei Erreichen über `ueberschrieben-von`/`actual` (mit der überschriebenen bzw. `expect`-Funktion) |
| `kette_unsicher` | nur bei sicheren Befunden: was zusätzlich nur über unsichere Kanten erreichbar ist, Aufbau wie `kette`; fehlt, wenn leer |
| `anzahl` | Länge von `kette` plus 1 |
| `ausnahmen` | Ausnahmen, an denen die Kette endete, sortiert |
| `ueber_ueberschreiben` | ob die Grenzkante oder ein Schritt der Kette über `ueberschreibt`/`actual` lief |
| `delegiert_gelesen` | wie die Metrik an `von` (Vermerk, kein Verstoß) |
| `unsicher` | nur bei Grenzkanten, die es nur unsicher gibt: `true` |

`knoten` des Befunds: `von`, `nach` und die Dateien von `von`, `nach` und `kette`. Lambdas als
Argument gehören wie überall zum Aufrufer. Konfigurierte Namen, die im Code nirgends sicher
vorkommen, ergeben eine Warnung.

### detekt-SARIF (seit A08)

Nur mit `[detekt].sarif`. Gesucht wird im ganzen Zielrepo, auch unter Pfaden, die `[scan]`
ausschließt (detekt schreibt nach `build/`); `.git` und Ordner mit eigenem `.git` (verschachtelte
Repos, Worktrees) werden nicht betreten. Gelesen wird SARIF 2.1.0: `runs[].results[]` mit `ruleId`,
`level`, `message.text`, `locations[0].physicalLocation.artifactLocation.uri` und
`region.startLine`.

- `uri`: absolute `file:`-URI, absoluter Pfad oder Pfad relativ zum Zielrepo; Ergebnisse außerhalb
  des Zielrepos werden mit Warnung verworfen, Ergebnisse in nicht erfassten Dateien mit einer
  Sammelwarnung, Ergebnisse in Fremdcode ohne Warnung.
- `schwere` aus `level`: `error` → `fehler`, `warning` → `warnung`, sonst `hinweis`; ohne `level`
  gilt wie in SARIF `warning`.
- `knoten`: die innerste Funktion, deren Zeilen die Zeile enthalten, sonst die Datei.
- `beleg`: `{ "zeile", "meldung", "sarif" }`, `sarif` = Pfad der SARIF-Datei relativ zum Zielrepo.
- Gleiche Datei, Zeile und Regel aus mehreren Ergebnissen werden ein Befund: `sarif` wird bei
  mehreren Dateien eine sortierte Liste, verschiedene Meldungen werden sortiert mit Zeilenumbruch
  verbunden, `schwere` ist die strengste.
- Eine leere Datei und eine Datei ohne Ergebnisse sind gültig (keine Verstöße). Eine Datei, die
  kein JSON mit `runs` ist, ergibt eine Warnung und wird übersprungen.

detekt-Befunde brauchen keine Einschätzung und machen keine Datei wichtig.


### Determinismus

Gleicher Stand des Zielrepos ergibt eine byte-gleiche Datei: UTF-8 ohne BOM, Zeilenende LF,
Einrückung 2, Schlüssel sortiert, abschließender Zeilenumbruch. Keine Zeitstempel, keine absoluten
Pfade, keine Rechnernamen. Die Laufzeit erscheint nur auf stdout.

## `deutung.json`, `schema: 1`

Ablage: `<zielrepo>/docs/daidalos/deutung.json`. Inhalt nur vom Skill (ab A06), gespeichert über
`daidalos deutung uebernehmen`, gelesen von `daidalos render`. Enthält nur Gedeutetes und verweist über Ids auf die Messung.

```json
{
  "schema": 1,
  "beschreibungen": {
    "modul::core": { "text": "Fachlicher Kern ohne Android.", "hash": "sha256:…" }
  },
  "bereiche": [
    { "id": "bereich:zeichen-pipeline", "name": "Zeichen-Pipeline", "beschreibung": "…",
      "knoten": ["paket::core/de.beispiel.zeichnen"] }
  ],
  "einschaetzungen": [
    { "befund": "befund:zyklus:datei:produktiv:3fa2c81b0d4e", "prioritaet": 1, "titel": "…",
      "begruendung": "…", "vorschlag": "…" }
  ],
  "kanten": {
    "kante:nutzt:datei:a.kt->datei:b.kt:produktiv": { "text": "Diese Verbindung schließt den Zyklus …" }
  }
}
```

| Feld | Bedeutung |
| --- | --- |
| `schema` | Formatversion, derzeit `1`; ein anderer Wert oder ungültiges JSON beendet `render` mit Exit-Code 2 |
| `beschreibungen` | Knoten-Id → `text` und `hash`. `hash` ist der Hash des Knotens zum Zeitpunkt der Deutung (Datei-Hash bzw. Gruppen-Hash) |
| `bereiche` | Liste mit `id`, `name`, `beschreibung` und `knoten` (Knoten-Ids). A04 zeigt sie nur als Liste |
| `einschaetzungen` | je Befund `prioritaet` (ganze Zahl, 1 = zuerst), `titel`, `begruendung`, `vorschlag` |
| `kanten` | Kanten-Id → `text`; die Karte zeigt die Texte ab A05 |

Alle Felder außer `schema` sind optional.

**Abgleich beim Lesen:**

- Eine Beschreibung gilt als **veraltet**, wenn ihr `hash` nicht gleich dem aktuellen `hash` des
  Knotens ist (auch wenn er fehlt). Sie wird trotzdem gezeigt, mit dem Vermerk „veraltet“.
- Verweise auf Knoten-, Befund- oder Kanten-Ids, die es in der Messung nicht gibt, werden
  übersprungen und als Warnung auf stderr gemeldet. Bereiche bleiben erhalten, nur ihre toten
  Verweise fallen weg.
- Unbekannte Schlüssel auf oberster Ebene: Warnung, kein Abbruch.
- Einschätzungen werden nach `prioritaet` sortiert (ohne Priorität ans Ende, Gleichstand nach
  Befund-Id), Bereiche nach `name`.

### Entwurf für `daidalos deutung uebernehmen` (seit A06)

Der Skill schreibt nie direkt in `deutung.json`, sondern einen **Entwurf** im selben Format, aber
**ohne** `hash`. `daidalos deutung uebernehmen ENTWURF.json [ZIEL]` prüft ihn, setzt die Hashes
ein und führt ihn mit der bestehenden `deutung.json` zusammen. Den Inhalt schreibt der Skill; das
Programm setzt nur Hashes ein, prüft und speichert.

- `schema` ist optional; wenn angegeben, muss es `1` sein.
- Ein `hash` im Entwurf wird ignoriert und durch den aktuellen Hash des Knotens ersetzt.
- Zusätzlicher Schlüssel `entfernen`: Liste von Ids (Knoten-Id einer Beschreibung, Kanten-Id,
  Bereichs-Id oder Befund-Id einer Einschätzung); diese Einträge fallen aus dem Bestand. So lassen
  sich tote Verweise beseitigen. `entfernen` wird vor den neuen Einträgen angewendet.
- **Prüfung** (jeder Fehler wird gemeldet, Exit-Code 2, es wird nichts geschrieben): unbekannte
  Knoten-, Befund- und Kanten-Ids; unbekannte Schlüssel auf oberster Ebene und in Einträgen; leere
  Texte; Bereich ohne `id` mit Präfix `bereich:`, ohne `name`, `beschreibung` oder mit leerer
  `knoten`-Liste; doppelte Bereichs-Ids oder Einschätzungen zum selben Befund; `prioritaet` keine
  ganze Zahl ≥ 1; Einschätzung ohne `titel` oder `begruendung`; Einschätzung **mit** `prioritaet`
  ohne `vorschlag`.
- **Zusammenführung:** Einträge des Entwurfs ersetzen gleichnamige ganz (Beschreibung und
  Kantentext je Id, Bereich je `id`, Einschätzung je `befund`), alles andere bleibt, auch
  Bestandseinträge mit toten Verweisen.
- **Ausgabe** deterministisch wie `daidalos.json` (UTF-8, LF, Einrückung 2, Schlüssel sortiert):
  `bereiche` nach `id`, deren `knoten` sortiert und ohne Doppelte, `einschaetzungen` nach `befund`,
  ohne Felder mit `null`.

**Einschätzung ohne Priorität (seit A06):** Jeder Befund braucht eine Einschätzung, sonst gilt er
als offen. 3 bis 10 Befunde bekommen eine `prioritaet`; die übrigen eine Einschätzung ohne
`prioritaet` (nachrangig, `vorschlag` freiwillig). Die Karte zeigt sie nach den priorisierten,
seit A06b mit einem kleinen, gedämpften Zeichen „nachrangig“ statt einer Prioritätszahl (in
Befundliste und Seitenleiste); `KARTE.md` führt sie als Aufzählung `- <sub>nachrangig</sub> …` nach
der nummerierten Liste.

## Zusammenfassung (`daidalos zusammenfassung`, seit A06)

Markdown auf stdout (`--json`: dasselbe als JSON), nur aus Messung und Deutung, schreibt nichts.
Inhalt: Projekt, Commit und Zahlen; Module und Ordner (Dateien, Zeilen, Fan-in, Fan-out,
Gradle-Kanten nach außen); Pakete je Modul bzw. Ordner; wichtige Dateien mit Grund; Befunde in
einer Zeile; **Messung** (seit A07: Funktionen produktiv und Test, `ruft`-Kanten sicher und
unsicher, unaufgelöste Aufrufe mit den zehn häufigsten Namen; JSON-Schlüssel `messung`); seit A09
**wichtige Funktionen** (JSON `wichtige_funktionen`: `id`, `datei`, `zeile_von`, `zeile_bis`,
`fan_in`, `komplexitaet`, `markiert`, `gruende`, `deutung`; `zahlen.wichtige_funktionen`);
**Offen**.
Die Spalte „Deutung“ zeigt je Knoten `ok`, `fehlt`, `veraltet` oder `fremd`. Die Zusammenfassung
arbeitet auf der Strukturansicht (ohne Funktionsebene, siehe dort).

**Wichtige Dateien** (Auswahlregel, keine Deutung): produktive (`rolle` nicht `test`), nicht
fremde Dateien, die mindestens eines erfüllen. Gründe in dieser Reihenfolge:

| Grund | Regel |
| --- | --- |
| `fan-in` | unter den 30 mit dem höchsten `metriken.fan_in` (nur Fan-in > 0; Gleichstand nach Id) |
| `befund` | in `knoten` eines Befunds (außer `unaufgeloest` der Art `aufruf` und detekt); bei `markierung-verlassen` nur die Dateien von `von` und `nach` |
| `einstieg` | in `beleg.einstiege` eines Zyklus |
| `trennstelle` | Ende der `trennstelle` eines Datei-Zyklus; bei Paket- und Modulzyklen die Enden aller Datei-Kanten gleicher Art und Rolle, die die verdichtete Trennstelle tragen |
| `jni` | Ende einer `jni`-Kante |
| `modulkante` | Ende einer produktiven `nutzt`-Datei-Kante mit `gewicht` ≥ 3 zwischen verschiedenen Modulen bzw. Ordnern |

**Wichtige Funktionen** (seit A09, Auswahlregel, keine Deutung): produktive Funktionen mit `hash`
(ohne implizite Konstruktoren) außerhalb von Fremdcode. Gründe: `fan-in` (die 20 mit dem höchsten
sicheren `metriken.fan_in`, nur Fan-in > 0, Gleichstand nach Id) und `grenzkante` (`von` eines
Befunds `markierung-verlassen`, nach Zahl der Grenzkanten, dann Id). Höchstens 40 insgesamt, die
Fan-in-Auswahl zuerst. Ihre Beschreibung hat als Schlüssel die Funktions-Id; Hash und Abgleich
laufen wie bei Dateien über den `hash` des Funktionsknotens.

**Offen:**

- Beschreibung `fehlt` für Module, Ordner und Pakete (ohne reinen Fremdcode), wichtige Dateien und
  (seit A09) wichtige Funktionen ohne Eintrag mit Text in `beschreibungen`.
- Beschreibung `veraltet` für jeden beschriebenen Knoten, dessen `hash` vom aktuellen abweicht.
- Befunde ohne Einschätzung (außer `unaufgeloest` der Art `aufruf` und detekt-Befunden).
- Tote Verweise: Ids in `beschreibungen`, `bereiche[].knoten`, `einschaetzungen[].befund` und
  `kanten`, die es in der Messung nicht gibt.

Sind alle offenen Beschreibungen bzw. Befunde einer Art offen, nennt das Markdown nur die Zahl;
über 40 Einträge ebenso. `--json` listet immer alle: `offen.beschreibungen` (`id`, `stand`),
`offen.befunde_ohne_einschaetzung`, `offen.tote_verweise` (`"<wo>: <id>"`).

`daidalos deutung pruefen` meldet genau diese Liste und endet mit 0, wenn sie leer ist, sonst
mit 1 (fehlende oder ungültige Messung bzw. ungültige `deutung.json`: 2; fehlende
`deutung.json`: alles offen, 1).

## Arbeitsblatt (`daidalos arbeitsblatt`, seit A06)

Markdown auf stdout für ein Modul, einen Ordner, ein Paket oder eine Datei (Id oder eindeutiger
Suchbegriff wie bei `daidalos pfad`). Die Dateien werden neu gelesen; `daidalos.json` ändert sich
nicht. Je Datei: Id, Zeilen, Sprache, Quellsatz, Fan-in/Fan-out, Grund als wichtige Datei, Stand
der Deutung; bei Kotlin die erste KDoc-Zeile der Datei (KDoc vor `package`) und die Deklarationen
der obersten Ebene mit Zeile und erster KDoc-Zeile, ohne KDoc der Datei den Kommentar vor der ersten Deklaration (Kopfkommentar, höchstens 160 Zeichen) (Tags wie `@param` zählen nicht, höchstens 160
Zeichen); `nutzt` und `genutzt von` (produktive vor Test-Kanten, nach Gewicht, je Richtung höchstens
8 Kanten mit je 3 Belegen); `ADR-\d{4}` in Kommentaren (bei Sprachen ohne Adapter im ganzen Text)
mit Anzahl. Hat sich die Datei seit dem Scan geändert oder fehlt sie, steht ein Vermerk dabei.
Für Module und Ordner: Kanten nach außen verdichtet, Pakete, wichtige Dateien voll, die übrigen
als eine Zeile (mit erster KDoc-Zeile); für Pakete alle Dateien voll, solange das Blatt unter
etwa 400 Zeilen bleibt. Was nicht passt, steht als Kurzzeile oder als „… und n weitere“.
Seit A07 listet das Arbeitsblatt **einer Datei** unter „deklariert“ zusätzlich die Funktions-Ids mit
Zeile und Komplexität (C: `C`, implizite Konstruktoren: `implizit`), nach Zeile sortiert; seit A09
mit `Z. von–bis` (eine Zahl bei einer Zeile) und bei wichtigen Funktionen „wichtig, Deutung
<stand>“.

## Aufrufe (`daidalos pfad` und `daidalos aufrufe`, seit A07)

`daidalos pfad VON NACH` nimmt auch Funktions-Ids (oder eindeutige Suchbegriffe wie
`Strich.zeichne` bzw. `Strich.zeichne/1`, also den Teil hinter `#`) und sucht dann den kürzesten Weg
über `ruft`. Ohne `--unsicher` zählen nur sichere Kanten, mit `--unsicher` auch unsichere; die
Ausgabe nennt je Schritt Datei, Zeile und Herkunft des Aufrufs und kennzeichnet unsichere Belege mit
ihrem Grund. `--mit-tests` wie auf den anderen Ebenen; `--json` hat zusätzlich `unsicher`.

`daidalos markierung [--datei D] [--unsicher] [--daten D]` (seit A08) gibt alle Grenzkanten der
Markierungs-Kette als Text aus, nach `anzahl` absteigend, dann nach Id: Kopf, markierte Funktion
mit Markierung und Aufrufzeilen, die Kette als eingerückter Baum (Datei:Zeile), unsichere
Fortsetzung, Ausnahmen und Befund-Id. Ohne `--unsicher` nur sichere Grenzkanten; `--datei` filtert
auf die Datei von `von` (voller relativer Pfad oder Endung).

`daidalos aufrufe ID [--rueckwaerts] [--tiefe N] [--unsicher] [--mit-tests]` gibt den Baum der
erreichbaren Funktionen als Text aus (Tiefensuche, Nachbarn nach Id): je Zeile Funktion, Datei und
Zeile sowie die Aufrufstellen. Jede Funktion steht einmal voll; spätere Vorkommen sind Verweise
(„siehe oben“), Selbstaufrufe „Rekursion“. Ist `--tiefe` erreicht, steht dort die Zahl der nicht
gezeigten Funktionen.

## Ausgaben auf der Befehlszeile

Seit A06 schreibt `daidalos` stdout und stderr immer als UTF-8, auch in Pipes unter Windows.

## `karte.html` und `KARTE.md`

`daidalos render` schreibt beide Dateien deterministisch (UTF-8, LF, keine Zeitstempel, keine
absoluten Pfade).

- `karte.html` ist eine einzige, offline lauffähige Datei: Vorlage, CSS und Skript aus
  `src/daidalos/karte/`, die Bibliotheken aus `src/daidalos/karte/vendor/` mit ihren Lizenztexten
  als HTML-Kommentar und zwei Datenblöcke `<script type="application/json">`:
  `id="daidalos-daten"` (die Messung, seit A07 als Strukturansicht ohne Funktionsebene, kompakt,
  Schlüssel sortiert) und
  `id="daidalos-deutung"` (die abgeglichene Deutung mit `veraltet` je Beschreibung, sonst `null`).
  Seit A05 ein dritter Block `id="daidalos-einstellungen"` mit Einstellungen, die keine Messung
  sind: `{ "editor_link": "vscode://file/{pfad}:{zeile}", "wurzel": "../.." }`. `editor_link`
  stammt aus `[editor].link`; `wurzel` ist der relative Weg vom Ausgabeordner zur Wurzel des
  Zielrepos (`../..` im Standardordner `docs/daidalos/`), `null`, wenn der Ausgabeordner nicht im
  Zielrepo liegt. In allen Blöcken ist jedes `<` als `\u003c` geschrieben, damit Inhalte das
  Script-Tag nicht beenden können. Quelltext wird nicht eingebettet.
- **ELK im Web Worker (seit A09b):** Statt `elk.bundled.js` stehen `elk-api.js` und der
  Worker-Quelltext `elk-worker.min.js` in der Karte, dieser als Text in
  `<script type="text/plain" id="elk-worker">`. Die Hülle `elk_lauf.js` (zwischen `elk-api.js` und
  `cytoscape-elk.js`) startet daraus einen Worker über eine Blob-URL (`file://` erlaubt keine
  Worker-Datei) und nutzt ihn für alle Layouts. Ein laufendes Layout wird abgebrochen, sobald ein
  neues beginnt. Nach 5 s wird der Worker beendet; dann ordnet Cytoscape an (`breadthfirst`, mit
  Rahmen `grid`) und die Karte zeigt „vereinfachte Anordnung“ (`data-anordnung="ersatz"` am
  `<html>`, sonst `elk`). Ersatzanordnungen werden nicht zwischengespeichert. Die Karte lädt
  dabei nichts aus dem Netz; `blob:` ist eine lokale Adresse.
- Auf der Dateiebene der Karte stehen Quellcode-Dateien (`kotlin`, `java`, `c`, `cpp`;
  Gradle-Skripte sind seit A05b `gradle-kotlin` und fallen damit heraus) und jede Datei mit einer
  `nutzt`- oder `jni`-Kante. Bei mehr als 150 solcher Dateien sind nur ausgeklappte Module zu sehen.
- Auf der Modulebene werden Ordner ohne Dateien der Karte und ohne Kanten zu einem Kasten
  „Weitere Ordner“ (Id `sammel:ordner`) zusammengefasst; `gradle-plugin`-Kanten sind standardmäßig
  ausgeblendet (Vermerk „Plugin für n Module“ am Ziel, Schalter „Plugins“).
- **Markierungs-Kette und detekt (seit A08):** Befunde `markierung-verlassen` und detekt stehen in
  der Befundliste; Funktions-Ids in ihren `knoten` zeigt die Karte über ihre Dateien (Dateiebene).
  Schalter „Markierung“ (Standard an) und „detekt“ (Standard aus) blenden sie in den Listen ein
  und aus. Die Seitenleiste zeigt die Kette als eingerückte Liste mit Datei:Zeile und Editor-Link,
  ab 31 Einträgen eingeklappt. `KARTE.md` hat den Abschnitt „Markierungs-Kette“ (eine Zeile je
  Befund mit Länge und den ersten drei Funktionen) und „detekt“ (Zahl je Regel).
- **Sprungadressen:** `karte.html#knoten=<id>`, `#befund=<id>`, `#ebene=modul|paket|datei`,
  `#ebene=<e>&kante=<id>` (gemessene Kanten-Id oder Id einer verdichteten Kante der Karte) und
  `#ebene=<e>&von=<id>&nach=<id>` (Pfad-Suche); Ids URL-kodiert (`encodeURIComponent`). Die Adresse
  folgt der Auswahl, jede neue Auswahl ist ein Eintrag im Browser-Verlauf. Seit A09 für die
  Funktionsebene: `#datei-funktionen=<pfad>`, `#funktion=<id>` (mit `&datei-funktionen=<pfad>`,
  wenn die Funktion als Nachbar einer anderen Datei gewählt ist), `#funktion=<id>&weg=vor|rueck&tiefe=N`
  (Wirkungsweg, `&gewaehlt=<id>` für eine andere gewählte Funktion darin), `#grenze=<befund-id>`
  (Grenzkante auf der Funktionsebene), `#ebene=funktion` und `#ebene=funktion&von=<id>&nach=<id>`
  (Weg zwischen zwei Funktionen).
- **Funktionsebene (seit A09):** eine Fokus-Ansicht je Datei, nie die ganze Ebene. Gezeigt werden
  die Datei mit Klassen, Objekten und Companions als verschachtelte Rahmen und ihren Funktionen,
  dazu je fremder Datei ein Rahmen mit den Funktionen, die hierher rufen oder von hier gerufen
  werden (ELK, Richtung rechts). Kanten: `ruft` (unsicher gestrichelt, Gewicht ab 2 als Zahl),
  `lesen`/`schreiben` dünn (Schalter „Lesezugriffe“, aus), `ueberschreibt`/`actual` gepunktet,
  Schalter „unsicher“ (in der Dateiansicht an). Kanten aus Testcode nur mit „mit Tests“. Über 150
  Kästen werden Nachbardateien mit den meisten Funktionen zu „Datei (+N)“ zusammengefasst, bis es
  passt; ein Klick klappt eine auf. Grenzkanten `markierung-verlassen` sind in der Befundfarbe
  gezeichnet, ihr Ziel bekommt einen Rand in derselben Farbe; gibt es keine Kante (Grenze über
  `ueberschreibt`), steht eine Ersatzkante da. **Wirkungsweg:** Breitensuche ab einer Funktion
  vorwärts oder rückwärts bis Tiefe 1–5 (Standard 3), ohne Wiederholungen, nur `ruft` (mit
  Lesezugriffen nur mit dem Schalter), im Wegmodus standardmäßig nur sichere Kanten. Wie in der
  Markierungs-Kette werden erreichte Ziele vorwärts um ihre Überschreibungen und `actual`
  erweitert, rückwärts jede Funktion um das, was sie überschreibt, und ihr `expect` (gleiche
  Spalte). Spalten nach Abstand, je Spalte und Datei ein Rahmen; über 150 Kästen wird die Tiefe
  gekürzt und die Zählzeile nennt, wie viel fehlt. Seit A09b: Beim Öffnen ist die Start-Funktion
  gewählt, aber ohne Fluss; die Ansicht passt den ganzen Weg unter der Infoleiste ein. Wäre die
  Schrift dabei kleiner als 9 px, steht die Startspalte bei diesem Zoom am Rand (vorwärts links,
  rückwärts rechts), senkrecht um den Start, und eine Zeile nennt „weiter rechts: N Funktionen“
  (auch links, darüber oder darunter). Kanten gleicher Quelle laufen als ein Strang
  (ELK `mergeEdges`, nur im Wegmodus). Ein Wirkungsweg ab einer markierten Funktion zeigt
  Lesezugriffe standardmäßig (die Markierungs-Kette zählt sie mit); der gemerkte Stand des
  Schalters bleibt dabei unberührt. Zählzeile, „wer … nutzt“ und Hinweise stehen in einer Leiste
  untereinander. Gemerkte Positionen unter dem Schlüssel
  `…|funktion:<pfad>` (Wirkungswege `…|funktion-weg:<id>:<richtung>:<tiefe>`).
- **Funktionsblock (seit A09):** ein vierter Block `<script type="application/json"
  id="funktionen">`, nur für die Karte; `daidalos.json` bleibt unverändert. Die Karte liest ihn
  erst beim ersten Öffnen der Funktionsebene. Ohne Funktionsknoten steht `null` darin. Aufbau
  (Schlüssel sortiert, kompakt):

  ```json
  { "format": 1, "arten": ["ruft", "lesen", "schreiben", "ueberschreibt", "actual", "jni"],
    "dateien": ["core/…/Strich.kt"], "felder": ["datei", "kurz", …],
    "funktionen": [[0, "Strich.setze/1", "Strich", 12, 20, 1, 3, 8, 2, 2, 1, 3, 0, 0,
                    "public", [], ["Int"], [], [], [["de.a.Strichpfad", true]], null,
                    ["de.a.Strichpfad", "funktion"]]],
    "kanten": [[0, 4, 0, 1, 2, 14, 3, -1]],
    "klassen": [[["Strich", "klasse", 10]]],
    "merkmale": { "markiert": 1, "ausnahme": 2, "ohne_koerper": 4, "implizit": 8, "test": 16, "c": 32 },
    "texte": ["import", "lesen", "unbekannter-empfaenger"] }
  ```

  - `dateien`: Pfade aller Dateien mit Funktionen, sortiert; `klassen[i]` gehört zu `dateien[i]`:
    `[name, art, zeile]` wie im Datei-Feld `klassen`.
  - `funktionen`: eine Zeile je Funktionsknoten, sortiert nach Id; die Spalten nennt `felder`:
    `datei` (Index in `dateien`), `kurz` (Teil der Id hinter `#`; die Id ist
    `funktion:<dateien[datei]>#<kurz>`), `behaelter`, `zeile_von`, `zeile_bis`, `merkmale`
    (Bitfeld nach `merkmale`), `komplexitaet`, `zeilen`, `fan_in`, `fan_in_unsicher`, `fan_out`,
    `fan_out_unsicher`, `externe_aufrufe`, `delegiert_gelesen`, `sichtbarkeit`, `modifikatoren`,
    `parameter`, `parameter_vorgabe`, `parameter_vararg`, `annotationen` (`[name, sicher]`),
    `erweiterung`, `markierung` (`[Annotation, Träger]` mit Träger `funktion`, `klasse` oder
    `datei` nach der Regel der Markierungs-Kette, aus `[markierungen].annotationen`; `null`,
    wenn nicht markiert oder ohne Konfiguration).
  - `kanten`: `[von, nach, art, sicher, gewicht, ersteZeile, herkunft, grund]`, sortiert. `von`
    und `nach` sind Indizes in `funktionen`, `art` ein Index in `arten`, `sicher` 0/1. Eine
    `ruft`-Kante wird nach ihren Belegen geteilt: Belege mit Herkunft `lesen` bzw. `schreiben`
    bilden eine Kante dieser Art, alle übrigen eine `ruft`-Kante; `sicher` und `gewicht` gelten je
    Teil. Von den Belegen steht nur die erste Zeile (`ersteZeile`) mit ihrer Herkunft (`herkunft`,
    Index in `texte`) und bei unsicheren Kanten der Grund des ersten unsicheren Belegs (`grund`,
    Index in `texte`); `-1` für keinen. Die volle Liste steht in `daidalos.json`. Bei `jni` ist
    `ersteZeile` die Kotlin-Zeile, bei `ueberschreibt`/`actual` `null`.
- **Im Editor öffnen:** Die Karte setzt den Link zur Laufzeit zusammen: Verzeichnis der eigenen
  `file://`-Adresse plus `wurzel` plus Pfad der Datei. `{pfad}` ist der absolute Pfad mit `/`, ohne
  führenden Schrägstrich (`E:/Repo/app/A.kt`, unter Linux `home/u/repo/app/A.kt`), jedes Segment
  URL-kodiert außer dem Laufwerk; `{zeile}` ist die Zeile (Datei-Kasten: 1, Beleg: seine Zeile).
  Ohne `file://` oder ohne `wurzel` sind die Editor-Symbole ausgegraut.
- **Gemerkte Positionen** (nur im Browser): `localStorage` unter
  `daidalos-positionen|<ziel.name>|<wurzel>|<ablageort>|<ebene>`, Wert `{ "<knoten-id>": [x, y] }`
  für verschobene Blätter. `<wurzel>` ist der eingebettete Weg zur Repo-Wurzel (leer ohne),
  `<ablageort>` der Pfad aus der eigenen Adresse der Karte (bei `file://` dekodiert, mit `//host`
  bei Netzlaufwerken; sonst Origin und Pfad). Seit A05b; Einträge unter dem alten Schlüssel
  `daidalos-positionen|<ziel.name>|<ebene>` übernimmt die Karte beim Öffnen einmal und löscht sie. Unbekannte Ids werden ignoriert; „Anordnung zurücksetzen“ löscht den Eintrag der Ebene.
- `KARTE.md` fasst Module, Gradle-Abhängigkeiten, Bereiche und Befunde zusammen; jede Erwähnung
  eines Knotens oder Befunds verlinkt auf seine Sprungadresse. Seit A09b steht zwischen
  „Bereiche“ und „Befunde“ der Abschnitt „Wichtige Funktionen“: eine Tabellenzeile je Funktion mit
  Beschreibung in der Deutung (Name als Link `karte.html#funktion=<id>`, `Datei:Zeile`, der Satz,
  `*(veraltet)*` wie bei anderen Beschreibungen), sortiert nach Datei und Zeile; ohne solche
  Beschreibungen fehlt der Abschnitt.

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

[markierungen]
# volle Namen; markiert: Funktion, umgebende Klasse (jede Ebene) oder Datei (@file:)
annotationen = ["de.beispiel.Strichpfad", "de.beispiel.Deterministisch"]
# volle Namen; bewusste Ausnahmen (Funktion oder Klasse): kein Befund, die Kette endet dort
ausnahmen = ["de.beispiel.WeckenOhneDaten"]
# gitwildmatch: weder Quelle noch Ziel einer Kette
ausgenommen = ["werkzeuge/gegenfaelle/"]

[detekt]
# gitwildmatch, relativ zum Zielrepo; auch unter ausgeschlossenen Pfaden gesucht
sarif = ["**/build/reports/detekt/*.sarif"]

[editor]
befehl = "code -g {datei}:{zeile}"
# Vorlage für „Im Editor öffnen“ in karte.html
link = "vscode://file/{pfad}:{zeile}"
```

| Schlüssel | Typ | Standard | Bedeutung |
| --- | --- | --- | --- |
| `[projekt].name` | nicht leerer Text | Ordnername | Name in `ziel.name` |
| `[scan].ausschliessen` | Liste von Texten | `[]` | zusätzliche Ausschlüsse |
| `[scan].fremd` | Liste von Texten | `[]` | Dateien werden erfasst und bekommen `"fremd": true` |
| `[editor].befehl` | Text | `code -g {datei}:{zeile}` | wird erst später benutzt (`daidalos serve`) |
| `[editor].link` | Text | `vscode://file/{pfad}:{zeile}` | Editor-Link in `karte.html`; ohne `{pfad}` eine Warnung. `daidalos render` liest ihn (Option `--konfiguration` wie bei `scan`) |
| `[markierungen].annotationen` | Liste von Texten | `[]` | seit A08; ohne Abschnitt `[markierungen]` gibt es keine Kette |
| `[markierungen].ausnahmen` | Liste von Texten | `[]` | seit A08 |
| `[markierungen].ausgenommen` | Liste von Texten | `[]` | seit A08, gitwildmatch |
| `[detekt].sarif` | Liste von Texten | `[]` | seit A08, gitwildmatch; leer: kein `ziel.detekt` |

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
