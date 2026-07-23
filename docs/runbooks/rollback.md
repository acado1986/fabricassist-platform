# Rollback

Application rollback uses the previously recorded immutable API, worker, and web
digests. Stop promotion, preserve logs/correlation IDs, and decide whether the
schema is backward compatible before changing tasks.

- If the new migration is additive and the prior image is compatible, roll ECS
  services and web together, then verify health and queue processing.
- If a breaking schema/cutover boundary is crossed, do not run an improvised
  downgrade. Restore the reviewed pre-deploy database snapshot with matching
  application digests or apply a forward fix.
- Never overwrite activated validator/template history or discard private
  objects created after a snapshot. Reconcile object references and deletion
  outbox before traffic resumes.

Record incident, decision owner, snapshot time, digests, data reconciliation,
smoke results, and follow-up issue.
