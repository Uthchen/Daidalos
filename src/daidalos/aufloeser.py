"""Auflöser: macht aus Kotlin-Namen Verbindungen zwischen Dateien.

Grundlage ist ein Symbolverzeichnis (voller Name → Dateien). Mehrdeutiges wird als unsicher
markiert und nie geraten.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from daidalos.adapter.kotlin import KotlinDatei

PRODUKTIV = "produktiv"
TEST = "test"

HERKUNFT_IMPORT = "import"
HERKUNFT_PAKET = "gleiches-paket"
HERKUNFT_QUALIFIZIERT = "voll-qualifiziert"


@dataclass(frozen=True)
class Quelldatei:
    """Eine Kotlin-Datei mit allem, was der Auflöser über sie wissen muss."""

    pfad: str
    inhalt: KotlinDatei
    container: str  # Modul- oder Ordner-Id
    rolle: str


@dataclass(frozen=True)
class Beleg:
    symbol: str
    zeile: int
    herkunft: str
    sicher: bool


@dataclass
class DateiKante:
    von: str  # Pfad
    nach: str
    rolle: str
    belege: list[Beleg] = field(default_factory=list)

    @property
    def gewicht(self) -> int:
        return len({b.symbol for b in self.belege})

    @property
    def sicher(self) -> bool:
        return any(b.sicher for b in self.belege)


@dataclass(frozen=True)
class Unaufgeloest:
    pfad: str
    name: str
    zeile: int


@dataclass
class Aufloesung:
    kanten: list[DateiKante]
    unaufgeloest: list[Unaufgeloest]
    interne_praefixe: tuple[str, ...]


def interne_praefixe(pakete: set[str]) -> tuple[str, ...]:
    """Präfixe, die als intern gelten: die ersten zwei Teile jedes gefundenen Pakets."""
    praefixe = {".".join(paket.split(".")[:2]) for paket in pakete if paket}
    return tuple(sorted(praefixe))


def ist_intern(name: str, praefixe: tuple[str, ...]) -> bool:
    return any(name == p or name.startswith(p + ".") for p in praefixe)


class Symbolverzeichnis:
    def __init__(self, dateien: list[Quelldatei]) -> None:
        self.voll: dict[str, list[str]] = defaultdict(list)
        # (Container, Paket) → einfacher Name → Dateien, nur oberste Ebene
        self.paket_im_container: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Paket → einfacher Name → Dateien, nur oberste Ebene, über alle Container
        self.paket: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        # (Container, Paket) → Name → Dateien, nur Erweiterungen der obersten Ebene
        self.erweiterungen: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.pakete: set[str] = set()
        for datei in dateien:
            paket = datei.inhalt.paket or ""
            if paket:
                self.pakete.add(paket)
            for deklaration in datei.inhalt.deklarationen:
                voll = f"{paket}.{deklaration.name}" if paket else deklaration.name
                _fuege_an(self.voll[voll], datei.pfad)
                if deklaration.oberste_ebene:
                    _fuege_an(
                        self.paket_im_container[(datei.container, paket)][deklaration.name],
                        datei.pfad,
                    )
                    _fuege_an(self.paket[paket][deklaration.name], datei.pfad)
                    if deklaration.erweiterung:
                        _fuege_an(
                            self.erweiterungen[(datei.container, paket)][deklaration.name],
                            datei.pfad,
                        )

    def laengstes_praefix(self, name: str) -> str | None:
        teile = name.split(".")
        for laenge in range(len(teile), 0, -1):
            kandidat = ".".join(teile[:laenge])
            if kandidat in self.voll:
                return kandidat
        return None


def _fuege_an(liste: list[str], pfad: str) -> None:
    if pfad not in liste:
        liste.append(pfad)


def loese_auf(dateien: list[Quelldatei]) -> Aufloesung:
    verzeichnis = Symbolverzeichnis(dateien)
    praefixe = interne_praefixe(verzeichnis.pakete)
    rollen = {d.pfad: d.rolle for d in dateien}
    kanten: dict[tuple[str, str], DateiKante] = {}
    unaufgeloest: list[Unaufgeloest] = []

    for datei in sorted(dateien, key=lambda d: d.pfad):

        def sichtbar(kandidaten: list[str], weich: bool, datei: Quelldatei = datei) -> list[str]:
            """Produktiver Code sieht keinen Testcode. ``weich``: notfalls alle behalten."""
            andere = sorted(k for k in kandidaten if k != datei.pfad)
            if datei.rolle != PRODUKTIV:
                return andere
            produktiv = [k for k in andere if rollen.get(k) == PRODUKTIV]
            if produktiv or not weich:
                return produktiv
            return andere

        def nimm(
            ziele: list[str],
            symbol: str,
            zeile: int,
            herkunft: str,
            sicher: bool,
            datei: Quelldatei = datei,
        ) -> None:
            for ziel in ziele:
                kante = kanten.get((datei.pfad, ziel))
                if kante is None:
                    kante = DateiKante(datei.pfad, ziel, datei.rolle)
                    kanten[(datei.pfad, ziel)] = kante
                beleg = Beleg(symbol, zeile, herkunft, sicher)
                if beleg not in kante.belege:
                    kante.belege.append(beleg)

        inhalt = datei.inhalt
        paket = inhalt.paket or ""
        importierte_namen: set[str] = set()
        stern_pakete: list[str] = []

        for imp in inhalt.importe:
            if imp.stern and imp.name in verzeichnis.pakete:
                stern_pakete.append(imp.name)
                continue
            if not imp.stern:
                importierte_namen.add(imp.sichtbarer_name)
            symbol = verzeichnis.laengstes_praefix(imp.name)
            if symbol is None:
                if ist_intern(imp.name, praefixe):
                    unaufgeloest.append(Unaufgeloest(datei.pfad, imp.name, imp.zeile))
                continue
            alle_ziele = verzeichnis.voll[symbol]
            ziele = sichtbar(alle_ziele, weich=True)
            if not ziele:
                continue  # nur die eigene Datei
            nimm(ziele, symbol, imp.zeile, HERKUNFT_IMPORT, len(ziele) == 1)

        eigenes_paket = verzeichnis.paket_im_container.get((datei.container, paket), {})
        for name, zeile in sorted(inhalt.namen.items()):
            if name in importierte_namen or name in inhalt.lokale_namen:
                continue
            gross = name[:1].isupper()
            ziele = sichtbar(eigenes_paket.get(name, []), weich=False)
            if ziele:
                symbol = f"{paket}.{name}" if paket else name
                nimm(ziele, symbol, zeile, HERKUNFT_PAKET, gross and len(ziele) == 1)
                continue
            for stern in stern_pakete:
                ziele = sichtbar(verzeichnis.paket[stern].get(name, []), weich=False)
                if ziele:
                    nimm(
                        ziele, f"{stern}.{name}", zeile, HERKUNFT_IMPORT, gross and len(ziele) == 1
                    )
                    break

        # ``x.name()`` kann eine Erweiterung aus dem gleichen Paket sein: immer unsicher.
        eigene_erweiterungen = verzeichnis.erweiterungen.get((datei.container, paket), {})
        for name, zeile in sorted(inhalt.mitglieder.items()):
            if name in importierte_namen or name in inhalt.lokale_namen:
                continue
            ziele = sichtbar(eigene_erweiterungen.get(name, []), weich=False)
            if ziele:
                symbol = f"{paket}.{name}" if paket else name
                nimm(ziele, symbol, zeile, HERKUNFT_PAKET, False)

        for kette, zeile in sorted(inhalt.qualifiziert.items()):
            if not ist_intern(kette, praefixe):
                continue
            symbol = verzeichnis.laengstes_praefix(kette)
            if symbol is None or "." not in symbol:
                continue
            ziele = sichtbar(verzeichnis.voll[symbol], weich=True)
            if ziele:
                nimm(ziele, symbol, zeile, HERKUNFT_QUALIFIZIERT, len(ziele) == 1)

    ergebnis = sorted(kanten.values(), key=lambda k: (k.von, k.nach))
    for kante in ergebnis:
        kante.belege.sort(key=lambda b: (b.zeile, b.symbol, b.herkunft, b.sicher))
    unaufgeloest.sort(key=lambda u: (u.pfad, u.zeile, u.name))
    return Aufloesung(ergebnis, unaufgeloest, praefixe)
