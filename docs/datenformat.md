# Datenformat

Stand 2026-11-22 (A02). Diese Datei beschreibt `daidalos.json` (Ausgabe des Programms) und
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
| `ziel.name` | Name des Zielordners (nur der letzte Pfadteil, kein absoluter Pfad) |
| `ziel.git_commit` | HEAD des Zielrepos (volle Länge); `null` ohne Git oder ohne Commit |
| `ziel.git_aenderungen` | ob eine **erfasste** Datei nicht committete Änderungen hat; nicht getrackte, aber erfasste Dateien zählen als Änderung; `null` ohne Git |
| `knoten` | Knoten, sortiert nach `id` |
| `kanten` | Kanten, sortiert nach `(von, nach, art)`; in A02 leer |
| `befunde` | Befunde, sortiert nach `id`; in A02 leer |

„Mit Git“ heißt: Das Zielverzeichnis enthält selbst `.git` (Ordner oder Datei) und `git` ist
aufrufbar. Ein Unterordner eines anderen Repos zählt nicht als Git-Repo.

### Id-Schema für alle Knotenarten

Alle späteren Kanten und Befunde verweisen über diese Ids auf Knoten.

| Art | Id | Beispiel |
| --- | --- | --- |
| datei | `datei:<pfad>` | `datei:core/src/main/kotlin/a/b/Strich.kt` |
| modul | `modul:<gradle-pfad>` | `modul::core`, `modul::platform-labor` |
| paket | `paket:<gradle-pfad>/<paketname>` | `paket::core/de.beispiel.zeichnen` |
| funktion | `funktion:<dateipfad>#<Klasse>.<name>/<stelligkeit>` | `funktion:core/.../Strich.kt#Strich.fuegeHinzu/1` |

- Pfade sind relativ zum Zielrepo und verwenden `/`.
- Pakete tragen den Modulpfad, weil derselbe Paketname in mehreren Modulen vorkommen kann.
- Die Funktions-Id ist vorläufig und wird in Etappe 4 festgezurrt.
- In A02 entstehen nur Knoten der Art `datei`.

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

### Determinismus

Gleicher Stand des Zielrepos ergibt eine byte-gleiche Datei: UTF-8 ohne BOM, Zeilenende LF,
Einrückung 2, Schlüssel sortiert, abschließender Zeilenumbruch. Keine Zeitstempel, keine absoluten
Pfade, keine Rechnernamen. Die Laufzeit erscheint nur auf stdout.

## `daidalos.toml`, Format v1

Optional, im Wurzelordner des Zielrepos; mit `--konfiguration` auch von anderswo.

```toml
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
