# Zusammenfassung · Modulgraph

ohne Git-Commit. Daidalos 0.1.0. Nur Gemessenes; Spalte „Deutung“: Stand der Beschreibung in deutung.json (ok, fehlt, veraltet, fremd).

Zahlen: 27 Dateien (fremd 1), 202 Zeilen, 5 Module, 2 Ordner, 9 Pakete, 21 nutzt-Kanten zwischen Dateien, 5 Befunde, 12 wichtige Dateien.

## Module und Ordner

| Id | Dateien | Zeilen | Fan-in | Fan-out | Gradle nach | Deutung |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `modul::anwendung` | 3 | 30 | 0 | 2 | kern (impl), kern-labor (impl), kern-labor (test), nativ (impl), regeln (plugin) | veraltet |
| `modul::kern` | 7 | 52 | 2 | 0 | regeln (plugin) | ok |
| `modul::kern-labor` | 6 | 61 | 0 | 1 | kern (api), regeln (plugin) | fehlt |
| `modul::nativ` | 3 | 21 | 1 | 0 | kern (impl), regeln (plugin) | fehlt |
| `modul::regeln` | 2 | 6 | 0 | 0 | – | fehlt |
| `ordner:.` | 4 | 21 | 0 | 0 | – | fehlt |
| `ordner:werkzeug` | 1 | 3 | 0 | 0 | – | fehlt |

## Pakete

### modul::anwendung

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `beispiel.anwendung` | 2 | 18 | 1 | 3 | fehlt |
| `beispiel.anwendung.fremd` | 0 | 0 | 1 | 1 | fremd |

### modul::kern

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `beispiel.kern` | 3 | 22 | 2 | 0 | fehlt |
| `beispiel.kern.zyklus` | 3 | 23 | 1 | 0 | ok |

### modul::kern-labor

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `beispiel.kern.labor.messung` | 3 | 31 | 1 | 3 | fehlt |
| `beispiel.kern.labor.protokoll` | 2 | 14 | 1 | 1 | fehlt |

### modul::nativ

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `beispiel.nativ` | 1 | 7 | 1 | 0 | fehlt |

### modul::regeln

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `beispiel.regeln` | 1 | 3 | 0 | 0 | fehlt |

### ordner:werkzeug

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `werkzeug` | 1 | 3 | 0 | 0 | fehlt |

## Wichtige Dateien

Auswahlregel: produktiv, nicht fremd und mindestens eines: unter den 30 mit dem höchsten Fan-in (fan-in), Mitglied eines Befunds (befund), Einstieg (einstieg) oder Trennstelle (trennstelle) eines Zyklus, Ende einer JNI-Kante (jni) oder einer modulübergreifenden Kante mit Gewicht ≥ 3 (modulkante).

| Id | Zeilen | Fan-in | Fan-out | Grund | Deutung |
| --- | ---: | ---: | ---: | --- | --- |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt` | 3 | 3 | 0 | fan-in | fehlt |
| `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt` | 11 | 2 | 2 | fan-in, befund, einstieg, trennstelle | fehlt |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt` | 11 | 2 | 1 | fan-in | fehlt |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt` | 7 | 2 | 1 | fan-in, befund, einstieg, trennstelle | ok |
| `datei:anwendung/src/main/kotlin/beispiel/anwendung/Start.kt` | 11 | 1 | 3 | fan-in | fehlt |
| `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Eintrag.kt` | 9 | 1 | 1 | fan-in, befund, trennstelle | fehlt |
| `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Journal.kt` | 5 | 1 | 0 | fan-in | fehlt |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt` | 8 | 1 | 2 | fan-in | fehlt |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt` | 9 | 1 | 1 | fan-in, befund | fehlt |
| `datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt` | 7 | 1 | 1 | fan-in, befund, trennstelle | fehlt |
| `datei:nativ/src/main/kotlin/beispiel/nativ/Insel.kt` | 7 | 1 | 0 | fan-in, befund, jni | fehlt |
| `datei:nativ/src/main/cpp/insel_jni.c` | 7 | 0 | 0 | jni | fehlt |

## Befunde

- `befund:jni-ohne-gegenstueck:nativ/src/main/kotlin/beispiel/nativ/Insel.kt:beispiel.nativ.Insel.fehlt`: JNI ohne Gegenstück (kotlin): beispiel.nativ.Insel.fehlt
- `befund:unaufgeloest:kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt`: 1 unaufgelöste interne Importe · ohne Einschätzung
- `befund:zyklus:datei:produktiv:c55399e18586`: Zyklus, Ebene datei, produktiv, 2 Knoten, Trennstelle `kante:nutzt:datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Eintrag.kt->datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt:produktiv` (Gewicht 1) · ohne Einschätzung
- `befund:zyklus:datei:produktiv:f45327fbce97`: Zyklus, Ebene datei, produktiv, 3 Knoten, Trennstelle `kante:nutzt:datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt->datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt:produktiv` (Gewicht 1)
- `befund:zyklus:paket:produktiv:99e6584ba329`: Zyklus, Ebene paket, produktiv, 2 Knoten, Trennstelle `kante:nutzt:paket::kern-labor/beispiel.kern.labor.protokoll->paket::kern-labor/beispiel.kern.labor.messung:produktiv` (Gewicht 1) · ohne Einschätzung

## Messung

Funktionen: 27 produktiv, 2 Test; ruft-Kanten: 14 sicher, 1 unsicher.
Unaufgelöste Aufrufe: keine.

## Offen

- Beschreibung fehlt: 23
  - `datei:anwendung/src/main/kotlin/beispiel/anwendung/Start.kt`
  - `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/messung/Messung.kt`
  - `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Eintrag.kt`
  - `datei:kern-labor/src/commonMain/kotlin/beispiel/kern/labor/protokoll/Journal.kt`
  - `datei:kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt`
  - `datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt`
  - `datei:kern/src/commonMain/kotlin/beispiel/kern/Werkzeug.kt`
  - `datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Ende.kt`
  - `datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt`
  - `datei:nativ/src/main/cpp/insel_jni.c`
  - `datei:nativ/src/main/kotlin/beispiel/nativ/Insel.kt`
  - `modul::kern-labor`
  - `modul::nativ`
  - `modul::regeln`
  - `ordner:.`
  - `ordner:werkzeug`
  - `paket::anwendung/beispiel.anwendung`
  - `paket::kern-labor/beispiel.kern.labor.messung`
  - `paket::kern-labor/beispiel.kern.labor.protokoll`
  - `paket::kern/beispiel.kern`
  - `paket::nativ/beispiel.nativ`
  - `paket::regeln/beispiel.regeln`
  - `paket:ordner:werkzeug/werkzeug`
- Beschreibung veraltet (Hash weicht ab): 1
  - `modul::anwendung`
- Befunde ohne Einschätzung: 3
  - `befund:unaufgeloest:kern-labor/src/commonTest/kotlin/beispiel/kern/labor/messung/AuswertungTest.kt`
  - `befund:zyklus:datei:produktiv:c55399e18586`
  - `befund:zyklus:paket:produktiv:99e6584ba329`
- Tote Verweise in deutung.json: 4
  - `bereiche bereich:zeichnen: paket::verschwunden/x`
  - `beschreibungen: modul::gibt-es-nicht`
  - `einschaetzungen: befund:zyklus:datei:produktiv:000000000000`
  - `kanten: kante:nutzt:datei:a.kt->datei:b.kt:produktiv`
