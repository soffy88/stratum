#!/usr/bin/env python3
"""BU 学习层质量门 — 按 su-learning-map 学习内容标准升级教材 BU (P0, 全确定性, 零 LLM).

校验内容(深卡下限与 build_learning_map.py 对齐; 证据规则与 A 仓数据现实对齐):
  路径: 3~7 条; id 唯一; card_ids 全体分区(不重不漏); name/promise 非空
  卡:   id 唯一正整数; 必填字段非空; context≥50; arguments≥3 且合计≥100;
        source_digest≥2 且合计≥220; boundary≥40; connections 解析; practice 可产出具体答案(动作词)
  证据(代码按 KU 数据重算, LLM 无权决定):
        verified 在手 → primary; ≥2 条独立 KU → corroborated; 单条 → primary
        grade ∈ {refuted,contradicted,low} → 丢弃(坏源)
        grade=unverified → 允许但记录 grounding_grades(铁律: 未核实≠坏, 卡上透明标注)
  逐字(verbatim): 卡 excerpt 必须来自 KU 的逐字来源, 二选一(代码解析, 见 _resolve_verbatim):
        a) grounded_by.evidence_quotes(NLLM 书, NO_SPAN 已验证)
        b) extraction_method ∈ {program_extract, legacy_ingest} 时 natural_text 本身
           (0-LLM 程序抠原文, 如 math_prog 的定理原文; LLM 综合书 natural_text 非逐字, 不可用)
        两种都没有 → 卡丢弃(无逐字支撑, NO_SPAN 精神)
  修剪: 丢卡后 connections 悬空 → 再丢(不动点); 空路径 → 丢; 全丢 → insufficient_data

用法:
  作为库: from bu_learning_gate import validate_learning_layer, evidence_class_for, resolve_verbatim
  审计CLI: python bu_learning_gate.py <substrate_id>   (读 DB 里已入库 BU, 校验并打印报告)
Exit(CLI): 0=ok, 1=alarm, 2=运行错误
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

EVIDENCE: frozenset[str] = frozenset({"primary", "corroborated", "external", "inference", "current"})
GRADE_BAD: frozenset[str] = frozenset({"refuted", "contradicted", "low"})
# 0-LLM 程序抠原文路径: natural_text 本身是逐字原文(LLM 综合书不在此列)
PROGRAM_EXTRACT: frozenset[str] = frozenset({"program_extract", "legacy_ingest"})
# 练习必须产出具体答案: 含动作词的祈使性提示(纯陈述句=无法判断完成)
PRACTICE_MARK = re.compile(
    r"写|列出|找出|举|挑|选|改|算|评|设计|判断|回忆|给出|检查|对比|回答|补|画|填"
)
# 七项书级理解: 无 KU 支撑时必须显式对冲(防止把推断写成事实)
FACET_KEYS = ("soul", "positioning", "question", "skeleton", "thinking", "for_whom", "boundary")
HEDGE_MARK = re.compile(
    r"似乎|可能|推断|从结构看|未直接|未见|仅凭|不足以|不涉及|不包含|留白|有限|未知|不确定"
)
FACET_MIN_TEXT = 15
FACET_MIN_BASIS = 30
SKELETON_MIN_HUBS = 2

FLOOR_CONTEXT = 50
FLOOR_ARGUMENTS_N = 3
FLOOR_ARGUMENTS_LEN = 100
FLOOR_DIGEST_N = 2
FLOOR_DIGEST_LEN = 220
FLOOR_BOUNDARY = 40
FLOOR_PRACTICE = 10
MIN_PATHS, MAX_PATHS = 3, 7
MAX_EXCERPT = 150


def evidence_class_for(grades: list[str] | tuple[str, ...] | set[str]) -> str | None:
    """KU grade → 证据分级(确定性, 代码权威)。

    verified 在手 → primary(独立裁判过);
    ≥2 条独立 KU → corroborated(多源印证); 单条(含 unverified) → primary(带逐字定位);
    grade 含 refuted|contradicted|low → None(坏源, 丢弃)。
    unverified 不是坏: grade 铁律=未核实≠不可用, 卡上透明记 grounding_grades。
    """
    gs = set(grades or [])
    if gs & GRADE_BAD:
        return None
    if not gs:
        return None
    if "verified" in gs:
        return "primary"
    if len(gs) >= 2:
        return "corroborated"
    return "primary"


def resolve_verbatim(grounded_by: dict | None, natural_text: str | None) -> list[dict]:
    """解析一条 KU 的逐字来源(代码权威, LLM 不参与)。

    优先 evidence_quotes(NLLM 书, NO_SPAN 已验证);
    其次 0-LLM 程序抠原文(extraction_method ∈ program_extract|legacy_ingest)时 natural_text 本身;
    LLM 综合书(无 quote) → 无逐字来源 → []。
    返回 [{"text","chunk_id","kind"}], kind ∈ quote|text_head。
    """
    gb = grounded_by or {}
    out: list[dict] = []
    for q in gb.get("evidence_quotes") or []:
        t = str(q.get("quote") or "").strip()
        if t:
            out.append({"text": t, "chunk_id": str(q.get("chunk_id") or ""), "kind": "quote"})
    if not out and str(gb.get("extraction_method") or "") in PROGRAM_EXTRACT:
        t = str(natural_text or "").strip()
        if t:
            out.append({"text": t[:MAX_EXCERPT], "chunk_id": str(gb.get("chapter_anchor") or ""), "kind": "text_head"})
    return out


def _insufficient(quality: dict, detail: str) -> dict:
    quality["status"] = "insufficient_data"
    quality["checks"].append({"check": "layer", "status": "fail", "detail": detail})
    return {"ok": False, "paths": [], "cards": [], "quality": quality}


def validate_learning_layer(
    paths: list[dict] | None,
    cards: list[dict] | None,
    ku_meta: dict[str, dict],
) -> dict:
    """校验并修剪学习层。返回 {ok, paths, cards, quality}。

    ku_meta: {ku_id: {"grade": str, "verbatim": [{"text","chunk_id","kind"}]}}
    cards 的 source_excerpts 由调用方(代码)注入; 本函数只校验逐字与一致性, 不生成内容。
    """
    quality: dict[str, Any] = {"status": "ok", "checks": [], "dropped": []}

    def _check(name: str, ok: bool, detail: str = "") -> None:
        quality["checks"].append({"check": name, "status": "pass" if ok else "fail", "detail": detail})

    def _drop(card: dict, reason: str) -> None:
        quality["dropped"].append(
            {"card": card.get("id"), "name": str(card.get("name", ""))[:40], "reason": reason}
        )

    if not isinstance(cards, list) or not cards:
        return _insufficient(quality, "deep_cards 为空")

    # ── 1. id 唯一 + 字段下限 ──────────────────────────────
    kept: dict[int, dict] = {}
    for c in cards:
        cid = c.get("id") if isinstance(c, dict) else None
        if not isinstance(cid, int) or cid <= 0 or cid in kept:
            _drop(c if isinstance(c, dict) else {"id": cid}, "bad_id")
            continue
        kept[cid] = c
    for cid, c in list(kept.items()):
        reasons: list[str] = []
        for f in ("name", "desc", "excerpt", "practice"):
            if not str(c.get(f) or "").strip():
                reasons.append(f"empty_{f}")
        if len(str(c.get("context") or "").strip()) < FLOOR_CONTEXT:
            reasons.append(f"context<{FLOOR_CONTEXT}")
        args = [str(x) for x in (c.get("arguments") or []) if str(x).strip()]
        if len(args) < FLOOR_ARGUMENTS_N:
            reasons.append("arguments<3")
        elif sum(len(a) for a in args) < FLOOR_ARGUMENTS_LEN:
            reasons.append(f"argument_chain<{FLOOR_ARGUMENTS_LEN}")
        dig = [str(x) for x in (c.get("source_digest") or []) if str(x).strip()]
        if len(dig) < FLOOR_DIGEST_N:
            reasons.append("digest<2")
        elif sum(len(x) for x in dig) < FLOOR_DIGEST_LEN:
            reasons.append(f"digest<{FLOOR_DIGEST_LEN}")
        if len(str(c.get("boundary") or "").strip()) < FLOOR_BOUNDARY:
            reasons.append(f"boundary<{FLOOR_BOUNDARY}")
        conns = c.get("connections")
        if not isinstance(conns, list) or not conns:
            reasons.append("no_connections")
        prac = str(c.get("practice") or "").strip()
        if len(prac) < FLOOR_PRACTICE:
            reasons.append("practice_short")
        elif not PRACTICE_MARK.search(prac):
            reasons.append("practice_not_actionable")
        if reasons:
            _drop(c, ",".join(reasons))
            del kept[cid]
            continue
        c["arguments"] = args
        c["source_digest"] = dig
        c["connections"] = [int(x) for x in conns if isinstance(x, int) or str(x).isdigit()]
        if not c["connections"]:
            _drop(c, "no_connections")
            del kept[cid]

    # ── 2. 挂载 KU + 证据分级(代码重算) + 逐字校验 ──────────
    for cid, c in list(kept.items()):
        kids = [k for k in (c.get("ku_ids") or []) if isinstance(k, str)]
        if not kids:
            _drop(c, "no_ku_ids")
            del kept[cid]
            continue
        unknown = [k for k in kids if k not in ku_meta]
        if unknown:
            _drop(c, f"unknown_ku:{unknown[:2]}")
            del kept[cid]
            continue
        grades = [str(ku_meta[k].get("grade", "unverified")) for k in kids]
        ev = evidence_class_for(grades)
        if ev is None:
            _drop(c, "evidence_floor(grades=" + ",".join(grades) + ")")
            del kept[cid]
            continue
        qs: list[dict] = []
        for k in kids:
            allowed = [str(v.get("text") or "") for v in ku_meta[k].get("verbatim", [])]
            for s in (c.get("source_excerpts") or []):
                if not isinstance(s, dict) or s.get("ku_id") != k:
                    continue
                st = str(s.get("text") or "")
                # ★2026-08-16: 落库/复验幂等 — 存储时 excerpt 被截到 MAX_EXCERPT, 而 verbatim
                #   完整原文(quote 路径可达 200+ 字)仍在 allowed 里; 截断文本是完整原文的前缀,
                #   必须放行, 否则审计 CLI 复验已入库数据会误报 no_verbatim_grounding。
                if st and (st in allowed or any(a.startswith(st) for a in allowed)):
                    qs.append({"text": st[:MAX_EXCERPT], "ku_id": k, "locator": s.get("locator", "")})
        if not qs:
            _drop(c, "no_verbatim_grounding")
            del kept[cid]
            continue
        c["source_excerpts"] = qs[:2]
        c["excerpt"] = qs[0]["text"]
        c["evidence"] = ev
        c["ku_ids"] = kids
        c["grounding_grades"] = grades  # ★铁律透明: 未核实≠坏, 但必须可见

    if not kept:
        return _insufficient(quality, "证据底限过后 0 卡存活")
    n_unv = sum(1 for c in kept.values() if set(c["grounding_grades"]) <= {"unverified", "pending"})
    _check("grounding_transparency", True, f"{n_unv} 张卡全部支撑 KU 为 unverified(已逐卡标注 grounding_grades)")

    # ── 3. 路径: 数量 / 分区 / 归属 ─────────────────────────
    pset: dict[str, dict] = {}
    if isinstance(paths, list):
        for p in paths:
            if not isinstance(p, dict):
                continue
            pid = p.get("id")
            if not isinstance(pid, str) or not pid or pid in pset:
                continue
            ids = [int(x) for x in (p.get("card_ids") or []) if isinstance(x, int) or str(x).isdigit()]
            p["card_ids"] = ids
            pset[pid] = p
    if not (MIN_PATHS <= len(pset) <= MAX_PATHS):
        _check("paths_count", False, f"{len(pset)} ∉ [{MIN_PATHS},{MAX_PATHS}]")
    else:
        _check("paths_count", True)
    for pid, p in pset.items():
        for f in ("name", "promise"):
            _check(f"path_{f}", bool(str(p.get(f) or "").strip()), pid)

    seen: set[int] = set()
    for pid, p in pset.items():
        uniq: list[int] = []
        for cid in p["card_ids"]:
            if cid in seen:
                continue
            seen.add(cid)
            uniq.append(cid)
        p["card_ids"] = uniq
    for cid, c in list(kept.items()):
        if c.get("path") not in pset:
            _drop(c, "path_unknown")
            del kept[cid]
    routed = {cid for p in pset.values() for cid in p["card_ids"]}
    orphan = [cid for cid in kept if cid not in routed]
    for cid in orphan:
        _drop(kept[cid], "not_routed")
        del kept[cid]
    stray = [cid for cid in routed if cid not in kept]
    for p in pset.values():
        p["card_ids"] = [cid for cid in p["card_ids"] if cid in kept]
    pset = {pid: p for pid, p in pset.items() if p["card_ids"]}
    _check("partition", not orphan and not stray and bool(kept))

    # ── 4. connections 不动点修剪(悬空连接 → 丢卡) ────────────
    changed = True
    while changed:
        changed = False
        for cid, c in list(kept.items()):
            c["connections"] = [x for x in c["connections"] if x in kept and x != cid]
            if not c["connections"]:
                _drop(c, "connections_pruned")
                del kept[cid]
                changed = True
        for p in pset.values():
            p["card_ids"] = [cid for cid in p["card_ids"] if cid in kept]
        before = len(pset)
        pset = {pid: p for pid, p in pset.items() if p["card_ids"]}
        if len(pset) != before:
            changed = True
        for cid, c in list(kept.items()):
            if c.get("path") not in pset:
                _drop(c, "path_emptied")
                del kept[cid]
                changed = True

    if not kept or not pset:
        return _insufficient(quality, "修剪后无存活卡/路径")
    if not (MIN_PATHS <= len(pset) <= MAX_PATHS):
        quality["status"] = "partial"
        _check("paths_count_after_prune", False, f"{len(pset)} 条路径(下限 {MIN_PATHS})")
    else:
        _check("paths_count_after_prune", True)
    if quality["dropped"]:
        quality["status"] = "partial"

    out_cards: list[dict] = []
    for p in pset.values():
        for cid in p["card_ids"]:
            if kept.get(cid):
                out_cards.append(kept[cid])
    out_paths = [p for p in pset.values()]
    _check("evidence_consistency", all(c["evidence"] in EVIDENCE for c in out_cards))
    _check("verbatim_excerpts", all(c["source_excerpts"] for c in out_cards))
    quality["stats"] = {"paths": len(out_paths), "cards": len(out_cards),
                        "dropped": len(quality["dropped"])}
    return {"ok": True, "paths": out_paths, "cards": out_cards, "quality": quality}


def validate_bu_facets(
    facets: dict | list | None,
    ku_meta: dict[str, dict],
    hub_names: list[str] | None = None,
    kc_labels: list[str] | None = None,
) -> dict:
    """七项书级理解 → 证据挂接版。返回 {ok, facets, quality}。

    每项 {key,text,basis,ku_ids,excerpts?}: text/basis 有下限; ku_ids 必须解析且 grade 非坏源;
    excerpt 必须逐字(代码注入); evidence 由代码按 KU grade 重算(LLM 无权)。
    无 KU 支撑的项: skeleton 必须引用 ≥2 个枢纽概念(数据算出), 其余必须显式对冲(HEDGE_MARK),
    否则丢弃(不编造确定性)。
    """
    quality: dict[str, Any] = {"status": "ok", "checks": [], "dropped": []}
    hubs = set(str(h) for h in (hub_names or []) if h)
    if isinstance(facets, list):
        facets = {str(f.get("key")): f for f in facets if isinstance(f, dict) and f.get("key")}
    if not isinstance(facets, dict):
        quality["status"] = "insufficient_data"
        quality["checks"].append({"check": "facets", "status": "fail", "detail": "facets 非对象"})
        return {"ok": False, "facets": [], "quality": quality}

    out: list[dict] = []
    for key in FACET_KEYS:
        f = facets.get(key)
        if not isinstance(f, dict):
            quality["dropped"].append({"facet": key, "reason": "missing"})
            continue
        text = str(f.get("text") or "").strip()
        basis = str(f.get("basis") or "").strip()
        reasons: list[str] = []
        if len(text) < FACET_MIN_TEXT:
            reasons.append("text_short")
        if len(basis) < FACET_MIN_BASIS:
            reasons.append("basis_short")
        kids = [k for k in (f.get("ku_ids") or []) if isinstance(k, str)]
        unknown = [k for k in kids if k not in ku_meta]
        if unknown:
            reasons.append(f"unknown_ku:{unknown[:2]}")
        if reasons:
            quality["dropped"].append({"facet": key, "reason": ",".join(reasons)})
            continue
        kids = [k for k in kids if str(ku_meta[k].get("grade")) not in GRADE_BAD]
        if kids and len([k for k in (f.get("ku_ids") or []) if k in ku_meta]) != len(kids):
            # 原引用含坏源(已剥除): 记录但不因这一条丢项(剩余 KU 仍可支撑)
            quality["checks"].append({"check": f"facet:{key}", "status": "pass",
                                          "detail": "bad_grade_ku_removed"})
        if (f.get("ku_ids") or []) and not kids:
            quality["dropped"].append({"facet": key, "reason": "all_ku_bad_grade"})
            continue
        exs: list[dict] = []
        for k in kids:
            allowed = [str(v.get("text") or "") for v in ku_meta[k].get("verbatim", [])]
            for s in (f.get("excerpts") or []):
                if not isinstance(s, dict) or s.get("ku_id") != k:
                    continue
                st = str(s.get("text") or "")
                # 同学习层: 存储截断前缀也放行(复验幂等, 见 validate_learning_layer 注释)
                if st and (st in allowed or any(a.startswith(st) for a in allowed)):
                    exs.append({"text": st[:MAX_EXCERPT], "ku_id": k, "locator": s.get("locator", "")})
        if kids and not exs:
            quality["dropped"].append({"facet": key, "reason": "no_verbatim"})
            continue
        grades = [str(ku_meta[k].get("grade", "unverified")) for k in kids]
        ev = evidence_class_for(grades) if kids else "inference"
        struct_hubs = sum(1 for h in hubs if h and h in text)
        if not kids and key == "skeleton" and struct_hubs >= SKELETON_MIN_HUBS:
            quality["checks"].append({"check": f"facet:{key}", "status": "pass", "detail": f"inference(枢纽x{struct_hubs})"})
        elif not kids and not HEDGE_MARK.search(text + basis):
            quality["dropped"].append({"facet": key, "reason": "no_grounding_no_hedge"})
            continue
        else:
            quality["checks"].append({"check": f"facet:{key}", "status": "pass", "detail": ev})
        out.append({"key": key, "text": text, "basis": basis, "ku_ids": kids,
                    "evidence": ev, "grades": grades, "excerpts": exs[:2]})
    if quality["dropped"]:
        quality["status"] = "partial"
    if not out:
        quality["status"] = "insufficient_data"
    quality["stats"] = {"facets": len(out), "dropped": len(quality["dropped"])}
    return {"ok": bool(out), "facets": out, "quality": quality}


# ───────────────────────── 审计 CLI ─────────────────────────
def _cli(substrate: str) -> int:
    import asyncpg
    from pathlib import Path as _P
    from dotenv import load_dotenv

    load_dotenv(_P(__file__).resolve().parents[1] / "aii" / ".env", override=True)

    async def _run():
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        try:
            bu = await conn.fetchrow(
                "SELECT learning_paths, deep_cards, bu_quality, facets_grounded "
                "FROM aii.bu_onto WHERE substrate_id=$1",
                substrate,
            )
            if not bu:
                print(f"无 BU 行: {substrate}")
                return 2
            kus = await conn.fetch(
                "SELECT ku_id, grade, grounded_by, natural_text, natural_text_zh "
                "FROM aii.ku_onto WHERE substrate_id=$1",
                substrate,
            )
        finally:
            await conn.close()
        ku_meta: dict[str, dict] = {}
        for r in kus:
            gb = r["grounded_by"]
            if isinstance(gb, str):  # asyncpg jsonb → str, 需解析
                try:
                    gb = json.loads(gb)
                except json.JSONDecodeError:
                    gb = {}
            ku_meta[r["ku_id"]] = {
                "grade": r["grade"],
                "verbatim": resolve_verbatim(gb, r["natural_text_zh"] or r["natural_text"]),
            }
        def _loads(v):
            # asyncpg 默认把 jsonb 返回为 str, 需解析成结构再入门(否则列表判空误报)
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return None
            return v

        res = validate_learning_layer(_loads(bu["learning_paths"]), _loads(bu["deep_cards"]), ku_meta)
        print("── 学习层 ──")
        print(json.dumps(res["quality"], ensure_ascii=False, indent=2))
        print(f"paths={len(res['paths'])} cards={len(res['cards'])} ok={res['ok']}")
        if bu["facets_grounded"] is not None:
            fg = bu["facets_grounded"]
            if isinstance(fg, str):
                try:
                    fg = json.loads(fg)
                except json.JSONDecodeError:
                    fg = None
            fres = validate_bu_facets(fg, ku_meta)
            print("── 七项(证据挂接) ──")
            print(json.dumps(fres["quality"], ensure_ascii=False, indent=2))
            for f in fres["facets"]:
                print(f"  {f['key']}: {f['evidence']} | ku={len(f['ku_ids'])} | {f['text'][:30]}")
        else:
            print("── 七项(证据挂接) ── 未生成(旧 BU)")
        return 0 if res["ok"] and res["quality"]["status"] == "ok" else 1

    import asyncio

    return asyncio.run(_run())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(_cli(sys.argv[1]))
