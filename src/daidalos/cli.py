"""Befehlszeile von Daidalos: scan, render, pfad, zusammenfassung, arbeitsblatt, deutung."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from daidalos import __version__
from daidalos.arbeitsblatt import Arbeitsblatt, ArbeitsblattFehler
from daidalos.deutung import (
    DeutungsFehler,
    EntwurfFehler,
    gleiche_ab,
    lies_deutung,
    lies_json,
    uebernimm,
)
from daidalos.export import als_json, schreibe_json, schreibe_text
from daidalos.konfiguration import (
    DATEINAME,
    Konfiguration,
    KonfigurationsFehler,
    lade_konfiguration,
)
from daidalos.pfad import EBENEN, PfadFehler, ebene_von, finde_knoten, suche_weg, weg_als_json
from daidalos.render import (
    RenderFehler,
    anzeigename,
    baue_karte,
    baue_karte_md,
    einstellungen_fuer_karte,
    lade_messung,
    wurzel_relativ,
)
from daidalos.scanner import scanne, zaehle_sprachen
from daidalos.zusammenfassung import Zusammenfassung, finde_offenes, wichtige_dateien

EXIT_OK = 0
EXIT_UNERWARTET = 1
EXIT_BEDIENFEHLER = 2

STANDARD_ORDNER = Path("docs") / "daidalos"
STANDARD_AUSGABE = STANDARD_ORDNER / "daidalos.json"
STANDARD_DEUTUNG = STANDARD_ORDNER / "deutung.json"


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

    render = befehle.add_parser("render", help="karte.html und KARTE.md erzeugen")
    render.add_argument(
        "ziel", nargs="?", default=".", metavar="ZIEL", help="Zielrepo (Standard: .)"
    )
    render.add_argument(
        "--daten", metavar="DATEI", help="Messung (Standard: <ZIEL>/docs/daidalos/daidalos.json)"
    )
    render.add_argument(
        "--deutung",
        metavar="DATEI",
        help="Deutung (Standard: <ZIEL>/docs/daidalos/deutung.json, falls vorhanden)",
    )
    render.add_argument(
        "--ausgabe", metavar="ORDNER", help="Ausgabeordner (Standard: <ZIEL>/docs/daidalos/)"
    )
    render.add_argument(
        "--konfiguration",
        metavar="DATEI",
        help=f"Konfigurationsdatei für [editor] link (Standard: <ZIEL>/{DATEINAME})",
    )

    pfad = befehle.add_parser("pfad", help="kürzesten belegten Weg zwischen zwei Knoten zeigen")
    pfad.add_argument("von", metavar="VON", help="Id oder eindeutiger Suchbegriff")
    pfad.add_argument("nach", metavar="NACH", help="Id oder eindeutiger Suchbegriff")
    pfad.add_argument("--ebene", choices=EBENEN, help="Ebene (Standard: aus den Knoten)")
    pfad.add_argument("--mit-tests", action="store_true", help="auch Test-Kanten verwenden")
    pfad.add_argument(
        "--daten", metavar="DATEI", help="Messung (Standard: ./docs/daidalos/daidalos.json)"
    )
    pfad.add_argument("--json", action="store_true", help="Ausgabe als JSON")

    zusammen = befehle.add_parser(
        "zusammenfassung", help="kurze Übersicht der Messung und was in der Deutung offen ist"
    )
    _ziel_daten_deutung(zusammen)
    zusammen.add_argument("--json", action="store_true", help="Ausgabe als JSON")

    blatt = befehle.add_parser(
        "arbeitsblatt", help="Arbeitsblatt für ein Modul, ein Paket oder eine Datei"
    )
    blatt.add_argument("knoten", metavar="KNOTEN", help="Id oder eindeutiger Suchbegriff")
    _ziel_daten_deutung(blatt)

    deutung = befehle.add_parser("deutung", help="Entwurf übernehmen oder deutung.json prüfen")
    deutung_befehle = deutung.add_subparsers(
        dest="deutung_befehl", metavar="AKTION", parser_class=_Parser, required=True
    )
    uebernehmen = deutung_befehle.add_parser(
        "uebernehmen", help="Entwurf prüfen, Hashes einsetzen und in deutung.json übernehmen"
    )
    uebernehmen.add_argument("entwurf", metavar="ENTWURF", help="Entwurf (JSON ohne hash)")
    _ziel_daten_deutung(uebernehmen)
    pruefen = deutung_befehle.add_parser(
        "pruefen", help="veraltete, fehlende und tote Einträge melden (Exit-Code 1, wenn offen)"
    )
    _ziel_daten_deutung(pruefen)
    return parser


def _ziel_daten_deutung(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "ziel", nargs="?", default=".", metavar="ZIEL", help="Zielrepo (Standard: .)"
    )
    parser.add_argument(
        "--daten", metavar="DATEI", help="Messung (Standard: <ZIEL>/docs/daidalos/daidalos.json)"
    )
    parser.add_argument(
        "--deutung",
        metavar="DATEI",
        help="Deutung (Standard: <ZIEL>/docs/daidalos/deutung.json)",
    )


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
    zeilen.append(f"Zyklen:    {', '.join(teile)} (produktiv/zusätzlich mit Tests)")
    return zeilen


def _lade_konfiguration(ziel: Path, angegeben: str | None) -> Konfiguration:
    """``--konfiguration`` muss existieren; ohne Angabe gilt ``<ZIEL>/daidalos.toml``, falls da."""
    if angegeben is not None:
        return lade_konfiguration(Path(angegeben), muss_existieren=True)
    return lade_konfiguration(ziel / DATEINAME, muss_existieren=False)


def _befehl_scan(argumente: argparse.Namespace) -> int:
    ziel = Path(argumente.ziel)
    if not ziel.is_dir():
        print(f"Fehler: Ziel {ziel} existiert nicht oder ist kein Ordner", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    try:
        konfiguration = _lade_konfiguration(ziel, argumente.konfiguration)
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


def _befehl_render(argumente: argparse.Namespace) -> int:
    ziel = Path(argumente.ziel)
    daten_pfad = Path(argumente.daten) if argumente.daten else ziel / STANDARD_AUSGABE
    ausgabe = Path(argumente.ausgabe) if argumente.ausgabe else ziel / STANDARD_ORDNER
    deutung_pfad: Path | None
    if argumente.deutung:
        deutung_pfad = Path(argumente.deutung)
        if not deutung_pfad.is_file():
            print(f"Fehler: {deutung_pfad.as_posix()} fehlt", file=sys.stderr)
            return EXIT_BEDIENFEHLER
    else:
        deutung_pfad = ziel / STANDARD_ORDNER / "deutung.json"
        if not deutung_pfad.is_file():
            deutung_pfad = None
    try:
        konfiguration = _lade_konfiguration(ziel, argumente.konfiguration)
        messung = lade_messung(daten_pfad)
        deutung = gleiche_ab(lies_deutung(deutung_pfad), messung) if deutung_pfad else None
    except (RenderFehler, DeutungsFehler, KonfigurationsFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER

    beginn = time.perf_counter()
    einstellungen = einstellungen_fuer_karte(
        konfiguration.editor.link, wurzel_relativ(ziel, ausgabe)
    )
    karte = baue_karte(messung, deutung, einstellungen)
    schreibe_text(karte, ausgabe / "karte.html")
    schreibe_text(baue_karte_md(messung, deutung), ausgabe / "KARTE.md")
    dauer = time.perf_counter() - beginn
    groesse = len(karte.encode("utf-8")) / 1024 / 1024
    print(f"Deutung:   {_anzeigepfad(deutung_pfad) if deutung_pfad else '-'}")
    print(f"Karte:     {_anzeigepfad(ausgabe / 'karte.html')} ({groesse:.2f} MiB)")
    print(f"Bericht:   {_anzeigepfad(ausgabe / 'KARTE.md')}")
    print(f"Laufzeit:  {dauer:.2f} s")
    return EXIT_OK


def _pfad_fehler(fehler: PfadFehler) -> int:
    print(f"Fehler: {fehler}", file=sys.stderr)
    if fehler.treffer:
        print("Treffer:", file=sys.stderr)
        for treffer in fehler.treffer:
            print(f"  {treffer}", file=sys.stderr)
    return EXIT_BEDIENFEHLER


def _befehl_pfad(argumente: argparse.Namespace) -> int:
    daten_pfad = Path(argumente.daten) if argumente.daten else STANDARD_AUSGABE
    try:
        daten = lade_messung(daten_pfad)
        von = finde_knoten(daten, argumente.von, argumente.ebene)
        nach = finde_knoten(daten, argumente.nach, argumente.ebene)
    except RenderFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    except PfadFehler as fehler:
        return _pfad_fehler(fehler)
    ebene = ebene_von(von)
    if ebene is None or ebene != ebene_von(nach):
        print(
            f"Fehler: {von['id']} und {nach['id']} liegen auf verschiedenen Ebenen "
            f"({ebene_von(von)}, {ebene_von(nach)})",
            file=sys.stderr,
        )
        return EXIT_BEDIENFEHLER
    schritte = suche_weg(daten, von, nach, ebene, argumente.mit_tests)
    if argumente.json:
        ergebnis = weg_als_json(von, nach, ebene, argumente.mit_tests, schritte)
        print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK

    namen = {k["id"]: anzeigename(k) for k in daten["knoten"]}
    start, ende = namen[von["id"]], namen[nach["id"]]
    kanten = "nutzt- und Gradle-Kanten" if ebene == "modul" else "nutzt-Kanten"
    rolle = "mit Tests" if argumente.mit_tests else "nur produktiv"
    if schritte is None:
        print(f"Kein Weg von {start} nach {ende} über {kanten} ({rolle}, Ebene {ebene}).")
        return EXIT_OK
    if not schritte:
        print(f"{start} ist selbst das Ziel.")
        return EXIT_OK
    anzahl = f"{len(schritte)} Schritt" + ("e" if len(schritte) != 1 else "")
    print(f"Weg von {start} nach {ende} (Ebene {ebene}, {rolle}, {anzahl}):")
    for nr, schritt in enumerate(schritte, 1):
        arten = []
        for k in schritt.kanten:
            text = k["art"] + (f" {k['gewicht']}" if k.get("gewicht") else "")
            arten.append(text + ("" if k.get("sicher", True) else " unsicher"))
        print(f"  {nr}. {namen[schritt.von]} → {namen[schritt.nach]}  [{', '.join(arten)}]")
        for b in schritt.belege:
            was = b["symbol"] if "symbol" in b else b["konfiguration"]
            print(f"       {b['datei']}:{b['zeile']}  {was}")
    return EXIT_OK


def _pfade(argumente: argparse.Namespace) -> tuple[Path, Path, Path]:
    ziel = Path(argumente.ziel)
    daten = Path(argumente.daten) if argumente.daten else ziel / STANDARD_AUSGABE
    deutung = Path(argumente.deutung) if argumente.deutung else ziel / STANDARD_DEUTUNG
    return ziel, daten, deutung


def _lade_beides(daten: Path, deutung: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Messung und rohe Deutung (``None``, wenn die Datei fehlt)."""
    messung = lade_messung(daten)
    return messung, lies_deutung(deutung) if deutung.is_file() else None


def _befehl_zusammenfassung(argumente: argparse.Namespace) -> int:
    _, daten, deutung = _pfade(argumente)
    try:
        messung, roh = _lade_beides(daten, deutung)
    except (RenderFehler, DeutungsFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    zusammenfassung = Zusammenfassung(messung, roh)
    if argumente.json:
        print(als_json(zusammenfassung.als_json()), end="")
    else:
        print(zusammenfassung.als_markdown(), end="")
    return EXIT_OK


def _befehl_arbeitsblatt(argumente: argparse.Namespace) -> int:
    ziel, daten, deutung = _pfade(argumente)
    try:
        messung, roh = _lade_beides(daten, deutung)
        knoten = finde_knoten(messung, argumente.knoten, None)
        print(Arbeitsblatt(messung, ziel, roh).baue(knoten), end="")
    except (RenderFehler, DeutungsFehler, ArbeitsblattFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    except PfadFehler as fehler:
        return _pfad_fehler(fehler)
    return EXIT_OK


def _befehl_deutung(argumente: argparse.Namespace) -> int:
    if argumente.deutung_befehl == "uebernehmen":
        return _deutung_uebernehmen(argumente)
    return _deutung_pruefen(argumente)


def _anzahl(entwurf: dict[str, Any], schluessel: str) -> int:
    return len(entwurf.get(schluessel) or [])


def _deutung_uebernehmen(argumente: argparse.Namespace) -> int:
    _, daten, deutung = _pfade(argumente)
    try:
        messung, bestand = _lade_beides(daten, deutung)
        entwurf = lies_json(Path(argumente.entwurf))
        neu = uebernimm(entwurf, bestand, messung)
    except (RenderFehler, DeutungsFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    except EntwurfFehler as fehler:
        print(f"Fehler: {fehler}; nichts geschrieben.", file=sys.stderr)
        for problem in fehler.probleme:
            print(f"  {problem}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    schreibe_json(neu, deutung)
    print(
        f"Übernommen: {_anzahl(entwurf, 'beschreibungen')} Beschreibungen, "
        f"{_anzahl(entwurf, 'bereiche')} Bereiche, "
        f"{_anzahl(entwurf, 'einschaetzungen')} Einschätzungen, "
        f"{_anzahl(entwurf, 'kanten')} Kantentexte, {_anzahl(entwurf, 'entfernen')} entfernt"
    )
    print(
        f"Bestand:    {len(neu['beschreibungen'])} Beschreibungen, {len(neu['bereiche'])} "
        f"Bereiche, {len(neu['einschaetzungen'])} Einschätzungen, {len(neu['kanten'])} Kantentexte"
    )
    print(f"Deutung:    {_anzeigepfad(deutung)}")
    return EXIT_OK


def _deutung_pruefen(argumente: argparse.Namespace) -> int:
    _, daten, deutung = _pfade(argumente)
    try:
        messung, roh = _lade_beides(daten, deutung)
    except (RenderFehler, DeutungsFehler) as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_BEDIENFEHLER
    if roh is None:
        print(f"Hinweis: {_anzeigepfad(deutung)} fehlt; alles ist offen.")
    offen = finde_offenes(messung, roh, wichtige_dateien(messung))
    stand = offen.beschreibungen
    gruppen = (
        ("Beschreibung fehlt", sorted(i for i, s in stand.items() if s == "fehlt")),
        ("Beschreibung veraltet", sorted(i for i, s in stand.items() if s == "veraltet")),
        ("Befund ohne Einschätzung", offen.befunde),
        ("Toter Verweis", offen.tote_verweise),
    )
    for titel, eintraege in gruppen:
        for eintrag in eintraege:
            print(f"{titel}: {eintrag}")
    anzahl = sum(len(e) for _, e in gruppen)
    zaehlung = ", ".join(f"{titel} {len(e)}" for titel, e in gruppen)
    print(f"Offen: {anzahl} ({zaehlung})")
    return EXIT_OK if offen.leer else EXIT_UNERWARTET


BEFEHLE = {
    "scan": _befehl_scan,
    "render": _befehl_render,
    "pfad": _befehl_pfad,
    "zusammenfassung": _befehl_zusammenfassung,
    "arbeitsblatt": _befehl_arbeitsblatt,
    "deutung": _befehl_deutung,
}


def main(argv: Sequence[str] | None = None) -> int:
    # Ausgaben immer UTF-8, auch in Pipes unter Windows (sonst Codepage 1252 und keine Umlaute
    # für Werkzeuge wie den Skill, die die Ausgabe weiterlesen).
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    parser = _baue_parser()
    argumente = parser.parse_args(argv)
    if argumente.befehl is None:
        parser.print_help(sys.stderr)
        return EXIT_BEDIENFEHLER
    try:
        return BEFEHLE[argumente.befehl](argumente)
    except Exception as fehler:  # unerwarteter Fehler: kurz melden, Code 1
        print(f"Unerwarteter Fehler: {type(fehler).__name__}: {fehler}", file=sys.stderr)
        return EXIT_UNERWARTET
