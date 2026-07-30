FROM ghcr.io/astral-sh/uv:0.6.14 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Refresh the rolling Bookworm security packages and the Python packaging
# tools shipped in the base image before installing application dependencies.
RUN apt-get update \
    && apt-get upgrade --yes \
    && python -m pip install --no-cache-dir --upgrade \
        "setuptools>=78.1.1" \
        "wheel>=0.46.2" \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 fabricassist
USER fabricassist
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn fabricassist.api.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1"]
