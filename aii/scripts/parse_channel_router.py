#!/usr/bin/env python3
r"""解析通道路由器 — MINERU-AII-INTEGRATION-SPEC-001 §2.2.

G0 的产出不是"谁取代谁", 而是填满这张路由表——本文件把 §2.2 表原样搬进代码:
唯一已经拍板的规则(原生 office 文档 → MinerU, 免转PDF)照做, 其余四类
`[PENDING-G0-DRYRUN]` 默认保守走现状 Unlimited-OCR, 不是"忘了", 是特意悬空
等 G0 三十份样本评估给出显著性判定后再回来改这张表。

不影响现有生产流量: 这个路由器目前没有任何代码调用它(Track B 还没接进
econ_batch_run.sh/math_flywheel_prog.sh 等真实消费管道), 纯粹是"通道决策"这
一层的接口先立好, 接线是另一个决定, 不在这次范围内。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

Channel = Literal["unlimited_ocr", "mineru_vlm"]

# spec §2.2 冻结规则: 原生 office 文档直接用 MinerU 原生解析, 不转 PDF。
_MINERU_NATIVE_EXTS = {".docx", ".pptx", ".xlsx"}

# spec §2.2 剩余四行, 原样抄进来防止以后有人忘了这些还没定:
#   纯文本 / 简单版式        → Unlimited-OCR (现状稳定, 已确定不是 PENDING)
#   密集表格                 → [PENDING-G0-DRYRUN]  当前默认 unlimited_ocr
#   含公式                   → [PENDING-G0-DRYRUN]  当前默认 unlimited_ocr
#   扫描件 / 复杂版式         → [PENDING-G0-DRYRUN]  当前默认 unlimited_ocr


def choose_channel(
    file_path: str, doc_features: dict | None = None, *, force: Channel | None = None
) -> Channel:
    """决定一份文档走哪条解析通道.

    Args:
        file_path: 文档路径(用扩展名判断是否原生 office 格式).
        doc_features: 预留给 G0 之后填表用的特征字典(如
            {"table_dense": bool, "formula_heavy": bool, "scanned_complex": bool}) ——
            目前这几类全部 PENDING, doc_features 传了也不影响结果, 占位不作数。
        force: G0/手测专用, 跳过路由表直接指定通道.

    Returns:
        "unlimited_ocr" 或 "mineru_vlm".
    """
    if force is not None:
        return force

    ext = Path(file_path).suffix.lower()
    if ext in _MINERU_NATIVE_EXTS:
        return "mineru_vlm"

    # 密集表格/含公式/扫描件复杂版式(doc_features 里对应字段)目前都是
    # [PENDING-G0-DRYRUN], 保守默认现状通道, 不因为 doc_features 传了什么就改判。
    return "unlimited_ocr"


if __name__ == "__main__":
    # 手工核对几个真实场景, 不是正式测试套件——确认铁律(office→mineru)和默认
    # (其余→unlimited_ocr)都对, 不影响现有生产路径。
    cases = [
        ("book.pdf", None, "unlimited_ocr"),
        ("report.docx", None, "mineru_vlm"),
        ("slides.pptx", None, "mineru_vlm"),
        ("data.xlsx", None, "mineru_vlm"),
        ("scanned.pdf", {"scanned_complex": True}, "unlimited_ocr"),  # 仍 PENDING, 默认不变
        ("book.pdf", None, "unlimited_ocr"),
    ]
    for path, features, expected in cases:
        got = choose_channel(path, features)
        status = "OK" if got == expected else "MISMATCH"
        print(f"[{status}] {path} (features={features}) -> {got} (expected {expected})")

    forced = choose_channel("anything.pdf", force="mineru_vlm")
    print(f"[{'OK' if forced == 'mineru_vlm' else 'MISMATCH'}] force override -> {forced}")
