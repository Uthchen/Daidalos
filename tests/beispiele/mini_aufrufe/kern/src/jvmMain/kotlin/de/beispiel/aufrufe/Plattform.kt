package de.beispiel.aufrufe

// actual zu expect in commonMain; Aufruf aus jvmMain trifft das actual
actual fun plattformName(): String = "JVM"

fun jvmGruss(): String = plattformName()
