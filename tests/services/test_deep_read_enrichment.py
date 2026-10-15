from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from stratum.services.bu_v2_provider import ModelResponse, ProviderError
from stratum.services.deep_read_enrichment import (
    _ROUNDS,
    _source_excerpt,
    build_deep_read,
    enabled_for_ingest,
    enrich_file,
)


class FakeProvider:
    name = "mock-veya-fllm"

    def __init__(self, *, wrong_count: bool = False) -> None:
        self.prompts: list[str] = []
        self.calls: list[dict[str, object]] = []
        self.wrong_count = wrong_count

    def complete(self, prompt: str, **kwargs: object) -> ModelResponse:
        marker = _ROUNDS[min(len(self.calls), len(_ROUNDS) - 1)]
        self.prompts.append(prompt)
        self.calls.append(kwargs)
        count = marker["count"] - (1 if self.wrong_count else 0)
        payload = {
            "summary": f"摘要：{marker['key']}",
            "items": [
                {
                    "question": f"{marker['key']} 问题 {i + 1}？",
                    "answer": f"基于来源的回答 {i + 1}。",
                    "evidence": ["来源中的线索"],
                    "confidence": 0.8,
                }
                for i in range(count)
            ],
        }
        return ModelResponse(json.dumps(payload, ensure_ascii=False), "mock-model", self.name)


def test_default_auto_enrichment_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRATUM_DEEP_READ_ENABLED", raising=False)
    assert enabled_for_ingest() is False
    monkeypatch.setenv("STRATUM_DEEP_READ_ENABLED", "ON")
    assert enabled_for_ingest() is True


def test_builds_12_items_in_three_context_carrying_rounds() -> None:
    provider = FakeProvider()
    result = build_deep_read(
        "第一段。\n关键论点在第二段。\n结论在最后。",
        title="示例文章",
        source_uri="https://example.test/a",
        source_kind="article",
        provider=provider,
    )
    assert [len(round_data["items"]) for round_data in result["rounds"]] == [4, 5, 3]
    assert result["question_count"] == 12
    assert result["supplement_targets"] == ["BU2", "KU"]
    assert result["authority"] == "supplement_only_canonical_BU_KU_unchanged"
    assert "摘要：overview" in provider.prompts[1]
    assert "摘要：deep_dive" in provider.prompts[2]
    assert len(provider.calls) == 3
    assert all(call["json_mode"] is True for call in provider.calls)


def test_rejects_incomplete_round_instead_of_writing_false_12_question_result() -> None:
    with pytest.raises(ProviderError, match="expected exactly"):
        build_deep_read("source text", title="bad result", provider=FakeProvider(wrong_count=True))


def test_long_book_text_samples_beginning_middle_and_end() -> None:
    excerpt, sampled = _source_excerpt("START" + ("x" * 30000) + "MIDDLE" + ("y" * 30000) + "END")
    assert sampled is True
    assert "开头" in excerpt and "中段" in excerpt and "结尾" in excerpt
    assert "START" in excerpt and "END" in excerpt
    assert len(excerpt) <= 18000 + 100


def test_markdown_file_writes_traceable_json_and_is_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "article.md"
    source.write_text(
        '---\ntitle: "Example article"\ndoc_kind: article\nsource_url: "https://example.test/a"\n---\n\n# Example article\n\nBody of the article.',
        encoding="utf-8",
    )
    provider = FakeProvider()
    output = enrich_file(source, provider=provider)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert output.name == "article.deep-read.json"
    assert payload["source"]["title"] == "Example article"
    assert payload["source"]["uri"] == "https://example.test/a"
    assert payload["source"]["kind"] == "article"
    assert payload["question_count"] == 12
    assert len(provider.prompts) == 3
    assert enrich_file(source, provider=FakeProvider()).read_bytes() == output.read_bytes()


def test_epub_is_read_as_a_book(tmp_path: Path) -> None:
    source = tmp_path / "sample.epub"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>',
        )
        archive.writestr(
            "OPS/book.opf",
            '<package><metadata><title>Sample Book</title></metadata><manifest><item id="c1" href="chapter1.xhtml"/></manifest><spine><itemref idref="c1"/></spine></package>',
        )
        archive.writestr(
            "OPS/chapter1.xhtml",
            "<html><body><h1>Chapter One</h1><p>A book claim.</p><script>ignore me</script></body></html>",
        )
    output = enrich_file(source, provider=FakeProvider())
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"]["title"] == "Sample Book"
    assert payload["source"]["kind"] == "book"
    assert payload["question_count"] == 12


def test_web_ingest_does_not_run_enrichment_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    import stratum.services.web_ingest as web_ingest

    monkeypatch.setenv("STRATUM_AII_INTAKE_DIR", str(tmp_path))
    monkeypatch.delenv("STRATUM_DEEP_READ_ENABLED", raising=False)
    monkeypatch.setattr(
        web_ingest,
        "_fetch",
        lambda *args, **kwargs: (
            SimpleNamespace(
                success=True,
                markdown="# Ingested\n\nExample body.",
                title="Ingested Article",
                author="",
                published="",
                strategy="fake",
                error=None,
            ),
            "web",
        ),
    )
    result = web_ingest.ingest_url("https://example.test/default")
    assert result.success is True
    assert result.deep_read_path == ""
    assert list(tmp_path.glob("*.md"))
    assert not list(tmp_path.glob("*.deep-read.json"))


def test_web_ingest_runs_enrichment_only_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    import stratum.services.deep_read_enrichment as deep_read
    import stratum.services.web_ingest as web_ingest

    monkeypatch.setenv("STRATUM_AII_INTAKE_DIR", str(tmp_path))
    monkeypatch.setenv("STRATUM_DEEP_READ_ENABLED", "1")
    monkeypatch.setattr(
        web_ingest,
        "_fetch",
        lambda *args, **kwargs: (
            SimpleNamespace(
                success=True,
                markdown="# Enabled\n\nExample body.",
                title="Enabled Article",
                author="",
                published="",
                strategy="fake",
                error=None,
            ),
            "web",
        ),
    )
    seen: list[Path] = []

    def fake_enrich(source: str | Path, **kwargs: object) -> Path:
        seen.append(Path(source))
        sidecar = Path(source).with_name(f"{Path(source).stem}.deep-read.json")
        sidecar.write_text('{"question_count": 12}\n', encoding="utf-8")
        return sidecar

    monkeypatch.setattr(deep_read, "enrich_file", fake_enrich)
    result = web_ingest.ingest_url("https://example.test/enabled")
    assert result.success is True
    assert result.deep_read_path.endswith(".deep-read.json")
    assert len(seen) == 1
    assert seen[0].is_file()
    assert Path(result.deep_read_path).is_file()
