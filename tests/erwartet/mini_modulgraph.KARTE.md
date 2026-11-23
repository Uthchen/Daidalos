# Karte · Modulgraph

Ohne Git-Commit. Die interaktive Karte liegt in [karte.html](karte.html) und läuft offline im Browser. Diese Datei fasst sie für GitHub und Git-Diff zusammen.

Erzeugt von Daidalos 0.1.0 aus `daidalos.json` und `deutung.json`. Gemessenes und Gedeutetes sind getrennt: Beschreibungen und Einschätzungen stammen aus der Deutung.

## Überblick

| Größe | Wert |
| --- | ---: |
| Module | 5 |
| Ordner außerhalb der Module | 2 |
| Pakete | 9 |
| Dateien (davon fremd) | 27 (1) |
| Zeilen | 202 |
| `nutzt`-Kanten zwischen Dateien | 21 |
| Zyklen | 3 |

## Module

Fan-in und Fan-out zählen verschiedene Module (und Ordner), die über produktive `nutzt`-Kanten verbunden sind; Instabilität = Fan-out / (Fan-in + Fan-out).

| Modul | Dateien | Zeilen | Fan-in | Fan-out | Instabilität | Beschreibung |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) | 3 | 30 | 0 | 2 | 1,00 | Startet das Beispiel und setzt die Teile zusammen. *(veraltet)* |
| [:kern](karte.html#knoten=modul%3A%3Akern) | 7 | 52 | 2 | 0 | 0,00 | Fachlicher Kern: Punkte, Striche und Werkzeuge ohne Plattformbezug. |
| [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor) | 6 | 61 | 0 | 1 | 1,00 |  |
| [:nativ](karte.html#knoten=modul%3A%3Anativ) | 3 | 21 | 1 | 0 | 0,00 |  |
| [:regeln](karte.html#knoten=modul%3A%3Aregeln) | 2 | 6 | 0 | 0 | – |  |

### Ordner außerhalb der Module

| Ordner | Dateien | Zeilen | Fan-in | Fan-out | Instabilität | Beschreibung |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [(Wurzel)](karte.html#knoten=ordner%3A.) | 4 | 21 | 0 | 0 | – |  |
| [werkzeug/](karte.html#knoten=ordner%3Awerkzeug) | 1 | 3 | 0 | 0 | – |  |

## Gradle-Abhängigkeiten

- [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) → [:kern](karte.html#knoten=modul%3A%3Akern) · `gradle-impl` (1 Beleg)
- [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) → [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor) · `gradle-impl` (1 Beleg)
- [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) → [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor) · `gradle-test` (1 Beleg)
- [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) → [:nativ](karte.html#knoten=modul%3A%3Anativ) · `gradle-impl` (1 Beleg)
- [:anwendung](karte.html#knoten=modul%3A%3Aanwendung) → [:regeln](karte.html#knoten=modul%3A%3Aregeln) · `gradle-plugin` (1 Beleg)
- [:kern](karte.html#knoten=modul%3A%3Akern) → [:regeln](karte.html#knoten=modul%3A%3Aregeln) · `gradle-plugin` (1 Beleg)
- [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor) → [:kern](karte.html#knoten=modul%3A%3Akern) · `gradle-api` (1 Beleg)
- [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor) → [:regeln](karte.html#knoten=modul%3A%3Aregeln) · `gradle-plugin` (1 Beleg)
- [:nativ](karte.html#knoten=modul%3A%3Anativ) → [:kern](karte.html#knoten=modul%3A%3Akern) · `gradle-impl` (1 Beleg)
- [:nativ](karte.html#knoten=modul%3A%3Anativ) → [:regeln](karte.html#knoten=modul%3A%3Aregeln) · `gradle-plugin` (1 Beleg)

## Bereiche

Aus der Deutung.

### Zeichnen

Alles rund um Striche. Enthält zum Test \</script\>\<b\>fett\</b\> im Text.

Knoten: [:kern](karte.html#knoten=modul%3A%3Akern), [:kern-labor](karte.html#knoten=modul%3A%3Akern-labor)

## Befunde

### Einschätzungen

Aus der Deutung, nach Priorität.

1. **Ring im Kern auflösen** ([Zyklus aus 3 Dateien](karte.html#befund=befund%3Azyklus%3Adatei%3Aproduktiv%3Af45327fbce97))
   Anfang, Mitte und Ende kennen sich gegenseitig.
   Vorschlag: Die schwächste Verbindung Anfang → Mitte entfernen.

- <sub>nachrangig</sub> **Fehlende Brücke der Insel** ([JNI ohne Gegenstück: beispiel.nativ.Insel.fehlt](karte.html#befund=befund%3Ajni-ohne-gegenstueck%3Anativ%2Fsrc%2Fmain%2Fkotlin%2Fbeispiel%2Fnativ%2FInsel.kt%3Abeispiel.nativ.Insel.fehlt))
   Die Funktion wird im Beispiel nie aufgerufen.

### Zyklen

#### Paketebene

- **[Zyklus aus 2 Paketen](karte.html#befund=befund%3Azyklus%3Apaket%3Aproduktiv%3A99e6584ba329)**
  - Mitglieder: [beispiel.kern.labor.messung](karte.html#knoten=paket%3A%3Akern-labor%2Fbeispiel.kern.labor.messung), [beispiel.kern.labor.protokoll](karte.html#knoten=paket%3A%3Akern-labor%2Fbeispiel.kern.labor.protokoll)
  - Einstiege: keine
  - Günstigste Trennstelle: [beispiel.kern.labor.protokoll](karte.html#knoten=paket%3A%3Akern-labor%2Fbeispiel.kern.labor.protokoll) → [beispiel.kern.labor.messung](karte.html#knoten=paket%3A%3Akern-labor%2Fbeispiel.kern.labor.messung) (Gewicht 1)

#### Dateiebene

- **[Zyklus aus 3 Dateien](karte.html#befund=befund%3Azyklus%3Adatei%3Aproduktiv%3Af45327fbce97)**
  - Mitglieder: [Anfang.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FAnfang.kt), [Ende.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FEnde.kt), [Mitte.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FMitte.kt)
  - Einstiege: [Anfang.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FAnfang.kt) (von [Auswertung.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fmessung%2FAuswertung.kt))
  - Günstigste Trennstelle: [Anfang.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FAnfang.kt) → [Mitte.kt](karte.html#knoten=datei%3Akern%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Fzyklus%2FMitte.kt) (Gewicht 1)

- **[Zyklus aus 2 Dateien](karte.html#befund=befund%3Azyklus%3Adatei%3Aproduktiv%3Ac55399e18586)**
  - Mitglieder: [Messung.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fmessung%2FMessung.kt), [Eintrag.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fprotokoll%2FEintrag.kt)
  - Einstiege: [Messung.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fmessung%2FMessung.kt) (von [Auswertung.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fmessung%2FAuswertung.kt))
  - Günstigste Trennstelle: [Eintrag.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fprotokoll%2FEintrag.kt) → [Messung.kt](karte.html#knoten=datei%3Akern-labor%2Fsrc%2FcommonMain%2Fkotlin%2Fbeispiel%2Fkern%2Flabor%2Fmessung%2FMessung.kt) (Gewicht 1)

### Weitere Befunde

- JNI-Funktionen ohne Gegenstück: 1
- Dateien mit unaufgelösten internen Importen: 1
