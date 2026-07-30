# Retention and deletion policy

- Original private images default to 30 days and follow the tenant policy.
- Normalized/evidence/result history persists until user deletion or tenant
  policy expiration because it supports audit and safety provenance.
- Refresh tokens are stored only as hashes and expire/revoke by session policy.
- Valkey hot entries are disposable and TTL bounded.
- Product profiles may remain generic sourced cache data after personal links
  are removed; physical-garment, scan, conversation, and service associations do
  not.
- Model/provider retention must be set and approved in the subprocessor record.

Deletion is eventually consistent through the PostgreSQL outbox. Operational
metrics retain aggregates only; no customer image or message content is copied.
Deleting a garment-history entry immediately removes it from the customer's
history and removes its personal conversation, service, and analysis
associations. Its private image objects are removed asynchronously by the same
auditable outbox workflow; a retryable storage failure never restores the entry.
