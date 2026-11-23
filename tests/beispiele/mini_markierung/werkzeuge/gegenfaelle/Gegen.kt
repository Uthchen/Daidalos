package de.beispiel.gegen

import de.beispiel.Strichpfad

// Fall: Pfad in [markierungen].ausgenommen ist weder Quelle noch Ziel
@Strichpfad
fun gegen(): Int = gegenHilfe()

fun gegenHilfe(): Int = 1
