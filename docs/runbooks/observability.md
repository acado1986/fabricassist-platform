# Observability and alerts

API and worker emit JSON logs with correlation/job/stage fields and redaction.
W3C trace context propagates through FastAPI and Celery when an OTLP endpoint is
configured. `/api/v1/metrics` exposes process HTTP/job metrics plus durable,
low-cardinality PostgreSQL aggregates for scan, identity, lookup, validator,
conversation, review, deletion, cache, queue-age, token, latency, and cost state.

Local:

```bash
make observability-up
# Grafana http://localhost:3000, Prometheus http://localhost:9090
```

Production restricts metrics to an internal scraper and requires a bearer token.
Alert owners must route API 5xx/queue age to on-call and review/deletion/validator
signals to operational owners. Never add tenant/user/scan IDs, object keys,
presigned URLs, label/chat text, prompts, or credentials as metric labels/log
fields.
# Garment-analysis v2 signals

The v2 executor records `fabricassist_garment_analysis_branches_total`,
`fabricassist_garment_analysis_branch_latency_seconds`, and
`fabricassist_garment_analysis_branch_tokens`. Labels are limited to stable
branch, terminal status, and provider values; scan, tenant, user, image, and run
identifiers remain in protected structured logs/traces rather than Prometheus
labels. Alert on sustained `permanent_failed` branches, retryable failures,
increased `needs_better_image`/`needs_review` outcomes, and token/latency budget
breaches from `model_runs`.
