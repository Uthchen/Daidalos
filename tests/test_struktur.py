"""Strukturgraph am Beispielprojekt ``mini_modulgraph``."""

from __future__ import annotations

from typing import Any

import pytest

from conftest import BEISPIELE
from daidalos.konfiguration import lade_konfiguration
from daidalos.scanner import scanne
from daidalos.struktur import ordne_zu
from plausibilitaet import verstoesse

ZIEL = BEISPIELE / "mini_modulgraph"
KERN = "kern/src/commonMain/kotlin/beispiel/kern"
LABOR = "kern-labor/src/commonMain/kotlin/beispiel/kern/labor"


@pytest.fixture(scope="module")
def daten() -> dict[str, Any]:
    return scanne(ZIEL, lade_konfiguration(ZIEL / "daidalos.toml")).daten


def _knoten(daten: dict[str, Any], knoten_id: str) -> dict[str, Any]:
    return next(k for k in daten["knoten"] if k["id"] == knoten_id)


def _kante(daten: dict[str, Any], kanten_id: str) -> dict[str, Any]:
    return next(k for k in daten["kanten"] if k["id"] == kanten_id)


def test_projektname_aus_konfiguration(daten: dict[str, Any]) -> None:
    assert daten["ziel"]["name"] == "Modulgraph"


def test_zuordnung_der_dateien(daten: dict[str, Any]) -> None:
    labor = _knoten(daten, f"datei:{LABOR}/messung/Messung.kt")
    assert labor["modul"] == "modul::kern-labor"
    assert labor["paket"] == "paket::kern-labor/beispiel.kern.labor.messung"
    assert labor["quellsatz"] == "commonMain"
    assert labor["rolle"] == "produktiv"
    test = _knoten(
        daten,
        "datei:kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt",
    )
    assert (test["quellsatz"], test["rolle"]) == ("commonTest", "test")
    werkzeug = _knoten(daten, "datei:werkzeug/Pruefung.kt")
    assert werkzeug["ordner"] == "ordner:werkzeug"
    assert "modul" not in werkzeug
    wurzel = _knoten(daten, "datei:settings.gradle.kts")
    assert wurzel["ordner"] == "ordner:."


def test_laengstes_praefix_fuer_verschachtelte_module() -> None:
    module = [("a/b", ":a:b"), ("a", ":a")]
    datei: dict[str, Any] = {"pfad": "a/b/src/androidTest/kotlin/X.kt"}
    ordne_zu(datei, module)
    assert datei["modul"] == "modul::a:b"
    assert (datei["quellsatz"], datei["rolle"]) == ("androidTest", "test")


def test_gradle_kanten(daten: dict[str, Any]) -> None:
    api = _kante(daten, "kante:gradle-api:modul::kern-labor->modul::kern")
    assert api["beleg"][0]["quellsatz"] == "commonMain"
    bedingt = _kante(daten, "kante:gradle-impl:modul::anwendung->modul::kern-labor")
    assert bedingt["beleg"][0]["bedingt"] is True


def test_datei_kanten_und_verdichtung(daten: dict[str, Any]) -> None:
    kante = _kante(
        daten,
        f"kante:nutzt:datei:{LABOR}/messung/Auswertung.kt->datei:{KERN}/Werkzeug.kt:produktiv",
    )
    assert kante["gewicht"] == 2
    modul = _kante(daten, "kante:nutzt:modul::kern-labor->modul::kern:produktiv")
    test = _kante(daten, "kante:nutzt:modul::kern-labor->modul::kern:test")
    assert modul["rolle"] == "produktiv"
    assert test["rolle"] == "test"
    assert modul["gewicht"] >= 3


def test_jni(daten: dict[str, Any]) -> None:
    jni = [k for k in daten["kanten"] if k["art"] == "jni"]
    assert len(jni) == 1
    assert jni[0]["beleg"][0]["funktion"] == "beispiel.nativ.Insel.rechne_schnell"
    offen = [b for b in daten["befunde"] if b["regel"] == "jni-ohne-gegenstueck"]
    assert [b["beleg"]["funktion"] for b in offen] == ["beispiel.nativ.Insel.fehlt"]


def test_unaufgeloest(daten: dict[str, Any]) -> None:
    (befund,) = [b for b in daten["befunde"] if b["regel"] == "unaufgeloest"]
    assert befund["beleg"]["importe"] == [{"import": "beispiel.kern.Gibtsnicht", "zeile": 3}]


def _zyklen(daten: dict[str, Any], ebene: str, rolle: str) -> list[dict[str, Any]]:
    return [
        b
        for b in daten["befunde"]
        if b["regel"] == "zyklus" and b["beleg"]["ebene"] == ebene and b["beleg"]["rolle"] == rolle
    ]


def test_zyklen_mit_trennstelle_und_ohne_fremdcode(daten: dict[str, Any]) -> None:
    datei = _zyklen(daten, "datei", "produktiv")
    mitglieder = [b["knoten"] for b in datei]
    assert [f"datei:{KERN}/zyklus/{n}.kt" for n in ("Anfang", "Ende", "Mitte")] in mitglieder
    # Start.kt <-> fremd/Bibliothek.kt zählt nicht
    assert not any("fremd" in k for m in mitglieder for k in m)
    ring = next(b for b in datei if len(b["knoten"]) == 3)
    assert ring["beleg"]["trennstelle"].endswith(
        "Anfang.kt->datei:" + KERN + "/zyklus/Mitte.kt:produktiv"
    )
    assert ring["beleg"]["einstiege"][0]["quellen"] == [f"datei:{LABOR}/messung/Auswertung.kt"]
    (paket,) = _zyklen(daten, "paket", "produktiv")
    assert paket["beleg"]["trennstelle"] == (
        "kante:nutzt:paket::kern-labor/beispiel.kern.labor.protokoll"
        "->paket::kern-labor/beispiel.kern.labor.messung:produktiv"
    )
    for befund in [b for b in daten["befunde"] if b["regel"] == "zyklus"]:
        beleg = befund["beleg"]
        assert beleg["trennstelle"] is not None or "kleinste_trennmenge" in beleg


def test_plausibilitaet(daten: dict[str, Any]) -> None:
    assert verstoesse(daten) == []
