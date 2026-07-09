#!/usr/bin/env python3
r"""G0 评估指标脚手架 — MINERU-AII-INTEGRATION-SPEC-001 §5.2.

本轮交付的是框架, 不是跑完的评估结果。真正的双通道对比(Unlimited-OCR vs
MinerU VLM)需要 MinerU VLM 装好(Track B, 按 §9 落地顺序还在 G0 过闸之前,
本轮不装), 跑不动的部分在函数体里用 raise NotImplementedError 标清楚, 不假装
能跑出数字。

★ 意外发现, 比"MinerU 没装"更根本的一个阻塞: Unlimited-OCR 现在的输出就是拍
平后的 MD 纯文本(见 scripts/math_ocr_convert.py 的 ocr_pdf_to_text 签名), 没
有自己的结构化中间态——这正是 spec §1 描述的"解析一次, 双路分叉"要解决的问题
本身, 也是 [MIGRATION-UOCR-MIDJSON] 那条待办的动机。也就是说 V1(表格/公式/
阅读顺序结构保真度)在 Unlimited-OCR 这一侧, 今天只能从拍平的 MD 文本里用启发
式反推, 不是从真正的结构化元素里量——这是近似值, 不是精确对比, 已在下面每个
函数的 docstring 里标注, 不要在报告里把它当成精确数字引用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TABLE_ROW_RE = re.compile(r"^\s*\|.*\|.*\|\s*$", re.MULTILINE)
LATEX_INLINE_RE = re.compile(r"\$([^$\n]{1,500})\$")
LATEX_BLOCK_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)


# ---------------------------------------------------------------------------
# V1 — 结构保真 (§5.2 V1)
# ---------------------------------------------------------------------------


@dataclass
class V1Result:
    channel: str  # "unlimited_ocr" | "mineru_vlm"
    doc_path: str
    table_row_count: int | None
    latex_span_count: int
    latex_balanced_rate: float | None  # 括号/环境配平率, 公式是否被OCR嚼碎的廉价代理指标
    reading_order_correct: float | None  # 需要人工标注真值, 本轮不做, 恒 None
    is_approximation: bool  # True = 从拍平MD文本反推, 不是从结构化元素量的
    notes: str


def compute_v1_from_flattened_md(doc_path: Path, *, channel: str) -> V1Result:
    """从拍平后的 MD 文本反推结构保真信号(近似值, 见模块 docstring)。

    表格准确率(真正的"这个表格单元格对不对")需要人工标注的 ground truth,
    这里给不了 —— 只给"表格行密度"这个更弱但立即可算的代理信号, 供后续人工
    抽查时对照。LaTeX 配平率是真实可算的信号(括号/环境是否闭合), 用来粗筛
    "这份文档的公式有没有被解析嚼碎", 不是"公式内容语义是否正确"。

    Args:
        doc_path: 样本文档路径(来自 g0_eval/sample_set.json)。
        channel: "unlimited_ocr" 或 "mineru_vlm" —— 本轮只有 unlimited_ocr
            有真实数据可算(读现成的 MD), mineru_vlm 侧要等 Track B 装完才能
            跑出对应产物, 调这个函数会直接抛 NotImplementedError。

    Raises:
        NotImplementedError: channel == "mineru_vlm"(Track B 未装)。
        FileNotFoundError: doc_path 不存在。
    """
    if channel == "mineru_vlm":
        raise NotImplementedError(
            "MinerU VLM 未装(Track B 还在 G0 过闸之前, 按 §9 落地顺序本轮不装)。"
            "装好后这里应该读 middle_json 里的结构化表格/公式元素, 不是再反推 MD。"
        )
    if channel != "unlimited_ocr":
        raise ValueError(f"unknown channel: {channel!r}")

    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    table_rows = len(TABLE_ROW_RE.findall(text))

    spans = LATEX_INLINE_RE.findall(text) + LATEX_BLOCK_RE.findall(text)
    if spans:
        balanced = sum(1 for s in spans if s.count("{") == s.count("}"))
        balanced_rate = balanced / len(spans)
    else:
        balanced_rate = None

    return V1Result(
        channel=channel,
        doc_path=str(doc_path),
        table_row_count=table_rows if table_rows > 0 else None,
        latex_span_count=len(spans),
        latex_balanced_rate=balanced_rate,
        reading_order_correct=None,  # 需要人工标注真值, 本轮不做
        is_approximation=True,
        notes="从拍平 MD 反推, 非结构化元素直接量测; 表格数=行密度非单元格准确率",
    )


# ---------------------------------------------------------------------------
# V2 — KU 终判 (§5.2 V2, 权重最高)
# ---------------------------------------------------------------------------


@dataclass
class V2ReviewRow:
    """对应 §5.3 的人工评审表一行: 文档ID / 通道 / KU / 标注 / 理由。"""

    doc_id: str
    channel: str
    ku_index: int
    ku_text: str
    label: str | None = None  # "完整" | "残缺" | "歧义" —— 初筛 Claude 实例填
    reason: str | None = None  # 初筛理由 —— 初筛 Claude 实例填


def sample_ku_candidates_for_review(
    ku_candidates: list[dict[str, Any]], *, doc_id: str, channel: str, limit: int = 15
) -> list[V2ReviewRow]:
    """从一份文档单通道的 KU 候选里抽前 N 条, 铺成待人工评审的行(§5.3)。

    不做初筛判断——这个函数只负责"抽样+铺表", 标注/理由留空, 由另一个
    Claude 实例的初筛阶段(本轮不跑, 见模块 docstring)去填。

    Args:
        ku_candidates: 该文档在该通道下抽出的 KU 候选列表, 每项至少含
            与 natural_text 等价的文本字段("text" 或 "natural_text")。
        doc_id: 样本文档标识(sample_set.json 里的 path 或 substrate_id)。
        channel: "unlimited_ocr" | "mineru_vlm"。
        limit: 每份文档每通道抽检上限(§5.3 冻结值: 15)。

    Returns:
        长度 <= limit 的 V2ReviewRow 列表, label/reason 均为 None(待填)。
    """
    rows = []
    for i, cand in enumerate(ku_candidates[:limit]):
        text = cand.get("text") or cand.get("natural_text") or ""
        rows.append(V2ReviewRow(doc_id=doc_id, channel=channel, ku_index=i, ku_text=text))
    return rows


# ---------------------------------------------------------------------------
# V3 — 成本 (§5.2 V3)
# ---------------------------------------------------------------------------


@dataclass
class V3Result:
    channel: str
    doc_path: str
    latency_seconds: float | None
    vram_peak_mb: float | None
    notes: str


def compute_v3_placeholder(doc_path: Path, *, channel: str) -> V3Result:
    """成本指标框架 —— 本轮不跑, 两个通道都需要真实计时/显存采样才有意义。

    Unlimited-OCR 侧理论上可以现在就测(它是活的), 但单独测它没有对比对象
    (MinerU 侧要 Track B 装完才有), 意义不大, 留到 G0 dry-run 真正双通道对
    比时一起测更省事——所以这里保持占位, 不做半吊子的单通道计时。
    """
    return V3Result(
        channel=channel,
        doc_path=str(doc_path),
        latency_seconds=None,
        vram_peak_mb=None,
        notes="占位——留到双通道能同时跑时一起测, 单通道测了也没有对比意义",
    )


if __name__ == "__main__":
    import json

    sample_path = Path(__file__).resolve().parent.parent / "g0_eval" / "sample_set.json"
    if not sample_path.exists():
        raise SystemExit(f"先跑 g0_sample_select.py 生成 {sample_path}")

    samples = json.loads(sample_path.read_text(encoding="utf-8"))
    print("V1(结构保真, Unlimited-OCR 侧近似值) 试算前3份:")
    count = 0
    for _category, items in samples["categories"].items():
        for item in items:
            p = Path(item["path"])
            if not p.exists() or count >= 3:
                continue
            v1 = compute_v1_from_flattened_md(p, channel="unlimited_ocr")
            print(
                f"  {v1.doc_path}: tables~{v1.table_row_count} latex={v1.latex_span_count} "
                f"balanced_rate={v1.latex_balanced_rate}"
            )
            count += 1
