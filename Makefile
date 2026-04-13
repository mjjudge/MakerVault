.PHONY: help bootstrap dev-api dev-web lint-api lint-web test-api test-web

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Check prerequisites and print setup instructions
	@bash scripts/bootstrap.sh

dev-api: ## Run the API in development mode (requires Python venv set up)
	@echo "Not yet implemented — see apps/api/README.md"

dev-web: ## Run the frontend dev server (requires Node.js)
	@echo "Not yet implemented — see apps/web/README.md"

lint-api: ## Lint the API (requires ruff installed)
	@echo "Not yet implemented"

lint-web: ## Lint the frontend (requires eslint installed)
	@echo "Not yet implemented"

test-api: ## Run API tests
	@echo "Not yet implemented"

test-web: ## Run frontend tests
	@echo "Not yet implemented"

up: ## Start all services via Docker Compose
	docker compose -f infra/docker/docker-compose.yml up -d

down: ## Stop all services
	docker compose -f infra/docker/docker-compose.yml down

logs: ## Follow Docker Compose logs
	docker compose -f infra/docker/docker-compose.yml logs -f
