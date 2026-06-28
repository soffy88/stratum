"""Prove the concurrent wrapper is logic-equivalent to serial oskill.ontology_extract.

Part A (deterministic mock LLM): identical mock fed to serial vs concurrent -> KU/edge/concept
sets must be IDENTICAL (after normalizing the global-vs-local id suffix). This isolates the
ORCHESTRATION from LLM stochasticity and proves concurrency changes only WHEN, not WHAT.

Part B (real flash, small text): serial vs concurrent timing + comparable KU counts/types.
"""
import asyncio, hashlib, json, re, time, os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

from aii.service import onto_prompts as P
from aii.service import onto_vocab as V
from oskill import ontology_extract
from aii.service.onto_extract_concurrent import ontology_extract_concurrent

PROMPTS = dict(
    pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
    pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
    pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL, pass2_system=P.PASS2_SYSTEM,
    valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES, valid_sub_types=V.VALID_SUB_TYPES,
    valid_relation_types=V.VALID_RELATION_TYPES, doc_type="textbook", source_credibility="high",
)

TEXT = ". ".join(f"Sentence {i} about economics concept number {i} explaining cause {i}"
                 for i in range(120)) + "."


def _mock_llm():
    """Deterministic async LLM: pure function of (system, user content). Same input -> same output."""
    async def llm(messages=None, *, system="", max_tokens=4096, **_):
        user = ""
        for m in (messages or []):
            if m.get("role") == "user":
                user = m.get("content", "")
        if "knowledge analyst" in system:           # pass1 chunk
            out = {"concepts": ["c"], "topics": ["t"], "chapter": "ch"}
        elif "knowledge architect" in system:        # outline
            out = {"chapters": ["ch"], "core_concepts": ["c"], "main_thread": "m"}
        else:                                         # pass2 chunk -> deterministic KUs from chunk text
            mt = re.search(r"Text chunk:\s*(.*)", user, re.DOTALL)
            chunk = (mt.group(1) if mt else user)[:400]
            h = hashlib.md5(chunk.encode()).hexdigest()[:6]
            n = 1 + (int(h, 16) % 3)                  # 1..3 KUs, deterministic per chunk
            kus = [{"id": f"temp_{h}_{k}", "title": f"T{h}{k}", "content": f"KU {h} #{k}",
                    "knowledge_type": ["conceptual", "rationale", "factual"][k % 3],
                    "sub_type": None, "concepts": [f"concept_{h}"]} for k in range(n)]
            edges = [{"source": f"temp_{h}_0", "target": f"temp_{h}_1", "relation_type": "explains"}] if n > 1 else []
            out = {"ku_candidates": kus, "edge_candidates": edges, "concept_candidates": [f"concept_{h}"]}
        await asyncio.sleep(0)  # yield, let gather interleave
        return {"content": [{"type": "text", "text": json.dumps(out)}]}
    return llm


def _norm_kus(result):
    """Normalize away global-vs-local id suffix: key by (chunk_idx, content, ktype)."""
    out = set()
    for ku in result.ku_candidates:
        m = re.match(r"ku_c(\d+)_", ku["id"])
        out.add((m.group(1) if m else "?", ku["content"], ku["knowledge_type"]))
    return out


def _norm_edges(result):
    out = set()
    for e in result.edge_candidates:
        sc = re.match(r"ku_c(\d+)_", e["source"]); dc = re.match(r"ku_c(\d+)_", e["target"])
        out.add((sc.group(1) if sc else e["source"], dc.group(1) if dc else e["target"], e["relation_type"]))
    return out


async def main():
    print("=== Part A: deterministic mock (orchestration equivalence) ===")
    mock = _mock_llm()
    serial = await ontology_extract(source_text=TEXT, llm=mock, **PROMPTS)
    conc = await ontology_extract_concurrent(source_text=TEXT, llm=mock, chunk_concurrency=10, **PROMPTS)
    print(f"serial   : KU={len(serial.ku_candidates)} edges={len(serial.edge_candidates)} concepts={len(serial.concept_candidates)} by_type={serial.stats['by_type']}")
    print(f"concurrent: KU={len(conc.ku_candidates)} edges={len(conc.edge_candidates)} concepts={len(conc.concept_candidates)} by_type={conc.stats['by_type']}")
    ku_eq = _norm_kus(serial) == _norm_kus(conc)
    edge_eq = _norm_edges(serial) == _norm_edges(conc)
    concept_eq = set(serial.concept_candidates) == set(conc.concept_candidates)
    type_eq = serial.stats["by_type"] == conc.stats["by_type"]
    print(f"KU set identical: {ku_eq} | edge set identical: {edge_eq} | concept set identical: {concept_eq} | by_type identical: {type_eq}")
    print("RESULT:", "✓ ORCHESTRATION EQUIVALENT" if (ku_eq and edge_eq and concept_eq and type_eq) else "✗ DIVERGENCE")

    print("\n=== Part B: real flash (timing + comparable quality) ===")
    from aii.api._provider import register_providers
    from obase import ProviderRegistry
    register_providers()
    real = ProviderRegistry.get().llm("default")
    t = time.time(); s = await ontology_extract(source_text=TEXT, llm=real, **PROMPTS); ts = time.time() - t
    t = time.time(); c = await ontology_extract_concurrent(source_text=TEXT, llm=real, chunk_concurrency=10, **PROMPTS); tc = time.time() - t
    print(f"serial    : {ts:.1f}s  KU={len(s.ku_candidates)} by_type={s.stats['by_type']}")
    print(f"concurrent: {tc:.1f}s  KU={len(c.ku_candidates)} by_type={c.stats['by_type']}")
    print(f"speedup: {ts/tc:.1f}x  (LLM stochastic -> counts/types comparable, not bit-identical)")


if __name__ == "__main__":
    asyncio.run(main())
