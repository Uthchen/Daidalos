"""Abgeleitete Ids und Felder, die seit A08 nicht mehr in ``daidalos.json`` stehen.

- ``ruft``-Kanten tragen keine ``id``; sie lautet ``kante:ruft:<von>-><nach>:<rolle>``.
- Funktionsknoten tragen kein ``datei``; die Datei ist der Teil der Id vor ``#`` ohne
  ``funktion:``.
"""

from __future__ import annotations

from typing import Any


def kanten_id(kante: dict[str, Any]) -> str:
    """Id einer Kante; bei ``ruft`` aus ``von``, ``nach`` und ``rolle`` gebildet."""
    if "id" in kante:
        return str(kante["id"])
    basis = f"kante:{kante['art']}:{kante['von']}->{kante['nach']}"
    rolle = kante.get("rolle")
    return f"{basis}:{rolle}" if rolle else basis


def datei_der_funktion(funktion: dict[str, Any] | str) -> str:
    """Pfad der Datei einer Funktion (Knoten oder Id), relativ und mit ``/``."""
    funktions_id = funktion if isinstance(funktion, str) else funktion["id"]
    return funktions_id.removeprefix("funktion:").split("#", 1)[0]
