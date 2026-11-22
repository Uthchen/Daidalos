# Auftrag A02 – Fundament: Projektgerüst, Konfiguration und Scanner

**Etappe:** 2, erster Teil · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** keine (A01 kann parallel laufen)

## Ziel

Am Ende gibt es ein lauffähiges Python-Paket `daidalos` mit dem Befehl

```
daidalos scan <zielrepo>
```

der alle relevanten Dateien des Zielrepos findet und `<zielrepo>/docs/daidalos/daidalos.json` schreibt: ein Knoten pro Datei mit Sprache, Zeilen, Größe und Hash. Noch keine Kanten, keine Analysen. Dazu die Leitplanken für alle weiteren Aufträge: `CLAUDE.md`, Architektur im Repo, Tests, CI.

Lies zuerst `docs/architektur.md` (liegt schon im Repo). Sie ist die verbindliche Architektur.

## Rahmen

- **Das Repo ist öffentlich.** Keine Inhalte aus Sketchorus oder anderen privaten Projekten committen, auch nicht als Testdaten. Testdaten sind erfundene Mini-Projekte. Der Ordner `lokal/` ist ignoriert und für private Ablagen da.
- **Sprache:** Doku, Kommentare, Fehlermeldungen, CLI-Ausgaben, JSON-Schlüssel und Bezeichner auf Deutsch. In Bezeichnern Umlaute umschreiben (`ae`, `oe`, `ue`, `ss`): `def scanne_dateien`, `class Knoten`, Schlüssel `"zeilen"`, `"sprache"`. Übliche Fachwörter bleiben (`hash`, `id`, `git_commit`).
- **Python ≥ 3.12**, Verwaltung mit **uv** (`uv init --package` bzw. `pyproject.toml` mit `src/`-Layout), Build-Backend `hatchling`.
- **Abhängigkeiten zur Laufzeit in A02:** nur `pathspec`. Konfiguration mit `tomllib` (Standardbibliothek), CLI mit `argparse`. tree-sitter und networkx kommen erst in A03.
- **Entwicklung:** `pytest`, `ruff` (Lint und Format, Zeilenlänge 100). Typ-Hinweise überall. In `pyproject.toml` `testpaths = ["tests"]` setzen und `lokal/` für ruff ausschließen, weil dort eine Kopie von Sketchorus mit eigenem Python-Code liegt.
- **Plattform:** muss unter Windows (Manus Rechner) und Linux laufen. Pfade intern mit `pathlib`, in allen Ausgaben relativ zum Zielrepo und mit `/`.

## Schritte

### 1. Repo-Grundlage
- `docs/architektur.md` und `docs/auftraege/` liegen schon bereit und werden unverändert mit committet.
- `.gitignore`: Python-Standard, `.venv/`, `lokal/`, `.pytest_cache/`, `.ruff_cache/`.
- `.gitattributes`: `* text=auto eol=lf`, damit Windows- und Linux-Checkouts gleich sind. Testbeispiele mit absichtlichen CRLF-Zeilenenden als `-text` markieren.
- `README.md`: kurz, was Daidalos ist, Installation (`uv sync`), Aufruf, Verweis auf `docs/architektur.md`.
- `LICENSE`: MIT, Inhaber „Manuel Grimm“, Jahr 2026.

### 2. `CLAUDE.md` für dieses Repo
Kurz und verbindlich, höchstens etwa 60 Zeilen. Inhalt:
- Was Daidalos ist (zwei Sätze) und Verweis auf `docs/architektur.md` und `docs/datenformat.md`.
- **Leitplanken:**
  1. Messen und Deuten bleiben getrennt. Das Programm schreibt nur Gemessenes in `daidalos.json`, nie Deutungen. `deutung.json` schreibt nur der Skill.
  2. Determinismus: gleicher Stand des Zielrepos ergibt byte-gleiche Ausgabe. Keine Zeitstempel, keine absoluten Pfade, keine Rechnernamen, stabile Sortierung.
  3. Unsicher statt raten: Was sich nicht eindeutig auflösen lässt, wird als unsicher markiert und nicht weggelassen oder geraten.
  4. Kein Netzwerk zur Laufzeit, keine Telemetrie.
  5. Keine Inhalte privater Projekte im Repo, Testdaten sind erfunden.
  6. Jede Änderung am Datenformat wird in `docs/datenformat.md` nachgetragen und erhöht bei inkompatiblen Änderungen `schema`.
- **Arbeitsweise:** pro Auftrag ein Branch `auftrag/aNN-kurzname`, kleine, thematische Commits, vor jedem Push `uv run ruff check`, `uv run ruff format --check`, `uv run pytest` grün. Am Ende jedes Auftrags einen Bericht `docs/auftraege/ANN-bericht.md` schreiben (was gemacht, Abweichungen vom Auftrag mit Grund, offene Fragen, nächste sinnvolle Schritte). Bei Unklarheit im Auftrag: die naheliegendste Lösung wählen und im Bericht begründen, statt anzuhalten.
- Befehle zum Entwickeln und Testen.

### 3. Datenformat festlegen: `docs/datenformat.md`
Beschreibe `daidalos.json` mit `schema: 1`. Vorerst nur das, was A02 schreibt, aber mit dem **Id-Schema für alle Knotenarten**, weil später alles darauf verweist:

| Art | Id | Beispiel |
| --- | --- | --- |
| datei | `datei:<pfad>` | `datei:core/src/main/kotlin/a/b/Strich.kt` |
| modul | `modul:<gradle-pfad>` | `modul::core`, `modul::platform-labor` |
| paket | `paket:<gradle-pfad>/<paketname>` | `paket::core/de.beispiel.zeichnen` |
| funktion | `funktion:<dateipfad>#<Klasse>.<name>/<stelligkeit>` | `funktion:core/.../Strich.kt#Strich.fuegeHinzu/1` |

Pakete tragen den Modulpfad, weil derselbe Paketname in mehreren Modulen vorkommen kann. Die Funktions-Id ist vorläufig und wird in Etappe 4 festgezurrt.

Aufbau der Datei:

```json
{
  "schema": 1,
  "daidalos": "0.1.0",
  "ziel": {
    "name": "Beispiel",
    "git_commit": "3f2a…",
    "git_aenderungen": false
  },
  "knoten": [
    {
      "id": "datei:core/src/main/kotlin/a/b/Strich.kt",
      "art": "datei",
      "pfad": "core/src/main/kotlin/a/b/Strich.kt",
      "sprache": "kotlin",
      "zeilen": 120,
      "bytes": 3456,
      "hash": "sha256:9c1e…"
    }
  ],
  "kanten": [],
  "befunde": []
}
```

- `ziel.git_commit`: HEAD des Zielrepos, `null` ohne Git. `ziel.git_aenderungen`: ob es nicht committete Änderungen an erfassten Dateien gibt, `null` ohne Git.
- `zeilen`: Anzahl Zeilen nach Umwandlung von CRLF und CR in LF. Bei Binärdateien fehlt das Feld.
- `bytes`: Größe auf der Platte.
- `hash`: SHA-256 über den Inhalt **nach** Umwandlung der Zeilenenden, bei Binärdateien über die rohen Bytes. Volle Länge, Präfix `sha256:`.
- Knoten sortiert nach `id`, später Kanten nach `(von, nach, art)`, Befunde nach `id`.

### 4. Konfiguration: `daidalos.toml` im Zielrepo
Modul `daidalos/konfiguration.py`. Die Datei ist optional. Format v1:

```toml
[scan]
# gitwildmatch-Muster wie in .gitignore, relativ zum Zielrepo
ausschliessen = [".claude/worktrees/", "build/", "docs/prototypen/daten/"]

# Fremdcode (eingebundene Bibliotheken): wird erfasst, aber als fremd markiert
fremd = ["**/src/main/cpp/fremd/"]

[editor]
befehl = "code -g {datei}:{zeile}"
```

- Dateien, die auf ein `fremd`-Muster passen, bekommen im Knoten `"fremd": true`. Sie bleiben in der Ausgabe, damit die Karte sie eingeklappt zeigen kann; spätere Analysen melden für sie keine Befunde. Bei eigenen Dateien fehlt das Feld.

- Eingebaute Ausschlüsse, die immer gelten: `.git/`, `.gradle/`, `.idea/`, `.vscode/`, `.kotlin/`, `node_modules/`, `__pycache__/`, `build/`, `out/`, sowie für Unreal `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/`. Außerdem immer `docs/daidalos/` selbst, damit sich Daidalos nicht selbst misst.
- `[editor]` wird nur gelesen und mit Standardwert versehen, benutzt wird es erst später.
- Unbekannte Abschnitte und Schlüssel: Warnung auf stderr, kein Abbruch (spätere Versionen fügen `[markierungen]` usw. hinzu). Falsche Typen: klare Fehlermeldung mit Dateiname und Schlüssel, Abbruch.
- Konfiguration als unveränderliche Dataclass.

### 5. Scanner
Modul `daidalos/scanner.py`, Endungstabelle in `daidalos/sprachen.py`.

- **Dateien finden:**
  - Ist das Ziel ein Git-Repo, liefert `git -c core.quotepath=off ls-files --cached --others --exclude-standard -z` die Kandidaten. So gilt `.gitignore` genau wie bei Git. Einträge, die auf `/` enden (verschachtelte Repos, Worktrees), und Einträge, die auf der Platte nicht mehr existieren, werden übersprungen.
  - Ohne Git: Verzeichnis durchlaufen, `.gitignore` im Wurzelordner per `pathspec` beachten. **Ausgeschlossene Ordner werden gar nicht erst betreten** (bei `os.walk` mit `topdown=True` aus `dirnames` entfernen, bevor abgestiegen wird). Hintergrund: In Sketchorus liegen unter einem ausgeschlossenen Ordner rund 160 GB Messdaten; ein Durchlauf, der erst hinterher filtert, wäre unbrauchbar. Dafür einen Test schreiben, der nachweist, dass ein ausgeschlossener Ordner nie gelistet wird.
  - Ist das Ziel ein Git-Repo, aber `git` nicht aufrufbar: Warnung und Rückfall auf den Durchlauf.
  - Danach eingebaute Ausschlüsse und `[scan].ausschliessen` per `pathspec` (gitwildmatch) anwenden.
  - Symlinks nicht verfolgen.
- **Sprache** nach Endung bzw. Dateiname: mindestens kotlin (`.kt`, `.kts` → `kotlin`; `build.gradle.kts`/`settings.gradle.kts` → `gradle-kotlin`), java, c, cpp (`.cpp .cc .cxx .h .hpp .hh .inl`), csharp, python, verse, markdown, json, toml, yaml, xml, ini, shell, powershell, batch, cmake (`CMakeLists.txt`, `.cmake`), groovy-gradle (`build.gradle`), properties, text. Alles andere `unbekannt`. Binär ist eine Datei, wenn die ersten 8 KiB ein Null-Byte enthalten, dann `sprache: "binaer"`.
- Große Dateien (> 5 MiB): hashen, aber keine Zeilen zählen, Feld `zeilen` fehlt.
- Lesefehler einer Datei bricht den Lauf nicht ab: Warnung, Datei mit `"lesefehler": true` und ohne Hash aufnehmen.
- Git-Aufrufe über eine kleine Hilfsfunktion mit `subprocess.run([...], check=True, capture_output=True)`, ohne Shell.

### 6. Export
Modul `daidalos/export.py`: `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)`, UTF-8, Zeilenende LF (`newline="\n"`), abschließender Zeilenumbruch. Zielordner anlegen. Schreiben über temporäre Datei und `os.replace`, damit nie eine halbe Datei liegen bleibt.

### 7. CLI
`daidalos/cli.py` mit `argparse`, Einstieg über `[project.scripts] daidalos = "daidalos.cli:main"` und `python -m daidalos`.

```
daidalos scan [ZIEL] [--ausgabe DATEI] [--konfiguration DATEI]
daidalos --version
```

- `ZIEL` Standard: aktuelles Verzeichnis. `--ausgabe` Standard: `<ZIEL>/docs/daidalos/daidalos.json`. `--konfiguration` Standard: `<ZIEL>/daidalos.toml`; so lässt sich ein Repo messen, ohne dort eine Datei anzulegen.
- Nach dem Lauf eine kurze Zusammenfassung auf stdout: Anzahl Dateien, Zeilen gesamt, Top-Sprachen nach Dateien, Pfad der Ausgabe, Laufzeit. (Laufzeit nur auf stdout, nie in die JSON.)
- Exit-Code 0 bei Erfolg, 2 bei Bedienfehler (Ziel existiert nicht, Konfiguration falsch), 1 bei unerwartetem Fehler.

### 8. Tests
Unter `tests/`, Beispielprojekt `tests/beispiele/mini_gradle/` (erfunden): `settings.gradle.kts` mit `:core` und `:app`, je ein `build.gradle.kts`, drei bis vier kleine `.kt`-Dateien in `src/main/kotlin/...`, ein `build/`-Ordner mit Müll, eine `README.md`, eine kleine Binärdatei, eine `.gitignore` mit einem Eintrag, eine `daidalos.toml` mit einem eigenen Ausschluss, eine Datei mit CRLF-Zeilenenden.

Tests mindestens für:
- Ausschlüsse greifen (eingebaut, `daidalos.toml`, `.gitignore`), sowohl im Git-Modus (Test legt in `tmp_path` per `git init` ein Repo aus einer Kopie des Beispiels an und committet) als auch ohne Git.
- Verschachteltes Repo/Worktree unter `.claude/worktrees/x/` wird nicht erfasst.
- Determinismus: zwei Läufe ergeben byte-gleiche Dateien.
- CRLF- und LF-Fassung derselben Datei ergeben denselben Hash und dieselbe Zeilenzahl.
- Sprache, Binärerkennung, Lesefehler.
- Konfiguration: fehlt, gültig, unbekannter Schlüssel (Warnung), falscher Typ (Fehler).
- CLI: Exit-Codes, Standard-Ausgabepfad.
- Golden-Test: Ausgabe für das Beispielprojekt ohne Git (also `git_commit: null`) gegen `tests/erwartet/mini_gradle.daidalos.json`. Ein Schalter `--aktualisiere-golden` für pytest (über `conftest.py`) schreibt die Datei neu.

### 9. CI
`.github/workflows/pruefung.yml`: bei Push und Pull Request, Matrix `ubuntu-latest` und `windows-latest`, Python 3.12, `astral-sh/setup-uv`, dann `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`.

### 10. Probe an Sketchorus (nur lokal)
- Gemessen wird die eingefrorene Kopie `lokal\sketchorus-kopie` aus A01, nicht das Original, weil im Original parallel gearbeitet wird und der Determinismus-Vergleich sonst nicht aussagekräftig ist. Lege dort keine Datei an. Lege die Konfiguration unter `lokal\sketchorus\daidalos.toml` ab (Ausschlüsse `.claude/worktrees/`, `build/`, `docs/prototypen/daten/`; fremd `**/src/main/cpp/fremd/`) und starte
  `uv run daidalos scan lokal\sketchorus-kopie --konfiguration lokal\sketchorus\daidalos.toml --ausgabe lokal\sketchorus\daidalos.json`.
- Prüfe: keine Datei aus `.claude/worktrees/` oder `build/` in der Ausgabe; zweiter Lauf byte-gleich; Laufzeit notieren. Gegenprobe mit dem Steckbrief `lokal/A01-steckbrief-sketchorus.md`, Abschnitt 6: Die Zahl der erfassten Dateien sollte bei rund 1 071 liegen (plus nicht getrackte, nicht ignorierte Dateien), 111 davon fremd. Weicht es deutlich ab, im Bericht erklären. Ergebnisse nur in den Bericht (Zahlen, keine Dateinamen).

### 11. Abschluss
- Branch `auftrag/a02-fundament`, pushen. Nicht nach `main` mergen, das macht Manu nach der Prüfung.
- Bericht `docs/auftraege/A02-bericht.md` (ohne Sketchorus-Inhalte, Zahlen sind in Ordnung).
- Antworte mir zum Schluss mit höchstens 10 Zeilen: Stand, Abweichungen, offene Fragen.

## Abnahmekriterien

- [ ] `uv sync && uv run pytest` grün unter Windows; CI grün auf Linux und Windows.
- [ ] `uv run daidalos scan tests/beispiele/mini_gradle` erzeugt eine Ausgabe gemäß `docs/datenformat.md`.
- [ ] Zwei Läufe auf Sketchorus sind byte-gleich, keine ausgeschlossenen Pfade enthalten.
- [ ] `CLAUDE.md`, `docs/architektur.md`, `docs/datenformat.md`, Bericht vorhanden.
- [ ] Nichts aus Sketchorus im Repo.

## Nicht in diesem Auftrag

tree-sitter, Gradle-Adapter, Kotlin-Importe, Kanten, Zyklen (alles A03), Karte, Skill.
