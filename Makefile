# etymyriad: developer convenience targets.
# Assumes a native local Postgres (systemctl), not a container.

DATABASE_URL ?= postgres://etymyriad:etymyriad@localhost:5432/etymyriad

.PHONY: help \
	db-up db-down db-init db-apply db-psql db-reset db-snapshot db-restore \
	etl-sync etl-test etl-cov etl-ty etl-lint etl-format \
	web-install web-dev web-dev-start web-dev-stop web-dev-logs \
	web-lint web-check web-test web-test-e2e web-build web-format \
	release-changelog release-bump release-bump-commit release-preflight

help: ## List available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
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

db-snapshot: ## Dump a known-good local DB to db/snapshot.dump (gitignored)
	pg_dump -Fc "$(DATABASE_URL)" -f db/snapshot.dump

db-restore: ## Restore db/snapshot.dump over the local database (seconds, not a full ETL reload)
	@test -f db/snapshot.dump || { echo "no db/snapshot.dump; run 'make db-snapshot' first"; exit 1; }
	@read -p "Drop all tables at $(DATABASE_URL) and restore db/snapshot.dump? [y/N] " ok; \
		[ "$$ok" = y ] || [ "$$ok" = Y ] || { echo "aborted"; exit 1; }
	psql "$(DATABASE_URL)" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
	pg_restore -j$$(nproc) -d "$(DATABASE_URL)" db/snapshot.dump

# --- ETL (Python) ------------------------------------------------------

etl-sync: ## Install the Python ETL dependencies
	cd etl && uv sync

etl-test: ## Run ETL tests
	cd etl && uv run pytest

etl-cov: ## Run ETL tests with a coverage report
	cd etl && uv run pytest --cov

etl-lint: ## Lint and format-check the ETL (ruff), as CI does
	cd etl && uv run ruff format --check && uv run ruff check

etl-ty: ## Type-check the ETL (ty)
	cd etl && uv run ty check

etl-format: ## Auto-format the ETL (ruff)
	cd etl && uv run ruff format

# --- Web (SvelteKit) ----------------------------------------------------

web-install: ## Install the web app dependencies
	cd web && npm install

web-dev: ## Run the web app in dev mode (foreground)
	cd web && npm run dev

web-dev-start: ## Run the web app in dev mode, detached (log: web/.dev-server.log)
	@if [ -f web/.dev-server.pid ] && kill -0 $$(cat web/.dev-server.pid) 2>/dev/null; then \
		echo "already running (pid $$(cat web/.dev-server.pid))"; \
	else \
		cd web && (nohup npm run dev > .dev-server.log 2>&1 & echo $$! > .dev-server.pid); \
		echo "frontend started, tail with 'make web-dev-logs' or stop with 'make web-dev-stop'"; \
	fi

web-dev-stop: ## Stop the detached web dev server started by web-dev-start
	@if [ -f web/.dev-server.pid ]; then \
		pkill -P $$(cat web/.dev-server.pid) 2>/dev/null; \
		kill $$(cat web/.dev-server.pid) 2>/dev/null; \
		rm -f web/.dev-server.pid; \
		echo "frontend stopped"; \
	else \
		echo "not running"; \
	fi

web-dev-logs: ## Tail the detached web dev server's log
	tail -f web/.dev-server.log

web-lint: ## Lint and format-check the web app (eslint, prettier)
	cd web && npm run format:check && npm run lint

web-check: ## Type-check the web app (svelte-check), as CI does
	cd web && npm run check

web-test: ## Run web unit tests (vitest)
	cd web && npm run test

web-test-e2e: ## Run web e2e tests (Playwright), against a real dev server + DB
	cd web && npm run test:e2e

web-build: ## Build the web app (Cloudflare adapter), as CI does
	cd web && npm run build

web-format: ## Auto-format the web app (Prettier)
	cd web && npm run format

# --- Release -------------------------------------------------------------

release-changelog: ## Regenerate CHANGELOG.md (set VERSION=vX.Y.Z to label unreleased commits before tagging)
	npx --yes git-cliff --config keepachangelog $(if $(VERSION),--tag $(VERSION),) -o CHANGELOG.md

release-bump: ## Bump etl/web versions + changelog, then stage (VERSION=vX.Y.Z required)
	@test -n "$(VERSION)" || { echo "usage: make release-bump VERSION=vX.Y.Z"; exit 1; }
	@git diff --cached --quiet || { \
		echo "staged changes present, commit or unstage before bumping"; exit 1; }
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
	$(MAKE) etl-ty
	$(MAKE) etl-cov
	$(MAKE) web-lint
	$(MAKE) web-check
	$(MAKE) web-test
	$(MAKE) web-build
