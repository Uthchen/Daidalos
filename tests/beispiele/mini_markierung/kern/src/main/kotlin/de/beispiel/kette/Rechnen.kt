package de.beispiel.kette

import de.beispiel.Deterministisch
import de.beispiel.Strichpfad
import de.beispiel.WeckenOhneDaten

// Fälle: Kette über mehrere unmarkierte Funktionen, Rekursion in der Kette (glaette → runde →
// zurueck → glaette), markiert ruft markiert, Ausnahme beendet die Kette (direkt und in der
// Kette), unsichere Fortsetzung der Kette (kette_unsicher)
@Strichpfad
fun zeichne(x: Int): Int = glaette(x) + rechneSicher(x) + wecke()

fun glaette(x: Int): Int = runde(x)

fun runde(x: Int): Int = if (x > 0) runde(x - 1) else zurueck(x)

fun zurueck(x: Int): Int = glaette(x + 1) + wecke() + listOf(Ding()).map { it.skaliere() }.size

@Deterministisch
fun rechneSicher(x: Int): Int = x * 2

@WeckenOhneDaten
fun wecke(): Int = holeDaten()

fun holeDaten(): Int = 3

fun extra(): Int = 5
