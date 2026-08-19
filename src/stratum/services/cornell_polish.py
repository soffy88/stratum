"""用 NIM 润色康奈尔笔记: 线索问更自然、总结更凝练、一句话记忆更好记。

硬顶: 每 key 40 rpm (NIM 免费层)。默认读 aii/.pipeline_keys.json 轮转。
命门: 只改 cues/summary/oneLiner/hints; **不改 modules.body 原文**(B仓片段不可臆造)。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "aii" / ".pipeline_keys.json",
    Path("/opt/aii") / ".." / ".pipeline_keys.json",  # unlikely
    Path(os.environ.get("AII_ROOT", "/data/soffy/projects/stratum/aii")) / ".pipeline_keys.json",
]

NIM_BASE = "https://integrate.api.nvidia.com/v1/chat/completions"
# 润色要稳定 JSON: nemotron-super 常 content=null、只吐 reasoning 且截断。
# 默认 llama-3.1-70b; 可用 CORNELL_NIM_MODEL / NIM_MODEL 覆盖。
NIM_MODEL = os.getenv(
    "CORNELL_NIM_MODEL",
    os.getenv("NIM_MODEL", "meta/llama-3.1-70b-instruct"),
)
NIM_RPM = min(float(os.getenv("NIM_RPM", "40")), float(os.getenv("NIM_RPM_CAP", "40")))
NIM_FREE_TIER = 40.0

POLISH_SYS = """你是学习笔记编辑。任务: 把康奈尔笔记的「线索问题/提示/总结/一句话记忆」写得更适合自学。
铁律:
1. 不编造知识点, 不改变学科事实; 只润色问法与记忆句。
2. 线索问 8~12 字到 40 字, 覆盖定义/理由/用法/关系, 避免套话重复。
3. 提示一行内, 给回忆方向不给完整答案。
4. 总结 2~3 句; 一句话记忆 ≤30 字, 好背。
5. 只输出 JSON, 不要 markdown 围栏。
输出格式:
{
  "cues": [{"id":"q1","text":"...","hint":"..."}, ...],  // 必须覆盖输入的全部 id
  "summary": "...",
  "oneLiner": "..."
}
"""


def _load_keys() -> list[tuple[str, str]]:
    for p in ROOT_CANDIDATES:
        try:
            if p.exists():
                raw = json.loads(p.read_text())
                return [(k, v) for k, v in raw.items() if isinstance(v, str) and v.strip()]
        except Exception:
            continue
    env = os.getenv("NVIDIA_NIM_API_KEY", "").strip()
    return [("env", env)] if env else []


class _KeyThrottle:
    """每 key 独立时间槽限流, 间隔 60/rpm 秒。"""

    def __init__(self, rpm: float):
        self._min = 60.0 / rpm if rpm > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if not self._min:
            return
        import time

        with self._lock:
            start = max(time.monotonic(), self._next)
            self._next = start + self._min
        w = start - time.monotonic()
        if w > 0:
            time.sleep(w)


def _call_nim(api_key: str, throttle: _KeyThrottle, prompt: str, *, max_tokens: int = 900) -> str:
    throttle.wait()
    payload = {
        "model": NIM_MODEL,
        "messages": [
            {"role": "system", "content": POLISH_SYS},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    with httpx.Client(timeout=120.0) as client:
        for attempt in range(4):
            r = client.post(
                NIM_BASE,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if r.status_code == 429:
                import time

                time.sleep(2.0 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            # OpenAI-compatible; nemotron 等可能 content=null 而 reasoning 有文
            try:
                msg = data["choices"][0]["message"]
                text = msg.get("content") or msg.get("reasoning") or msg.get("reasoning_content") or ""
                return text if isinstance(text, str) else str(text or "")
            except Exception:
                return json.dumps(data)[:2000]
    raise RuntimeError("NIM rate limited after retries")


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def polish_content(content: dict[str, Any], *, llm: Callable[[str], str] | None = None) -> dict[str, Any]:
    """同步润色; llm(prompt)->str 可注入。失败则原样返回。"""
    cues = content.get("cues") or []
    if not cues:
        return content
    payload = {
        "title": content.get("title"),
        "subject": content.get("subject"),
        "modules": [
            {"id": m.get("id"), "title": m.get("title"), "kind": m.get("kind")}
            for m in (content.get("modules") or [])
        ],
        "cues": [
            {"id": c.get("id"), "mod": c.get("mod"), "text": c.get("text"), "hint": c.get("hint")}
            for c in cues
        ],
        "summary": content.get("summary"),
        "oneLiner": content.get("oneLiner"),
    }
    prompt = (
        "请润色以下康奈尔笔记的线索/总结/记忆句。模块正文不在此改写。\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        if llm is None:
            keys = _load_keys()
            if not keys:
                return content
            thr = _KeyThrottle(NIM_RPM)
            raw = _call_nim(keys[0][1], thr, prompt)
        else:
            raw = llm(prompt)
        j = _extract_json(raw)
        if not j:
            return content
        out = dict(content)
        # merge cues by id
        by_id = {c["id"]: c for c in cues if c.get("id")}
        new_cues = []
        for item in j.get("cues") or []:
            cid = item.get("id")
            if cid not in by_id:
                continue
            base = dict(by_id[cid])
            if item.get("text"):
                base["text"] = str(item["text"])[:80]
            if item.get("hint"):
                base["hint"] = str(item["hint"])[:40]
            new_cues.append(base)
        # keep any missing originals
        seen = {c["id"] for c in new_cues}
        for c in cues:
            if c.get("id") not in seen:
                new_cues.append(c)
        if new_cues:
            out["cues"] = new_cues
        if j.get("summary"):
            out["summary"] = str(j["summary"])[:600]
        if j.get("oneLiner"):
            out["oneLiner"] = str(j["oneLiner"])[:60]
        meta = dict(out.get("meta") or {})
        meta["polished"] = True
        meta["polish_model"] = NIM_MODEL
        out["meta"] = meta
        return out
    except Exception as e:  # noqa: BLE001
        meta = dict(content.get("meta") or {})
        meta["polish_error"] = str(e)[:120]
        content = dict(content)
        content["meta"] = meta
        return content


async def polish_content_async(content: dict[str, Any], key_index: int = 0) -> dict[str, Any]:
    keys = _load_keys()
    if not keys:
        return content
    thr = _KeyThrottle(NIM_RPM)
    name, key = keys[key_index % len(keys)]

    def _run():
        return polish_content(content, llm=lambda p: _call_nim(key, thr, p))

    return await asyncio.to_thread(_run)


def build_drills(content: dict[str, Any]) -> list[dict[str, Any]]:
    """从模块生成默写题(不需 LLM)。"""
    drills = []
    # 1) 一句话记忆
    if content.get("oneLiner"):
        drills.append(
            {
                "id": "d_oneliner",
                "kind": "recall",
                "prompt": "默写「一句话记忆」",
                "answer": content["oneLiner"].strip(),
                "mod": None,
            }
        )
    # 2) 定义模块首段要点
    for m in content.get("modules") or []:
        if m.get("kind") in ("conceptual", None) and m.get("body"):
            body = m["body"]
            # 取 **要点：** 行或第一句
            ans = ""
            mm = re.search(r"\*\*要点[：:]\*\*\s*(.+)", body)
            if mm:
                ans = mm.group(1).strip()[:120]
            if not ans:
                # first non-empty line
                for line in body.splitlines():
                    line = line.strip().strip("-").strip()
                    if len(line) >= 8 and not line.startswith("---"):
                        ans = line[:120]
                        break
            if ans:
                drills.append(
                    {
                        "id": f"d_{m.get('id', 'm')}",
                        "kind": "definition",
                        "prompt": f"默写模块「{m.get('title')}」的核心句",
                        "answer": ans,
                        "mod": m.get("id"),
                    }
                )
            break
    # 3) 公式型: 含 = 或 LaTeX
    for m in content.get("modules") or []:
        body = m.get("body") or ""
        if re.search(r"[=≈≤≥]|\\frac|\\sum", body):
            for line in body.splitlines():
                if re.search(r"[=≈≤≥]|\\frac", line) and len(line.strip()) < 100:
                    drills.append(
                        {
                            "id": f"d_formula_{m.get('id')}",
                            "kind": "formula",
                            "prompt": f"默写公式/关系式（模块「{m.get('title')}」）",
                            "answer": line.strip()[:100],
                            "mod": m.get("id"),
                        }
                    )
                    break
    return drills[:5]
