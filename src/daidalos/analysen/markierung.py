"""Markierungs-Kette (A08): von markierten Funktionen den Aufrufen folgen.

detekt prüft markierte Funktionen nur in ihrem eigenen Körper. Hier wird jede unmarkierte interne
Funktion gemeldet, die von markiertem Code aus erreicht wird, mit der ganzen Kette dahinter.
Regeln in ``docs/datenformat.md`` (Abschnitt Markierungs-Kette).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from pathspec import GitIgnoreSpec

from daidalos.ids import datei_der_funktion
from daidalos.konfiguration import MarkierungsKonfiguration, Warner, warne_stderr

Knoten = dict[str, Any]
Kante = dict[str, Any]
Befund = dict[str, Any]

REGEL = "markierung-verlassen"


@dataclass
class KettenErgebnis:
    befunde: list[Befund] = field(default_factory=list)
    markiert: int = 0
    ausnahmen: int = 0
    grenzen_sicher: int = 0
    grenzen_unsicher: int = 0


@dataclass(frozen=True)
class _Schritt:
    """Eine erreichte Funktion: über welchen Aufruf (``ueber``: überschriebene bzw.
    ``expect``-Funktion, wenn sie nur über ``ueberschreibt``/``actual`` erreicht wird)."""

    ziel: str
    schritt: str  # ruft, ueberschrieben-von, actual
    ueber: str | None


def _sichere_namen(annotationen: list[dict[str, Any]] | None) -> set[str]:
    return {a["name"] for a in annotationen or [] if a.get("sicher")}


def _markierung(
    namen: tuple[str, ...], f: Knoten, eigene: set[str], umgebend: list[set[str]], datei: set[str]
) -> tuple[str, str] | None:
    """(Annotation, Träger) der Markierung; ``<init>`` deckt nur die eigene Annotation."""
    for name in namen:
        if name in eigene:
            return name, "funktion"
    if f["name"] == "<init>":
        return None
    for stufe in umgebend:
        for name in namen:
            if name in stufe:
                return name, "klasse"
    for name in namen:
        if name in datei:
            return name, "datei"
    return None


def markierung_der_funktion(
    funktion: Knoten, datei: Knoten, namen: tuple[str, ...]
) -> tuple[str, str] | None:
    """(Annotation, Träger) für eine Funktion; ``namen`` aus ``[markierungen].annotationen``.

    Dieselbe Regel wie in der Kette; ``datei`` ist der Datei-Knoten mit ``klassen`` und
    ``annotationen``.
    """
    klassen = {k["name"]: k for k in datei.get("klassen", [])}
    teile = funktion["behaelter"].split(".") if funktion["behaelter"] else []
    umgebend = [
        _sichere_namen(klassen.get(".".join(teile[:i]), {}).get("annotationen"))
        for i in range(len(teile), 0, -1)
    ]
    return _markierung(
        namen,
        funktion,
        _sichere_namen(funktion.get("annotationen")),
        umgebend,
        _sichere_namen(datei.get("annotationen")),
    )


class _Kette:
    def __init__(
        self,
        funktionen: list[Knoten],
        dateien: dict[str, Knoten],
        kanten: list[Kante],
        konfiguration: MarkierungsKonfiguration,
        delegiert: dict[str, set[str]],
    ) -> None:
        self.konfiguration = konfiguration
        self.delegiert = delegiert
        self.funktionen = {f["id"]: f for f in funktionen}
        self.dateien = dateien
        ausgenommen = GitIgnoreSpec.from_lines(konfiguration.ausgenommen)
        self.markierung: dict[str, tuple[str, str]] = {}
        self.ausnahme: set[str] = set()
        self.zaehlt: set[str] = set()
        for f in funktionen:
            pfad = datei_der_funktion(f)
            datei = dateien.get(pfad, {})
            if (
                f.get("sprache") != "kotlin"
                or f.get("rolle") != "produktiv"
                or datei.get("fremd")
                or ausgenommen.match_file(pfad)
            ):
                continue
            self.zaehlt.add(f["id"])
            klassen = {k["name"]: k for k in datei.get("klassen", [])}
            eigene = _sichere_namen(f.get("annotationen"))
            # umgebende Klassen von innen nach außen
            teile = f["behaelter"].split(".") if f["behaelter"] else []
            umgebend = [
                _sichere_namen(klassen.get(".".join(teile[:i]), {}).get("annotationen"))
                for i in range(len(teile), 0, -1)
            ]
            if eigene & set(konfiguration.ausnahmen) or any(
                u & set(konfiguration.ausnahmen) for u in umgebend
            ):
                self.ausnahme.add(f["id"])
            treffer = self._markierung(
                f, eigene, umgebend, _sichere_namen(datei.get("annotationen"))
            )
            if treffer is not None:
                self.markierung[f["id"]] = treffer

        self.raus: dict[str, list[Kante]] = defaultdict(list)
        self.ueberschrieben_von: dict[str, list[tuple[str, bool]]] = defaultdict(list)
        self.actuals: dict[str, list[tuple[str, bool]]] = defaultdict(list)
        for k in kanten:
            if k["art"] == "ruft":
                self.raus[k["von"]].append(k)
            elif k["art"] == "ueberschreibt":
                self.ueberschrieben_von[k["nach"]].append((k["von"], k["sicher"]))
            elif k["art"] == "actual":
                self.actuals[k["nach"]].append((k["von"], k["sicher"]))
        for liste in self.raus.values():
            liste.sort(key=lambda k: k["nach"])
        self._erweitert: dict[tuple[str, bool], list[_Schritt]] = {}
        self._ketten: dict[tuple[str, bool], dict[str, Any]] = {}

    def _markierung(
        self, f: Knoten, eigene: set[str], umgebend: list[set[str]], datei: set[str]
    ) -> tuple[str, str] | None:
        return _markierung(self.konfiguration.annotationen, f, eigene, umgebend, datei)

    # ------------------------------------------------------------ Graph

    def endet(self, funktion_id: str) -> bool:
        """Markiert oder Ausnahme: Die Kette endet hier."""
        return funktion_id in self.markierung or funktion_id in self.ausnahme

    def verstoss(self, funktion_id: str) -> bool:
        """Zählt, ist weder markiert noch Ausnahme und hat Code (nicht ``ohne_koerper``, kein
        impliziter Konstruktor)."""
        f = self.funktionen.get(funktion_id)
        return (
            f is not None
            and funktion_id in self.zaehlt
            and not self.endet(funktion_id)
            and not f.get("ohne_koerper")
            and not f.get("implizit")
        )

    def erweitere(self, ziel: str, sicher: bool) -> list[_Schritt]:
        """Das Ziel eines Aufrufs und alle Funktionen, die es (rekursiv) überschreiben bzw. als
        ``actual`` umsetzen."""
        schluessel = (ziel, sicher)
        if schluessel in self._erweitert:
            return self._erweitert[schluessel]
        ergebnis = [_Schritt(ziel, "ruft", None)]
        gesehen = {ziel}
        offen = deque([ziel])
        while offen:
            aktuell = offen.popleft()
            nachfolger = [
                ("ueberschrieben-von", x, s) for x, s in self.ueberschrieben_von.get(aktuell, [])
            ] + [("actual", x, s) for x, s in self.actuals.get(aktuell, [])]
            for schritt, x, s in sorted(nachfolger, key=lambda e: (e[1], e[0])):
                if (sicher and not s) or x in gesehen:
                    continue
                gesehen.add(x)
                ergebnis.append(_Schritt(x, schritt, aktuell))
                offen.append(x)
        self._erweitert[schluessel] = ergebnis
        return ergebnis

    def aufrufe(self, von: str, sicher: bool) -> list[tuple[Kante, list[int]]]:
        """Ausgehende ``ruft``-Kanten mit den Zeilen ihrer (sicheren) Belege."""
        ergebnis = []
        for k in self.raus.get(von, []):
            if sicher and not k["sicher"]:
                continue
            zeilen = sorted(z for b in k["beleg"] if b["sicher"] or not sicher for z in b["zeilen"])
            ergebnis.append((k, zeilen))
        return ergebnis

    def grenzen(self, start: str, sicher: bool) -> dict[str, tuple[list[int], bool]]:
        """Unmarkierte Ziele eines markierten Starts: Zeilen und ob über ``ueberschreibt``."""
        ergebnis: dict[str, tuple[list[int], bool]] = {}
        for k, zeilen in self.aufrufe(start, sicher):
            for s in self.erweitere(k["nach"], sicher):
                if s.ziel == start or not self.verstoss(s.ziel):
                    continue
                alt_zeilen, alt_ueber = ergebnis.get(s.ziel, ([], True))
                ergebnis[s.ziel] = (
                    sorted(alt_zeilen + zeilen),
                    alt_ueber and s.schritt != "ruft",
                )
        return ergebnis

    def kette(self, nach: str, sicher: bool) -> dict[str, Any]:
        """Breitensuche ab ``nach`` über unmarkierte Funktionen."""
        schluessel = (nach, sicher)
        if schluessel in self._ketten:
            return self._ketten[schluessel]
        erreicht: dict[str, dict[str, Any]] = {}
        ausnahmen: set[str] = set()
        ueber = False
        tiefe = {nach: 0}
        offen = deque([nach])
        while offen:
            aktuell = offen.popleft()
            for k, _ in self.aufrufe(aktuell, sicher):
                for s in self.erweitere(k["nach"], sicher):
                    if s.ziel in tiefe:
                        continue
                    if s.ziel in self.ausnahme and s.ziel in self.zaehlt:
                        ausnahmen.add(s.ziel)
                        continue
                    if not self.verstoss(s.ziel):
                        continue
                    tiefe[s.ziel] = tiefe[aktuell] + 1
                    eintrag: dict[str, Any] = {
                        "funktion": s.ziel,
                        "tiefe": tiefe[s.ziel],
                        "von": aktuell,
                        "zeile": self.funktionen[s.ziel]["zeile_von"],
                    }
                    if s.schritt != "ruft":
                        eintrag["schritt"] = s.schritt
                        eintrag["ueber"] = s.ueber
                        ueber = True
                    erreicht[s.ziel] = eintrag
                    offen.append(s.ziel)
        ergebnis = {
            "ausnahmen": sorted(ausnahmen),
            "eintraege": sorted(erreicht.values(), key=lambda e: (e["tiefe"], e["funktion"])),
            "ueber": ueber,
        }
        self._ketten[schluessel] = ergebnis
        return ergebnis

    # ------------------------------------------------------------ Befunde

    def befund(self, start: str, nach: str, zeilen: list[int], ueber: bool, sicher: bool) -> Befund:
        kette = self.kette(nach, sicher)
        annotation, traeger = self.markierung[start]
        beleg: dict[str, Any] = {
            "anzahl": len(kette["eintraege"]) + 1,
            "ausnahmen": kette["ausnahmen"],
            "delegiert_gelesen": len(self.delegiert.get(start, set())),
            "kette": kette["eintraege"],
            "markierung": {"name": annotation, "traeger": traeger},
            "nach": nach,
            "nach_zeile": self.funktionen[nach]["zeile_von"],
            "ueber_ueberschreiben": ueber or kette["ueber"],
            "von": start,
            "von_zeile": self.funktionen[start]["zeile_von"],
            "zeilen": zeilen,
        }
        if sicher:
            gesehen = {e["funktion"] for e in kette["eintraege"]} | {nach}
            weitere = [
                e for e in self.kette(nach, False)["eintraege"] if e["funktion"] not in gesehen
            ]
            if weitere:
                beleg["kette_unsicher"] = weitere
        else:
            beleg["unsicher"] = True
        funktionen = [start, nach, *(e["funktion"] for e in kette["eintraege"])]
        dateien = {f"datei:{datei_der_funktion(f)}" for f in funktionen}
        return {
            "beleg": beleg,
            "id": f"befund:markierung:{start}->{nach}",
            "knoten": sorted({start, nach} | dateien),
            "quelle": "daidalos",
            "regel": REGEL,
            "schwere": "warnung" if sicher else "hinweis",
        }


def markierungs_kette(
    knoten: list[Knoten],
    kanten: list[Kante],
    konfiguration: MarkierungsKonfiguration,
    delegiert: dict[str, set[str]] | None = None,
    warne: Warner = warne_stderr,
) -> KettenErgebnis:
    """Setzt ``markiert``/``ausnahme`` und ``metriken.delegiert_gelesen`` an den
    Funktionsknoten (in place) und liefert die Befunde ``markierung-verlassen``."""
    delegiert = delegiert or {}
    funktionen = [k for k in knoten if k["art"] == "funktion"]
    dateien = {k["pfad"]: k for k in knoten if k["art"] == "datei"}
    _warne_unbekannte(funktionen, dateien, konfiguration, warne)
    k = _Kette(funktionen, dateien, kanten, konfiguration, delegiert)

    ergebnis = KettenErgebnis()
    for f in funktionen:
        if f["id"] in k.markierung and f["id"] in k.zaehlt:
            f["markiert"] = True
            f["metriken"]["delegiert_gelesen"] = len(delegiert.get(f["id"], set()))
            ergebnis.markiert += 1
        if f["id"] in k.ausnahme:
            f["ausnahme"] = True
            ergebnis.ausnahmen += 1

    starts = sorted(i for i in k.markierung if i in k.zaehlt and i not in k.ausnahme)
    for start in starts:
        sicher = k.grenzen(start, True)
        alle = k.grenzen(start, False)
        for nach, (zeilen, ueber) in sorted(sicher.items()):
            ergebnis.befunde.append(k.befund(start, nach, zeilen, ueber, True))
            ergebnis.grenzen_sicher += 1
        for nach, (zeilen, ueber) in sorted(alle.items()):
            if nach in sicher:
                continue
            ergebnis.befunde.append(k.befund(start, nach, zeilen, ueber, False))
            ergebnis.grenzen_unsicher += 1
    return ergebnis


def _warne_unbekannte(
    funktionen: list[Knoten],
    dateien: dict[str, Knoten],
    konfiguration: MarkierungsKonfiguration,
    warne: Warner,
) -> None:
    """Warnung für konfigurierte Namen, die im Code nirgends (sicher aufgelöst) vorkommen."""
    vorhanden: set[str] = set()
    for f in funktionen:
        vorhanden |= _sichere_namen(f.get("annotationen"))
    for d in dateien.values():
        vorhanden |= _sichere_namen(d.get("annotationen"))
        for klasse in d.get("klassen", []):
            vorhanden |= _sichere_namen(klasse.get("annotationen"))
    for schluessel, namen in (
        ("annotationen", konfiguration.annotationen),
        ("ausnahmen", konfiguration.ausnahmen),
    ):
        for name in namen:
            if name not in vorhanden:
                warne(f"[markierungen].{schluessel}: {name} wird im Code nirgends verwendet")
