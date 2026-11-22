from __future__ import annotations

from daidalos.adapter.kotlin import lies_kotlin
from daidalos.aufloeser import (
    HERKUNFT_IMPORT,
    HERKUNFT_PAKET,
    HERKUNFT_QUALIFIZIERT,
    PRODUKTIV,
    TEST,
    Quelldatei,
    interne_praefixe,
    loese_auf,
)


def _datei(pfad: str, quelle: str, rolle: str = PRODUKTIV, container: str = "modul::m"):
    return Quelldatei(pfad, lies_kotlin(quelle.encode("utf-8"), pfad), container, rolle)


def _kanten(dateien: list[Quelldatei]):
    return {(k.von, k.nach): k for k in loese_auf(dateien).kanten}


def test_import_mit_alias_und_objekt_mitglied() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nclass Satz\nobject Hilfen { fun kennung() = 1 }\n"),
        _datei(
            "B.kt",
            "package de.y\nimport de.x.Satz as NeuerSatz\nimport de.x.Hilfen.kennung\n"
            "val s = NeuerSatz()\n",
        ),
    ]
    kante = _kanten(dateien)[("B.kt", "A.kt")]
    assert [(b.symbol, b.herkunft, b.sicher) for b in kante.belege] == [
        ("de.x.Satz", HERKUNFT_IMPORT, True),
        ("de.x.Hilfen.kennung", HERKUNFT_IMPORT, True),
    ]
    assert kante.gewicht == 2
    assert kante.sicher


def test_mehrdeutiger_import_ist_unsicher() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nfun hilfe() = 1\n"),
        _datei("B.kt", "package de.x\nfun hilfe() = 2\n", container="modul::n"),
        _datei("C.kt", "package de.y\nimport de.x.hilfe\n"),
    ]
    kanten = _kanten(dateien)
    assert not kanten[("C.kt", "A.kt")].sicher
    assert not kanten[("C.kt", "B.kt")].sicher


def test_gleiches_paket_gross_sicher_klein_unsicher() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nclass Punkt\nfun rechne() = 1\n"),
        _datei("B.kt", "package de.x\nval p = Punkt()\nval r = rechne()\n"),
    ]
    kante = _kanten(dateien)[("B.kt", "A.kt")]
    assert {(b.symbol, b.herkunft, b.sicher) for b in kante.belege} == {
        ("de.x.Punkt", HERKUNFT_PAKET, True),
        ("de.x.rechne", HERKUNFT_PAKET, False),
    }


def test_gleiches_paket_nur_im_selben_modul_und_verdeckung() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nclass Punkt\n", container="modul::anders"),
        _datei("B.kt", "package de.x\nval p = Punkt()\n"),
        _datei("C.kt", "package de.x\nclass Kreis\n"),
        _datei("D.kt", "package de.x\nimport de.z.Kreis\nval k = Kreis()\n"),
    ]
    kanten = _kanten(dateien)
    assert ("B.kt", "A.kt") not in kanten
    assert ("D.kt", "C.kt") not in kanten


def test_produktiv_sieht_keinen_testcode() -> None:
    dateien = [
        _datei("T.kt", "package de.x\nfun hilfe() = 1\n", rolle=TEST),
        _datei("P.kt", "package de.x\nval h = hilfe()\n"),
        _datei("U.kt", "package de.x\nval h = hilfe()\n", rolle=TEST),
    ]
    kanten = _kanten(dateien)
    assert ("P.kt", "T.kt") not in kanten
    assert kanten[("U.kt", "T.kt")].rolle == TEST


def test_voll_qualifiziert() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nobject Werkzeug { fun rechne() = 1 }\n"),
        _datei("B.kt", "package de.y\nval r = de.x.Werkzeug.rechne()\n"),
    ]
    kante = _kanten(dateien)[("B.kt", "A.kt")]
    assert [(b.symbol, b.herkunft) for b in kante.belege] == [
        ("de.x.Werkzeug.rechne", HERKUNFT_QUALIFIZIERT)
    ]


def test_erweiterung_im_gleichen_paket_ist_unsicher() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nfun String.laut() = this\n"),
        _datei("B.kt", 'package de.x\nval s = "a".laut()\n'),
    ]
    kante = _kanten(dateien)[("B.kt", "A.kt")]
    assert not kante.sicher


def test_stern_import() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nclass Punkt\n"),
        _datei("B.kt", "package de.y\nimport de.x.*\nval p = Punkt()\n"),
    ]
    assert _kanten(dateien)[("B.kt", "A.kt")].belege[0].herkunft == HERKUNFT_IMPORT


def test_unaufgeloest_und_extern_und_selbst() -> None:
    dateien = [
        _datei("A.kt", "package de.x\nclass Punkt\nval p = Punkt()\n"),
        _datei("B.kt", "package de.y\nimport de.x.Fehlt\nimport kotlin.math.max\n"),
    ]
    ergebnis = loese_auf(dateien)
    assert ergebnis.kanten == []
    assert [(u.pfad, u.name) for u in ergebnis.unaufgeloest] == [("B.kt", "de.x.Fehlt")]


def test_interne_praefixe() -> None:
    assert interne_praefixe({"de.a.kern", "de.a.labor.x", "werkzeug"}) == ("de.a", "werkzeug")
