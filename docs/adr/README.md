# Architecture decision records

FabricAssist records durable architectural decisions here. ADRs are immutable
historical records once superseded; a later decision links to and supersedes an
earlier record rather than rewriting history.

Use [`template.md`](template.md) for new decisions. Phase 1 records ADR-001
through ADR-008 as summaries of the original architecture. ADR-009 supersedes
ADR-005's model-authority decision; ADR-010 through ADR-012 record physical
garment identity/history, sourced product enrichment, and server-owned
contextual conversation.

ADR-013 is a historical record of the hosted prerelease API placement. ADR-014
records capability-level adapter selection and the PostgreSQL transactional job
outbox. ADR-015 records the production Render/Cloudflare/Neon/R2/QStash/Valkey
release topology. ADR-016 introduces the mixed GraphQL/REST/SSE boundary;
ADR-017 establishes one unified v1 API with read-only GraphQL, REST-only
writes, shared application services, and canonical SSE recovery.
ADR-018 converts retained ordered GraphQL connections to versioned opaque
keyset cursors with a hash-bound, exact Phase 6 migration approval.

The historical alpha plan and inventory are archived under
[`../archive/`](../archive/). Active prerelease operations live under
[`../prerelease/`](../prerelease/).
