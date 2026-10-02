from fastapi import APIRouter, Body
from aii.api._envelope import error_response

router = APIRouter()


@router.post("/ingest")
async def ingest(text: str = Body(..., embed=True)):
    # 旧摄取链路(KuIngestionEngine→旧表)已退役. 摄取走 onto 飞轮(USE_ONTOLOGY).
    return error_response(
        "DEPRECATED", "manual /ingest retired; ingestion now goes through the onto flywheel"
    )
