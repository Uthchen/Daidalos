"""Browser-Probe: karte.html in Chromium (Playwright).

Läuft nur, wenn Playwright und Chromium installiert sind (``uv run playwright install chromium``),
sonst übersprungen. In der CI nur unter Ubuntu.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main

pytestmark = pytest.mark.browser
sync_api = pytest.importorskip("playwright.sync_api")

BEREIT = "document.documentElement.dataset.zustand === 'bereit'"
CODE = {"kotlin", "java", "c", "cpp"}


@pytest.fixture(scope="module")
def karte(tmp_path_factory: pytest.TempPathFactory) -> Path:
    ausgabe = tmp_path_factory.mktemp("karte")
    argumente = [
        "render",
        str(BEISPIELE / "mini_modulgraph"),
        "--daten",
        str(ERWARTET / "mini_modulgraph.daidalos.json"),
        "--ausgabe",
        str(ausgabe),
    ]
    assert main(argumente) == 0
    return ausgabe / "karte.html"


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
def seite(browser: Any, karte: Path) -> Iterator[tuple[Any, list[str]]]:
    kontext = browser.new_context(viewport={"width": 1400, "height": 900})
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
    yield s, fehler
    kontext.close()


def oeffne(s: Any, karte: Path, hash_teil: str = "") -> None:
    s.goto(karte.as_uri() + hash_teil)
    s.wait_for_function(BEREIT, timeout=30000)


def warte(s: Any) -> None:
    s.wait_for_timeout(50)
    s.wait_for_function(BEREIT, timeout=30000)


def messung() -> dict[str, Any]:
    return json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))


def erwartete_knoten(ebene: str) -> int:
    d = messung()
    knoten = d["knoten"]
    gruppen = [k for k in knoten if k["art"] in ("modul", "ordner")]
    if ebene == "modul":
        return len(gruppen)
    mit_kante = {k[s] for k in d["kanten"] if k["art"] in ("nutzt", "jni") for s in ("von", "nach")}
    dateien = [
        k for k in knoten if k["art"] == "datei" and (k["sprache"] in CODE or k["id"] in mit_kante)
    ]
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


def test_zyklus_befund_hebt_knoten_hervor(seite: tuple[Any, list[str]], karte: Path) -> None:
    s, fehler = seite
    befund = next(
        b
        for b in messung()["befunde"]
        if b["regel"] == "zyklus" and b["beleg"]["ebene"] == "datei" and len(b["knoten"]) == 3
    )
    oeffne(s, karte)
    s.click(f'ol.befunde button[data-befund="{befund["id"]}"]')
    warte(s)
    s.wait_for_timeout(400)
    hervor = s.evaluate("window.daidalos.cy.nodes('.hl').map(n => n.id()).sort()")
    assert hervor == sorted(befund["knoten"])
    einstiege = s.evaluate("window.daidalos.cy.nodes('.einstieg').map(n => n.id()).sort()")
    assert einstiege == sorted(e["knoten"] for e in befund["beleg"]["einstiege"])
    trenn = s.evaluate("window.daidalos.cy.edges('.trenn').map(e => e.id())")
    assert trenn == [befund["beleg"]["trennstelle"]]
    assert s.evaluate("location.hash") == "#befund=" + quote(befund["id"], safe="")
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
