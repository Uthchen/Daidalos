# CLAUDE.md – Daidalos

Daidalos misst, wie die Teile einer Codebase miteinander verflochten sind, und zeichnet daraus eine
Karte für menschliche Entwickler. Das Programm misst nur; Deutungen schreibt ein eigener Skill.

Verbindlich: [docs/architektur.md](docs/architektur.md) (Architektur) und
[docs/datenformat.md](docs/datenformat.md) (Aufbau von `daidalos.json` und `daidalos.toml`).

## Leitplanken

1. **Messen und Deuten bleiben getrennt.** Das Programm schreibt nur Gemessenes in `daidalos.json`,
   nie Deutungen. Den Inhalt von `deutung.json` schreibt nur der Skill; `daidalos deutung
   uebernehmen` setzt dabei nur Hashes ein, prüft Ids und speichert.
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
uv run daidalos render <zielrepo>         # karte.html und KARTE.md erzeugen
uv run daidalos pfad VON NACH --daten D   # kürzester belegter Weg
uv run daidalos aufrufe ID --daten D      # Baum der erreichbaren Funktionen (--rueckwaerts, --tiefe N, --unsicher)
uv run daidalos markierung --daten D      # Grenzkanten der Markierungs-Kette (--datei D, --unsicher)
uv run daidalos zusammenfassung <zielrepo>          # Übersicht und Offenes für den Skill
uv run daidalos arbeitsblatt KNOTEN <zielrepo>      # Arbeitsblatt für Modul, Paket oder Datei
uv run daidalos deutung uebernehmen E.json <zielrepo>   # Entwurf prüfen, Hashes einsetzen
uv run daidalos deutung pruefen <zielrepo>          # Exit 0, wenn nichts offen ist
uv run daidalos fuehrung uebernehmen E.json <zielrepo>  # Führung prüfen, Hashes einsetzen
uv run daidalos fuehrung pruefen [NAME] <zielrepo>  # Exit 0, wenn nichts veraltet oder kaputt ist
uv run daidalos fuehrung liste <zielrepo>           # Führungen mit Stand
uv run playwright install chromium        # einmalig, für die Browser-Probe (Marker browser)
uv run python werkzeuge/hole_vendor.py --pruefen   # Prüfsummen der eingebetteten Bibliotheken
uv run python werkzeuge/ziel_auffrischen.py NAME  # Klon eines Ziels aus lokal/ziele.toml auffrischen, scannen, rendern
uv run python werkzeuge/ziel_auffrischen.py NAME --mit-detekt  # vorher detekt im Klon (Befehl aus lokal/ziele.toml)
uv run pytest                             # Tests
uv run pytest --aktualisiere-golden       # Golden-Dateien unter tests/erwartet/ neu schreiben
uv run ruff check                         # Lint
uv run ruff format                        # Formatieren
```

## Aufbau

- `src/daidalos/`: `cli.py` (Befehlszeile), `konfiguration.py` (`daidalos.toml`), `scanner.py`
  (Dateien finden und messen), `sprachen.py` (Endungstabelle), `export.py` (JSON schreiben),
  `struktur.py` (Module, Pakete, Kanten, Befunde, Metriken zusammensetzen), `aufloeser.py`
  (Kotlin-Namen → Datei-Kanten), `aufrufgraph.py` (Funktionsknoten, `ruft`-Kanten), `ids.py` (abgeleitete Ids: `ruft`-Kanten, Datei einer
  Funktion), `markierung_text.py` (`daidalos markierung`), `deutung.py` (`deutung.json` lesen und abgleichen), `fuehrung.py` (Führungen prüfen,
  Hashes, Stand je Schritt), `render.py`
  (`karte.html`, `KARTE.md`), `pfad.py` (`daidalos pfad`), `zusammenfassung.py` (Übersicht,
  wichtige Dateien, Offenes), `arbeitsblatt.py` (Arbeitsblätter); `deutung.py` auch für
  `deutung uebernehmen`.
- `skills/daidalos/`: der Skill (`SKILL.md`, `vorlagen/`); `.claude-plugin/`: Plugin und Marketplace.
- `src/daidalos/karte/`: `vorlage.html`, `karte.css`, `karte.js` (die Karte), `elk_lauf.js` (ELK im Web
  Worker mit Zeitgrenze), `vendor/`
  (Cytoscape.js, elkjs, cytoscape-elk mit `HERKUNFT.md`; byte-genau, siehe `.gitattributes`).
- `src/daidalos/adapter/`: `gradle.py`, `kotlin.py`, `kotlin_funktionen.py` (Funktionen, Klassen,
  Annotationen, rohe Aufrufe), `jni.py` (tree-sitter), `detekt.py` (SARIF), `baum.py` (Hilfen).
- `src/daidalos/analysen/`: `zyklen.py` (Zyklen, Einstiege, Trennstelle), `markierung.py` (Markierungs-Kette).
- `tests/beispiele/`: erfundene Mini-Projekte; `tests/erwartet/`: Golden-Dateien;
  `tests/plausibilitaet.py`: Testhilfe (Datei-Kanten gegen Gradle-Kanten).
