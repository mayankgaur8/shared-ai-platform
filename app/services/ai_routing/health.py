"""
Provider health check service with circuit breaker.

Tracks per-provider:
  - last health status
  - recent failure count
  - circuit breaker state (open = provider is tripped, skip it)

Circuit breaker logic:
  - Open after CIRCUIT_OPEN_THRESHOLD consecutive failures
  - Remains open for CIRCUIT_RESET_SECONDS, then goes half-open
  - One successful call in half-open resets to closed
"""
from __future__ import annotations

import time
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.providers.base import ProviderName, HealthStatus

logger = logging.getLogger("saib.ai_routing.health")

# Circuit breaker configuration
CIRCUIT_OPEN_THRESHOLD = 3       # failures before opening
CIRCUIT_RESET_SECONDS  = 60      # seconds before attempting half-open
HEALTH_CACHE_TTL       = 30      # seconds to cache a health result


@dataclass
class ProviderState:
    """In-memory state for one provider's health tracking."""
    provider:       ProviderName
    healthy:        bool = True
    last_latency:   int  = 0
    failures:       int  = 0      # consecutive failure count
    circuit_open:   bool = False
    opened_at:      float = 0.0
    last_checked:   float = 0.0
    last_detail:    str   = ""


class HealthService:
    """
    Singleton-style service that tracks provider health
    and exposes circuit breaker state to the routing engine.
    """

    def __init__(self) -> None:
        self._states: Dict[ProviderName, ProviderState] = {
            p: ProviderState(provider=p) for p in ProviderName
        }
        self._lock = asyncio.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def is_available(self, provider: ProviderName) -> bool:
        """
        Returns True if the provider should be tried.
        A closed or half-open circuit = available.
        """
        state = self._states[provider]
        if not state.circuit_open:
            return True
        # Check if reset window has passed (half-open)
        if time.time() - state.opened_at >= CIRCUIT_RESET_SECONDS:
            return True
        return False

    def record_success(self, provider: ProviderName, latency_ms: int) -> None:
        state = self._states[provider]
        state.healthy       = True
        state.last_latency  = latency_ms
        state.failures      = 0
        state.circuit_open  = False
        state.last_checked  = time.time()
        logger.debug("circuit.success provider=%s latency=%dms", provider.value, latency_ms)

    def record_failure(self, provider: ProviderName, detail: str = "") -> None:
        state = self._states[provider]
        state.healthy      = False
        state.failures    += 1
        state.last_detail  = detail[:200]
        state.last_checked = time.time()

        if state.failures >= CIRCUIT_OPEN_THRESHOLD and not state.circuit_open:
            state.circuit_open = True
            state.opened_at    = time.time()
            logger.warning("circuit.open provider=%s failures=%d", provider.value, state.failures)
        else:
            logger.debug("circuit.failure provider=%s count=%d", provider.value, state.failures)

    async def run_health_checks(self, providers: list) -> Dict[ProviderName, HealthStatus]:
        """
        Run health checks on all provided provider instances in parallel.
        Updates internal state and returns results.
        """
        tasks = {p.name: p.health_check() for p in providers}
        results: Dict[ProviderName, HealthStatus] = {}

        for name, coro in tasks.items():
            try:
                status = await coro
                results[name] = status
                if status.healthy:
                    self.record_success(name, status.latency_ms)
                else:
                    self.record_failure(name, status.detail)
            except Exception as exc:
                logger.error("health_check.error provider=%s error=%s", name, exc)
                results[name] = HealthStatus(
                    provider=name, healthy=False,
                    last_checked_at=time.time(), detail=str(exc),
                )
                self.record_failure(name, str(exc))

        return results

    def get_all_states(self) -> Dict[str, dict]:
        """Return a JSON-serializable snapshot of all provider states."""
        out = {}
        for name, state in self._states.items():
            circuit_status = "closed"
            if state.circuit_open:
                elapsed = time.time() - state.opened_at
                circuit_status = "open" if elapsed < CIRCUIT_RESET_SECONDS else "half-open"

            out[name.value] = {
                "healthy":       state.healthy,
                "last_latency_ms": state.last_latency,
                "recent_failures": state.failures,
                "circuit_breaker": circuit_status,
                "last_checked_at": state.last_checked,
                "detail":        state.last_detail,
            }
        return out


# ── Module-level singleton ─────────────────────────────────────────────────────
_health_service: Optional[HealthService] = None


def get_health_service() -> HealthService:
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service
