# ── Build Stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/build/deps -r requirements.txt

# ── Production Stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /build/deps /usr/local/lib/python3.12/site-packages/

# Copy application source
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 4 workers is a safe default for 2-core containers; tune via WORKERS env var
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-4} --loop uvloop --no-access-log"]
