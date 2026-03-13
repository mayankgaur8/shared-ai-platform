# Code Examples — Shared AI Interface Backend

> Complete starter code for all core modules. Production-ready patterns, not toy examples.

---

## Table of Contents

1. [Project Bootstrap (main.py + settings)](#1-project-bootstrap)
2. [Model Router](#2-model-router)
3. [Ollama Adapter](#3-ollama-adapter)
4. [OpenAI Adapter](#4-openai-adapter)
5. [Adapter Factory + Base Interface](#5-adapter-factory--base-interface)
6. [Prompt Renderer](#6-prompt-renderer)
7. [Workflow Executor](#7-workflow-executor)
8. [Sample Workflow — Quiz Generation](#8-sample-workflow--quiz-generation)
9. [RAG Retrieval Service](#9-rag-retrieval-service)
10. [Request Logging Middleware](#10-request-logging-middleware)
11. [Safety Middleware](#11-safety-middleware)
12. [User Memory Service](#12-user-memory-service)
13. [Context Builder](#13-context-builder)
14. [Database Models (SQLAlchemy)](#14-database-models-sqlalchemy)
15. [Docker + Docker Compose](#15-docker--docker-compose)
16. [Alembic Migration Example](#16-alembic-migration-example)

---

## 1. Project Bootstrap

### `app/config/settings.py`
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Shared AI Interface Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # dev, qa, production

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host/db
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str  # redis://host:6379/0
    REDIS_TTL_SESSION: int = 7200       # 2 hours
    REDIS_TTL_PROMPT_CACHE: int = 3600  # 1 hour
    REDIS_TTL_MODEL_RESPONSE: int = 300 # 5 minutes

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: int = 120

    # OpenAI (optional)
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 60

    # Safety
    INJECTION_DETECTION_ENABLED: bool = True
    OUTPUT_MODERATION_ENABLED: bool = True

    # Azure Storage
    AZURE_STORAGE_ACCOUNT: str = ""
    AZURE_STORAGE_KEY: str = ""
    AZURE_BLOB_CONTAINER: str = "documents"

    # Celery
    CELERY_BROKER_URL: str = ""   # defaults to REDIS_URL if empty
    CELERY_RESULT_BACKEND: str = ""

    # Embedding
    EMBEDDING_MODEL: str = "nomic-embed-text"  # Ollama embedding model
    EMBEDDING_DIMENSION: int = 768
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # Limits
    MAX_CONTEXT_TOKENS: int = 8192
    MAX_SESSION_MESSAGES: int = 20
    MAX_RAG_CHUNKS: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### `app/main.py`
```python
import time
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.config.database import init_db
from app.config.redis import init_redis
from app.logging_service.middleware import RequestLoggingMiddleware
from app.safety.middleware import SafetyMiddleware

from app.auth.router import router as auth_router
from app.apps.router import router as apps_router
from app.users.router import router as users_router
from app.prompts.router import router as prompts_router
from app.models_registry.router import router as models_router
from app.orchestration.router import router as orchestration_router
from app.rag.router import router as rag_router
from app.memory.router import router as memory_router
from app.templates.router import router as templates_router
from app.analytics.router import router as analytics_router
from app.admin.router import router as admin_router

log = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", service=settings.APP_NAME, env=settings.ENVIRONMENT)
    await init_db()
    await init_redis()
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Middleware (order matters — outermost runs first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SafetyMiddleware)

# Routers
app.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
app.include_router(apps_router, prefix="/v1/apps", tags=["apps"])
app.include_router(users_router, prefix="/v1/users", tags=["users"])
app.include_router(prompts_router, prefix="/v1/prompts", tags=["prompts"])
app.include_router(models_router, prefix="/v1/models", tags=["models"])
app.include_router(orchestration_router, prefix="/v1", tags=["orchestration"])
app.include_router(rag_router, prefix="/v1", tags=["rag"])
app.include_router(memory_router, prefix="/v1/memory", tags=["memory"])
app.include_router(templates_router, prefix="/v1/templates", tags=["templates"])
app.include_router(analytics_router, prefix="/v1/analytics", tags=["analytics"])
app.include_router(admin_router, prefix="/v1/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

---

## 2. Model Router

### `app/router_engine/model_router.py`
```python
import structlog
from typing import Optional
from uuid import UUID

from app.config.database import get_db
from app.models_registry.models import ModelRegistry, ModelProvider
from app.router_engine.routing_rules import TASK_ROUTING_RULES, TIER_ROUTING_RULES
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

log = structlog.get_logger()


class ModelRouter:
    """
    Selects the best available model for a given task, user tier, and app config.
    Falls back gracefully through the fallback chain.
    """

    async def route(
        self,
        db: AsyncSession,
        task_type: str,
        user_tier: str = "free",
        app_default_model_id: Optional[UUID] = None,
        fallback_model_id: Optional[UUID] = None,
        explicit_model_name: Optional[str] = None,
    ) -> "ModelRegistry":

        log.info("model_routing_start", task=task_type, tier=user_tier)

        # Step 1: Explicit model preference (per-request override)
        if explicit_model_name:
            model = await self._get_model_by_name(db, explicit_model_name)
            if model and model.is_active and model.is_healthy:
                log.info("model_selected", reason="explicit_preference", model=model.model_name)
                return model

        # Step 2: App-level default model
        if app_default_model_id:
            model = await self._get_model_by_id(db, app_default_model_id)
            if model and model.is_active and model.is_healthy:
                log.info("model_selected", reason="app_default", model=model.model_name)
                return model

        # Step 3: Task-type routing by capability tags
        task_rule = TASK_ROUTING_RULES.get(task_type)
        if task_rule:
            for tag in task_rule.get("preferred_tags", []):
                model = await self._get_model_by_tag_and_tier(db, tag, user_tier)
                if model:
                    log.info("model_selected", reason="task_routing", tag=tag, model=model.model_name)
                    return model

        # Step 4: Tier-based routing (free → Ollama only, pro → any)
        model = await self._get_default_by_tier(db, user_tier)
        if model:
            log.info("model_selected", reason="tier_default", tier=user_tier, model=model.model_name)
            return model

        # Step 5: App fallback model
        if fallback_model_id:
            model = await self._get_model_by_id(db, fallback_model_id)
            if model and model.is_active and model.is_healthy:
                log.info("model_selected", reason="app_fallback", model=model.model_name)
                return model

        # Step 6: Global platform default
        model = await self._get_global_default(db)
        if model:
            log.info("model_selected", reason="global_default", model=model.model_name)
            return model

        raise RuntimeError(
            f"No healthy model available for task={task_type}, tier={user_tier}. "
            "All models in fallback chain are unhealthy or inactive."
        )

    async def _get_model_by_id(self, db: AsyncSession, model_id: UUID) -> Optional["ModelRegistry"]:
        result = await db.execute(
            select(ModelRegistry).where(ModelRegistry.id == model_id)
        )
        return result.scalar_one_or_none()

    async def _get_model_by_name(self, db: AsyncSession, model_name: str) -> Optional["ModelRegistry"]:
        provider_name, _, name = model_name.partition("/")
        if not name:
            name = provider_name
        result = await db.execute(
            select(ModelRegistry)
            .join(ModelProvider)
            .where(
                and_(
                    ModelRegistry.model_name == name,
                    ModelRegistry.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_model_by_tag_and_tier(
        self, db: AsyncSession, tag: str, user_tier: str
    ) -> Optional["ModelRegistry"]:
        tier_providers = TIER_ROUTING_RULES.get(user_tier, {}).get("preferred_providers", [])

        result = await db.execute(
            select(ModelRegistry)
            .join(ModelProvider)
            .where(
                and_(
                    ModelRegistry.is_active == True,
                    ModelRegistry.is_healthy == True,
                    ModelRegistry.capability_tags.contains([tag]),
                    ModelProvider.name.in_(tier_providers) if tier_providers else True,
                )
            )
            .order_by(ModelRegistry.avg_latency_ms.asc().nullslast())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_default_by_tier(self, db: AsyncSession, user_tier: str) -> Optional["ModelRegistry"]:
        tier_providers = TIER_ROUTING_RULES.get(user_tier, {}).get("preferred_providers", ["ollama"])
        result = await db.execute(
            select(ModelRegistry)
            .join(ModelProvider)
            .where(
                and_(
                    ModelRegistry.is_active == True,
                    ModelRegistry.is_healthy == True,
                    ModelProvider.name.in_(tier_providers),
                )
            )
            .order_by(ModelRegistry.is_default.desc(), ModelRegistry.avg_latency_ms.asc().nullslast())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_global_default(self, db: AsyncSession) -> Optional["ModelRegistry"]:
        result = await db.execute(
            select(ModelRegistry)
            .where(
                and_(
                    ModelRegistry.is_active == True,
                    ModelRegistry.is_healthy == True,
                    ModelRegistry.is_default == True,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


### `app/router_engine/routing_rules.py`

TASK_ROUTING_RULES = {
    "quiz_generation":        {"preferred_tags": ["instruction", "fast"],        "fallback_tags": ["general"]},
    "assignment_generation":  {"preferred_tags": ["instruction", "reasoning"],   "fallback_tags": ["general"]},
    "question_paper":         {"preferred_tags": ["reasoning", "instruction"],   "fallback_tags": ["general"]},
    "mcq_generation":         {"preferred_tags": ["fast", "instruction"],        "fallback_tags": ["general"]},
    "mock_interview_chat":    {"preferred_tags": ["chat", "fast"],               "fallback_tags": ["general"]},
    "interview_questions":    {"preferred_tags": ["reasoning", "instruction"],   "fallback_tags": ["general"]},
    "resume_analysis":        {"preferred_tags": ["reasoning", "long_context"],  "fallback_tags": ["reasoning"]},
    "health_chatbot":         {"preferred_tags": ["safe", "instruction"],        "fallback_tags": ["general"]},
    "astrology_insights":     {"preferred_tags": ["creative", "chat"],           "fallback_tags": ["general"]},
}

TIER_ROUTING_RULES = {
    "free":       {"preferred_providers": ["ollama"]},
    "pro":        {"preferred_providers": ["ollama", "openai"]},
    "enterprise": {"preferred_providers": ["openai", "ollama"]},
}
```

---

## 3. Ollama Adapter

### `app/adapters/ollama_adapter.py`
```python
import httpx
import structlog
from typing import AsyncIterator, Optional

from app.adapters.base import BaseAdapter, AdapterRequest, AdapterResponse
from app.config.settings import get_settings

log = structlog.get_logger()
settings = get_settings()


class OllamaAdapter(BaseAdapter):
    """
    Wraps Ollama's REST API behind the unified BaseAdapter interface.
    Supports both streaming and non-streaming generation.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = settings.OLLAMA_TIMEOUT

    async def generate(self, request: AdapterRequest) -> AdapterResponse:
        messages = self._build_messages(request)
        payload = {
            "model": request.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                **(request.extra_params or {}),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()

                content = data["message"]["content"]
                eval_count = data.get("eval_count", 0)
                prompt_eval_count = data.get("prompt_eval_count", 0)

                return AdapterResponse(
                    content=content,
                    model=request.model_name,
                    provider="ollama",
                    input_tokens=prompt_eval_count,
                    output_tokens=eval_count,
                    total_tokens=prompt_eval_count + eval_count,
                    finish_reason=data.get("done_reason", "stop"),
                    raw_response=data,
                )
            except httpx.TimeoutException:
                log.error("ollama_timeout", model=request.model_name, url=self.base_url)
                raise
            except httpx.HTTPStatusError as e:
                log.error("ollama_http_error", status=e.response.status_code, model=request.model_name)
                raise

    async def stream(self, request: AdapterRequest) -> AsyncIterator[str]:
        messages = self._build_messages(request)
        payload = {
            "model": request.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        if not chunk.get("done"):
                            yield chunk["message"]["content"]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]

    def _build_messages(self, request: AdapterRequest) -> list[dict]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.conversation_history:
            messages.extend(request.conversation_history)
        messages.append({"role": "user", "content": request.user_prompt})
        return messages
```

---

## 4. OpenAI Adapter

### `app/adapters/openai_adapter.py`
```python
import structlog
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI

from app.adapters.base import BaseAdapter, AdapterRequest, AdapterResponse
from app.config.settings import get_settings

log = structlog.get_logger()
settings = get_settings()


class OpenAIAdapter(BaseAdapter):
    """
    Wraps the OpenAI API behind the unified BaseAdapter interface.
    Used as a fallback provider or for pro/enterprise tier users.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT,
        )

    async def generate(self, request: AdapterRequest) -> AdapterResponse:
        messages = self._build_messages(request)

        try:
            response = await self.client.chat.completions.create(
                model=request.model_name,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                **(request.extra_params or {}),
            )

            choice = response.choices[0]
            usage = response.usage

            return AdapterResponse(
                content=choice.message.content,
                model=response.model,
                provider="openai",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump(),
            )
        except Exception as e:
            log.error("openai_error", model=request.model_name, error=str(e))
            raise

    async def stream(self, request: AdapterRequest) -> AsyncIterator[str]:
        messages = self._build_messages(request)
        stream = await self.client.chat.completions.create(
            model=request.model_name,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def health_check(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    def _build_messages(self, request: AdapterRequest) -> list[dict]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.conversation_history:
            messages.extend(request.conversation_history)
        messages.append({"role": "user", "content": request.user_prompt})
        return messages
```

---

## 5. Adapter Factory + Base Interface

### `app/adapters/base.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional, Any


@dataclass
class AdapterRequest:
    model_name: str
    user_prompt: str
    system_prompt: Optional[str] = None
    conversation_history: Optional[list[dict]] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    extra_params: Optional[dict] = None


@dataclass
class AdapterResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str = "stop"
    raw_response: Any = field(default=None, repr=False)


class BaseAdapter(ABC):
    @abstractmethod
    async def generate(self, request: AdapterRequest) -> AdapterResponse:
        """Single-shot generation. Returns complete response."""
        ...

    @abstractmethod
    async def stream(self, request: AdapterRequest) -> AsyncIterator[str]:
        """Streaming generation. Yields content chunks."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Returns True if the provider is reachable and healthy."""
        ...
```

### `app/adapters/adapter_factory.py`
```python
from app.adapters.base import BaseAdapter
from app.adapters.ollama_adapter import OllamaAdapter
from app.adapters.openai_adapter import OpenAIAdapter
from app.models_registry.models import ModelRegistry, ModelProvider


class AdapterFactory:
    _registry: dict[str, type[BaseAdapter]] = {
        "ollama": OllamaAdapter,
        "openai": OpenAIAdapter,
    }

    @classmethod
    def get(cls, model: ModelRegistry, provider: ModelProvider) -> BaseAdapter:
        adapter_class = cls._registry.get(provider.name)
        if not adapter_class:
            raise ValueError(f"No adapter registered for provider: {provider.name}")

        if provider.name == "ollama":
            return OllamaAdapter(base_url=provider.base_url)
        elif provider.name == "openai":
            # In production: fetch api_key from Azure Key Vault using provider.api_key_secret
            from app.config.settings import get_settings
            return OpenAIAdapter(api_key=get_settings().OPENAI_API_KEY)
        else:
            return adapter_class()

    @classmethod
    def register(cls, provider_name: str, adapter_class: type[BaseAdapter]):
        """Register a new provider adapter at runtime."""
        cls._registry[provider_name] = adapter_class
```

---

## 6. Prompt Renderer

### `app/prompts/renderer.py`
```python
import structlog
from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError
from typing import Optional

from app.prompts.models import PromptVersion
from app.shared.exceptions import PromptRenderError

log = structlog.get_logger()

# Strict mode: raises error if any variable is undefined
jinja_env = Environment(undefined=StrictUndefined, autoescape=False)


class PromptRenderer:
    """
    Renders Jinja2 prompt templates with variable injection.
    Validates required variables before rendering.
    """

    def render(
        self,
        version: PromptVersion,
        variables: dict,
        extra_context: Optional[dict] = None,
    ) -> tuple[Optional[str], str]:
        """
        Returns (rendered_system_prompt, rendered_user_prompt).
        Raises PromptRenderError on missing required variables or syntax errors.
        """
        context = {**variables, **(extra_context or {})}

        # Validate required variables
        declared_vars = version.variables or []
        self._validate_variables(declared_vars, context)

        try:
            rendered_system = None
            if version.system_template:
                template = jinja_env.from_string(version.system_template)
                rendered_system = template.render(**context)

            user_template = jinja_env.from_string(version.user_template)
            rendered_user = user_template.render(**context)

            log.debug(
                "prompt_rendered",
                prompt_id=str(version.prompt_id),
                version=version.version,
                variable_count=len(context),
            )
            return rendered_system, rendered_user

        except TemplateSyntaxError as e:
            raise PromptRenderError(f"Template syntax error in prompt version {version.version}: {e}")
        except UndefinedError as e:
            raise PromptRenderError(f"Missing variable in prompt template: {e}")

    def _validate_variables(self, declared_vars: list[dict], provided: dict):
        errors = []
        for var in declared_vars:
            name = var.get("name")
            required = var.get("required", False)
            if required and name not in provided:
                if "default" not in var:
                    errors.append(f"Required variable '{name}' not provided")
        if errors:
            raise PromptRenderError(f"Variable validation failed: {'; '.join(errors)}")

    def preview(self, system_template: str, user_template: str, variables: dict) -> tuple[str, str]:
        """Render arbitrary templates for testing — no DB access needed."""
        try:
            sys_tmpl = jinja_env.from_string(system_template)
            usr_tmpl = jinja_env.from_string(user_template)
            return sys_tmpl.render(**variables), usr_tmpl.render(**variables)
        except (TemplateSyntaxError, UndefinedError) as e:
            raise PromptRenderError(str(e))
```

---

## 7. Workflow Executor

### `app/orchestration/executor.py`
```python
import time
import structlog
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.workflows.registry import WORKFLOW_REGISTRY
from app.router_engine.model_router import ModelRouter
from app.adapters.adapter_factory import AdapterFactory
from app.adapters.base import AdapterRequest
from app.prompts.renderer import PromptRenderer
from app.orchestration.context_builder import ContextBuilder
from app.logging_service.service import LoggingService
from app.shared.exceptions import WorkflowNotFoundError

log = structlog.get_logger()
model_router = ModelRouter()
prompt_renderer = PromptRenderer()
context_builder = ContextBuilder()


class WorkflowExecutor:
    """
    The core orchestration engine.
    Receives a workflow name + inputs, runs the full pipeline,
    and returns a structured response.
    """

    async def execute(
        self,
        db: AsyncSession,
        workflow_name: str,
        inputs: dict,
        user_id: UUID,
        app_id: UUID,
        session_id: Optional[UUID],
        app_config: "AppConfig",
        user_tier: str,
        model_preference: Optional[str] = None,
        options: Optional[dict] = None,
    ) -> dict:
        options = options or {}
        start_time = time.monotonic()

        # 1. Load workflow definition
        workflow_class = WORKFLOW_REGISTRY.get(workflow_name)
        if not workflow_class:
            raise WorkflowNotFoundError(f"Workflow '{workflow_name}' not registered")

        workflow = workflow_class()
        log.info("workflow_start", workflow=workflow_name, user_id=str(user_id))

        # 2. Validate inputs against workflow schema
        workflow.validate_inputs(inputs)

        # 3. Select model via router
        model = await model_router.route(
            db=db,
            task_type=workflow_name,
            user_tier=user_tier,
            app_default_model_id=app_config.default_model_id,
            fallback_model_id=app_config.fallback_model_id,
            explicit_model_name=model_preference,
        )

        # 4. Load and render prompt
        prompt_version = await workflow.get_prompt_version(db, app_id)
        rendered_system, rendered_user = prompt_renderer.render(
            version=prompt_version,
            variables=inputs,
        )

        # 5. Build context (memory + RAG)
        context = await context_builder.build(
            db=db,
            user_id=user_id,
            session_id=session_id,
            app_id=app_id,
            query=rendered_user,
            use_memory=options.get("use_memory", app_config.memory_enabled),
            use_rag=options.get("use_rag", app_config.rag_enabled),
        )

        # 6. Get adapter and call model
        adapter = AdapterFactory.get(model=model, provider=model.provider)
        adapter_request = AdapterRequest(
            model_name=model.model_name,
            system_prompt=rendered_system,
            user_prompt=rendered_user + (f"\n\n{context}" if context else ""),
            temperature=prompt_version.model_params.get("temperature", 0.7),
            max_tokens=prompt_version.model_params.get("max_tokens", app_config.max_tokens_per_request),
        )

        response = await adapter.generate(adapter_request)

        # 7. Parse and validate output per workflow spec
        parsed_output = workflow.parse_output(response.content)

        latency_ms = int((time.monotonic() - start_time) * 1000)

        # 8. Log the run (async, non-blocking)
        await LoggingService.log_workflow_run(
            db=db,
            user_id=user_id,
            app_id=app_id,
            session_id=session_id,
            workflow_name=workflow_name,
            model_id=model.id,
            prompt_id=prompt_version.prompt_id,
            prompt_version=prompt_version.version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=latency_ms,
            input_payload=inputs,
            output_payload=parsed_output,
        )

        log.info("workflow_complete", workflow=workflow_name, latency_ms=latency_ms, model=model.model_name)

        return {
            "workflow": workflow_name,
            "model_used": f"{model.provider.name}/{model.model_name}",
            "output": parsed_output,
            "tokens_used": {
                "input": response.input_tokens,
                "output": response.output_tokens,
            },
            "latency_ms": latency_ms,
            "cost_usd": self._calculate_cost(model, response),
        }

    def _calculate_cost(self, model: "ModelRegistry", response: "AdapterResponse") -> float:
        if model.cost_per_1k_input == 0 and model.cost_per_1k_output == 0:
            return 0.0
        input_cost = (response.input_tokens / 1000) * float(model.cost_per_1k_input)
        output_cost = (response.output_tokens / 1000) * float(model.cost_per_1k_output)
        return round(input_cost + output_cost, 8)
```

---

## 8. Sample Workflow — Quiz Generation

### `app/workflows/quiz_generation.py`
```python
import json
import re
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.workflows.base_workflow import BaseWorkflow
from app.shared.exceptions import WorkflowOutputParseError


class QuizGenerationWorkflow(BaseWorkflow):
    """
    Generates a structured quiz with questions, options, answers, and explanations.
    Supported question types: mcq, short_answer, true_false
    """

    workflow_name = "quiz_generation"
    prompt_slug = "quiz_generation"

    required_inputs = ["topic", "question_count"]
    optional_inputs = {
        "grade_level": "general",
        "question_types": ["mcq"],
        "difficulty": "medium",
        "response_language": "English",
    }

    def validate_inputs(self, inputs: dict):
        for field in self.required_inputs:
            if field not in inputs:
                raise ValueError(f"Missing required input: {field}")
        if inputs.get("question_count", 0) > 50:
            raise ValueError("question_count cannot exceed 50")

    def parse_output(self, raw_content: str) -> dict:
        """
        Extracts JSON from model response.
        Models sometimes wrap JSON in markdown code blocks.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\n?(.*?)\n?```", r"\1", raw_content, flags=re.DOTALL).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON object from response
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    raise WorkflowOutputParseError(
                        f"Could not parse quiz output as JSON. Raw: {raw_content[:200]}"
                    )
            else:
                raise WorkflowOutputParseError("No JSON found in quiz generation output")

        # Normalize structure
        questions = data.get("questions", data if isinstance(data, list) else [])
        return {
            "questions": questions,
            "question_count": len(questions),
            "metadata": data.get("metadata", {}),
        }


### `app/workflows/base_workflow.py`
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from app.prompts.models import Prompt, PromptVersion


class BaseWorkflow(ABC):
    workflow_name: str
    prompt_slug: str

    @abstractmethod
    def validate_inputs(self, inputs: dict): ...

    @abstractmethod
    def parse_output(self, raw_content: str) -> dict: ...

    async def get_prompt_version(self, db: AsyncSession, app_id: UUID) -> PromptVersion:
        """
        Finds the active prompt version for this workflow.
        Checks app-specific prompt first, then falls back to global.
        """
        # Try app-specific prompt
        result = await db.execute(
            select(Prompt).where(
                and_(Prompt.slug == self.prompt_slug, Prompt.app_id == app_id)
            )
        )
        prompt = result.scalar_one_or_none()

        # Fallback to global prompt
        if not prompt:
            result = await db.execute(
                select(Prompt).where(
                    and_(Prompt.slug == self.prompt_slug, Prompt.app_id.is_(None))
                )
            )
            prompt = result.scalar_one_or_none()

        if not prompt:
            raise ValueError(f"No prompt found for slug: {self.prompt_slug}")

        result = await db.execute(
            select(PromptVersion).where(
                and_(
                    PromptVersion.prompt_id == prompt.id,
                    PromptVersion.version == prompt.active_version,
                )
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            raise ValueError(f"Active version {prompt.active_version} not found for prompt {self.prompt_slug}")

        return version


### `app/workflows/registry.py`
from app.workflows.quiz_generation import QuizGenerationWorkflow
from app.workflows.assignment_generation import AssignmentGenerationWorkflow
from app.workflows.mock_interview_chat import MockInterviewChatWorkflow
from app.workflows.resume_analysis import ResumeAnalysisWorkflow
from app.workflows.health_chatbot import HealthChatbotWorkflow
from app.workflows.astrology_insights import AstrologyInsightsWorkflow
from app.workflows.interview_questions import InterviewQuestionsWorkflow
from app.workflows.mcq_generation import MCQGenerationWorkflow
from app.workflows.question_paper import QuestionPaperWorkflow

WORKFLOW_REGISTRY = {
    "quiz_generation":        QuizGenerationWorkflow,
    "assignment_generation":  AssignmentGenerationWorkflow,
    "mock_interview_chat":    MockInterviewChatWorkflow,
    "interview_questions":    InterviewQuestionsWorkflow,
    "resume_analysis":        ResumeAnalysisWorkflow,
    "health_chatbot":         HealthChatbotWorkflow,
    "astrology_insights":     AstrologyInsightsWorkflow,
    "mcq_generation":         MCQGenerationWorkflow,
    "question_paper":         QuestionPaperWorkflow,
}
```

---

## 9. RAG Retrieval Service

### `app/rag/retriever.py`
```python
import structlog
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text

from app.rag.embedder import Embedder
from app.rag.models import DocumentChunk, Embedding, Document
from app.config.settings import get_settings

log = structlog.get_logger()
settings = get_settings()


class RAGRetriever:
    """
    Retrieves semantically relevant document chunks for a query.
    Uses pgvector cosine similarity search with optional metadata filtering.
    """

    def __init__(self):
        self.embedder = Embedder()

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        user_id: UUID,
        app_id: UUID,
        document_ids: Optional[list[UUID]] = None,
        top_k: int = 5,
        min_score: float = 0.70,
        session_id: Optional[UUID] = None,
    ) -> list[dict]:
        """
        Embeds the query and finds the top_k most similar chunks
        from the user's indexed documents.
        """
        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)

        # Build filter conditions
        conditions = [Document.user_id == user_id]
        if app_id:
            conditions.append(Document.app_id == app_id)
        if document_ids:
            conditions.append(Document.id.in_(document_ids))
        if session_id:
            conditions.append(Document.session_id == session_id)

        # pgvector cosine similarity search
        # 1 - (embedding <=> query_vector) = cosine similarity
        query_vector = str(query_embedding)
        result = await db.execute(
            text("""
                SELECT
                    dc.id,
                    dc.content,
                    dc.chunk_index,
                    dc.metadata,
                    d.id as document_id,
                    d.filename,
                    1 - (e.embedding <=> :query_vector::vector) as score
                FROM document_chunks dc
                JOIN embeddings e ON e.chunk_id = dc.id
                JOIN documents d ON d.id = dc.document_id
                WHERE d.user_id = :user_id
                  AND d.status = 'indexed'
                ORDER BY e.embedding <=> :query_vector::vector
                LIMIT :top_k
            """),
            {
                "query_vector": query_vector,
                "user_id": str(user_id),
                "top_k": top_k * 2,  # fetch extra for post-filtering
            }
        )

        rows = result.mappings().all()

        # Filter by minimum score and return top_k
        results = [
            {
                "content": row["content"],
                "document_id": str(row["document_id"]),
                "filename": row["filename"],
                "chunk_index": row["chunk_index"],
                "score": float(row["score"]),
                "metadata": row["metadata"],
            }
            for row in rows
            if float(row["score"]) >= min_score
        ][:top_k]

        log.info(
            "rag_retrieval",
            query_length=len(query),
            results_found=len(results),
            top_score=results[0]["score"] if results else 0,
        )

        return results

    def format_context(self, chunks: list[dict]) -> str:
        """Formats retrieved chunks into a context string for prompt injection."""
        if not chunks:
            return ""
        parts = ["Relevant context from uploaded documents:"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"\n[Source {i}: {chunk['filename']}]\n{chunk['content']}")
        return "\n".join(parts)


### `app/rag/embedder.py`
import httpx
from app.config.settings import get_settings

settings = get_settings()


class Embedder:
    """Uses Ollama's embedding endpoint to generate vector embeddings."""

    async def embed_text(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": settings.EMBEDDING_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]


### `app/rag/chunker.py`
from app.config.settings import get_settings

settings = get_settings()


class TextChunker:
    """Splits documents into overlapping chunks suitable for embedding."""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def chunk(self, text: str) -> list[str]:
        """Simple character-based chunking with overlap."""
        if not text.strip():
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(". ")
                if last_period > self.chunk_size * 0.5:
                    chunk = chunk[: last_period + 1]
                    end = start + last_period + 1

            chunks.append(chunk.strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if len(c) > 50]  # filter tiny chunks
```

---

## 10. Request Logging Middleware

### `app/logging_service/middleware.py`
```python
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger()

SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with trace_id, latency, status code.
    Injects trace_id into request state for downstream use.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        trace_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        start = time.monotonic()

        # Bind trace context to all log messages in this request's scope
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )

        log.info("request_start", ip=request.client.host if request.client else "unknown")

        try:
            response = await call_next(request)
            latency_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "request_complete",
                status=response.status_code,
                latency_ms=latency_ms,
            )
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Latency-Ms"] = str(latency_ms)
            return response

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            log.error("request_error", error=str(exc), latency_ms=latency_ms)
            raise
```

---

## 11. Safety Middleware

### `app/safety/middleware.py`
```python
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import json

from app.safety.injection_detector import InjectionDetector
from app.safety.policy_engine import PolicyEngine

log = structlog.get_logger()
injection_detector = InjectionDetector()
policy_engine = PolicyEngine()

CHECKED_PATHS = {"/v1/generate", "/v1/chat"}


class SafetyMiddleware(BaseHTTPMiddleware):
    """
    Pre-checks incoming request bodies for injection/jailbreak patterns.
    Applied only to AI generation endpoints.
    Post-check is done inside WorkflowExecutor after model response.
    """

    async def dispatch(self, request: Request, call_next):
        if not any(request.url.path.startswith(p) for p in CHECKED_PATHS):
            return await call_next(request)

        # Read body (must be done before passing to next handler)
        body_bytes = await request.body()
        try:
            body = json.loads(body_bytes) if body_bytes else {}
        except json.JSONDecodeError:
            body = {}

        # Get app_id from header for policy lookup
        app_id = request.headers.get("X-App-Id")

        # Extract user message text from body
        user_message = (
            body.get("message")
            or (body.get("inputs") or {}).get("topic", "")
            or ""
        )

        if user_message:
            flagged, reason = injection_detector.detect(user_message)
            if flagged:
                log.warning("injection_detected", reason=reason, app_id=app_id,
                            trace_id=getattr(request.state, "trace_id", ""))
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Request blocked by safety filter.",
                        "reason": "potential_injection",
                    }
                )

        # Reconstruct request with body (Starlette requires this)
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive
        return await call_next(request)


### `app/safety/injection_detector.py`
import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|previous\s+|above\s+)?instructions",
    r"you\s+are\s+now\s+(a\s+|an\s+)?(different|new|evil|unrestricted|jailbroken)",
    r"\bDAN\s+mode\b|\bjailbreak\b",
    r"act\s+as\s+if|pretend\s+(you\s+are|to\s+be)",
    r"forget\s+(everything|all|your|the)\s+(above|previous|prior|training|instructions)",
    r"system\s+prompt\s*:|<\|system\|>|###\s*instruction",
    r"bypass\s+(safety|filter|restriction|moderation|guardrail)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|constraints)",
    r"you\s+have\s+no\s+restrictions|you\s+are\s+unfiltered",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]


class InjectionDetector:
    def detect(self, text: str) -> tuple[bool, str]:
        for i, pattern in enumerate(COMPILED_PATTERNS):
            if pattern.search(text):
                return True, f"Pattern {i}: {INJECTION_PATTERNS[i]}"
        return False, ""


### `app/safety/output_sanitizer.py`
from app.safety.policy_engine import SafetyPolicy


class OutputSanitizer:
    """
    Post-processes model output:
    - Adds required disclaimers per app policy
    - Strips harmful content patterns
    - Validates output format if required
    """

    def sanitize(self, content: str, policy: SafetyPolicy) -> str:
        result = content

        # Inject required disclaimers at end of response
        if policy and policy.required_disclaimers:
            for disclaimer_config in policy.required_disclaimers:
                trigger = disclaimer_config.get("trigger", "always")
                text = disclaimer_config.get("text", "")
                if trigger == "always" and text:
                    result = f"{result}\n\n---\n*{text}*"

        return result
```

---

## 12. User Memory Service

### `app/memory/service.py`
```python
import json
import structlog
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.memory.models import UserMemory, Session, Message
from app.config.redis import get_redis
from app.config.settings import get_settings

log = structlog.get_logger()
settings = get_settings()


class MemoryService:
    """
    Manages all tiers of user memory:
    - L2: Short-term session messages (Redis)
    - L3: App-specific long-term memory (PostgreSQL)
    - L4: Cross-app user memory (PostgreSQL)
    """

    # ─── Short-Term (Redis) ─────────────────────────────────────

    async def get_session_history(
        self, session_id: UUID, limit: int = 20
    ) -> list[dict]:
        redis = await get_redis()
        key = f"session:{session_id}:messages"
        raw = await redis.lrange(key, -limit, -1)
        return [json.loads(m) for m in raw]

    async def append_message(
        self, session_id: UUID, role: str, content: str
    ):
        redis = await get_redis()
        key = f"session:{session_id}:messages"
        message = json.dumps({"role": role, "content": content})
        await redis.rpush(key, message)
        await redis.expire(key, settings.REDIS_TTL_SESSION)

        # Cap session history at 100 messages in Redis
        length = await redis.llen(key)
        if length > 100:
            await redis.ltrim(key, -100, -1)

    # ─── Long-Term Memory (PostgreSQL) ──────────────────────────

    async def get_user_memories(
        self,
        db: AsyncSession,
        user_id: UUID,
        app_id: Optional[UUID] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[UserMemory]:
        conditions = [
            UserMemory.user_id == user_id,
            UserMemory.is_active == True,
        ]
        if app_id is not None:
            # Get app-specific AND cross-app memories
            conditions.append(
                (UserMemory.app_id == app_id) | (UserMemory.app_id.is_(None))
            )
        if memory_type:
            conditions.append(UserMemory.memory_type == memory_type)

        result = await db.execute(
            select(UserMemory)
            .where(and_(*conditions))
            .order_by(UserMemory.last_accessed.desc())
            .limit(limit)
        )
        memories = result.scalars().all()

        # Update last_accessed timestamps
        if memories:
            memory_ids = [m.id for m in memories]
            await db.execute(
                update(UserMemory)
                .where(UserMemory.id.in_(memory_ids))
                .values(last_accessed=func.now())
            )
            await db.commit()

        return memories

    async def upsert_memory(
        self,
        db: AsyncSession,
        user_id: UUID,
        key: str,
        value: str,
        memory_type: str = "fact",
        app_id: Optional[UUID] = None,
        source: str = "inferred",
        confidence: float = 1.0,
    ) -> UserMemory:
        # Check if memory with this key already exists
        result = await db.execute(
            select(UserMemory).where(
                and_(
                    UserMemory.user_id == user_id,
                    UserMemory.key == key,
                    UserMemory.app_id == app_id,
                    UserMemory.is_active == True,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.source = source
            await db.commit()
            return existing
        else:
            memory = UserMemory(
                user_id=user_id,
                app_id=app_id,
                memory_type=memory_type,
                key=key,
                value=value,
                source=source,
                confidence=confidence,
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)
            return memory

    def format_for_prompt(self, memories: list[UserMemory]) -> str:
        """Formats memories into a context block for system prompt injection."""
        if not memories:
            return ""
        facts = [f"- {m.key}: {m.value}" for m in memories]
        return "Known facts about this user:\n" + "\n".join(facts)
```

---

## 13. Context Builder

### `app/orchestration/context_builder.py`
```python
import structlog
from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.service import MemoryService
from app.rag.retriever import RAGRetriever
from app.config.settings import get_settings

log = structlog.get_logger()
settings = get_settings()
memory_service = MemoryService()
rag_retriever = RAGRetriever()


class ContextBuilder:
    """
    Assembles the full context for a request by combining:
    1. Long-term user memories
    2. Short-term session history (already in adapter messages format)
    3. RAG-retrieved document chunks
    """

    async def build(
        self,
        db: AsyncSession,
        user_id: UUID,
        session_id: Optional[UUID],
        app_id: UUID,
        query: str,
        use_memory: bool = True,
        use_rag: bool = False,
        document_ids: Optional[list[UUID]] = None,
    ) -> str:
        context_parts = []

        # 1. Long-term user memory
        if use_memory:
            memories = await memory_service.get_user_memories(
                db=db,
                user_id=user_id,
                app_id=app_id,
                limit=8,
            )
            if memories:
                context_parts.append(memory_service.format_for_prompt(memories))

        # 2. RAG context
        if use_rag:
            chunks = await rag_retriever.retrieve(
                db=db,
                query=query,
                user_id=user_id,
                app_id=app_id,
                document_ids=document_ids,
                top_k=settings.MAX_RAG_CHUNKS,
                min_score=0.70,
            )
            if chunks:
                context_parts.append(rag_retriever.format_context(chunks))

        if not context_parts:
            return ""

        return "\n\n".join(context_parts)
```

---

## 14. Database Models (SQLAlchemy)

### `app/auth/models.py`
```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.config.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    auth_provider = Column(String(50), default="local")
    external_id = Column(String(255), nullable=True)
    tier = Column(String(20), default="free")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### `app/prompts/models.py`
```python
import uuid
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.config.database import Base


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    is_global = Column(Boolean, default=False)
    active_version = Column(Integer, default=1)
    is_archived = Column(Boolean, default=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"))
    version = Column(Integer, nullable=False)
    system_template = Column(Text, nullable=True)
    user_template = Column(Text, nullable=False)
    variables = Column(JSONB, default=list)
    model_params = Column(JSONB, default=dict)
    test_inputs = Column(JSONB, default=dict)
    notes = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    prompt = relationship("Prompt", back_populates="versions")
```

---

## 15. Docker + Docker Compose

### `infra/docker/Dockerfile`
```dockerfile
# ── Build Stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/build/deps -r requirements.txt

# ── Production Stage ─────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copy application code
COPY app/ ./app/
COPY alembic.ini .
COPY migrations/ ./migrations/

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--loop", "uvloop", "--no-access-log"]
```

### `infra/docker/docker-compose.yml`
```yaml
version: "3.9"

services:
  api:
    build:
      context: ../../
      dockerfile: infra/docker/Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ../../app:/app/app   # hot reload
    environment:
      DATABASE_URL: postgresql+asyncpg://saib:saib@postgres:5432/saib
      REDIS_URL: redis://redis:6379/0
      JWT_SECRET: dev-secret-change-in-production
      OLLAMA_BASE_URL: http://ollama:11434
      DEBUG: "true"
      ENVIRONMENT: dev
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks: [saib]

  worker:
    build:
      context: ../../
      dockerfile: infra/docker/Dockerfile.dev
    command: celery -A app.jobs.celery_app worker --loglevel=info --concurrency=2
    environment:
      DATABASE_URL: postgresql+asyncpg://saib:saib@postgres:5432/saib
      REDIS_URL: redis://redis:6379/0
      OLLAMA_BASE_URL: http://ollama:11434
    depends_on: [postgres, redis]
    networks: [saib]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: saib
      POSTGRES_USER: saib
      POSTGRES_PASSWORD: saib
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U saib"]
      interval: 10s
      retries: 5
    networks: [saib]

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5
    networks: [saib]

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks: [saib]
    # For GPU: add deploy section with nvidia runtime

volumes:
  pg_data:
  ollama_data:

networks:
  saib:
    driver: bridge
```

---

## 16. Alembic Migration Example

### `migrations/versions/001_initial_schema.py`
```python
"""Initial schema

Revision ID: 001
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "001"
down_revision = None


def upgrade():
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=True),
        sa.Column("auth_provider", sa.String(50), server_default="local"),
        sa.Column("tier", sa.String(20), server_default="free"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_admin", sa.Boolean, server_default="false"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ... (other tables follow the same pattern as DDL in ARCHITECTURE.md)


def downgrade():
    op.drop_table("users")
    # reverse order for FK constraints
```

### `requirements.txt`
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.7.0
pydantic-settings==2.3.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
redis[hiredis]==5.0.4
celery==5.4.0
httpx==0.27.0
openai==1.35.0
jinja2==3.1.4
structlog==24.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
pgvector==0.3.2
```

### `requirements-dev.txt`
```
pytest==8.2.0
pytest-asyncio==0.23.7
pytest-cov==5.0.0
httpx==0.27.0         # test client
ruff==0.5.0           # linting
mypy==1.10.0
faker==25.0.0
```
