from __future__ import annotations

import pytest

from daidalos.sprachen import erkenne_sprache


@pytest.mark.parametrize(
    ("pfad", "sprache"),
    [
        ("a/B.kt", "kotlin"),
        ("skript.kts", "kotlin"),
        ("build.gradle.kts", "gradle-kotlin"),
        ("core/settings.gradle.kts", "gradle-kotlin"),
        ("app/build.gradle", "groovy-gradle"),
        ("X.java", "java"),
        ("a.c", "c"),
        ("a.CPP", "cpp"),
        ("a.h", "cpp"),
        ("a.inl", "cpp"),
        ("Mod.Build.cs", "csharp"),
        ("a.py", "python"),
        ("a.verse", "verse"),
        ("README.md", "markdown"),
        ("a.json", "json"),
        ("a.toml", "toml"),
        ("a.yml", "yaml"),
        ("a.xml", "xml"),
        ("Config/Default.ini", "ini"),
        ("a.sh", "shell"),
        ("a.ps1", "powershell"),
        ("a.bat", "batch"),
        ("CMakeLists.txt", "cmake"),
        ("x.cmake", "cmake"),
        ("gradle.properties", "properties"),
        ("notiz.txt", "text"),
        ("schema.sql", "sql"),
        ("gradle.lockfile", "unbekannt"),
        ("Makefile", "unbekannt"),
        (".gitignore", "unbekannt"),
        ("a.xyz", "unbekannt"),
    ],
)
def test_sprache_nach_name_und_endung(pfad: str, sprache: str) -> None:
    assert erkenne_sprache(pfad) == sprache
