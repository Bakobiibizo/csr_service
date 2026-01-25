FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml ./

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy source, config, and standards
COPY src/ src/
COPY config/ config/
COPY standards/ standards/

EXPOSE 9020

CMD ["uv", "run", "uvicorn", "src.csr_service.main:app", "--host", "0.0.0.0", "--port", "9020"]
