# Build stage: compile dependencies
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies only in builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install with aggressive optimization
COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir --user \
    --compile \
    -r requirements.txt && \
    find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true


# Runtime stage - minimal, hardened production image
FROM python:3.12-slim-bookworm

LABEL maintainer="bytesampler" \
      version="1.0" \
      description="Bytesampler adapter service"

# Python production optimization flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random

WORKDIR /app

# Copy pre-compiled dependencies from builder (--chown during COPY is faster than RUN chown)
COPY --from=builder --chown=5678:5678 /root/.local /home/appuser/.local

# Create non-root user once (UID 5678, GID 5678) with minimal shell
RUN groupadd -g 5678 appuser && \
    useradd -u 5678 -g 5678 -s /sbin/nologin -c "App user" appuser && \
    mkdir -p /app && chown -R 5678:5678 /app

# Copy application code with correct ownership
COPY --chown=5678:5678 . /app

# Add local pip packages to PATH (installed with --user in builder)
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/home/appuser/.local/lib/python3.12/site-packages:$PYTHONPATH

# Disable core dumps in container
RUN ulimit -c 0

# Security: Switch to non-root user before exposing port and running container
USER appuser

EXPOSE 8000

# Lightweight healthcheck: just verify imports work
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD python -c "import bytesampler_adapter" || exit 1

CMD ["python", "-u", "bytesampler_adapter.py"]
