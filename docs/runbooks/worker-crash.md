# Worker crash

Celery uses late acknowledgement, worker-lost rejection, prefetch one, bounded
task time limits, PostgreSQL idempotency/state checks, and expiring concurrency
leases. Run `./infrastructure/scripts/failure-drill.sh worker` locally.

For an incident, preserve the killed task/job/correlation IDs, replace the
worker, verify expired leases clear, and allow broker redelivery. Confirm the
scan or message reaches one final state without duplicate active revisions.
Repeated deterministic failures must become operator-visible rather than retry
forever.
