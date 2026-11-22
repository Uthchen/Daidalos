"""Gemeinsame Hilfen für tree-sitter: Parser je Sprache und kleine Baum-Werkzeuge."""

from __future__ import annotations

from collections.abc import Iterator
from functools import cache

import tree_sitter_c
import tree_sitter_kotlin
from tree_sitter import Language, Node, Parser


@cache
def _sprache(name: str) -> Language:
    if name == "kotlin":
        return Language(tree_sitter_kotlin.language())
    if name == "c":
        return Language(tree_sitter_c.language())
    raise ValueError(f"keine Grammatik für {name}")


def parse(name: str, quelle: bytes) -> Node:
    """Liefert den Wurzelknoten des Syntaxbaums."""
    return Parser(_sprache(name)).parse(quelle).root_node


def text(knoten: Node) -> str:
    return (knoten.text or b"").decode("utf-8", "replace")


def zeile(knoten: Node) -> int:
    """Zeile, 1-basiert."""
    return knoten.start_point[0] + 1


def alle(knoten: Node) -> Iterator[Node]:
    """Alle Knoten in Dokumentreihenfolge (Tiefensuche, ohne Rekursion)."""
    stapel = [knoten]
    while stapel:
        aktuell = stapel.pop()
        yield aktuell
        stapel.extend(reversed(aktuell.children))


def benannte_kinder(knoten: Node, typ: str) -> list[Node]:
    return [kind for kind in knoten.named_children if kind.type == typ]


def erstes_kind(knoten: Node, typ: str) -> Node | None:
    for kind in knoten.named_children:
        if kind.type == typ:
            return kind
    return None


def string_wert(knoten: Node) -> str | None:
    """Inhalt eines einfachen String-Literals ohne Interpolation, sonst ``None``."""
    if knoten.type == "value_argument":
        kinder = knoten.named_children
        if len(kinder) != 1:
            return None
        knoten = kinder[0]
    if knoten.type != "string_literal":
        return None
    teile: list[str] = []
    for kind in knoten.named_children:
        if kind.type == "string_content":
            teile.append(text(kind))
        else:
            return None  # Interpolation oder Escape: nicht einfach
    return "".join(teile)
