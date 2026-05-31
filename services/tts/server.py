"""F5-TTS FastAPI HTTP wrapper — stratum-tts microservice.

Endpoints:
  GET  /health  → {status, model_loaded}
  POST /invoke  → {text, voice, speed} → {audio_b64}   (HttpToolClient compat)
  POST /synthesize → same as /invoke                    (human-friendly alias)
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stratum-tts")

app = FastAPI(title="stratum-tts", version="1.0.0")

# ── Global state ──────────────────────────────────────────────────────────────
_model: Any = None
_model_loaded: bool = False
_load_error: str = ""
_startup_time: float = time.time()

# Single-worker executor — GPU is not re-entrant
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="f5tts")

# Reference voices: voice_name → (audio_path, reference_text)
# "default" uses the bundled English example from the F5-TTS package.
def _default_ref() -> tuple[str, str]:
    try:
        from importlib.resources import files
        path = str(files("f5_tts").joinpath("infer/examples/basic/basic_ref_en.wav"))
        return path, "Some call me nature, others call me mother nature."
    except Exception:
        return "/workspace/F5-TTS/src/f5_tts/infer/examples/basic/basic_ref_en.wav", \
               "Some call me nature, others call me mother nature."

_VOICES: dict[str, tuple[str, str]] = {}


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup() -> None:
    global _model, _model_loaded, _load_error, _VOICES
    log.info("Startup: loading F5-TTS model (may download ~1GB on first run)...")
    _VOICES["default"] = _default_ref()

    def _load():
        from f5_tts.api import F5TTS  # noqa: PLC0415
        return F5TTS()

    loop = asyncio.get_event_loop()
    try:
        _model = await loop.run_in_executor(_executor, _load)
        _model_loaded = True
        log.info("F5-TTS model loaded OK.")
    except Exception as exc:
        _load_error = str(exc)
        log.error("F5-TTS model load failed: %s", exc)


# ── Schemas ───────────────────────────────────────────────────────────────────
class InvokeRequest(BaseModel):
    text: str
    voice: str = "default"
    speed: float = 1.0


class InvokeResponse(BaseModel):
    audio_b64: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    uptime_seconds: int
    error: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model_loaded=_model_loaded,
        uptime_seconds=int(time.time() - _startup_time),
        error=_load_error,
    )


def _run_inference(text: str, voice: str, speed: float) -> bytes:
    """Blocking inference — runs in thread executor."""
    ref_audio, ref_text = _VOICES.get(voice, _VOICES["default"])
    wav, sr, _ = _model.infer(
        ref_file=ref_audio,
        ref_text=ref_text,
        gen_text=text,
        speed=speed,
        show_info=False,
    )
    buf = io.BytesIO()
    sf.write(buf, wav, sr, format="WAV")
    return buf.getvalue()


async def _synthesize(req: InvokeRequest) -> InvokeResponse:
    if not _model_loaded or _model is None:
        raise HTTPException(
            status_code=503,
            detail=f"Model not ready. error={_load_error or 'still loading'}",
        )
    if not req.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    loop = asyncio.get_event_loop()
    try:
        wav_bytes = await loop.run_in_executor(
            _executor, _run_inference, req.text, req.voice, req.speed
        )
    except Exception as exc:
        log.error("inference failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"inference failed: {exc}") from exc

    audio_b64 = base64.b64encode(wav_bytes).decode()
    log.info("synthesized text_len=%d audio_bytes=%d", len(req.text), len(wav_bytes))
    return InvokeResponse(audio_b64=audio_b64)


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest) -> InvokeResponse:
    """HttpToolClient-compatible endpoint (oprim TtsClient calls this)."""
    return await _synthesize(req)


@app.post("/synthesize", response_model=InvokeResponse)
async def synthesize(req: InvokeRequest) -> InvokeResponse:
    """Human-friendly alias for /invoke."""
    return await _synthesize(req)


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "9301"))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
