# etymyriad: developer convenience targets.
# Assumes a native local Postgres (systemctl), not a container.

DATABASE_URL ?= postgres://etymyriad:etymyriad@localhost:5432/etymyriad

.PHONY: help \
	db-up db-down db-init db-apply db-psql db-reset \
	etl-sync etl-test etl-cov etl-check etl-lint etl-format \
	web-install web-dev web-lint web-check web-build \
	release-changelog release-bump release-bump-commit release-preflight

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# --- Database ---------------------------------------------------------

db-up: ## Start the local Postgres service
	sudo systemctl start postgresql

db-down: ## Stop the local Postgres service
	sudo systemctl stop postgresql

db-init: ## Create the local etymyriad role and database (one-time)
	sudo -u postgres psql -c "CREATE ROLE etymyriad LOGIN PASSWORD 'etymyriad';"
	sudo -u postgres psql -c "CREATE DATABASE etymyriad OWNER etymyriad;"

db-psql: ## Open a psql shell on the local database
	psql "$(DATABASE_URL)"

db-reset: ## Drop and recreate the local database's tables, then re-init
	@read -p "Drop all tables at $(DATABASE_URL)? [y/N] " ok; \
		[ "$$ok" = y ] || [ "$$ok" = Y ] || { echo "aborted"; exit 1; }
	psql "$(DATABASE_URL)" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
	$(MAKE) db-apply

db-apply: ## Apply the schema via psql to $(DATABASE_URL) (local or remote, e.g. Neon)
	psql "$(DATABASE_URL)" -f db/schema.sql

# --- ETL (Python) ------------------------------------------------------

etl-sync: ## Install the Python ETL dependencies
	cd etl && uv sync

etl-test: ## Run ETL tests
	cd etl && uv run pytest

etl-cov: ## Run ETL tests with a coverage report
	cd etl && uv run pytest --cov

etl-lint: ## Lint and format-check the ETL (ruff), as CI does
	cd etl && uv run ruff format --check && uv run ruff check

etl-check: ## Check ETL formatting/style with ruff and type-check with ty
	cd etl && uv run ruff check && uv run ty check

etl-format: ## Auto-format the ETL (ruff)
	cd etl && uv run ruff format

# --- Web (SvelteKit) ----------------------------------------------------

web-install: ## Install the web app dependencies
	cd web && npm install

web-dev: ## Run the web app in dev mode
	cd web && npm run dev

web-lint: ## Lint the web app (eslint), as CI does
	cd web && npm run lint

web-check: ## Type-check the web app (svelte-check), as CI does
	cd web && npm run check

web-build: ## Build the web app (Cloudflare adapter), as CI does
	cd web && npm run build

# --- Release -------------------------------------------------------------

release-changelog: ## Regenerate CHANGELOG.md (set VERSION=vX.Y.Z to label unreleased commits before tagging)
	npx --yes git-cliff --config keepachangelog $(if $(VERSION),--tag $(VERSION),) -o CHANGELOG.md

release-bump: ## Bump etl/web versions + changelog, then stage (VERSION=vX.Y.Z required)
	@test -n "$(VERSION)" || { echo "usage: make release-bump VERSION=vX.Y.Z"; exit 1; }
	git reset
	$(MAKE) release-changelog VERSION=$(VERSION)
	cd etl && uv version $(VERSION:v%=%)
	cd web && npm version $(VERSION:v%=%) --no-git-tag-version
	git add CHANGELOG.md etl/pyproject.toml etl/uv.lock web/package.json web/package-lock.json

release-bump-commit: ## Bump, then commit and tag (VERSION=vX.Y.Z required)
	$(MAKE) release-bump VERSION=$(VERSION)
	git commit -m "chore: bump to $(VERSION)"
	$(MAKE) release-changelog VERSION=$(VERSION)
	git add CHANGELOG.md
	git commit --amend --no-edit
	git tag $(VERSION)

release-preflight: ## Run the full CI check suite locally (etl + web)
	$(MAKE) etl-lint
	$(MAKE) etl-check
	$(MAKE) etl-cov
	$(MAKE) web-lint
	$(MAKE) web-check
	$(MAKE) web-build
