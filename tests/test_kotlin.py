from __future__ import annotations

from daidalos.adapter.kotlin import lies_kotlin

QUELLE = b"""package de.a.kern

import de.a.labor.Satz as NeuerSatz
import de.a.kern.Hilfen.kennung
import kotlin.math.*

/** Kommentar mit [de.a.x.Y] und Punkt */
class Aussen(val p: Punkt) : Schnittstelle {
    class Innen
    companion object { fun erzeuge(): Aussen = TODO() }
    fun tu(x: Strich): Int {
        val s = "Text Kreis ${x.laenge}"
        return de.a.kern.Werkzeug.rechne(x, farbe = Rot)
    }
}
object Hilfen { fun kennung() = 1; external fun nativ_fn(a: Int): Int }
fun View.abstand(): Int = formatFehler(1)
val oben: Int = 2
typealias Zahl = Int
enum class Farbe { ROT }
annotation class Markierung
"""


def test_paket_und_importe() -> None:
    datei = lies_kotlin(QUELLE)
    assert datei.paket == "de.a.kern"
    assert [(i.name, i.alias, i.zeile, i.stern) for i in datei.importe] == [
        ("de.a.labor.Satz", "NeuerSatz", 3, False),
        ("de.a.kern.Hilfen.kennung", None, 4, False),
        ("kotlin.math", None, 5, True),
    ]
    assert datei.importe[0].sichtbarer_name == "NeuerSatz"


def test_deklarationen() -> None:
    datei = lies_kotlin(QUELLE)
    oben = {d.name for d in datei.deklarationen if d.oberste_ebene}
    assert oben == {"Aussen", "Hilfen", "abstand", "oben", "Zahl", "Farbe", "Markierung"}
    verschachtelt = {d.name for d in datei.deklarationen if not d.oberste_ebene}
    assert verschachtelt == {"Aussen.Innen", "Aussen.erzeuge", "Hilfen.kennung", "Hilfen.nativ_fn"}
    abstand = next(d for d in datei.deklarationen if d.name == "abstand")
    assert abstand.erweiterung


def test_namen_ohne_kommentare_strings_und_mitglieder() -> None:
    datei = lies_kotlin(QUELLE)
    for name in ("Punkt", "Schnittstelle", "Strich", "View", "formatFehler", "Rot", "x"):
        assert name in datei.namen
    # Kommentar, String, Mitglied hinter dem Punkt, benanntes Argument
    for name in ("Kreis", "laenge", "rechne", "farbe", "Y"):
        assert name not in datei.namen
    assert "laenge" in datei.mitglieder
    assert datei.namen["Punkt"] == 8


def test_voll_qualifiziert() -> None:
    datei = lies_kotlin(QUELLE)
    assert datei.qualifiziert["de.a.kern.Werkzeug.rechne"] == 13
    assert "de.a.x.Y" not in datei.qualifiziert


def test_externe_funktionen() -> None:
    datei = lies_kotlin(QUELLE)
    assert [(e.klasse, e.name) for e in datei.externe] == [("Hilfen", "nativ_fn")]
    oben = lies_kotlin(b"package p\nexternal fun f(): Int\n", "werk/insel.kt")
    assert [(e.klasse, e.name) for e in oben.externe] == [("InselKt", "f")]
    benannt = lies_kotlin(b'@file:JvmName("Werk")\npackage p\nexternal fun f(): Int\n')
    assert benannt.externe[0].klasse == "Werk"


def test_rueckfall_fuer_annotationen_auf_eigener_zeile() -> None:
    quelle = b"""package p

@Target(AnnotationTarget.CLASS)
@Retention(AnnotationRetention.SOURCE)
annotation class Strichpfad
"""
    datei = lies_kotlin(quelle)
    assert [(d.name, d.zeile) for d in datei.deklarationen] == [("Strichpfad", 5)]
    assert "Strichpfad" not in datei.namen
