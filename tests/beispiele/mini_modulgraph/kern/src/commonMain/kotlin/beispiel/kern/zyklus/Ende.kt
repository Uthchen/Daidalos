package beispiel.kern.zyklus

const val ENDE_GRENZE = 2

class Ende {
    fun art(): AnfangsArt = AnfangsArt.EINS

    fun zurueck(): Anfang = Anfang()
}
