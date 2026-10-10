from stratum.services.bu_v2_crossbook_evidence import BU2CrossBookEvidenceComparator


def _entry(cid: str) -> dict:
    return {
        "evidence_id": cid,
        "claim_id": cid,
        "claim_statement": "the limit of a function at a point",
        "evidence_ids": [],
        "evidence_strengths": {},
        "argument_ids": [],
        "chapter_ids": ["ch1"],
        "is_supported": True,
        "provenance": [],
    }


def test_empty_evidence_ids_do_not_crash_alignment():
    cmp = BU2CrossBookEvidenceComparator()
    cmp._align_evidence_pairs(["a", "b"], {"a": [_entry("c1")], "b": [_entry("c2")]})
