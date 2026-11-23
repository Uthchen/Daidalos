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


# ---------------------------------------------------------------- A08: detekt im Klon

SCHREIBE_SARIF = """\
import json, os, pathlib, sys
klon = pathlib.Path.cwd()
# umgebung aus ziele.toml, ohne Variablen-Ersetzung
assert os.environ["DAIDALOS_PROBE"] == "Wert mit $HOME", os.environ.get("DAIDALOS_PROBE")
assert (klon / "lokal.properties").read_text(encoding="utf-8") == "sdk=erfunden"
ziel = klon / "core" / "build" / "reports" / "detekt" / "detekt.sarif"
ziel.parent.mkdir(parents=True)
datei = (klon / "core/src/main/kotlin/de/beispiel/zeichnen/Strich.kt").resolve().as_uri()
ergebnis = {"ruleId": "detekt.style.Probe", "level": "warning", "message": {"text": "Probe"},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": datei},
                                                 "region": {"startLine": 3}}}]}
ziel.write_text(json.dumps({"version": "2.1.0", "runs": [{"results": [ergebnis]}]}))
print("SARIF geschrieben")
if len(sys.argv) > 1:
    print("Abbruch mit Absicht")
    sys.exit(3)
"""


def _mit_detekt(aufbau: tuple[Path, Path], argumente: str = "") -> Path:
    quelle, wurzel = aufbau
    (quelle / "lokal.properties").write_text("sdk=erfunden", encoding="utf-8")
    skript = wurzel / "schreibe_sarif.py"
    skript.write_text(SCHREIBE_SARIF, encoding="utf-8")
    toml = wurzel / "lokal" / "detekt.toml"
    toml.write_text('[detekt]\nsarif = ["**/build/reports/detekt/*.sarif"]\n', encoding="utf-8")
    befehl = json.dumps([sys.executable, skript.as_posix(), *argumente.split()])
    with (wurzel / "lokal" / "ziele.toml").open("a", encoding="utf-8") as datei:
        datei.write(
            f'konfiguration = "{toml.as_posix()}"\nkopiere = ["lokal.properties"]\n'
            f"detekt = {befehl}\n"
            'umgebung = { DAIDALOS_PROBE = "Wert mit $HOME" }\n'
        )
    return wurzel


def test_mit_detekt_schreibt_sarif_im_klon(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    wurzel = _mit_detekt(aufbau)
    assert _lauf(wurzel, "--mit-detekt") == 1
    messung = _messung(wurzel)
    assert messung["ziel"]["detekt"] == {"dateien": 1, "ergebnisse": 1}
    assert [b["regel"] for b in messung["befunde"] if b["quelle"] == "detekt"] == [
        "detekt.style.Probe"
    ]
    assert "detekt:    fertig nach" in capsys.readouterr().out
    # ohne --mit-detekt: nach dem Säubern liegt keine SARIF-Datei mehr im Klon
    assert _lauf(wurzel, "--erzwingen") == 1
    assert _messung(wurzel)["ziel"]["detekt"] == {"dateien": 0, "ergebnisse": 0}
    # kopiert wird trotzdem
    klon = wurzel / "lokal" / "ziele" / "mini" / "klon"
    assert (klon / "lokal.properties").read_text(encoding="utf-8") == "sdk=erfunden"


def test_mit_detekt_abbruch_ergibt_exit_2(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    wurzel = _mit_detekt(aufbau, "abbrechen")
    assert _lauf(wurzel, "--mit-detekt") == 2
    fehler = capsys.readouterr().err
    assert "Exit-Code 3" in fehler
    assert "Abbruch mit Absicht" in fehler


def test_mit_detekt_ohne_befehl_ist_fehler(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, wurzel = aufbau
    assert _lauf(wurzel, "--mit-detekt") == 2
    assert "detekt = [...]" in capsys.readouterr().err


@pytest.mark.parametrize("wert", ['"JAVA_HOME"', "{ JAVA_HOME = 17 }", "[1]"])
def test_umgebung_muss_tabelle_text_sein(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str], wert: str
) -> None:
    _, wurzel = aufbau
    with (wurzel / "lokal" / "ziele.toml").open("a", encoding="utf-8") as datei:
        datei.write(f"umgebung = {wert}\n")
    assert _lauf(wurzel) == 2
    assert "umgebung muss eine Tabelle" in capsys.readouterr().err


@pytest.mark.parametrize("pfad", ["../geheim.txt", "a/../../b", "/abs/datei"])
def test_kopiere_lehnt_pfade_ausserhalb_ab(
    aufbau: tuple[Path, Path], capsys: pytest.CaptureFixture[str], pfad: str
) -> None:
    _, wurzel = aufbau
    with (wurzel / "lokal" / "ziele.toml").open("a", encoding="utf-8") as datei:
        datei.write(f'kopiere = ["{pfad}"]\n')
    assert _lauf(wurzel) == 2
    assert "relativer Pfad ohne .." in capsys.readouterr().err
