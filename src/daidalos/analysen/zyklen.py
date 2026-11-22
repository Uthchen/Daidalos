"""Zyklen: starke Zusammenhangskomponenten mit Einstiegen und günstigster Trennstelle."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import networkx as nx

MAX_KANTEN_TRENNMENGE = 8


@dataclass(frozen=True)
class GraphKante:
    id: str
    von: str
    nach: str
    gewicht: int
    sicher: bool = True


@dataclass(frozen=True)
class Zyklus:
    knoten: tuple[str, ...]
    kanten: tuple[GraphKante, ...]
    einstiege: tuple[tuple[str, tuple[str, ...]], ...]  # (Mitglied, Quellen)
    trennstelle: str | None
    kleinste_trennmenge: tuple[str, ...] | None
    loesende_kanten: tuple[str, ...] = ()


def _stark_zusammenhaengend(knoten: Iterable[str], kanten: Iterable[GraphKante]) -> bool:
    graph = nx.DiGraph()
    graph.add_nodes_from(knoten)
    graph.add_edges_from((k.von, k.nach) for k in kanten)
    return nx.is_strongly_connected(graph)


def _reihenfolge(kante: GraphKante) -> tuple[int, str]:
    return (kante.gewicht, kante.id)


def loesende_kanten(knoten: tuple[str, ...], kanten: tuple[GraphKante, ...]) -> tuple[str, ...]:
    """Alle Kanten, deren Wegfall allein die Komponente zerfallen lässt, nach Id sortiert."""
    treffer = []
    for kandidat in kanten:
        rest = [k for k in kanten if k.id != kandidat.id]
        if not _stark_zusammenhaengend(knoten, rest):
            treffer.append(kandidat.id)
    return tuple(sorted(treffer))


def trennstelle(knoten: tuple[str, ...], kanten: tuple[GraphKante, ...]) -> str | None:
    """Lösende Kante mit kleinstem Gewicht (Gleichstand: Id)."""
    loesend = set(loesende_kanten(knoten, kanten))
    for kandidat in sorted(kanten, key=_reihenfolge):
        if kandidat.id in loesend:
            return kandidat.id
    return None


def kleinste_trennmenge(
    knoten: tuple[str, ...], kanten: tuple[GraphKante, ...]
) -> tuple[str, ...] | None:
    """Kleinste Kantenmenge (dann kleinstes Gesamtgewicht, dann Ids), höchstens 8 Kanten."""
    if len(kanten) > MAX_KANTEN_TRENNMENGE:
        return None
    for groesse in range(2, len(kanten) + 1):
        passend: list[tuple[int, tuple[str, ...]]] = []
        for auswahl in combinations(kanten, groesse):
            ids = {k.id for k in auswahl}
            rest = [k for k in kanten if k.id not in ids]
            if not _stark_zusammenhaengend(knoten, rest):
                passend.append((sum(k.gewicht for k in auswahl), tuple(sorted(ids))))
        if passend:
            return min(passend)[1]
    return None


def finde_zyklen(kanten: list[GraphKante], ausgeschlossen: set[str] | None = None) -> list[Zyklus]:
    """Zyklen im Graphen aus ``kanten``. Knoten in ``ausgeschlossen`` werden vorher entfernt."""
    ausgeschlossen = ausgeschlossen or set()
    gueltig = [
        k
        for k in kanten
        if k.von not in ausgeschlossen and k.nach not in ausgeschlossen and k.von != k.nach
    ]
    graph = nx.DiGraph()
    graph.add_edges_from((k.von, k.nach) for k in gueltig)
    zyklen: list[Zyklus] = []
    for komponente in nx.strongly_connected_components(graph):
        if len(komponente) < 2:
            continue
        mitglieder = tuple(sorted(komponente))
        innen = tuple(
            sorted(
                (k for k in gueltig if k.von in komponente and k.nach in komponente),
                key=lambda k: k.id,
            )
        )
        quellen: dict[str, set[str]] = {}
        for k in gueltig:
            if k.nach in komponente and k.von not in komponente:
                quellen.setdefault(k.nach, set()).add(k.von)
        einstiege = tuple((m, tuple(sorted(quellen[m]))) for m in sorted(quellen))
        loesend = loesende_kanten(mitglieder, innen)
        gewicht = {k.id: k for k in innen}
        trenn = min(loesend, key=lambda i: _reihenfolge(gewicht[i])) if loesend else None
        menge = None if trenn is not None else kleinste_trennmenge(mitglieder, innen)
        zyklen.append(Zyklus(mitglieder, innen, einstiege, trenn, menge, loesend))
    zyklen.sort(key=lambda z: z.knoten)
    return zyklen


def befund_id(ebene: str, rolle: str, knoten: tuple[str, ...]) -> str:
    summe = hashlib.sha256("\n".join(sorted(knoten)).encode("utf-8")).hexdigest()[:12]
    return f"befund:zyklus:{ebene}:{rolle}:{summe}"


def zyklus_befunde(
    ebene: str,
    rolle: str,
    kanten: list[GraphKante],
    ausgeschlossen: set[str] | None = None,
    kantenart: str | None = None,
) -> list[dict[str, Any]]:
    """Befunde ``zyklus`` für eine Ebene und Rolle.

    ``kantenart`` unterscheidet auf Modulebene ``gradle`` und ``nutzt`` und wird Teil der Id.
    """
    befunde: list[dict[str, Any]] = []
    id_ebene = f"{ebene}:{kantenart}" if kantenart else ebene
    for zyklus in finde_zyklen(kanten, ausgeschlossen):
        beleg: dict[str, Any] = {
            "ebene": ebene,
            "einstiege": [
                {"knoten": mitglied, "quellen": list(quellen)}
                for mitglied, quellen in zyklus.einstiege
            ],
            "kanten": [k.id for k in zyklus.kanten],
            "knoten": list(zyklus.knoten),
            "loesende_kanten": list(zyklus.loesende_kanten),
            "rolle": rolle,
            "trennstelle": zyklus.trennstelle,
            "unsicher": any(not k.sicher for k in zyklus.kanten),
        }
        if kantenart:
            beleg["kantenart"] = kantenart
        if zyklus.trennstelle is None and zyklus.kleinste_trennmenge is not None:
            beleg["kleinste_trennmenge"] = list(zyklus.kleinste_trennmenge)
        befunde.append(
            {
                "beleg": beleg,
                "id": befund_id(id_ebene, rolle, zyklus.knoten),
                "knoten": list(zyklus.knoten),
                "quelle": "daidalos",
                "regel": "zyklus",
                "schwere": "warnung",
            }
        )
    return befunde
