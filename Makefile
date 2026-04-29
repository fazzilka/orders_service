.PHONY: run logs down lint type test upgrade downgrade migrate

UV_DEV_RUN = uv run --extra dev

run:
	docker compose up --build -d

logs:
	docker compose logs -f api consumer celery-worker

down:
	docker compose down

lint:
	$(UV_DEV_RUN) ruff format .
	$(UV_DEV_RUN) ruff check --fix .

type:
	$(UV_DEV_RUN) mypy app consumer worker scripts

test:
	$(UV_DEV_RUN) pytest

upgrade:
	uv run alembic upgrade head

# make downgrade REV=0001_initial
downgrade:
	uv run alembic downgrade $(REV)

# make migrate MSG="add something"
migrate:
	uv run alembic revision --autogenerate -m "$(MSG)"
