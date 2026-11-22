# Auftrag A06 – Skill v1: Daidalos deutet

**Etappe:** 3, dritter Teil · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Voraussetzung:** A05b ist nach `main` gemergt. Branch `auftrag/a06-skill` von `main`.

## Ziel

Der Claude-Skill `daidalos` macht aus den Messungen eine Karte mit Bedeutung. Er benennt Bereiche, beschreibt Module, Pakete und wichtige Dateien in je einem Satz, gewichtet die Befunde mit Begründung und Vorschlag und schreibt das alles in `deutung.json`. Danach ruft er `daidalos render` auf. Beim nächsten Lauf deutet er nur, was sich geändert hat.

Dafür bekommt das Programm drei Hilfen, damit der Skill wenig lesen muss und keine Hashes abschreiben muss: `daidalos zusammenfassung`, `daidalos arbeitsblatt` und `daidalos deutung`.

Lies vorher `docs/architektur.md`, Abschnitt „Der Skill“, und in `docs/datenformat.md` das Format von `deutung.json`. Als Vorbild für Arbeitsblätter dient Floorplan (`E:\Repositories\floorplan`, `skills/` und `tools/describe.mjs`). Die Bewertung aus A01 (`lokal/A01-floorplan-bewertung.md`) nennt, was davon gut war: „defines / uses / used by / named in“ und die erste KDoc-Zeile je Datei.

## Teil 0 – Vorab aus der Prüfung von A05b

1. **Mindestzoom nach Schriftgröße.** Beim Fokus-Zoom 0,6 sind Dateinamen auf Sketchorus nur etwa 6 px hoch. Ersetze die feste 0,6 durch den Zoom, bei dem Dateinamen mindestens 11 px groß dargestellt werden. Den Wert aus der Schriftgröße der Datei-Kästen ableiten und in der Konstante dokumentieren. Behälter wie bisher.
2. **Wackelnder Test stabilisieren.** `test_editor_link_aus_file_seite`: auf das Ende des Zeichnens und eine sichtbare Position des Knotens warten, statt auf feste Zeiten zu bauen. Den Test zehnmal hintereinander laufen lassen, alle grün.

## Teil 1 – Programmhilfen

### 1.1 `daidalos zusammenfassung`

```
daidalos zusammenfassung [ZIEL] [--daten DATEI] [--deutung DATEI]
```

Markdown auf stdout, kurz genug für den Kontext des Skills (Ziel: unter 300 Zeilen bei Sketchorus). Inhalt:
- Projekt, Commit, Zahlen.
- Module und Ordner als Tabelle mit Dateien, Zeilen, Fan-in, Fan-out und Gradle-Abhängigkeiten.
- Pakete je Modul mit Dateien und Fan-in/Fan-out.
- **Wichtige Dateien:** produktive, nicht fremde Dateien, die mindestens eines erfüllen: unter den 30 mit dem höchsten Fan-in, Mitglied eines Befunds, Einstieg oder Trennstelle eines Zyklus, Träger einer JNI-Kante oder einer modulübergreifenden Kante mit Gewicht ≥ 3. Mit Id, Zeilen, Fan-in, Fan-out und Grund der Aufnahme.
- Befunde mit Id, kurz.
- **Offen:** Knoten aus Modulen, Paketen und wichtigen Dateien ohne Beschreibung oder mit veralteter Beschreibung (Hash weicht ab). Befunde ohne Einschätzung. Tote Verweise in `deutung.json`.
- `--json` gibt dasselbe maschinenlesbar aus.

Welche Dateien „wichtig“ sind, ist eine Auswahlregel und keine Deutung. Sie gehört deshalb ins Programm und wird in `docs/datenformat.md` (Abschnitt Zusammenfassung) beschrieben.

### 1.2 `daidalos arbeitsblatt`

```
daidalos arbeitsblatt KNOTEN [ZIEL] [--daten DATEI]
```

Für ein Modul, ein Paket oder eine Datei ein Arbeitsblatt in Markdown, wie bei Floorplan. Das Programm liest dafür die betroffenen Dateien **neu** mit dem Kotlin-Adapter. In `daidalos.json` kommt dadurch nichts dazu.
- Je Datei: Pfad, Zeilen, Quellsatz, **deklariert** (Top-Level-Klassen, Objekte, Funktionen), **erste KDoc-Zeile** jeder Top-Level-Deklaration bzw. der Datei, **nutzt** und **genutzt von** (mit Gewicht und den ersten Belegen), **ADR-Nummern** in Kommentaren (`ADR-\d{4}`, nur gezählt und aufgelistet, die Verknüpfung kommt in Etappe 6).
- Für Modul oder Paket: die Dateien, nach Fan-in sortiert, und die Kanten nach außen verdichtet.
- **Größe begrenzen:** höchstens etwa 400 Zeilen. Bei größeren Modulen nur die wichtigen Dateien voll, die übrigen als eine Zeile. Der Rest kommt über ein Arbeitsblatt je Paket.
- Für C-Dateien und andere Sprachen ohne Adapter: Pfad, Zeilen, Kanten, kein „deklariert“.

### 1.3 `daidalos deutung`

```
daidalos deutung uebernehmen ENTWURF.json [ZIEL]
daidalos deutung pruefen [ZIEL]
```

- **`uebernehmen`:** liest einen Entwurf im Format von `deutung.json`, aber **ohne** `hash`-Felder. Für jede Beschreibung setzt es den aktuellen Hash des Knotens aus `daidalos.json` ein, prüft alle Ids (Knoten, Befunde, Kanten) und führt den Entwurf mit der bestehenden `deutung.json` zusammen. Einträge aus dem Entwurf ersetzen gleichnamige, alles andere bleibt. Unbekannte Ids führen zu Exit-Code 2 mit Liste, und nichts wird geschrieben. Ausgabe sortiert und deterministisch wie `daidalos.json`.
- **`pruefen`:** meldet veraltete Beschreibungen, tote Verweise und Befunde ohne Einschätzung. Exit-Code 0, wenn alles aktuell ist, sonst 1, damit es sich in Skripten nutzen lässt.
- Leitplanke 1 bleibt gewahrt: Den Inhalt schreibt der Skill. Das Programm setzt nur Hashes ein, prüft und speichert. In `CLAUDE.md` und `docs/architektur.md` so festhalten.

## Teil 2 – Der Skill

### 2.1 Ablage und Installation

- `skills/daidalos/SKILL.md` im Repo, dazu bei Bedarf `skills/daidalos/vorlagen/` (z. B. ein Beispiel-Entwurf).
- Als Claude-Code-Plugin installierbar: `.claude-plugin/plugin.json` und `.claude-plugin/marketplace.json`, sodass Manu in einem anderen Repo `/plugin marketplace add Uthchen/Daidalos` und `/plugin install daidalos` ausführen kann. Schau dir an, wie Floorplan das macht (`.claude-plugin/` dort), und prüfe das Format gegen die aktuelle Claude-Code-Dokumentation.
- Das Programm muss im Zielrepo aufrufbar sein. Der Skill prüft zuerst `daidalos --version`. Fehlt es, nennt er die Installation: `uv tool install git+https://github.com/Uthchen/Daidalos` bzw. für die Entwicklung `uv tool install -e E:\Repositories\Daidalos`. In der README beschreiben.

### 2.2 Inhalt von `SKILL.md`

Deutsch, knapp, mit klarer Beschreibung, wann der Skill greift (etwa „Karte erstellen“, „Codebase-Karte aktualisieren“, „daidalos“, „was hängt woran“). Ablauf:

1. `daidalos scan` im Zielrepo, dann `daidalos zusammenfassung`.
2. Nur was unter **Offen** steht, wird gedeutet. Beim ersten Lauf ist das alles.
3. Für jedes offene Modul ein `daidalos arbeitsblatt`, bei Bedarf je Paket. Dazu **gezielt** Code lesen: die Dateien, die das Arbeitsblatt als wichtig zeigt, und bei Zyklen und Befunden genau die Belegzeilen. ADRs lesen, wenn das Arbeitsblatt Nummern nennt und die Frage es braucht.
4. **Bereiche** benennen: Gruppen von Paketen oder Dateien, die zusammen eine Aufgabe erfüllen (z. B. „Zeichen-Pipeline“). 3 bis 8 Bereiche, jeder mit Name, einem Satz und seinen Knoten.
5. **Beschreibungen:** je Modul, Paket und wichtiger Datei **ein** Satz in einfacher Sprache. Er sagt, wofür das Teil da ist, nicht wie es heißt.
6. **Einschätzungen:** 3 bis 10 Befunde nach Priorität, je mit Titel, Begründung und konkretem Vorschlag. Die Priorität richtet sich nach Wirkung (wie viele Teile betroffen sind, Strichpfad oder nicht) und Aufwand (Trennstelle mit Gewicht 1 ist billig).
7. **Kanten-Texte** nur dort, wo es etwas zu sagen gibt: Trennstellen, überraschende Modulkanten, JNI-Brücken.
8. Entwurf als Datei schreiben, dann `daidalos deutung uebernehmen`, dann `daidalos deutung pruefen`, dann `daidalos render`.
9. Kurz berichten: was neu gedeutet wurde, die drei wichtigsten Einschätzungen, wo die Karte liegt.

**Feste Regeln im Skill:**
- Keine Zahl erfinden. Zahlen kommen aus der Messung und dürfen in Texten nur zitiert werden.
- Über Code, den der Skill nicht gelesen hat, schreibt er nichts. Im Zweifel lieber kürzer.
- Jede Aussage hängt an einer Id. Die Struktur von `deutung.json` erzwingt das.
- Leser sind menschliche Entwickler. Die Sprache ist Deutsch, schlicht, ohne Marketing.
- Fragen wie „Warum hängt X an Y?“ beantwortet der Skill mit `daidalos pfad` und verlinkt die Sprungadresse in `karte.html`.
- Der Skill schreibt nur in `docs/daidalos/` des Zielrepos und committet nicht selbst.

## Teil 3 – Tests

- Python: `zusammenfassung` (Golden je Beispiel, Auswahlregel für wichtige Dateien, Abschnitt Offen mit veralteter Beschreibung), `arbeitsblatt` (Golden, Größenbegrenzung, Datei ohne Adapter), `deutung uebernehmen` (Hash eingesetzt, Zusammenführung, unbekannte Id bricht ohne Schreiben ab, Determinismus), `deutung pruefen` (Exit-Codes).
- Ein Test, der prüft, dass `SKILL.md` nur Befehle nennt, die es im CLI gibt (aus der `argparse`-Hilfe gelesen).
- Plugin-Dateien sind gültiges JSON mit den Pflichtfeldern.

## Teil 4 – Probe an Sketchorus (nur lokal)

- Den Skill selbst ausführen, also als Claude Code den Ablauf aus `SKILL.md` Schritt für Schritt befolgen, auf der eingefrorenen Kopie, mit Ausgabe nach `lokal\sketchorus\`. So zeigt sich, ob die Anleitung ausreicht. Was in `SKILL.md` gefehlt hat oder missverständlich war, dort nachbessern und im Bericht nennen.
- Zeit, gelesene Dateien und die Größe von Zusammenfassung und Arbeitsblättern im Bericht festhalten.
- Danach einen zweiten Lauf ohne Änderung: Es darf nichts offen sein, und `deutung pruefen` meldet 0.
- Dann eine Datei in der Kopie geringfügig ändern, neu scannen: Genau diese Datei und ihre Gruppen (Paket, Modul) stehen unter Offen.
- Die Karte mit Deutung rendern. Bildschirmfotos nach `lokal\A06-*.png`: Seitenleiste mit Beschreibung, Befunde mit Einschätzung, Bereiche, Kante mit Deutungstext.
- `lokal\sketchorus\deutung.json` und `KARTE.md` bleiben lokal. Die Leitung liest sie dort.

## Abschluss

- Branch `auftrag/a06-skill`, pushen, nicht mergen.
- Bericht `docs/auftraege/A06-bericht.md`.
- Antwort an mich mit höchstens 10 Zeilen.

## Abnahmekriterien

- [ ] CI grün, Browser-Probe zehnmal stabil.
- [ ] Zusammenfassung für Sketchorus unter 300 Zeilen, Arbeitsblätter unter etwa 400 Zeilen.
- [ ] `deutung uebernehmen` schreibt deterministisch und weist unbekannte Ids ab.
- [ ] Sketchorus-Probe: alle Module, Pakete und wichtigen Dateien beschrieben, 3 bis 10 Einschätzungen, zweiter Lauf ohne Offenes, gezielte Änderung erzeugt genau die erwarteten offenen Knoten.
- [ ] Plugin lässt sich in einem anderen Repo installieren (lokal mit dem Plugin-Befehl ausprobiert).

## Nicht in diesem Auftrag

Führungen (Etappe 5), Bereiche als Kartenebene, ADR-Verknüpfung (Etappe 6), Live-Steuerung (Etappe 7). Die Karte in Sketchorus selbst ablegen und committen ist ein eigener Schritt nach Manus Freigabe.
