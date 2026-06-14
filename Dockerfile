FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY overrides/ ./overrides/
COPY docs/ ./docs/
COPY docker-entrypoint.sh /usr/local/bin/

RUN chown -R app:app /app && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uv", "run", "gunicorn", "src.server:create_app()", \
     "--bind", "0.0.0.0:8080", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "30"]
