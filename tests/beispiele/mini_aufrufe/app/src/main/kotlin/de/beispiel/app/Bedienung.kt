package de.beispiel.app

import de.beispiel.aufrufe.Anlage

// Eigenschaftskette: Strich kommt in dieser Datei nicht vor
fun bediene(anlage: Anlage) {
    anlage.bank.strich.pruefe()
}
