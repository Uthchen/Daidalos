"""``daidalos pfad`` am Beispiel ``mini_modulgraph``."""

from __future__ import annotations

import json

import pytest

from conftest import ERWARTET
from daidalos.cli import main

DATEN = str(ERWARTET / "mini_modulgraph.daidalos.json")
KERN = "kern/src/commonMain/kotlin/beispiel/kern"


def pfad(*argumente: str) -> list[str]:
    return ["pfad", *argumente, "--daten", DATEN]


def test_modulweg(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(pfad(":anwendung", ":kern")) == 0
    text = capsys.readouterr().out
    assert "Weg von :anwendung nach :kern (Ebene modul" in text
    assert ":anwendung → :kern" in text
    assert "gradle-impl" in text


def test_dateiweg_mit_belegen(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(pfad("Auswertung.kt", "zyklus/Ende.kt", "--json")) == 0
    ergebnis = json.loads(capsys.readouterr().out)
    assert ergebnis["ebene"] == "datei"
    weg = ergebnis["weg"]
    assert weg[0]["von"].endswith("Auswertung.kt")
    assert weg[-1]["nach"] == f"datei:{KERN}/zyklus/Ende.kt"
    assert all(schritt["belege"] for schritt in weg)
    assert {"datei", "symbol", "zeile"} <= set(weg[0]["belege"][0])


def test_paketweg(capsys: pytest.CaptureFixture[str]) -> None:
    argumente = pfad("beispiel.kern.labor.messung", "beispiel.kern", "--json")
    assert main(argumente) == 0
    weg = json.loads(capsys.readouterr().out)["weg"]
    assert weg and weg[0]["belege"][0]["datei"].startswith("kern-labor/")


def test_mehrdeutige_datei(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(pfad("build.gradle.kts", ":kern")) == 2
    fehler = capsys.readouterr().err
    assert "mehrdeutig" in fehler
    assert "datei:kern/build.gradle.kts" in fehler


def test_unerreichbar(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(pfad(":kern", ":anwendung")) == 0
    assert "Kein Weg von :kern nach :anwendung" in capsys.readouterr().out
    assert main(pfad(":kern", ":anwendung", "--json")) == 0
    assert json.loads(capsys.readouterr().out)["weg"] is None


def test_verschiedene_ebenen_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(pfad(":kern", "Punkt.kt")) == 2
    assert "verschiedenen Ebenen" in capsys.readouterr().err


def test_test_kanten_nur_mit_tests(capsys: pytest.CaptureFixture[str]) -> None:
    test_datei = "kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt"
    assert main(pfad(test_datei, "Auswertung.kt", "--json")) == 0
    assert json.loads(capsys.readouterr().out)["weg"] is None
    assert main(pfad(test_datei, "Auswertung.kt", "--mit-tests", "--json")) == 0
    assert json.loads(capsys.readouterr().out)["weg"]
