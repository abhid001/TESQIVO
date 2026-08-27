.PHONY: help dev-backend test lint up down logs backup restore fmt

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

test: ## Run the backend test suite
	cd backend && .venv/bin/python -m pytest -q

lint: ## Lint the backend
	cd backend && .venv/bin/ruff check app/ tests/

fmt: ## Format the backend
	cd backend && .venv/bin/ruff format app/ tests/

up: ## Start the full stack (Docker Compose)
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail service logs
	docker compose logs -f --tail=100

backup: ## Dump PostgreSQL + attachments to ./backups/
	mkdir -p backups
	docker compose exec -T db pg_dump -Fc -U tesqivo tesqivo > backups/db-$$(date +%Y%m%d-%H%M%S).dump
	docker run --rm -v tesqivo_attachments:/data -v $$(pwd)/backups:/backup alpine \
		tar czf /backup/attachments-$$(date +%Y%m%d-%H%M%S).tgz -C /data .
	@echo "backup written to ./backups/"

restore: ## Restore from BACKUP=<db dump> ATTACH=<attachments tgz>
	@test -n "$(BACKUP)" || (echo "usage: make restore BACKUP=backups/db-XXX.dump [ATTACH=backups/attachments-XXX.tgz]"; exit 1)
	cat $(BACKUP) | docker compose exec -T db pg_restore --clean --if-exists -U tesqivo -d tesqivo
	@test -z "$(ATTACH)" || docker run --rm -v tesqivo_attachments:/data -v $$(pwd):/host alpine \
		sh -c "rm -rf /data/* && tar xzf /host/$(ATTACH) -C /data"
	docker compose run --rm migrate
