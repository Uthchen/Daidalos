# Auftrag A07b – Nacharbeit Aufrufgraph: Accessoren, Rückgabetypen, kleinere JSON

**Etappe:** 4 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A07 (`7c87600`). Branch `auftrag/a07b-nacharbeit` von `main`.

## Ziel

Die offenen Fragen aus dem A07-Bericht sind entschieden. Dieser Auftrag schließt die Lücken, die A08 sonst trüben würden, und macht die Messung wieder handlich. Leitplanke 3 gilt unverändert: Eine falsche sichere Kante ist schlimmer als eine unsichere.

## Entscheidungen der Leitung zu den offenen Fragen

1. **Größe:** Die Funktionsebene bleibt in `daidalos.json`. Es gibt also keine zweite Datei, weil Karte, Skill und `pfad` eine Quelle lesen sollen. Die Datei wird aber kleiner: siehe Schritt 4.
2. **Getter und Setter** werden Ziele: siehe Schritt 1.
3. **`Klasse(…).f()`** gilt als bekannter Typ: siehe Schritt 2.
4. **Fan-in und Fan-out** zählen nur produktive Kanten, wie bei Dateien. Das bleibt so.

Alle Abweichungen aus A07 sind angenommen.

## Schritte

### 1. Lesen und Schreiben von Eigenschaften mit eigenem Accessor

- Hat eine interne Eigenschaft einen `get()` mit Körper, wird jedes Lesen eine `ruft`-Kante zum Knoten `<get-x>`. Herkunft ist `lesen`.
- Hat sie einen `set()` mit Körper, wird jede Zuweisung eine Kante zu `<set-x>`, auch `+=` und Ähnliches. Herkunft ist `schreiben`.
- Für den Empfänger gelten dieselben Regeln wie bei Aufrufen: `this`/implizit, Parameter, Eigenschaft, lokal, Objekt, Ketten aus Eigenschaften. Bei unbekanntem Empfänger ist die Kante unsicher, bei mehr als 5 Kandidaten gibt es keine Kante. Dafür werden keine neuen Unaufgelöst-Zahlen gezählt, weil Lesen kein Aufruf ist.
- Eigenschaften ohne eigenen Accessor ergeben keine Kante. Delegierte Eigenschaften (`by lazy`, `by mutableStateOf`) ebenfalls nicht. Sie werden aber am Knoten der Klasse unter `klassen[].eigenschaften` mit `delegiert: true` vermerkt, damit A08 sie nennen kann.
- Mehrere Lesezugriffe derselben Funktion auf dasselbe Ziel bilden eine Kante mit Gewicht, wie bei Aufrufen.

### 2. Mehr Typen durch Nachschlagen statt Inferenz

Es kommen nur Fälle dazu, bei denen der Typ **ausdrücklich im Code steht**:

- **Erklärte Rückgabetypen interner Funktionen:** `f().g()` und `a.b().c()`, wenn `f` bzw. `b` sicher aufgelöst ist und einen ausgeschriebenen Rückgabetyp hat. Ausdrucksfunktionen ohne Rückgabetyp (`fun f() = …`) zählen nur, wenn ihr Ausdruck ein Konstruktoraufruf ist.
- **Konstruktor-Ergebnis:** `Klasse(…).f()`.
- **Übernahme bei Initialisierern:** `val x = y`, `val p = feld` und `val k = liefere()` übernehmen den Typ der rechten Seite, sofern diese nach den Regeln hier oder in A07 bekannt ist. Das gilt für lokale Werte und Eigenschaften.
- **Casts und Null-Operatoren:** `(x as T).f()`, `(x as? T)?.f()`, `x!!.f()`, Klammern.
- **Nicht dazu:**
  - Smart-Casts;
  - Typargumente (`List<T>`, `it`);
  - Rückgabetypen externer Funktionen;
  - Typaliase;
  - Überladungen nach Argumenttypen.

  Die zehn häufigsten verbleibenden unsicheren Fälle werden im Bericht mit Art aufgelistet.

Neue Herkünfte heißen `rueckgabe`, `konstruktor-ergebnis`, `initialisierer` und `cast`. Der Beleg nennt dabei die Herkunft des **letzten** Schritts.

### 3. Plausibilität

Die Prüfung aus A07 (`nutzt`-Weg über höchstens drei Kanten) gilt auch für die neuen Herkünfte und für `lesen`/`schreiben`. Verstöße: 0.

### 4. Kleinere `daidalos.json`

- **`enthaelt` Datei → Funktion entfällt.** Die Zugehörigkeit steht in `datei` des Funktionsknotens. Programme, die bisher `enthaelt` lesen, müssen das berücksichtigen.
- **Belege von `ruft` zusammenfassen:** je `(herkunft, sicher, grund)` ein Eintrag mit sortierter Liste `zeilen`. Beispiel:

  ```json
  {"herkunft": "this", "sicher": true, "zeilen": [12, 40, 41]}
  ```

  `gewicht` bleibt die Zahl der Aufrufstellen.
- **Funktionsknoten:**
  - `parameter` nur noch als Liste von Typen wie geschrieben.
  - Vorgabewerte und `vararg` als Indizes in `parameter_vorgabe` und `parameter_vararg`, und zwar nur, wenn es welche gibt.
  - Leere Listen und `false`-Felder dürfen bei Funktionsknoten entfallen. Das gilt nur dort, und in `datenformat.md` muss für jedes Feld der Standardwert stehen.
- **Ziel:** `daidalos.json` an Sketchorus unter **8 MB**. Wenn das nicht ohne Informationsverlust geht, Messwerte berichten und nicht weiter kürzen.
- **`schema`:** Die Funktionsebene ist in `datenformat.md` bis A09 als **vorläufig** gekennzeichnet. Deshalb bleibt `schema` 1, obwohl sich Felder ändern. Diese Ausnahme wird dort genau so beschrieben.

## Tests

- **`mini_aufrufe` erweitern um:**
  - Getter mit Körper, gelesen über `this`, Parameter und Kette;
  - Setter mit Körper bei `=` und `+=`;
  - Eigenschaft ohne Accessor, ohne Kante;
  - `by lazy`, ohne Kante und mit `delegiert`;
  - Rückgabetyp intern und `f().g()`;
  - Ausdrucksfunktion mit Konstruktor und ohne;
  - `Klasse(…).f()`;
  - `val k = liefere()`;
  - `as`, `as?`, `!!`;
  - Rückgabetyp extern, unverändert unsicher.
- Golden-Dateien neu. Die Determinismus-Prüfung bleibt.
- Ein Test prüft, dass `enthaelt` Datei → Funktion nicht mehr vorkommt und alle Leser (`render`, `zusammenfassung`, `arbeitsblatt`, `pfad`, `aufrufe`) ohne sie auskommen.

## Probe an Sketchorus

Am Klon mit `--erzwingen`. Zu berichten ist eine Tabelle vorher/nachher:

- Aufrufstellen sicher, unsicher, unaufgelöst und extern;
- neue Kanten durch `lesen` und `schreiben`;
- Größe von `daidalos.json` und Scan-Zeit.

Für die Stichprobe zieht Claude Code mit Startwert 8 neu:

- **30 sichere Kanten**, davon mindestens 15 mit den neuen Herkünften (`lesen`, `schreiben`, `rueckgabe`, `konstruktor-ergebnis`, `initialisierer`, `cast`);
- **10 unsichere Kanten**.

Abnahme wie in A07: **30 von 30 sicheren Kanten richtig**. Die Tabelle kommt nur nach `lokal/A07b-stichprobe.md`.

Die drei Ketten aus A07 sind noch einmal zu erzeugen. Zu berichten ist, ob jetzt der markierte Getter `<get-voll>` erreicht wird, nur nach `lokal/A07b-ketten.md`.

## Abschluss

- Branch pushen, nicht mergen.
- Bericht `docs/auftraege/A07b-bericht.md`.
- Antwort an mich mit höchstens 8 Zeilen.
- Keine Sketchorus-Inhalte im Repo.
