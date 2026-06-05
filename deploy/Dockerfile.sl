# Build context: /home/soffy/projects  (parent of stratum/ and platform/)
FROM python:3.14-slim

WORKDIR /app

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Python runtime deps ───────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
        psycopg2-binary \
        fastapi \
        "uvicorn[standard]" \
        "python-jose[cryptography]" \
        pydantic \
        httpx \
        python-multipart \
        python-ulid \
        pyyaml \
        structlog \
        "mcp>=1.27" \
        alembic \
        python-frontmatter \
        pymupdf4llm \
        lancedb \
        tantivy \
        pymupdf \
        "edge-tts>=6.1"

# ── Platform packages (copied from host, installed editable) ──────────────────
# Packages live at platform/3O/{obase,oprim,oskill,omodul} in the build context.
# obase — no inter-package deps
COPY platform/3O/obase /opt/platform/obase
RUN pip install --no-cache-dir -e /opt/platform/obase

# oprim — no inter-package deps
COPY platform/3O/oprim /opt/platform/oprim
RUN pip install --no-cache-dir -e /opt/platform/oprim

# oskill — depends on oprim
COPY platform/3O/oskill /opt/platform/oskill
RUN pip install --no-cache-dir -e /opt/platform/oskill

# omodul — depends on oprim + oskill + obase
COPY platform/3O/omodul /opt/platform/omodul
RUN pip install --no-cache-dir -e /opt/platform/omodul

# oservice — depends on obase + oprim + oskill + omodul
COPY platform/3O/oservice /opt/platform/oservice
RUN pip install --no-cache-dir -e /opt/platform/oservice

# ── Application source ────────────────────────────────────────────────────────
COPY stratum/src/ /app/src/

ENV PYTHONPATH=/app/src

EXPOSE 9304

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:9304/api/v1/health || exit 1

CMD ["uvicorn", "stratum.api.main:app", "--host", "0.0.0.0", "--port", "9304"]
