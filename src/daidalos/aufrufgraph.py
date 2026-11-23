"""Aufrufgraph: Funktionsknoten und ``ruft``-Kanten aus den rohen Aufrufen des Kotlin-Adapters.

Die Auflösung folgt den Schritten in ``docs/datenformat.md`` (Abschnitt Aufrufgraph). Was sich
nicht eindeutig auflösen lässt, wird als unsicher markiert und nie geraten: Eine falsche sichere
Kante wiegt schwerer als eine unsichere.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from daidalos.adapter.jni import CFunktion
from daidalos.adapter.kotlin import Import
from daidalos.adapter.kotlin_funktionen import (
    Aufruf,
    Empfaenger,
    FunktionenDatei,
    FunktionRoh,
    KlasseRoh,
    Parameter,
    Rahmen,
    typ_basis,
)

PRODUKTIV = "produktiv"
TEST = "test"
MAX_KANDIDATEN = 5
UNAUFGELOEST_NAMEN = 10

Knoten = dict[str, Any]
Kante = dict[str, Any]


# ---------------------------------------------------------------- Eingaben


@dataclass
class Quelle:
    """Eine Kotlin-Datei mit allem, was die Auflösung braucht."""

    pfad: str
    paket: str
    container: str
    rolle: str
    quellsatz: str | None
    importe: list[Import]
    inhalt: FunktionenDatei
    # (JVM-Klasse relativ zum Paket, Name, Zeile) der ``external fun``
    externe: list[tuple[str, str, int]] = field(default_factory=list)
    fremd: bool = False


@dataclass
class CQuelle:
    pfad: str
    rolle: str
    quellsatz: str | None
    funktionen: list[CFunktion]
    # (JVM-Klasse mit Paket, Methode) je C-Funktion, ``None`` bei unlesbarem Namen
    namen: dict[str, tuple[str, str] | None]


# ---------------------------------------------------------------- Index


@dataclass(eq=False)
class FInfo:
    quelle: Quelle | CQuelle
    behaelter: str
    name: str
    parameter: list[Parameter]
    erweiterung: str | None
    sichtbarkeit: str
    modifikatoren: list[str]
    roh: FunktionRoh | None
    implizit: bool = False
    zeile_von: int = 0
    zeile_bis: int = 0
    id: str = ""
    benutzt: bool = True  # implizite Konstruktoren erst, wenn ein Aufruf sie trifft

    @property
    def stelligkeit(self) -> int:
        return len(self.parameter)

    @property
    def voll(self) -> str:
        paket = self.quelle.paket if isinstance(self.quelle, Quelle) else ""
        teile = [t for t in (paket, self.behaelter) if t]
        return ".".join([*teile, self.name])

    def passt(self, anzahl: int | None) -> bool:
        if anzahl is None:
            return True
        pflicht = sum(1 for p in self.parameter if not p.vorgabe and not p.vararg)
        if anzahl < pflicht:
            return False
        return any(p.vararg for p in self.parameter) or anzahl <= len(self.parameter)

    def typen(self) -> tuple[str, ...]:
        return tuple(p.typ or "?" for p in self.parameter)


@dataclass(eq=False)
class KInfo:
    quelle: Quelle
    roh: KlasseRoh
    voll: str
    funktionen: dict[str, list[FInfo]] = field(default_factory=lambda: defaultdict(list))
    _obertypen: list[KInfo] | None = None
    offen: bool = False  # mindestens ein Obertyp ist nicht intern aufgelöst

    @property
    def kette(self) -> str:
        return self.roh.name


@dataclass(frozen=True)
class Treffer:
    ziel: FInfo
    sicher: bool
    herkunft: str
    grund: str | None


@dataclass
class Ergebnis:
    """Ausgang einer Auflösung: Treffer, extern, unaufgelöst, lokal oder Wert."""

    treffer: list[Treffer] = field(default_factory=list)
    art: str = "intern"  # intern, extern, unaufgeloest, lokal, wert
    grund: str | None = None


_EXTERN = "extern"
_UNBEKANNT = "unbekannt"


@dataclass
class Typ:
    """Ergebnis einer Typauflösung."""

    art: str  # intern, extern, unbekannt
    klassen: list[KInfo] = field(default_factory=list)
    basis: str | None = None  # bei extern: Name wie geschrieben
    objekt: bool = False  # Empfänger ist der Klassenname selbst (Objekt, Companion)
    voll: str | None = None  # bei extern über Import: voller Name


def _ist_test_quellsatz(quellsatz: str | None) -> bool:
    return quellsatz is not None and ("test" in quellsatz or "Test" in quellsatz)


def quellsatz_sichtbar(von: str | None, ziel: str | None) -> bool:
    """Ob Code im Quellsatz ``von`` Deklarationen aus ``ziel`` desselben Moduls sieht."""
    if von is None or ziel is None or von == ziel:
        return True
    if ziel == "commonMain":
        return True
    if _ist_test_quellsatz(von):
        if ziel in {"commonTest", "main"}:
            return True
        stamm = von.replace("Test", "").replace("test", "")
        if ziel == f"{stamm}Main" or (stamm == "" and ziel == "main"):
            return True
        return von == "test" and ziel == "main"
    return False


class Aufrufgraph:
    def __init__(
        self,
        quellen: list[Quelle],
        c_quellen: list[CQuelle],
        abhaengig: dict[str, set[str]] | None = None,
    ) -> None:
        # Modul-Id → Module, von denen es laut Gradle (transitiv) abhängt; ``None``: alle sichtbar
        self.abhaengig = abhaengig
        self.quellen = sorted(quellen, key=lambda q: q.pfad)
        self.c_quellen = sorted(c_quellen, key=lambda q: q.pfad)
        self.klassen: dict[str, list[KInfo]] = defaultdict(list)
        self.klassen_je_datei: dict[tuple[str, str], KInfo] = {}
        self.funktionen: list[FInfo] = []
        self.je_voll: dict[str, list[FInfo]] = defaultdict(list)
        # (Container, Paket) → Name → oberste Funktionen ohne Erweiterung
        self.oberste: dict[tuple[str, str], dict[str, list[FInfo]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Paket → Name → oberste Funktionen ohne Erweiterung, über alle Container
        self.oberste_paket: dict[str, dict[str, list[FInfo]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.erweiterungen_paket: dict[tuple[str, str], dict[str, list[FInfo]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.erweiterungen_paket_alle: dict[str, dict[str, list[FInfo]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.alle_je_name: dict[str, list[FInfo]] = defaultdict(list)
        self.eigenschaften_paket: dict[tuple[str, str], dict[str, tuple[Quelle, str | None]]] = (
            defaultdict(dict)
        )
        self.typaliase: set[str] = set()
        self.pakete: set[str] = set()
        self.je_datei: dict[str, list[FInfo]] = defaultdict(list)
        self._baue_index()

    # ------------------------------------------------------------ Index

    def _baue_index(self) -> None:
        for q in self.quellen:
            if q.paket:
                self.pakete.add(q.paket)
            for alias in q.inhalt.typaliase:
                self.typaliase.add(f"{q.paket}.{alias}" if q.paket else alias)
            for name, typ in q.inhalt.eigenschaften.items():
                self.eigenschaften_paket[(q.container, q.paket)].setdefault(name, (q, typ))
            for k in q.inhalt.klassen:
                voll = f"{q.paket}.{k.name}" if q.paket else k.name
                info = KInfo(q, k, voll)
                self.klassen[voll].append(info)
                self.klassen_je_datei[(q.pfad, k.name)] = info
            sekundaer: set[str] = set()
            for f in q.inhalt.funktionen:
                info_f = FInfo(
                    quelle=q,
                    behaelter=f.behaelter,
                    name=f.name,
                    parameter=f.parameter,
                    erweiterung=f.erweiterung,
                    sichtbarkeit=f.sichtbarkeit,
                    modifikatoren=f.modifikatoren,
                    roh=f,
                    zeile_von=f.zeile_von,
                    zeile_bis=f.zeile_bis,
                )
                if f.name == "<init>" and f.zeile_von != self._klassenzeile(q, f.behaelter):
                    sekundaer.add(f.behaelter)
                self._nimm_funktion(info_f)
            # implizite primäre Konstruktoren (erst bei Bedarf ausgegeben)
            for k in q.inhalt.klassen:
                if k.konstruktor_knoten or k.art not in {"klasse", "enum"}:
                    continue
                if k.primaer is None and k.name in sekundaer:
                    continue
                self._nimm_funktion(
                    FInfo(
                        quelle=q,
                        behaelter=k.name,
                        name="<init>",
                        parameter=list(k.primaer or []),
                        erweiterung=None,
                        sichtbarkeit="public",
                        modifikatoren=[],
                        roh=None,
                        implizit=True,
                        zeile_von=k.zeile,
                        zeile_bis=k.zeile,
                        benutzt=False,
                    )
                )
        for q in self.c_quellen:
            for c in q.funktionen:
                self._nimm_funktion(
                    FInfo(
                        quelle=q,
                        behaelter="",
                        name=c.name,
                        parameter=[Parameter(n, t, False, False) for n, t in c.parameter],
                        erweiterung=None,
                        sichtbarkeit="public",
                        modifikatoren=[],
                        roh=None,
                        zeile_von=c.zeile,
                        zeile_bis=c.zeile_bis or c.zeile,
                    )
                )
        self._vergib_ids()

    @staticmethod
    def _klassenzeile(q: Quelle, kette: str) -> int | None:
        for k in q.inhalt.klassen:
            if k.name == kette:
                return k.zeile
        return None

    def _nimm_funktion(self, f: FInfo) -> None:
        self.funktionen.append(f)
        self.je_datei[f.quelle.pfad].append(f)
        if not isinstance(f.quelle, Quelle):
            return
        q = f.quelle
        self.je_voll[f.voll].append(f)
        self.alle_je_name[f.name].append(f)
        if f.behaelter:
            info = self.klassen_je_datei.get((q.pfad, f.behaelter))
            if info is not None:
                info.funktionen[f.name].append(f)
        elif f.erweiterung is not None:
            self.erweiterungen_paket[(q.container, q.paket)][f.name].append(f)
            self.erweiterungen_paket_alle[q.paket][f.name].append(f)
        else:
            self.oberste[(q.container, q.paket)][f.name].append(f)
            self.oberste_paket[q.paket][f.name].append(f)

    def _vergib_ids(self) -> None:
        for pfad, liste in self.je_datei.items():
            basis: dict[str, list[FInfo]] = defaultdict(list)
            for f in liste:
                teile = f"{f.behaelter}." if f.behaelter else ""
                erw = f"[{f.erweiterung}]" if f.erweiterung else ""
                basis[f"funktion:{pfad}#{teile}{erw}{f.name}/{f.stelligkeit}"].append(f)
            for kern, gruppe in basis.items():
                if len(gruppe) == 1:
                    gruppe[0].id = kern
                    continue
                mit_typen: dict[str, list[FInfo]] = defaultdict(list)
                for f in gruppe:
                    mit_typen[f"{kern}({','.join(f.typen())})"].append(f)
                for kern_typ, rest in mit_typen.items():
                    if len(rest) == 1:
                        rest[0].id = kern_typ
                    else:
                        for f in rest:
                            f.id = f"{kern_typ}@{f.zeile_von}"

    # ------------------------------------------------------------ Sichtbarkeit

    def sichtbar(self, von: Quelle, ziel: Quelle | CQuelle) -> bool:
        """Produktiv sieht keinen Test; im selben Modul gelten die Quellsätze, zwischen Modulen
        die Gradle-Abhängigkeiten (Ordner außerhalb von Modulen sehen alles)."""
        if von.rolle == PRODUKTIV and ziel.rolle == TEST:
            return False
        if not isinstance(ziel, Quelle):
            return True
        if von.container == ziel.container:
            return quellsatz_sichtbar(von.quellsatz, ziel.quellsatz)
        if (
            self.abhaengig is not None
            and von.container.startswith("modul:")
            and ziel.container.startswith("modul:")
        ):
            return ziel.container in self.abhaengig.get(von.container, set())
        return True

    def _f_sichtbar(self, von: Quelle, f: FInfo) -> bool:
        if f.sichtbarkeit == "private" and f.quelle.pfad != von.pfad:
            return False
        return self.sichtbar(von, f.quelle)

    def _k_sichtbar(self, von: Quelle, liste: list[KInfo]) -> list[KInfo]:
        sichtbar = [k for k in liste if self.sichtbar(von, k.quelle)]
        if len(sichtbar) > 1:
            # ``expect``/``actual``: die ``actual``-Klasse vertritt die ``expect``-Klasse
            actual = [k for k in sichtbar if "actual" in k.roh.modifikatoren]
            if actual and len(actual) < len(sichtbar):
                sichtbar = [k for k in sichtbar if "expect" not in k.roh.modifikatoren]
        return sichtbar

    # ------------------------------------------------------------ Typen

    def loese_typ(self, typ: str | None, q: Quelle, kette: str = "") -> Typ:
        """Typ wie geschrieben → Klassen. ``kette``: Klassenkette des Kontexts (verschachtelt)."""
        basis = typ_basis(typ)
        if basis is None:
            return Typ(_UNBEKANNT if typ is None else _EXTERN, basis=None)
        teile = basis.split(".")
        erster = teile[0]
        klassen: list[KInfo] | None = None
        voll_extern: str | None = None
        # 1. verschachtelte Klassen der umgebenden Klassen, von innen nach außen
        if kette:
            stufen = kette.split(".")
            for i in range(len(stufen), 0, -1):
                kandidat = ".".join([*stufen[:i], erster])
                info = self.klassen_je_datei.get((q.pfad, kandidat))
                if info is not None:
                    klassen = [info]
                    break
                # verschachtelte Klassen in Obertypen der umgebenden Klasse
                umgebend = self.klassen_je_datei.get((q.pfad, ".".join(stufen[:i])))
                if umgebend is not None:
                    for ober in self.obertypen(umgebend):
                        treffer = self.klassen.get(f"{ober.voll}.{erster}")
                        if treffer:
                            klassen = self._k_sichtbar(q, treffer)
                            break
                    if klassen:
                        break
        # 2. Klassen der eigenen Datei auf oberster Ebene
        if klassen is None:
            info = self.klassen_je_datei.get((q.pfad, erster))
            if info is not None:
                klassen = [info]
        # 3. Importe und Aliase
        if klassen is None:
            for imp in q.importe:
                if not imp.stern and imp.sichtbarer_name == erster:
                    treffer = self.klassen.get(imp.name)
                    if treffer:
                        klassen = self._k_sichtbar(q, treffer)
                    else:
                        voll_extern = imp.name
                    break
        # 4. gleiches Paket im selben Modul
        if klassen is None and voll_extern is None:
            voll = f"{q.paket}.{erster}" if q.paket else erster
            treffer = [k for k in self.klassen.get(voll, []) if k.quelle.container == q.container]
            if treffer:
                klassen = self._k_sichtbar(q, treffer)
        # 5. Stern-Importe interner Pakete
        if klassen is None and voll_extern is None:
            for imp in q.importe:
                if imp.stern and imp.name in self.pakete:
                    treffer = self.klassen.get(f"{imp.name}.{erster}")
                    if treffer:
                        klassen = self._k_sichtbar(q, treffer)
                        break
        # 6. voll qualifiziert
        if klassen is None and voll_extern is None and len(teile) > 1:
            for laenge in range(len(teile) - 1, 0, -1):
                paket = ".".join(teile[:laenge])
                if paket in self.pakete:
                    treffer = self.klassen.get(".".join(teile[: laenge + 1]))
                    if treffer:
                        klassen = self._k_sichtbar(q, treffer)
                        teile = teile[laenge:]
                    break
        if klassen is None:
            alias = f"{q.paket}.{erster}" if q.paket else erster
            if alias in self.typaliase:
                return Typ(_UNBEKANNT)
            return Typ(_EXTERN, basis=basis, voll=voll_extern)
        if not klassen:
            return Typ(_UNBEKANNT)
        for teil in teile[1:]:
            weiter: list[KInfo] = []
            for k in klassen:
                weiter.extend(self.klassen.get(f"{k.voll}.{teil}", []))
            if not weiter:
                return Typ(_UNBEKANNT)
            klassen = self._k_sichtbar(q, weiter)
        return Typ("intern", klassen=klassen)

    def obertypen(self, k: KInfo) -> list[KInfo]:
        if k._obertypen is None:
            k._obertypen = []
            umgebend = k.kette.rsplit(".", 1)[0] if "." in k.kette else ""
            for ober in k.roh.obertypen:
                typ = self.loese_typ(ober, k.quelle, umgebend)
                if typ.art == "intern":
                    k._obertypen.extend(t for t in typ.klassen if t is not k)
                else:
                    k.offen = True
        return k._obertypen

    def alle_obertypen(self, klassen: list[KInfo]) -> list[KInfo]:
        """Die Klassen selbst und alle internen Obertypen, Breite zuerst."""
        gesehen: list[KInfo] = []
        offen = list(klassen)
        while offen:
            k = offen.pop(0)
            if k in gesehen:
                continue
            gesehen.append(k)
            offen.extend(self.obertypen(k))
        return gesehen

    def ist_offen(self, klassen: list[KInfo]) -> bool:
        """Ob einer der Typen einen nicht intern aufgelösten Obertyp hat."""
        for k in self.alle_obertypen(klassen):
            self.obertypen(k)
            if k.offen:
                return True
        return False

    def companion(self, k: KInfo) -> KInfo | None:
        if k.roh.companion is None:
            return None
        return self.klassen_je_datei.get((k.quelle.pfad, k.roh.companion))

    # ------------------------------------------------------------ Mitglieder

    def mitglieder(self, klassen: list[KInfo], name: str, von: Quelle) -> list[FInfo]:
        """Funktionen ``name`` in den Klassen und ihren Obertypen; überschriebene nur einmal."""
        ergebnis: list[FInfo] = []
        signaturen: set[tuple[str, int, tuple[str, ...]]] = set()
        for k in self.alle_obertypen(klassen):
            for f in k.funktionen.get(name, []):
                if f.erweiterung is not None or not self._f_sichtbar(von, f):
                    continue
                signatur = (f.name, f.stelligkeit, f.typen())
                if signatur in signaturen:
                    continue
                signaturen.add(signatur)
                ergebnis.append(f)
        return ergebnis

    def eigenschaft(self, klassen: list[KInfo], name: str) -> tuple[bool, str | None, KInfo | None]:
        """(gefunden, Typ, Klasse) einer Eigenschaft in den Klassen und ihren Obertypen."""
        for k in self.alle_obertypen(klassen):
            if name in k.roh.eigenschaften:
                return True, k.roh.eigenschaften[name], k
        return False, None, None

    # ------------------------------------------------------------ Entscheidung

    def _entscheide(
        self,
        kandidaten: list[FInfo],
        anzahl: int | None,
        herkunft: str,
        zwang: str | None = None,
        referenz: bool = False,
    ) -> Ergebnis | None:
        passend = [f for f in kandidaten if f.passt(anzahl)]
        if not passend:
            return None
        # ``expect`` und passendes ``actual`` zählen als eine Funktion: das ``actual`` gilt.
        actual = {(f.voll, f.stelligkeit) for f in passend if "actual" in f.modifikatoren}
        passend = [
            f
            for f in passend
            if not ("expect" in f.modifikatoren and (f.voll, f.stelligkeit) in actual)
        ]
        herkunft = "referenz" if referenz else herkunft
        if len(passend) == 1 and zwang is None:
            return Ergebnis([Treffer(passend[0], True, herkunft, None)])
        grund = zwang or "ueberladung"
        passend.sort(key=lambda f: f.id)
        return Ergebnis([Treffer(f, False, herkunft, grund) for f in passend])

    # ------------------------------------------------------------ Erweiterungen

    def _sichtbare_erweiterungen(self, q: Quelle, name: str) -> list[FInfo]:
        ergebnis: list[FInfo] = []

        def nimm(liste: list[FInfo]) -> None:
            for f in liste:
                if f not in ergebnis and self._f_sichtbar(q, f):
                    ergebnis.append(f)

        nimm(
            [
                f
                for f in self.je_datei.get(q.pfad, [])
                if f.name == name and f.erweiterung is not None and not f.behaelter
            ]
        )
        for imp in q.importe:
            if not imp.stern and imp.sichtbarer_name == name:
                nimm([f for f in self.je_voll.get(imp.name, []) if f.erweiterung is not None])
        nimm(self.erweiterungen_paket.get((q.container, q.paket), {}).get(name, []))
        for imp in q.importe:
            if imp.stern and imp.name in self.pakete:
                nimm(self.erweiterungen_paket_alle.get(imp.name, {}).get(name, []))
        return ergebnis

    def _erweiterung(
        self, q: Quelle, name: str, anzahl: int | None, typ: Typ, referenz: bool = False
    ) -> Ergebnis | None:
        """Schritt 5: Erweiterung für einen Empfänger bekannten Typs."""
        sichtbar = [f for f in self._sichtbare_erweiterungen(q, name) if f.passt(anzahl)]
        if not sichtbar:
            return None
        passend: list[FInfo] = []
        if typ.art == "intern":
            umfang = self.alle_obertypen(typ.klassen)
            for f in sichtbar:
                assert isinstance(f.quelle, Quelle)
                ziel = self.loese_typ(f.erweiterung, f.quelle, "")
                if ziel.art == "intern" and any(k in umfang for k in ziel.klassen):
                    passend.append(f)
            if not passend and not self.ist_offen(typ.klassen):
                return None  # passt zu keiner Erweiterung, kein externer Obertyp
        elif typ.art == _EXTERN and typ.basis is not None:
            einfach = typ.basis.rsplit(".", 1)[-1]
            for f in sichtbar:
                basis = typ_basis(f.erweiterung)
                if basis is not None and basis.rsplit(".", 1)[-1] == einfach:
                    passend.append(f)
            if not passend:
                return None
        herkunft = "referenz" if referenz else "erweiterung"
        if len(passend) == 1:
            return Ergebnis([Treffer(passend[0], True, herkunft, None)])
        ziele = sorted(passend or sichtbar, key=lambda f: f.id)
        return Ergebnis([Treffer(f, False, herkunft, "erweiterung") for f in ziele])

    # ------------------------------------------------------------ Unbekannter Empfänger

    def _unbekannt(self, q: Quelle, name: str, anzahl: int | None, referenz: bool) -> Ergebnis:
        kandidaten = [
            f
            for f in self.alle_je_name.get(name, [])
            if (f.behaelter or f.erweiterung is not None)
            and f.passt(anzahl)
            and self._f_sichtbar(q, f)
            and not f.implizit
        ]
        if not kandidaten:
            return Ergebnis(art="extern")
        if len(kandidaten) > MAX_KANDIDATEN:
            return Ergebnis(art="unaufgeloest", grund="zu-viele-kandidaten")
        herkunft = "referenz" if referenz else "unbekannter-empfaenger"
        return Ergebnis(
            [
                Treffer(f, False, herkunft, "unbekannter-empfaenger")
                for f in sorted(kandidaten, key=lambda f: f.id)
            ]
        )

    # ------------------------------------------------------------ Konstruktoren

    def _konstruktoren(self, klassen: list[KInfo], q: Quelle) -> list[FInfo]:
        ergebnis: list[FInfo] = []
        for k in klassen:
            if k.roh.art not in {"klasse", "enum"}:
                continue
            ergebnis.extend(f for f in k.funktionen.get("<init>", []) if self._f_sichtbar(q, f))
        return ergebnis

    def _konstruktor(
        self, typ: Typ, q: Quelle, anzahl: int | None, referenz: bool
    ) -> Ergebnis | None:
        if typ.art != "intern":
            return None
        kandidaten = self._konstruktoren(typ.klassen, q)
        if not kandidaten:
            return None
        zwang = "ueberladung" if len(typ.klassen) > 1 else None
        return self._entscheide(kandidaten, anzahl, "konstruktor", zwang, referenz)

    # ------------------------------------------------------------ Empfänger-Ketten

    def _rahmen_typ(self, r: Rahmen, q: Quelle, f: FInfo) -> Typ | None:
        """Typ eines impliziten Empfängers; ``None`` für Lambdas ohne Empfänger."""
        if r.art == "klasse":
            info = self.klassen_je_datei.get((q.pfad, r.wert or ""))
            return Typ("intern", klassen=[info]) if info is not None else Typ(_UNBEKANNT)
        if r.art == "erweiterung":
            return self.loese_typ(r.wert, q, f.behaelter)
        if r.art == "objekt":
            klassen: list[KInfo] = []
            offen = False
            for ober in r.obertypen:
                t = self.loese_typ(ober, q, f.behaelter)
                if t.art == "intern":
                    klassen.extend(t.klassen)
                else:
                    offen = True
            if offen and not klassen:
                return Typ(_EXTERN, basis=r.obertypen[0] if r.obertypen else None)
            return Typ("intern", klassen=klassen)
        if r.art == "bereich":
            if r.empfaenger is None:
                return Typ(_EXTERN)
            return self._empfaenger_typ(r.empfaenger, q, f, ())
        return None

    def _lambda_mit_empfaenger(self, name: str | None) -> bool | None:
        """Ob das Lambda-Argument von ``name`` einen Empfänger haben kann.

        ``True``: interne Funktion mit Empfänger-Lambda; ``False``: interne Funktionen ohne;
        ``None``: keine interne Funktion dieses Namens (extern, Empfänger unbekannt).
        """
        kandidaten = [f for f in self.alle_je_name.get(name or "", []) if f.roh is not None]
        if not kandidaten:
            return None
        for f in kandidaten:
            for p in f.parameter:
                typ = (p.typ or "").removeprefix("suspend")
                if "->" in typ and ".(" in typ.split("->", 1)[0]:
                    return True
        return False

    def _empfaenger_typ(
        self, e: Empfaenger, q: Quelle, f: FInfo, rahmen: tuple[Rahmen, ...]
    ) -> Typ:
        """Typ des Empfängers einer Kette; ``objekt`` bei Klassen- oder Objektnamen."""
        if e.art == "this":
            return self._this_typ(e.name, q, f, rahmen or self._rahmen_von(f))
        if e.art != "kette" or e.name is None:
            return Typ(_UNBEKANNT)
        typ: Typ
        if e.herkunft in {"lokal", "parameter"}:
            typ = self.loese_typ(e.typ, q, f.behaelter) if e.typ else Typ(_UNBEKANNT)
        elif e.herkunft == "this":
            klasse = self._innerste_klasse(rahmen or self._rahmen_von(f), q)
            typ = self._eigenschafts_typ(klasse, e.name) if klasse else Typ(_UNBEKANNT)
        else:
            typ = self._freier_name(e.name, q, f, rahmen or self._rahmen_von(f))
        for teil in e.rest:
            typ = self._weiter(typ, teil, q)
            if typ.art != "intern":
                return typ
        return typ

    def _rahmen_von(self, f: FInfo) -> tuple[Rahmen, ...]:
        if not f.behaelter:
            return ()
        teile = f.behaelter.split(".")
        return tuple(Rahmen("klasse", wert=".".join(teile[:i])) for i in range(len(teile), 0, -1))

    def _innerste_klasse(self, rahmen: tuple[Rahmen, ...], q: Quelle) -> list[KInfo] | None:
        for r in rahmen:
            if r.art == "klasse":
                info = self.klassen_je_datei.get((q.pfad, r.wert or ""))
                return [info] if info is not None else None
        return None

    def _eigenschafts_typ(self, klassen: list[KInfo], name: str) -> Typ:
        gefunden, typ, klasse = self.eigenschaft(klassen, name)
        if not gefunden or typ is None or klasse is None:
            return Typ(_UNBEKANNT)
        umgebend = klasse.kette
        return self.loese_typ(typ, klasse.quelle, umgebend)

    def _this_typ(self, label: str | None, q: Quelle, f: FInfo, rahmen: tuple[Rahmen, ...]) -> Typ:
        for r in rahmen:
            if r.art == "lambda":
                if label is None and self._lambda_mit_empfaenger(r.wert) is not False:
                    return Typ(_UNBEKANNT)
                continue
            if label is not None:
                if r.art == "klasse" and (r.wert or "").rsplit(".", 1)[-1] == label:
                    return self._rahmen_typ(r, q, f) or Typ(_UNBEKANNT)
                continue
            typ = self._rahmen_typ(r, q, f)
            if typ is not None:
                return typ
        if label is not None:
            return Typ(_UNBEKANNT)
        return Typ(_UNBEKANNT)

    def _freier_name(self, name: str, q: Quelle, f: FInfo, rahmen: tuple[Rahmen, ...]) -> Typ:
        # Eigenschaften impliziter Empfänger
        for r in rahmen:
            typ = self._rahmen_typ(r, q, f) if r.art != "lambda" else None
            if typ is None:
                if r.art == "lambda" and self._lambda_mit_empfaenger(r.wert):
                    return Typ(_UNBEKANNT)
                continue
            if typ.art == "intern":
                gefunden, _, _ = self.eigenschaft(typ.klassen, name)
                if gefunden:
                    return self._eigenschafts_typ(typ.klassen, name)
            elif typ.art == _UNBEKANNT and name[:1].islower():
                return Typ(_UNBEKANNT)
        # Eigenschaften der obersten Ebene
        if name in q.inhalt.eigenschaften:
            return self._oberste_eigenschaft(q, q.inhalt.eigenschaften[name])
        for imp in q.importe:
            if not imp.stern and imp.sichtbarer_name == name:
                paket, _, kurz = imp.name.rpartition(".")
                for (_, p), werte in self.eigenschaften_paket.items():
                    if p == paket and kurz in werte:
                        quelle, typ_text = werte[kurz]
                        if self.sichtbar(q, quelle):
                            return self._oberste_eigenschaft(quelle, typ_text)
        eigene = self.eigenschaften_paket.get((q.container, q.paket), {})
        if name in eigene and self.sichtbar(q, eigene[name][0]):
            quelle, typ_text = eigene[name]
            return self._oberste_eigenschaft(quelle, typ_text)
        # Klassen- oder Objektname
        typ = self.loese_typ(name, q, f.behaelter)
        if typ.art == "intern":
            typ.objekt = True
            return typ
        # Paketpräfix ``de.x.Klasse.f()`` wird in ``_weiter`` fortgesetzt
        if any(p == name or p.startswith(name + ".") for p in self.pakete):
            return Typ("paket", basis=name)
        if name[:1].isupper():
            return typ  # extern, z. B. ``Math`` oder ``Log``
        return Typ(_UNBEKANNT)

    def _oberste_eigenschaft(self, quelle: Quelle, typ_text: str | None) -> Typ:
        if typ_text is None:
            return Typ(_UNBEKANNT)
        return self.loese_typ(typ_text, quelle, "")

    def _weiter(self, typ: Typ, teil: str, q: Quelle) -> Typ:
        if typ.art == "paket":
            pfad = f"{typ.basis}.{teil}"
            if pfad in self.klassen:
                return Typ("intern", klassen=self._k_sichtbar(q, self.klassen[pfad]), objekt=True)
            if any(p == pfad or p.startswith(pfad + ".") for p in self.pakete):
                return Typ("paket", basis=pfad)
            return Typ(_UNBEKANNT)
        if typ.art != "intern":
            return Typ(_UNBEKANNT) if typ.art != _EXTERN else Typ(_EXTERN, basis=None)
        if typ.objekt:
            verschachtelt: list[KInfo] = []
            for k in typ.klassen:
                verschachtelt.extend(self.klassen.get(f"{k.voll}.{teil}", []))
            if verschachtelt:
                return Typ("intern", klassen=self._k_sichtbar(q, verschachtelt), objekt=True)
            # ``Enum.entries``: Liste der Standardbibliothek; ``Enum.EINTRAG``: die Enum-Klasse
            if all(k.roh.art == "enum" for k in typ.klassen):
                if teil == "entries":
                    return Typ(_EXTERN, basis="List")
                if all(teil in k.roh.eintraege for k in typ.klassen):
                    return Typ("intern", klassen=typ.klassen)
            # Eigenschaft eines Objekts oder des Companion
            ziele = [
                k if k.roh.art in {"objekt", "companion"} else self.companion(k)
                for k in typ.klassen
            ]
            ziele_da = [k for k in ziele if k is not None]
            return self._eigenschafts_typ(ziele_da, teil) if ziele_da else Typ(_UNBEKANNT)
        return self._eigenschafts_typ(typ.klassen, teil)

    # ------------------------------------------------------------ Auflösung

    def loese(self, a: Aufruf, f: FInfo) -> Ergebnis:
        q = f.quelle
        assert isinstance(q, Quelle)
        if a.lokal:
            return Ergebnis(art="lokal")
        if a.wert:
            return Ergebnis(art="wert")
        e = a.empfaenger
        if e.art == "ohne":
            return self._ohne_empfaenger(a, q, f)
        if e.art == "unbekannt":
            return self._unbekannt(q, a.name, a.argumente, a.referenz)
        if e.art == "super":
            return self._super(a, q, f)
        if a.name == "<init>" and e.art == "this":
            klasse = self._innerste_klasse(a.rahmen, q)
            if klasse is None:
                return Ergebnis(art="extern")
            return self._konstruktor(
                Typ("intern", klassen=klasse), q, a.argumente, False
            ) or Ergebnis(art="extern")
        typ = self._empfaenger_typ(e, q, f, a.rahmen)
        herkunft = {
            "lokal": "lokal",
            "parameter": "parameter",
            "this": "eigenschaft",
        }.get(e.herkunft or "", "eigenschaft")
        if e.art == "this":
            herkunft = "this"
        elif e.art == "kette" and e.herkunft == "frei" and e.name is not None:
            erster = typ if not e.rest else self._freier_name(e.name, q, f, a.rahmen)
            herkunft = "objekt" if erster.objekt or erster.art == "paket" else "eigenschaft"
        return self._auf_typ(typ, a, q, herkunft)

    def _auf_typ(self, typ: Typ, a: Aufruf, q: Quelle, herkunft: str) -> Ergebnis:
        name, anzahl, referenz = a.name, a.argumente, a.referenz
        if typ.art == _UNBEKANNT or typ.art == "paket":
            return self._unbekannt(q, name, anzahl, referenz)
        if typ.art == _EXTERN:
            return self._erweiterung(q, name, anzahl, typ, referenz) or Ergebnis(art="extern")
        klassen = typ.klassen
        zwang = "unbekannter-empfaenger" if len(klassen) > 1 else None
        if typ.objekt:
            if referenz and all(k.roh.art not in {"objekt", "companion"} for k in klassen):
                ziele = klassen  # ``Klasse::methode``: Mitglied der Instanz
            else:
                ziele = []
                for k in klassen:
                    if k.roh.art in {"objekt", "companion", "enum-eintrag"}:
                        ziele.append(k)
                    elif (c := self.companion(k)) is not None:
                        ziele.append(c)
            kandidaten = self.mitglieder(ziele, name, q) if ziele else []
            ergebnis = self._entscheide(kandidaten, anzahl, herkunft, zwang, referenz)
            if ergebnis is not None:
                return ergebnis
            return Ergebnis(art="extern")
        kandidaten = self.mitglieder(klassen, name, q)
        ergebnis = self._entscheide(kandidaten, anzahl, herkunft, zwang, referenz)
        if ergebnis is not None:
            return ergebnis
        return self._erweiterung(q, name, anzahl, typ, referenz) or Ergebnis(art="extern")

    def _super(self, a: Aufruf, q: Quelle, f: FInfo) -> Ergebnis:
        klasse: list[KInfo] | None = None
        for r in a.rahmen:
            if r.art == "klasse":
                klasse = self._innerste_klasse((r,), q)
                break
            if r.art == "objekt":
                t = self._rahmen_typ(r, q, f)
                if t is None or t.art != "intern":
                    return Ergebnis(art="extern")
                obertypen = t.klassen
                break
        else:
            obertypen = []
        if klasse is not None:
            info = klasse[0]
            if a.empfaenger.name is not None:
                t = self.loese_typ(a.empfaenger.name, q, info.kette)
                obertypen = t.klassen if t.art == "intern" else []
            else:
                obertypen = self.obertypen(info)
        if not obertypen:
            return Ergebnis(art="extern")
        if a.name == "<init>":
            return self._konstruktor(
                Typ("intern", klassen=obertypen), q, a.argumente, False
            ) or Ergebnis(art="extern")
        kandidaten = self.mitglieder(obertypen, a.name, q)
        return self._entscheide(kandidaten, a.argumente, "super", None, a.referenz) or Ergebnis(
            art="extern"
        )

    def _ohne_empfaenger(self, a: Aufruf, q: Quelle, f: FInfo) -> Ergebnis:
        name, anzahl, referenz = a.name, a.argumente, a.referenz
        offen = False  # ein impliziter Empfänger hat Mitglieder, die wir nicht kennen
        unbekannt = False  # ein impliziter Empfänger hat einen unbekannten Typ
        implizite: list[KInfo] = []
        for r in a.rahmen:
            if r.art == "objekt" and name in r.namen:
                return Ergebnis(art="lokal")
            if r.art == "lambda":
                mit = self._lambda_mit_empfaenger(r.wert)
                if mit is None:
                    offen = True
                elif mit:
                    unbekannt = True
                continue
            typ = self._rahmen_typ(r, q, f)
            if typ is None:
                continue
            if typ.art == _UNBEKANNT:
                unbekannt = True
                continue
            if typ.art == _EXTERN:
                offen = True
                continue
            implizite.extend(typ.klassen)
            kandidaten = self.mitglieder(typ.klassen, name, q)
            if r.art == "klasse":
                c = self.companion(typ.klassen[0]) if typ.klassen else None
                if c is not None:
                    kandidaten += [x for x in self.mitglieder([c], name, q) if x not in kandidaten]
            zwang = "unbekannter-empfaenger" if unbekannt else None
            ergebnis = self._entscheide(kandidaten, anzahl, "this", zwang, referenz)
            if ergebnis is not None:
                return ergebnis
            gefunden, _, _ = self.eigenschaft(typ.klassen, name)
            if gefunden and not referenz:
                return Ergebnis(art="wert")
            if self.ist_offen(typ.klassen) or (r.art == "objekt" and typ.art != "intern"):
                offen = True
        # Erweiterungen mit einem impliziten Empfänger
        if implizite:
            typ = Typ("intern", klassen=implizite)
            sichtbar = [x for x in self._sichtbare_erweiterungen(q, name) if x.passt(anzahl)]
            if sichtbar:
                umfang = self.alle_obertypen(implizite)
                passend = []
                for x in sichtbar:
                    assert isinstance(x.quelle, Quelle)
                    t = self.loese_typ(x.erweiterung, x.quelle, "")
                    if t.art == "intern" and any(k in umfang for k in t.klassen):
                        passend.append(x)
                if passend:
                    zwang = "unbekannter-empfaenger" if unbekannt else None
                    if len(passend) > 1:
                        zwang = zwang or "erweiterung"
                    return self._entscheide(passend, anzahl, "erweiterung", zwang, referenz) or (
                        Ergebnis(art="extern")
                    )

        def zwang_aussen() -> str | None:
            if unbekannt:
                return "unbekannter-empfaenger"
            if offen and name[:1].islower():
                return "kleingeschrieben"
            return None

        def nur_oberste(liste: list[FInfo]) -> list[FInfo]:
            return [x for x in liste if self._f_sichtbar(q, x)]

        # dieselbe Datei
        eigene = nur_oberste(
            [
                x
                for x in self.je_datei.get(q.pfad, [])
                if not x.behaelter and x.erweiterung is None and x.name == name
            ]
        )
        ergebnis = self._entscheide(eigene, anzahl, "ohne-empfaenger", zwang_aussen(), referenz)
        if ergebnis is not None:
            return ergebnis
        # Importe und Aliase
        for imp in q.importe:
            if imp.stern or imp.sichtbarer_name != name:
                continue
            kandidaten = nur_oberste(
                [x for x in self.je_voll.get(imp.name, []) if x.erweiterung is None]
            )
            ergebnis = self._entscheide(kandidaten, anzahl, "import", zwang_aussen(), referenz)
            if ergebnis is not None:
                return ergebnis
            klassen = self.klassen.get(imp.name)
            if klassen:
                typ = Typ("intern", klassen=self._k_sichtbar(q, klassen))
                return self._konstruktor(typ, q, anzahl, referenz) or Ergebnis(art="extern")
        # gleiches Paket im selben Modul
        kandidaten = nur_oberste(self.oberste.get((q.container, q.paket), {}).get(name, []))
        ergebnis = self._entscheide(kandidaten, anzahl, "gleiches-paket", zwang_aussen(), referenz)
        if ergebnis is not None:
            return ergebnis
        # Stern-Importe
        for imp in q.importe:
            if imp.stern and imp.name in self.pakete:
                kandidaten = nur_oberste(self.oberste_paket.get(imp.name, {}).get(name, []))
                ergebnis = self._entscheide(kandidaten, anzahl, "import", zwang_aussen(), referenz)
                if ergebnis is not None:
                    return ergebnis
        # Konstruktor
        typ = self.loese_typ(name, q, f.behaelter)
        ergebnis = self._konstruktor(typ, q, anzahl, referenz)
        if ergebnis is not None:
            if zwang_aussen() == "unbekannter-empfaenger":
                return Ergebnis(
                    [
                        Treffer(t.ziel, False, t.herkunft, "unbekannter-empfaenger")
                        for t in ergebnis.treffer
                    ]
                )
            return ergebnis
        return Ergebnis(art="extern")

    # ------------------------------------------------------------ Ausgabe

    def baue(self) -> AufrufErgebnis:
        kanten_belege: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        extern: Counter[str] = Counter()
        unaufgeloest: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
        statistik: Counter[str] = Counter()
        nach_id = {f.id: f for f in self.funktionen}
        for f in self.funktionen:
            if f.roh is None or not isinstance(f.quelle, Quelle):
                continue
            for a in f.roh.aufrufe:
                ergebnis = self.loese(a, f)
                if ergebnis.art == "intern" and ergebnis.treffer:
                    for t in ergebnis.treffer:
                        t.ziel.benutzt = True
                        beleg: dict[str, Any] = {
                            "herkunft": t.herkunft,
                            "sicher": t.sicher,
                            "zeile": a.zeile,
                        }
                        if t.grund is not None:
                            beleg["grund"] = t.grund
                        kanten_belege[(f.id, t.ziel.id)].append(beleg)
                    sicher = any(t.sicher for t in ergebnis.treffer)
                    statistik["intern-sicher" if sicher else "intern-unsicher"] += 1
                    if not sicher:
                        statistik[f"unsicher:{ergebnis.treffer[0].grund}"] += 1
                elif ergebnis.art == "unaufgeloest":
                    unaufgeloest[f.quelle.pfad][(a.name, ergebnis.grund or "")] += 1
                    statistik["unaufgeloest"] += 1
                    statistik[f"unaufgeloest:{ergebnis.grund}"] += 1
                elif ergebnis.art in {"lokal", "wert"}:
                    statistik[ergebnis.art] += 1
                else:
                    extern[f.id] += 1
                    statistik["extern"] += 1
        return AufrufErgebnis(self, nach_id, kanten_belege, extern, unaufgeloest, statistik)


@dataclass
class AufrufErgebnis:
    graph: Aufrufgraph
    nach_id: dict[str, FInfo]
    kanten_belege: dict[tuple[str, str], list[dict[str, Any]]]
    extern: Counter[str]
    unaufgeloest: dict[str, Counter[tuple[str, str]]]
    statistik: Counter[str]


# ---------------------------------------------------------------- JSON


def _kanten_id(art: str, von: str, nach: str, rolle: str | None = None) -> str:
    basis = f"kante:{art}:{von}->{nach}"
    return f"{basis}:{rolle}" if rolle else basis


def _annotationen(graph: Aufrufgraph, q: Quelle, namen: list[Any]) -> list[dict[str, Any]]:
    ergebnis: set[tuple[str, bool]] = set()
    for a in namen:
        ergebnis.add(loese_annotation(graph, q, a.name))
    return [{"name": n, "sicher": s} for n, s in sorted(ergebnis)]


def loese_annotation(graph: Aufrufgraph, q: Quelle, name: str) -> tuple[str, bool]:
    """Voller Name einer Annotation und ob er sicher ist."""
    teile = name.split(".")
    for imp in q.importe:
        if not imp.stern and imp.sichtbarer_name == teile[0]:
            return ".".join([imp.name, *teile[1:]]), True
    if len(teile) > 1:
        if teile[0][:1].islower():
            return name, True  # voll qualifiziert geschrieben
        typ = graph.loese_typ(name, q, "")
        if typ.art == "intern" and len(typ.klassen) == 1:
            return typ.klassen[0].voll, True
        return name, False
    eigen = graph.klassen_je_datei.get((q.pfad, name))
    if eigen is not None:
        return eigen.voll, True
    voll = f"{q.paket}.{name}" if q.paket else name
    if any(k.quelle.container == q.container for k in graph.klassen.get(voll, [])):
        return voll, True
    for imp in q.importe:
        if imp.stern and imp.name in graph.pakete and f"{imp.name}.{name}" in graph.klassen:
            return f"{imp.name}.{name}", True
    return name, False


def _obertyp_json(graph: Aufrufgraph, k: KInfo, ober: str) -> dict[str, Any]:
    umgebend = k.kette.rsplit(".", 1)[0] if "." in k.kette else ""
    typ = graph.loese_typ(ober, k.quelle, umgebend)
    if typ.art == "intern" and len(typ.klassen) >= 1:
        voll: str | None = typ.klassen[0].voll
    else:
        voll = typ.voll
    return {"name": ober, "voll": voll}


def _parameter_json(p: Parameter) -> dict[str, Any]:
    return {"name": p.name, "typ": p.typ, "vararg": p.vararg, "vorgabe": p.vorgabe}


def _hash_text(text: str) -> str:
    inhalt = text.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(inhalt.encode("utf-8")).hexdigest()


@dataclass
class Messung:
    knoten: list[Knoten]
    kanten: list[Kante]
    befunde: list[dict[str, Any]]
    # Datei-Pfad → zusätzliche Felder des Datei-Knotens
    datei_felder: dict[str, dict[str, Any]]
    statistik: Counter[str]


def miss(
    quellen: list[Quelle],
    c_quellen: list[CQuelle],
    datei_ids: dict[str, str],
    abhaengig: dict[str, set[str]] | None = None,
) -> Messung:
    """Funktionsknoten, Kanten und Befunde aus allen Kotlin- und C-Dateien."""
    graph = Aufrufgraph(quellen, c_quellen, abhaengig)
    ergebnis = graph.baue()
    knoten: list[Knoten] = []
    kanten: list[Kante] = []
    befunde: list[dict[str, Any]] = []
    datei_felder: dict[str, dict[str, Any]] = defaultdict(dict)

    # ruft
    rein_sicher: dict[str, set[str]] = defaultdict(set)
    raus_sicher: dict[str, set[str]] = defaultdict(set)
    rein_alle: dict[str, set[str]] = defaultdict(set)
    raus_alle: dict[str, set[str]] = defaultdict(set)
    for (von, nach), belege in sorted(ergebnis.kanten_belege.items()):
        quelle = ergebnis.nach_id[von].quelle
        rolle = quelle.rolle
        belege.sort(key=lambda b: (b["zeile"], b["herkunft"], not b["sicher"], b.get("grund", "")))
        sicher = any(b["sicher"] for b in belege)
        kanten.append(
            {
                "art": "ruft",
                "beleg": belege,
                "gewicht": len(belege),
                "id": _kanten_id("ruft", von, nach, rolle),
                "nach": nach,
                "rolle": rolle,
                "sicher": sicher,
                "von": von,
            }
        )
        if rolle == PRODUKTIV and von != nach:
            raus_alle[von].add(nach)
            rein_alle[nach].add(von)
            if sicher:
                raus_sicher[von].add(nach)
                rein_sicher[nach].add(von)

    # ueberschreibt und actual
    for f in graph.funktionen:
        q = f.quelle
        if not isinstance(q, Quelle) or f.roh is None:
            continue
        if "override" in f.modifikatoren and f.behaelter:
            kanten.extend(_ueberschreibt(graph, f))
        if "actual" in f.modifikatoren:
            ziele = [
                x
                for x in graph.je_voll.get(f.voll, [])
                if "expect" in x.modifikatoren
                and x.stelligkeit == f.stelligkeit
                and isinstance(x.quelle, Quelle)
                and x.quelle.container == q.container
                and x.erweiterung == f.erweiterung
            ]
            for x in sorted(ziele, key=lambda x: x.id):
                kanten.append(
                    {
                        "art": "actual",
                        "gewicht": 1,
                        "id": _kanten_id("actual", f.id, x.id),
                        "nach": x.id,
                        "rolle": q.rolle,
                        "sicher": len(ziele) == 1,
                        "von": f.id,
                    }
                )

    # jni auf Funktionsebene
    kanten.extend(_jni(graph))

    # Knoten
    for f in sorted(graph.funktionen, key=lambda x: x.id):
        if not f.benutzt:
            continue
        q = f.quelle
        metriken = {
            "externe_aufrufe": ergebnis.extern.get(f.id, 0),
            "fan_in": len(rein_sicher[f.id]),
            "fan_in_unsicher": len(rein_alle[f.id]),
            "fan_out": len(raus_sicher[f.id]),
            "fan_out_unsicher": len(raus_alle[f.id]),
        }
        k: Knoten = {
            "art": "funktion",
            "behaelter": f.behaelter,
            "datei": q.pfad,
            "erweiterung": f.erweiterung,
            "id": f.id,
            "modifikatoren": f.modifikatoren,
            "name": f.name,
            "parameter": [_parameter_json(p) for p in f.parameter],
            "rolle": q.rolle,
            "sichtbarkeit": f.sichtbarkeit,
            "stelligkeit": f.stelligkeit,
            "zeile_bis": f.zeile_bis,
            "zeile_von": f.zeile_von,
        }
        if q.quellsatz is not None:
            k["quellsatz"] = q.quellsatz
        if isinstance(q, Quelle):
            k["sprache"] = "kotlin"
            k["annotationen"] = _annotationen(graph, q, f.roh.annotationen if f.roh else [])
            if f.roh is not None:
                k["hash"] = f.roh.hash
                metriken["zeilen"] = f.roh.zeilen
                metriken["komplexitaet"] = f.roh.komplexitaet
            else:
                metriken["zeilen"] = 0
                metriken["komplexitaet"] = 1
            if f.implizit:
                k["implizit"] = True
        else:
            k["sprache"] = "c"
            k["annotationen"] = []
            c = next(x for x in q.funktionen if x.name == f.name)
            k["hash"] = _hash_text(c.text)
            metriken["zeilen"] = len(
                [z for z in c.text.replace("\r\n", "\n").split("\n") if z.strip()]
            )
            metriken["komplexitaet"] = None
        k["metriken"] = metriken
        knoten.append(k)
        datei_id = datei_ids[q.pfad]
        kanten.append(
            {
                "art": "enthaelt",
                "id": _kanten_id("enthaelt", datei_id, f.id),
                "nach": f.id,
                "von": datei_id,
            }
        )
        felder = datei_felder[q.pfad]
        felder["funktionen"] = felder.get("funktionen", 0) + 1

    # Datei-Felder: Klassen und Annotationen
    for q in graph.quellen:
        felder = datei_felder[q.pfad]
        felder.setdefault("funktionen", 0)
        felder["annotationen"] = _annotationen(graph, q, q.inhalt.datei_annotationen)
        klassen = []
        for kr in q.inhalt.klassen:
            info = graph.klassen_je_datei[(q.pfad, kr.name)]
            klassen.append(
                {
                    "annotationen": _annotationen(graph, q, kr.annotationen),
                    "art": kr.art,
                    "name": kr.name,
                    "obertypen": [_obertyp_json(graph, info, o) for o in kr.obertypen],
                    "zeile": kr.zeile,
                }
            )
        felder["klassen"] = sorted(klassen, key=lambda k: (k["name"], k["zeile"]))
    for cq in graph.c_quellen:
        datei_felder[cq.pfad].setdefault("funktionen", 0)

    # Befund unaufgelöst, Art aufruf
    fremd = {q.pfad for q in graph.quellen if q.fremd}
    for pfad, zaehler in sorted(ergebnis.unaufgeloest.items()):
        if pfad in fremd:
            continue
        namen = sorted(zaehler.items(), key=lambda e: (-e[1], e[0][0], e[0][1]))
        befunde.append(
            {
                "beleg": {
                    "anzahl": sum(zaehler.values()),
                    "art": "aufruf",
                    "namen": [
                        {"anzahl": anzahl, "grund": grund, "name": name}
                        for (name, grund), anzahl in namen[:UNAUFGELOEST_NAMEN]
                    ],
                },
                "id": f"befund:unaufgeloest:aufruf:{pfad}",
                "knoten": [datei_ids[pfad]],
                "quelle": "daidalos",
                "regel": "unaufgeloest",
                "schwere": "hinweis",
            }
        )
    return Messung(knoten, kanten, befunde, dict(datei_felder), ergebnis.statistik)


def _ueberschreibt(graph: Aufrufgraph, f: FInfo) -> list[Kante]:
    q = f.quelle
    assert isinstance(q, Quelle)
    info = graph.klassen_je_datei.get((q.pfad, f.behaelter))
    if info is None:
        return []
    # Breite zuerst; je Pfad die nächste passende Funktion
    gefunden: list[FInfo] = []
    gesehen: set[int] = set()
    offen = list(graph.obertypen(info))
    while offen:
        k = offen.pop(0)
        if id(k) in gesehen:
            continue
        gesehen.add(id(k))
        passend = [
            x
            for x in k.funktionen.get(f.name, [])
            if x.stelligkeit == f.stelligkeit and x.erweiterung == f.erweiterung
        ]
        if len(passend) > 1:
            gleiche = [x for x in passend if _typen_gleich(x, f)]
            passend = gleiche or passend
        if passend:
            gefunden.extend(x for x in passend if x not in gefunden)
            continue
        offen.extend(graph.obertypen(k))
    if not gefunden:
        return []
    sicher = len(gefunden) == 1 and not info.offen
    return [
        {
            "art": "ueberschreibt",
            "gewicht": 1,
            "id": _kanten_id("ueberschreibt", f.id, x.id),
            "nach": x.id,
            "rolle": q.rolle,
            "sicher": sicher,
            "von": f.id,
        }
        for x in sorted(gefunden, key=lambda x: x.id)
    ]


def _typen_gleich(a: FInfo, b: FInfo) -> bool:
    def einfach(typ: str | None) -> str:
        basis = typ_basis(typ) or (typ or "")
        return basis.rsplit(".", 1)[-1]

    return [einfach(p.typ) for p in a.parameter] == [einfach(p.typ) for p in b.parameter]


def _jni(graph: Aufrufgraph) -> list[Kante]:
    kotlin: dict[tuple[str, str], FInfo] = {}
    for q in graph.quellen:
        for klasse, name, zeile_nr in q.externe:
            voll = f"{q.paket}.{klasse}" if q.paket else klasse
            for f in graph.je_datei.get(q.pfad, []):
                if f.name == name and f.zeile_von == zeile_nr and f.roh is not None:
                    kotlin.setdefault((voll, name), f)
    kanten: list[Kante] = []
    for cq in graph.c_quellen:
        for c in cq.funktionen:
            schluessel = cq.namen.get(c.name)
            if schluessel is None or schluessel not in kotlin:
                continue
            kt = kotlin[schluessel]
            ziel = next(
                f for f in graph.je_datei[cq.pfad] if f.name == c.name and f.zeile_von == c.zeile
            )
            rolle = kt.quelle.rolle
            kanten.append(
                {
                    "art": "jni",
                    "beleg": [
                        {
                            "funktion": ".".join(schluessel),
                            "zeile_c": c.zeile,
                            "zeile_kotlin": kt.zeile_von,
                        }
                    ],
                    "gewicht": 1,
                    "id": _kanten_id("jni", kt.id, ziel.id, rolle),
                    "nach": ziel.id,
                    "rolle": rolle,
                    "sicher": True,
                    "von": kt.id,
                }
            )
    return kanten
