from __future__ import annotations

from daidalos.analysen.zyklen import (
    GraphKante,
    befund_id,
    finde_zyklen,
    kleinste_trennmenge,
    zyklus_befunde,
)


def _k(von: str, nach: str, gewicht: int = 1, sicher: bool = True) -> GraphKante:
    return GraphKante(f"{von}->{nach}", von, nach, gewicht, sicher)


def test_ring_mit_eindeutiger_trennstelle_und_einstiegen() -> None:
    kanten = [_k("a", "b", 2), _k("b", "c", 1), _k("c", "a", 3), _k("x", "a"), _k("y", "a")]
    (zyklus,) = finde_zyklen(kanten)
    assert zyklus.knoten == ("a", "b", "c")
    assert zyklus.trennstelle == "b->c"
    assert zyklus.einstiege == (("a", ("x", "y")),)


def test_gleichstand_nach_id() -> None:
    (zyklus,) = finde_zyklen([_k("b", "a"), _k("a", "b")])
    assert zyklus.trennstelle == "a->b"


def test_keine_einzelne_trennstelle_ergibt_trennmenge() -> None:
    # a <-> b doppelt verbunden über zwei Wege: keine einzelne Kante trennt.
    kanten = [_k("a", "b"), _k("b", "a"), _k("a", "c"), _k("c", "a"), _k("b", "c"), _k("c", "b")]
    (zyklus,) = finde_zyklen(kanten)
    assert zyklus.trennstelle is None
    assert zyklus.kleinste_trennmenge is not None
    assert len(zyklus.kleinste_trennmenge) == 2


def test_trennmenge_nur_bis_acht_kanten() -> None:
    knoten = tuple("abcde")
    kanten = tuple(_k(a, b) for a in knoten for b in knoten if a != b)
    assert kleinste_trennmenge(knoten, kanten) is None


def test_ausgeschlossene_knoten() -> None:
    assert finde_zyklen([_k("a", "f"), _k("f", "a")], {"f"}) == []


def test_befunde_stabil_mit_unsicher() -> None:
    befunde = zyklus_befunde("datei", "produktiv", [_k("b", "a", sicher=False), _k("a", "b")])
    (befund,) = befunde
    assert befund["id"] == befund_id("datei", "produktiv", ("a", "b"))
    assert befund["id"].startswith("befund:zyklus:datei:produktiv:")
    assert len(befund["id"].rsplit(":", 1)[1]) == 12
    assert befund["beleg"]["unsicher"] is True
    assert befund["beleg"]["kanten"] == ["a->b", "b->a"]
    modul = zyklus_befunde("modul", "produktiv", [_k("a", "b"), _k("b", "a")], kantenart="gradle")
    assert modul[0]["id"].startswith("befund:zyklus:modul:gradle:produktiv:")


def test_loesende_kanten_alle_treffer_sortiert() -> None:
    # Ring a→b→c→a mit Abkürzung a→c: Die Abkürzung allein löst nichts, jede Ringkante schon.
    kanten = [_k("a", "b", 2), _k("b", "c", 1), _k("c", "a", 3), _k("a", "c", 1)]
    (zyklus,) = finde_zyklen(kanten)
    assert zyklus.loesende_kanten == ("a->b", "b->c", "c->a")
    assert zyklus.trennstelle == "b->c"


def test_loesende_kanten_leer_ohne_einzelne_trennstelle() -> None:
    kanten = [_k("a", "b"), _k("b", "a"), _k("a", "c"), _k("c", "a"), _k("b", "c"), _k("c", "b")]
    (befund,) = zyklus_befunde("datei", "produktiv", kanten)
    assert befund["beleg"]["loesende_kanten"] == []
    assert befund["beleg"]["trennstelle"] is None


def test_trennstelle_ist_leichteste_loesende_kante() -> None:
    kanten = [_k("a", "b", 5), _k("b", "a", 2)]
    (befund,) = zyklus_befunde("datei", "produktiv", kanten)
    assert befund["beleg"]["loesende_kanten"] == ["a->b", "b->a"]
    assert befund["beleg"]["trennstelle"] == "b->a"
