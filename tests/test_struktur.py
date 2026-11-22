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


# ---------------------------------------------------------------- A04: Metriken und Zyklus-Regel


def test_metriken_je_ebene(daten: dict[str, Any]) -> None:
    for k in daten["knoten"]:
        assert set(k["metriken"]) == {"fan_in", "fan_out", "instabilitaet"}
    # Messung nutzt Eintrag, Eintrag nutzt Messung (Zyklus im Labor).
    messung = _knoten(daten, f"datei:{LABOR}/messung/Messung.kt")["metriken"]
    assert messung["fan_out"] >= 1
    assert messung["fan_in"] >= 1
    labor = _knoten(daten, "modul::kern-labor")
    assert labor["metriken"]["fan_out"] == 1  # nutzt nur :kern
    regeln = _knoten(daten, "modul::regeln")["metriken"]
    assert regeln == {"fan_in": 0, "fan_out": 0, "instabilitaet": None}


def test_instabilitaet_gerundet() -> None:
    from daidalos.struktur import kopplung

    assert kopplung(2, 1) == {"fan_in": 2, "fan_out": 1, "instabilitaet": 0.333}
    assert kopplung(0, 0)["instabilitaet"] is None


def test_gruppen_zaehlen_nur_eigene_dateien(daten: dict[str, Any]) -> None:
    dateien = [k for k in daten["knoten"] if k["art"] == "datei"]
    anwendung = _knoten(daten, "modul::anwendung")
    eigene = [d for d in dateien if d.get("modul") == "modul::anwendung" and not d.get("fremd")]
    assert anwendung["dateien"] == len(eigene)
    assert anwendung["zeilen"] == sum(d.get("zeilen", 0) for d in eigene)
    assert any(d.get("fremd") and d.get("modul") == "modul::anwendung" for d in dateien)


def test_gruppen_hash_folgt_den_dateien() -> None:
    from daidalos.struktur import gruppen_hash

    a = {"pfad": "a.kt", "hash": "sha256:1"}
    b = {"pfad": "b.kt", "hash": "sha256:2"}
    assert gruppen_hash([a, b]) == gruppen_hash([b, a])
    assert gruppen_hash([a, b]) != gruppen_hash([a, {**b, "hash": "sha256:3"}])
    assert gruppen_hash([a]).startswith("sha256:")


def test_gruppen_haben_hash(daten: dict[str, Any]) -> None:
    for k in daten["knoten"]:
        if k["art"] in ("modul", "paket", "ordner"):
            assert k["hash"].startswith("sha256:")


def _zyklus(ebene: str, rolle: str, knoten: list[str]) -> dict[str, Any]:
    return {
        "beleg": {"ebene": ebene, "rolle": rolle, "knoten": knoten},
        "id": f"befund:zyklus:{ebene}:{rolle}:{'-'.join(knoten)}",
        "knoten": knoten,
    }


def test_test_zyklus_entfaellt_bei_gleicher_menge() -> None:
    from daidalos.struktur import nur_neue_test_zyklen

    befunde = [
        _zyklus("datei", "produktiv", ["a", "b"]),
        _zyklus("datei", "mit-tests", ["a", "b"]),
        _zyklus("paket", "mit-tests", ["a", "b"]),
    ]
    ergebnis = nur_neue_test_zyklen(befunde)
    assert [b["id"] for b in ergebnis] == [befunde[0]["id"], befunde[2]["id"]]


def test_test_zyklus_verschmilzt_produktive() -> None:
    from daidalos.struktur import nur_neue_test_zyklen

    p1 = _zyklus("paket", "produktiv", ["a", "b"])
    p2 = _zyklus("paket", "produktiv", ["c", "d"])
    t = _zyklus("paket", "mit-tests", ["a", "b", "c", "d", "e"])
    ergebnis = nur_neue_test_zyklen([p1, p2, t])
    assert ergebnis[2]["beleg"]["enthaelt_produktiv"] == sorted([p1["id"], p2["id"]])


def test_beispiel_hat_keine_doppelten_test_zyklen(daten: dict[str, Any]) -> None:
    rollen = [b["beleg"]["rolle"] for b in daten["befunde"] if b["regel"] == "zyklus"]
    assert "mit-tests" not in rollen
