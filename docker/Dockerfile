FROM python:3.11-slim

WORKDIR /app

# Runtime dependencies live in the uv-managed virtualenv; remove build tooling
# inherited from the base image to reduce attack surface.
RUN python -m pip uninstall --yes setuptools wheel && rm -rf /root/.cache/pip

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source, config, and standards
COPY src/ src/
COPY config/ config/
COPY standards/ standards/

RUN addgroup --system csr && adduser --system --ingroup csr csr \
    && chown -R csr:csr /app

USER csr

EXPOSE 9020

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9020/ready', timeout=2)"]

CMD ["uv", "run", "--no-sync", "uvicorn", "src.csr_service.main:app", "--host", "0.0.0.0", "--port", "9020", "--proxy-headers"]
