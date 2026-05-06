# FAQ SaaS (V7)

FastAPI service that scrapes page(s), optionally uses a **sitemap** for scoped internal URLs, generates FAQs via **Groq / Gemini / OpenAI**, and serves a small **admin UI** from `web/` (projects, history, exports).

## Requirements

- Python **3.10+**
- One of: **GROQ_API_KEY**, **GEMINI_API_KEY**, or **OPENAI_API_KEY** (see `server/.env.example`). For **OpenAI-compatible** hosts such as [AICC](https://api.ai.cc/console/token), set **`OPENAI_BASE_URL`** (e.g. `https://api.ai.cc/v1`), your key in **`OPENAI_API_KEY`**, optional **`OPENAI_MODEL`**, and usually **`AI_PROVIDER=openai`** if other keys are also set.
- **MongoDB** optional locally (app falls back to in-memory mock if DB is down — not for production persistence)

## Quick start

```bash
./setup.sh          # installs deps; copies server/.env.example → server/.env if missing
# Edit server/.env — add an AI key

./start.sh          # expects .venv at repo root; or:
cd server && ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** · API docs **http://localhost:8000/docs**

Sign in with the seeded admin account (when the DB is empty): **username `admin`** / password from **`SEED_ADMIN_PASSWORD`** (default in code: `vtnetzwelt`) — override in `server/.env`. Set **`JWT_SECRET`** for production.

**Important:** Uvicorn must run with working directory **`server/`** (as `./start.sh` does). From the repo root, `uvicorn main:app` fails with `Could not import module "main"` — either use `./start.sh` or:

`cd server && ../.venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`

If MongoDB is not running locally, the app still starts after ~2s (in-memory mock DB). Open the URL in the browser; do not open `web/index.html` as a `file://` page or API calls will fail.

### Troubleshooting

| Symptom | Fix |
|--------|-----|
| `Could not import module "main"` | Run from **`server/`** (`./start.sh` or `cd server` then uvicorn). |
| `No .venv found` | Run `./setup.sh` once, or install deps globally and use `python3` (start.sh falls back). |
| Blank page / fetch errors | Use **http://localhost:8000**, not `file:///.../index.html`. |
| Slow first start | Without Mongo, wait ~2s for DB probe; then the server binds. |
| Groq “rate limit” / 429 | Free tier daily caps apply. The server tries other Groq models, then **Gemini** / **OpenAI** if keys are set in `server/.env`. |

## Docker (recommended for production)

```bash
export GROQ_API_KEY=...                    # or GEMINI / OPENAI
export CORS_ORIGINS=https://your-app.com   # optional in dev; use in prod

docker compose build && docker compose up -d
```

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for checklist, Gunicorn, TLS, and scaling (`WEB_CONCURRENCY`).

## Layout

```
faq_saas_v7/
├── server/           # FastAPI app (run from here or Docker WORKDIR /app/server)
├── web/              # Static UI
├── Dockerfile
├── docker-compose.yml
└── docs/
```

Optional: `react-app/` — if built, static mount prefers `web/` then `react-app/build`.

## API (short)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health / demo flag |
| POST | `/api/generate` | FAQ generation |
| POST | `/api/export` | CSV / XLSX / DOCX / PDF |
| CRUD | `/api/projects`, `/api/history` | Projects & history |

## Configuration

All variables are documented in **`server/.env.example`**. Important for production:

- **`CORS_ORIGINS`** — comma-separated browser origins (do not rely on `*` in production).
- **`LOG_LEVEL`** — `INFO`, `WARNING`, etc.
- **`ENVIRONMENT`** — set `production` when deployed.

## Documentation

- **Deployment & operations:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Interactive API:** `/docs` and `/redoc` on a running server

## License

Use and modify under your own terms.
