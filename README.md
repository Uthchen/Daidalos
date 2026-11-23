# Daidalos

Daidalos zeichnet eine Karte, die zeigt, wie die Teile einer Codebase miteinander verflochten sind,
und markiert, wo dieses Geflecht ungesund ist. Das Programm misst nur. Die Deutung (Namen, Texte,
Prioritäten) übernimmt ein eigener Skill, und beides liegt in getrennten Dateien.

Stand: Etappe 3. `daidalos scan` misst Dateien, Module, Pakete, Kanten und Zyklen,
`daidalos render` zeichnet daraus die offline lauffähige Karte `karte.html` und den Kurzbericht
`KARTE.md`, `daidalos pfad` zeigt den kürzesten belegten Weg zwischen zwei Knoten. Der Skill
`daidalos` für Claude Code deutet die Messung mit `daidalos zusammenfassung`, `daidalos
arbeitsblatt` und `daidalos deutung uebernehmen` / `pruefen`.

## Installation

Voraussetzung sind Python ≥ 3.12 und [uv](https://docs.astral.sh/uv/).

```
uv sync
```

## Aufruf

```
uv run daidalos scan <zielrepo>
uv run daidalos scan <zielrepo> --konfiguration <datei> --ausgabe <datei>
uv run daidalos render <zielrepo>
uv run daidalos pfad :app :core --daten <zielrepo>/docs/daidalos/daidalos.json
uv run daidalos zusammenfassung <zielrepo>
uv run daidalos arbeitsblatt :core <zielrepo>
uv run daidalos deutung uebernehmen entwurf.json <zielrepo>
uv run daidalos deutung pruefen <zielrepo>
uv run python -m daidalos --version
```

Ohne weitere Angaben liest Daidalos `<zielrepo>/daidalos.toml` (optional) und schreibt
`<zielrepo>/docs/daidalos/daidalos.json`. `render` liest diese Datei und, falls vorhanden,
`deutung.json` daneben und schreibt `karte.html` und `KARTE.md` in denselben Ordner.

Die Karte bettet Cytoscape.js (MIT), elkjs (EPL-2.0) und cytoscape-elk (MIT) ein; Herkunft und
Lizenzen stehen in [src/daidalos/karte/vendor/HERKUNFT.md](src/daidalos/karte/vendor/HERKUNFT.md).

Die Browser-Probe der Tests braucht Chromium: `uv run playwright install chromium`. Ohne Chromium
werden diese Tests übersprungen.

## Skill für Claude Code

Der Skill liegt in [skills/daidalos/SKILL.md](skills/daidalos/SKILL.md) und lässt sich als Plugin
in jedem anderen Repo installieren. Er ruft das Programm `daidalos` im Zielrepo auf; dafür muss es
als Werkzeug installiert sein:

```
uv tool install git+https://github.com/Uthchen/Daidalos
```

Für die Entwicklung aus dem lokalen Klon (Änderungen wirken sofort):

```
uv tool install -e E:\Repositories\Daidalos
```

Dann in Claude Code:

```
/plugin marketplace add Uthchen/Daidalos
/plugin install daidalos@daidalos
```

oder ohne Sitzung `claude plugin marketplace add Uthchen/Daidalos` und
`claude plugin install daidalos@daidalos`. Aufruf mit `/daidalos:daidalos` oder einfach „Karte
erstellen“, „Codebase-Karte aktualisieren“, „was hängt woran“. Der Skill schreibt nur in
`docs/daidalos/` und committet nicht.

## Ein Repo in Bewegung kartieren

Ändert sich ein Zielrepo laufend (parallele Entwicklung, Commits im Minutentakt), scannt man
besser nicht dessen Arbeitsbaum: Halbfertiges würde mitgemessen, und die Deutung liefe einem
wandernden Stand hinterher. Für die Entwicklung im Daidalos-Repo gibt es dafür
`werkzeuge/ziel_auffrischen.py`. Es hält je Ziel einen eigenen Git-Klon unter `lokal/`, der genau
einen Commit zeigt; am echten Repo ändert sich nichts.

Die Ziele stehen in `lokal/ziele.toml` (beim ersten Lauf mit einem Beispiel angelegt):

```toml
[beispiel]
quelle = "../MeinProjekt"                    # echtes Repo, wird nur gelesen
klon = "lokal/ziele/beispiel/klon"           # muss unter lokal/ liegen
ausgabe = "lokal/ziele/beispiel/daidalos"    # Messung, Deutung, Karte
konfiguration = "lokal/ziele/beispiel/daidalos.toml"  # optional
zweig = "main"                               # optional, sonst origin/HEAD des Klons
kopiere = ["local.properties"]               # optional: aus der Quelle, nicht in Git
detekt = ["gradlew.bat", "detekt"]           # optional: Befehl für --mit-detekt (im Klon)
umgebung = { JAVA_HOME = "C:/Java/jdk-21" }  # optional: Umgebung nur für den detekt-Befehl
```

`umgebung` ergänzt die eigene Umgebung nur für den detekt-Befehl, nicht für den Scan; Werte werden
wörtlich übernommen (keine Variablen-Ersetzung).

Auffrischen:

```
uv run python werkzeuge/ziel_auffrischen.py beispiel
```

Beim ersten Lauf entsteht der Klon (`git clone --no-hardlinks`), danach holt `git fetch` den neuen
Stand und der Klon wird hart auf `origin/<zweig>` gesetzt (vorher wird geprüft, dass er unter
`lokal/` liegt und `origin` die Quelle ist). Ist der Commit unverändert, endet das Werkzeug mit
„Stand unverändert“ (`--erzwingen` scannt trotzdem). Sonst laufen `scan` und `render`; am Ende stehen
Commit, Zahl der Dateien, Zahl der offenen Deutungen und die Zeile für den Skill. Der Skill deutet
danach nur, was sich geändert hat. Exit-Code 0 ohne Offenes, 1 mit offenen Deutungen, 2 bei Fehlern.

## Dokumentation

- [docs/architektur.md](docs/architektur.md): verbindliche Architektur
- [docs/datenformat.md](docs/datenformat.md): Aufbau von `daidalos.json`, `deutung.json` und
  `daidalos.toml`
- [docs/auftraege/](docs/auftraege/): Aufträge und Berichte

## Lizenz

MIT, siehe [LICENSE](LICENSE).
