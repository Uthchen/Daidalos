# Arbeitsblatt · Modul :kern

`modul::kern` · 7 Dateien · 52 Zeilen · Fan-in 2, Fan-out 0 · Deutung ok
Plugins: kotlin.multiplatform

## Kanten nach außen

- Nutzt:
  - :regeln (gradle-plugin, 1 Beleg)
- Genutzt von:
  - :kern-labor (gradle-api, 1 Beleg)
  - :anwendung (gradle-impl, 1 Beleg)
  - :nativ (gradle-impl, 1 Beleg)
  - :kern-labor (nutzt produktiv, Gewicht 4, 3 Datei-Kanten)
  - :anwendung (nutzt produktiv, Gewicht 1, 1 Datei-Kante)
  - :kern-labor (nutzt test, Gewicht 1, 1 Datei-Kante)

## Pakete

- beispiel.kern (3 Dateien, 22 Z., Fan-in 2, Fan-out 0, Deutung fehlt)
- beispiel.kern.zyklus (3 Dateien, 23 Z., Fan-in 1, Fan-out 0, Deutung ok)

## Dateien

Nach Fan-in sortiert, Tests zuletzt. Wichtige Dateien voll, die übrigen als eine Zeile.

### kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt` · 3 Zeilen · kotlin · Quellsatz commonMain · Fan-in 3, Fan-out 0 · wichtig: fan-in · Deutung fehlt
- deklariert:
  - ohne KDoc: class Punkt (Z. 3)
- genutzt von:
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt (Gewicht 1): beispiel.kern.Punkt Z. 4
  - kern/src/commonMain/kotlin/beispiel/kern/Strich.kt (Gewicht 1): beispiel.kern.Punkt Z. 5
  - kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt (Gewicht 1): beispiel.kern.Punkt Z. 3
  - kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt (Gewicht 1, test): beispiel.kern.Punkt Z. 7

### kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt` · 11 Zeilen · kotlin · Quellsatz commonMain · Fan-in 2, Fan-out 1 · wichtig: fan-in · Deutung fehlt
- deklariert:
  - ohne KDoc: fun abstand (Z. 3), fun verschoben (Z. 5), object Hilfen (Z. 7)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt (Gewicht 1): beispiel.kern.Punkt Z. 3
- genutzt von:
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt (Gewicht 2): beispiel.kern.Hilfen.kennung Z. 3, beispiel.kern.abstand Z. 5
  - kern/src/commonMain/kotlin/beispiel/kern/Strich.kt (Gewicht 1, unsicher): beispiel.kern.verschoben Z. 7

### kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt` · 7 Zeilen · kotlin · Quellsatz commonMain · Fan-in 2, Fan-out 1 · wichtig: fan-in, befund, einstieg, trennstelle · Deutung ok
- deklariert:
  - ohne KDoc: class AnfangsArt (Z. 3), class Anfang (Z. 5)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt (Gewicht 1): beispiel.kern.zyklus.Mitte Z. 6
- genutzt von:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt (Gewicht 2): beispiel.kern.zyklus.AnfangsArt Z. 6, beispiel.kern.zyklus.Anfang Z. 8
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt (Gewicht 1): beispiel.kern.zyklus.Anfang Z. 6

### kern/src/commonMain/kotlin/beispiel/kern/Strich.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt` · 8 Zeilen · kotlin · Quellsatz commonMain · Fan-in 1, Fan-out 2 · wichtig: fan-in · Deutung fehlt
- deklariert:
  - ohne KDoc: class Strich (Z. 4)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt (Gewicht 1): beispiel.kern.Punkt Z. 5
  - kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt (Gewicht 1, unsicher): beispiel.kern.verschoben Z. 7
- genutzt von:
  - anwendung/src/main/kotlin/beispiel/anwendung/Start.kt (Gewicht 1): beispiel.kern.Strich Z. 4

### kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt` · 9 Zeilen · kotlin · Quellsatz commonMain · Fan-in 1, Fan-out 1 · wichtig: fan-in, befund · Deutung fehlt
- deklariert:
  - ohne KDoc: val ENDE_GRENZE (Z. 3), class Ende (Z. 5)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt (Gewicht 2): beispiel.kern.zyklus.AnfangsArt Z. 6, beispiel.kern.zyklus.Anfang Z. 8
- genutzt von:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt (Gewicht 2): beispiel.kern.zyklus.ENDE_GRENZE Z. 4, beispiel.kern.zyklus.Ende Z. 6

### kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt

`datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt` · 7 Zeilen · kotlin · Quellsatz commonMain · Fan-in 1, Fan-out 1 · wichtig: fan-in, befund, trennstelle · Deutung fehlt
- deklariert:
  - ohne KDoc: class Mitte (Z. 3)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt (Gewicht 2): beispiel.kern.zyklus.ENDE_GRENZE Z. 4, beispiel.kern.zyklus.Ende Z. 6
- genutzt von:
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt (Gewicht 1): beispiel.kern.zyklus.Mitte Z. 6

### Weitere Dateien

- kern/build.gradle.kts (7 Z., Fan-in 0, Fan-out 0)
