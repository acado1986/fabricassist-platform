.DEFAULT_GOAL := help

.PHONY: help bootstrap up start down logs reset-local smoke migrate seed migration-test test lint openapi frontend-build check observability-up observability-down backup-restore-test load-test security-check iac-check release-check

help: ## List the stable FabricAssist developer commands.
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Install locked backend and frontend foundation dependencies.
	@command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
	@command -v uv >/dev/null || { echo "uv is required for the Phase 2 backend" >&2; exit 1; }
	@command -v docker >/dev/null || { echo "Docker is required" >&2; exit 1; }
	@docker compose version >/dev/null || { echo "Docker Compose v2 is required" >&2; exit 1; }
	cd backend && uv sync --frozen
	@command -v node >/dev/null || { echo "Node.js is required for the Phase 3 frontend" >&2; exit 1; }
	@command -v corepack >/dev/null || { echo "Corepack is required for pnpm" >&2; exit 1; }
	@corepack enable
	@corepack prepare pnpm@10.28.2 --activate
	pnpm --dir frontend install --frozen-lockfile

up: ## Start the healthy local dependency stack, API, and analysis worker.
	docker compose up -d --build --wait fabricassist-postgres fabricassist-valkey fabricassist-minio fabricassist-minio-init fabricassist-api fabricassist-worker

start: up ## Start the local backend stack and Expo web client.
	pnpm --dir frontend --filter fabricassist-app web

down: ## Stop the local FabricAssist Compose project without deleting volumes.
	docker compose down

logs: ## Follow logs from the local FabricAssist Compose project.
	docker compose logs --follow

reset-local: ## Remove local FabricAssist volumes only with CONFIRM=1.
	@if [ "$(CONFIRM)" != "1" ]; then echo "Use: make reset-local CONFIRM=1" >&2; exit 2; fi
	@./infrastructure/scripts/reset-local.sh --confirm

smoke: ## Verify local PostgreSQL, Valkey, MinIO, bucket privacy, and API health.
	@./infrastructure/scripts/smoke.sh

migrate: ## Apply the Alembic schema baseline through the API Compose service.
	docker compose exec -T fabricassist-api alembic -c /app/alembic.ini upgrade head

seed: ## Seed the idempotent non-loginable development tenant and admin.
	docker compose exec -T fabricassist-api python /app/scripts/seed.py

migration-test: ## Run Alembic/storage integration tests against isolated Compose services.
	docker compose --profile test up -d fabricassist-postgres-test fabricassist-minio-test fabricassist-minio-test-init
	@until docker compose exec -T fabricassist-postgres-test pg_isready -U fabricassist_test -d fabricassist_test >/dev/null 2>&1; do sleep 1; done
	@container_id=$$(docker compose ps -aq fabricassist-minio-test-init); \
	until [ "$$(docker inspect -f '{{.State.Status}}' $$container_id)" = "exited" ]; do sleep 1; done; \
	test "$$(docker inspect -f '{{.State.ExitCode}}' $$container_id)" = "0"
	cd backend && FABRICASSIST_TEST_DATABASE_URL=postgresql://fabricassist_test:change-me-local-postgres-test@localhost:$${FABRICASSIST_POSTGRES_TEST_PORT:-5433}/fabricassist_test uv run pytest tests/integration

test: ## Run foundation checks plus backend and frontend unit tests.
	@./infrastructure/scripts/validate-foundation.sh
	cd backend && uv run pytest tests/unit
	pnpm --dir frontend test

lint: ## Run configuration, backend, and frontend quality checks.
	@sh -n infrastructure/scripts/validate-foundation.sh
	@docker compose config --quiet
	cd backend && uv run ruff format --check .
	cd backend && uv run ruff check .
	cd backend && uv run pyright .
	pnpm --dir frontend format:check
	pnpm --dir frontend lint
	pnpm --dir frontend typecheck
	@git diff --check

openapi: ## Generate deterministic FastAPI OpenAPI and the frontend client.
	@mkdir -p docs/api
	cd backend && uv run python -c "import json; from fabricassist.api.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > ../docs/api/openapi.json
	pnpm --dir frontend generate:api

frontend-build: ## Build the Phase 3 Expo web artifact in Docker.
	docker build --file frontend/Dockerfile frontend

check: bootstrap lint test ## Run the complete default Phase 5 local quality gate.

observability-up: ## Start the optional local OTEL, Prometheus, and Grafana profile.
	FABRICASSIST_OTEL_EXPORTER_OTLP_ENDPOINT=http://fabricassist-otel-collector:4318 docker compose --profile observability up -d --build --wait

observability-down: ## Stop optional observability services without deleting data.
	docker compose --profile observability down

backup-restore-test: ## Prove a local PostgreSQL backup restores into an isolated drill database.
	@./infrastructure/scripts/backup-restore-drill.sh

load-test: ## Run the bounded local metadata load smoke (override LOAD_* variables).
	python3 infrastructure/scripts/load-smoke.py \
		--url "$${LOAD_URL:-http://localhost:8000}" \
		--duration "$${LOAD_DURATION:-15}" \
		--concurrency "$${LOAD_CONCURRENCY:-8}"

security-check: ## Run local static secret, production-settings, and container-policy checks.
	@./infrastructure/scripts/security-check.sh

iac-check: ## Format and validate the OpenTofu staging baseline.
	@command -v tofu >/dev/null || { echo "OpenTofu 1.9+ is required for iac-check" >&2; exit 1; }
	tofu -chdir=infrastructure/terraform/staging fmt -check -recursive
	tofu -chdir=infrastructure/terraform/staging init -backend=false
	tofu -chdir=infrastructure/terraform/staging validate

release-check: check security-check frontend-build ## Run non-cloud Phase 19 release gates.
	@printf '%s\n' 'Run migration-test, E2E, Android/iOS, IaC, load, and restore gates per docs/runbooks/release.md.'
