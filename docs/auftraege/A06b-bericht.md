# Bericht A06b – Zielrepo als Klon mit festem Stand

Stand 2026-11-23. Branch `auftrag/a06b-klon` von `main` (`4be7a0a`), nicht nach `main` gemergt.

## Was gemacht wurde

### Werkzeug `werkzeuge/ziel_auffrischen.py`

- Liest `lokal/ziele.toml`. Fehlt die Datei, legt es sie mit einem auskommentierten Beispiel an und
  endet mit Exit-Code 2. Je Ziel gibt es `quelle`, `klon` und `ausgabe` als Pflichtfelder sowie
  optional `konfiguration` und `zweig`. Unbekannte Schlüssel gelten als Fehler. Pfade sind relativ
  zur Daidalos-Wurzel oder absolut.
- Vor jedem Git-Aufruf wird geprüft:
  - Der Klon liegt unter `lokal/` und nicht in der Quelle.
  - Die Ausgabe liegt nicht im Klon, sonst würde `git clean -fdx` sie löschen.
  - Die Quelle ist ein Git-Repo.
  - Eine angegebene Konfiguration existiert.
- Vor dem Zurücksetzen wird außerdem geprüft, dass der Klon die Wurzel eines eigenen Repos ist und
  dass `remote.origin.url` auf die Quelle zeigt. Der Vergleich läuft über aufgelöste Pfade.
- Fehlt der Klon, wird er mit `git clone --no-hardlinks --config core.autocrlf=false` angelegt.
  Sonst laufen `fetch --prune origin`, `checkout --detach`, `reset --hard` und `clean -fdx`, alles
  nur im Klon.
- Ist der Commit gleich dem in der vorhandenen `daidalos.json`, endet das Werkzeug mit „Stand
  unverändert: <commit>“. `--erzwingen` scannt trotzdem.
- `scan` und `render` laufen im selben Prozess über `daidalos.cli.main`, mit `--ausgabe`,
  `--daten`, `--deutung` (falls vorhanden) und `--konfiguration`.
- Am Ende gibt das Werkzeug aus:
  - den Commit (kurz) mit Betreff,
  - die Zahl der Dateien,
  - die Zahl der offenen Deutungen (dieselbe Rechnung wie `deutung pruefen`),
  - die Zeile `Für den Skill: …` mit Ziel, `--daten`, `--deutung`, `--ausgabe` und
    `--konfiguration`.
- Exit-Codes: 0 bei Erfolg, 1 bei offenen Deutungen, 2 bei Fehlern. Netzwerk wird nur für den
  lokalen `git fetch` genutzt.

### Nachrangige Einschätzungen

- In der Karte erscheinen Einschätzungen ohne `prioritaet` in der gewichteten Befundliste mit einem
  leeren, gestrichelten Kreis statt einer Zahl. Neben dem Titel steht ein kleines, gedämpftes
  Zeichen „nachrangig“. In der Seitenleiste des Befunds steht dasselbe Zeichen statt
  „Priorität N“.
- `KARTE.md` zeigt zuerst die priorisierten Einschätzungen als nummerierte Liste. Danach folgen die
  nachrangigen als `- <sub>nachrangig</sub> **Titel** (…)`. Vorher wurden alle Einschätzungen
  fortlaufend nummeriert, auch die ohne Priorität.
- Das Beispiel `mini_modulgraph` hat eine nachrangige Einschätzung zur fehlenden JNI-Brücke
  bekommen. Golden-Dateien (`KARTE.md`, Zusammenfassung, Prüfsumme der Kartendaten) sind neu
  geschrieben.

### Tests

- `tests/test_ziel_auffrischen.py` arbeitet an einem Git-Repo aus `mini_gradle` in `tmp_path`. Die
  Wurzel wird über `--wurzel` gesetzt. Geprüft wird:
  - Der erste Lauf legt den Klon an, ohne Alternates; `git_aenderungen` ist `false`, und die Zeile
    für den Skill wird ausgegeben.
  - Nach einem neuen Commit in der Quelle wird der neue Stand gescannt. Eine uncommittete geänderte
    oder neue Datei der Quelle erscheint nicht.
  - Der zweite Lauf meldet „Stand unverändert“, `--erzwingen` scannt trotzdem.
  - Fremde Dateien und Änderungen im Klon werden entfernt.
  - Exit-Code 2, wenn `origin` nicht zur Quelle passt (der Klon bleibt dann unberührt), wenn der
    Klon außerhalb von `lokal/` liegt (auch über `..`) und wenn `ziele.toml` fehlt (die Datei wird
    dabei angelegt).
  - Exit-Code 0 bei vollständiger Deutung.
- Golden-Test für `KARTE.md` und ein eigener Test für die Zeile mit „nachrangig“.
- Browser-Probe `test_nachrangige_einschaetzung_ohne_zahl`: kein Zahlenkreis, das Zeichen ist
  gedämpft, und es erscheint auch in der Seitenleiste des Befunds.
- `ruff check`, `ruff format --check`, `pytest`: **254 bestanden, 1 übersprungen**, lokal unter
  Windows mit Browser-Probe.

### Doku

- `CLAUDE.md`: eine Zeile unter Befehle.
- `README.md`: Abschnitt „Ein Repo in Bewegung kartieren“.
- `SKILL.md`: ein Hinweis, gekennzeichnet als „Nur für die Entwicklung im Daidalos-Repo“.
- `docs/datenformat.md`: wie das Zeichen „nachrangig“ in Karte und `KARTE.md` erscheint.

## Sketchorus umgestellt (nur lokal)

- `lokal/ziele.toml` enthält den Eintrag `sketchorus`.
- Die `daidalos.toml` der Probe liegt jetzt unter `lokal/ziele/sketchorus/daidalos.toml`.
- `deutung.json` wurde nach `lokal/ziele/sketchorus/daidalos/` kopiert.

| Schritt | Ergebnis |
| --- | --- |
| Erster Lauf | Klon angelegt, 1076 Dateien, rund 12 s (Klon, Scan, Render) |
| Offen nach dem Auffrischen | **1**: Beschreibung von `ordner:docs` veraltet. Seit dem Stand der alten Kopie kamen 2 Commits dazu, im Ordner `docs/` neue Aufträge, ein Zwischenstand und Messdaten. Alle 163 übrigen Beschreibungen, 18 Einschätzungen und 6 Kantentexte gelten weiter. |
| Skill nach `SKILL.md` | Zusammenfassung, Arbeitsblatt für `ordner:docs`, Ordnerinhalt geprüft. Der Satz stimmt weiter und wurde unverändert neu übernommen. **1 Knoten neu gedeutet**, `deutung pruefen` meldet 0. Zeit nach der Uhr des Rechners: 01:00:39 bis 01:00:56, also unter einer Minute. |
| Render | Karte und `KARTE.md` in `lokal/ziele/sketchorus/daidalos/`, 11 nachrangige Einschätzungen mit Zeichen |
| Zweiter Lauf | „Stand unverändert: <commit>“, Exit-Code 0 |
| Quelle | HEAD, `git status` (583 Einträge) und `worktree list` vor und nach dem Lauf gleich |

`lokal/sketchorus-kopie` (647 MB) ist gelöscht, nachdem Scan, Deutung und Render am Klon gelaufen
waren. Die Kopie hatte ein eigenes `.git` und war nicht als Worktree bei Sketchorus eingetragen.
`lokal/sketchorus/` mit den älteren Ergebnissen bleibt.

Bildschirmfoto: `lokal/A06b-nachrangig.png`. Es zeigt die gewichteten Befunde 6 und 7 und darunter
die ersten nachrangigen Einschätzungen.

## Kein „nicht committet“ mehr

Die Karte des Klons zeigt den Hinweis nicht; in der Messung steht `git_aenderungen: false`. Eine
Ursachensuche war nicht nötig. Der Hinweis kam bisher daher, dass die Kopie den Arbeitsbaum samt
uncommitteter Änderungen enthielt. Den beiden Kandidaten aus dem Auftrag beugt das Werkzeug vor:

- Die Ausgabe im Klon ist verboten.
- Der Klon wird mit `core.autocrlf=false` angelegt. Damit gilt nur die `.gitattributes` des Ziels,
  und eine globale Einstellung `core.autocrlf=true` kann keine Scheinänderungen erzeugen.

## Abweichungen vom Auftrag

1. **Standardzweig:** Ohne `zweig` gilt `origin/HEAD` des Klons. Das ist der Zweig, auf dem die
   Quelle beim Klonen stand. Bei einem lokalen Repo gibt es keinen anderen „Standardzweig“. So
   bleibt das Verhalten fest, auch wenn in der Quelle kurz ein anderer Zweig ausgecheckt ist.
2. **Zusätzliche Schutzprüfungen:** Neben `lokal/` und `origin` prüft das Werkzeug auch:
   - Der Klon ist die Wurzel eines eigenen Repos.
   - Die Ausgabe liegt nicht im Klon.
3. **„Stand unverändert“** vergleicht mit dem Commit in der vorhandenen `daidalos.json` und nicht
   mit dem vorigen HEAD des Klons. So wird auch nach einem abgebrochenen Scan neu gescannt.
4. **Werkzeug ruft `daidalos` im Prozess auf** statt über einen Unterprozess. Das ist schneller und
   nutzt dieselbe Umgebung.

## Offene Fragen

- Soll `ziel_auffrischen.py` später in das Programm wandern (etwa `daidalos ziel auffrischen`),
  oder bleibt es ein Entwicklerwerkzeug?
- Ist `<sub>nachrangig</sub>` in `KARTE.md` so recht? Auf GitHub erscheint es klein. In reinem Text
  stehen die Tags sichtbar da.

## Nächste sinnvolle Schritte

- Nach jedem größeren Sketchorus-Commit das Werkzeug laufen lassen und den Skill nur bei Exit-Code
  1 starten.
- Auf Wunsch eine Option `--nur-pruefen`, die ohne Scan nur sagt, ob die Quelle einen neuen Commit
  hat.
