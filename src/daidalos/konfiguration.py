"""Konfiguration aus ``daidalos.toml`` im Zielrepo (Format v1)."""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DATEINAME = "daidalos.toml"
STANDARD_EDITOR_BEFEHL = "code -g {datei}:{zeile}"

# Gelten immer, zusätzlich zu .gitignore und [scan].ausschliessen.
EINGEBAUTE_AUSSCHLUESSE: tuple[str, ...] = (
    ".git/",
    ".gradle/",
    ".idea/",
    ".vscode/",
    ".kotlin/",
    "node_modules/",
    "__pycache__/",
    "build/",
    "out/",
    # Unreal
    "Binaries/",
    "Intermediate/",
    "Saved/",
    "DerivedDataCache/",
    # Daidalos misst sich nicht selbst.
    "/docs/daidalos/",
)

Warner = Callable[[str], None]


class KonfigurationsFehler(Exception):
    """Die Konfiguration ist nicht lesbar oder hat falsche Typen."""


@dataclass(frozen=True)
class ScanKonfiguration:
    ausschliessen: tuple[str, ...] = ()
    fremd: tuple[str, ...] = ()


@dataclass(frozen=True)
class EditorKonfiguration:
    befehl: str = STANDARD_EDITOR_BEFEHL


@dataclass(frozen=True)
class ProjektKonfiguration:
    # Anzeigename des Zielrepos; ohne Angabe gilt der Ordnername.
    name: str | None = None


@dataclass(frozen=True)
class Konfiguration:
    projekt: ProjektKonfiguration = field(default_factory=ProjektKonfiguration)
    scan: ScanKonfiguration = field(default_factory=ScanKonfiguration)
    editor: EditorKonfiguration = field(default_factory=EditorKonfiguration)
    # Datei, aus der gelesen wurde; None, wenn keine vorhanden war.
    quelle: Path | None = None


def warne_stderr(text: str) -> None:
    print(f"Warnung: {text}", file=sys.stderr)


_BEKANNT: dict[str, frozenset[str]] = {
    "projekt": frozenset({"name"}),
    "scan": frozenset({"ausschliessen", "fremd"}),
    "editor": frozenset({"befehl"}),
}


def lade_konfiguration(
    pfad: Path, *, muss_existieren: bool = False, warne: Warner = warne_stderr
) -> Konfiguration:
    """Liest die Konfiguration. Fehlt die Datei, gelten die Standardwerte.

    Unbekannte Abschnitte und Schlüssel ergeben eine Warnung, falsche Typen einen
    ``KonfigurationsFehler``.
    """
    if not pfad.is_file():
        if muss_existieren:
            raise KonfigurationsFehler(f"{pfad}: Konfigurationsdatei nicht gefunden")
        return Konfiguration()
    try:
        with pfad.open("rb") as datei:
            daten = tomllib.load(datei)
    except tomllib.TOMLDecodeError as fehler:
        raise KonfigurationsFehler(f"{pfad}: kein gültiges TOML ({fehler})") from fehler
    except OSError as fehler:
        raise KonfigurationsFehler(f"{pfad}: nicht lesbar ({fehler})") from fehler

    for abschnitt, inhalt in daten.items():
        if abschnitt not in _BEKANNT:
            warne(f"{pfad}: unbekannter Abschnitt [{abschnitt}] wird ignoriert")
            continue
        if not isinstance(inhalt, dict):
            raise KonfigurationsFehler(f"{pfad}: [{abschnitt}] muss ein Abschnitt sein")
        for schluessel in inhalt:
            if schluessel not in _BEKANNT[abschnitt]:
                warne(f"{pfad}: unbekannter Schlüssel [{abschnitt}].{schluessel} wird ignoriert")

    projekt = daten.get("projekt", {})
    scan = daten.get("scan", {})
    editor = daten.get("editor", {})
    name = projekt.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise KonfigurationsFehler(
            f"{pfad}: [projekt].name muss eine nicht leere Zeichenkette sein"
        )
    return Konfiguration(
        projekt=ProjektKonfiguration(name=name),
        scan=ScanKonfiguration(
            ausschliessen=_liste_von_texten(pfad, scan, "scan", "ausschliessen"),
            fremd=_liste_von_texten(pfad, scan, "scan", "fremd"),
        ),
        editor=EditorKonfiguration(
            befehl=_text(pfad, editor, "editor", "befehl", STANDARD_EDITOR_BEFEHL),
        ),
        quelle=pfad,
    )


def _liste_von_texten(
    pfad: Path, abschnitt: dict[str, Any], name: str, schluessel: str
) -> tuple[str, ...]:
    wert = abschnitt.get(schluessel, [])
    if not isinstance(wert, list) or not all(isinstance(eintrag, str) for eintrag in wert):
        raise KonfigurationsFehler(
            f"{pfad}: [{name}].{schluessel} muss eine Liste von Zeichenketten sein"
        )
    return tuple(wert)


def _text(pfad: Path, abschnitt: dict[str, Any], name: str, schluessel: str, standard: str) -> str:
    wert = abschnitt.get(schluessel, standard)
    if not isinstance(wert, str):
        raise KonfigurationsFehler(f"{pfad}: [{name}].{schluessel} muss eine Zeichenkette sein")
    return wert
