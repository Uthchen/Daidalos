package de.beispiel.app

import de.beispiel.zeichnen.Punkt
import de.beispiel.zeichnen.Strich

fun main() {
    val strich = Strich()
    strich.fuegeHinzu(Punkt(1f, 2f))
    println(strich.laenge())
}
