"""段落锚点：从 highlight/snippet 反查文档中的位置，供检索/问答出处定位。"""

from __future__ import annotations

import re
from typing import Any


def split_paragraphs(text: str) -> list[str]:
    if not text:
        return []
    # Prefer blank-line paragraphs; fallback fixed windows
    parts = re.split(r"\n\s*\n", text)
    paras = [p.strip() for p in parts if p and p.strip()]
    if len(paras) <= 1 and len(text) > 400:
        # sliding chunks ~300 chars
        paras = []
        step = 280
        for i in range(0, len(text), step):
            chunk = text[i : i + step].strip()
            if chunk:
                paras.append(chunk)
    return paras


def locate_anchor(full_text: str, highlight: str | None) -> dict[str, Any]:
    """Return paragraph_index, char_start, char_end, snippet for a highlight in full_text."""
    text = full_text or ""
    hl = (highlight or "").strip()
    paras = split_paragraphs(text)

    if not hl:
        snippet = (paras[0][:240] if paras else text[:240]) or ""
        return {
            "paragraph_index": 0 if paras else None,
            "char_start": 0,
            "char_end": min(len(snippet), len(text)),
            "snippet": snippet,
            "anchor_status": "head",
        }

    # exact / fuzzy locate
    idx = text.find(hl[:80])
    if idx < 0:
        # try whitespace-normalized
        compact_hl = re.sub(r"\s+", "", hl[:60])
        compact_text = re.sub(r"\s+", "", text)
        cidx = compact_text.find(compact_hl)
        if cidx >= 0:
            # approximate map back
            idx = max(0, min(len(text) - 1, int(cidx * len(text) / max(len(compact_text), 1))))
        else:
            # paragraph score by overlap
            best_i, best_score = 0, -1.0
            tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", hl.lower()))
            for i, p in enumerate(paras):
                pt = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", p.lower()))
                if not tokens:
                    score = 0.0
                else:
                    score = len(tokens & pt) / len(tokens)
                if score > best_score:
                    best_score, best_i = score, i
            p = paras[best_i] if paras else text[:240]
            start = text.find(p[:40]) if p else 0
            if start < 0:
                start = 0
            return {
                "paragraph_index": best_i if paras else None,
                "char_start": start,
                "char_end": start + len(p),
                "snippet": p[:280],
                "anchor_status": "approx",
                "score": round(best_score, 3),
            }

    end = idx + min(len(hl), 400)
    # which paragraph
    p_idx = 0
    cursor = 0
    for i, p in enumerate(paras):
        pos = text.find(p, cursor)
        if pos < 0:
            continue
        if pos <= idx < pos + len(p) + 2:
            p_idx = i
            break
        cursor = pos + len(p)

    snippet = text[max(0, idx - 40) : min(len(text), end + 80)]
    return {
        "paragraph_index": p_idx,
        "char_start": idx,
        "char_end": end,
        "snippet": snippet.strip(),
        "anchor_status": "exact",
    }


def enrich_result_with_anchor(
    *,
    substrate_id: str,
    title: str | None,
    highlight: str | None,
    full_text: str | None,
    score: float | None = None,
) -> dict[str, Any]:
    anchor = locate_anchor(full_text or "", highlight)
    return {
        "substrate_id": substrate_id,
        "title": title or substrate_id,
        "score": score,
        "highlight": highlight,
        "paragraph_index": anchor.get("paragraph_index"),
        "char_start": anchor.get("char_start"),
        "char_end": anchor.get("char_end"),
        "snippet": anchor.get("snippet"),
        "anchor_status": anchor.get("anchor_status"),
        "deep_link": f"stratum://substrate/{substrate_id}"
        + (
            f"#p{anchor['paragraph_index']}"
            if anchor.get("paragraph_index") is not None
            else ""
        ),
    }
