"""Testhilfe: Jede modulübergreifende ``nutzt``-Kante muss durch Gradle gedeckt sein.

Kein Befund in ``daidalos.json`` (die Modulregeln prüft der Build), sondern eine Prüfung des
Auflösers. Aufruf: ``uv run python tests/plausibilitaet.py <daidalos.json>``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PRODUKTIV_ARTEN = frozenset({"gradle-api", "gradle-impl", "gradle-compileonly", "gradle-sonstige"})


def _sichtbar(direkt: dict[str, set[str]], api: dict[str, set[str]], von: str) -> set[str]:
    """Direkte Abhängigkeiten und alles, was diese per ``api`` weitergeben (transitiv)."""
    ergebnis: set[str] = set()
    offen = list(direkt.get(von, set()))
    while offen:
        modul = offen.pop()
        if modul in ergebnis:
            continue
        ergebnis.add(modul)
        offen.extend(api.get(modul, set()))
    return ergebnis


def verstoesse(daten: dict[str, Any]) -> list[str]:
    modul_von = {k["id"]: k.get("modul") for k in daten["knoten"] if k["art"] == "datei"}
    produktiv: dict[str, set[str]] = {}
    mit_test: dict[str, set[str]] = {}
    api: dict[str, set[str]] = {}
    for k in daten["kanten"]:
        art = k["art"]
        if not art.startswith("gradle-") or art == "gradle-plugin":
            continue
        mit_test.setdefault(k["von"], set()).add(k["nach"])
        if art in PRODUKTIV_ARTEN:
            produktiv.setdefault(k["von"], set()).add(k["nach"])
        if art == "gradle-api":
            api.setdefault(k["von"], set()).add(k["nach"])

    fehler: list[str] = []
    for k in daten["kanten"]:
        if k["art"] != "nutzt" or not k["von"].startswith("datei:"):
            continue
        von, nach = modul_von.get(k["von"]), modul_von.get(k["nach"])
        if von is None or nach is None or von == nach:
            continue
        direkt = produktiv if k["rolle"] == "produktiv" else mit_test
        if nach not in _sichtbar(direkt, api, von):
            fehler.append(f"{k['id']} ({von} → {nach})")
    return fehler


def main() -> int:
    daten = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    fehler = verstoesse(daten)
    for zeile in fehler:
        print(zeile)
    print(f"Verstöße: {len(fehler)}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
