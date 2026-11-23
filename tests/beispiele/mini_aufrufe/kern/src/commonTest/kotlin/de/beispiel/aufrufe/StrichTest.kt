package de.beispiel.aufrufe

// Testcode: sieht produktiven Code; produktiver Code sieht nurImTest() nicht
fun nurImTest(): Int = 42

class StrichTest {
    fun pruefeZeichnen() {
        val strich = Strich("t")
        strich.zeichne(2f)
        nurImTest()
    }
}
