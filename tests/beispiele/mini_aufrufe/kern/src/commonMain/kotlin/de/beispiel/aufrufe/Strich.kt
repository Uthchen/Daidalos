package de.beispiel.aufrufe

import de.beispiel.marken.Strichpfad

// Überladung nach Stelligkeit und mit gleicher Stelligkeit, Vorgabewert, vararg,
// companion object, Konstruktor mit init, impliziter Konstruktor, this und Eigenschaften
class Punkt(val x: Int, val y: Int) {
    companion object {
        fun ursprung(): Punkt = Punkt(0, 0)
    }
}

class Strich(val name: String) {
    private val start: Punkt = Punkt.ursprung()
    val ende = Punkt(1, 1)

    init {
        pruefe()
    }

    fun pruefe() {
        if (name.isEmpty() || name.length > 10) {
            println("ungültig")
        }
    }

    fun setze(x: Int) = setze(x, 0f)

    fun setze(a: Int, b: Float) {}

    fun setze(p: Punkt, b: Float) {}

    fun male(farbe: Int, dicke: Float = 1f) {}

    fun sammle(vararg punkte: Punkt) {}

    @Strichpfad
    fun zeichne(dicke: Float) {
        setze(1)
        this.male(2)
        sammle(start, ende, Punkt(2, 2))
        ende.verschiebe(1)
        setze(3, dicke)
    }
}

fun Punkt.verschiebe(dx: Int): Punkt = Punkt(x + dx, y)
