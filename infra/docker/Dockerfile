# ==============================================================================
# Production Dockerfile for Financial RAG Agent (Multi-stage, Non-root, Lean)
# ==============================================================================

# --- Stage 1: Build & Dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast dependency resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache-dir .

# --- Stage 2: Runtime Minimal Image ---
FROM python:3.12-slim AS runner

WORKDIR /app

# Security: Create non-root unprivileged service account
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DATA_SOURCE_MODE=live_api

# Copy application source and data
COPY config/ /app/config/
COPY src/ /app/src/
COPY data/ /app/data/
COPY README.md /app/README.md

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-config", "config/logging.json"]
