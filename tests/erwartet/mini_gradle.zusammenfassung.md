# Zusammenfassung · mini_gradle

ohne Git-Commit. Daidalos 0.1.0. Nur Gemessenes; Spalte „Deutung“: Stand der Beschreibung in deutung.json (ok, fehlt, veraltet, fremd).

Zahlen: 13 Dateien (fremd 1), 56 Zeilen, 2 Module, 3 Ordner, 2 Pakete, 3 nutzt-Kanten zwischen Dateien, 0 Befunde, 2 wichtige Dateien.

## Module und Ordner

| Id | Dateien | Zeilen | Fan-in | Fan-out | Gradle nach | Deutung |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `modul::app` | 3 | 22 | 0 | 1 | core (impl) | fehlt |
| `modul::core` | 3 | 17 | 1 | 0 | – | fehlt |
| `ordner:.` | 4 | 11 | 0 | 0 | – | fehlt |
| `ordner:daten` | 1 | 0 | 0 | 0 | – | fehlt |
| `ordner:gradle` | 1 | 4 | 0 | 0 | – | fehlt |

## Pakete

### modul::app

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `de.beispiel.app` | 2 | 15 | 0 | 1 | fehlt |

### modul::core

| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |
| --- | ---: | ---: | ---: | ---: | --- |
| `de.beispiel.zeichnen` | 2 | 14 | 1 | 0 | fehlt |

## Wichtige Dateien

Auswahlregel: produktiv, nicht fremd und mindestens eines: unter den 30 mit dem höchsten Fan-in (fan-in), Mitglied eines Befunds (befund), Einstieg (einstieg) oder Trennstelle (trennstelle) eines Zyklus, Ende einer JNI-Kante (jni) oder einer modulübergreifenden Kante mit Gewicht ≥ 3 (modulkante).

| Id | Zeilen | Fan-in | Fan-out | Grund | Deutung |
| --- | ---: | ---: | ---: | --- | --- |
| `datei:core/src/main/kotlin/de/beispiel/zeichnen/Punkt.kt` | 3 | 2 | 0 | fan-in | fehlt |
| `datei:core/src/main/kotlin/de/beispiel/zeichnen/Strich.kt` | 11 | 1 | 1 | fan-in | fehlt |

## Befunde

Keine.

## Offen

- Beschreibung fehlt: alle 9 (Module, Ordner, Pakete und wichtige Dateien; siehe Spalte Deutung)
