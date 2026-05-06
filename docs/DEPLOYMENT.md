# Production deployment

## Checklist

1. **Secrets** — Set **`JWT_SECRET`** (long random string) for signing login tokens. Set at least one real AI key: `GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`. Never commit `server/.env` (gitignored).
2. **Admin user** — On first start with an **empty user collection**, the server seeds an admin from **`SEED_ADMIN_USERNAME`** / **`SEED_ADMIN_PASSWORD`** (defaults exist for dev — change immediately). Further users are created from the UI (Admin panel) or API.
3. **MongoDB** — Use a managed instance or the included `docker-compose` MongoDB. Set `MONGO_URI` and `DATABASE_NAME`.
4. **CORS** — Set `CORS_ORIGINS` to a comma-separated list of your real front-end origins (e.g. `https://faq.yourdomain.com`). Leave unset only for local dev (wildcard `*`).
5. **Environment** — `ENVIRONMENT=production` and `LOG_LEVEL=INFO` (or `WARNING`).
6. **TLS** — Put the app behind Nginx, Caddy, or a cloud load balancer with HTTPS; do not expose API keys in the browser.
7. **Scaling** — In Docker, increase `WEB_CONCURRENCY` (Gunicorn workers) to match CPU cores; each worker runs the FastAPI app.
8. **Health** — Use `GET /api/health` for load-balancer or Kubernetes liveness/readiness probes.

## Docker

```bash
# From repository root — set keys in your shell or a .env file used by Compose
export GROQ_API_KEY=...   # or GEMINI / OPENAI
export CORS_ORIGINS=https://your-frontend.example.com

docker compose build
docker compose up -d
```

The API listens on port **8000**. Data persists in the `mongodb_data` volume.

## Run without Docker (VM / bare metal)

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
gunicorn main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 --timeout 120
```

For development with auto-reload, use `uvicorn main:app --reload` instead.

## Reverse proxy snippet (Nginx)

Proxy `/` to `http://127.0.0.1:8000`, add `proxy_set_header Host $host`, `X-Forwarded-For`, `X-Forwarded-Proto` for correct URLs behind TLS.

## Operational notes

- **Demo mode** activates when no real AI credentials are configured; responses are canned FAQs — not suitable for production UX.
- **MongoDB mock mode** runs if Mongo is unreachable only for development; deploy real Mongo for persistence.
- **Optional** duplicate tree: `backend/core/ai_client.py` is legacy; the running app lives under **`server/`**.
