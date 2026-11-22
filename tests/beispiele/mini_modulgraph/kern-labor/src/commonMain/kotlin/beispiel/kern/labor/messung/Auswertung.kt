package beispiel.kern.labor.messung

import beispiel.kern.Hilfen.kennung
import beispiel.kern.Punkt
import beispiel.kern.abstand
import beispiel.kern.zyklus.Anfang

fun auswerten(a: Punkt, b: Punkt): String = kennung() + abstand(a, b)

fun beginne(): Anfang = Anfang()

fun letzteMessung(): Messung? = null
