# Arbeitsblatt · Paket beispiel.kern.labor.messung

`paket::kern-labor/beispiel.kern.labor.messung` · 3 Dateien · 31 Zeilen · Fan-in 1, Fan-out 3 · Deutung fehlt

## Kanten nach außen

- Nutzt:
  - beispiel.kern.labor.protokoll (nutzt produktiv, Gewicht 3, 2 Datei-Kanten)
  - beispiel.kern (nutzt produktiv, Gewicht 3, 2 Datei-Kanten)
  - beispiel.kern (nutzt test, Gewicht 1, 1 Datei-Kante)
  - beispiel.kern.zyklus (nutzt produktiv, Gewicht 1, 1 Datei-Kante)
- Genutzt von:
  - beispiel.kern.labor.protokoll (nutzt produktiv, Gewicht 1, 1 Datei-Kante)

## Dateien

Nach Fan-in sortiert, Tests zuletzt. Voll, solange das Blatt kurz bleibt, danach als eine Zeile.

### kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt

`datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt` · 11 Zeilen · kotlin · Quellsatz commonMain · Fan-in 2, Fan-out 2 · wichtig: fan-in, befund, einstieg, trennstelle · Deutung fehlt
- deklariert:
  - ohne KDoc: class Messung (Z. 7)
- nutzt:
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Eintrag.kt (Gewicht 2): beispiel.kern.labor.protokoll.Eintrag Z. 3, beispiel.kern.labor.protokoll.EintragsArt Z. 4
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Journal.kt (Gewicht 1): beispiel.kern.labor.protokoll.Journal Z. 5
- genutzt von:
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt (Gewicht 1): beispiel.kern.labor.messung.Messung Z. 12
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Eintrag.kt (Gewicht 1): beispiel.kern.labor.messung.Messung Z. 3

### kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt

`datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt` · 12 Zeilen · kotlin · Quellsatz commonMain · Fan-in 0, Fan-out 4 · Deutung fehlt
- deklariert:
  - ohne KDoc: fun auswerten (Z. 8), fun beginne (Z. 10), fun letzteMessung (Z. 12)
- nutzt:
  - kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt (Gewicht 2): beispiel.kern.Hilfen.kennung Z. 3, beispiel.kern.abstand Z. 5
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt (Gewicht 1): beispiel.kern.labor.messung.Messung Z. 12
  - kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt (Gewicht 1): beispiel.kern.Punkt Z. 4
  - kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt (Gewicht 1): beispiel.kern.zyklus.Anfang Z. 6
- genutzt von:
  - kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt (Gewicht 1, test, unsicher): beispiel.kern.labor.messung.auswerten Z. 7

### kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt

`datei:kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt` · 8 Zeilen · kotlin · Quellsatz commonTest · Test · Fan-in 0, Fan-out 0 · Deutung fehlt
- deklariert:
  - ohne KDoc: class AuswertungTest (Z. 5)
- nutzt:
  - kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Auswertung.kt (Gewicht 1, test, unsicher): beispiel.kern.labor.messung.auswerten Z. 7
  - kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt (Gewicht 1, test): beispiel.kern.Punkt Z. 7
