"""★宿主 extract 微服务(:8301) — LangExtract grounded extraction(直连 opencode)。
容器内 NIM 代理不稳; 宿主 127.0.0.1:10101(opencode gpt-5.5) 已验证通。
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # docs_service
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse

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
    uvicorn.run(app, host="0.0.0.0", port=8301)

