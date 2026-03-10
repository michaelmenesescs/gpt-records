.PHONY: up down logs shell db-shell qdrant-shell migrate cli

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f agent

build:
	docker compose build

shell:
	docker compose exec agent bash

db-shell:
	docker compose exec db psql -U gpt -d gpt_records

qdrant-shell:
	open http://localhost:6333/dashboard

migrate:
	docker compose exec agent python -c "from db.session import init_db; from memory.qdrant_store import init_collections; init_db(); init_collections()"

# Interactive agent CLI (runs inside container)
cli:
	docker compose exec agent python -m agent

# Run the agent CLI locally (requires .env set up)
cli-local:
	cd agent && python -m agent
