# Bericht A06 – Skill v1: Daidalos deutet

Stand 2026-11-22. Branch `auftrag/a06-skill` von `main` (`8f4ed2a`), nicht nach `main` gemergt.

## Was gemacht wurde

### Teil 0 – Vorab aus A05b

| Punkt | Ergebnis |
| --- | --- |
| Mindestzoom | `MIN_ZOOM_FOKUS = LESBAR_PX_FOKUS / SCHRIFT_DATEI = 11 / 11,5 ≈ 0,957` in `karte.js`; die Schriftgröße der Datei-Kästen steht jetzt einmal in `SCHRIFT_DATEI` und wird für Stil, Breitenmessung und `LESBAR` genutzt. Behälter wie bisher. Test `test_fokus_zoom_haelt_dateinamen_lesbar` prüft, dass Zoom × Schriftgröße = 11 px ergibt. |
| Wackelnder Test | `test_editor_link_aus_file_seite` wartet über `warte_bis_ruhig_sichtbar` auf: Zustand „bereit“, keine Animation, Knoten sichtbar ganz im Bild und an derselben Stelle wie bei der vorigen Abfrage; nach dem Klick auf `letzterLink() !== null` statt fester Zeit. Die ganze Browser-Probe zehnmal hintereinander: 10 × 25 bestanden. |

### Teil 1 – Programmhilfen

- **`daidalos zusammenfassung`** (`zusammenfassung.py`): Markdown oder `--json`; Zahlen, Module und Ordner mit Gradle-Kanten, Pakete je Modul, wichtige Dateien mit Grund, Befunde in einer Zeile, **Offen**. Spalte „Deutung“ je Knoten (`ok`, `fehlt`, `veraltet`, `fremd`). Sketchorus: **248 Zeilen**.
- **`daidalos arbeitsblatt`** (`arbeitsblatt.py`): liest die Dateien neu mit dem Kotlin-Adapter; je Datei Kopf, deklariert, erste KDoc-Zeile, Kopfkommentar, nutzt / genutzt von mit Gewicht und Belegen, ADR-Nummern in Kommentaren. Module: wichtige Dateien voll, übrige als Kurzzeile mit erster Kommentarzeile, begrenzt auf etwa 400 Zeilen. C-Dateien: Pfad, Zeilen, Kanten. Sketchorus: 13 Blätter für Module und Ordner, zusammen 3 075 Zeilen, das größte **399 Zeilen**.
- **`daidalos deutung uebernehmen` / `pruefen`** (`deutung.py`): Entwurf ohne Hashes → Prüfung aller Ids und Pflichttexte → Hashes eingesetzt → Zusammenführung → deterministische Ausgabe. Unbekannte Ids: Exit-Code 2, Liste auf stderr, nichts geschrieben. `pruefen`: 0 / 1 (2 bei Bedienfehlern).
- `daidalos` schreibt stdout und stderr jetzt immer als UTF-8 (sonst kamen in Pipes unter Windows keine Umlaute beim Skill an).
- Doku: `docs/datenformat.md` (Entwurf, Einschätzung ohne Priorität, Zusammenfassung mit Auswahlregel, Arbeitsblatt, UTF-8), `docs/architektur.md` und `CLAUDE.md` (Leitplanke 1: das Programm setzt nur Hashes ein, prüft und speichert), README.

### Teil 2 – Skill

- `skills/daidalos/SKILL.md` mit Ablauf in neun Schritten, festen Regeln und Fragen über `daidalos pfad`; `skills/daidalos/vorlagen/entwurf-beispiel.json` (passt zu `mini_modulgraph`).
- Plugin: `.claude-plugin/plugin.json` und `.claude-plugin/marketplace.json` (Plugin an der Repo-Wurzel, `source: "./"`), geprüft gegen die aktuelle Doku (Pflichtfelder `name`, `owner`, `plugins`; Plugin nur `name`).
- `claude plugin validate .`: bestanden mit zwei Warnungen (`CLAUDE.md` an der Plugin-Wurzel wird nicht als Kontext geladen – gewollt, sie gehört zum Repo; kein Icon).
- **Installation in einem anderen Repo ausprobiert** mit Claude Code 2.1.330 und eigenem `CLAUDE_CONFIG_DIR` (damit Manus Einstellungen unberührt bleiben): `claude plugin marketplace add E:/Repositories/Daidalos` und `claude plugin install daidalos@daidalos` in einem leeren Git-Repo → installiert, aktiviert, Skill `daidalos:daidalos` vorhanden. Nach dem Push ebenso direkt von GitHub: `claude plugin marketplace add Uthchen/Daidalos#auftrag/a06-skill` und `claude plugin install daidalos@daidalos` → installiert, `skills/daidalos/SKILL.md` und `vorlagen/` im Plugin-Cache. Ohne `#…` gilt nach dem Merge `main`.
- Wheel geprüft: Karte und Bibliotheken sind enthalten, `uv tool install git+…` liefert also ein lauffähiges `daidalos`.

### Teil 3 – Tests

`test_zusammenfassung.py` (Golden Markdown und JSON je Beispiel, Auswahlregel an erfundenen Daten, Trennstelle eines Paketzyklus, Offen mit veralteter Beschreibung, zweiter Lauf ohne Offenes und gezielte Änderung), `test_arbeitsblatt.py` (Golden für Modul, Paket, Kotlin- und C-Datei, Größenbegrenzung, KDoc, Kopfkommentar, ADR, KDoc vor `annotation class`, geänderte Datei), `test_deutung_werkzeuge.py` (Hash eingesetzt, Zusammenführung und `entfernen`, unbekannte Ids ohne Schreiben, ungültige Entwürfe, Determinismus, Exit-Codes von `pruefen`), `test_skill.py` (SKILL.md nennt nur Befehle und Optionen aus dem `argparse`-Parser, jeder Befehl kommt vor, Frontmatter, Plugin-Dateien, Beispiel-Entwurf). `ruff check`, `ruff format --check`, `pytest`: **244 bestanden, 1 übersprungen** (lokal unter Windows, mit Browser-Probe).

## Teil 4 – Probe an Sketchorus (nur lokal)

Ablauf genau nach `SKILL.md` auf der eingefrorenen Kopie, Ausgabe nach `lokal/sketchorus/` (mit `--daten`, `--deutung`, `--ausgabe`, `--konfiguration`). Statt eines installierten Werkzeugs `uv run daidalos` aus dem Repo, damit nichts global installiert wird.

| Größe | Wert |
| --- | --- |
| Zeit (Uhr des Rechners, Scan bis Render) | 23:28 bis 23:35, rund 7 min |
| Zusammenfassung | 248 Zeilen |
| Arbeitsblätter | 13 (7 Module, 6 Ordner), 3 075 Zeilen, größtes 399 |
| Zusätzlich gelesen | Köpfe von 24 Dateien (meist dort, wo das Blatt keine KDoc zeigte) und 13 Belegstellen in 9 Dateien für die Einschätzungen |
| Ergebnis | 163 Beschreibungen (7 Module, 6 Ordner, 52 Pakete, 98 wichtige Dateien), 8 Bereiche, 18 Einschätzungen (7 mit Priorität), 6 Kantentexte (4 Trennstellen, 2 JNI-Brücken) |
| `deutung pruefen` | 0 offen, Exit-Code 0 |
| Zweiter Lauf ohne Änderung | Zusammenfassung „Nichts offen“, `pruefen` 0 |
| Eine Zeile an eine wichtige Datei des App-Moduls angehängt, neu gescannt | offen genau diese Datei, ihr Paket und ihr Modul (veraltet); `pruefen` 1. Neu übernommen → 0; Datei wiederhergestellt und abgeglichen |

Die drei wichtigsten Einschätzungen betreffen Kreise im Kern-Modul (ein Datei- und ein Paketkreis) und im App-Modul; jede Trennstelle hat Gewicht 1 und hängt an einer einzelnen Konstante oder einem Typ. Die Texte stehen nur in `lokal/sketchorus/deutung.json`.

Bildschirmfotos: `lokal/A06-seitenleiste.png` (Paket mit Beschreibung), `lokal/A06-befund.png` (Befund mit Einschätzung), `lokal/A06-befunde-liste.png` (gewichtete Befunde), `lokal/A06-bereiche.png` (Bereiche), `lokal/A06-kante.png` (Trennstelle mit Deutungstext). `deutung.json`, `KARTE.md`, `karte.html`, Zusammenfassungen und Arbeitsblätter liegen in `lokal/sketchorus/`.

### Was die Probe an Anleitung und Programm verbessert hat

- **Kopfkommentar:** Viele Dateien der Labor-Module beschreiben sich in einem `//`-Kopfkommentar statt in KDoc. Ohne ihn zeigten die Blätter dort nur „ohne KDoc“. Das Arbeitsblatt zeigt jetzt den Kommentar vor der ersten Deklaration, auch in den Kurzzeilen.
- **KDoc vor `annotation class`:** Nach Annotationszeilen (`@Target`, `@Retention`) liest die Grammatik die Deklaration nicht als eigenen Knoten; die KDoc der Markierungs-Annotationen fehlte. Behoben über den Zeilenbereich des Knotens nach der KDoc.
- **SKILL.md:** Hinweise auf `scan --ausgabe`, `render --ausgabe` und `--konfiguration` bei abweichendem Ablageort; mehrdeutige Suchbegriffe (ein Dateiname kam in zwei Modulen vor) mit Pfadende oder Id; welche Teile eines Blatts für Beschreibungen reichen und wann ein Blick in die Datei nötig ist.
- **UTF-8-Ausgabe** (siehe oben), gefunden beim ersten Aufruf aus einer Pipe.

## Abweichungen vom Auftrag

1. **Jeder Befund braucht eine Einschätzung.** Der Auftrag verlangt 3 bis 10 Einschätzungen, `pruefen` soll aber Befunde ohne Einschätzung melden und der zweite Lauf nichts Offenes zeigen. Sketchorus hat 18 Befunde. Lösung: 3 bis 10 Befunde bekommen `prioritaet` und `vorschlag`, die übrigen eine kurze Einschätzung **ohne** Priorität („nachrangig, weil …“). Das Format erlaubte fehlende Priorität schon; die Karte sortiert sie ans Ende. Beschrieben in `docs/datenformat.md` und `SKILL.md`.
2. **`entfernen` im Entwurf:** zusätzlicher Schlüssel, damit der Skill tote Verweise streichen kann, ohne `deutung.json` von Hand zu ändern. Nur im Entwurf, nicht in `deutung.json`.
3. **Ordner zählen wie Module:** Offen und `pruefen` verlangen auch für Ordner (etwa Doku- und Werkzeugordner) eine Beschreibung, weil sie auf der Modulebene der Karte neben den Modulen stehen.
4. **`--deutung` auch bei `arbeitsblatt`:** Das Blatt zeigt damit den Stand der Deutung je Knoten; sonst wie im Auftrag.
5. **Wichtige Dateien bei Paket- und Modulzyklen:** „Trennstelle eines Zyklus“ ist dort eine verdichtete Kante; aufgenommen werden die Dateien der Datei-Kanten darunter.
6. **Probe ohne `uv tool install`:** Statt das Werkzeug global zu installieren, lief die Probe mit `uv run daidalos`.

## Offene Fragen

- Sollen nachrangige Einschätzungen in der Karte eigens gekennzeichnet werden („ohne Priorität“), oder reicht die Sortierung ans Ende?
- Der größte Ordner hat 386 Dateien; sein Arbeitsblatt ist mit Kurzzeilen voll. Lohnt eine Unterteilung von Ordnern (z. B. nach zweitem Pfadteil) für die Deutung?
- Die Wahl „30 mit dem höchsten Fan-in“ ergibt bei Sketchorus 98 wichtige Dateien. Passt die Menge, oder soll die Schwelle für `modulkante` (Gewicht ≥ 3) höher?

## Nächste sinnvolle Schritte

- Nach dem Merge `uv tool install git+https://github.com/Uthchen/Daidalos` und den Skill in Sketchorus selbst laufen lassen (eigener Schritt nach Manus Freigabe).
- Die priorisierten Kreise in Sketchorus sind fast alle billig zu lösen (Trennstelle mit Gewicht 1); ein kleiner Auftrag dort könnte sie anhand von `lokal/sketchorus/deutung.json` auflösen.
- „Named in“ aus Floorplan (Namen in Skripten und Strings) ins Arbeitsblatt aufnehmen; bei Sketchorus verbindet es Auswerteskripte mit Kotlin-Formaten.
