"""Golden-Test: Ausgabe für das Beispielprojekt ohne Git.

Neu schreiben mit ``uv run pytest --aktualisiere-golden``.
"""

from __future__ import annotations

from pathlib import Path

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main

GOLDEN = ERWARTET / "mini_gradle.daidalos.json"


def test_mini_gradle_golden(tmp_path: Path, aktualisiere_golden: bool) -> None:
    ausgabe = tmp_path / "daidalos.json"
    # Das Beispiel liegt im Daidalos-Repo, hat aber selbst kein .git: Verzeichnisdurchlauf.
    assert main(["scan", str(BEISPIELE / "mini_gradle"), "--ausgabe", str(ausgabe)]) == 0
    if aktualisiere_golden:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_bytes(ausgabe.read_bytes())
    assert ausgabe.read_bytes() == GOLDEN.read_bytes()
