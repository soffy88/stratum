"""Operator CLI: build one deck without the job table.

    python -m stratum.services.ppt_export.cli <substrate_id> --style paper-notes \
        --pages 12 [--chapter ch2] [--run-id br_...] --out /tmp/deck [--renderer libreoffice]

Reads the book's stored understanding, writes deck.json with the configured
model (``PPT_LLM_*``, default veya-fllm), renders with luobo-ppt and prints a
JSON summary. Nothing is written to the database.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from stratum.services.ppt_export.deck_builder import DEFAULT_PAGES, DeckOptions, build_deck
from stratum.services.ppt_export.engine import render_deck
from stratum.services.ppt_export.llm import ppt_provider_config, resolve_ppt_provider
from stratum.services.ppt_export.material import load_material
from stratum.services.ppt_export.styles import DEFAULT_STYLE


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ppt-export")
    ap.add_argument("substrate_id")
    ap.add_argument("--style", default=DEFAULT_STYLE)
    ap.add_argument("--pages", type=int, default=DEFAULT_PAGES)
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--audience", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--renderer", default=None, choices=["lite", "libreoffice"])
    a = ap.parse_args(argv)

    t0 = time.time()

    def progress(stage: str, frac: float) -> None:
        print(f"[{time.time() - t0:6.1f}s] {stage} {frac:.0%}", file=sys.stderr, flush=True)

    material = load_material(a.substrate_id, run_id=a.run_id)
    opts = DeckOptions(pages=a.pages, chapter_id=a.chapter, audience=a.audience)
    deck, report = build_deck(material, opts, resolve_ppt_provider(), progress=progress)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "deck.generated.json").write_text(
        json.dumps(deck, ensure_ascii=False, indent=1), "utf-8"
    )
    result = render_deck(deck, a.style, out / "work", renderer=a.renderer, progress=progress)
    summary = {
        "book": material.title,
        "run_id": material.run_id,
        "bu_status": material.bu_status,
        "language": material.language,
        "model": ppt_provider_config(),
        "slides": len(deck["slides"]),
        "pptx": str(result.pptx),
        "previews": [str(p) for p in result.previews],
        "renderer": result.renderer,
        "qa": result.qa.get("counts"),
        "qa_errors": [i for i in result.qa.get("issues", []) if i.get("level") == "ERROR"],
        "fixes": result.fixes,
        "model_calls": report.model_calls,
        "language_retries": report.language_retries,
        "fallback_slides": report.fallback_slides,
        "titles_polished": report.titles_polished,
        "warnings": report.warnings,
        "seconds": round(time.time() - t0, 1),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if result.qa_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
