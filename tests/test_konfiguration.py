from __future__ import annotations

from pathlib import Path

import pytest

from daidalos.konfiguration import (
    STANDARD_EDITOR_BEFEHL,
    STANDARD_EDITOR_LINK,
    Konfiguration,
    KonfigurationsFehler,
    lade_konfiguration,
)


def _schreibe(tmp_path: Path, text: str) -> Path:
    pfad = tmp_path / "daidalos.toml"
    pfad.write_text(text, encoding="utf-8")
    return pfad


def test_fehlende_datei_ergibt_standardwerte(tmp_path: Path) -> None:
    konfiguration = lade_konfiguration(tmp_path / "daidalos.toml")
    assert konfiguration == Konfiguration()
    assert konfiguration.editor.befehl == STANDARD_EDITOR_BEFEHL


def test_fehlende_datei_ist_fehler_wenn_ausdruecklich_verlangt(tmp_path: Path) -> None:
    with pytest.raises(KonfigurationsFehler, match="nicht gefunden"):
        lade_konfiguration(tmp_path / "gibt-es-nicht.toml", muss_existieren=True)


def test_gueltige_datei(tmp_path: Path) -> None:
    pfad = _schreibe(
        tmp_path,
        '[scan]\nausschliessen = ["a/", "b/"]\nfremd = ["**/fremd/"]\n'
        '[editor]\nbefehl = "subl {datei}:{zeile}"\n',
    )
    konfiguration = lade_konfiguration(pfad)
    assert konfiguration.scan.ausschliessen == ("a/", "b/")
    assert konfiguration.scan.fremd == ("**/fremd/",)
    assert konfiguration.editor.befehl == "subl {datei}:{zeile}"
    assert konfiguration.quelle == pfad


def test_konfiguration_ist_unveraenderlich(tmp_path: Path) -> None:
    konfiguration = lade_konfiguration(_schreibe(tmp_path, "[scan]\n"))
    with pytest.raises(AttributeError):
        konfiguration.scan = None  # type: ignore[misc]


def test_unbekannte_schluessel_warnen_ohne_abbruch(tmp_path: Path) -> None:
    pfad = _schreibe(
        tmp_path, '[scan]\nausschliessen = []\nneu = 1\n[markierungen]\nnamen = ["X"]\n'
    )
    warnungen: list[str] = []
    konfiguration = lade_konfiguration(pfad, warne=warnungen.append)
    assert konfiguration.scan.ausschliessen == ()
    assert len(warnungen) == 2
    assert any("[scan].neu" in w for w in warnungen)
    assert any("[markierungen]" in w for w in warnungen)


def test_warnung_landet_auf_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lade_konfiguration(_schreibe(tmp_path, "[scan]\nneu = 1\n"))
    assert "[scan].neu" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("text", "schluessel"),
    [
        ('[scan]\nausschliessen = "build/"\n', "[scan].ausschliessen"),
        ("[scan]\nfremd = [1, 2]\n", "[scan].fremd"),
        ("[editor]\nbefehl = 3\n", "[editor].befehl"),
        ("scan = 5\n", "[scan]"),
    ],
)
def test_falscher_typ_ist_fehler(tmp_path: Path, text: str, schluessel: str) -> None:
    pfad = _schreibe(tmp_path, text)
    with pytest.raises(KonfigurationsFehler) as info:
        lade_konfiguration(pfad)
    assert schluessel in str(info.value)
    assert "daidalos.toml" in str(info.value)


def test_kaputtes_toml_ist_fehler(tmp_path: Path) -> None:
    with pytest.raises(KonfigurationsFehler, match="kein gültiges TOML"):
        lade_konfiguration(_schreibe(tmp_path, "[scan\n"))


def test_projektname(tmp_path: Path) -> None:
    konfiguration = lade_konfiguration(_schreibe(tmp_path, '[projekt]\nname = "Beispiel"\n'))
    assert konfiguration.projekt.name == "Beispiel"
    assert lade_konfiguration(tmp_path / "fehlt.toml").projekt.name is None


@pytest.mark.parametrize("wert", ["1", '""'])
def test_projektname_falsch(tmp_path: Path, wert: str) -> None:
    with pytest.raises(KonfigurationsFehler, match=r"\[projekt\]\.name"):
        lade_konfiguration(_schreibe(tmp_path, f"[projekt]\nname = {wert}\n"))


def test_editor_link(tmp_path: Path) -> None:
    assert lade_konfiguration(tmp_path / "fehlt.toml").editor.link == STANDARD_EDITOR_LINK
    pfad = _schreibe(tmp_path, '[editor]\nlink = "idea://open?file={pfad}&line={zeile}"\n')
    assert lade_konfiguration(pfad).editor.link == "idea://open?file={pfad}&line={zeile}"
    warnungen: list[str] = []
    lade_konfiguration(
        _schreibe(tmp_path, '[editor]\nlink = "x://{zeile}"\n'), warne=warnungen.append
    )
    assert any("{pfad}" in w for w in warnungen)
    with pytest.raises(KonfigurationsFehler, match=r"\[editor\]\.link"):
        lade_konfiguration(_schreibe(tmp_path, "[editor]\nlink = 1\n"))
