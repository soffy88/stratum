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

    def _load(self, force_device: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        dev = force_device or self._pick_device()
        self._model = SentenceTransformer(MODEL_NAME, device=dev)
        self._device = dev

    def embed(self, texts: list[str]) -> tuple[list[list[float]], str]:
        with self._lock:
            if self._model is None:
                self._load()
            self._last = time.time()
            # ★小卡(如笔记本4G的1050Ti)扛不住大batch一次性编码, 见2026-07-08实测: 一次OOM
            # 崩了整个进程, 卡了下游飞轮十几小时才被发现. batch_size给小默认值+OOM时降批重试,
            # 而不是让整个请求(乃至进程)崩掉.
            bs = int(os.getenv("AII_EMBED_BATCH_SIZE", "16"))
            vecs = None
            for attempt in range(3):
                try:
                    vecs = self._model.encode(list(texts), normalize_embeddings=True, batch_size=bs)
                    break
                except RuntimeError as e:
                    if self._device != "cuda" or attempt == 2:
                        break  # 非GPU错误, 或重试用尽 → 走下面的CPU兜底/继续抛
                    print(
                        f"EMBED WARNING: cuda encode failed (attempt {attempt + 1}/3): {e}",
                        flush=True,
                    )
                    import torch

                    torch.cuda.empty_cache()
                    bs = max(1, bs // 4)  # ★降批重试
            if vecs is None:
                if self._device != "cuda":
                    raise RuntimeError("embed failed on cpu, no fallback left")
                # ★GPU重试也救不回来(不只是简单OOM, 可能是驱动/上下文级故障) → 强制卸载重建成
                #   纯CPU模型, 把这次请求做完, 不让它彻底失败("不能停"). 不去手动"修复"GPU本身
                #   (那是驱动层的事, 应用层做不到) —— 卸载CPU化之后, 空闲超时会整体卸载, 下次
                #   新请求重新走_pick_device()探测, GPU若已恢复会自然切回去, 这就是"自愈".
                print(
                    "EMBED WARNING: GPU embedding broken after retries, forcing CPU reload",
                    flush=True,
                )
                self._model = None
                self._device = None
                import torch

                torch.cuda.empty_cache()
                self._load(force_device="cpu")
                vecs = self._model.encode(list(texts), normalize_embeddings=True, batch_size=bs)
            out = [v[:DIM].tolist() for v in vecs]
            # 长文本大 batch 的激活会被 torch 缓存分配器留着(可达数G), 每次编码后立刻还给显存,
            # 稳态只留模型(~2G), 免得挤占 OCR 用卡.
            if self._device == "cuda":
                import torch

                torch.cuda.empty_cache()
            return out, self._device or "cpu"

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
