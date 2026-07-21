FROM ghcr.io/astral-sh/uv:0.6.14 AS uv
FROM python:3.12.3-slim-bookworm

COPY --from=uv /uv /uvx /bin/
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md alembic.ini ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 fabricassist
USER fabricassist
EXPOSE 8000
CMD ["uvicorn", "fabricassist.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
