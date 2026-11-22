"""Befehlszeile: ``daidalos scan [ZIEL]``."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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


def _strukturzeilen(daten: dict[str, Any]) -> list[str]:
    """Zusammenfassung des Strukturgraphen für stdout."""
    knoten = daten["knoten"]
    kanten = daten["kanten"]
    befunde = daten["befunde"]
    module = sum(1 for k in knoten if k["art"] == "modul")
    pakete = sum(1 for k in knoten if k["art"] == "paket")
    gradle = sum(1 for k in kanten if k["art"].startswith("gradle-"))
    datei_kanten = [k for k in kanten if k["art"] == "nutzt" and k["von"].startswith("datei:")]
    sicher = sum(1 for k in datei_kanten if k["sicher"])
    jni = sum(k["gewicht"] for k in kanten if k["art"] == "jni")
    jni_offen = sum(1 for b in befunde if b["regel"] == "jni-ohne-gegenstueck")
    unaufgeloest = sum(len(b["beleg"]["importe"]) for b in befunde if b["regel"] == "unaufgeloest")

    zyklen: dict[tuple[str, str], int] = {}
    for b in befunde:
        if b["regel"] != "zyklus":
            continue
        ebene = b["beleg"]["ebene"]
        if "kantenart" in b["beleg"]:
            ebene = f"{ebene} ({b['beleg']['kantenart']})"
        schluessel = (ebene, b["beleg"]["rolle"])
        zyklen[schluessel] = zyklen.get(schluessel, 0) + 1
    zeilen = [
        f"Module:    {module} (Gradle-Kanten: {gradle})",
        f"Pakete:    {pakete}",
        f"Kanten:    {len(datei_kanten)} zwischen Dateien "
        f"(sicher: {sicher}, unsicher: {len(datei_kanten) - sicher}; "
        f"unaufgelöste Importe: {unaufgeloest})",
        f"JNI:       {jni} Paare (ohne Gegenstück: {jni_offen})",
    ]
    ebenen = ("datei", "paket", "modul (nutzt)", "modul (gradle)")
    teile = []
    for ebene in ebenen:
        produktiv = zyklen.get((ebene, "produktiv"), 0)
        mit_tests = zyklen.get((ebene, "mit-tests"), 0)
        teile.append(f"{ebene} {produktiv}/{mit_tests}")
    zeilen.append(f"Zyklen:    {', '.join(teile)} (produktiv/mit Tests)")
    return zeilen


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

    alle_knoten = ergebnis.daten["knoten"]
    knoten = [k for k in alle_knoten if k["art"] == "datei"]
    zeilen = sum(k.get("zeilen", 0) for k in knoten)
    fremd = sum(1 for k in knoten if k.get("fremd"))
    sprachen = ", ".join(f"{name} {anzahl}" for name, anzahl in zaehle_sprachen(knoten)[:6])
    modus = "git" if ergebnis.git_modus else "Verzeichnisdurchlauf"
    print(f"Dateien:   {len(knoten)} (davon fremd: {fremd})")
    print(f"Zeilen:    {zeilen}")
    print(f"Sprachen:  {sprachen or '-'}")
    for zeile in _strukturzeilen(ergebnis.daten):
        print(zeile)
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
