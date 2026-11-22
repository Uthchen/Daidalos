package beispiel.kern

fun abstand(a: Punkt, b: Punkt): Int = (a.x - b.x) + (a.y - b.y)

fun Punkt.verschoben(d: Int): Punkt = Punkt(x + d, y)

object Hilfen {
    const val GRENZE = 3

    fun kennung(): String = "k"
}
