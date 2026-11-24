"""Führungen durch die Karte (seit A10): prüfen, Hashes einsetzen, Stand je Schritt.

Eine Führung schreibt der Skill; sie ist Deutung. Das Programm prüft nur Ids und Sprungadressen
gegen die Messung, setzt die Hashes ein und meldet, welche Schritte **veraltet** (ein Hash stimmt
nicht mehr) oder **kaputt** (eine Id fehlt) sind. Format: ``docs/datenformat.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from daidalos.ids import kanten_id as _kid
from daidalos.render import strukturansicht

SCHEMA_FUEHRUNG = 1
ORDNER = "fuehrungen"
NAME_MUSTER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SCHRITTE_MIN, SCHRITTE_MAX = 3, 15
HERVORHEBEN_MIN, HERVORHEBEN_MAX = 1, 8
TIEFE_MAX = 5
# Sammelkasten „Weitere Ordner“ der Modulebene; die Karte kennt ihn als Knoten.
SAMMEL = "sammel:ordner"

_FELDER = frozenset({"schema", "name", "titel", "frage", "schritte"})
_FELDER_SCHRITT = frozenset({"ansicht", "hervorheben", "titel", "text", "belege", "hashes"})
_SCHLUESSEL_ANSICHT = frozenset(
    {
        "ebene",
        "knoten",
        "befund",
        "grenze",
        "kante",
        "funktion",
        "weg",
        "tiefe",
        "gewaehlt",
        "datei-funktionen",
        "von",
        "nach",
    }
)
_EBENEN = frozenset({"modul", "paket", "datei", "funktion"})

STAND_OK, STAND_VERALTET, STAND_KAPUTT = "ok", "veraltet", "kaputt"


class FuehrungsFehler(Exception):
    """Eine Führungsdatei ist nicht lesbar oder hat ein anderes ``schema``."""


# ---------------------------------------------------------------- Index der Messung


@dataclass
class Index:
    """Was eine Führung aus der Messung kennen darf."""

    knoten: dict[str, dict[str, Any]]  # alle Knoten der vollen Messung, auch Funktionen
    kanten: set[str]  # Kanten der Strukturansicht und der Funktionsebene
    struktur_kanten: set[str]  # nur Kanten der Strukturansicht (Sprungadresse ``kante=``)
    befunde: dict[str, dict[str, Any]]  # Befunde der Strukturansicht (die Karte kennt nur sie)
    dateien_mit_funktionen: set[str] = field(default_factory=set)

    @classmethod
    def aus(cls, messung: dict[str, Any]) -> Index:
        struktur = strukturansicht(messung)
        knoten = {k["id"]: k for k in messung["knoten"]}
        mit_funktionen = {
            k["id"].removeprefix("funktion:").split("#", 1)[0]
            for k in messung["knoten"]
            if k["art"] == "funktion"
        }
        return cls(
            knoten=knoten,
            kanten={_kid(k) for k in messung["kanten"]},
            struktur_kanten={_kid(k) for k in struktur["kanten"]},
            befunde={b["id"]: b for b in struktur["befunde"]},
            dateien_mit_funktionen=mit_funktionen,
        )

    def ist_funktion(self, knoten_id: str) -> bool:
        k = self.knoten.get(knoten_id)
        return k is not None and k["art"] == "funktion"

    def ist_strukturknoten(self, knoten_id: str) -> bool:
        k = self.knoten.get(knoten_id)
        return knoten_id == SAMMEL or (k is not None and k["art"] != "funktion")

    def bekannt(self, element_id: str) -> bool:
        """Knoten, Kante oder Befund, den die Karte hervorheben kann."""
        return element_id in self.knoten or element_id in self.kanten or element_id in self.befunde

    def datei_hash(self, pfad: str) -> str | None:
        k = self.knoten.get("datei:" + pfad)
        return k.get("hash") if k else None


# ---------------------------------------------------------------- Sprungadressen


def pruefe_ansicht(ansicht: Any, index: Index) -> list[str]:
    """Probleme einer Sprungadresse der Karte (leer, wenn sie passt)."""
    if not isinstance(ansicht, str) or not ansicht.startswith("#") or len(ansicht) < 2:
        return ["ansicht muss eine Sprungadresse sein, die mit # beginnt"]
    try:
        paare = parse_qsl(ansicht[1:], keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return [f"ansicht {ansicht!r} ist nicht lesbar"]
    p: list[str] = []
    werte: dict[str, str] = {}
    for schluessel, wert in paare:
        if schluessel not in _SCHLUESSEL_ANSICHT:
            p.append(f"ansicht: unbekannter Schlüssel {schluessel!r}")
        elif schluessel in werte:
            p.append(f"ansicht: {schluessel} doppelt")
        werte[schluessel] = wert
    if p:
        return p

    def braucht(schluessel: str, wovon: str) -> None:
        if schluessel in werte and wovon not in werte:
            p.append(f"ansicht: {schluessel} nur zusammen mit {wovon}")

    ebene = werte.get("ebene")
    if ebene is not None and ebene not in _EBENEN:
        p.append(f"ansicht: unbekannte ebene {ebene!r}")
    if "knoten" in werte and not index.ist_strukturknoten(werte["knoten"]):
        p.append(f"ansicht: unbekannter Knoten {werte['knoten']}")
    if "befund" in werte and werte["befund"] not in index.befunde:
        p.append(f"ansicht: unbekannter Befund {werte['befund']}")
    if "grenze" in werte:
        befund = index.befunde.get(werte["grenze"])
        if befund is None or befund["regel"] != "markierung-verlassen":
            p.append(f"ansicht: {werte['grenze']} ist keine Grenzkante der Markierungs-Kette")
    if "kante" in werte and werte["kante"] not in index.struktur_kanten:
        p.append(f"ansicht: unbekannte Kante {werte['kante']}")
    for schluessel in ("funktion", "gewaehlt"):
        if schluessel in werte and not index.ist_funktion(werte[schluessel]):
            p.append(f"ansicht: unbekannte Funktion {werte[schluessel]}")
    braucht("weg", "funktion")
    braucht("tiefe", "weg")
    braucht("gewaehlt", "weg")
    if "weg" in werte and werte["weg"] not in ("vor", "rueck"):
        p.append("ansicht: weg muss vor oder rueck sein")
    if "tiefe" in werte and not (
        werte["tiefe"].isdigit() and 1 <= int(werte["tiefe"]) <= TIEFE_MAX
    ):
        p.append(f"ansicht: tiefe muss eine Zahl von 1 bis {TIEFE_MAX} sein")
    if "datei-funktionen" in werte and werte["datei-funktionen"] not in (
        index.dateien_mit_funktionen
    ):
        p.append(f"ansicht: keine Datei mit Funktionen: {werte['datei-funktionen']}")
    if ("von" in werte) != ("nach" in werte):
        p.append("ansicht: von und nach nur zusammen")
    elif "von" in werte:
        pruefe = index.ist_funktion if ebene == "funktion" else index.ist_strukturknoten
        for schluessel in ("von", "nach"):
            if not pruefe(werte[schluessel]):
                p.append(f"ansicht: unbekannter Knoten {werte[schluessel]} ({schluessel})")
    return p


# ---------------------------------------------------------------- Entwurf prüfen


def _nicht_leer(wert: Any) -> bool:
    return isinstance(wert, str) and wert.strip() != ""


def _pruefe_belege(belege: Any, wo: str, index: Index, p: list[str]) -> None:
    if not isinstance(belege, list) or not belege:
        p.append(f"{wo}: belege braucht mindestens einen Beleg")
        return
    for beleg in belege:
        if not isinstance(beleg, dict) or set(beleg) != {"datei", "zeile"}:
            p.append(f"{wo}: Beleg braucht genau datei und zeile")
            continue
        datei, zeile = beleg["datei"], beleg["zeile"]
        if not isinstance(datei, str) or "datei:" + datei not in index.knoten:
            p.append(f"{wo}: unbekannte Datei im Beleg {datei}")
            continue
        if not isinstance(zeile, int) or isinstance(zeile, bool) or zeile < 1:
            p.append(f"{wo}: zeile im Beleg zu {datei} muss eine ganze Zahl ≥ 1 sein")
            continue
        zeilen = index.knoten["datei:" + datei].get("zeilen")
        if isinstance(zeilen, int) and zeile > zeilen:
            p.append(f"{wo}: {datei} hat nur {zeilen} Zeilen (Beleg nennt {zeile})")


def _pruefe_schritt(schritt: Any, nr: int, index: Index, p: list[str]) -> None:
    wo = f"schritte[{nr}]"
    if not isinstance(schritt, dict):
        p.append(f"{wo}: kein Objekt")
        return
    for schluessel in sorted(set(schritt) - _FELDER_SCHRITT):
        p.append(f"{wo}: unbekannter Schlüssel {schluessel!r}")
    for feld in ("titel", "text"):
        if not _nicht_leer(schritt.get(feld)):
            p.append(f"{wo}: braucht {feld}")
    p.extend(f"{wo}: {problem}" for problem in pruefe_ansicht(schritt.get("ansicht"), index))
    hervorheben = schritt.get("hervorheben")
    if (
        not isinstance(hervorheben, list)
        or not HERVORHEBEN_MIN <= len(hervorheben) <= HERVORHEBEN_MAX
        or not all(isinstance(i, str) for i in hervorheben)
    ):
        p.append(f"{wo}: hervorheben braucht {HERVORHEBEN_MIN} bis {HERVORHEBEN_MAX} Ids als Liste")
    else:
        if len(set(hervorheben)) != len(hervorheben):
            p.append(f"{wo}: hervorheben enthält eine Id doppelt")
        for element_id in hervorheben:
            if not index.bekannt(element_id):
                p.append(f"{wo}: unbekannte Id {element_id}")
    _pruefe_belege(schritt.get("belege"), wo, index, p)


def pruefe_entwurf(entwurf: Any, messung: dict[str, Any]) -> list[str]:
    """Liste aller Probleme einer Führung; leer, wenn alles passt."""
    if not isinstance(entwurf, dict):
        return ["Entwurf ist kein JSON-Objekt"]
    index = Index.aus(messung)
    p: list[str] = []
    if entwurf.get("schema", SCHEMA_FUEHRUNG) != SCHEMA_FUEHRUNG:
        p.append(f"schema {entwurf.get('schema')!r} wird nicht unterstützt")
    for schluessel in sorted(set(entwurf) - _FELDER):
        p.append(f"unbekannter Schlüssel {schluessel!r}")
    name = entwurf.get("name")
    if not isinstance(name, str) or not NAME_MUSTER.fullmatch(name):
        p.append("name: Kleinbuchstaben, Ziffern und - (etwa stift-bis-strich)")
    for feld in ("titel", "frage"):
        if not _nicht_leer(entwurf.get(feld)):
            p.append(f"braucht {feld}")
    schritte = entwurf.get("schritte")
    if not isinstance(schritte, list) or not SCHRITTE_MIN <= len(schritte) <= SCHRITTE_MAX:
        p.append(f"schritte: {SCHRITTE_MIN} bis {SCHRITTE_MAX} Schritte als Liste")
        schritte = schritte if isinstance(schritte, list) else []
    for nr, schritt in enumerate(schritte, 1):
        _pruefe_schritt(schritt, nr, index, p)
    return p


# ---------------------------------------------------------------- Übernehmen


class EntwurfFehler(Exception):
    """Die Führung passt nicht zur Messung; nichts wird geschrieben. Exit-Code 2."""

    def __init__(self, probleme: list[str]) -> None:
        super().__init__(f"{len(probleme)} Problem(e) in der Führung")
        self.probleme = probleme


def hashes_des_schritts(schritt: dict[str, Any], index: Index) -> dict[str, str]:
    """Hashes aller Knoten aus ``hervorheben`` und der Dateien aus ``belege``; Knoten ohne
    ``hash`` (Kanten, Befunde, implizite Konstruktoren) fehlen."""
    hashes: dict[str, str] = {}
    for element_id in schritt["hervorheben"]:
        k = index.knoten.get(element_id)
        if k is not None and isinstance(k.get("hash"), str):
            hashes[element_id] = k["hash"]
    for beleg in schritt["belege"]:
        wert = index.datei_hash(beleg["datei"])
        if isinstance(wert, str):
            hashes["datei:" + beleg["datei"]] = wert
    return dict(sorted(hashes.items()))


def uebernimm(entwurf: Any, messung: dict[str, Any]) -> dict[str, Any]:
    """Geprüfte Führung mit eingesetzten Hashes; ``EntwurfFehler`` bei Problemen."""
    probleme = pruefe_entwurf(entwurf, messung)
    if probleme:
        raise EntwurfFehler(probleme)
    index = Index.aus(messung)
    schritte = []
    for s in entwurf["schritte"]:
        schritte.append(
            {
                "ansicht": s["ansicht"],
                "belege": [{"datei": b["datei"], "zeile": b["zeile"]} for b in s["belege"]],
                "hashes": hashes_des_schritts(s, index),
                "hervorheben": list(s["hervorheben"]),
                "text": s["text"],
                "titel": s["titel"],
            }
        )
    return {
        "frage": entwurf["frage"],
        "name": entwurf["name"],
        "schema": SCHEMA_FUEHRUNG,
        "schritte": schritte,
        "titel": entwurf["titel"],
    }


# ---------------------------------------------------------------- Lesen und Stand


def lies_fuehrung(pfad: Path) -> dict[str, Any]:
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as fehler:
        raise FuehrungsFehler(f"{pfad.name}: nicht lesbar ({fehler})") from fehler
    except json.JSONDecodeError as fehler:
        raise FuehrungsFehler(f"{pfad.name}: kein gültiges JSON ({fehler})") from fehler
    if not isinstance(daten, dict) or daten.get("schema") != SCHEMA_FUEHRUNG:
        schema = daten.get("schema") if isinstance(daten, dict) else None
        raise FuehrungsFehler(
            f"{pfad.name}: schema {schema!r} wird nicht unterstützt (erwartet {SCHEMA_FUEHRUNG})"
        )
    if not isinstance(daten.get("schritte"), list) or not isinstance(daten.get("name"), str):
        raise FuehrungsFehler(f"{pfad.name}: name oder schritte fehlen")
    return daten


def lies_fuehrungen(ordner: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Alle Führungen im Ordner, nach Name sortiert, und Warnungen zu unlesbaren Dateien."""
    fuehrungen: list[dict[str, Any]] = []
    warnungen: list[str] = []
    if not ordner.is_dir():
        return fuehrungen, warnungen
    for pfad in sorted(ordner.glob("*.json")):
        try:
            daten = lies_fuehrung(pfad)
        except FuehrungsFehler as fehler:
            warnungen.append(str(fehler))
            continue
        if daten["name"] != pfad.stem:
            warnungen.append(f"{pfad.name}: name {daten['name']!r} passt nicht zum Dateinamen")
            continue
        fuehrungen.append(daten)
    fuehrungen.sort(key=lambda f: f["name"])
    return fuehrungen, warnungen


def stand_des_schritts(schritt: Any, index: Index) -> tuple[str, list[str]]:
    """``ok``, ``veraltet`` oder ``kaputt`` mit Gründen.

    Kaputt: eine Id aus ``hervorheben``, eine Datei aus ``belege`` oder ein Teil der Sprungadresse
    fehlt in der Messung. Veraltet: ein gespeicherter Hash stimmt nicht mehr.
    """
    if not isinstance(schritt, dict):
        return STAND_KAPUTT, ["Schritt ist kein Objekt"]
    gruende: list[str] = list(pruefe_ansicht(schritt.get("ansicht"), index))
    hervorheben = schritt.get("hervorheben")
    for element_id in hervorheben if isinstance(hervorheben, list) else []:
        if not isinstance(element_id, str) or not index.bekannt(element_id):
            gruende.append(f"Id fehlt: {element_id}")
    belege = schritt.get("belege")
    for beleg in belege if isinstance(belege, list) else []:
        datei = beleg.get("datei") if isinstance(beleg, dict) else None
        if not isinstance(datei, str) or "datei:" + datei not in index.knoten:
            gruende.append(f"Datei fehlt: {datei}")
    if gruende:
        return STAND_KAPUTT, gruende
    hashes = schritt.get("hashes")
    for element_id, wert in sorted((hashes if isinstance(hashes, dict) else {}).items()):
        k = index.knoten.get(element_id)
        if k is None:
            # Ein Beleg kann auf eine Datei zeigen, die nicht in hervorheben steht.
            gruende.append(f"Id fehlt: {element_id}")
        elif k.get("hash") != wert:
            gruende.append(f"geändert: {element_id}")
    if any(g.startswith("Id fehlt") for g in gruende):
        return STAND_KAPUTT, gruende
    return (STAND_VERALTET if gruende else STAND_OK), gruende


def gesamtstand(staende: list[str]) -> str:
    if STAND_KAPUTT in staende:
        return STAND_KAPUTT
    return STAND_VERALTET if STAND_VERALTET in staende else STAND_OK


@dataclass
class Stand:
    name: str
    titel: str
    stand: str
    schritte: list[tuple[str, list[str]]]  # je Schritt (Stand, Gründe)


def stand_der_fuehrung(fuehrung: dict[str, Any], index: Index) -> Stand:
    schritte = [stand_des_schritts(s, index) for s in fuehrung["schritte"]]
    titel = fuehrung.get("titel")
    return Stand(
        name=fuehrung["name"],
        titel=titel if isinstance(titel, str) else fuehrung["name"],
        stand=gesamtstand([s for s, _ in schritte]),
        schritte=schritte,
    )


def fuer_karte(fuehrungen: list[dict[str, Any]], messung: dict[str, Any]) -> list[dict[str, Any]]:
    """Eingebetteter Block der Karte: je Führung Titel, Frage und Schritte mit ``stand``."""
    index = Index.aus(messung)
    block = []
    for f in fuehrungen:
        schritte = []
        for s in f["schritte"]:
            stand, _ = stand_des_schritts(s, index)
            if not isinstance(s, dict):
                s = {}
            schritte.append(
                {
                    "ansicht": s.get("ansicht") if isinstance(s.get("ansicht"), str) else "",
                    "belege": [
                        b
                        for b in (s.get("belege") if isinstance(s.get("belege"), list) else [])
                        if isinstance(b, dict)
                    ],
                    "hervorheben": [
                        i
                        for i in (
                            s.get("hervorheben") if isinstance(s.get("hervorheben"), list) else []
                        )
                        if isinstance(i, str)
                    ],
                    "stand": stand,
                    "text": s.get("text") if isinstance(s.get("text"), str) else "",
                    "titel": s.get("titel") if isinstance(s.get("titel"), str) else "",
                }
            )
        block.append(
            {
                "frage": f.get("frage") if isinstance(f.get("frage"), str) else "",
                "name": f["name"],
                "schritte": schritte,
                "stand": gesamtstand([s["stand"] for s in schritte]),
                "titel": f.get("titel") if isinstance(f.get("titel"), str) else f["name"],
            }
        )
    return block
