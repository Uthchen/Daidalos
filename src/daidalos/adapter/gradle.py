"""Gradle-Adapter: Module aus ``settings.gradle.kts``, Abhängigkeiten aus den Build-Skripten.

Die ``.kts``-Dateien sind Kotlin und werden mit tree-sitter-kotlin gelesen, damit Verschachtelung
und Bedingungen sichtbar sind. Groovy-Dateien werden nur grob über Textmuster ausgewertet.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from tree_sitter import Node

from daidalos.adapter.baum import alle, parse, string_wert, text, zeile

SETTINGS_KTS = "settings.gradle.kts"
SETTINGS_GROOVY = "settings.gradle"
BUILD_KTS = "build.gradle.kts"
BUILD_GROOVY = "build.gradle"

# Aufrufe, die ein ``project(...)`` umhüllen, ohne selbst die Konfiguration zu sein.
_HUELLEN = frozenset({"platform", "enforcedPlatform", "testFixtures"})
# Aufrufe mit ``project(...)``, die keine Code-Abhängigkeit sind.
_KEINE_ABHAENGIGKEIT = frozenset(
    {"dependsOn", "evaluationDependsOn", "mustRunAfter", "finalizedBy", "shouldRunAfter", "project"}
)
# Blöcke, die eine Abhängigkeit nicht bedingt machen.
_NEUTRALE_BLOECKE = frozenset(
    {
        "dependencies",
        "sourceSets",
        "kotlin",
        "android",
        "subprojects",
        "allprojects",
        "configure",
        "withType",
        "getting",
        "creating",
        "getByName",
        "named",
        "maybeCreate",
    }
)
_WURZEL_BLOECKE = frozenset({"subprojects", "allprojects"})

Warner = Callable[[str], None]


@dataclass(frozen=True)
class GradleModul:
    gradle_pfad: str  # ":core"
    pfad: str  # "core", relativ zum Zielrepo
    plugins: tuple[str, ...] = ()


@dataclass(frozen=True)
class GradleAbhaengigkeit:
    von: str  # Gradle-Pfad
    nach: str
    art: str  # gradle-api, gradle-impl, …
    beleg: dict[str, Any]


@dataclass
class GradleErgebnis:
    module: list[GradleModul] = field(default_factory=list)
    abhaengigkeiten: list[GradleAbhaengigkeit] = field(default_factory=list)


# ---------------------------------------------------------------- Hilfen


def normiere_gradle_pfad(roh: str) -> str:
    """``core`` und ``:core`` sind dasselbe Projekt."""
    return ":" + roh.strip().lstrip(":")


def ordner_aus_gradle_pfad(gradle_pfad: str) -> str:
    """``:a:b`` → ``a/b``."""
    return "/".join(teil for teil in gradle_pfad.split(":") if teil)


def art_fuer(konfiguration: str, quellsatz: str | None) -> str:
    """Kantenart aus Konfiguration und Quellsatz."""
    if "test" in konfiguration or "Test" in konfiguration:
        return "gradle-test"
    if quellsatz is not None and ("test" in quellsatz or "Test" in quellsatz):
        return "gradle-test"
    if konfiguration == "api":
        return "gradle-api"
    if konfiguration == "implementation":
        return "gradle-impl"
    if konfiguration == "compileOnly":
        return "gradle-compileonly"
    if konfiguration == "detektPlugins":
        return "gradle-plugin"
    return "gradle-sonstige"


def _aufruf_name(aufruf: Node) -> str | None:
    """Name des aufgerufenen Bezeichners, z. B. ``implementation`` oder ``add``."""
    if aufruf.type != "call_expression" or not aufruf.named_children:
        return None
    ziel = aufruf.named_children[0]
    if ziel.type == "identifier":
        return text(ziel)
    if ziel.type == "navigation_expression" and ziel.named_children:
        letztes = ziel.named_children[-1]
        if letztes.type == "identifier":
            return text(letztes)
    return None


def _argumente(aufruf: Node) -> list[Node]:
    for kind in aufruf.named_children:
        if kind.type == "value_arguments":
            return [a for a in kind.named_children if a.type == "value_argument"]
    return []


def _projekt_argument(aufruf: Node) -> str | None:
    """Gradle-Pfad aus ``project(":x")``, sonst ``None``."""
    if aufruf.type != "call_expression" or _aufruf_name(aufruf) != "project":
        return None
    if aufruf.named_children[0].type != "identifier":
        return None
    argumente = _argumente(aufruf)
    if len(argumente) != 1:
        return None
    wert = string_wert(argumente[0])
    return normiere_gradle_pfad(wert) if wert else None


def _umgebender_aufruf(knoten: Node) -> Node | None:
    """Aufruf, in dessen Argumentliste ``knoten`` steht."""
    eltern = knoten.parent
    if eltern is None or eltern.type != "value_argument":
        return None
    liste = eltern.parent
    if liste is None or liste.type != "value_arguments":
        return None
    aufruf = liste.parent
    return aufruf if aufruf is not None and aufruf.type == "call_expression" else None


@dataclass(frozen=True)
class _Block:
    """Ein Lambda-Block um einen Aufruf, von innen nach außen."""

    name: str | None  # Name des Besitzers, z. B. ``dependencies`` oder ``sourceSets``
    empfaenger: str | None  # bei ``commonMain.dependencies { }`` ``commonMain``
    delegiert_an: str | None  # bei ``val jvmTest by getting { }`` ``jvmTest``


def _besitzer_des_lambdas(lambda_knoten: Node) -> _Block:
    eltern = lambda_knoten.parent
    if eltern is not None and eltern.type == "annotated_lambda":
        aufruf = eltern.parent
        if aufruf is not None and aufruf.type == "call_expression":
            ziel = aufruf.named_children[0]
            empfaenger = None
            if ziel.type == "navigation_expression":
                kinder = ziel.named_children
                if len(kinder) == 2 and kinder[0].type == "identifier":
                    empfaenger = text(kinder[0])
            delegiert = None
            if _aufruf_name(aufruf) in {"getting", "creating"}:
                delegat = aufruf.parent
                deklaration = delegat.parent if delegat is not None else None
                if (
                    delegat is not None
                    and delegat.type == "property_delegate"
                    and deklaration is not None
                ):
                    variable = next(
                        (k for k in deklaration.named_children if k.type == "variable_declaration"),
                        None,
                    )
                    if variable is not None:
                        delegiert = text(variable).split(":")[0].strip()
            if _aufruf_name(aufruf) in {"getByName", "named", "maybeCreate"}:
                argumente = _argumente(aufruf)
                if argumente:
                    delegiert = string_wert(argumente[0])
            return _Block(_aufruf_name(aufruf), empfaenger, delegiert)
    # ``plugins.withType<X> { }`` liest tree-sitter als Vergleich mit einem Lambda rechts.
    if eltern is not None and eltern.type == "binary_expression" and "withType" in text(eltern):
        return _Block("withType", None, None)
    return _Block(None, None, None)


@dataclass(frozen=True)
class _Umgebung:
    quellsatz: str | None
    bedingt: bool
    wurzelweit: bool  # in subprojects { } oder allprojects { }


def _umgebung(aufruf: Node) -> _Umgebung:
    bloecke: list[_Block] = []
    bedingt = False
    knoten = aufruf.parent
    while knoten is not None:
        if knoten.type in {"if_expression", "when_expression", "when_entry"}:
            bedingt = True
        elif knoten.type == "lambda_literal":
            bloecke.append(_besitzer_des_lambdas(knoten))
        knoten = knoten.parent

    quellsatz: str | None = None
    for index, block in enumerate(bloecke):
        aussen = bloecke[index + 1] if index + 1 < len(bloecke) else None
        in_quellsaetzen = aussen is not None and aussen.name == "sourceSets"
        neutral = block.name in _NEUTRALE_BLOECKE or (block.name is not None and in_quellsaetzen)
        if not neutral:
            bedingt = True
        if quellsatz is None:
            if block.name == "dependencies" and block.empfaenger:
                quellsatz = block.empfaenger  # commonMain.dependencies { }
            elif block.delegiert_an:
                quellsatz = block.delegiert_an  # val jvmTest by getting { }
            elif in_quellsaetzen and block.name not in _NEUTRALE_BLOECKE:
                quellsatz = block.name  # sourceSets { commonMain { dependencies { } } }
    wurzelweit = any(block.name in _WURZEL_BLOECKE for block in bloecke)
    return _Umgebung(quellsatz, bedingt, wurzelweit)


# ---------------------------------------------------------------- settings.gradle(.kts)


@dataclass
class _Settings:
    module: dict[str, str]  # Gradle-Pfad → Ordner
    groovy: bool


def lies_settings_kts(quelle: bytes, warne: Warner) -> dict[str, str]:
    """Module aus ``include(...)`` und einfachen ``projectDir``-Zuweisungen."""
    wurzel = parse("kotlin", quelle)
    module: dict[str, str] = {}
    umgebogen: list[tuple[str, str]] = []
    for knoten in alle(wurzel):
        if knoten.type == "call_expression" and _aufruf_name(knoten) == "include":
            if knoten.named_children[0].type != "identifier":
                continue
            for argument in _argumente(knoten):
                wert = string_wert(argument)
                if wert is None:
                    warne(
                        f"{SETTINGS_KTS}:{zeile(argument)}: include mit nicht einfachem "
                        f"Argument {text(argument)!r} wird übergangen"
                    )
                    continue
                gradle_pfad = normiere_gradle_pfad(wert)
                module[gradle_pfad] = ordner_aus_gradle_pfad(gradle_pfad)
        elif knoten.type == "assignment":
            links = knoten.child_by_field_name("left")
            rechts = knoten.child_by_field_name("right")
            if links is None or rechts is None or links.type != "navigation_expression":
                continue
            kinder = links.named_children
            if len(kinder) != 2 or text(kinder[1]) != "projectDir":
                continue
            gradle_pfad = _projekt_argument(kinder[0])
            if gradle_pfad is None:
                continue
            ordner = None
            if rechts.type == "call_expression" and _aufruf_name(rechts) == "file":
                argumente = _argumente(rechts)
                if len(argumente) == 1:
                    ordner = string_wert(argumente[0])
            if ordner is None:
                warne(
                    f"{SETTINGS_KTS}:{zeile(knoten)}: projectDir von {gradle_pfad} ist kein "
                    'einfaches file("…") und wird nicht angewendet'
                )
                continue
            umgebogen.append((gradle_pfad, ordner))
    for gradle_pfad, ordner in umgebogen:
        if gradle_pfad in module:
            normiert = PurePosixPath(ordner.replace("\\", "/")).as_posix().strip("/")
            module[gradle_pfad] = normiert.removeprefix("./")
    return module


_GROOVY_INCLUDE = re.compile(r"^\s*include\b(.*)$")
_GROOVY_STRING = re.compile(r"""['"]([^'"]+)['"]""")


def lies_settings_groovy(quelle: str) -> dict[str, str]:
    """Grobe Textauswertung der ``include``-Zeilen."""
    module: dict[str, str] = {}
    for zeilentext in quelle.splitlines():
        treffer = _GROOVY_INCLUDE.match(zeilentext)
        if not treffer:
            continue
        for wert in _GROOVY_STRING.findall(treffer.group(1)):
            gradle_pfad = normiere_gradle_pfad(wert)
            module[gradle_pfad] = ordner_aus_gradle_pfad(gradle_pfad)
    return module


# ---------------------------------------------------------------- build.gradle(.kts)


def _plugin_name(aufruf: Node) -> str | None:
    name = _aufruf_name(aufruf)
    if aufruf.named_children[0].type != "identifier":
        return None
    argumente = _argumente(aufruf)
    if len(argumente) != 1:
        return None
    if name == "id":
        return string_wert(argumente[0])
    if name == "kotlin":
        wert = string_wert(argumente[0])
        return f"org.jetbrains.kotlin.{wert}" if wert else None
    if name == "alias":
        roh = text(argumente[0]).strip()
        return roh.removeprefix("libs.plugins.")
    return None


def lies_plugins(wurzel: Node) -> tuple[str, ...]:
    """Plugins aus dem obersten ``plugins { }``-Block, roh und sortiert."""
    plugins: set[str] = set()
    for block in wurzel.named_children:
        if block.type != "call_expression" or _aufruf_name(block) != "plugins":
            continue
        for knoten in alle(block):
            if knoten is block or knoten.type != "call_expression":
                continue
            name = _plugin_name(knoten)
            if name:
                plugins.add(name)
        # Bezeichner in Backticks, z. B. `java-library`
        for knoten in alle(block):
            if knoten.type == "identifier" and text(knoten).startswith("`"):
                eltern = knoten.parent
                if eltern is not None and eltern.type in {"lambda_literal", "statements"}:
                    plugins.add(text(knoten).strip("`"))
    return tuple(sorted(plugins))


@dataclass(frozen=True)
class ProjektAufruf:
    """Ein gefundenes ``<konfiguration>(project(":x"))``."""

    nach: str
    konfiguration: str
    zeile: int
    quellsatz: str | None
    bedingt: bool
    wurzelweit: bool


def finde_projekt_aufrufe(wurzel: Node) -> list[ProjektAufruf]:
    """Alle ``<konfiguration>(project(":x"))`` und ``dependencies.add("k", project(":x"))``."""
    gefunden: list[ProjektAufruf] = []
    for knoten in alle(wurzel):
        nach = _projekt_argument(knoten)
        if nach is None:
            continue
        aufruf = _umgebender_aufruf(knoten)
        while aufruf is not None and _aufruf_name(aufruf) in _HUELLEN:
            aufruf = _umgebender_aufruf(aufruf)
        if aufruf is None:
            continue
        name = _aufruf_name(aufruf)
        if name is None or name in _KEINE_ABHAENGIGKEIT:
            continue
        if name == "add" and aufruf.named_children[0].type == "navigation_expression":
            argumente = _argumente(aufruf)
            konfiguration = string_wert(argumente[0]) if argumente else None
            if konfiguration is None:
                continue
        elif aufruf.named_children[0].type == "identifier":
            konfiguration = name
        else:
            continue
        umgebung = _umgebung(aufruf)
        gefunden.append(
            ProjektAufruf(
                nach=nach,
                konfiguration=konfiguration,
                zeile=zeile(aufruf),
                quellsatz=umgebung.quellsatz,
                bedingt=umgebung.bedingt,
                wurzelweit=umgebung.wurzelweit,
            )
        )
    return gefunden


_GROOVY_PROJEKT = re.compile(r"""\b(\w+)\s*\(?\s*project\s*\(\s*(?:path\s*:\s*)?['"]([^'"]+)['"]""")


def finde_projekt_aufrufe_groovy(quelle: str) -> list[ProjektAufruf]:
    gefunden: list[ProjektAufruf] = []
    for nummer, zeilentext in enumerate(quelle.splitlines(), start=1):
        for treffer in _GROOVY_PROJEKT.finditer(zeilentext):
            konfiguration = treffer.group(1)
            if konfiguration in _KEINE_ABHAENGIGKEIT or konfiguration in _HUELLEN:
                continue
            gefunden.append(
                ProjektAufruf(
                    nach=normiere_gradle_pfad(treffer.group(2)),
                    konfiguration=konfiguration,
                    zeile=nummer,
                    quellsatz=None,
                    bedingt=False,
                    wurzelweit=False,
                )
            )
    return gefunden


# ---------------------------------------------------------------- Gesamtlauf


def _lies(ziel: Path, pfad: str) -> bytes | None:
    try:
        return (ziel / pfad).read_bytes()
    except OSError:
        return None


def _beleg(datei: str, aufruf: ProjektAufruf, wurzel: bool) -> dict[str, Any]:
    beleg: dict[str, Any] = {
        "bedingt": aufruf.bedingt,
        "datei": datei,
        "konfiguration": aufruf.konfiguration,
        "quellsatz": aufruf.quellsatz,
        "zeile": aufruf.zeile,
    }
    if wurzel:
        beleg["quelle"] = "wurzel"
    return beleg


def lies_gradle(ziel: Path, erfasst: set[str], warne: Warner) -> GradleErgebnis:
    """Liest Module und Projekt-Abhängigkeiten. ``erfasst`` sind die Pfade aus dem Scanner."""
    ergebnis = GradleErgebnis()
    if SETTINGS_KTS in erfasst:
        quelle = _lies(ziel, SETTINGS_KTS)
        module = lies_settings_kts(quelle, warne) if quelle is not None else {}
    elif SETTINGS_GROOVY in erfasst:
        quelle = _lies(ziel, SETTINGS_GROOVY)
        warne(f"{SETTINGS_GROOVY}: Groovy wird nur grob unterstützt (nur include-Zeilen)")
        module = lies_settings_groovy(quelle.decode("utf-8", "replace")) if quelle else {}
    else:
        return ergebnis

    aufrufe_je_modul: dict[str, tuple[str, list[ProjektAufruf]]] = {}
    plugins_je_modul: dict[str, tuple[str, ...]] = {}
    for gradle_pfad, ordner in sorted(module.items()):
        praefix = f"{ordner}/" if ordner else ""
        kts = f"{praefix}{BUILD_KTS}"
        groovy = f"{praefix}{BUILD_GROOVY}"
        if kts in erfasst and (quelle := _lies(ziel, kts)) is not None:
            wurzel = parse("kotlin", quelle)
            plugins_je_modul[gradle_pfad] = lies_plugins(wurzel)
            aufrufe_je_modul[gradle_pfad] = (kts, finde_projekt_aufrufe(wurzel))
        elif groovy in erfasst and (quelle := _lies(ziel, groovy)) is not None:
            warne(f"{groovy}: Groovy wird nur grob unterstützt")
            text_quelle = quelle.decode("utf-8", "replace")
            aufrufe_je_modul[gradle_pfad] = (groovy, finde_projekt_aufrufe_groovy(text_quelle))

    ergebnis.module = [
        GradleModul(gradle_pfad, ordner, plugins_je_modul.get(gradle_pfad, ()))
        for gradle_pfad, ordner in sorted(module.items())
    ]

    def fuege_hinzu(von: str, aufruf: ProjektAufruf, datei: str, wurzel: bool) -> None:
        if aufruf.nach not in module:
            warne(f"{datei}:{aufruf.zeile}: unbekanntes Projekt {aufruf.nach} wird übergangen")
            return
        if von == aufruf.nach:
            return
        ergebnis.abhaengigkeiten.append(
            GradleAbhaengigkeit(
                von=von,
                nach=aufruf.nach,
                art=art_fuer(aufruf.konfiguration, aufruf.quellsatz),
                beleg=_beleg(datei, aufruf, wurzel),
            )
        )

    for gradle_pfad, (datei, aufrufe) in sorted(aufrufe_je_modul.items()):
        for aufruf in aufrufe:
            fuege_hinzu(gradle_pfad, aufruf, datei, wurzel=False)

    # Wurzel-Build: Abhängigkeiten in subprojects { } / allprojects { } gelten für jedes Modul.
    if BUILD_KTS in erfasst and (quelle := _lies(ziel, BUILD_KTS)) is not None:
        for aufruf in finde_projekt_aufrufe(parse("kotlin", quelle)):
            if not aufruf.wurzelweit:
                continue
            for gradle_pfad in sorted(module):
                fuege_hinzu(gradle_pfad, aufruf, BUILD_KTS, wurzel=True)

    ergebnis.abhaengigkeiten.sort(
        key=lambda a: (a.von, a.nach, a.art, a.beleg["datei"], a.beleg["zeile"])
    )
    return ergebnis
