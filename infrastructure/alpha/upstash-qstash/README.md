# Upstash QStash alpha infrastructure reference

QStash is an adapter at the existing FabricAssist job-dispatch boundary. Its messages are schema-versioned identifiers, and the internal endpoint verifies raw bytes, keys, and the exact destination. Configure current/next keys and the final Render HTTPS endpoint through protected secrets; see `docs/prerelease/secrets.md`, `smoke-tests.md`, and `troubleshooting.md`.
