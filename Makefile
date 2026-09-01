.PHONY: help test lint fmt up down logs pull create-admin seed backup restore

# `up`/`down`/`logs` build from source via the dev override so a checkout runs
# without a published image. Self-hosters use the base docker-compose.yml alone.
COMPOSE_DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

test: ## Run the backend test suite
	cd backend && .venv/bin/python -m pytest -q

lint: ## Lint the backend
	cd backend && .venv/bin/ruff check app/ tests/

fmt: ## Format the backend
	cd backend && .venv/bin/ruff format app/ tests/

up: ## Build from source and start the full stack
	$(COMPOSE_DEV) up -d --build

down: ## Stop the stack
	$(COMPOSE_DEV) down

logs: ## Tail service logs
	$(COMPOSE_DEV) logs -f --tail=100

pull: ## Pull the latest published image and restart (production upgrade)
	docker compose pull
	docker compose up -d

create-admin: ## Create the first System Admin (interactive)
	docker compose exec web python -m app.cli create-admin

seed: ## Load demo data (PASSWORD=... [USER=admin] [BASE=http://localhost:8080])
	@test -n "$(PASSWORD)" || (echo "usage: make seed PASSWORD=<admin password>"; exit 1)
	backend/.venv/bin/python scripts/seed_demo.py \
		--base $(or $(BASE),http://localhost:8080) \
		--user $(or $(USER),admin) --password '$(PASSWORD)'

backup: ## Dump PostgreSQL + the data volume to ./backups/
	mkdir -p backups
	docker compose exec -T db pg_dump -Fc -U tesqivo tesqivo > backups/db-$$(date +%Y%m%d-%H%M%S).dump
	docker run --rm -v tesqivo_appdata:/data -v $$(pwd)/backups:/backup alpine \
		tar czf /backup/appdata-$$(date +%Y%m%d-%H%M%S).tgz -C /data .
	@echo "backup written to ./backups/"

restore: ## Restore from BACKUP=<db dump> [ATTACH=<appdata tgz>]
	@test -n "$(BACKUP)" || (echo "usage: make restore BACKUP=backups/db-XXX.dump [ATTACH=backups/appdata-XXX.tgz]"; exit 1)
	cat $(BACKUP) | docker compose exec -T db pg_restore --clean --if-exists -U tesqivo -d tesqivo
	@test -z "$(ATTACH)" || docker run --rm -v tesqivo_appdata:/data -v $$(pwd):/host alpine \
		sh -c "find /data -mindepth 1 -delete && tar xzf /host/$(ATTACH) -C /data"
	docker compose restart web
