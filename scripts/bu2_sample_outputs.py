"""Print 3 sample outputs (thesis + concepts + an evidence quote) for a run."""

from __future__ import annotations
import json
import sys

sys.path.insert(0, "src")


def samples(run_id: str, chapter_ids: list[str]) -> dict:
    from stratum.db import query

    out = {}
    for cid in chapter_ids:
        rows = query(
            "SELECT chapter_thesis, concepts_introduced_refs, evidence_program_json, "
            "concept_definitions FROM chapter_understandings WHERE run_id=%(r)s AND chapter_id=%(c)s",
            {"r": run_id, "c": cid},
        )
        if not rows:
            continue
        r = rows[0]
        prog = r["evidence_program_json"] or []
        refs = []
        for ep in prog[:2]:
            refs.extend(ep.get("evidence_refs", []))
        out[cid] = {
            "thesis": r["chapter_thesis"],
            "concepts": (r["concepts_introduced_refs"] or [])[:10],
            "n_concepts": len(r["concepts_introduced_refs"] or []),
            "sample_claims": [ep.get("claim_ref") for ep in prog[:2]],
        }
    return out


if __name__ == "__main__":
    run_id = sys.argv[1]
    cids = sys.argv[2].split(",")
    print(json.dumps(samples(run_id, cids), indent=2, ensure_ascii=False))
