# Cloudflare Pages alpha infrastructure reference

The existing Expo app is statically exported and deployed by `.github/workflows/deploy-prerelease.yml` with `cloudflare/wrangler-action@v3`. Only the public API origin and environment name enter the build. Use the exact Pages origin in API and R2 CORS as documented in `docs/alpha/deployment.md`.
