# Herkunft der eingebetteten Bibliotheken

Diese Dateien werden von `daidalos render` in `karte.html` eingebettet. Sie wurden einmalig mit
`werkzeuge/hole_vendor.py` von `https://cdn.jsdelivr.net/npm/` geholt (Spiegel der npm-Pakete)
und gegen die dort festgelegten SHA-256-Prüfsummen geprüft. Zur Laufzeit wird nichts geladen.
Prüfen ohne Netz: `uv run python werkzeuge/hole_vendor.py --pruefen`.

| Datei | Paket | Version | Lizenz | Lizenztext |
| --- | --- | --- | --- | --- |
| `cytoscape.min.js` | [cytoscape](https://www.npmjs.com/package/cytoscape) (`dist/cytoscape.min.js`) | 3.28.1 | MIT | `cytoscape.LICENSE` |
| `elk.bundled.js` | [elkjs](https://www.npmjs.com/package/elkjs) (`lib/elk.bundled.js`) | 0.9.3 | EPL-2.0 | `elkjs.LICENSE.md` |
| `cytoscape-elk.js` | [cytoscape-elk](https://www.npmjs.com/package/cytoscape-elk) (`dist/cytoscape-elk.js`) | 2.4.0 | MIT | `cytoscape-elk.LICENSE` |

`cytoscape-elk` 2.4.0 verlangt `elkjs` ^0.9.3, daher nicht die neueste `elkjs`-Version.
Die Lizenztexte werden beim Rendern als Kommentar in `karte.html` übernommen.
