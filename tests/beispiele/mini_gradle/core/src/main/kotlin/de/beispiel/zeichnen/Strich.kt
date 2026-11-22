package de.beispiel.zeichnen

class Strich {
    private val punkte = mutableListOf<Punkt>()

    fun fuegeHinzu(punkt: Punkt) {
        punkte.add(punkt)
    }

    fun laenge(): Int = punkte.size
}
