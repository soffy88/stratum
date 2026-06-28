"""章节级高质量抽取测试: HQ prompt 小块抽全 → 章节级去重 → 结构门. 对比原 17 条.
输出全部 KU(全字段)到 stdout + ku_hq.json."""
import asyncio, json
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
from aii.api._provider import register_providers
from aii.service import onto_prompts as P
from aii.service import onto_vocab as V
from aii.service.chapter_dedup import dedup_kus
from aii.service.structural_gate import is_structural_noise
from obase import ProviderRegistry

SC = "/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad"
SECTION = Path(SC + "/exp_section.md").read_text(encoding="utf-8")


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    from oskill import ontology_extract
    # 1. HQ prompt, 小块抽全 (pass1/outline 用原版, pass2 用 HQ)
    r = await ontology_extract(
        source_text=SECTION, llm=llm, chunk_size=2000, doc_type="textbook", source_credibility="high",
        pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
        pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
        pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL_HQ, pass2_system=P.PASS2_SYSTEM_HQ,
        valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES, valid_sub_types=V.VALID_SUB_TYPES,
        valid_relation_types=V.VALID_RELATION_TYPES)
    raw = r.ku_candidates
    # 2. 结构门(拦残片/标题)
    gated = [k for k in raw if not is_structural_noise(k.get("content"))]
    # 3. 章节级去重
    dd = await dedup_kus(gated, llm, sim_threshold=0.82)
    final = dd["kept"]
    print(f"raw={len(raw)}  after_gate={len(gated)}  after_dedup={len(final)}  "
          f"by_type={dict(Counter(k.get('knowledge_type') for k in final))}", flush=True)
    print(f"dedup groups (same→keep): {dd['groups']}", flush=True)
    out = [{"n": i + 1, "type": k.get("knowledge_type"), "sub_type": k.get("sub_type"),
            "defines_concept": k.get("defines_concept"), "example": k.get("example"),
            "content": k.get("content"), "content_zh": k.get("content_zh")} for i, k in enumerate(final)]
    Path(SC + "/ku_hq.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {len(out)} final KUs to ku_hq.json", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
