from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Shared AI Interface Backend"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://saib:saib@localhost:5432/saib"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_TTL_SESSION: int = 7200
    REDIS_TTL_PROMPT_CACHE: int = 3600
    REDIS_TTL_MODEL_RESPONSE: int = 300

    # Auth
    JWT_SECRET: str = "change-this-in-production-minimum-32-characters"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3.2"   # legacy key kept for backwards compat
    OLLAMA_TIMEOUT: int = 120

    # OpenAI (optional — used as fallback)
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 60

    # ── Hybrid AI Router ───────────────────────────────────────────────────────

    # Default provider when no routing rule matches
    AI_PROVIDER_DEFAULT: str = "ollama"   # ollama | cheap_api | premium_api

    # Ollama provider
    OLLAMA_MODEL_DEFAULT: str = "llama3.2"
    AI_TIMEOUT_OLLAMA_MS: int = 120_000    # 2 minutes (ms)

    # Cheap cloud API provider (OpenAI-compatible endpoint, e.g. Groq, Together AI)
    CHEAP_API_BASE_URL: str = "https://api.groq.com/openai/v1"
    CHEAP_API_KEY: str = ""
    CHEAP_API_MODEL_DEFAULT: str = "llama3-8b-8192"
    AI_TIMEOUT_CHEAP_MS: int = 30_000      # 30 seconds (ms)
    CHEAP_API_COST_PER_1K_INPUT: float  = 0.0001   # USD per 1K input tokens
    CHEAP_API_COST_PER_1K_OUTPUT: float = 0.0001   # USD per 1K output tokens

    # Premium cloud API provider (OpenAI GPT-4 or compatible)
    PREMIUM_API_BASE_URL: str = "https://api.openai.com/v1"
    PREMIUM_API_KEY: str = ""
    PREMIUM_API_MODEL_DEFAULT: str = "gpt-4o-mini"
    AI_TIMEOUT_PREMIUM_MS: int = 60_000    # 60 seconds (ms)
    PREMIUM_API_COST_PER_1K_INPUT: float  = 0.005   # USD per 1K input tokens
    PREMIUM_API_COST_PER_1K_OUTPUT: float = 0.015   # USD per 1K output tokens

    # Budget control
    AI_BUDGET_MONTHLY_LIMIT: float = 0.0   # 0 = no limit; set e.g. 50.0 for $50/month cap

    # Response caching
    AI_CACHE_ENABLED: bool = True
    REDIS_TTL_AI_RESPONSE: int = 300        # seconds to cache AI responses

    # Security — internal app API key auth
    AI_REQUIRE_APP_KEY: bool = False        # set True in production
    AI_INTERNAL_APP_KEYS: str = ""          # comma-separated keys for calling apps

    # Azure Storage
    AZURE_STORAGE_ACCOUNT: str = ""
    AZURE_STORAGE_KEY: str = ""
    AZURE_BLOB_CONTAINER: str = "documents"

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # Embedding
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: int = 768
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # Safety
    INJECTION_DETECTION_ENABLED: bool = True
    OUTPUT_MODERATION_ENABLED: bool = True

    # Context limits
    MAX_CONTEXT_TOKENS: int = 8192
    MAX_SESSION_MESSAGES: int = 20
    MAX_RAG_CHUNKS: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
