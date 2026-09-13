"""Best-effort derived alignment; original fragment IDs remain authoritative."""

from __future__ import annotations
from difflib import SequenceMatcher


def align_fragment(original: str, translated: str) -> dict[str, object]:
    """Return ranges/score for UI highlights without making translation canonical."""
    score = SequenceMatcher(None, original, translated).ratio()
    return {
        "alignment_score": round(score, 6),
        "original_range": {"start": 0, "end": len(original)},
        "translated_range": {"start": 0, "end": len(translated)},
        "alignment_version": "v1",
    }
