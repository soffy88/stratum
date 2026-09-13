"""Provider-boundary capture for real document translation calls."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TranslationPair:
    run_id: str
    ordinal: int
    source_text: str
    translated_text: str
    source_text_hash: str
    translated_text_hash: str
    provider: str
    provider_version: str
    source_lang: str | None = None
    target_lang: str | None = None


class TranslationPairRecorder:
    def __init__(
        self,
        run_id: str,
        *,
        provider: str,
        provider_version: str,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.provider = provider
        self.provider_version = provider_version
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._lock = threading.Lock()
        self._next_ordinal = 0
        self.pairs: list[TranslationPair] = []
        self.calls = 0
        self.sentinel_path = None

    def sentinel(self, source_text: Any) -> None:
        """Write a process-local proof that the wrapped entrypoint ran."""
        if not self.sentinel_path:
            return
        event = {
            "pid": __import__("os").getpid(),
            "source_length": len(source_text) if isinstance(source_text, str) else None,
            "source_hash": hashlib.sha256(source_text.encode()).hexdigest()
            if isinstance(source_text, str)
            else None,
        }
        with self._lock:
            path = Path(self.sentinel_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record(self, source_text: str, translated_text: str) -> None:
        if not isinstance(source_text, str) or not isinstance(translated_text, str):
            return
        with self._lock:
            ordinal = self._next_ordinal
            self._next_ordinal += 1
            self.pairs.append(
                TranslationPair(
                    self.run_id,
                    ordinal,
                    source_text,
                    translated_text,
                    hashlib.sha256(source_text.encode()).hexdigest(),
                    hashlib.sha256(translated_text.encode()).hexdigest(),
                    self.provider,
                    self.provider_version,
                    self.source_lang,
                    self.target_lang,
                )
            )

    def write(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps([asdict(p) for p in self.pairs], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class RecordingTranslator:
    """Transparent decorator for BabelDOC's translator object."""

    def __init__(self, inner: Any, recorder: TranslationPairRecorder) -> None:
        self.inner = inner
        self.recorder = recorder

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def translate(
        self, text: str, ignore_cache: bool = False, rate_limit_params: dict | None = None
    ) -> str:
        self.recorder.sentinel(text)
        self.recorder.calls += 1
        translated = self.inner.translate(
            text, ignore_cache=ignore_cache, rate_limit_params=rate_limit_params
        )
        self.recorder.record(text, translated)
        return translated

    def llm_translate(
        self, text: str, ignore_cache: bool = False, rate_limit_params: dict | None = None
    ) -> str:
        """Proxy the concrete pdf2zh-next entrypoint without treating its
        batch prompt as a document pair.  Batch response extraction is owned
        by the version-pinned adapter, not this transparent protocol proxy.
        """
        self.recorder.sentinel(text)
        self.recorder.calls += 1
        result = self.inner.llm_translate(
            text, ignore_cache=ignore_cache, rate_limit_params=rate_limit_params
        )
        # BabelDOC's LLM-only path sends a JSON batch inside a prompt and
        # returns a JSON batch.  Extract only records carrying an input/output
        # identity; prompts without that shape (term/helper traffic) are not
        # recorded as document pairs.
        try:
            source_items = _json_batch(text, "input")
            translated_items = _json_batch(result, "output")
            by_id = {
                item.get("id"): item for item in translated_items if item.get("id") is not None
            }
            for index, item in enumerate(source_items):
                translated = by_id.get(item.get("id"))
                if translated is None and index < len(translated_items):
                    translated = translated_items[index]
                if (
                    translated
                    and isinstance(item.get("input"), str)
                    and isinstance(translated.get("output"), str)
                ):
                    self.recorder.record(item["input"], translated["output"])
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return result


def _json_batch(value: str, field: str) -> list[dict[str, object]]:
    """Extract the document batch, excluding the prompt's example JSON.

    BabelDOC sends a prompt containing both an example and a final JSON batch.
    Only a top-level decoded list whose items contain ``field`` is eligible;
    recursively walking every nested object can pair the example with the
    actual response and corrupt provenance.
    """
    candidates: list[list[dict[str, object]]] = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", value or ""):
        try:
            obj, _ = decoder.raw_decode(value[match.start() :])
        except (ValueError, json.JSONDecodeError):
            continue
        if isinstance(obj, list) and obj and all(isinstance(item, dict) for item in obj):
            records = [item for item in obj if isinstance(item.get(field), str)]
            if records:
                candidates.append(records)
    return candidates[-1] if candidates else []
