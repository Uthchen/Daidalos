"""Holt die Bibliotheken für ``karte.html`` einmalig nach ``src/daidalos/karte/vendor/``.

Nur für Entwickler, nicht zur Laufzeit. Jede Datei wird gegen eine festgelegte SHA-256-Prüfsumme
geprüft; passt sie nicht, wird nichts geschrieben. Aufruf: ``uv run python werkzeuge/hole_vendor.py``.
Mit ``--pruefen`` werden nur die abgelegten Dateien gegen die Prüfsummen geprüft (ohne Netz).
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

QUELLE = "https://cdn.jsdelivr.net/npm/"
ZIEL = Path(__file__).resolve().parent.parent / "src" / "daidalos" / "karte" / "vendor"

# (Ablagename, Paket@Version/Pfad, SHA-256)
DATEIEN: list[tuple[str, str, str]] = [
    (
        "cytoscape.min.js",
        "cytoscape@3.28.1/dist/cytoscape.min.js",
        "92d752b48ea949720675865197fd2a0001c95bc5888545e990af60321712d4c6",
    ),
    (
        "cytoscape.LICENSE",
        "cytoscape@3.28.1/LICENSE",
        "ac2a446d6e1b489d9568def4ba7790ab81f5023ebba335d49a77dbff1960232e",
    ),
    (
        "elk.bundled.js",
        "elkjs@0.9.3/lib/elk.bundled.js",
        "b0745abd7f23cd91690a1587e377edbe19fd7233c783300290936720546216d4",
    ),
    (
        "elkjs.LICENSE.md",
        "elkjs@0.9.3/LICENSE.md",
        "89591d4578fb1ebd91501312a3d25f021bd865a2e436641c1cf7b1bc7e3c1617",
    ),
    (
        "cytoscape-elk.js",
        "cytoscape-elk@2.4.0/dist/cytoscape-elk.js",
        "625ed13c9e4c566da6104f285d59a209ea9c2aaf97e7de1f9b5507a357f269a8",
    ),
    (
        "cytoscape-elk.LICENSE",
        "cytoscape-elk@2.4.0/LICENSE",
        "0ce4ff4d3a334ae70cf389e0e9095b6ea6ef7110b27d2728a32bb5a7f84ed064",
    ),
]


def _summe(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def pruefe_abgelegt() -> int:
    fehler = 0
    for name, _, erwartet in DATEIEN:
        pfad = ZIEL / name
        if not pfad.is_file() or _summe(pfad.read_bytes()) != erwartet:
            print(f"Abweichung: {name}")
            fehler += 1
    print("Alle Prüfsummen stimmen." if not fehler else f"{fehler} Abweichung(en).")
    return 1 if fehler else 0


def hole() -> int:
    geholt: dict[str, bytes] = {}
    for name, quelle, erwartet in DATEIEN:
        with urllib.request.urlopen(QUELLE + quelle, timeout=60) as antwort:
            daten = antwort.read()
        if _summe(daten) != erwartet:
            print(f"Prüfsumme falsch für {quelle}: {_summe(daten)}", file=sys.stderr)
            return 1
        geholt[name] = daten
    ZIEL.mkdir(parents=True, exist_ok=True)
    for name, daten in geholt.items():
        (ZIEL / name).write_bytes(daten)
        print(f"{name}: {len(daten)} Bytes")
    return 0


if __name__ == "__main__":
    sys.exit(pruefe_abgelegt() if "--pruefen" in sys.argv else hole())
