from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import auth
from .middleware.corpus_isolation import corpus_isolation_middleware

app = FastAPI(title="Stratum API", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
@app.get("/health")
def health_check(): return {"status": "healthy"}
