package beispiel.anwendung

import beispiel.anwendung.fremd.Bibliothek
import beispiel.kern.Strich
import beispiel.nativ.Insel

class Start {
    fun los(): Int = Insel.rechne_schnell(Strich().punkte.size)

    fun bibliothek(): Bibliothek = Bibliothek()
}
