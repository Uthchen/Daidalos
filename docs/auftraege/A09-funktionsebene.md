# Auftrag A09 – Zoomstufe Funktionen in der Karte

**Etappe:** 4 (Abschluss) · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** `main` mit A08 (`b82def6`). Branch `auftrag/a09-funktionsebene` von `main`.

## Ziel

Die vierte Zoomstufe aus der Architektur: **Funktionen**. Man öffnet eine Datei und sieht deren Klassen als Rahmen und die Funktionen darin. Dazu kommen die Aufrufe hinein und hinaus. Von jeder Funktion aus lässt sich der Wirkungsweg vorwärts und rückwärts aufklappen. Markierung, Grenzkanten und detekt-Funde sind dort sichtbar, wo sie entstehen.

Die ganze Funktionsebene (an Sketchorus 3 700 Funktionen) wird **nie** auf einmal gezeichnet. Sie ist eine **Fokus-Ansicht**.

## Entscheidungen der Leitung zu A08

1. Die Ketten an Sketchorus sind kurz. Die Seitenleiste bleibt die Hauptdarstellung der Kette. Auf der Funktionsebene werden Grenzkanten nur hervorgehoben (Schritt 3), eine eigene Kettenansicht gibt es nicht.
2. `ziele.toml` bekommt je Ziel `umgebung = { JAVA_HOME = "…" }` (Schritt 6). Die Datei ist lokal, also unbedenklich.
3. „detekt brach ab“ gegen „Build brach ab“ zu unterscheiden, ist Sache von Gradle. Das Init-Skript in `lokal/` bleibt.

## Schritte

### 1. Daten für die Karte

- `render` bettet die Funktionsebene **zusätzlich** ein, in einem eigenen `<script type="application/json" id="funktionen">`-Block. Dieser Block wird erst beim ersten Öffnen der Funktionsebene geparst. Die Startzeit der Karte darf nicht messbar steigen; vorher/nachher messen.
- Das Format ist kompakt und nur für die Karte gedacht (`daidalos.json` bleibt unverändert):
  - eine Tabelle der Dateipfade,
  - eine Funktionstabelle als Felder-Arrays mit Indizes statt Id-Texten,
  - Kanten als `[von, nach, art, sicher, gewicht, ersteZeile]`.

  Im Datenformat-Kapitel „karte.html“ beschreiben.
- Von den Belegen nur die erste Zeile je Kante; die volle Liste steht in `daidalos.json`.
- Größe von `karte.html` an Sketchorus vorher/nachher berichten. **Ziel: höchstens +3 MB.** Wird es mehr, zuerst prüfen, ob Testcode-Funktionen nur bei „mit Tests“ eingebettet werden können.

### 2. Funktionsansicht einer Datei

- **Einstieg:**
  - Doppelklick auf eine Datei der Dateiebene;
  - Knopf „Funktionen“ in deren Seitenleiste;
  - Ebenenwahl „Funktionen“, die die zuletzt gewählte Datei öffnet und sonst um eine Datei bittet;
  - Sprungadresse `#funktion=<id>` bzw. `#datei-funktionen=<pfad>`.
- **Gezeigt wird:**
  - die gewählte Datei mit ihren Klassen, Objekten und Companions als verschachtelte Rahmen und den Funktionen als Kästen. Funktionen der obersten Ebene liegen direkt im Dateirahmen.
  - **Nachbarn:** alle Funktionen anderer Dateien, die von hier aus gerufen werden oder hierher rufen. Sie stehen in eingeklappten Dateirahmen, einer je fremder Datei, und nur mit den beteiligten Funktionen. Aufrufer stehen links, Gerufene rechts (ELK layered, Richtung rechts).
  - Kanten `ruft` (sicher durchgezogen, unsicher gestrichelt), mit Gewicht ab 2. `lesen`/`schreiben` als eigene, dünnere Linienart. `ueberschreibt` und `actual` gepunktet.
- **Kasten einer Funktion:**
  - Name mit Stelligkeit und Komplexität als kleine Zahl;
  - Zeichen für `markiert` (Schild) und `ausnahme`;
  - `ohne_koerper` blass;
  - ein Punkt, wenn ein detekt-Fund dort hängt (nur bei eingeschaltetem „detekt“).
- **Grenze:** Mehr als 150 Kästen → Nachbardateien mit den meisten Funktionen werden zu „Datei (+N)“ zusammengefasst, bis es passt. Ein Klick klappt einzeln auf.
- Ein Schalter „Lesezugriffe“ (aus) blendet `lesen`/`schreiben` ein. Ein Schalter „unsicher“ (an) blendet unsichere Kanten ein.
- **Schlösser und gemerkte Positionen** wie auf den anderen Ebenen, mit Schlüssel je Datei.
- **Fokus** beim Klick auf eine Funktion wie auf den anderen Ebenen (75/40/14 % bzw. 82/50/22 %).

### 3. Markierung und Befunde auf der Funktionsebene

- Grenzkanten `markierung-verlassen` werden als Kante in der Befundfarbe der Markierung gezeichnet. Ihr Ziel bekommt einen Rand in derselben Farbe.
- Ein Klick auf einen Markierungsbefund in der Befundliste (oder auf der Dateiebene) bietet „Auf Funktionsebene zeigen“. Das öffnet die Datei von `von` mit gewählter Grenzkante.
- Funktionen in Zyklen werden nicht eigens behandelt, weil die Zyklen auf Datei-, Paket- und Modulebene gemessen sind.

### 4. Wirkungsweg vorwärts und rückwärts

- In der Seitenleiste einer Funktion gibt es zwei Knöpfe: „Wirkungsweg vorwärts“ und „rückwärts“, dazu eine Tiefe (1–5, Standard 3).
- Die Ansicht wechselt dann in einen **Wegmodus**: Nur die gewählte Funktion und alle in dieser Tiefe erreichbaren Funktionen sind zu sehen, gruppiert in ihre Dateirahmen. Die Spalten richten sich nach dem Abstand (ELK layered mit Schicht = Tiefe).
- Es gelten dieselben Regeln wie bei `daidalos aufrufe`:
  - ohne Wiederholungen;
  - standardmäßig nur sichere Kanten, mit „unsicher“ auch unsichere;
  - `ueberschreibt` wird wie in A08 gefolgt;
  - Lesezugriffe nur mit dem Schalter.
- Ab 150 Kästen wird die Tiefe gekürzt, und eine Zeile nennt, wie viel fehlt.
- Die Zählzeile zeigt: erreichte Funktionen, Dateien, davon markiert/unmarkiert.
- Sprungadresse `#funktion=<id>&weg=vor|rueck&tiefe=N`.
- „Zurück zur Datei“ verlässt den Wegmodus.

### 5. Seitenleiste einer Funktion

Die Seitenleiste zeigt:

- Signatur (Name, Parametertypen, Modifikatoren, Sichtbarkeit), Datei:Zeile von bis, Editor-Link.
- Annotationen mit vollem Namen; `markiert` mit Träger (Funktion/Klasse/Datei); `ausnahme`.
- Metriken: Zeilen, Komplexität, Fan-in/out (sicher und mit unsicheren), externe Aufrufe, delegiert gelesen.
- Listen „Gerufen von“ und „Ruft“, klickbar, je Eintrag Datei:Zeile des Aufrufs und Herkunft. Unsichere sind gekennzeichnet, mit Grund und mit den anderen Kandidaten.
- Befunde an dieser Funktion: Markierung und detekt.
- Die Beschreibung aus `deutung.json`, falls vorhanden (siehe 7).

### 6. Kleinigkeiten

- `ziele.toml`: `umgebung` je Ziel (Tabelle Text → Text). Gilt für den detekt-Befehl, nicht für den Scan. Es gibt keine Variablen-Ersetzung.
- `docs/datenformat.md`: Die Funktionsebene ist ab hier **nicht mehr vorläufig**. Vermerk „endgültig seit A09“. Danach gilt wieder Leitplanke 6.
- „Warum hängt“ in der Karte nimmt auch Funktionsnamen (Suchbegriffe wie bei `daidalos pfad`). Bei zwei Funktionen öffnet der Weg im Wegmodus.

### 7. Skill: Funktionen beschreiben (klein)

- In der Zusammenfassung kommt ein Abschnitt „Wichtige Funktionen“ hinzu. Er enthält die 20 produktiven Funktionen mit dem höchsten Fan-in (sicher) und alle `von`-Funktionen von Grenzkanten, höchstens 40 insgesamt.
- Diese Funktionen brauchen eine Beschreibung in einem Satz. Hash und Abgleich laufen wie bei Dateien, über den `hash` des Funktionsknotens.
- `SKILL.md`: kurz, woher der Satz kommt (Körper der Funktion lesen; das Arbeitsblatt der Datei nennt Zeilen).
- `deutung pruefen` meldet fehlende oder veraltete Funktionsbeschreibungen wie bei Dateien.

## Tests

- Browser-Probe an `mini_aufrufe` und `mini_markierung`:
  - Funktionsansicht öffnet per Doppelklick;
  - Klassen als Rahmen;
  - Nachbarn links und rechts;
  - Grenze 150 mit Zusammenfassung (an einer im Test erzeugten großen Datei);
  - Wirkungsweg vorwärts Tiefe 2 zeigt genau die erwarteten Funktionen;
  - rückwärts ebenso;
  - Schalter „Lesezugriffe“ und „unsicher“;
  - Grenzkante hervorgehoben;
  - Sprungadressen;
  - Positionen gemerkt;
  - Fokus-Zoom ≥ lesbar.
- Startzeit der Karte mit und ohne Funktionsblock als Test mit Toleranz. Messung über `performance.now()` bis „bereit“.
- Golden-Dateien und Zusammenfassung mit „Wichtige Funktionen“.

## Probe an Sketchorus

- **Abläufe:** Klon auffrischen, Skill laufen lassen, bis `pruefen` 0 meldet (Zeit und Zahl neuer Funktionsbeschreibungen berichten).
- **Zu berichten:**
  - Größe von `karte.html` und Startzeit vorher/nachher;
  - Zeit zum Öffnen der Funktionsansicht der größten Datei und eines Wirkungswegs Tiefe 3 vom am stärksten markierten Einstieg.

  Ziel jeweils < 1 s.
- **Bildschirmfotos nach `lokal/`:**
  - `A09-datei.png`: Funktionsansicht einer Strichpfad-Datei mit Markierungen;
  - `A09-weg.png`: Wirkungsweg vorwärts;
  - `A09-grenze.png`: Grenzkante hervorgehoben;
  - `A09-seitenleiste.png`.
- **Selbst lesen:** Claude Code öffnet drei Funktionsansichten und beurteilt im Bericht in wenigen Sätzen, ob man daraus versteht, was die Datei tut. Das ist der Maßstab für die Ebene.

## Abschluss

- Branch pushen, nicht mergen.
- Bericht `docs/auftraege/A09-bericht.md`.
- Antwort an mich mit höchstens 8 Zeilen.
- Keine Sketchorus-Inhalte im Repo.

Mit A09 ist Etappe 4 abgeschlossen.
