"""P12 §12 human-evaluation corpus.

Five real books across five disciplines, each with an expectation written before
any run against it. The point is stated in §12: without this, every improvement
is measured only on Thomas Calculus, and a detector or model that suits one
bilingual textbook would be reported as a general gain.

`corpus.json` records the gap honestly: the warehouse has no biology or
chemistry title with extracted text, so those two requested disciplines are
absent rather than substituted with something mislabelled.
"""

from __future__ import annotations

import json
from pathlib import Path

CORPUS_PATH = Path(__file__).with_name("corpus.json")


def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def book(substrate_id: str) -> dict:
    for entry in load_corpus()["books"]:
        if entry["id"] == substrate_id:
            return entry
    raise KeyError(f"{substrate_id} is not in the P12 evaluation corpus")


def disciplines() -> list[str]:
    return [b["discipline"] for b in load_corpus()["books"]]
