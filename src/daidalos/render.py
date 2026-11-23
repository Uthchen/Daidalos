"""``daidalos render``: ``karte.html`` und ``KARTE.md`` aus Messung und Deutung.

Rechnet nichts Neues aus. Alles, was die Karte zeigt, steht in der Messung oder der Deutung.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import quote

from daidalos import __version__
from daidalos.konfiguration import STANDARD_EDITOR_LINK
from daidalos.scanner import SCHEMA

Knoten = dict[str, Any]

# Reihenfolge der Bibliotheken in karte.html: (Datei, Lizenzdatei, Name)
BIBLIOTHEKEN = (
    ("cytoscape.min.js", "cytoscape.LICENSE", "Cytoscape.js 3.28.1 (MIT)"),
    ("elk.bundled.js", "elkjs.LICENSE.md", "elkjs 0.9.3 (EPL-2.0)"),
    ("cytoscape-elk.js", "cytoscape-elk.LICENSE", "cytoscape-elk 2.4.0 (MIT)"),
)
_PLATZHALTER = re.compile(r"\{\{([A-Z_]+)\}\}")
_EBENEN_TITEL = {"datei": "Dateiebene", "paket": "Paketebene", "modul": "Modulebene"}


class RenderFehler(Exception):
    """Eingaben fehlen oder passen nicht; Exit-Code 2."""


# ---------------------------------------------------------------- Eingaben


def lade_messung(pfad: Path) -> dict[str, Any]:
    if not pfad.is_file():
        raise RenderFehler(f"{pfad.name} fehlt: {pfad.as_posix()} (zuerst daidalos scan)")
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as fehler:
        raise RenderFehler(f"{pfad.name}: nicht lesbar ({fehler})") from fehler
    if not isinstance(daten, dict) or daten.get("schema") != SCHEMA:
        schema = daten.get("schema") if isinstance(daten, dict) else None
        raise RenderFehler(
            f"{pfad.name}: schema {schema!r} wird nicht unterstützt (erwartet {SCHEMA})"
        )
    return daten


# ---------------------------------------------------------------- Strukturansicht

# Kanten zwischen Funktionen; die Karte zeigt sie (noch) nicht.
FUNKTIONSKANTEN = frozenset({"ruft", "ueberschreibt", "actual"})
# Felder des Datei-Knotens, die nur die Funktionsebene betreffen
_FUNKTIONSFELDER = ("annotationen", "eigenschaften", "funktionen", "klassen")


def ist_abdeckungsbefund(befund: dict[str, Any]) -> bool:
    """``unaufgeloest`` der Art ``aufruf`` misst die eigene Abdeckung, nicht den Zielcode."""
    beleg = befund.get("beleg")
    return (
        befund.get("regel") == "unaufgeloest"
        and isinstance(beleg, dict)
        and beleg.get("art") == "aufruf"
    )


def strukturansicht(messung: dict[str, Any]) -> dict[str, Any]:
    """Die Messung ohne Funktionsebene: ohne Funktionsknoten, ohne Kanten von oder zu Funktionen,
    ohne Abdeckungsbefunde und ohne die Funktionsfelder der Datei-Knoten.

    Karte, ``KARTE.md``, Zusammenfassung und Deutung arbeiten auf dieser Ansicht. Für eine
    Messung ohne Funktionsebene ist sie inhaltlich gleich der Messung.
    """
    knoten = []
    for k in messung["knoten"]:
        if k["art"] == "funktion":
            continue
        if k["art"] == "datei" and any(f in k for f in _FUNKTIONSFELDER):
            k = {s: w for s, w in k.items() if s not in _FUNKTIONSFELDER}
        knoten.append(k)
    kanten = [
        k
        for k in messung["kanten"]
        if k["art"] not in FUNKTIONSKANTEN
        and not k["von"].startswith("funktion:")
        and not k["nach"].startswith("funktion:")
    ]
    befunde = [b for b in messung["befunde"] if not ist_abdeckungsbefund(b)]
    return {**messung, "befunde": befunde, "kanten": kanten, "knoten": knoten}


# ---------------------------------------------------------------- karte.html


def einbett_json(daten: Any) -> str:
    """JSON für ``<script type="application/json">``.

    Jedes ``<`` wird als ``\\u003c`` geschrieben. Damit kann kein Inhalt das Script-Tag beenden
    (``</script>``) oder einen HTML-Kommentar öffnen; ``JSON.parse`` liefert denselben Text.
    """
    text = json.dumps(daten, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text.replace("<", "\\u003c")


def _paketdatei(name: str) -> str:
    return resources.files("daidalos.karte").joinpath(name).read_text(encoding="utf-8")


def _vendor(name: str) -> str:
    return resources.files("daidalos.karte").joinpath("vendor", name).read_text(encoding="utf-8")


def _html_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _lizenzen() -> str:
    teile = []
    for _, lizenz, name in BIBLIOTHEKEN:
        text = _vendor(lizenz).replace("\r\n", "\n").strip()
        if "-->" in text or "--!>" in text:
            raise RenderFehler(f"Lizenztext {lizenz} lässt sich nicht als Kommentar einbetten")
        teile.append(f"{name}\n\n{text}")
    trenner = "\n\n" + "-" * 72 + "\n\n"
    return "<!--\nEingebettete Bibliotheken und ihre Lizenzen\n\n" + trenner.join(teile) + "\n-->"


def _skripte() -> str:
    teile = []
    for datei, _, name in BIBLIOTHEKEN:
        code = _vendor(datei)
        if "</script" in code.lower() or "<!--" in code:
            raise RenderFehler(f"{datei} enthält eine Zeichenfolge, die das Script-Tag stört")
        teile.append(f"<!-- {name} -->\n<script>\n{code}\n</script>")
    return "\n".join(teile)


def wurzel_relativ(ziel: Path, ausgabe: Path) -> str | None:
    """Weg vom Ausgabeordner zurück zur Wurzel des Zielrepos, etwa ``../..``.

    ``None``, wenn der Ausgabeordner nicht im Zielrepo liegt; dann kann die Karte keine Dateien im
    Editor öffnen. Es entsteht nie ein absoluter Pfad.
    """
    try:
        teile = ausgabe.resolve().relative_to(ziel.resolve()).parts
    except ValueError:
        return None
    return "/".join([".."] * len(teile)) or "."


def einstellungen_fuer_karte(editor_link: str, wurzel: str | None) -> dict[str, Any]:
    """Einstellungen für die Karte; keine Messung, deshalb nicht in ``daidalos.json``."""
    return {"editor_link": editor_link, "wurzel": wurzel}


def baue_karte(
    messung: dict[str, Any],
    deutung: dict[str, Any] | None,
    einstellungen: dict[str, Any] | None = None,
) -> str:
    if einstellungen is None:
        einstellungen = einstellungen_fuer_karte(STANDARD_EDITOR_LINK, None)
    werte = {
        "TITEL": _html_text(f"Karte · {messung['ziel']['name']}"),
        "LIZENZEN": _lizenzen(),
        "CSS": _paketdatei("karte.css"),
        "BIBLIOTHEKEN": _skripte(),
        "DATEN": einbett_json(strukturansicht(messung)),
        "DEUTUNG": einbett_json(deutung),
        "EINSTELLUNGEN": einbett_json(einstellungen),
        "SKRIPT": _paketdatei("karte.js"),
        "VERSION": _html_text(__version__),
    }
    # Ein Durchlauf: eingesetzte Inhalte werden nicht erneut nach Platzhaltern durchsucht.
    html = _PLATZHALTER.sub(lambda m: werte[m.group(1)], _paketdatei("vorlage.html"))
    return html.replace("\r\n", "\n")


# ---------------------------------------------------------------- Namen und Verweise


def anzeigename(knoten: Knoten) -> str:
    art = knoten["art"]
    if art == "modul":
        return knoten["gradle_pfad"]
    if art == "paket":
        return knoten["name"]
    if art == "ordner":
        return "(Wurzel)" if knoten["pfad"] == "." else f"{knoten['pfad']}/"
    if art == "funktion":
        return knoten["id"].split("#", 1)[1]
    return knoten["pfad"].rsplit("/", 1)[-1]


def sprungadresse(schluessel: str, wert: str) -> str:
    return f"karte.html#{schluessel}={quote(wert, safe='')}"


def _md(text: str) -> str:
    """Text für Markdown-Tabellen und Links entschärfen."""
    text = text.replace("\\", "\\\\").replace("\n", " ")
    for zeichen in "|[]*_`<>":
        text = text.replace(zeichen, "\\" + zeichen)
    return text


def _zahl(wert: float | None, stellen: int = 2) -> str:
    if wert is None:
        return "–"
    return f"{wert:.{stellen}f}".replace(".", ",")


# ---------------------------------------------------------------- KARTE.md


class _MdBauer:
    def __init__(self, messung: dict[str, Any], deutung: dict[str, Any] | None) -> None:
        self.messung = messung
        self.deutung = deutung or {
            "bereiche": [],
            "beschreibungen": {},
            "einschaetzungen": [],
            "kanten": {},
        }
        self.knoten = {k["id"]: k for k in messung["knoten"]}
        self.kanten = {k["id"]: k for k in messung["kanten"]}
        self.befunde = {b["id"]: b for b in messung["befunde"]}

    def kn(self, knoten_id: str) -> str:
        knoten = self.knoten.get(knoten_id)
        name = anzeigename(knoten) if knoten else knoten_id
        return f"[{_md(name)}]({sprungadresse('knoten', knoten_id)})"

    def bf(self, befund_id: str, text: str) -> str:
        return f"[{_md(text)}]({sprungadresse('befund', befund_id)})"

    def beschreibung(self, knoten_id: str) -> str:
        eintrag = self.deutung["beschreibungen"].get(knoten_id)
        if not eintrag:
            return ""
        return _md(eintrag["text"]) + (" *(veraltet)*" if eintrag["veraltet"] else "")

    def kante_kurz(self, kanten_id: str) -> str:
        kante = self.kanten.get(kanten_id)
        if kante is None:
            return _md(kanten_id)
        return f"{self.kn(kante['von'])} → {self.kn(kante['nach'])} (Gewicht {kante['gewicht']})"

    def befund_titel(self, befund: dict[str, Any]) -> str:
        beleg = befund["beleg"]
        if befund["regel"] == "zyklus":
            arten = {"datei": "Dateien", "paket": "Paketen", "modul": "Modulen"}
            titel = f"Zyklus aus {len(beleg['knoten'])} {arten[beleg['ebene']]}"
            if "kantenart" in beleg:
                titel += f" ({beleg['kantenart']})"
            return titel + (" mit Tests" if beleg["rolle"] == "mit-tests" else "")
        if befund["regel"] == "jni-ohne-gegenstueck":
            return f"JNI ohne Gegenstück: {beleg['funktion']}"
        if befund["regel"] == "unaufgeloest":
            return f"{len(beleg['importe'])} unaufgelöste Importe"
        return befund["regel"]

    def baue(self) -> str:
        z: list[str] = []
        ziel = self.messung["ziel"]
        z.append(f"# Karte · {_md(ziel['name'])}")
        z.append("")
        commit = ziel.get("git_commit")
        stand = f"Commit `{commit[:7]}`" if commit else "Ohne Git-Commit"
        if ziel.get("git_aenderungen"):
            stand += " mit nicht committeten Änderungen"
        z.append(
            f"{stand}. Die interaktive Karte liegt in [karte.html](karte.html) und läuft offline "
            "im Browser. Diese Datei fasst sie für GitHub und Git-Diff zusammen."
        )
        quellen = "`daidalos.json`" + (" und `deutung.json`" if self.deutung_da else "")
        z.append("")
        z.append(
            f"Erzeugt von Daidalos {__version__} aus {quellen}. Gemessenes und Gedeutetes "
            "sind getrennt: Beschreibungen und Einschätzungen stammen aus der Deutung."
        )
        z += self.ueberblick()
        z += self.module()
        z += self.gradle()
        z += self.bereiche()
        z += self.befunde_md()
        return "\n".join(z).rstrip("\n") + "\n"

    @property
    def deutung_da(self) -> bool:
        return any(self.deutung[s] for s in ("beschreibungen", "bereiche", "einschaetzungen"))

    def ueberblick(self) -> list[str]:
        knoten = self.messung["knoten"]
        dateien = [k for k in knoten if k["art"] == "datei"]
        zaehle = lambda art: sum(1 for k in knoten if k["art"] == art)  # noqa: E731
        datei_kanten = [
            k
            for k in self.messung["kanten"]
            if k["art"] == "nutzt" and k["von"].startswith("datei:")
        ]
        zyklen = [b for b in self.messung["befunde"] if b["regel"] == "zyklus"]
        z = ["", "## Überblick", "", "| Größe | Wert |", "| --- | ---: |"]
        z.append(f"| Module | {zaehle('modul')} |")
        z.append(f"| Ordner außerhalb der Module | {zaehle('ordner')} |")
        z.append(f"| Pakete | {zaehle('paket')} |")
        z.append(
            f"| Dateien (davon fremd) | {len(dateien)} "
            f"({sum(1 for d in dateien if d.get('fremd'))}) |"
        )
        z.append(f"| Zeilen | {sum(d.get('zeilen', 0) for d in dateien)} |")
        z.append(f"| `nutzt`-Kanten zwischen Dateien | {len(datei_kanten)} |")
        z.append(f"| Zyklen | {len(zyklen)} |")
        return z

    def _gruppentabelle(self, art: str) -> list[str]:
        gruppen = sorted(
            (k for k in self.messung["knoten"] if k["art"] == art), key=lambda k: k["id"]
        )
        kopf = "Modul" if art == "modul" else "Ordner"
        z = [
            "",
            f"| {kopf} | Dateien | Zeilen | Fan-in | Fan-out | Instabilität | Beschreibung |",
            "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for g in gruppen:
            m = g.get("metriken", {})
            z.append(
                f"| {self.kn(g['id'])} | {g.get('dateien', 0)} | {g.get('zeilen', 0)} | "
                f"{m.get('fan_in', 0)} | {m.get('fan_out', 0)} | "
                f"{_zahl(m.get('instabilitaet'))} | {self.beschreibung(g['id'])} |"
            )
        return z if gruppen else []

    def module(self) -> list[str]:
        z = ["", "## Module"]
        z.append("")
        z.append(
            "Fan-in und Fan-out zählen verschiedene Module (und Ordner), die über produktive "
            "`nutzt`-Kanten verbunden sind; Instabilität = Fan-out / (Fan-in + Fan-out)."
        )
        modul = self._gruppentabelle("modul")
        z += modul or ["", "Keine Gradle-Module gefunden."]
        ordner = self._gruppentabelle("ordner")
        if ordner:
            z += ["", "### Ordner außerhalb der Module", *ordner]
        return z

    def gradle(self) -> list[str]:
        kanten = [k for k in self.messung["kanten"] if k["art"].startswith("gradle-")]
        z = ["", "## Gradle-Abhängigkeiten", ""]
        if not kanten:
            return [*z, "Keine Projekt-Abhängigkeiten zwischen Modulen."]
        for k in sorted(kanten, key=lambda k: (k["von"], k["nach"], k["art"])):
            belege = "Beleg" if k["gewicht"] == 1 else "Belege"
            z.append(
                f"- {self.kn(k['von'])} → {self.kn(k['nach'])} · `{k['art']}` "
                f"({k['gewicht']} {belege})"
            )
        return z

    def bereiche(self) -> list[str]:
        if not self.deutung["bereiche"]:
            return []
        z = ["", "## Bereiche", "", "Aus der Deutung."]
        for b in self.deutung["bereiche"]:
            z += ["", f"### {_md(b['name'])}", ""]
            if b["beschreibung"]:
                z += [_md(b["beschreibung"]), ""]
            z.append("Knoten: " + (", ".join(self.kn(k) for k in b["knoten"]) or "–"))
        return z

    def einschaetzung(self, marke: str, e: dict[str, Any]) -> list[str]:
        befund = self.befunde[e["befund"]]
        verweis = self.bf(befund["id"], self.befund_titel(befund))
        z = [f"{marke} **{_md(e['titel'])}** ({verweis})"]
        if e["begruendung"]:
            z.append(f"   {_md(e['begruendung'])}")
        if e["vorschlag"]:
            z.append(f"   Vorschlag: {_md(e['vorschlag'])}")
        return z

    def befunde_md(self) -> list[str]:
        z = ["", "## Befunde"]
        einsch = self.deutung["einschaetzungen"]
        if einsch:
            z += ["", "### Einschätzungen", "", "Aus der Deutung, nach Priorität.", ""]
            priorisiert = [e for e in einsch if e["prioritaet"] is not None]
            nachrangig = [e for e in einsch if e["prioritaet"] is None]
            for nr, e in enumerate(priorisiert, 1):
                z += self.einschaetzung(f"{nr}.", e)
            if priorisiert and nachrangig:
                z.append("")
            # Ohne Priorität: kleines Zeichen „nachrangig“ statt einer Zahl.
            for e in nachrangig:
                z += self.einschaetzung("- <sub>nachrangig</sub>", e)
        zyklen = [b for b in self.messung["befunde"] if b["regel"] == "zyklus"]
        z += ["", "### Zyklen"]
        if not zyklen:
            z += ["", "Keine Zyklen."]
        for ebene in ("modul", "paket", "datei"):
            auf_ebene = [b for b in zyklen if b["beleg"]["ebene"] == ebene]
            if not auf_ebene:
                continue
            auf_ebene.sort(
                key=lambda b: (
                    b["beleg"]["rolle"] != "produktiv",
                    b["beleg"].get("kantenart") or "",
                    -len(b["knoten"]),
                    b["id"],
                )
            )
            z += ["", f"#### {_EBENEN_TITEL[ebene]}"]
            for b in auf_ebene:
                z += ["", *self.zyklus(b)]
        uebrige: dict[str, int] = {}
        for b in self.messung["befunde"]:
            if b["regel"] != "zyklus":
                uebrige[b["regel"]] = uebrige.get(b["regel"], 0) + 1
        namen = {
            "jni-ohne-gegenstueck": "JNI-Funktionen ohne Gegenstück",
            "unaufgeloest": "Dateien mit unaufgelösten internen Importen",
        }
        z += ["", "### Weitere Befunde", ""]
        if not uebrige:
            z.append("Keine.")
        for regel, anzahl in sorted(uebrige.items()):
            z.append(f"- {namen.get(regel, regel)}: {anzahl}")
        return z

    def zyklus(self, befund: dict[str, Any]) -> list[str]:
        beleg = befund["beleg"]
        z = [f"- **{self.bf(befund['id'], self.befund_titel(befund))}**"]
        z.append("  - Mitglieder: " + ", ".join(self.kn(k) for k in beleg["knoten"]))
        if beleg["einstiege"]:
            teile = [
                f"{self.kn(e['knoten'])} (von {', '.join(self.kn(q) for q in e['quellen'])})"
                for e in beleg["einstiege"]
            ]
            z.append("  - Einstiege: " + "; ".join(teile))
        else:
            z.append("  - Einstiege: keine")
        if beleg["trennstelle"]:
            z.append("  - Günstigste Trennstelle: " + self.kante_kurz(beleg["trennstelle"]))
        elif beleg.get("kleinste_trennmenge"):
            teile = [self.kante_kurz(k) for k in beleg["kleinste_trennmenge"]]
            z.append("  - Keine einzelne Trennstelle; kleinste Trennmenge: " + "; ".join(teile))
        else:
            z.append("  - Keine einzelne Trennstelle")
        if beleg.get("enthaelt_produktiv"):
            z.append(
                "  - Enthält die produktiven Zyklen "
                + ", ".join(
                    self.bf(i, self.befund_titel(self.befunde[i]))
                    for i in beleg["enthaelt_produktiv"]
                )
            )
        if beleg.get("unsicher"):
            z.append("  - Eine unsichere Kante ist beteiligt.")
        return z


def baue_karte_md(messung: dict[str, Any], deutung: dict[str, Any] | None) -> str:
    return _MdBauer(strukturansicht(messung), deutung).baue()
