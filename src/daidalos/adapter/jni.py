"""JNI-Brücke: ``external fun`` in Kotlin und ``Java_…``-Funktionen in C/C++.

Abgleich über die JNI-Namensregel: ``Java_`` + Klasse (``.`` und ``/`` als ``_``) + ``_`` + Methode,
optional ``__`` + Signatur. Escapes: ``_1`` = ``_``, ``_2`` = ``;``, ``_3`` = ``[``,
``_0xxxx`` = Unicode-Zeichen (vier Hex-Ziffern).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from daidalos.adapter.baum import alle, parse, text, zeile

PRAEFIX = "Java_"
_HEX = re.compile(r"[0-9a-fA-F]{4}")


@dataclass(frozen=True)
class CFunktion:
    name: str  # ``Java_…``
    zeile: int


@dataclass(frozen=True)
class JniName:
    klasse: str  # JVM-Name mit Punkten, innere Klassen mit ``$``, z. B. ``de.a.Insel``
    methode: str
    signatur: str | None  # dekodierte Signatur bei überladenen Varianten


def kodiere(teil: str) -> str:
    """Kodiert einen Namen nach der JNI-Regel (``.`` und ``/`` werden zu ``_``)."""
    ergebnis: list[str] = []
    for zeichen in teil:
        if zeichen in "./":
            ergebnis.append("_")
        elif zeichen == "_":
            ergebnis.append("_1")
        elif zeichen == ";":
            ergebnis.append("_2")
        elif zeichen == "[":
            ergebnis.append("_3")
        elif zeichen.isascii() and zeichen.isalnum():
            ergebnis.append(zeichen)
        else:
            ergebnis.append(f"_0{ord(zeichen):04x}")
    return "".join(ergebnis)


def jni_name(klasse: str, methode: str) -> str:
    """Kurzer JNI-Name ohne Signatur, z. B. ``Java_de_a_Insel_rechne_1schnell``."""
    return f"{PRAEFIX}{kodiere(klasse)}_{kodiere(methode)}"


def dekodiere(name: str) -> JniName | None:
    """Zerlegt einen ``Java_…``-Namen. ``None``, wenn er nicht der Regel folgt."""
    if not name.startswith(PRAEFIX):
        return None
    rest = name[len(PRAEFIX) :]
    teile: list[str] = []
    aktuell: list[str] = []
    signatur_ab: int | None = None
    i = 0
    while i < len(rest):
        zeichen = rest[i]
        if zeichen != "_":
            aktuell.append(zeichen)
            i += 1
            continue
        folge = rest[i + 1] if i + 1 < len(rest) else ""
        if folge == "1":
            aktuell.append("_")
            i += 2
        elif folge == "2":
            aktuell.append(";")
            i += 2
        elif folge == "3":
            aktuell.append("[")
            i += 2
        elif folge == "0" and _HEX.fullmatch(rest[i + 2 : i + 6]):
            aktuell.append(chr(int(rest[i + 2 : i + 6], 16)))
            i += 6
        elif folge == "_" and rest[i + 2 : i + 3] == "0" and _HEX.fullmatch(rest[i + 3 : i + 7]):
            # ``__0xxxx``: Trenner, danach ein Unicode-Escape (keine Signatur beginnt mit ``_0``)
            teile.append("".join(aktuell))
            aktuell = []
            i += 1
        elif folge == "_":
            # ``__``: Ende des Methodennamens, danach die Signatur
            teile.append("".join(aktuell))
            aktuell = []
            signatur_ab = len(teile)
            i += 2
        else:
            teile.append("".join(aktuell))
            aktuell = []
            i += 1
    teile.append("".join(aktuell))
    if signatur_ab is not None:
        kopf, signatur_teile = teile[:signatur_ab], teile[signatur_ab:]
        signatur: str | None = "/".join(signatur_teile)
    else:
        kopf, signatur = teile, None
    if len(kopf) < 2 or any(not t for t in kopf):
        return None
    return JniName(klasse=".".join(kopf[:-1]), methode=kopf[-1], signatur=signatur)


def finde_c_funktionen(quelle: bytes) -> list[CFunktion]:
    """Funktionsdefinitionen, deren Name mit ``Java_`` beginnt (tree-sitter-c, auch für C++)."""
    wurzel = parse("c", quelle)
    gefunden: dict[str, int] = {}
    for knoten in alle(wurzel):
        if knoten.type != "function_declarator":
            continue
        # Nur Definitionen: ein function_definition muss darüber liegen.
        oben = knoten.parent
        while oben is not None and oben.type in {"pointer_declarator", "parenthesized_declarator"}:
            oben = oben.parent
        if oben is None or oben.type != "function_definition":
            continue
        bezeichner = knoten.child_by_field_name("declarator")
        if bezeichner is None or bezeichner.type != "identifier":
            continue
        name = text(bezeichner)
        if name.startswith(PRAEFIX):
            gefunden.setdefault(name, zeile(bezeichner))
    return [CFunktion(name, z) for name, z in sorted(gefunden.items())]
