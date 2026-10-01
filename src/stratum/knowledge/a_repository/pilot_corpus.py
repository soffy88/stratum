"""A Repository P1 — pilot corpus (deterministic, traceable IDs).

Single source of truth for the frozen Chapter 1 baseline:
利率史（第四版）, Chapter 1 「古代时期的信贷」, pages 1-10.

IDs are deterministic (content-derived) so the frozen baseline is
reproducible and replay-verifiable. Quotes are verbatim spans from
wiki_kb/raw/02_经济学_(NEW)利率史(第4版).md.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List


BOOK_TITLE = "利率史（第四版）"
BOOK_AUTHOR = "[美]悉尼·霍默 理查德·西勒"
BOOK_TRANSLATOR = "曹建海"
BOOK_PUBLISHER = "中信出版社"
BOOK_ISBN = "9787508617497"
BOOK_LANGUAGE = "zh"
BOOK_EDITION = "第四版"

CHAPTER = "第一章 古代时期的信贷"
SOURCE_FORMAT = "PDF"
FILE_VERSION = "PDF-v1"
STORAGE_URI = "local://wiki_kb/raw/02_经济学_(NEW)利率史(第4版).md"
CHECKSUM = hashlib.sha256("利率史-第四版-pilot".encode("utf-8")).hexdigest()
FULL_PAGE_COUNT = 594

EXTRACTOR_VERSION = "p1-v1"

# ── Chapter 1 structure (pages 1-10) ────────────────────────────────────────

SECTIONS: List[Dict] = [
    {
        "section": "1.1",
        "title": "信贷并非现代发明",
        "page_start": 1,
        "page_end": 2,
    },
    {
        "section": "1.2",
        "title": "《汉谟拉比法典》与巴比伦法定利率",
        "page_start": 3,
        "page_end": 5,
    },
    {
        "section": "1.3",
        "title": "索伦法典与古希腊的利率自由化",
        "page_start": 6,
        "page_end": 7,
    },
    {
        "section": "1.4",
        "title": "《十二铜表法》与罗马利率限制",
        "page_start": 8,
        "page_end": 9,
    },
    {
        "section": "1.5",
        "title": "小结：信贷早于文字",
        "page_start": 10,
        "page_end": 10,
    },
]

CHAPTER_PAGE_COUNT = 10

# ── Evidence (verbatim spans, page-anchored) ────────────────────────────────

EVIDENCE: List[Dict] = [
    {
        "key": "ev_credit_ancient",
        "page_number": 1,
        "section": "1.1",
        "evidence_type": "QUOTE",
        "content_span": (
            "信贷在古代和中世纪时期就得到了普遍应用。信贷的历史远远早于工业、银行业，"
            "甚至早于铸币业；它可能比最原始的货币形式还要早。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_credit_neolithic",
        "page_number": 2,
        "section": "1.1",
        "evidence_type": "QUOTE",
        "content_span": (
            "含息贷款也许可以说是在新石器时期农民将种子贷给表亲并期望在收割季节"
            "加量归还的时候就开始了。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_date",
        "page_number": 3,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": (
            "在大约公元前1800年，古代巴比伦王朝的第一个国王汉谟拉比"
            "（Hammurabi）给他的臣民制订了第一部已知最早的正式法典。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_grain_rate",
        "page_number": 4,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": "法定利率上限确定为谷物贷款每年33.333%，以实物偿还",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_silver_rate",
        "page_number": 4,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": "银子贷款按重量计算每年20%",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_written",
        "page_number": 5,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": "所有贷款都必须附有书面合约，并由官员作证",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_forfeit",
        "page_number": 5,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": "如果作弊收取的利息高于法定上限，那么债务的本金就会被免除",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_hammurabi_collateral",
        "page_number": 5,
        "section": "1.2",
        "evidence_type": "QUOTE",
        "content_span": "土地和动产可以用作债务抵押，债主的仆人、妻妾、子女或奴隶也可以用来抵押",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_solon_date",
        "page_number": 6,
        "section": "1.3",
        "evidence_type": "QUOTE",
        "content_span": (
            "1200年以后，也就是在大约公元前600年的时候，古希腊的法律史始于"
            "索伦（Solon）的法典。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_solon_crisis",
        "page_number": 6,
        "section": "1.3",
        "evidence_type": "QUOTE",
        "content_span": (
            "当时，雅典出现了一次经济危机——其部分起因是过度的债务和普遍的"
            "个人劳役偿债——因而必须进行重大改革。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_solon_no_interest_limit",
        "page_number": 7,
        "section": "1.3",
        "evidence_type": "QUOTE",
        "content_span": (
            "与《汉谟拉比法典》形成鲜明对比的是，索伦的法典取消了对利率的所有限制。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_solon_debt_relief",
        "page_number": 7,
        "section": "1.3",
        "evidence_type": "QUOTE",
        "content_span": (
            "他们减少或者豁免了许多债务，允许不转移占有地抵押，但是禁止个人劳役偿债。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_twelve_tables_date",
        "page_number": 8,
        "section": "1.4",
        "evidence_type": "QUOTE",
        "content_span": (
            "早在大约公元前450年的著名的半传统型《十二铜表法》"
            "（Twelve Tables）中，在对待信贷问题上，更多的是模仿《汉谟拉比法典》，"
            "而不是索伦的法典。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_rome_rate_cap",
        "page_number": 9,
        "section": "1.4",
        "evidence_type": "QUOTE",
        "content_span": "贷款的利息被限制为不得超过每年8.333%",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_rome_penalty",
        "page_number": 9,
        "section": "1.4",
        "evidence_type": "QUOTE",
        "content_span": "高于法定上限的利息将被处以4倍损害赔偿",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_rome_servitude",
        "page_number": 9,
        "section": "1.4",
        "evidence_type": "QUOTE",
        "content_span": "个人劳役偿债得到允许，但是奴隶的人身健康受到保护",
        "extractor_version": EXTRACTOR_VERSION,
    },
    {
        "key": "ev_prehistory_conclusion",
        "page_number": 10,
        "section": "1.5",
        "evidence_type": "QUOTE",
        "content_span": (
            "历史最初时期巴比伦王朝、古希腊和古罗马的这三个案例足以支持这样一个结论："
            "即含息信贷在有文字历史出现之前就已经普及到了足以产生重大政治问题的程度。"
        ),
        "extractor_version": EXTRACTOR_VERSION,
    },
]

# ── KU candidates (derived only from the evidence spans above) ──────────────

KU_CANDIDATES: List[Dict] = [
    {
        "key": "kc_credit_predates_coinage",
        "evidence_key": "ev_credit_ancient",
        "content": "信贷的历史早于工业、银行业与铸币业",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "信贷在古代和中世纪时期就得到了普遍应用",
    },
    {
        "key": "kc_credit_neolithic_origin",
        "evidence_key": "ev_credit_neolithic",
        "content": "含息贷款可追溯至新石器时期的谷物借贷",
        "candidate_type": "FACT",
        "confidence": 0.90,
        "source_span": "新石器时期农民将种子贷给表亲",
    },
    {
        "key": "kc_hammurabi_code",
        "evidence_key": "ev_hammurabi_date",
        "content": "《汉谟拉比法典》（约前1800年）是最早的成文信贷法典之一",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "第一部已知最早的正式法典",
    },
    {
        "key": "kc_babylon_grain_rate_cap",
        "evidence_key": "ev_hammurabi_grain_rate",
        "content": "巴比伦法定利率上限：谷物贷款33.333%/年（实物偿还）",
        "candidate_type": "FACT",
        "confidence": 0.98,
        "source_span": "谷物贷款每年33.333%",
    },
    {
        "key": "kc_babylon_silver_rate_cap",
        "evidence_key": "ev_hammurabi_silver_rate",
        "content": "巴比伦法定利率上限：银子贷款20%/年（按重量计）",
        "candidate_type": "FACT",
        "confidence": 0.98,
        "source_span": "银子贷款按重量计算每年20%",
    },
    {
        "key": "kc_written_contract_required",
        "evidence_key": "ev_hammurabi_written",
        "content": "巴比伦要求所有贷款附书面合约并由官员作证",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "所有贷款都必须附有书面合约",
    },
    {
        "key": "kc_usury_principal_forfeit",
        "evidence_key": "ev_hammurabi_forfeit",
        "content": "收取高于法定上限的利息会导致债务本金被免除",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "债务的本金就会被免除",
    },
    {
        "key": "kc_babylon_collateral_scope",
        "evidence_key": "ev_hammurabi_collateral",
        "content": "巴比伦允许土地、动产及人身作为债务抵押",
        "candidate_type": "FACT",
        "confidence": 0.92,
        "source_span": "土地和动产可以用作债务抵押",
    },
    {
        "key": "kc_solon_code_date",
        "evidence_key": "ev_solon_date",
        "content": "索伦法典（约前600年）开启古希腊成文信贷法律史",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "古希腊的法律史始于索伦（Solon）的法典",
    },
    {
        "key": "kc_athens_debt_crisis",
        "evidence_key": "ev_solon_crisis",
        "content": "前6世纪雅典因过度债务与普遍个人劳役偿债爆发经济危机",
        "candidate_type": "FACT",
        "confidence": 0.90,
        "source_span": "雅典出现了一次经济危机",
    },
    {
        "key": "kc_solon_abolished_rate_cap",
        "evidence_key": "ev_solon_no_interest_limit",
        "content": "索伦法典取消利率上限，与巴比伦法典形成鲜明对比",
        "candidate_type": "FACT",
        "confidence": 0.96,
        "source_span": "索伦的法典取消了对利率的所有限制",
    },
    {
        "key": "kc_solon_debt_relief",
        "evidence_key": "ev_solon_debt_relief",
        "content": "索伦减免债务、允许不转移占有地抵押、禁止个人劳役偿债",
        "candidate_type": "FACT",
        "confidence": 0.94,
        "source_span": "减少或者豁免了许多债务",
    },
    {
        "key": "kc_twelve_tables_date",
        "evidence_key": "ev_twelve_tables_date",
        "content": "《十二铜表法》（约前450年）在信贷上仿效汉谟拉比法典而非索伦法典",
        "candidate_type": "FACT",
        "confidence": 0.95,
        "source_span": "更多的是模仿《汉谟拉比法典》",
    },
    {
        "key": "kc_rome_rate_cap",
        "evidence_key": "ev_rome_rate_cap",
        "content": "罗马法定利率上限：8.333%/年",
        "candidate_type": "FACT",
        "confidence": 0.98,
        "source_span": "贷款的利息被限制为不得超过每年8.333%",
    },
    {
        "key": "kc_rome_penalty_fourfold",
        "evidence_key": "ev_rome_penalty",
        "content": "罗马对超上限利息处以4倍损害赔偿",
        "candidate_type": "FACT",
        "confidence": 0.97,
        "source_span": "将被处以4倍损害赔偿",
    },
    {
        "key": "kc_rome_servitude_allowed",
        "evidence_key": "ev_rome_servitude",
        "content": "罗马允许个人劳役偿债但保护奴隶人身健康",
        "candidate_type": "FACT",
        "confidence": 0.94,
        "source_span": "但是奴隶的人身健康受到保护",
    },
    {
        "key": "kc_credit_precedes_writing",
        "evidence_key": "ev_prehistory_conclusion",
        "content": "含息信贷在有文字历史之前已普及到造成重大政治问题的程度",
        "candidate_type": "FACT",
        "confidence": 0.93,
        "source_span": "在有文字历史出现之前就已经普及",
    },
]