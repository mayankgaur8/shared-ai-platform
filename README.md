# Shared AI Interface Backend (SAIB)

> **One central AI platform to power all your apps.**
> Centralized model management · Prompt registry · User memory · Safety · Analytics

---

## What This Is

SAIB is a production-grade shared AI gateway that lets you build and run multiple AI-powered apps
(EduAI, Interview Prep, Resume Builder, Health Assistant, Astrology App, and future products)
from a single backend platform. Every app delegates model calls, prompt rendering, safety checks,
and user context to this shared backend.

**The key principle:** change a prompt once → all apps benefit immediately.
Swap a model once → every app automatically uses the new one. No per-app code changes.

---

## Documentation Index

| Document | Contents |
|----------|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Complete system design, tech stack, DB schema, API design, all 15 sections |
| [CODE_EXAMPLES.md](./CODE_EXAMPLES.md) | Starter code for all core modules (adapters, router, safety, memory, RAG) |
| [DIAGRAMS.md](./DIAGRAMS.md) | 12 Mermaid system diagrams (architecture, request flow, RAG, memory, safety, deployment) |
| [PROMPTS_SEED.md](./PROMPTS_SEED.md) | Ready-to-use prompt templates for all 9 workflows |

---

## Quick Start (Local Development)

```bash
# 1. Clone and setup
git clone <repo>
cd shared-ai-interface-backend
chmod +x infra/scripts/setup_local.sh
./infra/scripts/setup_local.sh

# 2. Pull Ollama model (first time)
docker exec <ollama_container_id> ollama pull llama3.2
docker exec <ollama_container_id> ollama pull nomic-embed-text

# 3. Start everything
docker compose -f infra/docker/docker-compose.yml up

# 4. Run a test request
curl -X POST http://localhost:8000/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt>" \
  -H "X-App-Id: <your_app_id>" \
  -d '{
    "workflow": "quiz_generation",
    "inputs": {
      "topic": "Photosynthesis",
      "question_count": 5,
      "grade_level": "8th grade"
    }
  }'
```

**API Docs:** http://localhost:8000/docs (DEBUG mode)
**Celery Monitor:** http://localhost:5555

---

## Platform Architecture (Summary)

```
Client Apps (EduAI, Interview, Resume, Health, Astrology)
    ↓ HTTPS
API Gateway (rate limiting, SSL)
    ↓
Auth Service (JWT, App Identity, RBAC)
    ↓
Orchestration Engine ─── Safety Middleware (pre + post)
    ├── Prompt Registry (Jinja2 versioned templates)
    ├── Model Router (task type → best model → fallback chain)
    ├── Context Builder (memory + RAG)
    └── Workflow Executor (named workflows per use case)
         ↓
Inference Adapters → Ollama (local) | OpenAI (fallback)
         ↓
Data Layer: PostgreSQL + pgvector | Redis | Azure Blob
         ↓
Observability: structlog + OpenTelemetry + Grafana
```

---

## Supported Workflows

| Workflow Key | Use Case | App |
|---|---|---|
| `quiz_generation` | Structured quiz with MCQ + short answer | EduAI |
| `assignment_generation` | Full assignment with rubric | EduAI |
| `mcq_generation` | Pure MCQ batch generation | EduAI |
| `question_paper` | Full question paper layout | EduAI |
| `interview_questions` | Interview Q bank with scoring guide | Interview Prep |
| `mock_interview_chat` | Multi-turn mock interview | Interview Prep |
| `resume_analysis` | ATS scoring + improvement suggestions | Resume Builder |
| `health_chatbot` | Wellness chatbot with strict guardrails | Health Assistant |
| `astrology_insights` | Personalized astrology readings | Astrology App |
| `english_coach_chat` | Conversational English coaching with corrections and one follow-up question | English Learning |

---

## English Coach Workflow

`english_coach_chat` is a structured chat workflow for English learners. It returns a friendly reply, validated correction items, and one follow-up practice question.

`goal` is optional for this workflow. If it is omitted, the backend safely defaults it to `General English improvement` before rendering the prompt.

If the model output is malformed, the backend falls back gracefully at a high level:
- it first tries to extract a JSON object if the model wrapped it in extra prose
- if parsing still fails, it returns the raw model text as `reply`
- `corrections` becomes `[]` and `follow_up_question` becomes `""`

No new environment variables are required for this workflow; it uses the existing Ollama, routing, timeout, and cache settings already documented in [.env.example](./.env.example).

### Example Request

```bash
curl -X POST http://localhost:8000/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": "english_coach_chat",
    "inputs": {
      "topic": "Daily routines",
      "user_message": "Yesterday I goed to market and buyed many things.",
      "level": "beginner",
      "goal": "Improve past tense"
    }
  }'
```

### Example Structured Response

```json
{
  "workflow": "english_coach_chat",
  "workflow_type": "english_learning",
  "reply": "Great effort! Two small fixes below.",
  "corrections": [
    {
      "original": "goed",
      "corrected": "went",
      "explanation": "irregular verb"
    },
    {
      "original": "buyed",
      "corrected": "bought",
      "explanation": "irregular verb"
    }
  ],
  "follow_up_question": "What did you do last weekend?",
  "model_used": "ollama/llama3.2",
  "tokens_used": {
    "input": 50,
    "output": 80
  },
  "latency_ms": 123,
  "cost_usd": 0.0,
  "cached": false
}
```

---

## Tech Stack

| Component | Technology |
|---|---|
| API Framework | Python FastAPI |
| Database | PostgreSQL 16 + pgvector |
| Cache + Queue | Redis + Celery |
| Local LLM | Ollama |
| External LLM | OpenAI (fallback) |
| Vector Search | pgvector → Qdrant (Phase 5) |
| Object Storage | Azure Blob Storage |
| Templating | Jinja2 |
| Logging | structlog + OpenTelemetry |
| Deployment | Docker → Azure App Service → AKS |
| CI/CD | GitHub Actions |

---

## Development Phases

| Phase | Goal | Timeline |
|---|---|---|
| **Phase 1** | MVP: Auth + Ollama + Prompt Registry + EduAI workflows | Weeks 1–6 |
| **Phase 2** | All 5 apps integrated + safety policies | Weeks 7–10 |
| **Phase 3** | RAG pipeline + user long-term memory | Weeks 11–15 |
| **Phase 4** | Analytics dashboard + OpenAI fallback + admin UI | Weeks 16–20 |
| **Phase 5** | AKS migration + Qdrant + hardening + SLA | Weeks 21–28 |

---

## Project Structure

```
shared-ai-backend/
├── app/
│   ├── main.py                # FastAPI app factory
│   ├── config/                # Settings, DB, Redis
│   ├── auth/                  # JWT, OAuth2, RBAC
│   ├── apps/                  # App registry
│   ├── users/                 # User management
│   ├── prompts/               # Prompt registry + renderer
│   ├── models_registry/       # Model provider + model config
│   ├── adapters/              # Ollama, OpenAI adapters
│   ├── router_engine/         # Smart model router
│   ├── orchestration/         # Workflow executor + context builder
│   ├── workflows/             # Named workflow definitions
│   ├── rag/                   # Document upload, chunking, retrieval
│   ├── memory/                # User memory (short + long term)
│   ├── templates/             # Response templates
│   ├── safety/                # Guardrails, injection detection
│   ├── logging_service/       # Structured request/response logging
│   ├── analytics/             # Usage and cost metrics
│   ├── admin/                 # Admin-only endpoints
│   ├── jobs/                  # Celery background jobs
│   └── shared/                # Exceptions, utilities
├── migrations/                # Alembic migrations
├── tests/                     # Unit, integration, e2e
├── infra/
│   ├── docker/                # Dockerfile, docker-compose
│   ├── kubernetes/            # AKS Helm manifests
│   ├── azure/                 # Bicep IaC
│   └── scripts/               # Setup and seed scripts
├── .github/workflows/         # CI/CD pipelines
├── .env.example
├── pyproject.toml
└── requirements.txt
```

---

## License

Private — Internal Platform
