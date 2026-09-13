"""Provider boundary for visual embeddings; no retrieval code knows model internals."""

from __future__ import annotations

from abc import ABC, abstractmethod
import math
from typing import Sequence

from stratum.config import (
    AII_VISUAL_EMBED_BACKEND,
    AII_VISUAL_EMBED_BASE_URL,
    AII_VISUAL_EMBED_DIM,
    AII_VISUAL_EMBED_MODEL,
    AII_VISUAL_EMBED_TIMEOUT,
)


class VisualEmbeddingUnavailable(RuntimeError):
    """The configured visual execution backend cannot serve this request."""


class VisualEmbeddingProvider(ABC):
    model: str
    dimension: int

    @abstractmethod
    def embed_image(self, image_path: str) -> list[float]: ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]: ...

    def embed_images(self, image_paths: Sequence[str]) -> list[list[float]]:
        """Batch contract; the default preserves compatibility with old adapters."""
        return [self.embed_image(path) for path in image_paths]

    def model_identity(self) -> dict[str, object]:
        return {"provider": type(self).__name__, "model": self.model, "dimension": self.dimension}

    def health(self) -> dict[str, object]:
        return {"ready": True, **self.model_identity()}

    def validate(self, vector: Sequence[float]) -> list[float]:
        values = [float(x) for x in vector]
        if len(values) != self.dimension or not values or not all(math.isfinite(x) for x in values):
            raise ValueError(f"visual embedding must be finite and dimension={self.dimension}")
        return values


class Qwen3VLEmbeddingProvider(VisualEmbeddingProvider):
    """Lazy SentenceTransformers adapter for the official Qwen model."""

    model = AII_VISUAL_EMBED_MODEL
    dimension = AII_VISUAL_EMBED_DIM

    def __init__(self) -> None:
        self._runtime = None
        self.device = None
        self.dtype = None

    def _load_runtime(self):
        if self._runtime is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "ProviderUnavailable: install sentence-transformers[image]"
                ) from exc
            import os

            model_id = self.model if "/" in self.model else f"Qwen/{self.model}"
            requested_device = os.environ.get("AII_VISUAL_EMBED_DEVICE")
            if requested_device:
                device = requested_device
            else:
                try:
                    import torch

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            if device.startswith("cuda"):
                try:
                    import torch

                    if not torch.cuda.is_available():
                        raise VisualEmbeddingUnavailable("CUDA requested but unavailable")
                except ImportError as exc:
                    raise VisualEmbeddingUnavailable(
                        "CUDA requested but torch is unavailable"
                    ) from exc
            production = os.environ.get("STRATUM_ENV", "").lower() == "production"
            if production and device == "cpu":
                raise VisualEmbeddingUnavailable(
                    "local visual backend cannot use CPU in production"
                )
            self.device = device
            self._runtime = SentenceTransformer(model_id, device=device)
            try:
                self.dtype = str(next(self._runtime.parameters()).dtype)
            except (AttributeError, StopIteration):
                self.dtype = None
        return self._runtime

    def embed_image(self, image_path: str) -> list[float]:
        vector = self._load_runtime().encode(
            [image_path], convert_to_numpy=True, normalize_embeddings=True
        )[0]
        return self.validate(vector.tolist())

    def embed_query(self, query: str) -> list[float]:
        vector = self._load_runtime().encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        )[0]
        return self.validate(vector.tolist())

    def model_identity(self) -> dict[str, object]:
        return {
            "provider": "qwen3-vl",
            "model": self.model,
            "dimension": self.dimension,
            "backend": "local",
            "device": self.device or "uninitialized",
            "dtype": self.dtype,
        }


class RemoteVisualEmbeddingProvider(VisualEmbeddingProvider):
    """Provider-neutral HTTP boundary for a GPU/remote visual embedding service."""

    model = AII_VISUAL_EMBED_MODEL
    dimension = AII_VISUAL_EMBED_DIM

    def __init__(
        self, base_url: str = AII_VISUAL_EMBED_BASE_URL, timeout: float = AII_VISUAL_EMBED_TIMEOUT
    ) -> None:
        if not base_url:
            raise VisualEmbeddingUnavailable(
                "remote visual backend requires AII_VISUAL_EMBED_BASE_URL"
            )
        self.base_url = base_url
        self.timeout = timeout

    def _request(
        self, *, images: list[str] | None = None, texts: list[str] | None = None
    ) -> list[list[float]]:
        try:
            import httpx

            response = httpx.post(
                f"{self.base_url}/v1/visual-embeddings",
                json={"model": self.model, "images": images or [], "texts": texts or []},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise VisualEmbeddingUnavailable(f"remote visual provider unavailable: {exc}") from exc
        if payload.get("model") != self.model or payload.get("dimension") != self.dimension:
            raise VisualEmbeddingUnavailable("remote visual provider identity mismatch")
        vectors = payload.get("embeddings")
        expected = len(images or []) + len(texts or [])
        if not isinstance(vectors, list) or len(vectors) != expected:
            raise VisualEmbeddingUnavailable(
                "remote visual provider returned wrong embedding count"
            )
        try:
            return [self.validate(vector) for vector in vectors]
        except (TypeError, ValueError) as exc:
            raise VisualEmbeddingUnavailable(
                f"remote visual provider returned invalid vector: {exc}"
            ) from exc

    def embed_images(self, image_paths: Sequence[str]) -> list[list[float]]:
        return self._request(images=list(image_paths))

    def embed_image(self, image_path: str) -> list[float]:
        return self.embed_images([image_path])[0]

    def embed_query(self, query: str) -> list[float]:
        return self._request(texts=[query])[0]

    def model_identity(self) -> dict[str, object]:
        return {
            "provider": "qwen3-vl",
            "model": self.model,
            "dimension": self.dimension,
            "backend": "remote",
            "device": self.base_url,
        }


def get_visual_embedding_provider() -> VisualEmbeddingProvider:
    # Keep one model identity for both index and query construction.
    if AII_VISUAL_EMBED_BACKEND == "remote":
        return RemoteVisualEmbeddingProvider()
    if AII_VISUAL_EMBED_BACKEND != "local":
        raise VisualEmbeddingUnavailable(
            f"unknown visual embedding backend: {AII_VISUAL_EMBED_BACKEND}"
        )
    return Qwen3VLEmbeddingProvider()


def test_visual_embedding_runtime_identity(provider: VisualEmbeddingProvider | None = None) -> None:
    """Runtime identity check used by index/query jobs and integration tests."""
    p = provider or get_visual_embedding_provider()
    if p.model != AII_VISUAL_EMBED_MODEL or p.dimension != AII_VISUAL_EMBED_DIM:
        raise AssertionError("visual index/query model identity mismatch")
    p.validate([0.0] * p.dimension)
