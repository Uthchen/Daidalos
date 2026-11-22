from __future__ import annotations

from pathlib import Path

import pytest

from daidalos import export
from daidalos.export import schreibe_json


def test_schreibt_utf8_lf_und_sortiert(tmp_path: Path) -> None:
    ziel = tmp_path / "neu" / "ordner" / "daidalos.json"
    schreibe_json({"b": "Größe", "a": [1, 2]}, ziel)
    erwartet = '{\n  "a": [\n    1,\n    2\n  ],\n  "b": "Größe"\n}\n'
    assert ziel.read_bytes() == erwartet.encode("utf-8")


def test_abbruch_laesst_keine_halbe_datei(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ziel = tmp_path / "daidalos.json"
    ziel.write_text("alt\n", encoding="utf-8")

    def scheitern(*_: object) -> None:
        raise OSError("Platte voll")

    monkeypatch.setattr(export.os, "replace", scheitern)
    with pytest.raises(OSError):
        schreibe_json({"neu": True}, ziel)
    assert ziel.read_text(encoding="utf-8") == "alt\n"
    assert list(tmp_path.iterdir()) == [ziel]
