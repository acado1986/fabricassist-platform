# ADR-001: Use a modular monolith with separate API and worker processes

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

FabricAssist needs independently scalable HTTP and background execution without
premature network boundaries between business modules.

## Decision

Build one Python codebase under `backend/src/fabricassist/`. Run API entry points
from `fabricassist.api` and background entry points from `fabricassist.worker`.
Keep domain code isolated from FastAPI, persistence, queue, storage, and provider
implementations.

## Consequences

The two processes can scale independently while sharing domain and application
code. Introducing a microservice requires a later ADR and an explicit migration
reason. Phase 1 creates no Python package or runtime.
