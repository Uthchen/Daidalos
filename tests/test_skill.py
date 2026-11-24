"""Skill und Plugin: SKILL.md nennt nur Befehle, die es im CLI gibt; Plugin-Dateien sind gültig."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from conftest import ERWARTET
from daidalos.cli import _baue_parser
from daidalos.deutung import pruefe_entwurf

REPO = Path(__file__).parents[1]
SKILL = REPO / "skills" / "daidalos" / "SKILL.md"
# ``daidalos`` gefolgt von Befehl, Unterbefehl und Optionen, bis Zeilen- oder Code-Ende.
_AUFRUF = re.compile(r"(?<![\w/-])daidalos((?: [^\n`]*)?)")


def _unterbefehle(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for aktion in parser._actions:
        if isinstance(aktion, argparse._SubParsersAction):
            return dict(aktion.choices)
    return {}


def _optionen(parser: argparse.ArgumentParser) -> set[str]:
    return {o for a in parser._actions for o in a.option_strings}


def _hilfe_befehle(parser: argparse.ArgumentParser) -> set[str]:
    """Befehle, wie sie in der argparse-Hilfe stehen (eingerückte Zeilen unter BEFEHL)."""
    hilfe = parser.format_help()
    return set(re.findall(r"^    (\w+)\s", hilfe, re.MULTILINE))


def test_skill_nennt_nur_vorhandene_befehle() -> None:
    parser = _baue_parser()
    befehle = _unterbefehle(parser)
    assert set(befehle) == _hilfe_befehle(parser)
    text = SKILL.read_text(encoding="utf-8")
    gefunden = 0
    for treffer in _AUFRUF.finditer(text):
        woerter = treffer.group(1).split()
        if not woerter:
            continue
        if woerter[0].startswith("-"):
            assert woerter[0] in _optionen(parser), woerter[0]
            gefunden += 1
            continue
        if not re.fullmatch(r"[a-z]+", woerter[0]):
            continue  # Fließtext wie „daidalos.json“ oder „daidalos misst“
        if woerter[0] not in befehle:
            # Nur Fließtext, kein Aufruf: das Wort danach ist kein Befehl, z. B. „daidalos ist“.
            assert woerter[0] not in {"zusammenfassen", "arbeitsblaetter", "pruefe"}, woerter
            continue
        unter = befehle[woerter[0]]
        rest = woerter[1:]
        unterbefehle = _unterbefehle(unter)
        if unterbefehle:
            assert rest and rest[0] in unterbefehle, woerter
            unter = unterbefehle[rest[0]]
            rest = rest[1:]
        for wort in rest:
            if wort.startswith("--"):
                assert wort.split("=")[0] in _optionen(unter), (woerter, wort)
        gefunden += 1
    # Jeder Befehl des CLI kommt im Skill vor.
    for befehl in befehle:
        assert re.search(rf"daidalos {befehl}\b", text), befehl
    assert gefunden >= 10


def test_skill_frontmatter() -> None:
    text = SKILL.read_text(encoding="utf-8")
    kopf = text.split("---")[1]
    assert re.search(r"^name: daidalos$", kopf, re.MULTILINE)
    assert re.search(r"^description: \".+\"$", kopf, re.MULTILINE)


def test_plugin_dateien() -> None:
    plugin = json.loads((REPO / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "daidalos"
    for feld in ("version", "description", "author", "license"):
        assert plugin[feld]
    assert plugin["author"]["name"]
    from daidalos import __version__

    assert plugin["version"] == __version__

    markt = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    for feld in ("name", "owner", "plugins"):
        assert markt[feld]
    assert markt["owner"]["name"]
    eintrag = next(p for p in markt["plugins"] if p["name"] == plugin["name"])
    assert eintrag["source"] == "./"
    assert (REPO / eintrag["source"] / "skills/daidalos/SKILL.md").is_file()


def test_beispiel_entwurf_passt() -> None:
    entwurf = json.loads(
        (REPO / "skills/daidalos/vorlagen/entwurf-beispiel.json").read_text(encoding="utf-8")
    )
    messung = json.loads((ERWARTET / "mini_modulgraph.daidalos.json").read_text(encoding="utf-8"))
    assert pruefe_entwurf(entwurf, messung) == []


def test_skill_ablauf_fuehrung() -> None:
    """Der zweite Ablauf (A10): eigener Abschnitt mit Übernehmen, Prüfen, Render und Link."""
    text = SKILL.read_text(encoding="utf-8")
    assert "führe mich" in text.split("---")[1]  # Auslöser in der description
    abschnitt = text.split("## Führung erstellen", 1)[1]
    for befehl in (
        "daidalos fuehrung uebernehmen",
        "daidalos fuehrung pruefen",
        "daidalos render",
        "daidalos aufrufe",
        "daidalos pfad",
    ):
        assert befehl in abschnitt, befehl
    assert "karte.html#fuehrung=<name>" in abschnitt
    assert "Körper" in abschnitt  # Funktionskörper lesen
    assert "Nur in `docs/daidalos/`" in abschnitt or "nur in `docs/daidalos/`" in abschnitt.lower()
    assert (SKILL.parent / "vorlagen" / "fuehrung-beispiel.json").is_file()
