# Start FabricAssist locally on a physical Android device

Use this runbook for the local development build on a USB-connected Android
device. It uses the mock vision provider, so it does not require a paid model
API or process customer images with an external provider.

## Prerequisites

- Run `make bootstrap` once.
- Enable USB debugging on the device and accept the computer's ADB prompt.
- Confirm the device is visible:

  ```bash
  adb devices
  ```

When more than one device is attached, set its serial once and use it in every
ADB command:

```bash
export ANDROID_SERIAL=<device-serial>
```

## 1. Start the local backend

From the repository root, use the Makefile as the stable local interface:

```bash
FABRICASSIST_VISION_PROVIDER=mock make up
make migrate
make seed
```

`make migrate` applies the current Alembic schema. `make seed` creates the
idempotent development tenant required for local registration. Do not skip
either command after a new or reset local database.

## 2. Connect the device to local services

In a second terminal, forward the three local ports used by the development
build:

```bash
adb -s "$ANDROID_SERIAL" reverse tcp:8000 tcp:8000  # API
adb -s "$ANDROID_SERIAL" reverse tcp:8081 tcp:8081  # Expo Metro
adb -s "$ANDROID_SERIAL" reverse tcp:9000 tcp:9000  # MinIO direct uploads
adb -s "$ANDROID_SERIAL" reverse --list
```

For a single connected device, `-s "$ANDROID_SERIAL"` may be omitted.

## 3. Start Metro

Keep this command running in the second terminal:

```bash
pnpm --dir frontend --filter fabricassist-app exec expo start --dev-client --lan
```

Wait for Metro to finish its first Android bundle before opening the app. A
temporary `Bundling ...` screen is normal; `Unable to load script` usually
means Metro is not running or the port-8081 reverse mapping is missing.

## 4. Build, install, and launch

For a fresh or changed native build, use Expo to build, install, and launch the
app:

```bash
pnpm --dir frontend --filter fabricassist-app android -- --device "$ANDROID_SERIAL"
```

For the known physical arm64 device, this direct Gradle fallback builds an
ABI-compatible debug APK:

```bash
(cd frontend/apps/client/android && \
  ./gradlew :app:assembleDebug -PreactNativeArchitectures=arm64-v8a)
adb -s "$ANDROID_SERIAL" install -r -d \
  frontend/apps/client/android/app/build/outputs/apk/debug/app-debug.apk
```

If the development APK is already installed, relaunch it without rebuilding:

```bash
adb -s "$ANDROID_SERIAL" shell am force-stop com.fabricassist.app
adb -s "$ANDROID_SERIAL" shell monkey -p com.fabricassist.app 1
```

`pnpm ... android` already installs and launches the app, so do not run the
two ADB relaunch commands after it unless you specifically need to restart it.

## Local troubleshooting

| Symptom | Check |
| --- | --- |
| Cannot register or sign in | Run `make seed`; local registration requires the development tenant. |
| Image upload fails | Confirm `adb -s "$ANDROID_SERIAL" reverse --list` includes port `9000`. |
| `Unable to load script` | Keep Metro running and confirm port `8081` is reversed. |
| API requests fail | Confirm port `8000` is reversed and run `make smoke`. |

## Stop local services

Stop Metro with `Ctrl-C`, then from the repository root run:

```bash
make down
```
