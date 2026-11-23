package de.beispiel.kette

import de.beispiel.Strichpfad

// Fälle: Klasse markiert deckt ihre Methoden und den Getter, nicht aber <init>;
// Lesen einer delegierten Eigenschaft (Vermerk)
@Strichpfad
class Pinsel(val breite: Int) {
    val startwert = vorbereite(breite)

    val doppelt: Int
        get() = breite * 2

    val faul by lazy { breite + 1 }

    fun male(): Int = doppelt + hilfe() + faul

    companion object {
        fun neu(): Pinsel = Pinsel(1)
    }
}

fun vorbereite(b: Int): Int = b

fun hilfe(): Int = 1
