# Bericht A08 – Markierungs-Kette und detekt-SARIF

Stand 2026-11-23. Branch `auftrag/a08-markierungskette` von `main` (`f029464`), nicht nach `main`
gemergt.

## Was gemacht wurde

### 1. Konfiguration

`daidalos.toml` kennt `[markierungen]` (`annotationen`, `ausnahmen`, `ausgenommen`) und
`[detekt].sarif`. Ohne `[markierungen]` gibt es keine Kette. Ohne `[detekt].sarif` gibt es kein
`ziel.detekt`, deshalb bleiben die Golden-Dateien der alten Beispiele dort unverändert.
Konfigurierte Namen, die im Code nirgends sicher aufgelöst vorkommen, ergeben eine Warnung.

### 2. und 3. Markierung und Kette (`src/daidalos/analysen/markierung.py`)

- **markiert:** Annotation an der Funktion, an einer umgebenden Klasse (jede Ebene, auch Objekt und
  Companion) oder an der Datei. Ein `<init>` ist nur durch die eigene Annotation markiert.
  Accessoren deckt die Klasse. Es zählen nur sichere Annotationen, deshalb zählt die gleichnamige
  Annotation aus einem anderen Paket nicht.
- **Ausnahme:** an der Funktion oder einer umgebenden Klasse. Eine Ausnahme ist nie Start.
- Es zählen nur produktive Kotlin-Funktionen ohne Fremdcode und außerhalb von `ausgenommen`.
- **Folgen:** über `ruft` einschließlich `lesen`/`schreiben`. Jedes Aufrufziel wird um alle
  Funktionen erweitert, die es rekursiv überschreiben, und um die `actual` einer `expect`.
- **Befunde:** Grenzkanten und Kette mit allen Belegfeldern aus dem Auftrag, dazu `von_zeile`,
  `nach_zeile` und je Ketteneintrag `von` und `zeile` (siehe Abweichungen).
- **Sicher und unsicher:** Zuerst läuft alles über sichere Kanten. Was nur unsicher erreichbar ist,
  steht in `kette_unsicher`. Grenzkanten, die es nur unsicher gibt, werden eigene Befunde mit
  `beleg.unsicher` und `schwere: hinweis`.
- **Ids:** `befund:markierung:<von>-><nach>`.
- **Delegierte Eigenschaften:** Der Aufrufgraph löst Lesezugriffe auf delegierte Eigenschaften nur
  für diesen Vermerk auf und erzeugt keine Kante. `metriken.delegiert_gelesen` steht an jeder
  markierten Funktion, `beleg.delegiert_gelesen` an jedem Befund.

### 4. detekt-SARIF (`src/daidalos/adapter/detekt.py`)

- **Suche:** im ganzen Zielrepo, auch in Pfaden, die der Scan ausschließt, ohne `.git` und ohne
  Ordner mit eigenem `.git` (Worktrees).
- **`uri`:** absolute `file:`-URI, absoluter Pfad oder relativer Pfad. Ergebnisse außerhalb des
  Repos ergeben eine Warnung.
- **Verworfen:** Ergebnisse in nicht erfassten Dateien (mit einer Sammelwarnung) und in Fremdcode
  (ohne Warnung).
- **Knoten:** die innerste Funktion, deren Zeilen die Zeile enthalten, sonst die Datei.
- **Zusammenführen:** gleiche Regel, Datei und Zeile werden ein Befund. `sarif` wird dann eine
  Liste, die Schwere die strengste.
- **Ungültige Dateien:** Leere Dateien sind gültig, kaputte ergeben eine Warnung.

### 5. `ziel_auffrischen.py`

- `kopiere`: relative Pfade ohne `..`; die Dateien werden nach jedem Zurücksetzen kopiert.
- `detekt` plus `--mit-detekt`: Der Befehl läuft im Klon, die Laufzeit wird ausgegeben. Bricht er
  ab, endet das Werkzeug mit Exit-Code 2 und zeigt die Ausgabe des Befehls.
- `git clean` läuft jetzt mit `core.longPaths=true`. Unter Windows ließen sich sonst lange Pfade
  in den Build-Ausgaben nicht löschen.

### 6. Kleinere `daidalos.json`

`ruft` ohne `id`, Funktionsknoten ohne `datei`. `src/daidalos/ids.py` leitet beides ab. Umgestellt
sind alle Leser: `pfad`, `aufrufe`, `arbeitsblatt`, Deutung, Zusammenfassung, `KARTE.md` und die
Plausibilitätsprüfung.

### 7. Ausgabe

- **Karte:**
  - Titel „`von` ruft unmarkiert `nach` (+N)“ bzw. „detekt: `regel`“.
  - Ein Klick hebt die Dateien hervor.
  - Die Seitenleiste zeigt die Kette als eingerückten Baum (Vorgänger im kürzesten Weg) mit
    Datei:Zeile und Editor-Link, ab 31 Einträgen eingeklappt; dazu die unsichere Fortsetzung und
    die Ausnahmen.
  - Schalter „Markierung“ (an) und „detekt“ (aus).
- **`KARTE.md`:** Abschnitt „Markierungs-Kette“ (längste zuerst, erste drei Funktionen) und
  „detekt“ (Zahl je Regel).
- **Zusammenfassung:**
  - detekt-Befunde brauchen keine Einschätzung und stehen nicht in der Befundliste.
  - Unter „Messung“ stehen markierte Funktionen, Ausnahmen, Grenzkanten und detekt je Regel.
  - Bei `markierung-verlassen` werden nur die Dateien von `von` und `nach` wichtig.
- **`SKILL.md`:** wie eine Grenzkante eingeschätzt wird (warum unmarkiert; markieren, Ausnahme
  oder umbauen; Beleg mit `daidalos aufrufe`), dazu die Frage „Wo verlässt markierter Code die
  Markierung?“.
- **Neu:** `daidalos markierung [--datei D] [--unsicher]`.

### Nebenbei (Entscheidung 3)

**Ursache des unsicheren Objekts im selben Paket gefunden und behoben.** Die Kotlin-Grammatik liest
`!Objekt.f(x)` als `(!Objekt).f(x)`. Der Empfänger war damit ein `unary_expression` und galt als
unbekannt. Jetzt sind vorangestelltes `!`, `-` und `+` für den Empfänger durchsichtig. Ein neuer
Test in `test_aufrufe.py` deckt das ab.

Wirkung an Sketchorus, gleicher Klon-Stand:

- unsichere Aufrufstellen `unbekannter-empfaenger`: 728 → 673;
- sichere Lesestellen: 173 → 186;
- alle 4 Grenzkanten, die es nur unsicher gab, waren genau dieser Fall: jetzt 0.

### Tests

- **Neues Beispiel `tests/beispiele/mini_markierung`:** alle zwölf geforderten Fälle, dazu
  `kette_unsicher` und eine Ausnahme mitten in der Kette.
- **`tests/test_markierung.py`:** Kette, Schalter ohne `[markierungen]`, Warnung,
  `daidalos markierung`, `KARTE.md` und Zusammenfassung.
- **SARIF:** im Test erzeugt, mit absoluter URI: Treffer in einer Funktion, Treffer außerhalb
  jeder Funktion, doppelter Treffer aus zwei Dateien, Treffer außerhalb des Repos, leere und
  kaputte Datei. Determinismus und keine absoluten Pfade.
- **`ziel_auffrischen.py`:**
  - `--mit-detekt` mit einem Python-Skript statt Gradle;
  - Abbruch mit Exit-Code 2;
  - `kopiere`;
  - Ablehnung von `..`, absoluten Pfaden und fehlendem Befehl.
- **Browser-Probe:** Kette in der Seitenleiste (Einrückung, Hervorhebung), Schalter „Markierung“
  und „detekt“.
- **Golden-Dateien:** neu geschrieben, `mini_markierung` ist dazugekommen.
- **Ergebnis:** `ruff check`, `ruff format --check` und `pytest` grün: **318 bestanden,
  1 übersprungen** (Windows, mit Browser-Probe).

## Probe an Sketchorus

Klon `4a233c2`, ein Zwischenstand, den Sketchorus selbst als unvollständig führt. Lauf mit
`ziel_auffrischen.py sketchorus --erzwingen --mit-detekt`. Die Zahlen gelten nach der Korrektur aus
Entscheidung 3. Drei Scans sind byte-gleich.

| Messgröße | Wert |
| --- | ---: |
| markierte Funktionen | 242 |
| Ausnahmen | 6 |
| Funktionen ohne Körper | 62 |
| Grenzkanten sicher / nur unsicher | 23 / 0 (vor der Korrektur 23 / 4) |
| Kettenlänge 1 / 2 | 18 / 5 |
| längste Kette | 2 |
| verschiedene `von` / `nach` | 15 / 19 |
| Markierung über Klasse / Funktion / Datei | 13 / 10 / 0 |
| `kette_unsicher` vorhanden | 0 |
| über `ueberschreibt` | 0 |
| an Ausnahmen geendet | 0 |
| markierte Funktionen mit `delegiert_gelesen` > 0 | 0 |
| Laufzeit detekt | 53,9 s (Gradle ohne Daemon, mit Build-Cache) |
| SARIF-Dateien / Ergebnisse / Befunde | 30 / 4 / 2 |
| Befunde je Regel | `MaxLineLength` 2 (Warnung; je 2 Ergebnisse aus zwei Quellsatz-Aufgaben zusammengeführt) |
| `daidalos.json` vorher → nachher | 13 790 073 → 11 182 618 Bytes |
| davon ohne `ruft`-`id` / ohne `datei` | −2 300 003 / −339 502 Bytes |
| Scan-Zeit | 4,6 s vorher, 5,2–7,2 s nachher |

„Vorher“ ist der Code von `main` am selben Klon-Stand. Die Befunde der Kette brauchen etwa 28 KB.
Die längere und schwankende Scan-Zeit nachher kommt vor allem aus dem Lesen der delegierten
Zugriffe und dem Rechner, nicht genau gemessen.

**Gruppierung:** 23 sichere Befunde liegen unter der Schwelle von 40. Eine Gruppierung je `nach`
ist deshalb nicht vorgeschlagen.

**Abgleich von Hand:** die 10 längsten sicheren und 5 zufällige (Startwert 9), Tabelle in
`lokal/A08-abgleich.md`.

- `nach` ist in **15 von 15** Fällen wirklich unmarkiert, die Kette ist **15 von 15** echt.
- Muster:
  - unmarkierte reine Rechen-Objekte, die deterministischer Code nutzt: 7;
  - eine unmarkierte Hilfsklasse des Strichpfads: 3;
  - Getter von Konstanten oder Messschaltern in Klassen, die nur einzelne Funktionen markieren: 3;
  - Funktionen des Messmodus: 2.
- In fast allen Fällen braucht `nach` eine Markierung, keine Ausnahme. Nur bei den Gettern genügt
  ebenso eine Konstante.

**Skill-Lauf:** bis `deutung pruefen` 0 meldet.

- Neu: 23 Einschätzungen (2 mit Priorität für die zwei Hauptmuster, 21 nachrangig mit Verweis auf
  das Muster).
- 13 neue und 17 erneuerte Beschreibungen. Die erneuerten Texte wurden gegen die Diffs geprüft;
  einer wurde präzisiert.
- Zeit: etwa 1 Minute für Entwurf, Übernahme und Prüfung. Das Lesen des Codes, etwa 15 Minuten,
  lag zum größten Teil schon im Abgleich.

Bildschirmfotos: `lokal/A08-kette.png` und `lokal/A08-befunde.png`.

## Abweichungen vom Auftrag

- **Funktionen ohne Code sind nie ein Verstoß.** Das sind abstrakte Funktionen,
  Schnittstellenmethoden ohne Körper, `expect`, `external` und implizite Konstruktoren. Sonst wäre
  bei einem Aufruf über eine Schnittstelle die körperlose Methode die Grenze und nicht ihre
  Umsetzung. Dafür gibt es das neue Feld `ohne_koerper` an Funktionsknoten.
- **Erweitert wird auch hinter markierten Zielen.** Ruft markierter Code eine markierte offene
  Methode, deren Überschreibung unmarkiert ist, wird die Überschreibung gemeldet. Der Aufruf kann
  dort landen.
- **Mehr Felder im Beleg.** `von_zeile`, `nach_zeile` und je Ketteneintrag `von` (Aufrufer) und
  `zeile`. Ohne sie kann die Karte keinen Baum mit Datei:Zeile zeigen, weil die Funktionsknoten
  bis A09 nicht eingebettet sind.
- **Ort von `unsicher`.** Es steht im Beleg (`beleg.unsicher`), wie beim Zyklus.
- **Ort von `delegiert_gelesen`.** Es steht als Metrik an jeder markierten Funktion (mit und ohne
  Befund) und im Beleg jedes Befunds.
- **Was nicht verfolgt wird.** `jni`-Kanten nicht (C kennt keine Markierung). Pfade aus
  `ausgenommen` und Fremdcode beenden die Kette ohne Befund.
- **`ziel.detekt.ergebnisse`** zählt alle gelesenen Ergebnisse vor dem Zusammenführen und
  Verwerfen. Die Zahl der Befunde sieht man an den Befunden selbst. Ohne `level` gilt wie in SARIF
  `warning`.
- **detekt-Befunde in Testcode** bleiben erhalten (detekt prüft Tests auch). Ergebnisse in
  Fremdcode und in nicht erfassten Dateien entfallen.
- **detekt-Befehl für Sketchorus (nur `lokal/`).**
  - Es ist kein Sammeltask, sondern die Liste der 17 Aufgabennamen, die `check` als
    detekt-Aufgaben braucht; Gradle führt sie in jedem Modul aus.
  - Dazu `--no-daemon`, sonst sperrt der Daemon Jar-Dateien gegen das nächste `git clean`.
  - Dazu ein Init-Skript unter `lokal/`, das `ignoreFailures` setzt. Der Stand hatte 2 Funde, und
    detekt brach ab, bevor alle SARIF-Dateien geschrieben waren. Echte Build-Fehler führen
    weiterhin zu Exit-Code 2.
  - `JAVA_HOME` muss beim Aufruf gesetzt sein; das Werkzeug setzt es nicht.
- **Ein Python-Test-Skript als Ersatz für Gradle** wird im Test mit absolutem Pfad aufgerufen.

## Grenzen

- Lambdas als Argument gehören zum Aufrufer. Ein Lambda, das markierter Code an eine unmarkierte
  Funktion übergibt, wird dort nicht als Teil der Kette gesehen.
- Externe Aufrufe verfolgt Daidalos nicht; das prüft detekt.
- Delegierte Eigenschaften zählen nur bei sicher aufgelöstem Empfänger und ergeben keine Kante.
  Was im Delegaten (`lazy { … }`) passiert, gehört zum Konstruktor bzw. zur obersten Ebene.
- SARIF-Funde in einer Zeile, die nur im Bereich des primären Konstruktors liegt (Klassenkopf bis
  letzter Initialisierer), hängen an `<init>`.

## Offene Fragen

1. Die Kette ist an Sketchorus kurz (höchstens 2): Der markierte Code ruft fast nur Blätter.
   Lohnt eine eigene Darstellung der Kette auf der Funktionsebene in A09 trotzdem, oder genügt die
   Seitenleiste?
2. Soll `ziele.toml` je Ziel Umgebungsvariablen kennen (etwa `JAVA_HOME`), oder bleibt das Sache
   der Shell?
3. Die zwei detekt-Funde des Klon-Stands sind die, die den Sketchorus-Build dort scheitern lassen.
   Soll Daidalos „detekt brach ab“ künftig von „Build brach ab“ unterscheiden, statt das über ein
   lokales Init-Skript zu lösen?

## Nächste sinnvolle Schritte

- A09: Funktionsebene der Karte. Die Kette auf ihr zeigen, `daidalos.json` für die Karte
  einbetten oder getrennt laden.
- `daidalos markierung --json` für Werkzeuge, wenn der Skill es braucht.
- Gruppierung je `nach` erst, wenn ein Ziel mehr als 40 sichere Grenzkanten hat.
