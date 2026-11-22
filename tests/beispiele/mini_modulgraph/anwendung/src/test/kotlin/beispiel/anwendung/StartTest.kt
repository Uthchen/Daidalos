package beispiel.anwendung

import beispiel.kern.labor.protokoll.Journal

class StartTest {
    fun pruefe(): Boolean = Start().los() == 0 && Journal.text.isNotEmpty()
}
