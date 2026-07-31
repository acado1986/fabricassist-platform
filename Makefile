.DEFAULT_GOAL := help

.PHONY: help bootstrap up start start-android down logs reset-local smoke migrate seed retention migration-test test-migrations test-neon test-object-storage test-object-storage-r2 test lint openapi check-openapi-drift check-version frontend-build build-release-web check-web-bundle-secrets check check-alpha-config check-production-config check-render-config check-deployment-workflows release-live-smoke test-qstash test-worker observability-up observability-down backup-restore-test load-test security-check iac-check release-check

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
	EXPO_PUBLIC_FABRICASSIST_API_URL="$${EXPO_PUBLIC_FABRICASSIST_API_URL:-$${FABRICASSIST_API_PUBLIC_URL:-http://localhost:8000}}" pnpm --dir frontend --filter fabricassist-app exec expo start --web --clear

ANDROID_ENV_FILE ?= .env.android

start-android: ## Start the local backend stack and Expo Dev Client for Android.
	@test -f .env.local || { echo '.env.local is required for local Docker settings.' >&2; exit 2; }
	@test -f "$(ANDROID_ENV_FILE)" || { echo "$(ANDROID_ENV_FILE) is required; copy .env.android.example to it." >&2; exit 2; }
	@set -a; . ./.env.local; . ./$(ANDROID_ENV_FILE); set +a; \
		$(MAKE) up; \
		ANDROID_EXPO_FLAGS="$${ANDROID_EXPO_FLAGS:---localhost}"; \
		pnpm --dir frontend --filter fabricassist-app exec expo start --dev-client $$ANDROID_EXPO_FLAGS --clear

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

retention: ## Run one scheduler-independent retention and merged-garment cleanup pass.
	cd backend && uv run python scripts/run_retention.py

migration-test: ## Run Alembic/storage integration tests against isolated Compose services.
	docker compose --profile test up -d fabricassist-postgres-test fabricassist-minio-test fabricassist-minio-test-init
	@until docker compose exec -T fabricassist-postgres-test pg_isready -U fabricassist_test -d fabricassist_test >/dev/null 2>&1; do sleep 1; done
	@container_id=$$(docker compose ps -aq fabricassist-minio-test-init); \
	until [ "$$(docker inspect -f '{{.State.Status}}' $$container_id)" = "exited" ]; do sleep 1; done; \
	test "$$(docker inspect -f '{{.State.ExitCode}}' $$container_id)" = "0"
	cd backend && FABRICASSIST_TEST_DATABASE_URL=postgresql://fabricassist_test:change-me-local-postgres-test@localhost:$${FABRICASSIST_POSTGRES_TEST_PORT:-5433}/fabricassist_test uv run pytest tests/integration

test-migrations: migration-test ## Run local PostgreSQL migration compatibility tests.

test-neon: ## Run opt-in Neon smoke with protected runtime and direct migration URLs.
	@test "$${FABRICASSIST_NEON_SMOKE:-}" = "1" || { echo "Set FABRICASSIST_NEON_SMOKE=1 to enable the live Neon smoke." >&2; exit 2; }
	cd backend && FABRICASSIST_NEON_SMOKE=1 FABRICASSIST_NEON_RUNTIME_URL="$${FABRICASSIST_NEON_RUNTIME_URL:?missing FABRICASSIST_NEON_RUNTIME_URL}" FABRICASSIST_NEON_MIGRATION_URL="$${FABRICASSIST_NEON_MIGRATION_URL:?missing FABRICASSIST_NEON_MIGRATION_URL}" uv run pytest tests/integration/test_neon.py

test-object-storage: ## Run the S3 storage contract against the local private MinIO service.
	docker compose --profile test up -d fabricassist-minio-test fabricassist-minio-test-init
	@container_id=$$(docker compose ps -aq fabricassist-minio-test-init); \
	until [ "$$(docker inspect -f '{{.State.Status}}' $$container_id)" = "exited" ]; do sleep 1; done; \
	test "$$(docker inspect -f '{{.State.ExitCode}}' $$container_id)" = "0"
	cd backend && FABRICASSIST_OBJECT_STORAGE_CONTRACT=1 FABRICASSIST_OBJECT_STORAGE_ENDPOINT_URL=http://localhost:$${FABRICASSIST_MINIO_TEST_PORT:-9002} FABRICASSIST_OBJECT_STORAGE_REGION=us-east-1 FABRICASSIST_OBJECT_STORAGE_BUCKET=fabricassist-test FABRICASSIST_OBJECT_STORAGE_ACCESS_KEY=fabricassist-test FABRICASSIST_OBJECT_STORAGE_SECRET_KEY=change-me-local-minio-test FABRICASSIST_OBJECT_STORAGE_FORCE_PATH_STYLE=true uv run pytest tests/integration/test_object_storage.py

test-object-storage-r2: ## Run opt-in live R2 smoke using externally supplied dedicated test-prefix credentials.
	@test "$${FABRICASSIST_R2_SMOKE:-}" = "1" || { echo "Set FABRICASSIST_R2_SMOKE=1 to enable the live R2 smoke." >&2; exit 2; }
	cd backend && FABRICASSIST_OBJECT_STORAGE_CONTRACT=1 FABRICASSIST_OBJECT_STORAGE_PROVIDER=r2 FABRICASSIST_OBJECT_STORAGE_ENDPOINT_URL="$${FABRICASSIST_R2_ENDPOINT_URL:?missing FABRICASSIST_R2_ENDPOINT_URL}" FABRICASSIST_OBJECT_STORAGE_REGION="$${FABRICASSIST_R2_REGION:-auto}" FABRICASSIST_OBJECT_STORAGE_BUCKET="$${FABRICASSIST_R2_BUCKET:?missing FABRICASSIST_R2_BUCKET}" FABRICASSIST_OBJECT_STORAGE_ACCESS_KEY="$${FABRICASSIST_R2_ACCESS_KEY:?missing FABRICASSIST_R2_ACCESS_KEY}" FABRICASSIST_OBJECT_STORAGE_SECRET_KEY="$${FABRICASSIST_R2_SECRET_KEY:?missing FABRICASSIST_R2_SECRET_KEY}" FABRICASSIST_OBJECT_STORAGE_FORCE_PATH_STYLE=false FABRICASSIST_OBJECT_STORAGE_TEST_PREFIX="$${FABRICASSIST_R2_TEST_PREFIX:?missing FABRICASSIST_R2_TEST_PREFIX}" uv run pytest tests/integration/test_object_storage.py

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

check-openapi-drift: ## Regenerate OpenAPI/client and fail if checked-in artifacts drift.
	$(MAKE) openapi
	git diff --exit-code -- docs/api/openapi.json frontend/packages/api-client/src/generated

check-version: ## Verify release metadata matches the root VERSION file.
	@python3 infrastructure/scripts/check-version.py

frontend-build: ## Build the Phase 3 Expo web artifact in Docker.
	docker build --file frontend/Dockerfile frontend

build-release-web: ## Export the Expo static web artifact and verify it has no secret markers.
	pnpm --dir frontend build:web
	$(MAKE) check-web-bundle-secrets

check-web-bundle-secrets: ## Scan the generated Expo web bundle without printing secret values.
	python3 infrastructure/scripts/check-web-bundle-secrets.py frontend/apps/client/dist

check: bootstrap check-version lint test ## Run the complete default Phase 5 local quality gate.

check-alpha-config: ## Validate typed alpha settings and safe alpha example configuration.
	cd backend && uv run pytest tests/unit/test_settings.py -k alpha
	@! grep -Eq '^EXPO_PUBLIC_.*(TOKEN|KEY|SECRET|DATABASE|S3|QSTASH)' .env.alpha.example
	@for expected in \
		FABRICASSIST_JOB_DISPATCHER \
		FABRICASSIST_EVIDENCE_PROVIDER \
		FABRICASSIST_CARE_PLANNER_PROVIDER \
		FABRICASSIST_CHAT_PROVIDER \
		FABRICASSIST_OBJECT_STORAGE_BACKEND \
		FABRICASSIST_PRODUCT_INFORMATION_PROVIDER \
		FABRICASSIST_PUBLICATION_RECOVERY_INTERVAL_SECONDS \
		FABRICASSIST_PUBLICATION_RECOVERY_BATCH_SIZE \
		FABRICASSIST_DELETION_MAX_ATTEMPTS; do \
		grep -Eq "^$${expected}=" .env.alpha.example || { \
			echo "missing alpha capability setting $${expected}" >&2; exit 1; \
		}; \
	done

check-production-config: ## Validate typed production settings and the safe production template.
	cd backend && uv run python -c "from fabricassist.settings import DeploymentProfile, Settings; settings = Settings(_env_file='../.env.production.example'); assert settings.environment == 'production'; assert settings.deployment_profile == DeploymentProfile.PRODUCTION"
	@! grep -Eq '^EXPO_PUBLIC_.*(TOKEN|KEY|SECRET|DATABASE|S3|QSTASH)' .env.production.example
	@for expected in \
		FABRICASSIST_JOB_DISPATCHER \
		FABRICASSIST_HOT_CACHE_BACKEND \
		FABRICASSIST_RATE_LIMITER_BACKEND \
		FABRICASSIST_CONCURRENCY_GATE_BACKEND \
		FABRICASSIST_VALKEY_URL \
		FABRICASSIST_EVIDENCE_PROVIDER \
		FABRICASSIST_CARE_PLANNER_PROVIDER \
		FABRICASSIST_CHAT_PROVIDER \
		FABRICASSIST_OBJECT_STORAGE_BACKEND; do \
		grep -Eq "^$${expected}=" .env.production.example || { \
			echo "missing production capability setting $${expected}" >&2; exit 1; \
		}; \
	done

check-render-config: ## Validate the Render alpha API workflow and container contract.
	@./infrastructure/scripts/validate-render-api-workflow.sh

check-deployment-workflows: ## Validate alpha and production release workflow contracts.
	python3 infrastructure/scripts/validate-deployment-workflows.py
	@./infrastructure/scripts/test-run-release-migrations.sh

release-live-smoke: ## Run an opt-in deployed-environment smoke using protected credentials.
	python3 infrastructure/scripts/release-live-smoke.py

test-qstash: ## Run synthetic QStash dispatcher adapter tests without network access.
	cd backend && uv run pytest tests/unit/test_qstash.py

test-worker: ## Run analysis-worker orchestration tests without infrastructure services.
	cd backend && uv run pytest tests/unit/test_analysis.py

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
