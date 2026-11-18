.PHONY: check backend-check frontend-check format backend-format frontend-format load-test smoke staging-up staging-down backup

check: backend-check frontend-check

backend-check:
	cd backend && ruff check app tests alembic scripts eval
	cd backend && ruff format --check app tests alembic scripts eval
	cd backend && mypy app
	cd backend && pytest -q
	cd backend && python -m eval.rag_eval --offline
	cd backend && pip-audit -r requirements.txt

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run build
	cd frontend && npm audit --omit=dev --audit-level=high

format: backend-format frontend-format

backend-format:
	cd backend && ruff check app tests alembic scripts eval --fix
	cd backend && ruff format app tests alembic scripts eval

frontend-format:
	cd frontend && npm run lint:fix

load-test:
	cd backend && locust -f tests/load/locustfile.py --host http://localhost

smoke:
	cd backend && python scripts/smoke_check.py

staging-up:
	docker compose -f docker-compose.yml -f docker-compose.staging.yml up --build -d

staging-down:
	docker compose -f docker-compose.yml -f docker-compose.staging.yml down

backup:
	docker compose exec backup sh -c "pg_dump -h db -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-ai_documents} -Fc -f /backups/manual_$$(date +%F-%H%M).dump"
