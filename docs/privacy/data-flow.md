# FabricAssist data flow

Private images upload directly from the authenticated client to one server-owned
S3 key. API metadata is tenant scoped in PostgreSQL. Workers read private images,
create normalized derivatives, send only configured evidence to the selected
model subprocessor, persist typed evidence/proposals/validation/model-run
metadata, and expose validated results. Product and conversation providers are
separate subprocessors/data sources.

Valkey may contain transient hot-cache, rate-limit, and concurrency state.
Celery broker data uses the independently configured broker URL and may use the
same Valkey service or a separate Redis-compatible/RabbitMQ broker.
It is never the sole business record. OTLP/log/metric exports exclude image
bytes, label/chat text, credentials, full URLs, and high-cardinality personal
identifiers. Deletion intent persists before object removal.
