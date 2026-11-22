"""``daidalos zusammenfassung``: Golden-Dateien, Auswahlregel für wichtige Dateien, Abschnitt Offen.

Neu schreiben mit ``uv run pytest --aktualisiere-golden``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main
from daidalos.zusammenfassung import finde_offenes, wichtige_dateien


def _ausgabe(capsys: pytest.CaptureFixture[str], argumente: list[str]) -> str:
    capsys.readouterr()
    assert main(argumente) == 0
    return capsys.readouterr().out


@pytest.mark.parametrize("beispiel", ["mini_gradle", "mini_modulgraph"])
@pytest.mark.parametrize("form", ["md", "json"])
def test_golden(
    beispiel: str, form: str, capsys: pytest.CaptureFixture[str], aktualisiere_golden: bool
) -> None:
    golden = ERWARTET / f"{beispiel}.zusammenfassung.{form}"
    argumente = [
        "zusammenfassung",
        str(BEISPIELE / beispiel),
        "--daten",
        str(ERWARTET / f"{beispiel}.daidalos.json"),
    ]
    text = _ausgabe(capsys, argumente + (["--json"] if form == "json" else []))
    if aktualisiere_golden:
        golden.write_bytes(text.encode("utf-8"))
    assert text.encode("utf-8") == golden.read_bytes()


def test_unter_300_zeilen_und_json_gleich(capsys: pytest.CaptureFixture[str]) -> None:
    daten = str(ERWARTET / "mini_modulgraph.daidalos.json")
    ziel = str(BEISPIELE / "mini_modulgraph")
    md = _ausgabe(capsys, ["zusammenfassung", ziel, "--daten", daten])
    js = json.loads(_ausgabe(capsys, ["zusammenfassung", ziel, "--daten", daten, "--json"]))
    assert md.count("\n") < 300
    for w in js["wichtige_dateien"]:
        assert f"`{w['id']}`" in md
    assert js["zahlen"]["wichtige_dateien"] == len(js["wichtige_dateien"])


# ---------------------------------------------------------------- Auswahlregel


def _datei(pfad: str, fan_in: int = 0, **extra: Any) -> dict[str, Any]:
    modul = "modul::" + pfad.split("/", 1)[0]
    return {
        "art": "datei",
        "id": f"datei:{pfad}",
        "metriken": {"fan_in": fan_in, "fan_out": 0, "instabilitaet": None},
        "modul": modul,
        "pfad": pfad,
        "rolle": "produktiv",
        "sprache": "kotlin",
        **extra,
    }


def _kante(von: str, nach: str, art: str = "nutzt", gewicht: int = 1) -> dict[str, Any]:
    return {
        "art": art,
        "gewicht": gewicht,
        "id": f"kante:{art}:datei:{von}->datei:{nach}:produktiv",
        "nach": f"datei:{nach}",
        "rolle": "produktiv",
        "sicher": True,
        "von": f"datei:{von}",
    }


def test_auswahlregel_wichtige_dateien() -> None:
    knoten = [_datei(f"a/F{nr:02}.kt", fan_in=100 - nr) for nr in range(35)]
    knoten += [
        _datei("a/Test.kt", fan_in=500, rolle="test"),
        _datei("a/Fremd.kt", fan_in=500, fremd=True),
        _datei("a/Zyklus1.kt"),
        _datei("a/Zyklus2.kt"),
        _datei("a/Aussen.kt"),
        _datei("b/Nutzer.kt"),
        _datei("b/Leicht.kt"),
        _datei("a/Brücke.kt"),
        _datei("a/insel.c", sprache="c"),
        _datei("a/Nichts.kt"),
    ]
    trenn = _kante("a/Zyklus1.kt", "a/Zyklus2.kt")
    messung = {
        "befunde": [
            {
                "beleg": {
                    "einstiege": [
                        {"knoten": "datei:a/Zyklus1.kt", "quellen": ["datei:a/Aussen.kt"]}
                    ],
                    "trennstelle": trenn["id"],
                },
                "id": "befund:zyklus:datei:produktiv:000000000001",
                "knoten": ["datei:a/Zyklus1.kt", "datei:a/Zyklus2.kt"],
                "regel": "zyklus",
            }
        ],
        "kanten": [
            trenn,
            _kante("b/Nutzer.kt", "a/F34.kt", gewicht=3),
            _kante("b/Leicht.kt", "a/F33.kt", gewicht=2),
            _kante("a/Brücke.kt", "a/insel.c", art="jni"),
        ],
        "knoten": knoten,
    }
    wichtig = wichtige_dateien(messung)
    # Die 30 mit dem höchsten Fan-in; Test- und Fremddateien zählen nicht.
    for nr in range(30):
        assert "fan-in" in wichtig[f"datei:a/F{nr:02}.kt"]
    assert "datei:a/F30.kt" not in wichtig
    assert "datei:a/Test.kt" not in wichtig and "datei:a/Fremd.kt" not in wichtig
    assert wichtig["datei:a/Zyklus1.kt"] == ["befund", "einstieg", "trennstelle"]
    assert wichtig["datei:a/Zyklus2.kt"] == ["befund", "trennstelle"]
    # Modulübergreifende Kante ab Gewicht 3, beide Enden; Gewicht 2 reicht nicht.
    assert wichtig["datei:b/Nutzer.kt"] == ["modulkante"]
    assert wichtig["datei:a/F34.kt"] == ["modulkante"]
    assert "datei:b/Leicht.kt" not in wichtig and "datei:a/F33.kt" not in wichtig
    assert wichtig["datei:a/Brücke.kt"] == ["jni"] and wichtig["datei:a/insel.c"] == ["jni"]
    assert "datei:a/Nichts.kt" not in wichtig and "datei:a/Aussen.kt" not in wichtig


def test_trennstelle_eines_paketzyklus_nimmt_die_dateien_darunter() -> None:
    messung = json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))
    wichtig = wichtige_dateien(messung)
    befund = next(b for b in messung["befunde"] if b["id"].startswith("befund:zyklus:paket"))
    trenn = next(k for k in messung["kanten"] if k["id"] == befund["beleg"]["trennstelle"])
    dateien = {k["id"]: k for k in messung["knoten"] if k["art"] == "datei"}
    unter = [
        k
        for k in messung["kanten"]
        if k["art"] == "nutzt"
        and k["von"].startswith("datei:")
        and k["rolle"] == "produktiv"
        and dateien[k["von"]].get("paket") == trenn["von"]
        and dateien[k["nach"]].get("paket") == trenn["nach"]
    ]
    assert unter
    for k in unter:
        assert "trennstelle" in wichtig[k["von"]] and "trennstelle" in wichtig[k["nach"]]


# ---------------------------------------------------------------- Offen


def test_offen_meldet_veraltete_beschreibung() -> None:
    messung = json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))
    knoten = {k["id"]: k for k in messung["knoten"]}
    strich = "datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt"
    deutung = {
        "beschreibungen": {
            strich: {"hash": "sha256:alt", "text": "Alt."},
            "modul::kern": {"hash": knoten["modul::kern"]["hash"], "text": "Aktuell."},
        },
        "schema": 1,
    }
    offen = finde_offenes(messung, deutung, wichtige_dateien(messung))
    assert offen.beschreibungen[strich] == "veraltet"
    assert "modul::kern" not in offen.beschreibungen
    assert offen.beschreibungen["modul::nativ"] == "fehlt"


def _beschreibe_alles(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Entwurf aus dem Abschnitt Offen: jede offene Id bekommt einen Text."""
    offen = json.loads(_ausgabe(capsys, ["zusammenfassung", str(ziel), "--json"]))["offen"]
    entwurf = {
        "beschreibungen": {
            b["id"]: {"text": f"Text zu {b['id']}."} for b in offen["beschreibungen"]
        },
        "einschaetzungen": [
            {"befund": b, "begruendung": "Nachrangig.", "titel": "Befund"}
            for b in offen["befunde_ohne_einschaetzung"]
        ],
        "entfernen": [v.split(": ", 1)[1] for v in offen["tote_verweise"]],
        "schema": 1,
    }
    datei = ziel / "docs" / "daidalos" / "entwurf.json"
    datei.write_text(json.dumps(entwurf), encoding="utf-8")
    capsys.readouterr()
    assert main(["deutung", "uebernehmen", str(datei), str(ziel)]) == 0


def test_zweiter_lauf_ohne_offenes_und_gezielte_aenderung(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ziel = tmp_path / "projekt"
    shutil.copytree(BEISPIELE / "mini_modulgraph", ziel)
    (ziel / "docs" / "daidalos" / "deutung.json").unlink()
    assert main(["scan", str(ziel)]) == 0
    _beschreibe_alles(ziel, capsys)
    assert main(["deutung", "pruefen", str(ziel)]) == 0
    md = _ausgabe(capsys, ["zusammenfassung", str(ziel)])
    assert "Nichts offen. Die Deutung ist aktuell." in md

    strich = ziel / "kern/src/commonMain/kotlin/beispiel/kern/Strich.kt"
    strich.write_text(strich.read_text(encoding="utf-8") + "// geändert\n", encoding="utf-8")
    assert main(["scan", str(ziel)]) == 0
    offen = json.loads(_ausgabe(capsys, ["zusammenfassung", str(ziel), "--json"]))["offen"]
    assert offen["beschreibungen"] == [
        {"id": "datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt", "stand": "veraltet"},
        {"id": "modul::kern", "stand": "veraltet"},
        {"id": "paket::kern/beispiel.kern", "stand": "veraltet"},
    ]
    assert offen["befunde_ohne_einschaetzung"] == [] and offen["tote_verweise"] == []
    assert main(["deutung", "pruefen", str(ziel)]) == 1
