package de.beispiel.kette

import de.beispiel.Strichpfad

// Fälle: Aufruf einer Schnittstellenmethode mit unmarkierter Umsetzung (über
// ueberschrieben-von); nur unsichere Grenzkante (Empfänger `it` ohne Typ)
interface Form {
    fun flaeche(): Int
}

class Kreis : Form {
    override fun flaeche(): Int = 3
}

@Strichpfad
fun messe(f: Form): Int = f.flaeche()

class Ding {
    fun skaliere(): Int = 1
}

class Sache {
    fun skaliere(): Int = 2
}

@Strichpfad
fun ungewiss(liste: List<Ding>): List<Int> = liste.map { it.skaliere() }
