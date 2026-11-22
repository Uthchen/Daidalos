plugins {
    alias(libs.plugins.kotlin.jvm) apply false
}

subprojects {
    // eigene Regeln für alle Module
    dependencies.add("detektPlugins", project(":regeln"))
}
