"""Kotlin-Adapter: Paket, Importe, Deklarationen und verwendete Namen einer ``.kt``-Datei.

Das Ergebnis ist eine Dataclass je Datei; aufgelöst wird erst im Auflöser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tree_sitter import Node

from daidalos.adapter.baum import parse, string_wert, text, zeile

_KOMMENTARE = frozenset({"line_comment", "block_comment"})
# Teile, in denen ein ``identifier`` ein deklarierter Name und keine Verwendung ist.
_DEKLARIEREND = frozenset(
    {
        "variable_declaration",
        "parameter",
        "class_parameter",
        "type_parameter",
        "enum_entry",
        "catch_block",
        "parameter_with_optional_type",
    }
)
_NICHT_VERWENDUNG = frozenset(
    {"import", "package_header", "qualified_identifier", "this_expression", "super_expression"}
)
_KLASSENARTIG = frozenset({"class_declaration", "object_declaration"})
# Knoten der obersten Ebene, die tree-sitter sicher erkennt.
_OBERSTE_EBENE_BEKANNT = frozenset(
    {
        "package_header",
        "import",
        "file_annotation",
        "class_declaration",
        "object_declaration",
        "function_declaration",
        "property_declaration",
        "type_alias",
        "line_comment",
        "block_comment",
        "shebang_line",
    }
)
# Rückfall für Stellen, die die Grammatik nicht als Deklaration liest (z. B. Annotationen auf
# eigenen Zeilen vor ``annotation class`` oder Parse-Fehler): nur Zeilen ohne Einrückung.
_RUECKFALL = re.compile(
    r"^(?:@[\w.]+(?:\([^)\n]*\))?\s+)*"
    r"(?:(?:private|internal|public|protected|data|enum|sealed|annotation|open|abstract|value"
    r"|inline|const|expect|actual|external|suspend|operator|infix|tailrec|inner)\s+)*"
    r"(?:(fun)\s+interface|(class|interface|object|fun|val|var|typealias))\s+"
    r"(?:<[^>\n]*>\s*)?(?:[\w<>?, ]+\.)?(\w+)",
    re.MULTILINE,
)
_RUECKFALL_ART = {
    "class": "klasse",
    "interface": "klasse",
    "object": "objekt",
    "fun": "funktion",
    "val": "eigenschaft",
    "var": "eigenschaft",
    "typealias": "typalias",
}


@dataclass(frozen=True)
class Import:
    name: str  # voller Name, z. B. ``de.a.Satz``
    alias: str | None
    zeile: int
    stern: bool = False  # ``import de.a.*``

    @property
    def sichtbarer_name(self) -> str:
        return self.alias or self.name.rsplit(".", 1)[-1]


@dataclass(frozen=True)
class Deklaration:
    name: str  # relativ zum Paket, z. B. ``Aussen.Innen`` oder ``Hilfen.kennung``
    art: str  # klasse, objekt, funktion, eigenschaft, typalias
    zeile: int
    oberste_ebene: bool
    erweiterung: bool = False  # Erweiterungsfunktion oder -eigenschaft ``fun Typ.name()``


@dataclass(frozen=True)
class ExternFunktion:
    klasse: str  # JVM-Name der umgebenden Klasse relativ zum Paket, z. B. ``Insel`` oder ``A$B``
    name: str
    zeile: int


@dataclass
class KotlinDatei:
    paket: str | None = None
    importe: list[Import] = field(default_factory=list)
    deklarationen: list[Deklaration] = field(default_factory=list)
    # verwendete einfache Namen mit der ersten Zeile ihres Vorkommens
    namen: dict[str, int] = field(default_factory=dict)
    # punktierte Ausdrücke wie ``de.a.b.Klasse.f`` mit erster Zeile
    qualifiziert: dict[str, int] = field(default_factory=dict)
    # Namen hinter einem Punkt (``x.name``), für Erweiterungen im gleichen Paket
    mitglieder: dict[str, int] = field(default_factory=dict)
    # alle in der Datei deklarierten Namen (auch lokal), für die Verdeckung
    lokale_namen: set[str] = field(default_factory=set)
    externe: list[ExternFunktion] = field(default_factory=list)
    jvm_name: str | None = None  # aus ``@file:JvmName("…")``


def _name_der_deklaration(knoten: Node) -> str | None:
    name = knoten.child_by_field_name("name")
    if name is None and knoten.type == "type_alias":
        name = knoten.child_by_field_name("type")
    return text(name) if name is not None else None


def _hat_modifikator(knoten: Node, wort: str) -> bool:
    for kind in knoten.named_children:
        if kind.type == "modifiers":
            return any(text(m) == wort for m in kind.named_children)
    return False


def _klassenart(knoten: Node) -> str:
    if knoten.type == "object_declaration":
        return "objekt"
    return "klasse"


def _eigenschaftsnamen(knoten: Node) -> list[str]:
    namen: list[str] = []
    for kind in knoten.named_children:
        if kind.type == "variable_declaration":
            bezeichner = kind.named_children[0] if kind.named_children else None
            if bezeichner is not None and bezeichner.type == "identifier":
                namen.append(text(bezeichner))
        elif kind.type == "multi_variable_declaration":
            for variable in kind.named_children:
                if variable.type == "variable_declaration" and variable.named_children:
                    namen.append(text(variable.named_children[0]))
    return namen


def _koerper(knoten: Node) -> Node | None:
    for kind in knoten.named_children:
        if kind.type in {"class_body", "enum_class_body"}:
            return kind
    return None


def _sammle_deklarationen(
    container: Node,
    praefix: str,
    jvm_praefix: str,
    oberste_ebene: bool,
    ist_objekt: bool,
    datei: KotlinDatei,
    datei_klasse: str,
) -> None:
    """Deklarationen der obersten Ebene und verschachtelte Klassen und Objekt-Mitglieder."""
    for kind in container.named_children:
        typ = kind.type
        if typ in _KLASSENARTIG:
            name = _name_der_deklaration(kind)
            if name is None:
                continue
            voll = f"{praefix}{name}"
            datei.deklarationen.append(
                Deklaration(voll, _klassenart(kind), zeile(kind), oberste_ebene)
            )
            koerper = _koerper(kind)
            if koerper is not None:
                _sammle_deklarationen(
                    koerper,
                    f"{voll}.",
                    f"{jvm_praefix}{name}$",
                    False,
                    typ == "object_declaration",
                    datei,
                    datei_klasse,
                )
        elif typ == "companion_object":
            koerper = _koerper(kind)
            name = _name_der_deklaration(kind) or "Companion"
            if koerper is not None:
                # Mitglieder des Companion sind über den Klassennamen erreichbar.
                _sammle_deklarationen(
                    koerper, praefix, f"{jvm_praefix}{name}$", False, True, datei, datei_klasse
                )
        elif typ == "function_declaration":
            name = _name_der_deklaration(kind)
            if name is None:
                continue
            if _hat_modifikator(kind, "external"):
                klasse = jvm_praefix.removesuffix("$") if jvm_praefix else datei_klasse
                datei.externe.append(ExternFunktion(klasse, name, zeile(kind)))
            if oberste_ebene or ist_objekt:
                datei.deklarationen.append(
                    Deklaration(
                        f"{praefix}{name}",
                        "funktion",
                        zeile(kind),
                        oberste_ebene,
                        _ist_erweiterung(kind),
                    )
                )
        elif typ == "property_declaration":
            if oberste_ebene or ist_objekt:
                for name in _eigenschaftsnamen(kind):
                    datei.deklarationen.append(
                        Deklaration(
                            f"{praefix}{name}",
                            "eigenschaft",
                            zeile(kind),
                            oberste_ebene,
                            _ist_erweiterung(kind),
                        )
                    )
        elif typ == "type_alias" and oberste_ebene:
            name = _name_der_deklaration(kind)
            if name is not None:
                datei.deklarationen.append(Deklaration(name, "typalias", zeile(kind), True))


def _ist_erweiterung(knoten: Node) -> bool:
    """``fun Typ.name()`` bzw. ``val Typ.name``: vor dem Namen steht ein Punkt."""
    for kind in knoten.children:
        if kind.type in {"identifier", "variable_declaration", "function_value_parameters"}:
            return False
        if kind.type == ".":
            return True
    return False


def _punktkette(knoten: Node) -> list[str] | None:
    """``a.b.c`` als Liste, wenn der Ausdruck nur aus Bezeichnern und Punkten besteht."""
    if knoten.type == "identifier":
        return [text(knoten)]
    if knoten.type == "navigation_expression":
        kinder = knoten.named_children
        if len(kinder) != 2 or kinder[1].type != "identifier":
            return None
        links = _punktkette(kinder[0])
        return None if links is None else [*links, text(kinder[1])]
    if knoten.type == "user_type":
        teile = [k for k in knoten.named_children if k.type == "identifier"]
        if len(teile) != len([k for k in knoten.named_children if k.type != "type_arguments"]):
            return None
        return [text(k) for k in teile]
    return None


def _ist_verwendung(knoten: Node) -> bool:
    """Ob ein ``identifier`` einen Namen verwendet (und nicht deklariert oder nur Mitglied ist)."""
    eltern = knoten.parent
    if eltern is None:
        return False
    typ = eltern.type
    if typ in _NICHT_VERWENDUNG or typ in _DEKLARIEREND:
        return False
    if typ in {"class_declaration", "object_declaration", "function_declaration", "type_alias"}:
        # Der Name selbst ist eine Deklaration; der Empfängertyp einer
        # Erweiterungsfunktion steht als ``user_type`` und nicht als ``identifier`` hier.
        return False
    if typ in {"navigation_expression", "user_type"}:
        # Nur der erste Teil einer Kette ist ein freier Name.
        return eltern.named_children[0] == knoten
    if typ == "value_argument":
        # benanntes Argument ``f(name = wert)``: der Name links ist keine Verwendung
        naechstes = knoten.next_sibling
        return not (naechstes is not None and naechstes.type == "=")
    return not (typ in {"label", "jump_expression"} and text(knoten).endswith("@"))


def _ist_deklarierter_name(knoten: Node) -> bool:
    eltern = knoten.parent
    if eltern is None:
        return False
    if eltern.type in _DEKLARIEREND:
        return eltern.named_children[0] == knoten
    if eltern.type in {"class_declaration", "object_declaration", "function_declaration"}:
        return eltern.child_by_field_name("name") == knoten
    if eltern.type == "type_alias":
        return eltern.child_by_field_name("type") == knoten
    return False


def _lies_kopf(wurzel: Node, datei: KotlinDatei) -> None:
    for kind in wurzel.named_children:
        if kind.type == "package_header":
            name = next((k for k in kind.named_children if k.type == "qualified_identifier"), None)
            if name is not None:
                datei.paket = text(name)
        elif kind.type == "import":
            name = next((k for k in kind.named_children if k.type == "qualified_identifier"), None)
            if name is None:
                continue
            alias_knoten = next((k for k in kind.named_children if k.type == "identifier"), None)
            stern = any(k.type == "*" for k in kind.children)
            datei.importe.append(
                Import(
                    name=text(name),
                    alias=text(alias_knoten) if alias_knoten is not None else None,
                    zeile=zeile(kind),
                    stern=stern,
                )
            )
        elif kind.type == "file_annotation":
            aufruf = next(
                (k for k in kind.named_children if k.type == "constructor_invocation"), None
            )
            if aufruf is None:
                continue
            typ = next((k for k in aufruf.named_children if k.type == "user_type"), None)
            argumente = next(
                (k for k in aufruf.named_children if k.type == "value_arguments"), None
            )
            if typ is not None and text(typ) == "JvmName" and argumente is not None:
                werte = [a for a in argumente.named_children if a.type == "value_argument"]
                if len(werte) == 1:
                    datei.jvm_name = string_wert(werte[0])


def _lies_namen(wurzel: Node, datei: KotlinDatei) -> None:
    stapel = [wurzel]
    while stapel:
        knoten = stapel.pop()
        typ = knoten.type
        if typ in _KOMMENTARE or typ in {"import", "package_header", "file_annotation"}:
            continue
        if typ == "string_content":
            continue
        if typ in {"navigation_expression", "user_type"} and (
            knoten.parent is None or knoten.parent.type not in {"navigation_expression"}
        ):
            kette = _punktkette(knoten)
            if kette is not None and len(kette) >= 2:
                voll = ".".join(kette)
                datei.qualifiziert.setdefault(voll, zeile(knoten))
        if typ == "identifier":
            name = text(knoten)
            if _ist_deklarierter_name(knoten):
                datei.lokale_namen.add(name)
            elif _ist_verwendung(knoten):
                datei.namen.setdefault(name, zeile(knoten))
            elif knoten.parent is not None and knoten.parent.type == "navigation_expression":
                datei.mitglieder.setdefault(name, zeile(knoten))
            continue
        stapel.extend(reversed(knoten.children))


def lies_kotlin(quelle: bytes, dateiname: str = "Datei.kt") -> KotlinDatei:
    """Liest eine ``.kt``-Datei. ``dateiname`` bestimmt die JVM-Klasse für Top-Level-Funktionen."""
    wurzel = parse("kotlin", quelle)
    datei = KotlinDatei()
    _lies_kopf(wurzel, datei)
    stamm = dateiname.rsplit("/", 1)[-1].removesuffix(".kt")
    datei_klasse = datei.jvm_name or f"{stamm[:1].upper()}{stamm[1:]}Kt"
    _sammle_deklarationen(wurzel, "", "", True, False, datei, datei_klasse)
    _lies_namen(wurzel, datei)
    _rueckfall_deklarationen(wurzel, datei)
    datei.deklarationen.sort(key=lambda d: (d.name, d.zeile))
    datei.importe.sort(key=lambda i: (i.zeile, i.name))
    datei.externe.sort(key=lambda e: (e.klasse, e.name, e.zeile))
    return datei


def _rueckfall_deklarationen(wurzel: Node, datei: KotlinDatei) -> None:
    """Deklarationen der obersten Ebene in Knoten, die die Grammatik nicht erkannt hat."""
    bekannt = {d.name for d in datei.deklarationen if d.oberste_ebene}
    for kind in wurzel.children:
        if kind.type in _OBERSTE_EBENE_BEKANNT or not kind.is_named:
            continue
        # Einrückung der ersten Zeile voranstellen, damit nur Zeilen ohne Einrückung passen.
        inhalt = " " * kind.start_point[1] + text(kind)
        for treffer in _RUECKFALL.finditer(inhalt):
            art = "klasse" if treffer.group(1) else _RUECKFALL_ART[treffer.group(2)]
            name = treffer.group(3)
            if name in bekannt:
                continue
            bekannt.add(name)
            versatz = inhalt[: treffer.start(3)].count("\n")
            datei.deklarationen.append(Deklaration(name, art, zeile(kind) + versatz, True))
            datei.lokale_namen.add(name)
            datei.namen.pop(name, None)
