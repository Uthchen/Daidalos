package de.beispiel.aufrufe

// A07b: Typen durch Nachschlagen: erklärter Rückgabetyp (auch a.b().c()), Ausdrucksfunktion mit
// und ohne Konstruktor, Konstruktor-Ergebnis, Initialisierer (lokal und Eigenschaft), as, as?, !!
// und externer Rückgabetyp (bleibt unsicher)
class Pinsel {
    fun male(): Int = 1

    fun naechster(): Pinsel = Pinsel()
}

fun neuerPinsel(): Pinsel = Pinsel()

fun bauePinsel() = Pinsel()

fun irgendein() = neuerPinsel()

class Atelier {
    val pinsel = neuerPinsel()

    fun benutze(): Int = pinsel.male()
}

fun typen(x: Any, atelier: Atelier?) {
    neuerPinsel().male()
    neuerPinsel().naechster().male()
    bauePinsel().male()
    irgendein().male()
    Pinsel().male()
    val k = neuerPinsel()
    k.male()
    val kopie = k
    kopie.male()
    (x as Pinsel).male()
    (x as? Pinsel)?.male()
    atelier!!.benutze()
    listOf(k).first().male()
}
