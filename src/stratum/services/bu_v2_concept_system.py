"""P13: Concept System Extraction.

Builds the book's concept system from P12 concept trajectories with full traceability.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookConceptSystem,
    BookUnderstandingV2,
    ChapterUnderstanding,
    ConceptRole,
    ConceptSystemEntry,
)
from stratum.services.bu_v2_concept_evolution import EvolutionResult
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph


@dataclass
class ConceptSystemAnalysis:
    system: BookConceptSystem
    traceability: dict[str, list[str]]


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class ConceptSystemBuilder:
    """Build BookConceptSystem from P12 trajectories and chapter understandings."""

    def build(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        evolution: EvolutionResult | None = None,
        graph: BookReasoningGraph | None = None,
    ) -> ConceptSystemAnalysis:
        system = BookConceptSystem()
        traceability: dict[str, list[str]] = {}

        concept_info = self._collect_concept_info(bu, chapters, evolution, graph)

        for label, info in concept_info.items():
            entry = self._classify_concept(label, info, bu, chapters, evolution, graph)
            traceability[entry.concept_id] = entry.chapter_refs

            if entry.role == ConceptRole.FOUNDATIONAL:
                system.foundational.append(entry)
            elif entry.role == ConceptRole.CORE:
                system.core.append(entry)
            elif entry.role == ConceptRole.DERIVED:
                system.derived.append(entry)
            elif entry.role == ConceptRole.BRIDGING:
                system.bridging.append(entry)
            elif entry.role == ConceptRole.APPLICATION:
                system.application.append(entry)
            elif entry.role == ConceptRole.TERMINAL:
                system.terminal.append(entry)

        return ConceptSystemAnalysis(system=system, traceability=traceability)

    def _collect_concept_info(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        evolution: EvolutionResult | None,
        graph: BookReasoningGraph | None,
    ) -> dict[str, dict]:
        info: dict[str, dict] = {}

        for cu in chapters:
            for cid in cu.concepts_introduced_refs:
                if cid not in info:
                    info[cid] = {
                        "introduced_at": cu.chapter_id,
                        "definitions": [],
                        "chapters": set(),
                        "refinements": 0,
                        "applications": 0,
                        "connections": 0,
                        "supports": [],
                    }
                info[cid]["chapters"].add(cu.chapter_id)
                if cu.chapter_thesis:
                    info[cid]["definitions"].append(cu.chapter_thesis[:200])

            for cid in cu.concepts_redefined_refs:
                if cid not in info:
                    info[cid] = {
                        "introduced_at": cu.chapter_id,
                        "definitions": [],
                        "chapters": set(),
                        "refinements": 0,
                        "applications": 0,
                        "connections": 0,
                        "supports": [],
                    }
                info[cid]["chapters"].add(cu.chapter_id)
                info[cid]["refinements"] += 1

            for dep in cu.dependencies_on_prior:
                if dep in info:
                    info[dep]["supports"].append(cu.chapter_id)

        if evolution:
            for traj in evolution.trajectories:
                cid = traj.concept
                if cid not in info:
                    info[cid] = {
                        "introduced_at": traj.introduced_at,
                        "definitions": [],
                        "chapters": set(),
                        "refinements": 0,
                        "applications": 0,
                        "connections": 0,
                        "supports": [],
                    }
                info[cid]["chapters"].update(e.chapter_id for e in traj.events if e.chapter_id)
                for e in traj.events:
                    if e.event_type == "REFINEMENT":
                        info[cid]["refinements"] += 1
                    elif e.event_type == "EXPANSION":
                        info[cid]["applications"] += 1
                    elif e.event_type == "CONNECTION":
                        info[cid]["connections"] += 1

        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CONCEPT":
                    cid = node.label
                    if cid in info:
                        info[cid]["chapters"].add(node.chapter_id)

        return info

    def _classify_concept(
        self,
        label: str,
        info: dict,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        evolution: EvolutionResult | None,
        graph: BookReasoningGraph | None,
    ) -> ConceptSystemEntry:
        chapter_list = sorted(info.get("chapters", []), key=lambda x: _num(x))
        introduced_at = info.get("introduced_at", chapter_list[0] if chapter_list else "")
        refinements = info.get("refinements", 0)
        applications = info.get("applications", 0)
        connections = info.get("connections", 0)
        supports = info.get("supports", [])

        prerequisites = self._find_prerequisites(label, chapter_list, chapters, graph)
        related = self._find_related_concepts(label, info, chapters, graph)
        refined_by = self._find_refined_by(label, info, chapters)
        applied_in = self._find_applied_in(label, info, chapters)
        supports_list = self._find_supports(label, info, chapters, graph)

        role = self._determine_role(
            label,
            introduced_at,
            chapter_list,
            refinements,
            applications,
            connections,
            supports,
            chapters,
            bu,
        )

        definition = ""
        if info.get("definitions"):
            definition = info["definitions"][0]
        elif evolution:
            for traj in evolution.trajectories:
                if traj.concept == label and traj.definitions:
                    definition = traj.definitions[0]
                    break

        final_role = self._describe_final_role(role, refinements, applications, connections)

        confidence = self._compute_confidence(info, evolution, label)

        return ConceptSystemEntry(
            concept_id=_stable_id("concept", label, bu.book_id),
            label=label,
            definition=definition,
            role=role,
            prerequisites=prerequisites,
            related_concepts=related,
            refined_by=refined_by,
            applied_in=applied_in,
            supports=supports_list,
            chapter_refs=chapter_list,
            final_role=final_role,
            confidence=confidence,
        )

    def _find_prerequisites(
        self,
        label: str,
        chapter_list: list[str],
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> list[str]:
        prereqs = []
        if not chapter_list:
            return prereqs
        first_chapter = chapter_list[0]
        for cu in chapters:
            if cu.chapter_id == first_chapter:
                for dep in cu.dependencies_on_prior:
                    prereqs.append(dep)
        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CONCEPT" and node.label == label:
                    for edge in graph.in_edges(node.node_id):
                        src = graph.nodes.get(edge.source_node_id)
                        if src and src.node_type == "CONCEPT":
                            prereqs.append(src.label)
        return list(dict.fromkeys(prereqs))[:10]

    def _find_related_concepts(
        self,
        label: str,
        info: dict,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> list[str]:
        related = []
        chapter_list = info.get("chapters", set())
        for cu in chapters:
            if cu.chapter_id in chapter_list:
                for cid in cu.concepts_introduced_refs:
                    if cid != label:
                        related.append(cid)
                for cid in cu.concepts_redefined_refs:
                    if cid != label:
                        related.append(cid)
        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CONCEPT" and node.label == label:
                    for edge in graph.out_edges(node.node_id):
                        tgt = graph.nodes.get(edge.target_node_id)
                        if tgt and tgt.node_type == "CONCEPT":
                            related.append(tgt.label)
                    for edge in graph.in_edges(node.node_id):
                        src = graph.nodes.get(edge.source_node_id)
                        if src and src.node_type == "CONCEPT":
                            related.append(src.label)
        return list(dict.fromkeys(related))[:15]

    def _find_refined_by(
        self, label: str, info: dict, chapters: list[ChapterUnderstanding]
    ) -> list[str]:
        refined = []
        for cu in chapters:
            if cu.chapter_id in info.get("chapters", set()) and label in cu.concepts_redefined_refs:
                refined.append(cu.chapter_id)
        return list(dict.fromkeys(refined))[:10]

    def _find_applied_in(
        self, label: str, info: dict, chapters: list[ChapterUnderstanding]
    ) -> list[str]:
        applied = []
        for cu in chapters:
            if cu.chapter_id in info.get("chapters", set()):
                for dep in cu.dependencies_on_prior:
                    if dep == label:
                        applied.append(cu.chapter_id)
        return list(dict.fromkeys(applied))[:10]

    def _find_supports(
        self,
        label: str,
        info: dict,
        chapters: list[ChapterUnderstanding],
        graph: BookReasoningGraph | None,
    ) -> list[str]:
        supports = list(info.get("supports", []))
        if graph:
            for node in graph.nodes.values():
                if node.node_type == "CONCEPT" and node.label == label:
                    for edge in graph.out_edges(node.node_id):
                        if edge.relation_type in ("SUPPORTS", "EXPLAINS", "APPLIES_TO"):
                            tgt = graph.nodes.get(edge.target_node_id)
                            if tgt:
                                supports.append(tgt.label)
        return list(dict.fromkeys(supports))[:10]

    def _determine_role(
        self,
        label: str,
        introduced_at: str,
        chapter_list: list[str],
        refinements: int,
        applications: int,
        connections: int,
        supports: list[str],
        chapters: list[ChapterUnderstanding],
        bu: BookUnderstandingV2,
    ) -> ConceptRole:
        chapter_nums = [_num(c) for c in chapter_list]
        if not chapter_nums:
            return ConceptRole.DERIVED

        min_chapter = min(chapter_nums)
        max_chapter = max(chapter_nums)
        total_chapters = len([c for c in chapters if _num(c.chapter_id) > 0])

        if min_chapter <= total_chapters * 0.2 and (refinements > 0 or applications > 0):
            return ConceptRole.FOUNDATIONAL
        if min_chapter <= total_chapters * 0.4 and (refinements > 0 or connections > 0):
            return ConceptRole.CORE
        if applications > 0 and connections > 0:
            return ConceptRole.BRIDGING
        if applications > 0 and refinements == 0:
            return ConceptRole.APPLICATION
        if max_chapter >= total_chapters * 0.8 and refinements == 0 and applications == 0:
            return ConceptRole.TERMINAL
        return ConceptRole.DERIVED

    def _describe_final_role(
        self, role: ConceptRole, refinements: int, applications: int, connections: int
    ) -> str:
        parts = [role.value.lower()]
        if refinements > 0:
            parts.append(f"refined {refinements}x")
        if applications > 0:
            parts.append(f"applied {applications}x")
        if connections > 0:
            parts.append(f"connected {connections}x")
        return "; ".join(parts)

    def _compute_confidence(
        self, info: dict, evolution: EvolutionResult | None, label: str
    ) -> float:
        base = 0.5
        if info.get("chapters"):
            base += min(0.2, len(info["chapters"]) * 0.05)
        if info.get("refinements", 0) > 0:
            base += 0.1
        if info.get("applications", 0) > 0:
            base += 0.1
        if info.get("connections", 0) > 0:
            base += 0.05
        if evolution:
            for traj in evolution.trajectories:
                if traj.concept == label:
                    base += traj.confidence * 0.2
                    break
        return min(1.0, base)


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0
