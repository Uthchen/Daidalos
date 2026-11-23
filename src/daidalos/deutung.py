"""Liest ``deutung.json`` (geschrieben vom Skill) und gleicht sie mit der Messung ab.

``render`` schreibt die Deutung nie, es liest sie nur. Verweise auf Ids, die es in der Messung
nicht mehr gibt, werden übersprungen und als Warnung gemeldet. Beschreibungen, deren ``hash``
nicht mehr zum Knoten passt, bleiben erhalten und bekommen ``veraltet: true``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from daidalos.ids import kanten_id as _kid
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
    kanten = {_kid(k) for k in messung["kanten"]}

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


# ---------------------------------------------------------------- Entwurf übernehmen

_ENTWURF_SCHLUESSEL = _BEKANNT | {"entfernen"}
_FELDER_BEREICH = frozenset({"id", "name", "beschreibung", "knoten"})
_FELDER_EINSCHAETZUNG = frozenset({"befund", "prioritaet", "titel", "begruendung", "vorschlag"})


class EntwurfFehler(Exception):
    """Der Entwurf passt nicht zur Messung; nichts wird geschrieben. Exit-Code 2."""

    def __init__(self, probleme: list[str]) -> None:
        super().__init__(f"{len(probleme)} Problem(e) im Entwurf")
        self.probleme = probleme


def lies_json(pfad: Path) -> Any:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as fehler:
        raise DeutungsFehler(f"{pfad.name}: nicht lesbar ({fehler})") from fehler
    except json.JSONDecodeError as fehler:
        raise DeutungsFehler(f"{pfad.name}: kein gültiges JSON ({fehler})") from fehler


def _nicht_leer(wert: Any) -> bool:
    return isinstance(wert, str) and wert.strip() != ""


def _pruefe_beschreibungen(roh: Any, knoten: set[str], p: list[str]) -> None:
    if not isinstance(roh, dict):
        p.append("beschreibungen: kein Objekt")
        return
    for knoten_id, eintrag in sorted(roh.items()):
        if knoten_id not in knoten:
            p.append(f"beschreibungen: unbekannter Knoten {knoten_id}")
        if not isinstance(eintrag, dict) or not _nicht_leer(eintrag.get("text")):
            p.append(f"beschreibungen: {knoten_id} braucht einen nicht leeren text")
        elif set(eintrag) - {"text", "hash"}:
            p.append(f"beschreibungen: {knoten_id} hat unbekannte Felder")


def _pruefe_bereiche(roh: Any, knoten: set[str], p: list[str]) -> None:
    if not isinstance(roh, list):
        p.append("bereiche: keine Liste")
        return
    ids: set[str] = set()
    for eintrag in roh:
        if not isinstance(eintrag, dict) or not _nicht_leer(eintrag.get("id")):
            p.append("bereiche: Eintrag ohne id")
            continue
        bid = eintrag["id"]
        if not bid.startswith("bereich:"):
            p.append(f"bereiche: id {bid} beginnt nicht mit bereich:")
        if bid in ids:
            p.append(f"bereiche: id {bid} doppelt")
        ids.add(bid)
        if set(eintrag) - _FELDER_BEREICH:
            p.append(f"bereiche: {bid} hat unbekannte Felder")
        for feld in ("name", "beschreibung"):
            if not _nicht_leer(eintrag.get(feld)):
                p.append(f"bereiche: {bid} braucht {feld}")
        mitglieder = eintrag.get("knoten")
        if not isinstance(mitglieder, list) or not mitglieder:
            p.append(f"bereiche: {bid} braucht eine nicht leere Liste knoten")
            continue
        for knoten_id in mitglieder:
            if knoten_id not in knoten:
                p.append(f"bereiche: {bid}: unbekannter Knoten {knoten_id}")


def _pruefe_einschaetzungen(roh: Any, befunde: set[str], p: list[str]) -> None:
    if not isinstance(roh, list):
        p.append("einschaetzungen: keine Liste")
        return
    gesehen: set[str] = set()
    for eintrag in roh:
        befund = eintrag.get("befund") if isinstance(eintrag, dict) else None
        if not isinstance(befund, str):
            p.append("einschaetzungen: Eintrag ohne befund")
            continue
        if befund not in befunde:
            p.append(f"einschaetzungen: unbekannter Befund {befund}")
        if befund in gesehen:
            p.append(f"einschaetzungen: {befund} doppelt")
        gesehen.add(befund)
        if set(eintrag) - _FELDER_EINSCHAETZUNG:
            p.append(f"einschaetzungen: {befund} hat unbekannte Felder")
        prioritaet = eintrag.get("prioritaet")
        if prioritaet is not None and (
            not isinstance(prioritaet, int) or isinstance(prioritaet, bool) or prioritaet < 1
        ):
            p.append(f"einschaetzungen: {befund}: prioritaet muss eine ganze Zahl ≥ 1 sein")
        for feld in ("titel", "begruendung"):
            if not _nicht_leer(eintrag.get(feld)):
                p.append(f"einschaetzungen: {befund} braucht {feld}")
        if prioritaet is not None and not _nicht_leer(eintrag.get("vorschlag")):
            p.append(f"einschaetzungen: {befund} mit prioritaet braucht einen vorschlag")


def _pruefe_kanten(roh: Any, kanten: set[str], p: list[str]) -> None:
    if not isinstance(roh, dict):
        p.append("kanten: kein Objekt")
        return
    for kanten_id, eintrag in sorted(roh.items()):
        if kanten_id not in kanten:
            p.append(f"kanten: unbekannte Kante {kanten_id}")
        if not isinstance(eintrag, dict) or not _nicht_leer(eintrag.get("text")):
            p.append(f"kanten: {kanten_id} braucht einen nicht leeren text")
        elif set(eintrag) - {"text"}:
            p.append(f"kanten: {kanten_id} hat unbekannte Felder")


def pruefe_entwurf(entwurf: Any, messung: dict[str, Any]) -> list[str]:
    """Liste aller Probleme (unbekannte Ids, fehlende Texte, falsche Typen); leer, wenn alles
    passt."""
    if not isinstance(entwurf, dict):
        return ["Entwurf ist kein JSON-Objekt"]
    p: list[str] = []
    if entwurf.get("schema", SCHEMA_DEUTUNG) != SCHEMA_DEUTUNG:
        p.append(f"schema {entwurf.get('schema')!r} wird nicht unterstützt")
    for schluessel in sorted(set(entwurf) - _ENTWURF_SCHLUESSEL):
        p.append(f"unbekannter Schlüssel {schluessel!r}")
    knoten = {k["id"] for k in messung["knoten"]}
    _pruefe_beschreibungen(entwurf.get("beschreibungen", {}), knoten, p)
    _pruefe_bereiche(entwurf.get("bereiche", []), knoten, p)
    _pruefe_einschaetzungen(
        entwurf.get("einschaetzungen", []), {b["id"] for b in messung["befunde"]}, p
    )
    _pruefe_kanten(entwurf.get("kanten", {}), {_kid(k) for k in messung["kanten"]}, p)
    entfernen = entwurf.get("entfernen", [])
    if not isinstance(entfernen, list) or not all(isinstance(i, str) for i in entfernen):
        p.append("entfernen: keine Liste von Ids")
    return p


def fuehre_zusammen(
    bestand: dict[str, Any] | None, entwurf: dict[str, Any], messung: dict[str, Any]
) -> dict[str, Any]:
    """Neue ``deutung.json``: Bestand plus Entwurf, Hashes aus der Messung, sortiert.

    Einträge des Entwurfs ersetzen gleichnamige (Beschreibung und Kantentext je Id, Bereich je
    ``id``, Einschätzung je ``befund``); ``entfernen`` streicht Einträge mit diesen Ids. Alles
    andere bleibt unverändert, auch Bestandseinträge mit toten Verweisen.
    """
    hashes = {k["id"]: k.get("hash") for k in messung["knoten"]}
    bestand = bestand or {}
    weg = set(entwurf.get("entfernen", []))

    roh = bestand.get("beschreibungen")
    beschreibungen = {
        k: v for k, v in (roh if isinstance(roh, dict) else {}).items() if k not in weg
    }
    for knoten_id, eintrag in (entwurf.get("beschreibungen") or {}).items():
        beschreibungen[knoten_id] = {"hash": hashes[knoten_id], "text": eintrag["text"]}

    bereiche = {
        b["id"]: b
        for b in bestand.get("bereiche") or []
        if isinstance(b, dict) and isinstance(b.get("id"), str) and b["id"] not in weg
    }
    for b in entwurf.get("bereiche") or []:
        bereiche[b["id"]] = {
            "beschreibung": b["beschreibung"],
            "id": b["id"],
            "knoten": sorted(set(b["knoten"])),
            "name": b["name"],
        }

    einschaetzungen = {
        e["befund"]: e
        for e in bestand.get("einschaetzungen") or []
        if isinstance(e, dict) and isinstance(e.get("befund"), str) and e["befund"] not in weg
    }
    for e in entwurf.get("einschaetzungen") or []:
        einschaetzungen[e["befund"]] = {
            f: e[f] for f in sorted(_FELDER_EINSCHAETZUNG) if e.get(f) is not None
        }

    roh = bestand.get("kanten")
    kanten = {k: v for k, v in (roh if isinstance(roh, dict) else {}).items() if k not in weg}
    for kanten_id, eintrag in (entwurf.get("kanten") or {}).items():
        kanten[kanten_id] = {"text": eintrag["text"]}

    return {
        "bereiche": [bereiche[i] for i in sorted(bereiche)],
        "beschreibungen": dict(sorted(beschreibungen.items())),
        "einschaetzungen": [einschaetzungen[i] for i in sorted(einschaetzungen)],
        "kanten": dict(sorted(kanten.items())),
        "schema": SCHEMA_DEUTUNG,
    }


def uebernimm(
    entwurf: Any, bestand: dict[str, Any] | None, messung: dict[str, Any]
) -> dict[str, Any]:
    """Prüft den Entwurf und führt ihn mit dem Bestand zusammen; ``EntwurfFehler`` bei
    Problemen, dann wird nichts geschrieben."""
    probleme = pruefe_entwurf(entwurf, messung)
    if probleme:
        raise EntwurfFehler(probleme)
    return fuehre_zusammen(bestand, entwurf, messung)
