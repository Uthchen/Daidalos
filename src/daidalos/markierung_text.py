"""``daidalos markierung``: Grenzkanten der Markierungs-Kette als Text (A08).

Liest nur die Befunde ``markierung-verlassen`` aus der Messung; rechnet nichts neu aus.
"""

from __future__ import annotations

from typing import Any

from daidalos.ids import datei_der_funktion
from daidalos.render import kurz_funktion


def _ort(funktion_id: str, zeile: int) -> str:
    return f"{datei_der_funktion(funktion_id)}:{zeile}"


def _baum(nach: str, eintraege: list[dict[str, Any]], einrueckung: str) -> list[str]:
    """Die Kette als eingerückter Baum unter ihrem Aufrufer (kürzester Weg)."""
    kinder: dict[str, list[dict[str, Any]]] = {}
    for e in eintraege:
        kinder.setdefault(e["von"], []).append(e)
    zeilen: list[str] = []
    gezeigt: set[str] = set()

    def gehe(funktion: str, stufe: int) -> None:
        for e in sorted(kinder.get(funktion, []), key=lambda e: e["funktion"]):
            gezeigt.add(e["funktion"])
            zusatz = (
                f"  (über {kurz_funktion(e['ueber'])}, {e['schritt']})" if "schritt" in e else ""
            )
            zeilen.append(
                f"{einrueckung}{'  ' * stufe}→ {kurz_funktion(e['funktion'])}  "
                f"{_ort(e['funktion'], e['zeile'])}{zusatz}"
            )
            gehe(e["funktion"], stufe + 1)

    gehe(nach, 1)
    for e in eintraege:
        if e["funktion"] not in gezeigt:
            zeilen.append(
                f"{einrueckung}  → {kurz_funktion(e['funktion'])}  "
                f"{_ort(e['funktion'], e['zeile'])}  (aufgerufen von {kurz_funktion(e['von'])})"
            )
    return zeilen


def markierungs_zeilen(daten: dict[str, Any], datei: str | None, unsicher: bool) -> list[str]:
    """Alle Grenzkanten, nach Länge der Kette absteigend, dann nach Id."""
    befunde = [b for b in daten["befunde"] if b["regel"] == "markierung-verlassen"]
    if not unsicher:
        befunde = [b for b in befunde if not b["beleg"].get("unsicher")]
    if datei is not None:
        gesucht = datei.replace("\\", "/").removeprefix("datei:")
        befunde = [
            b
            for b in befunde
            if datei_der_funktion(b["beleg"]["von"]) == gesucht
            or datei_der_funktion(b["beleg"]["von"]).endswith("/" + gesucht)
        ]
    befunde.sort(key=lambda b: (-b["beleg"]["anzahl"], b["id"]))
    art = "auch nur unsichere" if unsicher else "nur sichere"
    zeilen = [f"Grenzkanten der Markierungs-Kette: {len(befunde)} ({art}), längste Kette zuerst"]
    for b in befunde:
        beleg = b["beleg"]
        marke = beleg["markierung"]
        kopf = (
            f"{kurz_funktion(beleg['von'])} ruft unmarkiert {kurz_funktion(beleg['nach'])}  "
            f"[Kette {beleg['anzahl']}"
            + (", unsicher" if beleg.get("unsicher") else "")
            + (", über ueberschreibt" if beleg["ueber_ueberschreiben"] else "")
            + "]"
        )
        zeilen += ["", kopf]
        zeilen.append(
            f"  markiert: {_ort(beleg['von'], beleg['von_zeile'])} ({marke['name']} an "
            f"{marke['traeger']}); Aufruf in Zeile {', '.join(str(z) for z in beleg['zeilen'])}"
        )
        zeilen.append(
            f"  {kurz_funktion(beleg['nach'])}  {_ort(beleg['nach'], beleg['nach_zeile'])}"
        )
        zeilen += _baum(beleg["nach"], beleg["kette"], "  ")
        if beleg.get("kette_unsicher"):
            zeilen.append(f"  nur über unsichere Kanten: {len(beleg['kette_unsicher'])}")
            zeilen += _baum(beleg["nach"], beleg["kette_unsicher"], "  ")
        if beleg["ausnahmen"]:
            namen = ", ".join(kurz_funktion(a) for a in beleg["ausnahmen"])
            zeilen.append(f"  endet an Ausnahmen: {namen}")
        if beleg.get("delegiert_gelesen"):
            zeilen.append(f"  liest {beleg['delegiert_gelesen']} delegierte Eigenschaften")
        zeilen.append(f"  {b['id']}")
    return zeilen
