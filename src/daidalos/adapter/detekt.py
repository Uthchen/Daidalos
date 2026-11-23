"""detekt-Ergebnisse aus SARIF 2.1.0 lesen (A08).

Die Dateien entstehen nur beim Build und liegen meist unter ``build/``, das der Scan ausschließt.
Gesucht wird deshalb im ganzen Zielrepo nach ``[detekt].sarif``, unabhängig von den Ausschlüssen;
Ordner mit eigenem ``.git`` (verschachtelte Repos, Worktrees) werden nicht betreten.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from pathspec import GitIgnoreSpec

from daidalos.ids import datei_der_funktion
from daidalos.konfiguration import Warner, warne_stderr

Knoten = dict[str, Any]
Befund = dict[str, Any]

_SCHWERE = {"error": "fehler", "warning": "warnung"}
_RANG = {"fehler": 0, "warnung": 1, "hinweis": 2}
_LAUFWERK = re.compile(r"^[A-Za-z]:[/\\]")


def finde_sarif(ziel: Path, muster: tuple[str, ...]) -> list[str]:
    """Relative Pfade (mit ``/``) aller Dateien, die auf ein Muster passen, sortiert."""
    if not muster:
        return []
    spec = GitIgnoreSpec.from_lines(muster)
    gefunden: list[str] = []
    for wurzel, ordner, dateien in os.walk(ziel, topdown=True, followlinks=False):
        basis = Path(wurzel)
        ordner[:] = sorted(o for o in ordner if o != ".git" and not (basis / o / ".git").exists())
        relativ = basis.relative_to(ziel).as_posix()
        for name in dateien:
            pfad = name if relativ == "." else f"{relativ}/{name}"
            if spec.match_file(pfad) and not (basis / name).is_symlink():
                gefunden.append(pfad)
    return sorted(gefunden)


def relativer_pfad(uri: str, ziel: Path) -> str | None:
    """Pfad relativ zum Zielrepo (mit ``/``); ``None``, wenn er außerhalb liegt."""
    if _LAUFWERK.match(uri):
        absolut = uri
    else:
        teile = urlparse(uri)
        if teile.scheme == "file":
            absolut = url2pathname(teile.path)
            if os.name != "nt" and teile.netloc:
                return None
        elif not teile.scheme:
            absolut = os.path.join(str(ziel), unquote(uri))
        else:
            return None
    voll = os.path.normpath(absolut)
    wurzel = os.path.normpath(str(ziel))
    if not os.path.normcase(voll).startswith(os.path.normcase(wurzel) + os.sep):
        return None
    return voll[len(wurzel) + 1 :].replace(os.sep, "/")


def _innerste(funktionen: list[tuple[int, int, str]], zeile: int) -> str | None:
    passend = [(bis - von, fid) for von, bis, fid in funktionen if von <= zeile <= bis]
    return min(passend)[1] if passend else None


def lies_detekt(
    ziel: Path,
    muster: tuple[str, ...],
    knoten: list[Knoten],
    warne: Warner = warne_stderr,
) -> tuple[list[Befund], dict[str, int]]:
    """Befunde ``detekt`` und die Zählung für ``ziel.detekt``."""
    ziel = ziel.resolve()
    dateien = {k["pfad"]: k for k in knoten if k["art"] == "datei"}
    funktionen: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for k in knoten:
        if k["art"] == "funktion":
            funktionen[datei_der_funktion(k)].append((k["zeile_von"], k["zeile_bis"], k["id"]))

    gruppen: dict[tuple[str, str, int], dict[str, Any]] = {}
    sarif_dateien = finde_sarif(ziel, muster)
    gelesen = 0
    gueltig = 0
    nicht_erfasst = 0
    for sarif in sarif_dateien:
        try:
            text = (ziel / sarif).read_text(encoding="utf-8-sig")
            # Eine leere Datei ist ein leerer Bericht: keine Verstöße.
            daten = json.loads(text) if text.strip() else {"runs": []}
            laeufe = daten["runs"]
            if not isinstance(laeufe, list):
                raise TypeError("runs ist keine Liste")
        except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as fehler:
            warne(f"{sarif}: kein gültiges SARIF ({fehler}); übersprungen")
            continue
        gueltig += 1
        for lauf in laeufe:
            for ergebnis in (lauf or {}).get("results") or []:
                gelesen += 1
                try:
                    regel = ergebnis["ruleId"]
                    ort = ergebnis["locations"][0]["physicalLocation"]
                    uri = ort["artifactLocation"]["uri"]
                    zeile = int(ort["region"]["startLine"])
                    meldung = str((ergebnis.get("message") or {}).get("text", ""))
                except (KeyError, IndexError, TypeError, ValueError):
                    warne(f"{sarif}: Ergebnis ohne Regel oder Ort übersprungen")
                    continue
                pfad = relativer_pfad(str(uri), ziel)
                if pfad is None:
                    warne(f"{sarif}: Ergebnis {regel} außerhalb des Zielrepos verworfen ({uri})")
                    continue
                datei = dateien.get(pfad)
                if datei is None:
                    nicht_erfasst += 1
                    continue
                if datei.get("fremd"):
                    continue
                # SARIF: ohne ``level`` gilt ``warning``
                schwere = _SCHWERE.get(ergebnis.get("level", "warning"), "hinweis")
                schluessel = (str(regel), pfad, zeile)
                gruppe = gruppen.setdefault(
                    schluessel, {"meldungen": set(), "sarif": set(), "schwere": schwere}
                )
                gruppe["meldungen"].add(meldung)
                gruppe["sarif"].add(sarif)
                if _RANG[schwere] < _RANG[gruppe["schwere"]]:
                    gruppe["schwere"] = schwere
    if nicht_erfasst:
        warne(f"detekt: {nicht_erfasst} Ergebnisse in nicht erfassten Dateien verworfen")

    befunde: list[Befund] = []
    for (regel, pfad, zeile), gruppe in gruppen.items():
        quellen = sorted(gruppe["sarif"])
        knoten_id = _innerste(funktionen.get(pfad, []), zeile) or f"datei:{pfad}"
        befunde.append(
            {
                "beleg": {
                    "meldung": "\n".join(sorted(gruppe["meldungen"])),
                    "sarif": quellen[0] if len(quellen) == 1 else quellen,
                    "zeile": zeile,
                },
                "id": f"befund:detekt:{regel}:{pfad}:{zeile}",
                "knoten": [knoten_id],
                "quelle": "detekt",
                "regel": regel,
                "schwere": gruppe["schwere"],
            }
        )
    befunde.sort(key=lambda b: b["id"])
    return befunde, {"dateien": gueltig, "ergebnisse": gelesen}
