# Deletion failures

Deletion intent and private object keys are committed to the PostgreSQL outbox
before object-store calls. On failure:

1. Inspect only safe request/outbox IDs and error categories; never print
   presigned URLs.
2. Restore storage connectivity/permissions. The API durable-recovery loop
   retries transient rows automatically. For an immediate manual pass, run the
   `fabricassist.process_retention` task.
3. Verify failed rows become completed, referenced images are tombstoned, and
   personal conversation/service/product associations remain removed.
4. Alert on any failed outbox row older than the tenant policy window.

`OBJECT_DELETE_REJECTED` is permanent and requires correcting configuration or
permissions before creating an intentional new recovery action.
`OBJECT_DELETE_FAILED` retries only while its attempts are below
`FABRICASSIST_DELETION_MAX_ATTEMPTS`.

Do not delete the outbox row, resurrect personal links, or declare completion
solely because the database parent is hidden.
