"""Erkennung der Sprache einer Datei nach Dateiname und Endung."""

from __future__ import annotations

UNBEKANNT = "unbekannt"
BINAER = "binaer"

# Volle Dateinamen haben Vorrang vor Endungen.
DATEINAMEN: dict[str, str] = {
    "build.gradle": "groovy-gradle",
    "settings.gradle": "groovy-gradle",
    "CMakeLists.txt": "cmake",
}

# Mehrteilige Endungen (klein geschrieben) haben Vorrang vor der letzten Endung: Jedes Gradle-Skript
# in Kotlin (build.gradle.kts, settings.gradle.kts, gradle/x.gradle.kts) ist gradle-kotlin.
MEHRTEILIGE_ENDUNGEN: dict[str, str] = {
    ".gradle.kts": "gradle-kotlin",
}

# Endungen klein geschrieben, mit Punkt.
ENDUNGEN: dict[str, str] = {
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".inl": "cpp",
    ".cs": "csharp",
    ".py": "python",
    ".pyi": "python",
    ".verse": "verse",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".ini": "ini",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".bat": "batch",
    ".cmd": "batch",
    ".cmake": "cmake",
    ".gradle": "groovy-gradle",
    ".properties": "properties",
    ".txt": "text",
    ".sql": "sql",
}


def erkenne_sprache(pfad: str) -> str:
    """Liefert die Sprache für einen relativen Pfad mit ``/`` als Trenner.

    Binärdateien erkennt erst der Scanner am Inhalt; hier zählt nur der Name.
    """
    name = pfad.rsplit("/", 1)[-1]
    if name in DATEINAMEN:
        return DATEINAMEN[name]
    klein = name.lower()
    for endung, sprache in MEHRTEILIGE_ENDUNGEN.items():
        if klein.endswith(endung) and len(klein) > len(endung):
            return sprache
    punkt = name.rfind(".")
    if punkt <= 0:
        return UNBEKANNT
    return ENDUNGEN.get(name[punkt:].lower(), UNBEKANNT)
