from typing import Optional
from fastapi import APIRouter, Body
from aii.api._envelope import error_response

router = APIRouter()


@router.post("/feed")
async def feed(
    dir_path: str = Body(...),
    glob_pattern: str = Body("*.md"),
    max_chunks: Optional[int] = Body(None),
    max_files: Optional[int] = Body(None),
):
    # 旧批量摄取(KuIngestionEngine→旧表)已退役. 摄取走 onto 飞轮(USE_ONTOLOGY).
    return error_response(
        "DEPRECATED", "manual /feed retired; ingestion now goes through the onto flywheel"
    )
