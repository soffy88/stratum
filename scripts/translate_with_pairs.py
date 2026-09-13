"""Run pdf2zh-next externally while recording only main document calls."""

from __future__ import annotations

import os
import sys
import uuid
import multiprocessing

from stratum.services.translation_pair_recorder import RecordingTranslator, TranslationPairRecorder

import pdf2zh_next.high_level as high_level
from pdf2zh_next.main import cli

if sys.platform != "win32":
    try:
        multiprocessing.set_start_method("fork")
    except RuntimeError:
        pass

recorder = TranslationPairRecorder(
    os.environ.get("AII_TRANSLATION_RUN_ID", uuid.uuid4().hex),
    provider="pdf2zh-next",
    provider_version="2.9.0",
    source_lang=os.environ.get("AII_TRANSLATION_SOURCE_LANG", "en"),
    target_lang=os.environ.get("AII_TRANSLATION_TARGET_LANG"),
)
original_create = high_level.create_babeldoc_config
original_wrapper = high_level._translate_wrapper


def create_config(settings, file):
    config = original_create(settings, file)
    # Keep term_extraction_translator untouched.  Only document calls use the
    # recorder, even when BabelDOC would otherwise reuse the same instance.
    config.translator = RecordingTranslator(config.translator, recorder)
    return config


high_level.create_babeldoc_config = create_config


def translate_wrapper(*args, **kwargs):
    # pdf2zh-next executes BabelDOC in a child process.  The recorder is
    # intentionally process-local; write it from that child after the real
    # translator completes instead of pretending a parent append is ordered.
    try:
        return original_wrapper(*args, **kwargs)
    finally:
        output = os.environ.get("AII_TRANSLATION_PAIRS_OUTPUT")
        if output:
            recorder.write(output)


high_level._translate_wrapper = translate_wrapper
try:
    cli()
finally:
    pass
