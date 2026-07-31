# Feature tasks — retire the legacy alpha deployment profile

**Status:** Ready for implementation  
**Target executor:** GPT-5.6 Luna, medium reasoning  
**Scope:** Repository cleanup only; production remains live and staging is deferred  
**Primary outcome:** FabricAssist supports `local`/test and `production` without
an active alpha/prerelease runtime profile

## 1. Objective

The Render, Neon PostgreSQL, Cloudflare R2, Upstash QStash, Cloudflare Pages,
and TLS Valkey topology is the FabricAssist production deployment. The former
hosted alpha profile has been promoted and is no longer an active environment.

Remove the obsolete alpha runtime/configuration/deployment surface without:

- changing production behavior or provider resources;
- coupling application behavior directly to the production providers;
- weakening capability plug-and-play boundaries;
- introducing a staging profile prematurely;
- deleting historical architectural evidence; or
- touching credentials, local secret files, or unrelated working-tree changes.

After this feature, the supported runtime profiles are:

| Profile | Purpose |
| --- | --- |
| `local` | Local development and deterministic tests using Docker Compose |
| `production` | Active hosted production using configured capability adapters |

`development` and `test` may remain environment modes used with the local
deployment profile. Do **not** add `staging`, `.env.staging.example`, staging
workflows, staging provider resources, or staging-specific branches in this
feature. Staging will be designed later when public-release preparation starts.

## 2. Mandatory preparation

Before editing:

1. Read `AGENTS.md`, `docs/requirements.md`, and `docs/architecture.md`
   completely.
2. Read:
   - `docs/environment.md`
   - `docs/production/deployment.md`
   - `docs/adr/013-render-alpha-api-hosting.md`
   - `docs/adr/014-capability-adapters-and-job-outbox.md`
   - `docs/adr/015-production-hosted-release-topology.md`
   - `.github/workflows/deploy-production.yml`
   - `backend/src/fabricassist/settings.py`
3. Inspect `git status` and `git diff` before editing.
4. Start only after the current retention/identity work has been committed,
   stashed by its owner, or otherwise isolated. Do not overwrite or absorb those
   changes into this cleanup.
5. Inventory tracked references with a command equivalent to:

   ```bash
   git grep -n -i -E '\balpha\b|prerelease' -- \
     ':!docs/archive/**'
   ```

6. Do not open, print, copy, modify, or delete ignored/local files such as
   `.env`, `.env.local`, or `.env.alpha.backup`. They may contain secrets.
7. Do not commit, push, deploy, modify GitHub environments, or delete provider
   resources unless the user explicitly requests that separate operation.

## 3. Architecture invariants

All tasks must preserve these rules:

- Production topology is a composition of independently selected capabilities,
  not a single hard-coded provider stack.
- `JobDispatcher`, hot cache, rate limiter, concurrency gate, object storage,
  model providers, and product-information provider remain independently
  configurable.
- Domain and application code must not branch on Render, Neon, R2, QStash,
  Cloudflare, AWS, deployment profile, or provider names.
- QStash and Celery continue to invoke the same application use cases.
- PostgreSQL remains authoritative for business records, job intents,
  checkpoints, recovery, retention, and deletion state.
- R2 remains behind the S3-compatible object-storage adapter.
- AWS-compatible adapters/topology remain supported but inactive. Do not remove
  shared S3, PostgreSQL, container, or Celery compatibility.
- Production must retain explicit HTTPS/TLS, CORS, credential, rate-limit,
  concurrency, metrics, and secret validation.
- Removing the alpha profile must not become a hidden rename to staging.

## 4. Implementation sequence

Execute these feature tasks in order. Complete and validate one task before
starting the next. Keep each task reviewable and do not mix unrelated features.

### FT-01 — Establish a clean baseline and reference inventory

**Goal:** Prove the cleanup starts from a known repository state.

**Actions:**

1. Record the current branch, commit SHA, Alembic head, and `git status`.
2. Confirm unrelated retention/identity changes are isolated.
3. Produce a tracked-file inventory of active alpha/prerelease references,
   grouped into:
   - runtime settings and tests;
   - environment templates and Make targets;
   - GitHub workflows and validators;
   - active documentation;
   - infrastructure references;
   - historical ADR/archive material.
4. Record the baseline results of:

   ```bash
   make check-production-config
   make test-qstash
   make check-deployment-workflows
   git diff --check
   ```

**Acceptance:**

- No file has been changed yet.
- Every non-archive reference has an owner in FT-02 through FT-07.
- Any pre-existing failing command is recorded before implementation.

### FT-02 — Make production the only active hosted terminology

**Goal:** Ensure active documentation describes production, not a promoted
prerelease environment.

**Actions:**

1. Update `README.md`, `docs/README.md`, `docs/environment.md`, active runbooks,
   and production documentation to describe:
   - local development/test; and
   - the active production topology.
2. Remove prerelease documentation from active navigation and source-of-truth
   lists.
3. Migrate still-useful provider instructions from `docs/prerelease/` into the
   appropriate production documentation before retiring the old directory.
   Preserve at least:
   - Neon pooled runtime versus direct migration URLs;
   - R2 private bucket, exact CORS, retention, and presign rules;
   - QStash signing-key rotation and exact-destination verification;
   - Render API startup, readiness, and migration separation;
   - rollback, smoke, quota, and troubleshooting guidance.
4. Create a new ADR recording:
   - retirement of the active alpha profile;
   - production as the only hosted profile;
   - staging explicitly deferred;
   - no change to capability adapters or provider-neutral boundaries.
5. Keep historical ADR bodies immutable. Update ADR status/index metadata only
   where necessary to point to the new decision.
6. Move obsolete prerelease operational documents to an explicitly historical
   archive or delete them after their unique operational content is migrated.
   They must not remain listed as active guidance.

**Acceptance:**

- Active docs consistently describe production.
- No operational instruction was lost during migration.
- Historical records remain clearly marked as historical.
- No staging profile or staging promise was introduced.

### FT-03 — Remove the alpha runtime profile from typed settings

**Goal:** Make the backend settings contract accept only real supported
profiles.

**Actions:**

1. Remove `DeploymentProfile.ALPHA`.
2. Remove `"alpha"` from the `environment` literal.
3. Remove alpha/profile cross-validation and alpha-only error messages.
4. Remove `apply_alpha_defaults`.
5. Decide explicitly whether any former constrained defaults are useful for
   production:
   - Do not silently copy the three-image limit into production.
   - Do not weaken the current production pool, retry, or security settings.
   - Keep production values controlled by `.env.production.example` and typed
     limits.
6. Ensure production still validates:
   - explicit HTTPS application/API/CORS origins;
   - non-local PostgreSQL with TLS;
   - private S3-compatible HTTPS storage;
   - valid paired static S3 credentials when configured;
   - TLS Valkey for selected Valkey capabilities;
   - fail-closed production rate limiting;
   - non-no-op rate limiting and concurrency;
   - protected metrics when enabled;
   - QStash token, current/next signing keys, and HTTPS destination when
     selected.
7. Keep configuration requirements capability-specific: unselected adapters
   must not require their credentials or services.
8. Replace alpha settings tests with local/production tests. Add explicit tests
   that `alpha` is rejected as both an environment and deployment profile.
9. Update QStash tests to use production or a provider-neutral test
   configuration without weakening production validation.

**Primary files:**

- `backend/src/fabricassist/settings.py`
- `backend/tests/unit/test_settings.py`
- `backend/tests/unit/test_qstash.py`
- `backend/tests/unit/test_production_hardening.py`

**Acceptance:**

- `Settings` has no alpha enum/literal/default/validator branch.
- Production security regression tests still pass.
- QStash remains independently selectable and contract-tested.
- Local tests require no hosted credentials or network access.

### FT-04 — Consolidate environment templates and Make targets

**Goal:** Expose only supported local and production configuration.

**Actions:**

1. Delete tracked `.env.alpha.example`.
2. Update `.env.example` and `.env.production.example` accepted-value comments
   to list only supported profiles/environments.
3. Remove obsolete prerelease smoke variables and comments from the local
   template unless they are also used by the generic production smoke.
4. Remove `check-alpha-config` from `.PHONY`, the Makefile body, CI, and docs.
5. Rename alpha-oriented target descriptions to production-neutral names.
6. Keep these stable checks:

   ```bash
   make check-production-config
   make test-qstash
   make check-deployment-workflows
   make release-live-smoke
   ```

7. Ensure committed templates contain placeholders only and never add real
   project IDs, endpoints, tokens, credentials, database URLs, or account IDs.

**Acceptance:**

- Only local and production templates are active.
- `make help` exposes no alpha/prerelease target.
- Production configuration validation remains offline and deterministic.

### FT-05 — Retire prerelease CI/CD without changing production deployment

**Goal:** Remove dead deployment paths while preserving the stable production
release pipeline.

**Actions:**

1. Delete:
   - `.github/workflows/deploy-prerelease.yml`
   - `.github/workflows/prerelease-live-smoke.yml`
2. Remove prerelease checks from `.github/workflows/release-quality.yml`.
3. Refactor `infrastructure/scripts/validate-deployment-workflows.py` to validate
   production workflows only.
4. Update or replace `infrastructure/scripts/validate-render-api-workflow.sh`,
   which currently points at the prerelease workflow, so it validates the
   production Render deployment contract.
5. Rename script/target descriptions when their names imply prerelease or alpha.
6. Preserve production workflow invariants:
   - stable immutable `vMAJOR.MINOR.PATCH` tags;
   - one recorded source SHA;
   - quality before migration;
   - direct Neon migration before API/web deployment;
   - Render deploy hook scoped through protected secrets;
   - Cloudflare Pages production project;
   - revision/readiness verification;
   - protected production live smoke;
   - no provider credentials during pull-request quality checks.
7. Do not modify the live GitHub `production` environment or its secrets.

**Acceptance:**

- Repository workflows contain one active hosted deployment path: production.
- `make check-deployment-workflows` passes.
- Production workflow behavior is unchanged except removal of obsolete
  prerelease validation.

### FT-06 — Consolidate infrastructure references

**Goal:** Remove active infrastructure paths that imply a separate alpha stack.

**Actions:**

1. Move reusable documents under `infrastructure/alpha/` to
   `infrastructure/production/` or merge them into `docs/production/`.
2. Update every inbound link before removing the old directory.
3. Keep provider details as configuration of existing capability adapters:
   - Neon is PostgreSQL configuration, not a Neon repository implementation;
   - R2 uses `S3ObjectStorageAdapter`, not an R2-specific application port;
   - QStash implements `JobDispatcher`;
   - Cloudflare Pages hosts the shared Expo static export;
   - Render runs the existing API container.
4. Do not create provider resources, Terraform, or a staging directory.

**Acceptance:**

- No active infrastructure directory is named for the retired profile.
- All documentation links resolve.
- No provider-specific domain/application abstraction was introduced.

### FT-07 — Remove stale references and prove repository consistency

**Goal:** Finish the repository cleanup with explicit negative and positive
checks.

**Actions:**

1. Search tracked non-historical files for retired terminology:

   ```bash
   git grep -n -i -E '\balpha\b|prerelease' -- \
     ':!docs/archive/**' \
     ':!docs/adr/013-render-alpha-api-hosting.md' \
     ':!docs/adr/014-capability-adapters-and-job-outbox.md' \
     ':!docs/adr/015-production-hosted-release-topology.md' \
     ':!docs/feature-tasks/retire-legacy-alpha-profile.md'
   ```

2. Classify any remaining result. It must be either:
   - immutable historical context;
   - the retirement ADR/feature record; or
   - a defect to remove.
3. Check links and YAML parsing for active documentation/workflows.
4. Run the full validation matrix in section 6.
5. Review `git diff` for accidental secrets, provider identifiers, generated
   artifacts, or unrelated changes.

**Acceptance:**

- There is no executable alpha profile, template, Make target, CI path, or
  active operational guide.
- Production and local behavior pass their quality gates.
- Historical references are clearly non-operational.

### FT-08 — Prepare, but do not execute, external retirement

**Goal:** Leave a safe operator checklist for later manual resource cleanup.

**Actions:**

1. Document an operator-only checklist to inventory the obsolete GitHub
   environment and any separate Render, Neon, R2, QStash, Pages, or smoke-user
   resources.
2. Require confirmation that:
   - production uses different resources and credentials;
   - no DNS, CORS, webhook, QStash destination, backup, or rollback dependency
     points at the old resources;
   - required historical logs/backups have met retention policy;
   - deletion will not affect production data.
3. Require provider-side credential revocation before resource deletion.
4. Mark all external deletion commands/actions as manual and explicitly out of
   scope for the coding agent.

**Acceptance:**

- The repository cleanup does not perform any hosted destructive action.
- A human operator can retire old resources later without guessing.

## 5. Explicit non-goals

- Do not implement staging.
- Do not rename alpha directly to staging.
- Do not create another Render service, Neon database, R2 bucket, QStash topic,
  Pages project, Valkey instance, GitHub environment, or secret set.
- Do not deploy production.
- Do not remove Celery, MinIO, local PostgreSQL, local Valkey, AWS-compatible
  S3 support, or other retained adapters.
- Do not change care logic, garment identity, retention behavior, API schemas,
  OpenAPI artifacts, frontend behavior, or database schema.
- Do not add a migration; this cleanup changes configuration and operations, not
  persisted business data.
- Do not edit generated files unless an actual source contract change requires
  regeneration; none is expected.
- Do not combine this work with the future staging design.

## 6. Required validation

Run from the repository root and report exact results:

```bash
git diff --check
make check-production-config
make test-qstash
make check-deployment-workflows
make check-openapi-drift
make build-release-web
make check
```

Also run focused backend tests while iterating:

```bash
cd backend
uv run pytest \
  tests/unit/test_settings.py \
  tests/unit/test_qstash.py \
  tests/unit/test_production_hardening.py
```

If a command cannot run, state why. Do not claim it passed. Hosted Neon, R2,
QStash, Render, Cloudflare, and production smoke tests remain opt-in and must not
run without explicit permission and protected credentials.

## 7. Final acceptance criteria

The feature is complete only when:

1. `DeploymentProfile` supports `local` and `production`, with no alpha member.
2. The environment setting rejects `alpha`.
3. `.env.alpha.example`, alpha Make targets, and prerelease workflows are gone.
4. Active docs describe the production topology and local development only.
5. Unique operational knowledge from prerelease docs is preserved in production
   docs before old active docs are removed or archived.
6. Production still uses independently selected QStash, R2/S3, Neon/PostgreSQL,
   and Valkey-backed capabilities.
7. Local Celery/PostgreSQL/MinIO/Valkey remains runnable.
8. AWS-compatible alternatives remain inactive but supported through shared
   ports/protocols.
9. No staging implementation exists.
10. No hosted resources or secrets were changed.
11. Required checks pass, or every unrun check is explicitly reported.
12. The final report lists deleted/renamed files, configuration impact, tests,
    remaining historical references, and the later staging deferral.

## 8. Suggested reviewable commit sequence

Use focused commits only if the user asks the implementing agent to commit:

1. `docs(deployment): make production the only active hosted profile`
2. `refactor(config): remove the legacy alpha settings profile`
3. `ci(release): retire prerelease deployment workflows`
4. `docs(infrastructure): consolidate hosted production references`

Every commit must keep the repository internally consistent and pass its
relevant focused checks. Do not push or deploy unless explicitly requested.
