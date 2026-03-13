# Quick Start Guide

Two ways to run the backend. Use **Option A** if Docker Hub pulls are timing out.

---

## Option A — Run Locally (No Docker Required)

This works right now even without Docker Hub access.

### Prerequisites
- Python 3.12+
- PostgreSQL 15/16 installed locally (or use [Postgres.app](https://postgresapp.com) on macOS)
- Redis installed locally (`brew install redis` on macOS)
- [Ollama](https://ollama.com) installed and running

### Steps

```bash
# 1. Create and activate virtualenv
cd /Users/mayankgaur/Documents/shared-AI-interface-backend
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env if needed — defaults work for local Postgres/Redis/Ollama

# 4. Create the database
createdb saib        # or use psql: CREATE DATABASE saib;

# 5. Run migrations
alembic upgrade head

# 6. Pull Ollama model (one-time)
ollama pull llama3.2
ollama pull nomic-embed-text   # for RAG embeddings

# 7. Start the API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now live at **http://localhost:8000**

- Swagger UI:    http://localhost:8000/docs
- Health check:  http://localhost:8000/health
- Ready check:   http://localhost:8000/ready  (shows Ollama status)
- Workflows:     http://localhost:8000/v1/workflows

### Test a workflow

```bash
# Quiz generation (no auth required in stub mode)
curl -X POST http://localhost:8000/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "quiz_generation",
    "inputs": {
      "topic": "Newton'\''s Laws of Motion",
      "question_count": 3,
      "grade_level": "10th grade"
    }
  }'

# Health chatbot
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are some tips for better sleep?",
    "workflow_context": "health_chatbot"
  }'

# List all available workflows
curl http://localhost:8000/v1/workflows
```

---

## Option B — Docker Compose (Once Docker Hub is Reachable)

### Fix the TLS timeout

The `pull_policy: if_not_present` directive in `docker-compose.yml` is already set —
once each image is pulled once it will **never be re-pulled** on subsequent `docker compose up`.

**To pull images once (with retry on timeout):**
```bash
# Pull infrastructure images separately — retry if one times out
docker pull pgvector/pgvector:pg16
docker pull redis:7-alpine
docker pull ollama/ollama:latest
docker pull mher/flower:2.0

# Once all images are in local cache, compose up works offline:
docker compose -f infra/docker/docker-compose.yml up -d
```

**If Docker Hub is completely blocked on your network:**
```bash
# Option: use a registry mirror
# Add to /etc/docker/daemon.json (or Docker Desktop → Settings → Docker Engine):
{
  "registry-mirrors": ["https://mirror.gcr.io"]
}
# Then restart Docker Desktop and retry the pulls above.
```

### Start services

```bash
# Infrastructure only (postgres + redis + ollama) — skips api/worker build
docker compose -f infra/docker/docker-compose.yml up -d postgres redis ollama

# Wait for healthy, then start the api
docker compose -f infra/docker/docker-compose.yml up -d api

# Or start everything at once
docker compose -f infra/docker/docker-compose.yml up -d
```

### Pull Ollama model inside the container

```bash
docker compose -f infra/docker/docker-compose.yml exec ollama ollama pull llama3.2
docker compose -f infra/docker/docker-compose.yml exec ollama ollama pull nomic-embed-text
```

### Run migrations inside the container

```bash
docker compose -f infra/docker/docker-compose.yml exec api alembic upgrade head
```

---

## What Works Right Now (Stub Mode)

The API boots and is fully functional for AI calls — it talks directly to Ollama:

| Endpoint | Status |
|---|---|
| `GET /health` | ✅ Always returns 200 |
| `GET /ready` | ✅ Shows Ollama reachability |
| `GET /v1/workflows` | ✅ Lists all 9 workflows |
| `POST /v1/generate` | ✅ Calls Ollama — returns real AI output |
| `POST /v1/chat` | ✅ Calls Ollama — returns real AI response |
| `GET /docs` | ✅ Swagger UI |
| Safety middleware | ✅ Injection detection on all POST /v1/* paths |
| All other endpoints | ⏳ Stub — returns placeholder JSON |

## What's a Stub (Implement Next)

In order of priority for Phase 1:

1. **Auth** (`app/auth/`) — JWT login, register, `get_current_user` dependency
2. **App Registry** (`app/apps/`) — CRUD + API key validation
3. **Prompt Registry** (`app/prompts/`) — CRUD + versioning + Jinja2 renderer
4. **Model Registry** (`app/models_registry/`) — Register Ollama models in DB
5. **DB-backed logging** (`app/logging_service/`) — Persist request logs to PostgreSQL

All implementation patterns are in [CODE_EXAMPLES.md](./CODE_EXAMPLES.md).
The full DB schema is in [ARCHITECTURE.md](./ARCHITECTURE.md#5-database-design).
