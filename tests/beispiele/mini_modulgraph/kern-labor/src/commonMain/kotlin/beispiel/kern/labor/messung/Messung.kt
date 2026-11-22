package beispiel.kern.labor.messung

import beispiel.kern.labor.protokoll.Eintrag
import beispiel.kern.labor.protokoll.EintragsArt
import beispiel.kern.labor.protokoll.Journal

class Messung(val eintrag: Eintrag) {
    val art = EintragsArt.ROH

    fun journal(): Journal = Journal
}
