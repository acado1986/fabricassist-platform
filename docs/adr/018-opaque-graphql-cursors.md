# ADR-018: Opaque keyset cursors for retained GraphQL connections

**Status:** Accepted
**Date:** 2026-07-31
**Related:** ADR-017; `storefront-graphql-read-migration.md` Phase 6

## Decision

The retained ordered GraphQL connections `scans`, `garments`, and `messages`
use versioned opaque string cursors instead of UUID input arguments. Each
cursor contains the timestamp and UUID tie-breaker required by its ordering;
the server validates the referenced row through the authenticated tenant/user
scope before applying the keyset predicate.

The cursor payload is an implementation detail. It is not a signed capability,
does not select a tenant, and never bypasses ownership filtering. Invalid or
unauthorized cursors return the same pagination/not-found behavior as other
missing resources.

## Rationale

UUID-only cursors cannot encode the timestamp tie-breakers used for stable
pagination and encourage offset-like client assumptions. Opaque keyset cursors
make ordering explicit, avoid duplicates across equal timestamps, and keep
cursor internals replaceable without another public schema change.

## Compatibility and migration

This is an intentional Phase 6 GraphQL input contract change. REST endpoints
are unchanged. The checked-in approval manifest
`docs/api/graphql/phase-6-opaque-cursors.approval.json` is bound to the exact
pre/post SDL hashes and exactly the three approved argument-type changes. The
breaking check remains fail-closed for every other removal or type change.
