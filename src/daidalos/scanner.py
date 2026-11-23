"""Scanner: findet die Dateien des Zielrepos und misst sie einzeln.

Ergebnis ist ein Datei-Knoten je Datei mit Sprache, Zeilen, Größe und Hash.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from pathspec import GitIgnoreSpec

from daidalos import __version__
from daidalos.konfiguration import (
    EINGEBAUTE_AUSSCHLUESSE,
    Konfiguration,
    Warner,
    warne_stderr,
)
from daidalos.sprachen import BINAER, erkenne_sprache
from daidalos.struktur import baue_struktur

SCHEMA = 1
GROSSE_DATEI = 5 * 1024 * 1024  # ab hier keine Zeilenzählung
BINAER_PRUEFLAENGE = 8 * 1024
BLOCK = 1024 * 1024

Knoten = dict[str, Any]


class GitNichtVerfuegbar(Exception):
    """``git`` ist nicht aufrufbar oder liefert einen Fehler."""


@dataclass(frozen=True)
class ScanErgebnis:
    daten: dict[str, Any]
    git_modus: bool
    # Zählung der Aufrufstellen nach Ausgang (nur für stdout und Berichte)
    aufrufe: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------- Git


def fuehre_git_aus(ziel: Path, *argumente: str) -> bytes:
    """Ruft ``git`` ohne Shell im Zielrepo auf und liefert stdout."""
    try:
        lauf = subprocess.run(
            ["git", "-C", str(ziel), *argumente],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as fehler:
        raise GitNichtVerfuegbar("git ist nicht aufrufbar") from fehler
    except subprocess.CalledProcessError as fehler:
        meldung = fehler.stderr.decode("utf-8", "replace").strip()
        raise GitNichtVerfuegbar(f"git {' '.join(argumente)} schlug fehl: {meldung}") from fehler
    return lauf.stdout


def ist_git_repo(ziel: Path) -> bool:
    """Das Ziel ist ein Git-Repo, wenn es selbst ``.git`` enthält (Ordner oder Datei).

    Ein Unterordner eines fremden Repos zählt nicht als Git-Repo.
    """
    return (ziel / ".git").exists()


def _git_dateien(ziel: Path) -> list[str]:
    ausgabe = fuehre_git_aus(
        ziel,
        "-c",
        "core.quotepath=off",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    )
    pfade: set[str] = set()
    for roh in ausgabe.split(b"\0"):
        if not roh:
            continue
        pfad = roh.decode("utf-8", "surrogateescape")
        # Verschachtelte Repos und Worktrees meldet git mit abschließendem "/".
        if pfad.endswith("/"):
            continue
        pfade.add(pfad)
    return sorted(pfade)


def _git_commit(ziel: Path) -> str | None:
    try:
        return fuehre_git_aus(ziel, "rev-parse", "--verify", "-q", "HEAD").decode().strip()
    except GitNichtVerfuegbar:
        return None  # noch kein Commit


def _git_aenderungen(ziel: Path, erfasst: set[str]) -> bool:
    """Ob eine erfasste Datei nicht committete Änderungen hat (auch: nicht getrackt)."""
    ausgabe = fuehre_git_aus(
        ziel,
        "-c",
        "core.quotepath=off",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    teile = ausgabe.split(b"\0")
    i = 0
    while i < len(teile):
        eintrag = teile[i]
        i += 1
        if len(eintrag) < 4:
            continue
        status = eintrag[:2]
        pfad = eintrag[3:].decode("utf-8", "surrogateescape")
        if status[:1] in (b"R", b"C"):
            i += 1  # ursprünglicher Pfad folgt als eigener Eintrag
        if pfad in erfasst:
            return True
    return False


# ---------------------------------------------------------------- Dateien finden


def _ausschluss_spec(konfiguration: Konfiguration) -> GitIgnoreSpec:
    return GitIgnoreSpec.from_lines([*EINGEBAUTE_AUSSCHLUESSE, *konfiguration.scan.ausschliessen])


def _lies_gitignore(ziel: Path, warne: Warner) -> GitIgnoreSpec:
    datei = ziel / ".gitignore"
    if not datei.is_file():
        return GitIgnoreSpec.from_lines([])
    try:
        zeilen = datei.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as fehler:
        warne(f".gitignore nicht lesbar ({fehler}), wird nicht beachtet")
        return GitIgnoreSpec.from_lines([])
    return GitIgnoreSpec.from_lines(zeilen)


def _durchlauf_dateien(
    ziel: Path, ausschluss: GitIgnoreSpec, gitignore: GitIgnoreSpec
) -> list[str]:
    """Durchläuft das Verzeichnis ohne Git.

    Ausgeschlossene Ordner werden nicht betreten: sie fliegen aus ``ordner``,
    bevor ``os.walk`` absteigt. Symlinks werden nicht verfolgt.
    """
    pfade: list[str] = []
    for wurzel, ordner, dateien in os.walk(ziel, topdown=True, followlinks=False):
        basis = Path(wurzel).relative_to(ziel).as_posix()
        praefix = "" if basis == "." else basis + "/"
        behalten: list[str] = []
        for name in sorted(ordner):
            rel = f"{praefix}{name}/"
            voll = Path(wurzel) / name
            if voll.is_symlink():
                continue
            if ausschluss.match_file(rel) or gitignore.match_file(rel):
                continue
            # Verschachtelte Repos und Worktrees wie git überspringen.
            if (voll / ".git").exists():
                continue
            behalten.append(name)
        ordner[:] = behalten
        for name in dateien:
            rel = f"{praefix}{name}"
            if gitignore.match_file(rel):
                continue
            pfade.append(rel)
    return pfade


def finde_dateien(
    ziel: Path, konfiguration: Konfiguration, warne: Warner = warne_stderr
) -> tuple[list[str], bool]:
    """Liefert die erfassten Pfade (relativ, mit ``/``, sortiert) und ob Git genutzt wurde."""
    ausschluss = _ausschluss_spec(konfiguration)
    kandidaten: list[str] | None = None
    git_modus = False
    if ist_git_repo(ziel):
        try:
            kandidaten = _git_dateien(ziel)
            git_modus = True
        except GitNichtVerfuegbar as fehler:
            warne(f"{fehler}; Rückfall auf Verzeichnisdurchlauf")
    if kandidaten is None:
        kandidaten = _durchlauf_dateien(ziel, ausschluss, _lies_gitignore(ziel, warne))

    ergebnis: list[str] = []
    for pfad in kandidaten:
        if ausschluss.match_file(pfad):
            continue
        voll = ziel / pfad
        # Gelöschte Dateien, Submodule (Ordner) und Symlinks überspringen.
        if voll.is_symlink() or not voll.is_file():
            continue
        ergebnis.append(pfad)
    return sorted(set(ergebnis)), git_modus


# ---------------------------------------------------------------- Messen


def _oeffne(pfad: Path) -> BinaryIO:
    return pfad.open("rb")


class _ZeilenendenNormierer:
    """Wandelt CRLF und CR in LF, auch über Blockgrenzen hinweg."""

    def __init__(self) -> None:
        self._rest = b""

    def block(self, daten: bytes) -> bytes:
        daten = self._rest + daten
        if daten.endswith(b"\r"):
            self._rest = b"\r"
            daten = daten[:-1]
        else:
            self._rest = b""
        return daten.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    def ende(self) -> bytes:
        return b"\n" if self._rest else b""


def _miss_inhalt(datei: BinaryIO, zaehle_zeilen: bool) -> tuple[str, int | None, bool]:
    """Liefert (hash, zeilen, binaer)."""
    anfang = datei.read(BINAER_PRUEFLAENGE)
    binaer = b"\0" in anfang
    summe = hashlib.sha256()
    if binaer:
        summe.update(anfang)
        while block := datei.read(BLOCK):
            summe.update(block)
        return f"sha256:{summe.hexdigest()}", None, True

    normierer = _ZeilenendenNormierer()
    umbrueche = 0
    letztes = b""

    def nimm(teil: bytes) -> None:
        nonlocal umbrueche, letztes
        if teil:
            summe.update(teil)
            umbrueche += teil.count(b"\n")
            letztes = teil[-1:]

    nimm(normierer.block(anfang))
    while block := datei.read(BLOCK):
        nimm(normierer.block(block))
    nimm(normierer.ende())

    zeilen: int | None = None
    if zaehle_zeilen:
        zeilen = umbrueche + (1 if letztes and letztes != b"\n" else 0)
    return f"sha256:{summe.hexdigest()}", zeilen, False


def miss_datei(ziel: Path, pfad: str, fremd: GitIgnoreSpec, warne: Warner = warne_stderr) -> Knoten:
    """Erzeugt den Datei-Knoten für einen relativen Pfad."""
    knoten: Knoten = {
        "id": f"datei:{pfad}",
        "art": "datei",
        "pfad": pfad,
        "sprache": erkenne_sprache(pfad),
    }
    if fremd.match_file(pfad):
        knoten["fremd"] = True
    voll = ziel / pfad
    try:
        groesse = voll.stat().st_size
        knoten["bytes"] = groesse
        with _oeffne(voll) as datei:
            hash_wert, zeilen, binaer = _miss_inhalt(datei, groesse <= GROSSE_DATEI)
    except OSError as fehler:
        warne(f"{pfad}: nicht lesbar ({fehler.strerror or fehler})")
        knoten["lesefehler"] = True
        return knoten
    knoten["hash"] = hash_wert
    if binaer:
        knoten["sprache"] = BINAER
    elif zeilen is not None:
        knoten["zeilen"] = zeilen
    return knoten


def scanne(ziel: Path, konfiguration: Konfiguration, warne: Warner = warne_stderr) -> ScanErgebnis:
    """Scannt das Zielrepo und liefert den Inhalt von ``daidalos.json``."""
    ziel = ziel.resolve()
    pfade, git_modus = finde_dateien(ziel, konfiguration, warne)
    fremd = GitIgnoreSpec.from_lines(konfiguration.scan.fremd)
    dateien = [miss_datei(ziel, pfad, fremd, warne) for pfad in pfade]
    struktur = baue_struktur(ziel, dateien, warne)
    knoten = sorted([*dateien, *struktur.knoten], key=lambda k: k["id"])

    git_commit: str | None = None
    git_aenderungen: bool | None = None
    if git_modus:
        git_commit = _git_commit(ziel)
        try:
            git_aenderungen = _git_aenderungen(ziel, set(pfade))
        except GitNichtVerfuegbar as fehler:
            warne(f"{fehler}; git_aenderungen bleibt leer")

    daten: dict[str, Any] = {
        "schema": SCHEMA,
        "daidalos": __version__,
        "ziel": {
            "name": konfiguration.projekt.name or ziel.name,
            "git_commit": git_commit,
            "git_aenderungen": git_aenderungen,
        },
        "knoten": knoten,
        "kanten": struktur.kanten,
        "befunde": struktur.befunde,
    }
    return ScanErgebnis(daten=daten, git_modus=git_modus, aufrufe=struktur.aufrufe or {})


def zaehle_sprachen(knoten: Iterable[Knoten]) -> list[tuple[str, int]]:
    """Sprachen nach Anzahl Dateien, absteigend, bei Gleichstand alphabetisch."""
    zaehler: dict[str, int] = {}
    for k in knoten:
        if k.get("art") != "datei":
            continue
        zaehler[k["sprache"]] = zaehler.get(k["sprache"], 0) + 1
    return sorted(zaehler.items(), key=lambda paar: (-paar[1], paar[0]))
