#!/usr/bin/env python3
r"""G0 评估指标脚手架 — MINERU-AII-INTEGRATION-SPEC-001 §5.2.

2026-07-09 更新: MinerU VLM 侧的 V1 现在是真实现(compute_v1_from_middle_json),
不再是 NotImplementedError 占位——Track B 代码端已经搭好(见
aii/scripts/parse_channel_router.py + math_ocr_convert.py 的
ensure_mineru_container 系列)。但本机 GPU 硬件故障(Xid 79)未恢复, 这个函数
没有真实跑通过 MinerU VLM 的输出——单独用 CPU-only 的 `mineru pipeline` 后端
验证过 middle_json 的真实 schema(不是查文档假设的), 函数实现照这个真实
schema 写, 但"双通道完整对比"仍然要等 GPU 恢复、mineru-vlm 容器真的跑起来
才能出数字。

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
        channel: 只接受 "unlimited_ocr"——这个函数是"从拍平MD反推"这条近似
            路径专用的, MinerU VLM 有真正的结构化产物(middle_json), 不该也走
            这条近似路径, 见 compute_v1_from_middle_json()。

    Raises:
        ValueError: channel 不是 "unlimited_ocr"(MinerU VLM 请用
            compute_v1_from_middle_json, 不是把它硬凑进这个近似函数)。
        FileNotFoundError: doc_path 不存在。
    """
    if channel != "unlimited_ocr":
        raise ValueError(
            f"compute_v1_from_flattened_md 只服务 unlimited_ocr, 收到 {channel!r}。"
            "MinerU VLM 有真实结构化产物, 用 compute_v1_from_middle_json()。"
        )

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


# middle_json 里标志结构化元素的 type 值——真实实测出来的(见模块 docstring),
# 不是查文档假设的。公式这一项踩过一次坑: 第一版写成"block.type"级别, 拿一份
# 真含公式(MFR Predict 实测跑过8个公式区域)的页面验证后发现根本不对——公式
# 类型信息在 span 级别(block["lines"][i]["spans"][j]["type"]), 不是 block 级别,
# block 级别对含公式的段落仍然只标 "text"。已按实测修正。
# 表格类型名仍未在实测样本里遇到过(测试样本没有表格页), 保留 block 级别猜测,
# 如实标注这半条还没验证过, 不混同于已验证的公式那部分。
_TABLE_BLOCK_TYPES = {"table"}  # ⚠ 未实测验证, 猜测值(spec 文档类型枚举)
_EQUATION_SPAN_TYPES = {"interline_equation", "inline_equation"}  # ✅ 已实测验证


def compute_v1_from_middle_json(middle_json: dict, doc_path: Path) -> V1Result:
    """从 MinerU VLM 的真实结构化产物(middle_json)直接量测, 不是近似值。

    与 compute_v1_from_flattened_md 的关键差别: 这里数的是"解析器自己标注为
    表格/公式的结构化元素", 不是从文本正则反推的代理信号(is_approximation=False)。

    实测过的真实 schema(2026-07-09, mineru 3.4.3 pipeline 后端 CPU 实跑两页
    真实 PDF 核实, 不是照文档抄): middle_json 顶层 {pdf_info, _backend,
    _version_name}; 每页 pdf_info[i] 下有 para_blocks/discarded_blocks, 每个
    block 带 "type"(如 "title"/"text") + "lines"→"spans" 嵌套结构, **公式的
    type 在 span 级别**("inline_equation" 等, block 级别对含公式段落仍是
    "text"——第一版实现搞错了这个层级, 用真实含公式页面测出来才发现, 已修正)。
    表格 block 级别的 "table" 类型名还没在实测样本里遇到过真表格页, 是根据
    spec 文档类型枚举的猜测值, 见下面 _TABLE_BLOCK_TYPES 的 ⚠ 标注。

    Args:
        middle_json: omodul.mineru_vlm_parse 或 parse_with_mineru_vlm() 返回的
            middle_json 字典。
        doc_path: 仅用于结果里标注来源, 不读这个路径(数据已经在 middle_json 里)。

    Returns:
        V1Result, is_approximation=False。reading_order_correct 仍然是 None
        (需要人工标注真值, 本轮不做——这点和 Unlimited-OCR 侧一样, 不因为
        MinerU 有结构化产物就自动有阅读顺序真值)。
    """
    table_count = 0
    equation_count = 0
    for page in middle_json.get("pdf_info", []):
        blocks = page.get("para_blocks", []) + page.get("discarded_blocks", [])
        for block in blocks:
            if block.get("type", "") in _TABLE_BLOCK_TYPES:
                table_count += 1
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("type", "") in _EQUATION_SPAN_TYPES:
                        equation_count += 1

    return V1Result(
        channel="mineru_vlm",
        doc_path=str(doc_path),
        table_row_count=table_count or None,
        latex_span_count=equation_count,
        latex_balanced_rate=None,  # 结构化块本身已经是解析器判定过的公式, 配平率这个
        # 代理信号是给"从纯文本反推"那条路准备的, 这里没有反推, 不适用
        reading_order_correct=None,  # 需要人工标注真值, 本轮不做(两个通道待遇一致)
        is_approximation=False,
        notes="从 middle_json 结构化元素直接数, 非文本正则反推; 公式计数(span级别)"
        "已用真实含公式页面验证过(8个公式区域, 与 MFR Predict 日志对上); 表格计数"
        "(block级别 'table' 类型)还没在实测样本里遇到过真表格页, 是猜测值",
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
