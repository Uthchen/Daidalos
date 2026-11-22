package beispiel.kern

// Punkt ohne Import (gleiches Paket), verschoben als Erweiterung
class Strich {
    val punkte = mutableListOf<Punkt>()

    fun schiebe(p: Punkt): Punkt = p.verschoben(1)
}
