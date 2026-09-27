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
    # 不能用“任意句点”做边界：教材里的 0.01、1.5、v2.0 会被拆开，
    # 随后数字级证据补齐就会失效。仅把非小数点的句点视为句末。
    for i, ch in enumerate(text or ""):
        boundary = ch in "。！？!?\n"
        if ch == ".":
            prev_is_digit = i > 0 and text[i - 1].isdigit()
            next_is_digit = i + 1 < len(text) and text[i + 1].isdigit()
            boundary = not (prev_is_digit and next_is_digit)
        if not boundary:
            continue
        raw = text[start : i + 1]
        left = len(raw) - len(raw.lstrip())
        seg = raw.strip()
        if seg:
            out.append((seg, start + left))
        start = i + 1
    tail = text[start:] if text else ""
    if tail.strip():
        left = len(tail) - len(tail.lstrip())
        out.append((tail.strip(), start + left))
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
        if len(sent.strip()) >= 10 and name_key and name_key in sent.lower():
            picked.append((sent, off, "name_hit"))
        if len(picked) >= max_q:
            break
    # 2) 定义/因果句
    for sent, off in sents:
        if len(picked) >= max_q:
            break
        if any((sent, off, "name_hit") == p for p in picked):
            continue
        if len(sent.strip()) >= 10 and _DEF_KW.search(sent):
            picked.append((sent, off, "definition"))
    # 3) 首句兜底
    if not picked:
        first = next(((sent, off) for sent, off in sents if len(sent.strip()) >= 10), None)
        if first:
            picked.append((first[0], first[1], "first_sentence"))
    # 截断超长句(≤ 400 字符), 保持子串性质
    quotes = []
    for sent, off, kind in picked[:max_q]:
        s = sent[:400]
        quotes.append({"quote": s, "span": [off, off + len(s)], "kind": kind})
    return quotes


_CLAIM_NUM_RE = re.compile(r"\d+(?:\.\d+)?%?|\d+(?:[,.]\d+)+")


def _number_tokens(text: str) -> set[str]:
    """抽取数字时兼容 OCR/PDF 把小数点与数字拆开的写法。"""
    normalized = re.sub(r"(?<=\d)\s*[.．]\s*(?=\d)", ".", text or "")
    return set(_CLAIM_NUM_RE.findall(normalized))


def _claim_numbers(claim: str) -> set[str]:
    """提取事实数字，排除多行正文的结构性列表序号。

    LLM 常把一个 KU 写成“1. ...\n2. ...”；这些编号不是书中事实，
    不应要求它们出现在证据句里。教材还常在正文中写“详见1.2节”这类
    章节交叉引用；它们是导航标记而非知识断言，也不应触发数字对齐。
    行内数字、年份、比例和小数仍全部保留，继续接受严格的原文对齐检查。
    """
    # ASCII/全角编号与中文教材常见的“10　正文”编号都属于结构噪声。
    # 小数必须要求点后紧接数字，因此不会误删“1.3 billion”这类事实。
    text = re.sub(
        r"(?m)^\s*(?:#{1,4}\s*)?(?:[-*•]\s*)?(?:\d{1,3}(?:[)]|、|．|。)(?=\s|[\u4e00-\u9fffA-Za-z])"
        r"|\d{1,3}\.(?=\s)|\d{1,3}(?=\u3000+)"
        r"|\d+(?:\.\d+)+(?=\u3000))\s*",
        "",
        claim or "",
    )
    # 骨架抽取可能把原文的多项列表合并进同一行；这些行内“1．/2)/3.”
    # 仍是编号，不是事实数字。小数点后紧跟数字不会命中。
    text = re.sub(
        r"(?<![\d.])(?:\d{1,3}(?:[)）、．。、]|\.(?=\s))(?=\s|[\u4e00-\u9fffA-Za-z])"
        r"|\d{1,3}(?=\u3000+))\s*",
        "",
        text,
    )
    # 只去除明确的章节导航引用，避免误伤正文中的 1.2、1.3 等真实小数。
    text = re.sub(
        r"(?:详见|参见|见|参阅|见第)\s*\d+(?:\.\d+)+\s*(?:章|节|小节)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?<![\d.])\d+(?:\.\d+)+\s*(?:章|节|小节)", "", text)
    return _number_tokens(text)


def check_number_alignment(claim: str, quotes: list[dict]) -> list[str]:
    """反幻觉(数字级): claim 中的数字必须出现在某条 evidence quote 中。

    确定性零模型(规格: 数字/实体对不齐 → reject, 不依赖 NLI)。
    无数字的 claim 直接通过。
    """
    claim_nums = _claim_numbers(claim)
    if not claim_nums:
        return []
    quote_text = " ".join(q.get("quote") or "" for q in (quotes or []))
    quote_nums = _number_tokens(quote_text)
    missing = claim_nums - quote_nums
    if missing:
        return [f"HALLUCINATION: claim 数字 {sorted(missing)} 不在 evidence 中"]
    return []


def ensure_evidence_number_coverage(
    claim: str,
    quotes: list[dict],
    section_text: str,
    name: str = "",
    max_q: int = 8,
    fallback_text: str = "",
) -> list[dict]:
    """从原文窗口补齐 claim 中缺失数字的证据句。

    初始 evidence 选择优先知识点名/定义句，教材中的表格、比例和年份可能
    位于后续句子。先查定向窗口；窗口没有覆盖时再查同一章节的完整原文。
    只从原文逐字句子补证据，不生成或修改任何内容；找不到原文数字时仍由
    check_number_alignment 拒绝。
    """
    out = [
        dict(q)
        for q in (quotes or [])
        if len(str(q.get("quote") or "").strip()) >= 10
    ]
    if len(out) >= max_q:
        return out
    quote_norm = {re.sub(r"\s+", "", (q.get("quote") or "")).lower() for q in out}
    quote_text = " ".join(q.get("quote") or "" for q in out)
    missing = _claim_numbers(claim) - _number_tokens(quote_text)
    if not missing:
        return out
    sources = []
    for label, source in (("window", section_text), ("chapter", fallback_text)):
        if source and source not in [item[1] for item in sources]:
            sources.append((label, source))
    for label, source in sources:
        for sent, off in _split_sentences(source):
            if len(sent.strip()) < 10:
                continue
            nums = _number_tokens(sent)
            if not nums & missing:
                continue
            key = re.sub(r"\s+", "", sent).lower()
            if not key or key in quote_norm:
                continue
            s = sent[:400]
            out.append(
                {
                    "quote": s,
                    "span": [off, off + len(s)],
                    "kind": "number_alignment" if label == "window" else "number_alignment_chapter",
                }
            )
            quote_norm.add(key)
            missing -= _number_tokens(s)
            if not missing or len(out) >= max_q:
                break
        if not missing or len(out) >= max_q:
            break
    return out


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
        "x", "Externalities", "conceptual", "长文本" * 10, build_grounded_by("book", "ch1")
    )
    print("✅ ku_schema 自检通过")
