# Bericht A02 – Fundament: Projektgerüst, Konfiguration und Scanner

Stand 2026-11-22. Branch `auftrag/a02-fundament`, nicht nach `main` gemergt.

## Was gemacht wurde

| Schritt | Ergebnis |
| --- | --- |
| 1. Repo-Grundlage | `.gitignore` (mit `lokal/`), `.gitattributes` (`* text=auto eol=lf`; CRLF-Beispiel `-text`, `.bin` `binary`), `README.md`, `LICENSE` (MIT, Manuel Grimm, 2026). `docs/architektur.md` und `docs/auftraege/` unverändert committet. |
| 2. `CLAUDE.md` | Leitplanken 1–6, Sprache, Arbeitsweise, Befehle, Aufbau; rund 60 Zeilen. |
| 3. `docs/datenformat.md` | `daidalos.json` mit `schema: 1`, Id-Schema für alle Knotenarten, Datei-Knoten, Sprachtabelle, Determinismus; dazu `daidalos.toml` v1 und die Regeln, welche Dateien erfasst werden. |
| 4. Konfiguration | `daidalos/konfiguration.py`: unveränderliche Dataclasses, Standardwerte, Warnung bei Unbekanntem, `KonfigurationsFehler` bei falschen Typen und kaputtem TOML. |
| 5. Scanner | `daidalos/scanner.py`, `daidalos/sprachen.py`: Git-Modus über `git ls-files`, sonst Durchlauf, der ausgeschlossene Ordner nicht betritt; Hash und Zeilen nach Normierung der Zeilenenden (auch blockweise über Blockgrenzen), Binärerkennung, große Dateien, Lesefehler. |
| 6. Export | `daidalos/export.py`: sortiert, UTF-8, LF, atomar über temporäre Datei und `os.replace`. |
| 7. CLI | `daidalos scan [ZIEL] [--ausgabe] [--konfiguration]`, `--version`, `python -m daidalos`; Exit-Codes 0/1/2. |
| 8. Tests | 80 Tests (79 grün, 1 unter Windows übersprungen, siehe unten), Beispielprojekt `tests/beispiele/mini_gradle/`, Golden-Datei `tests/erwartet/mini_gradle.daidalos.json`, Schalter `--aktualisiere-golden`. |
| 9. CI | `.github/workflows/pruefung.yml`, Matrix Ubuntu/Windows, Python 3.12, setup-uv. |
| 10. Probe Sketchorus | siehe unten. |

Lokal unter Windows: `uv run ruff check`, `uv run ruff format --check` und `uv run pytest` grün.

## Probe an der eingefrorenen Kopie (nur Zahlen)

Gemessen wurde `lokal/sketchorus-kopie` mit der Konfiguration aus `lokal/sketchorus/daidalos.toml`;
Host: Win11-PC, Git-Modus.

| Größe | Wert |
| --- | --- |
| Erfasste Dateien | 1 074, davon fremd 111 |
| Zeilen gesamt | 228 396 |
| Dateien aus `.claude/worktrees/`, `build/`, `docs/prototypen/daten/` | 0 |
| Lesefehler | 0 |
| Zweiter Lauf | byte-gleich |
| Laufzeit | 4,58 s beim ersten Lauf (kalter Datei-Cache), 0,34 s beim zweiten |
| `ziel.git_aenderungen` | `true` (die Kopie hat nicht committete Änderungen) |

**Gegenprobe mit dem Steckbrief (Abschnitt 6):** 1 071 getrackte Dateien nach Ausschlüssen,
dazu 8 nicht getrackte, nicht ignorierte. 5 davon liegen in `docs/prototypen/daten/` und sind
ausgeschlossen, bleiben 3. 1 071 + 3 = 1 074, stimmt also genau. Auch die 111 fremden Dateien
stimmen.

**Zum Vergleich ohne Git (Verzeichnisdurchlauf, nur Dateiliste):** 1 128 Dateien in 0,05 s. Alle
1 074 aus dem Git-Modus sind dabei. Die 54 zusätzlichen liegen alle in einem Unterordner mit eigener
`.gitignore`. Der Durchlauf beachtet laut Auftrag nur die `.gitignore` im Wurzelordner; Git wertet
auch die verschachtelten aus. Das ist erwartet, siehe offene Fragen.

## Abweichungen und Entscheidungen

1. **„Ist ein Git-Repo“ heißt: `.git` liegt direkt im Ziel** (Ordner oder Datei). Ein Unterordner
   eines fremden Repos zählt nicht. Grund: Sonst würde `daidalos scan tests/beispiele/mini_gradle`
   das Daidalos-Repo selbst befragen, und der Golden-Test ohne Git wäre nicht möglich.
2. **Eingebauter Ausschluss `docs/daidalos/` ist an den Wurzelordner gebunden**
   (`/docs/daidalos/`), weil die Ausgabe genau dort liegt. Die übrigen eingebauten Ausschlüsse
   gelten in jeder Tiefe.
3. **Ordner mit eigenem `.git` werden auch im Durchlauf übersprungen**, wie es Git tut. So ist ein
   Worktree unter `.claude/worktrees/x/` in beiden Modi nicht erfasst.
4. **Symlinks** werden weder verfolgt noch als Datei erfasst. Der zugehörige Test läuft unter
   Windows ohne Symlink-Rechte nicht (übersprungen), wohl aber in der CI unter Linux.
5. **`git_aenderungen`** zählt auch nicht getrackte, aber erfasste Dateien als Änderung, weil sie
   nicht committet sind. Änderungen an ausgeschlossenen Dateien zählen nicht.
6. **Git-Fehler** (nicht aufrufbar *oder* Aufruf scheitert, etwa wegen „dubious ownership“) führen
   beide zu Warnung und Rückfall auf den Durchlauf.
7. **Lesefehler-Knoten** behalten `sprache` (nach Endung) und, wenn `stat` gelang, `bytes`; `hash`
   und `zeilen` fehlen.
8. **Ignorierte Testdateien force-added:** `build/` und `*.log` sind in den `.gitignore`-Dateien
   (Daidalos bzw. Beispielprojekt) ignoriert. Die Mülldateien des Beispiels sind deshalb mit
   `git add -f` getrackt, damit Tests und CI sie sehen.
9. **Kein Commit auf `main`:** `main` hatte noch keinen Commit. Alles liegt auf
   `auftrag/a02-fundament`, auf GitHub gibt es `main` damit noch nicht. Für einen Pull Request muss
   `main` zuerst entstehen (etwa aus dem ersten Commit dieses Branches).
10. **Ausgabe-Beispiel in `docs/datenformat.md`** zeigt die Schlüssel sortiert, so wie die Datei
    tatsächlich geschrieben wird.
11. **Zusätzliche Endungen** über die Mindestliste hinaus (z. B. `.pyi`, `.bash`, `.psm1`, `.cmd`,
    `.yml`, `.markdown`, `settings.gradle`). `.gitignore`, `.sql`, `.lockfile` u. ä. bleiben
    `unbekannt`.

## Offene Fragen

1. **Verschachtelte `.gitignore` im Durchlauf:** Sollen auch `.gitignore`-Dateien in Unterordnern
   beachtet werden? Das würde den Durchlauf an den Git-Modus angleichen (bei der Probe 54 Dateien
   Unterschied). Vorschlag: ja, in einem späteren Auftrag.
2. **Groß- und Kleinschreibung der Muster unter Windows:** Die Muster gelten derzeit
   case-sensitiv (wie Git mit `core.ignorecase=false`). Unter Windows könnte `Build/` damit
   durchrutschen. Bisher ohne praktische Folge.
3. **Sprachen für häufige `unbekannt`-Endungen** (bei der Probe 33 Dateien, z. B. SQL, Lockfiles):
   Sollen sie eigene Sprachen bekommen?

## Nächste sinnvolle Schritte

- Manu: Branch prüfen, `main` anlegen und mergen; danach prüfen, ob die CI auf GitHub grün ist
  (lokal ist nur Windows getestet).
- A03: Gradle-Adapter, Kotlin-Importe, Kanten, Zyklen; tree-sitter und networkx kommen hinzu.
