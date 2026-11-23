# Auftrag A07 – Funktionen und Aufrufgraph (Messung)

**Etappe:** 4 · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A06b (`f9fadaf`). Branch `auftrag/a07-aufrufgraph` von `main`.

## Einordnung

Etappe 4 ist in drei Aufträge geteilt:

- **A07 (dieser Auftrag):** Funktionen als Knoten und `ruft`-Kanten in `daidalos.json`, dazu Annotationen und Komplexität. Es geht nur um die Messung. Die Karte zeigt noch nichts davon.
- **A08:** Markierungs-Kette (`@Strichpfad`/`@Deterministisch` ruft Unmarkiertes) und detekt-SARIF als Befunde.
- **A09:** Zoomstufe Funktionen in der Karte, Wirkungsweg vorwärts und rückwärts, Skill-Ergänzung.

A08 baut vollständig auf den Kanten aus A07 auf. Deshalb gilt die Leitplanke 3 hier besonders: **Was sich nicht eindeutig auflösen lässt, wird unsicher markiert, nie geraten.** Eine falsche sichere Kante ist schlimmer als eine unsichere.

## Schritte

### 1. Funktionsknoten (Kotlin)

Funktionsknoten entstehen für:

- jede `fun` auf oberster Ebene, in Klassen, Objekten, `companion object`, Schnittstellen und `enum`-Einträgen mit Körper;
- Konstruktoren: der primäre, sobald die Klasse `init`-Blöcke oder Eigenschafts-Initialisierer mit Aufrufen hat, und jeder sekundäre;
- `get()`/`set()` mit Körper;
- `external fun`.

Lokale Funktionen (eine `fun` in einer `fun`) zählen zur umgebenden Funktion, ebenso Lambdas und anonyme Objekte.

**Id festzurren** (in `docs/datenformat.md` als endgültig eintragen):

| Fall | Form |
| --- | --- |
| Grundform | `funktion:<dateipfad>#<Behälter>.<name>/<stelligkeit>` |
| Behälter | Klassenkette relativ zur Datei, also `Aussen.Innen` oder `Klasse.Companion`. Auf oberster Ebene leer: `#name/2`. |
| Konstruktoren | `<init>` |
| Accessoren | `<get-feld>` bzw. `<set-feld>` |
| Erweiterungsfunktionen | Empfängertyp in eckigen Klammern hinter dem Namen, wie geschrieben: `#[Strich]laenge/0` bzw. `#Hilfen.[Strich]laenge/0` |
| Stelligkeit | Zahl der Parameter. Der Empfänger zählt nicht, ein `vararg` zählt als 1. |
| Gleiche Stelligkeit kollidiert | an **beide** Ids die Parametertypen anhängen, wie geschrieben und ohne Leerzeichen: `#Strich.setze/2(Int,Float)`, `#Strich.setze/2(Punkt,Float)` |

Felder je Funktionsknoten:

- `id`, `art: "funktion"`, `datei`, `zeile_von`, `zeile_bis`, `name`, `behaelter`, `stelligkeit`
- `sichtbarkeit`: `public`/`internal`/`protected`/`private`
- `modifikatoren`: sortiert, aus `override`, `abstract`, `open`, `suspend`, `inline`, `operator`, `infix`, `external`, `expect`, `actual`
- `erweiterung`: Empfängertyp oder `null`
- `parameter`: Liste `{name, typ, vorgabe: bool, vararg: bool}`
- `rolle`, `quellsatz` wie bei der Datei
- `annotationen`: siehe 2
- `metriken`: siehe 4
- `hash` über den Text der Funktion, nach CRLF→LF

Datei-Knoten bekommen `funktionen: <anzahl>`.

### 2. Annotationen mit vollem Namen

An Funktionen, Klassen und Dateien (`@file:`) wird jede Annotation mit ihrem **vollen Namen** gespeichert. Aufgelöst wird über Import, Alias, Stern-Import eines bekannten Pakets oder das gleiche Paket. Das Ergebnis ist eine sortierte Liste `{"name": "de.x.Strichpfad", "sicher": true}`. Lässt sich ein Name nicht auflösen, wird er mit `"sicher": false` und dem Namen wie geschrieben gespeichert.

Klassen bekommen dafür ein schlankes Feld in einer neuen Liste `klassen` je Datei-Knoten: `{name, art, zeile, annotationen, obertypen}`. `obertypen` enthält die Obertypen wie geschrieben und, falls auflösbar, voll aufgelöst.

Keine Sonderregeln für bestimmte Namen. Welche Annotation als Markierung gilt, entscheidet A08 über `daidalos.toml`. Das ist die Lehre aus `Gegenfaelle.kt`: Dort gibt es gleichnamige Annotationen mit anderem Paket.

### 3. `ruft`-Kanten

Jeder Aufruf in einem Funktionskörper (Lambdas und lokale Funktionen eingeschlossen) wird ausgewertet. Dazu gehören:

- `f(…)`, `x.f(…)`, `x?.f(…)`, `Klasse(…)`
- Aufrufe von Objekt- und Companion-Mitgliedern
- `super.f(…)` und `this.f(…)`
- Funktionsreferenzen `::f` und `X::f` (Herkunft `referenz`)

Die Auflösung läuft in dieser Reihenfolge. Es gilt der erste Schritt, der greift.

1. **Empfänger mit bekanntem Typ.** Der Typ steht bei:
   - `this`, auch implizit, einschließlich der äußeren Klassen;
   - Parametern mit Typangabe;
   - Eigenschaften der Klasse mit Typangabe oder Konstruktor-Initialisierer;
   - lokalen `val`/`var` mit Typangabe oder `= Klasse(…)`;
   - einem Objekt-, Companion- oder Klassennamen.

   Mehr Typinferenz gibt es nicht, also keine Rückgabetypen und keine Ketten `a.b().c()`.
2. **Ohne Empfänger.** Die Suche läuft in dieser Reihenfolge:
   - Mitglieder der umgebenden Klassen von innen nach außen;
   - lokale Funktionen;
   - dieselbe Datei auf oberster Ebene;
   - Importe und Aliase;
   - das gleiche Paket desselben Moduls;
   - Stern-Importe.

   Wie bei `nutzt` sieht produktiver Code keinen Testcode.
3. **Konstruktor:** `Name(…)`, wenn `Name` als Klasse aufgelöst wird. Das Ziel ist `<init>` mit passender Stelligkeit. Gibt es keinen Konstruktorknoten, ist das Ziel die Klasse selbst als `funktion:<pfad>#Klasse.<init>/n`. Dann wird ein Knoten mit `implizit: true` angelegt.
4. **Überladung:** Passend sind Kandidaten, deren Stelligkeit zur Zahl der Argumente passt. Vorgabewerte, `vararg` und ein nachgestelltes Lambda als letztes Argument werden dabei berücksichtigt. Bleibt genau ein Kandidat, ist die Kante sicher. Bleiben mehrere, gibt es eine **unsichere** Kante zu jedem.
5. **Erweiterungsfunktionen:** sicher nur, wenn der Empfängertyp nach Schritt 1 bekannt ist und genau eine passende Erweiterung sichtbar ist. Sonst ist die Kante unsicher und geht zu allen sichtbaren Erweiterungen dieses Namens mit passender Stelligkeit.
6. **Empfänger mit unbekanntem Typ** (`x.f()` mit `x` aus einer Kette oder einem Rückgabewert): Es gibt **unsichere** Kanten zu allen internen Mitgliedern und Erweiterungen namens `f` mit passender Stelligkeit, wenn es höchstens 5 sind. Bei mehr wird der Aufruf als `unaufgeloest` gezählt und mit dem Grund `zu-viele-kandidaten` belegt.
7. **Externe Ziele** (Kotlin-Standardbibliothek, Android, Bibliotheken) ergeben keine Kante. Sie werden je Funktion nur in `metriken.externe_aufrufe` gezählt. Ein Aufruf mit bekanntem externem Empfängertyp ist extern. Ein Aufruf ohne Empfänger, der intern nicht gefunden wird, ebenfalls.

Kante `ruft` (Funktion → Funktion):

- `gewicht`: Zahl der Aufrufstellen
- `sicher`: wahr, wenn mindestens ein Beleg sicher ist
- `rolle`
- `beleg`: Liste `{zeile, herkunft, sicher, grund?}`, sortiert nach Zeile
  - `herkunft`: `this`, `parameter`, `eigenschaft`, `lokal`, `objekt`, `ohne-empfaenger`, `import`, `gleiches-paket`, `konstruktor`, `erweiterung`, `referenz`, `super`, `unbekannter-empfaenger`
  - `grund` bei unsicheren Belegen: `ueberladung`, `erweiterung`, `unbekannter-empfaenger`, `kleingeschrieben`
- Selbstaufrufe werden gezählt (Rekursion), als Kante auf sich selbst.

Weitere Kanten:

- **`ueberschreibt`** (Funktion → Funktion): von einer `override fun` zu der Funktion in einem internen Obertyp, die sie überschreibt (gleicher Name, gleiche Stelligkeit). Sicher nur, wenn der Obertyp aufgelöst ist und genau eine passende Funktion hat. A08 folgt Aufrufen auf eine Schnittstelle über diese Kanten rückwärts zu den Umsetzungen. In A07 ist sie nur Messung.
- **`actual`** (Funktion → Funktion): von `actual fun` zu `expect fun` mit gleichem vollen Namen und gleicher Stelligkeit im selben Modul.
- **`jni`**: zusätzlich auf Funktionsebene von `external fun` zu einem Knoten der C-Funktion `Java_…`. C-Funktionsknoten entstehen nur für diese JNI-Funktionen. Ihre Id hat dieselbe Form, Behälter leer. Aufrufe innerhalb von C bleiben bis Etappe 8 außen vor.
- **`enthaelt`**: Datei → Funktion.
- `ruft` wird **nicht** auf Datei- oder Paketebene verdichtet. Die bestehenden `nutzt`-Kanten bleiben unverändert.

Kommentare und String-Inhalte zählen nicht, Interpolationen schon.

### 4. Metriken je Funktion

- `zeilen`: Codezeilen ohne Leer- und Kommentarzeilen.
- `komplexitaet`: zyklomatisch, also 1 + Anzahl von `if`, jedem `when`-Zweig außer `else`, `for`, `while`, `do`, `catch`, `&&`, `||`, `?:` und `?.let`/`?.run`/`?.also`/`?.apply`/`?.takeIf`. Die Regel kommt wörtlich in `datenformat.md`.
- `fan_in`, `fan_out`: Zahl verschiedener Funktionen über `ruft`, nur Kanten mit `sicher: true`.
- `fan_in_unsicher`, `fan_out_unsicher`: dieselben Zahlen einschließlich der unsicheren Kanten.
- `externe_aufrufe`: siehe 3.7.

### 5. Befund `unaufgeloest`

Der bestehende Befund `unaufgeloest` wird um die Art `aufruf` erweitert. Er bekommt je Datei:

- die Zahl der unaufgelösten Aufrufe,
- die zehn häufigsten Namen mit Grund.

Er ist kein Problem des Zielcodes, sondern ein Maß für die eigene Abdeckung. In der Zusammenfassung steht er unter „Messung“, nicht unter den Befunden.

### 6. `daidalos pfad` auf Funktionsebene

`daidalos pfad VON NACH` nimmt auch Funktions-Ids und findet den kürzesten Weg über `ruft`. Standardmäßig zählen nur sichere Kanten. Mit `--unsicher` zählen auch unsichere, und die Ausgabe kennzeichnet sie. Die Ausgabe nennt je Schritt die Datei und Zeile des Aufrufs.

Neu ist `daidalos aufrufe ID [--rueckwaerts] [--tiefe N] [--unsicher]`. Der Befehl gibt einen Baum der erreichbaren Funktionen als Text aus, ohne Wiederholungen. Bereits besuchte Funktionen erscheinen als Verweis. Das ist der Grundbaustein für A08, und man kann damit von Hand prüfen.

### 7. Was unverändert bleibt

- Karte, Zusammenfassung und Arbeitsblatt zeigen Funktionen noch nicht. Ausnahme: Das Arbeitsblatt einer Datei listet unter „deklariert“ jetzt die Funktions-Ids mit Komplexität, damit der Skill sie kopieren kann.
- `render` muss Funktionsknoten und `ruft`-Kanten überspringen. Die Ladezeit der Karte darf nicht messbar steigen. Dazu die Datenmenge in der Karte vorher und nachher berichten.
- `schema` bleibt 1. Die Änderungen sind rein additiv. Wo Programme bisher alle Knoten durchlaufen, bitte prüfen, dass sie nicht über die neue Art stolpern (Gruppen-Hash, Zusammenfassung, Deutung).

## Tests

- **Neues erfundenes Beispiel** `tests/beispiele/mini_aufrufe` mit KMP-Quellsätzen und je mindestens einem Fall für:
  - Überladung nach Stelligkeit;
  - Überladung mit gleicher Stelligkeit (Id mit Typen, Kante unsicher);
  - Vorgabewert und `vararg`;
  - nachgestelltes Lambda;
  - Erweiterungsfunktion mit bekanntem und mit unbekanntem Empfänger;
  - `companion object`;
  - `object`;
  - Schnittstelle mit zwei Umsetzungen und Aufruf über die Schnittstelle;
  - `super`-Aufruf;
  - `expect`/`actual`;
  - Konstruktor mit `init` und impliziter Konstruktor;
  - Aufruf im Lambda und in lokaler Funktion;
  - gleiches Paket ohne Import;
  - Alias-Import;
  - Stern-Import;
  - Funktionsreferenz;
  - Rekursion;
  - `x.a().b()` (unsicher bzw. unaufgelöst);
  - Aufruf in Kommentar und String, der nicht zählt;
  - Interpolation, die zählt;
  - Testcode, den produktiver Code nicht sieht;
  - externer Aufruf;
  - Annotation in zwei Paketen mit gleichem Namen;
  - `@file:`-Annotation.
- Golden-Datei für `daidalos.json` des Beispiels und für `daidalos aufrufe`.
- **Plausibilität** (erweitert `tests/plausibilitaet.py`):
  - Für jede sichere `ruft`-Kante zwischen zwei Dateien gibt es eine `nutzt`-Kante zwischen diesen Dateien oder es ist dieselbe Datei.
  - Jede `ueberschreibt`-Kante zeigt in einen Obertyp der Klasse.
  - Bei Sketchorus muss das mit 0 Verstößen laufen, bei den Beispielen ebenso.
- Determinismus: zwei Läufe sind byte-gleich, auch unter Windows.

## Probe an Sketchorus

Am Klon: `uv run python werkzeuge/ziel_auffrischen.py sketchorus --erzwingen`.

**Berichten:**

- Zahl der Funktionen (produktiv/test).
- Zahl der Aufrufstellen, aufgeteilt in:
  - intern sicher,
  - intern unsicher (mit Gründen),
  - unaufgelöst (mit Gründen),
  - extern.
- Die fünf häufigsten unaufgelösten Namen.
- Scan-Zeit vorher und nachher sowie Größe von `daidalos.json` vorher und nachher.

**Stichprobe:**

- Claude Code zieht mit festem Startwert 30 zufällige **sichere** `ruft`-Kanten und 15 unsichere aus dem produktiven Code.
- Jede wird im Code nachgesehen: Ist das Ziel richtig? Ist bei unsicheren Kanten das richtige Ziel unter den Kandidaten?
- **Abnahmeschwelle:** 30 von 30 sicheren Kanten richtig. Eine falsche sichere Kante heißt: Ursache finden, Regel verschärfen, neue Stichprobe.
- Die Tabelle mit Kante, Zeile und Urteil kommt nur nach `lokal/A07-stichprobe.md`. Im Bericht stehen nur die Zahlen.

**Drei Ketten von Hand:**

- `daidalos aufrufe` für drei Funktionen mit `@Strichpfad` (vorwärts, Tiefe 3), mit kurzem Urteil, ob der Baum plausibel ist und was fehlt.
- Das ist die Vorbereitung auf A08.
- Nur nach `lokal/A07-ketten.md`.

## Abschluss

Branch pushen, nicht mergen. Bericht `docs/auftraege/A07-bericht.md` mit:

- den Zahlen oben,
- den Grenzen der Auflösung (was bewusst unsicher bleibt),
- Vorschlägen, welche Typinferenz die meisten unsicheren Kanten sicher machen würde.

Antwort an mich mit höchstens 8 Zeilen. Keine Sketchorus-Inhalte im Repo.
