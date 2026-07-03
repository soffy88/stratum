"""KU/概念 判同(判"是不是讲同一个点") — 去重机制第①步。

命门(宁碎片不错合): 错合不可逆(地基污染), 碎片可恢复 → 存疑一律判 different。
读原文(zh 留 zh、en 留 en, 双语判官), 不预翻译; 判别维度经闭集词典提示; 名称受控对齐。
可重放: 命中台账既有决策 → 直接返回(不重问模型); 否则调最强模型 + 写台账(含 llm_raw)。
"""

from __future__ import annotations
import json
import re

from dictionary import canonical, dimensions_hint
from gates import run_gates

SYSTEM = """你是知识库的严格"判同"裁判。唯一任务: 判定两个条目是否指向同一个点(同一概念或同一论断)。
代价不对称: 错合(把不同的判为同一)是不可逆的地基污染; 保持两个同一的为分开只是碎片, 可恢复。
因此: 只要不确定, 一律判 different。

判据(任一不满足即 different):
1. 判别维度: 本质维度取值不同即不同概念(如弹性对象 price≠income; 侧 demand≠supply; 成本对象不同)。
   表述维度不同不算不同(大小写/单复数/语言/测量法 arc-point/时期措辞)。
2. 上下位: 一个是另一个的特化/子类即 different(如 increasing marginal cost ⊂ marginal cost; 短期X ⊂ X)。
3. 方向/反义: 方向或极性相反即 different(如 右导数 vs 导数; 单侧 vs 双侧)。
读原文语义判断(中文按中文、英文按英文), 不要依赖翻译。
只输出 JSON: {"verdict":"same|different|uncertain","reason":"简述"}。uncertain 会被当作 different。"""


def _fmt(item: dict) -> str:
    """条目呈现给判官: 名称(+受控 canonical)+ 学科/别名/正文片段, 保留原语言。"""
    lines = [f"名称: {item.get('name', '')}"]
    if item.get("name_zh") and item["name_zh"] != item.get("name"):
        lines.append(f"中文名: {item['name_zh']}")
    can = canonical(item.get("name", ""))
    if can:
        lines.append(f"术语规范: {can['canonical_en']} / {can['zh']}")
    if item.get("discipline"):
        lines.append(f"学科: {item['discipline']}")
    if item.get("aliases"):
        lines.append(f"别名: {item['aliases']}")
    if item.get("text"):
        lines.append(f"正文片段: {item['text'][:600]}")
    return "\n".join(lines)


def _parse(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            v = str(j.get("verdict", "")).lower()
            if v in ("same", "different", "uncertain"):
                return {"verdict": v, "reason": j.get("reason", "")}
        except Exception:
            pass
    return {"verdict": "uncertain", "reason": f"解析失败(保守判 different): {raw[:120]}"}


async def judge_pair(
    a: dict, b: dict, llm, ledger, *, kind: str, model: str, decision_type: str = "ku_dedup"
) -> dict:
    """判 a,b 是否同点。返回 {verdict, reason, replayed, decision_id}。verdict∈same/different/uncertain。
    a,b 须含 id + name(+ name_zh/discipline/aliases/text)。"""
    # 可重放: 命中台账 → 直接返回, 不重问
    prior = await ledger.replay_lookup(decision_type, kind, a["id"], b["id"]) if ledger else None
    if prior:
        vd = prior["verdict"]
        return {**vd, "replayed": True, "decision_id": prior["decision_id"]}

    # 程序关(确定性, 关1 判别维度 / 关2 上下位 / 关0 术语同名): 命中即定, 不调 LLM
    g = run_gates(a.get("name", ""), b.get("name", ""))
    if g:
        vd = {"verdict": g["verdict"], "reason": f"[{g['gate']}] {g['reason']}"}
        decision_id = None
        if ledger:
            decision_id = await ledger.record_pair(
                decision_type,
                kind,
                a["id"],
                b["id"],
                vd,
                model=g["gate"],
                actor="program",
                evidence={"a_name": a.get("name"), "b_name": b.get("name")},
            )
        return {**vd, "replayed": False, "gate": g["gate"], "decision_id": decision_id}

    # 关3: LLM 语义判(仅程序关未决的窄候选)
    hint = dimensions_hint(a.get("name", ""), b.get("name", ""))
    prompt = (
        f"{hint}\n\n" if hint else ""
    ) + f"条目 A:\n{_fmt(a)}\n\n条目 B:\n{_fmt(b)}\n\n判定 A、B 是否同一个点。"
    r = await llm(messages=[{"role": "user", "content": prompt}], system=SYSTEM, max_tokens=400)
    raw = r["content"][0]["text"] if isinstance(r, dict) else str(r)
    vd = _parse(raw)

    decision_id = None
    if ledger:
        decision_id = await ledger.record_pair(
            decision_type,
            kind,
            a["id"],
            b["id"],
            vd,
            model=model,
            llm_raw={"prompt_tail": prompt[-400:], "response": raw},
            actor="llm",
            evidence={"a_name": a.get("name"), "b_name": b.get("name")},
        )
    return {**vd, "replayed": False, "decision_id": decision_id}


def to_merge_action(verdict: str) -> str:
    """判同→合并动作(宁碎片): 只有确信 same 才合并; uncertain/different 都不合。"""
    return "same" if verdict == "same" else "different"
