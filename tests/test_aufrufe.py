"""Funktionen und Aufrufgraph (A07, A07b) am erfundenen Beispiel ``mini_aufrufe``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.adapter.kotlin_funktionen import lies_funktionen
from daidalos.cli import main
from plausibilitaet import funktions_verstoesse, indirekte_ruft_kanten, verstoesse

ZIEL = BEISPIELE / "mini_aufrufe"
KERN = "kern/src/commonMain/kotlin/de/beispiel/aufrufe"
APP = "app/src/main/kotlin/de/beispiel/app"


@pytest.fixture(scope="module")
def daten(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ausgabe = tmp_path_factory.mktemp("aufrufe") / "daidalos.json"
    assert main(["scan", str(ZIEL), "--ausgabe", str(ausgabe)]) == 0
    return json.loads(ausgabe.read_text(encoding="utf-8"))


def f(pfad: str, rest: str) -> str:
    return f"funktion:{pfad}#{rest}"


def kante(daten: dict[str, Any], art: str, von: str, nach: str) -> dict[str, Any] | None:
    for k in daten["kanten"]:
        if k["art"] == art and k["von"] == von and k["nach"] == nach:
            return k
    return None


def ruft(daten: dict[str, Any], von: str, nach: str) -> dict[str, Any]:
    k = kante(daten, "ruft", von, nach)
    assert k is not None, f"{von} -> {nach} fehlt"
    return k


def ziele(daten: dict[str, Any], von: str) -> set[str]:
    return {k["nach"] for k in daten["kanten"] if k["art"] == "ruft" and k["von"] == von}


def knoten(daten: dict[str, Any], knoten_id: str) -> dict[str, Any]:
    return next(k for k in daten["knoten"] if k["id"] == knoten_id)


def stellen(k: dict[str, Any]) -> set[tuple[int, bool, str]]:
    """(Zeile, sicher, Herkunft) je Aufruf- oder Zugriffsstelle einer ruft-Kante."""
    return {(z, b["sicher"], b["herkunft"]) for b in k["beleg"] for z in b["zeilen"]}


STRICH = f"{KERN}/Strich.kt"
WERKZEUG = f"{KERN}/Werkzeug.kt"
VIELE = f"{KERN}/Viele.kt"
FORMEN = f"{KERN}/Formen.kt"
HILFEN = f"{KERN}/hilfe/Hilfen.kt"
ZUGRIFFE = f"{KERN}/Zugriffe.kt"
TYPEN = f"{KERN}/Typen.kt"


def test_ueberladung_nach_stelligkeit(daten: dict[str, Any]) -> None:
    zeichne = f(STRICH, "Strich.zeichne/1")
    k = ruft(daten, zeichne, f(STRICH, "Strich.setze/1"))
    assert k["sicher"] and k["beleg"] == [{"herkunft": "this", "sicher": True, "zeilen": [39]}]


def test_ueberladung_gleicher_stelligkeit(daten: dict[str, Any]) -> None:
    # Id mit Typen an beiden, Kante unsicher zu beiden
    for typen in ("(Int,Float)", "(Punkt,Float)"):
        ziel = f(STRICH, f"Strich.setze/2{typen}")
        knoten(daten, ziel)
        k = ruft(daten, f(STRICH, "Strich.zeichne/1"), ziel)
        assert not k["sicher"]
        assert k["beleg"][0]["grund"] == "ueberladung"


def test_vorgabewert_und_vararg(daten: dict[str, Any]) -> None:
    zeichne = f(STRICH, "Strich.zeichne/1")
    assert ruft(daten, zeichne, f(STRICH, "Strich.male/2"))["sicher"]
    assert ruft(daten, zeichne, f(STRICH, "Strich.sammle/1"))["sicher"]
    sammle = knoten(daten, f(STRICH, "Strich.sammle/1"))
    assert sammle["parameter"] == ["Punkt"]
    assert sammle["parameter_vararg"] == [0]
    assert "parameter_vorgabe" not in sammle
    male = knoten(daten, f(STRICH, "Strich.male/2"))
    assert male["parameter"] == ["Int", "Float"]
    assert male["parameter_vorgabe"] == [1]
    assert "parameter_vararg" not in male


def test_nachgestelltes_lambda_und_aufruf_im_lambda(daten: dict[str, Any]) -> None:
    alles = f(WERKZEUG, "zeichneAlles/1")
    assert ruft(daten, alles, f(WERKZEUG, "wiederhole/2"))["sicher"]
    k = ruft(daten, alles, f(STRICH, "Strich.zeichne/1"))
    assert k["sicher"] and k["beleg"][0]["herkunft"] == "parameter"
    # aktion() ist ein Wert, keine Funktion
    assert ziele(daten, f(WERKZEUG, "wiederhole/2")) == set()


def test_lokale_funktion_gehoert_zur_umgebenden(daten: dict[str, Any]) -> None:
    alles = f(WERKZEUG, "zeichneAlles/1")
    assert not any(k["id"].endswith("#hilf/0") for k in daten["knoten"] if k["art"] == "funktion")
    assert ruft(daten, alles, f(WERKZEUG, "Zaehler.erhoehe/0"))["beleg"][0]["herkunft"] == "objekt"


def test_erweiterung_bekannt_und_unbekannt(daten: dict[str, Any]) -> None:
    alles = f(WERKZEUG, "zeichneAlles/1")
    strich = ruft(daten, alles, f(HILFEN, "[Strich]laenge/0"))
    # Zeile 34 über den Rückgabetyp von liefereStrich (A07b), Zeile 35 externer Rückgabewert
    assert stellen(strich) == {
        (33, True, "erweiterung"),
        (34, True, "erweiterung"),
        (35, False, "unbekannter-empfaenger"),
    }
    punkt = ruft(daten, alles, f(HILFEN, "[Punkt]laenge/0"))
    assert not punkt["sicher"]
    assert ruft(daten, f(STRICH, "Strich.zeichne/1"), f(STRICH, "[Punkt]verschiebe/1"))["sicher"]


def test_companion_und_object(daten: dict[str, Any]) -> None:
    init = f(STRICH, "Strich.<init>/1")
    k = ruft(daten, init, f(STRICH, "Punkt.Companion.ursprung/0"))
    assert k["sicher"] and k["beleg"][0]["herkunft"] == "objekt"


def test_schnittstelle_ueberschreibt_und_super(daten: dict[str, Any]) -> None:
    flaeche = f(FORMEN, "Form.flaeche/0")
    assert ruft(daten, f(FORMEN, "summe/1"), flaeche)["sicher"]
    for klasse in ("Kreis", "Quadrat"):
        k = kante(daten, "ueberschreibt", f(FORMEN, f"{klasse}.flaeche/0"), flaeche)
        assert k is not None and k["sicher"]
    k = ruft(daten, f(FORMEN, "Abgeleitet.beschreibe/0"), f(FORMEN, "Basis.beschreibe/0"))
    assert k["beleg"][0]["herkunft"] == "super"


def test_expect_actual(daten: dict[str, Any]) -> None:
    expect = f(VIELE, "plattformName/0")
    actual = f("kern/src/jvmMain/kotlin/de/beispiel/aufrufe/Plattform.kt", "plattformName/0")
    assert ziele(daten, f(VIELE, "begruesse/0")) == {expect}
    jvm = "kern/src/jvmMain/kotlin/de/beispiel/aufrufe/Plattform.kt"
    assert ziele(daten, f(jvm, "jvmGruss/0")) == {actual}
    k = kante(daten, "actual", actual, expect)
    assert k is not None and k["sicher"]


def test_konstruktor_mit_init_und_implizit(daten: dict[str, Any]) -> None:
    init = knoten(daten, f(STRICH, "Strich.<init>/1"))
    assert "implizit" not in init
    assert ruft(daten, f(STRICH, "Strich.<init>/1"), f(STRICH, "Strich.pruefe/0"))["sicher"]
    punkt = knoten(daten, f(STRICH, "Punkt.<init>/2"))
    assert punkt["implizit"] is True
    assert ruft(daten, f(STRICH, "Punkt.Companion.ursprung/0"), punkt["id"])["sicher"]


def test_gleiches_paket_alias_und_stern_import(daten: dict[str, Any]) -> None:
    alles = f(WERKZEUG, "zeichneAlles/1")
    assert ruft(daten, alles, f(WERKZEUG, "fakultaet/1"))["sicher"]
    assert ruft(daten, alles, f(HILFEN, "halbiere/1"))["beleg"][0]["herkunft"] == "import"
    # Alias in einer Funktionsreferenz
    assert ruft(daten, alles, f(HILFEN, "verdopple/1"))["beleg"][0]["herkunft"] == "referenz"
    k = ruft(daten, f(VIELE, "begruesse/0"), f(VIELE, "plattformName/0"))
    assert k["beleg"][0]["herkunft"] == "ohne-empfaenger"
    test = "kern/src/commonTest/kotlin/de/beispiel/aufrufe/StrichTest.kt"
    k = ruft(daten, f(test, "StrichTest.pruefeZeichnen/0"), f(test, "nurImTest/0"))
    assert k["rolle"] == "test"


def test_rekursion(daten: dict[str, Any]) -> None:
    k = ruft(daten, f(WERKZEUG, "fakultaet/1"), f(WERKZEUG, "fakultaet/1"))
    assert k["sicher"]
    assert knoten(daten, f(WERKZEUG, "fakultaet/1"))["metriken"]["fan_in"] == 1  # ohne sich selbst


def test_ketten_unsicher_oder_unaufgeloest(daten: dict[str, Any]) -> None:
    ketten = f(VIELE, "ketten/0")
    for klasse in ("Eins", "Zwei"):
        assert not ruft(daten, ketten, f(VIELE, f"{klasse}.teil/0"))["sicher"]
    assert not any(k.endswith("wert/0") for k in ziele(daten, ketten))
    (befund,) = [b for b in daten["befunde"] if b["id"].startswith("befund:unaufgeloest:aufruf:")]
    assert befund["beleg"] == {
        "anzahl": 1,
        "art": "aufruf",
        "namen": [{"anzahl": 1, "grund": "zu-viele-kandidaten", "name": "wert"}],
    }


def test_kommentar_string_interpolation(daten: dict[str, Any]) -> None:
    alles = f(WERKZEUG, "zeichneAlles/1")
    assert f(STRICH, "Strich.pruefe/0") not in ziele(daten, alles)
    assert ruft(daten, alles, f(WERKZEUG, "fakultaet/1"))["beleg"][0]["zeilen"] == [30]


def test_testcode_unsichtbar_und_extern(daten: dict[str, Any]) -> None:
    testlos = knoten(daten, f(WERKZEUG, "testlos/0"))
    assert ziele(daten, testlos["id"]) == set()
    assert testlos["metriken"]["externe_aufrufe"] == 1
    # println (zweimal), listOf, map, holeStrich: extern
    assert knoten(daten, f(WERKZEUG, "zeichneAlles/1"))["metriken"]["externe_aufrufe"] == 5


def test_eigenschaftskette_und_enum(daten: dict[str, Any]) -> None:
    k = ruft(daten, f(f"{APP}/Bedienung.kt", "bediene/1"), f(STRICH, "Strich.pruefe/0"))
    assert k["sicher"] and k["beleg"][0]["herkunft"] == "parameter"
    anlage = f"{KERN}/Anlage.kt"
    assert ziele(daten, f(anlage, "lautstaerke/0")) == {f(anlage, "Modus.stufe/0")}


def test_apply_mit_empfaenger(daten: dict[str, Any]) -> None:
    k = ruft(daten, f(f"{APP}/Haupt.kt", "main/0"), f(STRICH, "Strich.pruefe/0"))
    assert k["sicher"] and k["beleg"][0]["herkunft"] == "this"


def test_annotationen(daten: dict[str, Any]) -> None:
    werkzeug = knoten(daten, f"datei:{WERKZEUG}")
    assert werkzeug["annotationen"] == [
        {"name": "JvmName", "sicher": False},
        {"name": "de.beispiel.marken.Strichpfad", "sicher": True},
    ]
    assert knoten(daten, f(FORMEN, "summe/1"))["annotationen"] == [
        {"name": "de.beispiel.marken.Strichpfad", "sicher": True}
    ]
    viele = knoten(daten, f"datei:{VIELE}")
    eins = next(k for k in viele["klassen"] if k["name"] == "Eins")
    assert eins["annotationen"] == [{"name": "de.beispiel.fremdmarken.Strichpfad", "sicher": True}]
    # Annotation mit Argument auf eigener Zeile nach einer Ausdrucksfunktion
    assert knoten(daten, f(VIELE, "ketten/0"))["annotationen"] == [
        {"name": "Suppress", "sicher": False}
    ]


def test_klassen_und_obertypen(daten: dict[str, Any]) -> None:
    formen = knoten(daten, f"datei:{FORMEN}")
    assert formen["funktionen"] == 8
    kreis = next(k for k in formen["klassen"] if k["name"] == "Kreis")
    assert kreis["art"] == "klasse"
    assert kreis["obertypen"] == [{"name": "Form", "voll": "de.beispiel.aufrufe.Form"}]
    assert next(k for k in formen["klassen"] if k["name"] == "Form")["art"] == "schnittstelle"


def test_komplexitaet_und_zeilen(daten: dict[str, Any]) -> None:
    pruefe = knoten(daten, f(STRICH, "Strich.pruefe/0"))["metriken"]
    assert pruefe["komplexitaet"] == 3  # if und ||
    assert pruefe["zeilen"] == 5


def test_plausibilitaet(daten: dict[str, Any]) -> None:
    assert verstoesse(daten) == []
    assert funktions_verstoesse(daten) == []
    # bediene: Strich kommt in Bedienung.kt nicht vor
    assert len(indirekte_ruft_kanten(daten)) == 1


# ---------------------------------------------------------------- A07b: Accessoren


def test_getter_ueber_this_parameter_und_kette(daten: dict[str, Any]) -> None:
    getter = f(ZUGRIFFE, "Konto.<get-voll>/0")
    selbst = ruft(daten, f(ZUGRIFFE, "Konto.pruefeSelbst/0"), getter)
    # ``voll && this.voll``: zwei Lesestellen in einer Zeile, eine Kante mit Gewicht 2
    assert selbst["sicher"] and selbst["gewicht"] == 2
    assert selbst["beleg"] == [{"herkunft": "lesen", "sicher": True, "zeilen": [23, 23]}]
    buche = ruft(daten, f(ZUGRIFFE, "buche/2"), getter)
    # ``konto.voll`` (Parameter) und ``bank.konto.voll`` (Kette)
    assert stellen(buche) == {(32, True, "lesen"), (36, True, "lesen")}


def test_setter_bei_zuweisung_und_plus_gleich(daten: dict[str, Any]) -> None:
    setter = f(ZUGRIFFE, "Konto.<set-stand>/1")
    k = ruft(daten, f(ZUGRIFFE, "Konto.pruefeSelbst/0"), setter)
    assert k["beleg"] == [{"herkunft": "schreiben", "sicher": True, "zeilen": [21, 22]}]
    assert stellen(ruft(daten, f(ZUGRIFFE, "buche/2"), setter)) == {(33, True, "schreiben")}
    assert knoten(daten, setter)["parameter"] == [None]
    # der Setter ruft selbst weiter
    assert ruft(daten, setter, f(ZUGRIFFE, "Konto.maximal/1"))["sicher"]


def test_ohne_accessor_und_delegiert_keine_kante(daten: dict[str, Any]) -> None:
    # ``konto.einfach``, ``konto.stand`` (nur Setter) und ``konto.faul`` (by lazy)
    assert ziele(daten, f(ZUGRIFFE, "buche/2")) == {
        f(ZUGRIFFE, "Konto.<get-voll>/0"),
        f(ZUGRIFFE, "Konto.<set-stand>/1"),
    }
    datei = knoten(daten, f"datei:{ZUGRIFFE}")
    konto = next(k for k in datei["klassen"] if k["name"] == "Konto")
    assert konto["eigenschaften"] == [
        {"delegiert": False, "name": "start", "zeile": 5},
        {"delegiert": False, "name": "stand", "zeile": 6},
        {"delegiert": False, "name": "voll", "zeile": 11},
        {"delegiert": False, "name": "einfach", "zeile": 14},
        {"delegiert": True, "name": "faul", "zeile": 16},
    ]
    assert datei["eigenschaften"] == [{"delegiert": False, "name": "GRENZE", "zeile": 27}]


# ---------------------------------------------------------------- A07b: Typen durch Nachschlagen


def test_typen_durch_nachschlagen(daten: dict[str, Any]) -> None:
    male = ruft(daten, f(TYPEN, "typen/2"), f(TYPEN, "Pinsel.male/0"))
    assert stellen(male) == {
        # neuerPinsel().male(), neuerPinsel().naechster().male(), bauePinsel().male()
        (25, True, "rueckgabe"),
        (26, True, "rueckgabe"),
        (27, True, "rueckgabe"),
        # irgendein() = neuerPinsel(): Ausdrucksfunktion ohne Konstruktor
        (28, False, "unbekannter-empfaenger"),
        (29, True, "konstruktor-ergebnis"),
        # val k = neuerPinsel(); val kopie = k
        (31, True, "initialisierer"),
        (33, True, "initialisierer"),
        # as, as?
        (34, True, "cast"),
        (35, True, "cast"),
        # listOf(k).first(): Rückgabetyp extern, unverändert unsicher
        (37, False, "unbekannter-empfaenger"),
    }
    naechster = ruft(daten, f(TYPEN, "typen/2"), f(TYPEN, "Pinsel.naechster/0"))
    assert stellen(naechster) == {(26, True, "rueckgabe")}
    # ``atelier!!.benutze()``: ``!!`` ist durchsichtig
    assert stellen(ruft(daten, f(TYPEN, "typen/2"), f(TYPEN, "Atelier.benutze/0"))) == {
        (36, True, "parameter")
    }
    # Eigenschaft ``val pinsel = neuerPinsel()``
    benutze = ruft(daten, f(TYPEN, "Atelier.benutze/0"), f(TYPEN, "Pinsel.male/0"))
    assert stellen(benutze) == {(21, True, "initialisierer")}


def test_ketten_ueber_unbekannte_ausdrucksfunktion_bleiben_unsicher(
    daten: dict[str, Any],
) -> None:
    # ``fun irgendwas() = liefere()``: kein Konstruktor, also kein Typ
    ketten = f(VIELE, "ketten/0")
    assert stellen(ruft(daten, ketten, f(VIELE, "Eins.teil/0"))) == {
        (25, False, "unbekannter-empfaenger")
    }


# ---------------------------------------------------------------- A07b: kleinere Ausgabe


def test_keine_enthaelt_kante_zu_funktionen(daten: dict[str, Any]) -> None:
    assert not [
        k for k in daten["kanten"] if k["art"] == "enthaelt" and k["nach"].startswith("funktion:")
    ]
    # Funktionsknoten ohne leere Listen und ohne ``false``
    for k in daten["knoten"]:
        if k["art"] != "funktion":
            continue
        for feld in ("annotationen", "modifikatoren", "parameter"):
            assert k.get(feld, [None]) != [], (k["id"], feld)
        assert k.get("implizit", True) is True
        for b in (b for x in daten["kanten"] if x["art"] == "ruft" for b in x["beleg"]):
            assert b["zeilen"] == sorted(b["zeilen"])


def test_leser_ohne_enthaelt_kante(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], daten: dict[str, Any]
) -> None:
    """render, zusammenfassung, arbeitsblatt, pfad und aufrufe kommen ohne die Kante aus."""
    ziel = tmp_path / "ziel"
    ausgabe = ziel / "docs" / "daidalos"
    ausgabe.mkdir(parents=True)
    pfad = ausgabe / "daidalos.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    assert main(["render", str(ziel)]) == 0
    assert (ausgabe / "karte.html").exists()
    assert main(["zusammenfassung", str(ziel)]) == 0
    assert "Funktionen:" in capsys.readouterr().out
    assert main(["arbeitsblatt", ZUGRIFFE, str(ziel)]) == 0
    blatt = capsys.readouterr().out
    assert "Konto.<get-voll>/0" in blatt and "Konto.<set-stand>/1" in blatt
    assert main(["pfad", "buche", "Konto.maximal", "--daten", str(pfad)]) == 0
    weg = capsys.readouterr().out
    assert "Konto.<set-stand>/1" in weg and "Zugriffe.kt:33  schreiben" in weg
    assert main(["aufrufe", "Konto.maximal", "--rueckwaerts", "--daten", str(pfad)]) == 0
    assert "← Konto.<set-stand>/1" in capsys.readouterr().out


def test_zwei_laeufe_byte_gleich(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert main(["scan", str(ZIEL), "--ausgabe", str(a)]) == 0
    assert main(["scan", str(ZIEL), "--ausgabe", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()


def test_crlf_aendert_nichts(tmp_path: Path) -> None:
    text = (ZIEL / STRICH).read_bytes()
    lf = lies_funktionen(text)
    crlf = lies_funktionen(text.replace(b"\n", b"\r\n"))
    assert [(x.name, x.hash, x.zeilen) for x in lf.funktionen] == [
        (x.name, x.hash, x.zeilen) for x in crlf.funktionen
    ]


@pytest.mark.parametrize(
    ("name", "argumente"),
    [
        ("zeichne-vorwaerts", ["Strich.zeichne", "--unsicher"]),
        ("pruefe-rueckwaerts", ["Strich.pruefe", "--rueckwaerts", "--mit-tests"]),
        ("alles-tiefe-1", ["zeichneAlles", "--tiefe", "1"]),
    ],
)
def test_aufrufe_golden(
    name: str,
    argumente: list[str],
    capsys: pytest.CaptureFixture[str],
    aktualisiere_golden: bool,
) -> None:
    daten = ERWARTET / "mini_aufrufe.daidalos.json"
    assert main(["aufrufe", *argumente, "--daten", str(daten)]) == 0
    ausgabe = capsys.readouterr().out
    golden = ERWARTET / f"mini_aufrufe.aufrufe-{name}.txt"
    if aktualisiere_golden:
        golden.write_text(ausgabe, encoding="utf-8", newline="\n")
    assert ausgabe == golden.read_text(encoding="utf-8")


def test_pfad_auf_funktionsebene(capsys: pytest.CaptureFixture[str]) -> None:
    daten = str(ERWARTET / "mini_aufrufe.daidalos.json")
    assert main(["pfad", "zeichneAlles", "Punkt.<init>", "--daten", daten]) == 0
    text = capsys.readouterr().out
    assert "Ebene funktion" in text and "Strich.zeichne/1" in text
    assert "Werkzeug.kt:24  parameter" in text
    # nur über unsichere Kanten erreichbar
    assert main(["pfad", "ketten", "Zwei.teil", "--daten", daten]) == 0
    assert "Kein Weg" in capsys.readouterr().out
    assert main(["pfad", "ketten", "Zwei.teil", "--unsicher", "--daten", daten]) == 0
    assert "unsicher: unbekannter-empfaenger" in capsys.readouterr().out


def test_aufrufe_mehrdeutig_ist_bedienfehler(capsys: pytest.CaptureFixture[str]) -> None:
    daten = str(ERWARTET / "mini_aufrufe.daidalos.json")
    assert main(["aufrufe", "plattformName", "--daten", daten]) == 2
    assert "mehrdeutig" in capsys.readouterr().err


def test_vorangestellter_operator_gehoert_nicht_zum_empfaenger(tmp_path: Path) -> None:
    """``!Art.f(x)`` liest die Grammatik als ``(!Art).f(x)``; der Empfänger ist trotzdem ``Art``
    (A08, Entscheidung 3 zu A07b)."""
    paket = tmp_path / "src" / "de" / "a"
    paket.mkdir(parents=True)
    (paket / "Art.kt").write_text(
        "package de.a\n\nobject Art {\n    fun ist(x: Int): Boolean = x > 2\n"
        "    fun wert(): Int = 1\n}\n",
        encoding="utf-8",
    )
    (paket / "Nutzer.kt").write_text(
        "package de.a\n\nclass Nutzer {\n    fun f(x: Int) {\n"
        '        require(!Art.ist(x)) { "nein" }\n    }\n\n    fun g(): Int = -Art.wert()\n}\n',
        encoding="utf-8",
    )
    ausgabe = tmp_path / "daidalos.json"
    assert main(["scan", str(tmp_path), "--ausgabe", str(ausgabe)]) == 0
    daten = json.loads(ausgabe.read_text(encoding="utf-8"))
    ruft = [k for k in daten["kanten"] if k["art"] == "ruft"]
    assert len(ruft) == 2
    assert all(k["sicher"] and k["beleg"][0]["herkunft"] == "objekt" for k in ruft)
