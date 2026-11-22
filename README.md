# Daidalos

Daidalos zeichnet eine Karte, die zeigt, wie die Teile einer Codebase miteinander verflochten sind,
und markiert, wo dieses Geflecht ungesund ist. Das Programm misst nur. Die Deutung (Namen, Texte,
Prioritäten) übernimmt ein eigener Skill, und beides liegt in getrennten Dateien.

Stand: Etappe 2, erster Teil. `daidalos scan` erfasst die Dateien eines Zielrepos. Kanten und
Analysen folgen.

## Installation

Voraussetzung sind Python ≥ 3.12 und [uv](https://docs.astral.sh/uv/).

```
uv sync
```

## Aufruf

```
uv run daidalos scan <zielrepo>
uv run daidalos scan <zielrepo> --konfiguration <datei> --ausgabe <datei>
uv run python -m daidalos --version
```

Ohne weitere Angaben liest Daidalos `<zielrepo>/daidalos.toml` (optional) und schreibt
`<zielrepo>/docs/daidalos/daidalos.json`.

## Dokumentation

- [docs/architektur.md](docs/architektur.md): verbindliche Architektur
- [docs/datenformat.md](docs/datenformat.md): Aufbau von `daidalos.json` und `daidalos.toml`
- [docs/auftraege/](docs/auftraege/): Aufträge und Berichte

## Lizenz

MIT, siehe [LICENSE](LICENSE).
