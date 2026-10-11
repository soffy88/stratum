"""The 14 luobo-ppt style presets, read from the vendored index."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_VENDOR = Path(__file__).resolve().parents[4] / "vendor" / "luobo_ppt"
_IMAGE_VENDOR = Path("/app/vendor/luobo_ppt")


class LuoboUnavailable(RuntimeError):
    """The vendored luobo-ppt tree cannot be found."""


def luobo_home() -> Path:
    """Locate the vendored skill.

    ``LUOBO_PPT_HOME`` wins; otherwise the repository checkout, then the path
    the backend image copies it to.
    """
    env = os.environ.get("LUOBO_PPT_HOME", "").strip()
    candidates = [Path(env)] if env else []
    candidates += [_REPO_VENDOR, _IMAGE_VENDOR]
    for c in candidates:
        if (c / "scripts" / "pipeline.py").is_file():
            return c
    raise LuoboUnavailable(
        "luobo-ppt not found; set LUOBO_PPT_HOME or ship vendor/luobo_ppt with the backend"
    )


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, Any], ...]:
    data = json.loads((luobo_home() / "references" / "styles" / "index.json").read_text("utf-8"))
    return tuple(data.get("styles", []))


def list_styles() -> list[dict[str, Any]]:
    """Public view of the presets: id, Chinese name, scheme and what it suits."""
    return [
        {
            "id": s["id"],
            "name": s.get("name", s["id"]),
            "scheme": s.get("scheme", "light"),
            "mood": s.get("mood", ""),
            "best_for": s.get("best_for", ""),
            "avoid_for": s.get("avoid_for", ""),
        }
        for s in _index()
    ]


def style_ids() -> set[str]:
    return {s["id"] for s in _index()}


DEFAULT_STYLE = "paper-notes"
