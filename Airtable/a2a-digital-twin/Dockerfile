FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8080 \
    A2A_REPO_ROOT=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 app \
    && useradd -u 10001 -g app -s /usr/sbin/nologin app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt

COPY . /app

RUN chown -R app:app /app
USER app

EXPOSE 8080

# FastMCP HTTP server does not expose a fixed health endpoint.
# Probe socket availability on the configured MCP_PORT instead.
HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=25s \
  CMD python -c "import os,socket; s=socket.socket(); s.settimeout(4); s.connect(('127.0.0.1', int(os.getenv('MCP_PORT','8080')))); s.close()"

CMD ["python", "bootstrap_digital_twin.py"]
