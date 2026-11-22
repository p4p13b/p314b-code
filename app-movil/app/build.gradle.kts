plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Número de versión: el de la corrida de GitHub Actions (cada APK nueva
// se instala encima de la anterior sin perder los borradores).
val corrida = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()

android {
    namespace = "space.p314b.tallercito"
    compileSdk = 34

    defaultConfig {
        applicationId = "space.p314b.tallercito"
        minSdk = 26
        targetSdk = 34
        versionCode = corrida
        versionName = "1.0.$corrida"
    }

    // La firma: el almacén que indica TALLERCITO_KS (lo arma el workflow
    // desde el repo privado). Sin él, la firma de depuración.
    val ks = System.getenv("TALLERCITO_KS")
    signingConfigs {
        if (ks != null && file(ks).exists()) {
            create("propia") {
                storeFile = file(ks)
                storePassword = System.getenv("TALLERCITO_KS_CLAVE")
                keyAlias = System.getenv("TALLERCITO_KS_ALIAS") ?: "tallercito"
                keyPassword = System.getenv("TALLERCITO_KS_CLAVE")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("propia") ?: signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2024.09.03")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
}
