FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY agent_service/ agent_service/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "agent_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
