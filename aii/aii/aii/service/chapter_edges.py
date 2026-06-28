"""章内建边 v2: 收紧 judge(治 over-link 治本)+ top-K 封顶(结构剪枝). 不过滤候选(不误杀).

实证结论(对照 ch3 643边):
  - 放弃候选过滤捷径: tier评分/因果连接词/Hearst 都误杀真边(真对比/真因果落 weak tier 或无连接词).
  - over-link 根源是 judge 太松(1177候选53%判真)→ 治本=收紧 judge prompt(默认none/只强直接非平凡/
    明拒话题并列+近重复+定义并列), 仍全候选走LLM靠理解逐对判.
  - top-K: 每 KU 最多 K 条边, 超出保留共现最强的 K 条(结构剪枝防热概念过连, 不判边真假).
"""
from __future__ import annotations

import asyncio
import json
import re

from aii.service.onto_vocab import VALID_RELATION_TYPES

JUDGE_SYS_V2 = (
    "You are a STRICT knowledge-graph relation judge. Assert a relation ONLY when it is strong, direct, "
    "and informative. Default to 'none'. Output valid JSON only.")

JUDGE_TMPL_V2 = """\
Two knowledge units from one economics textbook chapter:

[A] {a}

[B] {b}

Assert a relation ONLY if a SPECIFIC, DIRECT, NON-TRIVIAL relation holds between A and B.
Answer "none" (do NOT link) if ANY of these:
- A and B merely share a topic/term but have no direct relation;
- A and B say essentially the SAME thing (near-duplicate / restatement / elaboration);
- A and B are two separate DEFINITIONS of related terms with no relation BETWEEN them
  (★ if A defines term X and B defines term Y, that is NOT 'explains'/'causes' even if X and Y are
   related — defining is not explaining; answer 'none' unless A states the actual mechanism/cause of B);
- the relation is trivial/obvious or already fully contained in either unit alone.
Only assert when the relation adds real structure to the knowledge graph. When in doubt → "none".

Valid relations (pick the single most specific TRUE one):
  explains (A gives the mechanism/WHY of B), causes (A causally produces B),
  prerequisite_of (A must hold/be done before B), special_case_of (A is a specific case of B),
  subsumes (A includes B as a part/member), contrasts_with (A and B are directly opposed/compared),
  supported_by (B is evidence/example supporting A).

Output JSON: {{"relation":"<one valid relation or 'none'>","direction":"AtoB" or "BtoA"}}"""


def parse_relation(resp) -> dict:
    txt = ""
    for blk in resp.get("content", []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += blk.get("text", "")
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return {"relation": "none"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"relation": "none"}


async def judge_pairs_v2(llm, pairs, texts, *, concurrency: int = 8) -> list:
    """对候选对用收紧 judge 逐对判. pairs=[(k1,k2)], texts={ku_id:text}.
    返回 [(k1,k2,relation,direction)] 仅 relation 受控且非 none."""
    sem = asyncio.Semaphore(concurrency)

    async def judge(k1, k2):
        async with sem:
            prompt = JUDGE_TMPL_V2.format(a=texts.get(k1, "")[:600], b=texts.get(k2, "")[:600])
            try:
                resp = await llm(messages=[{"role": "user", "content": prompt}],
                                 system=JUDGE_SYS_V2, max_tokens=80)
                j = parse_relation(resp)
            except Exception:
                j = {"relation": "none"}
            rel = (j.get("relation") or "none").strip().lower()
            if rel in ("none", "same_as") or rel not in VALID_RELATION_TYPES:
                return None
            src, dst = (k1, k2) if j.get("direction") != "BtoA" else (k2, k1)
            return (src, dst, rel)

    out = []
    for fut in asyncio.as_completed([judge(k1, k2) for k1, k2 in pairs]):
        r = await fut
        if r:
            out.append(r)
    return out


async def judge_pairs_v2_voted(llm, pairs, texts, *, votes: int = 3, concurrency: int = 12) -> list:
    """多 judge 投票消随机误杀: 每对判 votes 次, 某关系得多数(>votes/2)才连(取该关系多数方向).
    抖动单次误判 none 的真边, 多数票救回; 单次幻觉的边, 多数票否掉. 返回 [(src,dst,rel)]."""
    from collections import Counter
    sem = asyncio.Semaphore(concurrency)

    async def one(k1, k2):
        async with sem:
            prompt = JUDGE_TMPL_V2.format(a=texts.get(k1, "")[:600], b=texts.get(k2, "")[:600])
            try:
                resp = await llm(messages=[{"role": "user", "content": prompt}],
                                 system=JUDGE_SYS_V2, max_tokens=80)
                j = parse_relation(resp)
            except Exception:
                j = {"relation": "none"}
            rel = (j.get("relation") or "none").strip().lower()
            if rel in ("none", "same_as") or rel not in VALID_RELATION_TYPES:
                return ("none", None)
            return (rel, j.get("direction"))

    async def vote(k1, k2):
        results = await asyncio.gather(*(one(k1, k2) for _ in range(votes)))
        rels = Counter(r for r, _ in results)
        rel, cnt = rels.most_common(1)[0]
        if rel == "none" or cnt <= votes // 2:        # 需严格多数(>votes/2)的非-none关系
            # tie-break: if a single relation reaches majority among non-none votes
            nonnone = Counter({r: c for r, c in rels.items() if r != "none"})
            if not nonnone:
                return None
            rel, cnt = nonnone.most_common(1)[0]
            if cnt <= votes // 2:
                return None
        direction = next((d for r, d in results if r == rel), None)
        src, dst = (k1, k2) if direction != "BtoA" else (k2, k1)
        return (src, dst, rel)

    out = []
    for fut in asyncio.as_completed([vote(k1, k2) for k1, k2 in pairs]):
        r = await fut
        if r:
            out.append(r)
    return out


def topk_cap(edges, strength_of, k: int = 4) -> list:
    """每 KU 最多 k 条边: 度数超 k 的节点, 保留共现最强的 k 条. strength_of[(a,b)]=score."""
    from collections import defaultdict
    deg = defaultdict(int)
    for s, d, rel in edges:
        deg[s] += 1; deg[d] += 1
    # 按 score 降序, 贪心保留, 跳过会让任一端点超 k 的边
    ordered = sorted(edges, key=lambda e: strength_of.get((min(e[0], e[1]), max(e[0], e[1])), 0), reverse=True)
    kept, kdeg = [], defaultdict(int)
    for s, d, rel in ordered:
        if kdeg[s] < k and kdeg[d] < k:
            kept.append((s, d, rel)); kdeg[s] += 1; kdeg[d] += 1
    return kept
