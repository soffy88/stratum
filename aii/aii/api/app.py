import asyncio
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from aii.api._provider import register_providers
from aii.storage.pg_backend import PgBackend
from aii.api._dependencies import backend
from aii.api.routes import health, ingest, feed, query, chat, evolution, governance, stats, display
from aii.api._auth import APIKeyMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load environment (override to ignore placeholder system env vars)
    load_dotenv(override=True)
    
    # 2. Register providers (LLM, Embedding)
    register_providers()
    
    # 3. Monkey-patch oskill (fix internal 'module not callable' errors)
    try:
        import oskill.ku_extract_pipeline
        import oprim.structural_chunk
        import oprim.llm_extract_ku
        import oprim.ku_gate_validate
        
        oskill.ku_extract_pipeline.structural_chunk = oprim.structural_chunk.structural_chunk
        oskill.ku_extract_pipeline.llm_extract_ku = oprim.llm_extract_ku.llm_extract_ku
        oskill.ku_extract_pipeline.ku_gate_validate = oprim.ku_gate_validate.ku_gate_validate
        logger.info("oskill monkey-patch applied successfully.")
    except Exception as e:
        logger.warning(f"oskill monkey-patch failed: {e}")

    # 4. Initialize PG Pool
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        # Default DSN for local development if not in env
        dsn = "postgresql://aii_user:aii_pass@localhost:5432/aii_db"
    
    backend.dsn = dsn
    await backend._ensure_pool()
    logger.info("AII Backend initialized and PG Pool started.")

    # 5. 启动后台飞轮
    from aii.service.background_flywheel import flywheel_loop
    flywheel_task = asyncio.create_task(flywheel_loop(backend), name="aii-flywheel")
    app.state.flywheel_task = flywheel_task
    logger.info("AII background flywheel started.")

    yield

    # Cleanup
    flywheel_task.cancel()
    try:
        await flywheel_task
    except asyncio.CancelledError:
        pass
    if backend._pool:
        await backend._pool.close()
        logger.info("AII PG Pool closed.")

app = FastAPI(title="AII API", version="0.1.0", lifespan=lifespan)

# Auth + rate limiting (runs before CORS so preflight still passes)
app.add_middleware(APIKeyMiddleware)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "https://aii.uex.hk",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Route Mounting (Unified /api prefix)
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(ingest.router, prefix="/api", tags=["ingest"])
app.include_router(feed.router, prefix="/api", tags=["feed"])
app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(evolution.router, prefix="/api", tags=["evolution"])
app.include_router(governance.router, prefix="/api", tags=["governance"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(display.router, prefix="/api", tags=["display"])
