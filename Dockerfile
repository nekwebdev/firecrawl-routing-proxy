# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Dependency layer: only metadata first
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip wheel && \
    python -m pip wheel --wheel-dir /wheels \
      "fastapi>=0.115.0" \
      "httpx>=0.28.0" \
      "pydantic>=2.9.0" \
      "pydantic-settings>=2.6.0" \
      "uvicorn[standard]>=0.32.0"

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Source layer last for cache reuse when app code changes
COPY app ./app

RUN mkdir -p /data && chown -R app:app /app /data
USER app

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
