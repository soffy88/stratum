"""Drive the vendored luobo-ppt scripts on a deck.json.

Every step is a subprocess of the backend's own interpreter, so the API process
never imports the skill's modules (they rely on ``sys.path`` tricks and generic
module names such as ``common``). Steps:

    style_previews --apply  -> outline_check -> plan_deck --level full
    -> pipeline --procedural [--lite]  (make_assets, build_deck, render, qa_check, review)

Illustrations are always procedural: no image model, no network. Previews use
LibreOffice when ``PPT_PREVIEW_RENDERER=libreoffice`` and it is installed;
otherwise luobo-ppt's own approximate renderer. QA (overflow, overlap, text that
did not make it onto a slide) does not depend on the renderer.

When QA or the outline check reports a slide that does not fit, the slide is
moved to the roomier layout the check suggests (or trimmed) and only the
affected steps are re-run, at most twice.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stratum.services.ppt_export.fit import trim
from stratum.services.ppt_export.styles import luobo_home, style_ids

STEP_TIMEOUT = int(os.environ.get("PPT_STEP_TIMEOUT_S", "600"))
_OUTLINE_LINE = re.compile(r"^\[(ERROR|WARN)\]\s*第\s*(\d+)\s*页[：:]\s*(.*)$")
_SUGGEST = re.compile(r"可改用\s*([a-z_]+)")
# Layouts that accept the generic {title, items[{title,text}]} shape.
_ROOMY = {"definitions", "grid", "process"}
_FIT_ROUNDS = 2


class EngineError(RuntimeError):
    pass


@dataclass
class EngineResult:
    work: Path
    pptx: Path
    previews: list[Path]
    sheet: Path | None
    qa: dict[str, Any]
    outline: list[tuple[str, int, str]]
    renderer: str
    fixes: list[str] = field(default_factory=list)

    @property
    def qa_errors(self) -> int:
        return int((self.qa.get("counts") or {}).get("ERROR", 0))

    @property
    def qa_warnings(self) -> int:
        return int((self.qa.get("counts") or {}).get("WARN", 0))


def _run(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    path = luobo_home() / "scripts" / script
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    try:
        return subprocess.run(
            [sys.executable, str(path), *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"{script} timed out after {STEP_TIMEOUT}s") from exc


def _check(cp: subprocess.CompletedProcess[str], step: str) -> None:
    if cp.returncode != 0:
        tail = (cp.stdout or "")[-600:] + (cp.stderr or "")[-600:]
        raise EngineError(f"{step} failed (exit {cp.returncode}): {tail.strip()}")


def parse_outline(stdout: str) -> list[tuple[str, int, str]]:
    out = []
    for line in (stdout or "").splitlines():
        m = _OUTLINE_LINE.match(line.strip())
        if m:
            out.append((m.group(1), int(m.group(2)), m.group(3)))
    return out


_SIDE_LAYOUTS = {"rows_side", "side_cards"}


def _set_layout(slide: dict[str, Any], layout: str) -> None:
    """Switch layout and drop fields the new layout does not draw.

    luobo-ppt's QA requires every deck.json string to reach the slide, so a
    side panel left on a slide moved to ``list_icons`` is a fidelity error.
    """
    slide["layout"] = layout
    if layout not in _SIDE_LAYOUTS and "side" in slide:
        slide.pop("side")


def _shrink(slide: dict[str, Any]) -> bool:
    """Drop the last item and tighten text; True when something changed."""
    changed = False
    items = slide.get("items")
    if isinstance(items, list) and len(items) > 2:
        slide["items"] = items[:-1]
        changed = True
    if isinstance(slide.get("blocks"), list) and len(slide["blocks"]) > 3:
        slide["blocks"] = slide["blocks"][:-1]
        changed = True
    for side in ("left", "right"):
        s = slide.get(side)
        if isinstance(s, dict) and isinstance(s.get("items"), list) and len(s["items"]) > 2:
            s["items"] = s["items"][:-1]
            changed = True
    for key in ("body", "takeaway"):
        if isinstance(slide.get(key), str) and len(slide[key]) > 12:
            slide[key] = trim(slide[key], max(10, int(len(slide[key]) * 0.7)))
            changed = True
    return changed


def apply_outline_fixes(deck: dict[str, Any], issues: list[tuple[str, int, str]]) -> list[str]:
    """Act on capacity warnings from outline_check; returns what was changed."""
    fixes = []
    by_n = {s.get("n"): s for s in deck.get("slides", [])}
    for _level, n, msg in issues:
        if "装不下" not in msg:
            continue
        slide = by_n.get(n)
        if not slide:
            continue
        m = _SUGGEST.search(msg)
        if m and not slide.get("layout"):
            _set_layout(slide, m.group(1))
            fixes.append(f"slide {n}: layout -> {m.group(1)}")
        elif _shrink(slide):
            fixes.append(f"slide {n}: shortened")
    return fixes


def apply_qa_fixes(deck: dict[str, Any], qa: dict[str, Any]) -> list[str]:
    """Act on QA errors (overflow / overlap / rail) by changing the slide."""
    fixes = []
    bad = sorted(
        {
            int(i.get("slide") or 0)
            for i in qa.get("issues", [])
            if i.get("level") == "ERROR"
            and i.get("check") in ("overflow", "overlap", "rail", "fidelity")
        }
    )
    by_n = {s.get("n"): s for s in deck.get("slides", [])}
    for n in bad:
        slide = by_n.get(n)
        if not slide:
            continue
        fidelity = any(
            i.get("check") == "fidelity" and int(i.get("slide") or 0) == n
            for i in qa.get("issues", [])
        )
        if fidelity and "side" in slide and slide.get("layout") not in (None, *_SIDE_LAYOUTS):
            slide.pop("side")
            fixes.append(f"slide {n}: dropped side panel the layout cannot show")
        elif slide.get("type") in _ROOMY and slide.get("layout") != "list_icons":
            _set_layout(slide, "list_icons")
            fixes.append(f"slide {n}: layout -> list_icons")
        elif _shrink(slide):
            fixes.append(f"slide {n}: shortened")
    return fixes


def _write(work: Path, deck: dict[str, Any]) -> None:
    (work / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), "utf-8")


def render_deck(
    deck: dict[str, Any],
    style: str,
    work: Path,
    *,
    renderer: str | None = None,
    progress: Callable[[str, float], None] | None = None,
) -> EngineResult:
    """Turn ``deck`` into ``work/out/beautified.pptx`` with previews and QA."""
    if style not in style_ids():
        raise EngineError(f"unknown style {style!r}")
    work.mkdir(parents=True, exist_ok=True)
    renderer = (renderer or os.environ.get("PPT_PREVIEW_RENDERER") or "lite").lower()
    use_soffice = renderer == "libreoffice" and shutil.which("soffice") is not None

    _write(work, deck)
    _check(_run("style_previews.py", str(work), "--apply", style, cwd=work), "style")

    if progress:
        progress("checking", 0.0)
    cp = _run("outline_check.py", str(work), cwd=work)
    outline = parse_outline(cp.stdout)
    fixes = apply_outline_fixes(deck, outline)
    if fixes:
        _write(work, deck)

    qa: dict[str, Any] = {}
    for round_no in range(_FIT_ROUNDS + 1):
        if progress:
            progress("designing", round_no / (_FIT_ROUNDS + 1))
        plan_args = [str(work), "--level", "full"]
        if round_no:
            plan_args.append("--reset")
        _check(_run("plan_deck.py", *plan_args, cwd=work), "plan")
        pipe_args = [str(work), "--procedural"]
        if not use_soffice:
            pipe_args.append("--lite")
        cp = _run("pipeline.py", *pipe_args, cwd=work)
        report = work / "out" / "qa_report.json"
        pptx = work / "out" / "beautified.pptx"
        if not pptx.is_file() or not report.is_file():
            _check(cp, "pipeline")
            raise EngineError("pipeline produced no deck")
        qa = json.loads(report.read_text("utf-8"))
        if not (qa.get("counts") or {}).get("ERROR"):
            break
        if round_no == _FIT_ROUNDS:
            break
        more = apply_qa_fixes(deck, qa)
        if not more:
            break
        fixes += more
        _write(work, deck)

    previews = sorted((work / "out" / "png").glob("slide-*.png"))
    sheet = work / "out" / "sheet.png"
    return EngineResult(
        work=work,
        pptx=work / "out" / "beautified.pptx",
        previews=previews,
        sheet=sheet if sheet.is_file() else None,
        qa=qa,
        outline=outline,
        renderer="libreoffice" if use_soffice else "lite",
        fixes=fixes,
    )
