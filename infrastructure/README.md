# Infrastructure foundation

Local orchestration uses Docker Compose with project name `fabricassist`,
PostgreSQL/pgvector, Valkey, and MinIO. The root `docker-compose.yml` is the
Phase 1 configuration surface.

Phase 4 will complete bucket initialization, dependency readiness, reset and
smoke workflows, optional profiles, and integration isolation. Cloud deployment
assets are deferred until Phase 17 and must remain replaceable and adapter-led.
