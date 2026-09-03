# Single image: builds the web UI and bundles it into the API image, which serves
# both the SPA (at /) and the API (at /api/v1). Build context is the repo root.
#
#   docker build -t tesqivo .
#   docker run -p 8080:8080 -e TESQIVO_DB_URL=... -e TESQIVO_REDIS_URL=... tesqivo

# --- stage 1: build the SPA ---------------------------------------------------
FROM node:22-alpine AS web-build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_BASE=/api/v1
RUN npm run build   # -> /web/dist

# --- stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESQIVO_STATIC_DIR=/app/static \
    TESQIVO_ATTACHMENT_DIR=/data/attachments \
    TESQIVO_SECRET_KEY_FILE=/data/secret_key

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
COPY --from=web-build /web/dist ./static

ARG TESQIVO_VERSION=0.0.0-dev
ENV TESQIVO_VERSION=$TESQIVO_VERSION

RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --uid 10001 --create-home tesqivo \
    && mkdir -p /data/attachments \
    && chown -R tesqivo /app /data
USER tesqivo

EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD curl -fsS http://localhost:8080/api/v1/healthz || exit 1

LABEL org.opencontainers.image.title="TESQIVO" \
      org.opencontainers.image.description="API-first test management platform" \
      org.opencontainers.image.source="https://github.com/abhid001/TESQIVO" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
