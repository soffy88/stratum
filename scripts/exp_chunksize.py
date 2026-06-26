"""对照实验: 同一文本, chunk_size=2000(小块A) vs 11000(大块B单块). 同 prompt/flash, 只变块大小.
测: 数量 / 六分类 / KU 内容 / 位置分布(begin-mid-end, 验 lost-in-the-middle)."""
import asyncio, os, re, statistics
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
from aii.api._provider import register_providers
from aii.service import onto_prompts as P
from aii.service import onto_vocab as V
from obase import ProviderRegistry

SC = "/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad"
SECTION = Path(SC + "/exp_section.md").read_text(encoding="utf-8")
PROMPTS = dict(
    pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
    pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
    pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL, pass2_system=P.PASS2_SYSTEM,
    valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES, valid_sub_types=V.VALID_SUB_TYPES,
    valid_relation_types=V.VALID_RELATION_TYPES, doc_type="textbook", source_credibility="high")

_low = SECTION.lower()
_L = len(SECTION)


def position_third(content: str) -> str:
    """把 KU 内容映射到原文位置(取内容里特征词在原文的中位位置) → begin/mid/end."""
    words = [w for w in re.findall(r"[a-z]{6,}", (content or "").lower())]
    idxs = [_low.find(w) for w in words if _low.find(w) >= 0]
    if not idxs:
        return "?"
    pos = statistics.median(idxs) / _L
    return "begin" if pos < 0.34 else ("mid" if pos < 0.67 else "end")


async def run(chunk_size):
    llm = ProviderRegistry.get().llm("default")
    from oskill import ontology_extract
    return await ontology_extract(source_text=SECTION, llm=llm, chunk_size=chunk_size, **PROMPTS)


async def main():
    register_providers()
    print(f"SECTION chars={_L}\n", flush=True)
    for label, cs in [("A small chunk_size=2000", 2000), ("B big chunk_size=11000(single)", 11000)]:
        r = await run(cs)
        kus = r.ku_candidates
        thirds = Counter(position_third(k.get("content", "")) for k in kus)
        print(f"===== {label} =====", flush=True)
        print(f"KU count = {len(kus)} | by_type = {dict(Counter(k.get('knowledge_type') for k in kus))}", flush=True)
        print(f"position distribution: {dict(thirds)}  (begin/mid/end thirds of the section)", flush=True)
        print("--- KU titles (content[:75]) ---", flush=True)
        for k in kus:
            print(f"  [{position_third(k.get('content','')):5}] {k.get('content','')[:75]}", flush=True)
        print(flush=True)


if __name__ == "__main__":
    asyncio.run(main())
