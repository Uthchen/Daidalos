"""Kotlin-Adapter für Funktionen: Funktionen, Klassen, Annotationen und rohe Aufrufe einer Datei.

Gelesen wird nur, was im Text steht. Aufgelöst wird erst in ``daidalos.aufrufgraph``. Für jeden
Aufruf hält der Adapter fest, was die Auflösung über seine Umgebung wissen muss: den Empfänger, die
impliziten Empfänger (umgebende Klassen, Erweiterungsempfänger, Lambdas) und welche Namen an der
Stelle lokal deklariert sind.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from tree_sitter import Node

from daidalos.adapter.baum import parse, text, zeile

_KOMMENTARE = frozenset({"line_comment", "block_comment"})
_MODIFIKATOREN = frozenset(
    {
        "override",
        "abstract",
        "open",
        "suspend",
        "inline",
        "operator",
        "infix",
        "external",
        "expect",
        "actual",
    }
)
_SICHTBARKEIT = ("public", "internal", "protected", "private")
# Bereichsfunktionen der Standardbibliothek, deren Lambda einen Empfänger hat.
BEREICH_MIT_EMPFAENGER = frozenset({"apply", "run", "with"})
# Lambdas dieser Funktionen haben einen Empfänger, dessen Typ extern ist.
BEREICH_EXTERN = frozenset({"buildString", "buildList", "buildMap", "buildSet"})
# Funktionen der Standardbibliothek und von Compose, deren Lambda keinen Empfänger hat.
LAMBDA_OHNE_EMPFAENGER = frozenset(
    {
        "all",
        "also",
        "any",
        "associate",
        "associateBy",
        "associateWith",
        "check",
        "checkNotNull",
        "compareBy",
        "count",
        "derivedStateOf",
        "filter",
        "filterIndexed",
        "filterNot",
        "find",
        "first",
        "firstOrNull",
        "flatMap",
        "fold",
        "forEach",
        "forEachIndexed",
        "getOrElse",
        "getOrPut",
        "groupBy",
        "indexOfFirst",
        "indexOfLast",
        "last",
        "lastOrNull",
        "lazy",
        "let",
        "map",
        "mapIndexed",
        "mapNotNull",
        "maxByOrNull",
        "maxOf",
        "minByOrNull",
        "minOf",
        "none",
        "onEach",
        "partition",
        "reduce",
        "remember",
        "removeAll",
        "removeIf",
        "repeat",
        "require",
        "requireNotNull",
        "retainAll",
        "sortedBy",
        "sortedByDescending",
        "sumOf",
        "synchronized",
        "takeIf",
        "takeUnless",
        "thenBy",
        "use",
    }
)
_VERZWEIGUNGEN = frozenset(
    {"if_expression", "for_statement", "while_statement", "do_while_statement", "catch_block"}
)
# ``?.let`` und Verwandte zählen für die Komplexität.
_SICHERE_BEREICHE = frozenset({"let", "run", "also", "apply", "takeIf"})


# ---------------------------------------------------------------- Ergebnis


@dataclass(frozen=True)
class Parameter:
    name: str
    typ: str | None  # wie geschrieben, ohne Leerzeichen
    vorgabe: bool
    vararg: bool


@dataclass(frozen=True)
class AnnotationRoh:
    name: str  # wie geschrieben, ohne Argumente und ohne Ziel (``@get:``)
    zeile: int


@dataclass(frozen=True)
class Empfaenger:
    """Empfänger eines Aufrufs.

    ``art``: ``ohne``, ``this`` (``name`` = Label oder ``None``), ``super`` (``name`` = Typ in
    ``super<I>`` oder ``None``), ``kette`` (``name`` = erster Bezeichner, ``rest`` = weitere
    Eigenschaften, ``herkunft`` = ``lokal``, ``parameter`` oder ``frei``, ``typ`` = Typ des
    lokalen Namens oder ``None``) und ``unbekannt`` (Rückgabewert, Index, Ausdruck).
    """

    art: str
    name: str | None = None
    rest: tuple[str, ...] = ()
    herkunft: str | None = None
    typ: str | None = None


@dataclass(frozen=True)
class Rahmen:
    """Ein impliziter Empfänger, von innen nach außen.

    ``art``: ``klasse`` (``wert`` = Klassenkette in der Datei), ``erweiterung`` (``wert`` =
    Empfängertyp), ``objekt`` (anonymes Objekt oder lokale Klasse: ``obertypen``, ``namen`` = dort
    deklarierte Funktionen), ``bereich`` (Lambda von ``apply``/``run``/``with``: ``empfaenger``;
    ohne ``empfaenger`` extern) und ``lambda`` (Lambda als Argument von ``wert``; ob es einen
    Empfänger hat, entscheidet die Auflösung).
    """

    art: str
    wert: str | None = None
    obertypen: tuple[str, ...] = ()
    namen: frozenset[str] = frozenset()
    empfaenger: Empfaenger | None = None


@dataclass(frozen=True)
class Aufruf:
    zeile: int
    name: str
    argumente: int | None  # ``None`` bei Funktionsreferenzen
    empfaenger: Empfaenger
    rahmen: tuple[Rahmen, ...]
    # ``wert``: der Name ist ein lokaler Wert oder Parameter (Aufruf eines Werts, keine Funktion);
    # ``lokal``: der Name ist eine lokale Funktion oder Funktion eines anonymen Objekts.
    wert: bool = False
    lokal: bool = False
    referenz: bool = False


@dataclass
class FunktionRoh:
    behaelter: str  # Klassenkette relativ zur Datei, oberste Ebene ``""``
    name: str  # ``f``, ``<init>``, ``<get-feld>``
    erweiterung: str | None
    parameter: list[Parameter]
    zeile_von: int
    zeile_bis: int
    sichtbarkeit: str
    modifikatoren: list[str]
    annotationen: list[AnnotationRoh]
    hash: str
    zeilen: int
    komplexitaet: int
    aufrufe: list[Aufruf] = field(default_factory=list)
    # Klassenkette, in der die Funktion steht (für ``this``); bei Erweiterungen ebenso
    klasse: str = ""

    @property
    def stelligkeit(self) -> int:
        return len(self.parameter)


@dataclass
class KlasseRoh:
    name: str  # Kette relativ zur Datei, z. B. ``Aussen.Innen`` oder ``Klasse.Companion``
    art: str  # klasse, schnittstelle, objekt, companion, enum, annotation, enum-eintrag
    zeile: int
    annotationen: list[AnnotationRoh]
    obertypen: list[str]  # wie geschrieben, ohne Typargumente
    eigenschaften: dict[str, str | None]  # Name → Typ (wie geschrieben) oder ``None``
    typparameter: dict[str, str | None]
    primaer: list[Parameter] | None  # ``None``: kein primärer Konstruktor
    modifikatoren: list[str]
    companion: str | None = None  # Kette des Companion
    konstruktor_knoten: bool = False  # ob ein ``<init>``-Knoten für den primären entsteht


@dataclass
class FunktionenDatei:
    klassen: list[KlasseRoh] = field(default_factory=list)
    funktionen: list[FunktionRoh] = field(default_factory=list)
    datei_annotationen: list[AnnotationRoh] = field(default_factory=list)
    # Eigenschaften der obersten Ebene: Name → Typ oder ``None``
    eigenschaften: dict[str, str | None] = field(default_factory=dict)
    typaliase: set[str] = field(default_factory=set)


# ---------------------------------------------------------------- Hilfen


def ohne_leerzeichen(wert: str) -> str:
    return "".join(wert.split())


def _modifikator_knoten(knoten: Node) -> Node | None:
    for kind in knoten.named_children:
        if kind.type == "modifiers":
            return kind
    return None


def _modifikatoren(knoten: Node) -> tuple[str, list[str], list[AnnotationRoh]]:
    """Sichtbarkeit, sortierte Modifikatoren und Annotationen einer Deklaration."""
    sichtbarkeit = "public"
    gefunden: set[str] = set()
    annotationen: list[AnnotationRoh] = []
    mod = _modifikator_knoten(knoten)
    if mod is not None:
        for kind in mod.named_children:
            if kind.type == "annotation":
                name = _annotationsname(kind)
                if name:
                    annotationen.append(AnnotationRoh(name, zeile(kind)))
                continue
            wort = text(kind)
            if wort in _SICHTBARKEIT:
                sichtbarkeit = wort
            elif wort in _MODIFIKATOREN:
                gefunden.add(wort)
    return sichtbarkeit, sorted(gefunden), annotationen


def _annotationsname(annotation: Node) -> str | None:
    for kind in annotation.named_children:
        if kind.type == "user_type":
            return typ_basis(text(kind))
        if kind.type == "constructor_invocation":
            typ = next((k for k in kind.named_children if k.type == "user_type"), None)
            return typ_basis(text(typ)) if typ is not None else None
    return None


def typ_basis(typ: str | None) -> str | None:
    """``de.a.Liste<Punkt>?`` → ``de.a.Liste``. Funktionstypen und Leeres → ``None``."""
    if typ is None:
        return None
    wert = ohne_leerzeichen(typ)
    while wert.startswith("@"):
        # Annotation vor dem Typ, z. B. ``@Composable()->Unit``
        rest = wert[1:]
        ende = 0
        while ende < len(rest) and (rest[ende].isalnum() or rest[ende] in "_."):
            ende += 1
        wert = rest[ende:]
    wert = wert.removeprefix("suspend")
    if not wert or wert.startswith("(") or "->" in wert:
        return None
    tiefe = 0
    basis: list[str] = []
    for zeichen in wert:
        if zeichen == "<":
            tiefe += 1
        elif zeichen == ">":
            tiefe -= 1
        elif tiefe == 0 and zeichen not in "?!":
            basis.append(zeichen)
    return "".join(basis) or None


def _typ_nach(knoten: Node, start: int) -> str | None:
    """Text des ersten Typknotens unter den Kindern ab ``start``."""
    for kind in knoten.children[start:]:
        if kind.type in {
            "user_type",
            "nullable_type",
            "function_type",
            "parenthesized_type",
            "non_nullable_type",
            "type_modifiers",
            "definitely_non_nullable_type",
        }:
            return ohne_leerzeichen(text(kind))
        if kind.type == "=":
            return None
    return None


def _name(knoten: Node) -> str | None:
    name = knoten.child_by_field_name("name")
    return text(name) if name is not None else None


def _koerper(knoten: Node) -> Node | None:
    for kind in knoten.named_children:
        if kind.type in {"class_body", "enum_class_body"}:
            return kind
    return None


def _klassenart(knoten: Node) -> str:
    if knoten.type == "object_declaration":
        return "objekt"
    if any(kind.type == "interface" for kind in knoten.children):
        return "schnittstelle"
    mod = _modifikator_knoten(knoten)
    if mod is not None:
        woerter = {text(k) for k in mod.named_children}
        if "enum" in woerter:
            return "enum"
        if "annotation" in woerter:
            return "annotation"
    return "klasse"


def _obertypen(knoten: Node) -> list[str]:
    ergebnis: list[str] = []
    for kind in knoten.named_children:
        if kind.type != "delegation_specifiers":
            continue
        for spezifikation in kind.named_children:
            for teil in spezifikation.named_children:
                typ: Node | None = None
                if teil.type == "user_type":
                    typ = teil
                elif teil.type in {"constructor_invocation", "explicit_delegation"}:
                    typ = next((k for k in teil.named_children if k.type == "user_type"), None)
                if typ is not None:
                    basis = typ_basis(text(typ))
                    if basis:
                        ergebnis.append(basis)
    return ergebnis


def _typparameter(knoten: Node) -> dict[str, str | None]:
    ergebnis: dict[str, str | None] = {}
    for kind in knoten.named_children:
        if kind.type != "type_parameters":
            continue
        for tp in kind.named_children:
            if tp.type != "type_parameter":
                continue
            name = next((k for k in tp.named_children if k.type == "identifier"), None)
            if name is None:
                continue
            schranke = next(
                (k for k in tp.named_children if k.type in {"user_type", "nullable_type"}), None
            )
            ergebnis[text(name)] = typ_basis(text(schranke)) if schranke is not None else None
    return ergebnis


def _funktionsparameter(knoten: Node) -> list[Parameter]:
    liste = next((k for k in knoten.named_children if k.type == "function_value_parameters"), None)
    if liste is None:
        return []
    ergebnis: list[Parameter] = []
    kinder = liste.children
    vararg = False
    for i, kind in enumerate(kinder):
        if kind.type == "parameter_modifiers":
            vararg = vararg or "vararg" in text(kind).split()
            continue
        if kind.type != "parameter":
            continue
        name = next((k for k in kind.named_children if k.type == "identifier"), None)
        typ = _typ_nach(kind, 1)
        vorgabe = i + 1 < len(kinder) and kinder[i + 1].type == "="
        ergebnis.append(Parameter(text(name) if name else "_", typ, vorgabe, vararg))
        vararg = False
    return ergebnis


def _klassenparameter(knoten: Node) -> list[Parameter] | None:
    primaer = next((k for k in knoten.named_children if k.type == "primary_constructor"), None)
    if primaer is None:
        return None
    liste = next((k for k in primaer.named_children if k.type == "class_parameters"), None)
    if liste is None:
        return []
    ergebnis: list[Parameter] = []
    for kind in liste.named_children:
        if kind.type != "class_parameter":
            continue
        name = next((k for k in kind.named_children if k.type == "identifier"), None)
        mod = _modifikator_knoten(kind)
        vararg = mod is not None and "vararg" in text(mod).split()
        typ = _typ_nach(kind, 0)
        vorgabe = any(k.type == "=" for k in kind.children)
        ergebnis.append(Parameter(text(name) if name else "_", typ, vorgabe, vararg))
    return ergebnis


def _empfaenger_typ(knoten: Node) -> str | None:
    """Empfängertyp einer Erweiterung: der Typ direkt vor dem Punkt vor dem Namen."""
    vorher: Node | None = None
    for kind in knoten.children:
        if kind.type in {"identifier", "variable_declaration", "function_value_parameters"}:
            return None
        if kind.type == "." and vorher is not None:
            return ohne_leerzeichen(text(vorher))
        if kind.is_named and kind.type not in {"modifiers", "type_parameters"}:
            vorher = kind
    return None


def _hash(*teile: str) -> str:
    inhalt = "\n".join(teile).replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(inhalt.encode("utf-8")).hexdigest()


def _codezeilen(knoten_liste: list[Node]) -> int:
    """Zeilen mit mindestens einem Zeichen, das nicht zu einem Kommentar gehört."""
    zeilen: set[int] = set()
    stapel = list(knoten_liste)
    while stapel:
        k = stapel.pop()
        if k.type in _KOMMENTARE:
            continue
        if k.child_count == 0:
            if k.start_byte == k.end_byte:
                continue
            zeilen.update(range(k.start_point[0], k.end_point[0] + 1))
            continue
        stapel.extend(k.children)
    return len(zeilen)


def _komplexitaet(knoten_liste: list[Node]) -> int:
    """1 + Verzweigungen (Regel in ``docs/datenformat.md``)."""
    wert = 1
    stapel = list(knoten_liste)
    while stapel:
        k = stapel.pop()
        typ = k.type
        if typ in _KOMMENTARE:
            continue
        if typ in _VERZWEIGUNGEN:
            wert += 1
        elif typ == "when_entry":
            if not any(kind.type == "else" for kind in k.children):
                wert += 1
        elif typ == "binary_expression":
            if any(kind.type in {"&&", "||", "?:"} for kind in k.children):
                wert += 1
        elif typ == "navigation_expression":
            kinder = k.children
            if (
                len(kinder) == 3
                and kinder[1].type == "?."
                and text(kinder[2]) in _SICHERE_BEREICHE
                and k.parent is not None
                and k.parent.type == "call_expression"
            ):
                wert += 1
        stapel.extend(k.children)
    return wert


# ---------------------------------------------------------------- Aufrufe in Körpern


@dataclass(frozen=True)
class _Umgebung:
    # Namen in Gültigkeit: Name → (Art, Typ); Art ``lokal``, ``parameter``, ``funktion``
    bereiche: tuple[dict[str, tuple[str, str | None]], ...]
    rahmen: tuple[Rahmen, ...]
    typparameter: dict[str, str | None]

    def mit_bereich(self, bereich: dict[str, tuple[str, str | None]]) -> _Umgebung:
        return _Umgebung((*self.bereiche, bereich), self.rahmen, self.typparameter)

    def mit_rahmen(self, rahmen: Rahmen) -> _Umgebung:
        return _Umgebung(self.bereiche, (rahmen, *self.rahmen), self.typparameter)

    def suche(self, name: str) -> tuple[str, str | None] | None:
        for bereich in reversed(self.bereiche):
            if name in bereich:
                return bereich[name]
        return None

    def typ(self, typ: str | None) -> str | None:
        """Typparameter durch ihre Schranke ersetzen (ohne Schranke: unbekannt)."""
        basis = typ_basis(typ)
        if basis is not None and basis in self.typparameter:
            return self.typparameter[basis]
        return typ


def _deklarierter_typ(variable: Node, umgebung: _Umgebung) -> str | None:
    """Typ einer ``variable_declaration`` (mit Angabe) oder ``None``."""
    return umgebung.typ(_typ_nach(variable, 1))


def _konstruktor_typ(ausdruck: Node | None) -> str | None:
    """``Klasse(…)`` oder ``a.b.Klasse(…)`` mit großem Anfangsbuchstaben → ``Klasse``."""
    if ausdruck is None or ausdruck.type != "call_expression":
        return None
    aufgerufen = ausdruck.named_children[0] if ausdruck.named_children else None
    if aufgerufen is None:
        return None
    kette = _punktkette(aufgerufen)
    if kette and kette[-1][:1].isupper():
        return ".".join(kette)
    return None


def _punktkette(knoten: Node) -> list[str] | None:
    if knoten.type == "identifier":
        return [text(knoten)]
    if knoten.type == "navigation_expression":
        kinder = knoten.children
        if len(kinder) != 3 or kinder[1].type != "." or kinder[2].type != "identifier":
            return None
        links = _punktkette(kinder[0])
        return None if links is None else [*links, text(kinder[2])]
    return None


def _initialisierer(knoten: Node) -> Node | None:
    """Ausdruck hinter ``=`` einer ``property_declaration``."""
    gesehen = False
    for kind in knoten.children:
        if gesehen and kind.is_named:
            return kind
        if kind.type == "=":
            gesehen = True
    return None


class _Sammler:
    """Läuft durch einen Funktionskörper und sammelt Aufrufe mit ihrer Umgebung."""

    def __init__(self) -> None:
        self.aufrufe: list[Aufruf] = []

    # ------------------------------------------------------------ Empfänger

    def _empfaenger(self, knoten: Node, umgebung: _Umgebung) -> Empfaenger:
        if knoten.type == "this_expression":
            label = next((k for k in knoten.named_children if k.type == "identifier"), None)
            return Empfaenger("this", text(label) if label is not None else None)
        if knoten.type == "super_expression":
            typ = next((k for k in knoten.named_children if k.type == "user_type"), None)
            return Empfaenger("super", typ_basis(text(typ)) if typ is not None else None)
        kette = _punktkette(knoten)
        if kette is None:
            # ``this.feld.f()``: Kette hinter ``this``
            if knoten.type == "navigation_expression":
                teile: list[str] = []
                aktuell = knoten
                while aktuell.type == "navigation_expression":
                    kinder = aktuell.children
                    if len(kinder) != 3 or kinder[1].type != "." or kinder[2].type != "identifier":
                        return Empfaenger("unbekannt")
                    teile.insert(0, text(kinder[2]))
                    aktuell = kinder[0]
                if aktuell.type == "this_expression" and not aktuell.named_children:
                    return Empfaenger("kette", teile[0], tuple(teile[1:]), "this")
            return Empfaenger("unbekannt")
        erster, rest = kette[0], tuple(kette[1:])
        lokal = umgebung.suche(erster)
        if lokal is not None:
            art, typ = lokal
            if art == "funktion":
                return Empfaenger("unbekannt")
            return Empfaenger("kette", erster, rest, art, typ)
        return Empfaenger("kette", erster, rest, "frei")

    # ------------------------------------------------------------ Lauf

    def lauf(self, start: list[Node], umgebung: _Umgebung) -> None:
        # Stapel aus (Knoten, Umgebung) oder (None, Eintrag) zum späten Eintragen lokaler Namen.
        stapel: list[tuple[Node | None, _Umgebung, tuple[dict, str, tuple] | None]] = [
            (k, umgebung, None) for k in reversed(start)
        ]
        while stapel:
            knoten, umg, eintrag = stapel.pop()
            if knoten is None:
                assert eintrag is not None
                bereich, name, wert = eintrag
                bereich[name] = wert
                continue
            typ = knoten.type
            if typ in _KOMMENTARE:
                continue
            kinder: list[Node] = list(knoten.children)
            neue = umg
            spaeter: list[tuple[dict, str, tuple]] = []

            if typ in {"block", "control_structure_body", "when_entry"}:
                neue = umg.mit_bereich({})
            elif typ == "lambda_literal":
                neue = self._lambda(knoten, umg)
            elif typ == "for_statement":
                bereich: dict[str, tuple[str, str | None]] = {}
                for kind in knoten.named_children:
                    if kind.type == "variable_declaration":
                        name = kind.named_children[0] if kind.named_children else None
                        if name is not None:
                            bereich[text(name)] = ("lokal", _deklarierter_typ(kind, umg))
                    elif kind.type == "multi_variable_declaration":
                        for v in kind.named_children:
                            if v.named_children:
                                bereich[text(v.named_children[0])] = ("lokal", None)
                neue = umg.mit_bereich(bereich)
            elif typ == "catch_block":
                name = next((k for k in knoten.named_children if k.type == "identifier"), None)
                neue = umg.mit_bereich(
                    {text(name): ("lokal", _typ_nach(knoten, 0))} if name is not None else {}
                )
            elif typ == "property_declaration":
                bereich_jetzt = umg.bereiche[-1]
                initial = _initialisierer(knoten)
                for kind in knoten.named_children:
                    if kind.type == "variable_declaration" and kind.named_children:
                        name = text(kind.named_children[0])
                        decl = _deklarierter_typ(kind, umg) or _konstruktor_typ(initial)
                        spaeter.append((bereich_jetzt, name, ("lokal", decl)))
                    elif kind.type == "multi_variable_declaration":
                        for v in kind.named_children:
                            if v.named_children:
                                spaeter.append(
                                    (bereich_jetzt, text(v.named_children[0]), ("lokal", None))
                                )
            elif typ == "function_declaration":
                # lokale Funktion: gehört zur umgebenden Funktion
                name = _name(knoten)
                if name is not None:
                    umg.bereiche[-1][name] = ("funktion", None)
                bereich = {
                    p.name: ("parameter", umg.typ(p.typ)) for p in _funktionsparameter(knoten)
                }
                neue = _Umgebung(
                    (*umg.bereiche, bereich),
                    umg.rahmen,
                    {**umg.typparameter, **_typparameter(knoten)},
                )
            elif typ in {"object_literal", "class_declaration", "object_declaration"}:
                # anonymes Objekt oder lokale Klasse: eigener impliziter Empfänger
                koerper = _koerper(knoten)
                namen = frozenset(
                    n
                    for k in (koerper.named_children if koerper is not None else [])
                    if k.type == "function_declaration" and (n := _name(k)) is not None
                )
                if typ != "object_literal" and (name := _name(knoten)) is not None:
                    umg.bereiche[-1][name] = ("funktion", None)
                neue = umg.mit_rahmen(
                    Rahmen("objekt", obertypen=tuple(_obertypen(knoten)), namen=namen)
                ).mit_bereich({})
                if koerper is not None:
                    for k in koerper.named_children:
                        if k.type == "function_declaration" and (n := _name(k)) is not None:
                            neue.bereiche[-1].setdefault(n, ("funktion", None))
            elif typ == "call_expression":
                self._aufruf(knoten, umg)
            elif typ == "callable_reference":
                self._referenz(knoten, umg, None)
            elif typ == "navigation_expression":
                kinder_alle = knoten.children
                if len(kinder_alle) == 3 and kinder_alle[1].type == "::":
                    self._referenz(knoten, umg, kinder_alle[0])

            if spaeter:
                for eintrag_neu in spaeter:
                    stapel.append((None, umg, eintrag_neu))
            for kind in reversed(kinder):
                if kind.is_named:
                    stapel.append((kind, neue, None))

    def _lambda(self, knoten: Node, umg: _Umgebung) -> _Umgebung:
        bereich: dict[str, tuple[str, str | None]] = {}
        parameter = next((k for k in knoten.named_children if k.type == "lambda_parameters"), None)
        if parameter is None:
            bereich["it"] = ("lokal", None)
        else:
            for kind in parameter.named_children:
                if kind.type == "variable_declaration" and kind.named_children:
                    bereich[text(kind.named_children[0])] = (
                        "lokal",
                        _deklarierter_typ(kind, umg),
                    )
                elif kind.type == "multi_variable_declaration":
                    for v in kind.named_children:
                        if v.named_children:
                            bereich[text(v.named_children[0])] = ("lokal", None)
        neue = umg
        rahmen = self._lambda_rahmen(knoten, umg)
        if rahmen is not None:
            neue = neue.mit_rahmen(rahmen)
        return neue.mit_bereich(bereich)

    def _lambda_rahmen(self, knoten: Node, umg: _Umgebung) -> Rahmen | None:
        """Rahmen für ein Lambda, das Argument eines Aufrufs ist."""
        eltern = knoten.parent
        if eltern is None:
            return None
        if eltern.type == "annotated_lambda":
            aufruf = eltern.parent
        elif eltern.type == "value_argument":
            aufruf = eltern.parent.parent if eltern.parent is not None else None
        else:
            return None
        if aufruf is None or aufruf.type != "call_expression":
            return None
        kopf = aufruf.named_children[0]
        argumente_with: Node | None = None
        if kopf.type == "call_expression" and eltern.type == "annotated_lambda":
            # ``f(x) { }``: das Lambda gehört zum inneren Aufruf
            argumente_with = next(
                (k for k in kopf.named_children if k.type == "value_arguments"), None
            )
            kopf = kopf.named_children[0]
        empfaenger_knoten: Node | None = None
        if kopf.type == "identifier":
            name = text(kopf)
        elif kopf.type == "navigation_expression" and kopf.children[-1].type == "identifier":
            name = text(kopf.children[-1])
            empfaenger_knoten = kopf.children[0]
        else:
            return None
        if name in LAMBDA_OHNE_EMPFAENGER:
            return None
        if name in BEREICH_EXTERN:
            return Rahmen("bereich")
        if name in BEREICH_MIT_EMPFAENGER:
            if name == "with":
                if argumente_with is None:
                    argumente = next(
                        (k for k in aufruf.named_children if k.type == "value_arguments"), None
                    )
                else:
                    argumente = argumente_with
                erstes = None
                if argumente is not None:
                    werte = [k for k in argumente.named_children if k.type == "value_argument"]
                    if werte and werte[0].named_children:
                        erstes = werte[0].named_children[0]
                ziel = (
                    self._empfaenger(erstes, umg) if erstes is not None else Empfaenger("unbekannt")
                )
                return Rahmen("bereich", empfaenger=ziel)
            if empfaenger_knoten is not None:
                return Rahmen("bereich", empfaenger=self._empfaenger(empfaenger_knoten, umg))
            if name == "run":
                return None  # ``run { }`` ohne Empfänger
            return Rahmen("bereich", empfaenger=Empfaenger("unbekannt"))
        return Rahmen("lambda", wert=name)

    def _argumente(self, knoten: Node) -> tuple[Node, int]:
        """Kopf und Zahl der Argumente eines Aufrufs; ein nachgestelltes Lambda zählt mit."""
        kopf = knoten.named_children[0]
        anzahl = 0
        for kind in knoten.named_children[1:]:
            if kind.type == "value_arguments":
                anzahl += sum(1 for k in kind.named_children if k.type == "value_argument")
            elif kind.type == "annotated_lambda":
                anzahl += 1
        return kopf, anzahl

    def _aufruf(self, knoten: Node, umg: _Umgebung) -> None:
        kopf, anzahl = self._argumente(knoten)
        if kopf.type == "call_expression":
            if all(k.type == "annotated_lambda" for k in knoten.named_children[1:]):
                return  # ``f(x) { }``: der innere Aufruf zählt mit dem Lambda
            return  # Aufruf eines Ergebnisses ``f()()``: kein Funktionsname
        if knoten.parent is not None and knoten.parent.type == "call_expression":
            eltern = knoten.parent
            if eltern.named_children[0] == knoten and all(
                k.type == "annotated_lambda" for k in eltern.named_children[1:]
            ):
                anzahl += len(eltern.named_children) - 1
        if kopf.type == "identifier":
            name = text(kopf)
            lokal = umg.suche(name)
            wert = lokal is not None and lokal[0] in {"lokal", "parameter"}
            lokale_funktion = lokal is not None and lokal[0] == "funktion"
            self.aufrufe.append(
                Aufruf(
                    zeile(kopf),
                    name,
                    anzahl,
                    Empfaenger("ohne"),
                    umg.rahmen,
                    wert=wert,
                    lokal=lokale_funktion,
                )
            )
            return
        if kopf.type == "navigation_expression":
            kinder = kopf.children
            if len(kinder) != 3 or kinder[2].type != "identifier" or kinder[1].type == "::":
                return
            empfaenger = self._empfaenger(kinder[0], umg)
            self.aufrufe.append(
                Aufruf(zeile(kinder[2]), text(kinder[2]), anzahl, empfaenger, umg.rahmen)
            )

    def _referenz(self, knoten: Node, umg: _Umgebung, links: Node | None) -> None:
        name_knoten = knoten.children[-1]
        if name_knoten.type != "identifier":
            return
        name = text(name_knoten)
        if links is None:
            lokal = umg.suche(name)
            self.aufrufe.append(
                Aufruf(
                    zeile(name_knoten),
                    name,
                    None,
                    Empfaenger("ohne"),
                    umg.rahmen,
                    wert=lokal is not None and lokal[0] in {"lokal", "parameter"},
                    lokal=lokal is not None and lokal[0] == "funktion",
                    referenz=True,
                )
            )
            return
        empfaenger = self._empfaenger(links, umg)
        self.aufrufe.append(
            Aufruf(zeile(name_knoten), name, None, empfaenger, umg.rahmen, referenz=True)
        )


# ---------------------------------------------------------------- Deklarationen


class _Leser:
    def __init__(self, ergebnis: FunktionenDatei) -> None:
        self.ergebnis = ergebnis

    def _rahmen_der_kette(self, ketten: list[str]) -> tuple[Rahmen, ...]:
        """Klassenrahmen von innen nach außen."""
        return tuple(Rahmen("klasse", wert=k) for k in reversed(ketten))

    def _funktion(
        self,
        knoten: Node,
        behaelter: str,
        ketten: list[str],
        typparameter: dict[str, str | None],
        vorab: list[AnnotationRoh] | None = None,
    ) -> None:
        name = _name(knoten)
        if name is None:
            return
        sichtbarkeit, modifikatoren, annotationen = _modifikatoren(knoten)
        annotationen = [*(vorab or []), *annotationen]
        parameter = _funktionsparameter(knoten)
        erweiterung = _empfaenger_typ(knoten)
        tp = {**typparameter, **_typparameter(knoten)}
        rahmen = self._rahmen_der_kette(ketten)
        if erweiterung is not None:
            rahmen = (Rahmen("erweiterung", wert=erweiterung), *rahmen)
        umgebung = _Umgebung(
            ({p.name: ("parameter", _Umgebung((), (), tp).typ(p.typ)) for p in parameter},),
            rahmen,
            tp,
        )
        sammler = _Sammler()
        koerper = [k for k in knoten.named_children if k.type == "function_body"]
        standard = [
            k
            for liste in knoten.named_children
            if liste.type == "function_value_parameters"
            for k in liste.named_children
            if k.type not in {"parameter", "parameter_modifiers"}
        ]
        sammler.lauf([*standard, *koerper], umgebung)
        self.ergebnis.funktionen.append(
            FunktionRoh(
                behaelter=behaelter,
                name=name,
                erweiterung=erweiterung,
                parameter=parameter,
                zeile_von=zeile(knoten),
                zeile_bis=knoten.end_point[0] + 1,
                sichtbarkeit=sichtbarkeit,
                modifikatoren=modifikatoren,
                annotationen=annotationen,
                hash=_hash(text(knoten)),
                zeilen=_codezeilen([knoten]),
                komplexitaet=_komplexitaet([knoten]),
                aufrufe=sammler.aufrufe,
                klasse=ketten[-1] if ketten else "",
            )
        )

    def _accessoren(
        self,
        knoten: Node,
        behaelter: str,
        ketten: list[str],
        typparameter: dict[str, str | None],
    ) -> None:
        variable = next(
            (k for k in knoten.named_children if k.type == "variable_declaration"), None
        )
        if variable is None or not variable.named_children:
            return
        feld = text(variable.named_children[0])
        erweiterung = _empfaenger_typ(knoten)
        tp = {**typparameter, **_typparameter(knoten)}
        for kind in knoten.named_children:
            if kind.type not in {"getter", "setter"}:
                continue
            koerper = [k for k in kind.named_children if k.type == "function_body"]
            if not koerper:
                continue
            setter = kind.type == "setter"
            parameter: list[Parameter] = []
            if setter:
                wert = next((k for k in kind.named_children if k.type == "identifier"), None)
                parameter = [Parameter(text(wert) if wert else "value", None, False, False)]
            sichtbarkeit, modifikatoren, annotationen = _modifikatoren(knoten)
            eigene = _modifikatoren(kind)
            if eigene[0] != "public":
                sichtbarkeit = eigene[0]
            rahmen = self._rahmen_der_kette(ketten)
            if erweiterung is not None:
                rahmen = (Rahmen("erweiterung", wert=erweiterung), *rahmen)
            umgebung = _Umgebung(({p.name: ("parameter", None) for p in parameter},), rahmen, tp)
            sammler = _Sammler()
            sammler.lauf(koerper, umgebung)
            self.ergebnis.funktionen.append(
                FunktionRoh(
                    behaelter=behaelter,
                    name=f"<{'set' if setter else 'get'}-{feld}>",
                    erweiterung=erweiterung,
                    parameter=parameter,
                    zeile_von=zeile(kind),
                    zeile_bis=kind.end_point[0] + 1,
                    sichtbarkeit=sichtbarkeit,
                    modifikatoren=sorted(set(modifikatoren) | set(eigene[1])),
                    annotationen=annotationen + eigene[2],
                    hash=_hash(text(kind)),
                    zeilen=_codezeilen([kind]),
                    komplexitaet=_komplexitaet([kind]),
                    aufrufe=sammler.aufrufe,
                    klasse=ketten[-1] if ketten else "",
                )
            )

    def _klasse(
        self,
        knoten: Node,
        kette: str,
        art: str,
        ketten: list[str],
        typparameter: dict[str, str | None],
        vorab: list[AnnotationRoh] | None = None,
    ) -> None:
        sichtbarkeit, modifikatoren, annotationen = _modifikatoren(knoten)
        annotationen = [*(vorab or []), *annotationen]
        tp = {**typparameter, **_typparameter(knoten)}
        primaer = _klassenparameter(knoten) if art not in {"objekt", "companion"} else []
        if art == "schnittstelle" or art == "annotation":
            primaer = None
        if art in {"objekt", "companion", "enum-eintrag"}:
            primaer = []
        eigenschaften: dict[str, str | None] = {}
        for p in primaer or []:
            eigenschaften[p.name] = p.typ  # nur ``val``/``var`` sind Eigenschaften; Näherung
        klasse = KlasseRoh(
            name=kette,
            art=art,
            zeile=zeile(knoten),
            annotationen=annotationen,
            obertypen=_obertypen(knoten),
            eigenschaften=eigenschaften,
            typparameter=tp,
            primaer=primaer,
            modifikatoren=sorted(set(modifikatoren) | {sichtbarkeit}),
        )
        self.ergebnis.klassen.append(klasse)
        neue_ketten = [*ketten, kette]
        koerper = _koerper(knoten)
        # Teile des primären Konstruktors: init-Blöcke und Initialisierer der Eigenschaften
        init_teile: list[Node] = []
        if koerper is not None:
            for kind in koerper.named_children:
                if kind.type == "anonymous_initializer":
                    init_teile.append(kind)
                elif kind.type == "property_declaration":
                    variable = next(
                        (k for k in kind.named_children if k.type == "variable_declaration"), None
                    )
                    initial = _initialisierer(kind)
                    if variable is not None and variable.named_children:
                        name = text(variable.named_children[0])
                        typ = _typ_nach(variable, 1) or _konstruktor_typ(initial)
                        if _empfaenger_typ(kind) is None:
                            klasse.eigenschaften[name] = typ
                    if initial is not None:
                        init_teile.append(initial)
                    delegat = next(
                        (k for k in kind.named_children if k.type == "property_delegate"), None
                    )
                    if delegat is not None:
                        init_teile.append(delegat)
            self._sammle(koerper, neue_ketten, tp)
        # Parameter mit Vorgabe im primären Konstruktor
        primaer_knoten = next(
            (k for k in knoten.named_children if k.type == "primary_constructor"), None
        )
        vorgaben: list[Node] = []
        if primaer_knoten is not None:
            for k in primaer_knoten.named_children:
                if k.type == "class_parameters":
                    for p in k.named_children:
                        gesehen = False
                        for t in p.children:
                            if gesehen and t.is_named:
                                vorgaben.append(t)
                            if t.type == "=":
                                gesehen = True
        sammler = _Sammler()
        umgebung = _Umgebung(
            ({p.name: ("parameter", p.typ) for p in primaer or []},),
            self._rahmen_der_kette(neue_ketten),
            tp,
        )
        sammler.lauf(init_teile, umgebung)
        if sammler.aufrufe and art != "schnittstelle":
            # Aufruf des Oberklassen-Konstruktors gehört dazu
            obersammler = _Sammler()
            obersammler.lauf(
                [
                    k
                    for spez in knoten.named_children
                    if spez.type == "delegation_specifiers"
                    for k in spez.named_children
                ]
                + vorgaben,
                umgebung,
            )
            aufrufe = obersammler.aufrufe + sammler.aufrufe
            for spez in knoten.named_children:
                if spez.type != "delegation_specifiers":
                    continue
                for s in spez.named_children:
                    aufruf = next(
                        (k for k in s.named_children if k.type == "constructor_invocation"), None
                    )
                    if aufruf is None:
                        continue
                    typ = next((k for k in aufruf.named_children if k.type == "user_type"), None)
                    argumente = next(
                        (k for k in aufruf.named_children if k.type == "value_arguments"), None
                    )
                    if typ is None:
                        continue
                    teile = (typ_basis(text(typ)) or "").split(".")
                    anzahl = (
                        sum(1 for a in argumente.named_children if a.type == "value_argument")
                        if argumente is not None
                        else 0
                    )
                    empf = (
                        Empfaenger("ohne")
                        if len(teile) == 1
                        else Empfaenger("kette", teile[0], tuple(teile[1:-1]), "frei")
                    )
                    aufrufe.append(Aufruf(zeile(aufruf), teile[-1], anzahl, empf, umgebung.rahmen))
            klasse.konstruktor_knoten = True
            teile_alle = [*([primaer_knoten] if primaer_knoten is not None else []), *init_teile]
            self.ergebnis.funktionen.append(
                FunktionRoh(
                    behaelter=kette,
                    name="<init>",
                    erweiterung=None,
                    parameter=list(primaer or []),
                    zeile_von=zeile(knoten),
                    zeile_bis=max(k.end_point[0] + 1 for k in teile_alle),
                    sichtbarkeit=(
                        _modifikatoren(primaer_knoten)[0]
                        if primaer_knoten is not None
                        else "public"
                    ),
                    modifikatoren=[],
                    annotationen=[],
                    hash=_hash(*(text(k) for k in teile_alle)),
                    zeilen=_codezeilen(teile_alle),
                    komplexitaet=_komplexitaet(init_teile),
                    aufrufe=sorted(aufrufe, key=lambda a: (a.zeile, a.name)),
                    klasse=kette,
                )
            )

    def _sekundaer(
        self, knoten: Node, kette: str, ketten: list[str], typparameter: dict[str, str | None]
    ) -> None:
        sichtbarkeit, modifikatoren, annotationen = _modifikatoren(knoten)
        parameter = _funktionsparameter(knoten)
        umgebung = _Umgebung(
            ({p.name: ("parameter", p.typ) for p in parameter},),
            self._rahmen_der_kette(ketten),
            typparameter,
        )
        sammler = _Sammler()
        teile = [
            k for k in knoten.named_children if k.type in {"block", "constructor_delegation_call"}
        ]
        sammler.lauf(teile, umgebung)
        for teil in teile:
            if teil.type != "constructor_delegation_call":
                continue
            argumente = next((k for k in teil.named_children if k.type == "value_arguments"), None)
            anzahl = (
                sum(1 for a in argumente.named_children if a.type == "value_argument")
                if argumente is not None
                else 0
            )
            ziel = "this" if any(k.type == "this" for k in teil.children) else "super"
            sammler.aufrufe.append(
                Aufruf(
                    zeile(teil),
                    "<init>",
                    anzahl,
                    Empfaenger(ziel),
                    umgebung.rahmen,
                )
            )
        self.ergebnis.funktionen.append(
            FunktionRoh(
                behaelter=kette,
                name="<init>",
                erweiterung=None,
                parameter=parameter,
                zeile_von=zeile(knoten),
                zeile_bis=knoten.end_point[0] + 1,
                sichtbarkeit=sichtbarkeit,
                modifikatoren=modifikatoren,
                annotationen=annotationen,
                hash=_hash(text(knoten)),
                zeilen=_codezeilen([knoten]),
                komplexitaet=_komplexitaet([knoten]),
                aufrufe=sorted(sammler.aufrufe, key=lambda a: (a.zeile, a.name)),
                klasse=kette,
            )
        )

    def _sammle(self, container: Node, ketten: list[str], typparameter: dict[str, str | None]):
        praefix = f"{ketten[-1]}." if ketten else ""
        behaelter = ketten[-1] if ketten else ""
        # Annotationen auf eigener Zeile, die die Grammatik als eigenen Knoten liest
        # (``@A("x")`` nach einer Ausdrucksfunktion): gehören zur nächsten Deklaration.
        vorab: list[AnnotationRoh] = []
        for kind in container.named_children:
            typ = kind.type
            if typ in {"annotated_expression", "annotation"}:
                for teil in [kind, *kind.named_children]:
                    if teil.type == "annotation" and (name := _annotationsname(teil)):
                        vorab.append(AnnotationRoh(name, zeile(teil)))
                continue
            if typ in _KOMMENTARE:
                continue
            mitgegeben, vorab = vorab, []
            if typ in {"class_declaration", "object_declaration"}:
                name = _name(kind)
                if name is None:
                    continue
                self._klasse(
                    kind, f"{praefix}{name}", _klassenart(kind), ketten, typparameter, mitgegeben
                )
            elif typ == "companion_object":
                name = _name(kind) or "Companion"
                kette = f"{praefix}{name}"
                self._klasse(kind, kette, "companion", ketten, typparameter)
                for k in self.ergebnis.klassen:
                    if k.name == behaelter:
                        k.companion = kette
            elif typ == "enum_entry":
                koerper = _koerper(kind)
                name = next((k for k in kind.named_children if k.type == "identifier"), None)
                if koerper is None or name is None:
                    continue
                kette = f"{praefix}{text(name)}"
                self.ergebnis.klassen.append(
                    KlasseRoh(
                        name=kette,
                        art="enum-eintrag",
                        zeile=zeile(kind),
                        annotationen=_modifikatoren(kind)[2],
                        obertypen=[behaelter.rsplit(".", 1)[-1]] if behaelter else [],
                        eigenschaften={},
                        typparameter={},
                        primaer=[],
                        modifikatoren=[],
                    )
                )
                self._sammle(koerper, [*ketten, kette], typparameter)
            elif typ == "function_declaration":
                self._funktion(kind, behaelter, ketten, typparameter, mitgegeben)
            elif typ == "secondary_constructor":
                self._sekundaer(kind, behaelter, ketten, typparameter)
            elif typ == "property_declaration":
                if not ketten:
                    variable = next(
                        (k for k in kind.named_children if k.type == "variable_declaration"), None
                    )
                    if (
                        variable is not None
                        and variable.named_children
                        and _empfaenger_typ(kind) is None
                    ):
                        self.ergebnis.eigenschaften[text(variable.named_children[0])] = _typ_nach(
                            variable, 1
                        ) or _konstruktor_typ(_initialisierer(kind))
                self._accessoren(kind, behaelter, ketten, typparameter)
            elif typ == "type_alias" and not ketten:
                name = kind.child_by_field_name("type")
                if name is not None:
                    self.ergebnis.typaliase.add(text(name))


def lies_funktionen(quelle: bytes) -> FunktionenDatei:
    """Liest Funktionen, Klassen, Annotationen und rohe Aufrufe einer ``.kt``-Datei."""
    wurzel = parse("kotlin", quelle)
    ergebnis = FunktionenDatei()
    for kind in wurzel.named_children:
        if kind.type == "file_annotation":
            for teil in kind.named_children:
                if teil.type in {"user_type", "constructor_invocation"}:
                    typ = (
                        teil
                        if teil.type == "user_type"
                        else next((k for k in teil.named_children if k.type == "user_type"), None)
                    )
                    if typ is not None and (name := typ_basis(text(typ))):
                        ergebnis.datei_annotationen.append(AnnotationRoh(name, zeile(teil)))
    _Leser(ergebnis)._sammle(wurzel, [], {})
    return ergebnis
