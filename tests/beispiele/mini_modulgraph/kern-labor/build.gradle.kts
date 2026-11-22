plugins {
    alias(libs.plugins.kotlin.multiplatform)
}

kotlin {
    jvm()

    sourceSets {
        commonMain.dependencies {
            api(project(":kern"))
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
        }
    }
}
