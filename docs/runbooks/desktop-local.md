# Start FabricAssist locally in a desktop browser

Use this runbook when the Expo web client, API, and MinIO all run on the same
workstation. It uses the `localhost` connection profile; do not use the
wireless Android profile for this workflow.

## 1. Select the localhost profile

```bash
cp .env.localhost .env
docker compose up -d --force-recreate fabricassist-api fabricassist-worker
```

The active endpoints must be:

```dotenv
FABRICASSIST_API_PUBLIC_URL=http://localhost:8000
FABRICASSIST_S3_PUBLIC_ENDPOINT_URL=http://localhost:9000
```

## 2. Start local services

```bash
make up
make migrate
make seed
```

Verify the backend before opening the browser:

```bash
curl http://localhost:8000/api/v1/health/live
```

It should return `{"status":"ok"}`.

## 3. Start the Expo web client

```bash
pnpm --dir frontend --filter fabricassist-app exec expo start --web --clear
```

Open the URL printed by Expo, normally `http://localhost:8081`.

## Switch back to Android

- USB Android: `cp .env.android-usb .env`, then follow
  [the Android USB section](android-start-local.md#usb-connection).
- Wireless Android: `cp .env.android-wireless .env`, then follow
  [the Android wireless section](android-start-local.md#wireless-connection).

Whenever the active profile changes, recreate API and worker containers. An
Android switch between localhost/USB and LAN wireless also requires rebuilding
the development APK as documented in the Android runbook.
