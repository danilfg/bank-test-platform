SHELL := /bin/zsh

.PHONY: up down logs ps seed seed-rich migrate lint test build reseed-clean ensure-env

ENV_FILE := .env

ensure-env:
	@test -f $(ENV_FILE) || cp .env.example $(ENV_FILE)

up:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) up -d --build

down:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) down -v

logs:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) logs -f --tail=200

ps:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) ps

build:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) build

migrate:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) exec bank-api alembic upgrade head

seed: seed-rich

seed-rich:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) exec bank-api python scripts/seed_data.py

reseed-clean:
	$(MAKE) down
	$(MAKE) up
	$(MAKE) seed

lint:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) exec bank-api ruff check .

demo-test:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) exec bank-api pytest -q tests/api

test:
	@$(MAKE) ensure-env
	docker compose --env-file $(ENV_FILE) exec bank-api pytest -q
