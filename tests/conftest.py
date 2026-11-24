"""Gemeinsame Fixtures und der Schalter ``--aktualisiere-golden``."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

BEISPIELE = Path(__file__).parent / "beispiele"
ERWARTET = Path(__file__).parent / "erwartet"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--aktualisiere-golden",
        action="store_true",
        default=False,
        help="Golden-Dateien unter tests/erwartet/ neu schreiben",
    )


@pytest.fixture
def aktualisiere_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--aktualisiere-golden"))


def git(ordner: Path, *argumente: str) -> str:
    lauf = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@beispiel.invalid",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(ordner),
            *argumente,
        ],
        check=True,
        capture_output=True,
    )
    return lauf.stdout.decode("utf-8")


def git_init(ordner: Path) -> None:
    git(ordner, "init", "-q")
    # Zeilenenden nicht umschreiben, damit die CRLF-Datei unverändert bleibt.
    git(ordner, "config", "core.autocrlf", "false")


@pytest.fixture
def mini_kopie(tmp_path: Path) -> Path:
    """Kopie des Beispielprojekts ohne Git."""
    ziel = tmp_path / "mini_gradle"
    shutil.copytree(BEISPIELE / "mini_gradle", ziel)
    return ziel


@pytest.fixture
def mini_git(mini_kopie: Path) -> Path:
    """Kopie des Beispielprojekts als Git-Repo mit einem Commit."""
    git_init(mini_kopie)
    git(mini_kopie, "add", "-A")
    git(mini_kopie, "commit", "-q", "-m", "Anfang")
    return mini_kopie


def js(seite: Any, ausdruck: str) -> None:
    """Führt einen Ausdruck in der Browser-Probe aus, ohne seinen Wert zurückzugeben.

    ``void (…)`` darum: Playwright wartet sonst auf ein zurückgegebenes Promise oder scheitert
    daran, Cytoscape-Sammlungen zu übertragen. Für Ausdrücke, deren Wert gebraucht wird, bleibt
    ``seite.evaluate``. Mehrere Anweisungen mit Komma statt Semikolon verbinden.
    """
    seite.evaluate("void (" + ausdruck + ")")
