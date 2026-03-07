.PHONY: run test migrate setup lint

run:
	poetry run flask run

test:
	poetry run pytest

migrate:
	poetry run flask db upgrade

migration:
	poetry run flask db revision --autogenerate -m "$(msg)"

setup:
	poetry install
	cp -n .env.example .env || true
	@echo "Edit .env with your credentials, then run: make migrate && make run"

lint:
	poetry run flake8 virtual_assistant/
	poetry run isort --check-only virtual_assistant/
