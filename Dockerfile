# Reproducible build: use the committed uv.lock and keep build tooling out
# of the runtime image. FastMCP is pinned to the compatible 1.x SDK line.
FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.4

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY docs/ ./docs/
COPY rules/ ./rules/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH \
    ODOO_MCP_TRANSPORT=streamable-http

WORKDIR /app

RUN groupadd --gid 10001 monynha && useradd --uid 10001 --gid monynha --no-create-home monynha

# The source tree remains under /app for the existing local docs/rules paths.
COPY --from=builder /app /app

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).close()"]

# A single process keeps process-local MCP state consistent across requests.
CMD ["uvicorn", "odoo_mcp.hosted:create_hosted_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
