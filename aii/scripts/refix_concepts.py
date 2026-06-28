"""Un-merge the antonym/distinct concepts wrongly merged by the old 0.90-cosine normalize.

For each concept (in this substrate) carrying aliases (= names absorbed during the buggy merge),
re-judge (canonical, alias) with the NEW LLM judge. If DIFFERENT -> split the alias back into its
own concept node + best-effort relink KUs whose natural_text mentions the alias.

NOTE: the old merge was destructive (per-KU original names lost), so KU relink is best-effort by
text match. The concept NODES are split correctly (which is what the cleanliness check verifies).
"""
import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

import asyncpg
from aii.api._provider import register_providers
from aii.service.concept_onto_ops import (
    _encode, _CONCEPT_JUDGE_SYS, _CONCEPT_JUDGE_TMPL, _parse_same)
from obase import ProviderRegistry

SUB = "microecon_en_full"
DISC = "经济学"


async def judge_same(llm, a, b) -> bool:
    try:
        resp = await llm(messages=[{"role": "user", "content": _CONCEPT_JUDGE_TMPL.format(a=a, b=b)}],
                         system=_CONCEPT_JUDGE_SYS, max_tokens=20)
        return _parse_same(resp)
    except Exception:
        return True  # 判不了就别拆 (保守: 维持现状)


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector
    await register_vector(conn)

    # 本 substrate 的概念里带 aliases 的 (= 旧 merge 吸收过别名)
    rows = await conn.fetch(
        """SELECT DISTINCT c.concept_id, c.name, c.aliases
           FROM aii.ku_concept_onto kc
           JOIN aii.concept_onto c ON kc.concept_id=c.concept_id
           JOIN aii.ku_onto k ON kc.ku_id=k.ku_id AND k.substrate_id=$1
           WHERE c.aliases <> '[]'::jsonb""", SUB)
    print(f"concepts with aliases: {len(rows)}", flush=True)

    split_cnt = 0; kept_cnt = 0; relinked = 0; splits = []
    for r in rows:
        can_id, can_name = r["concept_id"], r["name"]
        aliases = json.loads(r["aliases"]) if isinstance(r["aliases"], str) else r["aliases"]
        keep_aliases, to_split = [], []
        for al in aliases:
            if await judge_same(llm, can_name, al):
                keep_aliases.append(al); kept_cnt += 1
            else:
                to_split.append(al); split_cnt += 1
        for al in to_split:
            vec = _encode([al])[0].tolist()
            a_id = await conn.fetchval(
                """INSERT INTO aii.concept_onto(name, discipline, vector) VALUES($1,$2,$3)
                   ON CONFLICT (name) DO UPDATE SET discipline=COALESCE(aii.concept_onto.discipline,$2)
                   RETURNING concept_id""", al, DISC, vec)
            # best-effort relink: 本 substrate 中链到 canonical 且正文提到 alias 的 KU → 也链到 split 节点
            n = await conn.execute(
                """INSERT INTO aii.ku_concept_onto(ku_id, concept_id)
                   SELECT kc.ku_id, $1 FROM aii.ku_concept_onto kc
                   JOIN aii.ku_onto k ON kc.ku_id=k.ku_id AND k.substrate_id=$2
                   WHERE kc.concept_id=$3 AND k.natural_text ILIKE '%'||$4||'%'
                   ON CONFLICT DO NOTHING""", a_id, SUB, can_id, al)
            relinked += int(n.split()[-1]) if n.startswith("INSERT") else 0
            splits.append((can_name, al))
        # 更新 canonical.aliases 只留判为 SAME 的
        await conn.execute("UPDATE aii.concept_onto SET aliases=$1::jsonb WHERE concept_id=$2",
                           json.dumps(keep_aliases), can_id)

    print(f"\nsplit={split_cnt} kept_merged={kept_cnt} ku_relinked={relinked}", flush=True)
    print("SPLITS (canonical -X-> back to own node):", flush=True)
    for c, a in splits:
        print(f"  '{c}'  ⊅  '{a}'", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
