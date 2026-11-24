"""Browser-Probe der Führungen (A10) an ``mini_aufrufe``.

Wie ``test_browser.py`` nur mit Playwright und Chromium, sonst übersprungen. Das Vorlesen läuft
gegen eine Attrappe von ``speechSynthesis`` mit einer lokalen und einer Netzstimme.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from conftest import BEISPIELE, js
from daidalos.cli import main

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")

NAME = "vom-aufruf-zum-strich"
AUFRUFE = "kern/src/commonMain/kotlin/de/beispiel/aufrufe/"
ZEICHNE_ALLES = "funktion:" + AUFRUFE + "Werkzeug.kt#zeichneAlles/1"
ZEICHNE = "funktion:" + AUFRUFE + "Strich.kt#Strich.zeichne/1"
LOKAL = ("file:", "data:", "blob:")
BEREIT = "document.documentElement.dataset.zustand === 'bereit'"
FERTIG = "document.documentElement.dataset.fuehrung === 'fertig'"

# Attrappe der Web Speech API: eine Netzstimme (zuerst), eine lokale deutsche Stimme. speak()
# merkt sich Stimme und Text und meldet das Ende nach 50 ms.
ATTRAPPE = """
(() => {
  const stimmen = window.__stimmen || [
    { name: 'Netz', lang: 'de-DE', localService: false, voiceURI: 'netz' },
    { name: 'Lokal', lang: 'de-DE', localService: true, voiceURI: 'lokal' },
    { name: 'Local English', lang: 'en-US', localService: true, voiceURI: 'en' }
  ];
  window.__gesprochen = [];
  const ss = {
    getVoices: () => stimmen, speaking: false,
    speak(u) {
      window.__gesprochen.push({ stimme: u.voice && u.voice.name, text: u.text, rate: u.rate });
      setTimeout(() => { if (u.onend) u.onend({}); }, 50); },
    cancel() {}, pause() { window.__pausiert = true; }, resume() { window.__pausiert = false; },
    addEventListener() {}
  };
  Object.defineProperty(window, 'speechSynthesis', { value: ss, configurable: true });
  window.SpeechSynthesisUtterance = function (text) { this.text = text; };
})();
"""


@pytest.fixture(scope="module")
def ziel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """mini_aufrufe mit der Beispielführung; Schritt 2 veraltet, eine zweite Führung mit einem
    kaputten Schritt (3)."""
    ziel = tmp_path_factory.mktemp("f") / "mini_aufrufe"
    shutil.copytree(BEISPIELE / "mini_aufrufe", ziel)
    assert main(["scan", str(ziel)]) == 0
    entwurf = ziel / "docs/daidalos/entwurf-fuehrung.json"
    assert main(["fuehrung", "uebernehmen", str(entwurf), str(ziel)]) == 0
    ordner = ziel / "docs/daidalos/fuehrungen"
    daten = json.loads((ordner / f"{NAME}.json").read_text(encoding="utf-8"))
    daten["schritte"][1]["hashes"]["datei:" + AUFRUFE + "Strich.kt"] = "sha256:alt"
    (ordner / f"{NAME}.json").write_text(json.dumps(daten), encoding="utf-8")
    kaputt = json.loads(json.dumps(daten))
    kaputt["name"] = "mit-luecke"
    kaputt["titel"] = "Mit Lücke"
    kaputt["schritte"][2]["hervorheben"].append("funktion:gibt/es#nicht/0")
    (ordner / "mit-luecke.json").write_text(json.dumps(kaputt), encoding="utf-8")
    assert main(["render", str(ziel)]) == 0
    return ziel


def karte(ziel: Path) -> Path:
    return ziel / "docs" / "daidalos" / "karte.html"


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as fehler:  # Chromium nicht installiert
            pytest.skip(f"Chromium nicht verfügbar: {fehler}")
        yield b
        b.close()


def _seite(browser: Any, init: str | None) -> Iterator[tuple[Any, list[str]]]:
    kontext = browser.new_context(viewport={"width": 1400, "height": 900})
    if init:
        kontext.add_init_script(init)
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


@pytest.fixture
def seite(browser: Any) -> Iterator[tuple[Any, list[str]]]:
    yield from _seite(browser, ATTRAPPE)


@pytest.fixture
def seite_netz(browser: Any) -> Iterator[tuple[Any, list[str]]]:
    """Nur eine Netzstimme: Vorlesen bleibt aus."""
    nur_netz = "window.__stimmen = [{ name: 'Netz', lang: 'de-DE', localService: false }];"
    yield from _seite(browser, nur_netz + ATTRAPPE)


def oeffne(s: Any, pfad: Path, hash_teil: str = "") -> None:
    s.goto(pfad.as_uri() + hash_teil)
    s.wait_for_function(BEREIT, timeout=30000)


def warte_schritt(s: Any, nr: int) -> None:
    s.wait_for_function(
        f"daidalos.fuehrung.stand().nr === {nr} && {FERTIG} && {BEREIT}", timeout=30000
    )


def stand(s: Any) -> dict[str, Any]:
    return s.evaluate("daidalos.fuehrung.stand()")


def leiste(s: Any) -> str:
    return s.inner_text("#fuehrung")


# ---------------------------------------------------------------- Liste und Start


def test_liste_und_start(seite: Any, ziel: Path) -> None:
    s, fehler = seite
    oeffne(s, karte(ziel))
    assert s.is_visible("#fuehrungen-knopf")
    assert not s.is_visible("#fuehrung")
    s.click("#fuehrungen-knopf")
    eintraege = s.locator("#f-liste li")
    assert eintraege.count() == 2
    text = s.inner_text("#f-liste")
    assert "Vom Aufruf bis zum Strich" in text
    assert "Was passiert, wenn zeichneAlles einen Strich zeichnet?" in text
    assert "4 Schritte" in text
    s.click(f"[data-fuehrung='{NAME}']")
    warte_schritt(s, 1)
    assert s.evaluate("location.hash") == f"#fuehrung={NAME}&schritt=1"
    assert s.is_visible("#fuehrung")
    t = leiste(s)
    assert "Schritt 1 von 4" in t
    assert "Zwei Module" in t
    assert "app/src/main/kotlin/de/beispiel/app/Haupt.kt:9" in t
    assert s.evaluate("daidalos.zustand.ebene") == "modul"
    assert fehler == []


def test_ohne_fuehrungen_kein_knopf(seite: Any, tmp_path: Path) -> None:
    s, _ = seite
    leer = tmp_path / "leer"
    shutil.copytree(BEISPIELE / "mini_aufrufe", leer)
    assert main(["scan", str(leer)]) == 0
    assert main(["render", str(leer)]) == 0
    oeffne(s, karte(leer))
    assert not s.is_visible("#fuehrungen-knopf")


# ---------------------------------------------------------------- Weiter, Zurück, Tastatur


def test_weiter_zurueck_tastatur_und_ansicht(seite: Any, ziel: Path) -> None:
    s, fehler = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}")
    warte_schritt(s, 1)
    s.click("[data-f='weiter']")
    warte_schritt(s, 2)
    assert s.evaluate("daidalos.zustand.ebene") == "datei"
    s.keyboard.press("ArrowRight")
    warte_schritt(s, 3)
    # Ansicht wechselt: Wirkungsweg vorwärts ab zeichneAlles, Tiefe 2
    assert s.evaluate("daidalos.zustand.ebene") == "funktion"
    assert s.evaluate("daidalos.zustand.weg") == {
        "art": "weg",
        "start": ZEICHNE_ALLES,
        "richtung": "vor",
        "tiefe": 2,
    }
    s.keyboard.press("ArrowLeft")
    warte_schritt(s, 2)
    s.keyboard.press(" ")
    warte_schritt(s, 3)
    s.click("[data-f='weiter']")
    warte_schritt(s, 4)
    assert s.is_disabled("[data-f='weiter']")
    assert s.evaluate("location.hash") == f"#fuehrung={NAME}&schritt=4"
    # Bedienung bleibt frei; „Ansicht“ stellt die Ansicht des Schritts wieder her.
    s.click("#ebenen [data-ebene='modul']")
    s.wait_for_function(f"daidalos.zustand.ebene === 'modul' && {BEREIT}")
    s.click("[data-f='ansicht']")
    warte_schritt(s, 4)
    assert s.evaluate("daidalos.zustand.ebene") == "funktion"
    assert s.evaluate("daidalos.zustand.auswahl.id") == ZEICHNE
    s.keyboard.press("Escape")
    assert not s.is_visible("#fuehrung")
    assert stand(s)["name"] is None
    assert "fuehrung=" not in s.evaluate("location.hash")
    assert fehler == []


def test_kamera_gleitet(seite: Any, ziel: Path) -> None:
    s, _ = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}")
    warte_schritt(s, 1)
    s.click("[data-f='weiter']")
    s.wait_for_function("daidalos.fuehrung.stand().nr === 2 && daidalos.cy.animated()")
    warte_schritt(s, 2)
    s.wait_for_timeout(s.evaluate("daidalos.fuehrung.KAMERA_MS") + 100)
    assert s.evaluate("daidalos.cy.animated()") is False


# ---------------------------------------------------------------- Hervorhebung


def test_hervorhebung_der_reihe_nach(seite: Any, ziel: Path) -> None:
    s, fehler = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}&schritt=3")
    warte_schritt(s, 3)
    erwartet = [
        ZEICHNE_ALLES,
        f"kante:ruft:{ZEICHNE_ALLES}->{ZEICHNE}:produktiv",
        ZEICHNE,
    ]
    hervor = stand(s)["hervor"]
    assert [h["id"] for h in hervor] == erwartet
    takt = s.evaluate("daidalos.fuehrung.HERVOR_TAKT")
    abstaende = [b["zeit"] - a["zeit"] for a, b in pairwise(hervor)]
    assert all(takt - 60 <= d <= takt + 250 for d in abstaende), abstaende
    # Alle bleiben stehen; die ruft-Kante ist eine Kante der Funktionsebene.
    fhl = set(s.evaluate("daidalos.cy.elements('.fhl').map(e => e.id())"))
    assert {ZEICHNE_ALLES, ZEICHNE} <= fhl
    kante = hervor[1]["elemente"]
    assert len(kante) == 1 and s.evaluate(f"daidalos.cy.getElementById('{kante[0]}').isEdge()")
    assert kante[0] in fhl
    assert s.evaluate(f"daidalos.cy.getElementById('{ZEICHNE}').style('border-width')") == "3.5px"
    assert stand(s)["fehlt"] == []
    assert fehler == []


# ---------------------------------------------------------------- veraltet, kaputt


def test_veraltet_hinweis(seite: Any, ziel: Path) -> None:
    s, _ = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}&schritt=2")
    warte_schritt(s, 2)
    assert "Code hat sich geändert, Text evtl. veraltet" in leiste(s)
    s.keyboard.press("ArrowRight")
    warte_schritt(s, 3)
    assert "veraltet" not in leiste(s)


def test_kaputter_schritt_wird_uebersprungen(seite: Any, ziel: Path) -> None:
    s, fehler = seite
    oeffne(s, karte(ziel), "#fuehrung=mit-luecke&schritt=2")
    warte_schritt(s, 2)
    s.click("[data-f='weiter']")
    warte_schritt(s, 4)
    assert "Schritt 3 übersprungen" in leiste(s)
    assert s.evaluate("location.hash") == "#fuehrung=mit-luecke&schritt=4"
    s.keyboard.press("ArrowLeft")
    warte_schritt(s, 2)
    # Sprungadresse direkt auf den kaputten Schritt: weiter zum nächsten guten
    js(s, "daidalos.fuehrung.starte('mit-luecke', 2)")
    warte_schritt(s, 4)
    assert fehler == []


# ---------------------------------------------------------------- Vorlesen


def test_vorlesen_nur_lokale_stimme_und_automatisch(seite: Any, ziel: Path) -> None:
    s, fehler = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}")
    warte_schritt(s, 1)
    sprache = s.evaluate("daidalos.fuehrung.sprache()")
    assert sprache["stimmen"] == ["Lokal"]
    assert sprache["stimme"] == "Lokal"
    assert sprache["grund"] == ""
    assert s.is_enabled("#f-an")
    assert s.is_disabled("#f-auto")
    s.check("#f-an")
    s.wait_for_function("window.__gesprochen.length === 1")
    gesprochen = s.evaluate("window.__gesprochen")
    assert gesprochen[0]["stimme"] == "Lokal"
    assert gesprochen[0]["text"].startswith("Zwei Module. ")
    # Automatisch: nach dem Ende plus 1,5 s weiter
    s.check("#f-auto")
    warte_schritt(s, 2)
    s.wait_for_function("window.__gesprochen.length === 2")
    assert all(g["stimme"] == "Lokal" for g in s.evaluate("window.__gesprochen"))
    # Pause hält an
    s.click("#f-pause")
    assert stand(s)["pause"] is True
    s.wait_for_timeout(s.evaluate("daidalos.fuehrung.AUTO_PAUSE") + 400)
    assert stand(s)["nr"] == 2
    assert fehler == []


def test_tempo_und_stimme_werden_gemerkt(seite: Any, ziel: Path) -> None:
    s, _ = seite
    oeffne(s, karte(ziel), f"#fuehrung={NAME}")
    warte_schritt(s, 1)
    s.fill("#f-tempo", "1.2")
    s.dispatch_event("#f-tempo", "change")
    assert s.evaluate("localStorage.getItem('daidalos-tempo')") == "1.2"
    s.select_option("#f-stimme", "0")
    assert s.evaluate("localStorage.getItem('daidalos-stimme')") == "lokal"
    s.reload()
    s.wait_for_function(BEREIT)
    assert s.evaluate("daidalos.fuehrung.sprache().tempo") == 1.2


def test_ohne_lokale_stimme_ist_vorlesen_aus(seite_netz: Any, ziel: Path) -> None:
    s, _ = seite_netz
    oeffne(s, karte(ziel), f"#fuehrung={NAME}")
    warte_schritt(s, 1)
    assert s.is_disabled("#f-an")
    grund = s.inner_text("#f-grund")
    assert "Keine deutsche Stimme auf diesem Rechner" in grund
    js(s, "daidalos.fuehrung.ladeStimmen()")
    assert s.evaluate("daidalos.fuehrung.sprache().stimme") is None
    assert s.evaluate("window.__gesprochen") == []
