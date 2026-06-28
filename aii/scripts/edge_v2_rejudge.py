"""v2 验证: 收紧 judge 重判 ch3 现有 643 边(judge 只能剪不能加 → v2⊆643), 看 over-link 降否+不误杀."""
import asyncio, os, re, json
from pathlib import Path
from collections import Counter, defaultdict
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / "aii" / ".env", override=True)
import asyncpg
from aii.api._provider import register_providers
from aii.service.chapter_edges import judge_pairs_v2, topk_cap
from obase import ProviderRegistry
SUB = "microecon_en_ch3"
SC = "/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad"


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    edges = await c.fetch(f"""
      SELECT e.src_id s, e.dst_id d, e.relation_type rel, ka.natural_text sa, kb.natural_text sb,
             COALESCE(co.strength,'none') strength, COALESCE(co.shared_concept_count,0) shared, COALESCE(co.semantic_sim,0) sim
      FROM aii.edge_onto e JOIN aii.ku_onto ka ON e.src_id=ka.ku_id JOIN aii.ku_onto kb ON e.dst_id=kb.ku_id
      LEFT JOIN aii.ku_cooccurrence co ON co.substrate_id='{SUB}' AND co.ku_a=LEAST(e.src_id,e.dst_id) AND co.ku_b=GREATEST(e.src_id,e.dst_id)
      WHERE e.substrate_id='{SUB}'""")
    await c.close()
    texts = {}
    for e in edges:
        texts[e["s"]] = e["sa"]; texts[e["d"]] = e["sb"]
    pairs = [(e["s"], e["d"]) for e in edges]
    orig_rel = {(e["s"], e["d"]): e["rel"] for e in edges}
    print(f"re-judging {len(pairs)} existing edges with STRICT v2 judge...", flush=True)
    survivors = await judge_pairs_v2(llm, pairs, texts, concurrency=10)
    surv_set = {(s, d) for s, d, _ in survivors}
    # strict judge may flip direction; match either direction
    surv_either = surv_set | {(d, s) for s, d in surv_set}

    kept = [e for e in edges if (e["s"], e["d"]) in surv_either]
    demoted = [e for e in edges if (e["s"], e["d"]) not in surv_either]
    print(f"\n=== v2 strict re-judge: {len(edges)} → kept {len(kept)} (demoted-to-none {len(demoted)}) ===")
    print(f"  density: {len(edges)/101:.1f}/KU → {len(kept)/101:.1f}/KU")
    print(f"  kept by relation: {dict(Counter(e['rel'] for e in kept))}")
    print(f"  demoted by relation: {dict(Counter(e['rel'] for e in demoted))}")

    # ★no-误杀 check: the real edges from last turn (contrasts + 'because' causal explains)
    contrasts = [e for e in edges if e["rel"] == "contrasts_with"]
    contrasts_kept = [e for e in contrasts if (e["s"], e["d"]) in surv_either]
    causal = [e for e in edges if e["rel"] == "explains" and re.search(r'\bbecause\b', (e["sa"] or "") + (e["sb"] or ""), re.I)]
    causal_kept = [e for e in causal if (e["s"], e["d"]) in surv_either]
    print(f"\n=== ★不误杀检验 ===")
    print(f"  contrasts_with: {len(contrasts)} → kept {len(contrasts_kept)} ({100*len(contrasts_kept)/max(len(contrasts),1):.0f}%)")
    print(f"  'because'-causal explains: {len(causal)} → kept {len(causal_kept)} ({100*len(causal_kept)/max(len(causal),1):.0f}%)")

    # top-K cap on survivors
    strength_of = {(min(e["s"], e["d"]), max(e["s"], e["d"])): e["shared"] + e["sim"] for e in edges}
    capped = topk_cap([(e["s"], e["d"], e["rel"]) for e in kept], strength_of, k=4)
    print(f"\n=== top-K(4) cap: {len(kept)} → {len(capped)} edges, density {len(capped)/101:.1f}/KU ===")

    # save kept sample for judgment
    sample = [{"rel": e["rel"], "a": (e["sa"] or "")[:90], "b": (e["sb"] or "")[:90], "strength": e["strength"]} for e in kept[:30]]
    Path(SC + "/v2_kept.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {len(sample)} kept-edge samples to v2_kept.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
