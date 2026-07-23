# FabricAssist infrastructure

Local orchestration uses Docker Compose with project name `fabricassist`,
PostgreSQL/pgvector, Valkey, and MinIO. The root `docker-compose.yml` is the
stable local configuration surface.

The optional `observability` profile adds OpenTelemetry Collector, Prometheus,
and Grafana. `terraform/staging` is an OpenTofu AWS staging baseline with
private ECS API/worker tasks, ALB TLS ingress, RDS PostgreSQL 17, encrypted
Valkey, customer-managed KMS encryption for private S3 images, ECR, CloudWatch,
backup retention, and deployment rollback. The public ALB and task HTTPS
egress are intentional, resource-scoped Trivy exceptions; application outbound
URL policy remains the SSRF boundary. No account, domain, remote-state, or
credential value is committed.
