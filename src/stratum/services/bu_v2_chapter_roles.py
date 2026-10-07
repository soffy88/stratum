"""P13: Chapter Role Assignment.

Assigns structural roles to each chapter based on content and position.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookChapterRoles,
    BookUnderstandingV2,
    ChapterRole,
    ChapterRoleAssignment,
    ChapterUnderstanding,
)


@dataclass
class ChapterRolesAnalysis:
    roles: BookChapterRoles
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class ChapterRoleAnalyzer:
    """Assign structural roles to chapters."""

    def analyze(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        structure: dict[str, Any] | None = None,
    ) -> ChapterRolesAnalysis:
        roles = BookChapterRoles()
        traceability: dict[str, list[str]] = {}

        numbered_chapters = [c for c in chapters if _num(c.chapter_id) > 0]
        numbered_chapters.sort(key=lambda c: _num(c.chapter_id))
        total = len(numbered_chapters)

        for i, cu in enumerate(numbered_chapters):
            role_list = self._determine_roles(cu, i, total, numbered_chapters, bu)
            evidence = self._build_evidence(cu, role_list, i, total)
            confidence = self._compute_confidence(cu, role_list, i, total)

            assignment = ChapterRoleAssignment(
                chapter_id=cu.chapter_id,
                roles=role_list,
                evidence=evidence,
                confidence=confidence,
            )
            roles.assignments.append(assignment)
            traceability[cu.chapter_id] = [evidence]

        return ChapterRolesAnalysis(roles=roles, traceability=traceability)

    def _determine_roles(
        self,
        cu: ChapterUnderstanding,
        index: int,
        total: int,
        all_chapters: list[ChapterUnderstanding],
        bu: BookUnderstandingV2,
    ) -> list[ChapterRole]:
        roles = []
        position = index / max(1, total - 1) if total > 1 else 0.5

        if position <= 0.15:
            roles.append(ChapterRole.FOUNDATION)
        elif position <= 0.3:
            roles.append(ChapterRole.DEFINITION)

        has_definitions = len(cu.concepts_introduced_refs) > 2
        has_redefinitions = len(cu.concepts_redefined_refs) > 0
        has_mechanisms = len(cu.mechanisms_refs) > 0
        has_arguments = len(cu.arguments_refs) > 0
        has_evidence = len(cu.evidence_program) > 0
        has_applications = any("application" in dep.lower() or "example" in dep.lower() for dep in cu.dependencies_on_prior)
        has_counterpoint = len(cu.qualifications) > 0 or len(cu.assumptions) > 1
        is_synthesis = position >= 0.85

        if has_definitions and position < 0.4:
            roles.append(ChapterRole.DEFINITION)
        elif has_redefinitions:
            roles.append(ChapterRole.DEVELOPMENT)
        elif has_mechanisms and has_arguments:
            roles.append(ChapterRole.ARGUMENT)
        elif has_evidence and not has_arguments:
            roles.append(ChapterRole.EVIDENCE)
        elif has_applications:
            roles.append(ChapterRole.APPLICATION)
        elif has_counterpoint:
            roles.append(ChapterRole.COUNTERPOINT)
        elif is_synthesis:
            roles.append(ChapterRole.SYNTHESIS)
        elif index == total - 1:
            roles.append(ChapterRole.CONCLUSION)
        elif index > 0 and index < total - 1:
            roles.append(ChapterRole.BRIDGE)

        if not roles:
            roles.append(ChapterRole.DEVELOPMENT)

        seen = set()
        unique_roles = []
        for r in roles:
            if r not in seen:
                seen.add(r)
                unique_roles.append(r)
        return unique_roles

    def _build_evidence(self, cu: ChapterUnderstanding, roles: list[ChapterRole], index: int, total: int) -> str:
        parts = []
        pos_desc = "early" if index < total * 0.3 else ("middle" if index < total * 0.7 else "late")
        parts.append(f"position: {pos_desc} ({index+1}/{total})")
        if ChapterRole.FOUNDATION in roles:
            parts.append(f"introduces {len(cu.concepts_introduced_refs)} concepts")
        if ChapterRole.DEFINITION in roles:
            parts.append(f"defines core concepts: {', '.join(cu.concepts_introduced_refs[:3])}")
        if ChapterRole.ARGUMENT in roles:
            parts.append(f"presents {len(cu.arguments_refs)} arguments with {len(cu.mechanisms_refs)} mechanisms")
        if ChapterRole.EVIDENCE in roles:
            parts.append(f"provides {len(cu.evidence_program)} evidence items")
        if ChapterRole.APPLICATION in roles:
            parts.append("applies prior concepts to new problems")
        if ChapterRole.COUNTERPOINT in roles:
            parts.append(f"qualifies prior claims: {len(cu.qualifications)} qualifications")
        if ChapterRole.SYNTHESIS in roles:
            parts.append("synthesizes book-level results")
        if ChapterRole.CONCLUSION in roles:
            parts.append("concludes the book's argument")
        if ChapterRole.BRIDGE in roles:
            parts.append(f"connects to: {', '.join(cu.dependencies_on_prior[:3])}")
        return "; ".join(parts)

    def _compute_confidence(self, cu: ChapterUnderstanding, roles: list[ChapterRole], index: int, total: int) -> float:
        base = 0.5
        signals = 0
        if index < total * 0.2 and ChapterRole.FOUNDATION in roles:
            signals += 1
        if len(cu.concepts_introduced_refs) > 3 and ChapterRole.DEFINITION in roles:
            signals += 1
        if len(cu.arguments_refs) > 1 and ChapterRole.ARGUMENT in roles:
            signals += 1
        if len(cu.evidence_program) > 2 and ChapterRole.EVIDENCE in roles:
            signals += 1
        if ChapterRole.SYNTHESIS in roles and index >= total - 2:
            signals += 1
        if ChapterRole.CONCLUSION in roles and index == total - 1:
            signals += 1
        return min(1.0, base + signals * 0.1)


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0