import os
import glob
from typing import Optional
from fastapi import APIRouter, Body
from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response
from aii.service.ku_ingestion_engine import KuIngestionEngine

router = APIRouter()

@router.post("/feed")
async def feed(
    dir_path: str = Body(...),
    glob_pattern: str = Body("*.md"),
    max_chunks: Optional[int] = Body(None),
    max_files: Optional[int] = Body(None)
):
    engine = KuIngestionEngine(backend=backend)
    if not os.path.isdir(dir_path):
        return error_response("INVALID_DIRECTORY", f"Path {dir_path} is not a directory")

    files = glob.glob(os.path.join(dir_path, glob_pattern))
    if max_files:
        files = files[:max_files]

    total_ku_ids = []
    files_processed = 0
    total_chunks = 0
    
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            
            res = await engine.ingest(content)
            total_ku_ids.extend(res.get("registered", []))
            total_chunks += res.get("chunks_processed", 0)
            files_processed += 1
            
            if max_chunks and total_chunks >= max_chunks:
                break
        except Exception as e:
            continue

    return success_response({
        "files_processed": files_processed,
        "total_ku_ids": len(total_ku_ids),
        "total_chunks": total_chunks,
        "stopped_early": (max_files and files_processed >= max_files) or (max_chunks and total_chunks >= max_chunks)
    })
