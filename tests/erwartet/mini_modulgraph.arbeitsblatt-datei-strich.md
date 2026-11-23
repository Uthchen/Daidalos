# Arbeitsblatt · Datei kern/src/commonMain/kotlin/beispiel/kern/Strich.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt` · 8 Zeilen · kotlin · Quellsatz commonMain · Fan-in 1, Fan-out 2 · wichtig: fan-in · Deutung fehlt
- Kopfkommentar: Punkt ohne Import (gleiches Paket), verschoben als Erweiterung
- deklariert:
  - ohne KDoc: class Strich (Z. 4)
  - Funktionen:
    - `funktion:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt#Strich.<init>/0` (Z. 4–5, Komplexität 1, wichtig, Deutung fehlt)
    - `funktion:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt#Strich.schiebe/1` (Z. 7, Komplexität 1)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt (Gewicht 1): beispiel.kern.Punkt Z. 5
  - kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt (Gewicht 1, unsicher): beispiel.kern.verschoben Z. 7
- genutzt von:
  - anwendung/src/main/kotlin/beispiel/anwendung/Start.kt (Gewicht 1): beispiel.kern.Strich Z. 4
