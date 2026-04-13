# MakerVault API — multi-stage build
# Stage 1: build / install dependencies
# Stage 2: minimal production image

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Builder stage
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /build

# Install pip and build tools
RUN pip install --no-cache-dir --upgrade pip

# Copy dependency declaration first for layer caching
COPY pyproject.toml ./

# Install runtime dependencies into an isolated prefix
RUN pip install --no-cache-dir --prefix=/install .

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="MakerVault API"
LABEL org.opencontainers.image.description="FastAPI backend for MakerVault"

# Non-root user for security
RUN addgroup --system makervault && adduser --system --ingroup makervault makervault

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./alembic.ini

# Ensure our package is importable
ENV PYTHONPATH=/app/src

# Run as non-root
USER makervault

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "makervault.main:app", "--host", "0.0.0.0", "--port", "8000"]
