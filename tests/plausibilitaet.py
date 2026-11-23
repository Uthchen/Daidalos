"""Testhilfe: Plausibilität der Auflösung.

- Jede modulübergreifende ``nutzt``-Kante muss durch Gradle gedeckt sein.
- Jede sichere ``ruft``-Kante zwischen zwei Dateien braucht eine ``nutzt``-Kante zwischen diesen
  Dateien (seit A07). Ausnahme: Kommt der Typ des Empfängers aus einer Deklaration (Eigenschaft,
  Parameter, lokal, ``this``, ``super``; seit A07b auch Rückgabetyp, Konstruktor-Ergebnis,
  Initialisierer, Cast und Zugriffe ``lesen``/``schreiben``), genügt ein Weg über höchstens drei
  ``nutzt``-Kanten.
  So erreichen Eigenschaftsketten wie ``q.index.f()`` und geerbte Mitglieder Dateien, deren Namen
  in der aufrufenden Datei nicht vorkommen. Diese Fälle zählt ``indirekte_ruft_kanten``.
- Jede ``ueberschreibt``-Kante zeigt in einen Obertyp der Klasse (seit A07).

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


def _klassen(daten: dict[str, Any]) -> dict[tuple[str, str], set[str]]:
    """(Datei-Pfad, Klassenkette) → volle Namen der Obertypen; dazu voller Name je Klasse."""
    ergebnis: dict[tuple[str, str], set[str]] = {}
    for k in daten["knoten"]:
        if k["art"] != "datei":
            continue
        for klasse in k.get("klassen", []):
            ergebnis[(k["pfad"], klasse["name"])] = {
                o["voll"] for o in klasse["obertypen"] if o["voll"]
            }
    return ergebnis


_UEBER_TYP = frozenset(
    {
        "eigenschaft",
        "lokal",
        "parameter",
        "this",
        "super",
        # seit A07b
        "rueckgabe",
        "konstruktor-ergebnis",
        "initialisierer",
        "cast",
        "lesen",
        "schreiben",
    }
)
INDIREKT_HOECHSTENS = 3


def _erreichbar(nutzt: dict[str, set[str]], von: str, nach: str, schritte: int) -> bool:
    stufe = {von}
    gesehen = {von}
    for _ in range(schritte):
        stufe = {z for s in stufe for z in nutzt.get(s, set())} - gesehen
        if nach in stufe:
            return True
        gesehen |= stufe
    return False


def indirekte_ruft_kanten(daten: dict[str, Any]) -> list[str]:
    """Sichere ruft-Kanten ohne direkte nutzt-Kante, die die Ausnahme erlaubt."""
    return _pruefe_ruft(daten)[1]


def _pruefe_ruft(daten: dict[str, Any]) -> tuple[list[str], list[str]]:
    knoten = {k["id"]: k for k in daten["knoten"]}
    nutzt: dict[str, set[str]] = {}
    for k in daten["kanten"]:
        if k["art"] == "nutzt" and k["von"].startswith("datei:"):
            nutzt.setdefault(k["von"], set()).add(k["nach"])
    fehler: list[str] = []
    indirekt: list[str] = []
    for k in daten["kanten"]:
        if k["art"] != "ruft" or not k["sicher"]:
            continue
        von = "datei:" + knoten[k["von"]]["datei"]
        nach = "datei:" + knoten[k["nach"]]["datei"]
        if von == nach or nach in nutzt.get(von, set()):
            continue
        herkunft = {b["herkunft"] for b in k["beleg"] if b["sicher"]}
        if herkunft <= _UEBER_TYP and _erreichbar(nutzt, von, nach, INDIREKT_HOECHSTENS):
            indirekt.append(k["id"])
        else:
            fehler.append(f"{k['id']} (ruft ohne nutzt)")
    return fehler, indirekt


def funktions_verstoesse(daten: dict[str, Any]) -> list[str]:
    """Verstöße der Funktionsebene: ruft ohne nutzt, ueberschreibt ohne Obertyp."""
    knoten = {k["id"]: k for k in daten["knoten"]}
    # voller Klassenname → (Datei, Kette); Paket aus dem Paket-Knoten der Datei
    voll_nach_klasse: dict[str, tuple[str, str]] = {}
    paket_von: dict[str, str] = {}
    for k in daten["knoten"]:
        if k["art"] == "datei" and "paket" in k:
            paket = knoten[k["paket"]]["name"]
            paket_von[k["pfad"]] = paket
            for klasse in k.get("klassen", []):
                voll_nach_klasse[f"{paket}.{klasse['name']}"] = (k["pfad"], klasse["name"])
    obertypen = _klassen(daten)

    def alle_ober(pfad: str, kette: str) -> set[str]:
        ergebnis: set[str] = set()
        offen = list(obertypen.get((pfad, kette), set()))
        while offen:
            voll = offen.pop()
            if voll in ergebnis:
                continue
            ergebnis.add(voll)
            if voll in voll_nach_klasse:
                offen.extend(obertypen.get(voll_nach_klasse[voll], set()))
        return ergebnis

    fehler = _pruefe_ruft(daten)[0]
    for k in daten["kanten"]:
        if k["art"] == "ueberschreibt":
            von, nach = knoten[k["von"]], knoten[k["nach"]]
            ziel = f"{paket_von.get(nach['datei'], '')}.{nach['behaelter']}".lstrip(".")
            if ziel not in alle_ober(von["datei"], von["behaelter"]):
                fehler.append(f"{k['id']} (ueberschreibt ohne Obertyp)")
    return fehler


def main() -> int:
    daten = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    fehler = verstoesse(daten) + funktions_verstoesse(daten)
    for zeile in fehler:
        print(zeile)
    print(f"Verstöße: {len(fehler)}")
    indirekt = len(indirekte_ruft_kanten(daten))
    print(f"Sichere ruft-Kanten nur über einen nutzt-Weg erreichbar: {indirekt}")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
