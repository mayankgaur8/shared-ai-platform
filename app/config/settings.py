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
    OLLAMA_DEFAULT_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: int = 120

    # OpenAI (optional — used as fallback)
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: int = 60

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
