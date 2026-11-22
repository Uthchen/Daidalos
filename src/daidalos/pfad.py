"""``daidalos pfad``: kürzester belegter Weg zwischen zwei Knoten in ``daidalos.json``.

Reine Abfrage über die gemessenen Kanten; schreibt nichts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

Knoten = dict[str, Any]
Kante = dict[str, Any]

EBENEN = ("modul", "paket", "datei")
_ART_EBENE = {"modul": "modul", "ordner": "modul", "paket": "paket", "datei": "datei"}
BELEGE_JE_SCHRITT = 3


class PfadFehler(Exception):
    """Suchbegriff nicht gefunden, mehrdeutig oder Ebenen passen nicht; Exit-Code 2."""

    def __init__(self, text: str, treffer: list[str] | None = None) -> None:
        super().__init__(text)
        self.treffer = treffer or []


@dataclass
class Schritt:
    von: str
    nach: str
    kanten: list[Kante]
    belege: list[dict[str, Any]]


def ebene_von(knoten: Knoten) -> str | None:
    return _ART_EBENE.get(knoten["art"])


def _passt(knoten: Knoten, begriff: str) -> bool:
    art = knoten["art"]
    if art == "modul":
        return begriff in (knoten["gradle_pfad"], knoten["pfad"])
    if art == "ordner":
        return begriff.rstrip("/") == knoten["pfad"]
    if art == "paket":
        return begriff == knoten["name"]
    if art == "datei":
        pfad = knoten["pfad"]
        return pfad == begriff or pfad.endswith("/" + begriff.lstrip("/"))
    return False


def finde_knoten(daten: dict[str, Any], begriff: str, ebene: str | None) -> Knoten:
    """Id oder eindeutiger Suchbegriff → Knoten."""
    kandidaten = [k for k in daten["knoten"] if ebene_von(k) is not None]
    if ebene:
        kandidaten = [k for k in kandidaten if ebene_von(k) == ebene]
    for k in kandidaten:
        if k["id"] == begriff:
            return k
    treffer = sorted((k for k in kandidaten if _passt(k, begriff)), key=lambda k: k["id"])
    if not treffer:
        auf = f" auf Ebene {ebene}" if ebene else ""
        raise PfadFehler(f"Kein Knoten{auf} passt zu {begriff!r}")
    if len(treffer) > 1:
        raise PfadFehler(f"{begriff!r} ist mehrdeutig", [k["id"] for k in treffer])
    return treffer[0]


def _zugehoerig(daten: dict[str, Any], ebene: str) -> dict[str, str]:
    """Datei-Id → Id des Pakets bzw. Moduls/Ordners."""
    feld = {"paket": ("paket",), "modul": ("modul", "ordner")}[ebene]
    zuordnung: dict[str, str] = {}
    for k in daten["knoten"]:
        if k["art"] != "datei":
            continue
        for f in feld:
            if f in k:
                zuordnung[k["id"]] = k[f]
                break
    return zuordnung


def _kanten_der_ebene(daten: dict[str, Any], ebene: str, mit_tests: bool) -> list[Kante]:
    knoten = {k["id"]: k for k in daten["knoten"]}
    ergebnis = []
    for k in daten["kanten"]:
        art = k["art"]
        if art != "nutzt" and not (ebene == "modul" and art.startswith("gradle-")):
            continue
        if not mit_tests and k.get("rolle") != "produktiv":
            continue
        von, nach = knoten.get(k["von"]), knoten.get(k["nach"])
        if von is None or nach is None or ebene_von(von) != ebene or ebene_von(nach) != ebene:
            continue
        ergebnis.append(k)
    return ergebnis


def _belege(daten: dict[str, Any], ebene: str, kanten: list[Kante]) -> list[Any]:
    """Die ersten Belege eines Schritts: Symbol und Zeile (bei Gradle Datei und Zeile)."""
    belege: list[dict[str, Any]] = []
    for k in kanten:
        if k["art"].startswith("gradle-"):
            for b in k["beleg"]:
                belege.append(
                    {
                        "art": k["art"],
                        "datei": b["datei"],
                        "konfiguration": b["konfiguration"],
                        "zeile": b["zeile"],
                    }
                )
    nutzt = [k for k in kanten if k["art"] == "nutzt"]
    if ebene == "datei":
        for k in nutzt:
            for b in k["beleg"]:
                pfad = k["von"].removeprefix("datei:")
                belege.append({"datei": pfad, "symbol": b["symbol"], "zeile": b["zeile"]})
    elif nutzt:
        zuordnung = _zugehoerig(daten, ebene)
        paare = {(k["von"], k["nach"], k["rolle"]) for k in nutzt}
        for k in daten["kanten"]:
            if k["art"] != "nutzt" or not k["von"].startswith("datei:"):
                continue
            if (zuordnung.get(k["von"]), zuordnung.get(k["nach"]), k["rolle"]) not in paare:
                continue
            for b in k["beleg"]:
                pfad = k["von"].removeprefix("datei:")
                belege.append({"datei": pfad, "symbol": b["symbol"], "zeile": b["zeile"]})
    return belege[:BELEGE_JE_SCHRITT]


def suche_weg(
    daten: dict[str, Any], von: Knoten, nach: Knoten, ebene: str, mit_tests: bool = False
) -> list[Schritt] | None:
    """Kürzester Weg (Breitensuche, Nachbarn nach Id sortiert); ``None``, wenn es keinen gibt."""
    kanten = _kanten_der_ebene(daten, ebene, mit_tests)
    nachbarn: dict[str, dict[str, list[Kante]]] = {}
    for k in kanten:
        nachbarn.setdefault(k["von"], {}).setdefault(k["nach"], []).append(k)
    vorgaenger: dict[str, str | None] = {von["id"]: None}
    offen = deque([von["id"]])
    while offen:
        aktuell = offen.popleft()
        if aktuell == nach["id"]:
            break
        for ziel in sorted(nachbarn.get(aktuell, {})):
            if ziel not in vorgaenger:
                vorgaenger[ziel] = aktuell
                offen.append(ziel)
    if nach["id"] not in vorgaenger:
        return None
    kette = [nach["id"]]
    while (vorher := vorgaenger[kette[-1]]) is not None:
        kette.append(vorher)
    kette.reverse()
    schritte = []
    for a, b in pairwise(kette):
        ks = sorted(nachbarn[a][b], key=lambda k: (k["art"], k["id"]))
        schritte.append(Schritt(a, b, ks, _belege(daten, ebene, ks)))
    return schritte


def weg_als_json(
    von: Knoten, nach: Knoten, ebene: str, mit_tests: bool, schritte: list[Schritt] | None
) -> dict[str, Any]:
    return {
        "ebene": ebene,
        "mit_tests": mit_tests,
        "nach": nach["id"],
        "von": von["id"],
        "weg": None
        if schritte is None
        else [
            {
                "belege": s.belege,
                "kanten": [
                    {
                        "art": k["art"],
                        "gewicht": k.get("gewicht"),
                        "id": k["id"],
                        "sicher": k.get("sicher", True),
                    }
                    for k in s.kanten
                ],
                "nach": s.nach,
                "von": s.von,
            }
            for s in schritte
        ],
    }
