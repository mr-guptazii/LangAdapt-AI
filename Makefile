.PHONY: dev api web worker test test-api test-web lint format migrate seed docker-up docker-down

dev: ## Run API + web concurrently (two terminals recommended instead)
	@echo "Run 'make api' and 'make web' in separate terminals, or 'make docker-up'."

api: ## Run the FastAPI dev server
	cd apps/api && .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

web: ## Run the Next.js dev server
	cd apps/web && npm run dev

worker: ## Run the Celery background worker
	cd apps/api && .venv/Scripts/python -m celery -A app.tasks.celery_app worker --loglevel=info

test: test-api test-web ## Run all tests

test-api:
	cd apps/api && .venv/Scripts/python -m pytest

test-web:
	cd apps/web && npx vitest run

lint: ## Lint both apps
	cd apps/api && .venv/Scripts/python -m ruff check app/ scripts/ tests/
	cd apps/web && npx eslint .

format: ## Auto-fix lint issues
	cd apps/api && .venv/Scripts/python -m ruff check app/ scripts/ tests/ --fix

migrate: ## Run Alembic migrations
	cd apps/api && .venv/Scripts/python -m alembic upgrade head

seed: ## Seed the database with demo data
	cd apps/api && PYTHONPATH=. .venv/Scripts/python scripts/seed.py

docker-up: ## Start the full stack via Docker Compose
	docker compose up --build

docker-down:
	docker compose down
