# etymyriad: developer convenience targets.
# Uses podman by default. Override with `make CONTAINER=docker ...`.

CONTAINER ?= podman
DATABASE_URL ?= postgres://etymyriad:etymyriad@localhost:5432/etymyriad

.PHONY: help db-up db-down db-init db-psql db-reset etl-sync web-install web-dev test ty lint format

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

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

etl-sync: ## Install the Python ETL dependencies
	cd etl && uv sync

web-install: ## Install the web app dependencies
	cd web && npm install

web-dev: ## Run the web app in dev mode
	cd web && npm run dev

test: ## Run ETL tests
	cd etl && uv run pytest

ty: ## Type-check the ETL with ty
	cd etl && uv run ty check

lint: ## Lint and format-check the ETL (ruff), as CI does
	cd etl && uv run ruff format --check && uv run ruff check

format: ## Auto-format the ETL (ruff)
	cd etl && uv run ruff format
