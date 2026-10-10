"""高级数学经济专用飞轮 — 论文召回审计(observe-only, 不拦截入库).

动机: advmath 现有完整性只保证"plan 加粗的核心术语都覆盖了"(chapter_synthesize_advmath
的 missing_bold_terms + synthesize_book 的一章失败整本失败)。但这**相对于 plan 加粗了什么**——
论文的新贡献常用非标准措辞, plan 可能没识别成加粗项就不在追踪范围内。论文比教材更怕漏
(教材漏个概念别的书还有, 论文的核心贡献是独有的, 漏了就永久丢)。

本审计独立于 plan: 直接从论文 abstract+intro+"we show/find/propose…"句抽出论文**自称**的
核心贡献(观点/方法/机制/程序/结果), 再逐条核对是否至少映射到一条已入库 KU。只记录漏项,
**不拦截入库、恒 exit 0**(和 advmath_verify.py 同哲学: 判官有主观误差, 先 observe-only)。

用法:
  SUBSTRATE=advmath_en_xxx AII_MD_FILE=/path/book.md python scripts/advmath_recall_audit.py
  或  python scripts/advmath_recall_audit.py --substrate advmath_en_xxx --md /path/book.md
报告写 advmath_pipeline/recall_audit/<SUBSTRATE>.json, 摘要打 stdout。
Exit: 恒 0(judge本身网络/key错也只打日志, 不拦截)。
"""

import argparse, asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
import httpx

MODEL = os.getenv("ADVMATH_VERIFY_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")


def _key() -> str:
    k = os.getenv("ADVMATH_VERIFY_KEY")
    if k:
        return k
    try:
        return json.load(open(ROOT / ".pipeline_keys.json")).get("advmath_verify", "")
    except Exception:
        return ""


# ── 从论文抽"自称贡献"的上下文: abstract+intro 前段 + 全文里的贡献信号句 ──
_CONTRIB_CUE = re.compile(
    r"(?i)\b(we\s+(show|find|prove|propose|develop|introduce|establish|derive|present|"
    r"contribute|demonstrate)|our\s+(main|key|central|primary)\s+(contribution|result|finding)|"
    r"this\s+(paper|article|work)\s+(shows|proposes|develops|introduces|contributes)|"
    r"(is|are)\s+the\s+first\s+to|not\s+previously\s+(identified|studied|shown)|novel(ly)?)\b"
)


def _contribution_context(md: str) -> str:
    head = md[:16000]  # abstract + intro 通常在前段
    cue_sents = []
    for m in _CONTRIB_CUE.finditer(md):
        s = max(0, m.start() - 120)
        e = min(len(md), m.end() + 220)
        cue_sents.append(md[s:e].replace("\n", " "))
        if len(cue_sents) >= 40:
            break
    tail = "\n\n信号句(全文散落的贡献陈述):\n" + "\n---\n".join(cue_sents) if cue_sents else ""
    return head + tail


EXTRACT_SYS = (
    "You analyze an academic paper and list ITS CORE CONTRIBUTIONS — the things THIS paper "
    "newly offers, that would be permanently lost if not captured: novel viewpoints/claims, "
    "methods, mechanisms, procedures/algorithms, and key results/findings. Ignore background, "
    "prior work, and generic setup. Output JSON only: "
    '{"contributions":[{"id":1,"kind":"viewpoint|method|mechanism|procedure|result","statement":"one concise sentence"}]}. '
    "Aim for completeness of the genuinely novel core (typically 5-15 items); do not pad with trivia."
)

COVER_SYS = (
    "You audit RECALL of a knowledge-extraction pipeline for one paper. You are given (A) the paper's "
    "core contributions and (B) the titles+glosses of the knowledge units (KUs) that were extracted. "
    "For EACH contribution decide if it is genuinely captured by at least one KU (its substance, not "
    "just a keyword overlap). Be strict: a contribution about a specific mechanism/result is 'covered' "
    "only if a KU actually carries that mechanism/result. Output JSON only: "
    '{"results":[{"id":1,"covered":true,"matched_ku":"<KU title or null>","note":"short"}]}.'
)


async def _chat(client, sysmsg, usermsg, key):
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}],
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(3):
        try:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=body,
            )
            if r.status_code == 429 and attempt < 2:
                await asyncio.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or ""
            if not content:  # 推理模型偶发空content(多因max_tokens被推理吃光)→重试
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
                return {"error": "empty content"}
            m = re.search(r"\{.*\}", content, re.DOTALL)
            return json.loads(m.group(0)) if m else {}
        except Exception as e:
            if attempt == 2:
                return {"error": str(e)}
            await asyncio.sleep(5)
    return {}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--substrate", default=os.getenv("SUBSTRATE"))
    ap.add_argument("--md", default=os.getenv("AII_MD_FILE"))
    args = ap.parse_args()
    SUB = args.substrate
    if not SUB or not args.md:
        print("  ⚠ recall_audit: 缺 SUBSTRATE 或 AII_MD_FILE, 跳过(不拦截)", flush=True)
        return
    key = _key()
    if not key:
        print("  ⚠ recall_audit: 无判官key, 跳过(不拦截)", flush=True)
        return
    md = Path(args.md).read_text(encoding="utf-8", errors="replace")

    # 仅论文生效: 教材没有 abstract/贡献陈述结构, 摘要-贡献审计对它是噪声。
    # advmath 论文来自 stratum-to-aii, 带 `doc_type: paper` frontmatter; 教材没有。
    if "doc_type:paper" not in md[:500].lower().replace(" ", ""):
        print(f"  recall_audit [{SUB}]: 非论文(无 doc_type:paper), 跳过", flush=True)
        return

    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT title, natural_text FROM aii.ku_onto WHERE substrate_id=$1", SUB
    )
    await conn.close()
    if not rows:
        print(f"  recall_audit [{SUB}]: 无KU(书可能未完/失败), 跳过", flush=True)
        return

    client = httpx.AsyncClient(timeout=90)
    ext = await _chat(client, EXTRACT_SYS, _contribution_context(md), key)
    contribs = ext.get("contributions", []) if isinstance(ext, dict) else []
    if ext.get("error") or not contribs:
        await client.aclose()
        print(
            f"  recall_audit [{SUB}]: 贡献抽取失败/为空({ext.get('error', '')})——不拦截", flush=True
        )
        return

    ku_list = "\n".join(
        f"- {r['title']}: {re.sub(chr(10) + '+', ' ', (r['natural_text'] or ''))[:140]}"
        for r in rows
    )
    cov_in = (
        "核心贡献:\n"
        + json.dumps(contribs, ensure_ascii=False)
        + f"\n\n已抽取KU({len(rows)}条):\n"
        + ku_list
    )
    cov = await _chat(client, COVER_SYS, cov_in, key)
    await client.aclose()
    results = cov.get("results", []) if isinstance(cov, dict) else []
    if cov.get("error") or not results:
        print(f"  recall_audit [{SUB}]: 覆盖核对失败({cov.get('error', '')})——不拦截", flush=True)
        return

    by_id = {c["id"]: c for c in contribs if "id" in c}
    misses = [r for r in results if not r.get("covered")]
    report = {
        "substrate": SUB,
        "ku_count": len(rows),
        "contributions_total": len(contribs),
        "covered": len(contribs) - len(misses),
        "misses": [
            {
                "kind": by_id.get(r["id"], {}).get("kind"),
                "statement": by_id.get(r["id"], {}).get("statement"),
                "note": r.get("note"),
            }
            for r in misses
        ],
    }
    outdir = ROOT / "advmath_pipeline" / "recall_audit"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{SUB}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

    cov_n = report["covered"]
    print(
        f"  recall_audit [{SUB}]: 论文自称核心贡献 {cov_n}/{len(contribs)} 已被KU覆盖"
        f"{'; ⚠可能漏:' if misses else ' ✓无遗漏'}",
        flush=True,
    )
    for m in report["misses"][:12]:
        print(f"    ⚠[{m['kind']}] {(m['statement'] or '')[:90]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
