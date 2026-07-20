"""Stratum service layer configuration — loaded from environment variables."""

import os
from pathlib import Path

# ── Database ──────────────────────────────────────────────────────────────────
# PostgreSQL DSN for new service layer tables (highlights, subscriptions, etc.)
# The existing DuckDB store (~/.stratum/meta.duckdb) is unchanged.
DATABASE_DSN = os.environ.get(
    "STRATUM_DATABASE_DSN",
    "postgresql://stratum:stratum@localhost:5433/stratum",
)
DATABASE_POOL_MIN = int(os.environ.get("STRATUM_DB_POOL_MIN", "2"))
DATABASE_POOL_MAX = int(os.environ.get("STRATUM_DB_POOL_MAX", "10"))

# ── Service URLs ──────────────────────────────────────────────────────────────
BASE_URL = os.environ.get("STRATUM_BASE_URL", "http://localhost:9302")

# ── File storage ──────────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get("STRATUM_DATA_DIR", str(Path.home() / ".stratum")))
UPLOAD_MAX_SIZE_MB = int(os.environ.get("STRATUM_UPLOAD_MAX_MB", "500"))
TEMP_FILE_TTL_MINUTES = int(os.environ.get("STRATUM_TEMP_TTL_MIN", "30"))

# ── LLM defaults ──────────────────────────────────────────────────────────────
DEFAULT_LLM_PROVIDER = os.environ.get("STRATUM_LLM_PROVIDER", "qwen3")
DEFAULT_LLM_MODEL = os.environ.get("STRATUM_LLM_MODEL", "qwen3-max")
DEFAULT_BUDGET_USD = float(os.environ.get("STRATUM_BUDGET_USD", "5.0"))

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_EXPIRE_HOURS = int(os.environ.get("STRATUM_JWT_EXPIRE_HOURS", "168"))

# ── WeChat ────────────────────────────────────────────────────────────────────
WECHAT_APP_ID = os.environ.get("STRATUM_WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.environ.get("STRATUM_WECHAT_APP_SECRET", "")
WECHAT_TOKEN = os.environ.get("STRATUM_WECHAT_TOKEN", "")
WECHAT_MCH_ID = os.environ.get("STRATUM_WECHAT_MCH_ID", "")
WECHAT_API_KEY = os.environ.get("STRATUM_WECHAT_API_KEY", "")

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRATUM_STRIPE_SECRET", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRATUM_STRIPE_WEBHOOK_SECRET", "")

# ── Email ─────────────────────────────────────────────────────────────────────
SMTP_HOST = os.environ.get("STRATUM_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("STRATUM_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("STRATUM_SMTP_USER", "")
SMTP_PASS = os.environ.get("STRATUM_SMTP_PASS", "")
SMTP_FROM = os.environ.get("STRATUM_SMTP_FROM", "noreply@stratum.kanpan.co")

# ── Platform content (Hevi) ───────────────────────────────────────────────────
HEVI_CONTENT_REPO_URL = os.environ.get("STRATUM_HEVI_CONTENT_REPO", "")
HEVI_CONTENT_POLL_INTERVAL_MIN = int(os.environ.get("STRATUM_HEVI_POLL_MIN", "5"))

# ── Subscription pricing (CNY) ───────────────────────────────────────────────
PRICES: dict[str, dict[str, int]] = {
    "plus": {"monthly": 29, "yearly": 299},
    "pro": {"monthly": 99, "yearly": 999},
}
