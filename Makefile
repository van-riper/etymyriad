# etymyriad: developer convenience targets.
# Uses podman by default. Override with `make CONTAINER=docker ...`.

CONTAINER ?= podman
DATABASE_URL ?= postgres://etymyriad:etymyriad@localhost:5432/etymyriad

.PHONY: help \
	db-up db-down db-init db-apply db-psql db-reset \
	etl-sync etl-test etl-cov etl-ty etl-lint etl-format \
	web-install web-dev web-check web-build \
	release-changelog release-bump release-bump-commit release-preflight

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# --- Database ---------------------------------------------------------

db-up: ## Start the local Postgres container
	$(CONTAINER) compose up -d

db-down: ## Stop the local Postgres container
	$(CONTAINER) compose down

db-init: ## Apply the schema to the local database (waits for readiness)
	@echo "waiting for postgres..."
	@for i in $$(seq 1 30); do \
		$(CONTAINER) exec etymyriad-db psql -U etymyriad -d etymyriad -c 'SELECT 1' \
			>/dev/null 2>&1 && break; \
		sleep 1; \
	done
	$(CONTAINER) exec -i etymyriad-db psql -U etymyriad -d etymyriad < db/schema.sql

db-psql: ## Open a psql shell on the local database
	$(CONTAINER) exec -it etymyriad-db psql -U etymyriad -d etymyriad

db-reset: ## Drop and recreate the local database volume, then re-init
	$(CONTAINER) compose down -v
	$(MAKE) db-up
	$(MAKE) db-init

db-apply: ## Apply the schema via psql to $(DATABASE_URL) (local or remote, e.g. Neon)
	psql "$(DATABASE_URL)" -f db/schema.sql

# --- ETL (Python) ------------------------------------------------------

etl-sync: ## Install the Python ETL dependencies
	cd etl && uv sync

etl-test: ## Run ETL tests
	cd etl && uv run pytest

etl-cov: ## Run ETL tests with a coverage report
	cd etl && uv run pytest --cov

etl-ty: ## Type-check the ETL with ty
	cd etl && uv run ty check

etl-lint: ## Lint and format-check the ETL (ruff), as CI does
	cd etl && uv run ruff format --check && uv run ruff check

etl-format: ## Auto-format the ETL (ruff)
	cd etl && uv run ruff format

# --- Web (SvelteKit) ----------------------------------------------------

web-install: ## Install the web app dependencies
	cd web && npm install

web-dev: ## Run the web app in dev mode
	cd web && npm run dev

web-check: ## Type-check the web app (svelte-check), as CI does
	cd web && npm run check

web-build: ## Build the web app (Cloudflare adapter), as CI does
	cd web && npm run build

# --- Release -------------------------------------------------------------

release-changelog: ## Regenerate CHANGELOG.md (set VERSION=vX.Y.Z to label unreleased commits before tagging)
	npx --yes git-cliff --config keepachangelog $(if $(VERSION),--tag $(VERSION),) -o CHANGELOG.md

release-bump: ## Bump etl/web versions + changelog, then stage (VERSION=vX.Y.Z required)
	@test -n "$(VERSION)" || { echo "usage: make release-bump VERSION=vX.Y.Z"; exit 1; }
	$(MAKE) release-changelog VERSION=$(VERSION)
	cd etl && uv version $(VERSION:v%=%)
	cd web && npm version $(VERSION:v%=%) --no-git-tag-version
	git add CHANGELOG.md etl/pyproject.toml etl/uv.lock web/package.json web/package-lock.json

release-bump-commit: ## Bump, then commit and tag (VERSION=vX.Y.Z required)
	$(MAKE) release-bump VERSION=$(VERSION)
	git commit -m "chore: bump to $(VERSION)"
	git tag $(VERSION)

release-preflight: ## Run the full CI check suite locally (etl + web)
	$(MAKE) etl-lint
	$(MAKE) etl-ty
	$(MAKE) etl-cov
	$(MAKE) web-check
	$(MAKE) web-build
