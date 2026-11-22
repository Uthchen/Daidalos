# Daidalos

Daidalos zeichnet eine Karte, die zeigt, wie die Teile einer Codebase miteinander verflochten sind,
und markiert, wo dieses Geflecht ungesund ist. Das Programm misst nur. Die Deutung (Namen, Texte,
Prioritäten) übernimmt ein eigener Skill, und beides liegt in getrennten Dateien.

Stand: Etappe 3, erster Teil. `daidalos scan` misst Dateien, Module, Pakete, Kanten und Zyklen,
`daidalos render` zeichnet daraus die offline lauffähige Karte `karte.html` und den Kurzbericht
`KARTE.md`, `daidalos pfad` zeigt den kürzesten belegten Weg zwischen zwei Knoten.

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
uv run python -m daidalos --version
```

Ohne weitere Angaben liest Daidalos `<zielrepo>/daidalos.toml` (optional) und schreibt
`<zielrepo>/docs/daidalos/daidalos.json`. `render` liest diese Datei und, falls vorhanden,
`deutung.json` daneben und schreibt `karte.html` und `KARTE.md` in denselben Ordner.

Die Karte bettet Cytoscape.js (MIT), elkjs (EPL-2.0) und cytoscape-elk (MIT) ein; Herkunft und
Lizenzen stehen in [src/daidalos/karte/vendor/HERKUNFT.md](src/daidalos/karte/vendor/HERKUNFT.md).

Die Browser-Probe der Tests braucht Chromium: `uv run playwright install chromium`. Ohne Chromium
werden diese Tests übersprungen.

## Dokumentation

- [docs/architektur.md](docs/architektur.md): verbindliche Architektur
- [docs/datenformat.md](docs/datenformat.md): Aufbau von `daidalos.json`, `deutung.json` und
  `daidalos.toml`
- [docs/auftraege/](docs/auftraege/): Aufträge und Berichte

## Lizenz

MIT, siehe [LICENSE](LICENSE).
