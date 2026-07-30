# FabricAssist alpha rollback runbook

Rollback is a selected-ref redeployment, not a tag rewrite and not an automatic database downgrade.

## When to roll back

Roll back when a release has a safety, authentication, tenant-isolation, storage, dispatch, or unrecoverable smoke failure that cannot be fixed forward within the alpha maintenance window. Pause new analysis dispatch only when a message or schema incompatibility makes execution unsafe; keep PostgreSQL as the source for pending state.

## Procedure

1. Identify the last good release SHA/tag and its recorded migration head.
2. Check whether queued QStash message schemas are compatible with that ref. Old messages must safely execute, no-op, or move to reviewed state; do not discard durable checkpoint information.
3. Manually dispatch `Deploy alpha` with the known-good tag or exact commit in `ref`. Alternatively create a **new** rollback tag that points at the good commit, for example:

   ```bash
   git tag -a v0.1.0-alpha.2-rollback <previous-good-commit> \
     -m "Rollback alpha to previous good release"
   git push origin v0.1.0-alpha.2-rollback
   ```

4. Allow its normal order: quality → migration compatibility check → API and web deployment → hosted smoke. Do not move or re-push an existing release tag and do not run automatic Alembic downgrade.
5. Verify API liveness/readiness, exact Pages/API CORS, signed QStash delivery, and the diagnostic live smoke. Record the rollback SHA/tag, reason, migration head, and results.

## Database and object safety

Prefer expand/migrate-compatible forward remediation. If the last-good code cannot read the current schema, keep the service disabled and prepare a tested forward fix; do not blindly downgrade Neon. R2 objects remain private and PostgreSQL deletion records remain authoritative during rollback.

## Failed rollback

If the selected ref fails quality or smoke, stop and keep the environment in a safe maintenance state. Verify secret names, destination URL, CORS, migration head, and QStash key overlap. Escalate with redacted workflow/job identifiers; never paste credentials or signed request bodies.
