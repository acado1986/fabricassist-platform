# Provider and subprocessor approval record

Complete this record outside the public repository for every production source:
legal entity, service/region, operation (evidence/planning/chat/product),
categories of data, retention/training settings, transfer basis, subprocessors,
security controls, deletion support, outage SLA, licensing, model/source
version, approval owner/date, and expiry/review date.

The deterministic mock providers are the only approved default and make no
network calls. No live model or catalog is production-approved merely because an
adapter is configurable. Arbitrary QR/web retrieval is not an approved fallback.

## Garment-analysis v2 production gate

The API and worker run only the v2 garment-analysis workflow. Before enabling a
live branch provider, record its current terms and obtain privacy-owner approval
outside this repository. The deployment must then set
`FABRICASSIST_GARMENT_ANALYSIS_PRIVACY_APPROVED=true`; otherwise production
readiness fails closed. This flag is an approval assertion, not a substitute for
the external record, and must be reset when provider/model/data-use terms change.
