"""Golden-Test: Ausgabe für das Beispielprojekt ohne Git.

Neu schreiben mit ``uv run pytest --aktualisiere-golden``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import BEISPIELE, ERWARTET
from daidalos.cli import main


@pytest.mark.parametrize(
    "beispiel", ["mini_gradle", "mini_modulgraph", "mini_aufrufe", "mini_markierung"]
)
def test_golden(beispiel: str, tmp_path: Path, aktualisiere_golden: bool) -> None:
    golden = ERWARTET / f"{beispiel}.daidalos.json"
    ausgabe = tmp_path / "daidalos.json"
    # Die Beispiele liegen im Daidalos-Repo, haben aber selbst kein .git: Verzeichnisdurchlauf.
    assert main(["scan", str(BEISPIELE / beispiel), "--ausgabe", str(ausgabe)]) == 0
    if aktualisiere_golden:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(ausgabe.read_bytes())
    assert ausgabe.read_bytes() == golden.read_bytes()
