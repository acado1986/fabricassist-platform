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
