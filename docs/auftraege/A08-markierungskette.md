# Auftrag A08 – Markierungs-Kette und detekt-SARIF

**Etappe:** 4 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A07b (`f029464`). Branch `auftrag/a08-markierungskette` von `main`.

## Ziel

Das ist der eigentliche Mehrwert von Daidalos für Sketchorus, Fund U6 der BS2-Prüfung. detekt prüft markierte Funktionen nur **in ihrem eigenen Körper**. Daidalos folgt den Aufrufen und meldet jede unmarkierte interne Funktion, die von markiertem Code aus erreicht wird. Gemeldet wird die ganze Kette.

Dazu liest Daidalos die SARIF-Dateien von detekt ein. So stehen beide Prüfungen in einer Karte, und die Befunde beider Prüfungen hängen an denselben Funktions-Ids.

## Entscheidungen der Leitung zu A07b

1. **Größe:** In diesem Auftrag fallen `id` der `ruft`-Kanten und `datei` der Funktionsknoten weg (beides lässt sich ableiten, siehe Schritt 6). Das Id-Schema und die Einrückung bleiben. Etwa 11 MB sind in Ordnung, weil die Datei im Klon unter `lokal/` liegt und nicht committet wird. Was die Karte einbettet, entscheidet A09.
2. **Unsichere Lesekanten:** Sie bleiben in der Messung, weil Leitplanke 3 gilt. Die Kette behandelt alle unsicheren Kanten gesondert (Schritt 3).
3. Das unsichere Objekt im selben Paket nebenbei untersuchen. Ist die Ursache klein, beheben. Sonst im Bericht beschreiben.

## Schritte

### 1. Konfiguration in `daidalos.toml`

```toml
[markierungen]
# volle Namen; eine Funktion ist markiert, wenn sie selbst, eine umgebende Klasse
# (jede Ebene) oder ihre Datei (@file:) eine dieser Annotationen trägt
annotationen = ["de.beispiel.Strichpfad", "de.beispiel.Deterministisch"]
# volle Namen; so markierte Funktionen sind bewusste Ausnahmen: kein Befund, die Kette endet dort
ausnahmen = ["de.beispiel.WeckenOhneDaten"]
# Pfade (gitwildmatch), die nicht als Quelle oder Ziel einer Kette zählen
ausgenommen = ["werkzeuge/gegenfaelle/"]

[detekt]
# gitwildmatch, relativ zum Zielrepo; gelesen auch wenn [scan].ausschliessen sie ausschließt
sarif = ["**/build/reports/detekt/*.sarif"]
```

Fehlt `[markierungen]`, gibt es keine Kette. Unbekannte Namen in `annotationen` (im Code nirgends verwendet) ergeben eine Warnung.

### 2. Was als markiert gilt

- Eine Funktion ist **markiert**, wenn eine der folgenden Stellen eine Annotation aus `annotationen` trägt:
  - die Funktion selbst;
  - eine umgebende Klasse, ein Objekt oder ein Companion auf beliebiger Ebene;
  - ihre Datei über `@file:`.

  Gezählt werden nur sichere Annotationen, also mit aufgelöstem vollem Namen.
- **Ausnahme aus der Architektur:** Die Markierung einer Klasse deckt **nicht** ihren `<init>`. `init`-Blöcke und Eigenschafts-Initialisierer stehen im Konstruktor. Accessoren `<get-x>`/`<set-x>` deckt sie dagegen.
- Ist eine Funktion mit einer Annotation aus `ausnahmen` versehen, gilt sie als **Ausnahme**. Die Funktion selbst und ihre Klasse zählen dafür, ihre Datei nicht.
- Es zählen nur produktive Funktionen außerhalb von `ausgenommen` und außerhalb von Fremdcode.
- Jeder Funktionsknoten bekommt `markiert: true` und `ausnahme: true`, falls zutreffend. Das gilt nur dann, wenn es zutrifft (Standard `false`).

### 3. Die Kette

- **Start:** jede markierte Funktion.
- **Folgen:** Es geht entlang von `ruft`, einschließlich `lesen` und `schreiben`. Endet eine Kante an einer abstrakten oder offenen Funktion, die überschrieben wird (es gibt eingehende `ueberschreibt`-Kanten), gelten auch alle Funktionen, die sie überschreiben, als erreicht. Das wird rekursiv fortgesetzt und im Beleg als Schritt `ueberschrieben-von` vermerkt. `actual` wird ebenso von `expect` zu `actual` gefolgt.
- **Verstoß:** Eine erreichte Funktion, die weder markiert noch Ausnahme ist. Von einer unmarkierten Funktion aus wird **weiter gefolgt**, denn ihre Aufrufe gehören zur Kette. An markierten Funktionen und Ausnahmen endet die Kette, weil sie selbst Start oder bewusst erlaubt sind.
- **Grenzkante:** eine Kante von einer markierten zu einer unmarkierten Funktion (keine Ausnahme). Jede Grenzkante ist ein **Befund** `markierung-verlassen`, mit folgendem Beleg:

  | Feld im Beleg | Bedeutung |
  | --- | --- |
  | `von` | die markierte Funktion |
  | `nach` | die erste unmarkierte Funktion |
  | `markierung` | der volle Annotationsname, der `von` markiert, und `traeger` = Funktion, Klasse oder Datei |
  | `zeilen` | Aufrufstellen in `von` |
  | `kette` | alle von `nach` aus erreichten unmarkierten Funktionen, sortiert, mit `tiefe` (kürzester Abstand ab `nach`) |
  | `anzahl` | Länge von `kette` plus 1 |
  | `ausnahmen` | Ausnahmen, an denen die Kette endete, sortiert |
  | `ueber_ueberschreiben` | ob ein Schritt über `ueberschreibt` lief |

- `knoten` des Befunds enthält `von`, `nach` und die **Dateien** der Kette. Über die Dateien erscheint der Befund schon jetzt auf der Dateiebene der Karte.
- `schwere`: `warnung`.
- **Sicher und unsicher:** Die Kette läuft zuerst nur über **sichere** Kanten. Was zusätzlich nur über unsichere Kanten erreichbar ist, kommt in denselben Befund unter `kette_unsicher`. Gibt es eine Grenzkante nur unsicher, wird sie ein eigener Befund mit `"unsicher": true` und `schwere: hinweis`.
- **Gruppierung:** Ein Befund je Paar aus markierter Funktion und unmarkierter Funktion. Zwei Befunde mit gleichem `nach` aus verschiedenen markierten Funktionen bleiben getrennt, teilen sich aber die `kette`. Werden es an Sketchorus mehr als 40 sichere Befunde, ist das zu berichten und eine Gruppierung je `nach` vorzuschlagen. Nicht ohne Rückfrage umsetzen.
- **Delegierte Eigenschaften und Lambdas:** Liest markierter Code eine delegierte Eigenschaft (`by lazy`), ist das kein Verstoß, aber ein Vermerk. Jeder Befund und jede markierte Funktion ohne Befund bekommt in `metriken.delegiert_gelesen` die Zahl der gelesenen delegierten Eigenschaften. Lambdas, die als Argument übergeben werden, gehören wie bisher zum Aufrufer. Das kommt als Grenze in den Bericht.
- **Externe Aufrufe** werden nicht verfolgt. Das prüft detekt (`KeinePlattformFunktionImRechenweg` u. a.).

Die Befund-Id muss stabil sein und lautet `befund:markierung:<von-id>-><nach-id>`. Damit überleben Einschätzungen im Skill einen neuen Scan.

### 4. detekt-SARIF lesen

- `scan` liest alle Dateien aus `[detekt].sarif`, auch wenn sie unter einem ausgeschlossenen Pfad liegen. Gelesen wird SARIF 2.1.0: `runs[].results[]` mit `ruleId`, `level`, `message.text`, `locations[0].physicalLocation.artifactLocation.uri` und `region.startLine`.
- `uri` ist relativ zum Zielrepo zu machen (detekt schreibt absolute `file:`-URIs). Ergebnisse außerhalb des Zielrepos werden mit Warnung verworfen.
- Jedes Ergebnis wird ein Befund `detekt` mit folgenden Angaben:
  - `quelle: "detekt"`, `regel` = `ruleId`;
  - `schwere` aus `level`: `error` → `fehler`, `warning` → `warnung`, sonst `hinweis`;
  - `knoten`: die Funktion, deren Zeilenbereich die Zeile enthält (innerste), sonst die Datei;
  - `beleg` mit `{zeile, meldung, sarif}`, wobei `sarif` der relative Pfad der SARIF-Datei ist.
- Doppelte Treffer (gleiche Datei, Zeile und Regel aus mehreren Quellsätzen bzw. SARIF-Dateien) werden zusammengeführt. `sarif` wird dann eine sortierte Liste.
- Id: `befund:detekt:<regel>:<pfad>:<zeile>`.
- Leere SARIF-Dateien sind gültig. In `ziel` kommt zusätzlich `detekt: {"dateien": n, "ergebnisse": m}`. Keine Zeitstempel und keine Dateialter (Determinismus).
- Ist eine Datei kein gültiges SARIF, gibt es eine Warnung und die Datei wird übersprungen.

### 5. SARIF passend zum Stand des Klons

SARIF liegt nur nach einem Build vor, und `build/` ist nicht in Git. Damit die SARIF-Befunde zum Commit des Klons passen, baut das Werkzeug sie **im Klon**:

- `lokal/ziele.toml` bekommt je Ziel optional zwei Einträge:
  - `kopiere = ["local.properties"]`: Dateien aus der Quelle, die der Build braucht und die nicht in Git sind. Sie werden nach dem Zurücksetzen in den Klon kopiert. Erlaubt sind nur Dateien, kein `..`.
  - `detekt = ["gradlew.bat", "detekt"]`: Befehl als Liste, im Klon ausgeführt. Unter Linux genügt `./gradlew`.
- `ziel_auffrischen.py --mit-detekt` führt den Befehl nach dem Zurücksetzen und vor dem Scan aus. Ohne die Option liest der Scan nur, was im Klon schon liegt. Nach `git clean` ist das nichts, dann sind es 0 SARIF-Dateien.
- Bricht der Befehl ab, gibt es Exit-Code 2 und die Ausgabe des Befehls wird gezeigt.
- Die Laufzeit des Befehls wird berichtet.
- Gradle darf beim ersten Lauf Abhängigkeiten laden. Das ist Gradle und nicht Daidalos, Leitplanke 4 gilt für Daidalos.
- Für Sketchorus ist der passende Detekt-Task aus dessen Build zu ermitteln, etwa ein Sammeltask über alle Module. Er gehört nur in `lokal/ziele.toml`.

### 6. Kleinere `daidalos.json` (Entscheidung 1)

- `ruft`-Kanten verlieren `id`. In `datenformat.md` steht die Ableitung `kante:ruft:<von>-><nach>:<rolle>`. Alle Leser bauen die Id bei Bedarf selbst.
- Funktionsknoten verlieren `datei`, weil sie aus der Id hervorgeht (Teil vor `#` ohne `funktion:`). Bei C-Knoten ebenso.
- Die Größe vorher und nachher an Sketchorus ist zu berichten.

### 7. Ausgabe in Karte, `KARTE.md`, Zusammenfassung und Skill

Die Funktionsebene der Karte kommt erst in A09. Bis dahin gilt:

- **Karte:**
  - Befunde `markierung-verlassen` und `detekt` erscheinen in der Befundliste.
  - Titel: „`<von>` ruft unmarkiert `<nach>` (+N)“ bzw. „detekt: `<regel>`“.
  - Ein Klick hebt die Dateien hervor.
  - Die Seitenleiste zeigt die Kette als eingerückte Liste mit Datei:Zeile und Editor-Link je Funktion. Bei mehr als 30 Einträgen werden diese eingeklappt.
  - Ein eigener Filterschalter „Markierung“ blendet die Befunde der Kette ein und aus.
  - detekt-Befunde sind standardmäßig **ausgeblendet** (Schalter „detekt“), weil detekt seine eigene Ausgabe hat.
- **`KARTE.md`:** Abschnitt „Markierungs-Kette“ mit je einer Zeile pro Befund, Anzahl und den ersten drei Funktionen der Kette. detekt nur als Zahl je Regel.
- **Zusammenfassung:**
  - Befunde `markierung-verlassen` brauchen eine Einschätzung wie jeder Befund. Kurze, nachrangige sind erlaubt, siehe `SKILL.md`.
  - detekt-Befunde brauchen **keine** Einschätzung. Sie stehen unter „Messung“ als Zahl je Regel, weil sie schon eine Regel mit eigener Begründung haben.
- **`SKILL.md`:** Ergänze, wie eine Einschätzung einer Grenzkante aussieht. Sie nennt, warum `nach` wohl unmarkiert ist (Hilfsfunktion, vergessen, absichtlich), und schlägt vor, ob `nach` markiert, Ausnahme oder umgebaut werden sollte. Mit `daidalos aufrufe` wird belegt.
- **Neu: `daidalos markierung [--datei D] [--unsicher]`.** Der Befehl gibt alle Grenzkanten als Text aus, sortiert nach der Länge der Kette, absteigend. Das ist für Mensch und Skill.

## Tests

- **Erfundenes Beispiel:** neues `tests/beispiele/mini_markierung` oder `mini_aufrufe` erweitern. Es braucht zwei Annotationen und eine Ausnahme im Paket `de.beispiel`. Dazu eine **gleichnamige** Annotation in einem anderen Paket, die nicht zählen darf. Folgende Fälle sind abzudecken:
  - markierte Funktion ruft unmarkierte, die eine weitere ruft (Kette Länge 2);
  - Klasse markiert, ihre Methoden gedeckt;
  - `<init>` der markierten Klasse nicht gedeckt;
  - Getter einer markierten Klasse gedeckt;
  - `@file:`-Markierung;
  - Aufruf einer Schnittstellenmethode mit unmarkierter Umsetzung (über `ueberschrieben-von`);
  - Ausnahme beendet die Kette;
  - markiert ruft markiert, kein Befund;
  - nur unsichere Grenzkante, dann ein Befund mit `unsicher`;
  - Rekursion in der Kette, ohne Endlosschleife;
  - Testcode und `ausgenommen`-Pfad ohne Befund;
  - Lesen einer delegierten Eigenschaft (Vermerk).
- **SARIF:** zwei erfundene SARIF-Dateien im Beispiel mit absoluter `file:`-URI (im Test erzeugt, weil die URI absolut ist). Dazu gehören:
  - ein Treffer in einer Funktion;
  - ein Treffer außerhalb jeder Funktion;
  - ein doppelter Treffer aus zwei Dateien;
  - ein Treffer außerhalb des Repos (verworfen);
  - eine leere SARIF-Datei;
  - eine kaputte SARIF-Datei (Warnung).
- `ziel_auffrischen.py --mit-detekt` mit einem Python-Befehl als Ersatz für Gradle, der eine SARIF-Datei schreibt. Außerdem: Abbruch mit Exit-Code 2, `kopiere`, Ablehnung von `..`.
- Golden-Dateien, Determinismus, Plausibilität unverändert grün. Browser-Probe: Kette in der Seitenleiste, Schalter „Markierung“ und „detekt“.

## Probe an Sketchorus

- `lokal/ziele/sketchorus/daidalos.toml` bekommt die echten Annotationen und Ausnahmen mit vollem Namen. Die gleichnamigen Annotationen in den Gegenfällen dürfen **nicht** zählen. `ausgenommen` enthält deren Ordner.
- Ablauf: `ziel_auffrischen.py sketchorus --erzwingen --mit-detekt`.
- **Zu berichten:**
  - Zahl der markierten Funktionen und der Ausnahmen;
  - Grenzkanten sicher und unsicher;
  - Verteilung der Kettenlängen;
  - die längste Kette (nur Länge);
  - Laufzeit von detekt;
  - Zahl der SARIF-Dateien und Ergebnisse je Regel.
- **Abgleich von Hand:** Claude Code nimmt die 10 längsten sicheren Ketten und 5 zufällige (Startwert 9) und prüft jeweils:
  - Ist `nach` wirklich unmarkiert?
  - Ist die Kette echt?
  - Gibt es einen Grund, warum `nach` keine Markierung braucht (reine Hilfsfunktion, Konstante)?

  Das Ergebnis kommt nur nach `lokal/A08-abgleich.md`. Im Bericht stehen nur Zahlen und Muster, keine Sketchorus-Namen.
- **Skill einmal laufen lassen**, bis `deutung pruefen` 0 meldet. Zu berichten sind Zeit und Zahl der neuen Einschätzungen.
- Bildschirmfotos: `lokal/A08-kette.png` (Seitenleiste mit Kette) und `lokal/A08-befunde.png`.

## Abschluss

- Branch pushen, nicht mergen.
- Bericht `docs/auftraege/A08-bericht.md`.
- Antwort an mich mit höchstens 8 Zeilen.
- Keine Sketchorus-Inhalte im Repo.
