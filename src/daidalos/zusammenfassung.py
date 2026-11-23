"""``daidalos zusammenfassung``: kurze Übersicht der Messung für den Skill.

Enthält die Auswahlregel für **wichtige Dateien** und die Liste dessen, was in der Deutung noch
**offen** ist. Beides ist Auswahl und Abgleich, keine Deutung; die Regeln stehen in
``docs/datenformat.md`` (Abschnitt Zusammenfassung). Schreibt nichts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from daidalos import __version__
from daidalos.ids import datei_der_funktion
from daidalos.ids import kanten_id as _kid
from daidalos.render import (
    anzeigename,
    braucht_keine_einschaetzung,
    ist_abdeckungsbefund,
    kurz_funktion,
    strukturansicht,
)

Knoten = dict[str, Any]

# Auswahlregel für wichtige Dateien
WICHTIG_FAN_IN_ANZAHL = 30
WICHTIG_MODULKANTE_AB = 3
# Gründe in fester Reihenfolge
GRUENDE = ("fan-in", "befund", "einstieg", "trennstelle", "jni", "modulkante")
# Auswahlregel für wichtige Funktionen (seit A09)
WICHTIG_FUNKTIONEN_FAN_IN = 20
WICHTIG_FUNKTIONEN_HOECHSTENS = 40
GRUENDE_FUNKTION = ("fan-in", "grenzkante")
# Bis zu so vielen offenen Einträgen je Gruppe werden Ids aufgezählt, sonst nur gezählt.
OFFEN_AUFZAEHLEN_BIS = 40


def _gruppe_von(knoten: Knoten) -> str | None:
    """Modul- oder Ordner-Id einer Datei."""
    return knoten.get("modul") or knoten.get("ordner")


def _ist_kandidat(knoten: Knoten) -> bool:
    return (
        knoten["art"] == "datei"
        and not knoten.get("fremd")
        and knoten.get("rolle", "produktiv") == "produktiv"
    )


def _datei_kanten_unter(
    messung: dict[str, Any], kante: dict[str, Any], knoten: dict[str, Knoten]
) -> list[dict[str, Any]]:
    """Datei-Kanten, die eine verdichtete ``nutzt``-Kante (Paket- oder Modulebene) tragen."""
    von, nach = knoten.get(kante["von"]), knoten.get(kante["nach"])
    if von is None or nach is None:
        return []
    feld = ("paket",) if von["art"] == "paket" else ("modul", "ordner")

    def gehoert(datei: Knoten | None, gruppe: str) -> bool:
        return datei is not None and any(datei.get(f) == gruppe for f in feld)

    rolle = kante.get("rolle")
    return [
        k
        for k in messung["kanten"]
        if k["art"] == kante["art"]
        and k["von"].startswith("datei:")
        and k.get("rolle") == rolle
        and gehoert(knoten.get(k["von"]), kante["von"])
        and gehoert(knoten.get(k["nach"]), kante["nach"])
    ]


def wichtige_dateien(messung: dict[str, Any]) -> dict[str, list[str]]:
    """Datei-Id → Gründe der Aufnahme (sortiert nach ``GRUENDE``).

    Kandidaten sind produktive, nicht fremde Dateien. Aufgenommen wird, wer mindestens eines
    erfüllt: unter den 30 mit dem höchsten Fan-in (Fan-in > 0, Gleichstand nach Id), Mitglied
    eines Befunds, Einstieg oder Ende der Trennstelle eines Zyklus (bei Paket- und Modulzyklen:
    die Dateien der Datei-Kanten unter der Trennstelle), Ende einer ``jni``-Kante oder Ende einer
    produktiven ``nutzt``-Datei-Kante mit Gewicht ≥ 3 zwischen verschiedenen Modulen/Ordnern.
    """
    messung = strukturansicht(messung)
    knoten = {k["id"]: k for k in messung["knoten"]}
    kanten = {_kid(k): k for k in messung["kanten"]}
    gruende: dict[str, set[str]] = {}

    def nimm(knoten_id: str, grund: str) -> None:
        k = knoten.get(knoten_id)
        if k is not None and _ist_kandidat(k):
            gruende.setdefault(knoten_id, set()).add(grund)

    kandidaten = [k for k in messung["knoten"] if _ist_kandidat(k)]
    nach_fan_in = sorted(
        (k for k in kandidaten if k.get("metriken", {}).get("fan_in", 0) > 0),
        key=lambda k: (-k["metriken"]["fan_in"], k["id"]),
    )
    for k in nach_fan_in[:WICHTIG_FAN_IN_ANZAHL]:
        nimm(k["id"], "fan-in")

    for befund in messung["befunde"]:
        if befund.get("quelle") == "detekt":
            continue
        if befund["regel"] == "markierung-verlassen":
            # nur die Dateien der Grenzkante, nicht die ganze Kette
            for funktion_id in (befund["beleg"]["von"], befund["beleg"]["nach"]):
                nimm(f"datei:{datei_der_funktion(funktion_id)}", "befund")
            continue
        for knoten_id in befund["knoten"]:
            nimm(knoten_id, "befund")
        if befund["regel"] != "zyklus":
            continue
        beleg = befund["beleg"]
        for einstieg in beleg.get("einstiege", []):
            nimm(einstieg["knoten"], "einstieg")
        trenn = kanten.get(beleg.get("trennstelle") or "")
        if trenn is None:
            continue
        if trenn["von"].startswith("datei:"):
            nimm(trenn["von"], "trennstelle")
            nimm(trenn["nach"], "trennstelle")
        else:
            for k in _datei_kanten_unter(messung, trenn, knoten):
                nimm(k["von"], "trennstelle")
                nimm(k["nach"], "trennstelle")

    for kante in messung["kanten"]:
        if kante["art"] == "jni":
            nimm(kante["von"], "jni")
            nimm(kante["nach"], "jni")
        elif (
            kante["art"] == "nutzt"
            and kante["von"].startswith("datei:")
            and kante.get("rolle") == "produktiv"
            and kante.get("gewicht", 0) >= WICHTIG_MODULKANTE_AB
        ):
            von, nach = knoten.get(kante["von"]), knoten.get(kante["nach"])
            if von and nach and _gruppe_von(von) != _gruppe_von(nach):
                nimm(kante["von"], "modulkante")
                nimm(kante["nach"], "modulkante")

    return {
        knoten_id: [g for g in GRUENDE if g in menge]
        for knoten_id, menge in sorted(gruende.items())
    }


def _zeilen(f: dict[str, Any]) -> str:
    """``12`` oder ``12–20``."""
    von, bis = f["zeile_von"], f["zeile_bis"]
    return str(von) if von == bis else f"{von}–{bis}"


def wichtige_funktionen(messung: dict[str, Any]) -> dict[str, list[str]]:
    """Funktions-Id → Gründe (seit A09); braucht die volle Messung mit Funktionsebene.

    Kandidaten sind produktive Funktionen mit ``hash`` (ohne implizite Konstruktoren) außerhalb
    von Fremdcode. Aufgenommen werden die 20 mit dem höchsten sicheren Fan-in (Fan-in > 0,
    Gleichstand nach Id) und jede markierte Funktion, von der eine Grenzkante der
    Markierungs-Kette ausgeht (``von``), nach Zahl ihrer Grenzkanten, dann Id; höchstens 40
    insgesamt, die Fan-in-Auswahl zuerst.
    """
    fremd = {k["pfad"] for k in messung["knoten"] if k["art"] == "datei" and k.get("fremd")}
    kandidaten = {
        k["id"]: k
        for k in messung["knoten"]
        if k["art"] == "funktion"
        and k.get("rolle") == "produktiv"
        and k.get("hash")
        and datei_der_funktion(k) not in fremd
    }
    nach_fan_in = sorted(
        (k for k in kandidaten.values() if k.get("metriken", {}).get("fan_in", 0) > 0),
        key=lambda k: (-k["metriken"]["fan_in"], k["id"]),
    )[:WICHTIG_FUNKTIONEN_FAN_IN]
    grenzen: dict[str, int] = {}
    for b in messung["befunde"]:
        if b["regel"] == "markierung-verlassen" and b["beleg"]["von"] in kandidaten:
            grenzen[b["beleg"]["von"]] = grenzen.get(b["beleg"]["von"], 0) + 1
    gruende: dict[str, list[str]] = {}
    for k in nach_fan_in:
        gruende[k["id"]] = ["fan-in"]
    for funktion_id in sorted(grenzen, key=lambda i: (-grenzen[i], i)):
        if funktion_id in gruende:
            gruende[funktion_id].append("grenzkante")
        elif len(gruende) < WICHTIG_FUNKTIONEN_HOECHSTENS:
            gruende[funktion_id] = ["grenzkante"]
    return dict(sorted(gruende.items()))


# ---------------------------------------------------------------- Offen


@dataclass
class Offen:
    """Was in der Deutung fehlt, veraltet oder ins Leere zeigt."""

    # Knoten-Id → "fehlt" oder "veraltet"; nur Module, Ordner, Pakete und wichtige Dateien
    # (fehlt) sowie jede beschriebene Knoten-Id mit abweichendem Hash (veraltet)
    beschreibungen: dict[str, str] = field(default_factory=dict)
    befunde: list[str] = field(default_factory=list)  # Befunde ohne Einschätzung
    tote_verweise: list[str] = field(default_factory=list)  # "<wo>: <id>"

    @property
    def leer(self) -> bool:
        return not (self.beschreibungen or self.befunde or self.tote_verweise)

    def als_json(self) -> dict[str, Any]:
        return {
            "befunde_ohne_einschaetzung": self.befunde,
            "beschreibungen": [
                {"id": knoten_id, "stand": stand}
                for knoten_id, stand in sorted(self.beschreibungen.items())
            ],
            "tote_verweise": self.tote_verweise,
        }


def zu_beschreiben(
    messung: dict[str, Any],
    wichtig: dict[str, list[str]],
    funktionen: dict[str, list[str]] | None = None,
) -> list[str]:
    """Ids, die eine Beschreibung brauchen: Module, Ordner und Pakete ohne reinen Fremdcode,
    dazu die wichtigen Dateien und (seit A09) die wichtigen Funktionen."""
    ids = [
        k["id"]
        for k in messung["knoten"]
        if k["art"] in ("modul", "ordner", "paket") and not k.get("fremd")
    ]
    return sorted([*ids, *wichtig, *(funktionen or {})])


def stand_der_beschreibung(eintrag: Any, knoten: Knoten) -> str:
    """``fehlt``, ``veraltet`` oder ``ok``."""
    if not isinstance(eintrag, dict) or not isinstance(eintrag.get("text"), str):
        return "fehlt"
    return "ok" if eintrag.get("hash") == knoten.get("hash") else "veraltet"


def finde_offenes(
    messung: dict[str, Any], deutung: dict[str, Any] | None, wichtig: dict[str, list[str]]
) -> Offen:
    """Abgleich der rohen ``deutung.json`` (oder ``None``) mit der vollen Messung.

    Seit A09 brauchen auch die wichtigen Funktionen eine Beschreibung; Hash und Abgleich wie bei
    Dateien über den ``hash`` des Funktionsknotens.
    """
    deutung = deutung or {}
    funktionen = wichtige_funktionen(messung)
    knoten = {k["id"]: k for k in messung["knoten"]}
    # Abdeckungs- und detekt-Befunde brauchen keine Einschätzung.
    befunde = {b["id"] for b in messung["befunde"] if not braucht_keine_einschaetzung(b)}
    alle_befunde = {b["id"] for b in messung["befunde"]}
    kanten = {_kid(k) for k in messung["kanten"]}
    offen = Offen()

    beschreibungen = deutung.get("beschreibungen")
    beschreibungen = beschreibungen if isinstance(beschreibungen, dict) else {}
    for knoten_id in zu_beschreiben(messung, wichtig, funktionen):
        stand = stand_der_beschreibung(beschreibungen.get(knoten_id), knoten[knoten_id])
        if stand != "ok":
            offen.beschreibungen[knoten_id] = stand
    tote: set[str] = set()
    for knoten_id, eintrag in beschreibungen.items():
        if knoten_id not in knoten:
            tote.add(f"beschreibungen: {knoten_id}")
        elif stand_der_beschreibung(eintrag, knoten[knoten_id]) == "veraltet":
            offen.beschreibungen[knoten_id] = "veraltet"

    bewertet: set[str] = set()
    for eintrag in deutung.get("einschaetzungen") or []:
        befund = eintrag.get("befund") if isinstance(eintrag, dict) else None
        if not isinstance(befund, str):
            continue
        bewertet.add(befund)
        if befund not in alle_befunde:
            tote.add(f"einschaetzungen: {befund}")
    offen.befunde = sorted(befunde - bewertet)

    for bereich in deutung.get("bereiche") or []:
        if not isinstance(bereich, dict):
            continue
        for knoten_id in bereich.get("knoten") or []:
            if knoten_id not in knoten:
                tote.add(f"bereiche {bereich.get('id')}: {knoten_id}")
    kanten_texte = deutung.get("kanten")
    for kanten_id in kanten_texte if isinstance(kanten_texte, dict) else {}:
        if kanten_id not in kanten:
            tote.add(f"kanten: {kanten_id}")
    offen.tote_verweise = sorted(tote)
    return offen


# ---------------------------------------------------------------- Ausgabe


def befund_kurz(befund: dict[str, Any], kanten: dict[str, dict[str, Any]]) -> str:
    """Ein Befund in einer Zeile, nur aus der Messung."""
    beleg = befund["beleg"]
    regel = befund["regel"]
    if regel == "zyklus":
        text = f"Zyklus, Ebene {beleg['ebene']}"
        if "kantenart" in beleg:
            text += f" ({beleg['kantenart']})"
        text += f", {beleg['rolle']}, {len(beleg['knoten'])} Knoten"
        trenn = kanten.get(beleg.get("trennstelle") or "")
        if trenn is not None:
            text += f", Trennstelle `{trenn['id']}` (Gewicht {trenn.get('gewicht')})"
        elif beleg.get("kleinste_trennmenge"):
            text += f", keine einzelne Trennstelle (Trennmenge {len(beleg['kleinste_trennmenge'])})"
        else:
            text += ", keine einzelne Trennstelle"
        if beleg.get("unsicher"):
            text += ", unsichere Kante beteiligt"
        return text
    if regel == "jni-ohne-gegenstueck":
        return f"JNI ohne Gegenstück ({beleg['seite']}): {beleg['funktion']}"
    if regel == "unaufgeloest":
        return f"{len(beleg['importe'])} unaufgelöste interne Importe"
    if regel == "markierung-verlassen":
        text = (
            f"`{kurz_funktion(beleg['von'])}` ({beleg['markierung']['name']} an "
            f"{beleg['markierung']['traeger']}) ruft unmarkiert `{kurz_funktion(beleg['nach'])}`, "
            f"Kette {beleg['anzahl']}"
        )
        if beleg.get("kette_unsicher"):
            text += f" (+{len(beleg['kette_unsicher'])} unsicher)"
        if beleg.get("unsicher"):
            text += ", nur über unsichere Kanten"
        if beleg["ausnahmen"]:
            text += f", endet an {len(beleg['ausnahmen'])} Ausnahmen"
        return text
    return regel


@dataclass
class Zusammenfassung:
    messung: dict[str, Any]
    deutung: dict[str, Any] | None

    def __post_init__(self) -> None:
        self.voll = self.messung
        self.messung = strukturansicht(self.messung)
        self.knoten = {k["id"]: k for k in self.messung["knoten"]}
        self.kanten = {_kid(k): k for k in self.messung["kanten"]}
        self.wichtig = wichtige_dateien(self.messung)
        self.wichtig_funktionen = wichtige_funktionen(self.voll)
        self.offen = finde_offenes(self.voll, self.deutung, self.wichtig)
        self.voll_knoten = {k["id"]: k for k in self.voll["knoten"]}
        roh = (self.deutung or {}).get("beschreibungen")
        self.beschreibungen = roh if isinstance(roh, dict) else {}

    # ------------------------------------------------------------ Bausteine

    def stand(self, knoten_id: str) -> str:
        return stand_der_beschreibung(self.beschreibungen.get(knoten_id), self.knoten[knoten_id])

    def zahlen(self) -> dict[str, int]:
        knoten = self.messung["knoten"]
        dateien = [k for k in knoten if k["art"] == "datei"]
        return {
            "befunde": len(self.bewertbare()),
            "dateien": len(dateien),
            "dateien_fremd": sum(1 for k in dateien if k.get("fremd")),
            "dateikanten": sum(
                1
                for k in self.messung["kanten"]
                if k["art"] == "nutzt" and k["von"].startswith("datei:")
            ),
            "module": sum(1 for k in knoten if k["art"] == "modul"),
            "ordner": sum(1 for k in knoten if k["art"] == "ordner"),
            "pakete": sum(1 for k in knoten if k["art"] == "paket"),
            "wichtige_dateien": len(self.wichtig),
            "wichtige_funktionen": len(self.wichtig_funktionen),
            "zeilen": sum(k.get("zeilen", 0) for k in dateien),
        }

    def gruppen(self) -> list[dict[str, Any]]:
        gradle: dict[str, list[str]] = {}
        for k in self.messung["kanten"]:
            if k["art"].startswith("gradle-"):
                art = k["art"].removeprefix("gradle-")
                gradle.setdefault(k["von"], []).append(f"{self.knoten[k['nach']]['pfad']} ({art})")
        zeilen = []
        for g in sorted(
            (k for k in self.messung["knoten"] if k["art"] in ("modul", "ordner")),
            key=lambda k: (k["art"], k["id"]),
        ):
            m = g.get("metriken", {})
            zeilen.append(
                {
                    "dateien": g.get("dateien", 0),
                    "deutung": "fremd" if g.get("fremd") else self.stand(g["id"]),
                    "fan_in": m.get("fan_in", 0),
                    "fan_out": m.get("fan_out", 0),
                    "gradle": sorted(gradle.get(g["id"], [])),
                    "id": g["id"],
                    "zeilen": g.get("zeilen", 0),
                }
            )
        return zeilen

    def pakete(self) -> list[dict[str, Any]]:
        zeilen = []
        for p in sorted(
            (k for k in self.messung["knoten"] if k["art"] == "paket"),
            key=lambda k: (k.get("modul") or k.get("ordner") or "", k["id"]),
        ):
            m = p.get("metriken", {})
            zeilen.append(
                {
                    "dateien": p.get("dateien", 0),
                    "deutung": "fremd" if p.get("fremd") else self.stand(p["id"]),
                    "fan_in": m.get("fan_in", 0),
                    "fan_out": m.get("fan_out", 0),
                    "gruppe": p.get("modul") or p.get("ordner"),
                    "id": p["id"],
                    "zeilen": p.get("zeilen", 0),
                }
            )
        return zeilen

    def wichtige(self) -> list[dict[str, Any]]:
        zeilen = []
        for knoten_id, gruende in self.wichtig.items():
            k = self.knoten[knoten_id]
            m = k.get("metriken", {})
            zeilen.append(
                {
                    "deutung": self.stand(knoten_id),
                    "fan_in": m.get("fan_in", 0),
                    "fan_out": m.get("fan_out", 0),
                    "gruende": gruende,
                    "id": knoten_id,
                    "zeilen": k.get("zeilen", 0),
                }
            )
        zeilen.sort(key=lambda z: (-z["fan_in"], z["id"]))
        return zeilen

    def funktionen_wichtig(self) -> list[dict[str, Any]]:
        zeilen = []
        for funktion_id, gruende in self.wichtig_funktionen.items():
            k = self.voll_knoten[funktion_id]
            m = k.get("metriken", {})
            zeilen.append(
                {
                    "datei": datei_der_funktion(k),
                    "deutung": stand_der_beschreibung(self.beschreibungen.get(funktion_id), k),
                    "fan_in": m.get("fan_in", 0),
                    "gruende": gruende,
                    "id": funktion_id,
                    "komplexitaet": m.get("komplexitaet"),
                    "markiert": bool(k.get("markiert")),
                    "zeile_bis": k["zeile_bis"],
                    "zeile_von": k["zeile_von"],
                }
            )
        zeilen.sort(key=lambda z: (-z["fan_in"], z["id"]))
        return zeilen

    def bewertbare(self) -> list[dict[str, Any]]:
        """Befunde, die eine Einschätzung brauchen (ohne detekt)."""
        return [b for b in self.messung["befunde"] if not braucht_keine_einschaetzung(b)]

    def befunde(self) -> list[dict[str, Any]]:
        bewertet = set(self.offen.befunde)
        return [
            {
                "einschaetzung": b["id"] not in bewertet,
                "id": b["id"],
                "kurz": befund_kurz(b, self.kanten),
            }
            for b in self.bewertbare()
        ]

    def messung_funktionen(self) -> dict[str, Any]:
        """Abdeckung der Funktionsebene: Funktionen, ruft-Kanten, unaufgelöste Aufrufe."""
        funktionen = [k for k in self.voll["knoten"] if k["art"] == "funktion"]
        ruft = [k for k in self.voll["kanten"] if k["art"] == "ruft"]
        abdeckung = [b for b in self.voll["befunde"] if ist_abdeckungsbefund(b)]
        namen: dict[tuple[str, str], int] = {}
        for b in abdeckung:
            for n in b["beleg"]["namen"]:
                schluessel = (n["name"], n["grund"])
                namen[schluessel] = namen.get(schluessel, 0) + n["anzahl"]
        haeufig = sorted(namen.items(), key=lambda e: (-e[1], e[0]))[:10]
        kette = [b for b in self.voll["befunde"] if b["regel"] == "markierung-verlassen"]
        detekt: dict[str, int] = {}
        for b in self.voll["befunde"]:
            if b.get("quelle") == "detekt":
                detekt[b["regel"]] = detekt.get(b["regel"], 0) + 1
        return {
            "ausnahmen": sum(1 for k in funktionen if k.get("ausnahme")),
            "detekt": {
                **(self.voll["ziel"].get("detekt") or {"dateien": 0, "ergebnisse": 0}),
                "regeln": [{"anzahl": n, "regel": r} for r, n in sorted(detekt.items())],
            }
            if "detekt" in self.voll["ziel"]
            else None,
            "grenzkanten_sicher": sum(1 for b in kette if not b["beleg"].get("unsicher")),
            "grenzkanten_unsicher": sum(1 for b in kette if b["beleg"].get("unsicher")),
            "markiert": sum(1 for k in funktionen if k.get("markiert")),
            "funktionen": sum(1 for k in funktionen if k.get("rolle") == "produktiv"),
            "funktionen_test": sum(1 for k in funktionen if k.get("rolle") == "test"),
            "ruft_sicher": sum(1 for k in ruft if k["sicher"]),
            "ruft_unsicher": sum(1 for k in ruft if not k["sicher"]),
            "unaufgeloeste_aufrufe": sum(b["beleg"]["anzahl"] for b in abdeckung),
            "unaufgeloeste_dateien": len(abdeckung),
            "unaufgeloeste_namen": [
                {"anzahl": anzahl, "grund": grund, "name": name}
                for (name, grund), anzahl in haeufig
            ],
        }

    def _messung_markdown(self) -> list[str]:
        m = self.messung_funktionen()
        aus = ["## Messung", ""]
        aus.append(
            f"Funktionen: {m['funktionen']} produktiv, {m['funktionen_test']} Test; "
            f"ruft-Kanten: {m['ruft_sicher']} sicher, {m['ruft_unsicher']} unsicher."
        )
        if m["unaufgeloeste_aufrufe"]:
            namen = ", ".join(
                f"`{n['name']}` ({n['anzahl']}, {n['grund']})" for n in m["unaufgeloeste_namen"]
            )
            aus.append(
                f"Unaufgelöste Aufrufe (Maß für die Abdeckung, kein Befund): "
                f"{m['unaufgeloeste_aufrufe']} in {m['unaufgeloeste_dateien']} Dateien; "
                f"häufigste: {namen}."
            )
        else:
            aus.append("Unaufgelöste Aufrufe: keine.")
        if m["markiert"] or m["grenzkanten_sicher"] or m["grenzkanten_unsicher"]:
            aus.append(
                f"Markierungs-Kette: {m['markiert']} markierte Funktionen, {m['ausnahmen']} "
                f"Ausnahmen; Grenzkanten {m['grenzkanten_sicher']} sicher, "
                f"{m['grenzkanten_unsicher']} nur unsicher (Befunde `markierung-verlassen`)."
            )
        if m["detekt"] is not None:
            regeln = ", ".join(f"`{r['regel']}` {r['anzahl']}" for r in m["detekt"]["regeln"])
            aus.append(
                f"detekt (eigene Regeln, keine Einschätzung nötig): {m['detekt']['dateien']} "
                f"SARIF-Dateien, {m['detekt']['ergebnisse']} Ergebnisse; Befunde je Regel: "
                f"{regeln or 'keine'}."
            )
        return aus

    # ------------------------------------------------------------ Ausgaben

    def als_json(self) -> dict[str, Any]:
        ziel = self.messung["ziel"]
        return {
            "befunde": self.befunde(),
            "daidalos": __version__,
            "gruppen": self.gruppen(),
            "offen": self.offen.als_json(),
            "pakete": self.pakete(),
            "wichtige_dateien": self.wichtige(),
            "wichtige_funktionen": self.funktionen_wichtig(),
            "messung": self.messung_funktionen(),
            "zahlen": self.zahlen(),
            "ziel": {
                "git_aenderungen": ziel.get("git_aenderungen"),
                "git_commit": ziel.get("git_commit"),
                "name": ziel["name"],
            },
        }

    def als_markdown(self) -> str:
        ziel = self.messung["ziel"]
        z = self.zahlen()
        commit = ziel.get("git_commit")
        stand = f"Commit `{commit[:7]}`" if commit else "ohne Git-Commit"
        if ziel.get("git_aenderungen"):
            stand += ", mit nicht committeten Änderungen"
        aus: list[str] = [
            f"# Zusammenfassung · {ziel['name']}",
            "",
            f"{stand}. Daidalos {__version__}. Nur Gemessenes; Spalte „Deutung“: Stand der "
            "Beschreibung in deutung.json (ok, fehlt, veraltet, fremd).",
            "",
            f"Zahlen: {z['dateien']} Dateien (fremd {z['dateien_fremd']}), {z['zeilen']} Zeilen, "
            f"{z['module']} Module, {z['ordner']} Ordner, {z['pakete']} Pakete, "
            f"{z['dateikanten']} nutzt-Kanten zwischen Dateien, {z['befunde']} Befunde, "
            f"{z['wichtige_dateien']} wichtige Dateien.",
        ]
        aus += ["", "## Module und Ordner", ""]
        aus.append("| Id | Dateien | Zeilen | Fan-in | Fan-out | Gradle nach | Deutung |")
        aus.append("| --- | ---: | ---: | ---: | ---: | --- | --- |")
        for g in self.gruppen():
            gradle = ", ".join(g["gradle"]) or "–"
            aus.append(
                f"| `{g['id']}` | {g['dateien']} | {g['zeilen']} | {g['fan_in']} | "
                f"{g['fan_out']} | {gradle} | {g['deutung']} |"
            )
        aus += ["", "## Pakete"]
        gruppe = None
        for p in self.pakete():
            if p["gruppe"] != gruppe:
                gruppe = p["gruppe"]
                aus += ["", f"### {gruppe}", ""]
                aus.append("| Paket | Dateien | Zeilen | Fan-in | Fan-out | Deutung |")
                aus.append("| --- | ---: | ---: | ---: | ---: | --- |")
            name = anzeigename(self.knoten[p["id"]])
            aus.append(
                f"| `{name}` | {p['dateien']} | {p['zeilen']} | {p['fan_in']} | "
                f"{p['fan_out']} | {p['deutung']} |"
            )
        aus += ["", "## Wichtige Dateien", ""]
        aus.append(
            "Auswahlregel: produktiv, nicht fremd und mindestens eines: unter den "
            f"{WICHTIG_FAN_IN_ANZAHL} mit dem höchsten Fan-in (fan-in), Mitglied eines Befunds "
            "(befund), Einstieg (einstieg) oder Trennstelle (trennstelle) eines Zyklus, Ende einer "
            f"JNI-Kante (jni) oder einer modulübergreifenden Kante mit Gewicht ≥ "
            f"{WICHTIG_MODULKANTE_AB} (modulkante)."
        )
        aus += ["", "| Id | Zeilen | Fan-in | Fan-out | Grund | Deutung |"]
        aus.append("| --- | ---: | ---: | ---: | --- | --- |")
        for w in self.wichtige():
            aus.append(
                f"| `{w['id']}` | {w['zeilen']} | {w['fan_in']} | {w['fan_out']} | "
                f"{', '.join(w['gruende'])} | {w['deutung']} |"
            )
        aus += self._funktionen_markdown()
        aus += ["", "## Befunde", ""]
        if not self.bewertbare():
            aus.append("Keine.")
        for b in self.befunde():
            marke = "" if b["einschaetzung"] else " · ohne Einschätzung"
            aus.append(f"- `{b['id']}`: {b['kurz']}{marke}")
        aus += ["", *self._messung_markdown()]
        aus += ["", *self._offen_markdown()]
        return "\n".join(aus) + "\n"

    def _funktionen_markdown(self) -> list[str]:
        zeilen = self.funktionen_wichtig()
        if not zeilen:
            return []
        aus = ["", "## Wichtige Funktionen", ""]
        aus.append(
            f"Auswahlregel: produktiv, nicht fremd; die {WICHTIG_FUNKTIONEN_FAN_IN} mit dem "
            "höchsten sicheren Fan-in (fan-in) und jede markierte Funktion mit einer Grenzkante "
            f"der Markierungs-Kette (grenzkante), höchstens {WICHTIG_FUNKTIONEN_HOECHSTENS}. Je "
            "Funktion ein Satz; den Körper zeigen die Zeilen (von–bis)."
        )
        aus += ["", "| Id | Zeilen | Fan-in | Komplexität | Grund | Deutung |"]
        aus.append("| --- | --- | ---: | ---: | --- | --- |")
        for f in zeilen:
            komplex = "–" if f["komplexitaet"] is None else f["komplexitaet"]
            aus.append(
                f"| `{f['id']}` | {_zeilen(f)} | {f['fan_in']} | "
                f"{komplex} | {', '.join(f['gruende'])} | {f['deutung']} |"
            )
        return aus

    def _offen_markdown(self) -> list[str]:
        offen = self.offen
        aus = ["## Offen", ""]
        if offen.leer:
            return [*aus, "Nichts offen. Die Deutung ist aktuell."]
        fehlt = sorted(i for i, s in offen.beschreibungen.items() if s == "fehlt")
        veraltet = sorted(i for i, s in offen.beschreibungen.items() if s == "veraltet")
        alle = zu_beschreiben(self.messung, self.wichtig, self.wichtig_funktionen)
        if fehlt and len(fehlt) == len(alle):
            aus.append(
                f"- Beschreibung fehlt: alle {len(alle)} (Module, Ordner, Pakete, wichtige "
                "Dateien und wichtige Funktionen; siehe Spalte Deutung)"
            )
        else:
            aus += self._liste("Beschreibung fehlt", fehlt)
        aus += self._liste("Beschreibung veraltet (Hash weicht ab)", veraltet)
        if offen.befunde and len(offen.befunde) == len(self.bewertbare()):
            aus.append(f"- Befunde ohne Einschätzung: alle {len(offen.befunde)}")
        else:
            aus += self._liste("Befunde ohne Einschätzung", offen.befunde)
        aus += self._liste("Tote Verweise in deutung.json", offen.tote_verweise)
        return aus

    @staticmethod
    def _liste(titel: str, ids: list[str]) -> list[str]:
        if not ids:
            return []
        if len(ids) > OFFEN_AUFZAEHLEN_BIS:
            return [f"- {titel}: {len(ids)} (siehe Spalte Deutung oder `--json`)"]
        return [f"- {titel}: {len(ids)}", *(f"  - `{i}`" for i in ids)]
