package de.beispiel.aufrufe

import de.beispiel.fremdmarken.Strichpfad

// x.a().b(): unbekannter Empfänger mit wenigen und mit zu vielen Kandidaten
@Strichpfad
class Eins { fun wert(): Int = 1; fun teil(): Int = 1 }

class Zwei { fun wert(): Int = 2; fun teil(): Int = 2 }

class Drei { fun wert(): Int = 3 }

class Vier { fun wert(): Int = 4 }

class Fuenf { fun wert(): Int = 5 }

class Sechs { fun wert(): Int = 6 }

fun liefere(): Any = Eins()

@Suppress("UNUSED")
fun ketten() {
    liefere().toString().length
    liefereEins().wert()
    liefereEins().teil()
}

fun liefereEins(): Eins = Eins()

expect fun plattformName(): String

fun begruesse(): String = "Hallo " + plattformName()
