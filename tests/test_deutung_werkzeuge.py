"""``daidalos deutung uebernehmen`` und ``daidalos deutung pruefen``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main

STRICH = "datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt"
ZYKLUS = "befund:zyklus:datei:produktiv:f45327fbce97"


@pytest.fixture
def ziel(tmp_path: Path) -> Path:
    """Zielrepo mit Messung im Standardordner, ohne deutung.json."""
    ziel = tmp_path / "projekt"
    shutil.copytree(BEISPIELE / "mini_modulgraph", ziel)
    (ziel / "docs" / "daidalos" / "deutung.json").unlink()
    shutil.copy(ERWARTET / "mini_modulgraph.daidalos.json", ziel / "docs/daidalos/daidalos.json")
    return ziel


def _messung() -> dict[str, Any]:
    return json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))


def _hash(knoten_id: str) -> str:
    return next(k["hash"] for k in _messung()["knoten"] if k["id"] == knoten_id)


def _uebernimm(ziel: Path, entwurf: dict[str, Any], name: str = "entwurf.json") -> int:
    datei = ziel / name
    datei.write_text(json.dumps(entwurf, ensure_ascii=False), encoding="utf-8")
    return main(["deutung", "uebernehmen", str(datei), str(ziel)])


def _deutung(ziel: Path) -> dict[str, Any]:
    return json.loads((ziel / "docs/daidalos/deutung.json").read_text(encoding="utf-8"))


def test_hash_wird_eingesetzt(ziel: Path) -> None:
    entwurf = {
        "beschreibungen": {STRICH: {"text": "Sammelt Punkte."}, "modul::kern": {"text": "K."}}
    }
    assert _uebernimm(ziel, entwurf) == 0
    d = _deutung(ziel)
    assert d["schema"] == 1
    assert d["beschreibungen"][STRICH] == {"hash": _hash(STRICH), "text": "Sammelt Punkte."}
    assert d["beschreibungen"]["modul::kern"]["hash"] == _hash("modul::kern")


def test_falscher_hash_im_entwurf_wird_ersetzt(ziel: Path) -> None:
    assert _uebernimm(ziel, {"beschreibungen": {STRICH: {"text": "T.", "hash": "sha256:x"}}}) == 0
    assert _deutung(ziel)["beschreibungen"][STRICH]["hash"] == _hash(STRICH)


def test_zusammenfuehrung(ziel: Path) -> None:
    erster = {
        "beschreibungen": {STRICH: {"text": "Alt."}, "modul::kern": {"text": "Kern."}},
        "bereiche": [
            {"beschreibung": "B.", "id": "bereich:a", "knoten": ["modul::kern"], "name": "A"}
        ],
        "einschaetzungen": [
            {"befund": ZYKLUS, "begruendung": "B.", "prioritaet": 1, "titel": "T", "vorschlag": "V"}
        ],
    }
    assert _uebernimm(ziel, erster) == 0
    zweiter = {
        "beschreibungen": {STRICH: {"text": "Neu."}},
        "bereiche": [
            {
                "beschreibung": "Z.",
                "id": "bereich:b",
                "knoten": ["modul::nativ", "modul::kern", "modul::nativ"],
                "name": "B",
            }
        ],
        "einschaetzungen": [{"befund": ZYKLUS, "begruendung": "Später.", "titel": "T2"}],
    }
    assert _uebernimm(ziel, zweiter) == 0
    d = _deutung(ziel)
    assert d["beschreibungen"][STRICH]["text"] == "Neu."
    assert d["beschreibungen"]["modul::kern"]["text"] == "Kern."  # bleibt
    assert [b["id"] for b in d["bereiche"]] == ["bereich:a", "bereich:b"]
    assert d["bereiche"][1]["knoten"] == ["modul::kern", "modul::nativ"]  # sortiert, einmal
    # Die Einschätzung wird ganz ersetzt, nicht feldweise gemischt.
    assert d["einschaetzungen"] == [{"befund": ZYKLUS, "begruendung": "Später.", "titel": "T2"}]
    assert _uebernimm(ziel, {"entfernen": ["bereich:a", STRICH, ZYKLUS]}) == 0
    d = _deutung(ziel)
    assert [b["id"] for b in d["bereiche"]] == ["bereich:b"]
    assert STRICH not in d["beschreibungen"] and d["einschaetzungen"] == []


def test_unbekannte_id_bricht_ohne_schreiben_ab(
    ziel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _uebernimm(ziel, {"beschreibungen": {STRICH: {"text": "Gut."}}}) == 0
    vorher = (ziel / "docs/daidalos/deutung.json").read_bytes()
    capsys.readouterr()
    entwurf = {
        "beschreibungen": {STRICH: {"text": "Anders."}, "modul::gibt-es-nicht": {"text": "X."}},
        "bereiche": [
            {"beschreibung": "B.", "id": "bereich:x", "knoten": ["paket::weg"], "name": "X"}
        ],
        "einschaetzungen": [{"befund": "befund:weg", "begruendung": "B.", "titel": "T"}],
        "kanten": {"kante:weg": {"text": "K."}},
    }
    assert _uebernimm(ziel, entwurf) == 2
    fehler = capsys.readouterr().err
    for teil in (
        "modul::gibt-es-nicht",
        "paket::weg",
        "befund:weg",
        "kante:weg",
        "nichts geschrieben",
    ):
        assert teil in fehler
    assert (ziel / "docs/daidalos/deutung.json").read_bytes() == vorher


@pytest.mark.parametrize(
    "entwurf",
    [
        {"beschreibungen": {STRICH: {"text": ""}}},
        {
            "einschaetzungen": [
                {"befund": ZYKLUS, "prioritaet": 1, "titel": "T", "begruendung": "B"}
            ]
        },
        {
            "einschaetzungen": [
                {
                    "befund": ZYKLUS,
                    "prioritaet": 0,
                    "titel": "T",
                    "begruendung": "B",
                    "vorschlag": "V",
                }
            ]
        },
        {
            "bereiche": [
                {"id": "zeichnen", "name": "Z", "beschreibung": "B", "knoten": ["modul::kern"]}
            ]
        },
        {"unbekannt": 1},
        {"schema": 2},
    ],
)
def test_ungueltiger_entwurf_ist_bedienfehler(ziel: Path, entwurf: dict[str, Any]) -> None:
    assert _uebernimm(ziel, entwurf) == 2
    assert not (ziel / "docs/daidalos/deutung.json").exists()


def test_kaputtes_json_ist_bedienfehler(ziel: Path) -> None:
    (ziel / "e.json").write_text("{", encoding="utf-8")
    assert main(["deutung", "uebernehmen", str(ziel / "e.json"), str(ziel)]) == 2


def test_deterministisch(ziel: Path, tmp_path: Path) -> None:
    entwurf = json.loads(
        (Path(__file__).parents[1] / "skills/daidalos/vorlagen/entwurf-beispiel.json").read_text(
            encoding="utf-8"
        )
    )
    assert _uebernimm(ziel, entwurf) == 0
    erstes = (ziel / "docs/daidalos/deutung.json").read_bytes()
    # Andere Reihenfolge im Entwurf, gleiches Ergebnis; zweimal übernehmen ändert nichts.
    umgedreht = {s: entwurf[s] for s in reversed(list(entwurf))}
    umgedreht["beschreibungen"] = dict(reversed(list(entwurf["beschreibungen"].items())))
    umgedreht["einschaetzungen"] = list(reversed(entwurf["einschaetzungen"]))
    (ziel / "docs/daidalos/deutung.json").unlink()
    assert _uebernimm(ziel, umgedreht) == 0
    assert _uebernimm(ziel, umgedreht) == 0
    zweites = (ziel / "docs/daidalos/deutung.json").read_bytes()
    assert erstes == zweites
    assert b"\r" not in erstes and erstes.endswith(b"}\n")
    assert json.loads(erstes) == json.loads(json.dumps(json.loads(erstes), sort_keys=True))


def test_pruefen_exit_codes(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Ohne deutung.json ist alles offen.
    assert main(["deutung", "pruefen", str(ziel)]) == 1
    assert "fehlt; alles ist offen" in capsys.readouterr().out
    # Kaputte deutung.json: Bedienfehler.
    (ziel / "docs/daidalos/deutung.json").write_text("{}", encoding="utf-8")
    assert main(["deutung", "pruefen", str(ziel)]) == 2
    (ziel / "docs/daidalos/deutung.json").unlink()
    # Alles Offene beschreiben und einschätzen: 0.
    capsys.readouterr()
    assert main(["zusammenfassung", str(ziel), "--json"]) == 0
    offen = json.loads(capsys.readouterr().out)["offen"]
    entwurf = {
        "beschreibungen": {b["id"]: {"text": "T."} for b in offen["beschreibungen"]},
        "einschaetzungen": [
            {"befund": b, "begruendung": "B.", "titel": "T"}
            for b in offen["befunde_ohne_einschaetzung"]
        ],
    }
    assert _uebernimm(ziel, entwurf) == 0
    assert main(["deutung", "pruefen", str(ziel)]) == 0
    assert "Offen: 0" in capsys.readouterr().out
    # Toter Verweis im Bestand: 1.
    d = _deutung(ziel)
    d["kanten"]["kante:weg"] = {"text": "K."}
    (ziel / "docs/daidalos/deutung.json").write_text(json.dumps(d), encoding="utf-8")
    assert main(["deutung", "pruefen", str(ziel)]) == 1
    assert "Toter Verweis: kanten: kante:weg" in capsys.readouterr().out


def test_render_liest_uebernommene_deutung(ziel: Path) -> None:
    assert _uebernimm(ziel, {"beschreibungen": {STRICH: {"text": "Sammelt Punkte."}}}) == 0
    assert main(["render", str(ziel)]) == 0
    md = (ziel / "docs/daidalos/KARTE.md").read_text(encoding="utf-8")
    assert "deutung.json" in md
