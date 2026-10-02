"""P8 Learning Compiler (§§80-83, §87): Verified BU -> LearningGraph.

- compile_graph: Problem -> Concept(s) -> Mechanism/Argument -> Central
  Thesis -> Qualification -> Application (§81), topologically ordered.
- compile_path: Path = f(Goal, TimeBudget, Graph, Mastery, Errors) (§82) —
  never a static list. Minimum Required Learning Subgraph (§83):
  target graph - mastered - unneeded-for-goal.
- strategy_router: knowledge_type -> interaction modes (§87).
- LearningGraph persistence uses the existing stratum.learning_graphs table
  via LearningGraphRepository (no new table).
"""

from __future__ import annotations

from typing import Any, Dict, List

from stratum.knowledge.bu_v2_models import (
    InteractionType, LearningGraph, LearningGraphEdge, LearningGraphNode,
    LearningPath,
)

_STRATEGY = {
    "factual": ["recall", "discrimination", "spacing"],
    "conceptual": ["self-explanation", "example", "non-example", "comparison", "mapping"],
    "relational": ["map reconstruction", "dependency reasoning", "comparison"],
    "procedural": ["worked example", "faded example", "independent execution"],
    "rationale": ["why", "derivation", "counterfactual", "teach-back"],
    "argument": ["reconstruction", "missing-premise", "objection", "defense"],
}

_KT_TO_INTERACTION = {
    "factual": InteractionType.DEFINITION,
    "conceptual": InteractionType.EXPLAIN_WHY,
    "relational": InteractionType.RELATION_RECONSTRUCTION,
    "procedural": InteractionType.SOLVE,
    "rationale": InteractionType.EXPLAIN_WHY,
    "argument": InteractionType.ARGUMENT_RECONSTRUCTION,
}


def strategy_router(knowledge_type: str) -> List[str]:
    """§87: learning mode follows knowledge type. Unknown types fall back to
    generative self-explanation, never to a bare flashcard."""
    return _STRATEGY.get(knowledge_type, ["self-explanation", "teach-back"])


def interaction_for(knowledge_type: str) -> InteractionType:
    return _KT_TO_INTERACTION.get(knowledge_type, InteractionType.EXPLAIN_WHY)


def compile_graph(graph_id: str, bu_id: str, bu: Dict[str, Any]) -> LearningGraph:
    """§81 ordering. Nodes reference LearningObjects by deterministic ids;
    edges carry prerequisite/dependency relations."""
    nodes: List[LearningGraphNode] = []
    edges: List[LearningGraphEdge] = []

    def add(lo_ref: str) -> None:
        if lo_ref not in {n.learning_object_ref for n in nodes}:
            nodes.append(LearningGraphNode(learning_object_ref=lo_ref))

    def link(src: str, dst: str, relation: str) -> None:
        edges.append(LearningGraphEdge(source_ref=src, target_ref=dst, relation=relation))

    gov = bu.get("governing_questions", [])
    problem = f"{bu_id}::lo::problem" if gov else f"{bu_id}::lo::q0"
    add(problem)
    prev_concepts: List[str] = []
    for i, c in enumerate(bu.get("concepts", [])):
        ref = f"{bu_id}::lo::concept{i}"
        add(ref)
        link(problem, ref, "REQUIRES")
        prev_concepts.append(ref)
    mech_refs, arg_refs = [], []
    for i, _ in enumerate(bu.get("mechanisms", [])):
        ref = f"{bu_id}::lo::mech{i}"
        add(ref)
        mech_refs.append(ref)
        for c in prev_concepts:
            link(c, ref, "GROUNDS")
    for i, _ in enumerate(bu.get("major_arguments", [])):
        ref = f"{bu_id}::lo::arg{i}"
        add(ref)
        arg_refs.append(ref)
        for c in prev_concepts:
            link(c, ref, "SUPPORTS")
    thesis = f"{bu_id}::lo::thesis"
    add(thesis)
    for r in mech_refs + arg_refs:
        link(r, thesis, "ESTABLISHES")
    if not (mech_refs or arg_refs):
        for c in prev_concepts:
            link(c, thesis, "ESTABLISHES")
    qual = f"{bu_id}::lo::qualification"
    add(qual)
    link(thesis, qual, "QUALIFIES")
    app = f"{bu_id}::lo::application"
    add(app)
    link(thesis, app, "APPLIES")
    link(qual, app, "BOUNDS")
    return LearningGraph(id=graph_id, bu_id=bu_id, version=1, nodes=nodes, edges=edges)


def _prereqs(graph: LearningGraph, node: str) -> List[str]:
    return [e.source_ref for e in graph.edges if e.target_ref == node]


def minimum_subgraph(graph: LearningGraph, goal_refs: List[str],
                     mastered: List[str]) -> List[str]:
    """§83: target closure - mastered. Unneeded-for-goal nodes never enter
    via the goal closure itself."""
    needed: List[str] = []
    stack = list(goal_refs)
    while stack:
        node = stack.pop()
        if node in needed or node in mastered:
            continue
        needed.append(node)
        stack.extend(_prereqs(graph, node))
    # Prerequisite-first order.
    order = {n.learning_object_ref: i for i, n in enumerate(graph.nodes)}
    return sorted(needed, key=lambda n: order.get(n, 0))


def compile_path(path_id: str, bu_id: str, graph_id: str, goal: str,
                 goal_refs: List[str], time_budget_min: int,
                 graph: LearningGraph, mastered: List[str],
                 error_history: List[str] | None = None) -> LearningPath:
    """§82: path computed from live inputs, not stored statically."""
    errors = error_history or []
    ordered = minimum_subgraph(graph, goal_refs, mastered)
    # Errors re-insert their prerequisite chains first (repair priority).
    for err in errors:
        if err not in ordered:
            ordered = minimum_subgraph(graph, [err], mastered) + ordered
    # Time budget trims from the tail (advanced/application material last).
    per_item = 8
    capacity = max(1, time_budget_min // per_item) if time_budget_min > 0 else len(ordered)
    trimmed = ordered[:capacity]
    return LearningPath(
        id=path_id, bu_id=bu_id, graph_id=graph_id, goal=goal,
        time_budget_min=time_budget_min, ordered_lo_refs=trimmed,
        rationale=(f"minimum subgraph for goal ({len(ordered)} items, "
                   f"{len(mastered)} mastered skipped, "
                   f"budget keeps {len(trimmed)})"))
