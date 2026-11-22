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

## Dokumentation

- [docs/architektur.md](docs/architektur.md): verbindliche Architektur
- [docs/datenformat.md](docs/datenformat.md): Aufbau von `daidalos.json`, `deutung.json` und
  `daidalos.toml`
- [docs/auftraege/](docs/auftraege/): Aufträge und Berichte

## Lizenz

MIT, siehe [LICENSE](LICENSE).
