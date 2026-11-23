package de.beispiel.aufrufe

// A07b: Lesen und Schreiben von Eigenschaften mit eigenem Accessor (über this, Parameter und
// Kette; Setter bei = und +=), Eigenschaft ohne Accessor, delegierte Eigenschaft
class Konto(val start: Int) {
    var stand: Int = start
        set(wert) {
            field = maximal(wert)
        }

    val voll: Boolean
        get() = stand >= GRENZE

    val einfach: Int = 3

    val faul by lazy { Konto(0) }

    fun maximal(wert: Int): Int = if (wert > GRENZE) GRENZE else wert

    fun pruefeSelbst(): Boolean {
        stand = 5
        stand += 2
        return voll && this.voll
    }
}

const val GRENZE = 100

class Bank(val konto: Konto)

fun buche(konto: Konto, bank: Bank): Int {
    if (konto.voll) return 0
    konto.stand = 1
    val vorrat = konto.faul
    println("$vorrat")
    return if (bank.konto.voll) konto.einfach else konto.stand
}
