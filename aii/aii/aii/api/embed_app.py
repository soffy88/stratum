"""AII 共享嵌入微服务 (BGE-M3).

设计目标(见架构讨论):
- 瘦进程常开: 空闲时不加载模型, 内存≈50MB.
- 按需加载: 首个请求时加载; 加载时**探测显存**自动选 GPU(空闲)或 CPU(被占).
- 空闲卸载: 超过 AII_EMBED_IDLE_SEC 无请求 → 卸载模型, 释放 内存/显存 归零.
  (显存不能靠 swap 页出, 只能显式卸载 → 一个机制通吃 CPU+GPU 省内存诉求.)
- 复刻飞轮当前实际路径 = sentence-transformers 的
  encode(normalize_embeddings=True)[:1024], 保证向量与库中存量一致.

所有消费方(三飞轮 + aii-backend)改调本服务, 不再各自进程内加载一份 BGE-M3.
"""

from __future__ import annotations

import asyncio
import gc
import os
import threading
import time

from fastapi import Body, FastAPI

MODEL_NAME = "BAAI/bge-m3"
DIM = 1024
IDLE_SEC = int(os.getenv("AII_EMBED_IDLE_SEC", "300"))  # 空闲多久卸载
VRAM_MIN_GB = float(os.getenv("AII_EMBED_VRAM_MIN_GB", "3.5"))  # 空闲显存 ≥ 此值才上 GPU


class _Embedder:
    def __init__(self) -> None:
        self._model = None
        self._device: str | None = None
        self._last = time.time()
        self._lock = threading.Lock()  # 序列化 load/unload/encode, 一次只跑一个

    def _pick_device(self) -> str:
        # 用 nvidia-smi 子进程探空闲显存, 而非 torch.cuda.mem_get_info() —— 后者会
        # 初始化一个 ~200M CUDA 上下文赖在显存里, 即便随后用 CPU. 子进程探测 0 显存占用.
        try:
            import subprocess

            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            free_mb = int(out.stdout.strip().splitlines()[0])
            if free_mb / 1024 >= VRAM_MIN_GB:
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _load(self) -> None:
        from sentence_transformers import SentenceTransformer

        dev = self._pick_device()
        self._model = SentenceTransformer(MODEL_NAME, device=dev)
        self._device = dev

    def embed(self, texts: list[str]) -> tuple[list[list[float]], str]:
        with self._lock:
            if self._model is None:
                self._load()
            self._last = time.time()
            vecs = self._model.encode(list(texts), normalize_embeddings=True)
            return [v[:DIM].tolist() for v in vecs], self._device or "cpu"

    def maybe_unload(self) -> bool:
        with self._lock:
            if self._model is not None and time.time() - self._last > IDLE_SEC:
                dev = self._device
                self._model = None
                self._device = None
                gc.collect()
                if dev == "cuda":
                    import torch

                    torch.cuda.empty_cache()
                return True
        return False

    def status(self) -> dict:
        return {
            "loaded": self._model is not None,
            "device": self._device,
            "idle_sec": round(time.time() - self._last, 1) if self._model else None,
        }


_EMB = _Embedder()
app = FastAPI(title="AII Embed Service", version="1.0")


@app.on_event("startup")
async def _start_idle_reaper() -> None:
    async def reaper() -> None:
        while True:
            await asyncio.sleep(min(IDLE_SEC, 60))
            try:
                if await asyncio.to_thread(_EMB.maybe_unload):
                    pass
            except Exception:
                pass

    asyncio.create_task(reaper())


@app.get("/health")
async def health() -> dict:
    return {"ok": True, **_EMB.status()}


@app.post("/embed")
async def embed(texts: list[str] = Body(..., embed=True)) -> dict:
    """批量嵌入: {"texts": ["...", ...]} → {"embeddings": [[...], ...], "dim", "device"}."""
    if not texts:
        return {"embeddings": [], "dim": DIM, "device": None}
    vecs, dev = await asyncio.to_thread(_EMB.embed, texts)
    return {"embeddings": vecs, "dim": DIM, "device": dev}
