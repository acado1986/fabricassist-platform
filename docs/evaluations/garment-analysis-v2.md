# Garment-analysis v2 evaluation record

This is the release evidence template for the Phase 10 cutover. It deliberately
does not assert production quality based on mock-provider tests.

## Version under evaluation

- Module: `garment-analysis-v2`
- Workflow: `asyncio-garment-analysis-v2`
- Care policy: `care-policy-v2`
- Retained-data projection: migration `20260803_0029`

## Required measured gates

| Measure | Threshold | Evidence | Status |
|---|---:|---|---|
| Safety-policy regression | 100% pass | `make test` plus approved textile fixtures | Automated suite required |
| Required provider calls | 2 normal branches | workflow call-count fixture | Automated suite required |
| Branch retry cap | At most 2 per branch | concurrency/redelivery tests | Automated suite required |
| Label clearer-image rate | Product-approved threshold | synthetic/licensed evaluation set | Pending product owner |
| Review rate | Product-approved threshold | synthetic/licensed evaluation set | Pending product owner |
| Token and latency budgets | Deployment-approved budget | `model_runs` aggregate and load drill | Pending operations owner |
| Provider privacy | Approved terms/region/retention | `docs/privacy/subprocessors.md` external record | Pending privacy owner |
| Backup and restore | Successful isolated drill | `make backup-restore-test` and staging record | Pending operations owner |

Record the fixture-set checksum, date, owner, environment, model/provider,
sample size, and exact command output with each approved row. Never use customer
images or live dual-run production requests as evaluation inputs.
