#!/usr/bin/env python3
"""A 仓入库海关检查 — Source Packet 标准 + KU 强校验层 (P1, 零 LLM 全确定性)。

设计(对齐 roadmap ②):
  [LLM 生成] → [ku_schema 强校验] → [确定性后处理(指纹/引用链)] → [DB 落库]

引用链(grounded_by)是确定性信息 —— 由落库点从调用上下文注入,
绝不依赖 LLM 输出(LLM 只负责内容, 不负责元数据)。

Source Packet 标准:
  {
    "substrate_id": "mankiw_principles_econ_10e",
    "chapter_anchor": "ch1",          # 或 "9"(数字章)
    "text_window": [1024, 2048],      # 原文窗口(未知则 null)
    "parser_version": "markitdown-v0.5",
    "extraction_method": "llm_summary" | "legacy_ingest" | "program_extract"
  }

用法:
    from ku_schema import build_grounded_by, validate_ku_point, ku_fingerprint
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

# ── KU 类型枚举(对齐 aii.ku_onto.knowledge_type 约束) ──────────
KU_TYPES: frozenset[str] = frozenset(
    {"conceptual", "rationale", "procedural", "factual", "positional"}
)
MIN_POINT_LEN = 5
MIN_TEXT_LEN = 20

# ── ku_id → chapter_anchor 解析 ────────────────────────────────
# 格式:  <substrate>::ch<N>_ku<M> | <substrate>::<N>::<name> | <substrate>::ch<N>_...
_CH_RE = re.compile(r"::ch(\d+)", re.IGNORECASE)
_NUM_RE = re.compile(r"::(\d+)::")
_NUM2_RE = re.compile(r"::(\d+)[_:]")


def parse_chapter_anchor(ku_id: str) -> str | None:
    """从 ku_id 解析章锚点(确定性)。解析失败返回 None(不伪造)。"""
    m = _CH_RE.search(ku_id)
    if m:
        return f"ch{m.group(1)}"
    m = _NUM_RE.search(ku_id)
    if m:
        return m.group(1)
    m = _NUM2_RE.search(ku_id)
    if m:
        return m.group(1)
    return None


def ku_fingerprint(natural_text: str) -> str:
    """确定性指纹(去重/追踪用)。"""
    return "sha256:" + hashlib.sha256((natural_text or "").encode("utf-8")).hexdigest()[:40]


def build_grounded_by(
    substrate_id: str,
    chapter_anchor: str | None,
    parser_version: str = "markitdown-v0.5",
    extraction_method: str = "llm_summary",
    text_window: list[int] | None = None,
    evidence_quotes: list[dict] | None = None,
) -> dict:
    """构造 Source Packet(引用链) —— 确定性, 落库点注入。

    evidence_quotes: Grounded 协议证据(claim 级溯源):
        [{"chunk_id": "ch1", "quote": "原文逐字", "span": [s,e], "kind": "definition"}]
    """
    packet = {
        "substrate_id": substrate_id,
        "chapter_anchor": chapter_anchor,
        "text_window": text_window,
        "parser_version": parser_version,
        "extraction_method": extraction_method,
    }
    if evidence_quotes:
        packet["evidence_quotes"] = evidence_quotes
    return packet


def validate_ku_point(
    ku_id: str,
    point: str | None,
    ku_type: str | None,
    natural_text: str | None,
    grounded_by: dict | None,
) -> list[str]:
    """校验单条 KU, 返回违规列表(空 = 通过)。

    规则(全确定性):
      - point ≥ 5 字符(空壳拒绝)
      - natural_text ≥ 20 字符
      - ku_type ∈ 枚举
      - grounded_by 引用链必填且含 substrate_id
    """
    errs: list[str] = []
    if not point or len(point.strip()) < MIN_POINT_LEN:
        errs.append(f"point 过短(<{MIN_POINT_LEN}): {point!r}"[:120])
    if not natural_text or len(natural_text.strip()) < MIN_TEXT_LEN:
        errs.append(f"natural_text 过短(<{MIN_TEXT_LEN})")
    if ku_type not in KU_TYPES:
        errs.append(f"ku_type 非法: {ku_type!r} (枚举 {sorted(KU_TYPES)})")
    if not grounded_by or not grounded_by.get("substrate_id"):
        errs.append("grounded_by 引用链缺失(substrate_id 必填)")
    return errs


_DEF_KW = re.compile(
    r"(is |are |means |defined as |refers to |is called |is known as |"
    r"是指|定义为|称为|指的是|即|表示|定理|定义|命题|公式|because|since|when|if )",
    re.IGNORECASE,
)


def _split_sentences(text: str) -> list[tuple[str, int]]:
    """按句子边界切分, 返回 [(sentence, start_offset)]。"""
    out: list[tuple[str, int]] = []
    start = 0
    for m in re.finditer(r"[^。！？.!?\n]+[。！？.!?\n]*", text):
        seg = m.group(0).strip()
        if seg:
            out.append((seg, m.start()))
    return out


def extract_evidence_quotes(
    section_text: str,
    name: str = "",
    max_q: int = 3,
) -> list[dict]:
    """从合成窗口原文确定性提取证据句(零 LLM)。

    优先级: 含知识点名的句子 → 定义/因果句 → 窗口首句。
    返回: [{"quote": 原文逐字, "span": [start, end](窗口内偏移), "kind": 类型}]
    窗口文本质量差(乱码/过短)时返回 []——调用方据此判 NO_SPAN 协议失败。
    """
    if not section_text or len(section_text.strip()) < 30:
        return []
    sents = _split_sentences(section_text)
    if not sents:
        return []
    picked: list[tuple[str, int, str]] = []
    name_key = (name or "").strip().lower()[:30]
    # 1) 含知识点名
    for sent, off in sents:
        if name_key and name_key in sent.lower():
            picked.append((sent, off, "name_hit"))
        if len(picked) >= max_q:
            break
    # 2) 定义/因果句
    for sent, off in sents:
        if len(picked) >= max_q:
            break
        if any((sent, off, "name_hit") == p for p in picked):
            continue
        if _DEF_KW.search(sent):
            picked.append((sent, off, "definition"))
    # 3) 首句兜底
    if not picked and sents:
        picked.append((sents[0][0], sents[0][1], "first_sentence"))
    # 截断超长句(≤ 400 字符), 保持子串性质
    quotes = []
    for sent, off, kind in picked[:max_q]:
        s = sent[:400]
        quotes.append({"quote": s, "span": [off, off + len(s)], "kind": kind})
    return quotes


_CLAIM_NUM_RE = re.compile(r"\d+(?:\.\d+)?%?|\d+(?:[,.]\d+)+")


def check_number_alignment(claim: str, quotes: list[dict]) -> list[str]:
    """反幻觉(数字级): claim 中的数字必须出现在某条 evidence quote 中。

    确定性零模型(规格: 数字/实体对不齐 → reject, 不依赖 NLI)。
    无数字的 claim 直接通过。
    """
    claim_nums = set(_CLAIM_NUM_RE.findall(claim or ""))
    if not claim_nums:
        return []
    quote_text = " ".join(q.get("quote") or "" for q in (quotes or []))
    quote_nums = set(_CLAIM_NUM_RE.findall(quote_text))
    missing = claim_nums - quote_nums
    if missing:
        return [f"HALLUCINATION: claim 数字 {sorted(missing)} 不在 evidence 中"]
    return []


def validate_quotes(quotes: list[dict], section_text: str) -> list[str]:
    """quote 必须是 section 原文子串(允许空白/引号/大小写规范化)。返回违规列表。"""
    errs: list[str] = []
    norm = lambda t: re.sub(r"[\s\u201c\u201d\"']+", "", t).lower()
    snorm = norm(section_text)
    for q in quotes or []:
        quote = q.get("quote") or ""
        if len(quote) < 10:
            errs.append("quote 过短(<10)")
            continue
        if norm(quote) not in snorm:
            errs.append(f"quote 非原文子串: {quote[:40]}...")
    return errs


def packet_json(packet: dict) -> str:
    return json.dumps(packet, ensure_ascii=False)


if __name__ == "__main__":
    # 自检
    assert parse_chapter_anchor("mankiw::ch1_ku14") == "ch1"
    assert parse_chapter_anchor("math_prog_abc::9::Prop 9.1") == "9"
    assert parse_chapter_anchor("advmath_xyz::ch3_ku13") == "ch3"
    assert parse_chapter_anchor("plain_id") is None
    assert ku_fingerprint("abc") == ku_fingerprint("abc")
    assert ku_fingerprint("abc") != ku_fingerprint("abd")
    assert validate_ku_point("x", "短", "conceptual", "长文本" * 10, None)
    assert not validate_ku_point(
        "x", "Externalities", "conceptual", "长文本" * 10,
        build_grounded_by("book", "ch1"))
    print("✅ ku_schema 自检通过")
