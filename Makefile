PYTHON ?= python3

.PHONY: setup up down init-db migrate run worker test-chunking

setup:
	$(PYTHON) -m pip install -r requirements.txt

up:
	docker compose -f docker-compose.local.yml up -d

down:
	docker compose -f docker-compose.local.yml down

init-db:
	flask --app run.py db init
	flask --app run.py db migrate -m "initial schema"
	flask --app run.py db upgrade

migrate:
	flask --app run.py db upgrade

run:
	$(PYTHON) run.py

worker:
	$(PYTHON) worker.py

test-chunking:
	$(PYTHON) scripts/test_wordpress_chunking.py --limit 5
