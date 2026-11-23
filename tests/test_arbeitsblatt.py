"""``daidalos arbeitsblatt``: Golden-Dateien, Größenbegrenzung, KDoc, ADR, Datei ohne Adapter.

Neu schreiben mit ``uv run pytest --aktualisiere-golden``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.arbeitsblatt import Arbeitsblatt, erste_kdoc_zeile, lies_quelle
from daidalos.cli import main

ZIEL = BEISPIELE / "mini_modulgraph"
DATEN = ERWARTET / "mini_modulgraph.daidalos.json"


def messung() -> dict[str, Any]:
    return json.loads(DATEN.read_text(encoding="utf-8"))


def _blatt(capsys: pytest.CaptureFixture[str], knoten: str) -> str:
    capsys.readouterr()
    assert main(["arbeitsblatt", knoten, str(ZIEL), "--daten", str(DATEN)]) == 0
    return capsys.readouterr().out


@pytest.mark.parametrize(
    ("knoten", "name"),
    [
        ("modul::kern", "modul-kern"),
        ("paket::kern-labor/beispiel.kern.labor.messung", "paket-messung"),
        ("Strich.kt", "datei-strich"),
        ("nativ/src/main/cpp/insel_jni.c", "datei-insel-c"),
    ],
)
def test_golden(
    knoten: str, name: str, capsys: pytest.CaptureFixture[str], aktualisiere_golden: bool
) -> None:
    golden = ERWARTET / f"mini_modulgraph.arbeitsblatt-{name}.md"
    text = _blatt(capsys, knoten)
    if aktualisiere_golden:
        golden.write_bytes(text.encode("utf-8"))
    assert text.encode("utf-8") == golden.read_bytes()


def test_c_datei_listet_nur_jni_funktionen(capsys: pytest.CaptureFixture[str]) -> None:
    text = _blatt(capsys, "nativ/src/main/cpp/insel_jni.c")
    # Ohne Kotlin-Adapter nur die JNI-Funktionen als Funktionsknoten (A07)
    assert "- deklariert:\n  - Funktionen:\n" in text
    assert "insel_jni.c#Java_beispiel_nativ_Insel_rechne_1schnell/3` (Z. " in text
    assert "7 Zeilen" in text and "Insel.kt" in text  # Pfad, Zeilen, Kanten


def test_datei_listet_funktionen_mit_komplexitaet(capsys: pytest.CaptureFixture[str]) -> None:
    text = _blatt(capsys, "Strich.kt")
    assert "Strich.kt#Strich.schiebe/1` (Z. 7, Komplexität 1)" in text


def test_unbekannter_knoten_ist_bedienfehler(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["arbeitsblatt", "gibt-es-nicht", str(ZIEL), "--daten", str(DATEN)]) == 2
    assert "Kein Knoten" in capsys.readouterr().err


def test_groesse_wird_begrenzt() -> None:
    daten = messung()
    modul = next(k for k in daten["knoten"] if k["id"] == "modul::kern")
    for grenze in (25, 40):
        text = Arbeitsblatt(daten, ZIEL, max_zeilen=grenze).baue(modul)
        # Kopf und Kanten sind fest; der Dateiteil hält die Grenze (Kurzzeilen mindestens 10).
        assert text.count("\n") <= grenze + 12
        assert "Weitere Dateien" in text
    voll = Arbeitsblatt(daten, ZIEL).baue(modul)
    assert "Weitere Dateien" not in voll or voll.count("### ") > 1


def test_kdoc_und_adr(tmp_path: Path) -> None:
    pfad = "a/src/main/kotlin/de/x/Probe.kt"
    datei = tmp_path / pfad
    datei.parent.mkdir(parents=True)
    datei.write_text(
        "/**\n * Probe für Arbeitsblätter (ADR-0001).\n */\npackage de.x\n\n"
        "// siehe ADR-0002 und ADR-0001\n"
        '/** Ein Strich aus Punkten. */\n@Deprecated("x")\nclass Strich\n\n'
        "/**\n * @param a nur Tags\n */\nfun ohneText(a: Int) = a\n\n"
        'val wert = "ADR-0009 im String zählt nicht"\n',
        encoding="utf-8",
    )
    gelesen = lies_quelle(tmp_path, {"pfad": pfad, "sprache": "kotlin"})
    assert gelesen.kdoc_datei == "Probe für Arbeitsblätter (ADR-0001)."
    assert gelesen.deklariert == [
        ("klasse", "Strich", 9, "Ein Strich aus Punkten."),
        ("funktion", "ohneText", 14, None),
        ("eigenschaft", "wert", 16, None),
    ]
    assert dict(gelesen.adr) == {"ADR-0001": 2, "ADR-0002": 1}


def test_kdoc_vor_annotation_class_mit_annotationszeilen(tmp_path: Path) -> None:
    # Die Grammatik liest ``annotation class`` nach Annotationszeilen nicht als Deklaration.
    (tmp_path / "M.kt").write_text(
        "package a\n\n/**\n * Markiert Code im Strichpfad.\n */\n"
        "@Target(AnnotationTarget.CLASS)\n@Retention(AnnotationRetention.SOURCE)\n"
        "annotation class Markierung\n",
        encoding="utf-8",
    )
    gelesen = lies_quelle(tmp_path, {"pfad": "M.kt", "sprache": "kotlin"})
    assert gelesen.deklariert == [("klasse", "Markierung", 8, "Markiert Code im Strichpfad.")]


def test_erste_kdoc_zeile() -> None:
    assert erste_kdoc_zeile("/** Kurz. */") == "Kurz."
    assert erste_kdoc_zeile("/*\n * kein KDoc\n */") is None
    assert erste_kdoc_zeile("/**\n *\n * Zweite Zeile zählt.\n */") == "Zweite Zeile zählt."
    lang = erste_kdoc_zeile("/** " + "x" * 300 + " */")
    assert lang is not None and len(lang) == 160 and lang.endswith("…")


def test_geaenderte_datei_wird_vermerkt(tmp_path: Path) -> None:
    datei = tmp_path / "A.kt"
    datei.write_text("package a\nclass A\n", encoding="utf-8")
    knoten = {"pfad": "A.kt", "sprache": "kotlin", "hash": "sha256:anders"}
    assert lies_quelle(tmp_path, knoten).geaendert
    assert not lies_quelle(tmp_path / "fehlt", knoten).vorhanden


def test_kopfkommentar_ohne_kdoc(tmp_path: Path) -> None:
    (tmp_path / "W.kt").write_text(
        "package a\n// Prototyp (Wegwerfcode). Erste Zeile\n// und zweite Zeile.\nclass W\n",
        encoding="utf-8",
    )
    gelesen = lies_quelle(tmp_path, {"pfad": "W.kt", "sprache": "kotlin"})
    assert gelesen.kdoc_datei is None
    assert gelesen.kopfkommentar == "Prototyp (Wegwerfcode). Erste Zeile und zweite Zeile."
