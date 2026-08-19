"""★stratum 内化 LangExtract — grounded structured extraction + visualization。

3O 落点: oprim.grounded_extract(指令+few-shot → JSON + 源字符定位) + 可视化审查。

LLM 配置(OpenAI 兼容, 环境变量):
  LX_API_BASE  默认 https://integrate.api.nvidia.com/v1 (NIM, 容器可达)
  LX_API_KEY   默认读 OPENCODE_API_KEY 或 .pipeline_keys.json 的 econ
  LX_MODEL     默认 nvidia/llama-3.3-nemotron-super-49b-v1.5
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import langextract as lx  # noqa: F401  (pip/容器或仓库副本)

ROOT = Path(__file__).resolve().parents[2]


def _nim_key() -> str:
    try:
        d = json.loads((ROOT / "aii" / ".pipeline_keys.json").read_text())
        return d.get("econ") or ""
    except Exception:
        return ""


def _model():
    from langextract.factory import ModelConfig, create_model
    base = os.getenv("LX_API_BASE", "https://integrate.api.nvidia.com/v1")
    key = os.getenv("LX_API_KEY") or _nim_key()
    model_id = os.getenv("LX_MODEL", "gpt-5.5")
    return create_model(ModelConfig(model_id=model_id, provider="openai",
                                    provider_kwargs={"base_url": base, "api_key": key}))


def grounded_extract(text: str, prompt: str, examples: list[dict],
                     model=None, chunk_size: int | None = None) -> dict:
    """指令+few-shot → {extractions: [{class, text, locations}], html?}。

    examples: [{"text": ..., "extractions": [{"extraction_class","extraction_text"}, ...]}]
    """
    if not prompt.lower().strip().startswith("extract") and "json" not in prompt.lower():
        prompt = f"Extract structured info as JSON. {prompt}"
    ex_data = [
        lx.data.ExampleData(
            text=e["text"],
            extractions=[lx.data.Extraction(**x) for x in e["extractions"]],
        ) for e in examples
    ]
    m = model or _model()
    result = lx.extract(text_or_documents=text, prompt_description=prompt,
                        examples=ex_data, model=m)
    out = []
    for e in result.extractions:
        txt = e.extraction_text or ""
        locs = []
        # ★定位: 原文搜索(提取值来自原文精确文本; Langextract 的 Annotator 对齐未在 extract 顶层暴露)
        start = 0
        for _ in range(3):
            i = text.find(txt, start)
            if i < 0:
                break
            locs.append({"start": i, "end": i + len(txt)})
            start = i + len(txt)
        out.append({"class": e.extraction_class, "text": txt, "locations": locs})
    return {"extractions": out, "count": len(out)}


def extract_html(text: str, result: dict) -> str:
    """生成自包含 HTML: 提取值在原文上下文高亮(审查用)。"""
    spans = []
    for e in result["extractions"]:
        for loc in e["locations"]:
            spans.append((loc["start"], loc["end"], e["class"]))
    if not spans:
        return "<html><body><p>无提取定位</p></body></html>"
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<style>mark{border-radius:3px;padding:0 2px}mark b{font-size:10px;color:#fff;"
            "background:#333;border-radius:3px;padding:0 3px;margin-right:3px}</style></head><body>"]
    # 简单按 span 高亮(重叠 span 合并处理简化: 逐 span 用 slice 标记)
    colors = ["#ffe066", "#9ae6b4", "#90cdf4", "#fbb6ce", "#e9d8fd", "#fbd38d"]
    html.append(text[: spans[0][0]].replace("<", "&lt;"))
    prev_end = 0
    for i, (s, e2, cls) in enumerate(spans):
        if s < prev_end:
            continue
        html.append(text[prev_end:s].replace("<", "&lt;"))
        html.append(f"<mark style='background:{colors[i % len(colors)]}'><b>{cls}</b>"
                    f"{text[s:e2].replace('<', '&lt;')}</mark>")
        prev_end = e2
    html.append(text[prev_end:].replace("<", "&lt;"))
    html.append("</body></html>")
    return "".join(html)
