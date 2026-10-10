"""论文技能 V3 排他性门(2026-07-16, 参考 cangjie-skill 的三重验证 V3)。

cangjie 判据: "不给常识建 skill——Claude 本来就会; 只留作者独有/反直觉/独特体系的洞见"。
论文语境: 论文整体通常是新贡献(能过), 真正有用的是**逐条筛 key_findings**——
哪些是这篇独有的非常识洞见(值得当技能), 哪些只是常识/教材级(agent 本来就知道, 别当技能亮点)。

判官结果写回 agent_skill.v3 = {worth_as_skill, novelty_note, findings:[{finding, exclusive, why}]}。
observe-only: 只标注不删除, 恒 exit 0(判官有主观误差, 留给人/下游决定)。

用法: SUBSTRATE=advmath_en_xxx python scripts/paper_v3_gate.py
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg

SUB = os.getenv("SUBSTRATE", "")

_SYS = (
    "你是论文技能的排他性判官。判据(来自 cangjie-skill V3): **不给常识建技能**——一个通用 AI agent "
    "本来就知道的东西(教材常识、显而易见的推论)不值得当技能亮点; 只有**这篇论文独有的、反直觉的、"
    "或需要这篇才知道的**洞见/方法/结论才算 exclusive。逐条判 key_findings, 并给论文级总判。只输出 JSON:\n"
    '{"worth_as_skill": true/false(这篇整体是否有非常识贡献、值得建技能),'
    ' "novelty_note": "一句话:这篇最不常识的点是什么",'
    ' "findings": [{"finding":"(照抄给的结论)", "exclusive": true/false, "why":"为什么算/不算非常识"}]}\n'
    '严格但公允: 真正的常识(如"变量X影响Y"级)判 false; 带具体机制/条件/反直觉方向的判 true。'
)


async def main():
    if not SUB:
        print("  v3_gate: 缺 SUBSTRATE, 跳过")
        return
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    row = await c.fetchrow(
        "SELECT overview_oneline, main_claims, agent_skill FROM aii.bu_onto "
        "WHERE substrate_id=$1 AND doc_type='paper'",
        SUB,
    )
    if not row:
        await c.close()
        print(f"  v3_gate [{SUB}]: 无 doc_type=paper 的 BU, 跳过")
        return

    def _obj(v):
        return json.loads(v) if isinstance(v, str) else (v or {})

    skill = _obj(row["agent_skill"])
    claims = _obj(row["main_claims"]) or []
    findings = [c_.get("claim") for c_ in claims if isinstance(c_, dict) and c_.get("claim")]
    if not findings:
        await c.close()
        print(f"  v3_gate [{SUB}]: 无 key_findings 可判, 跳过")
        return

    body = (
        f"论文一句话: {row['overview_oneline']}\n"
        f"方法总思路: {(skill.get('method') or {}).get('approach', '')}\n"
        f"本篇新造术语: {[t.get('term') for t in (skill.get('coined_terms') or [])]}\n"
        f"待判的 key_findings:\n" + "\n".join(f"- {f}" for f in findings)
    )

    from aii.api._provider import register_providers
    from obase import ProviderRegistry

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    try:
        verdict = json.loads(llm.call_sync(_SYS + "\n\n" + body))
    except Exception as e:
        await c.close()
        print(f"  v3_gate [{SUB}]: 判官调用失败(非致命): {e}")
        return

    await c.execute(
        "UPDATE aii.bu_onto SET agent_skill = jsonb_set(coalesce(agent_skill,'{}'::jsonb), '{v3}', $2::jsonb) "
        "WHERE substrate_id=$1",
        SUB,
        json.dumps(verdict, ensure_ascii=False),
    )
    await c.close()
    fv = verdict.get("findings") or []
    excl = sum(1 for f in fv if f.get("exclusive"))
    print(
        f"  v3_gate [{SUB}]: worth_as_skill={verdict.get('worth_as_skill')} | "
        f"非常识 findings {excl}/{len(fv)} | {verdict.get('novelty_note', '')[:50]}"
    )


if __name__ == "__main__":
    asyncio.run(main())
