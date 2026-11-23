"""``werkzeuge/ziel_auffrischen.py`` an einem erfundenen Mini-Repo, das der Test selbst anlegt."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, git, git_init

WERKZEUG = Path(__file__).resolve().parent.parent / "werkzeuge" / "ziel_auffrischen.py"


def _lade_werkzeug() -> Any:
    spec = importlib.util.spec_from_file_location("ziel_auffrischen", WERKZEUG)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


werkzeug = _lade_werkzeug()


def _commit(ordner: Path, text: str) -> str:
    git(ordner, "add", "-A")
    git(ordner, "commit", "-q", "-m", text)
    return git(ordner, "rev-parse", "HEAD").strip()


@pytest.fixture
def aufbau(tmp_path: Path) -> tuple[Path, Path]:
    """Quelle (Git-Repo aus mini_gradle) und Daidalos-Wurzel mit ``lokal/ziele.toml``."""
    quelle = tmp_path / "quelle"
    shutil.copytree(BEISPIELE / "mini_gradle", quelle)
    git_init(quelle)
    git(quelle, "checkout", "-q", "-b", "haupt")
    _commit(quelle, "Erster Stand")
    wurzel = tmp_path / "wurzel"
    (wurzel / "lokal").mkdir(parents=True)
    _schreibe_ziele(wurzel, quelle.as_posix(), "lokal/ziele/mini/klon")
    return quelle, wurzel


def _schreibe_ziele(wurzel: Path, quelle: str, klon: str) -> None:
    (wurzel / "lokal" / "ziele.toml").write_text(
        f'[mini]\nquelle = "{quelle}"\nklon = "{klon}"\nausgabe = "lokal/ziele/mini/daidalos"\n',
        encoding="utf-8",
    )


def _lauf(wurzel: Path, *weitere: str) -> int:
    return werkzeug.main(["mini", "--wurzel", str(wurzel), *weitere])


def _messung(wurzel: Path) -> dict[str, Any]:
    datei = wurzel / "lokal" / "ziele" / "mini" / "daidalos" / "daidalos.json"
    return json.loads(datei.read_text(encoding="utf-8"))


def _dateien(wurzel: Path) -> set[str]:
    return {k["pfad"] for k in _messung(wurzel)["knoten"] if k["art"] == "datei"}


def test_erster_lauf_legt_klon_an(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    quelle, wurzel = aufbau
    assert _lauf(wurzel) == 1  # ohne deutung.json ist alles offen
    klon = wurzel / "lokal" / "ziele" / "mini" / "klon"
    assert (klon / ".git").is_dir()
    assert git(klon, "rev-parse", "HEAD") == git(quelle, "rev-parse", "HEAD")
    # Der Klon teilt keine Objektdateien mit der Quelle (keine alternates).
    assert not (klon / ".git" / "objects" / "info" / "alternates").exists()
    messung = _messung(wurzel)
    assert messung["ziel"]["git_commit"] == git(quelle, "rev-parse", "HEAD").strip()
    assert messung["ziel"]["git_aenderungen"] is False
    ausgabe = wurzel / "lokal" / "ziele" / "mini" / "daidalos"
    assert (ausgabe / "karte.html").is_file()
    assert "nicht committet" not in (ausgabe / "KARTE.md").read_text(encoding="utf-8")
    text = capsys.readouterr().out
    assert "Erster Stand" in text
    assert "Für den Skill: Daidalos-Skill für Ziel lokal/ziele/mini/klon" in text
    assert "--daten lokal/ziele/mini/daidalos/daidalos.json" in text
    assert "--deutung lokal/ziele/mini/daidalos/deutung.json" in text
    assert "--ausgabe lokal/ziele/mini/daidalos" in text


def test_neuer_commit_wird_gescannt_uncommittetes_nicht(aufbau: tuple[Path, Path]) -> None:
    quelle, wurzel = aufbau
    _lauf(wurzel)
    neu = quelle / "kern" / "src" / "main" / "kotlin" / "Neu.kt"
    neu.parent.mkdir(parents=True, exist_ok=True)
    neu.write_text("package beispiel\n\nclass Neu\n", encoding="utf-8")
    commit = _commit(quelle, "Neue Datei")
    # Halbfertiges in der Quelle: geänderte und neue Datei, nicht committet.
    (quelle / "Halbfertig.kt").write_text("class Halb\n", encoding="utf-8")
    with (quelle / "kern" / "src" / "main" / "kotlin" / "Neu.kt").open("a", encoding="utf-8") as f:
        f.write("// noch nicht fertig\n")

    assert _lauf(wurzel) == 1
    dateien = _dateien(wurzel)
    assert "kern/src/main/kotlin/Neu.kt" in dateien
    assert "Halbfertig.kt" not in dateien
    klon = wurzel / "lokal" / "ziele" / "mini" / "klon"
    assert "noch nicht fertig" not in (klon / "kern/src/main/kotlin/Neu.kt").read_text("utf-8")
    assert _messung(wurzel)["ziel"] == {
        "name": _messung(wurzel)["ziel"]["name"],
        "git_commit": commit,
        "git_aenderungen": False,
    }


def test_stand_unveraendert(aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    _, wurzel = aufbau
    _lauf(wurzel)
    capsys.readouterr()
    assert _lauf(wurzel) == 0
    assert capsys.readouterr().out.startswith("Stand unverändert: ")
    assert _lauf(wurzel, "--erzwingen") == 1
    assert "Für den Skill:" in capsys.readouterr().out


def test_klon_wird_gesaeubert(aufbau: tuple[Path, Path]) -> None:
    quelle, wurzel = aufbau
    _lauf(wurzel)
    klon = wurzel / "lokal" / "ziele" / "mini" / "klon"
    (klon / "Fremd.kt").write_text("class Fremd\n", encoding="utf-8")
    (klon / "settings.gradle.kts").write_text("kaputt\n", encoding="utf-8")
    assert _lauf(wurzel, "--erzwingen") == 1
    assert not (klon / "Fremd.kt").exists()
    assert (klon / "settings.gradle.kts").read_bytes() == (
        quelle / "settings.gradle.kts"
    ).read_bytes()


def test_fremder_origin_bricht_ab(
    aufbau: tuple[Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    quelle, wurzel = aufbau
    _lauf(wurzel)
    andere = tmp_path / "andere"
    shutil.copytree(quelle, andere)
    _schreibe_ziele(wurzel, andere.as_posix(), "lokal/ziele/mini/klon")
    klon = wurzel / "lokal" / "ziele" / "mini" / "klon"
    (klon / "Bleibt.kt").write_text("class Bleibt\n", encoding="utf-8")
    capsys.readouterr()
    assert _lauf(wurzel) == 2
    assert "remote.origin.url" in capsys.readouterr().err
    assert (klon / "Bleibt.kt").exists()  # nichts zurückgesetzt


def test_klon_ausserhalb_von_lokal_bricht_ab(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    quelle, wurzel = aufbau
    _schreibe_ziele(wurzel, quelle.as_posix(), "ziele/mini/klon")
    assert _lauf(wurzel) == 2
    assert "nicht unter" in capsys.readouterr().err
    assert not (wurzel / "ziele").exists()
    _schreibe_ziele(wurzel, quelle.as_posix(), "lokal/../../quelle")
    assert _lauf(wurzel) == 2


def test_ziele_toml_wird_angelegt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _lauf(tmp_path) == 2
    datei = tmp_path / "lokal" / "ziele.toml"
    assert datei.is_file()
    assert "# [beispiel]" in datei.read_text(encoding="utf-8")
    assert "angelegt" in capsys.readouterr().err
    assert _lauf(tmp_path) == 2
    assert "Ziel mini fehlt" in capsys.readouterr().err


def test_mit_deutung_nichts_offen(aufbau: tuple[Path, Path]) -> None:
    _, wurzel = aufbau
    _lauf(wurzel)
    ausgabe = wurzel / "lokal" / "ziele" / "mini" / "daidalos"
    # Mini-Deutung, die alles Offene abdeckt, über den Weg des Skills.
    from daidalos.cli import main as daidalos
    from daidalos.render import lade_messung
    from daidalos.zusammenfassung import finde_offenes, wichtige_dateien

    messung = lade_messung(ausgabe / "daidalos.json")
    offen = finde_offenes(messung, None, wichtige_dateien(messung))
    entwurf = {
        "schema": 1,
        "beschreibungen": {i: {"text": "Erfunden."} for i in sorted(offen.beschreibungen)},
        "einschaetzungen": [
            {"befund": b, "titel": "Nachrangig", "begruendung": "Erfunden."} for b in offen.befunde
        ],
    }
    (ausgabe.parent / "entwurf.json").write_text(json.dumps(entwurf), encoding="utf-8")
    uebernehmen = [
        "deutung",
        "uebernehmen",
        str(ausgabe.parent / "entwurf.json"),
        "--daten",
        str(ausgabe / "daidalos.json"),
        "--deutung",
        str(ausgabe / "deutung.json"),
    ]
    assert daidalos(uebernehmen) == 0
    assert _lauf(wurzel, "--erzwingen") == 0
