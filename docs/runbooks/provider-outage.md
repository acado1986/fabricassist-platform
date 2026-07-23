# Provider outage

1. Confirm categorized provider failures and correlation/model-run metadata;
   never enable debug payload logging in production.
2. Preserve queued/failed database state. Allow bounded retry/backoff only for
   transient failures; deterministic schema/validator failures do not retry.
3. Apply global/tenant concurrency reductions or pause worker consumption if the
   provider is degraded. Do not fabricate or release a generic care result.
4. Exact/canonical validated caches may continue only when normal compatibility
   checks pass. Product lookup outage remains nonfatal and sourced as unavailable.
5. Communicate review/better-image/temporary failure status, restore workers
   gradually, and monitor queue age/error rate/cost.

Record provider status, retention implications, start/end time, impacted model
runs, retry decision, and post-incident fixture evaluation.
