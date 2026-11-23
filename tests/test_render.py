"""``daidalos render``: karte.html, KARTE.md, Einbettung und deutung.json."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main
from daidalos.deutung import gleiche_ab
from daidalos.render import baue_karte, einbett_json, strukturansicht, wurzel_relativ

BEISPIEL_NAMEN = ["mini_gradle", "mini_modulgraph"]


def deutung_von(beispiel: str) -> Path | None:
    pfad = BEISPIELE / beispiel / "docs" / "daidalos" / "deutung.json"
    return pfad if pfad.is_file() else None


def rendere(beispiel: str, ausgabe: Path) -> Path:
    argumente = [
        "render",
        str(BEISPIELE / beispiel),
        "--daten",
        str(ERWARTET / f"{beispiel}.daidalos.json"),
        "--ausgabe",
        str(ausgabe),
    ]
    assert main(argumente) == 0
    return ausgabe


def eingebettet(html: str, element_id: str) -> str:
    treffer = re.search(
        rf'<script type="application/json" id="{element_id}">(.*?)</script>', html, re.S
    )
    assert treffer, element_id
    return treffer.group(1)


@pytest.mark.parametrize("beispiel", BEISPIEL_NAMEN)
def test_karte_md_golden(beispiel: str, tmp_path: Path, aktualisiere_golden: bool) -> None:
    rendere(beispiel, tmp_path)
    golden = ERWARTET / f"{beispiel}.KARTE.md"
    if aktualisiere_golden:
        golden.write_bytes((tmp_path / "KARTE.md").read_bytes())
    assert (tmp_path / "KARTE.md").read_bytes() == golden.read_bytes()


@pytest.mark.parametrize("beispiel", BEISPIEL_NAMEN)
def test_eingebettete_daten(beispiel: str, tmp_path: Path, aktualisiere_golden: bool) -> None:
    html = (rendere(beispiel, tmp_path) / "karte.html").read_text(encoding="utf-8")
    daten = eingebettet(html, "daidalos-daten")
    deutung = eingebettet(html, "daidalos-deutung")
    # Inhalt gleich der Messung, Prüfsumme der eingebetteten Daten als Golden.
    messung = json.loads((ERWARTET / f"{beispiel}.daidalos.json").read_text(encoding="utf-8"))
    # Die Karte bekommt die Messung ohne Funktionsebene (A07).
    assert json.loads(daten) == strukturansicht(messung)
    summe = hashlib.sha256((daten + "\n" + deutung).encode("utf-8")).hexdigest() + "\n"
    golden = ERWARTET / f"{beispiel}.karte-daten.sha256"
    if aktualisiere_golden:
        golden.write_text(summe, encoding="utf-8", newline="\n")
    assert summe == golden.read_text(encoding="utf-8")


@pytest.mark.parametrize("beispiel", BEISPIEL_NAMEN)
def test_karte_struktur(beispiel: str, tmp_path: Path) -> None:
    html = (rendere(beispiel, tmp_path) / "karte.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "{{" not in html.split('<script type="application/json"')[0]
    for kennung in ('id="cy"', 'id="seite"', 'id="ebenen"', 'id="rollen"', 'id="k-nutzt"'):
        assert kennung in html
    assert "Cytoscape.js 3.28.1 (MIT)" in html
    assert "Eclipse Public License" in html
    # Kein Nachladen aus dem Netz.
    assert not re.search(r"""(src|href)\s*=\s*["']?https?://""", html)
    assert "fonts.googleapis" not in html
    assert "@import" not in html
    # Keine absoluten Pfade aus der Testumgebung.
    assert str(BEISPIELE.parent) not in html
    assert str(tmp_path) not in html


@pytest.mark.parametrize("beispiel", BEISPIEL_NAMEN)
def test_render_deterministisch(beispiel: str, tmp_path: Path) -> None:
    eins = rendere(beispiel, tmp_path / "eins")
    zwei = rendere(beispiel, tmp_path / "zwei")
    for name in ("karte.html", "KARTE.md"):
        assert (eins / name).read_bytes() == (zwei / name).read_bytes()
        assert b"\r\n" not in (eins / name).read_bytes()


def test_maskierung_von_script_ende() -> None:
    boese = {"text": "</script><script>alert(1)</script><!-- x"}
    text = einbett_json(boese)
    assert "</" not in text
    assert "<!--" not in text
    assert json.loads(text) == boese
    messung = json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))
    messung["ziel"]["name"] = "</script><b>x"
    html = baue_karte(messung, None)
    # Die Daten stehen vollständig im Script-Block und lassen sich zurücklesen.
    assert json.loads(eingebettet(html, "daidalos-daten"))["ziel"]["name"] == "</script><b>x"
    assert "<title>Karte · &lt;/script&gt;&lt;b&gt;x</title>" in html


def test_bibliotheken_in_fester_anzahl_von_script_tags(tmp_path: Path) -> None:
    html = (rendere("mini_modulgraph", tmp_path) / "karte.html").read_text(encoding="utf-8")
    # 4 Datenblöcke (seit A09 mit dem Funktionsblock), 3 Bibliotheken, 1 Kartenskript.
    assert html.count("</script>") == 8


def _messung() -> dict:
    return json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))


def test_deutung_veraltet_und_tote_verweise() -> None:
    roh = json.loads(deutung_von("mini_modulgraph").read_text(encoding="utf-8"))  # type: ignore[union-attr]
    warnungen: list[str] = []
    deutung = gleiche_ab(roh, _messung(), warnungen.append)
    beschreibungen = deutung["beschreibungen"]
    assert beschreibungen["modul::kern"]["veraltet"] is False
    assert beschreibungen["modul::anwendung"]["veraltet"] is True
    assert "modul::gibt-es-nicht" not in beschreibungen
    assert deutung["bereiche"][0]["knoten"] == ["modul::kern", "modul::kern-labor"]
    assert [e["prioritaet"] for e in deutung["einschaetzungen"]] == [1, None]
    assert len(deutung["kanten"]) == 1
    assert len(warnungen) == 4
    assert any("modul::gibt-es-nicht" in w for w in warnungen)
    assert any("000000000000" in w for w in warnungen)


def test_render_meldet_tote_verweise(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rendere("mini_modulgraph", tmp_path)
    fehler = capsys.readouterr().err
    assert "unbekannten Knoten modul::gibt-es-nicht" in fehler
    assert "unbekanntem Befund" in fehler


def test_veraltet_in_karte_md(tmp_path: Path) -> None:
    text = (rendere("mini_modulgraph", tmp_path) / "KARTE.md").read_text(encoding="utf-8")
    assert "Startet das Beispiel und setzt die Teile zusammen. *(veraltet)*" in text
    assert "](karte.html#befund=befund%3Azyklus%3Adatei%3Aproduktiv%3Af45327fbce97)" in text


def test_fehlende_daten_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["render", str(tmp_path)]) == 2
    assert "daidalos.json fehlt" in capsys.readouterr().err


def test_falsches_schema_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    daten = tmp_path / "docs" / "daidalos" / "daidalos.json"
    daten.parent.mkdir(parents=True)
    daten.write_text('{"schema": 99}', encoding="utf-8")
    assert main(["render", str(tmp_path)]) == 2
    assert "schema 99" in capsys.readouterr().err


def test_falsche_deutung_exit_2(tmp_path: Path) -> None:
    deutung = tmp_path / "deutung.json"
    deutung.write_text('{"schema": 2}', encoding="utf-8")
    argumente = [
        "render",
        str(tmp_path),
        "--daten",
        str(ERWARTET / "mini_modulgraph.daidalos.json"),
        "--deutung",
        str(deutung),
        "--ausgabe",
        str(tmp_path / "aus"),
    ]
    assert main(argumente) == 2


def test_standardpfade(tmp_path: Path) -> None:
    ordner = tmp_path / "docs" / "daidalos"
    ordner.mkdir(parents=True)
    (ordner / "daidalos.json").write_bytes((ERWARTET / "mini_gradle.daidalos.json").read_bytes())
    assert main(["render", str(tmp_path)]) == 0
    assert (ordner / "karte.html").is_file()
    assert (ordner / "KARTE.md").is_file()


def test_editor_link_standard_und_wurzel(tmp_path: Path) -> None:
    html = (rendere("mini_modulgraph", tmp_path) / "karte.html").read_text(encoding="utf-8")
    einstellungen = json.loads(eingebettet(html, "daidalos-einstellungen"))
    # Ausgabe außerhalb des Zielrepos: keine Wurzel, also kein Editor-Link.
    assert einstellungen == {"editor_link": "vscode://file/{pfad}:{zeile}", "wurzel": None}


def test_editor_link_aus_konfiguration_und_standardordner(tmp_path: Path) -> None:
    ordner = tmp_path / "docs" / "daidalos"
    ordner.mkdir(parents=True)
    (ordner / "daidalos.json").write_bytes((ERWARTET / "mini_gradle.daidalos.json").read_bytes())
    (tmp_path / "daidalos.toml").write_text(
        '[editor]\nlink = "idea://open?file={pfad}&line={zeile}"\n', encoding="utf-8"
    )
    assert main(["render", str(tmp_path)]) == 0
    html = (ordner / "karte.html").read_text(encoding="utf-8")
    einstellungen = json.loads(eingebettet(html, "daidalos-einstellungen"))
    assert einstellungen == {
        "editor_link": "idea://open?file={pfad}&line={zeile}",
        "wurzel": "../..",
    }
    assert str(tmp_path) not in html


def test_editor_link_ueber_option_konfiguration(tmp_path: Path) -> None:
    toml = tmp_path / "andere.toml"
    toml.write_text('[editor]\nlink = "subl://{pfad}:{zeile}"\n', encoding="utf-8")
    argumente = [
        "render",
        str(BEISPIELE / "mini_gradle"),
        "--daten",
        str(ERWARTET / "mini_gradle.daidalos.json"),
        "--ausgabe",
        str(tmp_path / "aus"),
        "--konfiguration",
        str(toml),
    ]
    assert main(argumente) == 0
    html = (tmp_path / "aus" / "karte.html").read_text(encoding="utf-8")
    assert json.loads(eingebettet(html, "daidalos-einstellungen"))["editor_link"] == (
        "subl://{pfad}:{zeile}"
    )
    assert main([*argumente[:-1], str(tmp_path / "fehlt.toml")]) == 2


def test_wurzel_relativ(tmp_path: Path) -> None:
    assert wurzel_relativ(tmp_path, tmp_path / "docs" / "daidalos") == "../.."
    assert wurzel_relativ(tmp_path, tmp_path) == "."
    assert wurzel_relativ(tmp_path / "a", tmp_path / "b") is None


def test_karte_md_nachrangig_ohne_zahl(tmp_path: Path) -> None:
    text = (rendere("mini_modulgraph", tmp_path) / "KARTE.md").read_text(encoding="utf-8")
    zeilen = text.splitlines()
    nachrangig = [z for z in zeilen if "Fehlende Brücke der Insel" in z]
    assert len(nachrangig) == 1
    assert nachrangig[0].startswith("- <sub>nachrangig</sub> **Fehlende Brücke der Insel**")
    assert any(z.startswith("1. **Ring im Kern auflösen**") for z in zeilen)
