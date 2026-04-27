set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

default: help

help:
	just --list

fmt:
	ruff format .

lint:
	ruff check .

test:
	pytest -q

check: fmt lint test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f websearch-proxy

health:
	curl -fsS http://127.0.0.1:8082/healthz

build:
	docker compose build websearch-proxy

shell:
	docker compose exec websearch-proxy /bin/sh
