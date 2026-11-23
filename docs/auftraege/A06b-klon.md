# Auftrag A06b – Zielrepo als Klon mit festem Stand

**Etappe:** 3 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A06 (`4be7a0a`). Branch `auftrag/a06b-klon` von `main`. Kleiner Auftrag.

## Ziel

Sketchorus wird parallel entwickelt und ändert sich oft im Minutentakt. Scan und Deutung laufen deshalb nie am Arbeitsbaum, sondern an einem eigenen Git-Klon. Der Klon zeigt immer genau einen Commit und enthält keine halbfertigen Zwischenstände. Aufgefrischt wird er per Befehl. Danach deutet der Skill nur neu, was sich geändert hat. Am Repo `E:\Repositories\Sketchorus` ändert sich nichts, auch nicht dessen `.git`. Also kein `git worktree`, kein Hook und keine Konfiguration dort.

## Schritte

1. **Werkzeug `werkzeuge/ziel_auffrischen.py`** (allgemein, ohne Sketchorus-Namen im Code).
   - Liest die Ziele aus `lokal/ziele.toml`. Die Datei ist ignoriert und wird vom Werkzeug beim ersten Lauf mit einem kommentierten Beispiel angelegt, falls sie fehlt. Je Ziel gibt es:
     - `quelle`: Pfad zum echten Repo.
     - `klon`: zum Beispiel `lokal/ziele/<name>/klon`.
     - `ausgabe`: zum Beispiel `lokal/ziele/<name>/daidalos`.
     - `konfiguration`: optional, Pfad zu einer `daidalos.toml` außerhalb des Klons.
     - `zweig`: optional. Ohne Angabe gilt der Standardzweig der Quelle.
   - `uv run python werkzeuge/ziel_auffrischen.py NAME` macht Folgendes:
     1. Fehlt der Klon, legt es ihn an mit `git clone --no-hardlinks <quelle> <klon>`. `--no-hardlinks` sorgt dafür, dass der Klon keine Objektdateien mit der Quelle teilt.
     2. Sonst holt es den neuen Stand mit `git -C <klon> fetch origin` und setzt den Klon hart auf `origin/<zweig>`: `git checkout --detach`, danach `git reset --hard` und `git clean -fdx`. Das gilt **nur im Klon**. Vorher prüft das Werkzeug, dass der Pfad wirklich unter `lokal/` liegt und `remote.origin.url` gleich `quelle` ist. Sonst bricht es mit einer klaren Meldung ab.
     3. Ist der Commit unverändert und liegt `daidalos.json` schon vor, endet es mit „Stand unverändert: <commit>“. Mit `--erzwingen` läuft es trotzdem weiter.
     4. Es ruft `scan` und `render` mit `--ausgabe` und, falls angegeben, `--konfiguration` auf.
     5. Am Ende gibt es aus: Commit (kurz) und Betreff, Anzahl der Dateien, die Zahl offener Deutungen (aus `deutung pruefen` bzw. `zusammenfassung --json`) und die fertige Zeile für den Skill. Die Zeile enthält Ziel, `--daten`, `--deutung` und `--ausgabe`, damit man sie in Claude Code einfügen kann.
   - Exit-Codes: 0 bei Erfolg, 1 bei offenen Deutungen nach dem Render, 2 bei Fehlern (Git, Pfade, Konfiguration).
   - Kein Netzwerk außer dem lokalen `git fetch` von `quelle`.
2. **Sketchorus umstellen** (nur lokal).
   - Eintrag `sketchorus` in `lokal/ziele.toml` anlegen. Die bisherige `daidalos.toml` der Probe nach `lokal/ziele/sketchorus/daidalos.toml` übernehmen.
   - `deutung.json` aus `lokal/sketchorus/` nach `lokal/ziele/sketchorus/daidalos/` kopieren.
   - Auffrischen und scannen. **Berichten, wie viel offen ist.** Erwartet: Die meisten Beschreibungen gelten weiter, weil die Hashes CRLF→LF normalisieren. Neu fällig ist nur, was sich zwischen der Kopie und dem aktuellen Commit geändert hat.
   - Den Skill einmal genau nach `SKILL.md` laufen lassen, bis `deutung pruefen` 0 meldet. Zeit und Anzahl neu gedeuteter Knoten berichten.
   - Danach `lokal/sketchorus-kopie` löschen, aber erst, wenn Scan, Deutung und Render am Klon gelaufen sind. Ältere Ergebnisse in `lokal/` bleiben.
3. **Kein „nicht committet“ mehr.** Die Karte des Klons darf den Hinweis „mit nicht committeten Änderungen“ nicht zeigen. Falls doch, ist die Ursache zu finden. Ein Kandidat ist die Ausgabe innerhalb des Klons, ein anderer ein Zeilenende-Unterschied.
4. **Nachrangige Einschätzungen kennzeichnen.** Einschätzungen ohne `prioritaet` bekommen in Seitenleiste und Befundliste ein kleines, gedämpftes Zeichen „nachrangig“ statt einer Prioritätszahl. Das gilt auch in `KARTE.md`.
5. **Doku.**
   - In `CLAUDE.md` unter Befehle eine Zeile für `ziel_auffrischen.py`.
   - In `README.md` ein kurzer Abschnitt „Ein Repo in Bewegung kartieren“. Er erklärt, warum ein Klon verwendet wird und wie man ihn auffrischt.
   - In `SKILL.md` ein Satz: Wenn der Benutzer ein Ziel aus `lokal/ziele.toml` nennt, zuerst das Werkzeug laufen lassen und dessen Pfade verwenden. Den Satz als Hinweis für die Entwicklung im Daidalos-Repo kennzeichnen.

## Tests

- **`ziel_auffrischen.py`** an einem erfundenen Mini-Repo, das der Test in `tmp_path` per Git erzeugt:
  - Erster Lauf legt den Klon an.
  - Ein neuer Commit in der Quelle wird nach dem Auffrischen gescannt.
  - Eine uncommittete Änderung in der Quelle erscheint **nicht** im Klon.
  - „Stand unverändert“ beim zweiten Lauf.
  - Abbruch mit Exit 2, wenn `origin` nicht zur Quelle passt oder der Klon außerhalb von `lokal/` liegt. Für den Test ist die Wurzel per Option einstellbar.
- Golden bzw. Browser-Probe für „nachrangig“.

## Abschluss

Branch pushen, nicht mergen. Bericht `docs/auftraege/A06b-bericht.md`. Antwort an mich mit höchstens 8 Zeilen. Bildschirmfoto der Befundliste mit „nachrangig“ nach `lokal/A06b-nachrangig.png`. Keine Sketchorus-Inhalte im Repo, auch nicht in `lokal/ziele.toml`-Beispielen.
