package de.beispiel.aufrufe

// Eigenschaften mit Typ für Ketten, Enum-Eintrag und Enum.entries
enum class Modus {
    LEISE,
    LAUT;

    fun stufe(): Int = ordinal
}

class Werkbank {
    val strich: Strich = Strich("bank")
}

class Anlage {
    val bank = Werkbank()
}

fun lautstaerke(): Int = Modus.LAUT.stufe() + Modus.entries.size
