"""``daidalos arbeitsblatt``: Arbeitsblatt für ein Modul, ein Paket oder eine Datei.

Vorbild sind die Arbeitsblätter von Floorplan: je Datei, was sie deklariert, die erste KDoc-Zeile,
was sie nutzt und wer sie nutzt. Die Dateien werden dafür **neu** mit dem Kotlin-Adapter gelesen;
in ``daidalos.json`` kommt nichts dazu. Schreibt nichts.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from daidalos.adapter.baum import alle, parse, text, zeile
from daidalos.adapter.kotlin import lies_kotlin
from daidalos.ids import datei_der_funktion
from daidalos.render import anzeigename
from daidalos.zusammenfassung import (
    stand_der_beschreibung,
    wichtige_dateien,
    wichtige_funktionen,
)

Knoten = dict[str, Any]

MAX_ZEILEN = 400  # Ziel für die Länge eines Arbeitsblatts
KANTEN_JE_RICHTUNG = 8  # je Datei und Richtung voll gezeigte Kanten
BELEGE_JE_KANTE = 3
KDOC_LAENGE = 160

_ADR = re.compile(r"ADR-\d{4}")
# Annotationen auf eigener Zeile liest die Grammatik teils als eigene Knoten vor der Deklaration
# (``@Deprecated("x")`` als ``annotated_expression``); die KDoc davor gehört trotzdem dazu.
_NUR_ANNOTATION = frozenset({"annotated_expression", "annotation"})
_ART_WORT = {
    "klasse": "class",
    "objekt": "object",
    "funktion": "fun",
    "eigenschaft": "val",
    "typalias": "typealias",
}


class ArbeitsblattFehler(Exception):
    """Knoten passt nicht; Exit-Code 2."""


def _mehrzahl(anzahl: int, eins: str, viele: str) -> str:
    return f"{anzahl} {eins if anzahl == 1 else viele}"


# ---------------------------------------------------------------- Lesen einer Datei


@dataclass
class Gelesen:
    """Was das Arbeitsblatt aus dem Quelltext einer Datei braucht."""

    vorhanden: bool = True
    geaendert: bool = False  # Inhalt passt nicht mehr zum Hash der Messung
    kdoc_datei: str | None = None
    # Kommentar ohne KDoc vor der ersten Deklaration (z. B. ``// Prototyp (…)``), gekürzt
    kopfkommentar: str | None = None
    # (Art, Name, Zeile, erste KDoc-Zeile) der Deklarationen der obersten Ebene
    deklariert: list[tuple[str, str, int, str | None]] = field(default_factory=list)
    adr: Counter[str] = field(default_factory=Counter)


def _hash(inhalt: bytes) -> str:
    text_lf = inhalt.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return f"sha256:{hashlib.sha256(text_lf).hexdigest()}"


def erste_kdoc_zeile(kommentar: str) -> str | None:
    """Erste inhaltliche Zeile eines ``/** … */``-Kommentars, ohne Tags wie ``@param``."""
    if not kommentar.startswith("/**"):
        return None
    rumpf = kommentar[3:].removesuffix("*/")
    for roh in rumpf.splitlines():
        zeile_text = roh.strip().lstrip("*").strip()
        if not zeile_text:
            continue
        if zeile_text.startswith("@"):
            return None
        if len(zeile_text) > KDOC_LAENGE:
            zeile_text = zeile_text[: KDOC_LAENGE - 1].rstrip() + "…"
        return zeile_text
    return None


def kopfkommentar(kommentare: list[str]) -> str | None:
    """Erste Zeilen aufeinanderfolgender Kommentare als ein Text, höchstens ``KDOC_LAENGE``."""
    teile: list[str] = []
    for kommentar in kommentare:
        for roh in kommentar.splitlines():
            zeile_text = roh.strip().removeprefix("//").removeprefix("/*").removesuffix("*/")
            zeile_text = zeile_text.strip().lstrip("*").strip()
            if zeile_text:
                teile.append(zeile_text)
        if len(" ".join(teile)) > KDOC_LAENGE:
            break
    if not teile:
        return None
    ganz = " ".join(teile)
    return ganz if len(ganz) <= KDOC_LAENGE else ganz[: KDOC_LAENGE - 1].rstrip() + "…"


def lies_quelle(ziel: Path, knoten: Knoten) -> Gelesen:
    pfad = ziel / knoten["pfad"]
    try:
        inhalt = pfad.read_bytes()
    except OSError:
        return Gelesen(vorhanden=False)
    gelesen = Gelesen(geaendert=knoten.get("hash") not in (None, _hash(inhalt)))
    if b"\0" in inhalt[:8192]:
        return gelesen
    if knoten.get("sprache") == "kotlin" and knoten["pfad"].endswith(".kt"):
        wurzel = parse("kotlin", inhalt)
        # (erste Zeile, letzte Zeile) des Knotens nach einer KDoc → erste KDoc-Zeile. Gilt für die
        # erste Deklaration in diesem Bereich; so auch für Deklarationen, die die Grammatik nur
        # als Teil eines anderen Knotens liest (``annotation class`` nach Annotationszeilen).
        kdoc: dict[tuple[int, int], str] = {}
        vorher = None
        kopf: list[str] = []
        kopf_offen = True
        for kind in wurzel.named_children:
            if kopf_offen and kind.type in ("line_comment", "block_comment"):
                if not text(kind).startswith("/**"):
                    kopf.append(text(kind))
            elif kopf_offen and kind.type not in ("package_header", "import", "file_annotation"):
                kopf_offen = False
            if kind.type == "package_header" and vorher is not None and gelesen.kdoc_datei is None:
                gelesen.kdoc_datei = erste_kdoc_zeile(text(vorher))
            elif kind.type != "block_comment" and vorher is not None:
                erste = erste_kdoc_zeile(text(vorher))
                if erste is not None:
                    kdoc[(zeile(kind), kind.end_point[0] + 1)] = erste
            if kind.type == "block_comment":
                vorher = kind
            elif kind.type not in _NUR_ANNOTATION:
                vorher = None
        gelesen.kopfkommentar = kopfkommentar(kopf)
        datei = lies_kotlin(inhalt, knoten["pfad"])
        oberste = sorted(
            (d for d in datei.deklarationen if d.oberste_ebene), key=lambda d: (d.zeile, d.name)
        )
        vergeben: set[tuple[int, int]] = set()
        for d in oberste:
            bereich = next((b for b in kdoc if b[0] <= d.zeile <= b[1] and b not in vergeben), None)
            if bereich is not None:
                vergeben.add(bereich)
            doc = kdoc[bereich] if bereich is not None else None
            gelesen.deklariert.append((d.art, d.name, d.zeile, doc))
        for k in alle(wurzel):
            if k.type in ("line_comment", "block_comment"):
                gelesen.adr.update(_ADR.findall(text(k)))
    else:
        gelesen.adr.update(_ADR.findall(inhalt.decode("utf-8", "replace")))
    return gelesen


# ---------------------------------------------------------------- Arbeitsblatt


class Arbeitsblatt:
    def __init__(
        self,
        messung: dict[str, Any],
        ziel: Path,
        deutung: dict[str, Any] | None = None,
        max_zeilen: int = MAX_ZEILEN,
    ) -> None:
        self.messung = messung
        self.ziel = ziel
        self.max_zeilen = max_zeilen
        self.knoten = {k["id"]: k for k in messung["knoten"]}
        self.wichtig = wichtige_dateien(messung)
        self.wichtig_funktionen = wichtige_funktionen(messung)
        roh = (deutung or {}).get("beschreibungen")
        self.beschreibungen = roh if isinstance(roh, dict) else {}
        self.funktionen: dict[str, list[Knoten]] = {}
        for k in messung["knoten"]:
            if k["art"] == "funktion":
                self.funktionen.setdefault(datei_der_funktion(k), []).append(k)
        self.raus: dict[str, list[dict[str, Any]]] = {}
        self.rein: dict[str, list[dict[str, Any]]] = {}
        for k in messung["kanten"]:
            if k["art"] in ("nutzt", "jni") or k["art"].startswith("gradle-"):
                self.raus.setdefault(k["von"], []).append(k)
                self.rein.setdefault(k["nach"], []).append(k)

    # ------------------------------------------------------------ Hilfen

    def name(self, knoten_id: str) -> str:
        k = self.knoten.get(knoten_id)
        if k is None:
            return knoten_id
        return k["pfad"] if k["art"] == "datei" else anzeigename(k)

    def stand(self, knoten_id: str) -> str:
        return stand_der_beschreibung(self.beschreibungen.get(knoten_id), self.knoten[knoten_id])

    @staticmethod
    def _metriken(k: Knoten) -> str:
        m = k.get("metriken", {})
        return f"Fan-in {m.get('fan_in', 0)}, Fan-out {m.get('fan_out', 0)}"

    def dateien_von(self, gruppe: Knoten) -> list[Knoten]:
        feld = "paket" if gruppe["art"] == "paket" else gruppe["art"]
        dateien = [
            k
            for k in self.messung["knoten"]
            if k["art"] == "datei" and k.get(feld) == gruppe["id"] and not k.get("fremd")
        ]
        # Produktive vor Test-Dateien, dann nach Fan-in, dann Pfad.
        return sorted(
            dateien,
            key=lambda k: (
                k.get("rolle") == "test",
                -k.get("metriken", {}).get("fan_in", 0),
                k["pfad"],
            ),
        )

    # ------------------------------------------------------------ Datei

    def _kanten_zeilen(self, kanten: list[dict[str, Any]], richtung: str) -> list[str]:
        ende = "nach" if richtung == "raus" else "von"
        kanten = sorted(
            kanten, key=lambda k: (k.get("rolle") == "test", -k.get("gewicht", 0), k[ende])
        )
        z = []
        for k in kanten[:KANTEN_JE_RICHTUNG]:
            merkmale = [k["art"] if k["art"] != "nutzt" else f"Gewicht {k.get('gewicht', 0)}"]
            if k["art"] == "jni":
                merkmale = [f"jni, {k.get('gewicht', 0)} Paare"]
            if k.get("rolle") == "test":
                merkmale.append("test")
            if not k.get("sicher", True):
                merkmale.append("unsicher")
            belege = []
            for b in k.get("beleg", [])[:BELEGE_JE_KANTE]:
                if "symbol" in b:
                    belege.append(f"{b['symbol']} Z. {b['zeile']}")
                elif "funktion" in b:
                    belege.append(f"{b['funktion']} Z. {b['zeile_kotlin']}/{b['zeile_c']}")
            rest = len(k.get("beleg", [])) - BELEGE_JE_KANTE
            if rest > 0:
                belege.append(f"+{rest}")
            beleg = f": {', '.join(belege)}" if belege else ""
            z.append(f"  - {self.name(k[ende])} ({', '.join(merkmale)}){beleg}")
        if len(kanten) > KANTEN_JE_RICHTUNG:
            z.append(f"  - … und {len(kanten) - KANTEN_JE_RICHTUNG} weitere")
        return z

    def _funktionszeilen(self, k: Knoten) -> list[str]:
        """Funktions-Ids der Datei mit Komplexität, nach Zeile."""
        funktionen = sorted(
            self.funktionen.get(k["pfad"], []), key=lambda f: (f["zeile_von"], f["id"])
        )
        z = []
        for f in funktionen:
            komplex = f.get("metriken", {}).get("komplexitaet")
            merkmal = f"Komplexität {komplex}" if komplex is not None else "C"
            if f.get("implizit"):
                merkmal = "implizit"
            if f["id"] in self.wichtig_funktionen:
                merkmal += f", wichtig, Deutung {self.stand(f['id'])}"
            bis = f"–{f['zeile_bis']}" if f["zeile_bis"] != f["zeile_von"] else ""
            z.append(f"  - `{f['id']}` (Z. {f['zeile_von']}{bis}, {merkmal})")
        return z

    def datei_voll(self, k: Knoten, mit_funktionen: bool = False) -> list[str]:
        gelesen = lies_quelle(self.ziel, k)
        kopf = [f"{k.get('zeilen', 0)} Zeilen", k["sprache"]]
        if k.get("quellsatz"):
            kopf.append(f"Quellsatz {k['quellsatz']}")
        if k.get("rolle") == "test":
            kopf.append("Test")
        kopf.append(self._metriken(k))
        if k["id"] in self.wichtig:
            kopf.append("wichtig: " + ", ".join(self.wichtig[k["id"]]))
        kopf.append(f"Deutung {self.stand(k['id'])}")
        z = [f"### {k['pfad']}", "", f"`{k['id']}` · " + " · ".join(kopf)]
        if not gelesen.vorhanden:
            z.append("- Datei fehlt im Arbeitsbaum (seit dem Scan gelöscht oder verschoben).")
        elif gelesen.geaendert:
            z.append("- Achtung: Inhalt hat sich seit dem Scan geändert; zuerst neu scannen.")
        if gelesen.kdoc_datei:
            z.append(f"- KDoc der Datei: {gelesen.kdoc_datei}")
        if gelesen.kopfkommentar:
            z.append(f"- Kopfkommentar: {gelesen.kopfkommentar}")
        if gelesen.deklariert:
            mit_doc = [d for d in gelesen.deklariert if d[3]]
            ohne_doc = [d for d in gelesen.deklariert if not d[3]]
            z.append("- deklariert:")
            for art, name, nr, doc in mit_doc:
                z.append(f"  - {_ART_WORT.get(art, art)} {name} (Z. {nr}): {doc}")
            if ohne_doc:
                teile = [f"{_ART_WORT.get(a, a)} {n} (Z. {nr})" for a, n, nr, _ in ohne_doc]
                z.append("  - ohne KDoc: " + ", ".join(teile))
        if mit_funktionen and self.funktionen.get(k["pfad"]):
            if not gelesen.deklariert:
                z.append("- deklariert:")
            z.append("  - Funktionen:")
            z += ["  " + zeile for zeile in self._funktionszeilen(k)]
        raus = self.raus.get(k["id"], [])
        rein = self.rein.get(k["id"], [])
        if raus:
            z += ["- nutzt:", *self._kanten_zeilen(raus, "raus")]
        if rein:
            z += ["- genutzt von:", *self._kanten_zeilen(rein, "rein")]
        if not raus and not rein:
            z.append("- keine Kanten")
        if gelesen.adr:
            teile = [
                f"{n} ({anzahl}×)" if anzahl > 1 else n for n, anzahl in sorted(gelesen.adr.items())
            ]
            z.append(f"- ADR in Kommentaren ({sum(gelesen.adr.values())}): " + ", ".join(teile))
        return [*z, ""]

    def datei_kurz(self, k: Knoten) -> str:
        m = k.get("metriken", {})
        test = ", Test" if k.get("rolle") == "test" else ""
        wichtig = ", wichtig" if k["id"] in self.wichtig else ""
        # KDoc der Datei, sonst Kopfkommentar, sonst KDoc der ersten dokumentierten Deklaration.
        gelesen = lies_quelle(self.ziel, k)
        doc = (
            gelesen.kdoc_datei
            or gelesen.kopfkommentar
            or next((d[3] for d in gelesen.deklariert if d[3]), None)
        )
        return (
            f"- {k['pfad']} ({k.get('zeilen', 0)} Z., Fan-in {m.get('fan_in', 0)}, "
            f"Fan-out {m.get('fan_out', 0)}{test}{wichtig})" + (f": {doc}" if doc else "")
        )

    # ------------------------------------------------------------ Gruppen

    def _verdichtet(self, gruppe: Knoten) -> list[str]:
        z: list[str] = []
        for richtung, titel, ende in (("raus", "Nutzt", "nach"), ("rein", "Genutzt von", "von")):
            kanten = (self.raus if richtung == "raus" else self.rein).get(gruppe["id"], [])
            if not kanten:
                continue
            z.append(f"- {titel}:")
            for k in sorted(kanten, key=lambda k: (k["art"], -k.get("gewicht", 0), k[ende])):
                if k["art"] == "nutzt":
                    was = (
                        f"nutzt {k.get('rolle')}, Gewicht {k.get('gewicht', 0)}, "
                        f"{_mehrzahl(k.get('dateikanten', 0), 'Datei-Kante', 'Datei-Kanten')}"
                    )
                else:
                    was = f"{k['art']}, {_mehrzahl(k.get('gewicht', 0), 'Beleg', 'Belege')}"
                z.append(f"  - {self.name(k[ende])} ({was})")
        return z or ["- keine Kanten nach außen"]

    def gruppe(self, g: Knoten) -> list[str]:
        art = {"modul": "Modul", "ordner": "Ordner", "paket": "Paket"}[g["art"]]
        dateien = self.dateien_von(g)
        z = [
            f"# Arbeitsblatt · {art} {self.name(g['id'])}",
            "",
            f"`{g['id']}` · {g.get('dateien', 0)} Dateien · {g.get('zeilen', 0)} Zeilen · "
            f"{self._metriken(g)} · Deutung {self.stand(g['id'])}",
        ]
        if g.get("plugins"):
            z.append(f"Plugins: {', '.join(g['plugins'])}")
        z += ["", "## Kanten nach außen", "", *self._verdichtet(g)]
        if g["art"] in ("modul", "ordner"):
            pakete = sorted(
                (
                    k
                    for k in self.messung["knoten"]
                    if k["art"] == "paket" and k.get(g["art"]) == g["id"]
                ),
                key=lambda k: k["id"],
            )
            if pakete:
                z += ["", "## Pakete", ""]
                for p in pakete:
                    z.append(
                        f"- {p['name']} ({p.get('dateien', 0)} Dateien, {p.get('zeilen', 0)} Z., "
                        f"{self._metriken(p)}, Deutung {self.stand(p['id'])})"
                    )
        z += ["", "## Dateien", ""]
        z.append(
            "Nach Fan-in sortiert, Tests zuletzt. "
            + (
                "Wichtige Dateien voll, die übrigen als eine Zeile."
                if g["art"] != "paket"
                else "Voll, solange das Blatt kurz bleibt, danach als eine Zeile."
            )
        )
        z.append("")
        voll_kandidaten = [k for k in dateien if g["art"] == "paket" or k["id"] in self.wichtig]
        # Platz für die Kurzzeilen aller übrigen Dateien freihalten.
        kurz = [k for k in dateien if k not in voll_kandidaten]
        budget = self.max_zeilen - len(z) - len(kurz) - 4
        bloecke: list[list[str]] = []
        for k in voll_kandidaten:
            block = self.datei_voll(k)
            if len(block) > budget:
                kurz.append(k)
                continue
            budget -= len(block)
            bloecke.append(block)
        for block in bloecke:
            z += block
        if kurz:
            kurz.sort(
                key=lambda k: (
                    k.get("rolle") == "test",
                    -k.get("metriken", {}).get("fan_in", 0),
                    k["pfad"],
                )
            )
            z += ["### Weitere Dateien", ""]
            platz = max(self.max_zeilen - len(z) - 2, 10)
            for k in kurz[:platz]:
                z.append(self.datei_kurz(k))
            if len(kurz) > platz:
                hinweis = (
                    "Arbeitsblatt je Paket" if g["art"] != "paket" else "Arbeitsblatt je Datei"
                )
                z.append(f"- … und {len(kurz) - platz} weitere (siehe {hinweis})")
            z.append("")
        return z

    def baue(self, knoten: Knoten) -> str:
        if knoten["art"] == "datei":
            z = [
                f"# Arbeitsblatt · Datei {knoten['pfad']}",
                "",
                *self.datei_voll(knoten, mit_funktionen=True)[2:],
            ]
        elif knoten["art"] in ("modul", "ordner", "paket"):
            z = self.gruppe(knoten)
        else:
            raise ArbeitsblattFehler(f"Für {knoten['art']}-Knoten gibt es kein Arbeitsblatt")
        return "\n".join(z).rstrip("\n") + "\n"
