"""
Abstract base for all AI providers.
Every provider must implement `generate()` and `health_check()`.
"""
from __future__ import annotations

import abc
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ProviderName(str, Enum):
    OLLAMA = "ollama"
    CHEAP_API = "cheap_api"
    PREMIUM_API = "premium_api"


@dataclass
class ProviderRequest:
    """Normalized request passed to any provider."""
    prompt: str
    system_prompt: str = "You are a helpful assistant."
    model: Optional[str] = None          # override provider default
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False
    task_type: str = "general"
    metadata: dict = field(default_factory=dict)


@dataclass
class ProviderResponse:
    """Normalized response from any provider."""
    success: bool
    provider: ProviderName
    model: str
    response_text: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    estimated_cost: float = 0.0
    raw_response: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class HealthStatus:
    """Provider health check result."""
    provider: ProviderName
    healthy: bool
    latency_ms: int = 0
    last_checked_at: float = 0.0
    recent_failures: int = 0
    circuit_open: bool = False   # True = tripped, do not use
    detail: str = ""


class BaseProvider(abc.ABC):
    """
    Common interface every AI provider adapter must implement.
    """

    name: ProviderName

    @abc.abstractmethod
    async def generate(self, request: ProviderRequest) -> ProviderResponse:
        """Send a generation request and return a normalized response."""
        ...

    @abc.abstractmethod
    async def health_check(self) -> HealthStatus:
        """Ping the provider and return its health status."""
        ...

    @property
    @abc.abstractmethod
    def default_model(self) -> str:
        """Return the default model identifier for this provider."""
        ...
