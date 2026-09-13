"""Main-process, object-injection qualification for pdf2zh-next."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import sys
from pathlib import Path

import pdf2zh_next.high_level as high_level
from pdf2zh_next.config import ConfigManager
from stratum.services.translation_pair_recorder import RecordingTranslator, TranslationPairRecorder


async def run() -> int:
    settings = ConfigManager().initialize_config()
    pdf = Path(next(iter(settings.basic.input_files)))
    config = high_level.create_babeldoc_config(settings, pdf)
    base = config.translator
    recorder = TranslationPairRecorder(
        os.environ.get("AII_TRANSLATION_RUN_ID", "main-process-qualification"),
        provider=type(base).__name__,
        provider_version="2.9.0",
        source_lang=settings.translation.lang_in,
        target_lang=settings.translation.lang_out,
    )
    recorder.sentinel_path = os.environ.get("AII_TRANSLATION_SENTINEL_PATH")
    config.translator = RecordingTranslator(base, recorder)
    print("PID=", os.getpid())
    print("BASE_TRANSLATOR_CLASS=", type(base).__name__)
    print("BASE_TRANSLATOR_MODULE=", type(base).__module__)
    print("BASE_TRANSLATOR_MRO=", [f"{c.__module__}.{c.__name__}" for c in type(base).__mro__])
    print("TRANSLATE_SIGNATURE=", inspect.signature(base.translate))
    print("CONFIG_TRANSLATOR_BEFORE=", type(base).__name__)
    print("CONFIG_TRANSLATOR_AFTER=", type(config.translator).__name__)
    print("CONFIG_IS_RECORDER=", isinstance(config.translator, RecordingTranslator))
    print("RECORDER_INNER_ID_MATCH=", config.translator.inner is base)
    async for event in high_level.babeldoc_translate(config):
        if event.get("type") == "finish":
            break
    output = os.environ.get("AII_TRANSLATION_PAIRS_OUTPUT")
    if output:
        recorder.write(output)
    print("RECORDER_CALLS=", recorder.calls)
    print("RECORDED_PAIRS=", len(recorder.pairs))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
