"""Intermediate persistence with resume support — P13-RUNTIME-QUALIFICATION-001 §12-§13.

Provides checkpointing for CPU-only long-running book processing.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stratum.knowledge.bu_v2_models import ChapterUnderstanding, ChapterDelta
from stratum.services.bu_v2_producer import EvidenceArtifact
from stratum.services.bu_v2_chunk_planner import SemanticChunk, ChunkPlan


@dataclass
class ChunkCheckpoint:
    """Checkpoint for a completed chunk."""

    run_id: str
    chapter_id: str
    chunk_id: str
    stage: str  # "chunk_understanding", "chunk_synthesis", "chapter_synthesis"
    input_hash: str
    output_data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: str | None = None


@dataclass
class ChapterCheckpoint:
    """Aggregate checkpoint for a chapter."""

    run_id: str
    chapter_id: str
    chunks_completed: list[str] = field(default_factory=list)
    chunk_understandings: list[dict] = field(default_factory=list)
    chapter_synthesis: dict | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    success: bool = False
    error: str | None = None


class BU2IntermediateStore:
    """File-based intermediate store with resume capability.

    Stores checkpoints at:
    - docs/book-understanding-2.0/evidence/p13_cpu/{run_id}/
    """

    def __init__(self, base_path: str | None = None):
        if base_path is None:
            base_path = "docs/book-understanding-2.0/evidence/p13_cpu"
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        d = self.base_path / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _chapter_dir(self, run_id: str, chapter_id: str) -> Path:
        d = self._run_dir(run_id) / chapter_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _checkpoint_path(self, run_id: str, chapter_id: str, chunk_id: str, stage: str) -> Path:
        safe_stage = stage.replace("/", "_")
        return self._chapter_dir(run_id, chapter_id) / f"{chunk_id}_{safe_stage}.json"

    def _chapter_checkpoint_path(self, run_id: str, chapter_id: str) -> Path:
        return self._chapter_dir(run_id, chapter_id) / "chapter_checkpoint.json"

    def _plan_path(self, run_id: str) -> Path:
        return self._run_dir(run_id) / "chunk_plan.json"

    def save_chunk_plan(self, run_id: str, plans: dict[str, ChunkPlan]) -> None:
        """Save the chunk plan for the entire run."""
        data = {
            chapter_id: {
                "chapter_id": plan.chapter_id,
                "total_chars": plan.total_chars,
                "estimated_calls": plan.estimated_calls,
                "chunks": [
                    {
                        "chunk_id": c.chunk_id,
                        "chapter_id": c.chapter_id,
                        "start_offset": c.start_offset,
                        "end_offset": c.end_offset,
                        "section_context": c.section_context,
                        "sequence": c.sequence,
                        "split_reason": c.split_reason,
                        "overlap_chars": c.overlap_chars,
                    }
                    for c in plan.chunks
                ],
            }
            for chapter_id, plan in plans.items()
        }
        self._plan_path(run_id).write_text(json.dumps(data, indent=2))

    def load_chunk_plan(self, run_id: str) -> dict[str, ChunkPlan] | None:
        """Load chunk plan if exists."""
        path = self._plan_path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        # Reconstruct ChunkPlan objects (simplified)
        return data

    def save_chunk_checkpoint(
        self,
        run_id: str,
        chapter_id: str,
        chunk_id: str,
        stage: str,
        input_hash: str,
        output_data: dict[str, Any],
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Save checkpoint for a chunk stage."""
        checkpoint = ChunkCheckpoint(
            run_id=run_id,
            chapter_id=chapter_id,
            chunk_id=chunk_id,
            stage=stage,
            input_hash=input_hash,
            output_data=output_data,
            success=success,
            error=error,
        )
        path = self._checkpoint_path(run_id, chapter_id, chunk_id, stage)
        path.write_text(json.dumps(checkpoint.__dict__, indent=2, default=str))

    def load_chunk_checkpoint(
        self,
        run_id: str,
        chapter_id: str,
        chunk_id: str,
        stage: str,
    ) -> ChunkCheckpoint | None:
        """Load checkpoint if exists and valid."""
        path = self._checkpoint_path(run_id, chapter_id, chunk_id, stage)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return ChunkCheckpoint(**data)

    def is_chunk_completed(
        self,
        run_id: str,
        chapter_id: str,
        chunk_id: str,
        stage: str,
        expected_input_hash: str,
    ) -> bool:
        """Check if chunk stage is completed with matching input."""
        checkpoint = self.load_chunk_checkpoint(run_id, chapter_id, chunk_id, stage)
        if not checkpoint:
            return False
        if not checkpoint.success:
            return False
        return checkpoint.input_hash == expected_input_hash

    def save_chapter_checkpoint(
        self,
        run_id: str,
        chapter_id: str,
        chunks_completed: list[str] | None = None,
        chunk_understandings: list[dict] | None = None,
        chapter_synthesis: dict | None = None,
        completed: bool = False,
        error: str | None = None,
    ) -> None:
        """Save/update chapter aggregate checkpoint."""
        path = self._chapter_checkpoint_path(run_id, chapter_id)

        # Load existing
        existing = None
        if path.exists():
            existing = json.loads(path.read_text())

        checkpoint = ChapterCheckpoint(
            run_id=run_id,
            chapter_id=chapter_id,
            chunks_completed=chunks_completed or (existing.get("chunks_completed", []) if existing else []),
            chunk_understandings=chunk_understandings or (existing.get("chunk_understandings", []) if existing else []),
            chapter_synthesis=chapter_synthesis or (existing.get("chapter_synthesis") if existing else None),
            started_at=existing.get("started_at", time.time()) if existing else time.time(),
            completed_at=time.time() if completed else None,
            success=completed and error is None,
            error=error,
        )
        path.write_text(json.dumps(checkpoint.__dict__, indent=2, default=str))

    def load_chapter_checkpoint(self, run_id: str, chapter_id: str) -> ChapterCheckpoint | None:
        """Load chapter checkpoint."""
        path = self._chapter_checkpoint_path(run_id, chapter_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return ChapterCheckpoint(**data)

    def get_completed_chapters(self, run_id: str) -> list[str]:
        """Get list of successfully completed chapter IDs."""
        completed = []
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            return completed

        for chapter_dir in run_dir.iterdir():
            if not chapter_dir.is_dir():
                continue
            checkpoint_path = chapter_dir / "chapter_checkpoint.json"
            if checkpoint_path.exists():
                try:
                    data = json.loads(checkpoint_path.read_text())
                    if data.get("success") and data.get("completed_at"):
                        completed.append(chapter_dir.name)
                except Exception:
                    pass
        return completed

    def get_completed_chunks(self, run_id: str, chapter_id: str, stage: str) -> list[str]:
        """Get list of completed chunk IDs for a chapter and stage."""
        completed = []
        chapter_dir = self._chapter_dir(run_id, chapter_id)
        if not chapter_dir.exists():
            return completed

        for path in chapter_dir.glob(f"*_{stage}.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("success"):
                    # Extract chunk_id from filename
                    chunk_id = path.stem.replace(f"_{stage}", "")
                    completed.append(chunk_id)
            except Exception:
                pass
        return completed

    def save_run_metadata(self, run_id: str, metadata: dict[str, Any]) -> None:
        """Save run-level metadata."""
        path = self._run_dir(run_id) / "run_metadata.json"
        path.write_text(json.dumps(metadata, indent=2, default=str))

    def load_run_metadata(self, run_id: str) -> dict[str, Any] | None:
        """Load run metadata."""
        path = self._run_dir(run_id) / "run_metadata.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())


def _compute_input_hash(*parts: str) -> str:
    """Compute deterministic hash for idempotency — §13."""
    import hashlib

    raw = "|".join(p for p in parts if p)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_chunk_input_hash(
    run_id: str,
    chapter_id: str,
    chunk_id: str,
    stage: str,
    prompt: str,
    system: str,
) -> str:
    """Deterministic key for idempotent chunk execution — §13."""
    return _compute_input_hash(run_id, chapter_id, chunk_id, stage, prompt, system)