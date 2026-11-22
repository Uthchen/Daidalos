"""Browser-Probe: karte.html in Chromium (Playwright).

Läuft nur, wenn Playwright und Chromium installiert sind (``uv run playwright install chromium``),
sonst übersprungen. In der CI nur unter Ubuntu.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main
from daidalos.pfad import suche_weg
from daidalos.render import baue_karte, einstellungen_fuer_karte

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")

BEREIT = "document.documentElement.dataset.zustand === 'bereit'"
CODE = {"kotlin", "java", "c", "cpp"}
STRICH = "datei:kern/src/commonMain/kotlin/beispiel/kern/Strich.kt"
START = "datei:anwendung/src/main/kotlin/beispiel/anwendung/Start.kt"
ANFANG_MITTE = (
    "kante:nutzt:datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Anfang.kt"
    "->datei:kern/src/commonMain/kotlin/beispiel/kern/zyklus/Mitte.kt:produktiv"
)


def messung() -> dict[str, Any]:
    return json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))


def _zielkopie(ordner: Path) -> Path:
    """Kopie von mini_modulgraph mit Leerzeichen und Umlaut im Pfad; Karte im Standardordner."""
    ziel = ordner / "mein Prüfprojekt"
    shutil.copytree(BEISPIELE / "mini_modulgraph", ziel)
    daten = ziel / "docs" / "daidalos" / "daidalos.json"
    daten.parent.mkdir(parents=True, exist_ok=True)
    daten.write_bytes((ERWARTET / "mini_modulgraph.daidalos.json").read_bytes())
    return ziel


@pytest.fixture(scope="module")
def ziel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ziel = _zielkopie(tmp_path_factory.mktemp("karte"))
    assert main(["render", str(ziel)]) == 0
    return ziel


@pytest.fixture(scope="module")
def karte(ziel: Path) -> Path:
    return ziel / "docs" / "daidalos" / "karte.html"


@pytest.fixture(scope="module")
def grosse_karte(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Wie mini_modulgraph, aber mit 160 zusätzlichen Dateien in :nativ (Aus- und Einklappen)."""
    ziel = _zielkopie(tmp_path_factory.mktemp("gross"))
    daten = messung()
    for nr in range(160):
        pfad = f"nativ/src/main/kotlin/beispiel/nativ/viel/Datei{nr:03}.kt"
        daten["knoten"].append(
            {
                "art": "datei",
                "id": "datei:" + pfad,
                "modul": "modul::nativ",
                "pfad": pfad,
                "rolle": "produktiv",
                "sprache": "kotlin",
                "zeilen": 1,
            }
        )
    karte = ziel / "docs" / "daidalos" / "karte.html"
    einstellungen = einstellungen_fuer_karte("vscode://file/{pfad}:{zeile}", "../..")
    karte.write_text(baue_karte(daten, None, einstellungen), encoding="utf-8", newline="\n")
    return karte


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as fehler:  # Chromium nicht installiert
            pytest.skip(f"Chromium nicht verfügbar: {fehler}")
        yield b
        b.close()


def _neue_seite(browser: Any, **optionen: Any) -> tuple[Any, Any, list[str]]:
    kontext = browser.new_context(viewport={"width": 1400, "height": 900}, **optionen)
    s = kontext.new_page()
    fehler: list[str] = []
    s.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
    s.on("pageerror", lambda e: fehler.append(str(e)))
    s.on(
        "request",
        lambda r: (
            fehler.append("Netz: " + r.url) if not r.url.startswith(("file:", "data:")) else None
        ),
    )
    return kontext, s, fehler


@pytest.fixture
def seite(browser: Any) -> Iterator[tuple[Any, list[str]]]:
    kontext, s, fehler = _neue_seite(browser)
    yield s, fehler
    kontext.close()


def oeffne(s: Any, karte: Path, hash_teil: str = "") -> None:
    s.goto(karte.as_uri() + hash_teil)
    s.wait_for_function(BEREIT, timeout=30000)


def warte(s: Any, ms: int = 50) -> None:
    s.wait_for_timeout(ms)
    s.wait_for_function(BEREIT, timeout=30000)


def seitenpunkt(s: Any, ausdruck: str) -> tuple[float, float]:
    """Punkt in Cytoscape-Bildschirmkoordinaten (``ausdruck``: {x, y}) → Seitenkoordinaten."""
    return s.evaluate(
        "(() => { const r = daidalos.cy.container().getBoundingClientRect(); const p = "
        + ausdruck
        + "; return [r.left + p.x, r.top + p.y]; })()"
    )


def klick_symbol(s: Any, knoten_id: str, abstand: float = 11) -> None:
    """Klick auf ein Symbol oben rechts im Kasten (11: Schloss, 29: Editor, 47: Code)."""
    x, y = seitenpunkt(
        s,
        f"(() => {{ const bb = daidalos.cy.getElementById({json.dumps(knoten_id)})"
        f".renderedBoundingBox({{includeLabels: false}}); "
        f"return {{x: bb.x2 - {abstand}, y: bb.y1 + 11}}; }})()",
    )
    s.mouse.click(x, y)
    s.wait_for_timeout(80)


def position(s: Any, knoten_id: str) -> dict[str, float]:
    return s.evaluate(f"daidalos.cy.getElementById({json.dumps(knoten_id)}).position()")


def erwartete_knoten(ebene: str) -> int:
    d = messung()
    knoten = d["knoten"]
    gruppen = [k for k in knoten if k["art"] in ("modul", "ordner")]
    mit_kante = {k[s] for k in d["kanten"] if k["art"] in ("nutzt", "jni") for s in ("von", "nach")}
    dateien = [
        k
        for k in knoten
        if k["art"] == "datei"
        and (
            k["sprache"] in CODE or k["id"] in mit_kante
        )
    ]
    if ebene == "modul":
        # Ordner ohne Kartendateien und ohne Kanten werden ein Kasten „Weitere Ordner“.
        mit_gruppenkante = {
            k[s] for k in d["kanten"] if k["art"] != "enthaelt" for s in ("von", "nach")
        }
        mit_datei = {f.get("modul") or f.get("ordner") for f in dateien}
        weitere = [
            g
            for g in gruppen
            if g["art"] == "ordner" and g["id"] not in mit_datei and g["id"] not in mit_gruppenkante
        ]
        return len(gruppen) - len(weitere) + (1 if weitere else 0)
    produktiv = [f for f in dateien if not f.get("fremd") and f["rolle"] == "produktiv"]
    if ebene == "paket":
        pakete = {f["paket"] for f in produktiv if "paket" in f}
        fremd_behaelter = {
            k.get("modul") or k.get("ordner")
            for k in knoten
            if k["art"] == "paket" and k.get("fremd")
        }
        behaelter = {
            next(p.get("modul") or p.get("ordner") for p in knoten if p["id"] == pid)
            for pid in pakete
        }
        return len(pakete) + len(fremd_behaelter) + len(behaelter | fremd_behaelter)
    pakete = {f["paket"] for f in produktiv if "paket" in f}
    fremd_behaelter = {f.get("modul") or f.get("ordner") for f in dateien if f.get("fremd")}
    behaelter = {f.get("modul") or f.get("ordner") for f in produktiv} | fremd_behaelter
    return len(produktiv) + len(pakete) + len(fremd_behaelter) + len(behaelter)


# ---------------------------------------------------------------- A04: Ebenen, Befunde, Adressen


def test_ebenen_ohne_fehler(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte)
    for ebene in ("modul", "paket", "datei"):
        s.click(f"#ebenen button[data-ebene={ebene}]")
        warte(s)
        anzahl = s.evaluate("window.daidalos.cy.nodes().length")
        assert anzahl == erwartete_knoten(ebene), ebene
        assert s.evaluate("location.hash") == f"#ebene={ebene}"
    assert fehler == []


def test_nur_produktiv_blendet_tests_aus(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    test_dateien = [
        k["id"]
        for k in messung()["knoten"]
        if k.get("rolle") == "test" and k["art"] == "datei" and k["sprache"] == "kotlin"
    ]
    assert test_dateien
    ids = set(s.evaluate("window.daidalos.cy.nodes().map(n => n.id())"))
    assert not ids & set(test_dateien)
    s.click("#rollen button[data-rolle=mit-tests]")
    warte(s)
    ids = set(s.evaluate("window.daidalos.cy.nodes().map(n => n.id())"))
    assert set(test_dateien) <= ids
    assert fehler == []


def _zyklus_befund() -> dict[str, Any]:
    return next(
        b
        for b in messung()["befunde"]
        if b["regel"] == "zyklus" and b["beleg"]["ebene"] == "datei" and len(b["knoten"]) == 3
    )


def test_zyklus_befund_hebt_knoten_hervor(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    befund = _zyklus_befund()
    oeffne(s, karte)
    s.click(f'ol.befunde button[data-befund="{befund["id"]}"]')
    warte(s, 400)
    hervor = s.evaluate("window.daidalos.cy.nodes('.hl').map(n => n.id()).sort()")
    assert hervor == sorted(befund["knoten"])
    einstiege = s.evaluate("window.daidalos.cy.nodes('.einstieg').map(n => n.id()).sort()")
    assert einstiege == sorted(e["knoten"] for e in befund["beleg"]["einstiege"])
    trenn = s.evaluate("window.daidalos.cy.edges('.trenn').map(e => e.id())")
    assert trenn == [befund["beleg"]["trennstelle"]]
    assert s.evaluate("location.hash") == "#befund=" + quote(befund["id"], safe="")
    # Der Fluss läuft im Ring über genau die Zyklus-Kanten.
    stand = s.evaluate("daidalos.fluss()")
    assert stand["laeuft"] is True
    assert stand["kanten"] == sorted(befund["beleg"]["kanten"])
    assert fehler == []


def test_sprungadresse_befund(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    befund = next(b for b in messung()["befunde"] if b["beleg"].get("ebene") == "paket")
    oeffne(s, karte, "#befund=" + quote(befund["id"], safe=""))
    s.wait_for_timeout(400)
    assert s.evaluate("window.daidalos.zustand.ebene") == "paket"
    hervor = s.evaluate("window.daidalos.cy.nodes('.hl').map(n => n.id()).sort()")
    assert hervor == sorted(befund["knoten"])
    assert befund["id"] in s.inner_text("#seite")
    assert fehler == []


def test_sprungadresse_knoten_und_seitenleiste(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#knoten=" + quote("modul::anwendung", safe=""))
    text = s.inner_text("#seite")
    assert ":anwendung" in text
    assert "veraltet" in text
    assert "gemessen" in text and "gedeutet" in text
    assert fehler == []


# ---------------------------------------------------------------- A05 Teil A


def test_weitere_ordner_und_plugin_kanten(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte)
    ids = set(s.evaluate("daidalos.cy.nodes().map(n => n.id())"))
    assert "sammel:ordner" in ids
    assert "ordner:." not in ids
    assert "ordner:werkzeug" in ids  # Ordner mit Code bleibt einzeln
    sammel = s.evaluate("daidalos.cy.getElementById('sammel:ordner').data('label')")
    assert sammel == "Weitere Ordner\n1 Ordner · 4 Dateien"
    # Plugin-Kanten standardmäßig aus, Vermerk am Ziel.
    plugins = [k["id"] for k in messung()["kanten"] if k["art"] == "gradle-plugin"]
    assert len(plugins) == 4
    kanten = set(s.evaluate("daidalos.cy.edges().map(e => e.id())"))
    assert not kanten & set(plugins)
    regeln = s.evaluate("daidalos.cy.getElementById('modul::regeln').data('label')")
    assert regeln.endswith("Plugin für 4 Module")
    s.check("#k-plugin")
    warte(s)
    kanten = set(s.evaluate("daidalos.cy.edges().map(e => e.id())"))
    assert set(plugins) <= kanten
    regeln = s.evaluate("daidalos.cy.getElementById('modul::regeln').data('label')")
    assert "Plugin" not in regeln
    # Klick auf „Weitere Ordner“ listet die Ordner mit Dateien und Zeilen.
    s.evaluate("daidalos.zeigeKnoten('sammel:ordner')")
    warte(s)
    text = s.inner_text("#seite")
    assert "(Wurzel)" in text and "4 Dateien" in text and "21 Zeilen" in text
    assert fehler == []


def test_kanten_im_paket_blasser(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    innen = s.evaluate("daidalos.cy.edges('.innen').map(e => e.id())")
    assert ANFANG_MITTE in innen
    assert s.evaluate("daidalos.cy.edges('.innen')[0].style('opacity')") == "0.32"
    befund = _zyklus_befund()
    s.evaluate(f"daidalos.zeigeBefund({json.dumps(befund['id'])})")
    warte(s, 300)
    # Im Zyklus normal gezeichnet.
    deck = s.evaluate(f"daidalos.cy.getElementById({json.dumps(ANFANG_MITTE)}).style('opacity')")
    assert deck == "1"
    assert fehler == []


# ---------------------------------------------------------------- B1 Sperren und Positionen


def test_sperren_verschieben_merken_zuruecksetzen(
    seite: tuple[Any, list[str]], karte: Path
) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    assert s.evaluate("daidalos.cy.nodes().every(n => n.locked())")
    assert s.inner_text("#schloss") == "alle gesperrt"
    vorher = position(s, STRICH)
    klick_symbol(s, STRICH)
    assert s.evaluate(f"daidalos.cy.getElementById('{STRICH}').locked()") is False
    assert s.evaluate(f"daidalos.cy.getElementById('{STRICH}').hasClass('offen')")
    assert s.inner_text("#schloss") == "1 entsperrt"
    # Der Klick auf das Schloss wählt nichts aus.
    assert s.evaluate("daidalos.zustand.auswahl") is None
    x, y = seitenpunkt(s, f"daidalos.cy.getElementById('{STRICH}').renderedPosition()")
    s.mouse.move(x, y)
    s.mouse.down()
    s.mouse.move(x + 40, y + 30, steps=4)
    s.mouse.move(x + 80, y + 60, steps=4)
    s.mouse.up()
    s.wait_for_timeout(80)
    verschoben = position(s, STRICH)
    assert verschoben != vorher
    # Nach dem Neuladen steht er wieder dort, die Sperre gilt wieder.
    s.reload()
    s.wait_for_function(BEREIT)
    assert position(s, STRICH) == pytest.approx(verschoben, abs=0.2)
    s.click("#zuruecksetzen")
    warte(s)
    assert position(s, STRICH) == pytest.approx(vorher, abs=0.2)
    # Globales Schloss: alles entsperren, dann wieder alles sperren.
    s.click("#schloss")
    assert s.inner_text("#schloss") == "alle entsperrt"
    assert s.evaluate("daidalos.cy.nodes().every(n => !n.locked())")
    s.click("#schloss")
    assert s.inner_text("#schloss") == "alle gesperrt"
    assert fehler == []


def test_gruppe_verschieben_gesperrtes_bleibt(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    paket = "paket::kern/beispiel.kern"
    punkt = "datei:kern/src/commonMain/kotlin/beispiel/kern/Punkt.kt"
    klick_symbol(s, paket)
    klick_symbol(s, punkt)  # Inhalt erbt „offen“; Punkt.kt wird ausdrücklich gesperrt.
    assert s.evaluate(f"daidalos.cy.getElementById('{punkt}').locked()") is True
    assert s.evaluate(f"daidalos.cy.getElementById('{STRICH}').locked()") is False
    vor_punkt, vor_strich = position(s, punkt), position(s, STRICH)
    x, y = seitenpunkt(
        s,
        f"(() => {{ const bb = daidalos.cy.getElementById('{paket}')"
        ".renderedBoundingBox({includeLabels: false}); return {x: bb.x1 + 5, y: bb.y2 - 5}; })()",
    )
    s.mouse.move(x, y)
    s.mouse.down()
    s.mouse.move(x + 50, y + 40, steps=5)
    s.mouse.up()
    s.wait_for_timeout(80)
    assert position(s, punkt) == vor_punkt
    assert position(s, STRICH) != vor_strich
    # Sperrzustand bleibt beim Ebenenwechsel erhalten.
    s.click("#ebenen button[data-ebene=paket]")
    warte(s)
    s.click("#ebenen button[data-ebene=datei]")
    warte(s)
    assert s.evaluate(f"daidalos.cy.getElementById('{STRICH}').locked()") is False
    assert s.evaluate(f"daidalos.cy.getElementById('{punkt}').locked()") is True
    assert fehler == []


# ---------------------------------------------------------------- B2 Fokus, B3 Fluss


FOKUS_PRUEFUNG = """(() => {
  const cy = daidalos.cy, n = cy.getElementById(%s);
  const n1 = n.connectedEdges().connectedNodes().not(n);
  const n2 = n1.connectedEdges().connectedNodes().not(n).not(n1);
  const rest = cy.nodes().filter(x => x.isChildless()).not(n).not(n1).not(n2);
  const op = c => [...new Set(c.map(x => x.style('opacity')))].sort();
  const direkt = n.connectedEdges();
  const weiter = n1.connectedEdges().not(direkt)
    .filter(e => n2.contains(e.source()) || n2.contains(e.target()));
  return { gewaehlt: n.style('opacity'), n1: op(n1), n2: op(n2), rest: op(rest),
           direkt: op(direkt), weiter: op(weiter), n1Zahl: n1.length, n2Zahl: n2.length };
})()"""


@pytest.mark.parametrize(
    ("thema", "stufen"), [("dark", ("0.82", "0.5", "0.22")), ("light", ("0.75", "0.4", "0.14"))]
)
def test_fokus_stufen(
    seite: tuple[Any, list[str]], karte: Path, thema: str, stufen: tuple[str, str, str]
) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    s.click(f".thema button[data-thema={thema}]")
    s.evaluate(f"daidalos.zeigeKnoten('{STRICH}')")
    warte(s, 400)
    r = s.evaluate(FOKUS_PRUEFUNG % json.dumps(STRICH))
    assert r["n1Zahl"] >= 2 and r["n2Zahl"] >= 1
    assert r["gewaehlt"] == "1"
    assert r["n1"] == [stufen[0]]
    assert r["n2"] == [stufen[1]]
    assert r["rest"] == [stufen[2]]
    assert r["direkt"] == ["1"]
    assert r["weiter"] == [stufen[1]]
    assert "wer Strich.kt nutzt: 1 direkt" in s.inner_text("#pfadinfo")
    # Esc hebt den Fokus auf.
    s.keyboard.press("Escape")
    assert s.evaluate("daidalos.cy.elements('.blass, .n1, .n2').length") == 0
    assert fehler == []


def test_fluss_nur_bei_auswahl(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    assert s.evaluate("daidalos.fluss()")["laeuft"] is False
    s.evaluate(f"daidalos.zeigeKnoten('{STRICH}')")
    warte(s, 200)
    eins = s.evaluate("daidalos.fluss()")
    s.wait_for_timeout(300)
    zwei = s.evaluate("daidalos.fluss()")
    assert eins["laeuft"] and zwei["laeuft"]
    assert zwei["versatz"] != eins["versatz"]
    # Stufe 1: direkte Kanten des gewählten Knotens.
    direkt = s.evaluate(f"daidalos.cy.getElementById('{STRICH}').connectedEdges().map(e => e.id())")
    assert sorted(direkt) == eins["kanten"]
    # Stufe 2: nur Kanten, die eine Kette durch den gewählten Knoten fortsetzen.
    pruefe = s.evaluate(
        """(() => {
      const cy = daidalos.cy, n = cy.getElementById(STRICH_ID);
      const rein1 = n.incomers('edge'), raus1 = n.outgoers('edge');
      return daidalos.fluss().kanten2.map(id => {
        const e = cy.getElementById(id);
        return (rein1.sources().contains(e.target()) && !e.source().same(n)) ||
               (raus1.targets().contains(e.source()) && !e.target().same(n));
      });
    })()""".replace("STRICH_ID", json.dumps(STRICH))
    )
    assert pruefe and all(pruefe)
    # Klick ins Leere hebt den Fokus und den Fluss auf.
    x, y = seitenpunkt(s, "({x: 4, y: 4})")
    s.mouse.click(x, y)
    s.wait_for_timeout(50)
    stand = s.evaluate("daidalos.fluss()")
    assert (stand["laeuft"], stand["kanten"], stand["kanten2"]) == (False, [], [])
    assert s.evaluate("daidalos.cy.edges('.fluss, .fluss2').length") == 0
    assert fehler == []


def test_keine_bewegung_bei_reduced_motion(browser: Any, karte: Path) -> None:
    kontext, s, fehler = _neue_seite(browser, reduced_motion="reduce")
    oeffne(s, karte, "#ebene=datei")
    s.evaluate(f"daidalos.zeigeKnoten('{STRICH}')")
    warte(s, 100)
    eins = s.evaluate("daidalos.fluss()")
    versatz = s.evaluate("daidalos.cy.edges('.fluss')[0].style('line-dash-offset')")
    s.wait_for_timeout(300)
    assert eins["laeuft"] is False
    assert eins["kanten"]  # stehende Striche
    assert s.evaluate("daidalos.cy.edges('.fluss')[0].style('line-style')") == "dashed"
    assert s.evaluate("daidalos.cy.edges('.fluss')[0].style('line-dash-offset')") == versatz
    assert fehler == []
    kontext.close()


# ---------------------------------------------------------------- B4 Kanten


def test_kantenklick_zeigt_belege_grenze_und_zyklus(
    seite: tuple[Any, list[str]], karte: Path
) -> None:
    s, fehler = seite
    oeffne(s, karte, "#ebene=datei")
    x, y = seitenpunkt(
        s, f"daidalos.cy.getElementById({json.dumps(ANFANG_MITTE)}).renderedMidpoint()"
    )
    s.mouse.click(x, y)
    s.wait_for_timeout(200)
    assert s.evaluate("daidalos.zustand.auswahl.id") == ANFANG_MITTE
    text = s.inner_text("#seite")
    assert "belege" in text.lower() and "beispiel.kern.zyklus.Mitte" in text
    assert "innerhalb eines Pakets" in text
    assert "Zyklus aus 3 Dateien" in text
    assert "günstigste Trennstelle" in text and "löst den Zyklus" in text
    assert s.evaluate(
        f"daidalos.cy.getElementById({json.dumps(ANFANG_MITTE)}).hasClass('kgewaehlt')"
    )
    # Fokus gilt für beide Enden.
    assert s.evaluate("daidalos.cy.nodes('.gewaehlt').length") == 2
    # Belege mit Editor-Link für genau diese Zeile.
    hrefs = s.eval_on_selector_all("#seite a[data-editor]", "l => l.map(a => a.href)")
    assert hrefs and all(h.startswith("vscode://file/") for h in hrefs)
    # Über eine Modulgrenze: einzige Verbindung der Pakete und Module.
    kante = f"kante:nutzt:{START}->{STRICH}:produktiv"
    s.evaluate(f"daidalos.zeigeKante({json.dumps(kante)})")
    warte(s, 200)
    text = s.inner_text("#seite")
    assert "über eine Modulgrenze" in text
    assert "einzige Verbindung der beiden Pakete" in text
    assert "einzige Verbindung der beiden Module" in text
    assert fehler == []


def test_verdichtete_kante_listet_datei_kanten(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    d = messung()
    paket_kante = next(
        k
        for k in d["kanten"]
        if k["art"] == "nutzt" and k["von"].startswith("paket:") and k["rolle"] == "produktiv"
    )
    oeffne(s, karte, "#ebene=paket")
    s.evaluate(f"daidalos.zeigeKante({json.dumps(paket_kante['id'])})")
    warte(s, 200)
    text = s.inner_text("#seite")
    assert "getragen von" in text.lower()
    traeger = s.eval_on_selector_all("#seite [data-kante]", "l => l.map(b => b.dataset.kante)")
    assert traeger and all(t.startswith("kante:nutzt:datei:") for t in traeger)
    # Gradle-Kante: tragende nutzt-Kanten.
    gradle = "kante:gradle-impl:modul::anwendung->modul::kern"
    s.evaluate(f"daidalos.zeigeKante({json.dumps(gradle)})")
    warte(s, 200)
    text = s.inner_text("#seite")
    assert "verwendet von" in text.lower() and "anwendung/build.gradle.kts:6" in text
    assert fehler == []


# ---------------------------------------------------------------- B5 Sprünge und Zurück


def test_sprung_mit_ebenenwechsel_und_zurueck(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    oeffne(s, karte, "#knoten=" + quote("paket::kern/beispiel.kern", safe=""))
    assert s.evaluate("daidalos.zustand.ebene") == "paket"
    # Kante aus „Nutzt“ öffnen, dort eine tragende Datei-Kante anklicken: Wechsel zur Dateiebene.
    s.click("#seite [data-kante]")
    warte(s, 200)
    s.click("#seite ul.liste [data-kante]")
    warte(s, 200)
    assert s.evaluate("daidalos.zustand.ebene") == "datei"
    datei_hash = s.evaluate("location.hash")
    assert datei_hash.startswith("#ebene=datei&kante=")
    # Knoten in den Belegen anklicken.
    s.click("#seite h2 [data-knoten]")
    warte(s, 200)
    assert s.evaluate("daidalos.zustand.auswahl.art") == "knoten"
    s.go_back()
    warte(s, 300)
    assert s.evaluate("location.hash") == datei_hash
    assert s.evaluate("daidalos.zustand.auswahl.art") == "kante"
    s.go_back()
    warte(s, 300)
    s.go_back()
    warte(s, 300)
    assert s.evaluate("daidalos.zustand.ebene") == "paket"
    assert s.evaluate("daidalos.zustand.auswahl.id") == "paket::kern/beispiel.kern"
    assert fehler == []


def test_sprung_klappt_modul_aus(browser: Any, grosse_karte: Path) -> None:
    kontext, s, fehler = _neue_seite(browser)
    oeffne(s, grosse_karte, "#ebene=datei")
    assert s.evaluate("daidalos.gross") is True
    assert s.evaluate("[...daidalos.zustand.offen]") == ["modul::nativ"]
    s.evaluate(f"daidalos.zeigeKnoten('{STRICH}')")
    warte(s, 200)
    assert "modul::kern" in s.evaluate("[...daidalos.zustand.offen]")
    s.click(f'#seite [data-knoten="{START}"]')
    warte(s, 200)
    assert "modul::anwendung" in s.evaluate("[...daidalos.zustand.offen]")
    assert s.evaluate(f"daidalos.cy.getElementById('{START}').hasClass('gewaehlt')")
    s.go_back()
    warte(s, 300)
    assert s.evaluate("daidalos.zustand.auswahl.id") == STRICH
    assert fehler == []
    kontext.close()


# ---------------------------------------------------------------- B6 Pfad-Suche


def _kette(schritte: Any) -> list[str] | None:
    if schritte is None:
        return None
    if not schritte:
        return None
    return [schritte[0].von] + [x.nach for x in schritte]


@pytest.mark.parametrize("mit_tests", [False, True])
def test_pfadsuche_wie_daidalos_pfad(
    seite: tuple[Any, list[str]], karte: Path, mit_tests: bool
) -> None:
    s, fehler = seite
    d = messung()
    oeffne(s, karte)
    ebenen = {"modul": ("modul", "ordner"), "paket": ("paket",), "datei": ("datei",)}
    for ebene, arten in ebenen.items():
        ids = sorted(k["id"] for k in d["knoten"] if k["art"] in arten)
        paare = [(a, b) for a in ids for b in ids if a != b]
        karte_wege = s.evaluate(
            "([paare, ebene, t]) => paare.map(([a, b]) => "
            "{ const w = daidalos.sucheWeg(a, b, ebene, t); return w && w.knoten; })",
            [paare, ebene, mit_tests],
        )
        knoten = {k["id"]: k for k in d["knoten"]}
        for (a, b), weg in zip(paare, karte_wege, strict=True):
            erwartet = _kette(suche_weg(d, knoten[a], knoten[b], ebene, mit_tests))
            assert weg == erwartet, (ebene, a, b)
    assert fehler == []


def test_pfadsuche_in_der_leiste_wie_cli(
    seite: tuple[Any, list[str]], karte: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    s, fehler = seite
    daten = str(ERWARTET / "mini_modulgraph.daidalos.json")
    assert main(["pfad", "Start.kt", "Punkt.kt", "--daten", daten, "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    erwartet = [cli["weg"][0]["von"]] + [x["nach"] for x in cli["weg"]]
    oeffne(s, karte, "#ebene=datei")
    s.fill("#pfad-von", "Start.kt")
    s.fill("#pfad-nach", "kern/Punkt.kt")
    s.click("#pfad-los")
    warte(s, 300)
    namen = [k.rsplit("/", 1)[-1] for k in erwartet]
    assert s.inner_text("#pfadinfo") == " → ".join(namen)
    hervor = s.evaluate("daidalos.cy.nodes('.hl').map(n => n.id()).sort()")
    assert hervor == sorted(erwartet)
    assert s.evaluate("daidalos.fluss()")["laeuft"] is True
    # Kein Weg: die Infozeile sagt es.
    assert main(["pfad", "Punkt.kt", "Start.kt", "--daten", daten, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["weg"] is None
    s.fill("#pfad-von", "kern/Punkt.kt")
    s.fill("#pfad-nach", "Start.kt")
    s.click("#pfad-los")
    warte(s, 300)
    assert "hängt nicht an" in s.inner_text("#pfadinfo")
    assert fehler == []


# ---------------------------------------------------------------- B7 Editor


def _erwarteter_link(ziel: Path, rel: str, zeile: int) -> str:
    voll = (ziel / rel).resolve().as_posix().lstrip("/")
    teile = voll.split("/")
    kodiert = [
        t if i == 0 and len(t) == 2 and t[1] == ":" else quote(t, safe="")
        for i, t in enumerate(teile)
    ]
    return "vscode://file/" + "/".join(kodiert) + f":{zeile}"


def test_editor_link_aus_file_seite(seite: tuple[Any, list[str]], karte: Path, ziel: Path) -> None:
    s, fehler = seite
    rel = "kern/src/commonMain/kotlin/beispiel/kern/Strich.kt"
    oeffne(s, karte, "#knoten=" + quote(STRICH, safe=""))
    href = s.get_attribute("#seite .symbole a[data-editor]", "href")
    assert href == _erwarteter_link(ziel, rel, 1)
    assert "Pr%C3%BCfprojekt" in href and "mein%20" in href
    assert s.is_disabled("#seite .symbole button")  # Code-Ansicht ausgegraut
    # Editor-Symbol am Kasten öffnet denselben Link.
    s.click("#ebenen button[data-ebene=datei]")
    warte(s)
    klick_symbol(s, STRICH, 29)
    assert s.evaluate("daidalos.letzterLink()") == href
    assert s.evaluate("daidalos.zustand.auswahl") is None
    # Der Klick löst nur die Editor-Adresse aus, keinen Netzzugriff.
    assert [f for f in fehler if not f.startswith("Netz: vscode://")] == []


def test_editor_ohne_file_ausgegraut(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    s.set_content(karte.read_text(encoding="utf-8"))
    s.wait_for_function(BEREIT, timeout=30000)
    assert s.evaluate("daidalos.editorLink('a.kt', 1)") is None
    s.evaluate(f"daidalos.zeigeKnoten('{STRICH}')")
    warte(s, 200)
    knopf = "#seite .symbole button[aria-label^='Im Editor öffnen geht nur']"
    assert s.is_disabled(knopf)
    assert "file://" in s.get_attribute(knopf, "title")
    assert fehler == []
