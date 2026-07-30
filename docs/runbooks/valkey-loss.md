# Valkey loss

PostgreSQL remains authoritative. Valkey loss removes hot cache, rate/concurrency
coordination, and broker availability but not completed evidence, results,
conversations, review state, or deletion intent.

Run the local drill with `./infrastructure/scripts/failure-drill.sh valkey`.
In production, stop new expensive mutations if fail-closed protection activates,
restore Valkey from the managed service, verify each selected capability and
the independently configured Celery broker when it also uses Valkey, redispatch queued
database operations idempotently, and confirm no duplicate active revision or
lost completed result. Monitor cache misses and queue age during warm-up.
