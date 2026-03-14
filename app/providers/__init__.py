"""
AI Provider adapters for the Avantika AI Backend.

Each provider exposes the same interface:
    generate(request: ProviderRequest) -> ProviderResponse

Providers:
  - OllamaProvider      — free / local / cheapest
  - CheapApiProvider    — fast + low cost cloud (OpenAI-compatible endpoint)
  - PremiumApiProvider  — best quality cloud (OpenAI or Anthropic)
"""
from .base import BaseProvider, ProviderRequest, ProviderResponse, ProviderName
from .ollama import OllamaProvider
from .cheap_api import CheapApiProvider
from .premium_api import PremiumApiProvider

__all__ = [
    "BaseProvider",
    "ProviderRequest",
    "ProviderResponse",
    "ProviderName",
    "OllamaProvider",
    "CheapApiProvider",
    "PremiumApiProvider",
]
