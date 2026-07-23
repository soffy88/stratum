#!/usr/bin/env python3
"""context-compiler C仓编译器 — 归档区文件 → cx 判断资产(编译 SPEC, 阶段: pilot)。

链路: archive_registry(compiled=0) → Triage 分流 → LLM 提炼 CBR → cx 表(grade=unverified)
      → registry 标 compiled=1。

Triage(按 archiver 的受控 type):
  decisions / postmortem → cx.decision_case(CBR六件套; postmortem 重点在 lesson)
  methodology            → cx.methodology
  spec / reference / raw → 本阶段跳过不编译(reference=他人资料非自己判断;
                           raw=未加工; spec=设计文档, 编译价值待下阶段定)——
                           不消耗 LLM, compiled 保持 0, 报告列出。

★go/no-go 门(父 SPEC 阶段1): "复用条件写得出来"是这条线成立的前提。
  decision_case 的 reuse_conditions / methodology 的 applicability 若 LLM 给不出
  实质内容 → 该条 **不入库**(宁缺毋滥), 报告标 gate_fail 等 Wiki 裁决。

纪律: grade 全部默认 unverified(建表默认值, 不显式传); source_files=[file_id] 溯源;
     embedding=BGE-M3(共享 aii-embed 服务, 笔记本 GPU); 默认 dry-run, --do 才写库。

用法:
  .venv/bin/python scripts/context_compiler.py         # dry-run: 提炼并打印, 不写库不标记
  .venv/bin/python scripts/context_compiler.py --do    # 写库
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent
REMOTE = os.getenv("ARCHIVER_REMOTE", "gdrive-rw:")
PIPE_DIR = ROOT / "context_pipeline"
REGISTRY_DB = PIPE_DIR / "archive_registry.sqlite"
REPORT_JSON = PIPE_DIR / "compile_report.json"
DSN = os.getenv("CONTEXT_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_context")
EMBED_URL = os.getenv("AII_EMBED_URL", "http://100.68.226.13:8102")
MAX_LLM_CHARS = 12000

COMPILE_MAP = {
    "decisions": "decision_case",
    "postmortem": "decision_case",
    "methodology": "methodology",
}


def _nim_key() -> str:
    k = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not k:
        try:
            k = json.load(open(ROOT / ".pipeline_keys.json")).get("math_zh", "")
        except Exception:
            pass
    return k


def _llm(prompt: str) -> str:
    os.environ.setdefault("NVIDIA_NIM_API_KEY", _nim_key())
    sys.path.insert(0, str(ROOT))
    from oprim.llm.llm_call import llm_call  # noqa: PLC0415

    for attempt in range(2):  # NIM 偶发 read timeout, 重试一次
        try:
            return llm_call(
                prompt=prompt,
                provider="nvidia_nim",
                model="meta/llama-3.1-70b-instruct",
                max_tokens=2500,
            ).text
        except Exception:
            if attempt == 1:
                raise
            time.sleep(3)
    raise RuntimeError("unreachable")


def _embed(text: str) -> list[float]:
    """BGE-M3 via 共享服务(笔记本GPU)。urllib 不认 no_proxy 的 CIDR, 显式绕代理。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"{EMBED_URL}/embed",
        json.dumps({"texts": [text[:2000]]}).encode(),
        {"Content-Type": "application/json"},
    )
    return json.loads(opener.open(req, timeout=120).read())["embeddings"][0]


def _fetch_file(archived_path: str, td: str) -> str:
    local = Path(td) / hashlib.md5(archived_path.encode()).hexdigest()
    r = subprocess.run(
        ["rclone", "copyto", f"{REMOTE}{archived_path}", str(local), "--retries", "3"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(f"下载失败: {r.stderr[:150]}")
    return local.read_text(encoding="utf-8", errors="replace")


_CASE_PROMPT = """你是决策案例编译器(CBR)。把这份材料提炼成一个决策案例。只返回 JSON。
忠于材料: 材料里没有的信息留 null, 不编造。若材料里根本没有真实的决策/取舍可提炼, 返回 {{"skip": true, "reason": "..."}}。

字段(CBR 六件套):
  title: 一句话案例名
  situation: ①当时面对什么情境、要达成什么目标
  alternatives: ②考虑过的备选方案数组 [{{"option":"...","note":"..."}}](含没选的; 材料没提就 null)
  rationale: ③为什么选了这个
  reuse_conditions: ★④复用条件——这个理由在什么情境下成立、什么情境下会反过来(这是最重要的字段, 认真写; 材料推不出来就写 null, 不硬编)
  result: ⑤后来发生了什么(材料没提就 null)
  lesson: ⑥模式化、可迁移的教训(非事件复述; 没有就 null)

材料(来自 {project}/{typ}, 文件 {name}):
{body}

返回 JSON:"""

_METHOD_PROMPT = """你是方法论编译器。把这份材料提炼成一条可复用方法论。只返回 JSON。
忠于材料, 不编造; 若材料不含可复用做法, 返回 {{"skip": true, "reason": "..."}}。

字段:
  name: 方法论名(短)
  description: 方法论内容(怎么做, 具体步骤/要点)
  applicability: ★适用边界——什么情况适用、什么情况不适用(最重要字段; 材料推不出就 null)

材料(来自 {project}, 文件 {name}):
{body}

返回 JSON:"""


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in LLM reply: {text[:150]}")
    return json.loads(m.group(0))


def _substantive(s) -> bool:
    return isinstance(s, str) and len(s.strip()) >= 20


async def main() -> int:
    do = "--do" in sys.argv
    mode = "执行" if do else "dry-run(提炼打印, 不写库不标记)"
    print(f"★ context-compiler {time.strftime('%Y-%m-%d %H:%M')}  模式: {mode}")
    conn = sqlite3.connect(REGISTRY_DB)
    rows = conn.execute(
        "SELECT file_id, orig_name, archived_path, project, type"
        " FROM archive_registry WHERE compiled=0"
    ).fetchall()
    print(f"  待编译登记: {len(rows)}")

    pg = await asyncpg.connect(DSN) if do else None
    report: dict = {
        "compiled": [],
        "skipped_type": [],
        "skipped_llm": [],
        "gate_fail": [],
        "failed": [],
        "ts": time.strftime("%FT%T"),
    }

    with tempfile.TemporaryDirectory(prefix="ctx_compile_") as td:
        for file_id, name, apath, project, typ in rows:
            target = COMPILE_MAP.get(typ)
            if target is None:
                report["skipped_type"].append({"file": name, "type": typ})
                continue
            print(f"\n── {name} ({project}/{typ} → {target})")
            try:
                body = _fetch_file(apath, td)[:MAX_LLM_CHARS]
                if target == "decision_case":
                    prompt = _CASE_PROMPT.format(project=project, typ=typ, name=name, body=body)
                else:
                    prompt = _METHOD_PROMPT.format(project=project, name=name, body=body)
                out = _parse_json(_llm(prompt))

                if out.get("skip"):
                    print(f"  ⤳ LLM 判无可提炼: {str(out.get('reason', ''))[:80]}")
                    report["skipped_llm"].append({"file": name, "reason": out.get("reason", "")})
                    if do:
                        conn.execute(
                            "UPDATE archive_registry SET compiled=1 WHERE file_id=?", (file_id,)
                        )
                        conn.commit()
                    continue

                # ★go/no-go 门: 复用条件必须有实质内容, 否则不入库(宁缺毋滥)
                key_field = "reuse_conditions" if target == "decision_case" else "applicability"
                if not _substantive(out.get(key_field)):
                    print(f"  ⛔ gate_fail: {key_field} 缺失/空洞 → 不入库, 等 Wiki 裁决")
                    report["gate_fail"].append({"file": name, "target": target, "extracted": out})
                    continue

                print(f"  ✓ 提炼成功; ★{key_field}: {str(out[key_field])[:90]}")
                if not do:
                    report["compiled"].append(
                        {
                            "file": name,
                            "target": target,
                            "dry_run": True,
                            **{k: out.get(k) for k in out if k != "skip"},
                        }
                    )
                    continue

                emb = _embed(
                    out.get("situation")
                    or out.get("description")
                    or out.get("title")
                    or out.get("name")
                    or name
                )
                vec = "[" + ",".join(f"{x:.7f}" for x in emb) + "]"
                if target == "decision_case":
                    rid = await pg.fetchval(
                        """INSERT INTO cx.decision_case
                           (title, project, situation, alternatives, rationale, reuse_conditions,
                            result, lesson, source_files, embedding)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::vector) RETURNING case_id""",
                        out.get("title") or name,
                        project,
                        out.get("situation"),
                        json.dumps(out.get("alternatives"), ensure_ascii=False)
                        if out.get("alternatives")
                        else None,
                        out.get("rationale"),
                        out.get("reuse_conditions"),
                        out.get("result"),
                        out.get("lesson"),
                        json.dumps([file_id]),
                        vec,
                    )
                else:
                    rid = await pg.fetchval(
                        """INSERT INTO cx.methodology
                           (name, description, applicability, embedding)
                           VALUES ($1,$2,$3,$4::vector) RETURNING method_id""",
                        out.get("name") or name,
                        out.get("description"),
                        out.get("applicability"),
                        vec,
                    )
                conn.execute("UPDATE archive_registry SET compiled=1 WHERE file_id=?", (file_id,))
                conn.commit()
                print(f"  ✓ 入库 {target} id={rid} (grade=unverified 默认)")
                report["compiled"].append(
                    {
                        "file": name,
                        "target": target,
                        "id": rid,
                        **{k: out.get(k) for k in out if k != "skip"},
                    }
                )
            except Exception as exc:
                print(f"  ✗ 失败(compiled 保持 0): {exc}")
                report["failed"].append({"file": name, "error": str(exc)[:300]})

    if pg:
        await pg.close()
    n = {
        k: len(report[k])
        for k in ("compiled", "skipped_type", "skipped_llm", "gate_fail", "failed")
    }
    print(
        f"\n══ 编译报告: 入库 {n['compiled']} / 类型跳过 {n['skipped_type']} / "
        f"LLM判无料 {n['skipped_llm']} / 复用条件门拦截 {n['gate_fail']} / 失败 {n['failed']} ══"
    )
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"报告 → {REPORT_JSON}")
    return 0 if n["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
