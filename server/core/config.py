import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load server/.env regardless of cwd (uvicorn may start from repo root)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv()  # optional: cwd .env overrides

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-test-key")
# OpenAI-compatible API (e.g. https://api.ai.cc/v1 for AICC — get key at https://api.ai.cc/console/token)
OPENAI_BASE_URL = (os.getenv("OPENAI_BASE_URL") or "").strip().rstrip("/")
# Model id for chat.completions (set to a model your host supports, e.g. gpt-4o-mini)
OPENAI_MODEL = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
# Free-tier alternatives (set one to avoid demo/sample FAQs):
# Groq: https://console.groq.com — OpenAI-compatible API, fast inference
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
# Google AI Studio: https://aistudio.google.com/apikey — Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# Optional overrides: groq | gemini | openai (default: auto-pick first available key)
AI_PROVIDER = (os.getenv("AI_PROVIDER") or "").strip().lower()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Use an ID that exists on generativelanguage.googleapis.com v1beta (see ListModels).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Offline / UI testing: no external AI calls (returns sample FAQs from scraped text category)
MOCK_AI = os.getenv("MOCK_AI", "").strip().lower() in ("1", "true", "yes", "on")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "faq_saas_v7")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Comma-separated list; empty = allow all origins (development only — set explicitly in production)
_raw_cors = (os.getenv("CORS_ORIGINS") or "").strip()


def cors_allow_origins() -> list[str]:
    """Allowed browser origins for CORS. Empty env → ['*'] (wildcard)."""
    if not _raw_cors:
        return ["*"]
    return [o.strip() for o in _raw_cors.split(",") if o.strip()]


LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()

# JWT (set JWT_SECRET in production)
JWT_SECRET = (os.getenv("JWT_SECRET") or "change-me-in-production-dev-only").strip()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES") or "10080")

# First-run admin seed when `users` collection is empty (override in .env)
SEED_ADMIN_USERNAME = (os.getenv("SEED_ADMIN_USERNAME") or "admin").strip()
SEED_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD") or "vtnetzwelt"


def has_real_ai_credentials() -> bool:
    """True if any configured provider can run real (non-demo) generation."""
    if GROQ_API_KEY:
        return True
    if GEMINI_API_KEY:
        return True
    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"):
        return True
    return False


def has_openai_compat_key() -> bool:
    return bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-test"))


def log_ai_env_status() -> None:
    """One-line diagnostic (no secrets)."""
    logger.info(
        "AI env: mock=%s gemini=%s groq=%s openai_real=%s openai_base_url=%s provider=%s",
        MOCK_AI,
        "set" if GEMINI_API_KEY else "empty",
        "set" if GROQ_API_KEY else "empty",
        has_openai_compat_key(),
        "set" if OPENAI_BASE_URL else "default",
        (os.getenv("AI_PROVIDER") or "auto"),
    )


log_ai_env_status()

# Token limits for API
MAX_TOKENS_PER_REQUEST = 4000
# Scraped + labeled text length cap before sending to the LLM (not the same as model max tokens)
MAX_SOURCE_CONTENT_FOR_LLM = 10000
MAX_URLS = 10
DEFAULT_FAQ_COUNT = 5
MAX_FAQ_COUNT = 50

# Similarity threshold for deduplication
SIMILARITY_THRESHOLD = 0.85
