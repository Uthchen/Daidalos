# Herkunft der eingebetteten Bibliotheken

Diese Dateien werden von `daidalos render` in `karte.html` eingebettet. Sie wurden einmalig mit
`werkzeuge/hole_vendor.py` von `https://cdn.jsdelivr.net/npm/` geholt (Spiegel der npm-Pakete)
und gegen die dort festgelegten SHA-256-Prüfsummen geprüft. Zur Laufzeit wird nichts geladen.
Prüfen ohne Netz: `uv run python werkzeuge/hole_vendor.py --pruefen`.

| Datei | Paket | Version | Lizenz | Lizenztext |
| --- | --- | --- | --- | --- |
| `cytoscape.min.js` | [cytoscape](https://www.npmjs.com/package/cytoscape) (`dist/cytoscape.min.js`) | 3.28.1 | MIT | `cytoscape.LICENSE` |
| `elk-api.js` | [elkjs](https://www.npmjs.com/package/elkjs) (`lib/elk-api.js`) | 0.9.3 | EPL-2.0 | `elkjs.LICENSE.md` |
| `elk-worker.min.js` | [elkjs](https://www.npmjs.com/package/elkjs) (`lib/elk-worker.min.js`) | 0.9.3 | EPL-2.0 | `elkjs.LICENSE.md` |
| `cytoscape-elk.js` | [cytoscape-elk](https://www.npmjs.com/package/cytoscape-elk) (`dist/cytoscape-elk.js`) | 2.4.0 | MIT | `cytoscape-elk.LICENSE` |

Prüfsummen (SHA-256) stehen in `werkzeuge/hole_vendor.py`; die beiden elkjs-Teile:

- `elk-api.js`: `b5866a7495d7d4731d4ec66342e2a090061f95fe9c80817846e807f0bb38a785`
- `elk-worker.min.js`: `114c4f17aea4b297a2d3dd6c86bdfccb45e12040da964ea8f9766345fce4f538`

Seit A09b rechnet ELK in einem Web Worker. Statt `elk.bundled.js` (API und Worker in einem Stück,
rechnet im Seiten-Thread) werden `elk-api.js` und `elk-worker.min.js` eingebettet; der Worker-Teil
steht als Text in `<script type="text/plain" id="elk-worker">`, `../elk_lauf.js` startet daraus
einen Worker über eine Blob-URL (eine Worker-Datei kann unter `file://` nicht geladen werden).

`cytoscape-elk` 2.4.0 verlangt `elkjs` ^0.9.3, daher nicht die neueste `elkjs`-Version.
Die Lizenztexte werden beim Rendern als Kommentar in `karte.html` übernommen.
