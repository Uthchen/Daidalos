from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from daidalos import __version__, cli
from daidalos.cli import main


def test_standard_ausgabepfad(mini_kopie: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scan", str(mini_kopie)]) == 0
    ausgabe = mini_kopie / "docs" / "daidalos" / "daidalos.json"
    daten = json.loads(ausgabe.read_text(encoding="utf-8"))
    assert daten["schema"] == 1
    stdout = capsys.readouterr().out
    assert "Dateien:   13 (davon fremd: 1)" in stdout
    assert "Module:    2 (Gradle-Kanten: 1)" in stdout
    assert "Zyklen:    datei 0/0" in stdout
    assert "Laufzeit:" in stdout


def test_standard_ziel_ist_aktuelles_verzeichnis(
    mini_kopie: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(mini_kopie)
    assert main(["scan"]) == 0
    assert (mini_kopie / "docs" / "daidalos" / "daidalos.json").is_file()


def test_ausgabe_und_konfiguration_ausserhalb(mini_kopie: Path, tmp_path: Path) -> None:
    konfig = tmp_path / "eigene.toml"
    konfig.write_text('[scan]\nausschliessen = ["app/"]\n', encoding="utf-8")
    ausgabe = tmp_path / "aus" / "x.json"
    argumente = ["scan", str(mini_kopie), "--konfiguration", str(konfig), "--ausgabe", str(ausgabe)]
    assert main(argumente) == 0
    knoten = json.loads(ausgabe.read_text(encoding="utf-8"))["knoten"]
    pfade = [k["pfad"] for k in knoten if k["art"] == "datei"]
    assert not any(p.startswith("app/") for p in pfade)
    # Die daidalos.toml im Ziel gilt dann nicht: entwurf/ ist wieder dabei.
    assert "entwurf/Alt.kt" in pfade
    assert not (mini_kopie / "docs").exists()


def test_ziel_fehlt_ist_bedienfehler(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["scan", str(tmp_path / "gibt-es-nicht")]) == 2
    assert "existiert nicht" in capsys.readouterr().err


def test_konfiguration_falsch_ist_bedienfehler(mini_kopie: Path) -> None:
    (mini_kopie / "daidalos.toml").write_text('[scan]\nfremd = "x"\n', encoding="utf-8")
    assert main(["scan", str(mini_kopie)]) == 2


def test_angegebene_konfiguration_fehlt_ist_bedienfehler(mini_kopie: Path, tmp_path: Path) -> None:
    assert main(["scan", str(mini_kopie), "--konfiguration", str(tmp_path / "nein.toml")]) == 2


def test_unbekannte_option_ist_bedienfehler() -> None:
    with pytest.raises(SystemExit) as info:
        main(["scan", "--gibt-es-nicht"])
    assert info.value.code == 2


def test_ohne_befehl_ist_bedienfehler() -> None:
    assert main([]) == 2


def test_unerwarteter_fehler_ist_code_1(
    mini_kopie: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def kaputt(*_: object, **__: object) -> None:
        raise RuntimeError("Absicht")

    monkeypatch.setattr(cli, "scanne", kaputt)
    assert main(["scan", str(mini_kopie)]) == 1
    assert "Absicht" in capsys.readouterr().err


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_python_m_daidalos() -> None:
    lauf = subprocess.run(
        [sys.executable, "-m", "daidalos", "--version"], capture_output=True, text=True
    )
    assert lauf.returncode == 0
    assert __version__ in lauf.stdout
