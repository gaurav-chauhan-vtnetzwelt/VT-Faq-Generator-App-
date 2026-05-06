# FAQ SaaS API + static web UI
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    WEB_CONCURRENCY=2

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt ./server/
RUN pip install --no-cache-dir -r ./server/requirements.txt

COPY server ./server
COPY web ./web

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

WORKDIR /app/server
USER appuser

EXPOSE 8000

# Workers scale with WEB_CONCURRENCY; increase on larger hosts
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"

CMD ["sh", "-c", "exec gunicorn main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-2} -b 0.0.0.0:8000 --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile -"]
