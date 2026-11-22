"""Befehlszeile: ``daidalos scan [ZIEL]``."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from daidalos import __version__
from daidalos.export import schreibe_json
from daidalos.konfiguration import DATEINAME, KonfigurationsFehler, lade_konfiguration
from daidalos.scanner import scanne, zaehle_sprachen

EXIT_OK = 0
EXIT_UNERWARTET = 1
EXIT_BEDIENFEHLER = 2

STANDARD_AUSGABE = Path("docs") / "daidalos" / "daidalos.json"


class _Parser(argparse.ArgumentParser):
    """argparse mit deutschen Fehlermeldungen; Bedienfehler enden mit Exit-Code 2."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_BEDIENFEHLER, f"Fehler: {message}\n")


def _baue_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="daidalos",
        description="Daidalos misst, wie die Teile einer Codebase verflochten sind.",
    )
    parser.add_argument("--version", action="version", version=f"daidalos {__version__}")
    befehle = parser.add_subparsers(dest="befehl", metavar="BEFEHL", parser_class=_Parser)
    scan = befehle.add_parser("scan", help="Dateien des Zielrepos erfassen")
    scan.add_argument("ziel", nargs="?", default=".", metavar="ZIEL", help="Zielrepo (Standard: .)")
    scan.add_argument(
        "--ausgabe",
        metavar="DATEI",
        help="Ausgabedatei (Standard: <ZIEL>/docs/daidalos/daidalos.json)",
    )
    scan.add_argument(
        "--konfiguration",
        metavar="DATEI",
        help=f"Konfigurationsdatei (Standard: <ZIEL>/{DATEINAME})",
    )
    return parser


def _anzeigepfad(pfad: Path) -> str:
    try:
        return pfad.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(pfad.resolve())


def _befehl_scan(argumente: argparse.Namespace) -> int:
    ziel = Path(argumente.ziel)
    if not ziel.is_dir():
        print(f"Fehler: Ziel {ziel} existiert nicht oder ist kein Ordner", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    if argumente.konfiguration is not None:
        konfig_pfad = Path(argumente.konfiguration)
        muss_existieren = True
    else:
        konfig_pfad = ziel / DATEINAME
        muss_existieren = False
    try:
        konfiguration = lade_konfiguration(konfig_pfad, muss_existieren=muss_existieren)
    except KonfigurationsFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER

    ausgabe = Path(argumente.ausgabe) if argumente.ausgabe else ziel / STANDARD_AUSGABE

    beginn = time.perf_counter()
    ergebnis = scanne(ziel, konfiguration)
    schreibe_json(ergebnis.daten, ausgabe)
    dauer = time.perf_counter() - beginn

    knoten = ergebnis.daten["knoten"]
    zeilen = sum(k.get("zeilen", 0) for k in knoten)
    fremd = sum(1 for k in knoten if k.get("fremd"))
    sprachen = ", ".join(f"{name} {anzahl}" for name, anzahl in zaehle_sprachen(knoten)[:6])
    modus = "git" if ergebnis.git_modus else "Verzeichnisdurchlauf"
    print(f"Dateien:   {len(knoten)} (davon fremd: {fremd})")
    print(f"Zeilen:    {zeilen}")
    print(f"Sprachen:  {sprachen or '-'}")
    print(f"Quelle:    {modus}")
    print(f"Ausgabe:   {_anzeigepfad(ausgabe)}")
    print(f"Laufzeit:  {dauer:.2f} s")
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(errors="replace")
    parser = _baue_parser()
    argumente = parser.parse_args(argv)
    if argumente.befehl is None:
        parser.print_help(sys.stderr)
        return EXIT_BEDIENFEHLER
    try:
        return _befehl_scan(argumente)
    except Exception as fehler:  # unerwarteter Fehler: kurz melden, Code 1
        print(f"Unerwarteter Fehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
        return EXIT_UNERWARTET
