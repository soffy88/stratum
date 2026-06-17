from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from aii.service.ku_ingestion_engine import KuIngestionEngine

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/ingest")
async def ingest(text: str = Body(..., embed=True)):
    engine = KuIngestionEngine(backend=backend)
    try:
        results = await engine.ingest(text)
        return success_response(results)
    except Exception as e:
        logger.exception("Ingest failed")
        return error_response("INGEST_ERROR", str(e))
