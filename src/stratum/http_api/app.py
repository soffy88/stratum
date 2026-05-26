"""Stratum HTTP API application."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from stratum.middleware.corpus_isolation import corpus_isolation_middleware
from stratum.http_api.routes import auth, search, substrates, notes, agents, scheduled_jobs
from stratum.http_api.routes.share import router as share_router

app = FastAPI(title="Stratum API", version="1.2.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def corpus_mw(request: Request, call_next):
    return await corpus_isolation_middleware(request, call_next)


# Auth (exempt from corpus middleware)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Authenticated routes (corpus_id injected by middleware)
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(substrates.router, prefix="/api", tags=["substrates"])
app.include_router(notes.router, prefix="/api", tags=["notes"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(scheduled_jobs.router, prefix="/api", tags=["scheduled_jobs"])

# Share (mixed: authenticated create/revoke + public read)
app.include_router(share_router, tags=["share"])


@app.get("/health")
def health_check():
    return {"status": "healthy"}
