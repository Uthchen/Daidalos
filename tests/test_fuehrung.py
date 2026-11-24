"""Führungen (A10): ``daidalos fuehrung uebernehmen|pruefen|liste``, Einbettung und Zusammenfassung.

Beispiel: die erfundene Führung ``tests/beispiele/mini_aufrufe/docs/daidalos/entwurf-fuehrung.json``
(4 Schritte), übernommen als Golden ``tests/erwartet/mini_aufrufe.fuehrung.json``.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main
from daidalos.fuehrung import Index, pruefe_ansicht, pruefe_entwurf

NAME = "vom-aufruf-zum-strich"
AUFRUFE = "kern/src/commonMain/kotlin/de/beispiel/aufrufe/"
STRICH = "datei:" + AUFRUFE + "Strich.kt"
ZEICHNE = "funktion:" + AUFRUFE + "Strich.kt#Strich.zeichne/1"
SAMMLE = "funktion:" + AUFRUFE + "Strich.kt#Strich.sammle/1"


@pytest.fixture
def ziel(tmp_path: Path) -> Path:
    """Kopie von ``mini_aufrufe`` mit Messung im Standardordner."""
    ziel = tmp_path / "mini_aufrufe"
    shutil.copytree(BEISPIELE / "mini_aufrufe", ziel)
    assert main(["scan", str(ziel)]) == 0
    return ziel


def _entwurf() -> dict[str, Any]:
    pfad = BEISPIELE / "mini_aufrufe" / "docs" / "daidalos" / "entwurf-fuehrung.json"
    return json.loads(pfad.read_text(encoding="utf-8"))


def _messung(ziel: Path) -> dict[str, Any]:
    return json.loads((ziel / "docs/daidalos/daidalos.json").read_text(encoding="utf-8"))


def _uebernimm(ziel: Path, entwurf: dict[str, Any]) -> int:
    datei = ziel / "entwurf.json"
    datei.write_text(json.dumps(entwurf, ensure_ascii=False), encoding="utf-8")
    return main(["fuehrung", "uebernehmen", str(datei), str(ziel)])


def _fuehrung(ziel: Path) -> Path:
    return ziel / "docs/daidalos/fuehrungen" / f"{NAME}.json"


def _ausgabe(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out


# ---------------------------------------------------------------- Übernehmen


def test_uebernehmen_golden_und_hashes(
    ziel: Path, aktualisiere_golden: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    assert f"karte.html#fuehrung={NAME}" in _ausgabe(capsys)
    golden = ERWARTET / "mini_aufrufe.fuehrung.json"
    if aktualisiere_golden:
        golden.write_bytes(_fuehrung(ziel).read_bytes())
    assert _fuehrung(ziel).read_bytes() == golden.read_bytes()

    daten = json.loads(_fuehrung(ziel).read_text(encoding="utf-8"))
    hashes = {k["id"]: k.get("hash") for k in _messung(ziel)["knoten"]}
    vierter = daten["schritte"][3]["hashes"]
    # Hashes für jeden Knoten aus hervorheben und für die Datei jedes Belegs
    assert vierter[ZEICHNE] == hashes[ZEICHNE]
    assert vierter[STRICH] == hashes[STRICH]
    # Kanten haben keinen Hash
    assert not any(k.startswith("kante:") for s in daten["schritte"] for k in s["hashes"])


def test_uebernehmen_ist_deterministisch_und_ersetzt_hashes(ziel: Path) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    erst = _fuehrung(ziel).read_bytes()
    entwurf = _entwurf()
    entwurf["schritte"][0]["hashes"] = {"modul::app": "sha256:falsch"}
    assert _uebernimm(ziel, entwurf) == 0
    assert _fuehrung(ziel).read_bytes() == erst


@pytest.mark.parametrize(
    ("aendere", "meldung"),
    [
        (
            lambda e: e["schritte"][1]["hervorheben"].append("datei:gibt/es/nicht.kt"),
            "unbekannte Id",
        ),
        (
            lambda e: e["schritte"][0].update(ansicht="#knoten=modul%3A%3Afehlt"),
            "unbekannter Knoten",
        ),
        (lambda e: e["schritte"][0].update(ansicht="#ebene=welt"), "unbekannte ebene"),
        (lambda e: e["schritte"][0].update(ansicht="#zoom=3"), "unbekannter Schlüssel"),
        (lambda e: e["schritte"][0].update(ansicht="ebene=modul"), "mit # beginnt"),
        (lambda e: e["schritte"][2].update(ansicht="#weg=vor"), "weg nur zusammen mit funktion"),
        (lambda e: e.update(name="Mit Leerzeichen"), "name"),
        (lambda e: e.update(schritte=e["schritte"][:2]), "3 bis 15"),
        (lambda e: e["schritte"][0].update(belege=[]), "mindestens einen Beleg"),
        (lambda e: e["schritte"][0]["belege"][0].update(zeile=9999), "hat nur"),
        (lambda e: e["schritte"][0].update(hervorheben=[]), "1 bis 8"),
    ],
)
def test_fehler_ergeben_exit_2_ohne_schreiben(
    ziel: Path, aendere: Any, meldung: str, capsys: pytest.CaptureFixture[str]
) -> None:
    entwurf = _entwurf()
    aendere(entwurf)
    assert _uebernimm(ziel, entwurf) == 2
    fehler = capsys.readouterr().err
    assert "nichts geschrieben" in fehler
    assert meldung in fehler
    assert not _fuehrung(ziel).parent.exists()


def test_sprungadressen_wie_in_der_karte(ziel: Path) -> None:
    index = Index.aus(_messung(ziel))
    ok = [
        "#ebene=datei",
        "#knoten=modul%3A%3Akern",
        "#befund=befund%3Azyklus%3Apaket%3Aproduktiv%3A8e8254fda44c",
        "#funktion=" + ZEICHNE,
        "#funktion=" + ZEICHNE + "&weg=rueck&tiefe=3",
        "#datei-funktionen=" + AUFRUFE + "Strich.kt",
        "#ebene=funktion&von=" + ZEICHNE + "&nach=" + SAMMLE,
        "#ebene=datei&von=" + STRICH + "&nach=datei%3A" + AUFRUFE + "Werkzeug.kt",
    ]
    for ansicht in ok:
        assert pruefe_ansicht(ansicht, index) == [], ansicht
    falsch = [
        "#funktion=" + ZEICHNE + "&weg=vor&tiefe=9",
        "#grenze=befund%3Azyklus%3Apaket%3Aproduktiv%3A8e8254fda44c",
        "#datei-funktionen=README.md",
        "#ebene=funktion&von=" + ZEICHNE,
        "#knoten=a&knoten=b",
        "#kante=kante%3Aruft%3Ax",
    ]
    for ansicht in falsch:
        assert pruefe_ansicht(ansicht, index), ansicht


def test_vorlage_im_skill_passt_zum_beispiel() -> None:
    vorlage = Path(__file__).parents[1] / "skills/daidalos/vorlagen/fuehrung-beispiel.json"
    messung = json.loads((ERWARTET / "mini_aufrufe.daidalos.json").read_text(encoding="utf-8"))
    assert pruefe_entwurf(json.loads(vorlage.read_text(encoding="utf-8")), messung) == []


# ---------------------------------------------------------------- Prüfen und Liste


def test_pruefen_ok_und_liste(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    capsys.readouterr()
    assert main(["fuehrung", "pruefen", str(ziel)]) == 0
    assert f"{NAME}: ok (4 Schritte)" in _ausgabe(capsys)
    assert main(["fuehrung", "pruefen", NAME, str(ziel)]) == 0
    assert main(["fuehrung", "pruefen", "gibt-es-nicht", str(ziel)]) == 2
    capsys.readouterr()
    assert main(["fuehrung", "liste", str(ziel)]) == 0
    assert _ausgabe(capsys) == f"{NAME}  Vom Aufruf bis zum Strich  (4 Schritte, ok)\n"


def test_veraltet_nach_aenderung(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    strich = ziel / AUFRUFE / "Strich.kt"
    strich.write_text(
        strich.read_text(encoding="utf-8").replace("this.male(2)", "this.male(3)"),
        encoding="utf-8",
    )
    assert main(["scan", str(ziel)]) == 0
    capsys.readouterr()
    assert main(["fuehrung", "pruefen", str(ziel)]) == 1
    text = _ausgabe(capsys)
    assert f"{NAME}: veraltet" in text
    assert f"Schritt 4 veraltet: geändert: {STRICH}; geändert: {ZEICHNE}" in text
    # Schritt 1 hebt das Modul hervor; sein Gruppen-Hash ändert sich mit jeder Datei darin.
    assert "Schritt 1 veraltet: geändert: modul::kern" in text
    assert main(["fuehrung", "liste", str(ziel)]) == 0
    assert "(4 Schritte, veraltet)" in _ausgabe(capsys)


def test_kaputt_nach_entfernen_einer_funktion(
    ziel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    strich = ziel / AUFRUFE / "Strich.kt"
    text = strich.read_text(encoding="utf-8")
    text = text.replace("    fun sammle(vararg punkte: Punkt) {}\n", "")
    strich.write_text(text.replace("        sammle(start, ende, Punkt(2, 2))\n", ""), "utf-8")
    assert main(["scan", str(ziel)]) == 0
    capsys.readouterr()
    assert main(["fuehrung", "pruefen", str(ziel)]) == 1
    ausgabe = _ausgabe(capsys)
    assert f"{NAME}: kaputt" in ausgabe
    assert f"Schritt 4 kaputt: Id fehlt: {SAMMLE}" in ausgabe

    # Zusammenfassung: eine Zeile unter Offen
    assert main(["zusammenfassung", str(ziel)]) == 0
    assert f"- Führung `{NAME}` kaputt (Schritte 1, 2, 3, 4)" in _ausgabe(capsys)
    assert main(["zusammenfassung", str(ziel), "--json"]) == 0
    offen = json.loads(_ausgabe(capsys))["offen"]["fuehrungen"]
    assert offen == [{"name": NAME, "schritte": [1, 2, 3, 4], "stand": "kaputt"}]


def test_kaputte_datei_wird_gemeldet(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ordner = ziel / "docs/daidalos/fuehrungen"
    ordner.mkdir(parents=True)
    (ordner / "kaputt.json").write_text("{", encoding="utf-8")
    assert main(["fuehrung", "pruefen", str(ziel)]) == 1
    assert "kaputt.json: kein gültiges JSON" in capsys.readouterr().err


# ---------------------------------------------------------------- Einbettung


def test_render_bettet_fuehrungen_ein(ziel: Path) -> None:
    assert _uebernimm(ziel, _entwurf()) == 0
    # Ein Schritt veraltet, einer kaputt (von Hand, wie nach einer Änderung im Code)
    pfad = _fuehrung(ziel)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    falsch = copy.deepcopy(daten)
    falsch["schritte"][1]["hashes"][STRICH] = "sha256:alt"
    falsch["schritte"][2]["hervorheben"].append("funktion:gibt/es#nicht/0")
    pfad.write_text(json.dumps(falsch), encoding="utf-8")

    assert main(["render", str(ziel)]) == 0
    html = (ziel / "docs/daidalos/karte.html").read_text(encoding="utf-8")
    roh = html.split('<script type="application/json" id="daidalos-fuehrungen">', 1)[1]
    block = json.loads(roh.split("</script>", 1)[0])
    assert [f["name"] for f in block] == [NAME]
    assert [s["stand"] for s in block[0]["schritte"]] == ["ok", "veraltet", "kaputt", "ok"]
    assert block[0]["stand"] == "kaputt"
    assert "hashes" not in block[0]["schritte"][0]

    md = (ziel / "docs/daidalos/KARTE.md").read_text(encoding="utf-8")
    assert "## Führungen" in md
    assert f"### [Vom Aufruf bis zum Strich](karte.html#fuehrung={NAME})" in md
    assert "Frage: Was passiert, wenn zeichneAlles einen Strich zeichnet?" in md
    assert "1. Zwei Module\n" in md
    assert "2. Werkzeug nutzt Strich *(Code geändert, Text evtl. veraltet)*" in md
    assert "3. Dreimal zeichnen *(kaputt, wird übersprungen)*" in md


def test_render_ohne_fuehrungen_unveraendert(ziel: Path) -> None:
    assert main(["render", str(ziel)]) == 0
    md = (ziel / "docs/daidalos/KARTE.md").read_text(encoding="utf-8")
    assert "Führungen" not in md
    html = (ziel / "docs/daidalos/karte.html").read_text(encoding="utf-8")
    assert '<script type="application/json" id="daidalos-fuehrungen">[]</script>' in html


def test_entwurf_mit_unbekanntem_feld(ziel: Path) -> None:
    entwurf = _entwurf()
    entwurf["schritte"][0]["zoom"] = 2
    assert any("unbekannter Schlüssel 'zoom'" in p for p in pruefe_entwurf(entwurf, _messung(ziel)))
