.PHONY: run logs down lint type test upgrade downgrade migrate

run:
	docker compose up --build -d

logs:
	docker compose logs -f api consumer celery-worker

down:
	docker compose down -v

lint:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy app consumer worker scripts

test:
	uv run pytest

upgrade:
	uv run alembic upgrade head

# make downgrade REV=0001_initial
downgrade:
	uv run alembic downgrade $(REV)

# make migrate MSG="add something"
migrate:
	uv run alembic revision --autogenerate -m "$(MSG)"
