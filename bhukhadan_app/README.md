# Bhuarjan Flutter App

This project has been ported from React Native to Flutter.

## ⚠️ Prerequisites (Critical)

Your system seems to be missing **Flutter** and **Android SDK** tools (adb). You generally need to install these before you can compile anything.

1.  **Install Flutter SDK**:
    *   Download from [flutter.dev](https://docs.flutter.dev/get-started/install/windows).
    *   Extract it (e.g., to `C:\src\flutter`).
    *   Add `C:\src\flutter\bin` to your **System PATH** environment variables.

2.  **Install Android SDK**:
    *   Install **Android Studio**.
    *   Open Android Studio -> SDK Manager -> Android SDK Command-line Tools.
    *   Add `platform-tools` to your PATH (usually `C:\Users\YOUR_USER\AppData\Local\Android\Sdk\platform-tools`).
    *   This will fix the `'adb' is not recognized` error.

## 🛠️ Setup Project (First Time Only)

Because we converted this from React Native, the `android` and `ios` folders are missing. You must generate them:

1.  Open your terminal in `E:\bhuarjan_app`.
2.  Run the following command:
    ```bash
    flutter create .
    ```
    *This generates the `android`, `ios`, `windows`, etc. folders.*

## 🚀 How to Compile & Run

### 1. Run on an Emulator/Device
Make sure your device is connected (check with `flutter devices`).
```bash
flutter run
```

### 2. Build Android APK
To generate an APK file for installation:
```bash
flutter build apk --release
```
The APK will be found at: `build/app/outputs/flutter-apk/app-release.apk`.

### 3. Build App Bundle (for Play Store)
```bash
flutter build appbundle
```

## Screenshot audit / blocking

- **Android**: `FLAG_SECURE` is enabled on the app window so system screenshots are blank/blocked. Detection of a successful capture is limited on Android; blocked captures are the primary protection.
- **iOS**: Screenshots are **detected** via `userDidTakeScreenshotNotification` and reported to Odoo. iOS does not provide an equivalent of Android `FLAG_SECURE` for fully blocking screenshots of the app UI.
- Detected events show a brief “Screenshot recorded for audit” snackbar, queue offline, and POST to `/api/bhukhadan/audit/screenshot`.
