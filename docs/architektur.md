# Daidalos – Architektur

Stand 2026-11-22. Quelle: Architekturplan https://claude.ai/artifact/Mhd4vGPZCBmp4xryPsEAF2 und Karten-Prototyp https://claude.ai/artifact/YYwhvAGMZX8zXf9seGAz8b. Diese Datei ist die verbindliche Fassung im Repo. Änderungen an der Architektur werden hier nachgetragen.

## Ziel

Daidalos zeichnet eine Karte, die zeigt, wie die Teile einer Codebase miteinander verflochten sind, und markiert, wo dieses Geflecht ungesund ist. Ein Mensch soll in zehn Minuten verstehen, welche Module es gibt, wer von wem abhängt, wo Zyklen und Engstellen sitzen und wo sich Arbeit lohnt.

Vorbild ist Floorplan: Messen und Deuten sind getrennt. Daidalos geht weiter bei
- **Struktur statt Größe:** Zyklen, Kopplung (Fan-in, Fan-out, Instabilität), Komplexität, Änderungshäufigkeit.
- **Mehreren Ebenen:** Gradle-Module, Pakete, Dateien, Funktionen, dazu nativer Code über JNI.
- **Projektwissen:** eigene Markierungen wie `@Strichpfad` und `@Deterministisch` sowie ADRs werden Teil der Karte.
- **Zielgruppe:** menschliche Entwickler, Ausgabe auf Deutsch.

## Gesamtbild

Zwei Schichten, die nur über Dateien miteinander reden:

```
Zielrepo ──► daidalos scan ──► docs/daidalos/daidalos.json   (Programm: nur Fakten)
                                     │
                     Skill liest Zusammenfassung + gezielt Code/ADRs
                                     ▼
                              docs/daidalos/deutung.json      (Skill: Namen, Texte, Prioritäten)
                                     │
         daidalos render ◄───────────┘
              ▼
   docs/daidalos/karte.html + KARTE.md
```

Weil Fakten und Deutung getrennt liegen, lässt sich jede Zahl nachprüfen und jede Beschreibung einzeln erneuern.

## Das Messprogramm

Eine Kette aus fünf Bausteinen, jeder mit einzeln prüf- und testbarem Zwischenergebnis.

1. **Scanner:** findet alle Dateien, erkennt die Sprache, zählt Zeilen, bildet pro Datei einen Hash. Beachtet `.gitignore` und `daidalos.toml` im Zielrepo (Ausschlüsse; für Sketchorus `.claude/worktrees/`, `build/`, `docs/prototypen/daten/`). Für Unreal sind `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/` von Haus aus ausgeschlossen.
2. **Sprach-Adapter:** je Sprache ein austauschbares Modul, das Bausteine im gemeinsamen Format meldet.
   - Kotlin/Java: Paket, Importe, Klassen, Funktionen, Aufrufe, Annotationen
   - Gradle: Module aus `settings.gradle.kts`, Abhängigkeiten aus `project(...)`-Zeilen, getrennt nach `api` und `implementation`
   - C/C++: `#include`, Klassen, Funktionen, Aufrufe, JNI-Brücke (`external fun` ↔ `Java_...`)
   - Unreal: `.uproject`, `.uplugin`, `*.Build.cs`, UCLASS/UFUNCTION/UPROPERTY
   - Blueprints: Export per `UnrealEditor-Cmd.exe Projekt.uproject -run=pythonscript` (headless, nur bei geänderten `.uasset`), ein JSON pro Blueprint; Graph-Details später per C++-Editor-Plugin
   - Verse: `.verse` mit `using`-Importen
   - Skripte in UE5-Projekten: Editor-Python, `*.Build.cs`/`*.Target.cs`, Batch/PowerShell/Shell, `Config/*.ini`; UnLua/AngelScript erst über den Rückfall-Adapter
   - Markdown: ADRs mit Nummer, Status, erwähnten Klassen/Pfaden
   - Rückfall für jede andere Sprache: Datei, Größe, git-Historie, Textverweise auf andere Dateinamen. Keine Datei bleibt unsichtbar.
3. **Auflöser:** macht aus Namen echte Verbindungen (Import → Datei, Datei → Paket → Modul, Aufruf → Funktion). Symbolverzeichnis pro Paket, weil Kotlin im selben Paket keinen Import braucht. Mehrdeutiges (Überladung, Erweiterungsfunktion, Interface) wird als **unsicher** markiert, nie geraten.
4. **Analysen** auf dem fertigen Graphen:
   - Zyklen auf jeder Ebene (Tarjan / starke Zusammenhangskomponenten)
   - Kopplung: Fan-in, Fan-out, Instabilität nach Robert C. Martin
   - Komplexität pro Funktion
   - Änderungshäufigkeit und gemeinsame Änderungen aus `git log`
   - Hotspots (oft geändert und komplex); Aufgaben einer Datei über Kohäsion (welche Funktionen dieselben Felder/Importe nutzen)
   - **Markierungs-Kette:** von jeder Funktion mit `@Strichpfad`/`@Deterministisch` den Aufrufen folgen und jede erreichte unmarkierte Funktion melden (Fund U6), ganze Kette, gruppiert pro markiertem Einstieg. Markierung an Klasse/Datei deckt deren Funktionen, nicht `init`-Blöcke und Property-Initialisierer; `@WeckenOhneDaten` und `@MessWarten` sind benannte Ausnahmen. Namen und Regeln stehen in `daidalos.toml`.
   - **Fremdbefunde:** detekt-SARIF 2.1.0 aus `<modul>/build/reports/detekt/*.sarif` einlesen und an Knoten hängen. Nur lokal nach Build vorhanden, daher Alter/Vorhandensein zeigen. Leerer Bericht = keine Verstöße.
   - **ADR-Verknüpfung:** `ADR-\d{4}` in Kommentaren = sicher; Pfade mit `...` und Klassennamen in ADRs = unscharf, mit Treffergüte.
   - Modulrichtungen nur zeigen, nicht prüfen (macht der Build).
   - Ungenutzte Dateien, Vorschlag für Bereiche (Gruppen eng verbundener Dateien).
5. **Export:** schreibt `daidalos.json`. Gleicher Code → byte-gleiches Ergebnis, damit Läufe per Git-Diff vergleichbar sind.

## Datenmodell

`daidalos.json` gehört dem Programm (nur Gemessenes), `deutung.json` gehört dem Skill (nur Benanntes). Keine Seite schreibt in die Datei der anderen.

| Objekt | Datei | Wichtigste Felder | Beispiel |
| --- | --- | --- | --- |
| Knoten | daidalos.json | id, art (modul, paket, datei, funktion, blueprint, adr), pfad, sprache, metriken, markierungen, hash | `:core`, `core/.../Strich.kt` |
| Kante | daidalos.json | von, nach, art (import, gradle-api, gradle-impl, ue-modul, ruft, jni, blueprint-ruft, gemeinsam-geaendert, adr-verweis), gewicht, sicher | `:app` → `:core`, gradle-impl |
| Befund | daidalos.json | quelle (daidalos, detekt), regel, schwere, knoten, beleg | @Strichpfad-Funktion ruft unmarkierte Funktion |
| Bereich | deutung.json | name, beschreibung, knoten | „Zeichen-Pipeline“ |
| Beschreibung | deutung.json | knoten-id, text, hash zum Zeitpunkt der Deutung | ein Satz pro Modul und Datei |
| Einschätzung | deutung.json | befund-id, prioritaet, begruendung, vorschlag | „Zyklus zuerst lösen, weil …“ |

Weicht der Hash einer Beschreibung vom aktuellen ab, deutet der Skill nur diesen Knoten neu.

## Der Skill

Er erfindet keine Zahlen, er ordnet die gemessenen ein. Ablauf: `daidalos scan` → Zusammenfassung lesen (nicht das ganze JSON) → Bereiche benennen, Module und wichtige Dateien in je einem Satz beschreiben (gezielt Code und ADRs lesen) → 3 bis 10 Befunde gewichten mit Begründung und Vorschlag → `deutung.json` schreiben → `daidalos render` → beim nächsten Lauf nur Knoten mit geändertem Hash neu deuten. Regeln: jede Aussage verweist auf eine Knoten- oder Befund-id; über ungelesenen Code wird nichts geschrieben.

Seit A06 liegt der Skill als `skills/daidalos/SKILL.md` im Repo und ist als Claude-Code-Plugin installierbar (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`). Drei Programmhilfen halten ihn knapp und frei von abgeschriebenen Hashes:

- `daidalos zusammenfassung`: Übersicht unter 300 Zeilen, wichtige Dateien nach fester Auswahlregel, Abschnitt **Offen** (fehlende und veraltete Beschreibungen, Befunde ohne Einschätzung, tote Verweise).
- `daidalos arbeitsblatt KNOTEN`: je Modul, Paket oder Datei, was deklariert ist, erste KDoc-Zeilen, nutzt / genutzt von mit Belegen, ADR-Nummern; liest die Dateien neu, ändert die Messung nicht.
- `daidalos deutung uebernehmen ENTWURF.json` und `daidalos deutung pruefen`: Der Skill schreibt einen Entwurf ohne Hashes; das Programm prüft alle Ids, setzt die aktuellen Hashes ein, führt mit der bestehenden `deutung.json` zusammen und speichert deterministisch. `pruefen` meldet Offenes mit Exit-Code 1.

**Leitplanke 1 bleibt gewahrt:** Den Inhalt der Deutung (Namen, Texte, Prioritäten) schreibt nur der Skill. Das Programm wählt nach festen Regeln aus (wichtige Dateien), setzt Hashes ein, prüft und speichert, aber es deutet nicht.

## Die Karte

Geflecht zum Hineinzoomen, Cytoscape.js eingebettet, offline, kein Netzwerk zur Laufzeit.

- **Ebenen:** Module → Bereiche/Pakete → Dateien → Funktionen. Filter nach Kantenart.
- **Überlagerungen:** Zyklen rot, ungeprüfte Ketten aus markiertem Code orange, detekt-Funde als Zeichen am Knoten, Hotspots groß, ADR-Verweise als eigene Linien.
- **Seitenleiste:** Beschreibung (Deutung), Zahlen (Messung), ADRs, Befunde. „Nutzt“/„Wird genutzt von“ klickbar, Klick springt mit Fokus dorthin.
- **Klickbare Verbindungen:** zeigen eigene Infos (genutzte Symbole mit Zeilen, Ebene der Grenze, ob einzige Verbindung, ob Wegfall einen Zyklus löst; bei gemeinsam geändert die Commit-Zahl; bei ADR den Beleg und die Sicherheit; bei Gradle-/Paket-Kanten die tragenden Datei-Importe).
- **Pfad-Suche:** „Warum hängt :app an X?“
- **Sperren:** alle Elemente standardmäßig gesperrt; Schloss je Element und global; später auch für Module, Pakete, Bereiche.
- **Fokus abgestuft:** gewählt 100 %, direkte Nachbarn / zwei Stufen / Rest: hell 75/40/14 %, dunkel 82/50/22 %. Zoom passt auf Auswahl + direkte Nachbarn.
- **Fluss-Animation:** nur auf Wunsch (Befund, Pfad-Suche, Führung, Auswahl), zwei Stufen (direkt kräftig, eine Stufe weiter langsamer/feiner; aufwärts „wer nutzt“, abwärts „worauf baut“). Kreisläufe laufen im Ring mit Einstieg und günstigster Trennstelle. `prefers-reduced-motion` respektieren.
- **Dark Mode Standard**, Umschalter Dunkel/Hell/System, kein reines Schwarz/Weiß.
- **Zoomstufe Funktionen:** Klassen als Rahmen mit Funktionen und Feldern, Kanten ruft/liest/schreibt, Ein- und Ausgaben, Wirkungsweg vorwärts/rückwärts, Aufgaben-Gruppen als Farbe. Datenfluss ist Näherung, Unsicheres markiert.
- **Vom Element zum Code:** Code-Vorschau in der Seitenleiste (live über `daidalos serve`, nie in `karte.html` eingebettet) und „Im Editor öffnen“ (Standard VS Code, `code -g datei:zeile`, ohne Server `vscode://file/...:zeile`). Symbole Code / Editor / Schloss an jedem Datei-Element, in der Code-Ansicht ein Editor-Symbol je Funktion.
- **Sprungadressen** wie `karte.html#befund-2`.

Ausgabe: `docs/daidalos/` im Zielrepo, committet: `daidalos.json`, `deutung.json`, `karte.html`, `KARTE.md`, später `fuehrungen/`.

## Führungen

Claude führt auf Zuruf durch die Karte („vom aufgelegten Stift bis zum fertigen Strich“): `daidalos pfad --von … --nach …` liefert den belegten Weg → Führung als `docs/daidalos/fuehrungen/<name>.json` (Schritte mit Ebene, Knoten, Kanten, Text) → `daidalos fuehrung pruefen` → Spieler in `karte.html` mit Weiter/Zurück/Pause und Sprachausgabe (Web Speech, Windows-Stimmen offline). Später Live-Modus über `daidalos serve` + MCP, in dem Claude die Führung jederzeit umplanen und Erkenntnisse als Befund in `deutung.json` festhalten kann. Optional später: Perfetto-Trace für echte Häufigkeiten.

## Technik

Python mit tree-sitter (eine Schnittstelle für alle Sprachen), Gradle-Dateien als Text, networkx für Graphen, Aufruf `python -m daidalos scan` bzw. `daidalos scan`. Karte mit Cytoscape.js, eingebettet.

## Fahrplan

1. Referenz: Floorplan einmal auf Sketchorus.
2. Gerüst und Modulgraph: Scanner mit `daidalos.toml`, Gradle-Adapter, Kotlin-Importe, Zyklen auf Modul- und Paketebene, `daidalos.json`.
3. Erste Karte: `karte.html` mit Modul-Geflecht, Zoom, Sprungadressen, `daidalos pfad`, Skill v1.
4. Aufrufgraph und Markierungs-Kette: Zoomstufe Funktionen (Kotlin), Markierungs-Kette, detekt-SARIF.
5. Führungen.
6. Messwerte: Komplexität, git-Historie, Hotspots, versteckte Kopplung, ADR-Verknüpfung.
7. Live-Steuerung: `daidalos serve` + MCP.
8. Nativer Code: C++-Adapter, JNI.
9. Unreal (optional).
10. Feinschliff: Rückfall-Adapter, inkrementelles Neudeuten.

## Entscheidungen

| Thema | Entscheidung |
| --- | --- |
| Sprache | Python + tree-sitter, alle Sprachen (Rückfall-Adapter) |
| Zielprojekte | Kotlin, C++, UE5; getestet zuerst nur an Sketchorus |
| Markierungen | detekt prüft Regeln; Daidalos zeigt die Kette „markiert ruft unmarkiert“ |
| Modulregeln | aus `project(...)` lesen und zeigen, Prüfung macht der Build |
| ADRs | `ADR-\d{4}` sicher, Pfade/Klassennamen unscharf |
| Ablage | `docs/daidalos/` im Zielrepo, committet |
| Leser | menschliche Entwickler |
| detekt | SARIF 2.1.0 einlesen |
| Editor | VS Code |
