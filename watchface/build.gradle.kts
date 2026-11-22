plugins {
    id("com.android.application")
}

android {
    // Change this to your own unique ID before publishing to Google Play.
    namespace = "com.mywatchfaces.meridian"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mywatchfaces.meridian"
        // Wear OS 4 (API 33) and later = Watch Face Format v1 supported (Pixel Watch 1st gen / 2 / 3 / 4)
        minSdk = 33
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }

    buildTypes {
        release {
            // WFF watch faces must not contain dex files (minSdk >= 33).
            // Enabling R8 strips the empty dex so the bundle passes the check.
            isMinifyEnabled = true
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("debug") // replace with your own key before publishing
        }
    }
}
