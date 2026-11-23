package de.beispiel.aufrufe.hilfe

import de.beispiel.aufrufe.Punkt
import de.beispiel.aufrufe.Strich

// Ziele für Alias- und Stern-Import und zwei Erweiterungen gleichen Namens
fun verdopple(x: Int): Int = x * 2

fun halbiere(x: Int): Int = x / 2

fun Strich.laenge(): Int = name.length

fun Punkt.laenge(): Int = x + y
