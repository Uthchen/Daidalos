"""Markierungs-Kette und detekt-SARIF (A08) am erfundenen Beispiel ``mini_markierung``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE
from daidalos.adapter.detekt import relativer_pfad
from daidalos.cli import main
from daidalos.konfiguration import lade_konfiguration
from daidalos.render import baue_karte_md
from daidalos.scanner import scanne
from daidalos.zusammenfassung import Zusammenfassung, finde_offenes, wichtige_dateien
from plausibilitaet import funktions_verstoesse, verstoesse

BEISPIEL = BEISPIELE / "mini_markierung"
KETTE = "kern/src/main/kotlin/de/beispiel/kette"


def f(datei: str, name: str) -> str:
    return f"funktion:{KETTE}/{datei}#{name}"


def befund_id(von: str, nach: str) -> str:
    return f"befund:markierung:{von}->{nach}"


def _scan(ziel: Path, warnungen: list[str] | None = None) -> dict[str, Any]:
    konfiguration = lade_konfiguration(ziel / "daidalos.toml")
    warne = warnungen.append if warnungen is not None else (lambda _: None)
    return scanne(ziel, konfiguration, warne).daten


@pytest.fixture(scope="module")
def daten() -> dict[str, Any]:
    return _scan(BEISPIEL)


def kette_befunde(daten: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["id"]: b for b in daten["befunde"] if b["regel"] == "markierung-verlassen"}


def funktion(daten: dict[str, Any], funktion_id: str) -> dict[str, Any]:
    return next(k for k in daten["knoten"] if k["id"] == funktion_id)


# ---------------------------------------------------------------- Markierung


def test_markiert_und_ausnahme(daten: dict[str, Any]) -> None:
    markiert = {k["id"] for k in daten["knoten"] if k.get("markiert")}
    assert markiert == {
        f("Dateiweit.kt", "dateiweit/0"),
        f("Formen.kt", "messe/1"),
        f("Formen.kt", "ungewiss/1"),
        f("Pinsel.kt", "Pinsel.<get-doppelt>/0"),
        f("Pinsel.kt", "Pinsel.Companion.neu/0"),
        f("Pinsel.kt", "Pinsel.male/0"),
        f("Rechnen.kt", "rechneSicher/1"),
        f("Rechnen.kt", "zeichne/1"),
    }
    assert {k["id"] for k in daten["knoten"] if k.get("ausnahme")} == {f("Rechnen.kt", "wecke/0")}
    # leere Werte entfallen
    assert all(k.get("markiert", True) and k.get("ausnahme", True) for k in daten["knoten"])


def test_init_der_markierten_klasse_ist_nicht_gedeckt(daten: dict[str, Any]) -> None:
    assert not funktion(daten, f("Pinsel.kt", "Pinsel.<init>/1")).get("markiert")
    b = kette_befunde(daten)[
        befund_id(f("Pinsel.kt", "Pinsel.Companion.neu/0"), f("Pinsel.kt", "Pinsel.<init>/1"))
    ]
    assert b["beleg"]["markierung"] == {"name": "de.beispiel.Strichpfad", "traeger": "klasse"}
    assert [e["funktion"] for e in b["beleg"]["kette"]] == [f("Pinsel.kt", "vorbereite/1")]


def test_gleichnamige_annotation_test_und_ausgenommen_zaehlen_nicht(daten: dict[str, Any]) -> None:
    ids = " ".join(kette_befunde(daten))
    assert "scheinbar" not in ids
    assert "testHilfe" not in ids
    assert "gegen" not in ids
    assert not funktion(daten, f("Schein.kt", "scheinbar/0")).get("markiert")


def test_markiert_ruft_markiert_und_getter_ohne_befund(daten: dict[str, Any]) -> None:
    nach = {b["beleg"]["nach"] for b in kette_befunde(daten).values()}
    assert f("Rechnen.kt", "rechneSicher/1") not in nach
    assert f("Pinsel.kt", "Pinsel.<get-doppelt>/0") not in nach
    # Ausnahme direkt gerufen: kein Befund
    assert f("Rechnen.kt", "wecke/0") not in nach


def test_kette_mit_rekursion_ausnahme_und_unsicherer_fortsetzung(daten: dict[str, Any]) -> None:
    b = kette_befunde(daten)[befund_id(f("Rechnen.kt", "zeichne/1"), f("Rechnen.kt", "glaette/1"))]
    beleg = b["beleg"]
    assert b["schwere"] == "warnung"
    assert [(e["funktion"], e["tiefe"]) for e in beleg["kette"]] == [
        (f("Rechnen.kt", "runde/1"), 1),
        (f("Rechnen.kt", "zurueck/1"), 2),
    ]
    assert beleg["anzahl"] == 3
    assert beleg["zeilen"] == [11]
    assert beleg["ausnahmen"] == [f("Rechnen.kt", "wecke/0")]
    assert {e["funktion"] for e in beleg["kette_unsicher"]} == {
        f("Formen.kt", "Ding.skaliere/0"),
        f("Formen.kt", "Sache.skaliere/0"),
    }
    assert beleg["ueber_ueberschreiben"] is False
    # knoten: von, nach und die Dateien der Kette
    assert b["knoten"] == sorted(
        [
            f"datei:{KETTE}/Rechnen.kt",
            f("Rechnen.kt", "glaette/1"),
            f("Rechnen.kt", "zeichne/1"),
        ]
    )


def test_schnittstelle_ueber_ueberschrieben_von(daten: dict[str, Any]) -> None:
    b = kette_befunde(daten)[
        befund_id(f("Formen.kt", "messe/1"), f("Formen.kt", "Kreis.flaeche/0"))
    ]
    assert b["beleg"]["ueber_ueberschreiben"] is True
    # die Schnittstellenmethode selbst hat keinen Körper und ist kein Verstoß
    assert funktion(daten, f("Formen.kt", "Form.flaeche/0"))["ohne_koerper"] is True
    assert all(
        b["beleg"]["nach"] != f("Formen.kt", "Form.flaeche/0")
        for b in kette_befunde(daten).values()
    )


def test_datei_markierung(daten: dict[str, Any]) -> None:
    b = kette_befunde(daten)[
        befund_id(f("Dateiweit.kt", "dateiweit/0"), f("Rechnen.kt", "extra/0"))
    ]
    assert b["beleg"]["markierung"]["traeger"] == "datei"


def test_nur_unsichere_grenzkante(daten: dict[str, Any]) -> None:
    befunde = kette_befunde(daten)
    for ziel in ("Ding.skaliere/0", "Sache.skaliere/0"):
        b = befunde[befund_id(f("Formen.kt", "ungewiss/1"), f("Formen.kt", ziel))]
        assert b["beleg"]["unsicher"] is True
        assert b["schwere"] == "hinweis"


def test_delegierte_eigenschaft_ist_vermerk(daten: dict[str, Any]) -> None:
    b = kette_befunde(daten)[befund_id(f("Pinsel.kt", "Pinsel.male/0"), f("Pinsel.kt", "hilfe/0"))]
    assert b["beleg"]["delegiert_gelesen"] == 1
    assert funktion(daten, f("Pinsel.kt", "Pinsel.male/0"))["metriken"]["delegiert_gelesen"] == 1
    assert funktion(daten, f("Rechnen.kt", "zeichne/1"))["metriken"]["delegiert_gelesen"] == 0


def test_anzahl_befunde_und_plausibilitaet(daten: dict[str, Any]) -> None:
    befunde = kette_befunde(daten)
    assert len(befunde) == 7
    assert sum(1 for b in befunde.values() if b["beleg"].get("unsicher")) == 2
    assert verstoesse(daten) == []
    assert funktions_verstoesse(daten) == []


def test_ohne_abschnitt_keine_kette(tmp_path: Path) -> None:
    ziel = tmp_path / "ziel"
    shutil.copytree(BEISPIEL, ziel)
    (ziel / "daidalos.toml").write_text('[projekt]\nname = "Ohne"\n', encoding="utf-8")
    daten = _scan(ziel)
    assert not kette_befunde(daten)
    assert not any(k.get("markiert") for k in daten["knoten"])
    assert "detekt" not in daten["ziel"]


def test_unbekannte_annotation_warnt(tmp_path: Path) -> None:
    ziel = tmp_path / "ziel"
    shutil.copytree(BEISPIEL, ziel)
    toml = (ziel / "daidalos.toml").read_text(encoding="utf-8")
    toml = toml.replace(
        '"de.beispiel.Deterministisch"]', '"de.beispiel.Deterministisch", "de.x.Fehlt"]'
    )
    (ziel / "daidalos.toml").write_text(toml, encoding="utf-8")
    warnungen: list[str] = []
    _scan(ziel, warnungen)
    assert any("de.x.Fehlt" in w and "nirgends" in w for w in warnungen)


def test_befehl_markierung(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ausgabe = tmp_path / "daidalos.json"
    assert main(["scan", str(BEISPIEL), "--ausgabe", str(ausgabe)]) == 0
    capsys.readouterr()
    assert main(["markierung", "--daten", str(ausgabe)]) == 0
    text = capsys.readouterr().out
    assert text.startswith("Grenzkanten der Markierungs-Kette: 5 (nur sichere)")
    # längste Kette zuerst
    assert text.index("zeichne/1 ruft unmarkiert glaette/1") < text.index("messe/1")
    assert "endet an Ausnahmen: wecke/0" in text
    assert main(["markierung", "--daten", str(ausgabe), "--unsicher", "--datei", "Formen.kt"]) == 0
    text = capsys.readouterr().out
    assert "3 (auch nur unsichere)" in text
    assert "zeichne" not in text


def test_karte_md_und_zusammenfassung(daten: dict[str, Any]) -> None:
    md = baue_karte_md(daten, None)
    assert "### Markierungs-Kette" in md
    assert "[zeichne/1 ruft unmarkiert glaette/1 (+2)](karte.html#befund=" in md
    assert "Kette 3: `glaette/1`, `runde/1`, `zurueck/1`" in md
    assert "### detekt" in md
    zusammen = Zusammenfassung(daten, None)
    text = zusammen.als_markdown()
    assert "Markierungs-Kette: 8 markierte Funktionen, 1 Ausnahmen" in text
    offen = finde_offenes(daten, None, wichtige_dateien(daten))
    assert sum(1 for b in offen.befunde if b.startswith("befund:markierung:")) == 7


# ---------------------------------------------------------------- detekt-SARIF


def _sarif(ergebnisse: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "detekt"}}, "results": ergebnisse}],
    }


def _ergebnis(regel: str, uri: str, zeile: int, level: str = "warning") -> dict[str, Any]:
    return {
        "ruleId": regel,
        "level": level,
        "message": {"text": f"Meldung {regel}"},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": zeile}}}
        ],
    }


@pytest.fixture
def mit_sarif(tmp_path: Path) -> Path:
    ziel = tmp_path / "ziel"
    shutil.copytree(BEISPIEL, ziel)
    rechnen = (ziel / KETTE / "Rechnen.kt").resolve().as_uri()
    pinsel = (ziel / KETTE / "Pinsel.kt").resolve().as_uri()
    draussen = (tmp_path / "anderswo" / "X.kt").resolve().as_uri()
    berichte = ziel / "kern" / "build" / "reports" / "detekt"
    berichte.mkdir(parents=True)
    (berichte / "main.sarif").write_text(
        json.dumps(
            _sarif(
                [
                    _ergebnis("detekt.style.MagicNumber", rechnen, 19, "error"),  # in rechneSicher
                    _ergebnis("detekt.style.WildcardImport", pinsel, 1),  # außerhalb jeder Funktion
                    _ergebnis("detekt.style.Doppelt", rechnen, 26),
                    _ergebnis("detekt.style.Draussen", draussen, 3),
                ]
            )
        ),
        encoding="utf-8",
    )
    (berichte / "test.sarif").write_text(
        json.dumps(_sarif([_ergebnis("detekt.style.Doppelt", rechnen, 26, "note")])),
        encoding="utf-8",
    )
    (berichte / "leer.sarif").write_text(json.dumps(_sarif([])), encoding="utf-8")
    (berichte / "kaputt.sarif").write_text("{ kein json", encoding="utf-8")
    return ziel


def test_sarif_befunde(mit_sarif: Path) -> None:
    warnungen: list[str] = []
    daten = _scan(mit_sarif, warnungen)
    detekt = {b["id"]: b for b in daten["befunde"] if b["quelle"] == "detekt"}
    assert daten["ziel"]["detekt"] == {"dateien": 3, "ergebnisse": 5}
    basis = "befund:detekt:detekt.style."
    treffer = detekt[f"{basis}MagicNumber:{KETTE}/Rechnen.kt:19"]
    assert treffer["knoten"] == [f("Rechnen.kt", "rechneSicher/1")]
    assert treffer["schwere"] == "fehler"
    assert treffer["beleg"] == {
        "meldung": "Meldung detekt.style.MagicNumber",
        "sarif": "kern/build/reports/detekt/main.sarif",
        "zeile": 19,
    }
    aussen = detekt[f"{basis}WildcardImport:{KETTE}/Pinsel.kt:1"]
    assert aussen["knoten"] == [f"datei:{KETTE}/Pinsel.kt"]
    doppelt = detekt[f"{basis}Doppelt:{KETTE}/Rechnen.kt:26"]
    assert doppelt["beleg"]["sarif"] == [
        "kern/build/reports/detekt/main.sarif",
        "kern/build/reports/detekt/test.sarif",
    ]
    assert doppelt["schwere"] == "warnung"  # die strengere von warning und note
    assert len(detekt) == 3
    assert any("Draussen" in w and "außerhalb" in w for w in warnungen)
    assert any("kaputt.sarif" in w and "kein gültiges SARIF" in w for w in warnungen)
    # detekt-Befunde brauchen keine Einschätzung
    offen = finde_offenes(daten, None, wichtige_dateien(daten))
    assert not any(b.startswith("befund:detekt:") for b in offen.befunde)
    text = Zusammenfassung(daten, None).als_markdown()
    assert "`detekt.style.Doppelt` 1" in text
    assert "befund:detekt:" not in text


def test_sarif_deterministisch(mit_sarif: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["scan", str(mit_sarif), "--ausgabe", str(a)]) == 0
    assert main(["scan", str(mit_sarif), "--ausgabe", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
    assert str(mit_sarif.resolve()) not in a.read_text(encoding="utf-8")


def test_relativer_pfad(tmp_path: Path) -> None:
    ziel = tmp_path.resolve()
    assert relativer_pfad((ziel / "a" / "B.kt").as_uri(), ziel) == "a/B.kt"
    assert relativer_pfad("a/B.kt", ziel) == "a/B.kt"
    assert relativer_pfad((ziel.parent / "B.kt").as_uri(), ziel) is None
    assert relativer_pfad("https://beispiel.invalid/B.kt", ziel) is None
