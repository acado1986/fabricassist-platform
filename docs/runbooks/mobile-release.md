# Mobile release

Android:

```bash
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build:android:release
```

The Maestro gate requires a development APK, the mock API, and Metro; it does
not install or start them implicitly. For the checked Android x86_64 AVD:

```bash
pnpm --dir frontend --filter fabricassist-app exec expo prebuild --platform android
(cd frontend/apps/client/android && \
  ./gradlew app:assembleDebug -PreactNativeArchitectures=x86_64)
adb -s emulator-5554 install -r \
  frontend/apps/client/android/app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5554 reverse tcp:8000 tcp:8000
adb -s emulator-5554 reverse tcp:8081 tcp:8081
# In separate terminals, run the mock API on 8000 and Expo Metro on 8081.
maestro --device emulator-5554 test frontend/e2e/maestro/customer-smoke.yaml
```

Use the target device ABI for a physical device and always pass `--device` when
more than one Android target is connected. Record the AVD/API level, APK digest,
API/mock configuration, and Maestro output with the release evidence.

iOS requires macOS/Xcode and the corresponding release command. Verify bundle
IDs, signing profiles, camera/photo permission copy, secure refresh storage,
production HTTPS API URL, no development credentials, dynamic type, screen
reader flow, and store privacy declarations. `eas.json` is optional and contains
no credentials. Record signed artifact hashes and store review results; lack of
a macOS/iOS gate remains a release blocker, not a silent pass.
