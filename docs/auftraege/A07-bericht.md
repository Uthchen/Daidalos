# Bericht A07 – Funktionen und Aufrufgraph (Messung)

Stand 2026-11-23. Branch `auftrag/a07-aufrufgraph` von `main` (`f9fadaf`), nicht nach `main`
gemergt.

## Was gemacht wurde

### Messung

- **Neuer Adapter `adapter/kotlin_funktionen.py`.** Er liest je `.kt`-Datei:
  - Funktionen mit Parametern, Sichtbarkeit, Modifikatoren, Annotationen, Hash, Codezeilen und
    Komplexität;
  - Klassen mit Art, Obertypen, Eigenschaften und Enum-Einträgen;
  - `@file:`-Annotationen;
  - je Aufruf den Empfänger und seine Umgebung: impliziten Empfänger (Klassen,
    Erweiterungsempfänger, anonyme Objekte, Lambdas) und die an der Stelle gültigen lokalen Namen,
    mit Blockbereichen und in Dokumentreihenfolge.
- **Neuer Auflöser `aufrufgraph.py`.** Er baut aus allen Dateien einen Index und löst Aufrufe nach
  den Schritten 1 bis 7 des Auftrags auf. Er erzeugt:
  - Funktionsknoten, auch implizite Konstruktoren und C-Funktionen `Java_…`;
  - die Kanten `ruft`, `ueberschreibt`, `actual`, `jni` auf Funktionsebene und `enthaelt`
    (Datei → Funktion);
  - die Metriken je Funktion;
  - den Befund `unaufgeloest` der Art `aufruf`.
- **Datei-Knoten** haben neu die Felder `funktionen`, `klassen` und `annotationen`.
- **`daidalos pfad`** nimmt Funktions-Ids und kurze Suchbegriffe (`Strich.zeichne`) und läuft über
  `ruft`; mit `--unsicher` auch über unsichere Kanten. Je Schritt nennt die Ausgabe Datei, Zeile,
  Herkunft und gegebenenfalls den Grund der Unsicherheit.
- **Neu: `daidalos aufrufe ID [--rueckwaerts] [--tiefe N] [--unsicher] [--mit-tests]`.** Der Befehl
  zeigt den Baum der erreichbaren Funktionen ohne Wiederholungen („siehe oben“, „Rekursion“). Ist die
  Tiefe erreicht, steht dort die Zahl der nicht gezeigten Funktionen.
- **Arbeitsblatt einer Datei:** Unter „deklariert“ stehen die Funktions-Ids mit Zeile und
  Komplexität.
- **Karte, `KARTE.md`, Zusammenfassung und Abgleich der Deutung** arbeiten auf einer
  *Strukturansicht* der Messung ohne Funktionsebene (`render.strukturansicht`):
  - Bei Sketchorus ist die Strukturansicht der neuen Messung **gleich** der alten `daidalos.json`.
  - Die eingebetteten Kartendaten sind byte-gleich, vorher wie nachher 1 859 150 Bytes.
  - Auch `karte.html` ist mit 4 025 601 Bytes gleich groß. Die Ladezeit kann also nicht steigen.
  - Die Golden-Prüfsummen der Kartendaten sind unverändert.
- **Zusammenfassung:** neuer Abschnitt „Messung“ (JSON: `messung`) mit Funktionen, `ruft`-Kanten und
  unaufgelösten Aufrufen. Abdeckungsbefunde brauchen keine Einschätzung und machen keine Datei
  wichtig.
- **`daidalos scan`** gibt zusätzlich die Zeilen `Funktionen:` und `Aufrufe:` aus.
- **`schema` bleibt 1.** Alle Änderungen sind additiv.

### Tests

- **Neues Beispiel `tests/beispiele/mini_aufrufe`**: KMP mit `commonMain`, `jvmMain` und
  `commonTest`, dazu ein Modul `app`. Es enthält jeden geforderten Fall, außerdem:
  - eine Eigenschaftskette über eine Datei ohne direkten Bezug;
  - Enum-Einträge;
  - `apply`;
  - eine Annotation mit Argument auf eigener Zeile.
- **`tests/test_aufrufe.py`** mit 28 Tests: je Fall eine Prüfung, Plausibilität, zwei Läufe
  byte-gleich, CRLF ändert Hash und Zeilen nicht, `pfad` auf Funktionsebene, mehrdeutige Id als
  Bedienfehler.
- **Golden-Dateien:** `mini_aufrufe.daidalos.json` und drei Ausgaben von `daidalos aufrufe`
  (vorwärts mit unsicheren Kanten, rückwärts mit Tests, Tiefe 1).
- **`tests/plausibilitaet.py`** prüft jetzt auch `ruft` und `ueberschreibt` (Abweichung siehe
  unten).
- Bestehende Tests sind angepasst:
  - Die Karte bettet die Strukturansicht ein.
  - Es gibt zwei `jni`-Ebenen.
  - Metriken werden nur für Nicht-Funktionen geprüft.
  - Das Arbeitsblatt einer C-Datei listet ihre JNI-Funktionen.
- `ruff check`, `ruff format --check`, `pytest`: **284 bestanden, 1 übersprungen**, lokal unter
  Windows, einschließlich Browser-Probe (26). Golden-Dateien und die drei Sketchorus-Läufe sind
  byte-gleich.

### Doku

- **`docs/datenformat.md`:**
  - die Funktions-Id als endgültig, mit allen Fällen;
  - Felder der Funktionsknoten, Klassen, Annotationen;
  - die Regeln für `ruft`, `ueberschreibt`, `actual` und `jni`;
  - Abschwächungen und Sichtbarkeit;
  - die Komplexitätsregel wörtlich;
  - Metriken je Funktion, Abdeckungsbefund und Strukturansicht;
  - `pfad` und `aufrufe`.
- **`CLAUDE.md`:** Befehl und Aufbau ergänzt.
- **`SKILL.md`:** ein kurzer Absatz zu `daidalos aufrufe` (Grund unter „Abweichungen“).

## Zahlen an Sketchorus

Klon `598b0fc`, `ziel_auffrischen.py sketchorus --erzwingen`; Deutung danach ohne offene Punkte.

| Messgröße | Wert |
| --- | ---: |
| Funktionen produktiv / Test | 2 726 / 949 (darin 171 implizite Konstruktoren, 26 C-Funktionen) |
| Aufrufstellen intern sicher | 10 980 |
| Aufrufstellen intern unsicher | 1 327 |
| davon `unbekannter-empfaenger` | 1 204 |
| davon `ueberladung` | 104 |
| davon `kleingeschrieben` | 19 |
| davon `erweiterung` | 0 |
| Aufrufstellen unaufgelöst (`zu-viele-kandidaten`) | 97 |
| Aufrufstellen extern | 18 227 |
| Aufrufe lokaler Funktionen bzw. von Funktionen anonymer Objekte (keine Kante) | 306 |
| Aufrufe von Werten, etwa `aktion()` (keine Kante) | 199 |
| `ruft`-Kanten (sicher) | 8 759 (7 478) |
| `ueberschreibt` (sicher) | 60 (54) |
| `actual` | 0 (Sketchorus nutzt kein `expect`/`actual`) |
| `jni` auf Funktionsebene | 26 |

Eine Aufrufstelle zählt einmal, auch wenn sie mehrere unsichere Kanten hat.

**Die fünf häufigsten unaufgelösten Namen:** `inhalt` (58), `lies` (12), `close` (10),
`freigeben` (8), `beende` (4).

**Scan-Zeit:** 1,97 s vorher, 3,85–3,92 s nachher (drei Läufe).

**`daidalos.json`:** 2 384 855 Bytes vorher, 15 612 965 Bytes nachher (Faktor 6,5). Davon entfallen:

| Teil | Größe |
| --- | ---: |
| `ruft`-Kanten mit Belegen | 6,6 MB |
| Funktionsknoten | 3,6 MB |
| `enthaelt`-Kanten | 2,1 MB (vorher 0,4 MB) |

**Plausibilität:** 0 Verstöße an Sketchorus und an allen drei Beispielen. 133 sichere Kanten an
Sketchorus erreichen ihr Ziel nur über einen `nutzt`-Weg (siehe Abweichungen).

**Stichprobe:** fester Startwert 7, 30 sichere und 15 unsichere produktive `ruft`-Kanten, jede im
Code nachgesehen. Die Tabelle steht nur in `lokal/A07-stichprobe.md`.

| Runde | Sicher richtig | Unsicher: Ziel unter den Kandidaten |
| --- | ---: | ---: |
| 1 | 30 von 30 | 14 von 15 |
| 2 | 30 von 30 | 15 von 15 |
| Endstand | 30 von 30 | 15 von 15 |

Den Ausreißer der ersten Runde zeigt Abweichung 6. Endstand: Durch die Enum-Regel entstanden 20
sichere Aufrufstellen mehr, die Ziehung ergab 18 neue Kanten; alle sind geprüft.

**Drei Ketten:** `daidalos aufrufe` mit Tiefe 3 für drei Einstiege mit `@Strichpfad` (Eingabe,
Kern-Thread, Darstellung); Bäume und Urteil nur in `lokal/A07-ketten.md`. Alle drei Bäume sind
plausibel. Jeder interne Aufruf in den Körpern der Einstiege ist gefunden. Es fehlt das Lesen von
Eigenschaften mit eigenem Getter: In einem Fall hat eine gelesene Eigenschaft einen markierten
`get()`, der als Knoten `<get-…>` existiert, aber von keiner Kante erreicht wird.

## Abweichungen vom Auftrag

1. **Plausibilitätsregel erweitert.**
   - Die wörtliche Regel („jede sichere `ruft`-Kante zwischen zwei Dateien hat eine `nutzt`-Kante“)
     ergab an Sketchorus 133 Verstöße.
   - Alle laufen über Empfänger mit bekanntem Typ, meist Eigenschaftsketten der Form
     `q.index.f()`: `q` hat einen Typ aus einer importierten Datei, dessen Eigenschaft `index` einen
     Typ aus einer dritten Datei hat.
   - Stichproben zeigen: Die Kanten sind richtig, nur kommt der Typ von `index` in der aufrufenden
     Datei nicht vor.
   - Die Prüfung lässt deshalb für Belege mit Herkunft `eigenschaft`, `parameter`, `lokal`, `this`
     und `super` einen `nutzt`-Weg über höchstens drei Kanten zu. Die Zahl dieser Fälle wird
     getrennt ausgegeben (133). Alle anderen Herkünfte brauchen weiterhin die direkte Kante.
2. **Ketten aus Eigenschaften** (`a.b.f()`, `Klasse.Companion.f()`, `Enum.EINTRAG.f()`) gelten als
   bekannter Typ. Der Auftrag verbietet Rückgabetypen und Ketten über Aufrufe. Beides bleibt
   ausgeschlossen, auch `Klasse(…).f()`. Eigenschaften mit Typangabe sind keine Inferenz, und die
   Stichprobe bestätigt sie.
3. **Sichtbarkeit über Produktiv/Test hinaus:**
   - Im selben Modul gelten Quellsätze: `commonMain` sieht kein `jvmMain`, `jvmTest` sieht `jvmMain`.
   - Zwischen Modulen zählen nur Gradle-Abhängigkeiten.
   - `private` gilt nur in der eigenen Datei.
   - Ohne die Quellsatz-Regel wäre jeder Aufruf einer `expect`-Funktion aus `commonMain` eine
     Überladung mit dem `actual`. Ohne die Gradle-Regel bekam `core` Kandidaten aus `core-labor`.
4. **Grund `kleingeschrieben`** hat eine eigene Bedeutung. Ein kleingeschriebener Name, der
   außerhalb der Klassen gefunden wird (Datei, Import, Paket), ist unsicher, wenn ein impliziter
   Empfänger unbekannte Mitglieder hat. Das gilt für einen externen Obertyp, einen externen
   Erweiterungsempfänger oder ein Lambda einer externen Funktion, außer bei bekannten Lambdas ohne
   Empfänger wie `let`, `map`, `forEach` oder `remember`. Ein gleichnamiges Mitglied hätte dann
   Vorrang. Großgeschriebene Namen (Composables, Klassen) bleiben sicher.
5. **Lambdas von `apply`, `run` und `with`** setzen einen impliziten Empfänger. Bei bekanntem Typ
   wird dort zuerst gesucht, bei unbekanntem Typ werden Treffer unsicher.
6. **Nach der ersten Stichprobe verschärft:**
   - Kandidaten aus Modulen ohne Gradle-Abhängigkeit fallen weg.
   - `Enum.entries` ist extern. Das war der Ausreißer `EineEnum.entries.filter { … }`, der auf eine
     gleichnamige eigene Methode `filter` einer Klasse zeigte.
   - `Enum.EINTRAG` hat den Typ der Enum-Klasse.
7. **Keine Kante:**
   - Aufrufe lokaler Funktionen und von Funktionen anonymer Objekte gehören zur Funktion.
   - Aufrufe von Werten (`aktion()`, Parameter mit Funktionstyp) haben kein Ziel.
   - Beide zählen weder als extern noch als unaufgelöst; sie stehen nur in den Zahlen oben.
8. **`fan_in`/`fan_out` je Funktion** zählen wie bei Dateien nur Kanten der Rolle `produktiv` und
   nicht die Funktion selbst. Die Rekursion bleibt als Kante sichtbar.
9. **Primärer Konstruktor:** Auch Objekte und Companions bekommen `<init>`, wenn ihre
   Initialisierer Aufrufe haben. Zu seinen Aufrufen zählen auch Vorgabewerte der Klassenparameter und
   der Aufruf des Oberklassen-Konstruktors. Implizite Konstruktoren werden nur angelegt, wenn ein
   Aufruf sie trifft. Bei gleicher Stelligkeit mit einem sekundären Konstruktor tragen beide
   Typen-Ids, auch wenn der implizite nie getroffen wird.
10. **Ids:**
    - Bleiben trotz Typen gleich, kommt `@<zeile_von>` dazu.
    - Fehlt ein Typ, steht `?` an seiner Stelle.
    - Ein benannter Companion heißt im Behälter mit seinem Namen.
11. **C-Funktionsknoten** entstehen für alle `Java_…`-Definitionen, nicht nur für die mit
    Gegenstück. Ihre `komplexitaet` ist `null`, weil die Regel nur für Kotlin gilt.
12. **Abdeckungsbefund als eigener Befund** `befund:unaufgeloest:aufruf:<pfad>` mit
    `beleg.art = "aufruf"`. Der bestehende Import-Befund ist unverändert, damit vorhandene
    Einschätzungen und Golden-Dateien gültig bleiben.
13. **`SKILL.md`:** Ein Absatz zu `daidalos aufrufe` ist nötig, weil `test_skill` verlangt, dass der
    Skill jeden Befehl nennt. Die eigentliche Skill-Ergänzung bleibt A09.
14. **Annotationen auf eigener Zeile:** Die Grammatik liest `@Suppress("x")` nach einer
    Ausdrucksfunktion als eigenen Knoten. Solche Annotationen werden der nächsten Deklaration
    zugeordnet.

## Grenzen der Auflösung (bewusst unsicher oder ohne Kante)

- **Ohne Typinferenz:**
  - Rückgabewerte, Ketten über Aufrufe, `Klasse(…).f()`;
  - Smart-Casts (`if (x is Kreis) x.radius()` bleibt beim deklarierten Typ, oft extern);
  - Typargumente (`List<Strich>` → `liste.first().f()`);
  - `it` und Lambda-Parameter ohne Typangabe;
  - lokale Werte, deren Initialisierer kein Konstruktor ist (`val p = feld`).
- **Überladungen gleicher Stelligkeit** werden nicht nach Argumenttypen unterschieden, auch
  Literale nicht (`varint(0)` → `Int` oder `Long`).
- **Lesen und Schreiben von Eigenschaften** ist kein Aufruf, auch nicht bei eigenem Getter oder
  Setter. Die Accessor-Knoten existieren, haben aber keine eingehenden Kanten.
- **Aufrufe über Schnittstellen** enden an der Schnittstellenmethode. Die Umsetzungen hängen über
  `ueberschreibt` daran.
- **DSL-Lambdas mit Empfänger** externer Funktionen (Compose `Canvas { }`, `launch { }`) sind nur
  über die Regel `kleingeschrieben` abgesichert. Ein gleichnamiges *großgeschriebenes* Mitglied des
  fremden Empfängers würde übersehen; das ist unüblich.
- **Mehrstufige KMP-Quellsätze** (`jvmCommonMain` o. ä.) kennt die Sichtbarkeitsregel nicht. Ziele
  dort sind aus anderen Plattform-Quellsätzen unsichtbar. Das verliert Kanten, erzeugt aber keine
  falschen.
- **Typaliase** als Empfängertyp gelten als unbekannt.
- **Datenklassen:** Erzeugte Funktionen (`copy`, `componentN`) gelten als extern.

## Welche Typinferenz am meisten brächte

Produktive unsichere und unaufgelöste Aufrufstellen an Sketchorus (716), nach Art des Empfängers:

| Empfänger | Stellen | Was helfen würde |
| --- | ---: | --- |
| lokaler Wert oder Lambda-Parameter ohne Typ | 341 | **Initialisierer übernehmen:** `val p = feld` (Eigenschaft mit Typ), `val x = y` (lokal mit Typ) und **erklärte Rückgabetypen interner Funktionen** (`val k = liefere()` mit `fun liefere(): K`) |
| Ausdruck als Empfänger (Rückgabewert, Index, `!!`, Klammer) | 227 | **erklärte Rückgabetypen interner Funktionen** für `f().g()` und `a.b().c()`; `Klasse(…).f()` als Konstruktor-Ergebnis; `(x as T).f()` |
| Überladung gleicher Stelligkeit | 93 | Argumenttypen aus Literalen (`0` → `Int`, `0L` → `Long`, `x.toLong()`) und aus Parametern oder lokalen Werten mit Typ |
| `it` im Lambda | 21 | Typargumente einfacher Sammlungen (`List<T>.forEach`) und eigener Funktionen mit Lambda-Parameter |
| `kleingeschrieben` | 17 | eine kleine Liste bekannter Mitglieder externer Obertypen (z. B. Basisklassen von detekt-Regeln), oder bewusst so lassen |
| Name oder Eigenschaft ohne Typ | 14 | Eigenschaften mit Initialisierer aus Eigenschaften oder Rückgabetypen (wie oben) |

**Empfehlung:** Zuerst erklärte Rückgabetypen interner Funktionen und die Übernahme von
Initialisierern (Eigenschaft, lokaler Wert, Konstruktor, Funktion mit Rückgabetyp). Zusammen
betreffen sie gut drei Viertel der Fälle (568 von 716) und brauchen keine echte Inferenz, nur einen
Schritt mehr Nachschlagen. Danach Literaltypen für Überladungen.

## Offene Fragen

1. **Größe von `daidalos.json`** (15,6 MB statt 2,4 MB). Die Datei liegt committet im Zielrepo,
   jeder Scan erzeugt große Diffs. Drei Möglichkeiten:
   - Belege kompakter schreiben (z. B. nur Zeilen je Herkunft);
   - die Funktionsebene in eine eigene Datei `aufrufe.json` legen;
   - `enthaelt` Datei → Funktion weglassen, es steht ja schon in `datei` des Funktionsknotens.
2. **Getter und Setter:** Sollen Lesen und Schreiben von Eigenschaften mit eigenem Accessor
   `ruft`-Kanten zu `<get-x>`/`<set-x>` werden? Für A08 wichtig, siehe die drei Ketten.
3. **`Klasse(…).f()`** als sicher werten? Das wäre ein Rückgabewert, aber ein trivialer.
4. **Fan-in/Fan-out** nur über produktive Kanten, wie bei Dateien? Oder sollen Test-Aufrufer
   mitzählen?

## Nächste sinnvolle Schritte

1. **A08:**
   - Markierung aus `daidalos.toml` über volle Namen. Die gleichnamige Annotation aus einem
     anderen Paket (22 Funktionen) bleibt an Sketchorus korrekt getrennt.
   - Der Kette über `ruft` folgen, an Schnittstellen über `ueberschreibt` rückwärts weiter.
   - Klassen-Markierungen auf ihre Funktionen übertragen, ohne `<init>`.
2. **Accessoren als Ziele aufnehmen** (Frage 2), bevor A08 Befunde meldet.
3. **Erklärte Rückgabetypen und Initialisierer-Übernahme** (siehe oben), danach die Stichprobe
   wiederholen.
4. **Über die Größe der JSON-Datei entscheiden**, bevor A09 die Funktionsebene in die Karte bringt.
