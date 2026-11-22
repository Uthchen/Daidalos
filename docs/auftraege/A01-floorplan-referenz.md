# Auftrag A01 – Referenzlauf Floorplan auf Sketchorus und Steckbrief

**Etappe:** 1 (Referenz) · **Ausführen in:** Claude Code, gestartet in `E:\Repositories\Daidalos` · **Dauer:** kurz

## Ziel

Zwei Dinge, die die nächsten Aufträge brauchen:
1. Sehen, was das Original Floorplan auf Sketchorus liefert und wo es zu kurz greift (Referenz für Daidalos).
2. Einen **Steckbrief von Sketchorus** mit den Fakten, die der Scanner und der Gradle-Adapter in A02/A03 richtig behandeln müssen.

## Wichtig vorab

- Das Daidalos-Repo ist **öffentlich**. Nichts aus Sketchorus (Code, Dateilisten, Floorplan-Ausgaben, Steckbrief) wird in Daidalos committet. Alles aus diesem Auftrag kommt in den Ordner `lokal/` im Daidalos-Repo; lege dazu eine `.gitignore` mit der Zeile `lokal/` an und committe nur diese `.gitignore`.
- Sketchorus wird **nicht verändert**. Kein Commit, kein Branch, keine neuen Dateien, die liegen bleiben. Falls Floorplan Ausgaben ins Zielrepo schreibt, verschiebe sie danach nach `lokal/floorplan-ausgabe/` und prüfe mit `git -C E:\Repositories\Sketchorus status --porcelain`, dass Sketchorus so sauber ist wie vorher. Notiere den Status **vor** dem Lauf, damit du vergleichen kannst.
- Sketchorus' eigene `CLAUDE.md` gilt für Arbeit in Sketchorus. Lies sie vorher und halte dich daran.

## Schritte

### 1. Floorplan laufen lassen
- Floorplan liegt in `E:\Repositories\floorplan`. Lies dort README und die Skill-Beschreibung unter `skills/` und finde heraus, wie man es auf ein fremdes Repo anwendet (Skripte unter `tools/`, Node, keine Abhängigkeiten).
- Führe es auf `E:\Repositories\Sketchorus` aus, so wie es gedacht ist, einschließlich des Deutungsteils, den Floorplan von Claude erwartet. Wenn das Original Ausschlüsse kennt, schließe `.claude/worktrees/`, `build/` und `docs/prototypen/daten/` aus. Falls nicht, notiere, wie sehr die Worktree-Kopien das Ergebnis verfälschen.
- Miss die Laufzeit der Skripte.

### 2. Bewerten
Schreibe `lokal/A01-floorplan-bewertung.md` mit kurzen Antworten:
- Was zeigt Floorplan zu Sketchorus? Erkennt es die Gradle-Module? Zeigt es Abhängigkeiten zwischen Kotlin-Dateien? Wie viele Dateien und Kanten?
- Was ist brauchbar und sollten wir übernehmen (Darstellung, Texte, Bedienung)?
- Was fehlt oder ist falsch? Denk an Modulgrenzen, Pakete, Zyklen, @Strichpfad/@Deterministisch, ADRs, JNI.
- Zwei, drei Bildschirmfotos der Floorplan-Ausgabe nach `lokal/`.

### 3. Steckbrief Sketchorus
Schreibe `lokal/A01-steckbrief-sketchorus.md`. Nur Fakten, mit Zahlen, je Punkt ein kurzes Beispiel (Code-Ausschnitte höchstens wenige Zeilen):
1. **Module:** Inhalt von `settings.gradle.kts` (welche `include(...)`-Schreibweise, gibt es `projectDir`-Umbiegungen, verschachtelte Pfade, `includeBuild`?).
2. **Abhängigkeiten zwischen Modulen:** Wie stehen sie in den `build.gradle.kts`? `project(":core")`, typsichere Accessoren wie `projects.core`, Version Catalogs, `api`/`implementation`/`testImplementation`/`compileOnly`/sonstige Konfigurationen? Liste je Modul alle Projekt-Abhängigkeiten mit Konfiguration.
3. **Quellordner:** Welche Source-Sets gibt es (`src/main/kotlin`, `src/main/java`, `src/test`, `src/androidTest`, eigene)? Wo liegen die `.kt`-Dateien pro Modul? Gibt es `.kt` außerhalb von `src/`?
4. **Pakete:** Paket-Wurzel(n) je Modul. Gibt es denselben Paketnamen in mehreren Modulen? Weichen Paketname und Ordnerpfad irgendwo voneinander ab? Wie viele Dateien ohne `package`-Zeile?
5. **Importe:** Kommen Wildcard-Importe (`import x.y.*`) vor, Aliase (`import x.Y as Z`), Top-Level-Funktionen, Erweiterungsfunktionen im Import? Grobe Zählung.
6. **Dateien nach Endung:** Anzahl und Zeilen je Endung (`git ls-files` als Grundlage, ohne die drei Ausschlüsse), dazu Größe von `.claude/worktrees/` in Dateien.
7. **Git:** Ist `.claude/worktrees/` in `.gitignore`? Was liefert `git ls-files --others --exclude-standard` für die Worktree-Ordner (einzelne Dateien oder nur den Ordner)? Line-Endings: `core.autocrlf`, `.gitattributes`?
8. **Native Teile:** wo liegt C/C++-Code (CMake? `externalNativeBuild`?), wie viele `external fun`.
9. **detekt:** Liegen gerade SARIF-Dateien unter `*/build/reports/detekt/`? Pfade und Größe, keine Inhalte nötig.
10. **Markierungen:** Wie sind `@Strichpfad`, `@Deterministisch`, `@WeckenOhneDaten`, `@MessWarten` definiert (voller Name der Annotation-Klasse) und wie oft werden sie verwendet, getrennt nach Datei-, Klassen- und Funktionsebene?

### 4. Abschluss
- Nur `.gitignore` committen, Branch `auftrag/a01-referenz`, pushen.
- Antworte mir am Ende mit einer Zusammenfassung von höchstens 15 Zeilen: die wichtigsten Lücken von Floorplan und die Steckbrief-Punkte, die überraschend waren. Manu gibt sie an die technische Leitung weiter, die beiden Dateien in `lokal/` ebenfalls.
