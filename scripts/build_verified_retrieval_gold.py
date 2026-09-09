"""Build deterministic verified retrieval gold from canonical PostgreSQL rows.

The target is selected first from a canonical source/fragment/provenance row;
the query is then derived from that target.  This intentionally leaves the
historical random candidate file untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import psycopg2

OWNER = "56d6bc01edc35765"
DB = dict(host="127.0.0.1", port=5435, user="aii", password="aii_safe_pass", dbname="aii_kg")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", " ")).strip()


def _query_id(kind: str, basis: str) -> str:
    return f"{kind}-{hashlib.sha256(basis.encode()).hexdigest()[:16]}"


def _load_source_ids(path: Path | None) -> list[str]:
    if not path:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("substrate_ids", [])
    return [str(item) for item in payload]


def _unique_phrase(source_id: str, chunks: list[dict], all_chunks: list[dict]) -> tuple[str, str] | None:
    corpus = [(_clean(row["text"]), row["id"], row["substrate_id"]) for row in all_chunks]
    local = [row for row in chunks if row["text"]]
    for chunk in local:
        text = _clean(chunk["text"])
        if len(text) < 18:
            continue
        if re.search(r"[\u3400-\u9fff]", text):
            candidates = [text[i : i + 28] for i in range(0, min(len(text) - 27, 100), 5)]
        else:
            words = text.split()
            candidates = [" ".join(words[i : i + 7]) for i in range(max(0, len(words) - 6))]
        for phrase in candidates:
            phrase = _clean(phrase).strip("#*-|` ")
            if len(phrase) < 18:
                continue
            matches = {sid for body, _, sid in corpus if phrase.lower() in body.lower()}
            if matches == {source_id}:
                return phrase, chunk["id"]
    return None


def build(source_ids: list[str]) -> list[dict]:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.user_id, s.title, s.source_path, s.file_hash,
               COALESCE((SELECT d.content FROM stratum.derivative d
                         WHERE d.substrate_id=s.id AND d.kind='markdown'
                         ORDER BY length(d.content) DESC LIMIT 1), '') AS content
        FROM stratum.substrates s
        WHERE s.id = ANY(%s) AND length(COALESCE(s.title,'')) > 0
        ORDER BY s.id
        """,
        (source_ids,),
    )
    sources = {row[0]: row for row in cur.fetchall()}
    cur.execute(
        """
        SELECT id, substrate_id, chunk_idx, text
        FROM stratum.substrate_chunk
        WHERE substrate_id = ANY(%s)
        ORDER BY substrate_id, chunk_idx
        """,
        (list(sources),),
    )
    chunks = [dict(id=r[0], substrate_id=r[1], chunk_idx=r[2], text=r[3] or "") for r in cur.fetchall()]
    chunks_by_source: dict[str, list[dict]] = defaultdict(list)
    for row in chunks:
        chunks_by_source[row["substrate_id"]].append(row)

    # Provenance-backed records are pulled from canonical Claim -> Evidence -> Source rows.
    cur.execute(
        """
        SELECT kc.id, kc.statement, kc.user_id, ce.evidence_id, e.substrate_id
        FROM stratum.knowledge_claims kc
        JOIN stratum.claim_evidence ce ON ce.claim_id=kc.id
        JOIN stratum.evidence e ON e.id=ce.evidence_id
        WHERE kc.deleted_at IS NULL AND length(COALESCE(kc.statement,'')) > 0
        ORDER BY kc.id, ce.evidence_id
        """
    )
    claim_rows = cur.fetchall()
    claims: dict[str, dict] = {}
    for claim_id, statement, user_id, evidence_id, substrate_id in claim_rows:
        entry = claims.setdefault(
            claim_id,
            {"statement": statement, "user_id": user_id, "evidence_ids": [], "source_ids": []},
        )
        entry["evidence_ids"].append(evidence_id)
        entry["source_ids"].append(substrate_id)

    cur.execute(
        """
        SELECT id, name, user_id, substrate_refs
        FROM stratum.concepts
        WHERE substrate_refs IS NOT NULL AND cardinality(substrate_refs) > 0
        ORDER BY id
        """
    )
    concepts = cur.fetchall()
    cur.close()
    conn.close()

    records: list[dict] = []
    # Exact-source records: title is the deterministic source key.
    for sid, row in sources.items():
        title = _clean(row[2])
        fragment_ids = [item["id"] for item in chunks_by_source.get(sid, [])]
        records.append(
            {
                "query_id": _query_id("exact-source", sid),
                "query": title,
                "gold_type": "exact-source",
                "expected_source_ids": [sid],
                "expected_fragment_ids": fragment_ids,
                "evidence_ids": [],
                "verification_basis": f"canonical_substrate_title:{sid}",
                "review_status": "verified",
                "reviewer": "codex-final-quality",
                "user_id": row[1],
                "source_ref": row[3] or row[4] or sid,
                "relevant_substrate_ids": [sid],
            }
        )

    # Two rare, source-unique fragment phrases per parser source where possible.
    for sid in sources:
        used: set[str] = set()
        for _ in range(2):
            candidate = _unique_phrase(sid, chunks_by_source.get(sid, []), chunks)
            if not candidate or candidate[0] in used:
                break
            phrase, fragment_id = candidate
            used.add(phrase)
            records.append(
                {
                    "query_id": _query_id("rare-phrase", f"{sid}:{phrase}"),
                    "query": phrase,
                    "gold_type": "rare phrase",
                    "expected_source_ids": [sid],
                    "expected_fragment_ids": [fragment_id],
                    "evidence_ids": [],
                    "verification_basis": f"canonical_fragment_exact_phrase:{fragment_id}",
                    "review_status": "verified",
                    "reviewer": "codex-final-quality",
                    "user_id": sources[sid][1],
                    "source_ref": sources[sid][3] or sources[sid][4] or sid,
                    "relevant_substrate_ids": [sid],
                }
            )

    # Claim-backed records.  Prefer multi-source provenance for synthesis cases.
    for claim_id, claim in claims.items():
        source_set = list(dict.fromkeys(claim["source_ids"]))
        # Claims may point at older canonical sources not in the parser batch;
        # they remain valid provenance gold and are evaluated as-is.
        kind = "cross-source synthesis" if len(source_set) >= 2 else "claim question"
        records.append(
            {
                "query_id": _query_id(kind, claim_id),
                "query": f"What does the canonical record establish about: {_clean(claim['statement'])}?",
                "gold_type": kind,
                "expected_source_ids": source_set,
                "expected_fragment_ids": [],
                "evidence_ids": list(dict.fromkeys(claim["evidence_ids"])),
                "verification_basis": f"canonical_claim_evidence:{claim_id}",
                "review_status": "verified",
                "reviewer": "codex-final-quality",
                "user_id": claim["user_id"] or OWNER,
                "source_ref": f"claim:{claim_id}",
                "relevant_substrate_ids": source_set,
            }
        )

    # Concept-backed records use the concept's explicit substrate_refs.
    for concept_id, name, user_id, refs in concepts:
        refs = list(refs or [])
        records.append(
            {
                "query_id": _query_id("concept", concept_id),
                "query": f"Where is the canonical concept {name} evidenced?",
                "gold_type": "concept lookup",
                "expected_source_ids": refs,
                "expected_fragment_ids": [],
                "evidence_ids": [],
                "verification_basis": f"canonical_concept_substrate_refs:{concept_id}",
                "review_status": "verified",
                "reviewer": "codex-final-quality",
                "user_id": user_id or OWNER,
                "source_ref": f"concept:{concept_id}",
                "relevant_substrate_ids": refs,
            }
        )

    # Keep all deterministic source/phrase/concept types, then fill the
    # remaining quota with provenance-backed claims.  Sorting the whole pool
    # first would let the synthetic claim IDs crowd out the required gold
    # categories.
    preferred = [
        item
        for item in records
        if item["gold_type"] in {"exact-source", "rare phrase", "concept lookup", "cross-source synthesis"}
    ]
    claim_records = [item for item in records if item["gold_type"] == "claim question"]
    preferred.sort(key=lambda item: item["query_id"])
    claim_records.sort(key=lambda item: item["query_id"])
    records = (preferred + claim_records)[:100]
    if len(records) < 100:
        raise RuntimeError(f"verified gold construction produced only {len(records)} records")
    return records[:100]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-ids", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = build(_load_source_ids(args.source_ids))
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = defaultdict(int)
    for record in records:
        counts[record["gold_type"]] += 1
    print(json.dumps({"verified": len(records), "types": dict(counts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
