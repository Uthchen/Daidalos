# CLAUDE.md – Daidalos

Daidalos misst, wie die Teile einer Codebase miteinander verflochten sind, und zeichnet daraus eine
Karte für menschliche Entwickler. Das Programm misst nur; Deutungen schreibt ein eigener Skill.

Verbindlich: [docs/architektur.md](docs/architektur.md) (Architektur) und
[docs/datenformat.md](docs/datenformat.md) (Aufbau von `daidalos.json` und `daidalos.toml`).

## Leitplanken

1. **Messen und Deuten bleiben getrennt.** Das Programm schreibt nur Gemessenes in `daidalos.json`,
   nie Deutungen. `deutung.json` schreibt nur der Skill.
2. **Determinismus:** Gleicher Stand des Zielrepos ergibt eine byte-gleiche Ausgabe. Keine
   Zeitstempel, keine absoluten Pfade, keine Rechnernamen, stabile Sortierung.
3. **Unsicher statt raten:** Was sich nicht eindeutig auflösen lässt, wird als unsicher markiert und
   weder weggelassen noch geraten.
4. **Kein Netzwerk zur Laufzeit, keine Telemetrie.**
5. **Keine Inhalte privater Projekte im Repo** (das Repo ist öffentlich). Testdaten sind erfunden.
   Private Ablagen gehören nach `lokal/` (ignoriert).
6. **Datenformat:** Jede Änderung wird in `docs/datenformat.md` nachgetragen. Inkompatible
   Änderungen erhöhen `schema`.

## Sprache

Doku, Kommentare, Fehlermeldungen, CLI-Ausgaben, JSON-Schlüssel und Bezeichner auf Deutsch. In
Bezeichnern Umlaute umschreiben (`ae`, `oe`, `ue`, `ss`). Übliche Fachwörter bleiben (`hash`, `id`,
`git_commit`).

## Arbeitsweise

- Pro Auftrag ein Branch `auftrag/aNN-kurzname`, kleine, thematische Commits.
- Vor jedem Push grün: `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`.
- Am Ende jedes Auftrags ein Bericht `docs/auftraege/ANN-bericht.md`: was gemacht, Abweichungen vom
  Auftrag mit Grund, offene Fragen, nächste sinnvolle Schritte.
- Ist ein Auftrag unklar: die naheliegendste Lösung wählen und im Bericht begründen, statt anzuhalten.
- Nicht nach `main` mergen; das macht Manu nach der Prüfung.
- Plattformen: Windows und Linux. Pfade intern mit `pathlib`, in Ausgaben relativ zum Zielrepo und
  mit `/`.

## Befehle

```
uv sync                                   # Umgebung anlegen
uv run daidalos scan <zielrepo>           # Zielrepo scannen
uv run pytest                             # Tests
uv run pytest --aktualisiere-golden       # Golden-Dateien unter tests/erwartet/ neu schreiben
uv run ruff check                         # Lint
uv run ruff format                        # Formatieren
```

## Aufbau

- `src/daidalos/`: `cli.py` (Befehlszeile), `konfiguration.py` (`daidalos.toml`), `scanner.py`
  (Dateien finden und messen), `sprachen.py` (Endungstabelle), `export.py` (JSON schreiben).
- `tests/beispiele/`: erfundene Mini-Projekte; `tests/erwartet/`: Golden-Dateien.
