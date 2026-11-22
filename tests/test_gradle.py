from __future__ import annotations

from pathlib import Path

from conftest import BEISPIELE
from daidalos.adapter.baum import parse
from daidalos.adapter.gradle import (
    art_fuer,
    finde_projekt_aufrufe,
    lies_gradle,
    lies_plugins,
    lies_settings_groovy,
    lies_settings_kts,
)


def _aufrufe(quelle: str):
    return finde_projekt_aufrufe(parse("kotlin", quelle.encode("utf-8")))


def test_include_mit_mehreren_argumenten_und_verschachtelt() -> None:
    module = lies_settings_kts(b'include(":a", ":b:c")\ninclude("d")\n', print)
    assert module == {":a": "a", ":b:c": "b/c", ":d": "d"}


def test_project_dir_wird_angewendet() -> None:
    quelle = b'include(":x")\nproject(":x").projectDir = file("woanders/x")\n'
    assert lies_settings_kts(quelle, print) == {":x": "woanders/x"}


def test_project_dir_nicht_einfach_ergibt_warnung() -> None:
    warnungen: list[str] = []
    quelle = b'include(":x")\nproject(":x").projectDir = File(rootDir, "y")\n'
    assert lies_settings_kts(quelle, warnungen.append) == {":x": "x"}
    assert any("projectDir" in w for w in warnungen)


def test_groovy_settings_grob() -> None:
    assert lies_settings_groovy("include ':a', ':b'\n// include ':c'\n") == {":a": "a", ":b": "b"}


def test_kmp_quellsatz_und_konfiguration() -> None:
    aufrufe = _aufrufe(
        """
kotlin {
    sourceSets {
        commonMain.dependencies { api(project(":kern")) }
        val jvmTest by getting { dependencies { implementation(project(":t")) } }
        commonTest { dependencies { implementation(project(":u")) } }
    }
}
"""
    )
    gefunden = {(a.nach, a.konfiguration, a.quellsatz, a.bedingt) for a in aufrufe}
    assert gefunden == {
        (":kern", "api", "commonMain", False),
        (":t", "implementation", "jvmTest", False),
        (":u", "implementation", "commonTest", False),
    }


def test_bedingte_abhaengigkeit() -> None:
    aufrufe = _aufrufe(
        'dependencies {\n  if (hasProperty("x")) { implementation(project(":y")) }\n'
        '  afterEvaluate { api(project(":z")) }\n  implementation(project(":w"))\n}\n'
    )
    assert {a.nach: a.bedingt for a in aufrufe} == {":y": True, ":z": True, ":w": False}


def test_huellen_und_keine_abhaengigkeiten() -> None:
    aufrufe = _aufrufe(
        'dependencies {\n  implementation(platform(project(":bom")))\n'
        '  testImplementation(testFixtures(project(":f")))\n}\n'
        'tasks.named("x") { dependsOn(project(":d")) }\n'
    )
    assert {(a.nach, a.konfiguration) for a in aufrufe} == {
        (":bom", "implementation"),
        (":f", "testImplementation"),
    }


def test_wurzelweit_in_subprojects() -> None:
    aufrufe = _aufrufe(
        "subprojects {\n  plugins.withType<X> {\n"
        '    dependencies.add("detektPlugins", project(":regeln"))\n  }\n}\n'
    )
    assert len(aufrufe) == 1
    assert aufrufe[0].konfiguration == "detektPlugins"
    assert aufrufe[0].wurzelweit
    assert not aufrufe[0].bedingt


def test_art_fuer() -> None:
    assert art_fuer("api", None) == "gradle-api"
    assert art_fuer("implementation", None) == "gradle-impl"
    assert art_fuer("implementation", "jvmTest") == "gradle-test"
    assert art_fuer("androidTestImplementation", None) == "gradle-test"
    assert art_fuer("testImplementation", None) == "gradle-test"
    assert art_fuer("compileOnly", None) == "gradle-compileonly"
    assert art_fuer("detektPlugins", None) == "gradle-plugin"
    assert art_fuer("runtimeOnly", None) == "gradle-sonstige"


def test_plugins() -> None:
    wurzel = parse(
        "kotlin",
        b'plugins {\n  alias(libs.plugins.kotlin.jvm) apply false\n  id("com.a") version "1"\n'
        b'  kotlin("jvm")\n}\n',
    )
    assert lies_plugins(wurzel) == ("com.a", "kotlin.jvm", "org.jetbrains.kotlin.jvm")


def test_beispielprojekt() -> None:
    ziel = BEISPIELE / "mini_modulgraph"
    erfasst = {p.relative_to(ziel).as_posix() for p in ziel.rglob("*") if p.is_file()}
    ergebnis = lies_gradle(ziel, erfasst, print)
    assert [m.gradle_pfad for m in ergebnis.module] == [
        ":anwendung",
        ":kern",
        ":kern-labor",
        ":nativ",
        ":regeln",
    ]
    kanten = {(a.von, a.nach, a.art, a.beleg["bedingt"]) for a in ergebnis.abhaengigkeiten}
    assert (":kern-labor", ":kern", "gradle-api", False) in kanten
    assert (":anwendung", ":kern-labor", "gradle-impl", True) in kanten
    assert (":anwendung", ":kern-labor", "gradle-test", False) in kanten
    regeln = {a.von for a in ergebnis.abhaengigkeiten if a.art == "gradle-plugin"}
    assert regeln == {":anwendung", ":kern", ":kern-labor", ":nativ"}
    wurzel = [a for a in ergebnis.abhaengigkeiten if a.art == "gradle-plugin"]
    assert all(a.beleg["quelle"] == "wurzel" for a in wurzel)


def test_ohne_settings_keine_module(tmp_path: Path) -> None:
    assert lies_gradle(tmp_path, set(), print).module == []
