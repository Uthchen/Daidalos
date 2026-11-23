package de.beispiel.app

import de.beispiel.aufrufe.Abgeleitet
import de.beispiel.aufrufe.Kreis
import de.beispiel.aufrufe.Strich
import de.beispiel.aufrufe.summe

// Modulübergreifend: Import, lokale Variable mit Konstruktor, apply mit Empfänger
fun main() {
    val strich = Strich("haupt")
    strich.apply { pruefe() }
    println(summe(Kreis(1.0)))
    Abgeleitet().beschreibe()
}
