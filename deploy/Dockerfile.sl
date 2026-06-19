# Build context: /home/soffy/projects  (parent of stratum/ and platform/)
FROM python:3.14-slim

WORKDIR /app

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        libmagic-dev \
        ffmpeg \
        nodejs \
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
        "edge-tts>=6.1" \
        defusedxml \
        numpy \
        scipy \
        pandas \
        scikit-learn \
        statsmodels \
        fsrs \
        paramiko \
        apscheduler \
        redis \
        duckdb \
        docker \
        asyncpg \
        "psycopg[binary]" \
        psutil \
        python-magic \
        boto3 \
        dnspython \
        trafilatura \
        readability-lxml \
        jinja2 \
        python-alipay-sdk \
        stripe \
        tenacity \
        bcrypt \
        pyotp \
        qrcode \
        rapidfuzz \
        pgvector \
        beautifulsoup4 \
        lxml \
        Pillow \
        ebooklib \
        chardet \
        google-api-python-client \
        google-auth-oauthlib \
        google-auth-httplib2 \
        dashscope \
        argon2-cffi \
        pyjwt \
        yt-dlp \
        faster-whisper

# yt-dlp: use nodejs as JS runtime (avoids deno default which isn't installed)
RUN mkdir -p /root/.config/yt-dlp && echo '--js-runtimes node' > /root/.config/yt-dlp/config

# python-ulid v3.x installs as module 'ulid'; oskill/omodul use 'python_ulid' (v2.x name).
# Shim: expose the same package under the old module name.
RUN python3 -c "\
import site, pathlib; \
d = pathlib.Path(site.getsitepackages()[0]) / 'python_ulid.py'; \
d.write_text('from ulid import *\nfrom ulid import ULID\n')"

# ── Platform packages (copied from host, installed editable) ──────────────────
# Packages live at platform/3O/{obase,oprim,oskill,omodul} in the build context.
# obase — no inter-package deps
COPY platform/3O/obase /opt/platform/obase
RUN pip install --no-cache-dir --no-deps -e /opt/platform/obase

# oprim — no inter-package deps
COPY platform/3O/oprim /opt/platform/oprim
RUN pip install --no-cache-dir --no-deps -e /opt/platform/oprim

# oskill — depends on oprim
COPY platform/3O/oskill /opt/platform/oskill
RUN pip install --no-cache-dir --no-deps -e /opt/platform/oskill

# omodul — depends on oprim + oskill + obase
COPY platform/3O/omodul /opt/platform/omodul
RUN pip install --no-cache-dir --no-deps -e /opt/platform/omodul

# oservi — depends on obase + oprim + oskill + omodul (already installed above).
# --no-deps avoids pulling git+ssh:// refs that require SSH keys unavailable in Docker build.
COPY platform/3O/oservi /opt/platform/oservi
RUN pip install --no-cache-dir --no-deps -e /opt/platform/oservi

# ── Application source ────────────────────────────────────────────────────────
COPY stratum/src/ /app/src/

ENV PYTHONPATH=/app/src

EXPOSE 9304

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:9304/api/v1/health || exit 1

CMD ["uvicorn", "stratum.api.main:app", "--host", "0.0.0.0", "--port", "9304"]
