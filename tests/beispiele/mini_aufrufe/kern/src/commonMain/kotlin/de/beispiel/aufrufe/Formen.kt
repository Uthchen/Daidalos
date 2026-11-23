package de.beispiel.aufrufe

import de.beispiel.marken.Strichpfad

// Schnittstelle mit zwei Umsetzungen, Aufruf über die Schnittstelle, super-Aufruf
interface Form {
    fun flaeche(): Double
}

class Kreis(val radius: Double) : Form {
    override fun flaeche(): Double = radius * radius * 3.0
}

class Quadrat(val seite: Double) : Form {
    override fun flaeche(): Double = seite * seite
}

@Strichpfad
fun summe(form: Form): Double {
    return form.flaeche()
}

open class Basis {
    open fun beschreibe(): String = "Basis"
}

class Abgeleitet : Basis() {
    override fun beschreibe(): String {
        return super.beschreibe() + "!"
    }
}
