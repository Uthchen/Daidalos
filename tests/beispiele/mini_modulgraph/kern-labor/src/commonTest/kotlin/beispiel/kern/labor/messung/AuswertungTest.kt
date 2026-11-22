package beispiel.kern.labor.messung

import beispiel.kern.Gibtsnicht

class AuswertungTest {
    // gleiches Paket ohne Import und voll qualifiziert
    fun pruefe(): String = auswerten(beispiel.kern.Punkt(0, 0), beispiel.kern.Punkt(1, 1))
}
