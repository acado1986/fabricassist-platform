# FabricAssist universal client

The `fabricassist-app` Expo workspace contains the shared Android, iOS, customer
web, and operator review experience. It uses strict TypeScript, Expo Router,
generated API types, and typed English/Spanish catalogs.

Release gates:

```bash
pnpm --dir frontend build:web
pnpm --dir frontend test:e2e
pnpm --dir frontend test:android:smoke
pnpm --dir frontend build:android:release
pnpm --dir frontend build:ios:release # macOS/Xcode only
```

`frontend/Dockerfile` serves the exported SPA from a non-root Nginx image with
SPA fallback and security headers. `eas.json` is optional; credentials and store
identifiers are supplied outside the repository. The Maestro command expects an
already installed ABI-compatible development APK plus running mock API and Metro;
see [`docs/runbooks/mobile-release.md`](../docs/runbooks/mobile-release.md).
