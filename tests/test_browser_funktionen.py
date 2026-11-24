"""Browser-Probe der Funktionsebene (A09) an ``mini_aufrufe`` und ``mini_markierung``.

Wie ``test_browser.py`` nur mit Playwright und Chromium, sonst übersprungen.
"""

from __future__ import annotations

import json
import re
import shutil
import statistics
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from conftest import BEISPIELE
from daidalos.cli import main
from daidalos.karte_funktionen import funktionsblock

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")

BEREIT = "document.documentElement.dataset.zustand === 'bereit'"
# Lokale Adressen; blob: ist der ELK-Worker aus dem eingebetteten Quelltext (A09b).
LOKAL = ("file:", "data:", "blob:")
AUFRUFE = "kern/src/commonMain/kotlin/de/beispiel/aufrufe/"
KETTE = "kern/src/main/kotlin/de/beispiel/kette/"


def _ziel(ordner: Path, beispiel: str) -> Path:
    ziel = ordner / beispiel
    shutil.copytree(BEISPIELE / beispiel, ziel)
    assert main(["scan", str(ziel)]) == 0
    assert main(["render", str(ziel)]) == 0
    return ziel


@pytest.fixture(scope="module")
def aufrufe(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _ziel(tmp_path_factory.mktemp("f"), "mini_aufrufe")


@pytest.fixture(scope="module")
def markierung(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _ziel(tmp_path_factory.mktemp("f"), "mini_markierung")


def karte(ziel: Path) -> Path:
    return ziel / "docs" / "daidalos" / "karte.html"


def messung(ziel: Path) -> dict[str, Any]:
    return json.loads((ziel / "docs" / "daidalos" / "daidalos.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as fehler:  # Chromium nicht installiert
            pytest.skip(f"Chromium nicht verfügbar: {fehler}")
        yield b
        b.close()


@pytest.fixture
def seite(browser: Any) -> Iterator[tuple[Any, list[str]]]:
    kontext = browser.new_context(viewport={"width": 1400, "height": 900})
    s = kontext.new_page()
    fehler: list[str] = []
    s.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
    s.on("pageerror", lambda e: fehler.append(str(e)))
    s.on(
        "request",
        lambda r: fehler.append("Netz: " + r.url) if not r.url.startswith(LOKAL) else None,
    )
    yield s, fehler
    kontext.close()


def oeffne(s: Any, pfad: Path, hash_teil: str = "") -> None:
    s.goto(pfad.as_uri() + hash_teil)
    s.wait_for_function(BEREIT, timeout=30000)


def warte(s: Any, ms: int = 80) -> None:
    s.wait_for_timeout(ms)
    s.wait_for_function(BEREIT, timeout=30000)


def f(datei: str, kurz: str) -> str:
    return f"funktion:{datei}#{kurz}"


def ids(s: Any, selektor: str) -> list[str]:
    return s.evaluate(f"daidalos.cy.nodes({json.dumps(selektor)}).map(n => n.id()).sort()")


def mitte(s: Any, knoten_id: str) -> tuple[float, float]:
    return s.evaluate(
        "(id) => { const r = daidalos.cy.container().getBoundingClientRect();"
        " const p = daidalos.cy.getElementById(id).renderedPosition();"
        " return [r.left + p.x, r.top + p.y]; }",
        knoten_id,
    )


# ---------------------------------------------------------------- Wege wie in der Karte


def _block(ziel: Path) -> dict[str, Any]:
    return funktionsblock(messung(ziel))


def erwarteter_weg(ziel: Path, start: str, vor: bool, tiefe: int) -> set[str]:
    """Breitensuche nach den Regeln aus dem Auftrag: sichere Aufrufe ohne Lesezugriffe und
    ohne Testcode, Ziele erweitert um ueberschreibt/actual (vorwärts: wer überschreibt;
    rückwärts: was überschrieben wird)."""
    b = _block(ziel)
    namen = ["funktion:" + b["dateien"][z[0]] + "#" + z[1] for z in b["funktionen"]]
    test = [bool(z[5] & 16) for z in b["funktionen"]]
    kanten = [(v, n, b["arten"][a], s) for v, n, a, s, *_ in b["kanten"]]

    def schritte(i: int) -> list[int]:
        return [
            (n if vor else v)
            for v, n, art, s in kanten
            if art == "ruft" and s and not test[v] and (v if vor else n) == i
        ]

    def erweitere(i: int) -> list[int]:
        return [
            (v if vor else n)
            for v, n, art, s in kanten
            if art in ("ueberschreibt", "actual") and s and not test[v] and (n if vor else v) == i
        ]

    s0 = namen.index(start)
    gesehen = {s0}
    rand = [s0]

    def ausbreiten(liste: list[int]) -> None:
        for x in liste:
            for y in erweitere(x):
                if y not in gesehen:
                    gesehen.add(y)
                    liste.append(y)

    if not vor:
        ausbreiten(rand)
    for _ in range(tiefe):
        neu = []
        for x in rand:
            for y in schritte(x):
                if y not in gesehen:
                    gesehen.add(y)
                    neu.append(y)
        ausbreiten(neu)
        rand = neu
    return {namen[i] for i in gesehen}


# ---------------------------------------------------------------- Tests


def test_doppelklick_oeffnet_funktionsansicht_mit_klassen(
    aufrufe: Path, seite: tuple[Any, list[str]]
) -> None:
    s, fehler = seite
    oeffne(s, karte(aufrufe), "#ebene=datei")
    assert not s.evaluate("daidalos.funktionsBlockGelesen()")
    datei = "datei:" + AUFRUFE + "Formen.kt"
    x, y = mitte(s, datei)
    s.mouse.dblclick(x, y)
    s.wait_for_function("daidalos.zustand.ebene === 'funktion'", timeout=10000)
    warte(s)
    assert s.evaluate("daidalos.zustand.fDatei") == AUFRUFE + "Formen.kt"
    assert s.evaluate("daidalos.funktionsBlockGelesen()")
    # Klassen als Rahmen, Funktionen darin
    rahmen = s.evaluate("daidalos.cy.nodes('[typ=\"fklasse\"]').map(n => n.data('label')).sort()")
    assert "Klasse Abgeleitet" in rahmen and "Schnittstelle Form" in rahmen
    eltern = s.evaluate(
        "(id) => daidalos.cy.getElementById(id).parent().data('label')",
        f(AUFRUFE + "Formen.kt", "Abgeleitet.beschreibe/0"),
    )
    assert eltern == "Klasse Abgeleitet"
    # oberste Ebene direkt im Dateirahmen
    assert (
        s.evaluate(
            "(id) => daidalos.cy.getElementById(id).parent().id()",
            f(AUFRUFE + "Formen.kt", "summe/1"),
        )
        == "ff:" + AUFRUFE + "Formen.kt"
    )
    assert "#datei-funktionen=" in s.evaluate("location.hash")
    assert fehler == []


LAGE = """() => { const cy = daidalos.cy; const m = cy.nodes('[typ="fdatei"]')[0].boundingBox();
  return cy.nodes('[typ="fnachbar"]').map(r => {
    const k = r.children(), e = k.connectedEdges();
    const raus = e.filter(x => k.contains(x.source()) && !k.contains(x.target())).length;
    const rein = e.filter(x => k.contains(x.target()) && !k.contains(x.source())).length;
    const bb = r.boundingBox();
    return { ruft: raus > 0, gerufen: rein > 0, x: (bb.x1 + bb.x2) / 2, mx: (m.x1 + m.x2) / 2 };
  }); }"""


def test_nachbarn_links_und_rechts(aufrufe: Path, seite: tuple[Any, list[str]]) -> None:
    """Aufrufer stehen links der Datei (Strich.kt hat nur Aufrufer), Gerufene rechts (Haupt.kt
    ruft nur)."""
    s, fehler = seite
    oeffne(s, karte(aufrufe), "#datei-funktionen=" + quote(AUFRUFE + "Strich.kt", safe=""))
    lage = s.evaluate(LAGE)
    assert len(lage) >= 3 and all(n["ruft"] and not n["gerufen"] for n in lage)
    assert all(n["x"] < n["mx"] for n in lage)
    haupt = "app/src/main/kotlin/de/beispiel/app/Haupt.kt"
    oeffne(s, karte(aufrufe), "#datei-funktionen=" + quote(haupt, safe=""))
    lage = s.evaluate(LAGE)
    assert len(lage) >= 2 and all(n["gerufen"] and not n["ruft"] for n in lage)
    assert all(n["x"] > n["mx"] for n in lage)
    assert fehler == []


@pytest.mark.parametrize(("richtung", "vor"), [("vor", True), ("rueck", False)])
def test_wirkungsweg_tiefe_2(
    aufrufe: Path, seite: tuple[Any, list[str]], richtung: str, vor: bool
) -> None:
    s, fehler = seite
    start = (
        f("app/src/main/kotlin/de/beispiel/app/Haupt.kt", "main/0")
        if vor
        else f(AUFRUFE + "Formen.kt", "Kreis.flaeche/0")
    )
    erwartet = erwarteter_weg(aufrufe, start, vor, 2)
    assert len(erwartet) > 2
    oeffne(s, karte(aufrufe), "#funktion=" + quote(start, safe="") + f"&weg={richtung}&tiefe=2")
    assert set(ids(s, '[typ="funktion"]')) == erwartet
    info = s.evaluate("document.getElementById('weginfo').innerText")
    assert f"{len(erwartet) - 1} Funktionen in" in info
    assert "markiert" in info and "unmarkiert" in info
    # Spalten nach Abstand: jede Kante des Wegs geht genau eine Spalte weiter
    stufen = s.evaluate(
        "() => { const w = daidalos.zustand.wegErgebnis; const fd = daidalos.fdaten();"
        " return Object.fromEntries([...w.stufe].map(([i, d]) => [fd.fn[i].id, d])); }"
    )
    xs = {i: s.evaluate("(id) => daidalos.cy.getElementById(id).position().x", i) for i in stufen}
    for a in stufen:
        for b in stufen:
            if stufen[a] < stufen[b]:
                assert (xs[a] < xs[b]) if vor else (xs[a] > xs[b]), (a, b)
    # Zurück zur Datei verlässt den Wegmodus
    s.click("#weginfo [data-zur-datei]")
    warte(s, 200)
    assert s.evaluate("daidalos.zustand.weg") is None
    assert fehler == []


def test_schalter_lesezugriffe_und_unsicher(aufrufe: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    zaehle = "(art) => daidalos.cy.edges().filter(e => e.data('art') === art).length"
    unsicher = "daidalos.cy.edges('.unsicher').length"
    lesen = None
    for datei in ("Zugriffe.kt", "Strich.kt", "Typen.kt", "Viele.kt"):
        oeffne(s, karte(aufrufe), "#datei-funktionen=" + quote(AUFRUFE + datei, safe=""))
        assert s.evaluate(zaehle, "lesen") == 0
        s.check("#k-lesen")
        warte(s, 150)
        lesen = s.evaluate(zaehle, "lesen") + s.evaluate(zaehle, "schreiben")
        if lesen:
            break
    assert lesen
    oeffne(s, karte(aufrufe), "#datei-funktionen=" + quote(AUFRUFE + "Viele.kt", safe=""))
    vorher = s.evaluate(unsicher)
    assert vorher > 0
    s.uncheck("#k-unsicher")
    warte(s, 150)
    assert s.evaluate(unsicher) == 0
    assert fehler == []


def test_grenzkante_hervorgehoben(markierung: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    von = f(KETTE + "Rechnen.kt", "zeichne/1")
    nach = f(KETTE + "Rechnen.kt", "glaette/1")
    befund = f"befund:markierung:{von}->{nach}"
    # aus der Befundliste: „Auf Funktionsebene zeigen“
    oeffne(s, karte(markierung), "#befund=" + quote(befund, safe=""))
    s.click("[data-grenze]")
    warte(s, 300)
    assert s.evaluate("daidalos.zustand.ebene") == "funktion"
    assert s.evaluate("daidalos.zustand.fDatei") == KETTE + "Rechnen.kt"
    gewaehlt = s.evaluate(
        "daidalos.cy.edges('.kgewaehlt').map(e => [e.source().id(), e.target().id(),"
        " e.hasClass('grenze')])"
    )
    assert gewaehlt == [[von, nach, True]]
    assert s.evaluate("(id) => daidalos.cy.getElementById(id).hasClass('grenzziel')", nach)
    # Farbe der Grenzkante ist die Befundfarbe der Markierung
    farbe = s.evaluate(
        "() => { const e = daidalos.cy.edges('.grenze')[0]; return e.style('line-color'); }"
    )
    warn = s.evaluate(
        "getComputedStyle(document.documentElement).getPropertyValue('--warn').trim()"
    )
    assert farbe.replace(" ", "") == _rgb(warn)
    # Grenzkante über ueberschreibt: Ersatzkante
    befund2 = (
        f"befund:markierung:{f(KETTE + 'Formen.kt', 'messe/1')}->"
        f"{f(KETTE + 'Formen.kt', 'Kreis.flaeche/0')}"
    )
    oeffne(s, karte(markierung), "#grenze=" + quote(befund2, safe=""))
    assert s.evaluate("daidalos.cy.edges('[art=\"grenze\"]').length") >= 1
    assert fehler == []


def _rgb(hexfarbe: str) -> str:
    h = hexfarbe.lstrip("#")
    return "rgb(" + ",".join(str(int(h[i : i + 2], 16)) for i in (0, 2, 4)) + ")"


def test_sprungadressen_und_seitenleiste(markierung: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    id_ = f(KETTE + "Formen.kt", "messe/1")
    oeffne(s, karte(markierung), "#funktion=" + quote(id_, safe=""))
    assert s.evaluate("daidalos.zustand.auswahl") == {"art": "funktion", "id": id_}
    text = s.inner_text("#seite").lower()
    for teil in (
        "fun messe(form)",
        "formen.kt:",
        "@de.beispiel.strichpfad",
        "markiert",
        "strichpfad an der funktion",
        "komplexität",
        "fan-in",
        "gerufen von",
        "ruft",
        "befunde an dieser funktion",
        "wirkungsweg vorwärts",
    ):
        assert teil in text, teil
    # unsichere Aufrufe mit Grund und anderen Kandidaten
    id2 = f(KETTE + "Formen.kt", "ungewiss/1")
    oeffne(s, karte(markierung), "#funktion=" + quote(id2, safe=""))
    text = s.inner_text("#seite")
    assert "unsicher: unbekannter-empfaenger" in text
    assert "andere Kandidaten" in text
    # Knopf „Wirkungsweg vorwärts“ schreibt die Adresse
    s.click("[data-weg='vor']")
    warte(s, 200)
    assert "&weg=vor&tiefe=3" in s.evaluate("location.hash")
    # Ebenenwahl „Funktionen“ öffnet die zuletzt gewählte Datei
    oeffne(s, karte(markierung), "#knoten=" + quote("datei:" + KETTE + "Pinsel.kt", safe=""))
    s.click("#ebenen [data-ebene='funktion']")
    warte(s, 200)
    assert s.evaluate("daidalos.zustand.fDatei") == KETTE + "Pinsel.kt"
    # ohne gewählte Datei: Bitte um eine Datei
    s.goto("about:blank")
    oeffne(s, karte(markierung), "#ebene=funktion")
    assert s.locator("#f-datei").count() == 1
    assert fehler == []


def test_positionen_und_fokus(markierung: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    pfad = KETTE + "Rechnen.kt"
    adresse = "#datei-funktionen=" + quote(pfad, safe="")
    oeffne(s, karte(markierung), adresse)
    id_ = f(pfad, "glaette/1")
    # Fokus beim Klick: Zoom mindestens lesbar
    x, y = mitte(s, id_)
    s.mouse.click(x, y)
    s.wait_for_timeout(600)
    assert s.evaluate("daidalos.cy.zoom()") >= s.evaluate("daidalos.MIN_ZOOM_FOKUS") - 1e-6
    assert s.evaluate("(id) => daidalos.cy.getElementById(id).hasClass('gewaehlt')", id_)
    # Entsperren, verschieben, neu laden: Position gemerkt, Schlüssel je Datei
    s.click("#schloss")
    vorher = s.evaluate("(id) => daidalos.cy.getElementById(id).position()", id_)
    x, y = mitte(s, id_)
    s.mouse.move(x, y)
    s.mouse.down()
    s.mouse.move(x + 60, y + 40, steps=5)
    s.mouse.up()
    nachher = s.evaluate("(id) => daidalos.cy.getElementById(id).position()", id_)
    assert nachher != vorher
    schluessel = s.evaluate("daidalos.speicherName(daidalos.positionsEbene())")
    assert schluessel.endswith("|funktion:" + pfad)
    s.reload()
    s.wait_for_function(BEREIT, timeout=30000)
    wieder = s.evaluate("(id) => daidalos.cy.getElementById(id).position()", id_)
    assert abs(wieder["x"] - nachher["x"]) < 0.2 and abs(wieder["y"] - nachher["y"]) < 0.2
    assert fehler == []


def test_warum_haengt_mit_funktionen(aufrufe: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    oeffne(s, karte(aufrufe), "#ebene=modul")
    s.fill("#pfad-von", "main/0")
    s.fill("#pfad-nach", "Basis.beschreibe/0")
    s.click("#pfad-los")
    warte(s, 300)
    assert s.evaluate("daidalos.zustand.ebene") == "funktion"
    assert s.evaluate("daidalos.zustand.weg.art") == "pfad"
    gezeigt = ids(s, '[typ="funktion"]')
    assert f("app/src/main/kotlin/de/beispiel/app/Haupt.kt", "main/0") in gezeigt
    assert f(AUFRUFE + "Formen.kt", "Basis.beschreibe/0") in gezeigt
    assert "Weg main/0" in s.inner_text("#weginfo")
    assert fehler == []


# ---------------------------------------------------------------- Grenze 150


@pytest.fixture(scope="module")
def grosse_karte(aufrufe: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """mini_aufrufe plus eine erfundene Datei, deren Funktion 200 Funktionen in 20 Dateien ruft."""
    from daidalos.render import baue_karte, einstellungen_fuer_karte

    daten = messung(aufrufe)
    modul = next(k for k in daten["knoten"] if k["art"] == "datei" and "Strich.kt" in k["id"])
    vorlage = {
        s: modul[s] for s in ("modul", "paket", "quellsatz", "rolle", "sprache") if s in modul
    }

    def funktion(pfad: str, name: str) -> dict[str, Any]:
        return {
            "art": "funktion",
            "behaelter": "",
            "erweiterung": None,
            "hash": "sha256:x",
            "id": f"funktion:{pfad}#{name}/0",
            "metriken": {"komplexitaet": 1, "zeilen": 1},
            "name": name,
            "rolle": "produktiv",
            "sichtbarkeit": "public",
            "sprache": "kotlin",
            "stelligkeit": 0,
            "zeile_bis": 1,
            "zeile_von": 1,
        }

    gross = AUFRUFE + "gross/Viel.kt"
    daten["knoten"].append({"art": "datei", "id": "datei:" + gross, "pfad": gross, **vorlage})
    daten["knoten"].append(funktion(gross, "alles"))
    for d in range(20):
        pfad = f"{AUFRUFE}gross/Ziel{d:02}.kt"
        daten["knoten"].append({"art": "datei", "id": "datei:" + pfad, "pfad": pfad, **vorlage})
        for n in range(10 if d else 2):
            daten["knoten"].append(funktion(pfad, f"f{n}"))
            daten["kanten"].append(
                {
                    "art": "ruft",
                    "beleg": [{"herkunft": "import", "sicher": True, "zeilen": [1]}],
                    "gewicht": 1,
                    "nach": f"funktion:{pfad}#f{n}/0",
                    "rolle": "produktiv",
                    "sicher": True,
                    "von": f"funktion:{gross}#alles/0",
                }
            )
    daten["knoten"].sort(key=lambda k: k["id"])
    ziel = tmp_path_factory.mktemp("gross") / "karte.html"
    html = baue_karte(daten, None, einstellungen_fuer_karte("vscode://file/{pfad}:{zeile}", None))
    ziel.write_text(html, encoding="utf-8", newline="\n")
    return ziel


def test_grenze_150_fasst_zusammen(grosse_karte: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    oeffne(s, grosse_karte, "#datei-funktionen=" + quote(AUFRUFE + "gross/Viel.kt", safe=""))
    kaesten = s.evaluate("daidalos.zustand.fKaesten")
    assert kaesten <= 150
    zu = ids(s, '[typ="fzu"]')
    # 1 + 2 + 19 × 10 = 193 Kästen: fünf Dateien mit 10 Funktionen werden zusammengefasst (je −9)
    assert len(zu) == 5
    assert all(
        re.search(r"\(\+10\)$", s.evaluate("(i) => daidalos.cy.getElementById(i).data('label')", i))
        for i in zu
    )
    # die Datei mit nur 2 Funktionen bleibt offen
    assert "fn:" + AUFRUFE + "gross/Ziel00.kt" in ids(s, '[typ="fnachbar"]')
    # Ein Klick klappt einzeln auf
    erste = zu[0]
    s.evaluate("(id) => void daidalos.cy.fit(daidalos.cy.getElementById(id), 200)", erste)
    x, y = mitte(s, erste)
    s.mouse.click(x, y)
    warte(s, 300)
    assert erste.removeprefix("fz:") in s.evaluate("[...daidalos.zustand.fAuf]")
    assert "fn:" + erste.removeprefix("fz:") in ids(s, '[typ="fnachbar"]')
    assert fehler == []


# ---------------------------------------------------------------- Startzeit


def test_startzeit_mit_und_ohne_funktionsblock(aufrufe: Path, browser: Any, tmp_path: Path) -> None:
    """Der Funktionsblock wird beim Start nicht gelesen; die Zeit bis „bereit“ steigt nicht
    messbar (Toleranz für Messrauschen)."""
    mit = karte(aufrufe)
    html = mit.read_text(encoding="utf-8")
    # Block künstlich auf etwa 1 MB vergrößern, damit ein Lesen beim Start auffiele
    block = re.search(r'(id="funktionen">)(.*?)(</script>)', html, re.S)
    assert block
    daten = json.loads(block.group(2))
    daten["funktionen"] = daten["funktionen"] * max(1, 1_000_000 // max(1, len(block.group(2))))
    gross = tmp_path / "mit.html"
    gross.write_text(
        html[: block.start(2)] + json.dumps(daten).replace("<", "\\u003c") + html[block.end(2) :],
        encoding="utf-8",
    )
    ohne = tmp_path / "ohne.html"
    ohne.write_text(html[: block.start(2)] + "null" + html[block.end(2) :], encoding="utf-8")
    zeiten: dict[str, list[float]] = {"mit": [], "ohne": []}
    for _ in range(4):
        for name, pfad in (("ohne", ohne), ("mit", gross)):
            kontext = browser.new_context(viewport={"width": 1400, "height": 900})
            s = kontext.new_page()
            oeffne(s, pfad)
            zeiten[name].append(s.evaluate("daidalos.zeiten.bereit"))
            assert not s.evaluate("daidalos.funktionsBlockGelesen()")
            kontext.close()
    mit_ms, ohne_ms = statistics.median(zeiten["mit"]), statistics.median(zeiten["ohne"])
    assert mit_ms <= ohne_ms * 1.5 + 150, zeiten


# ---------------------------------------------------------------- Wegmodus (A09b)

IM_BILD = """() => { const cy = daidalos.cy, b = cy.width(), h = cy.height();
  return cy.nodes('[typ="funktion"]').filter(n => {
    const r = n.renderedBoundingBox({ includeLabels: false });
    return r.x1 < 0 || r.y1 < 0 || r.x2 > b || r.y2 > h; }).length; }"""
HAUPT = "app/src/main/kotlin/de/beispiel/app/Haupt.kt"


def test_wegmodus_zeigt_ganzen_weg_ohne_fluss(aufrufe: Path, seite: tuple[Any, list[str]]) -> None:
    s, fehler = seite
    start = f(HAUPT, "main/0")
    oeffne(s, karte(aufrufe), "#funktion=" + quote(start, safe="") + "&weg=vor&tiefe=2")
    # Alle Kästen des Wegs im Bild, keine Hinweiszeile, Start gewählt, aber ohne Fluss.
    assert s.evaluate(IM_BILD) == 0
    assert s.evaluate("document.getElementById('weiter').hidden")
    assert s.evaluate("(id) => daidalos.cy.getElementById(id).hasClass('gewaehlt')", start)
    stand = s.evaluate("daidalos.fluss()")
    assert not stand["laeuft"] and stand["kanten"] == [] and stand["kanten2"] == []
    # Zählzeile und „wer … nutzt“ stehen in einer Leiste untereinander, ohne sich zu überdecken.
    a = s.evaluate("document.getElementById('weginfo').getBoundingClientRect().toJSON()")
    b = s.evaluate("document.getElementById('pfadinfo').getBoundingClientRect().toJSON()")
    assert a["height"] > 0 and b["height"] > 0 and a["bottom"] <= b["top"]
    # Wählt man eine andere Funktion, läuft der Fluss.
    andere = s.evaluate(
        "(id) => daidalos.cy.nodes('[typ=\"funktion\"]').filter(n => n.id() !== id)[0].id()",
        start,
    )
    s.evaluate("(id) => daidalos.zeigeFunktion(id)", andere)
    warte(s)
    assert s.evaluate("daidalos.fluss()")["kanten"]
    assert fehler == []


def test_wegmodus_zu_breit_startspalte_links_lesbar(
    aufrufe: Path, seite: tuple[Any, list[str]]
) -> None:
    """Passt der Weg nur unter der Lesegrenze ins Bild, steht die Startspalte links bündig bei
    lesbarem Zoom, und eine Zeile nennt, was rechts außerhalb liegt."""
    s, fehler = seite
    s.set_viewport_size({"width": 470, "height": 900})
    start = f(HAUPT, "main/0")
    oeffne(s, karte(aufrufe), "#funktion=" + quote(start, safe="") + "&weg=vor&tiefe=3")
    assert s.evaluate("daidalos.cy.zoom()") == pytest.approx(s.evaluate("daidalos.LESBAR"))
    links = s.evaluate(
        "(id) => daidalos.cy.getElementById(id).parent().renderedBoundingBox().x1", start
    )
    assert 20 <= links <= 40
    assert not s.evaluate("document.getElementById('weiter').hidden")
    rechts = s.evaluate(
        """() => { const cy = daidalos.cy; return cy.nodes('[typ="funktion"]').filter(n =>
          n.renderedBoundingBox({ includeLabels: false }).x2 > cy.width()).length; }"""
    )
    assert rechts > 0
    assert f"weiter rechts: {rechts} Funktion" in s.inner_text("#weiter")
    assert not s.evaluate("daidalos.fluss()")["laeuft"]
    assert fehler == []


def test_lesezugriffe_ab_markierter_start_funktion(
    markierung: Path, seite: tuple[Any, list[str]]
) -> None:
    s, fehler = seite
    oeffne(s, karte(markierung), "#ebene=funktion")
    markiert = s.evaluate("daidalos.fdaten().fn.find(f => f.markiert && !f.test).id")
    unmarkiert = s.evaluate("daidalos.fdaten().fn.find(f => !f.markiert && !f.test).id")
    oeffne(s, karte(markierung), "#funktion=" + quote(markiert, safe="") + "&weg=vor&tiefe=3")
    assert s.is_checked("#k-lesen")
    # Der gemerkte Stand bleibt aus: zurück in der Datei ist der Schalter wieder aus.
    assert s.evaluate("daidalos.zustand.fLesen") is False
    s.click("#weginfo [data-zur-datei]")
    warte(s, 150)
    assert not s.is_checked("#k-lesen")
    # Ab einer unmarkierten Funktion gilt der gemerkte Stand.
    s.evaluate("(id) => daidalos.zeigeWeg(id, 'vor', 3)", unmarkiert)
    warte(s)
    assert not s.is_checked("#k-lesen")
    s.check("#k-lesen")
    warte(s, 150)
    assert s.evaluate("daidalos.zustand.fLesen") is True
    assert fehler == []
