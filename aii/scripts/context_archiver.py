#!/usr/bin/env python3
"""context-archiver 归档管家 — AII-CONTEXT-REPO-SPEC-001 组件A。

纯文件管家: 读 GDrive alldata/ → 判归属(项目×类型, 受控集合) → 搬到分类目录
→ 登记(本地 SQLite) → 验证成功后把原件移 _pending_delete/(不物理删)。
不碰 PG、不碰判断引擎、不提炼知识。

访问方式(Wiki 拍板 2026-07-12): rclone 命令直连(copyto/moveto/lsjson),
无常驻挂载——现有 ~/gdrive 挂载是只读+仅数学文件夹, 与本管家无关。

命门:
  - 宁冗余不误删: 复制→验证→登记→原件移 _pending_delete(可逆), 绝不物理删;
    物理删除是 Wiki 手动的独立动作。
  - 拿不准不硬分: confidence < 阈值 / 疑似集合外项目 → archive_pending_review,
    原件留在 alldata/ 不动。
  - project/type 只能落在受控集合内, 不自造。
  - sha256 幂等: file_id=sha256, 同一文件再丢不重复归档(原件仍移待删区并记日志)。

指纹验证链(Drive 服务端只有 md5, 没有 sha256):
  ① 下载 alldata 原件到本地 tmp → 算 sha256(=file_id) + md5
  ② 本地 md5 == Drive 原件 md5  → 下载完整性(内容读没读错)
  ③ 服务端 copyto 后, Drive 目标 md5 == Drive 原件 md5 → 搬运完整性
  三者全过才算"验证成功"; 任何一步失败→不动原件, 记 error。

用法:
  .venv/bin/python scripts/context_archiver.py            # dry-run: 只分类打印, 不搬不删不登记
  .venv/bin/python scripts/context_archiver.py --do       # 真跑
  环境: ARCHIVER_CONF_THRESHOLD(默认0.75) / NVIDIA_NIM_API_KEY(缺省读 .pipeline_keys.json 的 math_zh)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# ★现有 gdrive: remote 是 drive.readonly scope(2026-07-12 实测写入 403), 归档需要
# 另一个全权限 remote(rclone config create gdrive-rw drive scope=drive, Wiki 浏览器授权)。
# 用 env 指定, 默认 gdrive-rw:; 只读的 gdrive: 和数学挂载完全不受影响。
REMOTE = os.getenv("ARCHIVER_REMOTE", "gdrive-rw:")
ALLDATA = "alldata"
PENDING_DELETE = "alldata/_pending_delete"
PIPE_DIR = ROOT / "context_pipeline"
REGISTRY_DB = PIPE_DIR / "archive_registry.sqlite"
REPORT_JSON = PIPE_DIR / "archive_report.json"

CONF_THRESHOLD = float(os.getenv("ARCHIVER_CONF_THRESHOLD", "0.75"))
MAX_LLM_CHARS = 6000  # 超长取头部+中段关键片段

PROJECTS = ("helios", "helixa", "helivex", "tide", "selene", "stratum", "hevi", "aegis", "general")
TYPES = ("decisions", "postmortem", "methodology", "spec", "reference", "raw")

# 规则关键词(小写匹配 文件名+相对路径)。项目名本身就是关键词; 别名在此登记。
# ★受控: 新项目不允许自动创建, 疑似集合外 → pending_review。
_PROJECT_KEYWORDS: dict[str, tuple[str, ...]] = {p: (p,) for p in PROJECTS if p != "general"}
_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "decisions": ("adr", "decision", "决策", "取舍", "选型"),
    "postmortem": ("postmortem", "post-mortem", "复盘", "事故", "badcase", "bad_case", "教训"),
    "methodology": ("methodology", "方法论", "sop", "规范", "checklist", "方法"),
    "spec": ("spec", "规格", "设计文档", "impl_spec"),
    "reference": ("reference", "参考", "论文", "paper", "摘录", "文章"),
    "raw": ("聊天导出", "语音转文字", "transcript", "chatlog"),
}


# ── rclone 直连封装 ──────────────────────────────────────────────────────────


def _rclone(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["rclone", *args, "--retries", "3"], capture_output=True, text=True, timeout=timeout
    )


def _lsjson(path: str, recursive: bool = False) -> list[dict]:
    args = ["lsjson", f"{REMOTE}{path}", "--files-only", "--hash"]
    if recursive:
        args.append("--recursive")
    r = _rclone(*args)
    if r.returncode != 0:
        if "directory not found" in r.stderr.lower():
            return []
        raise RuntimeError(f"rclone lsjson {path} failed: {r.stderr[:200]}")
    return json.loads(r.stdout or "[]")


def _exists(path: str) -> bool:
    r = _rclone("lsjson", f"{REMOTE}{path}", "--stat")
    return r.returncode == 0 and bool(r.stdout.strip()) and r.stdout.strip() != "null"


# ── 登记表(SQLite, 文件管家账本, 不进 C仓 PG) ────────────────────────────────


def _db() -> sqlite3.Connection:
    PIPE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REGISTRY_DB)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS archive_registry (
          file_id       TEXT PRIMARY KEY,
          orig_name     TEXT,
          archived_path TEXT,
          project       TEXT,
          type          TEXT,
          classified_by TEXT,
          confidence    REAL,
          status        TEXT DEFAULT 'archived',
          compiled      INTEGER DEFAULT 0,
          archived_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS archive_pending_review (
          file_path   TEXT PRIMARY KEY,
          guess_project TEXT, guess_type TEXT, confidence REAL, reason TEXT,
          created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    return conn


# ── 分类: 规则先行 ───────────────────────────────────────────────────────────


def _classify_by_rule(rel_path: str) -> tuple[str | None, str | None]:
    low = rel_path.lower()
    project = next((p for p, kws in _PROJECT_KEYWORDS.items() if any(k in low for k in kws)), None)
    # Doc ID 前缀(如 HELIVEX-IMPL_SPEC-001): 项目名开头 + 分隔符
    if project is None:
        m = re.match(r"([a-z]+)[-_]", Path(low).name)
        if m and m.group(1) in _PROJECT_KEYWORDS:
            project = m.group(1)
    typ = next((t for t, kws in _TYPE_KEYWORDS.items() if any(k in low for k in kws)), None)
    return project, typ


# ── 分类: LLM 兜底(读内容) ──────────────────────────────────────────────────


def _nim_key() -> str:
    k = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not k:
        try:
            k = json.load(open(ROOT / ".pipeline_keys.json")).get("math_zh", "")
        except Exception:
            pass
    return k


def _classify_by_llm(
    rel_path: str, content: str, hint_project: str | None, hint_type: str | None
) -> dict:
    """返回 {project,type,confidence,reason} 或抛异常。project/type 强制落在受控集合。"""
    os.environ.setdefault("NVIDIA_NIM_API_KEY", _nim_key())
    sys.path.insert(0, str(ROOT))
    from oprim.llm.llm_call import llm_call  # noqa: PLC0415

    body = content[:MAX_LLM_CHARS]
    if len(content) > MAX_LLM_CHARS:
        mid = len(content) // 2
        body = (
            content[: MAX_LLM_CHARS // 2]
            + "\n...[中略]...\n"
            + content[mid : mid + MAX_LLM_CHARS // 2]
        )
    hints = ""
    if hint_project or hint_type:
        hints = f"文件名规则线索: project≈{hint_project or '?'} type≈{hint_type or '?'}\n"
    prompt = (
        "你是文件归档分类器。判断这份材料属于哪个项目、哪种类型。只返回 JSON, 不加解释。\n\n"
        f"project 只能取: {', '.join(PROJECTS)}(general=跨项目/通用/不确定归属; "
        "如果内容明显属于一个不在列表里的新项目, project 填 general 且 confidence ≤ 0.5 并在 reason 里写疑似新项目名)\n"
        f"type 只能取: {', '.join(TYPES)}\n"
        "  decisions=决策/ADR/取舍 | postmortem=复盘/事故教训 | methodology=方法论/SOP/可复用做法 | "
        "spec=设计文档/规格 | reference=他人的参考资料/论文摘录(非自己的判断) | raw=聊天导出/语音转文字等未加工原始输入\n\n"
        f"{hints}文件名: {rel_path}\n文件内容:\n{body}\n\n"
        '返回: {"project": "...", "type": "...", "confidence": 0.0-1.0, "reason": "一句话"}'
    )
    result = llm_call(prompt=prompt, provider="nvidia_nim", model="meta/llama-3.1-70b-instruct")
    m = re.search(r"\{.*\}", result.text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in LLM reply: {result.text[:150]}")
    out = json.loads(m.group(0))
    if out.get("project") not in PROJECTS or out.get("type") not in TYPES:
        raise ValueError(f"LLM 输出越出受控集合: {out}")
    out["confidence"] = float(out.get("confidence", 0))
    return out


# ── 主流程 ───────────────────────────────────────────────────────────────────


def _plan_target(project: str, typ: str, name: str, sha: str) -> str:
    """目标路径; 重名冲突加短哈希后缀, 不覆盖(宁冗余不误删)。"""
    target = f"{project}/{typ}/{name}"
    if _exists(target):
        stem, dot, ext = name.rpartition(".")
        suffixed = f"{stem}.{sha[:8]}.{ext}" if dot else f"{name}.{sha[:8]}"
        target = f"{project}/{typ}/{suffixed}"
    return target


def main() -> int:
    do = "--do" in sys.argv
    mode = "执行" if do else "dry-run(只分类打印, 不搬不删不登记)"
    print(f"★ context-archiver {time.strftime('%Y-%m-%d %H:%M')}  模式: {mode}")
    print(
        f"  阈值 confidence ≥ {CONF_THRESHOLD} 才自动归档; 受控集合 {len(PROJECTS)}项目×{len(TYPES)}类型"
    )

    files = [
        f for f in _lsjson(ALLDATA, recursive=True) if not f["Path"].startswith("_pending_delete/")
    ]
    print(f"  alldata/ 待处理文件: {len(files)}")
    conn = _db()
    report = {
        "archived": [],
        "pending": [],
        "failed": [],
        "duplicate": [],
        "ts": time.strftime("%FT%T"),
    }

    with tempfile.TemporaryDirectory(prefix="ctx_arch_") as td:
        for f in files:
            rel, name = f["Path"], Path(f["Path"]).name
            src = f"{ALLDATA}/{rel}"
            drive_md5 = (f.get("Hashes") or {}).get("md5", "")
            print(f"\n── {rel} ({f.get('Size', '?')}B)")
            try:
                # ① 下载 + 双指纹
                local = Path(td) / hashlib.md5(rel.encode()).hexdigest()
                r = _rclone("copyto", f"{REMOTE}{src}", str(local), timeout=600)
                if r.returncode != 0:
                    raise RuntimeError(f"下载失败: {r.stderr[:150]}")
                blob = local.read_bytes()
                sha = hashlib.sha256(blob).hexdigest()
                if drive_md5 and hashlib.md5(blob).hexdigest() != drive_md5:
                    raise RuntimeError("下载 md5 与 Drive 原件不一致")

                # sha256 幂等: 已归档过的同内容文件 → 不重复归档, 原件仍移待删区
                row = conn.execute(
                    "SELECT archived_path FROM archive_registry WHERE file_id=?", (sha,)
                ).fetchone()
                if row:
                    print(f"  ≡ 重复(sha256 已归档于 {row[0]}), 跳过归档")
                    if do:
                        _rclone("moveto", f"{REMOTE}{src}", f"{REMOTE}{PENDING_DELETE}/{name}")
                    report["duplicate"].append({"file": rel, "existing": row[0]})
                    continue

                # ② 分类: 规则 → LLM 兜底
                proj, typ = _classify_by_rule(rel)
                if proj and typ:
                    cls = {
                        "project": proj,
                        "type": typ,
                        "confidence": 1.0,
                        "reason": "filename rule",
                    }
                    by = "rule"
                else:
                    text = blob.decode("utf-8", errors="replace")
                    cls = _classify_by_llm(rel, text, proj, typ)
                    by = "llm"
                print(
                    f"  → {cls['project']}/{cls['type']} conf={cls['confidence']:.2f} by={by} ({cls['reason'][:60]})"
                )

                # ③ 置信度门槛: 不足 → 待确认队列, 不硬分
                if cls["confidence"] < CONF_THRESHOLD:
                    print("  ⏸ confidence 不足 → archive_pending_review(原件不动)")
                    if do:
                        conn.execute(
                            "INSERT OR REPLACE INTO archive_pending_review VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                            (src, cls["project"], cls["type"], cls["confidence"], cls["reason"]),
                        )
                        conn.commit()
                    report["pending"].append({"file": rel, **cls})
                    continue

                target = _plan_target(cls["project"], cls["type"], name, sha)
                if not do:
                    print(f"  [dry-run] 将归档 → {target}")
                    report["archived"].append(
                        {"file": rel, "target": target, **cls, "by": by, "dry_run": True}
                    )
                    continue

                # ④ 服务端复制 + ★验证(目标存在 且 目标md5==原件md5)
                r = _rclone("copyto", f"{REMOTE}{src}", f"{REMOTE}{target}", timeout=600)
                if r.returncode != 0:
                    raise RuntimeError(f"copyto 失败: {r.stderr[:150]}")
                tgt_stat = _lsjson(target) or (
                    [
                        json.loads(
                            _rclone("lsjson", f"{REMOTE}{target}", "--stat", "--hash").stdout
                            or "null"
                        )
                    ]
                    if _exists(target)
                    else []
                )
                tgt_md5 = (
                    ((tgt_stat[0] or {}).get("Hashes") or {}).get("md5", "") if tgt_stat else ""
                )
                if not tgt_stat or (drive_md5 and tgt_md5 != drive_md5):
                    raise RuntimeError(
                        f"搬运验证失败: 目标缺失或 md5 不一致({tgt_md5} vs {drive_md5})"
                    )

                # ⑤ 登记 → ⑥ 原件移待删区(不物理删)
                conn.execute(
                    "INSERT INTO archive_registry (file_id, orig_name, archived_path, project, type, classified_by, confidence) VALUES (?,?,?,?,?,?,?)",
                    (sha, name, target, cls["project"], cls["type"], by, cls["confidence"]),
                )
                conn.commit()
                r = _rclone("moveto", f"{REMOTE}{src}", f"{REMOTE}{PENDING_DELETE}/{name}")
                if r.returncode != 0:
                    print(f"  ⚠ 原件移待删区失败(归档已成功, 原件留在 alldata): {r.stderr[:120]}")
                print(f"  ✓ 已归档 → {target}; 原件 → _pending_delete/")
                report["archived"].append(
                    {"file": rel, "target": target, **cls, "by": by, "sha256": sha}
                )

            except Exception as exc:  # 验证失败/LLM失败等: 不动原件, 记 error
                print(f"  ✗ 失败(原件不动): {exc}")
                report["failed"].append({"file": rel, "error": str(exc)[:300]})

    n_a, n_p, n_f, n_d = (len(report[k]) for k in ("archived", "pending", "failed", "duplicate"))
    print(f"\n══ 归档报告: 归档 {n_a} / 待确认 {n_p} / 失败 {n_f} / 重复 {n_d} ══")
    PIPE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"报告 → {REPORT_JSON}")
    return 0 if n_f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
