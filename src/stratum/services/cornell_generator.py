"""从 B仓 (aii_refined) 核心概念 + 关联 KU 组装康奈尔笔记内容。

不强制 LLM: 用结构化规则把已去重的 refined_ku 编成线索栏/笔记模块/总结。
命门: 忠实原文片段, 不臆造; 人类可读优先。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras

REFINED_DSN = os.environ.get(
    "REFINED_DATABASE_URL",
    os.environ.get(
        "REFINED_URL",
        "postgresql://aii:aii_safe_pass@127.0.0.1:5436/aii_refined",
    ),
)

_CJK = re.compile(r"[\u4e00-\u9fff]")


def _has_cjk(s: str | None) -> bool:
    return bool(s and _CJK.search(s))


def refined_connect():
    return psycopg2.connect(REFINED_DSN)


def topic_id_for_concept(concept_id: int, name: str | None) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", (name or "").strip())[:40].strip("-")
    if not slug:
        slug = "c"
    return f"c{concept_id}-{slug}".lower()


def _q(text: str, kind: str) -> str:
    t = (text or "").strip()
    if not t:
        return "这个知识点讲了什么？"
    if kind == "conceptual":
        return f"什么是「{t}」？如何准确定义它？"
    if kind == "rationale":
        return f"为什么「{t}」成立？其背后理由是什么？"
    if kind == "procedural":
        return f"如何运用「{t}」？关键步骤是什么？"
    if kind == "factual":
        return f"关于「{t}」的关键事实有哪些？"
    return f"「{t}」要记住什么？"


def _hint(kind: str) -> str:
    return {
        "conceptual": "看定义与判别条件",
        "rationale": "看推导/原因链条",
        "procedural": "看步骤与注意点",
        "factual": "看事实与出处",
        "relational": "看概念之间关系",
    }.get(kind, "对照笔记栏对应模块")


def _clip(s: str | None, n: int = 1200) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _body_from_ku(row: dict) -> str:
    zh = row.get("natural_text_zh") or ""
    en = row.get("natural_text") or ""
    point = row.get("point_zh") or row.get("point") or ""
    parts = []
    if point:
        parts.append(f"**要点：** {point}")
    text = zh if _has_cjk(zh) else en
    if text:
        parts.append(_clip(text, 1600))
    elif en and zh and en != zh:
        parts.append(_clip(en, 800))
    # contributions 原文片段
    contribs = row.get("contributions")
    if isinstance(contribs, str):
        try:
            contribs = json.loads(contribs)
        except Exception:
            contribs = []
    if isinstance(contribs, list) and contribs and not text:
        frags = [
            (c.get("fragment_text") or "").strip()
            for c in contribs
            if isinstance(c, dict) and c.get("fragment_text")
        ]
        if frags:
            parts.append(_clip(frags[0], 1200))
    return "\n\n".join(parts) if parts else "（暂无正文，待补全）"


def fetch_concept_bundle(concept_id: int, *, max_kus: int = 8) -> dict[str, Any] | None:
    """读 B仓 一个概念 + 其关联 refined_ku。"""
    conn = refined_connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT concept_id, name, name_zh, discipline, aliases, discriminative "
                "FROM rf.refined_concept WHERE concept_id=%s",
                (concept_id,),
            )
            concept = cur.fetchone()
            if not concept:
                return None
            cur.execute(
                """
                SELECT k.ku_id, k.point, k.point_zh, k.ku_type, k.natural_text, k.natural_text_zh,
                       k.contributions, k.grade
                FROM rf.refined_ku k
                JOIN rf.refined_ku_concept kc ON kc.ku_id = k.ku_id
                WHERE kc.concept_id = %s
                ORDER BY
                  CASE k.ku_type
                    WHEN 'conceptual' THEN 0
                    WHEN 'rationale' THEN 1
                    WHEN 'procedural' THEN 2
                    WHEN 'factual' THEN 3
                    ELSE 4
                  END,
                  k.updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (concept_id, max_kus),
            )
            kus = [dict(r) for r in cur.fetchall()]
            # 有向边：涉及本概念的
            cur.execute(
                """
                SELECT e.relation_type, e.strength,
                       s.concept_id AS src_id, s.name AS src_name, s.name_zh AS src_zh,
                       d.concept_id AS dst_id, d.name AS dst_name, d.name_zh AS dst_zh
                FROM rf.refined_directed_edge e
                JOIN rf.refined_concept s ON s.concept_id = e.src_concept
                JOIN rf.refined_concept d ON d.concept_id = e.dst_concept
                WHERE e.src_concept = %s OR e.dst_concept = %s
                ORDER BY e.strength DESC NULLS LAST
                LIMIT 12
                """,
                (concept_id, concept_id),
            )
            edges = [dict(r) for r in cur.fetchall()]
        return {"concept": dict(concept), "kus": kus, "edges": edges}
    finally:
        conn.close()


def list_core_concept_ids(*, discipline: str | None = None, limit: int = 50) -> list[int]:
    """核心概念 = 关联 KU 数最多的 canonical 概念。"""
    conn = refined_connect()
    try:
        with conn.cursor() as cur:
            where = ""
            args: list[Any] = []
            if discipline:
                where = "AND c.discipline = %s"
                args.append(discipline)
            args.append(limit)
            cur.execute(
                f"""
                SELECT c.concept_id, count(kc.ku_id) AS n
                FROM rf.refined_concept c
                JOIN rf.refined_ku_concept kc ON kc.concept_id = c.concept_id
                WHERE c.name IS NOT NULL AND c.name <> ''
                {where}
                GROUP BY c.concept_id
                HAVING count(kc.ku_id) >= 2
                ORDER BY n DESC, c.concept_id
                LIMIT %s
                """,
                args,
            )
            return [int(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


def build_cornell_content(bundle: dict[str, Any]) -> dict[str, Any]:
    """组装交互式康奈尔 content JSON (方案 §5)。"""
    c = bundle["concept"]
    kus = bundle["kus"]
    edges = bundle.get("edges") or []
    name = c.get("name_zh") if _has_cjk(c.get("name_zh")) else (c.get("name") or "未命名概念")
    name_en = c.get("name") if c.get("name") and c.get("name") != name else None
    title = name if not name_en else f"{name}（{name_en}）"
    topic_id = topic_id_for_concept(int(c["concept_id"]), c.get("name") or name)
    subject = c.get("discipline") or "unknown"

    # 模块: 定义 / 理由 / 方法 / 关系 / 原文摘录
    modules: list[dict] = []
    cues: list[dict] = []
    by_type: dict[str, list] = {}
    for ku in kus:
        by_type.setdefault(ku.get("ku_type") or "conceptual", []).append(ku)

    mod_i = 0

    def add_mod(title_m: str, body: str, kind: str, cue_text: str | None = None, hint: str | None = None):
        nonlocal mod_i
        mod_i += 1
        mid = f"m{mod_i}"
        modules.append({"id": mid, "title": title_m, "body": body, "kind": kind})
        qid = f"q{mod_i}"
        cues.append(
            {
                "id": qid,
                "mod": mid,
                "text": cue_text or _q(title_m, kind),
                "hint": hint or _hint(kind),
            }
        )

    # 1 定义模块
    defs = by_type.get("conceptual") or kus[:1]
    if defs:
        bodies = [_body_from_ku(k) for k in defs[:2]]
        add_mod(
            "定义与核心表述",
            "\n\n---\n\n".join(bodies),
            "conceptual",
            f"什么是「{name}」？核心定义是什么？",
            "先默写定义，再对照",
        )

    # 2 理由/原理
    rats = by_type.get("rationale") or []
    if rats:
        add_mod(
            "原理与理由",
            "\n\n---\n\n".join(_body_from_ku(k) for k in rats[:2]),
            "rationale",
            f"为什么需要「{name}」？它解决什么问题？",
        )

    # 3 方法/步骤
    procs = by_type.get("procedural") or []
    if procs:
        add_mod(
            "方法与步骤",
            "\n\n---\n\n".join(_body_from_ku(k) for k in procs[:2]),
            "procedural",
            f"如何应用「{name}」？步骤是什么？",
        )

    # 4 事实
    facts = by_type.get("factual") or []
    if facts:
        add_mod(
            "关键事实",
            "\n\n---\n\n".join(_body_from_ku(k) for k in facts[:2]),
            "factual",
            f"与「{name}」相关的关键事实？",
        )

    # 5 关系骨架
    if edges:
        lines = []
        for e in edges[:8]:
            sn = e.get("src_zh") or e.get("src_name")
            dn = e.get("dst_zh") or e.get("dst_name")
            lines.append(f"- **{sn}** —{e.get('relation_type')}→ **{dn}**")
        add_mod(
            "概念关系（有向边）",
            "\n".join(lines),
            "relational",
            f"「{name}」与哪些概念有推导/先修/包含关系？",
            "对照有向边类型",
        )

    # 若模块过少, 把剩余 KU 塞进「补充」
    used = set()
    for lst in (defs, rats, procs, facts):
        for k in lst[:2]:
            used.add(k["ku_id"])
    extra = [k for k in kus if k["ku_id"] not in used]
    if extra and len(modules) < 3:
        add_mod(
            "补充笔记",
            "\n\n---\n\n".join(_body_from_ku(k) for k in extra[:3]),
            "conceptual",
            f"还有哪些关于「{name}」的要点？",
        )
    if not modules:
        add_mod(
            "笔记",
            f"概念「{title}」暂无足够关联 KU，请稍后重新生成。",
            "conceptual",
            f"「{name}」目前有哪些材料？",
        )

    # 保证 8–12 线索(mneme 交互契约): 不够则从 point 补问
    if len(cues) < 8:
        for k in kus:
            if len(cues) >= 12:
                break
            pt = k.get("point_zh") or k.get("point") or name
            mid = modules[min(len(cues), len(modules) - 1)]["id"]
            cues.append(
                {
                    "id": f"q{len(cues) + 1}",
                    "mod": mid,
                    "text": _q(str(pt)[:40], k.get("ku_type") or "conceptual"),
                    "hint": _hint(k.get("ku_type") or "conceptual"),
                }
            )

    # 保证 4–8 模块(mneme 契约): 不足时从 KU 要点建"要点模块"
    if len(modules) < 4:
        used_pts = {k.get("point_zh") or k.get("point") for k in kus[:4]}
        for k in kus:
            if len(modules) >= 4:
                break
            pt = k.get("point_zh") or k.get("point") or ""
            if not pt or pt in used_pts:
                continue
            used_pts.add(pt)
            body = _body_from_ku(k) or pt
            mod_i += 1
            mid = f"m{mod_i}"
            modules.append({"id": mid, "title": f"要点：{str(pt)[:24]}",
                            "body": body, "kind": k.get("ku_type") or "conceptual"})
            if len(cues) < 12:
                cues.append({
                    "id": f"q{len(cues) + 1}",
                    "mod": mid,
                    "text": f"关于「{str(pt)[:40]}」你能说出什么？",
                    "hint": _hint(k.get("ku_type") or "conceptual"),
                })

    # 总结
    pts = [k.get("point_zh") or k.get("point") for k in kus[:4] if k.get("point_zh") or k.get("point")]
    summary = (
        f"「{title}」属于 {subject} 领域。"
        + (" 关联要点：" + "；".join(str(p) for p in pts[:3]) + "。" if pts else "")
        + f" 本笔记由 B仓 {len(kus)} 条去重 KU 自动汇编，可与人工笔记对照学习。"
    )
    one = pts[0] if pts else f"抓住「{name}」的定义—理由—用法三条线。"

    content = {
        "version": 1,
        "topicId": topic_id,
        "title": title,
        "subject": subject,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cues": cues,
        "modules": modules,
        "summary": summary,
        "oneLiner": one if isinstance(one, str) else str(one),
        "meta": {
            "concept_id": int(c["concept_id"]),
            "name": c.get("name"),
            "name_zh": c.get("name_zh"),
            "ku_count": len(kus),
            "edge_count": len(edges),
            "generator": "cornell_generator/v1",
        },
    }
    # 默写题(规则生成, 不依赖 LLM)
    try:
        from stratum.services.cornell_polish import build_drills

        content["drills"] = build_drills(content)
    except Exception:
        content["drills"] = []
    return content


def generate_for_concept(
    concept_id: int, *, max_kus: int = 8, polish: bool = False
) -> dict[str, Any] | None:
    bundle = fetch_concept_bundle(concept_id, max_kus=max_kus)
    if not bundle or not bundle["kus"]:
        return None
    content = build_cornell_content(bundle)
    if polish:
        try:
            from stratum.services.cornell_polish import polish_content, build_drills

            content = polish_content(content)
            content["drills"] = build_drills(content)
        except Exception as e:  # noqa: BLE001
            meta = dict(content.get("meta") or {})
            meta["polish_error"] = str(e)[:120]
            content["meta"] = meta
    ku_ids = [k["ku_id"] for k in bundle["kus"]]
    return {
        "topic_id": content["topicId"],
        "title": content["title"],
        "subject": content["subject"],
        "source": "machine",
        "refined_ku_ids": ku_ids,
        "refined_concept_ids": [int(bundle["concept"]["concept_id"])],
        "content": content,
    }


def stable_note_id(topic_id: str, source: str = "machine") -> str:
    h = hashlib.sha1(f"{source}:{topic_id}".encode()).hexdigest()[:16]
    return f"cn_{h}"
