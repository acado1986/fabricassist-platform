.DEFAULT_GOAL := help

.PHONY: help bootstrap up down logs reset-local smoke migrate seed test lint openapi frontend-build check

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

up: ## Start the healthy local dependency stack and API.
	docker compose up -d fabricassist-postgres fabricassist-valkey fabricassist-minio fabricassist-minio-init fabricassist-api

down: ## Stop the local FabricAssist Compose project without deleting volumes.
	docker compose down

logs: ## Follow logs from the local FabricAssist Compose project.
	docker compose logs --follow

reset-local: ## Remove local FabricAssist volumes only with CONFIRM=1.
	@if [ "$(CONFIRM)" != "1" ]; then echo "Use: make reset-local CONFIRM=1" >&2; exit 2; fi
	@./infrastructure/scripts/reset-local.sh --confirm

smoke: ## Verify local PostgreSQL, Valkey, MinIO, bucket privacy, and API health.
	@./infrastructure/scripts/smoke.sh

migrate: ## Apply migrations once Phase 5 implements them.
	@printf '%s\n' "make migrate is deferred to Phase 5; no database schema exists in Phase 1." >&2
	@exit 2

seed: ## Seed development data once Phase 5 implements it.
	@printf '%s\n' "make seed is deferred to Phase 5; no business data exists in Phase 1." >&2
	@exit 2

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

check: bootstrap lint test ## Run the complete Phase 4 local quality gate.
