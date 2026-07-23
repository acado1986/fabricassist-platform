# FabricAssist threat model

Primary assets are credentials, tenant identity, private garment images,
evidence/history/conversations, validator integrity, and deployment secrets.
Trust boundaries exist at client/API, presigned S3 upload, API/worker/Valkey,
PostgreSQL, model/product providers, telemetry, and operator review.

Key controls:

- Argon2id, rotating refresh families, short access JWTs, role/ownership checks.
- Explicit HTTPS CORS, security headers, upload decode/size/bomb checks, private
  object keys and short presigns.
- Valkey-backed global/tenant rate and provider concurrency limits.
- SSRF scheme/host/DNS/IP/redirect/size/content controls; untrusted prompt data
  cannot grant tools or change schemas/validators.
- Typed evidence/proposal/chat contracts and immutable deterministic validation.
- Structured redacted logs, low-cardinality internal metrics, OTLP without
  private payloads, least-privilege secrets/object access.
- PostgreSQL deletion outbox, retention, encrypted backup/restore drills,
  dependency/container/IaC scans, and immutable image deployment.

Residual production gates: textile-rule expert approval, live-provider privacy,
catalog licensing, external penetration test, staging load/failure drills, and
iOS store/build verification.
