# Bericht A09 – Zoomstufe Funktionen in der Karte

Stand 2026-11-23. Branch `auftrag/a09-funktionsebene` von `main` (`b82def6`, mit A08), nicht nach
`main` gemergt.

## Was gemacht wurde

### 1. Daten für die Karte

- Neues Modul `src/daidalos/karte_funktionen.py` baut den Block
  `<script type="application/json" id="funktionen">` (vierter Datenblock in `karte.html`).
  `daidalos.json` bleibt unverändert.
- Aufbau: Texttabelle der Dateipfade, Funktionstabelle als Felder-Arrays (Spaltennamen in
  `felder`), Kanten als `[von, nach, art, sicher, gewicht, ersteZeile, herkunft, grund]` mit
  Indizes, Klassen je Datei, Bitfeld `merkmale`. Beschrieben im Datenformat-Kapitel
  „karte.html“ (Funktionsblock).
- Die Karte liest den Block erst beim ersten Öffnen der Funktionsebene (`fdaten()`); ein
  Browser-Test prüft, dass er beim Start nicht gelesen wird.
- Der Träger einer Markierung (Funktion/Klasse/Datei) wird mit derselben Regel wie in der Kette
  bestimmt; dafür ist sie aus `analysen/markierung.py` als `markierung_der_funktion` herausgezogen.
  `render` gibt dazu `[markierungen].annotationen` aus `daidalos.toml` mit.

### 2. Funktionsansicht einer Datei

- Einstieg: Doppelklick auf eine Datei der Dateiebene, Knopf „Funktionen“ in der Seitenleiste einer
  Kotlin- oder C-Datei, Ebenenwahl „Funktionen“ (zuletzt gewählte Datei, sonst Eingabefeld mit
  Vorschlägen), Sprungadressen `#datei-funktionen=<pfad>` und `#funktion=<id>`.
- Datei als Rahmen, Klassen, Objekte und Companions als verschachtelte Rahmen („Klasse X“,
  „Objekt Y“, „Companion“), Funktionen als Kästen; oberste Ebene direkt im Dateirahmen.
- Nachbarn je fremder Datei in einem eigenen Rahmen nur mit den beteiligten Funktionen; ELK
  layered, Richtung rechts. Reine Aufrufer-Dateien stehen in der Modellreihenfolge vor der Datei,
  damit sie links landen.
- Kasten: Name mit Stelligkeit, Komplexität als hochgestellte Zahl, Schild (markiert), Zeichen für
  Ausnahme, Punkt für detekt-Fund (nur mit „detekt“), `ohne_koerper` und implizite Konstruktoren
  blass gestrichelt, Schloss oben rechts.
- Kanten: `ruft` durchgezogen, unsicher gestrichelt, Gewicht ab 2 als Zahl; `lesen`/`schreiben`
  dünn und gedämpft (Schalter „Lesezugriffe“, aus); `ueberschreibt`/`actual` gepunktet; `jni`
  violett.
- Grenze 150 Kästen: Nachbardateien mit den meisten Funktionen werden zu „Datei (+N)“
  zusammengefasst, bis es passt; ein Klick klappt eine einzeln auf.
- Schlösser, gemerkte Positionen (Schlüssel `…|funktion:<pfad>`), Fokus 75/40/14 % bzw.
  82/50/22 % wie auf den anderen Ebenen; der Fokus-Zoom hält die Schrift lesbar.

### 3. Markierung und Befunde

- Grenzkanten `markierung-verlassen` in der Befundfarbe (warn), ihr Ziel mit Rand derselben Farbe;
  bleibt im Fokus erhalten. Gibt es keine direkte Kante (Grenze über `ueberschreibt`), zeichnet
  die Karte eine Ersatzkante.
- Befund-Seitenleiste: „Auf Funktionsebene zeigen“ öffnet die Datei von `von` mit gewählter
  Grenzkante (`#grenze=<befund-id>`); bei detekt-Funden an einer Funktion öffnet derselbe Knopf die
  Funktion. Funktionen in der Kette der Befund-Seitenleiste sind jetzt klickbar.

### 4. Wirkungsweg

- Knöpfe „Wirkungsweg vorwärts“ und „rückwärts“ mit Tiefe 1–5 (Standard 3) in der Seitenleiste.
- Wegmodus: Breitensuche ohne Wiederholungen; Spalte = Abstand; je Spalte und Datei ein Rahmen;
  nur Kanten von Spalte d nach d+1 zählen fürs Layout.
- Regeln: `ruft` (Lesezugriffe nur mit dem Schalter), ohne Testcode außer mit „mit Tests“,
  standardmäßig nur sicher (eigener Stand des Schalters „unsicher“ im Wegmodus). Wie in A08:
  vorwärts wird jedes erreichte Ziel um seine Überschreibungen und `actual` erweitert, rückwärts
  jede Funktion um das, was sie überschreibt, und ihr `expect` (gleiche Spalte, gepunktete Kante).
- Über 150 Kästen wird die Tiefe gekürzt; die Zählzeile nennt erreichte Funktionen, Dateien,
  markiert/unmarkiert und was fehlt. „Zurück zur Datei“ in der Zählzeile und der Seitenleiste.
- Sprungadresse `#funktion=<id>&weg=vor|rueck&tiefe=N`.

### 5. Seitenleiste einer Funktion

Signatur (Sichtbarkeit, Modifikatoren, Empfänger, Parametertypen mit `vararg` und `= …`),
Datei:Zeile von–bis mit Editor-Link, Annotationen mit vollem Namen, markiert mit Träger,
Ausnahme, Messwerte (Zeilen, Komplexität, Fan-in/out sicher und mit unsicheren, externe Aufrufe,
delegiert gelesen), „Gerufen von“ und „Ruft“ (klickbar, je Eintrag Datei:Zeile des ersten Aufrufs
mit Editor-Link, Art, Herkunft, Gewicht; unsichere mit Grund und den anderen Kandidaten),
Überschreibt/actual, Befunde an der Funktion, Beschreibung aus `deutung.json`. Ohne gewählte
Funktion zeigt die Seitenleiste die Funktionen der Datei nach Klassen und Zeile.

### 6. Kleinigkeiten

- `ziele.toml`: `umgebung = { NAME = "Wert" }` je Ziel, nur für den detekt-Befehl, ohne
  Variablen-Ersetzung; Prüfung auf Tabelle Text → Text; README.
- `docs/datenformat.md`: Funktionsebene „endgültig seit A09“, danach gilt Leitplanke 6.
- „Warum hängt“ nimmt Funktions-Ids und Suchbegriffe wie `daidalos pfad` (`Strich.zeichne`,
  `Strich.zeichne/1`); bei zwei Funktionen öffnet der kürzeste Weg im Wegmodus
  (`#ebene=funktion&von=…&nach=…`).

### 7. Skill

- Zusammenfassung: Abschnitt „Wichtige Funktionen“ (20 mit höchstem sicheren Fan-in plus alle
  `von` von Grenzkanten, höchstens 40), JSON `wichtige_funktionen`.
- `deutung pruefen` und „Offen“ melden fehlende und veraltete Funktionsbeschreibungen; Hash über
  den `hash` des Funktionsknotens. Nebenbei behoben: Die Zusammenfassung glich die Deutung gegen
  die Strukturansicht ab und hätte jede Funktionsbeschreibung als toten Verweis gemeldet.
- Arbeitsblatt einer Datei: Funktionen mit `Z. von–bis` und Vermerk „wichtig, Deutung …“.
- `SKILL.md`: der Satz kommt aus dem Körper der Funktion (Zeilen aus Zusammenfassung und
  Arbeitsblatt).

### Tests

- `tests/test_funktionsebene.py`: Funktionsblock als Golden (`mini_aufrufe`, `mini_markierung`),
  Inhalt (alle Funktionen, Bitfeld, Träger, Teilung nach Lesezugriffen ohne Gewichtsverlust), ohne
  Funktionsebene `null`, Einbettung durch `render`, Auswahlregel der wichtigen Funktionen (auch die
  Grenze 40), Zusammenfassung, Abgleich (`ok`, `veraltet`, kein toter Verweis) und
  `deutung pruefen`.
- `tests/test_browser_funktionen.py` (Browser-Probe an `mini_aufrufe` und `mini_markierung`):
  Doppelklick öffnet die Funktionsansicht, Klassen als Rahmen, Nachbarn links (nur Aufrufer) und
  rechts (nur Gerufene), Grenze 150 mit Zusammenfassung an einer im Test erzeugten Datei, die 192
  Funktionen in 20 Dateien ruft (5 Dateien „(+10)“, Klick klappt auf), Wirkungsweg vorwärts und
  rückwärts Tiefe 2 gegen eine unabhängige Breitensuche in Python (genaue Menge, Spalten nach
  Abstand, „Zurück zur Datei“), Schalter „Lesezugriffe“ und „unsicher“, Grenzkante hervorgehoben
  (Farbe, Rand am Ziel, Ersatzkante über `ueberschreibt`), Sprungadressen und Seitenleiste,
  „Warum hängt“ mit Funktionen, Positionen gemerkt (Schlüssel je Datei), Fokus-Zoom ≥ lesbar.
- Startzeit mit und ohne Funktionsblock (Block künstlich auf etwa 1 MB vergrößert; Median aus 4,
  Toleranz ×1,5 + 150 ms; außerdem: Block beim Start nicht gelesen).
- Golden-Dateien: Zusammenfassung (Markdown und JSON) und zwei Arbeitsblätter neu, zwei
  Funktionsblöcke neu. `test_ziel_auffrischen.py` prüft `umgebung` (Wert kommt ohne Ersetzung an,
  falsche Typen werden abgelehnt).
- Ergebnis: `ruff check`, `ruff format --check` grün; `pytest -m "not browser"` 301 bestanden,
  1 übersprungen; neue Browser-Probe 11 bestanden. Zur alten Browser-Probe siehe „Offene Fragen“.

## Probe an Sketchorus

Klon `b610477` (neu aufgefrischt mit `--mit-detekt`, detekt 34,2 s; `JAVA_HOME` jetzt aus
`umgebung` in `lokal/ziele.toml`). „Vorher“ ist der Code von `main` (`b82def6`) am selben Stand.

| Messgröße | vorher | nachher |
| --- | ---: | ---: |
| `karte.html` | 4 114 986 Bytes | 4 991 585 Bytes (+0,84 MiB; Ziel ≤ +3 MB) |
| davon Funktionsblock | – | ≈ 0,82 MB (3 721 Funktionen, 9 071 Kanten, 375 Dateien) |
| Start bis „bereit“, Median aus 5 | 208 ms | 215 ms |
| Funktionsansicht größte Datei (Test, 52 Funktionen, 55 Kästen) | – | 151 ms (davon Block lesen 6 ms) |
| Funktionsansicht größte produktive Datei (50 Funktionen, 109 Kästen) | – | 235 ms |
| Wirkungsweg vorwärts Tiefe 3 ab dem stärksten markierten Einstieg | – | 44 ms (23 Kästen) |

Alle Zeiten unter 1 s. Der stärkste markierte Einstieg ist eine Funktion der Darstellung mit 5 Grenzkanten.
Testcode wird immer eingebettet, weil das Ziel von 3 MB weit unterschritten ist.

Der Wirkungsweg Tiefe 3 ab diesem Einstieg erreicht 22 Funktionen in 12 Dateien (21 markiert,
1 unmarkiert). Mit „Lesezugriffe“ sind es 33 (27 markiert, 6 unmarkiert): Die fünf Grenzkanten
dieses Einstiegs sind alles Getter, also Lesezugriffe. Das passt zur Regel „Lesezugriffe nur mit dem
Schalter“; „Auf Funktionsebene zeigen“ schaltet sie für eine solche Grenzkante deshalb selbst ein.

**Skill-Lauf:** `pruefen` meldete 38 offene Punkte: 35 wichtige Funktionen (20 nach Fan-in, 15 mit
Grenzkante) und 3 veraltete Beschreibungen (Modul `core`, Ordner `docs`, Paket `pinsel`; der neue
Stand ändert dort nur Auswertungscode in `jvmTest` und Doku-Daten, die Texte blieben gleich und
wurden erneuert). 35 neue Funktionsbeschreibungen aus den gelesenen Körpern, Übernahme, danach
`deutung pruefen` mit 0. Zeit: etwa 10 Minuten für Lesen und Schreiben; auf der Uhr 57 Minuten,
weil dazwischen die hängende alte Browser-Probe untersucht wurde.

Bildschirmfotos in `lokal/`: `A09-datei.png` (eine Strichpfad-Datei, alle Funktionen markiert,
zwei Grenzkanten), `A09-weg.png`, `A09-grenze.png`, `A09-seitenleiste.png`.

**Selbst gelesen (Maßstab der Ebene):** drei Funktionsansichten (Details in `lokal/A09-selbst-gelesen.txt`, hier nur
das Urteil, keine Inhalte des Zielprojekts).

- *Eine Pinsel-Datei im Strichpfad:* Der Ablauf ist ohne Code ablesbar: wer die Datei aufruft,
  welche ihrer Funktionen nacheinander rechnen und wohin das Ergebnis geht. Die Grenzkanten fallen
  sofort auf.
- *Ein Ringpuffer-Index:* Die Ansicht zeigt eindrücklich, wofür die Klasse da ist: links rund 25
  Schreiber, die immer dieselben zwei Funktionen paarweise rufen, und Leser mit dem anderen Paar.
  Das Protokoll ist aus den Paaren ablesbar, dass es lock-frei ist, sagt erst die Beschreibung.
- *Ein Rechenbaustein der Pinsel-Pipeline:* Innere Struktur und Hilfen (Mathe, Kurven, Zufall)
  zeigen, dass die Datei aus Eingabepunkten Abdrücke rechnet; was genau gerechnet wird, steht erst
  im Code.

Urteil: Für Dateien mit klarer Rolle versteht man aus der Ansicht, *was* die Datei im Ablauf tut
und wer sie benutzt; *wie* sie es tut, nicht. Die Seitenleiste mit Beschreibung und „Ruft“ schließt
die Lücke für die wichtigen Funktionen. Gleichnamige Dateien aus verschiedenen Modulen waren in der
ersten Fassung nicht zu unterscheiden; sie tragen jetzt den Modulordner davor. Bei sehr großen
Dateien (eine Darstellung mit vielen Funktionen) bleibt die Ansicht dicht; dort hilft der Fokus.

## Abweichungen vom Auftrag

- **Kanten mit zwei Feldern mehr.** Statt `[von, nach, art, sicher, gewicht, ersteZeile]` stehen
  `herkunft` und `grund` (Indizes in einer Texttabelle) dabei. Die Seitenleiste soll je Aufruf die
  Herkunft und bei unsicheren den Grund zeigen; ohne sie ginge das nur mit der vollen Messung.
- **`ruft` wird geteilt.** Eine `ruft`-Kante, deren Belege teils Aufrufe und teils Lesezugriffe
  sind, ergibt im Block zwei Kanten, damit „Lesezugriffe“ genau die Zugriffe ausblendet.
- **„Andere Kandidaten“** einer unsicheren Kante sind die übrigen unsicheren Ziele desselben
  Aufrufers mit demselben Namen. Die Messung hält Kandidaten nicht je Aufrufstelle fest; die
  Näherung trifft den üblichen Fall `unbekannter-empfaenger`.
- **Schalter „unsicher“ mit zwei Ständen.** In der Dateiansicht an (Schritt 2), im Wegmodus aus
  (Schritt 4: standardmäßig nur sicher); jeder Modus merkt sich seinen Stand.
- **Wirkungsweg und `daidalos aufrufe`.** `aufrufe` folgt allen `ruft`-Kanten (auch Lesezugriffen)
  und keinem `ueberschreibt`. Der Auftrag verlangt für die Karte Lesezugriffe nur mit Schalter und
  `ueberschreibt` wie in A08; die Karte folgt dem Auftrag, `aufrufe` blieb unverändert. Rückwärts
  ist die A08-Regel gespiegelt.
- **Spalten = Tiefe:** je Spalte und Datei ein eigener Rahmen; nur Kanten von Spalte d nach d+1
  zählen fürs Layout. So stimmt die Spalte auch, wenn eine Datei in mehreren Tiefen vorkommt.
- **Ab 150 Kästen im Wegmodus:** Ist schon Tiefe 1 zu groß, werden die ersten 150 nach Id gezeigt.
- **Kanten der Funktionsebene haben keine eigene Sprungadresse**; Grenzkanten haben `#grenze=`.
- **Wichtige Funktionen:** Kandidaten brauchen einen `hash` (ohne implizite Konstruktoren). Bei mehr
  als 40 kommen die 20 nach Fan-in zuerst, dann Grenzkanten nach ihrer Zahl.
- **Arbeitsblatt:** zeigt `Z. von–bis` statt nur der ersten Zeile (für den Skill).

## Offene Fragen

1. **Hängende alte Browser-Probe.** `test_browser.py::test_fokus_zoom_haelt_dateinamen_lesbar`
   hängt unter Windows gelegentlich: Der Seiten-Thread antwortet nach dem Sprung aus der
   Seitenleiste nicht mehr, vermutlich ein ELK-Layout, das nicht endet. Das tritt auch auf `main`
   auf (dort 1 von 3 Einzelläufen), ist also nicht neu durch A09. Im Gesamtlauf der alten Probe hing er in 3 von 3 Läufen; ohne ihn sind die übrigen 27 alten Browser-Tests grün (20 s). Soll das ein
   eigener kleiner Auftrag werden (ELK in einem Worker oder mit Zeitgrenze)?
2. Grenzkanten über Getter: An Sketchorus sind alle Grenzkanten des stärksten Einstiegs
   Lesezugriffe. Soll der Wirkungsweg ab einem markierten Einstieg Lesezugriffe standardmäßig
   zeigen, weil die Markierungs-Kette sie mitzählt?

## Nächste sinnvolle Schritte

- Etappe 5 (Führungen) kann die Funktionsebene nutzen: `#funktion=…&weg=…` ist schon ein Schritt.
- ELK-Hänger untersuchen (Frage 1).
- Beschreibungen der wichtigen Funktionen auch in `KARTE.md`.
