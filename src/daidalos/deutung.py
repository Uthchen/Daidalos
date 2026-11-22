"""Liest ``deutung.json`` (geschrieben vom Skill) und gleicht sie mit der Messung ab.

``render`` schreibt die Deutung nie, es liest sie nur. Verweise auf Ids, die es in der Messung
nicht mehr gibt, werden übersprungen und als Warnung gemeldet. Beschreibungen, deren ``hash``
nicht mehr zum Knoten passt, bleiben erhalten und bekommen ``veraltet: true``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from daidalos.konfiguration import Warner, warne_stderr

SCHEMA_DEUTUNG = 1
_BEKANNT = frozenset({"schema", "beschreibungen", "bereiche", "einschaetzungen", "kanten"})


class DeutungsFehler(Exception):
    """``deutung.json`` ist kein gültiges JSON oder hat ein anderes ``schema``."""


def _text(wert: Any) -> str | None:
    return wert if isinstance(wert, str) else None


def lies_deutung(pfad: Path) -> dict[str, Any]:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as fehler:
        raise DeutungsFehler(f"{pfad.name}: nicht lesbar ({fehler})") from fehler
    except json.JSONDecodeError as fehler:
        raise DeutungsFehler(f"{pfad.name}: kein gültiges JSON ({fehler})") from fehler
    if not isinstance(daten, dict) or daten.get("schema") != SCHEMA_DEUTUNG:
        schema = daten.get("schema") if isinstance(daten, dict) else None
        raise DeutungsFehler(
            f"{pfad.name}: schema {schema!r} wird nicht unterstützt (erwartet {SCHEMA_DEUTUNG})"
        )
    return daten


def gleiche_ab(
    deutung: dict[str, Any], messung: dict[str, Any], warne: Warner = warne_stderr
) -> dict[str, Any]:
    """Bereinigte Deutung: nur gültige Verweise, Beschreibungen mit ``veraltet``."""
    knoten = {k["id"]: k for k in messung["knoten"]}
    befunde = {b["id"] for b in messung["befunde"]}
    kanten = {k["id"] for k in messung["kanten"]}

    for schluessel in sorted(set(deutung) - _BEKANNT):
        warne(f"deutung.json: unbekannter Schlüssel {schluessel!r} wird ignoriert")

    beschreibungen: dict[str, Any] = {}
    roh = deutung.get("beschreibungen") or {}
    for knoten_id in sorted(roh) if isinstance(roh, dict) else []:
        eintrag = roh[knoten_id]
        text = _text(eintrag.get("text")) if isinstance(eintrag, dict) else None
        if knoten_id not in knoten:
            warne(f"deutung.json: Beschreibung für unbekannten Knoten {knoten_id} übersprungen")
            continue
        if text is None:
            warne(f"deutung.json: Beschreibung für {knoten_id} ohne Text übersprungen")
            continue
        hash_wert = _text(eintrag.get("hash"))
        beschreibungen[knoten_id] = {
            "hash": hash_wert,
            "text": text,
            "veraltet": hash_wert != knoten[knoten_id].get("hash"),
        }

    bereiche: list[dict[str, Any]] = []
    for eintrag in deutung.get("bereiche") or []:
        if not isinstance(eintrag, dict) or _text(eintrag.get("id")) is None:
            warne("deutung.json: Bereich ohne id übersprungen")
            continue
        mitglieder = []
        for knoten_id in eintrag.get("knoten") or []:
            if knoten_id in knoten:
                mitglieder.append(knoten_id)
            else:
                warne(f"deutung.json: {eintrag['id']}: unbekannter Knoten {knoten_id} übersprungen")
        bereiche.append(
            {
                "beschreibung": _text(eintrag.get("beschreibung")) or "",
                "id": eintrag["id"],
                "knoten": sorted(set(mitglieder)),
                "name": _text(eintrag.get("name")) or eintrag["id"],
            }
        )
    bereiche.sort(key=lambda b: (b["name"], b["id"]))

    einschaetzungen: list[dict[str, Any]] = []
    for eintrag in deutung.get("einschaetzungen") or []:
        if not isinstance(eintrag, dict):
            continue
        befund = _text(eintrag.get("befund"))
        if befund not in befunde:
            warne(f"deutung.json: Einschätzung zu unbekanntem Befund {befund} übersprungen")
            continue
        prioritaet = eintrag.get("prioritaet")
        einschaetzungen.append(
            {
                "befund": befund,
                "begruendung": _text(eintrag.get("begruendung")) or "",
                "prioritaet": prioritaet if isinstance(prioritaet, int) else None,
                "titel": _text(eintrag.get("titel")) or befund,
                "vorschlag": _text(eintrag.get("vorschlag")) or "",
            }
        )
    # Ohne Priorität ans Ende, sonst nach Priorität, dann Befund-Id.
    einschaetzungen.sort(key=lambda e: (e["prioritaet"] is None, e["prioritaet"] or 0, e["befund"]))

    kanten_texte: dict[str, Any] = {}
    roh = deutung.get("kanten") or {}
    for kanten_id in sorted(roh) if isinstance(roh, dict) else []:
        eintrag = roh[kanten_id]
        text = _text(eintrag.get("text")) if isinstance(eintrag, dict) else None
        if kanten_id not in kanten:
            warne(f"deutung.json: Text zu unbekannter Kante {kanten_id} übersprungen")
            continue
        if text is not None:
            kanten_texte[kanten_id] = {"text": text}

    return {
        "bereiche": bereiche,
        "beschreibungen": beschreibungen,
        "einschaetzungen": einschaetzungen,
        "kanten": kanten_texte,
        "schema": SCHEMA_DEUTUNG,
    }
