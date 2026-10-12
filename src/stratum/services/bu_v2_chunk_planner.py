"""CPU-only chunk planner — P13-RUNTIME-QUALIFICATION-001 §6.

Deterministically splits chapter text into semantic chunks for bounded LLM inference.
No LLM calls — purely structural.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# Chunk size targets
TARGET_MIN_CHARS = 5000
TARGET_MAX_CHARS = 12000
HARD_MAX_CHARS = 15000
OVERLAP_CHARS = 200

# Patterns that must NOT be split
_MATH_BLOCK = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$", re.DOTALL)
_MATH_DISPLAY = re.compile(r"\\\[.*?\\\]", re.DOTALL)
_CITATION = re.compile(r"\[[\d,\s\-]+\]")
_DEFINITION = re.compile(
    r"(Definition|Theorem|Lemma|Corollary|Proposition|Axiom|Postulate)\s+\d+[\.\:]",
    re.I,
)
_PROOF_START = re.compile(r"\bProof\b[\.\:]", re.I)
_NUMBERED_LIST = re.compile(r"^\s*\d+[\.\)]\s", re.M)


@dataclass
class SemanticChunk:
    """A deterministically bounded semantic unit of a chapter."""

    chunk_id: str
    chapter_id: str
    start_offset: int
    end_offset: int
    text: str
    section_context: str
    sequence: int
    split_reason: str = "SECTION_BOUNDARY"
    overlap_chars: int = 0

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class ChunkPlan:
    """Complete plan for processing one chapter."""

    chapter_id: str
    chunks: list[SemanticChunk]
    total_chars: int
    estimated_calls: int


def _find_section_boundaries(text: str) -> list[tuple[int, str]]:
    """Find all section/subsection boundaries in chapter text.

    Returns list of (offset, section_title).
    """
    boundaries = []

    # Markdown headings
    for m in re.finditer(r"^(#{2,4})\s+(.+)$", text, re.M):
        boundaries.append((m.start(), m.group(2).strip()))

    # Numbered sections like "3.1 Title" or "Section 3.1"
    for m in re.finditer(r"^(?:Section\s+)?(\d+\.\d+)\s+(.+)$", text, re.M):
        boundaries.append((m.start(), m.group(2).strip()))

    return sorted(boundaries)


def _find_paragraph_boundaries(text: str, start: int, end: int) -> list[int]:
    """Find paragraph boundaries (blank lines) within a range."""
    boundaries = []
    for m in re.finditer(r"\n\s*\n", text[start:end]):
        boundaries.append(start + m.end())
    return boundaries


def _find_sentence_boundaries(text: str, start: int, end: int) -> list[int]:
    """Find sentence boundaries within a range."""
    boundaries = []
    # Simple sentence boundary: period + space + uppercase
    for m in re.finditer(r"\.\s+[A-Z]", text[start:end]):
        boundaries.append(start + m.end() - 1)
    return boundaries


def _is_protected_region(text: str, start: int, end: int) -> bool:
    """Check if region contains content that must not be split."""
    region = text[start:end]

    # Math blocks
    if _MATH_BLOCK.search(region):
        return True
    if _MATH_DISPLAY.search(region):
        return True

    # Definitions, theorems, proofs
    if _DEFINITION.search(region):
        return True
    if _PROOF_START.search(region):
        return True

    # Citations (don't split mid-citation cluster)
    citations = _CITATION.findall(region)
    if len(citations) > 3:
        return True

    # Numbered list items
    if _NUMBERED_LIST.search(region):
        return True

    return False


def _split_at_boundary(text: str, start: int, target_end: int, hard_max: int) -> int:
    """Find the best split point near target_end, respecting protected regions."""

    # If target is within hard_max, just use it
    if target_end <= hard_max:
        return target_end

    # Try section boundaries first
    boundaries = _find_section_boundaries(text[start:])
    for offset, _ in boundaries:
        abs_offset = start + offset
        if start < abs_offset <= hard_max:
            return abs_offset

    # Try paragraph boundaries
    para_bounds = _find_paragraph_boundaries(text, start, hard_max)
    for b in reversed(para_bounds):
        if b - start >= TARGET_MIN_CHARS:
            # Check if protected
            if not _is_protected_region(text, b - 100, b + 100):
                return b

    # Try sentence boundaries
    sent_bounds = _find_sentence_boundaries(text, start, hard_max)
    for b in reversed(sent_bounds):
        if b - start >= TARGET_MIN_CHARS:
            if not _is_protected_region(text, b - 50, b + 50):
                return b

    # Hard split — must record reason
    return hard_max


class BU2ChunkPlanner:
    """Plan deterministic semantic chunks for a chapter."""

    def __init__(
        self,
        *,
        target_min_chars: int = TARGET_MIN_CHARS,
        target_max_chars: int = TARGET_MAX_CHARS,
        hard_max_chars: int = HARD_MAX_CHARS,
        overlap_chars: int = OVERLAP_CHARS,
    ):
        self.target_min = target_min_chars
        self.target_max = target_max_chars
        self.hard_max = hard_max_chars
        self.overlap = overlap_chars

    def plan_chapter(
        self, chapter_id: str, chapter_text: str, section_context: str = ""
    ) -> ChunkPlan:
        """Plan chunks for one chapter.

        Args:
            chapter_id: Chapter identifier (e.g., "ch1")
            chapter_text: Full chapter text
            section_context: Context about chapter's section/position

        Returns:
            ChunkPlan with deterministic chunks
        """
        chunks: list[SemanticChunk] = []
        total_chars = len(chapter_text)

        if total_chars <= self.hard_max:
            # Single chunk
            chunks.append(
                SemanticChunk(
                    chunk_id=f"{chapter_id}_ck1",
                    chapter_id=chapter_id,
                    start_offset=0,
                    end_offset=total_chars,
                    text=chapter_text,
                    section_context=section_context,
                    sequence=1,
                    split_reason="SINGLE_CHUNK",
                )
            )
            return ChunkPlan(
                chapter_id=chapter_id,
                chunks=chunks,
                total_chars=total_chars,
                estimated_calls=1,
            )

        # Multi-chunk planning
        start = 0
        sequence = 0

        while start < total_chars:
            sequence += 1
            target_end = min(start + self.target_max, total_chars)

            # Find best split point
            split_point = _split_at_boundary(chapter_text, start, target_end, self.hard_max)

            # Ensure minimum chunk size
            if split_point - start < self.target_min and sequence > 1:
                # Extend to minimum if possible
                split_point = min(start + self.target_min, total_chars)

            # Determine split reason
            if split_point >= total_chars:
                split_reason = "END_OF_CHAPTER"
            elif split_point == self.hard_max:
                split_reason = "HARD_SPLIT"
            else:
                split_reason = "SECTION_BOUNDARY"

            chunk_text = chapter_text[start:split_point]

            chunks.append(
                SemanticChunk(
                    chunk_id=f"{chapter_id}_ck{sequence}",
                    chapter_id=chapter_id,
                    start_offset=start,
                    end_offset=split_point,
                    text=chunk_text,
                    section_context=section_context,
                    sequence=sequence,
                    split_reason=split_reason,
                    overlap_chars=self.overlap if sequence > 1 else 0,
                )
            )

            # Next chunk starts with overlap
            if split_point >= total_chars:
                break
            start = max(start + 1, split_point - self.overlap)

        return ChunkPlan(
            chapter_id=chapter_id,
            chunks=chunks,
            total_chars=total_chars,
            estimated_calls=len(chunks) + 1,  # +1 for chapter synthesis
        )


def plan_all_chapters(
    chapters: list[tuple[str, str, str]],
    **planner_kwargs,
) -> dict[str, ChunkPlan]:
    """Plan chunks for all chapters.

    Args:
        chapters: List of (chapter_id, chapter_text, section_context)
        **planner_kwargs: Passed to BU2ChunkPlanner

    Returns:
        Dict mapping chapter_id to ChunkPlan
    """
    planner = BU2ChunkPlanner(**planner_kwargs)
    plans = {}
    for chapter_id, text, context in chapters:
        plans[chapter_id] = planner.plan_chapter(chapter_id, text, context)
    return plans
