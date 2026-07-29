# Start FabricAssist locally on a physical Android device

Use this runbook for the local development build on a physical Android device.
It supports both USB and Android 11+ wireless debugging. It uses the mock
vision provider, so it does not require a paid model API or process customer
images with an external provider.

## Select a local connection profile

The local workstation may keep three ignored profile copies beside `.env`:

| Profile | API and upload endpoint | Use when |
| --- | --- | --- |
| `.env.localhost` | `localhost` | Browser/web development on the workstation. |
| `.env.android-usb` | `localhost` | Android device connected through USB with `adb reverse`. |
| `.env.android-wireless` | Workstation LAN IP | Android device connected through trusted Wi-Fi. |

Activate one profile before starting Compose:

```bash
cp .env.android-wireless .env  # or .env.android-usb / .env.localhost
docker compose up -d --force-recreate fabricassist-api fabricassist-worker
```

The profile files are intentionally ignored because they inherit local provider
credentials from `.env`; never commit them. Rebuild the Android development APK
after changing between USB/localhost and wireless/LAN profiles.

## Prerequisites

- Run `make bootstrap` once.
- For USB development, enable USB debugging and accept the computer's ADB
  prompt.
- For cable-free development on Android 11+, enable **Wireless debugging** in
  Developer options. Put the phone and workstation on the same trusted Wi-Fi
  network. On the phone, choose **Pair device with pairing code** and note the
  displayed pairing IP address and port. On the workstation, run:

  ```bash
  adb pair <phone-ip>:<pairing-port>
  ```

  Enter the six-digit code from the phone when prompted. A successful pairing
  does **not** necessarily make the device available to ADB yet.

  Return to the main **Wireless debugging** page on the phone and copy its
  normal **IP address & Port**. This is the debugging endpoint, not the pairing
  endpoint and it commonly uses a different port. Connect to it explicitly:

  ```bash
  adb connect <phone-ip>:<debugging-port>
  adb devices -l
  ```

  The expected serial is `<phone-ip>:<debugging-port>`. Use that direct serial
  rather than a transient `adb-..._adb-tls-connect._tcp` mDNS service name:

  ```bash
  export ANDROID_SERIAL=<phone-ip>:<debugging-port>
  ```

  Wireless ADB remains paired until it is revoked, but repeat `adb connect`
  after changing networks or restarting wireless debugging.
- Confirm the connected device is visible before continuing:

  ```bash
  adb devices
  ```

For USB development, or when more than one device is attached, set its serial
once and use it in every ADB command:

```bash
export ANDROID_SERIAL=<device-serial>
```

For cable-free use, replace the localhost endpoints in `.env` with the
workstation's LAN IP, then restart Compose. This makes the API and MinIO
presigned upload URLs reachable from the phone:

```dotenv
FABRICASSIST_API_PUBLIC_URL=http://<workstation-lan-ip>:8000
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL=http://<workstation-lan-ip>:9000
```

Do not use these HTTP LAN values outside local development.

## 1. Start the local backend

From the repository root, use the Makefile as the stable local interface:

```bash
FABRICASSIST_EVIDENCE_PROVIDER=mock make up
make migrate
make seed
```

`make migrate` applies the current Alembic schema. `make seed` creates the
idempotent development tenant required for local registration. Do not skip
either command after a new or reset local database.

## 2. Connect the device to local services

### USB connection

In a second terminal, forward the three local ports used by the development
build:

```bash
adb -s "$ANDROID_SERIAL" reverse tcp:8000 tcp:8000  # API
adb -s "$ANDROID_SERIAL" reverse tcp:8081 tcp:8081  # Expo Metro
adb -s "$ANDROID_SERIAL" reverse tcp:9000 tcp:9000  # MinIO direct uploads
adb -s "$ANDROID_SERIAL" reverse --list
```

For a single connected device, `-s "$ANDROID_SERIAL"` may be omitted.

### Wireless connection

The wireless APK uses Expo Development Client and reaches Metro, the API, and
MinIO directly through the LAN. Do **not** use `adb reverse` in this flow.
Confirm the trusted LAN/firewall permits the phone to reach workstation ports
`8000`, `8081`, and `9000`.

## 3. Start Metro

Keep this command running in the second terminal:

```bash
REACT_NATIVE_PACKAGER_HOSTNAME=<workstation-lan-ip> \
  FABRICASSIST_API_PUBLIC_URL=http://<workstation-lan-ip>:8000 \
  pnpm --dir frontend --filter fabricassist-app exec expo start --dev-client --lan --clear
```

For USB reverse development, the `FABRICASSIST_API_PUBLIC_URL` prefix may be
omitted. For wireless development, it is required so the Expo config does not
send the phone to its own `localhost`. Stop any existing Metro process first;
the API URL is read when Metro starts, so an already-running server that was
started without the LAN URL will keep serving a localhost configuration.
`REACT_NATIVE_PACKAGER_HOSTNAME` makes Expo advertise the same LAN interface to
Metro; it is required on workstations that have both wired and Wi-Fi addresses.

The same Expo value is embedded in the Android development build. After first
switching from USB/localhost to wireless/LAN development, rebuild and reinstall
the development APK once before opening it through Metro. Do not subsequently
run an unprefixed `expo run:android`: it rebuilds the APK with the default
`http://localhost:8000` API URL and breaks wireless sign-in again.

Wait for Metro to finish its first Android bundle before opening the app. A
temporary `Bundling ...` screen is normal; `Unable to load script` usually
means Metro is not running. For USB, confirm the port-8081 reverse mapping.
For wireless, confirm the phone has LAN access to Metro, the API, and MinIO on
ports `8081`, `8000`, and `9000`.

## 4. Build, install, and launch

For a fresh or changed native build, use Expo to build, install, and launch the
app. For a wireless mDNS-connected device, set `ANDROID_SERIAL` and let Expo
use ADB's selected device; do not pass the mDNS service name to Expo's
`--device` option.

```bash
export ANDROID_SERIAL="$(adb devices | awk 'NR == 2 { print $1 }')"
env FABRICASSIST_API_PUBLIC_URL=http://<workstation-lan-ip>:8000 \
  pnpm --dir frontend --filter fabricassist-app exec expo run:android
```

After a successful build, if Expo does not finish the wireless installation,
install the generated APK through ADB:

```bash
adb -s "$ANDROID_SERIAL" install -r -d \
  frontend/apps/client/android/app/build/outputs/apk/debug/app-debug.apk
```

An Expo installation failure after `BUILD SUCCESSFUL` does not invalidate the
APK. Use the direct install above, then recreate the Metro mapping and start
Metro with the command in step 3 before opening the app.

For the known physical arm64 device, this direct Gradle fallback builds an
ABI-compatible debug APK:

```bash
(cd frontend/apps/client/android && \
  NODE_ENV=development \
  FABRICASSIST_API_PUBLIC_URL=http://<workstation-lan-ip>:8000 \
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
| Image upload fails | USB: confirm `adb -s "$ANDROID_SERIAL" reverse --list` includes port `9000`. Wireless: confirm the phone can reach `http://<workstation-lan-ip>:9000`. |
| `Unable to load script` | Keep Metro running. USB: confirm port `8081` is reversed. Wireless: rebuild the Expo Development Client after dependency/config changes, then confirm the phone can reach the workstation on port `8081`. |
| API requests fail | USB: confirm port `8000` is reversed. Wireless: confirm the LAN API URL is in `.env` and the phone can reach port `8000`; then run `make smoke`. |

## Stop local services

Stop Metro with `Ctrl-C`, then from the repository root run:

```bash
make down
```
