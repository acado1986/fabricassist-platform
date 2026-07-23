# OpenTofu deployment baseline

`staging/` is the Phase 19 AWS staging baseline. It creates two-AZ networking,
private ECS Fargate API/worker services, TLS ALB ingress, PostgreSQL 17, encrypted
Valkey, a private encrypted/versioned image bucket, immutable ECR repositories,
CloudWatch logs, health-gated rolling deployment, and deletion protection.

It intentionally does **not** contain account IDs, domains, credentials, remote
state bucket names, provider keys, or production defaults. Initialize with an
encrypted and locked S3 backend supplied by the deployment environment:

```bash
tofu -chdir=infrastructure/terraform/staging fmt -check
tofu -chdir=infrastructure/terraform/staging init -backend=false
tofu -chdir=infrastructure/terraform/staging validate
tofu -chdir=infrastructure/terraform/staging plan -var-file=/secure/staging.tfvars
```

Apply requires protected-environment approval. Run Alembic as a one-off task
before replacing services. Production should use a separately reviewed root
configuration and remote state; this staging module rejects `environment =
"production"`.
