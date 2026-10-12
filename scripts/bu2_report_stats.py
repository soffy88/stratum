"""Pull the before/after comparison numbers for a BU2 run (task H)."""

from __future__ import annotations
import json
import sys

sys.path.insert(0, "src")


def stats(run_id: str) -> dict:
    from stratum.db import query

    out: dict = {"run_id": run_id}
    cu = query(
        "SELECT chapter_id, array_length(concepts_introduced_refs,1) nc, "
        "chapter_thesis, array_length(supporting_ku_refs,1) nev, array_length(major_ku_refs,1) nku "
        "FROM chapter_understandings WHERE run_id=%(r)s ORDER BY chapter_id",
        {"r": run_id},
    )
    out["chapters"] = len(cu)
    out["chapter_ids"] = [x["chapter_id"] for x in cu]
    out["total_concepts"] = sum((x["nc"] or 0) for x in cu)
    out["empty_chapters"] = [x["chapter_id"] for x in cu if not x["nc"]]
    out["per_chapter_concepts"] = {x["chapter_id"]: (x["nc"] or 0) for x in cu}
    g = query(
        "SELECT id,node_count,edge_count,unresolved_count,mean_confidence FROM book_reasoning_graph WHERE run_id=%(r)s",
        {"r": run_id},
    )
    if g:
        gid = g[0]["id"]
        nodes = query(
            "SELECT node_type, count(*) c FROM reasoning_node WHERE graph_id=%(g)s GROUP BY node_type",
            {"g": gid},
        )
        out["graph"] = {
            "nodes_by_type": {n["node_type"]: n["c"] for n in nodes},
            "node_count": g[0]["node_count"],
            "edge_count": g[0]["edge_count"],
            "unresolved": g[0]["unresolved_count"],
        }
    bu = query(
        "SELECT governing_questions_json,central_theses_json,concept_evolution_json FROM book_understandings_v2 WHERE run_id=%(r)s ORDER BY version DESC LIMIT 1",
        {"r": run_id},
    )
    if bu:
        out["governing_questions"] = bu[0]["governing_questions_json"]
        out["central_theses"] = bu[0]["central_theses_json"]
        ce = bu[0]["concept_evolution_json"] or []
        out["concept_evolution_count"] = len(ce)
        # count placeholder definitions
        ph = sum(
            1 for s in ce if str(s.get("definition", "")).startswith("introduced or redefined")
        )
        out["concept_evolution_placeholders"] = ph
    gates = query(
        "SELECT gate_name,status,score FROM bu2_p13_quality_gates WHERE run_id=%(r)s ORDER BY gate_number",
        {"r": run_id},
    )
    out["gates"] = [
        {"gate": x["gate_name"], "status": x["status"], "score": x["score"]} for x in gates
    ]
    return out


if __name__ == "__main__":
    print(json.dumps(stats(sys.argv[1]), indent=2, ensure_ascii=False, default=str))
