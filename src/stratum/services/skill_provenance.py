"""Skill provenance tracking for AII.

Skill is a projection, never authority. Every persisted skill must carry
canonical refs so that a correction on the canonical layer can mark it stale.

This module is deliberately thin — it does not add a new table, it uses
existing metadata on bu_onto / exported package.

Usage:
  check_skill_stale(skill_meta, canonical_updated_at_map) -> bool
  build_skill_manifest(skill_id, concept_refs, claim_refs, evidence_refs) -> dict
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_skill_manifest(
    skill_id: str,
    version: str,
    concept_refs: list[str] | None = None,
    claim_refs: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    source_refs: list[str] | None = None,
    generator_version: str = "unknown",
) -> dict[str, Any]:
    return {
        "skill_id": skill_id,
        "version": version,
        "concept_refs": concept_refs or [],
        "claim_refs": claim_refs or [],
        "evidence_refs": evidence_refs or [],
        "source_refs": source_refs or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": generator_version,
    }


def is_skill_stale(
    skill_manifest: dict[str, Any],
    canonical_updated_at: dict[str, str],
) -> bool:
    """Return True if any canonical ref has been updated after skill generation.

    canonical_updated_at: {canonical_id: iso_timestamp}
    skill_manifest must contain generated_at and ref lists.
    """
    gen_at_str = skill_manifest.get("generated_at")
    if not gen_at_str:
        return False
    try:
        gen_at = datetime.fromisoformat(gen_at_str)
    except Exception:
        return False

    refs: list[str] = []
    for key in ("concept_refs", "claim_refs", "evidence_refs", "source_refs"):
        refs.extend(skill_manifest.get(key) or [])

    for ref in refs:
        ts_str = canonical_updated_at.get(ref)
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts > gen_at:
                return True
        except Exception:
            continue
    return False
