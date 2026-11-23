"""Funktionsebene der Karte (A09): Funktionsblock, wichtige Funktionen, Abgleich der Deutung."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main
from daidalos.deutung import uebernimm
from daidalos.karte_funktionen import funktionsblock
from daidalos.render import einbett_json
from daidalos.zusammenfassung import Zusammenfassung, finde_offenes, wichtige_dateien
from daidalos.zusammenfassung import wichtige_funktionen as wichtige

MARKEN = ("de.beispiel.Strichpfad", "de.beispiel.Deterministisch")
KETTE = "funktion:kern/src/main/kotlin/de/beispiel/kette/"


def messung(beispiel: str) -> dict[str, Any]:
    return json.loads((ERWARTET / f"{beispiel}.daidalos.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("beispiel", "marken"), [("mini_aufrufe", ()), ("mini_markierung", MARKEN)]
)
def test_funktionsblock_golden(
    beispiel: str, marken: tuple[str, ...], aktualisiere_golden: bool
) -> None:
    text = einbett_json(funktionsblock(messung(beispiel), marken)) + "\n"
    golden = ERWARTET / f"{beispiel}.karte-funktionen.json"
    if aktualisiere_golden:
        golden.write_text(text, encoding="utf-8", newline="\n")
    assert text == golden.read_text(encoding="utf-8")


def _zeilen(block: dict[str, Any]) -> dict[str, list[Any]]:
    felder = block["felder"]
    ergebnis = {}
    for z in block["funktionen"]:
        ergebnis["funktion:" + block["dateien"][z[0]] + "#" + z[1]] = dict(
            zip(felder, z, strict=True)
        )
    return ergebnis


def test_funktionsblock_inhalt() -> None:
    daten = messung("mini_markierung")
    block = funktionsblock(daten, MARKEN)
    zeilen = _zeilen(block)
    funktionen = [k for k in daten["knoten"] if k["art"] == "funktion"]
    assert set(zeilen) == {f["id"] for f in funktionen}
    # Träger der Markierung nach derselben Regel wie in der Kette
    assert zeilen[KETTE + "Dateiweit.kt#dateiweit/0"]["markierung"] == [
        "de.beispiel.Deterministisch",
        "datei",
    ]
    for f in funktionen:
        z = zeilen[f["id"]]
        assert bool(z["merkmale"] & 1) == bool(f.get("markiert"))
        assert bool(z["merkmale"] & 4) == bool(f.get("ohne_koerper"))
        assert z["zeile_von"] == f["zeile_von"]
        if not f.get("markiert"):
            assert z["markierung"] is None
    # ruft wird nach Lesezugriffen geteilt; die Summe der Gewichte bleibt
    ruft = [k for k in daten["kanten"] if k["art"] == "ruft"]
    im_block = [
        k for k in block["kanten"] if block["arten"][k[2]] in ("ruft", "lesen", "schreiben")
    ]
    assert sum(k["gewicht"] for k in ruft) == sum(k[4] for k in im_block)
    assert "lesen" in block["texte"]
    # ohne Namen der Markierungen bleibt der Träger offen
    assert all(z["markierung"] is None for z in _zeilen(funktionsblock(daten)).values())


def test_ohne_funktionsebene_kein_block() -> None:
    daten = messung("mini_gradle")
    daten["knoten"] = [k for k in daten["knoten"] if k["art"] != "funktion"]
    assert funktionsblock(daten) is None


def test_karte_bettet_block_ein(tmp_path: Path) -> None:
    ziel = tmp_path / "ziel"
    shutil.copytree(BEISPIELE / "mini_markierung", ziel)
    assert main(["scan", str(ziel)]) == 0
    assert main(["render", str(ziel)]) == 0
    html = (ziel / "docs" / "daidalos" / "karte.html").read_text(encoding="utf-8")
    block = re.search(r'<script type="application/json" id="funktionen">(.*?)</script>', html, re.S)
    assert block
    daten = json.loads(block.group(1))
    # daidalos.toml des Beispiels nennt die Markierungen: Träger gesetzt
    assert any(z[-1] for z in daten["funktionen"])
    # daidalos.json bleibt unverändert: die Karte bekommt weiter die Strukturansicht
    assert '"art":"funktion"' not in re.search(
        r'id="daidalos-daten">(.*?)</script>', html, re.S
    ).group(1)


def test_wichtige_funktionen() -> None:
    daten = messung("mini_markierung")
    wichtig = wichtige(daten)
    grenzen = {b["beleg"]["von"] for b in daten["befunde"] if b["regel"] == "markierung-verlassen"}
    assert grenzen <= set(wichtig)
    assert all("grenzkante" in wichtig[i] for i in grenzen)
    assert len(wichtig) <= 40
    knoten = {k["id"]: k for k in daten["knoten"]}
    for funktion_id, gruende in wichtig.items():
        k = knoten[funktion_id]
        assert k["rolle"] == "produktiv" and k.get("hash")
        if gruende == ["fan-in"]:
            assert k["metriken"]["fan_in"] > 0


def test_hoechstens_40_fan_in_zuerst() -> None:
    daten = messung("mini_aufrufe")
    # 50 erfundene Grenzkanten von verschiedenen produktiven Funktionen
    kandidaten = sorted(
        k["id"]
        for k in daten["knoten"]
        if k["art"] == "funktion" and k["rolle"] == "produktiv" and k.get("hash")
    )
    for nr, von in enumerate(kandidaten):
        daten["befunde"].append(
            {
                "beleg": {"von": von, "nach": von},
                "id": f"befund:x{nr}",
                "knoten": [von],
                "quelle": "daidalos",
                "regel": "markierung-verlassen",
                "schwere": "warnung",
            }
        )
    wichtig = wichtige(daten)
    assert len(wichtig) == min(40, len(kandidaten))
    fan_in = [i for i, g in wichtig.items() if "fan-in" in g]
    assert len(fan_in) == min(
        20,
        sum(
            1
            for i in kandidaten
            if any(k["id"] == i and k["metriken"]["fan_in"] > 0 for k in daten["knoten"])
        ),
    )


def test_zusammenfassung_und_pruefen(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    daten = messung("mini_markierung")
    text = Zusammenfassung(daten, None).als_markdown()
    assert "## Wichtige Funktionen" in text
    js = Zusammenfassung(daten, None).als_json()
    assert js["zahlen"]["wichtige_funktionen"] == len(js["wichtige_funktionen"])
    wichtig = wichtige(daten)
    offen = finde_offenes(daten, None, wichtige_dateien(daten))
    assert {i for i, s in offen.beschreibungen.items() if s == "fehlt"} >= set(wichtig)

    # Beschreibung einer Funktion: Hash wie bei Dateien; kein toter Verweis
    erste = sorted(wichtig)[0]
    entwurf = {"beschreibungen": {erste: {"text": "Ein Satz."}}}
    deutung = uebernimm(entwurf, None, daten)
    knoten = {k["id"]: k for k in daten["knoten"]}
    assert deutung["beschreibungen"][erste]["hash"] == knoten[erste]["hash"]
    offen = finde_offenes(daten, deutung, wichtige_dateien(daten))
    assert erste not in offen.beschreibungen
    assert not offen.tote_verweise
    js = Zusammenfassung(daten, deutung).als_json()
    assert not js["offen"]["tote_verweise"]
    assert next(f for f in js["wichtige_funktionen"] if f["id"] == erste)["deutung"] == "ok"

    # veraltet, wenn sich die Funktion ändert
    deutung["beschreibungen"][erste]["hash"] = "sha256:alt"
    offen = finde_offenes(daten, deutung, wichtige_dateien(daten))
    assert offen.beschreibungen[erste] == "veraltet"

    # deutung pruefen meldet fehlende Funktionsbeschreibungen
    pfad = tmp_path / "daidalos.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    deutung_pfad = tmp_path / "deutung.json"
    deutung_pfad.write_text(json.dumps(deutung), encoding="utf-8")
    capsys.readouterr()
    assert (
        main(
            [
                "deutung",
                "pruefen",
                str(tmp_path),
                "--daten",
                str(pfad),
                "--deutung",
                str(deutung_pfad),
            ]
        )
        == 1
    )
    ausgabe = capsys.readouterr().out
    assert erste in ausgabe
    assert sorted(wichtig)[-1] in ausgabe
