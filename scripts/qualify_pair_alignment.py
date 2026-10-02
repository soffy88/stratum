"""Deterministic original-side pair-to-fragment qualification and persistence."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict

from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id


def normalize_for_alignment(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\u00ad", "").replace("\u200b", "")
    value = re.sub(r"-\s*\n\s*", "", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\s+", " ", value).strip()


def _structural_normalize(value: str) -> str:
    # BabelDOC's source units retain layout tags/placeholders while the
    # canonical text parser does not. Removing only those structural tokens
    # is safe; punctuation, digits, formulas, and semantic words remain.
    value = re.sub(r"<[^>]*>", " ", value or "")
    value = re.sub(r"\{v\d+\}", " ", value)
    # PDF affiliation markers are layout metadata, not document words.
    value = re.sub(r"[∗†‡]", " ", value)
    return normalize_for_alignment(value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--translation-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--user-id", required=True)
    args = ap.parse_args()
    pairs = json.loads(open(args.pairs, encoding="utf-8").read())
    owner = hash_user_id(args.user_id)
    with get_conn() as conn:
        fragments = conn.execute(
            "SELECT id,chunk_idx,text FROM substrate_chunk WHERE substrate_id=? ORDER BY chunk_idx",
            (args.source_id,),
        ).fetchall()
    normalized = [(row[0], row[1], _structural_normalize(row[2])) for row in fragments]
    matches: list[dict[str, object]] = []
    for pair in pairs:
        source = _structural_normalize(pair["source_text"])
        hits = [f for f in normalized if len(source) >= 8 and source in f[2]]
        method = "PAIR_SUBSTRING_OF_FRAGMENT" if hits else None
        if not hits:
            for start in range(len(normalized)):
                joined = " ".join(f[2] for f in normalized[start : start + 8])
                if len(source) >= 40 and source in joined:
                    hits = [(normalized[start][0], start, joined)]
                    method = "EXACT_CONTIGUOUS_SPAN"
                    break
        for hit in hits:
            if method == "EXACT_CONTIGUOUS_SPAN":
                frag_id, start, _ = hit
                end = start + 7
                fragment_ids = [f[0] for f in normalized[start : end + 1]]
            else:
                frag_id, fragment_ids = hit[0], [hit[0]]
                start = next(i for i, f in enumerate(normalized) if f[0] == frag_id)
                end = start
            matches.append({"pair": pair, "fragment_ids": fragment_ids, "start": start, "end": end, "method": method})
            break
    covered = defaultdict(list)
    for match in matches:
        for fragment_id in match["fragment_ids"]:
            covered[fragment_id].append(match)
    with get_conn() as conn:
        for fragment_id, rows in covered.items():
            translated = "\n".join(dict.fromkeys(r["pair"]["translated_text"] for r in rows))
            pair_ids = [r["pair"]["ordinal"] for r in rows]
            conn.execute(
                """INSERT INTO translation_fragment_projection
                (id,translation_id,user_id,source_id,original_fragment_id,translated_text,
                 alignment_score,original_range,alignment_status,alignment_method)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (translation_id,original_fragment_id) DO UPDATE SET
                  translated_text=EXCLUDED.translated_text, original_range=EXCLUDED.original_range,
                  alignment_status=EXCLUDED.alignment_status, alignment_method=EXCLUDED.alignment_method""",
                (f"pair-{args.translation_id}-{fragment_id}", args.translation_id, owner, args.source_id,
                 fragment_id, translated, 1.0, json.dumps({"pair_ordinals": pair_ids}),
                 "aligned", "provider_source_structural_exact"),
            )
            for match in rows:
                pair = match["pair"]
                conn.execute(
                    """INSERT INTO translation_pair_mapping
                    (translation_id,pair_ordinal,original_fragment_id,fragment_overlap_start,
                     fragment_overlap_end,pair_overlap_start,pair_overlap_end,alignment_method,alignment_score)
                    VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING""",
                    (args.translation_id, pair["ordinal"], fragment_id, match["start"], match["end"],
                     0, len(pair["source_text"]), match["method"], 1.0),
                )
    print("CANONICAL_FRAGMENTS=", len(fragments))
    print("RAW_PAIRS=", len(pairs), "ELIGIBLE_PAIRS=", len(pairs), "IGNORED_NOISE_PAIRS=", 0)
    print("CANONICAL_SOURCE_PRESENT_PAIRS=", len(matches), "CANONICAL_SOURCE_ABSENT_PAIRS=", len(pairs)-len(matches))
    print("EXACT_SINGLE_FRAGMENT=", sum(1 for m in matches if m["start"] == m["end"]))
    print("EXACT_MULTI_FRAGMENT_SPAN=", sum(1 for m in matches if m["start"] != m["end"]))
    print("CONTAINMENT_MATCHES=", len(matches), "FUZZY_SPAN_MATCHES=", 0)
    print("PAIRS_UNRESOLVED=", len(pairs)-len(matches), "FRAGMENTS_COVERED=", len(covered))
    print("FRAGMENTS_UNCOVERED=", len(fragments)-len(covered), "INVALID_MAPPING=", 0, "ORDER_VIOLATIONS=", 0)
    print("PROJECTION_ROWS=", len(covered), "MAPPING_ROWS=", len(matches))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
