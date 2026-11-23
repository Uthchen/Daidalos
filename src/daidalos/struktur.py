"""Strukturgraph: Module, Pakete, Ordner, Kanten und Befunde aus den gemessenen Dateien.

Verbindet Gradle-Adapter, Kotlin-Adapter, Auflöser, JNI und Zyklen-Analyse.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from daidalos.adapter.gradle import GradleErgebnis, lies_gradle
from daidalos.adapter.jni import CFunktion, dekodiere, finde_c_funktionen
from daidalos.adapter.kotlin import KotlinDatei, lies_kotlin
from daidalos.adapter.kotlin_funktionen import FunktionenDatei, lies_funktionen
from daidalos.analysen.zyklen import GraphKante, zyklus_befunde
from daidalos.aufloeser import PRODUKTIV, TEST, Quelldatei, loese_auf
from daidalos.aufrufgraph import CQuelle, Quelle, miss
from daidalos.konfiguration import Warner, warne_stderr

Knoten = dict[str, Any]
Kante = dict[str, Any]
Befund = dict[str, Any]

ROLLE_MIT_TESTS = "mit-tests"
_C_SPRACHEN = frozenset({"c", "cpp"})
_C_ENDUNGEN = (".c", ".cc", ".cpp", ".cxx")


@dataclass
class Struktur:
    knoten: list[Knoten]
    kanten: list[Kante]
    befunde: list[Befund]
    # Zählung der Aufrufstellen (nur für Berichte, nicht in daidalos.json)
    aufrufe: dict[str, int] | None = None


# ---------------------------------------------------------------- Ids


def modul_id(gradle_pfad: str) -> str:
    return f"modul:{gradle_pfad}"


def ordner_id(pfad: str) -> str:
    teile = pfad.split("/")
    return f"ordner:{teile[0] if len(teile) > 1 else '.'}"


def datei_id(pfad: str) -> str:
    return f"datei:{pfad}"


def paket_id(container: str, name: str) -> str:
    """Im Modul ``paket:<gradle-pfad>/<name>``, im Ordner ``paket:<ordner-id>/<name>``."""
    behaelter = container.removeprefix("modul:")
    return f"paket:{behaelter}/{name}"


def kanten_id(art: str, von: str, nach: str, rolle: str | None = None) -> str:
    basis = f"kante:{art}:{von}->{nach}"
    return f"{basis}:{rolle}" if rolle else basis


# ---------------------------------------------------------------- Zuordnung


def ist_test_quellsatz(quellsatz: str | None) -> bool:
    if quellsatz is None:
        return False
    return "test" in quellsatz or "Test" in quellsatz


def ordne_zu(datei: Knoten, module: list[tuple[str, str]]) -> None:
    """Setzt ``modul``/``ordner``, ``quellsatz`` und ``rolle``.

    ``module`` sind (Ordner, Gradle-Pfad), längste Ordner zuerst.
    """
    pfad: str = datei["pfad"]
    for ordner, gradle_pfad in module:
        praefix = f"{ordner}/" if ordner else ""
        if pfad.startswith(praefix):
            datei["modul"] = modul_id(gradle_pfad)
            rest = pfad[len(praefix) :].split("/")
            if len(rest) >= 3 and rest[0] == "src":
                datei["quellsatz"] = rest[1]
            break
    else:
        datei["ordner"] = ordner_id(pfad)
    datei["rolle"] = TEST if ist_test_quellsatz(datei.get("quellsatz")) else PRODUKTIV


# ---------------------------------------------------------------- Hauptlauf


def _lies(ziel: Path, pfad: str) -> bytes | None:
    try:
        return (ziel / pfad).read_bytes()
    except OSError:
        return None


def _ist_kotlin(datei: Knoten) -> bool:
    return datei["pfad"].endswith(".kt") and datei.get("sprache") == "kotlin"


def _ist_c(datei: Knoten) -> bool:
    return datei.get("sprache") in _C_SPRACHEN and datei["pfad"].lower().endswith(_C_ENDUNGEN)


def baue_struktur(ziel: Path, dateien: list[Knoten], warne: Warner = warne_stderr) -> Struktur:
    """Ergänzt die Datei-Knoten (in place) und liefert alle weiteren Knoten, Kanten und Befunde."""
    erfasst = {d["pfad"] for d in dateien}
    gradle = lies_gradle(ziel, erfasst, warne)
    module = sorted(
        ((m.pfad, m.gradle_pfad) for m in gradle.module), key=lambda m: (-len(m[0]), m[0])
    )
    for datei in dateien:
        ordne_zu(datei, module)
    fremd = {datei_id(d["pfad"]) for d in dateien if d.get("fremd")}

    # Kotlin lesen
    kotlin: dict[str, KotlinDatei] = {}
    funktionen: dict[str, FunktionenDatei] = {}
    for datei in dateien:
        if not _ist_kotlin(datei) or datei.get("lesefehler"):
            continue
        quelle = _lies(ziel, datei["pfad"])
        if quelle is None:
            continue
        inhalt = lies_kotlin(quelle, datei["pfad"])
        kotlin[datei["pfad"]] = inhalt
        funktionen[datei["pfad"]] = lies_funktionen(quelle)
        if inhalt.paket:
            behaelter = datei.get("modul") or datei["ordner"]
            datei["paket"] = paket_id(behaelter, inhalt.paket)

    nach_pfad = {d["pfad"]: d for d in dateien}
    quelldateien = [
        Quelldatei(
            pfad=pfad,
            inhalt=inhalt,
            container=nach_pfad[pfad].get("modul") or nach_pfad[pfad]["ordner"],
            rolle=nach_pfad[pfad]["rolle"],
        )
        for pfad, inhalt in sorted(kotlin.items())
    ]
    aufloesung = loese_auf(quelldateien)

    knoten: list[Knoten] = []
    kanten: list[Kante] = []
    befunde: list[Befund] = []

    knoten.extend(_modul_knoten(gradle))
    knoten.extend(_paket_und_ordner_knoten(dateien, kotlin))
    kanten.extend(_gradle_kanten(gradle))
    kanten.extend(_enthaelt_kanten(dateien))

    datei_kanten: list[Kante] = []
    for k in aufloesung.kanten:
        von, nach = datei_id(k.von), datei_id(k.nach)
        datei_kanten.append(
            {
                "art": "nutzt",
                "beleg": [
                    {
                        "herkunft": b.herkunft,
                        "sicher": b.sicher,
                        "symbol": b.symbol,
                        "zeile": b.zeile,
                    }
                    for b in k.belege
                ],
                "gewicht": k.gewicht,
                "id": kanten_id("nutzt", von, nach, k.rolle),
                "nach": nach,
                "rolle": k.rolle,
                "sicher": k.sicher,
                "von": von,
            }
        )
    c_funktionen = _lies_c(ziel, dateien)
    jni_kanten, jni_befunde = _jni(dateien, kotlin, c_funktionen)
    kanten.extend(datei_kanten)
    kanten.extend(jni_kanten)
    befunde.extend(jni_befunde)

    paket_kanten = _verdichte(datei_kanten, {d["id"]: d.get("paket") for d in dateien})
    # Ordner stehen auf der Modulebene neben den Modulen.
    modul_kanten = _verdichte(
        datei_kanten, {d["id"]: d.get("modul") or d.get("ordner") for d in dateien}
    )
    kanten.extend(paket_kanten)
    kanten.extend(modul_kanten)

    befunde.extend(_unaufgeloest_befunde(aufloesung.unaufgeloest, fremd))

    befunde.extend(
        _zyklen(knoten, dateien, datei_kanten + jni_kanten, paket_kanten, modul_kanten, kanten)
    )
    _ergaenze_metriken(knoten, dateien, kanten)

    messung = miss(
        [
            Quelle(
                pfad=pfad,
                paket=inhalt.paket or "",
                container=nach_pfad[pfad].get("modul") or nach_pfad[pfad]["ordner"],
                rolle=nach_pfad[pfad]["rolle"],
                quellsatz=nach_pfad[pfad].get("quellsatz"),
                importe=inhalt.importe,
                inhalt=funktionen[pfad],
                externe=[(e.klasse, e.name, e.zeile) for e in inhalt.externe],
                fremd=bool(nach_pfad[pfad].get("fremd")),
            )
            for pfad, inhalt in sorted(kotlin.items())
        ],
        [
            CQuelle(
                pfad=pfad,
                rolle=nach_pfad[pfad]["rolle"],
                quellsatz=nach_pfad[pfad].get("quellsatz"),
                funktionen=liste,
                namen={
                    c.name: ((n.klasse, n.methode) if (n := dekodiere(c.name)) else None)
                    for c in liste
                },
            )
            for pfad, liste in sorted(c_funktionen.items())
        ],
        {d["pfad"]: d["id"] for d in dateien},
        _abhaengigkeiten(kanten),
    )
    knoten.extend(messung.knoten)
    kanten.extend(messung.kanten)
    befunde.extend(messung.befunde)
    for pfad, felder in messung.datei_felder.items():
        nach_pfad[pfad].update(felder)

    kanten.sort(key=lambda k: (k["von"], k["nach"], k["art"], k["id"]))
    knoten.sort(key=lambda k: k["id"])
    befunde.sort(key=lambda b: b["id"])
    return Struktur(knoten, kanten, befunde, dict(messung.statistik))


def _abhaengigkeiten(kanten: list[Kante]) -> dict[str, set[str]]:
    """Modul-Id → alle Module, von denen es über Gradle-Kanten (jeder Art) transitiv abhängt."""
    direkt: dict[str, set[str]] = defaultdict(set)
    for k in kanten:
        if k["art"].startswith("gradle-"):
            direkt[k["von"]].add(k["nach"])
    ergebnis: dict[str, set[str]] = {}
    for modul in direkt:
        gesehen: set[str] = set()
        offen = list(direkt[modul])
        while offen:
            m = offen.pop()
            if m not in gesehen:
                gesehen.add(m)
                offen.extend(direkt.get(m, set()))
        ergebnis[modul] = gesehen
    return ergebnis


# ---------------------------------------------------------------- Knoten


def _modul_knoten(gradle: GradleErgebnis) -> list[Knoten]:
    return [
        {
            "art": "modul",
            "gradle_pfad": m.gradle_pfad,
            "id": modul_id(m.gradle_pfad),
            "pfad": m.pfad,
            "plugins": list(m.plugins),
        }
        for m in gradle.module
    ]


def _paket_und_ordner_knoten(dateien: list[Knoten], kotlin: dict[str, KotlinDatei]) -> list[Knoten]:
    ergebnis: dict[str, Knoten] = {}
    mitglieder: dict[str, list[Knoten]] = defaultdict(list)
    for datei in dateien:
        if "ordner" in datei and datei["ordner"] not in ergebnis:
            ordner = datei["ordner"].removeprefix("ordner:")
            ergebnis[datei["ordner"]] = {"art": "ordner", "id": datei["ordner"], "pfad": ordner}
        if "ordner" in datei:
            mitglieder[datei["ordner"]].append(datei)
        if "paket" in datei:
            mitglieder[datei["paket"]].append(datei)
            if datei["paket"] not in ergebnis:
                paket: Knoten = {
                    "art": "paket",
                    "id": datei["paket"],
                    "name": kotlin[datei["pfad"]].paket,
                }
                if "modul" in datei:
                    paket["modul"] = datei["modul"]
                else:
                    paket["ordner"] = datei["ordner"]
                ergebnis[datei["paket"]] = paket
    # Ein Paket oder Ordner aus lauter Fremdcode ist selbst fremd.
    for knoten_id, knoten in ergebnis.items():
        if mitglieder[knoten_id] and all(d.get("fremd") for d in mitglieder[knoten_id]):
            knoten["fremd"] = True
    return list(ergebnis.values())


def gruppen_hash(dateien: list[Knoten]) -> str:
    """SHA-256 über die sortierten Zeilen ``<pfad> <hash>`` der Dateien einer Gruppe."""
    zeilen = sorted(f"{d['pfad']} {d.get('hash', '')}" for d in dateien)
    return "sha256:" + hashlib.sha256("\n".join(zeilen).encode("utf-8")).hexdigest()


def kopplung(fan_in: int, fan_out: int) -> dict[str, Any]:
    gesamt = fan_in + fan_out
    return {
        "fan_in": fan_in,
        "fan_out": fan_out,
        "instabilitaet": round(fan_out / gesamt, 3) if gesamt else None,
    }


def _ergaenze_metriken(knoten: list[Knoten], dateien: list[Knoten], kanten: list[Kante]) -> None:
    """Kopplung je Knoten, dazu Zeilen, Dateien und Hash für Module, Pakete und Ordner."""
    rein: dict[str, set[str]] = defaultdict(set)
    raus: dict[str, set[str]] = defaultdict(set)
    for k in kanten:
        if k["art"] == "nutzt" and k["rolle"] == PRODUKTIV:
            raus[k["von"]].add(k["nach"])
            rein[k["nach"]].add(k["von"])
    mitglieder: dict[str, list[Knoten]] = defaultdict(list)
    for datei in dateien:
        for feld in ("modul", "ordner", "paket"):
            if feld in datei:
                mitglieder[datei[feld]].append(datei)
    for k in [*knoten, *dateien]:
        k["metriken"] = kopplung(len(rein[k["id"]]), len(raus[k["id"]]))
        if k["art"] == "datei":
            continue
        eigene = [d for d in mitglieder[k["id"]] if not d.get("fremd")]
        k["dateien"] = len(eigene)
        k["zeilen"] = sum(d.get("zeilen", 0) for d in eigene)
        k["hash"] = gruppen_hash(mitglieder[k["id"]])


# ---------------------------------------------------------------- Kanten


def _gradle_kanten(gradle: GradleErgebnis) -> list[Kante]:
    gruppen: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for a in gradle.abhaengigkeiten:
        gruppen[(a.art, a.von, a.nach)].append(a.beleg)
    kanten: list[Kante] = []
    for (art, von, nach), belege in sorted(gruppen.items()):
        von_id, nach_id = modul_id(von), modul_id(nach)
        kanten.append(
            {
                "art": art,
                "beleg": sorted(belege, key=lambda b: (b["datei"], b["zeile"])),
                "gewicht": len(belege),
                "id": kanten_id(art, von_id, nach_id),
                "nach": nach_id,
                "rolle": TEST if art == "gradle-test" else PRODUKTIV,
                "sicher": True,
                "von": von_id,
            }
        )
    return kanten


def _enthaelt_kanten(dateien: list[Knoten]) -> list[Kante]:
    paare: set[tuple[str, str]] = set()
    for datei in dateien:
        behaelter = datei.get("modul") or datei["ordner"]
        paare.add((behaelter, datei["id"]))
        if "paket" in datei:
            paare.add((datei["paket"], datei["id"]))
            paare.add((behaelter, datei["paket"]))
    return [
        {"art": "enthaelt", "id": kanten_id("enthaelt", von, nach), "nach": nach, "von": von}
        for von, nach in sorted(paare)
    ]


def _verdichte(datei_kanten: list[Kante], zuordnung: dict[str, str | None]) -> list[Kante]:
    """Datei-Kanten zu Kanten zwischen Paketen oder Modulen, getrennt nach Rolle."""
    summen: dict[tuple[str, str, str], list[int]] = {}
    sicher: dict[tuple[str, str, str], bool] = {}
    for k in datei_kanten:
        von, nach = zuordnung.get(k["von"]), zuordnung.get(k["nach"])
        if von is None or nach is None or von == nach:
            continue
        schluessel = (von, nach, k["rolle"])
        summen.setdefault(schluessel, []).append(k["gewicht"])
        sicher[schluessel] = sicher.get(schluessel, False) or k["sicher"]
    return [
        {
            "art": "nutzt",
            "dateikanten": len(gewichte),
            "gewicht": sum(gewichte),
            "id": kanten_id("nutzt", von, nach, rolle),
            "nach": nach,
            "rolle": rolle,
            "sicher": sicher[(von, nach, rolle)],
            "von": von,
        }
        for (von, nach, rolle), gewichte in sorted(summen.items())
    ]


# ---------------------------------------------------------------- JNI


def _lies_c(ziel: Path, dateien: list[Knoten]) -> dict[str, list[CFunktion]]:
    """``Java_…``-Funktionen je C/C++-Datei."""
    ergebnis: dict[str, list[CFunktion]] = {}
    for datei in dateien:
        if not _ist_c(datei) or datei.get("lesefehler"):
            continue
        quelle = _lies(ziel, datei["pfad"])
        if quelle is None:
            continue
        gefunden = finde_c_funktionen(quelle)
        if gefunden:
            ergebnis[datei["pfad"]] = gefunden
    return ergebnis


def _jni(
    dateien: list[Knoten], kotlin: dict[str, KotlinDatei], c_funktionen: dict[str, list[CFunktion]]
) -> tuple[list[Kante], list[Befund]]:
    nach_pfad = {d["pfad"]: d for d in dateien}
    # (JVM-Klasse, Methode) → (Kotlin-Pfad, Zeile)
    kotlin_seite: dict[tuple[str, str], tuple[str, int]] = {}
    for pfad, inhalt in sorted(kotlin.items()):
        for ext in inhalt.externe:
            klasse = f"{inhalt.paket}.{ext.klasse}" if inhalt.paket else ext.klasse
            kotlin_seite.setdefault((klasse, ext.name), (pfad, ext.zeile))
    # (JVM-Klasse, Methode) → [(C-Pfad, Zeile, C-Name)]
    c_seite: dict[tuple[str, str], list[tuple[str, int, str]]] = defaultdict(list)
    for pfad, liste in sorted(c_funktionen.items()):
        for funktion in liste:
            name = dekodiere(funktion.name)
            if name is None:
                continue
            c_seite[(name.klasse, name.methode)].append((pfad, funktion.zeile, funktion.name))

    paare: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    befunde: list[Befund] = []
    for schluessel, (kt_pfad, kt_zeile) in sorted(kotlin_seite.items()):
        treffer = c_seite.get(schluessel)
        if not treffer:
            if not nach_pfad[kt_pfad].get("fremd"):
                befunde.append(_jni_befund("kotlin", kt_pfad, kt_zeile, ".".join(schluessel)))
            continue
        for c_pfad, c_zeile, _ in sorted(treffer):
            paare[(kt_pfad, c_pfad)].append(
                {"funktion": ".".join(schluessel), "zeile_c": c_zeile, "zeile_kotlin": kt_zeile}
            )
    for schluessel, treffer in sorted(c_seite.items()):
        if schluessel in kotlin_seite:
            continue
        for c_pfad, c_zeile, c_name in sorted(treffer):
            if not nach_pfad[c_pfad].get("fremd"):
                befunde.append(_jni_befund("c", c_pfad, c_zeile, c_name))

    kanten: list[Kante] = []
    for (kt_pfad, c_pfad), belege in sorted(paare.items()):
        rolle = nach_pfad[kt_pfad]["rolle"]
        von, nach = datei_id(kt_pfad), datei_id(c_pfad)
        kanten.append(
            {
                "art": "jni",
                "beleg": sorted(belege, key=lambda b: (b["zeile_kotlin"], b["funktion"])),
                "gewicht": len(belege),
                "id": kanten_id("jni", von, nach, rolle),
                "nach": nach,
                "rolle": rolle,
                "sicher": True,
                "von": von,
            }
        )
    return kanten, befunde


def _jni_befund(seite: str, pfad: str, zeile: int, name: str) -> Befund:
    return {
        "beleg": {"funktion": name, "seite": seite, "zeile": zeile},
        "id": f"befund:jni-ohne-gegenstueck:{pfad}:{name}",
        "knoten": [datei_id(pfad)],
        "quelle": "daidalos",
        "regel": "jni-ohne-gegenstueck",
        "schwere": "hinweis",
    }


# ---------------------------------------------------------------- Befunde


def _unaufgeloest_befunde(unaufgeloest: list[Any], fremd: set[str]) -> list[Befund]:
    je_datei: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for u in unaufgeloest:
        je_datei[u.pfad].append({"import": u.name, "zeile": u.zeile})
    befunde: list[Befund] = []
    for pfad, importe in sorted(je_datei.items()):
        if datei_id(pfad) in fremd:
            continue
        befunde.append(
            {
                "beleg": {"importe": importe},
                "id": f"befund:unaufgeloest:{pfad}",
                "knoten": [datei_id(pfad)],
                "quelle": "daidalos",
                "regel": "unaufgeloest",
                "schwere": "hinweis",
            }
        )
    return befunde


def _graph_kanten(kanten: list[Kante], nur_produktiv: bool) -> list[GraphKante]:
    return [
        GraphKante(k["id"], k["von"], k["nach"], k.get("gewicht", 1), k.get("sicher", True))
        for k in kanten
        if not nur_produktiv or k.get("rolle") == PRODUKTIV
    ]


def _zyklen(
    knoten: list[Knoten],
    dateien: list[Knoten],
    datei_kanten: list[Kante],
    paket_kanten: list[Kante],
    modul_kanten: list[Kante],
    alle_kanten: list[Kante],
) -> list[Befund]:
    fremd = {d["id"] for d in dateien if d.get("fremd")} | {
        k["id"] for k in knoten if k.get("fremd")
    }
    gradle_kanten = [k for k in alle_kanten if k["art"].startswith("gradle-")]
    befunde: list[Befund] = []
    for nur_produktiv, rolle in ((True, PRODUKTIV), (False, ROLLE_MIT_TESTS)):
        befunde += zyklus_befunde("datei", rolle, _graph_kanten(datei_kanten, nur_produktiv), fremd)
        befunde += zyklus_befunde("paket", rolle, _graph_kanten(paket_kanten, nur_produktiv), fremd)
        befunde += zyklus_befunde(
            "modul", rolle, _graph_kanten(modul_kanten, nur_produktiv), fremd, kantenart="nutzt"
        )
        befunde += zyklus_befunde(
            "modul", rolle, _graph_kanten(gradle_kanten, nur_produktiv), fremd, kantenart="gradle"
        )
    return nur_neue_test_zyklen(befunde)


def nur_neue_test_zyklen(befunde: list[Befund]) -> list[Befund]:
    """Zyklen „mit Tests“ nur, wenn ihre Mitgliedermenge nicht schon produktiv vorkommt.

    Ein Test-Zyklus, der produktive Zyklen derselben Ebene enthält, bekommt
    ``enthaelt_produktiv`` mit deren Ids.
    """

    def ebene(b: Befund) -> tuple[str, str | None]:
        return (b["beleg"]["ebene"], b["beleg"].get("kantenart"))

    produktiv = [b for b in befunde if b["beleg"]["rolle"] == PRODUKTIV]
    ergebnis: list[Befund] = []
    for b in befunde:
        if b["beleg"]["rolle"] != ROLLE_MIT_TESTS:
            ergebnis.append(b)
            continue
        menge = set(b["knoten"])
        gleiche_ebene = [p for p in produktiv if ebene(p) == ebene(b)]
        if any(set(p["knoten"]) == menge for p in gleiche_ebene):
            continue
        enthalten = sorted(p["id"] for p in gleiche_ebene if set(p["knoten"]) <= menge)
        if enthalten:
            b["beleg"]["enthaelt_produktiv"] = enthalten
        ergebnis.append(b)
    return ergebnis
