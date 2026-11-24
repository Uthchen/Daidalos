# Bericht A10 – Führungen durch die Karte

Branch `auftrag/a10-fuehrungen` von `main` (`0c1bfec`). Nicht nach `main` gemergt.

## Was gemacht wurde

1. **Format** `fuehrungen/<name>.json`, `schema: 1` (`src/daidalos/fuehrung.py`, eingetragen in
   `docs/datenformat.md`): `name`, `titel`, `frage`, 3 bis 15 Schritte mit `ansicht` (Sprungadresse
   der Karte), `hervorheben` (1 bis 8 Ids), `titel`, `text`, `belege` und `hashes`.
2. **Befehle** `daidalos fuehrung uebernehmen | pruefen | liste`. `uebernehmen` prüft Ids,
   Sprungadressen (jeder Schlüssel gegen die Messung) und Belege, setzt die Hashes ein und schreibt
   deterministisch; bei Problemen Exit 2, Liste, nichts geschrieben. `pruefen` meldet je Schritt
   `veraltet` (Hash weicht ab) oder `kaputt` (Id, Datei oder Teil der Ansicht fehlt), Exit 0/1.
   Die Zusammenfassung nennt solche Führungen unter „Offen“ (Markdown und `offen.fuehrungen`).
3. **Einbettung:** `render` liest `fuehrungen/` im Ausgabeordner und bettet sie als fünften
   JSON-Block mit Stand je Schritt ein. `KARTE.md` bekommt nach dem Überblick den Abschnitt
   „Führungen“ (Titel als Link `karte.html#fuehrung=<name>`, Frage, Schritt-Titel).
4. **Spieler** in `karte.js` (Abschnitt 14): Knopf „Führungen“ (nur mit Führungen), Liste in der
   Seitenleiste, `#fuehrung=<name>[&schritt=n]`, eigene Leiste über der Seitenleiste mit Text,
   Belegen (Editor-Link), Zurück/Weiter/Ansicht/Beenden. Je Schritt: Ansicht öffnen, Kamera gleitet
   600 ms vom alten zum neuen Ausschnitt, Ids der Reihe nach im Takt von 400 ms mit Rand, alle
   bleiben stehen. Veraltet: Hinweis; kaputt: übersprungen mit Hinweis. Tastatur `→`/Leertaste,
   `←`, `Esc`. Vorlesen nur mit `localService === true` und deutscher Sprache, sonst Schalter aus
   mit Grund; „Automatisch“ (Ende + 1,5 s), „Pause“, Stimme und Tempo in `localStorage`.
5. **Skill:** zweiter Ablauf „Führung erstellen“ in `SKILL.md`, Vorlage
   `skills/daidalos/vorlagen/fuehrung-beispiel.json`; Auslöser in der `description`.
6. **Kleinigkeiten aus A09b:** „Einpassen“ im Wegmodus ruft `wegAnsicht()`; Grenzkanten haben
   `z-index` über den übrigen Kanten, damit ein gebündelter Strang die Befundfarbe trägt; Hilfe
   `js(s, ausdruck)` in `tests/conftest.py`, 19 Aufrufe in `test_browser.py` umgestellt
   (`test_browser_funktionen.py` hatte keine ohne genutzten Wert).

**Tests:** `tests/test_fuehrung.py` (22: Übernehmen mit Hashes, Golden
`tests/erwartet/mini_aufrufe.fuehrung.json`, Determinismus, 11 Fehlerfälle mit Exit 2 ohne
Schreiben, Sprungadressen, `pruefen` ok/veraltet/kaputt, `liste`, Zusammenfassung, Einbettung,
`KARTE.md`), `tests/test_browser_fuehrung.py` (10: Liste und Start, Weiter/Zurück/Tastatur,
Ansichtswechsel, Kamera, Reihenfolge und Takt der Hervorhebung, veraltet, kaputt übersprungen,
`&schritt=`, Vorlesen mit Attrappe: nur lokale Stimme, ohne lokale Stimme aus, Automatisch, Pause,
gemerkte Werte), 2 neue Proben in `test_browser_funktionen.py`, `test_skill` für den neuen Ablauf.
Stand: `ruff check`, `ruff format --check`, `pytest`: 384 bestanden, 1 übersprungen.

## Abweichungen vom Auftrag, mit Grund

- **`belege` ist Pflicht (mindestens einer).** Der Auftrag verlangt „je Schritt ein Beleg“ vom
  Skill; das Programm prüft es mit, und dazu, dass die Zeile in der Datei liegt.
- **Ablage neben der Karte:** `render` liest Führungen aus `<ausgabe>/fuehrungen/`, die
  Zusammenfassung aus `fuehrungen/` neben `--deutung`, `fuehrung …` aus `--ausgabe` (Standard
  `<ZIEL>/docs/daidalos/`). So liegen sie bei Sketchorus wie gewünscht in
  `lokal/ziele/sketchorus/daidalos/fuehrungen/`.
- **`fuehrung pruefen [NAME] [ZIEL]`:** Zwei optionale Stellen sind mehrdeutig. Ein einzelner Wert
  gilt als `ZIEL`, wenn er ein Ordner ist oder kein gültiger Name sein kann, sonst als `NAME`.
- **Fokus beim Hervorheben:** Die Ansicht des Schritts setzt ihren eigenen Fokus (wie bei einer
  Auswahl); die Führung blendet nichts zusätzlich ab, sondern holt die hervorgehobenen Elemente aus
  der Blässe und passt die Kamera an, wenn eines außerhalb liegt. Ids, die eine Ansicht nicht
  zeigt, nennt die Leiste („In dieser Ansicht nicht zu sehen“), statt sie still zu übergehen.
- **Knopf „Ansicht“** zusätzlich zu Weiter: stellt die Ansicht des aktuellen Schritts wieder her,
  wenn man unterwegs selbst geklickt hat.
- **Adresse während der Führung:** bleibt `#fuehrung=…&schritt=n`, auch wenn der Nutzer etwas
  auswählt (sonst wäre der Schritt aus der Adresse verschwunden). Der Einstieg ist ein Eintrag im
  Verlauf; „Zurück“ im Browser beendet die Führung.
- **`js()` stellt `void (…)` voran**, mit Klammern; nackte Zuweisungen (`void a = b`) wären sonst
  ungültig. Zwei Aufrufe mit `;` laufen jetzt mit Komma.
- Nebenbei: Der Satz „Die Karte zeigt Funktionen noch nicht“ im Skill war seit A09 falsch und ist
  ersetzt.

## Probe an Sketchorus

Klon mit `ziel_auffrischen.py sketchorus` aufgefrischt, dann nach dem neuen Ablauf:
Zusammenfassung, ein Arbeitsblatt, `daidalos aufrufe` an zwei Stellen, `daidalos markierung`,
Code gelesen. Inhalte des Projekts stehen nur unter `lokal/`.

| | Stift bis Strich | Markierungs-Kette |
| --- | --- | --- |
| Schritte | 11 | 6 |
| `fuehrung pruefen` | 0 (ok) | 0 (ok) |

- **Zeit:** laut Uhr der Maschine (`date`) vom Start des Auffrischens bis `pruefen` mit Exit 0 etwa
  3 Minuten, mit einer Nachbesserung 3,5 Minuten, Lesen und Schreiben eingeschlossen.
- **Gelesene Funktionskörper:** 29 (21 für den Weg Eingabe → Kern-Thread → Ring → Darstellung,
  8 für die Grenzkanten der Markierung), dazu die KDoc der beiden Markierungs-Annotationen.
- **Beide Entwürfe gingen ohne Fehler durch `uebernehmen`.** Beim Abspielen meldete die Leiste in
  einem Schritt eine Id als „nicht zu sehen“: Die Funktion weckt den Render-Thread per Nachricht,
  ist also kein Aufrufer im gezeigten Wirkungsweg. Mit der Dateiansicht statt des Wirkungswegs
  zeigten danach alle 17 Schritte jede Id. Lehre für den Skill: eine Ansicht wählen, die alle Ids
  des Schritts enthält. `uebernehmen` kann das nicht prüfen (Frage der Ansicht, keine Messung).
- Die Vorschläge im letzten Schritt der Markierungs-Führung decken sich mit den Einschätzungen der
  bestehenden `deutung.json`.
- Bildschirmfotos: `lokal/A10-liste.png` (Liste) und `lokal/A10-schritt.png` (ein Schritt auf der
  Funktionsebene im Wirkungsweg). Der Generator der Entwürfe liegt lokal neben den Führungen.
- Headless-Chromium unter Windows fand drei lokale deutsche Stimmen; Vorlesen ist dort verfügbar.

**Hinweis für Manu:** Die Führungen liegen in `lokal/ziele/sketchorus/daidalos/fuehrungen/`.
Öffnen: `lokal/ziele/sketchorus/daidalos/karte.html#fuehrung=stift-bis-strich` bzw.
`#fuehrung=markierungs-kette`, Schalter „Vorlesen“ an, auf Wunsch „Automatisch“. Rückmeldung an
die Leitung ist der eigentliche Test dieser Etappe.

## Offene Fragen

- Soll `uebernehmen` warnen, wenn eine Id im Wirkungsweg der Ansicht nicht vorkommen kann (wie in
  der Probe)? Das ginge für `weg=` mit derselben Breitensuche wie die Karte, aber nicht allgemein.
- Gruppen-Hashes machen Schritte auf Modulebene bei jeder Änderung im Modul veraltet. Ist das
  gewollt, oder sollen Module und Pakete nur als Ort gelten (ohne Hash)?
- Der Text wird als „Titel. Text“ vorgelesen; Ids und Pfade spricht die Stimme nicht. Reicht das?

## Nächste sinnvolle Schritte

- Manus Hörprobe auswerten und die Regeln für Texte im Skill schärfen.
- Prüfung „Id in der Ansicht sichtbar“ für Wirkungswege in `uebernehmen`.
- Etappe 7: Live-Steuerung über `daidalos serve`, die denselben Spieler nutzt.
