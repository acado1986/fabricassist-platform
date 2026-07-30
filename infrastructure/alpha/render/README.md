# Render alpha API reference

Configure the existing `backend/Dockerfile` as a Docker web service with
`backend` as the root directory, auto-deploy disabled, and health path
`/api/v1/health/live`. Runtime values belong in the Render dashboard. GitHub
uses only the protected `RENDER_DEPLOY_HOOK_URL` to trigger an exact selected
SHA; it must never be stored in this repository.

See `docs/prerelease/render-api.md` for the FabricAssist operational contract.
