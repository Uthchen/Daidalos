// Erfundenes Gradle-Skript, das per apply(from = ...) eingebunden wuerde.
tasks.register("pruefe") {
    doLast { println("geprueft") }
}
