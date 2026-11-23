package de.beispiel.kette

import de.beispiel.fremd.Strichpfad

// Fall: gleichnamige Annotation aus einem anderen Paket markiert nicht
@Strichpfad
fun scheinbar(): Int = hilfe()
