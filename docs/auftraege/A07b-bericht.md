# Bericht A07b – Nacharbeit Aufrufgraph: Accessoren, Rückgabetypen, kleinere JSON

Stand 2026-11-23. Branch `auftrag/a07b-nacharbeit` von `main` (`7c87600`), nicht nach `main`
gemergt.

## Was gemacht wurde

### 1. Lesen und Schreiben von Eigenschaften mit eigenem Accessor

- Der Adapter sammelt je Funktion neben den Aufrufen die **Zugriffe**: Namen als Ausdruck, `a.x`
  (nicht als Kopf eines Aufrufs), `this.x`, `"$x"`, Zuweisungen (`=`, `+=` …) und `++`/`--`.
  Namen in Deklarationen, Typen, Labels, Argumentnamen und Funktionsreferenzen zählen nicht; lokale
  Werte und Parameter verdecken Eigenschaften.
- Der Auflöser löst nur Zugriffe auf Namen auf, für die es irgendwo einen Accessor-Knoten gibt.
  Empfänger wie bei Aufrufen (implizit/`this`, Parameter, Eigenschaft, lokal, Objekt, Ketten, die
  neuen Typen aus Schritt 2, Erweiterungseigenschaften, `super`).
  - Lesen → `<get-x>` (Herkunft `lesen`), Schreiben → `<set-x>` (Herkunft `schreiben`).
  - Unbekannter Empfänger: unsicher zu allen sichtbaren Accessoren des Namens; mehr als 5: keine
    Kante. Es wird nichts als unaufgelöst gezählt, auch nicht in `externe_aufrufe`.
  - Ohne eigenen Accessor oder delegiert: keine Kante.
- `klassen[].eigenschaften` = `[{ "delegiert", "name", "zeile" }]`, ebenso als Datei-Feld
  `eigenschaften` für die oberste Ebene.
- Mehrere Zugriffe auf dasselbe Ziel bilden eine Kante mit Gewicht.

### 2. Mehr Typen durch Nachschlagen

- Der Empfänger eines Aufrufs ist jetzt ein Ausdruck: Kette, **Ergebnis eines Aufrufs**,
  **Cast**; `!!` und Klammern sind durchsichtig. Der innere Aufruf wird einmal aufgelöst und das
  Ergebnis wiederverwendet.
- `rueckgabe`: erklärter Rückgabetyp eines sicher aufgelösten internen Ziels; Ausdrucksfunktionen
  ohne Rückgabetyp nur, wenn ihr Ausdruck sich als Konstruktor auflöst.
- `konstruktor-ergebnis`: `Klasse(…).f()`.
- `initialisierer`: `val x = y`, `val p = feld`, `val k = liefere()`, `val i = a.b` für lokale
  Werte, Eigenschaften der Klasse und der obersten Ebene. Die rechte Seite wird mit den Rahmen an
  ihrer eigenen Stelle aufgelöst, mit Schutz gegen Zyklen.
- `cast`: `(x as T).f()`, `(x as? T)?.f()`.
- Der Beleg nennt die Herkunft des letzten Schritts.

### 3. Plausibilität

`tests/plausibilitaet.py` lässt den `nutzt`-Weg über höchstens drei Kanten auch für die neuen
Herkünfte und für `lesen`/`schreiben` zu. **Verstöße: 0** an Sketchorus und an allen drei
Beispielen. 181 sichere Kanten an Sketchorus erreichen ihr Ziel nur über einen solchen Weg (A07: 133
bzw. 134 am selben Klon-Stand).

### 4. Kleinere `daidalos.json`

- Keine `enthaelt`-Kante Datei → Funktion mehr.
- `ruft`-Belege je (Herkunft, sicher, Grund) mit sortierter Liste `zeilen`.
- Funktionsknoten: `parameter` als Liste der Typen, `parameter_vorgabe`/`parameter_vararg` nur bei
  Bedarf; leere Listen (`annotationen`, `modifikatoren`, `parameter`) und `implizit: false`
  entfallen.
- `docs/datenformat.md`: Funktionsebene bis A09 **vorläufig**, `schema` bleibt 1, mit genau dieser
  Ausnahme und der Liste der Änderungen aus A07b; Standardwert je Feld des Funktionsknotens.
- Alle Leser kommen ohne die Kante aus. Angepasst wurden nur `pfad`/`aufrufe` (Belege mit `zeilen`)
  und die Strukturansicht (Datei-Feld `eigenschaften`).

### Tests

- `mini_aufrufe` hat zwei neue Dateien:
  - `Zugriffe.kt`: Getter über `this`, implizit, Parameter und Kette; Setter bei `=` und `+=`;
    Eigenschaft ohne Accessor; `by lazy`.
  - `Typen.kt`: Rückgabetyp, `a.b().c()`, Ausdrucksfunktion mit und ohne Konstruktor,
    `Klasse(…).f()`, `val k = liefere()`, `val kopie = k`, Eigenschaft mit Initialisierer, `as`,
    `as?`, `!!`, externer Rückgabetyp.
- `Werkzeug.kt` und `Viele.kt` sind so angepasst, dass die alten unsicheren Fälle weiter unsicher
  sind. `liefereStrich().laenge()` ist jetzt sicher; dafür gibt es neu `holeStrich().laenge()` mit
  externem Rückgabewert. Die Kette in `ketten()` läuft über eine Ausdrucksfunktion ohne
  Konstruktor.
- Neue Tests in `test_aufrufe.py`:
  - Getter, Setter, keine Kante ohne Accessor, `delegiert`;
  - Typen durch Nachschlagen;
  - keine `enthaelt`-Kante zu Funktionen, keine leeren Listen;
  - alle fünf Leser (`render`, `zusammenfassung`, `arbeitsblatt`, `pfad`, `aufrufe`) laufen auf der
    neuen Ausgabe.
- Golden-Dateien sind neu geschrieben. In `mini_modulgraph` wurde eine Kante sicher:
  `Start().los()`, jetzt mit Herkunft `konstruktor-ergebnis`. Die Determinismus-Prüfung bleibt.
- `ruff check`, `ruff format --check`, `pytest`: **291 bestanden, 1 übersprungen**, lokal unter
  Windows, einschließlich Browser-Probe.

## Probe an Sketchorus

Klon `7801d18`, `ziel_auffrischen.py sketchorus --erzwingen`. „Vorher“ ist der A07-Code (`main`) am
**selben** Klon-Stand. Drei Scans sind byte-gleich.

| Messgröße | vorher (A07) | nachher (A07b) |
| --- | ---: | ---: |
| Aufrufstellen intern sicher | 11 030 | 11 532 |
| Aufrufstellen intern unsicher | 1 329 | 864 |
| davon `unbekannter-empfaenger` | 1 206 | 725 |
| davon `ueberladung` | 104 | 119 |
| davon `kleingeschrieben` | 19 | 19 |
| davon `erweiterung` | 0 | 1 |
| Aufrufstellen unaufgelöst | 97 | 36 |
| Aufrufstellen extern | 18 343 | 18 367 |
| Lesestellen sicher / unsicher | – | 172 / 255 |
| Schreibstellen sicher / unsicher | – | 7 / 2 |
| neue Kanten nur aus `lesen`/`schreiben` (sicher) | – | 308 (139); produktiv 233 (108) |
| `ruft`-Kanten (sicher) | 8 804 (7 521) | 8 947 (8 020) |
| Funktionsknoten | 3 696 | 3 696 |
| `daidalos.json` | 15 695 817 Bytes | 13 704 798 Bytes |
| Scan-Zeit (drei Läufe) | 3,97–4,01 s | 4,43–4,61 s |

Eine Stelle zählt einmal, auch wenn sie mehrere unsichere Kanten hat. Bei `ueberladung` kommen
Stellen hinzu, weil ihr Empfänger jetzt einen Typ hat und erst dann die Überladung offen bleibt.

### Größe: Ziel 8 MB nicht erreicht

Die geforderten Maßnahmen, einzeln auf die Vorher-Datei angewandt:

| Schritt | Größe |
| --- | ---: |
| vorher | 15,70 MB |
| ohne `enthaelt` Datei → Funktion | 13,91 MB |
| + Belege zusammengefasst | 13,73 MB |
| + kompakte Funktionsknoten | 12,92 MB |
| nachher (mit den neuen Kanten und `eigenschaften`) | 13,70 MB |

Die Belege bringen wenig: Die meisten `ruft`-Kanten haben genau eine Aufrufstelle. Den Großteil der
Kanten machen die drei Ids aus, `id`, `von` und `nach`: 4,1 MB der 6,9 MB `ruft`. Eine Funktions-Id
enthält den ganzen Dateipfad. Ohne Informationsverlust ist 8 MB nicht zu erreichen, ohne das
Id-Schema oder die Einrückung zu ändern. Gemessen, **nicht umgesetzt**:

| Möglichkeit | Größe danach |
| --- | ---: |
| `ruft` ohne `id` (aus `von`, `nach`, `rolle` ableitbar) | 11,42 MB |
| dazu Funktionsknoten ohne `datei` (steht in der Id) | 11,08 MB |
| nur `zeilen` einzeilig statt eine Zahl je Zeile | 13,43 MB |
| ganze Datei ohne Einrückung (Vergleichswert) | 10,26 MB |

### Stichprobe

Startwert 8, produktive Kanten: 30 sichere, davon 15 mit neuen Herkünften (6 `initialisierer`,
2 `konstruktor-ergebnis`, 7 `lesen`), und 10 unsichere. Jede ist im Code nachgesehen. Tabelle nur in
`lokal/A07b-stichprobe.md`.

- **Sicher: 30 von 30 richtig.**
- Unsicher: Bei allen 10 ist das richtige Ziel unter den Kandidaten. Eine davon wäre eindeutig (ein
  Objekt im selben Paket), war aber schon in A07 unsicher; siehe Offene Fragen.

### Drei Ketten

Die drei Einstiege aus A07 sind neu erzeugt (`lokal/A07b-ketten.md`). **Der markierte Getter aus A07
wird jetzt erreicht** (sichere Kante, Herkunft `lesen`). Die beiden anderen Ketten bleiben gleich: Die
dort gelesenen Eigenschaften haben keinen eigenen Getter.

### Die zehn häufigsten verbleibenden unsicheren Fälle

Produktive unsichere und unaufgelöste Aufrufstellen an Sketchorus: 508 (A07: 716). Es gibt nur
neun Arten; mehr als neun lassen sich nicht unterscheiden.

| Art des Empfängers | Stellen |
| --- | ---: |
| Lambda- oder Schleifenvariable, Zerlegung ohne Typangabe (Typargument) | 157 |
| Überladung gleicher Stelligkeit | 98 |
| lokaler Wert, dessen Initialisierer keinen bekannten Typ hat | 64 |
| sonstiger Ausdruck (Literal, Operator, `if`-/`when`-Ausdruck u. ä.) | 50 |
| Aufrufergebnis ohne erklärten Typ oder mit unsicherem Ziel | 44 |
| Eigenschaft oder Name ohne Typ in einer Kette | 28 |
| Index `a[i].f()` | 24 |
| `it` im Lambda | 20 |
| `kleingeschrieben` (externer impliziter Empfänger) | 17 |
| Ergebnis einer externen Funktion | 6 |

Skript: `lokal/a07b/arten.py`.

## Abweichungen vom Auftrag

1. **`+=`, `++` und `--` lesen auch.** Sie ergeben eine Kante zu `<set-x>` und, falls es einen
   eigenen Getter gibt, zu `<get-x>`. So läuft Kotlin sie ab (Getter, dann Setter).
2. **`!!` und Klammern sind durchsichtig.** Der Beleg nennt die Herkunft des Inneren
   (`atelier!!.f()` → `parameter`), nicht `cast`. `!!` fügt keinen Typ hinzu. Ketten dürfen auch `?.`
   enthalten (`a?.b.f()`); das war in A07 ein unbekannter Empfänger.
3. **`val x = Klasse(…)` bleibt wie in A07** (Herkunft `lokal` bzw. `eigenschaft`). `initialisierer`
   zählt nur die neuen Fälle. So sind die Zahlen mit A07 vergleichbar.
4. **Konstruktor-Ergebnis:**
   - Die Klasse steht auch fest, wenn nur die Überladung des Konstruktors offen ist.
   - Ein externer großgeschriebener Aufruf ohne Empfänger gilt als externer Typ. Das ist dieselbe
     Regel wie bei `val x = Klasse()` in A07.
   - Ein externer Typ führt nur zu Erweiterungen oder „extern“, nie zu einer sicheren internen Kante.
5. **Primärer Konstruktor mit nur Zugriffen.**
   - Haben die Initialisierer einer Klasse keine Aufrufe, aber Zugriffe, entsteht `<init>`, sobald
     ein Zugriff eine Kante ergibt oder ein Aufruf ihn trifft. Sonst ginge die Kante verloren.
   - Er trägt dann wie in A07 keinen Oberklassen-Aufruf.
   - An Sketchorus ändert das die Zahl der Funktionsknoten nicht.
6. **`eigenschaften` auch als Datei-Feld** für die oberste Ebene, weil `by lazy` dort häufig ist. Die
   Strukturansicht entfernt das Feld wie die anderen Felder der Funktionsebene.
7. **Implizite Empfänger bei Zugriffen.** Eine Erweiterungseigenschaft eines impliziten Empfängers
   zählt nur, wenn sie sicher passt. Unsichere Erweiterungstreffer werden bei Zugriffen nicht
   weitergereicht. Das ist strenger als bei Aufrufen und erzeugt weniger unsichere Kanten.
8. **Größe:** 13,7 statt unter 8 MB. Der Auftrag sagt, dann zu berichten und nicht weiter zu kürzen.
   Die gemessenen Möglichkeiten stehen oben.

## Offene Fragen

1. **Größe von `daidalos.json`.** Die Ids sind der Hauptteil. Mögliche Wege:
   - `ruft` ohne `id` (−2,3 MB);
   - Funktionsknoten ohne `datei`;
   - kürzere Funktions-Ids, etwa ein Datei-Index statt des Pfads; das bricht das in A07 als
     endgültig erklärte Id-Schema;
   - `daidalos.json` ohne Einrückung.

   Was davon soll A09 bekommen?
2. **Unsichere Lesekanten** (321 Belege an 255 Stellen). Sie entstehen fast nur durch Namen, die
   auch externe Typen tragen (etwa `name` bei Enums), gelesen über `it` oder Lambda-Variablen. Das
   ist regelgerecht unsicher, aber laut. Soll A08 unsichere `lesen`-Kanten ganz ausblenden, oder
   sollen sie beim Lesen erst gar nicht entstehen?
3. Ein Aufruf über ein Objekt im selben Paket blieb in der Stichprobe unsicher (`unbekannter-empfaenger`),
   schon seit A07. Der Grund ist nicht untersucht. Die Kante ist unsicher, also nicht falsch.

## Nächste sinnvolle Schritte

1. **A08:** Markierungsketten über `ruft` einschließlich `lesen`/`schreiben`; delegierte
   Eigenschaften über `klassen[].eigenschaften` nennen.
2. **Typargumente einfacher Sammlungen** (`List<T>` → `it`, `for (x in liste)`) bringen am meisten
   (157 + 20 Stellen), sind aber echte Inferenz. Erst nach Entscheidung.
3. **Literaltypen bei Überladungen** (98 Stellen, `varint(0)` gegen `varint(0L)`).
4. **Größe** nach Entscheidung zu Frage 1, spätestens vor A09.
