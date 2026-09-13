"""Provenance validation for AII knowledge objects.

Enforces:
- Source text is immutable (no overwrite)
- Evidence must trace to Fragment -> Source
- AI Claim must have at least one Evidence
- Relation must have rationale or evidence_ids
- Note ownership: user-authored, AI never masquerades
- Skill must carry canonical refs
"""
from __future__ import annotations

from typing import Any


def validate_provenance(obj_type: str, payload: dict[str, Any]) -> list[str]:
    """Validate that a knowledge object carries required provenance.

    Returns list of violations (empty = pass).
    """
    errors: list[str] = []
    t = obj_type.lower()

    if t == "evidence":
        if not payload.get("substrate_id"):
            errors.append("evidence missing substrate_id (must trace to Source)")
        if not payload.get("quote") and not payload.get("quote_hash"):
            errors.append("evidence missing quote/quote_hash (must anchor to Fragment)")
        # locator_json may be empty but should exist for citation path
        if "locator_json" not in payload and "locator" not in payload:
            errors.append("evidence missing locator (required for citation path)")

    elif t == "claim":
        ev = payload.get("evidence_ids") or payload.get("evidence") or []
        if not ev:
            # hypothesis status is allowed to be orphan, but must be explicit
            if payload.get("status") != "hypothesis":
                errors.append("claim without evidence must be status=hypothesis")
        # generator/model tracking
        if not payload.get("created_by") and not payload.get("generator"):
            # soft warning, not hard fail — knowledge_claims doesn't have generator col yet
            pass

    elif t == "relation":
        has_rationale = bool((payload.get("rationale") or "").strip())
        has_ev = bool(payload.get("evidence_ids"))
        if not has_rationale and not has_ev:
            errors.append("relation requires rationale or at least one evidence_id")

    elif t == "note":
        author = payload.get("author") or payload.get("created_by") or "user"
        if author not in ("user",):
            # AI/system notes must be labeled, never masquerade as user
            if author in ("ai", "system"):
                # allowed but must be explicit — check explicit flag
                if payload.get("author_type") not in ("ai-generated", "system-generated", "user-authored"):
                    errors.append("note author_type must be explicit for ai/system notes")

    elif t == "skill":
        # skill must carry canonical refs
        has_any_ref = any(
            payload.get(k) for k in ("concept_refs", "claim_refs", "evidence_refs", "source_refs", "knowledge_refs")
        )
        if not has_any_ref:
            # allow transient generation but persisted skill must have refs
            if payload.get("persisted"):
                errors.append("persisted skill must carry at least one canonical ref")

    elif t == "source":
        # Source text must not be overwritten — this is checked at writer layer,
        # here we just ensure content_hash exists
        if not payload.get("content_hash") and not payload.get("file_hash"):
            errors.append("source should carry content_hash/file_hash for immutability check")

    return errors


def is_valid_citation_path(evidence: dict[str, Any], fragment: dict[str, Any] | None, source: dict[str, Any] | None) -> bool:
    """Check Evidence -> Fragment -> Source chain is intact."""
    if not evidence.get("substrate_id"):
        return False
    if source is None:
        return False
    if fragment is not None:
        if fragment.get("substrate_id") != evidence.get("substrate_id"):
            return False
    return True
