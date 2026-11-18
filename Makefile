.PHONY: check backend-check frontend-check format backend-format frontend-format load-test

check: backend-check frontend-check

backend-check:
	cd backend && ruff check app tests alembic
	cd backend && ruff format --check app tests alembic
	cd backend && mypy app
	cd backend && pytest -q
	cd backend && pip-audit -r requirements.txt

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run build
	cd frontend && npm audit --omit=dev --audit-level=high

format: backend-format frontend-format

backend-format:
	cd backend && ruff check app tests alembic --fix
	cd backend && ruff format app tests alembic

frontend-format:
	cd frontend && npm run lint:fix

load-test:
	cd backend && locust -f tests/load/locustfile.py --host http://localhost
