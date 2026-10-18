"""★宿主 extract 微服务(:8301) — LangExtract grounded extraction(直连 NVIDIA NIM)。
首选 NIM(nvidia/llama-3.3-nemotron-super-49b-v1.5)，回退 opencode gpt-5.5(127.0.0.1:10101)。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # docs_service
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

# ★首选 NVIDIA NIM (通过 .pipeline_keys.json 的 econ key)
# 回退 opencode gpt-5.5 (127.0.0.1:10101/v1) —— 需有效 token
# 优先级: 1) NIM (更稳定、无需本地 token) 2) opencode (需有效 token)
NIM_BASE = "https://integrate.api.nvidia.com/v1"
NIM_MODEL = "meta/llama-3.2-11b-vision-instruct"
OPENCODE_BASE = "http://127.0.0.1:10101/v1"
OPENCODE_MODEL = "gpt-5.5"

# 读取 NIM key (从 .pipeline_keys.json 的 econ)
def _nim_key() -> str:
    try:
        import json
        from pathlib import Path
        d = json.loads((Path(__file__).resolve().parents[2] / "aii" / ".pipeline_keys.json").read_text())
        return d.get("econ") or ""
    except Exception:
        return ""

# 优先用 NIM；无 key 才回退 opencode
nim_key = _nim_key()
if nim_key:
    os.environ.setdefault("LX_API_BASE", "https://integrate.api.nvidia.com/v1")
    os.environ.setdefault("LX_API_KEY", nim_key)
    os.environ.setdefault("LX_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
else:
    # 回退 opencode (需有效 token)
    os.environ.setdefault("LX_API_BASE", "http://127.0.0.1:10101/v1")
    os.environ.setdefault("LX_API_KEY", "")
    os.environ.setdefault("LX_MODEL", "gpt-5.5")
    if not os.environ.get("LX_API_KEY"):
        raise RuntimeError("LX_API_KEY not set — refusing to start (see aii-extract.service EnvironmentFile)")

from grounded_extract import extract_html, grounded_extract  # noqa: E402

app = FastAPI(title="grounded-extract", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True, "service": "grounded-extract"}


# 默认 KU 抽取示例(中英双语通用)
DEFAULT_KU_EXAMPLES = [
    {
        "text": "第一章 引言\n机器学习是一种让计算机从数据中学习的方法。\n第二章 监督学习\n监督学习使用标记数据训练模型。",
        "extractions": [
            {"extraction_class": "章节", "extraction_text": "第一章 引言"},
            {"extraction_class": "知识点", "extraction_text": "机器学习是一种让计算机从数据中学习的方法"},
            {"extraction_class": "章节", "extraction_text": "第二章 监督学习"},
            {"extraction_class": "知识点", "extraction_text": "监督学习使用标记数据训练模型"}
        ]
    },
    {
        "text": "Chapter 1 Introduction\nMachine learning enables computers to learn from data.\nChapter 2 Supervised Learning\nSupervised learning uses labeled data to train models.",
        "extractions": [
            {"extraction_class": "Chapter", "extraction_text": "Chapter 1 Introduction"},
            {"extraction_class": "Knowledge Point", "extraction_text": "Machine learning enables computers to learn from data"},
            {"extraction_class": "Chapter", "extraction_text": "Chapter 2 Supervised Learning"},
            {"extraction_class": "Knowledge Point", "extraction_text": "Supervised learning uses labeled data to train models"}
        ]
    }
]


@app.post("/extract")
async def extract(file: UploadFile = File(...), prompt: str = Form(...),
                  examples_json: str = Form("[]"), html: str = Form("0")):
    suffix = Path(file.filename).suffix or ".md"
    fd = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    fd.write(file.file.read())
    fd.close()
    try:
        text = Path(fd.name).read_text(encoding="utf-8", errors="replace")
        examples = json.loads(examples_json) if examples_json else []
        if not examples:
            examples = DEFAULT_KU_EXAMPLES
        r = grounded_extract(text, prompt, examples)
        if html == "1":
            r["html"] = extract_html(text, r)
        return r
    finally:
        Path(fd.name).unlink(missing_ok=True)




@app.post("/ku-visualize")
async def ku_visualize_endpoint(substrate: str = Form(...), limit: int = Form(60)):
    """KU 证据可视化审查: substrate_id → 高亮 HTML(字符串)。"""
    import subprocess
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[2] / "aii/scripts/ku_visualize.py"),
         "--substrate", substrate, "--limit", str(limit), "--out", "/tmp/ku_vis_live.html"],
        capture_output=True, text=True, timeout=300)
    html = ""
    try:
        html = Path("/tmp/ku_vis_live.html").read_text(encoding="utf-8")
    except Exception:
        pass
    return {"ok": r.returncode == 0, "html": html, "log": (r.stdout + r.stderr)[-300:]}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.environ.get("AII_EXTRACT_HOST", "127.0.0.1"),
        port=int(os.environ.get("AII_EXTRACT_PORT", "8301")),
    )

