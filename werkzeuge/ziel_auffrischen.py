"""Frischt einen Git-Klon eines Zielrepos auf und kartiert ihn: scan, render, offene Deutungen.

Nur für die Entwicklung im Daidalos-Repo. Ein Repo, das sich laufend ändert, wird nie am
Arbeitsbaum gescannt, sondern an einem eigenen Klon unter ``lokal/``, der genau einen Commit zeigt.
Am echten Repo (``quelle``) ändert sich nichts, auch nicht an dessen ``.git``.

Aufruf: ``uv run python werkzeuge/ziel_auffrischen.py NAME [--erzwingen] [--mit-detekt]``.
Mit ``--mit-detekt`` läuft nach dem Zurücksetzen der Befehl ``detekt`` des Ziels im Klon, damit die
SARIF-Dateien zum Commit des Klons passen.
Die Ziele stehen in ``lokal/ziele.toml`` (wird beim ersten Lauf mit einem Beispiel angelegt).

Exit-Codes: 0 Erfolg, 1 offene Deutungen nach dem Render, 2 Fehler (Git, Pfade, Konfiguration).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from daidalos.cli import main as daidalos
from daidalos.deutung import DeutungsFehler, lies_deutung
from daidalos.render import RenderFehler, lade_messung
from daidalos.zusammenfassung import finde_offenes, wichtige_dateien

EXIT_OK = 0
EXIT_OFFEN = 1
EXIT_FEHLER = 2

WURZEL = Path(__file__).resolve().parent.parent
ZIELE = Path("lokal") / "ziele.toml"
SCHLUESSEL = {"quelle", "klon", "ausgabe", "konfiguration", "zweig", "kopiere", "detekt"}
PFLICHT = ("quelle", "klon", "ausgabe")

BEISPIEL = """\
# Ziele für werkzeuge/ziel_auffrischen.py (nur lokal, nicht committen).
# Pfade relativ zur Daidalos-Wurzel oder absolut; "/" geht auch unter Windows.
#
# [beispiel]
# quelle = "../MeinProjekt"                          # echtes Repo, wird nur gelesen
# klon = "lokal/ziele/beispiel/klon"                 # muss unter lokal/ liegen
# ausgabe = "lokal/ziele/beispiel/daidalos"          # daidalos.json, deutung.json, Karte
# konfiguration = "lokal/ziele/beispiel/daidalos.toml"  # optional
# zweig = "main"                                     # optional, sonst origin/HEAD des Klons
# kopiere = ["local.properties"]                     # optional: aus der Quelle, nicht in Git
# detekt = ["gradlew.bat", "detekt"]                 # optional: Befehl für --mit-detekt (im Klon)
"""


class Fehler(Exception):
    """Abbruch mit Exit-Code 2 und klarer Meldung."""


@dataclass(frozen=True)
class Ziel:
    name: str
    quelle: Path
    klon: Path
    ausgabe: Path
    konfiguration: Path | None
    zweig: str | None
    # Dateien aus der Quelle, die der Build braucht und die nicht in Git sind (relativ, ohne ``..``)
    kopiere: tuple[str, ...] = ()
    # Befehl für ``--mit-detekt``, im Klon ausgeführt; ``None``: keiner eingetragen
    detekt: tuple[str, ...] | None = None


def _pfad(wurzel: Path, wert: object, schluessel: str, name: str) -> Path:
    if not isinstance(wert, str) or not wert.strip():
        raise Fehler(f"Ziel {name}: {schluessel} muss ein nicht leerer Text sein")
    pfad = Path(wert)
    return (pfad if pfad.is_absolute() else wurzel / pfad).resolve()


def lies_ziel(wurzel: Path, name: str) -> Ziel:
    datei = wurzel / ZIELE
    if not datei.is_file():
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(BEISPIEL, encoding="utf-8", newline="\n")
        raise Fehler(
            f"{ZIELE.as_posix()} fehlte und wurde mit einem Beispiel angelegt; "
            f"bitte Ziel {name} eintragen"
        )
    try:
        alle = tomllib.loads(datei.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as fehler:
        raise Fehler(f"{ZIELE.as_posix()} nicht lesbar: {fehler}") from fehler
    eintrag = alle.get(name)
    if not isinstance(eintrag, dict):
        bekannt = ", ".join(sorted(k for k, v in alle.items() if isinstance(v, dict))) or "keine"
        raise Fehler(f"Ziel {name} fehlt in {ZIELE.as_posix()} (bekannt: {bekannt})")
    unbekannt = sorted(set(eintrag) - SCHLUESSEL)
    if unbekannt:
        raise Fehler(f"Ziel {name}: unbekannte Schlüssel {', '.join(unbekannt)}")
    for schluessel in PFLICHT:
        if schluessel not in eintrag:
            raise Fehler(f"Ziel {name}: {schluessel} fehlt")
    zweig = eintrag.get("zweig")
    if zweig is not None and (not isinstance(zweig, str) or not zweig.strip()):
        raise Fehler(f"Ziel {name}: zweig muss ein nicht leerer Text sein")
    konfiguration = eintrag.get("konfiguration")
    if konfiguration is not None:
        konfiguration = _pfad(wurzel, konfiguration, "konfiguration", name)
    kopiere = _textliste(eintrag.get("kopiere", []), "kopiere", name)
    for datei in kopiere:
        teile = Path(datei).parts
        if not datei.strip() or datei[0] in "/\\" or ".." in teile or ":" in datei:
            raise Fehler(f"Ziel {name}: kopiere {datei!r} muss ein relativer Pfad ohne .. sein")
    detekt = eintrag.get("detekt")
    if detekt is not None:
        detekt = _textliste(detekt, "detekt", name)
        if not detekt:
            raise Fehler(f"Ziel {name}: detekt darf nicht leer sein")
    return Ziel(
        name=name,
        quelle=_pfad(wurzel, eintrag["quelle"], "quelle", name),
        klon=_pfad(wurzel, eintrag["klon"], "klon", name),
        ausgabe=_pfad(wurzel, eintrag["ausgabe"], "ausgabe", name),
        konfiguration=konfiguration,
        zweig=zweig,
        kopiere=kopiere,
        detekt=detekt,
    )


def _textliste(wert: object, schluessel: str, name: str) -> tuple[str, ...]:
    if not isinstance(wert, list) or not all(isinstance(t, str) for t in wert):
        raise Fehler(f"Ziel {name}: {schluessel} muss eine Liste von Texten sein")
    return tuple(wert)


def kopiere_dateien(ziel: Ziel) -> None:
    """Kopiert die Dateien aus ``kopiere`` von der Quelle in den frisch zurückgesetzten Klon."""
    for datei in ziel.kopiere:
        quelle = ziel.quelle / datei
        if not quelle.is_file():
            raise Fehler(f"kopiere: {datei} fehlt in der Quelle {ziel.quelle}")
        nach = ziel.klon / datei
        nach.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(quelle, nach)


def fuehre_detekt_aus(ziel: Ziel) -> float:
    """Führt den Befehl ``detekt`` im Klon aus; liefert die Laufzeit in Sekunden.

    Bricht der Befehl ab, steht seine Ausgabe in der Fehlermeldung (Exit-Code 2).
    """
    if ziel.detekt is None:
        raise Fehler(f"Ziel {ziel.name}: --mit-detekt braucht detekt = [...] in {ZIELE.as_posix()}")
    befehl = list(ziel.detekt)
    # Ein Programm im Klon (etwa gradlew.bat) mit vollem Pfad, sonst sucht Windows nur im PATH.
    if (ziel.klon / befehl[0]).is_file():
        befehl[0] = str(ziel.klon / befehl[0])
    beginn = time.perf_counter()
    try:
        lauf = subprocess.run(befehl, cwd=ziel.klon, capture_output=True)
    except OSError as fehler:
        befehl_text = " ".join(ziel.detekt)
        raise Fehler(f"detekt-Befehl {befehl_text} nicht ausführbar: {fehler}") from fehler
    dauer = time.perf_counter() - beginn
    if lauf.returncode != 0:
        ausgabe = (lauf.stdout + lauf.stderr).decode("utf-8", "replace").strip()
        raise Fehler(
            f"detekt-Befehl {' '.join(ziel.detekt)} brach ab (Exit-Code {lauf.returncode}) "
            f"nach {dauer:.1f} s:\n{ausgabe}"
        )
    return dauer


def _liegt_unter(pfad: Path, ordner: Path) -> bool:
    return pfad != ordner and pfad.is_relative_to(ordner)


def pruefe_pfade(wurzel: Path, ziel: Ziel) -> None:
    lokal = (wurzel / "lokal").resolve()
    if not _liegt_unter(ziel.klon, lokal):
        raise Fehler(f"Klon {ziel.klon} liegt nicht unter {lokal}; abgebrochen")
    if ziel.klon == ziel.quelle or _liegt_unter(ziel.klon, ziel.quelle):
        raise Fehler(f"Klon {ziel.klon} liegt in der Quelle {ziel.quelle}; abgebrochen")
    if ziel.ausgabe == ziel.klon or _liegt_unter(ziel.ausgabe, ziel.klon):
        raise Fehler(f"Ausgabe {ziel.ausgabe} liegt im Klon; sie würde beim Auffrischen gelöscht")
    if not (ziel.quelle / ".git").exists():
        raise Fehler(f"Quelle {ziel.quelle} ist kein Git-Repo")
    if ziel.konfiguration is not None and not ziel.konfiguration.is_file():
        raise Fehler(f"Konfiguration {ziel.konfiguration} fehlt")


def git(*argumente: str | Path) -> str:
    befehl = ["git", *(str(a) for a in argumente)]
    try:
        lauf = subprocess.run(befehl, check=True, capture_output=True)
    except FileNotFoundError as fehler:
        raise Fehler("git ist nicht installiert oder nicht im PATH") from fehler
    except subprocess.CalledProcessError as fehler:
        meldung = fehler.stderr.decode("utf-8", "replace").strip()
        raise Fehler(f"{' '.join(befehl)} schlug fehl: {meldung}") from fehler
    return lauf.stdout.decode("utf-8", "replace").strip()


def _gleicher_ort(url: str, quelle: Path) -> bool:
    try:
        return Path(url).resolve() == quelle
    except (OSError, ValueError):
        return False


def pruefe_klon(ziel: Ziel) -> None:
    """Nur ein echter Klon der Quelle darf zurückgesetzt und gesäubert werden."""
    if not (ziel.klon / ".git").is_dir():
        raise Fehler(f"{ziel.klon} ist kein Git-Klon (kein .git-Ordner); abgebrochen")
    oben = Path(git("-C", ziel.klon, "rev-parse", "--show-toplevel")).resolve()
    if oben != ziel.klon:
        raise Fehler(f"{ziel.klon} ist nicht die Wurzel eines Git-Repos; abgebrochen")
    try:
        url = git("-C", ziel.klon, "config", "--get", "remote.origin.url")
    except Fehler:
        url = ""
    if not _gleicher_ort(url, ziel.quelle):
        raise Fehler(
            f"remote.origin.url des Klons ({url or 'leer'}) ist nicht die Quelle {ziel.quelle}; "
            "abgebrochen"
        )


def frische_auf(ziel: Ziel) -> str:
    """Legt den Klon an oder setzt ihn hart auf ``origin/<zweig>``; liefert den Commit."""
    if not ziel.klon.exists():
        ziel.klon.parent.mkdir(parents=True, exist_ok=True)
        # --no-hardlinks: keine gemeinsamen Objektdateien mit der Quelle.
        # core.autocrlf=false: Dateien wie committet (nur .gitattributes gilt), damit der Klon
        # auf jedem Rechner gleich aussieht und git status nichts Unechtes meldet.
        git(
            "clone",
            "-q",
            "--no-hardlinks",
            "--config",
            "core.autocrlf=false",
            ziel.quelle,
            ziel.klon,
        )
    else:
        pruefe_klon(ziel)
        git("-C", ziel.klon, "fetch", "-q", "--prune", "origin")
    if ziel.zweig:
        ref = f"origin/{ziel.zweig}"
    else:
        ref = git("-C", ziel.klon, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    commit = git("-C", ziel.klon, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    git("-C", ziel.klon, "checkout", "-q", "--detach", commit)
    git("-C", ziel.klon, "reset", "-q", "--hard", commit)
    # Lange Pfade (Build-Ausgaben unter Windows) sonst nicht löschbar
    git("-C", ziel.klon, "-c", "core.longPaths=true", "clean", "-q", "-fdx")
    return commit


def _anzeige(pfad: Path, wurzel: Path) -> str:
    try:
        return pfad.relative_to(wurzel).as_posix()
    except ValueError:
        return pfad.as_posix()


def _alter_commit(daten: Path) -> str | None:
    try:
        return json.loads(daten.read_text(encoding="utf-8"))["ziel"]["git_commit"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def kartiere(ziel: Ziel) -> None:
    daten = ziel.ausgabe / "daidalos.json"
    deutung = ziel.ausgabe / "deutung.json"
    konfiguration = ["--konfiguration", str(ziel.konfiguration)] if ziel.konfiguration else []
    scan = ["scan", str(ziel.klon), "--ausgabe", str(daten), *konfiguration]
    if daidalos(scan) != 0:
        raise Fehler("daidalos scan schlug fehl")
    render = ["render", str(ziel.klon), "--daten", str(daten), "--ausgabe", str(ziel.ausgabe)]
    if deutung.is_file():
        render += ["--deutung", str(deutung)]
    if daidalos([*render, *konfiguration]) != 0:
        raise Fehler("daidalos render schlug fehl")


def zaehle_offen(ziel: Ziel) -> tuple[int, int]:
    """Anzahl der Dateien und der offenen Deutungen (wie ``daidalos deutung pruefen``)."""
    try:
        messung = lade_messung(ziel.ausgabe / "daidalos.json")
        deutung = ziel.ausgabe / "deutung.json"
        roh = lies_deutung(deutung) if deutung.is_file() else None
    except (RenderFehler, DeutungsFehler) as fehler:
        raise Fehler(str(fehler)) from fehler
    offen = finde_offenes(messung, roh, wichtige_dateien(messung))
    anzahl = len(offen.beschreibungen) + len(offen.befunde) + len(offen.tote_verweise)
    dateien = sum(1 for k in messung["knoten"] if k["art"] == "datei")
    return dateien, anzahl


def skill_zeile(ziel: Ziel, wurzel: Path) -> str:
    teile = [
        f"Daidalos-Skill für Ziel {_anzeige(ziel.klon, wurzel)}",
        f"--daten {_anzeige(ziel.ausgabe / 'daidalos.json', wurzel)}",
        f"--deutung {_anzeige(ziel.ausgabe / 'deutung.json', wurzel)}",
        f"--ausgabe {_anzeige(ziel.ausgabe, wurzel)}",
    ]
    if ziel.konfiguration:
        teile.append(f"--konfiguration {_anzeige(ziel.konfiguration, wurzel)}")
    return " ".join(teile)


def lauf(name: str, wurzel: Path, erzwingen: bool, mit_detekt: bool = False) -> int:
    wurzel = wurzel.resolve()
    ziel = lies_ziel(wurzel, name)
    pruefe_pfade(wurzel, ziel)
    if mit_detekt and ziel.detekt is None:
        raise Fehler(f"Ziel {name}: --mit-detekt braucht detekt = [...] in {ZIELE.as_posix()}")
    commit = frische_auf(ziel)
    kopiere_dateien(ziel)
    if not erzwingen and _alter_commit(ziel.ausgabe / "daidalos.json") == commit:
        print(f"Stand unverändert: {commit[:7]}")
        return EXIT_OK
    if mit_detekt:
        print(f"detekt:    {' '.join(ziel.detekt or ())} im Klon …", flush=True)
        dauer = fuehre_detekt_aus(ziel)
        print(f"detekt:    fertig nach {dauer:.1f} s")
    kartiere(ziel)
    betreff = git("-C", ziel.klon, "log", "-1", "--format=%s", commit)
    dateien, offen = zaehle_offen(ziel)
    print()
    print(f"Commit:    {commit[:7]} {betreff}")
    print(f"Dateien:   {dateien}")
    print(f"Offen:     {offen} (Deutung)")
    print(f"Für den Skill: {skill_zeile(ziel, wurzel)}")
    return EXIT_OFFEN if offen else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="ziel_auffrischen.py",
        description="Klon eines Zielrepos auffrischen, scannen und rendern.",
    )
    parser.add_argument("name", metavar="NAME", help="Ziel aus lokal/ziele.toml")
    parser.add_argument(
        "--erzwingen", action="store_true", help="auch bei unverändertem Commit scannen"
    )
    parser.add_argument(
        "--mit-detekt",
        action="store_true",
        help="vor dem Scan den Befehl detekt des Ziels im Klon ausführen (SARIF zum Commit)",
    )
    parser.add_argument(
        "--wurzel",
        default=str(WURZEL),
        metavar="ORDNER",
        help="Daidalos-Wurzel mit lokal/ (Standard: dieses Repo; für Tests)",
    )
    argumente = parser.parse_args(argv)
    try:
        return lauf(
            argumente.name, Path(argumente.wurzel), argumente.erzwingen, argumente.mit_detekt
        )
    except Fehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return EXIT_FEHLER


if __name__ == "__main__":
    sys.exit(main())
