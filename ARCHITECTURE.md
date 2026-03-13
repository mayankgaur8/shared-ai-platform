# Shared AI Interface Backend — Complete Architecture Blueprint

> **Version:** 1.0
> **Date:** 2026-03-13
> **Author:** Principal AI Architect
> **Status:** Implementation-Ready Blueprint

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Recommended Tech Stack](#3-recommended-tech-stack)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Database Design](#5-database-design)
6. [API Design](#6-api-design)
7. [Prompt Management Design](#7-prompt-management-design)
8. [Model Routing Design](#8-model-routing-design)
9. [Memory and Context Design](#9-memory-and-context-design)
10. [Safety and Guardrails](#10-safety-and-guardrails)
11. [Logging and Observability](#11-logging-and-observability)
12. [Deployment Architecture (Azure)](#12-deployment-architecture-azure)
13. [Development Roadmap](#13-development-roadmap)
14. [Code Examples](#14-code-examples)
15. [System Diagrams](#15-system-diagrams)
16. [Final Recommendation](#16-final-recommendation)

---

## 1. Project Vision

The **Shared AI Interface Backend (SAIB)** is a centralized AI gateway and intelligence platform that powers all current and future applications from a single control plane. Instead of embedding AI logic inside each product, every app delegates to this backend for model calls, prompt rendering, context management, safety checks, and logging.

### Platform Apps Supported

| App | Primary AI Workflows |
|-----|---------------------|
| EduAI | Quiz gen, assignment gen, question paper gen, MCQ gen |
| Interview Prep | Question gen, mock interview chat, feedback analysis |
| Resume Builder | ATS analysis, resume scoring, suggestion engine |
| Health Assistant | Symptom guidance chatbot with strict guardrails |
| Astrology App | Insights engine, horoscope generation |
| Future Products | Any LLM-driven feature |

### Core Platform Capabilities

```
┌─────────────────────────────────────────────────────┐
│             SHARED AI INTERFACE BACKEND              │
├─────────────┬─────────────┬──────────────────────────┤
│  Model Mgmt │  Prompt Mgmt│   User Memory & Context  │
├─────────────┼─────────────┼──────────────────────────┤
│  Workflows  │  Templates  │   Safety & Guardrails     │
├─────────────┼─────────────┼──────────────────────────┤
│  RAG / Docs │  Caching    │   Logs, Tracing, Analytics│
├─────────────┼─────────────┼──────────────────────────┤
│  Auth & API │  Rate Limit │   Admin Dashboard         │
└─────────────┴─────────────┴──────────────────────────┘
```

---

## 2. High-Level Architecture

### Architecture Overview

The system is organized into 8 horizontal layers:

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: CLIENT APPS                                            │
│  EduAI | Interview Prep | Resume Builder | Health | Astrology    │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS / REST
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 2: API GATEWAY (Kong / Azure APIM)                        │
│  Rate Limiting | SSL Termination | Routing | API Key Validation  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 3: AUTH SERVICE                                           │
│  JWT Validation | OAuth2 | App Identity | RBAC                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 4: ORCHESTRATION ENGINE (Core Backend)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │  Workflow   │  │   Prompt     │  │    Safety Middleware     │ │
│  │  Executor   │  │   Registry   │  │    (Pre/Post filter)     │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬────────────┘ │
│         └────────────────▼──────────────────────-─┘             │
│                    Model Router                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 5: INFERENCE ADAPTERS                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Ollama Adapter│  │OpenAI Adapter│  │ Future Provider Adapter│ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 6: DATA LAYER                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  PostgreSQL  │  │    Redis     │  │  Vector DB (Qdrant)    │ │
│  │  (Main DB)   │  │  (Cache+MQ)  │  │  (RAG + Embeddings)    │ │
│  └──────────────┘  └──────────────┘  └────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 7: OBSERVABILITY                                          │
│  Structured Logs | Distributed Tracing | Metrics | Alerting      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  LAYER 8: ADMIN CONTROL PLANE                                    │
│  Dashboard | Analytics | Prompt Mgmt UI | Model Config UI        │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **API Gateway** | SSL termination, rate limiting, API key auth, request routing to correct service |
| **Auth Service** | JWT/OAuth2 validation, app-level identity (each client app has its own app_id + secret), RBAC for users |
| **Orchestration Engine** | The brain — receives workflow requests, selects prompts, triggers safety checks, calls model router, stores results |
| **Workflow Executor** | Executes named workflows (e.g., `quiz_generation`, `mock_interview`) using registered workflow definitions |
| **Prompt Registry** | Stores, versions, and renders prompt templates with variable injection |
| **Safety Middleware** | Pre-checks input for injection/jailbreak, post-checks output for harmful content, applies per-app policies |
| **Model Router** | Selects the best model for the task, handles fallbacks, enforces per-app and per-user model preferences |
| **Inference Adapters** | Thin clients wrapping Ollama, OpenAI, and future provider APIs behind a unified interface |
| **RAG Service** | Chunks and embeds documents, retrieves relevant context for augmented prompts |
| **User Memory Service** | Stores and retrieves short-term session context, long-term user memory, and app-specific preferences |
| **Cache Layer (Redis)** | Caches prompt renders, model responses, embeddings lookups |
| **Background Jobs** | Async tasks: embedding generation, audit log flush, usage metric aggregation, scheduled reports |
| **Admin Dashboard** | Web UI for managing prompts, models, apps, safety policies, analytics |
| **Observability Stack** | Centralized structured logs, traces, metrics — queryable for debugging and business insights |

---

## 3. Recommended Tech Stack

### Option A: Budget-Friendly MVP Stack

> **Best for:** Solo developer or small team, fast iteration, low infrastructure cost

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend Runtime** | Python FastAPI | Fastest to build AI backends; native async; rich AI ecosystem |
| **Background Jobs** | Celery + Redis | Simple task queue, works well with FastAPI |
| **Main Database** | PostgreSQL 16 (Supabase or Railway) | Fully relational, JSONB for flexible fields, cheap managed hosting |
| **Cache / Queue** | Redis (Upstash or self-hosted) | Session cache, response cache, Celery broker |
| **Vector DB** | pgvector (extension on PostgreSQL) | Zero extra infra; good enough for <1M vectors |
| **Ollama** | Self-hosted on a single VM (Azure B-series GPU) | Local LLM serving |
| **Object Storage** | Azure Blob Storage | Document uploads |
| **Admin Dashboard** | FastAPI + simple React app or Retool | Quick to build |
| **Auth** | FastAPI + PyJWT + OAuth2 via Auth0 (free tier) | Solid JWT auth |
| **Monitoring** | Sentry (errors) + Prometheus + Grafana (free OSS) | Essential observability |
| **Deployment** | Azure App Service (Docker container) | Simple, no K8s complexity |
| **CI/CD** | GitHub Actions | Free for public repos, easy to configure |

**Monthly cost estimate:** $80–200/month (App Service B2, PostgreSQL Flexible, Redis Cache Basic, Blob)

---

### Option B: Enterprise Production Stack

> **Best for:** Multi-team, high traffic, SLA requirements, multi-tenant SaaS

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend Runtime** | Python FastAPI (core) + Node.js NestJS (admin/BFF) | FastAPI for AI latency-sensitive paths; NestJS for admin/BFF |
| **Background Jobs** | Celery + Redis Streams or Azure Service Bus | Durable, observable task processing |
| **Main Database** | Azure Database for PostgreSQL Flexible Server | Managed, HA, read replicas |
| **Cache** | Azure Cache for Redis (Premium tier) | Cluster mode, geo-replication |
| **Vector DB** | Qdrant (self-hosted on AKS or Qdrant Cloud) | Purpose-built, fast, supports filtering + namespaces |
| **Local LLM** | Ollama on Azure NC-series GPU VM or vLLM | Production-grade LLM inference |
| **Object Storage** | Azure Blob Storage + CDN | Documents, model artifacts |
| **Admin Dashboard** | React + Ant Design Pro | Full-featured admin UI |
| **Auth** | Azure AD B2C or Keycloak | Enterprise SSO + RBAC |
| **API Gateway** | Azure API Management (APIM) | Managed throttling, analytics, versioning |
| **Monitoring** | Azure Monitor + Application Insights + Grafana | Full observability suite |
| **Orchestration** | Azure Kubernetes Service (AKS) | Scale individual services independently |
| **Secrets** | Azure Key Vault | Centralized secrets, provider API keys |
| **CI/CD** | Azure DevOps Pipelines or GitHub Actions + GHCR | Full pipeline with environments |
| **Message Queue** | Azure Service Bus | Reliable async, dead-letter queues |
| **Search** | Azure AI Search (optional) | Hybrid BM25 + vector search for RAG |

**Monthly cost estimate:** $800–2500/month depending on GPU/model tier and traffic

---

### Which Stack to Choose: The Honest Recommendation

**Start with Option A (FastAPI + PostgreSQL + pgvector + Redis + Azure App Service).**

Reasons:
- You can ship the MVP in 4–6 weeks with one developer
- FastAPI has first-class Pydantic models — perfect for validating AI requests/responses
- pgvector eliminates a separate vector database until you exceed ~500K document chunks
- The entire stack migrates cleanly to Option B — FastAPI runs in K8s unchanged, pgvector migrates to Qdrant with a data migration script
- Azure App Service → AKS migration requires only Dockerfile + Helm chart additions

**Migrate to Option B when:**
- You exceed 1000 requests/day
- You need multi-region or HA
- You have 3+ apps using the platform in production

---

## 4. Project Folder Structure

```
shared-ai-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app factory, lifespan, middleware registration
│   ├── config/
│   │   ├── settings.py              # Pydantic BaseSettings — all env vars
│   │   ├── database.py              # SQLAlchemy engine + session factory
│   │   ├── redis.py                 # Redis connection pool
│   │   ├── vector_db.py             # Qdrant / pgvector client
│   │   └── logging.py              # Structlog configuration
│   │
│   ├── auth/
│   │   ├── router.py                # POST /auth/token, POST /auth/refresh, POST /auth/logout
│   │   ├── service.py               # JWT creation, validation, refresh logic
│   │   ├── models.py                # User, AppIdentity DB models
│   │   ├── schemas.py               # Pydantic request/response schemas
│   │   ├── dependencies.py          # FastAPI dependency: get_current_user, get_app_context
│   │   └── oauth.py                 # OAuth2 provider integrations
│   │
│   ├── apps/                        # App Registry — each client app registers here
│   │   ├── router.py                # CRUD for app registration
│   │   ├── service.py
│   │   ├── models.py                # App, AppConfig DB models
│   │   └── schemas.py
│   │
│   ├── users/
│   │   ├── router.py                # User profile, preferences, history
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   │
│   ├── prompts/                     # Central Prompt Registry
│   │   ├── router.py                # CRUD + versioning + test endpoints
│   │   ├── service.py               # Prompt CRUD, versioning, rollback
│   │   ├── renderer.py              # Jinja2 variable injection engine
│   │   ├── models.py                # Prompt, PromptVersion DB models
│   │   └── schemas.py
│   │
│   ├── models_registry/             # AI Model Registry (not Python models)
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py                # ModelProvider, ModelConfig DB models
│   │   └── schemas.py
│   │
│   ├── adapters/                    # Inference Provider Adapters
│   │   ├── base.py                  # Abstract BaseAdapter interface
│   │   ├── ollama_adapter.py        # Ollama REST API client
│   │   ├── openai_adapter.py        # OpenAI SDK wrapper
│   │   ├── adapter_factory.py       # Returns correct adapter by provider name
│   │   └── response_normalizer.py   # Normalizes all provider responses to unified schema
│   │
│   ├── router_engine/               # Smart Model Router
│   │   ├── router.py                # FastAPI endpoints for manual routing queries
│   │   ├── model_router.py          # Core routing logic — task type, cost, latency, fallback
│   │   ├── routing_rules.py         # Rule engine for routing decisions
│   │   └── schemas.py
│   │
│   ├── orchestration/               # Workflow Orchestration Engine
│   │   ├── router.py                # POST /run, POST /chat, POST /stream
│   │   ├── executor.py              # WorkflowExecutor — loads and runs workflow definitions
│   │   ├── context_builder.py       # Assembles full context: memory + docs + prompt
│   │   └── schemas.py
│   │
│   ├── workflows/                   # Named Workflow Definitions
│   │   ├── base_workflow.py         # Abstract Workflow base class
│   │   ├── quiz_generation.py
│   │   ├── assignment_generation.py
│   │   ├── question_paper.py
│   │   ├── mcq_generation.py
│   │   ├── interview_questions.py
│   │   ├── mock_interview_chat.py
│   │   ├── resume_analysis.py
│   │   ├── health_chatbot.py
│   │   ├── astrology_insights.py
│   │   └── registry.py              # Maps workflow name → class
│   │
│   ├── rag/                         # Retrieval Augmented Generation
│   │   ├── router.py                # Document upload, query RAG endpoints
│   │   ├── chunker.py               # Text splitting strategies
│   │   ├── embedder.py              # Embedding model calls (local or API)
│   │   ├── retriever.py             # Vector similarity search + reranking
│   │   ├── indexer.py               # Orchestrates chunk → embed → store pipeline
│   │   ├── models.py                # Document, DocumentChunk DB models
│   │   └── schemas.py
│   │
│   ├── memory/                      # User Memory and Context Service
│   │   ├── router.py
│   │   ├── service.py               # Read/write short-term, long-term, app memory
│   │   ├── models.py                # Session, Message, UserMemory DB models
│   │   ├── summarizer.py            # LLM-based memory compression
│   │   └── schemas.py
│   │
│   ├── templates/                   # Response/Document Templates
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── schemas.py
│   │
│   ├── safety/                      # Safety and Guardrails Module
│   │   ├── middleware.py            # FastAPI middleware for pre/post safety checks
│   │   ├── moderation.py            # Content moderation logic
│   │   ├── injection_detector.py    # Prompt injection and jailbreak detection
│   │   ├── output_sanitizer.py      # Output cleaning and disclaimer injection
│   │   ├── policy_engine.py         # Per-app safety policy evaluator
│   │   ├── models.py                # SafetyPolicy, SafetyLog DB models
│   │   └── schemas.py
│   │
│   ├── logging_service/             # Structured Request/Response Logging
│   │   ├── middleware.py            # Request logging middleware
│   │   ├── service.py               # Log write service
│   │   ├── models.py                # RequestLog, ErrorLog, AuditLog DB models
│   │   └── schemas.py
│   │
│   ├── analytics/                   # Usage Analytics and Cost Tracking
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── aggregator.py            # Scheduled aggregation jobs
│   │   ├── models.py                # UsageMetric, BillingMetric DB models
│   │   └── schemas.py
│   │
│   ├── admin/                       # Admin Endpoints (protected)
│   │   ├── router.py                # Admin-only endpoints
│   │   ├── dashboard_service.py     # Summary metrics for dashboard
│   │   └── schemas.py
│   │
│   ├── jobs/                        # Background Job Definitions
│   │   ├── celery_app.py            # Celery application instance
│   │   ├── embedding_job.py         # Async document embedding
│   │   ├── audit_flush_job.py       # Batch audit log writes
│   │   ├── usage_aggregation_job.py # Daily/hourly metric rollups
│   │   ├── memory_summarize_job.py  # Long-term memory compression
│   │   └── health_check_job.py      # Model provider health pings
│   │
│   └── shared/                      # Shared utilities
│       ├── exceptions.py            # Custom exception classes
│       ├── pagination.py            # Pagination helpers
│       ├── cache.py                 # Redis cache decorators/helpers
│       └── utils.py                 # Token counting, text utilities
│
├── migrations/                      # Alembic DB migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/
│   ├── conftest.py                  # Fixtures: test DB, test client, mock adapters
│   ├── unit/
│   │   ├── test_model_router.py
│   │   ├── test_prompt_renderer.py
│   │   ├── test_safety_middleware.py
│   │   └── test_workflow_executor.py
���   ├── integration/
│   │   ├── test_orchestration_api.py
│   │   ├── test_rag_pipeline.py
│   │   └── test_memory_service.py
│   └── e2e/
│       ├── test_quiz_workflow.py
│       └── test_mock_interview.py
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile               # Production multi-stage Dockerfile
│   │   ├── Dockerfile.dev           # Development with hot reload
│   │   └── docker-compose.yml       # Full local stack
│   ├── kubernetes/
│   │   ├── namespace.yaml
│   │   ├── deployment-api.yaml
│   │   ├── deployment-worker.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── hpa.yaml                 # Horizontal Pod Autoscaler
│   │   └── secrets.yaml             # Reference to Key Vault
│   ├── azure/
│   │   ├── main.bicep               # Infrastructure as Code (Azure Bicep)
│   │   ├── modules/
│   │   │   ├── appservice.bicep
│   │   │   ├── postgresql.bicep
│   │   │   ├── redis.bicep
│   │   │   ├── keyvault.bicep
│   │   │   └── storage.bicep
│   │   └── parameters/
│   │       ├── dev.json
│   │       ├── qa.json
│   │       └── prod.json
│   └── scripts/
│       ├── setup_local.sh
│       └── seed_db.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml                   # Tests + lint on PR
│       └── deploy.yml               # Build + push + deploy on merge to main
│
├── .env.example
├── alembic.ini
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## 5. Database Design

### Entity Relationship Overview

```
users ──< sessions ──< messages
  │
  ├──< user_memory
  └──< audit_logs

apps ──< app_configs
  │
  ├──< safety_policies
  └──< workflow_runs

prompts ──< prompt_versions
  │
  └── (referenced by workflow_runs)

model_providers ──< model_registry
  │
  └── (referenced by workflow_runs, request_logs)

documents ──< document_chunks
  │
  └──< embeddings

request_logs ──< response_logs
  │
  ├──< error_logs
  └──< usage_metrics

templates (standalone, referenced by prompts)
billing_metrics (aggregated from usage_metrics)
```

### Full Schema DDL

```sql
-- ============================================================
-- USERS AND AUTH
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) UNIQUE,
    full_name       VARCHAR(255),
    hashed_password VARCHAR(255),               -- null for OAuth users
    auth_provider   VARCHAR(50) DEFAULT 'local', -- 'local', 'google', 'azure_ad'
    external_id     VARCHAR(255),               -- provider's user ID
    tier            VARCHAR(20) DEFAULT 'free', -- 'free', 'pro', 'enterprise'
    is_active       BOOLEAN DEFAULT TRUE,
    is_admin        BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- APPS (client application registry)
-- ============================================================
CREATE TABLE apps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) UNIQUE NOT NULL,  -- 'eduai', 'interview_prep'
    display_name    VARCHAR(255) NOT NULL,
    description     TEXT,
    api_key_hash    VARCHAR(255) NOT NULL,          -- hashed app API key
    webhook_url     VARCHAR(500),
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app_configs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id                  UUID REFERENCES apps(id) ON DELETE CASCADE,
    default_model_id        UUID,                  -- FK to model_registry (set after)
    fallback_model_id       UUID,
    max_tokens_per_request  INTEGER DEFAULT 4096,
    rate_limit_rpm          INTEGER DEFAULT 60,    -- requests per minute
    rate_limit_daily        INTEGER DEFAULT 1000,
    allowed_workflows       TEXT[] DEFAULT '{}',
    safety_policy_id        UUID,                  -- FK to safety_policies
    memory_enabled          BOOLEAN DEFAULT TRUE,
    rag_enabled             BOOLEAN DEFAULT FALSE,
    custom_system_prompt    TEXT,
    extra_config            JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(app_id)
);

-- ============================================================
-- SESSIONS AND MESSAGES
-- ============================================================
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    session_key     VARCHAR(255) UNIQUE NOT NULL,  -- client-generated or server-assigned
    title           VARCHAR(500),
    context_summary TEXT,                          -- compressed summary of past messages
    message_count   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    last_activity   TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,          -- 'user', 'assistant', 'system'
    content         TEXT NOT NULL,
    content_type    VARCHAR(50) DEFAULT 'text',    -- 'text', 'json', 'markdown'
    tokens_used     INTEGER,
    model_id        UUID,                          -- FK to model_registry
    latency_ms      INTEGER,
    is_flagged      BOOLEAN DEFAULT FALSE,
    flag_reason     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- PROMPTS AND VERSIONING
-- ============================================================
CREATE TABLE prompts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id          UUID REFERENCES apps(id),      -- NULL = global prompt
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,          -- 'quiz_generation_v1'
    description     TEXT,
    category        VARCHAR(100),                  -- 'generation', 'chat', 'analysis'
    is_global       BOOLEAN DEFAULT FALSE,
    active_version  INTEGER DEFAULT 1,
    is_archived     BOOLEAN DEFAULT FALSE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(app_id, slug)
);

CREATE TABLE prompt_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id       UUID REFERENCES prompts(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    system_template TEXT,                          -- Jinja2 template for system message
    user_template   TEXT NOT NULL,                 -- Jinja2 template for user message
    variables       JSONB DEFAULT '[]',            -- [{"name": "topic", "type": "string", "required": true}]
    model_params    JSONB DEFAULT '{}',            -- {"temperature": 0.7, "max_tokens": 1024}
    test_inputs     JSONB DEFAULT '{}',            -- example variable values for testing
    notes           TEXT,                          -- change notes
    is_published    BOOLEAN DEFAULT FALSE,
    published_at    TIMESTAMPTZ,
    published_by    UUID REFERENCES users(id),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(prompt_id, version)
);

-- ============================================================
-- MODEL PROVIDERS AND REGISTRY
-- ============================================================
CREATE TABLE model_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) UNIQUE NOT NULL,  -- 'ollama', 'openai', 'anthropic'
    display_name    VARCHAR(255),
    base_url        VARCHAR(500),
    api_key_secret  VARCHAR(255),                  -- Key Vault reference name
    is_active       BOOLEAN DEFAULT TRUE,
    health_check_url VARCHAR(500),
    last_health_at  TIMESTAMPTZ,
    is_healthy      BOOLEAN DEFAULT TRUE,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE model_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID REFERENCES model_providers(id),
    model_name      VARCHAR(255) NOT NULL,         -- 'llama3.2', 'gpt-4o', 'mistral'
    display_name    VARCHAR(255),
    model_type      VARCHAR(50),                   -- 'chat', 'completion', 'embedding'
    context_window  INTEGER,                       -- max context tokens
    cost_per_1k_input  DECIMAL(10,6) DEFAULT 0,   -- 0 for local models
    cost_per_1k_output DECIMAL(10,6) DEFAULT 0,
    avg_latency_ms  INTEGER,
    capability_tags TEXT[] DEFAULT '{}',           -- ['reasoning', 'code', 'fast']
    max_tokens      INTEGER DEFAULT 4096,
    supports_streaming BOOLEAN DEFAULT TRUE,
    supports_functions BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    is_default      BOOLEAN DEFAULT FALSE,
    config          JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider_id, model_name)
);

-- Add deferred FK constraints
ALTER TABLE app_configs ADD FOREIGN KEY (default_model_id) REFERENCES model_registry(id);
ALTER TABLE app_configs ADD FOREIGN KEY (fallback_model_id) REFERENCES model_registry(id);

-- ============================================================
-- TEMPLATES
-- ============================================================
CREATE TABLE templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id          UUID REFERENCES apps(id),      -- NULL = global
    name            VARCHAR(255) NOT NULL,
    template_type   VARCHAR(100),                  -- 'quiz', 'resume', 'report'
    content         TEXT NOT NULL,                 -- Jinja2/Mustache template
    variables       JSONB DEFAULT '[]',
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- DOCUMENTS AND RAG
-- ============================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    session_id      UUID REFERENCES sessions(id),
    filename        VARCHAR(500) NOT NULL,
    original_name   VARCHAR(500),
    file_type       VARCHAR(50),                   -- 'pdf', 'docx', 'txt'
    file_size_bytes INTEGER,
    blob_url        VARCHAR(1000),                 -- Azure Blob Storage URL
    status          VARCHAR(50) DEFAULT 'pending', -- 'pending','processing','indexed','failed'
    chunk_count     INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    token_count     INTEGER,
    metadata        JSONB DEFAULT '{}',            -- page number, section, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- pgvector extension (use Qdrant in enterprise)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id        UUID REFERENCES document_chunks(id) ON DELETE CASCADE,
    model_name      VARCHAR(255) NOT NULL,         -- embedding model used
    embedding       vector(1536),                  -- adjust dimension per model
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- REQUEST AND RESPONSE LOGGING
-- ============================================================
CREATE TABLE request_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id        VARCHAR(64) UNIQUE NOT NULL,   -- distributed trace ID
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    session_id      UUID REFERENCES sessions(id),
    workflow_name   VARCHAR(100),
    endpoint        VARCHAR(255),
    method          VARCHAR(10),
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    request_payload JSONB,
    prompt_id       UUID REFERENCES prompts(id),
    prompt_version  INTEGER,
    model_id        UUID REFERENCES model_registry(id),
    status          VARCHAR(50) DEFAULT 'pending', -- 'success','error','flagged','cached'
    http_status     INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    total_tokens    INTEGER,
    latency_ms      INTEGER,
    cost_usd        DECIMAL(10,8),
    is_cached       BOOLEAN DEFAULT FALSE,
    safety_flagged  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE response_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES request_logs(id) ON DELETE CASCADE,
    response_body   TEXT,                          -- full response content
    parsed_output   JSONB,                         -- structured output if applicable
    quality_score   DECIMAL(3,2),                  -- 0.00-1.00, from evaluation hook
    evaluation_note TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE error_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID REFERENCES request_logs(id),
    error_type      VARCHAR(100),
    error_message   TEXT,
    stack_trace     TEXT,
    is_retried      BOOLEAN DEFAULT FALSE,
    retry_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- AUDIT LOGS
-- ============================================================
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    action          VARCHAR(100) NOT NULL,         -- 'prompt.created', 'model.updated'
    resource_type   VARCHAR(100),
    resource_id     UUID,
    old_value       JSONB,
    new_value       JSONB,
    ip_address      VARCHAR(45),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SAFETY POLICIES
-- ============================================================
CREATE TABLE safety_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id          UUID REFERENCES apps(id),      -- NULL = global policy
    name            VARCHAR(255) NOT NULL,
    rules           JSONB NOT NULL,                -- array of rule objects
    blocked_topics  TEXT[] DEFAULT '{}',
    required_disclaimers JSONB DEFAULT '[]',
    injection_detection_enabled BOOLEAN DEFAULT TRUE,
    output_moderation_enabled   BOOLEAN DEFAULT TRUE,
    severity_threshold VARCHAR(20) DEFAULT 'medium', -- 'low','medium','high'
    action_on_flag  VARCHAR(50) DEFAULT 'block',   -- 'block','warn','log_only'
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE app_configs ADD FOREIGN KEY (safety_policy_id) REFERENCES safety_policies(id);

-- ============================================================
-- USAGE AND BILLING METRICS
-- ============================================================
CREATE TABLE usage_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    model_id        UUID REFERENCES model_registry(id),
    period_date     DATE NOT NULL,
    request_count   INTEGER DEFAULT 0,
    input_tokens    BIGINT DEFAULT 0,
    output_tokens   BIGINT DEFAULT 0,
    total_tokens    BIGINT DEFAULT 0,
    cost_usd        DECIMAL(12,6) DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    avg_latency_ms  INTEGER,
    UNIQUE(user_id, app_id, model_id, period_date)
);

CREATE TABLE billing_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id          UUID REFERENCES apps(id),
    period_month    DATE NOT NULL,                 -- first day of month
    total_requests  BIGINT DEFAULT 0,
    total_tokens    BIGINT DEFAULT 0,
    total_cost_usd  DECIMAL(12,4) DEFAULT 0,
    unique_users    INTEGER DEFAULT 0,
    UNIQUE(app_id, period_month)
);

-- ============================================================
-- USER MEMORY
-- ============================================================
CREATE TABLE user_memory (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    app_id          UUID REFERENCES apps(id),      -- NULL = cross-app memory
    memory_type     VARCHAR(50) NOT NULL,          -- 'fact','preference','summary','context'
    key             VARCHAR(255),                  -- e.g., 'preferred_language', 'name'
    value           TEXT NOT NULL,
    source          VARCHAR(50) DEFAULT 'inferred', -- 'inferred','explicit','summarized'
    confidence      DECIMAL(3,2) DEFAULT 1.0,
    is_active       BOOLEAN DEFAULT TRUE,
    last_accessed   TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- WORKFLOW RUNS
-- ============================================================
CREATE TABLE workflow_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    app_id          UUID REFERENCES apps(id),
    session_id      UUID REFERENCES sessions(id),
    workflow_name   VARCHAR(100) NOT NULL,
    input_payload   JSONB NOT NULL,
    output_payload  JSONB,
    status          VARCHAR(50) DEFAULT 'pending', -- 'pending','running','completed','failed'
    model_id        UUID REFERENCES model_registry(id),
    prompt_id       UUID REFERENCES prompts(id),
    prompt_version  INTEGER,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    latency_ms      INTEGER,
    error_message   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ============================================================
-- INDEXES (critical for performance)
-- ============================================================
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at DESC);
CREATE INDEX idx_request_logs_user_app ON request_logs(user_id, app_id);
CREATE INDEX idx_request_logs_created_at ON request_logs(created_at DESC);
CREATE INDEX idx_request_logs_trace_id ON request_logs(trace_id);
CREATE INDEX idx_workflow_runs_user_app ON workflow_runs(user_id, app_id);
CREATE INDEX idx_user_memory_user_app ON user_memory(user_id, app_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_usage_metrics_period ON usage_metrics(app_id, period_date DESC);
CREATE INDEX idx_sessions_user_app ON sessions(user_id, app_id);
CREATE INDEX idx_document_chunks_document ON document_chunks(document_id);
```

---

## 6. API Design

### Base URL Structure

```
https://api.saib.yourdomain.com/v1/{resource}

Headers required on all requests:
  Authorization: Bearer <jwt_token>
  X-App-Id: <app_id>
  X-Request-Id: <client_trace_id>   (optional but recommended)
  Content-Type: application/json
```

### Authentication Endpoints

```
POST /v1/auth/token
POST /v1/auth/refresh
POST /v1/auth/logout
POST /v1/auth/register
GET  /v1/auth/me
```

**POST /v1/auth/token**
```json
// Request
{
  "email": "user@example.com",
  "password": "securepassword",
  "app_id": "3f2a7b..."
}

// Response 200
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "tier": "pro"
  }
}
```

### App Registry Endpoints

```
POST   /v1/apps                    # Register new app (admin)
GET    /v1/apps                    # List all apps (admin)
GET    /v1/apps/{app_id}           # Get app details
PUT    /v1/apps/{app_id}           # Update app
DELETE /v1/apps/{app_id}           # Deactivate app
GET    /v1/apps/{app_id}/config    # Get app config
PUT    /v1/apps/{app_id}/config    # Update app config
POST   /v1/apps/{app_id}/rotate-key # Rotate API key
```

### Workflow / Generation Endpoints

```
POST /v1/generate               # Run a named workflow (non-streaming)
POST /v1/generate/stream        # Run a named workflow (SSE streaming)
POST /v1/chat                   # Multi-turn chat with session memory
POST /v1/chat/stream            # Streaming chat
```

**POST /v1/generate**
```json
// Request
{
  "workflow": "quiz_generation",
  "inputs": {
    "topic": "Photosynthesis",
    "grade_level": "8th grade",
    "question_count": 10,
    "question_types": ["mcq", "short_answer"]
  },
  "session_id": "optional-session-uuid",
  "model_preference": "ollama/llama3.2",   // optional override
  "options": {
    "use_rag": false,
    "use_memory": true,
    "temperature": 0.7
  }
}

// Response 200
{
  "request_id": "trace-uuid",
  "workflow": "quiz_generation",
  "model_used": "ollama/llama3.2",
  "output": {
    "questions": [
      {
        "id": 1,
        "type": "mcq",
        "question": "What is the primary product of photosynthesis?",
        "options": ["A) Oxygen", "B) Glucose", "C) Carbon Dioxide", "D) Water"],
        "correct_answer": "B",
        "explanation": "Glucose is synthesized during the Calvin cycle..."
      }
    ]
  },
  "tokens_used": { "input": 245, "output": 612 },
  "latency_ms": 1840,
  "cost_usd": 0.0,
  "cached": false
}
```

**POST /v1/chat**
```json
// Request
{
  "session_id": "existing-session-uuid",   // or null to start new
  "message": "I have an interview at Google next week. Help me prepare.",
  "workflow_context": "mock_interview_chat",
  "options": {
    "use_memory": true,
    "inject_long_term_memory": true
  }
}

// Response 200
{
  "session_id": "uuid",
  "message_id": "uuid",
  "response": "Great! Let's start preparing you for your Google interview...",
  "model_used": "ollama/llama3.2",
  "tokens_used": { "input": 180, "output": 320 }
}
```

### Prompt Registry Endpoints

```
GET    /v1/prompts                              # List prompts
POST   /v1/prompts                              # Create prompt
GET    /v1/prompts/{prompt_id}                  # Get prompt with active version
PUT    /v1/prompts/{prompt_id}                  # Update prompt metadata
DELETE /v1/prompts/{prompt_id}                  # Archive prompt

GET    /v1/prompts/{prompt_id}/versions         # List all versions
POST   /v1/prompts/{prompt_id}/versions         # Create new version
GET    /v1/prompts/{prompt_id}/versions/{ver}   # Get specific version
POST   /v1/prompts/{prompt_id}/versions/{ver}/publish   # Publish version
POST   /v1/prompts/{prompt_id}/versions/{ver}/rollback  # Roll back to version
POST   /v1/prompts/{prompt_id}/test             # Test render with inputs
```

**POST /v1/prompts/{id}/test**
```json
// Request
{
  "version": 3,
  "test_inputs": {
    "topic": "Newton's Laws",
    "grade_level": "10th grade",
    "question_count": 5
  },
  "model_id": "uuid-of-model"
}

// Response 200
{
  "rendered_system": "You are an expert educator...",
  "rendered_user": "Generate 5 quiz questions about Newton's Laws for 10th grade students...",
  "token_estimate": 287,
  "model_response": "1. What is Newton's First Law of Motion?..."
}
```

### Model Registry Endpoints

```
GET    /v1/models                  # List all models
POST   /v1/models                  # Register model (admin)
PUT    /v1/models/{model_id}       # Update model config
DELETE /v1/models/{model_id}       # Deactivate model
GET    /v1/models/{model_id}/health # Check model health

GET    /v1/providers               # List model providers
POST   /v1/providers               # Add provider (admin)
PUT    /v1/providers/{id}          # Update provider
DELETE /v1/providers/{id}          # Disable provider
```

### RAG / Document Endpoints

```
POST   /v1/documents/upload        # Upload document for indexing
GET    /v1/documents               # List user's documents
GET    /v1/documents/{doc_id}      # Get document status
DELETE /v1/documents/{doc_id}      # Delete document and chunks
POST   /v1/rag/query               # Query RAG for relevant context
```

**POST /v1/documents/upload** (multipart/form-data)
```
file: <binary>
app_id: uuid
session_id: uuid (optional)
metadata: {"source": "textbook", "subject": "biology"}
```

**POST /v1/rag/query**
```json
// Request
{
  "query": "What are the stages of mitosis?",
  "document_ids": ["uuid1", "uuid2"],   // scope to specific docs
  "top_k": 5,
  "min_score": 0.75
}

// Response 200
{
  "chunks": [
    {
      "content": "Mitosis consists of four stages: prophase, metaphase, anaphase...",
      "document_id": "uuid1",
      "chunk_index": 12,
      "score": 0.91,
      "metadata": { "page": 47 }
    }
  ]
}
```

### Memory Endpoints

```
GET    /v1/memory/session/{session_id}    # Get session conversation history
GET    /v1/memory/user                    # Get user's long-term memories
POST   /v1/memory/user                    # Explicitly store memory
DELETE /v1/memory/user/{memory_id}        # Delete a memory
POST   /v1/memory/session/{session_id}/summarize  # Trigger context compression
```

### Analytics Endpoints

```
GET /v1/analytics/usage               # Usage by day/app/model
GET /v1/analytics/costs               # Cost breakdown
GET /v1/analytics/errors              # Error rates and types
GET /v1/analytics/latency             # Latency percentiles
GET /v1/analytics/prompts             # Prompt performance metrics
```

### Admin Endpoints (admin role required)

```
GET    /v1/admin/dashboard            # High-level platform stats
GET    /v1/admin/users                # User management
GET    /v1/admin/audit-logs           # Full audit trail
PUT    /v1/admin/safety-policies/{id} # Update safety policy
GET    /v1/admin/jobs                 # Background job status
POST   /v1/admin/jobs/{job}/trigger   # Manually trigger a job
GET    /v1/admin/models/health        # All model health statuses
```

---

## 7. Prompt Management Design

### Prompt Template Structure

Each prompt is composed of two Jinja2 templates:

```
system_template:
  "You are an expert {{ domain }} educator.
   Always respond in {{ response_language }}.
   Difficulty level: {{ difficulty }}.
   {{ custom_instructions }}"

user_template:
  "Generate {{ question_count }} {{ question_type }} questions
   about: {{ topic }}
   Grade level: {{ grade_level }}
   Format: Return valid JSON matching this schema: {{ output_schema }}"
```

### Variable Definitions

```json
{
  "variables": [
    { "name": "topic", "type": "string", "required": true, "description": "Subject topic" },
    { "name": "question_count", "type": "integer", "required": true, "default": 10 },
    { "name": "question_type", "type": "enum", "values": ["mcq", "short_answer", "essay"] },
    { "name": "grade_level", "type": "string", "required": false, "default": "general" },
    { "name": "response_language", "type": "string", "required": false, "default": "English" }
  ]
}
```

### Versioning and Lifecycle

```
DRAFT → PUBLISHED → DEPRECATED
  │         │
  └── (can roll back to any prior version)
```

**Rules:**
- Only one version is `active` at a time per prompt slug
- Publishing a new version automatically demotes the previous to `deprecated`
- Rollback sets an older version as active (new version record is created)
- Each version change creates an `audit_log` entry
- Production apps always pin to `active_version` (safe) or can pin to a specific version number (advanced)

### Per-App Prompt Overrides

```
Global prompt: "quiz_generation" → version 3 (default for all apps)
  └── EduAI override → version 5 (EduAI-specific tuning)
  └── HealthApp override → blocked (not allowed for health app)
```

Stored in `prompts` table with `app_id` set. The resolver checks:
1. App-specific prompt with matching slug → use it
2. Global prompt with matching slug → use it
3. No match → 404

### Environment-Specific Prompts

Use prompt naming convention + app config:

```
slug: "quiz_generation"
  dev:  app_config.prompt_env = "dev"   → resolves to quiz_generation (draft allowed)
  prod: app_config.prompt_env = "prod"  → only published versions
```

### Prompt Rendering Pipeline

```
Input Variables → Variable Validation → Template Fetch from DB/Cache
    → Jinja2 Render → Token Count Check → Final Prompt
```

Token budget enforcement: if rendered prompt exceeds `max_tokens_per_request - reserved_output_tokens`, truncation or error is raised.

---

## 8. Model Routing Design

### Routing Decision Tree

```
Incoming Request
       │
       ▼
[1] Per-request model_preference specified?
       │ Yes → Use specified model (validate it exists and is active)
       │ No
       ▼
[2] App config has default_model_id?
       │ Yes → Use app default model
       │ No
       ▼
[3] Workflow has preferred model tag?
       │ Yes → Find best active model matching tag
       │ No
       ▼
[4] Route by task type and user tier
       │ tier=free   → route to local Ollama model
       │ tier=pro    → route to best available (local preferred, OpenAI fallback)
       │ tier=enterprise → route to highest-quality model for task
       ▼
[5] Selected model healthy?
       │ Yes → Use it
       │ No  → Use fallback_model_id from app_config
              │ No fallback → Use global default → Error
```

### Routing Rules Configuration

```python
ROUTING_RULES = [
    # Task-type routing
    { "task": "code_generation",      "preferred_tags": ["code"], "fallback_tags": ["reasoning"] },
    { "task": "quiz_generation",      "preferred_tags": ["fast", "instruction"], "fallback_tags": ["general"] },
    { "task": "resume_analysis",      "preferred_tags": ["reasoning", "long_context"] },
    { "task": "health_chatbot",       "preferred_tags": ["safe", "instruction"], "max_cost_per_1k": 0.01 },
    { "task": "mock_interview_chat",  "preferred_tags": ["fast", "chat"] },
    { "task": "astrology_insights",   "preferred_tags": ["creative", "general"] },

    # User tier routing
    { "tier": "free",        "preferred_providers": ["ollama"] },
    { "tier": "pro",         "preferred_providers": ["ollama", "openai"] },
    { "tier": "enterprise",  "preferred_providers": ["openai", "ollama"] },
]
```

### Fallback Chain

```
Primary Model → [if fails] → Fallback Model → [if fails] → Global Default → [if fails] → Error 503
```

Each failure is logged with reason: `model_timeout`, `model_error`, `rate_limited`, `context_exceeded`.

### Health Monitoring

Background job `health_check_job.py` pings each model every 60 seconds:
- Ollama: `GET /api/tags` + `POST /api/generate` with minimal prompt
- OpenAI: `GET /v1/models`

Marks `model_registry.is_healthy = false` on failure. Router skips unhealthy models.

---

## 9. Memory and Context Design

### Memory Hierarchy

```
┌─────────────────────────────────────────────────────┐
│  L1: Request-level context (in-flight, not stored)  │
│  → Retrieved docs from RAG + current session msgs   │
├─────────────────────────────────────────────────────┤
│  L2: Short-term session memory (Redis TTL: 2 hours) │
│  → Last N messages from current session             │
├─────────────────────────────────────────────────────┤
│  L3: App-specific memory (PostgreSQL, per app_id)   │
│  → User preferences, app-specific facts             │
├─────────────────────────────────────────────────────┤
│  L4: Long-term user memory (PostgreSQL, cross-app)  │
│  → Name, learning style, goals, important facts     │
└─────────────────────────────────────────────────────┘
```

### Context Assembly for Each Request

```python
def build_context(user_id, session_id, app_id, query, use_rag=False):
    context_parts = []

    # 1. Long-term memories (always injected if available)
    long_term = memory_service.get_user_memories(user_id, app_id, limit=10)
    if long_term:
        context_parts.append(format_memories(long_term))

    # 2. Session history (recent N messages)
    session_msgs = memory_service.get_session_history(session_id, limit=20)
    if len(session_msgs) > TOKEN_BUDGET_HISTORY:
        session_msgs = get_or_create_summary(session_id)  # compressed summary
    context_parts.append(session_msgs)

    # 3. RAG context (if enabled and documents exist)
    if use_rag:
        rag_chunks = rag_service.retrieve(query, user_id=user_id, app_id=app_id)
        context_parts.append(format_rag_context(rag_chunks))

    return assemble_context(context_parts, token_budget=MAX_CONTEXT_TOKENS)
```

### Session Summarization (Memory Compression)

When session exceeds 20 messages or 4000 tokens:
1. Take all messages in session
2. Call LLM with summarization prompt: "Summarize this conversation preserving key facts"
3. Store summary in `sessions.context_summary`
4. Clear old messages from Redis short-term cache
5. Future context assembly uses summary + last 5 messages

### Long-Term Memory Extraction

After each assistant response, a background task analyzes the conversation for memorable facts:
- Named entities (user's name, company, grade level)
- Stated preferences ("I prefer visual explanations")
- Goals ("preparing for AWS certification")
- Important context ("my student is dyslexic")

Stored as `user_memory` records with `source='inferred'`.

### Memory Retrieval Safety

- Memories are always scoped to `user_id` — never cross-user
- `app_id=NULL` memories are cross-app (user preferences)
- `app_id=specific` memories are isolated to that app
- Memory retrieval checks `is_active` and `expires_at`
- Sensitive memory entries are flagged and excluded from prompts by default

---

## 10. Safety and Guardrails

### Safety Pipeline

```
User Input
    │
    ▼
[INPUT SAFETY LAYER]
├── Prompt Injection Detection
├── Jailbreak Pattern Matching
├── Topic Blocking (per app policy)
├── PII Detection (optional)
└── Input Length Enforcement
    │
    ▼ (if all pass)
[PROMPT RENDERING + MODEL CALL]
    │
    ▼
[OUTPUT SAFETY LAYER]
├── Content Moderation
├── Harmful Output Detection
├── Disclaimer Injection (health, legal, astrology)
├── PII Scrubbing (optional)
└── Output Format Validation
    │
    ▼
Response to Client
```

### Per-App Safety Policies

```json
// Health Assistant App Policy
{
  "app_id": "health-app-uuid",
  "name": "health_safety_policy",
  "blocked_topics": ["suicide_methods", "drug_synthesis", "self_harm_instructions"],
  "required_disclaimers": [
    {
      "trigger": "medical_advice",
      "text": "This is for informational purposes only. Please consult a qualified healthcare professional for medical advice."
    }
  ],
  "injection_detection_enabled": true,
  "output_moderation_enabled": true,
  "severity_threshold": "low",
  "action_on_flag": "block",
  "rules": [
    { "type": "topic_block", "topics": ["specific_drug_dosages"], "action": "block" },
    { "type": "always_add_disclaimer", "disclaimer_key": "medical_advice" }
  ]
}

// Astrology App Policy
{
  "app_id": "astrology-app-uuid",
  "name": "astrology_safety_policy",
  "required_disclaimers": [
    {
      "trigger": "always",
      "text": "Astrology readings are for entertainment purposes only."
    }
  ],
  "blocked_topics": ["dangerous_predictions", "financial_decisions"],
  "severity_threshold": "medium",
  "action_on_flag": "warn"
}
```

### Injection Detection Rules

```python
INJECTION_PATTERNS = [
    r"ignore (all |previous |above |prior )?instructions",
    r"you are now (a |an )?(different|new|evil|unrestricted)",
    r"DAN mode|jailbreak|act as if|pretend (you are|to be)",
    r"forget (everything|all|your|the) (above|previous|prior|training)",
    r"system prompt|<\|system\|>|###instruction",
    r"bypass (safety|filter|restriction|moderation)",
]

def detect_injection(text: str) -> tuple[bool, str]:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, f"Potential prompt injection detected: {pattern}"
    return False, ""
```

---

## 11. Logging and Observability

### Log Structure

Every request produces a structured log entry:

```json
{
  "timestamp": "2026-03-13T10:30:45.123Z",
  "level": "INFO",
  "trace_id": "abc123def456",
  "span_id": "span789",
  "service": "saib-api",
  "event": "request.completed",
  "user_id": "uuid",
  "app_id": "uuid",
  "app_name": "eduai",
  "workflow": "quiz_generation",
  "model": "ollama/llama3.2",
  "http_status": 200,
  "latency_ms": 1840,
  "input_tokens": 245,
  "output_tokens": 612,
  "cost_usd": 0.0,
  "cached": false,
  "safety_flagged": false
}
```

### Metrics to Track

| Metric | Type | Alert Threshold |
|--------|------|----------------|
| `request_latency_p95` | Histogram | > 5000ms |
| `request_error_rate` | Counter | > 5% |
| `model_timeout_count` | Counter | > 10/min |
| `safety_flag_rate` | Counter | > 1% |
| `token_usage_daily` | Gauge | > 80% of budget |
| `active_sessions` | Gauge | Monitor trend |
| `rag_retrieval_score_avg` | Histogram | < 0.6 average |
| `cache_hit_rate` | Gauge | < 20% (investigate) |

### Tracing Strategy

Use OpenTelemetry with Azure Monitor as backend:
- Each incoming request generates a `trace_id`
- Each sub-operation (safety check, prompt render, model call, RAG query) creates a `span`
- Spans include: duration, model name, token counts, error type
- Traces are stored in Azure Application Insights for 90 days

### Dashboard Panels (Grafana / Azure Monitor Workbook)

```
Row 1: Business Metrics
├── Total requests today (by app)
├── Active users (24h)
├── Tokens consumed (by model)
└── Estimated cost (by app)

Row 2: Performance
├── Request latency P50/P95/P99 (time series)
├── Error rate (time series)
├── Model response times by model
└── Cache hit rate

Row 3: Safety & Quality
├── Safety flags triggered (by app)
├── Blocked requests count
├── Average quality score (if eval hooks enabled)
└── RAG retrieval score distribution

Row 4: Infrastructure
├── API instance CPU/memory
├── PostgreSQL connections + slow queries
├── Redis memory usage + evictions
└── Model server (Ollama) resource usage
```

---

## 12. Deployment Architecture (Azure)

### MVP Deployment (App Service)

```
Internet
    │
    ▼
Azure Front Door / Application Gateway (WAF + SSL)
    │
    ▼
Azure App Service (B2/B3) — Docker container running FastAPI
    │
    ├── Azure Database for PostgreSQL Flexible Server (Standard_D2s_v3)
    ├── Azure Cache for Redis (Basic C1)
    ├── Azure Blob Storage (document uploads)
    └── Azure Key Vault (API keys, DB password, JWT secret)

Separate VM (Standard_NC4as_T4_v3) — Ollama GPU server
    └── Private VNet peering with App Service

Azure Container Registry — Docker images

GitHub Actions CI/CD:
    ├── PR → run tests → lint
    └── merge to main → build image → push to ACR → deploy to App Service
```

### Production Deployment (AKS)

```
Internet
    │
    ▼
Azure Application Gateway + WAF v2
    │
    ▼
Azure API Management (APIM) — rate limiting, analytics, versioning
    │
    ▼
AKS Cluster (System Pool: D4s_v3, User Pool: D8s_v3)
├── Namespace: saib-prod
│   ├── Deployment: saib-api (3 replicas, HPA: 3-20)
│   ├── Deployment: saib-worker (2 replicas — Celery workers)
│   ├── Deployment: qdrant (StatefulSet, 1 replica + PVC)
│   └── Ingress: nginx-ingress-controller
│
├── Namespace: saib-admin
│   └── Deployment: admin-dashboard (1 replica)
│
└── Namespace: monitoring
    ├── Prometheus + Grafana
    └── Jaeger (tracing)

Azure Database for PostgreSQL Flexible — Business Critical tier
Azure Cache for Redis — Premium P1 (cluster mode)
Azure Blob Storage — ZRS redundancy
Azure Key Vault — RBAC-based access for AKS Managed Identity
Azure GPU VM (NC-series) — Ollama, VNet-peered with AKS
Azure Container Registry — Geo-replicated
```

### Environment Separation

```
Branch Strategy:
  feature/* → dev
  develop   → qa
  main      → prod

Each environment:
  dev:  App Service (cheapest tier) + PostgreSQL + Redis
  qa:   App Service (same tier as prod, smaller) + PostgreSQL + Redis
  prod: AKS + PostgreSQL Business Critical + Redis Premium

Secrets per environment in Key Vault:
  kv-saib-dev
  kv-saib-qa
  kv-saib-prod
```

### Secrets Management

```python
# Never hardcode secrets. Use Key Vault references:
# In Azure App Service:
#   App Setting: DATABASE_URL = @Microsoft.KeyVault(VaultName=kv-saib-prod;SecretName=database-url)

# In code (config/settings.py):
class Settings(BaseSettings):
    DATABASE_URL: str          # injected from Key Vault via env var
    REDIS_URL: str
    JWT_SECRET: str
    OPENAI_API_KEY: str = ""   # optional, only set in prod
    OLLAMA_BASE_URL: str = "http://ollama-vm:11434"

    class Config:
        env_file = ".env"
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml (abbreviated)
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-dev.txt
      - run: pytest tests/ --cov=app --cov-report=xml
      - run: ruff check app/ tests/

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: azure/docker-login@v1
        with:
          login-server: ${{ secrets.ACR_LOGIN_SERVER }}
      - run: |
          docker build -f infra/docker/Dockerfile -t $ACR/saib-api:$GITHUB_SHA .
          docker push $ACR/saib-api:$GITHUB_SHA
      - uses: azure/webapps-deploy@v3      # MVP: App Service
        with:
          images: $ACR/saib-api:$GITHUB_SHA
```

---

## 13. Development Roadmap

### Phase 1: MVP Core (Weeks 1–6)

**Goal:** Single working AI backend that EduAI can call for quiz and assignment generation.

**Modules to build:**
- [ ] Project scaffold: FastAPI, PostgreSQL, Redis, Alembic
- [ ] Auth module: JWT tokens, user registration, app API keys
- [ ] App registry: CRUD for apps and app_configs
- [ ] Prompt registry: CRUD for prompts + single version per prompt
- [ ] Ollama adapter: basic chat and generation calls
- [ ] Model registry: register Ollama models, basic health check
- [ ] Orchestration engine: simple workflow executor (quiz_generation, assignment_generation)
- [ ] Request/response logging middleware
- [ ] Dockerize + deploy to Azure App Service
- [ ] Basic CI/CD with GitHub Actions

**Outcome:** EduAI sends requests to `/v1/generate` with `workflow=quiz_generation` and receives structured quiz output. All requests logged.

---

### Phase 2: Multi-App Integration (Weeks 7–10)

**Goal:** Onboard all current apps with app-specific configs and safety.

**Modules to build:**
- [ ] Prompt versioning: create versions, publish, rollback
- [ ] Per-app prompt overrides
- [ ] Safety module: injection detection, topic blocking, disclaimer injection
- [ ] Per-app safety policies
- [ ] Session management and basic short-term memory (Redis)
- [ ] Interview Prep workflows: interview_questions, mock_interview_chat
- [ ] Resume Builder workflow: resume_analysis
- [ ] Health chatbot workflow: health_chatbot with strict safety policy
- [ ] Astrology workflow: astrology_insights
- [ ] Rate limiting per app (Redis-based)

**Outcome:** All 5 current apps powered by the shared backend. Safety policies applied per app. Prompt changes managed centrally.

---

### Phase 3: RAG and Memory (Weeks 11–15)

**Goal:** Document-aware AI and persistent user memory.

**Modules to build:**
- [ ] Document upload API (Azure Blob + PostgreSQL metadata)
- [ ] Text chunker and embedding pipeline
- [ ] pgvector integration for similarity search
- [ ] RAG retrieval service with reranking
- [ ] Async embedding job (Celery)
- [ ] Long-term user memory extraction (background job)
- [ ] Memory injection into context builder
- [ ] Session summarization for long conversations
- [ ] User memory CRUD API

**Outcome:** Users can upload documents (resumes, textbooks, health reports) and the system uses them in AI responses. User facts persist across sessions.

---

### Phase 4: Analytics and Admin Dashboard (Weeks 16–20)

**Goal:** Full observability and admin control plane.

**Modules to build:**
- [ ] Usage metrics aggregation (daily Celery job)
- [ ] Cost tracking per model, per app, per user
- [ ] Analytics REST API (usage, costs, errors, latency)
- [ ] Admin dashboard (React frontend)
  - Prompt management UI
  - Model registry UI
  - Safety policy editor
  - Usage analytics charts
  - Audit log viewer
- [ ] OpenAI adapter (as fallback provider)
- [ ] Model router with full decision tree and fallback chain
- [ ] Quality evaluation hooks (basic scoring)

**Outcome:** Full visibility into platform usage. Admin can manage prompts and models without code changes. OpenAI available as fallback.

---

### Phase 5: Scale and Hardening (Weeks 21–28)

**Goal:** Production-grade reliability, performance, and enterprise readiness.

**Modules to build:**
- [ ] Migrate to AKS with Helm charts
- [ ] Migrate pgvector to Qdrant
- [ ] Redis caching for prompt renders and model responses
- [ ] Horizontal Pod Autoscaler configuration
- [ ] Azure APIM integration for advanced rate limiting and analytics
- [ ] Full OpenTelemetry distributed tracing
- [ ] Grafana dashboards + alert rules
- [ ] Multi-environment deployment (dev/qa/prod)
- [ ] Secret rotation automation (Key Vault)
- [ ] Load testing and performance tuning
- [ ] SLA monitoring and runbooks

**Outcome:** Platform ready for 10,000+ requests/day, HA deployment, full observability, enterprise security posture.

---

## 14. Code Examples

See [CODE_EXAMPLES.md](./CODE_EXAMPLES.md) for complete starter code.

---

## 15. System Diagrams

See [DIAGRAMS.md](./DIAGRAMS.md) for all Mermaid diagrams.

---

## 16. Final Recommendation

### The Right Architecture for Your Situation

Given your goals (start fast, Ollama-first, scale to SaaS), here is the precise recommendation:

**Stack:** FastAPI + PostgreSQL (+ pgvector) + Redis + Celery + Azure App Service → AKS later

**Why this specific choice:**
1. FastAPI gives you production-grade Python async performance with Pydantic validation that catches bad AI inputs before they hit models
2. pgvector means you run RAG from day one with zero additional infrastructure — Qdrant migration is a 1-day job later
3. Redis handles both your session cache AND Celery job queue — one less managed service to pay for in MVP
4. Azure App Service is 10 minutes to deploy, scales to 10 containers manually, and your Dockerfile runs unchanged in AKS later
5. The modular folder structure means you can hire one developer per module without conflicts

**What to build first (in this exact order):**
1. Auth + App Registry (foundation for everything)
2. Ollama Adapter + Model Registry (the actual AI capability)
3. Prompt Registry with basic versioning (central control)
4. Workflow Executor with quiz_generation (proves the architecture works end-to-end)
5. Request logging middleware (non-negotiable for production)
6. Safety middleware with health app policy (critical before health app goes live)

**What NOT to build in MVP:**
- Full RAG pipeline (add in Phase 3)
- OpenAI integration (add in Phase 4 as fallback)
- Admin dashboard UI (use direct API calls + DB queries initially)
- Long-term memory extraction (add in Phase 3)
- Kubernetes (add in Phase 5)

**The key architectural insight:** The value of this platform is NOT the AI — it's the centralized control. A change to one prompt file instantly affects all apps. A safety rule update covers all domains. A model swap requires zero app code changes. This is the moat you are building.

**Estimated timeline to first production deploy:** 5–6 weeks with one focused developer.
