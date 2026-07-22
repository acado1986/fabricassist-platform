# ADR-011: Enrich results through trusted product-information adapters

- **Status:** Accepted
- **Date:** 2026-07-22

## Context

Barcode, brand, model, and style-label images can identify useful product
metadata that is not readable in the photographed care label. A language model
is not an authoritative barcode database, public coverage is incomplete, and
catalog care information may describe a different variant or conflict with the
physical garment.

## Decision

Decode supported barcodes deterministically where possible, normalize and
validate their format/checksum, and query replaceable
`ProductInformationProvider` adapters. AI/OCR may locate a code or recover
printed digits, but it does not invent lookup records.

Every lookup persists identifier, provider, match level, normalized fields,
source/reference, retrieval time, schema version, validation status, and safe
raw/validated snapshots. Results are `exact`, `probable`,
`multiple_candidates`, or `not_found`. Product data is displayed with source and
match status and remains subordinate to photographed care-label evidence.

QR-derived URLs and catalog links are untrusted. FabricAssist never fetches an
arbitrary URL without scheme/host validation, redirect and response-size limits,
timeouts, an outbound-network policy, and SSRF protection.

## Consequences

- Product lookup requires a provider-neutral port, adapters, typed settings,
  rate/concurrency controls, source licensing review, contract tests, and durable
  PostgreSQL caching with refresh/invalidation metadata.
- A missing or ambiguous catalog result is normal and must not block image-led
  analysis.
- Catalog conflicts create uncertainty or review; they never weaken a physical
  prohibition.
- External product metadata may be reusable, but tenant/customer condition and
  service history remain isolated.
