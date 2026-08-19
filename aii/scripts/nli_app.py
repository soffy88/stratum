#!/usr/bin/env python3
"""NLI 蕴含校验服务 (规格 3.5, C2) — DeBERTa-v3-MNLI, GPU 常驻。

  POST /verify        {"evidence": "...", "claim": "..."}      → 单条
  POST /verify_batch  {"pairs": [{"evidence": "...", "claim": "..."}, ...]} → 真批处理

premise = evidence(原文), hypothesis = claim(抽出的命题) —— 方向不能反。
id2label 从 config 读取(不写死 0/1/2)。fp16 推理。
级联(子串→数字→embedding)在调用方完成, 本服务只做最后一道。

启动: .venv/bin/python scripts/nli_app.py  (127.0.0.1:8103)
"""
from __future__ import annotations

import os

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL = os.getenv("NLI_MODEL", "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
TAU_ENT = float(os.getenv("NLI_TAU_ENT", "0.50"))
TAU_CON = float(os.getenv("NLI_TAU_CON", "0.35"))
MAX_LEN = int(os.getenv("NLI_MAX_LEN", "256"))

app = FastAPI(title="NLI verifier", version="0.1")

_tokenizer = None
_model = None
_device = None
_id2label: dict[int, str] = {}


def _load() -> None:
    global _tokenizer, _model, _device, _id2label
    _tokenizer = AutoTokenizer.from_pretrained(MODEL)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    # ★GPU 被 ollama/embed 占用时自动降级 CPU(DeBERTa-base 批量可接受)
    _device = "cpu"
    if torch.cuda.is_available():
        try:
            _model = _model.to("cuda")
            torch.cuda.empty_cache()
            _model.half()
            _device = "cuda"
        except torch.cuda.OutOfMemoryError:
            _model = _model.to("cpu")
            print("CUDA OOM → CPU fallback", flush=True)
    _model.eval()
    _id2label = {int(k): str(v).lower() for k, v in _model.config.id2label.items()}
    print(f"NLI loaded: {MODEL} @ {_device}, labels={_id2label}", flush=True)


class Pair(BaseModel):
    evidence: str
    claim: str


class Batch(BaseModel):
    pairs: list[Pair]


def _verify_batch_tensors(evidences: list[str], claims: list[str]) -> list[dict]:
    tok = _tokenizer(
        evidences, claims, padding=True, truncation=True,
        max_length=MAX_LEN, return_tensors="pt",
    )
    tok = {k: v.to(_device) for k, v in tok.items()}
    with torch.inference_mode():
        logits = _model(**tok).logits
        probs = torch.softmax(logits.float(), dim=-1).cpu().tolist()
    out = []
    for p in probs:
        dist = {_id2label.get(i, str(i)): round(v, 4) for i, v in enumerate(p)}
        pe = dist.get("entailment", 0.0)
        pc = dist.get("contradiction", 0.0)
        label = max(dist, key=dist.get)
        out.append({
            "label": label,
            "probs": dist,
            "pass_support": pe >= TAU_ENT and pc <= TAU_CON,
            "score_entailment": pe,
        })
    return out


@app.on_event("startup")
def _startup() -> None:
    _load()


@app.get("/health")
def health() -> dict:
    return {"ok": _model is not None, "device": _device,
            "model": MODEL, "tau_ent": TAU_ENT, "tau_con": TAU_CON}


@app.post("/verify")
def verify(p: Pair) -> dict:
    if not p.evidence.strip() or not p.claim.strip():
        return {"label": "neutral", "probs": {"entailment": 0.0, "neutral": 1.0,
                "contradiction": 0.0}, "pass_support": False, "score_entailment": 0.0}
    return _verify_batch_tensors([p.evidence], [p.claim])[0]


@app.post("/verify_batch")
def verify_batch(b: Batch) -> list[dict]:
    if not b.pairs:
        return []
    evs = [p.evidence for p in b.pairs]
    cls = [p.claim for p in b.pairs]
    return _verify_batch_tensors(evs, cls)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("NLI_PORT", "8103")))
