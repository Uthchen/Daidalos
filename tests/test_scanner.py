from __future__ import annotations

import hashlib
import io
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from conftest import git, git_init
from daidalos import scanner
from daidalos.export import als_json, schreibe_json
from daidalos.konfiguration import Konfiguration, ScanKonfiguration, lade_konfiguration
from daidalos.scanner import finde_dateien, scanne

ERWARTETE_DATEIEN = [
    ".gitignore",
    "README.md",
    "app/build.gradle.kts",
    "app/src/main/kotlin/de/beispiel/app/Haupt.kt",
    "app/src/main/kotlin/de/beispiel/app/Leiste-crlf.kt",
    "core/build.gradle.kts",
    "core/src/main/cpp/fremd/mini.c",
    "core/src/main/kotlin/de/beispiel/zeichnen/Punkt.kt",
    "core/src/main/kotlin/de/beispiel/zeichnen/Strich.kt",
    "daidalos.toml",
    "daten/logo.bin",
    "gradle/pruefungen.gradle.kts",
    "settings.gradle.kts",
]


def _konfig(ziel: Path) -> Konfiguration:
    return lade_konfiguration(ziel / "daidalos.toml")


def _knoten(daten: dict[str, Any], pfad: str) -> dict[str, Any]:
    return next(k for k in daten["knoten"] if k["pfad"] == pfad)


# ---------------------------------------------------------------- Ausschlüsse


def test_ausschluesse_ohne_git(mini_kopie: Path) -> None:
    pfade, git_modus = finde_dateien(mini_kopie, _konfig(mini_kopie))
    assert not git_modus
    assert pfade == ERWARTETE_DATEIEN


def test_ausschluesse_mit_git(mini_git: Path) -> None:
    # Nicht getrackt, aber nicht ignoriert: wird erfasst.
    (mini_git / "Neu.kt").write_text("class Neu\n", encoding="utf-8")
    pfade, git_modus = finde_dateien(mini_git, _konfig(mini_git))
    assert git_modus
    assert pfade == sorted([*ERWARTETE_DATEIEN, "Neu.kt"])


def test_git_modus_traegt_commit_und_aenderungen(mini_git: Path) -> None:
    daten = scanne(mini_git, _konfig(mini_git)).daten
    kopf = git(mini_git, "rev-parse", "HEAD").strip()
    assert daten["ziel"] == {"name": "mini_gradle", "git_commit": kopf, "git_aenderungen": False}

    (mini_git / "README.md").write_text("geändert\n", encoding="utf-8")
    assert scanne(mini_git, _konfig(mini_git)).daten["ziel"]["git_aenderungen"] is True


def test_aenderung_an_ausgeschlossener_datei_zaehlt_nicht(mini_git: Path) -> None:
    (mini_git / "entwurf" / "Alt.kt").write_text("// geändert\n", encoding="utf-8")
    assert scanne(mini_git, _konfig(mini_git)).daten["ziel"]["git_aenderungen"] is False


def test_ohne_git_sind_git_felder_null(mini_kopie: Path) -> None:
    ziel = scanne(mini_kopie, _konfig(mini_kopie)).daten["ziel"]
    assert ziel["git_commit"] is None
    assert ziel["git_aenderungen"] is None


def test_eigene_ausgabe_wird_nicht_erfasst(mini_git: Path) -> None:
    ausgabe = mini_git / "docs" / "daidalos" / "daidalos.json"
    schreibe_json({"alt": True}, ausgabe)
    pfade, _ = finde_dateien(mini_git, _konfig(mini_git))
    assert not any(p.startswith("docs/daidalos/") for p in pfade)


def test_fremd_markierung(mini_kopie: Path) -> None:
    daten = scanne(mini_kopie, _konfig(mini_kopie)).daten
    assert _knoten(daten, "core/src/main/cpp/fremd/mini.c")["fremd"] is True
    assert "fremd" not in _knoten(daten, "core/src/main/kotlin/de/beispiel/zeichnen/Strich.kt")


def test_git_nicht_aufrufbar_faellt_auf_durchlauf_zurueck(
    mini_git: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def kein_git(*_: Any, **__: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(scanner.subprocess, "run", kein_git)
    warnungen: list[str] = []
    pfade, git_modus = finde_dateien(mini_git, _konfig(mini_git), warne=warnungen.append)
    assert not git_modus
    assert pfade == ERWARTETE_DATEIEN
    assert any("Rückfall" in w for w in warnungen)


# ---------------------------------------------------------------- Worktrees


def _lege_worktree_an(ziel: Path) -> None:
    unter = ziel / ".claude" / "worktrees" / "x"
    unter.mkdir(parents=True)
    (unter / "Kopie.kt").write_text("class Kopie\n", encoding="utf-8")
    git_init(unter)
    git(unter, "add", "-A")
    git(unter, "commit", "-q", "-m", "x")


def test_verschachteltes_repo_mit_git_wird_nicht_erfasst(mini_git: Path) -> None:
    _lege_worktree_an(mini_git)
    pfade, git_modus = finde_dateien(mini_git, _konfig(mini_git))
    assert git_modus
    assert not any(p.startswith(".claude/") for p in pfade)


def test_verschachteltes_repo_ohne_git_wird_nicht_erfasst(mini_kopie: Path) -> None:
    _lege_worktree_an(mini_kopie)
    pfade, _ = finde_dateien(mini_kopie, _konfig(mini_kopie))
    assert not any(p.startswith(".claude/") for p in pfade)


# ---------------------------------------------------------------- Durchlauf


def test_ausgeschlossener_ordner_wird_nie_betreten(
    mini_kopie: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ausgeschlossene Ordner dürfen nicht einmal gelistet werden (160-GB-Fall)."""
    tief = mini_kopie / "messdaten" / "gross" / "noch-tiefer"
    tief.mkdir(parents=True)
    (tief / "video.bin").write_bytes(b"\0" * 10)
    (mini_kopie / "build" / "unter").mkdir()

    gelistet: list[str] = []
    echtes_scandir = os.scandir

    def beobachtetes_scandir(pfad: Any = ".") -> Any:
        gelistet.append(Path(pfad).resolve().relative_to(mini_kopie.resolve()).as_posix())
        return echtes_scandir(pfad)

    monkeypatch.setattr(os, "scandir", beobachtetes_scandir)
    konfiguration = Konfiguration(scan=ScanKonfiguration(ausschliessen=("messdaten/",)))
    pfade, _ = finde_dateien(mini_kopie, konfiguration)

    assert "." in gelistet  # der Beobachter greift
    assert "core/src/main/kotlin" in gelistet
    for ordner in gelistet:
        assert not ordner.startswith("messdaten"), ordner
        assert not ordner.startswith("build"), ordner
        assert "/build" not in ordner, ordner
    assert not any(p.startswith("messdaten/") for p in pfade)


def test_gitignore_im_durchlauf_beachtet_ordner(mini_kopie: Path) -> None:
    (mini_kopie / ".gitignore").write_text("*.log\ngeheim/\n", encoding="utf-8")
    (mini_kopie / "geheim").mkdir()
    (mini_kopie / "geheim" / "a.kt").write_text("x\n", encoding="utf-8")
    pfade, _ = finde_dateien(mini_kopie, Konfiguration())
    assert not any(p.startswith("geheim/") for p in pfade)
    assert "notizen.log" not in pfade


def test_symlinks_werden_nicht_verfolgt(mini_kopie: Path, tmp_path: Path) -> None:
    draussen = tmp_path / "draussen"
    draussen.mkdir()
    (draussen / "Fremd.kt").write_text("x\n", encoding="utf-8")
    try:
        (mini_kopie / "verweis").symlink_to(draussen, target_is_directory=True)
        (mini_kopie / "datei-verweis.kt").symlink_to(draussen / "Fremd.kt")
    except OSError:
        pytest.skip("Symlinks hier nicht erlaubt")
    pfade, _ = finde_dateien(mini_kopie, _konfig(mini_kopie))
    assert not any(p.startswith("verweis") or p == "datei-verweis.kt" for p in pfade)


# ---------------------------------------------------------------- Messen


def test_crlf_und_lf_ergeben_gleichen_hash_und_zeilen(tmp_path: Path) -> None:
    (tmp_path / "lf.kt").write_bytes(b"a\nb\nc\n")
    (tmp_path / "crlf.kt").write_bytes(b"a\r\nb\r\nc\r\n")
    (tmp_path / "cr.kt").write_bytes(b"a\rb\rc\r")
    daten = scanne(tmp_path, Konfiguration()).daten
    lf, crlf, cr = (_knoten(daten, n) for n in ("lf.kt", "crlf.kt", "cr.kt"))
    assert lf["hash"] == crlf["hash"] == cr["hash"]
    assert lf["hash"] == "sha256:" + hashlib.sha256(b"a\nb\nc\n").hexdigest()
    assert lf["zeilen"] == crlf["zeilen"] == cr["zeilen"] == 3
    assert crlf["bytes"] == 9


def test_crlf_ueber_blockgrenze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner, "BLOCK", 3)
    monkeypatch.setattr(scanner, "BINAER_PRUEFLAENGE", 2)
    inhalt = b"ab\r\ncd\r\r\nef\r"
    hash_wert, zeilen, binaer = scanner._miss_inhalt(io.BytesIO(inhalt), True)
    erwartet = b"ab\ncd\n\nef\n"
    assert not binaer
    assert hash_wert == "sha256:" + hashlib.sha256(erwartet).hexdigest()
    assert zeilen == 4


@pytest.mark.parametrize(
    ("inhalt", "zeilen"),
    [(b"", 0), (b"x", 1), (b"x\n", 1), (b"x\ny", 2), (b"\n\n", 2)],
)
def test_zeilenzaehlung(inhalt: bytes, zeilen: int) -> None:
    assert scanner._miss_inhalt(io.BytesIO(inhalt), True)[1] == zeilen


def test_binaer_erkennung(tmp_path: Path) -> None:
    roh = b"PNG\0\r\n\x01"
    (tmp_path / "bild.png").write_bytes(roh)
    (tmp_path / "spaet.kt").write_bytes(b"a" * (9 * 1024) + b"\0")
    daten = scanne(tmp_path, Konfiguration()).daten
    bild = _knoten(daten, "bild.png")
    assert bild["sprache"] == "binaer"
    assert "zeilen" not in bild
    assert bild["hash"] == "sha256:" + hashlib.sha256(roh).hexdigest()
    # Null-Byte erst nach 8 KiB: gilt als Text.
    assert _knoten(daten, "spaet.kt")["sprache"] == "kotlin"


def test_gradle_skripte_sind_gradle_kotlin(mini_kopie: Path) -> None:
    # Jede Datei *.gradle.kts zählt als gradle-kotlin, nicht nur build/settings (A05b).
    daten = scanne(mini_kopie, _konfig(mini_kopie)).daten
    for pfad in ("gradle/pruefungen.gradle.kts", "app/build.gradle.kts", "settings.gradle.kts"):
        assert _knoten(daten, pfad)["sprache"] == "gradle-kotlin"


def test_grosse_datei_ohne_zeilen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner, "GROSSE_DATEI", 10)
    (tmp_path / "gross.txt").write_bytes(b"0123456789\nabc\n")
    knoten = _knoten(scanne(tmp_path, Konfiguration()).daten, "gross.txt")
    assert "zeilen" not in knoten
    assert knoten["hash"].startswith("sha256:")
    assert knoten["bytes"] == 15


def test_lesefehler_bricht_nicht_ab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "gut.kt").write_text("x\n", encoding="utf-8")
    (tmp_path / "kaputt.kt").write_text("y\n", encoding="utf-8")
    echtes_oeffnen = scanner._oeffne

    def oeffne(pfad: Path) -> Any:
        if pfad.name == "kaputt.kt":
            raise PermissionError(13, "Zugriff verweigert")
        return echtes_oeffnen(pfad)

    monkeypatch.setattr(scanner, "_oeffne", oeffne)
    warnungen: list[str] = []
    daten = scanne(tmp_path, Konfiguration(), warne=warnungen.append).daten
    kaputt = _knoten(daten, "kaputt.kt")
    assert kaputt["lesefehler"] is True
    assert "hash" not in kaputt
    assert "zeilen" not in kaputt
    assert "hash" in _knoten(daten, "gut.kt")
    assert any("kaputt.kt" in w for w in warnungen)


# ---------------------------------------------------------------- Determinismus


def test_zwei_laeufe_sind_byte_gleich(mini_git: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    schreibe_json(scanne(mini_git, _konfig(mini_git)).daten, a)
    schreibe_json(scanne(mini_git, _konfig(mini_git)).daten, b)
    assert a.read_bytes() == b.read_bytes()
    assert b"\r\n" not in a.read_bytes()
    assert a.read_bytes().endswith(b"}\n")


def test_ausgabe_ohne_absolute_pfade(mini_kopie: Path) -> None:
    text = als_json(scanne(mini_kopie, _konfig(mini_kopie)).daten)
    assert str(mini_kopie) not in text
    assert mini_kopie.parent.as_posix() not in text
    assert "\\" not in text


def test_git_aufruf_ohne_shell(mini_git: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    aufrufe: list[dict[str, Any]] = []
    echtes_run = subprocess.run

    def run(befehl: list[str], **optionen: Any) -> Any:
        aufrufe.append({"befehl": befehl, **optionen})
        return echtes_run(befehl, **optionen)

    monkeypatch.setattr(scanner.subprocess, "run", run)
    scanne(mini_git, _konfig(mini_git))
    assert aufrufe
    for aufruf in aufrufe:
        assert isinstance(aufruf["befehl"], list)
        assert aufruf["befehl"][0] == "git"
        assert not aufruf.get("shell", False)
