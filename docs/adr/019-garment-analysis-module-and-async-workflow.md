# ADR-019: Garment-analysis module and native asyncio workflow

- **Status:** Accepted
- **Date:** 2026-08-03
- **Owner:** FabricAssist Architecture / Garment Intelligence
- **Refines:** [ADR-009](009-validator-gated-ai-care-plans.md)

## Context

The garment-intelligence redesign needs a cohesive application boundary and
parallel provider calls, while preserving PostgreSQL authority, retry safety,
tenant isolation, and the existing API/worker modular-monolith architecture.
The initial target is a small, mostly static workflow: garment inspection and
label extraction are required branches, and stain analysis is an optional,
policy-gated branch. The existing worker, job-dispatch, outbox, and PostgreSQL
patterns already provide delivery and recovery primitives. Introducing a graph
runtime for this bounded DAG would add another execution state and another
dependency without providing a required capability.

ADR-009 also made an AI-proposed care plan a mandatory step. For the v2 base
workflow, the safety-relevant base plan can be derived from the complete,
merged evidence dossier, cleaning history, authority rules, and versioned
Python care policy. Model output remains appropriate for structured evidence
and optional, explicitly gated stain hypotheses or proposals, but it is not
the authority for the base care recommendation.

## Decision

### 1. Native asyncio orchestration

Implement v2 orchestration inside the existing worker with native
`asyncio.TaskGroup` structured concurrency. The public application facade
exposes a provider-neutral workflow protocol; the concrete implementation is
`AsyncioGarmentAnalysisWorkflow` in the bounded `garment_analysis` module.

The module is expressed through the existing horizontal layers:

- `fabricassist.application.garment_analysis` is the only public entry point
  for API and worker consumers;
- `fabricassist.domain.garment_analysis` contains provider- and persistence-
  independent contracts and deterministic policy; and
- `fabricassist.infrastructure.garment_analysis` contains persistence, image,
  provider, and observability adapters.

No LangChain or LangGraph dependency, graph checkpointer, provider-specific
workflow object, or second production workflow is introduced for v2. Provider
calls receive immutable inputs, and no SQLAlchemy `AsyncSession` is shared
between concurrent tasks.

### 2. Durable branch authority

`analysis_branch_results` in PostgreSQL is the sole durable authority for
branch execution state, recovery decisions, branch output, and business reads.
It has one row per `(revision_id, branch_name)` and is protected by a unique
constraint. A successor analysis revision is created for reanalysis; the
original branch result is not overwritten.

`model_runs` remains the immutable provider-invocation and usage audit. Job
transport state, Valkey coordination, progress events, and caches may assist
execution, but none may override or become a second business-read authority.
Branch completion, model-run completion, and durable progress publication must
be committed together where the repository boundary permits; reconciliation
must read the branch row as authoritative.

### 3. Future graph-engine adoption threshold

LangGraph or another graph engine may be reconsidered only in a new ADR after
all of the following have been demonstrated:

1. The workflow has materially exceeded the current bounded DAG: as a
   concrete complexity signal, production requires at least six independently
   retryable external-side-effect nodes, at least two fan-out/fan-in joins, and
   at least one compensation, multi-provider fallback, or long-lived human
   review continuation that cannot be represented clearly and safely by the
   native workflow. Dynamic fan-out or nested conditional branches are also
   qualifying signals when they are production requirements rather than
   hypothetical extensions.
2. At least one measured operational or delivery problem remains after
   improving the native implementation: for example, repeated recovery
   defects, materially excessive orchestration code, or an inability to meet
   agreed latency/reliability objectives. Complexity must be demonstrated by
   incidents, maintenance measurements, or failed acceptance tests, not by
   framework preference.
3. A graph prototype passes the existing provider, domain-boundary, tenant,
   crash/recovery, deletion, observability, and public-contract suites; it
   provides a material operational benefit over native asyncio; and its
   checkpoint/state-retention behavior has an explicit GDPR and deletion
   design.
4. The graph implementation remains behind the same workflow protocol, keeps
   `analysis_branch_results` as the sole business authority, defines bounded
   retries and leases, and includes a migration, rollback, dependency, and
   operator-runbook plan approved by architecture and safety owners.

The existence of conditional branches alone is not sufficient to cross this
threshold.

### 4. ADR-009 resolution: deterministic v2 base plan

For v2, replace ADR-009's mandatory AI care-planning call with a deterministic
Python care-policy engine. It merges the complete active evidence revision,
resolves source authority and conflicts, applies cleaning history only within
the permitted safety envelope, and derives the typed base care plan. It must
never silently rewrite a rejected proposal into a different recommendation.

The following ADR-009 contracts remain in force:

- structured evidence, proposal (when present), validation report, and result
  schemas remain strict and versioned;
- photographed label prohibitions and explicit instructions retain highest
  authority;
- deterministic validation remains mandatory before any actionable result or
  safety-relevant chat claim is released;
- validation outcomes, provider/model/prompt/schema metadata, and audit
  provenance remain persisted; and
- a constrained model retry is permitted only for an explicitly model-backed
  optional operation, such as a stain proposal, and never turns model prose
  into the base-plan authority.

`ProposedCarePlan` and `CareValidationReport` therefore remain audit and
validation models. The v2 base plan is a typed deterministic output that is
validated and rendered from the same versioned safety policies. Historical
records retain their original provider/planner metadata and are not rerun as
part of this documentation decision.

### 5. Crash semantics and attempt limits

Provider invocation is **at least once**, not exactly once. A worker crash or
lost response after an external request begins can cause that branch's
in-flight request to be repeated. Provider idempotency keys or request
fingerprints should be used where supported, but FabricAssist does not claim a
guarantee the provider cannot provide.

Before each provider call, a repository transaction atomically claims the
branch using a row lock or compare-and-set transition, records the lease and
increments the attempt number. Only pending or stale retryable work may be
claimed. Each branch has a hard cap of **two attempts** (initial attempt plus
one retry); deterministic validation failures do not consume infrastructure
retry budget and are not blindly retried. A completed sibling is loaded from
`analysis_branch_results` and is never re-invoked merely because another
branch failed or the worker was redelivered.

The branch result, error classification, model-run audit completion, and
durable progress/outbox event must be persisted transactionally where
possible. Lease expiry permits recovery after a worker crash, and terminal
failure, needs-input, or review outcomes are durable rather than inferred from
queue state.

## Consequences

- v2 has one execution/business-read state machine and avoids dual state
  between a graph checkpoint and domain rows.
- The bounded module can be tested with fake providers and pure policy tests
  without importing FastAPI, SQLAlchemy, Celery, Google SDKs, LangChain, or
  LangGraph into domain code.
- Deterministic policy coverage and textile-care ownership become release
  requirements; policy gaps produce uncertainty or review rather than a
  planner fallback.
- The approved decision requires later implementation phases to add branch
  persistence and atomic claims before enabling parallel production calls.
- A future graph adoption is possible, but it is a measured migration behind
  the same public contract rather than an opportunistic dependency addition.
