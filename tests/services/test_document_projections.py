from stratum.services.artifact_provenance import content_hash
from stratum.services.visual_embedding import Qwen3VLEmbeddingProvider
from stratum.services.translation_alignment import align_fragment


def test_optional_integrations_disabled_boot_cleanly():
    from stratum.config import (
        AII_ARTIFACT_PROVENANCE_ENABLED,
        AII_PDF_TRANSLATION_ENABLED,
        AII_VISUAL_RETRIEVAL_ENABLED,
    )
    from stratum.services.knowledge_view import KnowledgeViewRequest

    assert not AII_VISUAL_RETRIEVAL_ENABLED
    assert not AII_PDF_TRANSLATION_ENABLED
    assert not AII_ARTIFACT_PROVENANCE_ENABLED
    assert KnowledgeViewRequest(query="boot").query == "boot"


def test_visual_provider_runtime_identity_and_finite_dimension():
    provider = Qwen3VLEmbeddingProvider()
    assert provider.model == "Qwen3-VL-Embedding-2B"
    assert len(provider.validate([0.0] * provider.dimension)) == provider.dimension


def test_visual_provider_rejects_placeholder_shape_and_nonfinite():
    provider = Qwen3VLEmbeddingProvider()
    try:
        provider.validate([float("nan")])
        assert False
    except ValueError:
        pass


def test_visual_provider_runtime_is_lazy_and_no_placeholder_fallback():
    provider = Qwen3VLEmbeddingProvider()
    assert provider._runtime is None


def test_artifact_hash_is_a_derived_contract():
    assert content_hash("same") == content_hash("same")


def test_translation_alignment_retains_original_range():
    alignment = align_fragment("energy", "energie")
    assert alignment["alignment_version"] == "v1"
    assert alignment["original_range"] == {"start": 0, "end": 6}
