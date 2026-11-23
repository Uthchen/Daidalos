@file:Strichpfad
@file:JvmName("Werkzeuge")

package de.beispiel.aufrufe

import de.beispiel.aufrufe.hilfe.verdopple as doppelt
import de.beispiel.aufrufe.hilfe.*
import de.beispiel.marken.Strichpfad

// Oberste Ebene: gleiches Paket, Alias- und Stern-Import, nachgestelltes Lambda, Lambda,
// lokale Funktion, Funktionsreferenz, Rekursion, Kommentar und String, Interpolation,
// object, externer Aufruf, Erweiterung mit bekanntem und unbekanntem Empfänger (A07b: Rückgabe)
object Zaehler {
    fun erhoehe(): Int = 1
}

fun wiederhole(n: Int, aktion: () -> Unit) {
    for (i in 0 until n) {
        aktion()
    }
}

fun zeichneAlles(strich: Strich) {
    wiederhole(3) { strich.zeichne(1f) }
    fun hilf() = Zaehler.erhoehe()
    hilf()
    val werte = listOf(1, 2).map(::doppelt)
    println(werte)
    // strich.pruefe() zählt nicht
    val text = "strich.pruefe() zählt nicht, ${fakultaet(3)} schon"
    println(text)
    halbiere(4)
    strich.laenge()
    liefereStrich().laenge()
    holeStrich().laenge()
}

fun fakultaet(n: Int): Int = if (n <= 1) 1 else n * fakultaet(n - 1)

fun liefereStrich(): Strich = Strich("neu")

fun testlos() {
    nurImTest()
}
