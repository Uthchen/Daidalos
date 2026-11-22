plugins {
    id("com.android.application")
}

dependencies {
    implementation(project(":kern"))
    implementation(project(":nativ"))
    testImplementation(project(":kern-labor"))
    if (hasProperty("probe")) {
        implementation(project(":kern-labor"))
    }
}
