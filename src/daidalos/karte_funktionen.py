"""Funktionsebene für ``karte.html`` (seit A09): kompakter Block nur für die Karte.

``daidalos.json`` bleibt unverändert. Die Karte liest diesen Block erst, wenn die Funktionsebene
zum ersten Mal geöffnet wird. Der Aufbau steht in ``docs/datenformat.md`` (Abschnitt
„karte.html“, Funktionsblock). Alles hier ist Umformung der Messung, nichts wird neu gemessen;
nur der Träger einer Markierung wird nach derselben Regel wie in der Kette bestimmt.
"""

from __future__ import annotations

from typing import Any

from daidalos.analysen.markierung import markierung_der_funktion
from daidalos.ids import datei_der_funktion

Knoten = dict[str, Any]

# Formatversion des Blocks; unabhängig von ``schema`` der Messung.
FORMAT = 1

# Felder einer Zeile der Funktionstabelle, in dieser Reihenfolge.
FELDER = (
    "datei",  # Index in dateien
    "kurz",  # Teil der Id hinter "#"
    "behaelter",
    "zeile_von",
    "zeile_bis",
    "merkmale",  # Bitfeld, siehe MERKMALE
    "komplexitaet",  # null bei C
    "zeilen",
    "fan_in",
    "fan_in_unsicher",
    "fan_out",
    "fan_out_unsicher",
    "externe_aufrufe",
    "delegiert_gelesen",  # null außer an markierten Funktionen
    "sichtbarkeit",
    "modifikatoren",  # Liste
    "parameter",  # Liste der Typen (null ohne Angabe)
    "parameter_vorgabe",
    "parameter_vararg",
    "annotationen",  # Liste [Name, sicher]
    "erweiterung",
    "markierung",  # [Annotation, Träger] oder null
)
MERKMALE = {
    "markiert": 1,
    "ausnahme": 2,
    "ohne_koerper": 4,
    "implizit": 8,
    "test": 16,
    "c": 32,
}
# Kantenarten des Blocks; ``ruft`` wird nach der Herkunft der Belege in ``ruft`` und
# ``lesen``/``schreiben`` geteilt.
ARTEN = ("ruft", "lesen", "schreiben", "ueberschreibt", "actual", "jni")
ZUGRIFFE = ("lesen", "schreiben")


def _merkmale(funktion: Knoten) -> int:
    wert = 0
    for feld in ("markiert", "ausnahme", "ohne_koerper", "implizit"):
        if funktion.get(feld):
            wert |= MERKMALE[feld]
    if funktion.get("rolle") == "test":
        wert |= MERKMALE["test"]
    if funktion.get("sprache") == "c":
        wert |= MERKMALE["c"]
    return wert


def _teile_ruft(kante: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """``ruft`` nach Art: Aufrufe, Lesezugriffe und Schreibzugriffe getrennt."""
    gruppen: dict[str, list[dict[str, Any]]] = {}
    for beleg in kante["beleg"]:
        art = beleg["herkunft"] if beleg["herkunft"] in ZUGRIFFE else "ruft"
        gruppen.setdefault(art, []).append(beleg)
    return [(art, gruppen[art]) for art in ARTEN if art in gruppen]


def funktionsblock(messung: dict[str, Any], markierungen: tuple[str, ...] = ()) -> Any:
    """Der Block ``id="funktionen"``; ``None`` ohne Funktionsknoten.

    ``markierungen`` sind die vollen Namen aus ``[markierungen].annotationen``; ohne sie bleibt
    der Träger einer Markierung offen (``markiert`` steht trotzdem im Bitfeld).
    """
    funktionen = sorted(
        (k for k in messung["knoten"] if k["art"] == "funktion"), key=lambda k: k["id"]
    )
    if not funktionen:
        return None
    dateiknoten = {k["pfad"]: k for k in messung["knoten"] if k["art"] == "datei"}
    dateien = sorted({datei_der_funktion(f) for f in funktionen})
    datei_nr = {pfad: nr for nr, pfad in enumerate(dateien)}
    funktion_nr = {f["id"]: nr for nr, f in enumerate(funktionen)}
    texte: list[str] = []
    text_nr: dict[str, int] = {}

    def text(wert: str | None) -> int:
        """Index in der Texttabelle (Herkunft und Grund); -1 für keinen."""
        if wert is None:
            return -1
        if wert not in text_nr:
            text_nr[wert] = len(texte)
            texte.append(wert)
        return text_nr[wert]

    zeilen = []
    for f in funktionen:
        pfad = datei_der_funktion(f)
        m = f.get("metriken", {})
        markierung = None
        if f.get("markiert") and markierungen:
            treffer = markierung_der_funktion(f, dateiknoten.get(pfad, {}), markierungen)
            markierung = list(treffer) if treffer else None
        kurz = f["id"].split("#", 1)[1]
        zeilen.append(
            [
                datei_nr[pfad],
                kurz,
                f.get("behaelter", ""),
                f["zeile_von"],
                f["zeile_bis"],
                _merkmale(f),
                m.get("komplexitaet"),
                m.get("zeilen", 0),
                m.get("fan_in", 0),
                m.get("fan_in_unsicher", 0),
                m.get("fan_out", 0),
                m.get("fan_out_unsicher", 0),
                m.get("externe_aufrufe", 0),
                m.get("delegiert_gelesen"),
                f.get("sichtbarkeit", "public"),
                f.get("modifikatoren", []),
                f.get("parameter", []),
                f.get("parameter_vorgabe", []),
                f.get("parameter_vararg", []),
                [[a["name"], bool(a.get("sicher"))] for a in f.get("annotationen", [])],
                f.get("erweiterung"),
                markierung,
            ]
        )

    kanten = []
    for k in messung["kanten"]:
        von, nach = funktion_nr.get(k["von"]), funktion_nr.get(k["nach"])
        if von is None or nach is None or k["art"] not in ARTEN:
            continue
        if k["art"] == "ruft":
            for art, belege in _teile_ruft(k):
                sicher = any(b["sicher"] for b in belege)
                erster = min(belege, key=lambda b: (b["zeilen"][0], not b["sicher"]))
                unsicher = [b for b in belege if not b["sicher"]]
                grund = None if sicher else min(unsicher, key=lambda b: b["zeilen"][0]).get("grund")
                kanten.append(
                    [
                        von,
                        nach,
                        ARTEN.index(art),
                        1 if sicher else 0,
                        sum(len(b["zeilen"]) for b in belege),
                        erster["zeilen"][0],
                        text(erster["herkunft"]),
                        text(grund),
                    ]
                )
        else:
            zeile = None
            if k["art"] == "jni" and k.get("beleg"):
                zeile = k["beleg"][0].get("zeile_kotlin")
            kanten.append(
                [
                    von,
                    nach,
                    ARTEN.index(k["art"]),
                    1 if k.get("sicher", True) else 0,
                    k.get("gewicht", 1),
                    zeile,
                    -1,
                    -1,
                ]
            )
    kanten.sort()

    klassen = []
    for pfad in dateien:
        eintraege = dateiknoten.get(pfad, {}).get("klassen", [])
        klassen.append([[k["name"], k["art"], k["zeile"]] for k in eintraege])

    return {
        "arten": list(ARTEN),
        "dateien": dateien,
        "felder": list(FELDER),
        "format": FORMAT,
        "funktionen": zeilen,
        "kanten": kanten,
        "klassen": klassen,
        "merkmale": MERKMALE,
        "texte": texte,
    }
