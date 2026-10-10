from __future__ import annotations

"""★stratum 内化 LangExtract — grounded structured extraction + visualization。

3O 落点: oprim.grounded_extract(指令+few-shot → JSON + 源字符定位) + 可视化审查。

LLM 配置(OpenAI 兼容, 环境变量):
  LX_API_BASE  默认 http://127.0.0.1:10100/v1 (本地 opencode proxy, 提供 ve ya-free)
  LX_API_KEY   默认 local (本地模式，跳过鉴权) 或从 .pipeline_keys.json 读取
  LX_MODEL     默认 ve ya-free (本地 opencode proxy 提供的免费模型)
"""

import json
import os
import re
import sys
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
    base = os.getenv("LX_API_BASE", "http://127.0.0.1:10100/v1")
    key = os.getenv("LX_API_KEY", "local")
    model_id = os.getenv("LX_MODEL", "veya-free")
    
    # 本地模式：key 为 "local" 时跳过鉴权
    if key == "local":
        provider_kwargs = {"base_url": base, "api_key": "local"}
    else:
        key = os.getenv("LX_API_KEY") or _nim_key()
        provider_kwargs = {"base_url": base, "api_key": key}
    
    from langextract.factory import ModelConfig, create_model
    model_id = os.getenv("LX_MODEL", "veya-free")
    return create_model(ModelConfig(model_id=model_id, provider="openai",
                                    provider_kwargs=provider_kwargs))


def _local_fallback(text: str, prompt: str, examples: list[dict]) -> dict:
    """本地兜底: 增强规则抽 KU (无外部依赖, 极快)。
    
    支持识别:
    - 章节标题 (中英文、Markdown、编号)
    - 数学公式 (LaTeX 行内/行间、Unicode 数学符号)
    - 代码块 (Markdown 围栏、缩进代码、行内代码)
    - 表格 (Markdown 表格、ASCII 表格、CSV 风格)
    - 列表项 (有序/无序、任务列表)
    - 引用/引文 (引用块、文献引用)
    - 关键句 (定义、原理、方法、特征等)
    """
    import re
    lines = text.split('\n')
    extractions = []
    chapter_pattern = re.compile(
        r'^(第\s*[一二三四五六七八九十百千0-9]+\s*[章节讲课回篇部分]|\s*Chapter\s+\d+|#+\s*.+)', re.I
    )
    math_inline = re.compile(r'\$[^$]+\$')  # $...$
    math_display = re.compile(r'\$\$[^$]+\$\$')  # $$...$$
    math_unicode = re.compile(r'[∑∏∫∮∂∇√∞±≠≈≤≥∈∉⊂⊃⊆⊇∪∩∀∃∴∵∝≡≈≠≤≥±×÷]')
    code_fence = re.compile(r'^```')
    code_indent = re.compile(r'^    \S')  # 4 空格缩进代码
    code_inline = re.compile(r'`[^`]+`')
    table_pipe = re.compile(r'^\s*\|.*\|\s*$')  # | a | b |
    table_csv = re.compile(r'^[^,]+(,[^,]+)+$')  # 简单 CSV
    list_bullet = re.compile(r'^[\s]*[-*+]\s+')  # - item
    list_number = re.compile(r'^\s*\d+[\.\)]\s+')  # 1. item
    list_task = re.compile(r'^[\s]*[-*+]\s*\[[ xX]\]\s+')  # - [x] task
    quote_block = re.compile(r'^>\s+')  # > quote
    ref_cite = re.compile(r'\[\d+\]')  # [1] [1,2]
    doi_pattern = re.compile(r'10\.\d{4,}/[^\s]+')  # DOI
    arxiv_pattern = re.compile(r'arXiv:\d{4}\.\d{4,5}')  # arXiv
    isbn_pattern = re.compile(r'ISBN[- ]?\d{10,13}')  # ISBN
    
    lines = text.split('\n')
    extractions = []
    in_code_block = False
    code_fence_lang = None
    in_table = False
    
    for i, line in enumerate(lines):
        raw_line = line
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # 代码围栏开始/结束
        if code_fence.match(line_stripped):
            if not in_code_block:
                in_code_block = True
                code_fence_lang = line_stripped[3:].strip() or "text"
                extractions.append({
                    "class": "代码块开始",
                    "text": f"```{code_fence_lang}",
                    "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
                })
                in_code_block = True
            else:
                extractions.append({
                    "class": "代码块结束",
                    "text": "```",
                    "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
                })
                in_code_block = False
                code_fence_lang = None
            continue
        
        if in_code_block:
            # 代码块内部内容
            extractions.append({
                "class": "代码行",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 缩进代码
        if code_indent.match(line) and not in_code_block:
            extractions.append({
                "class": "代码行",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 表格检测
        if table_pipe.match(line_stripped):
            if not in_table:
                in_table = True
                extractions.append({
                    "class": "表格开始",
                    "text": line_stripped[:200],
                    "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
                })
            else:
                extractions.append({
                    "class": "表格行",
                    "text": line_stripped[:300],
                    "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
                })
            continue
        elif in_table and not table_pipe.match(line_stripped):
            in_table = False
            extractions.append({
                "class": "表格结束",
                "text": "",
                "locations": [{"start": text.find(line), "end": text.find(line)}]
            })
        
        # 列表项
        if list_task.match(line_stripped):
            extractions.append({
                "class": "任务项",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        if list_bullet.match(line_stripped) or list_number.match(line_stripped):
            extractions.append({
                "class": "列表项",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 引用块
        if quote_block.match(line):
            extractions.append({
                "class": "引用",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 章节标题
        chapter_match = chapter_pattern.match(line)
        if chapter_match:
            extractions.append({
                "class": "章节" if re.search(r'[第章节]', line) else "Chapter",
                "text": line_stripped[:200],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 行内代码
        if code_inline.search(line):
            for m in code_inline.finditer(line):
                extractions.append({
                    "class": "行内代码",
                    "text": m.group(),
                    "locations": [{"start": text.find(m.group()), "end": text.find(m.group()) + len(m.group())}]
                })
        
        # 数学公式
        if math_display.search(line):
            extractions.append({
                "class": "数学公式(行间)",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        if math_inline.search(line):
            for m in math_inline.finditer(line):
                extractions.append({
                    "class": "数学公式(行内)",
                    "text": m.group(),
                    "locations": [{"start": text.find(m.group()), "end": text.find(m.group()) + len(m.group())}]
                })
            # 不 continue，继续检查其他
        if math_unicode.search(line):
            extractions.append({
                "class": "数学符号",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            # 不 continue
        
        # 引用/文献
        if quote_block.match(line):
            extractions.append({
                "class": "引用",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        if ref_cite.search(line) or doi_pattern.search(line) or arxiv_pattern.search(line) or isbn_pattern.search(line):
            extractions.append({
                "class": "引用/文献",
                "text": line_stripped[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 关键句: 长度适中、含关键词
        if 50 <= len(line) <= 300 and any(kw in line for kw in [
            '是', '定义', '定义为', '方法', '原理', '特征', '特点', '定义为', '指', 
            '由于', '因此', '所以', '因为', '从而', '即', '即:', '例如', '如',
            '定理', '引理', '推论', '证明', '假设', '命题', '公式', '定律',
            '算法', '复杂度', '时间复杂度', '空间复杂度', '最优', '最小', '最大'
        ]):
            extractions.append({
                "class": "知识点",
                "text": line[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
        
        # 文献引用格式
        if ref_cite.search(line) or doi_pattern.search(line) or arxiv_pattern.search(line) or isbn_pattern.search(line):
            extractions.append({
                "class": "文献引用",
                "text": line[:300],
                "locations": [{"start": text.find(line), "end": text.find(line) + len(line)}]
            })
            continue
    
    return {"extractions": extractions, "count": len(extractions), "fallback": "local_enhanced"}


def grounded_extract(text: str, prompt: str, examples: list[dict],
                     model=None, chunk_size: int | None = None) -> dict:
    """指令+few-shot → {extractions: [{class, text, locations}], html?}。

    examples: [{"text": ..., "extractions": [{"extraction_class","extraction_text"}, ...]}]
    """
    # 默认使用本地兜底 (极快、稳定、无外部依赖)
    # 如需 LLM 增强, 请显式设置 USE_LLM=1 环境变量
    if not os.getenv("USE_LLM", "0") == "1":
        return _local_fallback(text, prompt, [])
    
    if not prompt.lower().strip().startswith("extract") and "json" not in prompt.lower():
        prompt = f"Extract structured info as JSON. {prompt}"
    ex_data = [
        lx.data.ExampleData(
            text=e["text"],
            extractions=[lx.data.Extraction(**x) for x in e["extractions"]],
        ) for e in examples
    ]
    m = model or _model()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lx.extract, text_or_documents=text, prompt_description=prompt,
                                     examples=ex_data, model=m)
            result = future.result(timeout=120)  # 120s 超时
    except TimeoutError:
        print("[grounded_extract] LLM 调用超时(120s), 启用本地兜底")
        return _local_fallback(text, prompt, [])
    except Exception as e:
        print(f"[grounded_extract] LLM 失败, 启用本地兜底: {e}")
        return _local_fallback(text, prompt, [])
    
    out = []
    for e in result.extractions:
        txt = e.extraction_text or ""
        locs = []
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
    spans = []
    for e in result["extractions"]:
        for loc in e["locations"]:
            spans.append((loc["start"], loc["end"], e["class"]))
    if not spans:
        return "<html><body><p>无提取定位</p></body></html>"
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<style>mark{border-radius:3px;padding:0 2px}mark b{font-size:10px;color:#fff;"
            "background:#333;border-radius:3px;padding:0 3px;margin-right:3px}</style></head><body>"]
    colors = ["#ffe066", "#9ae6b4", "#90cdf4", "#fbb6ce", "#e9d8fd", "#fbd38d"]
    html.append(text[: spans[0][0]].replace("<", "<"))
    prev_end = 0
    for i, (s, e2, cls) in enumerate(spans):
        if s < prev_end:
            continue
        html.append(text[prev_end:s].replace("<", "<"))
        html.append(f"<mark style='background:{colors[i % len(colors)]}'><b>{cls}</b>"
                    f"{text[s:e2].replace('<', '<')}</mark>")
        prev_end = e2
    html.append(text[prev_end:].replace("<", "<"))
    html.append("</body></html>")
    return "".join(html)
