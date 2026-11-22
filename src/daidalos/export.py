"""Schreibt ``daidalos.json`` deterministisch und atomar."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def als_json(daten: dict[str, Any]) -> str:
    """Stabile Textform: sortierte Schlüssel, Einrückung 2, abschließender Umbruch."""
    return json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def schreibe_json(daten: dict[str, Any], ziel: Path) -> None:
    schreibe_text(als_json(daten), ziel)


def schreibe_text(text: str, ziel: Path) -> None:
    """Schreibt UTF-8 mit LF über eine temporäre Datei und ``os.replace``.

    Nie bleibt eine halbe Datei zurück.
    """
    ziel.parent.mkdir(parents=True, exist_ok=True)
    deskriptor, temp_name = tempfile.mkstemp(
        prefix=f".{ziel.name}.", suffix=".tmp", dir=ziel.parent
    )
    try:
        with os.fdopen(deskriptor, "w", encoding="utf-8", newline="\n") as datei:
            datei.write(text)
        os.replace(temp_name, ziel)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
