# Deletion failures

Deletion intent and private object keys are committed to the PostgreSQL outbox
before object-store calls. On failure:

1. Inspect only safe request/outbox IDs and error categories; never print
   presigned URLs.
2. Restore storage connectivity/permissions. The API durable-recovery loop
   retries transient rows automatically. Run the scheduler-independent
   retention command once per day from any scheduler (Render Cron, system
   cron, Kubernetes CronJob, or a Celery wrapper):
   `python /app/scripts/run_retention.py`.
   The bundled Celery adapter is also available through
   `fabricassist.process_retention`.
3. Verify failed rows become completed, referenced images are tombstoned, and
   personal conversation/service/product associations remain removed.
4. Alert on any failed outbox row older than the tenant policy window.

`OBJECT_DELETE_REJECTED` is permanent and requires correcting configuration or
permissions before creating an intentional new recovery action.
`OBJECT_DELETE_FAILED` retries only while its attempts are below
`FABRICASSIST_DELETION_MAX_ATTEMPTS`.

The application use case is `run_retention_once`; schedulers must only provide
process invocation and should not duplicate retention logic. The task is
idempotent and uses PostgreSQL row locks for safe retries. If Celery Beat is
used, run one dedicated Beat process—not one Beat per worker replica.

Do not delete the outbox row, resurrect personal links, or declare completion
solely because the database parent is hidden.
