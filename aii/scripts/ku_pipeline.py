#!/usr/bin/env python3
"""KU 质检管道统一入口 (规格 4.1/4.3/6) — run_ku_qa_pipeline 落地。

把散在 synthesize_book.persist 的校验链收敛为可测试的单一入口:
  evaluate_ku_chain(ku) -> {status: pass|repair|reject, quality, signatures[]}

级联顺序(成本升序, 规格 3.4):
  MOJIBAKE(编码) → NO_SPAN(quote 子串) → HALLUCINATION(数字/embedding 粗滤)
  → LANG_MIX(语言混杂) → 软分(LOW_DENSITY/TOO_COARSE) → NLI(NOT_ENTAILED, 严进可选)

repair 决策(规格 4.2/4.3):
  choose_repair_action(signature, source_type) — 从 skill_rules 映射表 + trajectory
  历史过检率(utility) 选动作; 无法决断时调 omodul.diagnose_root_cause 兜底。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from block_quality import check_chunk_quality
from evaluate_ku import (
    NLI_STRICT, check_lang_mix, embedding_coarse_filter,
    infer_claim_type, score_ku,
)
from ku_schema import check_number_alignment, validate_quotes

REPAIR_BUDGET = int(os.getenv("KU_REPAIR_BUDGET", "2"))  # 每候选返工预算(规格: 每源5总量/每候选2)


async def _nli_verify(claim: str, quotes: list[dict]) -> dict | None:
    """调 NLI 服务(8103)。失败返回 None(不阻断)。"""
    import urllib.request as _ur
    try:
        ev = " ".join(q.get("quote", "") for q in quotes)[:2000]
        body = json.dumps({"pairs": [{"evidence": ev, "claim": claim[:800]}]}).encode()
        req = _ur.Request("http://127.0.0.1:8103/verify_batch", data=body,
                          headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())[0]
    except Exception:  # noqa: BLE001
        return None


async def evaluate_ku_chain(
    ku_id: str,
    claim: str,
    title: str,
    quotes: list[dict],
    window_text: str,
    ku_type: str = "conceptual",
    source_type: str = "unknown",
    nli_off: bool = False,
) -> dict:
    """完整校验链。返回 {status, quality, signatures}。

    status: pass | reject | repair
    quality: {score, checks:[...], status, claim_type}   (规格 5 持久化用)
    signatures: 触发的失败签名列表(供 repair 决策/审计)
    """
    quality: dict = {"score": 0.0, "checks": [], "status": "pass", "claim_type": ""}
    signatures: list[str] = []

    def _fail(sig: str, check: str) -> None:
        signatures.append(sig)
        quality["checks"].append({"check": check, "status": "fail", "signature": sig})

    # 1. 编码类检查(claim 是短命题, 不做块级 TOO_SHORT/BOILERPLATE)
    for pat, sig in ((r"\ufffd", "MOJIBAKE"), (r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "MOJIBAKE")):
        if re.search(pat, claim or ""):
            _fail(sig, f"编码异常: {pat}")
    # 原始块质量(仅信息, 不据此判 claim)
    # 2. NO_SPAN(quote 子串)
    qerrs = validate_quotes(quotes, window_text or "")
    if not quotes or qerrs:
        _fail("NO_SPAN", f"evidence_quotes: {qerrs[:1]}" if qerrs else "empty")
    # 3. HALLUCINATION(数字对齐 + embedding 粗滤)
    for err in check_number_alignment(claim, quotes):
        _fail("HALLUCINATION", err)
    for err in embedding_coarse_filter(claim, quotes):
        _fail("HALLUCINATION", err)
    # 4. 语言混杂
    for err in check_lang_mix(claim, "zh"):
        _fail("LANG_MIX", err)
    # 5. 软分
    kval = score_ku(claim, title, quotes)
    quality["score"] = kval["total"]
    if not kval["pass"]:
        _fail("LOW_DENSITY", f"软分 {kval['total']} < 阈值")
    # 6. NLI(打标不拒; KU_NLI_STRICT=1 时严进)
    nli = None
    if not nli_off and not signatures:
        nli = await _nli_verify(claim, quotes)
        if nli and not nli.get("pass_support", False):
            quality["checks"].append({
                "check": "nli", "status": "fail",
                "signature": "NOT_ENTAILED",
                "entailment": nli.get("score_entailment", 0.0),
                "label": nli.get("label"),
            })
            if NLI_STRICT:
                signatures.append("NOT_ENTAILED")
    if nli:
        quality["nli"] = {"label": nli.get("label"),
                          "entailment": nli.get("score_entailment", 0.0)}

    quality["claim_type"] = infer_claim_type(claim, ku_type)
    hard_fail = [s for s in signatures
                 if s in ("MOJIBAKE", "NO_SPAN", "HALLUCINATION", "LANG_MIX")]
    if hard_fail:
        quality["status"] = "reject"
    elif signatures:
        quality["status"] = "reject" if quality["score"] < 0.4 else "repair"
    else:
        quality["status"] = "pass"
    quality["checks"].append({"check": "chain", "status": quality["status"],
                              "score": quality["score"]})
    return {"status": quality["status"], "quality": quality, "signatures": signatures}


async def choose_repair_action(signatures: list[str], source_type: str = "unknown") -> str:
    """repair 动作选择(规格 4.2/4.3): signature_map 规则 + 轨迹效用统计。

    utility(action) ≈ 该签名下 action 的历史过检率; 无数据时按映射表默认顺序。
    """
    import asyncpg
    try:
        conn = await asyncpg.connect(
            os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"),
            timeout=5)
        try:
            actions: list[str] = []
            for sig in signatures[:1]:
                row = await conn.fetchrow(
                    "SELECT action FROM aii.skill_rules WHERE rule_name=$1"
                    " AND source='signature_map'", f"sig_{sig}")
                if row:
                    act = json.loads(row["action"])
                    actions = [act.get("repair")] + (act.get("alt") or [])
            if actions:
                stats = await conn.fetch(
                    "SELECT context->>'repair' AS act, count(*) FILTER"
                    " (WHERE outcome='recovered') AS rec, count(*) AS n"
                    " FROM aii.trajectory_logs WHERE failure_mode=$1"
                    " AND ts > now() - interval '7 days' GROUP BY 1",
                    signatures[0])
                rate = {r["act"]: (r["rec"] / r["n"] if r["n"] else 0) for r in stats}
                if rate:
                    actions.sort(key=lambda a: rate.get(a, 0), reverse=True)
            return actions[0] if actions else "abort"
        finally:
            await conn.close()
    except Exception:  # noqa: BLE001
        return "abort"


async def investigate_fallback(problem: str, context: dict | None = None) -> dict:
    """repair 无法决断时的调查兜底(规格 4.4): omodul.diagnose_root_cause。

    aii 侧可 import omodul(容器 /opt/platform 或 dev 副本)。失败静默返回空。
    """
    try:
        from omodul.diagnose_root_cause import (
            DiagnoseRootCauseConfig, DiagnoseRootCauseInput, diagnose_root_cause,
        )
        cfg = DiagnoseRootCauseConfig(
            signal_hash=f"ku_qa:{problem[:60]}",
            available_tools_hash="ku_qa:readonly",
            max_steps=5, confidence_threshold=0.7,
        )
        from oskill import Signal
        inp = DiagnoseRootCauseInput(
            signal=Signal(
                source="stratum_ku_qa",
                kind="quality_failure",
                summary=problem[:200],
                payload=(context or {}),
            ),
            available_tool_names=["trajectory_logs", "skill_rules"],
            initial_context=(context or {}),
        )
        outcome = await asyncio.to_thread(
            diagnose_root_cause, cfg, inp, Path("/tmp/ku_qa_investigate"),
        )
        return {
            "used": True,
            "conclusion": outcome.get("final_conclusion", {}),
            "requires_human": outcome.get("requires_human", False),
        }
    except Exception as e:  # noqa: BLE001
        return {"used": False, "error": str(e)[:120]}


if __name__ == "__main__":
    # 自检
    async def selftest():
        r = await evaluate_ku_chain(
            "test::ch1_ku1", "机会成本是指为了得到某种东西而必须放弃的其他东西的价值",
            "机会成本",
            [{"quote": "机会成本是指为了得到某种东西而必须放弃的其他东西的价值", "span": [0, 20]}],
            "机会成本是指为了得到某种东西而必须放弃的其他东西的价值。稀缺性导致选择。",
        )
        print("pass 例:", r["status"], r["quality"]["score"], r["quality"]["claim_type"])
        r2 = await evaluate_ku_chain(
            "test::ch1_ku2", "这是编造的话完全不基于原文内容", "编造",
            [{"quote": "原文说的是另外一件事完全不相关", "span": [0, 10]}],
            "原文说的是另外一件事完全不相关。",
        )
        print("reject 例:", r2["status"], r2["signatures"])
        print("repair 决策:", await choose_repair_action(["NO_SPAN"], "book"))
    asyncio.run(selftest())
