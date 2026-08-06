# Phase 19 approval record

This record distinguishes automated engineering evidence from external
production approval. A pending row is a release blocker, not an implicit
approval.

| Gate | Artifact/evidence | Status | Required approver |
|---|---|---|---|
| Deterministic textile-care policy | `care-validation-v1`, SHA-256 `c949dfb9eb846f85b2afc07a31a99f317d7c343a381eb69f0d0f012e204dc847`; default regression suite | **Pending external review** | Textile-care safety owner |
| Product source and licensing | Mock catalog only by default; sourced/conflict behavior covered by tests and `docs/privacy/data-flow.md` | **Pending live-source selection** | Product/legal owner |
| Provider privacy and retention | `docs/privacy/subprocessors.md`, v2 readiness approval assertion, and `docs/privacy/retention.md`; no paid provider required locally | **Pending live-provider selection** | Privacy owner |
| Security review | Local policy, dependency, secret, IaC, container build, and CI scan gates | **Pending staging scan and penetration review** | Security owner |
| Backup/rollback | `docs/runbooks/backup-restore.md` and `docs/runbooks/rollback.md` | **Pending staging drill sign-off** | Operations owner |
| Android release | Release command and Maestro development smoke procedure documented | **Pending signed release artifact** | Mobile release owner |
| iOS release | macOS/Xcode procedure documented | **Pending macOS build and store review** | Mobile release owner |

For each approval, append the date, approver identity, immutable artifact/image
digest, command or report reference, scope, and any exception owner/expiry. Do
not replace a pending status with approval based only on unit tests.
