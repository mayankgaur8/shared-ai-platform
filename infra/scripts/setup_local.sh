#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Local Development Setup Script
# Run once after cloning the repo to get the full stack running locally.
# ─────────────────────────────────────────────────────────────────────────────
set -e

echo "==> [1/7] Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "Docker required. Install from https://docker.com"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.12+ required."; exit 1; }

echo "==> [2/7] Setting up .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "    Created .env from .env.example"
    echo "    ⚠️  Edit .env and set your JWT_SECRET before continuing"
else
    echo "    .env already exists, skipping"
fi

echo "==> [3/7] Starting infrastructure (postgres, redis, ollama)..."
docker compose -f infra/docker/docker-compose.yml up -d postgres redis ollama
echo "    Waiting for postgres to be ready..."
sleep 5

echo "==> [4/7] Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt -r requirements-dev.txt
echo "    Dependencies installed"

echo "==> [5/7] Running database migrations..."
alembic upgrade head
echo "    Migrations applied"

echo "==> [6/7] Seeding default data..."
python3 infra/scripts/seed_db.py
echo "    Database seeded"

echo "==> [7/7] Pulling Ollama models..."
docker exec $(docker ps -qf "name=ollama") ollama pull llama3.2 || echo "    (Pull manually: docker exec <ollama_container> ollama pull llama3.2)"
docker exec $(docker ps -qf "name=ollama") ollama pull nomic-embed-text || echo "    (Pull manually for embeddings)"

echo ""
echo "✅ Setup complete!"
echo ""
echo "   Start the API server:    source .venv/bin/activate && uvicorn app.main:app --reload"
echo "   Or with Docker:          docker compose -f infra/docker/docker-compose.yml up"
echo ""
echo "   API docs:                http://localhost:8000/docs"
echo "   Health check:            http://localhost:8000/health"
echo "   Celery Flower:           http://localhost:5555"
