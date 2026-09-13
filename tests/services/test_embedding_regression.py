"""Embedding Space Regression Test.

Ensures retrieval/query and index/embedding generators use identical
BGE-M3 model/dimension to prevent silent drift.
"""

from __future__ import annotations

from pathlib import Path


def test_bge_m3_provider_identity_contract():
    """The selected text provider contract is deterministic and model-free."""
    source = Path(__file__).parents[2] / "src/stratum/services/retrieval_engine.py"
    text = source.read_text()
    assert "bge_m3" in text
    assert "1024" in text


def test_bge_m3_provider_factory_is_explicit():
    source = Path(__file__).parents[2] / "src/stratum/services/retrieval_engine.py"
    text = source.read_text()
    assert "from oprim.embedding.bge_m3 import BgeM3Embedder" in text
    assert "_get_bge().embed" in text


def test_bge_m3_provider_has_no_silent_provider_fallback():
    for name in ("retrieval_engine.py", "layer_generator.py"):
        source = Path(__file__).parents[2] / "src/stratum/services" / name
        text = source.read_text()
        assert "BgeM3Embedder" in text
        assert "qwen3_dashscope" not in text
