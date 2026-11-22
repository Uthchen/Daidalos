# Karte · mini\_gradle

Ohne Git-Commit. Die interaktive Karte liegt in [karte.html](karte.html) und läuft offline im Browser. Diese Datei fasst sie für GitHub und Git-Diff zusammen.

Erzeugt von Daidalos 0.1.0 aus `daidalos.json`. Gemessenes und Gedeutetes sind getrennt: Beschreibungen und Einschätzungen stammen aus der Deutung.

## Überblick

| Größe | Wert |
| --- | ---: |
| Module | 2 |
| Ordner außerhalb der Module | 2 |
| Pakete | 2 |
| Dateien (davon fremd) | 12 (1) |
| Zeilen | 52 |
| `nutzt`-Kanten zwischen Dateien | 3 |
| Zyklen | 0 |

## Module

Fan-in und Fan-out zählen verschiedene Module (und Ordner), die über produktive `nutzt`-Kanten verbunden sind; Instabilität = Fan-out / (Fan-in + Fan-out).

| Modul | Dateien | Zeilen | Fan-in | Fan-out | Instabilität | Beschreibung |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [:app](karte.html#knoten=modul%3A%3Aapp) | 3 | 22 | 0 | 1 | 1,00 |  |
| [:core](karte.html#knoten=modul%3A%3Acore) | 3 | 17 | 1 | 0 | 0,00 |  |

### Ordner außerhalb der Module

| Ordner | Dateien | Zeilen | Fan-in | Fan-out | Instabilität | Beschreibung |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [(Wurzel)](karte.html#knoten=ordner%3A.) | 4 | 11 | 0 | 0 | – |  |
| [daten/](karte.html#knoten=ordner%3Adaten) | 1 | 0 | 0 | 0 | – |  |

## Gradle-Abhängigkeiten

- [:app](karte.html#knoten=modul%3A%3Aapp) → [:core](karte.html#knoten=modul%3A%3Acore) · `gradle-impl` (1 Beleg)

## Befunde

### Zyklen

Keine Zyklen.

### Weitere Befunde

Keine.
